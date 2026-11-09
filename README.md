# Dead Cells Save Sync — Netflix (mobile) → Steam

Bring your Dead Cells progression from the **Netflix mobile** build
(iPhone/iPad) into the **Steam** build on desktop. Read, inspect, compare and
convert Dead Cells save files — with the byte-level format fully documented.

> Tested end-to-end on **Dead Cells v35**: Netflix iOS (`Dead Cells: Return to
> Castlevania`) → Steam on macOS. Achievements unlocked automatically after the
> transfer. See [`docs/SAVE_FORMAT.md`](docs/SAVE_FORMAT.md) for the format and
> [`CLAUDE.md`](CLAUDE.md) to reproduce the whole thing with Claude Code.

## Why this is not trivial

The Netflix build does **not** expose its files (`UIFileSharingEnabled` is unset
and its container isn't vendable over AFC), so on a non-jailbroken iPhone the
only way to reach `user_0.dat` is via an **iOS device backup**. If that backup is
encrypted, you need the *backup* password (Finder/iTunes "Encrypt local backup")
— which is **not** the device passcode.

Once you have the file, both builds share the same self-describing
[hxbit](https://github.com/HeapsIO/hxbit) save format, so progression transplants
cleanly when the game versions match.

## What it does

- **Parse / validate** the Dead Cells container (`DEADCE11` PC, `20DEAD19`
  mobile), including the recomputable header SHA-1.
- **Inspect** a save: platform, game version, DLC mask, chunks, and a
  human-readable progression summary (runes, blueprints, biomes…).
- **Compare** two saves: which is further along, and whether their `S_User`
  schemas are byte-compatible.
- **Convert** a mobile save into a PC-container save (transplants the persistent
  `S_User` meta-progression; drops the platform-specific in-progress run).
- **Extract** Dead Cells files from an encrypted iOS backup, with a small local
  web UI to find the backup password by trial.
- **Locate** the Steam save across accounts and back up before replacing.

## Install

```bash
git clone https://github.com/Juanipis/deadcells-save-sync
cd deadcells-save-sync
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # only needed for iOS extraction
```

Extraction from a device also needs [`libimobiledevice`](https://libimobiledevice.org)
(`brew install libimobiledevice ideviceinstaller`).

## Quick start (mobile → Steam)

```bash
# 1. Back up the iPhone (encrypted backups are fine; you'll need the password to read it)
idevicebackup2 backup --full ./ios-backup

# 2. Find the backup password (opens a local web UI) and extract Dead Cells
python dcsync.py keytool ./ios-backup/<UDID> ./extracted
#    ...or, if you know the password:
IOS_BACKUP_PW='...' python dcsync.py extract ./ios-backup/<UDID> ./extracted

# 3. Inspect and compare against your Steam save
python dcsync.py steam-find
python dcsync.py compare ./extracted/**/save/*/user_0.dat "<steam>/.../588650/remote/user_0.dat"

# 4. Convert the mobile save into a PC-container save
python dcsync.py convert ./extracted/**/save/*/user_0.dat \
                         "<steam>/.../588650/remote/user_0.dat" \
                         merged_user_0.dat

# 5. QUIT STEAM COMPLETELY, then replace the save and relaunch Steam.
#    (Steam uploads the local file to the cloud; no conflict because only the
#     local side changed. If a Cloud Conflict dialog appears, choose "local".)
```

⚠️ **Always keep a backup of both saves before overwriting anything.** Steam
saves live under `userdata/<accountid>/588650/remote/user_0.dat`.

## CLI

```
dcsync info     <save.dat>                      container + progression summary
dcsync compare  <a.dat> <b.dat>                 compare progression and S_User schema
dcsync convert  <src.dat> <dst.dat> <out.dat>   rebuild src's progression in dst's container
dcsync extract  <backup_dir> [out_dir] [--list] extract Dead Cells from an iOS backup
dcsync keytool  <backup_dir> [out_dir]          local web UI to find the backup password
dcsync steam-find                               locate Steam Dead Cells save(s)
```

## Library

```python
from deadcells_save import DCSave

s = DCSave.load("user_0.dat")     # validates the header SHA-1
print(s.platform, s.game_version(), s.flag_names())
s.chunks["S_User"]                # raw meta-progression chunk (hxbit)
s.save("out.dat")                 # recomputes flags + SHA-1
```

## Other platforms

This targets the **Netflix mobile** build specifically. The paid mobile build
(Playdigious) and console builds use the same container format but a different app
container / access path, which isn't covered here — PRs welcome. The Steam side
is the standard PC format and works as documented.

## Safety & privacy

- The tools never write your backup password to disk; it stays in memory.
- `.gitignore` excludes all saves, backups and iOS manifests so you don't
  accidentally commit personal data.
- Editing saves is at your own risk. Keep backups. This project is not affiliated
  with Motion Twin, Evil Empire, Playdigious, Netflix or Valve.

## License

MIT — see [`LICENSE`](LICENSE).

---

Made by [Juanipis](https://github.com/Juanipis) · [juanipis.xyz](https://juanipis.xyz)
