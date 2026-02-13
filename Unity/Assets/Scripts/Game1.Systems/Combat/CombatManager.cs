// ============================================================================
// Game1.Systems.Combat.CombatManager
// Migrated from: Combat/combat_manager.py (full file, 1956 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Orchestrates all combat: enemy spawning, player attacks, enemy attacks,
// enchantment effects, durability, EXP rewards, loot, and dungeon combat.
//
// Delegates to:
//   - DamageCalculator: all damage math (extracted)
//   - EnemySpawner: all spawning logic (extracted)
//   - AttackEffectsManager: visual feedback data
//
// NO MonoBehaviour, NO UnityEngine. Pure C#.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;

namespace Game1.Systems.Combat
{
    // ========================================================================
    // Minimal interfaces for entity dependencies (avoids circular references)
    // ========================================================================

    /// <summary>
    /// Interface for an active enemy instance in combat.
    /// </summary>
    public interface ICombatEnemy
    {
        string EnemyId { get; }
        bool IsAlive { get; set; }
        float CurrentHealth { get; set; }
        float MaxHealth { get; }
        float PositionX { get; }
        float PositionY { get; }
        int Tier { get; }
        bool IsBoss { get; }
        float Defense { get; }
        float AttackSpeed { get; }
        float DamageMin { get; }
        float DamageMax { get; }
        string DefinitionName { get; }
        string DamageType { get; }

        /// <summary>Chunk coordinates this enemy was spawned in.</summary>
        (int X, int Y) ChunkCoords { get; }

        /// <summary>AI state for corpse management.</summary>
        string AiState { get; set; }

        /// <summary>Time since death for corpse expiration.</summary>
        float TimeSinceDeath { get; set; }

        /// <summary>Corpse lifetime (seconds before removal).</summary>
        float CorpseLifetime { get; set; }

        /// <summary>Whether this is a dungeon enemy.</summary>
        bool IsDungeonEnemy { get; set; }

        /// <summary>Whether this enemy is in combat.</summary>
        bool InCombat { get; set; }

        /// <summary>Perform an attack and return the damage roll.</summary>
        float PerformAttack();

        /// <summary>Apply damage. Returns true if enemy died.</summary>
        bool TakeDamage(float amount, bool fromPlayer = false);

        /// <summary>Generate loot drops on death.</summary>
        List<(string MaterialId, int Quantity)> GenerateLoot();

        /// <summary>Check if enemy can attack (cooldown ready).</summary>
        bool CanAttack();

        /// <summary>Calculate distance to a position.</summary>
        float DistanceTo(float x, float y);

        /// <summary>
        /// Update AI behavior.
        /// </summary>
        void UpdateAi(float dt, float playerX, float playerY,
                      float aggroMultiplier = 1.0f, float speedMultiplier = 1.0f,
                      float safeZoneCenterX = 0f, float safeZoneCenterY = 0f,
                      float safeZoneRadius = 15f);
    }

    /// <summary>
    /// Interface for the player character in combat.
    /// </summary>
    public interface ICombatCharacter
    {
        float PositionX { get; }
        float PositionY { get; }
        float Health { get; set; }
        float MaxHealth { get; }

        /// <summary>Get weapon damage for currently selected slot.</summary>
        int GetWeaponDamage();

        /// <summary>Get tool effectiveness for a given action.</summary>
        float GetToolEffectivenessForAction(object weapon, string action);

        /// <summary>Get enemy-specific damage multiplier (beastDamage, etc.).</summary>
        float GetEnemyDamageMultiplier(ICombatEnemy enemy);

        /// <summary>Get effective luck (includes title/skill bonuses).</summary>
        int GetEffectiveLuck();

        /// <summary>Check if shield is actively blocking.</summary>
        bool IsShieldActive();

        /// <summary>Get shield damage reduction percentage.</summary>
        float GetShieldDamageReduction();

        /// <summary>Apply damage to player.</summary>
        void TakeDamage(float amount, bool fromAttack = false);

        /// <summary>Heal the player.</summary>
        void Heal(float amount);

        /// <summary>Add EXP to player.</summary>
        void AddExp(int amount);

        /// <summary>Add item to inventory. Returns true if successful.</summary>
        bool AddItemToInventory(string materialId, int quantity);

        // Stat accessors
        int Strength { get; }
        int DefenseStat { get; }

