import os

import click
from mediafile import MediaFile

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


# Function to walk through directories recursively and process files
def process_directory(directory):
	for root, _, files in os.walk(directory):
		for f in files:
			filepath = os.path.join(root, f)
			if not is_supported_song_file(filepath):
				continue
			try:
				process_song(filepath)
			except Exception as e:
				print(f"Error processing song '{filepath}':")
				print(e)

def has_all_mbid_tags(handle: MediaFile):
	"""these files are skipped alltogether"""
	handle_dict = handle.as_dict()
	return all(handle_dict.get(key) is not None for key in MBID_TAG_KEYS)

def no_of_mbid_tags(handle: MediaFile):
	handle_dict = handle.as_dict()
	return len([handle_dict.get(key) is not None for key in MBID_TAG_KEYS])
	
def process_song(filepath: str):
	handle = MediaFile(filepath)
	has_all = has_all_mbid_tags(handle)
	has_some = no_of_mbid_tags(handle)
	print(f"{filepath}, has_all: {has_all}, has_some: {has_some}")
	pprint(handle.as_dict(), True)
	# print(f"Title: {handle.title}, Artist: {handle.artist}, Album: {handle.album}. has_all: {has_all}")

# CLI command
@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, resolve_path=True))
def main(directory):
	process_directory(directory)


if __name__ == "__main__":
	main()