#!/usr/bin/env python3
"""dcsync - read, compare and sync Dead Cells save files.

Subcommands:
  info      <save.dat>                       Show container + progression summary
  compare   <a.dat> <b.dat>                  Compare progression and S_User schema
  convert   <src.dat> <dst.dat> <out.dat>    Rebuild src's progression in dst's container
  extract   <backup_dir> <out_dir>           Extract Dead Cells from an iOS backup
  keytool   <backup_dir>                      Launch the local password-testing web UI
  steam-find                                  Locate Steam Dead Cells save(s)

The backup password is read from the IOS_BACKUP_PW environment variable (never
written to disk). See README.md and CLAUDE.md for the full workflow.
"""
import argparse
import os
import sys
import time

from deadcells_save.container import DCSave
from deadcells_save import convert as convmod
from deadcells_save import progression as prog


def _describe(tag, s):
    v, d, m = s.game_version(), s.date(), s.dlc_mask()
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d)) if d else "?"
    print("%s: %s container v%d | build %s | game v%s | DLCMask %s | %s" % (
        tag, s.platform, s.version, s.builddate, v, m, when))
    print("   flags : %s" % ", ".join(s.flag_names()))
    print("   chunks: %s" % ", ".join("%s=%d" % (k, len(v)) for k, v in s.chunks.items()))


def cmd_info(args):
    s = DCSave.load(args.save)
    _describe("SAVE", s)
    print()
    if "S_User" in s.chunks:
        prog.report(s.chunks["S_User"], os.path.basename(args.save))


def cmd_compare(args):
    a, b = DCSave.load(args.a), DCSave.load(args.b)
    _describe("A", a)
    _describe("B", b)
    print()
    if "S_User" in a.chunks and "S_User" in b.chunks:
        _, diff, lines = convmod.schema_report(a, b, "A", "B")
        print("S_User schema: %d differing classes" % len(diff))
        for l in lines:
            print(l)
        if not lines:
            print("  (schemas identical -> direct transplant, no migration)")
        print()
        prog.diff(a.chunks["S_User"], b.chunks["S_User"],
                  os.path.basename(args.a), os.path.basename(args.b))


def cmd_convert(args):
    src, dst = DCSave.load(args.src), DCSave.load(args.dst)
    _describe("SOURCE", src)
    _describe("DEST  ", dst)
    print()
    _, diff, lines = convmod.schema_report(src, dst, "source", "dest")
    for l in lines:
        print(l)
    if not lines:
        print("S_User schemas identical -> clean transplant.")
    print()
    out = convmod.convert(src, dst, keep_run=args.keep_run)
    n = out.save(args.out)
    check = DCSave.load(args.out)  # revalidates SHA-1 + structure
    print("Wrote %s (%d bytes)" % (args.out, n))
    _describe("OUTPUT", check)


def cmd_extract(args):
    from deadcells_save import ios_backup
    pw = os.environ.get("IOS_BACKUP_PW")
    if not pw:
        sys.exit("Set IOS_BACKUP_PW in the environment (never pass it on the command line).")
    if args.list:
        files = ios_backup.list_files(args.backup_dir, pw)
        print("Dead Cells files in backup (%d):" % len(files))
        for dom, rel in files:
            print("  [%s] %s" % (dom.split("-", 1)[-1][:40], rel))
        return
    files = ios_backup.extract(args.backup_dir, pw, args.out_dir)
    print("Extracted %d files into %s" % (len(files), args.out_dir))
    save = ios_backup.find_user_save(args.out_dir)
    if save:
        print("Save file: %s" % save)


def cmd_keytool(args):
    from tools import keytool
    keytool.run(args.backup_dir, args.out_dir, port=args.port)


def cmd_steam_find(args):
    from deadcells_save import steam
    root = steam.steam_root()
    print("Steam root:", root or "not found")
    saves = steam.find_saves(root)
    if not saves:
        print("No Dead Cells saves found.")
        return
    for p in saves:
        print("  %s  (sha1 %s)" % (p, steam.sha1_file(p)[:12]))


def main(argv=None):
    p = argparse.ArgumentParser(prog="dcsync", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info"); s.add_argument("save"); s.set_defaults(func=cmd_info)

    s = sub.add_parser("compare"); s.add_argument("a"); s.add_argument("b")
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser("convert")
    s.add_argument("src"); s.add_argument("dst"); s.add_argument("out")
    s.add_argument("--keep-run", action="store_true",
                   help="also carry the in-progress run (not recommended cross-platform)")
    s.set_defaults(func=cmd_convert)

    s = sub.add_parser("extract")
    s.add_argument("backup_dir"); s.add_argument("out_dir", nargs="?", default="extracted")
    s.add_argument("--list", action="store_true", help="only list files, do not extract")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("keytool")
    s.add_argument("backup_dir"); s.add_argument("out_dir", nargs="?", default="extracted")
    s.add_argument("--port", type=int, default=8777)
    s.set_defaults(func=cmd_keytool)

    s = sub.add_parser("steam-find"); s.set_defaults(func=cmd_steam_find)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
