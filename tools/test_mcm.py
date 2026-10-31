"""Run arsenal_mcm.script under LuaJIT against stubs of MCM and ui_arsenal, and check the key:
its MCM option has a real default (unbound, -1; a nil default once crashed another mod's
startup), an unbound key or a missing MCM reads as no key, and only the bound key opens the
flat window, while the PDA works (arsenal_pages.pda_works: Fatal Error's PDA); else the HUD says
why not. Each press goes through the engine's order (engine_press): the scripts' callback, then
the window on top, then the next update. A window opened during the press got that same press
and closed on the key, so nothing showed; a test that only calls the callback passes on that.

    python test_mcm.py            the real script
    python test_mcm.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_mcm.script"), encoding="latin-1").read()
# the version line as the script has it now, so the mutant below names it whatever the release
VERSION_LINE = re.search(r'(?m)^VERSION = "[^"]+"', SRC).group(0)

STUBS = r"""
callbacks = {}
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
options = {}
-- MCM's modifier helpers: HELD is the modifier down with the key (0 none, 1 Shift, 2 Ctrl, 3 Alt);
-- get_mod_key(0) is true only with none held, as MCM's is
HELD = 0
ui_mcm = { get = function(path) return options[path] end,
           set = function(path, v) options[path] = v end,
           kb_mod_radio = "radio_h",
           get_mod_key = function(v) return HELD == (v or 0) end }
