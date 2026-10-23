"""Codebase Indexer and AST Chunking Engine.

Recursively analyzes target project codebases, extracts class/function symbols,
and produces structured code chunks for semantic retrieval.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from agentic_framework.config import settings
from agentic_framework.core.caching import cache


@dataclass
class CodeChunk:
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None  # class, function, module, block
    language: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodebaseIndexer:
    """Parses source code into searchable chunks with symbol metadata."""

    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
    }

    def __init__(self, target_dir: Optional[Path] = None):
        self.target_dir = (target_dir or settings.get_target_path()).resolve()

    def discover_files(self) -> List[Path]:
        """Find all indexed code files in target project, skipping excluded dirs."""
        files = []
        if not self.target_dir.exists():
            return files

        for path in self.target_dir.rglob("*"):
            if not path.is_file():
                continue

            # Check exclusions
            parts = path.parts
            if any(excluded in parts for excluded in settings.EXCLUDED_DIRS):
                continue

            # Check extension
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                if path.stat().st_size <= settings.MAX_FILE_SIZE_KB * 1024:
                    files.append(path)

        return files

    def index_python_file(self, file_path: Path) -> List[CodeChunk]:
        """Parse Python AST to extract classes, functions, and top-level chunks."""
        chunks: List[CodeChunk] = []
        rel_path = str(file_path.relative_to(self.target_dir)).replace("\\", "/")

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return chunks

        lines = content.splitlines()
        try:
            tree = ast.parse(content, filename=str(file_path))
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = node.lineno
                    end = node.end_lineno or (start + 20)
                    chunk_text = "\n".join(lines[start - 1:end])
                    chunks.append(
                        CodeChunk(
                            chunk_id=f"{rel_path}:{start}-{end}",
                            file_path=rel_path,
                            start_line=start,
                            end_line=end,
                            content=chunk_text,
                            symbol_name=node.name,
                            symbol_type="function",
                            language="python",
                        )
                    )
                elif isinstance(node, ast.ClassDef):
                    start = node.lineno
                    end = node.end_lineno or (start + 30)
                    chunk_text = "\n".join(lines[start - 1:end])
                    chunks.append(
                        CodeChunk(
                            chunk_id=f"{rel_path}:{start}-{end}",
                            file_path=rel_path,
                            start_line=start,
                            end_line=end,
                            content=chunk_text,
                            symbol_name=node.name,
                            symbol_type="class",
                            language="python",
                        )
                    )
        except Exception:
            pass

        # If AST chunks are sparse or for whole file context, create sliding chunks
        if not chunks:
            chunks = self._sliding_window_chunks(rel_path, lines, "python")

        return chunks

    def _sliding_window_chunks(
        self, rel_path: str, lines: List[str], language: str
    ) -> List[CodeChunk]:
        """Generate windowed chunks for non-AST or general files."""
        chunks = []
        total_lines = len(lines)
        if total_lines == 0:
            return chunks

        step = max(1, settings.RAG_CHUNK_SIZE - settings.RAG_CHUNK_OVERLAP)
        for i in range(0, total_lines, step):
            start = i + 1
            end = min(total_lines, i + settings.RAG_CHUNK_SIZE)
            chunk_text = "\n".join(lines[start - 1:end])
            if chunk_text.strip():
                chunks.append(
                    CodeChunk(
                        chunk_id=f"{rel_path}:{start}-{end}",
                        file_path=rel_path,
                        start_line=start,
                        end_line=end,
                        content=chunk_text,
                        symbol_name=None,
                        symbol_type="block",
                        language=language,
                    )
                )
        return chunks

    def index_codebase(self) -> List[CodeChunk]:
        """Index the entire target directory."""
        all_chunks: List[CodeChunk] = []
        files = self.discover_files()

        for file_path in files:
            lang = self.SUPPORTED_EXTENSIONS.get(file_path.suffix.lower(), "text")
            if lang == "python":
                chunks = self.index_python_file(file_path)
            else:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    rel_path = str(file_path.relative_to(self.target_dir)).replace("\\", "/")
                    chunks = self._sliding_window_chunks(rel_path, content.splitlines(), lang)
                except Exception:
                    chunks = []
            all_chunks.extend(chunks)

        return all_chunks
