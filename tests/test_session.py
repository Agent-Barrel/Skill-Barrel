"""SessionHandle over a fake Runner: start boot sequence, the COMPLETED and
AWAITING_MENU turn flows (non-consuming), stubs, health and snapshot."""
import json
import pathlib
import time

import pytest

from step2step.claude import session
from step2step.claude import transcript as tx
from step2step.claude.runner import DialogError
from step2step.claude.session import (
    MenuOption,
    PendingTurn,
    SessionHandle,
    SessionState,
    TurnOutcome,
)
from step2step.contracts import ControlError, UnsupportedOperation

IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
WORKING = "✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
MENU = "Which option?\n ❯ 1. Yes, and bypass permissions\n   2. No, keep planning"
# A real AskUserQuestion widget: rows PLUS the footer that identifies it. The
# transcript stays empty while it waits, so this is all a caller ever gets.
ASK_MENU = ("Which cache layer?\n"
            " ❯ 1. In-process LRU\n"
            "     Fastest p99.\n"
            "   2. External store\n"
            "Enter to select · Tab/Arrow keys to navigate · Esc to cancel")


class FakePty:
    def __init__(self):
        self.alive = True
        self.writes = []
        self.write_errors = 0
        self.terminated = False

    def isalive(self):
        return self.alive

    def write(self, s):
        self.writes.append(s)

    def terminate(self):
        self.terminated = True
        self.alive = False


class FakeScreen:
    def __init__(self, text=IDLE):
        self._text = text

    def set(self, text):
        self._text = text

    def text(self):
        return self._text

    def tail(self, n=12):
        rows = [r for r in self._text.splitlines() if r.strip()]
        return "\n".join(rows[-n:])


class FakeEvents:
    def count(self, event=None, tool=None):
        return 0


class FakeRunner:
    mode = "bypass"
    session_id = "fake-sid"
    workdir = pathlib.Path("wd")
    app_dir = pathlib.Path("app")
    claude_exe = "dummy-claude"
    extra_args = ()

    def __init__(self):
        self.pty = FakePty()
        self.screen = FakeScreen()
        self.events = FakeEvents()
        self.calls = []
        self.wait_result = {"outcome": "completed", "pending_tool": None,
                            "usage_reset": None, "signal_lines": 1}
        self.pending = None  # what _pending_transcript_tool returns
        self.confirm_result = True      # what _confirm_working reports
        self.confirm_reason = None
        self.dialog_result = True       # what the dialog commits report
        self.input_idle = True

    def log(self, msg):
        self.calls.append(("log", msg))

    def _ensure_mode(self, target):
        self.calls.append(("ensure_mode", target))
        return True

    def _send_prompt(self, idx, text):
        self.calls.append(("send", text))
        return 3  # pre-submit stop baseline

    def _confirm_working(self, baseline, baseline_events=None):
        self.calls.append(("confirm", baseline, baseline_events))
        return self.confirm_result

    # dialog commits (the real loops live in the Runner; see
    # tests/test_dialog_navigation.py)
    def _dialog_baseline(self, kind):
        return {"kind": kind}

    def select_dialog_option(self, kind, index):
        self.calls.append(("select", kind, index))
        return self.dialog_result

    def approve_plan_menu(self):
        self.calls.append(("approve",))
        return self.dialog_result

    def reject_plan_menu(self):
        self.calls.append(("reject",))
        return self.dialog_result

    def wait_input_idle(self, timeout=None):
        return self.input_idle

    def _confirm_dialog_gone(self, kind, base):
        return self.dialog_result

    def _wait_turn_event(self, baseline_stop, baseline_events, *,
                         timeout=None, stall_seconds=None, **kw):
        self.calls.append(("wait", baseline_stop, baseline_events))
        self.wait_kwargs = {"timeout": timeout, "stall_seconds": stall_seconds, **kw}
        return dict(self.wait_result)

    def _wait_settled(self):
        pass

    def _capture_response(self, idx=None):
        return {"response": "the response", "tools": ["Write"]}

    def _pending_transcript_tool(self):
        return self.pending

    def _finalize(self):
        self.calls.append(("finalize",))

    def interrupt(self, timeout=15.0):
        self.calls.append(("interrupt",))
        return True

    def text(self):
        return self.screen.text()

    def idle_for(self):
        return 0.5


