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
                     fire_dispersion_base="0.6", rpm="600", upgrades="up_gr_a, up_gr_b, risk_up_gr_wpn_fire_rate",
                     installed_upgrades="up_b1",
                     scopes="kobra, lam, ak_kit, rk_kit, missing_scope", silencer_status="2", silencer_name="wpn_sil",
                     grenade_launcher_status="2", grenade_launcher_name="wpn_gl", grenade_class="ammo_vog, ammo_vog_bad"),
    "wpn_ak74_pso": dict(kind="w_rifle", inv_name="st_ak74", inv_grid_x="10", parent_section="wpn_ak74"),
    "wpn_pm": dict(kind="w_pistol", inv_name="st_pm", inv_grid_x="1", ammo_class="ammo_9x18", upgrades="up_gr_pm",
                   scopes="pm_kit, never_kit", repair_type="pistol"),
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
                      fire_dispersion_base="0.75", upgrades="up_gr_t", silencer_status="2", silencer_name="toz_sil"),
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
    # R.I.S.K.: fire rate (+12, +240 and -240 RPM, and an element of no strength), weight (-2, then
    # +2 and +1 kg), damage (+2, +40, -40 %), recoil (a gun without a recoil profile gets none)
    "risk_up_gr_wpn_fire_rate": dict(elements="risk_up_fr_a, risk_up_fr_b, risk_up_fr_c, risk_up_fr_zero"),
    "risk_up_fr_a": dict(section="risk_sect_fr_a"), "risk_sect_fr_a": dict(value="+3", rpm="+12"),
    "risk_up_fr_b": dict(section="risk_sect_fr_b"), "risk_sect_fr_b": dict(value="+60", rpm="+240"),
    "risk_up_fr_c": dict(section="risk_sect_fr_c"), "risk_sect_fr_c": dict(value="-60", rpm="-240"),
    "risk_up_fr_zero": dict(section="risk_sect_fr_zero"), "risk_sect_fr_zero": dict(value="0", rpm="-600"),
    "risk_up_gr_wpn_weight": dict(elements="risk_up_w_a, risk_up_w_b, risk_up_w_c"),
    "risk_up_w_a": dict(section="risk_sect_w_a"), "risk_sect_w_a": dict(value="+50", inv_weight="-2.0"),
    "risk_up_w_b": dict(section="risk_sect_w_b"), "risk_sect_w_b": dict(value="-50", inv_weight="+2.0"),
    "risk_up_w_c": dict(section="risk_sect_w_c"), "risk_sect_w_c": dict(value="-25", inv_weight="+1.0"),
    "risk_up_gr_wpn_damage": dict(elements="risk_up_d_a, risk_up_d_b, risk_up_d_c"),
    "risk_up_d_a": dict(section="risk_sect_d_a"), "risk_sect_d_a": dict(value="+2"),
    "risk_up_d_b": dict(section="risk_sect_d_b"), "risk_sect_d_b": dict(value="+40"),
    "risk_up_d_c": dict(section="risk_sect_d_c"), "risk_sect_d_c": dict(value="-40"),
    "risk_up_gr_wpn_recoil": dict(elements="risk_up_r_a"),
    "risk_up_r_a": dict(section="risk_sect_r_a"), "risk_sect_r_a": dict(value="+30", zoom_cam_dispersion="-0.1"),
    # armor. A jacket (light by its repair type) in two variants that differ in shock; its
    # upgrades: group a (a1 more psi, opens c; a2 more psi than a1 alone), c (c1 more psi), b
    # (b1 adds spine armor through a bones profile, burn, a belt slot, carry weight)
    "novice_outfit": dict(**{"class": "EQU_STLK"}, kind="o_light", repair_type="outfit_novice", inv_name="st_jacket",
                          inv_grid_x="1", bones_koeff_protection="prof_jacket", hit_fraction_actor="0.83",
                          burn_protection="0.4", shock_protection="0.1", radiation_protection="0.00275",
                          telepatic_protection="0", artefact_count="1", additional_inventory_weight="12",
                          inv_weight="5", upgrades="up_gr_j_a, up_gr_j_b"),
    "novice_outfit_b": dict(**{"class": "EQU_STLK"}, kind="o_light", repair_type="outfit_novice", inv_name="st_jacket",
                            inv_grid_x="1", bones_koeff_protection="prof_jacket", hit_fraction_actor="0.83",
                            burn_protection="0.4", shock_protection="0.2", radiation_protection="0.00275",
                            telepatic_protection="0", artefact_count="1", additional_inventory_weight="12",
                            inv_weight="5"),
    "prof_jacket": dict(bip01_spine="1, 0.0375", bip01_head="1, 0.0"),
    "up_gr_j_a": dict(elements="up_j_a1, up_j_a2"),
    "up_j_a1": dict(section="up_sect_j_a1", property="prop_psy", effects="up_gr_j_c"),
    "up_sect_j_a1": dict(telepatic_protection="0.06"),
    "up_j_a2": dict(section="up_sect_j_a2", property="prop_psy"),
    "up_sect_j_a2": dict(telepatic_protection="0.09"),
    "up_gr_j_c": dict(elements="up_j_c1"),
    "up_j_c1": dict(section="up_sect_j_c1", property="prop_psy"),
    "up_sect_j_c1": dict(telepatic_protection="0.05"),
    "up_gr_j_b": dict(elements="up_j_b1"),
    "up_j_b1": dict(section="up_sect_j_b1", property="prop_armor"),
    "up_sect_j_b1": dict(bones_koeff_protection_add="prof_add", burn_protection="0.2", artefact_count="1",
                         additional_inventory_weight="10"),
    "prof_add": dict(bip01_spine="1, 0.03"),
    # a helmet: bullets meet its head armor; it ships an upgrade (radiation, burn) in a group
    # whose other upgrade (more radiation, and opening more still) it can no longer take
    "helm_x": dict(**{"class": "E_HLMET"}, kind="o_helmet", repair_type="helmet_light", inv_name="st_helm",
                   inv_grid_x="1", bones_koeff_protection="prof_helm", hit_fraction_actor="0.7",
                   burn_protection="0.013", radiation_protection="0.002", installed_upgrades="up_h_a1",
                   upgrades="up_gr_h_a", inv_weight="2"),
    "prof_helm": dict(bip01_spine="1, 0.0", bip01_head="1, 0.30"),
    "up_gr_h_a": dict(elements="up_h_a1, up_h_a2"),
    "up_h_a1": dict(section="up_sect_h_a1", property="prop_radio"),
    "up_sect_h_a1": dict(radiation_protection="0.0055", burn_protection="0.1"),
    "up_h_a2": dict(section="up_sect_h_a2", property="prop_radio", effects="up_gr_h_b"),
    "up_gr_h_b": dict(elements="up_h_b1"),
    "up_h_b1": dict(section="up_sect_h_b1", property="prop_radio"),
    "up_sect_h_b1": dict(radiation_protection="0.03"),
    "up_sect_h_a2": dict(radiation_protection="0.02"),
    # an exoskeleton (heavy by kind, exo by repair type), a scientific suit (medium), a heavy
    # suit without a repair type (by its kind), whose profile has only a default line; a
    # template without a kind, a multiplayer suit, a helmet template without an icon
    "exo_z": dict(**{"class": "E_STLK"}, kind="o_heavy", repair_type="outfit_exo", inv_name="st_exo", inv_grid_x="1",
                  bones_koeff_protection="prof_jacket"),
    "sci_w": dict(**{"class": "EQU_STLK"}, kind="o_sci", repair_type="outfit_medium", inv_name="st_seva",
                  inv_grid_x="1"),
    "heavy_v": dict(**{"class": "EQU_STLK"}, kind="o_heavy", inv_name="st_heavy", inv_grid_x="1",
                    bones_koeff_protection="prof_default"),
    "prof_default": dict(default="1, 0.5"),
    "outfit_base": dict(**{"class": "E_STLK"}, repair_type="outfit_medium", inv_name="st_seva", inv_grid_x="1"),
    "mp_exo_outfit": dict(**{"class": "E_STLK"}, kind="o_heavy", inv_name="st_exo", inv_grid_x="1"),
    "tch_helmet": dict(**{"class": "E_HLMET"}, kind="o_helmet", inv_name="st_helm"),
    # who wears them: spawn sections (their factions), the census below, a monster's section
    "sim_jacket_1": dict(community="stalker"), "sim_jacket_2": dict(community="stalker"),
    "sim_story": dict(community="dolg"), "sim_monster": dict(community="tushkano"),
    "game_relations": dict(rating="novice, 3999, trainee, 5999, experienced, 9999, professional, 15999, veteran, "
                                  "23999, expert, 34999, master, 49999, legend"),
    # what else turns gear up: a knife traders sell; a pistol a trader stocks but hides, one it
    # stocks none of, one only a trade config nobody uses stocks; a story character's rifle; knives
    # in bodies' lists (one a body may hold, one the count list keeps at none, one it does not
    # name); task rewards and a spy squad's rifle; the pump station guards' rifle; Homestead's;
    # a story gift; a crafted helmet; a stash rifle with a suppressor mount; a kit that makes the
    # AK-74 a gun of its own, which no fighter's kit roll leaves as an item; a PM kit nothing
    # gives; Nimble's USP, for USPs nothing gives; a rifle and a helmet nothing gives at all
    "wpn_knife2": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife2", inv_grid_x="6"),
    "wpn_knife7": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife7", inv_grid_x="6"),
    "wpn_knife8": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife8", inv_grid_x="6"),
    "wpn_knife9": dict(**{"class": "WP_KNIFE"}, inv_name="st_knife9", inv_grid_x="6"),
    "wpn_hidden": dict(kind="w_pistol", inv_name="st_hidden", inv_grid_x="1"),
    "wpn_zero": dict(kind="w_pistol", inv_name="st_zero", inv_grid_x="1"),
    "wpn_unused": dict(kind="w_pistol", inv_name="st_unused", inv_grid_x="1"),
    "wpn_story": dict(kind="w_rifle", inv_name="st_story", inv_grid_x="1"),
    "wpn_task": dict(kind="w_rifle", inv_name="st_task", inv_grid_x="1"),
    "wpn_task2": dict(kind="w_rifle", inv_name="st_task2", inv_grid_x="1"),
    "wpn_spy": dict(kind="w_rifle", inv_name="st_spy", inv_grid_x="1"),
    "wpn_guard": dict(kind="w_rifle", inv_name="st_guard", inv_grid_x="1"),
    "wpn_home": dict(kind="w_rifle", inv_name="st_home", inv_grid_x="1"),
    "wpn_abakan": dict(kind="w_rifle", inv_name="st_abakan", inv_grid_x="1"),
    "helm_crafted": dict(**{"class": "E_HLMET"}, kind="o_helmet", inv_name="st_helm_crafted", inv_grid_x="1"),
    "wpn_stash_sil": dict(kind="w_rifle", inv_name="st_stash_sil", inv_grid_x="1", silencer_status="2",
                          silencer_name="stash_sil", cost="5000"),
    "rk_kit": dict(inv_name="st_rk_kit"),
    "wpn_ak74_rk_kit": dict(kind="w_rifle", inv_name="st_ak74_rk", inv_grid_x="1", parent_section="wpn_ak74_rk_kit"),
    "never_kit": dict(inv_name="st_never_kit"),
    "wpn_pm_never_kit": dict(kind="w_pistol", inv_name="st_pm_never", inv_grid_x="1", parent_section="wpn_pm_never_kit"),
    "wpn_usp_nimble": dict(kind="w_pistol", inv_name="st_usp_nimble", inv_grid_x="1"),
    "wpn_nothing": dict(kind="w_rifle", inv_name="st_nothing", inv_grid_x="1"),
    "helm_never": dict(**{"class": "E_HLMET"}, kind="o_helmet", inv_name="st_helm_never", inv_grid_x="1"),
}
SECTIONS["novice_outfit"]["cost"] = "7290"
SECTIONS["exo_z"]["cost"] = "176027"
SECTIONS["helm_x"]["cost"] = "30000"
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
        "st_petrenko": "Petrenko", "st_jacket": "Jacket", "st_helm": "Helmet",
        "st_knife2": "Scout Knife", "st_knife7": "Monolith Blade", "st_knife8": "Kukri", "st_knife9": "Tomahawk",
        "st_hidden": "Hidden Pistol", "st_zero": "Zero Pistol", "st_unused": "Unused Pistol", "st_story": "Story Rifle",
        "st_task": "Task Rifle", "st_task2": "Task Rifle Two", "st_spy": "Spy Rifle", "st_guard": "Guard Rifle",
        "st_home": "Home Rifle", "st_abakan": "AN-94", "st_helm_crafted": "Cloth Mask", "st_stash_sil": "Stash Rifle",
        "st_rk_kit": "RK kit", "st_ak74_rk": "AK-74 RK", "st_never_kit": "Never kit", "st_pm_never": "PM Never",
        "st_usp_nimble": "USP Nimble", "st_nothing": "Nothing Rifle", "st_helm_never": "Never Helmet",
        "st_strelok": "Strelok", "st_exo": "Exoskeleton", "st_seva": "SEVA", "st_heavy": "Heavy Suit",
        "ui_inv_outfit_fire_wound_protection": "%c[0,255,255,255]Ballistic Res", "ui_inv_ap_res": "BR Class",
        "ui_inv_outfit_burn_protection": "Burn Res", "ui_inv_outfit_shock_protection": "Shock Res",
        "ui_inv_outfit_radiation_protection": "Radiation Res", "ui_inv_outfit_telepatic_protection": "Psy Res",
        "ui_inv_outfit_artefact_count": "Belt Slots", "ui_inv_outfit_additional_weight": "Weight Carried",
        "ui_inv_outfit_speed": "Movespeed", "st_perc": "%", "st_kg": "kg",
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
    # scopes no NPC gun gets
    "scope_blacklist": [("lam", "true")],
}
# stashes: the PM barred at economy 2, the APS too cheap, the TOZ at a tier no roll beats, the
# MP5's kind in no table, the RPG-7 in rare stashes only, the AK-74's scoped copy a tier up
TREASURE = {
    "possible_items": [("wpn_ak74", ""), ("wpn_ak74_kobra", ""), ("wpn_pm", "2"), ("wpn_toz34", ""), ("wpn_mp5", ""),
                       ("wpn_rpg7", ""), ("wpn_aps", ""), ("novice_outfit", ""), ("wpn_stash_sil", "")],
    "kind_tier_effect_common": [("w_rifle", "7, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1"),
                                ("w_pistol", "5, 600, 1,1, 0.8,1, 0.75,1, 0.3,1, 0.01,1"),
                                ("w_shotgun", "7, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1")],
    "kind_tier_effect_rare": [("w_rifle", "10, 600, 1,1, 0.8,1, 0.75,1, 0.6,1, 0.05,1"),
                              ("w_explosive", "5, 500, 1,1, 0.8,1.25, 0.75,1.5, 0.6,1.5, 0.5,1.5")],
}
TIERS = {"wpn_ak74": [("tier", "3")], "wpn_ak74_kobra": [("tier", "3.6")], "wpn_pm": [("tier", "1")],
         "wpn_toz34": [("tier", "5")], "wpn_mp5": [("tier", "2")], "wpn_rpg7": [("tier", "2")], "wpn_aps": [("tier", "1")],
         "wpn_stash_sil": [("tier", "2")]}
