"""Run arsenal_collection.script under LuaJIT against stubs (the engine, arsenal_data), and
check the collector: a variant is found once, a combination counts as its gun, the load-time
scan is quiet, later finds send news (a model's second variant too), a model counts as found
once, from its earliest variant, the set survives a save and a load, and finds kept under
sections that now share a variant move to it, the earliest kept.

    python test_collection.py            the real script
    python test_collection.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_collection.script"), encoding="latin-1").read()

STUBS = r"""
news = {}
callbacks = {}
clock = { 2012, 5, 14, 9, 30 }
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
game = {
    translate_string = function(k) return ({ st_arsenal_new_entry = "New in Arsenal: %s", st_arsenal_title = "Arsenal",
        st_arsenal_and_more = "%s and %s more" })[k] or k end,
    get_game_time = function() return { get = function() return unpack(clock) end } end,
}
level = { name = function() return "l01_escape" end }
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
    variant_for = function(sec) return by_var[parent[sec] or sec] end,
    variant_of = function(sec) return by_var[sec] end,
    get = function(sec) local v = by_var[sec]; return v and v.entry end,
}
local function item(sec) return { section = function() return sec end } end
inventory = { item("wpn_pm"), item("ammo_545") }
db = { actor = {
    give_game_news = function(self, cap, text) news[#news + 1] = text end,
    iterate_inventory = function(self, fn) for _, o in ipairs(inventory) do fn(self, o) end end,
} }
function take(sec) callbacks.actor_on_item_take(item(sec)) end
-- the option to count guns seen, and the inventory window: its mode and partner, as ui_inventory
-- keeps them; a box holds a Fort-17, an SKS and ammo; a trader five guns and a PM
seen_on = false
arsenal_mcm = { count_seen = function() return seen_on end }
-- what the player knows (arsenal_intel): told of every find
told = {}
arsenal_intel = { found = function(sec, live) told[#told + 1] = sec .. (live and " in play" or "") end }
for _, s in ipairs({ "a", "b", "c", "d", "e" }) do
    local v = { sec = "wpn_" .. s, name = s:upper() }
    model(s:upper(), { v })
    by_var[v.sec] = v
end
local function holding(list, box)
    local p = {}
    local function each(self, fn, arg) for _, s in ipairs(list) do fn(arg, item(s)) end end
    local function none() end
    p.iterate_inventory_box = box and each or none
    p.iterate_inventory = box and none or each
    return p
end
box = holding({ "wpn_fort17", "wpn_sks", "ammo_545" }, true)
trader = holding({ "wpn_a", "wpn_b", "wpn_c", "wpn_d", "wpn_e", "wpn_pm" }, false)
ui_inventory = { GUI = { mode = "loot", npc_is_box = true, partner = box,
    GetPartner = function(self) return self.partner end } }
function show(name) if callbacks.GUI_on_show then callbacks.GUI_on_show(name) end end
"""

MUTANTS = {
    "quiet_scan": ("if obj then\n            mark(obj:section(), true)", "if obj then\n            mark(obj:section(), false)"),
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
    "seen_quiet": ("local v = obj and mark(obj:section(), true)", "local v = obj and mark(obj:section(), false)"),
    "seen_register": ('    RegisterScriptCallback("GUI_on_show", GUI_on_show)\n', ""),
}


def main():
    src = SRC
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS)
    load = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); f(); return env end")
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

    saved = lua.table()
    g.callbacks.save_state(saved)
    m2 = load(src)
    m2.on_game_start()
    g.callbacks.load_state(saved)
    check(m2.is_found("wpn_ak74") and m2.is_found("wpn_sks_b") and not m2.is_found("wpn_toz34"),
          "the set survives a save and a load")

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
    gui = g.ui_inventory.GUI
    gui.mode, gui.npc_is_box, gui.partner = "trade", False, g.trader
    g.show("UIInventory")
    check(news()[-1] == "New in Arsenal: A, B, C and 2 more" and m4.is_found("wpn_e"),
          "a trader's stock counts too; three names, then how many more: %s" % news()[-1])
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
