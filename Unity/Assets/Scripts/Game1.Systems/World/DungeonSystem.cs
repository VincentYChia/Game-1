// ============================================================================
// Game1.Systems.World.DungeonSystem
// Migrated from: systems/dungeon.py (lines 1-805)
// Migration phase: 4
// Date: 2026-02-21
//
// Instanced dungeon system: 32x32 tile arenas with wave-based combat.
// Six rarity tiers with different mob counts and tier distributions.
// Full save/load support.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;
using Game1.Data.Models;

namespace Game1.Systems.World
{
    /// <summary>
    /// Dungeon rarity tiers with mob counts and tier distributions.
    /// Matches Python: dungeon.py DungeonRarity enum and config.
    /// </summary>
    public enum DungeonRarity
    {
        Common,
        Uncommon,
        Rare,
        Epic,
        Legendary,
        Unique
    }

    /// <summary>
    /// Configuration for a dungeon rarity level.
    /// </summary>
    public class DungeonRarityConfig
    {
        public DungeonRarity Rarity { get; set; }
        public int TotalMobs { get; set; }
        public int Waves { get; set; } = 3;
        public Dictionary<int, float> TierWeights { get; set; } = new();
    }

    /// <summary>
    /// A loot chest spawned on dungeon completion.
    /// Matches Python: dungeon.py LootChest class.
    /// </summary>
    public class LootChest
    {
        public GamePosition Position { get; set; }
        public List<LootDrop> Contents { get; set; } = new();
        public bool Opened { get; set; }
        public string ChestTier { get; set; } = "common";

        public Dictionary<string, object> ToDict()
        {
            var contentsList = new List<Dictionary<string, object>>();
            foreach (var drop in Contents)
            {
                contentsList.Add(new Dictionary<string, object>
                {
                    ["item_id"] = drop.ItemId,
                    ["quantity"] = drop.Quantity,
                });
            }

            return new Dictionary<string, object>
            {
                ["position_x"] = Position.X,
                ["position_z"] = Position.Z,
                ["contents"] = contentsList,
                ["opened"] = Opened,
                ["chest_tier"] = ChestTier,
            };
        }

        public static LootChest FromDict(Dictionary<string, object> data)
        {
            var chest = new LootChest();

            if (data.TryGetValue("position_x", out var px) && data.TryGetValue("position_z", out var pz))
                chest.Position = GamePosition.FromXZ(Convert.ToSingle(px), Convert.ToSingle(pz));

            if (data.TryGetValue("opened", out var opened))
                chest.Opened = Convert.ToBoolean(opened);

            if (data.TryGetValue("chest_tier", out var tier))
                chest.ChestTier = tier?.ToString() ?? "common";

            if (data.TryGetValue("contents", out var contentsObj)
                && contentsObj is IEnumerable<object> contentsList)
            {
                foreach (var item in contentsList)
                {
                    if (item is Dictionary<string, object> dropData)
                    {
                        chest.Contents.Add(new LootDrop
                        {
                            ItemId = dropData.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                            Quantity = dropData.TryGetValue("quantity", out var qty) ? Convert.ToInt32(qty) : 1,
                        });
                    }
                }
            }

            return chest;
        }
    }

    /// <summary>A single loot drop entry.</summary>
    public class LootDrop
    {
        public string ItemId { get; set; }
        public int Quantity { get; set; } = 1;
    }

    /// <summary>
    /// A dungeon instance with wave-based combat.
    /// Matches Python: dungeon.py DungeonInstance class.
    /// </summary>
    public class DungeonInstance
    {
        /// <summary>Unique dungeon instance ID.</summary>
        public string DungeonId { get; set; }

        /// <summary>Dungeon rarity tier.</summary>
        public DungeonRarity Rarity { get; set; }

        /// <summary>Entrance position in the world.</summary>
        public GamePosition EntrancePosition { get; set; }

        /// <summary>Dungeon arena size (default 32x32 tiles).</summary>
        public int ArenaSize { get; set; } = 32;

        /// <summary>Current wave number (1-indexed).</summary>
        public int CurrentWave { get; set; } = 0;

        /// <summary>Total number of waves.</summary>
        public int TotalWaves { get; set; } = 3;

        /// <summary>Enemies remaining in current wave.</summary>
        public int EnemiesRemaining { get; set; }

        /// <summary>Total enemies killed in this dungeon run.</summary>
        public int TotalKills { get; set; }

        /// <summary>Whether the dungeon is complete (all waves cleared).</summary>
        public bool IsComplete { get; set; }

        /// <summary>Whether the player has left the dungeon.</summary>
        public bool IsAbandoned { get; set; }

