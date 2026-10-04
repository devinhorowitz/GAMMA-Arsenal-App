"""Smoke test for ui_arsenal.script under LuaJIT, against stand-ins for the engine's widgets,
arsenal_data and arsenal_collection. Checks that every layout element the script asks for is
in ui_arsenal.xml (in game a missing one returns nil and the page dies), and that the page
fills: the count line, categories with found/total, one row per gun model, dim while none of
its variants is found, the "found only" filter, switching categories, an entry built and
handed to its scroll view once complete, a long name that wraps without covering the line
below it, a model's page (stat rows that list each variant's value where they differ, the
variants with when and where each was found, the found variant's icon), and a knife's page
without a stat card.

    python test_ui.py            the real script
    python test_ui.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "..", "gamedata")
SRC = io.open(os.path.join(GD, "scripts", "ui_arsenal.script"), encoding="latin-1").read()
XML = io.open(os.path.join(GD, "configs", "ui", "ui_arsenal.xml"), encoding="cp1251").read()
STRINGS = dict(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                          io.open(os.path.join(GD, "configs", "text", "eng", "st_arsenal.xml"), encoding="cp1251").read(),
                          re.S))

STUBS = r"""
local SIZES, STRINGS = ...
calls = {}
-- a widget: records what was set on it
local W = {}
W.__index = W
function new_widget(path, parent)
    local s = SIZES[path] or { 0, 0, 10, 10 }
    local w = setmetatable({ path = path, x = s[1], y = s[2], w = s[3], h = s[4], children = {} }, W)
    if parent and parent.children then table.insert(parent.children, w) end
    return w