# new-game kits: a knife for everyone, the PM at two prices, the TOZ on the easiest economy only,
# an MP5 that the injector adds for Loners, a USP it takes out, a gun the game lacks
KITS = {f + "_loadout": [("wpn_knife", "false,1,0")] for f in FACTIONS}
KITS["stalker_loadout"] += [("wpn_pm", "true,1,90"), ("wpn_toz34", "true,1,650,1"), ("wpn_usp_45", "true,1,200"),
                            ("wpn_gone", "true,1,5")]
KITS["bandit_loadout"] += [("wpn_pm", "true,1,90"), ("wpn_toz34", "true,1,650,1"), ("wpn_mp5", "true,1,400")]
KITS["dolg_loadout"] += [("wpn_pm", "true,1,120")]
SPEED = {"speed": [("novice_outfit", "1.1"), ("novice_outfit_b", "1.1")]}
# the census (tools/census.py): per spawn section its characters per rank and those wearing each
# visual; two visuals of one section drop the jacket's two variants, one visual drops both
CENSUS = {
    "sim_jacket_1": [("characters", "novice:4, trainee:3"), ("vis_jacket", "novice:2, trainee:2"),
                     ("vis_jacket_b", "novice:1"), ("vis_exo", "novice:1"), ("vis_twice", "trainee:1")],
    "sim_jacket_2": [("characters", "novice:4"), ("vis_jacket", "novice:1"), ("vis_none", "novice:3")],
    "sim_story": [("characters", "special:1"), ("vis_helm", "special:1")],
    # the trade configs some NPC uses (not trade_unused), and a story character's gear
    "arsenal_trade": [("trade_a", "1")],
    "arsenal_supplies": [("wpn_story", "st_strelok, GENERATE_NAME_x")],
    # who offers the Armor Exchange's dialogs: Duty's a named trader, the Loners' a name with no
    # text (so nobody), the Military's nobody at all
    "arsenal_dialogs": [("armor_exchange_insider_duty", "st_petrenko"),
                        ("armor_exchange_insider_loner", "st_nobody")],
    "sim_monster": [("characters", "novice:1"), ("vis_jacket", "novice:1")],
}
# death_manager's table: a visual's suit and helmet; a visual that drops nothing
DEATH = {"outfit_by_visual": [("vis_jacket", "novice_outfit,helm_x"), ("vis_jacket_b", "novice_outfit_b"),
                              ("vis_exo", "exo_z"), ("vis_helm", ",helm_x"), ("vis_none", ""),
                              ("vis_twice", "novice_outfit,novice_outfit_b")],
         "outfit_drop_settings": [("cost_start", "25000"), ("rank_multiplier", "20")],
         # bodies' item lists, and how many of an item a body may hold
         "item_count": [("wpn_knife7", "1, 1"), ("wpn_knife8", "0, 0")],
         "monolith_master": [("wpn_knife7", "0.01"), ("wpn_knife8", "0.5")],
         "stalker": [("wpn_knife9", "0.3")]}
