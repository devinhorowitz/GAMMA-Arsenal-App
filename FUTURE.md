# Future possibilities

Ideas looked at and set aside for now, with why and what each would take.

## Squared Away rigs

[Squared Away](https://fomok.github.io/zonebench/), by Fomok, adds chest rigs with pockets,
storage boxes and a Tarkov-style space limit for the bag. A player asked for its rigs in the
catalog and in Compare.

**Why not yet:** Squared Away runs only on its own engine, a fork of the modded exes. Arsenal is
built and tested on an install that runs Screen Space Shaders 24's own engine, which is closed
source, so no fork can carry it. Rig support couldn't be tried in game here.

**What it would take,** from a review of 2.0.6 Hotfix 4 (October 2026):

- **A rigs category:** the sections flagged `amp_rig = true`, leaving out the names Squared Away
  keeps only for old saves. Arsenal already hides an empty category, so nothing changes for
  players without it.
- **A rig card:** pockets and their cells, drum pockets, tier and weight. Rigs take no upgrades,
  so the card has no upgrade column.
- **Rigs in Compare.**
- **Where to find one:** taken from bodies, by rank, from Squared Away's own drop chances
  (`amp_drop_opts`, `amp_drop_id` and its menu values). Crafting and starting kits are already
  counted the usual way.
- English and Russian strings, tests, and the new category in [API.md](API.md).

About the size of Arsenal 1.2.0.
