# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Core foundations: sizes, methods, policy, config.

"""

from __future__ import annotations


# -- sizes --
"""Human friendly byte-size parsing and formatting.

Accepts IEC units (KiB, MiB, GiB, TiB, PiB = powers of 1024) and SI units
(KB, MB, GB, TB, PB = powers of 1000), case-insensitively, with or without
a space between the number and the unit. A bare number means bytes.

This module is deliberately dependency free so the toolkit keeps running on
mobile Python builds (Termux, Pydroid3, a-Shell) where ``pip`` may be absent.
"""


import re

__all__ = [
    "SizeError",
    "KIB",
    "MIB",
    "GIB",
    "GIB",
    "TIB",
    "PIB",
    "parse_size",
    "format_size",
    "format_size_exact",
    "format_speed",
    "format_duration",
]

KIB = 1024
MIB = KIB**2
GIB = KIB**3
TIB = KIB**4
PIB = KIB**5

SI = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1000,
    "m": 1000**2,
    "mb": 1000**2,
    "g": 1000**3,
    "gb": 1000**3,
    "t": 1000**4,
    "tb": 1000**4,
    "p": 1000**5,
    "pb": 1000**5,
}

IEC = {
    "kib": KIB,
    "mib": MIB,
    "gib": GIB,
    "tib": TIB,
    "pib": PIB,
    "eib": PIB * 1024,
}

UNITS = {**SI, **IEC}

_SIZE_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)\s*$")


class SizeError(ValueError):
    """Raised when a size string cannot be understood."""


def parse_size(text: str | int) -> int:
    """Parse ``"100MB"``, ``"1.5GiB"``, ``"2 TiB"`` or ``1234`` into bytes.

    Raises ``SizeError`` for anything that is not a non-negative size.
    """
    if isinstance(text, bool):
        raise SizeError("a boolean is not a size")
    if isinstance(text, int):
        if text < 0:
            raise SizeError("size must not be negative")
        return text
    if not isinstance(text, str):
        raise SizeError("size must be a string or an integer")

    match = _SIZE_RE.match(text)
    if match is None:
        raise SizeError(
            "cannot parse size %r - use forms like 512MiB, 100GB, 1.5TiB" % (text,)
        )

    number, unit = match.group(1).replace(",", "."), match.group(2).lower()
    if unit == "bit" or unit == "bits":
        raise SizeError("bits are ambiguous here - use bytes (e.g. 100MB)")
    if not unit and "." in match.group(1):
        raise SizeError(
            "a decimal number without a unit is ambiguous - use forms like 1.5MiB, 100MB"
        )
    if unit not in UNITS:
        known = ", ".join(sorted(u for u in UNITS if u))
        raise SizeError("unknown unit %r - known units: %s" % (unit, known))

    value = float(number) * UNITS[unit]
    if value < 0:
        raise SizeError("size must not be negative")
    return int(round(value))


def format_size(num_bytes: int, binary: bool = True) -> str:
    """Format bytes using the largest unit that keeps the number >= 1."""
    negative = num_bytes < 0
    value = float(abs(num_bytes))
    if binary:
        steps = [
            ("B", 1),
            ("KiB", KIB),
            ("MiB", MIB),
            ("GiB", GIB),
            ("TiB", TIB),
            ("PiB", PIB),
        ]
        threshold = 1024
    else:
        steps = [
            ("B", 1),
            ("KB", 1000),
            ("MB", 1000**2),
            ("GB", 1000**3),
            ("TB", 1000**4),
            ("PB", 1000**5),
        ]
        threshold = 1000
    label, factor = steps[0]
    for label, factor in steps:
        if value < factor * threshold or factor == steps[-1][1]:
            break
    scaled = value / factor
    if scaled >= 100 or factor == 1:
        text = f"{scaled:,.0f} {label}"
    else:
        text = f"{scaled:,.1f} {label}"
    return ("-" + text) if negative else text


def format_size_exact(num_bytes: int) -> str:
    """Format bytes as an exact count plus a human readable approximation."""
    return f"{num_bytes:,} bytes ({format_size(num_bytes)})"


def format_speed(bytes_per_second: float) -> str:
    """Format a throughput value for progress and estimate output."""
    return f"{format_size(int(bytes_per_second))}/s"


def format_duration(seconds: float) -> str:
    """Format a duration (runtime or ETA) in a compact human form."""
    seconds = max(int(seconds), 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h{minutes:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d{hours:02d}h"


# -- methods --
"""Compression methods, calibration and the cost model.

