from __future__ import annotations

import functools
import os
from io import BytesIO
from pathlib import Path
from statistics import mean, stdev
from typing import NotRequired, TypedDict

from dateutil import parser
from mediafile import Image as MFImage
from mediafile import ImageType, MediaFile
from PIL import Image, ImageFilter, ImageOps
from requests_cache import CachedSession

AVG_THRESHOLD = 10
CHANNEL_THRESHOLD = 15
MV_SEPARATOR = "/"#" & " # TODO make this configurable
MV_SEPARATOR_VISUAL = " & "
req = CachedSession("shira", expire_after=3600)

class Tags(TypedDict):
	title: str
	album: str
	artist: str | list[str]
	albumartist: str | list[str]
	track: int
	tracktotal: int
	year: str
	date: str
	cover_url: str
	cover_bytes: NotRequired[bytes]
	rating: NotRequired[int]
	comments: NotRequired[str]
	lyrics: NotRequired[str]

fallback_mv_keys = ["artist", "albumartist"]

def metadata_applier(tags: Tags, fixed_location: Path, exclude_tags: list[str], fallback_mv = True):
	"""set fallback_mv = True until auxio supports proper multi-value m4a tags from mutagen"""
	handle = MediaFile(fixed_location)
	handle.delete()
	# print({**tags, "cover_bytes": ""})
	for k, v in tags.items():
		if k in exclude_tags or k in ["cover_url", "cover_bytes"]: 
			continue
		if k == "date":
			v = parser.isoparse(str(v)).date()
		if isinstance(v, list):
			if not fallback_mv or (k not in fallback_mv_keys):
				setattr(handle, f"{k}s", v) # will not work for all single => multi migrations
			if k in fallback_mv_keys:
				setattr(handle, k,  MV_SEPARATOR.join(v) if fallback_mv else MV_SEPARATOR_VISUAL.join(v))
		else:
			setattr(handle, k, v)
	
	if "cover" not in exclude_tags:
		cover_bytes = tags.get("cover_bytes") or get_cover(tags["cover_url"])
		handle.images = [ MFImage(data=cover_bytes, desc="Cover", type=ImageType.front) ]

	handle.disc = 1
	handle.disctotal = 1
	handle.save()

# cover shenanigans

@functools.lru_cache
def get_cover(url):
	return req.get(url).content

def get_cover_local(file_path: Path, id_or_url: str, is_soundcloud: bool):
	"""
	reads a local image as bytes.  
	if given a directory, finds the matching image by filename stem matching id_or_url
	"""
	if file_path.is_file():
		return file_path.read_bytes()
	elif file_path.is_dir():
		for filename in os.listdir(file_path):
			fp = file_path / filename
			if (not fp.is_file()) or (fp.suffix.lower() not in [".jpg", ".jpeg", ".png"]):
				continue
			if (is_soundcloud and id_or_url.split("/")[-1] == fp.stem) or (is_soundcloud is False and id_or_url == fp.stem):
				return fp.read_bytes()
	return None

def get_dominant_color(pil_img: Image.Image) -> tuple[int, int, int, int]:
	img = pil_img.copy().convert("RGBA")
	img = img.resize((1, 1), resample=Image.Resampling.NEAREST)
	
	pixel = img.getpixel((0, 0))

	# Explicitly ensure the return type is always Tuple[int, int, int, int]
	if isinstance(pixel, tuple) and len(pixel) == 4:
		return pixel
	else:
		return (0,0,0,255)

def sample_image_corners(rgb_image, width, height, border_offset = 50):
	sample_colors = []
	regions = [
		(border_offset, border_offset), # topleft
		(width - border_offset, border_offset), #topright
		(border_offset, height - border_offset),   #botleft
		(width - border_offset, height - border_offset), #botright
		# (border_slice_center, height//2), #left center
		# (width//2 + height//2 + border_slice_center, height//2) #right center
	]
	for sx, sy in regions:
		r, g, b = rgb_image.getpixel((sx, sy))
		sample_colors.append((r, g, b))
	return sample_colors

def determine_image_crop(image_bytes: bytes):
	"""
	samples 4 pixels near the corners and 2 from centers of side slices of the thumbnail (which is first smoothed and reduced to 64 colors)

	returns 'crop' if average of standard deviation of r, g and b color channels 
	from each sample point is lower than a than a threshold, otherwise returns 'pad'
	"""
	pil_img = Image.open(BytesIO(image_bytes))
	filt_image = pil_img.filter(ImageFilter.SMOOTH).convert("P", palette=Image.ADAPTIVE, colors=64)
	rgb_filt_image = filt_image.convert("RGB")
	
	width, height = rgb_filt_image.size
	sample_colors50 = sample_image_corners(rgb_filt_image, width, height, 50)
	sample_colors0 = sample_image_corners(rgb_filt_image, width, height, 1)

	reds, greens, blues = [], [], []
	for r,g,b in sample_colors50:
		reds.append(r)
		greens.append(g)
		blues.append(b)

	dev_red = stdev(reds)
	dev_green = stdev(greens)
	dev_blue = stdev(blues)
	avg_dev = mean([dev_red, dev_green, dev_blue])

	# if 4 true corners are 100% equal, fill with that.
	# TODO later, crop the borders off of a black-bordered thumbnail for real cropping
	fill_recc = sample_colors0[0] if len(set(sample_colors0)) == 1 else None
	# print("average:", avg_dev, "colors:", dev_red, dev_green, dev_blue)

	if avg_dev < AVG_THRESHOLD and dev_red < CHANNEL_THRESHOLD and dev_green < CHANNEL_THRESHOLD and dev_blue < CHANNEL_THRESHOLD:
		return "crop", fill_recc
	else:
		return "pad", fill_recc

def get_1x1_cover(url: str, temp_location: Path, uniqueid: str, cover_format = "JPEG", cover_crop_method = "auto"):
	image_bytes = req.get(url).content
	pil_img = Image.open(BytesIO(image_bytes))

	width, height = pil_img.size
	aspect_ratio = width / height

	if aspect_ratio == 1:
		return image_bytes

	width, height = pil_img.size
	recc_fill_color = None

	if cover_crop_method == "auto":
		cover_crop_method, recc_fill_color = determine_image_crop(image_bytes)
	
	if cover_crop_method == "crop":
		img_half = round(width / 2)
		rect_half = round(height / 2)
		pil_img = pil_img.crop((img_half - rect_half, 0, img_half + rect_half, height))
	else:
		dominant_color = get_dominant_color(pil_img) if recc_fill_color is None else recc_fill_color
		pil_img = ImageOps.pad(pil_img, (width, width), color=dominant_color, centering=(0.5, 0.5))

	output_bytes = BytesIO()
	pil_img.save(output_bytes, format=cover_format)
	output_bytes.seek(0)

	return output_bytes.read()
