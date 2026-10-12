"""Opt-in subscription-backed integration checks in disposable workspaces.

STEP2STEP_CODEX_LIVE=1 pytest -q -s tests/codex/test_live.py
STEP2STEP_CODEX_MODEL overrides the lightweight default test model.
"""
import hashlib
import os
from pathlib import Path
import time

import pytest

from step2step.codex import SessionHandle, TurnOutcome

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("STEP2STEP_CODEX_LIVE") != "1",
                                                reason="set STEP2STEP_CODEX_LIVE=1 for real Codex tests")]


def _config_digest():
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.toml")}


@pytest.fixture
def live_session(tmp_path):
    handles = []
    before = _config_digest()
    def start(**kwargs):
        h = SessionHandle.start(workdir=tmp_path / "work", app_dir=tmp_path / "logs",
                                model=os.environ.get("STEP2STEP_CODEX_MODEL", "gpt-5.6-luna"),
                                effort="low", turn_timeout=180, request_timeout=30, **kwargs)
        handles.append(h)
        print("Codex session:", h.session_id, "artifacts:", h.run_dir, flush=True)
        return h
    yield start
    for h in handles:
        h.stop(force=True)
        assert not h.is_alive()
        assert h._transport.proc.poll() is not None
    assert _config_digest() == before, "Codex control modified global config"


def test_live_files_model_effort_and_resume(live_session):
    h = live_session(system_prompt_append="Begin every final reply with CHARTER_OK. This is a session-level role instruction.")
    r = h.run_turn("Create live.txt containing exactly FIRST using a file-writing tool, then reply DONE.")
    assert r.outcome == TurnOutcome.COMPLETED, r
    assert r.response.startswith("CHARTER_OK"), r.response
    assert (h.workdir / "live.txt").read_text().strip() == "FIRST"
    r = h.run_turn("Append a newline and SECOND to the file you just created. Then reply DONE.")
    assert r.outcome == TurnOutcome.COMPLETED, r
    assert r.response.startswith("CHARTER_OK"), r.response
    assert (h.workdir / "live.txt").read_text().splitlines() == ["FIRST", "SECOND"]
    rows = h.available_models()
    other = next((row for row in rows if row.name == "gpt-5.6-sol"), None)
    assert other is not None
    h.set_model(other.name, effort="medium")
    r = h.run_turn("Reply with exactly MODEL_CHANGED. Do not use tools.")
    assert r.outcome == TurnOutcome.COMPLETED, r
    state = h.model_state(refresh=True)
    assert state.model == other.name and state.effort == "medium", state
    session_id = h.session_id
    h.stop()
    resumed = live_session(session_id=session_id)
    assert len(resumed.transcript_turns()) >= 3
    r = resumed.run_turn("Without reading files, what were the two exact words you wrote to live.txt earlier?")
    assert r.outcome == TurnOutcome.COMPLETED, r
    assert "FIRST" in r.response and "SECOND" in r.response


def test_live_question_plan_reject_and_approve(live_session):
    h = live_session(mode="plan")
    p = h.send_prompt("Plan creating a one-line greeting.txt. Before writing your final plan, use the "
                      "request_user_input tool to ask whether its content should be HELLO or HI. "
                      "Do not decide for me. Do not create files until implementation is approved.")
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.AWAITING_MENU, r
    assert r.pending.kind == "ask_user_question"
    h.answer_questions({q["id"]: "HELLO" for q in r.pending.questions})
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.AWAITING_PLAN_APPROVAL, r
    assert not (h.workdir / "greeting.txt").exists()
    p = h.reject_plan("Use the filename revised.txt instead. The content choice HELLO is final; ask no more questions.")
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.AWAITING_PLAN_APPROVAL, r
    assert not (h.workdir / "revised.txt").exists()
    assert "revised.txt" in r.pending.plan
    h.approve_plan()
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.COMPLETED, r
    assert (h.workdir / "revised.txt").read_text().strip() == "HELLO"
    assert not (h.workdir / "greeting.txt").exists()


def test_live_interrupt_and_next_turn(live_session):
    h = live_session()
    p = h.send_prompt("Use a shell tool to execute `python3 -c 'import time; time.sleep(30)'`. "
                      "Wait until it finishes, then create interrupted.txt containing FINISHED.")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        turns = h.transcript_turns()
        if turns and "commandExecution" in turns[-1]["tools"]:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Codex never started the command to interrupt")
    h.interrupt()
    assert h.wait_turn(p).outcome == TurnOutcome.INTERRUPTED
    assert not (h.workdir / "interrupted.txt").exists()
    r = h.run_turn("The earlier task is cancelled. Reply only INTERRUPT_OK; do not use tools.")
    assert r.outcome == TurnOutcome.COMPLETED and "INTERRUPT_OK" in r.response


def test_live_command_approval(live_session):
    h = live_session(approval_policy="untrusted", sandbox_mode="workspace-write")
    p = h.send_prompt("Use a shell command to run `python3 -c \"from pathlib import Path; "
                      "Path('approval.txt').write_text('APPROVED')\"`. Do not use apply_patch. "
                      "If permission is requested, wait for it.")
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.AWAITING_MENU, r
    assert r.pending.kind == "command_approval", r
    assert not (h.workdir / "approval.txt").exists()
    h.answer_approval("accept", request_id=r.pending.request_id)
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.COMPLETED, r
    assert (h.workdir / "approval.txt").read_text() == "APPROVED"


def test_live_cli_plan_batch(tmp_path):
    import json
    import subprocess
    import sys
    prompts = tmp_path / "prompts.md"
    prompts.write_text("Create batch.txt containing exactly BATCH_OK. No questions are needed.", encoding="utf-8")
    before = _config_digest()
    result = subprocess.run([
        sys.executable, "-m", "step2step.codex", "--workdir", str(tmp_path / "work"),
        "--app-dir", str(tmp_path / "logs"), "--prompts", str(prompts), "--mode", "plan",
        "--model", os.environ.get("STEP2STEP_CODEX_MODEL", "gpt-5.6-luna"), "--effort", "low",
        "--turn-timeout", "120"], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr + result.stdout
    summary = json.loads(result.stdout)
    assert summary["completed"] == 1 and not summary["aborted"]
    assert (tmp_path / "work/batch.txt").read_text().strip() == "BATCH_OK"
    assert _config_digest() == before
