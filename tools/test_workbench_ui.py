"""Run Workbench's page (ui_arsenal_workbench.script) on the real arsenal_workbench.script, with
test_workbench's stand-ins for the engine, GAMMA's toolkit and Arsenal's data, plus stand-ins for
the engine's widgets; and arsenal_pages.script, the switch and the router. Checks: every layout
element the page asks for is in ui_arsenal.xml; the items carried and the models planned, under
their headings; the tree in the toolkit's places, each cell marked by its state, the kit it takes
with how many the player holds; a click plans or unplans and the card, the kits and the list
follow; the details under the cursor; attachments; Clear; Install only where it can go; the
switch, Back, the flat window; and the router.

    python test_workbench_ui.py            the real scripts
    python test_workbench_ui.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_workbench as TW  # noqa: E402

GD = os.path.join(HERE, "..", "gamedata")
PAGE = io.open(os.path.join(GD, "scripts", "ui_arsenal_workbench.script"), encoding="latin-1").read()
DATA = io.open(os.path.join(GD, "scripts", "arsenal_workbench.script"), encoding="latin-1").read()
PAGES = io.open(os.path.join(GD, "scripts", "arsenal_pages.script"), encoding="latin-1").read()
XML = io.open(os.path.join(GD, "configs", "ui", "ui_arsenal.xml"), encoding="cp1251").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(GD, "configs", "text", "eng", "st_arsenal.xml"), encoding="cp1251").read(),
                          re.S))

WIDGETS = r"""
local SIZES, STRINGS = ...
local W = {}
W.__index = W
function new_widget(path, parent)
    local s = SIZES[path] or { 0, 0, 10, 10 }
    local w = setmetatable({ path = path, x = s[1], y = s[2], w = s[3], h = s[4], children = {}, shown = true,
                             enabled = true }, W)
    if parent and parent.children then table.insert(parent.children, w) end
    w.parent = parent
    return w
