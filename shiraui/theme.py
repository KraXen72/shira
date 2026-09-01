"""Colour tokens, palette construction and the QSS template.

Three layers, applied in order:

1. ``QPalette`` -- reaches what QSS cannot: ``QFileDialog``, ``QMessageBox``,
   text selection, and the native ``QCheckBox`` checkmark glyph.
2. QSS built from a ``string.Template`` with one token dict per theme.
3. Icon re-bake, because qtawesome bakes colour into the rendered pixmap.

Token keys use underscores, not hyphens: ``string.Template`` would parse
``$text-primary`` as ``$text`` followed by a literal ``-primary``.
"""

from __future__ import annotations

from string import Template

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

# The accent is a petrol teal. It complements the cool highlight already in
# logo.svg (#d8e1e0, hue ~173) without colliding with the semantic colours --
# green would clash with `success`, amber with `warning`, and a red-orange
# would read as "stop" on a download button.
#
# Contrast is verified in tests/test_theme_contrast.py; every text pair here
# meets WCAG AA against the surface it is used on.

LIGHT: dict[str, str] = {
    "bg": "#F4F5F2",
    "surface": "#FFFFFF",
    "surface_alt": "#EAECE6",
    "border": "#D5D8CF",
    "border_strong": "#B9B2A7",  # taken verbatim from logo.svg
    "text_primary": "#1F2321",
    "text_muted": "#5A6058",
    "text_on_accent": "#FFFFFF",
    "accent": "#0F6E7B",
    "accent_hover": "#0B5B67",
    "accent_pressed": "#084751",
    "accent_subtle": "#E2EFF1",
    "success": "#1B6E3F",
    "warning": "#8A5A00",
    "danger": "#B3261E",
    "danger_subtle": "#FBEAE8",
}

DARK: dict[str, str] = {
    "bg": "#151816",
    "surface": "#1E221F",
    "surface_alt": "#272C28",
    "border": "#333834",
    "border_strong": "#454B46",
    "text_primary": "#E9EDE8",
    "text_muted": "#A6ADA2",
    "text_on_accent": "#0D1112",
    "accent": "#4FB6C4",
    "accent_hover": "#5FC3D0",
    "accent_pressed": "#3FA6B4",
    "accent_subtle": "#10292D",
    "success": "#6FD08A",
    "warning": "#E0B341",
    "danger": "#FF7B72",
    "danger_subtle": "#2C1A19",
}

THEMES = {"light": LIGHT, "dark": DARK}


def build_palette(t: dict[str, str]) -> QPalette:
	"""Map tokens onto a QPalette.

	The Disabled group is set explicitly. Fusion derives disabled colours by
	blending toward mid-grey, which lands unreadably close to the background
	on a dark palette.
	"""
	p = QPalette()
	C = QColor
	role = QPalette.ColorRole
	group = QPalette.ColorGroup

	p.setColor(role.Window, C(t["bg"]))
	p.setColor(role.WindowText, C(t["text_primary"]))
	p.setColor(role.Base, C(t["surface"]))
	p.setColor(role.AlternateBase, C(t["surface_alt"]))
	p.setColor(role.Text, C(t["text_primary"]))
	p.setColor(role.PlaceholderText, C(t["text_muted"]))
	p.setColor(role.Button, C(t["surface"]))
	p.setColor(role.ButtonText, C(t["text_primary"]))
	p.setColor(role.BrightText, C(t["danger"]))
	p.setColor(role.Highlight, C(t["accent"]))
	p.setColor(role.HighlightedText, C(t["text_on_accent"]))
	p.setColor(role.ToolTipBase, C(t["surface"]))
	p.setColor(role.ToolTipText, C(t["text_primary"]))
	p.setColor(role.Link, C(t["accent"]))
	p.setColor(role.LinkVisited, C(t["accent_pressed"]))
	p.setColor(role.Mid, C(t["border"]))
	p.setColor(role.Dark, C(t["border_strong"]))
	p.setColor(role.Shadow, C(t["border_strong"]))

	for r in (role.WindowText, role.Text, role.ButtonText, role.HighlightedText):
		p.setColor(group.Disabled, r, C(t["text_muted"]))
	p.setColor(group.Disabled, role.Base, C(t["surface_alt"]))
	p.setColor(group.Disabled, role.Button, C(t["surface_alt"]))
	p.setColor(group.Disabled, role.Highlight, C(t["border"]))
	return p


