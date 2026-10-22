"""Run arsenal_pages.script and z_arsenal_mac.script under LuaJIT against stand-ins for Modded
Exes' tab registry (pda_dynamic_tabs), Mod App Creator, MCM's option and the PDA, and check the
catalog's way in: its tile in MAC's launcher, or a PDA tab of its own. The tab comes only in play,
a second after the first update (one added during a load crashed the game, 2026-10-11), never
while the scripts start or the game loads; with MAC only when MCM asks for it, in place of the
tile; without MAC always; without the registry never. Changing the option adds or takes away the
tab once the game runs again, and the tile the other way round, once however often it changes; a
tab taken away while it was the PDA's last section sends the PDA to Tasks. The catalog opens in
the tab's section while there is one, and in its own for the tile and other mods; Back goes to
the launcher only while the tile is there. A page that fails to build, a registry that refuses or
a PDA that cannot be read leaves the game running and the catalog in reach.

    python test_tab.py            the real scripts
    python test_tab.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "..", "gamedata")
PAGES = io.open(os.path.join(GD, "scripts", "arsenal_pages.script"), encoding="latin-1").read()
MAC = io.open(os.path.join(GD, "scripts", "z_arsenal_mac.script"), encoding="latin-1").read()

STUBS = r"""
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
callbacks = {}
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
-- time events as _g.script keeps them: one per pair of ids, run once its time has come (seconds
-- of play, as time_global counts them), dropped once it returns true
NOW = 0
timers = {}
function CreateTimeEvent(ev_id, act_id, delay, fn, ...)
    local id = ev_id .. "/" .. act_id
    if not timers[id] then timers[id] = { at = NOW + delay, fn = fn, args = { ... } } end
end
function play(seconds)
    NOW = NOW + seconds
    for id, ev in pairs(timers) do
        if NOW >= ev.at and ev.fn(unpack(ev.args)) then timers[id] = nil end
    end
end
function pending()
    local n = 0
    for _ in pairs(timers) do n = n + 1 end
    return n
