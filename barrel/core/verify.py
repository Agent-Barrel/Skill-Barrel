"""검증 실행 -- **오케스트레이터가 테스트를 직접 돌린다**.

세션의 "다 됐습니다"는 증거가 아니다. 04-pipeline 문서의 완료 체크가 전부
"오케스트레이터가 명령을 재실행, 종료 코드 0"인 이유가 이것이고, 이 모듈이 그
재실행을 맡는다. tail은 실패 시 그대로 수정 프롬프트의 본문이 된다.

명령은 `<repo>/project.yaml`에서 온다(`build`/`test`/`e2e`). 선언이 없으면
**스택을 감지해** 기본값을 채운다(`Cargo.toml`→cargo, `go.mod`→go, `pom.xml`→mvn,
`package.json`→npm scripts, 그 밖에는 pytest). 자율 실행 기록이 실증한 "파이프라인이
사실상 파이썬을 전제한다"는 갭이 이 감지로 닫힌다. 감지는 매니페스트 파일에만
반응하고, 선언이 있으면 언제나 선언이 이긴다.

게이트 계약은 넷이다 -- 문자열(shlex 분해, `shell=False`), 인자 목록, **목록의
목록**(다단계, 첫 실패에서 중단), `{"shell": "A && B"}`(셸 위임 옵트인). 실행기는
자식을 **새 프로세스 그룹**으로 띄우고 타임아웃 시 그룹째 죽인다 -- 게이트가
남긴 고아 프로세스가 드라이버에 붙어 다음 게이트를 잠그는 것(자율 실행 기록의
사고 2)을 막기 위해서다. 전체 출력은 `capture_dir`에 남기고 tail만 돌려준다.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

PROJECT_YAML = "project.yaml"
TIMEOUT = 600
TAIL = 4000
KINDS = ("build", "test", "e2e")

# 대상 레포 안에서 찾는 venv 인터프리터 후보(레이아웃별).
_VENV_CANDIDATES = (
    pathlib.PurePath(".venv", "Scripts", "python.exe"),  # Windows
    pathlib.PurePath(".venv", "bin", "python"),  # POSIX
)

# 스택 감지: 매니페스트 파일 → 스택 이름. 순서가 우선순위다(모노레포에서 둘 이상이
# 맞으면 앞의 것). 파이썬은 매니페스트가 없어도 폴백이므로 맨 뒤에 둔다.
STACK_MANIFESTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rust", ("Cargo.toml",)),
    ("go", ("go.mod",)),
    ("maven", ("pom.xml",)),
    ("node", ("package.json",)),
    ("python", ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini")),
    ("make", ("Makefile", "makefile", "GNUmakefile")),
)
_STACK_DEFAULTS: dict[str, dict[str, list[str]]] = {
    "rust": {"build": ["cargo", "build"], "test": ["cargo", "test"]},
    "go": {"build": ["go", "build", "./..."], "test": ["go", "test", "./..."]},
    "maven": {"build": ["mvn", "-q", "-DskipTests", "package"], "test": ["mvn", "-q", "test"]},
}
_MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", re.M)


def venv_python(repo_path: str | pathlib.Path | None = None) -> str:
    """**대상 레포**의 `.venv` 인터프리터, 없으면 현재 인터프리터.

    검증은 대상 프로젝트의 의존성으로 돌아야 한다 -- 오케스트레이터의 venv는
    대상 레포의 패키지를 모른다. 레포에 venv가 없으면 서버를 띄운 인터프리터로
    폴백해 "python이 없다"로 죽지는 않게 한다(신규 프로젝트가 이 경우다).
    """
    if repo_path is not None:
        repo = pathlib.Path(repo_path)
        for candidate in _VENV_CANDIDATES:
            python = repo / candidate
            if python.is_file():
                return str(python)
    return sys.executable


# --- 스택 감지 -------------------------------------------------------------

def detect_stack(repo_path: str | pathlib.Path | None) -> str | None:
    """매니페스트 파일로 스택을 고른다. 모르면 None(파이썬 폴백이 적용된다)."""
    if repo_path is None:
        return None
    repo = pathlib.Path(repo_path)
    for stack, names in STACK_MANIFESTS:
        if any((repo / name).is_file() for name in names):
            return stack
    return None


def _package_scripts(repo: pathlib.Path) -> dict:
    try:
        data = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    scripts = data.get("scripts") if isinstance(data, dict) else None
    return scripts if isinstance(scripts, dict) else {}


def _make_targets(repo: pathlib.Path) -> set[str]:
    for name in ("Makefile", "makefile", "GNUmakefile"):
        path = repo / name
        if path.is_file():
            try:
                return set(_MAKE_TARGET_RE.findall(path.read_text(encoding="utf-8",
                                                                  errors="replace")))
            except OSError:
                return set()
    return set()


def _tool(name: str) -> str:
    """PATH의 실행파일 경로(없으면 이름 그대로 -- 실행 실패가 결과로 보고된다).
    Windows의 npm.cmd/mvn.cmd는 which로만 찾힌다."""
    return shutil.which(name) or name


def default_command(
    kind: str = "test", repo_path: str | pathlib.Path | None = None
) -> list[str] | None:
    """스택별 기본 명령. 선언이 없을 때만 쓰인다(`resolve_gate`)."""
    stack = detect_stack(repo_path)
    if stack is None or stack == "python":
        if kind == "test":
            return [venv_python(repo_path), "-m", "pytest", "-q"]
        return None
    repo = pathlib.Path(repo_path)
    if stack == "node":
        scripts = _package_scripts(repo)
        if kind == "test" and "test" in scripts:
            return [_tool("npm"), "test"]
        if kind == "build" and "build" in scripts:
            return [_tool("npm"), "run", "build"]
        return None
    if stack == "make":
        return [_tool("make"), kind] if kind in _make_targets(repo) else None
    table = _STACK_DEFAULTS[stack]
    if kind not in table:
        return None
    argv = list(table[kind])
    argv[0] = _tool(argv[0])
    return argv


# --- 게이트 명령 계약 ------------------------------------------------------

@dataclass
class GateCommand:
    """실행할 것. `shell`이 있으면 셸 한 줄(옵트인), 아니면 `steps`(argv 목록들)."""

    steps: list[list[str]] = field(default_factory=list)
    shell: str | None = None
    source: str = "spec"        # project.yaml | spec | detected:<stack> | default
    kind: str = "test"

    @property
    def argv(self) -> list[str] | None:
        """단일 단계·비셸일 때의 평평한 argv(구 `resolve_command` 호환)."""
        if self.shell is None and len(self.steps) == 1:
            return list(self.steps[0])
        return None

    def display(self) -> str:
        """사람이 읽을(그리고 세션에 지시할) 한 줄."""
        if self.shell is not None:
            return self.shell
        return " && ".join(_join(step) for step in self.steps)


def _join(argv: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def _tail(*chunks: str) -> str:
    joined = "\n".join(chunk for chunk in chunks if chunk)
    return joined[-TAIL:]


def _tokens(command: str) -> list[str]:
    """문자열 명령을 인자 목록으로. shell=False로 돌리기 위한 분해다.

    POSIX에서는 표준 셸 인용 규칙(shlex posix 모드)을 그대로 따른다.
    Windows에서만 `posix=False`: 경로의 역슬래시를 이스케이프로 먹지 않는다.
    대신 따옴표가 토큰에 남으므로 직접 벗긴다.
    """
    if sys.platform != "win32":
        return shlex.split(command)
    stripped = []
    for token in shlex.split(command, posix=False):
        if len(token) > 1 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        stripped.append(token)
    return stripped


def _step(value: Any, kind: str) -> tuple[list[str] | None, str | None]:
    if isinstance(value, str):
        tokens = _tokens(value)
        return (tokens, None) if tokens else (None, f"'{kind}' 명령이 비었다")
    if isinstance(value, (list, tuple)):
        if not value:
            return None, f"'{kind}' 명령이 비었다"
        if not all(isinstance(part, (str, int, float)) for part in value):
            return None, f"'{kind}' 명령의 인자가 문자열이 아니다"
        return [str(part) for part in value], None
    return None, f"'{kind}' 명령 형식이 잘못됐다: {type(value).__name__}"


def parse_spec(spec: Any, *, kind: str = "test", source: str = "spec"
               ) -> tuple[GateCommand | None, str | None]:
    """게이트 spec → GateCommand. 순수 함수; 오류는 문자열로.

    받는 모양: 문자열 / 인자 목록 / 목록의 목록(다단계) /
    `{"shell": "A && B"}` / `{"steps": [...]}` / `{"argv": [...]}`.
    """
    if isinstance(spec, dict):
        if "shell" in spec:
            line = spec["shell"]
            if not isinstance(line, str) or not line.strip():
                return None, f"'{kind}'의 shell 명령이 비었다"
            return GateCommand(shell=line.strip(), source=source, kind=kind), None
        if "steps" in spec:
            return parse_spec(spec["steps"], kind=kind, source=source)
        if "argv" in spec:
            return parse_spec([spec["argv"]], kind=kind, source=source)
        return None, f"'{kind}' 명령 매핑에 shell/steps/argv가 없다"
    if isinstance(spec, (list, tuple)) and spec and any(
            isinstance(item, (list, tuple)) for item in spec):
        # 다단계: 항목마다 argv 목록 또는 명령 문자열.
        steps = []
        for item in spec:
            argv, error = _step(item, kind)
            if error is not None:
                return None, error
            steps.append(argv)
        return GateCommand(steps=steps, source=source, kind=kind), None
    argv, error = _step(spec, kind)
    if error is not None:
        return None, error
    return GateCommand(steps=[argv], source=source, kind=kind), None


def project_config(repo_path: str | pathlib.Path) -> tuple[dict[str, Any], str | None]:
    """(project.yaml 내용, 오류). 파일이 없으면 ({}, None)."""
    path = pathlib.Path(repo_path) / PROJECT_YAML
    if not path.is_file():
        return {}, None
    try:
        import yaml  # 지연 임포트: pyyaml이 없어도 기본 명령은 돌아야 한다
    except ImportError:
        return {}, None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # yaml.YAMLError 및 인코딩 사고
        return {}, f"{PROJECT_YAML}을 읽지 못했다: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return {}, f"{PROJECT_YAML}의 최상위가 매핑이 아니다"
    return data, None


def resolve_gate(repo_path: str | pathlib.Path | None, kind_or_spec: Any = "test"
                 ) -> tuple[GateCommand | None, str | None]:
    """(GateCommand, 오류). 종류 이름(`build`/`test`/`e2e`)이면 project.yaml →
    스택 기본값 순으로 찾고, 그 밖의 값은 spec 그 자체로 해석한다."""
    if not (isinstance(kind_or_spec, str) and kind_or_spec in KINDS):
        return parse_spec(kind_or_spec, kind="spec", source="spec")
    kind = kind_or_spec
    declared = None
    if repo_path is not None:
        config, error = project_config(repo_path)
        if error is not None:
            return None, error
        declared = config.get(kind)
        if declared is None and isinstance(config.get("commands"), dict):
            declared = config["commands"].get(kind)
    if declared is not None:
        gate, error = parse_spec(declared, kind=kind, source=PROJECT_YAML)
        if error is not None:
            return None, f"{PROJECT_YAML}의 {error}"
        return gate, None
    fallback = default_command(kind, repo_path)
    if fallback is None:
        return None, f"{PROJECT_YAML}에 '{kind}' 명령이 없고 기본값도 없다"
    stack = detect_stack(repo_path)
    return GateCommand(steps=[fallback], kind=kind,
                       source=f"detected:{stack}" if stack else "default"), None


def resolve_command(
    repo_path: str | pathlib.Path, kind: str = "test"
) -> tuple[list[str] | None, str | None]:
    """(명령, 오류) -- 단일 단계·비셸 게이트를 평평한 argv로 주는 호환 API.
    다단계나 셸 게이트는 `resolve_gate`로 읽어야 한다."""
    gate, error = resolve_gate(repo_path, kind)
    if gate is None:
        return None, error
    argv = gate.argv
    if argv is None:
        return None, f"{PROJECT_YAML}의 '{kind}' 명령이 다단계/셸 형식이다 -- resolve_gate로 읽어라"
    return argv, None


def command_string(repo_path: str | pathlib.Path | None, kind: str = "test") -> str:
    """세션에 "이 명령을 직접 돌려 확인하라"고 지시할 때 쓰는 한 줄. 해석 실패면 빈 문자열."""
    gate, _error = resolve_gate(repo_path, kind)
    return gate.display() if gate is not None else ""


# --- 실행 -----------------------------------------------------------------

def _spawn(cmd: list[str] | str, cwd: str, shell: bool) -> subprocess.Popen:
    kwargs: dict[str, Any] = dict(
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", shell=shell,
    )
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _kill_group(proc: subprocess.Popen) -> None:
    """자식이 만든 프로세스 트리를 통째로 죽인다(그룹 리더 = 자식)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _run_one(cmd: list[str] | str, *, cwd: str, timeout: int, shell: bool) -> dict[str, Any]:
    step: dict[str, Any] = {
        ("shell" if shell else "argv"): cmd, "exit_code": -1, "output": "",
        "timed_out": False, "duration": 0.0, "error": None,
    }
    started = time.monotonic()
    try:
        proc = _spawn(cmd, cwd, shell)
    except (OSError, subprocess.SubprocessError) as exc:
        step["output"] = f"명령을 실행하지 못했다: {exc}"
        step["error"] = "spawn"
        step["duration"] = time.monotonic() - started
        return step
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out = ""
        step["timed_out"] = True
        step["error"] = "timeout"
        step["output"] = (out or "") + f"\n[타임아웃] {timeout}초 안에 끝나지 않았다"
        step["exit_code"] = proc.returncode if proc.returncode is not None else -1
        step["duration"] = time.monotonic() - started
        return step
    step["exit_code"] = proc.returncode
    step["output"] = out or ""
    step["duration"] = time.monotonic() - started
    return step


