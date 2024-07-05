import json
import re
from typing import TypedDict

from requests_cache import CachedSession

from shiradl.__init__ import __version__ as shiraver
from shiradl.metadata import clean_title, parse_datestring
from shiradl.tagging import Tags

# it's better if this is a "submodule" of shira (a part of it)
# works on it's own (name == __main__), but everything apart from the musibrainz logic doesen't live in it
# it's in a separate python module is to have a separate command & to separate the code

# at some point, i might have to just switch this to depend on picard itself or it's submodule - i can only get so far with lookup
# acoutsid fingerprinting might be a good idea
# however, even then, it's not 100% accurate...

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
 
leading_zero_re = r"(?<=\b)0+(?=[1-9])" # strips all leading zeros
hyphens_re = r"‐|‑|‒|–|—|―|⁃|－" # non-standard hyphens

# MusicBrainz usually has songs with feat. in the title without it
# allows multiple words for bare ft. (till the end of title)
# look i'm not stoked about this regex but it works
title_feat_re = r"\s?(?:(ft\. \b.+\b)|(\(feat\.?.+\)))" 
# title_feat_re = r"\s?(?:(ft\. \b\w+\b)|(\(feat\.?.+\)))" # stricter version

def normalized_compare_regex(in1: str, in2: str, strict = True, debug = False):
	"""
	compares 2 strings after normalization
	- e.g. 2:09 matches 02:09  
	- e.g. Sci-Fi matches Sci—Fi  
	:param strict: if off, it will check if in1 is a substring of in2 rather than direct comparison
	"""
	expr = [in1.lower().strip(), in2.lower().strip()]
	for i in range(len(expr)):
		expr[i] = re.sub(leading_zero_re, "", expr[i]) 
		expr[i] = re.sub(hyphens_re, "-", expr[i])
		expr[i] = re.sub(title_feat_re, "", expr[i])
		expr[i] = expr[i].strip()
	
	if debug:
		print(f"e1: {in1} e2: {in2}, strict:{strict}")
		print(f"out: e1: {expr[0]} e2: {expr[1]}")

	return expr[0] == expr[1] if strict else expr[0] in expr[1]

def check_bareartist_match(artist: str, a_dict: MBArtist):
	"""fuzzy song artist (single/bare) matching"""
	return artist == a_dict["name"] or artist.lower() == a_dict["name"].lower() \
		or artist == a_dict["sort-name"] or artist.lower() == a_dict["sort-name"].lower()

def check_artist_match(artist: str, acred_list: list[MBArtistCredit]):
	"""fuzzy song artist matching (matches serveral artists as well)"""
	if len(acred_list) > 1:
		# not using ARTIST_SEPARATOR here because ytmusic joins artists by &
		joinphrase = str(acred_list[0].get("joinphrase")).strip() or "&" 
		yt_artists = [a.strip() for a in artist.split(joinphrase)]
		
		all_artists_match = True
		for yta in yt_artists:
			found_match = False
			for acred in acred_list:
				if check_bareartist_match(yta, acred["artist"]):
					found_match = True
					break
			if not found_match:
				all_artists_match = False
				break
		
		return all_artists_match
	else:
		return check_bareartist_match(artist, acred_list[0]["artist"])

def check_barealbum_match(album: str, r_dict: MBRelease):
	"""semi-strict album match checker"""
	return album == r_dict["title"] or album.replace("(Single)", "").strip() == r_dict["title"] \
		or album.lower() == r_dict["title"].lower() or album.replace("(Single)", "").strip().lower() == r_dict["title"].lower() \
		or normalized_compare_regex(album, r_dict["title"])

def check_barealbum_match2(album: str, r_dict: MBRelease):
	"""looser check_barealbum_match if title_match and artist_match are both true """
	return album in r_dict["title"] or album.replace("(Single)", "").strip() in r_dict["title"] \
		or album.lower() in r_dict["title"].lower() or album.replace("(Single)", "").strip().lower() in r_dict["title"].lower() \
		or normalized_compare_regex(album, r_dict["title"], strict=False)

def check_album_match(album: str, r_dict: MBRelease, title_match: bool, artist_match: bool):
	"""fuzzy song album matching"""
	if title_match and artist_match:
		# exception: if title & artist match, allow mbid album to be a superset (contain) album needle
		# e.g. album="Meet the Woo" would match "Meet the Woo, V.2", but not the other way around
		# this is pretty damn loose at this point but we trust in MusicBrainz API result ordering
		return check_barealbum_match2(album, r_dict)
	else:
		return check_barealbum_match(album, r_dict)

