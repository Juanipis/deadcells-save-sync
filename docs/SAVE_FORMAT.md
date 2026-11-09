# Dead Cells save file format

Reverse-engineered and verified empirically against **Dead Cells v35** — the
Steam build on macOS and the **Netflix mobile** build (`Dead Cells: Return to
Castlevania`, bundle id `com.netflix.NGP.DeadCellsReturnToCastlevania`) on iOS —
and cross-checked with the community modding docs (see Sources).

## Container

A fixed **59-byte header** followed by a **zlib** blob.

| Offset | Bytes | Field | Notes |
|-------:|------:|-------|-------|
| 0  | 4  | `magic`     | `DE AD CE 11` on PC · `19 AD DE 20` on mobile (that is `0x20DEAD19` little-endian) |
| 4  | 1  | `version`   | `1` on PC · `2` on mobile |
| 5  | 20 | `sha1`      | **SHA-1 of the entire file with these 20 bytes set to `0x00`** |
| 25 | 20 | `githash`   | commit of the build that wrote the save (a fixed sentinel on mobile) |
| 45 | 10 | `builddate` | `YYYY-MM-DD` in UTF-8, no length prefix |
| 55 | 4  | `flags`     | u32 LE bitmask: which chunks the payload carries |

The SHA-1 is the file's only integrity check and is **recomputable**, so modified
saves can be written back with a valid header.

## Flags and chunks

Decompressing the payload yields chunks in ascending bit order. Each *data* chunk
is `[u32 LE size][contents]`. Feature-flag bits carry no chunk.

| Bit | Value | Name | Content |
|----:|------:|------|---------|
| 0 | `0x001` | `S_User`            | hxbit — persistent meta-progression |
| 1 | `0x002` | `S_Game`            | hxbit — in-progress run state |
| 2 | `0x004` | `S_UserAndGameData` | hxbit — snapshot of User at run start |
| 3 | `0x008` | `S_Date`            | `f64` LE, unix timestamp |
| 4 | `0x010` | `S_Experimental`    | *(feature flag, no chunk)* |
| 5 | `0x020` | `S_UsesMods`        | *(feature flag, no chunk)* |
| 6 | `0x040` | `S_HaveLore`        | *(feature flag, no chunk)* |
| 7 | `0x080` | `S_VersionNumber`   | `f32` LE, game version |
| 8 | `0x100` | `S_DLCMask`         | `u32` LE |

## hxbit chunks

The `S_*` data chunks are [hxbit](https://github.com/HeapsIO/hxbit) (Haxe)
serialization, and are **self-describing**:

```
[len+1]["HXS"] [u8 version]
( [len+1][class name] [u16 BE clid] [u32 crc] )*  [0x00]
... schema definitions: per class, an array of field names, then their types ...
... object data ...
```

Strings are length-prefixed with **+1** (`0x00` = null). The `crc` is each
class's **schema fingerprint**:

> **same class name + same crc ⇒ identical on-disk layout ⇒ data is interchangeable.**

The `clid` is only a per-build registration index; it can differ between builds
even when the crc (and therefore the layout) is identical. That is exactly what
happens between the Netflix mobile build and the Steam build of the same game
version: the `tool.*` classes have identical crcs but clids offset by a few.

The hxbit *type* encoding is not documented here, so numeric values are not
decoded. Text identifiers in the data region (blueprints, runes, lore rooms,
biomes, monsters) are recovered heuristically, which is enough to compare saves.

### Observed `S_User` classes (v35)

`User`, `MonsterStat`, `BiomeStat`, `UserStats`, `tool.ItemProgress`,
`tool.ItemMetaManager`, `tool.SpeedrunData`, `tool.StoryManager`, `tool.Tutorial`,
`tool.bossRush.BossRushData`.

`S_Game` carries ~90 entity classes (`en.hero.Beheaded`, `en.inter.CursedChest`,
…) — the live run state, not progression.

## Platform notes

- **Netflix mobile** bundles all DLC; a mobile save typically has a much larger
  `S_User` and `DLCMask` with several bits set (e.g. `31` = `0x1F`).
- **Steam** with all DLC owned has been observed with `DLCMask = 1`; the game
  re-evaluates DLC ownership at runtime, so keeping the destination's mask is
  safe when transplanting.
- Cross-platform transplant works cleanly when both saves are the **same game
  version** (identical schema crcs). Different versions may still load via
  hxbit's embedded schema migration, but that is not guaranteed.

## Sources

- Dead Cells Community Modding Docs — <https://n3rdl0rd.github.io/ModDocCE/files/save>
- hxbit — <https://github.com/HeapsIO/hxbit>