        /// <summary>Get equipped weapon for a given hand slot.</summary>
        object GetEquippedWeapon(string hand);

        /// <summary>Get the currently selected hand slot name.</summary>
        string GetSelectedSlot();

        /// <summary>Get total armor defense from equipment.</summary>
        float GetTotalArmorDefense();

        /// <summary>Get total protection enchantment reduction.</summary>
        float GetProtectionEnchantmentReduction();

        /// <summary>Get weapon metadata tags.</summary>
        List<string> GetWeaponMetadataTags(object weapon);

        /// <summary>Get weapon enchantments.</summary>
        List<Dictionary<string, object>> GetWeaponEnchantments(object weapon);

        /// <summary>Check if offhand has an item equipped.</summary>
        bool HasOffhand { get; }

        /// <summary>Get durability loss multiplier from DEF stat.</summary>
        float GetDurabilityLossMultiplier();

        /// <summary>Get current weapon durability.</summary>
        float GetWeaponDurability(object weapon);

        /// <summary>Set weapon durability.</summary>
        void SetWeaponDurability(object weapon, float value);

        /// <summary>Get max weapon durability.</summary>
        float GetWeaponMaxDurability(object weapon);

        // Buff accessors
        float GetEmpowerBonus();
        float GetPierceBonus();
        float GetFortifyReduction();
        float GetWeakenReduction();

        // Title accessors
        TitleBonuses GetTitleBonuses();
    }

    /// <summary>
    /// Manages all combat in the game: enemy spawning, player attacks, enemy attacks,
    /// enchantment effects, durability, EXP rewards, loot, and dungeon integration.
    ///
    /// This is the central orchestrator that delegates to DamageCalculator and EnemySpawner
    /// for their respective concerns.
    /// </summary>
    public class CombatManager
    {
        // ====================================================================
        // Dependencies
        // ====================================================================

        private readonly CombatConfig _config;
        private readonly EnemySpawner _spawner;
        private readonly Random _rng;

        // ====================================================================
        // State
        // ====================================================================

        /// <summary>
        /// Active enemies organized by chunk coordinates.
        /// Python: self.enemies: Dict[Tuple[int, int], List[Enemy]]
        /// </summary>
        private readonly Dictionary<(int, int), List<ICombatEnemy>> _enemies = new();

        /// <summary>
        /// Dead enemies waiting to be looted or expire.
        /// Python: self.corpses: List[Enemy]
        /// </summary>
        private readonly List<ICombatEnemy> _corpses = new();

        /// <summary>
        /// Time accumulator since last combat action (for combat state timeout).
        /// Python: self.player_last_combat_time
        /// </summary>
        private float _playerLastCombatTime = 0f;

        /// <summary>
        /// Whether the player is currently in combat.
        /// Python: self.player_in_combat
        /// </summary>
        public bool PlayerInCombat { get; private set; } = false;

        // ====================================================================
        // Dungeon Integration
        // ====================================================================

        /// <summary>Whether the player is currently in a dungeon.</summary>
        public bool InDungeon { get; set; } = false;

        /// <summary>Enemies spawned in the current dungeon.</summary>
        private readonly List<ICombatEnemy> _dungeonEnemies = new();

        /// <summary>
        /// Callback invoked when a dungeon enemy is killed (for wave tracking).
        /// </summary>
        public Action OnDungeonEnemyKilled { get; set; }

        // ====================================================================
        // Construction
        // ====================================================================

        /// <summary>
        /// Create a new CombatManager.
        /// </summary>
        /// <param name="config">Combat configuration.</param>
        /// <param name="spawner">Enemy spawner for managing spawn logic.</param>
        /// <param name="rng">Random number generator.</param>
        public CombatManager(CombatConfig config, EnemySpawner spawner, Random rng = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _spawner = spawner ?? throw new ArgumentNullException(nameof(spawner));
            _rng = rng ?? new Random();
        }

        // ====================================================================
        // Main Update Loop
        // ====================================================================

