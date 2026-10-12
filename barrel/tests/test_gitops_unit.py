"""gitops 경계 사례 -- 커밋 no-op 판정과 clone 대상 검사.

이 모듈의 계약은 "예외를 던지지 않는다"이다. 여기서는 그 계약이 깨지던
경계(대상이 파일인 clone)와, 인덱스 전체를 보던 no-op 판정을 고정한다.
"""
from __future__ import annotations

import subprocess

import pytest

from barrel.core import gitops

pytestmark = pytest.mark.skipif(not gitops.git_available(), reason="git이 없다")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def test_commit_nop_ignores_unrelated_staged_files(repo):
    """세션이 남긴 무관한 스테이징이 무변경 커밋을 실패로 오보하면 안 된다."""
    (repo / "a.txt").write_text("a", encoding="utf-8")
    first = gitops.commit(repo, ["a.txt"], "first")
    assert first["committed"] is True

    # 세션(bypass)이 git add만 해 두고 간 파일 -- 인덱스는 더럽지만 a.txt는 무변경.
    (repo / "junk.txt").write_text("junk", encoding="utf-8")
    subprocess.run(["git", "add", "junk.txt"], cwd=repo, check=True)

    again = gitops.commit(repo, ["a.txt"], "again")

    assert again["committed"] is False and again["error"] is None  # 조용한 no-op
    assert gitops.log_subjects(repo) == ["first"]


def test_clone_onto_a_file_reports_instead_of_raising(tmp_path):
    target = tmp_path / "dest"
    target.write_text("파일이다", encoding="utf-8")

    result = gitops.clone("https://example.invalid/repo.git", target)

    assert result["cloned"] is False
    assert "디렉터리가 아니다" in result["error"]
    assert target.exists()  # 남의 파일을 지우지 않는다


def test_remove_tree_also_removes_a_stray_file(tmp_path):
    target = tmp_path / "stray"
    target.write_text("x", encoding="utf-8")

    gitops.remove_tree(target)

    assert not target.exists()


# --- push / expect_branch (autonomy 04 §6, 05 "푸시와 브랜치 강제를 선택으로") ----

def _commit(repo, name):
    (repo / name).write_text(name, encoding="utf-8")
    assert gitops.commit(repo, [name], f"add {name}")["committed"]


def test_expect_branch_reports_a_mismatch_with_a_remedy(repo):
    _commit(repo, "a.txt")
    branch = gitops.current_branch(repo)
    assert gitops.expect_branch(repo, branch) is None
    message = gitops.expect_branch(repo, "release")
    assert "'release'" in message and "allow_any_branch" in message


def test_expect_branch_without_a_commit(repo):
    assert "브랜치를 알 수 없다" in gitops.expect_branch(repo, "main")


def test_push_to_a_local_bare_remote(repo, tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    _commit(repo, "a.txt")
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    branch = gitops.current_branch(repo)

    result = gitops.push(repo, "origin")

    assert result["pushed"] is True and result["branch"] == branch and result["error"] is None
    head = subprocess.run(["git", "rev-parse", branch], cwd=bare, capture_output=True,
                          text=True, check=True).stdout.strip()
    assert head == gitops.head_sha(repo)


def test_push_failure_is_reported_not_raised(repo):
    _commit(repo, "a.txt")
    result = gitops.push(repo, "nowhere")
    assert result["pushed"] is False and "git push exited" in result["error"]
    assert gitops.push(repo / "missing", "origin")["error"].startswith("git 레포가 아니다")
