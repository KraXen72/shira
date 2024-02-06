import struct
import sys

from mutagen._constants import GENRES
from mutagen._file import FileType
from mutagen._tags import PaddingInfo, Tags
from mutagen._util import DictProxy, bchr, cdata, convert_error, get_size, insert_bytes, loadfile, reraise, resize_bytes
from mutagen.mp4 import (
	AtomDataType,
	MP4Chapters,
	MP4Cover,
	MP4FreeForm,
	MP4Info,
	MP4MetadataError,
	MP4MetadataValueError,
	MP4NoTrackError,
	MP4StreamInfoError,
	_find_padding,
	_item_sort_key,
	_key2name,
	_name2key,
	error,
)
from mutagen.mp4._atom import Atom, AtomError, Atoms

# this is a patched version of mutagen's MP4Tags, until they fix it

class MP4Tags(DictProxy, Tags):
	r"""MP4Tags()

	Dictionary containing Apple iTunes metadata list key/values.

	Keys are four byte identifiers, except for freeform ('----')
	keys. Values are usually unicode strings, but some atoms have a
	special structure:

	Text values (multiple values per key are supported):

	* '\\xa9nam' -- track title
	* '\\xa9alb' -- album
	* '\\xa9ART' -- artist
	* 'aART' -- album artist
	* '\\xa9wrt' -- composer
	* '\\xa9day' -- year
	* '\\xa9cmt' -- comment
	* 'desc' -- description (usually used in podcasts)
	* 'purd' -- purchase date
	* '\\xa9grp' -- grouping
	* '\\xa9gen' -- genre
	* '\\xa9lyr' -- lyrics
	* 'purl' -- podcast URL
	* 'egid' -- podcast episode GUID
	* 'catg' -- podcast category
	* 'keyw' -- podcast keywords
	* '\\xa9too' -- encoded by
	* 'cprt' -- copyright
	* 'soal' -- album sort order
	* 'soaa' -- album artist sort order
	* 'soar' -- artist sort order
	* 'sonm' -- title sort order
	* 'soco' -- composer sort order
	* 'sosn' -- show sort order
	* 'tvsh' -- show name
	* '\\xa9wrk' -- work
	* '\\xa9mvn' -- movement

	Boolean values:

	* 'cpil' -- part of a compilation
	* 'pgap' -- part of a gapless album
	* 'pcst' -- podcast (iTunes reads this only on import)

	Tuples of ints (multiple values per key are supported):

	* 'trkn' -- track number, total tracks
	* 'disk' -- disc number, total discs

	Integer values:

	* 'tmpo' -- tempo/BPM
	* '\\xa9mvc' -- Movement Count
	* '\\xa9mvi' -- Movement Index
	* 'shwm' -- work/movement
	* 'stik' -- Media Kind
	* 'hdvd' -- HD Video
	* 'rtng' -- Content Rating
	* 'tves' -- TV Episode
	* 'tvsn' -- TV Season
	* 'plID', 'cnID', 'geID', 'atID', 'sfID', 'cmID', 'akID' -- Various iTunes
	  Internal IDs

	Others:

	* 'covr' -- cover artwork, list of MP4Cover objects (which are
	  tagged strs)
	* 'gnre' -- ID3v1 genre. Not supported, use '\\xa9gen' instead.

	The freeform '----' frames use a key in the format '----:mean:name'
	where 'mean' is usually 'com.apple.iTunes' and 'name' is a unique
	identifier for this frame. The value is a str, but is probably
	text that can be decoded as UTF-8. Multiple values per key are
	supported.

	MP4 tag data cannot exist outside of the structure of an MP4 file,
	so this class should not be manually instantiated.

	Unknown non-text tags and tags that failed to parse will be written
	back as is.
	"""

	def __init__(self, *args, **kwargs):
		self._failed_atoms = {}
		super(MP4Tags, self).__init__()
		if args or kwargs:
			self.load(*args, **kwargs)

	def load(self, atoms, fileobj):
		try:
			path = atoms.path(b"moov", b"udta", b"meta", b"ilst")
		except KeyError as key:
			raise MP4MetadataError(key)

		free = _find_padding(path)
		self._padding = free.datalength if free is not None else 0

		ilst = path[-1]
		for atom in ilst.children:
			ok, data = atom.read(fileobj)
			if not ok:
				raise MP4MetadataError("Not enough data")

			try:
				if atom.name in self.__atoms:
					info = self.__atoms[atom.name]
					info[0](self, atom, data)
				else:
					# unknown atom, try as text
					self.__parse_text(atom, data, implicit=False)
			except MP4MetadataError:
				# parsing failed, save them so we can write them back
				self._failed_atoms.setdefault(_name2key(atom.name), []).append(data)

	def __setitem__(self, key, value):
		if not isinstance(key, str):
			raise TypeError("key has to be str")
		self._render(key, value)
		super(MP4Tags, self).__setitem__(key, value)

	@classmethod
	def _can_load(cls, atoms):
		return b"moov.udta.meta.ilst" in atoms

	def _render(self, key, value):
		atom_name = _key2name(key)[:4]
		if atom_name in self.__atoms:
			render_func = self.__atoms[atom_name][1]
			render_args = self.__atoms[atom_name][2:]
		else:
			render_func = type(self).__render_text
			render_args = []

		return render_func(self, key, value, *render_args)

	@convert_error(IOError, error)
	@loadfile(writable=True)
	def save(self, filething=None, padding=None):

		values = []
		items = sorted(self.items(), key=lambda kv: _item_sort_key(*kv))
		for key, value in items:
			try:
				values.append(self._render(key, value))
			except (TypeError, ValueError) as s:
				reraise(MP4MetadataValueError, s, sys.exc_info()[2])

		for key, failed in self._failed_atoms.items():
			# don't write atoms back if we have added a new one with
			# the same name, this excludes freeform which can have
			# multiple atoms with the same key (most parsers seem to be able
			# to handle that)
			if key in self:
				assert _key2name(key) != b"----"
				continue
			for data in failed:
				values.append(Atom.render(_key2name(key), data))

		data = Atom.render(b"ilst", b"".join(values))

		# Find the old atoms.
		try:
			atoms = Atoms(filething.fileobj)
		except AtomError as err:
			reraise(error, err, sys.exc_info()[2])

		self.__save(filething.fileobj, atoms, data, padding)

	def __save(self, fileobj, atoms, data, padding):
		try:
			path = atoms.path(b"moov", b"udta", b"meta", b"ilst")
		except KeyError:
			self.__save_new(fileobj, atoms, data, padding)
		else:
			self.__save_existing(fileobj, atoms, path, data, padding)

	def __save_new(self, fileobj, atoms, ilst_data, padding_func):
		hdlr = Atom.render(b"hdlr", b"\x00" * 8 + b"mdirappl" + b"\x00" * 9)
		meta_data = b"\x00\x00\x00\x00" + hdlr + ilst_data

		try:
			path = atoms.path(b"moov", b"udta")
		except KeyError:
			path = atoms.path(b"moov")

		offset = path[-1]._dataoffset

		# ignoring some atom overhead... but we don't have padding left anyway
		# and padding_size is guaranteed to be less than zero
		content_size = get_size(fileobj) - offset
		padding_size = -len(meta_data)
		assert padding_size < 0
		info = PaddingInfo(padding_size, content_size)
		new_padding = info._get_padding(padding_func)
		new_padding = min(0xFFFFFFFF, new_padding)

		free = Atom.render(b"free", b"\x00" * new_padding)
		meta = Atom.render(b"meta", meta_data + free)
		if path[-1].name != b"udta":
			# moov.udta not found -- create one
			data = Atom.render(b"udta", meta)
		else:
			data = meta

		insert_bytes(fileobj, len(data), offset)
		fileobj.seek(offset)
		fileobj.write(data)
		self.__update_parents(fileobj, path, len(data))
		self.__update_offsets(fileobj, atoms, len(data), offset)

	def __save_existing(self, fileobj, atoms, path, ilst_data, padding_func):
		# Replace the old ilst atom.
		ilst = path[-1]
		offset = ilst.offset
		length = ilst.length

		# Use adjacent free atom if there is one
		free = _find_padding(path)
		if free is not None:
			offset = min(offset, free.offset)
			length += free.length

		# Always add a padding atom to make things easier
		padding_overhead = len(Atom.render(b"free", b""))
		content_size = get_size(fileobj) - (offset + length)
		padding_size = length - (len(ilst_data) + padding_overhead)
		info = PaddingInfo(padding_size, content_size)
		new_padding = info._get_padding(padding_func)
		# Limit padding size so we can be sure the free atom overhead is as we
		# calculated above (see Atom.render)
		new_padding = min(0xFFFFFFFF, new_padding)

		ilst_data += Atom.render(b"free", b"\x00" * new_padding)

		resize_bytes(fileobj, length, len(ilst_data), offset)
		delta = len(ilst_data) - length

		fileobj.seek(offset)
		fileobj.write(ilst_data)
		self.__update_parents(fileobj, path[:-1], delta)
		self.__update_offsets(fileobj, atoms, delta, offset)

	def __update_parents(self, fileobj, path, delta):
		"""Update all parent atoms with the new size."""

		if delta == 0:
			return

		for atom in path:
			fileobj.seek(atom.offset)
			size = cdata.uint_be(fileobj.read(4))
			if size == 1:  # 64bit
				# skip name (4B) and read size (8B)
				size = cdata.ulonglong_be(fileobj.read(12)[4:])
				fileobj.seek(atom.offset + 8)
				fileobj.write(cdata.to_ulonglong_be(size + delta))
			else:  # 32bit
				fileobj.seek(atom.offset)
				fileobj.write(cdata.to_uint_be(size + delta))

	def __update_offset_table(self, fileobj, fmt, atom, delta, offset):
		"""Update offset table in the specified atom."""
		if atom.offset > offset:
			atom.offset += delta
		fileobj.seek(atom.offset + 12)
		data = fileobj.read(atom.length - 12)
		fmt = fmt % cdata.uint_be(data[:4])
		try:
			offsets = struct.unpack(fmt, data[4:])
			offsets = [o + (0, delta)[offset < o] for o in offsets]
			fileobj.seek(atom.offset + 16)
			fileobj.write(struct.pack(fmt, *offsets))
		except struct.error:
			raise MP4MetadataError("wrong offset inside %r" % atom.name)

	def __update_tfhd(self, fileobj, atom, delta, offset):
		if atom.offset > offset:
			atom.offset += delta
		fileobj.seek(atom.offset + 9)
		data = fileobj.read(atom.length - 9)
		flags = cdata.uint_be(b"\x00" + data[:3])
		if flags & 1:
			o = cdata.ulonglong_be(data[7:15])
			if o > offset:
				o += delta
			fileobj.seek(atom.offset + 16)
			fileobj.write(cdata.to_ulonglong_be(o))

	def __update_offsets(self, fileobj, atoms, delta, offset):
		"""Update offset tables in all 'stco' and 'co64' atoms."""
		if delta == 0:
			return
		moov = atoms[b"moov"]
		for atom in moov.findall(b"stco", True):
			self.__update_offset_table(fileobj, ">%dI", atom, delta, offset)
		for atom in moov.findall(b"co64", True):
			self.__update_offset_table(fileobj, ">%dQ", atom, delta, offset)
		try:
			for atom in atoms[b"moof"].findall(b"tfhd", True):
				self.__update_tfhd(fileobj, atom, delta, offset)
		except KeyError:
			pass

	def __parse_data(self, atom, data):
		pos = 0
		while pos < atom.length - 8:
			head = data[pos:pos + 12]
			if len(head) != 12:
				raise MP4MetadataError("truncated atom % r" % atom.name)
			length, name = struct.unpack(">I4s", head[:8])
			if length < 1:
				raise MP4MetadataError(
					"atom %r has a length of zero" % atom.name)
			version = ord(head[8:9])
			flags = struct.unpack(">I", b"\x00" + head[9:12])[0]
			if name != b"data":
				raise MP4MetadataError(
					"unexpected atom %r inside %r" % (name, atom.name))

			chunk = data[pos + 16:pos + length]
			if len(chunk) != length - 16:
				raise MP4MetadataError("truncated atom % r" % atom.name)
			yield version, flags, chunk
			pos += length

	def __add(self, key, value, single=False):
		assert isinstance(key, str)

		if single:
			self[key] = value
		else:
			self.setdefault(key, []).extend(value)

	def __render_data(self, key, version, flags, value):
		return Atom.render(_key2name(key), b"".join([
			Atom.render(
				b"data", struct.pack(">2I", version << 24 | flags, 0) + data)
			for data in value]))

	def __parse_freeform(self, atom, data):
		length = cdata.uint_be(data[:4])
		mean = data[12:length]
		pos = length
		length = cdata.uint_be(data[pos:pos + 4])
		name = data[pos + 12:pos + length]
		pos += length
		value = []
		while pos < atom.length - 8:
			length, atom_name = struct.unpack(">I4s", data[pos:pos + 8])
			if atom_name != b"data":
				raise MP4MetadataError(
					"unexpected atom %r inside %r" % (atom_name, atom.name))
			if length < 1:
				raise MP4MetadataError(
					"atom %r has a length of zero" % atom.name)
			version = ord(data[pos + 8:pos + 8 + 1])
			flags = struct.unpack(">I", b"\x00" + data[pos + 9:pos + 12])[0]
			value.append(MP4FreeForm(data[pos + 16:pos + length],
									 dataformat=flags, version=version))
			pos += length

		key = _name2key(atom.name + b":" + mean + b":" + name)
		self.__add(key, value)

	def __render_freeform(self, key, value):
		if isinstance(value, bytes):
			value = [value]

		dummy, mean, name = _key2name(key).split(b":", 2)
		mean = struct.pack(">I4sI", len(mean) + 12, b"mean", 0) + mean
		name = struct.pack(">I4sI", len(name) + 12, b"name", 0) + name

		data = b""
		for v in value:
			flags = AtomDataType.UTF8
			version = 0
			if isinstance(v, MP4FreeForm):
				flags = v.dataformat
				version = v.version

			data += struct.pack(
				">I4s2I", len(v) + 16, b"data", version << 24 | flags, 0)
			data += v

		return Atom.render(b"----", mean + name + data)

	def __parse_pair(self, atom, data):
		key = _name2key(atom.name)
		values = [struct.unpack(">2H", d[2:6]) for
				  version, flags, d in self.__parse_data(atom, data)]
		self.__add(key, values)

	def __render_pair(self, key, value):
		data = []
		for v in value:
			try:
				track, total = v
			except TypeError:
				raise ValueError
			if 0 <= track < 1 << 16 and 0 <= total < 1 << 16:
				data.append(struct.pack(">4H", 0, track, total, 0))
			else:
				raise MP4MetadataValueError(
					"invalid numeric pair %r" % ((track, total),))
		return self.__render_data(key, 0, AtomDataType.IMPLICIT, data)

	def __render_pair_no_trailing(self, key, value):
		data = []
		for (track, total) in value:
			if 0 <= track < 1 << 16 and 0 <= total < 1 << 16:
				data.append(struct.pack(">3H", 0, track, total))
			else:
				raise MP4MetadataValueError(
					"invalid numeric pair %r" % ((track, total),))
		return self.__render_data(key, 0, AtomDataType.IMPLICIT, data)

	def __parse_genre(self, atom, data):
		values = []
		for version, flags, data in self.__parse_data(atom, data):
			# version = 0, flags = 0
			if len(data) != 2:
				raise MP4MetadataValueError("invalid genre")
			genre = cdata.short_be(data)
			# Translate to a freeform genre.
			try:
				genre = GENRES[genre - 1]
			except IndexError:
				# this will make us write it back at least
				raise MP4MetadataValueError("unknown genre")
			values.append(genre)
		key = _name2key(b"\xa9gen")
		self.__add(key, values)

	def __parse_integer(self, atom, data):
		values = []
		for version, flags, data in self.__parse_data(atom, data):
			if version != 0:
				raise MP4MetadataValueError("unsupported version")
			if flags not in (AtomDataType.IMPLICIT, AtomDataType.INTEGER):
				raise MP4MetadataValueError("unsupported type")

			if len(data) == 1:
				value = cdata.int8(data)
			elif len(data) == 2:
				value = cdata.int16_be(data)
			elif len(data) == 3:
				value = cdata.int32_be(data + b"\x00") >> 8
			elif len(data) == 4:
				value = cdata.int32_be(data)
			elif len(data) == 8:
				value = cdata.int64_be(data)
			else:
				raise MP4MetadataValueError(
					"invalid value size %d" % len(data))
			values.append(value)

		key = _name2key(atom.name)
		self.__add(key, values)

	def __render_integer(self, key, value, min_bytes):
		assert min_bytes in (1, 2, 4, 8)

		data_list = []
		try:
			for v in value:
				# We default to the int size of the usual values written
				# by itunes for compatibility.
				if cdata.int8_min <= v <= cdata.int8_max and min_bytes <= 1:
					data = cdata.to_int8(v)
				elif cdata.int16_min <= v <= cdata.int16_max and \
						min_bytes <= 2:
					data = cdata.to_int16_be(v)
				elif cdata.int32_min <= v <= cdata.int32_max and \
						min_bytes <= 4:
					data = cdata.to_int32_be(v)
				elif cdata.int64_min <= v <= cdata.int64_max and \
						min_bytes <= 8:
					data = cdata.to_int64_be(v)
				else:
					raise MP4MetadataValueError(
						"value out of range: %r" % value)
				data_list.append(data)

		except (TypeError, ValueError, cdata.error) as e:
			raise MP4MetadataValueError(e)

		return self.__render_data(key, 0, AtomDataType.INTEGER, data_list)

	def __parse_bool(self, atom, data):
		for version, flags, data in self.__parse_data(atom, data):
			if len(data) != 1:
				raise MP4MetadataValueError("invalid bool")

			value = bool(ord(data))
			key = _name2key(atom.name)
			self.__add(key, value, single=True)

	def __render_bool(self, key, value):
		return self.__render_data(
			key, 0, AtomDataType.INTEGER, [bchr(bool(value))])

	def __parse_cover(self, atom, data):
		values = []
		pos = 0
		while pos < atom.length - 8:
			length, name, imageformat = struct.unpack(">I4sI",
													  data[pos:pos + 12])
			if name != b"data":
				if name == b"name":
					pos += length
					continue
				raise MP4MetadataError(
					"unexpected atom %r inside 'covr'" % name)
			if length < 1:
				raise MP4MetadataError(
					"atom %r has a length of zero" % atom.name)
			if imageformat not in (MP4Cover.FORMAT_JPEG, MP4Cover.FORMAT_PNG):
				# Sometimes AtomDataType.IMPLICIT or simply wrong.
				# In all cases it was jpeg, so default to it
				imageformat = MP4Cover.FORMAT_JPEG
			cover = MP4Cover(data[pos + 16:pos + length], imageformat)
			values.append(cover)
			pos += length

		key = _name2key(atom.name)
		self.__add(key, values)

	def __render_cover(self, key, value):
		atom_data = []
		for cover in value:
			try:
				imageformat = cover.imageformat
			except AttributeError:
				imageformat = MP4Cover.FORMAT_JPEG
			atom_data.append(Atom.render(
				b"data", struct.pack(">2I", imageformat, 0) + cover))
		return Atom.render(_key2name(key), b"".join(atom_data))

	def __parse_text(self, atom, data, implicit=True):
		# implicit = False, for parsing unknown atoms only take utf8 ones.
		# For known ones we can assume the implicit are utf8 too.
		values = []
		for version, flags, atom_data in self.__parse_data(atom, data):
			if implicit:
				if flags not in (AtomDataType.IMPLICIT, AtomDataType.UTF8):
					raise MP4MetadataError(
						"Unknown atom type %r for %r" % (flags, atom.name))
			else:
				if flags != AtomDataType.UTF8:
					raise MP4MetadataError(
						"%r is not text, ignore" % atom.name)

			try:
				text = atom_data.decode("utf-8")
			except UnicodeDecodeError as e:
				raise MP4MetadataError("%s: %s" % (_name2key(atom.name), e))

			values.append(text)

		key = _name2key(atom.name)
		self.__add(key, values)

	def __render_text(self, key, value, flags=AtomDataType.UTF8):
		if isinstance(value, str):
			value = [value]

		encoded = []
		for v in value:
			
			# if not isinstance(v, str):
			# 	raise TypeError("%r not str" % v)
			if isinstance(v, bytes):
				encoded.append(v)
			elif isinstance(v, str):
				encoded.append(v.encode("utf-8"))
			else:
				raise TypeError("%r is neither str or bytes" % v)

		return self.__render_data(key, 0, flags, encoded)

	def delete(self, filename):
		"""Remove the metadata from the given filename."""

		self._failed_atoms.clear()
		self.clear()
		self.save(filename, padding=lambda x: 0)

	__atoms = {
		b"----": (__parse_freeform, __render_freeform),
		b"trkn": (__parse_pair, __render_pair),
		b"disk": (__parse_pair, __render_pair_no_trailing),
		b"gnre": (__parse_genre, None),
		b"plID": (__parse_integer, __render_integer, 8),
		b"cnID": (__parse_integer, __render_integer, 4),
		b"geID": (__parse_integer, __render_integer, 4),
		b"atID": (__parse_integer, __render_integer, 4),
		b"sfID": (__parse_integer, __render_integer, 4),
		b"cmID": (__parse_integer, __render_integer, 4),
		b"akID": (__parse_integer, __render_integer, 1),
		b"tvsn": (__parse_integer, __render_integer, 4),
		b"tves": (__parse_integer, __render_integer, 4),
		b"tmpo": (__parse_integer, __render_integer, 2),
		b"\xa9mvi": (__parse_integer, __render_integer, 2),
		b"\xa9mvc": (__parse_integer, __render_integer, 2),
		b"cpil": (__parse_bool, __render_bool),
		b"pgap": (__parse_bool, __render_bool),
		b"pcst": (__parse_bool, __render_bool),
		b"shwm": (__parse_integer, __render_integer, 1),
		b"stik": (__parse_integer, __render_integer, 1),
		b"hdvd": (__parse_integer, __render_integer, 1),
		b"rtng": (__parse_integer, __render_integer, 1),
		b"covr": (__parse_cover, __render_cover),
		b"purl": (__parse_text, __render_text),
		b"egid": (__parse_text, __render_text),
	}

	# these allow implicit flags and parse as text
	for name in [b"\xa9nam", b"\xa9alb", b"\xa9ART", b"aART", b"\xa9wrt",
				 b"\xa9day", b"\xa9cmt", b"desc", b"purd", b"\xa9grp",
				 b"\xa9gen", b"\xa9lyr", b"catg", b"keyw", b"\xa9too",
				 b"cprt", b"soal", b"soaa", b"soar", b"sonm", b"soco",
				 b"sosn", b"tvsh"]:
		__atoms[name] = (__parse_text, __render_text)

	def pprint(self):

		def to_line(key, value):
			assert isinstance(key, str)
			if isinstance(value, str):
				return u"%s=%s" % (key, value)
			return u"%s=%r" % (key, value)

		values = []
		for key, value in sorted(self.items()):
			if not isinstance(key, str):
				key = key.decode("latin-1")
			if key == "covr":
				values.append(u"%s=%s" % (key, u", ".join(
					[u"[%d bytes of data]" % len(data) for data in value])))
			elif isinstance(value, list):
				for v in value:
					values.append(to_line(key, v))
			else:
				values.append(to_line(key, value))
		return u"\n".join(values)

