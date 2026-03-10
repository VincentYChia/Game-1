"""VisualEffectBridge — event-driven connector between combat events and visual systems.

Subscribes to GameEventBus events (DAMAGE_DEALT, ENEMY_KILLED, PLAYER_HIT,
DODGE_PERFORMED, ATTACK_STARTED, ATTACK_PHASE) and dispatches appropriate
visual responses (damage numbers, death effects, screen shake, particles).

This replaces scattered direct calls with a single subscriber that coordinates
all visual feedback. Other systems (AI, sound, analytics) can also subscribe
to the same events independently.

Usage:
    bridge = VisualEffectBridge(damage_mgr, death_mgr, screen_effects, particles)
    bridge.connect()  # Subscribes to EventBus
    # ... events flow automatically ...
    bridge.disconnect()  # Unsubscribes (cleanup)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from events.event_bus import GameEvent, get_event_bus

if TYPE_CHECKING:
    from rendering.visual_effects import DamageNumberManager, EnemyDeathManager


# Tier -> screen shake intensity on kill
_KILL_SHAKE = {1: 2, 2: 3, 3: 5, 4: 8}

# Tier -> death effect color
_TIER_COLORS = {
    1: (200, 100, 100),
    2: (255, 150, 0),
    3: (200, 100, 255),
    4: (255, 50, 50),
}


class VisualEffectBridge:
    """Subscribes to combat events and triggers visual effects.

    All visual managers are optional — if None, that effect category is skipped.
    This ensures graceful degradation if any visual system fails to load.
    """

    def __init__(
        self,
        damage_number_manager: Optional[DamageNumberManager] = None,
        death_effect_manager: Optional[EnemyDeathManager] = None,
        screen_effects=None,
        combat_particles=None,
    ):
        self._damage_mgr = damage_number_manager
        self._death_mgr = death_effect_manager
        self._screen_fx = screen_effects
        self._particles = combat_particles
        self._connected = False

    def connect(self) -> None:
        """Subscribe to all relevant EventBus events."""
        if self._connected:
            return
        bus = get_event_bus()
        bus.subscribe("DAMAGE_DEALT", self._on_damage_dealt, priority=10)
        bus.subscribe("ENEMY_KILLED", self._on_enemy_killed, priority=10)
        bus.subscribe("PLAYER_HIT", self._on_player_hit, priority=10)
        bus.subscribe("DODGE_PERFORMED", self._on_dodge, priority=10)
        bus.subscribe("SCREEN_SHAKE", self._on_screen_shake, priority=10)
        bus.subscribe("PARTICLE_BURST", self._on_particle_burst, priority=10)
        self._connected = True

    def disconnect(self) -> None:
        """Unsubscribe from all events."""
        if not self._connected:
            return
        bus = get_event_bus()
        bus.unsubscribe("DAMAGE_DEALT", self._on_damage_dealt)
        bus.unsubscribe("ENEMY_KILLED", self._on_enemy_killed)
        bus.unsubscribe("PLAYER_HIT", self._on_player_hit)
        bus.unsubscribe("DODGE_PERFORMED", self._on_dodge)
        bus.unsubscribe("SCREEN_SHAKE", self._on_screen_shake)
        bus.unsubscribe("PARTICLE_BURST", self._on_particle_burst)
        self._connected = False

    # --- Event Handlers ---

    def _on_damage_dealt(self, event: GameEvent) -> None:
        """Spawn damage number + hit sparks for any damage event."""
        d = event.data
        amount = d.get("amount", 0)
        if amount <= 0:
            return

        x = d.get("position_x", 0.0)
        y = d.get("position_y", 0.0)
        is_crit = d.get("is_crit", False)
        damage_type = d.get("damage_type", "physical")

        # Damage number
        if self._damage_mgr:
            self._damage_mgr.spawn(
                int(amount), x, y,
                is_crit=is_crit, damage_type=damage_type)

        # Hit sparks
        if self._particles and hasattr(self._particles, 'emit_hit_sparks'):
            intensity = min(amount / 50.0, 3.0)
            self._particles.emit_hit_sparks(x, y, damage_type, intensity)

        # Crit hit pause
        if is_crit and self._screen_fx and hasattr(self._screen_fx, 'hit_pause'):
            self._screen_fx.hit_pause(40)

    def _on_enemy_killed(self, event: GameEvent) -> None:
        """Death effect + screen shake on enemy kill."""
        d = event.data
        x = d.get("position_x", 0.0)
        y = d.get("position_y", 0.0)
        tier = d.get("tier", 1)
        visual_size = d.get("visual_size", 1.0)
        color = _TIER_COLORS.get(tier, (200, 100, 100))

        # Spawn death effect
        if self._death_mgr:
            self._death_mgr.spawn(x, y, visual_size, tier, color)

        # Screen shake scales with tier
        shake_intensity = _KILL_SHAKE.get(tier, 2)
        if self._screen_fx and hasattr(self._screen_fx, 'screen_shake'):
            self._screen_fx.screen_shake(shake_intensity, 150)

        # Hit pause for dramatic effect
        if self._screen_fx and hasattr(self._screen_fx, 'hit_pause'):
            self._screen_fx.hit_pause(60)

        # Death burst particles
        if self._particles and hasattr(self._particles, 'emit_death_burst'):
            self._particles.emit_death_burst(x, y, tier, color)

    def _on_player_hit(self, event: GameEvent) -> None:
        """Screen shake + flash when player takes damage."""
        d = event.data
        amount = d.get("amount", 0)
        damage_type = d.get("damage_type", "physical")

        # Spawn damage number on player
        if self._damage_mgr and amount > 0:
            px = d.get("player_x", 0.0)
            py = d.get("player_y", 0.0)
            self._damage_mgr.spawn(
                int(amount), px, py,
                damage_type=damage_type)

        # Screen shake proportional to damage
        if self._screen_fx and hasattr(self._screen_fx, 'screen_shake'):
            intensity = min(int(amount / 10) + 1, 8)
            self._screen_fx.screen_shake(intensity, 100)

    def _on_dodge(self, event: GameEvent) -> None:
        """Spawn dodge dust particles."""
        d = event.data
        x = d.get("position_x", 0.0)
        y = d.get("position_y", 0.0)
        direction = d.get("direction", (0.0, 0.0))

        if self._particles and hasattr(self._particles, 'emit_dodge_dust'):
            self._particles.emit_dodge_dust(x, y, direction)

    def _on_screen_shake(self, event: GameEvent) -> None:
        """Direct screen shake request from any system."""
        d = event.data
        if self._screen_fx and hasattr(self._screen_fx, 'screen_shake'):
            self._screen_fx.screen_shake(
                d.get("intensity", 3),
                d.get("duration_ms", 100))

    def _on_particle_burst(self, event: GameEvent) -> None:
        """Generic particle burst at a position."""
        d = event.data
        x = d.get("position_x", 0.0)
        y = d.get("position_y", 0.0)
        particle_type = d.get("particle_type", "generic")
        count = d.get("count", 8)

        if self._particles and hasattr(self._particles, 'emit_burst'):
            self._particles.emit_burst(x, y, particle_type, count)


# --- Event Publishing Helpers ---
# These are called from game_engine.py / combat_manager.py at key moments.

def publish_damage_dealt(
    target_id: str, attacker_id: str, amount: float,
    damage_type: str = "physical", is_crit: bool = False,
    position_x: float = 0.0, position_y: float = 0.0,
    source: str = "combat"
) -> None:
    """Publish a DAMAGE_DEALT event."""
    get_event_bus().publish("DAMAGE_DEALT", {
        "target_id": target_id,
        "attacker_id": attacker_id,
        "amount": amount,
        "damage_type": damage_type,
        "is_crit": is_crit,
        "position_x": position_x,
        "position_y": position_y,
    }, source=source)


def publish_enemy_killed(
    enemy_id: str, killer_id: str,
    position_x: float, position_y: float,
    tier: int = 1, visual_size: float = 1.0,
    is_boss: bool = False, loot: list = None,
    source: str = "combat"
) -> None:
    """Publish an ENEMY_KILLED event."""
    get_event_bus().publish("ENEMY_KILLED", {
        "enemy_id": enemy_id,
        "killer_id": killer_id,
        "position_x": position_x,
        "position_y": position_y,
        "tier": tier,
        "visual_size": visual_size,
        "is_boss": is_boss,
        "loot": loot or [],
    }, source=source)


def publish_player_hit(
    attacker_id: str, amount: float,
    damage_type: str = "physical",
    player_x: float = 0.0, player_y: float = 0.0,
    source: str = "combat"
) -> None:
    """Publish a PLAYER_HIT event."""
    get_event_bus().publish("PLAYER_HIT", {
        "attacker_id": attacker_id,
        "amount": amount,
        "damage_type": damage_type,
        "player_x": player_x,
        "player_y": player_y,
    }, source=source)


def publish_dodge_performed(
    position_x: float, position_y: float,
    direction: tuple = (0.0, 0.0),
    source: str = "player"
) -> None:
    """Publish a DODGE_PERFORMED event."""
    get_event_bus().publish("DODGE_PERFORMED", {
        "position_x": position_x,
        "position_y": position_y,
        "direction": direction,
    }, source=source)


def publish_attack_started(
    entity_id: str, attack_id: str,
    weapon_type: str = "", tags: list = None,
    source: str = "combat"
) -> None:
    """Publish an ATTACK_STARTED event."""
    get_event_bus().publish("ATTACK_STARTED", {
        "entity_id": entity_id,
        "attack_id": attack_id,
        "weapon_type": weapon_type,
        "tags": tags or [],
    }, source=source)
