"""
Training Dummy System for Tag Testing
Creates a special enemy that provides detailed feedback on effects applied
"""

from typing import Tuple
from Combat.enemy import Enemy, EnemyDefinition, AIPattern, DropDefinition
from entities.status_manager import add_status_manager_to_entity


def create_training_dummy_definition() -> EnemyDefinition:
    """Create EnemyDefinition for training dummy"""
    return EnemyDefinition(
        enemy_id="training_dummy",
        name="Training Dummy",
        tier=1,
        category="construct",  # Immune to poison, bleed
        behavior="idle",  # Doesn't move or attack
        max_health=10000.0,  # Very high HP
        damage_min=0,  # Doesn't attack
        damage_max=0,
        defense=0,  # No defense for clear damage numbers
        speed=0.0,  # Doesn't move
        aggro_range=0.0,  # Doesn't aggro
        attack_speed=0.0,  # Never attacks
        drops=[],  # No drops
        ai_pattern=AIPattern(
            default_state="idle",
            aggro_on_damage=False,  # Doesn't react
            aggro_on_proximity=False,
            flee_at_health=0.0,  # Never flees
            call_for_help_radius=0.0,
            pack_coordination=False
        ),
        special_abilities=[],  # No special attacks
        narrative="A stationary dummy for testing combat abilities. High HP, doesn't fight back. Perfect for testing tag combinations.",
        tags=["training", "dummy", "passive", "construct"]
    )


class TrainingDummy(Enemy):
    """
    Training dummy enemy with enhanced reporting

    Features:
    - High HP (10,000) - doesn't die easily
    - Stationary - doesn't move
    - Passive - doesn't attack back
    - Auto-resets at 10% health
    - Detailed damage reporting
    """

    def __init__(self, position: Tuple[float, float], chunk_coords: Tuple[int, int]):
        # Create training dummy definition
        definition = create_training_dummy_definition()

        # Initialize as Enemy
        super().__init__(definition, position, chunk_coords)

        # Override some Enemy behaviors
        self.is_alive = True
        self.ai_state_locked = True  # Prevent AI state changes

        # Enhanced tracking
        self.total_damage_taken = 0.0
        self.hit_count = 0
        self.reset_count = 0

    def take_damage(self, damage: float, damage_type: str = "physical", from_player: bool = False):
        """
        Take damage with detailed reporting

        Args:
            damage: Amount of damage
            damage_type: Type of damage
            from_player: Whether damage came from player
        """
        self.current_health -= damage
        self.total_damage_taken += damage
        self.hit_count += 1

        # Detailed console output
        print(f"\n🎯 TRAINING DUMMY HIT #{self.hit_count}")
        print(f"   Damage: {damage:.1f} {damage_type}")
        print(f"   HP: {self.current_health:.1f}/{self.max_health:.1f} ({self.current_health/self.max_health*100:.1f}%)")
        print(f"   Total damage taken: {self.total_damage_taken:.1f}")

        # Check active status effects
        if hasattr(self, 'status_manager') and len(self.status_manager.active_effects) > 0:
            print(f"   Active status effects:")
            for effect_name, effect in self.status_manager.active_effects.items():
                stacks = effect.get('stacks', 1)
                duration = effect.get('duration', 0)
                print(f"      - {effect_name} (x{stacks}, {duration:.1f}s remaining)")

        # Auto-reset at 10% health
        if self.current_health <= self.max_health * 0.1:
            self.reset_count += 1
            print(f"\n♻️  TRAINING DUMMY AUTO-RESET #{self.reset_count}")
            print(f"   Total hits taken: {self.hit_count}")
            print(f"   Total damage: {self.total_damage_taken:.1f}")

            # Reset health and tracking
            self.current_health = self.max_health
            self.total_damage_taken = 0.0
            self.hit_count = 0

            # Clear status effects
            if hasattr(self, 'status_manager'):
                self.status_manager.active_effects.clear()

            print(f"   HP restored to {self.max_health:.1f}")
            print(f"   Status effects cleared")

        # Training dummies never die
        return False  # Never returns True (never dies)

    def update_ai(self, dt: float, player_position: Tuple[float, float]):
        """Override AI - training dummy doesn't move or attack"""
        # Update status effects (burn, poison, etc. still tick)
        if hasattr(self, 'status_manager'):
            self.status_manager.update(dt)

        # Update ability cooldowns
        for ability_id in self.ability_cooldowns:
            if self.ability_cooldowns[ability_id] > 0:
                self.ability_cooldowns[ability_id] -= dt

        # Training dummy never moves or changes state
        pass

    def can_attack(self) -> bool:
        """Training dummy never attacks"""
        return False


def spawn_training_dummy(combat_manager, position: Tuple[float, float]) -> TrainingDummy:
    """
    Spawn a training dummy in the combat manager

    Args:
        combat_manager: CombatManager instance
        position: (x, y) position to spawn at

    Returns:
        TrainingDummy instance
    """
    # Calculate chunk coords
    chunk_x = int(position[0] // 16)
    chunk_y = int(position[1] // 16)
    chunk_coords = (chunk_x, chunk_y)

    # Create training dummy
    dummy = TrainingDummy(position, chunk_coords)

    # Add to combat manager's enemy list
    if chunk_coords not in combat_manager.enemies:
        combat_manager.enemies[chunk_coords] = []
    combat_manager.enemies[chunk_coords].append(dummy)

    print(f"🎯 Spawned Training Dummy at ({position[0]:.1f}, {position[1]:.1f})")
    print(f"   HP: {dummy.max_health:.0f}")
    print(f"   Click to attack, or use skills/turrets to test tag effects!")

    return dummy
