"""Run arsenal_data.script under LuaJIT against stubs of the engine, and check the catalog:
what is listed and where, what is skipped, the order, and the stat rows with their stand-ins.

    python test_data.py            the real script
    python test_data.py MUTANT     a broken copy (see MUTANTS); the run must fail
"""
import io
import os
import re
import sys

import lupa.luajit21 as L

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "..", "gamedata", "scripts", "arsenal_data.script"), encoding="latin-1").read()

# section -> fields; a stand-in for system.ltx after inheritance and DLTX
SECTIONS = {
    "wpn_ak74": dict(kind="w_rifle", inv_name="st_ak74", inv_grid_x="10", repair_type="rifle_5", ammo_class="ammo_545, ammo_545_bad, ammo_545_alt, ammo_545_ap",
                     bullet_speed="900", condition_shot_dec="0.0005", zoom_cam_dispersion="0.5",
                     fire_modes="1, -1", inv_weight="3.3", description="st_ak74_descr", parent_section="wpn_ak74",
                     fire_dispersion_base="0.6", rpm="600", upgrades="up_gr_a, up_gr_b", installed_upgrades="up_b1",
                     scopes="kobra, lam, ak_kit, missing_scope", silencer_status="2", silencer_name="wpn_sil",
                     grenade_launcher_status="2", grenade_launcher_name="wpn_gl", grenade_class="ammo_vog, ammo_vog_bad"),
    "wpn_ak74_pso": dict(kind="w_rifle", inv_name="st_ak74", inv_grid_x="10", parent_section="wpn_ak74"),
    "wpn_pm": dict(kind="w_pistol", inv_name="st_pm", inv_grid_x="1", ammo_class="ammo_9x18", upgrades="up_gr_pm",
                   scopes="pm_kit", repair_type="pistol"),
    # a copy that plays as the PM (one variant), with the same kit: the gun the kit makes is
    # made of the PM once
    "wpn_pm_copy": dict(kind="w_pistol", inv_name="st_pm", inv_grid_x="1", ammo_class="ammo_9x18", scopes="pm_kit"),
    "pm_kit": dict(inv_name="st_pm_kit"),
    # the gun the PM's kit makes: a model of its own
    "wpn_pm_pm_kit": dict(kind="w_pistol", inv_name="st_pm_tac", inv_grid_x="1", ammo_class="ammo_9x18"),
    "wpn_pm_copy_pm_kit": dict(kind="w_pistol", inv_name="st_pm_tac", inv_grid_x="1", ammo_class="ammo_9x18"),
    # fighters with a loadout of their own: an army sniper (a rank), UNISG's black ops (none),
    # and one whose loadout is missing
    "sim_sniper": dict(community="army", spec_rank="veteran"),
    "sim_blackops": dict(community="isg"),
    "sim_nobody": dict(community="stalker", spec_rank="novice"),
    "up_gr_pm": dict(elements="up_pm_sil"),
    "up_pm_sil": dict(section="up_sect_pm_sil", property="prop_silencer"),
    "up_sect_pm_sil": dict(silencer_status="2", silencer_name="wpn_sil"),
    "wpn_aps": dict(kind="w_pistol", inv_name="st_aps", inv_grid_x="2", cost="1"),
    "wpn_toz34": dict(kind="w_shotgun", inv_name="st_toz", inv_grid_x="3", scopes_sect="scope_toz",
                      fire_dispersion_base="0.75", upgrades="up_gr_t"),
    "wpn_rpg7": dict(kind="w_explosive", weapon_class="rpg7", inv_name="st_rpg", inv_grid_x="4", scope_status="1"),
    "grenade_f1": dict(kind="w_explosive", inv_name="st_f1", inv_grid_x="5"),
    "wpn_knife": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife", inv_grid_x="6", ammo_class="ammo_knife",
                      repair_type="knife"),
    # repair kits: Weapon Parts Overhaul's pair for rifle_5 (the pistol's pair is not in the game),
    # sharpening stones for knives
    "cleaning_kit_r5": dict(inv_name="st_ck_r5"),
    "toolkit_r5": dict(inv_name="st_tk_r5"),
    "sharpening_stones": dict(inv_name="st_stones"),
    "ammo_knife": dict(kind="w_ammo", fake_ammo="true"),
    "mp_wpn_ak74": dict(kind="w_rifle", inv_name="st_ak74", inv_grid_x="10"),
    "wpn_addon_scope": dict(kind="w_rifle", inv_name="st_scope", inv_grid_x="7"),
    "wpn_no_name": dict(kind="w_smg", inv_grid_x="8"),
    "wpn_no_icon": dict(kind="w_smg", inv_name="st_noicon"),
    "wpn_untranslated": dict(kind="w_smg", inv_name="st_missing", inv_grid_x="9"),
    "ammo_545": dict(kind="w_ammo", inv_name="st_545", inv_name_short="st_545_s", k_bullet_speed="1.1"),
    "ammo_545_ap": dict(kind="w_ammo", inv_name="st_545ap"),
    "ammo_545_bad": dict(kind="w_ammo", inv_name="st_545", inv_name_short="st_545_worn"),
    "ammo_545_alt": dict(kind="w_ammo", inv_name="st_545", inv_name_short="st_545_s"),
    "ammo_9x18": dict(kind="w_ammo", inv_name="st_918"),
    "actor": dict(),
    # guns that share a name: two that play the same, a magazine pair, a caliber pair, a pair
    # nothing tells apart (no recoil profile for the one difference), a mount pair where only
    # one has a recoil profile, and a knife's attack animation
    "wpn_fort": dict(kind="w_pistol", inv_name="st_fort", inv_grid_x="1", ammo_class="ammo_9x18", ammo_mag_size="13",
                     scopes="kit2"),
    # the gun the Fort-17's kit makes: the same name and play, so the same variant (a kit for looks)
    "wpn_fort_kit2": dict(kind="w_pistol", inv_name="st_fort", inv_grid_x="1", ammo_class="ammo_9x18", ammo_mag_size="13"),
    "kit2": dict(inv_name="st_kit2"),
    "wpn_fort17": dict(kind="w_pistol", inv_name="st_fort", inv_grid_x="1", ammo_class="ammo_9x18", ammo_mag_size="13"),
    "wpn_usp": dict(kind="w_pistol", inv_name="st_usp", inv_grid_x="1", ammo_class="ammo_9x19", ammo_mag_size="12"),
    "wpn_usp_45": dict(kind="w_pistol", inv_name="st_usp", inv_grid_x="1", ammo_class="ammo_45", ammo_mag_size="12"),
    "ammo_9x19": dict(kind="w_ammo", inv_name="st_919"),
    "ammo_45": dict(kind="w_ammo", inv_name="st_45"),
    "wpn_mp5": dict(kind="w_smg", inv_name="st_mp5", inv_grid_x="1", ammo_class="ammo_9x19", ammo_mag_size="30",
                    scopes="kurtz", upgrades="up_gr_mp5", grenade_class="ammo_vog"),
    "up_gr_mp5": dict(elements="up_mp5_gl"),
    "up_mp5_gl": dict(section="up_sect_mp5_gl", property="prop_underbarrel_slot"),
    "up_sect_mp5_gl": dict(grenade_launcher_status="2", grenade_launcher_name="wpn_gl"),
    "wpn_mp5_kurtz": dict(kind="w_smg", inv_name="st_mp5", inv_grid_x="1", ammo_class="ammo_9x19", ammo_mag_size="20"),
    # a copy that plays as the MP5: Nimble takes either, named once
    "wpn_mp5_alt": dict(kind="w_smg", inv_name="st_mp5", inv_grid_x="1", ammo_class="ammo_9x19", ammo_mag_size="30"),
    # Nimble's MP5, for an MP5 and money
    "wpn_mp5_nimble": dict(kind="w_smg", inv_name="st_mp5_nimble", inv_grid_x="1", ammo_class="ammo_45"),
    # a gun with its own laser: every combination carries it, so its Kobra is a scope
    "wpn_isg": dict(kind="w_rifle", inv_name="st_isg", inv_grid_x="1", laser_status="true", scopes="kobra"),
    "wpn_isg_kobra": dict(kind="w_rifle", inv_name="st_isg", parent_section="wpn_isg", laser_status="true"),
    "wpn_twin_a": dict(kind="w_rifle", inv_name="st_twin", inv_grid_x="1", zoom_cam_dispersion="0.5"),
    "wpn_twin_b": dict(kind="w_rifle", inv_name="st_twin", inv_grid_x="1", zoom_cam_dispersion="0.7"),
    "wpn_mount_a": dict(kind="w_rifle", inv_name="st_mount", inv_grid_x="1", zoom_cam_dispersion="0.5", silencer_status="2"),
    "wpn_mount_b": dict(kind="w_rifle", inv_name="st_mount", inv_grid_x="1", zoom_cam_dispersion="0.5", silencer_status="0"),
    "animation_hit_wpn_knife": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife", inv_grid_x="6"),
    # the AK-74's upgrade tree: group a (a1 more accurate, opens c; a2 a caliber conversion),
    # group b (b1, shipped with the gun), group c (c1 faster, c2 faster still but less accurate)
    "up_gr_a": dict(elements="up_a1, up_a2"),
    "up_a1": dict(section="up_sect_a1", property="prop_dispersion", effects="up_gr_c"),
    "up_sect_a1": dict(fire_dispersion_base="-0.15"),
    "up_a2": dict(section="up_sect_a2", property="prop_calibre, prop_silencer", effects="up_gr_c"),
    "up_sect_a2": dict(fire_dispersion_base="-0.3", ammo_class="ammo_9x19, ammo_9x19_bad"),
    "up_gr_b": dict(elements="up_b1"),
    "up_b1": dict(section="up_sect_b1", property="prop_rpm"),
    "up_sect_b1": dict(rpm="100"),
    "up_gr_c": dict(elements="up_c1, up_c2"),
    "up_c1": dict(section="up_sect_c1", property="prop_rpm"),
    "up_sect_c1": dict(rpm="50", fire_modes="1, 3, -1"),
    "up_c2": dict(section="up_sect_c2", property="prop_rpm"),
    "up_sect_c2": dict(rpm="80", fire_dispersion_base="0.6"),
    # what fits the AK-74: a scope, a kit (its combination has another name), a suppressor, a
    # launcher; the TOZ's scope comes through scopes_sect
    "kobra": dict(inv_name="st_kobra"),
    "wpn_ak74_kobra": dict(kind="w_rifle", inv_name="st_ak74", parent_section="wpn_ak74"),
    "ak_kit": dict(inv_name="st_kit"),
    "wpn_ak74_ak_kit": dict(inv_name="st_ak74_tac", parent_section="wpn_ak74"),
    "lam": dict(inv_name="st_lam"),
    "wpn_ak74_lam": dict(inv_name="st_ak74", parent_section="wpn_ak74", laser_status="true"),
    # a kit whose gun is a variant in the catalog (GAMMA's MP5K kit makes wpn_mp5_kurtz)
    "kurtz": dict(inv_name="st_kurtz"),
    # an upgrade that would take the TOZ's dispersion past zero
    "up_gr_t": dict(elements="up_t1"),
    "up_t1": dict(section="up_sect_t1", property="prop_dispersion"),
    "up_sect_t1": dict(fire_dispersion_base="-1.5"),
    "wpn_sil": dict(inv_name="st_sil"),
    "wpn_gl": dict(inv_name="st_gl"),
    "ammo_vog": dict(inv_name="st_vog"),
    "ammo_vog_bad": dict(inv_name="st_vog_bad"),
    "scope_toz": dict(scope_name="pu_scope"),
    "pu_scope": dict(inv_name="st_pu"),
    "prt_barrel": dict(inv_name="st_barrel"),
    "mag_ak_30": dict(inv_name="st_mag30", max_mag_size="30"),
    "mag_ak_60": dict(inv_name="st_mag60", max_mag_size="60"),
    "prt_bolt": dict(inv_name="st_bolt"),
    # one name, one gun shipped with an upgrade: the card (and the tag) counts it
    "wpn_upg_a": dict(kind="w_smg", inv_name="st_upg", inv_grid_x="1", rpm="500", installed_upgrades="up_fast"),
    "wpn_upg_b": dict(kind="w_smg", inv_name="st_upg", inv_grid_x="1", rpm="600"),
    "up_fast": dict(section="up_sect_fast"),
    "up_sect_fast": dict(rpm="200"),
}
PARTS = {"con_parts_list": dict(wpn_ak74="prt_barrel, prt_bolt, prt_gone")}
TEXT = {"st_ak74": "AK-74", "st_pm": "PM", "st_aps": "Stechkin APS", "st_toz": "TOZ-34", "st_rpg": "RPG-7",
        "st_f1": "F1", "st_knife": "Knife", "st_scope": "Scope", "st_noicon": "No icon",
        "st_545": "5.45x39 FMJ", "st_545_s": "5.45 FMJ", "st_545_worn": "5.45 FMJ (worn)", "st_545ap": "5.45x39 AP", "st_918": "9x18",
        "st_ak74_descr": "A rifle.", "st_fort": "Fort-17", "st_usp": "USP", "st_919": "9x19 FMJ",
        "st_45": "Cartridge .45 ACP", "st_mp5": "MP5", "st_twin": "Twin", "st_mount": "Mount",
        "st_kobra": "Kobra", "st_kit": "Tactical Kit", "st_ak74_tac": "AK-74 Tactical", "st_sil": "PBS-1",
        "st_gl": "GP-25", "st_vog": "VOG-25", "st_vog_bad": "VOG-25 (worn)", "st_pu": "PU", "st_upg": "Upgr",
        "st_barrel": "Barrel", "st_bolt": "Bolt", "st_lam": "LAM", "st_kurtz": "MP5K kit", "st_kit2": "Fort kit",
        "st_mag30": "AK-74 Magazine", "st_mag60": "AK-74 Drum", "st_mp5_nimble": "MP5 Frasier",
        "st_pm_kit": "PM kit", "st_pm_tac": "PM Tactical", "st_ck_r5": "Type C Cleaning Kit",
        "st_tk_r5": "Type C Repair Kit", "st_stones": "Sharpening Stones",
        "st_isg": "ISG Rifle", "st_camo_base": "Base", "st_camo_tan": "Tan",
        "st_camo_woodland": "Woodland"}
