"""Observability Web Dashboard & Studio compatibility bridge.

Re-exports FastAPI app and run_dashboard from the dedicated web module
`agentic_framework.web.server`.
"""

from agentic_framework.web.server import app, run_dashboard

__all__ = ["app", "run_dashboard"]
