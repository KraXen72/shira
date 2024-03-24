import json
import re
from typing import TypedDict

import requests

from shiradl.metadata import clean_title, parse_datestring
from shiradl.tagging import Tags

# it's better if this is a "submodule" of shira (a part of it)
# works on it's own (name == __main__), but everything apart from the musibrainz logic doesen't live in it
# it's in a separate python module is to have a separate command & to separate the code

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

def musicbrainz_enrich_tags(tags: Tags, skip_encode = False, exclude_tags: list[str] = [], use_mbid_data = True):  # noqa: B006
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
	
	if "mb*" in exclude_tags:
		return tags

	for key, tag in mb.get_mbid_tags().items():
		if tag is not None and key not in exclude_tags:
			if skip_encode is False:
				tags[key] =  [ t.encode("utf-8") for t in tag ] if isinstance(tag, list) else tag.encode("utf-8")
			else:
				tags[key] = tag
	return tags

	