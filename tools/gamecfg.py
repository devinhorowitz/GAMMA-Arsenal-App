"""The game's configs as the game reads them, for Arsenal's build tools: Mod Organizer 2's
virtual file system and the Modded Exes DLTX loader (src/xrCore/Xr_ini.cpp) over system.ltx.

Layers, highest priority first: MO2's overwrite, the profile's enabled mods in modlist.txt
order (top wins), the game's loose gamedata, then the base configs unpacked from configs.db0
(Anomaly's converter.exe can unpack it). Archives inside mods are not read. Paths come from
the environment:

    ARSENAL_GAMMA          the MO2 instance (default D:\\GAMMA)
    ARSENAL_PROFILE        its profile (default G.A.M.M.A)
    ARSENAL_ANOMALY        the game (default D:\\ANOMALY)
    ARSENAL_BASE_CONFIGS   the folder the base configs were unpacked to (it holds configs\\)
"""
import collections
import fnmatch
import os
import re
import sys

GAMMA = os.environ.get("ARSENAL_GAMMA", r"D:\GAMMA")
MODLIST = os.path.join(GAMMA, "profiles", os.environ.get("ARSENAL_PROFILE", "G.A.M.M.A"), "modlist.txt")
LOOSE_BASE = os.path.join(os.environ.get("ARSENAL_ANOMALY", r"D:\ANOMALY"), "gamedata")
OVERWRITE = os.path.join(GAMMA, "overwrite", "gamedata")
BASE_CFG = os.environ.get("ARSENAL_BASE_CONFIGS", "")

DELETE = object()

_WS = ''.join(chr(c) for c in range(33))


def xt(s):
    # xrCore _Trim: strips every char <= ' ' (not just whitespace)
    return s.strip(_WS)


