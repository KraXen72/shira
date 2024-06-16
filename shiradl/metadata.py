import datetime
import random
import re
from collections import Counter
from pathlib import Path

import requests

from .tagging import Tags, get_1x1_cover

TIGER_SINGLE = "tiger:is_single:true"

def parse_datestring(datestr: str):
	"""parse YYYYMMDD or YYYY-MM-DD into { year: str, month: str, day: str }"""
	if re.match(r"^\d{8}$", datestr):
		return { "year": datestr[0:4], "month": datestr[4:6], "day": datestr[6:8] }
	elif "-" in datestr and re.match(r"^\d{4}-\d{2}-\d{2}$", datestr):
		parts = datestr.split("-")
		return { "year": parts[0], "month": parts[1], "day": parts[2] }
	else:
		raise Exception(f"parse_datesting: unknown format of '{datestr}' - use YYYY-MM-DD or YYYYMMDD")


def get_year(track: dict[str, str | int], ytmusic_album: dict[str, str | int] | None = None):
	""":returns release_year, release_date"""
	date = {
		"day": "01",
		"month": "01",
		"year": ""
	}		
	release_date = ""
	release_year = ""

	upload_date = track.get("release_date") or track.get("upload_date")
	upload_date = str(upload_date) if upload_date is not None else None

	if upload_date: # YYYYMMDD
		date = parse_datestring(upload_date)
	elif ytmusic_album is not None:
		date["year"] = str(ytmusic_album.get("year") or track.get("release_year"))

	release_year = date["year"]
	release_date = datetime.datetime(day=int(date["day"]), month=int(date["month"]), year=int(date["year"])).isoformat() + "Z"
			
	return release_year, release_date

def dash_split(info, title_key: str,  obj):
	split_title = info[title_key].split(" - ")

	classic_ordering = True
	for keyword in ["animatic", "remix"]:
		if keyword in info[title_key].lower():
			obj["artist"].append(info["channel"])
			obj["title"].append(split_title[0] if keyword in split_title[1].lower() else split_title[0])
			classic_ordering = False
			break
	if classic_ordering:
		obj["artist"].append(split_title[0])
		obj["title"].append(split_title[1])
	
	return obj


def smart_tag(list_of_keys: list[str], data_obj: dict, additional_values: list[str]):
	"""
	counts how many times each value occurs and returns the value that occurs the most
	"""
	tags = additional_values if additional_values is not None else []
	for item in list_of_keys:
		if item in data_obj:
			tags.append(data_obj[item])

	for i, tag in enumerate(tags):
		if isinstance(tag, int):
			tags[i] = str(tag)

	# filter out none and 'null'
	cleaned_tags = list(filter(lambda x: x is not None and x != "null", tags))

	counts = Counter(cleaned_tags) # count how many times a string occurs in the tags list
	counts_entries = list(counts.items())
	sorted_counts = sorted(counts_entries, key = lambda x: x[1]) # sort it (ascending)
	dehashed_counts = list(reversed(sorted_counts)) # reverse (descending)

	top_result = dehashed_counts[0][0]

	# resolve conficlics
	if len(dehashed_counts) > 1 and dehashed_counts[0][1] == dehashed_counts[1][1]:
		second_result = dehashed_counts[1][0]

		# for example if years look like this: [('2017', 1), ({'year': '2017', 'month': '10', 'day': '19'}, 1)]
		if isinstance(top_result, str) and isinstance(second_result, dict):
			top_result, second_result = second_result, top_result

	return top_result, cleaned_tags

# site extractors
def youtube_extractor(info):
	md_keys = { "title": ["title", "track", "alt_title"], "artist": ["artist", "channel", "creator"], "albumartist": [], "album": ["album"] }
	add_values = { "title": [], "artist": [], "albumartist": [], "album": [], "year": [], }

	# video title is: Artist - Title format
	if info["title"].count(" - ") == 1:
		add_values = dash_split(info, "title", add_values)
	if info["fulltitle"].count(" - ") == 1:
		add_values = dash_split(info, "fulltitle", add_values)

	# channel is: Artist - Topic was superseeded by YTMusic API

	return md_keys, add_values

def soundcloud_extractor(info):
	md_keys = { "title": ["title", "fulltitle"], "artist": ["uploader"], "albumartist": ["uploader"], "album": [] }
	add_values = { "title": [], "artist": [], "albumartist": [], "album": [], "year": [], }

	return md_keys, add_values

