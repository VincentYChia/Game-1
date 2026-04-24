"""Tests for NL1Ingestor — mention extraction from speech banks."""

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.narrative_store import NarrativeStore  # noqa: E402
from world_system.wns.nl1_ingestor import NL1Ingestor  # noqa: E402


class TestNL1Ingestor(unittest.TestCase):
    def setUp(self):
        self.store = NarrativeStore(db_path=":memory:")
        self.ingestor = NL1Ingestor(store=self.store)

    def tearDown(self):
        self.store.close()

    def test_extracts_multiple_mentions(self):
        """A speech bank mentioning 'bandits' and 'copper' should yield >=2 NL1 rows."""
        speech = {
            "greeting": "Bandits are getting bold, traveler. Copper prices doubled.",
            "closing": "Watch the road.",
        }
        rows = self.ingestor.ingest_speech_bank(
            npc_id="npc_smith_01",
            speech_bank_json=speech,
            address="locality:tarmouth_copperdocks",
            game_time=100.0,
        )
        # We expect at least 2 rows: one each for "bandits", "copper", "road".
        self.assertGreaterEqual(len(rows), 2)
        # All rows tagged with the address.
        for r in rows:
            self.assertEqual(r.layer, 1)
            self.assertEqual(r.address, "locality:tarmouth_copperdocks")
            self.assertIn("locality:tarmouth_copperdocks", r.tags)
        # Persisted.
        stored = self.store.query_by_layer(layer=1, limit=50)
        self.assertEqual(len(stored), len(rows))

    def test_tags_include_witness_and_claim_type(self):
        speech = {"greeting": "I saw the guild burn last night."}
        rows = self.ingestor.ingest_speech_bank(
            npc_id="npc_lookout",
            speech_bank_json=speech,
            address="locality:greyfen",
            game_time=50.0,
        )
        self.assertTrue(rows, "expected at least one mention from 'guild'")
        r = rows[0]
        self.assertIn("witness:npc_lookout", r.tags)
        self.assertTrue(
            any(t.startswith("claim_type:") for t in r.tags),
            f"expected a claim_type tag in {r.tags}",
        )
        self.assertTrue(
            any(t.startswith("significance:") for t in r.tags),
            f"expected a significance tag in {r.tags}",
        )

    def test_empty_speech_bank_yields_no_rows(self):
        rows = self.ingestor.ingest_speech_bank(
            npc_id="npc_mute",
            speech_bank_json={},
            address="locality:somewhere",
        )
        self.assertEqual(rows, [])
        self.assertEqual(self.store.count_by_layer(1), 0)

    def test_non_string_values_are_skipped(self):
        rows = self.ingestor.ingest_speech_bank(
            npc_id="npc_odd",
            speech_bank_json={"bandits_hits": 3, "greeting": "copper for everyone"},
            address="locality:x",
        )
        # Only greeting is a string and mentions 'copper'.
        self.assertTrue(rows)
        self.assertTrue(all(r.payload["speech_bank_key"] == "greeting" for r in rows))

    def test_mention_payload_has_expected_keys(self):
        speech = {"greeting": "The king's market is busy today."}
        rows = self.ingestor.ingest_speech_bank(
            npc_id="n1",
            speech_bank_json=speech,
            address="locality:x",
        )
        self.assertTrue(rows)
        r = rows[0]
        mention = r.payload.get("extracted_mention")
        self.assertIsNotNone(mention)
        self.assertIn("entity", mention)
        self.assertIn("claim_type", mention)
        self.assertIn("significance", mention)


if __name__ == "__main__":
    unittest.main()
