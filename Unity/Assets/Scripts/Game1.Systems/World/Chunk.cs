// ============================================================================
// Game1.Systems.World.Chunk
// Migrated from: systems/chunk.py (559 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// A single 16x16 tile chunk of the world. Supports infinite world generation
// through seed-based deterministic generation. Chunk (0,0) contains the origin.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Enums;
using Game1.Data.Models;
using Game1.Entities;
using Game1.Systems.Combat;

namespace Game1.Systems.World
{
    // ========================================================================
    // Enums
    // ========================================================================

    /// <summary>
    /// Chunk biome/danger types. Values match Python ChunkType enum exactly.
    /// </summary>
    public enum ChunkType
    {
        PeacefulForest,
        PeacefulQuarry,
        PeacefulCave,
        DangerousForest,
        DangerousQuarry,
        DangerousCave,
        RareHiddenForest,
        RareAncientQuarry,
        RareDeepCave,
        WaterLake,
        WaterRiver,
        WaterCursedSwamp
    }

    /// <summary>
    /// Extensions for ChunkType to handle JSON serialization and category queries.
    /// </summary>
    public static class ChunkTypeExtensions
    {
        private static readonly Dictionary<string, ChunkType> _fromJson = new(StringComparer.OrdinalIgnoreCase)
        {
            ["peaceful_forest"]     = ChunkType.PeacefulForest,
            ["peaceful_quarry"]     = ChunkType.PeacefulQuarry,
            ["peaceful_cave"]       = ChunkType.PeacefulCave,
            ["dangerous_forest"]    = ChunkType.DangerousForest,
            ["dangerous_quarry"]    = ChunkType.DangerousQuarry,
            ["dangerous_cave"]      = ChunkType.DangerousCave,
            ["rare_hidden_forest"]  = ChunkType.RareHiddenForest,
            ["rare_ancient_quarry"] = ChunkType.RareAncientQuarry,
            ["rare_deep_cave"]      = ChunkType.RareDeepCave,
            ["water_lake"]          = ChunkType.WaterLake,
            ["water_river"]         = ChunkType.WaterRiver,
            ["water_cursed_swamp"]  = ChunkType.WaterCursedSwamp,
        };

        private static readonly Dictionary<ChunkType, string> _toJson = new()
        {
            [ChunkType.PeacefulForest]    = "peaceful_forest",
            [ChunkType.PeacefulQuarry]    = "peaceful_quarry",
            [ChunkType.PeacefulCave]      = "peaceful_cave",
            [ChunkType.DangerousForest]   = "dangerous_forest",
            [ChunkType.DangerousQuarry]   = "dangerous_quarry",
            [ChunkType.DangerousCave]     = "dangerous_cave",
            [ChunkType.RareHiddenForest]  = "rare_hidden_forest",
            [ChunkType.RareAncientQuarry] = "rare_ancient_quarry",
            [ChunkType.RareDeepCave]      = "rare_deep_cave",
            [ChunkType.WaterLake]         = "water_lake",
            [ChunkType.WaterRiver]        = "water_river",
            [ChunkType.WaterCursedSwamp]  = "water_cursed_swamp",
        };

        public static string ToJsonString(this ChunkType type) =>
            _toJson.TryGetValue(type, out var s) ? s : "peaceful_forest";

        public static ChunkType FromJsonString(string json) =>
            !string.IsNullOrEmpty(json) && _fromJson.TryGetValue(json, out var t)
                ? t
                : ChunkType.PeacefulForest;

        public static bool IsWater(this ChunkType type) =>
            type == ChunkType.WaterLake ||
            type == ChunkType.WaterRiver ||
            type == ChunkType.WaterCursedSwamp;

        public static bool IsPeaceful(this ChunkType type) =>
            type == ChunkType.PeacefulForest ||
            type == ChunkType.PeacefulQuarry ||
            type == ChunkType.PeacefulCave;

        public static bool IsDangerous(this ChunkType type) =>
            type == ChunkType.DangerousForest ||
            type == ChunkType.DangerousQuarry ||
            type == ChunkType.DangerousCave;

        public static bool IsRare(this ChunkType type) =>
            type == ChunkType.RareHiddenForest ||
            type == ChunkType.RareAncientQuarry ||
            type == ChunkType.RareDeepCave;

        public static bool IsForest(this ChunkType type) =>
            type == ChunkType.PeacefulForest ||
            type == ChunkType.DangerousForest ||
            type == ChunkType.RareHiddenForest;

