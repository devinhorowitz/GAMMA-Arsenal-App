"""Run arsenal_intel.script under LuaJIT against stubs of the engine and of arsenal_data, and check
what the player comes to know: his faction's gear from the start, kills and their tallies, PDAs
(their owner's faction or one it is allied with or at war with, up to his rank; encrypted ones
when decrypted; rare ones with specs), bodies, stashes and traders' stock, talks, a technician's
special guns, the news, the jailbreak, saving and regrouping.

    python test_intel.py            the real script
    python test_intel.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_intel.script"), encoding="latin-1").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(HERE, "..", "gamedata", "configs", "text", "eng", "st_arsenal.xml"),
                                  encoding="cp1251").read(), re.S))

STUBS = r"""
local T = ...
for k, v in pairs({ st_faction_dolg = "Duty", st_faction_freedom = "Freedom", st_faction_army = "Military",
    st_faction_ecolog = "Ecologist", st_faction_monolith = "Monolith", st_faction_stalker = "Loner" }) do T[k] = v end
game = { translate_string = function(k) return T[k] or k end,
         get_game_time = function() return { get = function() return 2012, 5, DAY, 10, 30 end } end }
DAY = 14
level = { name = function() return "l02_garbage" end }
AC_ID = 0
CALLBACKS = {}
function RegisterScriptCallback(name, fn) CALLBACKS[name] = fn end
TIMERS = {}
function CreateTimeEvent(a, b, delay, fn) TIMERS[#TIMERS + 1] = fn end
function run_timers() local t = TIMERS; TIMERS = {}; for _, fn in ipairs(t) do fn() end end
NEWS = {}
MONEY = 20000
PAID = {}
db = { actor = {
    id = function() return 0 end,
    character_community = function() return "actor_dolg" end,
    money = function() return MONEY end,
    give_game_news = function(self, title, text) NEWS[#NEWS + 1] = text end,
    iterate_inventory = function(self, fn, obj) for _, it in ipairs(ACTOR_ITEMS) do fn(obj, it) end end,
} }
ACTOR_ITEMS = {}
dialogs = { relocate_money_from_actor = function(a, b, n) MONEY = MONEY - n; PAID[#PAID + 1] = n end }
ranks = { get_obj_rank_name = function(o) return o.rank end }
game_object = { enemy = 3 }
-- Duty is at war with Freedom and Monolith, allied with the Military, neutral to the rest
local WAR = { dolg = { freedom = true, monolith = true }, freedom = { dolg = true }, monolith = { dolg = true } }
local ALLY = { dolg = { army = true }, army = { dolg = true } }
game_relations = {
    is_factions_enemies = function(a, b) return WAR[a] and WAR[a][b] or false end,
    is_factions_friends = function(a, b) return ALLY[a] and ALLY[a][b] or false end,
}
function IsStalker(o) return o and o.stalker == true end
COST = { wpn_special = 30000 }
ini_sys = { r_float_ex = function(self, sec, key) return key == "cost" and COST[sec] or nil end }
death_manager = { get_outfit_by_npc_visual = function(v) return VISUALS[v] end }
VISUALS = { vis_mono = { "mono_suit", "mono_helm" } }
PDA_INFO = {}
function se_load_var(id, name, key) return PDA_INFO[id] end
ui_pda_npc_tab = { unlock_encrypted_pda = function(a, b)
    for _, info in pairs(PDA_INFO) do if info.state == "encrypted" then info.state = "default" end end
end }

-- the catalog: models by section; which turn up; who carries or wears them, by rank; kits
local function model(sec, name, cat) return { sec = sec, name = name, cat = cat, variants = { { sec = sec, name = name } } } end
M = {}
for _, x in ipairs({ { "wpn_duty", "Duty Rifle", "rifles" }, { "duty_suit", "Duty Suit", "medium" },
    { "wpn_duty_rare", "Duty Marksman", "snipers" }, { "wpn_kit", "Kit Pistol", "pistols" },
    { "wpn_free", "Freedom Rifle", "rifles" }, { "wpn_army", "Army Rifle", "rifles" }, { "wpn_eco", "Eco Rifle", "rifles" },
    { "wpn_mono", "Monolith Rifle", "rifles" }, { "wpn_mono2", "Monolith SMG", "smgs" }, { "wpn_mono3", "Monolith MG", "rifles" },
    { "mono_suit", "Monolith Suit", "heavy" }, { "mono_helm", "Monolith Helmet", "helmets" },
    { "wpn_special", "Special Gun", "rifles" }, { "wpn_never", "Never Gun", "rifles" }, { "wpn_trade", "Trade Knife", "melee" },
    { "wpn_box", "Box Gun", "rifles" }, { "ammo_duty", "Duty Round", "ammo" }, { "ammo_free", "Freedom Round", "ammo" } }) do
    M[x[1]] = model(x[1], x[2], x[3])
end
-- a scoped copy of the Monolith rifle counts as it
local COMBO = { wpn_mono_kobra = "wpn_mono" }
local NEVER = { wpn_never = true }
GEAR = {
    dolg = { { e = "wpn_duty", ranks = { novice = 0.5, trainee = 0.5 }, best = 0.5 },
             { e = "duty_suit", ranks = { novice = 0.4 }, best = 0.4, armor = true },
             { e = "wpn_duty_rare", ranks = { legend = 0.05 }, best = 0.05 } },
    freedom = { { e = "wpn_free", ranks = { novice = 0.3 }, best = 0.3 } },
    army = { { e = "wpn_army", ranks = { trainee = 0.3 }, best = 0.3 } },
    ecolog = { { e = "wpn_eco", ranks = { novice = 0.3 }, best = 0.3 } },
    monolith = { { e = "wpn_mono", ranks = { veteran = 0.4 }, best = 0.4 }, { e = "wpn_mono2", ranks = { novice = 0.2 }, best = 0.2 },
                 { e = "wpn_mono3", ranks = { legend = 0.1 }, best = 0.1 }, { e = "mono_suit", ranks = { veteran = 0.5 }, best = 0.5, armor = true } },
}
arsenal_data = {
    FACTIONS = { "stalker", "dolg", "freedom", "csky", "ecolog", "killer", "army", "bandit", "monolith", "zombied",
        "renegade", "greh", "isg" },
    RANKS = { "novice", "trainee", "experienced", "professional", "veteran", "expert", "master", "legend" },
    CATEGORIES = { "pistols", "smgs", "rifles", "snipers", "melee", "medium", "heavy", "helmets", "ammo" },
    ARMOR = { medium = true, heavy = true, helmets = true },
}
function arsenal_data.entry_for(sec) return M[COMBO[sec] or sec] end
function arsenal_data.get(sec) return M[sec] end
function arsenal_data.obtainable(sec) return not NEVER[sec] end
function arsenal_data.list(c)
    local out = {}
    for _, e in pairs(M) do if e.cat == c then out[#out + 1] = e end end
    table.sort(out, function(a, b) return a.sec < b.sec end)
    return out
end
function arsenal_data.faction_gear(f)
    local out = {}
    for _, g in ipairs(GEAR[f] or {}) do out[#out + 1] = { e = M[g.e], ranks = g.ranks, best = g.best, armor = g.armor } end
    return out
end
function arsenal_data.kit_models(f) return f == "dolg" and { M.wpn_kit } or {} end
-- the guns that fire a round
local FIRED = { ammo_duty = { "wpn_duty" }, ammo_free = { "wpn_free" } }
function arsenal_data.fired_by(sec)
    local out = {}
    for _, s in ipairs(FIRED[sec] or {}) do out[#out + 1] = M[s] end
    return out
end
function arsenal_data.special(sec) return sec == "wpn_special" end
FOUND = {}
arsenal_collection = { entry_found = function(e) return FOUND[e.sec] end }
JAIL = false
-- tell is Arsenal's one way to the PDA (arsenal_mcm), on here; test_mcm.py silences it
arsenal_mcm = { jailbreak = function() return JAIL end,
    tell = function(text) db.actor:give_game_news("Arsenal", text) end }

-- a person or a box: what he carries, his faction and rank
function person(id, comm, rank, items, extra)
    local o = { stalker = true, rank = rank, items = items or {} }
    function o:id() return id end
    function o:character_community() return comm end
    function o:character_name() return extra and extra.name or ("npc " .. id) end
    function o:alive() return not (extra and extra.dead) end
    function o:relation(a) return extra and extra.relation or 1 end
    function o:get_visual_name() return extra and extra.visual or "vis_none" end
    function o:iterate_inventory(fn, owner) for _, s in ipairs(self.items) do fn(owner, item(s)) end end
    function o:iterate_inventory_box(fn, owner) for _, s in ipairs(self.items) do fn(owner, item(s)) end end
    return o
end
function item(sec, id)
    return { section = function() return sec end, id = function() return id or 0 end, name = function() return sec end }
end
"""

MUTANTS = {
    "ammo_reveal": ('    if e.cat == "ammo" then\n        add_fact(k, fact)\n        return nil\n    end\n', ""),
    "ammo_fact": ("        add_fact(k, fact)\n        return nil", "        return nil"),
    "ammo_known_gun": ("            if known(g) then return true end", "            if false then return true end"),
    "ammo_studied": ('    if e.cat == "ammo" then return known(e) end\n', ""),
    "obtainable": ("    if not (e and arsenal_data.obtainable(e.sec)) then return nil end", "    if not e then return nil end"),
    "seed_kit": ("        reveal(e, how, { ways = { kit = true } }, true, true)\n", ""),
    "seed_quiet": ("                true, true)\n", "                true, false)\n"),
    "kill_actor": ("    if not (victim and who and who:id() == AC_ID) then return end", "    if not victim then return end"),
    "kill_suit": ("        if e then reveal(e, how, fact(e)) end", "        -- no suit"),
    "tally_step": ("    if t.kills % TALLY == 0 then", "    if false then"),
    "tally_rank": ("                if i <= top and g.ranks[r] and not low then low = r end", "                if g.ranks[r] and not low then low = r end"),
    "study_at": ("    if t.kills >= STUDY then", "    if false then"),
    "pda_once": ("    if not size or st.pdas[id] then return end", "    if not size then return end"),
    "pda_encrypted": ('    if info.state == "encrypted" then return end\n', ""),
    "pda_specs": ("gear_fact(g, f), SPECS[obj:section()] == true)", "gear_fact(g, f), false)"),
    "pda_circle": ("        if x ~= f and gr and ((gr.is_factions_friends and gr.is_factions_friends(f, x))\n"
                   "            or (gr.is_factions_enemies and gr.is_factions_enemies(f, x))) then",
                   "        if x ~= f then"),
    "pda_rank": ("    local top = rank_at(rank) or #arsenal_data.RANKS", "    local top = #arsenal_data.RANKS"),
    "decrypt": ("        scan_pdas()\n        return r", "        return r"),
    "trade_fact": ('learn_items(partner, { kind = "trade", who = who }, function() return { sold = who } end)',
                   'learn_items(partner, { kind = "trade", who = who }, function() return nil end)'),
    "stash_fact": ('function() return { stash = lvl } end', 'function() return nil end'),
    "talk_daily": ("    if not willing(npc) or st.talked[npc:id()] == day() then return false end",
                   "    if not willing(npc) then return false end"),
    "talk_enemy": ("        and not (npc.relation and npc:relation(db.actor) == game_object.enemy)", ""),
    "talk_specs": ("specs = KNOWS_SPECS[rank] == true", "specs = false"),
    "gunsmith_known": ("if not st.known[e.sec] and arsenal_data.special(e.sec) then list[#list + 1] = e end",
                       "if arsenal_data.special(e.sec) then list[#list + 1] = e end"),
    "gunsmith_money": ("    return t ~= nil and db.actor:money() >= t.price", "    return t ~= nil"),
    "gunsmith_full": ("    local ways = { gunsmith = true }", "    local ways = {}"),
    "talks_shared": ("function reset() st, pending, rumors, offers, scheduled = fresh(), {}, {}, {}, false end",
                     "function reset() st, pending, rumors, scheduled = fresh(), {}, {}, false; offers = rumors end"),
    "news_batch": ("        if not groups[key] then", "        if true then"),
    "news_more": ("        if #names > 3 then", "        if false then"),
    "new_flag": ("            st.new[k] = true\n", ""),
    "viewed": ("    st.new[e.sec] = nil", "    -- stays new"),
    "found_live": ("    local e = live and model(sec)", "    local e = model(sec)"),
    "found_not_new": ("    if e and arsenal_data.obtainable(e.sec) then st.new[e.sec] = true end", "    -- not new"),
    "found_never": ("    if e and arsenal_data.obtainable(e.sec) then st.new[e.sec] = true end",
                    "    if e then st.new[e.sec] = true end"),
    "count_listed": ("        if e and not seen[e] and is_new(e) and listed(e) then", "        if e and not seen[e] and is_new(e) then"),
    "count_jail": ("        if e and not seen[e] and is_new(e) and listed(e) then", "        if e and not seen[e] and listed(e) then"),
    "count_once": ("            seen[e] = true\n            n = n + 1", "            n = n + 1"),
    "jail_listed": ("    if jailbroken() then return true end\n    return known(e) and arsenal_data.obtainable(e.sec)",
                    "    return known(e) and arsenal_data.obtainable(e.sec)"),
    "found_known": ("    if st.known[e.sec] ~= nil or (arsenal_collection and arsenal_collection.entry_found(e) ~= nil) then return true end",
                    "    if st.known[e.sec] ~= nil then return true end"),
    "regroup": ("        return e and e.sec or k", "        return k"),
    "load_version": ("    st = (type(d) == \"table\" and d.v == VERSION) and d or fresh()", "    st = (type(d) == \"table\") and d or fresh()"),
}


def main():
    src = SRC
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS, lua.table_from(STRINGS))
    m = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                 "setfenv(f, env); f(); return env end")(src)
    g = lua.globals()
    g.arsenal_intel = m
    m.on_game_start()
    cb = g.CALLBACKS
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    def run(fn):
        try:
            return fn()
        except Exception as err:
            return "error: %s" % str(err)[:90]

    M = g.M
    st = lambda: m.state()
    known = lambda: sorted(k for k in st().known.keys())
    studied = lambda: sorted(k for k, v in st().studied.items() if v)
    new = lambda: sorted(k for k, v in st().new.items() if v)

    def facts(sec, kind):
        f = st().facts[sec]
        t = f and f[kind]
        if not t:
            return {}
        return {k: sorted(v.keys()) if not isinstance(v, bool) and hasattr(v, "keys") else v for k, v in t.items()}

    # the start: a Duty player knows Duty's gear (carried and worn, every rank) and its kit,
    # studied, quietly; once
    cb.load_state(lua.table_from({}))
    run(lambda: cb.actor_on_first_update())
    check(known() == ["duty_suit", "wpn_duty", "wpn_duty_rare", "wpn_kit"],
          "his own faction's gear and kit are known from the start: %s" % known())
    check(studied() == known() and new() == [] and len(g.NEWS) == 0 and len(g.TIMERS) == 0,
          "and studied, quietly: studied %s, new %s, news %d" % (studied(), new(), len(g.NEWS)))
    check(facts("wpn_duty", "carried") == {"dolg": ["novice", "trainee"]} and facts("duty_suit", "worn") == {"dolg": ["novice"]},
          "with who carries and wears them: %s %s" % (facts("wpn_duty", "carried"), facts("duty_suit", "worn")))
    check(st().facts["wpn_kit"].ways.kit is True, "the kit's models: known as kit gear")
    lua.execute('table.insert(GEAR.dolg, { e = "wpn_army", ranks = { trainee = 0.2 }, best = 0.2 })')
    run(lambda: cb.actor_on_first_update())
    check("wpn_army" in known() and "wpn_army" in studied() and new() == [],
          "gear his faction gains is known on the next load, quietly: %s" % known())
    lua.execute("table.remove(GEAR.dolg)")
    st().known["wpn_army"], st().studied["wpn_army"] = None, None

    # a kill: what he had (his visual's suit and helmet too) is known, with his faction and rank,
    # and news of it; others' kills teach nothing; what never turns up is never learned
    mono = g.person(101, "monolith", "veteran", lua.table_from(["wpn_mono_kobra", "wpn_never"]),
                    lua.table_from({"visual": "vis_mono"}))
    run(lambda: cb.npc_on_death_callback(mono, g.person(5, "stalker", "novice")))
    check("wpn_mono" not in known(), "a kill by someone else teaches nothing")
    run(lambda: cb.npc_on_death_callback(mono, g.db.actor))
    check(all(s in known() for s in ("wpn_mono", "mono_suit", "mono_helm")) and "wpn_never" not in known(),
          "a kill: his gun (a scoped copy as its model), suit and helmet; never what never turns up: %s" % known())
    check(facts("wpn_mono", "carried") == {"monolith": ["veteran"]} and facts("mono_suit", "worn") == {"monolith": ["veteran"]},
          "who had it: %s %s" % (facts("wpn_mono", "carried"), facts("mono_suit", "worn")))
    run(lambda: g.run_timers())
    check(len(g.NEWS) == 1 and "a Monolith fighter" in g.NEWS[1] and "Monolith Rifle" in g.NEWS[1],
          "one news line for what one kill taught: %s" % list(g.NEWS.values()))
    check(set(new()) == {"wpn_mono", "mono_suit", "mono_helm"}, "and marked new: %s" % new())

    # the tally: every TALLY kills of a faction bring word of more of its gear, up to the highest
    # rank killed; at STUDY kills its gear is studied
    for _ in range(int(m.TALLY) - 1):
        run(lambda: cb.npc_on_death_callback(g.person(102, "monolith", "veteran", lua.table_from([])), g.db.actor))
    check(st().tally["monolith"].kills == m.TALLY and "wpn_mono2" in known() and "wpn_mono3" not in known(),
          "at %d kills, word of more of their gear, but not above the highest rank killed: %s"
          % (m.TALLY, known()))
    check("wpn_mono" not in studied(), "not studied before %d kills" % m.STUDY)
    for _ in range(int(m.STUDY) - int(m.TALLY)):
        run(lambda: cb.npc_on_death_callback(g.person(103, "monolith", "novice", lua.table_from([])), g.db.actor))
    check("wpn_mono" in studied() and "mono_suit" in studied() and "wpn_free" not in studied(),
          "at %d kills, the gear known of them is studied: %s" % (m.STUDY, studied()))

    # PDAs: their owner's word on his faction's gear or that of one it is allied or at war with
    # (Duty: Military, Freedom, Monolith; never the Ecologists), up to his rank; a package's size
    # by the PDA; once; an encrypted one when decrypted; a rare one with specs
    m.reset()
    g.math.randomseed(7)
    seen_f, ranks_ok = set(), True
    for i in range(40):
        m.reset()
        g.PDA_INFO[200 + i] = lua.table_from({"state": "default",
                                              "contact": lua.table_from({"comm": "dolg", "rank": "trainee"})})
        run(lambda: cb.actor_on_item_take(g.item("itm_pda_uncommon", 200 + i)))
        for k in known():
            for kind in ("carried", "worn"):
                for f, rs in facts(k, kind).items():
                    seen_f.add(f)
                    if any(r in ("legend", "veteran") for r in rs):
                        ranks_ok = False
    check(seen_f <= {"dolg", "army", "freedom", "monolith"} and "dolg" in seen_f and len(seen_f) >= 3,
          "a Duty PDA tells of Duty and its allies and enemies, never a neutral faction: %s" % sorted(seen_f))
    check(ranks_ok, "nothing above its owner's rank")
    m.reset()
    g.PDA_INFO[300] = lua.table_from({"state": "default", "contact": lua.table_from({"comm": "dolg", "rank": "legend"})})
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_uncommon", 300)))
    n1 = len(known())
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_uncommon", 300)))
    check(n1 == 2 and len(known()) == 2, "an uncommon PDA: two entries, once: %d then %d" % (n1, len(known())))
    m.reset()
    g.PDA_INFO[301] = lua.table_from({"state": "encrypted", "contact": lua.table_from({"comm": "dolg", "rank": "legend"})})
    g.ACTOR_ITEMS = lua.table_from([g.item("itm_pda_rare", 301)])
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_rare", 301)))
    locked = len(known())
    run(lambda: g.ui_pda_npc_tab.unlock_encrypted_pda(g.db.actor, g.person(9, "stalker", "novice")))
    check(locked == 0 and len(known()) == 3 and studied() == known(),
          "an encrypted PDA: nothing until a technician decrypts it; a rare one: three, with specs: %d %s %s"
          % (locked, known(), studied()))
    g.ACTOR_ITEMS = lua.table_from([])

    # windows: a trader's stock (who sells it), a stash (where), a body (who carried it)
    m.reset()
    gui = lua.table_from({"mode": "trade", "npc_is_box": False})
    trader = g.person(400, "stalker", "novice", lua.table_from(["wpn_trade"]), lua.table_from({"name": "Sidorovich"}))
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(trader)
    g.ui_inventory = lua.table_from({"GUI": gui})
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_trade", "sold") == {"Sidorovich": True}, "a trader's stock: sold by him: %s" % facts("wpn_trade", "sold"))
    gui.mode, gui.npc_is_box = "loot", True
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(g.person(401, "x", "novice", lua.table_from(["wpn_box"])))
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_box", "stash") == {"l02_garbage": True}, "a stash: where it lay: %s" % facts("wpn_box", "stash"))
    gui.npc_is_box = False
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(g.person(402, "freedom", "novice", lua.table_from(["wpn_free"])))
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_free", "carried") == {"freedom": ["novice"]}, "a body: who carried it: %s" % facts("wpn_free", "carried"))

    # talks: one thing a day per person; an expert's with specs; an enemy will not talk
    m.reset()
    g.math.randomseed(3)
    vet = g.person(500, "dolg", "veteran")
    ok1 = run(lambda: m.rumor_ok(g.db.actor, vet))
    text = run(lambda: m.rumor_text(g.db.actor, vet))
    run(lambda: m.rumor_told(g.db.actor, vet))
    check(ok1 is True and isinstance(text, str) and len(known()) == 1 and studied() == [],
          "a talk: one thing, no specs from a veteran: %s %s %s" % (ok1, text, known()))
    check(run(lambda: m.rumor_ok(g.db.actor, vet)) is False, "once a day")
    g.DAY = 15
    check(run(lambda: m.rumor_ok(g.db.actor, vet)) is True, "and again the next day")
    leg = g.person(501, "dolg", "legend")
    run(lambda: m.rumor_ok(g.db.actor, leg))
    run(lambda: m.rumor_told(g.db.actor, leg))
    check(len(studied()) == 1, "a legend's word comes with specs: %s" % studied())
    foe = g.person(502, "dolg", "legend", None, lua.table_from({"relation": 3}))
    check(run(lambda: m.rumor_ok(g.db.actor, foe)) is False, "an enemy does not talk")

    # a technician: word of a special gun not yet known, for money; with specs and how to get it
    m.reset()
    smith = g.person(600, "stalker", "expert", None, lua.table_from({"name": "Cardan"}))
    ok2 = run(lambda: m.gunsmith_ok(g.db.actor, smith))
    offer = run(lambda: m.gunsmith_offer(g.db.actor, smith))
    g.MONEY = 100
    poor = run(lambda: m.gunsmith_can_pay(g.db.actor, smith))
    g.MONEY = 20000
    run(lambda: m.gunsmith_pay(g.db.actor, smith))
    check(ok2 is True and "3000" in str(offer) and poor is False and list(g.PAID.values()) == [3000]
          and known() == ["wpn_special"] and studied() == ["wpn_special"]
          and st().facts["wpn_special"].ways.gunsmith is True,
          "a technician sells word of a special gun (a tenth of its price), studied, with how to get it: %s %s %s"
          % (ok2, offer, known()))
    check(run(lambda: m.gunsmith_ok(g.db.actor, g.person(601, "stalker", "expert"))) is False,
          "nothing more to sell once it is known")

    # A trader or technician has both talks, and the game checks both before the player picks
    # one, rumor first: either then works, in either order (a shared slot once lost the rumor's
    # faction, and asking crashed the game: "attempt to concatenate local 'f' (a nil value)")
    m.reset()
    g.math.randomseed(5)
    trader = g.person(610, "dolg", "veteran", None, lua.table_from({"name": "Mangun"}))
    both = (run(lambda: m.rumor_ok(g.db.actor, trader)), run(lambda: m.gunsmith_ok(g.db.actor, trader)))
    said = run(lambda: m.rumor_text(g.db.actor, trader))
    run(lambda: m.rumor_told(g.db.actor, trader))
    told = known()
    g.MONEY = 100
    poor = run(lambda: m.gunsmith_can_pay(g.db.actor, trader))
    offer = run(lambda: m.gunsmith_offer(g.db.actor, trader))
    named = lambda s: isinstance(s, str) and not s.startswith("error") and any(
        f in s for f in ("Duty", "Freedom", "Military", "Ecologist", "Monolith", "Loner"))
    check(both == (True, True) and named(said) and len(told) == 1 and poor is False and "3000" in str(offer),
          "a trader's two talks keep apart, the rumor checked first: %s %r %s %r %r" % (both, said, told, poor, offer))
    m.reset()
    both = (run(lambda: m.gunsmith_ok(g.db.actor, trader)), run(lambda: m.rumor_ok(g.db.actor, trader)))
    g.MONEY = 20000
    rich = run(lambda: m.gunsmith_can_pay(g.db.actor, trader))
    said = run(lambda: m.rumor_text(g.db.actor, trader))
    check(both == (True, True) and rich is True and named(said),
          "and the offer checked first: %s %r %r" % (both, rich, said))

    # news: one line per source, three names then how many more; seen pages no longer new
    m.reset()
    g.NEWS = lua.table_from({})
    big = g.person(700, "monolith", "legend", lua.table_from(["wpn_mono", "wpn_mono2", "wpn_mono3", "mono_suit"]))
    run(lambda: cb.npc_on_death_callback(big, g.db.actor))
    run(lambda: g.run_timers())
    check(len(g.NEWS) == 1 and "and 1 more" in g.NEWS[1], "three names, then how many more: %s" % list(g.NEWS.values()))
    run(lambda: m.viewed(M.wpn_mono))
    check("wpn_mono" not in new() and "wpn_mono2" in new(), "a page seen is no longer new")

    # finds: carried when a save loads, known but not new; found in play, new until read, though
    # known already (a variant found the first time); never what never turns up
    m.reset()
    run(lambda: m.found("wpn_eco", False))
    check("wpn_eco" in known() and "wpn_eco" not in new(), "carried when a save loads: known, not new: %s" % new())
    run(lambda: m.found("wpn_eco", True))
    run(lambda: m.found("wpn_mono_kobra", True))
    run(lambda: m.found("wpn_never", True))
    check(new() == ["wpn_eco", "wpn_mono"], "found in play: new, by its model, known before or not: %s" % new())
    # the count: listed models only, each once
    st().new["wpn_free"] = True
    st().new["wpn_mono_kobra"] = True
    check(run(lambda: m.count_new()) == 2, "two new: %s" % run(lambda: m.count_new()))
    g.JAIL = True
    check(run(lambda: m.count_new()) == 0, "none with the jailbreak")
    g.JAIL = False
    run(lambda: m.viewed(M.wpn_eco))
    check(run(lambda: m.count_new()) == 1, "one read, one left")

    # listed and studied: with the jailbreak, everything; a found model is known and studied
    m.reset()
    check(not m.listed(M.wpn_eco) and not m.studied(M.wpn_eco), "unknown: not listed")
    g.FOUND["wpn_eco"] = lua.table_from({})
    check(m.listed(M.wpn_eco) and m.studied(M.wpn_eco), "found: listed and studied")
    g.FOUND["wpn_eco"] = None
    g.JAIL = True
    check(m.listed(M.wpn_eco) and m.studied(M.wpn_eco) and m.listed(M.wpn_never) and not m.is_new(M.wpn_mono),
          "with the jailbreak, everything")
    g.JAIL = False
    check(not m.listed(M.wpn_never), "never what never turns up")

    # rounds: known, their values shown, once a gun that fires them is known or one is found;
    # where they lie is a fact, without news; never known on their own
    m.reset()
    run(lambda: cb.actor_on_first_update())
    check(m.known(M.ammo_duty) and m.studied(M.ammo_duty) and m.listed(M.ammo_duty),
          "a round a known gun fires: known, listed, its values shown")
    check(not m.known(M.ammo_free) and not m.studied(M.ammo_free), "a round no known gun fires: unknown")
    g.NEWS = lua.table_from({})
    got = run(lambda: m.reveal("ammo_free", lua.table_from({"kind": "trade", "who": "Owl"}),
                               lua.table_from({"sold": "Owl"})))
    run(lambda: g.run_timers())
    check(got is None and len(g.NEWS) == 0 and "ammo_free" not in known() and not m.known(M.ammo_free)
          and facts("ammo_free", "sold") == {"Owl": True},
          "a round in a trader's stock: a fact, no news, not known by itself: %s %s %s"
          % (got, list(g.NEWS.values()), facts("ammo_free", "sold")))
    run(lambda: m.found("ammo_free", True))
    g.FOUND["ammo_free"] = lua.table_from({})
    check(m.known(M.ammo_free) and "ammo_free" in new() and run(lambda: m.count_new()) == 1,
          "a round found in play: known and new: %s" % new())
    g.FOUND["ammo_free"] = None
    st().new["ammo_free"] = None
    free = g.person(810, "freedom", "novice", lua.table_from(["wpn_free"]))
    run(lambda: cb.npc_on_death_callback(free, g.db.actor))
    check(m.known(M.ammo_free), "known once a gun that fires it is")

    # saving: what is kept comes back; another version starts fresh; keys move to their model
    m.reset()
    run(lambda: m.reveal("wpn_mono_kobra", lua.table_from({"kind": "kill"}), None, True, True))
    data = lua.table_from({})
    cb.save_state(data)
    m.reset()
    cb.load_state(data)
    check(known() == ["wpn_mono"], "saved and loaded: %s" % known())
    cb.load_state(lua.table_from({"arsenal_intel": lua.table_from({"v": 99, "known": lua.table_from({"wpn_free": True})})}))
    check(known() == [], "a save of another version starts fresh: %s" % known())
    st().known["wpn_mono_kobra"] = lua.table_from({})
    m.regroup()
    check(known() == ["wpn_mono"], "a key under another section moves to its model: %s" % known())

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