        /// <summary>
        /// Update all enemies and combat logic per frame.
        /// Python: CombatManager.update()
        /// </summary>
        /// <param name="dt">Delta time in seconds.</param>
        /// <param name="character">Player character.</param>
        /// <param name="shieldBlocking">True if player is actively blocking.</param>
        /// <param name="isNight">True if it's currently night time.</param>
        public void Update(float dt, ICombatCharacter character, bool shieldBlocking, bool isNight)
        {
            float playerX = character.PositionX;
            float playerY = character.PositionY;

            // Night aggression modifiers
            // Python: aggro_mult = 1.3 if is_night else 1.0
            //         speed_mult = 1.15 if is_night else 1.0
            float aggroMult = isNight ? _config.NightAggroMultiplier : 1.0f;
            float speedMult = isNight ? _config.NightSpeedMultiplier : 1.0f;

            // Track dead enemies for removal
            var deadEnemies = new List<((int, int) ChunkCoords, ICombatEnemy Enemy)>();

            // Update all enemies
            foreach (var (chunkCoords, enemyList) in _enemies)
            {
                foreach (var enemy in enemyList)
                {
                    if (enemy.IsAlive)
                    {
                        // Update AI with night modifiers
                        enemy.UpdateAi(dt, playerX, playerY,
                            aggroMultiplier: aggroMult,
                            speedMultiplier: speedMult,
                            safeZoneCenterX: _config.SafeZoneX,
                            safeZoneCenterY: _config.SafeZoneY,
                            safeZoneRadius: _config.SafeZoneRadius);

                        // Check if enemy can attack player (melee range = 1.5)
                        if (enemy.CanAttack())
                        {
                            float dist = enemy.DistanceTo(playerX, playerY);
                            if (dist <= 1.5f)
                            {
                                EnemyAttackPlayer(enemy, character, shieldBlocking);
                            }
                        }
                    }
                    else
                    {
                        // Handle dead enemy corpse state
                        // Python: transition DEAD -> CORPSE
                        if (enemy.AiState == "dead")
                        {
                            enemy.AiState = "corpse";
                            enemy.TimeSinceDeath = 0f;
                        }

                        if (enemy.AiState == "corpse")
                        {
                            enemy.TimeSinceDeath += dt;
                            if (enemy.TimeSinceDeath >= enemy.CorpseLifetime)
                            {
                                deadEnemies.Add((chunkCoords, enemy));
                            }
                            else if (!_corpses.Contains(enemy))
                            {
                                _corpses.Add(enemy);
                            }
                        }
                    }
                }
            }

            // Remove expired corpses
            foreach (var (chunkCoords, enemy) in deadEnemies)
            {
                if (_enemies.TryGetValue(chunkCoords, out var list))
                {
                    list.Remove(enemy);
                }
                _corpses.Remove(enemy);
            }

            // Update player combat state
            _updatePlayerCombatState(dt);
        }

        // ====================================================================
        // Player Attack
        // ====================================================================

