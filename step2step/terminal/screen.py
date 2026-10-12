"""Thread-safe terminal rendering and style inspection, independent of any product."""
from __future__ import annotations

import threading

import pyte


class ScreenReader:
    """Thread-safe pyte wrapper. The PTY reader thread calls feed(); the runner
    thread calls rows()/text()."""

    def __init__(self, cols: int, rows: int):
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)
        self._lock = threading.Lock()

    def feed(self, data) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        with self._lock:
            self.stream.feed(data)

    def rows(self) -> list[str]:
        with self._lock:
            return list(self.screen.display)

    def row_flags(self) -> list[dict]:
        """Per-row style summary, index-aligned with rows(): {"bold", "colored",
        "reverse"}. A row is flagged when ANY non-blank cell carries it.

        This is the style channel rows() throws away, and it is how a highlight
        is found when the widget draws no ❯ pointer. pyte tracks bold (SGR 1),
        reverse (SGR 7) and fg, but NOT dim (SGR 2) -- which is exactly what
        makes a bold+coloured focused row stand out from dimColor siblings."""
        with self._lock:
            out = []
            for y in range(self.screen.lines):
                # .get() so we never materialise rows the emulator never wrote.
                row = self.screen.buffer.get(y)
                bold = colored = reverse = False
                for cell in (row.values() if row else ()):
                    if not cell.data.strip():
                        continue
                    bold = bold or bool(cell.bold)
                    reverse = reverse or bool(cell.reverse)
                    colored = colored or (cell.fg != "default")
                out.append({"bold": bold, "colored": colored, "reverse": reverse})
            return out

    def text(self) -> str:
        return "\n".join(self.rows())

    def tail(self, n: int = 12) -> str:
        rows = [r for r in self.rows() if r.strip()]
        return "\n".join(rows[-n:])
