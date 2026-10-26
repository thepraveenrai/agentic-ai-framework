"""Observability package exports."""

from agentic_framework.observability.tracer import tracer, Tracer
from agentic_framework.observability.logger import logger, console


def run_dashboard(host: str = "127.0.0.1", port: int = 8088):
    """Launch the Web Dashboard & Studio."""
    from agentic_framework.observability.dashboard import run_dashboard as _run
    return _run(host=host, port=port)


def __getattr__(name: str):
    if name == "dashboard_app":
        from agentic_framework.observability.dashboard import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["tracer", "Tracer", "logger", "console", "dashboard_app", "run_dashboard"]
