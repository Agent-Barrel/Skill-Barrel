"""유닛 루프 엔진 -- 세션은 스크립트 대역, git과 게이트는 진짜.

자율 실행 기록의 사고 3건과 03 사다리를 시나리오로 고정한다: 초록 기준선은 게이트
결함, 코드 실패는 되먹임, 같은 지문 반복은 칸 상승, 환경 실패는 설정된 복구 명령,
예산 초과는 blocked, 재개는 done만 건너뛴다, 정지 파일, 거부, 하네스 실패의 세션 교체.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from step2step.contracts import ControlError, TurnOutcome, TurnResult

from barrel.core import gitops, unitloop
from barrel.core.failures import Rung

PY = sys.executable
pytestmark = pytest.mark.skipif(not gitops.git_available(), reason="git이 없다")

CHECK_OK = [PY, "-c", "import sys; sys.exit(0 if open('out.txt').read().strip() == 'ok' else 1)"]


# --- 대역 ---------------------------------------------------------------------

def _result(outcome, response="done", tools=()):
    return TurnResult(outcome=outcome, turn_index=1, response=response, tools=list(tools),
                      pending=None, signal_lines=0, usage_reset_text=None,
                      started_at=0.0, ended_at=0.0)


def write(name, text):
    """턴 대역의 부수효과: 대상 레포에 파일을 쓴다."""
    def _do(repo):
        (repo / name).write_text(text, encoding="utf-8")
    return _do


class FakeSession:
    def __init__(self, unit, rung, script, repo, sid):
        self.unit, self.rung, self.script, self.repo = unit, rung, list(script), repo
        self.session_id = sid
        self.prompts: list[str] = []
        self.interrupts = 0
        self.stopped = False

    def send_prompt(self, text):
        self.prompts.append(text)
        return object()

    def wait_turn(self, pending, **kw):
        assert kw["timeout"] > 0 and kw["progress_probe"] is not None
        if self.script:
            step = self.script.pop(0)
        else:
            step = {"outcome": TurnOutcome.COMPLETED}
        if step.get("raise"):
            raise step["raise"]
        if step.get("do"):
            step["do"](self.repo)
        return _result(step.get("outcome", TurnOutcome.COMPLETED),
                       step.get("response", "done"), step.get("tools", ()))

    def approve_plan(self):
        return True

    def answer_menu_text(self, text):
        self.answered = text

    def interrupt(self):
        self.interrupts += 1
        return True

    def stop(self, force=False):
        self.stopped = True


class Factory:
    """유닛별 세션 스크립트 큐. 세션마다 스크립트 하나(턴 목록)를 소비한다."""

    def __init__(self, repo, scripts):
        self.repo, self.scripts = repo, {k: list(v) for k, v in scripts.items()}
        self.sessions: list[FakeSession] = []
        self.fail_start = 0

    def __call__(self, unit, rung, *, turn_timeout, snapshot_dir, app_dir):
        assert turn_timeout > 0
        if self.fail_start:
            self.fail_start -= 1
            raise RuntimeError("spawn failed")
        queue = self.scripts.get(unit.id, [])
        script = queue.pop(0) if queue else []
        s = FakeSession(unit, rung, script, self.repo, f"sid-{len(self.sessions) + 1}")
        self.sessions.append(s)
        return s


# --- 픽스처 ---------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "target"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("target\n", encoding="utf-8")
    assert gitops.commit(root, ["README.md"], "init")["committed"]
    (root / "orchestration").mkdir()
    return root


def roadmap(repo, units):
    path = repo / "orchestration" / "roadmap.json"
    path.write_text(json.dumps({"units": units}), encoding="utf-8")
    return path


def unit(uid="U1", **over):
    base = {"id": uid, "title": f"unit {uid}", "prompt": f"Make out.txt say ok for {uid}.",
            "gates": {"exists": ["out.txt"], "unit": CHECK_OK}}
    base.update(over)
    return base


def config(repo, **over):
    cfg = {"name": "t", "target_repo": str(repo),
           "ladder": {"models": ["fable", "opus"], "efforts": ["xhigh", "max"]},
           "budget": {"turn_seconds": 30, "unit_turns": 6, "unit_wall_seconds": 600,
                      "run_wall_seconds": 3600, "stall_seconds": 5, "progress_seconds": 5},
           "gates": {"timeout_seconds": 30},
           "preflight": {"tools": ["git"], "min_free_mb": 1},
           "prompt": {"project_name": "Demo", "one_liner": "a demo", "north_star": "docs/MISSION.md",
                      "references": ["src/"], "scope_note": "round 1", "hard_rules": ["Never touch main."]}}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return unitloop.apply_defaults(cfg)


def make_loop(tmp_path, repo, cfg, units, scripts, *, clock=None):
    factory = Factory(repo, scripts)
    log = []
    loop = unitloop.UnitLoop(cfg, unitloop.load_roadmap(roadmap(repo, units)),
                             results_dir=tmp_path / "results", session_factory=factory,
                             log=log.append, sleep=lambda s: None,
                             **({"clock": clock} if clock else {}))
    return loop, factory, log


def state_of(tmp_path):
    return json.loads((tmp_path / "results" / "state.json").read_text(encoding="utf-8"))


# --- 시나리오 -------------------------------------------------------------------

def test_green_baseline_is_a_gate_defect_not_a_completion(tmp_path, repo):
    (repo / "out.txt").write_text("ok", encoding="utf-8")            # already green
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit()], {})
    assert loop.run() == unitloop.EXIT_HALTED
    assert factory.sessions == []                                     # no session, no fake done
    assert state_of(tmp_path)["units"]["U1"]["status"] == "gate_defect"
    assert any("GATE DEFECT" in line for line in log)
    assert loop.notifier.sent and "gate defect" in loop.notifier.sent[0][0]
    assert gitops.log_subjects(repo) == ["init"]                      # nothing committed


def test_code_failure_is_fed_back_then_committed_without_bookkeeping(tmp_path, repo):
    (repo / "notes.txt").write_text("driver bookkeeping", encoding="utf-8")
    cfg = config(repo, git={"exclude": ["notes.txt"], "commit_prefix": "auto/"})
    scripts = {"U1": [[{"do": write("out.txt", "bad")}, {"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, cfg, [unit()], scripts)

    assert loop.run() == unitloop.EXIT_OK

    s = factory.sessions[0]
    assert len(s.prompts) == 2 and s.stopped
    assert "UNIT U1" in s.prompts[0] and "docs/MISSION.md" in s.prompts[0]
    assert "NOT yet green" in s.prompts[1] and '"unit" layer' in s.prompts[1]
    assert gitops.log_subjects(repo)[0] == "auto/U1: unit U1"
    committed = gitops.commit_files(repo)
    assert "out.txt" in committed and "notes.txt" not in committed
    rec = state_of(tmp_path)["units"]["U1"]
    assert rec["status"] == "done" and rec["attempts"][0]["session_id"] == "sid-1"
    assert [t["outcome"] for t in rec["attempts"][0]["turns"]] == ["completed", "completed"]
    failed_gate = next(g for g in rec["attempts"][0]["gates"] if not g["ok"])
    assert failed_gate["fingerprint"] and failed_gate["kind"] == "code"
    assert (tmp_path / "results" / "gates").is_dir()
    assert any("ALL UNITS DONE" in line for line in log)


def test_same_fingerprint_twice_climbs_the_ladder(tmp_path, repo):
    scripts = {"U1": [
        [{"do": write("out.txt", "bad")}, {"do": write("out.txt", "bad")}],   # rung 1: same failure x2
        [{"do": write("out.txt", "ok")}],                                      # rung 2 succeeds
    ]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo, repeat_limit=2), [unit(effort="xhigh")], scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert [s.rung for s in factory.sessions] == [Rung("fable", "xhigh"), Rung("fable", "max")]
    assert len(factory.sessions[0].prompts) == 2
    assert any("same failure 2x" in line for line in log)


def test_environment_failure_runs_the_configured_recovery_once(tmp_path, repo):
    marker = repo / "daemon.up"
    # the gate reports a docker failure until the recovery command creates the marker
    gate = [PY, "-c", (f"import os, sys\n"
                       f"if not os.path.exists({str(marker)!r}):\n"
                       f"    print('Cannot connect to the Docker daemon at unix:///var/run/docker.sock'); sys.exit(1)\n"
                       f"sys.exit(0 if open('out.txt').read().strip() == 'ok' else 1)")]
    recover = [PY, "-c", f"open({str(marker)!r}, 'w').write('up')"]
    cfg = config(repo, gates={"env_recover": [recover]})
    scripts = {"U1": [[{"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, cfg,
                                   [unit(gates={"exists": ["out.txt"], "unit": gate})], scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert marker.exists() and len(factory.sessions[0].prompts) == 1      # no extra turn
    assert any("env_recover" in line for line in log)


def test_environment_failure_without_recovery_halts_and_notifies(tmp_path, repo):
    gate = [PY, "-c", "print('no space left on device'); import sys; sys.exit(1)"]
    scripts = {"U1": [[{"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo),
                                   [unit(gates={"exists": ["out.txt"], "unit": gate})], scripts)
    assert loop.run() == unitloop.EXIT_HALTED
    assert any("environment" in title or "environment" in msg for title, msg in loop.notifier.sent)
    assert state_of(tmp_path)["units"]["U1"]["status"] == "blocked"


def test_unit_turn_budget_blocks_and_on_unit_blocked_decides(tmp_path, repo):
    scripts = {"U1": [[{"do": write("out.txt", "bad")}] * 5],
               "U2": [[{"do": write("out.txt", "ok")}]]}
    units = [unit("U1", budget={"unit_turns": 1}), unit("U2")]
    loop, factory, log = make_loop(tmp_path, repo, config(repo, on_unit_blocked="halt"), units, scripts)
    assert loop.run() == unitloop.EXIT_HALTED
    assert state_of(tmp_path)["units"]["U1"]["status"] == "blocked"
    assert "U2" not in state_of(tmp_path)["units"]

    loop, factory, log = make_loop(tmp_path, repo, config(repo, on_unit_blocked="skip"), units, scripts)
    (tmp_path / "results" / "state.json").unlink()
    loop.state.data["units"] = {}
    assert loop.run() == unitloop.EXIT_HALTED                  # U2 done, but U1 stays blocked
    st = state_of(tmp_path)["units"]
    assert st["U1"]["status"] == "blocked" and st["U2"]["status"] == "done"


def test_resume_skips_done_units_only(tmp_path, repo):
    scripts = {"U2": [[{"do": write("out.txt", "ok")}]]}
    units = [unit("U1"), unit("U2", depends_on=["U1"])]
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "state.json").write_text(json.dumps(
        {"name": "t", "units": {"U1": {"status": "done", "attempts": []}}}), encoding="utf-8")
    loop, factory, log = make_loop(tmp_path, repo, config(repo), units, scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert [s.unit.id for s in factory.sessions] == ["U2"]
    assert any("already done; skipping" in line for line in log)


def test_dependencies_must_be_done(tmp_path, repo):
    units = [unit("U1"), unit("U2", depends_on=["U1"])]
    scripts = {"U1": [[{"do": write("out.txt", "bad")}] * 9]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo, on_unit_blocked="skip",
                                                          budget={"unit_turns": 1}), units, scripts)
    assert loop.run() == unitloop.EXIT_HALTED
    assert state_of(tmp_path)["units"]["U2"]["reason"].startswith("dependencies not done")
    # a unit that exhausts its turn budget is abandoned (ladder rung 5), never U2
    assert [s.unit.id for s in factory.sessions] == ["U1"]


def test_stop_file_halts_gracefully(tmp_path, repo):
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit()], {})
    (repo / unitloop.STOP_FILE).write_text("", encoding="utf-8")
    assert loop.run() == unitloop.EXIT_STOPPED
    assert factory.sessions == []


def test_refusal_without_code_change_jumps_to_the_next_model(tmp_path, repo):
    scripts = {"U1": [
        [{"response": "I can't help with that request.", "do": None}],
        [{"do": write("out.txt", "ok")}],
    ]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit(effort="xhigh")], scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert [s.rung for s in factory.sessions] == [Rung("fable", "xhigh"), Rung("opus", "xhigh")]


def test_harness_failures_replace_the_session_on_the_same_rung(tmp_path, repo):
    scripts = {"U1": [
        [{"outcome": TurnOutcome.SUBMIT_FAILED}, {"outcome": TurnOutcome.SUBMIT_FAILED}],
        [{"outcome": TurnOutcome.NOISY_STAGNATION}],
        [{"do": write("out.txt", "ok")}],
    ]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo, harness_retries=3), [unit()], scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert len(factory.sessions) == 3
    assert {s.rung for s in factory.sessions} == {Rung("fable", "xhigh")}
    assert factory.sessions[1].interrupts == 1
    assert len(factory.sessions[0].prompts) == 2                     # one resend, then replaced


def test_a_session_that_cannot_start_counts_as_harness(tmp_path, repo):
    scripts = {"U1": [[{"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit()], scripts)
    factory.fail_start = 1
    assert loop.run() == unitloop.EXIT_OK
    assert len(factory.sessions) == 1


def test_control_error_in_a_turn_replaces_the_session(tmp_path, repo):
    scripts = {"U1": [[{"raise": ControlError("send_prompt needs an idle session")}],
                      [{"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit()], scripts)
    assert loop.run() == unitloop.EXIT_OK and len(factory.sessions) == 2


def test_run_budget_halts(tmp_path, repo):
    now = {"t": 0.0}
    cfg = config(repo, budget={"run_wall_seconds": 10})
    scripts = {"U1": [[{"do": write("out.txt", "ok")}]]}
    loop, factory, log = make_loop(tmp_path, repo, cfg, [unit()], scripts, clock=lambda: now["t"])
    now["t"] = 11.0
    assert loop.run() == unitloop.EXIT_HALTED
    assert loop.halt_reason == "run budget exceeded" and factory.sessions == []


def test_stale_artifacts_fail_a_measured_gate(tmp_path, repo):
    import os
    import time as _t
    (repo / "perf.json").write_text("{}", encoding="utf-8")
    old = _t.time() - 600                                       # a result from an earlier run
    os.utime(repo / "perf.json", (old, old))
    scripts = {"U1": [[{"do": write("out.txt", "ok")},                     # passes, but perf.json stale
                       {"do": lambda r: ((r / "perf.json").write_text("{}", encoding="utf-8"),
                                         write("out.txt", "ok")(r))}]]}
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit(artifacts=["perf.json"])], scripts)
    assert loop.run() == unitloop.EXIT_OK
    assert len(factory.sessions[0].prompts) == 2
    assert "measured nothing" in factory.sessions[0].prompts[1]


def test_dry_run_starts_no_session(tmp_path, repo):
    loop, factory, log = make_loop(tmp_path, repo, config(repo), [unit()], {})
    assert loop.run(dry_run=True) == unitloop.EXIT_OK
    assert factory.sessions == [] and any("DRY RUN" in line for line in log)
    assert any("baseline gate fails (good)" in line for line in log)


# --- 프롬프트·설정·로드맵 -----------------------------------------------------

def test_unit_prompt_carries_the_contract(repo):
    cfg = config(repo)
    u = unitloop.load_roadmap(roadmap(repo, [unit(references=["docs/backlog/01.md"])]))[0]
    text = unitloop.render_unit_prompt(cfg, u, repo)
    for needle in ("Demo (a demo)", "UNIT U1: unit U1", "docs/MISSION.md", "round 1", "src/",
                   "docs/backlog/01.md", "Never touch main.", "Do NOT commit", "ENV-BLOCKED:",
                   "$ [exists] exists out.txt", "$ [unit]", "progress log"):
        assert needle in text, needle
    cfg_session = config(repo, git={"commit_by": "session", "branch": "test",
                                    "push": {"remote": "origin", "branch": None}, "commit_prefix": ""})
    text2 = unitloop.render_unit_prompt(cfg_session, u, repo)
    assert 'beginning "U1: "' in text2 and "git push origin test" in text2


def test_feedback_prompt_shows_layer_command_and_tail(repo):
    cfg = config(repo)
    u = unitloop.load_roadmap(roadmap(repo, [unit()]))[0]
    text = unitloop.render_feedback_prompt(cfg, u, {"layer": "unit", "cmd": ["cargo", "test"],
                                                    "exit_code": 101, "tail": "thread panicked"}, repo)
    assert '"unit" layer' in text and "$ cargo test" in text and "exit 101" in text
    assert "thread panicked" in text and "ENV-BLOCKED" in text


def test_validate_config_lists_actionable_errors(tmp_path):
    errors = unitloop.validate_config(unitloop.apply_defaults({"name": "x y", "on_unit_blocked": "nope",
                                                                "ladder": {"efforts": ["ultra"]},
                                                                "budget": {"turn_seconds": 0},
                                                                "gates": {"before": ["docker prune"]}}))
    joined = "\n".join(errors)
    for needle in ("name:", "target_repo:", "ladder.models", "ladder.efforts", "budget:",
                   "on_unit_blocked", "gates.before"):
        assert needle in joined, needle
    good = unitloop.apply_defaults({"name": "ok", "target_repo": str(tmp_path),
                                    "ladder": {"models": ["m"]}})
    assert unitloop.validate_config(good) == []


def test_load_config_resolves_relative_target(tmp_path):
    (tmp_path / "target").mkdir()
    p = tmp_path / "run.json"
    p.write_text(json.dumps({"name": "r", "target_repo": "target", "ladder": {"models": ["m"]}}),
                 encoding="utf-8")
    cfg = unitloop.load_config(p)
    assert cfg["target_repo"] == str((tmp_path / "target").resolve())
    assert cfg["budget"] == {} and cfg["git"]["commit_by"] == "driver"


def test_load_roadmap_validation(repo):
    with pytest.raises(ValueError, match="no gates"):
        unitloop.load_roadmap(roadmap(repo, [{"id": "U1", "prompt": "x"}]))
    with pytest.raises(ValueError, match="unknown unit"):
        unitloop.load_roadmap(roadmap(repo, [unit("U1", depends_on=["U9"])]))
    with pytest.raises(ValueError, match="duplicate"):
        unitloop.load_roadmap(roadmap(repo, [unit("U1"), unit("U1")]))
    with pytest.raises(ValueError, match="effort"):
        unitloop.load_roadmap(roadmap(repo, [unit("U1", effort="ultra")]))
    (repo / "orchestration" / "u1.md").write_text("from file", encoding="utf-8")
    units = unitloop.load_roadmap(roadmap(repo, [{"id": "U1", "prompt_file": "u1.md",
                                                  "gates": {"unit": "make test"}}]))
    assert units[0].prompt == "from file" and units[0].layers[0].name == "unit"


def test_notifier_command_receives_the_message(tmp_path):
    out = tmp_path / "notified.txt"
    cmd = [PY, "-c", f"import sys; open({str(out)!r}, 'w').write(sys.argv[-1])"]
    n = unitloop.Notifier({"command": cmd, "webhook": None}, "run-x", lambda m: None)
    assert n.send("halted", "U3 blocked") is True
    assert out.read_text(encoding="utf-8") == "[run-x] halted: U3 blocked"
    quiet = unitloop.Notifier({"command": [PY, "-c", "raise SystemExit(1)"], "webhook": None}, "r",
                              lambda m: None)
    assert quiet.send("a", "b") is True                     # a failing command never raises


def test_run_state_is_atomic_and_tracks_gate_history(tmp_path):
    st = unitloop.RunState(tmp_path / "s" / "state.json", "t")
    a = st.start_attempt("U1", Rung("m", "x"), "sid", None)
    a["gates"].append({"ok": True, "duration": 12.0})
    a["gates"].append({"ok": False, "duration": 99.0})
    st.mark("U1", "done")
    assert st.gate_history("U1") == [12.0]
    reloaded = unitloop.RunState(tmp_path / "s" / "state.json", "t")
    assert reloaded.status("U1") == "done" and not list((tmp_path / "s").glob("*.tmp"))


def test_driver_dry_run_smoke(tmp_path, repo):
    roadmap(repo, [unit()])
    cfg_path = tmp_path / "run.json"
    cfg_path.write_text(json.dumps({"name": "smoke", "target_repo": str(repo),
                                    "ladder": {"models": ["m"]},
                                    "preflight": {"tools": ["git"], "min_free_mb": 1}}), encoding="utf-8")
    driver = pathlib.Path(__file__).resolve().parents[2] / "orchestration" / "drivers" / "unit_loop.py"
    done = subprocess.run([PY, str(driver), "--config", str(cfg_path), "--dry-run",
                           "--results-dir", str(tmp_path / "res"), "--log", str(tmp_path / "d.log")],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "DRY RUN" in done.stdout and (tmp_path / "d.log").exists()
    bad = subprocess.run([PY, str(driver), "--config", str(tmp_path / "missing.json")],
                         capture_output=True, text=True, timeout=60)
    assert bad.returncode == unitloop.EXIT_CONFIG
