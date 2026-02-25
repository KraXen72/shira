import pytest
from inline_snapshot import snapshot
from test_harness import DOWNLOADS_DIR, audio_files, invoke, read_metadata
 
TIMEOUT = 120

def fetch_metadata(url, label):
	final_path = DOWNLOADS_DIR / "metadata" / label
	final_path.mkdir(parents=True, exist_ok=True)
	result = invoke(url, final_path, ["--no-download"])
	assert result.exit_code == 0, result.output
	files = audio_files(final_path)
	assert len(files) > 0, "No audio file written"
	return read_metadata(final_path)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_night_lovell_polozhenie():
	assert fetch_metadata("https://www.youtube.com/watch?v=pVjdMQ_iAh0", "Night Lovell - Polozhenie - YouTube (tiger)") == snapshot(
		[
			{
				"title": "Polozhenie",
				"artist": "Night Lovell",
				"album": "Polozhenie (Single)",
				"albumartist": "Night Lovell",
				"track": 1,
				"tracktotal": 1,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_jreg_2x_speed():
	assert fetch_metadata("https://www.youtube.com/watch?v=gLYWLobR248", "I Watch My YouTube Videos At 2x Speed (tiger)") == snapshot(
		[
			{
				"title": "I Watch My YouTube Videos At 2x Speed",
				"artist": "JREG",
				"album": "I Watch My YouTube Videos At 2x Speed (Single)",
				"albumartist": "JREG",
				"track": 1,
				"tracktotal": 1,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_lund_fck_love_ytmusic():
	assert fetch_metadata("https://music.youtube.com/watch?v=5qdFjGI9948", "Lund - Fck Love (ytmusic)") == snapshot(
		[{"title": "F*ck Love", "artist": "Lund", "album": "F*ck Love", "albumartist": "Lund", "track": 1, "tracktotal": 1}]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_lund_fck_love_yt():
	assert fetch_metadata("https://youtube.com/watch?v=5qdFjGI9948", "Lund - Fck Love (same link, yt)") == snapshot(
		[{"title": "F*ck Love", "artist": "Lund", "album": "F*ck Love", "albumartist": "Lund", "track": 1, "tracktotal": 1}]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_eden_xo():
	assert fetch_metadata("https://music.youtube.com/watch?v=FIrd5KJudrg", "Eden - XO (yt music)") == snapshot(
		[{"title": "XO", "artist": "EDEN", "album": "i think you think too much of me", "albumartist": "EDEN", "track": 6, "tracktotal": 7}]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_tpbon_netflix():
	assert fetch_metadata("https://www.youtube.com/watch?v=aN9_RkCGzGM", "T-P-bon - Netflix (youtube)") == snapshot(
		[
			{
				"title": "Netflix",
				"artist": "『T・Pぼん』予告編",
				"album": "Netflix (Single)",
				"albumartist": "『T・Pぼん』予告編",
				"track": 1,
				"tracktotal": 1,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_daft_punk():
	assert fetch_metadata("https://youtu.be/TCd6PfxOy0Y?feature=shared", "youtu.be (daft punk)") == snapshot(
		[
			{
				"title": "Veridis Quo (Official Audio)",
				"artist": "Daft Punk",
				"album": "Veridis Quo (Official Audio) (Single)",
				"albumartist": "Daft Punk",
				"track": 1,
				"tracktotal": 1,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_virtual_insanity():
	assert fetch_metadata("https://youtu.be/4JkIs37a2JE?feature=shared", "youtu.be (virtual insanity, official video)") == snapshot(
		[
			{
				"title": "Virtual Insanity (Official Video)",
				"artist": "Jamiroquai",
				"album": "Virtual Insanity (Official Video) (Single)",
				"albumartist": "Jamiroquai",
				"track": 1,
				"tracktotal": 1,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_artist_topic():
	assert fetch_metadata("https://www.youtube.com/watch?v=EbjbmvK-BvM", "youtube artist - topic video") == snapshot(
		[
			{
				"title": "Brokendate",
				"artist": "Com Truise",
				"album": "Galactic Melt (10th Anniversary Edition)",
				"albumartist": "Com Truise",
				"track": 7,
				"tracktotal": 15,
			}
		]
	)


@pytest.mark.metadata(pytest.mark.timeout(TIMEOUT))
def test_metadata_music_channel():
	assert fetch_metadata("https://youtu.be/jwIWJIdpNFs?feature=shared", "youtu.be music channel video") == snapshot(
		[{"title": "Born of a Star", "artist": "Izar", "album": "End of My Life", "albumartist": "Izar", "track": 2, "tracktotal": 2}]
	)