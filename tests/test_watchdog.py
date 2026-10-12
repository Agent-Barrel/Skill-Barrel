"""SessionWatchdog: read-only observation, one event per transition."""
import pathlib
import time

from step2step.claude import transcript as tx
from step2step.claude.session import SessionHandle
from step2step.claude.watchdog import SessionWatchdog

IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
WORKING = "✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
ASK = ("Which?\n ❯ 1. A\n   2. B\n"
       "Enter to select · ↑/↓ to navigate · Esc to cancel")
USAGE = "body\n" * 20 + "You've reached your usage limit · resets at 7pm"
LIMBO = "neither working nor idle nor a dialog"


class FakePty:
    alive = True
    write_errors = 0

    def __init__(self):
        self.writes = []

    def isalive(self):
        return self.alive

    def write(self, s):
        self.writes.append(s)


class FakeScreen:
    def __init__(self, text=IDLE):
        self._text = text

    def set(self, text):
        self._text = text

    def text(self):
        return self._text

    def tail(self, n=12):
        return self._text


class FakeRunner:
    mode = "bypass"
    session_id = "wd-sid"
    workdir = pathlib.Path("wd")
    app_dir = pathlib.Path("app")
    claude_exe = "dummy"
    extra_args = ()
    last_progress_ts = None

    def __init__(self):
        self.pty = FakePty()
        self.screen = FakeScreen()
        self.events = None
        self.idle = 0.5

    def text(self):
        return self.screen.text()

    def idle_for(self):
        return self.idle

    def log(self, m):
        pass

    def _finalize(self):
        pass


def _wd(monkeypatch, **kw):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    h = SessionHandle(FakeRunner())
    seen = []
    wd = SessionWatchdog(h, lambda ev, info: seen.append((ev, info)), **kw)
    return h, wd, seen


def test_healthy_session_fires_nothing(monkeypatch):
    h, wd, seen = _wd(monkeypatch)
    assert wd.tick() == "ok" and wd.tick() == "ok"
    assert seen == [] and h._runner.pty.writes == []


def test_death_fires_once(monkeypatch):
    h, wd, seen = _wd(monkeypatch)
    h._runner.pty.alive = False
    assert wd.tick() == "died" and wd.tick() == "died"
    assert [e for e, _ in seen] == ["died"]


def test_dialog_and_usage_limit_and_recovery(monkeypatch):
    h, wd, seen = _wd(monkeypatch)
    h._runner.screen.set(ASK)
    wd.tick()
    h._runner.screen.set(IDLE)
    wd.tick()
    h._runner.screen.set(USAGE)
    wd.tick()
    assert [e for e, _ in seen] == ["dialog_waiting", "recovered", "usage_limited"]
    assert seen[0][1]["kind"] == "question"
    assert seen[2][1]["reset"] == "7pm"


def test_silence_and_no_progress(monkeypatch):
    h, wd, seen = _wd(monkeypatch, stall_seconds=10.0, progress_seconds=5.0)
    h._runner.screen.set(LIMBO)
    h._runner.idle = 11.0
    assert wd.tick() == "silent"
    h._runner.screen.set(WORKING)
    h._runner.last_progress_ts = time.monotonic() - 6.0
    assert wd.tick() == "no_progress"
    assert [e for e, _ in seen] == ["silent", "no_progress"]
    assert seen[1][1]["no_progress_for"] >= 5.0


def test_thread_lifecycle_and_handle_watch(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    h = SessionHandle(FakeRunner())
    seen = []
    wd = h.watch(lambda ev, info: seen.append(ev), poll=0.01)
    assert wd.alive
    h._runner.pty.alive = False
    deadline = time.monotonic() + 2.0
    while wd.alive and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen == ["died"] and not wd.alive       # a dead session ends the watch
    h.stop()                                        # idempotent stop


def test_callback_errors_do_not_stop_the_watch(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)
    h = SessionHandle(FakeRunner())

    def boom(ev, info):
        raise RuntimeError("callback bug")

    wd = SessionWatchdog(h, boom)
    h._runner.screen.set(ASK)
    assert wd.tick() == "dialog_waiting"
    assert wd.events[0][0] == "dialog_waiting"
