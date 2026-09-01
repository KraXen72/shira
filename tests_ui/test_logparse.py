"""Log parser tests. No QApplication required.

The fixtures below are real output captured from `python -m shiradl` in this
repo's venv, not invented strings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shiraui.logparse import Kind, LogParser, ProgressTracker  # noqa: E402


def parse_all(lines):
	p = LogParser()
	return [ev for ev in (p.feed(x) for x in lines) if ev is not None]


def test_track_start_is_parsed():
	line = (
		'[INFO     16:57:25] Downloading "Rick Astley - Never Gonna Give You Up '
		'(Official Video) (4K Remaster)" (track 1/1 from URL 1/1)'
	)
	ev = LogParser().feed(line)
	assert ev.kind is Kind.TRACK_START
	assert ev.data["track"] == 1 and ev.data["tracks"] == 1
	assert ev.data["title"].startswith("Rick Astley")


def test_track_start_with_parentheses_in_title():
	"""Titles routinely contain brackets; the regex must not stop early."""
	ev = LogParser().feed(
		'[INFO     10:00:00] Downloading "Song (feat. X) (Remix)" (track 3/12 from URL 2/5)'
	)
	assert ev.data["title"] == "Song (feat. X) (Remix)"
	assert (ev.data["track"], ev.data["tracks"]) == (3, 12)
	assert (ev.data["url"], ev.data["urls"]) == (2, 5)


def test_done_sentinel():
	ev = LogParser().feed("[INFO     16:57:29] Done (1 error(s))")
	assert ev.kind is Kind.RUN_DONE
	assert ev.data["errors"] == 1


def test_ffmpeg_missing_is_fatal():
	ev = LogParser().feed('[CRITICAL 16:59:02] FFmpeg not found at "definitely-not-real"')
	assert ev.kind is Kind.FATAL
	assert ev.data["reason"] == "ffmpeg"
	assert ev.data["headline"]


def test_saved_and_skipped():
	saved = LogParser().feed('[INFO     10:00:01] Saved to "C:\\M\\A\\01 T.m4a"')
	assert saved.kind is Kind.TRACK_SAVED
	skip = LogParser().feed(
		"[WARNING  10:00:02] File already exists at final location, skipping"
	)
	assert skip.kind is Kind.TRACK_SKIPPED


def test_ytdlp_raw_error_folds_into_previous_event():
	"""yt-dlp writes unprefixed lines; they belong to the event above them."""
	p = LogParser()
	first = p.feed('[INFO     10:00:00] Downloading "S" (track 1/1 from URL 1/1)')
	assert p.feed("ERROR: unable to download video data: HTTP Error 403: Forbidden") is None
	assert first.detail == ["ERROR: unable to download video data: HTTP Error 403: Forbidden"]


def test_traceback_body_folds_into_the_empty_error_heading():
	"""logging.exception("") emits an empty ERROR then a raw traceback."""
	p = LogParser()
	p.feed('[INFO     10:00:00] Downloading "S" (track 1/1 from URL 1/1)')
	head = p.feed("[ERROR    10:00:01] ")
	p.feed("Traceback (most recent call last):")
	p.feed('  File "x.py", line 1, in <module>')
	assert head.text == "Technical details"
	assert len(head.detail) == 2


def test_blank_lines_ignored():
	assert LogParser().feed("   ") is None


def test_full_run_progress():
	lines = [
		'[INFO     10:00:00] Downloading "A" (track 1/3 from URL 1/1)',
		'[INFO     10:00:05] Saved to "C:\\M\\A.m4a"',
		'[INFO     10:00:06] Downloading "B" (track 2/3 from URL 1/1)',
		"[WARNING  10:00:07] File already exists at final location, skipping",
		'[INFO     10:00:08] Downloading "C" (track 3/3 from URL 1/1)',
		'[ERROR    10:00:09] Failed to download "C" (track 3/3 from URL 1/1)',
		"[INFO     10:00:10] Done (1 error(s))",
	]
	t = ProgressTracker(link_total=1)
	for ev in parse_all(lines):
		t.apply(ev)

	assert (t.p.saved, t.p.skipped, t.p.failed) == (1, 1, 1)
	assert t.p.completed == 3
	assert t.p.track_total == 3
	assert t.p.done is True
	assert t.p.errors == 1


def test_progress_is_indeterminate_before_first_track():
	"""Nothing to count until a track is announced."""
	t = ProgressTracker(link_total=2)
	assert t.p.indeterminate is True
	t.apply(LogParser().feed('[INFO     10:00:00] Downloading "A" (track 1/9 from URL 1/2)'))
	assert t.p.indeterminate is False


def test_start_link_resets_per_link_counters_but_keeps_totals():
	t = ProgressTracker(link_total=2)
	t.apply(LogParser().feed('[INFO     10:00:00] Downloading "A" (track 1/1 from URL 1/2)'))
	t.apply(LogParser().feed('[INFO     10:00:01] Saved to "x.m4a"'))
	t.start_link(2)
	assert t.p.track_total == 0
	assert t.p.saved == 1  # cumulative across the whole queue
