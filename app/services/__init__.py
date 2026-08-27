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