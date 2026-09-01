"""Optional qtawesome icons with a graceful fallback chain.

qtawesome is not required. Resolution order is:

1. qtawesome, tinted with the current accent/text token
2. ``QStyle.StandardPixmap`` from the active style
3. a null ``QIcon`` -- the button then renders as plain text, which is correct
   rather than broken, because every icon-bearing button also carries a label
   or a tooltip

Icons are cached per (name, colour) and the cache is cleared on theme change,
since qtawesome bakes the colour into the rendered pixmap.
"""

from __future__ import annotations

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QStyle

try:  # noqa: SIM105 - want the flag, not just suppression
	import qtawesome as qta

	HAS_QTA = True
except Exception:  # ImportError, or a Qt-version incompatibility at import
	qta = None
	HAS_QTA = False

_tokens: dict[str, str] = {}
_cache: dict[tuple[str, str], QIcon] = {}


def set_tokens(tokens: dict[str, str]) -> None:
	_tokens.clear()
	_tokens.update(tokens)
	_cache.clear()


def icon(qta_name: str, std: QStyle.StandardPixmap | None = None,
         color: str = "text_primary") -> QIcon:
	key = (qta_name, color)
	if key in _cache:
		return _cache[key]

	result = QIcon()
	if HAS_QTA:
		try:
			result = qta.icon(qta_name, color=_tokens.get(color, "#888888"))
		except Exception:
			result = QIcon()

	if result.isNull() and std is not None:
		app = QApplication.instance()
		if app is not None:
			result = app.style().standardIcon(std)

	_cache[key] = result
	return result


# Unicode fallbacks for the two icon-only controls. These must always render
# something, so they never rely on qtawesome.
GLYPH = {
	"idle": "●",      # ●
	"busy": "⬇",      # ⬇
	"success": "✓",   # ✓
	"warning": "⚠",   # ⚠
	"error": "✕",     # ✕
	"cancelling": "◐",  # ◐
	"moon": "☾",      # ☾
	"sun": "☀",       # ☀
}
