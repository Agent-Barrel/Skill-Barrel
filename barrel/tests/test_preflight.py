"""환경 점검 -- 도구·디스크·docker·사용자 명령·브랜치·작업트리."""
from __future__ import annotations

import collections
import subprocess
import sys

import pytest

from barrel.core import gitops, preflight

PY = sys.executable
pytestmark = pytest.mark.skipif(not gitops.git_available(), reason="git이 없다")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "a.txt").write_text("a", encoding="utf-8")
    assert gitops.commit(root, ["a.txt"], "init")["committed"]
    return root


def _by_check(findings):
    return {f.check: f for f in findings}


def test_missing_tool_is_fatal_with_a_remedy(repo):
    findings = preflight.check_environment(repo, tools=["git", "definitely-not-a-tool-xyz"],
                                           min_free_mb=1)
    by = _by_check(findings)
    assert by["tool:git"].ok
    bad = by["tool:definitely-not-a-tool-xyz"]
    assert not bad.ok and bad.severity == "fatal" and "PATH" in bad.remedy
    assert "--" in bad.message()
    assert preflight.problems(findings, "fatal") == [bad]
    assert "definitely-not-a-tool-xyz" in preflight.summarize(findings)


def test_low_disk_is_fatal(repo, monkeypatch):
    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr(preflight.shutil, "disk_usage", lambda p: Usage(10, 9, 100 * 1024 * 1024))
    by = _by_check(preflight.check_environment(repo, tools=[], min_free_mb=1024))
    assert not by["disk"].ok and by["disk"].detail["free_mb"] == 100
    by = _by_check(preflight.check_environment(repo, tools=[], min_free_mb=50))
    assert by["disk"].ok


def test_user_commands_must_exit_zero(repo):
    ok_cmd = [PY, "-c", "print('fine')"]
    bad_cmd = [PY, "-c", "import sys; print('nope'); sys.exit(2)"]
    by = _by_check(preflight.check_environment(repo, tools=[], min_free_mb=1,
                                               commands=[ok_cmd, bad_cmd]))
    assert by[f"command:{PY}"].ok is False           # the failing one wins the key
    assert "exit 2" in by[f"command:{PY}"].what and "nope" in by[f"command:{PY}"].what


def test_docker_without_cli_is_fatal(repo, monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: None if name == "docker" else "/usr/bin/" + name)
    by = _by_check(preflight.check_environment(repo, tools=[], min_free_mb=1, docker=True))
    assert not by["docker"].ok and "docker" in by["docker"].remedy.lower()


def test_branch_and_worktree_checks(repo):
    branch = gitops.current_branch(repo)
    by = _by_check(preflight.check_environment(repo, min_free_mb=1, expect_branch=branch,
                                               clean_tree=True))
    assert by["branch"].ok and by["worktree"].ok
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    by = _by_check(preflight.check_environment(repo, min_free_mb=1, expect_branch="release",
                                               clean_tree=True))
    assert not by["branch"].ok and "allow_any_branch" in by["branch"].what
    assert not by["worktree"].ok and "dirty.txt" in by["worktree"].what


def test_missing_directory_and_non_repo(tmp_path):
    findings = preflight.check_environment(tmp_path / "ghost")
    assert [f.check for f in findings] == ["repo"] and not findings[0].ok
    plain = tmp_path / "plain"
    plain.mkdir()
    by = _by_check(preflight.check_environment(plain, tools=["git"], min_free_mb=1))
    assert not by["repo"].ok and "git init" in by["repo"].remedy
