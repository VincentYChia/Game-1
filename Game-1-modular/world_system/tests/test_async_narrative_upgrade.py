"""2026-07 audit Batch 3 — WMS game-loop responsiveness fixes.

1. L2 narrative upgrades no longer run a synchronous LLM call on the
   game loop. The template narrative is recorded immediately; a worker
   thread runs the LLM and the result patches EventStore + LayerStore
   rows on the main thread via drain_narrative_upgrades().
2. Retention Rule 5 uses one batched cause-chain pass instead of a
   per-event unindexed LIKE scan (was N+1, up to 5,000 scans/prune).
"""
import os
import sys
import unittest

_MODULAR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _MODULAR_ROOT not in sys.path:
    sys.path.insert(0, _MODULAR_ROOT)

from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent  # noqa: E402
from world_system.world_memory.event_store import EventStore  # noqa: E402
from world_system.world_memory.layer_store import LayerStore  # noqa: E402
from world_system.world_memory.interpreter import WorldInterpreter  # noqa: E402
from world_system.world_memory.wms_ai import NarrationResult  # noqa: E402


def _interp(interp_id="i1", narrative="template text", severity="minor",
            cause_ids=None, tags=None):
    return InterpretedEvent(
        interpretation_id=interp_id,
        created_at=100.0,
        narrative=narrative,
        category="combat",
        severity=severity,
        trigger_event_id="t1",
        trigger_count=3,
        cause_event_ids=list(cause_ids or []),
        affects_tags=list(tags or ["domain:combat"]),
    )


def _trigger_event():
    return WorldMemoryEvent(
        event_id="t1", event_type="combat", event_subtype="kill",
        actor_id="player", actor_type="player", game_time=100.0,
    )


class FakeWmsAI:
    """Deterministic stand-in: callback fires synchronously in-thread."""

    def __init__(self, result: NarrationResult):
        self.result = result
        self.calls = []

    def generate_narration_async(self, callback=None, **kwargs):
        self.calls.append(kwargs)
        if callback:
            callback(self.result)


class TestBatchedReferenceScan(unittest.TestCase):
    def test_batched_ids_match_per_event_like_scan(self):
        store = EventStore(db_path=":memory:")
        store.record_interpretation(_interp("i1", cause_ids=["e1", "e2"]))
        store.record_interpretation(_interp("i2", cause_ids=["e3"]))

        batched = store.get_all_referenced_event_ids()
        self.assertEqual(batched, {"e1", "e2", "e3"})
        for eid in ("e1", "e2", "e3"):
            self.assertTrue(store.is_referenced_by_interpretation(eid))
        self.assertNotIn("e99", batched)


class TestApplyNarrativeUpgrade(unittest.TestCase):
    def test_patches_narrative_severity_and_tags(self):
        store = EventStore(db_path=":memory:")
        store.record_interpretation(_interp("i1", tags=["domain:combat"]))

        ok = store.apply_narrative_upgrade(
            "i1", "the LLM version", severity="major",
            extra_tags=["tone:grim", "domain:combat"])
        self.assertTrue(ok)

        row = store.connection.execute(
            "SELECT narrative, severity, affects_tags_json FROM "
            "interpretations WHERE interpretation_id = 'i1'").fetchone()
        self.assertEqual(row[0], "the LLM version")
        self.assertEqual(row[1], "major")
        self.assertIn("tone:grim", row[2])
        # No duplicate for the pre-existing tag
        self.assertEqual(row[2].count("domain:combat"), 1)

    def test_missing_row_returns_false(self):
        store = EventStore(db_path=":memory:")
        self.assertFalse(store.apply_narrative_upgrade("nope", "x"))

    def test_none_severity_keeps_existing(self):
        store = EventStore(db_path=":memory:")
        store.record_interpretation(_interp("i1", severity="significant"))
        store.apply_narrative_upgrade("i1", "new text", severity=None)
        row = store.connection.execute(
            "SELECT severity FROM interpretations "
            "WHERE interpretation_id = 'i1'").fetchone()
        self.assertEqual(row[0], "significant")


