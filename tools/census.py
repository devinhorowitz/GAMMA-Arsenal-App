"""Write gamedata/configs/plugins/arsenal_census.ltx: what Arsenal needs to know about the Zone's
people and traders that a script cannot read while the game runs.

The NPC character files (gameplay\\character_desc_*.xml, after their #include) and the NPC logic
files (scripts\\**\\*.ltx) are read from the install, the way the game reads them, and written as:

    [arsenal_dialogs]        who offers which dialog Arsenal names (the Armor Exchange's):
    armor_exchange_insider_duty = bar_petrenko_name          the givers' name strings

    [arsenal_trade]          the trade configs some NPC's logic uses (items\\trade\\<name>.ltx),
    trade_stalker_sidorovich = escape_trader_name            each with its traders' name strings
                                                             ("-" when none has a name of his own);
                                                             a config nobody uses sells nothing

    [arsenal_supplies]       gear a story character carries (his <supplies>), for the story
    wpn_m24 = jup_..._name, ...                              characters a squad spawns; a trader,
                                                             technician, medic or barman keeps
                                                             nothing when he dies and is left out

    [sim_default_duty_2]     per spawn section a squad uses: its characters per rank, and
    characters = trainee:20, experienced:35, ...             those wearing each visual (a suit
    stalker_dolg_2 = trainee:5, experienced:7                and helmet drop by visual)

A spawn section whose profile is a class (a generic fighter) picks one of the class's
characters at random; a character counts at every rank its rank range touches. A section
whose profile names one character (a story NPC, a special squad's member) counts as
"special", with no rank. A visual is its path's third part, as death_manager matches it; a
character the game never picks at random (no_random) is left out.

Run after GAMMA changes these files (gamecfg.py names the settings it needs):
    python census.py
"""
import collections
import datetime
import os
import re

import gamecfg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "gamedata", "configs", "plugins", "arsenal_census.ltx")
FACTIONS = ["stalker", "dolg", "freedom", "csky", "ecolog", "killer", "army", "bandit", "monolith",
            "zombied", "renegade", "greh", "isg"]
# the dialogs whose givers Arsenal names: Grok's and Darkasleif's Armor Exchange
DIALOGS = re.compile(r"^armor_exchange_insider_\w+$")
# the dialogs of traders, technicians, medics and barmen, whose logic keeps nothing on death
SERVICE = {"dm_init_trader", "dm_init_mechanic", "dm_init_medic", "dm_init_batender", "dm_tech_repair"}
# the items whose carriers Arsenal lists: weapons and their addons, suits and helmets
GEAR_CLASSES = {"WP_KNIFE", "E_STLK", "EQU_STLK", "E_HLMET"}


def expand(vfs, rel):
    """an XML file as the engine reads it: #include lines replaced by the files they name
    (relative to configs, wildcards allowed)"""
    text, _ = vfs.read("configs\\" + rel)
    if text is None:
        return ""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") and "#include" in s:
            m = re.search(r'"([^"]*)"', s)
            if m:
                inc = m.group(1).replace("/", "\\")
                if "*" in inc:
                    d, mask = inc.rsplit("\\", 1)
                    for f in vfs.listdir("configs\\" + d, mask):
                        out.append(expand(vfs, d + "\\" + f))
                else:
                    out.append(expand(vfs, inc))
            continue
        out.append(line)
    return "\n".join(out)


