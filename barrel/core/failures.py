"""실패의 분류·지문·사다리·예산 -- 드라이버가 종료 코드 하나 이상을 알게 하는 층.

자율 실행 기록(03 자체복구)의 결론은 "감지 → 분류 → 복구 → 에스컬레이션" 루프였다.
이 모듈은 그 중 분류(코드/환경/하네스/게이트 결함/거부/능력/예산)와, 같은 실패를
두 번 세지 않기 위한 지문(정규화 → sha256 앞 16자, `decisions.question_hash`와
같은 모양), 그리고 복구 사다리(모델·effort 칸)와 세 층 예산(턴·유닛·실행)을 담는다.
DB·세션·PTY를 import하지 않는 순수 모듈이라 드라이버 없이도 테스트된다.

거부 판정은 `step2step.refusal`의 문구 감지에 **"코드 변경이 없었다"를 결합**해야
성립한다(문구만으로는 안 된다 -- 05 문서의 규칙).
"""
from __future__ import annotations

import hashlib
import math
import re
import time
import unicodedata
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

from step2step.refusal import looks_like_refusal, refusal_evidence


class FailureKind(str, Enum):
    CODE = "code"                  # 컴파일·테스트 실패: 꼬리를 되먹여 다시 시킨다
    ENVIRONMENT = "environment"    # 데몬·pull·디스크: 다시 시켜도 소용없다, 환경을 고친다
    HARNESS = "harness"            # 제출 미확인·세션 사망·정체·메뉴: 세션을 갈아치운다
    GATE_DEFECT = "gate_defect"    # 구현 전에도 통과, 명령 자체가 없음: 사람
    CAPABILITY = "capability"      # 같은 지점에서 반복 실패: 모델·effort 상향
    REFUSAL = "refusal"            # 거부 문구 + 코드 변경 없음: 다음 모델
    BUDGET = "budget"              # 턴·유닛·실행 예산 초과


@dataclass
class Classification:
    kind: FailureKind
    evidence: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.kind.value}({'; '.join(self.evidence)})"


# 워커의 자기보고 마커. 완료의 근거가 아니라 **분류의 근거**로만 쓴다.
ENV_MARKER = "ENV-BLOCKED:"
ENV_PATTERNS = tuple(re.compile(p, re.I) for p in (
    r"cannot connect to the docker daemon",
    r"is the docker daemon running",
    r"error response from daemon",
    r"docker: .*(timeout|timed out|hang)",
    r"no space left on device",
    r"disk quota exceeded",
    r"connection refused",
    r"could not resolve host",
    r"temporary failure in name resolution",
    r"network is unreachable",
    r"tls handshake timeout",
    r"read-only file system",
    r"too many open files",
    r"cannot allocate memory",
    r"out of memory",
    r"resource temporarily unavailable",
    r"permission denied .*(docker|/var/run|/dev/)",
))
# 이 턴 결과들은 세션 쪽 문제다: 같은 세션에 되먹여 봐야 소용없고 세션을 갈아치운다.
HARNESS_OUTCOMES = frozenset({
    "eof", "failed", "stalled", "noisy_stagnation", "deadline_exceeded",
    "submit_failed", "unsupported", "interrupted", "awaiting_menu",
    "awaiting_plan_approval", "awaiting_unknown_dialog",
})


def exit_class(result: dict[str, Any] | None) -> str:
    """게이트 결과의 종료 부류: config | spawn | timeout | signal | exit:<n> | none."""
    if not result:
        return "none"
    if result.get("error") in ("config", "spawn"):
        return str(result["error"])
    if result.get("timed_out"):
        return "timeout"
    code = result.get("exit_code")
    if isinstance(code, int) and code < 0:
        return "signal"
    return f"exit:{code}"


