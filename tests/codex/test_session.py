from copy import deepcopy
import dataclasses
import threading
import time

import pytest

from step2step.codex import (AuthenticationError, ControlError, ModelControlError, SessionControl,
                            SessionState, TurnOutcome, UnsupportedOperation)
from .conftest import FakeTransport


def test_same_contract_and_no_tui_claim(make_session):
    h = make_session()
    assert isinstance(h, SessionControl)
    assert h.health()["screen_source"] == "activity_log"
    assert "screen" not in h.capabilities
    assert "questions" in h.capabilities


def test_subscription_required_and_failed_start_cleans_up(make_session, monkeypatch):
    monkeypatch.setattr(FakeTransport, "account_type", "apikey")
    with pytest.raises(AuthenticationError): make_session()
    assert not FakeTransport.instances[-1].alive


def test_completion_before_rpc_response_and_duplicate_events(make_session):
    h = make_session()
    h._transport.on_start = lambda t, p: t.complete(text="EARLY")
    pending = h.send_prompt("test")
    result = h.wait_turn(pending)
    assert result.outcome == TurnOutcome.COMPLETED
    assert result.response == "EARLY"
    h._transport.complete(text="EARLY")
    assert h.wait_turn(pending) is result
    assert h.turn_count == 1
    assert len(h.transcript_turns()) == 1


def test_rejects_parallel_turns_stale_and_foreign_tokens(make_session):
    h = make_session()
    token = h.send_prompt("first")
    with pytest.raises(ControlError): h.send_prompt("concurrent")
    with pytest.raises(ControlError): h.wait_turn(dataclasses.replace(token))
    h._transport.complete()
    h.wait_turn(token)
    next_token = h.send_prompt("second")
    with pytest.raises(ControlError): h.wait_turn(token)
    h._transport.complete()
    assert h.wait_turn(next_token).turn_index == 2


def test_question_answer_is_exactly_once_and_wait_does_not_finish(make_session):
    h = make_session()
    p = h.send_prompt("ask")
    h._transport.question()
    result = h.wait_turn(p)
    assert result.outcome == TurnOutcome.AWAITING_MENU
    assert h.turn_count == 0
    assert h.peek_state() == SessionState.AWAITING_MENU
    h.answer_menu(2)
    assert h._transport.answers == [(100, {"answers": {"color": {"answers": ["Blue"]}}}, {})]
    h._transport.question(rid=100)  # duplicate request must never be answered twice
    assert h.pending_interaction() is None
    with pytest.raises(ControlError): h.answer_menu(1)
    h._transport.complete()
    assert h.wait_turn(p).outcome == TurnOutcome.COMPLETED


def test_multiple_questions_validation_and_stale_request(make_session):
    h = make_session(); h.send_prompt("ask")
    h._transport.question([{"id": "a", "question": "A"}, {"id": "b", "question": "B"}])
    with pytest.raises(ControlError): h.answer_menu_text("one")
    with pytest.raises(ValueError): h.answer_questions({"a": "only"})
    with pytest.raises(ControlError): h.answer_questions({"a": "one", "b": "two"}, request_id=99)
    h.answer_questions({"a": "free text", "b": ["one", "two"]}, request_id=100)
    assert h._transport.answers[-1][1]["answers"]["b"] == {"answers": ["one", "two"]}


def test_resolved_request_cannot_be_answered(make_session):
    h = make_session(); h.send_prompt("ask"); h._transport.question()
    h._transport.emit("serverRequest/resolved", {"requestId": 100})
    with pytest.raises(ControlError): h.answer_menu(1)


@pytest.mark.parametrize("method", ["item/commandExecution/requestApproval", "item/fileChange/requestApproval"])
@pytest.mark.parametrize("decision", ["accept", "acceptForSession", "decline", "cancel"])
def test_approvals(make_session, method, decision):
    h = make_session(); p = h.send_prompt("do")
    h._transport.emit(method, {"turnId": p.turn_id, "itemId": "item", "availableDecisions": [decision]}, id="approval")
    assert h.wait_turn(p).outcome == TurnOutcome.AWAITING_MENU
    with pytest.raises(ValueError): h.answer_approval("invented")
    h.answer_approval(decision, request_id="approval")
    assert h._transport.answers[-1][:2] == ("approval", {"decision": decision})


def test_unknown_request_is_explicit_and_can_be_interrupted(make_session):
    h = make_session(); p = h.send_prompt("go")
    h._transport.emit("item/future/request", {"turnId": p.turn_id}, id=88)
    result = h.wait_turn(p)
    assert result.outcome == TurnOutcome.UNSUPPORTED
    assert result.pending.request_id == 88
    assert not h._transport.answers
    h.interrupt()
    assert h.wait_turn(p).outcome == TurnOutcome.INTERRUPTED


def test_plan_is_not_completion_and_approval_executes_same_logical_turn(make_session):
    h = make_session(mode="plan")
    p = h.send_prompt("build")
    h._transport.complete(text="A plan", kind="plan")
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.AWAITING_PLAN_APPROVAL
    assert r.pending.plan == "A plan" and h.turn_count == 0
    assert [params for method, params in h._transport.calls if method == "turn/start"][0]["sandboxPolicy"] == {"type": "readOnly"}
    h.approve_plan()
    assert p.turn_id == "turn-2"
    params = [params for method, params in h._transport.calls if method == "turn/start"][-1]
    assert params["collaborationMode"]["mode"] == "default"
    assert params["sandboxPolicy"]["type"] == "dangerFullAccess"
    h._transport.complete(text="Implemented")
    assert h.wait_turn(p).response == "Implemented"
    assert h.turn_count == 1 and len(h.transcript_turns()) == 2


