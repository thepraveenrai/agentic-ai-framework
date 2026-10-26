"""Web Observability Studio and Multi-Agent Control Center.

Provides an ultra-modern, interactive localhost web application allowing developers
to trigger, monitor, inspect, and approve multi-agent engineering workflows with
real-time animated visual pipelines.
"""

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from agentic_framework.config import settings
from agentic_framework.core.hitl import hitl_manager, ActionRiskLevel, HITLDecision
from agentic_framework.mcp.tools import tool_registry
from agentic_framework.observability.logger import AgentLogger, logger
from agentic_framework.observability.tracer import tracer
from agentic_framework.orchestrator.graph import orchestrator

# Resolve paths for web frontend assets
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
ROOT_WEB_DIR = PROJECT_ROOT / "web"
LOCAL_STATIC_DIR = BASE_DIR / "static"

if ROOT_WEB_DIR.exists():
    WEB_DIR = ROOT_WEB_DIR
elif LOCAL_STATIC_DIR.exists():
    WEB_DIR = LOCAL_STATIC_DIR
else:
    WEB_DIR = ROOT_WEB_DIR


app = FastAPI(
    title="Agentic AI Framework • Local Studio",
    description="Interactive Web Workbench and Animated Observability Studio for Multi-Agent Engineering",
    version="2.1.0",
)


# ==============================================================================
# In-Memory Workflow Execution Manager & State
# ==============================================================================

