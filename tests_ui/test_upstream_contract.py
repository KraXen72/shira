"""Guards the two places this fork couples to upstream shiradl.

Neither coupling is enforced at runtime, and both fail *quietly* when upstream
drifts, which is the dangerous part:

1. `argsbuilder.build_args` emits flag strings. If upstream renames or drops an
   option, Click rejects the argv and every download fails with a usage error.
2. `logparse` matches exact log message text. If upstream rewords a message,
   the progress bar and the completion summary silently stop working while
   downloads carry on fine -- the worst kind of breakage, because it looks
   like the app hung.

These tests introspect the *installed* shiradl rather than a copy of its
option list, so `pip install -e .` after an upstream merge is enough to make
them meaningful. Run them first after any upstream sync.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

shiradl_cli = pytest.importorskip(
	"shiradl.cli", reason="shiradl must be installed: pip install -e ."
)

import click  # noqa: E402

from shiraui.argsbuilder import build_args  # noqa: E402
from shiraui.jobspec import COVER_CROPS, COVER_FORMATS, QUALITY_PRESETS, JobSpec  # noqa: E402
from shiraui.logparse import LogParser  # noqa: E402

CLI = shiradl_cli.cli
PARAMS = {p.name: p for p in CLI.params}
CLI_SOURCE = (Path(shiradl_cli.__file__)).read_text(encoding="utf-8")


def all_option_strings() -> set[str]:
	out: set[str] = set()
	for p in CLI.params:
		out.update(getattr(p, "opts", []) or [])
		out.update(getattr(p, "secondary_opts", []) or [])
	return out


def maximal_spec() -> JobSpec:
	"""A spec that turns on every option, so build_args emits all of them."""
	return JobSpec(
		urls=["https://music.youtube.com/watch?v=x"],
		final_path=Path("C:/Music"),
		work_dir=Path("C:/work"),
		cover_img="C:/art.jpg",
		exclude_tags="lyrics,comments",
		cookies_enabled=True,
		cookies_path="C:/cookies.txt",
		save_cover=True,
		overwrite=True,
		single_folder=True,
		use_playlist_name=True,
		print_exceptions=True,
		no_download=True,
		debug_logging=True,
	)


# --- 1. every flag we emit must exist upstream ------------------------------

def test_every_emitted_flag_exists_in_shiradl():
	emitted = {a for a in build_args(maximal_spec(), "u") if a.startswith("-")}
	unknown = emitted - all_option_strings()
	assert not unknown, (
		f"shiraui emits flags shiradl no longer has: {sorted(unknown)}. "
		f"Reconcile shiraui/argsbuilder.py with shiradl/cli.py's @click.option list."
	)


def test_config_file_opt_in_flag_exists():
	args = build_args(maximal_spec().__class__(
		urls=["u"], final_path=Path("C:/M"), work_dir=Path("C:/w"),
		use_config_file=True, config_path="C:/c.json",
	), "u")
	emitted = {a for a in args if a.startswith("-")}
	assert not emitted - all_option_strings()


def test_flags_we_treat_as_boolean_are_still_boolean():
	"""If upstream turned one into a value option, we would emit a bare flag."""
	for name in ("save_cover", "overwrite", "single_folder",
	             "use_playlist_name", "print_exceptions", "no_config_file",
	             "no_download"):
		assert name in PARAMS, f"shiradl no longer has --{name.replace('_', '-')}"
		assert PARAMS[name].is_flag, f"{name} is no longer a boolean flag upstream"


def test_value_options_still_take_values():
	for name in ("final_path", "temp_path", "itag", "cover_size",
	             "cover_format", "cover_quality", "cover_crop",
	             "template_folder", "template_file", "truncate",
	             "log_level", "ffmpeg_location", "cookies_location"):
		assert name in PARAMS, f"shiradl no longer has {name}"
		assert not PARAMS[name].is_flag, f"{name} became a flag upstream"


def test_urls_still_accepts_many():
	"""The queue submits one URL per process, but relies on it being variadic."""
	assert isinstance(PARAMS["urls"], click.Argument)
	assert PARAMS["urls"].nargs == -1


# --- 2. our dropdown values must still be accepted --------------------------

@pytest.mark.parametrize("name,values", [
	("cover_format", [v for _, v in COVER_FORMATS]),
	("cover_crop", [v for _, v in COVER_CROPS]),
])
def test_dropdown_values_are_valid_choices(name, values):
	choices = set(PARAMS[name].type.choices)
	assert set(values) <= choices, (
		f"shiraui offers {sorted(set(values) - choices)} for --{name.replace('_','-')}, "
		f"which shiradl no longer accepts (valid: {sorted(choices)})"
	)


def test_log_levels_we_send_are_valid():
	choices = set(PARAMS["log_level"].type.choices)
	assert {"INFO", "DEBUG"} <= choices


def test_quality_presets_are_plausible_format_selectors():
	"""--itag is a free-form yt-dlp selector, so only sanity-check it."""
	assert not PARAMS["itag"].is_flag
	assert all(v and not v.startswith("-") for _, v in QUALITY_PRESETS)


def test_cover_ranges_still_match_the_spinbox_limits():
	assert PARAMS["cover_size"].type.min == 0
	assert PARAMS["cover_size"].type.max == 16383
	assert PARAMS["cover_quality"].type.min == 1
	assert PARAMS["cover_quality"].type.max == 100


# --- 3. the log messages logparse depends on --------------------------------

@pytest.mark.parametrize("fragment,why", [
	('format="[%(levelname)-8s %(asctime)s] %(message)s"',
	 "LogParser.LINE_RE depends on this exact logging format"),
	("(track {j + 1}/{len(url)} from URL ",
	 "TRACK_RE drives the progress bar and the track counter"),
	('Done ({error_count} error(s))',
	 "RUN_DONE is how completion is detected; the exit code is always 0"),
	('Saved to "',
	 "TRACK_SAVED advances the progress bar"),
	("File already exists at final location, skipping",
	 "TRACK_SKIPPED advances the progress bar"),
	('FFmpeg not found at "',
	 "FATAL turns a silent no-op into an actionable message"),
])
def test_log_message_shapes_are_unchanged(fragment, why):
	assert fragment in CLI_SOURCE, (
		f"shiradl changed a log message shiraui parses.\n"
		f"  missing: {fragment!r}\n"
		f"  breaks:  {why}\n"
		f"  fix:     update the regexes in shiraui/logparse.py"
	)


def test_parser_handles_a_line_built_the_way_shiradl_builds_it():
	"""End-to-end check of the format string against the parser."""
	import logging

	rec = logging.LogRecord("shiradl.cli", logging.INFO, __file__, 1,
	                        'Downloading "S" (track 2/7 from URL 1/3)', None, None)
	fmt = logging.Formatter(
		"[%(levelname)-8s %(asctime)s] %(message)s", datefmt="%H:%M:%S"
	)
	ev = LogParser().feed(fmt.format(rec))
	assert ev is not None and ev.data.get("track") == 2 and ev.data.get("tracks") == 7


def test_logging_still_goes_to_stderr_not_stdout():
	"""The runner reads both channels, but a silent switch is worth knowing."""
	assert "logging.basicConfig(" in CLI_SOURCE
	assert "stream=" not in CLI_SOURCE.split("logging.basicConfig(")[1].split(")")[0]


# --- 4. the safety assumption ----------------------------------------------

def test_temp_path_is_still_the_directory_shiradl_deletes():
	"""paths.py hands over an app-owned dir precisely because of this."""
	dl_source = (Path(shiradl_cli.__file__).parent / "dl.py").read_text(encoding="utf-8")
	assert "shutil.rmtree(self.temp_path)" in dl_source, (
		"shiradl's cleanup changed. Re-check shiraui/paths.py: the work "
		"directory is app-owned and uniquely named on the assumption that "
		"--temp-path gets recursively deleted after every track."
	)
