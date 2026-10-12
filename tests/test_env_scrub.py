"""D3 regression: child_env drops the whole CLAUDE* family and the auth vars,
but preserves a caller-set ANTHROPIC_MODEL."""
from step2step.claude.runner import child_env


def test_scrubs_claude_prefix(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("CLAUDE_CODE_CHILD_SESSION", "1")
    monkeypatch.setenv("CLAUDE_PID", "999")
    monkeypatch.setenv("CLAUDE_EFFORT", "max")
    e = child_env()
    assert not any(k.upper().startswith("CLAUDE") for k in e)


def test_scrubs_auth(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "secret")
    e = child_env()
    assert "ANTHROPIC_API_KEY" not in e
    assert "ANTHROPIC_AUTH_TOKEN" not in e


def test_preserves_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "haiku")
    assert child_env().get("ANTHROPIC_MODEL") == "haiku"


def test_sets_term(monkeypatch):
    assert child_env()["TERM"] == "xterm-256color"
