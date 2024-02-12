import datetime
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

import requests

from .tagging import Tags, get_1x1_cover

TIGER_SINGLE = "tiger:is_single:true"

MBArtist = TypedDict("MBArtist", { 
	"id": str,
	"name": str, 
	"sort-name": str, 
})

MBArtistCredit = TypedDict("MBArtistCredit", { 
	"name": str, 
	"sort-name": str, 
	"artist": MBArtist
})

MBRelease = TypedDict("MBRelease", {
	"id": str,
	"title": str,
	"artist-credit": list[MBArtistCredit],
	"release-group": dict[str, str],
	"date": str
})

MBRecording = TypedDict("MBRecording", {
	"id": str,
	"title": str,
	"artist-credit": list[MBArtistCredit],
	"releases": list[MBRelease]
})

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

	for lb, rb in bracket_tuples: 
		lbe, rbe = re.escape(lb), re.escape(rb) # check for all matching variations of brackets
		for m in re.finditer(rf"{lbe}([^{lbe}{rbe}]+){rbe}", title):
			subs = "" # preserve info about a song cover or it's japanese title
			if "cover" in m.group(0).lower() or re.match(r"^[一-龠]+|[ぁ-ゔ]+|[ァ-ヴー]+|[々〆〤ヶ]+|\s+$", m.group(1)) is not None:
				subs = f"[{m.group(1)}]"
			title = title.replace(m.group(0), subs)
	
	# title = title.replace("（", " (").replace("）", ") ") # jap brackets fix
	title = re.sub(yeet_emoji, "", title) # remove emoji
	title = re.sub(r"\*\b[A-Z ]+\b\*", "", title) # remove stuff like *NOW ON ALL PLATFORMS*
	title = re.sub(r"(\S)\[", r"\g<1>" + " [", title, flags=re.MULTILINE) # jap title whitespace fix
	title = re.sub(r"\s{2,}", " ", title) # multiple spaces fix
	return title.replace("_", "-").strip()

def digits_match(in1: str, in2: str):
	"""makes it so that 2:09 matches 02:09"""
	leading0re = r"(?<=\b)0+(?=[1-9])"
	return re.sub(leading0re, "", in1.lower().strip()) == re.sub(leading0re, "", in2.lower().strip())

def check_bareartist_match(artist: str, a_dict: MBArtist):
	"""fuzzy song artist (single/bare) matching"""
	return artist == a_dict["name"] or artist.lower() == a_dict["name"].lower() \
		or artist == a_dict["sort-name"] or artist.lower() == a_dict["sort-name"].lower()

def check_artist_match(artist: str, a_list: list[MBArtistCredit]):
	"""fuzzy song artist matching (matches serveral artists as well)"""
	if len(a_list) > 1:
		# not using ARTIST_SEPARATOR here because ytmusic joins artists by &
		joinphrase = str(a_list[0].get("joinphrase")).strip() or "&" 
		yt_artists = [a.strip() for a in artist.split(joinphrase)]
		
		all_artists_match = True
		for yta in yt_artists:
			found_match = False
			for ac in a_list:
				if check_bareartist_match(yta, ac["artist"]):
					found_match = True
					break
			if not found_match:
				all_artists_match = False
				break
		
		return all_artists_match
	else:
		return check_bareartist_match(artist, a_list[0]["artist"])

def check_album_match(album: str, r_dict: MBRelease):
	"""fuzzy song album matching"""
	return album == r_dict["title"] or album.replace("(Single)", "").strip() == r_dict["title"] \
		or album.lower() == r_dict["title"].lower() or album.replace("(Single)", "").strip().lower() == r_dict["title"].lower() \
		or digits_match(album, r_dict["title"])

def check_title_match(title: str, r_dict: MBRecording):
	"""fuzzy song title matching"""
	return title == r_dict["title"] or title.lower() == r_dict["title"].lower() or digits_match(title, r_dict["title"])

def get_mb_artistids(a_list: list[MBArtistCredit], return_single = False):
	"""get artist mdid or list of mbids"""
	if len(a_list) == 1 or return_single:
		return a_list[0]["artist"]["id"]
	else:
		return [ a["artist"]["id"] for a in a_list ]
	