def classify(
    gate_result: dict[str, Any] | None = None,
    *,
    turn_outcome: str | None = None,
    response: str = "",
    worktree_changed: bool | None = None,
) -> Classification:
    """한 시도의 결과를 부류로. 순서가 곧 우선순위다.

    1. 턴 자체가 정상 종료가 아니면 하네스 실패(세션 교체).
    2. 거부 문구가 있고 **작업트리가 안 바뀌었으면** 거부(다음 모델).
    3. 게이트 명령이 없거나 실행 자체가 안 되면 게이트 결함(사람).
    4. 출력에 환경 패턴, 응답에 ENV-BLOCKED 마커, 또는 시그널 종료면 환경 실패.
    5. 나머지는 코드 실패(되먹임).
    """
    if turn_outcome and turn_outcome in HARNESS_OUTCOMES:
        return Classification(FailureKind.HARNESS, [f"turn outcome {turn_outcome}"])
    if worktree_changed is False and looks_like_refusal(response):
        return Classification(FailureKind.REFUSAL,
                              ["no worktree change"] + refusal_evidence(response)[:2])
    if gate_result is None:
        return Classification(FailureKind.CODE, ["no gate result"])
    klass = exit_class(gate_result)
    if klass in ("config", "spawn") or gate_result.get("exit_code") == 127:
        return Classification(FailureKind.GATE_DEFECT,
                              [klass, (gate_result.get("tail") or "")[-160:].strip()])
    evidence: list[str] = []
    tail = gate_result.get("tail") or ""
    for pat in ENV_PATTERNS:
        m = pat.search(tail)
        if m:
            evidence.append(f"tail matches /{pat.pattern}/")
            break
    marker = _env_marker_line(response)
    if marker:
        evidence.append(marker)
    if klass == "signal":
        evidence.append(f"exit {gate_result.get('exit_code')} (signal: resource exhaustion?)")
    if evidence:
        return Classification(FailureKind.ENVIRONMENT, evidence)
    return Classification(FailureKind.CODE, [klass])


def _env_marker_line(response: str) -> str | None:
    for line in (response or "").splitlines():
        if line.strip().upper().startswith(ENV_MARKER):
            return line.strip()[:200]
    return None


# --- 지문 -----------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(z|[+-]\d{2}:?\d{2})?\b", re.I)
_CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HEX_RE = re.compile(r"\b(0x)?[0-9a-f]{6,}\b", re.I)
_PATH_RE = re.compile(r"(?:[a-z]:)?(?:[\\/][\w.\-~ ]+){2,}", re.I)
_PID_RE = re.compile(r"\b(pid|process|thread)[ =:#]*\d+\b", re.I)
_NUM_RE = re.compile(r"\d+(\.\d+)?")
_WS_RE = re.compile(r"\s+")
_ERROR_LINE_RE = re.compile(
    r"error|failed|failure|panic|exception|traceback|assert|fatal|denied|cannot|unable|"
    r"timeout|timed out|not found|no such|killed", re.I)


def normalize_failure(text: str | None) -> str:
    """실패 출력의 비교 정규형: 매번 달라지는 값(시각·경로·PID·해시·숫자)을 지운다.

    강한 정규화를 택했다(03 §4 "이번 사고 기준으로는 강한 쪽이 나았겠지만"). 두 실패를
    같다고 볼지 여부는 이 함수가 곧 정의다.
    """
    value = unicodedata.normalize("NFKC", text or "")
    value = _ANSI_RE.sub("", value)
    value = _TS_RE.sub("<ts>", value)
    value = _UUID_RE.sub("<uuid>", value)
    value = _CLOCK_RE.sub("<clock>", value)
    value = _PATH_RE.sub("<path>", value)
    value = _PID_RE.sub(r"\1 <n>", value)
    value = _HEX_RE.sub("<hex>", value)
    value = _NUM_RE.sub("#", value)
    value = value.casefold()
    return _WS_RE.sub(" ", value).strip()


def error_lines(tail: str | None, limit: int = 5) -> list[str]:
    """지문에 넣을 줄: 오류처럼 생긴 첫 `limit`줄, 없으면 마지막 `limit`줄."""
    lines = [ln.strip() for ln in (tail or "").splitlines() if ln.strip()]
    picked = [ln for ln in lines if _ERROR_LINE_RE.search(ln)][:limit]
    return picked or lines[-limit:]


def fingerprint(gate_name: str, klass: str, tail: str | None, *, first_lines: int = 5) -> str:
    """(게이트 이름, 종료 부류, 정규화한 오류 줄들)의 sha256 앞 16자."""
    parts = [gate_name or "", klass or ""] + [normalize_failure(ln)
                                               for ln in error_lines(tail, first_lines)]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def fingerprint_result(gate_name: str, result: dict[str, Any] | None) -> str:
    return fingerprint(gate_name, exit_class(result), (result or {}).get("tail"))


class RepeatTracker:
    """같은 지문이 연속으로 몇 번 나왔나. `limit`에 닿으면 그 대응은 무효다."""

    def __init__(self, limit: int = 2):
        self.limit = max(1, int(limit))
        self.last: str | None = None
        self.streak = 0
        self.seen: dict[str, int] = {}

    def record(self, fp: str) -> int:
        self.seen[fp] = self.seen.get(fp, 0) + 1
        self.streak = self.streak + 1 if fp == self.last else 1
        self.last = fp
        return self.streak

    def exhausted(self) -> bool:
        return self.streak >= self.limit

    def reset(self) -> None:
        self.last, self.streak = None, 0


