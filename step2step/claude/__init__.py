"""step2step.claude: drive a fresh interactive Claude Code session with pre-defined
prompts, in either hands-off bypass mode or auto-approved plan mode.

Product API:

    from step2step.claude import run_session
    result = run_session(prompts, workdir, mode="plan")   # or mode="bypass"

`prompts` is a list of strings (use step2step.prompts.load_prompts(path)
to read a markdown file split on `---`). Returns a structured summary dict.
"""
from .runner import EFFORT_LEVELS, ModelControlError, Runner, run_session
from ..prompts import load_prompts, parse_prompts
from ..contracts import ControlError, SessionControl, UnsupportedOperation
from .transcript import (
    find_transcript,
    last_model_effort,
    parse_transcript,
    turn_asks_question,
)
from .session import (
    MenuOption,
    ModelConfirmation,
    ModelDialog,
    ModelRow,
    ModelState,
    PendingInteraction,
    PendingTurn,
    SessionHandle,
    SessionState,
    TurnOutcome,
    TurnResult,
)

__all__ = [
    "ControlError",
    "SessionControl",
    "UnsupportedOperation",
    "run_session",
    "Runner",
    "load_prompts",
    "parse_prompts",
    "find_transcript",
    "parse_transcript",
    "last_model_effort",
    "turn_asks_question",
    "EFFORT_LEVELS",
    "SessionHandle",
    "SessionState",
    "TurnOutcome",
    "MenuOption",
    "PendingInteraction",
    "PendingTurn",
    "TurnResult",
    "ModelState",
    "ModelRow",
    "ModelDialog",
    "ModelConfirmation",
    "ModelControlError",
]
