"""Command Line Interface (CLI) for Agentic AI Framework.

Provides rich terminal commands to run multi-agent workflows, individual agents,
observability dashboard, and MCP servers on any project.
"""

import argparse
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
from agentic_framework.config import settings
from agentic_framework.orchestrator.graph import orchestrator
from agentic_framework.rag.retriever import retriever
from agentic_framework.web.server import run_dashboard
from agentic_framework.mcp.server import mcp_server
from agentic_framework.observability.logger import logger, console


def main():
    parser = argparse.ArgumentParser(
        prog="agentic-ai",
        description="Autonomous Multi-Agent AI Framework for Software Engineering",
    )
    subparsers = parser.add_subparsers(dest="command", help="Framework Commands")

    # 1. run (Orchestrator)
    run_parser = subparsers.add_parser("run", help="Execute multi-agent workflow on target project")
    run_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    run_parser.add_argument("--task", "-t", required=True, help="Task specification")
    run_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation prompts")
    run_parser.add_argument("--model", "-m", help="Override LLM model name")
    run_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")

    # 2. fix (BugFixAgent + RegressionTestAgent auto-run)
    fix_parser = subparsers.add_parser("fix", help="Diagnose and patch bugs with BugFixAgent (auto-runs RegressionTestAgent to verify zero regressions)")
    fix_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    fix_parser.add_argument("--issue", "-i", required=True, help="Bug report, error trace, or issue description")
    fix_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation")
    fix_parser.add_argument("--model", "-m", help="Override LLM model name")
    fix_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")

    # 3. review (TechReviewAgent)
    review_parser = subparsers.add_parser("review", help="Audit code security and architecture with TechReviewAgent")
    review_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    review_parser.add_argument("--file", "-f", help="Specific file to review")
    review_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation")
    review_parser.add_argument("--model", "-m", help="Override LLM model name")
    review_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")

    # 4. feature (FeatureDevAgent + RegressionTestAgent auto-run)
    feat_parser = subparsers.add_parser("feature", help="Design and implement new features with FeatureDevAgent (auto-runs RegressionTestAgent to verify zero regressions)")
    feat_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    feat_parser.add_argument("--spec", "-s", required=True, help="Feature specification")
    feat_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation")
    feat_parser.add_argument("--model", "-m", help="Override LLM model name")
    feat_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")

    # 5. test (RegressionTestAgent)
    test_parser = subparsers.add_parser("test", help="Run regression verification with RegressionTestAgent on recent changes or test suites")
    test_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    test_parser.add_argument("--focus", help="Focus module or changed file")
    test_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation")
    test_parser.add_argument("--model", "-m", help="Override LLM model name")
    test_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")

    # 6. index (RAG)
    idx_parser = subparsers.add_parser("index", help="Index target project for RAG retrieval")
    idx_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    idx_parser.add_argument("--rebuild", action="store_true", help="Force rebuild existing index")

    # 7. dashboard / ui / web (Interactive Web Studio & Observability UI)
    dash_parser = subparsers.add_parser("dashboard", aliases=["ui", "web"], help="Start interactive web studio & dashboard at localhost")
    dash_parser.add_argument("--port", "-p", type=int, default=8088, help="Port to listen on (default 8088)")
    dash_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")

    # 8. mcp-serve
    subparsers.add_parser("mcp-serve", help="Run standard MCP JSON-RPC server over stdio")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Apply overrides
    if hasattr(args, "target_dir") and args.target_dir:
        settings.TARGET_PROJECT_PATH = str(Path(args.target_dir).resolve())

    if hasattr(args, "no_hitl") and args.no_hitl:
        settings.HITL_ENABLED = False

    if hasattr(args, "model") and args.model:
        settings.MODEL_NAME = args.model

    if hasattr(args, "provider") and args.provider:
        settings.LLM_PROVIDER = args.provider

    # Dispatch commands
    if args.command == "run":
        orchestrator.run(task=args.task, target_dir=settings.TARGET_PROJECT_PATH)

    elif args.command == "fix":
        orchestrator.run(
            task=f"Fix issue: {args.issue}",
            target_dir=settings.TARGET_PROJECT_PATH,
            specific_agent="BugFixAgent",
        )

    elif args.command == "review":
        task_desc = f"Conduct comprehensive technical and security review"
        if args.file:
            task_desc += f" on file: {args.file}"
        orchestrator.run(
            task=task_desc,
            target_dir=settings.TARGET_PROJECT_PATH,
            specific_agent="TechReviewAgent",
        )

    elif args.command == "feature":
        orchestrator.run(
            task=f"Implement feature: {args.spec}",
            target_dir=settings.TARGET_PROJECT_PATH,
            specific_agent="FeatureDevAgent",
        )

    elif args.command == "test":
        task_desc = "Discover test suite, run regression tests, and report results"
        if args.focus:
            task_desc += f" focusing on: {args.focus}"
        orchestrator.run(
            task=task_desc,
            target_dir=settings.TARGET_PROJECT_PATH,
            specific_agent="RegressionTestAgent",
        )

    elif args.command == "index":
        settings.TARGET_PROJECT_PATH = str(Path(args.target_dir).resolve())
        retriever.target_dir = Path(settings.TARGET_PROJECT_PATH)
        count = retriever.initialize_index(force_rebuild=args.rebuild)
        logger.success(f"Indexed {count} code chunks in {settings.TARGET_PROJECT_PATH}")

    elif args.command in ("dashboard", "ui", "web"):
        logger.info(f"Starting Agentic AI Localhost Web Studio at http://{args.host}:{args.port}")
        run_dashboard(host=args.host, port=args.port)

    elif args.command == "mcp-serve":
        mcp_server.run_stdio()


if __name__ == "__main__":
    main()
