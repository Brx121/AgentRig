from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .policy import Policy


@dataclass(frozen=True)
class Rule:
    render: Callable[[Policy], str]
    preflight: str
    architecture_section: str
    architecture_guidance: str
    checklist: tuple[str, ...]
    config_key: str | None = None
    defaults: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class Profile:
    rules: tuple[str, ...]
    checks: tuple[str, ...] = ()
    agent_scope: str = ""
    agent_note: str = ""


DEFAULT_OBJECT_MAX_BYTES = 1048576
DEFAULT_ASYNC_SECONDS = 3


def _object_storage(policy: Policy) -> str:
    limit = policy.database_object_max_bytes
    size = "1 MB (1,048,576 bytes)" if limit == DEFAULT_OBJECT_MAX_BYTES else f"{limit} bytes"
    return f"- Objects larger than {size} must use object storage; store only their metadata in the database."


def _background_work(policy: Policy) -> str:
    return (
        "- Decide whether the response needs the final result. Run slow or unpredictable work that can be "
        "acknowledged first in a queue and worker. Return a job ID promptly and provide a way to query "
        "status or results. Define concurrency limits, retries, cancellation, and failure reporting.\n"
        f"- Evaluate background execution when work is expected to exceed {policy.estimated_duration_max_seconds} seconds "
        "or has unpredictable duration. If it stays synchronous, explain why the response needs the final result "
        "and define a bounded end-to-end latency budget.\n"
        "- When a request repeatedly times out, identify what makes it slow and reassess whether it needs "
        "to wait for completion. Move work suitable for background execution to the queue instead of "
        "repeatedly increasing the request timeout."
    )


RULES = {
    "object-storage": Rule(
        _object_storage,
        "Data model and storage choice",
        "Data and Storage",
        "Record the project's storage choices and where object metadata is kept.",
        (
            "Confirm objects above the configured limit use object storage and the database stores only their metadata.",
        ),
        config_key="storage",
        defaults=(("database_object_max_bytes", DEFAULT_OBJECT_MAX_BYTES),),
    ),
    "background-work": Rule(
        _background_work,
        "Asynchronous and concurrent strategy. Decide whether the response needs the final result. "
        "Explain the synchronous latency budget or the background job design.",
        "Asynchronous Work",
        "Record which responses need the final result, the expected latency budget, and the queue and worker in use.",
        (
            "Confirm slow or unpredictable work that can be acknowledged first gets a job ID and runs in the background.",
            "Confirm remaining synchronous work has a latency budget.",
            "Confirm background work has concurrency limits, retries, cancellation, and failure reporting.",
            "Confirm work suitable for background execution does not stay synchronous through repeated timeout increases.",
        ),
        config_key="asynchronous_work",
        defaults=(("estimated_duration_max_seconds", DEFAULT_ASYNC_SECONDS),),
    ),
}

DEFAULT_PROFILE = "backend"
BACKEND_RULES = ("object-storage", "background-work")
BACKEND_SCOPE = "For backend changes involving data storage, long request work, or async jobs"
BACKEND_NOTE = "Skip Harness for UI-only changes. For full-stack changes, apply the prompt to the backend portion."
PROFILES = {
    "backend": Profile(BACKEND_RULES, ("time-sleep", "large-database-field"), BACKEND_SCOPE, BACKEND_NOTE),
    "frontend": Profile(()),
}


def canonical_profile(name: str) -> str:
    return "backend" if name == "python-backend" else name


def render_preflight(profile: Profile) -> str:
    questions = ["Assumptions and uncertainties", *(RULES[name].preflight for name in profile.rules)]
    return "\n".join(f"{index}. {text}" for index, text in enumerate(questions, start=1))
