import json

from harness.cli import main


MANAGED_FILES = {
    "config.json",
    "ARCHITECTURE.md",
    "PROMPT_TEMPLATE.md",
    "REVIEW_CHECKLIST.md",
    "manifest.json",
}


def test_init_creates_all_harness_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init"])

    assert exit_code == 0
    assert {path.name for path in (tmp_path / ".harness").iterdir()} == MANAGED_FILES
    assert "initialized" in capsys.readouterr().out


def test_repeat_init_fails_without_force_and_preserves_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    config = tmp_path / ".harness" / "config.json"
    original = config.read_text(encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["init"])

    assert exit_code == 2
    assert config.read_text(encoding="utf-8") == original
    assert "already exists" in capsys.readouterr().err


def test_force_overwrites_managed_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    (harness_dir / "config.json").write_text("stale", encoding="utf-8")
    unmanaged = harness_dir / "notes.md"
    unmanaged.write_text("keep me", encoding="utf-8")

    exit_code = main(["init", "--force"])

    assert exit_code == 0
    assert json.loads((harness_dir / "config.json").read_text(encoding="utf-8"))
    assert unmanaged.read_text(encoding="utf-8") == "keep me"


def test_manifest_records_version_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    main(["init"])

    manifest = json.loads((tmp_path / ".harness" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1
