"""실패 분류·지문·반복 추적·사다리·예산 -- 순수 함수들."""
from __future__ import annotations

import pytest

from barrel.core import failures
from barrel.core.failures import (Budget, BudgetClock, FailureKind, Ladder, RepeatTracker,
                                  Rung, classify, fingerprint, fingerprint_result,
                                  normalize_failure)


def _gate(tail="error: boom", exit_code=1, timed_out=False, error=None):
    return {"ok": False, "tail": tail, "exit_code": exit_code, "timed_out": timed_out,
            "error": error}


# --- 분류 ---------------------------------------------------------------------

def test_harness_outcomes_win():
    for outcome in ("eof", "stalled", "noisy_stagnation", "deadline_exceeded", "submit_failed",
                    "awaiting_menu"):
        assert classify(_gate(), turn_outcome=outcome).kind is FailureKind.HARNESS


def test_refusal_needs_a_phrase_and_no_code_change():
    text = "I can't help with bypassing that check."
    assert classify(None, response=text, worktree_changed=False).kind is FailureKind.REFUSAL
    assert classify(_gate(), response=text, worktree_changed=True).kind is FailureKind.CODE
    assert classify(_gate(), response=text, worktree_changed=None).kind is FailureKind.CODE


def test_gate_defects():
    assert classify(_gate(error="config")).kind is FailureKind.GATE_DEFECT
    assert classify(_gate(error="spawn")).kind is FailureKind.GATE_DEFECT
    assert classify(_gate(exit_code=127, tail="bash: run.sh: command not found")).kind \
        is FailureKind.GATE_DEFECT


def test_environment_from_tail_marker_or_signal():
    env = classify(_gate(tail="Cannot connect to the Docker daemon at unix:///var/run/docker.sock"))
    assert env.kind is FailureKind.ENVIRONMENT and env.evidence
    marker = classify(_gate(tail="tests failed"), response="Analysis…\nENV-BLOCKED: docker pull hangs\n")
    assert marker.kind is FailureKind.ENVIRONMENT and "ENV-BLOCKED" in marker.evidence[0]
    sig = classify(_gate(tail="", exit_code=-9))
    assert sig.kind is FailureKind.ENVIRONMENT
    assert classify(_gate(tail="assertion failed: left == right")).kind is FailureKind.CODE
    # a timeout with no environment signature is still a code problem to feed back
    assert classify(_gate(tail="test foo has been running for over 60 seconds",
                          timed_out=True)).kind is FailureKind.CODE


# --- 지문 ---------------------------------------------------------------------

def test_fingerprint_ignores_volatile_values():
    a = ("2026-08-13 04:59:58 error[E0308]: mismatched types\n"
         " --> /Users/x/proj/src/main.rs:42:7\npid 1234 exited\n")
    b = ("2026-08-13 10:28:08 error[E0308]: mismatched types\n"
         " --> C:\\Users\\y\\proj\\src\\main.rs:57:9\npid 9876 exited\n")
    assert normalize_failure(a) == normalize_failure(b)
    assert fingerprint("U1:unit", "exit:1", a) == fingerprint("U1:unit", "exit:1", b)
    assert fingerprint("U1:unit", "exit:1", a) != fingerprint("U1:unit", "timeout", a)
    assert fingerprint("U1:unit", "exit:1", a) != fingerprint("U1:unit", "exit:1",
                                                              "error[E0425]: cannot find value")


def test_fingerprint_result_uses_the_exit_class():
    res = _gate(tail="x", timed_out=True)
    assert failures.exit_class(res) == "timeout"
    assert failures.exit_class(_gate(exit_code=-9)) == "signal"
    assert failures.exit_class(_gate(error="config")) == "config"
    assert failures.exit_class(None) == "none"
    assert fingerprint_result("g", res) == fingerprint("g", "timeout", "x")


def test_error_lines_prefer_error_looking_lines():
    tail = "building\nstep 1 ok\nerror: nope\nstep 2\nFAILED test_x\n"
    assert failures.error_lines(tail) == ["error: nope", "FAILED test_x"]
    assert failures.error_lines("a\nb\nc\n", limit=2) == ["b", "c"]


def test_repeat_tracker():
    t = RepeatTracker(limit=2)
    assert t.record("a") == 1 and not t.exhausted()
    assert t.record("b") == 1
    assert t.record("b") == 2 and t.exhausted()
    t.reset()
    assert t.record("b") == 1 and t.seen["b"] == 3


# --- 사다리 ---------------------------------------------------------------------

def test_ladder_orders_effort_then_model_and_jumps_models_on_refusal():
    ladder = Ladder(["fable", "opus"], ["high", "xhigh", "max"])
    rungs = ladder.rungs(start_effort="xhigh")
    assert rungs == [Rung("fable", "xhigh"), Rung("fable", "max"),
                     Rung("opus", "xhigh"), Rung("opus", "max")]
    assert ladder.next(rungs, rungs[0], "repeat") == Rung("fable", "max")
    assert ladder.next(rungs, rungs[0], "refusal") == Rung("opus", "xhigh")
    assert ladder.next(rungs, rungs[-1], "repeat") is None
    assert ladder.rungs(start_effort="ultra")[0] == Rung("fable", "ultra")
    assert ladder.rungs(start_model="opus")[0].model == "opus"
    assert Ladder(["m"]).rungs() == [Rung("m", None)]
    with pytest.raises(ValueError):
        Ladder([])


# --- 예산 ---------------------------------------------------------------------

def test_budget_defaults_are_finite_and_overrides_validated():
    b = Budget()
    assert b.turn_seconds == 3600 and b.unit_turns == 12
    assert b.merged({"turn_seconds": 10, "ignored": 1}).turn_seconds == 10
    for bad in ({"turn_seconds": 0}, {"unit_wall_seconds": float("inf")},
                {"unit_turns": 2.5}, {"stall_seconds": "180"}):
        with pytest.raises(ValueError):
            b.merged(bad)


def test_budget_clock_layers():
    now = {"t": 100.0}
    clock = BudgetClock(Budget(turn_seconds=50, unit_turns=2, unit_wall_seconds=100,
                               run_wall_seconds=300), clock=lambda: now["t"])
    clock.start_unit()
    assert clock.exceeded(0) is None and clock.turn_budget() == 50
    assert clock.exceeded(2) == "unit_turns"
    now["t"] = 190.0
    assert clock.turn_budget() == 10          # capped by the remaining unit wall
    now["t"] = 201.0
    assert clock.exceeded(0) == "unit"
    now["t"] = 401.0
    assert clock.exceeded(0) == "run" and clock.turn_budget() == 1.0
    assert clock.start_unit({"unit_wall_seconds": 5}).unit_wall_seconds == 5
