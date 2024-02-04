import datetime
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

import requests

from .tagging import Tags, get_1x1_cover

# this file parses the extract_info object provided by yt_dlp for informations
# grabs as much info as it can from all over the place: yt music tags, channel name, video title, description and other fields
# puts all of these strings into an array, count how many times each value occurs and the one that occurs most is the most likely result

# based on the original https://github.com/KraXen72/tiger

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
	"release-group": dict[str, str]
})

MBRecording = TypedDict("MBRecording", {
	"id": str,
	"title": str,
	"artist-credit": list[MBArtistCredit],
	"releases": list[MBRelease]
})

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
		date = { "year": upload_date[0:4], "month": upload_date[4:6], "day": upload_date[6:8] }
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
	md_keys = { "title": ["title", "track", "alt_title"], "artist": ["artist", "channel", "creator"], "album_artist": [], "album": ["album"] }
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

	# video title is: Artist - Title format
	if info["title"].count(" - ") == 1:
		add_values = dash_split(info, "title", add_values)
	if info["fulltitle"].count(" - ") == 1:
		add_values = dash_split(info, "fulltitle", add_values)

	# channel is: Artist - Topic was superseeded by YTMusic API

	return md_keys, add_values

def soundcloud_extractor(info):
	md_keys = { "title": ["title", "fulltitle"], "artist": ["uploader"], "album_artist": ["uploader"], "album": [] }
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

	return md_keys, add_values

def smart_metadata(info, temp_location: Path, cover_format = "JPEG", cover_crop_method = "auto"):
	"""
	grabs as much info as it can from all over the place
	gets the most likely tag and returns a dict
	"""

	md: Tags = {
		"title": "",
		"artist": "",
		"album": "",
		"album_artist": "",
		"track": 1,
		"track_total": 1,
		"release_year": "",
		"release_date": "",
		"cover_url": info["thumbnail"],
		"cover_bytes": get_1x1_cover(
			info["thumbnail"], 
			temp_location, 
			info.get("id") or clean_title(info.get("title")) or str(random.randint(0, 9) * "16"), 
			cover_format, 
			cover_crop_method
		)
	}
	md_keys = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], } # keys to check from the 'info object'. site specific.
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }
	others = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

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
	md["album_artist"], others["album_artist"] = smart_tag(md_keys["album_artist"], info, [md["artist"]] + add_values["album_artist"])

	md["title"] = clean_title(str(md["title"]))

	# fallback: title (Single) => album, only if there is no album yet
	if ("album" not in info) and len(add_values["album"]) == 0:
		add_values["album"].append(f"{md['title']} (Single)")

	md["album"], others["album"] = smart_tag(md_keys["album"], info, add_values["album"])
	md["release_year"], md["release_date"] = get_year(info)

	if "(Single)" in md["album"]:
		md["comment"] = TIGER_SINGLE

	# print(md["release_year"], md["release_date"])
	# print({**md, "cover_bytes": ""})

	return md

bracket_tuples =[["[", "]"], ["(", ")"], ["【", "】"], ["「", "」"]]
title_banned_chars = ["♪"]

def clean_title(title: str):
	"""do you love regex?"""

	for lb, rb in bracket_tuples: 
		lbe, rbe = re.escape(lb), re.escape(rb) # check for all matching variations of brackets
		for m in re.finditer(rf"{lbe}([^{lbe}{rbe}]+){rbe}", title):
			subs = "" # preserve info about a song cover or it's japanese title
			if "cover" in m.group(0).lower() or re.match(r"^[一-龠]+|[ぁ-ゔ]+|[ァ-ヴー]+|[々〆〤ヶ]+|\s+$", m.group(1)) is not None:
				subs = f"[{m.group(1)}]"
			title = title.replace(m.group(0), subs)
	
	for ch in title_banned_chars:
		title = title.replace(ch, "")
	
	# title = title.replace("by {artist}", "")
	title = re.sub(r"(\S)\[", r"\g<1>" + " [", title, flags=re.MULTILINE) # jap title whitespace fix
	title = re.sub(r"\s{2,}", " ", title) # multiple spaces fix
	return title.replace("_", "-").strip()

