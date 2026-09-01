"""JobSpec -> argv for `python -m shiradl`.

THIS IS THE COUPLING POINT TO UPSTREAM. Every flag emitted here must exist as
a @click.option in shiradl/cli.py. Nothing enforces that at runtime, so when
merging a new upstream version, diff this module against cli.py's option list.
Verified against shiradl 1.8.5.

Two rules that are not obvious:

* ``--no-config-file`` is always passed. Click flags are one-way -- there is
  no ``--no-overwrite`` -- so an unticked checkbox emits nothing, and a
  ``true`` in ~/.shiradl/config.json would win and be unreachable from the UI.
* ``--log-level`` never carries the user's display preference. The progress
  lines the UI parses (``Downloading "..." (track j/N from URL i/M)``,
  ``Done (N error(s))``) are logger.info, so passing WARNING would silently
  delete the progress bar and the completion summary. Verbosity is filtered
  client-side instead.
"""

from __future__ import annotations

from .jobspec import JobSpec


def build_args(spec: JobSpec, url: str) -> list[str]:
	"""Build argv for a single URL.

	One process per URL is deliberate: ``Dl.soundcloud`` latches True and is
	never reset (shiradl/dl.py:85), and all URLs in one invocation share a
	single ``Dl``. A mixed YouTube + SoundCloud batch would therefore switch
	later tracks to mp3 and skip the YouTube Music lookup.
	"""
	args: list[str] = [url]

	args += ["--final-path", str(spec.final_path)]
	args += ["--temp-path", str(spec.work_dir)]

	if spec.use_config_file and spec.config_path:
		args += ["--config-location", spec.config_path]
	else:
		args.append("--no-config-file")

	args += ["--log-level", "DEBUG" if spec.debug_logging else "INFO"]

	args += ["--ffmpeg-location", spec.ffmpeg_location or "ffmpeg"]
	args += ["--itag", spec.itag or "140"]
	args += ["--cover-size", str(spec.cover_size)]
	args += ["--cover-format", spec.cover_format]
	args += ["--cover-quality", str(spec.cover_quality)]
	args += ["--cover-crop", spec.cover_crop]
	if spec.cover_img.strip():
		args += ["--cover-img", spec.cover_img.strip()]

	args += ["--template-folder", spec.template_folder]
	args += ["--template-file", spec.template_file]
	if spec.exclude_tags.strip():
		args += ["--exclude-tags", spec.exclude_tags.strip()]

	# `truncate < 4` is how shiradl disables truncation (dl.py:46). The UI
	# reaches that branch through an explicit checkbox rather than by letting
	# someone type 2 and silently get a different behaviour.
	args += ["--truncate", "0" if spec.no_truncate else str(spec.truncate)]

	if spec.cookies_enabled and spec.cookies_path.strip():
		args += ["--cookies-location", spec.cookies_path.strip()]

	if spec.save_cover:
		args.append("--save-cover")
	if spec.overwrite:
		args.append("--overwrite")
	if spec.single_folder:
		args.append("--single-folder")
	if spec.use_playlist_name:
		args.append("--use-playlist-name")
	if spec.print_exceptions:
		args.append("--print-exceptions")
	# Writes a 0.1s silent stub, tags it, and moves it into the library looking
	# like a real track. Dev-only; the UI gates it behind SHIRA_UI_DEV=1.
	if spec.no_download:
		args.append("--no-download")

	return args


def preview_command(spec: JobSpec, url: str) -> str:
	"""Human-copyable equivalent command, for the 'Copy command' button."""
	def q(s: str) -> str:
		return f'"{s}"' if " " in s else s

	return "python -m shiradl " + " ".join(q(a) for a in build_args(spec, url))
