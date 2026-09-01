"""Typed wrapper over QSettings.

The GUI is authoritative over its own settings: every run passes
``--no-config-file`` so that an unticked checkbox genuinely means false.
Click's flags are one-way (there is no ``--no-overwrite``), so without that
flag a ``true`` sitting in ``~/.shiradl/config.json`` would be injected anyway
and could not be turned off from the UI at all.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings

SCHEMA_VERSION = 1


class SettingsStore:
	def __init__(self) -> None:
		self.s = QSettings("KraXen72", "Shira UI")
		if self.s.value("schema_version") is None:
			self.s.setValue("schema_version", SCHEMA_VERSION)

	def get_str(self, key: str, default: str = "") -> str:
		v = self.s.value(key)
		return default if v is None else str(v)

	def get_int(self, key: str, default: int = 0) -> int:
		v = self.s.value(key)
		if v is None:
			return default
		try:
			return int(v)
		except (TypeError, ValueError):
			return default

	def get_bool(self, key: str, default: bool = False) -> bool:
		v = self.s.value(key)
		if v is None:
			return default
		# QSettings round-trips booleans as the strings "true"/"false" on
		# the Windows registry backend.
		if isinstance(v, str):
			return v.lower() in ("true", "1", "yes")
		return bool(v)

	def get_bytes(self, key: str):
		return self.s.value(key)

	def set(self, key: str, value) -> None:
		self.s.setValue(key, value)

	def sync(self) -> None:
		self.s.sync()

	def reset(self) -> None:
		self.s.clear()
		self.s.setValue("schema_version", SCHEMA_VERSION)