class WorkflowManager:
    """Manages asynchronous workflow executions, live event feeds, and Web HITL."""

    def __init__(self):
        self.lock = threading.Lock()
        self.active_job: Optional[Dict[str, Any]] = None
        self.job_history: List[Dict[str, Any]] = []
        self.event_subscribers: List[queue.Queue] = []
        self.pending_hitl: Optional[Dict[str, Any]] = None

        # Register event broadcast listener
        AgentLogger.subscribe(self._on_log_event)

    def _on_log_event(self, event: Dict[str, Any]) -> None:
        """Route logger events to active job and SSE subscribers."""
        with self.lock:
            if self.active_job and self.active_job.get("status") == "running":
                self.active_job["events"].append(event)
                # Track active agent
                if event.get("type") == "agent_start":
                    self.active_job["active_agent"] = event.get("agent")
                    self.active_job["active_subtask"] = event.get("task")

        # Broadcast to all connected web clients
        self._broadcast_event(event)

    def _broadcast_event(self, event: Dict[str, Any]) -> None:
        """Push an event to all active SSE queues."""
        for q in list(self.event_subscribers):
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def subscribe_events(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        self.event_subscribers.append(q)
        return q

    def unsubscribe_events(self, q: queue.Queue) -> None:
        if q in self.event_subscribers:
            self.event_subscribers.remove(q)

    def start_workflow(
        self,
        mode: str,
        task: str,
        target_dir: Optional[str] = None,
        file: Optional[str] = None,
        hitl_enabled: bool = False,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Launch multi-agent workflow in background thread."""
        with self.lock:
            if self.active_job and self.active_job.get("status") == "running":
                raise HTTPException(status_code=400, detail="A workflow is already currently running.")

            job_id = f"job-{int(time.time() * 1000)}"
            resolved_target = str(Path(target_dir or settings.TARGET_PROJECT_PATH).resolve())

            self.active_job = {
                "job_id": job_id,
                "mode": mode,
                "task": task,
                "target_dir": resolved_target,
                "file": file,
                "hitl_enabled": hitl_enabled,
                "provider": provider or settings.LLM_PROVIDER,
                "model": model or settings.MODEL_NAME,
                "status": "running",
                "start_time": time.time(),
                "end_time": None,
                "active_agent": "Orchestrator",
                "active_subtask": task,
                "events": [],
                "final_summary": None,
                "error": None,
                "modified_files": [],
            }
            self.pending_hitl = None

        # Configure HITL callback if web HITL is active
        if hitl_enabled:
            settings.HITL_ENABLED = True
            hitl_manager.enabled = True
            hitl_manager.set_callback(self._web_hitl_callback)
        else:
            settings.HITL_ENABLED = False
            hitl_manager.enabled = False
            hitl_manager.set_callback(None)

        # Apply runtime provider & model overrides if given
        if provider:
            settings.LLM_PROVIDER = provider
        if model:
            settings.MODEL_NAME = model

        # Launch in background worker thread
        worker = threading.Thread(
            target=self._execute_workflow_thread,
            args=(self.active_job,),
            daemon=True,
            name=f"WorkflowWorker-{job_id}",
        )
        worker.start()

        return {
            "job_id": job_id,
            "status": "started",
            "target_dir": resolved_target,
        }

    def _web_hitl_callback(
        self,
        action_name: str,
        details: str,
        risk: ActionRiskLevel,
        metadata: Dict[str, Any],
    ) -> HITLDecision:
        """Intercepts sensitive actions, broadcasts HITL request to web UI, and blocks for human response."""
        req_id = f"hitl-{int(time.time() * 1000)}"
        event_wait = threading.Event()
        decision_holder: Dict[str, Any] = {"decision": HITLDecision.REJECT, "feedback": None}

        with self.lock:
            self.pending_hitl = {
                "req_id": req_id,
                "action_name": action_name,
                "details": details,
                "risk": risk.value,
                "diff": metadata.get("diff", ""),
                "command": metadata.get("command", ""),
                "file_path": metadata.get("file_path", ""),
                "wait_event": event_wait,
                "decision_holder": decision_holder,
            }

        # Broadcast HITL prompt event to web client
        self._broadcast_event({
            "type": "hitl_request",
            "req_id": req_id,
            "action_name": action_name,
            "details": details,
            "risk": risk.value,
            "diff": metadata.get("diff", ""),
            "command": metadata.get("command", ""),
            "file_path": metadata.get("file_path", ""),
        })

        # Wait up to 5 minutes for user interaction in the web UI
        signaled = event_wait.wait(timeout=300.0)

        with self.lock:
            self.pending_hitl = None

        if not signaled:
            logger.warning("Web HITL approval timed out after 300 seconds. Rejecting action.")
            return HITLDecision.REJECT

        return decision_holder["decision"]

    def respond_hitl(self, req_id: str, approved: bool, feedback: Optional[str] = None) -> bool:
        """Called by the web client to approve or reject a pending action."""
        with self.lock:
            if not self.pending_hitl or self.pending_hitl.get("req_id") != req_id:
                return False

            pending = self.pending_hitl
            decision = HITLDecision.APPROVE if approved else HITLDecision.REJECT
            pending["decision_holder"]["decision"] = decision
            pending["decision_holder"]["feedback"] = feedback
            pending["wait_event"].set()

            self._broadcast_event({
                "type": "hitl_resolved",
                "req_id": req_id,
                "approved": approved,
                "feedback": feedback,
            })
            return True

    def _execute_workflow_thread(self, job: Dict[str, Any]) -> None:
        """Executes orchestrator in separate thread."""
        try:
            target = job["target_dir"]
            mode = job["mode"]
            task = job["task"]
            file_target = job.get("file")

            # Route mode
            if mode == "run":
                res = orchestrator.run(task=task, target_dir=target)
            elif mode == "fix":
                res = orchestrator.run(
                    task=f"Fix issue: {task}",
                    target_dir=target,
                    specific_agent="BugFixAgent",
                )
            elif mode == "feature":
                res = orchestrator.run(
                    task=f"Implement feature: {task}",
                    target_dir=target,
                    specific_agent="FeatureDevAgent",
                )
            elif mode == "review":
                task_desc = f"Conduct comprehensive technical and security review"
                if file_target:
                    task_desc += f" on file: {file_target}"
                res = orchestrator.run(
                    task=task_desc,
                    target_dir=target,
                    specific_agent="TechReviewAgent",
                )
            elif mode == "test":
                task_desc = "Discover test suite, run regression tests, and report results"
                if file_target:
                    task_desc += f" focusing on: {file_target}"
                res = orchestrator.run(
                    task=task_desc,
                    target_dir=target,
                    specific_agent="RegressionTestAgent",
                )
            else:
                raise ValueError(f"Unknown workflow mode: {mode}")

            with self.lock:
                job["status"] = "completed"
                job["end_time"] = time.time()
                job["final_summary"] = res.get("summary", "")
                job["trace_id"] = res.get("trace_id", "")
                self.job_history.append(dict(job))

            self._broadcast_event({
                "type": "workflow_completed",
                "job_id": job["job_id"],
                "summary": job["final_summary"],
                "trace_id": job.get("trace_id"),
                "duration": round(job["end_time"] - job["start_time"], 2),
            })

        except Exception as e:
            with self.lock:
                job["status"] = "failed"
                job["end_time"] = time.time()
                job["error"] = str(e)
                self.job_history.append(dict(job))

            self._broadcast_event({
                "type": "workflow_failed",
                "job_id": job["job_id"],
                "error": str(e),
                "duration": round(job["end_time"] - job["start_time"], 2),
            })


workflow_manager = WorkflowManager()


# ==============================================================================
# REST & Streaming Endpoints
# ==============================================================================

@app.get("/api/config")
def get_config():
    """Return framework runtime configuration and defaults."""
    target_path = str(settings.get_target_path())
    return {
        "target_project_path": target_path,
        "default_target_exists": Path(target_path).exists(),
        "llm_provider": settings.LLM_PROVIDER,
        "model_name": settings.MODEL_NAME,
        "hitl_enabled": settings.HITL_ENABLED,
        "dashboard_port": settings.DASHBOARD_PORT,
    }


@app.post("/api/workflow/run")
async def run_workflow_api(req: Request):
    """Trigger agent workflow execution."""
    data = await req.json()
    mode = data.get("mode", "run")
    task = data.get("task", "").strip()
    target_dir = data.get("target_dir", "").strip() or None
    file_target = data.get("file", "").strip() or None
    hitl_enabled = bool(data.get("hitl", False))
    provider = data.get("provider", "").strip() or None
    model = data.get("model", "").strip() or None

    if not task:
        raise HTTPException(status_code=400, detail="Task description is required.")

    result = workflow_manager.start_workflow(
        mode=mode,
        task=task,
        target_dir=target_dir,
        file=file_target,
        hitl_enabled=hitl_enabled,
        provider=provider,
        model=model,
    )
    return JSONResponse(content=result)


@app.get("/api/workflow/status")
def get_workflow_status():
    """Get status of active or most recent workflow."""
    with workflow_manager.lock:
        job = workflow_manager.active_job
        pending = workflow_manager.pending_hitl
        if not job:
            return {
                "status": "idle",
                "job": None,
                "pending_hitl": None,
            }
        job_copy = dict(job)
        job_copy["events"] = job_copy.get("events", [])[-100:]
        return {
            "status": job["status"],
            "job": job_copy,
            "pending_hitl": {
                "req_id": pending["req_id"],
                "action_name": pending["action_name"],
                "details": pending["details"],
                "diff": pending.get("diff", ""),
                "command": pending.get("command", ""),
                "file_path": pending.get("file_path", ""),
            } if pending else None,
        }


@app.post("/api/workflow/hitl/respond")
async def respond_hitl_api(req: Request):
    """Submit human approval or rejection."""
    data = await req.json()
    req_id = data.get("req_id")
    approved = bool(data.get("approved", False))
    feedback = data.get("feedback")

    if not req_id:
        raise HTTPException(status_code=400, detail="req_id is required.")

    success = workflow_manager.respond_hitl(req_id, approved=approved, feedback=feedback)
    if not success:
        raise HTTPException(status_code=404, detail="No active HITL request matching this ID.")
    return {"status": "ok", "approved": approved}


@app.get("/api/workflow/events")
def stream_events():
    """Server-Sent Events (SSE) streaming live logs, thoughts, and agent events."""
    q = workflow_manager.subscribe_events()

    def event_generator():
        try:
            yield 'event: connected\ndata: {"status": "ready"}\n\n'
            while True:
                try:
                    event = q.get(timeout=20.0)
                    yield f"event: message\ndata: {json.dumps(event)}\n\n"
                except Exception:
                    # Heartbeat keepalive
                    yield "event: ping\ndata: {}\n\n"
        finally:
            workflow_manager.unsubscribe_events(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/files/tree")
def get_file_tree(target_dir: Optional[str] = None):
    """List code files in the target project."""
    root = Path(target_dir or settings.get_target_path()).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Target directory {root} not found.")

    files = []
    excluded = set(settings.EXCLUDED_DIRS)
    for p in root.rglob("*"):
        if p.is_file():
            parts = p.relative_to(root).parts
            if any(part in excluded or part.startswith(".") for part in parts):
                continue
            files.append({
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "name": p.name,
                "suffix": p.suffix,
            })
    return {"root": str(root), "files": sorted(files, key=lambda x: x["path"])}


@app.get("/api/files/read")
def read_file_content(path: str, target_dir: Optional[str] = None):
    """Read a specific file from target project for code viewing."""
    root = Path(target_dir or settings.get_target_path()).resolve()
    target_file = (root / path).resolve()
    if not target_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tests/run")
def run_project_tests_api(target_dir: Optional[str] = None):
    """Run pytest / test runner on target project directly from browser."""
    if target_dir:
        settings.TARGET_PROJECT_PATH = target_dir
    res = tool_registry._tool_run_tests()
    return {"result": res}


@app.get("/api/traces")
def get_traces():
    """Get list of recent telemetry traces."""
    return JSONResponse(content=tracer.get_recent_traces())


@app.get("/api/traces/{trace_id}")
def get_trace(trace_id: str):
    """Get full details of a specific trace."""
    trace = tracer.get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return JSONResponse(content=trace)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Agentic AI Framework Local Studio", "version": "2.1.0"}


# ==============================================================================
# Web Static File Serving
# ==============================================================================

def get_web_dir() -> Path:
    """Find the active web folder."""
    if ROOT_WEB_DIR.exists():
        return ROOT_WEB_DIR
    if LOCAL_STATIC_DIR.exists():
        return LOCAL_STATIC_DIR
    return ROOT_WEB_DIR


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serve the primary HTML application."""
    html_file = get_web_dir() / "index.html"
    if not html_file.exists():
        return HTMLResponse(
            f"<h1>Web files not found</h1><p>Expected index.html at {html_file}</p>",
            status_code=404,
        )
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/styles.css")
def get_styles():
    """Serve styles.css directly."""
    css_file = get_web_dir() / "styles.css"
    if not css_file.exists():
        raise HTTPException(status_code=404, detail="styles.css not found")
    return FileResponse(css_file, media_type="text/css")


@app.get("/app.js")
def get_app_js():
    """Serve app.js directly."""
    js_file = get_web_dir() / "app.js"
    if not js_file.exists():
        raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(js_file, media_type="application/javascript")


# Mount /static as fallback
if (PROJECT_ROOT / "web").exists():
    app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "web")), name="static")


def run_dashboard(host: str = "127.0.0.1", port: int = 8088):
    """Run interactive Local Web Studio and Observability server."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_dashboard()