end
function W:SetText(t) self.text = t end
function W:GetText() return self.text end
function W:SetTextColor(c) self.color = c end
function W:SetWndPos(v) self.x, self.y = v.x, v.y end
function W:GetWndPos() return { x = self.x, y = self.y } end
function W:SetWndSize(v) self.w, self.h = v.x, v.y end
function W:SetWndRect(r) end
function W:GetWidth() return self.w end
function W:GetHeight() return self.h end
-- 18 a line, about 8 wide a character, as letterica16 wraps in its box
function W:AdjustHeightToText()
    self.h = 18 * math.max(1, math.ceil(#(self.text or "") * 8 / math.max(self.w, 1)))
end
function W:InitTexture(t) self.tex = t end
function W:SetTextureRect(r) self.rect = r end
function W:SetStretchTexture(b) end
function W:SetTextureColor(c) self.tcolor = c end
function W:Show(b) self.shown = b end
function W:SetAutoDelete(b) self.autodelete = b end
function W:GetCheck() return self.checked == true end
-- list box
function W:AddExistingItem(item) self.items = self.items or {}; table.insert(self.items, item) end
function W:RemoveAll() self.items = {}; self.sel = nil end
function W:GetSize() return #(self.items or {}) end
function W:SetSelectedIndex(i) self.sel = i end
function W:GetSelectedItem() return self.sel and self.items[self.sel + 1] end
-- scroll view
function W:Clear() self.content = {} end
function W:AddWindow(w, auto) self.content = self.content or {}; table.insert(self.content, w) end
function W:ScrollToBegin() end

-- ui_arsenal.xml must have every element asked for; utils.xml is the game's
CScriptXmlInit = function()
    local x = {}
    function x:ParseFile(f) self.file = f end
    local function init(kind) return function(self, path, parent)
        if self.file == "ui_arsenal.xml" and not SIZES[path] then
            error("no element '" .. path .. "' in the layout", 2)
        end
        local w = new_widget(path, parent)
        if self.file == "utils.xml" then w.h = 18 end
        return w
    end end
    x.InitTextWnd, x.InitStatic, x.InitCheck = init(), init(), init()
    x.Init3tButton, x.InitListBox, x.InitScrollView = init(), init(), init()
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
CUIListBoxItem = setmetatable({ children = {} }, { __index = W })
CUIListBoxItem.__index = CUIListBoxItem
CUIScriptWnd = setmetatable({}, { __index = W })
function CUIScriptWnd.Update(self) end
function CUIScriptWnd:Register(w, name) self.registered = self.registered or {}; self.registered[name] = w end
function CUIScriptWnd:AddCallback(name, ev, fn, obj) self.cb = self.cb or {}; self.cb[name] = function() fn(obj) end end
function CUIScriptWnd:SetWndRect(r) self.rect = r.r end
function CUIScriptWnd:ShowDialog(b) self.dialog_shown = true end
function CUIScriptWnd:HideDialog() self.dialog_shown = false end
function CUIScriptWnd:IsShown() return self.dialog_shown == true end
function CUIScriptWnd.OnKeyboard(self, dik, action) return false end
DIK_keys = { DIK_ESCAPE = 1, DIK_F7 = 65, DIK_A = 30 }
db = { actor = { alive = function() return actor_alive end } }
actor_alive = true
arsenal_mcm = { flat_key = function() return DIK_keys.DIK_F7 end }

function vector2() return { set = function(self, x, y) self.x, self.y = x, y; return self end } end
function Frect() return { set = function(self, a, b, c, d) self.r = { a, b, c, d }; return self end } end
function GetARGB(a, r, g, b) return string.format("%d,%d,%d,%d", a, r, g, b) end
ui_events = { BUTTON_CLICKED = 1, LIST_ITEM_SELECT = 2, WINDOW_KEY_PRESSED = 6 }
local T = { st_arsenal_found_count = "Found %s of %s", st_arsenal_found_on = "Found %s in %s",
            st_arsenal_not_found = "Not found yet", st_arsenal_cat_pistols = "Pistols",
            st_arsenal_cat_rifles = "Rifles", st_arsenal_cat_melee = "Melee", st_arsenal_fire_modes = "Fire modes",
            st_arsenal_variants = "Variants:", st_arsenal_variant_found = "%s, found %s in %s",
            st_prop_weight = "Weight", st_kg = "kg", ui_ammo_types = "Ammo", l01_escape = "Cordon",
            ui_inv_rate_of_fire = "Fire Rate" }
for k, v in pairs(STRINGS) do T[k] = T[k] or v end
T.st_perc, T.st_stat_rpm = "%", "RPM"
game = { translate_string = function(k) return T[k] or k end }
pda_section = nil
ActorMenu = { get_pda_menu = function() return { SetActiveSubdialog = function(self, s) pda_section = s end } end }
utils_xml = { is_widescreen = function() return true end, screen_ratio = function() return 0.75 end }
-- the card: accuracy is the same for every gun, the fire rate differs between Fort-17s
local RPM = { wpn_fort = "400 RPM", wpn_fort17 = "450 RPM" }
utils_ui = {
    get_stats_xml = function(handler, obj, sec, gr, stat)
        local w = new_widget("stats_box", handler); w.h = 18; w.stat = stat; w.sec = sec; return w
    end,
    get_stats_string_value = function(obj, sec, gr, stat)
        if stat == "fire_rate" then return (RPM[sec] or "600 RPM") .. " ", false end
        return "75 %", false
    end,
}
arsenal_theme = { argb = function(role) return role end, markup = function(role) return "<" .. role .. ">" end }
logged = {}
function printf(fmt, ...) logged[#logged + 1] = string.format(fmt, ...) end

-- a gun model: { sec, name, variants }, its first variant's section as its key
local function model(name, variants)
    local e = { name = name, variants = variants, sec = variants[1].sec }
    for _, v in ipairs(variants) do v.entry = e end
    return e
end
local guns = {
    pistols = { model("PM", { { sec = "wpn_pm", name = "PM" } }),
                model("Fort-17", { { sec = "wpn_fort", name = "Fort-17 (reliability 89%)" },
                                   { sec = "wpn_fort17", name = "Fort-17 (reliability 91%)" } }),
                model("Ghost", { { sec = "wpn_ghost", name = "Ghost" } }) },
    rifles = { model("AK-74 Tactical Modernized Carbine of the Northern Expedition Special Forces Unit",
                     { { sec = "wpn_ak74", name = "AK-74" } }) },
    smgs = {},
    melee = { model("Knife", { { sec = "wpn_knife", name = "Knife" } }) },
    medium = { model("SEVA", { { sec = "sci_suit", name = "SEVA" } }) },
}
for c, l in pairs(guns) do for _, e in ipairs(l) do e.cat = c end end
found = { wpn_fort17 = { y = 2012, mo = 5, d = 14, lvl = "l01_escape" } }
-- what fits the Fort-17s: four scopes (one shared), a kit, a suppressor (built into the other
-- variant), a launcher
FIT = {
    wpn_fort = { scopes = { { sec = "kobra", name = "Kobra" } }, kits = {}, suppressors = {}, launchers = {},
                 builtin = { suppressor = true, laser = true } },
    wpn_fort17 = { scopes = { { sec = "kobra", name = "Kobra" }, { sec = "kobra2", name = "Kobra" }, { sec = "pka", name = "PK-A" },
                              { sec = "okp", name = "OKP-7" }, { sec = "ps01", name = "PSO-1" } },
                   kits = { { sec = "fkit", name = "Tactical Kit", makes = "Fort-17 Tactical" },
                            { sec = "ckit", name = "Camo Kit" } },
                   suppressors = { { sec = "pbs", name = "PBS-1", upgrade = true } },
                   launchers = { { sec = "gp25", name = "GP-25", ammo = { "VOG-25" } },
                                 { sec = "m203", name = "M203", ammo = { "M406" }, upgrade = true } },
                   lasers = { { sec = "lam", name = "LAM" } },
                   builtin = {} },
}
icons = {}
arsenal_data = {
    CATEGORIES = { "pistols", "smgs", "rifles", "melee", "medium" },
    ARMOR = { medium = true },
    has_stat_card = function(sec) return sec ~= "wpn_knife" end,
    list = function(c) return guns[c] or {} end,
    count = function() return 5 end,
    get = function(sec)
        for _, l in pairs(guns) do for _, e in ipairs(l) do
            for _, v in ipairs(e.variants) do if v.sec == sec then return e end end
        end end
    end,
    icon = function(sec) icons[#icons + 1] = sec; return "ui\\ui_icon_equipment", { x1 = 0, y1 = 0, w = 250, h = 100 } end,
    -- a gun's card rows; a suit's are the outfit card's
    stat_rows = function(live, sec)
        if sec == "sci_suit" then
            return { { stat = "fire_wound_protection", gr = { name = "ui_inv_outfit_fire_wound_protection", icon_p = "b", unit = "st_perc" } },
                     { stat = "burn_protection", gr = { name = "ui_inv_outfit_burn_protection", icon_p = "t", unit = "st_perc" } } }
        end
        return { { stat = "accuracy", gr = { name = "ui_inv_accuracy", icon_p = "a", unit = "st_perc" } },
                 { stat = "fire_rate", gr = { name = "ui_inv_rate_of_fire", icon_p = "r", unit = "st_stat_rpm" } } }
    end,
    -- fully upgraded: the Fort-17s' accuracy rises (the better variant's counts), nothing raises fire rate
    max_stat = function(sec, stat)
        if stat == "accuracy" and (sec == "wpn_fort" or sec == "wpn_fort17") then
            return (sec == "wpn_fort17") and 82 or 80, 75
        end
        if stat == "accuracy" and sec == "wpn_pm" then return 90, 70 end
        if sec == "sci_suit" then return (stat == "fire_wound_protection") and 90 or 75, 75 end
        if stat == "fire_rate" then
            local r = ({ wpn_fort = 400, wpn_fort17 = 450 })[sec] or 600
            return r, r
        end
    end,
    mags = function(sec)
        return sec == "wpn_fort17" and { { sec = "mag13", name = "Fort Magazine", rounds = 13 } } or {}
    end,
    -- the Fort-17's upgrades: a 9x19 conversion, burst fire
    upgrade_options = function(sec)
        if sec == "wpn_fort17" then
            return { calibres = { { "9x19 FMJ", "9x19 AP" } }, fire_modes = { "1 / 3 / A", "1 / A" } }
        end
        return { calibres = {}, fire_modes = {} }
    end,
    attachments = function(sec) return FIT[sec] or { scopes = {}, kits = {}, suppressors = {}, launchers = {}, builtin = {} } end,
    parts = function(sec)
        return sec == "wpn_fort17" and { { sec = "prt_b", name = "Barrel" }, { sec = "prt_t", name = "Trigger" } } or {}
    end,
    fire_modes = function() return "1 / A" end,
    weight = function() return 3.3 end,
    kg = function(x) return math.floor(x * 100 + 0.5) / 100 end,
    ammo_names = function() return { "5.45 FMJ" } end,
    description = function() return "A gun." end,
}
-- where to find them: the Fort-17s are carried, stashed, traded with Nimble, made of another gun
-- and in new-game kits; the PM is in stashes no level list names; the knife turns up nowhere
local ALL = { "novice", "trainee", "experienced", "professional", "veteran", "expert", "master", "legend" }
arsenal_data.RANKS = ALL
arsenal_data.FACTIONS = { "stalker", "dolg", "freedom", "csky", "ecolog", "killer", "army", "bandit", "monolith",
    "zombied", "renegade", "greh", "isg" }
local FORT = { wpn_fort = true, wpn_fort17 = true }
function arsenal_data.carriers(sec)
    -- a loadout naming the suit: a suit's page shows who wears it, not this
    if sec == "sci_suit" then return { { faction = "ecolog", ranks = ALL } } end
    if not FORT[sec] then return {} end
    return { { faction = "bandit", ranks = { "novice", "trainee", "professional", "expert", "legend" } },
             { faction = "stalker", ranks = { "experienced", "professional", "veteran", "legend" } },
             { faction = "isg", ranks = {}, special = true },
             { faction = "army", ranks = ALL } }
end
function arsenal_data.stashes(sec)
    if FORT[sec] then return { "l01_escape", "l02_garbage" } end
    if sec == "sci_suit" then return { "l08_yantar" } end
    if sec == "wpn_pm" then return {} end
end
-- both Fort-17s trade for the same gun; Nimble's own Fort-17 comes for either Fort-12
function arsenal_data.nimble(sec)
    if not FORT[sec] then return { gets = {}, from = {} } end
    return { gets = { { name = "Fort-17 Nimble", cost = 30000 } },
             from = sec == "wpn_fort17" and { { names = { "Fort-12", "Fort-12 (old)" }, cost = 45000 } } or {} }
end
function arsenal_data.repair_kits(sec)
    if sec == "sci_suit" then return { { sec = "sew_b", name = "Basic Sewing Kit" } } end
    return FORT[sec] and { { sec = "ck_p", name = "Type A Cleaning Kit" }, { sec = "tk_p", name = "Type A Repair Kit" } } or {}
end
-- who wears the SEVA: Ecologists of four ranks, a Duty story character; it drops half the time
-- from rating 1747 on (Rookie), or not at all when DROP_OFF is set
function arsenal_data.worn_by(sec)
    if sec ~= "sci_suit" then return {} end
    return { { faction = "ecolog", ranks = { "novice", "trainee", "experienced", "professional" } },
             { faction = "dolg", ranks = {}, special = true } }
end
function arsenal_data.armor_drop(sec)
    if DROP_OFF then return { off = true } end
    return { chance = 50, rank = 1747 }
end
function arsenal_data.rank_at(v) return v < 3999 and "novice" or "trainee" end
-- the Armor Exchange: Petrenko gives the SEVA for one of 12 suits; Sidorovich and the Owl give an
-- exoskeleton for it
-- what turns up: the Ghost never does, nor the PSO-1; the SEVA also turns up on Strelok (and a
-- story character whose name has no text) and from a workbench
function arsenal_data.obtainable(sec) return sec ~= "wpn_ghost" end
function arsenal_data.addon_turns_up(sec) return sec ~= "ps01" end
function arsenal_data.turns_up_model(sec)
    if sec == "sci_suit" then return { story = { "st_strelok_name", "GENERATE_NAME_x" }, craft = true } end
    if sec == "wpn_ak74" then return { trader = true } end
    return {}
end
function arsenal_data.exchange(sec)
    if sec ~= "sci_suit" then return { gets = {}, takes = {} } end
    return { gets = { { traders = { "Petrenko" }, faction = "dolg", cost = 10000, count = 12 } },
             takes = { { traders = { "Sidorovich", "Owl" }, faction = "stalker", cost = 45000, name = "Exoskeleton" } } }
end
-- the Fort-17s' camos: the base, one to discover (two factions drop it), one to discover (none
-- does), one discovered
function arsenal_data.camos(sec)
    if not FORT[sec] then return {} end
    return { { name = "Base", icon = "black", required = false, locked = false, factions = {} },
             { name = "Tan", icon = "tan", required = true, locked = true, factions = { "stalker", "bandit" } },
             { name = "Arctic", icon = "arctic", required = true, locked = true, factions = {} },
             { name = "Woodland", icon = "woodland", required = true, locked = false, factions = {} } }
end
-- R.I.S.K. on the Fort-17s: fire rate (the card agrees), accuracy (the card shows 75, not 70: left
-- out), one that leaves the card as it is, weight, damage, recoil (the card has no such row: left out)
function arsenal_data.risk_enhancements(sec)
    if not FORT[sec] then return {} end
    return { { family = "fire_rate", stat = "fire_rate", base = 450, low = 462, high = 690, worst = 210 },
             { family = "accuracy", stat = "accuracy", base = 70, low = 71, high = 72 },
             { family = "sway", stat = "accuracy", base = 75, low = 75, high = 75, worst = 75 },
             { family = "weight", stat = "weight", base = 1.1, low = 0, high = 0.9, worst = 3.1 },
             { family = "damage", stat = "damage", base = 0, low = 2, high = 40, worst = -40 },
             { family = "recoil", stat = "recoil", base = 50, low = 55, high = 60 } }
end
function arsenal_data.made_from(sec)
    return FORT[sec] and { { from = "Fort-12", kit = "Conversion Kit" } } or {}
end
function arsenal_data.starting_kits(sec)
    if not FORT[sec] then return {} end
    return { { factions = { "stalker", "bandit" }, points = 150 },
             { factions = arsenal_data.FACTIONS },
             { factions = { "dolg" }, points = 200, economies = { 1, 2 } } }
end
for k, v in pairs({ st_faction_stalker = "Loner", st_faction_bandit = "Bandit", st_faction_isg = "UNISG",
        st_faction_army = "Military", st_faction_dolg = "Duty", st_rank_novice = "Rookie", st_rank_trainee = "Trainee",
        st_rank_experienced = "Experienced", st_rank_professional = "Professional", st_rank_veteran = "Veteran",
        st_rank_expert = "Expert", st_rank_master = "Master", st_rank_legend = "Legend", st_econ_1 = "Tourist (Easy)",
        st_econ_2 = "Scavenger (Medium)", l02_garbage = "Garbage", l08_yantar = "Yantar", st_faction_ecolog = "Ecologist",
        st_strelok_name = "Strelok" }) do
    T[k] = v
end
local function first(e)
    for _, v in ipairs(e.variants) do if found[v.sec] then return found[v.sec] end end
end
arsenal_collection = {
    is_found = function(sec) return found[sec] ~= nil end,
    found_at = function(sec) return found[sec] end,
    entry_found = first,
    count_found = function(list)
        local n = 0
        for _, e in ipairs(list or {}) do if first(e) then n = n + 1 end end
        return list and n or 1
    end,
}
"""

MUTANTS = {
    "layout_name": ('xml:InitListBox("wpn_list", self)', 'xml:InitListBox("weapon_list", self)'),
    "name_wrap": ("line:SetWndPos(vector2():set(0, name:GetWndPos().y + math.max(name:GetHeight(), NAME_H)))",
                  "-- found line where the layout puts it"),
    "dim": ('(found and "body") or "dim"', '"body"'),
    "model_found": ("local found = arsenal_collection.entry_found(e) ~= nil",
                    "local found = arsenal_collection.is_found(e.sec)"),
    "card_always": ("if know and arsenal_data.has_stat_card(shown.sec) then", "if know then"),
    "filter": ("if listed(e) and (found or not only) then", "if listed(e) then"),
    "add_after": ("self.detail:AddWindow(entry, true)", "-- not added"),
    "no_combine": ("if #values < 2 then", "if true then"),
    "first_variant": ("            shown = v\n            break", "            break"),
    "no_variants": ("if know and #e.variants > 1 then", "if false then"),
    "unsorted": ("table.sort(nums, function(a, b) return (tonumber(a) or 0) < (tonumber(b) or 0) end)", "-- as found"),
    "no_max": ("    if mx then\n", "    if false then\n"),
    "max_always": ("if not best or best <= base then return nil end", "if not best then return nil end"),
    "one_row": ("if col == TILE_COLS or i == #items then", "if i == #items then"),
    "builtin_all": ("text(\"entry_line\", #names == #e.variants and", "text(\"entry_line\", true and"),
    "no_parts": ("if #parts > 0 then", "if false then"),
    "no_kits": ("for _, it in ipairs(fit.kits) do", "for _, it in ipairs({}) do"),
    "same_name": ("if not seen[it.sec] and not seen[key] then", "if not seen[it.sec] then"),
    "no_card_check": ("if shown == b then", "if true then"),
    "no_mags": ("    if #mags > 0 then", "    if false then"),
    "modes_extra": ("if not has[m] then extra[#extra + 1] = m end", "extra[#extra + 1] = m"),
    "no_conversions": ('text("entry_line", string.format(game.translate_string("st_arsenal_ammo_by_upgrade"), c), "dim")',
                       "-- not shown"),
    "no_after": ("sup[#sup + 1] = { sec = it.sec, name = it.name, note = it.upgrade and after or nil, never = it.never }",
                 "sup[#sup + 1] = { sec = it.sec, name = it.name, never = it.never }"),
    "flat_offset": ("local x, y = self.flat and PDA_X or 0, self.flat and PDA_Y or 0", "local x, y = 0, 0"),
    "no_bezel": ('xml:InitStatic("flat_bezel", self)', "-- no frame"),
    "no_escape": ("if dik == DIK_keys.DIK_ESCAPE or dik == arsenal_mcm.flat_key() then",
                  "if dik == arsenal_mcm.flat_key() then"),
    "back_pda": ("    if self.flat then\n        self:Close()\n        return\n    end\n    local pda", "    local pda"),
    "dead_open": ("if not (db.actor and db.actor:alive()) then return nil end", "if not db.actor then return nil end"),
    "no_laser_note": ('builtin_note(builtin.laser, "st_arsenal_builtin_laser", "st_arsenal_builtin_laser_on")',
                      "-- no note"),
    "camo_none": ("    if #camo_list > 0 then", "    if false then"),
    "camo_on": ("and string.format(game.translate_string(\"st_arsenal_camo_locked_on\"), factions_text(c.factions))",
                "and game.translate_string(\"st_arsenal_camo_locked\")"),
    "camo_found": ("                elseif c.required then\n                    note = game.translate_string(\"st_arsenal_camo_found\")\n",
                   ""),
    "camo_green": ("                elseif c.required then\n                    t:SetTextColor(theme.argb(\"good\"))\n", ""),
    "camo_ratio": ("                local w = h * ratio", "                local w = h"),
    "risk_check": ("agrees = ok and type(s) == \"string\" and tonumber(s:match(\"[-+]?%d+%.?%d*\")) == r.base",
                   "agrees = true"),
    "risk_card_only": ('local row, unit, agrees = card_rows[r.stat], "", false', 'local row, unit, agrees = card_rows[r.stat], "", true'),
    "risk_bad": ('s = string.format(game.translate_string("st_arsenal_risk_bad"), s, num(r.worst) .. u)', "-- no bad roll"),
    "risk_sign": ('local function num(x) return (signed and x > 0) and ("+" .. x) or tostring(x) end',
                  "local function num(x) return tostring(x) end"),
    "risk_none": ("    if #risk_rows > 0 then", "    if false then"),
    "risk_same": ("            if r.low == r.base and r.high == r.base then", "            if false then"),
    "risk_worst_base": ("            if r.worst and r.worst ~= r.base then", "            if r.worst then"),
    "no_repair": ("    if #kits > 0 then", "    if false then"),
    "where_heading": ('text("entry_heading", game.translate_string("st_arsenal_where"))', "-- no heading"),
    "where_ranges": ("while j < #ranks and at[ranks[j + 1]] == at[ranks[j]] + 1 do j = j + 1 end", "-- no ranges"),
    "where_every_rank": ("if #ranks == #arsenal_data.RANKS then", "if false then"),
    "where_special": ('if special then parts[#parts + 1] = game.translate_string("st_arsenal_special") end',
                      "-- no special"),
    "where_every_faction": ('if #list == #arsenal_data.FACTIONS then return game.translate_string("st_arsenal_every_faction") end',
                            "-- every faction named"),
    "where_no_source": ("    if not any then\n        line(game.translate_string(full and", "    if false then\n        line(game.translate_string(full and"),
    "armor_modes": ("if know and not armor and arsenal_data.has_stat_card(shown.sec) then",
                    "if know and arsenal_data.has_stat_card(shown.sec) then"),
    "armor_rows": ("for _, row in ipairs(arsenal_data.stat_rows(false, shown.sec)) do", "for _, row in ipairs(arsenal_data.stat_rows(false)) do"),
    "armor_worn": ("known_rows(armor and safe(arsenal_data.worn_by, shown.sec) or {}, fx.worn)", "known_rows({}, fx.worn)"),
    "armor_carried": ("known_rows((not armor) and safe(arsenal_data.carriers, shown.sec) or {}, fx.carried)",
                      "known_rows(safe(arsenal_data.carriers, shown.sec) or {}, fx.carried)"),
    "never_role": ('local role = (not arsenal_data.obtainable(e.sec) and "never") or (found and "body") or "dim"',
                   'local role = (found and "body") or "dim"'),
    "count_obtainable": ("            if arsenal_data.obtainable(e.sec) then\n                total = total + 1",
                         "            if true then\n                total = total + 1"),
    "never_line": ('        line(game.translate_string("st_arsenal_never"), "warn")\n', ""),
    "addon_never_note": ("            if it.never then\n", "            if false then\n"),
    "addon_hide": ("if up or not imm then", "if true then"),
    "listed": ("if listed(e) and (found or not only) then", "if found or not only then"),
    "new_mark": ("e.name .. (is_new(e) and new_mark() or \"\")", "e.name"),
    "cat_new": ("if listed(e) and is_new(e) then fresh = true end", "-- no mark"),
    "not_studied_note": ('        text("entry_line", game.translate_string("st_arsenal_not_studied"), "dim")\n', ""),
    "gate_fits": ("    -- what fits it, its camos, parts and repair kits, once it is studied\n    if know then",
                  "    -- what fits it, its camos, parts and repair kits, once it is studied\n    if true then"),
    "facts_rows": ("        if full then return rows end\n", ""),
    "facts_stash": ('        line(string.format(game.translate_string("st_arsenal_stashes_seen"), table.concat(names, ", ")))\n', ""),
    "facts_sold": ('        line(string.format(game.translate_string("st_arsenal_sold_at"), table.concat(names, ", ")))\n', ""),
    "kit_mine": ("            if f == mine then has = true end\n", ""),
    "where_unknown": ('line(game.translate_string(full and "st_arsenal_no_source" or "st_arsenal_where_unknown"), "dim")',
                      'line(game.translate_string("st_arsenal_no_source"), "dim")'),
    "learned_line": ("    elseif learned and learned.at then", "    elseif false then"),
    "viewed": ("    if arsenal_intel then arsenal_intel.viewed(e) end\n", ""),
    "known_header": ("    if immersive() then\n        self.found_count", "    if false then\n        self.found_count"),
    "story_names": ("            if t ~= n then names[#names + 1] = t end", "            names[#names + 1] = t"),
    "full_sources": ("    local up = full and safe(arsenal_data.turns_up_model, shown.sec) or {}",
                     "    local up = safe(arsenal_data.turns_up_model, shown.sec) or {}"),
    "armor_drop_rank": ("rank and string.format(game.translate_string(\"st_arsenal_drop_rank\")", "false and string.format(game.translate_string(\"st_arsenal_drop_rank\")"),
    "armor_drop_off": ("        if d and d.off then\n", "        if false then\n"),
    "armor_exchange": ("local ex = armor and safe(arsenal_data.exchange, shown.sec)", "local ex = nil"),
    "armor_max": ("if row.gr.track or not (MAXED[row.stat] or arsenal_data.ARMOR[e.cat]) then return nil end",
                  "if row.gr.track or not MAXED[row.stat] then return nil end"),
    "where_levels": ("line(#names > 0 and string.format(game.translate_string(\"st_arsenal_stashes_at\")",
                     "line(false and string.format(game.translate_string(\"st_arsenal_stashes_at\")"),
    "where_distinct": ("for _, list in ipairs({ distinct(from), distinct(gets) }) do", "for _, list in ipairs({ from, gets }) do"),
    "where_eco": ("        if k.economies then", "        if false then"),
    "where_free": ('or string.format(game.translate_string("st_arsenal_start_free"), who)', "or who"),
    "where_row_height": ("y = y + math.max(f:GetHeight(), r:GetHeight()) + 2", "y = y + f:GetHeight() + 2"),
    "where_made": ('line(string.format(game.translate_string("st_arsenal_made_from"), mf.from, mf.kit))',
                   "-- not shown"),
}


def sizes():
    root = ET.fromstring(XML.split("?>", 1)[1])
    out = {}
    for el in root:
        out[el.tag] = [float(el.get(k, 0)) for k in ("x", "y", "width", "height")]
    return out


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

    def shown(ui):
        """the entry in the scroll view, or an empty stand-in when none was added"""
        e = ui.detail.content and ui.detail.content[1]
        return e if e is not None else lua.eval("{ children = {} }")

    def texts_of(entry):
        return [c.text for c in entry.children.values() if c.text]

    sz = sizes()
    used = sorted(set(re.findall(r'xml:Init\w+\("([\w:]+)"', src)))
    missing = [u for u in used if u not in sz]
    check(not missing, "every element the script asks for is in the layout: %s" % (missing or "%d used" % len(used)))

    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS, lua.table_from({k: lua.table_from(v) for k, v in sz.items()}), lua.table_from(STRINGS))
    m = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                 "setfenv(f, env); f(); return env end")(src)
    g = lua.globals()
    try:
        ui = m.get_ui()
    except Exception as e:  # a missing element or a nil call
        check(False, "the page builds: %s" % e)
        print("\n%d failed" % len(fails))
        return 1

    joined = lambda *v: m.joined(lua.table_from(list(v)))
    check(joined("350 RPM", "200 RPM", "245 RPM") == "200 / 245 / 350 RPM" and joined("30", "20") == "20 / 30"
          and joined("1.05 kg", "2 lb") == "1.05 kg / 2 lb",
          "values listed by number with one unit: %s | %s | %s"
          % (joined("350 RPM", "200 RPM", "245 RPM"), joined("30", "20"), joined("1.05 kg", "2 lb")))

    check(ui.found_count.text == "Found 1 of 5", "count line: %s" % ui.found_count.text)
    cats = [(r.key, r.name.text, r.count.text) for r in ui.cat_list["items"].values()]
    check(cats == [("pistols", "Pistols", "1/2"), ("rifles", "Rifles", "0/1"), ("melee", "Melee", "0/1"),
                   ("medium", "Medium armor", "0/1")],
          "categories with found/total models, empty ones left out: %s" % cats)
    rows = [(r.key, r.name.text, r.name.color) for r in ui.wpn_list["items"].values()]
    check([r[1] for r in rows] == ["PM", "Fort-17", "Ghost"], "one row per gun model: %s" % [r[1] for r in rows])
    check([r[2] for r in rows] == ["dim", "body", "never"],
          "a model is found once any variant is, else dim; one that never turns up darker: %s" % [r[2] for r in rows])
    entry = ui.detail.content and ui.detail.content[1]
    check(entry is not None and ui.sec == "wpn_pm", "the first model's entry is shown")
    if entry is not None:
        texts = texts_of(entry)
        stats = [c.stat for c in entry.children.values() if c.stat]
        check("PM" in texts and "Not found yet" in texts, "name and found line: %s" % texts[:3])
        check(stats == ["accuracy", "fire_rate"], "the stat card's rows: %s" % stats)
        check(entry.h > 200, "the entry is sized before it is added: %s" % entry.h)
        check(not any(t == "Variants:" for t in texts), "a model of one variant lists none")
        pm_max = [k.text for c in entry.children.values() if c.path == "stats_box"
                  for k in c.children.values() if k.path == "entry_max"]
        log = list(g.logged.values())
        check(pm_max == [] and len(log) == 1 and "wpn_pm accuracy" in log[0] and "75" in log[0],
              "no max where the formula disagrees with the card, and one log line: %s %s" % (pm_max, log))
        i = texts.index("Where to find:") if "Where to find:" in texts else -1
        check(i >= 0 and texts[i + 1] == "In stashes" and "Carried by:" not in texts
              and "No faction carries it and no stash holds it" not in texts,
              "in stashes, though no level is named; no fighter carries it: %s" % texts[i:i + 2])

    ui.found_only.checked = True
    ui.cb.found_only()
    rows = [r.name.text for r in ui.wpn_list["items"].values()]
    check(rows == ["Fort-17"], "found only: %s" % rows)
    fort = shown(ui)
    texts = texts_of(fort)
    check("Found 14.05.2012 in Cordon" in texts, "when and where: %s" % texts[:3])
    rowboxes = [c for c in fort.children.values() if c.path in ("stats_box", "item_info:stats_box")]
    card = [(c.stat or "", [k.text for k in c.children.values() if k.text and k.path != "entry_max"])
            for c in rowboxes]
    check(card == [("accuracy", []), ("", ["Fire Rate", "400 / 450 RPM"])],
          "the card's own row where the variants agree, each value where they differ: %s" % card)
    i = texts.index("Variants:") if "Variants:" in texts else -1
    check(i >= 0 and texts[i + 1:i + 3] == ["Fort-17 (reliability 89%)",
                                             "Fort-17 (reliability 91%), found 14.05.2012 in Cordon"],
          "the variants, the found one with when and where: %s" % texts[i:i + 3])
    lines = {c.text: c.color for c in fort.children.values() if c.text}
    check(lines.get("Fort-17 (reliability 89%)") == "dim"
          and lines.get("Fort-17 (reliability 91%), found 14.05.2012 in Cordon") == "good",
          "unfound variants dim, found ones green")
    check("wpn_fort17" in list(g.icons.values()) and "wpn_fort" not in list(g.icons.values()),
          "the icon is the found variant's: %s" % list(g.icons.values()))

    # the fully upgraded value right of the card's, the best variant's, only where an upgrade raises it
    maxes = [(c.stat or "", [k.text for k in c.children.values() if k.path == "entry_max"]) for c in rowboxes]
    check(maxes == [("accuracy", ["max 82 %"]), ("", [])],
          "max beside a stat an upgrade raises, the best variant's; none where nothing raises it: %s" % maxes)
    mx = [k for c in rowboxes for k in c.children.values() if k.path == "entry_max"]
    check(mx and mx[0].x == 250, "the max sits right of the value column")

    # what fits it and what it is made of, after the ammo, before the description
    order = [t for t in texts if t in ("R.I.S.K. enhancements:", "Variants:", "Where to find:", "Ammo", "Magazines:",
                                       "Scopes:", "Suppressors:", "Accessories:", "Camos:", "Parts:", "Repair kits:",
                                       "A gun.")]
    check(order == ["R.I.S.K. enhancements:", "Variants:", "Where to find:", "Ammo", "Magazines:", "Scopes:",
                    "Suppressors:", "Accessories:", "Camos:", "Parts:", "Repair kits:", "A gun."],
          "sections in order: %s" % order)
    def after(head, n):
        i = texts.index(head) if head in texts else -1
        return texts[i + 1:i + 1 + n] if i >= 0 else []

    # where to find it: a row per faction with its ranks (runs as ranges, all as every rank, a
    # rankless squad as special), stashes, Nimble (what he takes first, each line once), the gun
    # a kit makes it of, new-game kits (every faction, an economy lock)
    check(after("Where to find:", 9) == ["Carried by:", "Bandit", "Rookie – Trainee, Professional, Expert, Legend",
                                          "Loner", "Experienced – Veteran, Legend", "UNISG", "special squads",
                                          "Military", "every rank"],
          "the factions that carry it, with their ranks: %s" % after("Where to find:", 9))
    check(after("every rank", 7) == ["In stashes, most often at Cordon, Garbage",
                                     "From Nimble, for Fort-12 / Fort-12 (old) and 45000 RU",
                                     "Nimble gives the Fort-17 Nimble for it and 30000 RU",
                                     "Made from the Fort-12 with the Conversion Kit",
                                     "New-game kit, 150 points: Loner, Bandit", "New-game kit, free: every faction",
                                     "New-game kit, 200 points: Duty; Tourist (Easy), Scavenger (Medium) only"],
          "stashes, Nimble, a kit, new-game kits: %s" % after("every rank", 7))
    fr = [c for c in fort.children.values() if c.path == "where_faction"]
    rr = [c for c in fort.children.values() if c.path == "where_ranks"]
    check(len(fr) == 4 and len(rr) == 4 and all(f.y == r.y for f, r in zip(fr, rr)) and rr[0].x == 88
          and rr[0].h > 18 and fr[1].y >= rr[0].y + rr[0].h,
          "a faction and its ranks side by side; ranks that wrap push the next row down: %s"
          % [(f.y, r.y, r.h) for f, r in zip(fr, rr)])
    check(after("Scopes:", 5) == ["Kobra", "PK-A", "OKP-7", "PSO-1", "never turns up"],
          "every variant's scopes, each once, the shown variant's first; one that never turns up says so: %s"
          % after("Scopes:", 5))
    check(after("Suppressors:", 3) == ["Built in on Fort-17 (reliability 89%)", "PBS-1", "after an upgrade"],
          "a suppressor built into one variant is named for it; one an upgrade mounts says so: %s"
          % after("Suppressors:", 3))
    check(after("Accessories:", 10) == ["Laser built in on Fort-17 (reliability 89%)", "GP-25", "VOG-25", "M203",
                                          "M406\\nafter an upgrade", "LAM", "Tactical Kit", "makes the Fort-17 Tactical",
                                          "Camo Kit", "Camos:"],
          "a laser built into one variant, launchers with their grenades (an upgrade's says so), a laser module, "
          "kits: %s" % after("Accessories:", 10))
    modes = [t for t in texts if t.startswith("Fire modes")]
    check(modes == ["Fire modes: 1 / A (1 / 3 / A by upgrade)"], "fire modes an upgrade adds: %s" % modes)
    check(after("Ammo", 2) == ["5.45 FMJ", "By upgrade: 9x19 FMJ, 9x19 AP"],
          "the ammo of the caliber an upgrade converts it to: %s" % after("Ammo", 2))
    check(after("Parts:", 2) == ["Barrel", "Trigger"], "parts, a row each: %s" % after("Parts:", 2))
    check(after("Camos:", 7) == ["Base", "Tan", "Not discovered yet; on guns carried by Loner, Bandit", "Arctic",
                                 "Not discovered yet", "Woodland", "Discovered"],
          "camos, a row each: what one not yet discovered takes, one discovered says so: %s" % after("Camos:", 7))
    cn = {c.text: c.color for c in fort.children.values() if c.path == "part_name" and c.text in
          ("Base", "Tan", "Arctic", "Woodland")}
    check(cn == {"Base": None, "Tan": "dim", "Arctic": "dim", "Woodland": "good"},
          "a camo not yet discovered dim, a discovered one green: %s" % cn)
    sw = [(c.tex, c.w, c.h) for c in fort.children.values() if c.path == "camo_swatch"]
    check(sw == [("black", 18, 24), ("tan", 18, 24), ("arctic", 18, 24), ("woodland", 18, 24)],
          "each camo's swatch, square on a wide screen: %s" % sw)
    check(after("R.I.S.K. enhancements:", 9) == ["One on the gun as it ships, weakest to strongest", "Fire rate",
                                                 "462 \u2013 690 RPM (bad roll: 210 RPM)", "Sway",
                                                 "no change on the card", "Weight",
                                                 "0 \u2013 0.9 kg (bad roll: 3.1 kg)", "Damage",
                                                 "+2 \u2013 +40 % (bad roll: -40 %)"],
          "R.I.S.K. rows: a card stat where the card agrees, weight, damage signed; a stat the card shows "
          "otherwise or not at all left out; one that leaves the card as it is says so: %s"
          % after("R.I.S.K. enhancements:", 9))
    rn = [c for c in fort.children.values() if c.path == "risk_name"]
    rv = [c for c in fort.children.values() if c.path == "risk_values"]
    check(len(rn) == 4 and all(a.y == b.y for a, b in zip(rn, rv)) and rv[0].x == 128,
          "a family and its values side by side")
    check(after("Repair kits:", 2) == ["Type A Cleaning Kit", "Type A Repair Kit"],
          "the kits that repair it, once though both variants name them: %s" % after("Repair kits:", 2))
    check(after("Magazines:", 2) == ["Fort Magazine", "13 rounds"], "magazines with their rounds: %s" % after("Magazines:", 2))
    kobras = sum(1 for c in fort.children.values() if c.path == "tile_name" and c.text == "Kobra")
    check(kobras == 1, "two items of one name show once: %d" % kobras)
    names = {c.text: c for c in fort.children.values() if c.path == "tile_name"}
    pos = [(names[n].x, names[n].y) for n in ("Kobra", "PK-A", "OKP-7", "PSO-1") if n in names]
    check(len(pos) == 4 and [x for x, _ in pos] == [0, 118, 236, 0] and pos[3][1] > pos[0][1],
          "tiles three to a row, the fourth on the next: %s" % pos)

    ui.found_only.checked = False
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    check([r.key for r in ui.wpn_list["items"].values()] == ["wpn_ak74"] and ui.sec == "wpn_ak74", "switching category")
    kids = {c.path: c for c in shown(ui).children.values()}
    name, line = kids.get("entry_name"), kids.get("entry_found")
    check(name is not None and line is not None and name.h > 20 and line.y >= name.y + name.h,
          "a name that wraps pushes the found line down: name %s+%s, found at %s"
          % (name and name.y, name and name.h, line and line.y))
    ui.cat_list.sel = 2
    ui.cb.cat_list()
    knife = shown(ui)
    texts = texts_of(knife)
    stats = [c.stat for c in knife.children.values() if c.stat]
    check(ui.sec == "wpn_knife" and not stats and not any(t.startswith("Fire modes") for t in texts)
          and "Weight: 3.3 kg" in texts,
          "a knife: no stat card and no fire modes, as in the inventory; its weight: %s %s" % (stats, texts[:4]))
    i = texts.index("Where to find:") if "Where to find:" in texts else -1
    check(i >= 0 and texts[i + 1] == "No faction carries it and no stash holds it",
          "a gun no fighter carries and no stash holds says so: %s" % texts[i:i + 2])
    # a suit: the outfit card with its max, no fire modes, who wears it and how it drops, no
    # carriers, stashes, its repair kits
    ui.cat_list.sel = 3
    ui.cb.cat_list()
    seva = shown(ui)
    texts = texts_of(seva)
    stats = [c.stat for c in seva.children.values() if c.stat]
    check(ui.sec == "sci_suit" and stats == ["fire_wound_protection", "burn_protection"]
          and not any(t.startswith("Fire modes") for t in texts) and "Weight: 3.3 kg" in texts,
          "a suit: the outfit card, no fire modes: %s %s" % (stats, texts[:6]))
    smax = [(c.stat, [k.text for k in c.children.values() if k.path == "entry_max"])
            for c in seva.children.values() if c.path == "stats_box"]
    check(smax == [("fire_wound_protection", ["max 90 %"]), ("burn_protection", [])],
          "a suit's max where an upgrade raises a card value: %s" % smax)
    check(after("Where to find:", 7) == ["Worn by:", "Ecologist", "Rookie \u2013 Professional", "Duty", "special squads",
                                          "Drops from a body 50% of the time once your rank reaches 1747 (Rookie)",
                                          "In stashes, most often at Yantar"]
          and "Carried by:" not in texts,
          "who wears it, how it drops, stashes; no carriers: %s" % after("Where to find:", 7))
    check(after("In stashes, most often at Yantar", 4) == [
              "Carried by Strelok", "Crafted at a workbench",
              "From Petrenko, for any of 12 suits and 10000 RU (Duty only)",
              "Sidorovich, Owl gives the Exoskeleton for it and 45000 RU (Loner only)"],
          "story characters (a name with no text left out), crafting, the Armor Exchange both ways: %s"
          % after("In stashes, most often at Yantar", 4))
    check(after("Repair kits:", 1) == ["Basic Sewing Kit"], "its repair kits: %s" % after("Repair kits:", 1))
    g.DROP_OFF = True
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    ui.cat_list.sel = 3
    ui.cb.cat_list()
    off = texts_of(shown(ui))
    g.DROP_OFF = None
    check("Bodies drop no armor in this game's economy" in off, "with drops off, says so")
    # a model that never turns up: listed with the jailbreak, and says so
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    ui.wpn_list.sel = 2
    ui.cb.wpn_list()
    ghost = texts_of(shown(ui))
    i = ghost.index("Where to find:") if "Where to find:" in ghost else -1
    check(ui.sec == "wpn_ghost" and i >= 0 and ghost[i + 1] == "Never turns up in this game",
          "a model that never turns up says so: %s" % ghost[i:i + 2])

    # immersive: only what the player knows of, what he has learned of where to find it, its
    # stats once studied, a mark on what is new
    lua.execute("""
KNOWN = { wpn_pm = true, wpn_fort = true, wpn_ak74 = true }
STUDIED = {}
NEW = { wpn_pm = true }
FACTS = { wpn_pm = { stash = { l02_garbage = true }, sold = { Sidorovich = true } },
          wpn_fort = { carried = { bandit = { trainee = true }, stalker = { legend = true } }, ways = { kit = true } } }
LEARNED = { wpn_pm = { at = { d = 3, mo = 6, y = 2012, lvl = "l01_escape" }, how = { kind = "pda" } } }
arsenal_intel = {
    jailbroken = function() return false end,
    listed = function(e) return KNOWN[e.sec] == true end,
    studied = function(e) return STUDIED[e.sec] == true end,
    facts = function(e) return FACTS[e.sec] end,
    learned = function(e) return LEARNED[e.sec] end,
    describe = function(how) return "a Duty PDA" end,
    is_new = function(e) return NEW[e.sec] == true end,
    viewed = function(e) NEW[e.sec] = nil end,
    player_faction = function() return "stalker" end,
}
""")
    ui.cat_list.sel = 0
    ui = m.get_ui()
    check(ui.found_count.text == "Known 3 \u00b7 Found 1 of 5", "count line: %s" % ui.found_count.text)
    cats = [r.name.text for r in ui.cat_list["items"].values()]
    check(cats[0] == "Pistols <warn>*", "a category with something new is marked: %s" % cats)
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    rows = [r.name.text for r in ui.wpn_list["items"].values()]
    check(rows == ["PM <warn>*", "Fort-17"], "only what is known, the new one marked: %s" % rows)
    pm = shown(ui)
    texts = texts_of(pm)
    stats = [c.stat for c in pm.children.values() if c.stat]
    i = texts.index("Where to find:") if "Where to find:" in texts else -1
    check("Learned 03.06.2012 from a Duty PDA" in texts and not stats and not any(t.startswith("Weight") for t in texts)
          and any(t.startswith("Not studied yet") for t in texts),
          "a known model not yet studied: how it was learned, no stats: %s %s" % (stats, texts[:5]))
    check(texts[i + 1:i + 3] == ["Seen in stashes at Garbage", "Seen for sale at Sidorovich"],
          "where to find it: only where it was seen: %s" % texts[i:i + 3])
    rows = [r.name.text for r in m.get_ui().wpn_list["items"].values()]
    check(rows[0] == "PM", "seen: no longer new: %s" % rows)
    ui.wpn_list.sel = 1
    ui.cb.wpn_list()
    fort = shown(ui)
    texts = texts_of(fort)
    check("Scopes:" not in texts and "Parts:" not in texts and "Camos:" not in texts,
          "not studied: nothing of what fits it: %s" % [t for t in texts if t.endswith(":")])
    check(after("Where to find:", 7) == ["Carried by:", "Bandit", "Trainee", "Loner", "Legend",
                                          "New-game kit, 150 points: Loner", "New-game kit, free: Loner"],
          "the factions and ranks seen carrying it, the player's own faction's kits only: %s" % after("Where to find:", 7))
    lua.execute("STUDIED.wpn_fort = true")
    ui.wpn_list.sel = 0
    ui.cb.wpn_list()
    ui.wpn_list.sel = 1
    ui.cb.wpn_list()
    texts = texts_of(shown(ui))
    check("Scopes:" in texts and "PSO-1" not in texts, "studied: what fits it, but what never turns up left out")
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    texts = texts_of(shown(ui))
    i = texts.index("Where to find:") if "Where to find:" in texts else -1
    check(ui.sec == "wpn_ak74" and texts[i + 1] == "Nothing learned yet about where to find it",
          "nothing learned of where to find it says so, though traders sell it: %s" % texts[i:i + 2])
    lua.execute("arsenal_intel = nil")
    ui = m.get_ui()

    ui.cb.btn_back()
    check(g.pda_section == "eptLauncher", "Back returns to the launcher")

    # the flat window: the 2D PDA's frame behind the page, where the PDA puts its pages
    paths = lambda w: [c.path for c in w.children.values()]
    check("flat_bezel" not in paths(ui), "the PDA page has no frame of its own")
    g.actor_alive = False
    check(m.open_flat() is None, "no window while the player is dead")
    g.actor_alive = True
    flat = m.open_flat()
    check(flat is not None and flat.IsShown(flat), "the key opens the window")
    if flat is not None:
        kids = paths(flat)
        check(kids[:2] == ["flat_bezel", "flat_caption"], "the frame first, behind everything: %s" % kids[:3])
        check(list(flat.rect.values())[:2] == [112, 34], "placed as the PDA places its pages: %s" % list(flat.rect.values()))
        check(flat.found_count.text == "Found 1 of 5" and flat.detail.content and flat.detail.content[1] is not None,
              "the window fills like the page")
        ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_A, g.ui_events.WINDOW_KEY_PRESSED)
        check(flat.IsShown(flat) and not ret, "another key leaves it open")
        ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_ESCAPE, g.ui_events.WINDOW_KEY_PRESSED)
        check(not flat.IsShown(flat) and ret, "Escape closes it")
        m.open_flat()
        flat.OnKeyboard(flat, g.DIK_keys.DIK_F7, g.ui_events.WINDOW_KEY_PRESSED)
        check(not flat.IsShown(flat), "the key closes it again")
        m.open_flat()
        g.pda_section = None
        flat.cb.btn_back()
        check(not flat.IsShown(flat) and g.pda_section is None, "Back closes it, leaving the PDA alone")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
