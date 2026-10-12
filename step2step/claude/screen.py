"""pyte-backed screen reader plus the version-fragile TUI markers.

All strings that depend on Claude Code's TUI live here so a calibration pass is
a one-file change. The state machine (runner.py) only calls the helpers below.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts import MenuOption, ModelRow

# Number of trailing non-blank rows treated as the TUI "footer" (spinner, input
# box, mode line, hints). State detection that must not be fooled by response
# body text (working spinner, permission mode) is scoped to this region.
FOOTER_ROWS = 10

# --- Tunable markers (calibrate against the live TUI) -----------------------
# Shown in the footer while Claude is processing / interruptible (working-only).
# Only the full "esc to interrupt" phrase is used: a bare "to interrupt" also
# matches ordinary prose (e.g. "we tried not to interrupt"), which would make a
# response body read as "working" and stall shutdown. Combined with footer
# scoping (see is_working) this is robust against response text.
WORKING_MARKERS = ["esc to interrupt"]
# Shown by the first-launch workspace-trust dialog. It did not appear under
# --dangerously-skip-permissions on older versions; on 2.1.272 it does, as an
# UNNUMBERED two-row select whose default highlight is "No, exit":
#     ❯ No, exit
#       Yes, I trust this folder
#     Enter to confirm · Esc to cancel
# so a blind Enter EXITS the session. trust_dialog_rows() reads the rows and the
# runner walks the highlight onto the accept row before pressing Enter.
TRUST_MARKERS = ["do you trust", "trust the files", "trust this folder"]
TRUST_ACCEPT_RE = re.compile(r"yes,?\s*i\s*trust", re.I)
TRUST_DECLINE_RE = re.compile(r"no,?\s*exit", re.I)
# Footer/hints that mean the input box is up and ready. "shift+tab to cycle" is
# the most stable: it is present at idle AND while working, regardless of whether
# the welcome banner is still on screen (it scrolls off in longer sessions).
IDLE_MARKERS = ["shift+tab to cycle", "? for shortcuts", "for shortcuts", "/help"]
# Box-drawing characters used by the input box.
INPUT_BOX_CHARS = ["│", "╭", "╮", "╰", "╯", "▌"]
# The footer permission-mode line looks like "⏵⏵ bypass permissions on (shift+tab
# to cycle) · …" or "⏸ plan mode on (…)". We locate that line by MODE_LINE_HINT,
# then match a single distinctive keyword inside it — looser than full strings, so
# wording tweaks ("plan mode on" -> "plan mode") still resolve correctly.
MODE_LINE_HINT = "to cycle"
MODE_KEYWORDS = [
    ("plan", "plan"),
    ("bypass", "bypass"),
    ("accept-edits", "accept edit"),
    ("auto", "auto mode"),
]
# The plan-approval prompt (ExitPlanMode) shown at the end of a plan-mode turn.
# Option 1's exact text varies with how the session was launched: "Yes, and
# bypass permissions" when launched with --dangerously-skip-permissions, or
# "Yes, and use auto mode" when launched with --permission-mode plan. Either way
# option 1 is "proceed hands-off"; "would you like to proceed" is always present.
# Measured verbatim on 2.1.224 (tests/fixtures/screens/plan_approval.txt):
#   "Claude has written up a plan and is ready to execute. Would you like to proceed?"
#   " ❯ 1. Yes, and bypass permissions"
#   "   2. Yes, manually approve edits"
#   "   3. Tell Claude what to change"
PLAN_APPROVAL_MARKERS = [
    "would you like to proceed",
    "ready to code",
    "is ready to execute",
    "yes, and bypass permissions",
    "yes, and switch to bypass permissions",   # 2.1.272 wording of option 1
    "yes, and use auto mode",
    "yes, manually approve edits",
    "tell claude what to change",
]
# The line that sits DIRECTLY above the option list. Everything below the last
# one of these is the menu; everything above it is the plan body — which has its
# own numbered list, and parsing that as options would put Enter on the wrong
# row. "ready to code" is the older banner and renders ABOVE the plan body, so
# it only serves as a fallback when the newer sentence is absent.
PLAN_OPTION_ANCHORS = ["would you like to proceed", "ready to code"]

# The AskUserQuestion widget's own footer. Measured on 2.1.224 in TWO shapes —
#   multi-question:  "Enter to select · Tab/Arrow keys to navigate · Esc to cancel"
#   single question: "Enter to select · ↑/↓ to navigate · Esc to cancel"
# — so only the two stable ends are matched; the middle phrase varies with the
# widget's shape and must not be part of the test.
#
# This is the discriminator for a model-authored selection menu, and it is
# STRICTER than "there are numbered rows on screen": a response body's numbered
# list never carries it. It matters because the transcript may not help — a
# pending interaction's tool_use can be missing from the JSONL for as long as it
# waits (see transcript.pending_tool_use), so the screen is the reliable channel.
QUESTION_FOOTER_MARKERS = ["enter to select", "esc to cancel"]
# Rows the widget always appends itself; they are affordances, not model-authored
# answers, so question conversion must drop them.
QUESTION_BUILTIN_LABELS = ("type something", "chat about this")
# How many trailing non-blank rows count as "the dialog region". Deliberately
# deeper than FOOTER_ROWS: the task/agent panel renders BELOW the widget, so a
# 10-row tail can miss the option list entirely (measured — see
# tests/fixtures/screens/ask_user_question.txt).
DIALOG_ROWS = 26

# Usage-limit banner phrases. Exact wording is version-fragile (calibration V5
# tunes this list from live captures); matching is footer-scoped like is_working
# so a response body DISCUSSING usage limits cannot false-trip it.
USAGE_LIMIT_MARKERS = [
    "usage limit reached",
    "limit will reset",
    "approaching usage limit",
    "you've reached your",
    "usage limit",
]
_RESET_RE = re.compile(
    r"reset(?:s)?\s+(?:at\s+)?([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?[^\n·)]*)",
    re.I,
)

# Arrow keys for closed-loop menu navigation (answer_menu) and the /model picker
# (up/down = model row, left/right = effort). ESCAPE cancels any dialog.
CURSOR_UP = "\x1b[A"
CURSOR_DOWN = "\x1b[B"
CURSOR_LEFT = "\x1b[D"
CURSOR_RIGHT = "\x1b[C"
ESCAPE = "\x1b"

# Box-drawing gutter a framed dialog draws down the left edge. Allowed in the
# menu patterns for the same reason _MODEL_ROW_RE allows it: a framed row must
# not read as "no menu at all", which is the failure that leaves a driver
# blind while a dialog is waiting.
_GUTTER = r"[\s│┃|╎┆]"
_MENU_RE = re.compile(r"(?m)^" + _GUTTER + r"*[❯>›]?\s*\d+[.)]\s+\S")
# Capturing form of the same shape: (marker, number, label).
_MENU_CAP_RE = re.compile(r"^" + _GUTTER + r"*(❯|>|›)?\s*(\d+)[.)]\s+(.*?)"
                          + _GUTTER + r"*$")
# A row that is nothing but rules/frame — skipped, never a terminator: the
# measured question widget puts a separator BETWEEN options 3 and 4.
_SEPARATOR_RE = re.compile(r"^[\s─━╌┄┈–—\-│┃|╭╮╰╯╎┆]*$")
# An option's wrapped description line: the widget indents it under its option.
_DESC_RE = re.compile(r"^\s{4,}\S")
_TAB_MARK_RE = re.compile(r"^[☐☑✔✓✗×]\s*")
# A one-question widget draws a bare header row instead of a tab bar: " ☐ Config
# format". Only the ballot boxes count — ✔ also marks a done row in the task
# panel, and that must never be read as a question header.
_SINGLE_TAB_RE = re.compile(r"^[☐☑]\s*\S")

# --- /model picker markers (calibration V12-V17) ----------------------------
# Kept SHORT on purpose: at 200 columns the dialog's body sentence is one line,
# but a narrower terminal wraps it, and a full-sentence marker would then miss.
MODEL_DIALOG_MARKERS = ["select model"]
# Lines that belong to the dialog chrome, never to the option list.
MODEL_NOISE_MARKERS = [
    "switch between claude models",
    "for other/previous model names",
    "specify with --model",
    "currently using",
]
# The dialog footer advertises its two commit keys. Their presence is what tells
# us a session-only commit ('s') is even on offer.
MODEL_PERSIST_HINT = "set as default"
MODEL_SESSION_HINT = "use this session only"
# Shown instead of the effort widget on models with no effort control.
EFFORT_UNSUPPORTED = "effort not supported"
# The cache-invalidation confirm that fires when the conversation already has
# messages: "This conversation is cached for the current <model>…".
SWITCH_CONFIRM_MARKERS = ["switch model?", "change effort level?"]
SWITCH_ACCEPT_PREFIX = "yes, switch to"
# Effort values the TUI can display. Wider than the --effort flag's EFFORT_LEVELS
# (runner) on purpose: a session already on `ultracode`/`auto` must still parse.
EFFORT_TOKENS = ("low", "medium", "high", "xhigh", "max", "ultracode", "auto")

_MODEL_OVERFLOW_RE = re.compile(r"(?:…|\.\.\.)\s*\+(\d+)\s+models?", re.I)
# Pointer AND numbering are both optional: the picker is a generic virtualized
# Select, and whether it numbers or points at its rows is version-fragile.
_MODEL_ROW_RE = re.compile(r"^[\s│┃|]*(❯|>|›)?\s*(?:(\d+)[.)]\s+)?(\S.*?)[\s│┃|]*$")
_EFFORT_LINE_RE = re.compile(
    r"\b(low|medium|high|xhigh|max|ultracode|auto)\b\s+effort\b(?P<dflt>\s*\(default\))?",
    re.I,
)
# `search`, never anchored: fast-mode and settings-override notes are APPENDED to
# this line by the TUI.
_MODEL_CONFIRM_RE = re.compile(
    r"set model to\s+(?P<model>.+?)"
    r"(?P<scope>\s+and saved as your default for new sessions|\s+for this session only)"
    r"(?:\s+with\s+(?P<effort>\S+)\s+effort)?",
    re.I,
)
# `/effort <level>` prints a DIFFERENT line from a model change, with the scope
# in parentheses and a description after a colon (measured):
#   "Set effort level to medium (saved as your default for new sessions): Balanced…"
_EFFORT_CONFIRM_RE = re.compile(
    r"set effort level to\s+(?P<effort>[^\s(:]+)\s*(?:\((?P<scope>[^)]*)\))?",
    re.I,
)
_KEPT_MODEL_RE = re.compile(r"kept model as\s+(?P<model>.+?)\s*$", re.I | re.M)
_KEPT_EFFORT_RE = re.compile(r"kept effort level as\s+(?P<effort>\S+)", re.I)
_WORKING_EFFORT_RE = re.compile(r"thinking with\s+(\w+)\s+effort", re.I)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# Name and description are separated by a run of 2+ spaces (a column layout).
_NAME_SPLIT_RE = re.compile(r"\s{2,}")
# ✔ on the name marks the model the session is currently on. "(current model)"
# is kept as a fallback in case the badge changes back to words.
_CURRENT_BADGE_RE = re.compile(r"[✔✓✅]|\(?\s*current model\s*\)?", re.I)



@dataclass
class QuestionDialog:
    """A parsed AskUserQuestion widget — read from the SCREEN.

    The screen is not a second-best source here, it is the ONLY one: the
    tool_use carrying the question is absent from the transcript for exactly as
    long as the question is waiting (transcript.pending_tool_use). So a harness
    that wants to know WHAT was asked has to read it here.

    `options` is every row the widget drew; `model_options` drops the two rows
    the widget always appends itself ("Type something." / "Chat about this"),
    which are affordances rather than answers."""

    question: str                 # the question paragraph, lines joined
    header: str | None            # active tab (first unanswered), or None
    tabs: list[str]               # tab labels when the widget holds several questions
    options: list[MenuOption]
    descriptions: dict[int, str]  # option index -> its indented description
    raw: str

    @property
    def model_options(self) -> list[MenuOption]:
        return [o for o in self.options
                if o.label.strip().rstrip(".").lower() not in QUESTION_BUILTIN_LABELS]

    def as_tool_input(self) -> dict:
        """The same shape AskUserQuestion's tool `input` has, so a caller can
        feed screen-parsed content to code written against the transcript."""
        return {"questions": [{
            "question": self.question,
            "header": self.header,
            "options": [{"label": o.label,
                         "description": self.descriptions.get(o.index, "")}
                        for o in self.model_options],
        }]}


@dataclass
class ModelDialog:
    """A parsed /model picker.

    `highlighted is None` means WE COULD NOT READ which row is selected. That is
    a first-class result, not an error to paper over: the caller must Esc out
    rather than guess, because a guess would commit the wrong model."""

    rows: list[ModelRow]
    highlighted: ModelRow | None
    highlight_source: str        # "pointer" | "style" | "none"
    effort: str | None
    effort_is_default: bool
    effort_supported: bool
    hidden_rows: int             # from "… +N models"; 0 when the list fits
    persist_hint: bool           # footer offers "set as default"  (enter)
    session_only_hint: bool      # footer offers "use this session only" ('s')
    raw: str                     # the dialog region, for logs / escalation


@dataclass
class ModelConfirmation:
    """The system line the TUI prints after a model change lands."""

    model: str                   # display label as printed, e.g. "Opus 4.6"
    scope: str                   # "default" (global) | "session"
    effort: str | None
    trailing: str                # fast-mode / settings-override remainder
    line: str


def _contains_any(text: str, markers) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in markers)


def _footer(text: str, rows: int = FOOTER_ROWS) -> str:
    """The last `rows` non-blank lines — the TUI chrome (spinner/input box/mode
    line/hints). Scoping detection here keeps response body text from matching
    footer-only markers."""
    nonblank = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(nonblank[-rows:])


# --- State predicates (operate on a screen-text snapshot) -------------------
def is_working(text: str) -> bool:
    # Scope to the footer: the working spinner lives there, and this prevents a
    # response body that mentions the phrase from reading as "working".
    return _contains_any(_footer(text), WORKING_MARKERS)


def is_trust_dialog(text: str) -> bool:
    return _contains_any(text, TRUST_MARKERS)


_TRUST_POINTER_RE = re.compile(r"^" + _GUTTER + r"*(❯|>|›)\s*")


def trust_dialog_rows(text: str) -> list[MenuOption]:
    """The trust dialog's select rows (accept / decline) with their highlight,
    indexed in screen order; [] when the dialog is not the menu shape."""
    rows: list[MenuOption] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not (TRUST_ACCEPT_RE.search(stripped) or TRUST_DECLINE_RE.search(stripped)):
            continue
        highlighted = bool(_TRUST_POINTER_RE.match(line))
        label = _TRUST_POINTER_RE.sub("", line).strip(" \t│┃|")
        rows.append(MenuOption(index=len(rows) + 1, label=label, highlighted=highlighted))
    return rows


def has_input_box(text: str) -> bool:
    return any(ch in text for ch in INPUT_BOX_CHARS)


def looks_idle(text: str) -> bool:
    if is_working(text) or is_trust_dialog(text):
        return False
    return _contains_any(text, IDLE_MARKERS) or has_input_box(text)


def looks_like_question(text: str) -> bool:
    """Conservative: only flags a numbered selection menu (AskUserQuestion /
    permission style). Plain empty input boxes must NOT match, or every normal
    completion would be treated as a question."""
    nonblank = [ln for ln in text.splitlines() if ln.strip()]
    tail = "\n".join(nonblank[-10:]) if nonblank else ""
    return bool(_MENU_RE.search(tail))


def current_mode(text: str):
    """Active permission mode from the footer line, or None.

    Scans the footer region bottom-up for the line containing MODE_LINE_HINT, so
    the word "plan"/"cycle" elsewhere on screen — e.g. inside a plan Claude just
    wrote, or a help line — cannot be mistaken for the real mode footer, which is
    always the last such line."""
    for line in reversed(_footer(text).splitlines()):
        low = line.lower()
        if MODE_LINE_HINT in low:
            for mode, kw in MODE_KEYWORDS:
                if kw in low:
                    return mode
            return None  # footer found but no known mode keyword (e.g. default)
    return None


def plan_approval_options(text: str) -> list[MenuOption]:
    """The approval menu's rows, parsed BELOW the last PLAN_OPTION_ANCHORS line.

    Anchor-scoped for the same reason parse_model_dialog is: the plan body sits
    right above the menu and has its own numbered list. Parsing the whole screen
    would let "1. Rewrite beta.py" become option 1 — and an approver that then
    presses Enter has selected something nobody offered."""
    lines = text.splitlines()
    anchor = None
    for i, line in enumerate(lines):
        if _contains_any(line, PLAN_OPTION_ANCHORS):
            anchor = i  # last match wins: the option anchor renders below the banner
    if anchor is None:
        return []
    return menu_options("\n".join(lines[anchor + 1:]))


def _question_footer_row(lines) -> int | None:
    for i in range(len(lines) - 1, -1, -1):
        low = lines[i].lower()
        if all(m in low for m in QUESTION_FOOTER_MARKERS):
            return i
    return None


def _parse_tab_bar(line: str):
    """("label", answered) pairs from the widget's header row, or None.

    Two measured shapes on 2.1.224:
        several questions:  "←  ☐ a  ☐ b  ✔ Submit  →"   (columns split by 2+ spaces)
        one question:       " ☐ Config format"           (no arrows, no Submit)
    Recognising the second one matters: unparsed, that row runs into the
    question text and the caller escalates "☐ Config format Should the …?"."""
    stripped = line.strip()
    if not stripped:
        return None
    if "submit" in stripped.lower() and ("←" in stripped or "→" in stripped):
        tabs = []
        for cell in _NAME_SPLIT_RE.split(stripped):
            cell = cell.strip()
            if not cell or cell in ("←", "→"):
                continue
            answered = bool(cell[0] in "☑✔✓")
            label = _TAB_MARK_RE.sub("", cell).strip()
            if not label or label.lower() == "submit":
                continue
            tabs.append((label, answered))
        return tabs or None
    if _SINGLE_TAB_RE.match(stripped):
        label = _TAB_MARK_RE.sub("", stripped).strip()
        return [(label, stripped[0] == "☑")] if label else None
    return None


def parse_question_dialog(text: str) -> QuestionDialog | None:
    """Parse the AskUserQuestion widget out of a screen snapshot, or None.

    Works on the full screen AND on a blank-stripped tail (ScreenReader.tail /
    ExternalSession.text both drop blank rows), so it never leans on blank lines
    as separators."""
    lines = text.splitlines()
    footer = _question_footer_row(lines)
    if footer is None:
        return None

    # Walk UP from the footer to the top of the option block. Separators and
    # blanks are skipped rather than ending the walk (measured: a separator sits
    # between options 3 and 4); the first ordinary line above the block is the
    # question paragraph and stops it.
    start = None
    for i in range(footer - 1, -1, -1):
        line = lines[i]
        if not line.strip() or _SEPARATOR_RE.match(line):
            continue
        if _MENU_CAP_RE.match(line) or _DESC_RE.match(line):
            start = i
            continue
        break
    if start is None:
        return None

    options: list[MenuOption] = []
    descriptions: dict[int, str] = {}
    last = None
    for line in lines[start:footer]:
        m = _MENU_CAP_RE.match(line)
        if m and m.group(3).strip():
            last = int(m.group(2))
            options.append(MenuOption(index=last, label=m.group(3).strip(),
                                      highlighted=m.group(1) is not None))
            continue
        if last is not None and _DESC_RE.match(line):
            descriptions[last] = (descriptions.get(last, "") + " "
                                  + line.strip()).strip()
    if not options:
        return None

    # The question is what sits between the tab bar / last rule and the options.
    head = lines[:start]
    tabs: list[tuple[str, bool]] = []
    q_from = 0
    for i, line in enumerate(head):
        bar = _parse_tab_bar(line)
        if bar is not None:
            tabs, q_from = bar, i + 1
        elif line.strip() and _SEPARATOR_RE.match(line):
            q_from = i + 1
    question = " ".join(l.strip() for l in head[q_from:] if l.strip())
    header = next((label for label, done in tabs if not done), None)
    return QuestionDialog(question=question, header=header,
                          tabs=[label for label, _ in tabs],
                          options=options, descriptions=descriptions,
                          raw="\n".join(l for l in lines[q_from:footer + 1]
                                        if l.strip()))


def classify_dialog(text: str):
    """What interactive dialog is on screen: "plan_approval" | "question" |
    "unknown" | None. THE screen-side authority — every caller should ask this
    rather than re-deriving it, and none of them should ask the transcript,
    which is empty while an interaction waits.

    Ordering matters: the approval menu is checked first because it is the one
    we may answer with a key, and its wording is the more specific."""
    region = _footer(text, DIALOG_ROWS)
    if _contains_any(region, PLAN_APPROVAL_MARKERS) and plan_approval_options(text):
        return "plan_approval"
    if (all(m in region.lower() for m in QUESTION_FOOTER_MARKERS)
            and _MENU_RE.search(region)):
        return "question"
    if _MENU_RE.search(_footer(text, FOOTER_ROWS)):
        return "unknown"
    return None


def is_plan_approval(text: str) -> bool:
    """True when the plan-approval menu (ExitPlanMode) is showing."""
    return classify_dialog(text) == "plan_approval"


def menu_options(text: str) -> list[MenuOption]:
    """Parse the numbered selection menu out of a screen-text snapshot. Lines
    are pyte rows (space-padded), so labels are stripped; rows with an empty
    label are not options (mirrors _MENU_RE requiring \\S after the number)."""
    out = []
    for line in text.splitlines():
        m = _MENU_CAP_RE.match(line)
        if not m:
            continue
        label = m.group(3).strip()
        if not label:
            continue
        out.append(MenuOption(index=int(m.group(2)), label=label,
                              highlighted=m.group(1) is not None))
    return out


def highlighted_option(text: str) -> MenuOption | None:
    """The ❯-marked option, or None when no row is highlighted."""
    for opt in menu_options(text):
        if opt.highlighted:
            return opt
    return None


def is_usage_limit(text: str) -> bool:
    # Footer-scoped for the same reason as is_working: the banner renders near
    # the input box, while a response body may merely mention these phrases.
    return _contains_any(_footer(text), USAGE_LIMIT_MARKERS)


def parse_usage_reset(text: str) -> str | None:
    """Best-effort reset-time text from a usage-limit banner (e.g. "7:30pm"),
    or None. Format is version-fragile; calibration V5 tunes _RESET_RE."""
    m = _RESET_RE.search(text)
    return m.group(1).strip() if m else None


# --- /model picker ----------------------------------------------------------
def normalize_effort(label: str | None) -> str | None:
    """"xHigh (default)" -> "xhigh"; anything unrecognised -> None."""
    if not label:
        return None
    low = label.strip().lower()
    for token in EFFORT_TOKENS:
        if low == token or low.startswith(token + " ") or low.startswith(token + "("):
            return token
    return None


def normalize_model_label(label: str) -> str:
    """Compact casefold key: "Opus 5 (1M context)" -> "opus51mcontext". A
    leading "claude" is dropped so the CLI's full names ("claude-opus-5") and the
    picker's display labels ("Opus 5") reduce to the same thing."""
    key = _NON_ALNUM_RE.sub("", (label or "").lower())
    return key[len("claude"):] if key.startswith("claude") else key


