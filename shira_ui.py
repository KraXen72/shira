"""Launcher for Shira UI.

The implementation lives in the `shiraui` package. This shim keeps the
documented `python shira_ui.py` command (and any existing shortcut) working,
and is also the PyInstaller entry point.

When frozen there is no interpreter to spawn for downloads -- `sys.executable`
is this .exe -- so the executable re-runs itself with `--shiradl-child` and is
routed straight into shiradl's CLI here, before Qt is ever imported.
"""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def _run_child() -> int:
    from shiradl.cli import cli

    # standalone_mode lets click print its own usage errors and set the exit
    # code, exactly as `python -m shiradl` would.
    cli(sys.argv[2:], prog_name="shiradl")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--shiradl-child":
        raise SystemExit(_run_child())
    from shiraui.app import main

    raise SystemExit(main())
