"""SessionHandle model/effort surface over a fake Runner.

Layer A here is just "does --effort reach extra_args and the snapshot"; the
closed-loop TUI paths are exercised in test_runner_model.py, where the fake pty
can be driven keystroke by keystroke.
"""
import pathlib

import pytest

from step2step.claude import screen as scr
from step2step.claude import session
from step2step.claude import transcript as tx
from step2step.claude.runner import ModelControlError
from step2step.claude.session import SessionHandle

IDLE = "some output\n╭──╮\n│ ❯│\n╰──╯\nshift+tab to cycle"
WORKING = "out\n✻ Working… (esc to interrupt)\n╭──╮\n│ ❯│\n╰──╯"


class FakePty:
    def __init__(self):
        self.alive = True
        self.writes = []
        self.write_errors = 0

    def isalive(self):
        return self.alive

    def write(self, s):
        self.writes.append(s)


class FakeScreen:
    def __init__(self, text=IDLE):
        self._text = text

    def set(self, text):
        self._text = text

    def text(self):
        return self._text

    def tail(self, n=12):
        rows = [r for r in self._text.splitlines() if r.strip()]
        return "\n".join(rows[-n:])


class FakeRunner:
    mode = "bypass"
    session_id = "fake-sid"
    workdir = pathlib.Path("wd")
    app_dir = pathlib.Path("app")
    claude_exe = "dummy-claude"
    extra_args = ()

    def __init__(self, **kw):
        self.pty = FakePty()
        self.screen = FakeScreen()
        self.events = None
        self.calls = []

    def _prepare(self):
        self.calls.append(("prepare",))

    def _spawn(self):
        self.calls.append(("spawn",))

    def _handle_trust(self):
        self.calls.append(("trust",))

    def _wait_initial_idle(self):
        self.calls.append(("idle",))

    def preflight(self):
        return {"fatal": [], "warnings": []}

    def _pending_transcript_tool(self):
        return None

    def _model_baseline(self):
        return {"stop": 0, "events": 0, "confirms": 0, "effort_confirms": 0}

    def _abort_model_dialog(self):
        self.calls.append(("abort_dialog",))
        return True

    def log(self, message):
        self.calls.append(("log", message))

    def text(self):
        return self.screen.text()

    def idle_for(self):
        return 0.5


@pytest.fixture
def no_transcript(monkeypatch):
    monkeypatch.setattr(tx, "find_transcript", lambda sid: None)


@pytest.fixture
def boot(monkeypatch):
    """start() with the Runner swapped out; returns the ctor kwargs it saw."""
    created = {}

    class BootRunner(FakeRunner):
        def __init__(self, **kw):
            super().__init__()
            created.update(kw)

    monkeypatch.setattr(session, "Runner", BootRunner)
    return created


# --- start(): launch flags ----------------------------------------------------
def test_start_appends_effort_flag(boot, tmp_path, no_transcript):
    h = SessionHandle.start(workdir=tmp_path, model="haiku", effort="high",
                            claude_exe="dummy-claude")
    ea = boot["extra_args"]
    assert ea[ea.index("--model") + 1] == "haiku"
    assert ea[ea.index("--effort") + 1] == "high"
    assert h.effort == "high"


def test_start_without_effort_leaves_args_unchanged(boot, tmp_path, no_transcript):
    """Backward compat: an existing caller's argv must not gain a flag."""
    h = SessionHandle.start(workdir=tmp_path, model="haiku",
                            claude_exe="dummy-claude")
    assert "--effort" not in boot["extra_args"]
    assert h.effort is None


def test_start_rejects_an_unknown_effort(boot, tmp_path, no_transcript):
    with pytest.raises(ValueError):
        SessionHandle.start(workdir=tmp_path, effort="ultra",
                            claude_exe="dummy-claude")


def test_start_effort_ordering_keeps_charter_extractable(boot, tmp_path,
                                                         no_transcript):
    """debug_log.py recovers the charter by splitting on the LAST ' --model ',
    so --effort has to come after --model, not between charter and --model."""
    SessionHandle.start(workdir=tmp_path, system_prompt_append="be brief",
                        model="haiku", effort="low", claude_exe="dummy-claude")
    ea = list(boot["extra_args"])
    assert ea.index("--append-system-prompt") < ea.index("--model") < ea.index("--effort")


