"""
Combat Manager for Game-1
Handles enemy spawning, combat calculations, and loot
"""
import json
import random
import math
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from ..main import WorldSystem, Character, Inventory

from .enemy import Enemy, EnemyDatabase, EnemyDefinition, AIState
from data.models.world import PlacedEntityType
from core.effect_executor import get_effect_executor
from core.tag_debug import get_tag_debugger
from core.debug_display import debug_print


# ============================================================================
# COMBAT CONFIGURATION
# ============================================================================
class CombatConfig:
    """Loads and stores combat configuration from JSON"""

    def __init__(self):
        self.exp_rewards = {"tier1": 100, "tier2": 400, "tier3": 1600, "tier4": 6400}
        self.boss_multiplier = 10.0

        self.safe_zone_x = 50
        self.safe_zone_y = 50
        self.safe_zone_radius = 15

        self.spawn_rates = {}
        self.respawn_times = {}

        # Density weight mapping (for weighted spawn pool)
        self.density_weights = {
            "very_low": 0.5,
            "low": 0.75,
            "moderate": 1.0,
            "high": 2.0,
            "very_high": 3.0
        }

        # Attack ranges are now determined by equipped weapon
        self.base_attack_cooldown = 1.0
        self.tool_attack_cooldown = 0.5
        self.corpse_lifetime = 60.0
        self.combat_timeout = 5.0

    def load_from_file(self, filepath: str) -> bool:
        """Load combat config from JSON"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Load EXP rewards
            exp_data = data.get('experienceRewards', {})
            self.exp_rewards = {
                "tier1": exp_data.get('tier1', 100),
                "tier2": exp_data.get('tier2', 400),
                "tier3": exp_data.get('tier3', 1600),
                "tier4": exp_data.get('tier4', 6400)
            }
            self.boss_multiplier = exp_data.get('bossMultiplier', 10.0)

            # Load safe zone
            safe_data = data.get('safeZone', {})
            self.safe_zone_x = safe_data.get('centerX', 50)
            self.safe_zone_y = safe_data.get('centerY', 50)
            self.safe_zone_radius = safe_data.get('radius', 15)

            # Load spawn rates
            self.spawn_rates = data.get('spawnRates', {})

            # Load respawn times
            respawn_data = data.get('enemyRespawn', {})
            self.respawn_times = {
                'base': respawn_data.get('baseRespawnTime', 300),
                'tier1': respawn_data.get('tierMultipliers', {}).get('tier1', 1.0),
                'tier2': respawn_data.get('tierMultipliers', {}).get('tier2', 1.5),
                'tier3': respawn_data.get('tierMultipliers', {}).get('tier3', 2.0),
                'tier4': respawn_data.get('tierMultipliers', {}).get('tier4', 3.0),
                'boss': respawn_data.get('bossRespawnTime', 1800)
            }

            # Load mechanics
            mechanics = data.get('combatMechanics', {})
            # Note: player_attack_range is now determined by equipped weapon
            self.base_attack_cooldown = mechanics.get('baseAttackCooldown', 1.0)
            self.tool_attack_cooldown = mechanics.get('toolAttackCooldown', 0.5)
            self.corpse_lifetime = mechanics.get('enemyCorpseLifetime', 60)
            self.combat_timeout = mechanics.get('combatTimeout', 5.0)

            # Load spawn weights (optional, uses defaults if not present)
            spawn_weights = data.get('spawnWeights', {})
            if spawn_weights:
                for density, weight in spawn_weights.items():
                    self.density_weights[density] = float(weight)

            print(f"✓ Loaded combat configuration")
            return True

        except Exception as e:
            print(f"⚠ Error loading combat config: {e}")
            return False


# ============================================================================
# COMBAT MANAGER
# ============================================================================
class CombatManager:
    """Manages all combat in the game"""

    def __init__(self, world_system, character):
        self.world = world_system
        self.character = character
        self.config = CombatConfig()
        self.enemy_db = EnemyDatabase.get_instance()

        # Tag system integration
        self.effect_executor = get_effect_executor()
        self.debugger = get_tag_debugger()

        # Chunk templates for weighted spawn pool
        self.chunk_templates: Dict[str, dict] = {}
        self.chunk_type_mapping = {
            # Map ChunkType enum values to template chunkType strings
            "peaceful_forest": "peaceful_forest",
            "peaceful_quarry": "peaceful_quarry",
            "peaceful_cave": "peaceful_cave",
            "dangerous_forest": "dangerous_forest",
            "dangerous_quarry": "dangerous_quarry",
            "dangerous_cave": "dangerous_cave",
            "rare_hidden_forest": "rare_forest",
            "rare_ancient_quarry": "rare_quarry",
            "rare_deep_cave": "rare_cave"
        }

        # Active enemies by chunk
        self.enemies: Dict[Tuple[int, int], List[Enemy]] = {}

        # Spawn tracking
        self.spawn_timers: Dict[Tuple[int, int], float] = {}

        # Corpses (enemies waiting to be looted)
        self.corpses: List[Enemy] = []

        # Combat state
        self.player_last_combat_time = 0.0
        self.player_in_combat = False

    def load_config(self, config_path: str, enemies_path: str, chunk_templates_path: Optional[str] = None):
        """Load combat configuration, enemy definitions, and chunk templates"""
        self.config.load_from_file(config_path)
        self.enemy_db.load_from_file(enemies_path)

        # Load chunk templates if provided
        if chunk_templates_path:
            self._load_chunk_templates(chunk_templates_path)
        else:
            # Try default path (relative to game root directory)
            default_path = Path("Definitions.JSON/Chunk-templates-2.JSON")
            if default_path.exists():
                self._load_chunk_templates(str(default_path))

    def _load_chunk_templates(self, filepath: str):
        """Load chunk template definitions for weighted spawn pools"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            templates = data.get('templates', [])
            for template in templates:
                chunk_type = template.get('chunkType')
                if chunk_type:
                    self.chunk_templates[chunk_type] = template

            print(f"✓ Loaded {len(self.chunk_templates)} chunk templates for spawning")
            return True

        except FileNotFoundError:
            print(f"⚠ Chunk templates not found at {filepath}, using tier-only spawning")
            return False
        except Exception as e:
            print(f"⚠ Error loading chunk templates: {e}")
            return False

    def is_in_safe_zone(self, x: float, y: float) -> bool:
        """Check if position is in safe zone (no spawning)"""
        dx = x - self.config.safe_zone_x
        dy = y - self.config.safe_zone_y
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.config.safe_zone_radius

    def get_chunk_danger_level(self, chunk) -> str:
        """Determine danger level from chunk type"""
        chunk_type_str = chunk.chunk_type.value
        if "peaceful" in chunk_type_str:
            return "peaceful"
        elif "dangerous" in chunk_type_str:
            return "dangerous"
        elif "rare" in chunk_type_str:
            return "rare"
        return "normal"

    def _get_chunk_template(self, chunk) -> Optional[dict]:
        """Get chunk template for a given chunk"""
        chunk_type_str = chunk.chunk_type.value
        template_key = self.chunk_type_mapping.get(chunk_type_str, chunk_type_str)
        return self.chunk_templates.get(template_key)

    def _get_density_weight(self, density: str) -> float:
        """Get spawn weight for a density level"""
        return self.config.density_weights.get(density, 1.0)

    def _get_allowed_tiers_for_danger_level(self, danger_level: str) -> set:
        """Get allowed tiers for a given danger level (tier caps)"""
        if danger_level == "peaceful":
            return {1}  # Only T1 enemies
        elif danger_level == "dangerous":
            return {1, 2, 3}  # T1-T3 enemies
        elif danger_level == "rare":
            return {1, 2, 3, 4}  # T1-T4 enemies (including bosses)
        else:
            return {1}  # Default to safest tier

    def _filter_tier_weights_for_danger(self, tier_weights: Dict[str, float], danger_level: str) -> Dict[str, float]:
        """Filter tier weights based on danger level restrictions"""
        allowed_tiers = self._get_allowed_tiers_for_danger_level(danger_level)

        filtered = {}
        for tier_name, weight in tier_weights.items():
            tier_num = int(tier_name.replace('tier', ''))
            if tier_num in allowed_tiers and weight > 0:
                filtered[tier_name] = weight

        # If no valid tiers, allow T1 as fallback
        if not filtered:
            filtered = {'tier1': 1.0}

        return filtered

    def _build_weighted_spawn_pool(self, chunk, danger_level: str, spawn_config: dict) -> List[Tuple[EnemyDefinition, float]]:
        """
        Build weighted spawn pool for a chunk.
        Returns list of (enemy_definition, weight) tuples.
        Uses chunk template enemySpawns if available, otherwise falls back to tier-based spawning.
        """
        spawn_pool = []

        # Try to get chunk template
        chunk_template = self._get_chunk_template(chunk)

        # 1. Add priority enemies from enemySpawns (if template exists)
        priority_enemy_ids = set()
        if chunk_template and 'enemySpawns' in chunk_template:
            enemy_spawns = chunk_template['enemySpawns']
            for enemy_id, spawn_info in enemy_spawns.items():
                # Get enemy definition
                enemy_def = self.enemy_db.get_enemy(enemy_id)
                if not enemy_def:
                    continue

                # Get density weight
                density = spawn_info.get('density', 'moderate')
                weight = self._get_density_weight(density)

                # Add to pool
                spawn_pool.append((enemy_def, weight))
                priority_enemy_ids.add(enemy_id)

        # 2. Add general pool enemies (tier-based, but exclude priority enemies)
        tier_weights = spawn_config.get('tierWeights', {'tier1': 1.0})
        filtered_weights = self._filter_tier_weights_for_danger(tier_weights, danger_level)

        # Get all enemies from allowed tiers
        for tier_name, tier_weight in filtered_weights.items():
            tier = int(tier_name.replace('tier', ''))
            tier_enemies = self.enemy_db.get_enemies_by_tier(tier)

            for enemy_def in tier_enemies:
                # Skip if already in priority pool
                if enemy_def.enemy_id in priority_enemy_ids:
                    continue

                # Add with base weight (1.0)
                spawn_pool.append((enemy_def, 1.0))

        # If pool is empty, fallback to T1 enemies
        if not spawn_pool:
            tier1_enemies = self.enemy_db.get_enemies_by_tier(1)
            for enemy_def in tier1_enemies:
                spawn_pool.append((enemy_def, 1.0))

        return spawn_pool

    def _select_from_weighted_pool(self, spawn_pool: List[Tuple[EnemyDefinition, float]]) -> Optional[EnemyDefinition]:
        """Select an enemy from weighted spawn pool using weighted random selection"""
        if not spawn_pool:
            return None

        # Build lists for weighted selection
        enemies = [enemy_def for enemy_def, weight in spawn_pool]
        weights = [weight for enemy_def, weight in spawn_pool]

        # Weighted random choice
        return random.choices(enemies, weights=weights, k=1)[0]

    def spawn_enemies_in_chunk(self, chunk, initial_spawn=False):
        """
        Spawn enemies in a chunk using weighted spawn pool system.
        Uses chunk template enemySpawns if available, otherwise falls back to tier-based spawning.
        """
        chunk_coords = (chunk.chunk_x, chunk.chunk_y)

        # Don't spawn if in safe zone
        chunk_center_x = chunk.chunk_x * 16 + 8  # CHUNK_SIZE = 16
        chunk_center_y = chunk.chunk_y * 16 + 8
        if self.is_in_safe_zone(chunk_center_x, chunk_center_y):
            return

        # Get spawn config for this chunk's danger level
        danger_level = self.get_chunk_danger_level(chunk)
        spawn_config = self.config.spawn_rates.get(danger_level)

        if not spawn_config:
            return

        # Initialize enemy list for chunk if needed
        if chunk_coords not in self.enemies:
            self.enemies[chunk_coords] = []

        # Don't spawn if already at max (max 3 per chunk)
        MAX_PER_CHUNK = 3
        current_count = len([e for e in self.enemies[chunk_coords] if e.is_alive])
        if current_count >= MAX_PER_CHUNK:
            return

        # Determine how many to spawn
        min_enemies = spawn_config.get('minEnemies', 1)
        max_enemies = spawn_config.get('maxEnemies', 3)
        target_count = random.randint(min_enemies, max_enemies)
        to_spawn = max(0, target_count - current_count)

        # Build weighted spawn pool (uses chunk template enemySpawns + general tier pool)
        spawn_pool = self._build_weighted_spawn_pool(chunk, danger_level, spawn_config)

        # Spawn enemies using weighted selection
        for _ in range(to_spawn):
            # Select enemy from weighted pool
            enemy_def = self._select_from_weighted_pool(spawn_pool)
            if not enemy_def:
                continue

            # Pick random position in chunk
            spawn_x = chunk.chunk_x * 16 + random.uniform(2, 14)
            spawn_y = chunk.chunk_y * 16 + random.uniform(2, 14)

            # Create enemy
            enemy = Enemy(enemy_def, (spawn_x, spawn_y), chunk_coords)
            enemy.corpse_lifetime = self.config.corpse_lifetime
            self.enemies[chunk_coords].append(enemy)

    def spawn_initial_enemies(self, player_position: Tuple[float, float], count: int = 5):
        """Spawn initial enemies for testing (around player but outside safe zone)"""
        print(f"🎮 Spawning {count} initial enemies for testing...")

        # Get chunks around player
        player_chunk_x = int(player_position[0] // 16)
        player_chunk_y = int(player_position[1] // 16)

        spawned = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if spawned >= count:
                    break

                chunk_x = player_chunk_x + dx
                chunk_y = player_chunk_y + dy
                chunk_coords = (chunk_x, chunk_y)

                # Get chunk
                chunk = self.world.chunks.get(chunk_coords)
                if not chunk:
                    continue

                # Check if in safe zone
                chunk_center_x = chunk_x * 16 + 8
                chunk_center_y = chunk_y * 16 + 8
                if self.is_in_safe_zone(chunk_center_x, chunk_center_y):
                    continue

                # Get chunk's danger level for tier spawning
                danger_level = self.get_chunk_danger_level(chunk)
                spawn_config = self.config.spawn_rates.get(danger_level, {})

                # Spawn 1-2 enemies in this chunk
                to_spawn = min(2, count - spawned)
                for _ in range(to_spawn):
                    # Pick tier based on chunk danger level and weights, with tier restrictions
                    tier_weights = spawn_config.get('tierWeights', {'tier1': 1.0})
                    filtered_weights = self._filter_tier_weights_for_danger(tier_weights, danger_level)
                    tier = self._pick_weighted_tier(filtered_weights)

                    # Get random enemy of selected tier
                    enemy_def = self.enemy_db.get_random_enemy(tier)
                    if not enemy_def:
                        # Fallback to T1 if tier not available
                        enemy_def = self.enemy_db.get_random_enemy(1)
                        if not enemy_def:
                            continue

                    # Random position in chunk
                    spawn_x = chunk_x * 16 + random.uniform(4, 12)
                    spawn_y = chunk_y * 16 + random.uniform(4, 12)

                    # Create enemy
                    enemy = Enemy(enemy_def, (spawn_x, spawn_y), chunk_coords)
                    enemy.corpse_lifetime = self.config.corpse_lifetime

                    if chunk_coords not in self.enemies:
                        self.enemies[chunk_coords] = []
                    self.enemies[chunk_coords].append(enemy)

                    spawned += 1
                    print(f"   ✓ Spawned T{tier} {enemy_def.name} at ({spawn_x:.1f}, {spawn_y:.1f})")

        print(f"✓ Spawned {spawned} initial enemies")

    def _pick_weighted_tier(self, tier_weights: Dict[str, float]) -> int:
        """Pick a tier based on weighted probabilities"""
        tiers = []
        weights = []
        for tier_name, weight in tier_weights.items():
            if weight > 0:
                tier_num = int(tier_name.replace('tier', ''))
                tiers.append(tier_num)
                weights.append(weight)

        if not tiers:
            return 1

        return random.choices(tiers, weights=weights)[0]

    def update(self, dt: float, shield_blocking: bool = False):
        """Update all enemies and combat logic
        shield_blocking: True if player is actively blocking with shield
        """
        player_pos = (self.character.position.x, self.character.position.y)

        # Update spawn timers
        for chunk_coords in self.spawn_timers:
            self.spawn_timers[chunk_coords] += dt

        # Update all enemies
        dead_enemies = []
        for chunk_coords, enemy_list in self.enemies.items():
            for enemy in enemy_list:
                if enemy.is_alive:
                    # Update AI
                    enemy.update_ai(dt, player_pos)

                    # Check if enemy can use special ability
                    dist = enemy.distance_to(player_pos)
                    special_ability = enemy.can_use_special_ability(dist_to_target=dist, target_position=player_pos)
                    if special_ability:
                        # Build available targets list (player + turrets + other valid targets)
                        available_targets = [self.character]

                        # Include turrets so enemies can target them with abilities
                        if hasattr(self.world, 'placed_entities'):
                            turrets = [e for e in self.world.placed_entities
                                      if e.entity_type == PlacedEntityType.TURRET and e.health > 0]
                            available_targets.extend(turrets)

                        # Use special ability if in range (abilities define their own ranges via distance conditions)
                        enemy.use_special_ability(special_ability, self.character, available_targets)

                    # Check if enemy can attack player normally
                    elif enemy.can_attack():
                        dist = enemy.distance_to(player_pos)
                        if dist <= 1.5:  # Melee range
                            self._enemy_attack_player(enemy, shield_blocking=shield_blocking)

                else:
                    # Enemy is dead - handle corpse
                    if enemy.ai_state == AIState.CORPSE and enemy.time_since_death >= enemy.corpse_lifetime:
                        # Remove corpse
                        dead_enemies.append((chunk_coords, enemy))
                    elif enemy not in self.corpses and enemy.ai_state == AIState.CORPSE:
                        self.corpses.append(enemy)

        # Remove expired corpses
        for chunk_coords, enemy in dead_enemies:
            if enemy in self.enemies[chunk_coords]:
                self.enemies[chunk_coords].remove(enemy)
            if enemy in self.corpses:
                self.corpses.remove(enemy)

        # Check dynamic spawning for nearby chunks
        self._check_dynamic_spawning(dt)

        # Update player combat state
        self._update_player_combat_state(dt)

    def _check_dynamic_spawning(self, dt: float):
        """Check if chunks need more enemies spawned dynamically"""
        player_chunk_x = int(self.character.position.x // 16)
        player_chunk_y = int(self.character.position.y // 16)

        # Check chunks in 3x3 area around player
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                chunk_x = player_chunk_x + dx
                chunk_y = player_chunk_y + dy
                chunk_coords = (chunk_x, chunk_y)

                # Get chunk from world
                chunk = self.world.chunks.get(chunk_coords)
                if not chunk:
                    continue

                # Check spawn timer
                if chunk_coords not in self.spawn_timers:
                    self.spawn_timers[chunk_coords] = 0.0

                # Get spawn interval for this chunk
                danger_level = self.get_chunk_danger_level(chunk)
                spawn_config = self.config.spawn_rates.get(danger_level, {})
                spawn_interval = spawn_config.get('spawnInterval', 120)

                # Time to spawn?
                if self.spawn_timers[chunk_coords] >= spawn_interval:
                    self.spawn_enemies_in_chunk(chunk)
                    self.spawn_timers[chunk_coords] = 0.0

    def _execute_aoe_attack(self, primary_target: Enemy, hand: str, radius: int) -> Tuple[float, bool, List[Tuple[str, int]]]:
        """Execute an AoE attack (devastate effect) hitting all enemies in radius"""
        from core.debug_display import debug_print
        import math

        # Find all enemies in radius
        targets = []
        for e in self.active_enemies:
            if e.is_alive():
                dx = e.position.x - self.character.position.x
                dy = e.position.y - self.character.position.y
                distance = math.sqrt(dx*dx + dy*dy)
                if distance <= radius:
                    targets.append(e)

        if not targets:
            targets = [primary_target]  # Fallback to primary target

        print(f"\n🌀 DEVASTATE (AoE Attack): Hitting {len(targets)} target(s) in {radius}-tile radius!")
        debug_print(f"🌀 AoE Attack: {len(targets)} targets in {radius}-tile radius")

        # Consume the devastate buff before attacking
        self.character.buffs.consume_buffs_for_action("attack")

        # Attack each target (reuse single-target logic)
        total_damage = 0
        any_crit = False
        all_loot = []

        for i, target in enumerate(targets):
            # Temporarily remove the devastate check to avoid infinite recursion
            # Call the parent attack logic directly
            damage, is_crit, loot = self._single_target_attack(target, hand)
            total_damage += damage
            any_crit = any_crit or is_crit
            all_loot.extend(loot)

        return (total_damage, any_crit, all_loot)

    def _single_target_attack(self, enemy: Enemy, hand: str) -> Tuple[float, bool, List[Tuple[str, int]]]:
        """Single-target attack logic (extracted from player_attack_enemy)"""
        hand_label = "MAINHAND" if hand == 'mainHand' else "OFFHAND"
        print(f"   → {enemy.definition.name} (HP: {enemy.current_health:.1f}/{enemy.max_health:.1f})")

        # Get weapon damage from currently selected slot (via TAB)
        weapon_damage = self.character.get_weapon_damage()  # Get average damage

        # Check if using a tool (axe/pickaxe) for combat - apply effectiveness penalty
        tool_type_effectiveness = 1.0
        equipped_weapon = None

        if hasattr(self.character, '_selected_slot') and self.character._selected_slot:
            equipped_weapon = self.character.equipment.slots.get(self.character._selected_slot)
        else:
            equipped_weapon = self.character.equipment.slots.get(hand)

        if equipped_weapon:
            tool_type_effectiveness = self.character.get_tool_effectiveness_for_action(equipped_weapon, 'combat')

        if weapon_damage == 0:
            weapon_damage = 5  # Unarmed damage

        weapon_damage = int(weapon_damage * tool_type_effectiveness)

        # Continue with full attack logic (weapon tags, stats, buffs, etc.)
        # [This will be a copy of the existing logic from player_attack_enemy]
        # For now, let's do a simplified version that calls the main method
        # We'll refactor to avoid duplication

        # TEMPORARY: Just apply basic damage
        # TODO: Extract full attack logic to avoid duplication
        base_damage = weapon_damage

        # Apply stat bonuses
        strength_mult = 1.0 + (self.character.stats.strength * 0.01)
        base_damage = base_damage * strength_mult

        # Apply empower buffs
        if hasattr(self.character, 'buffs'):
            empower_bonus = self.character.buffs.get_damage_bonus("combat")
            if empower_bonus == 0:
                empower_bonus = self.character.buffs.get_damage_bonus("damage")
            if empower_bonus > 0:
                base_damage = base_damage * (1.0 + empower_bonus)

        # Crit check (10% base)
        is_crit = False
        crit_chance = 0.10
        if random.random() < crit_chance:
            is_crit = True
            base_damage *= 2.0

        # Apply defense
        defense_reduction = enemy.definition.defense * 0.01
        final_damage = base_damage * (1.0 - min(0.75, defense_reduction))

        print(f"      Damage: {final_damage:.1f}" + (" CRIT!" if is_crit else ""))

        # Apply damage
        enemy_died = enemy.take_damage(final_damage, from_player=True)

        loot = []
        if enemy_died:
            print(f"      ☠️ Killed!")
            exp_reward = self._calculate_exp_reward(enemy)
            self.character.leveling.add_exp(exp_reward)
            loot = enemy.generate_loot()
            if loot:
                for material_id, quantity in loot:
                    self.character.inventory.add_item(material_id, quantity)

        return (final_damage, is_crit, loot)

    def player_attack_enemy(self, enemy: Enemy, hand: str = 'mainHand') -> Tuple[float, bool, List[Tuple[str, int]]]:
        """
        Calculate player damage to enemy
        Returns (damage, is_crit, loot) where loot is empty list if enemy didn't die
        hand: 'mainHand' or 'offHand' to specify which hand is attacking
        """
        # Check for active devastate buffs (AoE attacks like Whirlwind Strike)
        if hasattr(self.character, 'buffs'):
            for buff in self.character.buffs.active_buffs:
                if buff.effect_type == "devastate" and buff.category in ["damage", "combat"]:
                    # Execute AoE attack instead
                    return self._execute_aoe_attack(enemy, hand, int(buff.bonus_value))

        hand_label = "MAINHAND" if hand == 'mainHand' else "OFFHAND"
        print(f"\n⚔️ PLAYER {hand_label} ATTACK: {enemy.definition.name} (HP: {enemy.current_health:.1f}/{enemy.max_health:.1f})")

        # Get weapon damage from currently selected slot (via TAB)
        weapon_damage = self.character.get_weapon_damage()  # Get average damage
        print(f"   Weapon damage: {weapon_damage}")

        # Check if using a tool (axe/pickaxe) for combat - apply effectiveness penalty
        # Use the currently selected slot instead of the hand parameter
        tool_type_effectiveness = 1.0  # Default to full effectiveness
        equipped_weapon = None

        # Get the currently selected weapon/tool
        if hasattr(self.character, '_selected_slot') and self.character._selected_slot:
            equipped_weapon = self.character.equipment.slots.get(self.character._selected_slot)
        else:
            # Backward compatibility: use specified hand
            equipped_weapon = self.character.equipment.slots.get(hand)

        if equipped_weapon:
            tool_type_effectiveness = self.character.get_tool_effectiveness_for_action(equipped_weapon, 'combat')
            if tool_type_effectiveness < 1.0:
                print(f"   ⚠ Using {equipped_weapon.name} for combat: {int(tool_type_effectiveness*100)}% effectiveness")

        if weapon_damage == 0:
            weapon_damage = 5  # Unarmed damage
            print(f"   Using unarmed damage: {weapon_damage}")

        # Apply tool type effectiveness penalty
        weapon_damage = int(weapon_damage * tool_type_effectiveness)

        # WEAPON TAG MODIFIERS
        weapon_tag_damage_mult = 1.0
        weapon_tag_crit_bonus = 0.0
        armor_penetration = 0.0
        crushing_bonus = 0.0

        if equipped_weapon:
            weapon_tags = equipped_weapon.get_metadata_tags()
            if weapon_tags:
                from entities.components.weapon_tag_calculator import WeaponTagModifiers

                # Hand requirement damage bonus (2H = +20%, versatile without offhand = +10%)
                has_offhand = self.character.equipment.slots.get('offHand') is not None
                weapon_tag_damage_mult = WeaponTagModifiers.get_damage_multiplier(weapon_tags, has_offhand)

                # Precision crit bonus (+10%)
                weapon_tag_crit_bonus = WeaponTagModifiers.get_crit_chance_bonus(weapon_tags)

                # Armor penetration (armor_breaker = ignore 25% defense)
                armor_penetration = WeaponTagModifiers.get_armor_penetration(weapon_tags)

                # Crushing bonus vs armored enemies (+20% if defense > 10)
                crushing_bonus = WeaponTagModifiers.get_damage_vs_armored_bonus(weapon_tags)

                if weapon_tag_damage_mult > 1.0 or armor_penetration > 0 or crushing_bonus > 0:
                    print(f"   🏷️  Weapon tags: {', '.join(weapon_tags)}")
                    if weapon_tag_damage_mult > 1.0:
                        print(f"      +{int((weapon_tag_damage_mult - 1.0) * 100)}% damage (hand requirement)")
                    if armor_penetration > 0:
                        print(f"      {int(armor_penetration * 100)}% armor penetration")
                    if crushing_bonus > 0 and enemy.definition.defense > 10:
                        print(f"      +{int(crushing_bonus * 100)}% vs armored")

        # Apply weapon tag damage multiplier
        weapon_damage = int(weapon_damage * weapon_tag_damage_mult)

        # Calculate multipliers
        str_multiplier = 1.0 + (self.character.stats.strength * 0.05)
        print(f"   STR multiplier: {str_multiplier:.2f} (STR: {self.character.stats.strength})")

        # Title bonuses (from activity tracker)
        title_multiplier = 1.0
        if hasattr(self.character, 'activity_tracker'):
            title_multiplier = 1.0 + self.character.activity_tracker.get_combat_bonus()
        print(f"   Title multiplier: {title_multiplier:.2f}")

        # Equipment bonuses (already in weapon damage)

        # Calculate base damage
        base_damage = weapon_damage * str_multiplier * title_multiplier

        # Apply crushing bonus vs armored enemies
        if crushing_bonus > 0 and enemy.definition.defense > 10:
            base_damage *= (1.0 + crushing_bonus)

        print(f"   Base damage: {base_damage:.1f}")

        # SKILL BUFF BONUSES: Check for active damage buffs (empower)
        skill_damage_bonus = 0.0
        if hasattr(self.character, 'buffs'):
            # Check for empower buffs on damage or combat category
            empower_damage = self.character.buffs.get_damage_bonus('damage')
            empower_combat = self.character.buffs.get_damage_bonus('combat')
            skill_damage_bonus = max(empower_damage, empower_combat)

            if skill_damage_bonus > 0:
                base_damage *= (1.0 + skill_damage_bonus)
                print(f"   ⚡ Skill buff: +{skill_damage_bonus*100:.0f}% damage (total: {base_damage:.1f})")

        # Check for critical hit
        is_crit = False
        base_crit_chance = 0.02 * self.character.stats.luck  # 2% per luck point

        # SKILL BUFF BONUSES: Check for pierce buffs (critical chance)
        pierce_bonus = 0.0
        if hasattr(self.character, 'buffs'):
            pierce_bonus = self.character.buffs.get_total_bonus('pierce', 'damage')
            if pierce_bonus == 0:
                pierce_bonus = self.character.buffs.get_total_bonus('pierce', 'combat')

        # Add weapon tag crit bonus (precision)
        crit_chance = base_crit_chance + pierce_bonus + weapon_tag_crit_bonus

        if pierce_bonus > 0:
            print(f"   ⚡ Pierce buff: +{pierce_bonus*100:.0f}% crit chance (total: {crit_chance*100:.1f}%)")
        elif weapon_tag_crit_bonus > 0:
            print(f"   🎯 Precision: +{weapon_tag_crit_bonus*100:.0f}% crit chance (total: {crit_chance*100:.1f}%)")

        if random.random() < crit_chance:
            is_crit = True
            base_damage *= 2.0
            print(f"   💥 CRITICAL HIT! x2 damage")

            # Execute on-crit triggers from equipment
            self._execute_triggers('on_crit', target=enemy, hand=hand)

        # Apply enemy defense (with armor penetration from weapon tags)
        effective_defense = enemy.definition.defense * (1.0 - armor_penetration)
        defense_reduction = effective_defense * 0.01  # 1% reduction per defense
        final_damage = base_damage * (1.0 - min(0.75, defense_reduction))

        if armor_penetration > 0:
            print(f"   Enemy defense: {enemy.definition.defense} → {effective_defense:.1f} (after armor pen) (reduction: {defense_reduction*100:.1f}%)")
        else:
            print(f"   Enemy defense: {enemy.definition.defense} (reduction: {defense_reduction*100:.1f}%)")
        print(f"   ➜ Final damage: {final_damage:.1f}")

        # Apply damage to enemy
        enemy_died = enemy.take_damage(final_damage, from_player=True)

        # LIFESTEAL ENCHANTMENT: Heal for % of damage dealt (capped at 50%)
        if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
            for ench in equipped_weapon.enchantments:
                effect = ench.get('effect', {})
                if effect.get('type') == 'lifesteal':
                    lifesteal_percent = min(effect.get('value', 0.1), 0.50)  # 10% default, 50% cap
                    heal_amount = final_damage * lifesteal_percent
                    old_health = self.character.health
                    self.character.health = min(self.character.max_health, self.character.health + heal_amount)
                    new_health = self.character.health
                    print(f"   💚 LIFESTEAL ENCHANT ({lifesteal_percent*100:.0f}%, capped at 50%): Healed {heal_amount:.1f} HP")
                    print(f"      HP: {old_health:.1f} → {new_health:.1f}")

        # CHAIN DAMAGE ENCHANTMENT: Damage nearby enemies
        if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
            for ench in equipped_weapon.enchantments:
                effect = ench.get('effect', {})
                if effect.get('type') == 'chain_damage':
                    chain_count = int(effect.get('value', 2))  # Chain to 2 enemies default
                    chain_damage_percent = effect.get('damagePercent', 0.5)  # 50% damage default

                    # Find chain targets (exclude primary target)
                    from core.geometry.target_finder import TargetFinder
                    finder = TargetFinder()
                    available_enemies = [e for e in self.active_enemies if e.is_alive and e != enemy]

                    chain_targets = finder.find_chain_targets(
                        primary=enemy,
                        max_targets=chain_count,
                        available_entities=available_enemies
                    )

                    if chain_targets:
                        chain_damage = final_damage * chain_damage_percent
                        print(f"   ⚡ {ench.get('name', 'Chain Damage')}: Hitting {len(chain_targets)} additional target(s)")
                        for target in chain_targets:
                            target.take_damage(chain_damage, from_player=True)
                            print(f"      → {target.definition.name}: {chain_damage:.1f} damage")

        # Consume any consume-on-use buffs (Power Strike, etc.)
        if hasattr(self.character, 'buffs'):
            self.character.buffs.consume_buffs_for_action("attack")

        # WEAPON DURABILITY LOSS
        if equipped_weapon and hasattr(equipped_weapon, 'durability_current'):
            from core.config import Config
            if not Config.DEBUG_INFINITE_DURABILITY:
                durability_loss = 1.0

                # DEF stat reduces durability loss
                durability_loss *= self.character.stats.get_durability_loss_multiplier()

                # Unbreaking enchantment reduces durability loss
                if hasattr(equipped_weapon, 'enchantments') and equipped_weapon.enchantments:
                    for ench in equipped_weapon.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'durability_multiplier':
                            reduction = effect.get('value', 0.0)
                            durability_loss *= (1.0 - reduction)

                equipped_weapon.durability_current = max(0, equipped_weapon.durability_current - durability_loss)

                # Only warn about low/broken durability (use effective max with VIT bonus)
                effective_max = self.character.get_effective_max_durability(equipped_weapon)
                if equipped_weapon.durability_current == 0:
                    print(f"   💥 {equipped_weapon.name} has broken! (0/{effective_max})")
                elif equipped_weapon.durability_current <= effective_max * 0.2:
                    print(f"   ⚠️ {equipped_weapon.name} durability low: {equipped_weapon.durability_current:.0f}/{effective_max}")

        # Initialize loot list
        loot = []

        # Grant EXP if killed
        if enemy_died:
            print(f"   💀 Enemy killed!")
            exp_reward = self._calculate_exp_reward(enemy)
            self.character.leveling.add_exp(exp_reward)
            print(f"   +{exp_reward} EXP")

            # Auto-loot: Generate and add loot to inventory automatically
            loot = enemy.generate_loot()
            if loot:
                print(f"   💰 Auto-looting {len(loot)} item type(s):")
                for material_id, quantity in loot:
                    # Add to character's inventory
                    success = self.character.inventory.add_item(material_id, quantity)
                    if success:
                        print(f"      +{quantity}x {material_id}")
                    else:
                        print(f"      ⚠️ Inventory full! Could not add {quantity}x {material_id}")
            else:
                print(f"   No loot dropped")

            # Track combat activity
            if hasattr(self.character, 'activity_tracker'):
                self.character.activity_tracker.record_activity('combat', 1)
        else:
            print(f"   Enemy HP remaining: {enemy.current_health:.1f}/{enemy.max_health:.1f}")

        # Update combat state
        self.player_last_combat_time = 0.0
        self.player_in_combat = True

        # Apply weapon durability loss (after successful attack)
        if equipped_weapon and hasattr(equipped_weapon, 'durability_current'):
            from core.config import Config
            if not Config.DEBUG_INFINITE_DURABILITY:
                # -1 durability for proper use (weapon), -2 for improper use (tool)
                durability_loss = 1 if tool_type_effectiveness >= 1.0 else 2
                equipped_weapon.durability_current = max(0, equipped_weapon.durability_current - durability_loss)

                # Only warn about improper use, low, or broken
                if durability_loss == 2:
                    print(f"   ⚠️ Improper use! {equipped_weapon.name} loses {durability_loss} durability ({equipped_weapon.durability_current}/{equipped_weapon.durability_max})")
                elif equipped_weapon.durability_current == 0:
                    print(f"   💥 {equipped_weapon.name} has broken! (0/{equipped_weapon.durability_max})")
                elif equipped_weapon.durability_current <= equipped_weapon.durability_max * 0.2:
                    print(f"   ⚠️ {equipped_weapon.name} durability low: {equipped_weapon.durability_current}/{equipped_weapon.durability_max}")

        return (final_damage, is_crit, loot)

    def _apply_weapon_enchantment_effects(self, enemy: Enemy):
        """
        Apply onHit enchantment effects from equipped weapons to enemy

        Handles effects like Fire Aspect (burning), Poison, etc.

        Args:
            enemy: Target enemy to apply status effects to
        """
        # Check mainhand weapon for enchantments
        weapons_to_check = ['mainHand', 'offHand']

        for hand in weapons_to_check:
            weapon = self.character.equipment.slots.get(hand)
            if not weapon or not hasattr(weapon, 'enchantments'):
                continue

            # Apply each enchantment's onHit effect
            for enchantment in weapon.enchantments:
                effect = enchantment.get('effect', {})
                effect_type = effect.get('type')

                if effect_type == 'damage_over_time':
                    # Map element to status tag
                    element = effect.get('element', 'physical')
                    status_tag_map = {
                        'fire': 'burn',
                        'poison': 'poison',
                        'bleed': 'bleed'
                    }

                    status_tag = status_tag_map.get(element, 'burn')

                    # Build status params from enchantment effect
                    status_params = {
                        'duration': effect.get('duration', 5.0),
                        'damage_per_second': effect.get('damagePerSecond', 10.0)
                    }

                    # Apply the status effect
                    if hasattr(enemy, 'status_manager'):
                        enemy.status_manager.apply_status(status_tag, status_params, source=self.character)
                        print(f"   🔥 {enchantment.get('name', 'Enchantment')} triggered! Applied {status_tag}")

                elif effect_type == 'knockback':
                    # Apply knockback using existing effect executor
                    knockback_distance = effect.get('value', 2.0)
                    knockback_params = {'knockback_distance': knockback_distance}

                    from core.effect_executor import get_effect_executor
                    executor = get_effect_executor()
                    executor._apply_knockback(self.character, enemy, knockback_params)
                    print(f"   💨 {enchantment.get('name', 'Knockback')} triggered! Pushed enemy back")

                elif effect_type == 'slow':
                    # Apply slow status to enemy
                    slow_params = {
                        'duration': effect.get('duration', 3.0),
                        'speed_reduction': effect.get('value', 0.3)  # 30% slow default
                    }

                    if hasattr(enemy, 'status_manager'):
                        enemy.status_manager.apply_status('slow', slow_params, source=self.character)
                        print(f"   ❄️ {enchantment.get('name', 'Frost')} triggered! Applied slow")

    def execute_instant_player_aoe(self, radius: int, skill_name: str) -> int:
        """Execute instant AoE attack around player (for skills like Whirlwind Strike)

        Args:
            radius: Radius in tiles
            skill_name: Name of the skill for display

        Returns:
            Number of enemies affected
        """
        import math

        # Get player position
        player_pos = (self.character.position.x, self.character.position.y)

        # Find all enemies in radius
        affected_enemies = []
        all_enemies = self.get_all_active_enemies()

        for enemy in all_enemies:
            if enemy.is_alive:
                dx = enemy.position[0] - player_pos[0]
                dy = enemy.position[1] - player_pos[1]
                distance = math.sqrt(dx*dx + dy*dy)
                if distance <= radius:
                    affected_enemies.append(enemy)

        if not affected_enemies:
            print(f"   ⚠️  No enemies in {radius}-tile radius")
            return 0

        print(f"\n🌀 {skill_name}: Hitting {len(affected_enemies)} enemy(s) in {radius}-tile radius!")
        debug_print(f"🌀 {skill_name}: {len(affected_enemies)} enemies")

        # Execute tag-based AoE attack on each enemy
        # Use physical damage with circle geometry
        for enemy in affected_enemies:
            # Get weapon damage type tags
            equipped_weapon = self.character.equipment.slots.get('mainHand')
            damage_tags = ['physical']  # Default
            if equipped_weapon and hasattr(equipped_weapon, 'effect_tags'):
                # Keep damage type tags from weapon
                damage_types = ['physical', 'fire', 'ice', 'lightning', 'poison', 'arcane', 'shadow', 'holy', 'chaos']
                damage_tags = [tag for tag in equipped_weapon.effect_tags if tag in damage_types]
                if not damage_tags:
                    damage_tags = ['physical']

            # Execute attack with circle geometry
            tags = damage_tags + ['circle']
            params = {
                'baseDamage': self.character.get_weapon_damage() or 10,
                'circle_radius': radius
            }

            # Use the tag-based attack system
            self.player_attack_enemy_with_tags(enemy, tags, params)

        return len(affected_enemies)

    def _execute_tag_attack_aoe(self, primary_target: Enemy, tags: List[str], params: dict) -> Tuple[float, bool, List[Tuple[str, int]]]:
        """Execute AoE attack using tag system (for devastate buffs like Whirlwind Strike)"""
        from core.debug_display import debug_print

        print(f"🌀 AoE ATTACK via tags: {tags}")
        debug_print(f"🌀 AoE Attack executing with tags: {tags}")

        # Get all active enemies for geometry
        all_enemies = self.get_all_active_enemies()
        alive_enemies = [e for e in all_enemies if e.is_alive]

        # Setup effect parameters with character bonuses
        effect_params = params.copy()

        # Apply character stat bonuses to base damage
        if "baseDamage" in effect_params:
            base_damage = effect_params["baseDamage"]

            # Weapon damage
            weapon_damage = self.character.get_weapon_damage()
            if weapon_damage > 0:
                base_damage += weapon_damage

            # STR multiplier
            str_multiplier = 1.0 + (self.character.stats.strength * 0.05)
            base_damage *= str_multiplier

            # Title bonuses
            if hasattr(self.character, 'activity_tracker'):
                title_multiplier = 1.0 + self.character.activity_tracker.get_combat_bonus()
                base_damage *= title_multiplier

            # Skill buff bonuses (empower) - but NOT devastate since we already consumed it
            if hasattr(self.character, 'buffs'):
                empower_damage = self.character.buffs.get_damage_bonus('damage')
                empower_combat = self.character.buffs.get_damage_bonus('combat')
                skill_bonus = max(empower_damage, empower_combat)
                if skill_bonus > 0:
                    base_damage *= (1.0 + skill_bonus)
                    print(f"   ⚡ Skill buff: +{skill_bonus*100:.0f}% damage")

            effect_params["baseDamage"] = base_damage
            print(f"   Base damage (with bonuses): {base_damage:.1f}")

        # Execute effect using tag system
        try:
            context = self.effect_executor.execute_effect(
                source=self.character,
                primary_target=primary_target,
                tags=tags,
                params=effect_params,
                available_entities=alive_enemies
            )

            print(f"   ✓ Affected {len(context.targets)} target(s)")

            # Apply weapon enchantment onHit effects
            if primary_target.is_alive:
                self._apply_weapon_enchantment_effects(primary_target)

            # Track damage and loot
            total_damage = 0.0
            loot = []

            # Check for kills and grant rewards
            for target in context.targets:
                if not target.is_alive:
                    total_damage += effect_params.get("baseDamage", 0)
                    print(f"   💀 {target.definition.name} killed!")

                    # EXP reward
                    exp_reward = self._calculate_exp_reward(target)
                    self.character.leveling.add_exp(exp_reward)

                    # Auto-loot
                    target_loot = target.generate_loot()
                    if target_loot:
                        for material_id, quantity in target_loot:
                            self.character.inventory.add_item(material_id, quantity)
                            loot.extend(target_loot)

            return (total_damage, False, loot)

        except Exception as e:
            debug_print(f"⚠️  AoE attack failed: {e}")
            print(f"   ⚠️  Attack failed: {e}")
            return (0.0, False, [])

    def player_attack_enemy_with_tags(self, enemy: Enemy, tags: List[str], params: dict = None) -> Tuple[float, bool, List[Tuple[str, int]]]:
        """
        Player attacks enemy using tag-based effects system

        Args:
            enemy: Target enemy
            tags: Effect tags (e.g., ["physical", "single_target"] or ["fire", "circle", "burn"])
            params: Effect parameters (baseDamage, geometry params, status effects)

        Returns:
            (total_damage, any_crit, loot) where loot is empty if enemy didn't die
        """
        # Check for active devastate buffs (AoE attacks like Whirlwind Strike)
        # Must check BEFORE normal attack to trigger AoE
        if hasattr(self.character, 'buffs'):
            for buff in self.character.buffs.active_buffs:
                if buff.effect_type == "devastate" and buff.category in ["damage", "combat"]:
                    # Override tags with AoE geometry
                    print(f"\n🌀 DEVASTATE BUFF ACTIVE: {buff.name} (radius={int(buff.bonus_value)})")

                    # Build AoE tags - preserve damage type but add circle geometry
                    aoe_tags = []

                    # Keep damage type tags (physical, fire, etc.)
                    damage_types = ['physical', 'fire', 'ice', 'lightning', 'poison', 'arcane', 'shadow', 'holy', 'chaos']
                    for tag in tags:
                        if tag in damage_types:
                            aoe_tags.append(tag)

                    # Add AoE geometry
                    aoe_tags.append('circle')

                    # Set radius in params
                    aoe_params = params.copy() if params else {}
                    aoe_params['circle_radius'] = int(buff.bonus_value)

                    # Consume the buff BEFORE executing effect
                    self.character.buffs.consume_buffs_for_action("attack")

                    # Execute with AoE tags
                    return self._execute_tag_attack_aoe(enemy, aoe_tags, aoe_params)

        debug_print(f"⚔️  PLAYER TAG ATTACK: {enemy.definition.name} (HP: {enemy.current_health:.1f}/{enemy.max_health:.1f})")
        debug_print(f"   Using tags: {tags}")

        # Get all active enemies for geometry calculations
        all_enemies = self.get_all_active_enemies()
        alive_enemies = [e for e in all_enemies if e.is_alive]

        # Setup effect parameters
        effect_params = params.copy() if params else {}

        # Apply character stat bonuses to base damage
        if "baseDamage" in effect_params:
            base_damage = effect_params["baseDamage"]

            # Weapon damage
            weapon_damage = self.character.get_weapon_damage()
            if weapon_damage > 0:
                base_damage += weapon_damage

            # STR multiplier
            str_multiplier = 1.0 + (self.character.stats.strength * 0.05)
            base_damage *= str_multiplier

            # Title bonuses
            if hasattr(self.character, 'activity_tracker'):
                title_multiplier = 1.0 + self.character.activity_tracker.get_combat_bonus()
                base_damage *= title_multiplier

            # Skill buff bonuses (empower)
            if hasattr(self.character, 'buffs'):
                empower_damage = self.character.buffs.get_damage_bonus('damage')
                empower_combat = self.character.buffs.get_damage_bonus('combat')
                skill_bonus = max(empower_damage, empower_combat)
                if skill_bonus > 0:
                    base_damage *= (1.0 + skill_bonus)
                    print(f"   ⚡ Skill buff: +{skill_bonus*100:.0f}% damage")

            effect_params["baseDamage"] = base_damage
            print(f"   Base damage (with bonuses): {base_damage:.1f}")

        # Execute effect using tag system
        try:
            context = self.effect_executor.execute_effect(
                source=self.character,
                primary_target=enemy,
                tags=tags,
                params=effect_params,
                available_entities=alive_enemies
            )

            print(f"   ✓ Affected {len(context.targets)} target(s)")

            # Get equipped weapon for enchantments
            equipped_weapon = None
            if hasattr(self.character, '_selected_slot') and self.character._selected_slot:
                equipped_weapon = self.character.equipment.slots.get(self.character._selected_slot)
            else:
                equipped_weapon = self.character.equipment.slots.get('mainHand')

            # LIFESTEAL ENCHANTMENT: Heal based on damage dealt (before enemy dies check)
            final_damage = effect_params.get("baseDamage", 0)
            if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
                for ench in equipped_weapon.enchantments:
                    effect = ench.get('effect', {})
                    if effect.get('type') == 'lifesteal':
                        lifesteal_percent = min(effect.get('value', 0.1), 0.50)  # 10% default, 50% cap
                        heal_amount = final_damage * lifesteal_percent
                        old_health = self.character.health
                        self.character.health = min(self.character.max_health, self.character.health + heal_amount)
                        new_health = self.character.health
                        print(f"   💚 LIFESTEAL ENCHANT ({lifesteal_percent*100:.0f}%, capped at 50%): Healed {heal_amount:.1f} HP")
                        print(f"      HP: {old_health:.1f} → {new_health:.1f}")

            # Consume any consume-on-use buffs (Power Strike, etc.)
            if hasattr(self.character, 'buffs'):
                self.character.buffs.consume_buffs_for_action("attack")

            # Apply weapon enchantment onHit effects (Fire Aspect, etc.)
            if enemy.is_alive:
                self._apply_weapon_enchantment_effects(enemy)

            # Track damage dealt
            total_damage = 0.0
            enemy_died = False

            # Check if primary enemy died
            if not enemy.is_alive:
                enemy_died = True
                total_damage += final_damage

            # Initialize loot
            loot = []

            # Grant EXP and loot if killed
            if enemy_died:
                print(f"   💀 Enemy killed!")
                exp_reward = self._calculate_exp_reward(enemy)
                self.character.leveling.add_exp(exp_reward)
                print(f"   +{exp_reward} EXP")

                # Auto-loot
                loot = enemy.generate_loot()
                if loot:
                    print(f"   💰 Auto-looting {len(loot)} item type(s):")
                    for material_id, quantity in loot:
                        success = self.character.inventory.add_item(material_id, quantity)
                        if success:
                            print(f"      +{quantity}x {material_id}")
                        else:
                            print(f"      ⚠️ Inventory full! Could not add {quantity}x {material_id}")

                # Track combat activity
                if hasattr(self.character, 'activity_tracker'):
                    self.character.activity_tracker.record_activity('combat', 1)

                # Execute on-kill triggers
                self._execute_triggers('on_kill', target=enemy, hand='mainHand')
            else:
                print(f"   Enemy HP remaining: {enemy.current_health:.1f}/{enemy.max_health:.1f}")

            # Update combat state
            self.player_last_combat_time = 0.0
            self.player_in_combat = True

            # Apply weapon durability loss (for tag-based attacks)
            equipped_weapon = None
            if hasattr(self.character, '_selected_slot') and self.character._selected_slot:
                equipped_weapon = self.character.equipment.slots.get(self.character._selected_slot)
            else:
                equipped_weapon = self.character.equipment.slots.get('mainHand')

            if equipped_weapon and hasattr(equipped_weapon, 'durability_current'):
                from core.config import Config
                if not Config.DEBUG_INFINITE_DURABILITY:
                    # Determine if using tool as weapon (improper use)
                    tool_type_effectiveness = self.character.get_tool_effectiveness_for_action(equipped_weapon, 'combat')
                    durability_loss = 1 if tool_type_effectiveness >= 1.0 else 2
                    equipped_weapon.durability_current = max(0, equipped_weapon.durability_current - durability_loss)

                    # Only warn about improper use, low, or broken
                    if durability_loss == 2:
                        print(f"   ⚠️ Improper use! {equipped_weapon.name} loses {durability_loss} durability ({equipped_weapon.durability_current}/{equipped_weapon.durability_max})")
                    elif equipped_weapon.durability_current == 0:
                        print(f"   💥 {equipped_weapon.name} has broken! (0/{equipped_weapon.durability_max})")
                    elif equipped_weapon.durability_current <= equipped_weapon.durability_max * 0.2:
                        print(f"   ⚠️ {equipped_weapon.name} durability low: {equipped_weapon.durability_current}/{equipped_weapon.durability_max}")

            # NEW: Comprehensive stat tracking
            if hasattr(self.character, 'stat_tracker'):
                # Determine damage type from tags
                damage_types = ['physical', 'fire', 'ice', 'lightning', 'poison', 'arcane', 'shadow', 'holy']
                damage_type = next((tag for tag in tags if tag in damage_types), 'physical')

                # Determine attack type (melee/ranged/magic)
                attack_type = 'magic' if 'magic' in tags or damage_type in ['arcane', 'holy'] else 'melee'

                # Get weapon element if equipped
                weapon_element = None
                if equipped_weapon and hasattr(equipped_weapon, 'tags'):
                    for tag in damage_types:
                        if tag in equipped_weapon.tags:
                            weapon_element = tag
                            break

                # Track damage dealt
                if final_damage > 0:
                    self.character.stat_tracker.record_damage_dealt(
                        amount=final_damage,
                        damage_type=damage_type,
                        attack_type=attack_type,
                        was_crit=context.any_crit if hasattr(context, 'any_crit') else False,
                        weapon_element=weapon_element
                    )

                # Track enemy kill
                if enemy_died:
                    self.character.stat_tracker.record_enemy_killed(
                        tier=enemy.definition.tier,
                        is_boss=enemy.definition.is_boss,
                        is_dragon='dragon' in enemy.definition.enemy_id.lower(),
                        weapon_element=weapon_element
                    )

                # Track status effects applied
                status_effect_tags = ['burn', 'freeze', 'poison', 'stun', 'root', 'slow', 'bleed', 'shock', 'weaken', 'vulnerable']
                for tag in tags:
                    if tag in status_effect_tags:
                        self.character.stat_tracker.record_status_effect(tag, applied_to_enemy=True)

            # Tag-based attacks don't use traditional crit system (handled by tags)
            return (total_damage, False, loot)

        except Exception as e:
            self.debugger.error(f"Tag-based attack failed: {e}")
            print(f"   ⚠ Tag attack failed: {e}")
            # Fall back to 0 damage on error
            return (0.0, False, [])

    def _enemy_attack_player(self, enemy: Enemy, shield_blocking: bool = False):
        """Enemy attacks player
        shield_blocking: True if player is actively blocking with shield (right mouse held)
        """
        print(f"\n👹 ENEMY ATTACK: {enemy.definition.name}")

        # Calculate damage
        damage = enemy.perform_attack()
        print(f"   Base damage: {damage:.1f}")

        # Calculate damage reduction
        defense_stat = self.character.stats.defense

        # Apply weaken status to player defense
        if hasattr(self.character, 'status_manager'):
            weaken_effect = self.character.status_manager._find_effect('weaken')
            if weaken_effect:
                stat_reduction = weaken_effect.params.get('stat_reduction', 0.25)
                affected_stats = weaken_effect.params.get('affected_stats', ['damage', 'defense'])

                if 'defense' in affected_stats:
                    defense_stat *= (1.0 - stat_reduction)
                    print(f"   ⚠️ WEAKENED: Defense reduced by {stat_reduction*100:.0f}%")

        def_multiplier = 1.0 - (defense_stat * 0.02)
        print(f"   DEF multiplier: {def_multiplier:.2f} (DEF: {defense_stat:.1f})")

        # Armor bonus from equipment
        armor_bonus = 0.0
        if hasattr(self.character, 'equipment'):
            armor_bonus = self.character.equipment.get_total_defense()
        print(f"   Armor bonus: {armor_bonus}")

        armor_multiplier = 1.0 - (armor_bonus * 0.01)

        # PROTECTION ENCHANTMENTS: Apply defense_multiplier enchantments
        protection_reduction = 0.0
        if hasattr(self.character, 'equipment'):
            armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
            for slot in armor_slots:
                armor_piece = self.character.equipment.slots.get(slot)
                if armor_piece and hasattr(armor_piece, 'enchantments'):
                    for ench in armor_piece.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'defense_multiplier':
                            protection_reduction += effect.get('value', 0.0)

        if protection_reduction > 0:
            print(f"   🛡️ Protection enchantments: -{protection_reduction*100:.0f}% damage reduction")

        protection_multiplier = 1.0 - protection_reduction

        # Apply multipliers
        final_damage = damage * def_multiplier * armor_multiplier * protection_multiplier

        # SHIELD BLOCKING: Apply shield damage reduction if actively blocking
        if shield_blocking and self.character.is_shield_active():
            shield_reduction = self.character.get_shield_damage_reduction()
            final_damage = final_damage * (1.0 - shield_reduction)
            print(f"   🛡️ Shield blocking: -{shield_reduction*100:.0f}% damage reduction")

        # SKILL BUFF BONUSES: Check for fortify buffs (flat damage reduction)
        fortify_reduction = 0.0
        if hasattr(self.character, 'buffs'):
            fortify_reduction = self.character.buffs.get_defense_bonus()

            if fortify_reduction > 0:
                final_damage = max(0, final_damage - fortify_reduction)
                print(f"   ⚡ Fortify buff: -{fortify_reduction:.1f} flat damage reduction")

        final_damage = max(1, final_damage)  # Minimum 1 damage
        print(f"   ➜ Final damage to player: {final_damage:.1f}")

        # Apply to player
        self.character.take_damage(final_damage, from_attack=True)
        print(f"   Player HP: {self.character.health:.1f}/{self.character.max_health:.1f}")

        # NEW: Track damage taken
        if hasattr(self.character, 'stat_tracker'):
            # Determine damage type from enemy (default to physical)
            enemy_damage_type = getattr(enemy.definition, 'damage_type', 'physical')
            enemy_attack_type = 'melee'  # Most enemies are melee by default

            self.character.stat_tracker.record_damage_taken(
                amount=final_damage,
                damage_type=enemy_damage_type,
                attack_type=enemy_attack_type
            )

        # REFLECT/THORNS: Check for reflect damage on armor (capped at 80%)
        if hasattr(self.character, 'equipment') and enemy.is_alive:
            reflect_percent = 0.0
            armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
            thorns_pieces = []

            for slot in armor_slots:
                armor_piece = self.character.equipment.slots.get(slot)
                if armor_piece and hasattr(armor_piece, 'enchantments'):
                    for ench in armor_piece.enchantments:
                        effect = ench.get('effect', {})
                        ench_type = effect.get('type', 'unknown')
                        ench_value = effect.get('value', 0.0)

                        # Check for all reflect/thorns variants (reflect_damage is the actual type in JSON)
                        if ench_type in ['reflect', 'thorns', 'reflect_damage']:
                            piece_value = ench_value
                            reflect_percent += piece_value
                            thorns_pieces.append(f"{slot}({piece_value*100:.0f}%)")

            # Cap total reflect at 80%
            uncapped = reflect_percent
            reflect_percent = min(reflect_percent, 0.80)

            if reflect_percent > 0:
                reflect_damage = final_damage * reflect_percent
                old_enemy_health = enemy.current_health
                enemy.current_health -= reflect_damage
                cap_indicator = f" [capped from {uncapped*100:.0f}%]" if uncapped > 0.80 else ""
                print(f"   ⚡ THORNS ({reflect_percent*100:.0f}%{cap_indicator}): Reflected {reflect_damage:.1f} damage to {enemy.definition.name}")
                print(f"      Sources: {', '.join(thorns_pieces)}")
                print(f"      Enemy HP: {old_enemy_health:.1f} → {enemy.current_health:.1f}")

                if enemy.current_health <= 0:
                    enemy.is_alive = False
                    enemy.current_health = 0
                    print(f"   💀 {enemy.definition.name} killed by thorns damage!")

        # Reset health regen timer (damage taken)
        self.character.time_since_last_damage_taken = 0.0

        # Update combat state
        self.player_last_combat_time = 0.0
        self.player_in_combat = True

    def _calculate_exp_reward(self, enemy: Enemy) -> int:
        """Calculate EXP reward for killing enemy"""
        tier = enemy.definition.tier
        tier_key = f"tier{tier}"
        base_exp = self.config.exp_rewards.get(tier_key, 100)

        # Boss multiplier
        if enemy.is_boss:
            base_exp *= self.config.boss_multiplier

        return int(base_exp)

    def _update_player_combat_state(self, dt: float):
        """Track if player is in combat (for health regen)"""
        if self.player_in_combat:
            self.player_last_combat_time += dt
            if self.player_last_combat_time >= self.config.combat_timeout:
                self.player_in_combat = False

    def get_enemies_in_range(self, position: Tuple[float, float], radius: float) -> List[Enemy]:
        """Get all living enemies within radius of position"""
        result = []
        for enemy_list in self.enemies.values():
            for enemy in enemy_list:
                if enemy.is_alive:
                    dist = math.sqrt(
                        (enemy.position[0] - position[0]) ** 2 +
                        (enemy.position[1] - position[1]) ** 2
                    )
                    if dist <= radius:
                        result.append(enemy)
        return result

    def get_enemy_at_position(self, position: Tuple[float, float], tolerance: float = 0.7) -> Optional[Enemy]:
        """Get enemy at or near a position (for clicking)"""
        for enemy_list in self.enemies.values():
            for enemy in enemy_list:
                if enemy.is_alive:
                    dist = math.sqrt(
                        (enemy.position[0] - position[0]) ** 2 +
                        (enemy.position[1] - position[1]) ** 2
                    )
                    if dist <= tolerance:
                        return enemy
        return None

    def get_corpse_at_position(self, position: Tuple[float, float], tolerance: float = 0.7) -> Optional[Enemy]:
        """Get corpse at or near a position (for looting)"""
        for corpse in self.corpses:
            dist = math.sqrt(
                (corpse.position[0] - position[0]) ** 2 +
                (corpse.position[1] - position[1]) ** 2
            )
            if dist <= tolerance:
                return corpse
        return None

    def loot_corpse(self, corpse: Enemy, player_inventory) -> List[Tuple[str, int]]:
        """Loot a corpse and add items to player inventory"""
        loot = corpse.generate_loot()

        # Add to inventory
        for material_id, quantity in loot:
            player_inventory.add_material(material_id, quantity)

        # Remove corpse
        if corpse in self.corpses:
            self.corpses.remove(corpse)

        # Remove from enemies list
        for chunk_coords, enemy_list in self.enemies.items():
            if corpse in enemy_list:
                enemy_list.remove(corpse)
                break

        return loot

    def _execute_triggers(self, trigger_type: str, target: Enemy = None, hand: str = 'mainHand'):
        """
        Execute trigger-based effects from equipment

        Args:
            trigger_type: Type of trigger ('on_kill', 'on_crit', 'on_hit', etc.)
            target: Target entity (if applicable)
            hand: Which hand to check for triggers
        """
        # Get weapon
        weapon = self.character.equipment.slots.get(hand)
        if not weapon:
            return

        # Check weapon enchantments for triggers
        if hasattr(weapon, 'enchantments'):
            for ench in weapon.enchantments:
                metadata_tags = ench.get('metadata_tags', [])

                # Check if this enchantment has the trigger
                if trigger_type in metadata_tags:
                    print(f"   🎯 TRIGGER! {trigger_type.upper()} effect: {ench.get('name', 'Unknown')}")

                    # Execute the enchantment effect
                    effect = ench.get('effect', {})
                    effect_type = effect.get('type', '')

                    # Handle different trigger effect types
                    if effect_type == 'heal_on_kill' and trigger_type == 'on_kill':
                        heal_amount = effect.get('value', 10.0)
                        self.character.heal(heal_amount)
                        print(f"      💚 Healed {heal_amount:.1f} HP")

                    elif effect_type == 'explosion' and trigger_type == 'on_kill':
                        # Would trigger an AOE explosion effect
                        print(f"      💥 Explosion effect (not fully implemented)")

                    elif effect_type == 'bonus_damage' and trigger_type == 'on_crit':
                        # Bonus damage on crit (would need to be integrated into damage calculation)
                        print(f"      ⚔️ Bonus damage on crit (not fully implemented)")

                    # Add more trigger effect types as needed

    def get_all_active_enemies(self) -> List[Enemy]:
        """Get all enemies (for rendering)"""
        all_enemies = []
        for enemy_list in self.enemies.values():
            all_enemies.extend(enemy_list)
        return all_enemies
