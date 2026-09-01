"""Runs shiradl as a child process, one QProcess per link.

Replaces the old QThread + contextlib.redirect_stdout approach. That design
could not be cancelled (shira_cli is one blocking call with no interruption
point), mutated the process-global sys.stdout from a worker thread, and
captured only stdout -- while shiradl logs everything to stderr.

One process per link is deliberate: Dl.soundcloud latches True and is never
reset (shiradl/dl.py:85) while every URL in one invocation shares a single Dl,
so a mixed YouTube + SoundCloud batch would corrupt the later tracks.
"""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from .argsbuilder import build_args
from .logparse import Kind, LogParser, ProgressTracker
from .preflight import child_command

_KILL_GRACE_MS = 3000


class State(Enum):
	IDLE = auto()
	RUNNING = auto()
	CANCELLING = auto()


class Outcome(Enum):
	SUCCESS = auto()
	ERRORS = auto()
	CANCELLED = auto()
	FATAL = auto()


class DownloadRunner(QObject):
	log_event = pyqtSignal(object)      # LogEvent
	progress = pyqtSignal(object)       # Progress
	link_started = pyqtSignal(int, str)  # 1-based index, url
	finished = pyqtSignal(object, object)  # Outcome, Progress

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		# Never name this `self.thread` -- that shadows QObject.thread().
		self._proc: QProcess | None = None
		self.state = State.IDLE
		self._spec = None
		self._urls: list[str] = []
		self._index = 0
		self._parser = LogParser()
		self._tracker = ProgressTracker()
		self._fatal: dict | None = None
		self._buf = {0: b"", 1: b""}
		self._path_additions: list[str] = []

	# -- lifecycle ---------------------------------------------------------

	def start(self, spec, path_additions: list[str] | None = None) -> bool:
		if self.state is not State.IDLE:
			return False
		self._spec = spec
		self._urls = list(spec.urls)
		self._index = 0
		self._fatal = None
		self._path_additions = path_additions or []
		self._tracker = ProgressTracker(link_total=len(self._urls))
		self.state = State.RUNNING
		self._run_next()
		return True

	def cancel(self) -> None:
		if self.state is not State.RUNNING or self._proc is None:
			return
		self.state = State.CANCELLING
		# terminate() posts WM_CLOSE on Windows, which a console-less child
		# ignores, so kill() is what actually works. Try the polite path first
		# for POSIX parity, then escalate.
		self._proc.terminate()
		QTimer.singleShot(_KILL_GRACE_MS, self._force_kill)

	def _force_kill(self) -> None:
		if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
			self._proc.kill()

	def _run_next(self) -> None:
		if self._index >= len(self._urls):
			self._emit_finished()
			return

		url = self._urls[self._index]
		self._index += 1
		self._tracker.start_link(self._index)
		self.link_started.emit(self._index, url)
		self._parser = LogParser()
		self._buf = {0: b"", 1: b""}

		proc = QProcess(self)
		proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
		# Keeps `--log-level DEBUG`'s info.json dumps out of the user's folders.
		proc.setWorkingDirectory(str(self._spec.work_dir))

		env = QProcessEnvironment.systemEnvironment()
		# Not optional: a piped child on Windows defaults to the locale
		# codepage, and an accented track title then raises UnicodeEncodeError
		# inside shiradl's logging StreamHandler.
		env.insert("PYTHONIOENCODING", "utf-8")
		env.insert("PYTHONUTF8", "1")
		if self._path_additions:
			sep = ";" if Path("C:/").drive else ":"
			env.insert("PATH", sep.join(self._path_additions) + sep + env.value("PATH", ""))
		proc.setProcessEnvironment(env)

		proc.readyReadStandardOutput.connect(lambda: self._drain(0))
		proc.readyReadStandardError.connect(lambda: self._drain(1))
		proc.finished.connect(self._on_finished)
		proc.errorOccurred.connect(self._on_error)

		self._proc = proc
		program, *prefix = child_command()
		proc.start(program, [*prefix, *build_args(self._spec, url)])

	# -- output ------------------------------------------------------------

	def _drain(self, channel: int) -> None:
		if self._proc is None:
			return
		raw = (
			self._proc.readAllStandardOutput()
			if channel == 0
			else self._proc.readAllStandardError()
		)
		self._buf[channel] += bytes(raw)
		*lines, self._buf[channel] = self._buf[channel].split(b"\n")
		for line in lines:
			self._handle(line.decode("utf-8", errors="replace"))

	def _flush(self) -> None:
		for channel in (0, 1):
			tail = self._buf[channel]
			if tail.strip():
				self._handle(tail.decode("utf-8", errors="replace"))
			self._buf[channel] = b""

	def _handle(self, line: str) -> None:
		ev = self._parser.feed(line)
		if ev is None:
			return
		if ev.kind is Kind.FATAL:
			self._fatal = ev.data
		self._tracker.apply(ev)
		self.log_event.emit(ev)
		self.progress.emit(self._tracker.p)

	# -- completion --------------------------------------------------------

	def _on_error(self, err: QProcess.ProcessError) -> None:
		if err is QProcess.ProcessError.FailedToStart:
			self._fatal = {
				"reason": "spawn",
				"headline": "Shira couldn't be started",
				"remedy": "The Python interpreter running this app could not launch shiradl.",
			}
			self._handle_terminal()

	def _on_finished(self, _code: int, _status) -> None:
		# Qt does not guarantee readyRead fires for the final chunk before
		# finished, so drain explicitly first.
		if self._proc is not None:
			self._drain(0)
			self._drain(1)
			self._flush()
		self._handle_terminal()

	def _handle_terminal(self) -> None:
		if self._proc is not None:
			self._proc.deleteLater()
			self._proc = None

		if self.state is State.CANCELLING:
			self._emit_finished()
			return
		if self._fatal is not None:
			self._emit_finished()
			return
		self._run_next()

	def _emit_finished(self) -> None:
		p = self._tracker.p
		if self.state is State.CANCELLING:
			outcome = Outcome.CANCELLED
		elif self._fatal is not None:
			outcome = Outcome.FATAL
			p.fatal = self._fatal
		elif p.failed > 0 or (p.errors or 0) > 0:
			outcome = Outcome.ERRORS
		else:
			outcome = Outcome.SUCCESS

		self.state = State.IDLE
		self.finished.emit(outcome, p)
