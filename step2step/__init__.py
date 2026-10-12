"""Product-neutral contracts and prompt utilities.

Select a product explicitly with ``step2step.claude`` or ``step2step.codex``.
Terminal I/O lives in ``step2step.terminal``; importing this package loads no
product, PTY backend, or platform-specific console bindings.
"""
from .contracts import (
    ControlError,
    MenuOption,
    ModelRow,
    ModelState,
    PendingInteraction,
    PendingTurn,
    SessionControl,
    SessionState,
    TurnOutcome,
    TurnResult,
    UnsupportedOperation,
)
from .prompts import load_prompts, parse_prompts

__all__ = [
    "ControlError",
    "SessionControl",
    "UnsupportedOperation",
    "load_prompts",
    "parse_prompts",
    "SessionState",
    "TurnOutcome",
    "MenuOption",
    "PendingInteraction",
    "PendingTurn",
    "TurnResult",
    "ModelState",
    "ModelRow",
]
