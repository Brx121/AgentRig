import json

from harness.cli import main


def test_check_reports_uninitialized_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["check"])

    assert exit_code == 1
    assert "missing .harness" in capsys.readouterr().out


def test_initialized_project_passes_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 0
    assert "No blocking issues" in capsys.readouterr().out


def test_missing_architecture_section_is_blocking(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    architecture = tmp_path / ".harness" / "ARCHITECTURE.md"
    architecture.write_text("# Architecture\n## Overview\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 1
    assert "missing required section" in capsys.readouterr().out


def test_harness_document_placeholder_is_blocking(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    checklist = tmp_path / ".harness" / "REVIEW_CHECKLIST.md"
    checklist.write_text(checklist.read_text(encoding="utf-8") + "\nTODO later\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 1
    assert "TODO" in capsys.readouterr().out


def test_invalid_json_is_blocking(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / ".harness" / "config.json").write_text("{", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 1
    assert "invalid-json" in capsys.readouterr().out


def test_non_positive_threshold_is_blocking(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    config_path = tmp_path / ".harness" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["constraints"]["storage"]["database_object_max_bytes"] = 0
    config_path.write_text(json.dumps(config), encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 1
    assert "invalid-threshold" in capsys.readouterr().out


def test_http_calls_pass_strict_check_without_timeout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "client.py").write_text('requests.get("https://example.com")\n', encoding="utf-8")
    (tmp_path / "app.js").write_text('fetch("https://example.com")\n', encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check", "--strict", "--json"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["advisories"] == []
    assert report["files_scanned"] == 2


def test_strict_mode_fails_on_advisory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "worker.py").write_text("time.sleep(10)\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check", "--strict"])

    assert exit_code == 1
    assert "time-sleep" in capsys.readouterr().out


def test_time_sleep_in_non_test_code_is_advisory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "worker.py").write_text("time.sleep(10)\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 0
    assert "time-sleep" in capsys.readouterr().out


def test_time_sleep_in_test_code_is_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_worker.py").write_text("time.sleep(0)\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 0
    assert "time-sleep" not in capsys.readouterr().out


def test_local_upload_path_passes_strict_check(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "settings.py").write_text('UPLOAD_DIR = "./uploads"\n', encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["check", "--strict"])

    assert exit_code == 0
    assert "No risk advisories found" in capsys.readouterr().out


def test_large_content_field_in_migration_is_advisory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_model_schema.py").write_text(
        "content = Column(Text)\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    exit_code = main(["check"])

    assert exit_code == 0
    assert "large-database-field" in capsys.readouterr().out


def test_json_report_is_parseable(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["check", "--json"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert set(report) == {"blocking", "advisories", "files_scanned"}
    assert isinstance(report["files_scanned"], int)


def test_oversized_file_generates_advisory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    oversized = tmp_path / "large.txt"
    oversized.write_bytes(b"x" * (1024 * 1024 + 1))
    capsys.readouterr()

    exit_code = main(["check"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "file-too-large" in output


def test_scan_skips_ignored_directories_locks_and_binary_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "client.py").write_text(
        "time.sleep(10)\n",
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\x00time.sleep(10)")
    capsys.readouterr()

    exit_code = main(["check", "--json"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report == {"blocking": [], "advisories": [], "files_scanned": 0}
