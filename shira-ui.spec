# PyInstaller spec for Shira UI.
#
#   pip install pyinstaller
#   pyinstaller shira-ui.spec
#
# Output: dist/Shira UI/Shira UI.exe  (one folder -- see the note at the end)
#
# Three things here are load-bearing:
#
# 1. copy_metadata("shiradl"). Since v1.8.x, shiradl reads its own version via
#    importlib.metadata inside MBSong.__init__. Without the .dist-info in the
#    bundle that raises PackageNotFoundError on *every track*, which surfaces
#    as "Done (N error(s))" rather than anything informative.
# 2. console=False, but the app still spawns itself as the downloader child
#    (see shiraui/preflight.child_command). The child inherits windowed mode,
#    so no console flashes -- QProcess pipes still carry its output.
# 3. FFmpeg is deliberately NOT bundled. This project is MIT; shipping a GPL
#    FFmpeg build alongside it would drag the whole distribution under GPL.
#    The app detects a missing FFmpeg at startup and shows an actionable
#    banner instead, so this degrades into a clear message rather than a
#    silent failure.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = [("logo.svg", ".")]
datas += copy_metadata("shiradl")
# yt-dlp resolves extractors dynamically, so static analysis misses most of them.
datas += copy_metadata("yt-dlp")
# ytmusicapi calls gettext.translation("base", ...) during YTMusic.__init__ and
# raises FileNotFoundError without its locales/ tree -- which happens before a
# single track is touched, so the whole run dies at Dl() construction.
datas += collect_data_files("ytmusicapi")

hiddenimports = [
    "shiradl",
    "shiradl.cli",
    "shiradl.dl",
    "shiradl.mbtag",
    "shiradl.metadata",
    "shiradl.musicbrainz",
    "shiradl.tagging",
    "shiradl.util",
]
hiddenimports += collect_submodules("yt_dlp")
hiddenimports += collect_submodules("ytmusicapi")
hiddenimports += collect_submodules("mediafile")

a = Analysis(
    ["shira_ui.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Qt modules the app never touches. Dropping them saves ~100 MB.
    excludes=[
        "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets", "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
        "PyQt6.Qt3DCore", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
        "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSensors",
        "PyQt6.QtSerialPort", "PyQt6.QtSql", "PyQt6.QtTest", "PyQt6.QtDesigner",
        "PyQt6.QtHelp", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "PyQt6.QtPdf",
        "PyQt6.QtPdfWidgets", "PyQt6.QtSpatialAudio", "PyQt6.QtTextToSpeech",
        "tkinter", "unittest", "pydoc_data",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Shira UI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # no console window; see note 2 above
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows requires .ico. Regenerate from logo.svg with tools/make_icon.py.
    icon="logo.ico",
)

# One-folder rather than one-file. onefile re-extracts ~200 MB to a temp
# directory on every launch, and the app spawns itself once per link, so each
# download would pay that cost again.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Shira UI",
)
