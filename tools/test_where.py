"""Run arsenal_where.script under LuaJIT against stubs (the game graph, the game's news helper)
and check how a place and a person go into words: a place by the game's own helper, its
trailing comma trimmed; the level alone when the vertex is gone, lies on another level, or the
helper fails or names strings it lacks; a person by name and faction, a faction the catalog
does not know left out, "a Duty fighter" unnamed, "someone" when nothing is known.

    python test_where.py            the real script
    python test_where.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_where.script"), encoding="latin-1").read()

STUBS = r"""
local T = { st_arsenal_in = "in %s", l01_escape = "Cordon", l02_garbage = "Garbage", st_faction_dolg = "Duty",
    st_arsenal_who_named = "%s fighter %s", st_arsenal_who_faction = "a %s fighter", st_arsenal_by_someone = "someone" }
game = { translate_string = function(k) return T[k] or k end }
arsenal_data = { FACTIONS = { "stalker", "dolg", "freedom" } }
-- game vertices: 10 and 30 to 40 on Cordon, 20 on the Garbage
local LEVEL_OF = { [10] = 1, [20] = 2, [30] = 1, [40] = 1 }
local LEVELS = { "l01_escape", "l02_garbage" }
function game_graph() return {
    valid_vertex_id = function(self, gv) return LEVEL_OF[gv] ~= nil end,
    vertex = function(self, gv) local l = LEVEL_OF[gv]; return l and { level_id = function() return l end } end,
} end
function alife() return { level_name = function(self, id) return LEVELS[id] end } end
function vector() return { set = function(self, x, y, z) return { x = x, y = y, z = z } end } end
-- the game's helper: what it is asked about, and what it says
ASKED = {}
dynamic_news_helper = { GetPointDescription = function(obj)
    ASKED[#ASKED + 1] = obj
    local gv = obj.m_game_vertex_id
    if gv == 10 then return "in Cordon, near the rookie village"
    elseif gv == 20 then return "in Garbage,"
    elseif gv == 30 then error("no level points")
    elseif gv == 40 then return "st_dyn_news_l99, st_dyn_l99_daleko_1" end
end }
function thing(gv, x, y, z)
    return { game_vertex_id = function() return gv end, position = function() return { x = x, y = y, z = z } end }
end
broken = { game_vertex_id = function() error("offline") end, position = function() return nil end }
"""

MUTANTS = {
    "round": ("    local function r(n) return math.floor(n * 10 + 0.5) / 10 end",
              "    local function r(n) return n end"),
    "guard": ("    local ok, gv, pos = pcall(function() return obj:game_vertex_id(), obj:position() end)",
              "    local ok, gv, pos = true, obj:game_vertex_id(), obj:position()"),
    "valid": ("    if gg and gg:valid_vertex_id(place.gv) then", "    if gg then"),
    "same_level": ("        if not lvl or on == lvl then", "        if true then"),
    "helper_guard": ("            local ok, s = pcall(dynamic_news_helper.GetPointDescription,\n",
                     "            local ok, s = true, dynamic_news_helper.GetPointDescription(\n"),
    "trim": ('s:gsub("[,%s]+$", "")', '(s)'),
    "leak": (' and not s:find("st_dyn", 1, true)', ""),
    "level_fallback": ('    return lvl and string.format(T("st_arsenal_in"), T(lvl)) or ""', '    return ""'),
    "no_place": ('    return p ~= "" and (s .. " " .. p) or s', '    return s .. " " .. p'),
    "named": ('        return fname and string.format(T("st_arsenal_who_named"), fname, how.who) or how.who',
              "        return how.who"),
    "known_faction": ("    local fname = f and is_faction(f) and T(\"st_faction_\" .. f)",
                      "    local fname = f and T(\"st_faction_\" .. f)"),
    "empty_name": ('    if how and how.who and how.who ~= "" then', "    if how and how.who then"),
    "unnamed": ('    return fname and string.format(T("st_arsenal_who_faction"), fname) or T("st_arsenal_by_someone")',
                '    return T("st_arsenal_by_someone")'),
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

    def run(fn):
        try:
            return fn()
        except Exception as err:
            return "error: %s" % str(err)[:90]

    t = lua.table_from
    p = run(lambda: m.place_of(g.thing(10, 12.345, 1.04, -7.96)))
    check(not isinstance(p, str) and p is not None and (p.gv, p.x, p.y, p.z) == (10, 12.3, 1.0, -8.0),
          "a place: its vertex, and its position to a tenth of a metre: %s" % (p if isinstance(p, str) else
                                                                            p and (p.gv, p.x, p.y, p.z),))
    check(run(lambda: m.place_of(None)) is None and run(lambda: m.place_of(g.broken)) is None,
          "none for nothing, or for an object the engine cannot place")

    cordon = t({"gv": 10, "x": 12.3, "y": 1.0, "z": -8.0})
    s = run(lambda: m.place_text(cordon, "l01_escape"))
    asked = g.ASKED[len(g.ASKED)] if len(g.ASKED) else None
    check(s == "in Cordon, near the rookie village", "in words, by the game's helper: %s" % s)
    check(asked is not None and asked.m_game_vertex_id == 10 and (asked.position.x, asked.position.z) == (12.3, -8.0),
          "which is asked about the kept vertex and position")
    check(run(lambda: m.place_text(t({"gv": 20, "x": 0, "y": 0, "z": 0}), "l02_garbage")) == "in Garbage",
          "its trailing comma trimmed, where the level has no points")
    check(run(lambda: m.place_text(cordon, "l02_garbage")) == "in Garbage",
          "a vertex on another level than the one kept (another mod list): the level alone")
    check(run(lambda: m.place_text(t({"gv": 99, "x": 0, "y": 0, "z": 0}), "l01_escape")) == "in Cordon",
          "a vertex that is gone: the level alone")
    check(run(lambda: m.place_text(t({"gv": 30, "x": 0, "y": 0, "z": 0}), "l01_escape")) == "in Cordon",
          "the helper failing: the level alone")
    check(run(lambda: m.place_text(t({"gv": 40, "x": 0, "y": 0, "z": 0}), "l01_escape")) == "in Cordon",
          "the helper naming strings it lacks: the level alone")
    check(run(lambda: m.place_text(None, "l01_escape")) == "in Cordon" and run(lambda: m.place_text(None, None)) == "",
          "no place: the level; nothing: nothing")
    check(run(lambda: m.at_place("a stash", cordon, "l01_escape")) == "a stash in Cordon, near the rookie village"
          and run(lambda: m.at_place("a stash", None, None)) == "a stash",
          "words with a place after them, when there is one")

    who = lambda d: run(lambda: m.who_text(t(d) if d is not None else None))
    check(who({"who": "Ivan Petrenko", "faction": "dolg"}) == "Duty fighter Ivan Petrenko",
          "a person: his faction and name: %s" % who({"who": "Ivan Petrenko", "faction": "dolg"}))
    check(who({"who": "Sidorovich", "faction": "trader"}) == "Sidorovich",
          "his name alone when the catalog does not know his faction: %s" % who({"who": "Sidorovich", "faction": "trader"}))
    check(who({"faction": "dolg"}) == "a Duty fighter" and who({"who": "", "faction": "dolg"}) == "a Duty fighter",
          "unnamed: a fighter of his faction")
    check(who({}) == "someone" and who(None) == "someone", "nothing known: someone")

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
