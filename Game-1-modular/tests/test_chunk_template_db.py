"""Tests for :class:`data.databases.chunk_template_db.ChunkTemplateDatabase`.

Covers:
- Sacred template load from the on-disk ``Definitions.JSON/Chunk-templates-2.JSON``
- Geo dispatch JSON load
- Querying by chunk_type / category / theme / geo_type
- Generated file overlay (write a temp generated file, reload, assert)
- ``geoTypes`` auto-registration WITHOUT overriding sacred dispatch
- Reload preserves previous state when the new load fails
- Density / tier_bias allow-list lookups (ChunkTemplate dataclass helpers)
- Orphan / malformed JSON entries don't crash the loader
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

from data.databases.chunk_template_db import (  # noqa: E402
    ChunkTemplate,
    ChunkTemplateDatabase,
    DENSITY_WEIGHTS,
    EnemySpawnSpec,
    GenerationRules,
    ResourceDensitySpec,
    TIER_BIAS_ORDER,
    _build_template,
)


# ── Sacred-state tests (read-only, no temp files) ────────────────────────


class SacredLoadTestCase(unittest.TestCase):
    """Read the on-disk sacred templates and assert structural invariants."""

    @classmethod
    def setUpClass(cls) -> None:
        ChunkTemplateDatabase.reset()
        cls.db = ChunkTemplateDatabase.get_instance()

    def test_loaded_flag(self) -> None:
        self.assertTrue(self.db.loaded, "DB should report loaded after first access")

    def test_minimum_template_count(self) -> None:
        # Chunk-templates-2.JSON ships with 21 templates (12 legacy + 9 geographic).
        self.assertGreaterEqual(len(self.db.templates), 12,
                                "expected at least the 12 legacy templates")

    def test_legacy_chunk_types_present(self) -> None:
        for chunk_type in (
            "peaceful_forest", "peaceful_quarry", "peaceful_cave",
            "dangerous_forest", "dangerous_quarry", "dangerous_cave",
            "water_lake", "water_river", "water_cursed_swamp",
        ):
            self.assertTrue(self.db.has(chunk_type),
                            f"sacred template missing: {chunk_type}")

    def test_template_typed_dataclass(self) -> None:
        peaceful = self.db.get("peaceful_forest")
        self.assertIsInstance(peaceful, ChunkTemplate)
        self.assertEqual(peaceful.category, "peaceful")
        self.assertEqual(peaceful.theme, "forest")
        self.assertEqual(peaceful.source, "sacred")
        self.assertGreater(len(peaceful.resource_density), 0)
        for spec in peaceful.resource_density.values():
            self.assertIsInstance(spec, ResourceDensitySpec)
            self.assertIn(spec.density, DENSITY_WEIGHTS)

    def test_get_by_category_and_theme(self) -> None:
        peaceful = self.db.get_by_category("peaceful")
        self.assertGreater(len(peaceful), 0)
        self.assertTrue(all(t.category == "peaceful" for t in peaceful))

        forests = self.db.get_by_theme("forest")
        self.assertGreater(len(forests), 0)
        self.assertTrue(all(t.theme == "forest" for t in forests))

    def test_geo_dispatch_loads_sacred_entries(self) -> None:
        """The 15 geo entries in geo_chunk_dispatch.json should all
        resolve to loaded templates."""
        bridge = self.db.geo_dispatch_map()
        self.assertGreaterEqual(len(bridge), 15)
        for geo_type, chunk_type in bridge.items():
            self.assertTrue(self.db.has(chunk_type),
                            f"geo dispatch '{geo_type}' → '{chunk_type}' "
                            f"but template doesn't exist")

    def test_get_for_geo_type(self) -> None:
        forest = self.db.get_for_geo_type("forest")
        self.assertIsNotNone(forest)
        self.assertEqual(forest.chunk_type, "peaceful_forest")

        unknown = self.db.get_for_geo_type("nonexistent_biome_xyz")
        self.assertIsNone(unknown)

    def test_stats_dict_shape(self) -> None:
        stats = self.db.stats()
        self.assertIn("total", stats)
        self.assertIn("sacred", stats)
        self.assertIn("generated", stats)
        self.assertIn("geo_dispatch_entries", stats)
        self.assertEqual(stats["sacred"] + stats["generated"], stats["total"])


# ── Generated-overlay tests (write temp files into Definitions.JSON) ─────


class GeneratedOverlayTestCase(unittest.TestCase):
    """Write a temp ``Chunk-templates-generated-*.JSON`` and reload."""

    def setUp(self) -> None:
        ChunkTemplateDatabase.reset()
        self.db = ChunkTemplateDatabase.get_instance()
        self._temp_files: list[Path] = []

    def tearDown(self) -> None:
        # Always clean up — even if the test failed.
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        ChunkTemplateDatabase.reset()

    def _write_generated(self, payload: dict, suffix: str = "test") -> Path:
        path = Path("Definitions.JSON") / f"Chunk-templates-generated-{suffix}.JSON"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        self._temp_files.append(path)
        return path

    def test_generated_file_adds_new_template(self) -> None:
        baseline_total = len(self.db.templates)

        self._write_generated({
            "metadata": {"source": "test", "version": "1"},
            "templates": [{
                "chunkType": "test_generated_biome_001",
                "name": "Test Generated Biome",
                "category": "rare",
                "theme": "cave",
                "resourceDensity": {
                    "diamond_geode": {"density": "moderate", "tierBias": "high"},
                },
                "enemySpawns": {
                    "void_wraith": {"density": "low", "tier": 4},
                },
                "generationRules": {
                    "rollWeight": 1, "spawnAreaAllowed": False,
                    "adjacencyPreference": ["dangerous_cave"],
                },
                "metadata": {
                    "narrative": "Generated test biome.",
                    "tags": ["rare", "end-game", "NEW:test_generated"],
                },
            }],
        })

        self.db.reload()
        self.assertEqual(len(self.db.templates), baseline_total + 1)
        self.assertTrue(self.db.has("test_generated_biome_001"))
        new_template = self.db.get("test_generated_biome_001")
        self.assertEqual(new_template.source, "generated")
        self.assertEqual(new_template.category, "rare")
        self.assertIn("diamond_geode", new_template.resource_density)

    def test_generated_overrides_sacred_on_collision(self) -> None:
        """If a generated file ships a chunkType that already exists in
        sacred, generated wins (last-writer-wins). This lets designers
        hot-tune via WES output without editing sacred files."""
        sacred_peaceful = self.db.get("peaceful_forest")
        self.assertIsNotNone(sacred_peaceful)

        self._write_generated({
            "templates": [{
                "chunkType": "peaceful_forest",
                "name": "Overridden Forest",
                "category": "peaceful",
                "theme": "forest",
                "resourceDensity": {},
                "enemySpawns": {},
                "generationRules": {"rollWeight": 99},
                "metadata": {"narrative": "OVERRIDE", "tags": ["test"]},
            }],
        }, suffix="override")

        self.db.reload()
        overridden = self.db.get("peaceful_forest")
        self.assertEqual(overridden.name, "Overridden Forest")
        self.assertEqual(overridden.source, "generated")
        self.assertEqual(overridden.generation_rules.roll_weight, 99)

    def test_geo_types_array_self_registers_dispatch(self) -> None:
        """Generated templates with a ``geoTypes`` array should register
        new dispatch entries for biome types not yet in the bridge JSON."""
        self._write_generated({
            "templates": [{
                "chunkType": "test_self_register_biome",
                "name": "Self Register Biome",
                "category": "dangerous",
                "theme": "quarry",
                "resourceDensity": {},
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "x", "tags": []},
                "geoTypes": ["new_geo_biome_xyz"],
            }],
        }, suffix="georegister")

        self.db.reload()
        bridge = self.db.geo_dispatch_map()
        self.assertEqual(bridge.get("new_geo_biome_xyz"), "test_self_register_biome")

    def test_sacred_dispatch_wins_over_generated_geo_types(self) -> None:
        """Generated templates may NOT override sacred dispatch entries —
        designer keeps full control of canonical biome routing."""
        # 'forest' is already mapped to 'peaceful_forest' in sacred
        # geo_chunk_dispatch.json. A generated template trying to
        # claim 'forest' must NOT win.
        self._write_generated({
            "templates": [{
                "chunkType": "test_invader_biome",
                "name": "Invader",
                "category": "dangerous",
                "theme": "forest",
                "resourceDensity": {},
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "x", "tags": []},
                "geoTypes": ["forest"],   # try to hijack sacred mapping
            }],
        }, suffix="invader")

        self.db.reload()
        forest_template = self.db.get_for_geo_type("forest")
        self.assertEqual(forest_template.chunk_type, "peaceful_forest",
                         "sacred dispatch must win over generated geoTypes")

    def test_reload_preserves_state_on_malformed_payload(self) -> None:
        """A malformed generated file must not corrupt the in-memory
        registry — the reload should keep the prior state."""
        baseline_count = len(self.db.templates)

        # Write a malformed JSON file (invalid syntax)
        path = Path("Definitions.JSON") / "Chunk-templates-generated-broken.JSON"
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json")
        self._temp_files.append(path)

        self.db.reload()
        # Should still have at least baseline (broken file just skipped).
        self.assertGreaterEqual(len(self.db.templates), baseline_count)

    def test_orphan_resource_id_in_template_is_silent(self) -> None:
        """A template referencing an unknown resourceId loads cleanly —
        chunk.py's _spawn_from_template handles the orphan at spawn time."""
        self._write_generated({
            "templates": [{
                "chunkType": "test_orphan_resource_biome",
                "name": "Orphan Test",
                "category": "rare",
                "theme": "cave",
                "resourceDensity": {
                    "this_resource_does_not_exist_xyz": {
                        "density": "high", "tierBias": "high",
                    },
                },
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "x", "tags": []},
            }],
        }, suffix="orphan")

        self.db.reload()
        # Template loads fine — orphan handling is at spawn time.
        self.assertTrue(self.db.has("test_orphan_resource_biome"))
        tmpl = self.db.get("test_orphan_resource_biome")
        self.assertIn("this_resource_does_not_exist_xyz", tmpl.resource_density)