def digits_match(in1: str, in2: str):
	leading0re = r"(?<=\b)0+(?=[1-9])"
	return re.sub(leading0re, "", in1.lower().strip()) == re.sub(leading0re, "", in2.lower().strip())

def check_bareartist_match(artist: str, a_dict: MBArtist):
	return artist == a_dict["name"] or artist.lower() == a_dict["name"].lower() \
		or artist == a_dict["sort-name"] or artist.lower() == a_dict["sort-name"].lower()

def check_artist_match(artist: str, a_list: list[MBArtistCredit]):
	if len(a_list) > 1:
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
	
def get_artist_mbids(a_list: list[MBArtistCredit]):
	"""get artist mdid or list of mbids"""
	if len(a_list) == 1:
		return a_list[0]["artist"]["id"]
	else:
		return [ a["artist"]["id"] for a in a_list ]

def check_album_match(album: str, r_dict: MBRelease):
	return album == r_dict["title"] or album.replace("(Single)", "").strip() == r_dict["title"] \
		or album.lower() == r_dict["title"].lower() or album.replace("(Single)", "").strip().lower() == r_dict["title"].lower() \
		or digits_match(album, r_dict["title"])

def check_title_match(title: str, r_dict: MBRecording):
	return title == r_dict["title"] or title.lower() == r_dict["title"].lower() or digits_match(title, r_dict["title"])
	

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

		self.song_dict = None
		self.artist_dict = None
		self.album_dict = None

		self.song_mbid = None
		self.artist_mbid = None
		self.album_mbid = None

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
		# print("a", self.artist)
		for t in tracks:
			# skip entries with missing album or artist
			if ("artist-credit" not in t) or (len(t["artist-credit"]) == 0) or ("releases" not in t) or (len(t["releases"]) == 0):
				continue

			title_match = check_title_match(self.title, t)
			artist_match = False
			album_match = False
			# print(t["title"], json.dumps(t["artist-credit"]))
			# print("")
			
			if check_artist_match(self.artist, t["artist-credit"]):
				self.artist_mbid = get_artist_mbids(t["artist-credit"])
				self.artist_dict = t["artist-credit"]
				artist_match = True
				break
				
			for a in t["releases"]:
				if check_album_match(self.album, a):
					self.album_mbid = a["release-group"]["id"]
					self.album_dict = a
					# print(json.dumps(self.album_dict))
					album_match = True
					break
				
			if title_match and artist_match and album_match:
				self.song_mbid = t["id"]
				self.song_dict = t
				break

		if self.song_dict is None:
			self.fetch_artist()

	def save_artist_dict(self, artists: list[MBArtist]):
		"""find most similar artist"""
		for a in artists:
			if check_bareartist_match(self.artist, a):
				self.artist_dict = a
				self.artist_mbid = a["id"]
				break

	def get_mbid_tags(self):
		"""get mbid tags with proper keys"""
		
		return {
			"track_mbid": self.song_mbid,
			"album_mbid": self.album_mbid,
			"artist_mbid": self.artist_mbid,
			"album_artist_mbid": self.artist_mbid
		}

def get_mbids_for_song(tags: Tags, skip_encode = False, exclude_tags: list[str] = [], use_mbid_data=True):
	"""takes in a tags dict, adds mbid tags to it, returns it"""
	mb = MBSong(title=tags["title"], artist=str(tags["artist"]), album=tags["album"])
	mb.fetch_song()

	if use_mbid_data:
		if mb.artist_dict:
			tags["artist"] = [str(a["artist"]["name"]) for a in mb.artist_dict] if isinstance(mb.artist_dict, list) else mb.artist_dict["name"]
			tags["album_artist"] = mb.artist_dict[0]["artist"]["name"] if isinstance(mb.artist_dict, list) else mb.artist_dict["name"]
	
	for key, tag in mb.get_mbid_tags().items():
		if tag is not None and key not in exclude_tags:
			if skip_encode is False:
				tags[key] =  [ t.encode("utf-8") for t in tag ] if isinstance(tag, list) else tag.encode("utf-8")
			else:
				tags[key] = tag
	
	return tags

	