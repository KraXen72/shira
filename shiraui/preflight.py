"""Startup and pre-launch environment checks.

shiradl's own checks log to stderr and then `return` with exit code 0
(shiradl/cli.py). The old GUI captured only stdout, so a missing ffmpeg
produced no message, no error, and no download -- the button simply appeared
dead. These checks run before launching so the UI can say something useful.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PreflightResult:
	ok: bool = True
	headline: str = ""
	remedy: str = ""
	# Prepended to the child's PATH; see the ffprobe note below.
	path_additions: list[str] = field(default_factory=list)
	ffmpeg: str | None = None
	ffprobe: str | None = None


#: argv[1] that makes the frozen executable behave as the shiradl CLI instead
#: of launching the GUI. See child_command().
CHILD_FLAG = "--shiradl-child"


def is_frozen() -> bool:
	return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def child_command() -> list[str]:
	"""Command prefix for spawning shiradl, minus its own arguments.

	Two very different cases:

	* **Running from source** -- spawn the interpreter with ``-m shiradl``.
	  Prefer ``pythonw.exe`` on Windows, because ``python.exe`` flashes a
	  console window on every launch and PyQt6 does not expose
	  ``setCreateProcessArgumentsModifier``, so CREATE_NO_WINDOW is not
	  available. pythonw was verified to deliver stdout and stderr correctly
	  through QProcess pipes.

	* **Frozen (PyInstaller)** -- there is no interpreter to call. Here
	  ``sys.executable`` is the .exe itself, so ``-m shiradl`` would simply
	  relaunch the GUI. Instead the executable re-runs *itself* with
	  CHILD_FLAG, which the entry point detects before any Qt import and
	  routes into ``shiradl.cli``.
	"""
	if is_frozen():
		return [sys.executable, CHILD_FLAG]

	exe = Path(sys.executable)
	if os.name == "nt" and exe.name.lower() == "python.exe":
		wexe = exe.with_name("pythonw.exe")
		if wexe.exists():
			exe = wexe
	return [str(exe), "-u", "-m", "shiradl"]


def check(ffmpeg_location: str = "ffmpeg") -> PreflightResult:
	r = PreflightResult()

	# shiradl is imported by version through importlib.metadata since 1.8.x,
	# and __init__.py no longer defines __version__. Against an uninstalled
	# source tree that raises inside MBSong.__init__ -- outside the try/except
	# in musicbrainz_enrich_tags -- so it surfaces as every track failing.
	try:
		from importlib.metadata import version

		version("shiradl")
	except Exception:
		return PreflightResult(
			ok=False,
			headline="Shira isn't installed properly",
			remedy=(
				"Run  pip install -e .  in the Shira UI folder, then click Recheck."
			),
		)

	ffmpeg = shutil.which(str(ffmpeg_location))
	if not ffmpeg:
		# Fall back to a copy this app downloaded earlier, so a cleared
		# settings file does not orphan it.
		from .ffmpeg_setup import managed_ffmpeg

		managed = managed_ffmpeg()
		if managed is not None:
			ffmpeg = str(managed)
	if not ffmpeg:
		return PreflightResult(
			ok=False,
			headline="FFmpeg wasn't found",
			remedy=(
				"FFmpeg is the helper program Shira uses to finish each file. "
				"Press Get FFmpeg and Shira will download it for you, or use "
				"Locate if you already have ffmpeg.exe somewhere."
			),
		)
	r.ffmpeg = ffmpeg

	# shiradl calls bare "ffprobe" from PATH and ignores --ffmpeg-location
	# (shiradl/dl.py get_audio_codec). So "ffmpeg chosen via Browse, ffprobe
	# not on PATH" passes shiradl's own check and then fails inside the
	# per-track try at fixup -- every track fails, visible only as
	# "Done (N error(s))". Look beside ffmpeg and fix it up for the child.
	ffprobe = shutil.which("ffprobe")
	if not ffprobe:
		sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
		if sibling.exists():
			ffprobe = str(sibling)
			r.path_additions.append(str(sibling.parent))
		else:
			return PreflightResult(
				ok=False,
				headline="FFprobe wasn't found",
				remedy=(
					"FFprobe comes with FFmpeg and Shira needs both. Reinstall "
					"FFmpeg so that ffprobe sits next to ffmpeg, then click Recheck."
				),
			)
	r.ffprobe = ffprobe
	return r
