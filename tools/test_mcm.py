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

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_mcm.script"), encoding="latin-1").read()
# the version line as the script has it now, so the mutant below names it whatever the release
VERSION_LINE = re.search(r'(?m)^VERSION = "[^"]+"', SRC).group(0)

STUBS = r"""
callbacks = {}
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
options = {}
ui_mcm = { get = function(path) return options[path] end,
           set = function(path, v) options[path] = v end }
-- the PDA: what reached it, and the log
news = {}
logged = {}
db = { actor = { give_game_news = function(self, title, text, icon) news[#news + 1] = { title, text, icon } end } }
function printf(fmt, ...) logged[#logged + 1] = string.format(fmt, ...) end
opened = 0
shown = nil
closed = 0
ui_arsenal = {
    open_flat = function() opened = opened + 1; shown = "catalog" end,
    flat_window = function() if shown == "catalog" then return {} end end,
}
ui_arsenal_workbench = { flat_window = function() if shown == "workbench" then return {} end end }
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
arsenal_pages = { pda_works = function() return PDA_WORKS end }
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
    "seen_any": ("return ok and v == true", "return ok"),
    "jail_def": ('{ id = "jailbreak", type = "check", val = 1, def = false }', '{ id = "jailbreak", type = "check", val = 1 }'),
    "jail_any": ("return (ok and v == true) or false", "return ok"),
    "pda_ignored": ("if not arsenal_pages.pda_works() then", "if false then"),
    "pda_silent": ('        actor_menu.set_msg(1, game.translate_string("st_arsenal_pda_down"), 3)\n', ""),
    "during_press": ('    CreateTimeEvent("arsenal_mcm", "open_flat", 0, function()\n'
                     "        ui_arsenal.open_flat()\n"
                     "        return true\n"
                     "    end)\n", "    ui_arsenal.open_flat()\n"),
    "reopens": ("    if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() then return end\n", ""),
    "workbench_ignored": ("if ui_arsenal.flat_window() or ui_arsenal_workbench.flat_window() then",
                          "if ui_arsenal.flat_window() then"),
    "news_def": ('{ id = "news", type = "check", val = 1, def = true }', '{ id = "news", type = "check", val = 1 }'),
    "news_off_unset": ("    return not (ok and v == false)", "    return ok and v == true"),
    "news_dropped": ('            { id = "news", type = "check", val = 1, def = true },\n', ""),
    "set_inverted": ('ui_mcm.set("arsenal/news", on and true or false)', 'ui_mcm.set("arsenal/news", not on)'),
    "tell_ignores": ("    if not news() then\n", "    if false then\n"),
    "tell_unlogged": ('        printf("[arsenal] PDA (silenced): %s", tostring(text))\n', ""),
    "credit_no_version": ("game.translate_string(\"st_arsenal_credit\"), VERSION, AUTHOR)",
                          "game.translate_string(\"st_arsenal_credit\"), \"\", AUTHOR)"),
    "version_behind": (VERSION_LINE, 'VERSION = "0.0.1"'),
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
    g.PDA_WORKS = False
    g.engine_press(65)
    msgs = [list(x.values()) for x in g.msgs.values()]
    check(g.opened == 2 and g.shown is None and msgs == [[1, "T:st_arsenal_pda_down", 3]],
          "with the PDA out of use, the key opens nothing and the HUD says why: %d %s" % (g.opened, msgs))
    g.PDA_WORKS = True
    g.engine_press(65)
    check(g.opened == 3 and g.shown == "catalog" and len(g.msgs) == 1,
          "and opens it again once the PDA works: %d" % g.opened)
    g.ui_mcm = None
    check(m.flat_key() is None, "without MCM, no key")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
