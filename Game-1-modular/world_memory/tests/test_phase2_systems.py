"""Comprehensive tests for Living World Phase 2 systems.

Tests cover:
- Phase 2.2: BackendManager (Ollama, Claude, Mock backends)
- Phase 2.3: NPC Agent System (NPCMemory, NPCAgentSystem, gossip)
- Phase 2.4: Faction System (reputation, ripple, milestones)
- Phase 2.5: Ecosystem Agent (resource tracking, scarcity, regeneration)
- SQL Schema Expansion (new tables in EventStore)

Run: cd Game-1-modular && python ai/tests/test_phase2_systems.py
"""

import json
import os
import sys
import tempfile
import time

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _reset_singletons():
    """Reset all singletons between tests."""
    from events.event_bus import GameEventBus
    GameEventBus.reset()

    from world_memory.backends.backend_manager import BackendManager
    BackendManager.reset()

    from world_memory.npc.npc_memory import NPCMemoryManager
    NPCMemoryManager.reset()

    from world_memory.npc.npc_agent import NPCAgentSystem
    NPCAgentSystem.reset()

    from world_memory.factions.faction_system import FactionSystem
    FactionSystem.reset()

    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    EcosystemAgent.reset()


# ══════════════════════════════════════════════════════════════════════
# Phase 2.2: BackendManager Tests
# ══════════════════════════════════════════════════════════════════════

def test_backend_manager_initialization():
    """Test BackendManager loads config and sets up backends."""
    _reset_singletons()
    from world_memory.backends.backend_manager import BackendManager

    manager = BackendManager.get_instance()
    manager.initialize()

    assert manager._initialized, "Manager should be initialized"
    assert "mock" in manager._backends, "Mock backend should exist"
    assert manager._backends["mock"].is_available(), "Mock should be available"
    assert len(manager._fallback_chain) > 0, "Fallback chain should be set"

    print("  [PASS] BackendManager initialization")


def test_mock_backend_generate():
    """Test MockBackend generates template responses."""
    _reset_singletons()
    from world_memory.backends.backend_manager import MockBackend

    mock = MockBackend()
    assert mock.is_available()

    # Dialogue template
    text, err = mock.generate("You are an NPC", "dialogue with player")
    assert err is None
    assert "dialogue" in text.lower() or len(text) > 0
    assert mock.get_info()["name"] == "mock"

    # Quest template
    text, err = mock.generate("Generate a quest", "quest for the player")
    assert err is None
    assert "quest" in text.lower()

    # Lore template
    text, err = mock.generate("Write lore", "tell me about the lore of this land")
    assert err is None
    assert len(text) > 0

    print("  [PASS] MockBackend generate")


def test_backend_manager_generate_with_fallback():
    """Test BackendManager falls back to mock when other backends unavailable."""
    _reset_singletons()
    from world_memory.backends.backend_manager import BackendManager

    manager = BackendManager.get_instance()
    manager.initialize()

    # Should fall back to mock (ollama/claude likely unavailable in test env)
    text, err = manager.generate(
        task="dialogue",
        system_prompt="You are an NPC",
        user_prompt="Hello dialogue test",
    )
    assert err is None, f"Should succeed via fallback, got: {err}"
    assert len(text) > 0, "Should return text"

    print("  [PASS] BackendManager generate with fallback")


def test_backend_manager_singleton():
    """Test BackendManager singleton pattern."""
    _reset_singletons()
    from world_memory.backends.backend_manager import BackendManager, get_backend_manager

    m1 = BackendManager.get_instance()
    m2 = get_backend_manager()
    assert m1 is m2, "Should return same instance"

    print("  [PASS] BackendManager singleton")


def test_backend_manager_stats():
    """Test BackendManager stats reporting."""
    _reset_singletons()
    from world_memory.backends.backend_manager import BackendManager

    manager = BackendManager.get_instance()
    manager.initialize()

    stats = manager.stats
    assert stats["initialized"] is True
    assert "backends" in stats
    assert "mock" in stats["backends"]
    assert stats["backends"]["mock"]["available"] is True

    print("  [PASS] BackendManager stats")


