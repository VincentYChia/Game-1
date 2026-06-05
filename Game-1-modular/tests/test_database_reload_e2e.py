"""E2E tests for the Phase 0 G07 database reload pattern (2026-06-03).

Five databases gained ``load_from_files()`` + ``reload()`` in this phase:
``MaterialDatabase``, ``EnemyDatabase``, ``ResourceNodeDatabase``,
``SkillDatabase``, ``TitleDatabase``. Each test follows the same shape:

1. Reset the singleton to get a clean slate.
2. Call ``load_from_files()`` to populate from sacred.
3. Write a temp ``<tool>-generated-<suffix>.JSON`` file with a sentinel
   entry that the sacred files don't have.
4. Call ``reload()``.
5. Assert the sentinel entry is now in the database.
6. Clean up the temp file.

Plus one cross-cutting test: ``reload_for_tools`` publishes
``EVT_DATABASE_RELOADED`` to the :class:`GameEventBus` per consolidation
§6 Phase 0 ship criterion.

Sacred files are NEVER touched. Temp files use unique sentinel suffixes
that won't collide with real generated content.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from typing import List

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)


# ── shared helpers ─────────────────────────────────────────────────────


def _write_generated(relpath: str, payload: dict) -> Path:
    """Write a generated JSON file at ``relpath`` (relative to project
    root). Caller is responsible for tracking + cleanup."""
    path = Path(relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def _cleanup(paths: List[Path]) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


# ── MaterialDatabase ───────────────────────────────────────────────────


class MaterialReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.material_db import MaterialDatabase
        MaterialDatabase.reset()
        self.db = MaterialDatabase.get_instance()
        self.db.load_from_files()
        self._temp_files: List[Path] = []

    def tearDown(self) -> None:
        _cleanup(self._temp_files)
        from data.databases.material_db import MaterialDatabase
        MaterialDatabase.reset()

    def test_sacred_load_populates(self) -> None:
        # The 7-call boot is now driven by SACRED_LOAD_SEQUENCE; assert
        # at least one material from each major category landed.
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.materials), 0,
                           "load_from_files should populate from sacred")

    def test_reload_picks_up_generated_file(self) -> None:
        sentinel_id = "moors_copper_reload_sentinel_g07b"
        path = _write_generated(
            "items.JSON/items-materials-generated-reload-test.JSON",
            {"materials": [{
                "materialId": sentinel_id,
                "name": "Moors Copper (Reload Sentinel)",
                "tier": 2,
                "category": "ore",
                "rarity": "uncommon",
                "description": "test material; cleaned up after assertion",
                "maxStack": 99,
            }]},
        )
        self._temp_files.append(path)

        # Sentinel not present pre-reload
        self.assertNotIn(sentinel_id, self.db.materials)

        self.db.reload()
        self.assertIn(sentinel_id, self.db.materials,
                      "reload() should overlay the generated file")
        mat = self.db.materials[sentinel_id]
        self.assertEqual(mat.tier, 2)
        self.assertEqual(mat.category, "ore")

    def test_reload_preserves_state_on_malformed_payload(self) -> None:
        # Snapshot baseline
        baseline_count = len(self.db.materials)
        self.assertGreater(baseline_count, 0)

        # Write malformed JSON into the generated overlay slot
        path = Path(
            "items.JSON/items-materials-generated-broken-g07b.JSON"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json")
        self._temp_files.append(path)

        self.db.reload()
        # Reload may skip the bad file but sacred should still be intact.
        self.assertGreaterEqual(len(self.db.materials), baseline_count,
                                "malformed generated must not empty the db")


# ── EnemyDatabase ──────────────────────────────────────────────────────


class EnemyReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        from Combat.enemy import EnemyDatabase
        EnemyDatabase.reset()
        self.db = EnemyDatabase.get_instance()
        self.db.load_from_files()
        self._temp_files: List[Path] = []

    def tearDown(self) -> None:
        _cleanup(self._temp_files)
        from Combat.enemy import EnemyDatabase
        EnemyDatabase.reset()

    def test_sacred_load_populates(self) -> None:
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.enemies), 0,
                           "load_from_files should populate from sacred")

    def test_reload_picks_up_generated_file(self) -> None:
        sentinel_id = "moors_raider_reload_sentinel_g07c"
        path = _write_generated(
            "Definitions.JSON/hostiles-generated-reload-test.JSON",
            {"enemies": [{
                "enemyId": sentinel_id,
                "name": "Moors Raider (Reload Sentinel)",
                "tier": 2,
                "biome": "moors",
                "stats": {"health": 200, "damage": [10, 15], "defense": 5},
                "aiPattern": {"behavior": "aggressive"},
                "drops": [],
                "specialAbilities": [],
                "tags": [],
            }]},
        )
        self._temp_files.append(path)

        self.assertNotIn(sentinel_id, self.db.enemies)
        self.db.reload()
        self.assertIn(sentinel_id, self.db.enemies,
                      "reload() should overlay the generated file")

    def test_reload_clears_per_tier_index(self) -> None:
        # Critical: load_from_file APPENDS to enemies_by_tier. Without
        # the clear in load_from_files, a reload would multiply counts.
        before_per_tier = {
            k: len(v) for k, v in self.db.enemies_by_tier.items()
        }
        self.db.reload()
        after_per_tier = {
            k: len(v) for k, v in self.db.enemies_by_tier.items()
        }
        self.assertEqual(before_per_tier, after_per_tier,
                         "reload must not multiply enemies_by_tier counts")


# ── ResourceNodeDatabase ───────────────────────────────────────────────


class NodeReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.resource_node_db import ResourceNodeDatabase
        ResourceNodeDatabase.reset()
        self.db = ResourceNodeDatabase.get_instance()
        self.db.load_from_files()
        self._temp_files: List[Path] = []

    def tearDown(self) -> None:
        _cleanup(self._temp_files)
        from data.databases.resource_node_db import ResourceNodeDatabase
        ResourceNodeDatabase.reset()

    def test_sacred_load_populates(self) -> None:
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.nodes), 0)

    def test_reload_picks_up_generated_file(self) -> None:
        sentinel_id = "moors_copper_seam_reload_sentinel_g07d"
        path = _write_generated(
            "Definitions.JSON/Resource-node-generated-reload-test.JSON",
            {"nodes": [{
                "resourceId": sentinel_id,
                "name": "Moors Copper Seam (Reload Sentinel)",
                "category": "ore",
                "tier": 2,
                "requiredTool": "pickaxe",
                "baseHealth": 200,
                "drops": [{"materialId": "moors_copper",
                           "quantity": "several",
                           "chance": "guaranteed"}],
                "metadata": {"tags": [], "narrative": ""},
            }]},
        )
        self._temp_files.append(path)

        self.assertNotIn(sentinel_id, self.db.nodes)
        self.db.reload()
        self.assertIn(sentinel_id, self.db.nodes)

    def test_reload_clears_category_caches(self) -> None:
        # Critical: load_from_file APPENDS to _trees / _ores / _stones
        # caches. Without the clear, counts multiply on each reload.
        before = (len(self.db._trees), len(self.db._ores),
                  len(self.db._stones))
        self.db.reload()
        after = (len(self.db._trees), len(self.db._ores),
                 len(self.db._stones))
        self.assertEqual(before, after,
                         "reload must not multiply category cache counts")


# ── SkillDatabase ──────────────────────────────────────────────────────


class SkillReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.skill_db import SkillDatabase
        SkillDatabase.reset()
        self.db = SkillDatabase.get_instance()
        self.db.load_from_files()
        self._temp_files: List[Path] = []

    def tearDown(self) -> None:
        _cleanup(self._temp_files)
        from data.databases.skill_db import SkillDatabase
        SkillDatabase.reset()

    def test_sacred_load_populates(self) -> None:
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.skills), 0)

    def test_reload_picks_up_generated_file(self) -> None:
        sentinel_id = "copperlash_gash_reload_sentinel_g07e"
        path = _write_generated(
            "Skills/skills-generated-reload-test.JSON",
            {"skills": [{
                "skillId": sentinel_id,
                "name": "Copperlash Gash (Reload Sentinel)",
                "tier": 2,
                "rarity": "uncommon",
                "categories": ["melee", "bleed"],
                "description": "test skill; cleaned up after assertion",
                "narrative": "for the moors",
                "tags": [],
                "effect": {"type": "damage", "category": "melee",
                           "magnitude": "moderate"},
                "cost": {"mana": "moderate", "cooldown": "moderate"},
                "evolution": {"canEvolve": False},
                "requirements": {"characterLevel": 1, "stats": {},
                                 "titles": []},
            }]},
        )
        self._temp_files.append(path)

        self.assertNotIn(sentinel_id, self.db.skills)
        self.db.reload()
        self.assertIn(sentinel_id, self.db.skills)


# ── TitleDatabase ──────────────────────────────────────────────────────


class TitleReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.title_db import TitleDatabase
        TitleDatabase.reset()
        self.db = TitleDatabase.get_instance()
        self.db.load_from_files()
        self._temp_files: List[Path] = []

    def tearDown(self) -> None:
        _cleanup(self._temp_files)
        from data.databases.title_db import TitleDatabase
        TitleDatabase.reset()

    def test_sacred_load_populates(self) -> None:
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.titles), 0)

    def test_reload_picks_up_generated_file(self) -> None:
        sentinel_id = "moors_reaver_reload_sentinel_g07a"
        path = _write_generated(
            "progression/titles-generated-reload-test.JSON",
            {"titles": [{
                "titleId": sentinel_id,
                "name": "Moors Reaver (Reload Sentinel)",
                "difficultyTier": "apprentice",
                "titleType": "combat",
                "bonuses": {"meleeDamage": 0.10},
                "prerequisites": {"activities": {"enemiesDefeated": 50}},
                "isHidden": False,
            }]},
        )
        self._temp_files.append(path)

        self.assertNotIn(sentinel_id, self.db.titles)
        self.db.reload()
        self.assertIn(sentinel_id, self.db.titles)


# ── EVT_DATABASE_RELOADED publish ──────────────────────────────────────


class ReloadEventPublishTests(unittest.TestCase):
    """Consolidation §6 Phase 0 ship criterion: on successful reload the
    dispatcher publishes ``EVT_DATABASE_RELOADED(tool_name)`` to the
    :class:`GameEventBus`."""

    def setUp(self) -> None:
        from events.event_bus import get_event_bus
        from data.databases.title_db import TitleDatabase
        TitleDatabase.reset()
        TitleDatabase.get_instance().load_from_files()

        self._bus = get_event_bus()
        self._received: list[dict] = []

        def _handler(event) -> None:
            # event is a GameEvent dataclass — pull the data dict
            self._received.append(getattr(event, "data", {}))

        self._handler = _handler
        self._bus.subscribe("EVT_DATABASE_RELOADED", self._handler)

    def tearDown(self) -> None:
        self._bus.unsubscribe("EVT_DATABASE_RELOADED", self._handler)
        from data.databases.title_db import TitleDatabase
        TitleDatabase.reset()

    def test_reload_publishes_event_per_tool(self) -> None:
        from world_system.content_registry.database_reloader import (
            reload_for_tools,
        )
        results = reload_for_tools(["titles"])
        # Reload should have run on TitleDatabase
        self.assertIn("TitleDatabase", results)
        # Bus subscriber should have received an event tagged "titles"
        matching = [
            evt for evt in self._received
            if evt.get("tool_name") == "titles"
        ]
        self.assertGreater(len(matching), 0,
                           "expected EVT_DATABASE_RELOADED for 'titles'")

    def test_unknown_tool_does_not_publish(self) -> None:
        from world_system.content_registry.database_reloader import (
            reload_for_tools,
        )
        self._received.clear()
        reload_for_tools(["nonexistent_tool_xyz"])
        self.assertEqual(self._received, [],
                         "unknown tool should not publish a reload event")


if __name__ == "__main__":
    unittest.main()
