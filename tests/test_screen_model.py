"""/model picker parsing: injected screen text (and real ANSI for row_flags).

The exact rendering is version-fragile and is pinned by calibration V12-V17;
what these tests lock down is the PARSER CONTRACT that the closed loop depends
on -- above all that an unreadable highlight comes back as None instead of a
guess, because a guess would commit the wrong model.
"""
import pytest

from step2step.claude import screen as scr

# 200x50 is the fixed geometry, so the body sentence is one line.
HEAD = (
    "  Select model\n"
    "  Switch between Claude models. Your pick becomes the default for new "
    "sessions. For other/previous model names, specify with --model.\n"
    "\n"
)
FOOT = "\n  Enter to set as default · s to use this session only · Esc to cancel\n"

# Verbatim from runtime/calib-model-*.txt (Claude Code 2.1.220, 200x50). Name and
# description are separated by a run of spaces; ✔ marks the active model.
MEASURED_ROWS = (
    "    1. Default (recommended)  Opus 5 with 1M context · Best for everyday, complex tasks\n"
    "    2. Opus (1M context)      Opus 5 with 1M context · Best for everyday, complex tasks\n"
    "    3. Fable                  Fable 5 · Most capable for your hardest and longest-running tasks\n"
    "    4. Sonnet                 Sonnet 5 · Efficient for routine tasks\n"
    "  ❯ 5. Haiku ✔                Haiku 4.5 · Fastest for quick answers"
)


def _dialog(rows, effort="  ◀ xHigh effort (default) ▶", extra=""):
    return HEAD + rows + "\n" + effort + extra + FOOT


NUMBERED = (
    "    1. Fable 5\n"
    "  ❯ 2. Opus 4.6\n"
    "    3. Sonnet 4.6\n"
    "    4. Haiku 4.5"
)
UNNUMBERED = (
    "    Fable 5\n"
    "  ❯ Opus 4.6\n"
    "    Sonnet 4.6\n"
    "    Haiku 4.5"
)
NO_POINTER = (
    "    Fable 5\n"
    "    Opus 4.6\n"
    "    Sonnet 4.6\n"
    "    Haiku 4.5"
)


# --- row parsing --------------------------------------------------------------
def test_numbered_and_unnumbered_rows_parse_the_same():
    a = scr.parse_model_dialog(_dialog(NUMBERED))
    b = scr.parse_model_dialog(_dialog(UNNUMBERED))
    assert [r.label for r in a.rows] == [r.label for r in b.rows] == [
        "Fable 5", "Opus 4.6", "Sonnet 4.6", "Haiku 4.5"]
    assert [r.index for r in a.rows] == [1, 2, 3, 4]
    assert [r.index for r in b.rows] == [None] * 4


def test_highlight_from_pointer():
    d = scr.parse_model_dialog(_dialog(NUMBERED))
    assert d.highlight_source == "pointer"
    assert d.highlighted.label == "Opus 4.6"


@pytest.mark.parametrize("marker", ["❯", ">", "›"])
def test_alternate_pointer_markers(marker):
    rows = "    Fable 5\n  %s Opus 4.6\n    Haiku 4.5" % marker
    assert scr.parse_model_dialog(_dialog(rows)).highlighted.label == "Opus 4.6"


def test_header_and_footer_are_never_rows():
    d = scr.parse_model_dialog(_dialog(NUMBERED))
    labels = " ".join(r.label.lower() for r in d.rows)
    for noise in ("switch between", "specify with", "set as default",
                  "use this session only", "effort"):
        assert noise not in labels


def test_currently_using_line_is_not_a_row():
    text = (HEAD + "  Currently using Opus 4.6 for this session only. "
            "Selecting a model will undo this.\n" + NUMBERED + FOOT)
    d = scr.parse_model_dialog(text)
    assert [r.label for r in d.rows] == ["Fable 5", "Opus 4.6", "Sonnet 4.6",
                                         "Haiku 4.5"]


@pytest.mark.parametrize("badge", ["✔", "(Current model)"])
def test_current_badge_is_flagged_and_kept_out_of_the_name(badge):
    rows = "    Fable 5\n  ❯ Opus %s\n    Haiku 4.5" % badge
    d = scr.parse_model_dialog(_dialog(rows))
    assert d.highlighted.name == "Opus"
    assert d.highlighted.current is True
    assert d.rows[0].current is False


