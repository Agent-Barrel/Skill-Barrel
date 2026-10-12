"""run_verify -- 오케스트레이터가 직접 돌리는 완료 체크."""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

from barrel.core import verify

# repo 인자가 없으면(또는 repo에 venv가 없으면) 현재 인터프리터다.
PY = verify.venv_python()


# --- 인터프리터 선택 --------------------------------------------------------

def test_repo_venv_interpreter_wins(tmp_path):
    """검증은 대상 레포의 의존성으로 돌아야 한다 -- 레포 venv가 최우선이다."""
    root = tmp_path / "repo"
    parts = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    exe = root / ".venv" / parts[0] / parts[1]
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")

    assert verify.venv_python(root) == str(exe)
    command, error = verify.resolve_command(root)
    assert error is None and command == [str(exe), "-m", "pytest", "-q"]


def test_without_a_repo_venv_the_current_interpreter_runs(tmp_path):
    assert verify.venv_python(tmp_path / "repo") == sys.executable
    assert verify.venv_python() == sys.executable

PASSING = "def test_feat_001_always_true():\n    assert True\n"
FAILING = "def test_feat_001_broken():\n    assert 1 == 2\n"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    return root


def write_yaml(repo: pathlib.Path, body: str) -> None:
    (repo / verify.PROJECT_YAML).write_text(body, encoding="utf-8")


# --- 기본 명령(pytest) -----------------------------------------------------

def test_default_command_is_the_venv_pytest(repo):
    command, error = verify.resolve_command(repo)
    assert error is None
    assert command == [PY, "-m", "pytest", "-q"]
    assert pathlib.Path(command[0]).name.startswith("python")


def test_green_tests_pass_verification(repo):
    (repo / "tests" / "test_ok.py").write_text(PASSING, encoding="utf-8")

    result = verify.run_verify(repo)

    assert result["ok"] and result["exit_code"] == 0
    assert result["kind"] == "test" and result["timed_out"] is False
    assert "passed" in result["tail"]


def test_failing_tests_fail_verification_with_a_tail(repo):
    (repo / "tests" / "test_bad.py").write_text(FAILING, encoding="utf-8")

    result = verify.run_verify(repo)

    assert result["ok"] is False and result["exit_code"] != 0
    assert "test_feat_001_broken" in result["tail"]


# --- project.yaml ----------------------------------------------------------

def test_string_command_is_split_without_a_shell(repo):
    write_yaml(repo, f"test: {PY} -c print(1)\n")

    result = verify.run_verify(repo)

    assert result["cmd"] == [PY, "-c", "print(1)"]
    assert result["ok"] and result["tail"].strip() == "1"


def test_quoted_string_command_keeps_the_path_intact(repo):
    write_yaml(repo, f'test: \'"{PY}" -c print(2)\'\n')

    result = verify.run_verify(repo)

    assert result["cmd"][0] == PY and result["ok"]


def test_list_command_is_used_verbatim(repo):
    # YAML 큰따옴표 스칼라는 역슬래시를 이스케이프로 먹는다 -- 경로는 작은따옴표로.
    write_yaml(repo, f"test: ['{PY}', '-c', 'raise SystemExit(3)']\n")

    result = verify.run_verify(repo)

    assert result["ok"] is False and result["exit_code"] == 3


def test_commands_mapping_is_accepted(repo):
    write_yaml(repo, f"commands:\n  e2e: {PY} -c print(9)\n")

    result = verify.run_verify(repo, kind="e2e")

    assert result["ok"] and result["tail"].strip() == "9"


def test_top_level_key_wins_over_the_mapping(repo):
    write_yaml(repo, f"test: {PY} -c print(1)\ncommands:\n  test: {PY} -c print(2)\n")
    assert verify.resolve_command(repo)[0][-1] == "print(1)"


def test_unknown_kind_without_a_default_is_reported(repo):
    result = verify.run_verify(repo, kind="e2e")

    assert result["ok"] is False and result["cmd"] == []
    assert "e2e" in result["tail"] and result["exit_code"] == -1


