from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str
    line: int | None = None


def issue_to_dict(issue: Issue) -> dict[str, Any]:
    return asdict(issue)


def format_text(blocking: list[Issue], advisories: list[Issue], files_scanned: int) -> str:
    lines = [f"Harness check: {files_scanned} files scanned"]
    if blocking:
        lines.append("Blocking issues:")
        lines.extend(_format_issue(issue) for issue in blocking)
    else:
        lines.append("No blocking issues found")
    if advisories:
        lines.append("Risk advisories:")
        lines.extend(_format_issue(issue) for issue in advisories)
    else:
        lines.append("No risk advisories found")
    return "\n".join(lines) + "\n"


def format_json(blocking: list[Issue], advisories: list[Issue], files_scanned: int) -> str:
    report = {
        "blocking": [issue_to_dict(issue) for issue in blocking],
        "advisories": [issue_to_dict(issue) for issue in advisories],
        "files_scanned": files_scanned,
    }
    return json.dumps(report, indent=2) + "\n"


def _format_issue(issue: Issue) -> str:
    location = issue.path if issue.line is None else f"{issue.path}:{issue.line}"
    return f"- [{issue.code}] {issue.message} ({location})"