@pytest.fixture
def no_transcript(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)


def _handle(**kw):
    return SessionHandle(FakeRunner(), **kw)


# --- start() ------------------------------------------------------------------
def test_start_composes_args_and_boots(monkeypatch, tmp_path, no_transcript):
    created = {}

    class BootRunner(FakeRunner):
        def __init__(self, **kw):
            super().__init__()
            created.update(kw)

        def preflight(self):
            self.calls.append(("preflight",))
            return {"fatal": [], "warnings": ["low disk (test)"]}

        def _prepare(self):
            self.calls.append(("prepare",))

        def _spawn(self):
            self.calls.append(("spawn",))

        def _handle_trust(self):
            self.calls.append(("trust",))

        def _wait_initial_idle(self):
            self.calls.append(("idle",))

    monkeypatch.setattr(session, "Runner", BootRunner)
    h = SessionHandle.start(workdir=tmp_path, model="haiku",
                            system_prompt_append="be brief", mode="plan",
                            claude_exe="dummy-claude", role="builder",
                            turn_timeout=99)
    assert h.turn_timeout == 99
    assert created["event_hooks"] is True
    assert created["prompts"] == []
    assert created["mode"] == "plan"
    ea = created["extra_args"]
    assert ea[ea.index("--append-system-prompt") + 1] == "be brief"
    assert ea[ea.index("--model") + 1] == "haiku"
    assert [c[0] for c in h._runner.calls if c[0] != "log"] == [
        "preflight", "prepare", "spawn", "trust", "idle"]
    assert h.role == "builder"
    assert h.system_prompt_append == "be brief"
    assert any(c[0] == "log" and "low disk" in c[1] for c in h._runner.calls)


def test_start_refuses_a_fatal_preflight(monkeypatch, tmp_path, no_transcript):
    class NoClaude(FakeRunner):
        def __init__(self, **kw):
            super().__init__()

        def preflight(self):
            return {"fatal": ["claude executable not found: x"], "warnings": []}

        def _prepare(self):
            raise AssertionError("must not spawn after a fatal preflight")

    monkeypatch.setattr(session, "Runner", NoClaude)
    with pytest.raises(ControlError, match="refused"):
        SessionHandle.start(workdir=tmp_path, claude_exe="x")


def test_from_snapshot_relaunches_with_the_same_launch_spec(monkeypatch, tmp_path,
                                                            no_transcript):
    created = {}

    class BootRunner(FakeRunner):
        def __init__(self, **kw):
            super().__init__()
            created.update(kw)

        def preflight(self):
            return {"fatal": [], "warnings": []}

        def _prepare(self):
            pass

        def _spawn(self):
            pass

        def _handle_trust(self):
            pass

        def _wait_initial_idle(self):
            pass

    monkeypatch.setattr(session, "Runner", BootRunner)
    snap = {
        "session_id": "old-sid", "workdir": str(tmp_path), "mode": "plan",
        "role": "builder", "model": "haiku", "effort": "low",
        "extra_args": ["--append-system-prompt", "be brief", "--model", "haiku",
                       "--effort", "low", "--verbose"],
        "claude_exe": "dummy-claude", "app_dir": str(tmp_path / "app"),
        "system_prompt_append": "be brief", "turn_timeout": 123.0,
        "snapshot_dir": str(tmp_path / "snaps"),
    }
    path = tmp_path / "session-old-sid.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    h = SessionHandle.from_snapshot(path)
    ea = created["extra_args"]
    assert ea.count("--model") == 1 and ea.count("--effort") == 1
    assert ea.count("--append-system-prompt") == 1 and "--verbose" in ea
    assert ea[ea.index("--model") + 1] == "haiku"
    assert created["mode"] == "plan" and created["claude_exe"] == "dummy-claude"
    assert h.role == "builder" and h.turn_timeout == 123.0
    assert h.snapshot_dir == tmp_path / "snaps"
    assert h.session_id == "fake-sid"          # a FRESH session, never the old id


