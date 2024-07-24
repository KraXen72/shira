<h1 align="center">shira</h1>
<p align="center"><img src="logo.svg" height=200></img></p>
<h4 align="center">A smart music downloader</h4>
<p align="center">
<em>Download music from YouTube, YouTube Music and Soundcloud, </br> with great metadata and little effort.</em>
</p>

## Installation
- Have [python](https://www.python.org/downloads/) (**3.11+**) and [git](https://git-scm.com/downloads) installed
- Have `ffmpeg` installed (See [Installing ffmpeg](#installing-ffmpeg)) and added to PATH, or [specify it with `--ffmpeg-location`](#configuration)/[config](#configuration)
- `git clone https://github.com/KraXen72/shira`, `cd shira`
- `pip install -r requirements.txt`
  
On some systems, you might have to use the `python3` or `python3.x` command instead of `python`  
**Guides**: [Using a cookies file](#setting-a-cookies-file), [Troubleshooting](#troubleshooting)


## Usage Examples
- `python -m shiradl https://music.youtube.com/watch?v=HdX2COsY2Xk` **YouTube Music**
- `python -m shiradl "https://music.youtube.com/watch?v=8YwKlPH93Ps&list=PLC1og_v3eb4jE0bmdkWtizrSQ4zt86-3D"`
- `python -m shiradl https://www.youtube.com/watch?v=X0-AvRA7kB0` **YouTube (video)**
- `python -m shiradl https://soundcloud.com/neffexmusic/fight-back` **SoundCloud**
- `python -m shiradl https://music.youtube.com/playlist?list=PLC1og_v3eb4jE0bmdkWtizrSQ4zt86-3D` **Album/Playlist**
- `python -m shiradl -u ./links.txt` **List of links to download**
  - [See all cli options/flags](#Configuration)

## Goals
- Provide an easy way to download audio from YouTube Music, YouTube or SoundCloud
  - Instead of a GUI/manual input for some steps like in [tiger](https://github.com/KraXen72/tiger), shira requires no additional user input once ran.
- Provide objectively correct or at least very reasonable music metadata & properly tag music files.
  - <ins>objectively correct</ins>: Shira queries the [MusicBrainz Database](https://musicbrainz.org) and [YouTube Music's API](https://github.com/sigma67/ytmusicapi) to get metadata
  - <ins>very reasonable</ins>: When downloading a Youtube video, tags will be inferred from the video info: `title`, `channel_name`, `description`, `upload_date`, etc.

## Tagging
- Adds a [lot of metadata](#tag-variables) to music files, in these [native tags](https://github.com/OxygenCobalt/Auxio/wiki/Supported-Metadata) (m4a, mp3)
- Embeds proper `m4a` (iTunes) and `.mp3` (ID3v2.4) tags with [mediafile](https://github.com/beetbox/mediafile)
- Uses [YouTube Music's API](https://github.com/sigma67/ytmusicapi) to get info.
- Uses [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API) to resolve MusicBrainz ID's from their api 
  - `track`, `album`, `artist`, `albumartist` ids
    - falls back to `artist`, `albumartist` if this recording can't be found, but artist can.
- uses my custom smart-metadata system from [tiger](https://github.com/KraXen72/tiger) for non-music videos
  - collects as much information as possible for each tag, and selects the value with most occurences (with fallbacks)
- Cleans up messy titles into more reasonable ones:
  - `IDOL【ENGLISH EDM COVER】「アイドル」 by ARTIST【Artist1 x @Artist2 】` =>
  - `IDOL [ENGLISH EDM COVER] [アイドル] by ARTIST`
- Is smart about turning a video's thumbnail into a square album cover
  
<details id="smartcrop">
<summary>More info about YouTube thumbnail to Album Art algorithm</summary>
<ol>
<li>samples 4 pixels near the corners of the thumbnail (which is first smoothed and reduced to 64 colors)</li>
<li>decides to crop if average of standard deviations of r, g and b color channels from each sample point is lower than a than a treshold</li>
<li>otherwise pads the image to 1:1 with it's dominant color</li>
</ol>
</details>

## About & Credits
- **This software is for educational purposes only and comes without any warranty**; See [LICENSE](./LICENSE).
- Credits for copyright-free example tracks used: [Andy Leech](https://soundcloud.com/andyleechmusic), [4lienetic](https://soundcloud.com/4lienetic), [NEFFEX](https://soundcloud.com/neffexmusic)
- The name **Shira** was inspired by a saber-toothed [tiger](https://github.com/KraXen72/tiger) from [Ice Age](https://iceage.fandom.com/wiki/Shira). 
- It also means ['poetry', 'singing' or 'music'](https://www.wikiwand.com/en/Shira_(given_name)) in Hebrew.
- The project is based on my previous [YouTube downloader tiger](https://github.com/KraXen72/tiger) and [Glomatico's YouTube Music Downloader](https://github.com/glomatico/gytmdl)
- Project logo is based on this [DeviantArt fanart](https://www.deviantart.com/f-a-e-l-e-s/art/Ice-age-5-Shira-and-Diego-757174602), which has been modified, vectorised and cleaned up.

### Support development
[![Recurring donation via Liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/KraXen72) [![One-time donation via ko-fi.com](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/kraxen72)  
Any donations are highly appreciated! <3

## Configuration
Shira can be configured using the command line arguments or the config file.  
The config file is created automatically when you run shira for the first time at `~/.shiradl/config.json` on Linux and `%USERPROFILE%\.shiradl\config.json` on Windows. Config file values can be overridden using command line arguments.

| Command line argument / Config file key | Description | Default value |
| --- | --- | --- |
| `-f`, `--final-path` / `final_path` | Path where the downloaded files will be saved. | `./YouTube Music` |
| `-t`, `--temp-path` / `temp_path` | Path where the temporary files will be saved. | `./temp` |
| `-c`, `--cookies-location` / `cookies_location` | Location of the cookies file. | `null` |
| `--ffmpeg-location` / `ffmpeg_location` | Location of the FFmpeg binary. | `ffmpeg` |
| `--config-location` / - | Location of the config file. | `<home folder>/.shiradl/config.json` |
| `-i`, `--itag` / `itag` | Itag (audio quality/format). [More info](#itags) | `140` |
| `--cover-size` / `cover_size` | Size of the cover.  `size >= 0` and `<= 16383` | `1200` |
| `--cover-format` / `cover_format` | Format of the cover. `jpg` or `png` | `jpg` |
| `--cover-quality` / `cover_quality` | JPEG quality of the cover.  [1<=x<=100] | `94` |
| `--cover-img` / `cover_img` | Path to image or folder of images. [More info](#cover-img)  | `null` |
| `--cover-crop` / `cover_crop` |  'crop' takes a 1:1 square from the center, pad always pads top & bottom. `auto`, `crop` or `pad` | `auto` - [More info](#smartcrop) |
| `--template-folder` / `template_folder` | Template of the album folders as a format string. | `{albumartist}/{album}` |
| `--template-file` / `template_file` | Template of the track files as a format string. | `{track:02d} {title}` |
| `-e`, `--exclude-tags` / `exclude_tags` | List of tags to exclude from file tagging separated by commas without spaces. | `null` |
| `--truncate` / `truncate` | Maximum length of the file/folder names. | `40` |
| `-l`, `--log-level` / `log_level` | Log level. | `INFO` |
| `-s`, `--save-cover` / `save_cover` | Save cover as a separate file. | `false` |
| `-o`, `--overwrite` / `overwrite` | Overwrite existing files. | `false` |
| `-p`, `--print-exceptions` / `print_exceptions` | Print exceptions. | `false` |
| `-u`, `--url-txt` / - | Read URLs as location of text files containing URLs. | `false` |
| `-n`, `--no-config-file` / - | Don't use the config file. | `false` |
| `-w`, `--single-folder` / - | Wrap singles in their own folder instead of placing them directly into artist's folder. | `false` |

### Itags
The following itags are available:
- `140` (128kbps AAC) - default, because it's the result of `bestaudio/best` on a free account
- `141` (256kbps AAC) - use if you have premium alongside `--cookies-location`
- `251` (128kbps Opus) - most stuff will error with `Failed to check URL 1/1`. Better to use `140`
  
SoundCloud will always download in 128kbps MP3
- SoundCloud also offers OPUS, which is currently not supported. [Some people were complaining](https://www.factmag.com/2018/01/04/soundcloud-mp3-opus-format-sound-quality-change-64-128-kbps/) that the quality is worse  
- [These are questionable claims](https://old.reddit.com/r/Techno/comments/bzodax/soundcloud_compression_128kbps_mp3_vs_64_kbps/) at best, but better safe than sorry.   

### Tag variables
The following variables can be used in the template folder/file and/or in the `exclude_tags` list:  
`title`, `album`, `artist`, `albumartist`, `track`, `tracktotal`, `year`, `date`, `cover`, `comments`, `lyrics`, `media_type`, `rating`, `track`, `tracktotal`, `mb_releasetrackid`, `mb_releasegroupid`, `mb_artistid`, `mb_albumartistid`  
To exclude all musicbrainz tags, you can add `mb*` to `exclude_tags`. (This does not work for other types of tags).

### Cover formats
Can be either `jpg` or `png`.

### Cover img
- Pass in a path to an image file, and it will get used for all of the links you're currently downloading.
- Pass in a path to a folder, and the script will use the first image matching the track/video id and jpeg/png format
  - You don't have to create covers for all tracks/videos in the playlist/album/etc.
  - SoundCloud will also consider images based on the URL slug instead of id
  - *for example*: `https://soundcloud.com/yatashi-gang-63564467/lovely-bastards-yatashigang` => `lovely-bastards-yatashigang.jpg` or `.png`

## Troubleshooting
- `python: No module named shiradl` 
  - Make sure you are not already in the `shiradl` directory, e.g. `/shira/shiradl`. if yes, move up one directory with `cd ..` and retry.
- I really need to run this on `python` 3.8+ and updating to 3.11+ is not an option
  - run `pip install typing-extensions` and modify `tagging.py` accordingly:
  ```diff
  - from typing import NotRequired, TypedDict
  + from typing_extensions import NotRequired, TypedDict
  ```

### Installing ffmpeg
#### Installing ffmpeg with scoop
- Scoop is a package manager for windows. It allows easy installing of programs and their updating from the commandline.
- Install [scoop](https://scoop.sh) by running a powershell command (on their website)
- Run `scoop install main/ffmpeg`
- Scoop automatically adds it to path. you can update ffmpeg by doing `scoop update` and `scoop update ffmpeg`/`*`
- If installing scoop/with scoop is not an option, continue reading:
#### Installing ffmpeg on Windows (manual install)
- Related: [Comprehensive tutorial with screenshots](https://phoenixnap.com/kb/ffmpeg-windows)
- Download an auto-built zip of latest ffmpeg: [download](https://www.gyan.dev/ffmpeg/builds/) / [mirror](https://github.com/BtbN/FFmpeg-Builds/releases).
- Extract it somewhere, for example into `C:\ffmpeg`. It's best if the path doesen't have spaces.
##### Adding ffmpeg to PATH
- Look for `Edit the system environment variables` in the Start Menu, launch it.
- Find the `Path` user variable, click `Edit`
- Click `New` on the side and enter the path to the `ffmpeg\bin` folder which has `ffmpeg.exe` in it, e.g. `C:\ffmpeg\bin`
- Click `Ok`. To verify that `ffmpeg` is installed, run `ffmpeg -version` in the terminal.
#### Pointing to ffmpeg manually
- If you do not want to add `ffmpeg` to path, you can point to it manually.
- Use the [config](#configuration) option `ffmpeg_location` or the cli flag `--ffmpeg-location` to point to the `ffmpeg.exe` file.
- Keep the `ffplay.exe` and `ffprobe.exe` files in the same directory.
#### Installing ffmpeg on linux
- use your distro's package manager to install `ffmpeg`

### Setting a cookies file
- By setting a cookies file, you can download age restricted tracks, private playlists and songs in 256kbps AAC if you are a premium user.
- You can export your cookies to a file by using this [Google Chrome extension](https://chrome.google.com/webstore/detail/gdocmgbfkjnnpapoeobnolbbkoibbcif) or [Firefox extension](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) on `https://music.youtube.com`

## Contributing
- Please report any bugs in Issues. Pull requests are welcome!
- Fork this repo, [Follow installation steps](#Installation), Make changes, Open a pull request