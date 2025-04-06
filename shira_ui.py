import sys
import os
import contextlib
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QComboBox, QCheckBox, QHBoxLayout
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon

from shiradl.cli import cli as shira_cli

class DummyBuffer:
    def __init__(self, stream):
        self.stream = stream
    def write(self, b):
        # b is bytes; decode and forward as text
        text = b.decode(self.stream.encoding, errors='ignore')
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
        while "\n" in self._buffer:
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

        self.setStyleSheet("""
            QWidget {
                background-color: #202124;
                color: #e8eaed;
                font-family: Segoe UI, sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background-color: #303134;
                border: 1px solid #5f6368;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3c4043;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #2b2c2e;
                border: 1px solid #5f6368;
                border-radius: 4px;
                padding: 4px;
            }
            QCheckBox {
                spacing: 6px;
            }
            QTextEdit {
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        layout.addWidget(QLabel("Enter URL or path to links.txt:"))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        browse_layout = QHBoxLayout()
        self.browse_button = QPushButton("Browse file")
        self.browse_button.clicked.connect(self.browse_file)
        browse_layout.addWidget(self.browse_button)
        layout.addLayout(browse_layout)

        layout.addWidget(QLabel("Platform:"))
        self.platform_select = QComboBox()
        self.platform_select.addItems(["YouTube Music", "YouTube", "SoundCloud"])
        layout.addWidget(self.platform_select)

        self.cookies_checkbox = QCheckBox("Use cookies.txt")
        layout.addWidget(self.cookies_checkbox)

        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        layout.addWidget(self.overwrite_checkbox)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)

        layout.addWidget(QLabel("Output log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(200)
        layout.addWidget(self.log_output)

        self.setLayout(layout)
        self.thread = None

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select links.txt file")
        if file_path:
            self.url_input.setText(file_path)

    def start_download(self):
        url = self.url_input.text().strip()
        args = []

        if url.endswith(".txt"):
            args += ["-u", url]
        else:
            args.append(url)

        if self.cookies_checkbox.isChecked():
            cookies_path = os.path.expanduser("~/.shira/cookies.txt")
            if os.path.exists(cookies_path):
                args += ["--cookies-location", cookies_path]

        if self.overwrite_checkbox.isChecked():
            args.append("--overwrite")

        self.log_output.append(f"\nRunning: python -m shiradl {' '.join(args)}\n")

        self.thread = DownloadThread(args)
        self.thread.line_output.connect(self.log_output.append)
        self.thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ShiraDownloader()
    window.show()
    sys.exit(app.exec())