# a trader: what its sell filter hides (no value), its supplies (count, chance), by goodwill
TRADE_A = {"trader": [("buy_supplies", "{+heavy_pockets} supplies_2, supplies_1"), ("sell_condition", "trade_sell")],
           "trade_sell": [("wpn_hidden", ""), ("wpn_knife2", "1, 1")],
           "supplies_1": [("wpn_knife2", "1, 1"), ("wpn_hidden", "1, 1"), ("wpn_zero", "0, 1"), ("pm_kit", "1, 0.5")],
           "supplies_2": [("kobra", "2, 0.3")]}
TRADE_UNUSED = {"trader": [("buy_supplies", "supplies_1")], "supplies_1": [("wpn_unused", "1, 1")]}
# task configs: an item reward, a random one (one choice a section the game lacks), a spy squad's gun
TASKS = {"task_a": [("on_complete", "%=reward_item(wpn_task) =give_money(100)%")],
         "task_b": [("on_complete", "{+done} %=reward_random_item(helm_reward:wpn_task2)%")],
         "task_spy": [("task_loadout_other", "wpn_spy")]}
CRAFT = {"1": [("title", "st_craft"), ("x_helm_crafted", "1, recipe_basic_0, prt_o_fabrics_1,5")]}
FILES = {r"items\settings\npc_loadouts\npc_loadouts.ltx": NPC, r"items\settings\new_game_loadouts.ltx": KITS,
         "treasure": TREASURE, "tiers": TIERS, r"items\settings\outfit_speed.ltx": SPEED,
         r"plugins\arsenal_census.ltx": CENSUS, "death": DEATH, r"items\trade\trade_a.ltx": TRADE_A,
         r"items\trade\trade_unused.ltx": TRADE_UNUSED, "tasks": TASKS, "craft": CRAFT}

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
    function o:section_for_each(fn)
        local names = {}
        for k in pairs(tbl) do names[#names + 1] = k end
        table.sort(names)
        for _, k in ipairs(names) do if fn(k) then return end end
    end
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
game_difficulties = { get_eco_factor = function(k)
    if k == "outfit_drops" then return OUTFIT_DROPS end
    return k == "type" and ECO or nil
end }
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
itms_manager = { ini_parts = ini(P), ini_death = lini(F.death), ini_craft = lini(F.craft) }
task_manager = { task_ini = lini(F.tasks) }
-- the pump station guards' guns ({ gun, ammo }) and Homestead's stash loot, as locals of the
-- functions that use them
local _GUNS_FOR_GUARDS = { { "wpn_guard", "ammo_9x18" } }
tasks_pump_station_defense = {}
function tasks_pump_station_defense.spawn_and_set() return _GUNS_FOR_GUARDS end
local gamma_yellow_loot = { [1] = { "wpn_home", "lead_box" } }
stalker_camp_builder = {}
function stalker_camp_builder.generate_gamma_stash_loot() return gamma_yellow_loot end
-- GAMMA's drop chances (its MCM values), and death_manager's rare suits: the exoskeleton
local DROP = { outfit_light_chance = 70, outfit_medium_chance = 50, outfit_exo_chance = 10, helmet_light_chance = 60 }
outfit_drop_mcm = { get_config = function(k) return DROP[k] end }
death_manager = { rare_armors = { exo_z = true } }
-- the Armor Exchange's tables: Duty gives the SEVA for the jacket or the exoskeleton (or a suit
-- the game lacks), the exoskeleton for the SEVA; the Military and the Loners give suits too
grok_armor_convert = {
    dolg_medium = { cost = 10000, reward = "sci_w", novice_outfit = true, exo_z = true, gone_suit = true },
    dolg_exo = { cost = 45000, reward = "exo_z", sci_w = true },
    army_medium = { cost = 1, reward = "heavy_v", novice_outfit_b = true },
    loner_light = { cost = 1, reward = "heavy_v", novice_outfit = true },
}
-- Nimble's script, with the one price these tests use
NimbleTrade = { MP5Cost = 65000, USPCost = 1000 }
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
-- the outfit card as GAMMA sets it up (ish_item_stats), a few of its rows
local function row(index, name, functor, magnitude, unit, sign)
    return { index = index, name = name, value_functor = functor, magnitude = magnitude or 1, unit = unit or "st_perc",
             sign = sign ~= false, typ = "float" }
