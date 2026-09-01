"""Application bootstrap."""

from __future__ import annotations

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from . import icons, paths
from .mainwindow import MainWindow
from .settings import SettingsStore
from .theme import ThemeController


def _pick_font() -> QFont | None:
	from PyQt6.QtGui import QFontDatabase

	families = set(QFontDatabase.families())
	for name in ("Segoe UI Variable Text", "Segoe UI", "Inter", "Cantarell", "Noto Sans"):
		if name in families:
			return QFont(name, 10)
	return None


def main() -> int:
	app = QApplication(sys.argv)
	app.setApplicationName("Shira UI")
	app.setOrganizationName("KraXen72")

	font = _pick_font()
	if font is not None:
		app.setFont(font)

	settings = SettingsStore()
	theme = ThemeController(app, settings)
	theme.subscribe(icons.set_tokens)
	theme.apply()

	# Cancelling or crashing skips shiradl's own cleanup, so old work
	# directories can accumulate. Only ever touches run-* dirs we created.
	try:
		paths.sweep_stale(None)
	except OSError:
		pass

	window = MainWindow(theme, settings)
	window.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())
