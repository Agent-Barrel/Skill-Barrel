"""Product selection and terminal imports must stay independent."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module,blocked", [
    ("step2step", ("step2step.claude", "step2step.codex", "step2step.terminal", "pyte", "ptyprocess", "winpty")),
    ("step2step.terminal", ("step2step.claude", "step2step.codex", "pyte", "ptyprocess", "winpty", "comtypes")),
    ("step2step.terminal.attach", ("step2step.claude", "step2step.codex", "step2step.terminal.attach.session", "step2step.terminal.attach.winconsole", "comtypes")),
    ("step2step.terminal.screen", ("step2step.claude", "step2step.codex")),
    ("step2step.terminal.pty_session", ("step2step.claude", "step2step.codex")),
    ("step2step.claude", ("step2step.codex", "step2step.terminal.attach.session", "step2step.terminal.attach.winconsole", "comtypes")),
    ("step2step.codex", ("step2step.claude", "step2step.terminal", "pyte", "ptyprocess", "winpty", "comtypes")),
])
def test_import_with_other_backends_unavailable(module, blocked):
    code = textwrap.dedent(f"""\
        import importlib
        import importlib.abc
        import sys
        class Blocked(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if any(fullname == p or fullname.startswith(p + '.') for p in {blocked!r}):
                    raise AssertionError('unexpected dependency: ' + fullname)
        sys.meta_path.insert(0, Blocked())
        importlib.import_module({module!r})
    """)
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_shared_modules_have_no_product_imports_including_windows_backends():
    package = REPO / "step2step"
    paths = [package / name for name in ("__init__.py", "contracts.py", "prompts.py",
                                         "paths.py", "refusal.py")]
    paths += list((package / "terminal").rglob("*.py"))
    for path in paths:
        module = ".".join(path.relative_to(REPO).with_suffix("").parts)
        parent = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    base = importlib.util.resolve_name("." * node.level + base, parent)
                imports = [base] + [base + "." + alias.name for alias in node.names]
            else:
                continue
            assert not any(name == p or name.startswith(p + ".") for name in imports
                           for p in ("step2step.claude", "step2step.codex", "step2step.core", "step2step.attach")), path


def test_root_exports_only_shared_contracts_and_prompts():
    import step2step
    from step2step import contracts, prompts
    from step2step import claude, codex

    for name in step2step.__all__:
        owner = prompts if name in ("load_prompts", "parse_prompts") else contracts
        assert getattr(step2step, name) is getattr(owner, name)
    assert not hasattr(step2step, "SessionHandle")
    assert not hasattr(step2step, "run_session")
    assert claude.SessionHandle is not codex.SessionHandle
    assert claude.ModelState is not contracts.ModelState
    assert claude.TurnResult is codex.TurnResult is contracts.TurnResult
    assert claude.SessionControl is codex.SessionControl is contracts.SessionControl


def test_removed_entrypoints_and_product_scripts():
    assert importlib.util.find_spec("step2step.core") is None
    assert importlib.util.find_spec("step2step.attach") is None
    assert importlib.util.find_spec("step2step.__main__") is None
    metadata = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert metadata["project"]["scripts"] == {
        "step2step-claude": "step2step.claude.__main__:main",
        "step2step-codex": "step2step.codex.__main__:main",
    }


@pytest.mark.parametrize("module", ["step2step.claude", "step2step.codex", "step2step.claude.attach.attach_runner"])
def test_product_cli_help(module):
    result = subprocess.run([sys.executable, "-m", module, "--help"], cwd=REPO,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--prompts" in result.stdout


@pytest.mark.parametrize("module", ["step2step.claude", "step2step.codex"])
def test_product_cli_lists_prompts_without_a_session(module, tmp_path):
    prompts = tmp_path / "prompts.md"
    prompts.write_text("alpha\n---\nbeta", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", module, "--list", "--prompts", str(prompts)],
                            cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(REPO)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "alpha" in result.stdout and "beta" in result.stdout
    assert list(tmp_path.iterdir()) == [prompts]
