import pytest

from harness.cli import main


def test_prompt_requires_initialization(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["prompt", "Add export"])

    assert exit_code == 2
    assert "Run harness init" in capsys.readouterr().err


def test_prompt_includes_task_and_core_constraints(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["prompt", "Add report export"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Add report export" in output
    assert "1 MB" in output
    assert "3 seconds" in output
    assert "repeatedly increasing the request timeout" in output
    for removed in (
        "Container local disk",
        "Schema and Compatibility",
        "Migration and compatibility",
        "Tests and acceptance criteria",
        "## Implementation Requirements",
        "External Integrations",
        "External call failure strategy",
        "## External Calls",
    ):
        assert removed not in output
    for heading in (
        "Assumptions and uncertainties",
        "Data model and storage choice",
        "Asynchronous and concurrent strategy",
    ):
        assert heading in output


@pytest.mark.parametrize("kind", ["feature", "bugfix", "refactor"])
def test_prompt_supports_all_kinds(tmp_path, monkeypatch, capsys, kind):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["prompt", "Adjust behavior", "--kind", kind])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert kind in output
    assert "1 MB" in output
    assert "3 seconds" in output