class MBSong:
	"""MusicBrainz song item"""
	def __init__(
		self,
		title: str = "",
		artist: str = "",
		album: str = ""
	):
		if title == "":
			raise Exception("title is required")
		self.title = clean_title(title)
		self.artist = artist
		self.album = album
		self.base = "https://musicbrainz.org/ws/2"
		self.default_params = { "fmt": "json" }

		self.song_dict = None # MBRecording
		self.artist_dict = None # MBArtistCredit
		self.album_dict = None # MBRelease

		self.mb_releasetrackid = None # song mbid
		self.mb_releasegroupid = None # album mbid
		self.mb_artistid = None # artist mbid

	def fetch_song(self):
		"""ping mb api to get song"""
		params = {
			"query": f'{self.title} artist:"{self.artist}" release:"{self.album}"',
			**self.default_params
		}
		res = requests.get(f"{self.base}/recording", params=params)
		if res.status_code >= 200 and res.status_code < 300:
			resjson = json.loads(res.text)
			self.save_song_dict(resjson["recordings"])

	def fetch_artist(self):
		"""ping mb api to get artist"""
		params = {
			"query": self.artist,
			**self.default_params
		}
		res = requests.get(f"{self.base}/artist", params=params)
		if res.status_code >= 200 and res.status_code < 300:
			resjson = json.loads(res.text)
			self.save_artist_dict(resjson["artists"])

	def save_song_dict(self, tracks: list[MBRecording]):
		"""find the most similar song"""

		for t in tracks:
			if ("artist-credit" not in t) or (len(t["artist-credit"]) == 0) or ("releases" not in t) or (len(t["releases"]) == 0):
				continue

			title_match = check_title_match(self.title, t)
			artist_match = False
			album_match = False
			
			if check_artist_match(self.artist, t["artist-credit"]):
				self.mb_artistid = get_mb_artistids(t["artist-credit"])
				self.artist_dict = t["artist-credit"]
				artist_match = True
				
			for a in t["releases"]:
				if check_album_match(self.album, a):
					self.mb_releasegroupid = a["release-group"]["id"]
					self.album_dict = a
					album_match = True
					break
				
			if title_match and artist_match and album_match:
				self.mb_releasetrackid = t["id"]
				self.song_dict = t
				break

		if self.song_dict is None:
			self.fetch_artist()

	def save_artist_dict(self, artists: list[MBArtist]):
		"""find most similar artist"""
		for a in artists:
			if check_bareartist_match(self.artist, a):
				self.artist_dict = a
				self.mb_artistid = a["id"]
				break

	def get_date_str(self):
		if self.song_dict is None:
			return None
		frd = self.song_dict.get("first-release-date")
		if frd is not None:
			return frd
		for r in self.song_dict["releases"]:
			if "date" not in r:
				continue
			return r["date"]
		return None

	def get_mbid_tags(self):
		"""get mbid tags with proper keys"""
		# !! make sure only supported fields are multi-value tags, otherwise auxio might crash (don't do multi-value album artists)
		first_mb_artistid = self.mb_artistid[0] if isinstance(self.mb_artistid, list) else self.mb_artistid
		
		return {
			"mb_releasetrackid": self.mb_releasetrackid,
			"mb_releasegroupid": self.mb_releasegroupid,
			"mb_artistid": self.mb_artistid,
			"mb_albumartistid": first_mb_artistid
		}

def musicbrainz_enrich_tags(tags: Tags, skip_encode = False, exclude_tags: list[str] = [], use_mbid_data = True):
	"""takes in a tags dict, adds mbid tags and (by default) also other mb info, returns it"""
	mb = MBSong(title=tags["title"], artist=str(tags["artist"]), album=tags["album"])
	mb.fetch_song()

	if use_mbid_data:
		if mb.artist_dict:
			if isinstance(mb.artist_dict, list): # TODO fix multi-value tags
				tags["artist"] = [a["artist"]["name"] for a in mb.artist_dict ]
			else: # TODO consider using mb.album_dict to get album artist?
				tags["artist"] = mb.artist_dict["name"]
			tags["albumartist"] = mb.artist_dict[0]["artist"]["name"] if isinstance(mb.artist_dict, list) else mb.artist_dict["name"]
		if mb.album_dict:
			tags["album"] = mb.album_dict["title"]
		if mb.song_dict:
			tags["title"] = mb.song_dict["title"]
			_release_date = mb.get_date_str()
			# print("mb", _release_date)
			if _release_date:
				tags["date"] = _release_date
				tags["year"] = parse_datestring(_release_date)["year"]

	for key, tag in mb.get_mbid_tags().items():
		if tag is not None and key not in exclude_tags:
			if skip_encode is False:
				tags[key] =  [ t.encode("utf-8") for t in tag ] if isinstance(tag, list) else tag.encode("utf-8")
			else:
				tags[key] = tag
	return tags

	