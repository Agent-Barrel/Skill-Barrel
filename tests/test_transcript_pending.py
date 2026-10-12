"""T1/T2: pending_tool_use on a synthetic JSONL + tool_inputs collection."""
import json

from step2step.claude import transcript as tx


def _write(tmp_path, events):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return p


def _ask(tid, questions=None):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "AskUserQuestion", "id": tid,
         "input": {"questions": questions or [{"question": "Which?"}]}}]}}


def _plan(tid):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "ExitPlanMode", "id": tid,
         "input": {"plan": "1. do the thing"}}]}}


def _result(tid):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid}]}}


_PROMPT = {"type": "user", "message": {"content": "the prompt"}}


# --- T1: pending_tool_use ----------------------------------------------------
def test_pending_ask_detected(tmp_path):
    p = _write(tmp_path, [_PROMPT, _ask("tu_1")])
    got = tx.pending_tool_use(p)
    assert got["name"] == "AskUserQuestion"
    assert got["id"] == "tu_1"
    assert got["input"]["questions"][0]["question"] == "Which?"


def test_resolved_ask_is_not_pending(tmp_path):
    p = _write(tmp_path, [_PROMPT, _ask("tu_1"), _result("tu_1")])
    assert tx.pending_tool_use(p) is None


def test_pending_plan_detected(tmp_path):
    p = _write(tmp_path, [_PROMPT, _plan("tu_2")])
    got = tx.pending_tool_use(p)
    assert got["name"] == "ExitPlanMode"
    assert got["input"]["plan"] == "1. do the thing"


def test_last_unresolved_wins(tmp_path):
    # First question answered, second still open -> the second is pending.
    p = _write(tmp_path, [_PROMPT, _ask("tu_1"), _result("tu_1"), _ask("tu_2")])
    assert tx.pending_tool_use(p)["id"] == "tu_2"


def test_non_question_tool_not_pending(tmp_path):
    # An unresolved Bash tool_use must not read as a pending interaction.
    bash = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "id": "tu_9", "input": {}}]}}
    p = _write(tmp_path, [_PROMPT, bash])
    assert tx.pending_tool_use(p) is None


def test_missing_transcript_returns_none(tmp_path):
    assert tx.pending_tool_use(None) is None
    assert tx.pending_tool_use(str(tmp_path / "nope.jsonl")) is None


# --- T2: parse_transcript collects tool_inputs -------------------------------
def test_tool_inputs_collected(tmp_path):
    p = _write(tmp_path, [_PROMPT, _ask("tu_1")])
    turns = tx.parse_transcript(p)
    assert turns[0]["tools"] == ["AskUserQuestion"]
    assert turns[0]["tool_inputs"] == [{
        "name": "AskUserQuestion", "id": "tu_1",
        "input": {"questions": [{"question": "Which?"}]}}]


def test_tool_inputs_only_question_tools(tmp_path):
    write = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "id": "tu_3",
         "input": {"file_path": "x"}}]}}
    p = _write(tmp_path, [_PROMPT, write])
    turns = tx.parse_transcript(p)
    assert turns[0]["tools"] == ["Write"]
    assert turns[0]["tool_inputs"] == []
