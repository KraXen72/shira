"""Fetch FFmpeg on the user's behalf, so the app never needs a terminal.

FFmpeg is not shipped with Shira UI. Downloading it here, at the user's own
request, means this project redistributes nothing -- it just automates what
the user would otherwise do by hand.

Only ffmpeg.exe and ffprobe.exe are kept. shiradl calls ffprobe separately and
ignores --ffmpeg-location when it does (shiradl/dl.py get_audio_codec), so both
must land in the same directory for the runner's PATH injection to work.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from . import paths

#: A pinned build, not the rolling ``ffmpeg-release-essentials.zip`` alias, so
#: the archive can be checked against a known hash. HTTPS alone proves you
#: reached gyan.dev; it does not prove the bytes are the ones reviewed here.
#:
#: To bump: pick the new versioned URL, fetch ``<url>.sha256``, and paste both
#: below. The app fails with a clear message rather than installing an
#: unverified binary if this ever goes stale.
SOURCE_URL = (
	"https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.zip"
)
EXPECTED_SHA256 = "fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9"
FFMPEG_VERSION = "9.0.1"
WANTED = ("ffmpeg.exe", "ffprobe.exe")


def managed_dir() -> Path:
	return paths.cache_root() / "ffmpeg"


def managed_ffmpeg() -> Path | None:
	"""Path to a previously downloaded ffmpeg, if it is still usable."""
	exe = managed_dir() / "ffmpeg.exe"
	probe = managed_dir() / "ffprobe.exe"
	if exe.is_file() and probe.is_file():
		return exe
	return None


def supported() -> bool:
	return os.name == "nt"


class FFmpegInstaller(QThread):
	"""Downloads and unpacks FFmpeg. Emits progress so the UI can show it."""

	progress = pyqtSignal(int, str)      # percent (-1 = indeterminate), message
	done = pyqtSignal(bool, str)         # ok, message-or-path

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self._cancelled = False

	def cancel(self) -> None:
		self._cancelled = True

	def run(self) -> None:
		tmp_zip = None
		try:
			self.progress.emit(-1, "Contacting server…")
			tmp_zip, digest = self._download()
			if self._cancelled:
				self.done.emit(False, "Cancelled.")
				return

			self.progress.emit(-1, "Verifying download…")
			if digest != EXPECTED_SHA256:
				raise RuntimeError(
					"the download did not match its expected checksum, so it "
					"was discarded. Nothing was installed."
				)

			self.progress.emit(-1, "Unpacking…")
			target = self._extract(tmp_zip)

			self.progress.emit(-1, "Checking it works…")
			version = self._verify(target)
			self.done.emit(True, str(target))
			del version
		except Exception as e:
			self.done.emit(False, f"{type(e).__name__}: {e}")
		finally:
			if tmp_zip is not None:
				Path(tmp_zip).unlink(missing_ok=True)

	# -- steps -------------------------------------------------------------

	def _download(self) -> tuple[str, str]:
		"""Stream to a temp file, hashing as we go. Returns (path, sha256)."""
		req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "shira-ui"})
		fd, tmp_path = tempfile.mkstemp(suffix=".zip")
		os.close(fd)
		digest = hashlib.sha256()

		with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as out:
			total = int(resp.headers.get("Content-Length", 0))
			read = 0
			while True:
				if self._cancelled:
					return tmp_path, ""
				chunk = resp.read(256 * 1024)
				if not chunk:
					break
				out.write(chunk)
				digest.update(chunk)
				read += len(chunk)
				if total:
					pct = int(read * 100 / total)
					self.progress.emit(
						pct, f"Downloading FFmpeg… {read // 1_000_000} of "
						     f"{total // 1_000_000} MB"
					)
				else:
					self.progress.emit(-1, f"Downloading FFmpeg… {read // 1_000_000} MB")
		return tmp_path, digest.hexdigest()

	def _extract(self, zip_path: str) -> Path:
		out_dir = managed_dir()
		out_dir.mkdir(parents=True, exist_ok=True)

		with zipfile.ZipFile(zip_path) as zf:
			# Search by basename rather than assuming the archive layout --
			# the top folder is version-stamped and has changed before.
			members = {}
			for info in zf.infolist():
				name = Path(info.filename).name.lower()
				if name in WANTED and name not in members:
					members[name] = info
			missing = set(WANTED) - set(members)
			if missing:
				raise RuntimeError(
					f"the download did not contain {', '.join(sorted(missing))}"
				)
			for name, info in members.items():
				with zf.open(info) as src, open(out_dir / name, "wb") as dst:
					shutil.copyfileobj(src, dst)

		exe = out_dir / "ffmpeg.exe"
		exe.chmod(exe.stat().st_mode | 0o111)
		(out_dir / "ffprobe.exe").chmod((out_dir / "ffprobe.exe").stat().st_mode | 0o111)
		return exe

	def _verify(self, exe: Path) -> str:
		flags = 0
		if os.name == "nt":
			flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
		r = subprocess.run(
			[str(exe), "-version"], capture_output=True, text=True,
			timeout=30, creationflags=flags,
		)
		if r.returncode != 0:
			raise RuntimeError("the downloaded FFmpeg did not run")
		return r.stdout.splitlines()[0] if r.stdout else "ok"
