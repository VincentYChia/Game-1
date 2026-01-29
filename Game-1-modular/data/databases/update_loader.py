"""
Update Loader - Auto-discovers and loads content from Update-N directories

This module extends all database loaders to automatically scan installed Update-N
packages and load their content without modifying core database code.

Usage in game_engine.py:
    from data.databases.update_loader import load_all_updates

    # After loading core databases
    load_all_updates()
"""

import json
from pathlib import Path
from typing import List

# Import all databases
from data.databases.equipment_db import EquipmentDatabase
from data.databases.skill_db import SkillDatabase
from data.databases.material_db import MaterialDatabase
# Add other databases as needed


def get_installed_updates(project_root: Path) -> List[str]:
    """Get list of installed updates from manifest"""
    manifest_path = project_root / "updates_manifest.json"

    if not manifest_path.exists():
        return []

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        return manifest.get('installed_updates', [])
    except:
        return []


def scan_update_directory(update_dir: Path, database_type: str) -> List[Path]:
    """Scan an update directory for relevant JSON files (both .JSON and .json)"""
    files = []

    if database_type == 'equipment':
        # Look for items/weapons/armor JSONs
        patterns = ['*items*.JSON', '*weapons*.JSON', '*armor*.JSON', '*tools*.JSON',
                    '*items*.json', '*weapons*.json', '*armor*.json', '*tools*.json']
    elif database_type == 'skills':
        # Look for skills JSONs
        patterns = ['*skills*.JSON', '*skills*.json']
    elif database_type == 'enemies':
        # Look for hostiles/enemies JSONs
        patterns = ['*hostiles*.JSON', '*enemies*.JSON', '*hostiles*.json', '*enemies*.json']
    elif database_type == 'materials':
        # Look for materials/consumables/devices JSONs
        patterns = ['*materials*.JSON', '*consumables*.JSON', '*devices*.JSON',
                    '*materials*.json', '*consumables*.json', '*devices*.json']
    else:
        patterns = ['*.JSON', '*.json']

    for pattern in patterns:
        files.extend(update_dir.glob(pattern))

    # Remove duplicates (in case both patterns match on case-insensitive systems)
    return list(set(files))


def load_equipment_updates(project_root: Path):
    """Load equipment from all installed updates"""
    db = EquipmentDatabase.get_instance()
    installed = get_installed_updates(project_root)

    if not installed:
        print("   No updates installed for equipment")
        return

    print(f"\n🔄 Loading equipment from {len(installed)} update(s)...")

    for update_name in installed:
        update_dir = project_root / update_name
        if not update_dir.exists():
            print(f"   ⚠️  Update directory not found: {update_name}")
            continue

        files = scan_update_directory(update_dir, 'equipment')

        for file in files:
            try:
                print(f"   📦 Loading: {update_name}/{file.name}")
                db.load_from_file(str(file))
            except Exception as e:
                print(f"   ⚠️  Error loading {file.name}: {e}")


def load_skill_updates(project_root: Path):
    """Load skills from all installed updates"""
    db = SkillDatabase.get_instance()
    installed = get_installed_updates(project_root)

    if not installed:
        print("   No updates installed for skills")
        return

    print(f"\n🔄 Loading skills from {len(installed)} update(s)...")

    for update_name in installed:
        update_dir = project_root / update_name
        if not update_dir.exists():
            print(f"   ⚠️  Update directory not found: {update_name}")
            continue

        files = scan_update_directory(update_dir, 'skills')

        for file in files:
            try:
                print(f"   ⚡ Loading: {update_name}/{file.name}")
                db.load_from_file(str(file))
            except Exception as e:
                print(f"   ⚠️  Error loading {file.name}: {e}")


def load_enemy_updates(project_root: Path):
    """Load enemies from all installed updates"""
    from Combat.enemy import EnemyDatabase
    db = EnemyDatabase.get_instance()
    installed = get_installed_updates(project_root)

    if not installed:
        print("   No updates installed for enemies")
        return

    print(f"\n🔄 Loading enemies from {len(installed)} update(s)...")

    for update_name in installed:
        update_dir = project_root / update_name
        if not update_dir.exists():
            print(f"   ⚠️  Update directory not found: {update_name}")
            continue

        files = scan_update_directory(update_dir, 'enemies')

        for file in files:
            try:
                print(f"   👾 Loading: {update_name}/{file.name}")
                db.load_additional_file(str(file))
            except Exception as e:
                print(f"   ⚠️  Error loading {file.name}: {e}")


