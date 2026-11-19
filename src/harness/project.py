from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Find the closest configured project without crossing a Git boundary."""
    start = start.resolve()
    for directory in (start, *start.parents):
        if (directory / ".harness").exists() or (directory / ".git").exists():
            return directory
    return start
