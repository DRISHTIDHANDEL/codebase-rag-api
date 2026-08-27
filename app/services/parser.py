import ast
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChunkMetadata:
    file_path: str
    entity_type: str          # "function" | "class" | "import" | "text"
    symbol_name: Optional[str]
    start_line: int
    end_line: int
    content: str


SUPPORTED_TEXT_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".txt", ".json", ".yml", ".yaml"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
MAX_FALLBACK_CHUNK_LINES = 50  # for non-Python files, chunk every N lines

def parse_python_file(file_path: str, repo_root: str) -> List[ChunkMetadata]:
    """
    Parses a single .py file using Python's ast module.
    Extracts top-level functions, classes, and imports as separate chunks.
    Falls back gracefully if the file has a syntax error.
    """
    chunks: List[ChunkMetadata] = []
    relative_path = os.path.relpath(file_path, repo_root)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return chunks  # couldn't even read the file — skip it

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        # File has broken/invalid Python syntax — don't crash the whole pipeline,
        # just skip this file and move on.
        return chunks

    source_lines = source.splitlines()

    for node in ast.walk(tree):
        entity_type = None
        symbol_name = None

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entity_type = "function"
            symbol_name = node.name
        elif isinstance(node, ast.ClassDef):
            entity_type = "class"
            symbol_name = node.name
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            entity_type = "import"
            symbol_name = None

        if entity_type is None:
            continue

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        content = "\n".join(source_lines[start_line - 1:end_line])

        chunks.append(
            ChunkMetadata(
                file_path=relative_path,
                entity_type=entity_type,
                symbol_name=symbol_name,
                start_line=start_line,
                end_line=end_line,
                content=content,
            )
        )

    return chunks
def parse_generic_file(file_path: str, repo_root: str) -> List[ChunkMetadata]:
    """
    Fallback for non-Python files (.js, .ts, .md, etc.)
    Simple line-based chunking since we don't have an AST for these languages here.
    """
    chunks: List[ChunkMetadata] = []
    relative_path = os.path.relpath(file_path, repo_root)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return chunks

    if not lines:
        return chunks

    for i in range(0, len(lines), MAX_FALLBACK_CHUNK_LINES):
        chunk_lines = lines[i:i + MAX_FALLBACK_CHUNK_LINES]
        if not any(line.strip() for line in chunk_lines):
            continue  # skip empty chunks

        start_line = i + 1
        end_line = i + len(chunk_lines)

        chunks.append(
            ChunkMetadata(
                file_path=relative_path,
                entity_type="text",
                symbol_name=None,
                start_line=start_line,
                end_line=end_line,
                content="\n".join(chunk_lines),
            )
        )

    return chunks


def parse_repository(repo_root: str) -> List[ChunkMetadata]:
    """
    Walks the entire repository folder, parses every supported file,
    and returns a flat list of all code chunks found.
    """
    all_chunks: List[ChunkMetadata] = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Modify dirnames in-place to skip unwanted folders (git, node_modules, etc.)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_TEXT_EXTENSIONS:
                continue

            file_path = os.path.join(dirpath, filename)

            if ext == ".py":
                file_chunks = parse_python_file(file_path, repo_root)
            else:
                file_chunks = parse_generic_file(file_path, repo_root)

            all_chunks.extend(file_chunks)

    return all_chunks