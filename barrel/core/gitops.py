"""git 체크포인트 -- **커밋의 주체는 오케스트레이터다**, 세션이 아니다.

정본(features.csv)과 문서가 바뀔 때마다 커밋 1건을 남긴다. 이 체크포인트가
멱등 재실행·롤백·영향 diff의 기준점이다(04-pipeline 문서).

이 모듈은 **예외를 던지지 않는다**. git이 없거나 커밋이 실패해도 파이프라인은
멈추지 않고, 호출자가 반환된 `error`를 warn 이벤트로 남긴다 -- 프로젝트 생성이
`git init` 실패를 경고로만 처리하는 기존 정책과 같은 선택이다.

author를 `-c user.name/user.email`로 주입하는 이유: 전역 git config가 없는
환경(새 PC, CI, tmp HOME)에서도 커밋이 성립해야 한다.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import stat
import subprocess
from typing import Any, Iterable, Sequence

AUTHOR_NAME = "Barrel"
AUTHOR_EMAIL = "barrel@local"
TIMEOUT = 60
# clone은 60초로 못 묶는 유일한 작업이다(원격 크기를 모른다).
CLONE_TIMEOUT = 600


def _run(repo: pathlib.Path, *args: str, timeout: int = TIMEOUT,
         env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """(exit_code, stdout, stderr). 실행 자체가 불가능하면 코드 -1."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, "", str(exc)
    return done.returncode, done.stdout or "", done.stderr or ""


def git_available() -> bool:
    return shutil.which("git") is not None


def is_repo(path: str | pathlib.Path) -> bool:
    return (pathlib.Path(path) / ".git").exists()


def ensure_repo(path: str | pathlib.Path) -> str | None:
    """레포가 아니면 `git init`. 오류 문자열 또는 None(성공)."""
    repo = pathlib.Path(path)
    if is_repo(repo):
        return None
    if not repo.is_dir():
        return f"디렉터리가 없다: {repo}"
    code, out, err = _run(repo, "init", "-q")
    if code != 0:
        return (err or out or f"git init exited {code}").strip()
    return None


def _relative(repo: pathlib.Path, path: str | pathlib.Path) -> str:
    candidate = pathlib.Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(repo)
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def commit(
    repo: str | pathlib.Path,
    paths: str | pathlib.Path | Iterable[str | pathlib.Path],
    message: str,
) -> dict[str, Any]:
    """지정 경로만 스테이징해 커밋 1건.

    `{"committed", "sha", "message", "paths", "error"}`. 스테이징 후 변경이
    없으면 no-op(`committed=False`, `error=None`) -- 같은 상태를 두 번 기록하는
    호출이 빈 커밋을 만들지 않게 한다.
    """
    root = pathlib.Path(repo)
    if isinstance(paths, (str, pathlib.PurePath)):
        paths = [paths]
    relatives = [_relative(root, p) for p in paths]
    result: dict[str, Any] = {
        "committed": False,
        "sha": None,
        "message": message,
        "paths": relatives,
        "error": None,
    }
    if not relatives:
        result["error"] = "커밋할 경로가 없다"
        return result
    if not is_repo(root):
        result["error"] = f"git 레포가 아니다: {root}"
        return result

    # -A: 삭제도 스테이징된다. `--`로 경로를 옵션과 분리한다.
    code, out, err = _run(root, "add", "-A", "--", *relatives)
    if code != 0:
        result["error"] = (err or out or f"git add exited {code}").strip()
        return result

    # pathspec 없는 `diff --cached`는 인덱스 **전체**를 본다 -- 세션이 남긴
    # 무관한 스테이징 때문에 무변경 커밋이 실패로 오보되지 않게 대상 경로만 본다.
    code, out, err = _run(root, "diff", "--cached", "--quiet", "--", *relatives)
    if code == 0:
        return result  # 변경 없음 -- no-op
    if code not in (1,):
        result["error"] = (err or out or f"git diff --cached exited {code}").strip()
        return result

    code, out, err = _run(
        root,
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "-m", message, "--", *relatives,
    )
    if code != 0:
        result["error"] = (err or out or f"git commit exited {code}").strip()
        return result

    result["committed"] = True
    result["sha"] = head_sha(root)
    return result


def _unstage(repo: pathlib.Path, relatives: Sequence[str]) -> tuple[int, str, str]:
    """색인에서만 뺀다(작업트리는 그대로).

    첫 커밋 전에는 `reset HEAD`가 성립하지 않으므로 색인에서 지우는 쪽을 쓴다 --
    HEAD가 없으면 "색인에서 지운다"가 곧 "스테이징을 취소한다"이다.
    """
    if head_sha(repo) is not None:
        return _run(repo, "reset", "-q", "HEAD", "--", *relatives)
    return _run(repo, "rm", "--cached", "-q", "--ignore-unmatch", "--", *relatives)


