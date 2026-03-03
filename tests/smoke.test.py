import pytest
from inline_snapshot import snapshot
from test_harness import DOWNLOADS_DIR, MB_TAGS, audio_files, invoke, mediafile_dict

SIZE_TOLERANCE = 512_000


def grab_smoke(url: str, label: "str"):
	fp = DOWNLOADS_DIR / label
	res = invoke(url, fp, ["--exclude-tags", ",".join(MB_TAGS)])
	assert res.exit_code == 0

	dlfiles = audio_files(fp)
	assert len(dlfiles) > 0

	meta_dict = mediafile_dict(dlfiles[0])
	size = dlfiles[0].stat().st_size

	return meta_dict, size


@pytest.mark.smoke
@pytest.mark.timeout(120)
def test1():
	"""YTM - Lesfm - Inspiring Cinematic"""
	meta_dict, size = grab_smoke("https://music.youtube.com/watch?v=HdX2COsY2Xk", "smoke1")
	# print(json.dumps(meta_dict, indent=4, sort_keys=True))

	assert size == pytest.approx(snapshot(3680042), SIZE_TOLERANCE, True)
	assert meta_dict == snapshot(
		{
			"title": "Inspiring Cinematic",
			"artist": "Lesfm",
			"album": "Inspiring Cinematic",
			"track": 1,
			"tracktotal": 1,
			"disc": 1,
			"disctotal": 1,
			"comments": "https://music.youtube.com/watch?v=HdX2COsY2Xk",
			"albumartist": "Lesfm",
			"year": 2021,
			"month": 1,
			"day": 26,
		}
	)


@pytest.mark.smoke
@pytest.mark.timeout(120)
def test2():
	"""YTM - Haterade - Go Off"""
	meta_dict, size = grab_smoke("https://music.youtube.com/watch?v=8YwKlPH93Ps", "smoke2")
	assert size == pytest.approx(snapshot(3104363), SIZE_TOLERANCE, True)
	assert meta_dict == snapshot(
		{
			"title": "Go Off",
			"artist": "Haterade",
			"album": "Go Off (Single)",
			"track": 1,
			"tracktotal": 1,
			"disc": 1,
			"disctotal": 1,
			"comments": "https://www.youtube.com/watch?v=8YwKlPH93Ps",
			"albumartist": "Haterade",
			"year": 2022,
			"month": 6,
			"day": 23,
		}
	)


@pytest.mark.smoke
@pytest.mark.timeout(120)
def test3():
	"""YT - Andy Leech x 4lienetic - Nightfall"""
	meta_dict, size = grab_smoke("https://www.youtube.com/watch?v=X0-AvRA7kB0", "smoke3")
	assert size == pytest.approx(snapshot(4754659), SIZE_TOLERANCE, True)
	assert meta_dict == snapshot(
		{
			"title": "Nightfall",
			"artist": "Andy Leech x 4lienetic",
			"album": "Nightfall (Single)",
			"track": 1,
			"tracktotal": 1,
			"disc": 1,
			"disctotal": 1,
			"comments": "https://www.youtube.com/watch?v=X0-AvRA7kB0",
			"albumartist": "Andy Leech x 4lienetic",
			"year": 2018,
			"month": 7,
			"day": 20,
		}
	)
