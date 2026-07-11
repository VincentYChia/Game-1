"""2026-07-11 affinity audit — time-compressed verification of the
faction/NPC affinity features that are only evident after hours of play.

Gaps this pins (all found orphaned despite working implementations):
1. NPC dialogue relationship persistence: the SQLite facade
   (hydrate_npc_from_db / flush_npc_to_db) had ZERO callers — hours of
   dialogue accumulated in-memory and vanished on quit.
2. Quest turn-in affinity: the live quest system moved NO affinity;
   quest_tool's designed deltas had no runtime caller.
3. The AffinityConsolidator (consolidated standing events) was never
   invoked.
Also certifies: accumulation → relationship-label threshold crossings,
WNS AffinityShift → FactionSystem, and location-inherited affinity.
"""
import os
import sys
import tempfile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

import pytest  # noqa: E402

from world_system.living_world.factions.faction_system import FactionSystem  # noqa: E402
from world_system.living_world.factions.quest_tool import QuestGenerator  # noqa: E402
from world_system.living_world.npc.npc_memory import NPCMemoryManager  # noqa: E402


@pytest.fixture()
def fs(tmp_path):
    FactionSystem.reset()
    fs = FactionSystem.get_instance()
    fs.db_path = tmp_path / "faction.db"   # isolate from real saves/
    fs.initialize()
    yield fs
    FactionSystem.reset()


@pytest.fixture()
def mem(fs):
    NPCMemoryManager.reset()
    m = NPCMemoryManager.get_instance()
    m.wire_faction_system(fs)
    yield m
    NPCMemoryManager.reset()


# ── 1. Persistence across "sessions" ─────────────────────────────────

def test_relationship_survives_session_restart(fs, mem):
    """Hours of dialogue -> quit -> relaunch: relationship must persist."""
    npc = "vell_sarn"
    m = mem.get_memory(npc)
    # Simulate ~50 positive exchanges over hours of play.
    for _ in range(50):
        m.adjust_relationship(0.01)
        m.interaction_count += 1
    mem.flush_npc_to_db(npc, game_time=500.0)

    # "Quit and relaunch": fresh manager, same FactionSystem DB.
    NPCMemoryManager.reset()
    m2mgr = NPCMemoryManager.get_instance()
    m2mgr.wire_faction_system(fs)
    m2 = m2mgr.hydrate_npc_from_db(npc)
    assert m2.relationship_score == pytest.approx(0.5, abs=0.01)
    assert m2.interaction_count == 50


def test_agent_flush_and_hydrate_pump(fs, mem):
    """The agent-side pump: flush after dialogue, hydrate on first touch."""
    from world_system.living_world.npc.npc_agent import NPCAgentSystem
    NPCAgentSystem.reset()
    agent = NPCAgentSystem.get_instance()
    agent.initialize(memory_manager=mem)

    m = agent._get_memory_hydrated("dock_hand")
    m.adjust_relationship(0.25)
    agent._flush_memory("dock_hand")

    row = fs.get_npc_affinity_toward_player("dock_hand")
    assert row == pytest.approx(25.0, abs=0.5), (
        "flush must write relationship (rescaled -100..100) to SQLite"
    )
    NPCAgentSystem.reset()


# ── 2. Quest turn-in moves affinity ──────────────────────────────────

def test_turn_in_derives_deltas_from_giver_tags(fs):
    fs.add_npc("captain_vell", "A copperlash captain.", game_time=1.0)
    fs.add_npc_belonging_tag("captain_vell", "guild:moors_raiders",
                             significance=0.9, role="captain")
    fs.add_npc_belonging_tag("captain_vell", "region:salt_moors",
                             significance=0.4, role="resident")

    applied = QuestGenerator.apply_turn_in(
        player_id="player", giver_npc_id="captain_vell",
        quest_id="generated_quest_xyz", game_time=10.0)

    assert applied["guild:moors_raiders"] == QuestGenerator.FACTION_PRIMARY_DELTA
    assert applied["region:salt_moors"] == QuestGenerator.FACTION_SECONDARY_DELTA
    assert fs.get_player_affinity("player", "guild:moors_raiders") == \
        pytest.approx(QuestGenerator.FACTION_PRIMARY_DELTA)
    assert fs.get_npc_affinity_toward_player("captain_vell") == \
        pytest.approx(QuestGenerator.NPC_TURN_IN_DELTA)