def test_broken_project_yaml_is_a_failure_not_a_silent_default(repo):
    write_yaml(repo, "test: [unclosed\n")

    result = verify.run_verify(repo)

    assert result["ok"] is False and result["cmd"] == []
    assert verify.PROJECT_YAML in result["tail"]


def test_empty_project_yaml_falls_back_to_the_default(repo):
    write_yaml(repo, "\n")
    assert verify.resolve_command(repo)[0] == [PY, "-m", "pytest", "-q"]


# --- 실행 사고 -------------------------------------------------------------

def test_tail_is_capped(repo):
    write_yaml(repo, f"test: ['{PY}', '-c', 'print(\"x\" * 20000)']\n")

    result = verify.run_verify(repo)

    assert result["ok"] and len(result["tail"]) == verify.TAIL


def test_timeout_is_reported_without_raising(repo):
    write_yaml(repo, f"test: ['{PY}', '-c', 'import time; time.sleep(30)']\n")

    result = verify.run_verify(repo, timeout=1)

    assert result["ok"] is False and result["timed_out"] is True
    assert "타임아웃" in result["tail"]


def test_missing_repo_is_reported(tmp_path):
    result = verify.run_verify(tmp_path / "ghost")
    assert result["ok"] is False and "작업 디렉터리가 없다" in result["tail"]


def test_unrunnable_command_is_reported(repo):
    write_yaml(repo, 'test: ["definitely-not-a-real-binary-xyz"]\n')

    result = verify.run_verify(repo)

    assert result["ok"] is False and "실행하지 못했다" in result["tail"]


# --- 스택 감지와 게이트 계약 (autonomy 04 §1, 05 "게이트 계약") ---------------

def test_stack_detection_keys_on_manifests_only(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "tests").mkdir()
    assert verify.detect_stack(repo) is None            # tests/ alone is not a stack
    (repo / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    assert verify.detect_stack(repo) == "rust"
    (repo / "package.json").write_text("{}", encoding="utf-8")
    assert verify.detect_stack(repo) == "rust"           # manifest order wins


@pytest.mark.parametrize("manifest,stack,test_cmd,build_cmd", [
    ("Cargo.toml", "rust", ["cargo", "test"], ["cargo", "build"]),
    ("go.mod", "go", ["go", "test", "./..."], ["go", "build", "./..."]),
    ("pom.xml", "maven", ["mvn", "-q", "test"], ["mvn", "-q", "-DskipTests", "package"]),
])
def test_compiled_stacks_get_build_and_test_defaults(tmp_path, monkeypatch,
                                                     manifest, stack, test_cmd, build_cmd):
    monkeypatch.setattr(verify.shutil, "which", lambda name: None)  # bare names
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / manifest).write_text("", encoding="utf-8")
    gate, error = verify.resolve_gate(repo, "test")
    assert error is None and gate.steps == [test_cmd] and gate.source == f"detected:{stack}"
    gate, error = verify.resolve_gate(repo, "build")
    assert error is None and gate.steps == [build_cmd]
    assert verify.resolve_gate(repo, "e2e")[0] is None    # still must be declared


def test_node_defaults_follow_package_scripts(tmp_path, monkeypatch):
    monkeypatch.setattr(verify.shutil, "which", lambda name: None)
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "package.json").write_text('{"scripts": {"test": "jest"}}', encoding="utf-8")
    assert verify.default_command("test", repo) == ["npm", "test"]
    assert verify.default_command("build", repo) is None   # no build script -> declare it


def test_make_defaults_need_the_target(tmp_path, monkeypatch):
    monkeypatch.setattr(verify.shutil, "which", lambda name: None)
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "Makefile").write_text("test:\n\tpytest\nlint:\n\truff\n", encoding="utf-8")
    assert verify.default_command("test", repo) == ["make", "test"]
    assert verify.default_command("build", repo) is None


