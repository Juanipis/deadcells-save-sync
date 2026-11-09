"""Reinterpret one Dead Cells save as another platform's container.

Strategy: rebuild the container with the destination platform's header (magic,
version, githash, builddate) and transplant only the ``S_User`` chunk, which
holds the persistent meta-progression. The ``S_Game`` chunk (in-progress run) is
NOT carried across: its entity classes are build-specific and a half-finished run
does not translate between platforms. The result is equivalent to "no run in
progress, full progression".

This works cleanly when both saves are the same game version (identical hxbit
schema CRCs). Different game versions may still load thanks to hxbit's embedded
schema migration, but are not guaranteed.
"""
import struct
import time

from .container import DCSave
from .hxbit import compare_classes, parse_classes


def schema_report(src, dst, label_src="source", label_dst="dest"):
    """Return report lines comparing the S_User schemas of two saves."""
    _, _, sc, _ = parse_classes(src.chunks["S_User"])
    _, _, dc, _ = parse_classes(dst.chunks["S_User"])
    same, diff, lines = compare_classes(sc, dc, label_src, label_dst)
    return same, diff, lines


def convert(src, dst, keep_run=False):
    """Build a new DCSave: src's S_User inside dst's container.

    Keeps the destination's game version and DLC mask so the game sees a native
    save. Feature flags (experimental/mods/lore) are inherited from the source.
    """
    chunks = {"S_User": src.chunks["S_User"]}
    for k in ("S_VersionNumber", "S_DLCMask"):
        if k in dst.chunks:
            chunks[k] = dst.chunks[k]
    chunks["S_Date"] = struct.pack("<d", time.time())
    if keep_run:
        for k in ("S_Game", "S_UserAndGameData"):
            if k in src.chunks:
                chunks[k] = src.chunks[k]

    return DCSave(
        magic=dst.magic,
        version=dst.version,
        sha1=b"\x00" * 20,
        githash=dst.githash,
        builddate=dst.builddate,
        flags=src.flags,  # build() masks this down to real feature flags + present chunks
        chunks=chunks,
    )