def test_backend_manager_override():
    """Test generating with a specific backend override."""
    _reset_singletons()
    from world_memory.backends.backend_manager import BackendManager

    manager = BackendManager.get_instance()
    manager.initialize()

    text, err = manager.generate(
        task="dialogue",
        system_prompt="test",
        user_prompt="test dialogue",
        backend_override="mock",
    )
    assert err is None
    assert len(text) > 0

    print("  [PASS] BackendManager override")


# ══════════════════════════════════════════════════════════════════════
# Phase 2.3: NPC Memory Tests
# ══════════════════════════════════════════════════════════════════════

def test_npc_memory_basic():
    """Test NPCMemory creation and manipulation."""
    _reset_singletons()
    from world_memory.npc.npc_memory import NPCMemory

    mem = NPCMemory(npc_id="blacksmith_01")
    assert mem.relationship_score == 0.0
    assert mem.emotional_state == "neutral"
    assert mem.interaction_count == 0

    # Adjust relationship
    mem.adjust_relationship(0.15)
    assert abs(mem.relationship_score - 0.15) < 0.001

    # Clamp to bounds
    mem.adjust_relationship(2.0)
    assert mem.relationship_score == 1.0

    mem.adjust_relationship(-3.0)
    assert mem.relationship_score == -1.0

    print("  [PASS] NPCMemory basic operations")


def test_npc_memory_knowledge():
    """Test NPCMemory knowledge management."""
    _reset_singletons()
    from world_memory.npc.npc_memory import NPCMemory

    mem = NPCMemory(npc_id="test_npc")
    mem._max_knowledge = 5

    for i in range(8):
        mem.add_knowledge(f"Fact {i}")

    assert len(mem.knowledge) == 5, f"Should trim to 5, got {len(mem.knowledge)}"
    assert mem.knowledge[0] == "Fact 3", "Should keep most recent"
    assert mem.knowledge[-1] == "Fact 7"

    # Duplicates rejected
    mem.add_knowledge("Fact 7")
    assert len(mem.knowledge) == 5

    print("  [PASS] NPCMemory knowledge")


def test_npc_memory_serialization():
    """Test NPCMemory serialization round-trip."""
    _reset_singletons()
    from world_memory.npc.npc_memory import NPCMemory

    mem = NPCMemory(npc_id="test_npc")
    mem.adjust_relationship(0.5)
    mem.set_emotion("happy")
    mem.add_knowledge("The player is a skilled crafter")
    mem.add_reputation_tag("crafter")
    mem.interaction_count = 3
    mem.conversation_summary = "Discussed crafting."

    data = mem.to_dict()
    restored = NPCMemory.from_dict(data)

    assert restored.npc_id == "test_npc"
    assert abs(restored.relationship_score - 0.5) < 0.001
    assert restored.emotional_state == "happy"
    assert "The player is a skilled crafter" in restored.knowledge
    assert "crafter" in restored.player_reputation_tags
    assert restored.interaction_count == 3

    print("  [PASS] NPCMemory serialization")


def test_npc_memory_manager():
    """Test NPCMemoryManager singleton and bulk operations."""
    _reset_singletons()
    from world_memory.npc.npc_memory import NPCMemoryManager

    mgr = NPCMemoryManager.get_instance()
    mgr.initialize()

    m1 = mgr.get_memory("npc_a")
    m2 = mgr.get_memory("npc_b")
    m3 = mgr.get_memory("npc_a")  # Same as m1

    assert m1 is m3, "Same NPC should return same memory"
    assert m1 is not m2

    m1.adjust_relationship(0.3)
    m2.adjust_relationship(-0.2)

    # Save all
    data = mgr.save_all()
    assert "npc_a" in data
    assert "npc_b" in data
    assert abs(data["npc_a"]["relationship_score"] - 0.3) < 0.001

    # Load all
    mgr2 = NPCMemoryManager()
    mgr2.initialize()
    mgr2.load_all(data)
    assert abs(mgr2.get_memory("npc_a").relationship_score - 0.3) < 0.001
    assert abs(mgr2.get_memory("npc_b").relationship_score - (-0.2)) < 0.001

    print("  [PASS] NPCMemoryManager")