# --- snapshot / health --------------------------------------------------------
def test_snapshot_carries_effort(no_transcript):
    snap = SessionHandle(FakeRunner(), model="haiku", effort="low").snapshot()
    assert (snap["model"], snap["effort"]) == ("haiku", "low")


def test_health_shape_unchanged(no_transcript):
    """Regression guard: model/effort belong on the model API, NOT on health().
    The original key set stays; `no_progress_for` (noisy-stagnation reading)
    is the one later addition."""
    got = SessionHandle(FakeRunner(), model="haiku", effort="low").health()
    assert set(got) == {"alive", "state", "idle_for", "mode", "write_errors",
                        "turn_count", "usage_limited", "no_progress_for"}
    assert "model" not in got and "effort" not in got


# --- model_state --------------------------------------------------------------
def test_model_state_falls_back_to_launch_flags(no_transcript):
    st = SessionHandle(FakeRunner(), model="haiku", effort="low").model_state()
    assert (st.model, st.effort, st.scope, st.source) == (
        "haiku", "low", "launch", "launch-flags")


def test_model_state_prefers_the_transcript(monkeypatch, no_transcript):
    monkeypatch.setattr(tx, "last_model_effort",
                        lambda p: {"model": "claude-sonnet-5", "effort": "high",
                                   "records": 3})
    st = SessionHandle(FakeRunner(), model="haiku", effort="low").model_state()
    assert (st.model, st.effort, st.source) == (
        "claude-sonnet-5", "high", "transcript")
    assert st.requested == "haiku"


