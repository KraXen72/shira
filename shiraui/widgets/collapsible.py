"""Disclosure section used for both Advanced options and the Activity log."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
	QFrame,
	QHBoxLayout,
	QScrollArea,
	QSizePolicy,
	QToolButton,
	QVBoxLayout,
	QWidget,
)

ANIM_MS = 160


class CollapsibleSection(QWidget):
	toggled = pyqtSignal(bool)

	def __init__(self, title: str, max_height: int = 340, parent=None) -> None:
		super().__init__(parent)
		self._max_height = max_height

		# setArrowType, not a qtawesome chevron: the disclosure indicator is
		# the one control that must render even with no optional deps present.
		self.button = QToolButton()
		self.button.setObjectName("Disclosure")
		self.button.setText(title)
		self.button.setCheckable(True)
		self.button.setChecked(False)
		self.button.setArrowType(Qt.ArrowType.RightArrow)
		self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
		self.button.setCursor(Qt.CursorShape.PointingHandCursor)
		self.button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
		self.button.setAccessibleName(f"{title}, collapsed")
		self.button.toggled.connect(self._on_toggled)

		# The header lives in a fixed-height widget. Adding the QHBoxLayout
		# straight to the root let it absorb spare vertical space, which
		# pushed the separator rule far away from its own header.
		header_bar = QWidget()
		header_bar.setFixedHeight(30)
		header = QHBoxLayout(header_bar)
		header.setContentsMargins(0, 0, 0, 0)
		header.setSpacing(8)
		header.addWidget(self.button, 1)
		self._header = header

		rule = QFrame()
		rule.setObjectName("Separator")
		rule.setFixedHeight(1)

		self.body = QWidget()
		self.body_layout = QVBoxLayout(self.body)
		self.body_layout.setContentsMargins(0, 12, 0, 0)
		self.body_layout.setSpacing(14)

		self.area = QScrollArea()
		self.area.setWidgetResizable(True)
		self.area.setFrameShape(QFrame.Shape.NoFrame)
		self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		self.area.setWidget(self.body)
		self.area.setMaximumHeight(0)
		self.area.setVisible(False)

		root = QVBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.setSpacing(0)
		root.addWidget(header_bar)
		root.addWidget(rule)
		root.addWidget(self.area)
		# Never taller than its contents, so a collapsed section does not
		# leave a band of empty space below itself.
		self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

		self._anim = QPropertyAnimation(self.area, b"maximumHeight", self)
		self._anim.setDuration(ANIM_MS)
		self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
		self._anim.finished.connect(self._on_anim_done)

	def add_header_widget(self, w: QWidget) -> None:
		self._header.addWidget(w)

	def add(self, w: QWidget) -> None:
		self.body_layout.addWidget(w)

	def set_expanded(self, on: bool) -> None:
		self.button.setChecked(on)

	def is_expanded(self) -> bool:
		return self.button.isChecked()

	def content_height(self) -> int:
		return min(self.body.sizeHint().height(), self._max_height)

	def _on_toggled(self, on: bool) -> None:
		self.button.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
		self.button.setAccessibleName(
			f"{self.button.text()}, {'expanded' if on else 'collapsed'}"
		)
		target = self.content_height() if on else 0
		if on:
			# Must be visible before the open animation, or it animates nothing.
			self.area.setVisible(True)
		self._anim.stop()
		self._anim.setStartValue(self.area.maximumHeight())
		self._anim.setEndValue(target)
		self._anim.start()
		self.toggled.emit(on)

	def _on_anim_done(self) -> None:
		if not self.button.isChecked():
			self.area.setVisible(False)
		else:
			# Let it grow later if the content changes (e.g. Custom quality).
			self.area.setMaximumHeight(self._max_height)
