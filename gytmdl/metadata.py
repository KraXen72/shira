import datetime
import json
import re
from collections import Counter
from typing import TypedDict

import requests

from .tagging import Tags

# this file parses the extract_info object provided by yt_dlp for informations
# grabs as much info as it can from all over the place: yt music tags, channel name, video title, description and other fields
# puts all of these strings into an array, count how many times each value occurs and the one that occurs most is the most likely result

# based on the original https://github.com/KraXen72/tiger

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

def parse_date(datestring):
	"""
	parses one of 3 date formats: 2020-07-01, 2020 and 20200630.
	otherwise return None
	"""
	if datestring.count("-") == 2: # 2020-07-01
		parts = datestring.split("-")
		return { "year": parts[0], "month": parts[1], "day": parts[2] }
	elif ("-" not in datestring) and ("." not in datestring):
		if len(datestring) == 4: # 2020
			return { "year": datestring }
		elif len(datestring) == 8: # 20200630
			# TODO change to ints, use in get_year
			return { "year": datestring[0:4], "month": datestring[4:6], "day": datestring[6:8] }

def dash_split(string, obj):
	split_title = string.split(" - ")
	obj["artist"].append(split_title[0])
	obj["title"].append(split_title[1])
	return obj

def get_most_likely_tag(list_of_keys: list[str], data_obj: dict, additional_values: list[str]):
	"""
	counts how many times each value occurs and returns the value that occurs the most
	"""
	tags = additional_values if additional_values is not None else []
	for item in list_of_keys:
		if item in data_obj:
			tags.append(data_obj[item])

	# stringify the dict into json so Counter doesen't freak out
	for i, tag in enumerate(tags):
		if isinstance(tag, dict):
			tags[i] = json.dumps(tag, separators=(",", ":"))
		if isinstance(tag, int):
			tags[i] = str(tag)

	# filter out none and 'null'
	cleaned_tags = list(filter(lambda x: x is not None and x != "null", tags))

	counts = Counter(cleaned_tags) # count how many times a string occurs in the tags list
	counts_entries = list(counts.items())
	sorted_counts = sorted(counts_entries, key = lambda x: x[1]) # sort it (ascending)
	descending_counts = list(reversed(sorted_counts)) # reverse (descending)

	dehashed_counts: list[tuple[dict[str, str] | str, int]] = [] # re-parse jsons
	for count_tuple in descending_counts:
		val = count_tuple[0]
		count = count_tuple[1]

		if val.startswith("{") and val.endswith("}"):
			try:
				data_obj = json.loads(val)
				dehashed_counts.append((data_obj, count))
			except:
				dehashed_counts.append(count_tuple)
		else:
			dehashed_counts.append(count_tuple)

	top_result = dehashed_counts[0][0]

	# resolve conficlics
	if len(dehashed_counts) > 1 and dehashed_counts[0][1] == dehashed_counts[1][1]:
		second_result = dehashed_counts[1][0]
		# print("top 2 tags have the same count:", dehashed_counts)

		# for example if years look like this: [('2017', 1), ({'year': '2017', 'month': '10', 'day': '19'}, 1)]
		if isinstance(top_result, str) and isinstance(second_result, dict):
			top_result, second_result = second_result, top_result

    # TODO rewrite so top_result is always string and not the year thingy
	return top_result, cleaned_tags