Python's ``zipfile`` exposes four writable methods - ``ZIP_STORED``,
``ZIP_DEFLATED``, ``ZIP_BZIP2`` and ``ZIP_LZMA`` - but it *ignores*
``compresslevel`` for LZMA (see ``zipfile._get_compressor``). This module
supplies a small LZMA1 compressor that honours a level preset, and it can be
installed temporarily by ``lzma_preset()`` for the duration of a write.

The ZIP LZMA property block is built with the public LZMA property layout
(``lc/lp/pb`` byte followed by a little-endian dictionary size), so no
private ``lzma`` helper is required from this code. ``zipfile`` itself
decodes those properties, and the round trip is covered by the test suite.

Every ratio and speed number in this module is *measured* in memory at
runtime rather than hard coded, because the real values depend on the
algorithm build shipped with the running interpreter.
"""


import bz2
import contextlib
import lzma
import math
import struct
import time
import zlib
import zipfile
from dataclasses import dataclass, field

# same-file (sizes): KIB, MIB, format_duration, format_size

__all__ = [
    "ZIP64_LIMIT",
    "LZMA_PRESET_DICT_SIZES",
    "Method",
    "METHODS",
    "get_method",
    "normalize_level",
    "compress_payload",
    "Calibration",
    "calibrate",
    "Estimate",
    "estimate",
    "lzma_preset",
    "approx_encoder_memory",
]

#: Largest value a classic (non ZIP64) 32 bit size field can hold.
ZIP64_LIMIT = 0xFFFFFFFE

#: liblzma dictionary sizes used by presets 0-9.
LZMA_PRESET_DICT_SIZES = {
    0: 256 * KIB,
    1: 1 * MIB,
    2: 2 * MIB,
    3: 4 * MIB,
    4: 4 * MIB,
    5: 8 * MIB,
    6: 8 * MIB,
    7: 16 * MIB,
    8: 32 * MIB,
    9: 64 * MIB,
}

#: LZMA1 filter id as used in the ZIP LZMA header.
_FILTER_LZMA1_ID = 9


def lzma1_properties(dict_size: int, lc: int = 3, lp: int = 0, pb: int = 2) -> bytes:
    """Build the ZIP LZMA property block for an LZMA1 filter."""
    return bytes([(pb * 5 + lp) * 9 + lc]) + dict_size.to_bytes(4, "little")


class LZMA1Compressor:
    """Streaming LZMA1 compressor with zipfile's ``compress``/``flush`` API."""

    def __init__(self, dict_size: int) -> None:
        self.dict_size = int(dict_size)
        self._comp = None
        self._filters = [
            {
                "id": lzma.FILTER_LZMA1,
                "dict_size": self.dict_size,
                "lc": 3,
                "lp": 0,
                "pb": 2,
            }
        ]

    def _init(self) -> bytes:
        self._comp = lzma.LZMACompressor(lzma.FORMAT_RAW, filters=self._filters)
        properties = lzma1_properties(self.dict_size)
        return struct.pack("<BBH", _FILTER_LZMA1_ID, 4, len(properties)) + properties

    def compress(self, data: bytes) -> bytes:
        if self._comp is None:
            return self._init() + self._comp.compress(data)
        return self._comp.compress(data)

    def flush(self) -> bytes:
        if self._comp is None:
            return self._init() + self._comp.flush()
        return self._comp.flush()


