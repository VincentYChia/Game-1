"""Tests for NarrativeStore — schema, insert, query-by-address/layer."""

import os
import sys
import unittest
import uuid

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.narrative_store import (  # noqa: E402
    ALL_LAYERS,
    NarrativeRow,
    NarrativeStore,
)


class TestNarrativeStoreSchema(unittest.TestCase):
    def setUp(self):
        self.store = NarrativeStore(db_path=":memory:")

    def tearDown(self):
        self.store.close()

    def test_schema_creates_every_layer_table(self):
        """Every NL layer (1..7) has both event and tag tables with address indexes."""
        cur = self.store._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row["name"] for row in cur.fetchall()}
        for n in ALL_LAYERS:
            self.assertIn(f"nl{n}_events", names, f"missing nl{n}_events table")
            self.assertIn(f"nl{n}_tags", names, f"missing nl{n}_tags table")
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        idx_names = {row["name"] for row in cur.fetchall()}
        for n in ALL_LAYERS:
            self.assertIn(
                f"idx_nl{n}_address", idx_names,
                f"missing address index for layer {n}",
            )

    def test_schema_version_recorded(self):
        cur = self.store._conn.cursor()
        cur.execute("SELECT value FROM wns_meta WHERE key = 'schema_version'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["value"], "1")


class TestNarrativeStoreInsertQuery(unittest.TestCase):
    def setUp(self):
        self.store = NarrativeStore(db_path=":memory:")

    def tearDown(self):
        self.store.close()

    def _row(
        self, layer=2, address="locality:tarmouth_copperdocks",
        narrative="bandits rising", tags=None, payload=None, ts=100.0,
    ):
        return NarrativeRow(
            id=str(uuid.uuid4()),
            created_at=ts,
            layer=layer,
            address=address,
            narrative=narrative,
            tags=list(tags or [address, "tone:ominous"]),
            payload=dict(payload or {"task": f"wns_layer{layer}"}),
        )

    def test_insert_and_get_round_trips(self):
        row = self._row()
        self.store.insert_row(row)
        got = self.store.get(layer=2, event_id=row.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.narrative, row.narrative)
        self.assertEqual(got.address, row.address)
        self.assertEqual(set(got.tags), set(row.tags))
        self.assertEqual(got.payload, row.payload)

    def test_query_by_address_filters_correctly(self):
        a = self._row(address="locality:a")
        b = self._row(address="locality:a")
        c = self._row(address="locality:b")
        self.store.insert_row(a)
        self.store.insert_row(b)
        self.store.insert_row(c)
        got_a = self.store.query_by_address(layer=2, address="locality:a")
        got_b = self.store.query_by_address(layer=2, address="locality:b")
        self.assertEqual(len(got_a), 2)
        self.assertEqual(len(got_b), 1)
        self.assertEqual(got_b[0].id, c.id)

    def test_query_by_layer_counts_match(self):
        self.store.insert_row(self._row(layer=2))
        self.store.insert_row(self._row(layer=3))
        self.store.insert_row(self._row(layer=3))
        self.assertEqual(self.store.count_by_layer(2), 1)
        self.assertEqual(self.store.count_by_layer(3), 2)
        self.assertEqual(len(self.store.query_by_layer(3)), 2)

    def test_insert_invalid_layer_raises(self):
        row = NarrativeRow(
            id="x", created_at=0.0, layer=99, address="locality:a",
            narrative="oops",
        )
        with self.assertRaises(ValueError):
            self.store.insert_row(row)

    def test_tags_junction_populated(self):
        row = self._row(tags=["locality:a", "tone:ominous", "relationship:rivalry"])
        self.store.insert_row(row)
        cur = self.store._conn.cursor()
        cur.execute("SELECT tag FROM nl2_tags WHERE event_id = ?", (row.id,))
        got_tags = {r["tag"] for r in cur.fetchall()}
        self.assertEqual(
            got_tags,
            {"locality:a", "tone:ominous", "relationship:rivalry"},
        )

    def test_stats_reports_counts(self):
        self.store.insert_row(self._row(layer=1))
        self.store.insert_row(self._row(layer=2))
        self.store.insert_row(self._row(layer=7))
        stats = self.store.stats
        self.assertEqual(stats["counts"]["nl1"], 1)
        self.assertEqual(stats["counts"]["nl2"], 1)
        self.assertEqual(stats["counts"]["nl7"], 1)
        self.assertEqual(stats["total_rows"], 3)


if __name__ == "__main__":
    unittest.main()