end
utils_ui.stats_table.outfit = {
    fire_wound_protection = row(10, "ui_inv_outfit_fire_wound_protection", { "grok_actor_damage_balancer", "get_outfit_value", "FireWound" }),
    apres_modifier = row(11, "ui_inv_ap_res", { "grok_actor_damage_balancer", "get_outfit_ap_res" }, 100, ""),
    burn_protection = row(20, "ui_inv_outfit_burn_protection", { "grok_actor_damage_balancer", "get_outfit_value", "Burn" }),
    shock_protection = row(30, "ui_inv_outfit_shock_protection", { "grok_actor_damage_balancer", "get_outfit_value", "Shock" }),
    radiation_protection = row(50, "ui_inv_outfit_radiation_protection", { "utils_item", "get_outfit_protection", "Radiation" },
        (100 / 0.055) / 1.82143),
    telepatic_protection = row(60, "ui_inv_outfit_telepatic_protection", { "grok_actor_damage_balancer", "get_outfit_value", "Telepatic" }),
    artefact_count = row(100, "ui_inv_outfit_artefact_count", { "utils_item", "get_outfit_belt_size" }, 1, "", false),
    additional_inventory_weight = row(110, "ui_inv_outfit_additional_weight",
        { "utils_item", "get_outfit_property", "additional_inventory_weight" }, 1, "st_kg"),
    speed_modifier = row(120, "ui_inv_outfit_speed", { "outfit_speed_mcm", "get_outfit_speed" }, 100, "%", false),
}
-- grok_actor_damage_balancer: get_adb_constants sets its adjuster and ini key; its card
-- functions need a live suit (without one they give the wrong values)
local ADB = { FireWound = { 0.80, "fire_wound_protection" }, Burn = { 1.00, "burn_protection" },
    Shock = { 0.102, "shock_protection" }, Telepatic = { 1.70, "telepatic_protection" } }
grok_actor_damage_balancer = {}
function grok_actor_damage_balancer.get_adb_constants(name)
    local a = ADB[name]
    grok_actor_damage_balancer.adjuster = a and a[1]
    grok_actor_damage_balancer.defense = a and a[2]
end
function grok_actor_damage_balancer.get_outfit_value(obj, sec, name) return 999 end
function grok_actor_damage_balancer.get_outfit_ap_res(obj) return nil end
outfit_speed_mcm = { get_outfit_speed = function(obj, sec) return 1 end }
-- utils_item's section paths: radiation and belt slots from the section; the carry weight
-- falls through to get_param
function utils_item.get_outfit_protection(obj, sec, name, def)
    return name == "Radiation" and tonumber(S[sec].radiation_protection or 0) or (def or 0)
