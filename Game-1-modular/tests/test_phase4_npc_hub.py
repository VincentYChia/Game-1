"""Phase 4 NPC hub + reverse cross-ref tests (2026-06-03).

Per consolidation §2.5 (corrected): NPCs are the largest narrative-
injection surface, not "the hub feature". Six other content tools
need NPC voice when authoring cross-referenced content. The
``get_voice_excerpt`` API is the canonical single source.

Reverse cross-ref schema additions let generated content reference
the content that birthed it:
    Title.granted_by_quest_id / .granted_by_npc_id
    Skill.taught_by_npc_id / .rewarded_by_quest_id
    Hostile.hunted_by_quest_id
    Material.gather_quest_id / .inherited_from_chunk_id
    Node.inherited_from_chunk_id

These are all Optional fields with None defaults — additive schema
migration, non-breaking for existing sacred JSON.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)


# ── NPCDatabase.get_voice_excerpt ────────────────────────────────────


class GetVoiceExcerptTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.npc_db import NPCDatabase
        from data.models.npcs import NPCDefinition
        # Reset and inject a probe NPC directly to avoid disk I/O.
        NPCDatabase._instance = None
        db = NPCDatabase.get_instance()
        db.npcs["captain_vell"] = NPCDefinition(
            npc_id="captain_vell",
            name="Captain Vell",
            title="Copperlash Vendetta",
            narrative="buried his brother on the moors-stone",
            personality={
                "voice": "salt-dry, terse",
                "alignment": "vengeful",
            },
            locality={"home_chunk": "dangerous_copper_moors"},
            faction={"tag": "guild:moors_raiders"},
            tags=["captain", "moors", "vendetta"],
        )
        self.db = db

    def tearDown(self) -> None:
        from data.databases.npc_db import NPCDatabase
        NPCDatabase._instance = None

    def test_unknown_id_returns_none(self) -> None:
        self.assertIsNone(self.db.get_voice_excerpt("does_not_exist"))

    def test_returns_canonical_shape(self) -> None:
        excerpt = self.db.get_voice_excerpt("captain_vell")
        self.assertIsNotNone(excerpt)
        for key in (
            "npc_id", "name", "title", "narrative",
            "voice_anchor", "personality_summary",
            "primary_faction", "home_chunk",
            "locality_summary", "tags",
        ):
            self.assertIn(key, excerpt, f"missing key '{key}'")

    def test_voice_anchor_from_personality(self) -> None:
        excerpt = self.db.get_voice_excerpt("captain_vell")
        self.assertEqual(excerpt["voice_anchor"], "salt-dry, terse")

    def test_home_chunk_extracted(self) -> None:
        excerpt = self.db.get_voice_excerpt("captain_vell")
        self.assertEqual(excerpt["home_chunk"], "dangerous_copper_moors")

    def test_primary_faction_extracted(self) -> None:
        excerpt = self.db.get_voice_excerpt("captain_vell")
        self.assertEqual(
            excerpt["primary_faction"], "guild:moors_raiders",
        )

    def test_narrative_preserved(self) -> None:
        excerpt = self.db.get_voice_excerpt("captain_vell")
        self.assertIn("moors-stone", excerpt["narrative"])


# ── Reverse cross-ref schema additions ──────────────────────────────


class ReverseXrefSchemaTests(unittest.TestCase):
    """Verify each affected dataclass accepts the new optional fields
    without breaking existing construction."""

    def test_title_supports_granted_by_quest_id(self) -> None:
        from data.models.titles import TitleDefinition
        from data.models.unlock_conditions import UnlockRequirements
        t = TitleDefinition(
            title_id="probe", name="Probe", tier="apprentice",
            category="combat", bonus_description="test",
            bonuses={}, requirements=UnlockRequirements([]),
            granted_by_quest_id="probe_quest_001",
            granted_by_npc_id="captain_vell",
        )
        self.assertEqual(t.granted_by_quest_id, "probe_quest_001")
        self.assertEqual(t.granted_by_npc_id, "captain_vell")

    def test_title_default_xref_fields_none(self) -> None:
        from data.models.titles import TitleDefinition
        from data.models.unlock_conditions import UnlockRequirements
        t = TitleDefinition(
            title_id="probe", name="Probe", tier="apprentice",
            category="combat", bonus_description="test",
            bonuses={}, requirements=UnlockRequirements([]),
        )
        self.assertIsNone(t.granted_by_quest_id)
        self.assertIsNone(t.granted_by_npc_id)

    def test_skill_supports_taught_by_npc_id(self) -> None:
        from data.models.skills import (
            SkillCost, SkillDefinition, SkillEffect,
            SkillEvolution, SkillRequirements,
        )
        s = SkillDefinition(
            skill_id="probe", name="Probe", tier=2,
            rarity="uncommon", categories=["melee"],
            description="probe", narrative="probe",
            tags=[],
            effect=SkillEffect(
                effect_type="damage", category="melee",
                magnitude="moderate", target="enemy",
                duration="instant", additional_effects=[],
            ),
            cost=SkillCost(mana="moderate", cooldown="moderate"),
            evolution=SkillEvolution(
                can_evolve=False, next_skill_id=None, requirement="",
            ),
            requirements=SkillRequirements(
                character_level=1, stats={}, titles=[],
            ),
            taught_by_npc_id="captain_vell",
            rewarded_by_quest_id="probe_quest_001",
        )
        self.assertEqual(s.taught_by_npc_id, "captain_vell")
        self.assertEqual(s.rewarded_by_quest_id, "probe_quest_001")

    def test_material_supports_inherited_from_chunk_id(self) -> None:
        from data.models.materials import MaterialDefinition
        m = MaterialDefinition(
            material_id="probe", name="Probe", tier=2,
            category="metal", rarity="uncommon",
            inherited_from_chunk_id="dangerous_copper_moors",
            gather_quest_id="probe_quest_001",
        )
        self.assertEqual(
            m.inherited_from_chunk_id, "dangerous_copper_moors",
        )
        self.assertEqual(m.gather_quest_id, "probe_quest_001")

    def test_resource_node_supports_inherited_from_chunk_id(self) -> None:
        from data.models.resources import ResourceNodeDefinition
        n = ResourceNodeDefinition(
            resource_id="probe", name="Probe", category="ore",
            tier=2, required_tool="pickaxe", base_health=200,
            drops=[],
            inherited_from_chunk_id="dangerous_copper_moors",
        )
        self.assertEqual(
            n.inherited_from_chunk_id, "dangerous_copper_moors",
        )

    def test_hostile_supports_hunted_by_quest_id(self) -> None:
        from Combat.enemy import EnemyDefinition, AIPattern
        e = EnemyDefinition(
            enemy_id="probe", name="Probe", tier=2,
            category="humanoid", behavior="aggressive",
            max_health=200.0, damage_min=5.0, damage_max=10.0,
            defense=2.0, speed=2.0,
            aggro_range=8.0, attack_speed=1.0,
            drops=[],
            ai_pattern=AIPattern(
                default_state="patrol",
                aggro_on_damage=True,
                aggro_on_proximity=True,
                flee_at_health=0.0,
                call_for_help_radius=0.0,
            ),
            hunted_by_quest_id="probe_quest_001",
        )
        self.assertEqual(e.hunted_by_quest_id, "probe_quest_001")


if __name__ == "__main__":
    unittest.main()