-- the PDA: what reached it, and the log
news = {}
logged = {}
db = { actor = { give_game_news = function(self, title, text, icon) news[#news + 1] = { title, text, icon } end } }
function printf(fmt, ...) logged[#logged + 1] = string.format(fmt, ...) end
opened = 0
shown = nil
closed = 0
-- an open flat page: its Close hides it, as HideDialog does
unloaded = 0
local function window() return { Close = function() shown = nil; unloaded = unloaded + 1 end } end
ui_arsenal = {
    open_flat = function() opened = opened + 1; shown = "catalog" end,
    flat_window = function() if shown == "catalog" then return window() end end,
}
ui_arsenal_workbench = { flat_window = function() if shown == "workbench" then return window() end end }
ui_arsenal_compare = { flat_window = function() if shown == "compare" then return window() end end }
timers = {}
-- as _g.script: an event already queued under the same ids is kept, not replaced
function CreateTimeEvent(ev_id, act_id, delay, fn, ...)
    local id = ev_id .. "/" .. act_id
    if not timers[id] then timers[id] = { fn = fn, args = { ... } } end
end
function tick()
    for id, t in pairs(timers) do
        if t.fn(unpack(t.args)) then timers[id] = nil end
    end
end
-- one key press in the engine's order (Level_input.cpp): the scripts' callback, then the window
-- on top, if a page is open flat (its OnKeyboard closes it on Escape or the key: ui_arsenal,
-- ui_arsenal_workbench), then the next update, which runs the time events
function engine_press(key)
    if callbacks.on_key_press then callbacks.on_key_press(key) end
    if shown and (key == 1 or key == options["arsenal/flat_key"]) then
        shown = nil
        closed = closed + 1
    end
    tick()
end
PDA_WORKS = true
-- TABS: whether the engine has Modded Exes' tab registry ("boom": the question fails)
TABS = false
arsenal_pages = { pda_works = function() return PDA_WORKS end,
                  tab_supported = function() if TABS == "boom" then error("no answer") end return TABS end }
game = { translate_string = function(k) return k == "st_arsenal_credit" and "Arsenal v%s by %s" or ("T:" .. k) end }
msgs = {}
actor_menu = { set_msg = function(typ, msg, tm) msgs[#msgs + 1] = { typ, msg, tm } end }
"""

MUTANTS = {
    "def_nil": ('{ id = "flat_key", type = "key_bind", val = 2, def = -1 }',
                '{ id = "flat_key", type = "key_bind", val = 2, def = nil }'),
    "unbound": ("return (k and k >= 0) and k or nil", "return k"),
    "no_callback": ('RegisterScriptCallback("on_key_press", on_key_press)', "-- not registered"),
    "any_key": ("if not (k and key == k) then return end", "if not k then return end"),
    "seen_def": ('{ id = "count_seen", type = "check", val = 1, def = false }', '{ id = "count_seen", type = "check", val = 1 }'),
    "seen_any": ('pcall(opt, "arsenal/count_seen")\n    return ok and v == true',
                 'pcall(opt, "arsenal/count_seen")\n    return ok'),
    "jail_def": ('{ id = "jailbreak", type = "check", val = 1, def = false }', '{ id = "jailbreak", type = "check", val = 1 }'),
    "jail_any": ('pcall(opt, "arsenal/jailbreak")\n    return (ok and v == true) or false',
                 'pcall(opt, "arsenal/jailbreak")\n    return ok'),
    # a read through a closure made for it, as 1.8.4 read every option
    "read_closure": ('    local ok, v = pcall(opt, "arsenal/jailbreak")',
                     '    local ok, v = pcall(function() return ui_mcm and ui_mcm.get("arsenal/jailbreak") end)'),
    "pda_ignored": ("if not arsenal_pages.pda_works() then", "if false then"),
    "pda_silent": ('        actor_menu.set_msg(1, game.translate_string("st_arsenal_pda_down"), 3)\n', ""),
    "during_press": ('    CreateTimeEvent("arsenal_mcm", "open_flat", 0, function()\n'
                     "        ui_arsenal.open_flat()\n"
                     "        return true\n"
                     "    end)\n", "    ui_arsenal.open_flat()\n"),
    "reopens": ("    if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() or ui_arsenal_compare.flat_window() then return end\n", ""),
    "workbench_ignored": ("if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() or ui_arsenal_compare.flat_window() then",
                          "if ui_arsenal.flat_window() or ui_arsenal_compare.flat_window() then"),
    "compare_ignored": ("if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() or ui_arsenal_compare.flat_window() then",
                        "if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() then"),
    "kept_on_load": ('    RegisterScriptCallback("actor_on_net_destroy", close_flat)\n', ""),
    "load_skips_compare": ("{ ui_arsenal, ui_arsenal_workbench, ui_arsenal_compare }", "{ ui_arsenal, ui_arsenal_workbench }"),
    "gunsmith_def": ('{ id = "gunsmith", type = "check", val = 1, def = true }', '{ id = "gunsmith", type = "check", val = 1 }'),
    "gunsmith_dropped": ('            { id = "gunsmith", type = "check", val = 1, def = true },\n', ""),
    "gunsmith_off_unset": ('pcall(opt, "arsenal/gunsmith")\n    return not (ok and v == false)',
                           'pcall(opt, "arsenal/gunsmith")\n    return ok and v == true'),
    "gunsmith_always": ('pcall(opt, "arsenal/gunsmith")\n    return not (ok and v == false)',
                        'pcall(opt, "arsenal/gunsmith")\n    return true'),
    "news_def": ('{ id = "news", type = "check", val = 1, def = true }', '{ id = "news", type = "check", val = 1 }'),
    "sources_def": ('{ id = "sources", type = "check", val = 1, def = false }', '{ id = "sources", type = "check", val = 1 }'),
    "sources_dropped": ('            { id = "sources", type = "check", val = 1, def = false },\n', ""),
    "sources_any": ('pcall(opt, "arsenal/sources")\n    return (ok and v == true) or false',
                    'pcall(opt, "arsenal/sources")\n    return ok'),
    "news_off_unset": ('pcall(opt, "arsenal/news")\n    return not (ok and v == false)',
                       'pcall(opt, "arsenal/news")\n    return ok and v == true'),
    "news_dropped": ('            { id = "news", type = "check", val = 1, def = true },\n', ""),
    "set_inverted": ('ui_mcm.set("arsenal/news", on and true or false)', 'ui_mcm.set("arsenal/news", not on)'),
    "tell_ignores": ("    if not news() then\n", "    if false then\n"),
    "tell_unlogged": ('        printf("[arsenal] PDA (silenced): %s", tostring(text))\n', ""),
    "credit_no_version": ("game.translate_string(\"st_arsenal_credit\"), VERSION, AUTHOR)",
                          "game.translate_string(\"st_arsenal_credit\"), \"\", AUTHOR)"),
    "version_behind": (VERSION_LINE, 'VERSION = "0.0.1"'),
    "mod_ignored": ("    if not mod_held() then return end\n", ""),
    "mod_none_strict": ("    if m == 0 then return true end\n", ""),
    "mod_def": ("val = 2, def = 0,\n              hint", "val = 2,\n              hint"),
    "mod_old_mcm": ("return not ok or held == true", "return ok and held == true"),
    # the PDA tab option
    "tab_always": ("    if tab_choice() then\n", "    if true then\n"),
    "tab_no_mac": ("return mac_mcm ~= nil and mac_mcm.add_app ~= nil and arsenal_pages.tab_supported()",
                   "return arsenal_pages.tab_supported()"),
    "tab_no_registry": ("return mac_mcm ~= nil and mac_mcm.add_app ~= nil and arsenal_pages.tab_supported()",
                        "return mac_mcm ~= nil and mac_mcm.add_app ~= nil"),
    "tab_choice_unguarded": ("    local ok, v = pcall(function() return mac_mcm ~= nil and mac_mcm.add_app ~= nil and arsenal_pages.tab_supported() end)",
                             "    local ok, v = true, mac_mcm ~= nil and mac_mcm.add_app ~= nil and arsenal_pages.tab_supported()"),
    "tab_at_end": ("table.insert(page.gr, 4, {", "table.insert(page.gr, {"),
    "tab_def": ('{ id = "pda_tab", type = "check", val = 1, def = false }', '{ id = "pda_tab", type = "check", val = 1 }'),
    "tab_any": ('pcall(opt, "arsenal/pda_tab")\n    return (ok and v == true) or false',
                'pcall(opt, "arsenal/pda_tab")\n    return ok'),
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
    m = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                 "setfenv(f, env); f(); return env end")(src)
    g = lua.globals()
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    opts = m.on_mcm_load()
    key = [o for o in opts.gr.values() if o.type == "key_bind"]
    check(opts.id == "arsenal" and len(key) == 1 and key[0].id == "flat_key", "one key option, arsenal/flat_key")
    check(key and key[0]["def"] == -1, "its default is unbound, -1, not nil: %s" % (key and key[0]["def"],))

    seen = [o for o in opts.gr.values() if o.id == "count_seen"]
    check(len(seen) == 1 and seen[0].type == "check" and seen[0]["def"] is False,
          "counting guns seen is a check box, off by default (false, not nil)")
    check(m.count_seen() is False, "off while the option is unset")
    g.options["arsenal/count_seen"] = True
    check(m.count_seen() is True, "on once the player turns it on")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.count_seen() is False, "off without MCM")
    g.ui_mcm = mcm
    jail = [o for o in opts.gr.values() if o.id == "jailbreak"]
    check(len(jail) == 1 and jail[0].type == "check" and jail[0]["def"] is False,
          "the jailbreak is a check box, off by default (false, not nil): Arsenal starts immersive")
    check(m.jailbreak() is False, "off while the option is unset")
    g.options["arsenal/jailbreak"] = True
    check(m.jailbreak() is True, "on once the player turns it on")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.jailbreak() is False, "off without MCM")
    g.ui_mcm = mcm
    # a read leaves nothing for the collector: the pages read options thousands of times as they
    # fill (measured with the collector stopped and the JIT off)
    per_read = lua.eval("""function(m, n)
        if jit then jit.off() end
        m.jailbreak(); m.news(); m.flat_key(); m.count_seen(); m.gunsmith(); m.sources()
        collectgarbage("collect"); collectgarbage("stop")
        local before = collectgarbage("count")
        for _ = 1, n do m.jailbreak(); m.news(); m.flat_key(); m.count_seen(); m.gunsmith(); m.sources() end
        local kb = collectgarbage("count") - before
        collectgarbage("restart")
        if jit then jit.on() end
        return kb * 1024 / n
    end""")(m, 2000)
    check(per_read < 1, "reading the options makes no closure: %.1f bytes for six reads" % per_read)
    # "Show where items are defined": a check box, off by default, for modders
    src = [o for o in opts.gr.values() if o.id == "sources"]
    check(len(src) == 1 and src[0].type == "check" and src[0]["def"] is False,
          "Show where items are defined is a check box, off by default (false, not nil)")
    check(m.sources() is False, "off while the option is unset")
    g.options["arsenal/sources"] = True
    check(m.sources() is True, "on once the player turns it on")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.sources() is False, "off without MCM")
    g.ui_mcm = mcm
    # "Paid word of special guns": the talk where a technician sells word of a special gun
    # (arsenal_intel.gunsmith_ok); a check box, on by default, so a player who never opens MCM keeps it
    smith = [o for o in opts.gr.values() if o.id == "gunsmith"]
    check(len(smith) == 1 and smith[0].type == "check" and smith[0]["def"] is True,
          "Paid word of special guns is a check box, on by default (true, not nil)")
    check(m.gunsmith() is True, "on while the option is unset")
    g.options["arsenal/gunsmith"] = False
    check(m.gunsmith() is False, "off once the player turns it off")
    g.options["arsenal/gunsmith"] = True
    check(m.gunsmith() is True, "and on again")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.gunsmith() is True, "on without MCM")
    g.ui_mcm = mcm
    g.options["arsenal/gunsmith"] = None

    # "Arsenal tab in the PDA": offered only where there is a choice, with MAC and Modded Exes' tab
    # registry both (without MAC the tab is there anyway, without the registry the tile), after the
    # key and its modifier; a check box, off by default; the rest of the page whole either way
    def option_ids():
        try:
            return [o.id for o in m.on_mcm_load().gr.values()]
        except L.LuaError as e:
            return "error: %s" % str(e).splitlines()[0]
    plain = option_ids()
    g.TABS = True
    no_mac = option_ids()
    lua.execute("mac_mcm = { add_app = function() end }")
    both = option_ids()
    g.TABS = False
    no_registry = option_ids()
    g.TABS = "boom"
    failing = option_ids()
    g.TABS = True
    tab = [o for o in m.on_mcm_load().gr.values() if o.id == "pda_tab"]
    check(no_mac == plain and no_registry == plain and failing == plain
          and both == plain[:3] + ["pda_tab"] + plain[3:]
          and len(tab) == 1 and tab[0].type == "check" and tab[0]["def"] is False,
          "the PDA tab: offered with MAC and the registry only (a failing check offers none), after the "
          "key's modifier, off by default; the rest whole: %s | %s" % (both, failing))
    check(m.pda_tab() is False, "off while the option is unset")
    g.options["arsenal/pda_tab"] = True
    check(m.pda_tab() is True, "on once the player turns it on")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.pda_tab() is False, "off without MCM")
    g.ui_mcm = mcm
    g.options["arsenal/pda_tab"] = None

    # PDA notifications: on until silenced, here or by the Silence box on the pages (set_news);
    # every message goes through tell, which drops it while they are off and logs that it did
    news = [o for o in opts.gr.values() if o.id == "news"]
    check(len(news) == 1 and news[0].type == "check" and news[0]["def"] is True,
          "PDA notifications are a check box, on by default (true, not nil)")
    check(m.news() is True, "on while the option is unset")
    m.tell("New in Arsenal: PM")
    sent = [list(x.values()) for x in g.news.values()]
    check(sent == [["T:st_arsenal_title", "New in Arsenal: PM", "ui_inGame2_Predmet_poluchen"]],
          "a message goes to the PDA under Arsenal's name: %s" % sent)
    m.set_news(False)
    check(g.options["arsenal/news"] is False and m.news() is False,
          "Silence writes the option off: %s" % g.options["arsenal/news"])
    m.tell("New in Arsenal: AK-74")
    logged = list(g.logged.values())
    check(len(g.news) == 1 and logged == ["[arsenal] PDA (silenced): New in Arsenal: AK-74"],
          "silenced, nothing reaches the PDA, and the log says what was dropped: %d %s" % (len(g.news), logged))
    m.set_news(True)
    check(g.options["arsenal/news"] is True and m.news() is True, "and on again")
    mcm, g.ui_mcm = g.ui_mcm, None
    check(m.news() is True, "on without MCM")
    g.ui_mcm = mcm
    # the credit line: this release, by its author
    build = io.open(os.path.join(HERE, "build.py"), encoding="utf-8").read()
    want = re.search(r'(?m)^VERSION = "([^"]+)"', build).group(1)
    check(m.VERSION == want and m.AUTHOR == "Windwalker" and m.credit() == "Arsenal v%s by Windwalker" % want,
          "the pages name this release, %s (build.py's), by Windwalker: %s" % (want, m.credit()))
    # and nothing else talks to the PDA itself
    scripts = os.path.join(HERE, "..", "gamedata", "scripts")
    direct = [f for f in sorted(os.listdir(scripts)) if f != "arsenal_mcm.script"
              and "give_game_news" in io.open(os.path.join(scripts, f), encoding="latin-1").read()]
    check(not direct, "every PDA message goes through arsenal_mcm.tell: %s" % (direct or "yes"))

    m.on_game_start()
    press = g.callbacks.on_key_press
    check(press is not None, "the key press callback is registered")
    g.options["arsenal/flat_key"] = -1
    check(m.flat_key() is None, "an unbound key reads as no key")
    g.engine_press(30)
    check(g.opened == 0, "with no key bound, no key opens the window")
    g.options["arsenal/flat_key"] = 65
    check(m.flat_key() == 65, "a bound key: %s" % m.flat_key())
    g.engine_press(30)
    check(g.opened == 0, "another key opens nothing: %d" % g.opened)
    g.engine_press(65)
    check(g.opened == 1 and g.shown == "catalog",
          "the key opens the window, still open once the press is through: %d %s" % (g.opened, g.shown))
    g.engine_press(65)
    check(g.shown is None and g.closed == 1 and g.opened == 1,
          "the key again closes it, and nothing reopens it: %s %d %d" % (g.shown, g.closed, g.opened))
    g.engine_press(65)
    check(g.opened == 2 and g.shown == "catalog", "and the key opens it once more: %d %s" % (g.opened, g.shown))
    g.engine_press(1)
    check(g.shown is None and g.opened == 2, "Escape closes it: %s %d" % (g.shown, g.opened))
    g.shown = "workbench"
    g.engine_press(65)
    check(g.shown is None and g.opened == 2,
          "with Workbench open flat, the key closes it and opens nothing: %s %d" % (g.shown, g.opened))
    g.shown = "compare"
    g.engine_press(65)
    check(g.shown is None and g.opened == 2,
          "with Compare open flat, the key closes it and opens nothing: %s %d" % (g.shown, g.opened))
    g.PDA_WORKS = False
    g.engine_press(65)
    msgs = [list(x.values()) for x in g.msgs.values()]
    check(g.opened == 2 and g.shown is None and msgs == [[1, "T:st_arsenal_pda_down", 3]],
          "with the PDA out of use, the key opens nothing and the HUD says why: %d %s" % (g.opened, msgs))
    g.PDA_WORKS = True
    g.engine_press(65)
    check(g.opened == 3 and g.shown == "catalog" and len(g.msgs) == 1,
          "and opens it again once the PDA works: %d" % g.opened)
    g.engine_press(65)
    # the modifier: MCM's picker, none by default; with none the key opens Arsenal whatever is
    # held (a sprinting player's Shift), with Ctrl asked for only Ctrl and the key do
    mod = [o for o in opts.gr.values() if o.id == "flat_mod"]
    content = [c[1] for c in mod[0].content.values()] if mod else []
    check(len(mod) == 1 and mod[0].type == "radio_h" and mod[0]["def"] == 0 and mod[0].hint == "mcm_kb_modifier"
          and content == [0, 1, 2, 3],
          "the key's modifier is MCM's own picker (none, Shift, Ctrl, Alt), none by default: %s" % content)
    check(m.flat_mod() == 0, "none while the option is unset")
    g.HELD = 1
    g.engine_press(65)
    check(g.shown == "catalog", "with none asked for, Shift and the key open it too: %s" % g.shown)
    g.engine_press(65)
    g.options["arsenal/flat_mod"] = 2
    check(m.flat_mod() == 2, "Ctrl once picked: %s" % m.flat_mod())
    before = g.opened
    g.HELD = 0
    g.engine_press(65)
    check(g.opened == before and g.shown is None, "with Ctrl asked for, the key alone opens nothing")
    g.HELD = 1
    g.engine_press(65)
    check(g.opened == before and g.shown is None, "nor Shift and the key")
    g.HELD = 2
    g.engine_press(65)
    check(g.opened == before + 1 and g.shown == "catalog", "Ctrl and the key open it: %d %s" % (g.opened, g.shown))
    g.HELD = 0
    g.engine_press(65)
    check(g.shown is None, "and the key alone closes it again: %s" % g.shown)
    helper, g.ui_mcm.get_mod_key = g.ui_mcm.get_mod_key, None
    g.engine_press(65)
    check(g.shown == "catalog", "an MCM without the helper asks for none: the key alone opens it: %s" % g.shown)
    g.engine_press(65)
    g.ui_mcm.get_mod_key = helper
    g.options["arsenal/flat_mod"] = 7
    check(m.flat_mod() == 0, "a value out of range reads as none: %s" % m.flat_mod())
    g.options["arsenal/flat_mod"] = None
    # a load with a page open flat: each page closes as the level goes, so the engine holds no
    # window the restarted scripts have freed
    unload = g.callbacks.actor_on_net_destroy
    check(unload is not None, "a callback closes flat pages when the level goes")
    for page in ("catalog", "workbench", "compare"):
        g.shown, before = page, g.unloaded
        if unload is not None:
            unload()
        check(g.shown is None and g.unloaded == before + 1,
              "a load with %s open flat closes it first: %s" % (page, g.shown))
    g.shown = None
    if unload is not None:
        unload()
    check(g.unloaded == 3, "and with nothing open, closes nothing: %d" % g.unloaded)

    # the string tables: English and Russian hold the same ids, and every option has its label and
    # its description in both (a missing one shows MCM the raw id)
    def ids(lang):
        p = os.path.join(HERE, "..", "gamedata", "configs", "text", lang, "st_arsenal.xml")
        return set(re.findall(r'<string id="([^"]+)">', io.open(p, encoding="cp1251").read()))
    eng, rus = ids("eng"), ids("rus")
    check(eng == rus, "English and Russian hold the same strings: %s %s" % (sorted(eng - rus), sorted(rus - eng)))
    opts = [o.id for o in m.on_mcm_load().gr.values() if o.type in ("check", "key_bind")]
    need = ["ui_mcm_arsenal_" + i + s for i in opts for s in ("", "_desc")]
    missing = [n for n in need if n not in eng or n not in rus]
    check(not missing, "every option's label and description, in both: %s" % (missing or opts))
    g.ui_mcm = None
    check(m.flat_key() is None, "without MCM, no key")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
