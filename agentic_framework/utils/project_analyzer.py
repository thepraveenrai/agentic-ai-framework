"""Project Environment and Language Analyzer.

Automatically detects target project language, dependency management,
test framework, and source structure for any folder.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from agentic_framework.config import settings


class ProjectAnalyzer:
    """Discovers project metadata, language stacks, and test runners."""

    def __init__(self, target_dir: Optional[Path] = None):
        self.target_dir = (target_dir or settings.get_target_path()).resolve()

    def analyze(self) -> Dict[str, Any]:
        """Perform comprehensive analysis of the target project folder."""
        if not self.target_dir.exists():
            return {
                "exists": False,
                "error": f"Target directory not found: {self.target_dir}",
            }

        languages = self.detect_languages()
        package_manager = self.detect_package_manager()
        test_runner = self.detect_test_runner()
        is_git = (self.target_dir / ".git").exists()

        return {
            "exists": True,
            "target_dir": str(self.target_dir),
            "is_git_repository": is_git,
            "languages": languages,
            "primary_language": languages[0] if languages else "unknown",
            "package_manager": package_manager,
            "test_runner_command": test_runner,
            "has_tests": self.has_tests(),
        }

    def detect_languages(self) -> List[str]:
        """Detect programming languages based on file extensions."""
        counts: Dict[str, int] = {}
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
        }

        try:
            for p in self.target_dir.rglob("*"):
                if p.is_file() and not any(x in p.parts for x in settings.EXCLUDED_DIRS):
                    ext = p.suffix.lower()
                    if ext in ext_map:
                        lang = ext_map[ext]
                        counts[lang] = counts.get(lang, 0) + 1
        except Exception:
            pass

        sorted_langs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [lang for lang, _ in sorted_langs]

    def detect_package_manager(self) -> str:
        """Detect build and package management system."""
        if (self.target_dir / "pyproject.toml").exists():
            return "poetry/uv/pyproject"
        elif (self.target_dir / "requirements.txt").exists():
            return "pip"
        elif (self.target_dir / "package.json").exists():
            if (self.target_dir / "yarn.lock").exists():
                return "yarn"
            elif (self.target_dir / "pnpm-lock.yaml").exists():
                return "pnpm"
            return "npm"
        elif (self.target_dir / "Cargo.toml").exists():
            return "cargo"
        elif (self.target_dir / "go.mod").exists():
            return "go"
        return "generic"

    def detect_test_runner(self) -> str:
        """Detect default test execution command for the target project."""
        import sys
        py_bin = f'"{sys.executable}"'

        # Python
        if (self.target_dir / "tests").exists():
            return f"{py_bin} -m pytest tests"
        if (self.target_dir / "test").exists():
            return f"{py_bin} -m pytest test"
        if (self.target_dir / "pytest.ini").exists() or (self.target_dir / "requirements.txt").exists() or (self.target_dir / "pyproject.toml").exists():
            return f"{py_bin} -m pytest ."

        # Node / JS / TS
        if (self.target_dir / "package.json").exists():
            return "npm test"

        # Rust
        if (self.target_dir / "Cargo.toml").exists():
            return "cargo test"

        # Go
        if (self.target_dir / "go.mod").exists():
            return "go test ./..."

        return f"{py_bin} -m pytest"

    def has_tests(self) -> bool:
        """Check if project contains existing test files."""
        for pattern in ["test_*.py", "*_test.py", "*.test.ts", "*.spec.ts", "*.test.js", "*_test.go"]:
            if any(self.target_dir.rglob(pattern)):
                return True
        return False


project_analyzer = ProjectAnalyzer()
