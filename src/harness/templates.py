from __future__ import annotations

from .profiles import DEFAULT_PROFILE, PROFILES, RULES


PROMPT_TEMPLATE = """# Engineering Task

Task type: {kind}

## Task Description

{task_description}

## Required Preflight Answers

Answer these before proposing or writing implementation code:

{preflight}

## Core Engineering Constraints

{constraints}

## Project Architecture

{architecture}

## Review Checklist

{checklist}

## Kind Focus

{kind_focus}
"""


def managed_files(profile_name: str) -> dict[str, object]:
    rules = [RULES[name] for name in PROFILES[profile_name].rules]
    config = {"version": 1, "profile": profile_name}
    if not rules:
        return {
            "config.json": config,
            "manifest.json": {"version": 1, "managed_files": ["config.json", "manifest.json"]},
        }

    architecture = [
        "# Architecture",
        "## Overview\n\nDescribe the project's components, boundaries, and runtime model.",
        *(f"## {rule.architecture_section}\n\n{rule.architecture_guidance}" for rule in rules),
    ]
    checklist = ["# Review Checklist"]
    for rule in rules:
        items = "\n".join(f"- {item}" for item in rule.checklist)
        checklist.append(f"## {rule.architecture_section}\n\n{items}")

    constraints = {rule.config_key: dict(rule.defaults) for rule in rules if rule.config_key is not None}
    files = {
        "config.json": {**config, "constraints": constraints},
        "ARCHITECTURE.md": "\n\n".join(architecture) + "\n",
        "PROMPT_TEMPLATE.md": PROMPT_TEMPLATE,
        "REVIEW_CHECKLIST.md": "\n\n".join(checklist) + "\n",
    }
    return {**files, "manifest.json": {"version": 1, "managed_files": [*files, "manifest.json"]}}


MANAGED_FILE_CONTENTS = managed_files(DEFAULT_PROFILE)
CONFIG_TEMPLATE = MANAGED_FILE_CONTENTS["config.json"]
