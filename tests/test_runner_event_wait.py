"""R1/R2/R4/R5: the result-driven wait loop, interrupt, last-turn capture and
opt-in event hooks — driven by fake pty/watchers and injected screen text."""
import json
import time

from step2step.claude import hooks
from step2step.claude import runner as runner_mod
from step2step.claude import transcript as tx
from step2step.claude.runner import Runner

WORKING = "some output\n✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
MENU = "Which option?\n ❯ 1. Yes, and bypass permissions\n   2. No, keep planning"
# What makes a dialog a dialog is its WORDING, not that it has numbered rows —
# MENU above deliberately has rows but neither dialog's phrasing. Shapes below
# are trimmed from tests/fixtures/screens/.
ASK_MENU = ("Which cache layer?\n"
            " ❯ 1. In-process LRU\n"
            "   2. External store\n"
            "Enter to select · Tab/Arrow keys to navigate · Esc to cancel")
PLAN_MENU = ("Claude has written up a plan and is ready to execute. "
             "Would you like to proceed?\n"
             " ❯ 1. Yes, and bypass permissions\n"
             "   2. Tell Claude what to change")
LIMBO = "neither working, idle, question nor limit"
USAGE = "body\n" * 20 + "You've reached your usage limit · resets at 7pm"

PRE_ASK = (1.0, "PreToolUse", "sid", "AskUserQuestion")
POST_ASK = (2.0, "PostToolUse", "sid", "AskUserQuestion")
PRE_PLAN = (3.0, "PreToolUse", "sid", "ExitPlanMode")
NOTIF = (4.0, "Notification", "sid", "")


class FakePty:
    def __init__(self, alive=True):
        self.alive = alive
        self.last_output_ts = time.monotonic()
        self.writes = []
        self.on_write = None

    def isalive(self):
        return self.alive

    def write(self, s):
        self.writes.append(s)
        if self.on_write:
            self.on_write(s)


class FakeScreen:
    def __init__(self, text=""):
        self._text = text

    def set(self, text):
        self._text = text

    def text(self):
        return self._text

    def tail(self, n=12):
        rows = [r for r in self._text.splitlines() if r.strip()]
        return "\n".join(rows[-n:])


class FakeWatcher:
    def __init__(self, n=0):
        self.n = n

    def count(self):
        return self.n


class FakeEvents:
    def __init__(self, evs=()):
        self._evs = list(evs)

    def events(self):
        return list(self._evs)


def _runner(tmp_path, screen=IDLE, stop=0, alive=True, events=None, idle=0.0,
            **kw):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude",  # explicit => no PATH lookup
               logger=lambda m: None, **kw)
    r.pty = FakePty(alive)
    r.pty.last_output_ts = time.monotonic() - idle
    r.screen = FakeScreen(screen)
    r.watcher = FakeWatcher(stop)
    r.events = FakeEvents(events) if events is not None else None
    return r


# --- R1 step 1-2: eof / completed --------------------------------------------
def test_eof(tmp_path):
    r = _runner(tmp_path, alive=False)
    assert r._wait_turn_event(0, 0)["outcome"] == "eof"


def test_completed_on_stop_signal(tmp_path):
    res = _runner(tmp_path, stop=1)._wait_turn_event(0, 0)
    assert res["outcome"] == "completed"
    assert res["signal_lines"] == 1


# --- R1 step 3: event fast path ----------------------------------------------
def test_awaiting_menu_via_event_fast_path(tmp_path):
    r = _runner(tmp_path, screen=MENU, events=[PRE_ASK])
    res = r._wait_turn_event(0, 0)
    assert res["outcome"] == "awaiting_menu"
    assert res["pending_tool"] == "AskUserQuestion"


def test_awaiting_plan_via_event_fast_path(tmp_path):
    r = _runner(tmp_path, screen=MENU, events=[PRE_PLAN])
    assert r._wait_turn_event(0, 0)["outcome"] == "awaiting_plan_approval"


def test_matched_post_event_clears_fast_path(tmp_path):
    # A resolved Pre+Post pair is no interaction; idle screen -> completed_idle.
    r = _runner(tmp_path, screen=IDLE, events=[PRE_ASK, POST_ASK], idle=1.0)
    assert r._wait_turn_event(0, 0, stall_seconds=0.0)["outcome"] == "completed_idle"


def test_baseline_events_ignores_previous_turns(tmp_path):
    # An interaction event from BEFORE the baseline must not trip this turn.
    r = _runner(tmp_path, screen=IDLE, events=[PRE_ASK], idle=1.0)
    res = r._wait_turn_event(0, baseline_events=1, stall_seconds=0.0)
    assert res["outcome"] == "completed_idle"


def test_notification_event_unknown_dialog(tmp_path):
    r = _runner(tmp_path, screen=MENU, events=[NOTIF])
    assert r._wait_turn_event(0, 0)["outcome"] == "awaiting_unknown_dialog"