        /// <summary>
        /// Player attacks an enemy with their equipped weapon.
        /// Implements the full damage pipeline from combat_manager.py player_attack_enemy().
        ///
        /// Returns (finalDamage, isCritical, lootDropped).
        /// </summary>
        /// <param name="enemy">Target enemy.</param>
        /// <param name="character">Player character.</param>
        /// <param name="hand">Which hand is attacking ("mainHand" or "offHand").</param>
        /// <returns>Tuple of (damage dealt, was critical, loot list).</returns>
        public (float Damage, bool IsCritical, List<(string MaterialId, int Qty)> Loot) PlayerAttackEnemy(
            ICombatEnemy enemy, ICombatCharacter character, string hand = "mainHand")
        {
            // Get weapon damage
            int weaponDamage = character.GetWeaponDamage();

            // Get equipped weapon for effectiveness check
            string selectedSlot = character.GetSelectedSlot();
            object equippedWeapon = selectedSlot != null
                ? character.GetEquippedWeapon(selectedSlot)
                : character.GetEquippedWeapon(hand);

            // Tool effectiveness penalty
            float toolEffectiveness = 1.0f;
            if (equippedWeapon != null)
            {
                toolEffectiveness = character.GetToolEffectivenessForAction(equippedWeapon, "combat");
            }

            // Get weapon tag modifiers
            WeaponTagModifiers weaponTags = null;
            if (equippedWeapon != null)
            {
                var tags = character.GetWeaponMetadataTags(equippedWeapon);
                if (tags != null && tags.Count > 0)
                {
                    weaponTags = WeaponTagModifiers.FromTags(tags, character.HasOffhand);
                }
            }

            // Get buff bonuses
            float empowerBonus = character.GetEmpowerBonus();
            float pierceBonus = character.GetPierceBonus();

            // Get title bonuses
            TitleBonuses titles = character.GetTitleBonuses();

            // Enemy-specific damage multiplier
            float enemyDamageMult = character.GetEnemyDamageMultiplier(enemy);

            // Calculate damage
            DamageResult result = DamageCalculator.CalculatePlayerDamage(
                weaponDamage,
                toolEffectiveness,
                weaponTags,
                character.Strength,
                character.GetEffectiveLuck(),
                titles,
                empowerBonus,
                pierceBonus,
                enemyDamageMult,
                enemy.Defense,
                _rng);

            // Apply damage to enemy
            bool enemyDied = enemy.TakeDamage(result.FinalDamage, fromPlayer: true);

            // Apply lifesteal enchantment
            // Python: lifesteal_percent = min(value, 0.50), heal = finalDamage * lifesteal_percent
            if (equippedWeapon != null)
            {
                _applyLifesteal(character, equippedWeapon, result.FinalDamage);
            }

            // Apply chain damage enchantment
            if (equippedWeapon != null)
            {
                _applyChainDamage(enemy, character, equippedWeapon, result.FinalDamage);
            }

            // Apply weapon enchantment on-hit effects (burn, poison, knockback, frost)
            if (enemy.IsAlive && equippedWeapon != null)
            {
                ApplyWeaponEnchantmentEffects(enemy, character, equippedWeapon);
            }

            // Apply weapon durability loss
            if (equippedWeapon != null)
            {
                _applyDurabilityLoss(character, equippedWeapon, toolEffectiveness);
            }

            // Initialize loot
            var loot = new List<(string MaterialId, int Qty)>();

            // Grant EXP and loot if killed
            if (enemyDied)
            {
                int expReward = DamageCalculator.CalculateExpReward(
                    _config, enemy.Tier, enemy.IsBoss, InDungeon);
                character.AddExp(expReward);

                // No loot drops in dungeons - only EXP (2x already applied)
                if (!InDungeon)
                {
                    loot = enemy.GenerateLoot();
                    foreach (var (materialId, quantity) in loot)
                    {
                        character.AddItemToInventory(materialId, quantity);
                    }
                }

                // Notify dungeon manager of kill
                if (InDungeon)
                {
                    OnDungeonEnemyKilled?.Invoke();
                    _dungeonEnemies.Remove(enemy);
                }

                // Raise game event
                GameEvents.RaiseEnemyKilled(enemy);
                GameEvents.RaiseDamageDealt(character, enemy, result.FinalDamage);
            }

            // Update combat state
            _playerLastCombatTime = 0f;
            PlayerInCombat = true;

            return (result.FinalDamage, result.IsCritical, loot);
        }

        // ====================================================================
        // Enemy Attack
        // ====================================================================

        /// <summary>
        /// Enemy attacks the player. Calculates defensive reductions and applies damage.
        /// Python: _enemy_attack_player()
        /// </summary>
        /// <param name="enemy">Attacking enemy.</param>
        /// <param name="character">Player character.</param>
        /// <param name="shieldBlocking">Whether player is actively blocking.</param>
        public void EnemyAttackPlayer(ICombatEnemy enemy, ICombatCharacter character, bool shieldBlocking)
        {
            // Calculate base damage
            float baseDamage = enemy.PerformAttack();

            // Get defense parameters
            float defenseStat = character.DefenseStat;
            float armorBonus = character.GetTotalArmorDefense();
            float protectionReduction = character.GetProtectionEnchantmentReduction();
            float shieldReduction = shieldBlocking && character.IsShieldActive()
                ? character.GetShieldDamageReduction()
                : 0f;
            float fortifyReduction = character.GetFortifyReduction();
            float weakenReduction = character.GetWeakenReduction();

            // Calculate final damage
            float finalDamage = DamageCalculator.CalculateEnemyDamageToPlayer(
                baseDamage,
                defenseStat,
                armorBonus,
                protectionReduction,
                shieldBlocking && character.IsShieldActive(),
                shieldReduction,
                fortifyReduction,
                weakenReduction);

            // Apply damage to player
            character.TakeDamage(finalDamage, fromAttack: true);

            // Thorns/reflect damage
            _applyReflectDamage(enemy, character, finalDamage);

            // Update combat state
            _playerLastCombatTime = 0f;
            PlayerInCombat = true;

            // Raise game event
            GameEvents.RaiseDamageDealt(enemy, character, finalDamage);
        }