@contextlib.contextmanager
def lzma_preset(preset: int):
    """Make ``zipfile`` honour an LZMA preset for the duration of the block.

    ``zipfile`` resolves its compressor lazily through the module level
    ``_get_compressor`` helper, so replacing that helper while writing is
    enough. The original helper is always restored, even on error, and older
    or newer interpreters that no longer expose the helper fall back to the
    unmodified ``zipfile`` behaviour.
    """
    original = getattr(zipfile, "_get_compressor", None)
    if original is None or not hasattr(zipfile, "ZIP_LZMA"):
        yield False
        return
    dict_size = LZMA_PRESET_DICT_SIZES.get(int(preset), LZMA_PRESET_DICT_SIZES[6])

    def patched(compress_type, compresslevel=None):
        if compress_type == zipfile.ZIP_LZMA:
            return LZMA1Compressor(dict_size)
        return original(compress_type, compresslevel)

    zipfile._get_compressor = patched
    try:
        yield True
    finally:
        zipfile._get_compressor = original


@dataclass(frozen=True)
class Method:
    """A writable ZIP compression method."""

    key: str
    zip_constant: int
    label: str
    supports_level: bool
    level_label: str
    min_level: int
    max_level: int
    default_level: int | None

    @property
    def level_range(self) -> str:
        if not self.supports_level:
            return "-"
        return f"{self.min_level}-{self.max_level}"


METHODS: dict[str, Method] = {
    m.key: m
    for m in (
        Method("stored", zipfile.ZIP_STORED, "stored (no compression)", False, "-", 0, 0, None),
        Method("deflate", zipfile.ZIP_DEFLATED, "deflate (zlib)", True, "level", 1, 9, 9),
        Method("bzip2", zipfile.ZIP_BZIP2, "bzip2 (BWT + RLE)", True, "level", 1, 9, 9),
        Method("lzma", zipfile.ZIP_LZMA, "lzma (LZMA1)", True, "preset", 0, 9, 6),
    )
}

#: Sample sizes used for calibration, chosen to cover whole bzip2 blocks.
DEFAULT_SAMPLE_BYTES = {"stored": 0, "deflate": 8 * MIB, "bzip2": 16 * MIB, "lzma": 8 * MIB}

#: Stored entries are limited by disk throughput, which cannot be measured
#: meaningfully from an in-memory payload, so a documented assumption is used.
STORED_ASSUMED_SPEED = 256 * MIB

_CALIBRATION_CACHE: dict[tuple[str, int, int], "Calibration"] = {}


def get_method(key: str) -> Method:
    """Look a method up by name, raising a friendly error when unknown."""
    try:
        return METHODS[key.lower()]
    except (KeyError, AttributeError):
        known = ", ".join(sorted(METHODS))
        raise ValueError(f"unknown method {key!r} - choose one of: {known}") from None


def normalize_level(key: str, level: int | None) -> int:
    """Validate a level for a method, filling in the method default."""
    method = get_method(key)
    if not method.supports_level:
        return 0
    level = method.default_level if level is None else int(level)
    if not method.min_level <= level <= method.max_level:
        raise ValueError(
            f"{method.key} {method.level_label} must be between "
            f"{method.min_level} and {method.max_level}, got {level}"
        )
    return level


def approx_encoder_memory(key: str, level: int | None = None) -> int:
    """Rough working-set size of the encoder for a method, in bytes."""
    method = get_method(key)
    level = normalize_level(key, level)
    if method.key == "stored":
        return 1 * MIB
    if method.key == "deflate":
        return 4 * MIB
    if method.key == "bzip2":
        # bzip2 keeps one block (100k x level) plus the sort buffers.
        return int(100_000 * max(level, 1) * 10)
    return int(LZMA_PRESET_DICT_SIZES.get(level, MIB * 8) * 10.5)


def compress_payload(data: bytes, key: str, level: int | None = None) -> bytes:
    """Compress *data* the same way the archive writer would."""
    method = get_method(key)
    level = normalize_level(key, level)
    if method.key == "stored":
        return data
    if method.key == "deflate":
        return zlib.compress(data, level)
    if method.key == "bzip2":
        return bz2.compress(data, level)
    compressor = LZMA1Compressor(LZMA_PRESET_DICT_SIZES.get(level, 8 * MIB))
    return compressor.compress(data) + compressor.flush()


