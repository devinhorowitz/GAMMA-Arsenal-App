"""Run arsenal_intel.script under LuaJIT against stubs of the engine and of arsenal_data, and check
what the player comes to know: his faction's gear from the start, kills and their tallies, PDAs
(their owner's faction or one it is allied with or at war with, up to his rank; encrypted ones
when decrypted; rare ones with specs), bodies, stashes and traders' stock as their windows show
them (a trader's as the window lists it, a stash looked into again as it fills, never a box of
the player's own, a companion's pack), talks, a technician's special guns (and the MCM option that
turns that talk off), the news, the jailbreak, saving and regrouping (keys that are one model now,
together).

    python test_intel.py            the real script
    python test_intel.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_intel.script"), encoding="latin-1").read()
WHERE = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_where.script"), encoding="latin-1").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(HERE, "..", "gamedata", "configs", "text", "eng", "st_arsenal.xml"),
                                  encoding="cp1251").read(), re.S))

STUBS = r"""
local T = ...
for k, v in pairs({ st_faction_dolg = "Duty", st_faction_freedom = "Freedom", st_faction_army = "Military",
    st_faction_ecolog = "Ecologist", st_faction_monolith = "Monolith", st_faction_stalker = "Loner",
    l01_escape = "Cordon", l02_garbage = "Garbage" }) do T[k] = v end
game = { translate_string = function(k) return T[k] or k end,
         get_game_time = function() return { get = function() return 2012, 5, DAY, 10, 30 end } end }