# Arsenal's own strings, so the tags read as in game
TEXT.update(re.findall(r'<string id="([^"]+)">\s*<text>(.*?)</text>',
                       io.open(os.path.join(HERE, "..", "gamedata", "configs", "text", "eng", "st_arsenal.xml"),
                               encoding="cp1251").read(), re.S))
RECOIL = {"wpn_ak74": dict(s="0.2, 0.3", e="0:0.5, 0.1:0"), "wpn_mount_a": dict(s="0.2, 0.3", e="0:0.5, 0.1:0")}

FACTIONS = ["stalker", "dolg", "freedom", "csky", "ecolog", "killer", "army", "bandit", "monolith", "zombied",
            "renegade", "greh", "isg"]
# ini files of ordered lines (key, value): name -> section -> lines
# NPC loadouts: Loners have three ranks of their own (a slot with a missing gun, a gun weighted
# 0 and a line without a weight), the rest of theirs fall to the faction's loadout; every other
# faction has none and falls to the default
NPC = {
    "default": [("primary", "def_primary")],
    "def_primary": [("wpn_pm:0:r", "")],
    "stalker": [("primary", "vet_primary")],
    "vet_primary": [("wpn_toz34:0:0:5", "")],
    "stalker_novice": [("primary", "st_primary"), ("secondary", "st_secondary")],
    "stalker_trainee": [("primary", "st_primary")],
    "stalker_legend": [("primary", "st_primary")],
    "st_primary": [("wpn_ak74:r:0:30", ""), ("wpn_mp5:0:r:10", ""), ("wpn_mp5_kurtz:0:0", ""),
                   ("wpn_gone:0:0:50", ""), ("wpn_aps:0:0:0", "")],
    "st_secondary": [("wpn_pm:0:r", "")],
    "loadouts_per_name": [("sim_sniper", "loadout_sniper"), ("sim_blackops", "loadout_blackops"),
                          ("sim_nobody", "loadout_missing")],
    "loadout_sniper": [("primary", "sniper_primary")],
    "sniper_primary": [("wpn_ak74:1:0:10", ""), ("wpn_toz34:0:0:30", "")],
    "loadout_blackops": [("primary", "blackops_primary")],
    "blackops_primary": [("wpn_mp5:4:1", "")],
}
# stashes: the PM barred at economy 2, the APS too cheap, the TOZ at a tier no roll beats, the
# MP5's kind in no table, the RPG-7 in rare stashes only, the AK-74's scoped copy a tier up
TREASURE = {
    "possible_items": [("wpn_ak74", ""), ("wpn_ak74_kobra", ""), ("wpn_pm", "2"), ("wpn_toz34", ""), ("wpn_mp5", ""),
                       ("wpn_rpg7", ""), ("wpn_aps", ""), ("novice_outfit", "")],
    "kind_tier_effect_common": [("w_rifle", "7, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1"),
                                ("w_pistol", "5, 600, 1,1, 0.8,1, 0.75,1, 0.3,1, 0.01,1"),
                                ("w_shotgun", "7, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1")],
    "kind_tier_effect_rare": [("w_rifle", "10, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1"),
                              ("w_explosive", "5, 500, 1,1, 0.8,1.25, 0.75,1.5, 0.6,1.5, 0.5,1.5")],
}
TIERS = {"wpn_ak74": [("tier", "3")], "wpn_ak74_kobra": [("tier", "3.6")], "wpn_pm": [("tier", "1")],
         "wpn_toz34": [("tier", "5")], "wpn_mp5": [("tier", "2")], "wpn_rpg7": [("tier", "2")], "wpn_aps": [("tier", "1")]}
