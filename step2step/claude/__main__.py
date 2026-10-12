"""CLI entry point: feed pre-defined prompts to a fresh Claude Code TUI session.

Examples:
    python -m step2step.claude --list --prompts prompts.md
    python -m step2step.claude --workdir test-folder --prompts prompts.md
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from .. import prompts as promptsmod
from .runner import EFFORT_LEVELS, Runner
from ..paths import REPO_ROOT, RUNTIME_DIR


def _make_logger(log_path: pathlib.Path):
    fh = open(log_path, "a", encoding="utf-8")

    def log(msg) -> None:
        line = str(msg)
        print(line, flush=True)
        try:
            fh.write(line + "\n")
            fh.flush()
        except Exception:
            pass

    return log, fh


def main(argv=None) -> int:
    # The TUI screen (shown by the stall handler) contains box-drawing chars; the
    # default Windows console codepage (e.g. cp949) can't encode them. Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        prog="step2step-claude",
        description="Feed pre-defined prompts to a fresh interactive Claude Code session.",
    )
    ap.add_argument("--workdir", help="directory Claude runs in")
    ap.add_argument("--prompts", required=True, help="path to the prompts markdown file")
    ap.add_argument("--claude", default=None, help="path to the claude executable")
    ap.add_argument("--hook-form", default="args", choices=["args", "shell"])
    ap.add_argument("--send-mode", default="paste", choices=["paste", "plain"])
    ap.add_argument("--on-stall", default="pause", choices=["pause", "skip", "abort"])
    ap.add_argument("--mode", default="bypass", choices=["bypass", "plan"],
                    help="bypass: hands-off direct execution; "
                         "plan: plan each prompt and auto-approve it")
    ap.add_argument("--model", default=None,
                    help="model for the session (--model): an alias like haiku/"
                         "opus/fable, or a full name like claude-opus-5")
    ap.add_argument("--effort", default=None, choices=list(EFFORT_LEVELS),
                    help="reasoning effort for the session (--effort); without "
                         "it the session follows your global effortLevel")
    ap.add_argument("--list", action="store_true", help="parse & print prompts, then exit")
    ap.add_argument("extra", nargs="*", help="extra args passed through to claude")
    args = ap.parse_args(argv)

    app_dir = REPO_ROOT

    prompts = promptsmod.load_prompts(args.prompts)
    if args.list:
        for i, p in enumerate(prompts, 1):
            print("--- prompt %d (%d chars) ---" % (i, len(p)))
            print(p)
        print("\n[total %d prompts]" % len(prompts))
        return 0
    if not prompts:
        print("No prompts found in", args.prompts)
        return 2
    if not args.workdir:
        print("--workdir is required (unless --list)")
        return 2

    runtime = RUNTIME_DIR
    runtime.mkdir(exist_ok=True)
    log, fh = _make_logger(runtime / "run.log")
    try:
        summary = Runner(
            workdir=args.workdir,
            prompts=prompts,
            app_dir=app_dir,
            claude_exe=args.claude,
            extra_args=args.extra,
            hook_form=args.hook_form,
            send_mode=args.send_mode,
            on_stall=args.on_stall,
            mode=args.mode,
            model=args.model,
            effort=args.effort,
            logger=log,
        ).run()
        log("[summary] %d/%d completed (mode=%s aborted=%s)"
            % (summary["completed"], summary["total"], summary["mode"], summary["aborted"]))
        for r in summary["results"]:
            log("  prompt %d: %s" % (r["index"], r["status"]))
    finally:
        fh.close()
    # Exit code so a calling harness / CI can detect failure from the CLI:
    #   0 = every prompt completed, not aborted; 1 = aborted or some incomplete.
    if summary["aborted"] or summary["completed"] != summary["total"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
