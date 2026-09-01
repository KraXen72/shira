"""Parse shiradl's output into structured events. Pure Python, no Qt.

shiradl configures logging as
``format="[%(levelname)-8s %(asctime)s] %(message)s", datefmt="%H:%M:%S"``
(shiradl/cli.py) bound to **stderr**. The old GUI only redirected stdout, so
every one of these lines was invisible -- which is why clicking Download with
a bad ffmpeg path appeared to do nothing at all.

Lines that do not match the prefix are continuations: yt-dlp's own
``ERROR: ...`` messages and the tracebacks that ``logging.exception("")``
emits unconditionally on the root logger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

LINE_RE = re.compile(r"^\[(?P<level>[A-Z]+)\s+(?P<time>\d{2}:\d{2}:\d{2})\]\s?(?P<msg>.*)$")

TRACK_RE = re.compile(
	r'^Downloading "(?P<title>.+)" \(track (?P<j>\d+)/(?P<n>\d+) '
	r"from URL (?P<i>\d+)/(?P<m>\d+)\)$"
)
FAILED_RE = re.compile(r'^Failed to download "(?P<title>.+)" \(track (?P<j>\d+)/(?P<n>\d+)')
SAVED_RE = re.compile(r'^Saved to "(?P<path>.+)"$')
DONE_RE = re.compile(r"^Done \((?P<errors>\d+) error\(s\)\)$")
SKIPPED_RE = re.compile(r"^File already exists at final location, skipping$")
FFMPEG_RE = re.compile(r'^FFmpeg not found at "(?P<path>.+)"$')
COOKIES_RE = re.compile(r'^Cookies file not found at "(?P<path>.+)"$')

LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class Kind(Enum):
	PLAIN = "plain"
	TRACK_START = "track_start"
	TRACK_SAVED = "track_saved"
	TRACK_SKIPPED = "track_skipped"
	TRACK_FAILED = "track_failed"
	RUN_DONE = "run_done"
	FATAL = "fatal"
	RAW = "raw"


@dataclass
class LogEvent:
	level: str
	time: str
	text: str
	kind: Kind = Kind.PLAIN
	data: dict = field(default_factory=dict)
	detail: list[str] = field(default_factory=list)

	@property
	def severity(self) -> int:
		return LEVEL_ORDER.get(self.level, 20)


class LogParser:
	"""Feed lines in, get LogEvents out. Continuations fold into the previous."""

	def __init__(self) -> None:
		self.last: LogEvent | None = None

	def feed(self, line: str) -> LogEvent | None:
		line = line.rstrip("\r\n")
		if not line.strip():
			return None

		m = LINE_RE.match(line)
		if not m:
			# yt-dlp's own output, or a traceback body.
			if self.last is not None:
				self.last.detail.append(line)
				return None
			level = "ERROR" if line.startswith("ERROR") else "INFO"
			ev = LogEvent(level, "", line, Kind.RAW)
			self.last = ev
			return ev

		level, time_s, msg = m["level"], m["time"], m["msg"]
		ev = LogEvent(level, time_s, msg)

		if t := TRACK_RE.match(msg):
			ev.kind = Kind.TRACK_START
			ev.data = {
				"title": t["title"],
				"track": int(t["j"]), "tracks": int(t["n"]),
				"url": int(t["i"]), "urls": int(t["m"]),
			}
		elif s := SAVED_RE.match(msg):
			ev.kind = Kind.TRACK_SAVED
			ev.data = {"path": s["path"]}
		elif SKIPPED_RE.match(msg):
			ev.kind = Kind.TRACK_SKIPPED
		elif f := FAILED_RE.match(msg):
			ev.kind = Kind.TRACK_FAILED
			ev.data = {"title": f["title"]}
		elif d := DONE_RE.match(msg):
			ev.kind = Kind.RUN_DONE
			ev.data = {"errors": int(d["errors"])}
		elif ff := FFMPEG_RE.match(msg):
			ev.kind = Kind.FATAL
			ev.data = {
				"reason": "ffmpeg",
				"path": ff["path"],
				"headline": "FFmpeg wasn't found",
				"remedy": (
					"FFmpeg is the helper program Shira uses to finish each file. "
					"Install it, then click Recheck."
				),
			}
		elif ck := COOKIES_RE.match(msg):
			ev.kind = Kind.FATAL
			ev.data = {
				"reason": "cookies",
				"path": ck["path"],
				"headline": "Your cookies file wasn't found",
				"remedy": f"Shira looked for it at {ck['path']}.",
			}
		elif level == "ERROR" and not msg.strip():
			# logging.exception("") -- an empty ERROR heading a traceback.
			ev.kind = Kind.PLAIN
			ev.text = "Technical details"

		self.last = ev
		return ev


@dataclass
class Progress:
	"""Track-level progress. Per-file percentage is not obtainable.

	shiradl sets ``quiet: True`` in its yt-dlp options (shiradl/dl.py), which
	suppresses yt-dlp's progress output entirely. Counting tracks from the log
	is the only honest signal available without modifying upstream.
	"""

	link_index: int = 0
	link_total: int = 0
	track: int = 0
	track_total: int = 0
	title: str = ""
	saved: int = 0
	skipped: int = 0
	failed: int = 0
	done: bool = False
	errors: int | None = None
	fatal: dict | None = None

	@property
	def completed(self) -> int:
		return self.saved + self.skipped + self.failed

	@property
	def indeterminate(self) -> bool:
		"""True before the first track is announced, when there is nothing to count."""
		return self.track_total == 0


class ProgressTracker:
	"""Folds LogEvents into a Progress snapshot."""

	def __init__(self, link_total: int = 1) -> None:
		self.p = Progress(link_total=link_total)

	def start_link(self, index: int) -> None:
		self.p.link_index = index
		self.p.track = 0
		self.p.track_total = 0
		self.p.title = ""
		self.p.done = False

	def apply(self, ev: LogEvent) -> Progress:
		if ev.kind is Kind.TRACK_START:
			self.p.track = ev.data["track"]
			self.p.track_total = ev.data["tracks"]
			self.p.title = ev.data["title"]
		elif ev.kind is Kind.TRACK_SAVED:
			self.p.saved += 1
		elif ev.kind is Kind.TRACK_SKIPPED:
			self.p.skipped += 1
		elif ev.kind is Kind.TRACK_FAILED:
			self.p.failed += 1
		elif ev.kind is Kind.RUN_DONE:
			self.p.done = True
			self.p.errors = ev.data["errors"]
		elif ev.kind is Kind.FATAL:
			self.p.fatal = ev.data
		return self.p