# --- R1 step 4: screen fallback (the SCREEN classifies, not the transcript) ---
def test_screen_fallback_ask_needs_no_transcript(tmp_path, monkeypatch):
    # The regression this change exists for. A WAITING AskUserQuestion has no
    # tool_use row in the JSONL at all, so the old transcript cross-check called
    # every real question an unknown dialog — and with the hook missed, nobody
    # ever answered it.
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    r = _runner(tmp_path, screen=ASK_MENU, events=[], idle=3.0)
    res = r._wait_turn_event(0, 0)
    assert res["outcome"] == "awaiting_menu"
    assert res["pending_tool"] == "AskUserQuestion"


def test_screen_fallback_plan_needs_no_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    r = _runner(tmp_path, screen=PLAN_MENU, events=[], idle=3.0)
    res = r._wait_turn_event(0, 0)
    assert res["outcome"] == "awaiting_plan_approval"
    assert res["pending_tool"] == "ExitPlanMode"


def test_menu_shape_without_dialog_wording_is_unknown(tmp_path, monkeypatch):
    # D2 spirit, now enforced by the screen rather than the transcript: rows
    # that carry neither dialog's wording are never a menu we answer, and
    # nothing is typed into the TUI.
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    r = _runner(tmp_path, screen=MENU, events=[], idle=3.0)
    assert r._wait_turn_event(0, 0)["outcome"] == "awaiting_unknown_dialog"
    assert r.pty.writes == []


# --- R1 steps 5-6: usage limit / adaptive tail --------------------------------
def test_usage_limit(tmp_path):
    res = _runner(tmp_path, screen=USAGE)._wait_turn_event(0, 0)
    assert res["outcome"] == "usage_limit"
    assert res["usage_reset"] == "7pm"


def test_completed_idle(tmp_path):
    r = _runner(tmp_path, screen=IDLE, idle=1.0)
    assert r._wait_turn_event(0, 0, stall_seconds=0.0)["outcome"] == "completed_idle"


def test_stalled(tmp_path):
    r = _runner(tmp_path, screen=LIMBO, idle=1.0)
    assert r._wait_turn_event(0, 0, stall_seconds=0.0)["outcome"] == "stalled"


def test_timeout_returns_deadline_exceeded(tmp_path):
    r = _runner(tmp_path, screen=WORKING)
    t0 = time.monotonic()
    assert r._wait_turn_event(0, 0, timeout=0.4)["outcome"] == "deadline_exceeded"
    assert time.monotonic() - t0 < 5.0


def test_timeout_none_is_the_default_budget_not_forever(tmp_path, monkeypatch):
    # Incident 3 of the autonomy record: a caller passed no deadline and a
    # screen that kept repainting held the wait for 5.5 hours. None now means
    # DEFAULT_TURN_TIMEOUT, checked on every tick.
    monkeypatch.setattr(runner_mod, "DEFAULT_TURN_TIMEOUT", 0.3)
    r = _runner(tmp_path, screen=WORKING)
    r.pty.on_write = None
    t0 = time.monotonic()
    res = r._wait_turn_event(0, 0)
    assert res["outcome"] == "deadline_exceeded"
    assert time.monotonic() - t0 < 5.0


def test_deadline_is_checked_even_while_output_keeps_coming(tmp_path):
    # The old check lived inside the keep-waiting branch, which is exactly the
    # branch a repainting screen keeps taking. Keep last_output_ts fresh on
    # every poll and the budget must still end the wait.
    r = _runner(tmp_path, screen=WORKING)
    orig = r.text

    def text():
        r.pty.last_output_ts = time.monotonic()
        return orig()

    r.text = text
    assert r._wait_turn_event(0, 0, timeout=0.3)["outcome"] == "deadline_exceeded"


# --- noisy stagnation: output is not progress ---------------------------------
def test_noisy_stagnation_when_the_progress_sample_stays_flat(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "PROGRESS_POLL", 0.0)
    r = _runner(tmp_path, screen=WORKING)
    r.progress_sample = lambda probe=None: {"transcript_bytes": 1, "probe": probe and probe()}
    res = r._wait_turn_event(0, 0, timeout=5.0, progress_seconds=0.2)
    assert res["outcome"] == "noisy_stagnation"
    assert r.last_progress_ts is not None


def test_changing_progress_sample_keeps_waiting_until_the_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "PROGRESS_POLL", 0.0)
    r = _runner(tmp_path, screen=WORKING)
    counter = {"n": 0}

    def sample(probe=None):
        counter["n"] += 1
        return {"transcript_bytes": counter["n"]}

    r.progress_sample = sample
    res = r._wait_turn_event(0, 0, timeout=0.4, progress_seconds=0.1)
    assert res["outcome"] == "deadline_exceeded"


def test_progress_probe_counts_as_progress(tmp_path, monkeypatch):
    # A harness probe (e.g. a worktree digest) that keeps changing is progress
    # even when the substrate's own counters are flat.
    monkeypatch.setattr(runner_mod, "PROGRESS_POLL", 0.0)
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    r = _runner(tmp_path, screen=WORKING, events=[])
    ticks = iter(range(10_000))
    res = r._wait_turn_event(0, 0, timeout=0.4, progress_seconds=0.1,
                             progress_probe=lambda: next(ticks))
    assert res["outcome"] == "deadline_exceeded"