@dataclass(frozen=True)
class Calibration:
    """Measured behaviour of one method/level pair on repetitive data."""

    method: str
    level: int
    sample_bytes: int
    output_bytes: int
    seconds: float

    @property
    def ratio(self) -> float:
        if self.output_bytes <= 0:
            return 1.0
        return self.sample_bytes / self.output_bytes

    @property
    def bytes_per_second(self) -> float:
        return self.sample_bytes / max(self.seconds, 1e-9)

    @property
    def mib_per_second(self) -> float:
        return self.bytes_per_second / MIB


def calibrate(
    key: str,
    level: int | None = None,
    sample_bytes: int | None = None,
    use_cache: bool = True,
) -> Calibration:
    """Measure ratio and throughput for ``key`` by compressing zeros in RAM."""
    method = get_method(key)
    level = normalize_level(key, level)
    if sample_bytes is None:
        sample_bytes = DEFAULT_SAMPLE_BYTES.get(method.key, 8 * MIB)

    if method.key == "stored" or sample_bytes <= 0:
        return Calibration(method.key, level, 0, 0, 0.0)

    cache_key = (method.key, level, int(sample_bytes))
    if use_cache and cache_key in _CALIBRATION_CACHE:
        return _CALIBRATION_CACHE[cache_key]

    payload = b"\0" * int(sample_bytes)
    started = time.perf_counter()
    compressed = compress_payload(payload, method.key, level)
    elapsed = max(time.perf_counter() - started, 1e-9)
    result = Calibration(method.key, level, len(payload), len(compressed), elapsed)
    _CALIBRATION_CACHE[cache_key] = result
    return result


#: Rough per-entry bookkeeping overhead in the archive (headers + descriptor).
ENTRY_OVERHEAD = 128


def format_ratio(ratio: float) -> str:
    """Format an expansion ratio like ``1,028:1``."""
    if ratio <= 0:
        return "n/a"
    if ratio < 10:
        return f"{ratio:.2f}:1"
    return f"{ratio:,.0f}:1"


def describe_method(key: str, level: int | None = None) -> str:
    """Human readable method description, e.g. ``deflate level 9``."""
    method = get_method(key)
    if not method.supports_level:
        return method.key
    return f"{method.key} {method.level_label} {normalize_level(key, level)}"


@dataclass(frozen=True)
class Estimate:
    """Predicted cost of building one archive."""

    target_bytes: int
    method: str
    level: int
    ratio: float
    output_bytes: int
    seconds: float
    entries: int
    split_bytes: int | None
    zip64_required: bool
    encoder_memory: int
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def megabytes_per_second(self) -> float:
        if self.seconds <= 0:
            return float("inf")
        return (self.target_bytes / MIB) / self.seconds

    def as_dict(self) -> dict:
        return {
            "target_bytes": self.target_bytes,
            "target_human": format_size(self.target_bytes),
            "method": self.method,
            "level": self.level,
            "ratio": round(self.ratio, 3),
            "ratio_human": format_ratio(self.ratio),
            "output_bytes": self.output_bytes,
            "output_human": format_size(self.output_bytes),
            "seconds": round(self.seconds, 2),
            "duration_human": format_duration(self.seconds),
            "entries": self.entries,
            "split_bytes": self.split_bytes,
            "zip64_required": self.zip64_required,
            "encoder_memory_bytes": self.encoder_memory,
            "warnings": list(self.warnings),
        }