        public static bool IsQuarry(this ChunkType type) =>
            type == ChunkType.PeacefulQuarry ||
            type == ChunkType.DangerousQuarry ||
            type == ChunkType.RareAncientQuarry;

        public static bool IsCave(this ChunkType type) =>
            type == ChunkType.PeacefulCave ||
            type == ChunkType.DangerousCave ||
            type == ChunkType.RareDeepCave;
    }

    /// <summary>
    /// Types of crafting stations. Matches Python StationType enum.
    /// </summary>
    public enum StationType
    {
        Smithing,
        Alchemy,
        Refining,
        Engineering,
        Adornments
    }

    public static class StationTypeExtensions
    {
        private static readonly Dictionary<string, StationType> _fromJson = new(StringComparer.OrdinalIgnoreCase)
        {
            ["smithing"]    = StationType.Smithing,
            ["alchemy"]     = StationType.Alchemy,
            ["refining"]    = StationType.Refining,
            ["engineering"] = StationType.Engineering,
            ["adornments"]  = StationType.Adornments,
            ["SMITHING"]    = StationType.Smithing,
            ["ALCHEMY"]     = StationType.Alchemy,
            ["REFINING"]    = StationType.Refining,
            ["ENGINEERING"] = StationType.Engineering,
            ["ADORNMENTS"]  = StationType.Adornments,
        };

        private static readonly Dictionary<StationType, string> _toJson = new()
        {
            [StationType.Smithing]    = "smithing",
            [StationType.Alchemy]     = "alchemy",
            [StationType.Refining]    = "refining",
            [StationType.Engineering] = "engineering",
            [StationType.Adornments]  = "adornments",
        };

        public static string ToJsonString(this StationType type) =>
            _toJson.TryGetValue(type, out var s) ? s : "smithing";

        public static StationType FromJsonString(string json) =>
            !string.IsNullOrEmpty(json) && _fromJson.TryGetValue(json, out var t)
                ? t
                : StationType.Smithing;
    }

    /// <summary>
    /// Types of player-placed entities. Matches Python PlacedEntityType enum.
    /// </summary>
    public enum PlacedEntityType
    {
        Turret,
        Trap,
        Bomb,
        UtilityDevice,
        CraftingStation,
        TrainingDummy,
        Barrier,
        DroppedItem
    }

    public static class PlacedEntityTypeExtensions
    {
        private static readonly Dictionary<string, PlacedEntityType> _fromJson = new(StringComparer.OrdinalIgnoreCase)
        {
            ["turret"]          = PlacedEntityType.Turret,
            ["TURRET"]          = PlacedEntityType.Turret,
            ["trap"]            = PlacedEntityType.Trap,
            ["TRAP"]            = PlacedEntityType.Trap,
            ["bomb"]            = PlacedEntityType.Bomb,
            ["BOMB"]            = PlacedEntityType.Bomb,
            ["utility_device"]  = PlacedEntityType.UtilityDevice,
            ["UTILITY_DEVICE"]  = PlacedEntityType.UtilityDevice,
            ["crafting_station"] = PlacedEntityType.CraftingStation,
            ["CRAFTING_STATION"] = PlacedEntityType.CraftingStation,
            ["training_dummy"]  = PlacedEntityType.TrainingDummy,
            ["TRAINING_DUMMY"]  = PlacedEntityType.TrainingDummy,
            ["barrier"]         = PlacedEntityType.Barrier,
            ["BARRIER"]         = PlacedEntityType.Barrier,
            ["dropped_item"]    = PlacedEntityType.DroppedItem,
            ["DROPPED_ITEM"]    = PlacedEntityType.DroppedItem,
        };

        public static string ToJsonString(this PlacedEntityType type) => type.ToString().ToUpperInvariant();

        public static PlacedEntityType FromJsonString(string json) =>
            !string.IsNullOrEmpty(json) && _fromJson.TryGetValue(json, out var t)
                ? t
                : PlacedEntityType.Turret;
    }

    // ========================================================================
    // Tile / Station / Entity Data Classes
    // ========================================================================

    /// <summary>
    /// A single world tile. Matches Python WorldTile dataclass.
    /// </summary>
    public class WorldTile
    {
        public GamePosition Position { get; set; }
        public TileType TileType { get; set; }
        public string OccupiedBy { get; set; }
        public string Ownership { get; set; }
        public bool Walkable { get; set; } = true;

        public WorldTile() { }

        public WorldTile(GamePosition position, TileType tileType, bool walkable = true)
        {
            Position = position;
            TileType = tileType;
            Walkable = walkable;
        }
    }

