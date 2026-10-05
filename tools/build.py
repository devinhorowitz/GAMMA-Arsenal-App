"""Check Arsenal and install it as the MO2 mod "Arsenal".

Writes the generated files (the 1 px rule texture, the Russian string table), then checks:
every XML parses (string tables as windows-1251), every script compiles under LuaJIT, and the
tests pass (test_data, test_collection, test_ui, test_mcm, test_intel, test_mac, test_workbench,
test_workbench_ui). Only then mirrors gamedata/ into
D:\\GAMMA\\mods\\Arsenal\\gamedata (files that are no longer in the source are removed there)
and writes its meta.ini.

    build.py            check and install
    build.py --check    check only
"""
import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GD = os.path.join(ROOT, "gamedata")
MOD = r"D:\GAMMA\mods\Arsenal"
VERSION = "1.1.0"

META = """[General]
modid=0
version={version}
newestVersion=
category=
installationFile=
repository=
gameName=stalkeranomaly
comments=Arsenal {version}: a PDA app (Mod App Creator) cataloging every weapon of the running game.
notes="Built from D:/GAMMA/_baseline/arsenal by tools/build.py. Do not edit here: rebuild."
url=
hasCustomURL=false
"""


def rule_dds(color=(90, 90, 90, 255), size=4):
    """An uncompressed A8R8G8B8 DDS of one color."""
    head = struct.pack("<4s7I44x9I12x4x", b"DDS ", 124, 0x100F, size, size, size * 4, 0, 1,
                       32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, 0x1000)
    r, g, b, a = color
    return head + bytes([b, g, r, a]) * (size * size)


def generate():
    p = os.path.join(GD, "textures", "ui", "arsenal", "ui_rule.dds")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(rule_dds())
    subprocess.run([sys.executable, os.path.join(HERE, "rus_strings.py")], check=True)


def check():
    bad = []
    lua = L.LuaRuntime()
    compiles = lua.eval("function(s) local f, e = loadstring(s) return e end")
    n_xml = n_lua = 0
    for root, _, files in os.walk(GD):
        for f in files:
            p = os.path.join(root, f)
            if f.endswith(".xml"):
                raw = open(p, "rb").read()
                text = raw.decode("cp1251")
                try:
                    ET.fromstring(text.split("?>", 1)[1] if text.startswith("<?xml") else text)
                    n_xml += 1
                except ET.ParseError as e:
                    bad.append("%s: %s" % (p, e))
            elif f.endswith(".script"):
                err = compiles(open(p, encoding="latin-1").read())
                n_lua += 1
                if err:
                    bad.append("%s: %s" % (p, err))
    print("xml parse: %d, scripts compile: %d" % (n_xml, n_lua))
    for t in ("test_data.py", "test_collection.py", "test_ui.py", "test_mcm.py", "test_intel.py", "test_mac.py",
              "test_workbench.py", "test_workbench_ui.py"):
        r = subprocess.run([sys.executable, os.path.join(HERE, t)], capture_output=True, text=True)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]
        print("%-20s %s" % (t, last))
        if r.returncode != 0:
            bad.append(t + ": " + last)
    return bad


def install():
    dst = os.path.join(MOD, "gamedata")
    os.makedirs(dst, exist_ok=True)
    want = set()
    for root, _, files in os.walk(GD):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), GD)
            want.add(rel)
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(os.path.join(root, f), out)
    removed = 0
    for root, _, files in os.walk(dst):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), dst)
            if rel not in want:
                os.remove(os.path.join(root, f))
                removed += 1
    with open(os.path.join(MOD, "meta.ini"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(META.format(version=VERSION))
    print("installed %d files to %s (%d stale removed)" % (len(want), MOD, removed))


def main():
    generate()
    bad = check()
    if bad:
        print("NOT installed:")
        print("\n".join(bad))
        return 1
    if "--check" not in sys.argv:
        install()
    return 0


if __name__ == "__main__":
    sys.exit(main())