def _capture(capture_dir, name: str, gate: GateCommand, cwd: str, steps: list[dict],
             started_at: float) -> str | None:
    """전체 출력을 파일로. tail은 되먹임에 충분하지만 사후 분석에는 부족하다."""
    if capture_dir is None:
        return None
    try:
        directory = pathlib.Path(capture_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(started_at))
        path = directory / f"{name}-{stamp}.log"
        lines = [f"# gate {name} ({gate.source}) in {cwd}", f"# $ {gate.display()}", ""]
        for i, step in enumerate(steps, 1):
            what = step.get("shell") or _join(step.get("argv") or [])
            lines.append(f"## step {i}: {what}")
            lines.append(f"## exit={step['exit_code']} duration={step['duration']:.1f}s"
                         f"{' TIMEOUT' if step['timed_out'] else ''}")
            lines.append(step["output"])
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
        return str(path)
    except OSError:
        return None


def run_command(
    command: Any, *, cwd: str | pathlib.Path, timeout: int = TIMEOUT,
    capture_dir: str | pathlib.Path | None = None, name: str | None = None,
) -> dict[str, Any]:
    """GateCommand(또는 spec)를 `cwd`에서 실행. 예외를 밖으로 내보내지 않는다.

    `{"ok", "exit_code", "tail", "cmd", "kind", "timed_out", "duration",
    "started_at", "source", "output_path", "steps", "error"}`. 다단계는 첫 실패에서
    멈춘다. `cmd`는 단일 단계면 평평한 argv, 다단계면 목록의 목록, 셸이면 문자열.
    `error`는 기계용 부류: config | spawn | timeout | None(실행은 됐고 종료코드가 답).
    """
    gate = command
    if not isinstance(gate, GateCommand):
        gate, error = parse_spec(command, kind="spec")
        if gate is None:
            return _failure(error or "실행할 명령을 찾지 못했다", kind="spec", error="config")
    started_at = time.time()
    result: dict[str, Any] = {
        "ok": False, "exit_code": -1, "tail": "", "kind": gate.kind,
        "timed_out": False, "duration": 0.0, "started_at": started_at,
        "source": gate.source, "output_path": None, "steps": [], "error": None,
        "cmd": (gate.shell if gate.shell is not None
                else (gate.argv if gate.argv is not None else [list(s) for s in gate.steps])),
    }
    workdir = pathlib.Path(cwd)
    if not workdir.is_dir():
        result["tail"] = f"작업 디렉터리가 없다: {workdir}"
        result["error"] = "config"
        return result
    plan: list[tuple[Any, bool]] = ([(gate.shell, True)] if gate.shell is not None
                                    else [(step, False) for step in gate.steps])
    outputs: list[str] = []
    ok = True
    for cmd, shell in plan:
        step = _run_one(cmd, cwd=str(workdir), timeout=timeout, shell=shell)
        result["steps"].append(step)
        outputs.append(step["output"])
        result["exit_code"] = step["exit_code"]
        result["duration"] += step["duration"]
        if step["timed_out"]:
            result["timed_out"] = True
        if step["error"] is not None:
            result["error"] = step["error"]
        if step["exit_code"] != 0 or step["error"] is not None:
            ok = False
            break
    result["ok"] = ok
    result["tail"] = _tail(*outputs)
    result["output_path"] = _capture(capture_dir, name or gate.kind, gate, str(workdir),
                                     result["steps"], started_at)
    return result