class TestLayerStoreUpdate(unittest.TestCase):
    def test_update_patches_row_and_junction(self):
        ls = LayerStore(":memory:")
        ls.insert_event(layer=2, narrative="template", game_time=100.0,
                        category="combat", severity="minor",
                        significance="minor", tags=["domain:combat"],
                        event_id="i1")

        ok = ls.update_event_narrative(
            2, "i1", "upgraded", severity="major",
            extra_tags=["tone:grim"])
        self.assertTrue(ok)

        rows = ls.query_by_tags(2, ["tone:grim"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["narrative"], "upgraded")
        self.assertEqual(rows[0]["severity"], "major")

    def test_missing_row_returns_false(self):
        ls = LayerStore(":memory:")
        self.assertFalse(ls.update_event_narrative(2, "nope", "x"))


class TestAsyncUpgradeFlow(unittest.TestCase):
    def _make_interpreter(self, wms_ai):
        interp = WorldInterpreter()
        interp.event_store = EventStore(db_path=":memory:")
        interp.layer_store = LayerStore(":memory:")
        interp.wms_ai = wms_ai
        return interp

    def test_dispatch_then_drain_patches_both_stores(self):
        result = NarrationResult(text="rich narrative", severity="major",
                                 tags=["tone:grim"], success=True)
        fake = FakeWmsAI(result)
        wi = self._make_interpreter(fake)

        interpretation = _interp("i1")
        wi.event_store.record_interpretation(interpretation)
        wi.layer_store.insert_event(
            layer=2, narrative=interpretation.narrative, game_time=100.0,
            category="combat", severity="minor", significance="minor",
            tags=list(interpretation.affects_tags), event_id="i1")

        wi._dispatch_narrative_upgrade(interpretation, _trigger_event())
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["layer"], 2)

        # Template stands until the main-thread drain applies the result.
        row = wi.event_store.connection.execute(
            "SELECT narrative FROM interpretations "
            "WHERE interpretation_id = 'i1'").fetchone()
        self.assertEqual(row[0], "template text")

        applied = wi.drain_narrative_upgrades()
        self.assertEqual(applied, 1)

        row = wi.event_store.connection.execute(
            "SELECT narrative, severity FROM interpretations "
            "WHERE interpretation_id = 'i1'").fetchone()
        self.assertEqual(row[0], "rich narrative")
        self.assertEqual(row[1], "major")
        l2 = wi.layer_store.query_by_tags(2, ["tone:grim"])
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0]["narrative"], "rich narrative")

        stats = wi.stats
        self.assertEqual(stats["upgrades_dispatched"], 1)
        self.assertEqual(stats["upgrades_applied"], 1)

    def test_failed_result_is_not_applied(self):
        result = NarrationResult(text="", success=False, error="boom")
        wi = self._make_interpreter(FakeWmsAI(result))
        interpretation = _interp("i1")
        wi.event_store.record_interpretation(interpretation)

        wi._dispatch_narrative_upgrade(interpretation, _trigger_event())
        self.assertEqual(wi.drain_narrative_upgrades(), 0)
        row = wi.event_store.connection.execute(
            "SELECT narrative FROM interpretations "
            "WHERE interpretation_id = 'i1'").fetchone()
        self.assertEqual(row[0], "template text")

    def test_backpressure_skips_instead_of_stalling(self):
        result = NarrationResult(text="never used", success=True,
                                 tags=["a:b"])
        fake = FakeWmsAI(result)
        wi = self._make_interpreter(fake)
        wi.max_upgrades_in_flight = 0  # saturate immediately

        wi._dispatch_narrative_upgrade(_interp("i1"), _trigger_event())
        self.assertEqual(len(fake.calls), 0)
        self.assertEqual(wi.stats["upgrades_skipped_backpressure"], 1)
        self.assertEqual(wi.drain_narrative_upgrades(), 0)

    def test_in_flight_counter_returns_to_zero(self):
        result = NarrationResult(text="x", success=True, tags=["a:b"])
        wi = self._make_interpreter(FakeWmsAI(result))
        interpretation = _interp("i1")
        wi.event_store.record_interpretation(interpretation)
        for _ in range(3):
            wi._dispatch_narrative_upgrade(interpretation, _trigger_event())
        self.assertEqual(wi._upgrades_in_flight, 0)


if __name__ == "__main__":
    unittest.main()
