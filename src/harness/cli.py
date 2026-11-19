from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .init_command import InitializationError, initialize
from .profiles import PROFILES, canonical_profile
from .project import find_project_root
from .prompt_command import KIND_FOCUS, PromptError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Generate engineering constraints and tool-neutral AI prompts.",
    )
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create .harness managed files")
    init_parser.add_argument("--force", action="store_true", help="overwrite harness managed files")

    setup_parser = commands.add_parser("setup", help="set up a project for Codex and Claude Code")
    setup_parser.add_argument("path", nargs="?", type=Path, help="project root (default: discover from cwd)")

    setup_parser.add_argument("--profile", type=canonical_profile, choices=tuple(PROFILES), help="default project profile")

    prompt_parser = commands.add_parser("prompt", help="print a complete AI prompt")
    prompt_parser.add_argument("task_description", help="task description, or - to read stdin")
    prompt_parser.add_argument(
        "--kind", choices=tuple(KIND_FOCUS), default="feature", help="task focus"
    )
    prompt_parser.add_argument("--path", type=Path, help="project root (default: discover from cwd)")

    prompt_parser.add_argument(
        "--profile", type=canonical_profile, choices=tuple(PROFILES), help="override the project profile for this task"
    )

    check_parser = commands.add_parser("check", help="validate harness files and scan risks")
    check_parser.add_argument("path", nargs="?", type=Path, help="project root (default: discover from cwd)")
    check_parser.add_argument("--strict", action="store_true", help="fail on advisory findings")
    check_parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            initialize(Path.cwd(), force=args.force)
            print("harness initialized")
            return 0
        if args.command == "setup":
            from .setup_command import setup_project

            root = args.path if args.path is not None else find_project_root(Path.cwd())
            changes = setup_project(root, profile_name=args.profile)
            if changes:
                print(f"harness configured in {root.resolve()}")
                for path in changes:
                    print(f"  {path}")
            else:
                print(f"harness already configured in {root.resolve()}")
            return 0
        if args.command == "prompt":
            from .prompt_command import render_prompt

            task = sys.stdin.read() if args.task_description == "-" else args.task_description
            print(render_prompt(task, args.kind, root=args.path, profile_name=args.profile))
            return 0
        if args.command == "check":
            from .check_command import run_check

            root = args.path if args.path is not None else find_project_root(Path.cwd())
            exit_code, output = run_check(root, strict=args.strict, as_json=args.json)
            print(output, end="" if output.endswith("\n") else "\n")
            return exit_code
    except (InitializationError, PromptError, OSError) as error:
        print(f"harness: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"harness: unexpected error: {error}", file=sys.stderr)
        return 3
    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