def enabled_mods():
    mods = []
    with open(MODLIST, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("+"):
                name = line[1:]
                if name.endswith("_separator"):
                    continue
                mods.append(name)
    return mods


class VFS:
    def __init__(self, sub="configs"):
        self.layers = [("<overwrite>", OVERWRITE)]
        self.mods = enabled_mods()
        for m in self.mods:
            self.layers.append((m, os.path.join(GAMMA, "mods", m, "gamedata")))
        self.layers.append(("<ANOMALY/gamedata loose>", LOOSE_BASE))
        self.layers.append(("<base configs.db0>", BASE_CFG))
        self.files = {}          # rel lower (configs\...) -> (layer, abspath)
        self.all = collections.defaultdict(list)  # rel lower -> [layers...] (every provider)
        self.dirs = collections.defaultdict(set)  # dir lower -> set(file lower)
        self.archives = []
        for name, root in self.layers:
            base = os.path.join(root, sub)
            if not os.path.isdir(base):
                continue
            for dp, dn, fn in os.walk(base):
                for f in fn:
                    ap = os.path.join(dp, f)
                    rel = os.path.relpath(ap, root).lower().replace("/", "\\")
                    self.all[rel].append(name)
                    if rel not in self.files:
                        self.files[rel] = (name, ap)
                    d, b = rel.rsplit("\\", 1)
                    self.dirs[d].add(b)
        for m in self.mods:
            db = os.path.join(GAMMA, "mods", m, "db")
            if os.path.isdir(db):
                for dp, dn, fn in os.walk(db):
                    for f in fn:
                        self.archives.append((m, os.path.join(dp, f)))

    def read(self, rel):
        rel = rel.lower().replace("/", "\\")
        hit = self.files.get(rel)
        if not hit:
            return None, None
        layer, ap = hit
        with open(ap, "rb") as f:
            data = f.read()
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        return data.decode("cp1251", errors="replace"), layer

    def listdir(self, d, mask):
        # CLocatorAPI::file_list without FS_RootOnly: every file under d (subfolders too),
        # PatternMatch'ed on its path relative to d; '*' also crosses '\'.
        d = d.lower().replace("/", "\\").rstrip("\\")
        mask = mask.lower()
        pre = d + "\\" if d else ""
        out = []
        for rel in self.files:
            if rel.startswith(pre):
                entry = rel[len(pre):]
                if fnmatch.fnmatchcase(entry, mask):
                    out.append(entry)
        return sorted(out)


def norm_path(p):
    p = p.replace("/", "\\")
    parts = []
    for seg in p.split("\\"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "\\".join(parts)


class Item:
    __slots__ = ("key", "value", "depth", "idx", "file", "layer")

    def __init__(self, key, value, depth, file, layer):
        self.key, self.value, self.depth, self.file, self.layer = key, value, depth, file, layer
        self.idx = 0


class Loader:
    def __init__(self, vfs):
        self.vfs = vfs
        self.BaseData = {}
        self.BaseOrigin = {}
        self.BaseParents = {}
        self.OverrideData = {}
        self.OverrideParents = {}
        self.OverrideOrigins = collections.defaultdict(list)   # sec -> [(file, layer)]
        self.ModifyList = collections.defaultdict(list)
        self.SectionsToDelete = set()
        self.dups = []
        self.missing_includes = []
        self.files_loaded = []
        self.mod_files = []

    @staticmethod
    def merge_parent_set(base, override, include_removers):
        for p in override:
            removal = p.startswith("!")
            stale = (p[1:] if removal else "!" + p)
            base[:] = [x for x in base if x != stale]
            if include_removers or not removal:
                base.append(p)

    def insert_item(self, sect_name, items, it):
        if it.key and it.key[0] in "<>":
            lst = self.ModifyList[sect_name]
            lst.append(it)
            it.idx = len(lst)
            return
        it.idx = len(items)
        items.append(it)

    def load(self, rel, depth, is_root=False):
        text, layer = self.vfs.read(rel)
        if text is None:
            self.missing_includes.append(rel)
            return
        self.files_loaded.append((rel, layer, depth))
        cur_dir = rel.rsplit("\\", 1)[0] if "\\" in rel else ""
        cur = None   # (kind, name, items)
        marked_create = set()

        def stash():
            nonlocal cur
            if cur is None:
                return
            kind, name, items = cur
            if kind == "base":
                if name in self.BaseData:
                    self.dups.append((name, self.BaseOrigin[name], (rel, layer)))
                else:
                    self.BaseData[name] = items
                    self.BaseOrigin[name] = (rel, layer)
            else:
                if name in self.OverrideData:
                    tgt = self.OverrideData[name]
                    for it in items:
                        it.idx = len(tgt)
                        tgt.append(it)
                else:
                    self.OverrideData[name] = items
                self.OverrideOrigins[name].append((rel, layer))
            cur = None

        lines = text.splitlines()
        i = 0
        n = len(lines)
        while i < n:
            raw = lines[i]
            i += 1
            s = xt(raw)
            # comments: ';' or '//' (whichever first), unless inside a quoted string
            comm = s.find(";")
            c2 = s.find("//")
            if c2 != -1 and (comm == -1 or c2 < comm):
                comm = c2
            if comm != -1:
                q1 = s.find('"')
                in_q = False
                if q1 != -1 and q1 < comm:
                    q2 = s.find('"', q1 + 1)
                    if q2 != -1 and q2 > comm:
                        in_q = True
                if not in_q:
                    s = s[:comm]
            s = xt(s)
            if not s:
                continue
            if s[0] == "#" and "#include" in s:
                m = re.search(r'"([^"]*)"', s)
                if m:
                    inc = m.group(1)
                    full = norm_path((cur_dir + "\\" if cur_dir else "") + inc)
                    if "*.ltx" in inc.lower():
                        d, mask = full.rsplit("\\", 1)
                        for f in self.vfs.listdir(d, mask):
                            self.load(d + "\\" + f, depth + 1)
                    else:
                        self.load(full, depth + 1)
                continue
            if s.startswith("!!["):
                stash()
                name = s[3:s.index("]")].lower()
                self.SectionsToDelete.add(name)
                continue
            if s[0] == "[" or s.startswith("![") or s.startswith("@["):
                stash()
                is_mod = s.startswith("![") or s.startswith("@[")
                start = 2 if is_mod else 1
                name = s[start:s.index("]")].lower()
                is_override = is_mod
                if s.startswith("@[") and name not in self.BaseData:
                    marked_create.add(name)
                items = []
                cur = ("override" if is_override else "base", name, items)
                k = s.find("]:")
                if k != -1:
                    parents = [xt(p) for p in s[k + 2:].split(",") if xt(p)]
                    mp = self.OverrideParents if is_override else self.BaseParents
                    lst = mp.setdefault(name, [])
                    self.merge_parent_set(lst, parents, True)
                continue
            # key = value
            is_del = s[0] == "!"
            body = s[1:] if is_del else s
            if "=" in body:
                key, val = body.split("=", 1)
                key = xt(key)
                val = xt(val)
                # multi-line quoted values
                while val.count('"') % 2 == 1 and i < n:
                    val += "\r\n" + lines[i]
                    i += 1
                if len(val) >= 2 and val[0] == '"' and val[-1] == '"' and val.count('"') == 2:
                    val = val[1:-1]
                value = val if val != "" else None
            else:
                key = xt(body)
                value = None
            if not key:
                continue
            if is_del:
                value = DELETE
            if cur is None:
                continue
            it = Item(key, value, depth, rel, layer)
            self.insert_item(cur[1], cur[2], it)
        stash()

        if is_root:
            # DLTX mod files for this root: mod_<name>_*.ltx in the same folder
            stem = rel.rsplit("\\", 1)[-1][:-4]
            ambiguous = [f[:-4] for f in self.vfs.listdir(cur_dir, stem + "_*.ltx")]
            mods = self.vfs.listdir(cur_dir, "mod_" + stem + "_*.ltx")
            d = -200
            self.mod_files = []
            for mf in mods:
                if any(re.fullmatch("mod_" + a + "_.+.ltx", mf) for a in ambiguous):
                    continue
                self.mod_files.append(mf)
                self.load((cur_dir + "\\" if cur_dir else "") + mf, d)
                d += -200
        for name in marked_create:
            if name not in self.BaseData:
                self.BaseData[name] = []
                self.BaseOrigin[name] = (rel, layer)

    @staticmethod
    def sort_filter(items):
        items.sort(key=lambda it: (it.key.encode("cp1251", "replace"), it.depth, -it.idx))
        out = []
        last = None
        for it in items:
            if it.key == last:
                continue
            out.append(it)
            last = it.key
        return out

    @staticmethod
    def merge(base, over, deleted, base_and_mod):
        res = dict(base)
        for k, it in over.items():
            if it.value is DELETE:
                if base_and_mod:
                    deleted.add(k)
                    res.pop(k, None)
                # parent merge: keep the parent's value if any
                continue
            res[k] = it
        return res

    def finalize(self):
        for k in list(self.BaseData):
            self.BaseData[k] = self.sort_filter(self.BaseData[k])
        for k in list(self.OverrideData):
            self.OverrideData[k] = self.sort_filter(self.OverrideData[k])
        self.cache = {}
        self.final_parents = {}
        self.unused_overrides = set(self.OverrideData)
        sys.setrecursionlimit(10000)
        for name in list(self.BaseData):
            self.evaluate(name, [])
        for s in self.SectionsToDelete:
            self.cache.pop(s, None)
        self.unused_overrides -= set(self.cache)
        return self.cache

    def evaluate(self, name, stack):
        if name in self.cache:
            return self.cache[name]
        if name in stack:
            raise RuntimeError("cycle " + " -> ".join(stack + [name]))
        stack = stack + [name]
        bp = self.BaseParents.get(name)
        op = self.OverrideParents.get(name)
        if op is not None and bp is None:
            bp = []
            self.BaseParents[name] = bp
            self.merge_parent_set(bp, op, False)
        elif bp is not None and op is not None:
            self.merge_parent_set(bp, op, False)
        self.final_parents[name] = list(bp or [])
        deleted = set()
        resolved_parents = {}
        for p in (bp or []):
            if p not in self.BaseData:
                self.BaseData[p] = []
                self.BaseOrigin[p] = ("<auto-created parent>", "")
            pd = self.evaluate(p, stack)
            resolved_parents = self.merge(resolved_parents, pd, deleted, False)
        own = {it.key: it for it in self.BaseData.get(name, [])}
        if name in self.OverrideData:
            own = self.merge(own, {it.key: it for it in self.OverrideData[name]}, deleted, True)
            self.unused_overrides.discard(name)
        result = self.merge(resolved_parents, own, deleted, False)
        mods = self.ModifyList.get(name)
        if mods:
            mods = sorted(mods, key=lambda it: (it.key[1:], it.idx))
            for it in mods:
                if it.value is None or it.value is DELETE:
                    continue
                k = it.key[1:]
                if k in result:
                    cur = result[k]
                    vals = [x.strip() for x in (cur.value or "").split(",") if x.strip()]
                elif k not in deleted:
                    vals = []
                else:
                    continue
                add = [x.strip() for x in it.value.split(",") if x.strip()]
                if it.key[0] == ">":
                    vals = vals + add
                else:
                    vals = [v for v in vals if v not in add]
                ni = Item(k, ",".join(vals), it.depth, it.file, it.layer)
                result[k] = ni
            result = {k: v for k, v in result.items() if v.value not in ("",)}
        self.cache[name] = result
        return result


def system():
    """system.ltx resolved: section -> key -> value (None for a key without one)"""
    if not os.path.isdir(os.path.join(BASE_CFG, "configs")):
        raise SystemExit("set ARSENAL_BASE_CONFIGS to the folder the base configs were unpacked to")
    vfs = VFS()
    ld = Loader(vfs)
    ld.load("configs\\system.ltx", 0, is_root=True)
    data = ld.finalize()
    return vfs, {s: {k: (None if it.value is DELETE else it.value) for k, it in v.items()} for s, v in data.items()}
