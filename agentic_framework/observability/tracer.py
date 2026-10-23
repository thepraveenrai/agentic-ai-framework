"""Observability Tracer and Telemetry Engine.

Tracks agent reasoning steps, LLM calls, tool executions, token metrics,
latencies, costs, and execution traces with JSON persistence.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from agentic_framework.config import settings


@dataclass
class ToolCallRecord:
    name: str
    args: Dict[str, Any]
    result: Any = None
    duration_ms: float = 0.0
    status: str = "success"  # success, error, rejected_by_user
    error: Optional[str] = None


@dataclass
class SpanRecord:
    span_id: str
    agent_name: str
    task_name: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    thought: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    status: str = "running"  # running, completed, failed
    error_message: Optional[str] = None


@dataclass
class TraceSession:
    trace_id: str
    start_time: str
    task_description: str
    target_project: str
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    status: str = "in_progress"  # in_progress, success, failed
    total_spans: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    spans: List[Dict[str, Any]] = field(default_factory=list)
    final_output: Optional[str] = None


class Tracer:
    """Central singleton tracer for agentic observability."""

    _instance: Optional["Tracer"] = None

    def __new__(cls) -> "Tracer":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_tracer()
        return cls._instance

    def _init_tracer(self) -> None:
        self.active_trace: Optional[TraceSession] = None
        self.active_spans: Dict[str, SpanRecord] = {}
        self.traces_dir = Path(settings.TRACES_DIR)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self._all_traces: List[TraceSession] = []

    def start_trace(self, task_description: str, target_project: str) -> str:
        """Start a new trace session."""
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        self.active_trace = TraceSession(
            trace_id=trace_id,
            start_time=now,
            task_description=task_description,
            target_project=str(target_project),
        )
        return trace_id

    def start_span(
        self, agent_name: str, task_name: str, model: str = "", input_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Begin an agent action or LLM reasoning span."""
        span_id = f"span-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        span = SpanRecord(
            span_id=span_id,
            agent_name=agent_name,
            task_name=task_name,
            start_time=now,
            model=model or settings.MODEL_NAME,
            input_data=input_data,
        )
        self.active_spans[span_id] = span
        return span_id

    def record_thought(self, span_id: str, thought: str) -> None:
        """Record agent reasoning thought."""
        if span_id in self.active_spans:
            self.active_spans[span_id].thought = thought

    def record_tool_call(
        self,
        span_id: str,
        tool_name: str,
        args: Dict[str, Any],
        result: Any = None,
        duration_ms: float = 0.0,
        status: str = "success",
        error: Optional[str] = None,
    ) -> None:
        """Record an executed tool invocation."""
        record = ToolCallRecord(
            name=tool_name,
            args=args,
            result=result,
            duration_ms=duration_ms,
            status=status,
            error=error,
        )
        if span_id in self.active_spans:
            self.active_spans[span_id].tool_calls.append(asdict(record))

    def record_tokens(
        self, span_id: str, prompt_tokens: int, completion_tokens: int, model: str = ""
    ) -> None:
        """Record token consumption and calculate estimated cost."""
        if span_id in self.active_spans:
            span = self.active_spans[span_id]
            span.prompt_tokens += prompt_tokens
            span.completion_tokens += completion_tokens
            span.total_tokens = span.prompt_tokens + span.completion_tokens
            # Standard estimated pricing: ~$0.14 per 1M prompt, $0.28 per 1M completion (Deepseek baseline)
            cost = (prompt_tokens * 0.00000014) + (completion_tokens * 0.00000028)
            span.estimated_cost_usd += round(cost, 6)

    def end_span(
        self,
        span_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> Optional[SpanRecord]:
        """Complete a span and add it to the active trace."""
        if span_id not in self.active_spans:
            return None

        span = self.active_spans.pop(span_id)
        end_time_dt = datetime.now(timezone.utc)
        start_time_dt = datetime.fromisoformat(span.start_time)
        duration_ms = (end_time_dt - start_time_dt).total_seconds() * 1000.0

        span.end_time = end_time_dt.isoformat()
        span.duration_ms = round(duration_ms, 2)
        span.output_data = output_data
        span.status = status
        span.error_message = error_message

        if self.active_trace:
            self.active_trace.spans.append(asdict(span))
            self.active_trace.total_spans += 1
            self.active_trace.total_tokens += span.total_tokens
            self.active_trace.total_cost_usd = round(
                self.active_trace.total_cost_usd + span.estimated_cost_usd, 6
            )

        return span

    def end_trace(self, status: str = "success", final_output: Optional[str] = None) -> Optional[TraceSession]:
        """Finish the active trace and save to disk."""
        if not self.active_trace:
            return None

        end_time_dt = datetime.now(timezone.utc)
        start_time_dt = datetime.fromisoformat(self.active_trace.start_time)
        self.active_trace.end_time = end_time_dt.isoformat()
        self.active_trace.duration_ms = round(
            (end_time_dt - start_time_dt).total_seconds() * 1000.0, 2
        )
        self.active_trace.status = status
        self.active_trace.final_output = final_output

        # Persist trace JSON to disk
        trace_file = self.traces_dir / f"{self.active_trace.trace_id}.json"
        try:
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.active_trace), f, indent=2)
        except Exception:
            pass

        completed_trace = self.active_trace
        self._all_traces.append(completed_trace)
        self.active_trace = None
        return completed_trace

    def get_recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent traces from disk and memory."""
        traces = []
        if self.traces_dir.exists():
            for p in sorted(self.traces_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        traces.append(json.load(f))
                except Exception:
                    continue
        return traces

    def get_trace_by_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full trace details by ID."""
        file_path = self.traces_dir / f"{trace_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None


# Global tracer instance
tracer = Tracer()
