"""Round-trip and integrity tests for the save container.

These use synthetic chunk bytes (the container layer does not care about hxbit
internals), so they need no real save file and can run anywhere.
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from deadcells_save.container import DCSave, DCSaveError, MAGIC_PC, MAGIC_MOBILE  # noqa: E402


def make_save(magic=MAGIC_PC, version=1):
    return DCSave(
        magic=magic,
        version=version,
        sha1=b"\x00" * 20,
        githash=b"\xab" * 20,
        builddate="2026-06-16",
        flags=0x040,  # S_HaveLore feature flag
        chunks={
            "S_User": b"HXS-user-payload-bytes",
            "S_Date": struct.pack("<d", 1788120000.0),
            "S_VersionNumber": struct.pack("<f", 35.0),
            "S_DLCMask": struct.pack("<I", 1),
        },
    )


def test_roundtrip_pc():
    s = make_save()
    blob = s.build()
    back = DCSave.parse(blob)
    assert back.magic == MAGIC_PC
    assert back.platform == "PC"
    assert back.builddate == "2026-06-16"
    assert back.chunks["S_User"] == b"HXS-user-payload-bytes"
    assert abs(back.game_version() - 35.0) < 1e-6
    assert back.dlc_mask() == 1


def test_roundtrip_mobile():
    s = make_save(magic=MAGIC_MOBILE, version=2)
    back = DCSave.parse(s.build())
    assert back.platform == "mobile"
    assert back.version == 2


def test_sha1_is_recomputed():
    s = make_save()
    blob = bytearray(s.build())
    # zeroed sha region + rest must hash to the stored digest
    import hashlib
    stored = bytes(blob[5:25])
    z = bytearray(blob)
    z[5:25] = b"\x00" * 20
    assert hashlib.sha1(bytes(z)).digest() == stored


def test_tamper_detected():
    blob = bytearray(make_save().build())
    blob[-1] ^= 0xFF  # corrupt a payload byte
    with pytest.raises(DCSaveError):
        DCSave.parse(bytes(blob))


def test_flags_rebuilt_from_chunks():
    s = make_save()
    del s.chunks["S_DLCMask"]
    back = DCSave.parse(s.build())
    assert "S_DLCMask" not in back.chunks
    assert "S_User" in back.chunks
    # feature flag preserved
    assert "S_HaveLore" in back.flag_names()


def test_unknown_magic_rejected():
    blob = bytearray(make_save().build())
    blob[0:4] = b"\x00\x01\x02\x03"
    with pytest.raises(DCSaveError):
        DCSave.parse(bytes(blob))
