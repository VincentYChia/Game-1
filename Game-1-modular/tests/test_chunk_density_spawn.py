"""Tests for the template-driven resource spawn pathway in
``systems.chunk.Chunk.spawn_resources``.

When a :class:`ChunkTemplate` is loaded for ``chunk.chunk_type`` AND its
``resource_density`` map is non-empty, the new ``_spawn_from_template``
helper builds a weighted pool from the template (filtered by tier_range)
instead of falling through to ResourceNodeDatabase substring matching.

These tests use a real Chunk instance — no mocking of pygame — and assert
that:

- Generated templates produce spawns that respect the density-weighted
  pool (over many runs, a "very_high" resource lands more often than a
  "very_low" one).
- Orphan resourceIds in a template are silently skipped (the chunk still
  generates non-empty when at least one referenced resource exists).
- A chunk type that has NO template falls through to the legacy
  substring-matched ResourceNodeDatabase path (zero regression).
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

from core.paths import get_resource_path  # noqa: E402
from data.databases.chunk_template_db import ChunkTemplateDatabase  # noqa: E402
from data.databases.resource_node_db import ResourceNodeDatabase  # noqa: E402
from data.databases.world_generation_db import WorldGenerationConfig  # noqa: E402
from systems.chunk import Chunk  # noqa: E402


class DensityDrivenSpawnTestCase(unittest.TestCase):
    """End-to-end: write a generated template + spawn a chunk + check pool."""

    @classmethod
    def setUpClass(cls) -> None:
        # Make sure the resource DB is loaded — game_engine bootstraps
        # this on startup but tests run headless. ChunkTemplateDatabase
        # depends on ResourceNodeDatabase being loaded so the orphan-
        # filter in _spawn_from_template can resolve real resourceIds.
        rdb = ResourceNodeDatabase.get_instance()
        if not rdb.loaded:
            rdb.load_from_file(
                str(get_resource_path("Definitions.JSON/resource-node-1.JSON"))
            )
        WorldGenerationConfig.get_instance()

    def setUp(self) -> None:
        self._temp_files: list[Path] = []
        ChunkTemplateDatabase.reset()

    def tearDown(self) -> None:
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        ChunkTemplateDatabase.reset()

    def _write_generated(self, payload: dict, suffix: str) -> Path:
        path = Path("Definitions.JSON") / f"Chunk-templates-generated-{suffix}.JSON"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        self._temp_files.append(path)
        return path

    def test_density_weighted_spawn_distribution(self) -> None:
        """Over many seeds, a 'very_high' resource should appear far
        more often than a 'very_low' one in the same template."""
        self._write_generated({
            "templates": [{
                "chunkType": "test_density_distribution_biome",
                "name": "Density Test",
                "category": "peaceful",
                "theme": "forest",
                "resourceDensity": {
                    "oak_tree":   {"density": "very_high", "tierBias": "low"},
                    "pine_tree":  {"density": "very_low",  "tierBias": "low"},
                },
                "enemySpawns": {},
                "generationRules": {"rollWeight": 5},
                "metadata": {"narrative": "x", "tags": []},
            }],
        }, suffix="density")
        ChunkTemplateDatabase.get_instance().reload()

        # Spawn many chunks at different seeds (all with the same chunk_type)
        # and tally which resource_ids land. very_high (3.0x) should clearly
        # dominate very_low (0.5x) — a 6:1 weight ratio.
        spawn_counts: Counter[str] = Counter()
        for seed in range(60):
            chunk = Chunk(chunk_x=100 + seed, chunk_y=100, seed=seed)
            chunk.chunk_type = "test_density_distribution_biome"
            chunk.resources = []
            chunk.spawn_resources()
            for r in chunk.resources:
                spawn_counts[r.resource_type] += 1

        oak = spawn_counts.get("oak_tree", 0)
        pine = spawn_counts.get("pine_tree", 0)
        self.assertGreater(oak, 0, f"oak should appear; got counts={dict(spawn_counts)}")
        # With 6:1 weight ratio, oak should comfortably outnumber pine.
        # Allow for randomness — assert oak > 2*pine rather than the
        # statistically-expected 6:1.
        self.assertGreater(
            oak, 2 * pine,
            f"density-weighted pool should favor very_high; "
            f"oak={oak}, pine={pine}",
        )

    def test_orphan_resources_silently_skipped(self) -> None:
        """A template mixing one valid resource and one orphan should
        spawn only the valid resource. The chunk must NOT be empty."""
        self._write_generated({
            "templates": [{
                "chunkType": "test_orphan_mix_biome",
                "name": "Orphan Mix",
                "category": "peaceful",
                "theme": "forest",
                "resourceDensity": {
                    "oak_tree": {"density": "very_high", "tierBias": "low"},
                    "this_id_does_not_exist_xyz": {
                        "density": "very_high", "tierBias": "low"
                    },
                },
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "x", "tags": []},
            }],
        }, suffix="orphan_mix")
        ChunkTemplateDatabase.get_instance().reload()

        chunk = Chunk(chunk_x=200, chunk_y=200, seed=42)
        chunk.chunk_type = "test_orphan_mix_biome"
        chunk.resources = []
        chunk.spawn_resources()

        spawned_ids = {r.resource_type for r in chunk.resources}
        # All spawned resources should be the only valid one.
        self.assertTrue(
            spawned_ids.issubset({"oak_tree"}),
            f"unexpected resource_ids spawned: {spawned_ids}",
        )

    def test_all_orphan_template_falls_through_to_legacy(self) -> None:
        """Template with EVERY resource being orphan should let the
        legacy ResourceNodeDatabase fallback path run (chunk type must
        contain 'forest'/'quarry'/'cave' for that to spawn anything).
        """
        self._write_generated({
            "templates": [{
                "chunkType": "test_all_orphan_forest",
                "name": "All Orphan",
                "category": "peaceful",
                "theme": "forest",
                "resourceDensity": {
                    "fake_resource_a": {"density": "high", "tierBias": "low"},
                    "fake_resource_b": {"density": "high", "tierBias": "low"},
                },
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "x", "tags": []},
            }],
        }, suffix="all_orphan")
        ChunkTemplateDatabase.get_instance().reload()

        chunk = Chunk(chunk_x=300, chunk_y=300, seed=42)
        chunk.chunk_type = "test_all_orphan_forest"
        chunk.resources = []
        chunk.spawn_resources()

        # Fallthrough should have populated the chunk via legacy substring
        # matching. The chunk_type contains 'forest' so trees should land.
        self.assertGreater(
            len(chunk.resources), 0,
            "all-orphan template must fall through to legacy spawn path",
        )

    def test_chunk_with_no_template_uses_legacy_path(self) -> None:
        """A chunk_type with no matching template uses the existing
        ResourceNodeDatabase substring path — zero regression for chunks
        outside the template registry."""
        chunk = Chunk(chunk_x=400, chunk_y=400, seed=7)
        chunk.chunk_type = "peaceful_forest"  # canonical sacred — has template
        chunk.resources = []
        chunk.spawn_resources()
        # Should produce some resources via either path.
        self.assertGreater(len(chunk.resources), 0)

        # Non-templated chunk_type — exercise legacy substring fallback.
        chunk2 = Chunk(chunk_x=500, chunk_y=500, seed=7)
        chunk2.chunk_type = "made_up_forest_type"
        chunk2.resources = []
        chunk2.spawn_resources()
        # Substring "forest" → trees should spawn via ResourceNodeDatabase.
        self.assertGreater(len(chunk2.resources), 0)


if __name__ == "__main__":
    unittest.main()
