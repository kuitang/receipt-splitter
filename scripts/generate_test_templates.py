#!/usr/bin/env python3
"""Generate front-end test templates using Django from virtualenv."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    env = os.environ.copy()
    env.setdefault("SECRET_KEY", "test-secret")
    env.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")

    # Use virtualenv Python if available, otherwise use current interpreter (for CI)
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if venv_python.exists():
        python_executable = str(venv_python)
    else:
        # In CI or non-venv environments, use the current Python interpreter
        python_executable = sys.executable

    command = [python_executable, "manage.py", "generate_test_templates"]
    return subprocess.call(command, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
