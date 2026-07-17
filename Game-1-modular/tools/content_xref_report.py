"""
Content cross-reference report — designer tool.

Boots the real GameEngine headless (every database loaded exactly as the
game loads it, Update-N included) and prints every entry-level dangling
reference: recipe inputs/outputs, placements, skill unlocks, enemy drops.

Run:  python tools/content_xref_report.py
The pytest guard (tests/integration/test_07_content_xref.py) fails on any
NEW violation; this tool is the human-readable full listing for designer
review of the known baseline.
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def main():
    from core.config import Config
    _orig = Config.init_screen_settings
    Config.init_screen_settings = (
        lambda width=None, height=None, fullscreen=False:
        _orig(width=1280, height=720, fullscreen=False)
    )
    from core.game_engine import GameEngine
    print("Booting engine (headless) ...")
    engine = GameEngine()

    from data.databases.material_db import MaterialDatabase
    from data.databases.equipment_db import EquipmentDatabase
    from data.databases.recipe_db import RecipeDatabase
    from data.databases.skill_db import SkillDatabase
    from data.databases.placement_db import PlacementDatabase
    from data.databases.skill_unlock_db import SkillUnlockDatabase

    known = set(MaterialDatabase.get_instance().materials.keys())
    known |= set(EquipmentDatabase.get_instance().items.keys())
    recipes = RecipeDatabase.get_instance().recipes
    skills = SkillDatabase.get_instance().skills

    sections = []

    rows = []
    for rid, recipe in sorted(recipes.items()):
        for inp in recipe.inputs:
            ref = inp.get('materialId') or inp.get('itemId')
            if ref and ref not in known:
                rows.append(f"  {rid}: input '{ref}' unknown")
    sections.append(("RECIPE INPUTS -> unknown items", rows))

    rows = []
    for rid, recipe in sorted(recipes.items()):
        # Enchanting outputs are enchantment IDs (a separate namespace
        # applied to gear), not inventory items — excluded by design.
        if getattr(recipe, 'station_type', '') in ('enchanting', 'adornments'):
            continue
        out = getattr(recipe, 'output_id', None)
        if out and out not in known:
            rows.append(f"  {rid}: output '{out}' unknown "
                        f"(crafting it yields an item no database loads)")
    sections.append(("RECIPE OUTPUTS -> unknown items", rows))

    rows = []
    for rid in sorted(PlacementDatabase.get_instance().placements):
        if rid not in recipes:
            rows.append(f"  placement '{rid}' has no loaded recipe")
    sections.append(("PLACEMENTS -> missing recipes", rows))

    rows = []
    for uid, unlock in sorted(SkillUnlockDatabase.get_instance().unlocks.items()):
        ref = getattr(unlock, 'skill_id', None) or uid
        if ref not in skills:
            rows.append(f"  unlock '{uid}' -> skill '{ref}' not loaded")
    sections.append(("SKILL UNLOCKS -> missing skills", rows))

    rows = []
    enemy_db = getattr(engine.combat_manager, 'enemy_database', None)
    if enemy_db is None:
        from Combat.enemy import EnemyDatabase
        enemy_db = EnemyDatabase.get_instance()
    for eid, definition in sorted(enemy_db.enemies.items()):
        for drop in getattr(definition, 'drops', []):
            ref = getattr(drop, 'item_id', None) or getattr(drop, 'material_id', None)
            if ref and ref not in known:
                rows.append(f"  {eid}: drop '{ref}' unknown "
                            f"(loot cannot materialize)")
    sections.append(("ENEMY DROPS -> unknown items", rows))

    print("\n" + "=" * 72)
    print("CONTENT CROSS-REFERENCE REPORT")
    print("=" * 72)
    total = 0
    for title, rows in sections:
        print(f"\n## {title} ({len(rows)})")
        for row in rows:
            print(row)
        total += len(rows)
    print(f"\nTOTAL: {total} dangling references")


if __name__ == '__main__':
    main()
