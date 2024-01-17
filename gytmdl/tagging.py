from __future__ import annotations

import functools
from pathlib import Path

import requests
from mutagen.mp4 import MP4, MP4Cover
from typing_extensions import NotRequired, TypedDict  # noqa: UP035


class Tags(TypedDict):
	title: str
	album: str
	artist: str
	album_artist: str
	track: int
	track_total: int
	release_year: str
	release_date: str
	cover_url: str
	rating: NotRequired[int]
	comment: NotRequired[str]
	lyrics: NotRequired[str]
		
MP4_TAGS_MAP = {
	"album": "\xa9alb",
	"album_artist": "aART",
	"artist": "\xa9ART",
	"comment": "\xa9cmt",
	"lyrics": "\xa9lyr",
	"media_type": "stik",
	"rating": "rtng",
	"release_date": "\xa9day",
	"title": "\xa9nam",

	# see https://github.com/OxygenCobalt/Auxio/wiki/Supported-Metadata
	# see https://github.com/metabrainz/picard/blob/master/picard/formats/mp4.py#L115
	"track_mbid": "----:com.apple.iTunes:MusicBrainz Release Track Id",
	"album_mbid": "----:com.apple.iTunes:MusicBrainz Release Group Id",
	"artist_mbid": "----:com.apple.iTunes:MusicBrainz Artist Id",
	"album_artist_mbid": "----:com.apple.iTunes:MusicBrainz Album Artist Id",
}


def tagger_mp4(tags: Tags, fixed_location: Path, exclude_tags: list[str], cover_format: str):
	mp4_tags = {}
	for k, v in MP4_TAGS_MAP.items():
		if k not in exclude_tags and tags.get(k) is not None:
			mp4_tags[v] = [tags[k]]
	
	if not {"track", "track_total"} & set(exclude_tags):
		mp4_tags["trkn"] = [[0, 0]]
	if "cover" not in exclude_tags:
		mp4_tags["covr"] = [
			MP4Cover(get_cover(tags["cover_url"]), imageformat=MP4Cover.FORMAT_JPEG if cover_format == "jpg" else MP4Cover.FORMAT_PNG)
		]
	if "track" not in exclude_tags:
		mp4_tags["trkn"][0][0] = tags["track"]
	if "track_total" not in exclude_tags:
		mp4_tags["trkn"][0][1] = tags["track_total"]

	mp4 = MP4(fixed_location)
	mp4.clear()
	mp4.update(mp4_tags)
	mp4.save()

@functools.lru_cache
def get_cover(url):
	return requests.get(url).content