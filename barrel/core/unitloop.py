"""범용 유닛 루프 -- 작업 단위 하나에 세션 하나, 게이트는 드라이버가 직접, 실패는 분류해서
사다리로 오른다.

자율 실행 기록(docs/autonomy, 이제 docs/done/autonomy)의 05 문서가 인벤토리로 남긴 일회용
드라이버의 뼈대 여덟 가지를 그대로 옮기되, 프로젝트 고유값 12곳은 설정으로 뺐다:

    유닛 루프 · 게이트 독립 실행 · 실패 되먹임 · 상태 파일 재개 · 모델·effort 사다리 ·
    예산 가드 · 거부 감지 · 중지 파일

그리고 그 기록이 "같이 고쳐야 한다"고 한 네 가지를 구조로 막는다: 턴 마감은 항상
유한하고(예산 시계), 정리·복구 명령은 전부 설정에서 오며(코드에 docker 패턴 없음),
진행 상태 파일은 대상 레포 **밖**(`results_dir`)에 있어 커밋에 섞일 수 없고, push와
브랜치 강제는 선택이다. 03 문서의 감지 → 분류 → 복구 → 에스컬레이션 루프는
`failures`(분류·지문·사다리·예산)와 `gates`(다층·fail-first·싼 통과 의심)를 써서
`_attempt`/`_run_unit`에 있다.

입력은 JSON 둘: 실행 설정(드라이버 쪽)과 로드맵(대상 레포 안, 유닛 목록). 세션은
`session_factory`로 주입되므로 세션 없이 통째로 테스트된다(`barrel/tests/test_unitloop.py`).
종료 코드: 0 전 유닛 done · 2 blocked/halt(사람 호출) · 3 설정/preflight · 4 중지 파일.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from step2step.contracts import ControlError, TurnOutcome
from step2step.refusal import looks_like_refusal

from . import failures, gates, gitops, preflight
from .failures import Budget, BudgetClock, FailureKind, Ladder, RepeatTracker, Rung

EXIT_OK, EXIT_HALTED, EXIT_CONFIG, EXIT_STOPPED = 0, 2, 3, 4
STOP_FILE = ".unit-loop-stop"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
PROMPT_PREVIEW = 1200
RESPONSE_PREVIEW = 300

DEFAULT_CONFIG: dict[str, Any] = {
    "name": None,                    # 실행 이름(로그·결과 디렉터리 이름). 필수
    "target_repo": None,             # 대상 레포 경로. 필수, 기본값 없음
    "roadmap": "orchestration/roadmap.json",   # 대상 레포 안의 유닛 목록
    "git": {
        "branch": None,              # 시작 시 확인할 브랜치(None이면 확인 안 함)
        "allow_any_branch": False,
        "push": None,                # {"remote": "origin", "branch": null|"name"} 또는 null
        "commit_prefix": "",         # 커밋 제목 접두사(유닛 id 앞)
        "commit_by": "driver",       # driver | session
        "exclude": [],               # 커밋에서 제외할 경로(부기 파일 등)
    },
    "prompt": {
        "project_name": None,        # 없으면 name
        "one_liner": "",
        "north_star": None,          # 대상 레포 안 경로. 모든 세션이 먼저 읽는 불변 계약
        "references": [],
        "scope_note": "",
        "hard_rules": [],
        "extra": "",
    },
    "ladder": {"models": [], "efforts": []},
    "budget": {},                    # failures.Budget 필드 override
    "gates": {
        "timeout_seconds": 3600,
        "before": [],                # 게이트 직전 정리 명령(argv 목록들)
        "after_timeout": [],         # 게이트 타임아웃 직후 정리 명령
        "env_recover": [],           # 환경 실패로 분류됐을 때 1회 실행할 복구 명령
    },
    "preflight": {"tools": ["git"], "docker": False, "min_free_mb": 1024, "commands": []},
    "notify": {"command": None, "webhook": None},
    "on_unit_blocked": "halt",       # halt | skip
    "repeat_limit": 2,               # 같은 지문 연속 N회면 그 칸은 무효
    "harness_retries": 2,            # 같은 칸에서 세션 교체 상한
    "usage_wait_seconds": 900,       # usage limit 시 대기
    "menu_default_answer": "Use your best judgement and continue; do not ask again.",
}


# --- 설정 -------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str | pathlib.Path) -> dict[str, Any]:
    """JSON 설정 + 기본값. 상대 `target_repo`는 설정 파일 위치 기준."""
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    cfg = apply_defaults(raw)
    target = cfg.get("target_repo")
    if isinstance(target, str) and target and not pathlib.Path(target).expanduser().is_absolute():
        cfg["target_repo"] = str((p.parent / target).resolve())
    elif isinstance(target, str) and target:
        cfg["target_repo"] = str(pathlib.Path(target).expanduser())
    return cfg


def apply_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_CONFIG, cfg or {})


def _argv_lists(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not all(
            isinstance(cmd, list) and cmd and all(isinstance(a, (str, int, float)) for a in cmd)
            for cmd in value):
        errors.append(f"{where} must be a list of argv lists, e.g. [[\"docker\", \"system\", \"prune\", \"-f\"]]")


def validate_config(cfg: dict[str, Any]) -> list[str]:
    """설정 오류 목록(비어 있으면 OK). 메시지마다 조치를 적는다."""
    errors: list[str] = []
    name = cfg.get("name")
    if not isinstance(name, str) or not name.strip() or any(c in name for c in "/\\ "):
        errors.append("name: give the run a short name without spaces or slashes (used for log and result paths)")
    target = cfg.get("target_repo")
    if not isinstance(target, str) or not target.strip():
        errors.append("target_repo: required, no default -- the path of the repo the units work in")
    elif not pathlib.Path(target).is_dir():
        errors.append(f"target_repo: not a directory: {target}")
    if not isinstance(cfg.get("roadmap"), str) or not cfg["roadmap"]:
        errors.append("roadmap: path (inside target_repo) of the unit list JSON")
    ladder = cfg.get("ladder") or {}
    if not isinstance(ladder.get("models"), list) or not ladder["models"]:
        errors.append("ladder.models: list at least one model, e.g. [\"claude-fable-5\", \"claude-opus-5\"]")
    for effort in ladder.get("efforts") or []:
        if effort not in EFFORT_LEVELS:
            errors.append(f"ladder.efforts: {effort!r} is not one of {EFFORT_LEVELS}")
    try:
        Budget().merged(cfg.get("budget") or {})
    except (ValueError, TypeError) as exc:
        errors.append(f"budget: {exc}")
    git = cfg.get("git") or {}
    if git.get("commit_by") not in ("driver", "session"):
        errors.append("git.commit_by: 'driver' (single commit gateway, default) or 'session'")
    push = git.get("push")
    if push is not None and (not isinstance(push, dict) or not push.get("remote")):
        errors.append("git.push: null or {\"remote\": \"origin\", \"branch\": null}")
    if not isinstance(git.get("exclude"), list):
        errors.append("git.exclude: list of paths to keep out of unit commits")
    if cfg.get("on_unit_blocked") not in ("halt", "skip"):
        errors.append("on_unit_blocked: 'halt' (stop for a human) or 'skip' (go on to the next unit)")
    for key in ("repeat_limit", "harness_retries"):
        if not isinstance(cfg.get(key), int) or cfg[key] < 1:
            errors.append(f"{key}: positive integer")
    g = cfg.get("gates") or {}
    if not isinstance(g.get("timeout_seconds"), (int, float)) or g["timeout_seconds"] <= 0:
        errors.append("gates.timeout_seconds: positive number")
    for key in ("before", "after_timeout", "env_recover"):
        _argv_lists(g.get(key), f"gates.{key}", errors)
    pf = cfg.get("preflight") or {}
    _argv_lists(pf.get("commands"), "preflight.commands", errors)
    if not isinstance(pf.get("tools"), list):
        errors.append("preflight.tools: list of executables that must be on PATH")
    n = cfg.get("notify") or {}
    if n.get("command") is not None and not (isinstance(n["command"], list) and n["command"]):
        errors.append("notify.command: argv list; the message is appended as the last argument")
    if n.get("webhook") is not None and not (isinstance(n["webhook"], str)
                                             and n["webhook"].startswith("http")):
        errors.append("notify.webhook: an http(s) URL that accepts a JSON POST")
    return errors


# --- 로드맵 -------------------------------------------------------------------

@dataclass
class Unit:
    id: str
    title: str
    prompt: str
    layers: list[gates.GateLayer]
    depends_on: list[str] = field(default_factory=list)
    effort: str | None = None
    model: str | None = None
    expect_baseline_fail: bool = True
    expected_gate_seconds: float | None = None
    artifacts: list[str] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)


def load_roadmap(path: str | pathlib.Path, *, default_timeout: int = gates.DEFAULT_TIMEOUT
                 ) -> list[Unit]:
    p = pathlib.Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    raw_units = data.get("units") if isinstance(data, dict) else data
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError(f"{p}: expected {{\"units\": [...]}} with at least one unit")
    units: list[Unit] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_units):
        if not isinstance(raw, dict) or not raw.get("id"):
            raise ValueError(f"{p}: unit #{i} needs an id")
        uid = str(raw["id"])
        if uid in seen:
            raise ValueError(f"{p}: duplicate unit id {uid}")
        seen.add(uid)
        prompt = raw.get("prompt")
        if not prompt and raw.get("prompt_file"):
            prompt = (p.parent / raw["prompt_file"]).read_text(encoding="utf-8")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{p}: unit {uid} needs a prompt or prompt_file")
        try:
            layers = gates.parse_layers(raw.get("gates"), default_timeout=default_timeout)
        except ValueError as exc:
            raise ValueError(f"{p}: unit {uid}: {exc}") from exc
        if not layers:
            raise ValueError(f"{p}: unit {uid} declares no gates -- a unit without a gate "
                             "cannot be judged (exists/build/unit/behavior/integration/perf)")
        effort = raw.get("effort")
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ValueError(f"{p}: unit {uid}: effort {effort!r} not in {EFFORT_LEVELS}")
        units.append(Unit(
            id=uid, title=str(raw.get("title") or uid), prompt=prompt, layers=layers,
            depends_on=[str(d) for d in raw.get("depends_on", [])],
            effort=effort, model=raw.get("model"),
            expect_baseline_fail=bool(raw.get("expect_baseline_fail", True)),
            expected_gate_seconds=raw.get("expected_gate_seconds"),
            artifacts=[str(a) for a in raw.get("artifacts", [])],
            budget=dict(raw.get("budget") or {}),
            references=[str(r) for r in raw.get("references", [])],
        ))
    for unit in units:
        for dep in unit.depends_on:
            if dep not in seen:
                raise ValueError(f"{p}: unit {unit.id} depends on unknown unit {dep}")
    return units


# --- 프롬프트 -------------------------------------------------------------------

def gate_lines(unit: Unit, repo) -> list[str]:
    return [f"  $ [{layer.name}] {layer.display(repo)}" for layer in unit.layers]


def commit_rule(cfg: dict[str, Any], unit: Unit) -> str:
    git = cfg["git"]
    if git["commit_by"] == "session":
        branch = git.get("branch") or "the current branch"
        rule = (f"Commit ALL your changes on {branch} with a message beginning "
                f"\"{git['commit_prefix']}{unit.id}: \".")
        if git.get("push"):
            rule += f" Then `git push {git['push']['remote']} {git['push'].get('branch') or branch}`."
        return rule
    return "Do NOT commit or push; the driver commits once the gate is green."


def render_unit_prompt(cfg: dict[str, Any], unit: Unit, repo) -> str:
    p = cfg["prompt"]
    name = p.get("project_name") or cfg["name"]
    lines = [f"You are one worker session in an autonomous build of {name}"
             + (f" ({p['one_liner']})" if p.get("one_liner") else "")
             + f". Your entire task this session is UNIT {unit.id}: {unit.title}.", ""]
    reads = []
    if p.get("north_star"):
        reads.append(f"  - {p['north_star']}   (the north-star: goal, invariants, scope"
                     + (f"; this round = {p['scope_note']}" if p.get("scope_note") else "")
                     + ". Read it first; never edit it except its progress log.)")
    for ref in list(p.get("references") or []) + list(unit.references):
        reads.append(f"  - {ref}")
    if reads:
        lines += ["FIRST, read these for the immutable mission and context (do not let the "
                  "goal drift):", *reads, ""]
    lines += [f"UNIT {unit.id} — {unit.title}", unit.prompt.rstrip(), ""]
    lines += ["ACCEPTANCE (you are DONE only when all hold):",
              "- The gate below is green. The driver runs it itself, layer by layer, and "
              "does not trust any report of success:", *gate_lines(unit, repo), ""]
    rules = list(p.get("hard_rules") or [])
    rules += ["Do not weaken tests or the gate to make it pass.",
              commit_rule(cfg, unit),
              f"If the ENVIRONMENT is broken (a daemon down, a pull that hangs, no disk, a "
              f"tool missing), say so on a line starting with `{failures.ENV_MARKER}` and "
              "stop -- do not keep retrying code changes against a dead environment."]
    lines += ["HARD RULES (violating these fails the unit):"] + [f"- {r}" for r in rules] + [""]
    steps = ["Read the material above and the relevant source.",
             "Implement the smallest correct change that satisfies the acceptance criteria.",
             "Run the gate yourself until it passes. Fix real failures.",
             "Add or extend tests so the new behaviour is actually covered."]
    if p.get("north_star"):
        steps.append(f"Append a dated one-line entry to the progress log in {p['north_star']} "
                     f"for {unit.id}.")
    lines += ["WORKFLOW:"] + [f"  {i}. {s}" for i, s in enumerate(steps, 1)] + [""]
    if p.get("extra"):
        lines += [p["extra"].rstrip(), ""]
    lines.append("Do not start other units. Do not refactor unrelated code. Report concisely "
                 "what you changed and paste the final gate output at the end.")
    return "\n".join(lines)


def render_feedback_prompt(cfg: dict[str, Any], unit: Unit, result: dict[str, Any], repo) -> str:
    layer = result.get("layer", "gate")
    cmd = result.get("cmd")
    shown = cmd if isinstance(cmd, str) else (
        " && ".join(" ".join(map(str, s)) for s in cmd) if cmd and isinstance(cmd[0], list)
        else " ".join(map(str, cmd or [])))
    how = ("timed out after %ss" % result.get("timeout", "")).replace("after s", "timed out") \
        if result.get("timed_out") else f"exit {result.get('exit_code')}"
    return "\n".join([
        f"The acceptance gate for UNIT {unit.id} is NOT yet green. The driver ran the "
        f"\"{layer}\" layer:",
        f"  $ {shown}",
        f"and it FAILED ({how}). Tail of the output:",
        "---",
        (result.get("tail") or "").rstrip(),
        "---",
        "Diagnose and fix the real cause, then run the gate again yourself until it passes. "
        "Do not weaken tests or the gate to make it pass. " + commit_rule(cfg, unit),
        f"If the failure is the environment rather than the code, say so on a line starting "
        f"with `{failures.ENV_MARKER}` and stop. Continue until the gate is genuinely green.",
    ])


# --- 알림 -----------------------------------------------------------------------

class Notifier:
    """정지·halt·blocked·게이트 결함·usage limit을 사람에게 알린다. 절대 예외를 내지 않는다.
    설정된 명령(argv + 메시지) 및/또는 웹훅(JSON POST); 둘 다 없고 macOS면 알림 센터."""

    def __init__(self, cfg_notify: dict[str, Any], run_name: str, log: Callable[[str], None]):
        self.command = cfg_notify.get("command")
        self.webhook = cfg_notify.get("webhook")
        self.run_name = run_name
        self.log = log
        self.sent: list[tuple[str, str]] = []

    def send(self, title: str, message: str) -> bool:
        self.sent.append((title, message))
        self.log(f"[notify] {title}: {message}")
        ok = False
        if self.command:
            try:
                subprocess.run([str(a) for a in self.command] + [f"[{self.run_name}] {title}: {message}"],
                               capture_output=True, timeout=30)
                ok = True
            except Exception as exc:  # noqa: BLE001
                self.log(f"[notify] command failed: {exc!r}")
        if self.webhook:
            try:
                body = json.dumps({"text": f"[{self.run_name}] {title}: {message}",
                                   "run": self.run_name, "title": title,
                                   "message": message}).encode("utf-8")
                req = urllib.request.Request(self.webhook, data=body,
                                             headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=15).read()
                ok = True
            except Exception as exc:  # noqa: BLE001
                self.log(f"[notify] webhook failed: {exc!r}")
        if not self.command and not self.webhook and platform.system() == "Darwin":
            try:
                script = 'display notification "%s" with title "%s"' % (
                    message.replace('"', "'")[:200], f"{self.run_name}: {title}".replace('"', "'"))
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
                ok = True
            except Exception:  # noqa: BLE001
                pass
        return ok


# --- 상태 파일 -------------------------------------------------------------------

class RunState:
    """`results_dir/state.json`. 대상 레포 밖이라 커밋에 섞일 수 없다. 원자적 저장."""

    def __init__(self, path: pathlib.Path, name: str):
        self.path = pathlib.Path(path)
        self.data: dict[str, Any] = {"name": name, "started": time.time(), "units": {},
                                     "last_checkpoint": None, "budgets_spent": {}}
        if self.path.is_file():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except ValueError:
                pass

    def unit(self, uid: str) -> dict[str, Any]:
        return self.data["units"].setdefault(uid, {"status": "pending", "attempts": []})

    def status(self, uid: str) -> str:
        return self.unit(uid).get("status", "pending")

    def mark(self, uid: str, status: str, **fields: Any) -> None:
        rec = self.unit(uid)
        rec["status"] = status
        rec.update(fields)
        rec["updated"] = time.time()
        self.save()

    def start_attempt(self, uid: str, rung: Rung, session_id: str | None,
                      snapshot_path: str | None) -> dict[str, Any]:
        attempt = {"rung": {"model": rung.model, "effort": rung.effort},
                   "session_id": session_id, "snapshot_path": snapshot_path,
                   "started": time.time(), "ended": None, "turns": [], "gates": [],
                   "outcome": None}
        self.unit(uid)["attempts"].append(attempt)
        self.save()
        return attempt

    def gate_history(self, uid: str) -> list[float]:
        """통과한 게이트 실행의 총 소요(싼 통과 의심의 기준)."""
        out = []
        for attempt in self.unit(uid).get("attempts", []):
            for g in attempt.get("gates", []):
                if g.get("ok") and isinstance(g.get("duration"), (int, float)):
                    out.append(float(g["duration"]))
        return out

    def save(self) -> None:
        self.data["last_checkpoint"] = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


# --- 엔진 -----------------------------------------------------------------------

_STUCK = (TurnOutcome.STALLED, TurnOutcome.NOISY_STAGNATION, TurnOutcome.DEADLINE_EXCEEDED)
_DEAD = (TurnOutcome.EOF, TurnOutcome.FAILED, TurnOutcome.INTERRUPTED, TurnOutcome.UNSUPPORTED,
         TurnOutcome.AWAITING_UNKNOWN_DIALOG)


def default_session_factory(cfg: dict[str, Any], log: Callable[[str], None]):
    """실제 Claude Code 세션. 지연 import: 엔진 자체는 substrate 없이도 로드된다."""
    def factory(unit: Unit, rung: Rung, *, turn_timeout: float, snapshot_dir, app_dir):
        from step2step.claude.session import SessionHandle
        return SessionHandle.start(
            workdir=cfg["target_repo"], role=f"unit:{unit.id}", model=rung.model,
            effort=rung.effort, mode="bypass", app_dir=app_dir, snapshot_dir=snapshot_dir,
            logger=lambda m: log("[s2s] %s" % m), turn_timeout=turn_timeout,
        )
    return factory


class UnitLoop:
    def __init__(self, cfg: dict[str, Any], units: Sequence[Unit], *, results_dir,
                 session_factory=None, log: Callable[[str], None] = print,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg = cfg
        self.units = list(units)
        self.results_dir = pathlib.Path(results_dir)
        self.log = log
        self.clock = clock
        self.sleep = sleep
        self.repo = pathlib.Path(cfg["target_repo"])
        self.factory = session_factory or default_session_factory(cfg, log)
        self.state = RunState(self.results_dir / "state.json", cfg["name"])
        self.notifier = Notifier(cfg["notify"], cfg["name"], log)
        self.budget = Budget().merged(cfg.get("budget") or {})
        self.clock_budget = BudgetClock(self.budget, clock)
        self.ladder = Ladder(cfg["ladder"]["models"], cfg["ladder"]["efforts"])
        self.gate_dir = self.results_dir / "gates"
        self.stop_files = [self.results_dir / f"{cfg['name']}.stop", self.repo / STOP_FILE]
        self.halt_reason: str | None = None

    # ------------------------------------------------------------ helpers
    def _stop_requested(self) -> bool:
        return any(p.exists() for p in self.stop_files)

    def worktree_digest(self) -> str:
        head = gitops.head_sha(self.repo) or ""
        status = "\n".join(gitops.status_porcelain(self.repo))
        return hashlib.sha256((head + "\n" + status).encode("utf-8")).hexdigest()[:16]

    def _exclude(self) -> list[str]:
        return list(self.cfg["git"]["exclude"]) + [STOP_FILE]

    def _gates_of(self, unit: Unit, only: str, name: str) -> list[dict[str, Any]]:
        g = self.cfg["gates"]
        results = gates.run_layers(self.repo, unit.layers, capture_dir=self.gate_dir,
                                   name=f"{unit.id}-{name}", before=g["before"],
                                   after_timeout=g["after_timeout"], only=only)
        for r in results:
            self._log_gate(unit, r)
        return results

    def _log_gate(self, unit: Unit, r: dict[str, Any]) -> None:
        cmd = r.get("cmd")
        shown = cmd if isinstance(cmd, str) else " ".join(map(str, cmd or [])) \
            if not (cmd and isinstance(cmd[0], list)) else " && ".join(" ".join(map(str, s)) for s in cmd)
        self.log(f"[gate] [{r.get('layer')}] $ {shown}")
        if r.get("timed_out"):
            self.log(f"[gate] TIMEOUT after {r.get('duration', 0):.0f}s")
        else:
            self.log(f"[gate] exit={r.get('exit_code')} in {r.get('duration', 0):.0f}s -> "
                     f"{'PASS' if r.get('ok') else 'FAIL'}"
                     + (f" ({r['error']})" if r.get("error") else ""))

    def _record_gate(self, attempt: dict, unit: Unit, r: dict[str, Any],
                     fp: str | None = None, kind: str | None = None) -> None:
        attempt["gates"].append({"layer": r.get("layer"), "ok": r.get("ok"),
                                 "exit_code": r.get("exit_code"), "duration": r.get("duration"),
                                 "timed_out": r.get("timed_out"), "fingerprint": fp,
                                 "kind": kind, "output_path": r.get("output_path"),
                                 "at": time.time()})
        self.state.save()

    # ------------------------------------------------------------ run
    def run(self, *, only: Sequence[str] | None = None, dry_run: bool = False) -> int:
        errors = validate_config(self.cfg)
        if errors:
            for e in errors:
                self.log(f"[config] {e}")
            return EXIT_CONFIG
        pf = self.cfg["preflight"]
        git = self.cfg["git"]
        findings = preflight.check_environment(
            self.repo, tools=pf["tools"], commands=pf["commands"],
            min_free_mb=pf["min_free_mb"], docker=pf["docker"],
            expect_branch=(git["branch"] if git["branch"] and not git["allow_any_branch"] else None),
        )
        for f in findings:
            self.log(f"[preflight] {'ok' if f.ok else f.severity.upper()} {f.message()}")
        if preflight.problems(findings, "fatal"):
            self.notifier.send("preflight failed", preflight.summarize(findings))
            return EXIT_CONFIG
        wanted = [u for u in self.units if not only or u.id in set(only)]
        self.log(f"START unit-loop name={self.cfg['name']} target={self.repo} "
                 f"units={[u.id for u in wanted]} dry_run={dry_run} "
                 f"budget={self.budget}")
        for unit in wanted:
            if self.state.status(unit.id) == "done":
                self.log(f"[{unit.id}] already done; skipping")
                continue
            if self._stop_requested():
                self.log(f"[{unit.id}] stop file present -> stopping before the unit")
                self.notifier.send("stopped", f"stop file present before {unit.id}")
                return EXIT_STOPPED
            if self.clock_budget.exceeded() == "run":
                return self._halt("run budget exceeded")
            missing = [d for d in unit.depends_on if self.state.status(d) != "done"]
            if missing:
                self.log(f"[{unit.id}] dependencies not done: {missing} -> skipping")
                self.state.mark(unit.id, "blocked", reason=f"dependencies not done: {missing}")
                if self.cfg["on_unit_blocked"] == "halt":
                    return self._halt(f"{unit.id} blocked on {missing}")
                continue
            self.log(f"=== UNIT {unit.id}: {unit.title} (effort={unit.effort or self.ladder.efforts[0]}) ===")
            if dry_run:
                self.log(f"[{unit.id}] DRY RUN — prompt preview:")
                self.log(render_unit_prompt(self.cfg, unit, self.repo)[:PROMPT_PREVIEW])
                mff = gates.must_fail_first(self.repo, unit.layers, capture_dir=self.gate_dir,
                                            name=f"{unit.id}-baseline", before=self.cfg["gates"]["before"],
                                            after_timeout=self.cfg["gates"]["after_timeout"])
                for r in mff["results"]:
                    self._log_gate(unit, r)
                self.log(f"[{unit.id}] baseline gate {'PASSES -> GATE DEFECT' if mff['passed'] else 'fails (good)'}")
                continue
            status = self._run_unit(unit)
            if status == "done":
                continue
            if status == "stop":
                return EXIT_STOPPED
            if status in ("halt", "gate_defect"):
                return EXIT_HALTED
            if status == "blocked":
                if self.cfg["on_unit_blocked"] == "skip":
                    self.log(f"[{unit.id}] blocked; on_unit_blocked=skip -> next unit")
                    continue
                return self._halt(f"{unit.id} blocked")
        if dry_run:
            return EXIT_OK
        if all(self.state.status(u.id) == "done" for u in wanted):
            self.log("ALL UNITS DONE.")
            return EXIT_OK
        return EXIT_HALTED

    def _halt(self, reason: str) -> int:
        self.halt_reason = reason
        self.log(f"HALT: {reason}")
        self.notifier.send("halted", reason)
        return EXIT_HALTED

    # ------------------------------------------------------------ one unit
    def _run_unit(self, unit: Unit) -> str:
        self.clock_budget.start_unit(unit.budget)
        self.state.mark(unit.id, "running", started=time.time())
        if unit.expect_baseline_fail:
            mff = gates.must_fail_first(self.repo, unit.layers, capture_dir=self.gate_dir,
                                        name=f"{unit.id}-baseline", before=self.cfg["gates"]["before"],
                                        after_timeout=self.cfg["gates"]["after_timeout"])
            for r in mff["results"]:
                self._log_gate(unit, r)
            if mff["passed"]:
                # 사고 1: 구현 전에 초록인 게이트는 완료를 판정하지 못한다. 세션을 띄우지
                # 않고, "이미 됐다"고도 하지 않는다 -- 게이트가 틀렸다.
                reason = f"gate passes before any work (layers {[r['layer'] for r in mff['results']]}) -- the gate cannot detect completion; fix the gate"
                self.log(f"[{unit.id}] GATE DEFECT: {reason}")
                self.state.mark(unit.id, "gate_defect", reason=reason)
                self.notifier.send(f"{unit.id} gate defect", reason)
                return "gate_defect"
        rungs = self.ladder.rungs(unit.effort, unit.model)
        rung: Rung | None = rungs[0]
        harness_retries = 0
        while rung is not None:
            if self._stop_requested():
                self.state.mark(unit.id, "blocked", reason="stop file")
                self.notifier.send("stopped", f"stop file present during {unit.id}")
                return "stop"
            self.log(f"[{unit.id}] attempt {rung.label()}")
            status, why = self._attempt(unit, rung)
            self.log(f"[{unit.id}] attempt result: {status} {why}".rstrip())
            if status == "done":
                self.state.mark(unit.id, "done", finished=time.time())
                self._commit(unit)
                return "done"
            if status == "stop":
                self.state.mark(unit.id, "blocked", reason="stop file")
                return "stop"
            if status == "halt":
                self.state.mark(unit.id, "blocked", reason=why)
                self._halt(f"{unit.id}: {why}")
                return "halt"
            if status == "blocked":
                self.state.mark(unit.id, "blocked", reason=why)
                self.notifier.send(f"{unit.id} blocked", why)
                return "blocked"
            if status == "replace_session":
                harness_retries += 1
                if harness_retries <= self.cfg["harness_retries"]:
                    continue                      # 같은 칸, 새 세션(사다리 칸 2)
                harness_retries = 0
                rung = self.ladder.next(rungs, rung, "harness")
            elif status == "next_model":
                rung = self.ladder.next(rungs, rung, "refusal")
            else:                                  # next_rung
                rung = self.ladder.next(rungs, rung, "repeat")
        why = "ladder exhausted"
        self.state.mark(unit.id, "blocked", reason=why)
        self.notifier.send(f"{unit.id} blocked", why)
        return "blocked"

    # ------------------------------------------------------------ one attempt
    def _attempt(self, unit: Unit, rung: Rung) -> tuple[str, str]:
        budget = self.clock_budget.unit_budget
        snapshot_dir = self.results_dir / "sessions"
        app_dir = self.results_dir / "app_dir"
        try:
            session = self.factory(unit, rung, turn_timeout=self.clock_budget.turn_budget(),
                                   snapshot_dir=snapshot_dir, app_dir=app_dir)
        except Exception as exc:  # noqa: BLE001 -- 세션을 못 띄운 것도 하네스 실패다
            self.log(f"[{unit.id}] session start failed: {exc!r}")
            return "replace_session", f"session start failed: {exc}"
        sid = getattr(session, "session_id", None)
        attempt = self.state.start_attempt(
            unit.id, rung, sid, str(snapshot_dir / f"session-{sid}.json") if sid else None)
        watch = getattr(session, "watch", None)
        if watch is not None:
            try:
                watch(lambda ev, info: self.log(f"[{unit.id}] [watchdog] {ev} {info}"))
            except Exception as exc:  # noqa: BLE001
                self.log(f"[{unit.id}] watchdog not started: {exc!r}")
        tracker = RepeatTracker(self.cfg["repeat_limit"])
        prompt = render_unit_prompt(self.cfg, unit, self.repo)
        env_recovered = False
        resubmits = 0
        turns = 0
        try:
            while True:
                exceeded = self.clock_budget.exceeded(turns)
                if exceeded == "run":
                    return "halt", "run budget exceeded"
                if exceeded:
                    return "blocked", f"unit budget exceeded ({exceeded}, {turns} turns)"
                if self._stop_requested():
                    return "stop", "stop file"
                turns += 1
                digest0 = self.worktree_digest()
                t0 = self.clock()
                try:
                    pending = session.send_prompt(prompt)
                    result = session.wait_turn(
                        pending, timeout=self.clock_budget.turn_budget(),
                        stall_seconds=budget.stall_seconds,
                        progress_seconds=budget.progress_seconds,
                        progress_probe=self.worktree_digest)
                    result = self._resolve_interactions(unit, session, pending, result, budget)
                except ControlError as exc:
                    self.log(f"[{unit.id}] turn {turns} control error: {exc}")
                    self._fold(session)
                    return "replace_session", f"turn error: {exc}"
                duration = self.clock() - t0
                outcome = result.outcome
                attempt["turns"].append({"index": turns, "outcome": outcome.value,
                                         "duration": round(duration, 1),
                                         "tools": list(getattr(result, "tools", []) or [])[:40],
                                         "at": time.time()})
                self.state.save()
                self.log(f"[{unit.id}] turn {turns} outcome={outcome.value} {duration:.0f}s "
                         f"tools={list(getattr(result, 'tools', []) or [])[:12]} "
                         f"resp={(result.response or '')[:RESPONSE_PREVIEW]!r}")
                if outcome is TurnOutcome.USAGE_LIMIT:
                    wait = min(float(self.cfg["usage_wait_seconds"]), self.clock_budget.remaining_run())
                    self.notifier.send(f"{unit.id} usage limit",
                                       f"waiting {wait:.0f}s (reset: {result.usage_reset_text})")
                    self.sleep(wait)
                    continue
                if outcome is TurnOutcome.SUBMIT_FAILED:
                    if resubmits >= 1:
                        self._fold(session)
                        return "replace_session", "prompt submission not confirmed twice"
                    resubmits += 1
                    self.log(f"[{unit.id}] submit not confirmed -> resend once")
                    continue
                if outcome in _STUCK:
                    folded = self._fold(session)
                    return "replace_session", f"{outcome.value} (interrupt {'ok' if folded else 'failed'})"
                if outcome in (TurnOutcome.AWAITING_MENU, TurnOutcome.AWAITING_PLAN_APPROVAL):
                    self._fold(session)
                    return "replace_session", f"interaction not resolved ({outcome.value})"
                if outcome in _DEAD:
                    self._fold(session)
                    return "replace_session", outcome.value
                # ---- completed: judge by the gate, never by the response ----
                changed = self.worktree_digest() != digest0
                if looks_like_refusal(result.response) and not changed:
                    self.log(f"[{unit.id}] refusal with no code change -> next model")
                    return "next_model", "refusal"
                verdict, failed = self._judge(unit, attempt, turns)
                if verdict == "done":
                    return "done", f"gate PASS after {turns} turn(s)"
                cls = failures.classify(failed, response=result.response, worktree_changed=changed)
                fp = failures.fingerprint_result(f"{unit.id}:{failed.get('layer')}", failed)
                streak = tracker.record(fp)
                self._record_gate(attempt, unit, failed, fp, cls.kind.value)
                self.log(f"[{unit.id}] failure {cls} fingerprint={fp} streak={streak}")
                if cls.kind is FailureKind.GATE_DEFECT:
                    return "halt", f"gate defect: {cls}"
                if cls.kind is FailureKind.ENVIRONMENT:
                    if not env_recovered and self.cfg["gates"]["env_recover"]:
                        env_recovered = True
                        self.log(f"[{unit.id}] environment failure -> running env_recover once")
                        for r in gates._cleanup(self.repo, self.cfg["gates"]["env_recover"]):
                            self.log(f"[env_recover] exit={r['exit_code']} {r['tail'][-200:]!r}")
                        verdict, failed2 = self._judge(unit, attempt, turns)
                        if verdict == "done":
                            return "done", f"gate PASS after env_recover ({turns} turn(s))"
                        fp2 = failures.fingerprint_result(f"{unit.id}:{failed2.get('layer')}", failed2)
                        self._record_gate(attempt, unit, failed2, fp2, "environment")
                        if fp2 == fp:
                            return "halt", f"environment failure persists after env_recover: {cls}"
                        failed = failed2
                    else:
                        return "halt", f"environment failure ({cls}); no env_recover configured or already used"
                if tracker.exhausted():
                    return "next_rung", f"same failure {streak}x ({fp})"
                prompt = render_feedback_prompt(self.cfg, unit, failed, self.repo)
        finally:
            attempt["ended"] = time.time()
            try:
                session.stop(force=False)
            except Exception as exc:  # noqa: BLE001
                self.log(f"[{unit.id}] session stop failed: {exc!r}")
            self.state.save()

    def _resolve_interactions(self, unit: Unit, session, pending, result, budget):
        """플랜 승인·질문 메뉴는 검증된 주입으로 답하고 같은 PendingTurn을 재대기."""
        for _ in range(4):
            if result.outcome is TurnOutcome.AWAITING_PLAN_APPROVAL:
                self.log(f"[{unit.id}] plan approval -> approve_plan")
                if session.approve_plan() is False:
                    raise ControlError("plan approval Enter did not take")
            elif result.outcome is TurnOutcome.AWAITING_MENU:
                self.log(f"[{unit.id}] question menu -> answer_menu_text(default)")
                session.answer_menu_text(self.cfg["menu_default_answer"])
            else:
                return result
            result = session.wait_turn(pending, timeout=self.clock_budget.turn_budget(),
                                       stall_seconds=budget.stall_seconds,
                                       progress_seconds=budget.progress_seconds,
                                       progress_probe=self.worktree_digest)
        return result

    def _fold(self, session) -> bool:
        try:
            return session.interrupt() is not False
        except Exception as exc:  # noqa: BLE001
            self.log(f"[loop] interrupt raised {exc!r}")
            return False

    def _judge(self, unit: Unit, attempt: dict, turns: int) -> tuple[str, dict[str, Any] | None]:
        """게이트 층을 돌려 (verdict, 실패 결과). verdict: done | failed."""
        started = time.time()
        results = self._gates_of(unit, "every_turn", f"t{turns}")
        if gates.all_passed(results) or not results:
            results += self._gates_of(unit, "final", f"t{turns}")
        for r in results:
            if r["ok"]:
                self._record_gate(attempt, unit, r)
        if not gates.all_passed(results):
            return "failed", next(r for r in results if not r["ok"])
        total = sum(r.get("duration") or 0.0 for r in results)
        if gates.suspiciously_cheap(total, self.state.gate_history(unit.id),
                                    unit.expected_gate_seconds):
            self.log(f"[{unit.id}] gate passed suspiciously fast ({total:.0f}s) -> re-running once")
            again = self._gates_of(unit, "all", f"t{turns}-recheck")
            for r in again:
                self._record_gate(attempt, unit, r)
            if not gates.all_passed(again):
                return "failed", next(r for r in again if not r["ok"])
        stale = gates.stale_artifacts(self.repo, unit.artifacts, started)
        if stale:
            failed = {"layer": "artifacts", "ok": False, "exit_code": 1, "timed_out": False,
                      "cmd": "artifact freshness", "duration": 0.0, "error": None,
                      "tail": "measured nothing: " + ", ".join(stale)}
            self.log(f"[{unit.id}] artifacts not refreshed: {stale}")
            return "failed", failed
        self.log(f"[{unit.id}] gate PASS after {turns} turn(s)")
        return "done", None

    # ------------------------------------------------------------ git
    def _commit(self, unit: Unit) -> None:
        git = self.cfg["git"]
        dirty = gitops.status_porcelain(self.repo)
        if git["commit_by"] == "driver" or dirty:
            suffix = "" if git["commit_by"] == "driver" else " (driver fallback commit)"
            message = f"{git['commit_prefix']}{unit.id}: {unit.title}{suffix}"
            res = gitops.commit_all(self.repo, message, exclude=self._exclude())
            if res.get("error"):
                self.log(f"[git] commit FAILED: {res['error']}")
                self.notifier.send(f"{unit.id} commit failed", str(res["error"]))
            elif res.get("committed"):
                self.log(f"[git] commit {res['sha'][:8] if res.get('sha') else '?'} "
                         f"{message!r} paths={res['paths']} excluded={res['excluded']}")
            else:
                self.log("[git] nothing to commit")
        push = git.get("push")
        if push:
            res = gitops.push(self.repo, push["remote"], push.get("branch"))
            if res["pushed"]:
                self.log(f"[git] push {push['remote']} {res['branch']} -> ok: {res['output'][:120]}")
            else:
                self.log(f"[git] push FAILED: {res['error']}")
                self.notifier.send(f"{unit.id} push failed", str(res["error"]))
