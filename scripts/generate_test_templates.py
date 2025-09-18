#!/usr/bin/env python3
"""Generate front-end test templates without requiring a virtualenv."""

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

    command = [sys.executable, "manage.py", "generate_test_templates"]
    return subprocess.call(command, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
