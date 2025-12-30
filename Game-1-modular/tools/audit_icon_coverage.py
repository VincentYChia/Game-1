#!/usr/bin/env python3
"""
Icon Coverage Audit Tool

Scans all database JSONs and checks which items have icons vs missing icons.
Generates report and optionally creates missing placeholder icons.

Usage:
    python tools/audit_icon_coverage.py --report
    python tools/audit_icon_coverage.py --generate-missing
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class IconAuditor:
    def __init__(self):
        self.assets_dir = project_root / "assets"
        self.missing_icons: List[Tuple[str, str, str]] = []  # (item_id, category, expected_path)
        self.existing_icons: List[Tuple[str, str, str]] = []  # (item_id, category, icon_path)
        self.total_items = 0

    def check_icon_exists(self, icon_path: str) -> bool:
        """Check if icon file exists"""
        full_path = self.assets_dir / icon_path
        return full_path.exists()

    def audit_items_json(self, json_path: Path):
        """Audit items from items JSON files"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            for section_name, section_data in data.items():
                if section_name == 'metadata':
                    continue

                if not isinstance(section_data, list):
                    continue

                for item in section_data:
                    item_id = item.get('itemId')
                    if not item_id:
                        continue

                    self.total_items += 1

                    # Determine category
                    item_type = item.get('type', 'material')
                    category = item.get('category', item_type)

                    # Determine expected icon path
                    icon_path = item.get('iconPath')
                    if not icon_path:
                        # Auto-generate expected path based on category
                        if category in ['weapon', 'bow', 'staff', 'dagger', 'mace', 'sword']:
                            icon_path = f"items/weapon/{item_id}.png"
                        elif category in ['armor', 'helmet', 'chestplate', 'boots', 'gloves']:
                            icon_path = f"items/armor/{item_id}.png"
                        elif category in ['device', 'turret', 'trap', 'bomb']:
                            icon_path = f"items/device/{item_id}.png"
                        elif category in ['consumable', 'potion']:
                            icon_path = f"items/consumable/{item_id}.png"
                        elif category == 'station':
                            icon_path = f"items/station/{item_id}.png"
                        else:
                            icon_path = f"items/material/{item_id}.png"

                    # Check if icon exists
                    if self.check_icon_exists(icon_path):
                        self.existing_icons.append((item_id, category, icon_path))
                    else:
                        self.missing_icons.append((item_id, category, icon_path))

        except Exception as e:
            print(f"⚠️  Error auditing {json_path.name}: {e}")

    def audit_skills_json(self, json_path: Path):
        """Audit skills from skills JSON files"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            for skill in data.get('skills', []):
                skill_id = skill.get('skillId')
                if not skill_id:
                    continue

                self.total_items += 1

                icon_path = skill.get('iconPath', f"skills/{skill_id}.png")

                if self.check_icon_exists(icon_path):
                    self.existing_icons.append((skill_id, 'skill', icon_path))
                else:
                    self.missing_icons.append((skill_id, 'skill', icon_path))

        except Exception as e:
            print(f"⚠️  Error auditing {json_path.name}: {e}")

    def audit_enemies_json(self, json_path: Path):
        """Audit enemies from hostiles JSON files"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            for enemy in data.get('enemies', []):
                enemy_id = enemy.get('enemyId')
                if not enemy_id:
                    continue

                self.total_items += 1

                icon_path = enemy.get('iconPath', f"enemies/{enemy_id}.png")

                if self.check_icon_exists(icon_path):
                    self.existing_icons.append((enemy_id, 'enemy', icon_path))
                else:
                    self.missing_icons.append((enemy_id, 'enemy', icon_path))

        except Exception as e:
            print(f"⚠️  Error auditing {json_path.name}: {e}")

    def run_audit(self):
        """Run complete audit across all content"""
        print("🔍 Auditing Icon Coverage...\n")

        # Audit items
        items_dir = project_root / "items.JSON"
        if items_dir.exists():
            for json_file in items_dir.glob("*.JSON"):
                self.audit_items_json(json_file)

        # Audit skills
        skills_dir = project_root / "Skills"
        if skills_dir.exists():
            for json_file in skills_dir.glob("*.JSON"):
                self.audit_skills_json(json_file)

        # Audit enemies
        definitions_dir = project_root / "Definitions.JSON"
        if definitions_dir.exists():
            for json_file in definitions_dir.glob("hostiles*.JSON"):
                self.audit_enemies_json(json_file)

        # Audit Update-N content
        for update_dir in project_root.glob("Update-*"):
            if update_dir.is_dir():
                for json_file in update_dir.glob("*.JSON"):
                    filename = json_file.name.lower()
                    if 'items' in filename or 'weapons' in filename:
                        self.audit_items_json(json_file)
                    elif 'skills' in filename:
                        self.audit_skills_json(json_file)
                    elif 'hostiles' in filename or 'enemies' in filename:
                        self.audit_enemies_json(json_file)

    def print_report(self):
        """Print detailed coverage report"""
        total = len(self.existing_icons) + len(self.missing_icons)
        coverage_pct = (len(self.existing_icons) / total * 100) if total > 0 else 0

        print("\n" + "="*70)
        print("📊 ICON COVERAGE REPORT")
        print("="*70)
        print(f"\nTotal Items Scanned: {self.total_items}")
        print(f"Icons Found: {len(self.existing_icons)}")
        print(f"Icons Missing: {len(self.missing_icons)}")
        print(f"Coverage: {coverage_pct:.1f}%")

        if self.missing_icons:
            print("\n" + "="*70)
            print("❌ MISSING ICONS")
            print("="*70)

            # Group by category
            by_category: Dict[str, List[Tuple[str, str]]] = {}
            for item_id, category, icon_path in self.missing_icons:
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append((item_id, icon_path))

            for category in sorted(by_category.keys()):
                items = by_category[category]
                print(f"\n{category.upper()} ({len(items)} missing):")
                for item_id, icon_path in items[:10]:  # Show first 10
                    print(f"   - {item_id}: {icon_path}")
                if len(items) > 10:
                    print(f"   ... and {len(items) - 10} more")

        print("\n" + "="*70)

    def generate_missing_icons(self):
        """Generate placeholder icons for all missing items"""
        if not self.missing_icons:
            print("✅ No missing icons to generate!")
            return

        print(f"\n🎨 Generating {len(self.missing_icons)} placeholder icons...\n")

        # Import icon generation utilities
        sys.path.insert(0, str(project_root / "tools"))
        from create_placeholder_icons_simple import create_minimal_png, COLOR_SCHEMES

        generated = 0
        errors = []

        for item_id, category, icon_path in self.missing_icons:
            try:
                # Determine color scheme
                if category in ['weapon', 'bow', 'staff', 'dagger', 'mace', 'sword']:
                    color = COLOR_SCHEMES.get('weapon', (180, 50, 50))
                elif category in ['armor', 'helmet', 'chestplate', 'boots']:
                    color = COLOR_SCHEMES.get('armor', (50, 100, 180))
                elif category in ['device', 'turret', 'trap', 'bomb']:
                    color = COLOR_SCHEMES.get('device', (200, 100, 200))
                elif category in ['consumable', 'potion']:
                    color = COLOR_SCHEMES.get('consumable', (80, 180, 80))
                elif category == 'skill':
                    color = COLOR_SCHEMES.get('skill', (100, 200, 200))
                elif category == 'enemy':
                    color = COLOR_SCHEMES.get('enemy', (220, 80, 80))
                else:
                    color = COLOR_SCHEMES.get('material', (150, 150, 150))

                # Create icon
                output_path = self.assets_dir / icon_path
                create_minimal_png(output_path, 64, 64, color)
                generated += 1

            except Exception as e:
                errors.append((item_id, str(e)))

        print(f"\n✅ Generated {generated} placeholder icons")

        if errors:
            print(f"\n⚠️  {len(errors)} errors:")
            for item_id, error in errors[:5]:
                print(f"   - {item_id}: {error}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Audit icon coverage across all game content')
    parser.add_argument('--report', action='store_true', help='Generate coverage report')
    parser.add_argument('--generate-missing', action='store_true', help='Generate missing placeholder icons')
    parser.add_argument('--all', action='store_true', help='Run report and generate missing icons')

    args = parser.parse_args()

    if not args.report and not args.generate_missing and not args.all:
        parser.print_help()
        return 1

    auditor = IconAuditor()
    auditor.run_audit()

    if args.report or args.all:
        auditor.print_report()

    if args.generate_missing or args.all:
        auditor.generate_missing_icons()

    return 0


if __name__ == '__main__':
    sys.exit(main())
