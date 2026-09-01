"""Validation + argv tests. No QApplication required."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shiraui.argsbuilder import build_args  # noqa: E402
from shiraui.jobspec import JobSpec  # noqa: E402
from shiraui.validation import (  # noqa: E402
	ERROR,
	WARNING,
	clean_urls,
	sample_preview,
	validate_template,
)


def sev(issues, severity):
	return [i for i in issues if i.severity == severity]


# --- templates -------------------------------------------------------------

def test_default_templates_are_clean():
	assert not validate_template("{albumartist}/{album}", "f", "The folder pattern")
	assert not validate_template("{track:02d} {title}", "f", "The file pattern")


def test_unknown_key_is_an_error():
	"""{genre} raises KeyError on every track and shows only as 'Done (N errors)'."""
	issues = validate_template("{genre}/{album}", "f", "The folder pattern")
	errs = sev(issues, ERROR)
	assert errs and "genre" in errs[0].message
	assert "albumartist" in errs[0].message  # tells the user what IS valid


def test_optional_key_warns_but_does_not_block():
	issues = validate_template("{comments}", "f", "The file pattern")
	assert not sev(issues, ERROR)
	assert sev(issues, WARNING)


def test_numeric_format_on_text_key_is_an_error():
	"""{title:02d} raises ValueError at format time."""
	assert sev(validate_template("{title:02d}", "f", "The file pattern"), ERROR)


def test_numeric_format_on_track_is_fine():
	assert not sev(validate_template("{track:02d}", "f", "The file pattern"), ERROR)


def test_empty_template_is_an_error():
	assert sev(validate_template("   ", "f", "The file pattern"), ERROR)


def test_template_with_no_tags_warns_about_collisions():
	issues = validate_template("my music", "f", "The file pattern")
	assert sev(issues, WARNING)


def test_unbalanced_brace_is_reported_not_raised():
	assert sev(validate_template("{album", "f", "The folder pattern"), ERROR)


# --- preview ---------------------------------------------------------------

def test_preview_renders_defaults():
	assert sample_preview("{albumartist}/{album}", "{track:02d} {title}") == (
		"Radiohead \\ In Rainbows \\ 05 Nude.m4a"
	)


def test_preview_degrades_instead_of_raising():
	assert sample_preview("{nope}", "{title}") == "—"


# --- urls ------------------------------------------------------------------

def test_clean_urls_filters_and_dedupes():
	ok, bad = clean_urls(
		"https://music.youtube.com/watch?v=a\n"
		"\n"
		"# a comment\n"
		"  https://soundcloud.com/x/y  \n"
		"not a url\n"
		"https://music.youtube.com/watch?v=a\n"
	)
	assert ok == ["https://music.youtube.com/watch?v=a", "https://soundcloud.com/x/y"]
	assert bad == ["not a url"]


# --- argv ------------------------------------------------------------------

def base_spec(**kw):
	spec = JobSpec(urls=["u"], final_path=Path("C:/Music"), work_dir=Path("C:/work"))
	for k, v in kw.items():
		setattr(spec, k, v)
	return spec


def test_no_config_file_is_always_passed():
	"""Otherwise a `true` in config.json overrides an unticked box."""
	assert "--no-config-file" in build_args(base_spec(), "u")


def test_config_file_opt_in_replaces_the_flag():
	args = build_args(base_spec(use_config_file=True, config_path="C:/c.json"), "u")
	assert "--no-config-file" not in args
	assert "--config-location" in args


def test_log_level_never_carries_user_verbosity():
	"""WARNING would suppress the logger.info progress lines the UI parses."""
	assert build_args(base_spec(), "u")[-1:] or True
	args = build_args(base_spec(), "u")
	assert args[args.index("--log-level") + 1] == "INFO"
	dbg = build_args(base_spec(debug_logging=True), "u")
	assert dbg[dbg.index("--log-level") + 1] == "DEBUG"


def test_work_dir_is_always_the_app_owned_temp_path():
	args = build_args(base_spec(), "u")
	assert args[args.index("--temp-path") + 1] == str(Path("C:/work"))


def test_unticked_flags_emit_nothing():
	args = build_args(base_spec(), "u")
	for flag in ("--overwrite", "--save-cover", "--single-folder",
	             "--use-playlist-name", "--print-exceptions", "--no-download"):
		assert flag not in args


def test_ticked_flags_emit():
	args = build_args(base_spec(overwrite=True, save_cover=True), "u")
	assert "--overwrite" in args and "--save-cover" in args


def test_no_truncate_emits_zero():
	"""shiradl disables truncation for values < 4 (dl.py:46)."""
	args = build_args(base_spec(no_truncate=True), "u")
	assert args[args.index("--truncate") + 1] == "0"


def test_cookies_only_sent_when_enabled_and_set():
	assert "--cookies-location" not in build_args(base_spec(cookies_path="c.txt"), "u")
	args = build_args(base_spec(cookies_enabled=True, cookies_path="c.txt"), "u")
	assert args[args.index("--cookies-location") + 1] == "c.txt"


def test_empty_optional_strings_are_omitted_not_blank():
	"""The old GUI sent --exclude-tags "" and --cover-img "" unconditionally."""
	args = build_args(base_spec(), "u")
	assert "--exclude-tags" not in args
	assert "--cover-img" not in args


def test_url_is_first_positional():
	assert build_args(base_spec(), "https://x/y")[0] == "https://x/y"


def test_url_txt_flag_is_never_emitted():
	"""Link files are read client-side; -u applies to all positionals."""
	args = build_args(base_spec(), "list.txt")
	assert "--url-txt" not in args and "-u" not in args