# new-game kits: a knife for everyone, the PM at two prices, the TOZ on the easiest economy only,
# an MP5 that the injector adds for Loners, a USP it takes out, a gun the game lacks
KITS = {f + "_loadout": [("wpn_knife", "false,1,0")] for f in FACTIONS}
KITS["stalker_loadout"] += [("wpn_pm", "true,1,90"), ("wpn_toz34", "true,1,650,1"), ("wpn_usp_45", "true,1,200"),
                            ("wpn_gone", "true,1,5")]
KITS["bandit_loadout"] += [("wpn_pm", "true,1,90"), ("wpn_toz34", "true,1,650,1"), ("wpn_mp5", "true,1,400")]
KITS["dolg_loadout"] += [("wpn_pm", "true,1,120")]
FILES = {r"items\settings\npc_loadouts\npc_loadouts.ltx": NPC, r"items\settings\new_game_loadouts.ltx": KITS,
         "treasure": TREASURE, "tiers": TIERS}

STUBS = r"""
local S, T, R, P, F = ...
local function ini(tbl)
    local o = {}
    function o:r_string_ex(sec, key) local s = tbl[sec]; return s and s[key] end
    function o:r_float_ex(sec, key) local v = self:r_string_ex(sec, key); return v and tonumber(v) end
    function o:section_exist(sec) return tbl[sec] ~= nil end
    function o:section_for_each(fn)
        local names = {}
        for k in pairs(tbl) do names[#names + 1] = k end
        table.sort(names)
        for _, k in ipairs(names) do if fn(k) then return end end
    end
    return o
end
-- an ini file of ordered lines, sec -> { { key, value }, ... }; like the engine's, reading the
-- lines of a missing section fails
local function lini(tbl)
    local o = {}
    function o:section_exist(sec) return tbl[sec] ~= nil end
    function o:line_count(sec) assert(tbl[sec], "line_count on a missing section"); return #tbl[sec] end
    function o:r_line_ex(sec, i, a, b)
        assert(tbl[sec], "r_line_ex on a missing section")
        local l = tbl[sec][i + 1]
        return true, l[1], l[2]
    end
    function o:r_string_ex(sec, key)
        local v
        for _, l in ipairs(tbl[sec] or {}) do if l[1] == key then v = l[2] end end
        return v
    end
    function o:r_float_ex(sec, key) local v = self:r_string_ex(sec, key); return v and tonumber(v) end
    return o
end
ini_sys = ini(S)
function ini_file(name) return F[name] and lini(F[name]) or ini(R) end
-- the stash script: its ini files, and its level lists as locals of the functions that use them
local map_tiers = { l01_escape = { 1, 1, 2 }, l02_garbage = { 2, 3 }, l03_agroprom = { 3, 3, 4 },
    l08_yantar = { 3, 4, 4, 4 }, lab = { 4, 4 }, l10_radar = { 4, 5 } }
local blacklisted_maps = { lab = true }
treasure_manager = { ini_treasure = lini(F.treasure), ini_tiers = lini(F.tiers) }
function treasure_manager.set_random_stash() return map_tiers end
function treasure_manager.box_in_valid_map(lvl) return not blacklisted_maps[lvl] end
ECO = 2
local toolkit_map = { rifle_5 = { "cleaning_kit_r5", "toolkit_r5" }, pistol = { "cleaning_kit_p", "toolkit_p" } }
zzzz_arti_jamming_repairs = {}
function zzzz_arti_jamming_repairs.get_suitable_kit(obj, clean) return toolkit_map end
function GetItemList(typ)
    if typ ~= "repair" then return {} end
    return { sharpening_stones = { knife = true }, glue_a = { outfit = true }, cleaning_kit_r5 = { rifle_5 = true } }
end

-- 3DSS's camo system: its loaded configs and checks as locals of the functions that use them
-- (copies of the real ones). The AK-74 in Base, Tan (to discover; Loners drop it rarely,
-- Military commonly, Bandits too but they carry no AK-74) and Woodland (to discover, and
-- discovered; UNISG drops it but carries no AK-74, Loners never); a PM camo that is not the
-- AK-74's; the MP5's Base under two sections of one variant.
local CAMO_W = { common = 50, uncommon = 25, rare = 10, very_rare = 4, legendary = 1, none = 0 }
local config_files = {
    { name = "ak.ltx", section_order = { "wpn_ak74", "wpn_ak74_tan", "wpn_ak74_woodland", "wpn_pm_tan" },
      sections = {
        wpn_ak74 = { label = "st_camo_base", icon = "black", drop_factions = {}, faction_rarities = {} },
        wpn_ak74_tan = { label = "st_camo_tan", icon = "tan", unlock_required = true, rarity = "rare",
            drop_factions = { stalker = true, army = true, bandit = true }, faction_rarities = { army = "common" } },
        wpn_ak74_woodland = { label = "st_camo_woodland", icon = "woodland", unlock_required = true, rarity = "rare",
            drop_factions = { isg = true, stalker = true }, faction_rarities = { stalker = "none" } },
        wpn_pm_tan = { label = "st_camo_tan", icon = "tan", drop_factions = {}, faction_rarities = {} },
      } },
    { name = "mp5.ltx", section_order = { "wpn_mp5", "wpn_mp5_alt" }, sections = {
        wpn_mp5 = { label = "st_camo_base", icon = "black", drop_factions = {}, faction_rarities = {} },
        wpn_mp5_alt = { base = "wpn_mp5_alt", label = "st_camo_base", icon = "black", drop_factions = {},
            faction_rarities = {} },
      } },
}
local unlocked_sections = { ["ak.ltx|wpn_ak74_woodland"] = true }
local function target_belongs_to_weapon(file_data, base_section, target_section)
    if not file_data.sections[base_section] then return false end
    if target_section == base_section then return true end
    local section_data = file_data.sections[target_section]
    if section_data and section_data.base then return section_data.base == base_section end
    return string.sub(target_section, 1, #base_section + 1) == base_section .. "_"
end
local function label_for(file_data, base_section, target_section)
    local d = file_data.sections[target_section]
    return d and d.label and game.translate_string(d.label) or target_section
end
local function camo_is_unlocked(file_data, section)
    local d = file_data.sections[section]
    if not d or not d.unlock_required then return true end
    return unlocked_sections[file_data.name .. "|" .. section] == true
end
local function camo_can_drop_for(d, faction)
    if next(d.drop_factions) and not (faction and d.drop_factions[faction]) then return false end
    local r = faction and d.faction_rarities[faction]
    if r == nil then r = d.rarity end
    if r ~= nil then return (CAMO_W[r] or 0) > 0 end
    return false
end
local function camo_rarity_weight(d, faction, default)
    local r = faction and d.faction_rarities[faction]
    if r == nil then r = d.rarity end
    if r ~= nil then return CAMO_W[r] or 0 end
    return default and CAMO_W[default] or 0
end
z_3dss_gamma_camo_system = {}
function z_3dss_gamma_camo_system.get_camo_options(weapon)
    return { config_files, target_belongs_to_weapon, label_for, camo_is_unlocked }
end
function z_3dss_gamma_camo_system.assign_drop_camo(weapon, faction)
    return { camo_can_drop_for, camo_rarity_weight }
end
game_difficulties = { get_eco_factor = function(k) return k == "type" and ECO or nil end }
-- the kit injector: an MP5 for Loners and Bandits, an RPG-7 for Loners on the harder economies,
-- the AK-74 given to everyone, the USP taken out
new_game_loadout_injector_mcm = {
    loadout_removed_items = { wpn_usp_45 = true },
    loadout_items = {
        wpn_mp5 = { { section = "wpn_mp5", points = 400, faction = { stalker = true, bandit = true }, economy = {} } },
        wpn_rpg7 = { { section = "wpn_rpg7", points = 300, faction = { stalker = true },
                       economy = { st_econ_2 = true, st_econ_3 = true } } },
        wpn_ak74 = { { section = "wpn_ak74", faction = {}, economy = {}, add_to_inventory = true } },
    },
}
game = { translate_string = function(k) return T[k] or k end }
function normalize(v, mn, mx) return (v - mn) / (mx - mn) end
-- _g's item lists: a weapon whose first ammo is fake ammo (a knife's) is a fake_ammo_wpn
function IsItem(typ, sec)
    if typ ~= "fake_ammo_wpn" then return nil end
    local a = (S[sec] and S[sec].ammo_class or ""):match("^%s*([^,%s]+)")
    return a and S[a] and S[a].fake_ammo == "true" or nil
end
utils_item = { get_ammo = function(sec, id)
    local out = {}
    for a in (S[sec] and S[sec].ammo_class or ""):gmatch("[^,%s]+") do out[#out + 1] = a end
    return out
end }
-- as the game: the section's value plus the changes of the upgrades it ships with
function utils_item.get_param(sec, id, param, typ, add)
    local s = S[sec]
    local v = s and s[param] and tonumber(s[param])
    if v == nil then return nil end
    for u in (s.installed_upgrades or ""):gmatch("[^,%s]+") do
        local ps = S[u] and S[u].section
        local d = ps and S[ps] and S[ps][param] and tonumber(S[ps][param])
        if d then v = v + d end
    end
    return v
end
itms_manager = { ini_parts = ini(P) }
-- Nimble's script, with the one price these tests use
NimbleTrade = { MP5Cost = 65000 }
-- Mags Redux's binder: the AK-74 takes the "ak_545" group (a drum, a box, and a section gone)
magazine_binder = {
    get_weapon_base_type = function(sec) return sec == "wpn_ak74" and "ak_545" or false end,
    get_mags_for_basetype = function(bt) return bt == "ak_545" and { "mag_ak_60", "mag_ak_30", "mag_gone" } or nil end,
}
utils_xml = {
    get_icons_texture = function(sec) return "ui\\ui_icon_equipment" end,
    get_item_axis = function(sec) return { x1 = 0, y1 = 0, w = 100, h = 50 } end,
}
utils_ui = { stats_table = { weapon = {
    accuracy = { index = 1, magnitude = 1, value_functor = { "ish_item_stats", "scale_100", "utils_ui", "prop_accuracry" } },
    fire_rate = { index = 4, magnitude = 1000, value_functor = { "utils_ui", "prop_rpm" } },
    ammo_mag_size = { index = 5, magnitude = 1 },
    speed = { index = 101, magnitude = 1000, value_functor = { "momopate_weaponstats", "get_weapon_bspeed" } },
    reliability = { index = 103, magnitude = 10000, value_functor = { "momopate_weaponstats", "get_weapon_reliability" } },
    recoil = { index = 104, magnitude = 1, value_functor = { "momopate_weaponstats", "get_weapon_recoil" } },
} } }
function utils_ui.prepare_stats_table() end
"""

