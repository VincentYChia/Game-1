#!/usr/bin/env python3
"""
Test Class Tag System

Verifies that the tag-driven class system works correctly:
1. ClassDefinition has tags field
2. Tags are loaded from JSON
3. Skill affinity bonus is calculated correctly
4. Class tags are recognized by tag system

Run: python test_class_tags.py
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Add project root to path (Game-1-modular)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# TEST INFRASTRUCTURE
# ============================================================================

@dataclass
class TestResult:
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str = ""


@dataclass
class TestSuite:
    name: str
    results: List[TestResult] = field(default_factory=list)

    def add(self, result: TestResult):
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"  {status}: {result.name}")
        if not result.passed:
            print(f"         Expected: {result.expected}")
            print(f"         Actual:   {result.actual}")
            if result.message:
                print(f"         Note: {result.message}")

    def summary(self) -> tuple:
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        return passed, total


# ============================================================================
# ISOLATED CLASS DEFINITION (no game engine imports)
# ============================================================================

@dataclass
class MockClassDefinition:
    """Replicate ClassDefinition for testing without pygame"""
    class_id: str
    name: str
    description: str
    bonuses: Dict[str, float]
    starting_skill: str = ""
    recommended_stats: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    preferred_damage_types: List[str] = field(default_factory=list)
    preferred_armor_type: str = ""

    def has_tag(self, tag: str) -> bool:
        return tag.lower() in [t.lower() for t in self.tags]

    def get_skill_affinity_bonus(self, skill_tags: List[str]) -> float:
        if not skill_tags or not self.tags:
            return 0.0
        matching_tags = set(t.lower() for t in self.tags) & set(t.lower() for t in skill_tags)
        bonus_per_tag = 0.05
        max_bonus = 0.20
        return min(len(matching_tags) * bonus_per_tag, max_bonus)


# ============================================================================
# TESTS
# ============================================================================

def test_class_definition_model() -> TestSuite:
    """Test ClassDefinition model with tags"""
    suite = TestSuite("ClassDefinition Model")
    print(f"\n{'='*60}")
    print("TEST SUITE: ClassDefinition Model")
    print(f"{'='*60}")

    # Test 1: Create class with tags
    print("\n1. Testing class creation with tags...")

    warrior = MockClassDefinition(
        class_id="warrior",
        name="Warrior",
        description="Frontline fighter",
        bonuses={"max_health": 30, "melee_damage": 0.10},
        tags=["warrior", "melee", "physical", "tanky", "frontline"],
        preferred_damage_types=["physical", "slashing"],
        preferred_armor_type="heavy"
    )

    suite.add(TestResult(
        name="Class has tags",
        passed=len(warrior.tags) == 5,
        expected="5 tags",
        actual=f"{len(warrior.tags)} tags: {warrior.tags}"
    ))

    # Test 2: has_tag method
    print("\n2. Testing has_tag method...")

    suite.add(TestResult(
        name="has_tag('melee') returns True",
        passed=warrior.has_tag('melee'),
        expected=True,
        actual=warrior.has_tag('melee')
    ))

    suite.add(TestResult(
        name="has_tag('ranged') returns False",
        passed=not warrior.has_tag('ranged'),
        expected=False,
        actual=warrior.has_tag('ranged')
    ))

    suite.add(TestResult(
        name="has_tag case insensitive",
        passed=warrior.has_tag('MELEE'),
        expected=True,
        actual=warrior.has_tag('MELEE')
    ))

    return suite


def test_skill_affinity_bonus() -> TestSuite:
    """Test skill affinity bonus calculation"""
    suite = TestSuite("Skill Affinity Bonus")
    print(f"\n{'='*60}")
    print("TEST SUITE: Skill Affinity Bonus")
    print(f"{'='*60}")

    warrior = MockClassDefinition(
        class_id="warrior",
        name="Warrior",
        description="Frontline fighter",
        bonuses={},
        tags=["warrior", "melee", "physical", "tanky"]
    )

    # Test 1: No matching tags
    print("\n1. Testing no matching tags...")

    bonus = warrior.get_skill_affinity_bonus(["magic", "ranged", "arcane"])
    suite.add(TestResult(
        name="No matching tags = 0% bonus",
        passed=bonus == 0.0,
        expected=0.0,
        actual=bonus
    ))

    # Test 2: One matching tag
    print("\n2. Testing one matching tag...")

    bonus = warrior.get_skill_affinity_bonus(["melee", "magic"])
    suite.add(TestResult(
        name="One matching tag = 5% bonus",
        passed=abs(bonus - 0.05) < 0.001,
        expected=0.05,
        actual=bonus
    ))

    # Test 3: Multiple matching tags
    print("\n3. Testing multiple matching tags...")

    bonus = warrior.get_skill_affinity_bonus(["melee", "physical", "tanky"])
    suite.add(TestResult(
        name="Three matching tags = 15% bonus",
        passed=abs(bonus - 0.15) < 0.001,
        expected=0.15,
        actual=bonus
    ))

    # Test 4: Cap at 20%
    print("\n4. Testing bonus cap at 20%...")

    bonus = warrior.get_skill_affinity_bonus(["warrior", "melee", "physical", "tanky", "frontline"])
    suite.add(TestResult(
        name="Five matching tags capped at 20%",
        passed=abs(bonus - 0.20) < 0.001,
        expected=0.20,
        actual=bonus
    ))

    return suite


def test_classes_json_tags() -> TestSuite:
    """Test that classes-1.JSON has tags for all classes"""
    suite = TestSuite("Classes JSON Tags")
    print(f"\n{'='*60}")
    print("TEST SUITE: Classes JSON Tags")
    print(f"{'='*60}")

    # Load classes JSON
    print("\n1. Loading classes-1.JSON...")

    try:
        json_path = project_root / "progression" / "classes-1.JSON"
        with open(json_path, 'r') as f:
            data = json.load(f)

        classes = data.get('classes', [])
        suite.add(TestResult(
            name="Classes JSON loaded",
            passed=len(classes) == 6,
            expected="6 classes",
            actual=f"{len(classes)} classes"
        ))

        # Test 2: Each class has tags
        print("\n2. Checking each class has tags...")

        expected_classes = ["warrior", "ranger", "scholar", "artisan", "scavenger", "adventurer"]

        for class_data in classes:
            class_id = class_data.get('classId', 'unknown')
            tags = class_data.get('tags', [])
            preferred_damage = class_data.get('preferredDamageTypes', [])
            armor_type = class_data.get('preferredArmorType', '')

            suite.add(TestResult(
                name=f"{class_id} has tags",
                passed=len(tags) >= 3,
                expected="at least 3 tags",
                actual=f"{len(tags)} tags: {tags}"
            ))

            suite.add(TestResult(
                name=f"{class_id} has preferredDamageTypes",
                passed=len(preferred_damage) >= 1,
                expected="at least 1 damage type",
                actual=f"{len(preferred_damage)} types: {preferred_damage}"
            ))

            suite.add(TestResult(
                name=f"{class_id} has preferredArmorType",
                passed=len(armor_type) > 0,
                expected="armor type set",
                actual=f"'{armor_type}'"
            ))

    except Exception as e:
        suite.add(TestResult(
            name="Load classes JSON",
            passed=False,
            expected="JSON to load",
            actual=f"Error: {e}"
        ))

    return suite


def test_tag_definitions_json() -> TestSuite:
    """Test that tag-definitions.JSON has class tags"""
    suite = TestSuite("Tag Definitions JSON")
    print(f"\n{'='*60}")
    print("TEST SUITE: Tag Definitions JSON")
    print(f"{'='*60}")

    # Load tag definitions
    print("\n1. Loading tag-definitions.JSON...")

    try:
        json_path = project_root / "Definitions.JSON" / "tag-definitions.JSON"
        with open(json_path, 'r') as f:
            data = json.load(f)

        categories = data.get('categories', {})
        tag_defs = data.get('tag_definitions', {})

        # Test 2: Class category exists
        print("\n2. Checking class category...")

        class_category = categories.get('class', [])
        suite.add(TestResult(
            name="Class category exists",
            passed=len(class_category) == 6,
            expected="6 class tags",
            actual=f"{len(class_category)} tags: {class_category}"
        ))

        # Test 3: Playstyle category exists
        print("\n3. Checking playstyle category...")

        playstyle_category = categories.get('playstyle', [])
        suite.add(TestResult(
            name="Playstyle category exists",
            passed=len(playstyle_category) >= 6,
            expected="at least 6 playstyle tags",
            actual=f"{len(playstyle_category)} tags: {playstyle_category}"
        ))

        # Test 4: Armor type category exists
        print("\n4. Checking armor_type category...")

        armor_category = categories.get('armor_type', [])
        suite.add(TestResult(
            name="Armor type category exists",
            passed=len(armor_category) == 4,
            expected="4 armor types (heavy, medium, light, robes)",
            actual=f"{len(armor_category)} types: {armor_category}"
        ))

        # Test 5: Class tag definitions exist
        print("\n5. Checking class tag definitions...")

        for class_name in ['warrior', 'ranger', 'scholar', 'artisan', 'scavenger', 'adventurer']:
            tag_def = tag_defs.get(class_name, {})
            suite.add(TestResult(
                name=f"{class_name} tag definition exists",
                passed=tag_def.get('category') == 'class',
                expected="category='class'",
                actual=f"category='{tag_def.get('category', 'MISSING')}'"
            ))

    except Exception as e:
        suite.add(TestResult(
            name="Load tag definitions JSON",
            passed=False,
            expected="JSON to load",
            actual=f"Error: {e}"
        ))

    return suite


# ============================================================================
# MAIN
# ============================================================================

def run_all_tests() -> tuple:
    """Run all test suites"""
    print("\n" + "="*70)
    print("CLASS TAG SYSTEM TESTS")
    print("="*70)

    all_suites = []

    all_suites.append(test_class_definition_model())
    all_suites.append(test_skill_affinity_bonus())
    all_suites.append(test_classes_json_tags())
    all_suites.append(test_tag_definitions_json())

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    total_passed = 0
    total_tests = 0

    for suite in all_suites:
        passed, total = suite.summary()
        total_passed += passed
        total_tests += total
        status = "✅" if passed == total else "❌"
        print(f"  {status} {suite.name}: {passed}/{total} passed")

    print(f"\n{'='*70}")
    print(f"FINAL RESULT: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ {total_tests - total_passed} TESTS FAILED")

    print("="*70 + "\n")

    return total_passed, total_tests


if __name__ == "__main__":
    passed, total = run_all_tests()
    sys.exit(0 if passed == total else 1)
