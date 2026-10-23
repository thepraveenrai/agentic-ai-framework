# Agentic AI Framework — User Guide & Step-by-Step Manual

This guide explains how to install, configure, and run the **Agentic AI Framework** on **any existing software project** on your system.

---

## 1. Quick Installation & Setup

### Prerequisites
- Python 3.10 or higher.
- A virtual environment is recommended.

### Step 1: Clone or Navigate to the Framework
```bash
cd c:\Workspace\my-workpace\ArtificialIntelligence\agentic-ai-framework
```

### Step 2: Create and Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install the Framework in Editable Mode
```bash
pip install -e .
```
This registers the global CLI command `agentic-ai`.

---

## 2. API Configuration

The framework comes preconfigured with OpenRouter and can also utilize OpenAI or Anthropic models.

Open `.env` in the framework root:
```env
# Provider: "openrouter", "openai", "anthropic", or "mock"
LLM_PROVIDER=openrouter

# OpenRouter Configuration
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=deepseek/deepseek-v4-flash-0731
MODEL_TEMPERATURE=0.0

# Optional Guardrail & Cache controls
GUARDRAILS_ENABLED=true
CACHE_ENABLED=true
HITL_ENABLED=true
```

---

## 3. How to Use with ANY Existing Project

The framework is completely **project-agnostic**. You can point it at any folder on your machine (Python backend, React/Next.js frontend, Go microservice, Rust CLI, Java Spring app, etc.).

Pass the path to your project with `--target-dir` (or `-d`).

### Workflow 1: Automatic Bug Diagnosis & Patching (`fix`)
When your project has a broken test, stack trace, or bug report:
```bash
agentic-ai fix --target-dir "C:\path\to\my-project" --issue "Users get ZeroDivisionError in pricing calculation when quantity is 0"
```
**What the Framework Does:**
1. Discovers project files and builds the RAG code index.
2. `BugFixAgent` retrieves the relevant code snippet using hybrid vector search.
3. Diagnoses the defect, formulates a root cause analysis, and applies a surgical patch.
4. Validates the fix using your project's test runner (`pytest`, `npm test`, `cargo test`, etc.).

---

### Workflow 2: Technical & Security Code Review (`review`)
Audit your project for OWASP vulnerabilities, architecture anti-patterns, and code smells:
```bash
# Review entire target project
agentic-ai review --target-dir "C:\path\to\my-project"

# Review a specific file
agentic-ai review --target-dir "C:\path\to\my-project" --file "src/auth/jwt.py"
```
**What the Framework Does:**
- Runs static analysis and security checks (detecting dangerous `eval`, SQL injection risks, exposed credentials).
- Evaluates modularity, Single Responsibility Principle, and code smells.
- Produces a formatted report with:
  - 🚨 Critical Vulnerabilities (Must Fix Immediately)
  - ⚠️ Warnings & Code Smells
  - 💡 Architecture & Performance Recommendations
  - 📝 Readiness Score (0–100)

---

### Workflow 3: New Feature Implementation (`feature`)
Add a new feature, module, or endpoint to your project:
```bash
agentic-ai feature --target-dir "C:\path\to\my-project" --spec "Add an export_to_csv() method on OrderService supporting date range filtering"
```
**What the Framework Does:**
- `FeatureDevAgent` scans existing patterns and insertion points.
- Implements the new feature cleanly using `apply_patch` or `write_file`.
- Verifies code syntax and integrity through output guardrails.

---

### Workflow 4: Regression Testing & Test Synthesis (`test`)
Generate missing unit tests and ensure existing suites pass:
```bash
agentic-ai test --target-dir "C:\path\to\my-project" --focus "calculator.py"
```
**What the Framework Does:**
- Discovers the project test framework (`pytest`, `npm test`, etc.).
- `RegressionTestAgent` analyzes edge cases (zero values, type mismatches, empty collections).
- Synthesizes and writes new regression tests and executes the full suite.

---

### Workflow 5: Full Multi-Agent Orchestration (`run`)
For complex, multi-stage engineering tasks:
```bash
agentic-ai run --target-dir "C:\path\to\my-project" --task "Implement discount coupon validation and verify with test suite"
```
**What the Framework Does:**
- The **Orchestrator** decomposes your request into an optimal multi-agent sequence (e.g. `FeatureDevAgent` -> `RegressionTestAgent` -> `TechReviewAgent`).
- Coordinates state, context, and artifacts across agents.
- Delivers a unified execution summary.

---

## 4. Human-in-the-Loop (HITL) Controls

By default, the framework enables interactive human approval before:
1. Writing or modifying code files.
2. Executing shell commands in the target project.

When a modification is proposed, a unified diff is displayed in the terminal:
```text
⚠️ Human-In-The-Loop Approval Required
Action: apply_patch(calculator.py)
Details:
--- a/calculator.py
+++ b/calculator.py
@@ -18,3 +18,3 @@
-    return unit_price / quantity
+    return 0.0

Do you approve this action? (yes / no / feedback) [y]:
```
- Type **`y`** to approve and apply the change.
- Type **`n`** to cancel.
- Type **`f`** to provide real-time textual feedback (e.g., *"Also handle negative quantities by raising a ValueError"*), and the agent will adapt its solution!

To run fully autonomous (e.g., in CI/CD pipelines or headless scripts):
```bash
agentic-ai run --target-dir "C:\path\to\my-project" --task "..." --no-hitl
```

---

## 5. Web Observability Dashboard

Inspect agent reasoning, ReAct thoughts, tool calls, token usage, and latency in real time.

Start the dashboard:
```bash
agentic-ai dashboard --port 8088
```
Then open your browser at **`http://localhost:8088`**.

### Dashboard Features:
- **Trace Explorer:** Browse every execution trace session.
- **Agent Reasoning Timeline:** Inspect ReAct thoughts and step-by-step logic.
- **Tool Invocations:** View exact tool parameters, outputs, and execution latencies in milliseconds.
- **Cost & Token Telemetry:** Track total prompt/completion tokens and estimated USD expenditure.

---

## 6. Model Context Protocol (MCP) Mode

The framework can run as a standard MCP server to expose project tools to Cursor, Claude Desktop, Antigravity, or other MCP clients:
```bash
agentic-ai mcp-serve
```
This communicates over JSON-RPC 2.0 stdio adhering to the official Model Context Protocol.

---

## 7. Python Programmatic SDK

You can also import and control the framework directly inside your own Python code:

```python
from agentic_framework.orchestrator.graph import orchestrator
from agentic_framework.config import settings

# Configure target project
settings.TARGET_PROJECT_PATH = "C:/path/to/my-project"
settings.HITL_ENABLED = False  # Headless mode

# Run autonomous task
result = orchestrator.run(
    task="Fix the ZeroDivisionError in calculator.py and ensure tests pass"
)

print("Trace ID:", result["trace_id"])
print("Status:", result["status"])
print("Summary:", result["summary"])
```