def blocks(text, tag):
    """(attributes, body) of each <tag ...>...</tag>, comments left out"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.findall(r"<%s\b([^>]*)>(.*?)</%s>" % (tag, tag), text, re.S)


def field(body, tag):
    return [x.strip() for x in re.findall(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), body, re.S)]


def attr(attrs, name):
    m = re.search(r'%s\s*=\s*"([^"]*)"' % name, attrs)
    return m.group(1) if m else None


def supplies(body):
    """the item sections a character's <supplies> spawn: every line of its [spawn] and
    [spawn_loadout...] sections (a loadout section picks one of its lines)"""
    out = []
    for text in field(body, "supplies"):
        for line in text.replace("\\n", "\n").splitlines():
            s = line.split(";")[0].strip()
            if not s or s.startswith("[") or s.startswith("#"):
                continue
            sec = s.split("=", 1)[0].strip()
            if re.match(r"^[\w\.\-]+$", sec):
                out.append(sec)
    return out


def main():
    vfs, S = gamecfg.system()

    def sv(sec, key):
        return (S.get(sec) or {}).get(key)

    def gear(sec):
        d = S.get(sec)
        if not d:
            return False
        return (d.get("kind") or "").startswith(("w_", "o_")) or d.get("class") in GEAR_CLASSES

    files = [x.strip() for x in (sv("profiles", "specific_characters_files") or "").split(",") if x.strip()]
    pfiles = [x.strip() for x in (sv("profiles", "files") or "").split(",") if x.strip()]
    chars = {}
    offers = collections.OrderedDict()     # dialog -> the name strings of the characters offering it
    for f in files:
        for attrs, body in blocks(expand(vfs, "gameplay\\" + f + ".xml"), "specific_character"):
            cid = attr(attrs, "id")
            name = (field(body, "name") or [None])[0]
            dialogs = field(body, "actor_dialog")
            for d in dialogs:
                if name and DIALOGS.match(d):
                    lst = offers.setdefault(d, [])
                    if name not in lst:
                        lst.append(name)
            rank = re.search(r'<rank\s+min\s*=\s*"(-?\d+)"\s+max\s*=\s*"(-?\d+)"', body)
            single = field(body, "rank")
            if rank:
                lo, hi = int(rank.group(1)), int(rank.group(2))
            elif single and single[0].lstrip("-").isdigit():
                lo = hi = int(single[0])
            else:
                lo = hi = None
            chars[cid] = dict(classes=field(body, "class"), visual=(field(body, "visual") or [None])[-1],
                              no_random=(attr(attrs, "no_random") or "0").strip() in ("1", "true"), rank=(lo, hi),
                              name=name, service=bool(SERVICE & set(dialogs)), supplies=supplies(body))
    profiles = {}
    for f in pfiles:
        for attrs, body in blocks(expand(vfs, "gameplay\\" + f + ".xml"), "character"):
            profiles[attr(attrs, "id")] = dict(cls=(field(body, "class") or [None])[0],
                                               char=(field(body, "specific_character") or [None])[0])
    by_class = collections.defaultdict(list)
    for cid, c in chars.items():
        if not c["no_random"]:
            for cl in c["classes"]:
                by_class[cl].append(c)

    # rank names by rating (game_relations' "rating": name, upper bound, name, ...)
    rating = [x.strip() for x in (sv("game_relations", "rating") or "").split(",") if x.strip()]
    names, bounds = rating[0::2], [int(x) for x in rating[1::2]]

    def ranks_of(lo, hi):
        out = []
        for i, n in enumerate(names):
            a = bounds[i - 1] if i > 0 else -10 ** 9
            b = bounds[i] if i < len(bounds) else 10 ** 9
            if hi >= a and lo < b:
                out.append(n)
        return out

    # the visual's third part, as death_manager.get_outfit_by_npc_visual takes it
    def visual_key(v):
        parts = (v or "").strip().split("\\")
        return parts[2].strip() if len(parts) > 2 and parts[2].strip() else None

    used = set()
    for d in S.values():
        for k in ("npc", "npc_random"):
            for x in (d.get(k) or "").split(","):
                if x.strip():
                    used.add(x.strip())
    out = collections.OrderedDict()
    carried = collections.OrderedDict()    # gear -> the name strings of story characters with it
    for sec in sorted(used):
        d = S.get(sec) or {}
        comm, prof = d.get("community"), profiles.get(d.get("character_profile"))
        if not prof:
            continue
        cast = [chars[prof["char"]]] if prof["char"] in chars else by_class.get(prof["cls"], [])
        for c in cast:
            if c["supplies"] and not c["service"] and c["name"]:
                for item in c["supplies"]:
                    if gear(item):
                        lst = carried.setdefault(item, [])
                        if c["name"] not in lst:
                            lst.append(c["name"])
        if comm not in FACTIONS:
            continue
        lines = collections.OrderedDict()
        total = collections.Counter()
        if prof["char"]:
            c = chars.get(prof["char"])
            k = c and visual_key(c["visual"])
            if k:
                total["special"] += 1
                lines.setdefault(k, collections.Counter())["special"] += 1
        else:
            for c in by_class.get(prof["cls"], []):
                lo, hi = c["rank"]
                k = visual_key(c["visual"])
                if lo is None or not k:
                    continue
                for r in ranks_of(lo, hi):
                    total[r] += 1
                    lines.setdefault(k, collections.Counter())[r] += 1
        if total:
            out[sec] = (total, lines)

    # the trade configs NPC logic names ("trade = items\trade\<name>.ltx"), each with the name
    # strings of the traders using it. A logic section's NPC: the spawn sections whose
    # custom_data is its file ([logic]), the one its suitable line names (check_npc_name), the
    # one a smart terrain job is named for ([logic@<npc section>]), or the one the file is
    # named after. A generated name (a nameless NPC) is left out.
    rx = re.compile(r"^\s*trade\s*=\s*items\\trade\\([\w\-]+)\.ltx\s*$", re.I)
    named = re.compile(r"check_npc_name\(([\w\-]+)\)", re.I)
    npcs = [s for s, d in S.items() if d.get("character_profile")]
    by_cd = collections.defaultdict(list)
    for s in npcs:
        by_cd[(S[s].get("custom_data") or "").strip().lower()].append(s)

    def npc_sections(x):
        x = (x or "").lower()
        if not x:
            return []
        for c in (x, x + "_stalker", re.sub(r"_logic$", "", x)):
            if c in S and S[c].get("character_profile"):
                return [c]
        found = [s for s in npcs if x in s.lower() and not s.endswith("_squad")]
        return found if len(found) == 1 else []

    def trader_name(sec):
        prof = (S.get(sec) or {}).get("character_profile")
        p = profiles.get(prof)
        c = chars.get(p["char"]) if p and p["char"] else chars.get(prof)
        n = c and c["name"]
        return n if n and not n.startswith("GENERATE_NAME") else None

    trade = collections.OrderedDict()
    for rel in sorted(vfs.files):
        if not (rel.startswith("configs\\scripts\\") and rel.endswith(".ltx")):
            continue
        text, _ = vfs.read(rel)
        sections, cur = collections.OrderedDict(), None
        for line in (text or "").splitlines():
            line = line.split(";")[0]
            m = re.match(r"^\s*\[([^\]]+)\]", line)
            if m:
                cur = m.group(1).split(":")[0].strip()
                sections.setdefault(cur, [])
            elif cur is not None:
                sections[cur].append(line)
        for sec, body in sections.items():
            cfgs = [m.group(1).lower() for m in (rx.match(x) for x in body) if m]
            if not cfgs:
                continue
            owners = list(by_cd.get(rel[len("configs\\"):].lower(), [])) if sec == "logic" else []
            for x in body:
                if x.strip().lower().startswith("suitable"):
                    for n in named.findall(x):
                        owners += npc_sections(n)
            if not owners and "@" in sec:
                owners = npc_sections(sec.split("@", 1)[1])
            if not owners:
                owners = npc_sections(os.path.splitext(os.path.basename(rel))[0])
            for c in cfgs:
                who = trade.setdefault(c, [])
                for o in owners:
                    n = trader_name(o)
                    if n and n not in who:
                        who.append(n)

    order = names + ["special"]

    def counts(c):
        return ", ".join("%s:%d" % (r, c[r]) for r in order if c[r])

    text = ["; Arsenal: what it needs to know of the Zone's people and traders, from the NPC character",
            "; and logic files, by tools/census.py (%s). See census.py." % datetime.date.today().isoformat(), "",
            "; who offers which dialog: the name strings of the characters that have it",
            "[arsenal_dialogs]"]
    for d, names_of in offers.items():
        text.append("%s = %s" % (d, ", ".join(names_of)))
    text += ["", "; the trade configs some NPC's logic uses: the name strings of the traders using it",
             "[arsenal_trade]"]
    for t in sorted(trade):
        text.append("%s = %s" % (t, ", ".join(trade[t]) or "-"))
    text += ["", "; gear a story character carries, for characters a squad spawns (not traders, technicians,",
             "; medics or barmen, who keep nothing): the characters' name strings", "[arsenal_supplies]"]
    for item in sorted(carried):
        text.append("%s = %s" % (item, ", ".join(carried[item])))
    text.append("")
    for sec, (total, lines) in out.items():
        text.append("[%s]" % sec)
        text.append("characters = %s" % counts(total))
        for k in sorted(lines):
            text.append("%s = %s" % (k, counts(lines[k])))
        text.append("")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="cp1251", newline="\n") as f:
        f.write("\n".join(text))
    print("%d spawn sections, %d characters, %d trade configs, %d carried items -> %s" % (
        len(out), len(chars), len(trade), len(carried), os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
