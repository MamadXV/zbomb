# ZipBomb Lab (zbomb) - made by Xv - github.com/MamadXV
"""Read-only accessors over the method, recipe and theme registries.

The CLI and the TUI both need *metadata* about compression methods, bomb
recipes and colour themes. Routing that through one small module means the
presentation layers never reach into the engine or theme internals directly,
and a registry change has exactly one place to land.
"""

from __future__ import annotations

__all__ = [
    "method_keys",
    "method_rows",
    "default_method_key",
    "method_guide",
    "recipe_keys",
    "recipe_entries",
    "recipe_summary",
    "theme_keys",
    "theme_entries",
    "default_output_name",
]


def method_keys() -> tuple[str, ...]:
    """All writable compression methods, in registry order."""
    from ..core import METHODS

    return tuple(METHODS)


def method_rows() -> list[dict]:
    """Metadata for every method (key, label, level range, zip constant)."""
    from ..core import METHODS

    return [
        {
            "key": key,
            "label": method.label,
            "level_label": method.level_label,
            "level_range": method.level_range,
            "min_level": method.min_level,
            "max_level": method.max_level,
            "default_level": method.default_level,
            "supports_level": method.supports_level,
            "zip_constant": str(method.zip_constant),
        }
        for key, method in METHODS.items()
    ]


def default_method_key() -> str:
    """The method the lab falls back to when nothing is configured."""
    keys = method_keys()
    return "deflate" if "deflate" in keys else (keys[0] if keys else "deflate")


#: What each codec is and when to pick it. The Methods screen blends this
#: with measured output into one guide entry per method.
METHOD_GUIDE = {
    "stored": {
        "title": "stored - the uncompressed baseline",
        "what": "Bytes are written exactly as-is, with no compressor in the loop.",
        "expect": (
            "Output stays roughly the declared size; ratios sit near 1.00:1 and the "
            "lab's assumed ceiling is disk throughput (about 256 MiB/s)."
        ),
        "levels": "stored has no level. Any level is recorded as 0.",
        "use": "Use it as a control run: if anything looks bigger with stored, suspect overhead, not compression.",
    },
    "deflate": {
        "title": "deflate - the zip mainstream",
        "what": (
            "The classic LZ77 + Huffman mix that most zip tools write. zipfile "
            "honours levels 1-9 here, and the engine matches that."
        ),
        "expect": (
            "The default level is 9: good ratios for tiny archives without the "
            "wait of heavier codecs. Runtime rises faster than ratios near 8-9."
        ),
        "levels": (
            "Pick a low level (1-3) for fast probes, a mid level (5-6) for "
            "balanced runs, or 9 for the smallest artifact."
        ),
        "use": "Pick deflate when the target reader is ordinary zip tooling.",
    },
    "bzip2": {
        "title": "bzip2 - the bomb builder's workhorse",
        "what": (
            "A block-sorting (BWT) plus run-length chain that makes long repeated "
            "runs collapse dramatically."
        ),
        "expect": (
            "The lab default is 9 on our zero-fill payloads; the RLE pre-pass "
            "turns long zero runs into an extreme ratio per megabyte on disk."
        ),
        "levels": (
            "Higher levels mostly enlarge the working set (100k x level blocks) "
            "while ratios plateau past about 7 on repetitive payloads."
        ),
        "use": "Pick bzip2 when the goal is maximum declared bytes from the smallest archive.",
    },
    "lzma": {
        "title": "lzma - the slowest, most searching pass",
        "what": (
            "A dictionary coder over larger windows. The lab sets a real preset "
            "because zipfile would otherwise ignore the requested level."
        ),
        "expect": (
            "Preset 6 is the default balance; memory grows roughly with preset "
            "(about 10.5x the preset dictionary size, e.g. ~84 MiB at 6)."
        ),
        "levels": (
            "Use preset 0-2 for quick probes, 6 for a balanced run, or 9 only "
            "when a long write is acceptable."
        ),
        "use": "Pick lzma for slow, space-critical archives where decoder memory is acceptable.",
    },
}  #: method key -> plain-language guide text


def method_guide(key: str = "") -> list[dict]:
    """Method guide cards: TUI content plus the previous row metadata.

    ``key`` optionally filters to a single method; otherwise every known
    method is returned in registry order.
    """
    from ..core import METHODS

    cards: list[dict] = []
    for name, method in METHODS.items():
        if key and name != key:
            continue
        guide = METHOD_GUIDE.get(name, {})
        cards.append(
            {
                "key": name,
                "label": method.label,
                "level_label": method.level_label,
                "level_range": method.level_range,
                "min_level": method.min_level,
                "max_level": method.max_level,
                "default_level": method.default_level,
                "supports_level": method.supports_level,
                "zip_constant": str(method.zip_constant),
                "title": guide.get("title", method.label),
                "what": guide.get("what", ""),
                "expect": guide.get("expect", ""),
                "levels": guide.get("levels", ""),
                "use": guide.get("use", ""),
            }
        )
    return cards


def recipe_keys() -> tuple[str, ...]:
    """Every structural recipe key, in registry order."""
    from ..engine import RECIPES

    return tuple(RECIPES)


def recipe_entries() -> list[dict]:
    """Metadata for every recipe (key, label, summary, knobs, defaults)."""
    from ..engine import describe_recipes

    return [
        {
            "key": recipe.key,
            "label": recipe.label,
            "summary": recipe.summary,
            "knobs": tuple(recipe.knobs),
            "default_fanout": recipe.default_fanout,
            "default_entries": recipe.default_entries,
            "recursive": recipe.recursive,
        }
        for recipe in describe_recipes()
    ]


def recipe_summary(key: str) -> str:
    """One-line human summary for a recipe key (empty when unknown)."""
    for entry in recipe_entries():
        if entry["key"] == key:
            return entry["summary"]
    return ""


def theme_keys() -> tuple[str, ...]:
    """Every colour theme name, in registry order."""
    from ..ui import THEME_NAMES

    return tuple(THEME_NAMES)


def theme_entries() -> list[dict]:
    """Metadata for every theme (name, label, description, dark flag)."""
    from ..ui import THEMES

    return [
        {
            "name": name,
            "label": entry["label"],
            "description": entry["description"],
            "dark": bool(entry.get("dark", True)),
        }
        for name, entry in THEMES.items()
    ]


def default_output_name(
    size_text: str, method: str, level: int | None = None, recipe: str = "flat"
) -> str:
    """Generate an archive name that describes what is inside."""
    from ..core import METHODS, normalize_level

    safe = "".join(ch if ch.isalnum() else "-" for ch in size_text).strip("-") or "target"
    method_def = METHODS.get(method) or METHODS[default_method_key()]
    suffix = (
        f"{method_def.key}{normalize_level(method_def.key, level)}"
        if method_def.supports_level
        else method_def.key
    )
    tag = f"_{recipe}" if recipe and recipe != "flat" else ""
    return f"zeros_{safe}_{suffix}{tag}.zip"


__credit__ = "ZipBomb Lab - zipbomb_lab.domain.data - made by Xv @XvRendering https://github.com/MamadXV"
