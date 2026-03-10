"""GameEventBus — lightweight pub/sub for decoupled inter-system communication.

All new visual, animation, and AI systems communicate through events rather than
direct imports. Existing systems publish events at key moments; new systems
subscribe to react visually or logically.

Usage:
    bus = get_event_bus()
    bus.subscribe("DAMAGE_DEALT", my_handler)
    bus.publish("DAMAGE_DEALT", {"target_id": "enemy_3", "amount": 50, "type": "fire"})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import time


@dataclass
class GameEvent:
    """Immutable event payload passed through the bus."""
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # System that published (for debugging)


# Type alias for subscriber callbacks
EventHandler = Callable[[GameEvent], None]


class GameEventBus:
    """Singleton event bus supporting typed pub/sub with optional priority ordering.

    Follows the project's singleton pattern (get_instance / get_event_bus).

    Event types are strings by convention — no enum required. Standard events:

    Combat:
        DAMAGE_DEALT      - {attacker_id, target_id, amount, damage_type, is_crit}
        ENEMY_KILLED      - {enemy_id, killer_id, position, tier, loot}
        PLAYER_HIT        - {attacker_id, amount, damage_type}
        PLAYER_DIED       - {position, killer_id}
        ATTACK_STARTED    - {entity_id, attack_id, phase, weapon_type}
        ATTACK_PHASE      - {entity_id, phase, progress}

    Skills:
        SKILL_ACTIVATED   - {skill_id, caster_id, tags, position}
        STATUS_APPLIED    - {target_id, status_type, duration}
        STATUS_EXPIRED    - {target_id, status_type}

    World:
        RESOURCE_GATHERED - {resource_id, position, tool_used}
        ITEM_CRAFTED      - {recipe_id, quality, discipline}
        CHEST_OPENED      - {chest_id, position}
        ENTITY_SPAWNED    - {entity_id, entity_type, position}

    Player:
        DODGE_PERFORMED   - {direction, position}
        LEVEL_UP          - {new_level, stat_points}
        EQUIPMENT_CHANGED - {slot, old_item, new_item}

    Visual:
        SCREEN_SHAKE      - {intensity, duration_ms}
        PARTICLE_BURST    - {position, particle_type, count}
        FLASH_ENTITY      - {entity_id, color, duration_ms}
    """

    _instance: Optional[GameEventBus] = None

    def __init__(self):
        # event_type -> list of (priority, handler)
        self._subscribers: Dict[str, List[tuple]] = {}
        # Wildcard subscribers that receive ALL events
        self._global_subscribers: List[tuple] = []
        self._muted: bool = False
        # Simple stats for debugging
        self._publish_count: int = 0
        self._handler_errors: int = 0

    @classmethod
    def get_instance(cls) -> GameEventBus:
        """Get or create the singleton event bus."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def subscribe(self, event_type: str, handler: EventHandler,
                  priority: int = 0) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event type string (e.g. "DAMAGE_DEALT").
                       Use "*" to subscribe to all events.
            handler: Callable that receives a GameEvent.
            priority: Lower values run first. Default 0.
        """
        if event_type == "*":
            self._global_subscribers.append((priority, handler))
            self._global_subscribers.sort(key=lambda x: x[0])
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append((priority, handler))
            self._subscribers[event_type].sort(key=lambda x: x[0])

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        if event_type == "*":
            self._global_subscribers = [
                (p, h) for p, h in self._global_subscribers if h is not handler
            ]
        elif event_type in self._subscribers:
            self._subscribers[event_type] = [
                (p, h) for p, h in self._subscribers[event_type] if h is not handler
            ]

    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                source: str = "") -> GameEvent:
        """Publish an event to all subscribers.

        Args:
            event_type: Event type string.
            data: Event payload dict.
            source: Publishing system name (for debug logging).

        Returns:
            The GameEvent that was published.
        """
        if self._muted:
            return GameEvent(event_type=event_type, data=data or {}, source=source)

        event = GameEvent(
            event_type=event_type,
            data=data or {},
            source=source,
        )

        self._publish_count += 1

        # Notify type-specific subscribers
        handlers = self._subscribers.get(event_type, [])
        for _, handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._handler_errors += 1
                print(f"[EventBus] Error in handler for {event_type}: {e}")

        # Notify global subscribers
        for _, handler in self._global_subscribers:
            try:
                handler(event)
            except Exception as e:
                self._handler_errors += 1
                print(f"[EventBus] Error in global handler for {event_type}: {e}")

        return event

    def mute(self) -> None:
        """Suppress all event delivery (for batch operations)."""
        self._muted = True

    def unmute(self) -> None:
        """Resume event delivery."""
        self._muted = False

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()
        self._global_subscribers.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        """Debug statistics."""
        return {
            "total_published": self._publish_count,
            "handler_errors": self._handler_errors,
            "subscriber_count": sum(
                len(v) for v in self._subscribers.values()
            ) + len(self._global_subscribers),
            "event_types": list(self._subscribers.keys()),
        }


def get_event_bus() -> GameEventBus:
    """Module-level accessor following project singleton pattern."""
    return GameEventBus.get_instance()