def model_matches(label: str, target: str) -> bool:
    """Whether a picker row label denotes `target`. Deliberately loose in BOTH
    directions -- "opus" must match "Opus 5", and the full API name
    "claude-haiku-4-5-20251001" must match the row "Haiku 4.5" -- because the
    picker shows display labels while callers pass aliases or full names.

    Loose matching means several rows can match one target (Opus 4.1 and Opus
    4.6 both match "opus"); use matching_model_rows and refuse ambiguity rather
    than picking one."""
    a, b = normalize_model_label(label), normalize_model_label(target)
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def matching_model_rows(rows, target: str) -> list[ModelRow]:
    """Rows matching `target`, most specific first. Matching runs against the
    NAME column, not the whole row: the description mentions other model names
    ("Use /fast … (Opus 5)"), and matching those would pick the wrong row.

    An exact key match wins outright, so asking for "haiku" is unambiguous even
    though "Haiku 4.5 Pro" would also prefix-match."""
    key = normalize_model_label(target)
    exact = [r for r in rows if normalize_model_label(r.name) == key]
    return exact or [r for r in rows if model_matches(r.name, target)]


def is_model_dialog(text: str) -> bool:
    return _contains_any(text, MODEL_DIALOG_MARKERS)


def is_switch_confirm(text: str) -> bool:
    """The cache-invalidation confirm ("Switch model?" / "Change effort
    level?"). It only appears once the conversation has messages, so a fresh
    session never sees it -- and a mid-session change always does."""
    return _contains_any(text, SWITCH_CONFIRM_MARKERS)


