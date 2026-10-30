"""Smoke test for ui_arsenal.script under LuaJIT, against stand-ins for the engine's widgets,
arsenal_data and arsenal_collection. Checks that every layout element the script asks for is
in ui_arsenal.xml (in game a missing one returns nil and the page dies), and that the page
fills: the count line, categories with found/total, one row per gun model, dim while none of
its variants is found, the "found only" filter, switching categories, an entry built and
handed to its scroll view once complete, a long name that wraps without covering the line
below it, a model's page (stat rows that list each variant's value where they differ, the
variants with when and where each was found, the found variant's icon), a knife's page
without a stat card, and Compare over the entry (the real arsenal_compare.script) for what has
one.

    python test_ui.py            the real script
    python test_ui.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

from lua_jit import L

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "..", "gamedata")
SRC = io.open(os.path.join(GD, "scripts", "ui_arsenal.script"), encoding="latin-1").read()
PAGES = io.open(os.path.join(GD, "scripts", "arsenal_pages.script"), encoding="latin-1").read()
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
function W:IsShown() return self.shown ~= false end
function W:Enable(b) self.enabled = b end
function W:TextControl() return self end
function W:SetAutoDelete(b) self.autodelete = b end
function W:GetCheck() return self.checked == true end
function W:SetCheck(v) self.checked = v == true end
-- list box; filling one anew scrolls it to the top, as the engine's does
function W:AddExistingItem(item) self.items = self.items or {}; table.insert(self.items, item) end
-- the engine translates an added line's text
function W:AddTextItem(t)
    local it = { text = game.translate_string(t) }
    self.items = self.items or {}; table.insert(self.items, it)
    return it
end
function W:RemoveAll() self.items = {}; self.sel = nil; self.scroll = 0 end
function W:GetSize() return #(self.items or {}) end
function W:SetSelectedIndex(i) self.sel = i end
function W:GetSelectedIndex() return self.sel end
function W:GetSelectedItem() return self.sel and self.items[self.sel + 1] end
-- scroll view, and the scroll of a list box: MAX_SCROLL as far as anything reaches
MAX_SCROLL = 1000
function W:Clear() self.content = {}; self.scroll = 0 end
function W:AddWindow(w, auto) self.content = self.content or {}; table.insert(self.content, w) end
function W:ScrollToBegin() self.scroll = 0 end
function W:GetCurrentScrollPos() return self.scroll or 0 end
function W:GetMaxScrollPos() return MAX_SCROLL end
function W:SetScrollPos(p) self.scroll = p end

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
    x.InitFrame = init()
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
-- a selection by cb[name](), a click (LIST_ITEM_CLICKED) by clk[name](). The engine finds a
-- callback by the name Register gives a window, which also sends its messages to the page, a
-- window inside another too
function CUIScriptWnd:AddCallback(name, ev, fn, obj)
    local t = ev == ui_events.LIST_ITEM_CLICKED and "clk" or "cb"
    self[t] = self[t] or {}; self[t][name] = function()
        assert(self.registered and self.registered[name], "no window registered as '" .. name .. "'")
        fn(obj)
    end
end
function CUIScriptWnd:SetWndRect(r) self.rect = r.r end
function CUIScriptWnd:ShowDialog(b) self.dialog_shown = true end
function CUIScriptWnd:HideDialog() self.dialog_shown = false end
function CUIScriptWnd:IsShown() return self.dialog_shown == true end
function CUIScriptWnd.OnKeyboard(self, dik, action) return false end
DIK_keys = { DIK_ESCAPE = 1, DIK_F7 = 65, DIK_A = 30 }
db = { actor = { alive = function() return actor_alive end } }
actor_alive = true
-- MCM's "PDA notifications", on until a case turns it off; the credit line as arsenal_mcm makes it
NEWS_ON = true
-- MCM's jailbreak, off until a case turns it on
JAILBREAK = false
-- MCM's "Show where items are defined", off until a case turns it on
SOURCES = false
arsenal_mcm = { flat_key = function() return DIK_keys.DIK_F7 end,
    credit = function() return "Arsenal v1.2.1 by Windwalker" end,
    news = function() return NEWS_ON end,
    set_news = function(on) NEWS_ON = on end,
    jailbreak = function() return JAILBREAK end,
    sources = function() return SOURCES end }
-- the system ini as arsenal_sources reads it: Modded Exes' DLTX lines, each with the file it came from
DLTX_SECTIONS = { wpn_pm = {} }
for i = 1, 40 do DLTX_SECTIONS.wpn_pm["line" .. i] = { name = "line" .. i, value = "1", filename = "w_pm.ltx" } end
DLTX_SECTIONS.wpn_pm.cost = { name = "cost", value = "300", filename = "mod_system_x_pm.ltx" }
ini_sys = {
    section_exist = function(self, s) return type(s) == "string" and s ~= "" end,
    r_string_ex = function(self, s, k) if k == "visual" then return "dynamics\\weapons\\" .. s .. "\\" .. s end end,
    dltx_get_section = function(self, s) return DLTX_SECTIONS[s] or {} end,
}

function vector2() return { set = function(self, x, y) self.x, self.y = x, y; return self end } end
function Frect() return { set = function(self, a, b, c, d) self.r = { a, b, c, d }; return self end } end
function GetARGB(a, r, g, b) return string.format("%d,%d,%d,%d", a, r, g, b) end
ui_events = { BUTTON_CLICKED = 1, LIST_ITEM_SELECT = 2, LIST_ITEM_CLICKED = 3, WINDOW_KEY_PRESSED = 6 }
TIME = 0
function time_global() return TIME end
-- the mod's own found lines come from its table (STRINGS), so the page reads as the game shows it
local T = { st_arsenal_found_count = "Found %s of %s",
            st_arsenal_not_found = "Not found yet", st_arsenal_cat_pistols = "Pistols",
            st_arsenal_cat_rifles = "Rifles", st_arsenal_cat_melee = "Melee", st_arsenal_fire_modes = "Fire modes",
            st_arsenal_variants = "Variants:",
            st_prop_weight = "Weight", st_kg = "kg", ui_ammo_types = "Ammo", l01_escape = "Cordon",
            ui_inv_rate_of_fire = "Fire Rate" }
for k, v in pairs(STRINGS) do T[k] = T[k] or v end
T.st_perc, T.st_stat_rpm = "%", "RPM"
-- the engine's takes a string only
game = { translate_string = function(k) assert(type(k) == "string", "translate_string: not a string"); return T[k] or k end }
TEXT = T
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
arsenal_theme = { argb = function(role, a) return a and (role .. "@" .. a) or role end,
                  markup = function(role) return "<" .. role .. ">" end,
                  set_active = function(btn, on) btn.active = on end }
-- the switch to Workbench: the real arsenal_pages (main loads it), whose open records the page
-- asked for; and MAC's tile, for Back (arsenal_pages.back_to_launcher), there unless a case
-- takes it away
opened_pages = {}
TILE = true
z_arsenal_mac = { has_tile = function() return TILE end }
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
    ammo = { model("5.45x39 FMJ", { { sec = "ammo_545", name = "5.45x39 FMJ" } }) },
}
for c, l in pairs(guns) do for _, e in ipairs(l) do e.cat = c end end
found = { wpn_fort17 = { y = 2012, mo = 5, d = 14, lvl = "l01_escape", how = { kind = "stash" } } }
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
    CATEGORIES = { "pistols", "smgs", "rifles", "melee", "medium", "ammo" },
    ARMOR = { medium = true },
    has_stat_card = function(sec) return sec ~= "wpn_knife" and sec ~= "ammo_545" end,
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
    -- the other Fort-17 also chambers 9x18
    ammo_names = function(sec) return sec == "wpn_fort" and { "5.45 FMJ", "9x18 FMJ" } or { "5.45 FMJ" } end,
    description = function() return "A gun." end,
    variant_of = function(sec)
        for _, l in pairs(guns) do for _, e in ipairs(l) do
            for _, v in ipairs(e.variants) do if v.sec == sec then return v end end
        end end
    end,
}
-- where to find them: the Fort-17s are carried, stashed, traded with Nimble, made of another gun
-- and in new-game kits; the PM is in stashes no level list names; the knife turns up nowhere
local ALL = { "novice", "trainee", "experienced", "professional", "veteran", "expert", "master", "legend" }
arsenal_data.RANKS = ALL
arsenal_data.FACTIONS = { "stalker", "dolg", "freedom", "csky", "ecolog", "killer", "army", "bandit", "monolith",
    "zombied", "renegade", "greh", "isg" }
local FORT = { wpn_fort = true, wpn_fort17 = true }
-- the factions' gear, in no particular order: Loners wear the SEVA and carry the AK-74 and the
-- Fort-17; bandits carry the PM and the Fort-17; nobody else carries anything
GEAR = { stalker = { "sci_suit", "wpn_ak74", "wpn_fort" }, bandit = { "wpn_pm", "wpn_fort" } }
function arsenal_data.faction_gear(f)
    local out = {}
    for _, s in ipairs(GEAR[f] or {}) do
        local e = arsenal_data.get(s)
        out[#out + 1] = { e = e, ranks = { novice = 0.5 }, armor = (e.cat == "medium") or nil, best = 0.5 }
    end
    return out
end
function arsenal_data.carriers(sec)
    -- a loadout naming the suit: a suit's page shows who wears it, not this
    if sec == "sci_suit" then return { { faction = "ecolog", ranks = ALL } } end
    if not FORT[sec] then return {} end
    return { { faction = "bandit", ranks = { "novice", "trainee", "professional", "expert", "legend" } },
             { faction = "stalker", ranks = { "experienced", "professional", "veteran", "legend" } },
             { faction = "isg", ranks = {}, special = true },
             { faction = "army", ranks = ALL } }
end
-- a stash's odds: the Fort-17s' two levels (Garbage's a sliver, the same in a rare stash), the
-- SEVA's one (none in rare stashes), the PM in stashes no level list names
function arsenal_data.stash_odds(sec)
    if FORT[sec] then
        return { { lvl = "l01_escape", common = 0.0123, rare = 0.034 }, { lvl = "l02_garbage", common = 0.0006, rare = 0.0006 } }
    end
    if sec == "sci_suit" then return { { lvl = "l08_yantar", common = 0.05, rare = 0 } } end
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
function arsenal_data.entry_for(sec) return arsenal_data.get(sec) end
function arsenal_data.addon_turns_up(sec) return sec ~= "ps01" end
function arsenal_data.turns_up_model(sec)
    if sec == "sci_suit" then return { story = { "st_strelok_name", "GENERATE_NAME_x" }, craft = true } end
    if sec == "wpn_ak74" or sec == "wpn_pm" then return { trader = true } end
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
-- traders by tier: the AK-74 from four (one with the game's name for Heavy Pockets when it has
-- one); the PM turns up at traders that keep no tiers
function arsenal_data.sold_by(sec)
    if sec ~= "wpn_ak74" then return {} end
    return { { tier = 1, need = false, traders = { "Sidorovich", "mechanics" } },
             { tier = 2, need = { kits = 1 }, traders = { "Mechanic One" } },
             { tier = 3, need = { kits = 2, drugkit = true, story = true }, traders = { "Beard" } },
             { tier = 4, need = { goodwill = 1500, heavy = true }, traders = { "Owl" } } }
end
-- the Fort-17's rounds, one of them buckshot without a falloff
function arsenal_data.gun_rounds(sec)
    if sec ~= "wpn_fort17" then return {} end
    return { { sec = "ammo_545", name = "5.45 FMJ", damage = 38, ap = 27, speed = 924, kept = 0.932 },
             { sec = "ammo_buck", name = "12x70 Buckshot", damage = 19, ap = 3, speed = 325, pellets = 9 } }
end
function arsenal_data.round_stats(sec)
    if sec ~= "ammo_545" then return nil end
    return { damage = 1.14, ap = 27, speed = 1.5, kept = { [50] = 0.965, [100] = 0.932, [200] = 0.872 },
             effects = { { id = "st_arsenal_round_mutants", text = "+15%" },
                         { id = "st_arsenal_round_effect", text = "3 Shock stacks" }, { text = "20% chance to stagger" } } }
end
-- what fires the 5.45: the AK-74 and the Ghost
function arsenal_data.fired_by(sec)
    if sec ~= "ammo_545" then return {} end
    return { arsenal_data.get("wpn_ak74"), arsenal_data.get("wpn_ghost") }
end
HIT = { wpn_fort17 = 0.465, wpn_fort = 0.465, wpn_pm = 0.45 }
function arsenal_data.hit_power(sec) return HIT[sec] or 0 end
-- jams: the Fort-17 from the engine and with worn parts, the PM with worn parts, the AK-74 never
JAMS = { wpn_fort17 = { base = 0.003, worn = 0.014, both = 1 - 0.997 * 0.986 }, wpn_pm = { base = 0, worn = 0.017, both = 0.017 },
         wpn_ak74 = { base = 0 } }
function arsenal_data.jam_chance(sec) return JAMS[sec] end
-- the SEVA against bullets; PEN = "all" or "none" for a suit that stops everything or nothing
function arsenal_data.penetration(sec)
    if sec ~= "sci_suit" then return nil end
    local p = { class = 0.31, protection = 0.25, stopped = 0.45, pierced = 0.75, stops = 23, of = 43,
                holds = { name = "5.45 FMJ", ap = 27 }, fails = { name = "12x76 Dart", ap = 42 } }
    if PEN == "all" then p.fails, p.stops = nil, 43 end
    if PEN == "none" then p.holds, p.stops = nil, 0 end
    return p
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
    -- as the real one puts a find: how it came (st_arsenal_got_*), and where; or, for a record
    -- that has no how, the level alone
    describe = function(at)
        local where = T[at.lvl] or at.lvl
        return at.how and (T["st_arsenal_got_" .. at.how.kind] .. " in " .. where) or where
    end,
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
    # what goes on a gun
    "fits_none": ("for _, f in ipairs(safe(arsenal_data.fits, shown.sec) or {}) do", "for _, f in ipairs({}) do"),
    "fits_unlisted": ("            if listed(f.e) then\n                local n = f.e.name",
                      "            if true then\n                local n = f.e.name"),
    "fits_makes": ('                if f.makes then n = string.format("%s (%s)", n, string.format(T("st_arsenal_makes"), f.makes)) end\n', ""),
    "fits_upgrade": ('                if f.upgrade then n = string.format("%s (%s)", n, T("st_arsenal_after_upgrade")) end\n', ""),
    "fits_more_never": ("            elseif arsenal_data.obtainable(f.e.sec) then\n                unmet[f.e] = true",
                        "            else\n                unmet[f.e] = true"),
    "fits_more_once": ("        for _ in pairs(unmet) do more = more + 1 end", "        more = 3"),
    "fits_more_hidden": ("            if more > 0 then\n                text(\"entry_line\", string.format(T(\"st_arsenal_fits_more\")",
                         "            if false then\n                text(\"entry_line\", string.format(T(\"st_arsenal_fits_more\")"),
    "fits_fires": ("                for _, a in ipairs(f.ammo or {}) do fires[#fires + 1] = a end\n", ""),
    "fits_fires_distinct": ("            fires = distinct(fires)\n", ""),
    "fits_names_distinct": ('T("st_arsenal_cat_" .. c), table.concat(distinct(names[c]), ", ")',
                            'T("st_arsenal_cat_" .. c), table.concat(names[c], ", ")'),
    "fits_know": ("    if know and addon then\n        local T = game.translate_string\n        local cats",
                  "    if addon then\n        local T = game.translate_string\n        local cats"),
    "addon_not_studied": ('addon and "st_arsenal_not_studied_addon" or "st_arsenal_not_studied"', '"st_arsenal_not_studied"'),
    "mounted_rows": ("local mounted = known_rows(addon and safe(arsenal_data.mounted_on, shown.sec) or {}, fx.carried)",
                     "local mounted = known_rows({}, fx.carried)"),
    "mounted_known": ("local mounted = known_rows(addon and safe(arsenal_data.mounted_on, shown.sec) or {}, fx.carried)",
                      "local mounted = addon and safe(arsenal_data.mounted_on, shown.sec) or {}"),
    "find_words": ("    return date_of(at), arsenal_collection.describe(at)", "    return date_of(at), at.lvl"),
    "learned_where": ("arsenal_intel.describe(learned.how, learned.at)", "arsenal_intel.describe(learned.how)"),
    "silence_unpainted": ("    self:PaintFooter()\n    arsenal_pages.show_back(self.back_row, self.flat)\n",
                          "    arsenal_pages.show_back(self.back_row, self.flat)\n"),
    "silence_inverted": ("arsenal_mcm.set_news(not self.silence:GetCheck())", "arsenal_mcm.set_news(self.silence:GetCheck())"),
    "no_credit": ("    self.credit:SetText(arsenal_mcm.credit())\n", ""),
    "jailbreak_unlit": ("    self.jailbreak:Show(jb)\n", "    self.jailbreak:Show(false)\n"),
    "jailbreak_always": ("local jb = arsenal_mcm.jailbreak() == true", "local jb = true"),
    "jailbreak_uncolored": ('        self.jailbreak:SetTextureColor(theme.argb("warn"))\n', ""),
    "switch_not_pressed": ("    theme.set_active(self.page_catalog, true)\n", ""),
    "switch_dead": ('    arsenal_pages.open("workbench")', "    -- nothing"),
    "toggle_ignored": ("    by_faction = self.by_faction_check:GetCheck() == true\n", ""),
    "toggle_no_memory": ("    self.cat = last_key[by_faction]\n", ""),
    "toggle_no_save": ("    last_key[by_faction] = self.cat\n    by_faction = self.by_faction_check:GetCheck() == true\n",
                       "    by_faction = self.by_faction_check:GetCheck() == true\n"),
    "toggle_both": ("    if by_faction then\n        for _, f in ipairs(arsenal_data.FACTIONS) do",
                    "    if false then\n        for _, f in ipairs(arsenal_data.FACTIONS) do"),
    "toggle_check_sync": ("    self.by_faction_check:SetCheck(by_faction)\n", ""),
    "jam_line": ("        if jam then text(\"entry_line\", jam) end\n", ""),
    "jam_both": ('        if base > 0 then return string.format(T("st_arsenal_jam_both"), percent(base), percent(j.both)) end\n', ""),
    "jam_both_value": ('percent(base), percent(j.both)) end\n', 'percent(base), percent(j.worn)) end\n'),
    "jam_none": ('return base > 0 and string.format(T("st_arsenal_jam_base"), percent(base)) or T("st_arsenal_jam_none")',
                 'return base > 0 and string.format(T("st_arsenal_jam_base"), percent(base)) or nil'),
    "hit_power_line": ("        if hp and hp > 0 then\n", "        if false then\n"),
    "percent_sliver": ('    if p < 0.1 then return "<0.1%" end\n', ""),
    "percent_whole": ('(p < 10 and string.format("%.1f", p) or tostring(math.floor(p + 0.5)))', 'string.format("%.1f", p)'),
    "or_list": ('return table.concat(parts, ", ", 1, #parts - 1) .. " " .. game.translate_string("st_arsenal_or") .. " " .. parts[#parts]',
                'return table.concat(parts, ", ")'),
    "need_kit_one": ('(n.kits == 1) and T("st_arsenal_need_kit")', '(false) and T("st_arsenal_need_kit")'),
    "heavy_game_name": ('parts[#parts + 1] = T("st_arsenal_need_heavy")',
                        'parts[#parts + 1] = T("encyclopedia_achievements_heavy_pockets")'),
    "sold_fallback": ("    elseif up.trader then\n", "    elseif false then\n"),
    "sold_heading": ('        line(T("st_arsenal_sold_tiers"), "dim")\n', ""),
    "sold_need": ('text("entry_line", r.need and string.format(T("st_arsenal_tier_need")', 'text("entry_line", false and string.format(T("st_arsenal_tier_need")'),
    "stash_rare_part": ("(r.rare > 0 and r.rare ~= r.common)", "(r.rare > 0)"),
    "stash_note": ('            text("entry_line", T("st_arsenal_stash_odds_note"), "dim")\n', ""),
    "stash_none_named": ("        if #spots > 0 then\n", "        if true then\n"),
    "rounds_table": ("        if know and #rounds > 0 then\n            round_row", "        if false then\n            round_row"),
    "rounds_pellets": ("local dmg = r.pellets and string.format(T(\"st_arsenal_pellets\"), tostring(r.damage), tostring(r.pellets))\n                    or tostring(r.damage)",
                       "local dmg = tostring(r.damage)"),
    "rounds_kept": ('r.kept and percent(r.kept) or "-"', "percent(r.kept)"),
    "rounds_cols": ("c:SetWndPos(vector2():set(ROUND_COLS[i], y))", "c:SetWndPos(vector2():set(0, y))"),
    "rounds_other": ("            if not mine[n] then other[#other + 1] = n end", "            other[#other + 1] = n"),
    "rounds_header_dim": ("            if role then c:SetTextColor(theme.argb(role)) end\n", ""),
    "round_effects": ("            for _, x in ipairs(rs.effects or {}) do\n                row(x.id, x.text)\n            end\n", ""),
    "round_blank": ('n:SetText(id and game.translate_string(id) or "")', "n:SetText(game.translate_string(id))"),
    "round_rows": ('            row("st_arsenal_round_ap", tostring(rs.ap))\n', ""),
    "round_value_x": ("local v = xml:InitTextWnd(\"round_value\", entry)\n            v:SetWndPos(vector2():set(v:GetWndPos().x, y))",
                      "local v = xml:InitTextWnd(\"round_value\", entry)\n            v:SetWndPos(vector2():set(0, y))"),
    "fired_listed": ("            if listed(g) then guns[#guns + 1] = g.name end", "            guns[#guns + 1] = g.name"),
    "ammo_weight": ('    if know and e.cat ~= "ammo" then\n        text("entry_line", string.format("%s: %s %s"',
                    '    if know then\n        text("entry_line", string.format("%s: %s %s"'),
    "pen_block": ("        if p and p.of > 0 then\n            local T", "        if false then\n            local T"),
    "pen_all": ("            elseif p.holds then\n", "            elseif false then\n"),
    "pen_count": ('            text("entry_line", string.format(T("st_arsenal_pen_count"), tostring(p.stops), tostring(p.of)))\n', ""),
    "pen_damage": ('string.format(T("st_arsenal_pen_damage"), percent(p.stopped), percent(p.pierced))',
                   'string.format(T("st_arsenal_pen_damage"), percent(p.pierced), percent(p.stopped))'),
    "layout_name": ('xml:InitListBox("wpn_list", self)', 'xml:InitListBox("weapon_list", self)'),
    "name_wrap": ("line:SetWndPos(vector2():set(0, name:GetWndPos().y + math.max(name:GetHeight(), NAME_H)))",
                  "-- found line where the layout puts it"),
    "dim": ('return arsenal_collection.entry_found(e) and "body" or "dim"', 'return "body"'),
    "model_found": ("local found = arsenal_collection.entry_found(e) ~= nil",
                    "local found = arsenal_collection.is_found(e.sec)"),
    "card_always": ("if know and arsenal_data.has_stat_card(shown.sec) then", "if know then"),
    "filter": ("            if passes(show, found, is_new(e)) then list[#list + 1] = e end", "            list[#list + 1] = e"),
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
    "no_conversions": ('text("entry_line", string.format(T("st_arsenal_ammo_by_upgrade"), c), "dim")', "-- not shown"),
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
    "never_role": ('    if not arsenal_data.obtainable(e.sec) then return "never" end\n', ""),
    "count_obtainable": ("            if arsenal_data.obtainable(e.sec) then\n                total = total + 1",
                         "            if true then\n                total = total + 1"),
    "never_line": ('        line(game.translate_string("st_arsenal_never"), "warn")\n', ""),
    "addon_never_note": ("            if it.never then\n", "            if false then\n"),
    "addon_hide": ("if up or not imm then", "if true then"),
    "listed": ("        if listed(e) then\n            local found", "        if true then\n            local found"),
    "row_glow": ('new and "wpn_glow" or nil', "nil"),
    "action_always": ("        b:Show(a ~= nil)", "        b:Show(true)"),
    "action_everywhere": ("        if not a.show or safe(a.show, sec) then", "        if true then"),
    "action_model_key": ("    local ok, err = pcall(a.run, self.action_sec)", "    local ok, err = pcall(a.run, self.sec)"),
    "action_unguarded": ("    local ok, err = pcall(a.run, self.action_sec)", "    local ok, err = true, a.run(self.action_sec)"),
    "action_stale": ("    self.detail:Clear()\n    self:UpdateActions(nil)\n", "    self.detail:Clear()\n"),
    "cmp_hidden": ("    self.cmp_add:Show(can)", "    self.cmp_add:Show(false)"),
    "cmp_everywhere": ("    local can = sec ~= nil and safe(arsenal_compare.comparable, sec) == true", "    local can = sec ~= nil"),
    "cmp_stale": ("    self:UpdateActions(nil)\n    self:UpdateCompare(nil)\n", "    self:UpdateActions(nil)\n"),
    "cmp_variant": ("    self:UpdateCompare(shown.sec)\n", "    self:UpdateCompare(sec)\n"),
    "cmp_no_open": ('    elseif what then\n        arsenal_pages.open("compare")', "    elseif what then\n        -- stays"),
    "cmp_open_first": ('    if what == "left" then\n        self:UpdateCompare(sec)', "    if false then\n        self:UpdateCompare(sec)"),
    "cmp_line_stale": ('    if what == "left" then\n        self:UpdateCompare(sec)\n', '    if what == "left" then\n'),
    "cmp_tab_dead": ('function ArsenalPDA:OnComparePage()\n    arsenal_pages.open("compare")',
                     "function ArsenalPDA:OnComparePage()\n    -- nothing"),
    "cmp_no_line": ('    self.cmp_status:SetText(can and (safe(arsenal_compare.line, sec) or "") or "")',
                    '    self.cmp_status:SetText("")'),
    "action_twice": ("    remove_action(id)\n    actions[#actions + 1]", "    actions[#actions + 1]"),
    "no_factions": ('        add(FACTION .. f, game.translate_string("st_faction_" .. f), models_of(FACTION .. f))\n', ""),
    "faction_by_name": ("        if a.cat ~= b.cat then return (order[a.cat] or 99) < (order[b.cat] or 99) end\n", ""),
    "faction_unsorted": ("    table.sort(out, function(a, b)\n        if a.cat ~= b.cat", "    local _ = (function(a, b)\n        if a.cat ~= b.cat"),
    "faction_list": ("    for _, e in ipairs(models_of(self.cat)) do", "    for _, e in ipairs(arsenal_data.list(self.cat)) do"),
    "read_this_row_only": ("    for key, row in pairs(self.cat_rows or {}) do\n        if row.glow and not fresh_in(key) then",
                           "    for key, row in pairs({ [self.cat] = self.cat_rows[self.cat] }) do\n        if row.glow and not fresh_in(key) then"),
    "row_bright": ('    if new then return "bright" end\n', ""),
    "cat_glow": ('fresh and "cat_glow" or nil', "nil"),
    "cat_bright": ('fresh and "bright" or "body"', '"body"'),
    "cat_fresh_unlisted": ("if listed(e) and is_new(e) then return true end", "if is_new(e) then return true end"),
    "no_pulse": ("if row.glow then row.glow:SetTextureColor(color) end", "-- still"),
    "pulse_flat": ("math.floor(GLOW_MIN + (GLOW_MAX - GLOW_MIN) * wave)", "GLOW_MAX"),
    "read_on_show": ("    local shown = e.variants[1]\n",
                     "    if arsenal_intel then arsenal_intel.viewed(e) end\n    local shown = e.variants[1]\n"),
    "no_click": ('    self:AddCallback("wpn_list", ui_events.LIST_ITEM_CLICKED, self.OnWeaponClicked, self)\n', ""),
    "click_glow_stays": ("        item.glow:Show(false)\n        item.glow = nil\n", ""),
    "click_cat_stays": ("        if row.glow and not fresh_in(key) then", "        if false then"),
    "click_count_stale": ('            row.name:SetTextColor(theme.argb(row.heading and "heading" or "body"))\n        end\n    end\n    self:SetCounts()\n',
                          '            row.name:SetTextColor(theme.argb(row.heading and "heading" or "body"))\n        end\n    end\n'),
    "header_no_new": ("    self.found_count:SetText(new > 0", "    self.found_count:SetText(false"),
    "not_studied_note": ('        text("entry_line", game.translate_string(addon and "st_arsenal_not_studied_addon" or "st_arsenal_not_studied"),\n'
                         '            "dim")\n', ""),
    "gate_fits": ("    -- what fits it, its camos, parts and repair kits, once it is studied\n    if know then",
                  "    -- what fits it, its camos, parts and repair kits, once it is studied\n    if true then"),
    "facts_rows": ("        if full then return rows end\n", ""),
    "facts_stash": ('        line(string.format(game.translate_string("st_arsenal_stashes_seen"), table.concat(names, ", ")))\n', ""),
    "facts_sold": ('        line(string.format(game.translate_string("st_arsenal_sold_at"), table.concat(names, ", ")))\n', ""),
    "kit_mine": ("            if f == mine then has = true end\n", ""),
    "where_unknown": ('line(game.translate_string(full and "st_arsenal_no_source" or "st_arsenal_where_unknown"), "dim")',
                      'line(game.translate_string("st_arsenal_no_source"), "dim")'),
    "learned_line": ("    elseif learned and learned.at then", "    elseif false then"),
    "viewed": ("    arsenal_intel.viewed(e)\n", ""),
    "known_header": ("    if immersive() then\n        local new", "    if false then\n        local new"),
    "story_names": ("            if t ~= n then names[#names + 1] = t end", "            names[#names + 1] = t"),
    "full_sources": ("    local up = full and safe(arsenal_data.turns_up_model, shown.sec) or {}",
                     "    local up = safe(arsenal_data.turns_up_model, shown.sec) or {}"),
    "armor_drop_rank": ("rank and string.format(game.translate_string(\"st_arsenal_drop_rank\")", "false and string.format(game.translate_string(\"st_arsenal_drop_rank\")"),
    "armor_drop_off": ("        if d and d.off then\n", "        if false then\n"),
    "armor_exchange": ("local ex = armor and safe(arsenal_data.exchange, shown.sec)", "local ex = nil"),
    "armor_max": ("if row.gr.track or not (MAXED[row.stat] or arsenal_data.ARMOR[e.cat]) then return nil end",
                  "if row.gr.track or not MAXED[row.stat] then return nil end"),
    "where_distinct": ("for _, list in ipairs({ distinct(from), distinct(gets) }) do", "for _, list in ipairs({ from, gets }) do"),
    "where_eco": ("        if k.economies then", "        if false then"),
    "where_free": ('or string.format(game.translate_string("st_arsenal_start_free"), who)', "or who"),
    "where_row_height": ("y = y + math.max(f:GetHeight(), r:GetHeight()) + 2", "y = y + f:GetHeight() + 2"),
    "where_made": ('line(string.format(game.translate_string("st_arsenal_made_from"), mf.from, mf.kit))',
                   "-- not shown"),
    "mark_read_never_shown": ("        self.mark_read:Show(new > 0)\n", ""),
    "mark_read_noop": ("    arsenal_intel.mark_all_read()\n", ""),
    "mark_read_rows_stale": ("    arsenal_intel.mark_all_read()\n    self:SetCounts()\n    self:FillCategories()\n    self:FillWeapons()\n",
                             "    arsenal_intel.mark_all_read()\n    self:SetCounts()\n"),
    "mark_read_unheard": ('    self:AddCallback("mark_read", ui_events.BUTTON_CLICKED, self.OnMarkRead, self)\n', ""),
    "sources_always": ("    local src = arsenal_mcm.sources() and safe(arsenal_sources.of, shown.sec)",
                       "    local src = safe(arsenal_sources.of, shown.sec)"),
    "sources_backslashes": (r'local function slashes(p) return (tostring(p):gsub("\\", "/")) end',
                            "local function slashes(p) return tostring(p) end"),
    "sources_no_files": ("            for _, f in ipairs(src.files) do\n", "            for _, f in ipairs({}) do\n"),
    "show_next_ignored": ("            self.cat, self.sec = e.cat, e.sec\n", ""),
    "show_next_sticky": ("        next_sec = nil\n        if e and listed(e) then", "        if e and listed(e) then"),
    # 1.8: groups that fold, the Show and Sort boxes, icons in the rows, the page opened where it was left
    "group_flat": ("    return arsenal_data.GROUPS or {", "    return nil or {"),
    "group_no_heading": ("            if g.flat or #g.cats < 2 then", "            if true then"),
    "group_one_heading": ("            if g.flat or #g.cats < 2 then", "            if g.flat then"),
    "fold_ignored": ("    view.folded[id] = (not view.folded[id]) or nil\n", ""),
    "fold_drops_cat": ("                            present[c] = true\n", ""),
    "fold_selects_nothing": ("        idx = g and self.cat_index[GROUP .. g.id]\n", ""),
    "heading_selects": ("    if item and not item.heading and item.key ~= self.cat then", "    if item and item.key ~= self.cat then"),
    "heading_color_lost": ('row.name:SetTextColor(theme.argb(row.heading and "heading" or "body"))',
                           'row.name:SetTextColor(theme.argb("body"))'),
    "heading_counts_one": ("                    n, f = n + cn, f + cf\n", ""),
    "show_missing": ('    if show == "missing" then return not found end\n', ""),
    "show_new_offered": ('        if s ~= "new" or immersive() then out[#out + 1] = s end', "        out[#out + 1] = s"),
    # the Show and Sort boxes' lists, the page's own
    "drop_unmarked": ("        d.list:SetSelectedIndex(cur - 1)\n", ""),
    "drop_unnamed": ("        d.box:TextControl():SetText(labels[cur])\n", ""),
    "drop_full_height": ("math.min(#labels, d.rows) * DROP_ROW_H", "d.rows * DROP_ROW_H"),
    "drop_uncapped": ("math.min(#labels, d.rows) * DROP_ROW_H", "#labels * DROP_ROW_H"),
    "drop_both_open": ("function ArsenalPDA:OpenDrop(id)\n    self:CloseDrops()\n", "function ArsenalPDA:OpenDrop(id)\n"),
    "drop_no_catcher": ("    d.frame:Show(true)\n    self.drop_catcher:Show(true)\n", "    d.frame:Show(true)\n"),
    "drop_back_never": ("    d.back:Show(true)\n", ""),
    "drop_back_left_open": ("        d.back:Show(false)\n        d.frame:Show(false)\n", "        d.frame:Show(false)\n"),
    "drop_back_unsized": ("    d.back:SetWndSize(size)\n", ""),
    "drop_back_over": ('        local back = xml:InitStatic("drop_back", self)\n        local frame = xml:InitFrame(id .. "_list", self)\n',
                       '        local frame = xml:InitFrame(id .. "_list", self)\n        local back = xml:InitStatic("drop_back", self)\n'),
    "drop_back_unplaced": ("        back:SetWndPos(frame:GetWndPos())\n", ""),
    "drop_catcher_deaf": ('    self:Register(self.drop_catcher, "drop_catcher")\n', ""),
    "drop_list_deaf": ('        self:Register(list, id .. "_list_box")\n', ""),
    "drop_pick_stays_open": ("    local i = self.drops[id].list:GetSelectedIndex() + 1\n    self:CloseDrops()\n",
                             "    local i = self.drops[id].list:GetSelectedIndex() + 1\n"),
    "drop_pick_off_by_one": ("self.drops[id].list:GetSelectedIndex() + 1", "self.drops[id].list:GetSelectedIndex()"),
    "drop_open_at_reset": ("        reveal = not same }\n    self:CloseDrops()\n", "        reveal = not same }\n"),
    "drop_escape_ignored": ("            and self.drop_catcher:IsShown() then", "            and false then"),
    "drop_escape_always": ("            and self.drop_catcher:IsShown() then", "            then"),
    "drop_escape_closes_window": ("        self:CloseDrops()\n        return true\n", "        self:CloseDrops()\n"),
    "drop_drawn_under": ("    self.cat = arsenal_data.CATEGORIES[1]\n    self.sec = nil\nend",
                         '    xml:InitStatic("rule_top", self)\n    self.cat = arsenal_data.CATEGORIES[1]\n    self.sec = nil\nend'),
    "drop_engine_combo": ('xml:Init3tButton("sort_box", self)', 'xml:InitComboBox("sort_box", self)'),
    "show_box_stale": ("    view.show = s\n    self:FillShowBox()\n", "    view.show = s\n"),
    "show_same_refills": ("    if not s or s == view.show then return end\n", "    if not s then return end\n"),
    "sort_same_refills": ("    if not o or o.key == view.sort[sort_mode(self.cat)] then return end\n",
                          "    if not o then return end\n"),
    "sort_ignored": ("    local up = sort_models(list, self.sort_key, view.reverse,\n        not (self.cat and self.cat:sub(1, #FACTION) == FACTION))\n",
                     "    local up = true\n"),
    "sort_faction_unnamed": ('    if key == "kind" or (key == "name" and by_name) then', '    if key == "kind" or key == "name" then'),
    "sort_name_unreversed": ("            for i = 1, math.floor(#list / 2) do list[i], list[#list + 1 - i] = list[#list + 1 - i], list[i] end\n", ""),
    "sort_unknown_first": ("            if va ~= nil and vb == nil then return true end\n            if va == nil and vb ~= nil then return false end\n", ""),
    "sort_leaks": ("    if not studied(e) then return nil end\n    local sec = shown_variant(e).sec", "    local sec = shown_variant(e).sec"),
    "sort_no_reverse": ("    view.reverse = not view.reverse\n", ""),
    "sort_arrow_fixed": ('self.sort_arrow:InitTexture(up and "ui_scroll_btn_up" or "ui_scroll_btn_down")',
                         'self.sort_arrow:InitTexture("ui_scroll_btn_up")'),
    "sort_forgotten": ("        if o.key == view.sort[sort_mode(self.cat)] then cur = i end", "        if false then cur = i end"),
    "sort_one_memory": ('    return (key and key:sub(1, #FACTION) == FACTION) and "faction" or "cat"', '    return "cat"'),
    "sort_faction_kind": ('        add("kind", T("st_arsenal_sort_kind"))\n', ""),
    "icons_none": ("            { icon = shown_variant(e).sec })", "            nil)"),
    "icon_untinted": ("    icon:SetTextureColor(GetARGB(255, v, v, v))\n    return icon", "    return icon"),
    "icon_first_variant": ("{ icon = shown_variant(e).sec }", "{ icon = e.sec }"),
    "icon_read_stays_dim": ("    item:Paint(role_of(e, false))\n", "    item.name:SetTextColor(theme.argb(role_of(e, false)))\n"),
    "restore_none": ("    if self.restore then self:Restore() end\n", ""),
    "restore_unrecorded": ("    view.wpn_scroll = self.wpn_list:GetCurrentScrollPos()\n", ""),
    "restore_now": ("    self.restore = kept\n", "    self.restore = kept\n    self:Restore()\n"),
    "restore_cat_lost": ("    self.cat = view.cat or self.cat\n", ""),
    "restore_no_reveal": ("        if i and i >= 0 then scroll_to(self.wpn_list, math.max(0, i - 3) * MODEL_ROW_H) end\n", ""),
    # Back, with MAC's tile or without it (the page; then arsenal_pages, PAGES_MUTANTS)
    "back_unplaced": ("    arsenal_pages.show_back(self.back_row, self.flat)\n    self:SetCounts()", "    self:SetCounts()"),
    "back_row_empty": ("arsenal_pages.back_row(self.btn_back, self.action_btns)", "arsenal_pages.back_row(self.btn_back, {})"),
    "back_flat_as_pda": ("    arsenal_pages.show_back(self.back_row, self.flat)\n    self:SetCounts()",
                         "    arsenal_pages.show_back(self.back_row, false)\n    self:SetCounts()"),
    "pages_back_ignores_flat": ("    local back = flat or back_to_launcher()", "    local back = back_to_launcher()"),
    "pages_back_never_hidden": ("    row.back:Show(back)\n", ""),
    "pages_buttons_stay": ("        b:SetWndPos(vector2():set(row.xs[i] + (back and 0 or row.shift), b:GetWndPos().y))\n", ""),
    "pages_shift_short": ("    row.shift = back:GetWndPos().x + back:GetWidth() - right", "    row.shift = back:GetWndPos().x - right"),
    "pages_shift_inverted": ("(back and 0 or row.shift)", "(back and row.shift or 0)"),
}

PAGES_MUTANTS = {"pages_back_ignores_flat", "pages_back_never_hidden", "pages_buttons_stay", "pages_shift_short",
                 "pages_shift_inverted"}


def sizes():
    root = ET.fromstring(XML.split("?>", 1)[1])
    out = {}
    for el in root:
        out[el.tag] = [float(el.get(k, 0)) for k in ("x", "y", "width", "height")]
    return out


def main():
    src, pages = SRC, PAGES
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        if mutant in PAGES_MUTANTS:
            assert pages.count(old) == 1, old
            pages = pages.replace(old, new)
        else:
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

    def show_only(u, kind):
        """pick `kind` in the Show box, as the player does: a click on the box opens its list,
        and a click on the option there selects it, then is heard"""
        opts = list(u.show_opts.values())
        u.cb.show_box()
        u.drops.show.list.sel = opts.index(kind)
        u.clk.show_list_box()

    sz = sizes()
    used = sorted(set(re.findall(r'xml:Init\w+\("([\w:]+)"', src)))
    missing = [u for u in used if u not in sz]
    check(not missing, "every element the script asks for is in the layout: %s" % (missing or "%d used" % len(used)))

    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(STUBS, lua.table_from({k: lua.table_from(v) for k, v in sz.items()}), lua.table_from(STRINGS))
    # the real arsenal_sources, over the ini_sys stand-in
    lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
             "setfenv(f, env); f(); arsenal_sources = env end")(
        io.open(os.path.join(GD, "scripts", "arsenal_sources.script"), encoding="latin-1").read())
    cmp_src = io.open(os.path.join(GD, "scripts", "arsenal_compare.script"), encoding="latin-1").read()
    lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
             "setfenv(f, env); f(); arsenal_compare = env end")(cmp_src)
    lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
             "setfenv(f, env); f(); arsenal_pages = env end")(pages)
    lua.execute("arsenal_pages.open = function(page, sec) opened_pages[#opened_pages + 1] = { page = page, sec = sec } end")
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

    check(ui.found_count.text == "Found 1 of 6", "count line: %s" % ui.found_count.text)
    items = list(ui.cat_list["items"].values())
    cats = [(r.key, r.name.text, r.count.text) for r in items]
    check(cats == [("pistols", "Pistols", "1/2"), ("rifles", "Rifles", "0/1"), ("melee", "Melee", "0/1"),
                   ("medium", "Medium armor", "0/1"), ("ammo", "Ammo", "0/1")],
          "categories with found/total models, empty ones left out, and nothing else: %s" % cats)
    tog = ui.by_faction_check
    check(tog is not None and tog.checked is False, "the faction toggle, off: %s" % (tog and tog.checked,))

    # the toggle: every faction with gear instead, found/total of it, in the factions' order; a
    # faction's gear in the categories' order; each view back on the row chosen last in it
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    tog.checked = True
    ui.cb.by_faction()
    facs = [(r.key, r.count.text if r.count else None) for r in ui.cat_list["items"].values()]
    check(facs == [("f:stalker", "1/3"), ("f:bandit", "1/2")],
          "with the toggle, the factions with gear instead, found/total of it, in the factions' order: %s" % facs)
    gear = [r.name.text for r in ui.wpn_list["items"].values()]
    check(ui.cat == "f:stalker" and ui.cat_list.sel == 0
          and gear == ["Fort-17", "AK-74 Tactical Modernized Carbine of the Northern Expedition Special Forces Unit", "SEVA"],
          "the first faction's gear, pistols to suits: %s" % gear)
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    tog.checked = False
    ui.cb.by_faction()
    keys = [r.key for r in ui.cat_list["items"].values()]
    check(keys[0] == "pistols" and ui.cat == "rifles" and ui.cat_list.sel == 1
          and [r.key for r in ui.wpn_list["items"].values()] == ["wpn_ak74"],
          "toggled back: the categories, on the one chosen before: %s %s" % (ui.cat, keys))
    tog.checked = True
    ui.cb.by_faction()
    check(ui.cat == "f:bandit" and ui.cat_list.sel == 1, "and the factions on theirs: %s" % ui.cat)
    tog.checked = False
    ui.cb.by_faction()
    ui.cat_list.sel = 0
    ui.cb.cat_list()
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

    show_only(ui, "found")
    rows = [r.name.text for r in ui.wpn_list["items"].values()]
    check(rows == ["Fort-17"], "found only: %s" % rows)
    fort = shown(ui)
    texts = texts_of(fort)
    check("Found 14.05.2012: looted from a stash in Cordon" in texts, "when, how and where: %s" % texts[:3])
    rowboxes = [c for c in fort.children.values() if c.path in ("stats_box", "item_info:stats_box")]
    card = [(c.stat or "", [k.text for k in c.children.values() if k.text and k.path != "entry_max"])
            for c in rowboxes]
    check(card == [("accuracy", []), ("", ["Fire Rate", "400 / 450 RPM"])],
          "the card's own row where the variants agree, each value where they differ: %s" % card)
    i = texts.index("Variants:") if "Variants:" in texts else -1
    check(i >= 0 and texts[i + 1:i + 3] == ["Fort-17 (reliability 89%)",
                                             "Fort-17 (reliability 91%), found 14.05.2012: looted from a stash in Cordon"],
          "the variants, the found one with when, how and where: %s" % texts[i:i + 3])
    lines = {c.text: c.color for c in fort.children.values() if c.text}
    check(lines.get("Fort-17 (reliability 89%)") == "dim"
          and lines.get("Fort-17 (reliability 91%), found 14.05.2012: looted from a stash in Cordon") == "good",
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

    def after_in(ts, head, n):
        i = ts.index(head) if head in ts else -1
        return ts[i + 1:i + 1 + n] if i >= 0 else []

    # where to find it: a row per faction with its ranks (runs as ranges, all as every rank, a
    # rankless squad as special), stashes, Nimble (what he takes first, each line once), the gun
    # a kit makes it of, new-game kits (every faction, an economy lock)
    check(after("Where to find:", 9) == ["Carried by:", "Bandit", "Rookie – Trainee, Professional, Expert, Legend",
                                          "Loner", "Experienced – Veteran, Legend", "UNISG", "special squads",
                                          "Military", "every rank"],
          "the factions that carry it, with their ranks: %s" % after("Where to find:", 9))
    check(after("every rank", 8) == ["In stashes: Cordon 1.2% (rare 3.4%), Garbage <0.1%",
                                     "The chance one stash there holds it.",
                                     "From Nimble, for Fort-12 / Fort-12 (old) and 45000 RU",
                                     "Nimble gives the Fort-17 Nimble for it and 30000 RU",
                                     "Made from the Fort-12 with the Conversion Kit",
                                     "New-game kit, 150 points: Loner, Bandit", "New-game kit, free: every faction",
                                     "New-game kit, 200 points: Duty; Tourist (Easy), Scavenger (Medium) only"],
          "stashes with the chance one holds it (a rare stash's where it differs, a sliver as one), Nimble, a kit, "
          "new-game kits: %s" % after("every rank", 8))
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
    check(after("Ammo", 18) == ["Round", "Damage", "AP", "m/s", "100 m", "5.45 FMJ", "38", "27", "924", "93%",
                                "12x70 Buckshot", "19 x 9", "3", "325", "-",
                                "Damage from this gun, armor piercing (AP), bullet speed, and the damage left at 100 m.",
                                "Other variants: 9x18 FMJ", "By upgrade: 9x19 FMJ, 9x19 AP"],
          "a gun's rounds as a table (pellets, no falloff), what only another variant chambers, then what an "
          "upgrade converts it to: %s" % after("Ammo", 18))
    cells = [c for c in fort.children.values() if c.path == "round_cell"]
    rnames = [c for c in fort.children.values() if c.path == "round_name"]
    check(len(cells) == 12 and [c.x for c in cells[:4]] == [144, 194, 244, 294] and len(rnames) == 3
          and all(c.y == rnames[i // 4].y for i, c in enumerate(cells)) and cells[0].color == "dim"
          and rnames[0].color == "dim" and cells[4].color is None,
          "four columns beside each name, the header dim: %s" % [(c.x, c.y) for c in cells[:5]])
    check("Hit power: 0.465" in texts and "Jam chance: 0.3% a shot, 1.7% once its parts wear below 80%" in texts
          and texts.index("Hit power: 0.465") == texts.index("Fire modes: 1 / A (1 / 3 / A by upgrade)") + 1,
          "hit power and jams under the fire modes, the engine's chance and with worn parts: %s"
          % [t for t in texts if t.startswith("Hit") or t.startswith("Jam")])
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

    show_only(ui, "all")
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
    check(after("Where to find:", 8) == ["Worn by:", "Ecologist", "Rookie \u2013 Professional", "Duty", "special squads",
                                          "Drops from a body 50% of the time once your rank reaches 1747 (Rookie)",
                                          "In stashes: Yantar 5.0%", "The chance one stash there holds it."]
          and "Carried by:" not in texts,
          "who wears it, how it drops, stashes (none in rare ones); no carriers: %s" % after("Where to find:", 8))
    check(after("Against bullets:", 3) == ["Stops rounds up to 5.45 FMJ (AP 27); 12x76 Dart (AP 42) and stronger pierce it.",
                                           "Stops 23 of the 43 rounds that turn up.",
                                           "A hit does 45% of its damage when stopped, 75% when it pierces."]
          and texts.index("Against bullets:") < texts.index("Where to find:"),
          "a suit against bullets: the strongest round it stops, the weakest that pierces, how many, what a hit "
          "does either way: %s" % after("Against bullets:", 3))
    check(after("The chance one stash there holds it.", 4) == [
              "Carried by Strelok", "Crafted at a workbench",
              "From Petrenko, for any of 12 suits and 10000 RU (Duty only)",
              "Sidorovich, Owl gives the Exoskeleton for it and 45000 RU (Loner only)"],
          "story characters (a name with no text left out), crafting, the Armor Exchange both ways: %s"
          % after("The chance one stash there holds it.", 4))
    check(after("Repair kits:", 1) == ["Basic Sewing Kit"], "its repair kits: %s" % after("Repair kits:", 1))
    # a suit that stops every round, one that stops none
    def page(cat, row=0):
        try:
            ui.cat_list.sel = (cat + 1) % 5
            ui.cb.cat_list()
            ui.cat_list.sel = cat
            ui.cb.cat_list()
            if row:
                ui.wpn_list.sel = row
                ui.cb.wpn_list()
        except L.LuaError as err:
            return ["error: %s" % str(err)[:80]]
        return texts_of(shown(ui))
    g.PEN = "all"
    t_all = page(3)
    g.PEN = "none"
    t_none = page(3)
    g.PEN = None
    check(after_in(t_all, "Against bullets:", 2) == ["Stops every round that turns up, the strongest 5.45 FMJ (AP 27).",
                                                     "Stops 43 of the 43 rounds that turn up."]
          and after_in(t_none, "Against bullets:", 2) == ["Every round pierces it, from 12x76 Dart (AP 42) up.",
                                                          "Stops 0 of the 43 rounds that turn up."],
          "a suit that stops every round, one that stops none: %s %s"
          % (after_in(t_all, "Against bullets:", 2), after_in(t_none, "Against bullets:", 2)))

    # traders by tier, with what unlocks each: a toolkit, toolkits, a drug kit or the story,
    # goodwill or Heavy Pockets; a gun that never jams says so
    ak = page(1)
    check(after_in(ak, "Sold by traders:", 4) == ["Tier 1: Sidorovich, mechanics", "Tier 2, after a toolkit: Mechanic One",
                                                  "Tier 3, after 2 toolkits, after a drug kit or later in the story: Beard",
                                                  "Tier 4, goodwill 1500 or Heavy Pockets: Owl"]
          and "Sold by traders" not in ak and "Jam chance: none" in ak,
          "sold by, a row per tier with what unlocks it; never jams: %s" % after_in(ak, "Sold by traders:", 4))
    g.TEXT["encyclopedia_achievements_heavy_pockets"] = "HEAVY POCKETS"
    ak = page(1)
    g.TEXT["encyclopedia_achievements_heavy_pockets"] = None
    check("Tier 4, goodwill 1500 or Heavy Pockets: Owl" in ak, "Heavy Pockets in Arsenal's words, not the game's "
          "capitalized achievement title: %s" % [t for t in ak if t.startswith("Tier 4")])
    pm = page(0)
    check("Sold by traders" in pm and "Sold by traders:" not in pm and "Hit power: 0.45" in pm
          and "Jam chance: 1.7% a shot once its parts wear below 80%" in pm,
          "a trader without tiers; hit power; jams with worn parts only: %s"
          % [t for t in pm if t.startswith("Sold") or t.startswith("Hit") or t.startswith("Jam")])

    # a round's page: its own values, the guns that fire it; no card, fire modes or weight
    page(4)
    rnd = shown(ui)
    t_rnd = texts_of(rnd)
    stats = [c.stat for c in rnd.children.values() if c.stat]
    check(ui.sec == "ammo_545" and not stats and not any(t.startswith("Fire modes") or t.startswith("Weight")
                                                         or t.startswith("Hit power") for t in t_rnd),
          "a round: no card, fire modes, hit power or weight: %s" % t_rnd[:6])
    check(after_in(t_rnd, "Not found yet", 13) == ["Damage", "x1.14", "Armor piercing", "27", "Bullet speed", "x1.5",
                                                   "Left at 50/100/200 m", "97% / 93% / 87%", "Against mutants", "+15%",
                                                   "Effect", "3 Shock stacks", "20% chance to stagger"],
          "its values, a row each, then ArtiGrok's effects, a second effect under the first's name: %s"
          % after_in(t_rnd, "Not found yet", 13))
    rs = [c for c in rnd.children.values() if c.path == "round_stat"]
    rv = [c for c in rnd.children.values() if c.path == "round_value"]
    check(len(rs) == 7 and all(a.y == b.y for a, b in zip(rs, rv)) and rv[0].x == 154 and rs[6].text == ""
          and len({a.y for a in rs}) == 7,
          "a value beside its name, the second effect's name blank: %s" % [(a.y, b.y, a.text) for a, b in zip(rs, rv)])
    check(after_in(t_rnd, "Fired by:", 1) == ["AK-74 Tactical Modernized Carbine of the Northern Expedition Special Forces "
                                              "Unit, Ghost"],
          "the guns that fire it: %s" % after_in(t_rnd, "Fired by:", 1))
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
NEW = { wpn_pm = true, wpn_ghost = true }
FACTS = { wpn_pm = { stash = { l02_garbage = true }, sold = { Sidorovich = true } },
          wpn_fort = { carried = { bandit = { trainee = true }, stalker = { legend = true } }, ways = { kit = true } } }
LEARNED = { wpn_pm = { at = { d = 3, mo = 6, y = 2012, lvl = "l01_escape" }, how = { kind = "pda" } } }
arsenal_intel = {
    jailbroken = function() return false end,
    listed = function(e) return KNOWN[e.sec] == true end,
    studied = function(e) return STUDIED[e.sec] == true end,
    facts = function(e) return FACTS[e.sec] end,
    learned = function(e) return LEARNED[e.sec] end,
    describe = function(how, at) return "a Duty PDA" .. (at and at.lvl and (" in " .. game.translate_string(at.lvl)) or "") end,
    is_new = function(e) return NEW[e.sec] == true end,
    viewed = function(e) NEW[e.sec] = nil end,
    count_new = function() local n = 0; for k in pairs(NEW) do if KNOWN[k] then n = n + 1 end end; return n end,
    player_faction = function() return "stalker" end,
}
""")
    ui.cat_list.sel = 0
    ui = m.get_ui()
    check(ui.found_count.text == "Known 3 \u00b7 Found 1 of 6 \u00b7 1 new",
          "count line, with what is new: %s" % ui.found_count.text)
    cat = ui.cat_list["items"][1]
    check(cat.name.text == "Pistols" and cat.name.color == "bright" and cat.glow is not None
          and cat.glow.path == "cat_glow", "a category with something new glows: %s %s" % (cat.name.text, cat.name.color))
    other = ui.cat_list["items"][2]
    check(other.glow is None and other.name.color == "body", "one without does not: %s" % other.name.color)
    def faction_rows():
        ui.by_faction_check.checked = True
        ui.cb.by_faction()
        return {r.key: r for r in ui.cat_list["items"].values()}

    def category_view():
        ui.by_faction_check.checked = False
        ui.cb.by_faction()
    rows_by_key = faction_rows()
    bandit, loner = rows_by_key.get("f:bandit"), rows_by_key.get("f:stalker")
    check(bandit is not None and bandit.glow is not None and loner is not None and loner.glow is None,
          "with the toggle, the faction whose gear holds the new PM glows; the other does not")
    category_view()
    cat = ui.cat_list["items"][1]
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    rows = list(ui.wpn_list["items"].values())
    check([r.name.text for r in rows] == ["PM", "Fort-17"] and rows[0].glow is not None
          and rows[0].glow.path == "wpn_glow" and rows[0].name.color == "bright" and rows[1].glow is None,
          "only what is known; the new one glows, brighter: %s" % [(r.name.text, r.name.color) for r in rows])
    pulse = []
    for t in (500, 1500):
        g.TIME = t
        ui.Update(ui)
        pulse.append(rows[0].glow.tcolor)
    check(pulse == ["heading@110", "heading@40"] and cat.glow.tcolor == "heading@40",
          "the glow brightens and fades over two seconds: %s" % pulse)
    check(lua.eval("NEW.wpn_pm") is True, "shown first by itself, it stays new until clicked")
    pm = shown(ui)
    texts = texts_of(pm)
    stats = [c.stat for c in pm.children.values() if c.stat]
    i = texts.index("Where to find:") if "Where to find:" in texts else -1
    check("Learned 03.06.2012 from a Duty PDA in Cordon" in texts and not stats and not any(t.startswith("Weight") for t in texts)
          and any(t.startswith("Not studied yet") for t in texts),
          "a known model not yet studied: how it was learned, no stats: %s %s" % (stats, texts[:5]))
    check(ui.cmp_add.shown is False and ui.cmp_status.text == "", "and no Compare: its stats are unknown")
    check(texts[i + 1:i + 3] == ["Seen in stashes at Garbage", "Seen for sale at Sidorovich"],
          "where to find it: only where it was seen: %s" % texts[i:i + 3])
    # a click on it, though it is shown already: read, like an opened letter
    pm_glow, cat_glow = rows[0].glow, cat.glow
    ui.wpn_list.sel = 0
    click = ui.clk and ui.clk.wpn_list
    check(click is not None, "a click on the gun list is heard")
    if click is not None:
        click()
    check(lua.eval("NEW.wpn_pm") is None and rows[0].glow is None and pm_glow.shown is False
          and rows[0].name.color != "bright", "clicked: read, its glow gone, its usual color: %s" % rows[0].name.color)
    check(cat.glow is None and cat_glow.shown is False and cat.name.color == "body",
          "nothing listed in it new any more: the category stops glowing")
    bandit = faction_rows().get("f:bandit")
    check(bandit is not None and bandit.glow is None and bandit.name.color == "body",
          "and so does the faction it belongs to")
    # a new gun two factions carry: both glow; read under one, both stop
    lua.execute("NEW.wpn_fort = true")
    category_view()
    rows_by_key = faction_rows()
    check(rows_by_key["f:stalker"].glow is not None and rows_by_key["f:bandit"].glow is not None,
          "a new gun two factions carry: both glow")
    keys = [r.key for r in ui.cat_list["items"].values()]
    ui.cat_list.sel = keys.index("f:stalker")
    ui.cb.cat_list()
    names = [r.name.text for r in ui.wpn_list["items"].values()]
    ui.wpn_list.sel = names.index("Fort-17") if "Fort-17" in names else 0
    ui.clk.wpn_list()
    check(lua.eval("NEW.wpn_fort") is None and rows_by_key["f:stalker"].glow is None
          and rows_by_key["f:bandit"].glow is None, "read under one faction, read under both")
    category_view()
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    check(ui.found_count.text == "Known 3 \u00b7 Found 1 of 6", "the count line drops the new count: %s" % ui.found_count.text)
    ui = m.get_ui()
    rows = list(ui.wpn_list["items"].values())
    check(rows[0].glow is None and rows[0].name.color != "bright", "opened again: still read")
    ui.cat_list.sel = 0
    ui.cb.cat_list()
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
    # a round the player knows: its page names only the guns he knows fire it
    lua.execute("KNOWN.ammo_545 = true; STUDIED.ammo_545 = true")
    ui = m.get_ui()
    keys = [r.key for r in ui.cat_list["items"].values()]
    ui.cat_list.sel = keys.index("ammo") if "ammo" in keys else 0
    ui.cb.cat_list()
    t = texts_of(shown(ui))
    check(ui.sec == "ammo_545" and after_in(t, "Fired by:", 1) == ["AK-74 Tactical Modernized Carbine of the Northern "
                                                                   "Expedition Special Forces Unit"],
          "immersive: only the known guns that fire it: %s" % after_in(t, "Fired by:", 1))

    check(ui.mark_read.shown is False, "nothing new: no Mark all read")
    intel = g.arsenal_intel
    lua.execute("arsenal_intel = nil")
    ui = m.get_ui()

    # the switch to Workbench: this page pressed, the other half opens Workbench
    check(ui.page_catalog.active is True, "the switch shows the catalog pressed")
    ui.cb.page_workbench()
    check(len(g.opened_pages) == 1 and g.opened_pages[1].page == "workbench", "the switch opens Workbench")

    # the model's button (ui_arsenal.add_action: Workbench's Customize, or another app's): none
    # added, none shown; one shows where it applies and runs on the section shown; it hides on
    # other pages and with nothing shown; one slot, the first that applies
    btns = lambda: [ui.action_btns[1]]
    check(ui.action_btns[2] is None, "one slot for the model's button: %s" % ui.action_btns[2])
    check(all(b.shown is False for b in btns()), "no app added a button: none shows")
    lua.execute("RAN = nil")
    m.add_action("workbench", lua.eval('{ label = "st_wb", run = function(sec) RAN = sec end, '
                                       'show = function(sec) return sec ~= "wpn_knife" end }'))
    ui = m.get_ui()
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    ui.wpn_list.sel = 1
    ui.cb.wpn_list()
    b = btns()
    check(ui.sec == "wpn_fort" and b[0].shown is True and b[0].text == "st_wb",
          "added: its button shows on the page, labelled: %s %s" % (b[0].shown, b[0].text))
    click = ui.cb.action_1 if ui.cb else None
    if click is not None:
        click()
    check(g.RAN == "wpn_fort17", "a click runs it on the section shown, the found variant: %s" % g.RAN)
    ui.cat_list.sel = 2
    ui.cb.cat_list()
    check(ui.sec == "wpn_knife" and btns()[0].shown is False, "a page it does not apply to: hidden")
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    show_only(ui, "found")
    check(ui.sec is None and btns()[0].shown is False, "nothing shown, no button: %s" % ui.sec)
    show_only(ui, "all")
    m.add_action("workbench", lua.eval('{ label = "st_wb2", run = function(sec) end }'))
    m.add_action("other", lua.eval('{ run = function(sec) error("boom") end }'))
    ui = m.get_ui()
    b = btns()
    check(b[0].shown and b[0].text == "st_wb2",
          "added again, replaced; the first that applies takes the slot: %s" % [(x.shown, x.text) for x in b])
    m.remove_action("workbench")
    ui = m.get_ui()
    b = btns()
    check(b[0].shown and b[0].text == "other", "with the first gone, the next takes the slot: %s" % b[0].text)
    g.logged = lua.table_from([])
    try:
        ui.cb.action_1()
        ok = True
    except L.LuaError:
        ok = False
    check(ok and len(g.logged) == 1 and "other" in g.logged[1], "a button that fails is logged, not raised: %s"
          % list(g.logged.values()))
    m.remove_action("workbench")
    m.remove_action("other")
    ui = m.get_ui()
    check(all(x.shown is False for x in btns()), "removed: gone")

    ui.cb.btn_back()
    check(g.pda_section == "eptLauncher", "Back returns to the launcher")

    # Compare (arsenal_compare): over the entry, for what has a card, with a line saying what a
    # click does; the first waits on the left, a second (the variant the page shows) opens
    # Compare's page; the switch opens it too
    def show(sec):
        keys = [r.key for r in ui.cat_list["items"].values()]
        for ci in range(len(keys)):
            ui.cat_list.sel = ci
            ui.cb.cat_list()
            models = [r.key for r in ui.wpn_list["items"].values()]
            if sec in models:
                ui.wpn_list.sel = models.index(sec)
                ui.cb.wpn_list()
                return ui.sec
        return None

    cmp = g.arsenal_compare
    cmp.clear()
    show_only(ui, "all")
    ui = m.get_ui()
    n_open = len(g.opened_pages)
    knife = (show("wpn_knife"), ui.cmp_add.shown, ui.cmp_status.text)
    ammo = (show("ammo_545"), ui.cmp_add.shown)
    check(knife == ("wpn_knife", False, "") and ammo == ("ammo_545", False),
          "no Compare for a knife or a round: %s %s" % (knife, ammo))
    show("wpn_pm")
    check(ui.cmp_add.shown is True and ui.cmp_status.text == "",
          "a gun: Compare, and no line while nothing is compared: %r" % ui.cmp_status.text)
    ui.cb.cmp_add()
    check(tuple(cmp.sides()) == ("wpn_pm", None) and len(g.opened_pages) == n_open
          and ui.cmp_status.text == "Now pick another gun",
          "the first waits on the left, the page stays, its line asks for another: %s %r"
          % (tuple(cmp.sides()), ui.cmp_status.text))
    show("wpn_fort")
    check(ui.cmp_status.text == "vs. PM", "another gun's line names what it joins: %r" % ui.cmp_status.text)
    ui.cb.cmp_add()
    check(tuple(cmp.sides()) == ("wpn_pm", "wpn_fort17") and len(g.opened_pages) == n_open + 1
          and g.opened_pages[n_open + 1].page == "compare",
          "the second, the variant the page shows, and Compare's page opens: %s" % (tuple(cmp.sides()),))
    show("wpn_pm")
    check(ui.cmp_status.text == "In the comparison", "one in already says so: %r" % ui.cmp_status.text)
    ui.cb.cmp_add()
    check(len(g.opened_pages) == n_open + 2 and g.opened_pages[n_open + 2].page == "compare",
          "and a click on it opens the page")
    show("sci_suit")
    check(ui.cmp_add.shown is True and ui.cmp_status.text == "Starts a new comparison", "a suit: %r" % ui.cmp_status.text)
    show("wpn_ak74")
    check(ui.cmp_status.text == "Replaces Fort-17", "a third gun replaces the right: %r" % ui.cmp_status.text)
    show_only(ui, "found")
    check(ui.sec is None and ui.cmp_add.shown is False and ui.cmp_status.text == "", "nothing shown: no Compare")
    show_only(ui, "all")
    n_open = len(g.opened_pages)
    ui.cb.page_compare()
    check(len(g.opened_pages) == n_open + 1 and g.opened_pages[n_open + 1].page == "compare", "the switch opens Compare")
    cmp.clear()

    # the flat window: the 2D PDA's frame behind the page, where the PDA puts its pages
    paths = lambda w: [c.path for c in w.children.values()]
    check("flat_bezel" not in paths(ui), "the PDA page has no frame of its own")
    g.actor_alive = False
    check(m.open_flat() is None, "no window while the player is dead")
    g.actor_alive = True
    ui.by_faction_check.checked = True
    ui.cb.by_faction()
    flat = m.open_flat()
    check(flat is not None and flat.by_faction_check.checked is True
          and all(str(r.key).startswith("f:") for r in flat.cat_list["items"].values()),
          "the window opens on the view the page last had: %s"
          % (flat and [r.key for r in flat.cat_list["items"].values()],))
    ui.by_faction_check.checked = False
    ui.cb.by_faction()
    check(flat is not None and flat.IsShown(flat), "the key opens the window")
    if flat is not None:
        kids = paths(flat)
        check(kids[:2] == ["flat_bezel", "flat_caption"], "the frame first, behind everything: %s" % kids[:3])
        check(list(flat.rect.values())[:2] == [112, 34], "placed as the PDA places its pages: %s" % list(flat.rect.values()))
        check(flat.found_count.text == "Found 1 of 6" and flat.detail.content and flat.detail.content[1] is not None,
              "the window fills like the page")
        ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_A, g.ui_events.WINDOW_KEY_PRESSED)
        check(flat.IsShown(flat) and not ret, "another key leaves it open")
        flat.cb.sort_box()
        ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_ESCAPE, g.ui_events.WINDOW_KEY_PRESSED)
        check(flat.IsShown(flat) and ret and flat.drops.sort.frame.shown is False,
              "Escape with a drop-down open closes the drop-down, the window stays")
        ret = flat.OnKeyboard(flat, g.DIK_keys.DIK_ESCAPE, g.ui_events.WINDOW_KEY_PRESSED)
        check(not flat.IsShown(flat) and ret, "Escape closes it")
        m.open_flat()
        flat.OnKeyboard(flat, g.DIK_keys.DIK_F7, g.ui_events.WINDOW_KEY_PRESSED)
        check(not flat.IsShown(flat), "the key closes it again")
        m.open_flat()
        g.pda_section = None
        flat.cb.btn_back()
        check(not flat.IsShown(flat) and g.pda_section is None, "Back closes it, leaving the PDA alone")
        # Back in the PDA goes to MAC's launcher: there while the catalog has its tile; with a PDA
        # tab of its own instead, it goes, and the button left of it moves into its place. Flat,
        # Back closes the window, so it stays.
        back_x, act_x = sz["btn_back"][0], sz["action_btn"][0]
        pda_btn = ui.action_btns[1]
        tiled = (ui.btn_back.shown is not False, pda_btn.x)
        g.TILE = False
        m.get_ui()
        m.open_flat()
        untiled = (ui.btn_back.shown, pda_btn.x)
        flat_row = (flat.btn_back.shown is not False, flat.action_btns[1].x)
        flat.Close(flat)
        g.TILE = True
        m.get_ui()
        again = (ui.btn_back.shown, pda_btn.x)
        check(tiled == (True, act_x) and untiled == (False, back_x) and flat_row == (True, act_x)
              and again == (True, act_x),
              "Back while the catalog has MAC's tile, the button beside it in place; with a tab instead, "
              "no Back, the button in its place; flat, Back stays: %s %s %s %s" % (tiled, untiled, flat_row, again))

    # the footer: Silence is MCM's "PDA notifications" seen here too, ticked while the messages
    # are off, written on a click and read afresh at every open; under the lists, the credit line
    sil = ui.silence
    check(sil is not None and sil.checked is False and ui.credit.text == "Arsenal v1.2.1 by Windwalker",
          "the footer: Silence unticked while the messages are on, and the credit line: %s, %s"
          % (sil and sil.checked, ui.credit and ui.credit.text))
    if sil is not None:
        sil.checked = True               # the engine ticks the box, then calls back
        ui.cb.silence()
        check(g.NEWS_ON is False, "ticking Silence turns the messages off: %s" % g.NEWS_ON)
        sil.checked = False
        ui.cb.silence()
        check(g.NEWS_ON is True, "unticking it turns them on: %s" % g.NEWS_ON)
        g.NEWS_ON = False                # silenced in MCM: the next open shows it
        m.get_ui()
        check(sil.checked is True, "silenced in MCM, the box is ticked at the next open: %s" % sil.checked)
        g.NEWS_ON = True
        m.get_ui()
        check(sil.checked is False, "and unticked once they are on again: %s" % sil.checked)
    # the jailbreak lamp: gone while MCM's jailbreak is off, lit in the warning color while it
    # is on, read afresh at every open
    lamp, lbl = ui.jailbreak, ui.jailbreak_lbl
    check(lamp is not None and lbl is not None and lamp.shown is False and lbl.shown is False,
          "the footer: no jailbreak lamp while the jailbreak is off: %s, %s"
          % (lamp and lamp.shown, lbl and lbl.shown))
    if lamp is not None and lbl is not None:
        warn = "warn"                    # the theme stub names the role
        g.JAILBREAK = True
        m.get_ui()
        check(lamp.shown is True and lbl.shown is True and lamp.tcolor == warn and lbl.color == warn,
              "jailbroken in MCM, the next open lights the lamp and its label: %s %s %s %s"
              % (lamp.shown, lbl.shown, lamp.tcolor, lbl.color))
        g.JAILBREAK = False
        m.get_ui()
        check(lamp.shown is False and lbl.shown is False,
              "and it goes out once the jailbreak is off: %s, %s" % (lamp.shown, lbl.shown))
    # nothing on the page reaches into the footer, which keeps the content box's last rows
    body = ["by_faction_lbl", "by_faction", "cat_list", "rule_cat", "show_box", "sort_box", "sort_dir", "wpn_list",
            "rule_wpn", "detail"]
    foot = ["silence_lbl", "silence", "jailbreak", "jailbreak_lbl", "mark_read", "credit"]
    rule = sz["rule_foot"][1]
    low = [(k, sz[k][1] + sz[k][3]) for k in body if sz[k][1] + sz[k][3] > rule - 2]
    out = [k for k in foot if sz[k][1] < rule or sz[k][1] + sz[k][3] > 709]
    check(not low and not out, "the page stops above the footer's rule at %d, the footer under it and inside the "
          "content box: %s %s" % (rule, low, out))
    # Compare's row over the entry, level with the toggles over the lists; the entry level with the lists
    a, st, d, lst = sz["cmp_add"], sz["cmp_status"], sz["detail"], sz["wpn_list"]
    check(d[1] == lst[1] and d[1] + d[3] == lst[1] + lst[3] and a[1] + a[3] <= d[1] and st[1] + st[3] <= d[1]
          and a[1] + a[3] / 2 == sz["by_faction_lbl"][1] + sz["by_faction_lbl"][3] / 2
          and a[0] >= sz["rule_wpn"][0] + 4 and a[0] + a[2] <= st[0] and st[0] + st[2] <= 792,
          "Compare and its line over the entry, level with the toggles; the entry level with the lists")
    # the Show and Sort boxes and the direction button over the model list, left to right, level
    # with "By faction", clear of the rules and of the list
    sb, so, sd = sz["show_box"], sz["sort_box"], sz["sort_dir"]
    mid = lambda r: r[1] + r[3] / 2
    check(sz["rule_cat"][0] + 4 <= sb[0] and sb[0] + sb[2] <= so[0] and so[0] + so[2] <= sd[0]
          and sd[0] + sd[2] <= sz["rule_wpn"][0] and all(r[1] + r[3] <= sz["wpn_list"][1] for r in (sb, so, sd))
          and all(abs(mid(r) - mid(sz["by_faction_lbl"])) <= 1 for r in (sb, so, sd)),
          "Show, Sort and the direction over the model list, side by side, level with By faction: %s %s %s"
          % (sb, so, sd))
    arrow = sz["sort_dir_arrow"]
    check(arrow[0] >= 0 and arrow[1] >= 0 and arrow[0] + arrow[2] <= sd[2] and arrow[1] + arrow[3] <= sd[3],
          "the arrow inside its button: %s in %s" % (arrow, sd))
    # the boxes' lists, the page's own (the engine's drop-down draws its open list a second time,
    # straight to the screen: in the 3D PDA apart from the page). Each opens right under its box,
    # as wide, its rows as high as the script counts them, at most four for Show and ten for Sort
    # (the options menu's own), its list box inside it; the catcher over the whole page; all three
    # made last, so they draw over the page and take its clicks first
    drop_h = int(re.search(r"local DROP_ROW_H = (\d+)", src).group(1))
    bad = []
    for box, most in (("show", 4), ("sort", 10)):
        b, f, lb = sz[box + "_box"], sz[box + "_list"], sz[box + "_list_box"]
        ih = int(re.search(r'<%s_list_box [^>]*item_height="(\d+)"' % box, XML).group(1))
        if not (f[0] == b[0] and f[1] == b[1] + b[3] and f[2] == b[2] and f[3] == most * drop_h and ih == drop_h
                and lb[0] >= 0 and lb[1] >= 0 and lb[0] + lb[2] <= f[2] and lb[3] == f[3]):
            bad.append((box, b, f, lb, ih))
    kids = paths(ui)
    check(not bad and sz["drop_catcher"] == [0, 0, 1024, 768]
          and kids[-5:] == ["drop_catcher", "drop_back", "show_list", "drop_back", "sort_list"]
          and "InitComboBox" not in src,
          "no engine drop-down: the lists under their boxes, as wide, %d-high rows, 4 and 10 at most; the catcher "
          "over the page; each list over a back of its own; all made last: %s %s" % (drop_h, bad, kids[-5:]))
    # the backs are solid, in the PDA screen's own color: the texture the layout names, as
    # textures_descr declares it, and the file build.py writes, every pixel opaque
    descr = io.open(os.path.join(GD, "configs", "ui", "textures_descr", "ui_arsenal.xml"), encoding="cp1251").read()
    tex = re.search(r"<drop_back [^>]*>\s*<texture>(\w+)</texture>", XML)
    tex = tex.group(1) if tex else None
    m_file = re.search(r'<file name="([^"]+)">\s*<texture id="%s"' % tex, descr) if tex else None
    dds = os.path.join(GD, "textures", m_file.group(1).replace("\\", os.sep) + ".dds") if m_file else None
    pixels = []
    if dds and os.path.exists(dds):
        raw = open(dds, "rb").read()[128:]
        pixels = sorted(set((raw[i + 2], raw[i + 1], raw[i], raw[i + 3]) for i in range(0, len(raw), 4)))
    check(tex == "arsenal_screen" and pixels == [(22, 26, 27, 255)] and 'stretch="1"' in XML.split("<drop_back", 1)[1].split(">", 1)[0],
          "the backs: stretched, solid, the PDA screen's color: %s %s %s" % (tex, dds, pixels))
    # left to right, nothing in the footer over the next: Silence, the lamp and its label, the credit
    row = [sz[k] for k in foot]
    over = [(foot[i], foot[i + 1]) for i in range(len(row) - 1) if row[i][0] + row[i][2] > row[i + 1][0]]
    check(not over, "the footer's parts side by side, none over the next: %s" % over)
    # Mark all read in the footer, between the lamp's label and the credit, level with Silence
    mr = sz["mark_read"]
    check(sz["jailbreak_lbl"][0] + sz["jailbreak_lbl"][2] <= mr[0] and mr[0] + mr[2] <= sz["credit"][0]
          and abs(mid(mr) - mid(sz["silence"])) <= 1 and mr[1] >= rule,
          "Mark all read in the footer, level with Silence, before the credit: %s" % mr)

    # without discovery there is nothing to mark read
    check(ui.mark_read.shown is False, "with discovery off, no Mark all read")

    # MCM's "Show where items are defined": the page ends with the files that wrote its lines, most
    # first, its section, model and icon, paths with forward slashes; off, none of it
    def pm_page():
        u = m.get_ui()
        u.cat_list.sel = 0
        u.cb.cat_list()
        names = [r.name.text for r in u.wpn_list["items"].values()]
        u.wpn_list.sel = names.index("PM") if "PM" in names else 0
        u.cb.wpn_list()
        return u, texts_of(shown(u))
    _, t = pm_page()
    check("Defined in" not in t, "the option off: no Defined in")
    g.SOURCES = True
    ui, t = pm_page()
    want = ["Section: wpn_pm", "w_pm.ltx: 40 lines", "mod_system_x_pm.ltx: 1 line",
            "Model: dynamics/weapons/wpn_pm/wpn_pm", "Icon: ui/ui_icon_equipment"]
    check(ui.sec == "wpn_pm" and after_in(t, "Defined in", 5) == want,
          "on: where the game read it from: %s" % after_in(t, "Defined in", 5))
    lua.execute("ini_sys.dltx_get_section = nil")
    _, t = pm_page()
    check(after_in(t, "Defined in", 2) == ["Section: wpn_pm", "Which files wrote its lines takes Modded Exes (their DLTX)."],
          "without Modded Exes' DLTX: says so, and still the section: %s" % after_in(t, "Defined in", 2))
    g.SOURCES = False

    # show_next (arsenal_api.open): the next open shows that model, in its category, once
    m.show_next("wpn_ak74")
    ui = m.get_ui()
    check(ui.sec == "wpn_ak74" and ui.cat == "rifles", "show_next: the next open shows that model: %s %s" % (ui.cat, ui.sec))
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    ui = m.get_ui()
    check(ui.cat == "pistols", "and only once: the open after it keeps the page as left: %s" % ui.cat)

    # Mark all read: shown while anything is new; a click reads it all, glows and count with it
    g.arsenal_intel = intel
    lua.execute("NEW.wpn_pm = true; NEW.wpn_fort = true; arsenal_intel.mark_all_read = function() "
                "for k in pairs(NEW) do NEW[k] = nil end end")
    ui = m.get_ui()
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    glowing = lambda: [r.key for r in list(ui.cat_list["items"].values()) + list(ui.wpn_list["items"].values())
                       if r.glow is not None]
    check(ui.mark_read.shown is True and glowing() and "new" in ui.found_count.text,
          "two new guns: Mark all read shows, rows glow: %s %s" % (glowing(), ui.found_count.text))
    mark = ui.cb.mark_read if ui.cb else None
    check(mark is not None, "a click on Mark all read is heard")
    if mark is not None:
        mark()
    check(lua.eval("next(NEW)") is None and not glowing() and ui.mark_read.shown is False
          and "new" not in ui.found_count.text,
          "after it: nothing new, nothing glows, the count line plain, the button gone: %s %s %s"
          % (glowing(), ui.mark_read.shown, ui.found_count.text))
    check(ui.sec is not None and len(texts_of(shown(ui))) > 0, "and the page shown stays shown: %s" % ui.sec)

    # ---- 1.8: icons in the model rows, the Show and Sort boxes, groups that fold, the page
    # opened where it was left ----
    def model_names(u):
        return [r.name.text for r in u.wpn_list["items"].values()]

    def pick(u, box, key):
        """pick `key` in a drop-down (Sort: its option's key), as the player does: the box, then
        the option in its list"""
        opts = [o if isinstance(o, str) else o.key for o in getattr(u, box + "_opts").values()]
        if key not in opts:
            return False
        u.cb[box + "_box"]()
        u.drops[box].list.sel = opts.index(key)
        u.clk[box + "_list_box"]()
        return True

    def attempt(fn, what):
        try:
            return fn()
        except L.LuaError as err:
            check(False, "%s: %s" % (what, str(err).split("\n")[0][:120]))
            return None

    lua.execute("arsenal_intel = nil")
    ui = m.get_ui()
    show_only(ui, "all")
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    g.icons = lua.table_from([])
    ui.FillWeapons(ui)
    rows = list(ui.wpn_list["items"].values())
    tints = [(r.name.text, r.icon.tcolor if r.icon else None) for r in rows]
    check(list(g.icons.values())[:3] == ["wpn_pm", "wpn_fort17", "wpn_ghost"]
          and tints == [("PM", "255,150,150,150"), ("Fort-17", "255,255,255,255"), ("Ghost", "255,90,90,90")],
          "each row has its icon, the found variant's; grayed while not found, darker for what never turns up: %s %s"
          % (list(g.icons.values())[:3], tints))
    ic = rows[0].icon
    check(ic is not None and ic.w <= sz["wpn_row_icon"][2] and ic.h <= sz["wpn_row_icon"][3]
          and abs(ic.x - (sz["wpn_row_icon"][0] + (sz["wpn_row_icon"][2] - ic.w) / 2)) < 0.01,
          "an icon fitted in its box, centered: %s" % (ic and (ic.x, ic.y, ic.w, ic.h),))
    item_h = int(re.search(r'<wpn_list [^>]*item_height="(\d+)"', XML).group(1))
    row_h = int(re.search(r"local MODEL_ROW_H = (\d+)", src).group(1))
    inside = [k for k in ("wpn_row_icon", "wpn_row_name", "wpn_glow") if sz[k][1] + sz[k][3] > item_h]
    check(item_h == row_h and not inside, "the model rows %d high in the layout and the script (%d), all of a "
          "row inside it: %s" % (item_h, row_h, inside or "yes"))

    # the Show box: everything, the found, the not found; and while discovery is on, what is new.
    # Its list holds them, the one chosen marked there and named on the box, the list as tall as
    # they are
    tx = lambda k: g.TEXT[k]
    shw, srt = ui.drops.show, ui.drops.sort
    state = lambda: (shw.frame.shown, srt.frame.shown, ui.drop_catcher.shown)
    lines = lambda d: [it.text for it in d.list["items"].values()]
    check(list(ui.show_opts.values()) == ["all", "found", "missing"]
          and lines(shw) == [tx("st_arsenal_show_" + s) for s in ("all", "found", "missing")]
          and shw.list.sel == 0 and ui.show_box.text == "All" and shw.frame.h == 3 * drop_h,
          "Show offers all, found, not found (nothing is new without discovery), all marked and named, three "
          "rows high: %s %s %s %s" % (lines(shw), shw.list.sel, ui.show_box.text, shw.frame.h))
    show_only(ui, "missing")
    check(model_names(ui) == ["PM", "Ghost"] and ui.show_box.text == tx("st_arsenal_show_missing")
          and shw.list.sel == 2 and state() == (False, False, False),
          "not found; the list closed, the box naming it: %s %s %s" % (model_names(ui), ui.show_box.text, state()))
    show_only(ui, "found")
    check(model_names(ui) == ["Fort-17"], "found: %s" % model_names(ui))
    show_only(ui, "all")

    # closed until a box is clicked; then its list is open over the catcher, the other's closed; a
    # click on the catcher (anywhere else on the page) or Escape closes it, another key not; and
    # every open of the page starts with them closed
    closed = state()
    ui.cb.show_box()
    opened = state()
    ui.cb.sort_box()
    other = state()
    ui.cb.drop_catcher()
    caught = state()
    ui.cb.show_box()
    ui.OnKeyboard(ui, g.DIK_keys.DIK_A, g.ui_events.WINDOW_KEY_PRESSED)
    kept = state()
    esc = ui.OnKeyboard(ui, g.DIK_keys.DIK_ESCAPE, g.ui_events.WINDOW_KEY_PRESSED)
    escaped = state()
    check(closed == (False, False, False) and opened == (True, False, True) and other == (False, True, True)
          and caught == (False, False, False) and kept == (True, False, True) and esc is True
          and escaped == (False, False, False),
          "a box opens its list over the catcher, closing the other; the catcher or Escape closes it, another "
          "key not: %s %s %s %s %s %s %s" % (closed, opened, other, caught, kept, esc, escaped))
    # each list's back: where its frame is, as large, shown with it and only with it
    rect = lambda w: (w.x, w.y, w.w, w.h)
    backed = lambda: all(d.back.shown == d.frame.shown and rect(d.back) == rect(d.frame) for d in (shw, srt))
    ui.cb.sort_box()
    sort_open = backed() and srt.back.shown is True
    ui.cb.show_box()
    show_open = backed() and shw.back.shown is True and srt.back.shown is False
    ui.cb.drop_catcher()
    check(sort_open and show_open and backed() and shw.back.shown is False,
          "each list's back where its frame is, as large, shown with it: %s %s" % (rect(shw.back), rect(shw.frame)))
    ui.cb.sort_box()
    ui = m.get_ui()
    check(state() == (False, False, False), "a list left open is closed at the next open: %s" % (state(),))

    # the Sort box: name, finds, the card's rows, weight; picked, kept for every row that offers it
    keys = [o.key for o in ui.sort_opts.values()]
    labels = [o.label for o in ui.sort_opts.values()]
    check(keys == ["name", "found", "accuracy", "fire_rate", "weight"] and labels[3] == "Fire Rate"
          and lines(srt) == labels and srt.list.sel == 0 and ui.sort_box.text == "Name" and srt.frame.h == 5 * drop_h,
          "a gun category sorts by name, finds, its card's rows by their own names, weight; all five in its "
          "list: %s %s %s" % (keys, lines(srt), srt.frame.h))
    # the option already chosen, picked again, changes nothing: the model list stays as scrolled
    ui.wpn_list.scroll = 40
    show_only(ui, "all")
    pick(ui, "sort", "name")
    check(ui.wpn_list.scroll == 40 and state() == (False, False, False),
          "the chosen option picked again: the list closes, the model list as it was: %s %s"
          % (ui.wpn_list.scroll, state()))
    # more options than its rows: the list as tall as its rows, and it scrolls
    ui.FillDrop(ui, "sort", lua.table_from(["x%d" % i for i in range(14)]), 1)
    check(srt.frame.h == 10 * drop_h and len(lines(srt)) == 14 and rect(srt.back) == rect(srt.frame),
          "fourteen orders: ten rows shown, the list scrolls to the rest, its back as tall: %s %s %s"
          % (srt.frame.h, len(lines(srt)), rect(srt.back)))
    ui.FillWeapons(ui)
    check(model_names(ui) == ["PM", "Fort-17", "Ghost"] and ui.sort_arrow.tex == "ui_scroll_btn_up",
          "by name, the catalog's own order, the arrow up: %s %s" % (model_names(ui), ui.sort_arrow.tex))
    pick(ui, "sort", "fire_rate")
    check(model_names(ui) == ["Ghost", "PM", "Fort-17"] and ui.sort_arrow.tex == "ui_scroll_btn_down",
          "by fire rate, most first, a tie by name; the arrow down: %s" % model_names(ui))
    ui.cb.sort_dir()
    check(model_names(ui) == ["Fort-17", "Ghost", "PM"] and ui.sort_arrow.tex == "ui_scroll_btn_up",
          "the button turns it round, and its arrow: %s %s" % (model_names(ui), ui.sort_arrow.tex))
    ui.cb.sort_dir()
    pick(ui, "sort", "name")
    ui.cb.sort_dir()
    check(model_names(ui) == ["Ghost", "Fort-17", "PM"], "by name turned round: %s" % model_names(ui))
    ui.cb.sort_dir()
    pick(ui, "sort", "found")
    check(model_names(ui) == ["Fort-17", "Ghost", "PM"], "newest finds first, the rest after by name: %s"
          % model_names(ui))
    check([e.name for e in m.arsenal_data.list("pistols").values()] == ["PM", "Fort-17", "Ghost"],
          "sorting leaves arsenal_data's own list as it was")
    pick(ui, "sort", "fire_rate")
    keys_cat = [r.key for r in ui.cat_list["items"].values()]
    ui.cat_list.sel = keys_cat.index("ammo")
    ui.cb.cat_list()
    ammo_keys = [o.key for o in ui.sort_opts.values()]
    check(ammo_keys == ["name", "found", "damage", "ap"] and ui.sort_box.text == "Name",
          "rounds sort by name, finds, damage, AP; a row without fire rate shows its own first: %s %s"
          % (ammo_keys, ui.sort_box.text))
    ui.cat_list.sel = keys_cat.index("pistols")
    ui.cb.cat_list()
    check(ui.sort_key == "fire_rate" and model_names(ui) == ["Ghost", "PM", "Fort-17"],
          "back on pistols, fire rate again: %s" % ui.sort_key)
    ui.by_faction_check.checked = True
    ui.cb.by_faction()
    fkeys = [r.key for r in ui.cat_list["items"].values()]
    ui.cat_list.sel = fkeys.index("f:stalker")
    ui.cb.cat_list()
    fk = [o.key for o in ui.sort_opts.values()]
    kind_order = model_names(ui)
    pick(ui, "sort", "name")
    check(fk == ["kind", "name", "found", "weight"] and kind_order == ["Fort-17", "AK-74 Tactical Modernized Carbine "
          "of the Northern Expedition Special Forces Unit", "SEVA"]
          and model_names(ui)[0].startswith("AK-74") and model_names(ui)[-1] == "SEVA",
          "a faction's gear: by kind first, its own order; by name sorts it: %s %s" % (fk, model_names(ui)))
    pick(ui, "sort", "kind")
    ui.by_faction_check.checked = False
    ui.cb.by_faction()
    pick(ui, "sort", "name")

    # what the player has not learned is not his to sort by: with discovery on, a model not yet
    # studied goes last whichever way the list runs
    g.arsenal_intel = intel
    lua.execute("STUDIED = { wpn_fort = true }")
    ui = m.get_ui()
    ui.cat_list.sel = 0
    ui.cb.cat_list()
    check(list(ui.show_opts.values()) == ["all", "found", "missing", "new"], "with discovery, Show offers new too")
    pick(ui, "sort", "fire_rate")
    a = model_names(ui)
    attempt(lambda: ui.cb.sort_dir(), "turned round with an unstudied model")
    b = model_names(ui)
    attempt(lambda: ui.cb.sort_dir(), "and back")
    check(a == ["Fort-17", "PM"] and b == ["Fort-17", "PM"],
          "the unstudied PM last both ways, its fire rate unknown to the player: %s %s" % (a, b))
    pick(ui, "sort", "name")
    lua.execute("NEW = { wpn_pm = true }")
    ui.FillWeapons(ui)
    show_only(ui, "new")
    check(model_names(ui) == ["PM"], "new: only what is new: %s" % model_names(ui))
    show_only(ui, "all")

    # groups: a heading over each group of more than one category, with found/total over them;
    # the rest as they are; a click on a heading folds it and keeps the category shown
    lua.execute('arsenal_data.GROUPS = { { id = "ammo", cats = { "ammo" } }, '
                '{ id = "weapons", cats = { "pistols", "smgs", "rifles", "melee" } }, { id = "armor", cats = { "medium" } } }')
    lua.execute("arsenal_intel = nil")
    ui = m.get_ui()

    def cat_rows(u):
        return [(r.name.text, r.count.text if r.count else None, bool(r.heading)) for r in u.cat_list["items"].values()]
    check(cat_rows(ui) == [("Ammo", "0/1", False), ("- Weapons", "1/4", True), ("Pistols", "1/2", False),
                           ("Rifles", "0/1", False), ("Melee", "0/1", False), ("Medium armor", "0/1", False)],
          "Weapons under a heading counting all of them; a group of one has none: %s" % cat_rows(ui))
    head = ui.cat_list["items"][2]
    pist = ui.cat_list["items"][3]
    check(head.name.color == "heading" and pist.name.x > sz["row_name"][0],
          "the heading in the headings' color, its categories indented: %s %s" % (head.name.color, pist.name.x))
    ui.cat_list.sel = 2
    ui.cb.cat_list()
    ui.cat_list.sel = 3
    ui.cb.cat_list()
    before = (ui.cat, model_names(ui))
    ui.cat_list.sel = 1
    ui.cb.cat_list()
    check((ui.cat, model_names(ui)) == before, "choosing a heading leaves the category shown: %s" % ui.cat)
    ui.clk.cat_list()
    check([r[0] for r in cat_rows(ui)] == ["Ammo", "+ Weapons", "Medium armor"] and ui.cat == "rifles"
          and ui.cat_list.sel == 1 and model_names(ui) == before[1],
          "a click folds it; the rifles stay shown, the heading chosen: %s %s %s" % (cat_rows(ui), ui.cat, ui.cat_list.sel))
    ui = m.get_ui()
    check([r[0] for r in cat_rows(ui)][1] == "+ Weapons" and ui.cat == "rifles" and ui.cat_list.sel == 1,
          "folded still at the next open, on the same category, its heading chosen: %s %s" % (ui.cat, ui.cat_list.sel))
    ui.cat_list.sel = 1
    ui.clk.cat_list()
    check(len(cat_rows(ui)) == 6 and ui.cat_list.sel == 3, "a click again opens it, the rifles chosen: %s"
          % ui.cat_list.sel)
    # a folded group glows while something under it is new; read, it keeps its color, and the
    # model's icon its tint as read
    g.arsenal_intel = intel
    lua.execute("NEW = { wpn_pm = true }; STUDIED = { wpn_fort = true }")
    ui = m.get_ui()
    ui.cat_list.sel = 2
    ui.cb.cat_list()
    ui.cat_list.sel = 1
    ui.clk.cat_list()
    head = ui.cat_list["items"][2]
    check(head.glow is not None and head.name.color == "heading", "folded with something new: the heading glows")
    pm_row = list(ui.wpn_list["items"].values())[model_names(ui).index("PM")]
    tint_new = pm_row.icon.tcolor if pm_row.icon else None
    ui.wpn_list.sel = model_names(ui).index("PM")
    ui.clk.wpn_list()
    check(head.glow is None and head.name.color == "heading",
          "read: its glow gone, the heading's color kept: %s" % head.name.color)
    check(tint_new == "255,255,255,255" and pm_row.icon.tcolor == "255,150,150,150",
          "the new model's icon full, read and not found grayed: %s %s" % (tint_new, pm_row.icon.tcolor))
    ui.cat_list.sel = 1
    ui.clk.cat_list()
    lua.execute("arsenal_data.GROUPS = nil")
    lua.execute("arsenal_intel = nil")

    # the page opens where it was left, in either window: the same model, each list and the entry
    # scrolled as they were, once the lists have measured their rows (the next update)
    ui = m.get_ui()
    ui.Update(ui)
    keys_cat = [r.key for r in ui.cat_list["items"].values()]
    ui.cat_list.sel = keys_cat.index("rifles")
    ui.cb.cat_list()
    ui.wpn_list.sel = 0
    ui.cb.wpn_list()
    ui.cat_list.scroll, ui.wpn_list.scroll, ui.detail.scroll = 5, 60, 120
    ui.Update(ui)
    ui = m.get_ui()
    pending = (ui.wpn_list.scroll, ui.detail.scroll)
    ui.Update(ui)
    check(ui.sec == "wpn_ak74" and pending == (0, 0) and (ui.cat_list.scroll, ui.wpn_list.scroll, ui.detail.scroll)
          == (5, 60, 120),
          "reopened on the same model, scrolled as left at the next update: %s %s %s"
          % (ui.sec, pending, (ui.cat_list.scroll, ui.wpn_list.scroll, ui.detail.scroll)))
    g.MAX_SCROLL = 40
    ui = m.get_ui()
    ui.Update(ui)
    check(ui.wpn_list.scroll == 40, "no further than the list reaches: %s" % ui.wpn_list.scroll)
    g.MAX_SCROLL = 1000
    flat = m.open_flat()
    if flat is not None:
        flat.Update(flat)
        check(flat.cat == "rifles" and flat.sec == "wpn_ak74" and flat.wpn_list.scroll == 40,
              "the flat window opens where the page was left: %s %s %s" % (flat.cat, flat.sec, flat.wpn_list.scroll))
        flat.Close(flat)
    # another app's model (show_next) opens with its row in view, not the old scroll
    lua.execute("""
EXTRA = {}
for i = 1, 8 do
    local sec = "wpn_x" .. i
    local e = { name = "X" .. i, sec = sec, cat = "pistols", variants = { { sec = sec, name = "X" .. i } } }
    e.variants[1].entry = e
    EXTRA[#EXTRA + 1] = e
end
BASE_LIST, BASE_GET = arsenal_data.list, arsenal_data.get
arsenal_data.list = function(c)
    if c ~= "pistols" then return BASE_LIST(c) end
    local out = {}
    for _, e in ipairs(BASE_LIST(c)) do out[#out + 1] = e end
    for _, e in ipairs(EXTRA) do out[#out + 1] = e end
    return out
end
arsenal_data.get = function(s)
    for _, e in ipairs(EXTRA) do if e.sec == s then return e end end
    return BASE_GET(s)
end
""")
    m.show_next("wpn_x6")
    ui = m.get_ui()
    ui.Update(ui)
    i = model_names(ui).index("X6") if "X6" in model_names(ui) else -1
    check(ui.sec == "wpn_x6" and i == 8 and ui.wpn_list.scroll == (i - 3) * row_h,
          "show_next: its row scrolled into view, a few rows below the top: %s %s %s" % (ui.sec, i, ui.wpn_list.scroll))
    lua.execute("arsenal_data.list, arsenal_data.get = BASE_LIST, BASE_GET")

    # what goes on a gun, while immersive: a category of its own; its page says what it fits (the
    # guns the player knows of, a line per category, with a kit's gun and a mount an upgrade
    # adds), how many more that turn up he has yet to meet, a launcher's grenades, and the
    # fighters he has seen with it on their guns
    lua.execute("""
KOBRA = { name = "Kobra", sec = "kobra", cat = "scopes", variants = { { sec = "kobra", name = "Kobra" } } }
KOBRA.variants[1].entry = KOBRA
arsenal_data.ATTACHMENTS = { scopes = true }
table.insert(arsenal_data.CATEGORIES, "scopes")
BASE_LIST, BASE_GET = arsenal_data.list, arsenal_data.get
arsenal_data.list = function(c) if c == "scopes" then return { KOBRA } end return BASE_LIST(c) end
arsenal_data.get = function(s) if s == "kobra" then return KOBRA end return BASE_GET(s) end
arsenal_data.fits = function(sec)
    if sec ~= "kobra" then return {} end
    local g = BASE_GET
    return { { e = g("wpn_pm"), how = "scopes" }, { e = g("wpn_pm"), how = "launchers", ammo = { "VOG-25" } },
             { e = g("wpn_fort"), how = "kits", makes = "Fort-17 Tactical" },
             { e = g("wpn_fort"), how = "launchers", upgrade = true, ammo = { "VOG-25" } },
             { e = g("wpn_ak74"), how = "launchers", ammo = { "M406" } }, { e = g("wpn_ghost"), how = "scopes" },
             { e = g("wpn_knife"), how = "scopes" } }
end
arsenal_data.mounted_on = function(sec)
    if sec ~= "kobra" then return {} end
    return { { faction = "dolg", ranks = { "veteran", "expert" } }, { faction = "army", ranks = { "novice" } } }
end
-- an attachment has no stat card (test_data checks the real one)
BASE_CARD = arsenal_data.has_stat_card
arsenal_data.has_stat_card = function(s) return s ~= "kobra" and BASE_CARD(s) end
KNOWN = { kobra = true, wpn_pm = true, wpn_fort = true }
STUDIED = { kobra = true }
NEW = {}
FACTS = { kobra = { carried = { dolg = { expert = true } } } }
""")
    g.arsenal_intel = intel
    ui = m.get_ui()
    keys = [r.key for r in ui.cat_list["items"].values()]
    rows = {r.key: r.name.text for r in ui.cat_list["items"].values()}
    ui.cat_list.sel = keys.index("scopes") if "scopes" in keys else 0
    ui.cb.cat_list()
    t = texts_of(shown(ui))
    check(rows.get("scopes") == "Scopes" and ui.sec == "kobra",
          "an attachment's category in the list: %s %s" % (rows.get("scopes"), ui.sec))
    check(after_in(t, "Fits:", 3) == ["Pistols: PM, Fort-17 (makes the Fort-17 Tactical), Fort-17 (after an upgrade)",
                                      "and 2 more you have yet to come across", "Fires: VOG-25"],
          "what it fits: the known guns by category, a kit's gun, an upgrade's mount; the unmet that turn up "
          "counted; the grenades of the known guns only: %s" % after_in(t, "Fits:", 3))
    check(after_in(t, "On fighters' guns:", 3)[:2] == ["Duty", "Expert"] and "Army" not in t,
          "the fighters seen with it on their guns, as far as learned: %s" % after_in(t, "On fighters' guns:", 3))
    check(ui.cmp_add.shown is False, "no Compare for it")
    lua.execute("STUDIED = {}")
    ui = m.get_ui()
    t = texts_of(shown(ui))
    check("Not studied yet: find one to see what it fits" in t and "Fits:" not in t,
          "not studied: found first-hand only, and what it fits stays hidden: %s" % [x for x in t if "studied" in x])
    lua.execute("STUDIED = { kobra = true }; KNOWN.wpn_ak74 = true")
    ui = m.get_ui()
    t = texts_of(shown(ui))
    check(after_in(t, "Fits:", 4) == ["Pistols: PM, Fort-17 (makes the Fort-17 Tactical), Fort-17 (after an upgrade)",
                                      "Rifles: AK-74 Tactical Modernized Carbine of the Northern Expedition Special "
                                      "Forces Unit", "and 1 more you have yet to come across", "Fires: VOG-25, M406"],
          "a gun he comes to know joins the list, its grenades too: %s" % after_in(t, "Fits:", 4))
    g.arsenal_intel = None
    lua.execute("""
arsenal_data.list, arsenal_data.get, arsenal_data.has_stat_card = BASE_LIST, BASE_GET, BASE_CARD
table.remove(arsenal_data.CATEGORIES)
arsenal_data.ATTACHMENTS, arsenal_data.fits, arsenal_data.mounted_on = nil, nil, nil
""")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