MUTANTS = {
    "variants": ("if parent and parent ~= sec then return nil end", "-- variants kept"),
    "grenades": ("not ini_sys:r_string_ex(sec, \"weapon_class\")", "false"),
    "mp": ("sec:find(\"^mp_\")", "false"),
    "untranslated": ("return (s ~= key) and s or nil", "return s"),
    "standin": ("if alt and not live then", "if false then"),
    "order": ("table.sort(by_cat[c], by_name)", "-- unsorted"),
    "speed": ("bs = bs * 0.70", "bs = bs * 0.75"),
    "worn": ('if not (r:find("_bad$") or r:find("_verybad$")) then', "if true then"),
    "dedupe": ("if n and not seen[n] then\n                seen[n] = true\n                out[#out + 1] = n",
               "if n then\n                seen[n] = true\n                out[#out + 1] = n"),
    "nimble_dedupe": ("if n and not seen[n] then\n                        seen[n] = true\n                        names",
                      "if n then\n                        seen[n] = true\n                        names"),
    "collapse": ("sg = okS and sg or sec", "sg = sec"),
    "shortest": ("table.sort(secs, shorter)", "table.sort(secs, function(a, b) return shorter(b, a) end)"),
    "tags": ("label(g.name, vars)", "-- no labels"),
    "variant_order": ("table.sort(vars, by_name)", "-- as found"),
    "unknown": ("if not ok or v == nil then", 'v = v or "" if not ok then'),
    "caliber_digit": ('if w:find("%d") then return w end', "-- any word"),
    "number": ('e.name = string.format("%s [%d]", base[e], nth[base[e]])', "e.name = base[e]"),
    "animation": ('sec:find("^animation_")', "false"),
    "knife_card": ('not IsItem("fake_ammo_wpn", sec)', "true"),
    "shipped": ('local ok, v = pcall(utils_item.get_param, sec, nil, k, "float", true)', "local ok, v = false, nil"),
    "no_effects": ("queue[#queue + 1] = nxt", "-- not followed"),
    "calibre": ("if not calibre(u) then opts[#opts + 1] = u.ps end", "opts[#opts + 1] = u.ps"),
    "installed_group": ("if not g.fixed then", "if true then"),
    "mounts": ('if status(u.ps, "silencer_status") == 2 then', "if false then"),
    "mount_flag": ("s.upgrade = not u.installed", "s.upgrade = false"),
    "options_calibre": ("                if calibre(u) then", "                if false then"),
    "options_modes": ('local fm = ini_sys:r_string_ex(u.ps, "fire_modes")', "local fm = nil"),
    "worse": ("if v and v > cur then", "if v then"),
    "kits": ("if v or (cname and cname ~= own) then", "if false then"),
    "scopes_sect": ('scope(ini_sys:r_string_ex(ss, "scope_name"))', "-- scopes_sect left out"),
    "parts_parent": ('local key = ini_sys:r_string_ex(sec, "parent_section") or sec', "local key = sec"),
    "lasers": ('if not own_laser and ini_sys:r_string_ex(combo, "laser_status") == "true" then', "if false then"),
    "laser_own": ('if not own_laser and ini_sys:r_string_ex(combo, "laser_status") == "true" then',
                  'if ini_sys:r_string_ex(combo, "laser_status") == "true" then'),
    "laser_builtin": ("    out.builtin.laser = own_laser\n", ""),
    "cosmetic": ("if not (v and v == variant_of(sec)) then", "if true then"),
    "kg_raw": ("return math.floor(x * 100 + 0.5) / 100", "return x"),
    "mags_sort": ("    table.sort(out, function(a, b)\n        if a.rounds ~= b.rounds", "    local _ = (function(a, b)\n        if a.rounds ~= b.rounds"),
    "mags_guard": ("    if not magazine_binder then return out end\n", ""),
    "nimble_guard": ("    if not NimbleTrade then return out end\n", ""),
    "nimble_variant": ("return s == sec or (mine ~= nil and variant_of(s) == mine)", "return true"),
    "kit_variant": ("if v or (cname and cname ~= own) then", "if cname and cname ~= own then"),
    "carry_missing": ('if f[1] ~= "" and ini_sys:section_exist(f[1]) then', 'if f[1] ~= "" then'),
    "carry_weight": ("local w = tonumber(f[4]) or 10", "local w = tonumber(f[4]) or 1"),
    "carry_faction": ('l = ini:section_exist(f) and f or "default"', 'l = "default"'),
    "carry_named": ('for _, l in ipairs(lines(ini, "loadouts_per_name")) do', "for _, l in ipairs({}) do"),
    "carry_special": ('            add(l.v, f, RANK_AT[r] and r or "special")',
                      "            if RANK_AT[r] then add(l.v, f, r) end"),
    "carry_order": ("if a.best ~= b.best then return a.best > b.best end",
                    "if a.best ~= b.best then return a.best < b.best end"),
    "stash_rare": ('for _, t in ipairs({ "kind_tier_effect_common", "kind_tier_effect_rare" }) do',
                   'for _, t in ipairs({ "kind_tier_effect_common" }) do'),
    "stash_ceil": ("tier = math.max(1, math.min(5, math.ceil(tier)))", "tier = math.max(1, math.min(5, math.floor(tier)))"),
    "stash_blacklist": ('if n > 0 and not (type(skip) == "table" and skip[lvl]) then', "if n > 0 then"),
    "stash_eco": ("if tonumber(x) == eco then barred = true end", "-- not barred"),
    "stash_price": ('(ini_sys:r_float_ex(sec, "cost") or 1000) > 1', "true"),
    "stash_never": ("chance * multi > 1", "chance * multi > 0"),
    "stash_rebuild": ("if not stashed or stashed_eco ~= eco then", "if not stashed then"),
    "stash_order": ("if a.share ~= b.share then return a.share > b.share end",
                    "if a.share ~= b.share then return a.share < b.share end"),
    "stash_limit": ("for i = 1, math.min(STASH_LEVELS, #best) do", "for i = 1, #best do"),
    "stash_guard": ("    if not (ini and tiers) then return end\n", ""),
    "made_model": ("local kit = m and m.entry ~= e and item_of(k)", "local kit = m and item_of(k)"),
    "made_dedupe": ("if key and not seen[key] then", "if key then"),
    "kit_removed": ("local e = not removed[l.k] and ini_sys:section_exist(l.k) and entry_for(l.k)",
                    "local e = ini_sys:section_exist(l.k) and entry_for(l.k)"),
    "kit_eco": ("                if top then", "                if false then"),
    "kit_free": ('add(e, f, v[1] == "true" and (tonumber(v[3]) or 0) or nil, eco)', "add(e, f, tonumber(v[3]) or 0, eco)"),
    "kit_injector": ("for sec, list in pairs(inj and inj.loadout_items or {}) do", "for sec, list in pairs({}) do"),
    "kit_injector_eco": ('if it.economy["st_econ_" .. n] then eco[n] = true end', "eco[n] = true"),
    "kit_injector_faction": ("if not next(it.faction or {}) or it.faction[f] then", "if true then"),
    "kit_inventory": ("add(e, f, (not it.add_to_inventory) and (tonumber(it.points) or 0) or nil, eco)",
                      "add(e, f, tonumber(it.points) or 0, eco)"),
    "kit_group": ('local key = tostring(k.points) .. "|" .. table.concat(ecos, ",")',
                  'local key = table.concat(ecos, ",")'),
    "repair_parent": ('local rt = ini_sys:r_string_ex(ini_sys:r_string_ex(sec, "parent_section") or sec, "repair_type")',
                      'local rt = ini_sys:r_string_ex(sec, "repair_type")'),
    "repair_map": ('local map = upvalue(wpo and wpo.get_suitable_kit, "toolkit_map")', "local map = nil"),
    "repair_items": ('local ok, list = pcall(GetItemList, "repair")', "local ok, list = false, nil"),
    "repair_once": ("local it = not seen[k] and item_of(k)", "local it = item_of(k)"),
    "camo_carriers": ("if carriers_of[f] and can_drop and weight and can_drop(d, f) then",
                      "if can_drop and weight and can_drop(d, f) then"),
    "camo_sort": ("if w[a] ~= w[b] then return w[a] > w[b] end", "if w[a] ~= w[b] then return w[a] < w[b] end"),
    "camo_once": ("local c = by_name[name]", "local c"),
    "camo_unlock": ("c.locked = c.locked and not unlocked(fd, t)", "c.locked = c.locked"),
    "camo_required": ("c.required = c.required or d.unlock_required == true", "c.required = false"),
    "camo_belongs": ("if d and belongs(fd, s, t) then", "if d then"),
    "camo_guard": ("    if not (e and type(files) == \"table\" and belongs and label_for and unlocked) then return out end\n", ""),
    "kit_sort": ("table.sort(g.factions, function(a, b) return FACTION_AT[a] < FACTION_AT[b] end)", "-- unsorted"),
    "no_cap": ("return math.min(100, math.floor(above0((p.fire_dispersion_base - 1.5) / (0 - 1.5)) * 100))",
               "return math.floor(above0((p.fire_dispersion_base - 1.5) / (0 - 1.5)) * 100)"),
}