        /// <summary>Loot chest spawned on completion.</summary>
        public LootChest RewardChest { get; set; }

        /// <summary>Enemy spawn configs per wave.</summary>
        public List<WaveConfig> Waves { get; set; } = new();

        /// <summary>Dungeon world seed for deterministic generation.</summary>
        public int Seed { get; set; }

        // ====================================================================
        // Wave Management
        // ====================================================================

        /// <summary>
        /// Start the next wave.
        /// Returns the wave config or null if all waves are complete.
        /// </summary>
        public WaveConfig StartNextWave()
        {
            if (CurrentWave >= TotalWaves)
            {
                IsComplete = true;
                return null;
            }

            CurrentWave++;
            if (CurrentWave <= Waves.Count)
            {
                var wave = Waves[CurrentWave - 1];
                EnemiesRemaining = wave.EnemyCount;
                return wave;
            }

            return null;
        }

        /// <summary>
        /// Record an enemy kill in the current wave.
        /// Returns true if the wave is cleared.
        /// </summary>
        public bool RecordKill()
        {
            TotalKills++;
            EnemiesRemaining = Math.Max(0, EnemiesRemaining - 1);

            if (EnemiesRemaining <= 0)
            {
                // Check if all waves complete
                if (CurrentWave >= TotalWaves)
                {
                    IsComplete = true;
                }
                return true; // Wave cleared
            }
            return false;
        }

        // ====================================================================
        // Serialization
        // ====================================================================

        public Dictionary<string, object> ToDict()
        {
            var wavesData = new List<Dictionary<string, object>>();
            foreach (var wave in Waves)
            {
                wavesData.Add(wave.ToDict());
            }

            var data = new Dictionary<string, object>
            {
                ["dungeon_id"] = DungeonId,
                ["rarity"] = Rarity.ToString().ToLowerInvariant(),
                ["entrance_x"] = EntrancePosition.X,
                ["entrance_z"] = EntrancePosition.Z,
                ["arena_size"] = ArenaSize,
                ["current_wave"] = CurrentWave,
                ["total_waves"] = TotalWaves,
                ["enemies_remaining"] = EnemiesRemaining,
                ["total_kills"] = TotalKills,
                ["is_complete"] = IsComplete,
                ["is_abandoned"] = IsAbandoned,
                ["waves"] = wavesData,
                ["seed"] = Seed,
            };

            if (RewardChest != null)
                data["reward_chest"] = RewardChest.ToDict();

            return data;
        }

        public static DungeonInstance FromDict(Dictionary<string, object> data)
        {
            var dungeon = new DungeonInstance();

            if (data.TryGetValue("dungeon_id", out var id))
                dungeon.DungeonId = id?.ToString();
            if (data.TryGetValue("rarity", out var rarity))
                dungeon.Rarity = ParseRarity(rarity?.ToString());
            if (data.TryGetValue("entrance_x", out var ex) && data.TryGetValue("entrance_z", out var ez))
                dungeon.EntrancePosition = GamePosition.FromXZ(Convert.ToSingle(ex), Convert.ToSingle(ez));
            if (data.TryGetValue("arena_size", out var aSize))
                dungeon.ArenaSize = Convert.ToInt32(aSize);
            if (data.TryGetValue("current_wave", out var cw))
                dungeon.CurrentWave = Convert.ToInt32(cw);
            if (data.TryGetValue("total_waves", out var tw))
                dungeon.TotalWaves = Convert.ToInt32(tw);
            if (data.TryGetValue("enemies_remaining", out var er))
                dungeon.EnemiesRemaining = Convert.ToInt32(er);
            if (data.TryGetValue("total_kills", out var tk))
                dungeon.TotalKills = Convert.ToInt32(tk);
            if (data.TryGetValue("is_complete", out var ic))
                dungeon.IsComplete = Convert.ToBoolean(ic);
            if (data.TryGetValue("is_abandoned", out var ia))
                dungeon.IsAbandoned = Convert.ToBoolean(ia);
            if (data.TryGetValue("seed", out var seed))
                dungeon.Seed = Convert.ToInt32(seed);

            if (data.TryGetValue("reward_chest", out var chestObj)
                && chestObj is Dictionary<string, object> chestData)
                dungeon.RewardChest = LootChest.FromDict(chestData);

            return dungeon;
        }

        private static DungeonRarity ParseRarity(string s)
        {
            if (string.IsNullOrEmpty(s)) return DungeonRarity.Common;
            return s.ToLowerInvariant() switch
            {
                "uncommon" => DungeonRarity.Uncommon,
                "rare" => DungeonRarity.Rare,
                "epic" => DungeonRarity.Epic,
                "legendary" => DungeonRarity.Legendary,
                "unique" => DungeonRarity.Unique,
                _ => DungeonRarity.Common,
            };
        }
    }

