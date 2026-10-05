"""Run arsenal_workbench.script under LuaJIT against stubs of the engine, GAMMA's toolkit and
Arsenal's data, and check: the tree and the engine's links, the toolkit's rules on a plan and
the engine's cross-row rule, what waits for a second visit, the kits, the items carried, the
card with a plan, the mounts, the saved plans, and the handoff to the toolkit window.

    python test_workbench.py            the real script
    python test_workbench.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_workbench.script"), encoding="latin-1").read()

# An item's upgrades as configs: row 1 a pair (a opens c/d; b opens nothing), c and d (both open
# e/f), e and f a pair; row 2 a chain of lone upgrades; row 3 one upgrade; rows 4 and 5 as the
# Kiparis has them: the fourth row's c/d group is opened by its a and by the fifth row's c/d.
SECTIONS = {
    "wpn_test": dict(upgrades="up_gr_firstab_t, up_gr_secona_t, up_gr_thirda_t, up_gr_fourta_t, up_gr_fiftha_t",
                     installed_upgrades="up_firsta_t, up_secona_t", inv_name="st_test", parent_section="wpn_test"),
    "up_gr_firstab_t": dict(elements="up_firsta_t, up_firstb_t"),
    "up_firsta_t": dict(section="s_firsta", property="prop_recoil", effects="up_gr_firstcd_t"),
    "up_firstb_t": dict(section="s_firstb", property="prop_weight"),
    "up_gr_firstcd_t": dict(elements="up_firstc_t, up_firstd_t"),
    "up_firstc_t": dict(section="s_firstc", property="prop_dispersion", effects="up_gr_firstef_t"),
    "up_firstd_t": dict(section="s_firstd", property="prop_rpm", effects="up_gr_firstef_t"),
    "up_gr_firstef_t": dict(elements="up_firste_t, up_firstf_t"),
    "up_firste_t": dict(section="s_firste", property="prop_bullet_speed"),
    "up_firstf_t": dict(section="s_firstf", property="prop_silencer"),
    "up_gr_secona_t": dict(elements="up_secona_t"),
    "up_secona_t": dict(section="s_secona", property="prop_reliability", effects="up_gr_seconc_t"),
    "up_gr_seconc_t": dict(elements="up_seconc_t"),
    "up_seconc_t": dict(section="s_seconc", property="prop_inertion", effects="up_gr_secone_t"),
    "up_gr_secone_t": dict(elements="up_secone_t"),
    "up_secone_t": dict(section="s_secone", property="prop_rpm"),
    "up_gr_thirda_t": dict(elements="up_thirda_t"),
    "up_thirda_t": dict(section="s_thirda", property="prop_scope"),
    "up_gr_fourta_t": dict(elements="up_fourta_t"),
    "up_fourta_t": dict(section="s_fourta", property="prop_ammo_size", effects="up_gr_fourtcd_t"),
    "up_gr_fourtcd_t": dict(elements="up_fourtc_t, up_fourtd_t"),
    "up_fourtc_t": dict(section="s_fourtc", property="prop_recoil", effects="up_gr_fourte_t"),
    "up_fourtd_t": dict(section="s_fourtd", property="prop_recoil", effects="up_gr_fourte_t"),
    "up_gr_fourte_t": dict(elements="up_fourte_t"),
    "up_fourte_t": dict(section="s_fourte", property="prop_bullet_speed"),
    "up_gr_fiftha_t": dict(elements="up_fiftha_t"),
    "up_fiftha_t": dict(section="s_fiftha", property="prop_underbarrel_slot", effects="up_gr_fifthcd_t"),
    "up_gr_fifthcd_t": dict(elements="up_fifthc_t, up_fifthd_t"),
    "up_fifthc_t": dict(section="s_fifthc", property="prop_calibre", effects="up_gr_fourtcd_t"),
    "up_fifthd_t": dict(section="s_fifthd", property="prop_rpm", effects="up_gr_fourtcd_t"),
    # change sections: a suppressor mount on f, a launcher mount on the fifth row's a
    "s_firsta": {}, "s_firstb": {}, "s_firstc": {}, "s_firstd": {}, "s_firste": {},
    "s_firstf": dict(silencer_status="2", silencer_name="sil_up"),
    "s_secona": {}, "s_seconc": {}, "s_secone": {}, "s_thirda": {}, "s_fourta": {}, "s_fourtc": {}, "s_fourtd": {},
    "s_fourte": {},
    "s_fiftha": dict(grenade_launcher_status="2", grenade_launcher_name="gl_up"),
    "s_fifthc": {}, "s_fifthd": {},
    "sil_up": dict(inv_weight="0.4"), "gl_up": dict(inv_weight="1.3"), "sil_own": dict(inv_weight="0.3"),
    "scope_a": dict(inv_weight="0.25"), "scope_b": dict(inv_weight="0.5"),
    # a gun with its own suppressor mount, its scoped combination, a suit, a helmet, a knife
    "wpn_own": dict(upgrades="up_gr_thirda_t", silencer_status="2", silencer_name="sil_own", inv_name="st_own"),
    "wpn_own_scope_a": dict(parent_section="wpn_own", upgrades="up_gr_thirda_t", inv_name="st_own"),
    "suit_x": dict(upgrades="up_gr_thirda_t", inv_name="st_suit"),
    "helm_x": dict(upgrades="up_gr_thirda_t", inv_name="st_helm"),
    "wpn_knife": dict(upgrades="up_gr_thirda_t", inv_name="st_knife"),
    "wpn_plain": dict(inv_name="st_plain"),
    "wpn_broken": dict(upgrades="up_gr_x"),
    "itm_basickit": {}, "itm_advancedkit": {}, "itm_expertkit": {},
}

STUBS = r"""
SEC = ...
logs = {}
function printf(fmt, ...) logs[#logs + 1] = string.format(fmt, ...) end
callbacks = {}
function RegisterScriptCallback(name, fn) callbacks[name] = fn end
ini_sys = {
    r_string_ex = function(self, sec, key) return SEC[sec] and SEC[sec][key] end,
    r_float_ex = function(self, sec, key) return SEC[sec] and SEC[sec][key] and tonumber(SEC[sec][key]) end,
    section_exist = function(self, sec) return SEC[sec] ~= nil end,
}
game = { translate_string = function(k) return (k:gsub("^st_", "")) end }

-- GAMMA's tree builder (aaaa_streamlined_mp.script), as far as these configs need it: the row
-- from the name's row word, the column from its ninth letter, the first upgrade at a place
-- kept, effects as the set of the next group's upgrades, the kit from the first property and
-- the column's tier, lone odd columns marked solo
local ROW = { first = 1, secon = 2, third = 3, fourt = 4, fifth = 5 }
local COL = { a = 1, b = 2, c = 3, d = 4, e = 5, f = 6 }
local FAMILY = { prop_recoil = "internal", prop_rpm = "internal", prop_calibre = "internal", prop_reliability = "internal",
    prop_weight = "external", prop_dispersion = "external", prop_bullet_speed = "external", prop_inertion = "external",
    prop_ammo_size = "external", prop_silencer = "optical", prop_scope = "optical", prop_underbarrel_slot = "optical" }
local function list(sec, key)
    local out = {}
    for x in (SEC[sec] and SEC[sec][key] or ""):gmatch("[^,%s]+") do out[#out + 1] = x end
    return out
end
local function extract(tree, group)
    for _, el in ipairs(list(group, "elements")) do
        for word, row in pairs(ROW) do
            if el:find(word) then
                tree[row] = tree[row] or {}
                local col = COL[el:sub(9, 9)]
                if col and not tree[row][col] then
                    local eff = SEC[el].effects
                    local set
                    if eff then
                        set = {}
                        for _, x in ipairs(list(eff, "elements")) do set[x] = true end
                    end
                    local tier = col <= 2 and 1 or col <= 4 and 2 or 3
                    local fam = FAMILY[list(el, "property")[1]]
                    tree[row][col] = { section = el, stats = SEC[el].section, name = "name_" .. el, icon = "icon_" .. el,
                        effect = set, tool = fam and ("upgr_w_" .. tier .. "_" .. fam) or nil, prop = list(el, "property") }
                end
            end
        end
    end
    for _, el in ipairs(list(group, "elements")) do
        if SEC[el].effects then extract(tree, SEC[el].effects) end
    end
end
tree_calls = {}
utils_item = {
    get_upgrades_tree = function(sec, new_table)
        tree_calls[#tree_calls + 1] = { sec = sec, new_table = new_table }
        if sec == "wpn_broken" then error("bad tree") end
        local t = {}
        for _, g in ipairs(list(sec, "upgrades")) do extract(t, g) end
        for _, row in pairs(t) do
            for col, c in pairs(row) do
                if col % 2 == 1 and not row[col + 1] then c.solo = true end
            end
        end
        return t
    end,
    get_item_remaining_uses = function(obj) return obj.uses or 1 end,
}

-- items in the world: a section, an id, upgrades, a parent
function item(sec, id, ups, uses)
    local o = { sec = sec, idv = id, ups = ups or {}, uses = uses }
    function o:section() return self.sec end
    function o:id() return self.idv end
    function o:iterate_installed_upgrades(fn)
        if self.ups == "boom" then error("offline") end
        for _, u in ipairs(self.ups) do fn(u) end
    end
    function o:parent() return self.parent_obj end
    function o:cast_Weapon()
        if not self.disp then return nil end
        local w = { d = self.disp }
        function w.GetFireDispersion(me) return me.d end
        return w
    end
    return o
end
AC_ID = 0
ACTOR_OBJ = { idv = 0, id = function(self) return self.idv end }
CARRIED, STASHED, BY_ID = {}, {}, {}
db = { actor = { iterate_inventory = function(self, fn)
    for _, o in ipairs(CARRIED) do fn(self, o) end
end } }
RANGES = {}
function IterateStashesInRange(fn, range)
    RANGES[#RANGES + 1] = range
    for _, o in ipairs(STASHED) do fn("box", o) end
end
ui_mcm = { get = function(key) if key == "craft_from_stashes/range" then return 25 end end }
level = { object_by_id = function(id) return BY_ID[id] end }
WORLD = {}
function alife_object(id)
    local sec = WORLD[id]
    return sec and { section_name = function() return sec end } or nil
end
function IsWeapon(o) return o.sec:find("^wpn_") ~= nil end
function IsOutfit(o) return o.sec:find("^suit_") ~= nil end

-- Arsenal's data, as far as Workbench asks it: the listing, and values that record what they
-- were asked for
CATS = { wpn_test = "rifles", wpn_own = "rifles", wpn_own_scope_a = "rifles", suit_x = "light", helm_x = "helmets",
         wpn_knife = "melee", wpn_plain = "rifles" }
asked = {}
arsenal_data = {
    entry_for = function(sec) return CATS[sec] and { cat = CATS[sec] } or nil end,
    get = function(sec) return CATS[sec] and { cat = CATS[sec] } or nil end,
    is_helmet = function(sec) return sec:find("^helm_") ~= nil end,
    is_armor = function(sec) return CATS[sec] == "light" or CATS[sec] == "helmets" end,
    kg = function(x) return math.floor(x * 100 + 0.5) / 100 end,
    params_with = function(sec, ups)
        asked[#asked + 1] = { sec = sec, ups = table.concat(ups, ",") }
        return { sec = sec, n = #ups, inv_weight = 3 + 0.1 * #ups, rad = 0.005 }
    end,
    armor_params_with = function(sec, ups) return { sec = sec, n = #ups, inv_weight = 8 + 0.5 * #ups } end,
    armor_value = function(stat, p)
        if stat == "fire_wound_protection" then return 40 + p.n end
        if stat == "additional_inventory_weight" then return 5.5 end
        return nil
    end,
    CARD = {
        accuracy = function(p) return 70 + p.n end,
        recoil = function(p) return 50 - p.n end,
        fire_rate = function(p) return 600 end,
        damage = function(p) return 99 end,
    },
    stat_rows = function(live, sec)
        if CATS[sec] == "light" or CATS[sec] == "helmets" then
            return { { stat = "fire_wound_protection", gr = { name = "ui_inv_fire", unit = "st_perc", sign = true } },
                     { stat = "apres_modifier", gr = { name = "ui_inv_br", unit = "" } },
                     { stat = "additional_inventory_weight", gr = { name = "ui_inv_carry", unit = "st_kg", sign = true } } }
        end
        return { { stat = "accuracy", gr = { name = "ui_inv_accuracy", unit = "st_perc" } },
                 { stat = "damage", gr = { name = "ui_inv_damage", unit = "" } },
                 { stat = "fire_rate", gr = { name = "%c[0,255,255,255]ui_inv_rate_of_fire", unit = "st_rpm" } },
                 { stat = "recoil", gr = { name = "ui_inv_recoil", unit = "", sign_inverse = true } },
                 { stat = "max_range", gr = { name = "ui_inv_range", unit = "" } } }
    end,
    attachments = function(sec)
        if sec == "wpn_own" then return { scopes = { { sec = "scope_a" }, { sec = "scope_b" } } } end
        return { scopes = {} }
    end,
    params_count = 0,
}
utils_ui = { get_stats_string_value = function(obj, sec, gr, stat)
    if stat == "apres_modifier" then return "+58 " end
    return nil
end }

-- the toolkit window: its Upgrade tab on the item, cells that record checks
OPENED = {}
CONSOLE_3D = false
function get_console_cmd(t, name) if name == "g_3d_pda" then return CONSOLE_3D end end
PDA = { shown = true, section = "eptWorkbench" }
function PDA:IsShown() return self.shown end
function PDA:HideDialog() self.shown = false; self.hid = true end
db.actor.activate_slot = function(self, n) PDA.slot = n end
ActorMenu = { get_pda_menu = function() return PDA end }
NOW = 1000
function time_global() return NOW end
EVENTS = {}
function CreateTimeEvent(ev, act, t, f, ...) EVENTS[ev .. "/" .. act] = { f = f, p = { ... } } end
function RemoveTimeEvent(ev, act) EVENTS[ev .. "/" .. act] = nil end
function ResetTimeEvent(ev, act, t) RESETS = (RESETS or 0) + 1 end
function workshop(installed, enabled)
    local dlg = { inst_upgr = {}, upgr = utils_item.get_upgrades_tree("wpn_test"), upgr_xml = {}, checks = {}, evals = 0 }
    for _, u in ipairs(installed) do dlg.inst_upgr[u] = true end
    for r, row in pairs(dlg.upgr) do
        dlg.upgr_xml[r] = {}
        for c, info in pairs(row) do
            local btn = { on = false, en = enabled[info.section] ~= false }
            function btn:IsEnabled() return self.en end
            function btn:SetCheck(v) self.on = v; table.insert(dlg.checks, info.section) end
            dlg.upgr_xml[r][c] = { btn = btn }
        end
    end
    dlg.CC = { ID = "inventory", GetCell_ID = function(self, id, b) return WS_CELL ~= false and (id * 10) or nil end,
               On_Select = function(self, idx) dlg.selected = idx end }
    function dlg:On_CC_Mouse1(cc, idx) self.clicked = idx end
    function dlg:EvaluateUpgrades() self.evals = self.evals + 1 end
    local ui = { dlg_upgrade = dlg }
    function ui:OnButton_upgrade() self.tab = "upgrade" end
    return ui
end
ui_workshop = { get_workshop_ui = function(a, b, flags, dbg)
    if WS_OPEN then return nil end
    OPENED[#OPENED + 1] = { flags = flags, dbg = dbg }
    WS = workshop(WS_INSTALLED or {}, WS_ENABLED or {})
    return WS
end }
"""

MUTANTS = {
    "no_upgrades_guard": ('    if sec and utils_item and utils_item.get_upgrades_tree and (ini_sys:r_string_ex(sec, "upgrades") or "") ~= "" then',
                          "    if sec and utils_item and utils_item.get_upgrades_tree then"),
    "no_new_table": ("pcall(utils_item.get_upgrades_tree, sec, true)", "pcall(utils_item.get_upgrades_tree, sec)"),
    "no_pcall_tree": ("        local ok, got = pcall(utils_item.get_upgrades_tree, sec, true)",
                      "        local ok, got = true, utils_item.get_upgrades_tree(sec, true)"),
    "no_at": ("            if c then t.at[c.section] = { row = row, col = col } end\n", ""),
    "links_no_effects": ("                    t.parents[nxt][g] = true\n", ""),
    "links_no_follow": ("                    queue[#queue + 1] = nxt\n", ""),
    "col_major": ("    for row = 1, ROWS do\n        for col = 1, COLS do\n            local c = t[row] and t[row][col]\n            if c then\n                out",
                  "    for col = 1, COLS do\n        for row = 1, ROWS do\n            local c = t[row] and t[row][col]\n            if c then\n                out"),
    "partner_off_by_one": ("t[row][(col % 2 == 1) and col + 1 or col - 1]", "t[row][(col % 2 == 1) and col - 1 or col + 1]"),
    "parent_any_row": ("        local p = t[row][c]\n        if p and p.effect", "        local p = t[1][c]\n        if p and p.effect"),
    "open_from_col_2": ("    if col <= 2 then return true end", "    if col <= 1 then return true end"),
    "open_from_col_3": ("    if col <= 2 then return true end", "    if col <= 3 then return true end"),
    "no_engine_rule": ("    return opened(t, row, col, have) and not groups_missing(t, t[row][col].section, have)",
                       "    return opened(t, row, col, have)"),
    "groups_any_member": ("            if have[m] then ok = true end", "            ok = true"),
    "state_partner_installed_only": ('    if p and have[p.section] then return "partner" end',
                                     '    if p and installed[p.section] then return "partner" end'),
    "state_no_parent": ('    if not allowed(t, row, col, have) then return "parent" end\n', ""),
    "no_prune_loop": ("                plan[sec] = nil\n                changed = true\n", "                plan[sec] = nil\n"),
    "no_prune_on_leave": ("        plan[c.section] = nil\n        prune(t, installed, plan)\n        return plan",
                          "        plan[c.section] = nil\n        return plan"),
    "no_prune_on_swap": ("        plan[p.section] = nil\n        prune(t, installed, plan)\n    end\n    return true",
                         "        plan[p.section] = nil\n    end\n    return true"),
    "keep_partner": ("    if p and plan[p.section] then\n        plan[p.section] = nil", "    if false then\n        plan[p.section] = nil"),
    "swap_installed": ('    if p and installed[p.section] then return false, "partner" end\n', ""),
    "no_parent_pull": ("        for _, pc in ipairs(parents(t, row, col)) do\n            local trial",
                       "        for _, pc in ipairs({}) do\n            local trial"),
    "no_group_pull": ("        if not join_group(t, g, installed, plan, depth) then return false, \"parent\" end",
                      "        return false, \"parent\""),
    "group_last_member": ("        return x.row < y.row or (x.row == y.row and x.col < y.col)",
                          "        return x.row > y.row or (x.row == y.row and x.col > y.col)"),
    "toggle_mutates": ("    local plan = copy(planned)\n    if plan[c.section] then", "    local plan = planned\n    if plan[c.section] then"),
    "installed_toggles": ('    if installed[c.section] then return nil, "installed" end\n    local plan = copy(planned)',
                          "    local plan = copy(planned)"),
    "valid_keeps_installed": ("        if planned[sec] and not installed[sec] then", "        if planned[sec] then"),
    "valid_no_pairs": ("            plan[sec] = nil\n        end\n    end\n    prune(t, installed, plan)\n    return plan",
                       "        end\n    end\n    prune(t, installed, plan)\n    return plan"),
    "valid_no_prune": ("    prune(t, installed, plan)\n    return plan\nend\n\n-- the planned upgrades in",
                       "    return plan\nend\n\n-- the planned upgrades in"),
    "later_none": ("        if groups_missing(t, sec, done) then", "        if false then"),
    "later_from_all": ("            done[sec] = true\n        end\n    end\n    return out", "        end\n        done[sec] = true\n    end\n    return out"),
    "kits_once": ("            n[tool] = (n[tool] or 0) + 1", "            n[tool] = 1"),
    "kits_unsorted": ("    table.sort(out, function(a, b) return a.sec < b.sec end)\n    return out\nend\n\n-- Craft",
                      "    return out\nend\n\n-- Craft"),
    "held_no_uses": ("held[s] = (held[s] or 0) + (utils_item.get_item_remaining_uses(obj) or 1)", "held[s] = (held[s] or 0) + 1"),
    "held_no_stashes": ("    local range = stash_range()\n    if range then\n        local ok, err", "    local range = nil\n    if range then\n        local ok, err"),
    "held_fixed_range": ('    return ui_mcm and ui_mcm.get("craft_from_stashes/range") or 10', "    return 10"),
    "installed_unsafe": ("    local ok, err = pcall(function()\n        obj:iterate_installed_upgrades", "    local ok, err = true, (function()\n        obj:iterate_installed_upgrades"),
    "carried_melee": ('        if e and e.cat ~= "melee" and e.cat ~= "ammo" and has_tree(sec) then', "        if e and has_tree(sec) then"),
    "carried_no_tree": ('        if e and e.cat ~= "melee" and e.cat ~= "ammo" and has_tree(sec) then', '        if e and e.cat ~= "melee" and e.cat ~= "ammo" then'),
    "carried_unsorted": ("        if a.kind ~= b.kind then return KIND_ORDER[a.kind] < KIND_ORDER[b.kind] end\n", ""),
    "helmet_as_suit": ('    if arsenal_data.is_helmet(sec) then return "helmet" end\n', ""),
    "check_every_gun": ("    if checked[sec] then return end\n    checked[sec] = true", "    if false then return end"),
    "check_logs_all": ("    if live ~= p.rad then", "    if true then"),
    "scope_keeps_gun": ("    if not scope then return base end", "    if not scope then return sec end"),
    "scope_no_combo": ("    return ini_sys:section_exist(combo) and combo or base\nend", "    return base\nend"),
    "scope_weight_off": ("    return p.inv_weight + weight_of(scope) + weight_of(att.silencer)", "    return p.inv_weight + weight_of(att.silencer)"),
    "card_plan_now": ("        b = arsenal_data.params_with(planned, plan)", "        b = arsenal_data.params_with(planned, now)"),
    "card_damage": ('            if f and r.stat ~= "damage" then x, y = f(a), f(b) end', "            if f then x, y = f(a), f(b) end"),
    "better_flip": ("    return b > a\nend", "    return b < a\nend"),
    "no_inverse": ("    if gr.sign_inverse then return b < a end\n", ""),
    "no_sign": ('    if gr.sign and v > 0 then s = "+" .. s end\n', ""),
    "no_card_value": ("            row.plan_text = row.now_text\n", ""),
    "mount_own_flag": ("    from(sec, true)", "    from(sec, false)"),
    "mount_no_upgrades": ("        if ps and ini_sys:section_exist(ps) then from(ps, false) end", "        -- upgrades add none"),
    "fits_base": ("    local ok, a = pcall(arsenal_data.attachments, base)", "    local ok, a = pcall(arsenal_data.attachments, sec)"),
    "plan_ignores_sec": ("    if not p or (id and p.sec ~= sec) then return {}, {} end", "    if not p then return {}, {} end"),
    "plan_shared": ("    return copy(p.set), copy(p.att or {})", "    return p.set, p.att or {}"),
    "empty_plan_kept": ("    if next(set) == nil and next(att or {}) == nil then", "    if false then"),
    "att_only_dropped": ("    if next(set) == nil and next(att or {}) == nil then", "    if next(set) == nil then"),
    "forget_all": ("        if not (se and se:section_name() == p.sec) then plans.id[id] = nil end", "        plans.id[id] = nil"),
    "forget_none": ("        if not (se and se:section_name() == p.sec) then plans.id[id] = nil end", "        if not se then plans.id[id] = nil end"),
    "save_unsorted": ("            table.sort(list)\n            out[kind][k]", "            out[kind][k]"),
    "save_no_att": ("            out[kind][k] = { sec = p.sec, list = list, att = copy(p.att or {}) }",
                    "            out[kind][k] = { sec = p.sec, list = list }"),
    "load_keeps_old": ("local function load_state(m_data)\n    plans = { id = {}, sec = {} }\n", "local function load_state(m_data)\n"),
    "no_callbacks": ('    RegisterScriptCallback("save_state", save_state)\n', ""),
    "toolkit_worst": ("        if have[s] then return 4 - i end", "        if have[s] then return i end"),
    "toolkit_no_stash": ("    if range then pcall(IterateStashesInRange, count, range) end\n", ""),
    "install_anywhere": ("    if not (obj and obj:parent() and obj:parent():id() == AC_ID and obj:section() == sec) then",
                         "    if not obj then"),
    "install_empty": ('    if next(planned) == nil then return "nothing" end\n', ""),
    "install_no_toolkit": ('    if not toolkit() then return "no_toolkit" end\n', ""),
    "flags_off": ("    local flags = { level_of == 1, level_of == 2, level_of == 3, false, false }",
                  "    local flags = { true, true, true, true, true }"),
    "no_upgrade_tab": ("    ui:OnButton_upgrade()\n", ""),
    "no_select": ("    dlg.CC:On_Select(idx)\n", ""),
    "no_click": ("    dlg:On_CC_Mouse1(dlg.CC.ID, idx)\n", ""),
    "check_row_major": ("    for col = 1, COLS do\n        for row = 1, ROWS do\n            local info",
                        "    for row = 1, ROWS do\n        for col = 1, COLS do\n            local info"),
    "check_disabled": ("                if not skip[info.section] and st and st.btn:IsEnabled() then",
                       "                if not skip[info.section] and st then"),
    "check_later": ("                if not skip[info.section] and st and st.btn:IsEnabled() then",
                    "                if st and st.btn:IsEnabled() then"),
    "no_evaluate": ("                    dlg:EvaluateUpgrades()\n", ""),
    "check_installed": ("            if info and planned[info.section] and not dlg.inst_upgr[info.section] then",
                        "            if info and planned[info.section] then"),
    "pda_not_closed": ("        if get_console_cmd(1, \"g_3d_pda\") then\n            db.actor:activate_slot(0)\n        else\n            pda:HideDialog()\n        end",
                       "        if false then end"),
    "no_wait": ("    if p and p:IsShown() and time_global() - pending.t0 < 3000 then", "    if false then"),
    "wait_forever": ("    if p and p:IsShown() and time_global() - pending.t0 < 3000 then", "    if p and p:IsShown() then"),
    "tick_unsafe": ("    local ok, left, err = pcall(open_toolkit, job.id, job.sec, job.planned)",
                    "    local ok, left, err = true, open_toolkit(job.id, job.sec, job.planned)"),
}


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
    lua.execute(STUBS, lua.table_from({k: lua.table_from(v) for k, v in SECTIONS.items()}))
    g = lua.globals()
    try:
        env = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                       "setfenv(f, env); f(); return env end")(src)
        env.on_game_start()
    except L.LuaError as e:
        print("FAIL  the script loads: %s" % e)
        print("\n1 failed")
        return 1
    to_set = lua.eval("function(list) local t = {} for _, k in ipairs(list) do t[k] = true end return t end")
    to_list = lua.eval("function(list) local t = {} for i, k in ipairs(list) do t[i] = k end return t end")

    def S(*names):
        return to_set(lua.table_from(list(names)))

    def Lst(*names):
        return to_list(lua.table_from(list(names)))

    def keys(t):
        return sorted(k for k in t.keys()) if t is not None else None

    def call(fn, *args):
        try:
            r = fn(*args)
            return r if isinstance(r, tuple) else (r,)
        except L.LuaError as e:
            return ("error: %s" % e,)

    E = S()
    # the tree, as GAMMA builds it, a new table every time, with the engine's links
    t = env.tree("wpn_test")
    calls = g.tree_calls
    check(t[1][1].section == "up_firsta_t" and len(calls) == 1 and calls[1].new_table is True,
          "the tree is GAMMA's, asked for as a new table")
    check(t.at["up_fifthc_t"] is not None and t.at["up_fifthc_t"].row == 5 and t.at["up_fifthc_t"].col == 3,
          "each upgrade's cell")
    check(t.group_of["up_fourtc_t"] == "up_gr_fourtcd_t" and keys(t.parents["up_gr_fourtcd_t"]) == ["up_gr_fifthcd_t", "up_gr_fourta_t"],
          "the engine's links: a group opened from two rows has both as parents: %s"
          % (t.parents["up_gr_fourtcd_t"] and keys(t.parents["up_gr_fourtcd_t"])))
    n = len(g.tree_calls)
    t0 = env.tree("wpn_plain")
    check(len(env.cells(t0)) == 0 and len(g.tree_calls) == n, "no upgrades: no tree, GAMMA not asked")
    r = call(env.tree, "wpn_broken")
    check(not isinstance(r[0], str) and len(env.cells(r[0])) == 0 and len(g.logs) == 1 and "wpn_broken" in g.logs[1],
          "a tree that fails to build: none, logged: %s" % list(g.logs.values()))
    check(env.has_tree("wpn_test") is True and env.has_tree("wpn_plain") is False, "has_tree")

    order = [(x.row, x.col) for x in env.cells(t).values()]
    check(order == [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (2, 1), (2, 3), (2, 5), (3, 1), (4, 1), (4, 3), (4, 4),
                    (4, 5), (5, 1), (5, 3), (5, 4)], "cells in the toolkit's install order, row by row: %s" % order)

    def names(section):
        return section.replace("up_", "").replace("_t", "")

    def states(installed, planned):
        return {names(x.cell.section): env.state(t, x.row, x.col, installed, planned) for x in env.cells(t).values()}

    st = states(E, E)
    check(st == {"firsta": "open", "firstb": "open", "firstc": "parent", "firstd": "parent", "firste": "parent",
                 "firstf": "parent", "secona": "open", "seconc": "parent", "secone": "parent", "thirda": "open",
                 "fourta": "open", "fourtc": "parent", "fourtd": "parent", "fourte": "parent", "fiftha": "open", "fifthc": "parent",
                 "fifthd": "parent"}, "nothing in: the first columns open, the rest wait: %s" % st)
    st = states(S("up_firsta_t"), S("up_firstd_t"))
    check((st["firsta"], st["firstb"], st["firstc"], st["firstd"], st["firste"], st["firstf"])
          == ("installed", "partner", "partner", "planned", "open", "open"),
          "a installed, d planned: their partners shut, d opens e and f: %s" % st)
    st = states(E, S("up_firstb_t"))
    check(st["firsta"] == "partner" and st["firstc"] == "parent", "a planned partner shuts its pair; b opens nothing: %s" % st)
    st = states(S("up_fourta_t"), E)
    check(st["fourtc"] == "parent", "the toolkit's opener in, the engine's other parent group not: still shut: %s" % st["fourtc"])
    st = states(S("up_fourta_t", "up_fiftha_t", "up_fifthd_t"), E)
    check(st["fourtc"] == "open" and st["fourtd"] == "open", "both parent groups in: open: %s" % st["fourtc"])
    check(env.state(t, 2, 2, E, E) is None, "an empty cell has no state")

    def toggle(installed, planned, row, col):
        r = call(env.toggle, t, row, col, installed, planned)
        if isinstance(r[0], str):
            return r[0]
        return [names(k) for k in keys(r[0])] if r[0] is not None else ("nil", r[1] if len(r) > 1 else None)

    check(toggle(E, E, 1, 1) == ["firsta"], "an open upgrade joins")
    got = toggle(E, E, 1, 5)
    check(got == ["firsta", "firstc", "firste"], "a fifth-column upgrade brings the first opener that can join, and its own: %s" % (got,))
    got = toggle(E, S("up_firsta_t", "up_firstc_t", "up_firste_t"), 1, 6)
    check(got == ["firsta", "firstc", "firstf"], "f takes e's place; c, which opens both, stays: %s" % (got,))
    got = toggle(E, S("up_firsta_t", "up_firstc_t", "up_firstf_t"), 1, 1)
    check(got == [], "an opener leaves with all it alone opened: %s" % (got,))
    got = toggle(E, S("up_firsta_t", "up_firstc_t", "up_firste_t"), 1, 4)
    check(got == ["firsta", "firstd", "firste"], "d takes c's place; e, opened by both, stays: %s" % (got,))
    got = toggle(E, S("up_firsta_t", "up_firstc_t", "up_firste_t"), 1, 2)
    check(got == ["firstb"], "b takes a's place; what only a opened goes: %s" % (got,))
    check(toggle(S("up_firstb_t"), E, 1, 1) == ("nil", "partner"), "an installed partner keeps it out")
    check(toggle(S("up_firstb_t"), E, 1, 5) == ("nil", "parent"), "no opener can join: out: %s" % (toggle(S("up_firstb_t"), E, 1, 5),))
    check(toggle(S("up_firsta_t"), E, 1, 1) == ("nil", "installed"), "an installed upgrade does not toggle")
    check(toggle(E, E, 2, 5) == ["secona", "seconc", "secone"], "a lone chain comes along whole")
    got = toggle(E, S("up_secona_t", "up_seconc_t", "up_secone_t", "up_thirda_t"), 2, 1)
    check(got == ["thirda"], "leaving takes down the chain, other rows stay: %s" % (got,))
    got = toggle(E, E, 4, 3)
    check(got == ["fiftha", "fifthc", "fourta", "fourtc"],
          "an upgrade opened from two rows brings its row's opener and the other group's first upgrade, with its "
          "opener: %s" % (got,))
    got = toggle(S("up_fourta_t", "up_fiftha_t", "up_fifthd_t"), E, 4, 3)
    check(got == ["fourtc"], "with both parent groups in, it joins alone: %s" % (got,))
    got = toggle(E, S("up_fourta_t", "up_fourtc_t", "up_fiftha_t", "up_fifthc_t"), 5, 3)
    check(got == ["fiftha", "fourta"], "the other row's parent leaves: what needed it goes too: %s" % (got,))
    check(toggle(E, E, 4, 2) == ("nil", "none"), "no cell: nothing")
    before = S("up_firsta_t", "up_firstc_t")
    env.toggle(t, 1, 4, E, before)
    env.toggle(t, 1, 1, E, before)
    check(keys(before) == ["up_firsta_t", "up_firstc_t"], "toggle leaves the plan it was given as it was")

    v = env.valid(t, S("up_firsta_t"), S("up_firsta_t", "up_firstc_t", "up_firstd_t", "up_firste_t", "up_seconc_t", "bogus"))
    check([names(k) for k in keys(v)] == ["firstc", "firste"],
          "a plan checked again: installed, partnered, unopened and unknown upgrades leave it: %s" % keys(v))
    v = env.valid(t, S("up_firstb_t"), S("up_firsta_t", "up_secona_t"))
    check([names(k) for k in keys(v)] == ["secona"], "the partner of something since installed leaves: %s" % keys(v))
    v = env.valid(t, S("up_fourta_t"), S("up_fourtc_t"))
    check(len(v) == 0, "the engine's rule too: no upgrade of the other parent group, out: %s" % keys(v))

    o = [names(x.cell.section) for x in env.order(t, S("up_seconc_t", "up_firste_t", "up_firstc_t", "up_secona_t", "up_firsta_t")).values()]
    check(o == ["firsta", "firstc", "firste", "secona", "seconc"], "the plan in install order: %s" % o)

    lt = env.later(t, E, S("up_fourta_t", "up_fourtc_t", "up_fiftha_t", "up_fifthc_t"))
    check([names(k) for k in keys(lt)] == ["fourtc"],
          "the toolkit installs row 4 before row 5: the upgrade the fifth row opens too waits for a second visit: %s" % keys(lt))
    lt = env.later(t, E, S("up_fourta_t", "up_fourtc_t", "up_fourte_t", "up_fiftha_t", "up_fifthc_t"))
    check([names(k) for k in keys(lt)] == ["fourtc", "fourte"],
          "and what only it opens waits with it: %s" % keys(lt))
    lt = env.later(t, S("up_fiftha_t", "up_fifthc_t"), S("up_fourta_t", "up_fourtc_t"))
    check(len(lt) == 0, "once the fifth row's is in, it goes in on the next visit: %s" % keys(lt))
    lt = env.later(t, E, S("up_firsta_t", "up_firstc_t", "up_firste_t"))
    check(len(lt) == 0, "openers earlier in the same visit: nothing waits")

    k = [(x.sec, x.n) for x in env.kits(t, S("up_firsta_t", "up_firstc_t", "up_firste_t", "up_secona_t", "up_seconc_t", "up_secone_t")).values()]
    check(k == [("upgr_w_1_internal", 2), ("upgr_w_2_external", 2), ("upgr_w_3_external", 1), ("upgr_w_3_internal", 1)],
          "the kits, one per upgrade, by kit: %s" % k)
    k = [x.sec for x in env.kits(t, S("up_firstb_t", "up_secona_t", "up_thirda_t", "up_fourta_t", "up_fiftha_t", "up_fifthc_t",
                                     "up_fourtd_t")).values()]
    check(k == sorted(k) and len(k) == 4, "kits of four kinds, by name: %s" % k)

    lua.execute('CARRIED = { item("upgr_w_1_internal", 101), item("upgr_w_1_internal", 102, nil, 3), item("upgr_w_2_external", 103) }\n'
                'STASHED = { item("upgr_w_2_external", 201), item("upgr_w_3_internal", 202, nil, 2) }')
    held = env.kits_held(S("upgr_w_1_internal", "upgr_w_2_external", "upgr_w_3_internal"))
    h = {x: held[x] for x in held.keys()}
    check(h == {"upgr_w_1_internal": 4, "upgr_w_2_external": 2, "upgr_w_3_internal": 2},
          "kits held, by uses, carried and in stashes nearby: %s" % h)
    check(list(g.RANGES.values()) == [25], "stashes within Craft From Stashes' range: %s" % list(g.RANGES.values()))

    o = lua.eval('item("wpn_test", 7, { "up_firsta_t", "up_secona_t", "up_firstc_t" })')
    check(list(env.installed_on(o).values()) == ["up_firsta_t", "up_secona_t", "up_firstc_t"], "an object's upgrades in the order they went in")
    n_logs = len(g.logs)
    check(len(env.installed_on(lua.eval('item("wpn_test", 8, "boom")'))) == 0 and len(g.logs) == n_logs + 1,
          "an object that cannot tell: none, logged")
    check(list(env.installed_in("wpn_test").values()) == ["up_firsta_t", "up_secona_t"], "a section's own upgrades")

    # the items carried: guns, suits, helmets with a tree, by kind then name; knives and items
    # without a tree left out; one accuracy check per gun section in the log
    lua.execute("""
CARRIED = { item("helm_x", 5), item("wpn_own", 4), item("suit_x", 3), item("wpn_test", 2, { "up_firsta_t" }),
            item("wpn_knife", 6), item("wpn_plain", 9), item("wpn_test", 1) }
CARRIED[4].disp = 0.006
CARRIED[7].disp = 0.004
CARRIED[2].disp = 0.005
""")
    n_logs = len(g.logs)
    got = [(x.sec, x.id, x.kind) for x in env.carried().values()]
    check(got == [("wpn_own", 4, "gun"), ("wpn_test", 1, "gun"), ("wpn_test", 2, "gun"), ("suit_x", 3, "suit"), ("helm_x", 5, "helmet")],
          "carried: guns, suits, helmets, by name then id; no knife, nothing without a tree: %s" % got)
    model_logs = [x for x in list(g.logs.values())[n_logs:] if "accuracy model" in x]
    check(len(model_logs) == 1 and "wpn_test" in model_logs[0] and "0.006 rad" in model_logs[0] and "%" not in model_logs[0],
          "a gun whose engine dispersion the model misses is logged, with its numbers; one that matches is not: %s"
          % model_logs)
    env.carried()
    check(len([x for x in list(g.logs.values())[n_logs:] if "accuracy model" in x]) == 1, "and only once a session")

    # the card: the card's rows in its order, now and with the plan, damage and rows without a
    # formula left to the card's own value, then weight
    rows = env.card("wpn_test", Lst("up_firsta_t"), Lst("up_firsta_t", "up_firstc_t", "up_firste_t"), None, None)
    got = [(r.stat, r.now_text, r.plan_text, r.better) for r in rows.values()]
    check(got == [("accuracy", "71 perc", "73 perc", True), ("fire_rate", "600 rpm", "600 rpm", None),
                  ("recoil", "49", "47", True), ("weight", "3.1 kg", "3.3 kg", False)],
          "a gun's card now and planned: better and worse marked, lower better on a row the card shows the "
          "other way round, heavier worse: %s" % got)
    asked = [(a.sec, a.ups) for a in g.asked.values()]
    check(asked[-2:] == [("wpn_test", "up_firsta_t"), ("wpn_test", "up_firsta_t,up_firstc_t,up_firste_t")],
          "values asked with the upgrades in, and in plan: %s" % asked[-2:])
    lua.execute("asked = {}")
    rows = env.card("wpn_own_scope_a", Lst(), Lst(), lua.eval("{ silencer = 'sil_own' }"),
                    lua.eval("{ scope = 'scope_b', silencer = 'sil_own', launcher = 'gl_up' }"))
    asked = [(a.sec, a.ups) for a in g.asked.values()]
    w = [(r.now_text, r.plan_text) for r in rows.values() if r.stat == "weight"]
    check(asked == [("wpn_own_scope_a", ""), ("wpn_own", "")] and w == [("3.55 kg", "5.1 kg")],
          "a scope swap: the gun without its combination (none for scope_b), weights of scope, suppressor and "
          "launcher added: %s %s" % (asked, w))
    lua.execute("SEC.wpn_own_scope_b = { parent_section = 'wpn_own' }; asked = {}")
    env.card("wpn_own", Lst(), Lst(), None, lua.eval("{ scope = 'scope_b' }"))
    check([a.sec for a in g.asked.values()] == ["wpn_own", "wpn_own_scope_b"], "a scope with a combination: that section")
    lua.execute("asked = {}")
    env.card("wpn_own_scope_a", Lst(), Lst(), None, lua.eval("{ scope = false }"))
    check([a.sec for a in g.asked.values()] == ["wpn_own_scope_a", "wpn_own"], "no scope: the gun it is made of")
    rows = env.card("suit_x", Lst(), Lst("up_thirda_t"), None, None)
    got = [(r.stat, r.now_text, r.plan_text, r.better) for r in rows.values()]
    check(got == [("fire_wound_protection", "+40 perc", "+41 perc", True), ("apres_modifier", "+58 ", "+58 ", None),
                  ("additional_inventory_weight", "+5.5 kg", "+5.5 kg", None), ("weight", "8 kg", "8.5 kg", False)],
          "a suit's card: its rows with signs, a row without a formula as the card shows it: %s" % got)

    m = env.mounts("wpn_test", Lst("up_firstf_t", "up_fiftha_t"))
    check(m.silencer is not None and m.silencer.sec == "sil_up" and m.silencer.own is False
          and m.launcher is not None and m.launcher.sec == "gl_up", "mounts an upgrade adds")
    m = env.mounts("wpn_own", Lst())
    check(m.silencer is not None and m.silencer.sec == "sil_own" and m.silencer.own is True and m.launcher is None,
          "the gun's own mount")
    check(env.mounts("wpn_test", Lst()).silencer is None, "no mount, no suppressor")
    f = env.fits("wpn_own_scope_a", Lst())
    check(list(f.scopes.values()) == ["scope_a", "scope_b"] and f.silencer.sec == "sil_own",
          "what fits a scoped gun: its base gun's scopes and mounts")

    # plans: by id (with the section it was made for) and by section, with attachments
    P7 = ["up_firsta_t", "up_firste_t", "up_firstc_t", "up_thirda_t", "up_seconc_t", "up_secona_t"]
    env.set_plan(7, "wpn_test", S(*P7), lua.eval("{ scope = 'scope_a', silencer = false }"))
    env.set_plan(None, "wpn_own", S("up_thirda_t"), None)
    p, a = env.plan_of(7, "wpn_test")
    check(keys(p) == sorted(P7) and a.scope == "scope_a" and a.silencer is False, "a carried item's plan and attachments")
    check(keys(env.plan_of(None, "wpn_own")[0]) == ["up_thirda_t"], "a model's plan")
    check(keys(env.plan_of(7, "wpn_other")[0]) == [], "an id now on another item: no plan")
    p["up_firstf_t"] = True
    check(keys(env.plan_of(7, "wpn_test")[0]) == sorted(P7), "a plan handed out is a copy")
    env.set_plan(8, "wpn_test", S(), lua.eval("{ scope = 'scope_a' }"))
    check(env.plan_of(8, "wpn_test")[1].scope == "scope_a", "attachments alone are a plan")
    env.set_plan(8, "wpn_test", S(), None)
    check(list(env.planned_models().values()) == ["wpn_own"], "the models with a plan")
    mdata = lua.table()
    check(g.callbacks.save_state is not None and g.callbacks.load_state is not None, "plans go into the save")
    save = g.callbacks.save_state or (lambda x: None)
    load = g.callbacks.load_state or (lambda x: None)
    save(mdata)
    wb = mdata.arsenal_workbench
    check(wb is not None and wb.id[8] is None, "an emptied plan is gone")
    check(wb is not None and list(wb.id[7].list.values()) == sorted(P7) and wb.id[7].sec == "wpn_test"
          and wb.id[7].att is not None and wb.id[7].att.scope == "scope_a",
          "plans saved as sorted lists with their section and attachments")
    env.set_plan(9, "wpn_test", S("up_firstb_t"), None)
    load(mdata)
    check(keys(env.plan_of(7, "wpn_test")[0]) == sorted(P7) and env.plan_of(7, "wpn_test")[1].scope == "scope_a"
          and keys(env.plan_of(9, "wpn_test")[0]) == [], "loaded back, and only what was saved")
    env.set_plan(10, "wpn_test", S("up_firstb_t"), None)
    env.set_plan(11, "wpn_test", S("up_firstb_t"), None)
    # 7 is gone from the world, 10 lies in a stash, 11's id is now another item's
    lua.execute("WORLD = { [10] = 'wpn_test', [11] = 'helm_x' }")
    env.forget_gone()
    check(keys(env.plan_of(7, "wpn_test")[0]) == [] and keys(env.plan_of(10, "wpn_test")[0]) == ["up_firstb_t"]
          and keys(env.plan_of(11, "wpn_test")[0]) == [] and keys(env.plan_of(None, "wpn_own")[0]) == ["up_thirda_t"],
          "plans of items gone or replaced are forgotten; one in a stash and the models' stay")

    # the handoff: only a carried item, with a plan and a toolkit
    lua.execute("""
GUN = item("wpn_test", 7, { "up_firsta_t" })
GUN.parent_obj = ACTOR_OBJ
LOOSE = item("wpn_test", 8, {})
BY_ID[7], BY_ID[8] = GUN, LOOSE
CARRIED = { GUN }
STASHED = {}
""")
    # a plan made before a (now installed) went in: a stays unchecked
    plan = S("up_firsta_t", "up_firstc_t", "up_firste_t", "up_fourta_t", "up_fourtc_t", "up_fiftha_t", "up_fifthc_t")
    check(env.cannot_install(8, "wpn_test", plan) == "not_carried", "an item not carried: no handoff")
    check(env.cannot_install(7, "wpn_other", plan) == "not_carried", "an id now on another item: no handoff")
    check(env.cannot_install(7, "wpn_test", S()) == "nothing", "nothing planned: no handoff")
    check(env.cannot_install(7, "wpn_test", plan) == "no_toolkit", "no toolkit: no handoff")
    lua.execute('STASHED = { item("itm_basickit", 300) }')
    check(env.cannot_install(7, "wpn_test", plan) is None and env.toolkit() == 1, "a toolkit in a stash nearby will do")
    lua.execute('STASHED = {}; CARRIED = { GUN, item("itm_basickit", 301), item("itm_expertkit", 302) }')
    check(env.toolkit() == 3, "the best toolkit counts: %s" % env.toolkit())

    lua.execute("WS_INSTALLED = { 'up_firsta_t' }; WS_ENABLED = { up_firste_t = false }")
    env.install(7, "wpn_test", plan)
    check(g.PDA.hid is True and g.EVENTS["arsenal_workbench/install"] is not None, "the PDA closes, the toolkit waits for it")
    lua.execute("PDA.shown = true")
    ev = g.EVENTS["arsenal_workbench/install"]
    check(ev.f() is False and len(g.OPENED) == 0, "while the PDA is still up, it waits")
    lua.execute("PDA.shown = false")
    check(ev.f() is True and len(g.OPENED) == 1, "then it opens the toolkit window")
    ws = g.WS
    dlg = ws.dlg_upgrade
    check(list(g.OPENED[1].flags.values()) == [False, False, True, False, False] and g.OPENED[1].dbg is False,
          "with the best toolkit's flags, not in test mode")
    check(ws.tab == "upgrade" and dlg.selected == 70 and dlg.clicked == 70, "on the Upgrade tab, the item selected")
    checks = [names(x) for x in dlg.checks.values()]
    check(checks == ["fourta", "fiftha", "firstc", "fifthc"] and dlg.evals == 4,
          "the plan checked column by column, each evaluated; a disabled one (no kit) and one for a second visit "
          "left: %s" % checks)
    last = env.last_install
    check(last is not None and sorted(names(x) for x in last.left.values()) == ["firste", "fourtc"] and last.err is None,
          "what was left is told: %s" % (last and list(last.left.values())))
    lua.execute("WS_OPEN = true")
    env.install(7, "wpn_test", plan)
    lua.execute("PDA.shown = false")
    n_logs = len(g.logs)
    g.EVENTS["arsenal_workbench/install"].f()
    check(env.last_install.err is not None and len(g.logs) == n_logs + 1, "a toolkit window already open: told, logged")
    lua.execute("WS_OPEN = false; NOW = 1000; PDA.shown = true")
    env.install(7, "wpn_test", plan)
    lua.execute("NOW = 5000; PDA.shown = true")
    check(g.EVENTS["arsenal_workbench/install"].f() is True, "a PDA that will not close is waited for three seconds at most")
    lua.execute("NOW = 1000; CONSOLE_3D = true; PDA.shown = true; PDA.slot = nil")
    env.install(7, "wpn_test", plan)
    check(g.PDA.slot == 0, "the 3D PDA is put away")
    lua.execute("WS_CELL = false; PDA.shown = false")
    g.EVENTS["arsenal_workbench/install"].f()
    check(env.last_install.err is not None, "an item the window does not list: told")
    lua.execute("WS_CELL = nil; ui_workshop.get_workshop_ui = function() error('broken') end")
    env.install(7, "wpn_test", plan)
    r = call(g.EVENTS["arsenal_workbench/install"].f)
    check(r[0] is True and env.last_install.err is not None, "a toolkit that fails: caught, told: %s" % (r,))

    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
