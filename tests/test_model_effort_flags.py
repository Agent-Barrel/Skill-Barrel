"""Layer A: launch-time --model / --effort.

The whole point of this layer is that it never touches the TUI — it only shapes
argv. So these tests are about argv shape, flag precedence and the backward
compatibility bar (a Runner built the old way must produce the OLD argv exactly).
"""
import json

import pytest

from step2step.claude import transcript as tx
from step2step.claude.runner import EFFORT_LEVELS, Runner


def _runner(tmp_path, **kw):
    return Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
                  claude_exe="dummy-claude",  # explicit => no PATH lookup
                  logger=lambda m: None, **kw)


def _argv(tmp_path, **kw):
    r = _runner(tmp_path, **kw)
    r.settings_file = tmp_path / "settings.json"   # normally set by _prepare()
    return r._argv()


# --- argv shape ---------------------------------------------------------------
def test_argv_unchanged_without_model_or_effort(tmp_path):
    """The backward-compat bar: the default argv is byte-identical to the
    pre-existing shape, with no stray flags."""
    r = _runner(tmp_path)
    r.settings_file = tmp_path / "settings.json"
    assert r._argv() == [
        "dummy-claude",
        "--session-id", r.session_id,
        "--settings", str(r.settings_file),
        "--dangerously-skip-permissions",
    ]


def test_argv_appends_model_and_effort(tmp_path):
    argv = _argv(tmp_path, model="haiku", effort="low")
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--effort") + 1] == "low"


def test_argv_model_only(tmp_path):
    argv = _argv(tmp_path, model="claude-opus-5")
    assert argv[argv.index("--model") + 1] == "claude-opus-5"
    assert "--effort" not in argv


def test_argv_effort_only(tmp_path):
    argv = _argv(tmp_path, effort="xhigh")
    assert argv[argv.index("--effort") + 1] == "xhigh"
    assert "--model" not in argv


def test_extra_args_stay_last(tmp_path):
    argv = _argv(tmp_path, model="haiku", extra_args=["--verbose", "--ide"])
    assert argv[-2:] == ["--verbose", "--ide"]


@pytest.mark.parametrize("extra", [["--model", "sonnet"], ["--model=sonnet"]])
def test_extra_args_model_wins_and_is_not_duplicated(tmp_path, extra):
    """SessionHandle.start puts --model in extra_args, so the ctor value must
    defer rather than emit the flag twice."""
    argv = _argv(tmp_path, model="haiku", extra_args=extra)
    assert argv.count("--model") + sum(a.startswith("--model=") for a in argv) == 1
    assert "haiku" not in argv


@pytest.mark.parametrize("extra", [["--effort", "max"], ["--effort=max"]])
def test_extra_args_effort_wins_and_is_not_duplicated(tmp_path, extra):
    argv = _argv(tmp_path, effort="low", extra_args=extra)
    assert argv.count("--effort") + sum(a.startswith("--effort=") for a in argv) == 1
    assert "low" not in argv


def test_model_is_not_validated(tmp_path):
    """Aliases, full names and models that do not exist yet are all legal — only
    the server decides. Validating here would reject future model names."""
    argv = _argv(tmp_path, model="some-model-from-2027")
    assert "some-model-from-2027" in argv


# --- effort validation --------------------------------------------------------
@pytest.mark.parametrize("level", EFFORT_LEVELS)
def test_every_documented_effort_level_is_accepted(tmp_path, level):
    assert _runner(tmp_path, effort=level).effort == level


def test_invalid_effort_raises(tmp_path):
    with pytest.raises(ValueError) as e:
        _runner(tmp_path, effort="ultra")
    assert "effort" in str(e.value)


def test_effort_levels_match_the_cli_flag():
    assert EFFORT_LEVELS == ("low", "medium", "high", "xhigh", "max")


# --- transcript.last_model_effort ---------------------------------------------
def _jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return path


def test_last_model_effort_reads_last_assistant_record(tmp_path):
    p = _jsonl(tmp_path / "t.jsonl", [
        {"type": "user", "message": {"content": "hi"}},
        {"type": "assistant", "effort": "high",
         "message": {"model": "claude-opus-5", "content": []}},
        {"type": "assistant", "effort": "low",
         "message": {"model": "claude-haiku-4-5", "content": []}},
    ])
    assert tx.last_model_effort(p) == {"model": "claude-haiku-4-5",
                                       "effort": "low", "records": 2}


def test_last_model_effort_reports_none_effort_for_models_without_one(tmp_path):
    """A switch to a model that reports no effort must read as None, not as the
    stale previous value."""
    p = _jsonl(tmp_path / "t.jsonl", [
        {"type": "assistant", "effort": "max",
         "message": {"model": "claude-opus-5", "content": []}},
        {"type": "assistant", "message": {"model": "claude-haiku-4-5", "content": []}},
    ])
    assert tx.last_model_effort(p)["effort"] is None


def test_last_model_effort_none_without_assistant_records(tmp_path):
    p = _jsonl(tmp_path / "t.jsonl", [{"type": "user", "message": {"content": "hi"}}])
    assert tx.last_model_effort(p) is None


def test_last_model_effort_tolerates_missing_and_broken_files(tmp_path):
    assert tx.last_model_effort(None) is None
    assert tx.last_model_effort(tmp_path / "nope.jsonl") is None
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n{\"type\": \"assistant\", \"message\": {}}\n",
                   encoding="utf-8")
    assert tx.last_model_effort(bad) == {"model": None, "effort": None, "records": 1}
