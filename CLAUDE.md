# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of [KraXen72/shira](https://github.com/KraXen72/shira) (a YouTube/YouTube Music/SoundCloud music downloader with heavy metadata enrichment) that adds `shira_ui.py`, a PyQt6 GUI on top of it. `shiradl/` is upstream code kept pristine so it can be merged forward; `shira_ui.py` is the only fork-specific source file.

Syncing with upstream is a real git merge, not a file copy — the fork shares history with `KraXen72/shira`:

```bash
git remote add upstream https://github.com/KraXen72/shira.git
```

```bash
git fetch upstream && git merge upstream/master
```

Only `.gitignore` and `README.md` conflict (both are fork-owned; keep our side and re-apply upstream's new ignore entries). Currently synced to upstream **v1.8.5**.

**After every sync, run the contract tests first:**

```bash
pip install -e . && python -m pytest tests_ui
```

`tests_ui/test_upstream_contract.py` introspects the *installed* shiradl and
guards the two places this fork couples to it. Both fail quietly when upstream
drifts, which is why they are tested rather than trusted:

- **`shiraui/argsbuilder.py` emits flag strings.** If upstream renames or drops
  an option, Click rejects the argv and every download fails with a usage
  error. The test checks every emitted flag against `cli.params`, that booleans
  are still booleans, that `--cover-format`/`--cover-crop` values are still
  valid `Choice`s, and that the `IntRange` bounds still match the spin boxes.
- **`shiraui/logparse.py` matches exact log text.** If upstream rewords a
  message, the progress bar and completion summary stop working while downloads
  carry on fine — it looks like the app hung. The test asserts the message
  shapes still exist in `cli.py`, and round-trips a record through shiradl's own
  `logging` format into the parser.

It also re-checks the safety assumption behind `shiraui/paths.py` — that
`--temp-path` is still `shutil.rmtree`'d — so if upstream ever stops doing that,
the reason for the app-owned work directory gets revisited deliberately.

A failure names the file to reconcile. Fix `shiraui/`, never `shiradl/`.

## Commands

`shiradl` must be **installed**, not just checked out — see "The install requirement" below.

```bash
pip install -e .             # required before anything works
python shira_ui.py           # launch the GUI
python -m shiradl <URL>      # upstream CLI (also installed as `shiradl`)
python -m shiradl.mbtag PATH # MusicBrainz re-tagger for existing files (also `mbtag`)
```

Upstream manages deps with uv and defines tasks via taskipy in `pyproject.toml`:

```bash
pytest -v -x                       # or: task test
pytest tests/smoke.test.py -v -x   # or: task test:smoke
pytest tests/metadata.test.py -v -x
pytest tests/download.test.py -v -x
```

Tests are marked `download`, `metadata`, and `smoke` (all hit the network); select with `-m`. Note `python_files = ["*.test.py", "test_*.py"]` — the unusual `*.test.py` naming is deliberate, so a new test file named otherwise silently won't run. There is no linter configured.

## The install requirement

Since v1.8.x, `shiradl` resolves its own version through `importlib.metadata`:

- `musicbrainz.py:162` — `_pkg_version('shiradl')` inside `MBSong.__init__`
- `cli.py` — `@click.version_option(package_name="shiradl")`

Neither has a fallback, and `__init__.py` no longer defines `__version__`. Running against a bare source tree raises `PackageNotFoundError`. The `MBSong(...)` construction in `musicbrainz_enrich_tags` sits *outside* the surrounding try/except, so this surfaces as every single track failing, not as a clean startup error. `pip install -e .` fixes it.

## Architecture

### Download pipeline

`shiradl/cli.py` is the orchestrator — the whole per-track pipeline lives in its `cli()` loop, not in `Dl`. Reading that loop is the fastest way to understand the project. Per track it:

1. `Dl.get_download_queue(url)` — yt-dlp flat extract; expands playlists, detects SoundCloud, resolves `MPREb_` YTMusic album URLs.
2. Metadata, via one of two mutually exclusive paths:
   - **YTMusic path** — `Dl.get_ytmusic_watch_playlist()` returns a hit → `Dl.get_tags()` builds `Tags` from the ytmusicapi album/watch-playlist data.
   - **"Tigerv2" path** (`metadata.smart_metadata`) — no YTMusic album (or SoundCloud). Scrapes tags out of the raw yt-dlp info dict using per-domain extractors (`youtube_extractor` / `soundcloud_extractor`) plus `smart_tag()`, which picks the most frequently occurring candidate value across several info-dict keys.
3. `musicbrainz.musicbrainz_enrich_tags()` — queries the MusicBrainz WS/2 API and *overwrites* title/artist/album/date when a match is found, then adds `mb_*` MBID tags. Match confidence comes from `normalized_compare_regex` (strips leading zeros, `feat.`/`ft.` clauses, commas; normalizes exotic hyphens). A failed fetch now degrades gracefully and returns the tags unenriched.
4. `Dl.get_final_location()` — formats `--template-folder`/`--template-file` against the tags. Singles get special-cased: the trailing `/{album}` segment and the `{track:02d} ` prefix are stripped unless `--single-folder`.
5. Download (`Dl.download` / `download_souncloud`, or `Dl.stub_download` under `--no-download`) → `Dl.fixup` (ffmpeg remux, `-f mp4` when ffprobe reports opus) → `tagging.metadata_applier` → move into place.

Failures are per-track: exceptions are logged and counted, the loop continues, and `temp_path` is wiped in the `finally`.

### Key invariants

- **`Tags`** (`tagging.py`) is the single dict passed between every stage. It is a `TypedDict` whose keys are `mediafile` attribute names — `metadata_applier` does `setattr(MediaFile_handle, key, value)`, so adding a tag means adding a key mediafile understands. `mb_*` values are utf-8 **bytes** unless `skip_encode`.
- **`Dl.tags` is a single-track cache.** `cli.py` must reset `dl.tags = None` before each track or the previous track's tags leak through `get_tags()`.
- **`Dl.soundcloud` is sticky mutable state** set during `get_download_queue` and read everywhere afterwards to pick mp3 vs m4a, skip the YTMusic lookup, and switch the default output folder to `./SoundCloud`.
- Multi-value artists are joined with `MV_SEPARATOR` (`/`) in file tags but `MV_SEPARATOR_VISUAL` (` & `) in filenames. `fallback_mv=True` in `metadata_applier` exists because Auxio doesn't read real multi-value m4a tags yet.
- Cover art is fetched through a shared `requests_cache` session named `shira_requests_cache`, stored in the OS cache directory (`use_cache_dir=True`). Three modules construct their own session with that same name but different TTLs.
- `--cover-crop auto` runs `determine_image_crop`, which samples corner pixels of a smoothed 64-color version of the thumbnail and decides crop-vs-pad from the per-channel stddev.

### Config resolution

`--no-config-file` carries a Click **callback** (`no_config_callback`) that does the actual config loading as a side effect — it writes a default `~/.shiradl/config.json` from the option defaults on first run, then injects file values into `ctx.params` for any option whose `ParameterSource` isn't `COMMANDLINE`. Option ordering in the decorator stack therefore matters: `--config-location` must be parsed before the callback fires. Adding a non-persistable option means adding it to `EXCLUDED_PARAMS`.

### GUI

The interface is the `shiraui/` package; `shira_ui.py` is a 5-line launcher shim
that keeps the documented `python shira_ui.py` command working. `shiraui` cannot
collide with upstream's `shiradl`, so the whole GUI tree is fork-owned and
upstream never touches it. Its tests live in `tests_ui/` — deliberately not in
`tests/`, which is upstream's.

`shiraui/runner.py` launches `pythonw.exe -u -m shiradl` via **QProcess**, one
process per link. It does *not* import `cli.cli` in-process. Four reasons, each
a defect in the old design:

- **stderr.** `cli.py` binds its logging handler to stderr, but the old GUI only
  did `redirect_stdout` — so every `logger.*` call was invisible and a missing
  ffmpeg looked like a dead button. Separate QProcess channels fix it.
- **Cancel.** `shira_cli()` is one blocking call with no interruption point;
  only killing a child process can stop it.
- **`Dl.soundcloud` latches** True and never resets (`dl.py:85`) while all URLs
  share one `Dl`, so a mixed YouTube+SoundCloud batch corrupts later tracks.
  One process per link sidesteps it without touching `shiradl/`.
- **`setWorkingDirectory`** keeps `--log-level DEBUG`'s `info.json` dumps out of
  the user's folders.

The child always runs at `INFO` (or `DEBUG`). Never pass the user's verbosity
through: the progress lines the UI parses — `Downloading "..." (track j/N from
URL i/M)` and the `Done (N error(s))` sentinel — are `logger.info`, so `WARNING`
would silently delete the progress bar and completion summary. The "Log detail"
combo filters client-side instead.

Completion is read from the `Done (N error(s))` sentinel, never the exit code:
`cli.py` returns 0 even when every track failed.

Per-file download percentage is **not obtainable**. `dl.py` passes `quiet: True`
to yt-dlp, which suppresses its progress output entirely; getting it back would
mean editing `dl.py`. Progress is therefore track-level, with an indeterminate
bar inside a track.

`shiraui/argsbuilder.py` is the one place argv is built, and the fork's only
real coupling to upstream — nothing enforces it at runtime. When merging a new
upstream version, diff it against `cli.py`'s `@click.option` list. Verified
against 1.8.5.

`--no-config-file` is always passed. Click flags are one-way (there is no
`--no-overwrite`), so an unticked box emits nothing and a `true` in
`~/.shiradl/config.json` would win and be unreachable from the UI.

**Safety:** `--temp-path` is `shutil.rmtree`'d after every track (`dl.py:261`).
It is never a user-typed path — `shiraui/paths.py` always appends its own
unique `run-<pid>-<ts>` leaf, so the worst rmtree target is a directory the app
made seconds earlier. Stale `run-*` dirs are swept at startup, because
cancelling kills the child and skips shiradl's own `finally`.

Theming is Fusion + `QPalette` + one QSS `string.Template` with a token dict per
theme (`shiraui/theme.py`). Fusion is mandatory: the `windows11` style routes
buttons, combos, progress bars and scrollbars through the native engine and
ignores QSS. Light/dark uses `QStyleHints.setColorScheme()` (Qt 6.11).

## Fork-specific notes

- `PyQt6` is deliberately **not** in `pyproject.toml` — that file describes the upstream `shiradl` distribution, and keeping it untouched avoids a conflict on every future merge. Install PyQt6 separately.
- `qtawesome` is optional and documented in the README, not `pyproject.toml`. The icon layer falls back to `QStyle.StandardPixmap` and then to Unicode glyphs, and is tested with qtawesome absent.
- `shiradl/` uses tabs; `shira_ui.py` uses 4 spaces. Match the file you're editing.
- `Dl.get_audio_codec` invokes bare `ffprobe` from PATH, ignoring `--ffmpeg-location`.