# site extractors
def youtube_extractor(info):
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

	# video title is: Artist - Title format
	if info["title"].count(" - ") == 1:
		add_values = dash_split(info["title"], add_values)

	if info["fulltitle"].count(" - ") == 1:
		add_values = dash_split(info["title"], add_values)

	# channel is: Artist - Topic
	if info["uploader"].endswith(" - Topic"):
		clean_uploader = info["uploader"][:-8] #slice off last 8 ( - Topic)
		if ("categories" not in info) or (info["categories"] == ["Music"]):
			add_values["artist"].append(clean_uploader)

			# parse and use auto-generated description
			if info["description"].endswith("Auto-generated by YouTube."):
				lines = info["description"].split("\n\n")

				if lines[1].count(" · ") == 1: # artist · title
					l1split = lines[1].split(" · ")
					add_values["artist"].append(l1split[1])
					add_values["title"].append(l1split[0])

				add_values["album"].append(lines[2])
				# add_values["publisher"].append(lines[3].replace("℗ ", "").replace("℗", ""))

				if lines[4].startswith("Released on: "):
					raw_date = lines[4][13:]
					date = parse_date(raw_date)
					add_values["year"].append(date)

	# fallback: upload date => year, only if there is no date yet
	# if ("upload_date" in info) and len(add_values["publisher"]) == 0:
	if ("upload_date" in info):
		add_values["year"].append(parse_date(info["upload_date"]))

	return add_values

def soundcloud_extractor(info):
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

	# add_values["publisher"] = f"{info['uploader']} via SoundCloud."
	# TODO finish soundcloud extractor
	return add_values

def smart_metadata(info):
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
		"cover_url": info["thumbnail"]
	}
	md_keys = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], } # keys to check from the 'info object'. site specific.
	add_values = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }
	others = { "title": [], "artist": [], "album_artist": [], "album": [], "year": [], }

	# f = open("playlist.json", "w", encoding="utf8")
	# json.dump(info, f, indent=4, ensure_ascii=False)
	# f.close()
	# print("webpage_url_domain" in info, info.get("webpage_url_domain"), info.keys())
	domain = info["webpage_url_domain"]
	

	# TODO extract this
	match domain:
		case "soundcloud.com":
			md_keys = {
				"title": ["title", "fulltitle"],
				"artist": ["uploader"],
				"album_artist": ["uploader"],
				"album": [], # soundcloud doesen't expose album metadata?
				"year": ["upload_date"],
				# "publisher": []
			}
			add_values = soundcloud_extractor(info)
		case _:
			if domain != "youtube.com":
				print("[warning] unsupported domain:", domain, "using youtube extractor as fallback.")
			md_keys = {
				"title": ["title", "track", "alt_title"],
				"artist": ["artist", "channel", "creator"],
				"album_artist": [],
				"album": ["album"],
				"year": ["release_date", "release_year"],
				# "publisher": []
			}
			add_values = youtube_extractor(info)

	# pass all the vales to get_most_likely_tag
	# which counts how many times each value occurs and returns the value that occurs the most
	# also dumps all the other possibilities into the other dictionary
	
	md["title"], others["title"] = get_most_likely_tag(md_keys["title"], info, add_values["title"])
	md["artist"], others["artist"] = get_most_likely_tag(md_keys["artist"], info, add_values["artist"])
	md["album_artist"], others["album_artist"] = get_most_likely_tag(md_keys["album_artist"], info, [md["artist"]] + add_values["album_artist"])

	md["title"] = clean_title(str(md["title"]))

	# fallback: title (Single) => album, only if there is no album yet
	if ("album" not in info) and len(add_values["album"]) == 0:
		add_values["album"].append(f"{md['title']} (Single)")

	md["album"], others["album"] = get_most_likely_tag(md_keys["album"], info, add_values["album"])
	tdate, others["year"] = get_most_likely_tag(md_keys["year"], info, add_values["year"])

	if isinstance(tdate, str):
		md["release_year"] = tdate
	else:
		md["release_year"] = tdate["year"]
		md["release_date"] = datetime.datetime(
			day=int(tdate["day"]), 
			month=int(tdate["month"]), 
			year=int(tdate["year"])
		).isoformat() + "Z"

	return md