def test_progress_sample_reads_transcript_events_and_probe(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    p.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    monkeypatch.setattr(tx, "find_transcript", lambda sid: str(p))
    r = _runner(tmp_path, stop=2, events=[PRE_ASK, POST_ASK])
    s = r.progress_sample(lambda: "digest-1")
    assert s["transcript_bytes"] == p.stat().st_size
    assert s["transcript_records"] == 2
    assert s["hook_events"] == 2 and s["stop_count"] == 2
    assert s["probe"] == "digest-1"
    # a broken probe is reported, never raised
    bad = r.progress_sample(lambda: 1 / 0)
    assert bad["probe"].startswith("probe-error:")


# --- the batch-path loops are bounded too ------------------------------------
def test_wait_for_signal_has_a_finite_budget(tmp_path):
    r = _runner(tmp_path, screen=WORKING)
    assert r._wait_for_signal(0, timeout=0.3) == "stall"


def test_wait_plan_ready_has_a_finite_budget(tmp_path):
    r = _runner(tmp_path, screen=WORKING)
    assert r._wait_plan_ready(0, timeout=0.3) == "stall"


# --- R2: interrupt -----------------------------------------------------------
def test_interrupt_noop_when_idle(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    assert r.interrupt() is True
    assert r.pty.writes == []


def test_interrupt_true_when_dead(tmp_path):
    r = _runner(tmp_path, screen=WORKING, alive=False)
    assert r.interrupt() is True
    assert r.pty.writes == []


def test_interrupt_presses_esc_until_settled(tmp_path):
    r = _runner(tmp_path, screen=WORKING)
    r.pty.on_write = lambda s: r.screen.set(IDLE)
    assert r.interrupt() is True
    assert "\x1b" in r.pty.writes


def test_interrupt_folds_a_waiting_question(tmp_path):
    # A waiting widget is not "working" — its footer says "Esc to cancel", not
    # "esc to interrupt" — so a working-only test sent no ESC at all and the
    # caller went on typing into a menu that was still eating keys.
    r = _runner(tmp_path, screen=ASK_MENU)
    r.pty.on_write = lambda s: r.screen.set(IDLE)
    assert r.interrupt() is True
    assert r.pty.writes == ["\x1b"]


def test_interrupt_folds_a_waiting_plan_approval(tmp_path):
    r = _runner(tmp_path, screen=PLAN_MENU)
    r.pty.on_write = lambda s: r.screen.set(IDLE)
    assert r.interrupt() is True
    assert r.pty.writes == ["\x1b"]


def test_interrupt_leaves_an_unidentified_numbered_list_alone(tmp_path):
    # "unknown" is usually just a numbered list in a finished response; pressing
    # ESC at it for the whole timeout would slow every stall down for nothing.
    r = _runner(tmp_path, screen=MENU)
    assert r.interrupt() is True
    assert r.pty.writes == []


# --- R4: _capture_response(idx=None) -----------------------------------------
def _fake_transcript(tmp_path, monkeypatch):
    events = [
        {"type": "user", "message": {"content": "p1"}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "r1"}]}},
        {"type": "user", "message": {"content": "p2"}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "r2"},
            {"type": "tool_use", "name": "Write", "id": "t", "input": {}}]}},
    ]
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    monkeypatch.setattr(tx, "find_transcript", lambda sid: str(p))


def test_capture_response_last_turn(tmp_path, monkeypatch):
    _fake_transcript(tmp_path, monkeypatch)
    cap = _runner(tmp_path)._capture_response(None)
    assert cap["response"] == "r2"
    assert cap["tools"] == ["Write"]


def test_capture_response_by_index_unchanged(tmp_path, monkeypatch):
    _fake_transcript(tmp_path, monkeypatch)
    r = _runner(tmp_path)
    assert r._capture_response(1)["response"] == "r1"
    assert r._capture_response(2)["response"] == "r2"


def test_capture_response_screen_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    cap = _runner(tmp_path, screen=IDLE)._capture_response(None)
    assert cap["tools"] == []
    assert "shift+tab" in cap["response"]


# --- R5: event_hooks opt-in --------------------------------------------------
def test_prepare_default_settings_byte_identical(tmp_path):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude", logger=lambda m: None)
    r._prepare()
    expected = hooks.build_settings(
        r.python_exe, r.runtime / "signal_hook.py", r.signal_file,
        form=r.hook_form)
    assert r.settings_file.read_text(encoding="utf-8") == json.dumps(
        expected, indent=2)
    assert r.events is None


def test_prepare_event_hooks_registers_events(tmp_path):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude", logger=lambda m: None,
               event_hooks=True)
    r._prepare()
    cfg = json.loads(r.settings_file.read_text(encoding="utf-8"))
    assert list(cfg["hooks"].keys()) == [
        "Stop", "PreToolUse", "PostToolUse", "Notification", "PreCompact",
        "SessionEnd"]
    assert isinstance(r.events, hooks.EventWatcher)
    ev_path = r.runtime / ("run-%s.events" % r.session_id)
    assert r.events.path == ev_path
    assert ev_path.exists() and r.events.count() == 0
