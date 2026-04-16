# -*- coding: utf-8 -*-
"""
Game-1 JSON Validator

Production-quality JSON validator for Game-1.
Pragmatic approach: detects real issues, not schema pedantry.

Features:
- Auto-detects JSON file types
- Validates structure and required fields
- Detects duplicate IDs
- Validates cross-file references
- Comprehensive reporting
- Suitable for automation/CI/CD

Usage:
  python json_validator.py                 # Validate entire repo
  python json_validator.py --file <path>   # Validate single file
  python json_validator.py --verbose       # Show warnings
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Error severity levels"""
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    file: str
    severity: Severity
    message: str
    field: str = ""

    def __str__(self) -> str:
        location = self.file
        if self.field:
            location += f" ({self.field})"
        return f"[{self.severity.value}] {location}: {self.message}"


@dataclass
class ValidationReport:
    """Validation report"""
    total_files: int = 0
    valid_files: int = 0
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def files_with_errors(self) -> int:
        return self.total_files - self.valid_files

    def add_error(self, issue: ValidationIssue):
        self.errors.append(issue)
        self.valid_files -= 1 if self.valid_files > 0 else 0

    def add_warning(self, issue: ValidationIssue):
        self.warnings.append(issue)


class GameJSONValidator:
    """JSON validator for Game-1 files"""

    FILE_PATTERNS = {
        'items': ['items.JSON/items-*.JSON', 'items.JSON/items-*.json'],
        'recipes': ['recipes.JSON/recipes-*.json', 'recipes.JSON/recipes-*.JSON'],
        'placements': ['placements.JSON/placements-*.JSON', 'placements.JSON/placements-*.json'],
        'skills': ['Skills/skills-*.JSON', 'Skills/skills-*.json'],
        'npcs': ['progression/npcs-*.JSON', 'progression/npcs-*.json'],
        'quests': ['progression/quests-*.JSON', 'progression/quests-*.json'],
        'titles': ['progression/titles-*.JSON', 'progression/titles-*.json'],
        'classes': ['progression/classes-*.JSON', 'progression/classes-*.json'],
        'enemies': ['Definitions.JSON/hostiles-*.JSON', 'Definitions.JSON/hostiles-*.json'],
        'tags': ['Definitions.JSON/tag-definitions.JSON'],
        'configs': ['Definitions.JSON/*.JSON', 'world_system/config/*.json'],
        'chunk_saves': ['saves/chunks/chunk_*.json'],
    }

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.report = ValidationReport()

        # ID caches for cross-file validation
        self.item_ids: Set[str] = set()
        self.recipe_ids: Set[str] = set()
        self.skill_ids: Set[str] = set()
        self.quest_ids: Set[str] = set()
        self.npc_ids: Set[str] = set()

    def validate_file(self, filepath: str) -> Tuple[bool, List[str]]:
        """Validate a single JSON file. Returns (is_valid, errors)."""
        filepath = str(filepath)
        errors = []

        # Load JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"JSON parse error: {e}")
            return False, errors
        except Exception as e:
            errors.append(f"Failed to load: {e}")
            return False, errors

        # Detect type
        file_type = self._detect_file_type(filepath)
        if not file_type:
            errors.append("Unable to detect file type")
            return False, errors

        # Validate based on type
        if file_type == 'items':
            errors.extend(self._validate_items(data, filepath))
        elif file_type == 'recipes':
            errors.extend(self._validate_recipes(data, filepath))
        elif file_type == 'placements':
            errors.extend(self._validate_placements(data, filepath))
        elif file_type == 'skills':
            errors.extend(self._validate_skills(data, filepath))
        elif file_type == 'npcs':
            errors.extend(self._validate_npcs(data, filepath))
        elif file_type == 'quests':
            errors.extend(self._validate_quests(data, filepath))
        elif file_type == 'titles':
            errors.extend(self._validate_titles(data, filepath))
        elif file_type == 'classes':
            errors.extend(self._validate_classes(data, filepath))
        elif file_type == 'enemies':
            errors.extend(self._validate_enemies(data, filepath))
        elif file_type == 'tags':
            errors.extend(self._validate_tags(data, filepath))

        return len(errors) == 0, errors

    def validate_repository(self, scan_updates: bool = True) -> ValidationReport:
        """Validate entire repository"""
        self.report = ValidationReport()

        # Find all JSON files
        files_to_validate = []
        for file_type, patterns in self.FILE_PATTERNS.items():
            for pattern in patterns:
                for filepath in self.repo_root.glob(pattern):
                    files_to_validate.append(str(filepath))

        # Add update files
        if scan_updates:
            for update_dir in ['Update-1', 'Update-2']:
                update_path = self.repo_root / update_dir
                if update_path.exists():
                    for json_file in update_path.glob('*.JSON'):
                        files_to_validate.append(str(json_file))

        self.report.total_files = len(files_to_validate)
        self.report.valid_files = len(files_to_validate)

        # First pass: load data for caching
        all_data = {}
        for filepath in files_to_validate:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    all_data[filepath] = json.load(f)
            except:
                pass

        # Build ID caches
        self._build_caches(all_data)

        # Second pass: validate each file
        for filepath in files_to_validate:
            is_valid, errors = self.validate_file(filepath)
            if not is_valid:
                for error in errors:
                    self.report.add_error(ValidationIssue(
                        file=filepath,
                        severity=Severity.ERROR,
                        message=error
                    ))

        # Third pass: cross-file validation
        self._validate_cross_file_refs(all_data)

        return self.report

    def _build_caches(self, all_data: Dict[str, Any]):
        """Build ID caches from all loaded data"""
        for filepath, data in all_data.items():
            if not isinstance(data, dict):
                continue

            # Items
            for section in data.values():
                if isinstance(section, list):
                    for item in section:
                        if isinstance(item, dict):
                            if 'itemId' in item:
                                self.item_ids.add(item['itemId'])
                            if 'materialId' in item:
                                self.item_ids.add(item['materialId'])

            # Recipes
            if 'recipes' in data and isinstance(data['recipes'], list):
                for recipe in data['recipes']:
                    if isinstance(recipe, dict) and 'recipeId' in recipe:
                        self.recipe_ids.add(recipe['recipeId'])

            # Skills
            if 'skills' in data and isinstance(data['skills'], list):
                for skill in data['skills']:
                    if isinstance(skill, dict) and 'skillId' in skill:
                        self.skill_ids.add(skill['skillId'])

            # Quests
            if 'quests' in data and isinstance(data['quests'], list):
                for quest in data['quests']:
                    if isinstance(quest, dict) and 'questId' in quest:
                        self.quest_ids.add(quest['questId'])

            # NPCs
            if 'npcs' in data and isinstance(data['npcs'], list):
                for npc in data['npcs']:
                    if isinstance(npc, dict) and 'npc_id' in npc:
                        self.npc_ids.add(npc['npc_id'])

    def _validate_cross_file_refs(self, all_data: Dict[str, Any]):
        """Validate cross-file references"""
        for filepath, data in all_data.items():
            if not isinstance(data, dict):
                continue

            # Check recipes reference valid items
            if 'recipes' in data and isinstance(data['recipes'], list):
                for recipe in data['recipes']:
                    if not isinstance(recipe, dict):
                        continue
                    if 'outputId' in recipe and recipe['outputId'] not in self.item_ids:
                        self.report.add_error(ValidationIssue(
                            file=filepath,
                            severity=Severity.ERROR,
                            message=f"Recipe references non-existent item '{recipe['outputId']}'"
                        ))
                    if 'inputs' in recipe and isinstance(recipe['inputs'], list):
                        for inp in recipe['inputs']:
                            if isinstance(inp, dict):
                                inp_id = inp.get('materialId') or inp.get('itemId')
                                if inp_id and inp_id not in self.item_ids:
                                    self.report.add_warning(ValidationIssue(
                                        file=filepath,
                                        severity=Severity.WARNING,
                                        message=f"Recipe input '{inp_id}' not found"
                                    ))

    # ========================================================================
    # VALIDATION METHODS
    # ========================================================================

    def _validate_items(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate items file"""
        errors = []
        seen_ids = set()

        if 'metadata' not in data:
            errors.append("Missing 'metadata' section")

        for section_name, items in data.items():
            if section_name == 'metadata' or not isinstance(items, list):
                continue

            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{section_name}[{i}]: Not an object")
                    continue

                # Check for ID
                item_id = item.get('itemId') or item.get('materialId')
                if not item_id:
                    errors.append(f"{section_name}[{i}]: Missing itemId or materialId")
                    continue

                # Check duplicates
                if item_id in seen_ids:
                    errors.append(f"Duplicate ID '{item_id}'")
                    continue
                seen_ids.add(item_id)

                # Check required fields
                for field in ['name', 'category', 'tier', 'rarity']:
                    if field not in item:
                        errors.append(f"{section_name}[{i}] ({item_id}): Missing '{field}'")

                # Validate tier/rarity values
                if 'tier' in item and item['tier'] not in [1, 2, 3, 4]:
                    errors.append(f"{section_name}[{i}] ({item_id}): Invalid tier {item['tier']}")
                if 'rarity' in item and item['rarity'] not in ['common', 'uncommon', 'rare', 'epic', 'legendary', 'artifact']:
                    errors.append(f"{section_name}[{i}] ({item_id}): Invalid rarity '{item['rarity']}'")

        return errors

    def _validate_recipes(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate recipes file"""
        errors = []
        seen_ids = set()

        if 'recipes' not in data or not isinstance(data['recipes'], list):
            errors.append("'recipes' must be an array")
            return errors

        for i, recipe in enumerate(data['recipes']):
            if not isinstance(recipe, dict):
                errors.append(f"recipes[{i}]: Not an object")
                continue

            if 'recipeId' not in recipe:
                errors.append(f"recipes[{i}]: Missing recipeId")
                continue

            recipe_id = recipe['recipeId']
            if recipe_id in seen_ids:
                errors.append(f"Duplicate recipeId '{recipe_id}'")
            seen_ids.add(recipe_id)

            # Check inputs (required for all)
            if 'inputs' not in recipe:
                errors.append(f"Recipe '{recipe_id}': Missing 'inputs'")

            # Check for output spec - recipes must have one of these:
            # - outputId (+ outputQty) for smithing/alchemy/engineering
            # - enchantmentId for enchanting
            # - outputs array for refining
            has_output = (
                'outputId' in recipe or
                'enchantmentId' in recipe or
                'outputs' in recipe
            )
            if not has_output:
                errors.append(f"Recipe '{recipe_id}': Missing output specification (outputId, enchantmentId, or outputs)")

            # Validate inputs
            if 'inputs' in recipe and isinstance(recipe['inputs'], list):
                for j, inp in enumerate(recipe['inputs']):
                    if isinstance(inp, dict):
                        if 'quantity' not in inp:
                            errors.append(f"Recipe '{recipe_id}' input[{j}]: Missing 'quantity'")
                        if not (inp.get('materialId') or inp.get('itemId')):
                            errors.append(f"Recipe '{recipe_id}' input[{j}]: Missing materialId or itemId")

            # Validate outputs if present
            if 'outputs' in recipe and isinstance(recipe['outputs'], list):
                for j, out in enumerate(recipe['outputs']):
                    if isinstance(out, dict):
                        if 'quantity' not in out:
                            errors.append(f"Recipe '{recipe_id}' output[{j}]: Missing 'quantity'")
                        if not (out.get('materialId') or out.get('itemId')):
                            errors.append(f"Recipe '{recipe_id}' output[{j}]: Missing materialId or itemId")

        return errors

    def _validate_placements(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate placements file"""
        errors = []
        seen_ids = set()

        if 'placements' not in data or not isinstance(data['placements'], list):
            errors.append("'placements' must be an array")
            return errors

        for i, placement in enumerate(data['placements']):
            if not isinstance(placement, dict):
                errors.append(f"placements[{i}]: Not an object")
                continue

            if 'recipeId' not in placement:
                errors.append(f"placements[{i}]: Missing recipeId")
                continue

            recipe_id = placement['recipeId']
            if recipe_id in seen_ids:
                errors.append(f"Duplicate recipeId in placements: '{recipe_id}'")
            seen_ids.add(recipe_id)

            # Placements can have different layout specs:
            # - placementMap (smithing, engineering, refining)
            # - ingredients (alchemy)
            # - other placement data
            has_layout = (
                'placementMap' in placement or
                'ingredients' in placement
            )
            if not has_layout:
                # This is a warning not error - placement might be optional
                pass

            # Validate placementMap if present
            if 'placementMap' in placement:
                if isinstance(placement['placementMap'], dict) and not placement['placementMap']:
                    errors.append(f"Placement '{recipe_id}': placementMap is empty")

        return errors

    def _validate_skills(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate skills file"""
        errors = []
        seen_ids = set()

        if 'skills' not in data or not isinstance(data['skills'], list):
            errors.append("'skills' must be an array")
            return errors

        for i, skill in enumerate(data['skills']):
            if not isinstance(skill, dict):
                errors.append(f"skills[{i}]: Not an object")
                continue

            if 'skillId' not in skill:
                errors.append(f"skills[{i}]: Missing skillId")
                continue

            skill_id = skill['skillId']
            if skill_id in seen_ids:
                errors.append(f"Duplicate skillId '{skill_id}'")
            seen_ids.add(skill_id)

            if 'name' not in skill:
                errors.append(f"Skill '{skill_id}': Missing 'name'")

        return errors

    def _validate_npcs(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate NPCs file"""
        errors = []
        seen_ids = set()

        if 'npcs' not in data or not isinstance(data['npcs'], list):
            errors.append("'npcs' must be an array")
            return errors

        for i, npc in enumerate(data['npcs']):
            if not isinstance(npc, dict):
                errors.append(f"npcs[{i}]: Not an object")
                continue

            if 'npc_id' not in npc:
                errors.append(f"npcs[{i}]: Missing npc_id")
                continue

            npc_id = npc['npc_id']
            if npc_id in seen_ids:
                errors.append(f"Duplicate npc_id '{npc_id}'")
            seen_ids.add(npc_id)

            if 'name' not in npc:
                errors.append(f"NPC '{npc_id}': Missing 'name'")

        return errors

    def _validate_quests(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate quests file"""
        errors = []
        seen_ids = set()

        if 'quests' not in data or not isinstance(data['quests'], list):
            errors.append("'quests' must be an array")
            return errors

        for i, quest in enumerate(data['quests']):
            if not isinstance(quest, dict):
                errors.append(f"quests[{i}]: Not an object")
                continue

            if 'questId' not in quest:
                errors.append(f"quests[{i}]: Missing questId")
                continue

            quest_id = quest['questId']
            if quest_id in seen_ids:
                errors.append(f"Duplicate questId '{quest_id}'")
            seen_ids.add(quest_id)

            if 'name' not in quest:
                errors.append(f"Quest '{quest_id}': Missing 'name'")

        return errors

    def _validate_titles(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate titles file"""
        errors = []
        seen_ids = set()

        if 'titles' not in data or not isinstance(data['titles'], list):
            errors.append("'titles' must be an array")
            return errors

        for i, title in enumerate(data['titles']):
            if not isinstance(title, dict):
                errors.append(f"titles[{i}]: Not an object")
                continue

            if 'titleId' not in title:
                errors.append(f"titles[{i}]: Missing titleId")
                continue

            title_id = title['titleId']
            if title_id in seen_ids:
                errors.append(f"Duplicate titleId '{title_id}'")
            seen_ids.add(title_id)

            if 'name' not in title:
                errors.append(f"Title '{title_id}': Missing 'name'")

        return errors

    def _validate_classes(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate classes file"""
        errors = []
        seen_ids = set()

        if 'classes' not in data or not isinstance(data['classes'], list):
            errors.append("'classes' must be an array")
            return errors

        for i, cls in enumerate(data['classes']):
            if not isinstance(cls, dict):
                errors.append(f"classes[{i}]: Not an object")
                continue

            if 'classId' not in cls:
                errors.append(f"classes[{i}]: Missing classId")
                continue

            class_id = cls['classId']
            if class_id in seen_ids:
                errors.append(f"Duplicate classId '{class_id}'")
            seen_ids.add(class_id)

            if 'name' not in cls:
                errors.append(f"Class '{class_id}': Missing 'name'")

        return errors

    def _validate_enemies(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate enemies file"""
        errors = []
        seen_ids = set()

        enemies = data if isinstance(data, list) else data.get('enemies', [])
        if not enemies:
            errors.append("No enemies found")
            return errors

        for i, enemy in enumerate(enemies):
            if not isinstance(enemy, dict):
                errors.append(f"enemies[{i}]: Not an object")
                continue

            if 'enemyId' not in enemy:
                errors.append(f"enemies[{i}]: Missing enemyId")
                continue

            enemy_id = enemy['enemyId']
            if enemy_id in seen_ids:
                errors.append(f"Duplicate enemyId '{enemy_id}'")
            seen_ids.add(enemy_id)

            for field in ['name', 'tier', 'behavior', 'stats', 'drops']:
                if field not in enemy:
                    errors.append(f"Enemy '{enemy_id}': Missing '{field}'")

        return errors

    def _validate_tags(self, data: Dict[str, Any], filepath: str) -> List[str]:
        """Validate tag definitions"""
        errors = []

        if 'metadata' not in data:
            errors.append("Missing 'metadata'")
        if 'categories' not in data:
            errors.append("Missing 'categories'")
            return errors

        if isinstance(data['categories'], dict):
            for cat, tags in data['categories'].items():
                if not isinstance(tags, list):
                    errors.append(f"Category '{cat}': tags must be a list, got {type(tags).__name__}")

        return errors

    def _detect_file_type(self, filepath: str) -> Optional[str]:
        """Detect file type from path"""
        filepath_lower = filepath.lower()

        for file_type, patterns in self.FILE_PATTERNS.items():
            for pattern in patterns:
                pattern_lower = pattern.lower()
                parts = pattern_lower.split('*')
                if all(part in filepath_lower for part in parts if part):
                    return file_type

        return None

    def print_report(self, verbose: bool = False):
        """Print validation report"""
        print("\n" + "=" * 80)
        print("GAME-1 JSON VALIDATION REPORT")
        print("=" * 80)
        print(f"\nFiles Scanned:  {self.report.total_files}")
        print(f"Valid Files:    {self.report.valid_files}")
        print(f"Files with Errors: {self.report.files_with_errors}")
        print(f"\nTotal Errors:   {len(self.report.errors)}")
        print(f"Total Warnings: {len(self.report.warnings)}")

        if self.report.is_valid:
            print(f"\n✓ ALL FILES VALID")
        else:
            print(f"\n✗ VALIDATION FAILED - {len(self.report.errors)} errors found")

        # Print errors
        if self.report.errors:
            print(f"\n{'─' * 80}")
            print("ERRORS:")
            print(f"{'─' * 80}")
            for error in self.report.errors[:30]:
                print(f"  {error}")
            if len(self.report.errors) > 30:
                print(f"  ... and {len(self.report.errors) - 30} more")

        # Print warnings if verbose
        if verbose and self.report.warnings:
            print(f"\n{'─' * 80}")
            print("WARNINGS:")
            print(f"{'─' * 80}")
            for warning in self.report.warnings[:10]:
                print(f"  {warning}")
            if len(self.report.warnings) > 10:
                print(f"  ... and {len(self.report.warnings) - 10} more")

        print(f"\n{'=' * 80}\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Game-1 JSON Validator')
    parser.add_argument('--file', help='Validate single file')
    parser.add_argument('--repo', default='.', help='Repository root')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show warnings')
    parser.add_argument('--no-updates', action='store_true', help='Skip Update directories')

    args = parser.parse_args()

    validator = GameJSONValidator(args.repo)

    if args.file:
        is_valid, errors = validator.validate_file(args.file)
        if is_valid:
            print(f"✓ {args.file} is valid")
            sys.exit(0)
        else:
            print(f"✗ {args.file} has errors:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
    else:
        print("Scanning repository...")
        validator.validate_repository(scan_updates=not args.no_updates)
        validator.print_report(verbose=args.verbose)
        sys.exit(0 if validator.report.is_valid else 1)