def commit_all(
    repo: str | pathlib.Path,
    message: str,
    *,
    exclude: str | pathlib.Path | Iterable[str | pathlib.Path] = (),
) -> dict[str, Any]:
    """작업트리의 **변경·신규 파일 전부**를 커밋 1건으로(단, `exclude`는 뺀다).

    `commit()`은 무엇을 커밋할지 아는 호출자의 것이다. 이쪽은 목록을 **모를 때**
    쓴다 -- 개발 배치가 워크스페이스에 무엇을 만들었는지는 세션만 알고, 그래도
    커밋의 주체는 오케스트레이터여야 한다(04-pipeline).

    `exclude`가 있는 이유는 하나다: features.csv는 상태 전이가 자기 커밋으로
    남기므로, 코드 커밋에 섞이면 이력이 두 사건을 하나로 붙여 말하게 된다.

    반환은 `commit()`과 같은 모양 + `excluded`. `paths`는 실제로 커밋에 담긴
    파일들이다(스테이징 결과이지 호출자가 지정한 것이 아니므로).
    """
    root = pathlib.Path(repo)
    if isinstance(exclude, (str, pathlib.PurePath)):
        exclude = [exclude]
    excluded = [_relative(root, p) for p in exclude]
    result: dict[str, Any] = {
        "committed": False,
        "sha": None,
        "message": message,
        "paths": [],
        "excluded": excluded,
        "error": None,
    }
    if not is_repo(root):
        result["error"] = f"git 레포가 아니다: {root}"
        return result

    code, out, err = _run(root, "add", "-A")
    if code != 0:
        result["error"] = (err or out or f"git add exited {code}").strip()
        return result

    if excluded:
        code, out, err = _unstage(root, excluded)
        if code != 0:
            result["error"] = (err or out or f"git unstage exited {code}").strip()
            return result

    # `core.quotepath=false`: 한글 경로가 `\355\225\234`로 돌아오면 이벤트에도
    # 테스트에도 쓸 수 없다.
    code, out, err = _run(root, "-c", "core.quotepath=false", "diff", "--cached", "--name-only")
    if code != 0:
        result["error"] = (err or out or f"git diff --cached exited {code}").strip()
        return result
    staged = [line.strip() for line in out.splitlines() if line.strip()]
    if not staged:
        return result  # 커밋할 것이 없다 -- no-op

    code, out, err = _run(
        root,
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "-m", message,
    )
    if code != 0:
        result["error"] = (err or out or f"git commit exited {code}").strip()
        return result

    result["committed"] = True
    result["paths"] = staged
    result["sha"] = head_sha(root)
    return result


