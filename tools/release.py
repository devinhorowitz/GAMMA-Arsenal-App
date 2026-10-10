"""Package Arsenal for a release: build/Arsenal-<version>.zip, one folder "Arsenal" holding
gamedata/ (the mod), README.md and LICENSE, so MO2's quick installer finds gamedata/ and
installs it like any mod. The tests run first; the zip is kept only when every file in it
matches its source byte for byte (the README's images point at the GitHub copies, since the
zip carries none) and gamedata/ holds the mod's files and nothing else.

    python release.py
"""
import hashlib
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GD = os.path.join(ROOT, "gamedata")
RAW = "https://raw.githubusercontent.com/devinhorowitz/GAMMA-Arsenal-App/main/"
TESTS = ["test_data.py", "test_collection.py", "test_ui.py", "test_mcm.py", "test_intel.py", "test_mac.py",
         "test_workbench.py", "test_workbench_ui.py", "test_compare.py"]


def version():
    src = open(os.path.join(HERE, "build.py"), encoding="utf-8").read()
    return re.search(r'^VERSION = "([^"]+)"', src, re.M).group(1)


def main():
    for t in TESTS:
        r = subprocess.run([sys.executable, os.path.join(HERE, t)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        last = (r.stdout.strip().splitlines() or ["no output"])[-1]
        print("  %-20s %s" % (t, last))
        if r.returncode != 0:
            raise SystemExit("refusing to package: %s failed" % t)

    v = version()
    out = os.path.join(ROOT, "build")
    os.makedirs(out, exist_ok=True)
    zp = os.path.join(out, "Arsenal-%s.zip" % v)

    entries = []                          # (archive name, bytes)
    for base, _, names in os.walk(GD):
        for n in names:
            p = os.path.join(base, n)
            entries.append(("Arsenal/gamedata/" + os.path.relpath(p, GD).replace(os.sep, "/"), open(p, "rb").read()))
    entries.sort()
    mod_files = len(entries)
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    readme = re.sub(r'(\]\(|src=")media/', lambda m: m.group(1) + RAW + "media/", readme)
    entries.append(("Arsenal/README.md", readme.encode("utf-8")))
    entries.append(("Arsenal/LICENSE", open(os.path.join(ROOT, "LICENSE"), "rb").read()))

    tmp = zp + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in entries:
            z.writestr(name, data)

    with zipfile.ZipFile(tmp) as z:
        names = z.namelist()
        bad = [n for n, data in entries if z.read(n) != data]
    in_gd = [n for n in names if n.startswith("Arsenal/gamedata/")]
    problems = []
    if bad:
        problems.append("differs from its source: %s" % bad)
    if len(in_gd) != mod_files or mod_files < 13:
        problems.append("gamedata/ holds %d files, the mod has %d" % (len(in_gd), mod_files))
    if {n.split("/", 1)[0] for n in names} != {"Arsenal"}:
        problems.append("more than one top folder")
    if not any(n.startswith("Arsenal/gamedata/scripts/") for n in names):
        problems.append("no scripts")
    if "media/" in readme.replace(RAW + "media/", ""):
        problems.append("the README still points at media/ in the zip")
    if problems:
        os.remove(tmp)
        raise SystemExit("refusing to package: " + "; ".join(problems))
    os.replace(tmp, zp)
    digest = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    print("%s\n  %d files (%d in gamedata/), %d bytes, sha256 %s" % (zp, len(names), len(in_gd),
                                                                     os.path.getsize(zp), digest))


if __name__ == "__main__":
    main()
