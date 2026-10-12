"""다층 게이트 -- 존재 / 빌드 / 단위 / 행위 / 통합 / 성능.

자율 실행 기록(04 §2·§3·§7)의 세 규칙을 코드로 옮긴다.
- 게이트는 단일 명령이 아니라 **층**이다. 층마다 비용이 다르니 `every_turn=False`인
  비싼 층은 나머지가 통과한 뒤에만 돈다.
- 게이트는 **통과 전에 반드시 실패해야 한다**. 유닛 착수 전 기준선에서 전 층이
  통과하면 그 게이트는 아무것도 판정하지 못하는 것이고(사고 1), 그것은 결함이다.
- 비싼 게이트가 싸게 통과하면 의심한다. 기록의 중앙값 20% 미만(또는 선언값의 10%
  미만)이면 재실행해 둘 다 통과를 요구하고, 측정형 게이트는 산출물이 갱신됐는지 본다.

`exists` 층은 명령 없이 선언으로 판정한다(파일 존재·심볼 grep) -- 사고 1의 응급
처치였던 "존재 표식"의 정식 자리다.
"""
from __future__ import annotations

import pathlib
import re
import statistics
import time
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from . import verify

LAYERS = ("exists", "build", "unit", "behavior", "integration", "perf")
DEFAULT_TIMEOUT = 3600
_SKIP_DIRS = {".git", "target", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


@dataclass
class GateLayer:
    name: str
    spec: Any
    timeout: int = DEFAULT_TIMEOUT
    every_turn: bool = True
    must_fail_before: bool = True

    def display(self, repo=None) -> str:
        if self.name == "exists":
            return _exists_display(self.spec)
        gate, error = verify.resolve_gate(repo, self.spec)
        return gate.display() if gate else f"<invalid gate: {error}>"


def parse_layers(spec: dict[str, Any] | None, *, default_timeout: int = DEFAULT_TIMEOUT
                 ) -> list[GateLayer]:
    """로드맵 유닛의 `gates` 매핑 → 층 목록(LAYERS 순서). 값은 게이트 spec 그대로이거나
    `{"spec": ..., "every_turn": bool, "timeout": n, "must_fail_before": bool}`."""
    if not spec:
        return []
    unknown = sorted(set(spec) - set(LAYERS))
    if unknown:
        raise ValueError(f"unknown gate layer(s) {unknown}; layers are {list(LAYERS)}")
    layers: list[GateLayer] = []
    for name in LAYERS:
        if name not in spec:
            continue
        value = spec[name]
        opts: dict[str, Any] = {}
        if isinstance(value, dict) and "spec" in value:
            opts, value = value, value["spec"]
        layers.append(GateLayer(
            name=name, spec=value,
            timeout=int(opts.get("timeout", default_timeout)),
            every_turn=bool(opts.get("every_turn", name not in ("integration", "perf"))),
            must_fail_before=bool(opts.get("must_fail_before", True)),
        ))
    return layers


# --- exists 층 --------------------------------------------------------------

def _exists_display(spec: Any) -> str:
    paths, symbols = _exists_parts(spec)
    parts = [f"exists {p}" for p in paths]
    parts += [f"grep {s['pattern']!r} in {s.get('in', '.')}" for s in symbols]
    return " && ".join(parts) or "exists <nothing>"


def _exists_parts(spec: Any) -> tuple[list[str], list[dict[str, str]]]:
    if isinstance(spec, (list, tuple)):
        return [str(p) for p in spec], []
    if isinstance(spec, dict):
        paths = [str(p) for p in spec.get("paths", [])]
        symbols = []
        for s in spec.get("symbols", []):
            if isinstance(s, str):
                symbols.append({"pattern": s, "in": "."})
            elif isinstance(s, dict) and s.get("pattern"):
                symbols.append({"pattern": str(s["pattern"]), "in": str(s.get("in", "."))})
        return paths, symbols
    return [], []


def _grep(root: pathlib.Path, pattern: str, where: str) -> str | None:
    rx = re.compile(pattern)
    base = root / where
    if base.is_file():
        files: Iterable[pathlib.Path] = [base]
    elif base.is_dir():
        files = (p for p in base.rglob("*")
                 if p.is_file() and not (set(p.relative_to(root).parts) & _SKIP_DIRS))
    else:
        return None
    for path in files:
        try:
            if path.stat().st_size > 5_000_000:
                continue
            if rx.search(path.read_text(encoding="utf-8", errors="replace")):
                return str(path.relative_to(root))
        except OSError:
            continue
    return None


def check_exists(repo: str | pathlib.Path, spec: Any) -> dict[str, Any]:
    """파일·심볼 존재 판정. run_command와 같은 모양의 결과."""
    root = pathlib.Path(repo)
    started = time.monotonic()
    paths, symbols = _exists_parts(spec)
    missing: list[str] = []
    for rel in paths:
        if not (root / rel).exists():
            missing.append(f"missing path: {rel}")
    for sym in symbols:
        if _grep(root, sym["pattern"], sym["in"]) is None:
            missing.append(f"missing symbol: {sym['pattern']!r} in {sym['in']}")
    if not paths and not symbols:
        missing.append("exists layer declares nothing")
    ok = not missing
    return {"ok": ok, "exit_code": 0 if ok else 1, "tail": "\n".join(missing),
            "cmd": _exists_display(spec), "kind": "exists", "timed_out": False,
            "duration": time.monotonic() - started, "started_at": time.time(),
            "source": "spec", "output_path": None, "steps": [], "error": None}


# --- 실행 -----------------------------------------------------------------

def _cleanup(repo, commands: Sequence[Sequence[str]], *, timeout: int = 300) -> list[dict]:
    """설정된 정리 명령(argv 목록)을 돌린다. 실패는 결과로만 남긴다 -- 정리가 게이트를
    막을 이유는 없다. 하네스는 자기가 설정으로 받은 명령만 실행한다(03 "열어 둔 판단")."""
    out = []
    for argv in commands:
        argv = [str(a) for a in argv]
        if argv:
            out.append(verify.run_command([argv], cwd=repo, timeout=timeout, name="cleanup"))
    return out


def run_layer(repo, layer: GateLayer, *, capture_dir=None, name: str = "gate",
              before: Sequence[Sequence[str]] = (), after_timeout: Sequence[Sequence[str]] = ()
              ) -> dict[str, Any]:
    """층 하나. `before` 정리 명령 → 판정 → 타임아웃이면 `after_timeout` 정리."""
    cleanup = _cleanup(repo, before)
    if layer.name == "exists":
        result = check_exists(repo, layer.spec)
    else:
        result = verify.run_gate(repo, layer.spec, timeout=layer.timeout,
                                 capture_dir=capture_dir, name=f"{name}-{layer.name}")
    result["layer"] = layer.name
    result["cleanup"] = cleanup
    if result.get("timed_out") and after_timeout:
        result["cleanup"] += _cleanup(repo, after_timeout)
    return result


def run_layers(repo, layers: Sequence[GateLayer], *, capture_dir=None, name: str = "gate",
               before=(), after_timeout=(), only: str = "all") -> list[dict[str, Any]]:
    """층을 순서대로, 첫 실패에서 멈춘다. `only`: all | every_turn | final."""
    results = []
    for layer in layers:
        if only == "every_turn" and not layer.every_turn:
            continue
        if only == "final" and layer.every_turn:
            continue
        result = run_layer(repo, layer, capture_dir=capture_dir, name=name,
                           before=before, after_timeout=after_timeout)
        results.append(result)
        if not result["ok"]:
            break
    return results


def all_passed(results: Sequence[dict[str, Any]]) -> bool:
    return bool(results) and all(r["ok"] for r in results)


def must_fail_first(repo, layers: Sequence[GateLayer], *, capture_dir=None,
                    name: str = "baseline", before=(), after_timeout=()) -> dict[str, Any]:
    """기준선에서 게이트 전체를 돌린다. `{"passed": bool, "results": [...]}` --
    `passed`가 True면 게이트 결함이다(구현 전에 이미 초록)."""
    checked = [l for l in layers if l.must_fail_before]
    if not checked:
        return {"passed": False, "results": [], "skipped": True}
    results = run_layers(repo, checked, capture_dir=capture_dir, name=name,
                         before=before, after_timeout=after_timeout)
    return {"passed": all_passed(results), "results": results, "skipped": False}


# --- 통과를 의심하기 ---------------------------------------------------------

def suspiciously_cheap(duration: float, history: Sequence[float] = (),
                       expected: float | None = None) -> bool:
    """기록 중앙값의 20% 미만(rewrite 06) 또는 선언값의 10% 미만이면 True."""
    samples = [h for h in history if isinstance(h, (int, float)) and h > 0]
    if len(samples) >= 2:
        return duration < 0.2 * statistics.median(samples)
    if expected and expected > 0:
        return duration < 0.1 * expected
    return False


def stale_artifacts(repo, paths: Sequence[str], since: float) -> list[str]:
    """`since`(epoch 초) 이후 갱신되지 않았거나 없는 산출물 -- 측정형 게이트가
    아무것도 재지 않았다는 증거다."""
    root = pathlib.Path(repo)
    stale = []
    for rel in paths:
        p = root / rel
        try:
            if p.stat().st_mtime < since - 1.0:
                stale.append(f"{rel} (not refreshed)")
        except OSError:
            stale.append(f"{rel} (missing)")
    return stale
