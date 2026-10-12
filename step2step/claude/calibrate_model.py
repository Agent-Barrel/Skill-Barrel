"""Marker-independent capture for the /model picker and /effort (V7-V21).

Sibling of `calibrate`, not a subcommand of it: that tool's CLI is positional and
documented, and this one has to do something it deliberately does not -- **send a
real prompt first**. The cache-invalidation confirm ("Switch model?") is gated on
the conversation already having messages, so a capture taken on an empty session
measures the wrong dialog entirely.

Safety: this never presses Enter inside the picker (that would rewrite the
operator's global default). It commits with 's' only, and SHA-256s
~/.claude/settings.json before and after every step so the dump proves whether
anything global moved.

Usage:
    python -m step2step.claude.calibrate_model <workdir> [model] [effort]

Read runtime/calib-model-<short>.txt afterwards and tune the screen module's
MODEL_* markers against it.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time
import uuid

from . import hooks
from . import screen as scr
from ..terminal.pty_session import PtySession
from ..terminal.screen import ScreenReader
from .runner import BRACKET_START, BRACKET_END, COLS, ENTER, ROWS, child_env, resolve_claude
from ..paths import RUNTIME_DIR

SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
CHAR_DELAY = 0.03
STEP_PAUSE = 0.8


def settings_bytes() -> bytes | None:
    try:
        return SETTINGS_PATH.read_bytes()
    except OSError:
        return None


def settings_digest() -> str:
    """SHA-256 of the user's global settings, or a marker. The whole point of
    committing with 's' is that this must not change."""
    raw = settings_bytes()
    return hashlib.sha256(raw).hexdigest()[:16] if raw is not None else "(unreadable)"


def settings_keys() -> str:
    """The two global keys a model/effort change can move. A digest only says
    "something moved"; this says WHICH -- and the s-commit turned out to move
    one of them but not the other, which a digest could never have shown."""
    raw = settings_bytes()
    if raw is None:
        return "(unreadable)"
    try:
        data = json.loads(raw)
    except Exception:
        return "(unparseable)"
    return "model=%r effortLevel=%r" % (data.get("model"), data.get("effortLevel"))


def restore_settings(original: bytes | None) -> str:
    """Put the operator's global settings back.

    V10/V11 measure whether the ARGUMENT forms (`/model x`, `/effort x`) persist
    globally -- and the only way to measure that is to let them try. This undoes
    it. Running a calibration must never leave the operator on a different
    default model than they started on."""
    if original is None:
        return "no baseline"
    if settings_bytes() == original:
        return "unchanged"
    try:
        SETTINGS_PATH.write_bytes(original)
        return "RESTORED (a step had rewritten it)"
    except OSError as e:
        return "RESTORE FAILED: %r" % e


class Capture:
    def __init__(self, path: pathlib.Path, screen: ScreenReader, pty: PtySession):
        self.fh = open(path, "w", encoding="utf-8")
        self.screen = screen
        self.pty = pty
        self.t0 = time.monotonic()
        self.baseline_digest = settings_digest()

    def snap(self, tag: str) -> None:
        text = self.screen.text()
        flags = self.screen.row_flags()
        dialog = scr.parse_model_dialog(text, row_flags=flags)
        digest = settings_digest()
        self.fh.write(
            "\n===== %s | t=%.1f =====\n"
            "predicates: model_dialog=%s switch_confirm=%s working=%s idle=%s "
            "question=%s\n"
            "settings.json: %s%s | %s\n"
            % (tag, time.monotonic() - self.t0,
               scr.is_model_dialog(text), scr.is_switch_confirm(text),
               scr.is_working(text), scr.looks_idle(text),
               scr.looks_like_question(text),
               digest,
               "  <-- CHANGED from %s" % self.baseline_digest
               if digest != self.baseline_digest else " (unchanged)",
               settings_keys())
        )
        if dialog is None:
            self.fh.write("parse_model_dialog: None\n")
        else:
            self.fh.write(
                "parse_model_dialog: highlighted=%r source=%s effort=%r "
                "default=%s supported=%s hidden=%d persist_hint=%s "
                "session_hint=%s\n  rows=%r\n"
                % (dialog.highlighted.label if dialog.highlighted else None,
                   dialog.highlight_source, dialog.effort,
                   dialog.effort_is_default, dialog.effort_supported,
                   dialog.hidden_rows, dialog.persist_hint,
                   dialog.session_only_hint,
                   [(r.label, r.index, r.highlighted, r.current)
                    for r in dialog.rows])
            )
        confirms = scr.find_model_confirmations(text)
        if confirms:
            self.fh.write("confirmations: %r\n"
                          % [(c.model, c.scope, c.effort) for c in confirms])
        eff = scr.find_effort_confirmations(text)
        if eff:
            self.fh.write("effort_confirmations: %r\n"
                          % [(c.effort, c.scope) for c in eff])
        kept = scr.parse_kept_model(text)
        if kept:
            self.fh.write("kept_model: %r\n" % kept)
        menu = scr.menu_options(text)
        if menu:
            self.fh.write("menu_options: %r\n"
                          % [(o.index, o.label, o.highlighted) for o in menu])
        # Rows with their style flags: THE evidence for V13 (how the picker
        # marks its focused row when it draws no pointer).
        self.fh.write("--- rows (| bold/colored/reverse) ---\n")
        for i, (line, f) in enumerate(zip(text.splitlines(), flags)):
            if not line.strip():
                continue
            self.fh.write("%3d |%s%s%s| %s\n"
                          % (i, "B" if f["bold"] else " ",
                             "C" if f["colored"] else " ",
                             "R" if f["reverse"] else " ", line.rstrip()))
        self.fh.flush()

    def key(self, tag: str, keys: str, pause: float = STEP_PAUSE) -> None:
        self.snap("pre-" + tag)
        self.pty.write(keys)
        time.sleep(pause)
        self.snap("post-" + tag)

    def type_slow(self, tag: str, text: str) -> None:
        """Per-character typing: a pasted slash command does not open the
        command palette (measured; see the substrate findings doc)."""
        self.snap("pre-type-" + tag)
        for ch in text:
            self.pty.write(ch)
            time.sleep(CHAR_DELAY)
        time.sleep(0.6)
        self.snap("post-type-" + tag)

    def settle_idle(self, tag: str, tries: int = 5) -> bool:
        """ESC until no dialog is up. Without this every later phase types into
        whatever the previous phase left open, and the whole capture measures
        the wrong screen (that is exactly what the first run did)."""
        for i in range(tries):
            text = self.screen.text()
            if not scr.is_model_dialog(text) and not scr.is_switch_confirm(text):
                self.snap("idle-ok-" + tag)
                return True
            self.pty.write(scr.ESCAPE)
            time.sleep(1.0)
        self.snap("idle-FAILED-" + tag)
        return False

    def close(self) -> None:
        self.fh.write("\nfinal settings.json digest: %s (baseline %s)\n"
                      % (settings_digest(), self.baseline_digest))
        self.fh.close()


def main() -> int:
    workdir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    model = sys.argv[2] if len(sys.argv) > 2 else "haiku"
    effort = sys.argv[3] if len(sys.argv) > 3 else "low"

    runtime = RUNTIME_DIR
    runtime.mkdir(exist_ok=True)
    pathlib.Path(workdir).mkdir(parents=True, exist_ok=True)

    sid = str(uuid.uuid4())
    short = sid[:8]
    hook_script = hooks.write_signal_hook(runtime / "signal_hook.py")
    sig = runtime / ("calibm-%s.signal" % short)
    watcher = hooks.SignalWatcher(sig)
    watcher.reset()
    settings_file = runtime / ("calibm-settings-%s.json" % short)
    hooks.write_settings(
        settings_file,
        hooks.build_settings(pathlib.Path(sys.executable), hook_script, sig,
                             form="args"),
    )

    # V7/V8: does --effort launch cleanly in the interactive TUI, next to
    # --model and --dangerously-skip-permissions?
    argv = [
        resolve_claude(),
        "--session-id", sid,
        "--settings", str(settings_file),
        "--dangerously-skip-permissions",
        "--model", model,
        "--effort", effort,
    ]

    original_settings = settings_bytes()
    screen = ScreenReader(COLS, ROWS)
    pty = PtySession(
        argv, cwd=workdir, cols=COLS, rows=ROWS, env=child_env(),
        raw_log_path=str(runtime / ("calibm-pty-%s.log" % short)),
        on_data=screen.feed,
    )
    dump_path = runtime / ("calib-model-%s.txt" % short)
    pty.spawn()
    cap = Capture(dump_path, screen, pty)
    cap.fh.write("argv: %s\n" % " ".join(argv))

    try:
        # --- boot -----------------------------------------------------------
        for _ in range(60):
            if scr.looks_idle(screen.text()) and not scr.is_working(screen.text()):
                break
            time.sleep(1.0)
        cap.snap("booted")

        # --- one real turn, so the conversation has messages (V12 needs it) --
        cap.snap("pre-prompt")
        pty.write(BRACKET_START + "reply with exactly PONG" + BRACKET_END)
        time.sleep(0.2)
        pty.write(ENTER)
        for _ in range(120):
            if watcher.count() > 0:
                break
            time.sleep(1.0)
        time.sleep(2.0)
        cap.snap("after-turn-1")

        # --- V17c: does a plain 's' commit (effort UNTOUCHED) drag the
        # session's effort into the operator's global settings? This has to run
        # FIRST, while global settings are still pristine, or a later phase's
        # write would mask it.
        cap.type_slow("slash-model-0", "/model")
        cap.key("open-picker-0", ENTER, pause=2.5)
        cap.key("commit-s-untouched", "s", pause=2.5)
        if scr.is_switch_confirm(screen.text()):
            cap.key("accept-switch-0", ENTER, pause=3.0)
        cap.snap("after-commit-s-untouched")
        cap.settle_idle("after-probe-0")

        # --- V9/V13/V14/V15: open the picker --------------------------------
        cap.type_slow("slash-model", "/model")
        cap.key("open-picker", ENTER, pause=2.5)

        # --- V13/V14: vertical navigation -----------------------------------
        for i in range(3):
            cap.key("down-%d" % (i + 1), scr.CURSOR_DOWN, pause=0.6)
        for i in range(2):
            cap.key("up-%d" % (i + 1), scr.CURSOR_UP, pause=0.6)

        # --- V15/V16: horizontal = effort, and does the row stay put? -------
        for i in range(4):
            cap.key("right-%d" % (i + 1), scr.CURSOR_RIGHT, pause=0.6)
        for i in range(2):
            cap.key("left-%d" % (i + 1), scr.CURSOR_LEFT, pause=0.6)

        # --- V16: does Right wrap at the top of the effort range? -----------
        for i in range(3):
            cap.key("right-past-end-%d" % (i + 1), scr.CURSOR_RIGHT, pause=0.6)

        # --- V19: Esc must be a true no-op ----------------------------------
        cap.key("esc-picker", scr.ESCAPE, pause=1.5)

        # --- V17: reopen and commit with 's' (NEVER Enter), then V12 --------
        cap.settle_idle("before-commit")
        cap.type_slow("slash-model-2", "/model")
        cap.key("open-picker-2", ENTER, pause=2.5)
        cap.key("down-commit", scr.CURSOR_DOWN, pause=0.6)
        cap.key("commit-s", "s", pause=2.5)
        # V12: the cache-invalidation confirm. Accept it via its highlighted
        # option 1 and capture the resulting system line -- this is the half of
        # V17 the first run never reached.
        if scr.is_switch_confirm(screen.text()):
            cap.key("accept-switch", ENTER, pause=3.0)
        cap.snap("after-commit-s")

        # --- V10: the argument form, from a KNOWN-idle screen ---------------
        cap.settle_idle("before-model-arg")
        cap.type_slow("slash-model-arg", "/model %s" % model)
        cap.key("submit-model-arg", ENTER, pause=3.0)
        if scr.is_switch_confirm(screen.text()):
            cap.key("accept-switch-model-arg", ENTER, pause=3.0)
        cap.snap("after-model-arg")

        # --- V11: /effort with an argument ----------------------------------
        cap.settle_idle("before-effort-arg")
        cap.type_slow("slash-effort-arg", "/effort %s" % effort)
        cap.key("submit-effort-arg", ENTER, pause=3.0)
        if scr.is_switch_confirm(screen.text()):
            cap.key("accept-switch-effort-arg", ENTER, pause=3.0)
        cap.snap("after-effort-arg")

        # --- V20: the bare /effort slider (evidence for never opening it) ---
        cap.settle_idle("before-effort-bare")
        cap.type_slow("slash-effort-bare", "/effort")
        cap.key("open-effort-slider", ENTER, pause=2.5)
        cap.key("esc-effort-slider", scr.ESCAPE, pause=1.5)
        cap.settle_idle("after-effort-bare")

        # --- V17b: can a SESSION-ONLY effort change be committed at all? ----
        # The only session-scoped effort path is the picker's arrow keys plus
        # 's' -- `/effort <level>` always writes the global default. So: land on
        # a model that supports effort, move it, commit with 's', and check the
        # confirmation carries a "with <X> effort" clause.
        cap.settle_idle("before-effort-via-picker")
        cap.type_slow("slash-model-3", "/model")
        cap.key("open-picker-3", ENTER, pause=2.5)
        for i in range(6):                      # walk to a row that has effort
            d = scr.parse_model_dialog(screen.text(), row_flags=screen.row_flags())
            if d and d.effort_supported and d.effort:
                break
            cap.key("seek-effort-row-%d" % (i + 1), scr.CURSOR_DOWN, pause=0.6)
        cap.key("effort-left", scr.CURSOR_LEFT, pause=0.8)
        cap.key("effort-commit-s", "s", pause=2.5)
        if scr.is_switch_confirm(screen.text()):
            cap.key("accept-switch-effort", ENTER, pause=3.0)
        cap.snap("after-effort-via-picker")

        # --- V18: does a following turn report the new model/effort? --------
        pty.write(BRACKET_START + "reply with exactly PONG2" + BRACKET_END)
        time.sleep(0.2)
        pty.write(ENTER)
        base = watcher.count()
        for _ in range(120):
            if watcher.count() > base:
                break
            time.sleep(1.0)
        time.sleep(2.0)
        cap.snap("after-turn-2")
    finally:
        cap.close()
        restored = restore_settings(original_settings)
        with open(dump_path, "a", encoding="utf-8") as fh:
            fh.write("global settings: %s\n" % restored)
        try:
            if pty.isalive():
                pty.sendcontrol("c")
                time.sleep(0.4)
            if pty.isalive():
                pty.sendcontrol("c")
                time.sleep(0.6)
            if pty.isalive():
                pty.terminate()
        except Exception:
            pass
        pty.close_log()

    from . import transcript as tx
    print("DUMP     :", dump_path)
    print("RAW      :", runtime / ("calibm-pty-%s.log" % short))
    print("SIGNALS  :", watcher.count())
    print("SETTINGS :", settings_digest(), "(baseline %s) -> %s"
          % (cap.baseline_digest, restored))
    print("TRANSCRIPT:", tx.last_model_effort(tx.find_transcript(sid)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
