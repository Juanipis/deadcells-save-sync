"""Read the hxbit schema embedded in Dead Cells save chunks.

Each hxbit chunk starts with an "HXS" marker, a version byte, and a
null-terminated class list::

    [len+1]["HXS"] [u8 version]
    ( [len+1][class name] [u16 BE clid] [u32 crc] )*  [0x00]
    ... schema definitions (field-name arrays + type encodings) ...
    ... object data ...

Strings are length-prefixed with ``len+1`` (``0x00`` means null). The ``crc`` is
the schema fingerprint of each class: **same name + same crc means the on-disk
layout is identical**, which is the criterion for deciding whether two saves are
data-compatible. The ``clid`` is only a per-build registration index and may
differ between builds even when the schema is identical.

The hxbit *type* encoding is not documented, so field names are recovered
heuristically (length-prefixed ASCII identifier runs), which is enough for
inspection and comparison but not for decoding numeric values.
"""
import string

IDENT = set(string.ascii_letters + string.digits + "_.")


def read_str(b, p):
    n = b[p]
    p += 1
    if n == 0:
        return None, p
    return b[p:p + n - 1].decode("utf-8", "replace"), p + n - 1


def parse_classes(chunk):
    """Return (marker, version, [(name, clid, crc_hex)], schema_start_offset)."""
    p = 0
    marker, p = read_str(chunk, p)
    version = chunk[p]
    p += 1
    classes = []
    while True:
        name, p = read_str(chunk, p)
        if name is None:
            break
        clid = int.from_bytes(chunk[p:p + 2], "big")
        p += 2
        crc = chunk[p:p + 4].hex()
        p += 4
        classes.append((name, clid, crc))
    return marker, version, classes, p


def scan_field_names(chunk, start, min_run=3):
    """Heuristically extract runs of length-prefixed field names from ``start``."""
    runs, p, n = [], start, len(chunk)
    while p < n:
        cur, q = [], p
        while q < n:
            ln = chunk[q]
            if not (2 <= ln <= 40) or q + ln > n:
                break
            s = chunk[q + 1:q + ln]
            if not s or any(chr(c) not in IDENT for c in s):
                break
            t = s.decode("ascii")
            if not (t[0].isalpha() or t[0] == "_"):
                break
            cur.append(t)
            q += ln
        if len(cur) >= min_run:
            runs.append((p, cur))
            p = q
        else:
            p += 1
    return runs


def compare_classes(a_classes, b_classes, label_a="A", label_b="B"):
    """Compare two class lists. Returns (same_names, differing_names, report_lines).

    A class is 'same' only if both clid and crc match. In practice the crc
    (schema fingerprint) is what matters for data compatibility; clids differing
    while crcs match means the layout is identical across builds.
    """
    da = {n: (c, k) for n, c, k in a_classes}
    db = {n: (c, k) for n, c, k in b_classes}
    same, diff, out = [], [], []
    for n in sorted(set(da) | set(db)):
        if n not in da:
            out.append("  ONLY IN %s: %s" % (label_b, n))
        elif n not in db:
            out.append("  ONLY IN %s: %s" % (label_a, n))
        elif da[n] != db[n]:
            diff.append(n)
            crc_note = "" if da[n][1] == db[n][1] else "  (CRC DIFFERS -> schema changed)"
            out.append("  DIFF: %-30s %s=clid%s/%s  %s=clid%s/%s%s" % (
                n, label_a, da[n][0], da[n][1], label_b, db[n][0], db[n][1], crc_note))
        else:
            same.append(n)
    return same, diff, out
