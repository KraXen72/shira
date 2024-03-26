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


def process_directory(directory: click.Path, fetch_complete: bool, fetch_partial: bool, dry_run: bool, debug: bool):
	for root, _, files in os.walk(str(directory)):
		for i in range(len(files)):
			f = files[i]
			filepath = os.path.join(root, f)
			if not is_supported_song_file(filepath):
				continue
			try:
				process_song(filepath, i+1, len(files), fetch_complete, fetch_partial, dry_run, debug)
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
	# status = f"[song] {filepath}, has_all: {has_all}, has_some: {has_some}"
	# progprint(ind, total, message=status)
	# pprint(handle.as_dict(), True)

	if has_some != 0 and (not (fetch_complete and has_all) and not (fetch_partial and has_some > 0)):
		progprint(ind, total, message="[skipping]: check args for fetching all or partial songs")
		return 
	if handle.title is None or handle.artist is None:
		progprint(ind, total, message="[skipping]: 'title' and 'artist' tags are required to search MusicBrainz")
		return 
	# The fallback likely won't work but i cba to fix it properly for now
	formb_album = str(handle.album) if handle.album is not None else f"{handle.title} (Single)"

	mb = MBSong(title=str(handle.title), artist=str(handle.artist), album=formb_album, debug=debug)
	mb.fetch_song()

	if debug:
		pprint(mb.get_mbid_tags())
	if dry_run:
		progprint(ind, total, message="[dry-run] skipping writing...")
		return 
	else:
		for [k, v] in mb.get_mbid_tags().items():
			setattr(handle, k, v)
		handle.save()
		ptags = mb.get_mb_tags()
		if ptags is not None:
			progprint(ind, total, message=f"[ok] written IDs for result: {ptags['artist']} - {ptags['title']} (on {ptags['album']})")
		else:
			progprint(ind, total, message="[ok] written!")


# TODO add suport for file_okay

@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--fetch-complete", "-c", is_flag=True, help=f"Fetch from MusicBrainz even if has {", ".join(MBID_TAG_KEYS)} present.")
@click.option("--fetch-partial", "-p", is_flag=True, help="Fetch from MusicBrainz even if has some mb_* tags present.")
@click.option("--dry-run", "-d", is_flag=True, help="Don't write to any files, just print out the mb_* tags")
@click.option("--debug", "-g", is_flag=True, help="Prints out extra information for debugging. Does not imply --dry-run.")
def mbtag_cli(directory: click.Path, fetch_complete=False, fetch_partial=False, dry_run=False, debug=False):
	process_directory(directory, fetch_complete, fetch_partial, dry_run, debug)


if __name__ == "__main__":
	mbtag_cli()
