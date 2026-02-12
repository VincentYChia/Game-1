// Game1.Data.Models.World
// Migrated from: data/models/world.py (526 lines)
// Phase: 1 - Foundation
// Contains: WorldTile, LootDrop, CraftingStation, PlacedEntity, DungeonEntrance

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Game1.Data.Enums;
using Game1.Data.Constants;

namespace Game1.Data.Models
{
    /// <summary>
    /// A single world tile. Color lookup deferred to Phase 2 (config injection).
    /// </summary>
    [Serializable]
    public class WorldTile
    {
        [JsonProperty("position")]
        public GamePosition Position { get; set; }

        [JsonProperty("tileType")]
        public TileType TileType { get; set; }

        [JsonProperty("occupiedBy")]
        public string OccupiedBy { get; set; }

        [JsonProperty("ownership")]
        public string Ownership { get; set; }

        [JsonProperty("walkable")]
        public bool Walkable { get; set; } = true;

        /// <summary>
        /// Get display color for this tile.
        /// Dirt is hardcoded (139, 69, 19). Other colors use defaults until config is injected.
        /// </summary>
        public (int R, int G, int B) GetColor()
        {
            return TileType switch
            {
                TileType.Grass => (34, 139, 34),
                TileType.Stone => (128, 128, 128),
                TileType.Water => (30, 144, 255),
                TileType.Dirt => (139, 69, 19),
                _ => (34, 139, 34)
            };
        }
    }

    /// <summary>
    /// Loot drop definition. Pure data.
    /// </summary>
    [Serializable]
    public class LootDrop
    {
        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("minQuantity")]
        public int MinQuantity { get; set; }

        [JsonProperty("maxQuantity")]
        public int MaxQuantity { get; set; }

