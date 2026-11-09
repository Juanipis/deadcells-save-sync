"""Human-readable progression from a Dead Cells ``S_User`` chunk.

The hxbit *type* encoding is not decoded here; instead the text identifiers the
game serializes in the data region (blueprints, runes, lore rooms, biomes,
monsters) are recovered. That is enough to compare two saves and see which is
further along.

Schema/data boundary: the schema section contains exactly one field-name array
per class, each preceded by a length byte of ``n+1``. After consuming as many
arrays as there are classes, the data region begins.
"""
import string

from .hxbit import parse_classes

IDENT = set(string.ascii_letters + string.digits + "_.")

# Identifiers used for permanent runes/unlocks (labels are best-effort).
RUNES = {
    "LadderKey": "Vine rune",
    "ExploKey": "Ram rune",
    "TeleportKey": "Teleportation rune",
    "HomKey": "Homunculus rune",
    "ChallengeKey": "Challenge rune",
    "SpawnKey": "Spawn rune",
    "BossRune1": "Boss rune I",
    "BossRune2": "Boss rune II",
    "WallJumpKey": "Wall-jump / Spider rune",
    "BreakableGroundKey": "Breakable-ground rune",
    "CustomKey": "Custom mode",
    "ScoringKey": "Scoring / daily mode",
    "TrainingUnlock": "Training room",
    "BossRushStatue": "Boss Rush",
    "ArmoryUnlock": "Armory",
}


def _read_run(chunk, p):
    """Read a run of consecutive length-prefixed strings from ``p``."""
    out, n = [], len(chunk)
    while p < n:
        ln = chunk[p]
        if not (2 <= ln <= 40) or p + ln > n:
            break
        raw = chunk[p + 1:p + ln]
        if not raw or any(chr(c) not in IDENT for c in raw):
            break
        if not (chr(raw[0]).isalpha() or raw[0] == 0x5F):
            break
        out.append(raw.decode())
        p += ln
    return out, p


def data_start(chunk):
    """Offset where the schema ends and the data region begins."""
    _, _, classes, p = parse_classes(chunk)
    n, seen = len(chunk), 0
    while p < n and seen < len(classes):
        run, end = _read_run(chunk, p + 1)
        if run and chunk[p] == len(run) + 1:
            seen += 1
            p = end
        else:
            p += 1
    return p


def data_strings(chunk):
    """All text identifiers in the data region, in order of appearance."""
    p, n = data_start(chunk), len(chunk)
    out = []
    while p < n:
        run, end = _read_run(chunk, p)
        if run:
            out.extend(run)
            p = end
        else:
            p += 1
    return out


def summarize(chunk):
    names = data_strings(chunk)
    uniq = list(dict.fromkeys(names))
    runes = [t for t in uniq if t in RUNES]
    return {
        "all": uniq,
        "runes": runes,
        "biome_transitions": [t for t in uniq if t.startswith("T_")],
    }


def report(chunk, label):
    s = summarize(chunk)
    print("=== %s ===" % label)
    print("Unique identifiers in data region: %d" % len(s["all"]))
    print()
    print("Runes / modes unlocked (%d):" % len(s["runes"]))
    for r in s["runes"]:
        print("   - %-20s %s" % (r, RUNES[r]))
    print()
    print("Biome transitions recorded: %d" % len(s["biome_transitions"]))
    return s


def diff(chunk_a, chunk_b, label_a="A", label_b="B"):
    sa, sb = summarize(chunk_a), summarize(chunk_b)
    A, B = set(sa["all"]), set(sb["all"])
    only_a = [t for t in sa["all"] if t not in B]
    only_b = [t for t in sb["all"] if t not in A]
    print("%s: %d identifiers | %s: %d identifiers" % (label_a, len(A), label_b, len(B)))
    print()
    print("Only in %s (%d):\n   %s" % (label_a, len(only_a), ", ".join(only_a) or "-"))
    print()
    print("Only in %s (%d):\n   %s" % (label_b, len(only_b), ", ".join(only_b) or "-"))
    print()
    ra, rb = set(sa["runes"]), set(sb["runes"])
    print("Runes only in %s: %s" % (label_a, ", ".join(sorted(ra - rb)) or "-"))
    print("Runes only in %s: %s" % (label_b, ", ".join(sorted(rb - ra)) or "-"))
    return sa, sb
