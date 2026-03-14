from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=path.parent,
        encoding=encoding,
        newline="\n",
    ) as tmp_file:
        tmp_file.write(content)
        temp_name = tmp_file.name
    os.replace(temp_name, path)


def atomic_write_json(path: Path, data: Any, encoding: str = "utf-8") -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write_text(path, payload + "\n", encoding=encoding)


def read_json(path: Path, default: Any = None, encoding: str = "utf-8") -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding=encoding))

