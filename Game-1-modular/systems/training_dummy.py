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

    def take_damage(self, damage: float, damage_type: str = "physical", from_player: bool = False,
                    source_tags: list = None, attacker_name: str = None, source=None, tags=None, **kwargs):
        """
        Take damage with detailed reporting

        Accepts parameters from both player attacks and effect_executor system.

        Args:
            damage: Amount of damage
            damage_type: Type of damage
            from_player: Whether damage came from player
            source_tags: Optional tags from attacking item/entity (player attacks)
            attacker_name: Optional name of attacker (player attacks)
            source: Source entity (effect_executor)
            tags: Tags from effect_executor system
            **kwargs: Additional damage metadata (crit, armor_pen, etc.)
        """
        # Normalize tags parameter (accept from either source_tags or tags)
        if tags and not source_tags:
            source_tags = tags
        if not source_tags:
            source_tags = []

        # Normalize attacker_name (try to get from source if not provided)
        if not attacker_name and source:
            if hasattr(source, 'item_id'):
                attacker_name = source.item_id
            elif hasattr(source, 'name'):
                attacker_name = source.name

        self.current_health -= damage
        self.total_damage_taken += damage
        self.hit_count += 1

        # Detailed console output
        print(f"\n🎯 TRAINING DUMMY HIT #{self.hit_count}")

        # Attacker info
        if attacker_name:
            print(f"   Attacker: {attacker_name}")
        elif from_player:
            print(f"   Attacker: Player")
        elif source:
            print(f"   Attacker: {type(source).__name__}")

        # Damage breakdown
        print(f"   Damage: {damage:.1f} ({damage_type})")

        # Additional damage metadata
        if kwargs.get('is_crit'):
            print(f"   💥 CRITICAL HIT!")
        if kwargs.get('armor_penetration'):
            print(f"   🗡️  Armor Penetration: {kwargs['armor_penetration']*100:.0f}%")
        if kwargs.get('bonus_damage'):
            print(f"   ⚡ Bonus Damage: +{kwargs['bonus_damage']:.1f}")

        # Tag information with comprehensive validation
        if source_tags and len(source_tags) > 0:
            print(f"   🏷️  TAGS DETECTED: {source_tags}")

            # Categorize tags by system
            damage_tags = [t for t in source_tags if t in [
                'physical', 'slashing', 'piercing', 'crushing',
                'fire', 'ice', 'lightning', 'poison', 'energy', 'arcane'
            ]]
            geometry_tags = [t for t in source_tags if t in [
                'single', 'circle', 'cone', 'chain', 'beam', 'line', 'aoe'
            ]]
            status_tags = [t for t in source_tags if t in [
                'burn', 'freeze', 'slow', 'shock', 'bleed', 'poison_status', 'root', 'stun'
            ]]
            property_tags = [t for t in source_tags if t in [
                'fast', 'reach', 'precision', 'armor_breaker', 'cleaving', '1H', '2H', 'versatile'
            ]]

            # Unknown tags (potential typos or new tags)
            known_tags = set(damage_tags + geometry_tags + status_tags + property_tags)
            unknown_tags = [t for t in source_tags if t not in known_tags]

            # Display categorized tags
            if damage_tags:
                print(f"      ⚔️  Damage: {', '.join(damage_tags)}")
            if geometry_tags:
                print(f"      📐 Geometry: {', '.join(geometry_tags)}")
            if status_tags:
                print(f"      💫 Status: {', '.join(status_tags)}")
            if property_tags:
                print(f"      🔧 Properties: {', '.join(property_tags)}")
            if unknown_tags:
                print(f"      ❓ Unknown: {', '.join(unknown_tags)} (typo or new tag?)")

            # Tag validation warnings
            tag_warnings = []
            if not damage_tags and not status_tags:
                tag_warnings.append("No damage or status tags (what type of attack is this?)")
            if not geometry_tags:
                tag_warnings.append("No geometry tag (defaulting to single target)")
            if 'burn' in status_tags and 'fire' not in damage_tags:
                tag_warnings.append("burn status without fire damage tag")
            if 'freeze' in status_tags and 'ice' not in damage_tags:
                tag_warnings.append("freeze status without ice damage tag")
            if len(geometry_tags) > 1:
                tag_warnings.append(f"Multiple geometry tags: {geometry_tags} (which one applies?)")

            if tag_warnings:
                print(f"      ⚠️  Tag Warnings:")
                for warning in tag_warnings:
                    print(f"         • {warning}")
            else:
                print(f"      ✅ Tag validation passed")

        else:
            print(f"   ⚠️  NO TAGS DETECTED!")
            print(f"      This attack is using the legacy damage system")
            print(f"      Expected: Attack should have tags like ['physical', 'single', 'piercing']")

        # Effect parameters (if passed)
        if 'effect_params' in kwargs and kwargs['effect_params']:
            print(f"   📊 Effect Parameters:")
            for key, value in kwargs['effect_params'].items():
                print(f"      {key}: {value}")
        elif source and hasattr(source, 'effect_params') and source.effect_params:
            print(f"   📊 Source Effect Parameters:")
            for key, value in source.effect_params.items():
                print(f"      {key}: {value}")

        print(f"   HP: {self.current_health:.1f}/{self.max_health:.1f} ({self.current_health/self.max_health*100:.1f}%)")
        print(f"   Total damage taken: {self.total_damage_taken:.1f}")

        # Check active status effects
        if hasattr(self, 'status_manager') and len(self.status_manager.active_effects) > 0:
            print(f"   📋 Active Status Effects:")
            for effect in self.status_manager.active_effects:
                effect_name = effect.status_id
                stacks = effect.stacks
                duration = effect.duration_remaining
                damage_per_tick = effect.damage_per_second if hasattr(effect, 'damage_per_second') else 0
                if damage_per_tick > 0:
                    print(f"      - {effect_name} (x{stacks}, {duration:.1f}s, {damage_per_tick:.1f} dmg/sec)")
                else:
                    print(f"      - {effect_name} (x{stacks}, {duration:.1f}s)")

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

    def update_ai(self, dt: float, player_position: Tuple[float, float],
                  aggro_multiplier: float = 1.0, speed_multiplier: float = 1.0):
        """Override AI - training dummy doesn't move or attack

        Args:
            dt: Delta time in seconds
            player_position: Current player position
            aggro_multiplier: Ignored (training dummy doesn't aggro)
            speed_multiplier: Ignored (training dummy doesn't move)
        """
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