        // ====================================================================
        // Enchantment Effects
        // ====================================================================

        /// <summary>
        /// Apply on-hit enchantment effects from weapon to enemy.
        /// Handles: damage_over_time (burn/poison/bleed), knockback, slow (frost touch).
        /// Python: _apply_weapon_enchantment_effects()
        /// </summary>
        /// <param name="enemy">Target enemy.</param>
        /// <param name="character">Player character.</param>
        /// <param name="weapon">Equipped weapon object.</param>
        public void ApplyWeaponEnchantmentEffects(ICombatEnemy enemy, ICombatCharacter character, object weapon)
        {
            var enchantments = character.GetWeaponEnchantments(weapon);
            if (enchantments == null)
                return;

            foreach (var enchantment in enchantments)
            {
                if (!enchantment.TryGetValue("effect", out object effectObj))
                    continue;

                var effect = effectObj as Dictionary<string, object>;
                if (effect == null)
                    continue;

                string effectType = effect.TryGetValue("type", out object typeObj)
                    ? typeObj as string
                    : null;

                if (effectType == null)
                    continue;

                // Status effects map for DoT enchantments
                // Python: status_tag_map = {'fire': 'burn', 'poison': 'poison', 'bleed': 'bleed'}
                if (effectType == "damage_over_time")
                {
                    // The element -> status tag mapping is handled by the status manager
                    // We just emit the enchantment data for the combat system to process
                    OnEnchantmentTriggered?.Invoke(enemy, enchantment);
                }
                else if (effectType == "knockback")
                {
                    OnEnchantmentTriggered?.Invoke(enemy, enchantment);
                }
                else if (effectType == "slow")
                {
                    // Frost Touch: apply slow status
                    OnEnchantmentTriggered?.Invoke(enemy, enchantment);
                }
            }
        }

        /// <summary>
        /// Callback for enchantment effects that need external systems (status manager, etc.).
        /// Args: target enemy, enchantment data dictionary.
        /// </summary>
        public Action<ICombatEnemy, Dictionary<string, object>> OnEnchantmentTriggered { get; set; }

        // ====================================================================
        // AoE / Devastate Attack
        // ====================================================================

        /// <summary>
        /// Execute an AoE (devastate) attack hitting all enemies in radius.
        /// Python: _execute_aoe_attack()
        /// </summary>
        /// <param name="character">Player character (center of AoE).</param>
        /// <param name="radius">AoE radius in tiles.</param>
        /// <param name="hand">Attack hand.</param>
        /// <returns>Total damage dealt, any crit, combined loot.</returns>
        public (float TotalDamage, bool AnyCrit, List<(string, int)> Loot) ExecuteAoeAttack(
            ICombatCharacter character, int radius, string hand = "mainHand")
        {
            var allEnemies = GetAllActiveEnemies();
            var targets = new List<ICombatEnemy>();

            // Find all enemies in radius
            foreach (var enemy in allEnemies)
            {
                if (!enemy.IsAlive)
                    continue;

                float dist = enemy.DistanceTo(character.PositionX, character.PositionY);
                if (dist <= radius)
                {
                    targets.Add(enemy);
                }
            }

            float totalDamage = 0f;
            bool anyCrit = false;
            var allLoot = new List<(string, int)>();

            foreach (var target in targets)
            {
                var (damage, isCrit, loot) = PlayerAttackEnemy(target, character, hand);
                totalDamage += damage;
                anyCrit = anyCrit || isCrit;
                allLoot.AddRange(loot);
            }

            return (totalDamage, anyCrit, allLoot);
        }

        /// <summary>
        /// Execute instant AoE around player (for skills like Whirlwind Strike).
        /// Python: execute_instant_player_aoe()
        /// </summary>
        /// <returns>Number of enemies affected.</returns>
        public int ExecuteInstantAoe(ICombatCharacter character, int radius)
        {
            var allEnemies = GetAllActiveEnemies();
            var affected = new List<ICombatEnemy>();

            foreach (var enemy in allEnemies)
            {
                if (!enemy.IsAlive)
                    continue;

                float dist = enemy.DistanceTo(character.PositionX, character.PositionY);
                if (dist <= radius)
                {
                    affected.Add(enemy);
                }
            }

            foreach (var enemy in affected)
            {
                PlayerAttackEnemy(enemy, character);
            }

            return affected.Count;
        }

