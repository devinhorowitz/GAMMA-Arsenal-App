"""Run arsenal_collection.script under LuaJIT against stubs (the engine, arsenal_data), and
check the collector: a variant is found once, a combination counts as its gun, the load-time
scan is quiet, later finds send news (a model's second variant too), a model counts as found
once, from its earliest variant, the set survives a save and a load, and finds kept under
sections that now share a variant move to it, the earliest kept. A find keeps how it came, from
what is open as it is taken (a stash's, a body's or a trader's window, a companion's pack, the
workshop, a talk), else picked up; already carried when a save loads; seen in a window, as the
window shows it (a trader's stock as it lists it, a stash looked into again as it fills, never a
box of the player's own or a companion's pack); a find kept before that shows its level alone.

    python test_collection.py            the real script
    python test_collection.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_collection.script"), encoding="latin-1").read()
WHERE = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_where.script"), encoding="latin-1").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(HERE, "..", "gamedata", "configs", "text", "eng", "st_arsenal.xml"),
                                  encoding="cp1251").read(), re.S))

STUBS = r"""
news = {}
callbacks = {}
clock = { 2012, 5, 14, 9, 30 }
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
local T = ...
for k, v in pairs({ st_arsenal_new_entry = "New in Arsenal: %s", st_arsenal_title = "Arsenal",
    st_arsenal_and_more = "%s and %s more", l01_escape = "Cordon", st_faction_dolg = "Duty" }) do T[k] = v end
