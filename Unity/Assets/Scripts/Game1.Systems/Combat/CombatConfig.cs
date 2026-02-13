// ============================================================================
// Game1.Systems.Combat.CombatConfig
// Migrated from: Combat/combat_manager.py (lines 24-108)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Combat configuration loaded from JSON. Stores EXP rewards, safe zone settings,
    /// spawn rates, respawn times, attack cooldowns, and density weights.
    /// All defaults match Python CombatConfig.__init__ exactly.
    /// </summary>
    public class CombatConfig
    {
        // ====================================================================
        // EXP Rewards (per enemy tier)
        // ====================================================================

        /// <summary>
        /// Base EXP reward per enemy tier.
        /// Python: {"tier1": 100, "tier2": 400, "tier3": 1600, "tier4": 6400}
        /// </summary>
        public Dictionary<string, int> ExpRewards { get; set; } = new()
        {
            { "tier1", 100 },
            { "tier2", 400 },
            { "tier3", 1600 },
            { "tier4", 6400 }
        };

        /// <summary>
        /// EXP multiplier for boss enemies.
        /// Python: self.boss_multiplier = 10.0
        /// </summary>
        public float BossMultiplier { get; set; } = 10.0f;

        // ====================================================================
        // Safe Zone (no spawning region around world origin)
        // ====================================================================

        /// <summary>Center X of safe zone. Python: self.safe_zone_x = 0</summary>
        public float SafeZoneX { get; set; } = 0f;

        /// <summary>Center Y of safe zone (maps to Z in 3D). Python: self.safe_zone_y = 0</summary>
        public float SafeZoneY { get; set; } = 0f;

        /// <summary>Radius of safe zone. Python: self.safe_zone_radius = 15</summary>
        public float SafeZoneRadius { get; set; } = 15f;

        // ====================================================================
        // Spawn Configuration
        // ====================================================================

        /// <summary>
        /// Spawn rates per danger level (loaded from JSON).
        /// Keys: "peaceful", "dangerous", "rare", etc.
        /// Values: JObject containing minEnemies, maxEnemies, spawnInterval, tierWeights.
        /// </summary>
        public Dictionary<string, JObject> SpawnRates { get; set; } = new();

        /// <summary>
        /// Respawn configuration by tier (loaded from JSON).
        /// Keys: "base", "tier1", "tier2", "tier3", "tier4", "boss".
        /// Values: multipliers or absolute times in seconds.
        /// </summary>
        public Dictionary<string, float> RespawnTimes { get; set; } = new();

        /// <summary>
        /// Density weight mapping for weighted spawn pools.
        /// Maps density descriptor strings to spawn weight multipliers.
        /// Python: self.density_weights
        /// </summary>
        public Dictionary<string, float> DensityWeights { get; set; } = new()
        {
            { "very_low", 0.5f },
            { "low", 0.75f },
            { "moderate", 1.0f },
            { "high", 2.0f },
            { "very_high", 3.0f }
        };

        // ====================================================================
        // Attack / Combat Mechanics
        // ====================================================================

        /// <summary>
        /// Base cooldown between player attacks in seconds.
        /// Python: self.base_attack_cooldown = 1.0
        /// </summary>
        public float BaseAttackCooldown { get; set; } = 1.0f;

        /// <summary>
        /// Cooldown when attacking with a tool (axe/pickaxe) instead of a weapon.
        /// Python: self.tool_attack_cooldown = 0.5
        /// </summary>
        public float ToolAttackCooldown { get; set; } = 0.5f;

        /// <summary>
        /// Time in seconds before enemy corpses are removed.
        /// Python: self.corpse_lifetime = 30.0
        /// </summary>
        public float CorpseLifetime { get; set; } = 30.0f;

        /// <summary>
        /// Seconds without combat before player exits combat state.
        /// Python: self.combat_timeout = 5.0
        /// </summary>
        public float CombatTimeout { get; set; } = 5.0f;

        /// <summary>
        /// Maximum number of alive enemies per chunk.
        /// Python: MAX_PER_CHUNK = 3 (hardcoded in spawn_enemies_in_chunk)
        /// </summary>
        public int MaxEnemiesPerChunk { get; set; } = 3;

        /// <summary>
        /// Tiles per chunk side. Python: CHUNK_SIZE = 16.
        /// </summary>
        public int ChunkSize { get; set; } = 16;

        /// <summary>
        /// Aggro range multiplier applied at night.
        /// Python: aggro_mult = 1.3 if is_night else 1.0
        /// </summary>
        public float NightAggroMultiplier { get; set; } = 1.3f;

        /// <summary>
        /// Movement speed multiplier applied to enemies at night.
        /// Python: speed_mult = 1.15 if is_night else 1.0
        /// </summary>
        public float NightSpeedMultiplier { get; set; } = 1.15f;

        // ====================================================================
        // JSON Loading
        // ====================================================================

        /// <summary>
        /// Load combat configuration from a JSON file.
        /// Mirrors Python CombatConfig.load_from_file() exactly.
        /// </summary>
        /// <param name="filepath">Full path to the combat configuration JSON file.</param>
        /// <returns>True if loaded successfully, false on error.</returns>
        public bool LoadFromFile(string filepath)
        {
            try
            {
                string jsonText = File.ReadAllText(filepath);
                var data = JObject.Parse(jsonText);

                // Load EXP rewards
                var expData = data["experienceRewards"] as JObject;
                if (expData != null)
                {
                    ExpRewards["tier1"] = expData.Value<int?>("tier1") ?? 100;
                    ExpRewards["tier2"] = expData.Value<int?>("tier2") ?? 400;
                    ExpRewards["tier3"] = expData.Value<int?>("tier3") ?? 1600;
                    ExpRewards["tier4"] = expData.Value<int?>("tier4") ?? 6400;
                    BossMultiplier = expData.Value<float?>("bossMultiplier") ?? 10.0f;
                }

                // Load safe zone (defaults to origin)
                var safeData = data["safeZone"] as JObject;
                if (safeData != null)
                {
                    SafeZoneX = safeData.Value<float?>("centerX") ?? 0f;
                    SafeZoneY = safeData.Value<float?>("centerY") ?? 0f;
                    SafeZoneRadius = safeData.Value<float?>("radius") ?? 15f;
                }

                // Load spawn rates
                var spawnRatesData = data["spawnRates"] as JObject;
                if (spawnRatesData != null)
                {
                    SpawnRates.Clear();
                    foreach (var prop in spawnRatesData.Properties())
                    {
                        SpawnRates[prop.Name] = prop.Value as JObject ?? new JObject();
                    }
                }

                // Load respawn times
                var respawnData = data["enemyRespawn"] as JObject;
                if (respawnData != null)
                {
                    RespawnTimes["base"] = respawnData.Value<float?>("baseRespawnTime") ?? 300f;

                    var tierMults = respawnData["tierMultipliers"] as JObject;
                    RespawnTimes["tier1"] = tierMults?.Value<float?>("tier1") ?? 1.0f;
                    RespawnTimes["tier2"] = tierMults?.Value<float?>("tier2") ?? 1.5f;
                    RespawnTimes["tier3"] = tierMults?.Value<float?>("tier3") ?? 2.0f;
                    RespawnTimes["tier4"] = tierMults?.Value<float?>("tier4") ?? 3.0f;
                    RespawnTimes["boss"] = respawnData.Value<float?>("bossRespawnTime") ?? 1800f;
                }

                // Load mechanics
                var mechanics = data["combatMechanics"] as JObject;
                if (mechanics != null)
                {
                    BaseAttackCooldown = mechanics.Value<float?>("baseAttackCooldown") ?? 1.0f;
                    ToolAttackCooldown = mechanics.Value<float?>("toolAttackCooldown") ?? 0.5f;
                    CorpseLifetime = mechanics.Value<float?>("enemyCorpseLifetime") ?? 30f;
                    CombatTimeout = mechanics.Value<float?>("combatTimeout") ?? 5.0f;
                }

                // Load spawn weights (optional, merges with defaults)
                var spawnWeights = data["spawnWeights"] as JObject;
                if (spawnWeights != null)
                {
                    foreach (var prop in spawnWeights.Properties())
                    {
                        DensityWeights[prop.Name] = prop.Value.Value<float>();
                    }
                }

                return true;
            }
            catch (Exception)
            {
                // Silently use defaults on failure (matches Python behavior)
                return false;
            }
        }

        // ====================================================================
        // Helper Methods
        // ====================================================================

        /// <summary>
        /// Get the base EXP reward for a given tier.
        /// </summary>
        /// <param name="tier">Enemy tier (1-4).</param>
        /// <returns>Base EXP reward for that tier.</returns>
        public int GetExpReward(int tier)
        {
            string key = $"tier{tier}";
            return ExpRewards.TryGetValue(key, out int reward) ? reward : 100;
        }

        /// <summary>
        /// Get the density weight for a given density descriptor.
        /// </summary>
        /// <param name="density">Density string (e.g., "moderate", "high").</param>
        /// <returns>Weight multiplier, defaults to 1.0 for unknown densities.</returns>
        public float GetDensityWeight(string density)
        {
            return DensityWeights.TryGetValue(density, out float weight) ? weight : 1.0f;
        }

        /// <summary>
        /// Get spawn configuration for a danger level.
        /// </summary>
        /// <param name="dangerLevel">Danger level string (e.g., "peaceful", "dangerous").</param>
        /// <returns>Spawn config JObject or null if not found.</returns>
        public JObject GetSpawnConfig(string dangerLevel)
        {
            return SpawnRates.TryGetValue(dangerLevel, out JObject config) ? config : null;
        }
    }
}