def estimate(
    target_bytes: int,
    key: str,
    level: int | None = None,
    split: int | None = None,
    calibration: Calibration | None = None,
) -> Estimate:
    """Predict output size, runtime, ZIP64 need and resource warnings."""
    target_bytes = int(target_bytes)
    if target_bytes <= 0:
        raise ValueError("target size must be greater than zero")

    method = get_method(key)
    level = normalize_level(key, level)
    cal = calibration if calibration is not None else calibrate(method.key, level)

    if method.key == "stored":
        ratio = 1.0
        output = target_bytes
        seconds = target_bytes / STORED_ASSUMED_SPEED
    else:
        ratio = cal.ratio
        output = max(1, int(target_bytes / max(ratio, 1e-12)))
        seconds = target_bytes / max(cal.bytes_per_second, 1.0)

    entries = 1
    if split:
        split = max(int(split), 1)
        entries = max(1, math.ceil(target_bytes / split))
    output += ENTRY_OVERHEAD * entries

    zip64_required = (
        target_bytes > ZIP64_LIMIT or output > ZIP64_LIMIT or entries > 65534
    )

    memory = approx_encoder_memory(method.key, level)
    warnings: list[str] = []
    if seconds > 1800:
        warnings.append(
            f"expected runtime {format_duration(seconds)} at "
            f"{cal.mib_per_second:,.0f} MiB/s - a multi-hour run needs a "
            f"stable machine, or use --split/--resume"
        )
    if output > ZIP64_LIMIT:
        warnings.append(
            "the output file itself exceeds 4 GiB, so ZIP64 is required"
        )
    if entries > 65534:
        warnings.append(
            f"{entries:,} entries exceed the classic limit of 65,534, so ZIP64 is required"
        )
    if memory > 256 * MIB:
        warnings.append(
            f"{describe_method(method.key, level)} needs roughly "
            f"{format_size(memory)} of RAM while encoding"
        )
    if method.key == "lzma" and level > 6:
        warnings.append(
            "higher LZMA presets on repetitive data cost memory and time but "
            "do not improve the ratio (the dictionary size is not the limit)"
        )

    return Estimate(
        target_bytes=target_bytes,
        method=method.key,
        level=level,
        ratio=ratio,
        output_bytes=output,
        seconds=seconds,
        entries=entries,
        split_bytes=(int(split) if split else None),
        zip64_required=zip64_required,
        encoder_memory=memory,
        warnings=tuple(warnings),
    )


def compare_methods(target_bytes: int, level: int | None = None) -> list[Estimate]:
    """Estimate the same target with every writable method, for the tables."""
    results = []
    for method_key in METHODS:
        results.append(estimate(target_bytes, method_key, level=level_matches(method_key, level)))
    return results


def level_matches(key: str, level: int | None) -> int | None:
    """Pass an explicit level only to methods that accept one."""
    if level is None:
        return None
    method = get_method(key)
    return level if method.supports_level else None


# -- policy --
"""Safety gates for archive creation: caps, confirmations, pre-flight checks.

The lab keeps two different limits on purpose:

* creating real bytes is capped (``MAX_CREATE_BYTES``), because writing is the
  only operation that consumes disk and hours of CPU;
* the estimator is effectively uncapped (``MAX_ESTIMATE_BYTES``), because
  predicting a 100 TB archive costs nothing and is the honest way to study the
  growth curve without building the artifact.

Even with ``force=True`` the absolute output ceiling and the disk-space checks
still apply - those protect your machine, they do not gate curiosity.
"""


import shutil
import sys
from pathlib import Path

# same-file (methods): ZIP64_LIMIT, Estimate
# same-file (sizes): GIB, MIB, PIB, TIB, format_size

__all__ = [
    "PolicyError",
    "ACK_PHRASE",
    "MAX_CREATE_BYTES",
    "MAX_OUTPUT_BYTES",
    "MAX_ESTIMATE_BYTES",
    "MAX_DECLARED_EXPANSION",
    "MAX_SPLITS",
    "DISK_MARGIN",
    "Policy",
    "check_create",
    "check_recipe",
    "disk_free",
    "is_32bit",
    "describe_limits",
]

#: Largest payload ``create`` will build. Raise it knowingly in this file only.
MAX_CREATE_BYTES = 1 * TIB

#: Absolute ceiling for the written archive, whatever the flags say.
MAX_OUTPUT_BYTES = 8 * GIB

#: Highest target the estimator answers for.
MAX_ESTIMATE_BYTES = 16 * PIB

#: Absolute ceiling on the recursively expanded size of a structural recipe.
#: A nested bomb can declare petabytes from a small file, so this is a hard
#: stop that no flag lifts - routine work never needs a PB-class artifact.
MAX_DECLARED_EXPANSION = 8 * PIB

#: Largest number of entries a single archive may be split into.
MAX_SPLITS = 4096

#: Phrase required when a request goes past the create cap.
ACK_PHRASE = "I understand this writes real data"

