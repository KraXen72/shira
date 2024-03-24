import os

import click
from mediafile import MediaFile

from mbtag.musicbrainz import MBSong
from shiradl.util import pprint

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


def process_directory(directory: click.Path, fetch_complete: bool, fetch_partial: bool):
	for root, _, files in os.walk(str(directory)):
		for f in files:
			filepath = os.path.join(root, f)
			if not is_supported_song_file(filepath):
				continue
			try:
				process_song(filepath, fetch_complete, fetch_partial)
			except Exception as e:
				print(f"Error processing song '{filepath}':")
				print(e)

def has_all_mbid_tags(handle: MediaFile):
	"""these files are skipped alltogether"""
	handle_dict = handle.as_dict()
	return all(handle_dict.get(key) is not None for key in MBID_TAG_KEYS)

def no_of_mbid_tags(handle: MediaFile):
	handle_dict = handle.as_dict()
	return sum([handle_dict.get(key) is not None for key in MBID_TAG_KEYS])
	
def process_song(filepath: str, fetch_complete: bool, fetch_partial: bool):
	handle = MediaFile(filepath)
	has_all = has_all_mbid_tags(handle)
	has_some = no_of_mbid_tags(handle)
	print(f"{filepath}, has_all: {has_all}, has_some: {has_some}")
	pprint(handle.as_dict(), True)
	if (has_all and (not fetch_complete)) or (has_some and (not fetch_partial)):
		print("[skipping]: check args for fetching all or partial songs")
		return
	if handle.title is None or handle.artist is None:
		print("[skipping]: 'title' and 'artist' tags are required to search MusicBrainz")
		return
	# The fallback likely won't work but i cba to fix it properly for now
	formb_album = str(handle.album) if handle.album is not None else f"{handle.title} (Single)"

	mb = MBSong(title=str(handle.title), artist=str(handle.artist), album=formb_album, debug=True)
	mb.fetch_song()

	pprint(mb.get_mbid_tags())
	

	# TODO apply tags
	# for key, tag in mb.get_mbid_tags().items():
	# 	if tag is not None:
	# 		if skip_encode is False:
	# 			tags[key] =  [ t.encode("utf-8") for t in tag ] if isinstance(tag, list) else tag.encode("utf-8")
	# 		else:
	# 			tags[key] = tag

	# print(f"Title: {handle.title}, Artist: {handle.artist}, Album: {handle.album}. has_all: {has_all}")

# TODO add suport for file_okay

@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--fetch-complete", "-c", is_flag=True, help=f"Fetch from MusicBrainz even if has {", ".join(MBID_TAG_KEYS)} present.")
@click.option("--fetch-partial", "-p", is_flag=True, help="Fetch from MusicBrainz even if has some mb_* tags present.")
def mbtag_cli(directory: click.Path, fetch_complete = False, fetch_partial = False):
	process_directory(directory, fetch_complete, fetch_partial)

if __name__ == "__main__":
	mbtag_cli()
