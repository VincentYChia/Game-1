// ============================================================================
// Game1.Systems.World.NaturalResource
// Migrated from: systems/natural_resource.py (192 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Harvestable world resources (trees, ores, stones, fishing spots).
// JSON-driven via ResourceNodeDatabase when available, with hardcoded fallbacks.
// ============================================================================

using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Game1.Data.Models;

namespace Game1.Systems.World
{
    // ========================================================================
    // JSON Definition Classes (loaded from Resource-node-1.JSON)
    // ========================================================================

    /// <summary>
    /// JSON definition for a resource node type. Loaded from Resource-node-1.JSON.
    /// </summary>
    public class NaturalResourceDefinition
    {
        [JsonProperty("resourceId")]
        public string ResourceId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("requiredTool")]
        public string RequiredTool { get; set; }

        [JsonProperty("minToolTier")]
        public int MinToolTier { get; set; } = 1;

        [JsonProperty("baseHealth")]
        public int BaseHealth { get; set; } = 100;

        [JsonProperty("baseYield")]
        public int BaseYield { get; set; } = 1;

        [JsonProperty("respawnTime")]
        public float RespawnTime { get; set; } = -1f;

        [JsonProperty("doesRespawn")]
        public bool DoesRespawn { get; set; }

        [JsonProperty("drops")]
        public List<ResourceDrop> Drops { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }
    }

    /// <summary>
    /// A single drop entry from a resource node.
    /// </summary>
    public class ResourceDrop
    {
        [JsonProperty("materialId")]
        public string MaterialId { get; set; }

        [JsonProperty("quantity")]
        public int Quantity { get; set; } = 1;

        [JsonProperty("minQuantity")]
        public int MinQuantity { get; set; } = 1;

        [JsonProperty("maxQuantity")]
        public int MaxQuantity { get; set; } = 1;

        [JsonProperty("chance")]
        public float Chance { get; set; } = 1.0f;
    }

    /// <summary>
    /// A loot drop result (materialId + quantity range + chance).
    /// Matches Python LootDrop dataclass.
    /// </summary>
    public class LootDrop
    {
        public string ItemId { get; set; }
        public int Quantity { get; set; } = 1;
        public int MinQuantity { get; set; }
        public int MaxQuantity { get; set; }
        public float Chance { get; set; }

        public LootDrop(string itemId, int minQty, int maxQty, float chance = 1.0f)
        {
            ItemId = itemId;
            MinQuantity = minQty;
            MaxQuantity = maxQty;
            Chance = chance;
        }
    }

    // ========================================================================
    // Natural Resource Instance (runtime world object)
    // ========================================================================

    /// <summary>
    /// A specific resource instance placed in the world.
    /// Has HP, can be harvested, may respawn on a timer.
    /// Matches Python NaturalResource class.
    /// </summary>
    public class NaturalResourceInstance
    {
        public string ResourceId { get; set; }
        public GamePosition Position { get; set; }
        public int Tier { get; set; }

        // Health
        public int MaxHp { get; set; }
        public int CurrentHp { get; set; }

        // Tool requirements
        public string RequiredTool { get; set; }
        public int MinToolTier { get; set; } = 1;

        // Respawn
        public bool Respawns { get; set; }
        public float RespawnTimer { get; set; }
        public float TimeUntilRespawn { get; set; }

        // State
        public bool IsDepleted { get; set; }

        // Loot
        public List<LootDrop> LootTable { get; set; } = new();

        // RNG for loot rolls
        private readonly System.Random _rng = new();

        public NaturalResourceInstance() { }

        /// <summary>
        /// Create a resource instance with hardcoded defaults based on category.
        /// Matches Python NaturalResource.__init__() fallback logic.
        /// </summary>
        public NaturalResourceInstance(GamePosition position, string resourceId, int tier)
        {
            Position = position;
            ResourceId = resourceId;
            Tier = tier;

            // Determine defaults from resource category
            string lower = resourceId.ToLowerInvariant();

            if (lower.Contains("tree") || lower.Contains("sapling"))
            {
                RequiredTool = "axe";
                Respawns = true;
                RespawnTimer = 60.0f;
                MaxHp = tier switch { 1 => 100, 2 => 200, 3 => 400, 4 => 800, _ => 100 };
            }
            else if (lower.Contains("fishing_spot"))
            {
                RequiredTool = "fishing_rod";
                Respawns = true;
                RespawnTimer = tier switch { 1 => 30f, 2 => 45f, 3 => 60f, 4 => 90f, _ => 30f };
                MaxHp = tier switch { 1 => 50, 2 => 75, 3 => 100, 4 => 150, _ => 50 };
            }
            else
            {
                RequiredTool = "pickaxe";
                Respawns = false;
                RespawnTimer = 0f;
                MaxHp = tier switch { 1 => 100, 2 => 200, 3 => 400, 4 => 800, _ => 100 };
            }

            CurrentHp = MaxHp;
        }

        /// <summary>
        /// Create a resource instance from a JSON definition.
        /// </summary>
        public NaturalResourceInstance(GamePosition position, NaturalResourceDefinition def)
        {
            Position = position;
            ResourceId = def.ResourceId;
            Tier = def.Tier;
            MaxHp = def.BaseHealth;
            CurrentHp = MaxHp;
            RequiredTool = def.RequiredTool;
            MinToolTier = def.MinToolTier;
            Respawns = def.DoesRespawn;
            RespawnTimer = def.RespawnTime > 0 ? def.RespawnTime : 0f;

            // Build loot table from definition drops
            foreach (var drop in def.Drops)
            {
                LootTable.Add(new LootDrop(
                    drop.MaterialId,
                    drop.MinQuantity,
                    drop.MaxQuantity,
                    drop.Chance));
            }
        }

        /// <summary>
        /// Take damage from harvesting. Returns (actualDamage, wasDestroyed).
        /// Critical hits deal 2x damage. Matches Python take_damage().
        /// </summary>
        public (int actualDamage, bool destroyed) TakeDamage(int damage, bool isCrit = false)
        {
            if (IsDepleted) return (0, false);

            int actual = isCrit ? damage * 2 : damage;
            CurrentHp -= actual;

            if (CurrentHp <= 0)
            {
                CurrentHp = 0;
                IsDepleted = true;
                return (actual, true);
            }

            return (actual, false);
        }

        /// <summary>
        /// Roll loot table and return list of (itemId, quantity) drops.
        /// Matches Python get_loot().
        /// </summary>
        public List<(string itemId, int quantity)> GetLoot()
        {
            var drops = new List<(string, int)>();
            foreach (var loot in LootTable)
            {
                if (_rng.NextDouble() <= loot.Chance)
                {
                    int qty = _rng.Next(loot.MinQuantity, loot.MaxQuantity + 1);
                    drops.Add((loot.ItemId, qty));
                }
            }
            return drops;
        }

        /// <summary>
        /// Update respawn timer. Matches Python NaturalResource.update(dt).
        /// </summary>
        public void Update(float dt)
        {
            if (IsDepleted && Respawns && RespawnTimer > 0f)
            {
                TimeUntilRespawn += dt;
                if (TimeUntilRespawn >= RespawnTimer)
                {
                    CurrentHp = MaxHp;
                    IsDepleted = false;
                    TimeUntilRespawn = 0f;
                }
            }
        }

        /// <summary>
        /// Get respawn progress as 0.0-1.0. Matches Python get_respawn_progress().
        /// </summary>
        public float GetRespawnProgress()
        {
            if (!IsDepleted || !Respawns || RespawnTimer <= 0f) return 0f;
            return MathF.Min(1.0f, TimeUntilRespawn / RespawnTimer);
        }

        /// <summary>
        /// Serialize for save data.
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["position"] = new Dictionary<string, object>
                {
                    ["x"] = Position.X, ["y"] = Position.Y, ["z"] = Position.Z
                },
                ["resource_id"] = ResourceId,
                ["tier"] = Tier,
                ["current_hp"] = CurrentHp,
                ["max_hp"] = MaxHp,
                ["depleted"] = IsDepleted,
                ["time_until_respawn"] = TimeUntilRespawn,
            };
        }
    }
}