# Deliberately NOT styled here:
#
# * QCheckBox::indicator -- touching any sub-control switches off native
#   drawing, making us responsible for every state's image (checked, hover,
#   tristate, disabled). Fusion draws it from Highlight/Text and tracks the
#   palette for free. Styling it is the classic "blank white squares" bug.
# * QFileDialog / QMessageBox -- they take the palette only. Native-feeling
#   dialogs are the right call and QSS-ing them is a losing game.
QSS = Template("""
QWidget { color: $text_primary; font-size: 13px; }

QFrame#HeaderBar {
    background-color: $surface;
    border: none;
    border-bottom: 1px solid $border;
}
QFrame#Card, QFrame#StatusCard {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
}
QFrame#StatusCard[tone="warning"] { border-left: 3px solid $warning; }
QFrame#StatusCard[tone="danger"]  { border-left: 3px solid $danger; }
QFrame#ErrorBanner {
    background-color: $danger_subtle;
    border: 1px solid $danger;
    border-left: 3px solid $danger;
    border-radius: 8px;
}
QFrame#DevBanner {
    background-color: $surface_alt;
    border: 1px solid $warning;
    border-left: 3px solid $warning;
    border-radius: 8px;
}
QFrame#Separator { background-color: $border; border: none; }

QLabel#Wordmark   { font-size: 15px; font-weight: 600; }
QLabel#SectionTitle {
    font-size: 11px; font-weight: 600; color: $text_muted;
    letter-spacing: 0.7px;
}
QLabel#Hint       { font-size: 12px; color: $text_muted; }
QLabel#FieldError { font-size: 12px; color: $danger; }
QLabel#Preview    { font-size: 12px; color: $text_muted; }

QLineEdit, QPlainTextEdit#UrlInput, QComboBox, QSpinBox {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 0 10px;
    min-height: 32px;
    selection-background-color: $accent;
    selection-color: $text_on_accent;
}
QPlainTextEdit#UrlInput { padding: 8px 10px; }
QLineEdit:focus, QPlainTextEdit#UrlInput:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid $accent;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: $surface_alt;
    color: $text_muted;
}
QLineEdit[invalid="true"], QPlainTextEdit#UrlInput[invalid="true"] {
    border-color: $danger;
}
QLineEdit[flash="true"], QPlainTextEdit#UrlInput[flash="true"] {
    border-color: $accent;
}
QLineEdit[readOnly="true"] { background-color: $surface_alt; }

QPushButton {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 0 14px;
    min-height: 30px;
}
QPushButton:hover    { background-color: $surface_alt; border-color: $border_strong; }
QPushButton:pressed  { background-color: $border; }
QPushButton:focus    { border-color: $accent; }
QPushButton:disabled { color: $text_muted; border-color: $border; background-color: $bg; }

QPushButton#PrimaryButton {
    background-color: $accent;
    color: $text_on_accent;
    border: none;
    font-weight: 600;
    min-height: 38px;
    padding: 0 18px;
}
QPushButton#PrimaryButton:hover   { background-color: $accent_hover; }
QPushButton#PrimaryButton:pressed { background-color: $accent_pressed; }
/* A faded accent would still read as clickable, so disabled goes flat. */
QPushButton#PrimaryButton:disabled {
    background-color: $surface_alt;
    color: $text_muted;
}
QPushButton#GhostButton { min-height: 38px; padding: 0 18px; }
QPushButton#LinkButton {
    border: none;
    background: transparent;
    color: $accent;
    padding: 0 4px;
    min-height: 22px;
}
QPushButton#LinkButton:hover { color: $accent_hover; text-decoration: underline; }
QPushButton#LinkButton:disabled { color: $text_muted; background: transparent; }

QToolButton#Disclosure {
    border: none;
    background: transparent;
    font-weight: 600;
    text-align: left;
    padding: 4px 2px;
}
QToolButton#Disclosure:hover { color: $accent; }
QToolButton#IconToggle {
    border: 1px solid $border;
    border-radius: 6px;
    background: transparent;
    min-width: 30px; min-height: 30px;
}
QToolButton#IconToggle:hover { background-color: $surface_alt; border-color: $border_strong; }

QComboBox::drop-down { border: none; width: 26px; }
/* The popup is a top-level window; it inherits nothing useful and must be
   styled on its own. setView(QListView()) is required for ::item to apply. */
QComboBox QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 4px;
    outline: 0;
    selection-background-color: $accent;
    selection-color: $text_on_accent;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 2px 8px; border-radius: 4px; }

QSpinBox::up-button, QSpinBox::down-button {
    width: 18px; border: none; background: transparent;
}

QCheckBox { spacing: 9px; }
QCheckBox:disabled { color: $text_muted; }

QSlider::groove:horizontal {
    height: 4px; background: $border; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0;
    background: $accent; border-radius: 7px;
}
QSlider::handle:horizontal:disabled { background: $border_strong; }

QProgressBar {
    border: none;
    background-color: $surface_alt;
    border-radius: 5px;
    max-height: 10px; min-height: 10px;
}
QProgressBar::chunk { background-color: $accent; border-radius: 5px; }
QProgressBar[state="success"]::chunk   { background-color: $success; }
QProgressBar[state="warning"]::chunk   { background-color: $warning; }
QProgressBar[state="danger"]::chunk    { background-color: $danger; }
QProgressBar[state="cancelled"]::chunk { background-color: $text_muted; }

QTextEdit#Log, QListWidget#Queue {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px;
}
QTextEdit#Log { font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }
QListWidget#Queue::item { padding: 5px 6px; border-radius: 4px; }
QListWidget#Queue::item:selected { background-color: $accent_subtle; color: $text_primary; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

QScrollBar:vertical {
    border: none; background: transparent; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: $border_strong; border-radius: 5px; min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: $text_muted; }
QScrollBar:horizontal {
    border: none; background: transparent; height: 10px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: $border_strong; border-radius: 5px; min-width: 28px;
}
/* Without these the native arrow stubs remain at both ends. */
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QToolTip {
    color: $text_primary;
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 6px 9px;
}

QMenu { background-color: $surface; border: 1px solid $border; border-radius: 6px; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: $accent_subtle; color: $text_primary; }
""")


