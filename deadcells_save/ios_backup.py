"""Locate and extract Dead Cells (Netflix) save files from an iOS device backup.

The Netflix build of Dead Cells does not declare ``UIFileSharingEnabled`` and its
container is not vendable over AFC/house-arrest, so files cannot be pulled
directly from the device. The only route on a non-jailbroken iPhone is a device
backup (``idevicebackup2 backup``) followed by extracting the app's ``AppDomain``
from it.

If the backup is encrypted, decryption needs the *backup* password (the one set
in Finder/iTunes "Encrypt local backup"), which is NOT the device passcode. This
module never writes the password to disk; it is passed in memory only.

Depends on the ``iphone_backup_decrypt`` package for encrypted backups.
"""
import os

# Bundle identifier of the Netflix build. The paid Steam/console builds use a
# different id and expose files differently; this tool targets Netflix mobile.
NETFLIX_BUNDLE_ID = "com.netflix.NGP.DeadCellsReturnToCastlevania"
DEFAULT_MATCH = "DeadCells"


def _open_backup(backup_dir, passphrase):
    from iphone_backup_decrypt import EncryptedBackup

    backup = EncryptedBackup(backup_directory=backup_dir, passphrase=passphrase.encode("utf-8"))
    backup.test_decryption()
    return backup


def test_passphrase(backup_dir, passphrase):
    """Return True if ``passphrase`` unlocks the backup's keybag. Fast-ish (~seconds)."""
    import plistlib

    from iphone_backup_decrypt import google_iphone_dataprotection as gidp

    with open(os.path.join(backup_dir, "Manifest.plist"), "rb") as fh:
        blob = plistlib.load(fh)["BackupKeyBag"]
    kb = gidp.Keybag(blob)
    return bool(kb.unlockWithPassphrase(passphrase.encode("utf-8")))


def list_files(backup_dir, passphrase, match=DEFAULT_MATCH):
    """List (domain, relative_path) for Dead Cells files inside the backup."""
    backup = _open_backup(backup_dir, passphrase)
    with backup.manifest_db_cursor() as cur:
        cur.execute(
            "SELECT domain, relativePath FROM Files "
            "WHERE domain LIKE ? AND flags=1 ORDER BY domain, relativePath",
            ("%" + match + "%",),
        )
        return cur.fetchall()


def extract(backup_dir, passphrase, out_dir, match=DEFAULT_MATCH):
    """Extract all matching files into ``out_dir`` preserving domain/path. Returns list."""
    backup = _open_backup(backup_dir, passphrase)
    with backup.manifest_db_cursor() as cur:
        cur.execute(
            "SELECT domain, relativePath FROM Files "
            "WHERE domain LIKE ? AND flags=1 ORDER BY domain, relativePath",
            ("%" + match + "%",),
        )
        files = cur.fetchall()

    os.makedirs(out_dir, exist_ok=True)
    extracted = []
    for dom, rel in files:
        dest = os.path.join(out_dir, dom, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            backup.extract_file(relative_path=rel, domain_like=dom, output_filename=dest)
            extracted.append(dest)
        except Exception as exc:  # noqa: BLE001 - keep going on individual failures
            print("  ! failed %s/%s: %s" % (dom, rel, exc))
    return extracted


def find_user_save(out_dir):
    """Find the extracted ``user_0.dat`` (the meta-progression save)."""
    for root, _dirs, files in os.walk(out_dir):
        if "user_0.dat" in files and os.sep + "save" + os.sep in root + os.sep:
            return os.path.join(root, "user_0.dat")
    # fallback: any user_0.dat
    for root, _dirs, files in os.walk(out_dir):
        if "user_0.dat" in files:
            return os.path.join(root, "user_0.dat")
    return None