def main():
    src = SRC
    mutant = sys.argv[1] if len(sys.argv) > 1 else None
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    tbl = lambda d: lua.table_from({k: (lua.table_from(v) if isinstance(v, dict) else v) for k, v in d.items()})
    lines = lambda d: lua.table_from({s: lua.table_from([lua.table_from([k, v]) for k, v in ls]) for s, ls in d.items()})
    lua.execute(STUBS, tbl(SECTIONS), lua.table_from(TEXT), tbl(RECOIL), tbl(PARTS),
                lua.table_from({name: lines(d) for name, d in FILES.items()}))
    m = lua.eval("function(src) local env = setmetatable({}, {__index = _G}); local f = assert(loadstring(src)); "
                 "setfenv(f, env); f(); return env end")(src)
    lua.globals().arsenal_data = m
    fails = []

    def check(cond, what):
        print(("ok    " if cond else "FAIL  ") + what)
        if not cond:
            fails.append(what)

    same = lua.eval("function(a, b) return rawequal(a, b) end")
    secs = lambda cat: [e.sec for e in m.list(cat).values()]
    names = lambda cat: [e.name for e in m.list(cat).values()]
    vnames = lambda e: [v.name for v in e.variants.values()] if e is not None else None
    check(m.count() == 15, "fifteen gun models listed: %d" % m.count())
    check(m.get("wpn_ak74_pso") is None and m.entry_for("wpn_ak74_pso") is not None
          and same(m.entry_for("wpn_ak74_pso"), m.get("wpn_ak74")),
          "a scoped combination is not listed, and counts as its gun")
    check(secs("pistols") == ["wpn_fort", "wpn_pm", "wpn_pm_pm_kit", "wpn_aps", "wpn_usp_45"]
          and names("pistols") == ["Fort-17", "PM", "PM Tactical", "Stechkin APS", "USP"],
          "pistols by name, not by section: %s %s" % (secs("pistols"), names("pistols")))
    check(secs("launchers") == ["wpn_rpg7"], "a grenade is not a launcher: %s" % secs("launchers"))
    check(secs("melee") == ["wpn_knife"], "a WP_KNIFE class is melee, a knife's attack animation is no gun: %s" % secs("melee"))
    check(not {"wpn_no_name", "wpn_no_icon", "wpn_untranslated"} & set(secs("smgs")),
          "no name, no icon or an untranslated name: not listed: %s" % secs("smgs"))
    check(m.get("mp_wpn_ak74") is None and m.get("wpn_addon_scope") is None and m.get("animation_hit_wpn_knife") is None,
          "multiplayer, attack animations and leftovers skipped")

    # guns that share a name: one model, and its variants
    fort = m.variant_of("wpn_fort17")
    check(fort is not None and fort.sec == "wpn_fort" and fort.name == "Fort-17"
          and list(fort.members.values()) == ["wpn_fort", "wpn_fort17", "wpn_fort_kit2"]
          and same(m.variant_for("wpn_fort17"), fort)
          and vnames(m.get("wpn_fort")) == ["Fort-17"],
          "guns of one name that play the same are one variant, named by the shortest section: %r"
          % ([fort.sec, fort.name, list(fort.members.values())] if fort is not None else None,))
    mp5 = m.get("wpn_mp5")
    check(names("smgs") == ["MP5", "MP5 Frasier", "Upgr"] and vnames(mp5) == ["MP5 (20 rds)", "MP5 (30 rds)"] and same(m.get("wpn_mp5_kurtz"), mp5),
          "a magazine pair: one model, its variants by name: %s %s" % (names("smgs"), vnames(mp5)))
    check(vnames(m.get("wpn_usp")) == ["USP (.45)", "USP (9x19)"],
          "a caliber pair, the caliber the word with a digit: %s" % vnames(m.get("wpn_usp")))
    twin_a, twin_b = m.variant_of("wpn_twin_a"), m.variant_of("wpn_twin_b")
    check(twin_a is not None and twin_b is not None and twin_a.name == "Twin [1]" and twin_b.name == "Twin [2]",
          "what no tag tells apart is numbered: %s" % [twin_a and twin_a.name, twin_b and twin_b.name])
    mount_a, mount_b = m.variant_of("wpn_mount_a"), m.variant_of("wpn_mount_b")
    check(mount_a is not None and mount_b is not None and mount_a.name == "Mount (suppressor mount)" and mount_b.name == "Mount",
          "a value one gun lacks is no difference: %s" % [mount_a and mount_a.name, mount_b and mount_b.name])
    check(m.get("wpn_pm").name == "PM" and vnames(m.get("wpn_pm")) == ["PM"], "a model of one variant has the plain name")
    check(m.entry_for("ammo_545") is None, "ammo is no weapon")

    # the values the card reads include the upgrades a gun ships with, and so do the tags
    check(m.params("wpn_ak74").rpm == 700, "a gun's values include the upgrades it ships with: rpm %s"
          % m.params("wpn_ak74").rpm)
    check(vnames(m.get("wpn_upg_a")) == ["Upgr (600 RPM)", "Upgr (700 RPM)"],
          "tags read the card's values, shipped upgrades in: %s" % vnames(m.get("wpn_upg_a")))

    # fully upgraded: per group the best upgrade or none; groups opened by an upgrade count, a
    # caliber conversion and a group the gun ships an upgrade in do not
    acc, rof = m.max_stat("wpn_ak74", "accuracy"), m.max_stat("wpn_ak74", "fire_rate")
    check(tuple(acc) == (70, 60), "accuracy fully upgraded, from as it ships: %s" % (tuple(acc),))
    check(tuple(rof) == (780, 700), "fire rate fully upgraded, through a group an upgrade opens: %s" % (tuple(rof),))
    check(m.max_stat("wpn_ak74", "damage") is None and m.max_stat("wpn_ak74", "max_range") is None,
          "no maximum for a stat the formulas here do not cover")

    # what fits, and what a gun is made of
    att = m.attachments("wpn_ak74")
    fits = ([x.name for x in att.scopes.values()], [x.name for x in att.lasers.values()],
            [(x.name, x.makes) for x in att.kits.values()], [x.name for x in att.suppressors.values()],
            [(x.name, list(x.ammo.values())) for x in att.launchers.values()])
    check(fits == (["Kobra"], ["LAM"], [("Tactical Kit", "AK-74 Tactical")], ["PBS-1"], [("GP-25", ["VOG-25"])]),
          "scopes, laser modules, kits (named for the gun they make), suppressor, launcher with its grenades: %s"
          % (fits,))
    isg = m.attachments("wpn_isg")
    isg_fit = ([x.name for x in isg.scopes.values()], len(isg.lasers), isg.builtin.laser, att.builtin.laser)
    check(isg_fit == (["Kobra"], 0, True, False),
          "a gun with its own laser: its combinations carry the laser, so a scope stays a scope, and the "
          "laser is built in: %s" % (isg_fit,))
    kurtz = [(x.name, x.makes) for x in m.attachments("wpn_mp5").kits.values()]
    check(kurtz == [("MP5K kit", "MP5 (20 rds)")], "a kit that makes a variant in the catalog names it: %s" % kurtz)
    pm_sil = [(x.name, x.upgrade) for x in m.attachments("wpn_pm").suppressors.values()]
    mp5_gl = [(x.name, x.upgrade, list(x.ammo.values())) for x in m.attachments("wpn_mp5").launchers.values()]
    check(pm_sil == [("PBS-1", True)] and mp5_gl == [("GP-25", True, ["VOG-25"])],
          "a suppressor or launcher an upgrade mounts, marked so: %s %s" % (pm_sil, mp5_gl))
    check([x.upgrade for x in att.suppressors.values()] == [None],
          "the gun's own suppressor is not marked: %s" % [x.upgrade for x in att.suppressors.values()])
    opts = m.upgrade_options("wpn_ak74")
    cal = [list(c.values()) for c in opts.calibres.values()]
    check(cal == [["9x19 FMJ"]] and list(opts.fire_modes.values()) == ["1 / 3 / A"],
          "an upgrade's other caliber (its ammo) and fire modes: %s %s" % (cal, list(opts.fire_modes.values())))
    mags = [(x.name, x.rounds) for x in m.mags("wpn_ak74").values()]
    check(mags == [("AK-74 Magazine", 30), ("AK-74 Drum", 60)] and len(m.mags("wpn_pm")) == 0,
          "the magazines of a gun's group, fewest rounds first, unknown ones left out; none for a gun without: %s"
          % mags)
    binder, lua.globals().magazine_binder = lua.globals().magazine_binder, None
    try:
        none = len(m.mags("wpn_ak74"))
    except Exception as err:  # the guard is gone
        none = "error: %s" % str(err)[:60]
    lua.globals().magazine_binder = binder
    check(none == 0, "no magazines while Mags Redux does not run: %s" % none)
    gets = [(x.name, x.cost) for x in m.nimble("wpn_mp5").gets.values()]
    frm = [(list(x.names.values()), x.cost) for x in m.nimble("wpn_mp5_nimble")["from"].values()]
    check(gets == [("MP5 Frasier", 65000)] and len(m.nimble("wpn_mp5_kurtz").gets) == 0,
          "what Nimble gives for a gun, not for another variant of its name: %s" % gets)
    check(frm == [(["MP5 (30 rds)"], 65000)], "what Nimble takes for his gun, guns not in the list left out: %s" % frm)
    nimble, lua.globals().NimbleTrade = lua.globals().NimbleTrade, None
    try:
        none = len(m.nimble("wpn_mp5").gets)
    except Exception as err:  # the guard is gone
        none = "error: %s" % str(err)[:60]
    lua.globals().NimbleTrade = nimble
    check(none == 0, "nothing from Nimble without his script: %s" % none)

    # where a gun turns up: the fighters that carry it, the likeliest first, ranks lowest first
    def carriers(sec):
        return [(c.faction, list(c.ranks.values()), c.special, round(c.best, 3)) for c in m.carriers(sec).values()]
    ak = carriers("wpn_ak74")
    check(ak == [("stalker", ["novice", "trainee", "legend"], None, 0.6), ("army", ["veteran"], None, 0.25)],
          "fighters that carry a gun: its share of a slot's weight (a missing gun left out), the ranks with their "
          "own loadout; a sniper's loadout under his faction and rank: %s" % ak)
    mp5c = carriers("wpn_mp5_kurtz")
    check(mp5c == [("isg", [], True, 1.0), ("stalker", ["novice", "trainee", "legend"], None, 0.4)],
          "a model's variants count together (a line without a weight weighs 10); a squad without a rank is "
          "special; the likeliest first: %s" % mp5c)
    toz = carriers("wpn_toz34")
    check(toz == [("stalker", ["experienced", "professional", "veteran", "expert", "master"], None, 1.0),
                  ("army", ["veteran"], None, 0.75)],
          "ranks without a loadout of their own take the faction's: %s" % toz)
    pm = carriers("wpn_pm")
    check(len(pm) == 13 and pm[0] == ("stalker", ["novice"], None, 1.0)
          and all(c[1] == list(m.RANKS.values()) for c in pm[1:]) and [c[0] for c in pm] == FACTIONS,
          "a faction without loadouts takes the default; ties in faction order: %s" % pm[:3])
    check(carriers("wpn_aps") == [], "a gun weighted 0 is carried by nobody: %s" % carriers("wpn_aps"))

    # stashes: the levels whose stashes most often draw the model's tiers
    lv = lambda sec: (None if m.stashes(sec) is None else list(m.stashes(sec).values()))
    check(lv("wpn_ak74_pso") == ["l03_agroprom", "l08_yantar", "l02_garbage"],
          "the levels that most often draw a model's tiers (a scoped copy's too, its tier rounded up), best "
          "first, three at most, a level marked stashes skip left out: %s" % lv("wpn_ak74_pso"))
    check(lv("wpn_rpg7") == ["l02_garbage", "l01_escape"], "a kind only rare stashes hold: %s" % lv("wpn_rpg7"))
    never = [lv(s) for s in ("wpn_toz34", "wpn_mp5", "wpn_aps", "wpn_knife")]
    check(never == [None] * 4, "never: a tier no roll beats, a kind in no table, a gun too cheap, a gun not in "
          "the list: %s" % never)
    check(lv("wpn_pm") is None, "not at an economy that bars it: %s" % lv("wpn_pm"))
    g = lua.globals()
    g.ECO = 1
    check(lv("wpn_pm") == ["l01_escape"], "at another economy it is: %s" % lv("wpn_pm"))
    g.ECO = 2
    tm = g.treasure_manager
    keep, tm.set_random_stash = tm.set_random_stash, lua.eval("function() return nil end")
    check(lv("wpn_ak74") == [], "in stashes, no levels named, when the level lists cannot be read: %s" % lv("wpn_ak74"))
    tm.set_random_stash = keep
    g.treasure_manager = None
    m.reset()
    try:
        none = lv("wpn_ak74")
    except Exception as err:  # the guard is gone
        none = "error: %s" % str(err)[:60]
    g.treasure_manager = tm
    m.reset()
    check(none is None, "nothing from stashes without the stash script: %s" % none)

    # a gun a kit makes of another model, and new-game kits
    made = [(x["from"], x.kit) for x in m.made_from("wpn_pm_copy_pm_kit").values()]
    check(made == [("PM", "PM kit")], "a gun a kit makes of another model, once: %s" % made)
    check(len(m.made_from("wpn_mp5_kurtz")) == 0 and len(m.made_from("wpn_fort")) == 0,
          "not a kit that makes a variant of the gun's own model")

    def kits(sec):
        return [(list(k.factions.values()), k.points, k.economies and list(k.economies.values()))
                for k in m.starting_kits(sec).values()]
    check(kits("wpn_pm") == [(["stalker", "bandit"], 90, None), (["dolg"], 120, None)],
          "new-game kits by price, factions in order: %s" % kits("wpn_pm"))
    check(kits("wpn_toz34") == [(["stalker", "bandit"], 650, [1])], "an economy lock: %s" % kits("wpn_toz34"))
    check(kits("wpn_knife") == [(FACTIONS, None, None)], "given free to every faction: %s" % kits("wpn_knife"))
    check(kits("wpn_mp5_kurtz") == [(["stalker", "bandit"], 400, None)],
          "the injector's items join the file's, factions in order: %s" % kits("wpn_mp5_kurtz"))
    check(kits("wpn_rpg7") == [(["stalker"], 300, [2, 3])] and kits("wpn_ak74") == [(FACTIONS, None, None)],
          "the injector's economies, and an item it gives free: %s %s" % (kits("wpn_rpg7"), kits("wpn_ak74")))
    check(kits("wpn_usp") == [], "not an item the injector takes out: %s" % kits("wpn_usp"))
    rk = lambda sec: [x.name for x in m.repair_kits(sec).values()]
    check(rk("wpn_ak74_pso") == ["Type C Cleaning Kit", "Type C Repair Kit"],
          "the kits of a gun's repair type (a combination's from its gun), each once: %s" % rk("wpn_ak74_pso"))
    check(rk("wpn_knife") == ["Sharpening Stones"] and rk("wpn_pm") == [] and rk("wpn_aps") == [],
          "a repair item that names the type; kits the game lacks, or no type, give none: %s %s %s"
          % (rk("wpn_knife"), rk("wpn_pm"), rk("wpn_aps")))
    wpo, g.zzzz_arti_jamming_repairs = g.zzzz_arti_jamming_repairs, None
    try:
        none = rk("wpn_ak74")
    except Exception as err:  # the guard is gone
        none = "error: %s" % str(err)[:60]
    g.zzzz_arti_jamming_repairs = wpo
    check(none == ["Type C Cleaning Kit"], "only _g's list without Weapon Parts Overhaul: %s" % none)
    # camos: as the camo wheel lists them, each name once, discovered or not, with the factions
    # that carry the gun and can drop it in that camo, likeliest first
    camo = lambda sec: [(c.name, c.icon, c.required, c.locked, list(c.factions.values())) for c in m.camos(sec).values()]
    ak_c = camo("wpn_ak74_pso")
    check(ak_c == [("Base", "black", False, False, []), ("Tan", "tan", True, True, ["army", "stalker"]),
                   ("Woodland", "woodland", True, False, [])],
          "a gun's camos: discovered or not, the factions that carry it and drop the camo, the likeliest "
          "first; another gun's camo left out: %s" % ak_c)
    check(camo("wpn_mp5_kurtz") == [("Base", "black", False, False, [])] and camo("wpn_pm") == [],
          "a camo of two sections of one model named once; none for a gun without: %s %s"
          % (camo("wpn_mp5_kurtz"), camo("wpn_pm")))
    cs, g.z_3dss_gamma_camo_system = g.z_3dss_gamma_camo_system, None
    try:
        none = camo("wpn_ak74")
    except Exception as err:  # the guard is gone
        none = "error: %s" % str(err)[:60]
    g.z_3dss_gamma_camo_system = cs
    check(none == [], "no camos without the camo system: %s" % none)
    looks = [(x.name, x.makes) for x in m.attachments("wpn_fort").kits.values()]
    check(looks == [("Fort kit", None)], "a kit that makes the same variant names nothing: %s" % looks)
    check(tuple(m.max_stat("wpn_toz34", "accuracy")) == (100, 50),
          "a percentage stops at 100: %s" % (tuple(m.max_stat("wpn_toz34", "accuracy")),))
    check([x.name for x in m.attachments("wpn_toz34").scopes.values()] == ["PU"], "a scope named through scopes_sect")
    check(m.attachments("wpn_rpg7").builtin.scope and not att.builtin.scope and not att.builtin.suppressor,
          "a built-in scope is told apart from an attachable one")
    check([x.name for x in m.parts("wpn_ak74_pso").values()] == ["Barrel", "Bolt"],
          "parts of the gun a combination was made from, unknown parts left out: %s"
          % [x.name for x in m.parts("wpn_ak74_pso").values()])
    check(list(m.ammo_names("wpn_ak74").values()) == ["5.45 FMJ", "5.45x39 AP"], "ammo names, short first, worn rounds left out, each once")
    check(m.fire_modes("wpn_ak74") == "1 / A" and m.fire_modes("wpn_pm") == "1", "fire modes")
    check(m.has_stat_card("wpn_ak74") and m.has_stat_card("wpn_pm") and not m.has_stat_card("wpn_knife"),
          "a stat card for a gun, none for a knife (fake ammo), as in the inventory")
    check(m.description("wpn_ak74") == "A rifle." and m.description("wpn_pm") is None, "descriptions")
    # 0.995 * 100 is 99.5 in doubles, so the game's round_100 shows 0.995 kg as 1
    check([m.kg(x) for x in (0.995, 3.3, 1, 1.094, 1.096)] == [1, 3.3, 1, 1.09, 1.1],
          "weights rounded as the inventory shows them: %s" % [m.kg(x) for x in (0.995, 3.3, 1, 1.094, 1.096)])

    rows = [(r.stat, r.gr.value_functor and r.gr.value_functor[2]) for r in m.stat_rows(False).values()]
    check([s for s, _ in rows] == ["accuracy", "fire_rate", "ammo_mag_size", "speed", "reliability", "recoil"],
          "stat rows in the card's order: %s" % [s for s, _ in rows])
    alt = dict(rows)
    check(alt["speed"] == "standin_bspeed" and alt["reliability"] == "standin_reliability"
          and alt["recoil"] == "standin_recoil" and alt["accuracy"] == "scale_100", "stand-ins only where needed")
    live = dict((r.stat, r.gr.value_functor and r.gr.value_functor[2]) for r in m.stat_rows(True).values())
    check(live["speed"] == "get_weapon_bspeed", "a live weapon keeps the card's own functions")
    check(abs(m.standin_bspeed(None, "wpn_ak74") - 900 * 1.1 * 0.70 / 1000) < 1e-9, "bullet speed as Momopate's")
    check(abs(m.standin_reliability(None, "wpn_ak74") - (1 - 0.0005 - 0.99)) < 1e-12, "reliability as Momopate's")
    want = (1 / 0.5) * (1 / (3 * 0.25 + 0.1)) * 100
    check(abs(m.standin_recoil(None, "wpn_ak74") - want) < 1e-9, "recoil as Momopate's: %s" % m.standin_recoil(None, "wpn_ak74"))
    check(m.standin_recoil(None, "wpn_pm") is None, "no recoil entry: no value")
    print("\n%d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
