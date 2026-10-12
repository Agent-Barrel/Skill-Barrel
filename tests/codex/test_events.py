from step2step.codex.events import EventState


def event(method, **params):
    return {"method": method, "params": {"threadId": "ours", "turnId": "t", **params}}


def test_foreign_thread_and_late_events_cannot_corrupt_completed_response():
    s = EventState("ours")
    s.apply(event("item/agentMessage/delta", itemId="a", delta="partial"))
    s.apply(event("item/completed", item={"id": "a", "type": "agentMessage", "text": "canonical"}))
    s.apply(event("item/agentMessage/delta", itemId="a", delta="duplicate"))
    s.apply(event("turn/completed", turn={"id": "t", "status": "completed", "items": []}))
    s.apply(event("item/agentMessage/delta", itemId="a", delta="late"))
    s.apply(event("item/completed", threadId="foreign", item={"id": "a", "type": "agentMessage", "text": "wrong"}))
    assert s.transcript()[0]["response"] == "canonical"
    assert s.turn("t").status == "completed"


def test_final_plan_replaces_deltas():
    s = EventState("ours")
    s.apply(event("item/plan/delta", itemId="p", delta="tentative"))
    s.apply(event("item/completed", item={"id": "p", "type": "plan", "text": "final plan"}))
    assert s.transcript()[0]["plan"] == "final plan"


def test_completed_turn_discards_unanswered_requests():
    s = EventState("ours")
    s.apply({**event("item/tool/requestUserInput", questions=[{"id": "q"}]), "id": 8})
    assert s.pending("t").request_id == 8
    s.apply(event("turn/completed", turn={"id": "t", "status": "interrupted", "items": []}))
    assert s.pending("t") is None
    s.apply({**event("item/tool/requestUserInput", questions=[{"id": "q"}]), "id": 8})
    assert s.pending("t") is None


def test_heartbeat_does_not_reset_progress_clock():
    s = EventState("ours")
    s.turn("t").last_progress = 1
    s.apply(event("thread/status/changed", status={"type": "active"}))
    assert s.turn("t").last_progress == 1
    s.apply(event("item/commandExecution/outputDelta", itemId="cmd", delta="progress"))
    assert s.turn("t").last_progress > 1


def test_response_is_final_answer_with_commentary_preserved_separately():
    s = EventState("ours")
    s.apply(event("item/completed", item={"id": "progress", "type": "agentMessage", "phase": "commentary", "text": "Working..."}))
    s.apply(event("item/completed", item={"id": "answer", "type": "agentMessage", "phase": "final_answer", "text": "FINAL"}))
    s.apply(event("turn/completed", turn={"id": "t", "status": "completed", "items": []}))
    assert s.transcript()[0]["response"] == "FINAL"
    assert s.transcript()[0]["commentary"] == "Working..."


def test_failure_without_repeated_error_retains_prior_error_notification():
    s = EventState("ours")
    s.apply(event("error", error={"codexErrorInfo": "UsageLimitExceeded"}, willRetry=False))
    s.apply(event("turn/completed", turn={"id": "t", "status": "failed", "error": None, "items": []}))
    assert s.turn("t").error == {"codexErrorInfo": "UsageLimitExceeded"}