def test_python_stack_keeps_the_pytest_default(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert verify.default_command("test", repo) == [PY, "-m", "pytest", "-q"]
    assert verify.default_command("build", repo) is None


def test_declared_command_beats_detection(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "Cargo.toml").write_text("", encoding="utf-8")
    write_yaml(repo, f"test: {PY} -c print(7)\n")
    gate, error = verify.resolve_gate(repo, "test")
    assert error is None and gate.source == verify.PROJECT_YAML
    assert verify.run_verify(repo)["tail"].strip() == "7"


def test_multi_step_gate_runs_in_order_and_stops_at_the_first_failure(repo):
    write_yaml(repo, (f"test:\n  - ['{PY}', '-c', 'print(\"one\")']\n"
                      f"  - ['{PY}', '-c', 'print(\"two\"); raise SystemExit(4)']\n"
                      f"  - ['{PY}', '-c', 'print(\"three\")']\n"))
    result = verify.run_verify(repo)
    assert result["ok"] is False and result["exit_code"] == 4
    assert "one" in result["tail"] and "two" in result["tail"]
    assert "three" not in result["tail"]
    assert len(result["steps"]) == 2 and result["cmd"][0][-1] == 'print("one")'
    assert result["error"] is None                       # it ran; the exit code is the verdict
    # the flat compat API refuses to flatten a multi-step gate
    assert verify.resolve_command(repo)[0] is None


def test_shell_gate_is_an_explicit_opt_in(repo):
    write_yaml(repo, f"test:\n  shell: \"{PY} -c 'print(1)' && {PY} -c 'print(2)'\"\n")
    result = verify.run_verify(repo)
    assert result["ok"] and result["tail"].split() == ["1", "2"]
    assert isinstance(result["cmd"], str) and "&&" in result["cmd"]
    gate, _ = verify.resolve_gate(repo, "test")
    assert gate.display() == gate.shell


def test_parse_spec_shapes():
    gate, err = verify.parse_spec({"steps": [["a", 1], "b c"]}, kind="unit")
    assert err is None and gate.steps == [["a", "1"], ["b", "c"]]
    assert verify.parse_spec({"argv": ["x"]})[0].steps == [["x"]]
    assert verify.parse_spec({"shell": "  "})[0] is None
    assert verify.parse_spec([])[0] is None
    assert verify.parse_spec({"nope": 1})[0] is None
    assert verify.parse_spec(42)[0] is None


def test_run_gate_takes_a_raw_spec_and_names_the_capture(repo, tmp_path):
    out = tmp_path / "gates"
    result = verify.run_gate(repo, [PY, "-c", "print('hi')"], capture_dir=out, name="unit-U1")
    assert result["ok"] and result["kind"] == "unit-U1"
    path = pathlib.Path(result["output_path"])
    assert path.parent == out and path.name.startswith("unit-U1-")
    body = path.read_text(encoding="utf-8")
    assert "hi" in body and "exit=0" in body and "# $" in body


def test_result_carries_duration_source_and_error_kind(repo):
    result = verify.run_verify(repo)
    assert result["source"] == "default" and result["duration"] >= 0.0
    assert result["error"] is None and result["output_path"] is None
    assert verify.run_verify(repo, kind="e2e")["error"] == "config"
    write_yaml(repo, 'test: ["definitely-not-a-real-binary-xyz"]\n')
    assert verify.run_verify(repo)["error"] == "spawn"
    write_yaml(repo, f"test: ['{PY}', '-c', 'import time; time.sleep(30)']\n")
    assert verify.run_verify(repo, timeout=1)["error"] == "timeout"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_timeout_kills_the_whole_process_group(repo):
    """게이트가 띄운 손자까지 죽는다 -- 사고 2의 고아 빌드가 남지 않게."""
    marker = repo / "grandchild.pid"
    child = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(marker)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    (repo / "child.py").write_text(child, encoding="utf-8")
    write_yaml(repo, f"test: ['{PY}', 'child.py']\n")
    result = verify.run_verify(repo, timeout=2)
    assert result["timed_out"] is True
    pid = int(marker.read_text())
    import time as _t
    deadline = _t.monotonic() + 5
    alive = True
    while _t.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
            break
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        _t.sleep(0.1)
    assert not alive


def test_command_string_for_prompts(repo):
    assert verify.command_string(repo, "test").endswith("-m pytest -q")
    assert verify.command_string(None, "test").endswith("-m pytest -q")
    write_yaml(repo, "test:\n  shell: cargo build && cargo test\n")
    assert verify.command_string(repo, "test") == "cargo build && cargo test"
    assert verify.command_string(repo, "e2e") == ""
