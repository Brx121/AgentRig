from io import StringIO
import json

import pytest

from harness.cli import main


def test_setup_keeps_project_guidance_and_is_repeatable(tmp_path, monkeypatch, capsys):
    project = tmp_path / "project"
    project.mkdir()
    agents = project / "AGENTS.md"
    claude = project / "CLAUDE.md"
    agents.write_bytes(b"# My existing guide\r\nKeep these instructions.\r\n")
    claude.write_text("# Claude instructions\n\nUse the project test command.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["setup", str(project)]) == 0
    assert agents.read_bytes().startswith(b"# My existing guide\r\nKeep these instructions.\r\n")
    assert claude.read_text(encoding="utf-8").startswith("# Claude instructions\n\nUse the project test command.\n")
    for path in (agents, claude):
        assert "harness prompt" in path.read_text(encoding="utf-8")

    configuration = project / ".harness" / "config.json"
    config = json.loads(configuration.read_text(encoding="utf-8"))
    config["constraints"]["storage"]["database_object_max_bytes"] = 2097152
    configuration.write_text(json.dumps(config), encoding="utf-8")
    first_run = {path: path.read_bytes() for path in (agents, claude, configuration)}
    capsys.readouterr()

    assert main(["setup", str(project)]) == 0
    assert "already configured" in capsys.readouterr().out
    assert first_run == {path: path.read_bytes() for path in first_run}


def test_prompt_resolves_project_or_accepts_explicit_path_and_stdin(tmp_path, monkeypatch, capsys):
    projects = [tmp_path / name for name in ("first", "second")]
    for project, limit in zip(projects, (2097152, 4194304), strict=True):
        project.mkdir()
        assert main(["setup", str(project)]) == 0
        path = project / ".harness" / "config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["constraints"]["storage"]["database_object_max_bytes"] = limit
        path.write_text(json.dumps(config), encoding="utf-8")

    subdir = projects[0] / "src"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    capsys.readouterr()
    assert main(["prompt", "--", "Export reports"]) == 0
    first = capsys.readouterr().out
    assert "2097152 bytes" in first
    assert "1 MB" not in first

    monkeypatch.setattr("sys.stdin", StringIO("Export reports\nInclude a status page\n"))
    assert main(["prompt", "--path", str(projects[1]), "--kind", "bugfix", "-"]) == 0
    second = capsys.readouterr().out
    assert "4194304 bytes" in second
    assert "Export reports\nInclude a status page" in second

    (subdir / ".git").mkdir()
    assert main(["prompt", "Nested repository task"]) == 2
    assert "missing .harness/config.json" in capsys.readouterr().err


def test_frontend_setup_upgrades_legacy_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Project notes\n\nUse the existing component library.\n", encoding="utf-8")
    harness = tmp_path / ".harness"
    harness.mkdir()
    (harness / "config.json").write_text('{"version": 1, "profile": "frontend"}\n', encoding="utf-8")
    (harness / "manifest.json").write_text(
        '{"version": 1, "managed_files": ["config.json", "manifest.json"]}\n', encoding="utf-8"
    )
    capsys.readouterr()

    assert main(["setup", "--profile", "frontend"]) == 0
    assert {path.name for path in harness.iterdir()} == {
        "ARCHITECTURE.md",
        "PROMPT_TEMPLATE.md",
        "REVIEW_CHECKLIST.md",
        "config.json",
        "manifest.json",
    }
    assert json.loads((harness / "manifest.json").read_text(encoding="utf-8"))["managed_files"] == [
        "config.json",
        "ARCHITECTURE.md",
        "PROMPT_TEMPLATE.md",
        "REVIEW_CHECKLIST.md",
        "manifest.json",
    ]
    assert "Use the existing component library." in agents.read_text(encoding="utf-8")
    assert "harness prompt" in agents.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("filename", "content", "error_code"),
    [
        ("config.json", '{"constraints": []}', "invalid-config"),
        ("PROMPT_TEMPLATE.md", "{task_description}", "invalid-prompt-template"),
    ],
)
def test_check_and_prompt_agree_on_invalid_inputs(tmp_path, monkeypatch, capsys, filename, content, error_code):
    monkeypatch.chdir(tmp_path)
    assert main(["setup"]) == 0
    (tmp_path / ".harness" / filename).write_text(content, encoding="utf-8")
    capsys.readouterr()

    assert main(["check", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert error_code in {issue["code"] for issue in report["blocking"]}

    assert main(["prompt", "Export reports"]) == 2
    assert filename in capsys.readouterr().err
