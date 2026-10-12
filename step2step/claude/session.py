"""SessionHandle: incremental, interactive ownership of one Claude Code session.

Where Runner.run() drives a FIXED prompt list to completion, a SessionHandle
keeps the session alive between turns so a calling harness can decide prompt
k+1 after seeing response k, detect mid-turn interactions (AskUserQuestion /
ExitPlanMode menus, unknown dialogs), and answer them. It composes the SAME
Runner primitives (_prepare/_spawn/_handle_trust/_wait_initial_idle/
_send_prompt/_wait_turn_event/_capture_response/_finalize) — TUI knowledge
stays in this layer's modules (screen/hooks/transcript), never in callers.

    handle = SessionHandle.start(workdir="proj", mode="bypass")
    result = handle.run_turn("build the thing")        # TurnResult
    if result.outcome is TurnOutcome.AWAITING_PLAN_APPROVAL:
        handle.approve_plan()
        result = handle.wait_turn(pending)             # same PendingTurn
    handle.stop()

Threading rule: one owning thread per handle — every write/wait happens on it.

This handle owns a spawned Claude session. The shared
step2step.terminal.attach.session.ExternalSession provides console I/O for an
already-running process, driven by the separate Claude AttachRunner.
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass

from . import screen as scr
from . import transcript as tx
from .runner import (DEFAULT_TURN_TIMEOUT, EFFORT_LEVELS, ENTER, ModelControlError,
                     Runner, STALL_SECONDS, DialogError,
                     KEY_VERIFY_DELAY, INJECT_VERIFY_TIMEOUT)  # noqa: F401 -- re-exported
from .screen import MenuOption, ModelConfirmation, ModelDialog, ModelRow
from ..paths import REPO_ROOT
from ..contracts import (
    SessionState, TurnOutcome, PendingInteraction, TurnResult, PendingTurn,
    ModelState as BaseModelState, ControlError, UnsupportedOperation,
)


# Watchdog poll period (step2step.claude.watchdog.SessionWatchdog).
HEALTH_POLL = 2.0

_AWAITING = (TurnOutcome.AWAITING_MENU, TurnOutcome.AWAITING_PLAN_APPROVAL,
             TurnOutcome.AWAITING_UNKNOWN_DIALOG)


@dataclass
class ModelState(BaseModelState):
    """Claude model aliases and display labels retain their matching behavior."""

    def matches(self, target: str) -> bool:
        return any(scr.model_matches(v, target)
                   for v in (self.model, self.requested) if v)


class SessionHandle:
    """One live interactive session. Construct via start(); the __init__ takes
    an already-built Runner so tests can inject a fake."""

    capabilities = frozenset({"turns", "plan", "approve_plan", "interrupt",
                              "models", "effort", "screen", "transcript"})

    @property
    def session_id(self) -> str:
        return self._runner.session_id

    def __init__(self, runner: Runner, *, role: str | None = None,
                 model: str | None = None, effort: str | None = None,
                 snapshot_dir=None, turn_timeout: float = DEFAULT_TURN_TIMEOUT):
        if not isinstance(turn_timeout, (int, float)) or not turn_timeout > 0:
            raise ValueError("turn_timeout must be a positive number of seconds, "
                             "got %r" % (turn_timeout,))
        self._runner = runner
        self.role = role  # metadata only; prompt injection is the harness's job
        self.model = model
        self.effort = effort
        self.snapshot_dir = pathlib.Path(snapshot_dir) if snapshot_dir else None
        # The budget wait_turn(timeout=None) applies. A handle-level default so a
        # caller that forgets the argument still gets a finite wait.
        self.turn_timeout = float(turn_timeout)
        self.turn_count = 0
        self.usage_limited = False
        self.system_prompt_append: str | None = None
        self.last_outcome: str | None = None
        self._stopped_at: float | None = None
        self._watchdog = None
        self._started_at = time.time()
        # Model/effort bookkeeping. `_model_busy` is a flag, not a lock: a lock
        # here could wedge the owning thread, and the owning-thread rule already
        # makes real contention a bug worth surfacing rather than serialising.
        self._model_busy = False
        self._last_confirmation = None
        self._model_scope = "launch" if (model or effort) else None

    # ------------------------------------------------------------- lifecycle
    @classmethod
    def start(cls, *, workdir, role: str | None = None,
              system_prompt_append: str | None = None,
              model: str | None = None, effort: str | None = None,
              extra_args=None, mode: str = "bypass", app_dir=None,
              claude_exe=None, logger=None, snapshot_dir=None,
              turn_timeout: float = DEFAULT_TURN_TIMEOUT) -> "SessionHandle":
        """Spawn and boot a fresh session (trust dialog handled, input box
        idle). mode='plan' does NOT pre-enter plan mode — like Runner, plan is
        entered per prompt (send_prompt), because approval returns the TUI to
        bypass.

        `model` and `effort` become --model / --effort. Setting them at LAUNCH is
        the cheap, deterministic path: a mid-session change forces the whole
        conversation to be re-read on the next turn.

        `turn_timeout` is the per-turn budget wait_turn() applies when its own
        `timeout` is None. It defaults to DEFAULT_TURN_TIMEOUT and cannot be
        disabled -- a turn that never ends must still return."""
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ValueError("effort must be one of %s, got %r"
                             % (", ".join(EFFORT_LEVELS), effort))
        args = list(extra_args or [])
        if system_prompt_append:
            args += ["--append-system-prompt", system_prompt_append]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]
        runner = Runner(
            workdir=workdir, prompts=[], app_dir=app_dir or REPO_ROOT,
            mode=mode, on_stall="skip", claude_exe=claude_exe,
            extra_args=args, logger=logger, event_hooks=True,
        )
        handle = cls(runner, role=role, model=model, effort=effort,
                     snapshot_dir=snapshot_dir, turn_timeout=turn_timeout)
        handle.system_prompt_append = system_prompt_append
        checks = runner.preflight()
        for w in checks.get("warnings", ()):
            runner.log("[preflight] WARNING %s" % w)
        if checks.get("fatal"):
            raise ControlError("session start refused: " + "; ".join(checks["fatal"]))
        runner._prepare()
        runner._spawn()
        runner._handle_trust()
        runner._wait_initial_idle()
        handle.snapshot()
        return handle

    # ------------------------------------------------------------- rehydration
    @staticmethod
    def load_snapshot(path) -> dict:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_snapshot(cls, snap, *, logger=None, app_dir=None, snapshot_dir=None,
                      claude_exe=None, turn_timeout=None) -> "SessionHandle":
        """Relaunch a FRESH session with a snapshot's launch spec (workdir,
        mode, role, model, effort, system prompt, extra args) -- the
        extension spec's default "fresh" rehydration. The old child is not
        resumed (`claude --resume` is uncalibrated) and its conversation is not
        replayed; the harness re-primes from its own state. `snap` is the
        dict snapshot() returned or a path to the file it wrote."""
        if not isinstance(snap, dict):
            snap = cls.load_snapshot(snap)
        extra = _strip_flags(list(snap.get("extra_args") or []),
                             ("--model", "--effort", "--append-system-prompt"))
        return cls.start(
            workdir=snap["workdir"], role=snap.get("role"),
            system_prompt_append=snap.get("system_prompt_append"),
            model=snap.get("model"), effort=snap.get("effort"),
            extra_args=extra, mode=snap.get("mode") or "bypass",
            app_dir=app_dir or snap.get("app_dir"),
            claude_exe=claude_exe or snap.get("claude_exe"), logger=logger,
            snapshot_dir=snapshot_dir or snap.get("snapshot_dir"),
            turn_timeout=(turn_timeout or snap.get("turn_timeout")
                          or DEFAULT_TURN_TIMEOUT),
        )

    def watch(self, on_event, **kw):
        """Start a read-only SessionWatchdog for this handle (see
        step2step.claude.watchdog); stop() stops it."""
        from .watchdog import SessionWatchdog
        self._watchdog = SessionWatchdog(self, on_event, **kw).start()
        return self._watchdog

    def stop(self, *, force: bool = False) -> None:
        """Settle-then-Ctrl-C via the Runner teardown; force additionally
        terminates the PTY child and sweeps its process tree first."""
        wd = getattr(self, "_watchdog", None)
        if wd is not None:
            wd.stop()
        if force and self._runner.pty:
            self._runner.pty.terminate()
        self._runner._finalize()
        self._stopped_at = time.time()
        self._autosnapshot()

    # ------------------------------------------------------------- prompts
    def send_prompt(self, text: str) -> PendingTurn:
        """Bracket-paste `text` + Enter, then CONFIRM the turn started.

        Baselines are captured pre-submit so even an instant Stop/interaction
        cannot race them. The confirmation (Runner._confirm_working) is what
        the batch path always had and this path lacked: a paste or Enter the
        TUI swallows leaves the screen idle, and an unconfirmed idle turn used
        to come back as COMPLETED_IDLE carrying the PREVIOUS turn's response.
        The evidence rides on the PendingTurn (`submitted`, `baseline_turns`,
        `transcript_seen`) for wait_turn to judge.

        Precondition: an idle input box (an unidentified numbered list in a
        finished response is fine; a working session, a waiting dialog or the
        usage banner is not -- answer or interrupt first). Sending over the
        previous turn's post-turn work would make its spinner read as "our
        turn started"."""
        if not self.is_alive():
            raise ControlError("send_prompt: the session is not alive")
        self._runner._wait_settled()
        state = self.peek_state()
        if state not in (SessionState.IDLE, SessionState.AWAITING_UNKNOWN_DIALOG):
            raise ControlError("send_prompt needs an idle session, not %s -- answer "
                               "or interrupt first" % state.value)
        if self._runner.mode == "plan":
            self._runner._ensure_mode("plan")
        turns0 = self.transcript_turns()
        transcript_seen = bool(turns0) or self._find_transcript() is not None
        baseline_events = self._runner.events.count() if self._runner.events else 0
        baseline_stop = self._runner._send_prompt(self.turn_count + 1, text)
        submitted = bool(self._runner._confirm_working(baseline_stop, baseline_events))
        if not submitted:
            self._runner.log("[send] submission NOT confirmed (%s)"
                             % getattr(self._runner, "confirm_reason", None))
        return PendingTurn(baseline_stop=baseline_stop,
                           baseline_events=baseline_events,
                           prompt=text, submitted_at=time.time(),
                           submitted=submitted, baseline_turns=len(turns0),
                           transcript_seen=transcript_seen)

    def _find_transcript(self) -> str | None:
        try:
            return tx.find_transcript(self._runner.session_id)
        except Exception:
            return None

    @staticmethod
    def _idle_turn_is_real(pending: PendingTurn, turns: list[dict]) -> bool:
        """COMPLETED_IDLE has no Stop evidence; decide from the transcript.

        The transcript grew past the pre-submit count -> a turn ran. No
        transcript to consult at all (none existed at submit and none exists
        now) -> trust the submit confirmation. Anything else -- a transcript
        that did not grow -- means the idle screen is the OLD turn's."""
        if turns and len(turns) > pending.baseline_turns:
            return True
        if not turns and not pending.transcript_seen:
            return pending.submitted
        return False

    def wait_turn(self, pending: PendingTurn, *, timeout: float | None = None,
                  stall_seconds: float = STALL_SECONDS,
                  progress_seconds: float | None = None,
                  progress_probe=None) -> TurnResult:
        """Result-driven wait (runner R1). AWAITING_* results do not consume
        the turn — respond, then call wait_turn again with the same
        PendingTurn.

        `timeout=None` means this handle's `turn_timeout` (never forever).
        `progress_seconds`/`progress_probe` tune noisy-stagnation detection
        (see Runner.progress_sample); a harness passes e.g. a worktree digest
        as the probe so "files changed" counts as progress."""
        budget = self.turn_timeout if timeout is None else timeout
        res = self._runner._wait_turn_event(
            pending.baseline_stop, pending.baseline_events,
            timeout=budget, stall_seconds=stall_seconds,
            progress_seconds=progress_seconds, progress_probe=progress_probe)
        outcome = TurnOutcome(res["outcome"])
        interaction = None
        response = ""
        tools: list[str] = []
        turn_index = self.turn_count + 1
        if outcome in (TurnOutcome.COMPLETED, TurnOutcome.COMPLETED_IDLE):
            self._runner._wait_settled()
            turns = self.transcript_turns()
            if (outcome is TurnOutcome.COMPLETED_IDLE
                    and not self._idle_turn_is_real(pending, turns)):
                # Idle, no Stop, and no evidence a turn ran: the prompt was
                # swallowed. Reporting the previous response as this turn's
                # is the "failure that looks like success" -- refuse it.
                self._runner.log("[wait] idle without a Stop signal and no evidence "
                                 "the prompt was submitted -> submit_failed")
                outcome = TurnOutcome.SUBMIT_FAILED
            else:
                cap = self._runner._capture_response(None)
                response, tools = cap["response"], cap["tools"]
                if turns:
                    turn_index = turns[-1]["index"]
                self.turn_count = turn_index
        elif outcome in _AWAITING:
            interaction = self.pending_interaction(tool_hint=res["pending_tool"])
        elif outcome is TurnOutcome.USAGE_LIMIT:
            self.usage_limited = True
        if outcome not in _AWAITING:
            # A consumed turn (or a terminal failure) is worth persisting: the
            # snapshot written at start() alone carried turn_count=0 and no
            # transcript, so nothing downstream could map a unit to its session.
            self.last_outcome = outcome.value
            self._autosnapshot()
        return TurnResult(outcome=outcome, turn_index=turn_index,
                          response=response, tools=tools, pending=interaction,
                          signal_lines=res["signal_lines"],
                          usage_reset_text=res["usage_reset"],
                          started_at=pending.submitted_at, ended_at=time.time(),
                          raw=res)

    def run_turn(self, text: str, **kw) -> TurnResult:
        return self.wait_turn(self.send_prompt(text), **kw)

    # ------------------------------------------------------------- inspection
    def peek_state(self) -> SessionState:
        """Non-blocking state classification from screen + transcript."""
        if not self.is_alive():
            return SessionState.DEAD
        txt = self._runner.text()
        if scr.is_working(txt):
            return SessionState.WORKING
        if scr.is_usage_limit(txt):
            return SessionState.USAGE_LIMITED
        # Screen-only classification: while an interaction waits, its tool_use is
        # not in the transcript at all, so asking there would call every real
        # question an unknown dialog.
        kind = scr.classify_dialog(txt)
        if kind == "question":
            return SessionState.AWAITING_MENU
        if kind == "plan_approval":
            return SessionState.AWAITING_PLAN_APPROVAL
        if kind == "unknown":
            return SessionState.AWAITING_UNKNOWN_DIALOG
        if scr.looks_idle(txt):
            return SessionState.IDLE
        return (SessionState.STALLED
                if self._runner.idle_for() >= STALL_SECONDS
                else SessionState.STARTING)

    def pending_interaction(self, tool_hint: str | None = None
                            ) -> PendingInteraction | None:
        """The interaction currently waiting, or None.

        The SCREEN classifies it and, while it waits, also supplies the content:
        the tool_use carrying the question is not written to the transcript
        until the interaction resolves, so a live caller that trusted the
        transcript got `questions == []` every time. The transcript is still
        preferred WHEN it has something (verbatim tool input beats a scrape) —
        `source` says which one a caller is holding. `tool_hint` (from the event
        fast path) still wins the classification when it is available."""
        text = self._runner.text() if self._runner.screen else ""
        tail = self.screen_tail()
        menu = scr.menu_options(self.screen_tail(scr.DIALOG_ROWS))
        on_screen = scr.classify_dialog(text)
        pending = self._runner._pending_transcript_tool()
        name = ((pending or {}).get("name") or tool_hint
                or {"question": "AskUserQuestion",
                    "plan_approval": "ExitPlanMode"}.get(on_screen))
        if name is None and not menu:
            return None
        inp = (pending or {}).get("input") or {}
        source = "transcript" if pending else "screen"
        if name == "AskUserQuestion":
            kind, plan = "ask_user_question", None
            questions = list(inp.get("questions") or [])
            if not questions:
                dialog = scr.parse_question_dialog(text)
                if dialog is not None:
                    questions = dialog.as_tool_input()["questions"]
                    source = "screen"
        elif name == "ExitPlanMode":
            kind, questions, plan = "plan_approval", [], inp.get("plan")
        else:
            kind, questions, plan = "unknown_dialog", [], None
        return PendingInteraction(kind=kind,
                                  tool_use_id=(pending or {}).get("id"),
                                  questions=questions, plan=plan,
                                  menu=menu, screen_tail=tail, source=source)

    def screen_tail(self, n: int = 20) -> str:
        return self._runner.screen.tail(n) if self._runner.screen else ""

    def transcript_turns(self) -> list[dict]:
        try:
            return tx.parse_transcript(tx.find_transcript(self._runner.session_id))
        except Exception:
            return []

    # ------------------------------------------------------------- answering
    # Every method here is a verified closed loop over the screen (see the
    # runner's dialog-navigation block): arrows only, read-back after each
    # key, commit only on a verified highlight, then confirm the dialog went
    # away. Failures raise DialogError (a ControlError) with the stage and the
    # screen tail; nothing is ever typed blind. answer_menu and approve_plan
    # were verified live on 2.1.272 (`python -m step2step.claude.calibrate_dialogs
    # <dir> --answer`); reject_plan and answer_menu_text share the same loop but
    # their post-Enter screens have not been captured yet (V6).
    def _question_dialog(self):
        dlg = scr.parse_question_dialog(self._runner.text())
        if dlg is None:
            raise ControlError("no AskUserQuestion widget is waiting")
        return dlg

    def _dialog_fail(self, stage: str, message: str) -> None:
        """ESC whatever is left of the dialog and raise; the evidence rides on
        the error so a harness can escalate with the screen attached."""
        tail = self.screen_tail(scr.DIALOG_ROWS)
        self._runner.pty.write(scr.ESCAPE)
        time.sleep(0.2)
        self._runner.log("[dialog] FAILED at %s: %s" % (stage, message))
        raise DialogError(message, stage=stage, screen_tail=tail)

    def answer_questions(self, answers, *, request_id=None) -> None:
        """Answer the waiting question by option label or free text.

        Single-question widgets only. `answers` maps the one question (any
        key -- the widget shows no ids) to a label (or a one-element list);
        a label matching a model-authored option selects it, anything else is
        typed via the widget's free-text row. Multi-question (tab bar)
        widgets raise UnsupportedOperation: their Submit tab has no readable
        focus state, so a verified loop cannot be built until calibrated."""
        dlg = self._question_dialog()
        if len(dlg.tabs) > 1:
            raise UnsupportedOperation(
                "multi-question AskUserQuestion widgets are not calibrated (%d tabs); "
                "answer_menu/answer_menu_text handle a single question" % len(dlg.tabs))
        if not isinstance(answers, dict) or len(answers) != 1:
            raise ValueError("answers must map exactly one question to one answer")
        value = next(iter(answers.values()))
        if isinstance(value, (list, tuple)):
            if len(value) != 1:
                raise ValueError("one answer per question; multi-select is not supported")
            value = value[0]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("the answer must be a nonempty string")
        wanted = value.strip().casefold()
        for opt in dlg.model_options:
            if opt.label.strip().casefold() == wanted:
                self.answer_menu(opt.index)
                return
        self.answer_menu_text(value)

    def answer_approval(self, decision, *, request_id=None) -> None:
        raise UnsupportedOperation("Claude command/file approval control is not calibrated")

    def answer_menu(self, option_index: int) -> None:
        """Select option `option_index` (1-based, as printed) on the waiting
        AskUserQuestion widget. Verified closed loop; raises DialogError when
        the highlight cannot be read/moved or the Enter did not take."""
        dlg = self._question_dialog()
        if option_index not in {o.index for o in dlg.options}:
            raise ValueError("option_index %r is not on the menu: %r"
                             % (option_index, [o.label for o in dlg.options]))
        if not self._runner.select_dialog_option("question", option_index):
            self._dialog_fail("commit-ignored",
                              "the question widget stayed up after Enter")

    def answer_menu_text(self, text: str) -> None:
        """Answer the waiting question with free text via its "Type something"
        row: select that row (verified), wait for the input, bracket-paste
        `text`, Enter, and confirm the widget resolved."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be nonempty")
        dlg = self._question_dialog()
        row = next((o for o in dlg.options
                    if o.label.strip().rstrip(".").lower() == scr.QUESTION_BUILTIN_LABELS[0]),
                   None)
        if row is None:
            raise ControlError("the widget offers no free-text row: %r"
                               % [o.label for o in dlg.options])
        base = self._runner._dialog_baseline("question")
        if not self._runner.select_dialog_option("question", row.index):
            self._dialog_fail("commit-ignored",
                              "the question widget stayed up after Enter")
        if not self._runner.wait_input_idle():
            self._dialog_fail("no-input",
                              "no input box appeared after selecting the free-text row")
        self._runner._send_prompt(self.turn_count + 1, text)
        if not self._runner._confirm_dialog_gone("question", base):
            self._dialog_fail("text-ignored",
                              "the widget did not resolve after the free-text answer")

    def approve_plan(self) -> bool:
        """Approve the pending plan -- verified, never a blind Enter.

        Requires the approval menu on screen with option 1 ("Yes, …") as the
        highlighted row (the default under --dangerously-skip-permissions,
        measured), presses Enter once, then confirms the menu folded. The turn
        is NOT consumed: call wait_turn() again with the same PendingTurn (no
        Stop fired while the menu was up). False means the menu stayed up
        (an Enter that did not take is never repeated blindly); DialogError
        when there is no approval menu or option 1 is not the 'Yes' row."""
        return self._runner.approve_plan_menu()

    def reject_plan(self, feedback: str) -> PendingTurn:
        """Send the plan back with `feedback`: select the revise row ("Tell
        Claude what to change" / "No, keep planning", fallback the last row),
        wait for the input box, then submit `feedback` as a new turn. Returns
        the NEW PendingTurn (the old one is dead)."""
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("feedback must be nonempty")
        if not self._runner.reject_plan_menu():
            self._dialog_fail("commit-ignored", "the approval menu stayed up after Enter")
        if not self._runner.wait_input_idle():
            self._dialog_fail("no-input", "no input box appeared after rejecting the plan")
        return self.send_prompt(feedback)

    def interrupt(self) -> bool:
        """ESC any in-progress work or identified dialog until the screen
        settles (runner R2). True when it settled or the session is dead;
        False when the ESCs did not take -- never paste over a False."""
        return bool(self._runner.interrupt())

    # ------------------------------------------------------------- health
    def is_alive(self) -> bool:
        return bool(self._runner.pty and self._runner.pty.isalive())

    def health(self) -> dict:
        return {
            "alive": self.is_alive(),
            "state": self.peek_state().value,
            "idle_for": self._runner.idle_for() if self._runner.pty else None,
            "mode": (scr.current_mode(self._runner.text())
                     if self._runner.screen else None),
            "write_errors": (self._runner.pty.write_errors
                             if self._runner.pty else 0),
            "turn_count": self.turn_count,
            "usage_limited": self.usage_limited,
            # Seconds since the progress sample last changed during a wait, or
            # None before the first reading. Distinct from idle_for: a session
            # can print for hours without this moving (noisy stagnation).
            "no_progress_for": self._no_progress_for(),
        }

    def _no_progress_for(self) -> float | None:
        ts = getattr(self._runner, "last_progress_ts", None)
        return None if ts is None else max(0.0, time.monotonic() - ts)

    def ensure_mode(self, target: str) -> bool:
        return self._runner._ensure_mode(target)

    # ------------------------------------------------------- model / effort
    def model_state(self, *, refresh: bool = False) -> ModelState:
        """Best-known model/effort for this session, by descending authority:

        1. the transcript's last assistant record -- what the last turn ACTUALLY
           ran on (a settings override or an org effort cap can make this differ
           from what we asked for),
        2. the last confirmation line this handle verified,
        3. the launch flags.

        `refresh=True` also reads the working spinner, which only shows an
        effort while a turn is running."""
        now = time.time()
        try:
            actual = tx.last_model_effort(tx.find_transcript(self._runner.session_id))
        except Exception:
            actual = None
        if actual and actual.get("model"):
            effort = actual.get("effort")
            if effort is None and refresh:
                effort = scr.current_effort(self._runner.text())
            return ModelState(model=actual["model"], effort=effort,
                              requested=self.model,
                              scope=self._model_scope, source="transcript",
                              observed_at=now)
        if self._last_confirmation is not None:
            c = self._last_confirmation
            return ModelState(model=c.model, effort=c.effort,
                              requested=self.model, scope=self._model_scope,
                              source="confirmation", observed_at=now, raw=c.line)
        return ModelState(model=self.model, effort=self.effort,
                          requested=self.model, scope="launch",
                          source="launch-flags", observed_at=now)

    def available_models(self) -> list:
        """The picker's rows, read and dismissed. Never presses a commit key;
        returns [] when the dialog cannot be opened or read."""
        self._require_ready("available_models")
        self._model_busy = True
        try:
            base = self._runner._model_baseline()
            dialog = self._runner._open_model_dialog(base)
            return list(dialog.rows)
        except ModelControlError:
            return []
        finally:
            self._runner._abort_model_dialog()
            self._model_busy = False

    def set_model(self, model: str, *, effort: str | None = None,
                  strategy: str = "auto", persist: bool = False,
                  accept_cache_reset: bool = True,
                  force: bool = False) -> ModelState:
        """Change the LIVE session's model, the way a person would.

        strategy  "picker"  -- open /model, arrow to the row, verify, commit.
                  "command" -- type "/model <model>". MEASURED to always save
                               the global default, so it requires persist=True.
                  "auto"    -- picker unless persist=True and no effort change.

        persist   False (default): commits with 's' ("use this session only"),
                  measured NOT to touch ~/.claude/settings.json. True: presses
                  Enter, which rewrites the operator's global default model.

        effort    Changing effort ALWAYS writes the global effortLevel -- there
                  is no session-scoped effort path in the TUI (measured: the
                  picker's arrows persist it even on an 's' commit). So an
                  effort change requires persist=True; to give one session its
                  own effort without touching global config, pass effort= to
                  start() instead, which uses the --effort launch flag.

        force     False short-circuits when the session already matches, so a
                  no-op cannot cost a full conversation re-read.

        Call BETWEEN turns, on the owning thread. Raises ModelControlError on
        any verification failure; every pre-commit failure leaves the TUI closed
        and idle with nothing committed."""
        if strategy not in ("auto", "picker", "command"):
            raise ValueError("strategy must be auto|picker|command, got %r"
                             % strategy)
        if effort is not None and not persist:
            raise ModelControlError(
                "changing effort always writes the global effortLevel (measured: "
                "even the picker's session-only commit persists it). Pass "
                "persist=True to accept that, or set effort at launch via "
                "SessionHandle.start(effort=...), which is session-scoped.",
                stage="effort-persists-globally")
        if not force and self._already(model, effort):
            self._runner.log("[model] already on %r/%r; no keys sent"
                             % (model, effort))
            return self.model_state()

        self._require_ready("set_model")
        use_command = strategy == "command" or (strategy == "auto" and persist
                                                and effort is None)
        if use_command and not persist:
            raise ModelControlError(
                "strategy='command' uses /model <alias>, which was measured to "
                "always save the global default; pass persist=True or use "
                "strategy='picker'", stage="command-persists-globally")

        self._model_busy = True
        try:
            if use_command:
                conf = self._runner.set_model_via_command(
                    model, accept_cache_reset=accept_cache_reset)
            else:
                conf = self._runner.set_model_via_picker(
                    model, effort=effort, persist=persist,
                    accept_cache_reset=accept_cache_reset)
        finally:
            self._model_busy = False
        self._last_confirmation = conf
        self._model_scope = conf.scope
        self.model = model
        if conf.effort:
            self.effort = conf.effort
        return self.model_state()

    def set_effort(self, effort: str, *, persist: bool = True,
                   accept_cache_reset: bool = True,
                   force: bool = False) -> ModelState:
        """Change only the effort level.

        persist defaults to True and cannot be False: every mid-session effort
        path writes the operator's global effortLevel (measured -- both
        `/effort <level>` and the picker's arrows do it). The bare `/effort`
        slider is never opened; it renders as a positional track that no text
        predicate can read."""
        if not persist:
            raise ModelControlError(
                "there is no session-scoped effort change: every mid-session "
                "path writes the global effortLevel. Use "
                "SessionHandle.start(effort=...) for a session-scoped effort.",
                stage="effort-persists-globally")
        if not force and self._already(None, effort):
            self._runner.log("[model] already on effort %r; no keys sent" % effort)
            return self.model_state()
        self._require_ready("set_effort")
        self._model_busy = True
        try:
            conf = self._runner.set_effort_via_command(
                effort, accept_cache_reset=accept_cache_reset)
        finally:
            self._model_busy = False
        self.effort = conf.effort
        return self.model_state()

    # --- model/effort helpers ---
    def _already(self, model: str | None, effort: str | None) -> bool:
        state = self.model_state()
        if model is not None and not state.matches(model):
            return False
        if effort is not None and state.effort != effort:
            return False
        return model is not None or effort is not None

    def _require_ready(self, what: str) -> None:
        """Model changes are a between-turns operation: they type into the
        composer and navigate a dialog, so anything else on screen would eat the
        keys (or, worse, receive them)."""
        if self._model_busy:
            raise ModelControlError("%s is already running on this handle" % what,
                                    stage="reentrant")
        if not self.is_alive():
            raise ModelControlError("the session is not alive", stage="dead")
        state = self.peek_state()
        if state is not SessionState.IDLE:
            raise ModelControlError(
                "%s needs an idle session, not %s -- call it between turns"
                % (what, state.value),
                stage="not-idle", screen_tail=self.screen_tail())
        if self.pending_interaction() is not None:
            raise ModelControlError(
                "%s refuses to run while an interaction is pending" % what,
                stage="pending-interaction", screen_tail=self.screen_tail())

    def snapshot(self) -> dict:
        """Persistable session identity for rehydration. Returns the dict and,
        when snapshot_dir was given, also writes session-<sid>.json there."""
        try:
            transcript = tx.find_transcript(self._runner.session_id)
        except Exception:
            transcript = None
        snap = {
            "session_id": self._runner.session_id,
            "workdir": str(self._runner.workdir),
            "mode": self._runner.mode,
            "role": self.role,
            "model": self.model,
            "effort": self.effort,
            "extra_args": list(self._runner.extra_args),
            "claude_exe": self._runner.claude_exe,
            "app_dir": str(self._runner.app_dir),
            "transcript": transcript,
            "system_prompt_append": self.system_prompt_append,
            "snapshot_dir": str(self.snapshot_dir) if self.snapshot_dir else None,
            "turn_count": self.turn_count,
            "usage_limited": self.usage_limited,
            "turn_timeout": self.turn_timeout,
            "last_outcome": self.last_outcome,
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "saved_at": time.time(),
        }
        if self.snapshot_dir:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            path = self.snapshot_dir / ("session-%s.json" % snap["session_id"])
            path.write_text(json.dumps(snap, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        return snap

    def _autosnapshot(self) -> None:
        """Re-snapshot when a snapshot_dir was given (skips the transcript
        lookup otherwise). Never lets a bookkeeping failure break a turn."""
        if not self.snapshot_dir:
            return
        try:
            self.snapshot()
        except Exception as e:
            self._runner.log("[snapshot] write failed: %r" % e)


def _strip_flags(args: list, flags) -> list:
    """Remove `--flag value` / `--flag=value` pairs so from_snapshot can pass
    the same values explicitly without duplicating them in argv."""
    out = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in flags:
            skip = True
            continue
        if any(a.startswith(f + "=") for f in flags):
            continue
        out.append(a)
    return out