class MP4(FileType):
    """MP4(filething)

    An MPEG-4 audio file, probably containing AAC.

    If more than one track is present in the file, the first is used.
    Only audio ('soun') tracks will be read.

    Arguments:
        filething (filething)

    Attributes:
        info (`MP4Info`)
        tags (`MP4Tags`)
    """

    MP4Tags = MP4Tags
    MP4Chapters = MP4Chapters

    _mimes = ["audio/mp4", "audio/x-m4a", "audio/mpeg4", "audio/aac"]

    @loadfile()
    def load(self, filething):
        fileobj = filething.fileobj

        try:
            atoms = Atoms(fileobj)
        except AtomError as err:
            reraise(error, err, sys.exc_info()[2])

        self.info = MP4Info()
        try:
            self.info.load(atoms, fileobj)
        except MP4NoTrackError:
            pass
        except error:
            raise
        except Exception as err:
            reraise(MP4StreamInfoError, err, sys.exc_info()[2])

        if not MP4Tags._can_load(atoms):
            self.tags = None
        else:
            try:
                self.tags = self.MP4Tags(atoms, fileobj)
            except error:
                raise
            except Exception as err:
                reraise(MP4MetadataError, err, sys.exc_info()[2])

        if not MP4Chapters._can_load(atoms):
            self.chapters = None
        else:
            try:
                self.chapters = self.MP4Chapters(atoms, fileobj)
            except error:
                raise
            except Exception as err:
                reraise(MP4MetadataError, err, sys.exc_info()[2])

    @property
    def _padding(self):
        if self.tags is None:
            return 0
        else:
            return self.tags._padding

    def save(self, *args, **kwargs):
        """save(filething=None, padding=None)"""

        super(MP4, self).save(*args, **kwargs)

    def pprint(self):
        """
        Returns:
            text: stream information, comment key=value pairs and chapters.
        """
        stream = "%s (%s)" % (self.info.pprint(), self.mime[0])
        try:
            tags = self.tags.pprint()
        except AttributeError:
            pass
        else:
            stream += ((tags and "\n" + tags) or "")

        try:
            chapters = self.chapters.pprint()
        except AttributeError:
            pass
        else:
            stream += "\n" + chapters

        return stream

    def add_tags(self):
        if self.tags is None:
            self.tags = self.MP4Tags()
        else:
            raise error("an MP4 tag already exists")

    @staticmethod
    def score(filename, fileobj, header_data):
        return (b"ftyp" in header_data) + (b"mp4" in header_data)
