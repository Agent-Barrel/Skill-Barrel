"""Incremental Codex control through its subscription-authenticated app-server."""
from __future__ import annotations

from copy import deepcopy
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import queue
import threading
import time
import uuid

from ..contracts import (ControlError, MenuOption, ModelRow, ModelState, PendingInteraction,
                         PendingTurn, SessionState, TurnOutcome, TurnResult,
                         UnsupportedOperation)
from .events import APPROVALS, QUESTION, EventState
from .transport import Transport


class ModelControlError(ControlError):
    def __init__(self, message, *, stage="validation", screen_tail=None):
        super().__init__(message)
        self.stage, self.screen_tail = stage, screen_tail


class AuthenticationError(ControlError):
    pass


def _positive(value, name):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


class SessionHandle:
    capabilities = frozenset({"turns", "plan", "approve_plan", "reject_plan", "questions",
                              "approvals", "interrupt", "models", "effort", "transcript",
                              "activity_log", "resume"})

    @classmethod
    def start(cls, *, workdir, role=None, system_prompt_append=None, model=None,
              effort=None, mode="bypass", app_dir=None, codex_exe=None, logger=None,
              snapshot_dir=None, request_timeout=30.0, turn_timeout=600.0,
              stall_seconds=120.0, approval_policy="never", sandbox_mode="danger-full-access",
              session_id=None):
        if mode not in ("bypass", "plan"):
            raise ValueError("mode must be bypass or plan")
        if approval_policy not in ("never", "on-request", "untrusted"):
            raise ValueError("approval_policy must be never, on-request, or untrusted")
        if sandbox_mode not in ("danger-full-access", "workspace-write", "read-only"):
            raise ValueError("invalid sandbox_mode")
        h = cls()
        h.request_timeout = _positive(request_timeout, "request_timeout")
        h.turn_timeout = _positive(turn_timeout, "turn_timeout")
        h.stall_seconds = _positive(stall_seconds, "stall_seconds")
        h.workdir = Path(workdir).expanduser().resolve()
        h.workdir.mkdir(parents=True, exist_ok=True)
        h.app_dir = Path(app_dir or h.workdir / ".step2step").expanduser().resolve()
        h.run_dir = h.app_dir / "codex" / str(uuid.uuid4())
        h.run_dir.mkdir(parents=True)
        if app_dir is None and not (h.app_dir / ".gitignore").exists():
            (h.app_dir / ".gitignore").write_text("*\n", encoding="utf-8")
        h.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        h.codex_exe, h.role, h.mode = str(codex_exe) if codex_exe else None, role, mode
        h.approval_policy, h.sandbox_mode = approval_policy, sandbox_mode
        h._owner = threading.get_ident()
        h._lock = threading.RLock()
        h._started_at = time.time()
        h._logger = logger
        h._wire_logger = logging.Logger(f"codex-{h.run_dir.name}")
        h._log_handler = RotatingFileHandler(h.run_dir / "events.jsonl", maxBytes=5_000_000,
                                            backupCount=3, encoding="utf-8")
        h._wire_logger.addHandler(h._log_handler)
        h._transport = None
        h._closed = False
        h._active = None
        h._cached_result = None
        h._forced_outcome = None
        h._phase = None
        h._physical_turns = []
        h.turn_count = 0
        h.usage_limited = False
        h.model, h.effort = model, effort
        h._model_scope = "launch"
        h._observed_model = h._observed_effort = None
        try:
            h._transport = Transport(executable=codex_exe, cwd=str(h.workdir),
                                     timeout=h.request_timeout, stderr_path=h.run_dir / "stderr.log")
            h._transport.request("initialize", {
                "clientInfo": {"name": "step2step", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            })
            h._transport.notify("initialized")
            account = h._transport.request("account/read", {"refreshToken": False})
            if (account.get("account") or {}).get("type") != "chatgpt":
                raise AuthenticationError("Codex requires ChatGPT subscription login. Run `codex login`.")
            h._models = h._list_models()
            h._validate_model(model, effort)
            # Starting a writable thread makes Codex 0.153.4 persist workspace
            # trust in global config.toml, even with invocation trust overrides.
            # Boot read-only, then set the requested policy on every actual turn.
            params = {"cwd": str(h.workdir), "modelProvider": "openai",
                      "approvalPolicy": h._approval(), "sandbox": "read-only",
                      "approvalsReviewer": "user"}
            if model:
                params["model"] = model
            if effort:
                params["config"] = {"model_reasoning_effort": effort}
            if system_prompt_append:
                params["developerInstructions"] = system_prompt_append
            if session_id:
                params.update(threadId=session_id, excludeTurns=True)
                result = h._transport.request("thread/resume", params)
            else:
                params["ephemeral"] = False
                result = h._transport.request("thread/start", params)
            thread = result["thread"]
            h.session_id = thread["id"]
            h._metadata_path = h.app_dir / "codex" / f"session-{h.session_id}.json"
            h._events = EventState(h.session_id)
            if result.get("modelProvider") != "openai":
                raise AuthenticationError("Codex did not select the OpenAI subscription provider")
            if (thread.get("status") or {}).get("type") == "active":
                raise ControlError("Refusing to take ownership of an already active thread")
            h.model = result["model"]
            h.effort = result.get("reasoningEffort")
            h._observed_model, h._observed_effort = h.model, h.effort
            h._validate_model(h.model, h.effort)
            if session_id:
                cursor = None
                while True:
                    page = h._transport.request("thread/turns/list", {
                        "threadId": h.session_id, "limit": 100, "cursor": cursor,
                        "sortDirection": "asc", "itemsView": "full"})
                    for turn in page["data"]:
                        h._events.load_turn(turn)
                    cursor = page.get("nextCursor")
                    if not cursor:
                        break
                h.turn_count = len(h._events.turns)
                if h._metadata_path.exists():
                    try:
                        saved = json.loads(h._metadata_path.read_text(encoding="utf-8"))
                        if saved.get("session_id") == h.session_id and saved.get("workdir") == str(h.workdir):
                            h.turn_count = int(saved["turn_count"])
                    except (ValueError, KeyError, TypeError):
                        pass  # History remains authoritative if the local sidecar is unavailable.
            h._events.rate_limits = h._transport.request("account/rateLimits/read")
            h._pump()
            h.snapshot()
            h._log(f"[codex] started {h.session_id} model={h.model} effort={h.effort}")
            return h
        except BaseException:
            if h._transport:
                h._transport.close(force=True)
            h._log_handler.close()
            raise

    @classmethod
    def resume(cls, session_id: str, **kwargs):
        """Explicitly reopen a saved, inactive conversation; never replay a prompt."""
        return cls.start(session_id=session_id, **kwargs)

    def _require_owner(self):
        if threading.get_ident() != self._owner:
            raise ControlError("Session mutations and waits must run on the owning thread")
        if self._closed:
            raise ControlError("session is closed")

    def _log(self, message):
        if self._logger:
            try:
                self._logger(message)
            except Exception:
                pass

    def _approval(self):
        return {"on-request": "on-request", "untrusted": "untrusted", "never": "never"}[self.approval_policy]

    def _sandbox(self, plan=False):
        if plan or self.sandbox_mode == "read-only":
            return {"type": "readOnly"}
        if self.sandbox_mode == "workspace-write":
            return {"type": "workspaceWrite", "writableRoots": [str(self.workdir)]}
        return {"type": "dangerFullAccess"}

    def _list_models(self):
        models, cursor = [], None
        while True:
            page = self._transport.request("model/list", {"limit": 100, "cursor": cursor})
            models.extend(page["data"])
            cursor = page.get("nextCursor")
            if not cursor:
                return models

    def _validate_model(self, model, effort):
        if model is None:
            return
        row = next((m for m in self._models if m["model"] == model or m["id"] == model), None)
        if row is None:
            raise ModelControlError(f"Model {model!r} is not in the available Codex model list")
        supported = {e["reasoningEffort"] for e in row.get("supportedReasoningEfforts", [])}
        if effort is not None and effort not in supported:
            raise ModelControlError(f"Effort {effort!r} is not supported by {model}: {sorted(supported)}")

    def _pump(self):
        with self._lock:
            while True:
                try:
                    msg = self._transport.events.get_nowait()
                except queue.Empty:
                    break
                self._events.apply(msg)
                # Log only this conversation; never log account/auth replies or tokens.
                params = msg.get("params") or {}
                if params.get("threadId") == self.session_id:
                    self._wire_logger.info(json.dumps(msg, ensure_ascii=False))

    def _require_idle(self):
        self._require_owner()
        self._pump()
        if not self.is_alive():
            raise ControlError("Codex session is disconnected")
        if self._active is not None and self._cached_result is None:
            raise ControlError("Finish or interrupt the pending turn before this operation")

    def _launch(self, text, *, planning):
        params = {"threadId": self.session_id,
                  "input": [{"type": "text", "text": text}],
                  "model": self.model, "effort": self.effort,
                  "approvalPolicy": self._approval(), "approvalsReviewer": "user",
                  "sandboxPolicy": self._sandbox(planning),
                  "collaborationMode": {"mode": "plan" if planning else "default", "settings": {
                      "model": self.model, "reasoning_effort": self.effort,
                      "developer_instructions": None}}}
        result = self._transport.request("turn/start", params)
        turn = result["turn"]
        turn_id = turn["id"]
        with self._lock:
            local = self._events.turn(turn_id)
            local.prompt = text
            self._physical_turns.append(turn_id)
            self._active.turn_id = turn_id
            # Preserve notifications that may have arrived before the RPC response.
            if turn.get("status") != "inProgress":
                self._events.load_turn(turn)
        self._pump()

    def send_prompt(self, text: str) -> PendingTurn:
        self._require_idle()
        if not isinstance(text, str) or not text.strip():
            raise ValueError("prompt must be nonempty text")
        self._active = PendingTurn(0, 0, text, time.time(), self.session_id)
        self._cached_result = None
        self._forced_outcome = None
        self._physical_turns = []
        self._remaining = self.turn_timeout
        self._phase = "planning" if self.mode == "plan" else "execution"
        self._log(f"[codex] send turn {self.turn_count + 1}: {len(text)} characters")
        try:
            self._launch(text, planning=self._phase == "planning")
        except BaseException:
            self._forced_outcome = TurnOutcome.FAILED
            raise
        return self._active

    def _check_pending(self, pending):
        if pending is not self._active or pending.session_id != self.session_id:
            raise ControlError("PendingTurn belongs to a different session or an earlier turn")

    def _interaction(self):
        if not self._active or not self._active.turn_id or self._cached_result:
            return None
        if self._phase == "approval":
            rec = self._events.turn(self._active.turn_id).record()
            return PendingInteraction("plan_approval", None, [], rec["plan"] or rec["response"],
                                      [MenuOption(1, "Execute plan", False),
                                       MenuOption(2, "Revise plan", False)],
                                      self.screen_tail(), "app-server")
        return self._events.pending(self._active.turn_id)

    def pending_interaction(self, tool_hint=None):
        self._pump()
        with self._lock:
            if self._active and self._active.turn_id and self._phase == "planning" and self._events.turn(self._active.turn_id).status == "completed":
                self._phase = "approval"
            return self._interaction()

    def _outcome(self):
        if self._forced_outcome:
            return self._forced_outcome
        turn = self._events.turn(self._active.turn_id)
        if turn.status == "completed":
            if self._phase != "execution" and not self.is_alive():
                return TurnOutcome.EOF
            if self._phase == "planning":
                self._phase = "approval"
            return (TurnOutcome.AWAITING_PLAN_APPROVAL if self._phase == "approval"
                    else TurnOutcome.COMPLETED)
        if turn.status == "interrupted":
            return TurnOutcome.INTERRUPTED
        if turn.status == "failed":
            if "usagelimitexceeded" in json.dumps(turn.error).lower():
                self.usage_limited = True
                return TurnOutcome.USAGE_LIMIT
            return TurnOutcome.FAILED
        if not self.is_alive() or self._events.disconnected:
            return TurnOutcome.EOF
        interaction = self._interaction()
        if interaction:
            if interaction.kind == "unknown_dialog":
                return TurnOutcome.UNSUPPORTED
            return TurnOutcome.AWAITING_MENU
        return None

    def _result(self, outcome):
        records = [self._events.turn(tid).record() for tid in self._physical_turns]
        last = records[-1] if records else {}
        result = TurnResult(outcome, self.turn_count + 1, last.get("response", ""),
                            [tool for r in records for tool in r["tools"]],
                            self._interaction(), 0, self._reset_text(), self._active.submitted_at,
                            time.time(), {"provider": "codex", "thread_id": self.session_id,
                                          "turns": records, "error": last.get("error"),
                                          "rate_limits": deepcopy(self._events.rate_limits),
                                          "usage": deepcopy(self._events.token_usage)})
        if outcome in (TurnOutcome.COMPLETED, TurnOutcome.FAILED, TurnOutcome.EOF,
                       TurnOutcome.INTERRUPTED, TurnOutcome.USAGE_LIMIT):
            self.turn_count += 1
            self._cached_result = result
            result.pending = None
            self.snapshot()
        self._log(f"[codex] turn {result.turn_index}: {outcome.value}")
        return result

    def wait_turn(self, pending, *, timeout=None, stall_seconds=None):
        self._require_owner()
        self._check_pending(pending)
        if self._cached_result:
            return self._cached_result
        stall = self.stall_seconds if stall_seconds is None else _positive(stall_seconds, "stall_seconds")
        budget = self._remaining if timeout is None else min(self._remaining, _positive(timeout, "timeout"))
        start = time.monotonic()
        try:
            while True:
                self._pump()
                with self._lock:
                    outcome = self._outcome()
                    if outcome:
                        return self._result(outcome)
                    elapsed = time.monotonic() - start
                    idle = time.monotonic() - self._events.turn(pending.turn_id).last_progress
                    if elapsed >= budget:
                        return self._result(TurnOutcome.DEADLINE_EXCEEDED)
                    if idle >= stall:
                        return self._result(TurnOutcome.STALLED)
                time.sleep(min(0.05, max(0.001, budget - elapsed)))
        finally:
            self._remaining = max(0.0, self._remaining - (time.monotonic() - start))

    def run_turn(self, text, **kwargs):
        return self.wait_turn(self.send_prompt(text), **kwargs)

    def answer_questions(self, answers: dict[str, str | list[str]], *, request_id=None):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind != "ask_user_question":
            raise ControlError("No question is pending")
        if request_id is not None and request_id != pending.request_id:
            raise ControlError("Question request is stale")
        ids = {q["id"] for q in pending.questions}
        if set(answers) != ids:
            raise ValueError(f"Provide exactly one answer entry for each question id: {sorted(ids)}")
        payload = {}
        for key, value in answers.items():
            values = [value] if isinstance(value, str) else value
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError("Answers must be nonempty strings or lists of nonempty strings")
            payload[key] = {"answers": values}
        self._respond(pending, {"answers": payload})

    def _respond(self, pending, payload):
        self._transport.respond(pending.request_id, payload)
        with self._lock:
            self._events.requests.pop(pending.request_id, None)
            self._events.resolved.add((self._active.turn_id, pending.request_id))
            self._events.turn(self._active.turn_id).last_progress = time.monotonic()

    def answer_menu(self, option_index):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind != "ask_user_question" or len(pending.questions) != 1:
            raise ControlError("answer_menu requires one pending question; use answer_questions for multiple")
        if not isinstance(option_index, int) or option_index < 1 or option_index > len(pending.menu):
            raise ValueError("option_index is out of range (1-based)")
        self.answer_questions({pending.questions[0]["id"]: pending.menu[option_index - 1].label},
                              request_id=pending.request_id)

    def answer_menu_text(self, text):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind != "ask_user_question" or len(pending.questions) != 1:
            raise ControlError("answer_menu_text requires one pending question")
        self.answer_questions({pending.questions[0]["id"]: text}, request_id=pending.request_id)

    def answer_approval(self, decision, *, request_id=None):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind not in APPROVALS.values():
            raise ControlError("No command or file approval is pending")
        if request_id is not None and pending.request_id != request_id:
            raise ControlError("Approval request is stale")
        allowed = pending.raw["params"].get("availableDecisions") or ["accept", "acceptForSession", "decline", "cancel"]
        if decision not in allowed or not isinstance(decision, str):
            raise ValueError(f"Unsupported approval decision: {decision!r}")
        self._respond(pending, {"decision": decision})

    def approve_plan(self):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind != "plan_approval":
            raise ControlError("No plan is awaiting approval; call wait_turn first")
        self._phase = "execution"
        self._launch("Implement the approved plan.\n\n" + (pending.plan or ""), planning=False)

    def reject_plan(self, feedback):
        self._require_owner()
        pending = self.pending_interaction()
        if not pending or pending.kind != "plan_approval":
            raise ControlError("No plan is awaiting approval")
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("feedback must be nonempty")
        # A new token invalidates stale waiters; this remains the same logical task.
        self._active = PendingTurn(0, 0, self._active.prompt, self._active.submitted_at, self.session_id)
        self._phase = "planning"
        self._launch("Revise the plan using this feedback; do not implement yet:\n" + feedback, planning=True)
        return self._active

    def interrupt(self):
        """True once the turn is confirmed stopped (or nothing was running);
        raises ControlError when the server never confirms."""
        self._require_owner()
        self._pump()
        if not self._active or self._cached_result:
            return True
        if self._phase == "approval":
            self._forced_outcome = TurnOutcome.INTERRUPTED
            self._result(TurnOutcome.INTERRUPTED)
            return True
        turn = self._events.turn(self._active.turn_id)
        if turn.status == "inProgress":
            self._transport.request("turn/interrupt", {"threadId": self.session_id, "turnId": turn.id})
            deadline = time.monotonic() + self.request_timeout
            while turn.status == "inProgress":
                self._pump()
                if not self.is_alive() or time.monotonic() >= deadline:
                    raise ControlError("Could not confirm turn interruption")
                time.sleep(0.02)
        self._result(self._outcome() or TurnOutcome.INTERRUPTED)
        return True

    def ensure_mode(self, target):
        self._require_idle()
        if target not in ("bypass", "plan"):
            raise ValueError("target must be bypass or plan")
        self.mode = target
        return True

    def available_models(self):
        self._require_idle()
        self._models = self._list_models()
        return [ModelRow(m.get("displayName", m["model"]), m["model"], i, -1, False,
                         m["model"] == self.model, m["model"],
                         tuple(e["reasoningEffort"] for e in m.get("supportedReasoningEfforts", [])),
                         "app-server") for i, m in enumerate(self._models, 1)]

    def model_state(self, *, refresh=False):
        if refresh:
            self._require_owner()
            result = self._transport.request("thread/read", {"threadId": self.session_id, "includeTurns": False})
            thread = result["thread"]
            self._observed_model, self._observed_effort = thread.get("model"), thread.get("reasoningEffort")
        pending_change = (self.model, self.effort) != (self._observed_model, self._observed_effort)
        return ModelState(self._observed_model, self._observed_effort, self.model,
                          self._model_scope, "requested" if pending_change else "server-config", time.time(),
                          requested_effort=self.effort)

    def set_model(self, model, *, effort=None, persist=False, strategy="auto",
                  accept_cache_reset=True, force=False):
        self._require_idle()
        if persist or strategy != "auto":
            raise UnsupportedOperation("Codex supports session-scoped model changes via app-server only")
        new_effort = self.effort if effort is None else effort
        self._validate_model(model, new_effort)
        self.model, self.effort = model, new_effort
        self._model_scope = "session"
        return self.model_state()

    def set_effort(self, effort, *, persist=False, **kwargs):
        return self.set_model(self.model, effort=effort, persist=persist, **kwargs)

    def _reset_text(self):
        resets = []
        def visit(obj):
            if isinstance(obj, dict):
                if obj.get("resetsAt") is not None:
                    resets.append(str(obj["resetsAt"]))
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, list):
                for value in obj:
                    visit(value)
        visit(self._events.rate_limits)
        return ", ".join(dict.fromkeys(resets)) or None

    def is_alive(self):
        return not self._closed and bool(self._transport and self._transport.is_alive())

    def peek_state(self):
        self._pump()
        if not self.is_alive():
            return SessionState.DEAD
        if self.usage_limited:
            return SessionState.USAGE_LIMITED
        if not self._active or self._cached_result:
            return SessionState.IDLE
        if self._active.turn_id is None:
            return SessionState.STARTING
        pending = self.pending_interaction()
        if pending:
            return {"plan_approval": SessionState.AWAITING_PLAN_APPROVAL,
                    "unknown_dialog": SessionState.AWAITING_UNKNOWN_DIALOG}.get(pending.kind, SessionState.AWAITING_MENU)
        turn = self._events.turn(self._active.turn_id)
        if turn.status != "inProgress":
            return SessionState.IDLE
        return (SessionState.STALLED if time.monotonic() - turn.last_progress >= self.stall_seconds
                or self._remaining <= 0
                else SessionState.WORKING)

    def screen_tail(self, n=20):
        self._pump()
        with self._lock:
            return "\n".join(list(self._events.activity)[-n:]) if n > 0 else ""

    def transcript_turns(self):
        self._pump()
        with self._lock:
            return self._events.transcript()

    def health(self):
        self._pump()
        return {"alive": self.is_alive(), "state": self.peek_state().value, "mode": self.mode,
                "provider": "codex", "screen_source": "activity_log", "turn_count": self.turn_count,
                "usage_limited": self.usage_limited, "usage_reset_text": self._reset_text(),
                "rate_limits": deepcopy(self._events.rate_limits), "usage": deepcopy(self._events.token_usage)}

    def snapshot(self):
        snapshot = {"provider": "codex", "session_id": self.session_id, "workdir": str(self.workdir),
                    "mode": self.mode, "role": self.role, "model": self.model, "effort": self.effort,
                    "app_dir": str(self.app_dir), "codex_exe": self.codex_exe,
                    "turn_count": self.turn_count, "usage_limited": self.usage_limited,
                    "started_at": self._started_at, "saved_at": time.time(),
                    "transcript": str(self.run_dir / "transcript.json"),
                    "screen_source": "activity_log"}
        (self.run_dir / "session.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        self._metadata_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        (self.run_dir / "transcript.json").write_text(json.dumps(self._events.transcript(), ensure_ascii=False, indent=2), encoding="utf-8")
        if self.snapshot_dir:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
            (self.snapshot_dir / f"session-{self.session_id}.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return snapshot

    def stop(self, *, force=False):
        if self._closed:
            return
        self._require_owner()
        try:
            if not force and self.is_alive():
                self.interrupt()
                self._transport.request("thread/backgroundTerminals/clean", {"threadId": self.session_id})
        finally:
            try:
                self._transport.close(force=force)
                self._pump()
                self.snapshot()
            finally:
                self._closed = True
                self._log_handler.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop(force=bool(args[0]))
