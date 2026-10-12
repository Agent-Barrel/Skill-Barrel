"""CLI behavior that needs no Claude session: prompt listing and usage errors."""
import pytest

from step2step.claude import __main__ as cli


def _prompts(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("alpha\n---\nbeta", encoding="utf-8")
    return str(p)


def test_list_returns_zero(tmp_path, capsys):
    rc = cli.main(["--list", "--prompts", _prompts(tmp_path)])
    assert rc == 0
    assert "total 2 prompts" in capsys.readouterr().out


def test_missing_workdir_returns_two(tmp_path):
    # Not --list and no --workdir -> usage error (exit 2), no session spawned.
    rc = cli.main(["--prompts", _prompts(tmp_path)])
    assert rc == 2


def test_empty_prompts_returns_two(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    rc = cli.main(["--workdir", str(tmp_path), "--prompts", str(empty)])
    assert rc == 2


# --- --model / --effort -------------------------------------------------------
def test_unknown_effort_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["--workdir", str(tmp_path), "--prompts", _prompts(tmp_path),
                  "--effort", "ultra"])
    assert e.value.code == 2


def test_model_and_effort_reach_the_runner(monkeypatch, tmp_path):
    seen = {}

    class FakeRunner:
        def __init__(self, **kw):
            seen.update(kw)

        def run(self):
            return {"completed": 2, "total": 2, "mode": "bypass",
                    "aborted": False, "results": []}

    monkeypatch.setattr(cli, "Runner", FakeRunner)
    rc = cli.main(["--workdir", str(tmp_path), "--prompts", _prompts(tmp_path),
                   "--model", "haiku", "--effort", "low"])
    assert rc == 0
    assert (seen["model"], seen["effort"]) == ("haiku", "low")


def test_model_and_effort_default_to_none(monkeypatch, tmp_path):
    seen = {}

    class FakeRunner:
        def __init__(self, **kw):
            seen.update(kw)

        def run(self):
            return {"completed": 2, "total": 2, "mode": "bypass",
                    "aborted": False, "results": []}

    monkeypatch.setattr(cli, "Runner", FakeRunner)
    cli.main(["--workdir", str(tmp_path), "--prompts", _prompts(tmp_path)])
    assert seen["model"] is None and seen["effort"] is None
