from __future__ import annotations

import json
from pathlib import Path
from string import Formatter

from .policy import PolicyError, parse_policy, parse_profile
from .profiles import PROFILES, RULES, render_preflight
from .project import find_project_root
from .templates import PROMPT_TEMPLATE, managed_files


class PromptError(ValueError):
    pass


KIND_FOCUS = {
    "feature": "Prioritize the user-visible outcome.",
    "bugfix": "Prioritize reproducing the failure and identifying the root cause.",
    "refactor": "Prioritize preserving existing behavior and clarifying code boundaries.",
}
PROMPT_FIELDS = {"kind", "task_description", "constraints", "architecture", "checklist", "kind_focus", "preflight"}
REQUIRED_PROMPT_FIELDS = {"task_description", "constraints"}


def validate_prompt_template(template: str) -> None:
    try:
        parts = list(Formatter().parse(template))
    except ValueError as error:
        raise PromptError(f"invalid format: {error}") from error
    fields = set()
    for _, field, format_spec, conversion in parts:
        if field is None:
            continue
        if field not in PROMPT_FIELDS or format_spec or conversion:
            raise PromptError(f"unsupported placeholder: {{{field}}}")
        fields.add(field)
    missing = REQUIRED_PROMPT_FIELDS - fields
    if missing:
        formatted = ", ".join(f"{{{name}}}" for name in sorted(missing))
        raise PromptError(f"missing required placeholder(s): {formatted}")


def _read_required(root: Path, name: str) -> str:
    path = root / ".harness" / name
    if not path.is_file():
        raise PromptError(f"Run harness init before prompt (or use harness setup): missing .harness/{name}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PromptError(f"cannot read .harness/{name}: {error}") from error


def _load_config(root: Path) -> object:
    content = _read_required(root, "config.json")
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise PromptError(f".harness/config.json: {error}") from error


def _project_context(root: Path, name: str, default: str, *, required: bool) -> str:
    if required or (root / ".harness" / name).exists():
        return _read_required(root, name).strip()
    return default.strip()


def render_prompt(
    task_description: str, kind: str, root: Path | None = None, *, profile_name: str | None = None
) -> str:
    task = task_description.strip()
    if not task:
        raise PromptError("task description must not be empty")
    if kind not in KIND_FOCUS:
        raise PromptError(f"unsupported task kind: {kind}")

    if profile_name is not None:
        try:
            profile_name = parse_profile({}, profile_name)
        except PolicyError as error:
            raise PromptError(str(error)) from error
        if not PROFILES[profile_name].rules:
            return _lightweight_prompt(task, kind)

    project_root = root if root is not None else find_project_root(Path.cwd())
    config = _load_config(project_root)
    try:
        selected_name = parse_profile(config, profile_name)
        selected = PROFILES[selected_name]
        if not selected.rules:
            return _lightweight_prompt(task, kind)
        policy = parse_policy(config)
        has_project_rules = bool(PROFILES[parse_profile(config)].rules)
    except PolicyError as error:
        raise PromptError(f".harness/config.json: {error}") from error

    defaults = managed_files(selected_name)
    architecture = _project_context(
        project_root, "ARCHITECTURE.md", str(defaults["ARCHITECTURE.md"]), required=has_project_rules
    )
    checklist = _project_context(
        project_root, "REVIEW_CHECKLIST.md", str(defaults["REVIEW_CHECKLIST.md"]), required=has_project_rules
    )
    template = _project_context(project_root, "PROMPT_TEMPLATE.md", PROMPT_TEMPLATE, required=False)
    try:
        validate_prompt_template(template)
    except PromptError as error:
        raise PromptError(f".harness/PROMPT_TEMPLATE.md: {error}") from error

    return template.format(
        kind=kind,
        task_description=task,
        constraints="\n".join(RULES[rule].render(policy) for rule in selected.rules),
        preflight=render_preflight(selected),
        architecture=architecture,
        checklist=checklist,
        kind_focus=KIND_FOCUS[kind],
    )


def _lightweight_prompt(task: str, kind: str) -> str:
    return f"# Engineering Task\n\nTask type: {kind}\n\n{task}\n\n{KIND_FOCUS[kind]}"
