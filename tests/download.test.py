import pytest
from test_harness import DOWNLOADS_DIR, audio_files, invoke

LINKS = [
	"https://www.youtube.com/watch?v=pVjdMQ_iAh0",
	"https://www.youtube.com/watch?v=gLYWLobR248",
	"https://music.youtube.com/watch?v=5qdFjGI9948",
	"https://youtube.com/watch?v=5qdFjGI9948",
	"https://music.youtube.com/watch?v=FIrd5KJudrg",
	"https://www.youtube.com/watch?v=aN9_RkCGzGM",
	# "https://soundcloud.com/alognaibiman/sets/kokeshi-anime-openings",
	"https://youtu.be/TCd6PfxOy0Y?feature=shared",
	"https://youtu.be/4JkIs37a2JE?feature=shared",
	"https://www.youtube.com/watch?v=EbjbmvK-BvM",
	"https://youtu.be/jwIWJIdpNFs?feature=shared",
]
LABELS = [
	"Night Lovell - Polozhenie - YouTube (tiger)",
	"I Watch My YouTube Videos At 2x Speed (tiger)",
	"Lund - Fck Love (ytmusic)",
	"Lund - Fck Love (same link, yt)",
	"Eden - XO (yt music)",
	"T-P-bon - Netflix (youtube)",
	# "kokeshi-anime-openings (soundcloud set)",
	"youtu.be (daft punk)",
	"youtu.be (virtual insanity, official video)",
	"youtube artist - topic video",
	"youtu.be music channel video",
]

@pytest.mark.integration
@pytest.mark.download
@pytest.mark.timeout(120)
@pytest.mark.parametrize("url,label", zip(LINKS, LABELS), ids=LABELS)
def test_download(url, label):
	final_path = DOWNLOADS_DIR / "download" / label
	final_path.mkdir(parents=True, exist_ok=True)

	result = invoke(url, final_path)
	assert result.exit_code == 0, result.output

	files = audio_files(final_path)
	assert len(files) > 0, "No audio file written"
	for f in files:
		assert f.stat().st_size > 50_000, f"Suspiciously small: {f.name}"
