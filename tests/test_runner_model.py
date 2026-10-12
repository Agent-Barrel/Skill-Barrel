"""Closed-loop /model driving over a fake pty + scripted screen.

The invariant every test here exists to protect: **no key that can commit is
ever written on a path that fails verification**. The picker is the one place
this repo injects keys into a menu (see the questions/autopilot guide for why
AskUserQuestion is different), and it is only defensible because the commit is
gated on a re-read of the highlighted row.
"""
import time

import pytest

from step2step.claude import runner as runner_mod
from step2step.claude import screen as scr
from step2step.claude.runner import (
    ENTER,
    EFFORT_LADDER,
    ModelControlError,
    Runner,
)

IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
WORKING = "out\n✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
COMMIT_KEYS = {"s", ENTER}

ROWS = ["Fable", "Sonnet", "Haiku"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# Captured before the fast_waits fixture shrinks them.
PROD = {k: getattr(runner_mod, k) for k in
        ("CHAR_TYPE_DELAY", "DIALOG_WAIT", "CONFIRM_LINE_WAIT", "KEY_STEP_DELAY")}


def picker(selected=0, effort="low", supported=True, session_hint=True,
           rows=ROWS, echo="/model"):
    """Render a picker the way the live TUI does (measured 2.1.220)."""
    body = ["  Select model",
            "  Switch between Claude models. Your pick becomes the default for "
            "new sessions.", ""]
    for i, name in enumerate(rows):
        body.append("  %s %d. %-20s %s 5 · a description"
                    % ("❯" if i == selected else " ", i + 1, name, name))
    body.append("")
    body.append("  ○ %s effort ←/→ to adjust" % effort.capitalize() if supported
                else "  ○ Effort not supported for %s" % rows[selected])
    foot = "  Enter to set as default · Esc to cancel"
    if session_hint:
        foot = "  Enter to set as default · s to use this session only · Esc to cancel"
    body.append(foot)
    return "❯ %s\n%s" % (echo, "\n".join(body))


CONFIRM_MENU = ("  Switch model?\n"
                "  This conversation is cached for the current model.\n"
                "  ❯ 1. Yes, switch to Sonnet 5\n"
                "    2. No, go back")


def confirmed(model="Sonnet 5", scope="for this session only", effort=None):
    line = "  ⎿  Set model to %s %s" % (model, scope)
    if effort:
        line += " with %s effort" % effort
    return IDLE + "\n" + line


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
    """Screen text with a settable style channel, so a test can exercise the
    pointer path and the row_flags path with the same driver."""

    def __init__(self, text=IDLE):
        self._text = text
        self.flags = None
        self.reads = 0

    def set(self, text):
        self._text = text

    def text(self):
        self.reads += 1
        return self._text

    def row_flags(self):
        return self.flags or [{"bold": False, "colored": False, "reverse": False}
                              for _ in self._text.splitlines()]

    def tail(self, n=12):
        rows = [r for r in self._text.splitlines() if r.strip()]
        return "\n".join(rows[-n:])


class FakeWatcher:
    def __init__(self, n=0):
        self.n = n

    def count(self):
        return self.n


class FakeEvents:
    def __init__(self, n=0):
        self.n = n

    def count(self, event=None, tool=None):
        return self.n


@pytest.fixture(autouse=True)
def fast_waits(monkeypatch):
    """Shrink the real-world timeouts. These tests exercise decision logic, not
    latency; the production values are asserted separately below."""
    monkeypatch.setattr(runner_mod, "DIALOG_WAIT", 0.5)
    monkeypatch.setattr(runner_mod, "CONFIRM_LINE_WAIT", 1.0)
    monkeypatch.setattr(runner_mod, "KEY_STEP_DELAY", 0.0)
    monkeypatch.setattr(runner_mod, "CHAR_TYPE_DELAY", 0.0)


def test_production_timeouts_are_sane():
    """Asserted against the values captured at import, before fast_waits."""
    assert PROD["CHAR_TYPE_DELAY"] > 0             # per-char typing is required
    assert PROD["DIALOG_WAIT"] >= 5
    assert PROD["CONFIRM_LINE_WAIT"] >= 10
    assert PROD["KEY_STEP_DELAY"] >= 0.2           # the TUI needs a frame to redraw


def _runner(tmp_path, screen=IDLE, stop=0, alive=True, events=None, **kw):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude", logger=lambda m: None, **kw)
    r.pty = FakePty(alive)
    r.screen = FakeScreen(screen)
    r.watcher = FakeWatcher(stop)
    r.events = FakeEvents(events) if events is not None else None
    return r


class Picker:
    """A scripted TUI: echoes typed characters into a composer, opens on Enter
    after "/model", then reacts to arrows and commit keys like the real widget.

    It records every key written WHILE THE PICKER IS OPEN, which is the scope
    the "no commit key on a failing path" invariant is about (the Enter that
    submits the slash command itself is legitimate)."""

    def __init__(self, runner, selected=0, effort="low", supported=True,
                 session_hint=True, rows=ROWS, on_commit=None,
                 ignore_arrows=False, vanish_after=None):
        self.r = runner
        self.selected = selected
        self.effort = effort
        self.supported = supported
        self.session_hint = session_hint
        self.rows = rows
        self.on_commit = on_commit
        self.ignore_arrows = ignore_arrows
        self.vanish_after = vanish_after
        self.presses = 0
        self.open = False
        self.composer = ""
        self.writes_while_open = []
        self.reads_at = []          # (key, screen.reads) for each key while open
        runner.pty.on_write = self.handle

    def render(self):
        if self.open:
            self.r.screen.set(picker(self.selected, self.effort, self.supported,
                                     self.session_hint, self.rows))
        else:
            self.r.screen.set("❯ %s\n%s" % (self.composer, IDLE))

    def handle(self, s):
        if self.open:
            self.writes_while_open.append(s)
            self.reads_at.append((s, self.r.screen.reads))
            self._in_picker(s)
            return
        if s == ENTER:
            if self.composer.strip() == "/model":
                self.open = True
                self.composer = ""
                self.render()
            return
        if s == scr.ESCAPE:
            self.composer = ""
            self.render()
            return
        if len(s) == 1 and s.isprintable():
            self.composer += s
            self.render()

    def _in_picker(self, s):
        self.presses += 1
        if self.vanish_after is not None and self.presses > self.vanish_after:
            self.open = False
            self.r.screen.set(IDLE)
            return
        if s in (scr.CURSOR_DOWN, scr.CURSOR_UP):
            if not self.ignore_arrows:
                step = 1 if s == scr.CURSOR_DOWN else -1
                self.selected = max(0, min(len(self.rows) - 1,
                                           self.selected + step))
        elif s in (scr.CURSOR_RIGHT, scr.CURSOR_LEFT) and self.supported:
            if not self.ignore_arrows and self.effort in EFFORTS:
                step = 1 if s == scr.CURSOR_RIGHT else -1
                i = max(0, min(len(EFFORTS) - 1, EFFORTS.index(self.effort) + step))
                self.effort = EFFORTS[i]
        elif s in COMMIT_KEYS:
            self.open = False
            self.r.screen.set(
                (self.on_commit(s, self) if self.on_commit
                 else confirmed(self.rows[self.selected] + " 5",
                                "for this session only" if s == "s"
                                else "and saved as your default for new sessions",
                                self.effort if self.supported else None)))
            return
        elif s == scr.ESCAPE:
            self.open = False
            self.r.screen.set(IDLE + "\n  ⎿  Kept model as Fable 5")
            return
        self.render()


def _no_commit_key(r, p=None):
    """No key that could commit was pressed inside the picker. (The Enter that
    submits `/model` itself is not a commit -- it only opens the dialog.)"""
    if p is not None:
        assert not (COMMIT_KEYS & set(p.writes_while_open)), \
            "a commit key was written inside the picker: %r" % p.writes_while_open
    assert "s" not in r.pty.writes, \
        "the session-only commit key was written: %r" % r.pty.writes


# --- typing -------------------------------------------------------------------
def test_type_text_writes_one_character_per_write(tmp_path):
    """The single most important guard in this file: a bracketed paste does NOT
    open the command palette (measured), so slash commands must be typed."""
    r = _runner(tmp_path)
    r._type_text("/model", delay=0)
    assert r.pty.writes == list("/model")


def test_enter_slash_command_escapes_when_the_echo_never_appears(tmp_path):
    r = _runner(tmp_path, screen=IDLE)
    assert r._enter_slash_command("/model", wait=0.2) is False
    assert r.pty.writes[-1] == scr.ESCAPE
    assert ENTER not in r.pty.writes


def test_enter_slash_command_submits_after_the_echo(tmp_path):
    r = _runner(tmp_path, screen="❯ /model\n" + IDLE)
    assert r._enter_slash_command("/model") is True
    assert r.pty.writes[-1] == ENTER


# --- picker: the happy paths --------------------------------------------------
def test_picker_navigates_to_the_target_and_commits_session_only(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=0)
    conf = r.set_model_via_picker("haiku")
    assert (conf.model, conf.scope) == ("Haiku 5", "session")
    assert r.pty.writes.count(scr.CURSOR_DOWN) == 2      # Fable -> Sonnet -> Haiku
    assert "s" in r.pty.writes and ENTER not in r.pty.writes[-3:]


def test_picker_walks_upward_when_the_target_is_above(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=2)
    r.set_model_via_picker("fable")
    assert r.pty.writes.count(scr.CURSOR_UP) == 2
    assert scr.CURSOR_DOWN not in r.pty.writes


def test_picker_does_not_move_when_already_on_target(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=1)
    r.set_model_via_picker("sonnet")
    assert scr.CURSOR_DOWN not in r.pty.writes
    assert scr.CURSOR_UP not in r.pty.writes


def test_picker_persist_uses_enter(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=1)
    conf = r.set_model_via_picker("sonnet", persist=True)
    assert conf.scope == "default"
    assert "s" not in r.pty.writes and ENTER in r.pty.writes


def test_picker_adjusts_effort_then_commits(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=1, effort="low")
    conf = r.set_model_via_picker("sonnet", effort="xhigh")
    assert p.effort == "xhigh" and conf.effort == "xhigh"
    assert r.pty.writes.count(scr.CURSOR_RIGHT) == 3     # low->medium->high->xhigh


def test_picker_walks_effort_left_when_target_is_lower(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=1, effort="max")
    r.set_model_via_picker("sonnet", effort="high")
    assert r.pty.writes.count(scr.CURSOR_LEFT) == 2
    assert scr.CURSOR_RIGHT not in r.pty.writes


def test_picker_answers_the_cache_invalidation_confirm(tmp_path):
    r = _runner(tmp_path, events=0)

    state = {"asked": False}

    def on_commit(key, p):
        state["asked"] = True
        r.pty.on_write = lambda s: (
            r.screen.set(confirmed("Sonnet 5", "for this session only"))
            if s == ENTER else None)
        return CONFIRM_MENU

    Picker(r, selected=1, on_commit=on_commit)
    conf = r.set_model_via_picker("sonnet")
    assert state["asked"] and conf.scope == "session"
    assert r.pty.writes[-1] == ENTER          # accepted the confirm


def test_picker_declining_the_cache_reset_raises_and_never_reopens(tmp_path):
    r = _runner(tmp_path, events=0)
    Picker(r, selected=1, on_commit=lambda key, p: CONFIRM_MENU)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("sonnet", accept_cache_reset=False)
    assert e.value.stage == "cache-declined"


# --- picker: every failure path must leave the commit key unwritten -----------
def test_never_commits_when_arrows_are_ignored(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0, ignore_arrows=True)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "nav-ignored"
    _no_commit_key(r, p)
    assert scr.ESCAPE in r.pty.writes


def test_never_commits_when_the_effort_will_not_move(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=1, effort="low", ignore_arrows=True)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("sonnet", effort="max")
    assert e.value.stage == "effort-nav"
    _no_commit_key(r, p)


def test_never_commits_when_effort_is_unsupported(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=2, supported=False)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku", effort="max")
    assert e.value.stage == "effort-unsupported"
    _no_commit_key(r, p)


def test_never_commits_when_the_dialog_vanishes_mid_navigation(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0, vanish_after=1)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "dialog-vanished"
    _no_commit_key(r, p)


def test_never_commits_when_a_stop_signal_races_the_navigation(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0)
    original = p.handle

    def racing(s):
        original(s)
        r.watcher.n = 1          # a turn completed underneath us
    r.pty.on_write = racing
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "stop-raced"
    _no_commit_key(r, p)


def test_never_commits_when_an_interaction_event_races(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0)
    original = p.handle

    def racing(s):
        original(s)
        r.events.n = 1           # e.g. an AskUserQuestion menu is rendering
    r.pty.on_write = racing
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "interaction-raced"
    _no_commit_key(r, p)


def test_never_commits_when_the_session_starts_working(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0)
    original = p.handle

    def racing(s):
        original(s)
        if s in (scr.CURSOR_DOWN, scr.CURSOR_UP):
            r.screen.set(WORKING)
    r.pty.on_write = racing
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage in ("working-raced", "dialog-vanished")
    _no_commit_key(r, p)


def test_refuses_enter_when_the_session_key_is_not_offered(tmp_path):
    """The "never silently rewrite the operator's global default" test."""
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=1, session_hint=False)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("sonnet")
    assert e.value.stage == "no-session-key"
    _no_commit_key(r, p)