def test_measured_row_shape_splits_name_from_description():
    """The v2.1.220 rendering, verbatim from a calibration capture."""
    d = scr.parse_model_dialog(_dialog(MEASURED_ROWS,
                                       effort="  ○ Low effort ←/→ to adjust"))
    assert [r.name for r in d.rows] == [
        "Default (recommended)", "Opus (1M context)", "Fable", "Sonnet", "Haiku"]
    assert d.rows[4].current is True          # the ✔ row
    assert [r.current for r in d.rows[:4]] == [False] * 4
    assert d.highlighted.name == "Haiku"
    assert d.effort == "low"


def test_description_words_do_not_win_the_match():
    """Every row's description says "Opus 5" somewhere ("Best for…", the /fast
    note). Matching must run on the name column or "opus" hits row 1."""
    d = scr.parse_model_dialog(_dialog(MEASURED_ROWS))
    got = scr.matching_model_rows(d.rows, "opus")
    assert [r.name for r in got] == ["Opus (1M context)"]


@pytest.mark.parametrize("target,expect", [
    ("haiku", "Haiku"),
    ("sonnet", "Sonnet"),
    ("fable", "Fable"),
    ("default", "Default (recommended)"),
    ("claude-haiku-4-5-20251001", "Haiku"),
])
def test_measured_rows_resolve_unambiguously(target, expect):
    d = scr.parse_model_dialog(_dialog(MEASURED_ROWS))
    got = scr.matching_model_rows(d.rows, target)
    assert [r.name for r in got] == [expect]


def test_measured_effort_unsupported_line():
    d = scr.parse_model_dialog(
        _dialog(MEASURED_ROWS, effort="  ○ Effort not supported for Haiku"))
    assert d.effort_supported is False and d.effort is None


def test_measured_footer_hints_and_fast_mode_note():
    d = scr.parse_model_dialog(
        _dialog(MEASURED_ROWS, effort="  ○ Low effort ←/→ to adjust",
                extra="\n  Use /fast to turn on Fast mode (Opus 5)."),
    )
    assert d.persist_hint is True and d.session_only_hint is True
    assert not any("fast mode" in r.label.lower() for r in d.rows)


def test_not_a_dialog_returns_none():
    assert scr.parse_model_dialog("just some output\nshift+tab to cycle") is None
    assert scr.is_model_dialog("just some output") is False


def test_plan_approval_menu_is_not_a_model_dialog():
    menu = ("Which option?\n ❯ 1. Yes, and bypass permissions\n"
            "   2. No, keep planning")
    assert scr.is_model_dialog(menu) is False


# --- the must-abort contract --------------------------------------------------
def test_no_pointer_and_no_flags_yields_no_highlight():
    d = scr.parse_model_dialog(_dialog(NO_POINTER))
    assert d.highlighted is None and d.highlight_source == "none"
    assert len(d.rows) == 4          # rows still parse; only the highlight is unknown


def test_two_pointers_yields_no_highlight():
    rows = "  ❯ Fable 5\n  ❯ Opus 4.6\n    Haiku 4.5"
    assert scr.parse_model_dialog(_dialog(rows)).highlighted is None


def test_two_styled_rows_yields_no_highlight():
    text = _dialog(NO_POINTER)
    flags = [{"bold": False, "colored": False, "reverse": False}
             for _ in text.splitlines()]
    for r in scr.parse_model_dialog(text).rows[:2]:
        flags[r.row] = {"bold": True, "colored": False, "reverse": False}
    d = scr.parse_model_dialog(text, row_flags=flags)
    assert d.highlighted is None and d.highlight_source == "none"


def test_highlight_from_style_when_no_pointer_is_drawn():
    text = _dialog(NO_POINTER)
    flags = [{"bold": False, "colored": False, "reverse": False}
             for _ in text.splitlines()]
    target = [r for r in scr.parse_model_dialog(text).rows
              if r.label == "Sonnet 4.6"][0]
    flags[target.row] = {"bold": True, "colored": True, "reverse": False}
    d = scr.parse_model_dialog(text, row_flags=flags)
    assert d.highlight_source == "style"
    assert d.highlighted.label == "Sonnet 4.6"
    assert d.highlighted.highlighted is True