def test_reject_plan_returns_new_pending_token(make_session):
    h = make_session(mode="plan"); p = h.send_prompt("build")
    h._transport.complete(text="plan", kind="plan"); h.wait_turn(p)
    revised = h.reject_plan("Use SQLite")
    with pytest.raises(ControlError): h.wait_turn(p)
    h._transport.complete(text="SQLite plan", kind="plan")
    assert h.wait_turn(revised).pending.plan == "SQLite plan"
    assert h.turn_count == 0
    h.interrupt()
    assert h.wait_turn(revised).outcome == TurnOutcome.INTERRUPTED


def test_model_validation_and_session_scoped_change(make_session):
    h = make_session()
    with pytest.raises(ModelControlError): h.set_model("claude-model")
    with pytest.raises(ModelControlError): h.set_effort("invalid")
    with pytest.raises(UnsupportedOperation): h.set_model("model-b", persist=True)
    s = h.set_model("model-b")
    assert s.requested == "model-b" and s.source == "requested"
    p = h.send_prompt("next")
    with pytest.raises(ControlError): h.set_effort("low")
    h._transport.complete(); h.wait_turn(p)
    assert h.model_state(refresh=True).model == "model-b"
    assert not any(method.startswith("config/") for method, _ in h._transport.calls)


@pytest.mark.parametrize("status,error,expected", [
    ("failed", {"codexErrorInfo": "UsageLimitExceeded"}, TurnOutcome.USAGE_LIMIT),
    ("failed", {"message": "failed"}, TurnOutcome.FAILED),
    ("interrupted", None, TurnOutcome.INTERRUPTED),
])
def test_failure_is_never_success(make_session, status, error, expected):
    h = make_session(); p = h.send_prompt("go")
    h._transport.complete(status=status, error=error)
    assert h.wait_turn(p).outcome == expected


def test_deadline_does_not_allow_new_work_until_interrupt(make_session):
    h = make_session(turn_timeout=0.02)
    p = h.send_prompt("go")
    assert h.wait_turn(p).outcome == TurnOutcome.DEADLINE_EXCEEDED
    with pytest.raises(ControlError): h.send_prompt("unsafe retry")
    assert h.interrupt() is True
    assert h.wait_turn(p).outcome == TurnOutcome.INTERRUPTED
    h.send_prompt("new task")


def test_silent_stall_is_distinct_from_the_deadline(make_session):
    h = make_session(turn_timeout=60.0, stall_seconds=0.02)
    p = h.send_prompt("go")
    assert h.wait_turn(p).outcome == TurnOutcome.STALLED
    with pytest.raises(ControlError): h.send_prompt("unsafe retry")
    assert h.interrupt() is True


def test_disconnect_no_resubmission(make_session):
    h = make_session(); p = h.send_prompt("go")
    h._transport.alive = False
    assert h.wait_turn(p).outcome == TurnOutcome.EOF
    with pytest.raises(ControlError): h.send_prompt("retry")
    assert sum(method == "turn/start" for method, _ in h._transport.calls) == 1


def test_cross_thread_reads_allowed_writes_rejected(make_session):
    h = make_session(); observed = []
    def worker():
        observed.append(h.peek_state())
        try: h.send_prompt("wrong owner")
        except ControlError: observed.append("rejected")
    t = threading.Thread(target=worker); t.start(); t.join()
    assert observed == [SessionState.IDLE, "rejected"]


def test_resume_calls_explicit_thread_id(make_session):
    h = make_session(session_id="saved")
    request = next(p for m, p in h._transport.calls if m == "thread/resume")
    assert request["threadId"] == "saved"
    assert not any(m == "turn/start" for m, _ in h._transport.calls)
    h.stop(); h.stop()
    assert not h.is_alive()


def test_boot_is_readonly_but_each_execution_gets_requested_policy(make_session):
    h = make_session(sandbox_mode="workspace-write", approval_policy="on-request")
    boot = next(p for m, p in h._transport.calls if m == "thread/start")
    assert boot["sandbox"] == "read-only"
    h.send_prompt("build")
    turn = next(p for m, p in h._transport.calls if m == "turn/start")
    assert turn["sandboxPolicy"]["type"] == "workspaceWrite"
    assert turn["approvalPolicy"] == "on-request"


def test_request_ids_may_be_reused_in_a_different_turn(make_session):
    h = make_session(); p = h.send_prompt("first"); h._transport.question(rid=0)
    h.answer_menu(1); h._transport.complete(); h.wait_turn(p)
    p = h.send_prompt("second"); h._transport.question(rid=0)
    assert h.wait_turn(p).pending.request_id == 0
    h.answer_menu(2)
    assert len(h._transport.answers) == 2


def test_terminal_success_survives_server_exit(make_session):
    h = make_session(); p = h.send_prompt("done")
    h._transport.complete(); h._transport.alive = False
    assert h.wait_turn(p).outcome == TurnOutcome.COMPLETED
    assert not h.is_alive()


def test_model_list_uses_shared_rows(make_session):
    from step2step.contracts import ModelRow
    h = make_session()
    rows = h.available_models()
    assert all(isinstance(row, ModelRow) for row in rows)
    assert rows[0].name == "model-a" and rows[0].supported_efforts == ("low", "high")


def test_usage_windows_are_exposed_without_classifying_low_balance_as_failure(make_session):
    h = make_session()
    assert h.health()["usage_reset_text"] == "1234"
    assert not h.usage_limited
    p = h.send_prompt("go")
    h._transport.emit("account/rateLimits/updated", {"rateLimits": {"primary": {"usedPercent": 100, "resetsAt": 4567}}})
    h._transport.complete(error={"codexErrorInfo": "UsageLimitExceeded"}, status="failed")
    r = h.wait_turn(p)
    assert r.outcome == TurnOutcome.USAGE_LIMIT and r.usage_reset_text == "4567"