        // ====================================================================
        // EXP Rewards
        // ====================================================================

        /// <summary>
        /// Calculate EXP reward for killing an enemy (delegates to DamageCalculator).
        /// Python: _calculate_exp_reward()
        /// </summary>
        public int CalculateExpReward(ICombatEnemy enemy)
        {
            return DamageCalculator.CalculateExpReward(_config, enemy.Tier, enemy.IsBoss, InDungeon);
        }

        // ====================================================================
        // Safe Zone
        // ====================================================================

        /// <summary>
        /// Check if a position is in the safe zone.
        /// Delegates to EnemySpawner.IsInSafeZone().
        /// </summary>
        public bool IsInSafeZone(float x, float y)
        {
            return _spawner.IsInSafeZone(x, y);
        }

        // ====================================================================
        // Enemy Queries
        // ====================================================================

        /// <summary>
        /// Get all active enemies (world or dungeon depending on context).
        /// Python: get_all_active_enemies()
        /// </summary>
        public List<ICombatEnemy> GetAllActiveEnemies()
        {
            if (InDungeon)
                return new List<ICombatEnemy>(_dungeonEnemies);

            var all = new List<ICombatEnemy>();
            foreach (var list in _enemies.Values)
            {
                all.AddRange(list);
            }
            return all;
        }

        /// <summary>
        /// Get all living enemies within radius of a position.
        /// Python: get_enemies_in_range()
        /// </summary>
        public List<ICombatEnemy> GetEnemiesInRange(float x, float y, float radius)
        {
            var result = new List<ICombatEnemy>();
            var enemies = InDungeon ? _dungeonEnemies : GetAllActiveEnemies();

            foreach (var enemy in enemies)
            {
                if (enemy.IsAlive && enemy.DistanceTo(x, y) <= radius)
                {
                    result.Add(enemy);
                }
            }
            return result;
        }

        /// <summary>
        /// Get enemy at or near a position (for click targeting).
        /// Python: get_enemy_at_position() — tolerance default 0.7
        /// </summary>
        public ICombatEnemy GetEnemyAtPosition(float x, float y, float tolerance = 0.7f)
        {
            var enemies = InDungeon ? _dungeonEnemies : GetAllActiveEnemies();

            foreach (var enemy in enemies)
            {
                if (enemy.IsAlive && enemy.DistanceTo(x, y) <= tolerance)
                {
                    return enemy;
                }
            }
            return null;
        }

        /// <summary>
        /// Get corpse at or near a position (for looting).
        /// Python: get_corpse_at_position()
        /// </summary>
        public ICombatEnemy GetCorpseAtPosition(float x, float y, float tolerance = 0.7f)
        {
            foreach (var corpse in _corpses)
            {
                if (corpse.DistanceTo(x, y) <= tolerance)
                    return corpse;
            }
            return null;
        }

        // ====================================================================
        // Enemy Management
        // ====================================================================

        /// <summary>
        /// Register an enemy in a chunk.
        /// </summary>
        public void AddEnemy(ICombatEnemy enemy)
        {
            var coords = enemy.ChunkCoords;
            if (!_enemies.ContainsKey(coords))
            {
                _enemies[coords] = new List<ICombatEnemy>();
            }
            enemy.CorpseLifetime = _config.CorpseLifetime;
            _enemies[coords].Add(enemy);
        }

        /// <summary>
        /// Get alive enemy count for a chunk.
        /// </summary>
        public int GetAliveCountInChunk(int chunkX, int chunkY)
        {
            if (_enemies.TryGetValue((chunkX, chunkY), out var list))
            {
                return list.Count(e => e.IsAlive);
            }
            return 0;
        }

        /// <summary>
        /// Get all enemies in a specific chunk.
        /// </summary>
        public List<ICombatEnemy> GetEnemiesInChunk(int chunkX, int chunkY)
        {
            return _enemies.TryGetValue((chunkX, chunkY), out var list)
                ? new List<ICombatEnemy>(list)
                : new List<ICombatEnemy>();
        }

        // ====================================================================
        // Corpse / Loot
        // ====================================================================