    /// <summary>
    /// A crafting station placed in the world.
    /// </summary>
    public class CraftingStationInstance
    {
        public GamePosition Position { get; set; }
        public StationType StationType { get; set; }
        public int StationTier { get; set; } = 1;

        public CraftingStationInstance() { }

        public CraftingStationInstance(GamePosition position, StationType stationType, int tier)
        {
            Position = position;
            StationType = stationType;
            StationTier = tier;
        }

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["position"] = new Dictionary<string, object>
                {
                    ["x"] = Position.X, ["y"] = Position.Y, ["z"] = Position.Z
                },
                ["station_type"] = StationType.ToJsonString().ToUpperInvariant(),
                ["tier"] = StationTier,
            };
        }

        public static CraftingStationInstance FromSaveData(Dictionary<string, object> data)
        {
            var posDict = data["position"] as Dictionary<string, object>;
            float px = Convert.ToSingle(posDict["x"]);
            float py = Convert.ToSingle(posDict["y"]);
            float pz = Convert.ToSingle(posDict["z"]);

            return new CraftingStationInstance
            {
                Position = new GamePosition(px, py, pz),
                StationType = StationTypeExtensions.FromJsonString(data["station_type"]?.ToString()),
                StationTier = data.ContainsKey("tier") ? Convert.ToInt32(data["tier"]) : 1,
            };
        }
    }

    /// <summary>
    /// A player-placed entity in the world (turret, trap, barrier, etc.).
    /// Migrated from Python PlacedEntity dataclass.
    /// </summary>
    public class PlacedEntity
    {
        public string EntityId { get; set; }
        public string ItemId { get; set; }
        public PlacedEntityType EntityType { get; set; }
        public GamePosition Position { get; set; }
        public int Tier { get; set; } = 1;
        public float Health { get; set; } = 100f;
        public float MaxHealth { get; set; } = 100f;
        public string Owner { get; set; }

        // Turret-specific
        public float Range { get; set; } = 5.0f;
        public float Damage { get; set; } = 20.0f;
        public float AttackSpeed { get; set; } = 1.0f;

        // Lifetime management
        public float Lifetime { get; set; } = 300.0f;
        public float TimeRemaining { get; set; } = 300.0f;

        // Tag system
        public List<string> Tags { get; set; } = new();
        public Dictionary<string, object> EffectParams { get; set; } = new();
        public Dictionary<string, object> CraftedStats { get; set; } = new();
        public Dictionary<string, object> Properties { get; set; } = new();

        // Status
        public bool Triggered { get; set; }

        public PlacedEntity()
        {
            EntityId = Guid.NewGuid().ToString("N")[..12];
        }

        /// <summary>
        /// Apply crafted stats bonuses. Matches Python _apply_crafted_stats().
        /// Power: +X% damage, Durability: +X% lifetime, Efficiency: +X% attack speed.
        /// </summary>
        public void ApplyCraftedStats()
        {
            if (CraftedStats == null || CraftedStats.Count == 0) return;

            float baseDamage = Damage;
            float baseLifetime = Lifetime;
            float baseAttackSpeed = AttackSpeed;

            if (CraftedStats.TryGetValue("power", out var powerObj))
            {
                float power = Convert.ToSingle(powerObj);
                if (power > 0)
                    Damage = baseDamage * (1f + power / 100f);
            }

            if (CraftedStats.TryGetValue("durability", out var durObj))
            {
                float durability = Convert.ToSingle(durObj);
                if (durability > 0)
                {
                    Lifetime = baseLifetime * (1f + durability / 100f);
                    TimeRemaining = Lifetime;
                }
            }

            if (CraftedStats.TryGetValue("efficiency", out var effObj))
            {
                float efficiency = Convert.ToSingle(effObj);
                if (efficiency > 0)
                {
                    float effective = MathF.Min(efficiency, 900f);
                    AttackSpeed = baseAttackSpeed * (1f + effective / 100f);
                }
            }

            // Barrier health by tier: T1=50, T2=100, T3=200, T4=400
            if (EntityType == PlacedEntityType.Barrier)
            {
                Health = Tier switch
                {
                    1 => 50f,
                    2 => 100f,
                    3 => 200f,
                    4 => 400f,
                    _ => 50f,
                };
                MaxHealth = Health;
            }
        }

        /// <summary>
        /// Take damage and return true if destroyed (health &lt;= 0).
        /// </summary>
        public bool TakeDamage(float damage)
        {
            Health -= damage;
            if (Health <= 0f)
            {
                Health = 0f;
                return true;
            }
            return false;
        }

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["position"] = new Dictionary<string, object>
                {
                    ["x"] = Position.X, ["y"] = Position.Y, ["z"] = Position.Z
                },
                ["item_id"] = ItemId,
                ["entity_type"] = EntityType.ToJsonString(),
                ["tier"] = Tier,
                ["health"] = Health,
                ["owner"] = Owner,
                ["time_remaining"] = TimeRemaining,
                ["range"] = Range,
                ["damage"] = Damage,
                ["attack_speed"] = AttackSpeed,
                ["tags"] = Tags,
                ["effect_params"] = EffectParams,
            };
        }

        public static PlacedEntity FromSaveData(Dictionary<string, object> data)
        {
            var posDict = data["position"] as Dictionary<string, object>;
            float px = Convert.ToSingle(posDict["x"]);
            float py = Convert.ToSingle(posDict["y"]);
            float pz = Convert.ToSingle(posDict["z"]);

            var entity = new PlacedEntity
            {
                Position = new GamePosition(px, py, pz),
                ItemId = data.TryGetValue("item_id", out var id) ? id?.ToString() : "",
                EntityType = PlacedEntityTypeExtensions.FromJsonString(
                    data.TryGetValue("entity_type", out var et) ? et?.ToString() : "TURRET"),
                Tier = data.TryGetValue("tier", out var tier) ? Convert.ToInt32(tier) : 1,
                Health = data.TryGetValue("health", out var hp) ? Convert.ToSingle(hp) : 100f,
                Owner = data.TryGetValue("owner", out var owner) ? owner?.ToString() : null,
                TimeRemaining = data.TryGetValue("time_remaining", out var tr) ? Convert.ToSingle(tr) : 300f,
                Range = data.TryGetValue("range", out var rng) ? Convert.ToSingle(rng) : 5.0f,
                Damage = data.TryGetValue("damage", out var dmg) ? Convert.ToSingle(dmg) : 20.0f,
                AttackSpeed = data.TryGetValue("attack_speed", out var spd) ? Convert.ToSingle(spd) : 1.0f,
            };

            entity.MaxHealth = entity.Health;
            return entity;
        }
    }

    /// <summary>
    /// A dungeon entrance in the world.
    /// </summary>
    public class DungeonEntrance
    {
        public GamePosition Position { get; set; }
        public DungeonRarity Rarity { get; set; }
        public bool Discovered { get; set; }
    }

    // ========================================================================
    // Chunk
    // ========================================================================

    /// <summary>
    /// A 16x16 tile chunk of the world. Deterministically generated from seed.
    /// Coordinates use centered system: chunk (0,0) contains the world origin.
    /// </summary>
    public class Chunk
    {
        public int ChunkX { get; }
        public int ChunkY { get; }
        public int Seed { get; }
        public ChunkType Type { get; set; }
        public bool IsGenerated { get; set; }
        public bool IsLoaded { get; set; }

        /// <summary>Tiles keyed by "x,y,z" string. Matches Python dict[str, WorldTile].</summary>
        public Dictionary<string, WorldTile> Tiles { get; } = new();

        /// <summary>Natural resources in this chunk.</summary>
        public List<NaturalResourceInstance> Resources { get; } = new();

        /// <summary>Enemies spawned in this chunk.</summary>
        public List<Enemy> Enemies { get; } = new();

        /// <summary>Optional dungeon entrance in this chunk.</summary>
        public DungeonEntrance DungeonEntrance { get; set; }

        /// <summary>Game time when chunk was last unloaded (for respawn calculation).</summary>
        public float? UnloadTimestamp { get; set; }

        // Modification tracking for save system
        private bool _modified;
        private readonly Dictionary<string, Dictionary<string, object>> _resourceModifications = new();

        private readonly System.Random _rng;

        public Chunk(int chunkX, int chunkY, int size = 16, BiomeGenerator biomeGenerator = null)
        {
            ChunkX = chunkX;
            ChunkY = chunkY;

            // Get seed deterministically from biome generator or compute manually
            if (biomeGenerator != null)
            {
                Seed = biomeGenerator.GetChunkSeed(chunkX, chunkY);
                Type = biomeGenerator.DetermineChunkType(chunkX, chunkY);
            }
            else
            {
                Seed = HashCode.Combine(chunkX, chunkY, 42);
                Type = ChunkType.PeacefulForest;
            }

            _rng = new System.Random(Seed);
            IsGenerated = true;
            IsLoaded = true;
        }

        /// <summary>
        /// Get the world-space center of this chunk.
        /// Returns (chunkX * size + size/2, chunkY * size + size/2).
        /// </summary>
        public (float X, float Z) GetWorldCenter()
        {
            int size = GameConfig.ChunkSize;
            return (ChunkX * size + size / 2f, ChunkY * size + size / 2f);
        }

        /// <summary>
        /// Check if a world position falls within this chunk.
        /// </summary>
        public bool ContainsWorldPosition(float worldX, float worldZ)
        {
            int size = GameConfig.ChunkSize;
            float startX = ChunkX * size;
            float startZ = ChunkY * size;
            return worldX >= startX && worldX < startX + size &&
                   worldZ >= startZ && worldZ < startZ + size;
        }

        /// <summary>
        /// Generate tiles for this chunk. Called during construction.
        /// </summary>
        public void GenerateTiles()
        {
            int size = GameConfig.ChunkSize;
            int startX = ChunkX * size;
            int startZ = ChunkY * size;

            if (Type.IsWater())
            {
                GenerateWaterTiles(startX, startZ, size);
            }
            else
            {
                GenerateLandTiles(startX, startZ, size);
            }

            // Spawn natural resources after tiles (matches Python chunk.py)
            GenerateResources();

            // Spawn enemies based on chunk danger level (matches Python combat_manager.py)
            GenerateEnemies();
        }

        private void GenerateLandTiles(int startX, int startZ, int size)
        {
            bool isStone = Type.IsQuarry() || Type.IsCave();
            var baseTile = isStone ? TileType.Stone : TileType.Grass;

            for (int x = startX; x < startX + size; x++)
            {
                for (int z = startZ; z < startZ + size; z++)
                {
                    var pos = GamePosition.FromXZ(x, z);
                    var tileType = _rng.NextDouble() < 0.1 ? TileType.DirtPath : baseTile;
                    string key = $"{x},{z},0";
                    Tiles[key] = new WorldTile(pos, tileType, walkable: true);
                }
            }
        }

        private void GenerateWaterTiles(int startX, int startZ, int size)
        {
            bool isSwamp = Type == ChunkType.WaterCursedSwamp;
            bool isLake = Type == ChunkType.WaterLake;
            int centerX = size / 2;
            int centerZ = size / 2;

            for (int localX = 0; localX < size; localX++)
            {
                for (int localZ = 0; localZ < size; localZ++)
                {
                    int x = startX + localX;
                    int z = startZ + localZ;
                    var pos = GamePosition.FromXZ(x, z);
                    TileType tileType;

                    if (isLake)
                    {
                        float dist = MathF.Sqrt(
                            (localX - centerX) * (localX - centerX) +
                            (localZ - centerZ) * (localZ - centerZ));

                        if (localX < 2 || localX >= size - 2 || localZ < 2 || localZ >= size - 2)
                            tileType = TileType.Grass;
                        else if (dist < 5f)
                            tileType = TileType.Water;
                        else
                            tileType = TileType.Grass;
                    }
                    else if (isSwamp)
                    {
                        bool isPath = Math.Abs(localX - centerX) < 2 || Math.Abs(localZ - centerZ) < 2;
                        if (isPath)
                            tileType = TileType.DirtPath;
                        else
                            tileType = _rng.NextDouble() < 0.5 ? TileType.Water : TileType.DirtPath;
                    }
                    else // River
                    {
                        int distFromCenter = Math.Abs(localX - size / 2);
                        tileType = (distFromCenter < 3 && _rng.NextDouble() < 0.8)
                            ? TileType.Water
                            : TileType.Grass;
                    }

                    string key = $"{x},{z},0";
                    bool walkable = tileType != TileType.Water;
                    Tiles[key] = new WorldTile(pos, tileType, walkable);
                }
            }
        }

        // ====================================================================
        // Resource Spawning (matches Python chunk.py spawn_resources)
        // ====================================================================

        /// <summary>
        /// Spawn natural resources in this chunk based on chunk type and danger level.
        /// Peaceful: 3-5 T1 resources. Dangerous: 4-7 T1-T2. Rare: 3-5 T1-T3.
        /// Safe zone (~3 chunk radius from origin) has fewer resources.
        /// </summary>
        public void GenerateResources()
        {
            Resources.Clear();

            int size = GameConfig.ChunkSize;
            int startX = ChunkX * size;
            int startZ = ChunkY * size;

            // Skip water chunks (they get fishing spots instead)
            if (Type.IsWater()) return;

            // Determine resource count and tier range based on chunk type
            int minResources, maxResources, maxTier;

            if (Type.IsDangerous())
            {
                minResources = 4; maxResources = 7; maxTier = 2;
            }
            else if (Type.IsRare())
            {
                minResources = 3; maxResources = 5; maxTier = 3;
            }
            else // Peaceful
            {
                minResources = 3; maxResources = 5; maxTier = 1;
            }

            // Safe zone around origin — reduce resources near spawn
            float distToOrigin = MathF.Sqrt(ChunkX * ChunkX + ChunkY * ChunkY);
            if (distToOrigin < 2f)
            {
                minResources = 2;
                maxResources = 3;
            }

            int resourceCount = _rng.Next(minResources, maxResources + 1);
            var occupied = new HashSet<string>();

            // Try ResourceNodeDatabase first, fall back to hardcoded
            var resDb = Game1.Data.Databases.ResourceNodeDatabase.Instance;
            bool dbLoaded = resDb != null && resDb.Loaded;

            for (int i = 0; i < resourceCount; i++)
            {
                // Find valid position (up to 10 attempts)
                GamePosition pos = null;
                for (int attempt = 0; attempt < 10; attempt++)
                {
                    int localX = _rng.Next(1, size - 1);
                    int localZ = _rng.Next(1, size - 1);
                    int worldX = startX + localX;
                    int worldZ = startZ + localZ;
                    string key = $"{worldX},{worldZ}";

                    if (occupied.Contains(key)) continue;
                    occupied.Add(key);
                    pos = GamePosition.FromXZ(worldX, worldZ);
                    break;
                }

                if (pos == null) continue;

                // Determine resource tier (weighted toward lower tiers)
                int tier = _rng.Next(1, maxTier + 1);
                if (tier > 1 && _rng.NextDouble() < 0.5) tier--; // Bias toward lower tiers

                // Create resource instance
                NaturalResourceInstance resource = _createResource(pos, tier, dbLoaded, resDb);
                if (resource != null)
                    Resources.Add(resource);
            }
        }

        private NaturalResourceInstance _createResource(GamePosition pos, int tier,
            bool dbLoaded, Game1.Data.Databases.ResourceNodeDatabase resDb)
        {
            // Determine category based on chunk type
            string category;
            if (Type.IsQuarry() || Type.IsCave())
                category = _rng.NextDouble() < 0.7 ? "ore" : "stone";
            else
                category = _rng.NextDouble() < 0.6 ? "tree" : "ore";

            if (dbLoaded)
            {
                var candidates = resDb.GetResourcesForCategory(category, 1, tier);
                if (candidates.Count > 0)
                {
                    var nodeDef = candidates[_rng.Next(candidates.Count)];
                    // Create from database definition with proper loot table
                    var resource = new NaturalResourceInstance(pos, nodeDef.NodeId, nodeDef.Tier);
                    resource.MaxHp = nodeDef.Health;
                    resource.CurrentHp = nodeDef.Health;
                    resource.RequiredTool = nodeDef.ToolRequired ?? "pickaxe";
                    resource.Respawns = true;
                    resource.RespawnTimer = nodeDef.RespawnTime > 0 ? nodeDef.RespawnTime : 60f;

                    // Build loot table from database drops
                    foreach (var drop in nodeDef.Drops)
                    {
                        resource.LootTable.Add(new LootDrop(
                            drop.MaterialId,
                            drop.QuantityMin,
                            drop.QuantityMax,
                            drop.Chance));
                    }
                    return resource;
                }
            }

            // Fallback: hardcoded resources
            return _createFallbackResource(pos, tier, category);
        }

        private NaturalResourceInstance _createFallbackResource(GamePosition pos, int tier, string category)
        {
            string resourceId;
            string tool;
            string dropId;

            switch (category)
            {
                case "tree":
                    resourceId = tier switch { 1 => "oak_tree", 2 => "ash_tree", 3 => "ironwood_tree", _ => "oak_tree" };
                    tool = "axe";
                    dropId = tier switch { 1 => "oak_log", 2 => "ash_log", 3 => "ironwood_log", _ => "oak_log" };
                    break;
                case "ore":
                    resourceId = tier switch { 1 => "copper_vein", 2 => "iron_vein", 3 => "mithril_vein", _ => "copper_vein" };
                    tool = "pickaxe";
                    dropId = tier switch { 1 => "copper_ore", 2 => "iron_ore", 3 => "mithril_ore", _ => "copper_ore" };
                    break;
                default: // stone
                    resourceId = tier switch { 1 => "limestone_deposit", 2 => "granite_deposit", 3 => "obsidian_deposit", _ => "limestone_deposit" };
                    tool = "pickaxe";
                    dropId = tier switch { 1 => "limestone", 2 => "granite", 3 => "obsidian", _ => "limestone" };
                    break;
            }

            var resource = new NaturalResourceInstance(pos, resourceId, tier);
            resource.RequiredTool = tool;
            resource.Respawns = category == "tree";
            resource.RespawnTimer = 60f;

            // Add hardcoded loot drop
            resource.LootTable.Add(new LootDrop(dropId, 2, 5, 1.0f));
            return resource;
        }

        // ====================================================================
        // Enemy Spawning (matches Python combat_manager.py spawn_enemies_in_chunk)
        // ====================================================================

        /// <summary>
        /// Spawn enemies in this chunk based on chunk type and danger level.
        /// Peaceful: 0-1 T1 (low chance). Dangerous: 1-3 T1-T2. Rare: 1-2 T2-T3.
        /// Safe zone (~2 chunks from origin) = no enemies.
        /// Max 3 per chunk (matches Python MaxEnemiesPerChunk).
        /// </summary>
        public void GenerateEnemies()
        {
            Enemies.Clear();

            int size = GameConfig.ChunkSize;
            int startX = ChunkX * size;
            int startZ = ChunkY * size;

            // No enemies in water chunks
            if (Type.IsWater()) return;

            // Safe zone: no enemies within 15 tiles of origin (matches Python safe_zone_radius=15)
            float centerX = ChunkX * size + size / 2f;
            float centerZ = ChunkY * size + size / 2f;
            float distToOrigin = MathF.Sqrt(centerX * centerX + centerZ * centerZ);
            if (distToOrigin <= 15f) return;

            // Determine enemy count and tier range based on chunk danger level
            // Matches Python: peaceful→T1 only, dangerous→T1-T3, rare→T1-T4
            int minEnemies, maxEnemies, maxTier;

            if (Type.IsDangerous())
            {
                minEnemies = 1; maxEnemies = 3; maxTier = 3;
            }
            else if (Type.IsRare())
            {
                minEnemies = 1; maxEnemies = 2; maxTier = 4;
            }
            else // Peaceful
            {
                // Low chance of a single T1 enemy in peaceful chunks
                if (_rng.NextDouble() > 0.4) return; // 60% chance of no enemies
                minEnemies = 0; maxEnemies = 1; maxTier = 1;
            }

            int enemyCount = _rng.Next(minEnemies, maxEnemies + 1);
            if (enemyCount <= 0) return;

            // Cap at 3 per chunk
            enemyCount = Math.Min(enemyCount, 3);

            var enemyDb = EnemyDatabaseAdapter.Instance;
            bool dbLoaded = enemyDb != null && enemyDb.Loaded;

            var occupied = new HashSet<string>();

            for (int i = 0; i < enemyCount; i++)
            {
                // Find valid spawn position (avoid edges, 2 tile buffer)
                GamePosition pos = null;
                for (int attempt = 0; attempt < 10; attempt++)
                {
                    int localX = _rng.Next(2, size - 2);
                    int localZ = _rng.Next(2, size - 2);
                    int worldX = startX + localX;
                    int worldZ = startZ + localZ;
                    string key = $"{worldX},{worldZ}";

                    if (occupied.Contains(key)) continue;
                    occupied.Add(key);
                    pos = GamePosition.FromXZ(worldX, worldZ);
                    break;
                }

                if (pos == null) continue;

                // Pick tier (weighted toward lower)
                int tier = _rng.Next(1, maxTier + 1);
                if (tier > 1 && _rng.NextDouble() < 0.5) tier--;

                // Create enemy from database or fallback
                Enemy enemy = _createEnemy(pos, tier, dbLoaded, enemyDb);
                if (enemy != null)
                    Enemies.Add(enemy);
            }
        }

        private Enemy _createEnemy(GamePosition pos, int tier,
            bool dbLoaded, EnemyDatabaseAdapter enemyDb)
        {
            if (dbLoaded)
            {
                // Try to get a random enemy of this tier from the database
                var spawnDef = enemyDb.GetRandomEnemy(tier, _rng);
                if (spawnDef != null)
                {
                    var fullDef = enemyDb.GetEnemyDefinition(spawnDef.EnemyId);
                    if (fullDef != null)
                    {
                        return new Enemy(fullDef, pos);
                    }
                }
            }

            // Fallback: create a basic enemy definition if database not loaded
            var fallbackDef = new EnemyDefinition
            {
                EnemyId = $"wild_beast_t{tier}",
                Name = tier switch
                {
                    1 => "Wild Beast",
                    2 => "Dire Beast",
                    3 => "Elder Beast",
                    _ => "Wild Beast"
                },
                Tier = tier,
                Category = "beast",
                Behavior = "passive_patrol",
                MaxHealth = tier switch { 1 => 50f, 2 => 120f, 3 => 250f, _ => 50f },
                DamageMin = tier switch { 1 => 5f, 2 => 12f, 3 => 25f, _ => 5f },
                DamageMax = tier switch { 1 => 10f, 2 => 20f, 3 => 40f, _ => 10f },
                Defense = tier switch { 1 => 2f, 2 => 5f, 3 => 10f, _ => 2f },
                Speed = 2.0f,
                AggroRange = 5f,
                AttackSpeed = 1.0f,
                Drops = new System.Collections.Generic.List<DropDefinition>
                {
                    new DropDefinition
                    {
                        MaterialId = "beast_hide",
                        QuantityMin = 1,
                        QuantityMax = tier + 1,
                        Chance = 0.75f
                    }
                }
            };

            return new Enemy(fallbackDef, pos);
        }

        // ====================================================================
        // Modification Tracking (for save system)
        // ====================================================================

        /// <summary>
        /// Mark a resource as modified for save tracking.
        /// </summary>
        public void MarkResourceModified(NaturalResourceInstance resource)
        {
            int localX = (int)MathF.Floor(resource.Position.X) - (ChunkX * GameConfig.ChunkSize);
            int localZ = (int)MathF.Floor(resource.Position.Z) - (ChunkY * GameConfig.ChunkSize);
            string localKey = $"{localX},{localZ}";

            _resourceModifications[localKey] = new Dictionary<string, object>
            {
                ["local_x"] = localX,
                ["local_y"] = localZ,
                ["resource_id"] = resource.ResourceId,
                ["current_hp"] = resource.CurrentHp,
                ["max_hp"] = resource.MaxHp,
                ["depleted"] = resource.IsDepleted,
                ["time_until_respawn"] = resource.TimeUntilRespawn,
            };
            _modified = true;
        }

        /// <summary>Check if this chunk has modifications worth saving.</summary>
        public bool HasModifications() => _modified || DungeonEntrance != null;

        /// <summary>
        /// Get save data for this chunk's modifications.
        /// </summary>
        public Dictionary<string, object> GetSaveData()
        {
            if (!HasModifications()) return null;

            var data = new Dictionary<string, object>
            {
                ["chunk_x"] = ChunkX,
                ["chunk_y"] = ChunkY,
                ["chunk_type"] = Type.ToJsonString(),
            };

            if (_resourceModifications.Count > 0)
            {
                var modList = new List<Dictionary<string, object>>(_resourceModifications.Values);
                data["modified_resources"] = modList;
            }

            if (DungeonEntrance != null)
            {
                data["dungeon_entrance"] = new Dictionary<string, object>
                {
                    ["position"] = new Dictionary<string, object>
                    {
                        ["x"] = DungeonEntrance.Position.X,
                        ["y"] = DungeonEntrance.Position.Y,
                        ["z"] = DungeonEntrance.Position.Z,
                    },
                    ["rarity"] = DungeonEntrance.Rarity.ToString().ToLowerInvariant(),
                };
            }

            if (UnloadTimestamp.HasValue)
                data["unload_timestamp"] = UnloadTimestamp.Value;

            return data;
        }

        /// <summary>
        /// Restore modifications from save data, advancing respawn timers by elapsed time.
        /// </summary>
        public void RestoreModifications(Dictionary<string, object> saveData, float elapsedTime = 0f)
        {
            // This would be called after resources are spawned to overlay modifications
            // Implementation depends on resource list being populated first
            _modified = true;
        }

        /// <summary>
        /// Prepare chunk for unloading by recording the game timestamp.
        /// </summary>
        public void PrepareForUnload(float gameTime)
        {
            UnloadTimestamp = gameTime;

            // Mark any changed resources
            foreach (var resource in Resources)
            {
                if (resource.CurrentHp < resource.MaxHp || resource.IsDepleted || resource.TimeUntilRespawn > 0f)
                {
                    MarkResourceModified(resource);
                }
            }
        }
    }
}
