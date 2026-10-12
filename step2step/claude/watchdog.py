"""Read-only session watchdog (the extension spec's HealthMonitor).

The owning thread is the only writer, and it is usually blocked inside
wait_turn. Nobody else looked at a session in between: a dead child, a
usage-limit banner or a dialog that appeared while no one was waiting was
noticed only the next time the owner happened to poll (the former web app registry
read state only when a web request arrived). This daemon thread polls the
READ-ONLY surface every HEALTH_POLL seconds -- is_alive, idle_for, the screen
classification, the progress reading -- and reports state CHANGES to a
callback. It never writes to the PTY, never interrupts, never answers;
deciding what to do (escalate, replace the session, notify) is the harness's.

    wd = handle.watch(lambda event, info: log(event, info))
    ...
    wd.stop()

Events (each fired once per transition, `info` carries the evidence):
    died            the child process is gone
    usage_limited   the usage-limit banner is on screen (info["reset"])
    dialog_waiting  a question / plan-approval / unknown dialog is waiting
    silent          not working, not idle-looking, no output for
                    stall_seconds (info["idle_for"])
    no_progress     working but the progress sample has been flat for
                    progress_seconds (info["no_progress_for"])
    recovered       back to a healthy reading after one of the above
"""
from __future__ import annotations

import threading
import time

from . import screen as scr
from .runner import PROGRESS_SECONDS, STALL_SECONDS

HEALTH_POLL = 2.0

_PROBLEMS = ("died", "usage_limited", "dialog_waiting", "silent", "no_progress")


class SessionWatchdog:
    def __init__(self, handle, on_event, *, poll: float = HEALTH_POLL,
                 stall_seconds: float = STALL_SECONDS,
                 progress_seconds: float = PROGRESS_SECONDS):
        self.handle = handle
        self.on_event = on_event
        self.poll = poll
        self.stall_seconds = stall_seconds
        self.progress_seconds = progress_seconds
        self.state: str | None = None       # last reported condition
        self.events: list[tuple[str, dict]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> "SessionWatchdog":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="session-watchdog")
            self._thread.start()
        return self

    def stop(self, timeout: float | None = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                pass  # an observation that raised is not a reason to die
            if self.tick_result == "died":
                return
            self._stop.wait(self.poll)

    # ------------------------------------------------------------ observing
    tick_result: str | None = None

    def observe(self) -> tuple[str, dict]:
        """One reading: (condition, info). Read-only by construction."""
        handle = self.handle
        runner = handle._runner
        if not handle.is_alive():
            return "died", {}
        txt = runner.text() if getattr(runner, "screen", None) else ""
        if scr.is_usage_limit(txt):
            return "usage_limited", {"reset": scr.parse_usage_reset(txt)}
        kind = scr.classify_dialog(txt)
        if kind is not None:
            return "dialog_waiting", {"kind": kind}
        working = scr.is_working(txt)
        no_progress = handle._no_progress_for()
        if working and no_progress is not None and no_progress >= self.progress_seconds:
            return "no_progress", {"no_progress_for": no_progress}
        idle = runner.idle_for() if getattr(runner, "pty", None) else 0.0
        if not working and not scr.looks_idle(txt) and idle >= self.stall_seconds:
            return "silent", {"idle_for": idle}
        return "ok", {}

    def tick(self) -> str:
        """Observe once and fire the callback on a state change. Public so a
        harness (or a test) can drive it without the thread."""
        condition, info = self.observe()
        self.tick_result = condition
        if condition != self.state:
            previous, self.state = self.state, condition
            if condition in _PROBLEMS:
                self._fire(condition, info)
            elif previous in _PROBLEMS:
                self._fire("recovered", {"from": previous})
        return condition

    def _fire(self, event: str, info: dict) -> None:
        info = dict(info, at=time.time())
        self.events.append((event, info))
        try:
            self.on_event(event, info)
        except Exception:
            pass  # the harness's callback failing must not stop the watch