def test_snapshot_is_rewritten_after_turns_and_stop(tmp_path, no_transcript):
    h = SessionHandle(FakeRunner(), snapshot_dir=tmp_path)
    h.run_turn("x")
    on_disk = json.loads((tmp_path / "session-fake-sid.json").read_text(encoding="utf-8"))
    assert on_disk["turn_count"] == 1 and on_disk["last_outcome"] == "completed"
    assert on_disk["stopped_at"] is None
    h.stop()
    on_disk = json.loads((tmp_path / "session-fake-sid.json").read_text(encoding="utf-8"))
    assert on_disk["stopped_at"] is not None


# --- send_prompt / wait_turn / run_turn ---------------------------------------
def test_send_prompt_returns_baselines(no_transcript):
    h = _handle()
    before = time.time()
    pt = h.send_prompt("do x")
    assert isinstance(pt, PendingTurn)
    assert pt.baseline_stop == 3       # FakeRunner._send_prompt's return
    assert pt.baseline_events == 0
    assert pt.prompt == "do x"
    assert pt.submitted_at >= before
    # bypass mode never touches shift+tab
    assert ("ensure_mode", "plan") not in h._runner.calls


def test_wait_turn_uses_the_handle_budget_by_default(no_transcript):
    # timeout=None is the handle's finite turn_timeout, never "forever".
    h = _handle(turn_timeout=42)
    h.run_turn("x")
    assert h._runner.wait_kwargs["timeout"] == 42
    h.run_turn("y", timeout=5)
    assert h._runner.wait_kwargs["timeout"] == 5
    h.run_turn("z", progress_seconds=7, progress_probe=len)
    assert h._runner.wait_kwargs["progress_seconds"] == 7
    assert h._runner.wait_kwargs["progress_probe"] is len


def test_turn_timeout_must_be_positive():
    with pytest.raises(ValueError):
        _handle(turn_timeout=0)
    with pytest.raises(ValueError):
        _handle(turn_timeout=None)


def test_plan_mode_reenters_per_prompt(no_transcript):
    h = _handle()
    h._runner.mode = "plan"
    h.send_prompt("plan me")
    assert ("ensure_mode", "plan") in h._runner.calls


def test_run_turn_completed(no_transcript):
    h = _handle()
    res = h.run_turn("do x")
    assert res.outcome is TurnOutcome.COMPLETED
    assert res.response == "the response"
    assert res.tools == ["Write"]
    assert res.turn_index == 1 and h.turn_count == 1
    assert res.pending is None
    assert res.signal_lines == 1
    assert res.raw["outcome"] == "completed"
    assert res.ended_at >= res.started_at
    # the wait consumed the baselines captured at submit
    assert ("wait", 3, 0) in h._runner.calls


def test_turn_index_follows_transcript(monkeypatch):
    # turn_index derives from the live transcript when it exists.
    monkeypatch.setattr(tx, "find_transcript", lambda sid: "t.jsonl")
    monkeypatch.setattr(tx, "parse_transcript",
                        lambda p: [{"index": 1}, {"index": 2}])
    h = _handle()
    assert h.run_turn("x").turn_index == 2
    assert h.turn_count == 2


def test_awaiting_menu_does_not_consume_turn(no_transcript):
    h = _handle()
    h._runner.screen.set(MENU)
    h._runner.wait_result = {"outcome": "awaiting_menu",
                             "pending_tool": "AskUserQuestion",
                             "usage_reset": None, "signal_lines": 0}
    h._runner.pending = {"name": "AskUserQuestion", "id": "tu_1",
                         "input": {"questions": [{"question": "Which?"}]}}
    pt = h.send_prompt("ask me")
    res = h.wait_turn(pt)
    assert res.outcome is TurnOutcome.AWAITING_MENU
    assert h.turn_count == 0           # not consumed
    p = res.pending
    assert p.kind == "ask_user_question"
    assert p.tool_use_id == "tu_1"
    assert p.questions == [{"question": "Which?"}]
    assert [(o.index, o.highlighted) for o in p.menu] == [(1, True), (2, False)]
    assert "Which option?" in p.screen_tail
    # after answering, the SAME PendingTurn finishes the turn
    h._runner.wait_result = {"outcome": "completed", "pending_tool": None,
                             "usage_reset": None, "signal_lines": 1}
    res2 = h.wait_turn(pt)
    assert res2.outcome is TurnOutcome.COMPLETED
    assert h.turn_count == 1


