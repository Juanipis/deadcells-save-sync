"""Read/write the Dead Cells save container (PC and mobile).

Header layout (59 bytes) followed by a zlib-compressed payload:

    0   4  magic      0xDEADCE11 (PC)  |  0x20DEAD19 (mobile, stored little-endian)
    4   1  version    1 (PC)  |  2 (mobile)
    5  20  sha1       SHA-1 of the whole file computed with these 20 bytes zeroed
   25  20  githash    commit of the build that wrote the save (fixed sentinel on mobile)
   45  10  builddate  "YYYY-MM-DD" in UTF-8, no length prefix
   55   4  flags      u32 LE bitmask: which chunks the payload carries

The payload decompresses to a sequence of chunks in ascending bit order. Each
data chunk is ``[u32 LE size][contents]``.

The SHA-1 is the only integrity check and is recomputable, so modified saves can
be written back. Verified empirically against Dead Cells v35 (Steam macOS and the
Netflix mobile build).
"""
import hashlib
import struct
import zlib

MAGIC_PC = b"\xde\xad\xce\x11"
MAGIC_MOBILE = b"\x19\xad\xde\x20"  # 0x20DEAD19 in little-endian, as written on disk
HEADER_LEN = 59

# (bit, name, kind). kind None -> feature flag, carries no chunk.
FLAG_ORDER = [
    (0x001, "S_User", "hxbit"),
    (0x002, "S_Game", "hxbit"),
    (0x004, "S_UserAndGameData", "hxbit"),
    (0x008, "S_Date", "date"),
    (0x010, "S_Experimental", None),
    (0x020, "S_UsesMods", None),
    (0x040, "S_HaveLore", None),
    (0x080, "S_VersionNumber", "float"),
    (0x100, "S_DLCMask", "raw"),
]
FLAG_BY_NAME = {n: (b, t) for b, n, t in FLAG_ORDER}
FEATURE_FLAG_MASK = 0x010 | 0x020 | 0x040


class DCSaveError(ValueError):
    """Raised when a file is not a recognizable / valid Dead Cells save."""


class DCSave:
    """A parsed Dead Cells save container."""

    def __init__(self, magic, version, sha1, githash, builddate, flags, chunks):
        self.magic = magic
        self.version = version
        self.sha1 = sha1
        self.githash = githash
        self.builddate = builddate
        self.flags = flags
        self.chunks = chunks  # dict name -> raw chunk contents (bytes)

    # ------------------------------------------------------------------ read
    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    @classmethod
    def parse(cls, raw):
        if len(raw) < HEADER_LEN:
            raise DCSaveError("file too small to be a Dead Cells save")
        magic = raw[0:4]
        if magic not in (MAGIC_PC, MAGIC_MOBILE):
            raise DCSaveError("unknown magic: %s" % magic.hex())
        version = raw[4]
        sha1 = raw[5:25]
        githash = raw[25:45]
        builddate = raw[45:55].decode("utf-8", "replace")
        flags = struct.unpack_from("<I", raw, 55)[0]

        zeroed = bytearray(raw)
        zeroed[5:25] = b"\x00" * 20
        if hashlib.sha1(bytes(zeroed)).digest() != sha1:
            raise DCSaveError("header SHA-1 mismatch: file is corrupt or truncated")

        try:
            payload = zlib.decompress(raw[HEADER_LEN:])
        except zlib.error as exc:
            raise DCSaveError("payload is not valid zlib: %s" % exc)

        chunks, p = {}, 0
        for bit, name, kind in FLAG_ORDER:
            if not (flags & bit) or kind is None:
                continue
            (size,) = struct.unpack_from("<I", payload, p)
            p += 4
            chunks[name] = payload[p:p + size]
            p += size
        if p != len(payload):
            raise DCSaveError("payload has %d unconsumed bytes" % (len(payload) - p))
        return cls(magic, version, sha1, githash, builddate, flags, chunks)

    # ----------------------------------------------------------------- write
    def build(self):
        """Serialize to bytes, recomputing flags and the header SHA-1."""
        flags = self.flags & FEATURE_FLAG_MASK  # keep feature flags, rebuild chunk flags
        for bit, name, kind in FLAG_ORDER:
            if kind is not None and name in self.chunks:
                flags |= bit

        payload = bytearray()
        for bit, name, kind in FLAG_ORDER:
            if kind is None or name not in self.chunks:
                continue
            body = self.chunks[name]
            payload += struct.pack("<I", len(body)) + body

        out = bytearray()
        out += self.magic
        out += bytes([self.version])
        out += b"\x00" * 20  # SHA-1 placeholder
        out += self.githash
        out += self.builddate.encode("utf-8").ljust(10, b" ")[:10]
        out += struct.pack("<I", flags)
        assert len(out) == HEADER_LEN, len(out)
        out += zlib.compress(bytes(payload), 9)

        out[5:25] = hashlib.sha1(bytes(out)).digest()
        return bytes(out)

    def save(self, path):
        data = self.build()
        with open(path, "wb") as fh:
            fh.write(data)
        return len(data)

    # --------------------------------------------------------------- helpers
    @property
    def platform(self):
        return "PC" if self.magic == MAGIC_PC else "mobile"

    def game_version(self):
        c = self.chunks.get("S_VersionNumber")
        return struct.unpack("<f", c[:4])[0] if c and len(c) >= 4 else None

    def date(self):
        c = self.chunks.get("S_Date")
        return struct.unpack("<d", c[:8])[0] if c and len(c) >= 8 else None

    def dlc_mask(self):
        c = self.chunks.get("S_DLCMask")
        return struct.unpack("<I", c[:4])[0] if c and len(c) >= 4 else None

    def flag_names(self):
        return [n for b, n, _ in FLAG_ORDER if self.flags & b]
