import json

from harness.cli import main


def test_frontend_project_applies_readability_rule_without_source_scan(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["setup", "--profile", "frontend"]) == 0
    assert "harness prompt" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "harness prompt" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert {path.name for path in (tmp_path / ".harness").iterdir()} == {
        "ARCHITECTURE.md",
        "PROMPT_TEMPLATE.md",
        "REVIEW_CHECKLIST.md",
        "config.json",
        "manifest.json",
    }
    (tmp_path / "model.py").write_text("content = Column(Text)\ntime.sleep(10)\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["prompt", "Adjust table styling"]) == 0
    output = capsys.readouterr().out
    assert "Adjust table styling" in output
    assert "Core Engineering Constraints" in output
    assert "Page Copy and Readability" in output
    assert "small-print explanations" in output
    assert "object storage" not in output
    assert "Asynchronous" not in output

    assert main(["check", "--strict", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"blocking": [], "advisories": [], "files_scanned": 0}


def test_frontend_override_skips_full_stack_context(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["setup", "--profile", "backend"]) == 0
    architecture = tmp_path / ".harness" / "ARCHITECTURE.md"
    architecture.write_text(architecture.read_text() + "\nInternal backend context\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["prompt", "--profile", "frontend", "--", "Change the theme"]) == 0
    light = capsys.readouterr().out
    assert "Internal backend context" not in light
    assert "object storage" not in light

    assert main(["prompt", "Export reports"]) == 0
    complete = capsys.readouterr().out
    assert "Internal backend context" in complete
    assert "object storage" in complete
    assert len(light) < len(complete)


def test_backend_applies_language_checks_only_to_matching_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["setup", "--profile", "backend"]) == 0
    (tmp_path / "worker.py").write_text("time.sleep(10)\n", encoding="utf-8")
    (tmp_path / "worker.js").write_text("time.sleep(10)\n", encoding="utf-8")
    (tmp_path / "schema.sql").write_text("content TEXT\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["prompt", "Export reports"]) == 0
    prompt = capsys.readouterr().out
    assert "object storage" in prompt
    assert "queue and worker" in prompt

    assert main(["check", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert {(item["code"], item["path"]) for item in report["advisories"]} == {
        ("time-sleep", "worker.py"),
        ("large-database-field", "schema.sql"),
    }


def test_switch_to_frontend_updates_managed_guidance_and_preserves_manual_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Project notes\n\nUse the existing component library.\n", encoding="utf-8")
    assert main(["setup", "--profile", "backend"]) == 0
    assert "harness prompt" in agents.read_text()

    assert main(["setup", "--profile", "frontend"]) == 0
    assert "Use the existing component library." in agents.read_text()
    assert "harness prompt" in agents.read_text()
    assert "frontend changes" in agents.read_text()
    assert "backend changes involving data storage" not in agents.read_text()
    assert (tmp_path / "CLAUDE.md").exists()

    capsys.readouterr()
    assert main(["setup"]) == 0
    assert "already configured" in capsys.readouterr().out


def test_legacy_profile_is_read_then_normalized_by_setup(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["setup"]) == 0
    path = tmp_path / ".harness" / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    assert config["profile"] == "backend"
    config["profile"] = "python-backend"
    config["constraints"]["asynchronous_work"]["estimated_duration_max_seconds"] = 7
    path.write_text(json.dumps(config), encoding="utf-8")
    capsys.readouterr()

    assert main(["prompt", "Export a report"]) == 0
    assert "7 seconds" in capsys.readouterr().out
    assert main(["check", "--strict"]) == 0

    assert main(["setup"]) == 0
    config["profile"] = "backend"
    assert json.loads(path.read_text(encoding="utf-8")) == config
