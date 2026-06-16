"""
Playtest scenario 7: entry-level content cross-reference validation.

The 2026-06-10 audit verified which content FILES load; this closes the
declared gap one level down: every ID one piece of loaded content points
at must resolve in the loaded databases. Runs against the booted engine's
singletons — the exact runtime contract, Update-N merges included — so it
also guards every future WES-generated commit.

The KNOWN_* sets below are the pre-existing baseline (43 dangling
references, all in sacred content JSON awaiting designer decisions —
full human-readable listing:
Development-Plan/repo-audit-2026-06-10/CONTENT_XREF_REPORT.md, regenerate
with `python tools/content_xref_report.py`). The tests FAIL only on NEW
violations. When a designer fixes an entry, delete it here so the guard
covers it permanently.
"""
import pytest

from data.databases.material_db import MaterialDatabase
from data.databases.equipment_db import EquipmentDatabase
from data.databases.recipe_db import RecipeDatabase
from data.databases.skill_db import SkillDatabase
from data.databases.placement_db import PlacementDatabase
from data.databases.skill_unlock_db import SkillUnlockDatabase

KNOWN_GHOST_RECIPE_INPUTS = {
    ('alchemy_transmute_iron_steel', 'coal'),
}

# grappling_hook/jetpack exist in items-engineering-1.JSON but carry
# neither flags.stackable nor flags.placeable, so no database loads them —
# the recipes craft into the void.
KNOWN_GHOST_RECIPE_OUTPUTS = {
    ('engineering_grappling_hook', 'grappling_hook'),
    ('engineering_jetpack', 'jetpack'),
}

KNOWN_ORPHAN_PLACEMENTS = {
    'alchemy_antidote', 'alchemy_berserker_rage',
    'alchemy_crystallize_lightning', 'alchemy_haste_potion',
    'alchemy_invisibility_potion', 'alchemy_levitation_elixir',
    'alchemy_liquid_courage', 'alchemy_mana_potion',
    'alchemy_night_vision_elixir', 'alchemy_philosophers_stone',
    'alchemy_poison_vial', 'alchemy_water_breathing_potion',
    'engineering_auto_collector', 'engineering_poison_trap',
    'engineering_proximity_alarm', 'engineering_repair_drone',
    'engineering_resource_scanner', 'engineering_shield_generator',
    'engineering_slow_field_generator', 'engineering_teleporter',
    'engineering_void_bomb',
    'refining_clay_to_brick', 'refining_coal_to_charcoal',
    'refining_gold_ore_to_ingot', 'refining_hide_to_leather',
    'refining_limestone_to_quicklime', 'refining_platinum_ore_to_ingot',
    'refining_rarity_gold_rare', 'refining_rarity_platinum_legendary',
    'refining_rarity_silver_epic', 'refining_rarity_steel_uncommon',
    'refining_sand_to_glass', 'refining_silver_ore_to_ingot',
}

KNOWN_GHOST_SKILL_UNLOCKS = {
    ('unlock_fortify', 'fortify'),
    ('unlock_miners_endurance', 'miners_endurance'),
}

# All three Update-1 bosses drop materials that do not exist.
KNOWN_GHOST_ENEMY_DROPS = {
    ('void_archon', 'shadow_crystal'),
    ('void_archon', 'arcane_dust'),
    ('storm_titan', 'lightning_essence'),
    ('storm_titan', 'storm_core'),
    ('inferno_drake', 'drake_scale'),
}


@pytest.fixture()
def known_item_ids(engine):
    """Every ID that can legally appear as an item reference."""
    ids = set(MaterialDatabase.get_instance().materials.keys())
    ids |= set(EquipmentDatabase.get_instance().items.keys())
    return ids


def _assert_no_new(violations, baseline, what):
    new = violations - baseline
    assert not new, (
        f"{len(new)} NEW {what} (beyond the documented baseline — see "
        f"CONTENT_XREF_REPORT.md):\n"
        + "\n".join(f"  {v}" for v in sorted(new)[:25])
    )


def test_recipe_inputs_resolve(engine, known_item_ids):
    violations = set()
    for recipe_id, recipe in RecipeDatabase.get_instance().recipes.items():
        for inp in recipe.inputs:
            ref = inp.get('materialId') or inp.get('itemId')
            if ref and ref not in known_item_ids:
                violations.add((recipe_id, ref))
    _assert_no_new(violations, KNOWN_GHOST_RECIPE_INPUTS,
                   "recipe inputs referencing unknown items")


def test_recipe_outputs_resolve(engine, known_item_ids):
    violations = set()
    for recipe_id, recipe in RecipeDatabase.get_instance().recipes.items():
        # Enchanting outputs are enchantment IDs (a separate namespace
        # applied to gear, not inventory items) — correct by design.
        if getattr(recipe, 'station_type', '') in ('enchanting', 'adornments'):
            continue
        out = getattr(recipe, 'output_id', None)
        if out and out not in known_item_ids:
            violations.add((recipe_id, out))
    _assert_no_new(violations, KNOWN_GHOST_RECIPE_OUTPUTS,
                   "recipes whose output no database loads")


def test_placements_reference_existing_recipes(engine):
    recipes = RecipeDatabase.get_instance().recipes
    violations = {rid for rid in PlacementDatabase.get_instance().placements
                  if rid not in recipes}
    _assert_no_new(violations, KNOWN_ORPHAN_PLACEMENTS,
                   "placements pointing at recipes that do not load")


def test_skill_unlocks_reference_existing_skills(engine):
    skills = SkillDatabase.get_instance().skills
    violations = set()
    for unlock_id, unlock in SkillUnlockDatabase.get_instance().unlocks.items():
        skill_ref = getattr(unlock, 'skill_id', None) or unlock_id
        if skill_ref not in skills:
            violations.add((unlock_id, skill_ref))
    _assert_no_new(violations, KNOWN_GHOST_SKILL_UNLOCKS,
                   "skill unlocks pointing at skills that do not load")


def test_enemy_drops_resolve(engine, known_item_ids):
    enemy_db = getattr(engine.combat_manager, 'enemy_database', None)
    if enemy_db is None:
        from Combat.enemy import EnemyDatabase
        enemy_db = EnemyDatabase.get_instance() \
            if hasattr(EnemyDatabase, 'get_instance') else None
    if enemy_db is None or not getattr(enemy_db, 'enemies', None):
        pytest.skip("EnemyDatabase not reachable from engine")
    violations = set()
    for enemy_id, definition in enemy_db.enemies.items():
        for drop in getattr(definition, 'drops', []):
            ref = getattr(drop, 'item_id', None) or getattr(drop, 'material_id', None)
            if ref and ref not in known_item_ids:
                violations.add((enemy_id, ref))
    _assert_no_new(violations, KNOWN_GHOST_ENEMY_DROPS,
                   "enemy drops referencing unknown items")
