import sys
import os
import subprocess
import contextlib
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QComboBox,
    QCheckBox,
    QFormLayout,
    QStyleFactory,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor

from shiradl.cli import cli as shira_cli


class DummyBuffer:
    def __init__(self, stream):
        self.stream = stream

    def write(self, b):
        text = b.decode(self.stream.encoding, errors="ignore")
        self.stream.write(text)


class EmittingStream:
    def __init__(self, emit_func):
        self.emit_func = emit_func
        self._buffer = ""

    @property
    def encoding(self):
        return "utf-8"

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer or "\r" in self._buffer:
            nl = self._buffer.find("\n")
            cr = self._buffer.find("\r")
            if cr != -1 and (nl == -1 or cr < nl):
                line, self._buffer = self._buffer.split("\r", 1)
                if self._buffer.startswith("\n"):
                    self._buffer = self._buffer[1:]
                self.emit_func("\r" + line)
            else:
                line, self._buffer = self._buffer.split("\n", 1)
                self.emit_func(line)

    def flush(self):
        if self._buffer:
            self.emit_func(self._buffer)
            self._buffer = ""

    def isatty(self):
        return False

    @property
    def buffer(self):
        return DummyBuffer(self)


class DownloadThread(QThread):
    line_output = pyqtSignal(str)

    def __init__(self, args):
        super().__init__()
        self.args = args

    def run(self):
        try:
            stream = EmittingStream(self.line_output.emit)
            with contextlib.redirect_stdout(stream):
                try:
                    shira_cli(self.args, standalone_mode=False)
                except SystemExit:
                    pass
        except Exception as e:
            self.line_output.emit(f"Error: {str(e)}")


class ShiraDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shira UI - Smart Music Downloader")
        self.setWindowIcon(QIcon("logo.svg"))
        self.setMinimumWidth(640)

        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Main tab
        main_tab = QWidget()
        main_layout = QVBoxLayout()

        main_layout.addWidget(QLabel("Enter URL or path to links.txt:"))
        self.url_input = QLineEdit()
        main_layout.addWidget(self.url_input)

        browse_layout = QHBoxLayout()
        self.browse_button = QPushButton("Browse file")
        self.browse_button.clicked.connect(self.browse_links_file)
        browse_layout.addWidget(self.browse_button)
        main_layout.addLayout(browse_layout)

        fp_layout = QHBoxLayout()
        self.final_path_input = QLineEdit(os.path.abspath("YouTube Music"))
        fp_layout.addWidget(QLabel("Final path:"))
        fp_layout.addWidget(self.final_path_input)
        fp_btn = QPushButton("Browse")
        fp_btn.clicked.connect(lambda: self.browse_folder(self.final_path_input))
        fp_layout.addWidget(fp_btn)
        main_layout.addLayout(fp_layout)

        tp_layout = QHBoxLayout()
        self.temp_path_input = QLineEdit(os.path.abspath("temp"))
        tp_layout.addWidget(QLabel("Temp path:"))
        tp_layout.addWidget(self.temp_path_input)
        tp_btn = QPushButton("Browse")
        tp_btn.clicked.connect(lambda: self.browse_folder(self.temp_path_input))
        tp_layout.addWidget(tp_btn)
        main_layout.addLayout(tp_layout)

        cp_layout = QHBoxLayout()
        self.config_path_input = QLineEdit(str(Path.home() / ".shiradl" / "config.json"))
        cp_layout.addWidget(QLabel("Config file:"))
        cp_layout.addWidget(self.config_path_input)
        cp_btn = QPushButton("Browse")
        cp_btn.clicked.connect(lambda: self.browse_file(self.config_path_input))
        cp_layout.addWidget(cp_btn)
        main_layout.addLayout(cp_layout)

        self.cookies_checkbox = QCheckBox("Use cookies.txt")
        main_layout.addWidget(self.cookies_checkbox)
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        main_layout.addWidget(self.overwrite_checkbox)
        self.save_cover_checkbox = QCheckBox("Save cover as separate file")
        main_layout.addWidget(self.save_cover_checkbox)
        self.single_folder_checkbox = QCheckBox("Wrap singles in folder")
        main_layout.addWidget(self.single_folder_checkbox)
        self.use_playlist_name_checkbox = QCheckBox("Use playlist name")
        main_layout.addWidget(self.use_playlist_name_checkbox)

        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Log level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        log_layout.addWidget(self.log_level_combo)
        main_layout.addLayout(log_layout)

        btn_layout = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        btn_layout.addWidget(self.download_button)
        self.open_folder_button = QPushButton("Open download folder")
        self.open_folder_button.clicked.connect(self.open_download_folder)
        btn_layout.addWidget(self.open_folder_button)
        main_layout.addLayout(btn_layout)

        main_tab.setLayout(main_layout)
        self.tabs.addTab(main_tab, "Main")

        # Advanced tab
        adv_tab = QWidget()
        adv_layout = QFormLayout()

        self.ffmpeg_input = QLineEdit("ffmpeg")
        adv_layout.addRow("FFmpeg location:", self.ffmpeg_input)

        self.itag_input = QLineEdit("140")
        adv_layout.addRow("Itag:", self.itag_input)

        self.cover_size_input = QLineEdit("1200")
        adv_layout.addRow("Cover size:", self.cover_size_input)

        self.cover_format_combo = QComboBox()
        self.cover_format_combo.addItems(["jpg", "png"])
        adv_layout.addRow("Cover format:", self.cover_format_combo)

        self.cover_quality_input = QLineEdit("94")
        adv_layout.addRow("Cover quality:", self.cover_quality_input)

        cover_img_layout = QHBoxLayout()
        self.cover_img_input = QLineEdit()
        cover_img_layout.addWidget(self.cover_img_input)
        cover_img_btn = QPushButton("Browse")
        cover_img_btn.clicked.connect(lambda: self.browse_file(self.cover_img_input))
        cover_img_layout.addWidget(cover_img_btn)
        adv_layout.addRow(QLabel("Cover image:"), cover_img_layout)

        self.cover_crop_combo = QComboBox()
        self.cover_crop_combo.addItems(["auto", "crop", "pad"])
        adv_layout.addRow("Cover crop:", self.cover_crop_combo)

        self.template_folder_input = QLineEdit("{albumartist}/{album}")
        adv_layout.addRow("Template folder:", self.template_folder_input)

        self.template_file_input = QLineEdit("{track:02d} {title}")
        adv_layout.addRow("Template file:", self.template_file_input)

        self.exclude_tags_input = QLineEdit()
        adv_layout.addRow("Exclude tags:", self.exclude_tags_input)

        self.truncate_input = QLineEdit("60")
        adv_layout.addRow("Truncate length:", self.truncate_input)

        self.print_exceptions_checkbox = QCheckBox("Print exceptions")
        adv_layout.addRow(self.print_exceptions_checkbox)

        self.no_config_checkbox = QCheckBox("Don't use config file")
        adv_layout.addRow(self.no_config_checkbox)

        adv_tab.setLayout(adv_layout)
        self.tabs.addTab(adv_tab, "Advanced")

        layout.addWidget(QLabel("Output log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(200)
        layout.addWidget(self.log_output)

        self.setLayout(layout)
        self.thread = None

    # Browse helpers
    def browse_links_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select links.txt file")
        if file_path:
            self.url_input.setText(file_path)

    def browse_folder(self, widget: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if folder:
            widget.setText(folder)

    def browse_file(self, widget: QLineEdit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if file_path:
            widget.setText(file_path)

    def open_download_folder(self):
        path = self.final_path_input.text().strip()
        if not path:
            return
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def handle_output(self, text: str):
        if text.startswith("\r"):
            cursor = self.log_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(text[1:])
            self.log_output.setTextCursor(cursor)
        else:
            self.log_output.append(text)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            return
        args = []

        if url.endswith(".txt"):
            args += ["-u", url]
        else:
            args.append(url)

        args += ["--final-path", self.final_path_input.text().strip()]
        args += ["--temp-path", self.temp_path_input.text().strip()]

        config_path = self.config_path_input.text().strip()
        if config_path:
            args += ["--config-location", config_path]
        if self.no_config_checkbox.isChecked():
            args.append("--no-config-file")

        if self.cookies_checkbox.isChecked():
            cookies_path = os.path.expanduser("~/.shira/cookies.txt")
            if os.path.exists(cookies_path):
                args += ["--cookies-location", cookies_path]

        args += ["--ffmpeg-location", self.ffmpeg_input.text().strip()]
        args += ["--itag", self.itag_input.text().strip()]
        args += ["--cover-size", self.cover_size_input.text().strip()]
        args += ["--cover-format", self.cover_format_combo.currentText()]
        args += ["--cover-quality", self.cover_quality_input.text().strip()]
        if self.cover_img_input.text().strip():
            args += ["--cover-img", self.cover_img_input.text().strip()]
        args += ["--cover-crop", self.cover_crop_combo.currentText()]
        args += ["--template-folder", self.template_folder_input.text().strip()]
        args += ["--template-file", self.template_file_input.text().strip()]
        if self.exclude_tags_input.text().strip():
            args += ["--exclude-tags", self.exclude_tags_input.text().strip()]
        args += ["--truncate", self.truncate_input.text().strip()]
        args += ["--log-level", self.log_level_combo.currentText()]

        if self.save_cover_checkbox.isChecked():
            args.append("--save-cover")
        if self.overwrite_checkbox.isChecked():
            args.append("--overwrite")
        if self.print_exceptions_checkbox.isChecked():
            args.append("--print-exceptions")
        if self.single_folder_checkbox.isChecked():
            args.append("--single-folder")
        if self.use_playlist_name_checkbox.isChecked():
            args.append("--use-playlist-name")

        self.log_output.append(
            f"\nRunning: python -m shiradl {' '.join(args)}\n"
        )

        self.thread = DownloadThread(args)
        self.thread.line_output.connect(self.handle_output)
        self.thread.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if "Breeze" in QStyleFactory.keys():
        app.setStyle("Breeze")
    window = ShiraDownloader()
    window.show()
    sys.exit(app.exec())

