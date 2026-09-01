# Shira UI

A desktop interface for [shira](https://github.com/KraXen72/shira) — smart music downloader for YouTube, YouTube Music and SoundCloud.

Paste some links, pick a folder, press Download. No command line needed.

### Features
- Supports YouTube, YouTube Music, and SoundCloud
- Light and dark themes, remembered between launches
- Queue several links at once, or drop a `links.txt` onto the window
- Live progress, a working Cancel button, and a colour-coded activity log
- Plain-language advanced options, collapsed by default
- Your settings are remembered and are always what actually runs

---

## Installing from scratch

This assumes a machine with **nothing** installed yet. It takes about five
minutes. Every command goes in a terminal — PowerShell on Windows, Terminal on
macOS or Linux.

### What you need, and why

| | Why |
|---|---|
| **Python 3.12 or newer** | Runs the app. See the note below about 3.11. |
| **FFmpeg** (including **ffprobe**) | Shira converts and tags every file with it. Downloads cannot work without it. `ffprobe` ships alongside `ffmpeg`; both are needed. If you skip this, the app offers a **Get FFmpeg** button that downloads it for you. |
| **Git** | To download the code. |

> **Use Python 3.12+, not 3.11.** `shiradl`'s own `pyproject.toml` says `>=3.11`,
> but that is wrong: `shiradl/mbtag.py` uses f-string syntax introduced in 3.12.
> On 3.11 the app installs and downloads fine, but the separate `mbtag`
> re-tagging tool fails with a `SyntaxError`. 3.12+ avoids the whole question.

### Step 1 — install the prerequisites

**Windows**

```powershell
winget install Python.Python.3.13 Gyan.FFmpeg Git.Git
```

**Close and reopen your terminal afterwards**, so the new programs are picked up.

<details>
<summary>macOS / Linux</summary>

macOS, with [Homebrew](https://brew.sh):

```bash
brew install python@3.13 ffmpeg git
```

Debian / Ubuntu:

```bash
sudo apt install python3 python3-venv ffmpeg git
```

</details>

Check they are all available before continuing. Each should print a version:

```powershell
python --version; ffmpeg -version; ffprobe -version; git --version
```

If any says "not recognized", it did not install or your terminal still has the
old `PATH` — reopen the terminal and try again.

### Step 2 — download Shira UI

```powershell
git clone https://github.com/Maxikozie/shira-ui.git
```

```powershell
cd shira-ui
```

### Step 3 — create a private environment for it

This keeps Shira's dependencies out of your system Python. It creates a `.venv`
folder inside the project.

```powershell
py -3.13 -m venv .venv
```

On macOS or Linux use `python3 -m venv .venv`.

### Step 4 — install everything

```powershell
.venv\Scripts\python.exe -m pip install -e . PyQt6
```

On macOS or Linux: `.venv/bin/python -m pip install -e . PyQt6`

That one command installs **everything**: `shiradl` itself plus `yt-dlp`,
`ytmusicapi`, `mediafile`, `pillow`, `requests-cache`, `click`, and the PyQt6
interface toolkit. You do not install `shiradl` separately — `-e .` installs the
copy inside the folder you just cloned.

> **The `-e` is required, not a preference.** Since v1.8.x, `shiradl` looks up
> its own version through `importlib.metadata`, which only works for a properly
> installed package. Without it, every single track fails with a confusing
> error rather than one clear message at startup.

Optional — nicer button icons. The app looks correct without it:

```powershell
.venv\Scripts\python.exe -m pip install qtawesome
```

### Step 5 — run it

```powershell
.venv\Scripts\python.exe shira_ui.py
```

On macOS or Linux: `.venv/bin/python shira_ui.py`

If the window opens and the status card says **Ready**, you are done. If
something is missing, a banner at the top of the window will say what and how
to fix it.

### Check the install worked

```powershell
.venv\Scripts\python.exe -m shiradl --version
```

Should print `python -m shiradl, version 1.8.5` or newer. If it prints a
`PackageNotFoundError` instead, Step 4 did not complete — re-run it.

### Making it easier to launch

Rather than typing the command each time, create a shortcut with this as its
target (adjust the path to where you cloned it):

```
C:\path\to\shira-ui\.venv\Scripts\pythonw.exe C:\path\to\shira-ui\shira_ui.py
```

`pythonw.exe` rather than `python.exe` opens the app without a console window
behind it.

---

## Updating

Get the newest Shira UI:

```powershell
git pull
```

```powershell
.venv\Scripts\python.exe -m pip install -e . PyQt6
```

Re-running the install is what picks up any new or updated dependencies.

<details>
<summary>Pulling in a newer upstream shiradl</summary>

This fork shares git history with upstream, so syncing is a real merge:

```bash
git remote add upstream https://github.com/KraXen72/shira.git
git fetch upstream && git merge upstream/master
```

Then reinstall and run the tests **first**:

```bash
pip install -e . && python -m pytest tests_ui
```

Those tests check the interface against the `shiradl` you actually have
installed. If upstream renamed a command-line flag or reworded a log message,
they fail and name exactly what to reconcile — both of which otherwise break
quietly, the second one while downloads appear to keep working.

</details>

---

## Troubleshooting

**The window doesn't open, or `ModuleNotFoundError: No module named 'PyQt6'`**

The install in Step 4 did not finish, or you are running the wrong Python. Use
the one inside `.venv`, not a bare `python`.

**`PackageNotFoundError: No package metadata was found for shiradl`**

You are running against an uninstalled copy of the source. From the project
folder, run:

```powershell
.venv\Scripts\python.exe -m pip install -e .
```

**A red banner says FFmpeg wasn't found**

Press **Get FFmpeg** in the banner and Shira downloads it for you (about
111 MB) into its own folder — no terminal needed. If you already have
`ffmpeg.exe` somewhere, press **Locate** and point at it instead. Installing it
yourself with `winget install Gyan.FFmpeg` and pressing **Recheck** also works.

**A red banner says FFprobe wasn't found**

`ffprobe` normally ships with `ffmpeg`. Reinstall FFmpeg so both sit in the
same folder — Shira looks for `ffprobe` next to `ffmpeg` automatically.

**Downloads fail, or "no formats available"**

YouTube changes frequently and `yt-dlp` needs to keep up:

```powershell
.venv\Scripts\python.exe -m pip install -U yt-dlp
```

For private, members-only or age-restricted tracks, export a `cookies.txt` from
your browser and switch on **Use my cookies.txt** under *Advanced options →
When things go wrong*.

**A `SyntaxError` mentioning `mbtag.py`**

You are on Python 3.11. Re-create the environment with 3.12 or newer:

```powershell
rmdir /s /q .venv
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e . PyQt6
```

**Everything downloads but nothing appears in my folder**

Open *Advanced options* and check the **Preview** line under the naming
patterns — it shows exactly where files will land. The **Open** button next to
*Save music to* opens the destination.

---

## Building a standalone .exe (Windows)

Produces a folder you can zip and hand to someone who has no Python at all.
They still need FFmpeg — see the note below.

Build with a **non-conda** Python. A conda interpreter links `_ctypes` against
a `libffi` that PyInstaller does not collect, and the resulting build fails at
startup with `DLL load failed while importing _ctypes`.

```powershell
py -3.14 -m venv .venv-build
```

```powershell
.venv-build\Scripts\python.exe -m pip install -e . PyQt6 pyinstaller
```

```powershell
.venv-build\Scripts\python.exe -m PyInstaller shira-ui.spec --noconfirm --clean
```

The result is `dist\Shira UI\Shira UI.exe`, about 116 MB unpacked. Ship the
whole `Shira UI` folder, not just the .exe — the `_internal` folder beside it
is required.

The window and taskbar icon comes from `logo.ico`. Regenerate it after editing
`logo.svg`:

```powershell
python tools\make_icon.py
```

To produce a release archive (about 53 MB zipped):

```powershell
Compress-Archive -Path "dist\Shira UI" -DestinationPath "dist\Shira-UI-windows-x64.zip"
```

Note the .exe is unsigned, so Windows SmartScreen warns on first run —
"More info" then "Run anyway". Code signing requires a purchased certificate.

**FFmpeg is not bundled — the app fetches it instead.** On first run, if
FFmpeg is missing, the banner offers a **Get FFmpeg** button that downloads it
(about 111 MB) into the app's own folder and verifies it runs. So someone using
the .exe never has to open a terminal.

It is downloaded rather than shipped so that this project redistributes
nothing: the user triggers the download themselves, which sidesteps FFmpeg's
GPL redistribution obligations entirely. **Locate** remains available for
anyone who already has `ffmpeg.exe`, and `winget install Gyan.FFmpeg` still
works if they prefer.

The download is pinned to a specific FFmpeg build and checked against a
SHA-256 hash before anything is unpacked; a mismatch is discarded and nothing
is installed. To move to a newer FFmpeg, update `SOURCE_URL` and
`EXPECTED_SHA256` in `shiraui/ffmpeg_setup.py` — the publisher serves the hash
at `<url>.sha256`.

<details>
<summary>How the packaged app runs downloads</summary>

Normally the app spawns `pythonw.exe -m shiradl` for each link. In a frozen
build there is no interpreter to spawn — `sys.executable` is the .exe itself,
so `-m shiradl` would just relaunch the GUI.

Instead the executable re-runs *itself* with `--shiradl-child`, which
`shira_ui.py` detects before Qt is imported and routes into `shiradl.cli`.
That also makes the packaged app usable as a CLI:

```powershell
"dist\Shira UI\Shira UI.exe" --shiradl-child --version
```

`shira-ui.spec` bundles shiradl's `.dist-info`, because shiradl reads its own
version through `importlib.metadata`; without it every track fails. It also
bundles `ytmusicapi`'s locale files, which it loads via `gettext` while
constructing `YTMusic()` — missing them kills the run before any track starts.

</details>

---

## For developers

The interface lives in the `shiraui/` package; `shira_ui.py` is a small
launcher shim. `shiradl/` is vendored upstream code, kept byte-identical so
merges stay clean — fixes belong in `shiraui/`.

```bash
python -m pytest tests_ui
```

`tests_ui/` is the interface's own suite; `tests/` belongs to upstream.
See [CLAUDE.md](CLAUDE.md) for architecture notes.
