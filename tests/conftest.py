"""Shared test fixtures.

`screen` loads a captured Claude Code screen from tests/fixtures/screens/ — see
that directory's README for what each capture is and why it looks that way.
Predicates are asserted against REAL screens rather than hand-written strings so
a TUI change is caught by a re-capture, not by someone's memory of the layout.
"""
import pathlib

import pytest

SCREENS = pathlib.Path(__file__).parent / "fixtures" / "screens"


@pytest.fixture
def screen():
    def load(name: str) -> str:
        return (SCREENS / (name + ".txt")).read_text(encoding="utf-8")

    return load
