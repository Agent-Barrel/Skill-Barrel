"""Fixed prompt batches over the incremental Codex session API."""
import sys
from ..contracts import TurnOutcome
from .session import SessionHandle


def run_session(prompts, workdir, *, mode="bypass", on_stall="abort", on_turn=None,
                interaction_handler=None, **kwargs):
    """Plan batches auto-approve plans; questions/permissions need a handler.

    interaction_handler(handle, interaction) must answer the supplied interaction
    through the handle, or return False to abort. No approval is guessed.
    `pause` aborts the batch for caller intervention; interactive takeover should
    use SessionHandle, which keeps a pending turn alive instead of closing it.
    """
    if on_stall not in ("abort", "skip", "pause"):
        raise ValueError("on_stall must be abort, skip, or pause")
    if mode not in ("bypass", "plan"):
        raise ValueError("mode must be bypass or plan")
    prompts = list(prompts)
    if any(not isinstance(p, str) or not p.strip() for p in prompts):
        raise ValueError("prompts must contain nonempty strings")
    summary = {"completed": 0, "total": len(prompts), "aborted": False,
               "abort_reason": None, "mode": mode, "results": [], "provider": "codex",
               "workdir": str(workdir)}
    if not prompts:
        return summary
    handle = SessionHandle.start(workdir=workdir, mode=mode, **kwargs)
    try:
        summary["session_id"] = handle.session_id
        for i, prompt in enumerate(prompts, 1):
            pending = handle.send_prompt(prompt)
            while True:
                result = handle.wait_turn(pending)
                if result.outcome is TurnOutcome.AWAITING_PLAN_APPROVAL:
                    handle.approve_plan()
                    continue
                if result.outcome is TurnOutcome.AWAITING_MENU and interaction_handler:
                    before = result.pending.request_id
                    if interaction_handler(handle, result.pending) is not False:
                        after = handle.pending_interaction()
                        if after is None or after.request_id != before:
                            continue
                break
            record = {"index": i, "status": result.outcome.value,
                      "response": result.response, "tools": result.tools,
                      "signal_lines": [], "raw": result.raw}
            summary["results"].append(record)
            if result.outcome is TurnOutcome.COMPLETED:
                summary["completed"] += 1
            elif (result.outcome in (TurnOutcome.STALLED, TurnOutcome.DEADLINE_EXCEEDED)
                  and on_stall == "skip"):
                handle.interrupt()  # Never send a new prompt over unfinished work.
            else:
                summary["aborted"] = True
                summary["abort_reason"] = result.outcome.value
            if on_turn:
                on_turn(record)
            if summary["aborted"]:
                break
    finally:
        handle.stop(force=sys.exc_info()[0] is not None)
        summary["transcript"] = str(handle.run_dir / "transcript.json")
    return summary