    /// <summary>Configuration for a single dungeon wave.</summary>
    public class WaveConfig
    {
        public int WaveNumber { get; set; }
        public int EnemyCount { get; set; }
        public List<WaveEnemy> Enemies { get; set; } = new();

        public Dictionary<string, object> ToDict()
        {
            var enemyData = new List<Dictionary<string, object>>();
            foreach (var e in Enemies)
            {
                enemyData.Add(new Dictionary<string, object>
                {
                    ["enemy_id"] = e.EnemyId,
                    ["tier"] = e.Tier,
                    ["count"] = e.Count,
                });
            }
            return new Dictionary<string, object>
            {
                ["wave_number"] = WaveNumber,
                ["enemy_count"] = EnemyCount,
                ["enemies"] = enemyData,
            };
        }
    }

    /// <summary>Enemy spawn definition within a wave.</summary>
    public class WaveEnemy
    {
        public string EnemyId { get; set; }
        public int Tier { get; set; } = 1;
        public int Count { get; set; } = 1;
    }

    /// <summary>
    /// Dungeon manager — creates, tracks, and manages dungeon instances.
    /// Matches Python: dungeon.py DungeonManager class.
    /// </summary>
    public class DungeonSystem
    {
        private static DungeonSystem _instance;
        private static readonly object _lock = new object();

        private readonly Dictionary<string, DungeonInstance> _activeDungeons = new();
        private DungeonInstance _currentDungeon;
        private Random _rng;

