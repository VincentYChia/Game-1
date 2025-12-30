#!/usr/bin/env python3
"""
Update Manager - Handles installation/uninstallation of Update-N packages

This system allows mass JSON production without modifying core game files.
All new content goes in Update-N directories and gets auto-discovered.

Usage:
    python tools/update_manager.py install Update-1
    python tools/update_manager.py uninstall Update-1
    python tools/update_manager.py list
    python tools/update_manager.py validate Update-1
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class UpdateManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.manifest_path = project_root / "updates_manifest.json"
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load or create updates manifest"""
        if self.manifest_path.exists():
            with open(self.manifest_path, 'r') as f:
                return json.load(f)
        return {
            "version": "1.0",
            "installed_updates": [],
            "schema_version": 1,
            "last_updated": None
        }

    def _save_manifest(self):
        """Save updates manifest"""
        self.manifest["last_updated"] = datetime.now().isoformat()
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def validate_update(self, update_name: str) -> Tuple[bool, List[str]]:
        """Validate an update package before installation"""
        update_dir = self.project_root / update_name
        errors = []

        if not update_dir.exists():
            return False, [f"Update directory not found: {update_dir}"]

        # Check for valid JSON files
        json_files = list(update_dir.glob("*.JSON"))
        if not json_files:
            errors.append(f"No .JSON files found in {update_name}/")

        # Validate each JSON file
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                # Check for metadata
                if 'metadata' not in data:
                    errors.append(f"{json_file.name}: Missing 'metadata' section")

                # Check for content
                content_keys = [k for k in data.keys() if k != 'metadata']
                if not content_keys:
                    errors.append(f"{json_file.name}: No content sections found")

            except json.JSONDecodeError as e:
                errors.append(f"{json_file.name}: Invalid JSON - {e}")
            except Exception as e:
                errors.append(f"{json_file.name}: {e}")

        return len(errors) == 0, errors

    def check_conflicts(self, update_name: str) -> List[str]:
        """Check for ID conflicts with existing content"""
        update_dir = self.project_root / update_name
        conflicts = []

        # Load all IDs from the update
        update_ids = {
            'items': set(),
            'skills': set(),
            'enemies': set()
        }

        for json_file in update_dir.glob("*.JSON"):
            with open(json_file, 'r') as f:
                data = json.load(f)

            # Extract IDs based on file type
            if 'items' in json_file.name.lower() or 'test_weapons' in data:
                items = data.get('items', data.get('test_weapons', []))
                for item in items:
                    if 'itemId' in item:
                        update_ids['items'].add(item['itemId'])

            if 'skills' in json_file.name.lower():
                skills = data.get('skills', [])
                for skill in skills:
                    if 'skillId' in skill:
                        update_ids['skills'].add(skill['skillId'])

            if 'hostiles' in json_file.name.lower() or 'enemies' in json_file.name.lower():
                enemies = data.get('enemies', [])
                for enemy in enemies:
                    if 'enemyId' in enemy:
                        update_ids['enemies'].add(enemy['enemyId'])

        # Check against core game files (basic check)
        # TODO: Full database scan
        core_files = {
            'items': list(self.project_root.glob('items.JSON/*.JSON')),
            'skills': list(self.project_root.glob('Skills/*.JSON')),
            'enemies': list(self.project_root.glob('Definitions.JSON/hostiles-*.JSON'))
        }

        for category, files in core_files.items():
            for core_file in files:
                try:
                    with open(core_file, 'r') as f:
                        data = json.load(f)

                    # Check for conflicts
                    if category == 'items':
                        items = data.get('items', data.get('weapons', data.get('armor', [])))
                        for item in items:
                            item_id = item.get('itemId')
                            if item_id and item_id in update_ids['items']:
                                conflicts.append(f"Item ID conflict: {item_id} (exists in {core_file.name})")

                    elif category == 'skills':
                        skills = data.get('skills', [])
                        for skill in skills:
                            skill_id = skill.get('skillId')
                            if skill_id and skill_id in update_ids['skills']:
                                conflicts.append(f"Skill ID conflict: {skill_id} (exists in {core_file.name})")

                    elif category == 'enemies':
                        enemies = data.get('enemies', [])
                        for enemy in enemies:
                            enemy_id = enemy.get('enemyId')
                            if enemy_id and enemy_id in update_ids['enemies']:
                                conflicts.append(f"Enemy ID conflict: {enemy_id} (exists in {core_file.name})")

                except:
                    pass  # Skip files that fail to load

        return conflicts

    def install_update(self, update_name: str, force: bool = False) -> bool:
        """Install an update package"""
        print(f"\n📦 Installing {update_name}...\n")

        # Check if already installed
        if update_name in self.manifest['installed_updates']:
            if not force:
                print(f"⚠️  {update_name} is already installed. Use --force to reinstall.")
                return False
            else:
                print(f"♻️  Reinstalling {update_name} (--force enabled)")

        # Validate update
        print("1️⃣  Validating update package...")
        valid, errors = self.validate_update(update_name)
        if not valid:
            print(f"❌ Validation failed:")
            for error in errors:
                print(f"   - {error}")
            return False
        print(f"   ✅ Validation passed")

        # Check conflicts
        print("\n2️⃣  Checking for ID conflicts...")
        conflicts = self.check_conflicts(update_name)
        if conflicts and not force:
            print(f"❌ Conflicts detected:")
            for conflict in conflicts:
                print(f"   - {conflict}")
            print(f"\n💡 Use --force to install anyway (conflicts will be overridden)")
            return False
        elif conflicts:
            print(f"⚠️  {len(conflicts)} conflicts found, but --force enabled")
        else:
            print(f"   ✅ No conflicts found")

        # Install (just update manifest - databases will auto-discover)
        print(f"\n3️⃣  Registering update...")
        if update_name not in self.manifest['installed_updates']:
            self.manifest['installed_updates'].append(update_name)
        self._save_manifest()

        print(f"\n✅ {update_name} installed successfully!")
        print(f"\n📝 Note: Databases will auto-discover content on next game launch.")
        print(f"   No manual file copying needed!")

        return True

    def uninstall_update(self, update_name: str) -> bool:
        """Uninstall an update package"""
        print(f"\n🗑️  Uninstalling {update_name}...\n")

        if update_name not in self.manifest['installed_updates']:
            print(f"⚠️  {update_name} is not installed")
            return False

        # Remove from manifest
        self.manifest['installed_updates'].remove(update_name)
        self._save_manifest()

        print(f"✅ {update_name} uninstalled")
        print(f"📝 Content will not be loaded on next game launch")

        return True

    def list_updates(self):
        """List all available and installed updates"""
        print("\n📦 Update Packages:\n")

        # Find all Update-N directories
        update_dirs = sorted([d for d in self.project_root.iterdir()
                             if d.is_dir() and d.name.startswith('Update-')])

        if not update_dirs:
            print("   No Update-N directories found")
            return

        installed = set(self.manifest['installed_updates'])

        for update_dir in update_dirs:
            status = "✅ INSTALLED" if update_dir.name in installed else "⭕ Available"

            # Count files
            json_files = list(update_dir.glob("*.JSON"))

            print(f"{status} {update_dir.name}/")
            print(f"          {len(json_files)} JSON file(s)")

            # Show file names
            for json_file in json_files:
                print(f"            - {json_file.name}")
            print()


