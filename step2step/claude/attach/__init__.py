"""Experimental: inject into an ALREADY-RUNNING (externally launched) Claude Code
session on Windows, instead of spawning + owning one via ConPTY (that is what
`step2step.claude` does).

The premise, established by research: on Windows a raw-mode Node/Ink TUI does not
read a VT byte stream from the console host -- libuv reads INPUT_RECORDs via
ReadConsoleInputW and synthesizes VT itself. So writing INPUT_RECORDs into the
target console's input buffer with WriteConsoleInput (after AttachConsole) is the
primitive that delivers keystrokes to a foreign session. Screen state is scraped
back non-destructively with ReadConsoleOutputCharacter (and optionally UI
Automation for Windows Terminal).

This package is a PROOF-OF-CONCEPT harness, not a finished feature.
"""
