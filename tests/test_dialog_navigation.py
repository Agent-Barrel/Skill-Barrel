"""The closed-loop dialog navigation behind answer_menu / approve_plan /
reject_plan, driven against a REAL Runner with a fake pty whose on_write hook
simulates the TUI: arrows move ❯, Enter folds the dialog. The rule under test
is the /model picker's: re-verify before every key, read the highlight back
after every arrow, commit only on a verified target, never a digit, never a
second Enter, and fail closed (ESC + DialogError) on anything else."""
import time

import pytest

from step2step.claude import runner as runner_mod
from step2step.claude import screen as scr
from step2step.claude import transcript as tx
from step2step.claude.runner import DialogError, ENTER, Runner
from step2step.claude.session import SessionHandle, TurnOutcome
from step2step.contracts import ControlError

WORKING = "some output\n✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
QUESTION_LABELS = ["JSON", "YAML", "Type something.", "Chat about this"]
PLAN_LABELS = ["Yes, and bypass permissions", "Yes, manually approve edits",
               "Tell Claude what to change"]


def ask_screen(hl: int) -> str:
    rows = ["Should the config file be JSON or YAML?", ""]
    for i, label in enumerate(QUESTION_LABELS, 1):
        rows.append("%s %d. %s" % ("❯" if i == hl else " ", i, label))
        if i <= 2:
            rows.append("     a one-line description")
        if i == 3:
            rows.append("─" * 40)
    rows += ["", "Enter to select · ↑/↓ to navigate · Esc to cancel"]
    return "\n".join(rows)


def plan_screen(hl: int) -> str:
    rows = ["Claude has written up a plan and is ready to execute. "
            "Would you like to proceed?", ""]
    for i, label in enumerate(PLAN_LABELS, 1):
        rows.append(" %s %d. %s" % ("❯" if i == hl else " ", i, label))
    rows.append("      shift+tab to approve with this feedback")
    return "\n".join(rows)


class FakePty:
    def __init__(self):
        self.alive = True
        self.last_output_ts = time.monotonic() - 5.0
        self.writes = []
        self.on_write = None
        self.write_errors = 0

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


class Sim:
    """Arrow keys move ❯ within [1, n]; Enter replaces the screen."""

    def __init__(self, r, make, n, hl=1, on_enter=WORKING, arrows_work=True):
        self.r, self.make, self.n, self.hl = r, make, n, hl
        self.on_enter, self.arrows_work = on_enter, arrows_work
        self.enters = 0
        r.screen.set(make(hl))
        r.pty.on_write = self.write

    def write(self, s):
        if not self.arrows_work and s in (scr.CURSOR_DOWN, scr.CURSOR_UP):
            return
        if s == scr.CURSOR_DOWN:
            self.hl = min(self.n, self.hl + 1)
        elif s == scr.CURSOR_UP:
            self.hl = max(1, self.hl - 1)
        elif s == ENTER:
            self.enters += 1
            if self.on_enter is not None:
                self.r.screen.set(self.on_enter)
            return
        else:
            return
        self.r.screen.set(self.make(self.hl))


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(runner_mod, "KEY_VERIFY_DELAY", 0.0)
    monkeypatch.setattr(runner_mod, "DIALOG_SETTLE", 0.02)
    monkeypatch.setattr(runner_mod, "INJECT_VERIFY_TIMEOUT", 0.4)
    monkeypatch.setattr(runner_mod, "CONFIRM_WAIT", 0.2)
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)


def _runner(tmp_path, screen=IDLE, stop=0):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude", logger=lambda m: None)
    r.pty = FakePty()
    r.screen = FakeScreen(screen)
    r.watcher = FakeWatcher(stop)
    r.events = None
    return r


def _arrows(writes):
    return [w for w in writes if w in (scr.CURSOR_DOWN, scr.CURSOR_UP)]


# --- question widget ---------------------------------------------------------
def test_arrows_to_the_target_then_one_enter(tmp_path):
    r = _runner(tmp_path)
    sim = Sim(r, ask_screen, 4, hl=1)
    assert r.select_dialog_option("question", 3) is True
    assert _arrows(r.pty.writes) == [scr.CURSOR_DOWN, scr.CURSOR_DOWN]
    assert r.pty.writes.count(ENTER) == 1 and sim.enters == 1
    assert not any(w.isdigit() for w in r.pty.writes)   # never a digit


def test_navigates_upwards_too(tmp_path):
    r = _runner(tmp_path)
    Sim(r, ask_screen, 4, hl=4)
    assert r.select_dialog_option("question", 2) is True
    assert _arrows(r.pty.writes) == [scr.CURSOR_UP, scr.CURSOR_UP]


def test_already_on_the_target_presses_enter_only(tmp_path):
    r = _runner(tmp_path)
    Sim(r, ask_screen, 4, hl=2)
    assert r.select_dialog_option("question", 2) is True
    assert r.pty.writes == [ENTER]


def test_ignored_arrows_fail_closed_without_enter(tmp_path):
    r = _runner(tmp_path)
    Sim(r, ask_screen, 4, hl=1, arrows_work=False)
    with pytest.raises(DialogError) as e:
        r.select_dialog_option("question", 2)
    assert e.value.stage == "nav-ignored"
    assert ENTER not in r.pty.writes
    assert r.pty.writes[-1] == scr.ESCAPE                # folded on the way out
    assert "JSON" in e.value.screen_tail


