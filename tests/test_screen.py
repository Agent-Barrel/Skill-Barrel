from step2step.claude import screen as scr


def test_working_detected_in_footer():
    working = "output\n" * 20 + "✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"
    assert scr.is_working(working) is True


def test_working_not_triggered_by_prose():
    # D4 regression: the phrase in the response BODY, with an idle input box at the
    # bottom, must NOT read as working (footer scoping is what saves this).
    screen = ("The docs note that 'esc to interrupt' cancels the current turn.\n"
              + "further explanation line\n" * 12
              + "╭────────╮\n│ ❯      │\n╰────────╯\n? for shortcuts")
    assert scr.is_working(screen) is False


def test_current_mode_reads_real_footer_bottom_up():
    # D6 regression: a transcript line above must not win over the real footer.
    poisoned = ("Assistant: press shift+tab to cycle through plan options.\n"
                + "body\n" * 5
                + "⏵⏵ bypass permissions on (shift+tab to cycle)")
    assert scr.current_mode(poisoned) == "bypass"


def test_current_mode_plan():
    assert scr.current_mode("⏸ plan mode on (shift+tab to cycle)") == "plan"


def test_current_mode_none_without_footer():
    assert scr.current_mode("just some text\nno footer here") is None


def test_looks_like_question_numbered_menu():
    # Still True by design; the runner gates the guard on idle-fallback, not this.
    assert scr.looks_like_question("1. alpha\n2. beta\n3. gamma") is True


def test_empty_input_box_not_question():
    assert scr.looks_like_question("output\n╭─────╮\n│ ❯   │\n╰─────╯") is False


def test_plan_approval_detected():
    menu = "Would you like to proceed?\n1. Yes, and bypass permissions\n2. No, keep planning"
    assert scr.is_plan_approval(menu) is True


def test_looks_idle_input_box():
    assert scr.looks_idle("╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle") is True
