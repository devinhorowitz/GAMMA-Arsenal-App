<img src="media/arsenal_icon_amber.png" width="96" align="right" alt="">

# Arsenal

**Every gun in your GAMMA game, in the PDA: its stats, where to find it, what fits it, and
which ones you have found.**

![Arsenal's page for the RD 5.45 Custom "ISG"](media/arsenal_screenshot.png)

Arsenal is a PDA app for the S.T.A.L.K.E.R. Anomaly modpack GAMMA. It reads the running
game's own configs, so the catalog is whatever your mod list has, with the numbers your
inventory shows.

## What a gun's page shows

- **The stat card** from the inventory, and the most each stat reaches fully upgraded.
- **Variants.** Guns that share a name are one entry. Versions that play differently are
  listed by what sets them apart, each with when and where you found it.
- **Where to find it.** The factions whose fighters carry it and at which ranks, likeliest
  first; the levels whose stashes most often hold it; Nimble's trade-ins; the gun and kit it
  is made from; new-game kits and their points.
- **Ammo,** and the calibers a conversion upgrade opens.
- **Magazines,** when Mags Redux is on.
- **Scopes, suppressors and accessories:** launchers with their grenades, laser modules,
  kits, and mounts an upgrade adds.
- **Camos** from 3DSS's camo system: the ones you have discovered, and which factions' guns
  carry the rest.
- **Parts,** and the **repair kits** that fit the gun.

In English and Russian.

## Collecting

A gun counts as found the first time it enters your inventory: picked up, looted, bought,
crafted or given as a reward. Whatever you carry when a save loads counts too, so a
playthrough already underway starts with credit. The PDA counts found models by category,
a filter shows only those, and a news line tells you when a new one comes in.

Guns you only see do not count, unless you turn on **MCM > Arsenal > Count guns you see**.
Then the guns in a body, a stash or a trader's stock count when you open it.

## Requirements

- GAMMA. Arsenal reads GAMMA's loadouts, stashes, repair kits and camos where a mod list has
  them, and leaves out what it lacks.
- [Mod App Creator (MAC)](https://www.moddb.com/mods/stalker-anomaly/addons/mod-app-creator-mac)
  for the PDA tile. Without it, open Arsenal with the key below.
- MCM, which GAMMA includes.

## Install

In Mod Organizer 2, use **Install a new mod from archive**, pick the zip, and enable the mod.
Arsenal shares no file with any other mod, so its place in the load order does not matter.
It works in a new game or an existing one.

## Sharper pages with the 3D PDA

With the 3D PDA on, the game draws PDA pages onto the screen of the PDA in your hands, which
softens small text and icons. **MCM > Arsenal > Open Arsenal on its own** takes a key that
opens Arsenal straight on the screen, as sharp as the inventory.

## Credits

- The [GAMMA Item Database](https://stalker-gamma-db.com/) by simonwdev and SaloEater, the
  reference for what a weapon page should cover. Arsenal reads the game itself rather than
  their data, as SaloEater suggested, so any mod list gets a true catalog.
- Mod App Creator by Denis_3edd.
- The GAMMA mods whose data Arsenal reads: Weighted NPC Random Loadouts, Grok's stash
  overhaul, Darkasleif's Nimble Upgrades Guns, Weapon Parts Overhaul, and 3DSS for GAMMA's
  camo system.

## Development

`tools/` builds and tests the mod. `build.py` runs the tests and installs into an MO2 mod
folder; `test_*.py` run the scripts under LuaJIT (lupa) against stand-ins for the engine,
each with mutants the tests must catch; `release.py` packages the zip.

## License

MIT; see [LICENSE](LICENSE).