def test_a_turn_completing_mid_navigation_aborts(tmp_path):
    r = _runner(tmp_path)
    sim = Sim(r, ask_screen, 4, hl=1)
    orig = sim.write

    def write(s):
        orig(s)
        r.watcher.n = 1          # Stop fired under our feet

    r.pty.on_write = write
    with pytest.raises(DialogError) as e:
        r.select_dialog_option("question", 3)
    assert e.value.stage == "stop-raced"
    assert ENTER not in r.pty.writes


def test_a_replaced_dialog_aborts(tmp_path):
    r = _runner(tmp_path)
    sim = Sim(r, ask_screen, 4, hl=1)
    other = ask_screen(1).replace("JSON or YAML", "TOML or INI")

    def write(s):
        r.screen.set(other)      # a different question appeared

    r.pty.on_write = write
    with pytest.raises(DialogError) as e:
        r.select_dialog_option("question", 2)
    assert e.value.stage == "dialog-changed"
    assert ENTER not in r.pty.writes


def test_an_ignored_enter_is_reported_not_repeated(tmp_path):
    r = _runner(tmp_path)
    sim = Sim(r, ask_screen, 4, hl=1, on_enter=None)   # Enter changes nothing
    assert r.select_dialog_option("question", 1) is False
    assert sim.enters == 1


def test_enter_taken_when_the_widget_resolves_via_working(tmp_path):
    r = _runner(tmp_path)
    Sim(r, ask_screen, 4, hl=1, on_enter=WORKING)
    assert r.select_dialog_option("question", 1) is True


def test_no_dialog_is_an_error(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    with pytest.raises(DialogError) as e:
        r.select_dialog_option("question", 1)
    assert e.value.stage == "no-dialog" and r.pty.writes == []


# --- plan approval -------------------------------------------------------------
def test_approve_plan_verifies_option_one_then_enters(tmp_path):
    r = _runner(tmp_path)
    sim = Sim(r, plan_screen, 3, hl=1)
    assert r.approve_plan_menu() is True
    assert r.pty.writes == [ENTER] and sim.enters == 1


def test_approve_plan_refuses_when_option_one_is_not_highlighted(tmp_path):
    r = _runner(tmp_path)
    Sim(r, plan_screen, 3, hl=2)
    with pytest.raises(DialogError) as e:
        r.approve_plan_menu()
    assert e.value.stage == "option-1" and r.pty.writes == []


def test_approve_plan_refuses_a_non_yes_first_row(tmp_path):
    r = _runner(tmp_path)
    Sim(r, lambda hl: plan_screen(hl).replace("Yes, and bypass permissions",
                                              "Abort everything"), 3, hl=1)
    with pytest.raises(DialogError) as e:
        r.approve_plan_menu()
    assert e.value.stage == "option-1" and r.pty.writes == []


def test_approve_plan_reports_a_menu_that_stayed_up(tmp_path):
    r = _runner(tmp_path)
    Sim(r, plan_screen, 3, hl=1, on_enter=None)
    assert r.approve_plan_menu() is False
    assert r.pty.writes == [ENTER]                 # one Enter, never two


def test_reject_plan_walks_to_the_revise_row(tmp_path):
    r = _runner(tmp_path)
    Sim(r, plan_screen, 3, hl=1, on_enter=IDLE)
    assert r.reject_plan_menu() is True
    assert _arrows(r.pty.writes) == [scr.CURSOR_DOWN, scr.CURSOR_DOWN]
    assert r.pty.writes.count(ENTER) == 1


# --- submission confirmation (Runner._confirm_working) -------------------------
def test_confirm_started_by_working(tmp_path):
    r = _runner(tmp_path, screen=WORKING)
    assert r._confirm_working(0) is True and r.pty.writes == []


def test_confirm_resends_enter_once_on_a_plain_idle_screen(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    r.pty.on_write = lambda s: r.screen.set(WORKING) if s == ENTER else None
    assert r._confirm_working(0) is True
    assert r.pty.writes == [ENTER] and r.confirm_reason == "resent"


def test_confirm_never_presses_enter_into_a_dialog(tmp_path):
    # Spec R3: a rendered menu counts as "started"; the usage banner or an
    # unidentified menu blocks the re-send instead of receiving it.
    r = _runner(tmp_path, screen=ask_screen(1))
    assert r._confirm_working(0) is True and r.pty.writes == []
    r = _runner(tmp_path, screen="body\n" * 20 + "You've reached your usage limit · resets at 7pm")
    assert r._confirm_working(0) is False
    assert r.pty.writes == [] and r.confirm_reason == "blocked"


def test_confirm_reports_unconfirmed(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    assert r._confirm_working(0) is False
    assert r.pty.writes == [ENTER] and r.confirm_reason == "unconfirmed"


# --- SessionHandle over the real runner ----------------------------------------
def test_handle_send_prompt_refuses_a_working_session(tmp_path):
    h = SessionHandle(_runner(tmp_path, screen=WORKING))
    with pytest.raises(ControlError):
        h.send_prompt("x")


def test_handle_marks_an_unconfirmed_submission(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    h = SessionHandle(r)
    pt = h.send_prompt("x")
    assert pt.submitted is False and r.confirm_reason == "unconfirmed"
    r.pty.last_output_ts = time.monotonic() - 5.0
    res = h.wait_turn(pt, stall_seconds=0.0)
    assert res.outcome is TurnOutcome.SUBMIT_FAILED and res.response == ""