def slash_input_echo(text: str, typed: str) -> bool:
    """Whether the composer shows what we typed. `in`, not equality: the command
    palette may autocomplete around the text as it is entered."""
    return typed.strip().lower() in text.lower()


def _is_model_noise(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in MODEL_NOISE_MARKERS)


def parse_model_dialog(text: str, row_flags=None) -> ModelDialog | None:
    """Parse the /model picker out of a FULL screen snapshot, or None when it is
    not showing.

    Pass `ScreenReader.row_flags()` as `row_flags` whenever available: it is the
    fallback that finds the highlight when the widget draws no ❯ pointer. The
    text must be the full screen (not tail()), or the flags will not line up.

    Region-scoped like current_mode/is_working: everything is read BELOW the
    "Select model" anchor, so the working footer's "thinking with xhigh effort"
    can never be mistaken for the dialog's effort widget."""
    lines = text.splitlines()
    anchor = None
    for i, line in enumerate(lines):
        if _contains_any(line, MODEL_DIALOG_MARKERS):
            anchor = i  # last match wins: the live dialog is the bottom-most
    if anchor is None:
        return None

    region = lines[anchor + 1:]
    rows: list[ModelRow] = []
    hidden = 0
    effort = None
    effort_is_default = False
    effort_supported = True
    persist_hint = session_only_hint = False
    seen_rows = False

    for offset, line in enumerate(region):
        stripped = line.strip()
        low = stripped.lower()
        if not stripped or set(stripped) <= set("─━-│┃|╭╮╰╯ "):
            continue
        if _is_model_noise(stripped):
            continue

        m = _MODEL_OVERFLOW_RE.search(stripped)
        if m:
            if not hidden:
                hidden = int(m.group(1))
            seen_rows = True
            continue
        if EFFORT_UNSUPPORTED in low:
            if effort is None:
                effort_supported = False
            seen_rows = True
            continue
        m = _EFFORT_LINE_RE.search(stripped)
        if m:
            # First occurrence wins. Anything further down the screen -- above
            # all the working spinner's "thinking with <X> effort" -- belongs to
            # the session, not to this dialog.
            if effort is None and effort_supported:
                effort = m.group(1).lower()
                effort_is_default = bool(m.group("dflt"))
            seen_rows = True
            continue
        if MODEL_PERSIST_HINT in low or MODEL_SESSION_HINT in low:
            persist_hint = persist_hint or MODEL_PERSIST_HINT in low
            session_only_hint = session_only_hint or MODEL_SESSION_HINT in low
            # The hint line is the dialog's last line: stop, so nothing painted
            # below it can be read back as part of the dialog.
            break
        if seen_rows:
            # Past the option list (effort widget / overflow already seen);
            # anything further is chrome we do not model.
            continue

        m = _MODEL_ROW_RE.match(line)
        if not m:
            continue
        label = m.group(3).strip()
        if not label:
            continue
        # Name column = everything before the first run of 2+ spaces. Rows with
        # no description degrade to name == label.
        name = _NAME_SPLIT_RE.split(label, 1)[0].strip()
        current = bool(_CURRENT_BADGE_RE.search(name))
        name = _CURRENT_BADGE_RE.sub("", name).strip()
        rows.append(ModelRow(label=label, name=name or label,
                             index=int(m.group(2)) if m.group(2) else None,
                             row=anchor + 1 + offset,
                             highlighted=m.group(1) is not None,
                             current=current))

    pointed = [r for r in rows if r.highlighted]
    if len(pointed) == 1:
        highlighted, source = pointed[0], "pointer"
    else:
        styled = []
        if row_flags:
            for r in rows:
                f = row_flags[r.row] if r.row < len(row_flags) else None
                if f and (f.get("bold") or f.get("colored") or f.get("reverse")):
                    styled.append(r)
        if len(styled) == 1:
            highlighted, source = styled[0], "style"
            highlighted.highlighted = True
        else:
            # Ambiguous or absent. NEVER guess -- the caller aborts on None.
            highlighted, source = None, "none"

    return ModelDialog(
        rows=rows, highlighted=highlighted, highlight_source=source,
        effort=effort, effort_is_default=effort_is_default,
        effort_supported=effort_supported, hidden_rows=hidden,
        persist_hint=persist_hint, session_only_hint=session_only_hint,
        raw="\n".join(l for l in region if l.strip()),
    )


