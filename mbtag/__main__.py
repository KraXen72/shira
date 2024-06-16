import json
import os

import click
from mediafile import MediaFile

from mbtag.musicbrainz import MBSong
from shiradl.util import pprint, progprint

# Define supported extensions list using the keys from the TYPES dictionary
SONG_EXTS = ["mp3", "aac", "alac", "ogg", "opus", "flac", "ape", "wv", "mpc", "asf", "aiff", "dsf", "wav"]
MBID_TAG_KEYS = ["mb_releasetrackid", "mb_releasegroupid", "mb_artistid", "mb_albumartistid"]


# Function to check if a file is a supported song file
def is_supported_song_file(filename):
	ext = os.path.splitext(filename)[1][1:]
	if ext.lower() in SONG_EXTS:
		return True
	try:
		MediaFile(filename)
		return True
	except:
		return False


def process_directory(directory_or_file: click.Path, fetch_complete: bool, fetch_partial: bool, dry_run: bool, debug: bool):
	if not os.path.exists(str(directory_or_file)):
		print(f"[error]: Path '{directory_or_file}' does not exist.")
		return
	if os.path.isfile(str(directory_or_file)):
		process_song(str(directory_or_file), 0, 1, fetch_complete, fetch_partial, dry_run, debug)
		print()
		return
	for root, _, files in os.walk(str(directory_or_file)):
		for i in range(len(files)):
			f = files[i]
			filepath = os.path.join(root, f)
			if not is_supported_song_file(filepath):
				continue
			try:
				process_song(filepath, i, len(files), fetch_complete, fetch_partial, dry_run, debug)
				# print()
			except Exception as e:
				print(f"Error processing song '{filepath}':")
				print(e)
	print()


def has_all_mbid_tags(handle: MediaFile):
	"""these files are skipped alltogether"""
	handle_dict = handle.as_dict()
	return all(handle_dict.get(key) is not None for key in MBID_TAG_KEYS)


def no_of_mbid_tags(handle: MediaFile):
	handle_dict = handle.as_dict()
	return sum([handle_dict.get(key) is not None for key in MBID_TAG_KEYS])


def process_song(filepath: str, ind: int, total: int, fetch_complete: bool, fetch_partial: bool, dry_run=False, debug=False,):
	handle = MediaFile(filepath)
	has_all = has_all_mbid_tags(handle)
	has_some = no_of_mbid_tags(handle)
	status = f"[song] {filepath}, has_all: {has_all}, has_some: {has_some}"
	progprint(ind, total, message=status)
	# pprint(handle.as_dict(), True)

	# by default, partials and completes are not fetched
	continue_partials = has_some == 0 or (has_some > 0 and (fetch_partial or fetch_complete))
	continue_complete = not has_all or (has_all and fetch_complete)
	# print(f"continue_partials: {continue_partials}, continue_complete: {continue_complete}  ")

	if not (continue_partials and continue_complete):
		msg = f"[skipped] check args for fetching complete or partial songs. c:{int(not continue_complete)}, p:{int(not continue_partials)}  "
		# progprint(ind, total, message=msg)
		print(msg)
		return 
	if handle.title is None or handle.artist is None:
		msg = "[skipped] 'title' and 'artist' tags are required to search MusicBrainz  "
		# progprint(ind, total, message=msg)
		print(msg)
		return 
	# The fallback likely won't work but i cba to fix it properly for now
	formb_album = str(handle.album) if handle.album is not None else f"{handle.title} (Single)"

	mb = MBSong(title=str(handle.title), artist=str(handle.artist), album=formb_album, debug=debug)
	mb.fetch_song()

	if debug:
		pprint(mb.get_mbid_tags())
	if dry_run:
		msg = "[skipped] didn't write due to --dry-run  "
		# progprint(ind, total, message=msg)
		print(msg)
		print(mb.get_mb_tags())
		print(json.dumps(mb.get_mbid_tags(), indent=2))
		return 
	else:
		for [k, v] in mb.get_mbid_tags().items():
			setattr(handle, k, v)
		handle.save()
		ptags = mb.get_mb_tags()
		msg = ""
		if ptags is not None:
			msg = f"[ok] written IDs for result: {ptags['artist']} - {ptags['title']} (on {ptags['album']})  "
		else:
			msg = "[ok] written!  "
		print(msg)
		# progprint(ind, total, message=msg)

@click.command()
@click.argument("input_path", type=click.Path(exists=True, file_okay=True, resolve_path=True))
@click.option("--fetch-complete", "-c", is_flag=True, help=f"Fetch from MusicBrainz even if has {", ".join(MBID_TAG_KEYS)} present.")
@click.option("--fetch-partial", "-p", is_flag=True, help="Fetch from MusicBrainz even if has some mb_* tags present.")
@click.option("--dry-run", "-d", is_flag=True, help="Don't write to any files, just print out the mb_* tags")
@click.option("--debug", "-g", is_flag=True, help="Prints out extra information for debugging. Does not imply --dry-run.")
def mbtag_cli(input_path: click.Path, fetch_complete=False, fetch_partial=False, dry_run=False, debug=False):
	process_directory(input_path, fetch_complete, fetch_partial, dry_run, debug)

if __name__ == "__main__":
	mbtag_cli()
