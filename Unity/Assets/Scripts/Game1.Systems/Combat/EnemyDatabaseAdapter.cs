// ============================================================================
// Game1.Systems.Combat.EnemyDatabaseAdapter
// Migrated from: Combat/enemy.py EnemyDatabase class
// Migration phase: 4
// Date: 2026-02-21
//
// Loads enemy definitions from hostiles-1.JSON and implements IEnemyDatabase
// (defined in EnemySpawner.cs) so the spawner can look up enemies by ID/tier.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Game1.Core;
using Game1.Entities;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Singleton database that loads enemy definitions from JSON and adapts them
    /// to the IEnemyDatabase interface required by EnemySpawner.
    /// Thread-safe double-checked locking per CONVENTIONS.md section 3.
    /// </summary>
    public class EnemyDatabaseAdapter : IEnemyDatabase
    {
        private static EnemyDatabaseAdapter _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, EnemyDefinition> _enemies = new();
        private readonly Dictionary<int, List<EnemyDefinition>> _enemiesByTier = new();
        private readonly Random _rng = new();

        public static EnemyDatabaseAdapter Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new EnemyDatabaseAdapter();
                        }
                    }
                }
                return _instance;
            }
        }

        private EnemyDatabaseAdapter() { }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        public bool Loaded { get; private set; }
        public int EnemyCount => _enemies.Count;

        // ====================================================================
        // Loading
        // ====================================================================

        /// <summary>
        /// Load enemy definitions from hostiles JSON file.
        /// Handles the nested JSON format: { "enemies": [ { "enemyId", "stats": { ... }, "drops": [...] } ] }
        /// </summary>
        public void LoadFromFile(string relativePath)
        {
            string fullPath = GamePaths.GetContentPath(relativePath);
            if (!File.Exists(fullPath))
            {
                System.Diagnostics.Debug.WriteLine($"[EnemyDatabaseAdapter] File not found: {fullPath}");
                return;
            }

            try
            {
                string json = File.ReadAllText(fullPath);
                var data = JObject.Parse(json);

                var enemiesArray = data["enemies"] as JArray;
                if (enemiesArray == null)
                {
                    System.Diagnostics.Debug.WriteLine("[EnemyDatabaseAdapter] No 'enemies' array found in JSON");
                    return;
                }

                foreach (JObject enemyObj in enemiesArray)
                {
                    var definition = ParseEnemyDefinition(enemyObj);
                    if (definition != null && !string.IsNullOrEmpty(definition.EnemyId))
                    {
                        _enemies[definition.EnemyId] = definition;

                        if (!_enemiesByTier.ContainsKey(definition.Tier))
                            _enemiesByTier[definition.Tier] = new List<EnemyDefinition>();
                        _enemiesByTier[definition.Tier].Add(definition);
                    }
                }

                Loaded = true;
                System.Diagnostics.Debug.WriteLine(
                    $"[EnemyDatabaseAdapter] Loaded {_enemies.Count} enemies from {relativePath}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[EnemyDatabaseAdapter] Error loading {relativePath}: {ex.Message}");
            }
        }

        // ====================================================================
        // IEnemyDatabase Implementation
        // ====================================================================

        /// <summary>Get an enemy definition by ID. Returns null if not found.</summary>
        public ISpawnableEnemyDefinition GetEnemy(string enemyId)
        {
            if (string.IsNullOrEmpty(enemyId)) return null;
            return _enemies.TryGetValue(enemyId, out var def) ? new SpawnableEnemyWrapper(def) : null;
        }

        /// <summary>Get all enemy definitions for a given tier.</summary>
        public IList<ISpawnableEnemyDefinition> GetEnemiesByTier(int tier)
        {
            if (!_enemiesByTier.TryGetValue(tier, out var list))
                return Array.Empty<ISpawnableEnemyDefinition>();

            return list.Select(d => (ISpawnableEnemyDefinition)new SpawnableEnemyWrapper(d)).ToList();
        }

        /// <summary>Get a random enemy definition for a given tier.</summary>
        public ISpawnableEnemyDefinition GetRandomEnemy(int tier, Random rng)
        {
            if (!_enemiesByTier.TryGetValue(tier, out var list) || list.Count == 0)
                return null;

            var r = rng ?? _rng;
            return new SpawnableEnemyWrapper(list[r.Next(list.Count)]);
        }

        // ====================================================================
        // Direct Queries (for game code that needs full EnemyDefinition)
        // ====================================================================

        /// <summary>Get the full EnemyDefinition by ID. Returns null if not found.</summary>
        public EnemyDefinition GetEnemyDefinition(string enemyId)
        {
            if (string.IsNullOrEmpty(enemyId)) return null;
            return _enemies.TryGetValue(enemyId, out var def) ? def : null;
        }

        /// <summary>Get all loaded enemy definitions.</summary>
        public IReadOnlyDictionary<string, EnemyDefinition> AllEnemies => _enemies;

        // ====================================================================
        // JSON Parsing
        // ====================================================================

        /// <summary>
        /// Parse a single enemy definition from the hostiles JSON format.
        /// Handles the nested stats/drops/metadata structure.
        /// </summary>
        private static EnemyDefinition ParseEnemyDefinition(JObject obj)
        {
            try
            {
                var def = new EnemyDefinition
                {
                    EnemyId = obj.Value<string>("enemyId") ?? "",
                    Name = obj.Value<string>("name") ?? "",
                    Tier = obj.Value<int?>("tier") ?? 1,
                    Category = obj.Value<string>("category") ?? "beast",
                    Behavior = obj.Value<string>("behavior") ?? "passive_patrol",
                };

                // Parse nested stats object
                var stats = obj["stats"] as JObject;
                if (stats != null)
                {
                    def.MaxHealth = stats.Value<float?>("health") ?? 100f;
                    def.Defense = stats.Value<float?>("defense") ?? 0f;
                    def.Speed = stats.Value<float?>("speed") ?? 1.0f;
                    def.AggroRange = stats.Value<float?>("aggroRange") ?? 5f;
                    def.AttackSpeed = stats.Value<float?>("attackSpeed") ?? 1.0f;

                    // Damage is an array [min, max]
                    var damageArr = stats["damage"] as JArray;
                    if (damageArr != null && damageArr.Count >= 2)
                    {
                        def.DamageMin = damageArr[0].Value<float>();
                        def.DamageMax = damageArr[1].Value<float>();
                    }
                }

                // Parse drops array
                var dropsArr = obj["drops"] as JArray;
                if (dropsArr != null)
                {
                    foreach (JObject dropObj in dropsArr)
                    {
                        var drop = new DropDefinition
                        {
                            MaterialId = dropObj.Value<string>("materialId") ?? "",
                        };

                        // Quantity is an array [min, max]
                        var qtyArr = dropObj["quantity"] as JArray;
                        if (qtyArr != null && qtyArr.Count >= 2)
                        {
                            drop.QuantityMin = qtyArr[0].Value<int>();
                            drop.QuantityMax = qtyArr[1].Value<int>();
                        }

                        // Chance is a string: "guaranteed", "high", "moderate", "low", "rare"
                        string chanceStr = dropObj.Value<string>("chance") ?? "guaranteed";
                        drop.Chance = ParseChanceString(chanceStr);

                        def.Drops.Add(drop);
                    }
                }

                // Parse metadata
                var metadata = obj["metadata"] as JObject;
                if (metadata != null)
                {
                    def.Narrative = metadata.Value<string>("narrative") ?? "";
                    var tagsArr = metadata["tags"] as JArray;
                    if (tagsArr != null)
                    {
                        def.Tags = tagsArr.Select(t => t.Value<string>()).Where(t => t != null).ToList();
                    }
                }

                // Parse special abilities
                var abilities = obj["specialAbilities"] as JArray;
                if (abilities != null)
                {
                    foreach (JObject abilityObj in abilities)
                    {
                        def.SpecialAbilities.Add(abilityObj.ToObject<SpecialAbility>());
                    }
                }

                return def;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[EnemyDatabaseAdapter] Error parsing enemy: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Convert chance string from JSON to numeric probability.
        /// Matches Python: enemy.py chance parsing.
        /// </summary>
        private static float ParseChanceString(string chance)
        {
            return chance?.ToLowerInvariant() switch
            {
                "guaranteed" => 1.0f,
                "high" => 0.75f,
                "moderate" => 0.5f,
                "low" => 0.25f,
                "rare" => 0.10f,
                "very_rare" => 0.05f,
                _ => float.TryParse(chance, out float val) ? val : 1.0f,
            };
        }

        // ====================================================================
        // ISpawnableEnemyDefinition Wrapper
        // ====================================================================

        /// <summary>
        /// Lightweight wrapper that adapts EnemyDefinition to ISpawnableEnemyDefinition.
        /// </summary>
        private class SpawnableEnemyWrapper : ISpawnableEnemyDefinition
        {
            private readonly EnemyDefinition _def;
            public SpawnableEnemyWrapper(EnemyDefinition def) => _def = def;
            public string EnemyId => _def.EnemyId;
            public int Tier => _def.Tier;
        }
    }
}