def test_explicit_deltas_win(fs):
    applied = QuestGenerator.apply_turn_in(
        player_id="player", giver_npc_id="",
        explicit_deltas={"guild:smiths": 12.0}, game_time=10.0)
    assert applied == {"guild:smiths": 12.0}
    assert fs.get_player_affinity("player", "guild:smiths") == pytest.approx(12.0)


def test_thirty_quests_accumulate_and_clamp(fs):
    """'Hours of play': 30 turn-ins for one faction accumulate and the
    value clamps at the +100 ceiling rather than overflowing."""
    fs.add_npc("giver", "n", game_time=0.0)
    fs.add_npc_belonging_tag("giver", "guild:smiths", significance=1.0)
    for i in range(30):
        QuestGenerator.apply_turn_in("player", "giver", game_time=float(i))
    assert fs.get_player_affinity("player", "guild:smiths") <= 100.0
    assert fs.get_player_affinity("player", "guild:smiths") > 50.0
    assert fs.get_npc_affinity_toward_player("giver") <= 100.0


# ── 3. Relationship labels cross thresholds over time ────────────────

def test_labels_progress_with_accumulated_dialogue(mem):
    thresholds = {"hostile": -0.6, "unfriendly": -0.2, "neutral": 0.2,
                  "friendly": 0.6, "trusted": 1.0}
    m = mem.get_memory("regular")
    seen = [m.get_relationship_label(thresholds)]
    for _ in range(100):
        m.adjust_relationship(0.01)
        label = m.get_relationship_label(thresholds)
        if label != seen[-1]:
            seen.append(label)
    assert seen[0] in ("neutral", "unfriendly")
    assert "friendly" in seen and "trusted" in seen, (
        f"labels never progressed: {seen}"
    )


# ── 4. WNS AffinityShift reaches FactionSystem ───────────────────────

def test_wns_shift_end_to_end(fs):
    from world_system.wns.affinity_shift_parser import parse_affinity_shifts
    from world_system.wns.affinity_resolver import AffinityResolver

    narrative = ('The raiders overplayed their hand. '
                 '<AffinityShift><Target>faction:moors_raiders</Target>'
                 '<Scope>region:salt_moors</Scope>'
                 '<Effect>standing_delta: -6</Effect></AffinityShift>')
    shifts, cleaned = parse_affinity_shifts(narrative)
    resolver = AffinityResolver(faction_system=fs)
    records = resolver.resolve_batch(
        shifts, weaver_layer=4, weaver_address="region:salt_moors",
        narrative_event_id="row1", game_time=42.0)
    assert records[0].applied
    assert fs.get_player_affinity("region:salt_moors", "moors_raiders") == \
        pytest.approx(-6.0)
    assert "AffinityShift" not in cleaned


# ── 5. Location-inherited affinity ───────────────────────────────────

def test_inherited_affinity_sums_location_defaults(fs):
    """compute_inherited_affinity sums LOCATION DEFAULTS (tag -> value)
    along an address hierarchy — the mechanism dialogue_helper uses for
    an NPC's ambient faction climate."""
    cursor = fs.connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO location_affinity_defaults "
        "(address_tier, location_id, tag, affinity_value) VALUES (?,?,?,?)",
        ("nation", "nation:ardenreach", "guild:merchants", 20.0))
    cursor.execute(
        "INSERT OR REPLACE INTO location_affinity_defaults "
        "(address_tier, location_id, tag, affinity_value) VALUES (?,?,?,?)",
        ("region", "region:salt_moors", "guild:merchants", 15.0))
    fs.connection.commit()

    inherited = fs.compute_inherited_affinity(
        [("locality", "locality:tarmouth"),
         ("region", "region:salt_moors"),
         ("nation", "nation:ardenreach")])
    assert inherited.get("guild:merchants") == pytest.approx(35.0), (
        f"defaults should SUM down the hierarchy, got {inherited}"
    )


# ── 6. Consolidator publishes ────────────────────────────────────────

def test_consolidator_runs_and_summarizes(fs):
    fs.set_player_affinity("player", "guild:smiths", 30.0, game_time=1.0)
    fs.set_player_affinity("player", "guild:thieves", -20.0, game_time=1.0)
    from world_system.living_world.factions.consolidator import (
        AffinityConsolidator,
    )
    summary = AffinityConsolidator.consolidate_and_publish("player")
    assert summary, "consolidator returned an empty standing summary"
