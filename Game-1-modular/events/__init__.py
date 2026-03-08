"""Game event bus — pub/sub system for decoupled inter-system communication."""
from events.event_bus import GameEventBus, GameEvent, get_event_bus

__all__ = ['GameEventBus', 'GameEvent', 'get_event_bus']
