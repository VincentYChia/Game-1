"""
Enemy system for Game-1
Handles enemy definitions, AI states, and behavior
"""
from __future__ import annotations
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from pathlib import Path
from entities.status_manager import add_status_manager_to_entity
from core.effect_executor import get_effect_executor
from core.tag_debug import get_tag_debugger


# ============================================================================
# ENEMY AI STATES
# ============================================================================
class AIState(Enum):
    IDLE = "idle"
    WANDER = "wander"
    PATROL = "patrol"
    GUARD = "guard"
    CHASE = "chase"
    ATTACK = "attack"
    FLEE = "flee"
    DEAD = "dead"
    CORPSE = "corpse"


# ============================================================================
# ENEMY DEFINITION (from JSON)
# ============================================================================
@dataclass
class DropDefinition:
    material_id: str
    quantity_min: int
    quantity_max: int
    chance: float  # 0.0 to 1.0

@dataclass
class SpecialAbility:
    """Tag-based special attack for enemies"""
    ability_id: str
    cooldown: float  # Seconds between uses
    tags: List[str]  # Effect tags (e.g., ["fire", "circle", "burn"])
    params: Dict[str, Any]  # Effect parameters
    health_threshold: float = 1.0  # Use when HP below this (1.0 = always, 0.5 = below 50%)
    priority: int = 0  # Higher priority abilities used first

@dataclass
class AIPattern:
    default_state: str
    aggro_on_damage: bool
    aggro_on_proximity: bool
    flee_at_health: float  # 0.0 to 1.0
    call_for_help_radius: float
    pack_coordination: bool = False
    special_abilities: List[str] = field(default_factory=list)

@dataclass
class EnemyDefinition:
    enemy_id: str
    name: str
    tier: int
    category: str
    behavior: str

    # Stats
    max_health: float
    damage_min: float
    damage_max: float
    defense: float
    speed: float
    aggro_range: float
    attack_speed: float

    # Drops and AI
    drops: List[DropDefinition]
    ai_pattern: AIPattern

    # Special abilities (tag-based attacks)
    special_abilities: List[SpecialAbility] = field(default_factory=list)

    # Metadata
    narrative: str = ""
    tags: List[str] = field(default_factory=list)
    icon_path: Optional[str] = None  # Optional path to enemy icon image (PNG/JPG)


