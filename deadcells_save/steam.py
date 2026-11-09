"""Locate the Steam Dead Cells save and install a new one safely.

Dead Cells' Steam AppID is 588650. Saves live under Steam's per-user cloud
folder::

    <steam>/userdata/<accountid>/588650/remote/user_0.dat

Steam Cloud tracks each file's SHA-1/size in ``remotecache.vdf``. The safe way to
replace a save is: fully quit Steam, replace the file, relaunch. Because only the
local side changed relative to ``remotecache.vdf``, Steam uploads the local file
to the cloud (no conflict). Never edit the save while Steam is running.
"""
import glob
import hashlib
import os
import platform
import shutil
import time

STEAM_APPID = "588650"


def steam_root():
    """Best-effort path to the Steam installation for the current OS."""
    home = os.path.expanduser("~")
    candidates = []
    system = platform.system()
    if system == "Darwin":
        candidates.append(os.path.join(home, "Library/Application Support/Steam"))
    elif system == "Linux":
        candidates += [
            os.path.join(home, ".steam/steam"),
            os.path.join(home, ".local/share/Steam"),
            os.path.join(home, ".var/app/com.valvesoftware.Steam/data/Steam"),
        ]
    else:  # Windows
        candidates += [
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
        ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def find_saves(root=None):
    """Return a list of Dead Cells ``user_0.dat`` paths across all Steam accounts."""
    root = root or steam_root()
    if not root:
        return []
    pattern = os.path.join(root, "userdata", "*", STEAM_APPID, "remote", "user_0.dat")
    return sorted(glob.glob(pattern))


def sha1_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def install(new_save_path, target_path, backup_dir=None):
    """Back up the current save and replace it. Assumes Steam is CLOSED.

    Returns the path of the backup that was made (or None if there was nothing
    to back up).
    """
    made_backup = None
    if os.path.exists(target_path):
        backup_dir = backup_dir or os.path.dirname(target_path)
        os.makedirs(backup_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        made_backup = os.path.join(backup_dir, "user_0.dat.bak-%s" % stamp)
        shutil.copy2(target_path, made_backup)
    shutil.copy2(new_save_path, target_path)
    return made_backup
