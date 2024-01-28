from __future__ import annotations

import functools
from io import BytesIO
from pathlib import Path

import requests
from mutagen.id3 import ID3, Frames
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image, ImageOps
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
	cover_1x1: NotRequired[bytes]
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

	# doesen't include track (trkn) or disc (disk)
}

# this is for ID3v2.3
MP3_TAGS_MAP = {
	"album": "TALB",
	"album_artist": "TPE2",
	"artist": "TPE1",
	"comment": "COMM",
	"lyics": "USLT",
	"media_type": "TMED",
	# "rating": "" # no support for rating in mp3 for now
	"release_date": "TDRL",
	"title": "TIT2",

	"track_mbid": "TXXX:MusicBrainz Release Track Id",
	"album_mbid": "TXXX:MusicBrainz Release Group Id",
	"artist_mbid": "TXXX:MusicBrainz Artist Id",
	"album_artist_mbid": "TXXX:MusicBrainz Album Artist Id"

	# doesen't include track (TRCK) and disc (TPOS, TSST)
}

def tagger_mp3(tags: Tags, fixed_location: Path, exclude_tags: list[str], cover_format: str):
	# this mp3 tagger is not perfect, it raises 'Invalid ID3v2.4 frame-header-ID' and 'id3v2.4 header has empty tag type='
	# warnings in https://audio-tag-analyzer.netlify.app. both mutagen and eyed3 do this though.
	mp3 = ID3(fixed_location)
	mp3.clear()

	for k, v in MP3_TAGS_MAP.items():
		if k not in exclude_tags and tags.get(k) is not None:
			if v.startswith("TXXX"):
				mp3.add(Frames["TXXX"](encoding=3, text=tags[k], desc=v[5:]))
			else:
				mp3.add(Frames[v](encoding=3, text=tags[k]))
	
	if not {"track", "track_total"} & set(exclude_tags):
		mp3.add(Frames["TRCK"](encoding=3, text="0/0"))

	if ("track" not in exclude_tags) or ("track_total" not in exclude_tags):
		mp3.add(Frames["TRCK"](encoding=3, text=f"{tags["track"]}/{tags["track_total"]}"))

	if "cover" not in exclude_tags:
		cover_bytes = tags.get("cover_1x1") or get_cover(tags["cover_url"])
		mp3.add(Frames["APIC"](
			encoding=3, 
			mime="image/jpeg" if cover_format == "jpg" else "image/png",
			type=3,
			desc="Cover",
			data=cover_bytes
		))

	mp3.add(Frames["TPOS"](encoding=3, text="1/1"))
	mp3.save(v2_version=4)


def tagger_m4a(tags: Tags, fixed_location: Path, exclude_tags: list[str], cover_format: str):
	mp4_tags = {}
	for k, v in MP4_TAGS_MAP.items():
		if k not in exclude_tags and tags.get(k) is not None:
			mp4_tags[v] = [tags[k]]
	
	if not {"track", "track_total"} & set(exclude_tags):
		mp4_tags["trkn"] = [[0, 0]]
	if "cover" not in exclude_tags:
		cover_bytes = tags.get("cover_1x1") or get_cover(tags["cover_url"])
		mp4_tags["covr"] = [
			MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG if cover_format == "jpg" else MP4Cover.FORMAT_PNG)
		]
	if "track" not in exclude_tags:
		mp4_tags["trkn"][0][0] = tags["track"]
	if "track_total" not in exclude_tags:
		mp4_tags["trkn"][0][1] = tags["track_total"]

	mp4_tags["disk"] = [[1, 1]]

	mp4 = MP4(fixed_location)
	mp4.clear()
	mp4.update(mp4_tags)
	mp4.save()

@functools.lru_cache
def get_cover(url):
	return requests.get(url).content

def get_dominant_color(pil_img):
    img = pil_img.copy()
    img = img.convert("RGBA")
    img = img.resize((1, 1), resample=0)
    dominant_color = img.getpixel((0, 0))
    return dominant_color

def get_cover_with_padding(url: str, temp_location: Path, uniqueid: str, cover_format = "JPEG"):
	image_bytes = requests.get(url).content
	image = Image.open(BytesIO(image_bytes))

	width, height = image.size
	aspect_ratio = width / height

	if aspect_ratio == 1:
		return image_bytes
	
	# if temp_location.is_dir() is False:
	# 	os.mkdir(temp_location)

	# temp_path = temp_location / f"{uniqueid}.{cover_format.lower()}"
	# with open(temp_path, "wb") as temp_file:
	# 	temp_file.write(image_bytes)

	dominant_color = get_dominant_color(image)
	width, height = image.size
	padded_image = ImageOps.pad(image, (width, width), color=dominant_color, centering=(0.5, 0.5))

	output_bytes = BytesIO()
	padded_image.save(output_bytes, format=cover_format)
	output_bytes.seek(0)

	return output_bytes.read()