def get_year(track: dict[str, str | int], ytmusic_album: dict[str, str | int]):
	date = {
		"day": "01",
		"month": "01",
		"year": ""
	}		
	release_date = ""
	release_year = ""

	# f = open("album.json", "w", encoding="utf8")
	# json.dump(ytmusic_album, f, indent=4, ensure_ascii=False)
	# f.close()
	

	upload_date = track.get("release_date") or track.get("upload_date")
	upload_date = str(upload_date) if upload_date is not None else None
	if upload_date: # YYYYMMDD
		date = { "year": upload_date[0:4], "month": upload_date[4:6], "day": upload_date[6:8] }
	else: # only year
		date["year"] = str(ytmusic_album.get("year") or track.get("release_year"))

	release_year = date["year"]
	release_date = datetime.datetime(day=int(date["day"]), month=int(date["month"]), year=int(date["year"])).isoformat() + "Z"
			
	return release_year, release_date

def clean_title(title: str):
	"""do you love regex?"""

	brackets =[["[", "]"], ["(", ")"], ["【", "】"], ["「", "」"]]
	for lb, rb in brackets: 
		lbe, rbe = re.escape(lb), re.escape(rb) # check for all matching variations of brackets
		for m in re.finditer(rf"{lbe}([^{lbe}{rbe}]+){rbe}", title):
			subs = "" # preserve info about a song cover or it's japanese title
			if "cover" in m.group(0).lower() or re.match(r"^[一-龠]+|[ぁ-ゔ]+|[ァ-ヴー]+|[々〆〤ヶ]+|\s+$", m.group(1)) is not None:
				subs = f"[{m.group(1)}]"
			title = title.replace(m.group(0), subs)
	
	# title = title.replace("by {artist}", "")
	title = re.sub(r"(\S)\[", r"\g<1>" + " [", title, flags=re.MULTILINE) # jap title whitespace fix
	title = re.sub(r"\s{2,}", " ", title) # multiple spaces fix
	return title.replace("_", "-").strip()

def check_artist_match(artist: str, a_dict: MBArtist):
	return artist == a_dict["name"] or artist.lower() == a_dict["name"].lower() \
		or artist == a_dict["sort-name"] or artist.lower() == a_dict["sort-name"].lower()

def check_album_match(album: str, r_dict: MBRelease):
	return album == r_dict["title"] or album.replace("(Single)", "").strip() == r_dict["title"] \
		or album.lower() == r_dict["title"].lower() or album.replace("(Single)", "").strip().lower() == r_dict["title"].lower()
	

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
		for t in tracks:
			# skip entries with missing album or artist
			if ("artist-credit" not in t) or (len(t["artist-credit"]) == 0) or ("releases" not in t) or (len(t["releases"]) == 0):
				continue

			title_match = t["title"] == self.title
			artist_match = False
			album_match = False
			
			for a in t["artist-credit"]:
				if check_artist_match(self.artist, a["artist"]):
					self.artist_mbid = a["artist"]["id"]
					self.artist_dict = a["artist"]
					artist_match = True
					break
			for a in t["releases"]:
				if check_album_match(self.album, a):
					self.album_mbid = a["release-group"]["id"]
					self.album_dict = a
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
			if check_artist_match(self.artist, a):
				self.artist_dict = a
				self.artist_mbid = a["id"]
				break

	def get_mbid_tags(self):
		"""get mbid tags with proper keys"""

		# f = open("rec.json", "w", encoding="utf8")
		# json.dump(self.album_dict, f, indent=4, ensure_ascii=False)
		# f.close()
		
		return {
			"track_mbid": self.song_mbid,
			"album_mbid": self.album_mbid,
			"artist_mbid": self.artist_mbid,
			"album_artist_mbid": self.artist_mbid
		}

def get_mbids_for_song(tags: Tags, do_encode = True):
	"""takes in a tags dict, adds mbid tags to it, returns it"""
	mb = MBSong(title=tags["title"], artist=tags["artist"], album=tags["album"])
	mb.fetch_song()
	
	for key, tag in mb.get_mbid_tags().items():
		if tag is not None:
			if do_encode is False:
				tags[key] = tag
			else:
				tags[key] = tag.encode("utf-8")
	
	return tags

	