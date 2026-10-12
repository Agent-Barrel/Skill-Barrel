"""Single source of truth for repo-anchored paths.

Modules used to compute pathlib.Path(__file__).resolve().parent.parent
individually, which silently changes meaning whenever a file moves to a
different depth. Import these instead. Assumes the package sits directly
under the repo root (true for this repo's from-source usage; the project
is not pip-installed).
"""
from __future__ import annotations

import pathlib

# step2step/paths.py -> parents[0] = step2step/ (package) -> parents[1] = repo root
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime"