def test_npc_agent_fallback_dialogue():
    """Test NPCAgentSystem generates fallback dialogue without LLM."""
    _reset_singletons()
    from world_memory.npc.npc_agent import NPCAgentSystem
    from world_memory.npc.npc_memory import NPCMemoryManager

    mem_mgr = NPCMemoryManager.get_instance()
    mem_mgr.initialize()

    agent = NPCAgentSystem.get_instance()
    agent.initialize(memory_manager=mem_mgr)
    agent.assign_personality("blacksmith_01", "blacksmith")

    result = agent.generate_dialogue(
        "blacksmith_01", "Hello there!", npc_name="Thorin"
    )
    assert result.success
    assert result.from_fallback  # No backend, so fallback
    assert len(result.text) > 0

    print("  [PASS] NPCAgent fallback dialogue")


def test_npc_agent_with_mock_backend():
    """Test NPCAgentSystem with mock backend for dialogue."""
    _reset_singletons()
    from world_memory.npc.npc_agent import NPCAgentSystem
    from world_memory.npc.npc_memory import NPCMemoryManager
    from world_memory.backends.backend_manager import BackendManager

    mem_mgr = NPCMemoryManager.get_instance()
    mem_mgr.initialize()

    backend_mgr = BackendManager.get_instance()
    backend_mgr.initialize()

    agent = NPCAgentSystem.get_instance()
    agent.initialize(memory_manager=mem_mgr, backend_manager=backend_mgr)
    agent.assign_personality("merchant_01", "merchant")

    result = agent.generate_dialogue(
        "merchant_01", "What do you sell?", npc_name="Merchant Gale"
    )
    assert result.success
    assert len(result.text) > 0

    # Check memory was updated
    mem = mem_mgr.get_memory("merchant_01")
    assert mem.interaction_count >= 1

    print("  [PASS] NPCAgent with mock backend")


def test_npc_gossip_propagation():
    """Test gossip propagation scheduling and delivery."""
    _reset_singletons()
    from world_memory.npc.npc_agent import NPCAgentSystem
    from world_memory.npc.npc_memory import NPCMemoryManager

    mem_mgr = NPCMemoryManager.get_instance()
    mem_mgr.initialize()

    # Pre-create memories so agent knows about these NPCs
    mem_mgr.get_memory("npc_a")
    mem_mgr.get_memory("npc_b")

    agent = NPCAgentSystem.get_instance()
    agent.initialize(memory_manager=mem_mgr)
    agent.assign_personality("npc_a", "blacksmith")
    agent.assign_personality("npc_b", "guard")

    # Propagate gossip
    count = agent.propagate_gossip(
        event_summary="A dire wolf was slain near the forge",
        significance=0.5,
        source_x=10.0, source_y=20.0,
        event_category="population_change",
        game_time=100.0,
    )
    assert count >= 1, f"At least one NPC should receive gossip, got {count}"

    # Deliver gossip (game_time past delivery time)
    delivered = agent.update(game_time=500.0)
    assert delivered >= 1, f"Should deliver gossip, got {delivered}"

    # Check NPC knowledge was updated
    mem_b = mem_mgr.get_memory("npc_b")
    assert any("dire wolf" in k for k in mem_b.knowledge), \
        f"NPC should know about wolf: {mem_b.knowledge}"

    print("  [PASS] NPC gossip propagation")


def test_npc_event_reactions():
    """Test NPCs reacting to world events."""
    _reset_singletons()
    from world_memory.npc.npc_agent import NPCAgentSystem
    from world_memory.npc.npc_memory import NPCMemoryManager

    mem_mgr = NPCMemoryManager.get_instance()
    mem_mgr.initialize()

    agent = NPCAgentSystem.get_instance()
    agent.initialize(memory_manager=mem_mgr)
    agent.assign_personality("guard_01", "guard")

    mem = mem_mgr.get_memory("guard_01")
    old_score = mem.relationship_score

    agent.on_world_event("ENEMY_KILLED", {"enemy_type": "wolf"})

    new_score = mem.relationship_score
    assert new_score > old_score, "Guard should appreciate monster slaying"

    print("  [PASS] NPC event reactions")


