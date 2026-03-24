"""
Item Validator - Validate item JSON files for correctness

Checks for:
- Required fields
- Duplicate IDs
- Valid data types
- Consistent tier/rarity relationships
"""

import json
from typing import Dict, List, Any, Tuple


class ItemValidator:
    """Validate item JSON definitions"""

    REQUIRED_FIELDS = {
        'equipment': ['itemId', 'name', 'category', 'tier', 'rarity', 'slot', 'stats'],
        'material': ['materialId', 'name', 'tier', 'category', 'rarity']
    }

    VALID_RARITIES = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'artifact']
    VALID_TIERS = [1, 2, 3, 4]
    VALID_SLOTS = ['mainHand', 'offHand', 'helmet', 'chestplate', 'leggings', 'boots', 'gauntlets', 'tool']

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.seen_ids = set()

    def validate_file(self, filepath: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate an item JSON file

        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        self.seen_ids = set()

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.errors.append(f"Failed to load JSON: {e}")
            return False, self.errors, self.warnings

        # Validate structure
        if 'metadata' not in data:
            self.warnings.append("Missing 'metadata' section")

        # Validate items
        for section_name, items in data.items():
            if section_name == 'metadata':
                continue

            if not isinstance(items, list):
                self.warnings.append(f"Section '{section_name}' is not a list")
                continue

            for i, item in enumerate(items):
                self._validate_item(item, section_name, i)

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _validate_item(self, item: Dict[str, Any], section: str, index: int):
        """Validate a single item"""
        category = item.get('category', 'unknown')

        # Check for required fields
        required = self.REQUIRED_FIELDS.get(category, [])
        for field in required:
            if field not in item:
                self.errors.append(f"{section}[{index}]: Missing required field '{field}'")

        # Check for duplicate IDs
        item_id = item.get('itemId') or item.get('materialId')
        if item_id:
            if item_id in self.seen_ids:
                self.errors.append(f"{section}[{index}]: Duplicate ID '{item_id}'")
            self.seen_ids.add(item_id)
        else:
            self.errors.append(f"{section}[{index}]: No ID field found")

        # Validate rarity
        rarity = item.get('rarity')
        if rarity and rarity not in self.VALID_RARITIES:
            self.warnings.append(f"{item_id}: Invalid rarity '{rarity}'")

        # Validate tier
        tier = item.get('tier')
        if tier and tier not in self.VALID_TIERS:
            self.warnings.append(f"{item_id}: Invalid tier {tier}")

        # Equipment-specific validation
        if category == 'equipment':
            slot = item.get('slot')
            if slot and slot not in self.VALID_SLOTS:
                self.warnings.append(f"{item_id}: Invalid slot '{slot}'")

            stats = item.get('stats', {})
            if 'damage' in stats and not isinstance(stats['damage'], list):
                self.errors.append(f"{item_id}: 'damage' must be a list [min, max]")

    def print_results(self, filepath: str):
        """Print validation results"""
        is_valid, errors, warnings = self.validate_file(filepath)

        print(f"\n{'='*70}")
        print(f"Validation Results: {filepath}")
        print(f"{'='*70}")

        if is_valid:
            print(f" VALID - {len(self.seen_ids)} items checked")
        else:
            print(f"L INVALID - {len(errors)} errors found")

        if errors:
            print(f"\n=4 Errors ({len(errors)}):")
            for error in errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

        if warnings:
            print(f"\n   Warnings ({len(warnings)}):")
            for warning in warnings[:10]:  # Show first 10
                print(f"  - {warning}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")

        print(f"{'='*70}\n")

        return is_valid


# Example usage
if __name__ == "__main__":
    import sys

    validator = ItemValidator()

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = '../../items.JSON/items-smithing-1.JSON'

    validator.print_results(filepath)