end
function utils_item.get_outfit_belt_size(obj, sec) return tonumber(S[sec].artefact_count or 0) end
function utils_item.get_outfit_property(obj, sec, name, def) return nil end
-- utils_ui's: the row's function (or the section's value with its shipped upgrades), times the
-- magnitude, rounded up, with a sign and the unit; nil for zero
function utils_ui.get_stats_string_value(obj, sec, gr, stat)
    local f = gr.value_functor
    local value = f and _G[f[1]] and _G[f[1]][f[2]] and _G[f[1]][f[2]](obj, sec, unpack(f, 3))
    if not value then value = utils_item.get_param(sec, nil, stat, gr.typ or "float", true) end
    if not value or value == 0 then return nil end
    local v = math.ceil(value * gr.magnitude)
    local unit = gr.unit and gr.unit ~= "" and game.translate_string(gr.unit) or ""
    return ((gr.sign and v > 0) and "+" or "") .. v .. " " .. unit, v < 0
end
"""

MUTANTS = {
    "variants": ("if parent and parent ~= sec then return nil end", "-- variants kept"),
    "armor_f32": ("        p[k] = f32(ini_sys:r_float_ex(sec, k) or 0)", "        p[k] = ini_sys:r_float_ex(sec, k) or 0"),
    "armor_light_burn": ("        v = p.light_burn", "        v = p.burn_protection"),
    "armor_head": ('p = { sec = sec, bone = is_helmet(sec) and "bip01_head" or "bip01_spine" }',
                   'p = { sec = sec, bone = "bip01_spine" }'),
    "armor_default_bone": ('ini_sys:r_string_ex(profile, bone) or ini_sys:r_string_ex(profile, "default")',
                           "ini_sys:r_string_ex(profile, bone)"),
    "armor_path_opens": ("                    sum = sum + n\n", ""),
    "armor_path_fixed": ("(not fixed or el == fixed)", "true"),
    "armor_installed": ("        if ps and ini_sys:section_exist(ps) then add_upgrade(p, ps) end", "        -- shipped upgrades left out"),
    "armor_by_repair": ('return is_helmet(sec) and "helmets" or ARMOR_REPAIR[ini_sys:r_string_ex(sec, "repair_type") or ""]\n            or ARMOR_KIND[kind]',
                        'return is_helmet(sec) and "helmets" or ARMOR_KIND[kind]'),
    "armor_template": ("        if not (kind and ARMOR_KIND[kind]) then return nil end\n", ""),
    "armor_signature": ("    for _, k in ipairs(PROTECTIONS) do\n        t[#t + 1] = string.format(\"%.6g\", p[k])\n    end\n", ""),
    "armor_taggers": ("label(g.name, vars, ARMOR[g.cat] and ARMOR_TAGGERS or TAGGERS)", "label(g.name, vars, TAGGERS)"),
    "armor_ap_res": ('    return 1 - (ini_sys:r_float_ex(sec, "hit_fraction_actor") or 1)', "    return nil"),
    "armor_speed": ("    return speeds[sec] or 1", "    return 1"),
    "armor_risk": ("    if is_armor(sec) then return out end\n    local p = params(sec)", "    local p = params(sec)"),
    "armor_card": ("    if is_armor(sec) then return true end\n", ""),
    "armor_functor_args": ('g.value_functor = { "arsenal_data", alt, unpack(f, 3) }', 'g.value_functor = { "arsenal_data", alt }'),
    "armor_radiation": ('    get_outfit_protection = "standin_outfit_protection",\n', ""),
    "worn_sum": ("wearing[e][f][r] = (wearing[e][f][r] or 0) + n", "wearing[e][f][r] = n"),
    "worn_once": ("if e and not seen[e] then", "if e then"),
    "worn_faction": ("        if not (f and FACTION_AT[f]) then return end\n        total[f] = total[f] or {}",
                     "        total[f] = total[f] or {}"),
    "drop_rare": ("if type(rare) == \"table\" and rare[sec] then chance = chance * 0.15 end", "-- no rare roll"),
    "drop_mode": ("    if mode ~= 2 and mode ~= 3 then return { off = true } end\n", ""),
    "drop_gate": ("rank = need > 0 and math.ceil(need) or nil", "rank = nil"),
    "drop_novice": ('rt = (rt == "outfit_novice" and "outfit_light") or (rt == "outfit" and "outfit_medium") or rt', "rt = rt"),
    "rank_bound": ("if not top or value < top then return r[i] end", "if not top or value <= top then return r[i] end"),
    "exchange_givers": ("for _, name in ipairs(#who > 0 and x.tables or {}) do", "for _, name in ipairs(x.tables) do"),
    "up_sell_filter": ("if (tonumber(v[1]) or 0) > 0 and (tonumber(v[2]) or 0) > 0 and not hidden[x.k] then",
                       "if (tonumber(v[1]) or 0) > 0 and (tonumber(v[2]) or 0) > 0 then"),
    "up_count": ("if (tonumber(v[1]) or 0) > 0 and (tonumber(v[2]) or 0) > 0 and not hidden[x.k] then",
                 "if (tonumber(v[2]) or 0) > 0 and not hidden[x.k] then"),
    "up_story": ('mark_up(l.k, "story", n ~= "" and n or nil)', "-- no story gear"),
    "up_corpse_count": ("if (tonumber(fields(x.v, \",\")[1]) or 0) > 0 and (most[x.k] or 0) >= 1 then",
                        "if (tonumber(fields(x.v, \",\")[1]) or 0) > 0 then"),
    "up_random_reward": ('"reward_item%(([^%)]*)%)", "reward_random_item%(([^%)]*)%)"', '"reward_item%(([^%)]*)%)"'),
    "up_spy": ('                    mark_up((x.v or ""):match("^%s*([%w_%.%-]+)"), "task")\n', ""),
    "up_guards": ('if type(g) == "table" and type(g[1]) == "string" then mark_up(g[1], "task") end', "-- no guards"),
    "up_home": ('if type(s) == "string" then mark_up(s, "homestead") end', "-- no Homestead"),
    "up_gifts": ('        mark_up(g, "gift")\n', ""),
    "up_craft": ('if item then mark_up(item, "craft") end', "-- no crafting"),
    "addon_bits": ("local n = bit.band(bits, m[1]) ~= 0 and status(s, m[2]) == 2", "local n = status(s, m[2]) == 2"),
    "addon_blacklist": ("if not black[k] and not (per_gun[s] and per_gun[s][k]) and ini_sys:section_exist(combo) then",
                        "if ini_sys:section_exist(combo) then"),
    "addon_kit_stays": ("                    if p and p ~= combo then", "                    if true then"),
    "addon_stash": ("        mounts(s, 7)\n", ""),
    "reach_kit": ("local m = addon_ok[k] and variant_of(s .. \"_\" .. k)", "local m = variant_of(s .. \"_\" .. k)"),
    "reach_nimble": ("if m and reach[m] then add(entry_for(t.gives)) end", "if m then add(entry_for(t.gives)) end"),
    "reach_exchange": ("            if #givers(x.dialog) > 0 then\n", "            if true then\n"),
    "reach_drops_off": ("and not (armor_drop(e.sec) or {}).off", ""),
    "reach_rolled": ("        for combo, base in pairs(rolled) do", "        for combo, base in pairs({}) do"),
    "gear_turns_up": ("if r and next(r) and obtainable(e.sec) and not (src[2] and (armor_drop(e.sec) or {}).off) then",
                      "if r and next(r) then"),
    "gear_worn": ("    for _, src in ipairs({ { carried, false }, { worn, true } }) do", "    for _, src in ipairs({ { carried, false } }) do"),
    "special_carried": ("        if #c.ranks > 0 then return false end\n    end\n    for _, c in ipairs(ARMOR[e.cat]",
                        "    end\n    for _, c in ipairs(ARMOR[e.cat]"),
    "special_stash": ("    return stashes(e.sec) == nil\nend", "    return true\nend"),
    "kit_faction": ("            if k.faction == f then", "            if true then"),
    "exchange_exists": ("if v == true and ini_sys:section_exist(s) then", "if v == true then"),
    "exchange_model": ("if entry_for(s) == e then mine = true end", "if s == sec then mine = true end"),
    "grenades": ("not ini_sys:r_string_ex(sec, \"weapon_class\")", "false"),
    "mp": ("sec:find(\"^mp_\")", "false"),
    "untranslated": ("return (s ~= key) and s or nil", "return s"),
    "standin": ("gr = live and gr or standin_row(gr, standin)", "gr = gr"),
    "order": ("table.sort(by_cat[c], by_name)", "-- unsorted"),
    "speed": ("bs = bs * 0.70", "bs = bs * 0.75"),
    "worn": ('if not (r:find("_bad$") or r:find("_verybad$")) then', "if true then"),
    "dedupe": ("if n and not seen[n] then\n                seen[n] = true\n                out[#out + 1] = n",
               "if n then\n                seen[n] = true\n                out[#out + 1] = n"),
    "nimble_dedupe": ("if n and not seen[n] then\n                        seen[n] = true\n                        names",
                      "if n then\n                        seen[n] = true\n                        names"),
    "collapse": ("sg = okS and sg or sec", "sg = sec"),
    "shortest": ("table.sort(secs, shorter)", "table.sort(secs, function(a, b) return shorter(b, a) end)"),
    "tags": ("label(g.name, vars, ARMOR[g.cat] and ARMOR_TAGGERS or TAGGERS)", "-- no labels"),
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
    "carry_order": ("if a.best ~= b.best then return a.best > b.best end\n        return FACTION_AT[a.faction]",
                    "if a.best ~= b.best then return a.best < b.best end\n        return FACTION_AT[a.faction]"),
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
    "upvalue_wrap": ('if type(v) == "function" then held[#held + 1] = v end', "-- not followed"),
    "upvalue_depth": ("for _ = 0, WRAPS do", "for _ = 0, 1 do"),
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
    "risk_upgrades": ("if not g:find(NOT_UPGRADES) then queue[#queue + 1] = g end", "queue[#queue + 1] = g"),
    "risk_zero": ("if v and v ~= 0 then", "if v then"),
    "risk_worst": ("local bad = f.lower_better and math.max or math.min", "local bad = math.min"),
    "risk_damage": ("                elseif f.stat == \"damage\" then\n                    x = v\n", ""),
    "risk_weight": ("x = kg(weight(sec) + (ini_sys:r_float_ex(ps, \"inv_weight\") or 0))", "x = kg(weight(sec))"),
    "risk_sign": ("if x and v > 0 then", "if x then"),
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
    check(m.count() == 41, "thirty-four gun models and seven suits and helmets listed: %d" % m.count())
    check(m.get("wpn_ak74_pso") is None and m.entry_for("wpn_ak74_pso") is not None
          and same(m.entry_for("wpn_ak74_pso"), m.get("wpn_ak74")),
          "a scoped combination is not listed, and counts as its gun")
    check(secs("pistols") == ["wpn_fort", "wpn_hidden", "wpn_pm", "wpn_pm_never_kit", "wpn_pm_pm_kit", "wpn_aps",
                              "wpn_usp_45", "wpn_usp_nimble", "wpn_unused", "wpn_zero"]
          and names("pistols") == ["Fort-17", "Hidden Pistol", "PM", "PM Never", "PM Tactical", "Stechkin APS", "USP",
                                   "USP Nimble", "Unused Pistol", "Zero Pistol"],
          "pistols by name, not by section: %s %s" % (secs("pistols"), names("pistols")))
    check(secs("launchers") == ["wpn_rpg7"], "a grenade is not a launcher: %s" % secs("launchers"))
    check(secs("melee") == ["wpn_knife", "wpn_knife8", "wpn_knife7", "wpn_knife2", "wpn_knife9"],
          "a WP_KNIFE class is melee, a knife's attack animation is no gun: %s" % secs("melee"))
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

    # armor: by GAMMA's armor class (its repair type; a helmet is a helmet), else by kind;
    # templates, multiplayer suits and an item without an icon are not listed
    check(secs("light") == ["novice_outfit"] and secs("helmets") == ["helm_crafted", "helm_x", "helm_never"]
          and secs("exo") == ["exo_z"]
          and secs("medium") == ["sci_w"] and secs("heavy") == ["heavy_v"],
          "suits by repair type, else kind; helmets: %s" % [secs(c) for c in ("light", "medium", "heavy", "exo", "helmets")])
    check(m.get("outfit_base") is None and m.get("mp_exo_outfit") is None and m.get("tch_helmet") is None,
          "a template without a kind, a multiplayer suit, a helmet template without an icon: not listed")
    jacket = m.get("novice_outfit")
    check(vnames(jacket) == ["Jacket (Shock Res 2%)", "Jacket (Shock Res 3%)"],
          "suits of one name that differ: tagged by the card's values: %s" % vnames(jacket))
    # the card as the inventory shows a live suit: the outfit card's rows, stand-ins in place
    # of functions that need a live suit, their own arguments kept
    def card(sec):
        out = {}
        for r in m.stat_rows(False, sec).values():
            v = lua.globals().utils_ui.get_stats_string_value(None, sec, r.gr, r.stat)
            if isinstance(v, tuple):
                v = v[0]
            out[r.stat] = v
        return out
    jc = card("novice_outfit")
    want = {"fire_wound_protection": "+4 %", "apres_modifier": "+18 ", "burn_protection": "+41 %",
            "shock_protection": "+2 %", "radiation_protection": "+3 %", "telepatic_protection": None,
            "artefact_count": "1 ", "additional_inventory_weight": "+12 kg", "speed_modifier": "111 %"}
    check(jc == want, "a jacket's card: bullets meet its spine armor, values in float32 as the engine keeps "
          "them (burn 0.4 shows 41), BR class 1 - hit fraction rounded up, its speed line: %s" % jc)
    hc = card("helm_x")
    check(hc.get("fire_wound_protection") == "+25 %" and hc.get("burn_protection") == "+2 %"
          and hc.get("radiation_protection") == "+8 %",
          "a helmet: its head armor, the upgrade it ships with in, burn as light burn, which that upgrade "
          "leaves alone: %s" % hc)
    check(m.has_stat_card("novice_outfit") and m.has_stat_card("helm_x") and not m.has_stat_card("wpn_knife"),
          "suits and helmets have a card")
    check(len(m.risk_enhancements("novice_outfit")) == 0, "no R.I.S.K. weapon enhancements for a suit")
    check(card("heavy_v").get("fire_wound_protection") == "+40 %", "a bone a profile does not list takes its default "
          "line: %s" % card("heavy_v").get("fire_wound_protection"))
    # fully upgraded: per group the upgrade whose own change and what it opens add most; an
    # upgrade a group's alternative opens does not count without it; a group the item ships an
    # upgrade in keeps it; burn (light burn), BR class and speed do not move
    mx = {stat: tuple(m.max_stat("novice_outfit", stat) or ()) for stat in
          ("telepatic_protection", "fire_wound_protection", "burn_protection", "artefact_count",
           "additional_inventory_weight", "apres_modifier", "speed_modifier")}
    check(mx == {"telepatic_protection": (19, 0), "fire_wound_protection": (6, 4), "burn_protection": (41, 41),
                 "artefact_count": (2, 1), "additional_inventory_weight": (22, 12), "apres_modifier": (),
                 "speed_modifier": ()},
          "a jacket fully upgraded: psi through the upgrade that opens another (19, not 16 for the bigger single "
          "one or 24 for both), spine armor added by a profile, burn unmoved, a belt slot, carry weight: %s" % mx)
    # who wears them: a faction's characters of a rank, all its spawn sections together, and those
    # in each model (every visual that drops it, a visual that drops both variants once); a
    # story character as special; a monster's section is no faction
    def worn(sec):
        try:
            return [(r.faction, list(r.ranks.values()), r.special, round(r.best, 3)) for r in m.worn_by(sec).values()]
        except Exception as err:  # a faction without a place in the order
            return "error: %s" % str(err)[:60]
    check(worn("novice_outfit") == [("stalker", ["novice", "trainee"], None, 1.0)]
          and worn("novice_outfit_b") == worn("novice_outfit"),
          "worn by: shares pooled over a faction's sections, each model once per visual: %s" % worn("novice_outfit"))
    check(worn("helm_x") == [("dolg", [], True, 1.0), ("stalker", ["novice", "trainee"], None, 0.667)],
          "a helmet: by rank, and a story character's as special: %s" % worn("helm_x"))
    check(worn("exo_z") == [("stalker", ["novice"], None, 0.125)] and worn("sci_w") == [],
          "worn by nobody: none: %s %s" % (worn("exo_z"), worn("sci_w")))
    # how it drops: the chance by repair type (a novice suit as light), a rare suit's roll, the
    # rank progressive drops need, none when this economy drops none
    def drop(sec):
        d = m.armor_drop(sec)
        return (d.chance, d.rank, d.off)
    g = lua.globals()
    check(drop("novice_outfit") == (70, None, None) and drop("exo_z") == (1.5, 7552, None)
          and drop("helm_x") == (60, 250, None),
          "drops: chance by type, a rare suit's 15%%, the rank its cost needs: %s %s %s"
          % (drop("novice_outfit"), drop("exo_z"), drop("helm_x")))
    g.OUTFIT_DROPS = 3
    full = drop("exo_z")
    g.OUTFIT_DROPS = 1
    off = drop("exo_z")
    g.OUTFIT_DROPS = None
    check(full == (1.5, None, None) and off == (None, None, True),
          "full drops need no rank; with drops off, none: %s %s" % (full, off))
    ranks = [m.rank_at(v) for v in (0, 3998, 3999, 7552, 49999, 90000)]
    check(ranks == ["novice", "novice", "trainee", "experienced", "legend", "legend"],
          "a rating's rank, each up to its bound: %s" % ranks)
    # the Armor Exchange: what a faction's traders take for a suit (how many suits, any one) and
    # what they give for it; a variant counts as its model; a dialog nobody offers is left out
    def ex(sec):
        x = m.exchange(sec)
        return ([(list(g.traders.values()), g.faction, g.cost, g.count) for g in x.gets.values()],
                [(list(t.traders.values()), t.faction, t.cost, t.name) for t in x.takes.values()])
    check(ex("sci_w") == ([(["Petrenko"], "dolg", 10000, 2)], [(["Petrenko"], "dolg", 45000, "Exoskeleton")]),
          "exchange: Duty's trader gives it for one of two suits, and gives a suit for it: %s" % (ex("sci_w"),))
    check(ex("novice_outfit_b") == ([], [(["Petrenko"], "dolg", 10000, "SEVA")]) and ex("heavy_v") == ([], []),
          "a variant of a suit the exchange takes counts; a dialog nobody offers is left out: %s %s"
          % (ex("novice_outfit_b"), ex("heavy_v")))
    # whether a model turns up: what the other sources read, traders (the sell filter, a count
    # and a chance, configs some NPC uses), story gear, bodies' lists (what a body may hold),
    # tasks, the pump station, Homestead, gifts, crafting; what comes of what turns up: Nimble
    # for a gun that does, a kit that does on a gun that does, the Armor Exchange; never: what
    # nothing gives
    UP = ["wpn_ak74", "wpn_pm", "wpn_mp5_nimble", "wpn_rpg7", "wpn_knife2", "wpn_story", "wpn_knife7", "wpn_task",
          "wpn_task2", "wpn_spy", "wpn_guard", "wpn_home", "wpn_abakan", "helm_crafted", "wpn_stash_sil", "wpn_pm_pm_kit",
          "wpn_ak74_rk_kit", "sci_w", "exo_z", "novice_outfit"]
    NEVER = ["wpn_hidden", "wpn_zero", "wpn_unused", "wpn_knife8", "wpn_knife9", "wpn_pm_never_kit", "wpn_usp_nimble",
             "wpn_nothing", "helm_never", "heavy_v", "wpn_aps"]
    def verdicts(lst):
        try:
            return [s for s in lst if not m.obtainable(s)], [s for s in lst if m.obtainable(s)]
        except Exception as err:
            return "error: %s" % str(err)[:80], None
    v_up, v_never = verdicts(UP), verdicts(NEVER)
    check(v_up[0] == [] and v_never[1] == [],
          "what turns up and what never does: up but judged never %s; never but judged up %s" % (v_up[0], v_never[1]))
    u = lambda sec: {k: (list(v.values()) if not isinstance(v, bool) else v) for k, v in m.turns_up_model(sec).items()}
    check(u("wpn_story") == {"story": ["st_strelok", "GENERATE_NAME_x"]} and u("wpn_knife2") == {"trader": True}
          and u("wpn_ak74_rk_kit") == {"rolled": ["AK-74"]} and u("wpn_home") == {"homestead": True},
          "how a model turns up: %s %s %s %s" % (u("wpn_story"), u("wpn_knife2"), u("wpn_ak74_rk_kit"), u("wpn_home")))
    addons = {a: m.addon_turns_up(a) for a in ("kobra", "lam", "ak_kit", "rk_kit", "never_kit", "pm_kit", "wpn_sil",
                                                "wpn_gl", "toz_sil", "stash_sil")}
    check(addons == {"kobra": True, "lam": False, "ak_kit": True, "rk_kit": False, "never_kit": False, "pm_kit": True,
                     "wpn_sil": True, "wpn_gl": True, "toz_sil": False, "stash_sil": True},
          "addons: a fighter's scope roll (not a blacklisted scope; a kit stays on the gun it makes), mounts a "
          "loadout asks for, a stash gun's mount, what traders sell: %s" % addons)
    g = lua.globals()
    g.OUTFIT_DROPS = 1
    m.reset()
    off = m.obtainable("exo_z")
    g.OUTFIT_DROPS = None
    m.reset()
    check(off is False and m.obtainable("exo_z"), "a suit only fighters wear never turns up when bodies drop none")
    # a faction's gear, what turns up only, the likeliest first; special models (what turns up but
    # no ordinary fighter carries and no stash holds); a faction's new-game kit
    def gear(f):
        try:
            return [(x.e.sec, sorted(x.ranks.keys()), x.armor) for x in m.faction_gear(f).values()]
        except Exception as err:
            return "error: %s" % str(err)[:60]
    check(gear("stalker")[:5] == [("novice_outfit", ["novice", "trainee"], True), ("wpn_pm", ["novice"], None),
                                  ("wpn_toz34", ["experienced", "expert", "master", "professional", "veteran"], None),
                                  ("helm_x", ["novice", "trainee"], True), ("wpn_ak74", ["legend", "novice", "trainee"], None)]
          and "wpn_aps" not in [x[0] for x in gear("stalker")],
          "a faction's gear, carried and worn, the likeliest first, what never turns up left out: %s" % (gear("stalker"),))
    spec = {x: m.special(x) for x in ("wpn_story", "wpn_knife2", "wpn_ak74_rk_kit", "wpn_ak74", "wpn_pm", "wpn_rpg7",
                                      "wpn_nothing", "sci_w", "novice_outfit")}
    check(spec == {"wpn_story": True, "wpn_knife2": True, "wpn_ak74_rk_kit": True, "wpn_ak74": False, "wpn_pm": False,
                   "wpn_rpg7": False, "wpn_nothing": False, "sci_w": True, "novice_outfit": False},
          "special: turns up, but no ordinary fighter carries or wears it and no stash holds it: %s" % spec)
    kit = sorted(x.sec for x in m.kit_models("bandit").values())
    check(kit == ["wpn_ak74", "wpn_knife", "wpn_mp5_kurtz", "wpn_pm", "wpn_toz34"],
          "a faction's new-game kit, the injector's too: %s" % kit)
    hm = tuple(m.max_stat("helm_x", "radiation_protection") or ())
    check(hm == (8, 8), "a helmet's group with its shipped upgrade takes no other: %s" % (hm,))

    # what fits, and what a gun is made of
    att = m.attachments("wpn_ak74")
    fits = ([x.name for x in att.scopes.values()], [x.name for x in att.lasers.values()],
            [(x.name, x.makes) for x in att.kits.values()], [x.name for x in att.suppressors.values()],
            [(x.name, list(x.ammo.values())) for x in att.launchers.values()])
    check(fits == (["Kobra"], ["LAM"], [("Tactical Kit", "AK-74 Tactical"), ("RK kit", "AK-74 RK")], ["PBS-1"],
                   [("GP-25", ["VOG-25"])]),
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
    keep = tm.set_random_stash
    wrap = lua.eval("function(f) return function(...) return f(...) end end")
    tm.set_random_stash = wrap(wrap(keep))
    check(lv("wpn_ak74_pso") == ["l03_agroprom", "l08_yantar", "l02_garbage"],
          "the level lists behind mods' wrappers of the stash function: %s" % lv("wpn_ak74_pso"))
    tm.set_random_stash = lua.eval("function() return nil end")
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
    # R.I.S.K.: per family the stat with one enhancement on the gun as it ships, the worst bad roll
    risk = {r.family: (r.base, r.low, r.high, r.worst) for r in m.risk_enhancements("wpn_ak74").values()}
    fams = [r.family for r in m.risk_enhancements("wpn_ak74").values()]
    check(fams == ["fire_rate", "recoil", "weight", "damage"]
          and risk["fire_rate"] == (700, 712, 940, 460) and risk["weight"] == (3.3, 1.3, 1.3, 5.3)
          and risk["damage"] == (0, 2, 40, -40),
          "R.I.S.K. per family, in the card's order: the card value with its weakest and strongest good "
          "result and its worst bad one, an element of no strength left out; weight in kg (lighter is "
          "better); damage as its percent: %s" % risk)
    rec = risk.get("recoil")
    check(rec is not None and rec[1] == rec[2] and rec[1] > rec[0] and rec[3] is None,
          "recoil through the card's formula, no bad roll when there is none: %s" % (rec,))
    pm_fams = [r.family for r in m.risk_enhancements("wpn_pm").values()]
    check("recoil" not in pm_fams, "no recoil row for a gun without a recoil profile: %s" % pm_fams)
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