def check_title_match(title: str, r_dict: MBRecording, debug = False):
	"""fuzzy song title matching"""
	return title == r_dict["title"] or title.lower() == r_dict["title"].lower() \
		or normalized_compare_regex(title, r_dict["title"], debug=debug)

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
		album: str = "",
		debug = False,
		cache_lifetime_seconds = 60
	):
		if title == "":
			raise Exception("title is required")
		self.title = clean_title(title)
		self.artist = artist
		self.album = album
		self.base = "https://musicbrainz.org/ws/2"
		self.default_params = { "fmt": "json" }
		self.req = CachedSession("mbtag", expire_after=cache_lifetime_seconds)
		self.head = { "User-Agent": f"shiradl+mbtag/{shiraver} ( https://github.com/KraXen72/shira )" }

		self.song_dict = None # MBRecording
		self.artist_dict = None # MBArtistCredit
		self.album_dict = None # MBRelease

		self.mb_releasetrackid = None # song mbid
		self.mb_releasegroupid = None # album mbid
		self.mb_artistid = None # artist mbid
		self.debug = debug

	def fetch_song(self):
		"""
		ping mb api to get song (/recording)
		subsequently calls fetch_arist if nothing is found
		"""
		params = {
			"query": f'{self.title} AND artist:"{self.artist}" AND release:"{self.album}"',
			**self.default_params
		}
		res = self.req.get(f"{self.base}/recording", params=params, headers=self.head)
		if self.debug:
			print(res.url)
			print("fetch_song query:", params["query"])
		if res.status_code >= 200 and res.status_code < 300:
			resjson = json.loads(res.text)
			self.save_song_dict(resjson["recordings"])

	def fetch_artist(self):
		"""ping mb api to get artist (/artist)"""
		params = {
			"query": self.artist,
			**self.default_params
		}
		res = self.req.get(f"{self.base}/artist", params=params, headers=self.head)
		if self.debug:
			print(res.url)
			print("fetch_artist query:", params["query"])
		if res.status_code >= 200 and res.status_code < 300:
			resjson = json.loads(res.text)
			self.save_artist_dict(resjson["artists"])

	def _debug_print_track(self, track: MBRecording, titm: bool, artm: bool, albm: bool):
		if not self.debug:
			return
		print(f"matches: title:{titm}, artist:{artm}, album:{albm}")
		print(track["title"], [r["title"] for r in track["releases"]])

	def save_song_dict(self, tracks: list[MBRecording]):
		"""find the most similar song"""

		if self.debug:
			f = open("info.json", "w", encoding="utf8")
			json.dump(tracks, f, indent=4, ensure_ascii=False)
			f.close()
			print("looking for:")
			print("title:", self.title)
			print("artist:", self.artist)
			print("album:", self.album)
		
		for t in tracks:
			if ("artist-credit" not in t) or (len(t["artist-credit"]) == 0) or ("releases" not in t) or (len(t["releases"]) == 0):
				continue

			title_match = check_title_match(self.title, t, self.debug)
			artist_match = False
			album_match = False
			
			if check_artist_match(self.artist, t["artist-credit"]):
				self.mb_artistid = get_mb_artistids(t["artist-credit"])
				self.artist_dict = t["artist-credit"]
				artist_match = True
				
			for a in t["releases"]:
				if check_album_match(self.album, a, title_match, artist_match):
					self.mb_releasegroupid = a["release-group"]["id"]
					self.album_dict = a
					album_match = True
					self._debug_print_track(t, title_match, artist_match, album_match)
					break
				
			if title_match and artist_match and album_match:
				self.mb_releasetrackid = t["id"]
				self.song_dict = t
				self._debug_print_track(t, title_match, artist_match, album_match)
				break
			self._debug_print_track(t, title_match, artist_match, album_match)	
		
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
		return_val = None
		if self.song_dict is None:
			return None
		elif self.song_dict.get("first-release-date") is not None:
			return_val = self.song_dict.get("first-release-date")
		else:
			for r in self.song_dict["releases"]:
				if "date" not in r:
					continue
				return_val = r["date"]
				break

		if return_val is not None:
			if re.match(r"^\d{8}$", return_val) or re.match(r"^\d{4}-\d{2}-\d{2}$", return_val):
				return return_val
			elif re.match(r"^\d{4}-\d{2}$", return_val):
				return return_val + "-01"
			elif re.match(r"^\d{6}$", return_val):
				return return_val + "01"
			elif re.match(r"^\d{4}$", return_val):
				return return_val + "-01-01"
			else:
				print(f"unknown date format {return_val}, skipping date metadata")

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


	def get_mb_tags(self):
		"""
		quickly get {title, artist, album} if it was fetched from MB,  
		otherwise all 3 will be None.  
		Does no fetching itself.
		"""
		artist = None
		if self.artist_dict is not None:
			artist = self.artist_dict[0]["artist"]["name"] if isinstance(self.artist_dict, list) else self.artist_dict["name"]
		return {
			"title": self.song_dict.get("title") if self.song_dict is not None else None,
			"artist": artist,
			"album": self.album_dict.get("title") if self.album_dict is not None else None,
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

	