# ══════════════════════════════════════════════════════════════════════
# Phase 2.4: Faction System Tests
# ══════════════════════════════════════════════════════════════════════

def test_faction_initialization():
    """Test FactionSystem loads definitions correctly."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    assert system._initialized
    assert len(system._factions) >= 4, f"Should have 4+ factions, got {len(system._factions)}"
    assert "village_guard" in system._factions
    assert "crafters_guild" in system._factions
    assert system.get_reputation("village_guard") == 0.0

    print("  [PASS] Faction initialization")


def test_faction_modify_reputation():
    """Test basic reputation modification."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    new_score = system.modify_reputation(
        "village_guard", 0.3, "Helped defend the village"
    )
    assert abs(new_score - 0.3) < 0.001
    assert abs(system.get_reputation("village_guard") - 0.3) < 0.001

    # Verify history
    history = system.get_recent_history("village_guard")
    assert len(history) >= 1
    assert history[-1].reason == "Helped defend the village"

    print("  [PASS] Faction modify reputation")


def test_faction_clamping():
    """Test reputation clamping to [-1.0, 1.0]."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    system.modify_reputation("village_guard", 5.0, "Big boost")
    assert system.get_reputation("village_guard") == 1.0

    system.modify_reputation("village_guard", -10.0, "Big drop")
    assert system.get_reputation("village_guard") == -1.0

    print("  [PASS] Faction clamping")


def test_faction_ripple_effects():
    """Test reputation ripple to allied/hostile factions."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    # Large change to village_guard should ripple to allies
    system.modify_reputation(
        "village_guard", 0.5, "Major contribution",
        apply_ripple=True,
    )

    # Crafters guild is allied (0.3 relationship) — should get positive ripple
    cg_rep = system.get_reputation("crafters_guild")
    assert cg_rep > 0, f"Crafters guild should get positive ripple, got {cg_rep}"

    print("  [PASS] Faction ripple effects")


def test_faction_milestones():
    """Test reputation milestone detection."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    milestones_received = []

    def on_milestone(event):
        milestones_received.append(event.data)

    bus.subscribe("FACTION_MILESTONE_REACHED", on_milestone)

    system = FactionSystem.get_instance()
    system.initialize()

    # Push past 0.25 threshold
    system.modify_reputation("village_guard", 0.26, "Good deeds")

    assert len(milestones_received) >= 1, "Should receive milestone event"
    assert milestones_received[0]["threshold"] == 0.25
    assert milestones_received[0]["milestone_label"] == "Recognized"

    crossed = system.get_crossed_milestones("village_guard")
    assert 0.25 in crossed

    print("  [PASS] Faction milestones")


def test_faction_labels():
    """Test reputation label calculation."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    assert system.get_reputation_label("village_guard") == "neutral"

    system.modify_reputation("village_guard", 0.6, "test", apply_ripple=False)
    assert system.get_reputation_label("village_guard") == "respected"

    system.modify_reputation("village_guard", -1.2, "test", apply_ripple=False)
    assert system.get_reputation_label("village_guard") == "hostile"

    print("  [PASS] Faction labels")


