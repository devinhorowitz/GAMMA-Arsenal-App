# Arsenal's API

For mods that use Arsenal: read its catalog, teach the player of a gun, put a button on
Arsenal's pages, open Arsenal at a model, or find where the game read an item from.

Everything is in `gamedata\scripts\arsenal_api.script`. That file is the contract: it stays
stable between releases, while the rest of Arsenal changes freely. Call only these functions,
not Arsenal's other scripts.

## The rules

- **Check that Arsenal is there.** X-Ray gives each script a table under its file name, so
  call `arsenal_api.model(...)`, and guard it: `if arsenal_api then ... end`.
- **Nothing throws.** A missing module, a section Arsenal doesn't list, or a call before the
  game is up returns `nil`, `false` or an empty table. An internal error is logged as
  `[arsenal_api] ...`.
- **You get copies.** Changing a returned table changes nothing in Arsenal.
- **`arsenal_api.VERSION`** only goes up, and only when a function changes meaning or goes
  away. New functions and new fields come without a bump, so check `>=`:

```lua
if arsenal_api and arsenal_api.VERSION >= 1 then
    -- ...
end
```

## Reading the catalog

**`arsenal_api.categories()`** returns the categories in Arsenal's order: `{ "pistols", "smgs",
"shotguns", "rifles", "snipers", "launchers", "melee", "ammo", "scopes", "suppressors",
"accessories", "light", "medium", "heavy", "exo", "helmets" }`. The attachments' three came in
1.8.0; read them by name, not by position.

**`arsenal_api.model(sec)`** returns the model a section belongs to, or `nil`. Any section of
it will do, a scoped or silenced one too.

```lua
{
    sec = "wpn_ak74",       -- the model's own section (its first variant's)
    name = "AK-74",         -- as the catalog shows it
    category = "rifles",    -- one of categories()
    variants = {            -- versions that play differently, each with its sections
        { sec = "wpn_ak74", name = "AK-74", members = { "wpn_ak74", "wpn_ak74_pso", ... } },
    },
    obtainable = true,      -- it turns up in this game (else only the jailbreak lists it)
    found = false,          -- the player has had one
    known = true,           -- the catalog lists it for him (always, with the jailbreak)
    studied = false,        -- its page shows its stats
    new = true,             -- it is marked new
}
```

**`arsenal_api.models(category)`** returns every model of a category, by name, each as
`model()` gives it, or `{}` for an unknown category.

## Teaching the player

**`arsenal_api.reveal(sec, who, study, quiet)`** teaches the player of a model, as if a source
told him. `who` names the source as it reads after "Learned from":

```lua
arsenal_api.reveal("wpn_mg42", "the Mercenary Database")
-- PDA: "Learned from the Mercenary Database: MG42"
-- the page: "Learned 14.05.2012 from the Mercenary Database"
```

From then on the model is listed, marked new and announced on the PDA unless `quiet` is true.
With `study` true, its page shows its stats too. It returns `true` when the model was new to
the player. Nothing happens for what never turns up in this game, or with the jailbreak on,
which lists everything anyway.

**`arsenal_api.mark_all_read()`** reads every new model at once, as the page's **Mark all
read** does.

## Arsenal's pages

**`arsenal_api.add_action(id, def)`** puts your button on Arsenal's model pages, as
Workbench's Customize is:

```lua
arsenal_api.add_action("my_mod", {
    label = "st_my_mod_button",                             -- a string id
    show = function(sec) return my_mod.handles(sec) end,    -- whether it applies to this item
    run = function(sec) my_mod.open(sec) end,               -- what a click does
})
```

`sec` is the section the page shows. Up to three apps' buttons show at once, and adding the
same `id` again replaces it. It returns `false` when the arguments are wrong.
**`arsenal_api.remove_action(id)`** takes the button away.

**`arsenal_api.open(page, sec)`** opens Arsenal on a page: `"catalog"` (the default),
`"workbench"` or `"compare"`. With `sec`, the catalog shows that model and Workbench that item;
a model the player doesn't know yet isn't shown. It opens in the PDA when the PDA is open,
otherwise in Arsenal's own window. It returns `false` when it can't: an unknown page, the
player not up and about, or Fatal Error's PDA out of use.

## Where an item comes from

**`arsenal_api.defined_in(sec)`** returns where the game read a section from, or `nil`:

```lua
{
    section = "wpn_ak74_pmc",
    model = "dynamics\\weapons\\wpn_ak74_pmc\\wpn_ak74_pmc",
    icon = "ui\\ui_icon_bas",
    files = {                                   -- most lines first
        { name = "w_ak74_pmc.ltx", lines = 52, dltx = false },
        { name = "mod_system_3dss_ak74_pmc.ltx", lines = 6, dltx = true },
    },
}
```

`files` lists the config files that wrote the section's lines, with how many each wrote. File
names come without their folders, and a line the section inherits keeps its parent's file.
`dltx` marks a `mod_*.ltx`, a DLTX file. `files` needs Modded Exes' DLTX exports, and it is
`nil` without them. MO2's mod names can't be seen from inside the game; the file names are the
way back to them, in MO2's Data tab.

The same shows at the end of each model's page with **MCM > Arsenal > Show where items are
defined**.

## Permissions

Arsenal is MIT licensed. Using it as a dependency needs nothing from you. If you copy its code,
keep the copyright notice and the license text with what you copy.
