"""범용 유닛 루프 드라이버 -- 로드맵의 유닛들을 세션 하나씩으로 자율 완주시킨다.

    .venv/bin/python orchestration/drivers/unit_loop.py --config orchestration/fixtures/my-run.json
    (Windows: .venv\\Scripts\\python)

옵션: --only U3 [--only U4 …] (일부 유닛만), --dry-run (설정·preflight·프롬프트 미리보기·
fail-first 게이트만, 세션 미기동), --results-dir / --log (기본 orchestration/results/<name>,
orchestration/logs/<name>.log -- 둘 다 gitignore). 진행 상태는 results/<name>/state.json이라
대상 레포에 부기 파일이 생기지 않고, 재실행하면 done인 유닛은 건너뛴다. 곱게 멈추려면
`touch orchestration/results/<name>/<name>.stop` 또는 대상 레포에 `.unit-loop-stop`.

설정 예시는 orchestration/fixtures/unit_loop.example.json, 엔진은 barrel/core/unitloop.py.
종료 코드: 0 전 유닛 done · 2 blocked/halt(사람 검토) · 3 설정/preflight 실패 · 4 중지 파일.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from barrel.core import unitloop  # noqa: E402


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True, help="실행 설정 JSON")
    ap.add_argument("--only", action="append", default=[], help="이 유닛 id만(반복 가능)")
    ap.add_argument("--dry-run", action="store_true",
                    help="세션 없이 설정·preflight·프롬프트 미리보기·fail-first 게이트만")
    ap.add_argument("--results-dir", default=None, help="기본 orchestration/results/<name>")
    ap.add_argument("--log", default=None, help="기본 orchestration/logs/<name>.log")
    args = ap.parse_args()

    try:
        cfg = unitloop.load_config(args.config)
    except (OSError, ValueError) as exc:
        print(f"[config] cannot load {args.config}: {exc}", file=sys.stderr)
        return unitloop.EXIT_CONFIG
    name = cfg.get("name") or "unit-loop"
    results_dir = Path(args.results_dir) if args.results_dir else REPO / "orchestration" / "results" / name
    log_path = Path(args.log) if args.log else REPO / "orchestration" / "logs" / f"{name}.log"
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log_path, "a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    errors = unitloop.validate_config(cfg)
    if errors:
        for e in errors:
            log(f"[config] {e}")
        return unitloop.EXIT_CONFIG
    roadmap = Path(cfg["target_repo"]) / cfg["roadmap"]
    try:
        units = unitloop.load_roadmap(roadmap, default_timeout=int(cfg["gates"]["timeout_seconds"]))
    except (OSError, ValueError) as exc:
        log(f"[roadmap] {exc}")
        return unitloop.EXIT_CONFIG
    loop = unitloop.UnitLoop(cfg, units, results_dir=results_dir, log=log)
    try:
        code = loop.run(only=args.only or None, dry_run=args.dry_run)
    finally:
        logf.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