#: Free space kept in reserve on the target volume.
DISK_MARGIN = 64 * MIB
DISK_MARGIN_FRACTION = 0.05
MIN_FREE_AFTER = 256 * MIB


class PolicyError(Exception):
    """Raised when a request is refused by the safety policy."""

    def __init__(self, message: str, kind: str = "policy") -> None:
        super().__init__(message)
        self.kind = kind


def is_32bit() -> bool:
    """True on 32 bit interpreters, which cannot write large ZIP64 outputs."""
    return sys.maxsize <= 2**32


def disk_free(path: Path) -> int | None:
    """Free bytes on the volume holding *path*.

    Returns ``None`` when the platform or sandbox refuses to answer, which
    happens on some Android storage paths.
    """
    candidate = Path(path)
    for _ in range(64):
        try:
            if candidate.exists():
                return shutil.disk_usage(str(candidate)).free
        except OSError:
            return None
        if candidate.parent == candidate:
            return None
        candidate = candidate.parent
    return None


class Policy:
    """Resolved limits for one command invocation."""

    def __init__(
        self,
        max_create: int = MAX_CREATE_BYTES,
        max_output: int = MAX_OUTPUT_BYTES,
        max_splits: int = MAX_SPLITS,
        max_estimate: int = MAX_ESTIMATE_BYTES,
    ) -> None:
        self.max_create = int(max_create)
        self.max_output = int(max_output)
        self.max_splits = int(max_splits)
        self.max_estimate = int(max_estimate)

    def check_estimate_target(self, target_bytes: int) -> None:
        if target_bytes > self.max_estimate:
            raise PolicyError(
                f"target {format_size(target_bytes)} is beyond the estimator "
                f"ceiling of {format_size(self.max_estimate)}",
                kind="estimate-cap",
            )

    def required_disk(self, output_bytes: int) -> int:
        margin = max(DISK_MARGIN, int(output_bytes * DISK_MARGIN_FRACTION))
        return int(output_bytes) + margin

    def check_create(
        self,
        path: Path,
        est: Estimate,
        force: bool = False,
        ack: str | None = None,
        overwrite: bool = True,
    ) -> list[str]:
        """Validate a create request; return advisory warnings."""
        warnings: list[str] = []
        path = Path(path)

        if path.exists() and path.is_dir():
            raise PolicyError(f"{path} is a directory, not an archive path", kind="path")

        if path.exists() and not overwrite:
            raise PolicyError(
                f"{path} already exists - choose another name or allow overwrite",
                kind="path",
            )

        if est.entries > self.max_splits:
            raise PolicyError(
                f"--split would create {est.entries:,} entries, above the limit "
                f"of {self.max_splits:,}",
                kind="split-cap",
            )

        if est.output_bytes > self.max_output:
            raise PolicyError(
                f"projected output {format_size(est.output_bytes)} is above the "
                f"absolute output ceiling of {format_size(self.max_output)}; pick "
                f"a lighter method - bzip2 and lzma produce far smaller archives "
                f"for the same payload",
                kind="output-cap",
            )

        if is_32bit() and est.output_bytes > ZIP64_LIMIT:
            raise PolicyError(
                "this is a 32 bit Python build, which cannot address the "
                f"{format_size(est.output_bytes)} output; use a 64 bit "
                "interpreter or lower the target",
                kind="platform",
            )

        if est.target_bytes > self.max_create:
            if not force:
                raise PolicyError(
                    f"target {format_size(est.target_bytes)} exceeds the create cap "
                    f"of {format_size(self.max_create)}. Re-run with --force --ack "
                    f'"{ACK_PHRASE}", or use "estimate" to model this size without '
                    f"writing anything.",
                    kind="cap",
                )
            if (ack or "").strip() != ACK_PHRASE:
                raise PolicyError(
                    f'--force requires --ack "{ACK_PHRASE}" exactly', kind="ack"
                )
            warnings.append(
                f"cap override active for {format_size(est.target_bytes)} "
                f"(default cap {format_size(self.max_create)})"
            )

        free = disk_free(path.parent)
        if free is None:
            warnings.append(
                "free disk space could not be determined on this platform - check "
                "the volume yourself before a long run"
            )
        else:
            needed = self.required_disk(est.output_bytes)
            if free < needed:
                raise PolicyError(
                    f"need about {format_size(needed)} free "
                    f"({format_size(est.output_bytes)} output plus margin) but "
                    f"{path.parent} has {format_size(free)}",
                    kind="disk",
                )
            if free < needed + MIN_FREE_AFTER:
                warnings.append(
                    f"only {format_size(free - needed)} would remain free after "
                    f"this run"
                )

        warnings.extend(est.warnings)
        return warnings


