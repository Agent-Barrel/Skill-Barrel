"""다층 게이트 -- 층 파싱, exists 판정, 순차 실행, fail-first, 싼 통과 의심."""
from __future__ import annotations

import sys
import time

import pytest

from barrel.core import gates

PY = sys.executable


def _cmd(code=0, text="hi"):
    return [PY, "-c", f"import sys; print({text!r}); sys.exit({code})"]


def test_parse_layers_orders_and_reads_options():
    layers = gates.parse_layers({
        "unit": "cargo test",
        "exists": ["src/a.rs"],
        "perf": {"spec": ["bash", "perf.sh"], "timeout": 99},
        "integration": {"spec": {"shell": "a && b"}, "every_turn": True},
    }, default_timeout=7)
    assert [l.name for l in layers] == ["exists", "unit", "integration", "perf"]
    by = {l.name: l for l in layers}
    assert by["unit"].timeout == 7 and by["unit"].every_turn is True
    assert by["perf"].timeout == 99 and by["perf"].every_turn is False   # expensive by default
    assert by["integration"].every_turn is True                          # overridden
    assert by["integration"].display() == "a && b"
    assert by["exists"].display() == "exists src/a.rs"
    with pytest.raises(ValueError, match="unknown gate layer"):
        gates.parse_layers({"smoke": "x"})
    assert gates.parse_layers(None) == []


def test_check_exists_paths_and_symbols(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.rs").write_text("pub fn schema_v2() {}", encoding="utf-8")
    ok = gates.check_exists(tmp_path, {"paths": ["src/a.rs"],
                                       "symbols": [{"pattern": r"schema_v2", "in": "src"}]})
    assert ok["ok"] and ok["exit_code"] == 0 and ok["kind"] == "exists"
    bad = gates.check_exists(tmp_path, {"paths": ["src/b.rs"], "symbols": ["nope_symbol"]})
    assert not bad["ok"] and "missing path: src/b.rs" in bad["tail"]
    assert "missing symbol" in bad["tail"]
    assert not gates.check_exists(tmp_path, {})["ok"]


def test_run_layers_stops_at_the_first_failure_and_runs_cleanup(tmp_path):
    marker = tmp_path / "before.txt"
    layers = gates.parse_layers({"build": _cmd(0, "built"), "unit": _cmd(3, "broken"),
                                 "perf": _cmd(0, "never")})
    results = gates.run_layers(tmp_path, layers, name="t",
                               before=[[PY, "-c", f"open({str(marker)!r}, 'w').write('x')"]])
    assert [r["layer"] for r in results] == ["build", "unit"]
    assert results[1]["exit_code"] == 3 and "broken" in results[1]["tail"]
    assert marker.exists() and results[0]["cleanup"][0]["ok"]
    assert not gates.all_passed(results)
    only_final = gates.run_layers(tmp_path, layers, only="final")
    assert [r["layer"] for r in only_final] == ["perf"] and gates.all_passed(only_final)
    every = gates.run_layers(tmp_path, layers, only="every_turn")
    assert [r["layer"] for r in every] == ["build", "unit"]


def test_after_timeout_cleanup_runs_only_on_timeout(tmp_path):
    marker = tmp_path / "after.txt"
    slow = gates.GateLayer("unit", [PY, "-c", "import time; time.sleep(5)"], timeout=1)
    result = gates.run_layer(tmp_path, slow, name="t",
                             after_timeout=[[PY, "-c", f"open({str(marker)!r}, 'w').write('x')"]])
    assert result["timed_out"] and marker.exists()


def test_must_fail_first(tmp_path):
    green = gates.parse_layers({"build": _cmd(0), "unit": _cmd(0)})
    assert gates.must_fail_first(tmp_path, green)["passed"] is True
    red = gates.parse_layers({"build": _cmd(0), "unit": _cmd(1)})
    verdict = gates.must_fail_first(tmp_path, red)
    assert verdict["passed"] is False and [r["layer"] for r in verdict["results"]] == ["build", "unit"]
    skipped = gates.parse_layers({"unit": {"spec": _cmd(0), "must_fail_before": False}})
    assert gates.must_fail_first(tmp_path, skipped) == {"passed": False, "results": [], "skipped": True}


def test_suspicious_and_stale(tmp_path):
    assert gates.suspiciously_cheap(5, history=[100, 120, 90])
    assert not gates.suspiciously_cheap(50, history=[100, 120, 90])
    assert gates.suspiciously_cheap(5, expected=600)
    assert not gates.suspiciously_cheap(5, history=[100])            # one sample is not history
    old = tmp_path / "old.json"
    old.write_text("{}", encoding="utf-8")
    since = time.time() + 100
    assert gates.stale_artifacts(tmp_path, ["old.json", "missing.json"], since) == [
        "old.json (not refreshed)", "missing.json (missing)"]
    assert gates.stale_artifacts(tmp_path, ["old.json"], time.time() - 100) == []