def test_awaiting_plan_pending_carries_plan(no_transcript):
    h = _handle()
    h._runner.screen.set(MENU)
    h._runner.wait_result = {"outcome": "awaiting_plan_approval",
                             "pending_tool": "ExitPlanMode",
                             "usage_reset": None, "signal_lines": 0}
    h._runner.pending = {"name": "ExitPlanMode", "id": "tu_2",
                         "input": {"plan": "1. build it"}}
    res = h.wait_turn(h.send_prompt("plan it"))
    assert res.outcome is TurnOutcome.AWAITING_PLAN_APPROVAL
    assert res.pending.kind == "plan_approval"
    assert res.pending.plan == "1. build it"


def test_usage_limit_sets_flag(no_transcript):
    h = _handle()
    h._runner.wait_result = {"outcome": "usage_limit", "pending_tool": None,
                             "usage_reset": "7pm", "signal_lines": 0}
    res = h.wait_turn(h.send_prompt("x"))
    assert res.outcome is TurnOutcome.USAGE_LIMIT
    assert res.usage_reset_text == "7pm"
    assert h.usage_limited is True
    assert h.health()["usage_limited"] is True


# --- submission confirmation --------------------------------------------------
def test_send_prompt_confirms_the_turn_started(no_transcript):
    h = _handle()
    pt = h.send_prompt("do x")
    assert ("confirm", 3, 0) in h._runner.calls
    assert pt.submitted is True and pt.baseline_turns == 0
    assert pt.transcript_seen is False


def test_unconfirmed_idle_turn_is_submit_failed_not_the_old_response(no_transcript):
    # The autonomy record's top structural defect: a swallowed paste leaves the
    # screen idle, and completed_idle used to hand back the PREVIOUS turn.
    h = _handle()
    h._runner.confirm_result = False
    h._runner.wait_result = {"outcome": "completed_idle", "pending_tool": None,
                             "usage_reset": None, "signal_lines": 0}
    res = h.run_turn("do x")
    assert res.outcome is TurnOutcome.SUBMIT_FAILED
    assert res.response == "" and res.tools == []
    assert h.turn_count == 0


def test_confirmed_idle_turn_without_any_transcript_is_accepted(no_transcript):
    # No JSONL to consult (none before, none after): trust the confirmation.
    h = _handle()
    h._runner.wait_result = {"outcome": "completed_idle", "pending_tool": None,
                             "usage_reset": None, "signal_lines": 0}
    res = h.run_turn("do x")
    assert res.outcome is TurnOutcome.COMPLETED_IDLE
    assert res.response == "the response"


def test_idle_turn_is_real_when_the_transcript_grew(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: "t.jsonl")
    turns = [[{"index": 1, "prompt": "old"}]]
    monkeypatch.setattr(tx, "parse_transcript", lambda p: list(turns[0]))
    h = _handle()
    h._runner.confirm_result = False          # confirmation missed, but…
    h._runner.wait_result = {"outcome": "completed_idle", "pending_tool": None,
                             "usage_reset": None, "signal_lines": 0}
    pt = h.send_prompt("new")
    assert pt.baseline_turns == 1 and pt.transcript_seen is True
    turns[0] = [{"index": 1, "prompt": "old"}, {"index": 2, "prompt": "new"}]
    res = h.wait_turn(pt)                      # …the transcript grew: real turn
    assert res.outcome is TurnOutcome.COMPLETED_IDLE and res.turn_index == 2


def test_idle_turn_with_a_flat_transcript_is_submit_failed(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: "t.jsonl")
    monkeypatch.setattr(tx, "parse_transcript",
                        lambda p: [{"index": 1, "prompt": "old"}])
    h = _handle()
    h._runner.wait_result = {"outcome": "completed_idle", "pending_tool": None,
                             "usage_reset": None, "signal_lines": 0}
    assert h.run_turn("new").outcome is TurnOutcome.SUBMIT_FAILED