def check_create(
    path: Path,
    est: Estimate,
    force: bool = False,
    ack: str | None = None,
    overwrite: bool = True,
    policy: Policy | None = None,
) -> list[str]:
    """Module level convenience wrapper around ``Policy.check_create``."""
    return (policy or Policy()).check_create(
        path, est, force=force, ack=ack, overwrite=overwrite
    )


def check_recipe(
    path: Path,
    plan,
    force: bool = False,
    ack: str | None = None,
    overwrite: bool = True,
    policy: Policy | None = None,
) -> list[str]:
    """Validate a structural recipe write and return advisory warnings.

    The expanded size is checked against :data:`MAX_DECLARED_EXPANSION` first,
    then the usual create gates run against the plan (whose ``target_bytes`` is
    the recursively expanded total). Import of the recipes section is
    avoided here so ``policy`` stays dependency free.
    """
    pol = policy or Policy()
    if plan.recipe == "overlap" and not force:
        raise PolicyError(
            "the overlap recipe writes a deliberately malformed archive (the "
            "central directory disagrees with the local headers); re-run with "
            f'--force --ack "{ACK_PHRASE}" to build it for detector testing',
            kind="malformed",
        )
    est = plan.as_estimate()
    if est.target_bytes > MAX_DECLARED_EXPANSION:
        raise PolicyError(
            f"this {plan.recipe} bomb would expand to "
            f"{format_size(est.target_bytes)}, above the absolute expansion "
            f"ceiling of {format_size(MAX_DECLARED_EXPANSION)}",
            kind="expansion-cap",
        )
    warnings = pol.check_create(path, est, force=force, ack=ack, overwrite=overwrite)
    if plan.recipe == "traversal":
        warnings.append(
            "this tree contains symlink loops and special files; extracting it "
            "with a tool that honours Unix modes can hang the machine"
        )
    if plan.preamble != "none":
        warnings.append(
            f"a {plan.preamble} preamble is prepended so the file also reads as "
            f"that type; keep it off shared systems"
        )
    if plan.recipe != "flat":
        warnings.append(
            f"{plan.recipe} bomb: the {format_size(est.output_bytes)} file on disk "
            f"expands to about {format_size(plan.expanded_bytes)} when extracted"
        )
    return warnings


def describe_limits(policy: Policy | None = None) -> list[str]:
    """Human readable policy summary, used by the panel and the CLI."""
    policy = policy or Policy()
    return [
        f"create cap            {format_size(policy.max_create)} uncompressed",
        f"absolute output cap   {format_size(policy.max_output)} on disk",
        f"estimator ceiling     {format_size(policy.max_estimate)} uncompressed",
        f"expansion ceiling     {format_size(MAX_DECLARED_EXPANSION)} (recipes only)",
        f"entries per archive   {policy.max_splits:,}",
        f"cap override phrase   {ACK_PHRASE!r} (with --force)",
        f"reserve kept free     {format_size(DISK_MARGIN)} or 5% of the output",
        "caps live in zipbomb_lab/core.py and no flag disables them",
    ]


# -- config --
"""Persistent settings and the artifact audit log.

Two small files live next to each other in the user's home directory (or
wherever ``ZIPBOMB_LAB_CONFIG`` points, which is handy in containers and on
mobile shells where ``$HOME`` may be read-only):

``zipbomb_lab.json``  remembered defaults for the control panel and the CLI
``zipbomb_lab.log``   append-only record of every archive that was created

Both files are optional. Missing or damaged configuration never stops the
tool: it falls back to defaults and reports a warning.
"""


import json
import os
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

__all__ = [
    "Config",
    "config_path",
    "log_path",
    "load",
    "save",
    "append_audit",
    "read_audit",
]

