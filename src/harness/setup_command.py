from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from .init_command import InitializationError, render_file_content, write_atomic
from .policy import PolicyError, parse_profile
from .profiles import PROFILES, Profile
from .templates import managed_files


BEGIN = "<!-- AgentRig: begin -->"
END = "<!-- AgentRig: end -->"
AGENT_GUIDANCE = """\
{begin}
## Engineering Harness

{scope}, run:

    harness prompt --kind feature -- "Describe the current task"

Choose `feature`, `bugfix`, or `refactor` to match the task. Read the generated prompt and answer its applicable preflight questions before changing code. Apply the project rules that are relevant to the task.
{note}
After using Harness for a change, run `harness check --json` and review the findings in context.
{end}
"""

# Fingerprints of previously shipped built-in templates. Only stock content is replaced.
LEGACY_TEMPLATES = {
    "ARCHITECTURE.md": {
        "973b014f143e8baf89d0cbbd14c4a199371274c97c929229d67ae94f609f3b90",
        "596c7d83498f7580ead889501a704945073f3355a45859071df6b32793850028",
        "5347ff9b32f9b30a8d54a26807bc2a22ef8d7c5884bcfa9ea5392223dbab1da0",
        "60c7c6e324af7664488b6099d14f93bd9ec7c23f6d0a618ded757461c1359d2a",
        "c85a6cccfe19a6d8e0905bb18f56ecf831db7c387fd84f9afc94a192db1b5801",
    },
    "PROMPT_TEMPLATE.md": {
        "3fbe7c0e0fa99ac9dd9455fe369aa593c787f9a4b9a036ac4aa13013f568e703",
        "019c7447f00d3ada493c0f75c6e194f1912be959a06d84c076c60edb98c88009",
        "55506da513a55ddea3c9fe8deb58990a9108cfbd28a410bb2c0ea11324909372",
        "cc1c6ecac7259a0b773b2e31581e546887c9550e69098a4ddb6f5dbf643e4133",
    },
    "REVIEW_CHECKLIST.md": {
        "18a32e5bff89b636bf256a462c1d14a16dfe7b65bb5afcf15247db972605eabc",
        "584310cfa59207ffd2d58a7b0075d3291a1d08a23433615e92d058811cf9ab55",
        "3b52fef3e0f049b95e9feb3fa41917e314f14c814ef224d3fa55fc1ea9fd08de",
        "64a407196fdddd728b3c41372013c45a116d4528e74302bd0cfa8a07b077de24",
        "20575e94db2b1ab089d8ad776ee3cc60569bf15b4e7a7e23b2c5fd9a43581129",
    },
}


def _read_if_present(path: Path) -> str | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InitializationError(f"expected a regular file: {path}")
    if not path.exists():
        return None
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeError as error:
        raise InitializationError(f"expected UTF-8 text: {path}") from error


def _merge_guidance(original: str, path: Path, profile: Profile) -> str:
    newline = "\r\n" if "\r\n" in original else "\n"
    enabled = bool(profile.agent_scope)
    block = AGENT_GUIDANCE.format(
        begin=BEGIN, end=END, scope=profile.agent_scope, note=profile.agent_note
    ).replace("\n", newline)
    if BEGIN not in original and END not in original:
        if not enabled:
            return original
        separator = ""
        if original and not original.endswith(newline * 2):
            separator = newline if original.endswith(newline) else newline * 2
        return original + separator + block

    start = original.find(BEGIN)
    end = original.find(END)
    if original.count(BEGIN) != 1 or original.count(END) != 1 or start > end:
        raise InitializationError(f"invalid AgentRig markers in {path.name}")
    replacement = block.removesuffix(newline) if enabled else ""
    return original[:start] + replacement + original[end + len(END):]


def setup_project(root: Path, *, profile_name: str | None = None) -> list[Path]:
    if not root.is_dir():
        raise InitializationError(f"project path is not a directory: {root}")
    harness_dir = root / ".harness"
    if harness_dir.is_symlink() or (harness_dir.exists() and not harness_dir.is_dir()):
        raise InitializationError(f"expected a project directory: {harness_dir}")

    config_path = harness_dir / "config.json"
    original_config = _read_if_present(config_path)
    try:
        config = json.loads(original_config) if original_config is not None else {}
        selected = parse_profile(config, profile_name)
    except (json.JSONDecodeError, PolicyError) as error:
        raise InitializationError(f".harness/config.json: {error}") from error

    defaults = managed_files(selected)
    pending: dict[Path, str | None] = {}
    stored_profile = config.get("profile")
    if (
        original_config is not None
        and (profile_name is not None or stored_profile is not None)
        and stored_profile != selected
    ):
        pending[config_path] = render_file_content({**config, "profile": selected})

    for name, default in defaults.items():
        path = harness_dir / name
        existing = _read_if_present(path)
        if existing is None:
            pending[path] = render_file_content(default)
        elif name in LEGACY_TEMPLATES:
            normalized = existing.replace("\r\n", "\n")
            updated = render_file_content(default)
            if normalized != updated and sha256(normalized.encode("utf-8")).hexdigest() in LEGACY_TEMPLATES[name]:
                pending[path] = updated
        elif name == "manifest.json":
            try:
                manifest = json.loads(existing)
            except json.JSONDecodeError:
                continue
            if manifest != default and any(manifest == managed_files(name)["manifest.json"] for name in PROFILES):
                pending[path] = render_file_content(default)

    agent_files = ["AGENTS.md", "CLAUDE.md"]
    override = root / "AGENTS.override.md"
    if _read_if_present(override):
        agent_files.append(override.name)
    for name in agent_files:
        path = root / name
        existing = _read_if_present(path) or ""
        updated = _merge_guidance(existing, path, PROFILES[selected])
        if updated != existing:
            pending[path] = updated if updated.strip() else None

    harness_dir.mkdir(exist_ok=True)
    for path, content in pending.items():
        if content is None:
            path.unlink()
        else:
            write_atomic(path, content)
    return [path.relative_to(root) for path in pending]