def test_completed_with_stop_signal_never_second_guesses(no_transcript):
    h = _handle()
    h._runner.confirm_result = False
    assert h.run_turn("x").outcome is TurnOutcome.COMPLETED


def test_send_prompt_refuses_a_working_session(no_transcript):
    h = _handle()
    h._runner.screen.set(WORKING)
    with pytest.raises(ControlError):
        h.send_prompt("x")
    assert ("send", "x") not in h._runner.calls


def test_send_prompt_refuses_a_waiting_question(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    with pytest.raises(ControlError):
        h.send_prompt("x")


def test_send_prompt_allows_an_unidentified_numbered_list(no_transcript):
    # A numbered list in a finished response is not a dialog we refuse to
    # type over; a swallowed paste is caught by the confirmation instead.
    h = _handle()
    h._runner.screen.set(MENU)
    h.send_prompt("x")
    assert ("send", "x") in h._runner.calls


# --- interactions -------------------------------------------------------------
def test_approve_plan_is_the_verified_runner_path(no_transcript):
    h = _handle()
    assert h.approve_plan() is True
    assert ("approve",) in h._runner.calls
    h._runner.dialog_result = False
    assert h.approve_plan() is False        # an Enter that did not take is reported


def test_interrupt_returns_the_runner_verdict(no_transcript):
    h = _handle()
    assert h.interrupt() is True
    assert ("interrupt",) in h._runner.calls


def test_answering_needs_a_waiting_question(no_transcript):
    h = _handle()
    with pytest.raises(ControlError):
        h.answer_menu(1)
    with pytest.raises(ControlError):
        h.answer_menu_text("free text")
    with pytest.raises(ControlError):
        h.answer_questions({"q": "JSON"})
    assert not any(c[0] == "select" for c in h._runner.calls)


def test_answer_menu_selects_a_printed_option(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    h.answer_menu(2)
    assert ("select", "question", 2) in h._runner.calls
    with pytest.raises(ValueError):
        h.answer_menu(9)


def test_answer_menu_reports_an_ignored_enter(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    h._runner.dialog_result = False
    with pytest.raises(DialogError) as e:
        h.answer_menu(1)
    assert e.value.stage == "commit-ignored"
    assert "\x1b" in h._runner.pty.writes       # folded, never a second Enter


ASK_MENU_FREE = ("Which cache layer?\n"
                 " ❯ 1. In-process LRU\n"
                 "   2. External store\n"
                 "   3. Type something.\n"
                 "   4. Chat about this\n"
                 "Enter to select · ↑/↓ to navigate · Esc to cancel")


def test_answer_menu_text_uses_the_free_text_row(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU_FREE)
    h.answer_menu_text("neither, use redis")
    assert ("select", "question", 3) in h._runner.calls
    assert ("send", "neither, use redis") in h._runner.calls


def test_answer_menu_text_needs_a_free_text_row(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    with pytest.raises(ControlError):
        h.answer_menu_text("x")


def test_answer_questions_matches_labels_else_types(no_transcript):
    h = _handle()
    h._runner.screen.set(ASK_MENU_FREE)
    h.answer_questions({"q": "external store"})
    assert ("select", "question", 2) in h._runner.calls
    h.answer_questions({"q": ["something else"]})
    assert ("select", "question", 3) in h._runner.calls
    with pytest.raises(ValueError):
        h.answer_questions({"a": "x", "b": "y"})


ASK_TABS = ("←  ☐ 캐시 계층  ☐ 재시도 정책  ✔ Submit  →\n"
            "Which cache layer?\n"
            " ❯ 1. In-process LRU\n"
            "   2. External store\n"
            "   3. Type something.\n"
            "Enter to select · Tab/Arrow keys to navigate · Esc to cancel")


def test_multi_question_widgets_are_explicitly_unsupported(no_transcript):
    # The Submit tab shows ✔ even before anything is answered, so nothing on
    # screen says when it has focus -- a verified loop cannot be built yet.
    h = _handle()
    h._runner.screen.set(ASK_TABS)
    with pytest.raises(UnsupportedOperation):
        h.answer_questions({"q": "External store"})


def test_reject_plan_returns_a_new_pending_turn(no_transcript):
    h = _handle()
    pt = h.reject_plan("use sqlite")
    assert ("reject",) in h._runner.calls
    assert isinstance(pt, PendingTurn) and pt.prompt == "use sqlite"
    with pytest.raises(ValueError):
        h.reject_plan("   ")


def test_pending_interaction_unknown_dialog(no_transcript):
    # Rows carrying neither dialog's wording read as an unknown dialog.
    h = _handle()
    h._runner.screen.set(MENU)
    p = h.pending_interaction()
    assert p.kind == "unknown_dialog"
    assert p.tool_use_id is None and p.questions == [] and p.plan is None
    assert len(p.menu) == 2


def test_pending_interaction_reads_the_question_off_the_screen(no_transcript):
    # With no transcript row (the normal case while a question waits) the
    # content still has to arrive, or a harness escalates "내용 불명" to a human.
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    p = h.pending_interaction()
    assert p.kind == "ask_user_question"
    assert p.source == "screen"
    one = p.questions[0]
    assert one["question"] == "Which cache layer?"
    assert [o["label"] for o in one["options"]] == ["In-process LRU",
                                                    "External store"]
    assert one["options"][0]["description"] == "Fastest p99."


def test_transcript_content_wins_once_it_exists(no_transcript):
    # Verbatim tool input beats a scrape — it just is not available in time.
    h = _handle()
    h._runner.screen.set(ASK_MENU)
    h._runner.pending = {"name": "AskUserQuestion", "id": "t",
                         "input": {"questions": [{"question": "verbatim?"}]}}
    p = h.pending_interaction()
    assert p.source == "transcript"
    assert p.questions == [{"question": "verbatim?"}]
    assert p.tool_use_id == "t"


def test_pending_interaction_none_when_quiet(no_transcript):
    assert _handle().pending_interaction() is None


# --- state / health / stop / snapshot ----------------------------------------
def test_peek_state_variants(no_transcript):
    h = _handle()
    assert h.peek_state() is SessionState.IDLE
    h._runner.screen.set(WORKING)
    assert h.peek_state() is SessionState.WORKING
    h._runner.screen.set(MENU)
    assert h.peek_state() is SessionState.AWAITING_UNKNOWN_DIALOG
    # Classified off the screen: no transcript row exists while it waits.
    h._runner.screen.set(ASK_MENU)
    assert h.peek_state() is SessionState.AWAITING_MENU
    h._runner.pty.alive = False
    assert h.peek_state() is SessionState.DEAD


def test_health_shape(no_transcript):
    got = _handle().health()
    assert set(got) == {"alive", "state", "idle_for", "mode", "write_errors",
                        "turn_count", "usage_limited", "no_progress_for"}
    assert got["no_progress_for"] is None       # no wait has sampled progress yet
    assert got["alive"] is True
    assert got["state"] == "idle"
    assert got["idle_for"] == 0.5
    assert got["write_errors"] == 0
    assert got["turn_count"] == 0


def test_stop_finalizes(no_transcript):
    h = _handle()
    h.stop()
    assert ("finalize",) in h._runner.calls
    assert h._runner.pty.terminated is False


def test_stop_force_terminates_first(no_transcript):
    h = _handle()
    h.stop(force=True)
    assert h._runner.pty.terminated is True
    assert ("finalize",) in h._runner.calls


def test_snapshot_dict_and_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: "t.jsonl")
    h = SessionHandle(FakeRunner(), role="builder", model="haiku",
                      snapshot_dir=tmp_path)
    snap = h.snapshot()
    assert snap["session_id"] == "fake-sid"
    assert snap["mode"] == "bypass"
    assert snap["role"] == "builder" and snap["model"] == "haiku"
    assert snap["transcript"] == "t.jsonl"
    assert snap["turn_count"] == 0
    on_disk = json.loads((tmp_path / "session-fake-sid.json")
                         .read_text(encoding="utf-8"))
    assert on_disk == snap


# --- exports ------------------------------------------------------------------
def test_claude_exports():
    import step2step.claude as s2s

    for name in ("SessionHandle", "SessionState", "TurnOutcome", "MenuOption",
                 "PendingInteraction", "PendingTurn", "TurnResult"):
        assert hasattr(s2s, name), name
    assert s2s.MenuOption is MenuOption
