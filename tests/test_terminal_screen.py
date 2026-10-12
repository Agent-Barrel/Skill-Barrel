"""Terminal rendering is independent of product screen predicates."""
from step2step.terminal.screen import ScreenReader


def test_screen_renders_cursor_updates_and_nonblank_tail():
    screen = ScreenReader(20, 4)
    screen.feed("progress 10%\r\x1b[2Kdone\r\n\r\nready")
    assert screen.rows() == ["done".ljust(20), " " * 20, "ready".ljust(20), " " * 20]
    assert screen.text() == "\n".join(screen.rows())
    assert screen.tail(1).strip() == "ready"


def test_screen_accepts_bytes_and_replaces_invalid_utf8():
    screen = ScreenReader(20, 2)
    screen.feed("한글".encode("utf-8") + b"\xff")
    assert screen.text().strip() == "한글\ufffd"


# --- row_flags against a real pyte stream -------------------------------------
def test_row_flags_align_with_rows_and_find_the_styled_row():
    rd = ScreenReader(40, 6)
    rd.feed("plain\r\n\x1b[1m\x1b[36mfocused\x1b[0m\r\n\x1b[2mdim\x1b[0m\r\n")
    rows, flags = rd.rows(), rd.row_flags()
    assert len(rows) == len(flags) == 6
    hit = [i for i, f in enumerate(flags)
           if f["bold"] or f["colored"] or f["reverse"]]
    assert hit == [1] and rows[1].strip() == "focused"
    # dim collapses to plain in pyte -- that is what makes the focused row unique
    assert flags[2] == {"bold": False, "colored": False, "reverse": False}


def test_row_flags_detects_reverse_video():
    rd = ScreenReader(40, 3)
    rd.feed("a\r\n\x1b[7mselected\x1b[0m\r\n")
    assert rd.row_flags()[1]["reverse"] is True