def test_pointer_wins_over_style():
    text = _dialog(NUMBERED)
    flags = [{"bold": True, "colored": True, "reverse": False}
             for _ in text.splitlines()]
    d = scr.parse_model_dialog(text, row_flags=flags)
    assert d.highlight_source == "pointer" and d.highlighted.label == "Opus 4.6"


# --- effort widget ------------------------------------------------------------
@pytest.mark.parametrize("line,expect,dflt", [
    ("  ◀ xHigh effort (default) ▶", "xhigh", True),
    ("  ◀ xHigh effort ▶", "xhigh", False),
    ("  ◀ Max effort ▶", "max", False),
    ("  ◀ low effort ▶", "low", False),
    ("  ◀ Medium effort (default) ▶", "medium", True),
])
def test_effort_variants(line, expect, dflt):
    d = scr.parse_model_dialog(_dialog(NUMBERED, effort=line))
    assert (d.effort, d.effort_is_default, d.effort_supported) == (expect, dflt, True)


def test_effort_unsupported():
    d = scr.parse_model_dialog(_dialog(NUMBERED, effort="  ⚠ Effort not supported for Haiku 4.5"))
    assert d.effort_supported is False and d.effort is None


def test_working_footer_effort_cannot_leak_into_the_dialog():
    """Region scoping, in the spirit of the is_working footer regressions: a
    spinner line below the dialog must not become the dialog's effort."""
    text = (_dialog(NUMBERED, effort="  ◀ low effort ▶")
            + "\n✻ Burrowing… (3m 49s · ↓ 14.5k tokens · thinking with xhigh effort)")
    assert scr.parse_model_dialog(text).effort == "low"


def test_dialog_effort_does_not_confuse_current_effort():
    assert scr.current_effort(_dialog(NUMBERED)) is None
    assert scr.current_effort(
        "body\n" * 20 +
        "✻ Burrowing… (3m 49s · ↓ 14.5k tokens · thinking with xhigh effort)"
    ) == "xhigh"


def test_current_effort_not_tripped_by_prose():
    body = "we were thinking with high effort about this\n" * 3
    assert scr.current_effort(body + "\n" * 20 + "shift+tab to cycle") is None


# --- virtualization / footer hints --------------------------------------------
@pytest.mark.parametrize("marker", ["… +3 models", "... +3 models", "…  +3 model"])
def test_hidden_rows(marker):
    d = scr.parse_model_dialog(_dialog(NUMBERED, extra="\n  " + marker))
    assert d.hidden_rows == 3


def test_no_overflow_marker_means_zero_hidden():
    assert scr.parse_model_dialog(_dialog(NUMBERED)).hidden_rows == 0


def test_footer_hints():
    d = scr.parse_model_dialog(_dialog(NUMBERED))
    assert d.persist_hint is True and d.session_only_hint is True


def test_missing_session_hint_is_detected():
    text = HEAD + NUMBERED + "\n  ◀ xHigh effort ▶\n  enter confirm · esc cancel\n"
    d = scr.parse_model_dialog(text)
    assert d.session_only_hint is False and d.persist_hint is False


# --- confirmation lines -------------------------------------------------------
def test_confirmation_session_only():
    c = scr.parse_model_confirmation("Set model to Opus 4.6 for this session only")
    assert (c.model, c.scope, c.effort) == ("Opus 4.6", "session", None)


def test_confirmation_default():
    c = scr.parse_model_confirmation(
        "Set model to Opus 4.6 and saved as your default for new sessions")
    assert c.scope == "default"


def test_confirmation_with_effort():
    c = scr.parse_model_confirmation(
        "Set model to Opus 4.6 for this session only with xhigh effort")
    assert (c.model, c.scope, c.effort) == ("Opus 4.6", "session", "xhigh")


def test_confirmation_tolerates_appended_fast_mode_note():
    line = ("Set model to Opus 4.6 for this session only with max effort. "
            "Fast mode is ON and available with Opus 4.6 (/fast).")
    c = scr.parse_model_confirmation(line)
    assert (c.model, c.scope, c.effort) == ("Opus 4.6", "session", "max")
    assert "fast mode" in c.trailing.lower()


def test_find_confirmations_returns_all_in_order():
    text = ("Set model to Haiku 4.5 for this session only\n"
            "…\nSet model to Opus 4.6 and saved as your default for new sessions\n")
    found = scr.find_model_confirmations(text)
    assert [c.model for c in found] == ["Haiku 4.5", "Opus 4.6"]
    assert [c.scope for c in found] == ["session", "default"]