def _failure(message: str, *, kind: str, error: str) -> dict[str, Any]:
    return {"ok": False, "exit_code": -1, "tail": message, "cmd": [], "kind": kind,
            "timed_out": False, "duration": 0.0, "started_at": time.time(),
            "source": None, "output_path": None, "steps": [], "error": error}


def run_verify(
    repo_path: str | pathlib.Path, kind: str = "test", *, timeout: int = TIMEOUT,
    capture_dir: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """`kind`의 명령을 repo에서 실행하고 `run_command`와 같은 dict를 돌려준다.

    예외를 밖으로 내보내지 않는다 -- 실행 실패도 "검증 실패"라는 결과이고,
    호출자는 tail을 그대로 세션에 되먹인다.
    """
    repo = pathlib.Path(repo_path)
    gate, error = resolve_gate(repo, kind)
    if gate is None:
        return _failure(error or "실행할 명령을 찾지 못했다", kind=kind, error="config")
    result = run_command(gate, cwd=repo, timeout=timeout, capture_dir=capture_dir, name=kind)
    result["kind"] = kind
    return result


def run_gate(
    repo_path: str | pathlib.Path, spec: Any, *, timeout: int = TIMEOUT,
    capture_dir: str | pathlib.Path | None = None, name: str | None = None,
) -> dict[str, Any]:
    """임의 게이트 spec(문자열/목록/목록의 목록/{"shell"})을 실행. 드라이버용."""
    gate, error = resolve_gate(repo_path, spec)
    if gate is None:
        return _failure(error or "실행할 명령을 찾지 못했다", kind=name or "gate", error="config")
    if name:
        gate.kind = name
    return run_command(gate, cwd=repo_path, timeout=timeout, capture_dir=capture_dir, name=name)


def _decode(chunk: Any) -> str:
    if chunk is None:
        return ""
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", errors="replace")
    return str(chunk)