game = {
    translate_string = function(k) return T[k] or k end,
    get_game_time = function() return { get = function() return unpack(clock) end } end,
}
-- objects in the world by id (level.object_by_id), and time events as _g.script keeps them
OBJS = {}
level = { name = function() return "l01_escape" end, object_by_id = function(id) return OBJS[id] end }
TIMERS = {}
function CreateTimeEvent(a, b, delay, fn) TIMERS[#TIMERS + 1] = fn end
function run_timers() local t = TIMERS; TIMERS = {}; for _, fn in ipairs(t) do fn() end end
-- gun models and their variants, as arsenal_data builds them
local function model(name, variants)
    local e = { name = name, variants = variants, sec = variants[1].sec }
    for _, v in ipairs(variants) do v.entry = e end
    return e
end
local ak = { sec = "wpn_ak74", name = "AK-74" }
local pm = { sec = "wpn_pm", name = "PM" }
local fort = { sec = "wpn_fort", name = "Fort-17" }                   -- one variant, two sections
local sks200, sks350 = { sec = "wpn_sks", name = "SKS (200 RPM)" }, { sec = "wpn_sks_b", name = "SKS (350 RPM)" }
sks = model("SKS", { sks200, sks350 })
model("AK-74", { ak }); model("PM", { pm }); model("Fort-17", { fort })
local by_var = { wpn_ak74 = ak, wpn_pm = pm, wpn_fort = fort, wpn_fort17 = fort, wpn_sks = sks200, wpn_sks_b = sks350 }
local parent = { wpn_ak74_pso = "wpn_ak74" }
arsenal_data = {
    FACTIONS = { "stalker", "dolg", "freedom" },
    variant_for = function(sec) return by_var[parent[sec] or sec] end,
    variant_of = function(sec) return by_var[sec] end,
    get = function(sec) local v = by_var[sec]; return v and v.entry end,
}
local function item(sec) return { section = function() return sec end } end
inventory = { item("wpn_pm"), item("ammo_545") }
-- where things are (arsenal_where): all on Cordon, at vertex 10
function game_graph() return { valid_vertex_id = function(self, gv) return gv == 10 end,
    vertex = function() return { level_id = function() return 1 end } end } end
function alife() return { level_name = function() return "l01_escape" end } end
function vector() return { set = function(self, x, y, z) return { x = x, y = y, z = z } end } end
dynamic_news_helper = { GetPointDescription = function(obj) return "in Cordon, near the rookie village" end }
local function at_spot(o)
    o.game_vertex_id = function() return 10 end
    o.position = function() return { x = 1, y = 2, z = 3 } end
    return o
end
talking = false
db = { actor = at_spot({
    give_game_news = function(self, cap, text) news[#news + 1] = text end,
    iterate_inventory = function(self, fn) for _, o in ipairs(inventory) do fn(self, o) end end,
    is_talking = function() return talking end,
}) }
-- a talk's other side (_g.get_speaker), and the workshop window
speaker = at_spot({ character_name = function() return "Wolf" end })
function get_speaker(safe) return talking and speaker or nil end
crafting = false
ui_workshop = { GUI = { IsShown = function() return crafting end } }
function IsStalker(o) return o and o.stalker == true end
function take(sec) callbacks.actor_on_item_take(item(sec)) end
-- the option to count guns seen, and the inventory window: its mode and partner, as ui_inventory
-- keeps them; a box holds a Fort-17, an SKS and ammo; a trader five guns and a PM
seen_on = false
-- tell is Arsenal's one way to the PDA (arsenal_mcm), on here; test_mcm.py silences it
arsenal_mcm = { count_seen = function() return seen_on end,
    tell = function(text) db.actor:give_game_news("Arsenal", text) end }
-- what the player knows (arsenal_intel): told of every find
told = {}
arsenal_intel = { found = function(sec, live) told[#told + 1] = sec .. (live and " in play" or "") end }
for _, s in ipairs({ "a", "b", "c", "d", "e" }) do
    local v = { sec = "wpn_" .. s, name = s:upper() }
    model(s:upper(), { v })
    by_var[v.sec] = v
end
-- a box or a fighter holding a list of sections, under an id of its own; a fighter's ruck (what is
-- not in his slots) the list given, else all he holds
local last_id = 500
function holding(list, box, ruck)
    local p = at_spot({ list = list, ruck = ruck })
    last_id = last_id + 1
    local id = last_id
    p.id = function() return id end
    local function each(self, fn, arg) for _, s in ipairs(self.list) do fn(arg, item(s)) end end
    local function each_ruck(self, fn, arg) for _, s in ipairs(self.ruck or self.list) do fn(arg, item(s)) end end
    local function none() end
    p.iterate_inventory_box = box and each or none
    p.iterate_inventory = box and none or each
    p.iterate_ruck = box and none or each_ruck
    return p
end
-- the inventory window's own cells (ui_inventory's CC), by bag: the ids it shows, each an item in
-- the world
function cells(bags)
    local cc = {}
    for bag, list in pairs(bags) do
        local ids = {}
        for _, x in ipairs(list) do
            OBJS[x[1]] = item(x[2])
            ids[x[1]] = 1
        end
        cc[bag] = { indx_id = ids }
    end
    return cc
end
box = holding({ "wpn_fort17", "wpn_sks", "ammo_545" }, true)
trader = holding({ "wpn_a", "wpn_b", "wpn_c", "wpn_d", "wpn_e", "wpn_pm" }, false)
trader.stalker = true
trader.character_name = function() return "Sidorovich" end
trader.character_community = function() return "trader" end
body = holding({}, false)
body.stalker = true
body.character_name = function() return "Ivan Petrenko" end
body.character_community = function() return "dolg" end
-- the inventory window: open or not, and how often a take asks (only a new find should)
shown, asked = false, 0
ui_inventory = { GUI = { mode = "loot", npc_is_box = true, partner = box,
    IsShown = function() asked = asked + 1; return shown end,
    GetPartner = function(self) return self.partner end } }
function show(name) if callbacks.GUI_on_show then callbacks.GUI_on_show(name) end end
-- what goes on the guns: the Kobra, the PSO-1 and the PBS, each a model; the combinations that
-- carry one; a gun whose attachments cannot be read; a box with a scoped gun
for _, a in ipairs({ { "kobra", "Kobra" }, { "pso", "PSO-1" }, { "sil", "PBS" } }) do
    local v = { sec = a[1], name = a[2] }
    model(a[2], { v })
    by_var[a[1]] = v
end
parent.wpn_ak74_kobra, parent.wpn_b_sil, parent.wpn_e_pso = "wpn_ak74", "wpn_b", "wpn_e"
local on = { wpn_ak74_kobra = { "kobra" }, wpn_b_sil = { "sil" }, wpn_e_pso = { "pso" } }
arsenal_data.mounted_addons = function(obj)
    local s = obj:section()
    if s == "wpn_c" then error("cannot read it") end
    return on[s] or {}
end
box2 = holding({ "wpn_e_pso" }, true)
function carry(list) inventory = {} for _, s in ipairs(list) do inventory[#inventory + 1] = item(s) end end
"""

MUTANTS = {
    "quiet_scan": ("            mark_with(obj, true, carried)", "            mark_with(obj, false, carried)"),
    "twice": ("if not v or found[v.sec] then return nil end", "if not v then return nil end"),
    "intel": ("    if arsenal_intel and arsenal_intel.found then arsenal_intel.found(sec, scanned) end\n", ""),
    "intel_all_live": ("arsenal_intel.found(sec, scanned)", "arsenal_intel.found(sec, true)"),
    "intel_never_live": ("arsenal_intel.found(sec, scanned)", "arsenal_intel.found(sec, false)"),
    "no_save": ("m_data.arsenal = { v = VERSION, found = found }", "m_data.arsenal = nil"),
    "variant": ("local v = arsenal_data.variant_for(sec)", "local v = arsenal_data.variant_of(sec)"),
    "no_regroup": ("    regroup()\n    scan()", "    scan()"),
    "latest": ("if not out[key] or earlier(at, out[key]) then", "if not out[key] or earlier(out[key], at) then"),
    "count_keys": ("if e and not seen[e] then", "if e then"),
    "drop_gone": ("local key = v and v.sec or sec", "local key = v and v.sec or false"),
    "model_latest": ("if at and (not first or earlier(at, first)) then", "if at and (not first or earlier(first, at)) then"),
    "count_variants": ("if entry_found(e) then n = n + 1 end", "for _, v in ipairs(e.variants) do if found[v.sec] then n = n + 1 end end"),
    "seen_option": ("    if not (arsenal_mcm and arsenal_mcm.count_seen()) then return end\n", ""),
    "seen_name": ('if name ~= "UIInventory" or not scanned then return end', "if not scanned then return end"),
    "seen_mode": ('if not (gui and (gui.mode == "loot" or gui.mode == "trade")) then return end', "if not gui then return end"),
    "seen_box": ("    if gui.npc_is_box then\n", "    if false then\n"),
    "seen_more": ("    if #list > 3 then\n", "    if false then\n"),
    "seen_quiet": ("for _, v in ipairs(obj and mark_with(obj, true, how) or {}) do",
                   "for _, v in ipairs(obj and mark_with(obj, false, how) or {}) do"),
    "seen_register": ('    RegisterScriptCallback("GUI_on_show", GUI_on_show)\n', ""),
    "how_kept": ("    at.how = how\n", ""),
    "eager": ("mark_with(obj, not scanned, scanned and take_source or carried)",
              "mark_with(obj, not scanned, scanned and take_source() or carried())"),
    "shown": ('    if gui and gui:IsShown() and (gui.mode == "loot" or gui.mode == "trade") then',
              '    if gui and (gui.mode == "loot" or gui.mode == "trade") then'),
    "trade": ('    if gui.mode == "trade" then\n        return { kind = pre .. "trade"', '    if false then\n        return { kind = pre .. "trade"'),
    "box": ('    elseif gui.npc_is_box then\n        return { kind = pre .. "stash"', '    elseif false then\n        return { kind = pre .. "stash"'),
    "workshop": ("    if ws and ws:IsShown() then", "    if false then"),
    "talk": ("    if db.actor:is_talking() then", "    if false then"),
    "scan_carried": ("            mark_with(obj, true, carried)", "            mark_with(obj, true)"),
    # what is on a gun
    "mounted_none": ("local ok, on = pcall(arsenal_data.mounted_addons, obj)", "local ok, on = false, nil"),
    "mounted_loud": ("        local a = mark(s, true, once)", "        local a = mark(s, false, once)"),
    "mounted_how_each": ("        local a = mark(s, true, once)", "        local a = mark(s, true, how)"),
    "mounted_quiet": ("    if not quiet then notify(new) end", "    notify(new)"),
    "mounted_pcall": ("local ok, on = pcall(arsenal_data.mounted_addons, obj)",
                      "local ok, on = true, arsenal_data.mounted_addons(obj)"),
    "mounted_once": ("        if made == nil then made = (type(how) == \"function\") and how() or how end",
                     "        made = (type(how) == \"function\") and how() or how"),
    "seen_prefix": ('    local pre = seen and "seen_" or ""', '    local pre = ""'),
    "who": ("        s = string.format(s, arsenal_where.who_text(how))", "        s = string.format(s, how.who)"),
    "old_level": ('    if not way then return at.lvl and game.translate_string(at.lvl) or "" end', '    if not way then return "" end'),
    "place": ("    return arsenal_where.at_place(s, how.place, at.lvl)", "    return s"),
    # a window counts what it shows: a trader's stock as it lists it, his ruck without it
    "stock_all": ("        stock_of(gui, partner)(take)", "        partner:iterate_inventory(take, partner)"),
    "stock_cells_unread": ("        if #lists == 0 then\n            partner:iterate_ruck(fn, partner)",
                           "        if true then\n            partner:iterate_ruck(fn, partner)"),
    "stock_ruck_all": ("            partner:iterate_ruck(fn, partner)", "            partner:iterate_inventory(fn, partner)"),
    # a stash looked into again a moment after it opens, while its window is still open on it
    "seen_stash_once": ("    if box then look_again(partner:id()) end\n", ""),
    "seen_again_closed": ("        if gui and gui.npc_is_box and gui:IsShown() then ok, box = pcall(gui.GetPartner, gui) end",
                          "        if gui then ok, box = pcall(gui.GetPartner, gui) end"),
    "seen_again_other": ("        if ok and box and box:id() == id then see(gui, box) end", "        if ok and box then see(gui, box) end"),
    # the player's own boxes
    "seen_own_stash": ("    if box and not zone_stash(partner) then return end\n", ""),
    "seen_own_list": ('    if type(caches) == "table" then return caches[id] ~= nil end', '    if type(caches) == "table" then return true end'),
    "seen_own_backpack": ('    if type(m.player_created_stashes) == "table" and m.player_created_stashes[id] ~= nil then return false end\n',
                          ""),
    "seen_own_workbench": ("        if sid == id then return false end\n", ""),
    # a live companion
    "seen_pack": ('    if not box and gui.mode == "loot" and IsStalker(partner) and living(gui, partner) then return end\n', ""),
    "gift_as_body": ('    elseif IsStalker(partner) and living(gui, partner) then\n        return { kind = "gift"',
                     '    elseif false then\n        return { kind = "gift"'),
    "living_companions_only": ("    return gui.npc_is_companion == true or (partner.alive ~= nil and partner:alive() == true)",
                               "    return gui.npc_is_companion == true"),
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
    load = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); f(); return env end")
    lua.globals().arsenal_where = load(WHERE)
    m = load(src)
    m.on_game_start()
    g = lua.globals()
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    news = lambda: list(g.news.values())
    g.callbacks.load_state(lua.table())
    g.take("wpn_ak74")                      # a take before the first update: loading, quiet
    check(news() == [], "takes while a save loads send no news")
    g.callbacks.actor_on_first_update(None)
    check(m.is_found("wpn_pm") and news() == [], "the load-time scan finds what is carried, quietly")
    check(m.count_found(None) == 2, "two found: %d" % m.count_found(None))
    g.callbacks.load_state(lua.table())
    g.callbacks.actor_on_first_update(None)
    g.take("wpn_ak74_pso")
    check(news() == ["New in Arsenal: AK-74"], "a scoped AK-74 finds the AK-74, with news: %s" % news())
    g.take("wpn_ak74")
    check(len(news()) == 1, "found once")
    check(list(g.told.values()) == ["wpn_ak74", "wpn_pm", "wpn_pm", "wpn_ak74_pso in play"],
          "what the player knows is told of each find, quiet ones too, and which were found in play: %s"
          % list(g.told.values()))
    check(m.found_at("wpn_ak74").lvl == "l01_escape" and m.found_at("wpn_ak74").d == 14, "when and where")
    words = lambda sec: m.describe(m.found_at(sec))
    check(words("wpn_pm") == "already in your pack in Cordon, near the rookie village",
          "how: what the load-time scan finds was already carried: %s" % words("wpn_pm"))
    check(words("wpn_ak74") == "picked up in Cordon, near the rookie village",
          "a take with nothing open: picked up, and the spot: %s" % words("wpn_ak74"))
    g.asked = 0
    g.take("wpn_ak74")
    check(g.asked == 0 and words("wpn_ak74").startswith("picked up"),
          "a gun already found: nothing asked of the windows, its find unchanged")

    # a model of two variants: each is news, the model counts once, found when its first was
    g.take("wpn_sks_b")
    g.clock[3] = 20                         # six days later
    g.take("wpn_sks")
    check(news()[-2:] == ["New in Arsenal: SKS (350 RPM)", "New in Arsenal: SKS (200 RPM)"],
          "each new variant is news, by its name: %s" % news()[-2:])
    at = m.entry_found(g.sks)
    check(at is not None and at.d == 14, "a model is found when its first variant was: %s" % (at and at.d,))
    check(m.count_found(lua.table_from([g.sks])) == 1 and m.count_found(None) == 3,
          "a model counts once, whatever its variants: %d of the list, %d in all"
          % (m.count_found(lua.table_from([g.sks])), m.count_found(None)))

    gui = g.ui_inventory.GUI
    g.shown = True
    g.take("wpn_fort")
    gui.npc_is_box, gui.partner = False, g.body
    g.take("wpn_a")
    gui.mode, gui.partner = "trade", g.trader
    g.take("wpn_b")
    g.shown, g.crafting = False, True
    g.take("wpn_c")
    g.crafting, g.talking = False, True
    g.take("wpn_d")
    g.talking = False
    gui.mode, gui.npc_is_box, gui.partner = "loot", True, g.box
    g.take("wpn_e")
    got = [words(x) for x in ("wpn_fort", "wpn_a", "wpn_b", "wpn_c", "wpn_d", "wpn_e")]
    place = " in Cordon, near the rookie village"
    check(got == ["looted from a stash" + place, "taken from the body of Duty fighter Ivan Petrenko" + place,
                  "bought from Sidorovich" + place, "crafted" + place, "given to you by Wolf" + place, "picked up" + place],
          "a stash's window, a body's (whose), a trader's (whom), the workshop, a talk (who gave it), and a "
          "window left closed is not open: %s" % got)
    check(m.describe(lua.table_from({"y": 2012, "mo": 5, "d": 1, "lvl": "l01_escape"})) == "Cordon",
          "a find kept before Arsenal kept how: its level alone")

    saved = lua.table()
    g.callbacks.save_state(saved)
    m2 = load(src)
    m2.on_game_start()
    g.callbacks.load_state(saved)
    check(m2.is_found("wpn_ak74") and m2.is_found("wpn_sks_b") and not m2.is_found("wpn_toz34"),
          "the set survives a save and a load")
    check(m2.describe(m2.found_at("wpn_a")) == "taken from the body of Duty fighter Ivan Petrenko" + place,
          "and how each came: %s" % m2.describe(m2.found_at("wpn_a")))

    # a save from an older catalog: finds under two sections of one variant, and a gun this
    # mod list no longer has
    old = lua.eval("""function() return { arsenal = { v = 1, found = {
        wpn_fort17 = { y = 2012, mo = 5, d = 14, h = 9, mi = 30, lvl = "l01_escape" },
        wpn_fort = { y = 2012, mo = 6, d = 1, h = 8, mi = 0, lvl = "l02_garbage" },
        wpn_gone = { y = 2012, mo = 5, d = 1, h = 0, mi = 0, lvl = "l01_escape" } } } } end""")()
    m3 = load(src)
    m3.on_game_start()
    g.callbacks.load_state(old)
    check(m3.count_found(None) == 1, "the count is of models, not of sections: %d" % m3.count_found(None))
    g.callbacks.actor_on_first_update(None)
    at = m3.found_at("wpn_fort")
    check(at is not None and at.mo == 5 and not m3.is_found("wpn_fort17"),
          "finds move to their variant on the first update, the earliest kept: %s" % (at and (at.mo, at.d),))
    check(m3.is_found("wpn_gone"), "a gun the catalog does not have keeps its find")
    check(m3.count_found(None) == 2, "Fort-17 and the PM carried: %d" % m3.count_found(None))
    # guns seen in a body, stash or trader's window: only with the option on, only that window
    m4 = load(src)
    m4.on_game_start()
    g.callbacks.load_state(lua.table())
    g.callbacks.actor_on_first_update(None)
    before = len(news())
    g.show("UIInventory")
    check(not m4.is_found("wpn_fort") and len(news()) == before, "a box's guns do not count while the option is off")
    g.seen_on = True
    g.show("UIPdaWnd")
    g.ui_inventory.GUI.mode = "inventory"
    g.show("UIInventory")
    check(not m4.is_found("wpn_fort"), "not another window, not the player's own inventory")
    g.ui_inventory.GUI.mode = "loot"
    g.show("UIInventory")
    check(m4.is_found("wpn_fort") and m4.is_found("wpn_sks") and news()[before:] == ["New in Arsenal: Fort-17, SKS (200 RPM)"],
          "with it on, a box's guns count when it opens, one news line for all: %s" % news()[before:])
    check(m4.describe(m4.found_at("wpn_fort")) == "seen in a stash" + place,
          "seen there: %s" % m4.describe(m4.found_at("wpn_fort")))
    gui = g.ui_inventory.GUI
    gui.mode, gui.npc_is_box, gui.partner = "trade", False, g.trader
    g.show("UIInventory")
    check(news()[-1] == "New in Arsenal: A, B, C and 2 more" and m4.is_found("wpn_e"),
          "a trader's stock counts too; three names, then how many more: %s" % news()[-1])
    check(m4.describe(m4.found_at("wpn_e")) == "seen in Sidorovich's stock" + place,
          "seen in his stock: %s" % m4.describe(m4.found_at("wpn_e")))

    # what is on a gun is found with it, the same way: a scoped AK-74 brings the Kobra; a new gun
    # and what is on it are one news line, how they came asked once; a gun whose attachments
    # cannot be read is still found
    m5 = load(src)
    m5.on_game_start()
    g.seen_on, g.shown = False, False
    g.callbacks.load_state(lua.table())
    g.callbacks.actor_on_first_update(None)
    w5 = lambda sec: m5.describe(m5.found_at(sec))
    before = len(news())
    g.take("wpn_ak74")
    g.take("wpn_ak74_kobra")
    check(m5.is_found("kobra") and news()[before:] == ["New in Arsenal: AK-74", "New in Arsenal: Kobra"]
          and w5("kobra") == "picked up" + place,
          "an attachment on a gun already found is found with it: %s %s" % (news()[before:], w5("kobra")))
    before = len(news())
    g.asked, g.shown = 0, True
    gui.mode, gui.npc_is_box, gui.partner = "trade", False, g.trader
    g.take("wpn_b_sil")
    check(news()[before:] == ["New in Arsenal: B, PBS"] and g.asked == 1
          and w5("sil") == "bought from Sidorovich" + place == w5("wpn_b"),
          "a new gun and what is on it: one news line, how they came asked once: %s, asked %d, %s"
          % (news()[before:], g.asked, w5("sil")))
    g.shown = False
    try:
        g.take("wpn_c")
        took = True
    except Exception:
        took = False
    check(took and m5.is_found("wpn_c"), "a gun whose attachments cannot be read is still found")
    # carried when a save loads: quietly, with the gun
    m6 = load(src)
    m6.on_game_start()
    g.carry(lua.table_from(["wpn_e_pso"]))
    g.callbacks.load_state(lua.table())
    before = len(news())
    g.callbacks.actor_on_first_update(None)
    check(m6.is_found("pso") and m6.is_found("wpn_e") and len(news()) == before
          and m6.describe(m6.found_at("pso")).startswith("already in your pack"),
          "what is on a gun carried when a save loads is found quietly: %s" % m6.describe(m6.found_at("pso")))
    # seen on a gun in a window, with the option on
    m7 = load(src)
    m7.on_game_start()
    g.carry(lua.table_from([]))
    g.callbacks.load_state(lua.table())
    g.callbacks.actor_on_first_update(None)
    g.seen_on = True
    gui.mode, gui.npc_is_box, gui.partner = "loot", True, g.box2
    g.show("UIInventory")
    check(m7.is_found("pso") and news()[-1] == "New in Arsenal: E, PSO-1"
          and m7.describe(m7.found_at("pso")) == "seen in a stash" + place,
          "an attachment seen on a gun in a window counts with it: %s" % news()[-1])

    def fresh_module():
        mod = load(src)
        mod.on_game_start()
        g.carry(lua.table_from([]))
        g.callbacks.load_state(lua.table())
        g.callbacks.actor_on_first_update(None)
        g.TIMERS = lua.table_from({})
        return mod

    # a trader's stock as the trade window lists it, in its own cells: not the gun in his slot, nor
    # what his trade keeps off the counter (in his ruck still), which the window leaves out; without
    # those cells, his ruck, never his slots
    m8 = fresh_module()
    g.seen_on = True
    lua.execute("""
owl = holding({ "wpn_a", "wpn_b" }, false, { "wpn_a", "wpn_b" })
owl.stalker = true
owl.character_name = function() return "Owl" end
owl.character_community = function() return "stalker" end
beard = holding({ "wpn_c", "wpn_d" }, false, { "wpn_d" })
beard.stalker = true
beard.character_name = function() return "Beard" end
beard.character_community = function() return "stalker" end
""")
    gui.mode, gui.npc_is_box, gui.partner = "trade", False, g.owl
    gui.CC = g.cells(lua.eval('{ npc_trade_bag = { { 901, "wpn_b" } }, npc_trade = {} }'))
    g.show("UIInventory")
    check(m8.is_found("wpn_b") and not m8.is_found("wpn_a")
          and m8.describe(m8.found_at("wpn_b")) == "seen in Owl's stock" + place,
          "a trader's stock as the window lists it: not what it leaves out: %s %s"
          % (m8.is_found("wpn_a"), m8.describe(m8.found_at("wpn_b"))))
    gui.CC, gui.partner = None, g.beard
    g.show("UIInventory")
    check(m8.is_found("wpn_d") and not m8.is_found("wpn_c"),
          "a trade window without cells of its own: his ruck, not his slots: %s" % m8.is_found("wpn_c"))

    # a stash fills as it opens (treasure_manager spawns its loot), after its window says it is open:
    # looked into again a moment later, while the window is still open on it, what came counts, in
    # one line; a window closed by then, or open on another box, counts nothing more
    m9 = fresh_module()
    g.shown = True
    lua.execute("""
fresh = holding({ "wpn_a" }, true)
shut = holding({}, true)
other = holding({}, true)
moved = holding({ "wpn_e" }, true)
treasure_manager = { caches = { [fresh.id()] = true, [shut.id()] = true, [other.id()] = false, [moved.id()] = "x" } }
""")
    gui.mode, gui.npc_is_box, gui.partner = "loot", True, g.fresh
    before = len(news())
    g.show("UIInventory")
    g.fresh.list[2] = "wpn_b"
    g.run_timers()
    check(m9.is_found("wpn_a") and m9.is_found("wpn_b") and news()[before:] == ["New in Arsenal: A", "New in Arsenal: B"]
          and m9.describe(m9.found_at("wpn_b")) == "seen in a stash" + place,
          "a stash looked into again a moment later: what spawned after it opened counts, once: %s" % news()[before:])
    gui.partner = g.shut
    g.show("UIInventory")
    g.shut.list[1] = "wpn_c"
    g.shown = False
    g.run_timers()
    g.shown = True
    gui.partner = g.other
    g.show("UIInventory")
    g.other.list[1] = "wpn_d"
    gui.partner = g.moved
    g.run_timers()
    check(not m9.is_found("wpn_c") and not m9.is_found("wpn_d") and not m9.is_found("wpn_e"),
          "a window closed by then, or open on another box, counts nothing more: %s %s %s"
          % (m9.is_found("wpn_c"), m9.is_found("wpn_d"), m9.is_found("wpn_e")))

    # a box of the player's own (a dropped backpack, a furniture stash: none of treasure_manager's
    # stashes) counts nothing, then or later; without treasure_manager's list, the boxes item_backpack
    # and Hideout Furniture record as his (player_created_stashes, workshop_stashes)
    m10 = fresh_module()
    lua.execute('mine = holding({ "wpn_a" }, true)')
    gui.partner = g.mine
    g.show("UIInventory")
    check(not m10.is_found("wpn_a") and len(g.TIMERS) == 0, "a box of the player's own counts nothing, then or later")
    lua.execute("""
treasure_manager = nil
pack, bench, found_box = holding({ "wpn_a" }, true), holding({ "wpn_b" }, true), holding({ "wpn_c" }, true)
alife_storage_manager = { get_state = function() return {
    player_created_stashes = { [pack.id()] = "inv_backpack" }, workshop_stashes = { [77] = bench.id() } } end }
""")
    for b in ("pack", "bench", "found_box"):
        gui.partner = g[b]
        g.show("UIInventory")
    got = [m10.is_found(s) for s in ("wpn_a", "wpn_b", "wpn_c")]
    check(got == [False, False, True],
          "without treasure_manager's list: not a backpack or furniture stash of his, a box else: %s" % got)
    lua.execute("alife_storage_manager = nil")

    # a live companion: what is taken from his pack he hands over (given to you by him); what his
    # window shows is no body, stash or stock, and does not count by being seen
    m11 = fresh_module()
    g.seen_on, g.shown = False, True
    lua.execute("""
wolf = holding({ "wpn_c", "wpn_d" }, false)
wolf.stalker = true
wolf.alive = function() return true end
wolf.character_name = function() return "Wolf" end
wolf.character_community = function() return "stalker" end
""")
    gui.mode, gui.npc_is_box, gui.partner = "loot", False, g.wolf
    g.take("wpn_c")
    w11 = m11.describe(m11.found_at("wpn_c"))
    g.seen_on, g.shown = True, False
    g.show("UIInventory")
    check(w11 == "given to you by Wolf" + place and not m11.is_found("wpn_d"),
          "a companion's pack: what is taken from it, given by him; what it shows does not count: %s %s"
          % (w11, m11.is_found("wpn_d")))
    gui.CC, g.seen_on = None, False
    lua.execute("treasure_manager = nil")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
