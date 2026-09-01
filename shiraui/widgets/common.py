"""Small shared widgets: URL input, path row, status card, log view, overlay."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
	QFrame,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPlainTextEdit,
	QProgressBar,
	QPushButton,
	QSizePolicy,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from ..icons import GLYPH
from ..logparse import Kind, LogEvent
from ..theme import repolish


class UrlInput(QPlainTextEdit):
	"""Multi-line link box. One URL per line."""

	submitted = pyqtSignal()

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.setObjectName("UrlInput")
		self.setPlaceholderText(
			"Paste a YouTube, YouTube Music or SoundCloud link\n"
			"Add more links on their own lines"
		)
		self.setFixedHeight(78)
		self.setTabChangesFocus(True)

	def keyPressEvent(self, e):
		# Ctrl+Enter starts the download; plain Enter adds another line.
		if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
			e.modifiers() & Qt.KeyboardModifier.ControlModifier
		):
			self.submitted.emit()
			return
		super().keyPressEvent(e)

	def set_invalid(self, on: bool) -> None:
		self.setProperty("invalid", "true" if on else "false")
		repolish(self)

	def flash(self) -> None:
		"""Briefly outline the box in the accent colour after a drop."""
		self.setProperty("flash", "true")
		repolish(self)
		QTimer.singleShot(600, lambda: (self.setProperty("flash", "false"), repolish(self)))


class PathRow(QWidget):
	"""Read-only path display with Change / Open buttons."""

	changed = pyqtSignal(str)
	open_requested = pyqtSignal()

	def __init__(self, value: str = "", parent=None) -> None:
		super().__init__(parent)
		self.edit = QLineEdit(value)
		self.edit.setReadOnly(True)
		self.edit.setCursorPosition(0)

		self.change_btn = QPushButton("Change")
		self.change_btn.setFixedWidth(104)
		self.open_btn = QPushButton("Open")
		self.open_btn.setFixedWidth(96)
		self.open_btn.clicked.connect(self.open_requested)

		row = QHBoxLayout(self)
		row.setContentsMargins(0, 0, 0, 0)
		row.setSpacing(8)
		row.addWidget(self.edit, 1)
		row.addWidget(self.change_btn)
		row.addWidget(self.open_btn)

	def text(self) -> str:
		return self.edit.text()

	def set_text(self, v: str) -> None:
		self.edit.setText(v)
		self.edit.setCursorPosition(0)
		self.changed.emit(v)


class StatusCard(QFrame):
	"""Always-visible status: glyph, message, counter, progress, current track."""

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.setObjectName("StatusCard")
		self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

		self.glyph = QLabel(GLYPH["idle"])
		self.glyph.setFixedWidth(18)
		self.message = QLabel("Ready")
		self.message.setStyleSheet("font-weight: 600;")
		self.counter = QLabel("")
		self.counter.setObjectName("Hint")

		top = QHBoxLayout()
		top.setContentsMargins(0, 0, 0, 0)
		top.setSpacing(8)
		top.addWidget(self.glyph)
		top.addWidget(self.message)
		top.addStretch(1)
		top.addWidget(self.counter)

		self.bar = QProgressBar()
		self.bar.setTextVisible(False)
		self.bar.setRange(0, 100)
		self.bar.setValue(0)
		# Per-file percentage is unavailable: shiradl passes quiet=True to
		# yt-dlp, which suppresses its progress output entirely.
		self.bar.setToolTip(
			"Shira reports progress one track at a time; the percentage of an "
			"individual file isn't available."
		)

		self.detail = QLabel("")
		self.detail.setObjectName("Hint")
		self.detail.setVisible(False)

		self.action = QPushButton("")
		self.action.setObjectName("LinkButton")
		self.action.setVisible(False)

		bottom = QHBoxLayout()
		bottom.setContentsMargins(0, 0, 0, 0)
		bottom.addWidget(self.detail)
		# Explicit stretch: relying on the detail label's stretch factor left
		# the action button centred whenever the label was hidden.
		bottom.addStretch(1)
		bottom.addWidget(self.action)

		root = QVBoxLayout(self)
		root.setContentsMargins(16, 14, 16, 14)
		root.setSpacing(8)
		root.addLayout(top)
		root.addWidget(self.bar)
		root.addLayout(bottom)

	def set_tone(self, tone: str) -> None:
		self.setProperty("tone", tone)
		repolish(self)

	def set_bar_state(self, state: str) -> None:
		self.bar.setProperty("state", state)
		repolish(self.bar)

	def set_indeterminate(self, on: bool) -> None:
		if on:
			self.bar.setRange(0, 0)
		else:
			self.bar.setRange(0, 100)

	def show_detail(self, text: str) -> None:
		self.detail.setText(text)
		self.detail.setVisible(bool(text))


class LogView(QWidget):
	"""Log pane that stores structured records so themes can re-render them."""

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.records: list[LogEvent] = []
		self.tokens: dict[str, str] = {}
		self.min_level = 20
		self.show_details = False

		self.view = QTextEdit()
		self.view.setObjectName("Log")
		self.view.setReadOnly(True)
		self.view.setMinimumHeight(150)
		self.view.document().setMaximumBlockCount(5000)
		self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

		root = QVBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.addWidget(self.view)

	def set_tokens(self, tokens: dict[str, str]) -> None:
		self.tokens = tokens
		self.rerender()

	def clear(self) -> None:
		self.records.clear()
		self.view.clear()

	def append(self, ev: LogEvent) -> None:
		self.records.append(ev)
		if ev.severity >= self.min_level:
			self._write(ev)

	def rerender(self) -> None:
		self.view.clear()
		for ev in self.records:
			if ev.severity >= self.min_level:
				self._write(ev)

	def _colour(self, ev: LogEvent) -> str:
		t = self.tokens
		if ev.kind is Kind.TRACK_SAVED:
			return t.get("success", "#1B6E3F")
		return {
			"DEBUG": t.get("text_muted", "#888"),
			"INFO": t.get("text_primary", "#000"),
			"WARNING": t.get("warning", "#8A5A00"),
			"ERROR": t.get("danger", "#B3261E"),
			"CRITICAL": t.get("danger", "#B3261E"),
		}.get(ev.level, t.get("text_primary", "#000"))

	def _write(self, ev: LogEvent) -> None:
		glyph = {
			"WARNING": GLYPH["warning"] + " ",
			"ERROR": GLYPH["error"] + " ",
			"CRITICAL": GLYPH["error"] + " ",
		}.get(ev.level, "")

		bar = self.view.verticalScrollBar()
		at_bottom = bar.value() >= bar.maximum() - 4

		cur = self.view.textCursor()
		cur.movePosition(QTextCursor.MoveOperation.End)

		if ev.time:
			stamp = QTextCharFormat()
			stamp.setForeground(_qcolor(self.tokens.get("text_muted", "#888")))
			cur.insertText(f"{ev.time}  ", stamp)

		body = QTextCharFormat()
		body.setForeground(_qcolor(self._colour(ev)))
		if ev.level in ("ERROR", "CRITICAL"):
			body.setFontWeight(600)
		cur.insertText(f"{glyph}{ev.text}\n", body)

		if ev.detail:
			muted = QTextCharFormat()
			muted.setForeground(_qcolor(self.tokens.get("text_muted", "#888")))
			if self.show_details:
				for line in ev.detail:
					cur.insertText(f"    {line}\n", muted)
			else:
				# Tracebacks arrive unconditionally: logging.exception("") runs
				# on the root logger regardless of --print-exceptions.
				cur.insertText(
					f"    ▸ {len(ev.detail)} more technical lines "
					f"(turn on 'Show full technical error details')\n",
					muted,
				)

		if at_bottom:
			self.view.moveCursor(QTextCursor.MoveOperation.End)


class DropOverlay(QFrame):
	"""Full-window drop target hint."""

	def __init__(self, parent=None) -> None:
		super().__init__(parent)
		self.setObjectName("DropOverlay")
		self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
		self.setVisible(False)

		title = QLabel("Drop your links.txt here")
		title.setAlignment(Qt.AlignmentFlag.AlignCenter)
		title.setStyleSheet("font-size: 15px; font-weight: 600;")
		sub = QLabel("or drop a link from your browser")
		sub.setObjectName("Hint")
		sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

		root = QVBoxLayout(self)
		root.addStretch(1)
		root.addWidget(title)
		root.addWidget(sub)
		root.addStretch(1)

	def restyle(self, tokens: dict[str, str]) -> None:
		self.setStyleSheet(
			f"QFrame#DropOverlay {{"
			f" background-color: {tokens['accent_subtle']};"
			f" border: 2px dashed {tokens['accent']};"
			f" border-radius: 12px; margin: 10px; }}"
		)


def _qcolor(hex_str: str):
	from PyQt6.QtGui import QColor

	return QColor(hex_str)


def elide_path(p: str, limit: int = 64) -> str:
	if len(p) <= limit:
		return p
	tail = Path(p)
	return "…" + str(Path(*tail.parts[-3:])) if len(tail.parts) > 3 else p