def get_youtube_maxres_thumbnail(info):
	# sometimes info["thumbnail"] results in the fallback youtube 404 gray thumbnail
	pinged_urls = []
	thumbs = list(reversed(info["thumbnails"]))

	def ping_yt(url: str):
		res = requests.get(str(t["url"]))
		pinged_urls.append(t["url"])
		return res

	for t in thumbs: # try to get maxresdefault
		if t["url"] in pinged_urls:
			continue
		if t["url"].endswith("/maxresdefault.jpg") or t["url"].endswith("/maxresdefault.png"):
			res = ping_yt(t["url"])
			if res.status_code == 404:
				continue
			return str(t["url"])
	for t in thumbs: # otherwise, just take the one with the best preference but out format
		if t["url"] in pinged_urls:
			continue
		if t["url"].endswith(".jpg") or t["url"].endswith(".png"):
			res = ping_yt(t["url"])
			if res.status_code == 404:
				continue
			return str(t["url"])
	return str(info["thumbnail"])

# based on the original https://github.com/KraXen72/tiger
def smart_metadata(info, temp_location: Path, cover_format = "JPEG", cover_crop_method = "auto"):
	"""
	grabs as much info as it can from all over the place
	gets the most likely tag and returns a dict
	"""
	
	thumbnail = get_youtube_maxres_thumbnail(info)
	# thumbnail = info["thumbnail"]
	md: Tags = {
		"title": "",
		"artist": "",
		"album": "",
		"albumartist": "",
		"track": 1,
		"tracktotal": 1,
		"year": "",
		"date": "",
		"cover_url": thumbnail,
		"cover_bytes": get_1x1_cover(
			thumbnail, 
			temp_location, 
			info.get("id") or clean_title(info.get("title")) or str(random.randint(0, 9) * "16"), 
			cover_format, 
			cover_crop_method
		)
	}
	md_keys = { "title": [], "artist": [], "albumartist": [], "album": [], "year": [], } # keys to check from the 'info object'. site specific.
	add_values = { "title": [], "artist": [], "albumartist": [], "album": [], "year": [], }
	others = { "title": [], "artist": [], "albumartist": [], "album": [], "year": [], }

	domain = info["webpage_url_domain"]
	match domain:
		case "soundcloud.com":
			md_keys, add_values = soundcloud_extractor(info)
		case _:
			if domain != "youtube.com":
				print("[warning] unsupported domain:", str(domain), "using youtube extractor as fallback.")
			md_keys, add_values = youtube_extractor(info)
	
	md["title"], others["title"] = smart_tag(md_keys["title"], info, add_values["title"])
	md["artist"], others["artist"] = smart_tag(md_keys["artist"], info, add_values["artist"])
	md["albumartist"], others["albumartist"] = smart_tag(md_keys["albumartist"], info, [md["artist"]] + add_values["albumartist"])

	md["title"] = clean_title(str(md["title"]))

	# fallback: title (Single) => album, only if there is no album yet
	if ("album" not in info) and len(add_values["album"]) == 0:
		add_values["album"].append(f"{md['title']} (Single)")

	md["album"], others["album"] = smart_tag(md_keys["album"], info, add_values["album"])
	md["year"], md["date"] = get_year(info)

	if "(Single)" in md["album"]:
		md["comments"] = TIGER_SINGLE # TODO remove this later?

	return md

bracket_tuples =[["[", "]"], ["(", ")"], ["【", "】"], ["「", "」"], ["（", "）"]]
title_banned_chars = ["♪"]

# https://stackoverflow.com/a/49986645/13342359
yeet_emoji = re.compile(pattern = "["
	"\U0001F600-\U0001F64F"  # emoticons
	"\U0001F300-\U0001F5FF"  # symbols & pictographs
	"\U0001F680-\U0001F6FF"  # transport & map symbols
	"\U0001F1E0-\U0001F1FF"  # flags (iOS)
"]+", flags = re.UNICODE)

def clean_title(title: str):
	"""clean up youtube titles with regex and a lot of black magic"""

	for char in title_banned_chars:
		title = title.replace(char, "")
	for lb, rb in bracket_tuples: 
		lbe, rbe = re.escape(lb), re.escape(rb) # check for all matching variations of brackets
		for m in re.finditer(rf"{lbe}([^{lbe}{rbe}]+){rbe}", title):
			subs = "" # preserve info about a song cover or it's japanese title
			if "cover" in m.group(0).lower() or re.match(r"^[一-龠]+|[ぁ-ゔ]+|[ァ-ヴー]+|[々〆〤ヶ]+|\s+$", m.group(1)) is not None:
				subs = f"[{m.group(1)}]"
			title = title.replace(m.group(0), subs)
	
	title = re.sub(yeet_emoji, "", title) # remove emoji
	title = re.sub(r"\*\b[A-Z ]+\b\*", "", title) # remove stuff like *NOW ON ALL PLATFORMS*
	title = re.sub(r"(\S)\[", r"\g<1>" + " [", title, flags=re.MULTILINE) # jap title whitespace fix
	title = re.sub(r"\s{2,}", " ", title) # multiple spaces fix
	return title.replace("_", "-").strip()