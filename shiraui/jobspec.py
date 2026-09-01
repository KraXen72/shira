"""Typed description of one download run.

Nothing downstream reads widgets: the UI builds a JobSpec, the validator
checks it, and the args builder turns it into argv.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Audio quality presets. --itag is passed straight to yt-dlp's `format` key
# (shiradl/dl.py), so it accepts any format selector, not just numeric itags.
QUALITY_PRESETS: list[tuple[str, str]] = [
	("Standard — AAC, about 128 kbps (recommended)", "140"),
	("Higher — Opus, about 160 kbps", "251"),
	("Best available", "bestaudio"),
]

COVER_FORMATS = [("JPEG — smaller files", "jpg"), ("PNG — larger, lossless", "png")]
COVER_CROPS = [
	("Fit automatically (recommended)", "auto"),
	("Crop to a square", "crop"),
	("Add bars above and below", "pad"),
]


@dataclass
class JobSpec:
	urls: list[str] = field(default_factory=list)
	final_path: Path = Path()
	work_dir: Path = Path()

	itag: str = "140"
	cover_size: int = 1200
	cover_format: str = "jpg"
	cover_quality: int = 94
	cover_img: str = ""
	cover_crop: str = "auto"

	template_folder: str = "{albumartist}/{album}"
	template_file: str = "{track:02d} {title}"
	exclude_tags: str = ""
	truncate: int = 60
	no_truncate: bool = False

	ffmpeg_location: str = "ffmpeg"
	cookies_enabled: bool = False
	cookies_path: str = ""

	save_cover: bool = False
	overwrite: bool = False
	single_folder: bool = False
	use_playlist_name: bool = False
	print_exceptions: bool = False

	debug_logging: bool = False
	# Developer-only; see argsbuilder. Never persisted.
	no_download: bool = False
	# Opt-in escape hatch: defer to ~/.shiradl/config.json instead of the GUI.
	use_config_file: bool = False
	config_path: str = ""
