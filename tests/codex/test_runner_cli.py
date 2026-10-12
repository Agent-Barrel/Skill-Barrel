import pytest

from step2step.codex import runner, __main__ as cli
from step2step.contracts import TurnOutcome


def wire(monkeypatch, make_session, **options):
    handles = []
    def start(**kwargs):
        h = make_session(mode=kwargs.get("mode", "bypass"), **options)
        h._transport.on_start = lambda t, p: t.complete(
            text="PLAN" if p["collaborationMode"]["mode"] == "plan" else "DONE",
            kind="plan" if p["collaborationMode"]["mode"] == "plan" else "agentMessage")
        handles.append(h)
        return h
    # Replace the facade without replacing the fixture's actual SessionHandle class.
    class Factory:
        pass
    Factory.start = staticmethod(start)
    monkeypatch.setattr(runner, "SessionHandle", Factory)
    return handles


def test_batch_plan_auto_approval_count_and_callback(make_session, monkeypatch, tmp_path):
    handles = wire(monkeypatch, make_session)
    records = []
    r = runner.run_session(["one", "two"], tmp_path, mode="plan", on_turn=records.append)
    assert not r["aborted"] and r["completed"] == 2
    assert len(records) == 2 and all(x["status"] == "completed" for x in records)
    h = handles[0]
    assert sum(m == "turn/start" for m, _ in h._transport.calls) == 4
    assert not h.is_alive()


def test_unhandled_question_aborts_without_guessing(make_session, monkeypatch, tmp_path):
    h = make_session(); h._transport.on_start = lambda t, p: t.question()
    class Factory:
        @staticmethod
        def start(**kw): return h
    monkeypatch.setattr(runner, "SessionHandle", Factory)
    r = runner.run_session(["ask", "must not run"], tmp_path)
    assert r["aborted"] and r["abort_reason"] == "awaiting_menu"
    assert r["completed"] == 0 and len(r["results"]) == 1
    assert not h._transport.answers
    assert not h.is_alive()


def test_handler_answers_request_then_batch_continues(make_session, monkeypatch, tmp_path):
    h = make_session(); h._transport.on_start = lambda t, p: t.question()
    class Factory:
        @staticmethod
        def start(**kw): return h
    monkeypatch.setattr(runner, "SessionHandle", Factory)
    def handler(handle, pending):
        handle.answer_menu(1)
        handle._transport.complete()
    r = runner.run_session(["ask"], tmp_path, interaction_handler=handler)
    assert r["completed"] == 1


def test_stall_skip_confirms_interrupt_before_next_prompt(make_session, monkeypatch, tmp_path):
    h = make_session(turn_timeout=0.01)
    h._transport.on_start = lambda t, p: t.complete() if t.turn_count == 2 else None
    class Factory:
        @staticmethod
        def start(**kw): return h
    monkeypatch.setattr(runner, "SessionHandle", Factory)
    r = runner.run_session(["hang", "finish"], tmp_path, on_stall="skip")
    assert not r["aborted"] and r["completed"] == 1 and len(r["results"]) == 2
    methods = [m for m, _ in h._transport.calls]
    assert methods.index("turn/interrupt") < len(methods) - 1 - methods[::-1].index("turn/start")


def test_cli_list_requires_no_executable(tmp_path, capsys):
    p = tmp_path / "prompts.md"; p.write_text("one\n---\ntwo")
    assert cli.main(["--prompts", str(p), "--list", "--codex", "/missing/codex"]) == 0
    assert "total 2 prompts" in capsys.readouterr().out


def test_cli_options_and_nonzero_incomplete_exit(monkeypatch, tmp_path):
    p = tmp_path / "prompts.md"; p.write_text("one")
    seen = {}
    def run(**kwargs):
        seen.update(kwargs)
        return {"completed": 0, "total": 1, "aborted": False}
    monkeypatch.setattr(cli, "run_session", run)
    assert cli.main(["--prompts", str(p), "--workdir", str(tmp_path), "--model", "model-a",
                     "--effort", "high", "--turn-timeout", "45"]) == 1
    assert seen["model"] == "model-a" and seen["turn_timeout"] == 45


def test_cli_missing_workdir_fails(tmp_path):
    p = tmp_path / "prompts.md"; p.write_text("one")
    with pytest.raises(SystemExit) as e: cli.main(["--prompts", str(p)])
    assert e.value.code == 2
