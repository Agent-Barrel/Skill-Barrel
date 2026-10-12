"""Opt-in live smoke tests: each spawns ONE real Claude Code session. Skipped
unless STEP2STEP_LIVE=1 (so the default suite never bills). Uses haiku by
default (override with STEP2STEP_MODEL) to keep usage small.

    STEP2STEP_LIVE=1 pytest -m live

The mid-session model-switch test needs a SECOND opt-in
(STEP2STEP_LIVE_MODEL_CONTROL=1) because it drives the /model picker on a live
session. It asserts the operator's ~/.claude/settings.json is byte-identical
afterwards, and is written so persist=True is unreachable from it.
"""
import hashlib
import os
import pathlib
import shutil

import pytest

pytestmark = pytest.mark.live

REPO = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = pathlib.Path.home() / ".claude" / "settings.json"


def _scrub_env():
    for k in list(os.environ):
        if k.upper().startswith("CLAUDE") or k.upper() in (
                "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            os.environ.pop(k, None)


def _settings_digest():
    try:
        return hashlib.sha256(SETTINGS.read_bytes()).hexdigest()
    except OSError:
        return None


@pytest.mark.skipif(os.environ.get("STEP2STEP_LIVE") != "1",
                    reason="live test; set STEP2STEP_LIVE=1 to run")
def test_bypass_one_prompt_creates_file():
    # Scrub so the nested spawn is a clean top-level session; force a cheap model.
    _scrub_env()
    model = os.environ.get("STEP2STEP_MODEL", "haiku")

    from step2step.claude import run_session

    workdir = REPO / "test-folder" / "pytest_live"
    shutil.rmtree(workdir, ignore_errors=True)
    res = run_session(
        ["Create a file named live.txt in the current working directory "
         "containing exactly one line: LIVE_OK"],
        str(workdir),
        mode="bypass",
        on_stall="skip",
        extra_args=["--model", model],
    )
    assert res["aborted"] is False
    assert res["completed"] == 1
    assert (workdir / "live.txt").read_text(encoding="utf-8").strip() == "LIVE_OK"


@pytest.mark.skipif(os.environ.get("STEP2STEP_LIVE") != "1",
                    reason="live test; set STEP2STEP_LIVE=1 to run")
def test_launch_flags_reach_the_transcript():
    """Layer A end to end: --model/--effort are what the turn actually ran on,
    and neither writes the operator's global settings."""
    _scrub_env()
    from step2step.claude import SessionHandle, last_model_effort, find_transcript

    before = _settings_digest()
    workdir = REPO / "test-folder" / "pytest_live_flags"
    shutil.rmtree(workdir, ignore_errors=True)
    h = SessionHandle.start(workdir=str(workdir), model="sonnet", effort="low")
    try:
        res = h.run_turn("reply with exactly PONG")
        assert res.outcome.value in ("completed", "completed_idle")
        actual = last_model_effort(find_transcript(h._runner.session_id))
        assert actual is not None
        assert "sonnet" in (actual["model"] or "")
        assert actual["effort"] == "low"
    finally:
        h.stop(force=True)
    assert _settings_digest() == before, \
        "launch flags must not touch ~/.claude/settings.json"


@pytest.mark.skipif(
    os.environ.get("STEP2STEP_LIVE") != "1"
    or os.environ.get("STEP2STEP_LIVE_MODEL_CONTROL") != "1",
    reason="drives the /model picker on a live session; "
           "set STEP2STEP_LIVE=1 and STEP2STEP_LIVE_MODEL_CONTROL=1")
def test_mid_session_model_switch_is_session_scoped():
    """The picker path, end to end, with the guarantee that matters: the
    operator's global default is untouched.

    persist is never passed, so it cannot be True here."""
    _scrub_env()
    from step2step.claude import SessionHandle, last_model_effort, find_transcript

    before = _settings_digest()
    workdir = REPO / "test-folder" / "pytest_live_switch"
    shutil.rmtree(workdir, ignore_errors=True)
    h = SessionHandle.start(workdir=str(workdir), model="sonnet", effort="low")
    try:
        first = h.run_turn("reply with exactly PONG")
        assert first.outcome.value in ("completed", "completed_idle")

        rows = h.available_models()
        assert rows, "the picker listed no models"
        assert h.peek_state().value == "idle", "available_models left a dialog open"

        state = h.set_model("haiku")             # session-only commit ('s')
        assert state.matches("haiku"), state

        second = h.run_turn("reply with exactly PONG2")
        assert second.outcome.value in ("completed", "completed_idle")
        actual = last_model_effort(find_transcript(h._runner.session_id))
        assert "haiku" in (actual["model"] or ""), actual
    finally:
        h.stop(force=True)
    assert _settings_digest() == before, \
        "a session-only model change must not rewrite ~/.claude/settings.json"