        [JsonProperty("chance")]
        public float Chance { get; set; } = 1.0f;
    }

    /// <summary>
    /// A placed crafting station with color lookup.
    /// Color Constants: SMITHING (180,60,60), ALCHEMY (60,180,60), REFINING (180,120,60),
    /// ENGINEERING (60,120,180), ADORNMENTS (180,60,180), Default (150,150,150)
    /// </summary>
    [Serializable]
    public class CraftingStation
    {
        [JsonProperty("position")]
        public GamePosition Position { get; set; }

        [JsonProperty("stationType")]
        public StationType StationType { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        public (int R, int G, int B) GetColor()
        {
            return StationType switch
            {
                StationType.Smithing => (180, 60, 60),
                StationType.Alchemy => (60, 180, 60),
                StationType.Refining => (180, 120, 60),
                StationType.Engineering => (60, 120, 180),
                StationType.Adornments => (180, 60, 180),
                _ => (150, 150, 150)
            };
        }
    }

    /// <summary>
    /// A player-placed entity in the world (turret, trap, station, etc.).
    /// Second most complex model. Includes crafted stats application.
    /// </summary>
    [Serializable]
    public class PlacedEntity
    {
        [JsonProperty("position")]
        public GamePosition Position { get; set; }

        [JsonProperty("itemId")]
        public string ItemId { get; set; }

        [JsonProperty("entityType")]
        public PlacedEntityType EntityType { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; } = 1;

        [JsonProperty("health")]
        public float Health { get; set; } = 100.0f;

        [JsonProperty("owner")]
        public string Owner { get; set; }

        [JsonProperty("range")]
        public float Range { get; set; } = 5.0f;

        [JsonProperty("damage")]
        public float Damage { get; set; } = 20.0f;

        [JsonProperty("attackSpeed")]
        public float AttackSpeed { get; set; } = 1.0f;

        [JsonProperty("lastAttackTime")]
        public float LastAttackTime { get; set; }

        [JsonIgnore]
        public object TargetEnemy { get; set; }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("effectParams")]
        public Dictionary<string, object> EffectParams { get; set; } = new();

        [JsonProperty("lifetime")]
        public float Lifetime { get; set; } = 300.0f;

        [JsonProperty("timeRemaining")]
        public float TimeRemaining { get; set; } = 300.0f;

        [JsonIgnore]
        public List<object> StatusEffects { get; set; } = new();

        [JsonProperty("isStunned")]
        public bool IsStunned { get; set; }

        [JsonProperty("isFrozen")]
        public bool IsFrozen { get; set; }

        [JsonProperty("isRooted")]
        public bool IsRooted { get; set; }

        [JsonProperty("isBurning")]
        public bool IsBurning { get; set; }

        [JsonIgnore]
        public HashSet<string> VisualEffects { get; set; } = new();

        [JsonProperty("triggered")]
        public bool Triggered { get; set; }

        [JsonProperty("craftedStats")]
        public Dictionary<string, object> CraftedStats { get; set; } = new();

        public float MaxHealth { get; set; }

        /// <summary>
        /// Initialize after construction/deserialization.
        /// Applies barrier health by tier and crafted stats.
        /// </summary>
        public void Initialize()
        {
            Tags ??= new List<string>();
            EffectParams ??= new Dictionary<string, object>();
            StatusEffects ??= new List<object>();
            VisualEffects ??= new HashSet<string>();
            CraftedStats ??= new Dictionary<string, object>();

            // Barrier health by tier: T1=50, T2=100, T3=200, T4=400
            if (EntityType == PlacedEntityType.Barrier)
            {
                Health = BarrierHealth.GetHealth(Tier);
            }

            MaxHealth = Health;
            ApplyCraftedStats();
        }

        /// <summary>
        /// Apply crafted_stats bonuses to entity stats.
        /// Power: damage *= (1 + power/100)
        /// Durability: lifetime *= (1 + durability/100), resets time_remaining
        /// Efficiency: attack_speed *= (1 + min(efficiency, 900)/100), cap at 900
        /// </summary>
        private void ApplyCraftedStats()
        {
            if (CraftedStats == null || CraftedStats.Count == 0) return;

            float baseDamage = Damage;
            float baseLifetime = Lifetime;
            float baseAttackSpeed = AttackSpeed;

            // Power affects damage
            if (CraftedStats.TryGetValue("power", out var powerObj))
            {
                float power = Convert.ToSingle(powerObj);
                if (power > 0)
                {
                    Damage = baseDamage * (1 + power / 100f);
                    if (EffectParams.TryGetValue("baseDamage", out var bdObj))
                    {
                        float bd = Convert.ToSingle(bdObj);
                        EffectParams["baseDamage"] = bd * (1 + power / 100f);
                    }
                }
            }

            // Durability affects lifetime
            if (CraftedStats.TryGetValue("durability", out var durObj))
            {
                float durability = Convert.ToSingle(durObj);
                if (durability > 0)
                {
                    Lifetime = baseLifetime * (1 + durability / 100f);
                    TimeRemaining = Lifetime;
                }
            }

            // Efficiency affects attack speed (cap at 900 to prevent near-zero reload)
            if (CraftedStats.TryGetValue("efficiency", out var effObj))
            {
                float efficiency = Convert.ToSingle(effObj);
                if (efficiency > 0)
                {
                    float effectiveEfficiency = Math.Min(efficiency, 900f);
                    AttackSpeed = baseAttackSpeed * (1 + effectiveEfficiency / 100f);
                }
            }
        }

        /// <summary>
        /// Entity color constants by type.
        /// </summary>
        public (int R, int G, int B) GetColor()
        {
            return EntityType switch
            {
                PlacedEntityType.Turret => (255, 140, 0),
                PlacedEntityType.Trap => (160, 82, 45),
                PlacedEntityType.Bomb => (178, 34, 34),
                PlacedEntityType.UtilityDevice => (60, 180, 180),
                PlacedEntityType.CraftingStation => (105, 105, 105),
                PlacedEntityType.TrainingDummy => (200, 200, 0),
                PlacedEntityType.Barrier => (120, 120, 120),
                PlacedEntityType.DroppedItem => (255, 215, 0),
                _ => (150, 150, 150)
            };
        }

        /// <summary>
        /// Take damage and return true if destroyed (health &lt;= 0).
        /// </summary>
        public bool TakeDamage(float damage, string damageType = "physical")
        {
            Health -= damage;
            if (Health <= 0)
            {
                Health = 0;
                return true;
            }
            return false;
        }

        /// <summary>
        /// Update status effects. Stub for Phase 1 - full implementation in Phase 4 (Combat).
        /// Uses StatusEffectType enum pattern matching instead of Python's __class__.__name__.
        /// </summary>
        public void UpdateStatusEffects(float dt)
        {
            // Stub: Full implementation in Phase 4 when status effect classes are available.
            // Will use 'is' pattern matching instead of Python's effect.__class__.__name__
        }
    }

    /// <summary>
    /// A dungeon entrance in the world with rarity-based coloring.
    /// </summary>
    [Serializable]
    public class DungeonEntrance
    {
        [JsonProperty("position")]
        public GamePosition Position { get; set; }

        [JsonProperty("rarity")]
        public DungeonRarity Rarity { get; set; }

        [JsonProperty("discovered")]
        public bool Discovered { get; set; }

        /// <summary>
        /// Rarity Color Constants:
        /// COMMON (150,150,150), UNCOMMON (30,200,30), RARE (30,100,255),
        /// EPIC (180,60,255), LEGENDARY (255,165,0), UNIQUE (255,50,50)
        /// </summary>
        public (int R, int G, int B) GetRarityColor()
        {
            return Rarity switch
            {
                DungeonRarity.Common => (150, 150, 150),
                DungeonRarity.Uncommon => (30, 200, 30),
                DungeonRarity.Rare => (30, 100, 255),
                DungeonRarity.Epic => (180, 60, 255),
                DungeonRarity.Legendary => (255, 165, 0),
                DungeonRarity.Unique => (255, 50, 50),
                _ => (150, 150, 150)
            };
        }
    }
}
