"""Filesystem locations owned by the app.

The work directory matters more than it looks. shiradl calls
``dl.cleanup()`` -> ``shutil.rmtree(temp_path)`` in a ``finally`` after *every*
track (shiradl/dl.py:261, shiradl/cli.py). Whatever path is handed to
``--temp-path`` is therefore recursively deleted, repeatedly, without
confirmation.

The old GUI exposed that as a free-text Browse field next to the destination
field, so pointing it at Desktop would have destroyed Desktop.

Here the app always appends its own uniquely-named leaf, and the user can
never type the path. The worst possible rmtree target is a directory this
process created seconds earlier containing only its own partial downloads --
the blast radius is structurally zero rather than merely validated.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

APP_DIR_NAME = "shira-ui"
_STALE_SECONDS = 24 * 60 * 60


def _std(loc: QStandardPaths.StandardLocation) -> Path:
	return Path(QStandardPaths.writableLocation(loc))


def default_library() -> Path:
	"""Default destination.

	The old GUI used ``os.path.abspath("YouTube Music")``, which resolves
	against the current working directory -- so where music landed depended on
	where the app happened to be launched from.
	"""
	music = _std(QStandardPaths.StandardLocation.MusicLocation)
	if not str(music):
		music = Path.home() / "Music"
	return music / "Shira"


def cache_root() -> Path:
	base = _std(QStandardPaths.StandardLocation.CacheLocation)
	if not str(base):
		base = Path.home() / ".cache"
	return base / APP_DIR_NAME


def work_root(library: Path | None = None) -> Path:
	"""Parent for per-run work directories.

	When *library* is given, the work root sits beside it. shiradl finishes
	each track with ``shutil.move``, which degrades to a full copy across
	volumes -- so keeping the work dir on the same drive as the library is
	markedly faster for external drives.
	"""
	if library is not None:
		return Path(library) / ".shira-ui-work"
	return cache_root() / "work"


def new_run_dir(library: Path | None = None) -> Path:
	"""Create and return a unique work directory for one run."""
	root = work_root(library)
	leaf = f"run-{os.getpid()}-{int(time.time() * 1000)}"
	path = root / leaf
	path.mkdir(parents=True, exist_ok=True)
	return path


def scratch_dir() -> Path:
	"""Working directory for the child process.

	``--log-level DEBUG`` makes shiradl dump an ``info.json`` into the process
	CWD for every URL (shiradl/dl.py). Pointing the child here keeps that out
	of the user's repo or home directory.
	"""
	path = cache_root() / "scratch"
	path.mkdir(parents=True, exist_ok=True)
	return path


def sweep_stale(library: Path | None = None) -> int:
	"""Delete run directories older than 24h. Returns how many were removed.

	Cancelling kills the child, so shiradl's ``finally`` never runs and its
	work directory is orphaned. A crash does the same.
	"""
	removed = 0
	roots = [work_root(None)]
	if library is not None:
		roots.append(work_root(library))

	cutoff = time.time() - _STALE_SECONDS
	for root in roots:
		if not root.is_dir():
			continue
		for child in root.iterdir():
			# Only ever touch directories this app named.
			if not child.is_dir() or not child.name.startswith("run-"):
				continue
			try:
				if child.stat().st_mtime < cutoff:
					shutil.rmtree(child, ignore_errors=True)
					removed += 1
			except OSError:
				pass
	return removed


def discard(run_dir: Path) -> None:
	"""Remove a run directory, tolerating a child still holding handles."""
	try:
		if run_dir.is_dir() and run_dir.name.startswith("run-"):
			shutil.rmtree(run_dir, ignore_errors=True)
	except OSError:
		pass


def logo_path() -> Path:
	"""Absolute path to logo.svg.

	The old GUI used ``QIcon("logo.svg")``, a cwd-relative path, so the window
	icon silently vanished unless launched from the repo root. When frozen,
	bundled data lives in the PyInstaller extraction dir instead.
	"""
	base = getattr(sys, "_MEIPASS", None)
	if base:
		return Path(base) / "logo.svg"
	return Path(__file__).resolve().parent.parent / "logo.svg"


def default_cookies() -> Path:
	"""Where the cookies file is expected.

	Note the old GUI hardcoded ``~/.shira/cookies.txt`` while shiradl's config
	lives in ``~/.shiradl/`` -- two different directories. This uses the
	directory shiradl actually owns.
	"""
	return Path.home() / ".shiradl" / "cookies.txt"