def repolish(widget) -> None:
	"""Re-evaluate style for a widget whose dynamic properties changed.

	Qt caches the resolved style, so a property-driven selector such as
	``QLineEdit[invalid="true"]`` will not take effect until this runs.
	"""
	widget.style().unpolish(widget)
	widget.style().polish(widget)
	widget.update()


class ThemeController:
	"""Owns the active colour scheme and applies it across the app."""

	def __init__(self, app: QApplication, settings) -> None:
		self.app = app
		self.settings = settings
		self.mode = settings.get_str("ui/theme", "system")
		self.tokens: dict[str, str] = LIGHT
		self._on_change = []

		app.setStyle(QStyleFactory.create("Fusion"))
		hints = app.styleHints()
		if hasattr(hints, "colorSchemeChanged"):
			hints.colorSchemeChanged.connect(self._system_scheme_changed)

	def subscribe(self, fn) -> None:
		self._on_change.append(fn)

	def resolved(self) -> str:
		"""The concrete theme in use: 'light' or 'dark'."""
		if self.mode in ("light", "dark"):
			return self.mode
		scheme = self.app.styleHints().colorScheme()
		return "dark" if scheme == Qt.ColorScheme.Dark else "light"

	def set_mode(self, mode: str) -> None:
		self.mode = mode
		self.settings.set("ui/theme", mode)
		self.apply()

	def toggle(self) -> None:
		"""Left-click behaviour: flip to the opposite of what is showing."""
		self.set_mode("light" if self.resolved() == "dark" else "dark")

	def _system_scheme_changed(self, *_) -> None:
		if self.mode == "system":
			self.apply()

	def apply(self) -> None:
		name = self.resolved()
		self.tokens = THEMES[name]

		hints = self.app.styleHints()
		if hasattr(hints, "setColorScheme"):
			# Keeps native-drawn bits (scrollbar corners, dialogs) in step.
			hints.setColorScheme(
				Qt.ColorScheme.Dark if name == "dark" else Qt.ColorScheme.Light
			)

		self.app.setPalette(build_palette(self.tokens))
		# Re-setting an identical stylesheet string is a no-op, so blank first.
		self.app.setStyleSheet("")
		self.app.setStyleSheet(QSS.substitute(self.tokens))

		for fn in self._on_change:
			fn(self.tokens)

		# setPalette alone does not repaint widgets that already resolved one.
		for w in self.app.allWidgets():
			repolish(w)
