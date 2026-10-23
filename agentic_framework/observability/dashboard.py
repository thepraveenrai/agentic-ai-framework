"""Web Observability Dashboard for Agentic AI Framework.

Provides a fast, responsive FastAPI server with an embedded real-time UI
to visualize agent reasoning loops, tool calls, token costs, and telemetry.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, List
import uvicorn
from agentic_framework.observability.tracer import tracer
from agentic_framework.config import settings

app = FastAPI(
    title="Agentic AI Framework Observability",
    description="Real-time telemetry, tracing, and multi-agent execution inspector.",
    version="1.0.0",
)

HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agentic AI Framework • Observability Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(23, 32, 54, 0.75);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.25);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --code-bg: #070a12;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Outfit', sans-serif;
      min-height: 100vh;
      padding: 2rem;
      background-image: radial-gradient(circle at 15% 20%, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
                        radial-gradient(circle at 85% 70%, rgba(16, 185, 129, 0.08) 0%, transparent 45%);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .logo-icon {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, #6366f1, #a855f7);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      box-shadow: 0 4px 15px var(--accent-glow);
    }
    .brand h1 {
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand p {
      font-size: 0.875rem;
      color: var(--text-muted);
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }
    .metric-card {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.25rem;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .metric-title {
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
    }
    .metric-value {
      font-size: 1.8rem;
      font-weight: 700;
      color: var(--text);
    }
    .metric-sub {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }
    .main-layout {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 1.5rem;
    }
    .panel {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      height: 720px;
    }
    .panel-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255,255,255,0.02);
    }
    .panel-title {
      font-size: 1rem;
      font-weight: 600;
    }
    .trace-list {
      overflow-y: auto;
      padding: 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      flex: 1;
    }
    .trace-item {
      padding: 0.875rem;
      border-radius: 12px;
      background: rgba(255,255,255,0.02);
      border: 1px solid transparent;
      cursor: pointer;
      transition: all 0.2s;
    }
    .trace-item:hover, .trace-item.active {
      background: rgba(99, 102, 241, 0.12);
      border-color: rgba(99, 102, 241, 0.4);
    }
    .trace-item-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.35rem;
    }
    .trace-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: var(--accent);
    }
    .badge {
      font-size: 0.65rem;
      padding: 0.2rem 0.5rem;
      border-radius: 20px;
      text-transform: uppercase;
      font-weight: 600;
    }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: var(--success); }
    .badge-running { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
    .badge-failed { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
    .trace-task {
      font-size: 0.85rem;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .trace-meta {
      font-size: 0.7rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
      display: flex;
      gap: 0.75rem;
    }
    .detail-view {
      padding: 1.5rem;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }
    .timeline {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      position: relative;
    }
    .span-card {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      transition: border-color 0.2s;
    }
    .span-card:hover {
      border-color: rgba(255, 255, 255, 0.18);
    }
    .span-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }
    .agent-pill {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      background: linear-gradient(135deg, #4f46e5, #7c3aed);
      color: white;
    }
    .span-task {
      font-size: 0.85rem;
      font-weight: 600;
      color: #e5e7eb;
    }
    .thought-bubble {
      background: rgba(99, 102, 241, 0.08);
      border-left: 3px solid var(--accent);
      padding: 0.65rem 0.85rem;
      border-radius: 0 8px 8px 0;
      font-size: 0.825rem;
      color: #d1d5db;
      margin: 0.5rem 0;
      white-space: pre-wrap;
    }
    .code-box {
      background: var(--code-bg);
      border-radius: 8px;
      padding: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #38bdf8;
      overflow-x: auto;
      margin-top: 0.5rem;
    }
    .btn {
      background: var(--accent);
      color: white;
      border: none;
      padding: 0.4rem 0.8rem;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.8rem;
      font-family: inherit;
    }
    .btn:hover {
      opacity: 0.9;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="brand">
      <div class="logo-icon">⚡</div>
      <div>
        <h1>Agentic AI Framework</h1>
        <p>Real-Time Multi-Agent Observability, Tracing & Guardrails</p>
      </div>
    </div>
    <button class="btn" onclick="fetchData()">⟳ Refresh Traces</button>
  </div>

  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-title">Total Sessions</div>
      <div class="metric-value" id="metric-sessions">0</div>
      <div class="metric-sub">Executed multi-agent workflows</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Total Agent Spans</div>
      <div class="metric-value" id="metric-spans">0</div>
      <div class="metric-sub">ReAct thoughts & actions</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Token Consumption</div>
      <div class="metric-value" id="metric-tokens">0</div>
      <div class="metric-sub">Across all LLM invocations</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Estimated Cost</div>
      <div class="metric-value" id="metric-cost">$0.000</div>
      <div class="metric-sub">Cumulative model expenditure</div>
    </div>
  </div>

  <div class="main-layout">
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Trace Sessions</span>
        <span id="trace-count" style="font-size: 0.75rem; color: var(--text-muted);">0 found</span>
      </div>
      <div class="trace-list" id="trace-list">
        <p style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No traces recorded yet. Run a task to inspect execution traces!</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <span class="panel-title" id="detail-title">Trace Details</span>
        <span id="detail-badge"></span>
      </div>
      <div class="detail-view" id="detail-view">
        <p style="color: var(--text-muted); font-size: 0.9rem;">Select a trace session on the left to inspect multi-agent reasoning steps, tool executions, guardrail verdicts, and diff patches.</p>
      </div>
    </div>
  </div>

  <script>
    let traces = [];
    let selectedTraceId = null;

    async function fetchData() {
      try {
        const res = await fetch('/api/traces');
        traces = await res.json();
        renderMetrics();
        renderTraceList();
        if (traces.length > 0 && !selectedTraceId) {
          selectTrace(traces[0].trace_id);
        } else if (selectedTraceId) {
          selectTrace(selectedTraceId);
        }
      } catch (err) {
        console.error("Failed to fetch traces", err);
      }
    }

    function renderMetrics() {
      let totalSpans = 0;
      let totalTokens = 0;
      let totalCost = 0.0;
      traces.forEach(t => {
        totalSpans += (t.spans ? t.spans.length : 0);
        totalTokens += (t.total_tokens || 0);
        totalCost += (t.total_cost_usd || 0.0);
      });
      document.getElementById('metric-sessions').innerText = traces.length;
      document.getElementById('metric-spans').innerText = totalSpans;
      document.getElementById('metric-tokens').innerText = totalTokens.toLocaleString();
      document.getElementById('metric-cost').innerText = '$' + totalCost.toFixed(4);
      document.getElementById('trace-count').innerText = traces.length + ' sessions';
    }

    function renderTraceList() {
      const container = document.getElementById('trace-list');
      if (traces.length === 0) {
        container.innerHTML = '<p style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No traces recorded yet. Execute a task to see traces here.</p>';
        return;
      }
      container.innerHTML = traces.map(t => {
        const badgeClass = t.status === 'success' ? 'badge-success' : (t.status === 'in_progress' ? 'badge-running' : 'badge-failed');
        const isActive = t.trace_id === selectedTraceId ? 'active' : '';
        return `
          <div class="trace-item ${isActive}" onclick="selectTrace('${t.trace_id}')">
            <div class="trace-item-header">
              <span class="trace-id">${t.trace_id}</span>
              <span class="badge ${badgeClass}">${t.status}</span>
            </div>
            <div class="trace-task" title="${t.task_description}">${t.task_description}</div>
            <div class="trace-meta">
              <span>⏱ ${t.duration_ms ? (t.duration_ms/1000).toFixed(1) + 's' : 'running'}</span>
              <span>🧩 ${t.spans ? t.spans.length : 0} spans</span>
              <span>⚡ ${t.total_tokens || 0} tokens</span>
            </div>
          </div>
        `;
      }).join('');
    }

    function selectTrace(traceId) {
      selectedTraceId = traceId;
      renderTraceList();
      const t = traces.find(item => item.trace_id === traceId);
      if (!t) return;

      document.getElementById('detail-title').innerText = `Session: ${t.trace_id}`;
      const badgeClass = t.status === 'success' ? 'badge-success' : (t.status === 'in_progress' ? 'badge-running' : 'badge-failed');
      document.getElementById('detail-badge').innerHTML = `<span class="badge ${badgeClass}">${t.status}</span>`;

      const view = document.getElementById('detail-view');
      const spansHtml = (t.spans || []).map((s, idx) => {
        const toolsHtml = (s.tool_calls || []).map(tc => `
          <div style="margin-top: 0.5rem; padding: 0.5rem; background: rgba(0,0,0,0.3); border-radius: 6px; border-left: 2px solid #38bdf8;">
            <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 600;">🛠 Tool: ${tc.name} (${tc.duration_ms.toFixed(0)}ms) - [${tc.status}]</div>
            <div class="code-box">Args: ${JSON.stringify(tc.args, null, 2)}</div>
            ${tc.result ? `<div class="code-box" style="color: #4ade80;">Result: ${typeof tc.result === 'string' ? tc.result.substring(0, 300) : JSON.stringify(tc.result).substring(0, 300)}</div>` : ''}
          </div>
        `).join('');

        return `
          <div class="span-card">
            <div class="span-top">
              <span class="agent-pill">🤖 ${s.agent_name}</span>
              <span style="font-size: 0.75rem; color: var(--text-muted);">${s.duration_ms}ms • ${s.total_tokens} tokens</span>
            </div>
            <div class="span-task">${s.task_name}</div>
            ${s.thought ? `<div class="thought-bubble"><strong>Reasoning:</strong><br>${escapeHtml(s.thought)}</div>` : ''}
            ${toolsHtml}
            ${s.output_data ? `<div class="code-box" style="color: #a78bfa;">Output: ${JSON.stringify(s.output_data, null, 2)}</div>` : ''}
          </div>
        `;
      }).join('');

      view.innerHTML = `
        <div style="background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 12px; border: 1px solid var(--border);">
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem;">TARGET PROJECT</div>
          <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #a5b4fc; margin-bottom: 0.75rem;">${t.target_project}</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem;">TASK SPECIFICATION</div>
          <div style="font-size: 0.95rem; font-weight: 500;">${escapeHtml(t.task_description)}</div>
          ${t.final_output ? `<div style="margin-top: 1rem; padding: 0.75rem; background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10b981; border-radius: 0 8px 8px 0; font-size: 0.85rem; color: #a7f3d0;"><strong>Final Result:</strong><br>${escapeHtml(t.final_output)}</div>` : ''}
        </div>
        <h3 style="font-size: 0.95rem; font-weight: 600; color: #e5e7eb; margin-top: 0.5rem;">Agent Execution Sequence (${(t.spans || []).length} steps)</h3>
        <div class="timeline">${spansHtml || '<p style="color: var(--text-muted); font-size: 0.85rem;">No spans recorded in this trace.</p>'}</div>
      `;
    }

    function escapeHtml(text) {
      if (!text) return '';
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Auto load on open and poll every 4 seconds
    fetchData();
    setInterval(fetchData, 4000);
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index_view():
    """Serve embedded web dashboard."""
    return HTML_UI


@app.get("/api/traces")
def get_traces():
    """Get list of recent traces."""
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
    return {"status": "ok", "app": "Agentic AI Framework Observability"}


def run_dashboard(host: str = "127.0.0.1", port: int = 8088):
    """Run observability server."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_dashboard()
