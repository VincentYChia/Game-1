"""Phase 7 mixed-trigger polish + quest archive tests (2026-06-03).

Three new substrate components:

- :class:`QuestArchiveDatabase` — separate substrate for completed-
  quest prose history. WMS sees quest *facts* via existing event
  types; the archive holds the *prose* the WNS chronicler reads.
- :class:`MixedTriggerArbiter` — deterministic decision when a
  narrative and a behavior firing concur at the same address.
- :class:`PlayerPresenceDriftDetector` — negative-pattern behavior
  trigger (locality absence as signal).
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


# ── QuestArchiveDatabase ─────────────────────────────────────────────


class QuestArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        from data.databases.quest_archive_db import QuestArchiveDatabase
        QuestArchiveDatabase.reset()
        self.db = QuestArchiveDatabase.get_instance()

    def tearDown(self) -> None:
        from data.databases.quest_archive_db import QuestArchiveDatabase
        QuestArchiveDatabase.reset()

    def _make_record(
        self, quest_id: str, **overrides,
    ):
        from data.databases.quest_archive_db import ArchivedQuestRecord
        kwargs = dict(
            quest_id=quest_id,
            original_quest_def_json={"name": quest_id},
            time_started=10.0,
            time_completed=20.0,
            duration=10.0,
            actual_result="succeeded",
            actual_rewards_granted={"gold": 100},
            participating_npcs=["captain_vell"],
            participating_entities=["moors_copper", "copperlash_rider"],
            archived_narrative_tags=["vendetta", "moors"],
            wns_thread_id="thread_moors_vendetta",
            archived_at_game_day=10,
        )
        kwargs.update(overrides)
        return ArchivedQuestRecord(**kwargs)

    def test_archive_and_get(self) -> None:
        record = self._make_record("vendetta_001")
        self.db.archive(record)
        got = self.db.get("vendetta_001")
        self.assertIsNotNone(got)
        self.assertEqual(got.quest_id, "vendetta_001")
        self.assertEqual(got.duration, 10.0)

    def test_query_by_tags_match_all(self) -> None:
        self.db.archive(self._make_record(
            "q1", archived_narrative_tags=["vendetta", "moors"],
        ))
        self.db.archive(self._make_record(
            "q2", archived_narrative_tags=["vendetta", "harbor"],
        ))
        self.db.archive(self._make_record(
            "q3", archived_narrative_tags=["delivery", "moors"],
        ))
        results = self.db.query_by_tags(["vendetta", "moors"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].quest_id, "q1")

    def test_query_by_tags_match_any(self) -> None:
        self.db.archive(self._make_record(
            "q1", archived_narrative_tags=["vendetta"],
        ))
        self.db.archive(self._make_record(
            "q2", archived_narrative_tags=["delivery"],
        ))
        results = self.db.query_by_tags(
            ["vendetta", "delivery"], match_all=False,
        )
        self.assertEqual(len(results), 2)

    def test_recent_archived_returns_newest_first(self) -> None:
        self.db.archive(self._make_record("old", time_completed=10.0))
        self.db.archive(self._make_record("mid", time_completed=20.0))
        self.db.archive(self._make_record("new", time_completed=30.0))
        recent = self.db.recent_archived(limit=2)
        self.assertEqual([r.quest_id for r in recent], ["new", "mid"])

    def test_query_by_npc(self) -> None:
        self.db.archive(self._make_record(
            "q1", participating_npcs=["captain_vell", "mayor"],
        ))
        self.db.archive(self._make_record(
            "q2", participating_npcs=["mayor"],
        ))
        self.assertEqual(len(self.db.query_by_npc("captain_vell")), 1)
        self.assertEqual(len(self.db.query_by_npc("mayor")), 2)

    def test_round_trip_via_dict(self) -> None:
        from data.databases.quest_archive_db import ArchivedQuestRecord
        record = self._make_record("probe")
        restored = ArchivedQuestRecord.from_dict(record.to_dict())
        self.assertEqual(restored.quest_id, record.quest_id)
        self.assertEqual(restored.participating_npcs, record.participating_npcs)


# ── MixedTriggerArbiter ──────────────────────────────────────────────


class MixedTriggerArbiterTests(unittest.TestCase):
    def _make(self, archetype, address, purpose, game_time=100.0):
        from world_system.wns.mixed_trigger_arbiter import FiringCandidate
        return FiringCandidate(
            archetype=archetype, address=address, purpose=purpose,
            bundle=None, game_time=game_time,
        )

    def test_outside_window_issue_both(self) -> None:
        from world_system.wns.mixed_trigger_arbiter import (
            MixedTriggerArbiter,
        )
        arb = MixedTriggerArbiter(window_seconds=30.0)
        decision = arb.decide(
            self._make("narrative", "addr:a", "new-skill",
                       game_time=100.0),
            self._make("behavior", "addr:a", "new-skill",
                       game_time=200.0),  # 100 s apart, outside
        )
        self.assertEqual(decision, arb.DECISION_BOTH)

    def test_different_addresses_issue_both(self) -> None:
        from world_system.wns.mixed_trigger_arbiter import (
            MixedTriggerArbiter,
        )
        arb = MixedTriggerArbiter()
        decision = arb.decide(
            self._make("narrative", "addr:a", "new-skill"),
            self._make("behavior", "addr:b", "new-skill"),
        )
        self.assertEqual(decision, arb.DECISION_BOTH)

    def test_same_purpose_suppress_behavior(self) -> None:
        from world_system.wns.mixed_trigger_arbiter import (
            MixedTriggerArbiter,
        )
        arb = MixedTriggerArbiter()
        decision = arb.decide(
            self._make("narrative", "addr:a", "new-skill"),
            self._make("behavior", "addr:a", "new-skill"),
        )
        self.assertEqual(decision, arb.DECISION_SUPPRESS_BEHAVIOR)

    def test_complementary_purposes_issue_mixed(self) -> None:
        # The user's chunks pseudo-trace: narrative new-chunk +
        # behavior new-material → merge.
        from world_system.wns.mixed_trigger_arbiter import (
            MixedTriggerArbiter,
        )
        arb = MixedTriggerArbiter()
        decision = arb.decide(
            self._make("narrative", "addr:a", "new-chunk"),
            self._make("behavior", "addr:a", "new-material"),
        )
        self.assertEqual(decision, arb.DECISION_MIXED)

    def test_unrelated_purposes_issue_both(self) -> None:
        from world_system.wns.mixed_trigger_arbiter import (
            MixedTriggerArbiter,
        )
        arb = MixedTriggerArbiter()
        decision = arb.decide(
            self._make("narrative", "addr:a", "new-title"),
            self._make("behavior", "addr:a", "new-material"),
        )
        self.assertEqual(decision, arb.DECISION_BOTH)


# ── PlayerPresenceDriftDetector ──────────────────────────────────────


class DriftDetectorTests(unittest.TestCase):
    def _make_store(self):
        import sqlite3
        from world_system.world_memory.stat_store import StatStore
        conn = sqlite3.connect(":memory:")
        store = StatStore(conn=conn)
        store._manifest = {
            "combat.kills.locality.*": {
                "tags": ["domain:combat", "locality:{dim}"],
            },
            "meta.last_activity_day.locality.*": {
                "tags": ["domain:meta", "locality:{dim}"],
            },
        }
        return store

    def test_no_store_returns_empty(self) -> None:
        from world_system.wns.presence_drift_detector import (
            PlayerPresenceDriftDetector,
        )
        detector = PlayerPresenceDriftDetector(
            stat_store=None, absence_threshold_days=30,
        )
        self.assertEqual(
            detector.scan(current_game_day=100), [],
        )

    def test_locality_under_threshold_skipped(self) -> None:
        from world_system.wns.presence_drift_detector import (
            PlayerPresenceDriftDetector,
        )
        store = self._make_store()
        store.increment("combat.kills.locality.tarmouth", 20.0)
        store.set_value(
            "meta.last_activity_day.locality.tarmouth", 95.0,
        )
        detector = PlayerPresenceDriftDetector(
            stat_store=store, absence_threshold_days=30,
        )
        # 100 - 95 = 5 days, below threshold
        candidates = detector.scan(
            current_game_day=100, known_localities=["tarmouth"],
        )
        self.assertEqual(candidates, [])

    def test_locality_past_threshold_surfaced(self) -> None:
        from world_system.wns.presence_drift_detector import (
            PlayerPresenceDriftDetector,
        )
        store = self._make_store()
        store.increment("combat.kills.locality.tarmouth", 20.0)
        store.set_value(
            "meta.last_activity_day.locality.tarmouth", 30.0,
        )
        detector = PlayerPresenceDriftDetector(
            stat_store=store, absence_threshold_days=30,
        )
        # 100 - 30 = 70 days, well past threshold
        candidates = detector.scan(
            current_game_day=100, known_localities=["tarmouth"],
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].locality_id, "tarmouth")
        self.assertEqual(candidates[0].days_since, 70)

    def test_locality_with_no_history_skipped(self) -> None:
        from world_system.wns.presence_drift_detector import (
            PlayerPresenceDriftDetector,
        )
        store = self._make_store()
        # No historical activity at this locality.
        detector = PlayerPresenceDriftDetector(
            stat_store=store, absence_threshold_days=30,
            min_historical_activity=10,
        )
        candidates = detector.scan(
            current_game_day=100, known_localities=["never_visited"],
        )
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