# ── Builder-helpers / dataclass-internals tests (no I/O) ─────────────────


class TemplateBuilderTestCase(unittest.TestCase):
    """White-box tests for ``_build_template`` — defensive parsing."""

    def test_missing_chunk_type_returns_none(self) -> None:
        self.assertIsNone(_build_template({}, source="sacred"))
        self.assertIsNone(_build_template({"chunkType": ""}, source="sacred"))
        self.assertIsNone(_build_template({"chunkType": None}, source="sacred"))

    def test_non_dict_input_returns_none(self) -> None:
        self.assertIsNone(_build_template("not_a_dict", source="sacred"))
        self.assertIsNone(_build_template(None, source="sacred"))

    def test_minimal_template_uses_defaults(self) -> None:
        tmpl = _build_template({"chunkType": "minimal"}, source="sacred")
        self.assertIsNotNone(tmpl)
        self.assertEqual(tmpl.name, "minimal")  # defaults to chunk_type
        self.assertEqual(tmpl.category, "peaceful")
        self.assertEqual(tmpl.theme, "forest")
        self.assertEqual(len(tmpl.resource_density), 0)
        self.assertEqual(len(tmpl.enemy_spawns), 0)
        self.assertEqual(tmpl.generation_rules.roll_weight, 1)
        self.assertEqual(tmpl.geo_types, [])

    def test_unknown_density_value_falls_back_to_one(self) -> None:
        tmpl = _build_template({
            "chunkType": "weird",
            "resourceDensity": {
                "x": {"density": "completely_invalid", "tierBias": "low"},
            },
        }, source="sacred")
        spec = tmpl.resource_density["x"]
        self.assertEqual(spec.density, "completely_invalid")
        self.assertEqual(spec.spawn_weight, 1.0)  # fallback

    def test_enemy_spawn_clamps_tier_to_1_4(self) -> None:
        tmpl = _build_template({
            "chunkType": "tier_clamp",
            "enemySpawns": {
                "low": {"density": "moderate", "tier": -5},
                "high": {"density": "moderate", "tier": 99},
                "string": {"density": "moderate", "tier": "not_a_number"},
            },
        }, source="sacred")
        self.assertEqual(tmpl.enemy_spawns["low"].tier, 1)
        self.assertEqual(tmpl.enemy_spawns["high"].tier, 4)
        self.assertEqual(tmpl.enemy_spawns["string"].tier, 1)

    def test_density_weight_resolution(self) -> None:
        spec = ResourceDensitySpec("x", "very_high", "high")
        self.assertEqual(spec.spawn_weight, 3.0)
        self.assertEqual(spec.tier_bias_rank, 3)

        spec_low = EnemySpawnSpec("y", "very_low", 1)
        self.assertEqual(spec_low.spawn_weight, 0.5)


# ── Allow-list invariants ────────────────────────────────────────────────


class AllowListInvariantsTestCase(unittest.TestCase):
    """Sanity-check the canonical density / tier_bias allow-lists."""

    def test_density_weights_complete(self) -> None:
        # Match prompt_fragments_tool_chunks.json's allow-list.
        for required in ("very_low", "low", "moderate", "high", "very_high"):
            self.assertIn(required, DENSITY_WEIGHTS)

    def test_tier_bias_complete(self) -> None:
        for required in ("low", "mid", "high", "legendary"):
            self.assertIn(required, TIER_BIAS_ORDER)

    def test_density_weights_monotone(self) -> None:
        order = ["very_low", "low", "moderate", "high", "very_high"]
        weights = [DENSITY_WEIGHTS[k] for k in order]
        self.assertEqual(weights, sorted(weights))


if __name__ == "__main__":
    unittest.main()
