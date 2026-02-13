// ============================================================================
// Game1.Systems.Combat.EnemySpawner
// Migrated from: Combat/combat_manager.py (lines 195-451)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Extracted spawning logic from CombatManager into a focused class.
// Handles safe zone checks, chunk danger levels, weighted spawn pools,
// tier restrictions, and dynamic respawning.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Minimal interface for a chunk used by the spawner.
    /// Avoids hard dependency on the World.Chunk class.
    /// </summary>
    public interface ISpawnableChunk
    {
        /// <summary>Chunk grid X coordinate.</summary>
        int ChunkX { get; }

        /// <summary>Chunk grid Y coordinate (maps to Z in 3D).</summary>
        int ChunkY { get; }

        /// <summary>
        /// Chunk type value string (e.g., "peaceful_forest", "dangerous_cave").
        /// Used to determine danger level and map to chunk templates.
        /// </summary>
        string ChunkTypeValue { get; }
    }

    /// <summary>
    /// Minimal interface for an enemy definition used by the spawner.
    /// </summary>
    public interface ISpawnableEnemyDefinition
    {
        string EnemyId { get; }
        int Tier { get; }
    }

    /// <summary>
    /// Minimal interface for the enemy database used by the spawner.
    /// </summary>
    public interface IEnemyDatabase
    {
        /// <summary>Get an enemy definition by ID. Returns null if not found.</summary>
        ISpawnableEnemyDefinition GetEnemy(string enemyId);

        /// <summary>Get all enemy definitions for a given tier.</summary>
        IList<ISpawnableEnemyDefinition> GetEnemiesByTier(int tier);

        /// <summary>Get a random enemy definition for a given tier. Returns null if tier has no enemies.</summary>
        ISpawnableEnemyDefinition GetRandomEnemy(int tier, Random rng);
    }

    /// <summary>
    /// Manages enemy spawning logic: safe zone checks, weighted spawn pools,
    /// chunk danger levels, tier restrictions, and dynamic respawning.
    ///
    /// Extracted from Python CombatManager (lines 195-560) into a standalone class.
    /// All spawning algorithms match the Python source exactly.
    /// </summary>
    public class EnemySpawner
    {
        private readonly CombatConfig _config;
        private readonly IEnemyDatabase _enemyDb;
        private readonly Random _rng;

        /// <summary>
        /// Chunk templates loaded from JSON. Maps chunkType string to template data.
        /// Python: self.chunk_templates: Dict[str, dict]
        /// </summary>
        private readonly Dictionary<string, JObject> _chunkTemplates = new();

        /// <summary>
        /// Maps chunk type enum values to template chunkType strings.
        /// Python: self.chunk_type_mapping
        /// </summary>
        private static readonly Dictionary<string, string> ChunkTypeMapping = new()
        {
            { "peaceful_forest", "peaceful_forest" },
            { "peaceful_quarry", "peaceful_quarry" },
            { "peaceful_cave", "peaceful_cave" },
            { "dangerous_forest", "dangerous_forest" },
            { "dangerous_quarry", "dangerous_quarry" },
            { "dangerous_cave", "dangerous_cave" },
            { "rare_hidden_forest", "rare_forest" },
            { "rare_ancient_quarry", "rare_quarry" },
            { "rare_deep_cave", "rare_cave" }
        };

        /// <summary>
        /// Spawn timers per chunk, tracking time since last dynamic spawn check.
        /// Python: self.spawn_timers: Dict[Tuple[int, int], float]
        /// </summary>
        private readonly Dictionary<(int, int), float> _spawnTimers = new();

        /// <summary>
        /// Create a new EnemySpawner.
        /// </summary>
        /// <param name="config">Combat configuration (has safe zone, density weights, etc.).</param>
        /// <param name="enemyDb">Enemy database for looking up definitions.</param>
        /// <param name="rng">Random number generator for spawn rolls.</param>
        public EnemySpawner(CombatConfig config, IEnemyDatabase enemyDb, Random rng = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _enemyDb = enemyDb ?? throw new ArgumentNullException(nameof(enemyDb));
            _rng = rng ?? new Random();
        }

        // ====================================================================
        // Chunk Template Loading
        // ====================================================================

        /// <summary>
        /// Load chunk template definitions from JSON for weighted spawn pools.
        /// Python: _load_chunk_templates()
        /// </summary>
        /// <param name="filepath">Path to Chunk-templates-2.JSON.</param>
        /// <returns>True if loaded successfully.</returns>
        public bool LoadChunkTemplates(string filepath)
        {
            try
            {
                string jsonText = File.ReadAllText(filepath);
                var data = JObject.Parse(jsonText);

                var templates = data["templates"] as JArray;
                if (templates != null)
                {
                    foreach (JObject template in templates)
                    {
                        string chunkType = template.Value<string>("chunkType");
                        if (!string.IsNullOrEmpty(chunkType))
                        {
                            _chunkTemplates[chunkType] = template;
                        }
                    }
                }

                return true;
            }
            catch (Exception)
            {
                return false;
            }
        }

        // ====================================================================
        // Safe Zone
        // ====================================================================

        /// <summary>
        /// Check if a position is within the safe zone (no spawning allowed).
        /// Python: is_in_safe_zone() — distance from safe zone center <= radius.
        /// </summary>
        /// <param name="x">World X position.</param>
        /// <param name="y">World Y position (maps to Z in 3D).</param>
        /// <returns>True if position is in the safe zone.</returns>
        public bool IsInSafeZone(float x, float y)
        {
            float dx = x - _config.SafeZoneX;
            float dy = y - _config.SafeZoneY;
            float distance = MathF.Sqrt(dx * dx + dy * dy);
            return distance <= _config.SafeZoneRadius;
        }

        /// <summary>
        /// Check if a chunk's center is within the safe zone.
        /// Python: chunk_center_x = chunk.chunk_x * 16 + 8
        /// </summary>
        public bool IsChunkInSafeZone(int chunkX, int chunkY)
        {
            float centerX = chunkX * _config.ChunkSize + (_config.ChunkSize / 2f);
            float centerY = chunkY * _config.ChunkSize + (_config.ChunkSize / 2f);
            return IsInSafeZone(centerX, centerY);
        }

        // ====================================================================
        // Danger Level Detection
        // ====================================================================

        /// <summary>
        /// Determine danger level from a chunk's type string.
        /// Python: get_chunk_danger_level() — checks for "peaceful"/"dangerous"/"rare" substrings.
        /// </summary>
        /// <param name="chunkTypeValue">The chunk type string (e.g., "peaceful_forest").</param>
        /// <returns>Danger level: "peaceful", "dangerous", "rare", or "normal".</returns>
        public string GetChunkDangerLevel(string chunkTypeValue)
        {
            if (string.IsNullOrEmpty(chunkTypeValue))
                return "normal";

            // Python: if "peaceful" in chunk_type_str: return "peaceful"
            if (chunkTypeValue.Contains("peaceful"))
                return "peaceful";
            if (chunkTypeValue.Contains("dangerous"))
                return "dangerous";
            if (chunkTypeValue.Contains("rare"))
                return "rare";

            return "normal";
        }

        /// <summary>
        /// Get allowed enemy tiers for a given danger level.
        /// Python: _get_allowed_tiers_for_danger_level()
        /// </summary>
        /// <param name="dangerLevel">Danger level string.</param>
        /// <returns>Set of allowed tier numbers.</returns>
        public HashSet<int> GetAllowedTiersForDangerLevel(string dangerLevel)
        {
            return dangerLevel switch
            {
                "peaceful" => new HashSet<int> { 1 },           // Only T1
                "dangerous" => new HashSet<int> { 1, 2, 3 },    // T1-T3
                "rare" => new HashSet<int> { 1, 2, 3, 4 },      // T1-T4 (including bosses)
                _ => new HashSet<int> { 1 }                      // Default to safest tier
            };
        }

        // ====================================================================
        // Weighted Spawn Pool
        // ====================================================================

        /// <summary>
        /// Build a weighted spawn pool for a chunk.
        /// Combines chunk template enemySpawns (priority) with tier-filtered general pool.
        /// Python: _build_weighted_spawn_pool()
        /// </summary>
        /// <param name="chunk">The chunk to build a pool for.</param>
        /// <param name="dangerLevel">Danger level of the chunk.</param>
        /// <param name="spawnConfig">Spawn configuration JObject for this danger level.</param>
        /// <returns>List of (enemyDefinition, weight) tuples.</returns>
        public List<(ISpawnableEnemyDefinition Definition, float Weight)> BuildWeightedSpawnPool(
            ISpawnableChunk chunk, string dangerLevel, JObject spawnConfig)
        {
            var spawnPool = new List<(ISpawnableEnemyDefinition, float)>();

            // 1. Add priority enemies from chunk template enemySpawns
            var priorityIds = new HashSet<string>();
            var chunkTemplate = _getChunkTemplate(chunk);

            if (chunkTemplate != null)
            {
                var enemySpawns = chunkTemplate["enemySpawns"] as JObject;
                if (enemySpawns != null)
                {
                    foreach (var prop in enemySpawns.Properties())
                    {
                        string enemyId = prop.Name;
                        var spawnInfo = prop.Value as JObject;
                        var enemyDef = _enemyDb.GetEnemy(enemyId);

                        if (enemyDef == null)
                            continue;

                        // Get density weight
                        string density = spawnInfo?.Value<string>("density") ?? "moderate";
                        float weight = _config.GetDensityWeight(density);

                        spawnPool.Add((enemyDef, weight));
                        priorityIds.Add(enemyId);
                    }
                }
            }

            // 2. Add general pool enemies (tier-based, exclude priority enemies)
            var tierWeights = _extractTierWeights(spawnConfig);
            var filteredWeights = _filterTierWeightsForDanger(tierWeights, dangerLevel);

            foreach (var (tierName, tierWeight) in filteredWeights)
            {
                int tier = _parseTierNumber(tierName);
                var tierEnemies = _enemyDb.GetEnemiesByTier(tier);

                foreach (var enemyDef in tierEnemies)
                {
                    // Skip if already in priority pool
                    if (priorityIds.Contains(enemyDef.EnemyId))
                        continue;

                    // Add with base weight 1.0
                    // Python: spawn_pool.append((enemy_def, 1.0))
                    spawnPool.Add((enemyDef, 1.0f));
                }
            }

            // Fallback: if pool is empty, use T1 enemies
            if (spawnPool.Count == 0)
            {
                var t1Enemies = _enemyDb.GetEnemiesByTier(1);
                foreach (var enemyDef in t1Enemies)
                {
                    spawnPool.Add((enemyDef, 1.0f));
                }
            }

            return spawnPool;
        }

        /// <summary>
        /// Select an enemy from a weighted spawn pool using weighted random selection.
        /// Python: _select_from_weighted_pool() — uses random.choices(weights=weights).
        /// </summary>
        /// <param name="spawnPool">Weighted spawn pool.</param>
        /// <returns>Selected enemy definition, or null if pool is empty.</returns>
        public ISpawnableEnemyDefinition SelectFromWeightedPool(
            List<(ISpawnableEnemyDefinition Definition, float Weight)> spawnPool)
        {
            if (spawnPool == null || spawnPool.Count == 0)
                return null;

            // Weighted random choice (replicates Python random.choices behavior)
            float totalWeight = 0f;
            foreach (var (_, weight) in spawnPool)
            {
                totalWeight += weight;
            }

            if (totalWeight <= 0f)
                return spawnPool[0].Definition;

            float roll = (float)_rng.NextDouble() * totalWeight;
            float cumulative = 0f;

            foreach (var (definition, weight) in spawnPool)
            {
                cumulative += weight;
                if (roll < cumulative)
                    return definition;
            }

            // Edge case: return last element
            return spawnPool[^1].Definition;
        }

        /// <summary>
        /// Pick a tier based on weighted probabilities.
        /// Python: _pick_weighted_tier()
        /// </summary>
        /// <param name="tierWeights">Dictionary mapping tier names to weights.</param>
        /// <returns>Selected tier number (1-4).</returns>
        public int PickWeightedTier(Dictionary<string, float> tierWeights)
        {
            var tiers = new List<int>();
            var weights = new List<float>();

            foreach (var (tierName, weight) in tierWeights)
            {
                if (weight > 0f)
                {
                    tiers.Add(_parseTierNumber(tierName));
                    weights.Add(weight);
                }
            }

            if (tiers.Count == 0)
                return 1;

            float totalWeight = weights.Sum();
            float roll = (float)_rng.NextDouble() * totalWeight;
            float cumulative = 0f;

            for (int i = 0; i < tiers.Count; i++)
            {
                cumulative += weights[i];
                if (roll < cumulative)
                    return tiers[i];
            }

            return tiers[^1];
        }

        // ====================================================================
        // Spawn Execution
        // ====================================================================

        /// <summary>
        /// Determine how many enemies should be spawned in a chunk.
        /// Returns spawn positions and enemy definitions for the caller to instantiate.
        ///
        /// Python: spawn_enemies_in_chunk()
        /// </summary>
        /// <param name="chunk">The chunk to spawn enemies in.</param>
        /// <param name="currentAliveCount">Number of alive enemies currently in this chunk.</param>
        /// <returns>List of (enemyDefinition, spawnX, spawnY) for the caller to instantiate.</returns>
        public List<(ISpawnableEnemyDefinition Definition, float SpawnX, float SpawnY)> DetermineSpawns(
            ISpawnableChunk chunk, int currentAliveCount)
        {
            var result = new List<(ISpawnableEnemyDefinition, float, float)>();

            // Don't spawn if chunk center is in safe zone
            if (IsChunkInSafeZone(chunk.ChunkX, chunk.ChunkY))
                return result;

            // Get danger level and spawn config
            string dangerLevel = GetChunkDangerLevel(chunk.ChunkTypeValue);
            JObject spawnConfig = _config.GetSpawnConfig(dangerLevel);
            if (spawnConfig == null)
                return result;

            // Don't spawn if at max
            // Python: MAX_PER_CHUNK = 3
            if (currentAliveCount >= _config.MaxEnemiesPerChunk)
                return result;

            // Determine how many to spawn
            // Python: min_enemies = spawn_config.get('minEnemies', 1)
            //         max_enemies = spawn_config.get('maxEnemies', 3)
            int minEnemies = spawnConfig.Value<int?>("minEnemies") ?? 1;
            int maxEnemies = spawnConfig.Value<int?>("maxEnemies") ?? 3;
            int targetCount = _rng.Next(minEnemies, maxEnemies + 1);
            int toSpawn = Math.Max(0, targetCount - currentAliveCount);

            // Build weighted spawn pool
            var spawnPool = BuildWeightedSpawnPool(chunk, dangerLevel, spawnConfig);

            // Spawn enemies
            for (int i = 0; i < toSpawn; i++)
            {
                var enemyDef = SelectFromWeightedPool(spawnPool);
                if (enemyDef == null)
                    continue;

                // Random position within chunk (offset from edges)
                // Python: spawn_x = chunk.chunk_x * 16 + random.uniform(2, 14)
                float spawnX = chunk.ChunkX * _config.ChunkSize + (float)(_rng.NextDouble() * 12.0 + 2.0);
                float spawnY = chunk.ChunkY * _config.ChunkSize + (float)(_rng.NextDouble() * 12.0 + 2.0);

                result.Add((enemyDef, spawnX, spawnY));
            }

            return result;
        }

        // ====================================================================
        // Dynamic Respawning
        // ====================================================================

        /// <summary>
        /// Check if any chunks in the 3x3 area around the player need dynamic spawning.
        /// Returns chunk coordinates that are due for respawn.
        ///
        /// Python: _check_dynamic_spawning()
        /// </summary>
        /// <param name="playerX">Player world X position.</param>
        /// <param name="playerY">Player world Y position.</param>
        /// <param name="dt">Delta time since last frame.</param>
        /// <param name="getChunkDangerLevel">Function to get danger level for a chunk coordinate.
        /// Returns null if chunk doesn't exist.</param>
        /// <returns>List of chunk coordinates that should have spawning triggered.</returns>
        public List<(int ChunkX, int ChunkY)> CheckDynamicSpawning(
            float playerX, float playerY, float dt,
            Func<int, int, string> getChunkDangerLevel)
        {
            var chunksToSpawn = new List<(int, int)>();

            int playerChunkX = (int)(playerX / _config.ChunkSize);
            int playerChunkY = (int)(playerY / _config.ChunkSize);

            // Check 3x3 area around player
            // Python: for dx in range(-1, 2): for dy in range(-1, 2):
            for (int dx = -1; dx <= 1; dx++)
            {
                for (int dy = -1; dy <= 1; dy++)
                {
                    int chunkX = playerChunkX + dx;
                    int chunkY = playerChunkY + dy;
                    var chunkCoords = (chunkX, chunkY);

                    // Initialize timer if needed
                    if (!_spawnTimers.ContainsKey(chunkCoords))
                    {
                        _spawnTimers[chunkCoords] = 0f;
                    }

                    // Accumulate time
                    _spawnTimers[chunkCoords] += dt;

                    // Get danger level (returns null if chunk doesn't exist)
                    string dangerLevel = getChunkDangerLevel(chunkX, chunkY);
                    if (dangerLevel == null)
                        continue;

                    // Get spawn interval for this danger level
                    JObject spawnConfig = _config.GetSpawnConfig(dangerLevel);
                    if (spawnConfig == null)
                        continue;

                    // Python: spawn_interval = spawn_config.get('spawnInterval', 120)
                    float spawnInterval = spawnConfig.Value<float?>("spawnInterval") ?? 120f;

                    // Check if enough time has passed
                    if (_spawnTimers[chunkCoords] >= spawnInterval)
                    {
                        chunksToSpawn.Add(chunkCoords);
                        _spawnTimers[chunkCoords] = 0f;
                    }
                }
            }

            return chunksToSpawn;
        }

        /// <summary>
        /// Reset the spawn timer for a chunk (e.g., after spawning).
        /// </summary>
        public void ResetSpawnTimer(int chunkX, int chunkY)
        {
            _spawnTimers[(chunkX, chunkY)] = 0f;
        }

        /// <summary>
        /// Update all spawn timers by delta time.
        /// Python: for chunk_coords in self.spawn_timers: self.spawn_timers[chunk_coords] += dt
        /// </summary>
        public void UpdateTimers(float dt)
        {
            var keys = _spawnTimers.Keys.ToList();
            foreach (var key in keys)
            {
                _spawnTimers[key] += dt;
            }
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        /// <summary>
        /// Get chunk template for a given chunk.
        /// Python: _get_chunk_template()
        /// </summary>
        private JObject _getChunkTemplate(ISpawnableChunk chunk)
        {
            string chunkTypeStr = chunk.ChunkTypeValue;
            string templateKey = ChunkTypeMapping.TryGetValue(chunkTypeStr, out string mapped)
                ? mapped
                : chunkTypeStr;

            return _chunkTemplates.TryGetValue(templateKey, out JObject template) ? template : null;
        }

        /// <summary>
        /// Extract tier weights from spawn config JObject.
        /// Python: tier_weights = spawn_config.get('tierWeights', {'tier1': 1.0})
        /// </summary>
        private Dictionary<string, float> _extractTierWeights(JObject spawnConfig)
        {
            var result = new Dictionary<string, float> { { "tier1", 1.0f } };

            var tierWeights = spawnConfig?["tierWeights"] as JObject;
            if (tierWeights != null)
            {
                result.Clear();
                foreach (var prop in tierWeights.Properties())
                {
                    result[prop.Name] = prop.Value.Value<float>();
                }
            }

            return result;
        }

        /// <summary>
        /// Filter tier weights based on danger level restrictions.
        /// Python: _filter_tier_weights_for_danger()
        /// </summary>
        private Dictionary<string, float> _filterTierWeightsForDanger(
            Dictionary<string, float> tierWeights, string dangerLevel)
        {
            var allowedTiers = GetAllowedTiersForDangerLevel(dangerLevel);
            var filtered = new Dictionary<string, float>();

            foreach (var (tierName, weight) in tierWeights)
            {
                int tierNum = _parseTierNumber(tierName);
                if (allowedTiers.Contains(tierNum) && weight > 0f)
                {
                    filtered[tierName] = weight;
                }
            }

            // Fallback: if no valid tiers, allow T1
            // Python: if not filtered: filtered = {'tier1': 1.0}
            if (filtered.Count == 0)
            {
                filtered["tier1"] = 1.0f;
            }

            return filtered;
        }

        /// <summary>
        /// Parse tier number from tier name string.
        /// Python: int(tier_name.replace('tier', ''))
        /// </summary>
        private int _parseTierNumber(string tierName)
        {
            string numStr = tierName.Replace("tier", "");
            return int.TryParse(numStr, out int result) ? result : 1;
        }
    }
}
