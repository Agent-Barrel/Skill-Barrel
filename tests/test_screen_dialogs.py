"""Screen-side dialog classification, asserted against REAL captured screens.

Why these live on fixtures instead of hand-written strings: the transcript is
useless while an interaction waits (a pending tool_use is not written to the
JSONL until it resolves), so the screen is the only channel — and the real
screens turned out to contain layout traps nobody would think to write by hand.
See tests/fixtures/screens/README.md.
"""
from step2step.claude import screen as scr


def strip_blanks(text: str) -> str:
    """What ScreenReader.tail() / ExternalSession.text() hand a caller."""
    return "\n".join(ln for ln in text.splitlines() if ln.strip())


# --- classification ----------------------------------------------------------
def test_classifies_the_three_real_screens(screen):
    assert scr.classify_dialog(screen("plan_approval")) == "plan_approval"
    assert scr.classify_dialog(screen("ask_user_question_tabs")) == "question"
    assert scr.classify_dialog(screen("working_with_task_panel")) is None


def test_classification_survives_blank_stripping(screen):
    # Both screen sources drop blank rows, so no predicate may depend on them.
    for name, expected in (("plan_approval", "plan_approval"),
                           ("ask_user_question", "question"),
                           ("working_with_task_panel", None)):
        assert scr.classify_dialog(strip_blanks(screen(name))) == expected


def test_question_is_not_read_as_plan_approval(screen):
    assert scr.is_plan_approval(screen("ask_user_question_tabs")) is False


def test_plan_approval_wins_over_a_question_footer():
    # Both shapes on one screen: the approval is the one we answer with a key,
    # so it must win.
    both = ("Would you like to proceed?\n"
            " ❯ 1. Yes, and bypass permissions\n"
            "   2. Tell Claude what to change\n"
            "Enter to select · Tab/Arrow keys to navigate · Esc to cancel")
    assert scr.classify_dialog(both) == "plan_approval"


def test_numbered_list_without_a_dialog_footer_is_unknown():
    # Menu-shaped but carries neither dialog's wording: report "unknown" rather
    # than guessing, and never "question".
    assert scr.classify_dialog("1. alpha\n2. beta\n3. gamma") == "unknown"


def test_idle_input_box_is_not_a_dialog():
    assert scr.classify_dialog("output\n╭─────╮\n│ ❯   │\n╰─────╯") is None


# --- plan approval options ---------------------------------------------------
def test_plan_approval_options_from_the_real_menu(screen):
    opts = scr.plan_approval_options(screen("plan_approval"))
    assert [(o.index, o.label) for o in opts] == [
        (1, "Yes, and bypass permissions"),
        (2, "Yes, manually approve edits"),
        (3, "Tell Claude what to change"),
    ]
    assert opts[0].highlighted is True


def test_numbered_plan_body_is_not_parsed_as_options(screen):
    # The trap: the plan body above the anchor is numbered too. Reading it as
    # the menu would put Enter on a row nobody offered.
    opts = scr.plan_approval_options(screen("plan_approval_numbered_body"))
    assert [o.label for o in opts] == ["Yes, and bypass permissions",
                                       "Yes, manually approve edits",
                                       "Tell Claude what to change"]
    assert "trap" not in " ".join(o.label for o in opts)


def test_plan_approval_options_empty_without_an_anchor():
    assert scr.plan_approval_options("1. alpha\n2. beta") == []


def test_option_rows_survive_a_box_gutter():
    framed = ("│ Would you like to proceed?                │\n"
              "│ ❯ 1. Yes, and bypass permissions          │\n"
              "│   2. Tell Claude what to change           │")
    opts = scr.plan_approval_options(framed)
    assert [(o.index, o.label, o.highlighted) for o in opts] == [
        (1, "Yes, and bypass permissions", True),
        (2, "Tell Claude what to change", False)]


