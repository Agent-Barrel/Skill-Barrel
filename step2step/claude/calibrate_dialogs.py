"""Live calibration for the two interactive dialogs: plan approval + question.

`screen.classify_dialog` decides what a waiting dialog IS, and it decides it
from version-fragile TUI wording. This tool drives a throwaway session into both
dialogs for real, dumps each screen with its style flags, and prints which
marker matched what — so a Claude Code upgrade that renames a string shows up
here as a row that stopped matching, not as a harness that quietly stops
answering questions.

It is a verification, not just a capture: the session is driven through
SessionHandle, so the run also asserts the outcome mapping
(AWAITING_PLAN_APPROVAL / AWAITING_MENU) and that a waiting question's content
arrives at all — which it can only do from the screen, since a pending
interaction has no tool_use row in the transcript (transcript.pending_tool_use).

Usage:
    python -m step2step.claude.calibrate_dialogs <workdir> [--model haiku] [--save]

    --save   copy the captures over tests/fixtures/screens/ (review the diff:
             a capture may carry whatever the session happened to print)
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import time

from . import screen as scr
from .session import SessionHandle, TurnOutcome
from ..paths import REPO_ROOT, RUNTIME_DIR

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "screens"

PLAN_PROMPT = ("Plan only: create hello.txt whose single line is HELLO. "
               "Keep the plan to two bullets. Do nothing else.")
QUESTION_PROMPT = (
    "Use the AskUserQuestion tool to ask me exactly one multiple-choice "
    "question: whether the config file should be json or yaml. Give two "
    "options, each with a one-line description. Ask only — change nothing.")
TURN_TIMEOUT = 300.0


def _utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _marker_table(text: str) -> list[str]:
    """Which of the version-fragile strings actually matched, one row each."""
    low = text.lower()
    rows = ["  classify_dialog -> %r" % scr.classify_dialog(text)]
    rows.append("  PLAN_APPROVAL_MARKERS:")
    for m in scr.PLAN_APPROVAL_MARKERS:
        rows.append("    [%s] %s" % ("x" if m in low else " ", m))
    rows.append("  PLAN_OPTION_ANCHORS:")
    for m in scr.PLAN_OPTION_ANCHORS:
        rows.append("    [%s] %s" % ("x" if m in low else " ", m))
    rows.append("  QUESTION_FOOTER_MARKERS:")
    for m in scr.QUESTION_FOOTER_MARKERS:
        rows.append("    [%s] %s" % ("x" if m in low else " ", m))
    opts = scr.plan_approval_options(text)
    rows.append("  plan_approval_options: %s"
                % ([(o.index, o.label, o.highlighted) for o in opts] or "(none)"))
    q = scr.parse_question_dialog(text)
    if q is None:
        rows.append("  parse_question_dialog: None")
    else:
        rows.append("  parse_question_dialog:")
        rows.append("    question: %s" % q.question[:120])
        rows.append("    tabs=%s header=%r" % (q.tabs, q.header))
        for o in q.options:
            mark = "*" if o.highlighted else " "
            rows.append("    %s%d. %s | %s"
                        % (mark, o.index, o.label, q.descriptions.get(o.index, "")))
        rows.append("    model_options: %s" % [o.label for o in q.model_options])
    return rows


def _wait_gone(handle, kind: str, timeout: float = 20.0) -> bool:
    """Poll until `kind` is no longer on screen.

    Needed after approve_plan()/interrupt(): the menu stays painted for a beat,
    and a wait_turn() issued into that afterimage truthfully reports the dialog
    it can still see. Callers that answer a dialog have to watch it go rather
    than immediately re-asking (barrel's plan-approval loop does the same)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if scr.classify_dialog(handle._runner.text()) != kind:
            return True
        time.sleep(0.5)
    return False


def _capture(handle, out_dir: pathlib.Path, name: str, report: list[str]) -> str:
    # rstrip: pyte pads every row to the terminal width, which makes a saved
    # capture unreadable as a fixture and its diffs meaningless.
    text = "\n".join(r.rstrip() for r in handle._runner.text().splitlines())
    (out_dir / (name + ".txt")).write_text(text, encoding="utf-8")
    flags = handle._runner.screen.row_flags()
    (out_dir / (name + ".flags.txt")).write_text(
        "\n".join("%3d %s %s" % (i, "".join(k[0] for k, v in f.items() if v) or "-",
                                 row)
                  for i, (f, row) in enumerate(zip(flags, handle._runner.screen.rows()))),
        encoding="utf-8")
    report.append("== %s ==" % name)
    report.extend(_marker_table(text))
    report.append("")
    return text


def main(argv=None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="step2step.claude.calibrate_dialogs")
    ap.add_argument("workdir")
    ap.add_argument("--model", default="haiku",
                    help="model alias for the throwaway session (default: haiku)")
    ap.add_argument("--save", action="store_true",
                    help="copy the captures over tests/fixtures/screens/")
    ap.add_argument("--answer", action="store_true",
                    help="calibration V2: answer the question widget with "
                         "answer_menu(1) instead of folding it, and verify the "
                         "turn then completes")
    args = ap.parse_args(argv)

    workdir = pathlib.Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_dir = RUNTIME_DIR / "calib-dialogs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: list[str] = []
    failures: list[str] = []

    print("[calib] starting a throwaway session (model=%s) in %s" % (args.model, workdir))
    handle = SessionHandle.start(workdir=str(workdir), mode="plan",
                                 model=args.model, logger=print)
    try:
        # --- 1) plan approval -------------------------------------------------
        print("[calib] turn 1: asking for a plan")
        pending = handle.send_prompt(PLAN_PROMPT)
        res = handle.wait_turn(pending, timeout=TURN_TIMEOUT)
        print("[calib] outcome=%s" % res.outcome.value)
        if res.outcome is not TurnOutcome.AWAITING_PLAN_APPROVAL:
            failures.append("turn 1 was %s, expected awaiting_plan_approval"
                            % res.outcome.value)
        _capture(handle, out_dir, "plan_approval", report)

        # Approving is part of the check: option 1 must still be the default
        # highlight, or every plan-mode caller silently picks the wrong row.
        opts = scr.plan_approval_options(handle._runner.text())
        first = next((o for o in opts if o.index == 1), None)
        if first is None or not first.label.lower().startswith("yes"):
            failures.append("option 1 is %r, expected a 'Yes, ...' row"
                            % (first.label if first else None))
        elif not first.highlighted:
            failures.append("option 1 is not the default highlight")
        else:
            print("[calib] approving (option 1: %s)" % first.label)
            handle.approve_plan()
            if not _wait_gone(handle, "plan_approval"):
                failures.append("the approval menu was still on screen 20s after "
                                "Enter — option 1 may no longer be the proceed row")
            res = handle.wait_turn(pending, timeout=TURN_TIMEOUT)
            print("[calib] post-approval outcome=%s mode=%s"
                  % (res.outcome.value, scr.current_mode(handle._runner.text())))
            if res.outcome not in (TurnOutcome.COMPLETED, TurnOutcome.COMPLETED_IDLE):
                failures.append("the approved turn ended as %s" % res.outcome.value)

        # --- 2) AskUserQuestion ----------------------------------------------
        print("[calib] turn 2: asking the session to raise a question widget")
        pending = handle.send_prompt(QUESTION_PROMPT)
        res = handle.wait_turn(pending, timeout=TURN_TIMEOUT)
        print("[calib] outcome=%s" % res.outcome.value)
        if res.outcome is not TurnOutcome.AWAITING_MENU:
            failures.append("turn 2 was %s, expected awaiting_menu (the session may "
                            "have answered in prose instead of using the tool)"
                            % res.outcome.value)
        _capture(handle, out_dir, "ask_user_question", report)
        got = res.pending
        if got is None or not got.questions:
            failures.append("the waiting question carried no content — the screen "
                            "parse is the only source and it came back empty")
        else:
            print("[calib] question source=%s text=%r"
                  % (got.source, got.questions[0].get("question", "")[:80]))
            report.append("== pending_interaction ==")
            report.append("  source: %s" % got.source)
            report.append("  questions: %r" % got.questions)
            report.append("")
        if args.answer and res.outcome is TurnOutcome.AWAITING_MENU:
            # V2: the closed loop presses arrows/Enter only against a verified
            # highlight, so a widget that ignores them fails here loudly
            # instead of silently in a harness.
            print("[calib] answering the widget with answer_menu(1)")
            try:
                handle.answer_menu(1)
                report.append("== answer_menu(1) == ok (widget resolved)")
                res = handle.wait_turn(pending, timeout=TURN_TIMEOUT)
                print("[calib] post-answer outcome=%s" % res.outcome.value)
                if res.outcome not in (TurnOutcome.COMPLETED, TurnOutcome.COMPLETED_IDLE):
                    failures.append("the answered turn ended as %s" % res.outcome.value)
            except Exception as exc:  # noqa: BLE001 -- the failure IS the finding
                failures.append("answer_menu(1) failed: %r (stage=%s)"
                                % (exc, getattr(exc, "stage", None)))
                report.append("== answer_menu(1) == FAILED %r" % (exc,))
                handle.interrupt()
            _capture(handle, out_dir, "after_answer", report)
        else:
            handle.interrupt()      # fold the menu; never a menu key
            if not _wait_gone(handle, "question"):
                failures.append("ESC did not fold the question widget within 20s")
            _capture(handle, out_dir, "after_interrupt", report)
    finally:
        try:
            handle.stop(force=True)
        except Exception as exc:  # noqa: BLE001
            print("[calib] stop failed: %r" % exc)

    report_path = out_dir / "report.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print("[calib] captures: %s" % out_dir)

    if args.save and not failures:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        for name in ("plan_approval", "ask_user_question"):
            shutil.copyfile(out_dir / (name + ".txt"), FIXTURES / (name + ".txt"))
        print("[calib] copied captures into %s — review the diff before committing"
              % FIXTURES)

    if failures:
        print("\n[calib] FAILURES:")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("\n[calib] OK — both dialogs classified and read from the screen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