end
function W:SetText(t) self.text = t end
function W:GetText() return self.text end
function W:SetTextColor(c) self.color = c end
function W:SetWndPos(v) self.x, self.y = v.x, v.y end
function W:GetWndPos() return { x = self.x, y = self.y } end
function W:SetWndSize(v) self.w, self.h = v.x, v.y end
function W:GetWidth() return self.w end
function W:GetHeight() return self.h end
function W:AdjustHeightToText() self.h = 18 * math.max(1, math.ceil(#(self.text or "") * 8 / math.max(self.w, 1))) end
function W:InitTexture(t) self.tex = t end
function W:SetTextureRect(r) self.rect = r end
function W:SetStretchTexture(b) end
function W:SetTextureColor(c) self.tcolor = c end
function W:Show(b) self.shown = b end
function W:IsShown() return self.shown ~= false end
function W:Enable(b) self.enabled = b end
function W:IsEnabled() return self.enabled ~= false end
function W:TextControl() return self end
function W:SetAutoDelete(b) self.autodelete = b end
function W:IsCursorOverWindow() return HOVER == self end
function W:AddExistingItem(item) self.items = self.items or {}; table.insert(self.items, item) end
function W:RemoveAll() self.items = {}; self.sel = nil end
function W:GetSize() return #(self.items or {}) end
function W:SetSelectedIndex(i) self.sel = i end
function W:GetSelectedItem() return self.sel and self.items[self.sel + 1] end
function W:Clear() self.content = {} end
function W:AddWindow(w, auto) self.content = self.content or {}; table.insert(self.content, w) end

-- ui_arsenal.xml must have every element asked for
CScriptXmlInit = function()
    local x = {}
    function x:ParseFile(f) self.file = f end
    local function init(self, path, parent)
        if self.file == "ui_arsenal.xml" and not SIZES[path] then error("no element '" .. path .. "' in the layout", 2) end
        return new_widget(path, parent)
    end
    x.InitTextWnd, x.InitStatic, x.InitCheck, x.Init3tButton, x.InitListBox, x.InitScrollView = init, init, init, init, init, init
    return x
end
function class(name)
    return function(base)
        local cls = setmetatable({}, { __index = base })
        cls.__index = cls
        setmetatable(cls, { __index = base, __call = function(c, ...)
            local o = setmetatable({ children = {} }, c)
            if c.__init then c.__init(o, ...) end
            return o
        end })
        _G[name] = cls
        return cls
    end
end
function super() end
CUIListBoxItem = setmetatable({ children = {} }, { __index = W })
CUIListBoxItem.__index = CUIListBoxItem
CUIScriptWnd = setmetatable({}, { __index = W })
function CUIScriptWnd.Update(self) end
function CUIScriptWnd:Register(w, name) self.registered = self.registered or {}; self.registered[name] = w end
function CUIScriptWnd:AddCallback(name, ev, fn, obj)
    self.cb = self.cb or {}
    self.ncb = self.ncb or {}
    self.ncb[name] = (self.ncb[name] or 0) + 1
    self.cb[name] = function() fn(obj) end
end
function CUIScriptWnd:SetWndRect(r) self.rect = r.r end
function CUIScriptWnd:ShowDialog(b) self.dialog_shown = true end
function CUIScriptWnd:HideDialog() self.dialog_shown = false end
function CUIScriptWnd:IsShown() return self.dialog_shown == true end
function CUIScriptWnd.OnKeyboard(self, dik, action) return false end
DIK_keys = { DIK_ESCAPE = 1, DIK_F7 = 65, DIK_A = 30 }
arsenal_mcm = { flat_key = function() return DIK_keys.DIK_F7 end }
function vector2() return { set = function(self, x, y) self.x, self.y = x, y; return self end } end
function Frect() return { set = function(self, a, b, c, d) self.r = { a, b, c, d }; return self end } end
function GetARGB(a, r, g, b) return string.format("%d,%d,%d,%d", a, r, g, b) end
ui_events = { BUTTON_CLICKED = 1, LIST_ITEM_SELECT = 2, LIST_ITEM_CLICKED = 3, WINDOW_KEY_PRESSED = 6 }
utils_xml = { is_widescreen = function() return true end }
arsenal_theme = { argb = function(role, a) return a and (role .. "@" .. a) or role end,
                  markup = function(role) return "<" .. role .. ">" end,
                  set_active = function(btn, on) btn.active = on end }
game.translate_string = function(k) return STRINGS[k] or (k:gsub("^st_", "")) end
db.actor.alive = function() return ALIVE end
ALIVE = true
-- the toolkit's property functors: a line per property
inventory_upgrades = { prop = function(stats, prop) return "line " .. prop .. " of " .. stats end }
SEC.prop_recoil = { functor = "inventory_upgrades.prop" }
SEC.prop_dispersion = { functor = "inventory_upgrades.prop" }
arsenal_data.icon = function(sec) return "ui_icons_" .. sec, { x1 = 0, y1 = 0, w = 100, h = 50 } end
for _, k in ipairs({ "1_internal", "1_external", "1_optical", "2_internal", "2_external", "2_optical", "3_internal",
                    "3_external", "3_optical" }) do
    SEC["upgr_w_" .. k] = { inv_name = "st_kit_" .. k }
end
"""

MUTANTS = {
    "no_headings": ('        if i == 1 and e.id then\n            self.list:AddExistingItem(WorkbenchRow(xml, nil, T("st_arsenal_wb_carried"), "dim"))\n        end\n', ""),
    "heading_selects": ("    if not item.key then\n        -- a heading: back to the item shown\n        self:FillList()\n        return\n    end\n", ""),
    "no_count": ('        local row = WorkbenchRow(xml, e.key, e.name, "body", n > 0 and ("+" .. n) or nil)',
                 '        local row = WorkbenchRow(xml, e.key, e.name, "body", nil)'),
    "want_ignored": ("    if want then\n        if want.id and ids[want.id] then", "    if false then\n        if want.id and ids[want.id] then"),
    "want_model_only": ("        elseif want.sec and secs[want.sec] then\n            key = \"id:\" .. secs[want.sec].id\n", ""),
    "no_valid": ("    self.plan = W.valid(self.t, self.installed, plan)", "    self.plan = plan"),
    "all_rows": ("        if t[r] and next(t[r]) then", "        if true then"),
    "solo_unshifted": ("                    local dy = (cell.solo and c % 2 == 1) and SOLO_DY or 0", "                    local dy = 0"),
    "no_marks": ("                    s.mark:Show(MARKS[st] ~= nil)", "                    s.mark:Show(false)"),
    "no_later_mark": ('                    if st == "planned" and later[cell.section] then st = "later" end\n', ""),
    "kit_count_off": ("                        s.num:SetText(tostring(n))", "                        s.num:SetText(\"\")"),
    "card_now_only": ("        if r.plan_text and r.plan_text ~= r.now_text then", "        if false then"),
    "card_no_roles": ('cols[3]:SetTextColor(theme.argb((r.better == true and "good") or (r.better == false and "danger") or "body"))',
                      'cols[3]:SetTextColor(theme.argb("body"))'),
    "card_codes_kept": ('    return (s:gsub("%%c%[[^%]]*%]", ""))', "    return s"),
    "card_plan_now": ("    local ok, rows = pcall(arsenal_workbench.card, e.sec, now, plan, self.att_now, att)",
                      "    local ok, rows = pcall(arsenal_workbench.card, e.sec, now, now, self.att_now, att)"),
    "kits_held_ignored": ('            cell.num:SetTextColor(theme.argb(have >= k.n and "good" or "danger"))',
                          '            cell.num:SetTextColor(theme.argb("good"))'),
    "toggle_unsaved": ("    self.plan = plan\n    self:Save()\n    self:Refresh()", "    self.plan = plan\n    self:Refresh()"),
    "refused_silent": ("    if not plan then\n        self.hover = nil\n        self:ShowInfo({ cell = { r, c } })\n        return\n    end",
                       "    if not plan then\n        return\n    end"),
    "clear_keeps": ("    self.plan, self.att = {}, {}\n    self:Save()", "    self:Save()"),
    "install_always": ("    self.btn_install:Enable(why == nil)", "    self.btn_install:Enable(true)"),
    "install_unchecked": ("    if not e or arsenal_workbench.cannot_install(e.id, e.sec, self.plan) then", "    if not e then"),
    "hover_dead": ("    if key ~= self.hover then", "    if false then"),
    "info_no_state": ('        line(T("st_arsenal_wb_state_" .. st), st == "installed" and "good" or (st == "planned" and "heading" or "dim"))',
                      "        line(nil)"),
    "info_no_props": ("            if ok and type(s) == \"string\" and s ~= \"\" then line(s, \"body\") end", "            -- no lines"),
    "scope_cycle_stuck": ("        self.att.scope = list[cur % n + 1]", "        self.att.scope = list[cur]"),
    "names_long": ('            choice = s and short(name_of(s)) or T("st_arsenal_wb_att_none")',
                   '            choice = s and name_of(s) or T("st_arsenal_wb_att_none")'),
    "short_keeps_parens": ('    s = s:gsub("%s*%b()%s*$", "")', '    s = s'),
    "kits_no_more": ("        if k and more > 0 and i == MAX_KITS then", "        if false then"),
    "silencer_stuck": ("        local want = not on and mount.sec or false", "        local want = mount.sec"),
    "switch_dead": ('    arsenal_pages.open("catalog")', "    -- nothing"),
    "page_not_pressed": ("    theme.set_active(self.page_workbench, true)\n", ""),
    "back_dead": ('        pda:SetActiveSubdialog("eptLauncher")', "        -- nowhere"),
    "pending_kept": ("    local want = pending\n    pending = nil\n    SINGLETON:Reset(want)", "    local want = pending\n    SINGLETON:Reset(want)"),
    # arsenal_pages
    "router_all": ("        if section == PAGES.workbench.tab then", "        if true then"),
    "router_unsafe": ("            local ok, ui = pcall(ui_arsenal_workbench.get_ui)", "            local ok, ui = true, ui_arsenal_workbench.get_ui()"),
    "router_no_varargs": ("        return orig(section, ...)", "        return orig(section)"),
    "router_twice": ("    if wrapped or not (pda and pda.set_active_subdialog) then return end", "    if not (pda and pda.set_active_subdialog) then return end"),
    "open_no_item": ("        ui_arsenal_workbench.show_next(sec, id)", "        -- forgotten"),
    "open_flat_ignored": ("    if flat_cat or flat_wb then", "    if false then"),
    "no_customize": ("    ui_arsenal.add_action(\"workbench\", {", "    local _ = ({"),
}

PAGES_MUTANTS = {"router_all", "router_unsafe", "router_no_varargs", "router_twice", "open_no_item", "open_flat_ignored", "no_customize"}


def sizes():
    root = ET.fromstring(XML.split("?>", 1)[1])
    return {el.tag: [float(el.get(k, 0)) for k in ("x", "y", "width", "height")] for el in root}


def main():
    page, pages = PAGE, PAGES
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        if mutant in PAGES_MUTANTS:
            assert pages.count(old) == 1, old
            pages = pages.replace(old, new)
        else:
            assert page.count(old) == 1, old
            page = page.replace(old, new)
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(TW.STUBS, lua.table_from({k: lua.table_from(v) for k, v in TW.SECTIONS.items()}))
    lua.execute(WIDGETS, lua.table_from({k: lua.table_from(v) for k, v in sizes().items()}), lua.table_from(STRINGS))
    g = lua.globals()
    load = lua.eval("function(name, src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); _G[name] = env; f(); return env end")
    try:
        data = load("arsenal_workbench", DATA)
        data.on_game_start()
        ui = load("ui_arsenal_workbench", page)
    except L.LuaError as e:
        print("FAIL  the scripts load: %s" % e)
        print("\n1 failed")
        return 1
    # the catalog's page as far as the switch needs it
    lua.execute("""
ui_arsenal = { actions = {}, flat = nil }
function ui_arsenal.add_action(id, def) ui_arsenal.actions[id] = def end
function ui_arsenal.flat_window() return ui_arsenal.flat end
function ui_arsenal.open_flat() ui_arsenal.opened_flat = (ui_arsenal.opened_flat or 0) + 1 end
OPENED_PAGES = {}
PDA.SetActiveSubdialog = function(self, tab) OPENED_PAGES[#OPENED_PAGES + 1] = tab end
""")
    lua.execute("""
GUN = item("wpn_test", 7, { "up_firsta_t", "up_secona_t" })
GUN.parent_obj = ACTOR_OBJ
GUN.weapon_is_silencer_attached = function() return false end
GUN.weapon_is_grenadelauncher_attached = function() return false end
SUIT = item("suit_x", 3)
SUIT.parent_obj = ACTOR_OBJ
CARRIED = { SUIT, GUN, item("itm_basickit", 50), item("upgr_w_1_internal", 51), item("upgr_w_2_external", 52, nil, 2) }
STASHED = {}
BY_ID[7], BY_ID[3] = GUN, SUIT
WORLD = { [7] = "wpn_test", [3] = "suit_x" }
""")

    try:
        page_ = ui.get_ui()
    except L.LuaError as e:
        print("FAIL  the page builds: %s" % e)
        print("\n1 failed")
        return 1
    check(page_ is not None, "the page builds, every element in the layout")
    try:
        steps(lua, g, ui, data, page_, pages, load, check)
    except L.LuaError as e:
        check(False, "every step runs: %s" % str(e).splitlines()[0])
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


def steps(lua, g, ui, data, page_, pages, load, check):

    def texts(item_list):
        return [(it.key, it.name.text, it.count and it.count.text) for it in item_list.values()]

    rows = texts(page_.list["items"])
    check(rows == [(None, "Carried", None), ("id:7", "test", None), ("id:3", "suit", None)],
          "the list: carried, guns before suits: %s" % rows)
    check(page_.cur.key == "id:7" and page_.title.text == "test" and page_.list.sel == 1,
          "the first item shown, its row selected: %s" % page_.cur.key)
    check(page_.page_workbench.active is True, "the switch shows this page pressed")

    def forms():
        return [f for f in page_.tree_view.content.values()]

    fs = forms()
    idx = [f.children[1].text for f in fs]
    check(idx == ["1", "2", "3", "4", "5"], "a form per row of the tree, numbered: %s" % idx)

    def slot(r, c):
        return page_.forms[r].slots[c]

    s11, s12, s21 = slot(1, 1), slot(1, 2), slot(2, 1)
    check(s11.pic.tex == "icon_up_firsta_t" and s11.mark.shown is True and s11.mark.tex == "ui_inGame2_workshop_upgr_green",
          "an installed upgrade: its picture, marked green")
    check(s12.mark.shown is True and s12.mark.tex == "ui_inGame2_workshop_upgr_dark" and "@110" in str(s12.pic.tcolor),
          "the other of its pair: shut, dark, dimmed")
    check(slot(1, 3).mark.shown is False and slot(2, 2).btn.shown is False, "an open upgrade unmarked; an empty place hidden")
    check((s21.pic.x, s21.pic.y) == (32, 26 + 25) and (slot(1, 1).pic.x, slot(1, 1).pic.y) == (32, 26)
          and (slot(1, 4).pic.x, slot(1, 4).pic.y) == (176, 76),
          "cells where the toolkit puts them, a lone one between its pair's places: %s" % ((s21.pic.x, s21.pic.y),))
    check(s11.num.text == "1" and s11.num.color == "good" and slot(1, 3).num.text == "2"
          and slot(1, 5).num.text == "0" and slot(1, 5).num.color == "danger",
          "each cell's kit with how many are held, red at none: %s %s %s" % (s11.num.text, slot(1, 3).num.text, slot(1, 5).num.text))

    def card_rows():
        """(name, now, arrow, planned, planned's color) a row"""
        box = page_.card.content[1] if page_.card.content and len(page_.card.content) else None
        rows, cur = [], None
        for c in (box.children.values() if box else []):
            if c.path == "wb_card_name":
                cur = [c.text, None, None, None, None]
                rows.append(cur)
            elif c.path == "wb_card_now" and cur:
                cur[1] = c.text
            elif c.path == "wb_card_to" and cur:
                cur[2] = c.text
            elif c.path == "wb_card_plan" and cur:
                cur[3], cur[4] = c.text, c.color
        return [tuple(r) for r in rows]

    ct = card_rows()
    check(ct[:2] == [("ui_inv_accuracy", None, None, "72 perc", None), ("ui_inv_rate_of_fire", None, None, "600 rpm", None)],
          "the card now: a value the plan leaves alone in the last column; names without the game's color codes: %s"
          % ct[:2])

    # a click plans: the row, the card, the kits follow
    page_.cb["wb_cell_1_5"]()
    plan = data.plan_of(7, "wpn_test")[0]
    check(sorted(plan.keys()) == ["up_firstc_t", "up_firste_t"], "a click plans it and what it needs: %s" % sorted(plan.keys()))
    check(page_.rows["id:7"].count.text == "+2", "the list counts the plan: %s" % page_.rows["id:7"].count.text)
    ct = card_rows()
    check(len(ct) > 1 and ct[0] == ("ui_inv_accuracy", "72 perc", STRINGS["st_arsenal_wb_to"], "74 perc", "good"),
          "the card: now, the arrow, then planned, green when better: %s" % ct[:1])
    check(any(r[4] == "danger" for r in ct) and ct[1][1] is None, "worse planned values red; an unchanged one alone: %s" % ct)
    kits = [(c.num.text, c.num.color) for c in page_.kit_cells.values() if c.num.shown]
    check(kits == [("1/2", "good"), ("1/0", "danger")], "the kits the plan takes, needed/held: %s" % kits)
    check(slot(1, 3).mark.tex == "ui_inGame2_workshop_upgr_yellow", "planned: yellow")
    check(page_.btn_clear.enabled is True and page_.btn_install.enabled is True,
          "a plan and a toolkit: Clear and Install: %s %s %s" % (page_.btn_clear.enabled, page_.btn_install.enabled,
                                                               page_.install_why))
    page_.cb["wb_cell_1_3"]()
    check(len(data.plan_of(7, "wpn_test")[0]) == 0, "a click on a planned one takes it out, and what only it opened")

    # a click refused: the reason in the details
    page_.cb["wb_cell_1_2"]()
    info = [c.text for c in page_.info.content[1].children.values()]
    check(len(data.plan_of(7, "wpn_test")[0]) == 0 and "name_up_firstb_t" in info[0] and "Not with" in info[1],
          "a click it cannot take: nothing planned, the details say why: %s" % info[:2])

    # the details follow the cursor
    g.HOVER = slot(1, 3).btn
    page_.Update(page_)
    info = [c.text for c in page_.info.content[1].children.values()]
    check(len(info) >= 4 and info[0] == "name_up_firstc_t" and info[1] == "Click to plan it."
          and info[2].startswith("Kit: kit_2_external") and "line prop_dispersion of s_firstc" in info,
          "the upgrade under the cursor: name, state, kit, its lines: %s" % info)
    g.HOVER = None
    page_.Update(page_)
    info = [c.text for c in page_.info.content[1].children.values()]
    check(info and info[0].startswith("Click upgrades"), "away from the tree: the plan: %s" % info[:1])

    # a second visit: marked red, told
    page_.cb["wb_cell_4_3"]()
    check(slot(4, 3).mark.tex == "ui_inGame2_workshop_upgr_red" and slot(5, 3).mark.tex == "ui_inGame2_workshop_upgr_yellow",
          "the upgrade for a second visit red, the rest yellow")
    info = [c.text for c in page_.info.content[1].children.values()]
    check(any("second visit" in x for x in info), "and the details say so: %s" % info)

    # attachments: a gun shows them, cycling through what fits
    att = [(r.lbl.shown, r.btn.shown, r.btn.text) for r in page_.att_rows.values()]
    check(att[0][1] is False and att[2][1] is True and att[2][2] == "None", "a gun: the launcher the plan mounts: %s" % att)
    page_.cb["wb_att_3"]()
    check(data.plan_of(7, "wpn_test")[1].launcher == "gl_up" and page_.att_rows[3].btn.text == "gl_up",
          "a click attaches it to the plan: %s" % page_.att_rows[3].btn.text)
    page_.cb["wb_att_3"]()
    check(data.plan_of(7, "wpn_test")[1].launcher is None, "and off again")

    # Clear
    page_.cb.wb_clear()
    check(len(data.plan_of(7, "wpn_test")[0]) == 0 and page_.rows["id:7"].count.text == "", "Clear empties the plan")
    check(page_.btn_install.enabled is False, "nothing planned: no Install")

    # Install: the toolkit's handoff, only when it can go
    lua.execute("INSTALLS = {}; arsenal_workbench.install = function(id, sec, plan) INSTALLS[#INSTALLS + 1] = { id = id, sec = sec } end")
    page_.cb.wb_install()
    check(len(g.INSTALLS) == 0, "Install with nothing planned does nothing")
    page_.cb["wb_cell_1_3"]()
    page_.cb.wb_install()
    check(len(g.INSTALLS) == 1 and g.INSTALLS[1].id == 7, "Install hands the item to the toolkit")

    # more kinds of kit than frames: the last frame counts the rest
    data.set_plan(7, "wpn_test", lua.eval("""{ up_firstc_t = true, up_firstf_t = true, up_seconc_t = true, up_secone_t = true,
        up_thirda_t = true, up_fourta_t = true, up_fourtd_t = true, up_fourte_t = true, up_fiftha_t = true,
        up_fifthd_t = true }"""), None)
    ui.show_next(None, 7)
    page_ = ui.get_ui()
    shown = [c.num.text for c in page_.kit_cells.values() if c.back.shown]
    check(len(shown) == 6 and shown[5] == "+2" and len(page_.kits) == 7,
          "seven kinds of kit: five shown, the last frame counts two more: %s" % shown)
    data.set_plan(7, "wpn_test", lua.eval("{ up_firstc_t = true }"), None)

    # the suit: no attachments, its own card
    page_.list.sel = 2
    page_.cb.wb_list()
    check(page_.cur.key == "id:3" and all(r.btn.shown is False for r in page_.att_rows.values()), "a suit: no attachments")
    page_.list.sel = 0
    page_.cb.wb_list()
    check(page_.cur.key == "id:3" and page_.list.sel == 2, "a heading picks nothing: %s %s" % (page_.cur.key, page_.list.sel))

    # Customize: a model from the catalog, under its heading; one carried, that one
    ui.show_next("wpn_own")
    page_ = ui.get_ui()
    rows = texts(page_.list["items"])
    check(rows[-2:] == [(None, "From the catalog", None), ("sec:wpn_own", "own", None)] and page_.cur.key == "sec:wpn_own",
          "a model from the catalog: under its heading, shown: %s" % rows)
    check(page_.btn_install.enabled is False, "a model is planned only")
    check(rows[1] == ("id:7", "test", "+1"), "the list counts each item's plan as it fills: %s" % (rows[1],))
    # a scope: each that fits, then as it is (none now)
    seen, labels = [], []
    lua.execute("SEC.scope_a.inv_name = 'Scope A (rail)'; SEC.scope_b.inv_name = 'Scope B w/ red dot'")
    for _ in range(3):
        page_.cb["wb_att_1"]()
        seen.append(data.plan_of(None, "wpn_own")[1].scope)
        labels.append(page_.att_rows[1].btn.text)
    check(seen == ["scope_a", "scope_b", None], "the scope steps through what fits, then back: %s" % seen)
    check(labels == ["Scope A", "Scope B", "None"], "long names shortened on their buttons: %s" % labels)
    # a gun carried before the one asked for: the one asked for is picked, not the first
    lua.execute("OWN = item('wpn_own', 4); OWN.parent_obj = ACTOR_OBJ; table.insert(CARRIED, OWN); BY_ID[4] = OWN; WORLD[4] = 'wpn_own'")
    ui.show_next("wpn_test")
    page_ = ui.get_ui()
    check(page_.cur.key == "id:7" and page_.entries[1].key == "id:4",
          "a model the player carries: the carried one: %s" % page_.cur.key)
    page_.list.sel = 3
    page_.cb.wb_list()
    page_ = ui.get_ui()
    check(page_.cur.key == "id:3", "asked once: the next opening keeps the item picked since: %s" % page_.cur.key)
    # a plan made stale (the item has since got one of its upgrades): checked when shown, and kept so
    data.set_plan(7, "wpn_test", lua.eval("{ up_firsta_t = true, up_firstc_t = true }"), None)
    ui.show_next(None, 7)
    page_ = ui.get_ui()
    check(sorted(data.plan_of(7, "wpn_test")[0].keys()) == ["up_firstc_t"],
          "an item's plan is checked against it when shown: %s" % sorted(data.plan_of(7, "wpn_test")[0].keys()))

    # the switch, Back
    lua.execute("arsenal_pages = { open = function(p) LAST_OPEN = p end }")
    page_.cb.page_catalog()
    check(g.LAST_OPEN == "catalog", "the switch opens the catalog")
    page_.cb.btn_back()
    check(g.OPENED_PAGES[len(g.OPENED_PAGES)] == "eptLauncher", "Back goes to the launcher")
    callbacks = page_.ncb
    check(max(callbacks.values()) == 1, "each callback registered once, however often the page fills: %s" % max(callbacks.values()))

    # arsenal_pages: the switch and the router
    lua.execute("arsenal_pages = nil")
    try:
        pg = load("arsenal_pages", pages)
        pg.on_game_start()
    except L.LuaError as e:
        check(False, "arsenal_pages loads: %s" % e)
        return
    act = g.ui_arsenal.actions.workbench
    check(act is not None and act.label == "st_arsenal_wb_customize" and act.show("wpn_own") is True
          and act.show("wpn_plain") is False, "Customize on the catalog's pages that Workbench can plan for")
    lua.execute("""
ORIG_CALLS = {}
pda = { set_active_subdialog = function(section, a, b) ORIG_CALLS[#ORIG_CALLS + 1] = { section, a, b }; return "other page" end }
""")
    g.callbacks.on_game_load()
    first = g.pda.set_active_subdialog
    g.callbacks.on_game_load()
    check(lua.eval("function(a, b) return a == b end")(first, g.pda.set_active_subdialog), "wrapped once")
    r = g.pda.set_active_subdialog("eptWorkbench")
    check(r is not None and r.list is not None and r.forms is not None, "the router: Workbench's section is its page")
    r = g.pda.set_active_subdialog("eptTasks", 1, 2)
    calls = [list(c.values()) for c in g.ORIG_CALLS.values()]
    check(r == "other page" and calls == [["eptTasks", 1, 2]], "any other section passes down whole, once: %s" % calls)
    lua.execute("ui_arsenal_workbench.get_ui = function() error('boom') end")
    n = len(g.logs)
    r = g.pda.set_active_subdialog("eptWorkbench")
    check(r is None and len(g.logs) == n + 1, "a page that fails: nothing, logged")
    lua.execute("PDA.shown = true; OPENED_PAGES = {}")
    lua.execute("ui_arsenal_workbench.get_ui = function() return 'page' end")
    act.run("wpn_own")
    check(list(g.OPENED_PAGES.values()) == ["eptWorkbench"], "Customize opens Workbench's section")
    lua.execute("NEXT = nil; ui_arsenal_workbench.show_next = function(sec, id) NEXT = sec end")
    act.run("wpn_own")
    check(g.NEXT == "wpn_own", "on that model")
    lua.execute("ui_arsenal.flat = { Close = function() CLOSED = true end }; FLAT_WB = 0; "
                "ui_arsenal_workbench.open_flat = function() FLAT_WB = FLAT_WB + 1 end")
    pg.open("workbench", "wpn_own")
    check(g.CLOSED is True and g.FLAT_WB == 1, "in the flat window: the catalog's closes, Workbench's opens")



if __name__ == "__main__":
    sys.exit(main())
