"""Run arsenal_mcm.script under LuaJIT against stubs of MCM and ui_arsenal, and check the key:
its MCM option has a real default (unbound, -1; a nil default once crashed another mod's
startup), an unbound key or a missing MCM reads as no key, and only the bound key opens the
flat window.

    python test_mcm.py            the real script
    python test_mcm.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_mcm.script"), encoding="latin-1").read()

STUBS = r"""
callbacks = {}
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
options = {}
ui_mcm = { get = function(path) return options[path] end }
opened = 0
ui_arsenal = { open_flat = function() opened = opened + 1 end }
"""

MUTANTS = {
    "def_nil": ('{ id = "flat_key", type = "key_bind", val = 2, def = -1 }',
                '{ id = "flat_key", type = "key_bind", val = 2, def = nil }'),
    "unbound": ("return (k and k >= 0) and k or nil", "return k"),
    "no_callback": ('RegisterScriptCallback("on_key_press", on_key_press)', "-- not registered"),
    "any_key": ("if k and key == k then", "if k then"),
    "seen_def": ('{ id = "count_seen", type = "check", val = 1, def = false }', '{ id = "count_seen", type = "check", val = 1 }'),
    "seen_any": ("return ok and v == true", "return ok"),
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
    m.on_game_start()
    press = g.callbacks.on_key_press
    check(press is not None, "the key press callback is registered")
    g.options["arsenal/flat_key"] = -1
    check(m.flat_key() is None, "an unbound key reads as no key")
    if press is not None:
        press(30)
    check(g.opened == 0, "with no key bound, no key opens the window")
    g.options["arsenal/flat_key"] = 65
    check(m.flat_key() == 65, "a bound key: %s" % m.flat_key())
    if press is not None:
        press(30)
        press(65)
    check(g.opened == 1, "only the bound key opens the window: %d" % g.opened)
    g.ui_mcm = None
    check(m.flat_key() is None, "without MCM, no key")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
