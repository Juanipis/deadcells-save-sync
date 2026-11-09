# CLAUDE.md — reproducing a Netflix→Steam Dead Cells save transfer

This file is written **for an AI coding assistant (Claude Code)** helping a user
move their Dead Cells progression from the **Netflix mobile** build on an iPhone
to the **Steam** build on desktop. Follow it top to bottom. It captures
everything learned doing this for real on Dead Cells v35 (iOS 26 → Steam macOS).

## The one-paragraph mental model

Dead Cells saves are a 59-byte header (`magic`, `version`, a **recomputable**
SHA-1, git hash, build date, a flags bitmask) followed by a zlib blob of
`[u32 size][bytes]` chunks. The important chunk is `S_User` — persistent
meta-progression, serialized with **hxbit** (Haxe), which is *self-describing*:
it embeds its class list with a schema-CRC per class. **Same class name + same
CRC = identical layout = data is interchangeable.** So if the mobile and Steam
builds are the same game version, you can lift the mobile `S_User` straight into a
PC container. That's the whole trick. See `docs/SAVE_FORMAT.md`.

## Hard-won gotchas (read these first)

1. **You cannot pull the file directly.** The Netflix app has no
   `UIFileSharingEnabled` and its container isn't vendable over AFC. `afcclient
   --documents`/`--container` and `ideviceinstaller archive` all fail. The only
   route on a non-jailbroken device is a **full device backup**.
2. **The backup is probably encrypted, and the password is NOT the passcode.**
   `ideviceinfo -q com.apple.mobile.backup -k WillEncrypt` → `true`. The password
   is whatever was set in Finder/iTunes "Encrypt local backup", possibly years
   ago. You can *create* the backup without it; you need it only to *read* it.
   - If the user can't recall it: ask what they were doing when they might have
     enabled it (a prior sync, a script, another project). In the real case it
     had been set by the user's own earlier tool, and the password was a simple
     personal string they recognized once prompted.
   - Last resort with no password: on the iPhone, *Settings → General → Transfer
     or Reset → Reset → Reset All Settings*. This keeps apps/data/saves but wipes
     the backup password (and Wi-Fi passwords). Then re-backup **unencrypted**.
     You cannot simply untick encryption in Finder without the current password.
3. **Mobile magic is little-endian.** The container magic is `0x20DEAD19`, stored
   on disk as bytes `19 AD DE 20`. PC is `DE AD CE 11`. Version is 2 (mobile) / 1
   (PC).
4. **The header SHA-1 is over the whole file with its own 20 bytes zeroed.** It's
   the only integrity check and is recomputable, so edits are possible. If a save
   won't load, first verify this SHA-1.
5. **Don't carry `S_Game` across platforms.** It's the in-progress run: ~90
   build-specific entity classes. Transplant only `S_User` (+ keep the
   destination's `S_VersionNumber` and `S_DLCMask`). The result is "full
   progression, no active run", which is clean.
6. **Steam Cloud will fight you if Steam is running.** Quit Steam completely
   before touching the file. After replacing it and relaunching, Steam sees only
   the local side changed and uploads it (verify in `remotecache.vdf`: the
   `sha`/`size` should update to your new file). If both local and cloud changed
   you'll get a conflict dialog — choose local.

## Prerequisites

```bash
brew install libimobiledevice ideviceinstaller       # macOS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Confirm the device: `idevice_id -l` then
`ideviceinfo | grep -E 'DeviceName|ProductVersion'`.
Confirm the app is installed: `ideviceinstaller list | grep -i deadcells`
→ `com.netflix.NGP.DeadCellsReturnToCastlevania`.

## Step-by-step

### 1. Back up BOTH sides first (non-negotiable)
- Steam save: copy `<steam>/userdata/<accountid>/588650/remote/` somewhere safe
  and record `shasum -a256`. Find it with `python dcsync.py steam-find`.
- iPhone: `idevicebackup2 backup --full ./ios-backup` (may prompt for the device
  passcode on-screen; it can take 30–60 min). This is a full device backup, tens
  of GB — check space with `ideviceinfo -q com.apple.disk_usage`.

### 2. Get the backup password → extract Dead Cells
- If unknown, launch the trial UI and let the user type candidates:
  `python dcsync.py keytool ./ios-backup/<UDID> ./extracted`
  (each attempt is a few seconds; ~10M-iteration PBKDF2).
- If known: `IOS_BACKUP_PW='...' python dcsync.py extract ./ios-backup/<UDID> ./extracted`
- The save is `.../AppDomain-com.netflix.NGP.DeadCellsReturnToCastlevania/Documents/save/<ID>/user_0.dat`.
  **Back this up too** before proceeding.

### 3. Understand and compare
```bash
python dcsync.py info    ./extracted/**/save/*/user_0.dat
python dcsync.py compare ./extracted/**/save/*/user_0.dat "<steam>/.../remote/user_0.dat"
```
Confirm the game versions match and the `S_User` schema CRCs are identical (the
tool prints "schemas identical" when clids differ but CRCs match — that's fine
and expected). Decide direction from which save has more identifiers.

### 4. Convert
```bash
python dcsync.py convert ./extracted/**/save/*/user_0.dat \
                         "<steam>/.../remote/user_0.dat" \
                         merged_user_0.dat
python dcsync.py info merged_user_0.dat     # re-validates SHA-1 + structure
```

### 5. Install into Steam
1. Quit Steam completely (`osascript -e 'quit app "Steam"'` on macOS) and wait
   until no `steam_osx` process remains. Confirm the file is free with `lsof`.
2. Copy `merged_user_0.dat` over `<steam>/.../remote/user_0.dat` (the backup from
   step 1 is your rollback).
3. Relaunch Steam. Watch the file for ~60s to confirm it isn't reverted from the
   cloud, then check `remotecache.vdf` shows the new `sha`/`size`.
4. Launch Dead Cells and have the user verify unlocks in-game. (Programmatic
   screenshots may be blocked by macOS screen-recording permissions — ask the
   user to look.)

## Rollback
Quit Steam, copy the step-1 backup back over `remote/user_0.dat`, relaunch.

## Verifying you did it right
- `dcsync info` on the merged file: PC container v1, `S_User` size equal to the
  mobile save's, game version equal to the Steam save's.
- After the user plays, the game rewrites `user_0.dat` (its sha changes) — that
  confirms the save was accepted and is in active use.

## Repo layout
- `deadcells_save/` — library: `container.py` (format), `hxbit.py` (schema),
  `progression.py` (readable progression), `convert.py` (transplant),
  `ios_backup.py` (extraction), `steam.py` (locate/install).
- `dcsync.py` — CLI. `tools/keytool.py` — password-finder web UI.
- `docs/SAVE_FORMAT.md` — byte-level format. `tests/` — synthetic round-trip tests.

## Privacy rules when working in this repo
Never commit or print: the iOS backup password, device UDID/serial, Wi-Fi MAC,
Steam account id, or any real `.dat`/`.db`/backup file. `.gitignore` already
excludes them; keep it that way.
