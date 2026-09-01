"""Main window: assembly, wiring and UI state. No parsing or argv building."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
	QCheckBox,
	QComboBox,
	QFileDialog,
	QFrame,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QListView,
	QMainWindow,
	QMenu,
	QMessageBox,
	QProgressBar,
	QPushButton,
	QSlider,
	QSpinBox,
	QToolButton,
	QVBoxLayout,
	QWidget,
)

from . import ffmpeg_setup, paths, preflight
from .argsbuilder import preview_command
from .icons import GLYPH
from .jobspec import COVER_CROPS, COVER_FORMATS, QUALITY_PRESETS, JobSpec
from .runner import DownloadRunner, Outcome, State
from .validation import ERROR, clean_urls, sample_preview, validate
from .widgets.collapsible import CollapsibleSection
from .widgets.common import DropOverlay, LogView, PathRow, StatusCard, UrlInput

CUSTOM_QUALITY = "__custom__"
DEV_MODE = os.environ.get("SHIRA_UI_DEV") == "1"


def _label(text: str) -> QLabel:
	lab = QLabel(text)
	lab.setObjectName("SectionTitle")
	return lab


def _group(title: str) -> tuple[QWidget, QVBoxLayout]:
	box = QWidget()
	lay = QVBoxLayout(box)
	lay.setContentsMargins(0, 0, 0, 0)
	lay.setSpacing(10)
	lay.addWidget(_label(title))
	return box, lay


def _row(label: str, widget: QWidget, tip: str = "") -> QWidget:
	holder = QWidget()
	lay = QHBoxLayout(holder)
	lay.setContentsMargins(0, 0, 0, 0)
	lay.setSpacing(14)
	lab = QLabel(label)
	lab.setFixedWidth(150)
	lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
	lay.addWidget(lab)
	lay.addWidget(widget, 1)
	if tip:
		lab.setToolTip(tip)
		widget.setToolTip(tip)
	return holder


class MainWindow(QMainWindow):
	def __init__(self, theme, settings) -> None:
		super().__init__()
		self.theme = theme
		self.settings = settings
		self.runner = DownloadRunner(self)
		self._preflight = preflight.PreflightResult()
		self._run_dir: Path | None = None
		self._finished = False
		self._installer = None

		self.setWindowTitle("Shira")
		logo = paths.logo_path()
		if logo.exists():
			self.setWindowIcon(QIcon(str(logo)))
		self.setMinimumSize(680, 520)
		self.resize(760, 560)

		self._build()
		self._wire()
		self._restore()
		self.theme.subscribe(self._on_theme)
		self._on_theme(self.theme.tokens)
		self.run_preflight()
		self._set_idle()

	# ------------------------------------------------------------------ UI

	def _build(self) -> None:
		root = QWidget()
		outer = QVBoxLayout(root)
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		outer.addWidget(self._build_header())

		body = QWidget()
		self.body_layout = QVBoxLayout(body)
		self.body_layout.setContentsMargins(24, 20, 24, 16)
		self.body_layout.setSpacing(20)

		self.body_layout.addWidget(self._build_links())
		self.body_layout.addWidget(self._build_destination())
		self.body_layout.addWidget(self._build_advanced())
		self.banner = self._build_banner()
		self.body_layout.addWidget(self.banner)
		self.status = StatusCard()
		self.body_layout.addWidget(self.status)
		self.body_layout.addWidget(self._build_actions())
		self.body_layout.addWidget(self._build_log())
		self.body_layout.addStretch(1)

		outer.addWidget(body, 1)
		self.setCentralWidget(root)

		self.overlay = DropOverlay(root)
		self.setAcceptDrops(True)

	def _build_header(self) -> QWidget:
		bar = QFrame()
		bar.setObjectName("HeaderBar")
		bar.setFixedHeight(52)
		bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

		mark = QLabel("Shira")
		mark.setObjectName("Wordmark")

		self.theme_btn = QToolButton()
		self.theme_btn.setObjectName("IconToggle")
		self.theme_btn.setToolTip("Switch between light and dark")
		self.theme_btn.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
		menu = QMenu(self.theme_btn)
		for text, mode in (("Follow Windows", "system"), ("Light", "light"), ("Dark", "dark")):
			act = menu.addAction(text)
			act.setCheckable(True)
			act.setData(mode)
			act.triggered.connect(lambda _c, m=mode: self._set_theme_mode(m))
		self.theme_menu = menu
		self.theme_btn.setMenu(menu)
		self.theme_btn.clicked.connect(self.theme.toggle)

		lay = QHBoxLayout(bar)
		lay.setContentsMargins(24, 0, 18, 0)
		lay.addWidget(mark)
		lay.addStretch(1)
		lay.addWidget(self.theme_btn)
		return bar

	def _build_links(self) -> QWidget:
		box, lay = _group("MUSIC LINK")
		lay.setSpacing(6)

		self.url_input = UrlInput()
		self.open_list_btn = QPushButton("Open list…")
		self.open_list_btn.setFixedWidth(150)
		self.open_list_btn.setToolTip("Choose a .txt file with one link per line.")

		row = QHBoxLayout()
		row.setContentsMargins(0, 0, 0, 0)
		row.setSpacing(8)
		row.addWidget(self.url_input, 1)

		side = QVBoxLayout()
		side.setContentsMargins(0, 0, 0, 0)
		side.addWidget(self.open_list_btn)
		side.addStretch(1)
		row.addLayout(side)
		lay.addLayout(row)

		self.url_error = QLabel("")
		self.url_error.setObjectName("FieldError")
		self.url_error.setVisible(False)
		lay.addWidget(self.url_error)

		hint = QLabel("…or drop a links.txt file anywhere on this window.")
		hint.setObjectName("Hint")
		lay.addWidget(hint)
		return box

	def _build_destination(self) -> QWidget:
		box, lay = _group("SAVE MUSIC TO")
		lay.setSpacing(6)
		self.dest = PathRow(str(paths.default_library()))
		self.dest.setToolTip(
			"The folder your finished music goes into. Shira creates artist "
			"and album folders inside it."
		)
		lay.addWidget(self.dest)
		self.dest_error = QLabel("")
		self.dest_error.setObjectName("FieldError")
		self.dest_error.setVisible(False)
		lay.addWidget(self.dest_error)
		return box

	def _build_advanced(self) -> QWidget:
		self.advanced = CollapsibleSection("Advanced options", max_height=420)
		self.reset_btn = QPushButton("Reset to defaults")
		self.reset_btn.setObjectName("LinkButton")
		self.advanced.add_header_widget(self.reset_btn)

		# --- audio
		g, lay = _group("AUDIO")
		self.quality = QComboBox()
		self.quality.setView(QListView())
		for text, value in QUALITY_PRESETS:
			self.quality.addItem(text, value)
		self.quality.addItem("Custom…", CUSTOM_QUALITY)
		lay.addWidget(_row(
			"Audio quality", self.quality,
			"How much detail is kept in the audio. Standard plays everywhere. "
			"Opus sounds slightly better but some phones and car stereos can't "
			"open it. SoundCloud always downloads as MP3 and ignores this.",
		))
		self.itag_custom = QLineEdit()
		self.itag_custom.setPlaceholderText("e.g. 140, 251, bestaudio")
		self.custom_row = _row(
			"Format code", self.itag_custom,
			"An advanced yt-dlp format code. Only change this if you know what it means.",
		)
		self.custom_row.setVisible(False)
		lay.addWidget(self.custom_row)
		self.advanced.add(g)

		# --- artwork
		g, lay = _group("ALBUM ARTWORK")
		self.cover_size = QSpinBox()
		self.cover_size.setRange(0, 16383)
		self.cover_size.setSingleStep(100)
		self.cover_size.setValue(1200)
		self.cover_size.setSuffix(" px")
		lay.addWidget(_row(
			"Artwork size", self.cover_size,
			"Size of the album artwork stored inside each file. 1200 looks "
			"sharp everywhere. Set to 0 for no artwork.",
		))

		self.cover_format = QComboBox()
		self.cover_format.setView(QListView())
		for text, value in COVER_FORMATS:
			self.cover_format.addItem(text, value)
		lay.addWidget(_row(
			"Artwork format", self.cover_format,
			"JPEG is right for album covers. PNG keeps every pixel but roughly "
			"triples the file size.",
		))

		qual_holder = QWidget()
		qh = QHBoxLayout(qual_holder)
		qh.setContentsMargins(0, 0, 0, 0)
		qh.setSpacing(10)
		self.cover_quality = QSlider(Qt.Orientation.Horizontal)
		self.cover_quality.setRange(1, 100)
		self.cover_quality.setValue(94)
		self.cover_quality_lab = QLabel("94")
		self.cover_quality_lab.setFixedWidth(28)
		qh.addWidget(self.cover_quality, 1)
		qh.addWidget(self.cover_quality_lab)
		self.quality_row = _row(
			"Artwork quality", qual_holder,
			"Only used for JPEG artwork. 94 looks identical to the original.",
		)
		lay.addWidget(self.quality_row)

		self.cover_crop = QComboBox()
		self.cover_crop.setView(QListView())
		for text, value in COVER_CROPS:
			self.cover_crop.addItem(text, value)
		lay.addWidget(_row(
			"Artwork shape", self.cover_crop,
			"Video thumbnails are wide but album art is square. 'Fit "
			"automatically' decides whether to trim the sides or add bars.",
		))

		img_holder = QWidget()
		ih = QHBoxLayout(img_holder)
		ih.setContentsMargins(0, 0, 0, 0)
		ih.setSpacing(8)
		self.cover_img = QLineEdit()
		self.cover_img.setPlaceholderText("optional")
		self.cover_img_btn = QPushButton("Browse…")
		self.cover_img_btn.setFixedWidth(96)
		ih.addWidget(self.cover_img, 1)
		ih.addWidget(self.cover_img_btn)
		lay.addWidget(_row(
			"Use my own artwork", img_holder,
			"Optional. One image for everything, or a folder of images named "
			"after each song's video ID.",
		))

		self.save_cover = QCheckBox("Also save the artwork as a separate image file")
		self.save_cover.setToolTip("Writes a Cover.jpg next to each album.")
		lay.addWidget(self.save_cover)
		self.advanced.add(g)

		# --- files
		g, lay = _group("FILES AND FOLDERS")
		self.tpl_folder = QLineEdit("{albumartist}/{album}")
		lay.addWidget(_row(
			"Folder pattern", self.tpl_folder,
			"How Shira names the folders it creates. Words in curly braces are "
			"replaced with the song's details.",
		))
		self.tpl_file = QLineEdit("{track:02d} {title}")
		lay.addWidget(_row(
			"File pattern", self.tpl_file,
			"How Shira names each file. {track:02d} means the track number "
			"with a leading zero, like 05.",
		))
		self.preview = QLabel("")
		self.preview.setObjectName("Preview")
		lay.addWidget(_row("Preview", self.preview))
		self.tpl_error = QLabel("")
		self.tpl_error.setObjectName("FieldError")
		self.tpl_error.setWordWrap(True)
		self.tpl_error.setVisible(False)
		lay.addWidget(self.tpl_error)

		trunc_holder = QWidget()
		th = QHBoxLayout(trunc_holder)
		th.setContentsMargins(0, 0, 0, 0)
		th.setSpacing(10)
		# Values below 4 silently disable truncation in shiradl, and 4-10
		# produce unusable names; the spin box makes both unreachable.
		self.truncate = QSpinBox()
		self.truncate.setRange(15, 200)
		self.truncate.setValue(60)
		self.truncate.setSuffix(" characters")
		self.no_truncate = QCheckBox("Don't shorten")
		th.addWidget(self.truncate, 1)
		th.addWidget(self.no_truncate)
		lay.addWidget(_row(
			"Shorten long names to", trunc_holder,
			"Windows can't open files whose full path is longer than 260 "
			"characters, so long names get shortened.",
		))

		self.exclude_tags = QLineEdit()
		self.exclude_tags.setPlaceholderText("e.g. lyrics,comments")
		lay.addWidget(_row(
			"Tags to leave out", self.exclude_tags,
			"Comma-separated information Shira should not write into your "
			"files. Leave empty to keep everything.",
		))

		self.overwrite = QCheckBox("Replace files that already exist")
		self.overwrite.setToolTip(
			"Off: Shira skips anything already downloaded. On: it downloads "
			"again and overwrites."
		)
		self.single_folder = QCheckBox("Give single tracks their own folder")
		self.use_playlist_name = QCheckBox("Name playlist folders after the playlist")
		for c in (self.overwrite, self.single_folder, self.use_playlist_name):
			lay.addWidget(c)
		self.advanced.add(g)

		# --- troubleshooting
		g, lay = _group("WHEN THINGS GO WRONG")
		self.log_detail = QComboBox()
		self.log_detail.setView(QListView())
		# Filters what is displayed. The child always runs at INFO (or DEBUG)
		# because the progress lines the UI parses are logger.info -- passing
		# WARNING through would delete the progress bar and the summary.
		for text, value in (
			("Normal", 20), ("Warnings and errors only", 30),
			("Errors only", 40), ("Everything (for bug reports)", 10),
		):
			self.log_detail.addItem(text, value)
		lay.addWidget(_row(
			"Log detail", self.log_detail,
			"How much Shira shows in the activity log. Choose 'Everything' if "
			"you're reporting a problem.",
		))

		self.print_exceptions = QCheckBox("Show full technical error details")
		lay.addWidget(self.print_exceptions)

		self.cookies_enabled = QCheckBox("Use my cookies.txt (private or age-restricted tracks)")
		lay.addWidget(self.cookies_enabled)
		ck_holder = QWidget()
		ch = QHBoxLayout(ck_holder)
		ch.setContentsMargins(0, 0, 0, 0)
		ch.setSpacing(8)
		self.cookies_path = QLineEdit(str(paths.default_cookies()))
		self.cookies_btn = QPushButton("Browse…")
		self.cookies_btn.setFixedWidth(96)
		ch.addWidget(self.cookies_path, 1)
		ch.addWidget(self.cookies_btn)
		self.cookies_row = _row("Cookies file", ck_holder)
		self.cookies_row.setEnabled(False)
		lay.addWidget(self.cookies_row)

		ff_holder = QWidget()
		fh = QHBoxLayout(ff_holder)
		fh.setContentsMargins(0, 0, 0, 0)
		fh.setSpacing(8)
		self.ffmpeg = QLineEdit("ffmpeg")
		self.ffmpeg_btn = QPushButton("Locate…")
		self.ffmpeg_btn.setFixedWidth(96)
		self.ffmpeg_state = QLabel("")
		self.ffmpeg_state.setObjectName("Hint")
		fh.addWidget(self.ffmpeg, 1)
		fh.addWidget(self.ffmpeg_btn)
		fh.addWidget(self.ffmpeg_state)
		lay.addWidget(_row(
			"FFmpeg program", ff_holder,
			"The helper program Shira uses to finish each file. Leave as "
			"'ffmpeg' if it was installed normally.",
		))

		self.use_config = QCheckBox("Use my shiradl config file instead of these settings")
		self.use_config.setToolTip(
			"Off (recommended): what you see here is exactly what runs.\n"
			"On: options you turn OFF here may be switched back on by the file, "
			"because the underlying tool has no way to express 'off'."
		)
		lay.addWidget(self.use_config)

		work_holder = QWidget()
		wh = QHBoxLayout(work_holder)
		wh.setContentsMargins(0, 0, 0, 0)
		wh.setSpacing(8)
		self.work_label = QLabel(str(paths.work_root(None)))
		self.work_label.setObjectName("Hint")
		self.work_open = QPushButton("Open folder")
		self.work_open.setObjectName("LinkButton")
		wh.addWidget(self.work_label, 1)
		wh.addWidget(self.work_open)
		lay.addWidget(_row(
			"Temporary files", work_holder,
			"Shira deletes this folder after every track, so the app manages "
			"it for you and it can't be pointed at your own files.",
		))

		self.copy_cmd = QPushButton("Copy the equivalent command")
		self.copy_cmd.setObjectName("LinkButton")
		lay.addWidget(self.copy_cmd)

		if DEV_MODE:
			self.no_download = QCheckBox("TEST MODE — write silent placeholder files")
			lay.addWidget(self.no_download)
		else:
			self.no_download = None
		self.advanced.add(g)
		return self.advanced

	def _build_banner(self) -> QWidget:
		frame = QFrame()
		frame.setObjectName("ErrorBanner")
		frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
		frame.setVisible(False)

		self.banner_title = QLabel("")
		self.banner_title.setStyleSheet("font-weight: 600;")
		self.banner_body = QLabel("")
		self.banner_body.setWordWrap(True)
		# Downloading FFmpeg on request means this project redistributes
		# nothing, and the user never has to open a terminal.
		self.banner_get = QPushButton("Get FFmpeg")
		self.banner_get.setObjectName("PrimaryButton")
		self.banner_get.setFixedWidth(140)
		self.banner_get.setVisible(False)
		self.banner_fix = QPushButton("Locate ffmpeg…")
		self.banner_fix.setFixedWidth(140)
		self.banner_recheck = QPushButton("Recheck")
		self.banner_recheck.setFixedWidth(96)

		self.banner_bar = QProgressBar()
		self.banner_bar.setTextVisible(False)
		self.banner_bar.setVisible(False)

		btns = QHBoxLayout()
		btns.setContentsMargins(0, 0, 0, 0)
		btns.addStretch(1)
		btns.addWidget(self.banner_get)
		btns.addWidget(self.banner_fix)
		btns.addWidget(self.banner_recheck)

		lay = QVBoxLayout(frame)
		lay.setContentsMargins(16, 12, 16, 12)
		lay.setSpacing(6)
		lay.addWidget(self.banner_title)
		lay.addWidget(self.banner_body)
		lay.addWidget(self.banner_bar)
		lay.addLayout(btns)
		return frame

	def _build_actions(self) -> QWidget:
		holder = QWidget()
		lay = QHBoxLayout(holder)
		lay.setContentsMargins(0, 0, 0, 0)
		lay.setSpacing(10)
		lay.addStretch(1)

		self.download_btn = QPushButton("Download")
		self.download_btn.setObjectName("PrimaryButton")
		self.download_btn.setFixedWidth(170)
		self.download_btn.setDefault(True)

		self.cancel_btn = QPushButton("Cancel")
		self.cancel_btn.setObjectName("GhostButton")
		self.cancel_btn.setFixedWidth(130)
		self.cancel_btn.setEnabled(False)

		lay.addWidget(self.download_btn)
		lay.addWidget(self.cancel_btn)
		return holder

	def _build_log(self) -> QWidget:
		self.log_section = CollapsibleSection("Activity log", max_height=260)
		self.copy_log = QPushButton("Copy")
		self.copy_log.setObjectName("LinkButton")
		self.clear_log = QPushButton("Clear")
		self.clear_log.setObjectName("LinkButton")
		self.log_section.add_header_widget(self.copy_log)
		self.log_section.add_header_widget(self.clear_log)
		self.log = LogView()
		self.log_section.add(self.log)
		return self.log_section

	# --------------------------------------------------------------- wiring

	def _wire(self) -> None:
		self.url_input.textChanged.connect(self._on_input_changed)
		self.url_input.submitted.connect(self.start)
		self.open_list_btn.clicked.connect(self.pick_list)
		self.dest.change_btn.clicked.connect(self.pick_destination)
		self.dest.open_requested.connect(lambda: self.open_folder(self.dest.text()))

		self.download_btn.clicked.connect(self.start)
		self.cancel_btn.clicked.connect(self.runner.cancel)

		self.quality.currentIndexChanged.connect(self._on_quality_changed)
		self.cover_quality.valueChanged.connect(
			lambda v: self.cover_quality_lab.setText(str(v))
		)
		self.cover_format.currentIndexChanged.connect(self._on_cover_format)
		self.cover_img_btn.clicked.connect(self.pick_cover)
		self.tpl_folder.textChanged.connect(self._on_templates_changed)
		self.tpl_file.textChanged.connect(self._on_templates_changed)
		self.no_truncate.toggled.connect(lambda on: self.truncate.setEnabled(not on))
		self.cookies_enabled.toggled.connect(self.cookies_row.setEnabled)
		self.cookies_btn.clicked.connect(self.pick_cookies)
		self.ffmpeg_btn.clicked.connect(self.pick_ffmpeg)
		self.reset_btn.clicked.connect(self.reset_defaults)
		self.copy_cmd.clicked.connect(self.copy_command)
		self.work_open.clicked.connect(lambda: self.open_folder(str(paths.work_root(None))))

		self.log_detail.currentIndexChanged.connect(self._on_log_detail)
		self.print_exceptions.toggled.connect(self._on_details_toggled)
		self.copy_log.clicked.connect(self._copy_log)
		self.clear_log.clicked.connect(self.log.clear)

		self.banner_recheck.clicked.connect(self.run_preflight)
		self.banner_fix.clicked.connect(self.pick_ffmpeg)
		self.banner_get.clicked.connect(self.get_ffmpeg)

		self.advanced.toggled.connect(lambda on: self._grow_for(self.advanced, on))
		self.log_section.toggled.connect(lambda on: self._grow_for(self.log_section, on))
		self.runner.log_event.connect(self._on_log_event)
		self.runner.progress.connect(self._on_progress)
		self.runner.link_started.connect(self._on_link_started)
		self.runner.finished.connect(self._on_finished)

	# --------------------------------------------------------------- theme

	def _on_theme(self, tokens: dict[str, str]) -> None:
		self.log.set_tokens(tokens)
		self.overlay.restyle(tokens)
		self.theme_btn.setText(
			GLYPH["sun"] if self.theme.resolved() == "dark" else GLYPH["moon"]
		)
		for act in self.theme_menu.actions():
			act.setChecked(act.data() == self.theme.mode)

	def _set_theme_mode(self, mode: str) -> None:
		self.theme.set_mode(mode)

	# ------------------------------------------------------------ preflight

	def run_preflight(self) -> None:
		self._preflight = preflight.check(self.ffmpeg.text().strip() or "ffmpeg")
		ok = self._preflight.ok
		self.banner.setVisible(not ok)
		if not ok:
			self.banner_title.setText(self._preflight.headline)
			self.banner_body.setText(self._preflight.remedy)
			self.ffmpeg_state.setText("not found")
			self.download_btn.setToolTip(self._preflight.headline)
			# Only offer the download for the case it actually solves, and
			# only where a single-archive install is sensible.
			self.banner_get.setVisible(
				ffmpeg_setup.supported()
				and "FFmpeg" in self._preflight.headline
			)
		else:
			self.ffmpeg_state.setText("found")
			self.download_btn.setToolTip("")
			self.banner_get.setVisible(False)
			if self._preflight.ffmpeg and not self.ffmpeg.text().strip():
				self.ffmpeg.setText(self._preflight.ffmpeg)
		self._refresh_download_enabled()

	def get_ffmpeg(self) -> None:
		if getattr(self, "_installer", None) is not None:
			return
		self.banner_get.setEnabled(False)
		self.banner_fix.setEnabled(False)
		self.banner_recheck.setEnabled(False)
		self.banner_bar.setVisible(True)
		self.banner_bar.setRange(0, 0)

		self._installer = ffmpeg_setup.FFmpegInstaller(self)
		self._installer.progress.connect(self._on_ffmpeg_progress)
		self._installer.done.connect(self._on_ffmpeg_done)
		self._installer.start()

	def _on_ffmpeg_progress(self, pct: int, message: str) -> None:
		if pct < 0:
			self.banner_bar.setRange(0, 0)
		else:
			self.banner_bar.setRange(0, 100)
			self.banner_bar.setValue(pct)
		self.banner_body.setText(message)

	def _on_ffmpeg_done(self, ok: bool, detail: str) -> None:
		self._installer = None
		self.banner_bar.setVisible(False)
		for b in (self.banner_get, self.banner_fix, self.banner_recheck):
			b.setEnabled(True)

		if ok:
			# Point at the copy we just unpacked and persist it, so this is a
			# one-time step even across restarts.
			self.ffmpeg.setText(detail)
			self.settings.set("adv/ffmpeg", detail)
			self.run_preflight()
			if self._preflight.ok:
				self.status.message.setText("FFmpeg installed — ready to download")
		else:
			self.banner_title.setText("Couldn't download FFmpeg")
			self.banner_body.setText(
				f"{detail}\n\nYou can still press Locate if you have ffmpeg.exe "
				f"already, or install it yourself from ffmpeg.org."
			)

	# ------------------------------------------------------------- actions

	def collect(self) -> JobSpec:
		urls, _ = clean_urls(self.url_input.toPlainText())
		itag = self.quality.currentData()
		if itag == CUSTOM_QUALITY:
			itag = self.itag_custom.text().strip() or "140"

		spec = JobSpec(
			urls=urls,
			final_path=Path(self.dest.text()),
			work_dir=self._run_dir or paths.work_root(None),
			itag=itag,
			cover_size=self.cover_size.value(),
			cover_format=self.cover_format.currentData(),
			cover_quality=self.cover_quality.value(),
			cover_img=self.cover_img.text(),
			cover_crop=self.cover_crop.currentData(),
			template_folder=self.tpl_folder.text(),
			template_file=self.tpl_file.text(),
			exclude_tags=self.exclude_tags.text(),
			truncate=self.truncate.value(),
			no_truncate=self.no_truncate.isChecked(),
			ffmpeg_location=self.ffmpeg.text().strip() or "ffmpeg",
			cookies_enabled=self.cookies_enabled.isChecked(),
			cookies_path=self.cookies_path.text(),
			save_cover=self.save_cover.isChecked(),
			overwrite=self.overwrite.isChecked(),
			single_folder=self.single_folder.isChecked(),
			use_playlist_name=self.use_playlist_name.isChecked(),
			print_exceptions=self.print_exceptions.isChecked(),
			debug_logging=self.log_detail.currentData() == 10,
			no_download=bool(self.no_download and self.no_download.isChecked()),
			use_config_file=self.use_config.isChecked(),
			config_path=str(Path.home() / ".shiradl" / "config.json"),
		)
		return spec

	def start(self) -> None:
		if self.runner.state is not State.IDLE or not self._preflight.ok:
			return

		spec = self.collect()
		issues = validate(spec)
		self._show_issues(issues)
		if any(i.severity == ERROR for i in issues):
			return

		dest = Path(spec.final_path)
		try:
			dest.mkdir(parents=True, exist_ok=True)
		except OSError as e:
			self._fatal_banner("That folder can't be used", str(e))
			return

		# A fresh, uniquely named, app-created directory. shiradl rmtree's
		# --temp-path after every track, so it must never be a user path.
		self._run_dir = paths.new_run_dir(dest)
		spec.work_dir = self._run_dir

		self.log.clear()
		self._set_running(len(spec.urls))
		self.runner.start(spec, self._preflight.path_additions)

	def pick_list(self) -> None:
		path, _ = QFileDialog.getOpenFileName(
			self, "Choose a links file", "", "Text files (*.txt);;All files (*)"
		)
		if path:
			self._load_list(path)

	def _load_list(self, path: str) -> None:
		# Read client-side rather than passing --url-txt: that flag applies to
		# every positional argument, so a list and a pasted link could never
		# be mixed in one run.
		try:
			text = Path(path).read_text(encoding="utf-8", errors="replace")
		except OSError as e:
			QMessageBox.warning(self, "Shira", f"Couldn't read that file:\n{e}")
			return
		urls, bad = clean_urls(text)
		if not urls:
			QMessageBox.information(self, "Shira", "That file didn't contain any links.")
			return
		self.url_input.setPlainText("\n".join(urls))
		self.url_input.flash()
		note = f"Loaded {len(urls)} link{'s' if len(urls) != 1 else ''}"
		if bad:
			note += f" ({len(bad)} line{'s' if len(bad) != 1 else ''} skipped)"
		self.status.message.setText(note)

	def pick_destination(self) -> None:
		path = QFileDialog.getExistingDirectory(self, "Choose a folder", self.dest.text())
		if path:
			self.dest.set_text(path)
			self._on_input_changed()

	def pick_cover(self) -> None:
		path, _ = QFileDialog.getOpenFileName(
			self, "Choose an image", "", "Images (*.jpg *.jpeg *.png);;All files (*)"
		)
		if path:
			self.cover_img.setText(path)

	def pick_cookies(self) -> None:
		path, _ = QFileDialog.getOpenFileName(
			self, "Choose cookies.txt", "", "Text files (*.txt);;All files (*)"
		)
		if path:
			self.cookies_path.setText(path)

	def pick_ffmpeg(self) -> None:
		filt = "Programs (*.exe);;All files (*)" if os.name == "nt" else "All files (*)"
		path, _ = QFileDialog.getOpenFileName(self, "Locate ffmpeg", "", filt)
		if path:
			self.ffmpeg.setText(path)
			self.run_preflight()

	def open_folder(self, path: str) -> None:
		p = Path(path)
		if not p.exists():
			QMessageBox.information(
				self, "Shira", f"That folder doesn't exist yet:\n{p}"
			)
			return
		QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

	def copy_command(self) -> None:
		spec = self.collect()
		url = spec.urls[0] if spec.urls else "<link>"
		from PyQt6.QtWidgets import QApplication

		QApplication.clipboard().setText(preview_command(spec, url))
		self.status.message.setText("Command copied to the clipboard")

	def _copy_log(self) -> None:
		from PyQt6.QtWidgets import QApplication

		QApplication.clipboard().setText(self.log.view.toPlainText())
		self.status.message.setText("Log copied to the clipboard")

	def reset_defaults(self) -> None:
		if QMessageBox.question(
			self, "Shira", "Put every advanced option back to its default?"
		) != QMessageBox.StandardButton.Yes:
			return
		self.quality.setCurrentIndex(0)
		self.itag_custom.clear()
		self.cover_size.setValue(1200)
		self.cover_format.setCurrentIndex(0)
		self.cover_quality.setValue(94)
		self.cover_crop.setCurrentIndex(0)
		self.cover_img.clear()
		self.tpl_folder.setText("{albumartist}/{album}")
		self.tpl_file.setText("{track:02d} {title}")
		self.exclude_tags.clear()
		self.truncate.setValue(60)
		self.no_truncate.setChecked(False)
		self.ffmpeg.setText("ffmpeg")
		for c in (self.save_cover, self.overwrite, self.single_folder,
		          self.use_playlist_name, self.print_exceptions,
		          self.cookies_enabled, self.use_config):
			c.setChecked(False)
		self.log_detail.setCurrentIndex(0)
		self.run_preflight()

	# ---------------------------------------------------------- UI reactions

	def _on_input_changed(self) -> None:
		# A finished result stays on screen until the user starts a new task,
		# so a summary is never cleared before it has been read.
		if getattr(self, "_finished", False) and self.runner.state is State.IDLE:
			self._finished = False
			self._set_idle()

		urls, bad = clean_urls(self.url_input.toPlainText())
		self.url_input.set_invalid(bool(bad) and not urls)
		if bad:
			self.url_error.setText(
				f"{len(bad)} line{'s' if len(bad) != 1 else ''} "
				f"{'are' if len(bad) != 1 else 'is'} not a web address and will be ignored."
			)
			self.url_error.setVisible(True)
		else:
			self.url_error.setVisible(False)
		self._refresh_download_enabled()

	def _on_quality_changed(self) -> None:
		is_custom = self.quality.currentData() == CUSTOM_QUALITY
		self.custom_row.setVisible(is_custom)
		if self.advanced.is_expanded():
			self.advanced.area.setMaximumHeight(self.advanced.content_height())

	def _on_cover_format(self) -> None:
		# cover-quality is JPEG-only in shiradl.
		self.quality_row.setEnabled(self.cover_format.currentData() == "jpg")

	def _on_templates_changed(self) -> None:
		self.preview.setText(sample_preview(self.tpl_folder.text(), self.tpl_file.text()))

	def _on_log_detail(self) -> None:
		self.log.min_level = self.log_detail.currentData()
		self.log.rerender()

	def _on_details_toggled(self, on: bool) -> None:
		self.log.show_details = on
		self.log.rerender()

	def _grow_for(self, section, opening: bool) -> None:
		"""Grow or shrink the window by a bounded delta. Width never changes."""
		if self.isMaximized() or self.isFullScreen():
			return
		delta = section.content_height() + 12
		avail = self.screen().availableGeometry().height() - 60
		new_h = self.height() + (delta if opening else -delta)
		self.resize(self.width(), max(self.minimumHeight(), min(new_h, avail)))

	def _show_issues(self, issues) -> None:
		url_msgs = [i.message for i in issues if i.field == "urls"]
		dest_msgs = [i.message for i in issues if i.field == "final_path"]
		tpl_msgs = [
			i.message for i in issues
			if i.field in ("template_folder", "template_file")
		]
		other = [
			i for i in issues
			if i.field not in ("urls", "final_path", "template_folder", "template_file")
		]

		self.url_error.setText("\n".join(url_msgs))
		self.url_error.setVisible(bool(url_msgs))
		self.dest_error.setText("\n".join(dest_msgs))
		self.dest_error.setVisible(bool(dest_msgs))
		self.tpl_error.setText("\n".join(tpl_msgs))
		self.tpl_error.setVisible(bool(tpl_msgs))

		if tpl_msgs and any(
			i.severity == ERROR for i in issues
			if i.field in ("template_folder", "template_file")
		):
			self.advanced.set_expanded(True)

		blocking = [i for i in other if i.severity == ERROR]
		if blocking:
			self._fatal_banner("Check your settings", blocking[0].message)
		elif self._preflight.ok:
			self.banner.setVisible(False)

	def _fatal_banner(self, title: str, body: str) -> None:
		self.banner_title.setText(title)
		self.banner_body.setText(body)
		self.banner.setVisible(True)

	def _refresh_download_enabled(self) -> None:
		urls, _ = clean_urls(self.url_input.toPlainText())
		self.download_btn.setEnabled(
			bool(urls) and self._preflight.ok and self.runner.state is State.IDLE
		)

	# ------------------------------------------------------------- run state

	def _set_idle(self) -> None:
		self.status.glyph.setText(GLYPH["idle"])
		self.status.message.setText("Ready")
		self.status.counter.setText("")
		self.status.set_tone("")
		self.status.set_bar_state("")
		self.status.set_indeterminate(False)
		self.status.bar.setValue(0)
		self.status.show_detail("")
		self.status.action.setVisible(False)
		self.cancel_btn.setEnabled(False)
		self._set_inputs_enabled(True)
		self._refresh_download_enabled()

	def _set_running(self, link_total: int) -> None:
		self.status.glyph.setText(GLYPH["busy"])
		self.status.message.setText("Looking up links…")
		self.status.counter.setText(f"link 1 of {link_total}" if link_total > 1 else "")
		self.status.set_tone("")
		self.status.set_bar_state("")
		self.status.set_indeterminate(True)
		self.status.action.setVisible(False)
		self.download_btn.setEnabled(False)
		self.cancel_btn.setEnabled(True)
		self._set_inputs_enabled(False)

	def _set_inputs_enabled(self, on: bool) -> None:
		for w in (self.url_input, self.open_list_btn, self.dest, self.advanced):
			w.setEnabled(on)

	def _on_link_started(self, index: int, url: str) -> None:
		total = len(self.runner._urls)
		self.status.counter.setText(f"link {index} of {total}" if total > 1 else "")
		self.status.message.setText("Looking up links…")
		self.status.set_indeterminate(True)

	def _on_log_event(self, ev) -> None:
		self.log.append(ev)
		if ev.severity >= 40 and not self.log_section.is_expanded():
			self.log_section.set_expanded(True)

	def _on_progress(self, p) -> None:
		if p.indeterminate:
			self.status.set_indeterminate(True)
			return
		self.status.set_indeterminate(False)
		self.status.message.setText("Downloading")
		pct = int(round(100 * p.completed / max(1, p.track_total)))
		self.status.bar.setValue(min(100, pct))
		self.status.counter.setText(f"track {min(p.track, p.track_total)} of {p.track_total}")
		if p.title:
			self.status.show_detail(p.title)
		self.setWindowTitle(f"Shira — {pct}%")

	def _on_finished(self, outcome, p) -> None:
		self.setWindowTitle("Shira")
		self.status.set_indeterminate(False)
		self._set_inputs_enabled(True)
		self.cancel_btn.setEnabled(False)
		self.status.show_detail("")
		# The summary message carries the tally; leaving "track 4 of 10" up
		# next to "Finished" just reads as a stalled run.
		self.status.counter.setText("")
		self._finished = True

		if self._run_dir is not None:
			# Cancelling kills the child, so shiradl's own cleanup never runs.
			paths.discard(self._run_dir)
			self._run_dir = None

		if outcome is Outcome.CANCELLED:
			self.status.glyph.setText(GLYPH["idle"])
			self.status.message.setText(f"Stopped — {p.saved} saved")
			self.status.set_bar_state("cancelled")
			self.status.set_tone("")
		elif outcome is Outcome.FATAL:
			info = p.fatal or {}
			self.status.glyph.setText(GLYPH["error"])
			self.status.message.setText(info.get("headline", "Shira stopped unexpectedly"))
			self.status.set_bar_state("danger")
			self.status.set_tone("danger")
			self.status.bar.setValue(0)
			self._fatal_banner(
				info.get("headline", "Shira stopped unexpectedly"),
				info.get("remedy", "See the activity log for details."),
			)
			self.log_section.set_expanded(True)
		elif outcome is Outcome.ERRORS:
			self.status.glyph.setText(GLYPH["warning"])
			self.status.message.setText(
				f"Finished with problems — {p.saved} saved, {p.failed or p.errors} failed"
			)
			self.status.set_bar_state("warning")
			self.status.set_tone("warning")
			self.status.bar.setValue(100)
			self.log_section.set_expanded(True)
			self._offer("Copy details", self._copy_log)
		else:
			self.status.glyph.setText(GLYPH["success"])
			extra = f", {p.skipped} already there" if p.skipped else ""
			self.status.message.setText(f"Done — {p.saved} saved{extra}")
			self.status.set_bar_state("success")
			self.status.set_tone("")
			self.status.bar.setValue(100)
			self._offer("Open folder", lambda: self.open_folder(self.dest.text()))

		self._refresh_download_enabled()

	def _offer(self, text: str, fn) -> None:
		try:
			self.status.action.clicked.disconnect()
		except TypeError:
			pass
		self.status.action.setText(text)
		self.status.action.clicked.connect(fn)
		self.status.action.setVisible(True)

	# ------------------------------------------------------- drag and drop

	def dragEnterEvent(self, e) -> None:
		md = e.mimeData()
		if md.hasUrls() and any(
			u.isLocalFile() and u.toLocalFile().lower().endswith(".txt") for u in md.urls()
		):
			e.acceptProposedAction()
			self._show_overlay(True)
		elif md.hasText() and md.text().strip().lower().startswith("http"):
			e.acceptProposedAction()
			self._show_overlay(True)

	def dragLeaveEvent(self, _e) -> None:
		self._show_overlay(False)

	def dropEvent(self, e) -> None:
		self._show_overlay(False)
		md = e.mimeData()
		if md.hasUrls():
			for u in md.urls():
				if u.isLocalFile() and u.toLocalFile().lower().endswith(".txt"):
					self._load_list(u.toLocalFile())
					e.acceptProposedAction()
					return
		if md.hasText():
			text = md.text().strip()
			existing = self.url_input.toPlainText().strip()
			self.url_input.setPlainText(f"{existing}\n{text}".strip())
			self.url_input.flash()
			e.acceptProposedAction()

	def _show_overlay(self, on: bool) -> None:
		if on:
			self.overlay.setGeometry(self.centralWidget().rect())
			self.overlay.raise_()
		self.overlay.setVisible(on)

	def resizeEvent(self, e) -> None:
		super().resizeEvent(e)
		if self.overlay.isVisible():
			self.overlay.setGeometry(self.centralWidget().rect())

	# ------------------------------------------------------------ persistence

	def _restore(self) -> None:
		s = self.settings
		geo = s.get_bytes("ui/geometry")
		if geo is not None:
			self.restoreGeometry(geo)

		self.dest.set_text(s.get_str("paths/library", str(paths.default_library())))
		self.ffmpeg.setText(s.get_str("adv/ffmpeg", "ffmpeg"))

		itag = s.get_str("adv/itag", "140")
		idx = self.quality.findData(itag)
		if idx >= 0:
			self.quality.setCurrentIndex(idx)
		else:
			# A hand-set value must not be silently discarded.
			self.quality.setCurrentIndex(self.quality.findData(CUSTOM_QUALITY))
			self.itag_custom.setText(itag)

		self.cover_size.setValue(s.get_int("adv/cover_size", 1200))
		fi = self.cover_format.findData(s.get_str("adv/cover_format", "jpg"))
		self.cover_format.setCurrentIndex(max(0, fi))
		self.cover_quality.setValue(s.get_int("adv/cover_quality", 94))
		ci = self.cover_crop.findData(s.get_str("adv/cover_crop", "auto"))
		self.cover_crop.setCurrentIndex(max(0, ci))
		self.cover_img.setText(s.get_str("adv/cover_img", ""))
		self.tpl_folder.setText(s.get_str("adv/tpl_folder", "{albumartist}/{album}"))
		self.tpl_file.setText(s.get_str("adv/tpl_file", "{track:02d} {title}"))
		self.exclude_tags.setText(s.get_str("adv/exclude_tags", ""))
		self.truncate.setValue(s.get_int("adv/truncate", 60))
		self.no_truncate.setChecked(s.get_bool("adv/no_truncate", False))
		self.cookies_enabled.setChecked(s.get_bool("adv/cookies_on", False))
		self.cookies_path.setText(s.get_str("adv/cookies_path", str(paths.default_cookies())))
		self.save_cover.setChecked(s.get_bool("adv/save_cover", False))
		self.overwrite.setChecked(s.get_bool("adv/overwrite", False))
		self.single_folder.setChecked(s.get_bool("adv/single_folder", False))
		self.use_playlist_name.setChecked(s.get_bool("adv/use_playlist_name", False))
		self.print_exceptions.setChecked(s.get_bool("adv/print_exceptions", False))
		self.use_config.setChecked(s.get_bool("adv/use_config", False))
		li = self.log_detail.findData(s.get_int("ui/log_level", 20))
		self.log_detail.setCurrentIndex(max(0, li))

		self.advanced.set_expanded(s.get_bool("ui/advanced_open", False))
		self.log_section.set_expanded(s.get_bool("ui/log_open", False))

		self._on_templates_changed()
		self._on_cover_format()
		self._on_quality_changed()
		self.log.min_level = self.log_detail.currentData()
		self.log.show_details = self.print_exceptions.isChecked()
		self.truncate.setEnabled(not self.no_truncate.isChecked())
		self.cookies_row.setEnabled(self.cookies_enabled.isChecked())

	def _persist(self) -> None:
		s = self.settings
		s.set("ui/geometry", self.saveGeometry())
		s.set("paths/library", self.dest.text())
		s.set("adv/ffmpeg", self.ffmpeg.text())
		itag = self.quality.currentData()
		s.set("adv/itag", self.itag_custom.text().strip() if itag == CUSTOM_QUALITY else itag)
		s.set("adv/cover_size", self.cover_size.value())
		s.set("adv/cover_format", self.cover_format.currentData())
		s.set("adv/cover_quality", self.cover_quality.value())
		s.set("adv/cover_crop", self.cover_crop.currentData())
		s.set("adv/cover_img", self.cover_img.text())
		s.set("adv/tpl_folder", self.tpl_folder.text())
		s.set("adv/tpl_file", self.tpl_file.text())
		s.set("adv/exclude_tags", self.exclude_tags.text())
		s.set("adv/truncate", self.truncate.value())
		s.set("adv/no_truncate", self.no_truncate.isChecked())
		s.set("adv/cookies_on", self.cookies_enabled.isChecked())
		s.set("adv/cookies_path", self.cookies_path.text())
		s.set("adv/save_cover", self.save_cover.isChecked())
		s.set("adv/overwrite", self.overwrite.isChecked())
		s.set("adv/single_folder", self.single_folder.isChecked())
		s.set("adv/use_playlist_name", self.use_playlist_name.isChecked())
		s.set("adv/print_exceptions", self.print_exceptions.isChecked())
		s.set("adv/use_config", self.use_config.isChecked())
		s.set("ui/log_level", self.log_detail.currentData())
		s.set("ui/advanced_open", self.advanced.is_expanded())
		s.set("ui/log_open", self.log_section.is_expanded())
		s.sync()

	def closeEvent(self, e) -> None:
		if self.runner.state is not State.IDLE:
			if QMessageBox.question(
				self, "Shira", "A download is still running. Stop it and quit?"
			) != QMessageBox.StandardButton.Yes:
				e.ignore()
				return
			self.runner.cancel()
		self._persist()
		if self._run_dir is not None:
			paths.discard(self._run_dir)
		super().closeEvent(e)