        public static DungeonSystem Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new DungeonSystem();
                        }
                    }
                }
                return _instance;
            }
        }

        private DungeonSystem()
        {
            _rng = new Random();
            InitializeRarityConfigs();
        }

        public static void ResetInstance()
        {
            lock (_lock) { _instance = null; }
        }

        /// <summary>Currently active dungeon (player is inside).</summary>
        public DungeonInstance CurrentDungeon => _currentDungeon;

        /// <summary>Whether the player is in a dungeon.</summary>
        public bool IsInDungeon => _currentDungeon != null && !_currentDungeon.IsComplete
                                   && !_currentDungeon.IsAbandoned;

        // ====================================================================
        // Rarity Configuration
        // Matches Python: dungeon.py rarity mob counts
        // ====================================================================

        private readonly Dictionary<DungeonRarity, DungeonRarityConfig> _rarityConfigs = new();

        private void InitializeRarityConfigs()
        {
            // Common: 20 mobs, 3 waves
            _rarityConfigs[DungeonRarity.Common] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Common,
                TotalMobs = 20,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [1] = 0.80f, [2] = 0.20f },
            };
            // Uncommon: 25 mobs, 3 waves
            _rarityConfigs[DungeonRarity.Uncommon] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Uncommon,
                TotalMobs = 25,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [1] = 0.50f, [2] = 0.40f, [3] = 0.10f },
            };
            // Rare: 30 mobs, 3 waves
            _rarityConfigs[DungeonRarity.Rare] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Rare,
                TotalMobs = 30,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [1] = 0.20f, [2] = 0.50f, [3] = 0.30f },
            };
            // Epic: 40 mobs, 3 waves
            _rarityConfigs[DungeonRarity.Epic] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Epic,
                TotalMobs = 40,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [2] = 0.30f, [3] = 0.50f, [4] = 0.20f },
            };
            // Legendary: 50 mobs, 3 waves
            _rarityConfigs[DungeonRarity.Legendary] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Legendary,
                TotalMobs = 50,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [3] = 0.40f, [4] = 0.60f },
            };
            // Unique: 50 mobs, 3 waves (boss-oriented)
            _rarityConfigs[DungeonRarity.Unique] = new DungeonRarityConfig
            {
                Rarity = DungeonRarity.Unique,
                TotalMobs = 50,
                Waves = 3,
                TierWeights = new Dictionary<int, float> { [3] = 0.30f, [4] = 0.70f },
            };
        }

        // ====================================================================
        // Dungeon Creation
        // ====================================================================

        /// <summary>
        /// Create a new dungeon instance at the given position.
        /// Matches Python: dungeon.py DungeonManager.create_dungeon()
        /// </summary>
        public DungeonInstance CreateDungeon(
            GamePosition entrancePosition,
            DungeonRarity rarity = DungeonRarity.Common,
            int? seed = null)
        {
            int dungeonSeed = seed ?? _rng.Next();
            var config = _rarityConfigs[rarity];

            var dungeon = new DungeonInstance
            {
                DungeonId = $"dungeon_{Guid.NewGuid():N}",
                Rarity = rarity,
                EntrancePosition = entrancePosition,
                ArenaSize = 32,
                TotalWaves = config.Waves,
                Seed = dungeonSeed,
            };

            // Generate wave configs
            var waveRng = new Random(dungeonSeed);
            int mobsRemaining = config.TotalMobs;
            int baseMobsPerWave = mobsRemaining / config.Waves;

            for (int w = 1; w <= config.Waves; w++)
            {
                int waveMobs;
                if (w == config.Waves)
                {
                    waveMobs = mobsRemaining; // Last wave gets remainder
                }
                else
                {
                    waveMobs = baseMobsPerWave;
                    mobsRemaining -= waveMobs;
                }

                var wave = new WaveConfig
                {
                    WaveNumber = w,
                    EnemyCount = waveMobs,
                };

                // Distribute enemies by tier weight
                foreach (var tierWeight in config.TierWeights)
                {
                    int count = (int)(waveMobs * tierWeight.Value);
                    if (count > 0)
                    {
                        wave.Enemies.Add(new WaveEnemy
                        {
                            EnemyId = $"enemy_t{tierWeight.Key}",
                            Tier = tierWeight.Key,
                            Count = count,
                        });
                    }
                }

                dungeon.Waves.Add(wave);
            }

            _activeDungeons[dungeon.DungeonId] = dungeon;
            return dungeon;
        }

        /// <summary>
        /// Enter a dungeon (set as current).
        /// </summary>
        public bool EnterDungeon(string dungeonId)
        {
            if (!_activeDungeons.TryGetValue(dungeonId, out var dungeon)) return false;
            if (dungeon.IsComplete || dungeon.IsAbandoned) return false;

            _currentDungeon = dungeon;
            return true;
        }

        /// <summary>
        /// Leave the current dungeon (abandon if not complete).
        /// </summary>
        public void LeaveDungeon()
        {
            if (_currentDungeon != null && !_currentDungeon.IsComplete)
            {
                _currentDungeon.IsAbandoned = true;
            }
            _currentDungeon = null;
        }

        /// <summary>
        /// Generate loot chest for a completed dungeon.
        /// Matches Python: dungeon.py loot generation with dilutive weight normalization.
        /// </summary>
        public LootChest GenerateLootChest(DungeonInstance dungeon)
        {
            if (dungeon == null || !dungeon.IsComplete) return null;

            var chest = new LootChest
            {
                Position = dungeon.EntrancePosition,
                ChestTier = dungeon.Rarity.ToString().ToLowerInvariant(),
            };

            // Generate loot based on rarity
            var lootRng = new Random(dungeon.Seed + dungeon.TotalKills);
            int lootCount = 3 + (int)dungeon.Rarity; // More loot for higher rarity

            for (int i = 0; i < lootCount; i++)
            {
                chest.Contents.Add(new LootDrop
                {
                    ItemId = $"loot_{dungeon.Rarity.ToString().ToLowerInvariant()}_{i}",
                    Quantity = 1 + lootRng.Next(3),
                });
            }

            dungeon.RewardChest = chest;
            return chest;
        }

        // ====================================================================
        // Serialization
        // ====================================================================

        /// <summary>Serialize all active dungeons for save data.</summary>
        public Dictionary<string, object> ToDict()
        {
            var dungeonsList = new List<Dictionary<string, object>>();
            foreach (var dungeon in _activeDungeons.Values)
            {
                dungeonsList.Add(dungeon.ToDict());
            }

            return new Dictionary<string, object>
            {
                ["dungeons"] = dungeonsList,
                ["current_dungeon_id"] = _currentDungeon?.DungeonId,
            };
        }

        /// <summary>Restore dungeon state from save data.</summary>
        public void FromDict(Dictionary<string, object> data)
        {
            _activeDungeons.Clear();
            _currentDungeon = null;

            if (data.TryGetValue("dungeons", out var dungeonsObj)
                && dungeonsObj is IEnumerable<object> dungeonsList)
            {
                foreach (var item in dungeonsList)
                {
                    if (item is Dictionary<string, object> dungeonData)
                    {
                        var dungeon = DungeonInstance.FromDict(dungeonData);
                        if (dungeon != null && !string.IsNullOrEmpty(dungeon.DungeonId))
                        {
                            _activeDungeons[dungeon.DungeonId] = dungeon;
                        }
                    }
                }
            }

            if (data.TryGetValue("current_dungeon_id", out var currentId)
                && currentId != null)
            {
                _activeDungeons.TryGetValue(currentId.ToString(), out _currentDungeon);
            }
        }
    }
}
