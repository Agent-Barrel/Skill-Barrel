"""F7: transcript parser turns the JSONL into per-turn {prompt, response, tools}."""
import json

from step2step.claude import transcript as tx

# A minimal transcript mirroring the real schema: user(str) starts a turn,
# tool_result user messages are folded in, assistant text is the response.
_EVENTS = [
    {"type": "mode"},
    {"type": "user", "message": {"content": "make hello.txt with PONG"}},
    {"type": "assistant", "message": {"content": [{"type": "thinking"}]}},
    {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write"}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
    {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Done. Created hello.txt."}]}},
    {"type": "user", "message": {"content": "now ask me something"}},
    {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "AskUserQuestion"},
        {"type": "text", "text": "Which option?"}]}},
]


def _write(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in _EVENTS), encoding="utf-8")
    return p


def test_two_turns(tmp_path):
    turns = tx.parse_transcript(_write(tmp_path))
    assert [t["index"] for t in turns] == [1, 2]


def test_prompt_and_response(tmp_path):
    turns = tx.parse_transcript(_write(tmp_path))
    assert turns[0]["prompt"] == "make hello.txt with PONG"
    assert "Created hello.txt" in turns[0]["response"]
    assert turns[0]["tools"] == ["Write"]


def test_tool_result_not_a_new_turn(tmp_path):
    # The tool_result user message must fold into turn 1, not start a turn.
    turns = tx.parse_transcript(_write(tmp_path))
    assert len(turns) == 2


def test_turn_asks_question(tmp_path):
    turns = tx.parse_transcript(_write(tmp_path))
    assert tx.turn_asks_question(turns[1]) is True
    assert tx.turn_asks_question(turns[0]) is False


def test_missing_file_returns_empty():
    assert tx.parse_transcript(None) == []
    assert tx.parse_transcript("nonexistent-xyz.jsonl") == []
