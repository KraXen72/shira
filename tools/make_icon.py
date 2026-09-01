"""Render logo.svg into the multi-resolution logo.ico used by the .exe build.

PyInstaller needs a Windows .ico; the project only ships an SVG. Run this after
changing logo.svg:

    python tools/make_icon.py

Requires PyQt6 (for QtSvg rendering) and Pillow, both already app dependencies.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
# Windows picks whichever frame fits the context, so ship the full ladder
# rather than one large image scaled down badly at 16px.
SIZES = [256, 128, 64, 48, 32, 16]


def main() -> int:
	svg = ROOT / "logo.svg"
	if not svg.is_file():
		print(f"no logo.svg at {svg}", file=sys.stderr)
		return 1

	app = QApplication([])
	renderer = QSvgRenderer(str(svg))
	if not renderer.isValid():
		print("logo.svg could not be parsed", file=sys.stderr)
		return 1

	frames: list[Image.Image] = []
	for size in SIZES:
		img = QImage(size, size, QImage.Format.Format_ARGB32)
		img.fill(Qt.GlobalColor.transparent)
		painter = QPainter(img)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
		renderer.render(painter)
		painter.end()

		# Round-trip through PNG so Pillow gets correct premultiplied alpha.
		data = QByteArray()
		buf = QBuffer(data)
		buf.open(QBuffer.OpenModeFlag.WriteOnly)
		img.save(buf, "PNG")
		buf.close()
		frames.append(Image.open(io.BytesIO(bytes(data))).convert("RGBA"))

	out = ROOT / "logo.ico"
	frames[0].save(out, format="ICO", sizes=[(s, s) for s in SIZES])
	print(f"wrote {out} ({out.stat().st_size} bytes)")
	del app
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
