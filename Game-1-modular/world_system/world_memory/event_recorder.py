"""Event Recorder — subscribes to GameEventBus, converts events to
WorldMemoryEvents, enriches with geographic context, and writes to SQLite.

This is the bridge between Layer 0 (ephemeral bus) and Layer 2 (persistent SQLite).
It tracks occurrence counts and triggers the Interpreter via the TriggerManager
when counts hit threshold milestones (1, 3, 5, 10, 25, 50, 100, ...).

Design authority: WORLD_MEMORY_SYSTEM.md §5 (Event Schema & Recording Pipeline)
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set, Tuple

from world_system.world_memory.event_schema import (
    BUS_TO_MEMORY_TYPE, SKIP_BUS_EVENTS, EventType, WorldMemoryEvent,
)
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry
from world_system.world_memory.trigger_manager import TriggerManager


# ── Intensity tag baselines (Design Doc §9.2) ──────────────────────

_TIER_BASELINES = {1: 10, 2: 25, 3: 60, 4: 150}


class EventRecorder:
    """Subscribes to GameEventBus, records events to SQLite.

    Enriches each event with geographic context and occurrence counts.
    Uses TriggerManager (threshold sequence + dual-track) to decide
    when to notify the Interpreter.
    """

    _instance: ClassVar[Optional[EventRecorder]] = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.trigger_manager: Optional[TriggerManager] = None
        self.session_id: str = ""
        self._game_time: float = 0.0

        # Interpreter callback — set by WorldInterpreter.initialize()
        self._interpreter_callback: Optional[Callable] = None

        # Stats
        self.events_recorded: int = 0
        self.events_skipped: int = 0
        self._connected: bool = False

    @classmethod
    def get_instance(cls) -> EventRecorder:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, event_store: EventStore,
                   geo_registry: GeographicRegistry,
                   entity_registry: EntityRegistry,
                   trigger_manager: Optional[TriggerManager] = None,
                   session_id: str = "") -> None:
        """Wire up dependencies and subscribe to the event bus."""
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.trigger_manager = trigger_manager or TriggerManager.get_instance()
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._connect_bus()

    def set_interpreter_callback(self, callback: Callable) -> None:
        """Register the interpreter's trigger callback."""
        self._interpreter_callback = callback

    def set_game_time(self, game_time: float) -> None:
        """Update current game time (called from game loop)."""
        self._game_time = game_time

    def _connect_bus(self) -> None:
        """Subscribe to all GameEventBus events."""
        if self._connected:
            return
        try:
            from events.event_bus import get_event_bus
            bus = get_event_bus()
            bus.subscribe("*", self._on_bus_event, priority=-10)
            self._connected = True
        except ImportError:
            print("[EventRecorder] Could not import event_bus — running without bus")

    def disconnect(self) -> None:
        """Unsubscribe from the bus."""
        if not self._connected:
            return
        try:
            from events.event_bus import get_event_bus
            bus = get_event_bus()
            bus.unsubscribe("*", self._on_bus_event)
            self._connected = False
        except ImportError:
            pass

    # ── Event processing ─────────────────────────────────────────────

    def _on_bus_event(self, event) -> None:
        """Handle a GameEventBus event: filter, convert, enrich, record."""
        if not self.event_store:
            return

        # Filter visual-only and noise events
        if event.event_type in SKIP_BUS_EVENTS:
            self.events_skipped += 1
            return

        # Check if we know how to map this bus event
        mem_type = BUS_TO_MEMORY_TYPE.get(event.event_type)
        if mem_type is None:
            self.events_skipped += 1
            return

        # Convert to WorldMemoryEvent (Phase 1 tags built here)
        memory_event = self._convert_event(event, mem_type)
        if memory_event is None:
            self.events_skipped += 1
            return

        # Enrich with geographic context
        self._enrich_geographic(memory_event)

        # Phase 2 tags: location, species, intensity (depend on enrichment)
        self._add_derived_tags(memory_event)

        # Update occurrence count
        count = self.event_store.increment_occurrence(
            memory_event.actor_id,
            memory_event.event_type,
            memory_event.event_subtype,
        )
        memory_event.interpretation_count = count

        # Check threshold triggers (dual-track)
        actions = self.trigger_manager.on_event(memory_event)
        memory_event.triggered_interpretation = len(actions) > 0

        # Write to SQLite
        self.event_store.record(memory_event)
        self.events_recorded += 1

        # Update entity activity logs
        self._update_activity_logs(memory_event)

        # Notify interpreter for each trigger action
        if self._interpreter_callback:
            for action in actions:
                try:
                    self._interpreter_callback(action)
                except Exception as e:
                    print(f"[EventRecorder] Interpreter error: {e}")

    def _convert_event(self, event, mem_type: EventType) -> Optional[WorldMemoryEvent]:
        """Convert a GameEvent to a WorldMemoryEvent."""
        data = event.data or {}

        # Extract position
        pos_x = data.get("position_x", data.get("player_x", 0.0))
        pos_y = data.get("position_y", data.get("player_y", 0.0))

        # Extract actor/target
        actor_id = data.get("actor_id", data.get("attacker_id",
                   data.get("killer_id", data.get("entity_id", "player"))))
        actor_type = data.get("actor_type", "player")
        target_id = data.get("target_id", data.get("enemy_id",
                   data.get("npc_id", data.get("resource_id", None))))
        target_type = data.get("target_type", None)

        # Derive subtype
        subtype = self._derive_subtype(event, mem_type)

        # Build Phase 1 tags (from bus event data directly)
        tags = self._build_event_tags(event, mem_type)

        # Extract magnitude
        magnitude = data.get("amount", data.get("quantity",
                   data.get("value", data.get("experience", 0.0))))
        if isinstance(magnitude, (list, dict)):
            magnitude = 0.0

        return WorldMemoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=mem_type.value,
            event_subtype=subtype,
            actor_id=str(actor_id),
            actor_type=str(actor_type),
            target_id=str(target_id) if target_id else None,
            target_type=str(target_type) if target_type else None,
            position_x=float(pos_x),
            position_y=float(pos_y),
            chunk_x=0, chunk_y=0,  # Filled by _enrich_geographic
            game_time=self._game_time,
            real_time=event.timestamp if hasattr(event, "timestamp") else time.time(),
            session_id=self.session_id,
            magnitude=float(magnitude),
            result=data.get("result", data.get("outcome", "success")),
            quality=data.get("quality"),
            tier=data.get("tier"),
            tags=tags,
            context=self._extract_context(event),
        )

    def _derive_subtype(self, event, mem_type: EventType) -> str:
        """Derive a specific subtype from event data."""
        data = event.data or {}

        if mem_type == EventType.ENEMY_KILLED:
            enemy_id = data.get("enemy_id", "unknown")
            # Strip instance suffix to get enemy type (e.g., "wolf_3" → "wolf")
            base = str(enemy_id).rstrip("0123456789").rstrip("_")
            return f"killed_{base}" if base else "killed_unknown"

        if mem_type == EventType.ATTACK_PERFORMED:
            dmg_type = data.get("damage_type", "physical")
            return f"dealt_{dmg_type}"

        if mem_type == EventType.DAMAGE_TAKEN:
            dmg_type = data.get("damage_type", "physical")
            return f"took_{dmg_type}"

        if mem_type == EventType.RESOURCE_GATHERED:
            res_id = data.get("resource_id", data.get("material_id", "unknown"))
            return f"gathered_{res_id}"

        if mem_type == EventType.CRAFT_ATTEMPTED:
            recipe_id = data.get("recipe_id", "unknown")
            return f"crafted_{recipe_id}"

        if mem_type == EventType.SKILL_USED:
            skill_id = data.get("skill_id", "unknown")
            return f"used_{skill_id}"

        if mem_type == EventType.LEVEL_UP:
            new_level = data.get("new_level", 0)
            return f"reached_level_{new_level}"

        if mem_type == EventType.NPC_INTERACTION:
            npc_id = data.get("npc_id", "unknown")
            return f"talked_to_{npc_id}"

        if mem_type == EventType.QUEST_ACCEPTED:
            return f"accepted_{data.get('quest_id', 'unknown')}"

        if mem_type == EventType.QUEST_COMPLETED:
            return f"completed_{data.get('quest_id', 'unknown')}"

        return mem_type.value

    def _build_event_tags(self, event, mem_type: EventType) -> List[str]:
        """Phase 1 tags: generated from bus event data fields (Design Doc §9.2)."""
        tags = [f"event:{mem_type.value}"]
        data = event.data or {}

        # Resource tags
        for key in ("resource_type", "material_id", "resource_id"):
            if key in data:
                tags.append(f"resource:{data[key]}")

        # Enemy / species tags
        for key in ("enemy_type", "enemy_id"):
            if key in data and data[key]:
                base = str(data[key]).rstrip("0123456789").rstrip("_")
                if base:
                    tags.append(f"species:{base}")
                break  # Only add one species tag

        # Combat tags
        if "damage_type" in data:
            tags.append(f"element:{data['damage_type']}")
        if "weapon_type" in data:
            tags.append(f"combat:{data['weapon_type']}")
        if data.get("is_crit"):
            tags.append("combat:critical")
        if data.get("is_boss"):
            tags.append("combat:boss")

        # Tier tags
        if "tier" in data and data["tier"] is not None:
            tags.append(f"tier:{data['tier']}")

        # Biome tags
        if "biome" in data:
            tags.append(f"biome:{data['biome']}")

        # Discipline tags
        if "discipline" in data:
            tags.append(f"domain:{data['discipline']}")

        # Quality tags
        if "quality" in data:
            tags.append(f"quality:{data['quality']}")

        # NPC tags
        if "npc_id" in data and data["npc_id"]:
            tags.append(f"npc:{data['npc_id']}")

        # Quest tags
        if "quest_id" in data and data["quest_id"]:
            tags.append(f"quest:{data['quest_id']}")

        # Skill tags (from game tag system)
        if "tags" in data and isinstance(data["tags"], list):
            for tag in data["tags"]:
                if ":" not in tag:
                    tags.append(f"game:{tag}")
                else:
                    tags.append(tag)

        return tags

    def _add_derived_tags(self, event: WorldMemoryEvent) -> None:
        """Phase 2 tags: depend on geographic enrichment and computed values.

        Called AFTER _enrich_geographic() so locality/district are available.
        Design Doc §9.2: location tags, intensity tags.
        """
        # Location tags
        if event.locality_id:
            event.tags.append(f"location:{event.locality_id}")
        if event.district_id:
            event.tags.append(f"location:{event.district_id}")

        # Intensity tags (magnitude relative to tier baseline)
        if event.magnitude > 0:
            baseline = _TIER_BASELINES.get(event.tier or 1, 10)
            ratio = event.magnitude / baseline
            if ratio > 3.0:
                event.tags.append("intensity:extreme")
            elif ratio > 1.5:
                event.tags.append("intensity:heavy")
            elif ratio > 0.5:
                event.tags.append("intensity:moderate")
            else:
                event.tags.append("intensity:light")

    def _extract_context(self, event) -> Dict[str, Any]:
        """Extract context snapshot from event data."""
        data = event.data or {}
        # Include all non-standard fields as context
        standard_keys = {
            "position_x", "position_y", "player_x", "player_y",
            "actor_id", "attacker_id", "killer_id", "entity_id",
            "target_id", "enemy_id", "npc_id", "resource_id",
            "actor_type", "target_type",
            "amount", "quantity", "value", "experience",
            "result", "outcome", "quality", "tier",
        }
        context = {}
        for key, val in data.items():
            if key not in standard_keys:
                # Ensure JSON-serializable
                if isinstance(val, (str, int, float, bool, type(None))):
                    context[key] = val
                elif isinstance(val, (list, dict)):
                    context[key] = val
        return context

    def _enrich_geographic(self, event: WorldMemoryEvent) -> None:
        """Stamp chunk coordinates and geographic region IDs onto the event."""
        event.chunk_x = int(event.position_x) // 16
        event.chunk_y = int(event.position_y) // 16

        if self.geo_registry:
            address = self.geo_registry.get_full_address(
                event.position_x, event.position_y
            )
            event.locality_id = address.get("locality")
            event.district_id = address.get("district")
            event.province_id = address.get("province")

            # Add biome from region if available
            if event.locality_id:
                region = self.geo_registry.regions.get(event.locality_id)
                if region and region.biome_primary:
                    event.biome = region.biome_primary

    def _update_activity_logs(self, event: WorldMemoryEvent) -> None:
        """Append event to relevant entity activity logs."""
        if not self.entity_registry:
            return

        # Actor's log
        actor = self.entity_registry.get(event.actor_id)
        if actor:
            actor.add_activity(event.event_id)

        # Target's log
        if event.target_id:
            target = self.entity_registry.get(event.target_id)
            if target:
                target.add_activity(event.event_id)

        # Region's log
        if event.locality_id:
            region_entity = self.entity_registry.get(f"region_{event.locality_id}")
            if region_entity:
                region_entity.add_activity(event.event_id)

    # ── Manual event recording (for game code that publishes directly) ──

    def record_direct(self, event_type: str, event_subtype: str,
                      actor_id: str = "player", actor_type: str = "player",
                      position_x: float = 0.0, position_y: float = 0.0,
                      target_id: Optional[str] = None,
                      magnitude: float = 0.0,
                      tags: Optional[List[str]] = None,
                      context: Optional[Dict[str, Any]] = None,
                      locality_id: Optional[str] = None) -> Optional[WorldMemoryEvent]:
        """Record an event directly (bypass bus). For testing or direct integration."""
        if not self.event_store:
            return None

        event = WorldMemoryEvent.create(
            event_type=event_type,
            event_subtype=event_subtype,
            actor_id=actor_id,
            actor_type=actor_type,
            position_x=position_x,
            position_y=position_y,
            target_id=target_id,
            magnitude=magnitude,
            tags=tags or [],
            context=context or {},
            game_time=self._game_time,
            session_id=self.session_id,
        )
        self._enrich_geographic(event)
        # Allow explicit locality override (useful for testing without geo registry)
        if locality_id and not event.locality_id:
            event.locality_id = locality_id
        self._add_derived_tags(event)

        count = self.event_store.increment_occurrence(
            actor_id, event_type, event_subtype
        )
        event.interpretation_count = count

        # Check threshold triggers (dual-track)
        actions = self.trigger_manager.on_event(event)
        event.triggered_interpretation = len(actions) > 0

        self.event_store.record(event)
        self.events_recorded += 1
        self._update_activity_logs(event)

        if self._interpreter_callback:
            for action in actions:
                try:
                    self._interpreter_callback(action)
                except Exception as e:
                    print(f"[EventRecorder] Interpreter error: {e}")

        return event

    # ── Debug ────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "events_recorded": self.events_recorded,
            "events_skipped": self.events_skipped,
            "connected": self._connected,
            "session_id": self.session_id,
            "total_in_store": self.event_store.get_event_count() if self.event_store else 0,
        }
