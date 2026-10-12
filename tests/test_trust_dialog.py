"""The 2.1.272 workspace-trust dialog: an unnumbered select whose default
highlight is "No, exit". The runner must walk the highlight onto the accept row
and verify it before Enter -- a blind Enter exits the session (measured)."""
import time

import pytest

from step2step.claude import runner as runner_mod
from step2step.claude import screen as scr
from step2step.claude.runner import ENTER, Runner

IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
OLD_TRUST = "Do you trust the files in this folder?\n\n(y/n)"


def trust_screen(hl: int) -> str:
    rows = ["Accessing workspace: /tmp/x", "",
            "Quick safety check: Is this a project you created or one you trust?",
            "Claude Code'll be able to read, edit, and execute files here.", "",
            "%s No, exit" % ("❯" if hl == 1 else " "),
            "%s Yes, I trust this folder" % ("❯" if hl == 2 else " "), "",
            "Enter to confirm · Esc to cancel"]
    return "\n".join(rows)


class FakePty:
    def __init__(self):
        self.alive = True
        self.writes = []
        self.on_write = None
        self.last_output_ts = time.monotonic()

    def isalive(self):
        return self.alive

    def write(self, s):
        self.writes.append(s)
        if self.on_write:
            self.on_write(s)


class FakeScreen:
    def __init__(self, text):
        self._text = text

    def set(self, text):
        self._text = text

    def text(self):
        return self._text

    def tail(self, n=12):
        return self._text


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(runner_mod, "KEY_VERIFY_DELAY", 0.0)
    monkeypatch.setattr(runner_mod, "TRUST_WAIT", 0.5)
    monkeypatch.setattr(runner_mod.time, "sleep", lambda s: None)


def _runner(tmp_path, screen):
    r = Runner(workdir=tmp_path / "wd", prompts=[], app_dir=tmp_path,
               claude_exe="dummy-claude", logger=lambda m: None)
    r.pty = FakePty()
    r.screen = FakeScreen(screen)
    return r


def test_rows_are_parsed_with_the_highlight():
    rows = scr.trust_dialog_rows(trust_screen(1))
    assert [(r.index, r.highlighted) for r in rows] == [(1, True), (2, False)]
    assert scr.TRUST_ACCEPT_RE.search(rows[1].label) and scr.TRUST_DECLINE_RE.search(rows[0].label)
    assert scr.trust_dialog_rows(OLD_TRUST) == []
    assert scr.is_trust_dialog(trust_screen(1)) and scr.is_trust_dialog(OLD_TRUST)


def test_walks_to_the_accept_row_before_enter(tmp_path):
    r = _runner(tmp_path, trust_screen(1))
    state = {"hl": 1}

    def write(s):
        if s == scr.CURSOR_DOWN:
            state["hl"] = 2
            r.screen.set(trust_screen(2))
        elif s == ENTER:
            r.screen.set(IDLE if state["hl"] == 2 else "")   # Enter on "No, exit" = dead session
            if state["hl"] == 1:
                r.pty.alive = False

    r.pty.on_write = write
    r._handle_trust()
    assert r.pty.writes == [scr.CURSOR_DOWN, ENTER]
    assert r.pty.alive and scr.looks_idle(r.screen.text())


def test_never_presses_enter_when_arrows_do_nothing(tmp_path):
    r = _runner(tmp_path, trust_screen(1))
    r._handle_trust()
    assert ENTER not in r.pty.writes and r.pty.writes[:1] == [scr.CURSOR_DOWN]


def test_enter_only_when_already_on_accept(tmp_path):
    r = _runner(tmp_path, trust_screen(2))
    r.pty.on_write = lambda s: r.screen.set(IDLE) if s == ENTER else None
    r._handle_trust()
    assert r.pty.writes == [ENTER]


def test_legacy_dialog_keeps_the_old_key_sequence(tmp_path):
    r = _runner(tmp_path, OLD_TRUST)
    r.pty.on_write = lambda s: r.screen.set(IDLE) if s == ENTER else None
    r._handle_trust()
    assert r.pty.writes == [ENTER]