def test_faction_bus_integration():
    """Test FactionSystem reacts to GameEventBus events."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem
    from events.event_bus import GameEventBus, GameEvent

    bus = GameEventBus.get_instance()
    system = FactionSystem.get_instance()
    system.initialize()

    old_guard = system.get_reputation("village_guard")

    # Simulate killing an enemy
    bus.publish("ENEMY_KILLED", {"enemy_id": "wolf_01"}, source="test")

    new_guard = system.get_reputation("village_guard")
    assert new_guard > old_guard, "Guard rep should increase from enemy kill"

    print("  [PASS] Faction bus integration")


def test_faction_serialization():
    """Test faction save/load round-trip."""
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem

    system = FactionSystem.get_instance()
    system.initialize()

    system.modify_reputation("village_guard", 0.4, "test", apply_ripple=False)
    system.modify_reputation("crafters_guild", -0.2, "test", apply_ripple=False)
    system.assign_npc_to_faction("npc_01", "village_guard")

    data = system.save()

    # Restore into new system
    _reset_singletons()
    from world_memory.factions.faction_system import FactionSystem as FS2
    system2 = FS2.get_instance()
    system2.initialize()
    system2.load(data)

    assert abs(system2.get_reputation("village_guard") - 0.4) < 0.001
    assert abs(system2.get_reputation("crafters_guild") - (-0.2)) < 0.001
    assert system2.get_npc_faction("npc_01") == "village_guard"

    print("  [PASS] Faction serialization")


# ══════════════════════════════════════════════════════════════════════
# Phase 2.5: Ecosystem Agent Tests
# ══════════════════════════════════════════════════════════════════════

def test_ecosystem_initialization():
    """Test EcosystemAgent loads config and biome defaults."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent

    agent = EcosystemAgent.get_instance()
    agent.initialize()

    assert agent._initialized
    assert len(agent._biomes) >= 5, f"Should have 5+ biomes, got {len(agent._biomes)}"
    assert "forest" in agent._biomes
    assert "mountain" in agent._biomes

    forest = agent._biomes["forest"]
    assert "oak_log" in forest.resources
    assert forest.resources["oak_log"].initial_total == 300

    print("  [PASS] Ecosystem initialization")


def test_ecosystem_resource_gathering():
    """Test resource depletion from gathering events."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Check initial state
    info = agent.get_resource_info("mountain", "iron_ore")
    assert info is not None
    assert info["current"] == 250.0
    assert info["gathered"] == 0

    # Simulate gathering
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "iron_ore",
        "quantity": 10,
        "biome": "mountain",
    }, source="test")

    info = agent.get_resource_info("mountain", "iron_ore")
    assert info["current"] == 240.0
    assert info["gathered"] == 10

    print("  [PASS] Ecosystem resource gathering")


def test_ecosystem_scarcity_detection():
    """Test scarcity flag triggers at thresholds."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    scarcity_events = []

    def on_scarcity(event):
        scarcity_events.append(event.data)

    bus.subscribe("RESOURCE_SCARCITY", on_scarcity)

    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Deplete mithril_ore (initial=20) past 70% threshold
    # Need to gather 14+ units (14/20 = 70%)
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "mithril_ore",
        "quantity": 15,
        "biome": "mountain",
    }, source="test")

    info = agent.get_resource_info("mountain", "mithril_ore")
    assert info["scarce"], f"Should be scarce at 75% depletion"

    assert len(scarcity_events) >= 1, "Should publish scarcity event"
    assert scarcity_events[0]["severity"] == "scarce"

    # Deplete past 90% threshold
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "mithril_ore",
        "quantity": 4,
        "biome": "mountain",
    }, source="test")

    info = agent.get_resource_info("mountain", "mithril_ore")
    assert info["critical"], "Should be critical at 95% depletion"

    print("  [PASS] Ecosystem scarcity detection")


def test_ecosystem_regeneration():
    """Test resource regeneration over time."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Deplete some resource
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "oak_log",
        "quantity": 100,
        "biome": "forest",
    }, source="test")

    info = agent.get_resource_info("forest", "oak_log")
    assert info["current"] == 200.0

    # Tick with time elapsed (regen rate = 300s per unit for "normal")
    # After 600 game-seconds, should regen 2 units
    agent._last_tick_time = 1.0  # Simulate a prior tick
    agent._tick_interval = 0  # Allow immediate tick
    agent.tick(601.0)

    info = agent.get_resource_info("forest", "oak_log")
    assert info["current"] > 200.0, f"Should regenerate, got {info['current']}"

    print("  [PASS] Ecosystem regeneration")


def test_ecosystem_scarcity_report():
    """Test scarcity report API."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Initially no scarcity
    report = agent.get_scarcity_report()
    assert len(report) == 0, "Should start with no scarcity"

    # Deplete crystal in cave (initial=40, deplete 30 → 75%)
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "crystal",
        "quantity": 30,
        "biome": "cave",
    }, source="test")

    report = agent.get_scarcity_report()
    assert "cave" in report, f"Cave should have scarcity: {report}"
    assert any(r["resource_id"] == "crystal" for r in report["cave"])

    print("  [PASS] Ecosystem scarcity report")


