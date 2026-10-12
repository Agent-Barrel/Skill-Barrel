"""환경 점검 -- 세션을 띄우기 전에, 그리고 환경에 민감한 게이트 앞에서.

자율 실행 기록의 사고 2는 아무도 환경을 보지 않아서 시작됐다: 데몬은 살아 있었지만
이미지 pull 경로가 잠겨 있었고, 드라이버는 "게이트 실패"라는 종료 코드 하나만 보고
같은 되먹임을 네 번 반복했다. 여기는 값싼 결정적 검사만 모은다 -- 도구가 PATH에
있는가, 디스크가 남았는가, docker 데몬이 응답하는가, 사용자가 설정에 적은 점검
명령이 0으로 끝나는가, 브랜치·작업트리가 기대와 같은가. 메시지는
`analyze.preflight`의 형식("문제 -- 조치")을 따르되 예외 대신 목록으로 돌려준다:
호출자가 fatal만 막고 warning은 로그로 흘리도록.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from . import gitops

DEFAULT_MIN_FREE_MB = 1024
COMMAND_TIMEOUT = 20


@dataclass
class Finding:
    ok: bool
    check: str                   # tool:<name> | disk | docker | command:<argv0> | branch | worktree | repo
    what: str                    # 무엇을 봤나 / 무엇이 문제인가
    remedy: str = ""             # 조치(문제일 때)
    severity: str = "fatal"      # fatal | warning
    detail: dict[str, Any] = field(default_factory=dict)

    def message(self) -> str:
        if self.ok or not self.remedy:
            return self.what
        return f"{self.what} -- {self.remedy}"


def problems(findings: Iterable[Finding], severity: str | None = None) -> list[Finding]:
    return [f for f in findings if not f.ok and (severity is None or f.severity == severity)]


def summarize(findings: Iterable[Finding]) -> str:
    bad = problems(findings)
    if not bad:
        return "환경 점검 통과"
    return "; ".join(f"[{f.severity}] {f.message()}" for f in bad)


def check_environment(
    repo: str | pathlib.Path,
    *,
    tools: Sequence[str] = ("git",),
    commands: Sequence[Sequence[str]] = (),
    min_free_mb: int = DEFAULT_MIN_FREE_MB,
    docker: bool = False,
    expect_branch: str | None = None,
    clean_tree: bool = False,
    timeout: int = COMMAND_TIMEOUT,
) -> list[Finding]:
    """결정적 검사 묶음. 예외를 던지지 않는다 -- 결과가 곧 판정이다."""
    root = pathlib.Path(repo)
    out: list[Finding] = []

    if not root.is_dir():
        out.append(Finding(False, "repo", f"대상 디렉터리가 없다: {root}",
                           "target_repo 경로를 확인하라"))
        return out

    needs_git = "git" in tools or expect_branch is not None or clean_tree
    if needs_git and not gitops.is_repo(root):
        out.append(Finding(False, "repo", f"git 작업트리가 아니다: {root}",
                           "`git init` 후 커밋 1건을 만들고 다시 시작하라"))

    for tool in tools:
        path = shutil.which(tool)
        if path:
            out.append(Finding(True, f"tool:{tool}", f"{tool}: {path}"))
        else:
            out.append(Finding(False, f"tool:{tool}", f"도구를 찾을 수 없다: {tool}",
                               "설치하거나 PATH에 넣어라"))

    try:
        free_mb = shutil.disk_usage(str(root)).free // (1024 * 1024)
        if free_mb < min_free_mb:
            out.append(Finding(False, "disk", f"디스크 여유가 {free_mb} MB뿐이다 ({root})",
                               f"{min_free_mb} MB 이상 확보하라 -- 빌드·이미지·로그가 실패한다",
                               detail={"free_mb": free_mb}))
        else:
            out.append(Finding(True, "disk", f"디스크 여유 {free_mb} MB",
                               detail={"free_mb": free_mb}))
    except OSError as exc:
        out.append(Finding(False, "disk", f"디스크 용량을 읽지 못했다: {exc}",
                           "경로를 확인하라", severity="warning"))

    if docker:
        if not shutil.which("docker"):
            out.append(Finding(False, "docker", "docker CLI가 없다",
                               "Docker를 설치하거나 preflight.docker를 끄라"))
        else:
            out.append(_run_check("docker", ["docker", "info"], root, timeout,
                                  what_ok="docker 데몬 응답",
                                  what_bad="docker 데몬에 접근할 수 없다",
                                  remedy="Docker Desktop(데몬)을 켜고 pull이 되는지 확인하라"))

    for argv in commands:
        argv = [str(part) for part in argv]
        if not argv:
            continue
        out.append(_run_check(f"command:{argv[0]}", argv, root, timeout,
                              what_ok=f"점검 명령 통과: {' '.join(argv)}",
                              what_bad=f"점검 명령 실패: {' '.join(argv)}",
                              remedy="그 명령이 0으로 끝나게 환경을 고쳐라"))

    if expect_branch is not None and gitops.is_repo(root):
        error = gitops.expect_branch(root, expect_branch)
        out.append(Finding(error is None, "branch",
                           error or f"브랜치 {expect_branch!r} 확인",
                           "" if error is None else "위 조치대로",
                           detail={"expected": expect_branch}))

    if clean_tree and gitops.is_repo(root):
        dirty = gitops.status_porcelain(root)
        if dirty:
            out.append(Finding(False, "worktree",
                               f"커밋되지 않은 변경 {len(dirty)}건이 있다: {'; '.join(dirty[:5])}",
                               "커밋하거나 stash한 뒤 다시 시작하라",
                               detail={"count": len(dirty)}))
        else:
            out.append(Finding(True, "worktree", "작업트리 깨끗함"))
    return out


def _run_check(check: str, argv: list[str], cwd: pathlib.Path, timeout: int, *,
               what_ok: str, what_bad: str, remedy: str) -> Finding:
    try:
        done = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return Finding(False, check, f"{what_bad} ({timeout}초 안에 응답 없음)", remedy,
                       detail={"timed_out": True})
    except (OSError, subprocess.SubprocessError) as exc:
        return Finding(False, check, f"{what_bad} ({exc})", remedy)
    if done.returncode != 0:
        tail = ((done.stderr or "") + (done.stdout or "")).strip()[-300:]
        return Finding(False, check, f"{what_bad} (exit {done.returncode}: {tail})", remedy,
                       detail={"exit_code": done.returncode})
    return Finding(True, check, what_ok)
