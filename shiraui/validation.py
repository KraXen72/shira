"""Pre-flight validation of a JobSpec. Pure Python, no Qt.

The headline case is naming templates. shiradl formats them per track, so an
unknown key like {genre} raises KeyError on *every* track. That is caught by
cli.py's per-track handler and surfaces only as "Done (12 error(s))" with no
indication of the cause. Catching it here turns a baffling failure into a
sentence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from urllib.parse import urlparse

# Always present on every Tags dict (shiradl/tagging.py).
SAFE_KEYS = {
	"title", "album", "artist", "albumartist",
	"track", "tracktotal", "year", "date",
}
# Declared NotRequired -- present on some paths only, so using them is a
# warning rather than an error.
OPTIONAL_KEYS = {"comments", "lyrics", "rating"}
NUMERIC_KEYS = {"track", "tracktotal"}

KNOWN_HOSTS = (
	"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
	"music.youtube.com", "soundcloud.com", "www.soundcloud.com",
	"on.soundcloud.com", "m.soundcloud.com",
)

ERROR = "error"
WARNING = "warning"


@dataclass
class Issue:
	severity: str
	field: str
	message: str

	@property
	def blocking(self) -> bool:
		return self.severity == ERROR


def validate_template(text: str, field: str, label: str) -> list[Issue]:
	issues: list[Issue] = []
	if not text.strip():
		issues.append(Issue(ERROR, field, f"{label} can't be empty."))
		return issues

	try:
		parsed = list(Formatter().parse(text))
	except ValueError as e:
		issues.append(Issue(ERROR, field, f"{label} isn't valid: {e}"))
		return issues

	used: list[str] = []
	for _literal, name, spec, _conv in parsed:
		if name is None:
			continue
		# "{albumartist[0]}" / "{a.b}" -- take the root identifier.
		root = name.split(".")[0].split("[")[0].strip()
		if not root:
			issues.append(Issue(
				ERROR, field,
				f"{label} has an empty {{}} placeholder.",
			))
			continue
		used.append(root)

		if root not in SAFE_KEYS and root not in OPTIONAL_KEYS:
			issues.append(Issue(
				ERROR, field,
				f"There's no tag called '{root}'. You can use: "
				+ ", ".join(sorted(SAFE_KEYS)) + ".",
			))
			continue

		if root in OPTIONAL_KEYS:
			issues.append(Issue(
				WARNING, field,
				f"'{root}' isn't available for every track, so some downloads "
				f"will fail. Safer options: " + ", ".join(sorted(SAFE_KEYS)) + ".",
			))

		# "{title:02d}" raises ValueError at format time.
		if spec and spec.rstrip().endswith(("d", "n")) and root not in NUMERIC_KEYS:
			issues.append(Issue(
				ERROR, field,
				f"'{root}' is text, so it can't be numbered with ':{spec}'. "
				f"Number formats only work on: " + ", ".join(sorted(NUMERIC_KEYS)) + ".",
			))

	if not used:
		issues.append(Issue(
			WARNING, field,
			f"{label} doesn't use any tags, so every track would get the "
			f"same name and overwrite the last.",
		))
	return issues


def sample_preview(template_folder: str, template_file: str) -> str:
	"""Render both templates against a fixed sample, for the live preview."""
	sample = {
		"title": "Nude", "album": "In Rainbows", "artist": "Radiohead",
		"albumartist": "Radiohead", "track": 5, "tracktotal": 10,
		"year": "2007", "date": "2007-10-10",
		"comments": "", "lyrics": "", "rating": 0,
	}
	try:
		folder = template_folder.format(**sample)
		name = template_file.format(**sample)
	except (KeyError, ValueError, IndexError):
		return "—"
	parts = [p for p in folder.replace("\\", "/").split("/") if p.strip()]
	return " \\ ".join([*parts, name + ".m4a"])


def clean_urls(raw: str) -> tuple[list[str], list[str]]:
	"""Split the URL box into (accepted, rejected), preserving order.

	Duplicates are dropped. The old GUI decided links-file mode with
	``url.endswith(".txt")``, which misread both a URL ending in .txt and a
	links file with any other extension; the file is now read client-side, so
	only real URLs reach here.
	"""
	accepted: list[str] = []
	rejected: list[str] = []
	seen: set[str] = set()

	for line in raw.splitlines():
		item = line.strip()
		if not item or item.startswith("#"):
			continue
		parsed = urlparse(item)
		if parsed.scheme not in ("http", "https") or not parsed.netloc:
			rejected.append(item)
			continue
		if item in seen:
			continue
		seen.add(item)
		accepted.append(item)
	return accepted, rejected


def is_known_host(url: str) -> bool:
	try:
		return urlparse(url).netloc.lower() in KNOWN_HOSTS
	except ValueError:
		return False


def validate(spec) -> list[Issue]:
	"""Full check of a JobSpec. Any Issue with severity ERROR blocks the run."""
	issues: list[Issue] = []

	if not spec.urls:
		issues.append(Issue(ERROR, "urls", "Add at least one link to download."))
	for url in spec.urls:
		if not is_known_host(url):
			issues.append(Issue(
				WARNING, "urls",
				f"{url} isn't a YouTube, YouTube Music or SoundCloud address. "
				f"Shira may not be able to download it.",
			))

	dest = Path(spec.final_path)
	if not str(dest).strip():
		issues.append(Issue(ERROR, "final_path", "Choose a folder to save music into."))
	else:
		probe = dest if dest.exists() else dest.parent
		if not probe.exists():
			issues.append(Issue(
				ERROR, "final_path",
				f"The folder {dest} doesn't exist and can't be created.",
			))
		elif probe.exists() and not probe.is_dir():
			issues.append(Issue(
				ERROR, "final_path", f"{probe} is a file, not a folder.",
			))

	issues += validate_template(spec.template_folder, "template_folder", "The folder pattern")
	issues += validate_template(spec.template_file, "template_file", "The file pattern")

	# Defence in depth. get_sanizated_string already neutralises ".." in
	# shiradl 1.8.5, but that is upstream behaviour we do not control.
	try:
		rendered = sample_preview(spec.template_folder, spec.template_file)
		if rendered != "—":
			joined = (dest / rendered.replace(" \\ ", "/")).resolve()
			if not str(joined).startswith(str(dest.resolve())):
				issues.append(Issue(
					ERROR, "template_folder",
					"That naming pattern would save files outside your chosen folder.",
				))
	except (OSError, ValueError):
		pass

	if spec.cookies_enabled:
		cookies = spec.cookies_path.strip()
		if not cookies:
			issues.append(Issue(ERROR, "cookies", "Choose your cookies.txt file, or untick the box."))
		elif not Path(cookies).is_file():
			# The old GUI silently dropped the flag here and downloaded
			# without cookies, so the box appeared to do nothing.
			issues.append(Issue(ERROR, "cookies", f"No cookies file at {cookies}."))

	if spec.cover_img.strip() and not Path(spec.cover_img.strip()).exists():
		issues.append(Issue(ERROR, "cover_img", f"No image or folder at {spec.cover_img.strip()}."))

	if not 0 <= spec.cover_size <= 16383:
		issues.append(Issue(ERROR, "cover_size", "Artwork size must be between 0 and 16383."))
	if not 1 <= spec.cover_quality <= 100:
		issues.append(Issue(ERROR, "cover_quality", "Artwork quality must be between 1 and 100."))

	return issues