def test_ambiguous_target_is_refused(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0, rows=["Opus", "Opus Pro", "Haiku"])
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("opu")
    assert e.value.stage == "ambiguous-model"
    _no_commit_key(r, p)


def test_unlisted_target_is_refused(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("gpt")
    assert e.value.stage == "model-not-listed"
    _no_commit_key(r, p)


def test_unreadable_highlight_aborts_without_guessing(tmp_path):
    """No pointer, no style: parse_model_dialog reports highlighted=None and the
    driver must Esc rather than pick a row."""
    r = _runner(tmp_path, screen="❯ /model\n" + IDLE, events=0)
    flat = picker(selected=0).replace("❯", " ")
    r.pty.on_write = lambda s: (r.screen.set(flat) if s == ENTER else None)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "dialog-parse"
    _no_commit_key(r)


def test_dialog_that_never_opens_aborts(tmp_path):
    r = _runner(tmp_path, screen="❯ /model\n" + IDLE, events=0)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("haiku")
    assert e.value.stage == "dialog-open"
    _no_commit_key(r)


def test_scope_mismatch_is_loud(tmp_path):
    """If a session-only commit somehow lands as a global default, fail rather
    than report success -- the operator's config may have moved."""
    r = _runner(tmp_path, events=0)
    Picker(r, selected=1, on_commit=lambda key, p: confirmed(
        "Sonnet 5", "and saved as your default for new sessions"))
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("sonnet")
    assert e.value.stage == "scope-mismatch"


def test_stale_confirmation_in_scrollback_does_not_satisfy_verification(tmp_path):
    """Baseline-relative, like the Stop-hook watcher: an older "Set model to …"
    line already on screen must not count as this change's confirmation."""
    stale = confirmed("Sonnet 5", "for this session only")
    r = _runner(tmp_path, screen=stale, events=0)
    Picker(r, selected=1, on_commit=lambda key, p: stale)   # nothing new appears
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_picker("sonnet")
    assert e.value.stage == "post-commit"


def test_precommit_rereads_the_screen_after_the_last_arrow(tmp_path):
    r = _runner(tmp_path, events=0)
    p = Picker(r, selected=0)
    reads_at_commit = {}
    r.pty.on_write = lambda s: (reads_at_commit.setdefault("n", r.screen.reads)
                                if s in COMMIT_KEYS else None, p.handle(s))[-1]
    r.set_model_via_picker("haiku")
    # The gate re-reads after navigation settles, so the commit key is written
    # strictly after more reads than the final arrow needed.
    assert reads_at_commit["n"] > 0


# --- the argument forms -------------------------------------------------------
def test_command_form_applies_and_verifies(tmp_path):
    r = _runner(tmp_path, screen="❯ /model sonnet\n" + IDLE, events=0)
    r.pty.on_write = lambda s: (
        r.screen.set(confirmed("Sonnet 5",
                               "and saved as your default for new sessions"))
        if s == ENTER else None)
    conf = r.set_model_via_command("sonnet")
    assert (conf.model, conf.scope) == ("Sonnet 5", "default")


def test_command_form_detects_a_rejected_argument(tmp_path):
    r = _runner(tmp_path, screen="❯ /model nope\n" + IDLE, events=0)
    r.pty.on_write = lambda s: (r.screen.set(picker()) if s == ENTER else None)
    with pytest.raises(ModelControlError) as e:
        r.set_model_via_command("nope")
    assert e.value.stage == "arg-rejected"


def test_effort_command_verifies_the_level(tmp_path):
    r = _runner(tmp_path, screen="❯ /effort high\n" + IDLE, events=0)
    r.pty.on_write = lambda s: (
        r.screen.set(IDLE + "\n  ⎿  Set effort level to high (saved as your "
                     "default for new sessions): Comprehensive")
        if s == ENTER else None)
    conf = r.set_effort_via_command("high")
    assert (conf.effort, conf.scope) == ("high", "default")


def test_effort_command_rejects_a_different_level(tmp_path):
    r = _runner(tmp_path, screen="❯ /effort high\n" + IDLE, events=0)
    r.pty.on_write = lambda s: (
        r.screen.set(IDLE + "\n  ⎿  Set effort level to low (saved as your "
                     "default for new sessions): Quick")
        if s == ENTER else None)
    with pytest.raises(ModelControlError) as e:
        r.set_effort_via_command("high")
    assert e.value.stage == "confirmation-mismatch"


def test_effort_ladder_covers_every_flag_level():
    from step2step.claude.runner import EFFORT_LEVELS
    assert set(EFFORT_LEVELS) <= set(EFFORT_LADDER)