# --- 사다리 -----------------------------------------------------------------

@dataclass(frozen=True)
class Rung:
    model: str
    effort: str | None

    def label(self) -> str:
        return f"model={self.model} effort={self.effort}"


class Ladder:
    """모델 × effort 칸. 같은 모델에서 effort를 올리고, 다 오르면 다음 모델로.
    거부는 effort와 무관하므로 바로 다음 모델의 첫 칸으로 점프한다."""

    def __init__(self, models: Sequence[str], efforts: Sequence[str | None] = ()):
        if not models:
            raise ValueError("ladder.models must list at least one model")
        self.models = [str(m) for m in models]
        self.efforts = [e for e in efforts] or [None]

    def rungs(self, start_effort: str | None = None, start_model: str | None = None) -> list[Rung]:
        models = list(self.models)
        if start_model and start_model in models:
            models = models[models.index(start_model):]
        elif start_model:
            models = [start_model] + models
        efforts = list(self.efforts)
        if start_effort is not None:
            efforts = (efforts[efforts.index(start_effort):]
                       if start_effort in efforts else [start_effort] + efforts)
        return [Rung(m, e) for m in models for e in efforts]

    def next(self, rungs: Sequence[Rung], current: Rung, reason: str) -> Rung | None:
        """다음 칸. reason이 'refusal'이면 다음 모델의 첫 칸, 아니면 순서상 다음 칸."""
        try:
            i = list(rungs).index(current)
        except ValueError:
            return None
        if reason == "refusal":
            for r in rungs[i + 1:]:
                if r.model != current.model:
                    return r
            return None
        return rungs[i + 1] if i + 1 < len(rungs) else None


# --- 예산 -----------------------------------------------------------------

@dataclass(frozen=True)
class Budget:
    """세 층 예산 + 감지 임계값(rewrite 06의 이름). 전부 유한해야 한다."""

    turn_seconds: float = 3600.0
    unit_turns: int = 12
    unit_wall_seconds: float = 4 * 3600.0
    run_wall_seconds: float = 24 * 3600.0
    stall_seconds: float = 180.0
    progress_seconds: float = 1800.0

    def merged(self, overrides: dict[str, Any] | None) -> "Budget":
        if not overrides:
            return self
        known = {k: v for k, v in overrides.items() if k in self.__dataclass_fields__}
        return replace(self, **known).validated()

    def validated(self) -> "Budget":
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"budget.{name} must be a number, got {value!r}")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"budget.{name} must be finite and positive, got {value!r}")
        if int(self.unit_turns) != self.unit_turns:
            raise ValueError("budget.unit_turns must be an integer")
        return self


class BudgetClock:
    """실행·유닛 시계. `exceeded()`가 어느 층이 터졌는지 말한다."""

    def __init__(self, budget: Budget, clock: Callable[[], float] = time.monotonic):
        self.budget = budget.validated()
        self._clock = clock
        self.run_started = clock()
        self.unit_started: float | None = None
        self.unit_budget = budget

    def start_unit(self, overrides: dict[str, Any] | None = None) -> Budget:
        self.unit_budget = self.budget.merged(overrides)
        self.unit_started = self._clock()
        return self.unit_budget

    def run_elapsed(self) -> float:
        return self._clock() - self.run_started

    def unit_elapsed(self) -> float:
        return 0.0 if self.unit_started is None else self._clock() - self.unit_started

    def remaining_run(self) -> float:
        return max(0.0, self.budget.run_wall_seconds - self.run_elapsed())

    def remaining_unit(self) -> float:
        return max(0.0, self.unit_budget.unit_wall_seconds - self.unit_elapsed())

    def exceeded(self, turns_used: int = 0) -> str | None:
        if self.remaining_run() <= 0:
            return "run"
        if self.unit_started is not None and self.remaining_unit() <= 0:
            return "unit"
        if turns_used >= self.unit_budget.unit_turns:
            return "unit_turns"
        return None

    def turn_budget(self) -> float:
        """한 턴에 줄 수 있는 시간: 턴 예산과 남은 유닛·실행 예산 중 최소(≥1초)."""
        return max(1.0, min(self.unit_budget.turn_seconds, self.remaining_unit(),
                            self.remaining_run()))
