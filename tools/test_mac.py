"""Run z_arsenal_mac.script under LuaJIT against stand-ins for Mod App Creator's launcher, and
check the tile and its badge: the app is added; MAC's get_ui is wrapped once and still returns
the launcher page, passing its arguments along; the badge sits on Arsenal's tile wherever MAC
put it, is made once per page, shows the count of what is new (one, two or three digits, at
most 999) and hides at none; a page of another shape gets none; a badge that fails leaves the
launcher working and is logged once; without MAC nothing is wrapped.

    python test_mac.py            the real script
    python test_mac.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys
import xml.etree.ElementTree as ET

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "..", "gamedata")
SRC = io.open(os.path.join(GD, "scripts", "z_arsenal_mac.script"), encoding="latin-1").read()
XML = io.open(os.path.join(GD, "configs", "ui", "ui_arsenal.xml"), encoding="cp1251").read()

STUBS = r"""
local SIZES = ...
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
function vector2() return { set = function(self, x, y) self.x, self.y = x, y; return self end } end
arsenal_theme = { argb = function(role) return role end }
COUNT = 0
arsenal_intel = { count_new = function()
    if COUNT == "boom" then error("no count") end
    return COUNT
end }
ui_arsenal = { get_ui = function() return "arsenal page" end }

-- a widget: records what was set on it
local W = {}
W.__index = W
function widget(path, parent, x, y, w, h)
    local o = setmetatable({ path = path, x = x or 0, y = y or 0, w = w or 10, h = h or 10, children = {} }, W)
    if parent and parent.children then table.insert(parent.children, o) end
    return o
end
function W:SetText(t) self.text = t end
function W:InitTexture(t) self.tex = t end
function W:SetTextureColor(c) self.tcolor = c end
function W:Show(b) self.shown = b end
function W:SetWndPos(v) self.x, self.y = v.x, v.y end
function W:GetWndPos() return { x = self.x, y = self.y } end
function W:SetWndSize(v) self.w, self.h = v.x, v.y end
function W:GetWidth() return self.w end

-- ui_arsenal.xml must have every element asked for
CScriptXmlInit = function()
    local x = {}
    function x:ParseFile(f) self.file = f end
    local function init(self, path, parent)
        local s = SIZES[path]
        if self.file ~= "ui_arsenal.xml" or not s then error("no element '" .. path .. "' in the layout", 2) end
        return widget(path, parent, s[1], s[2], s[3], s[4])
    end
    x.InitStatic, x.InitTextWnd = init, init
    return x
end

-- MAC: tiles 50 wide, ten to a row from (50, 100), in the order of its table
function launcher(ids)
    local page = widget("launcher", nil)
    page.apps, page.apps_ids = {}, {}
    for i, id in ipairs(ids) do
        page.apps[i] = widget("app_" .. id, page, 50 + ((i - 1) % 10) * 75, 100 + math.floor((i - 1) / 10) * 80, 50, 50)
        page.apps_ids[i] = id
    end
    return page
