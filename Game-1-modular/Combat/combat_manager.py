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
from core.effect_executor import get_effect_executor
from core.tag_debug import get_tag_debugger


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

        # Active enemies by chunk
        self.enemies: Dict[Tuple[int, int], List[Enemy]] = {}

        # Spawn tracking
        self.spawn_timers: Dict[Tuple[int, int], float] = {}

        # Corpses (enemies waiting to be looted)
        self.corpses: List[Enemy] = []

        # Combat state
        self.player_last_combat_time = 0.0
        self.player_in_combat = False

    def load_config(self, config_path: str, enemies_path: str):
        """Load combat configuration and enemy definitions"""
        self.config.load_from_file(config_path)
        self.enemy_db.load_from_file(enemies_path)

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

    def spawn_enemies_in_chunk(self, chunk, initial_spawn=False):
        """Spawn enemies in a chunk based on its danger level"""
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

        # Spawn enemies
        for _ in range(to_spawn):
            # Pick tier based on weights, filtered by danger level restrictions
            tier_weights = spawn_config.get('tierWeights', {'tier1': 1.0})
            filtered_weights = self._filter_tier_weights_for_danger(tier_weights, danger_level)
            tier = self._pick_weighted_tier(filtered_weights)

            # Get random enemy of that tier
            enemy_def = self.enemy_db.get_random_enemy(tier)
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
                    special_ability = enemy.can_use_special_ability()
                    if special_ability:
                        # Use special ability if in range
                        dist = enemy.distance_to(player_pos)
                        # Special abilities have varied ranges, use aggro range as max
                        if dist <= enemy.definition.aggro_range:
                            enemy.use_special_ability(special_ability, self.character, [self.character])

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

    def player_attack_enemy(self, enemy: Enemy, hand: str = 'mainHand') -> Tuple[float, bool, List[Tuple[str, int]]]:
        """
        Calculate player damage to enemy
        Returns (damage, is_crit, loot) where loot is empty list if enemy didn't die
        hand: 'mainHand' or 'offHand' to specify which hand is attacking
        """
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

        return (final_damage, is_crit, loot)

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
        print(f"\n⚔️ PLAYER TAG ATTACK: {enemy.definition.name} (HP: {enemy.current_health:.1f}/{enemy.max_health:.1f})")
        print(f"   Using tags: {tags}")

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

            # Track damage dealt
            total_damage = 0.0
            enemy_died = False

            # Check if primary enemy died
            if not enemy.is_alive:
                enemy_died = True
                total_damage += effect_params.get("baseDamage", 0)  # Rough estimate

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
            else:
                print(f"   Enemy HP remaining: {enemy.current_health:.1f}/{enemy.max_health:.1f}")

            # Update combat state
            self.player_last_combat_time = 0.0
            self.player_in_combat = True

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
        def_multiplier = 1.0 - (self.character.stats.defense * 0.02)
        print(f"   DEF multiplier: {def_multiplier:.2f} (DEF: {self.character.stats.defense})")

        # Armor bonus from equipment
        armor_bonus = 0.0
        if hasattr(self.character, 'equipment'):
            armor_bonus = self.character.equipment.get_total_defense()
        print(f"   Armor bonus: {armor_bonus}")

        armor_multiplier = 1.0 - (armor_bonus * 0.01)

        # Apply multipliers
        final_damage = damage * def_multiplier * armor_multiplier

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
        self.character.take_damage(final_damage)
        print(f"   Player HP: {self.character.health:.1f}/{self.character.max_health:.1f}")

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

    def get_all_active_enemies(self) -> List[Enemy]:
        """Get all enemies (for rendering)"""
        all_enemies = []
        for enemy_list in self.enemies.values():
            all_enemies.extend(enemy_list)
        return all_enemies