CONFIG_ENV = "ZIPBOMB_LAB_CONFIG"
LOG_ENV = "ZIPBOMB_LAB_LOG"
DEFAULT_CONFIG_NAME = "zipbomb_lab.json"
DEFAULT_LOG_NAME = "zipbomb_lab.log"


@dataclass
class Config:
    """Remembered defaults. Sizes are stored as strings for readability."""

    output_dir: str = "."
    method: str = "deflate"
    level: int = 9
    size: str = "100MB"
    chunk: str = "4MiB"
    split: str = ""
    progress: str = "auto"
    verify: str = "sample"
    confirm_before_write: bool = True
    theme: str = "ember"
    compact: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        return cls(**clean)


def _home() -> Path:
    try:
        return Path.home()
    except RuntimeError:  # pragma: no cover - no resolvable home directory
        return Path.cwd()


def config_path() -> Path:
    """Location of the JSON settings file."""
    override = os.environ.get(CONFIG_ENV)
    return Path(override) if override else _home() / DEFAULT_CONFIG_NAME


def log_path() -> Path:
    """Location of the audit log."""
    override = os.environ.get(LOG_ENV)
    return Path(override) if override else _home() / DEFAULT_LOG_NAME


def load(path: Path | None = None) -> tuple[Config, list[str]]:
    """Load settings, returning defaults plus warnings when unusable."""
    target = Path(path) if path else config_path()
    warnings: list[str] = []
    if not target.exists():
        return Config(), warnings
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warnings.append(f"could not read {target} ({exc}); using defaults")
        return Config(), warnings
    if not isinstance(data, dict):
        warnings.append(f"{target} does not contain a JSON object; using defaults")
        return Config(), warnings
    try:
        return Config.from_dict(data), warnings
    except (TypeError, ValueError) as exc:
        warnings.append(f"{target} has invalid values ({exc}); using defaults")
        return Config(), warnings


def save(config: Config, path: Path | None = None) -> Path:
    """Write settings, creating the parent directory when needed."""
    target = Path(path) if path else config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(config), indent=2, sort_keys=True)
    target.write_text(payload + "\n", encoding="utf-8")
    return target


def append_audit(record: dict, path: Path | None = None) -> None:
    """Append one JSON line describing a created (or refused) artifact."""
    target = Path(path) if path else log_path()
    entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        # The audit log is a convenience, never a reason to fail a run.
        pass


def read_audit(limit: int = 20, path: Path | None = None) -> list[str]:
    """Return the newest audit lines, oldest first."""
    target = Path(path) if path else log_path()
    if not target.exists():
        return []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line for line in lines[-max(int(limit), 0) :] if line.strip()]

__all__ = ['ACK_PHRASE', 'Calibration', 'Config', 'DISK_MARGIN', 'Estimate', 'GIB', 'KIB', 'LZMA_PRESET_DICT_SIZES', 'MAX_CREATE_BYTES', 'MAX_DECLARED_EXPANSION', 'MAX_ESTIMATE_BYTES', 'MAX_OUTPUT_BYTES', 'MAX_SPLITS', 'METHODS', 'MIB', 'Method', 'PIB', 'Policy', 'PolicyError', 'SizeError', 'TIB', 'ZIP64_LIMIT', 'append_audit', 'approx_encoder_memory', 'calibrate', 'check_create', 'check_recipe', 'compress_payload', 'config_path', 'describe_limits', 'disk_free', 'estimate', 'format_duration', 'format_size', 'format_size_exact', 'format_speed', 'get_method', 'is_32bit', 'load', 'log_path', 'lzma_preset', 'normalize_level', 'parse_size', 'read_audit', 'save']

# --- backward-compat: old module paths share this module object ---
import sys as _sys_compat
for _alias in ("sizes", "methods", "policy", "config"):
    _sys_compat.modules.setdefault(f"{__name__.rsplit('.', 1)[0]}.{_alias}", _sys_compat.modules[__name__])
del _sys_compat


__credit__ = "ZipBomb Lab - zipbomb_lab.core - made by Xv @XvRendering https://github.com/MamadXV"
