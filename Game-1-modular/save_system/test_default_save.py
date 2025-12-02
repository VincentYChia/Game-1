"""
Test script to validate the default save file.
Verifies that all equipment items referenced in the save actually exist.
"""

import sys
import json
import os
from pathlib import Path

# Add the parent directory (Game-1-modular) to path so we can import from data/
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.databases.equipment_db import EquipmentDatabase

def test_default_save():
    """Test that default save has valid equipment items."""
    print("\n=== Testing Default Save ===\n")

    # Load equipment database
    eq_db = EquipmentDatabase.get_instance()

    # Try loading from JSON files first
    items_dir = "items.JSON"
    json_files = ["items-smithing-2.JSON", "items-tools-1.JSON"]

    for json_file in json_files:
        filepath = os.path.join(items_dir, json_file)
        if os.path.exists(filepath):
            eq_db.load_from_file(filepath)
            print(f"✓ Loaded {filepath}")

    print(f"\n📊 Total equipment items in database: {len(eq_db.items)}")
    print(f"   Sample items: {list(eq_db.items.keys())[:10]}\n")

    # Load default save
    save_path = "saves/default_save.json"
    if not os.path.exists(save_path):
        print(f"❌ Default save not found: {save_path}")
        return False

    with open(save_path, 'r') as f:
        save_data = json.load(f)

    print(f"✓ Loaded default save from {save_path}\n")

    # Check equipped items
    equipment = save_data.get("player", {}).get("equipment", {})
    print("🔍 Checking equipped items:")

    all_valid = True
    for slot, item_id in equipment.items():
        if item_id is None:
            print(f"   ⊘ {slot:15} - (empty)")
            continue

        if eq_db.is_equipment(item_id):
            print(f"   ✓ {slot:15} - {item_id}")
        else:
            print(f"   ❌ {slot:15} - {item_id} (NOT FOUND IN DATABASE)")
            all_valid = False

    # Check inventory items with equipment_data
    print("\n🔍 Checking inventory equipment:")
    inventory = save_data.get("player", {}).get("inventory", [])

    for i, slot in enumerate(inventory):
        if slot and slot.get("equipment_data"):
            item_id = slot["item_id"]
            if eq_db.is_equipment(item_id):
                print(f"   ✓ Slot {i:2d} - {item_id}")
            else:
                print(f"   ❌ Slot {i:2d} - {item_id} (NOT FOUND IN DATABASE)")
                all_valid = False

    print("\n" + "="*50)
    if all_valid:
        print("✅ All equipment items in default save are valid!")
        print("="*50 + "\n")
        return True
    else:
        print("❌ Some equipment items are missing from database!")
        print("="*50 + "\n")
        return False

if __name__ == "__main__":
    success = test_default_save()
    exit(0 if success else 1)
