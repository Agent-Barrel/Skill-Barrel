"""S1/S2/S4: menu parsing, usage-limit detection, cursor-key constants."""
from step2step.claude import screen as scr

MENU = ("Would you like to proceed?\n"
        " ❯ 1. Yes, and bypass permissions\n"
        "   2. Yes, manually approve edits\n"
        "   3. No, keep planning\n")


# --- S1: menu_options / highlighted_option -----------------------------------
def test_menu_options_parse():
    opts = scr.menu_options(MENU)
    assert [(o.index, o.highlighted) for o in opts] == [
        (1, True), (2, False), (3, False)]
    assert opts[0].label == "Yes, and bypass permissions"
    assert opts[2].label == "No, keep planning"


def test_menu_labels_stripped():
    # pyte rows are space-padded to the screen width.
    opts = scr.menu_options(" ❯ 1. alpha            ")
    assert opts[0].label == "alpha"


def test_menu_alt_highlight_markers():
    assert scr.menu_options(" > 2. beta")[0].highlighted is True
    assert scr.menu_options(" › 3. gamma")[0].highlighted is True


def test_menu_paren_numbering():
    opts = scr.menu_options("1) alpha\n2) beta")
    assert [o.index for o in opts] == [1, 2]
    assert not any(o.highlighted for o in opts)


def test_highlighted_option():
    got = scr.highlighted_option(MENU)
    assert got is not None and got.index == 1
    assert scr.highlighted_option("1. alpha\n2. beta") is None


def test_no_menu_on_plain_screen():
    plain = "just prose\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
    assert scr.menu_options(plain) == []
    assert scr.highlighted_option(plain) is None


def test_empty_label_is_not_an_option():
    assert scr.menu_options("1. \n2.    ") == []


# --- S2: usage-limit detection -----------------------------------------------
def test_usage_limit_detected_in_footer():
    screen = ("body\n" * 20
              + "You've reached your usage limit · resets at 7pm\n"
              + "╭──╮\n│ ❯│\n╰──╯")
    assert scr.is_usage_limit(screen) is True


def test_usage_limit_not_tripped_by_body_prose():
    # The phrase in the response BODY, pushed out of the footer region by an
    # idle input box, must NOT read as a usage limit (same D4 footer scoping).
    screen = ("Docs: a 'usage limit reached' banner appears when quota runs out.\n"
              + "further explanation line\n" * 12
              + "╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle")
    assert scr.is_usage_limit(screen) is False


def test_parse_usage_reset_variants():
    assert scr.parse_usage_reset("Your limit will reset at 7:30pm · daily") == "7:30pm"
    assert scr.parse_usage_reset("usage resets 9am") == "9am"
    assert scr.parse_usage_reset("no times mentioned here") is None


# --- S4: cursor-key constants ------------------------------------------------
def test_cursor_key_constants():
    assert scr.CURSOR_UP == "\x1b[A"
    assert scr.CURSOR_DOWN == "\x1b[B"