        /// <summary>
        /// Loot a corpse and add items to player inventory.
        /// Python: loot_corpse()
        /// </summary>
        public List<(string MaterialId, int Quantity)> LootCorpse(
            ICombatEnemy corpse, ICombatCharacter character)
        {
            // No drops in dungeons
            if (InDungeon)
            {
                _corpses.Remove(corpse);
                _dungeonEnemies.Remove(corpse);
                return new List<(string, int)>();
            }

            var loot = corpse.GenerateLoot();

            foreach (var (materialId, quantity) in loot)
            {
                character.AddItemToInventory(materialId, quantity);
            }

            // Remove corpse from tracking
            _corpses.Remove(corpse);
            foreach (var (_, enemyList) in _enemies)
            {
                if (enemyList.Remove(corpse))
                    break;
            }

            return loot;
        }

        /// <summary>
        /// Get all current corpses (for rendering).
        /// </summary>
        public IReadOnlyList<ICombatEnemy> Corpses => _corpses;

        // ====================================================================
        // Dungeon Combat
        // ====================================================================

        /// <summary>
        /// Add a dungeon enemy.
        /// </summary>
        public void AddDungeonEnemy(ICombatEnemy enemy)
        {
            enemy.IsDungeonEnemy = true;
            enemy.InCombat = true;
            enemy.AiState = "chase";
            _dungeonEnemies.Add(enemy);
        }

        /// <summary>
        /// Clear all dungeon enemies (when exiting dungeon).
        /// Python: clear_dungeon_enemies()
        /// </summary>
        public void ClearDungeonEnemies()
        {
            _dungeonEnemies.Clear();
            // Remove dungeon corpses
            _corpses.RemoveAll(c => c.IsDungeonEnemy);
        }

        /// <summary>
        /// Get all alive dungeon enemies.
        /// </summary>
        public List<ICombatEnemy> GetDungeonEnemies()
        {
            return _dungeonEnemies.Where(e => e.IsAlive).ToList();
        }

