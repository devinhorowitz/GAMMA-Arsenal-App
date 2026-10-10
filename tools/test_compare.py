"""Compare, Arsenal's third page: arsenal_compare.script (what is compared, and the rows) and
ui_arsenal_compare.script (the page), under LuaJIT with stand-ins for the engine's widgets,
arsenal_data and the inventory's stat card.

Checks: what compares with what (guns, suits, helmets; not a knife, a round or a gun without a
card, nor a model whose stats the player has not studied); the catalog's button filling the
left, then the right, then replacing the right or the side Change picked, a model of another
kind starting over; the line the catalog shows for each case; Swap, Clear, and what can no
longer be compared dropped; the rows (the card's in its order, then the facts, the better value
by the right direction, the upgraded value only where the formula gives the card's own); and the
page: every element in the layout, the panels and their hints, the mirrored rows with the better
side green, the bands, a row of text as tall as its longer side, Swap, Clear, Change, the switch,
Back, the flat window, the footer, and its geometry.

    python test_compare.py            the real scripts
    python test_compare.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "..", "gamedata")
DATA = io.open(os.path.join(GD, "scripts", "arsenal_compare.script"), encoding="latin-1").read()
PAGE = io.open(os.path.join(GD, "scripts", "ui_arsenal_compare.script"), encoding="latin-1").read()
XML = io.open(os.path.join(GD, "configs", "ui", "ui_arsenal.xml"), encoding="cp1251").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(GD, "configs", "text", "eng", "st_arsenal.xml"), encoding="cp1251").read(),
                          re.S))

STUBS = r"""
local SIZES, STRINGS = ...
-- a widget: records what was set on it
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
-- 18 a line, about 8 wide a character, as letterica16 wraps in its box
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
function W:GetCheck() return self.checked == true end
function W:SetCheck(v) self.checked = v == true end
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
-- luabind's class, enough for a script: class "Name" (Base) with __init and super()
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
ui_events = { BUTTON_CLICKED = 1, LIST_ITEM_SELECT = 2, LIST_ITEM_CLICKED = 3, WINDOW_KEY_PRESSED = 6 }
function vector2() return { set = function(self, x, y) self.x, self.y = x, y; return self end } end
function Frect() return { set = function(self, a, b, c, d) self.r = { a, b, c, d }; return self end } end
function GetARGB(a, r, g, b) return string.format("%d,%d,%d,%d", a, r, g, b) end
ALIVE = true
db = { actor = { alive = function() return ALIVE end } }
-- MCM's "PDA notifications", on until a case turns it off; its jailbreak, off; the credit line
NEWS_ON = true
JAILBREAK = false
arsenal_mcm = { flat_key = function() return DIK_keys.DIK_F7 end,
    credit = function() return "Arsenal v1.3.0 by Windwalker" end,
    news = function() return NEWS_ON end,
    set_news = function(on) NEWS_ON = on end,
    jailbreak = function() return JAILBREAK end }
arsenal_theme = { argb = function(role, a) return a and (role .. "@" .. a) or role end,
                  set_active = function(btn, on) btn.active = on end }