# ============================================================================
# ENEMY DATABASE (Singleton)
# ============================================================================
class EnemyDatabase:
    _instance = None

    def __init__(self):
        self.enemies: Dict[str, EnemyDefinition] = {}
        self.enemies_by_tier: Dict[int, List[EnemyDefinition]] = {1: [], 2: [], 3: [], 4: []}
        self.loaded = False

        # Chance text to float mapping
        self.chance_map = {
            "guaranteed": 1.0,
            "high": 0.75,
            "moderate": 0.5,
            "low": 0.25,
            "rare": 0.10,
            "improbable": 0.05
        }

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EnemyDatabase()
        return cls._instance

    def load_from_file(self, filepath: str) -> bool:
        """Load enemy definitions from hostiles JSON"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for enemy_data in data.get('enemies', []):
                # Parse stats
                stats = enemy_data.get('stats', {})
                damage = stats.get('damage', [5, 10])

                # Parse drops
                drops = []
                for drop_data in enemy_data.get('drops', []):
                    qty = drop_data.get('quantity', [1, 1])
                    chance_text = drop_data.get('chance', 'low')
                    chance_val = self.chance_map.get(chance_text, 0.5)

                    drops.append(DropDefinition(
                        material_id=drop_data.get('materialId', ''),
                        quantity_min=qty[0] if isinstance(qty, list) else qty,
                        quantity_max=qty[1] if isinstance(qty, list) else qty,
                        chance=chance_val
                    ))

                # Parse AI pattern
                ai_data = enemy_data.get('aiPattern', {})
                ai_pattern = AIPattern(
                    default_state=ai_data.get('defaultState', 'idle'),
                    aggro_on_damage=ai_data.get('aggroOnDamage', True),
                    aggro_on_proximity=ai_data.get('aggroOnProximity', False),
                    flee_at_health=ai_data.get('fleeAtHealth', 0.0),
                    call_for_help_radius=ai_data.get('callForHelpRadius', 0.0),
                    pack_coordination=ai_data.get('packCoordination', False),
                    special_abilities=ai_data.get('specialAbilities', [])
                )

                # Parse special abilities (tag-based attacks)
                special_abilities = []
                for ability_data in enemy_data.get('specialAbilities', []):
                    special_abilities.append(SpecialAbility(
                        ability_id=ability_data.get('abilityId', ''),
                        cooldown=ability_data.get('cooldown', 10.0),
                        tags=ability_data.get('tags', []),
                        params=ability_data.get('params', {}),
                        health_threshold=ability_data.get('healthThreshold', 1.0),
                        priority=ability_data.get('priority', 0)
                    ))

                # Parse metadata
                metadata = enemy_data.get('metadata', {})

                # Auto-generate icon path if not provided
                enemy_id = enemy_data.get('enemyId', '')
                icon_path = enemy_data.get('iconPath')
                if not icon_path and enemy_id:
                    icon_path = f"enemies/{enemy_id}.png"

                # Create definition
                enemy_def = EnemyDefinition(
                    enemy_id=enemy_id,
                    name=enemy_data.get('name', 'Unknown Enemy'),
                    tier=enemy_data.get('tier', 1),
                    category=enemy_data.get('category', 'beast'),
                    behavior=enemy_data.get('behavior', 'passive_patrol'),
                    max_health=stats.get('health', 50) * 0.1,  # Reduced by 90% for testing
                    damage_min=damage[0] if isinstance(damage, list) else damage,
                    damage_max=damage[1] if isinstance(damage, list) else damage,
                    defense=stats.get('defense', 0),
                    speed=stats.get('speed', 1.0),
                    aggro_range=stats.get('aggroRange', 5),
                    attack_speed=stats.get('attackSpeed', 1.0),
                    drops=drops,
                    ai_pattern=ai_pattern,
                    special_abilities=special_abilities,
                    narrative=metadata.get('narrative', ''),
                    tags=metadata.get('tags', []),
                    icon_path=icon_path
                )

                self.enemies[enemy_def.enemy_id] = enemy_def
                if enemy_def.tier in self.enemies_by_tier:
                    self.enemies_by_tier[enemy_def.tier].append(enemy_def)

            self.loaded = True
            print(f"✓ Loaded {len(self.enemies)} enemy definitions")
            return True

        except Exception as e:
            print(f"⚠ Error loading enemies: {e}")
            self._create_placeholders()
            return False

    def _create_placeholders(self):
        """Create basic placeholder enemies if file fails to load"""
        wolf = EnemyDefinition(
            enemy_id="wolf_grey",
            name="Grey Wolf",
            tier=1,
            category="beast",
            behavior="passive_patrol",
            max_health=80,
            damage_min=8,
            damage_max=12,
            defense=5,
            speed=1.2,
            aggro_range=5,
            attack_speed=1.0,
            drops=[DropDefinition("wolf_pelt", 2, 4, 1.0)],
            ai_pattern=AIPattern("wander", True, False, 0.2, 8)
        )
        self.enemies["wolf_grey"] = wolf
        self.enemies_by_tier[1].append(wolf)
        self.loaded = True

    def get_enemy(self, enemy_id: str) -> Optional[EnemyDefinition]:
        return self.enemies.get(enemy_id)

    def get_random_enemy(self, tier: int) -> Optional[EnemyDefinition]:
        """Get random enemy of specified tier"""
        enemies = self.enemies_by_tier.get(tier, [])
        return random.choice(enemies) if enemies else None


# ============================================================================
# ENEMY INSTANCE (Active enemy in world)
# ============================================================================
class Enemy:
    """Active enemy instance with position, health, AI state"""

    def __init__(self, definition: EnemyDefinition, position: Tuple[float, float], chunk_coords: Tuple[int, int]):
        self.definition = definition
        self.position = list(position)  # [x, y] for easy modification
        self.spawn_position = list(position)  # Remember spawn point
        self.chunk_coords = chunk_coords

        # Combat stats
        self.current_health = definition.max_health
        self.max_health = definition.max_health
        self.is_boss = "boss" in definition.behavior.lower()

        # AI state
        self.ai_state = self._get_initial_state()
        self.target_position: Optional[List[float]] = None
        self.last_damaged_by_player = False

        # Movement
        self.wander_timer = 0.0
        self.wander_cooldown = random.uniform(2.0, 5.0)

        # Combat
        self.attack_cooldown = 0.0
        self.in_combat = False
        self.last_attack_time = 0.0

        # Death and respawn
        self.is_alive = True
        self.time_since_death = 0.0
        self.corpse_lifetime = 60.0  # Will be overridden by config

        # Add status effect manager
        add_status_manager_to_entity(self)

        # Add category for tag system context-awareness
        self.category = definition.category

        # Tag-based attack system
        self.effect_executor = get_effect_executor()
        self.debugger = get_tag_debugger()

        # Special ability cooldowns (dict: ability_id -> cooldown_remaining)
        self.ability_cooldowns: Dict[str, float] = {
            ability.ability_id: 0.0 for ability in definition.special_abilities
        }

    def _get_initial_state(self) -> AIState:
        """Map behavior string to initial AI state"""
        state_map = {
            "idle": AIState.IDLE,
            "wander": AIState.WANDER,
            "patrol": AIState.PATROL,
            "guard": AIState.GUARD,
        }
        default = self.definition.ai_pattern.default_state
        return state_map.get(default, AIState.IDLE)

    def distance_to(self, position: Tuple[float, float]) -> float:
        """Calculate distance to a position"""
        dx = self.position[0] - position[0]
        dy = self.position[1] - position[1]
        return (dx * dx + dy * dy) ** 0.5

    def take_damage(self, damage: float, from_player: bool = True) -> bool:
        """Apply damage to enemy. Returns True if enemy died"""
        self.current_health -= damage
        self.in_combat = True

        if from_player:
            self.last_damaged_by_player = True
            # Aggro on damage
            if self.definition.ai_pattern.aggro_on_damage and self.ai_state != AIState.DEAD:
                self.ai_state = AIState.CHASE

        # Check for death
        if self.current_health <= 0:
            self.current_health = 0
            self.is_alive = False
            self.ai_state = AIState.DEAD
            return True

        # Check for flee threshold
        health_percent = self.current_health / self.max_health
        if health_percent <= self.definition.ai_pattern.flee_at_health and self.ai_state != AIState.FLEE:
            self.ai_state = AIState.FLEE

        return False

    def generate_loot(self) -> List[Tuple[str, int]]:
        """Generate loot drops based on drop table"""
        loot = []
        for drop in self.definition.drops:
            if random.random() <= drop.chance:
                quantity = random.randint(drop.quantity_min, drop.quantity_max)
                loot.append((drop.material_id, quantity))
        return loot

    def update_ai(self, dt: float, player_position: Tuple[float, float]):
        """Update enemy AI behavior"""
        if not self.is_alive:
            # Handle corpse decay
            if self.ai_state == AIState.DEAD:
                self.ai_state = AIState.CORPSE
            self.time_since_death += dt
            return

        # Update status effects
        if hasattr(self, 'status_manager'):
            self.status_manager.update(dt)

        # Update attack cooldown
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        # Update ability cooldowns
        for ability_id in self.ability_cooldowns:
            if self.ability_cooldowns[ability_id] > 0:
                self.ability_cooldowns[ability_id] -= dt

        # Get distance to player
        dist_to_player = self.distance_to(player_position)

        # State machine
        if self.ai_state == AIState.IDLE:
            self._ai_idle(dt, dist_to_player)
        elif self.ai_state == AIState.WANDER:
            self._ai_wander(dt, dist_to_player)
        elif self.ai_state == AIState.PATROL:
            self._ai_patrol(dt, dist_to_player)
        elif self.ai_state == AIState.GUARD:
            self._ai_guard(dt, dist_to_player)
        elif self.ai_state == AIState.CHASE:
            self._ai_chase(dt, dist_to_player, player_position)
        elif self.ai_state == AIState.ATTACK:
            self._ai_attack(dt, dist_to_player, player_position)
        elif self.ai_state == AIState.FLEE:
            self._ai_flee(dt, dist_to_player, player_position)

    def _ai_idle(self, dt: float, dist_to_player: float):
        """Idle state - stand still, check for aggro"""
        if self.definition.ai_pattern.aggro_on_proximity and dist_to_player <= self.definition.aggro_range:
            self.ai_state = AIState.CHASE

    def _ai_wander(self, dt: float, dist_to_player: float):
        """Wander state - random movement"""
        self.wander_timer += dt

        if self.wander_timer >= self.wander_cooldown:
            # Pick new random direction
            angle = random.uniform(0, 6.28)  # 2*pi
            distance = random.uniform(1.0, 3.0)
            self.target_position = [
                self.spawn_position[0] + distance * (2 * random.random() - 1),
                self.spawn_position[1] + distance * (2 * random.random() - 1)
            ]
            self.wander_timer = 0
            self.wander_cooldown = random.uniform(2.0, 5.0)

        # Move towards target
        if self.target_position:
            self._move_towards(self.target_position, dt)

        # Check aggro
        if self.definition.ai_pattern.aggro_on_proximity and dist_to_player <= self.definition.aggro_range:
            self.ai_state = AIState.CHASE

    def _ai_patrol(self, dt: float, dist_to_player: float):
        """Patrol state - move in pattern around spawn"""
        # Simple back-and-forth patrol for now
        if not self.target_position:
            self.target_position = [
                self.spawn_position[0] + random.uniform(-5, 5),
                self.spawn_position[1] + random.uniform(-5, 5)
            ]

        # Move towards target
        self._move_towards(self.target_position, dt)

        # Reached target? Pick new one
        if self.distance_to(self.target_position) < 0.5:
            self.target_position = [
                self.spawn_position[0] + random.uniform(-5, 5),
                self.spawn_position[1] + random.uniform(-5, 5)
            ]

        # Check aggro
        if self.definition.ai_pattern.aggro_on_proximity and dist_to_player <= self.definition.aggro_range:
            self.ai_state = AIState.CHASE

    def _ai_guard(self, dt: float, dist_to_player: float):
        """Guard state - stay at spawn, aggro when close"""
        # Return to spawn if moved
        dist_from_spawn = self.distance_to(self.spawn_position)
        if dist_from_spawn > 1.0:
            self._move_towards(self.spawn_position, dt)

        # Check aggro
        if self.definition.ai_pattern.aggro_on_proximity and dist_to_player <= self.definition.aggro_range:
            self.ai_state = AIState.CHASE

    def _ai_chase(self, dt: float, dist_to_player: float, player_position: Tuple[float, float]):
        """Chase state - pursue player"""
        # In attack range?
        attack_range = 1.5  # Default melee range
        if dist_to_player <= attack_range:
            self.ai_state = AIState.ATTACK
            return

        # Player too far? Return to spawn
        if dist_to_player > self.definition.aggro_range * 2:
            self.ai_state = self._get_initial_state()
            self.target_position = None
            self.in_combat = False
            return

        # Chase player
        self._move_towards(player_position, dt)

    def _ai_attack(self, dt: float, dist_to_player: float, player_position: Tuple[float, float]):
        """Attack state - attack player"""
        attack_range = 1.5

        # Player moved away?
        if dist_to_player > attack_range * 1.5:
            self.ai_state = AIState.CHASE
            return

        # Attack cooldown handled by combat manager
        # Enemy just faces player and waits for attack cooldown

    def _ai_flee(self, dt: float, dist_to_player: float, player_position: Tuple[float, float]):
        """Flee state - run away from player"""
        # Run away from player
        dx = self.position[0] - player_position[0]
        dy = self.position[1] - player_position[1]

        # Normalize and run
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 0.1:
            flee_target = [
                self.position[0] + (dx / dist) * 5,
                self.position[1] + (dy / dist) * 5
            ]
            self._move_towards(flee_target, dt)

        # Safe now?
        if dist_to_player > self.definition.aggro_range * 2:
            self.ai_state = AIState.WANDER
            self.in_combat = False

    def _is_within_chunk_bounds(self, x: float, y: float) -> bool:
        """Check if position is within the enemy's spawn chunk boundaries"""
        # Each chunk is 16x16 tiles
        chunk_min_x = self.chunk_coords[0] * 16
        chunk_max_x = (self.chunk_coords[0] + 1) * 16
        chunk_min_y = self.chunk_coords[1] * 16
        chunk_max_y = (self.chunk_coords[1] + 1) * 16

        return chunk_min_x <= x <= chunk_max_x and chunk_min_y <= y <= chunk_max_y

    def _clamp_to_chunk_bounds(self, x: float, y: float) -> Tuple[float, float]:
        """Clamp position to chunk boundaries"""
        chunk_min_x = self.chunk_coords[0] * 16
        chunk_max_x = (self.chunk_coords[0] + 1) * 16
        chunk_min_y = self.chunk_coords[1] * 16
        chunk_max_y = (self.chunk_coords[1] + 1) * 16

        x = max(chunk_min_x, min(x, chunk_max_x))
        y = max(chunk_min_y, min(y, chunk_max_y))
        return (x, y)

    def _move_towards(self, target: Tuple[float, float], dt: float):
        """Move towards a target position, restricted to chunk boundaries"""
        # Check if immobilized by status effects
        if hasattr(self, 'status_manager') and self.status_manager.is_immobilized():
            return

        dx = target[0] - self.position[0]
        dy = target[1] - self.position[1]
        dist = (dx * dx + dy * dy) ** 0.5

        if dist > 0.1:
            # Normalize and move
            move_speed = self.definition.speed * dt * 2  # Reduced from 10 to 2 for slower movement
            new_x = self.position[0] + (dx / dist) * move_speed
            new_y = self.position[1] + (dy / dist) * move_speed

            # Clamp to chunk boundaries
            new_x, new_y = self._clamp_to_chunk_bounds(new_x, new_y)

            self.position[0] = new_x
            self.position[1] = new_y

    def can_attack(self) -> bool:
        """Check if enemy can attack (cooldown ready and not CC'd)"""
        # Check if stunned/silenced
        if hasattr(self, 'status_manager') and self.status_manager.is_silenced():
            return False

        return self.attack_cooldown <= 0 and self.ai_state == AIState.ATTACK

    def perform_attack(self) -> float:
        """Perform attack, return damage amount"""
        self.attack_cooldown = 1.0 / self.definition.attack_speed
        damage = random.uniform(self.definition.damage_min, self.definition.damage_max)
        return damage

    def can_use_special_ability(self) -> Optional[SpecialAbility]:
        """Check if enemy can use a special ability. Returns ability if available, None otherwise"""
        if not self.definition.special_abilities:
            return None

        # Check if silenced
        if hasattr(self, 'status_manager') and self.status_manager.is_silenced():
            return None

        # Sort abilities by priority (higher first)
        sorted_abilities = sorted(
            self.definition.special_abilities,
            key=lambda a: a.priority,
            reverse=True
        )

        # Find first usable ability
        health_percent = self.current_health / self.max_health
        for ability in sorted_abilities:
            # Check health threshold
            if health_percent > ability.health_threshold:
                continue

            # Check cooldown
            if self.ability_cooldowns.get(ability.ability_id, 0) > 0:
                continue

            # Found usable ability!
            return ability

        return None

    def attack_with_tags(self, target: Any, tags: List[str], params: dict, available_targets: List[Any] = None) -> bool:
        """
        Enemy attacks using tag-based effects system (inherits from player/turret systems)

        Args:
            target: Primary target (usually player)
            tags: Effect tags (e.g., ["fire", "circle", "burn"])
            params: Effect parameters (baseDamage, geometry params, etc.)
            available_targets: List of all potential targets for AOE/chain (default: [target])

        Returns:
            True if attack succeeded, False if failed
        """
        if available_targets is None:
            available_targets = [target] if target else []

        print(f"\n🔥 ENEMY SPECIAL: {self.definition.name}")
        print(f"   Using tags: {tags}")

        # Execute effect using tag system (same as player/turret)
        try:
            context = self.effect_executor.execute_effect(
                source=self,
                primary_target=target,
                tags=tags,
                params=params,
                available_entities=available_targets
            )

            self.debugger.info(
                f"Enemy {self.definition.enemy_id} used special ability: {len(context.targets)} targets affected"
            )
            print(f"   ✓ Affected {len(context.targets)} target(s)")

            return True

        except Exception as e:
            self.debugger.error(f"Enemy special ability failed: {e}")
            print(f"   ⚠ Ability failed: {e}")
            return False

    def use_special_ability(self, ability: SpecialAbility, target: Any, available_targets: List[Any] = None) -> bool:
        """
        Use a specific special ability

        Args:
            ability: The special ability to use
            target: Primary target
            available_targets: List of all potential targets

        Returns:
            True if successful
        """
        # Execute the tag-based attack
        success = self.attack_with_tags(
            target=target,
            tags=ability.tags,
            params=ability.params,
            available_targets=available_targets
        )

        if success:
            # Start cooldown
            self.ability_cooldowns[ability.ability_id] = ability.cooldown

        return success