def test_model_state_uses_the_last_confirmation_when_no_transcript(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    h._last_confirmation = scr.parse_model_confirmation(
        "Set model to Sonnet 5 for this session only with high effort")
    h._model_scope = "session"
    st = h.model_state()
    assert (st.model, st.effort, st.scope, st.source) == (
        "Sonnet 5", "high", "session", "confirmation")


def test_model_state_matches_across_vocabularies(monkeypatch, no_transcript):
    monkeypatch.setattr(tx, "last_model_effort",
                        lambda p: {"model": "claude-sonnet-5", "effort": None,
                                   "records": 1})
    st = SessionHandle(FakeRunner()).model_state()
    assert st.matches("sonnet") and not st.matches("opus")


# --- set_model / set_effort guards --------------------------------------------
def test_noop_change_sends_no_keys(monkeypatch, no_transcript):
    monkeypatch.setattr(tx, "last_model_effort",
                        lambda p: {"model": "claude-haiku-4-5", "effort": None,
                                   "records": 1})
    h = SessionHandle(FakeRunner(), model="haiku")
    h.set_model("haiku")
    assert h._runner.pty.writes == []          # a needless re-read costs real tokens


def test_force_overrides_the_noop_shortcut(monkeypatch, no_transcript):
    monkeypatch.setattr(tx, "last_model_effort",
                        lambda p: {"model": "claude-haiku-4-5", "effort": None,
                                   "records": 1})
    h = SessionHandle(FakeRunner(), model="haiku")
    called = {}
    h._runner.set_model_via_picker = lambda model, **k: (
        called.setdefault("model", model),
        scr.parse_model_confirmation(
            "Set model to Haiku 4.5 for this session only"))[-1]
    h.set_model("haiku", force=True)
    assert called["model"] == "haiku"


def test_bad_strategy_raises(no_transcript):
    with pytest.raises(ValueError):
        SessionHandle(FakeRunner()).set_model("haiku", strategy="magic")


def test_effort_change_without_persist_is_refused(no_transcript):
    """Measured: every mid-session effort path writes the operator's global
    effortLevel, including the picker's session-only commit."""
    h = SessionHandle(FakeRunner(), model="haiku")
    with pytest.raises(ModelControlError) as e:
        h.set_model("sonnet", effort="max")
    assert e.value.stage == "effort-persists-globally"
    assert h._runner.pty.writes == []


def test_set_effort_without_persist_is_refused(no_transcript):
    h = SessionHandle(FakeRunner())
    with pytest.raises(ModelControlError) as e:
        h.set_effort("max", persist=False)
    assert e.value.stage == "effort-persists-globally"
    assert h._runner.pty.writes == []


def test_command_strategy_without_persist_is_refused(no_transcript):
    """`/model <alias>` was measured to always save the global default."""
    h = SessionHandle(FakeRunner(), model="haiku")
    with pytest.raises(ModelControlError) as e:
        h.set_model("sonnet", strategy="command")
    assert e.value.stage == "command-persists-globally"


def test_set_model_refuses_while_working(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    h._runner.screen.set(WORKING)
    with pytest.raises(ModelControlError) as e:
        h.set_model("sonnet")
    assert e.value.stage == "not-idle"
    assert h._runner.pty.writes == []


def test_set_model_refuses_when_reentrant(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    h._model_busy = True
    with pytest.raises(ModelControlError) as e:
        h.set_model("sonnet")
    assert e.value.stage == "reentrant"


def test_set_model_refuses_on_a_dead_session(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    h._runner.pty.alive = False
    with pytest.raises(ModelControlError) as e:
        h.set_model("sonnet")
    assert e.value.stage == "dead"


# --- delegation ---------------------------------------------------------------
def test_set_model_delegates_to_the_picker_and_records_state(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    seen = {}

    def fake_picker(model, *, effort=None, persist=False, accept_cache_reset=True):
        seen.update(model=model, effort=effort, persist=persist)
        return scr.parse_model_confirmation(
            "Set model to Sonnet 5 for this session only")

    h._runner.set_model_via_picker = fake_picker
    st = h.set_model("sonnet")
    assert seen == {"model": "sonnet", "effort": None, "persist": False}
    assert (st.model, st.scope, st.source) == ("Sonnet 5", "session", "confirmation")
    assert h.model == "sonnet"


def test_persist_true_uses_the_command_form_under_auto(no_transcript):
    h = SessionHandle(FakeRunner(), model="haiku")
    seen = {}
    h._runner.set_model_via_command = lambda model, **k: (
        seen.setdefault("model", model),
        scr.parse_model_confirmation(
            "Set model to Sonnet 5 and saved as your default for new sessions"))[-1]
    h.set_model("sonnet", persist=True)
    assert seen["model"] == "sonnet"


def test_persist_true_with_effort_still_uses_the_picker(no_transcript):
    """The command form cannot set effort, so an effort change must go through
    the picker even when persisting."""
    h = SessionHandle(FakeRunner(), model="haiku")
    seen = {}
    h._runner.set_model_via_picker = lambda model, **k: (
        seen.update(k), scr.parse_model_confirmation(
            "Set model to Sonnet 5 and saved as your default for new sessions "
            "with max effort"))[-1]
    st = h.set_model("sonnet", effort="max", persist=True)
    assert seen["effort"] == "max" and seen["persist"] is True
    assert st.effort == "max"


def test_set_effort_uses_the_command_form_never_the_bare_slider(no_transcript):
    h = SessionHandle(FakeRunner())
    seen = {}
    h._runner.set_effort_via_command = lambda effort, **k: (
        seen.setdefault("effort", effort),
        scr.find_effort_confirmations(
            "Set effort level to max (saved as your default for new sessions): x"
        )[-1])[-1]
    st = h.set_effort("max")
    assert seen["effort"] == "max" and st.effort == "max"


def test_available_models_never_presses_a_commit_key(no_transcript):
    h = SessionHandle(FakeRunner())
    rows = scr.parse_model_dialog(
        "  Select model\n    1. Fable  a\n  ❯ 2. Sonnet  b\n"
        "  Enter to set as default · s to use this session only · Esc to cancel"
    ).rows
    h._runner._open_model_dialog = lambda base: type(
        "D", (), {"rows": rows})()
    got = h.available_models()
    assert [r.name for r in got] == ["Fable", "Sonnet"]
    assert "s" not in h._runner.pty.writes


def test_available_models_returns_empty_when_the_dialog_fails(no_transcript):
    h = SessionHandle(FakeRunner())

    def boom(base):
        raise ModelControlError("nope", stage="dialog-open")

    h._runner._open_model_dialog = boom
    assert h.available_models() == []


# --- exports ------------------------------------------------------------------
def test_claude_exports():
    import step2step.claude as claude
    for name in ("ModelState", "ModelRow", "ModelDialog", "ModelConfirmation",
                 "ModelControlError", "EFFORT_LEVELS", "last_model_effort"):
        assert hasattr(claude, name), name
        assert name in claude.__all__