def find_model_confirmations(text: str) -> list[ModelConfirmation]:
    """Every "Set model to …" line on screen, in order.

    A list, not a predicate: the confirmation is a scrollback system message, so
    one from an earlier change stays visible. Verification must compare a count
    taken BEFORE the change against one taken after -- the same baseline idiom
    the Stop-hook watcher uses."""
    out = []
    for m in _MODEL_CONFIRM_RE.finditer(text):
        scope = ("session" if "session only" in m.group("scope").lower()
                 else "default")
        out.append(ModelConfirmation(
            model=m.group("model").strip(),
            scope=scope,
            effort=normalize_effort(m.group("effort")),
            trailing=text[m.end():].split("\n", 1)[0].strip(),
            line=m.group(0).strip(),
        ))
    return out


def parse_model_confirmation(text: str) -> ModelConfirmation | None:
    found = find_model_confirmations(text)
    return found[-1] if found else None


def find_effort_confirmations(text: str) -> list[ModelConfirmation]:
    """Every "Set effort level to …" line, in order. Reuses ModelConfirmation
    with model="" — it is the same kind of evidence, and callers verify the same
    way (baseline count + scope check).

    An unreadable scope is reported as "default", the pessimistic side: a
    persist=False caller then fails loudly instead of silently accepting a
    change that may have rewritten the operator's global settings."""
    out = []
    for m in _EFFORT_CONFIRM_RE.finditer(text):
        raw_scope = (m.group("scope") or "").lower()
        out.append(ModelConfirmation(
            model="",
            scope="session" if "session only" in raw_scope else "default",
            effort=normalize_effort(m.group("effort")),
            trailing=text[m.end():].split("\n", 1)[0].strip(),
            line=m.group(0).strip(),
        ))
    return out


def parse_kept_model(text: str) -> str | None:
    """The "Kept model as <X>" line the confirm dialog prints when cancelled."""
    m = None
    for m in _KEPT_MODEL_RE.finditer(text):
        pass
    return m.group("model").strip() if m else None


def parse_kept_effort(text: str) -> str | None:
    m = None
    for m in _KEPT_EFFORT_RE.finditer(text):
        pass
    return normalize_effort(m.group("effort")) if m else None


def current_effort(text: str) -> str | None:
    """Effort from the working spinner, or None. The measured line looks like
    "✻ Burrowing… (3m 49s · ↓ 14.5k tokens · thinking with xhigh effort)".

    Deliberately conservative: footer-scoped AND the match must sit on a line
    carrying the spinner's "·" separator, so ordinary prose ("we were thinking
    with high effort") cannot trip it. Only rendered while a turn runs, so this
    is a bonus observation -- the transcript is the authority (calibration V18
    re-tunes it)."""
    for line in _footer(text).splitlines():
        if "·" not in line:
            continue
        m = _WORKING_EFFORT_RE.search(line)
        if m:
            return normalize_effort(m.group(1))
    return None