def clone(
    url: str, dest: str | pathlib.Path, *, timeout: int = CLONE_TIMEOUT
) -> dict[str, Any]:
    """`git clone <url> <dest>` -- 이 모듈의 규칙대로 예외를 던지지 않는다.

    `{"cloned", "url", "dest", "error", "stderr_tail"}`. private/404 URL은
    크레덴셜 프롬프트에 매달리지 않고 즉시 실패한다(GIT_TERMINAL_PROMPT=0 +
    빈 credential.helper). 실패하면 부분 산출물을 지워 재시도가 빈 자리에서
    시작하게 한다. **full clone이다**: analyze가 히스토리를 쓰고, shallow는
    이후 push를 복잡하게 만든다. 크기가 문제 되면 `--filter=blob:none`이 다음
    손잡이다.
    """
    target = pathlib.Path(dest)
    result: dict[str, Any] = {
        "cloned": False, "url": url, "dest": str(target),
        "error": None, "stderr_tail": "",
    }
    if target.exists():
        # 파일이면 iterdir()가 NotADirectoryError를 던진다 -- 이 모듈은 예외를
        # 던지지 않으므로 결과로 말한다.
        if not target.is_dir():
            result["error"] = f"대상 경로가 디렉터리가 아니다: {target}"
            return result
        if any(target.iterdir()):
            result["error"] = f"대상 디렉터리가 비어 있지 않다: {target}"
            return result
    target.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    try:
        done = subprocess.run(
            ["git", "-c", "credential.helper=", "clone", "--", url, str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
        remove_tree(target)
        return result
    if done.returncode != 0:
        tail = ((done.stderr or done.stdout) or "").strip()
        result["error"] = f"git clone exited {done.returncode}"
        result["stderr_tail"] = tail[-500:]
        remove_tree(target)
        return result
    result["cloned"] = True
    return result


def remove_tree(path: str | pathlib.Path) -> None:
    """rmtree, 윈도우의 읽기 전용 .git 오브젝트까지. 실패는 삼킨다."""
    target = pathlib.Path(path)
    if not target.exists():
        return
    if not target.is_dir():
        # 크래시가 같은 이름의 **파일**을 남겼을 수도 있다 -- rmtree는 파일에
        # NotADirectoryError를 내므로 직접 치운다.
        try:
            _make_writable(target)
            target.unlink()
        except OSError:
            pass
        return

    def _onexc(func, p, _exc):
        try:
            _make_writable(p)
            if pathlib.Path(p) != target:
                # POSIX에서 unlink/rmdir를 막는 것은 대상이 아니라 **부모
                # 디렉터리**의 쓰기 권한이다 (git objects 트리가 정확히 이 꼴).
                # 부모는 target 안쪽이므로 트리 밖을 건드리지 않는다.
                _make_writable(os.path.dirname(str(p)))
            func(p)
        except OSError:
            pass

    try:
        shutil.rmtree(target, onexc=_onexc)
    except OSError:
        pass


def _make_writable(p: str | pathlib.Path) -> None:
    # 기존 모드에 비트를 더하기만 한다. stat.S_IWRITE를 절대 모드로 주면
    # POSIX에서 0o200이 되어 디렉터리의 r/x까지 벗겨져 원래 실패보다 악화된다.
    st = os.stat(p)
    extra = stat.S_IWUSR
    if stat.S_ISDIR(st.st_mode):
        extra |= stat.S_IRUSR | stat.S_IXUSR
    os.chmod(p, st.st_mode | extra)


def current_branch(repo: str | pathlib.Path) -> str | None:
    code, out, _err = _run(pathlib.Path(repo), "rev-parse", "--abbrev-ref", "HEAD")
    return out.strip() if code == 0 and out.strip() else None


def expect_branch(repo: str | pathlib.Path, branch: str) -> str | None:
    """실행 시작 시 한 번 확인한다: 기대 브랜치가 아니면 조치를 적은 오류 문자열.

    자율 실행은 여러 시간 동안 커밋을 쌓으므로, 엉뚱한 브랜치에서 시작한 실행은
    시작하지 않는 편이 되돌리기보다 싸다(자율 실행 기록 04 §6).
    """
    current = current_branch(repo)
    if current is None:
        return f"브랜치를 알 수 없다: {repo} -- git 레포이고 커밋이 1건 이상인지 확인하라"
    if current != branch:
        return (f"현재 브랜치가 {current!r}다 -- {branch!r}로 전환하거나 설정의 "
                f"브랜치를 바꾸거나 allow_any_branch를 켜라")
    return None


def push(
    repo: str | pathlib.Path, remote: str = "origin", branch: str | None = None,
    *, timeout: int = CLONE_TIMEOUT,
) -> dict[str, Any]:
    """`git push <remote> <branch>` -- 이 모듈의 규칙대로 예외를 던지지 않는다.

    `{"pushed", "remote", "branch", "output", "error"}`. branch가 None이면 현재
    브랜치. 크레덴셜 프롬프트에 매달리지 않는다(GIT_TERMINAL_PROMPT=0).
    """
    root = pathlib.Path(repo)
    result: dict[str, Any] = {"pushed": False, "remote": remote, "branch": branch,
                              "output": "", "error": None}
    if not is_repo(root):
        result["error"] = f"git 레포가 아니다: {root}"
        return result
    if branch is None:
        branch = current_branch(root)
        result["branch"] = branch
        if branch is None:
            result["error"] = "브랜치를 알 수 없다"
            return result
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    code, out, err = _run(root, "push", remote, f"{branch}:{branch}",
                          timeout=timeout, env=env)
    result["output"] = (err or out).strip()[-1000:]
    if code != 0:
        result["error"] = f"git push exited {code}: {result['output'][-300:]}"
        return result
    result["pushed"] = True
    return result


def head_sha(repo: str | pathlib.Path) -> str | None:
    code, out, _err = _run(pathlib.Path(repo), "rev-parse", "HEAD")
    return out.strip() if code == 0 and out.strip() else None


def log_subjects(repo: str | pathlib.Path, limit: int = 20) -> list[str]:
    """최근 커밋 제목들(최신 우선). 레포가 비어 있으면 빈 목록."""
    code, out, _err = _run(pathlib.Path(repo), "log", f"-{int(limit)}", "--format=%s")
    if code != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def status_porcelain(repo: str | pathlib.Path) -> list[str]:
    """`git status --porcelain -uall` 줄들 -- 커밋 범위 검증용.

    `-uall`: 기본값은 추적되지 않은 디렉터리를 `?? src/` 한 줄로 접어버려서
    "무엇이 커밋되지 않고 남았나"를 파일 단위로 볼 수 없다.
    """
    code, out, _err = _run(pathlib.Path(repo), "status", "--porcelain", "-uall")
    if code != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def commit_files(repo: str | pathlib.Path, ref: str = "HEAD") -> list[str]:
    """해당 커밋이 실제로 담은 파일 목록."""
    code, out, _err = _run(pathlib.Path(repo), "show", "--name-only", "--format=", ref)
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]
