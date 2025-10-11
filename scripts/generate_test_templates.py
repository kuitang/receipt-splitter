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

    # Use virtualenv Python to ensure Django is available
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        print(f"Error: Virtual environment not found at {venv_python}", file=sys.stderr)
        print("Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt", file=sys.stderr)
        return 1

    command = [str(venv_python), "manage.py", "generate_test_templates"]
    return subprocess.call(command, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
