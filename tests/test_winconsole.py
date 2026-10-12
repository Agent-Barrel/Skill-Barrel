"""F12: text_records emits one KEY_EVENT per UTF-16 code unit (BMP = 1, astral =
surrogate pair = 2), and never raises on emoji."""
import sys

import pytest

if sys.platform != "win32":
    pytest.skip(
        "step2step.claude.attach drives the Win32 console (ctypes.WinDLL); "
        "Windows-only and not ported",
        allow_module_level=True,
    )

from step2step.terminal.attach import winconsole as wc


def test_external_session_backspace_sends_one_explicit_batch():
    from unittest.mock import Mock
    from step2step.terminal.attach.session import ExternalSession

    session = ExternalSession(123)
    session._con = Mock()
    session.backspace(3)
    session._con.write_records.assert_called_once()
    records = session._con.write_records.call_args.args[0]
    assert len(records) == 3
    for record in records:
        assert record.EventType == wc.KEY_EVENT
        assert record.Event.KeyEvent.bKeyDown
        assert record.Event.KeyEvent.uChar.UnicodeChar == "\x08"
        assert record.Event.KeyEvent.wVirtualKeyCode == wc.VK_BACK


def _wch(rec):
    u = rec.Event.KeyEvent.uChar.UnicodeChar
    return u if isinstance(u, int) else ord(u)


def test_ascii_one_record_each():
    recs = wc.text_records("Hi")
    assert len(recs) == 2
    assert [_wch(r) for r in recs] == [ord("H"), ord("i")]


def test_korean_bmp_one_record_each():
    recs = wc.text_records("안녕")
    assert len(recs) == 2
    assert [_wch(r) for r in recs] == [0xC548, 0xB155]


def test_emoji_surrogate_pair():
    recs = wc.text_records("\U0001F600")  # grinning face
    assert len(recs) == 2
    assert [_wch(r) for r in recs] == [0xD83D, 0xDE00]


def test_newline_is_return():
    recs = wc.text_records("\n")
    assert len(recs) == 1
    assert recs[0].Event.KeyEvent.wVirtualKeyCode == wc.VK_RETURN


def test_special_keys_present():
    for name in ("enter", "esc", "backspace", "shift_tab", "ctrl_c"):
        assert name in wc.SPECIAL_KEYS
        recs = wc.SPECIAL_KEYS[name]()
        assert recs and recs[0].EventType == wc.KEY_EVENT


def test_shift_tab_has_shift_state():
    rec = wc.SPECIAL_KEYS["shift_tab"]()[0]
    assert rec.Event.KeyEvent.dwControlKeyState & wc.SHIFT_PRESSED
    assert rec.Event.KeyEvent.wVirtualKeyCode == wc.VK_TAB
