"""FactionSystem — manages faction relationships, reputation, and ripple effects.

Tracks player reputation with each faction (-1.0 to 1.0), inter-faction
relationships, reputation history, and milestone unlocks.

Key mechanics:
- Reputation changes from world events (kills, crafting, gathering)
- Ripple effects: changing rep with one faction affects allied/hostile factions
- Milestones at 0.25/0.5/0.75 unlock content (dialogue, quests, recipes)
- Reputation history for narrative context

Configuration driven by AI-Config.JSON/faction-definitions.json.

Usage:
    system = FactionSystem.get_instance()
    system.initialize()
    system.modify_reputation("village_guard", 0.05, "Killed a wolf pack")
    label = system.get_reputation_label("village_guard")
    disposition = system.get_npc_disposition(npc_id)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from events.event_bus import get_event_bus


@dataclass
class FactionDefinition:
    """Static faction definition loaded from JSON."""
    faction_id: str
    name: str
    description: str = ""
    territory_regions: List[str] = field(default_factory=list)
    member_npc_ids: List[str] = field(default_factory=list)
    hostile_threshold: float = -0.5
    allied_threshold: float = 0.5
    tags: List[str] = field(default_factory=list)


@dataclass
class ReputationChange:
    """Record of a reputation change for history tracking."""
    faction_id: str
    delta: float
    new_score: float
    reason: str
    game_time: float
    is_ripple: bool = False


class FactionSystem:
    """Singleton system managing all faction state and reputation.

    Subscribes to GameEventBus for automatic reputation adjustments.
    Publishes FACTION_REP_CHANGED events when reputation shifts.
    """

    _instance: ClassVar[Optional[FactionSystem]] = None

    def __init__(self):
        self._factions: Dict[str, FactionDefinition] = {}
        self._player_reputation: Dict[str, float] = {}  # faction_id → score
        self._inter_faction: Dict[str, Dict[str, float]] = {}  # a → {b → relationship}
        self._reputation_history: List[ReputationChange] = []
        self._reputation_events: Dict[str, Dict[str, Dict]] = {}
        self._milestones: List[Dict[str, Any]] = []
        self._ripple_config: Dict[str, float] = {}
        self._crossed_milestones: Dict[str, List[float]] = {}  # faction_id → [thresholds crossed]
        self._npc_faction_map: Dict[str, str] = {}  # npc_id → faction_id
        self._initialized: bool = False
        self._bus_connected: bool = False

    @classmethod
    def get_instance(cls) -> FactionSystem:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance and cls._instance._bus_connected:
            cls._instance._disconnect_bus()
        cls._instance = None

    def initialize(self, config_path: Optional[str] = None) -> None:
        """Load faction definitions and subscribe to events.

        Args:
            config_path: Path to faction-definitions.json.
        """
        if self._initialized:
            return

        # Load config
        config = self._load_config(config_path)

        # Parse faction definitions
        for fid, fdata in config.get("factions", {}).items():
            self._factions[fid] = FactionDefinition(
                faction_id=fid,
                name=fdata.get("name", fid),
                description=fdata.get("description", ""),
                territory_regions=fdata.get("territory_regions", []),
                member_npc_ids=fdata.get("member_npc_ids", []),
                hostile_threshold=fdata.get("hostile_threshold", -0.5),
                allied_threshold=fdata.get("allied_threshold", 0.5),
                tags=fdata.get("tags", []),
            )
            # Initialize reputation at 0
            self._player_reputation[fid] = 0.0
            self._crossed_milestones[fid] = []

            # Build NPC→faction map
            for npc_id in fdata.get("member_npc_ids", []):
                self._npc_faction_map[npc_id] = fid

        # Inter-faction relationships
        self._inter_faction = config.get("inter_faction_relationships", {})

        # Reputation event modifiers
        self._reputation_events = config.get("reputation_events", {})

        # Milestones
        self._milestones = config.get("reputation_milestones", [])

        # Ripple config
        self._ripple_config = config.get("ripple_config", {
            "ally_ripple_factor": 0.3,
            "enemy_ripple_factor": -0.2,
            "neutral_ripple_factor": 0.0,
            "ripple_threshold": 0.1,
        })

        # Subscribe to relevant events on the bus
        self._connect_bus()

        self._initialized = True
        print(f"[FactionSystem] Initialized with {len(self._factions)} factions")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)

        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
        default_path = os.path.join(
            project_root, "world_system", "config", "faction-definitions.json"
        )
        if os.path.exists(default_path):
            with open(default_path, "r") as f:
                return json.load(f)

        return {}

    def _connect_bus(self) -> None:
        """Subscribe to GameEventBus for automatic reputation changes."""
        bus = get_event_bus()
        bus.subscribe("ENEMY_KILLED", self._on_event, priority=5)
        bus.subscribe("ITEM_CRAFTED", self._on_event, priority=5)
        bus.subscribe("RESOURCE_GATHERED", self._on_event, priority=5)
        bus.subscribe("LEVEL_UP", self._on_event, priority=5)
        self._bus_connected = True

    def _disconnect_bus(self) -> None:
        """Unsubscribe from GameEventBus."""
        bus = get_event_bus()
        bus.unsubscribe("ENEMY_KILLED", self._on_event)
        bus.unsubscribe("ITEM_CRAFTED", self._on_event)
        bus.unsubscribe("RESOURCE_GATHERED", self._on_event)
        bus.unsubscribe("LEVEL_UP", self._on_event)
        self._bus_connected = False

    # ── Event Handler ─────────────────────────────────────────────────

    def _on_event(self, event) -> None:
        """Handle a GameEventBus event and adjust reputations."""
        event_type = event.event_type
        modifiers = self._reputation_events.get(event_type, {})

        for faction_id, mod in modifiers.items():
            if faction_id not in self._factions:
                continue
            delta = mod.get("delta", 0.0)
            reason = mod.get("description", event_type)
            if delta != 0:
                self.modify_reputation(
                    faction_id, delta, reason,
                    game_time=getattr(event, "timestamp", 0.0),
                )

    # ── Public API ────────────────────────────────────────────────────

    def modify_reputation(self, faction_id: str, delta: float, reason: str,
                          game_time: float = 0.0,
                          apply_ripple: bool = True) -> Optional[float]:
        """Change player's reputation with a faction.

        Args:
            faction_id: Target faction.
            delta: Amount to change (-1.0 to 1.0 range).
            reason: Human-readable reason for change.
            game_time: Current game time.
            apply_ripple: If True, propagate to allied/hostile factions.

        Returns:
            New reputation score, or None if faction not found.
        """
        if faction_id not in self._factions:
            return None

        old_score = self._player_reputation.get(faction_id, 0.0)
        new_score = max(-1.0, min(1.0, old_score + delta))
        self._player_reputation[faction_id] = new_score

        # Record history
        change = ReputationChange(
            faction_id=faction_id,
            delta=delta,
            new_score=new_score,
            reason=reason,
            game_time=game_time,
            is_ripple=False,
        )
        self._reputation_history.append(change)
        # Keep history bounded
        if len(self._reputation_history) > 500:
            self._reputation_history = self._reputation_history[-500:]

        # Check milestones
        self._check_milestones(faction_id, old_score, new_score, game_time)

        # Publish event
        bus = get_event_bus()
        bus.publish("FACTION_REP_CHANGED", {
            "faction_id": faction_id,
            "old_score": old_score,
            "new_score": new_score,
            "delta": delta,
            "reason": reason,
        }, source="FactionSystem")

        # Ripple to related factions
        if apply_ripple and abs(delta) >= self._ripple_config.get("ripple_threshold", 0.1):
            self._apply_ripple(faction_id, delta, reason, game_time)

        return new_score

    def _apply_ripple(self, source_faction: str, delta: float,
                      reason: str, game_time: float) -> None:
        """Propagate reputation change to allied/hostile factions."""
        relationships = self._inter_faction.get(source_faction, {})
        ally_factor = self._ripple_config.get("ally_ripple_factor", 0.3)
        enemy_factor = self._ripple_config.get("enemy_ripple_factor", -0.2)

        for target_faction, relationship in relationships.items():
            if target_faction == source_faction:
                continue
            if target_faction not in self._factions:
                continue

            # Determine ripple factor based on relationship
            if relationship > 0.1:
                ripple_factor = ally_factor * relationship
            elif relationship < -0.1:
                ripple_factor = enemy_factor * abs(relationship)
            else:
                continue

            ripple_delta = delta * ripple_factor
            if abs(ripple_delta) < 0.001:
                continue

            old_score = self._player_reputation.get(target_faction, 0.0)
            new_score = max(-1.0, min(1.0, old_score + ripple_delta))
            self._player_reputation[target_faction] = new_score

            self._reputation_history.append(ReputationChange(
                faction_id=target_faction,
                delta=ripple_delta,
                new_score=new_score,
                reason=f"Ripple from {source_faction}: {reason}",
                game_time=game_time,
                is_ripple=True,
            ))

    def _check_milestones(self, faction_id: str, old_score: float,
                          new_score: float, game_time: float) -> None:
        """Check if a reputation milestone was crossed."""
        crossed = self._crossed_milestones.get(faction_id, [])
        for milestone in self._milestones:
            threshold = milestone.get("threshold", 0.0)
            if threshold in crossed:
                continue

            # Check if we crossed this threshold (in either direction)
            if threshold > 0:
                if old_score < threshold <= new_score:
                    crossed.append(threshold)
                    self._on_milestone_reached(
                        faction_id, milestone, new_score, game_time
                    )
            elif threshold < 0:
                if old_score > threshold >= new_score:
                    crossed.append(threshold)
                    self._on_milestone_reached(
                        faction_id, milestone, new_score, game_time
                    )

        self._crossed_milestones[faction_id] = crossed

    def _on_milestone_reached(self, faction_id: str, milestone: Dict,
                              score: float, game_time: float) -> None:
        """Handle a reputation milestone being reached."""
        label = milestone.get("label", "Unknown")
        unlock_type = milestone.get("unlock_type", "")
        faction = self._factions[faction_id]

        bus = get_event_bus()
        bus.publish("FACTION_MILESTONE_REACHED", {
            "faction_id": faction_id,
            "faction_name": faction.name,
            "milestone_label": label,
            "threshold": milestone.get("threshold", 0.0),
            "score": score,
            "unlock_type": unlock_type,
        }, source="FactionSystem")

        print(f"[FactionSystem] Milestone: {faction.name} → {label} "
              f"(score: {score:.2f}, unlock: {unlock_type})")

    def get_reputation(self, faction_id: str) -> float:
        """Get player's current reputation with a faction."""
        return self._player_reputation.get(faction_id, 0.0)

    def get_all_reputations(self) -> Dict[str, float]:
        """Get all faction reputations."""
        return dict(self._player_reputation)

    def get_reputation_label(self, faction_id: str) -> str:
        """Get human-readable reputation label for a faction."""
        score = self._player_reputation.get(faction_id, 0.0)
        faction = self._factions.get(faction_id)
        if not faction:
            return "unknown"

        if score <= faction.hostile_threshold:
            return "hostile"
        elif score <= -0.25:
            return "unfriendly"
        elif score < 0.1:
            return "neutral"
        elif score < 0.25:
            return "recognized"
        elif score < faction.allied_threshold:
            return "friendly"
        elif score < 0.75:
            return "respected"
        else:
            return "honored"

    def get_npc_disposition(self, npc_id: str) -> str:
        """Get disposition of an NPC based on their faction's player rep."""
        faction_id = self._npc_faction_map.get(npc_id)
        if not faction_id:
            return "neutral"
        return self.get_reputation_label(faction_id)

    def get_npc_faction(self, npc_id: str) -> Optional[str]:
        """Get the faction an NPC belongs to."""
        return self._npc_faction_map.get(npc_id)

    def assign_npc_to_faction(self, npc_id: str, faction_id: str) -> None:
        """Assign an NPC to a faction at runtime."""
        if faction_id in self._factions:
            self._npc_faction_map[npc_id] = faction_id
            if npc_id not in self._factions[faction_id].member_npc_ids:
                self._factions[faction_id].member_npc_ids.append(npc_id)

    def get_faction(self, faction_id: str) -> Optional[FactionDefinition]:
        """Get a faction definition."""
        return self._factions.get(faction_id)

    def get_recent_history(self, faction_id: Optional[str] = None,
                           limit: int = 20) -> List[ReputationChange]:
        """Get recent reputation change history."""
        history = self._reputation_history
        if faction_id:
            history = [h for h in history if h.faction_id == faction_id]
        return history[-limit:]

    def get_crossed_milestones(self, faction_id: str) -> List[float]:
        """Get thresholds already crossed for a faction."""
        return list(self._crossed_milestones.get(faction_id, []))

    # ── Serialization ─────────────────────────────────────────────────

    def save(self) -> Dict[str, Any]:
        """Serialize faction state for persistence."""
        return {
            "player_reputation": dict(self._player_reputation),
            "reputation_history": [
                {
                    "faction_id": rc.faction_id,
                    "delta": rc.delta,
                    "new_score": rc.new_score,
                    "reason": rc.reason,
                    "game_time": rc.game_time,
                    "is_ripple": rc.is_ripple,
                }
                for rc in self._reputation_history[-100:]  # Keep last 100
            ],
            "crossed_milestones": {
                fid: list(thresholds)
                for fid, thresholds in self._crossed_milestones.items()
            },
            "npc_faction_map": dict(self._npc_faction_map),
        }

    def load(self, data: Dict[str, Any]) -> None:
        """Restore faction state from saved data."""
        self._player_reputation = data.get("player_reputation", {})
        # Ensure all factions have a score
        for fid in self._factions:
            if fid not in self._player_reputation:
                self._player_reputation[fid] = 0.0

        self._crossed_milestones = {
            fid: list(thresholds)
            for fid, thresholds in data.get("crossed_milestones", {}).items()
        }

        self._npc_faction_map = data.get("npc_faction_map", {})

        # Restore history
        for entry in data.get("reputation_history", []):
            self._reputation_history.append(ReputationChange(
                faction_id=entry.get("faction_id", ""),
                delta=entry.get("delta", 0.0),
                new_score=entry.get("new_score", 0.0),
                reason=entry.get("reason", ""),
                game_time=entry.get("game_time", 0.0),
                is_ripple=entry.get("is_ripple", False),
            ))

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "faction_count": len(self._factions),
            "reputations": dict(self._player_reputation),
            "history_length": len(self._reputation_history),
            "milestones_crossed": {
                fid: len(thresholds)
                for fid, thresholds in self._crossed_milestones.items()
            },
        }
