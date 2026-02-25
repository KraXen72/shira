import sys
from pathlib import Path

from click.testing import CliRunner
from mediafile import MediaFile

from shiradl.cli import cli

TESTS_DIR = Path(__file__).parent
CONFIG_FILE = TESTS_DIR / "test_config.json"
DOWNLOADS_DIR = TESTS_DIR / "downloads"

# Tracks lines printed to stdout during the current test for ANSI clearing.
_output_line_count = [0]


def _print_invoke_output(text: str) -> None:
	if not text:
		return
	if not text.endswith("\n"):
		text += "\n"
	sys.stdout.write(text)
	sys.stdout.flush()
	_output_line_count[0] += text.count("\n")


def invoke(url: str, final_path: Path, extra_args: list[str] | None = None):
	"""Invoke the shira CLI using the shared test config, with final_path overridden."""
	runner = CliRunner()
	result = runner.invoke(
		cli,
		[url, "--config-location", str(CONFIG_FILE), "--final-path", str(final_path), *(extra_args or [])],
		catch_exceptions=False,
	)
	_print_invoke_output(result.output)
	return result


def audio_files(path: Path) -> list[Path]:
	"""Return sorted list of audio files recursively under path."""
	return sorted(
		f for f in path.rglob("*")
		if f.suffix in {".m4a", ".mp3", ".opus", ".flac"}
	)


def read_metadata(path: Path) -> list[dict]:
	"""Read basic metadata tags from all audio files under path."""
	return [
		{
			"title": mf.title,
			"artist": mf.artist,
			"album": mf.album,
			"albumartist": mf.albumartist,
			"track": mf.track,
			"tracktotal": mf.tracktotal,
		}
		for f in audio_files(path)
		for mf in [MediaFile(f)]
	]
