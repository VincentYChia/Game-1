"""
Attack state machine for phased combat.

Manages the IDLE -> WINDUP -> ACTIVE -> RECOVERY -> COOLDOWN cycle
for both player and enemy attacks. Does NOT calculate damage —
it only controls timing and emits events at phase transitions.

The damage pipeline (CombatManager.player_attack_enemy_with_tags,
CombatManager._enemy_attack_player) runs unchanged when triggered
by hit events from the hitbox system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Set, Dict, Any

from combat.combat_event import CombatEvent


class AttackPhase(Enum):
    IDLE = "idle"
    WINDUP = "windup"
    ACTIVE = "active"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"


@dataclass
class AttackDefinition:
    """Defines one attack type. Loaded from JSON via CombatDataLoader."""

    attack_id: str
    windup_ms: float
    active_ms: float
    recovery_ms: float
    cooldown_ms: float

    # Hitbox configuration
    hitbox_shape: str = "arc"             # "circle", "arc", "rect", "line"
    hitbox_params: Dict[str, Any] = field(default_factory=dict)

    # Combat modifiers
    damage_multiplier: float = 1.0
    movement_multiplier: float = 0.7      # Speed reduction during attack (1.0 = full speed)
    can_be_interrupted: bool = True

    # Animation
    animation_id: str = "swing_medium"

    # Projectile (if set, spawns projectile instead of melee hitbox)
    projectile_id: Optional[str] = None

    # Status tags to apply on hit
    status_tags: List[str] = field(default_factory=list)

    # Screen effects
    screen_shake: bool = False
    telegraph_color: List[int] = field(default_factory=lambda: [255, 100, 100])

    # Combo chain
    combo_next: Optional[str] = None
    combo_window_ms: float = 0.0

    def __post_init__(self):
        if self.hitbox_params is None:
            self.hitbox_params = {}
        if self.status_tags is None:
            self.status_tags = []
        if self.telegraph_color is None:
            self.telegraph_color = [255, 100, 100]

    @property
    def total_duration_ms(self) -> float:
        return self.windup_ms + self.active_ms + self.recovery_ms + self.cooldown_ms

    @property
    def hitbox_radius(self) -> float:
        return self.hitbox_params.get('radius', 1.5)

    @property
    def hitbox_arc_degrees(self) -> float:
        return self.hitbox_params.get('arc_degrees', 90.0)

    @property
    def hitbox_offset_forward(self) -> float:
        return self.hitbox_params.get('offset_forward', 0.8)


class AttackStateMachine:
    """Manages the attack phase cycle for one entity.

    Each entity (player, each enemy) gets its own instance.
    """

    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.phase: AttackPhase = AttackPhase.IDLE
        self.phase_timer: float = 0.0
        self.current_attack: Optional[AttackDefinition] = None
        self.hits_this_swing: Set[str] = set()
        self.combo_count: int = 0
        self.combo_timer: float = 0.0
        self.damage_context: Dict[str, Any] = {}

    def start_attack(self, attack_def: AttackDefinition,
                     damage_context: Dict[str, Any]) -> bool:
        """Begin attack if able.

        Can start from IDLE, or from COOLDOWN if within combo window.
        Returns False if the attack can't start right now.
        """
        if self.phase == AttackPhase.IDLE:
            pass  # Can always start from idle
        elif self.phase == AttackPhase.COOLDOWN and self.combo_timer > 0:
            # Combo input accepted during cooldown
            self.combo_count += 1
        else:
            return False

        self.current_attack = attack_def
        self.damage_context = damage_context
        self.phase = AttackPhase.WINDUP
        self.phase_timer = attack_def.windup_ms
        self.hits_this_swing.clear()
        return True

    def update(self, dt_ms: float) -> List[CombatEvent]:
        """Advance the state machine. Returns events that occurred this frame."""
        events = []

        if self.phase == AttackPhase.IDLE:
            # Decay combo timer
            if self.combo_timer > 0:
                self.combo_timer -= dt_ms
                if self.combo_timer <= 0:
                    self.combo_count = 0
                    self.combo_timer = 0
            return events

        self.phase_timer -= dt_ms

        if self.phase_timer <= 0:
            if self.phase == AttackPhase.WINDUP:
                self.phase = AttackPhase.ACTIVE
                self.phase_timer = self.current_attack.active_ms
                self.hits_this_swing.clear()
                events.append(CombatEvent(
                    "phase_change", self.entity_id,
                    data={"phase": "active", "attack": self.current_attack}
                ))

            elif self.phase == AttackPhase.ACTIVE:
                self.phase = AttackPhase.RECOVERY
                self.phase_timer = self.current_attack.recovery_ms
                events.append(CombatEvent(
                    "phase_change", self.entity_id,
                    data={"phase": "recovery"}
                ))

            elif self.phase == AttackPhase.RECOVERY:
                self.phase = AttackPhase.COOLDOWN
                self.phase_timer = self.current_attack.cooldown_ms
                # Start combo window
                if self.current_attack.combo_next:
                    self.combo_timer = self.current_attack.combo_window_ms
                events.append(CombatEvent(
                    "phase_change", self.entity_id,
                    data={"phase": "cooldown"}
                ))

            elif self.phase == AttackPhase.COOLDOWN:
                self.phase = AttackPhase.IDLE
                self.current_attack = None
                self.damage_context = {}
                events.append(CombatEvent(
                    "phase_change", self.entity_id,
                    data={"phase": "idle"}
                ))

        return events

    def interrupt(self) -> bool:
        """Cancel during WINDUP (e.g., entity got stunned)."""
        if self.phase == AttackPhase.WINDUP and self.current_attack \
                and self.current_attack.can_be_interrupted:
            self.phase = AttackPhase.IDLE
            self.phase_timer = 0
            self.current_attack = None
            self.damage_context = {}
            return True
        return False

    def force_reset(self) -> None:
        """Force back to IDLE (used on death, load, etc.)."""
        self.phase = AttackPhase.IDLE
        self.phase_timer = 0
        self.current_attack = None
        self.damage_context = {}
        self.hits_this_swing.clear()
        self.combo_count = 0
        self.combo_timer = 0

    def record_hit(self, target_id: str) -> bool:
        """Record that we hit this target. Returns False if already hit (prevents multi-hit)."""
        if target_id in self.hits_this_swing:
            return False
        self.hits_this_swing.add(target_id)
        return True

    # --- Properties ---

    @property
    def is_in_active_phase(self) -> bool:
        return self.phase == AttackPhase.ACTIVE

    @property
    def is_attacking(self) -> bool:
        return self.phase != AttackPhase.IDLE

    @property
    def is_in_windup(self) -> bool:
        return self.phase == AttackPhase.WINDUP

    @property
    def is_vulnerable(self) -> bool:
        """True during RECOVERY — potential counter-attack window."""
        return self.phase == AttackPhase.RECOVERY

    @property
    def movement_multiplier(self) -> float:
        if self.current_attack and self.phase in (
                AttackPhase.WINDUP, AttackPhase.ACTIVE, AttackPhase.RECOVERY):
            return self.current_attack.movement_multiplier
        return 1.0

    @property
    def windup_progress(self) -> float:
        """Progress through windup from 0.0 to 1.0. Returns 0 if not in windup."""
        if self.phase != AttackPhase.WINDUP or not self.current_attack:
            return 0.0
        elapsed = self.current_attack.windup_ms - self.phase_timer
        return min(1.0, elapsed / max(1.0, self.current_attack.windup_ms))