def test_no_confirmation():
    assert scr.find_model_confirmations("nothing here") == []
    assert scr.parse_model_confirmation("nothing here") is None


# --- switch confirm / kept lines ----------------------------------------------
def test_is_switch_confirm():
    for title in ("Switch model?", "Change effort level?"):
        assert scr.is_switch_confirm("body\n  %s\n  ..." % title) is True
    assert scr.is_switch_confirm("Select model\n  Opus 4.6") is False


def test_measured_switch_confirm_parses_with_the_existing_menu_parser():
    """Verbatim capture: the confirm is a plain numbered select with ❯, so it
    reuses menu_options — no new navigation code needed for it."""
    text = (
        "  Switch model?\n"
        "  Your next response will be slower and use more tokens\n"
        "  This conversation is cached for the current model. Switching to "
        "Opus 5 (1M context) (default) means the full history gets re-read on "
        "your next message.\n"
        "  ❯ 1. Yes, switch to Opus 5 (1M context) (default)\n"
        "    2. No, go back"
    )
    assert scr.is_switch_confirm(text) is True
    assert scr.parse_model_dialog(text) is None      # not the picker
    opt = scr.highlighted_option(text)
    assert opt.index == 1 and opt.label.lower().startswith(scr.SWITCH_ACCEPT_PREFIX)


def test_kept_lines_tolerate_the_transcript_gutter():
    """The TUI renders these system lines behind a "⎿  " gutter."""
    assert scr.parse_kept_model("  ⎿  Kept model as Haiku 4.5") == "Haiku 4.5"
    assert scr.parse_kept_effort("  ⎿  Kept effort level as xhigh") == "xhigh"
    assert scr.parse_kept_model("nothing") is None


def test_measured_confirmation_line_with_the_gutter():
    c = scr.parse_model_confirmation(
        "  ⎿  Set model to Haiku 4.5 and saved as your default for new sessions")
    assert (c.model, c.scope) == ("Haiku 4.5", "default")


# --- label matching -----------------------------------------------------------
@pytest.mark.parametrize("label,target", [
    ("Opus 4.6", "opus"),
    ("Opus 5 (1M context)", "opus"),
    ("Opus 5", "claude-opus-5"),
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
    ("Fable 5", "fable"),
    ("Default (recommended)", "default"),
])
def test_model_matches(label, target):
    assert scr.model_matches(label, target) is True


@pytest.mark.parametrize("label,target", [
    ("Sonnet 4.6", "opus"),
    ("Haiku 4.5", "fable"),
    ("Opus 4.6", ""),
])
def test_model_does_not_match(label, target):
    assert scr.model_matches(label, target) is False


def test_matching_rows_prefers_an_exact_key():
    rows = scr.parse_model_dialog(_dialog(
        "    Opus 4.6\n    Opus 4.6 Pro\n    Haiku 4.5")).rows
    got = scr.matching_model_rows(rows, "Opus 4.6")
    assert [r.label for r in got] == ["Opus 4.6"]


def test_matching_rows_reports_ambiguity():
    rows = scr.parse_model_dialog(_dialog(
        "    Opus 4.1\n    Opus 4.6\n    Haiku 4.5")).rows
    assert len(scr.matching_model_rows(rows, "opus")) == 2


def test_normalize_effort():
    assert scr.normalize_effort("xHigh (default)") == "xhigh"
    assert scr.normalize_effort("Max") == "max"
    assert scr.normalize_effort("ultracode") == "ultracode"
    assert scr.normalize_effort("nonsense") is None
    assert scr.normalize_effort(None) is None


def test_slash_input_echo_is_a_contains_check():
    assert scr.slash_input_echo("│ > /model sonnet          │", "/model sonnet")
    assert scr.slash_input_echo("│ > /model   ⟨model⟩ │", "/model")
    assert scr.slash_input_echo("│ >            │", "/model") is False


# --- key constants ------------------------------------------------------------
def test_arrow_and_escape_constants():
    assert scr.CURSOR_UP == "\x1b[A"
    assert scr.CURSOR_DOWN == "\x1b[B"
    assert scr.CURSOR_RIGHT == "\x1b[C"
    assert scr.CURSOR_LEFT == "\x1b[D"
    assert scr.ESCAPE == "\x1b"
