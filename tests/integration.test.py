from pathlib import Path

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot
from mediafile import MediaFile

from shiradl.cli import cli

LINKS = [
	"https://www.youtube.com/watch?v=pVjdMQ_iAh0",
	"https://www.youtube.com/watch?v=gLYWLobR248",
	"https://music.youtube.com/watch?v=5qdFjGI9948",
	"https://youtube.com/watch?v=5qdFjGI9948",
	"https://music.youtube.com/watch?v=FIrd5KJudrg",
	"https://www.youtube.com/watch?v=aN9_RkCGzGM",
	"https://soundcloud.com/alognaibiman/sets/kokeshi-anime-openings",
	"https://youtu.be/TCd6PfxOy0Y?feature=shared",
	"https://youtu.be/4JkIs37a2JE?feature=shared",
	"https://www.youtube.com/watch?v=EbjbmvK-BvM",
	"https://youtu.be/jwIWJIdpNFs?feature=shared"
]
LABELS = [
	"Night Lovell - Polozhenie - YouTube (tiger)",
	"I Watch My YouTube Videos At 2x Speed (tiger)",
	"Lund - Fck Love (ytmusic)",
	"Lund - Fck Love (same link, yt)",
	"Eden - XO (yt music)",
	"T-P-bon - Netflix (youtube)",
	"kokeshi-anime-openings (soundcloud set)",
	"youtu.be (daft punk)",
	"youtu.be (virtual insanity, official video)",
	"youtube artist - topic video",
	"youtu.be music channel video"
]


def _invoke(url: str, tmp_path: Path, extra_args: list[str]):
	runner = CliRunner()
	return runner.invoke(
		cli,
		[url, "--final-path", str(tmp_path), "--no-config-file", *extra_args],
		catch_exceptions=False,
	)


def _audio_files(tmp_path: Path) -> list[Path]:
	return sorted(
		f for f in tmp_path.rglob("*")
		if f.suffix in {".m4a", ".mp3", ".opus", ".flac"}
	)


@pytest.mark.integration
@pytest.mark.timeout(120)
@pytest.mark.parametrize("url", LINKS, ids=LABELS)
def test_metadata(url, tmp_path):
	result = _invoke(url, tmp_path, ["--no-download"])
	assert result.exit_code == 0, result.output

	audio_files = _audio_files(tmp_path)
	assert len(audio_files) > 0, "No audio file written"

	metadata = []
	for f in audio_files:
		mf = MediaFile(f)
		metadata.append({
			"title": mf.title,
			"artist": mf.artist,
			"album": mf.album,
			"albumartist": mf.albumartist,
			"track": mf.track,
			"tracktotal": mf.tracktotal,
		})
	assert metadata == snapshot()


@pytest.mark.integration
@pytest.mark.download
@pytest.mark.timeout(120)
@pytest.mark.parametrize("url", LINKS, ids=LABELS)
def test_download(url, tmp_path):
	result = _invoke(url, tmp_path, [])
	assert result.exit_code == 0, result.output

	audio_files = _audio_files(tmp_path)
	assert len(audio_files) > 0, "No audio file written"
	for f in audio_files:
		assert f.stat().st_size > 50_000, f"Suspiciously small: {f.name}"