def test_ecosystem_serialization():
    """Test ecosystem save/load round-trip."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Modify state
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "iron_ore",
        "quantity": 50,
        "biome": "mountain",
    }, source="test")

    data = agent.save()

    # Restore
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent as EA2
    bus2 = __import__("events.event_bus", fromlist=["GameEventBus"]).GameEventBus.get_instance()
    agent2 = EA2.get_instance()
    agent2.initialize()
    agent2.load(data)

    info = agent2.get_resource_info("mountain", "iron_ore")
    assert info["current"] == 200.0
    assert info["gathered"] == 50

    print("  [PASS] Ecosystem serialization")


def test_ecosystem_dynamic_resource_tracking():
    """Test that unknown resources are tracked dynamically."""
    _reset_singletons()
    from world_memory.ecosystem.ecosystem_agent import EcosystemAgent
    from events.event_bus import GameEventBus

    bus = GameEventBus.get_instance()
    agent = EcosystemAgent.get_instance()
    agent.initialize()

    # Gather a resource not in biome defaults
    bus.publish("RESOURCE_GATHERED", {
        "resource_id": "rare_gem",
        "quantity": 5,
        "biome": "swamp",
    }, source="test")

    info = agent.get_resource_info("swamp", "rare_gem")
    assert info is not None, "Should track new resources dynamically"
    assert info["gathered"] == 5

    print("  [PASS] Ecosystem dynamic resource tracking")


# ══════════════════════════════════════════════════════════════════════
# SQL Schema Expansion Tests
# ══════════════════════════════════════════════════════════════════════

def test_sql_npc_memory_tables():
    """Test NPC memory CRUD in EventStore."""
    _reset_singletons()
    from world_memory.memory.event_store import EventStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        # Save NPC memory
        store.save_npc_memory("npc_01", {
            "relationship_score": 0.35,
            "interaction_count": 5,
            "last_interaction_time": 100.0,
            "emotional_state": "happy",
            "knowledge": ["The player is a crafter", "Wolves are nearby"],
            "conversation_summary": "Discussed swords.",
            "player_reputation_tags": ["crafter", "hero"],
            "quest_state": {"quest_01": "active"},
        })

        # Load it back
        data = store.load_npc_memory("npc_01")
        assert data is not None
        assert abs(data["relationship_score"] - 0.35) < 0.001
        assert data["interaction_count"] == 5
        assert data["emotional_state"] == "happy"
        assert len(data["knowledge"]) == 2
        assert "crafter" in data["player_reputation_tags"]
        assert data["quest_state"]["quest_01"] == "active"

        # Load all
        store.save_npc_memory("npc_02", {
            "relationship_score": -0.1,
            "interaction_count": 1,
            "emotional_state": "neutral",
            "knowledge": [],
            "player_reputation_tags": [],
            "quest_state": {},
        })

        all_data = store.load_all_npc_memories()
        assert len(all_data) == 2
        assert "npc_01" in all_data
        assert "npc_02" in all_data

        store.close()

    print("  [PASS] SQL NPC memory tables")


def test_sql_faction_tables():
    """Test faction state CRUD in EventStore."""
    _reset_singletons()
    from world_memory.memory.event_store import EventStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        store.save_faction_state(
            "village_guard", 0.4, [0.25], "Helped defend", 500.0
        )
        store.save_faction_state(
            "crafters_guild", -0.1, [], "Minor offense", 600.0
        )

        all_states = store.load_all_faction_states()
        assert len(all_states) == 2
        assert abs(all_states["village_guard"]["player_reputation"] - 0.4) < 0.001
        assert 0.25 in all_states["village_guard"]["crossed_milestones"]

        # Test history
        store.save_faction_history([
            {"faction_id": "village_guard", "delta": 0.1, "new_score": 0.1,
             "reason": "First deed", "game_time": 100.0, "is_ripple": False},
            {"faction_id": "village_guard", "delta": 0.3, "new_score": 0.4,
             "reason": "Second deed", "game_time": 500.0, "is_ripple": False},
        ])

        store.close()

    print("  [PASS] SQL faction tables")


def test_sql_biome_resource_tables():
    """Test biome resource state CRUD in EventStore."""
    _reset_singletons()
    from world_memory.memory.event_store import EventStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = EventStore(save_dir=tmpdir)

        store.save_biome_resource("mountain", "iron_ore", {
            "initial_total": 250,
            "current_total": 180.5,
            "total_gathered": 70,
            "regeneration_rate": 600.0,
            "is_scarce": False,
            "is_critical": False,
        })

        store.save_biome_resource("forest", "oak_log", {
            "initial_total": 300,
            "current_total": 50.0,
            "total_gathered": 250,
            "regeneration_rate": 300.0,
            "is_scarce": True,
            "is_critical": False,
        })

        all_data = store.load_all_biome_resources()
        assert "mountain" in all_data
        assert "forest" in all_data
        assert abs(all_data["mountain"]["iron_ore"]["current_total"] - 180.5) < 0.1
        assert all_data["forest"]["oak_log"]["is_scarce"] is True

        store.close()

    print("  [PASS] SQL biome resource tables")


# ══════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all Phase 2 tests."""
    tests = [
        # Phase 2.2: BackendManager
        ("BackendManager", [
            test_backend_manager_initialization,
            test_mock_backend_generate,
            test_backend_manager_generate_with_fallback,
            test_backend_manager_singleton,
            test_backend_manager_stats,
            test_backend_manager_override,
        ]),
        # Phase 2.3: NPC Agent System
        ("NPC Agent System", [
            test_npc_memory_basic,
            test_npc_memory_knowledge,
            test_npc_memory_serialization,
            test_npc_memory_manager,
            test_npc_agent_fallback_dialogue,
            test_npc_agent_with_mock_backend,
            test_npc_gossip_propagation,
            test_npc_event_reactions,
        ]),
        # Phase 2.4: Faction System
        ("Faction System", [
            test_faction_initialization,
            test_faction_modify_reputation,
            test_faction_clamping,
            test_faction_ripple_effects,
            test_faction_milestones,
            test_faction_labels,
            test_faction_bus_integration,
            test_faction_serialization,
        ]),
        # Phase 2.5: Ecosystem Agent
        ("Ecosystem Agent", [
            test_ecosystem_initialization,
            test_ecosystem_resource_gathering,
            test_ecosystem_scarcity_detection,
            test_ecosystem_regeneration,
            test_ecosystem_scarcity_report,
            test_ecosystem_serialization,
            test_ecosystem_dynamic_resource_tracking,
        ]),
        # SQL Schema
        ("SQL Schema Expansion", [
            test_sql_npc_memory_tables,
            test_sql_faction_tables,
            test_sql_biome_resource_tables,
        ]),
    ]

    total_passed = 0
    total_failed = 0
    failures = []

    print("=" * 60)
    print("Living World Phase 2 — Comprehensive Test Suite")
    print("=" * 60)

    for section_name, section_tests in tests:
        print(f"\n--- {section_name} ---")
        for test_fn in section_tests:
            try:
                test_fn()
                total_passed += 1
            except Exception as e:
                total_failed += 1
                failures.append((test_fn.__name__, str(e)))
                print(f"  [FAIL] {test_fn.__name__}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Results: {total_passed} passed, {total_failed} failed, "
          f"{total_passed + total_failed} total")
    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  - {name}: {err}")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    os.chdir(_project_root)
    success = run_all_tests()
    sys.exit(0 if success else 1)