end
-- the engine's AddTab, and Modded Exes' registry: what reached it, in order, and each tab's page
CUITabControl = { AddTab = function() end }
calls = {}
getters = {}
SEQ = 0
REFUSE = false
pda_dynamic_tabs = {
    register = function(caption, getter, after)
        if REFUSE then error("no tab bar") end
        SEQ = SEQ + 1
        local id = "ept_dynamic_" .. SEQ
        calls[#calls + 1] = "register " .. tostring(caption) .. (after and (" after " .. after) or "")
        getters[id] = getter
        return id
    end,
    unregister = function(id)
        calls[#calls + 1] = "unregister " .. id
        getters[id] = nil
        return true
    end,
}
-- Mod App Creator
added, removed = {}, {}
mac_mcm = {
    add_app = function(id, data) added[id] = data end,
    remove_app = function(id) removed[#removed + 1] = id; added[id] = nil end,
}
-- MCM's option
PDA_TAB = false
arsenal_mcm = { pda_tab = function() return PDA_TAB end }
-- the PDA: the section it showed last, and what was opened in it
ACTIVE = "eptTasks"
opened = {}
PDA_FAILS = false
PDA = {
    GetActiveSection = function(self) if PDA_FAILS then error("no PDA yet") end return ACTIVE end,
    SetActiveSubdialog = function(self, s) opened[#opened + 1] = s; ACTIVE = s end,
}
ActorMenu = { get_pda_menu = function() return PDA end }
-- the pages
CATALOG_FAILS = false
ui_arsenal = {
    get_ui = function() if CATALOG_FAILS then error("boom") end return "catalog page" end,
    add_action = function() end,
    flat_window = function() end,
}
ui_arsenal_workbench = { get_ui = function() return "workbench page" end, flat_window = function() end }
ui_arsenal_compare = { get_ui = function() return "compare page" end, flat_window = function() end }
arsenal_workbench = { plannable = function() return true end }
-- the PDA's own sections, below every wrap
pda = { set_active_subdialog = function(section) return "pda:" .. section end }
"""

MUTANTS = {
    # when the tab comes
    "tab_at_first_update": ('RegisterScriptCallback("actor_on_first_update", function() sync_soon(1) end)',
                            'RegisterScriptCallback("actor_on_first_update", function() sync() end)'),
    "tab_at_game_start": ('    RegisterScriptCallback("on_game_load", route)\n',
                          '    sync()\n    RegisterScriptCallback("on_game_load", route)\n'),
    "tab_no_delay": ("function() sync_soon(1) end", "function() sync_soon(0) end"),
    "no_option_resync": ('    RegisterScriptCallback("on_option_change", function() sync_soon(0) end)\n', ""),
    "sync_unguarded": ('        local ok, err = pcall(sync)\n        if not ok then say("the PDA tab: " .. tostring(err)) end\n',
                       "        sync()\n"),
    "sync_repeats": ("        return true\n    end)\nend", "        return false\n    end)\nend"),
    # whether it comes
    "tab_ignores_option": ("(arsenal_mcm.pda_tab() or not (mac_mcm and mac_mcm.add_app))", "(not (mac_mcm and mac_mcm.add_app))"),
    "tab_needs_option": ("(arsenal_mcm.pda_tab() or not (mac_mcm and mac_mcm.add_app))", "(arsenal_mcm.pda_tab())"),
    "tab_unsupported_tried": ("    return tab_supported() and (", "    return ("),
    "tab_addtab_unchecked": ("\n        and CUITabControl ~= nil and CUITabControl.AddTab ~= nil", ""),
    "register_twice": ("    if want and not tab_section then", "    if want then"),
    "tab_caption": ('local TAB_CAPTION = "st_arsenal_title"', 'local TAB_CAPTION = "arsenal"'),
    "tab_anchored": ('pcall(pda_dynamic_tabs.register, TAB_CAPTION, function() return page_ui("catalog") end)',
                     'pcall(pda_dynamic_tabs.register, TAB_CAPTION, function() return page_ui("catalog") end, "eptTasks")'),
    "tab_getter_unsafe": ('function() return page_ui("catalog") end)', 'function() return script_of("catalog").get_ui() end)'),
    # the tile, the other way round
    "tab_tile_kept": ("            tab_section = id\n            z_arsenal_mac.remove_tile()\n", "            tab_section = id\n"),
    "tab_refused_no_tile": ('            say("no PDA tab of its own: " .. tostring(id))\n            z_arsenal_mac.add_tile()\n',
                            '            say("no PDA tab of its own: " .. tostring(id))\n'),
    "tab_refused_kept": ('        if ok and type(id) == "string" then', "        if true then"),
    "untab_no_tile": ('        if not ok then say("the PDA tab could not be taken away: " .. tostring(err)) end\n        z_arsenal_mac.add_tile()\n',
                      '        if not ok then say("the PDA tab could not be taken away: " .. tostring(err)) end\n'),
    "untab_kept": ("        local ok, err = pcall(pda_dynamic_tabs.unregister, id)\n", "        local ok, err = true\n"),
    "untab_stranded": ('        if pda_menu and pda_menu:GetActiveSection() == id then pda_menu:SetActiveSubdialog("eptTasks") end\n', ""),
    "untab_always_tasks": ("pda_menu:GetActiveSection() == id then", "true then"),
    # where the catalog opens, and Back
    "section_fixed": ("    return tab_section or PAGES.catalog.tab", "    return PAGES.catalog.tab"),
    "open_ignores_tab": ('page == "catalog" and catalog_section() or PAGES[page].tab', "PAGES[page].tab"),
    "back_always": ("    return z_arsenal_mac.has_tile() == true", "    return true"),
    "router_no_catalog": ('(section == PAGES.catalog.tab and "catalog") or ', ""),
}


def main():
    pages_src, mac_src = PAGES, MAC
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        assert pages_src.count(old) == 1, old
        pages_src = pages_src.replace(old, new)
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    def attempt(fn, *args):
        """a call's result, or the error it raised"""
        try:
            return fn(*args)
        except L.LuaError as e:
            return "error: %s" % str(e).splitlines()[0]

    def game(mac=True, registry=True, addtab=True, option=False):
        """a load: the Lua state anew, the scripts started, the level loaded, the first update;
        returns the runtime, its globals, the two scripts, and what reached the registry by each
        of those three steps"""
        lua = L.LuaRuntime(unpack_returned_tuples=True)
        lua.execute(STUBS)
        g = lua.globals()
        if not mac:
            lua.execute("mac_mcm = nil")
        if not registry:
            lua.execute("pda_dynamic_tabs = nil")
        if not addtab:
            lua.execute("CUITabControl = {}")
        g.PDA_TAB = option
        load = lua.eval("function(name, src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                        "setfenv(f, env); _G[name] = env; f(); return env end")
        pages = load("arsenal_pages", pages_src)
        tile = load("z_arsenal_mac", mac_src)
        seen = []
        pages.on_game_start()
        tile.on_game_start()
        seen.append(list(g.calls.values()))
        g.callbacks.on_game_load()
        seen.append(list(g.calls.values()))
        g.callbacks.actor_on_first_update()
        seen.append(list(g.calls.values()))
        return lua, g, pages, tile, seen

    calls = lambda g: list(g.calls.values())

    def option_change(g):
        """MCM's options changed: the callback the scripts registered for it, said once if none"""
        fn = g.callbacks.on_option_change
        if fn is None:
            if not g.unheard:
                g.unheard = True
                check(False, "a callback hears MCM's options change")
            return
        fn()
    last = lambda g: g.opened[len(g.opened)] if len(g.opened) else None

    # MAC and the option off: the tile, no tab, now or later
    lua, g, pages, tile, seen = game()
    g.play(5)
    check(seen == [[], [], []] and calls(g) == [] and g.added.arsenal is not None and tile.has_tile() is True,
          "MAC, the option off: the tile, and no tab: %s %s" % (seen, calls(g)))
    pages.open("catalog")
    check(pages.catalog_section() == "eptArsenal" and last(g) == "eptArsenal" and pages.back_to_launcher() is True,
          "the catalog in its own section; Back to the launcher: %s" % last(g))

    # MAC and the option on: nothing while the scripts start, the game loads or first updates;
    # the tab a second into play, once; no tile at all
    lua, g, pages, tile, seen = game(option=True)
    g.play(0.5)
    half = calls(g)
    g.play(0.5)
    check(seen == [[], [], []] and half == [] and calls(g) == ["register st_arsenal_title"] and g.pending() == 0,
          "the option on: nothing during the load, the tab a second into play, once, after the others: %s %s %s"
          % (seen, half, calls(g)))
    check(g.added.arsenal is None and tile.has_tile() is False and list(g.removed.values()) == [],
          "no tile: none added as the game started, none to take away")
    sec = pages.catalog_section()
    pages.open("catalog")
    check(sec == "ept_dynamic_1" and last(g) == sec and pages.back_to_launcher() is False,
          "the catalog opens in the tab's section; no Back to a launcher: %s %s" % (sec, last(g)))
    getter = g.getters[sec]
    shows = attempt(getter) if getter else None
    g.CATALOG_FAILS = True
    n = len(g.logs)
    failed = attempt(getter) if getter else "no getter"
    g.CATALOG_FAILS = False
    check(shows == "catalog page" and failed is None and len(g.logs) == n + 1,
          "the tab shows the catalog; one that fails to build shows nothing, logged, the PDA up: %s %s"
          % (shows, failed))
    # the router: the catalog's own section, for a tile and other mods, and the PDA's sections down
    r = (g.pda.set_active_subdialog("eptArsenal"), g.pda.set_active_subdialog("eptWorkbench"),
         g.pda.set_active_subdialog("eptMap"))
    check(r == ("catalog page", "workbench page", "pda:eptMap"),
          "the catalog's own section is still its page, the PDA's pass down: %s" % (r,))

    # the option off, the PDA last on the tab: once the game runs again the tab goes, the tile
    # comes back, and the PDA goes to Tasks rather than a section nothing answers
    g.ACTIVE = sec
    g.PDA_TAB = False
    option_change(g)
    paused = calls(g)
    g.play(0.01)
    check(paused == ["register st_arsenal_title"]
          and calls(g) == ["register st_arsenal_title", "unregister ept_dynamic_1"]
          and g.added.arsenal is not None and tile.has_tile() is True and pages.catalog_section() == "eptArsenal"
          and pages.back_to_launcher() is True and last(g) == "eptTasks",
          "the option off: in play the tab goes, the tile comes back, the PDA off the gone tab: %s %s %s"
          % (paused, calls(g), last(g)))
    # on again, changed twice before the game runs: one new tab, the tile taken away
    g.PDA_TAB = True
    option_change(g)
    option_change(g)
    g.play(0.01)
    check(calls(g)[2:] == ["register st_arsenal_title"] and list(g.removed.values()) == ["arsenal"]
          and tile.has_tile() is False and pages.catalog_section() == "ept_dynamic_2",
          "on again, changed twice: one new tab, the tile taken away: %s %s" % (calls(g)[2:], list(g.removed.values())))
    # an option change that changes nothing here: nothing happens
    option_change(g)
    g.play(0.01)
    check(calls(g)[2:] == ["register st_arsenal_title"], "a change that leaves the tab as it is: nothing: %s" % calls(g)[2:])
    # off while the PDA was last elsewhere: it stays there
    g.ACTIVE = "eptMap"
    n = len(g.opened)
    g.PDA_TAB = False
    option_change(g)
    g.play(0.01)
    check(calls(g)[-1] == "unregister ept_dynamic_2" and len(g.opened) == n and g.ACTIVE == "eptMap",
          "off while the PDA was elsewhere: it stays there: %s" % g.ACTIVE)

    # without MAC: the tab whatever the option, no tile, no Back to a launcher
    for option in (False, True):
        lua, g, pages, tile, seen = game(mac=False, option=option)
        g.play(1)
        check(seen == [[], [], []] and calls(g) == ["register st_arsenal_title"] and tile.has_tile() is False
              and pages.back_to_launcher() is False and pages.catalog_section() == "ept_dynamic_1",
              "without MAC, the option %s: the tab in play, no tile: %s" % ("on" if option else "off", calls(g)))

    # without the registry, or without AddTab: the tile, the option on or not, nothing logged
    for what in ("registry", "addtab"):
        lua, g, pages, tile, seen = game(option=True, registry=(what != "registry"), addtab=(what != "addtab"))
        g.play(1)
        check(calls(g) == [] and g.added.arsenal is not None and tile.has_tile() is True
              and pages.tab_supported() is False and pages.wants_tab() is False
              and pages.catalog_section() == "eptArsenal" and len(g.logs) == 0,
              "without the %s: the tile though the option is on, nothing logged: %s %s"
              % ("registry" if what == "registry" else "tab control's AddTab", calls(g), list(g.logs.values())))

    # a registry that refuses: the tile instead, logged once
    lua, g, pages, tile, seen = game(option=True)
    g.REFUSE = True
    g.play(1)
    check(g.added.arsenal is not None and tile.has_tile() is True and pages.catalog_section() == "eptArsenal"
          and len(g.logs) == 1 and "no PDA tab" in g.logs[1],
          "a registry that refuses: the tile instead, logged once: %s" % list(g.logs.values()))

    # a PDA that cannot be read as the tab goes: the tile back all the same, logged, the event done
    lua, g, pages, tile, seen = game(option=True)
    g.play(1)
    g.PDA_FAILS = True
    g.PDA_TAB = False
    option_change(g)
    err = attempt(g.play, 0.01)
    check(err is None and g.pending() == 0 and tile.has_tile() is True and len(g.logs) == 1 and "PDA tab" in g.logs[1],
          "a PDA that cannot be read: the tile back, logged, the game on: %s %s" % (err, list(g.logs.values())))

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
