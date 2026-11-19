from __future__ import annotations

import json
from stat import S_IMODE
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import Mapping

from .templates import MANAGED_FILE_CONTENTS


class InitializationError(Exception):
    pass


def render_file_content(content: object) -> str:
    if isinstance(content, Mapping):
        return json.dumps(content, indent=2, ensure_ascii=False) + "\n"
    return str(content)


def write_atomic(destination: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content.encode("utf-8"))
        if destination.exists():
            temporary.chmod(S_IMODE(destination.stat().st_mode))
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def initialize(root: Path, *, force: bool = False) -> None:
    harness_dir = root / ".harness"
    if harness_dir.exists() and not harness_dir.is_dir():
        raise InitializationError(".harness exists but is not a directory")

    existing = [name for name in MANAGED_FILE_CONTENTS if (harness_dir / name).exists()]
    if existing and not force:
        joined = ", ".join(existing)
        raise InitializationError(f"harness managed files already exists: {joined}")

    harness_dir.mkdir(parents=True, exist_ok=True)
    for name, content in MANAGED_FILE_CONTENTS.items():
        write_atomic(harness_dir / name, render_file_content(content))