# --- question dialog ---------------------------------------------------------
def test_parse_question_dialog_reads_the_widget(screen):
    q = scr.parse_question_dialog(screen("ask_user_question_tabs"))
    assert q is not None
    assert q.question.startswith("캐시 계층을 프로세스 내 LRU로")
    assert q.question.endswith("설정 1줄로 되돌릴 수 있습니다.")
    assert q.tabs == ["캐시 계층", "재시도 정책", "로그 포맷", "배치 크기"]
    assert q.header == "캐시 계층"          # first tab still unanswered (☐)
    # Option 4 sits BELOW a separator; skipping separators is what finds it.
    assert [o.index for o in q.options] == [1, 2, 3, 4]
    assert q.options[0].highlighted is True
    assert q.descriptions[1].startswith("p99가 7배 빠르고")


def test_widget_affordances_are_not_model_options(screen):
    q = scr.parse_question_dialog(screen("ask_user_question_tabs"))
    assert [o.label for o in q.model_options] == ["인메모리 LRU (Recommended)",
                                                  "외부 스토어"]


def test_as_tool_input_matches_the_askuserquestion_shape(screen):
    got = scr.parse_question_dialog(screen("ask_user_question_tabs")).as_tool_input()
    assert list(got) == ["questions"] and len(got["questions"]) == 1
    one = got["questions"][0]
    assert set(one) == {"question", "header", "options"}
    assert one["header"] == "캐시 계층"
    assert [o["label"] for o in one["options"]] == ["인메모리 LRU (Recommended)",
                                                    "외부 스토어"]
    assert one["options"][1]["description"].startswith("히트율 5%p 우위")


def test_parse_question_dialog_survives_blank_stripping(screen):
    full = scr.parse_question_dialog(screen("ask_user_question_tabs"))
    tail = scr.parse_question_dialog(strip_blanks(screen("ask_user_question_tabs")))
    assert tail is not None
    assert tail.question == full.question
    assert tail.tabs == full.tabs
    assert [o.label for o in tail.options] == [o.label for o in full.options]


def test_parse_question_dialog_none_without_the_footer(screen):
    assert scr.parse_question_dialog(screen("plan_approval")) is None
    assert scr.parse_question_dialog(screen("working_with_task_panel")) is None


def test_question_below_a_task_panel_is_still_found(screen):
    # The regression this whole change exists for: the widget renders ABOVE the
    # task panel, so a 10-row tail misses the options entirely.
    text = screen("ask_user_question_tabs")
    rows = [ln for ln in text.splitlines() if ln.strip()]
    assert "tasks" in "\n".join(rows[-6:])       # panel really is below
    assert scr.classify_dialog(text) == "question"


def test_single_question_widget_has_a_header_row_not_a_tab_bar(screen):
    # Captured live: one question draws " ☐ Config format" with no arrows and no
    # Submit. Unparsed, that row runs into the question and a harness escalates
    # "☐ Config format Should the config file be JSON or YAML?" to a human.
    q = scr.parse_question_dialog(screen("ask_user_question"))
    assert q.question == "Should the config file be JSON or YAML?"
    assert q.tabs == ["Config format"] and q.header == "Config format"
    assert [o.label for o in q.model_options] == ["JSON", "YAML"]
    assert q.descriptions[2].startswith("More human-readable")


def test_footer_middle_phrase_varies_between_widget_shapes(screen):
    # "Tab/Arrow keys to navigate" (several questions) vs "↑/↓ to navigate"
    # (one) — both captured. Only the stable ends may be markers.
    one = screen("ask_user_question")
    many = screen("ask_user_question_tabs")
    assert "↑/↓ to navigate" in one and "Tab/Arrow keys to navigate" in many
    assert scr.classify_dialog(one) == scr.classify_dialog(many) == "question"


def test_task_panel_done_marks_are_not_question_headers(screen):
    # ✔/◻ rows in the task panel look like a header row; only ballot boxes count.
    q = scr.parse_question_dialog(screen("ask_user_question_tabs"))
    assert "AWS" not in q.question and "tasks" not in q.question


def test_single_question_widget_without_tabs():
    one = ("Which cache layer?\n"
           " ❯ 1. In-process LRU\n"
           "     Fastest p99.\n"
           "   2. External store\n"
           "Enter to select · Tab/Arrow keys to navigate · Esc to cancel")
    q = scr.parse_question_dialog(one)
    assert q.tabs == [] and q.header is None
    assert q.question == "Which cache layer?"
    assert [o.label for o in q.model_options] == ["In-process LRU",
                                                  "External store"]
    assert q.descriptions[1] == "Fastest p99."
