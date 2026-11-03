"""Command Line Interface (CLI) for Agentic AI Framework.

Provides rich terminal commands to run multi-agent workflows, individual agents,
RAG code indexing, and MCP servers directly from the command line.
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
from agentic_framework.mcp.server import mcp_server
from agentic_framework.observability.logger import logger, console


def main():
    parser = argparse.ArgumentParser(
        prog="agentic-ai",
        description="Autonomous Multi-Agent AI Framework for Software Engineering (CLI)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose/debug log output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Show only warnings and errors")

    subparsers = parser.add_subparsers(dest="command", help="Framework Commands")

    # Common parent parser for shared arguments across subcommands
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    common_parser.add_argument("--no-hitl", action="store_true", help="Run without human confirmation prompts")
    common_parser.add_argument("--model", "-m", help="Override LLM model name")
    common_parser.add_argument("--provider", help="Override provider (openrouter, openai, mock)")
    common_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose/debug log output")
    common_parser.add_argument("--quiet", "-q", action="store_true", help="Show only warnings and errors")

    # 1. run (Orchestrator)
    run_parser = subparsers.add_parser("run", parents=[common_parser], help="Execute multi-agent workflow on target project")
    run_parser.add_argument("--task", "-t", required=True, help="Task specification")

    # 2. fix (BugFixAgent + RegressionTestAgent auto-run)
    fix_parser = subparsers.add_parser(
        "fix",
        parents=[common_parser],
        help="Diagnose and patch bugs with BugFixAgent (auto-runs RegressionTestAgent to verify zero regressions)",
    )
    fix_parser.add_argument("--issue", "-i", required=True, help="Bug report, error trace, or issue description")

    # 3. review (TechReviewAgent)
    review_parser = subparsers.add_parser(
        "review",
        parents=[common_parser],
        help="Audit code security and architecture with TechReviewAgent",
    )
    review_parser.add_argument("--file", "-f", help="Specific file to review")

    # 4. feature (FeatureDevAgent + RegressionTestAgent auto-run)
    feat_parser = subparsers.add_parser(
        "feature",
        parents=[common_parser],
        help="Design and implement new features with FeatureDevAgent (auto-runs RegressionTestAgent to verify zero regressions)",
    )
    feat_parser.add_argument("--spec", "-s", required=True, help="Feature specification")

    # 5. test (RegressionTestAgent)
    test_parser = subparsers.add_parser(
        "test",
        parents=[common_parser],
        help="Run regression verification with RegressionTestAgent on recent changes or test suites",
    )
    test_parser.add_argument("--focus", help="Focus module or changed file")

    # 6. index (RAG)
    idx_parser = subparsers.add_parser("index", help="Index target project for RAG retrieval")
    idx_parser.add_argument("--target-dir", "-d", default=".", help="Path to target project")
    idx_parser.add_argument("--rebuild", action="store_true", help="Force rebuild existing index")
    idx_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose/debug log output")
    idx_parser.add_argument("--quiet", "-q", action="store_true", help="Show only warnings and errors")

    # 7. mcp-serve
    subparsers.add_parser("mcp-serve", help="Run standard MCP JSON-RPC server over stdio")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Apply logging level overrides
    if getattr(args, "verbose", False):
        settings.LOG_LEVEL = "DEBUG"
    elif getattr(args, "quiet", False):
        settings.LOG_LEVEL = "WARNING"

    # Apply target project overrides
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
        task_desc = "Conduct comprehensive technical and security review"
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

    elif args.command == "mcp-serve":
        mcp_server.run_stdio()


if __name__ == "__main__":
    main()
