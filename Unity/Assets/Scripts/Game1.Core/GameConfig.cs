// ============================================================================
// Game1.Core.GameConfig
// Migrated from: core/config.py (lines 1-200)
// Migration phase: 1-2
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Core
{
    /// <summary>
    /// Global configuration constants for game settings.
    /// All game balance numbers, formulas, and constants are centralized here.
    /// These values MUST match the Python source exactly.
    /// </summary>
    public static class GameConfig
    {
        // ====================================================================
        // Display
        // ====================================================================
        public const int BaseWidth = 1600;
        public const int BaseHeight = 900;
        public const int FPS = 60;

        // ====================================================================
        // World
        // ====================================================================
        public const int ChunkSize = 16;       // Tiles per chunk side
        public const int TileSize = 32;        // Pixels per tile (Python) / world units per tile
        public const int WorldSizeX = 100;     // Tiles east-west (legacy)
        public const int WorldSizeZ = 100;     // Tiles north-south (legacy)

        // Chunk loading (defaults; actual values from world_generation.JSON)
        public const int ChunkLoadRadius = 4;
        public const int SpawnAlwaysLoaded = 1;

        // Player spawn and safe zone
        public const float PlayerSpawnX = 0.0f;
        public const float PlayerSpawnY = 0.0f;
        public const float PlayerSpawnZ = 0.0f;
        public const float SafeZoneRadius = 8.0f;

        // Height system (3D-ready, unused in initial 2D mode)
        public const float DefaultHeight = 0f;
        public const float MaxHeight = 50f;
        public const float FloorHeight = 0f;

        // ====================================================================
        // Character / Movement
        // ====================================================================
        public const float PlayerSpeed = 0.15f;
        public const float InteractionRange = 3.5f;
        public const float ClickTolerance = 0.7f;
        public const int MaxLevel = 30;

        // ====================================================================
        // Combat
        // ====================================================================
        public const float MeleeRange = 1.5f;
        public const float ShortRange = 5f;
        public const float MediumRange = 10f;
        public const float LongRange = 20f;
        public const float MaxCombatRange = 30f;

        /// <summary>
        /// Enemy health multiplier applied during JSON loading.
        /// Python: health * 0.1 baked into enemy parser.
        /// </summary>
        public const float EnemyHealthMultiplier = 0.1f;

        /// <summary>
        /// Maximum damage reduction from defense (75%).
        /// </summary>
        public const float MaxDefenseReduction = 0.75f;

        /// <summary>
        /// Critical hit damage multiplier (2x).
        /// </summary>
        public const float CriticalHitMultiplier = 2.0f;

        /// <summary>
        /// Maximum class affinity bonus (20%).
        /// </summary>
        public const float MaxClassAffinityBonus = 0.20f;

        /// <summary>
        /// Toggle for vertical distance calculations.
        /// false = use XZ-plane (horizontal) distance for 2D parity.
        /// </summary>
        public static bool UseVerticalDistance = false;

        // ====================================================================
        // Tier Multipliers
        // ====================================================================
        /// <summary>
        /// Tier multipliers: T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x.
        /// </summary>
        public static readonly float[] TierMultipliers = { 0f, 1.0f, 2.0f, 4.0f, 8.0f };

        /// <summary>
        /// Get tier multiplier for a given tier (1-4). Returns 1.0 for invalid tiers.
        /// </summary>
        public static float GetTierMultiplier(int tier)
        {
            if (tier < 1 || tier > 4) return 1.0f;
            return TierMultipliers[tier];
        }

        // ====================================================================
        // EXP Formula
        // ====================================================================
        /// <summary>
        /// Calculate EXP required for a given level.
        /// Formula: 200 * 1.75^(level - 1)
        /// Level 1 = 200, Level 2 = 350, Level 10 = 14880 (approx)
        /// </summary>
        public static int GetExpForLevel(int level)
        {
            if (level < 1) return 0;
            if (level > MaxLevel) return 0;
            return (int)(200.0 * Math.Pow(1.75, level - 1));
        }

        // ====================================================================
        // Stat Scaling Constants
        // ====================================================================
        /// <summary>STR: +5% melee/mining damage per point.</summary>
        public const float StrDamagePerPoint = 0.05f;

        /// <summary>DEF: +2% damage reduction per point.</summary>
        public const float DefReductionPerPoint = 0.02f;

        /// <summary>VIT: +15 max HP per point.</summary>
        public const int VitHpPerPoint = 15;

        /// <summary>LCK: +2% crit chance per point.</summary>
        public const float LckCritPerPoint = 0.02f;

        /// <summary>AGI: +5% forestry damage per point.</summary>
        public const float AgiForestryPerPoint = 0.05f;

        /// <summary>INT: -2% minigame difficulty per point.</summary>
        public const float IntDifficultyPerPoint = 0.02f;

        /// <summary>INT: +20 mana per point.</summary>
        public const int IntManaPerPoint = 20;

        /// <summary>INT: +5% elemental damage per point.</summary>
        public const float IntElementalPerPoint = 0.05f;

        // ====================================================================
        // Rarity Colors (R, G, B, A)
        // ====================================================================
        public static readonly Dictionary<string, (byte R, byte G, byte B, byte A)> RarityColors = new()
        {
            ["common"]    = (200, 200, 200, 255),
            ["uncommon"]  = (30,  255, 0,   255),
            ["rare"]      = (0,   112, 221, 255),
            ["epic"]      = (163, 53,  238, 255),
            ["legendary"] = (255, 128, 0,   255),
            ["artifact"]  = (230, 204, 128, 255),
        };

        /// <summary>
        /// Get rarity color tuple. Returns common color for unknown rarities.
        /// </summary>
        public static (byte R, byte G, byte B, byte A) GetRarityColor(string rarity)
        {
            if (string.IsNullOrEmpty(rarity)) return RarityColors["common"];
            return RarityColors.TryGetValue(rarity.ToLowerInvariant(), out var color)
                ? color
                : RarityColors["common"];
        }

        // ====================================================================
        // Durability
        // ====================================================================
        /// <summary>
        /// At 0% durability, effectiveness is 50%. Items never break.
        /// </summary>
        public const float MinDurabilityEffectiveness = 0.5f;

        // ====================================================================
        // Crafting Quality Tiers (by performance 0.0-1.0)
        // ====================================================================
        public const float QualityNormalThreshold = 0.0f;
        public const float QualityFineThreshold = 0.25f;
        public const float QualitySuperiorThreshold = 0.50f;
        public const float QualityMasterworkThreshold = 0.75f;
        public const float QualityLegendaryThreshold = 0.90f;

        // ====================================================================
        // Inventory
        // ====================================================================
        public const int DefaultInventorySlots = 30;
        public const int DefaultMaxStack = 99;
        public const int EquipmentMaxStack = 1;
        public const int HotbarSlots = 5;

        // ====================================================================
        // Skill System
        // ====================================================================
        public const int MaxSkillLevel = 10;
        public const float SkillLevelBonusPerLevel = 0.10f; // +10% per level
    }
}