end
PAGE = launcher({ "app_taskboard", "app_pgc", "arsenal" })
calls = {}
function original_get_ui(...)
    calls[#calls + 1] = { ... }
    return PAGE
end
added = {}
mac_mcm = {
    add_app = function(id, data) added[id] = data end,
    get_ui = original_get_ui,
}
"""

MUTANTS = {
    "no_wrap": ("    if type(mac_mcm.get_ui) == \"function\" then\n        wrap_launcher()\n    end\n", ""),
    "wrap_twice": ("    if mac_mcm.arsenal_get_ui then return end\n", ""),
    "no_varargs": ("        local ui = get_ui(...)", "        local ui = get_ui()"),
    "badge_each_time": ("    if not ui.arsenal_badge then", "    if true then"),
    "never_hidden": ("    b:Show(n > 0)", "    b:Show(true)"),
    "no_cap": ("local s = tostring(math.min(n, 999))", "local s = tostring(n)"),
    "one_shape": ("    local shape = BADGES[#s]", "    local shape = BADGES[1]"),
    "first_tile": ('        if id == "arsenal" then tile = apps[i] end', "        tile = tile or apps[i]"),
    "no_place": ("    b:SetWndPos(vector2():set(p.x + tile:GetWidth() - shape.w + 8, p.y - 6))", "    -- where the layout puts it"),
    "text_size": ("    text:SetWndSize(vector2():set(shape.w, BADGE_H))\n", ""),
    "no_tint": ('    b:SetTextureColor(arsenal_theme.argb("badge"))\n', ""),
    "no_guard": ("            local ok, err = pcall(badge, ui)", "            local ok, err = true, badge(ui)"),
    "warn_each_time": ("            if not ok and not warned then", "            if not ok then"),
    "shape_check": ('    if type(ids) ~= "table" or type(apps) ~= "table" then return end', ""),
}


def sizes():
    root = ET.fromstring(XML.split("?>", 1)[1])
    return {el.tag: [float(el.get(k, 0)) for k in ("x", "y", "width", "height")] for el in root}


def main():
    src = SRC
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS, lua.table_from({k: lua.table_from(v) for k, v in sizes().items()}))
    g = lua.globals()
    load = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); f(); return env end")
    m = load(src)
    m.on_game_start()

    def open_launcher(*args):
        """the launcher as the PDA opens it, or the error it raised"""
        try:
            return g.mac_mcm.get_ui(*args)
        except L.LuaError as e:
            return "error: %s" % e

    badges = lambda page: [c for c in page.children.values() if c.path == "mac_badge"]
    is_page = lua.eval("function(x) return x == PAGE end")

    app = g.added["arsenal"]
    check(app is not None and app.tab == "eptArsenal" and app.texture == "arsenal_app" and app.func() == "arsenal page",
          "the tile is added, opening Arsenal's page")
    check(lua.eval("mac_mcm.arsenal_get_ui == original_get_ui and mac_mcm.get_ui ~= original_get_ui") is True,
          "MAC's get_ui is wrapped, the original kept")

    page = open_launcher("a", 2)
    args = list(g.calls[len(g.calls)].values()) if len(g.calls) else []
    check(is_page(page) and args == ["a", 2], "the launcher page comes back, its arguments passed along: %s" % args)
    b = badges(page)
    check(len(b) == 1 and b[0].shown is False, "nothing new: no badge shown")

    tile = g.PAGE.apps[3]
    for n, text, tex, w in ((3, "3", "arsenal_badge_1", 20), (12, "12", "arsenal_badge_2", 28),
                            (345, "345", "arsenal_badge_3", 36), (1500, "999", "arsenal_badge_3", 36)):
        g.COUNT = n
        page = open_launcher()
        b = badges(page)
        one = b[0] if b else None
        t = one.children[1] if one and one.children else None
        check(len(b) == 1 and one.shown is True and t is not None and t.text == text and one.tex == tex
              and one.w == w and t.w == w and one.tcolor == "badge",
              "%d new: one badge, %s on the %d-wide shape, tinted: %s"
              % (n, text, w, one and (one.shown, t and t.text, one.tex, one.w, t and t.w, one.tcolor)))
        check(one is not None and one.x == tile.x + 50 - w + 8 and one.y == tile.y - 6,
              "on Arsenal's tile (the third), its top right corner: %s" % str(one and (one.x, one.y)))

    # MAC built a new page (an app was added): the new page gets its own badge
    lua.execute('PAGE = launcher({ "arsenal", "app_taskboard" })')
    g.COUNT = 2
    page = open_launcher()
    b = badges(page)
    check(len(b) == 1 and b[0].children[1].text == "2" and b[0].x == 50 + 50 - 20 + 8,
          "a new page, its own badge, on the tile where it is now: %s" % str(b and b[0].x))

    # wrapped once, though the game starts twice
    m.on_game_start()
    check(lua.eval("mac_mcm.arsenal_get_ui == original_get_ui") is True, "wrapped once")

    # a page of another shape: returned as it is
    lua.execute("PAGE = widget('other', nil)")
    page = open_launcher()
    check(is_page(page) and not badges(page) and len(g.logs) == 0, "a page of another shape: as it is, no badge, nothing logged")

    # a badge that fails: the launcher still opens, one line in the log
    lua.execute('PAGE = launcher({ "arsenal" })')
    g.COUNT = "boom"
    first = open_launcher()
    second = open_launcher()
    check(is_page(first) and is_page(second), "a failing badge leaves the launcher working: %s" % str(first))
    check(len(g.logs) == 1 and "no badge" in g.logs[1], "logged once: %s" % list(g.logs.values()))

    # no MAC: nothing to wrap, said once
    lua.execute("mac_mcm = nil; logs = {}")
    m2 = load(src)
    try:
        m2.on_game_start()
        ok = True
    except L.LuaError:
        ok = False
    check(ok and len(g.logs) == 1 and "not found" in g.logs[1], "without MAC: no tile, one line: %s" % list(g.logs.values()))

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