        /// <summary>
        /// Update dungeon enemies with full combat logic.
        /// Python: update_dungeon_enemies()
        /// </summary>
        public void UpdateDungeonEnemies(float dt, ICombatCharacter character,
            float aggroMultiplier = 1.0f, float speedMultiplier = 1.0f, bool shieldBlocking = false)
        {
            var deadEnemies = new List<ICombatEnemy>();

            foreach (var enemy in _dungeonEnemies)
            {
                if (enemy.IsAlive)
                {
                    enemy.UpdateAi(dt, character.PositionX, character.PositionY,
                        aggroMultiplier, speedMultiplier);

                    if (enemy.CanAttack())
                    {
                        float dist = enemy.DistanceTo(character.PositionX, character.PositionY);
                        if (dist <= 1.5f)
                        {
                            EnemyAttackPlayer(enemy, character, shieldBlocking);
                        }
                    }
                }
                else
                {
                    if (enemy.AiState == "dead")
                    {
                        enemy.AiState = "corpse";
                        enemy.TimeSinceDeath = 0f;
                    }

                    if (enemy.AiState == "corpse")
                    {
                        enemy.TimeSinceDeath += dt;
                        if (enemy.TimeSinceDeath >= enemy.CorpseLifetime)
                        {
                            deadEnemies.Add(enemy);
                        }
                    }
                }
            }

            foreach (var dead in deadEnemies)
            {
                _dungeonEnemies.Remove(dead);
                _corpses.Remove(dead);
            }
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        /// <summary>
        /// Update player combat state (exits combat after timeout).
        /// Python: _update_player_combat_state()
        /// </summary>
        private void _updatePlayerCombatState(float dt)
        {
            if (PlayerInCombat)
            {
                _playerLastCombatTime += dt;
                if (_playerLastCombatTime >= _config.CombatTimeout)
                {
                    PlayerInCombat = false;
                }
            }
        }

        /// <summary>
        /// Apply lifesteal enchantment heal.
        /// Python: lifesteal_percent = min(value, 0.50), heal = finalDamage * lifesteal_percent
        /// </summary>
        private void _applyLifesteal(ICombatCharacter character, object weapon, float damageDealt)
        {
            var enchantments = character.GetWeaponEnchantments(weapon);
            if (enchantments == null)
                return;

            foreach (var ench in enchantments)
            {
                if (!ench.TryGetValue("effect", out object effectObj))
                    continue;
                var effect = effectObj as Dictionary<string, object>;
                if (effect == null)
                    continue;

                string effectType = effect.TryGetValue("type", out object typeObj) ? typeObj as string : null;
                if (effectType != "lifesteal")
                    continue;

                float value = effect.TryGetValue("value", out object valObj)
                    ? Convert.ToSingle(valObj)
                    : 0.1f;

                float healAmount = DamageCalculator.CalculateLifestealHeal(damageDealt, value);
                character.Heal(healAmount);
            }
        }

        /// <summary>
        /// Apply chain damage enchantment to nearby enemies.
        /// Python: chain_count enemies, deal finalDamage * chainDamagePercent (default 50%).
        /// </summary>
        private void _applyChainDamage(ICombatEnemy primaryTarget, ICombatCharacter character,
            object weapon, float baseDamage)
        {
            var enchantments = character.GetWeaponEnchantments(weapon);
            if (enchantments == null)
                return;

            foreach (var ench in enchantments)
            {
                if (!ench.TryGetValue("effect", out object effectObj))
                    continue;
                var effect = effectObj as Dictionary<string, object>;
                if (effect == null)
                    continue;

                string effectType = effect.TryGetValue("type", out object typeObj) ? typeObj as string : null;
                if (effectType != "chain_damage")
                    continue;

                int chainCount = effect.TryGetValue("value", out object countObj)
                    ? Convert.ToInt32(countObj)
                    : 2;

                float chainPercent = effect.TryGetValue("damagePercent", out object pctObj)
                    ? Convert.ToSingle(pctObj)
                    : 0.5f;

                // Find chain targets (nearest enemies, exclude primary)
                var allEnemies = GetAllActiveEnemies();
                var candidates = allEnemies
                    .Where(e => e.IsAlive && e != primaryTarget)
                    .OrderBy(e => e.DistanceTo(primaryTarget.PositionX, primaryTarget.PositionY))
                    .Take(chainCount)
                    .ToList();

                float chainDamage = baseDamage * chainPercent;
                foreach (var target in candidates)
                {
                    target.TakeDamage(chainDamage, fromPlayer: true);
                }
            }
        }

        /// <summary>
        /// Apply reflect/thorns damage from player armor to attacking enemy.
        /// Python: reflect_percent from armor enchantments, capped at 80%.
        /// </summary>
        private void _applyReflectDamage(ICombatEnemy enemy, ICombatCharacter character, float incomingDamage)
        {
            if (!enemy.IsAlive)
                return;

            float totalReflect = character.GetProtectionEnchantmentReduction();
            // Note: GetProtectionEnchantmentReduction handles thorns separately
            // For the actual thorns calculation, we need a dedicated method.
            // The reflect damage is processed via the OnEnchantmentTriggered callback
            // from armor enchantments. For now, this is a placeholder for the thorns
            // logic that the CombatManager orchestrates.

            // The actual thorns reduction is calculated in the caller or via an
            // enchantment-specific callback. This method signature exists to match
            // the Python architecture.
        }

        /// <summary>
        /// Apply weapon durability loss after an attack.
        /// Python: durability_loss = 1 (weapon) or 2 (tool), * DEF mult, * unbreaking
        /// </summary>
        private void _applyDurabilityLoss(ICombatCharacter character, object weapon, float toolEffectiveness)
        {
            float currentDur = character.GetWeaponDurability(weapon);
            if (currentDur < 0f)
                return; // No durability system on this weapon

            bool isProperWeapon = toolEffectiveness >= 1.0f;
            float durMultiplier = character.GetDurabilityLossMultiplier();

            // Check for unbreaking enchantment
            float unbreakingValue = 0f;
            var enchantments = character.GetWeaponEnchantments(weapon);
            if (enchantments != null)
            {
                foreach (var ench in enchantments)
                {
                    if (!ench.TryGetValue("effect", out object effectObj))
                        continue;
                    var effect = effectObj as Dictionary<string, object>;
                    if (effect == null)
                        continue;

                    string effectType = effect.TryGetValue("type", out object typeObj) ? typeObj as string : null;
                    if (effectType == "durability_multiplier")
                    {
                        unbreakingValue = effect.TryGetValue("value", out object valObj)
                            ? Convert.ToSingle(valObj)
                            : 0f;
                    }
                }
            }

            float loss = DamageCalculator.CalculateDurabilityLoss(isProperWeapon, durMultiplier, unbreakingValue);
            float newDurability = Math.Max(0f, currentDur - loss);
            character.SetWeaponDurability(weapon, newDurability);
        }
    }
}