def main():
    parser = argparse.ArgumentParser(description='Manage Update-N packages')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Install command
    install_parser = subparsers.add_parser('install', help='Install an update')
    install_parser.add_argument('update', help='Update name (e.g., Update-1)')
    install_parser.add_argument('--force', action='store_true', help='Force installation (ignore conflicts)')

    # Uninstall command
    uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall an update')
    uninstall_parser.add_argument('update', help='Update name (e.g., Update-1)')

    # List command
    list_parser = subparsers.add_parser('list', help='List all updates')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate an update without installing')
    validate_parser.add_argument('update', help='Update name (e.g., Update-1)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    manager = UpdateManager(project_root)

    if args.command == 'install':
        success = manager.install_update(args.update, force=args.force)
        return 0 if success else 1

    elif args.command == 'uninstall':
        success = manager.uninstall_update(args.update)
        return 0 if success else 1

    elif args.command == 'list':
        manager.list_updates()
        return 0

    elif args.command == 'validate':
        print(f"\n🔍 Validating {args.update}...\n")
        valid, errors = manager.validate_update(args.update)
        conflicts = manager.check_conflicts(args.update)

        if valid and not conflicts:
            print(f"✅ {args.update} is valid and ready to install")
            return 0
        else:
            if errors:
                print(f"❌ Validation errors:")
                for error in errors:
                    print(f"   - {error}")
            if conflicts:
                print(f"⚠️  Conflicts detected:")
                for conflict in conflicts:
                    print(f"   - {conflict}")
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