utils_xml = { is_widescreen = function() return true end }
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
PDA_SECTION = nil
ActorMenu = { get_pda_menu = function() return { SetActiveSubdialog = function(self, s) PDA_SECTION = s end } end }
OPENED = {}
arsenal_pages = { open = function(p) OPENED[#OPENED + 1] = p end }

-- the mod's strings, and the game's the card rows name (one with the color codes and the colon
-- the card's own names carry)
local T = {}
for k, v in pairs(STRINGS) do T[k] = v end
T.ui_inv_accuracy = "%c[255,238,196,112]Accuracy:"
T.ui_inv_handling, T.ui_inv_rate_of_fire, T.ui_ammo_count = "Handling", "Fire Rate", "Rounds in magazine"
T.ui_inv_drag, T.ui_inv_recoil = "Drag", "Recoil"
T.ui_inv_outfit_fire_wound_protection, T.ui_inv_outfit_burn_protection = "Bullet", "Burn"
T.ui_inv_outfit_artefact_count, T.ui_inv_outfit_speed = "Artefacts", "Speed"
T.st_perc, T.st_stat_rpm, T.st_kg = "%", "RPM", "kg"
-- the engine's takes a string only
game = { translate_string = function(k) assert(type(k) == "string", "translate_string: not a string"); return T[k] or k end }

-- the catalog: models of every kind; the Fort-17 has two variants; the flare gun has no card
VARIANT, ENTRY = {}, {}
local function model(cat, name, variants)
    local e = { cat = cat, name = name, variants = {} }
    for _, v in ipairs(variants) do
        local var = { sec = v[1], name = v[2] or name, entry = e }
        table.insert(e.variants, var)
        VARIANT[v[1]] = var
        ENTRY[v[1]] = e
    end
    e.sec = e.variants[1].sec
end
model("rifles", "AK-74", { { "wpn_ak74" } })
model("rifles", "AKM", { { "wpn_akm" } })
model("pistols", "Fort-17", { { "wpn_fort", "Fort-17 (reliability 89%)" }, { "wpn_fort17", "Fort-17 (reliability 91%)" } })
model("snipers", "SVD Dragunov Sniper Rifle of the Northern Expedition", { { "wpn_svd" } })
model("pistols", "Flare Gun", { { "wpn_flare" } })
model("melee", "Knife", { { "wpn_knife" } })
model("ammo", "5.45x39 FMJ", { { "ammo_545" } })
model("medium", "SEVA", { { "sci_suit" } })
model("exo", "Exoskeleton", { { "exo_suit" } })
model("helmets", "Sphere M12", { { "helm_sphere" } })
local NO_CARD = { wpn_flare = true, wpn_knife = true, ammo_545 = true }

-- the card's rows: a gun's (recoil shown the other way round, as a row with sign_inverse is),
-- a suit's or helmet's
local function row(index, name, unit, extra)
    local gr = { index = index, name = name, unit = unit }
    for k, v in pairs(extra or {}) do gr[k] = v end
    return gr
end
GUN_ROWS = {
    accuracy = row(1, "ui_inv_accuracy", "st_perc"),
    handling = row(2, "ui_inv_handling", "st_perc"),
    fire_rate = row(4, "ui_inv_rate_of_fire", "st_stat_rpm"),
    ammo_mag_size = row(5, "ui_ammo_count", ""),
    drag = row(102, "ui_inv_drag", "st_perc"),
    recoil = row(104, "ui_inv_recoil", "", { sign_inverse = true }),
}
ARMOR_ROWS = {
    fire_wound_protection = row(10, "ui_inv_outfit_fire_wound_protection", "st_perc", { sign = true }),
    burn_protection = row(20, "ui_inv_outfit_burn_protection", "st_perc", { sign = true }),
    artefact_count = row(100, "ui_inv_outfit_artefact_count", ""),
    speed_modifier = row(120, "ui_inv_outfit_speed", "%"),
}
-- the card's texts as utils_ui writes them ("value unit", a trailing space without a unit);
-- none where the card shows no row (no gun here has handling; the AKM no drag)
CARD = {
    wpn_ak74 = { accuracy = "72 %", fire_rate = "600 RPM", ammo_mag_size = "30 ", drag = "-5 %", recoil = "40 " },
    wpn_akm = { accuracy = "68 %", fire_rate = "600 RPM", ammo_mag_size = "30 ", recoil = "35 " },
    wpn_fort17 = { accuracy = "75 %", fire_rate = "450 RPM", ammo_mag_size = "13 ", recoil = "55 " },
    wpn_svd = { accuracy = "90 %", fire_rate = "300 RPM", ammo_mag_size = "10 ", recoil = "20 " },
    sci_suit = { fire_wound_protection = "+40 %", burn_protection = "+41 %", artefact_count = "3 ", speed_modifier = "95 %" },
    exo_suit = { fire_wound_protection = "+70 %", burn_protection = "+20 %", artefact_count = "5 ", speed_modifier = "80 %" },
    helm_sphere = { fire_wound_protection = "+30 %", burn_protection = "+10 %" },
}
-- fully upgraded, { max, the value as it is by the formula }: the AKM's accuracy formula gives
-- 70 where its card shows 68, so it has no max; the AK-74's drag has one, but drag is no row the
-- gun formulas cover; nothing for the suits' speed
MAX = {
    wpn_ak74 = { accuracy = { 80, 72 }, fire_rate = { 600, 600 }, ammo_mag_size = { 30, 30 }, recoil = { 50, 40 },
                 drag = { -3, -5 } },
    wpn_akm = { accuracy = { 75, 70 }, fire_rate = { 650, 600 }, ammo_mag_size = { 30, 30 }, recoil = { 30, 35 } },
    sci_suit = { fire_wound_protection = { 48, 40 }, burn_protection = { 41, 41 }, artefact_count = { 3, 3 } },
    exo_suit = { fire_wound_protection = { 75, 70 }, burn_protection = { 25, 20 }, artefact_count = { 5, 5 } },
    helm_sphere = { fire_wound_protection = { 35, 30 } },
}
utils_ui = { get_stats_string_value = function(obj, sec, gr, stat, to_text)
    assert(obj == nil, "a live item")
    local c = CARD[sec]
    return c and c[stat], false
end }
arsenal_data = {
    ARMOR = { light = true, medium = true, heavy = true, exo = true, helmets = true },
    get = function(sec) return ENTRY[sec] end,
    variant_of = function(sec) return VARIANT[sec] end,
    has_stat_card = function(sec)
        local e = ENTRY[sec]
        if e and arsenal_data.ARMOR[e.cat] then return true end
        return e ~= nil and not NO_CARD[sec]
    end,
    icon = function(sec) return "ui_icons_" .. sec, { x1 = 0, y1 = 0, w = 100, h = 50 } end,
    stat_rows = function(live, sec)
        assert(live == false, "live rows")
        local t = arsenal_data.ARMOR[ENTRY[sec].cat] and ARMOR_ROWS or GUN_ROWS
        local out = {}
        for stat, gr in pairs(t) do out[#out + 1] = { stat = stat, gr = gr } end
        table.sort(out, function(a, b) return a.gr.index < b.gr.index end)
        return out
    end,
    max_stat = function(sec, stat)
        local m = MAX[sec] and MAX[sec][stat]
        if m then return m[1], m[2] end
    end,
    hit_power = function(sec) return ({ wpn_ak74 = 0.45, wpn_akm = 0.5, wpn_svd = 1.2 })[sec] or 0 end,
    jam_chance = function(sec) return ({ wpn_ak74 = { base = 0.003, worn = 0.014 }, wpn_akm = { base = 0 } })[sec] end,
    fire_modes = function(sec) return ({ wpn_svd = "1" })[sec] or "1 / A" end,
    weight = function(sec) return ({ wpn_ak74 = 3.3, wpn_akm = 3.6, sci_suit = 5, exo_suit = 15.004, helm_sphere = 2 })[sec] or 1 end,
    kg = function(x) return math.floor(x * 100 + 0.5) / 100 end,
    ammo_names = function(sec)
        return ({ wpn_ak74 = { "5.45x39 FMJ", "5.45x39 AP", "5.45x39 HP" }, wpn_akm = { "7.62x39 FMJ" } })[sec] or {}
    end,
    penetration = function(sec) return ({ sci_suit = { stops = 23, of = 43 }, exo_suit = { stops = 40, of = 43 } })[sec] end,
}
-- arsenal_intel: none until a case sets one up; a model in UNSTUDIED is not studied
UNSTUDIED = {}
function with_intel()
    arsenal_intel = { studied = function(e) return not UNSTUDIED[e.sec] end }
end
"""

DATA_MUTANTS = {
    "kind_helmet": ('    if e.cat == "helmets" then return "helmet" end\n', ""),
    "kind_card": ('    return arsenal_data.has_stat_card(sec) and "gun" or nil', '    return "gun"'),
    "studied_ignored": ("    return not arsenal_intel or arsenal_intel.studied(e) == true", "    return true"),
    "plan_in": ('    if sec == left or sec == right then return "in" end\n', ""),
    "plan_kind": ('    if not left or kind_of(left) ~= kind_of(sec) then return "left", left, "left" end',
                  '    if not left then return "left", left, "left" end'),
    "plan_want": ('    if want == "left" then return "replace", left, "left" end\n', ""),
    "add_want_kept": ("        if side == \"left\" then left = sec else right = sec end\n        want = nil\n",
                      "        if side == \"left\" then left = sec else right = sec end\n"),
    "add_restart_keeps_right": ("        left, right, want = sec, nil, nil", "        left = sec"),
    "swap_one": ("    if left and right then\n        left, right = right, left", "    if true then\n        left, right = right, left"),
    "validate_left": ("    if left and not comparable(left) then left = nil end\n", ""),
    "validate_no_shift": ("    if not left and right then\n        left, right = right, nil\n    end\n", ""),
    "line_next": ('        if not right then return T("st_arsenal_cmp_next_" .. kind_of(sec)) end\n', ""),
    "line_uncut": ('    if #s > n then s = s:sub(1, n - 3):gsub("%s+$", "") .. "..." end\n', ""),
    "line_parens": ('    s = s:gsub("%s*%b()%s*$", "")\n', ""),
    "line_restart": ('        return other and T("st_arsenal_cmp_restart") or ""', '        return ""'),
    "rows_codes": ('    return (tostring(s or ""):gsub("%%c%[[^%]]*%]", ""):match("^%s*(.-)[%s:]*$"))',
                   '    return tostring(s or "")'),
    "rows_max_unchecked": ("        if okm and m and b and b == out.num then", "        if okm and m and b then"),
    "rows_max_guns_all": ("            local maxed = armor or MAXED[row.stat] == true", "            local maxed = true"),
    "rows_armor_max": ("            local maxed = armor or MAXED[row.stat] == true", "            local maxed = MAXED[row.stat] == true"),
    "rows_inverse": ("                local lower = row.gr.sign_inverse == true", "                local lower = false"),
    "rows_both_missing": ("            local b = r and card_side(r, row, maxed) or nil\n            if a or b then",
                          "            local b = r and card_side(r, row, maxed) or nil\n            if true then"),
    "rows_no_card": ("    if arsenal_data.has_stat_card(l) then", "    if false then"),
    "facts_jam_higher": ('    { "jam", "st_arsenal_cmp_jam", true },', '    { "jam", "st_arsenal_cmp_jam" },'),
    "facts_gun_weight_higher": ('    { "weight", "st_arsenal_wb_weight", true },\n    { "rounds"',
                                '    { "weight", "st_arsenal_wb_weight" },\n    { "rounds"'),
    "facts_armor_weight_higher": ('    { "stops", "st_arsenal_cmp_stops" },\n    { "weight", "st_arsenal_wb_weight", true },',
                                  '    { "stops", "st_arsenal_cmp_stops" },\n    { "weight", "st_arsenal_wb_weight" },'),
    "facts_jam_worn": ("        if j.worn then", "        if false then"),
    "facts_wide": ("wide = f[4] == true", "wide = false"),
}

PAGE_MUTANTS = {
    "cmp_tab_not_pressed": ("    theme.set_active(self.page_compare, true)\n", ""),
    "cmp_tab_dead": ('function ComparePDA:OnCatalog()\n    arsenal_pages.open("catalog")', "function ComparePDA:OnCatalog()\n    -- nothing"),
    "cmp_no_better": ('        c:SetTextColor(theme.argb(best == here and "good" or role))', "        c:SetTextColor(theme.argb(role))"),
    "cmp_no_dash": ('        c:SetText("-")', '        c:SetText("")'),
    "cmp_max_dashed": ('                if c[1] == "cmp_max_l" or c[1] == "cmp_max_r" then', "                if false then"),
    "cmp_right_dashes": ('{ "cmp_val_r", row.r and row.r.text, "r", row.better, r ~= nil, "body" }',
                         '{ "cmp_val_r", row.r and row.r.text, "r", row.better, true, "body" }'),
    "cmp_no_band": ('        local band = i % 2 == 0 and xml:InitStatic("cmp_band", box) or nil', "        local band = nil"),
    "cmp_band_short": ("            band:SetWndSize(vector2():set(band:GetWidth(), h))\n", ""),
    "cmp_wide_unplaced": ("                t:SetWndPos(vector2():set(p.x, y + p.y))", "                t:SetWndPos(vector2():set(p.x, p.y))"),
    "cmp_wide_flat": ("                h = math.max(h, t:GetHeight() + 2)", "                h = ROW_H"),
    "cmp_box_unsized": ("    box:SetWndSize(vector2():set(box:GetWidth(), y))\n", ""),
    "cmp_swap_unrefreshed": ("    arsenal_compare.swap()\n    self:Fill()", "    arsenal_compare.swap()"),
    "cmp_clear_dead": ("    arsenal_compare.clear()\n", ""),
    "cmp_change_stays": ('    arsenal_compare.pick(side)\n    arsenal_pages.open("catalog")', "    arsenal_compare.pick(side)"),
    "cmp_change_no_cancel": ("    if arsenal_compare.wanted() == side then\n        arsenal_compare.pick(nil)",
                             "    if false then\n        arsenal_compare.pick(nil)"),
    "cmp_change_unmarked": ("    theme.set_active(p.change, arsenal_compare.wanted() == p.side)\n", ""),
    "cmp_no_validate": ("    arsenal_compare.validate()\n", ""),
    "cmp_hint_both": ('    self:FillPanel(self.panels.right, r, kind and ("st_arsenal_cmp_pick_" .. kind))',
                      '    self:FillPanel(self.panels.right, r, kind and ("st_arsenal_cmp_pick_" .. kind) or "st_arsenal_cmp_none")'),
    "cmp_swap_always": ("    self.btn_swap:Enable(l ~= nil and r ~= nil)", "    self.btn_swap:Enable(true)"),
    "cmp_icon_hidden": ("    st:SetTextureColor(GetARGB(255, 255, 255, 255))\n    st:Show(true)", "    st:SetTextureColor(GetARGB(255, 255, 255, 255))"),
    "cmp_icon_kept": ("        p.icon:Show(false)\n", ""),
    "cmp_head_always": ("    self.head:Show(l ~= nil)", "    self.head:Show(true)"),
    "cmp_rows_unguarded": ("    local ok, rows = pcall(arsenal_compare.rows, l, r)", "    local ok, rows = true, arsenal_compare.rows(l, r)"),
    "cmp_flat_offset": ("local x, y = self.flat and PDA_X or 0, self.flat and PDA_Y or 0", "local x, y = 0, 0"),
    "cmp_no_escape": ("if dik == DIK_keys.DIK_ESCAPE or dik == arsenal_mcm.flat_key() then", "if dik == arsenal_mcm.flat_key() then"),
    "cmp_back_pda": ("    if self.flat then\n        self:Close()\n        return\n    end\n    local pda", "    local pda"),
    "cmp_dead_open": ("if not (db.actor and db.actor:alive()) then return nil end", "if not db.actor then return nil end"),
    "cmp_silence_unpainted": ("function ComparePDA:Reset()\n    self:PaintFooter()\n", "function ComparePDA:Reset()\n"),
    "cmp_silence_inverted": ("arsenal_mcm.set_news(not self.silence:GetCheck())", "arsenal_mcm.set_news(self.silence:GetCheck())"),
    "cmp_no_credit": ("    self.credit:SetText(arsenal_mcm.credit())\n", ""),
    "cmp_jailbreak_always": ("local jb = arsenal_mcm.jailbreak() == true", "local jb = true"),
    "cmp_side_x": ("local SIDE_X = { left = 28, right = 418 }", "local SIDE_X = { left = 28, right = 410 }"),
}
MUTANTS = dict(DATA_MUTANTS, **PAGE_MUTANTS)


def sizes():
    root = ET.fromstring(XML.split("?>", 1)[1])
    return {el.tag: [float(el.get(k, 0)) for k in ("x", "y", "width", "height")] for el in root}


def main():
    data, page = DATA, PAGE
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        if mutant in DATA_MUTANTS:
            assert data.count(old) == 1, old
            data = data.replace(old, new)
        else:
            assert page.count(old) == 1, old
            page = page.replace(old, new)
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    sz = sizes()
    used = sorted(set(re.findall(r'xml:Init\w+\("([\w:]+)"', page)))
    missing = [u for u in used if u not in sz]
    check(not missing, "every element the page asks for is in the layout: %s" % (missing or "%d used" % len(used)))

    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS, lua.table_from({k: lua.table_from(v) for k, v in sz.items()}), lua.table_from(STRINGS))
    g = lua.globals()
    load = lua.eval("function(name, src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                    "setfenv(f, env); _G[name] = env; f(); return env end")
    try:
        cmp = load("arsenal_compare", data)
        ui = load("ui_arsenal_compare", page)
    except L.LuaError as e:
        print("FAIL  the scripts load: %s" % e)
        print("\n1 failed")
        return 1
    for part in (data_steps, row_steps, page_steps):
        try:
            part(lua, g, cmp, ui, check, sz, page)
        except L.LuaError as e:
            check(False, "%s runs: %s" % (part.__name__, str(e).splitlines()[0]))
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


def data_steps(lua, g, cmp, ui, check, sz, src):
    S = STRINGS
    kinds = {s: cmp.kind_of(s) for s in ("wpn_ak74", "wpn_fort17", "sci_suit", "exo_suit", "helm_sphere", "wpn_knife",
                                         "ammo_545", "wpn_flare", "wpn_none")}
    check(kinds == {"wpn_ak74": "gun", "wpn_fort17": "gun", "sci_suit": "suit", "exo_suit": "suit",
                    "helm_sphere": "helmet", "wpn_knife": None, "ammo_545": None, "wpn_flare": None, "wpn_none": None},
          "guns, suits and helmets; not a knife, a round, a gun without a card or what the catalog lacks: %s" % kinds)

    def sides():
        return tuple(cmp.sides())

    none = [cmp.add(s) for s in ("wpn_knife", "ammo_545", "wpn_flare", "wpn_none")]
    check(none == [None] * 4 and sides() == (None, None) and cmp.line("wpn_knife") == "",
          "what has no card goes in nowhere, and has no line: %s %s" % (none, sides()))
    check(cmp.line("wpn_ak74") == "", "nothing compared: the first has no line yet: %r" % cmp.line("wpn_ak74"))
    what = cmp.add("wpn_ak74")
    check(what == "left" and sides() == ("wpn_ak74", None), "the first goes left: %s %s" % (what, sides()))
    check(cmp.line("wpn_ak74") == S["st_arsenal_cmp_next_gun"], "alone, its line asks for another gun: %r"
          % cmp.line("wpn_ak74"))
    check(cmp.line("wpn_svd") == "vs. AK-74", "another gun's line names what it joins: %r" % cmp.line("wpn_svd"))
    what = cmp.add("wpn_ak74")
    check(what == "in" and sides() == ("wpn_ak74", None), "the same again: in already, nothing moves: %s %s" % (what, sides()))
    what = cmp.add("wpn_svd")
    check(what == "right" and sides() == ("wpn_ak74", "wpn_svd"), "the second goes right: %s %s" % (what, sides()))
    check(cmp.line("wpn_ak74") == S["st_arsenal_cmp_in"] and cmp.line("wpn_svd") == S["st_arsenal_cmp_in"],
          "both in: %r %r" % (cmp.line("wpn_ak74"), cmp.line("wpn_svd")))
    ln = cmp.line("wpn_akm")
    check(ln == "Replaces SVD Dragunov Sniper Rifle...", "a third replaces the right, its long name cut: %r" % ln)
    what = cmp.add("wpn_fort17")
    check(what == "replace" and sides() == ("wpn_ak74", "wpn_fort17"), "and does: %s %s" % (what, sides()))
    check(cmp.name("wpn_fort17") == "Fort-17 (reliability 91%)" and cmp.line("wpn_akm") == "Replaces Fort-17",
          "the variant's name on the page, without its tag in the line: %r %r" % (cmp.name("wpn_fort17"), cmp.line("wpn_akm")))
    cmp.pick("left")
    check(cmp.wanted() == "left" and cmp.line("wpn_akm") == "Replaces AK-74", "Change on the left: the next replaces it: %r"
          % cmp.line("wpn_akm"))
    what = cmp.add("wpn_akm")
    check(what == "replace" and sides() == ("wpn_akm", "wpn_fort17") and cmp.wanted() is None,
          "and does, once: %s %s %s" % (what, sides(), cmp.wanted()))
    what = cmp.add("wpn_svd")
    check(what == "replace" and sides() == ("wpn_akm", "wpn_svd"), "the next replaces the right again: %s" % (sides(),))
    # another kind starts over, and a pending Change goes with the old comparison
    check(cmp.line("sci_suit") == S["st_arsenal_cmp_restart"], "a suit's line: it starts over: %r" % cmp.line("sci_suit"))
    cmp.pick("left")
    what = cmp.add("sci_suit")
    check(what == "left" and sides() == ("sci_suit", None) and cmp.wanted() is None,
          "a suit with guns compared: it alone, on the left: %s %s %s" % (what, sides(), cmp.wanted()))
    check(cmp.line("helm_sphere") == S["st_arsenal_cmp_restart"], "a helmet is no suit: %r" % cmp.line("helm_sphere"))
    what = cmp.add("exo_suit")
    check(what == "right" and sides() == ("sci_suit", "exo_suit"), "two suits: %s" % (sides(),))
    cmp.swap()
    check(sides() == ("exo_suit", "sci_suit"), "Swap: %s" % (sides(),))
    cmp.clear()
    cmp.add("sci_suit")
    cmp.swap()
    check(sides() == ("sci_suit", None), "one alone stays on the left: %s" % (sides(),))
    cmp.pick("right")
    cmp.clear()
    check(sides() == (None, None) and cmp.wanted() is None, "Clear empties it: %s %s" % (sides(), cmp.wanted()))

    # what the player knows: a model not studied goes in nowhere; one no longer known drops out,
    # a lone right moving left
    lua.execute("with_intel(); UNSTUDIED.wpn_akm = true")
    check(cmp.comparable("wpn_akm") is False and cmp.add("wpn_akm") is None and cmp.line("wpn_akm") == "",
          "not studied: not in, no line")
    check(cmp.comparable("wpn_ak74") is True, "studied: in")
    cmp.add("wpn_ak74")
    cmp.add("wpn_svd")
    lua.execute("UNSTUDIED.wpn_svd = true")
    cmp.validate()
    check(sides() == ("wpn_ak74", None), "the right unknown again: dropped: %s" % (sides(),))
    lua.execute("UNSTUDIED.wpn_svd = nil")
    cmp.add("wpn_svd")
    lua.execute("UNSTUDIED.wpn_ak74 = true")
    cmp.validate()
    check(sides() == ("wpn_svd", None), "the left unknown again: the right moves left: %s" % (sides(),))
    lua.execute("arsenal_intel = nil; UNSTUDIED = {}")
    cmp.clear()


def row_steps(lua, g, cmp, ui, check, sz, src):
    def rows(l, r):
        out = []
        for row in cmp.rows(l, r).values():
            def side(s):
                return None if s is None else (s.text, s.num, s.max_text)
            out.append((row.label, side(row.l), side(row.r), row.better, row.max_better, bool(row.wide)))
        return out

    got = rows("wpn_ak74", "wpn_akm")
    want = [("Accuracy", ("72 %", 72, "80 %"), ("68 %", 68, None), "l", None, False),
            ("Fire Rate", ("600 RPM", 600, "600 RPM"), ("600 RPM", 600, "650 RPM"), None, "r", False),
            ("Rounds in magazine", ("30", 30, "30"), ("30", 30, "30"), None, None, False),
            ("Drag", ("-5 %", -5, None), None, None, None, False),
            ("Recoil", ("40", 40, "50"), ("35", 35, "30"), "r", "r", False),
            ("Hit power", ("0.45", 0.45, None), ("0.5", 0.5, None), "r", None, False),
            ("Jam chance", ("0.3%, worn 1.7%", 0.017, None), ("0%", 0, None), "r", None, False),
            ("Fire modes", ("1 / A", None, None), ("1 / A", None, None), None, None, False),
            ("Weight", ("3.3 kg", 3.3, None), ("3.6 kg", 3.6, None), "l", None, False),
            ("Rounds", ("5.45x39 FMJ, 5.45x39 AP, 5.45x39 HP", None, None), ("7.62x39 FMJ", None, None), None, None, True)]
    for i, (a, b) in enumerate(zip(got, want)):
        if a != b:
            print("      row %d: got  %s\n             want %s" % (i + 1, a, b))
    check(got == want,
          "two guns: the card's rows in its order (none neither has), each side's text and number, upgraded only where "
          "the formula gives the card's own value; then hit power, jams, fire modes, weight and rounds; the better "
          "marked higher, lower for recoil shown the other way round, jams and weight (%d rows)" % len(got))
    got = rows("sci_suit", "exo_suit")
    want = [("Bullet", ("+40 %", 40, "+48 %"), ("+70 %", 70, "+75 %"), "r", "r", False),
            ("Burn", ("+41 %", 41, "+41 %"), ("+20 %", 20, "+25 %"), "l", "l", False),
            ("Artefacts", ("3", 3, "3"), ("5", 5, "5"), "r", "r", False),
            ("Speed", ("95 %", 95, None), ("80 %", 80, None), "l", None, False),
            ("Rounds stopped", ("23 of 43", 23, None), ("40 of 43", 40, None), "r", None, False),
            ("Weight", ("5 kg", 5, None), ("15 kg", 15, None), "l", None, False)]
    for i, (a, b) in enumerate(zip(got, want)):
        if a != b:
            print("      row %d: got  %s\n             want %s" % (i + 1, a, b))
    check(got == want, "two suits: every row upgraded where the formula agrees, signed as the card signs it; rounds "
          "stopped, weight (%d rows)" % len(got))
    got = rows("wpn_ak74", None)
    check(len(got) == 10 and all(r[2] is None and r[3] is None and r[4] is None for r in got)
          and got[0][1] == ("72 %", 72, "80 %"),
          "one gun: its rows alone, nothing marked: %s" % (got[:1],))
    got = rows("helm_sphere", None)
    check([r[0] for r in got] == ["Bullet", "Burn", "Weight"],
          "a helmet: only the rows it has, no rounds stopped where there is no telling: %s" % [r[0] for r in got])
    check(rows("wpn_knife", None) == [], "what has no card: no rows")


def parse(page):
    """the rows on the page: { label, y, band, cells: { path: widget } }, and the box"""
    content = list(page.rows_view.content.values()) if page.rows_view.content else []
    if not content:
        return [], None
    box = content[0]
    rows, band = [], None
    for c in box.children.values():
        if c.path == "cmp_band":
            band = c
        elif c.path == "cmp_label":
            rows.append({"label": c.text, "y": c.y, "band": band, "cells": {}, "label_w": c})
            band = None
        elif rows:
            rows[-1]["cells"][c.path] = c
    return rows, box


def page_steps(lua, g, cmp, ui, check, sz, src):
    S = STRINGS
    cmp.clear()
    page = ui.get_ui()
    left, right = page.panels.left, page.panels.right
    check(page.page_compare.active is True, "the switch shows this page pressed")
    check(page.title.text == "" and left.empty.shown is True and left.empty.text == S["st_arsenal_cmp_none"]
          and right.empty.shown is True and right.empty.text == "" and left.name.shown is False
          and left.change.shown is False and left.icon.shown is False,
          "nothing compared: what to do, once, in the left panel: %r / %r" % (left.empty.text, right.empty.text))
    rows, box = parse(page)
    check(page.btn_swap.enabled is False and page.btn_clear.enabled is False and page.head.shown is False and box is None,
          "and no Swap, no Clear, no headings, no rows")

    cmp.add("wpn_ak74")
    page = ui.get_ui()
    check(page.title.text == "Comparing guns" and left.name.text == "AK-74" and left.name.shown is True
          and left.change.shown is True and left.empty.shown is False and left.icon.shown is True
          and left.icon.tex == "ui_icons_wpn_ak74",
          "one gun: its title, name, icon and Change: %r %r %r" % (page.title.text, left.name.text, left.icon.tex))
    check(right.empty.shown is True and right.empty.text == S["st_arsenal_cmp_pick_gun"] and right.name.shown is False
          and right.change.shown is False, "the right panel asks for another gun: %r" % right.empty.text)
    rows, box = parse(page)
    lone = [(r["cells"].get("cmp_val_l").text if r["cells"].get("cmp_val_l") else None,
             r["cells"].get("cmp_val_r").text if r["cells"].get("cmp_val_r") else None) for r in rows[:5]]
    check(page.head.shown is True and len(rows) == 10 and lone[0] == ("72 %", "") and lone[3] == ("-5 %", "")
          and rows[0]["cells"]["cmp_val_l"].color == "body" and rows[0]["cells"]["cmp_max_l"].text == "80 %",
          "its rows, the right side blank, nothing marked: %s" % lone)
    check(page.btn_swap.enabled is False and page.btn_clear.enabled is True, "one: Clear, no Swap")

    cmp.add("wpn_akm")
    page = ui.get_ui()
    rows, box = parse(page)

    def cells(i):
        c = rows[i]["cells"]
        return tuple((c[k].text, c[k].color) if k in c else None for k in ("cmp_max_l", "cmp_val_l", "cmp_val_r", "cmp_max_r"))
    acc, rate, drag, recoil, weight = cells(0), cells(1), cells(3), cells(4), cells(8)
    check(acc == (("80 %", "dim"), ("72 %", "good"), ("68 %", "body"), ("", None)),
          "the better value green; an upgraded value where known, blank where not: %s" % (acc,))
    check(rate == (("600 RPM", "dim"), ("600 RPM", "body"), ("600 RPM", "body"), ("650 RPM", "good")),
          "a tie unmarked; the better upgraded value green: %s" % (rate,))
    check(drag[2] == ("-", "dim") and drag[1] == ("-5 %", "body"), "a side without the row: a dash: %s" % (drag,))
    check(recoil[2][1] == "good" and weight[1][1] == "good", "lower is better where it should be: %s %s" % (recoil, weight))
    wide = rows[9]
    tl, tr = wide["cells"].get("cmp_text_l"), wide["cells"].get("cmp_text_r")
    check(wide["label"] == "Rounds" and tl is not None and tr is not None and tl.text == "5.45x39 FMJ, 5.45x39 AP, 5.45x39 HP"
          and tr.text == "7.62x39 FMJ" and "cmp_val_l" not in wide["cells"],
          "rounds as text across each side's columns: %s" % ((tl and tl.text, tr and tr.text),))
    ys = [r["y"] for r in rows]
    check(ys == [i * 20 for i in range(10)] and tl.y == 181 and tr.y == 181 and box.h == 180 + 38,
          "rows 20 apart; the text one placed on its row and as tall as its longer side, the box with it: %s %s %s"
          % (ys, tl.y, box.h))
    bands = [(i, r["band"].y, r["band"].h, r["band"].tcolor) for i, r in enumerate(rows) if r["band"] is not None]
    check([b[0] for b in bands] == [1, 3, 5, 7, 9] and all(b[1] == rows[b[0]]["y"] for b in bands)
          and bands[-1][2] == 38 and bands[0][2] == 20 and all(b[3] == "bright@36" for b in bands),
          "a faint band behind every other row, as tall as its row: %s" % bands)
    check(page.btn_swap.enabled is True and page.btn_clear.enabled is True, "two: Swap and Clear")
    lbl = rows[0]["label_w"]
    check(lbl.text == "Accuracy", "the row's name without the card's color codes and colon: %r" % lbl.text)

    page.cb.cmp_swap()
    rows, box = parse(page)
    check(left.name.text == "AKM" and right.name.text == "AK-74" and cells(0)[1] == ("68 %", "body")
          and cells(0)[2] == ("72 %", "good"), "Swap: sides and rows change places: %s" % (cells(0),))

    # Change: the next model goes to that side, so to the catalog; pressed while it waits, a
    # second click takes it back
    n = len(g.OPENED)
    page.cb.cmp_change_right()
    check(cmp.wanted() == "right" and len(g.OPENED) == n + 1 and g.OPENED[n + 1] == "catalog",
          "Change: that side next, and the catalog: %s %s" % (cmp.wanted(), list(g.OPENED.values())[n:]))
    page = ui.get_ui()
    check(right.change.active is True and left.change.active is False, "back on the page, the side waiting pressed")
    page.cb.cmp_change_right()
    check(cmp.wanted() is None and right.change.active is False and len(g.OPENED) == n + 1,
          "a second click takes it back and stays: %s" % cmp.wanted())

    # the switch, Back
    n = len(g.OPENED)
    page.cb.page_catalog()
    page.cb.page_workbench()
    check(list(g.OPENED.values())[n:] == ["catalog", "workbench"], "the switch opens the catalog and Workbench: %s"
          % list(g.OPENED.values())[n:])
    page.cb.btn_back()
    check(g.PDA_SECTION == "eptLauncher", "Back goes to the launcher")

    # Clear: empty again
    page.cb.cmp_clear()
    rows, box = parse(page)
    check(cmp.sides() == (None, None) and box is None and left.empty.shown is True and page.title.text == "",
          "Clear empties the page")
    cmp.add("wpn_ak74")
    page = ui.get_ui()
    check(left.icon.shown is True, "emptied and filled again, the icon shows")

    # what can no longer be compared drops out when the page opens
    cmp.add("wpn_svd")
    lua.execute("with_intel(); UNSTUDIED.wpn_svd = true")
    page = ui.get_ui()
    check(cmp.sides() == ("wpn_ak74", None) and right.empty.shown is True, "a model no longer known drops out as the page opens")
    lua.execute("arsenal_intel = nil; UNSTUDIED = {}")

    # rows that fail: logged, the page stays
    lua.execute("ROWS = arsenal_compare.rows; arsenal_compare.rows = function() error('boom') end")
    n = len(g.logs)
    try:
        page = ui.get_ui()
        ok = True
    except L.LuaError:
        ok = False
    rows, box = parse(page)
    check(ok and box is None and len(g.logs) == n + 1, "rows that fail: logged, no rows, the page up")
    lua.execute("arsenal_compare.rows = ROWS")

    check(max(page.ncb.values()) == 1, "each callback registered once, however often the page fills: %s" % max(page.ncb.values()))

    # the flat window
    g.ALIVE = False
    check(ui.open_flat() is None, "no window while the player is dead")
    g.ALIVE = True
    flat = ui.open_flat()
    kids = [c.path for c in flat.children.values()]
    check(flat.IsShown(flat) and list(flat.rect.values())[:2] == [112, 34] and kids[:2] == ["flat_bezel", "flat_caption"]
          and ui.flat_window() is not None,
          "the key's window: the frame first, placed as the PDA places its pages: %s" % list(flat.rect.values()))
    flat.OnKeyboard(flat, g.DIK_keys.DIK_A, g.ui_events.WINDOW_KEY_PRESSED)
    shown_a = flat.IsShown(flat)
    ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_ESCAPE, g.ui_events.WINDOW_KEY_PRESSED)
    check(shown_a and ret and not flat.IsShown(flat) and ui.flat_window() is None, "another key leaves it; Escape closes it")
    ui.open_flat()
    flat.OnKeyboard(flat, g.DIK_keys.DIK_F7, g.ui_events.WINDOW_KEY_PRESSED)
    check(not flat.IsShown(flat), "the key closes it again")
    ui.open_flat()
    g.PDA_SECTION = None
    flat.cb.btn_back()
    check(not flat.IsShown(flat) and g.PDA_SECTION is None, "Back closes it, leaving the PDA alone")

    footer(g, ui, check)
    geometry(sz, src, check)


def footer(g, ui, check):
    """Silence, the jailbreak lamp and the credit line, as on the other pages"""
    page = ui.get_ui()
    sil = page.silence
    check(sil.checked is False and page.credit.text == "Arsenal v1.3.0 by Windwalker",
          "the footer: Silence unticked while the messages are on, and the credit line: %s, %s" % (sil.checked, page.credit.text))
    sil.checked = True               # the engine ticks the box, then calls back
    page.cb.silence()
    check(g.NEWS_ON is False, "ticking Silence turns the messages off")
    sil.checked = False
    page.cb.silence()
    check(g.NEWS_ON is True, "unticking it turns them on")
    g.NEWS_ON = False
    check(ui.get_ui().silence.checked is True, "silenced in MCM, the box is ticked at the next open")
    g.NEWS_ON = True
    check(ui.get_ui().silence.checked is False, "and unticked once they are on again")
    check(page.jailbreak.shown is False and page.jailbreak_lbl.shown is False, "no jailbreak lamp while it is off")
    g.JAILBREAK = True
    p = ui.get_ui()
    check(p.jailbreak.shown is True and p.jailbreak_lbl.shown is True and p.jailbreak.tcolor == "warn"
          and p.jailbreak_lbl.color == "warn", "jailbroken: the lamp and its label lit in the warning color")
    g.JAILBREAK = False
    p = ui.get_ui()
    check(p.jailbreak.shown is False, "and out again")


def geometry(sz, src, check):
    """The panels side by side in the content box, the rows mirrored around the gap between them,
    everything above the footer's rule, and the header row shared with the other pages in order."""
    lx, rx = (int(v) for v in re.search(r"local SIDE_X = \{ left = (\d+), right = (\d+) \}", src).groups())
    bg = sz["cmp_icon_bg"]
    mid = (lx + bg[2] + rx) / 2
    check(lx == 28 and rx + bg[2] == 792 and rx - (lx + bg[2]) == 16 and mid == 410,
          "two panels across the content box, 16 apart, the gap's middle at %s" % mid)
    nm, ch, em = sz["cmp_name"], sz["cmp_change"], sz["cmp_empty"]
    check(nm[0] + nm[2] <= ch[0] - 4 and ch[0] + ch[2] <= bg[2] and em[0] >= 0 and em[0] + em[2] <= bg[2],
          "the name, Change and the hint inside a panel, side by side")
    rule, foot = sz["cmp_rule"][1], sz["rule_foot"][1]
    head, rows = sz["cmp_head"], sz["cmp_rows"]
    check(bg[1] + bg[3] <= nm[1] - 4 and nm[1] + nm[3] <= rule - 4 and ch[1] + ch[3] <= rule - 4
          and head[1] > rule and head[1] + head[3] <= rows[1] and rows[1] + rows[3] <= foot - 2,
          "top to bottom: the icon, the name and Change, the rule, the headings, the rows, above the footer's rule")
    x0 = rows[0]
    lab = sz["cmp_label"]
    centre = x0 + lab[0] + lab[2] / 2

    def right_edge(k):
        return x0 + sz[k][0] + sz[k][2]

    def left_edge(k):
        return x0 + sz[k][0]
    mirrored = (centre == mid and mid - right_edge("cmp_val_l") == left_edge("cmp_val_r") - mid
                and mid - right_edge("cmp_max_l") == left_edge("cmp_max_r") - mid
                and sz["cmp_val_l"][2] == sz["cmp_val_r"][2] and sz["cmp_max_l"][2] == sz["cmp_max_r"][2])
    check(mirrored and right_edge("cmp_max_l") < left_edge("cmp_val_l") and right_edge("cmp_val_l") < left_edge("cmp_label")
          and right_edge("cmp_label") < left_edge("cmp_val_r") and right_edge("cmp_val_r") < left_edge("cmp_max_r")
          and right_edge("cmp_max_r") <= x0 + rows[2] - 16,
          "the columns mirrored around the gap, none over the next, the last clear of the scroll bar")
    check(left_edge("cmp_text_l") == left_edge("cmp_max_l") and right_edge("cmp_text_l") == right_edge("cmp_val_l")
          and left_edge("cmp_text_r") == left_edge("cmp_val_r") and right_edge("cmp_text_r") == right_edge("cmp_max_r"),
          "a row of text over both of its side's columns")
    order = [["page_catalog", "page_workbench", "page_compare", "cmp_title", "cmp_swap", "cmp_clear", "btn_back"],
             ["page_catalog", "page_workbench", "page_compare", "found_count", "action_btn", "btn_back"],
             ["page_catalog", "page_workbench", "page_compare", "wb_title", "wb_install", "btn_back"]]
    over = [(row[i], row[i + 1]) for row in order for i in range(len(row) - 1)
            if sz[row[i]][0] + sz[row[i]][2] > sz[row[i + 1]][0]]
    out = [k for row in order for k in row if sz[k][0] < 28 or sz[k][0] + sz[k][2] > 792]
    check(not over and not out, "each page's header in order, nothing over the next, inside the content box: %s %s"
          % (over, out))


if __name__ == "__main__":
    sys.exit(main())
