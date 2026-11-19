from __future__ import annotations

import json
import re
from pathlib import Path

from .policy import PolicyError, parse_policy, parse_profile
from .profiles import PROFILES, RULES
from .prompt_command import PromptError, validate_prompt_template
from .reporting import Issue, format_json, format_text
from .templates import managed_files


SKIPPED_DIRECTORIES = {".git", ".harness", "node_modules", "venv", ".venv", "dist", "build"}
LOCK_FILES = {
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "cargo.lock",
    "composer.lock",
    "pipfile.lock",
}
MAX_READ_BYTES = 1024 * 1024
PLACEHOLDER_PATTERN = re.compile(r"(?i)\b(?:TBD|TODO)\b|<[^>\n]+>")
DATABASE_DEFINITION_PATH_PATTERN = re.compile(r"(?i)(?:migration|model|schema)")
LARGE_FIELD_PATTERN = re.compile(
    r"(?im)^[^\n]*\b(?:content|data)\b[^\n]*(?:text|bytea|blob|binary|jsonb)[^\n]*$"
)


def run_check(root: Path, *, strict: bool, as_json: bool) -> tuple[int, str]:
    if not root.is_dir():
        raise FileNotFoundError(f"check path is not a directory: {root}")
    selected, blocking = validate_harness(root)
    checks = PROFILES[selected].checks if selected is not None else ()
    advisories, files_scanned = scan_project(root, checks) if checks else ([], 0)
    output = (
        format_json(blocking, advisories, files_scanned)
        if as_json
        else format_text(blocking, advisories, files_scanned)
    )
    failed = bool(blocking) or (strict and bool(advisories))
    return (1 if failed else 0, output)


def validate_harness(root: Path) -> tuple[str | None, list[Issue]]:
    harness_dir = root / ".harness"
    if not harness_dir.is_dir():
        return None, [
            Issue(
                code="missing-harness",
                message="missing .harness directory; run harness setup",
                path=".harness",
            )
        ]

    config_path = harness_dir / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        selected = parse_profile(config)
        profile = PROFILES[selected]
        if profile.rules:
            parse_policy(config)
    except FileNotFoundError:
        return None, [
            Issue(code="missing-harness-file", message="missing required harness file: config.json", path=".harness/config.json")
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [Issue(code="invalid-json", message=f"invalid JSON: {error}", path=".harness/config.json")]
    except PolicyError as error:
        return None, [Issue(code=error.code, message=str(error), path=".harness/config.json")]

    issues = [
        Issue(
            code="missing-harness-file",
            message=f"missing required harness file: {name}",
            path=f".harness/{name}",
        )
        for name in managed_files(selected)
        if not (harness_dir / name).is_file()
    ]
    issues.extend(_validate_json_file(harness_dir / "manifest.json"))
    if profile.rules:
        sections = ("Overview", *(RULES[rule].architecture_section for rule in profile.rules))
        issues.extend(_validate_template(harness_dir / "PROMPT_TEMPLATE.md"))
        issues.extend(_validate_architecture(harness_dir / "ARCHITECTURE.md", sections))
        issues.extend(_validate_document_placeholders(harness_dir))
    return selected, issues


def scan_project(root: Path, checks: tuple[str, ...]) -> tuple[list[Issue], int]:
    scanners = [SOURCE_CHECKS[name] for name in checks]
    issues: list[Issue] = []
    files_scanned = 0
    for directory, directory_names, filenames in root.walk(top_down=True):
        directory_names[:] = [name for name in directory_names if name not in SKIPPED_DIRECTORIES]
        for filename in filenames:
            if filename in LOCK_FILES or filename.endswith(".lock"):
                continue
            path = directory / filename
            if path.is_symlink() or not path.is_file():
                continue
            try:
                with path.open("rb") as stream:
                    prefix = stream.read(8192)
                if b"\x00" in prefix:
                    continue
                if path.stat().st_size > MAX_READ_BYTES:
                    issues.append(
                        Issue(
                            code="file-too-large",
                            message="file exceeds the 1 MB scanner read limit and was not scanned",
                            path=_relative(path, root),
                        )
                    )
                    files_scanned += 1
                    continue
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            files_scanned += 1
            for scan in scanners:
                issues.extend(scan(path.relative_to(root), content))
    return issues, files_scanned


def _validate_json_file(path: Path) -> list[Issue]:
    if not path.is_file():
        return []
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [
            Issue(
                code="invalid-json",
                message=f"invalid JSON: {error}",
                path=_relative(path, path.parent.parent),
            )
        ]
    return []


def _validate_template(path: Path) -> list[Issue]:
    if not path.is_file():
        return []
    try:
        validate_prompt_template(path.read_text(encoding="utf-8"))
    except (PromptError, UnicodeError, OSError) as error:
        return [Issue(code="invalid-prompt-template", message=str(error), path=".harness/PROMPT_TEMPLATE.md")]
    return []


def _validate_architecture(path: Path, required_sections: tuple[str, ...]) -> list[Issue]:
    if not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    headings = {line.lstrip("#").strip() for line in content.splitlines() if line.startswith("## ")}
    missing = [section for section in required_sections if section not in headings]
    if not missing:
        return []
    return [
        Issue(
            code="missing-architecture-section",
            message=f"architecture document is missing required section: {section}",
            path=".harness/ARCHITECTURE.md",
        )
        for section in missing
    ]


def _validate_document_placeholders(harness_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted(harness_dir.glob("*.md")):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            match = PLACEHOLDER_PATTERN.search(line)
            if match:
                issues.append(
                    Issue(
                        code="harness-placeholder",
                        message=f"harness document contains placeholder: {match.group(0)}",
                        path=f".harness/{path.name}",
                        line=line_number,
                    )
                )
    return issues


def _check_time_sleep(path: Path, content: str) -> list[Issue]:
    if path.suffix.lower() != ".py" or _is_test_path(path):
        return []
    return [
        Issue(
            code="time-sleep",
            message="time.sleep found in non-test code; use an event loop, queue delay, or testable clock",
            path=path.as_posix(),
            line=line_number,
        )
        for line_number, line in enumerate(content.splitlines(), start=1)
        if re.search(r"\btime\.sleep\s*\(", line)
    ]


def _check_database_fields(path: Path, content: str) -> list[Issue]:
    if path.suffix.lower() in {".md", ".rst", ".txt"} or not DATABASE_DEFINITION_PATH_PATTERN.search(path.name):
        return []
    return [
        Issue(
            code="large-database-field",
            message="field may store large objects in the database",
            path=path.as_posix(),
            line=line_number,
        )
        for line_number, line in enumerate(content.splitlines(), start=1)
        if re.search(r"(?i)\b(?:blob|base64)\b", line) or LARGE_FIELD_PATTERN.search(line)
    ]


SOURCE_CHECKS = {
    "time-sleep": _check_time_sleep,
    "large-database-field": _check_database_fields,
}


def _is_test_path(path: Path) -> bool:
    return any(part in {"tests", "test"} or part.startswith("test_") or part.endswith("_test") for part in path.parts)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