DAY = 14
level = { name = function() return "l02_garbage" end, object_by_id = function(id) return OBJS[id] end }
OBJS = {}
-- where things are (arsenal_where): vertex 10 on Cordon, 20 (everyone's, unless told) on the Garbage
local LEVEL_OF, LEVELS = { [10] = 1, [20] = 2 }, { "l01_escape", "l02_garbage" }
function game_graph() return { valid_vertex_id = function(self, gv) return LEVEL_OF[gv] ~= nil end,
    vertex = function(self, gv) local l = LEVEL_OF[gv]; return { level_id = function() return l end } end } end
function alife() return { level_name = function(self, id) return LEVELS[id] end } end
function vector() return { set = function(self, x, y, z) return { x = x, y = y, z = z } end } end
dynamic_news_helper = { GetPointDescription = function(obj)
    return ({ [10] = "in Cordon, near the rookie village", [20] = "in Garbage, at the Depot" })[obj.m_game_vertex_id]
end }
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
    give_money = function(self, n) MONEY = math.max(0, MONEY + n) end,
    give_game_news = function(self, title, text) NEWS[#NEWS + 1] = text end,
    iterate_inventory = function(self, fn, obj) for _, it in ipairs(ACTOR_ITEMS) do fn(obj, it) end end,
} }
ACTOR_ITEMS = {}
-- the money news (news_manager), and the base game's payment (dialogs.script) over the engine's
-- transfer_money, which hands the one paid the payer's change in money, a negative sum
-- (xray-monolith's TransferMoney)
news_manager = { relocate_money = function(actor, kind, n) PAID[#PAID + 1] = n end }
dialogs = { relocate_money_from_actor = function(a, b, n)
    local npc = a == db.actor and b or a
    local before = MONEY
    db.actor:give_money(-n)
    npc:give_money(MONEY - before)
    news_manager.relocate_money(db.actor, "out", n)
end }
LOG = {}
function printf(fmt, ...)
    local args, i = { ... }, 0
    LOG[#LOG + 1] = (fmt:gsub("%%s", function() i = i + 1; return tostring(args[i]) end))
end
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
-- se vars by id, as alife_storage_manager keeps them ("info" is the PDA's own, ui_pda_npc_tab's);
-- the game releasing an object drops them (axr_main), and a new object may get its id
SE = {}
function se_load_var(id, name, key)
    if key == "info" then return PDA_INFO[id] end
    return SE[id] and SE[id][key]
end
function se_save_var(id, name, key, val)
    SE[id] = SE[id] or {}
    SE[id][key] = val
end
function release(id) SE[id] = nil; PDA_INFO[id] = nil end
ALIFE = {}
function alife_object(id) return ALIFE[id] end
function se_thing(sec, id) return { section_name = function() return sec end, name = function() return sec .. id end } end
-- a fighter's logic (db.storage): dont_keep_items for the ids listed (traders, technicians, medics)
KEEPS_NOTHING = {}
db.storage = setmetatable({}, { __index = function(t, id)
    if not KEEPS_NOTHING[id] then return nil end
    return { section_logic = "logic@trader", ini = { line_exist = function(self, sec, key)
        return sec == "logic@trader" and key == "dont_keep_items" end } }
end })
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
    { "wpn_box", "Box Gun", "rifles" }, { "ammo_duty", "Duty Round", "ammo" }, { "ammo_free", "Freedom Round", "ammo" },
    { "kobra", "Kobra", "scopes" } }) do
    M[x[1]] = model(x[1], x[2], x[3])
end
-- a scoped copy of the Monolith rifle counts as it, and has the Kobra on (arsenal_data.mounted_addons);
-- a gun whose attachments cannot be read
local COMBO = { wpn_mono_kobra = "wpn_mono" }
local ON = { wpn_mono_kobra = { "kobra" } }
function arsenal_data_mounted(obj)
    if obj:section() == "wpn_box" then error("cannot read it") end
    return ON[obj:section()] or {}
end
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
arsenal_data.mounted_addons = arsenal_data_mounted
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
-- MCM > Arsenal > Paid word of special guns, on unless a test turns it off
GUNSMITH = true
-- tell is Arsenal's one way to the PDA (arsenal_mcm), on here; test_mcm.py silences it
arsenal_mcm = { jailbreak = function() return JAIL end, gunsmith = function() return GUNSMITH end,
    tell = function(text) db.actor:give_game_news("Arsenal", text) end }

-- a person or a box: what he carries, his faction and rank
function person(id, comm, rank, items, extra)
    local o = { stalker = true, rank = rank, items = items or {}, purse = extra and extra.purse or 0 }
    function o:money() return self.purse end
    function o:give_money(n) self.purse = math.max(0, self.purse + n) end
    function o:id() return id end
    function o:character_community() return comm end
    function o:character_name() return extra and extra.name or ("npc " .. id) end
    function o:alive() return not (extra and extra.dead) end
    function o:relation(a) return extra and extra.relation or 1 end
    function o:get_visual_name() return extra and extra.visual or "vis_none" end
    function o:best_weapon() return extra and extra.weapon and item(extra.weapon) or nil end
    function o:game_vertex_id() return extra and extra.gv or 20 end
    function o:position() return { x = id, y = 0, z = 0 } end
    function o:iterate_inventory(fn, owner) for _, s in ipairs(self.items) do fn(owner, item(s)) end end
    function o:iterate_inventory_box(fn, owner) for _, s in ipairs(self.items) do fn(owner, item(s)) end end
    -- his ruck: what is not in his slots (extra.ruck), else all he has
    function o:iterate_ruck(fn, owner) for _, s in ipairs(extra and extra.ruck or self.items) do fn(owner, item(s)) end end
    function o:name() return "npc" .. id end
    function o:spawn_ini() return extra and extra.spawn_ini or nil end
    return o
end
-- an item: its section, its id, and whose hands it is in (parent), if anyone's
function item(sec, id, holder)
    return { section = function() return sec end, id = function() return id or 0 end, name = function() return sec end,
             parent = function() return holder end }
end
-- a spawn ini with the sections given
function spawn_ini(...)
    local has = {}
    for _, s in ipairs({ ... }) do has[s] = true end
    return { section_exist = function(self, s) return has[s] == true end }
end
-- the inventory window's own cells (ui_inventory's CC), by bag: the ids it shows, each an item
-- in the world (level.object_by_id)
function cells(bags)
    local cc = {}
    for bag, list in pairs(bags) do
        local ids = {}
        for _, x in ipairs(list) do
            OBJS[x[1]] = item(x[2], x[1])
            ids[x[1]] = 1
        end
        cc[bag] = { indx_id = ids }
    end
    return cc
end
-- whether the inventory window is open (ui_inventory.GUI:IsShown)
SHOWN = false
"""

MUTANTS = {
    # what is on a gun, learned with it
    "mounted_none": ("local ok, on = pcall(arsenal_data.mounted_addons, item)", "local ok, on = false, nil"),
    "mounted_pcall": ("local ok, on = pcall(arsenal_data.mounted_addons, item)",
                      "local ok, on = true, arsenal_data.mounted_addons(item)"),
    "ammo_reveal": ('    if e.cat == "ammo" then\n        add_fact(k, fact)\n        return nil\n    end\n', ""),
    "ammo_fact": ("        add_fact(k, fact)\n        return nil", "        return nil"),
    "ammo_known_gun": ("            if known(g) then return true end", "            if false then return true end"),
    "ammo_studied": ('    if e.cat == "ammo" then return known(e) end\n', ""),
    "obtainable": ("    if not (e and arsenal_data.obtainable(e.sec)) then return nil end", "    if not e then return nil end"),
    "seed_kit": ("        reveal(e, how, { ways = { kit = true } }, true, true)\n", ""),
    "seed_disguise": ('    if ok and type(f) == "string" and f ~= "" then return (f:gsub("^actor_", "")) end\n', ""),
    "seed_quiet": ("                true, true)\n", "                true, false)\n"),
    "kill_actor": ("    if not (victim and by_player(who)) then return end", "    if not victim then return end"),
    "silent_kill_missed": ("    return holder ~= nil and holder:id() == AC_ID", "    return false"),
    "silent_kill_any_holder": ("    return holder ~= nil and holder:id() == AC_ID", "    return holder ~= nil"),
    "kill_suit": ("        if e then reveal(e, how, fact(e)) end", "        -- no suit"),
    "tally_step": ("    if t.kills % TALLY == 0 then", "    if false then"),
    "tally_rank": ("                if i <= top and g.ranks[r] and not low then low = r end", "                if g.ranks[r] and not low then low = r end"),
    "study_at": ("    if t.kills >= STUDY then", "    if false then"),
    "pda_once": ("    if mark == who or mark == true then return end", "    if false then return end"),
    "pda_mark_any_owner": ("    if mark == who or mark == true then return end", "    if mark then return end"),
    "pda_test_build_marks": ("    if mark == who or mark == true then return end", "    if mark == who then return end"),
    "owner_constant": ('    return table.concat({ tostring(c.name), tostring(c.comm), tostring(c.rank), tostring(c.icon) }, "|")',
                       '    return "x"'),
    "marks_moved_plain": ('            se_save_var(id, se:name(), READ, owner_of(se_load_var(id, se:name(), "info")))',
                          "            se_save_var(id, se:name(), READ, true)"),
    "marks_not_moved": ("    move_marks()\n", ""),
    "marks_moved_late": ("    move_marks()\n    seed(actor_faction())\n    scan_pdas()\n", "    seed(actor_faction())\n    scan_pdas()\n    move_marks()\n"),
    "marks_any_object": ("        if se and PDA_SIZE[se:section_name()] then\n", "        if se then\n"),
    "marks_lists_kept": ("    st.pdas, st.talked = nil, nil\n", ""),
    "talk_mark_unsaved": ("    se_save_var(npc:id(), npc:name(), TALKED, day())\n", ""),
    "kill_keeps_all": ("    if not keeps_nothing(victim) then learn_items(victim, how, fact) end", "    learn_items(victim, how, fact)"),
    "kill_logic_unread": ("    local s = db.storage and db.storage[npc:id()]\n", "    local s = nil\n"),
    "kill_spawn_ini_unread": ('    if ok and ini and ini:section_exist("dont_keep_items") then return true end\n', ""),
    "pda_encrypted": ('    if info.state == "encrypted" then return end\n', ""),
    "pda_specs": ("gear_fact(g, f), SPECS[obj:section()] == true)", "gear_fact(g, f), false)"),
    "pda_circle": ("        if x ~= f and gr and ((gr.is_factions_friends and gr.is_factions_friends(f, x))\n"
                   "            or (gr.is_factions_enemies and gr.is_factions_enemies(f, x))) then",
                   "        if x ~= f then"),
    "pda_rank": ("    local top = rank_at(rank) or #arsenal_data.RANKS", "    local top = #arsenal_data.RANKS"),
    "decrypt": ("        scan_pdas()\n        return r", "        return r"),
    "trade_fact": ('function() return { sold = who } end, stock)', 'function() return nil end, stock)'),
    "stash_fact": ('function() return { stash = lvl } end', 'function() return nil end'),
    # a window teaches what it shows: a trader's stock as it lists it, his ruck without it
    "trade_all": ('function() return { sold = who } end, stock)', 'function() return { sold = who } end)'),
    "cells_unread": ("        if #lists == 0 then\n            partner:iterate_ruck(fn, partner)",
                     "        if true then\n            partner:iterate_ruck(fn, partner)"),
    "ruck_all": ("            partner:iterate_ruck(fn, partner)", "            partner:iterate_inventory(fn, partner)"),
    # a stash looked into again a moment after it opens, while its window is still open on it
    "stash_once": ("            look_again(partner:id(), place)\n", ""),
    "stash_again_closed": ("        if gui and gui.npc_is_box and gui:IsShown() then ok, box = pcall(gui.GetPartner, gui) end",
                           "        if gui then ok, box = pcall(gui.GetPartner, gui) end"),
    "stash_again_other": ("        if ok and box and box:id() == id then learn_stash(box, place) end",
                          "        if ok and box then learn_stash(box, place) end"),
    # the player's own boxes
    "own_stash": ("        if zone_stash(partner) then\n", "        if true then\n"),
    "own_stash_list": ("    if type(caches) == \"table\" then return caches[id] ~= nil end", "    if type(caches) == \"table\" then return true end"),
    "own_backpack": ("    if type(m.player_created_stashes) == \"table\" and m.player_created_stashes[id] ~= nil then return false end\n",
                     ""),
    "own_workbench": ("        if sid == id then return false end\n", ""),
    # a live companion's pack
    "pack_as_body": ("    elseif IsStalker(partner) and living(gui, partner) then", "    elseif false then"),
    "pack_unshown": ('learn_items(partner, { kind = "pack", who = who, place = place }, nil, shown_of(gui, partner, { "npc_bag" }))',
                     'learn_items(partner, { kind = "pack", who = who, place = place }, nil)'),
    "pack_fact": ('learn_items(partner, { kind = "pack", who = who, place = place }, nil,',
                  'learn_items(partner, { kind = "pack", who = who, place = place }, function() return { carried = '
                  '{ faction = "stalker" } } end,'),
    "pack_words": ('    elseif k == "talk" or k == "gunsmith" or k == "trade" or k == "pack" then',
                   '    elseif k == "talk" or k == "gunsmith" or k == "trade" then'),
    "pack_alive_only_companions": ("    return gui.npc_is_companion == true or (partner.alive ~= nil and partner:alive() == true)",
                                   "    return gui.npc_is_companion == true"),
    # keys that are one model now
    "regroup_first_known": ("                if sooner(type(v) == \"table\" and v.at, type(was) == \"table\" and was.at) then "
                            "out[nk] = v end\n", ""),
    "regroup_facts_dropped": ("                merge_facts(was, v)\n", ""),
    "regroup_facts_shallow": ("            merge_facts(into[kind], v)", "            into[kind] = into[kind]"),
    "talk_daily": ("    if not willing(npc) or se_load_var(npc:id(), npc:name(), TALKED) == day() then return false end",
                   "    if not willing(npc) then return false end"),
    "talk_enemy": ("        and not (npc.relation and npc:relation(db.actor) == game_object.enemy)", ""),
    "talk_specs": ("specs = KNOWS_SPECS[rank] == true", "specs = false"),
    "gunsmith_known": ("if not st.known[e.sec] and arsenal_data.special(e.sec) then list[#list + 1] = e end",
                       "if arsenal_data.special(e.sec) then list[#list + 1] = e end"),
    "gunsmith_money": ("    return t ~= nil and db.actor:money() >= t.price", "    return t ~= nil"),
    "pay_by_transfer": ("    pay(npc, t.price)", "    dialogs.relocate_money_from_actor(a, b, t.price)"),
    "pay_npc_unpaid": ("    npc:give_money(price)\n", ""),
    "pay_no_news": ('    news_manager.relocate_money(db.actor, "out", price)\n', ""),
    "gunsmith_full": ("    local ways = { gunsmith = true }", "    local ways = {}"),
    # MCM > Arsenal > Paid word of special guns
    "gunsmith_option_ignored": ("    if not willing(npc) or not sells_word() then return false end",
                                "    if not willing(npc) then return false end"),
    "gunsmith_option_hides_rumor": ("    if not willing(npc) or se_load_var(npc:id(), npc:name(), TALKED) == day() then return false end",
                                    "    if not willing(npc) or arsenal_mcm.gunsmith() == false"
                                    " or se_load_var(npc:id(), npc:name(), TALKED) == day() then return false end"),
    "gunsmith_option_needs_mcm": ("    return not (arsenal_mcm and arsenal_mcm.gunsmith and arsenal_mcm.gunsmith() == false)",
                                  "    return arsenal_mcm.gunsmith() == true"),
    "talks_shared": ("function reset() st, pending, rumors, offers, scheduled = fresh(), {}, {}, {}, false end",
                     "function reset() st, pending, rumors, scheduled = fresh(), {}, {}, false; offers = rumors end"),
    "news_batch": ("        if not groups[key] then", "        if true then"),
    "news_more": ("        if #names > 3 then", "        if false then"),
    "new_flag": ("            st.new[k] = true\n", ""),
    "viewed": ("    st.new[e.sec] = nil", "    -- stays new"),
    "mark_all_read_noop": ("        st.new[k] = nil\n", ""),
    "api_words": ('        return how.who or game.translate_string("st_arsenal_by_someone")\n',
                  '        return game.translate_string("st_arsenal_by_someone")\n'),
    "api_unknown": ('    elseif k == "api" then', '    elseif k == "api_" then'),
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
    "foreign_read": ('    if type(d) == "table" and d.v ~= VERSION then', "    if false then"),
    "foreign_overwritten": ("        m_data.arsenal_intel, m_data[OWN] = kept, st", "        m_data.arsenal_intel, m_data[OWN] = st, st"),
    "own_unsaved": ("        m_data.arsenal_intel, m_data[OWN] = kept, st", "        m_data.arsenal_intel = kept"),
    "own_unread": ("        kept, d = d, m_data[OWN]", "        kept, d = d, nil"),
    "foreign_unlogged": ('        printf("[arsenal] this save\'s records are another Arsenal\'s (data version %s): kept as they are",\n'
                         "            tostring(d.v))\n", ""),
    "tag_hook": ('    RegisterScriptCallback("actor_on_update", on_identify)\n', ""),
    "tag_once": ("    if id == ii.last then return end\n", ""),
    "tag_stale": ("    ii.last = ii.get_id()\n", "    ii.last = nil\n"),
    "tag_line": ("    local npc = tag and level.object_by_id(id)", "    local npc = tag and tag.weap and level.object_by_id(id)"),
    "tag_alive": ("    if not (npc and IsStalker(npc) and npc:alive()) then return end",
                  "    if not (npc and IsStalker(npc)) then return end"),
    "tag_faction": ("    if not is_faction(f) then return end\n    local ok, wpn", "    local ok, wpn"),
    "tag_fact": ("    reveal(e, how, { carried = { faction = f, rank = r } })", "    reveal(e, how)"),
    "tag_news": ('    if k == "kill" or k == "body" or k == "tag" then', '    if k == "kill" or k == "body" then'),
    "kill_who": ("who = victim:character_name(),", "who = nil,"),
    "kill_place": ("        place = arsenal_where.place_of(victim) }", "        place = nil }"),
    "window_place": ("    local place = arsenal_where.place_of(partner)", "    local place = nil"),
    "body_who": ("who = partner:character_name(), place = place }", "place = place }"),
    "pda_who": ('{ kind = "pda", faction = c.comm, who = c.name }', '{ kind = "pda", faction = c.comm }'),
    "pda_place": ('        return string.format(game.translate_string("st_arsenal_from_pda"), arsenal_where.who_text(how))',
                  '        s = string.format(game.translate_string("st_arsenal_from_pda"), arsenal_where.who_text(how))'),
    "tag_who": ("who = tag.name,", "who = nil,"),
    "talk_place": ('{ kind = "talk", who = npc:character_name(), place = arsenal_where.place_of(npc) }',
                   '{ kind = "talk", who = npc:character_name() }'),
    "describe_at": ("    return at and arsenal_where.at_place(s, how.place, at.lvl) or s", "    return s"),
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
    g.arsenal_where = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                               "setfenv(f, env); f(); return env end")(WHERE)
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
    kit = st().facts["wpn_kit"]
    check(kit is not None and kit.ways is not None and kit.ways.kit is True, "the kit's models: known as kit gear")
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
    check(all(s in known() for s in ("wpn_mono", "mono_suit", "mono_helm", "kobra")) and "wpn_never" not in known(),
          "a kill: his gun (a scoped copy as its model) and the scope on it, suit and helmet; never what never "
          "turns up: %s" % known())
    check(facts("wpn_mono", "carried") == {"monolith": ["veteran"]} and facts("mono_suit", "worn") == {"monolith": ["veteran"]}
          and facts("kobra", "carried") == {"monolith": ["veteran"]},
          "who had it: %s %s %s" % (facts("wpn_mono", "carried"), facts("mono_suit", "worn"), facts("kobra", "carried")))
    run(lambda: g.run_timers())
    check(len(g.NEWS) == 1 and "Learned from killing Monolith fighter npc 101: " in g.NEWS[1] and "Monolith Rifle" in g.NEWS[1]
          and "Kobra" in g.NEWS[1],
          "one news line for what one kill taught, naming him: %s" % list(g.NEWS.values()))
    rec = st().known["wpn_mono"]
    page = run(lambda: m.describe(rec.how, rec.at))
    check(page == "killing Monolith fighter npc 101 in Garbage, at the Depot",
          "and on its page, where he fell: %s" % page)
    old = run(lambda: m.describe(lua.table_from({"kind": "kill", "faction": "dolg"}), lua.table_from({"lvl": "l01_escape"})))
    check(old == "killing a Duty fighter in Cordon", "a kill kept before names and places: %s" % old)
    check(set(new()) == {"wpn_mono", "mono_suit", "mono_helm", "kobra"}, "and marked new: %s" % new())

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

    # a trader, technician or medic (dont_keep_items, in his logic or his spawn ini): death_manager
    # releases all he had as he dies, before the kill is heard of; that stock is not what his
    # faction carries and never reaches the body. His visual's suit does, and the kill counts.
    m.reset()
    g.KEEPS_NOTHING[450] = True
    by_logic = g.person(450, "freedom", "veteran", lua.table_from(["wpn_free", "wpn_eco"]), lua.table_from({"visual": "vis_mono"}))
    by_ini = g.person(451, "freedom", "veteran", lua.table_from(["wpn_box"]),
                      lua.table_from({"spawn_ini": g.spawn_ini("dont_keep_items")}))
    fighter = g.person(452, "freedom", "veteran", lua.table_from(["wpn_army"]), lua.table_from({"spawn_ini": g.spawn_ini("logic")}))
    for v in (by_logic, by_ini, fighter):
        run(lambda: cb.npc_on_death_callback(v, g.db.actor))
    tally = st().tally["freedom"]
    check(not any(s in known() for s in ("wpn_free", "wpn_eco", "wpn_box")) and "mono_suit" in known()
          and "wpn_army" in known() and tally is not None and tally.kills == 3,
          "a trader's or medic's kill: not his stock, by his logic or his spawn ini; his suit, and the kill counts: %s %s"
          % (known(), tally and tally.kills))

    # a silent kill (Stealth Kill Detection Fix): the death comes with the weapon in his hands as
    # the killer, so that nobody blames him; it is his kill all the same. A weapon in another's
    # hands, or in nobody's, is not his.
    m.reset()
    freedom = lambda i: g.person(i, "freedom", "novice", lua.table_from(["wpn_free"]))
    run(lambda: cb.npc_on_death_callback(freedom(460), g.item("wpn_knife", 9002, g.person(5, "stalker", "novice"))))
    run(lambda: cb.npc_on_death_callback(freedom(461), g.item("wpn_knife", 9003)))
    check(known() == [] and st().tally["freedom"] is None,
          "a kill with a weapon in another's hands, or in nobody's, is not his: %s" % known())
    run(lambda: cb.npc_on_death_callback(freedom(462), g.item("wpn_knife", 9001, g.db.actor)))
    tally = st().tally["freedom"]
    check(known() == ["wpn_free"] and tally is not None and tally.kills == 1,
          "a silent kill, his knife the killer: what the fighter had, and the kill counts: %s %s"
          % (known(), tally and tally.kills))

    # Immersive Identification: a fighter it identifies, who lives, shows the gun he holds, whether
    # or not the tag has its weapon line: known and new, not studied, with who carries it, and news;
    # never without II, for the dead, the unarmed or a non-faction; each identification read once;
    # none counts as a kill
    m.reset()
    g.NEWS = lua.table_from({})
    check(g.CALLBACKS.actor_on_update is None, "without II, no hook")
    lua.execute("""
        II_ID, II_WEAP, II_NAME, II_GETS = nil, "Freedom Rifle  (5.45x39)", "Ivan Petrenko", 0
        ii_identify = { get_last_identified_id = function() return II_ID end,
            get_last_identified = function() II_GETS = II_GETS + 1; return II_ID and { weap = II_WEAP, name = II_NAME } or nil end }
    """)
    g.OBJS[900] = g.person(900, "army", "novice", lua.table_from([]), lua.table_from({"weapon": "wpn_army"}))
    g.II_ID = 900
    run(lambda: cb.actor_on_first_update())
    upd = g.CALLBACKS.actor_on_update
    check(upd is not None, "with II, hooked on the first update")
    g.OBJS[901] = g.person(901, "freedom", "experienced", lua.table_from(["wpn_eco"]), lua.table_from({"weapon": "wpn_free"}))
    for i in range(3):
        run(lambda: upd())
        if i == 0:
            g.II_ID = 901
    run(lambda: g.run_timers())
    check("wpn_army" not in known(), "an identification from before the hook is not read: %s" % known())
    check("wpn_free" in known() and "wpn_free" in new() and "wpn_free" not in studied() and "wpn_eco" not in known(),
          "an identified fighter: the gun he holds, known and new, not studied; not what else he carries: %s" % known())
    check(facts("wpn_free", "carried") == {"freedom": ["experienced"]}, "who carries it: %s" % facts("wpn_free", "carried"))
    how = st().known["wpn_free"] and st().known["wpn_free"].how
    check(how and how.kind == "tag" and len(g.NEWS) == 1
          and "Learned from identifying Freedom fighter Ivan Petrenko: Freedom Rifle" in g.NEWS[1],
          "and news of it, by the name the tag showed: %s" % list(g.NEWS.values()))
    page = run(lambda: m.describe(how, st().known["wpn_free"].at))
    check(page == "identifying Freedom fighter Ivan Petrenko in Garbage, at the Depot", "where: %s" % page)
    check(g.II_GETS == 1, "each identification read once, not every frame: %d" % g.II_GETS)
    check(st().tally["freedom"] is None, "no kill tally from it")
    g.OBJS[902] = g.person(902, "monolith", "veteran", lua.table_from([]), lua.table_from({"weapon": "wpn_mono_kobra"}))
    g.II_ID, g.II_NAME = 902, None
    run(lambda: upd())
    check("wpn_mono" in known(), "a scoped copy as its model: %s" % known())
    rec = st().known["wpn_mono"]
    check(rec and run(lambda: m.describe(rec.how)) == "identifying a Monolith fighter",
          "a name the tag kept hidden stays hidden: %s" % (rec and run(lambda: m.describe(rec.how))))
    for npc_id, comm, extra, what in ((903, "army", {"weapon": "wpn_army", "dead": True}, "a dead fighter"),
                                      (904, "ecolog", {}, "an unarmed one"),
                                      (905, "trader", {"weapon": "wpn_box"}, "one of no faction"),
                                      (906, "army", {"weapon": "wpn_never"}, "a gun that never turns up")):
        g.OBJS[npc_id] = g.person(npc_id, comm, "novice", lua.table_from([]), lua.table_from(extra))
        g.II_ID = npc_id
        got = run(lambda: upd())
        check(got is None and not any(s in known() for s in ("wpn_army", "wpn_box", "wpn_never")),
              "nothing from %s: %s %s" % (what, got, known()))
    g.II_WEAP = None
    g.OBJS[907] = g.person(907, "army", "novice", lua.table_from([]), lua.table_from({"weapon": "wpn_army"}))
    g.II_ID = 907
    run(lambda: upd())
    check("wpn_army" in known(), "a tag without the weapon line (a low scanner tier) teaches it too: %s" % known())
    g.ii_identify = None

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
    g.PDA_INFO[300] = lua.table_from({"state": "default", "contact": lua.table_from({"comm": "dolg", "rank": "legend",
                                                                                     "name": "Petro"})})
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_uncommon", 300)))
    n1 = len(known())
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_uncommon", 300)))
    check(n1 == 2 and len(known()) == 2, "an uncommon PDA: two entries, once: %d then %d" % (n1, len(known())))
    rec = st().known[known()[0]]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(page == "the PDA of Duty fighter Petro", "on its page, whose PDA, and no place: %s" % page)
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

    # the read mark is the PDA's own, so the game releasing the PDA drops it, and a new PDA given
    # its id has a package (kept by id in Arsenal's save, the new one read as read). An Ecologist's
    # PDA tells only of their rifle: unknown again before each pickup, so a package shows.
    m.reset()
    eco = lambda: lua.table_from({"state": "default", "contact": lua.table_from({"comm": "ecolog", "rank": "novice"})})
    g.PDA_INFO[320] = eco()
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 320)))
    first = known()
    st().known["wpn_eco"] = None
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 320)))
    again = known()
    g.release(320)
    g.PDA_INFO[320] = eco()
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 320)))
    check(first == ["wpn_eco"] and again == [] and known() == ["wpn_eco"],
          "the same PDA once; released, a new PDA given its id has its package: %s %s %s" % (first, again, known()))
    mark = g.SE[320] and g.SE[320].arsenal_read
    check(st().pdas is None and isinstance(mark, str) and "ecolog" in mark,
          "the mark is on the PDA and names its owner, not in Arsenal's save: %r" % (mark,))
    # A PDA is no script class: one the engine releases itself (a trader's restock) keeps its se
    # vars, and the next PDA given its id gets its own owner over them. Another owner's PDA: read.
    m.reset()
    owner = lambda name: lua.table_from({"state": "default", "contact": lua.table_from(
        {"comm": "ecolog", "rank": "novice", "name": name})})
    g.PDA_INFO[340] = owner("Ivan")
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 340)))
    st().known["wpn_eco"] = None
    g.PDA_INFO[340] = owner("Petro")
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 340)))
    check(known() == ["wpn_eco"], "a stale mark from a PDA the engine released: another owner's PDA given its id is read: %s"
          % known())
    # a mark from 1.6.1's test build, before marks named the owner, still counts as read
    m.reset()
    g.PDA_INFO[350] = owner("Ivan")
    lua.execute("SE[350] = { arsenal_read = true }")
    run(lambda: cb.actor_on_item_take(g.item("itm_pda_common", 350)))
    check(known() == [], "a PDA marked by the test build stays read: %s" % known())

    # windows: a trader's stock (who sells it), a stash (where), a body (who carried it); a window
    # without cells of its own, its partner's ruck (a trader's) or all a body or box holds
    m.reset()
    gui = lua.table_from({"mode": "trade", "npc_is_box": False})
    gui.IsShown = lua.eval("function(self) return SHOWN end")
    trader = g.person(400, "stalker", "novice", lua.table_from(["wpn_trade"]), lua.table_from({"name": "Sidorovich"}))
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(trader)
    g.ui_inventory = lua.table_from({"GUI": gui})
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_trade", "sold") == {"Sidorovich": True}, "a trader's stock: sold by him: %s" % facts("wpn_trade", "sold"))
    rec = st().known["wpn_trade"]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(page == "Sidorovich in Garbage, at the Depot", "and on its page, where: %s" % page)
    gui.mode, gui.npc_is_box = "loot", True
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(g.person(401, "x", "novice", lua.table_from(["wpn_box"])))
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_box", "stash") == {"l02_garbage": True}, "a stash: where it lay: %s" % facts("wpn_box", "stash"))
    rec = st().known["wpn_box"]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(page == "a stash in Garbage, at the Depot", "and on its page, the spot: %s" % page)
    gui.npc_is_box = False
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(
        g.person(402, "freedom", "novice", lua.table_from(["wpn_free"]), lua.table_from({"dead": True})))
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("wpn_free", "carried") == {"freedom": ["novice"]}, "a body: who carried it: %s" % facts("wpn_free", "carried"))
    rec = st().known["wpn_free"]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(page == "the body of Freedom fighter npc 402 in Garbage, at the Depot", "and on its page, whose: %s" % page)
    # what is on a gun in a window, with the gun; a gun whose attachments cannot be read, still
    gui.npc_is_box = True
    gui.GetPartner = lua.eval("function(p) return function() return p end end")(
        g.person(403, "x", "novice", lua.table_from(["wpn_box", "wpn_mono_kobra"])))
    st().known["wpn_box"] = None
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(facts("kobra", "stash") == {"l02_garbage": True} and "wpn_mono" in known() and "wpn_box" in known(),
          "a stash's gun and the scope on it, where they lay: %s %s" % (facts("kobra", "stash"), known()))
    partner_of = lua.eval("function(p) return function() return p end end")

    # a trader's stock as the trade window lists it, in its own cells: not the gun in his slot, nor
    # what his trade keeps off the counter, which the window leaves out; without those cells, his
    # ruck, never his slots
    m.reset()
    g.NEWS = lua.table_from({})
    owl = g.person(410, "stalker", "novice", lua.table_from(["wpn_mono", "wpn_trade"]), lua.table_from({"name": "Owl"}))
    gui.mode, gui.npc_is_box = "trade", False
    gui.GetPartner = partner_of(owl)
    gui.CC = g.cells(lua.eval('{ npc_trade_bag = { { 4101, "wpn_trade" } }, npc_trade = {} }'))
    run(lambda: cb.GUI_on_show("UIInventory"))
    run(lambda: g.run_timers())
    check(known() == ["wpn_trade"] and facts("wpn_trade", "sold") == {"Owl": True} and st().facts["wpn_mono"] is None
          and list(g.NEWS.values()) == ["Learned from Owl: Trade Knife"],
          "a trader's stock as the window lists it, not the gun in his slot: %s %s" % (known(), list(g.NEWS.values())))
    m.reset()
    gui.CC = None
    beard = g.person(411, "stalker", "novice", lua.table_from(["wpn_mono", "wpn_trade"]),
                     lua.table_from({"name": "Beard", "ruck": lua.table_from(["wpn_trade"])}))
    gui.GetPartner = partner_of(beard)
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(known() == ["wpn_trade"], "a trade window without cells of its own: his ruck, not his slots: %s" % known())

    # a stash fills as it opens (treasure_manager spawns its loot), after its window says it is open:
    # looked into again a moment later, while the window is still open on it, it teaches what came,
    # and what the first look taught changes nothing; a window closed by then, or open on another
    # box, teaches nothing more
    m.reset()
    g.NEWS, g.TIMERS, g.SHOWN = lua.table_from({}), lua.table_from({}), True
    lua.execute("treasure_manager = { caches = { [420] = true, [421] = true, [422] = false, [423] = 'x' } }")
    fresh = g.person(420, "x", "novice", lua.table_from(["wpn_box"]))
    gui.mode, gui.npc_is_box = "loot", True
    gui.GetPartner = partner_of(fresh)
    run(lambda: cb.GUI_on_show("UIInventory"))
    first = known()
    fresh["items"][2] = "wpn_army"
    run(lambda: g.run_timers())
    run(lambda: g.run_timers())
    check(first == ["wpn_box"] and known() == ["wpn_army", "wpn_box"] and facts("wpn_army", "stash") == {"l02_garbage": True},
          "a stash looked into again a moment later: what spawned after it opened is known, where: %s %s"
          % (first, known()))
    check(list(g.NEWS.values()) == ["Learned from a stash: Box Gun", "Learned from a stash: Army Rifle"],
          "news once for each look's new gear: %s" % list(g.NEWS.values()))
    shut = g.person(421, "x", "novice", lua.table_from([]))
    gui.GetPartner = partner_of(shut)
    run(lambda: cb.GUI_on_show("UIInventory"))
    shut["items"][1] = "wpn_eco"
    g.SHOWN = False
    run(lambda: g.run_timers())
    closed = "wpn_eco" in known()
    g.SHOWN = True
    left = g.person(422, "x", "novice", lua.table_from([]))
    gui.GetPartner = partner_of(left)
    run(lambda: cb.GUI_on_show("UIInventory"))
    left["items"][1] = "wpn_eco"
    gui.GetPartner = partner_of(g.person(423, "x", "novice", lua.table_from(["wpn_free"])))
    run(lambda: g.run_timers())
    check(not closed and "wpn_eco" not in known() and "wpn_free" not in known(),
          "a window closed by then, or open on another box, teaches nothing more: %s %s" % (closed, known()))

    # a box of the player's own (a dropped backpack, a furniture stash: none of treasure_manager's
    # stashes) teaches nothing, then or later; without treasure_manager's list, the boxes
    # item_backpack and Hideout Furniture record as his (player_created_stashes, workshop_stashes)
    m.reset()
    g.TIMERS = lua.table_from({})
    gui.GetPartner = partner_of(g.person(430, "x", "novice", lua.table_from(["wpn_army"])))
    run(lambda: cb.GUI_on_show("UIInventory"))
    check(known() == [] and len(g.TIMERS) == 0, "a box of the player's own teaches nothing, then or later: %s" % known())
    lua.execute('treasure_manager = nil\n'
                'alife_storage_manager = { get_state = function() return {\n'
                '    player_created_stashes = { [430] = "inv_backpack" }, workshop_stashes = { [77] = 432 } } end }')
    got = []
    for box_id in (430, 432, 431):
        gui.GetPartner = partner_of(g.person(box_id, "x", "novice", lua.table_from(["wpn_army"])))
        run(lambda: cb.GUI_on_show("UIInventory"))
        got.append(known())
    check(got == [[], [], ["wpn_army"]],
          "without treasure_manager's list: not a backpack or furniture stash of his, a box else: %s" % got)
    lua.execute("alife_storage_manager = nil")

    # a live companion's pack, as the window shows it (what he was given): known, from him, with no
    # word of who carries it; not the gun in his hands, which the window leaves out; a fighter alive
    # the window does not call a companion, the same
    m.reset()
    g.NEWS, g.TIMERS = lua.table_from({}), lua.table_from({})
    wolf = g.person(440, "stalker", "veteran", lua.table_from(["wpn_free", "wpn_eco"]), lua.table_from({"name": "Wolf"}))
    gui.mode, gui.npc_is_box, gui.npc_is_companion = "loot", False, True
    gui.GetPartner = partner_of(wolf)
    gui.CC = g.cells(lua.eval('{ npc_bag = { { 4401, "wpn_eco" } } }'))
    run(lambda: cb.GUI_on_show("UIInventory"))
    run(lambda: g.run_timers())
    rec = st().known["wpn_eco"]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(known() == ["wpn_eco"] and st().facts["wpn_eco"] is None and page == "Wolf in Garbage, at the Depot"
          and list(g.NEWS.values()) == ["Learned from Wolf: Eco Rifle"],
          "a companion's pack: known, from him, no word of who carries it, not the gun he holds: %s %s %s %s"
          % (known(), st().facts["wpn_eco"], page, list(g.NEWS.values())))
    m.reset()
    gui.npc_is_companion = False
    run(lambda: cb.GUI_on_show("UIInventory"))
    rec = st().known["wpn_eco"]
    check(known() == ["wpn_eco"] and rec is not None and rec.how.kind == "pack",
          "a fighter alive the window does not call a companion: the same: %s" % known())
    gui.npc_is_companion, gui.CC, g.SHOWN = None, None, False

    # talks: one thing a day per person; an expert's with specs; an enemy will not talk
    m.reset()
    g.math.randomseed(3)
    vet = g.person(500, "dolg", "veteran")
    ok1 = run(lambda: m.rumor_ok(g.db.actor, vet))
    text = run(lambda: m.rumor_text(g.db.actor, vet))
    run(lambda: m.rumor_told(g.db.actor, vet))
    check(ok1 is True and isinstance(text, str) and len(known()) == 1 and studied() == [],
          "a talk: one thing, no specs from a veteran: %s %s %s" % (ok1, text, known()))
    rec = known() and st().known[known()[0]]
    page = rec and run(lambda: m.describe(rec.how, rec.at))
    check(page == "npc 500 in Garbage, at the Depot", "on its page, who told it and where: %s" % page)
    check(run(lambda: m.rumor_ok(g.db.actor, vet)) is False, "once a day")
    g.DAY = 15
    check(run(lambda: m.rumor_ok(g.db.actor, vet)) is True, "and again the next day")
    leg = g.person(501, "dolg", "legend")
    run(lambda: m.rumor_ok(g.db.actor, leg))
    run(lambda: m.rumor_told(g.db.actor, leg))
    check(len(studied()) == 1, "a legend's word comes with specs: %s" % studied())
    foe = g.person(502, "dolg", "legend", None, lua.table_from({"relation": 3}))
    check(run(lambda: m.rumor_ok(g.db.actor, foe)) is False, "an enemy does not talk")
    # the day's mark is the fighter's own: once he is released, a new fighter given his id talks
    m.reset()
    one = g.person(520, "ecolog", "novice")
    said = run(lambda: m.rumor_ok(g.db.actor, one))
    run(lambda: m.rumor_told(g.db.actor, one))
    st().known["wpn_eco"] = None
    twice = run(lambda: m.rumor_ok(g.db.actor, one))
    g.release(520)
    other = run(lambda: m.rumor_ok(g.db.actor, g.person(520, "ecolog", "novice")))
    check(said is True and twice is False and other is True and st().talked is None,
          "a fighter talks once a day; released, a new one given his id talks; nothing kept in the save: %s %s %s"
          % (said, twice, other))

    # a technician: word of a special gun not yet known, for money; with specs and how to get it
    m.reset()
    smith = g.person(600, "stalker", "expert", None, lua.table_from({"name": "Cardan", "purse": 5000}))
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
    check(g.MONEY == 17000 and smith.purse == 8000,
          "the price leaves the player and reaches the technician (transfer_money would take it from him too): "
          "player %s, technician %s" % (g.MONEY, smith.purse))
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
    lua.execute("SE[610] = nil")         # and his mark from that talk
    both = (run(lambda: m.gunsmith_ok(g.db.actor, trader)), run(lambda: m.rumor_ok(g.db.actor, trader)))
    g.MONEY = 20000
    rich = run(lambda: m.gunsmith_can_pay(g.db.actor, trader))
    said = run(lambda: m.rumor_text(g.db.actor, trader))
    check(both == (True, True) and rich is True and named(said),
          "and the offer checked first: %s %r %r" % (both, rich, said))
    # MCM > Arsenal > Paid word of special guns, off: the trader offers no word of a special gun,
    # and still talks of gear for free; on again, the offer is back. An Arsenal MCM without the
    # option keeps the offer
    m.reset()
    lua.execute("SE[610] = nil")
    g.GUNSMITH = False
    off = (run(lambda: m.rumor_ok(g.db.actor, trader)), run(lambda: m.gunsmith_ok(g.db.actor, trader)))
    g.GUNSMITH = True
    back = run(lambda: m.gunsmith_ok(g.db.actor, trader))
    m.reset()
    opt, g.arsenal_mcm.gunsmith = g.arsenal_mcm.gunsmith, None
    older = run(lambda: m.gunsmith_ok(g.db.actor, trader))
    g.arsenal_mcm.gunsmith = opt
    check(off == (True, False) and back is True and older is True,
          "the paid talk off: no offer, the free talk stays; on again, offered; without the option, offered: "
          "%s %r %r" % (off, back, older))

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
    # Mark all read: every new model read at once, the count to none; what is known stays known
    st().new["wpn_eco"] = True
    check(run(lambda: m.count_new()) == 2, "two new again: %s" % run(lambda: m.count_new()))
    run(lambda: m.mark_all_read())
    check(new() == [] and run(lambda: m.count_new()) == 0 and "wpn_eco" in known(),
          "Mark all read: nothing new, still known: %s %s" % (new(), known()))

    # another mod's source (arsenal_api.reveal), in its own words, on the page and in the news
    m.reset()
    g.NEWS = lua.table_from({})
    how = lua.table_from({"kind": "api", "who": "the Mercenary Database"})
    got = run(lambda: m.reveal("wpn_eco", how, None, False, False))
    run(lambda: g.run_timers())
    check(got is not None and "wpn_eco" in known() and "wpn_eco" in new()
          and run(lambda: m.describe(how, lua.table_from({"lvl": "l01_escape"}))) == "the Mercenary Database"
          and len(g.NEWS) == 1 and "Learned from the Mercenary Database: " in g.NEWS[1],
          "another mod's source, in its words: %s %s" % (run(lambda: m.describe(how)), list(g.NEWS.values())))
    nameless = run(lambda: m.describe(lua.table_from({"kind": "api"})))
    check(nameless == "someone", "one that gives no name: %s" % nameless)

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
    # keys that are one model now come together: learned when the first of them was, and every fact
    # of each kept, whichever of the two comes first
    merged = []
    for early, late in (("wpn_mono", "wpn_mono_kobra"), ("wpn_mono_kobra", "wpn_mono")):
        m.reset()
        lua.execute("""
local st, early, late = arsenal_intel.state(), ...
st.known[early] = { at = { y = 2012, mo = 5, d = 1, h = 8, mi = 0, lvl = "l01_escape" }, how = { kind = "kill" } }
st.known[late] = { at = { y = 2012, mo = 6, d = 2, h = 9, mi = 0, lvl = "l02_garbage" }, how = { kind = "talk" } }
st.facts[early] = { carried = { monolith = { novice = true } }, ways = { kit = true } }
st.facts[late] = { carried = { monolith = { veteran = true }, dolg = { legend = true } }, stash = { l01_escape = true } }
""", early, late)
        m.regroup()
        rec = st().known["wpn_mono"]
        merged.append((known(), rec and rec.at.mo, rec and rec.how.kind, facts("wpn_mono", "carried"),
                       facts("wpn_mono", "stash"), facts("wpn_mono", "ways")))
    want = (["wpn_mono"], 5, "kill", {"monolith": ["novice", "veteran"], "dolg": ["legend"]}, {"l01_escape": True},
            {"kit": True})
    check(merged == [want, want], "keys that are one model now: the first learned kept, every fact of each: %s" % merged)
    # that record (a later Arsenal's) is saved back as it was, never over, and logged; what this
    # one learns meanwhile is kept beside it, and read back on the next load
    same = lua.eval("function(a, b) return rawequal(a, b) end")
    later = lua.table_from({"v": 99, "known": lua.table_from({"wpn_free": True})})
    data = lua.table_from({"arsenal_intel": later})
    g.LOG = lua.table_from({})
    cb.load_state(data)
    start = known()
    run(lambda: m.reveal("wpn_eco", lua.table_from({"kind": "kill"}), None, True, True))
    cb.save_state(data)
    own = data["arsenal_intel_v1"]
    untouched = same(data.arsenal_intel, later) and later.v == 99 and list(later.known.keys()) == ["wpn_free"]
    check(start == [] and untouched and own is not None and list(own.known.keys()) == ["wpn_eco"],
          "a later version's record: saved back untouched, this one's beside it: %s %s %s"
          % (start, untouched, own and list(own.known.keys())))
    check(len(g.LOG) == 1 and "another Arsenal's (data version 99)" in g.LOG[1], "and logged: %s" % list(g.LOG.values()))
    m.reset()
    cb.load_state(data)
    back = known()
    cb.save_state(data)
    check(back == ["wpn_eco"] and same(data.arsenal_intel, later),
          "on the next load, this one's read back, the other's still kept: %s" % back)
    cb.load_state(lua.table_from({}))

    # a save from before 1.6.1: its read PDAs by id go onto the PDAs holding those ids now, before
    # the PDAs he carries are read; an id something else holds now, or nothing, is dropped; the
    # lists go from the save
    m.reset()
    g.ALIFE[330] = g.se_thing("itm_pda_uncommon", 330)
    g.ALIFE[331] = g.se_thing("medkit", 331)
    g.PDA_INFO[330] = lua.table_from({"state": "default", "contact": lua.table_from({"comm": "ecolog", "rank": "novice"})})
    g.ACTOR_ITEMS = lua.table_from([g.item("itm_pda_uncommon", 330)])
    cb.load_state(lua.table_from({"arsenal_intel": lua.table_from({
        "v": 1, "known": lua.table_from({}), "pdas": lua.table_from({330: True, 331: True, 332: True}),
        "talked": lua.table_from({540: 14})})}))
    got = run(lambda: cb.actor_on_first_update())
    mark = g.SE[330] and g.SE[330].arsenal_read
    check(got is None and "wpn_eco" not in known() and isinstance(mark, str) and g.SE[331] is None and st().pdas is None
          and st().talked is None,
          "an older save's read PDA stays read, carried at the load; nothing marked that is no PDA; the lists gone: "
          "%s %s %s %s" % (got, known(), mark, g.SE[331]))
    g.ACTOR_ITEMS = lua.table_from([])

    # a disguise: dressed as Freedom, the live community says Freedom; what he is taught at load is
    # still Duty's, his true faction (gameplay_disguise's), and Duty is still "his" faction
    m.reset()
    lua.execute('db.actor.character_community = function() return "actor_freedom" end\n'
                'function get_actor_true_community() return "dolg" end')
    cb.load_state(lua.table_from({}))
    run(lambda: cb.actor_on_first_update())
    check(known() == ["duty_suit", "wpn_duty", "wpn_duty_rare", "wpn_kit"] and "wpn_free" not in known(),
          "disguised as Freedom, a load teaches Duty's gear, not Freedom's: %s" % known())
    check(m.player_faction() == "dolg", "and his faction is still Duty: %s" % m.player_faction())
    lua.execute('db.actor.character_community = function() return "actor_dolg" end\n'
                'get_actor_true_community = nil')

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