def load_material_updates(project_root: Path):
    """Load materials/consumables/devices from all installed updates"""
    db = MaterialDatabase.get_instance()
    installed = get_installed_updates(project_root)

    if not installed:
        return  # Silent - materials are optional

    print(f"\n🔄 Loading materials from {len(installed)} update(s)...")

    for update_name in installed:
        update_dir = project_root / update_name
        if not update_dir.exists():
            print(f"   ⚠️  Update directory not found: {update_name}")
            continue

        files = scan_update_directory(update_dir, 'materials')

        for file in files:
            try:
                print(f"   💎 Loading: {update_name}/{file.name}")
                # Try load_from_file first (for dedicated material JSONs)
                if 'materials' in file.name.lower():
                    db.load_from_file(str(file))
                else:
                    # For consumables/devices, use load_stackable_items
                    db.load_stackable_items(str(file))
            except Exception as e:
                print(f"   ⚠️  Error loading {file.name}: {e}")


def load_recipe_updates(project_root: Path):
    """Load recipes from all installed updates"""
    from data.databases.recipe_db import RecipeDatabase
    db = RecipeDatabase.get_instance()
    installed = get_installed_updates(project_root)

    if not installed:
        return  # Silent - recipes are optional

    print(f"\n🔄 Loading recipes from {len(installed)} update(s)...")

    for update_name in installed:
        update_dir = project_root / update_name
        if not update_dir.exists():
            print(f"   ⚠️  Update directory not found: {update_name}")
            continue

        # Scan for recipe files (both .JSON and .json)
        patterns = ['*recipes*.JSON', '*crafting*.JSON', '*recipes*.json', '*crafting*.json']
        files = []
        for pattern in patterns:
            files.extend(update_dir.glob(pattern))
        files = list(set(files))  # Remove duplicates

        for file in files:
            try:
                print(f"   📜 Loading: {update_name}/{file.name}")

                # Determine station type from filename
                filename_lower = file.name.lower()
                if 'smithing' in filename_lower:
                    station_type = 'smithing'
                elif 'alchemy' in filename_lower:
                    station_type = 'alchemy'
                elif 'refining' in filename_lower:
                    station_type = 'refining'
                elif 'engineering' in filename_lower:
                    station_type = 'engineering'
                elif 'adornment' in filename_lower or 'enchanting' in filename_lower:
                    station_type = 'adornments'
                else:
                    # Try to auto-detect from content or default to smithing
                    station_type = 'smithing'
                    print(f"      ⚠️  Could not detect station type, defaulting to smithing")

                # Load recipes using the internal _load_file method
                count = db._load_file(str(file), station_type)
                print(f"      ✓ Loaded {count} recipes for {station_type}")

            except Exception as e:
                print(f"   ⚠️  Error loading {file.name}: {e}")


def load_all_updates(project_root: Path = None):
    """
    Load all content from installed Update-N packages

    Call this AFTER loading core databases in game_engine.py
    """
    if project_root is None:
        # Auto-detect project root
        project_root = Path(__file__).parent.parent.parent

    installed = get_installed_updates(project_root)

    if not installed:
        print("\n📦 No Update-N packages installed")
        return

    print(f"\n" + "="*70)
    print(f"📦 Loading {len(installed)} Update-N package(s): {', '.join(installed)}")
    print("="*70)

    # Load each database type
    load_equipment_updates(project_root)
    load_skill_updates(project_root)
    load_enemy_updates(project_root)
    load_material_updates(project_root)
    load_recipe_updates(project_root)

    print(f"\n✅ Update-N packages loaded successfully")
    print("="*70 + "\n")


def list_update_content(update_name: str, project_root: Path = None):
    """List all content in an update package (for debugging)"""
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    update_dir = project_root / update_name
    if not update_dir.exists():
        print(f"Update directory not found: {update_name}")
        return

    print(f"\n📦 Content in {update_name}:\n")

    all_json = list(update_dir.glob("*.JSON")) + list(update_dir.glob("*.json"))
    for json_file in sorted(set(all_json)):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            print(f"📄 {json_file.name}")

            # Count items by type
            for key, value in data.items():
                if key == 'metadata':
                    continue
                if isinstance(value, list):
                    print(f"   - {key}: {len(value)} entries")
                    # Show first few IDs
                    for i, item in enumerate(value[:3]):
                        id_key = next((k for k in ['itemId', 'skillId', 'enemyId'] if k in item), None)
                        if id_key:
                            print(f"      [{i+1}] {item[id_key]}")
                    if len(value) > 3:
                        print(f"      ... and {len(value) - 3} more")
            print()

        except Exception as e:
            print(f"   ⚠️  Error reading {json_file.name}: {e}\n")
