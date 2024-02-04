import functools
import json
import re
import shutil
import subprocess
from pathlib import Path

from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

from .metadata import clean_title, get_year
from .tagging import Tags, get_cover

ITAG_AAC_128 = "140"
ITAG_AAC_256 = "141"
ITAG_OPUS_128 = "251"

class Dl:
	def __init__(
		self,
		final_path: Path,
		temp_path: Path,
		cookies_location: Path,
		ffmpeg_location: Path,
		itag: str,
		cover_size: int,
		cover_format: str,
		cover_quality: int,
		template_folder: str,
		template_file: str,
		exclude_tags: str | None,
		truncate: int,
		dump_json: bool = False,
		**kwargs,
	):

		self.ytmusic = YTMusic()
		self.final_path = final_path
		self.temp_path = temp_path
		self.cookies_location = cookies_location
		self.ffmpeg_location = ffmpeg_location
		self.itag = itag
		self.cover_size = cover_size
		self.cover_format = cover_format
		self.cover_quality = cover_quality
		self.template_folder = template_folder
		self.template_file = template_file
		self.exclude_tags = [i.lower() for i in exclude_tags.split(",")] if exclude_tags is not None else []
		self.truncate = None if truncate is not None and truncate < 4 else truncate

		self.dump_json = dump_json
		self.tags: Tags | None = None 
		self.soundcloud = False
		self.default_ydl_opts = {"progress": True, "quiet": True, "no_warnings": True, "fixup": "never"}

	def get_ydl_extract_info(self, url) -> dict:
		ydl_opts: dict[str, str | bool] = {"quiet": True, "no_warnings": True, "extract_flat": True}
		if self.cookies_location is not None:
			ydl_opts["cookiefile"] = str(self.cookies_location)
		with YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=False)
			if info is None:
				raise Exception(f"Failed to extract info for {url}")
			return info

	def get_download_queue(self, url):
		url = url.split("&")[0]
		download_queue = []
		ydl_extract_info: dict = self.get_ydl_extract_info(url)
		
		if self.dump_json:
			# audio_formats = [ x for x in ydl_extract_info["formats"] if "acodec" in x and x["acodec"] != "none" ]
			# audio_formats = sorted(audio_formats, key = lambda x: x["quality"], reverse=True)

			f = open("info.json", "w", encoding="utf8")
			json.dump(ydl_extract_info, f, indent=4, ensure_ascii=False)
			f.close()

		if "soundcloud" in ydl_extract_info["webpage_url"] :
			# raise Exception("Not a YouTube URL")
			if str(self.final_path) == "./YouTube Music":
				self.final_path = Path("./SoundCloud")
			self.soundcloud = True
		if "MPREb_" in ydl_extract_info["webpage_url_basename"]:
			ydl_extract_info = self.get_ydl_extract_info(ydl_extract_info["url"])
		if "playlist" in ydl_extract_info["webpage_url_basename"]:
			download_queue.extend(ydl_extract_info["entries"])
		if "watch" in ydl_extract_info["webpage_url_basename"] or self.soundcloud:
			download_queue.append(ydl_extract_info)
		return download_queue

	def get_artist(self, artist_list):
		if len(artist_list) == 1:
			return artist_list[0]["name"]
		return ", ".join([i["name"] for i in artist_list][:-1]) + f' & {artist_list[-1]["name"]}'

	def get_ytmusic_watch_playlist(self, video_id):
		if self.soundcloud:
			return None
		ytmusic_watch_playlist = self.ytmusic.get_watch_playlist(video_id)
		if ytmusic_watch_playlist is None or isinstance(ytmusic_watch_playlist, str):
			raise Exception(f"Track is not available (None or string) {video_id}")
		
		if not ytmusic_watch_playlist["tracks"][0]["length"] and ytmusic_watch_playlist["tracks"][0].get("album"): # type: ignore
			raise Exception(f"Track is not available {video_id}")
		if not ytmusic_watch_playlist["tracks"][0].get("album"): # type: ignore
			return None
		return ytmusic_watch_playlist

	def search_track(self, title):
		return self.ytmusic.search(title, "songs")[0]["videoId"]

	@functools.lru_cache
	def get_ytmusic_album(self, browse_id):
		return self.ytmusic.get_album(browse_id)

	def get_tags(self, ytmusic_watch_playlist, track: dict[str, str | int]) -> Tags:
		if self.tags is None:
			return self.__collect_tags(ytmusic_watch_playlist, track)
		else:
			return self.tags
		
	def __collect_tags(self, ytmusic_watch_playlist, track: dict[str, str | int]):
		"""collects tag information into self.tags"""
		if self.tags is not None:
			return self.tags
		
		video_id = ytmusic_watch_playlist["tracks"][0]["videoId"]
		ytmusic_album: dict = self.ytmusic.get_album(ytmusic_watch_playlist["tracks"][0]["album"]["id"])

		_release_year, _release_date = get_year(track, ytmusic_album)
		tags: Tags = {
			"title": clean_title(ytmusic_watch_playlist["tracks"][0]["title"]),
			"album": ytmusic_album["title"],
			"album_artist": self.get_artist(ytmusic_album["artists"]),
			"artist": self.get_artist(ytmusic_watch_playlist["tracks"][0]["artists"]),
			"comment": f"https://music.youtube.com/watch?v={video_id}",
			"track": 1,
			"track_total": ytmusic_album["trackCount"],
			"release_date": _release_date,
			"release_year": _release_year,
			"cover_url": f'{ytmusic_watch_playlist["tracks"][0]["thumbnail"][0]["url"].split("=")[0]}'
			+ f'=w{self.cover_size}-l{self.cover_quality}-{"rj" if self.cover_format == "jpg" else "rp"}'
		}

		for i, video in enumerate(self.get_ydl_extract_info(f'https://www.youtube.com/playlist?list={str(ytmusic_album["audioPlaylistId"])}')["entries"]):
			if video["id"] == video_id:
				try:
					if ytmusic_album["tracks"][i]["isExplicit"]:
						tags["rating"] = 1
					else:
						tags["rating"] = 0
				except IndexError:
					tags["rating"] = 0
				finally:
					tags["track"] = i + 1
				break
		if ytmusic_watch_playlist["lyrics"]:
			lyrics = self.ytmusic.get_lyrics(ytmusic_watch_playlist["lyrics"])["lyrics"]
			if lyrics is not None:
				tags["lyrics"] = lyrics
		
		self.tags = tags
		return self.tags

	def get_sanizated_string(self, dirty_string, is_folder):
		dirty_string = re.sub(r'[\\/:*?"<>|;]', "_", dirty_string)
		if is_folder:
			dirty_string = dirty_string[: self.truncate]
			if dirty_string.endswith("."):
				dirty_string = dirty_string[:-1] + "_"
		else:
			if self.truncate is not None:
				dirty_string = dirty_string[: self.truncate - 4]
		return dirty_string.strip()

	def get_temp_location(self, song_id):
		if self.soundcloud:
			return self.temp_path / f"{song_id}.mp3"
		return self.temp_path / f"{song_id}.m4a"

	def get_fixed_location(self, song_id):
		if self.soundcloud:
			return self.temp_path / f"{song_id}_fixed.mp3"
		return self.temp_path / f"{song_id}_fixed.m4a"

	def get_final_location(self, tags, extension = ".m4a", is_single = False, single_folders = False):
		final_location_folder = self.template_folder.split("/")
		final_location_file = self.template_file.split("/")

		if is_single and not single_folders and self.template_folder.endswith("/{album}"):
			folder = self.template_folder[:-8]
			if len(folder.strip()) == 0:
				folder = "./"
			final_location_folder = folder.split("/")
			if (self.template_file.startswith("{track:02d} ")):
				locfile = self.template_file[12:]
				final_location_file = "{title}".split("/") if locfile.strip() == "" else locfile.split("/")
			
		final_location_folder = [self.get_sanizated_string(i.format(**tags), True) for i in final_location_folder]
		final_location_file = [self.get_sanizated_string(i.format(**tags), True) for i in final_location_file[:-1]] + [
			self.get_sanizated_string(final_location_file[-1].format(**tags), False) + extension
		]
		return self.final_path.joinpath(*final_location_folder).joinpath(*final_location_file)

	def get_cover_location(self, final_location):
		return final_location.parent / f"Cover.{self.cover_format}"

	def download(self, video_id, temp_location):
		ydl_opts = {**self.default_ydl_opts, "format": self.itag, "outtmpl": str(temp_location)}

		if self.cookies_location is not None:
			ydl_opts["cookiefile"] = str(self.cookies_location)
		with YoutubeDL(ydl_opts) as ydl:
			ydl.download("music.youtube.com/watch?v=" + video_id)

	def download_souncloud(self, url, temp_location):
		# opus is obviously a better format, however:
		# it's debatable whether soundcloud's mp3 is better than their opus
		# because they might just use lower quality audio for opus (there have been complaints)
		# this can be possibly later changed, for now we'll stick to mp3
		ydl_opts = {**self.default_ydl_opts, "format": "mp3", "outtmpl": str(temp_location)}

		if self.cookies_location is not None:
			ydl_opts["cookiefile"] = str(self.cookies_location)
		with YoutubeDL(ydl_opts) as ydl:
			ydl.download(url)

	def fixup(self, temp_location, fixed_location):
		fixup = [self.ffmpeg_location, "-loglevel", "error", "-i", temp_location]
		if self.soundcloud is False and self.itag == ITAG_OPUS_128:
			fixup.extend(["-f", "mp4"])
		subprocess.run([*fixup, "-movflags", "+faststart", "-c", "copy", fixed_location], check=True)	

	def move_to_final_location(self, fixed_location, final_location):
		final_location.parent.mkdir(parents=True, exist_ok=True)
		shutil.move(fixed_location, final_location)

	def save_cover(self, tags, cover_location):
		with open(cover_location, "wb") as f:
			f.write(get_cover(tags["cover_url"]))

	def cleanup(self):
		shutil.rmtree(self.temp_path)
