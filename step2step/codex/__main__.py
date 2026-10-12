"""Separate Codex control CLI; no product-level provider selection policy."""
import argparse
import json
import sys

from ..contracts import ControlError
from ..prompts import load_prompts
from .runner import run_session


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m step2step.codex")
    parser.add_argument("--workdir")
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--list", action="store_true", help="List prompts without starting Codex")
    parser.add_argument("--codex", dest="codex_exe")
    parser.add_argument("--app-dir")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--mode", choices=["bypass", "plan"], default="bypass")
    parser.add_argument("--on-stall", choices=["abort", "skip", "pause"], default="abort")
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--turn-timeout", type=float, default=600.0)
    parser.add_argument("--stall-seconds", type=float, default=120.0)
    parser.add_argument("--approval-policy", choices=["never", "on-request", "untrusted"], default="never")
    parser.add_argument("--sandbox-mode", choices=["danger-full-access", "workspace-write", "read-only"], default="danger-full-access")
    args = parser.parse_args(argv)
    try:
        prompts = load_prompts(args.prompts)
        if args.list:
            for i, prompt in enumerate(prompts, 1):
                print(f"--- prompt {i} ---\n{prompt}")
            print(f"\n[total {len(prompts)} prompts]")
            return 0
        if not args.workdir:
            parser.error("--workdir is required unless --list is used")
        if not prompts:
            raise ValueError("the prompts file is empty")
        options = vars(args).copy()
        options.pop("list")
        options["prompts"] = prompts
        result = run_session(**options)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result["aborted"] or result["completed"] != result["total"])
    except (ControlError, OSError, ValueError) as exc:
        print(f"Codex control failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
