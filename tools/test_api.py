"""Run arsenal_api.script, the contract other mods call, and arsenal_sources.script under LuaJIT,
against stand-ins for the modules behind them and the engine's DLTX exports. Checks the contract:
nothing throws, what comes back is a copy, each call reaches what it stands for and nothing else,
and where the game read a section from (the files that wrote its lines, most first).

    python test_api.py            the real scripts
    python test_api.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "gamedata", "scripts")
API = io.open(os.path.join(SCRIPTS, "arsenal_api.script"), encoding="latin-1").read()
SOURCES = io.open(os.path.join(SCRIPTS, "arsenal_sources.script"), encoding="latin-1").read()

STUBS = r"""
LOG = {}
function printf(fmt, ...) LOG[#LOG + 1] = string.format(fmt, ...) end
CALLS = {}
local function called(name, ...) CALLS[#CALLS + 1] = { name, ... } end

local ak = { sec = "wpn_ak74", cat = "rifles", name = "AK-74",
             variants = { { sec = "wpn_ak74", name = "AK-74", members = { "wpn_ak74", "wpn_ak74_pso" } } } }
local pm = { sec = "wpn_pm", cat = "pistols", name = "PM",
             variants = { { sec = "wpn_pm", name = "PM", members = { "wpn_pm" } } } }
MODELS = { wpn_ak74 = ak, wpn_ak74_pso = ak, wpn_pm = pm }
BROKEN = false
arsenal_data = {
    CATEGORIES = { "pistols", "rifles" },
    get = function(sec) if BROKEN then error("boom") end return MODELS[sec] end,
    entry_for = function(sec) if BROKEN then error("boom") end return MODELS[sec] end,
    list = function(cat) return ({ rifles = { ak }, pistols = { pm } })[cat] or {} end,
    obtainable = function(sec) return sec ~= "wpn_ghost" end,
    icon = function(sec) if sec == "wpn_noicon" then error("no icon") end return "ui\\ui_icon_equipment" end,
}
FOUND = { wpn_pm = { at = {} } }
arsenal_collection = { entry_found = function(e) return FOUND[e.sec] end }
JAIL = false
NEWLY = true
KNOWN = { wpn_ak74 = true }
arsenal_intel = {
    jailbroken = function() return JAIL end,
    known = function(e) return KNOWN[e.sec] == true end,
    studied = function(e) return false end,
    is_new = function(e) return e.sec == "wpn_ak74" end,
    reveal = function(x, how, fact, study, quiet)
        called("reveal", x, how.kind, how.who, fact, study, quiet)
        return NEWLY and MODELS[x] or nil
    end,
    mark_all_read = function() called("mark_all_read") end,
}
FLAT = false
ui_arsenal = {
    add_action = function(id, def) called("add_action", id, def.label) end,
    remove_action = function(id) called("remove_action", id) end,
    show_next = function(sec) called("show_next", sec) end,
    flat_window = function() return FLAT and {} or nil end,
    open_flat = function() called("open_flat", "catalog"); return {} end,
}
ui_arsenal_workbench = {
    show_next = function(sec) called("wb_show_next", sec) end,
    flat_window = function() return nil end,
    open_flat = function() called("open_flat", "workbench"); return {} end,
}
ui_arsenal_compare = { flat_window = function() return nil end,
                       open_flat = function() called("open_flat", "compare"); return {} end }
PDA_WORKS = true
PDA_SHOWN = false
arsenal_pages = {
    PAGES = { catalog = {}, workbench = {}, compare = {} },
    pda_works = function() return PDA_WORKS end,
    open = function(page, sec) called("pages_open", page, sec) end,
}
ActorMenu = { get_pda_menu = function() return { IsShown = function() return PDA_SHOWN end } end }

-- Modded Exes' DLTX lines of a section, each with the file it came from
DLTX = {
    wpn_pm = {
        a = { name = "a", value = "1", filename = "w_pm.ltx" },
        b = { name = "b", value = "1", filename = "w_pm.ltx" },
        c = { name = "c", value = "1", filename = "mod_system_x.ltx" },
        d = { name = "d", value = "1", filename = "mod_system_x.ltx" },
        e = { name = "e", value = "1", filename = "w_pm.ltx" },
        f = { name = "f", value = "1", filename = "a_parent.ltx" },
        g = { name = "g", value = "1", filename = "a_parent.ltx" },
        h = { name = "h", value = "1", filename = "" },
    },
}
ini_sys = {
    section_exist = function(self, s) return s == "wpn_pm" or s == "wpn_noicon" end,
    r_string_ex = function(self, s, k)
        if k == "visual" then return "dynamics\\weapons\\wpn_pm\\wpn_pm" end
        if k == "icons_texture" then return "ui\\ui_icons_pack" end
    end,
    dltx_get_section = function(self, s) return DLTX[s] or {} end,
}
"""

MUTANTS = {
    # arsenal_api
    "api_kind": ("API", 'local how = { kind = "api",', 'local how = { kind = "talk",'),
    "api_jail": ("API", "        if not arsenal_intel or arsenal_intel.jailbroken() then return false end\n",
                 "        if not arsenal_intel then return false end\n"),
    "api_quiet": ("API", "study == true, quiet == true)", "study == true, false)"),
    "api_shared_variants": ("API", "        variants = variants,\n", "        variants = e.variants,\n"),
    "api_shared_categories": ("API", "return copy_list(arsenal_data.CATEGORIES)", "return arsenal_data.CATEGORIES"),
    "api_throws": ("API", '    local ok, a = pcall(fn, ...)\n    if ok then return a end\n    printf("[arsenal_api] %s", tostring(a))\n    return nil\n',
                   "    return (fn(...))\n"),
    "api_open_no_next": ("API", "        if sec and page == \"catalog\" then ui_arsenal.show_next(sec) end\n", ""),
    "api_open_pda_only": ("API", "        if flat or (pda and pda:IsShown()) then", "        if true then"),
    "api_open_any_page": ("API", "        if not arsenal_pages.PAGES[page] or not arsenal_pages.pda_works() then return false end\n",
                          "        if not arsenal_pages.pda_works() then return false end\n"),
    "api_action_unchecked": ("API",
                             '        if type(id) ~= "string" or type(def) ~= "table" or type(def.run) ~= "function" then return false end\n',
                             ""),
    "api_found_wrong": ("API", "found = arsenal_collection ~= nil and arsenal_collection.entry_found(e) ~= nil,",
                        "found = true,"),
    # arsenal_sources
    "src_order": ("SOURCES", "return count[a] > count[b]", "return count[a] < count[b]"),
    "src_tie": ("SOURCES", "            return a < b\n", "            return a > b\n"),
    "src_dltx_flag": ("SOURCES", 'dltx = f:sub(1, 4) == "mod_"', "dltx = false"),
    "src_empty_kept": ("SOURCES", 'if type(f) == "string" and f ~= "" then', 'if type(f) == "string" then'),
    "src_icon_fallback": ("SOURCES", 'out.icon = okI and tex or ini_sys:r_string_ex(sec, "icons_texture")',
                          "out.icon = okI and tex or nil"),
    "src_no_guard": ("SOURCES", "    local ok, t = pcall(function() return ini_sys:dltx_get_section(sec) end)\n",
                     "    local ok, t = true, ini_sys:dltx_get_section(sec)\n"),
}


def main():
    api, src = API, SOURCES
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        which, old, new = MUTANTS[mutant]
        if which == "API":
            assert api.count(old) == 1, old
            api = api.replace(old, new)
        else:
            assert src.count(old) == 1, old
            src = src.replace(old, new)
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS)
    load = lua.eval("function(src, name) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); f(); _G[name] = env; return env end")
    s = load(src, "arsenal_sources")
    a = load(api, "arsenal_api")
    g = lua.globals()
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    def calls(name=None):
        out = [list(c.values()) for c in g.CALLS.values()]
        return [c for c in out if name is None or c[0] == name]

    def reset():
        g.CALLS = lua.table_from({})

    lst = lambda t: list(t.values()) if t is not None else None

    check(a.VERSION == 1, "VERSION 1: %s" % a.VERSION)

    # categories: Arsenal's order, a copy
    cats = a.categories()
    check(lst(cats) == ["pistols", "rifles"], "categories in Arsenal's order: %s" % lst(cats))
    cats[1] = "changed"
    check(g.arsenal_data.CATEGORIES[1] == "pistols", "a copy: changing it changes nothing in Arsenal")

    # model: any section of it, a copy, with what the player knows
    md = a.model("wpn_ak74_pso")
    check(md is not None and md.sec == "wpn_ak74" and md.name == "AK-74" and md.category == "rifles",
          "a scoped section gives its model: %s" % (md and (md.sec, md.name, md.category),))
    v = md and md.variants[1]
    check(v is not None and v.sec == "wpn_ak74" and lst(v.members) == ["wpn_ak74", "wpn_ak74_pso"],
          "with its variants and their sections")
    check(md.obtainable is True and md.found is False and md.known is True and md.studied is False and md.new is True,
          "and what the player knows of it: %s" % [md.obtainable, md.found, md.known, md.studied, md.new])
    v.members[1] = "changed"
    check(g.MODELS.wpn_ak74.variants[1].members[1] == "wpn_ak74", "a copy: its variants too")
    pm = a.model("wpn_pm")
    check(pm.found is True and pm.known is False and pm.new is False, "a found one: found; one not learned of: not known")
    check(a.model("nope") is None and a.model(None) is None, "nil for what Arsenal does not list, and for nil")

    # models: a category's, as model() gives them
    ms = a.models("rifles")
    check(ms is not None and len(ms) == 1 and ms[1].sec == "wpn_ak74", "a category's models")
    check(len(a.models("bogus")) == 0, "none for an unknown category, an empty table")

    # nothing throws: an internal error comes back nil, logged
    g.BROKEN = True
    try:
        got = a.model("wpn_pm")
        threw = False
    except Exception:
        got, threw = None, True
    g.BROKEN = False
    check(not threw and got is None and any("boom" in x for x in g.LOG.values()),
          "an internal error: nil, and the log says why, not an error: %s" % list(g.LOG.values()))

    # reveal: Arsenal's own discovery, in the source's words
    reset()
    ok = a.reveal("wpn_pm", "the Mercenary Database")
    r = calls("reveal")
    check(ok is True and len(r) == 1 and r[0][1:] == ["wpn_pm", "api", "the Mercenary Database", False, False],
          "reveal teaches the model, kind api, in the source's words, announced: %s %s" % (ok, r))
    reset()
    a.reveal("wpn_pm", "x", True, True)
    r = calls("reveal")
    check(r and r[0][-2:] == [True, True], "study and quiet pass through: %s" % r)
    g.NEWLY = False
    check(a.reveal("wpn_pm", "x") is False, "false when it was known already")
    g.NEWLY = True
    reset()
    g.JAIL = True
    check(a.reveal("wpn_pm", "x") is False and not calls("reveal"), "with the jailbreak: false, nothing taught")
    g.JAIL = False

    # mark all read; without the discovery module, nothing breaks
    reset()
    a.mark_all_read()
    check(len(calls("mark_all_read")) == 1, "mark_all_read reaches Arsenal's")
    intel, g.arsenal_intel = g.arsenal_intel, None
    try:
        a.mark_all_read()
        ok2, known = a.reveal("wpn_pm", "x"), a.model("wpn_pm").known
        quiet = True
    except Exception:
        ok2, known, quiet = None, None, False
    g.arsenal_intel = intel
    check(quiet and ok2 is False and known is True, "without arsenal_intel: no error, reveal false, all known")

    # actions: only well-formed ones reach the page
    reset()
    good = a.add_action("my_mod", lua.eval('{ label = "st_x", run = function() end }'))
    bad = a.add_action("my_mod", lua.eval('{ label = "st_x" }'))
    bad2 = a.add_action(5, lua.eval('{ run = function() end }'))
    check(good is True and bad is False and bad2 is False and calls("add_action") == [["add_action", "my_mod", "st_x"]],
          "add_action: true and passed on when well-formed, else false: %s" % calls("add_action"))
    a.remove_action("my_mod")
    check(calls("remove_action") == [["remove_action", "my_mod"]], "remove_action reaches the page")

    # open: in the PDA when it is open, else Arsenal's own window; the catalog or Workbench at a model
    reset()
    g.PDA_SHOWN = True
    ok = a.open("catalog", "wpn_pm")
    check(ok is True and calls("show_next") == [["show_next", "wpn_pm"]] and calls("pages_open") == [["pages_open", "catalog"]]
          and not calls("open_flat"), "PDA open: the catalog's page, at the model: %s" % calls())
    reset()
    g.PDA_SHOWN = False
    ok = a.open("workbench", "wpn_ak74")
    check(ok is True and calls("wb_show_next") == [["wb_show_next", "wpn_ak74"]] and calls("open_flat") == [["open_flat", "workbench"]]
          and not calls("pages_open"), "PDA closed: Workbench in its own window, at the item: %s" % calls())
    reset()
    g.FLAT = True
    a.open()
    check(calls("pages_open") == [["pages_open", "catalog"]] and not calls("open_flat"),
          "a page already open flat: the switch, to the catalog by default: %s" % calls())
    g.FLAT = False
    reset()
    check(a.open("settings") is False and not calls(), "an unknown page: false, nothing opened")
    g.PDA_WORKS = False
    check(a.open("catalog") is False and not calls("open_flat") and not calls("pages_open"),
          "Fatal Error's PDA out of use: false")
    g.PDA_WORKS = True

    # where a section was read from: the files that wrote its lines, most first, then by name; a
    # mod_ file marked; a line without a file left out; model and icon
    d = s.of("wpn_pm")
    files = [(f.name, f.lines, f.dltx) for f in d.files.values()] if d is not None and d.files is not None else None
    check(files == [("w_pm.ltx", 3, False), ("a_parent.ltx", 2, False), ("mod_system_x.ltx", 2, True)],
          "files most lines first, ties by name, mod_ files marked, empty ones left out: %s" % files)
    check(d.section == "wpn_pm" and d.model == "dynamics\\weapons\\wpn_pm\\wpn_pm" and d.icon == "ui\\ui_icon_equipment",
          "the section, its model, its icon as the page draws it: %s %s %s" % (d.section, d.model, d.icon))
    n = s.of("wpn_noicon")
    check(n is not None and n.icon == "ui\\ui_icons_pack" and n.files is not None and len(n.files) == 0,
          "an icon that cannot be drawn: its icons_texture; a section with no lines: no files: %s" % (n and n.icon,))
    check(s.of("nope") is None and s.of(None) is None, "nil for a section the game does not have")
    lua.execute("ini_sys.dltx_get_section = nil")
    try:
        d = s.of("wpn_pm")
    except Exception as ex:
        d = None
        print("      raised: %s" % str(ex).splitlines()[0])
    check(d is not None and d.files is None and d.model is not None,
          "without the DLTX exports: no files, the rest still, and no error")
    lua.execute("ini_sys.dltx_get_section = function(self, s) return DLTX[s] or {} end")

    # defined_in: the same, as a copy
    di = a.defined_in("wpn_pm")
    check(di is not None and di.files[1].name == "w_pm.ltx" and di.files[3].dltx is True and di.section == "wpn_pm",
          "defined_in hands out where it was read from")
    di.files[1].name = "changed"
    check(s.of("wpn_pm").files[1].name == "w_pm.ltx" and a.defined_in("nope") is None, "a copy; nil for an unknown section")

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
