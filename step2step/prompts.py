"""Parse a prompts markdown file into an ordered list of prompt strings.

Convention (matches how the user authors the file):
- Prompt sections are separated by a line containing only ``---``.
- A leading YAML frontmatter block is skipped, but ONLY if it really is YAML
  (first non-blank line is ``---`` and every line up to the next ``---`` is a
  ``key:`` line). This way a leading ``---`` used purely as a separator is not
  mistaken for frontmatter.
- ``---`` lines inside fenced code blocks (``` or ~~~) are NOT separators, so a
  horizontal rule or YAML snippet inside a prompt won't split it.
"""
from __future__ import annotations

import pathlib
import re

_SEP_RE = re.compile(r"^\s*---\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_YAML_KEY_RE = re.compile(r"^\s*[A-Za-z_][\w-]*\s*:")


def _is_yaml_frontmatter(block: list[str]) -> bool:
    nonblank = [ln for ln in block if ln.strip()]
    return bool(nonblank) and all(_YAML_KEY_RE.match(ln) for ln in nonblank)


def parse_prompts(text: str) -> list[str]:
    text = text.lstrip("﻿")
    lines = text.splitlines()

    start = 0
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first is not None and _SEP_RE.match(lines[first]):
        close = next(
            (j for j in range(first + 1, len(lines)) if _SEP_RE.match(lines[j])),
            None,
        )
        if close is not None and _is_yaml_frontmatter(lines[first + 1 : close]):
            start = close + 1

    chunks: list[list[str]] = [[]]
    in_fence = False
    fence_tok: str | None = None
    for ln in lines[start:]:
        m = _FENCE_RE.match(ln)
        if m:
            tok = m.group(1)[0]  # ` or ~
            if not in_fence:
                in_fence, fence_tok = True, tok
            elif tok == fence_tok:
                in_fence, fence_tok = False, None
            chunks[-1].append(ln)
            continue
        if not in_fence and _SEP_RE.match(ln):
            chunks.append([])
        else:
            chunks[-1].append(ln)

    out = ["\n".join(c).strip() for c in chunks]
    return [c for c in out if c]


def load_prompts(path: str | pathlib.Path) -> list[str]:
    return parse_prompts(pathlib.Path(path).read_text(encoding="utf-8"))
