"""The state machine that drives one interactive Claude Code session.

Two modes (chosen by the caller):

- mode="bypass" (default): launch with --dangerously-skip-permissions; every
  prompt runs hands-off. Completion is the injected Stop hook (a signal-file line
  count increasing past a pre-submit baseline), with a screen watchdog for an
  adaptive stall timer and an idle-without-signal fallback.

- mode="plan": launch the SAME way (--dangerously-skip-permissions) then switch
  to plan mode in the TUI with shift+tab. Each prompt is planned, and the runner
  AUTO-APPROVES the plan by selecting option 1 (Enter) so it executes hands-off.
  Option 1 is "Yes, and bypass permissions" for a --dangerously-skip-permissions
  launch (verified). The plan-ready point is the approval menu (the Stop hook
  does NOT fire there); the post-approval execution DOES fire the Stop hook.
  Approving returns the session to bypass mode, so the runner re-enters plan mode
  before the next prompt.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import sys
import time
import uuid

from . import hooks
from . import screen as scr
from . import transcript as tx
from ..contracts import ControlError
from ..terminal.pty_session import PtySession
from ..terminal.screen import ScreenReader
from ..paths import REPO_ROOT

COLS, ROWS = 200, 50
TRUST_WAIT = 45.0
INIT_IDLE_WAIT = 60.0
CONFIRM_WAIT = 12.0
STALL_SECONDS = 180.0
SETTLE_QUIET = 0.8
POLL = 0.15
# _wait_turn_event (R1): screen must be still this long before the menu
# fallback trusts it, and a menu gets this long to render after its PreToolUse.
QUESTION_SETTLE = 2.0
MENU_RENDER_WAIT = 10.0
# Turn budget applied when a caller passes timeout=None. NEVER infinite: the
# autonomy record's incident 3 was a 5.5-hour turn whose screen kept repainting
# while nothing advanced, waited on by a caller that passed no deadline. A
# harness can raise this per session or per turn; it cannot switch it off.
DEFAULT_TURN_TIMEOUT = 7200.0
# Noisy-stagnation detection (see Runner.progress_sample): sample every
# PROGRESS_POLL seconds and call it stagnation when the sample has not changed
# for PROGRESS_SECONDS while the footer still says "working". Compile-heavy
# projects legitimately sit inside one tool call for many minutes, so the
# default is generous; a harness tunes it per unit. float("inf") disables it.
PROGRESS_SECONDS = 1800.0
PROGRESS_POLL = 30.0
# Closed-loop dialog navigation (answer_menu / approve_plan / reject_plan): the
# pause after each arrow before the highlight is re-read, and how long a
# committed dialog gets to disappear before the commit is called ignored.
KEY_VERIFY_DELAY = 0.35      # re-read cadence after an arrow key
KEY_MOVE_TIMEOUT = 3.0       # how long a highlight gets to move before "nav-ignored"
INJECT_VERIFY_TIMEOUT = 20.0
# Free disk below which preflight() warns.
MIN_FREE_MB = 512
# The plan-approval option that means "revise" (reject_plan); the last row is
# the fallback when no label matches.
PLAN_REJECT_RE = re.compile(r"tell claude what to change|no, keep planning", re.I)

# Env vars scrubbed from the child so it runs as a clean, top-level session on
# the user's subscription (never an API key -> never API billing). Beyond this
# exact list, EVERY CLAUDE*-prefixed var is scrubbed (see child_env): a session
# launched from inside Claude Code inherits CLAUDECODE, CLAUDE_CODE_ENTRYPOINT,
# CLAUDE_CODE_SESSION_ID, CLAUDE_CODE_SSE_PORT, and also CLAUDE_CODE_EXECPATH,
# CLAUDE_CODE_CHILD_SESSION, CLAUDE_PID, CLAUDE_EFFORT, etc. Any of these leaking
# in would make the spawned session act as a nested child rather than a clean
# top-level session, so we drop the whole prefix.
SCRUB_ENV = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
]

BRACKET_START = "\x1b[200~"
BRACKET_END = "\x1b[201~"
ENTER = "\r"
SHIFT_TAB = "\x1b[Z"  # cycles the permission mode in the TUI
MODE_SWITCH_TRIES = 10

# Values `claude --effort <level>` accepts (measured against v2.1.220 --help).
# The TUI itself knows more (ultracode, auto) and filters the list per model, so
# this tuple gates the LAUNCH FLAG only -- never the screen parser, which must
# report whatever it reads.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# Order the picker's ←/→ walk through, measured off the bare /effort slider
# ("low  medium  high  xhigh  max  ultracode"). Used only to pick a DIRECTION;
# every step is still verified by reading the screen back.
EFFORT_LADDER = ("low", "medium", "high", "xhigh", "max", "ultracode")

# --- /model picker driving (calibrated against Claude Code 2.1.220) ---------
CHAR_TYPE_DELAY = 0.03   # per character: a pasted slash command never opens the palette
SLASH_ECHO_WAIT = 4.0    # composer must echo what we typed before we press Enter
DIALOG_WAIT = 8.0        # the picker must render
DIALOG_SETTLE = 0.5      # quiet time before a dialog read is trusted
KEY_STEP_DELAY = 0.30    # after each arrow, before re-reading
NAV_STEP_PAD = 4         # slack over the theoretical step count
CONFIRM_LINE_WAIT = 15.0 # the "Set model to …" system line must appear
ABORT_ESC_TRIES = 5


class StallAbort(Exception):
    pass


class DialogError(ControlError):
    """A dialog interaction (menu answer, plan approve/reject) could not be
    verified. Same contract as ModelControlError: `stage` names the step; when
    it is raised before the commit key nothing was committed, and the dialog
    was Esc'd shut unless the failure was that it had already gone."""

    def __init__(self, message, *, stage, screen_tail=None):
        super().__init__(message)
        self.stage = stage
        self.screen_tail = screen_tail


class ModelControlError(RuntimeError):
    """A model/effort change could not be verified.

    Contract: whenever this is raised from a stage BEFORE the commit key, the
    dialog has been Esc'd shut and NOTHING was committed. `stage` names the step
    so a caller can escalate with the screen tail attached."""

    def __init__(self, message, *, stage, screen_tail=None):
        super().__init__(message)
        self.stage = stage
        self.screen_tail = screen_tail


def _has_flag(args, flag: str) -> bool:
    """True when `args` already carries `flag`, in either `--x v` or `--x=v`
    form. Used so a ctor-level model/effort never duplicates one the caller
    already put in extra_args (SessionHandle.start passes --model that way)."""
    prefix = flag + "="
    return any(a == flag or a.startswith(prefix) for a in args)


def _now() -> float:
    return time.monotonic()


def child_env() -> dict:
    env = os.environ.copy()
    for k in list(env):
        ku = k.upper()
        # Drop the exact auth vars and the entire CLAUDE* family. ANTHROPIC_MODEL
        # is intentionally NOT CLAUDE-prefixed and not in SCRUB_ENV, so a caller
        # that sets it to pick the spawned session's model is passed through.
        if ku in SCRUB_ENV or ku.startswith("CLAUDE"):
            env.pop(k, None)
    env["TERM"] = "xterm-256color"
    return env


