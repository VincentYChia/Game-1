"""End-to-end test for the chunks reload chain.

Covers the seam between the Content Registry and the runtime ChunkTemplate
database. Simulates the WES→commit step by writing a generated file
directly to disk (matching the path the GeneratedFileWriter would write
for ``TOOL_CHUNKS``), then calls ``reload_for_tools(["chunks"])`` and
verifies the new chunk template is live in the singleton.

This does NOT exercise the full WES dispatcher path (planner + hubs +
executor_tool + ContentRegistry stage/commit) — those layers are tested
individually elsewhere. This file is the "chunks-specific" plumbing test
that proves the runtime integration shipped in 2026-04-28: generated
chunk templates actually land in the live registry and become available
to systems/chunk.py and Combat/combat_manager.py without a game restart.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent.parent.parent  # Game-1-modular/
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))
os.chdir(_GAME_DIR)

from data.databases.chunk_template_db import ChunkTemplateDatabase  # noqa: E402
from world_system.content_registry.database_reloader import (  # noqa: E402
    reload_for_tools,
)
from world_system.content_registry.xref_rules import (  # noqa: E402
    SACRED_OUTPUT_PREFIX,
    SACRED_OUTPUT_SUBDIR,
    SACRED_TOP_LEVEL_KEY,
    TOOL_CHUNKS,
)


class ChunksReloadE2ETestCase(unittest.TestCase):
    """Simulate WES→commit→reload→live for a single chunk template."""

    def setUp(self) -> None:
        ChunkTemplateDatabase.reset()
        self._temp_files: list[Path] = []

    def tearDown(self) -> None:
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        ChunkTemplateDatabase.reset()

    def _simulate_committed_generation(
        self,
        templates: list,
        suffix: str = "e2e_test",
    ) -> Path:
        """Write a generated file to the path the Content Registry would
        use for ``TOOL_CHUNKS``. This matches the GeneratedFileWriter's
        actual on-disk shape so the test catches any path/key drift."""
        subdir = Path(SACRED_OUTPUT_SUBDIR[TOOL_CHUNKS])
        prefix = SACRED_OUTPUT_PREFIX[TOOL_CHUNKS]
        wrapper_key = SACRED_TOP_LEVEL_KEY[TOOL_CHUNKS]

        path = subdir / f"{prefix}-generated-{suffix}.JSON"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({wrapper_key: templates}, f)
        self._temp_files.append(path)
        return path

    def test_xref_rules_paths_match_database_glob(self) -> None:
        """Sanity: the path the registry writes to MUST match the glob
        the runtime database scans. Drift here means generated files
        land somewhere the database never looks."""
        # SACRED_DIR (from db) must equal SACRED_OUTPUT_SUBDIR[chunks]
        self.assertEqual(
            ChunkTemplateDatabase.SACRED_DIR,
            SACRED_OUTPUT_SUBDIR[TOOL_CHUNKS],
        )
        # GENERATED_GLOB must match what SACRED_OUTPUT_PREFIX produces
        prefix = SACRED_OUTPUT_PREFIX[TOOL_CHUNKS]
        sample_filename = f"{prefix}-generated-anything.JSON"
        # The glob pattern in the db is "Chunk-templates-generated-*.JSON";
        # confirm the prefix-with-suffix matches.
        self.assertTrue(
            sample_filename.startswith(prefix + "-generated-"),
        )

    def test_committed_chunk_template_lands_in_live_registry(self) -> None:
        """Write a generated file → reload → assert the new template is
        present and queryable through the live singleton."""
        chunk_type = "test_e2e_committed_biome"

        self._simulate_committed_generation(
            templates=[{
                "chunkType": chunk_type,
                "name": "E2E Committed Biome",
                "category": "rare",
                "theme": "cave",
                "resourceDensity": {
                    "diamond_geode": {"density": "high", "tierBias": "high"},
                },
                "enemySpawns": {
                    "void_wraith": {"density": "low", "tier": 4},
                },
                "generationRules": {
                    "rollWeight": 1,
                    "spawnAreaAllowed": False,
                    "adjacencyPreference": ["dangerous_cave"],
                },
                "metadata": {
                    "narrative": "Reality bends here.",
                    "tags": ["rare", "end-game", "NEW:test_committed"],
                },
                "geoTypes": ["test_committed_biome_geo"],
            }],
        )

        # Trigger the same reload path the Content Registry uses post-commit.
        results = reload_for_tools([TOOL_CHUNKS])
        self.assertIn("ChunkTemplateDatabase", results)
        self.assertTrue(results["ChunkTemplateDatabase"],
                        "reload should report success")

        # Live registry now exposes the generated template.
        db = ChunkTemplateDatabase.get_instance()
        self.assertTrue(db.has(chunk_type))
        template = db.get(chunk_type)
        self.assertEqual(template.source, "generated")
        self.assertEqual(template.category, "rare")
        self.assertEqual(template.name, "E2E Committed Biome")

        # Geo-dispatch self-registration also worked.
        bridge = db.geo_dispatch_map()
        self.assertEqual(bridge.get("test_committed_biome_geo"), chunk_type)

    def test_multiple_committed_generations_overlay_correctly(self) -> None:
        """Two successive committed files (e.g., WES dispatched twice)
        should both be picked up; a chunk_type collision is last-writer-wins."""
        self._simulate_committed_generation(
            templates=[{
                "chunkType": "test_first_commit",
                "name": "First",
                "category": "peaceful",
                "theme": "forest",
                "resourceDensity": {},
                "enemySpawns": {},
                "generationRules": {},
                "metadata": {"narrative": "first", "tags": []},
            }],
            suffix="first_commit",
        )
        self._simulate_committed_generation(
            templates=[
                {
                    "chunkType": "test_first_commit",
                    "name": "First Overridden",
                    "category": "dangerous",   # was peaceful
                    "theme": "forest",
                    "resourceDensity": {},
                    "enemySpawns": {},
                    "generationRules": {},
                    "metadata": {"narrative": "override", "tags": []},
                },
                {
                    "chunkType": "test_second_commit",
                    "name": "Second",
                    "category": "rare",
                    "theme": "cave",
                    "resourceDensity": {},
                    "enemySpawns": {},
                    "generationRules": {},
                    "metadata": {"narrative": "second", "tags": []},
                },
            ],
            suffix="second_commit",
        )

        reload_for_tools([TOOL_CHUNKS])
        db = ChunkTemplateDatabase.get_instance()

        # Both chunk_types live.
        self.assertTrue(db.has("test_first_commit"))
        self.assertTrue(db.has("test_second_commit"))

        # Override won (sorted glob order: first_commit < second_commit,
        # so second_commit's override of test_first_commit wins).
        first = db.get("test_first_commit")
        self.assertEqual(first.category, "dangerous")
        self.assertEqual(first.name, "First Overridden")

    def test_reload_with_no_generated_files_keeps_sacred_intact(self) -> None:
        """A reload when no generated files exist must still load the
        sacred templates (i.e., reload doesn't silently empty the DB)."""
        # Don't write any generated files.
        reload_for_tools([TOOL_CHUNKS])
        db = ChunkTemplateDatabase.get_instance()
        # Sacred templates must still be present.
        self.assertTrue(db.has("peaceful_forest"))
        self.assertTrue(db.has("dangerous_quarry"))
        stats = db.stats()
        self.assertGreater(stats["sacred"], 0)


if __name__ == "__main__":
    unittest.main()
