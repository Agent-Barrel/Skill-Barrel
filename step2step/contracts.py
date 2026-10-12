"""Provider-neutral control contracts. No transport or provider imports."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

@dataclass
class MenuOption:
    """One parsed row of a numbered selection menu (❯ marks the highlight)."""

    index: int
    label: str
    highlighted: bool


@dataclass
class ModelRow:
    """A selectable model. Screen coordinates are -1 when no TUI is involved."""

    label: str
    name: str
    index: int | None
    row: int
    highlighted: bool
    current: bool
    model_id: str | None = None
    supported_efforts: tuple[str, ...] = ()
    source: str = "screen"


class SessionState(str, Enum):
    STARTING = "starting"
    IDLE = "idle"
    WORKING = "working"
    AWAITING_MENU = "awaiting_menu"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    AWAITING_UNKNOWN_DIALOG = "awaiting_unknown_dialog"
    USAGE_LIMITED = "usage_limited"
    STALLED = "stalled"
    DEAD = "dead"


class TurnOutcome(str, Enum):
    """Terminal and waiting outcomes shared by provider implementations."""

    COMPLETED = "completed"          # Stop signal past the baseline
    COMPLETED_IDLE = "completed_idle"  # idle fallback (hook miss)
    AWAITING_MENU = "awaiting_menu"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    AWAITING_UNKNOWN_DIALOG = "awaiting_unknown_dialog"
    USAGE_LIMIT = "usage_limit"
    STALLED = "stalled"                      # silence: no output for stall_seconds
    NOISY_STAGNATION = "noisy_stagnation"    # output keeps coming, progress does not
    DEADLINE_EXCEEDED = "deadline_exceeded"  # the turn budget ran out (never infinite)
    SUBMIT_FAILED = "submit_failed"          # the prompt was never confirmed as started
    EOF = "eof"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNSUPPORTED = "unsupported"


@dataclass
class PendingInteraction:
    kind: str                    # "ask_user_question" | "plan_approval" | "unknown_dialog"
    tool_use_id: str | None
    questions: list[dict]        # Question text, IDs and answer options
    plan: str | None             # Proposed plan, when awaiting approval
    menu: list[MenuOption]       # parsed from the screen tail
    screen_tail: str             # evidence for logging / escalation
    # Evidence source: screen, transcript, or app-server.
    source: str = "screen"
    request_id: str | int | None = None
    raw: dict | None = None


@dataclass
class TurnResult:
    outcome: TurnOutcome
    turn_index: int
    response: str
    tools: list[str]
    pending: PendingInteraction | None
    signal_lines: int
    usage_reset_text: str | None
    started_at: float
    ended_at: float
    raw: dict | None = None      # _wait_turn_event's internal dict, for audits


@dataclass
class ModelState:
    """Observed configuration and requested model; provider aliases stay in adapters."""

    model: str | None
    effort: str | None
    requested: str | None        # what WE last asked for (alias vocabulary)
    scope: str | None            # "launch" | "session" | "default"
    source: str                  # transcript | confirmation | launch-flags | unknown
    observed_at: float
    raw: str | None = None       # the evidence line, for logs
    requested_effort: str | None = None

    def matches(self, target: str) -> bool:
        return any(v == target for v in (self.model, self.requested) if v)


@dataclass
class PendingTurn:
    """Returned by send_prompt(); consumed by wait_turn(). AWAITING_* outcomes
    do NOT consume it. Answer, then wait again using the same token.
    Provider identifiers are optional for compatibility with Claude baselines."""

    baseline_stop: int
    baseline_events: int
    prompt: str
    submitted_at: float
    session_id: str | None = None
    turn_id: str | None = None
    # Submission evidence (keyword fields, appended so positional builders keep
    # working). `submitted` is whether the sender confirmed the turn actually
    # started; `baseline_turns`/`transcript_seen` let the waiter tell a real
    # idle completion from a swallowed prompt that left the screen idle.
    submitted: bool = True
    baseline_turns: int = 0
    transcript_seen: bool = False


class ControlError(RuntimeError):
    """A control operation failed; no automatic prompt retry is performed."""


class UnsupportedOperation(ControlError):
    pass


@runtime_checkable
class SessionControl(Protocol):
    capabilities: frozenset[str]

    @property
    def session_id(self) -> str: ...
    def send_prompt(self, text: str) -> PendingTurn: ...
    def wait_turn(self, pending: PendingTurn, *, timeout: float | None = None,
                  stall_seconds: float = 120.0) -> TurnResult:
        """`timeout=None` means the handle's default turn budget -- never
        "wait forever". Implementations may accept further keyword options."""
        ...
    def run_turn(self, text: str, **kw) -> TurnResult: ...
    def peek_state(self) -> SessionState: ...
    def pending_interaction(self) -> PendingInteraction | None: ...
    def answer_questions(self, answers: dict[str, str | list[str]], *, request_id=None) -> None: ...
    def answer_approval(self, decision: str, *, request_id=None) -> None: ...
    def answer_menu(self, option_index: int) -> None: ...
    def answer_menu_text(self, text: str) -> None: ...
    def approve_plan(self) -> bool: ...
    def reject_plan(self, feedback: str) -> PendingTurn: ...
    def interrupt(self) -> bool:
        """True when the session settled (or was already idle/dead); False when
        the interrupt did not take. Never silently discarded by callers."""
        ...
    def stop(self, *, force: bool = False) -> None: ...
    def is_alive(self) -> bool: ...
    def health(self) -> dict: ...
    def snapshot(self) -> dict: ...
    def screen_tail(self, n: int = 20) -> str: ...
    def transcript_turns(self) -> list[dict]: ...
    def ensure_mode(self, target: str) -> bool: ...
    def available_models(self) -> list: ...
    def model_state(self, *, refresh: bool = False) -> ModelState: ...
    def set_model(self, model: str, **kw) -> ModelState: ...
    def set_effort(self, effort: str, **kw) -> ModelState: ...