def resolve_claude(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    found = shutil.which("claude")
    if found:
        return found
    exe = "claude.exe" if os.name == "nt" else "claude"
    fallback = pathlib.Path.home() / ".local" / "bin" / exe
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError("claude executable not found on PATH or ~/.local/bin")


class Runner:
    def __init__(
        self,
        *,
        workdir,
        prompts,
        app_dir,
        claude_exe=None,
        extra_args=None,
        hook_form="args",
        send_mode="paste",
        on_stall="pause",
        mode="bypass",
        model=None,
        effort=None,
        logger=None,
        on_turn=None,
        event_hooks=False,
    ):
        if mode not in ("bypass", "plan"):
            raise ValueError("mode must be 'bypass' or 'plan', got %r" % mode)
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ValueError("effort must be one of %s, got %r"
                             % (", ".join(EFFORT_LEVELS), effort))
        self.workdir = pathlib.Path(workdir).resolve()
        self.prompts = list(prompts)
        self.app_dir = pathlib.Path(app_dir).resolve()
        self.runtime = self.app_dir / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.claude_exe = resolve_claude(claude_exe)
        self.extra_args = list(extra_args or [])
        self.hook_form = hook_form
        self.send_mode = send_mode  # "paste" | "plain"
        self.on_stall = on_stall  # "pause" | "skip" | "abort"
        self.mode = mode  # "bypass" | "plan"
        # Launch-time model/effort. Both are optional and both defer to whatever
        # the caller already put in extra_args (see _argv), so nothing a previous
        # caller relied on changes shape.
        self.model = model
        self.effort = effort
        self.session_id = str(uuid.uuid4())
        self.python_exe = pathlib.Path(sys.executable)
        self.log = logger or (lambda m: print(m, flush=True))
        # Optional per-turn callback: on_turn(dict) after each completed turn, so a
        # calling harness can react (answer a question, branch) without waiting for
        # the whole run. Receives {index, status, response, tools, signal_lines}.
        self.on_turn = on_turn
        # Opt-in interaction-event hooks (R5). False keeps _prepare()'s settings
        # byte-identical to the pre-existing Stop-only shape.
        self.event_hooks = bool(event_hooks)
        self.events: hooks.EventWatcher | None = None
        self.pty: PtySession | None = None
        self.screen: ScreenReader | None = None
        self.watcher: hooks.SignalWatcher | None = None
        self.raw_log = self.runtime / ("pty-%s.log" % self.session_id)
        # Progress bookkeeping for noisy-stagnation detection (progress_sample).
        self._transcript_path: str | None = None
        self.last_progress_ts: float | None = None
        # Why the last _confirm_working came back the way it did.
        self.confirm_reason: str | None = None

    # ------------------------------------------------------------------ utils
    def _log_paths(self) -> list[str]:
        paths = getattr(self.pty, "log_paths", None)
        return paths() if callable(paths) else [str(self.raw_log)]

    def preflight(self) -> dict:
        """Cheap environment checks before a child is spawned, each with the
        remedy in the message: {"fatal": [...], "warnings": [...]}. The
        autonomy record's incident 2 started with nobody looking at the
        environment; tool/daemon/docker checks belong to the harness
        (barrel.core.preflight), this covers only what the substrate itself
        needs to run at all."""
        fatal: list[str] = []
        warnings: list[str] = []
        exe = self.claude_exe
        resolved = exe if os.path.isabs(exe) or os.sep in exe else shutil.which(exe)
        if not resolved or not os.path.isfile(resolved):
            fatal.append("claude executable not found: %s -- install Claude Code or "
                         "pass claude_exe=" % exe)
        elif not os.access(resolved, os.X_OK):
            fatal.append("claude executable is not executable: %s -- fix its mode"
                         % resolved)
        try:
            self.runtime.mkdir(parents=True, exist_ok=True)
            probe = self.runtime / (".write-probe-%s" % self.session_id)
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as e:
            fatal.append("runtime dir is not writable: %s (%s) -- pass another app_dir"
                         % (self.runtime, e))
        try:
            free_mb = shutil.disk_usage(str(self.runtime)).free // (1024 * 1024)
            if free_mb < MIN_FREE_MB:
                warnings.append("only %d MB free under %s -- free disk before a long "
                                "session (PTY logs, transcripts, builds)"
                                % (free_mb, self.runtime))
        except OSError:
            pass
        return {"fatal": fatal, "warnings": warnings}

    def text(self) -> str:
        return self.screen.text()

    def idle_for(self) -> float:
        return _now() - self.pty.last_output_ts

    def progress_sample(self, probe=None) -> dict:
        """A cheap "is anything actually happening" reading.

        Output volume is NOT progress: a worker running its own wait tool
        repaints the screen for hours while nothing advances, and the
        silence-based stall timer never fires. So the wait loop compares THIS
        over time instead: the JSONL transcript Claude appends as it goes
        (bytes and records), the hook events file, the Stop count, and an
        optional caller `probe` (a harness adds e.g. a worktree digest). Equal
        samples for `progress_seconds` while "working" is noisy stagnation."""
        path = self._transcript_path
        if not path or not os.path.exists(path):
            path = tx.find_transcript(self.session_id)
            self._transcript_path = path
        tbytes = trecords = 0
        if path:
            try:
                tbytes = os.path.getsize(path)
                with open(path, "rb") as fh:
                    trecords = sum(chunk.count(b"\n")
                                   for chunk in iter(lambda: fh.read(1 << 20), b""))
            except OSError:
                pass
        sample = {
            "transcript_bytes": tbytes,
            "transcript_records": trecords,
            "hook_events": (len(self.events.events())
                            if self.events is not None else 0),
            "stop_count": self.watcher.count() if self.watcher is not None else 0,
        }
        if probe is not None:
            try:
                sample["probe"] = probe()
            except Exception as e:  # a broken probe must not wedge the wait itself
                sample["probe"] = "probe-error:%r" % (e,)
        return sample

    def _wait(self, pred, timeout, poll=POLL) -> bool:
        end = _now() + timeout
        while _now() < end:
            if not self.pty.isalive():
                return False
            try:
                if pred():
                    return True
            except Exception:
                pass
            time.sleep(poll)
        return False

    def _wait_settled(self, quiet=SETTLE_QUIET, timeout=10.0) -> bool:
        return self._wait(
            lambda: not scr.is_working(self.text()) and self.idle_for() >= quiet,
            timeout=timeout,
        )

    # ------------------------------------------------------------------ setup
    def _prepare(self) -> None:
        hook_script = hooks.write_signal_hook(self.runtime / "signal_hook.py")
        self.signal_file = self.runtime / ("run-%s.signal" % self.session_id)
        self.watcher = hooks.SignalWatcher(self.signal_file)
        self.watcher.reset()
        events_file = None
        if self.event_hooks:
            events_file = self.runtime / ("run-%s.events" % self.session_id)
            self.events = hooks.EventWatcher(events_file)
            self.events.reset()
        self.settings_file = self.runtime / ("hooks-settings-%s.json" % self.session_id)
        hooks.write_settings(
            self.settings_file,
            hooks.build_settings(
                self.python_exe, hook_script, self.signal_file, form=self.hook_form,
                events_file=events_file,
            ),
        )

    def _argv(self) -> list[str]:
        argv = [
            self.claude_exe,
            "--session-id",
            self.session_id,
            "--settings",
            str(self.settings_file),
            "--dangerously-skip-permissions",
        ]
        # extra_args wins: a caller that already passed --model/--effort there
        # (SessionHandle.start does) keeps exactly one copy of the flag.
        for flag, value in (("--model", self.model), ("--effort", self.effort)):
            if not value:
                continue
            if _has_flag(self.extra_args, flag):
                self.log("[argv] %s already in extra_args; ctor value %r ignored"
                         % (flag, value))
                continue
            argv += [flag, value]
        return argv + list(self.extra_args)

    def _spawn(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.screen = ScreenReader(COLS, ROWS)
        self.pty = PtySession(
            self._argv(),
            cwd=str(self.workdir),
            cols=COLS,
            rows=ROWS,
            env=child_env(),
            raw_log_path=str(self.raw_log),
            on_data=self.screen.feed,
        )
        self.pty.spawn()
        self.log("[spawn] %s" % " ".join(self._argv()))
        self.log("[spawn] cwd=%s" % self.workdir)
        # Report the EFFECTIVE model/effort, which may have come from extra_args
        # (SessionHandle.start passes them that way) rather than the ctor.
        argv = self._argv()
        eff = {f: (argv[argv.index(f) + 1] if f in argv else None)
               for f in ("--model", "--effort")}
        self.log("[spawn] mode=%s session=%s hook_form=%s send_mode=%s "
                 "model=%s effort=%s"
                 % (self.mode, self.session_id, self.hook_form, self.send_mode,
                    eff["--model"], eff["--effort"]))

    # ------------------------------------------------------------------ trust
    def _handle_trust(self) -> None:
        ok = self._wait(
            lambda: scr.is_trust_dialog(self.text()) or scr.looks_idle(self.text()),
            timeout=TRUST_WAIT,
        )
        if not ok:
            self.log("[trust] neither dialog nor idle within %ss" % TRUST_WAIT)
            return
        if not scr.is_trust_dialog(self.text()):
            self.log("[trust] no trust dialog (already trusted)")
            return
        self.log("[trust] dialog detected; attempting to accept")
        if scr.trust_dialog_rows(self.text()):
            # The menu shape (2.1.272+): the default highlight is "No, exit", so
            # the only safe move is to walk the highlight onto the accept row and
            # verify it before Enter. Never fall through to a blind Enter here.
            if self._accept_trust_menu():
                return
            self.log("[trust] FAILED to accept the trust menu (no key was committed)")
            return
        # Older dialog shapes: re-check after EACH key so we never type into an
        # already-idle box.
        for i, keys in enumerate([ENTER, "1" + ENTER, "y" + ENTER], 1):
            self.pty.write(keys)
            time.sleep(1.2)
            if not scr.is_trust_dialog(self.text()):
                self.log("[trust] accepted (attempt %d)" % i)
                return
        self.log("[trust] FAILED to dismiss trust dialog")

    def _accept_trust_menu(self) -> bool:
        """Arrow the trust dialog's highlight onto "Yes, I trust this folder",
        re-reading after every key; Enter only on a verified highlight."""
        for _ in range(4 + NAV_STEP_PAD):
            rows = scr.trust_dialog_rows(self.text())
            highlighted = [r for r in rows if r.highlighted]
            accept = next((r for r in rows if scr.TRUST_ACCEPT_RE.search(r.label)), None)
            if accept is None or len(highlighted) != 1:
                self.log("[trust] cannot read the menu highlight; not pressing Enter")
                return False
            if scr.TRUST_ACCEPT_RE.search(highlighted[0].label):
                self.pty.write(ENTER)
                if self._wait(lambda: not scr.is_trust_dialog(self.text()), timeout=8.0):
                    self.log("[trust] accepted (%s)" % highlighted[0].label)
                    return True
                return False
            before = highlighted[0].index
            self.pty.write(scr.CURSOR_DOWN if accept.index > before else scr.CURSOR_UP)

            def moved():
                after = [r for r in scr.trust_dialog_rows(self.text()) if r.highlighted]
                return len(after) == 1 and after[0].index != before

            self._wait(moved, timeout=KEY_MOVE_TIMEOUT, poll=KEY_VERIFY_DELAY)
            if not moved():
                self.log("[trust] arrow key moved nothing; not pressing Enter")
                return False
        return False

    def _wait_initial_idle(self) -> bool:
        ok = self._wait(lambda: scr.looks_idle(self.text()), timeout=INIT_IDLE_WAIT)
        self._wait_settled(quiet=1.0, timeout=8.0)
        self.log("[idle] initial input box ready" if ok
                 else "[idle] WARNING initial idle not confirmed; proceeding")
        return ok

    # ------------------------------------------------------------------ mode
    def _ensure_mode(self, target: str) -> bool:
        """Cycle the TUI permission mode with shift+tab until the footer shows
        `target` (e.g. 'plan'). Robust to the starting mode and to a missed
        keypress; checks the footer before each press."""
        for _ in range(MODE_SWITCH_TRIES):
            if scr.current_mode(self.text()) == target:
                return True
            self.pty.write(SHIFT_TAB)
            time.sleep(0.8)
        ok = scr.current_mode(self.text()) == target
        if ok:
            return True
        self.log("[mode] could not switch to %s (footer=%r)"
                 % (target, scr.current_mode(self.text())))
        return False

    # ------------------------------------------------------- model / effort
    def _fail_model(self, stage: str, message: str) -> None:
        """Raise ModelControlError with the screen tail attached. Callers reach
        this only through paths that have already Esc'd the dialog shut."""
        tail = self.screen.tail(16) if self.screen else ""
        self.log("[model] FAILED at %s: %s" % (stage, message))
        raise ModelControlError(message, stage=stage, screen_tail=tail)

    def _type_text(self, text: str, delay: float = CHAR_TYPE_DELAY) -> None:
        """Type one character at a time.

        NOT a bracketed paste: measured (see the substrate findings doc) that a
        pasted "/exit" never opens the command palette -- only per-character
        input does. Every slash command this module sends goes through here."""
        for ch in text:
            self.pty.write(ch)
            time.sleep(delay)

    def _enter_slash_command(self, line: str, *, wait: float = SLASH_ECHO_WAIT) -> bool:
        """Type `line` and submit it only after the composer echoes it back.

        Returns False (after pressing ESC to clear) when the echo never appears,
        so Enter is never pressed into a composer whose contents we could not
        confirm."""
        self._type_text(line)
        if not self._wait(lambda: scr.slash_input_echo(self.text(), line),
                          timeout=wait):
            self.log("[model] composer never echoed %r; aborting" % line)
            self.pty.write(scr.ESCAPE)
            time.sleep(0.5)
            return False
        self.pty.write(ENTER)
        return True

    def _read_model_dialog(self):
        flags = self.screen.row_flags() if self.screen else None
        return scr.parse_model_dialog(self.text(), row_flags=flags)

    def _abort_model_dialog(self) -> bool:
        """ESC until neither the picker nor the switch-confirm is up. Runs in a
        `finally` on every failure path so a dialog is never left open across a
        later send_prompt/wait_turn."""
        for _ in range(ABORT_ESC_TRIES):
            txt = self.text()
            if not scr.is_model_dialog(txt) and not scr.is_switch_confirm(txt):
                return True
            self.pty.write(scr.ESCAPE)
            time.sleep(0.6)
        self.log("[model] WARNING could not dismiss the dialog")
        return False

    def _guard_model_dialog(self, base: dict) -> None:
        """Re-verify the world before EVERY keypress. This is the guard the
        extension spec calls for: if a turn ended, a question menu rendered, or
        the dialog vanished while we were navigating, stop immediately rather
        than press the next key into whatever replaced it."""
        if not self.pty.isalive():
            self._fail_model("eof", "session ended while the dialog was open")
        if self.watcher is not None and self.watcher.count() > base["stop"]:
            self._fail_model("stop-raced", "a turn completed mid-navigation")
        if self.events is not None and self.events.count() > base["events"]:
            self._fail_model("interaction-raced",
                             "an interaction event fired mid-navigation")
        txt = self.text()
        if scr.is_working(txt):
            self._fail_model("working-raced", "the session started working")
        if not scr.is_model_dialog(txt) and not scr.is_switch_confirm(txt):
            self._fail_model("dialog-vanished", "the dialog is no longer on screen")

    def _model_baseline(self) -> dict:
        txt = self.text()
        return {
            "stop": self.watcher.count() if self.watcher is not None else 0,
            "events": self.events.count() if self.events is not None else 0,
            "confirms": len(scr.find_model_confirmations(txt)),
            "effort_confirms": len(scr.find_effort_confirmations(txt)),
        }

    def _open_model_dialog(self, base: dict):
        """`/model` with no argument -> the picker. Raises (dialog already shut)
        when it does not render or cannot be read."""
        if not self._enter_slash_command("/model"):
            self._fail_model("slash-echo", "composer never echoed /model")
        if not self._wait(lambda: scr.is_model_dialog(self.text()),
                          timeout=DIALOG_WAIT):
            self._abort_model_dialog()
            self._fail_model("dialog-open", "the /model picker did not render")
        self._wait_settled(quiet=DIALOG_SETTLE, timeout=5.0)
        dialog = self._read_model_dialog()
        if dialog is None or dialog.highlighted is None:
            self._abort_model_dialog()
            self._fail_model(
                "dialog-parse",
                "cannot tell which row is selected (source=%s)"
                % (dialog.highlight_source if dialog else "none"))
        return dialog

    def _select_model_row(self, target: str, base: dict):
        """Walk the highlight onto `target`, verifying after every press."""
        dialog = self._read_model_dialog()
        budget = len(dialog.rows) + dialog.hidden_rows + NAV_STEP_PAD
        stuck = 0
        for _ in range(budget):
            self._guard_model_dialog(base)
            dialog = self._read_model_dialog()
            if dialog is None or dialog.highlighted is None:
                self._fail_model("dialog-parse", "highlight became unreadable")
            matches = scr.matching_model_rows(dialog.rows, target)
            if len(matches) > 1:
                self._fail_model(
                    "ambiguous-model",
                    "%r matches %d rows: %r -- name it more precisely"
                    % (target, len(matches), [r.name for r in matches]))
            if not matches:
                self._fail_model(
                    "model-not-listed",
                    "%r is not in the picker; rows=%r"
                    % (target, [r.name for r in dialog.rows]))
            want = matches[0]
            if want.name == dialog.highlighted.name:
                return dialog
            before = dialog.highlighted.name
            here = dialog.rows.index(dialog.highlighted)
            there = dialog.rows.index(want)
            self.pty.write(scr.CURSOR_DOWN if there > here else scr.CURSOR_UP)
            time.sleep(KEY_STEP_DELAY)
            after = self._read_model_dialog()
            moved = (after is not None and after.highlighted is not None
                     and after.highlighted.name != before)
            stuck = 0 if moved else stuck + 1
            if stuck >= 2:
                self._fail_model("nav-ignored",
                                 "two arrow presses moved nothing")
        self._fail_model("model-nav", "never reached %r within %d steps"
                         % (target, budget))

    def _adjust_effort(self, target: str, row_name: str, base: dict):
        """Walk ←/→ to `target`.

        The widget is ONE line for the whole list -- it always shows the focused
        row's effort -- so the row must already be selected, and every step
        re-checks that ←/→ did not move it."""
        dialog = self._read_model_dialog()
        if not dialog.effort_supported:
            self._fail_model("effort-unsupported",
                             "%s does not support an effort level" % row_name)
        budget = 2 * len(EFFORT_LADDER) + NAV_STEP_PAD
        stuck = 0
        for _ in range(budget):
            self._guard_model_dialog(base)
            dialog = self._read_model_dialog()
            if dialog is None or dialog.highlighted is None:
                self._fail_model("dialog-parse", "highlight became unreadable")
            if dialog.highlighted.name != row_name:
                self._fail_model("effort-moved-row",
                                 "left/right moved the selection off %r onto %r"
                                 % (row_name, dialog.highlighted.name))
            if dialog.effort == target:
                return dialog
            before = dialog.effort
            # Direction from the known ladder; an unknown current level just
            # walks right and lets the read-back decide.
            key = scr.CURSOR_RIGHT
            if before in EFFORT_LADDER and target in EFFORT_LADDER:
                if EFFORT_LADDER.index(target) < EFFORT_LADDER.index(before):
                    key = scr.CURSOR_LEFT
            self.pty.write(key)
            time.sleep(KEY_STEP_DELAY)
            after = self._read_model_dialog()
            moved = after is not None and after.effort != before
            stuck = 0 if moved else stuck + 1
            if stuck >= 2:
                self._fail_model(
                    "effort-nav",
                    "%r is not reachable for %s (stuck at %r)"
                    % (target, row_name, before))
        self._fail_model("effort-nav", "never reached effort %r" % target)

    def _resolve_switch_confirm(self, *, accept: bool) -> None:
        """Answer the cache-invalidation dialog ("Switch model?").

        It is a plain numbered select, so the existing menu parser reads it. We
        require the highlight to actually be the "Yes, switch to …" option
        before pressing Enter -- never a blind Enter into a two-option menu."""
        if not accept:
            self.pty.write(scr.ESCAPE)
            time.sleep(1.0)
            return
        opt = scr.highlighted_option(self.screen.tail(14))
        if opt is None or not opt.label.lower().startswith(scr.SWITCH_ACCEPT_PREFIX):
            self._abort_model_dialog()
            self._fail_model("switch-confirm",
                             "the accept option is not highlighted (got %r)"
                             % (opt.label if opt else None))
        self.log("[model] cache-invalidation confirm: %s" % opt.label)
        self.pty.write(ENTER)
        time.sleep(0.6)

    def _await_model_confirmation(self, base: dict, *, accept_cache_reset: bool):
        """Wait for a NEW "Set model to …" line, answering the cache confirm on
        the way if it appears. Baseline-relative: the line is scrollback, so an
        older one must never satisfy the check."""
        deadline = _now() + CONFIRM_LINE_WAIT
        handled_confirm = False
        while _now() < deadline:
            if not self.pty.isalive():
                self._fail_model("eof", "session ended awaiting the confirmation")
            txt = self.text()
            found = scr.find_model_confirmations(txt)
            if len(found) > base["confirms"]:
                return found[-1]
            if scr.is_switch_confirm(txt) and not handled_confirm:
                self._wait_settled(quiet=DIALOG_SETTLE, timeout=3.0)
                self._resolve_switch_confirm(accept=accept_cache_reset)
                handled_confirm = True
                if not accept_cache_reset:
                    self._fail_model(
                        "cache-declined",
                        "declined the cache reset; kept %r"
                        % scr.parse_kept_model(self.text()))
                deadline = _now() + CONFIRM_LINE_WAIT
            time.sleep(POLL)
        self._abort_model_dialog()
        self._fail_model("post-commit", "no confirmation line within %ss"
                         % CONFIRM_LINE_WAIT)

    def set_model_via_picker(self, model: str, *, effort: str | None = None,
                             persist: bool = False,
                             accept_cache_reset: bool = True):
        """Drive `/model` exactly as a person would: arrow to the row, arrow the
        effort, verify, commit.

        `persist=False` commits with 's' ("use this session only"), which was
        measured NOT to touch ~/.claude/settings.json -- unless `effort` is also
        changed, which always writes the global effortLevel (see set_effort).
        Returns the parsed confirmation line."""
        base = self._model_baseline()
        self.log("[model] picker: model=%r effort=%r persist=%s"
                 % (model, effort, persist))
        committed = False
        try:
            self._open_model_dialog(base)
            dialog = self._select_model_row(model, base)
            row_name = dialog.highlighted.name
            if effort is not None:
                dialog = self._adjust_effort(effort, row_name, base)

            # --- pre-commit gate: the last read before any committing key ---
            self._guard_model_dialog(base)
            self._wait_settled(quiet=DIALOG_SETTLE, timeout=3.0)
            dialog = self._read_model_dialog()
            if dialog is None or dialog.highlighted is None:
                self._fail_model("precommit", "dialog unreadable at commit time")
            if dialog.highlighted.name != row_name \
                    or not scr.model_matches(dialog.highlighted.name, model):
                self._fail_model("precommit",
                                 "highlight is %r, wanted %r"
                                 % (dialog.highlighted.name, model))
            if effort is not None and dialog.effort != effort:
                self._fail_model("precommit", "effort is %r, wanted %r"
                                 % (dialog.effort, effort))

            if persist:
                key = ENTER
            else:
                if not dialog.session_only_hint:
                    self._fail_model(
                        "no-session-key",
                        "the footer does not offer 's' (use this session only); "
                        "refusing to fall back to Enter, which would rewrite "
                        "your global default")
                key = "s"
            self.pty.write(key)
            committed = True
            time.sleep(0.5)
            conf = self._await_model_confirmation(
                base, accept_cache_reset=accept_cache_reset)
        except Exception:
            self._abort_model_dialog()
            raise

        want_scope = "default" if persist else "session"
        if conf.scope != want_scope:
            self._fail_model("scope-mismatch",
                             "committed with scope=%r but asked for %r (%s)"
                             % (conf.scope, want_scope, conf.line))
        if not scr.model_matches(conf.model, model):
            self._fail_model("confirmation-mismatch",
                             "confirmation says %r, wanted %r"
                             % (conf.model, model))
        self.log("[model] %s%s" % (conf.line, "" if committed else " (?)"))
        return conf

    def set_model_via_command(self, model: str, *,
                              accept_cache_reset: bool = True):
        """`/model <alias>`. Measured to ALWAYS save the global default, so it
        is only reachable through persist=True."""
        base = self._model_baseline()
        line = "/model %s" % model
        self.log("[model] command: %s" % line)
        if not self._enter_slash_command(line):
            self._fail_model("slash-echo", "composer never echoed %r" % line)
        if self._wait(lambda: scr.is_model_dialog(self.text()), timeout=3.0):
            # The argument was not accepted and the picker opened instead.
            self._abort_model_dialog()
            self._fail_model("arg-rejected",
                             "%r opened the picker instead of applying" % line)
        conf = self._await_model_confirmation(
            base, accept_cache_reset=accept_cache_reset)
        if not scr.model_matches(conf.model, model):
            self._fail_model("confirmation-mismatch",
                             "confirmation says %r, wanted %r"
                             % (conf.model, model))
        self.log("[model] %s" % conf.line)
        return conf

    def set_effort_via_command(self, effort: str, *,
                               accept_cache_reset: bool = True):
        """`/effort <level>`. Measured to ALWAYS save the global default; the
        bare `/effort` slider is never opened (it renders as a positional track
        that no text predicate can read)."""
        base = self._model_baseline()
        line = "/effort %s" % effort
        self.log("[model] command: %s" % line)
        if not self._enter_slash_command(line):
            self._fail_model("slash-echo", "composer never echoed %r" % line)
        deadline = _now() + CONFIRM_LINE_WAIT
        handled = False
        while _now() < deadline:
            if not self.pty.isalive():
                self._fail_model("eof", "session ended awaiting the confirmation")
            txt = self.text()
            found = scr.find_effort_confirmations(txt)
            if len(found) > base["effort_confirms"]:
                conf = found[-1]
                if conf.effort != effort:
                    self._fail_model("confirmation-mismatch",
                                     "confirmation says %r, wanted %r"
                                     % (conf.effort, effort))
                self.log("[model] %s" % conf.line)
                return conf
            if scr.is_switch_confirm(txt) and not handled:
                self._wait_settled(quiet=DIALOG_SETTLE, timeout=3.0)
                self._resolve_switch_confirm(accept=accept_cache_reset)
                handled = True
                if not accept_cache_reset:
                    self._fail_model("cache-declined", "declined the cache reset")
                deadline = _now() + CONFIRM_LINE_WAIT
            time.sleep(POLL)
        self._abort_model_dialog()
        self._fail_model("post-commit", "no effort confirmation within %ss"
                         % CONFIRM_LINE_WAIT)

    # ------------------------------------------------------------------ send
    def _send_prompt(self, idx: int, text: str) -> int:
        baseline = self.watcher.count()
        norm = text.replace("\r\n", "\n").replace("\r", "\n")
        preview = norm.replace("\n", "\\n")[:90]
        self.log("[send %d/%d] %d chars: %s" % (idx, len(self.prompts), len(norm), preview))
        if self.send_mode == "paste":
            self.pty.write(BRACKET_START + norm + BRACKET_END)
        else:
            self.pty.write(norm)
        time.sleep(0.15)
        self.pty.write(ENTER)
        return baseline

    def _event_count(self, event: str, tool: str | None = None) -> int:
        """Count of hook events of `event` (and `tool`), 0 without event hooks."""
        if self.events is None:
            return 0
        return sum(1 for _ts, ev, _sid, tl in self.events.events()
                   if ev == event and (tool is None or tl == tool))

    def _confirm_working(self, baseline: int, baseline_events: int | None = None) -> bool:
        """Did the prompt we just sent actually start a turn?

        Evidence of a start: the working spinner, a Stop past `baseline` (an
        instant turn), an interaction event past `baseline_events`, or one of
        the two identified dialogs rendered at once (spec R3). Without any of
        it within CONFIRM_WAIT, Enter is re-sent ONCE -- unless something is
        on screen that would EAT that Enter (a dialog, the usage-limit banner,
        the trust prompt, the /model picker or its switch confirm): then
        nothing is pressed and this returns False with confirm_reason
        "blocked". A swallowed submission reported as a success is the most
        dangerous failure in the autonomy record, so callers treat False as
        "no turn started" rather than as "probably fine"."""
        def started():
            txt = self.text()
            if self.watcher.count() > baseline:
                return True
            if (baseline_events is not None
                    and self._event_count_total() > baseline_events):
                return True
            return (scr.is_working(txt)
                    or scr.classify_dialog(txt) in ("question", "plan_approval"))

        def blocked():
            txt = self.text()
            return (scr.classify_dialog(txt) is not None or scr.is_usage_limit(txt)
                    or scr.is_trust_dialog(txt) or scr.is_model_dialog(txt)
                    or scr.is_switch_confirm(txt))

        self.confirm_reason = None
        if self._wait(started, timeout=CONFIRM_WAIT):
            return True
        if blocked():
            self.confirm_reason = "blocked"
            self.log("[confirm] no working/signal in %ss and the screen would eat "
                     "an Enter; not re-sending" % CONFIRM_WAIT)
            return False
        self.log("[confirm] no working/signal in %ss; re-sending Enter" % CONFIRM_WAIT)
        self.pty.write(ENTER)
        if self._wait(started, timeout=CONFIRM_WAIT):
            self.confirm_reason = "resent"
            return True
        self.confirm_reason = "unconfirmed"
        return False

    def _event_count_total(self) -> int:
        return len(self.events.events()) if self.events is not None else 0

    def _wait_for_signal(self, baseline: int, timeout: float | None = None) -> str:
        """Wait for the Stop-hook signal to increment past `baseline` (a turn
        finished). Adaptive stall: a turn is only 'stalled' when there's been no
        signal AND no screen activity for STALL_SECONDS. The turn budget
        (`timeout`, default DEFAULT_TURN_TIMEOUT -- never infinite) also ends
        the wait as a stall, so the caller's stall policy decides."""
        deadline = _now() + (DEFAULT_TURN_TIMEOUT if timeout is None else timeout)
        while True:
            if not self.pty.isalive():
                self.log("[wait] session ended (EOF)")
                return "eof"
            if self.watcher.count() > baseline:
                return "signal"
            if _now() >= deadline:
                self.log("[wait] turn budget exceeded -> stall")
                return "stall"
            txt = self.text()
            if scr.is_working(txt) or self.idle_for() < STALL_SECONDS:
                time.sleep(POLL)
                continue
            if scr.looks_idle(txt):
                self.log("[wait] idle %.0fs, no signal -> done (possible hook miss)"
                         % self.idle_for())
                return "idle-fallback"
            return "stall"

    def _wait_plan_ready(self, baseline: int, timeout: float | None = None) -> str:
        """Plan mode: wait until the plan-approval menu appears (the Stop hook
        does NOT fire there). Also returns 'signal' if the turn happened to end
        without a plan (e.g. a pure question), so callers handle both. Bounded
        by the same turn budget as _wait_for_signal."""
        deadline = _now() + (DEFAULT_TURN_TIMEOUT if timeout is None else timeout)
        while True:
            if not self.pty.isalive():
                self.log("[wait] session ended (EOF)")
                return "eof"
            if self.watcher.count() > baseline:
                return "signal"  # turn ended without an approval menu
            if _now() >= deadline:
                self.log("[wait] turn budget exceeded -> stall")
                return "stall"
            txt = self.text()
            if scr.is_plan_approval(txt):
                return "approval"
            if scr.is_working(txt) or self.idle_for() < STALL_SECONDS:
                time.sleep(POLL)
                continue
            if scr.looks_idle(txt):
                return "idle-fallback"
            return "stall"

    # ------------------------------------------- interactive turn (SessionHandle)
    def _pending_interaction_event(self, baseline_events: int) -> str | None:
        """The interaction tool (AskUserQuestion/ExitPlanMode) whose PreToolUse
        appeared past `baseline_events` with no matching PostToolUse yet. These
        interactions are serialized in the TUI, so a single slot suffices."""
        if not self.events:
            return None
        pending = None
        for _ts, ev, _sid, tool in self.events.events()[baseline_events:]:
            if ev == "PreToolUse" and tool in tx.QUESTION_TOOLS:
                pending = tool
            elif ev == "PostToolUse" and tool == pending:
                pending = None
        return pending

    def _saw_notification(self, baseline_events: int) -> bool:
        if not self.events:
            return False
        return any(ev == "Notification"
                   for _ts, ev, _sid, _tool in self.events.events()[baseline_events:])

    def _pending_transcript_tool(self) -> dict | None:
        try:
            return tx.pending_tool_use(tx.find_transcript(self.session_id))
        except Exception:
            return None

    def _confirm_menu_render(self, baseline_stop: int, baseline_events: int) -> bool:
        """After an interaction PreToolUse, wait for the menu to actually render.
        False when the turn ends, the session dies, or the interaction resolves
        (PostToolUse) before any menu shows."""
        end = _now() + MENU_RENDER_WAIT
        while _now() < end:
            if not self.pty.isalive() or self.watcher.count() > baseline_stop:
                return False
            if scr.classify_dialog(self.text()) is not None:
                return True
            if self._pending_interaction_event(baseline_events) is None:
                return False
            time.sleep(POLL)
        return False

    def _wait_turn_event(self, baseline_stop: int, baseline_events: int, *,
                         timeout: float | None = None,
                         stall_seconds: float = STALL_SECONDS,
                         progress_seconds: float | None = None,
                         progress_probe=None) -> dict:
        """Result-driven wait loop for one interactive turn (R1). Unlike
        _wait_for_signal (kept for run()), this also detects mid-turn
        interactions (AskUserQuestion / ExitPlanMode menus, unknown dialogs) and
        usage limits, and NEVER types into the TUI. Returns an internal dict

            {"outcome", "pending_tool", "usage_reset", "signal_lines"}

        with outcome one of "eof" | "completed" | "completed_idle" |
        "awaiting_menu" | "awaiting_plan_approval" | "awaiting_unknown_dialog" |
        "usage_limit" | "stalled" | "noisy_stagnation" | "deadline_exceeded" —
        the session layer maps these onto TurnOutcome.

        Three ways a turn that never ends still returns:
          stalled            silence -- no output for `stall_seconds`
          noisy_stagnation   output, but progress_sample() flat for
                             `progress_seconds` (None -> PROGRESS_SECONDS,
                             float("inf") -> off)
          deadline_exceeded  the turn budget (`timeout`; None -> the
                             DEFAULT_TURN_TIMEOUT, never "forever")."""
        budget = DEFAULT_TURN_TIMEOUT if timeout is None else timeout
        deadline = _now() + budget
        if progress_seconds is None:
            progress_seconds = PROGRESS_SECONDS
        last_sample = None
        last_change = _now()
        next_sample = _now()

        def result(outcome, pending_tool=None, usage_reset=None):
            return {"outcome": outcome, "pending_tool": pending_tool,
                    "usage_reset": usage_reset,
                    "signal_lines": self.watcher.count()}

        while True:
            # 1) session death
            if not self.pty.isalive():
                return result("eof")
            # 2) the Stop hook fired -> the turn completed
            if self.watcher.count() > baseline_stop:
                return result("completed")
            # 3) the turn budget -- checked EVERY tick, not only inside the
            # keep-waiting branch: with no deadline at all a screen that kept
            # repainting held this loop for 5.5 hours (autonomy record,
            # incident 3).
            now = _now()
            if now >= deadline:
                self.log("[wait] turn budget %.0fs exceeded" % budget)
                return result("deadline_exceeded")
            # 4) event fast path: an interaction tool started and has not
            # finished; require the menu to actually render before reporting.
            tool = self._pending_interaction_event(baseline_events)
            if tool is not None and self._confirm_menu_render(
                    baseline_stop, baseline_events):
                return result("awaiting_menu" if tool == "AskUserQuestion"
                              else "awaiting_plan_approval", pending_tool=tool)
            txt = self.text()
            if (tool is None and self._saw_notification(baseline_events)
                    and not scr.is_working(txt)
                    and scr.looks_like_question(self.screen.tail(12))):
                return result("awaiting_unknown_dialog")
            # 5) screen fallback (hooks are version-fragile). The SCREEN decides
            # here — this used to cross-check the transcript's pending tool_use,
            # but that row is not written until the interaction resolves, so the
            # check reported "unknown dialog" for every real question and a
            # hook miss meant nobody ever answered. classify_dialog is stricter
            # than the old menu-shape test anyway: a numbered list in a response
            # body carries neither dialog's wording (D2 fix carried forward).
            if not scr.is_working(txt) and self.idle_for() >= QUESTION_SETTLE:
                kind = scr.classify_dialog(txt)
                if kind == "question":
                    return result("awaiting_menu", pending_tool="AskUserQuestion")
                if kind == "plan_approval":
                    return result("awaiting_plan_approval",
                                  pending_tool="ExitPlanMode")
                if kind == "unknown":
                    return result("awaiting_unknown_dialog")
            # 6) usage limit
            if scr.is_usage_limit(txt):
                return result("usage_limit",
                              usage_reset=scr.parse_usage_reset(txt))
            # 7) the pre-existing adaptive tail, plus the progress reading
            if scr.is_working(txt) or self.idle_for() < stall_seconds:
                if now >= next_sample:
                    sample = self.progress_sample(progress_probe)
                    if sample != last_sample:
                        last_sample, last_change = sample, now
                        self.last_progress_ts = now
                    elif scr.is_working(txt) and now - last_change >= progress_seconds:
                        self.log("[wait] no progress for %.0fs while working "
                                 "-> noisy stagnation" % (now - last_change))
                        return result("noisy_stagnation")
                    next_sample = now + PROGRESS_POLL
                time.sleep(POLL)
                continue
            if scr.looks_idle(txt):
                return result("completed_idle")
            return result("stalled")

    def _needs_interrupt(self, txt: str) -> bool:
        # A WAITING dialog is not "working": the question widget's footer says
        # "Esc to cancel", never "esc to interrupt". Testing is_working alone
        # therefore returned True on the first poll and sent no ESC at all —
        # so a caller asking to fold a menu folded nothing and then typed its
        # next prompt into a widget that was still eating keys (measured with
        # calibrate_dialogs). Only the two IDENTIFIED dialogs count: "unknown"
        # is often just a numbered list in a finished response, and pressing
        # ESC at that for the whole timeout would slow every stall down.
        return (scr.is_working(txt)
                or scr.classify_dialog(txt) in ("question", "plan_approval"))

    def interrupt(self, timeout: float = 15.0) -> bool:
        """Interrupt whatever is holding the session (R2): press ESC until it is
        neither working nor showing a dialog it recognises. Standalone on
        purpose — _shutdown keeps its own proven loop. True when the session
        settled (or is already dead/idle)."""
        deadline = _now() + timeout
        while _now() < deadline:
            if not self.pty.isalive():
                return True
            if not self._needs_interrupt(self.text()):
                return True
            self.pty.write("\x1b")
            time.sleep(1.0)
        return not self.pty.isalive() or not self._needs_interrupt(self.text())

    # ------------------------------------------------ dialog navigation (menus)
    # The discipline is the /model picker's (_select_model_row): re-verify the
    # world before every key, move one arrow at a time and read the highlight
    # back, commit only after a last read shows the target row, then confirm
    # the dialog actually went away. Never a digit, never a blind Enter, never
    # a second Enter. Measured live on Claude Code 2.1.272 (calibrate_dialogs
    # --answer): arrows move ❯ in the AskUserQuestion widget and Enter resolves
    # it; the repaint can lag the key by more than KEY_VERIFY_DELAY, hence the
    # bounded poll (KEY_MOVE_TIMEOUT) instead of a single read.
    def _fail_dialog(self, stage: str, message: str, *, escape: bool) -> None:
        tail = self.screen.tail(scr.DIALOG_ROWS) if self.screen else ""
        if escape:
            self.pty.write(scr.ESCAPE)
            time.sleep(0.5)
        self.log("[dialog] FAILED at %s: %s" % (stage, message))
        raise DialogError(message, stage=stage, screen_tail=tail)

    def _read_dialog(self, kind: str):
        """(options, identity) for the identified dialog `kind` on screen, else
        (None, None). Options come from the kind-specific parser -- never from
        menu_options(tail), which would read a numbered list in a response
        body, or the plan body, as answerable rows."""
        txt = self.text()
        if scr.classify_dialog(txt) != kind:
            return None, None
        if kind == "question":
            dlg = scr.parse_question_dialog(txt)
            if dlg is None:
                return None, None
            return dlg.options, (dlg.question, tuple(o.label for o in dlg.options),
                                 dlg.header)
        opts = scr.plan_approval_options(txt)
        if not opts:
            return None, None
        return opts, (tuple(o.label for o in opts),)

    def _dialog_baseline(self, kind: str) -> dict:
        opts, ident = self._read_dialog(kind)
        tool = "AskUserQuestion" if kind == "question" else "ExitPlanMode"
        return {"stop": self.watcher.count(),
                "post": self._event_count("PostToolUse", tool),
                "tool": tool, "options": opts, "identity": ident}

    def _guard_dialog(self, kind: str, base: dict):
        """Re-verify before EVERY key; returns the current options."""
        if not self.pty.isalive():
            self._fail_dialog("eof", "session ended while the dialog was open",
                              escape=False)
        if self.watcher.count() > base["stop"]:
            self._fail_dialog("stop-raced", "a turn completed mid-navigation",
                              escape=False)
        if self._event_count("PostToolUse", base["tool"]) > base["post"]:
            self._fail_dialog("interaction-raced",
                              "the interaction resolved mid-navigation", escape=False)
        if scr.is_working(self.text()):
            self._fail_dialog("working-raced", "the session started working",
                              escape=False)
        opts, ident = self._read_dialog(kind)
        if opts is None:
            self._fail_dialog("dialog-vanished",
                              "the %s dialog is no longer on screen" % kind, escape=False)
        if ident != base["identity"]:
            self._fail_dialog("dialog-changed",
                              "a different %s dialog replaced the one being navigated"
                              % kind, escape=True)
        return opts

    def _navigate_dialog(self, kind: str, target_index: int, base: dict):
        """Walk the highlight onto option `target_index`, verifying every press."""
        budget = 2 * len(base["options"]) + NAV_STEP_PAD
        stuck = 0
        for _ in range(budget):
            self._wait_settled(quiet=DIALOG_SETTLE, timeout=3.0)
            opts = self._guard_dialog(kind, base)
            highlighted = [o for o in opts if o.highlighted]
            if len(highlighted) != 1:
                self._fail_dialog("highlight-unreadable",
                                  "%d rows are highlighted; cannot navigate"
                                  % len(highlighted), escape=True)
            if target_index not in {o.index for o in opts}:
                self._fail_dialog("option-missing",
                                  "option %d is not on the menu: %r"
                                  % (target_index, [o.label for o in opts]), escape=True)
            cur = highlighted[0]
            if cur.index == target_index:
                return cur
            self.pty.write(scr.CURSOR_DOWN if target_index > cur.index else scr.CURSOR_UP)

            def moved(before=cur.index):
                # The repaint can land well after the key (measured: >0.35s on a
                # freshly booted TUI), so poll rather than sample once.
                after_opts, _ = self._read_dialog(kind)
                after = [o for o in (after_opts or []) if o.highlighted]
                return len(after) == 1 and after[0].index != before

            self._wait(moved, timeout=KEY_MOVE_TIMEOUT, poll=KEY_VERIFY_DELAY)
            stuck = 0 if moved() else stuck + 1
            if stuck >= 2:
                self._fail_dialog("nav-ignored", "two arrow presses moved nothing",
                                  escape=True)
        self._fail_dialog("nav-budget", "never reached option %d within %d steps"
                          % (target_index, budget), escape=True)

    def _confirm_dialog_gone(self, kind: str, base: dict) -> bool:
        """After a commit key: did the dialog actually go away?

        True on any of: a Stop past the baseline, a PostToolUse for the tool
        past the baseline, the working spinner, or the dialog kind/identity no
        longer on screen for DIALOG_SETTLE. Presses nothing -- a second Enter
        after a late-taken first one would select something on the NEXT
        screen."""
        end = _now() + INJECT_VERIFY_TIMEOUT
        gone_since = None
        while _now() < end:
            if not self.pty.isalive() or self.watcher.count() > base["stop"]:
                return True
            if self._event_count("PostToolUse", base["tool"]) > base["post"]:
                return True
            txt = self.text()
            if scr.is_working(txt):
                return True
            _opts, ident = self._read_dialog(kind)
            if ident is None or ident != base["identity"]:
                gone_since = gone_since or _now()
                if _now() - gone_since >= DIALOG_SETTLE:
                    return True
            else:
                gone_since = None
            time.sleep(POLL)
        self.log("[dialog] %s still on screen %.0fs after the commit key"
                 % (kind, INJECT_VERIFY_TIMEOUT))
        return False

    def select_dialog_option(self, kind: str, target_index: int) -> bool:
        """Closed loop: arrow to `target_index`, re-verify, Enter, confirm gone.
        False when the menu stayed up after the Enter (never retried)."""
        base = self._dialog_baseline(kind)
        if base["options"] is None:
            self._fail_dialog("no-dialog", "no %s dialog is on screen" % kind,
                              escape=False)
        self._navigate_dialog(kind, target_index, base)
        # pre-commit gate: the last read before the committing key
        opts = self._guard_dialog(kind, base)
        cur = [o for o in opts if o.highlighted]
        if len(cur) != 1 or cur[0].index != target_index:
            self._fail_dialog("precommit", "highlight is %r, wanted option %d"
                              % ([o.index for o in cur], target_index), escape=True)
        self.log("[dialog] %s: selecting option %d (%s)"
                 % (kind, target_index, cur[0].label))
        self.pty.write(ENTER)
        return self._confirm_dialog_gone(kind, base)

    def _plan_menu_ready(self):
        """The approval menu's option 1, verified as the highlighted 'Yes …' row
        (the default under --dangerously-skip-permissions, measured)."""
        opts, _ident = self._read_dialog("plan_approval")
        if opts is None:
            self._fail_dialog("no-dialog", "no plan-approval menu is on screen",
                              escape=False)
        first = next((o for o in opts if o.index == 1), None)
        if first is None or not first.label.lower().startswith("yes"):
            self._fail_dialog("option-1", "option 1 is %r, expected a 'Yes, …' row"
                              % (first.label if first else None), escape=False)
        if not first.highlighted:
            self._fail_dialog("option-1", "option 1 is not the highlighted row; "
                              "refusing a blind Enter", escape=False)
        return first

    def approve_plan_menu(self) -> bool:
        """Verified approval: option 1 highlighted -> Enter -> menu gone."""
        first = self._plan_menu_ready()
        base = self._dialog_baseline("plan_approval")
        self.log("[plan] approving (option 1: %s)" % first.label)
        self.pty.write(ENTER)
        return self._confirm_dialog_gone("plan_approval", base)

    def reject_plan_menu(self) -> bool:
        """Select the 'revise' row (PLAN_REJECT_RE, fallback: the last row)."""
        opts, _ident = self._read_dialog("plan_approval")
        if opts is None:
            self._fail_dialog("no-dialog", "no plan-approval menu is on screen",
                              escape=False)
        target = next((o for o in opts if PLAN_REJECT_RE.search(o.label)), opts[-1])
        return self.select_dialog_option("plan_approval", target.index)

    def wait_input_idle(self, timeout: float = INJECT_VERIFY_TIMEOUT) -> bool:
        """After folding a dialog: wait for an idle input box we may type into."""
        return self._wait(lambda: scr.looks_idle(self.text())
                          and scr.classify_dialog(self.text()) not in
                          ("question", "plan_approval"), timeout=timeout)

    # ------------------------------------------------------------------ stall
    def _stall(self, idx: int) -> str:
        self.log("\n" + "=" * 70)
        self.log("[STALL] prompt %d/%d did not complete cleanly" % (idx, len(self.prompts)))
        self.log("--- current screen ---\n%s\n----------------------" % self.screen.tail(20))
        self.log("raw log: %s" % ", ".join(self._log_paths()))
        # Honor the explicit policy first. "skip" must skip regardless of whether
        # stdin is a TTY -- a headless caller (a parent harness) sets skip
        # precisely so a stall advances instead of killing the whole run. Only
        # "pause" needs a human, so it falls back to abort when we cannot prompt.
        if self.on_stall == "abort":
            self.log("[stall] aborting (policy=abort)")
            raise StallAbort()
        if self.on_stall == "skip":
            self.log("[stall] skipping to next prompt (policy=skip)")
            return "skip"
        interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())
        if not interactive:
            self.log("[stall] pause requested but stdin is non-interactive -> aborting")
            raise StallAbort()
        return self._interactive_stall()

    def _interactive_stall(self) -> str:
        while True:
            try:
                choice = input(
                    "\n[paused] (a)bort  (w)ait more  (s)kip  (t)akeover > "
                ).strip().lower()
            except EOFError:
                raise StallAbort()
            if choice == "a":
                raise StallAbort()
            if choice == "w":
                self.pty.last_output_ts = _now()
                return "wait"
            if choice == "s":
                return "skip"
            if choice == "t":
                self._takeover()
            else:
                print("choose a / w / s / t")

    def _takeover(self) -> None:
        print("\n--- TAKEOVER: each line is sent to Claude; ':resume' to return ---")
        self.pty.mirror = True
        try:
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip() == ":resume":
                    break
                self.pty.write(line + ENTER)
        finally:
            self.pty.mirror = False

    # ------------------------------------------------------------------ run
    def _process_prompt(self, idx: int, text: str) -> str:
        if self.mode == "plan":
            return self._process_prompt_plan(idx, text)
        return self._process_prompt_bypass(idx, text)

    def _process_prompt_bypass(self, idx: int, text: str) -> str:
        baseline = self._send_prompt(idx, text)
        if not self._confirm_working(baseline):
            action = self._stall(idx)
            if action == "skip":
                return "skipped"
        while True:
            outcome = self._wait_for_signal(baseline)
            if outcome in ("signal", "idle-fallback"):
                break
            if outcome == "eof":
                return "eof"
            action = self._stall(idx)
            if action == "skip":
                return "skipped"
            # "wait" -> loop and keep waiting (stall timer was reset)
        self._wait_settled()
        # Only second-guess completion on an idle-fallback (no Stop-hook signal,
        # so genuinely uncertain). A real "signal" means the turn ended cleanly;
        # a numbered list on screen is then the response body, not a pending menu
        # -- otherwise every "reply with a numbered list" answer false-trips this
        # guard and (headless) gets dropped or aborts the run.
        if outcome == "idle-fallback" and scr.looks_like_question(self.screen.tail(12)):
            self.log("[guard] question/menu detected after idle-fallback turn %d" % idx)
            if self._stall(idx) == "skip":
                return "skipped"
        return outcome

    def _process_prompt_plan(self, idx: int, text: str) -> str:
        # Each prompt is planned then auto-approved. After a previous approval the
        # session is in auto mode, so re-enter plan mode first.
        if not self._ensure_mode("plan"):
            if self._stall(idx) == "skip":
                return "skipped"
        baseline = self._send_prompt(idx, text)
        if not self._confirm_working(baseline):
            if self._stall(idx) == "skip":
                return "skipped"
        # 1) wait for the plan-approval menu (or a direct end, or a stall)
        while True:
            res = self._wait_plan_ready(baseline)
            if res == "approval":
                break
            if res in ("signal", "idle-fallback"):
                # turn ended without an approval menu (e.g. a pure question)
                self.log("[plan %d] ended without approval menu (%s)" % (idx, res))
                self._wait_settled()
                return res
            if res == "eof":
                return "eof"
            if self._stall(idx) == "skip":
                return "skipped"
        # 2) auto-approve: select option 1 ("Yes, and bypass permissions" when
        # launched with --dangerously-skip-permissions, else "...use auto mode").
        # Verified, not blind: option 1 must be the highlighted "Yes" row and the
        # menu must fold after the Enter (approve_plan_menu).
        self.log("[plan %d] plan ready -> auto-approving (option 1: proceed)" % idx)
        approve_base = self.watcher.count()
        try:
            approved = self.approve_plan_menu()
        except DialogError as e:
            self.log("[plan %d] approval refused: %s" % (idx, e))
            approved = False
        if not approved and self._stall(idx) == "skip":
            return "skipped"
        # 3) the execution turn now runs hands-off and DOES fire the Stop hook
        while True:
            res = self._wait_for_signal(approve_base)
            if res in ("signal", "idle-fallback"):
                self._wait_settled()
                return "approved+" + res
            if res == "eof":
                return "eof"
            if self._stall(idx) == "skip":
                return "skipped"

    def _capture_response(self, idx: int | None = None) -> dict:
        """Best-effort clean response for turn `idx` from the live JSONL Claude
        writes as it goes; falls back to the screen tail if the transcript is not
        (yet) available. idx=None returns the LAST transcript turn (R4) — a
        session handle derives its turn index from the live transcript rather
        than a fixed prompt list. Returns {"response", "tools"}."""
        try:
            path = tx.find_transcript(self.session_id)
            if path:
                turns = tx.parse_transcript(path)
                if idx is None:
                    if turns:
                        t = turns[-1]
                        return {"response": t["response"], "tools": t["tools"]}
                else:
                    for t in turns:
                        if t["index"] == idx:
                            return {"response": t["response"], "tools": t["tools"]}
        except Exception:
            pass
        return {"response": self.screen.tail(40) if self.screen else "", "tools": []}

    def _emit_turn(self, rec: dict) -> None:
        if not self.on_turn:
            return
        try:
            self.on_turn(dict(rec))
        except Exception as e:
            self.log("[on_turn] callback error: %r" % e)

    def run(self) -> dict:
        """Drive the whole prompt sequence. Returns a structured summary so a
        calling app (e.g. a self-improvement loop) can react to outcomes:

            {"mode", "session_id", "workdir", "transcript", "total", "completed",
             "aborted",
             "results": [{"index", "status", "signal_lines", "response", "tools"},
                         ...]}

        `response` is the turn's clean assistant text (from the JSONL transcript
        when available, else the screen tail); `tools` lists the tool names the
        assistant used that turn (e.g. AskUserQuestion / ExitPlanMode)."""
        self._prepare()
        self._spawn()
        results: list[dict] = []
        aborted = False
        try:
            self._handle_trust()
            self._wait_initial_idle()
            for i, prompt in enumerate(self.prompts, 1):
                try:
                    status = self._process_prompt(i, prompt)
                except StallAbort:
                    self.log("[run] aborted by stall policy/user at prompt %d" % i)
                    cap = self._capture_response(i)
                    rec = {"index": i, "status": "aborted",
                           "signal_lines": self.watcher.count(),
                           "response": cap["response"], "tools": cap["tools"]}
                    results.append(rec)
                    self._emit_turn(rec)
                    aborted = True
                    break
                cap = ({"response": "", "tools": []} if status == "eof"
                       else self._capture_response(i))
                rec = {"index": i, "status": status,
                       "signal_lines": self.watcher.count(),
                       "response": cap["response"], "tools": cap["tools"]}
                results.append(rec)
                self.log("[turn %d/%d] status=%s signal_lines=%d"
                         % (i, len(self.prompts), status, self.watcher.count()))
                self._emit_turn(rec)
                if status == "eof":
                    self.log("[run] session ended early; stopping")
                    break
            else:
                self.log("[complete] all %d prompts processed" % len(self.prompts))
        finally:
            self._finalize()
        completed = sum(1 for r in results if str(r["status"]).startswith(("signal", "approved", "idle")))
        return {
            "mode": self.mode,
            "session_id": self.session_id,
            "workdir": str(self.workdir),
            "transcript": tx.find_transcript(self.session_id),
            "total": len(self.prompts),
            "completed": completed,
            "aborted": aborted,
            "results": results,
        }

    # ------------------------------------------------------------------ teardown
    def _finalize(self) -> None:
        try:
            self._shutdown()
        except Exception as e:
            self.log("[shutdown] %r" % e)
        self._copy_transcript()
        if self.pty:
            self.pty.close()  # join reader thread + close log
        self.log("[runtime] artifacts in %s" % self.runtime)

    def _shutdown(self) -> None:
        if not self.pty or not self.pty.isalive():
            return
        # Clean exit is tricky: after the Stop hook fires Claude runs post-turn
        # auto-memory ("running stop hook" / "Churned for 2s") with "esc to
        # interrupt" in the footer, and a Ctrl-C during that interrupts the work
        # instead of exiting. So: interrupt (ESC) any in-progress work until the
        # session is genuinely idle (not working AND silent), THEN send a tight
        # Ctrl-C pair. The confirm window is short (verified: 0.3s gap exits, 0.8s
        # does not), so the two presses must be close together.
        self.log("[shutdown] settling then exiting via Ctrl-C")
        deadline = _now() + 30.0
        while _now() < deadline and self.pty.isalive():
            if scr.is_working(self.text()) or self.idle_for() < 1.2:
                self.pty.write("\x1b")  # ESC: interrupt post-turn work
                time.sleep(1.0)
                continue
            self.pty.write("\x03")
            time.sleep(0.25)
            self.pty.write("\x03")
            if self._wait(lambda: not self.pty.isalive(), timeout=3.0):
                self.log("[shutdown] clean exit")
                return
        if self.pty.isalive():
            self.log("[shutdown] Ctrl-C did not exit; forcing terminate")
            self.pty.terminate()

    def _copy_transcript(self) -> None:
        # The full visual record is always the raw PTY log. Claude also writes a
        # clean JSONL transcript; on the current Claude Code these PTY-driven
        # sessions DO persist it, so we copy it beside the other artifacts (and
        # the summary's "transcript" field points a harness at it to parse).
        self.log("[transcript] full PTY record: %s" % ", ".join(self._log_paths()))
        src = tx.find_transcript(self.session_id)
        if not src:
            self.log("[transcript] (no clean JSONL persisted by Claude)")
            return
        dest = self.runtime / ("transcript-%s.jsonl" % self.session_id)
        try:
            shutil.copyfile(src, dest)
            self.log("[transcript] clean JSONL: %s" % dest)
        except Exception as e:
            self.log("[transcript] JSONL copy failed: %r" % e)


def run_session(
    prompts,
    workdir,
    *,
    mode: str = "bypass",
    app_dir=None,
    on_stall: str = "pause",
    claude_exe=None,
    extra_args=None,
    send_mode: str = "paste",
    hook_form: str = "args",
    model=None,
    effort=None,
    logger=None,
    on_turn=None,
) -> dict:
    """Run a sequence of prompts through one fresh Claude Code session and return
    a structured summary. This is the entry point for a calling app.

        from step2step.claude import run_session
        result = run_session(prompts, workdir, mode="plan")   # or mode="bypass"

    mode="bypass": hands-off direct execution (--dangerously-skip-permissions).
    mode="plan":   plan each prompt and auto-approve it (launch with
                   --dangerously-skip-permissions, switch to plan mode via
                   shift+tab, then select option 1 with Enter -- "Yes, and bypass
                   permissions" for this launch flag).

    model:      launch-time model for the session (--model). An alias ("haiku",
                "opus", "fable") or a full name ("claude-opus-5").
    effort:     launch-time reasoning effort (--effort), one of EFFORT_LEVELS
                (low|medium|high|xhigh|max). Without it the session inherits the
                user's global effortLevel, because child_env() scrubs CLAUDE*.
    extra_args: extra CLI args forwarded to `claude` (e.g. ["--model", "haiku"]).
                A --model/--effort here WINS over the model=/effort= arguments.
    on_turn:    optional callback invoked after each turn with a dict
                {index, status, response, tools, signal_lines}.
    on_stall:   "pause" | "skip" | "abort". A non-interactive (headless) caller
                should use "skip" or "abort" -- "pause" cannot prompt and falls
                back to abort.
    """
    if app_dir is None:
        app_dir = REPO_ROOT
    return Runner(
        workdir=workdir,
        prompts=list(prompts),
        app_dir=app_dir,
        mode=mode,
        on_stall=on_stall,
        claude_exe=claude_exe,
        extra_args=extra_args,
        send_mode=send_mode,
        hook_form=hook_form,
        model=model,
        effort=effort,
        logger=logger,
        on_turn=on_turn,
    ).run()
