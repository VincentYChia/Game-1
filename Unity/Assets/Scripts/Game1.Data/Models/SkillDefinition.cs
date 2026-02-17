// ============================================================================
// Game1.Data.Models.SkillDefinition
// Migrated from: data/models/skills.py (lines 1-136)
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// Represents a skill's effect configuration.
    /// </summary>
    public class SkillEffect
    {
        [JsonProperty("type")]
        public string EffectType { get; set; } = "";

        [JsonProperty("category")]
        public string Category { get; set; } = "";

        [JsonProperty("magnitude")]
        public string Magnitude { get; set; } = "";

        [JsonProperty("target")]
        public string Target { get; set; } = "self";

        [JsonProperty("duration")]
        public string Duration { get; set; } = "instant";

        [JsonProperty("additionalEffects")]
        public List<Dictionary<string, object>> AdditionalEffects { get; set; } = new();
    }

    /// <summary>
    /// Represents skill costs. Supports both string enums and numeric values.
    /// String: "low"=30, "moderate"=60, "high"=100, "extreme"=150
    /// </summary>
    public class SkillCost
    {
        /// <summary>Mana cost. Can be string ("moderate") or numeric (60).</summary>
        [JsonProperty("mana")]
        public object ManaCostRaw { get; set; } = "moderate";

        /// <summary>Cooldown. Can be string ("short") or numeric (120).</summary>
        [JsonProperty("cooldown")]
        public object CooldownRaw { get; set; } = "moderate";
    }

    /// <summary>
    /// Represents skill evolution data.
    /// </summary>
    public class SkillEvolution
    {
        [JsonProperty("canEvolve")]
        public bool CanEvolve { get; set; }

        [JsonProperty("nextSkillId")]
        public string NextSkillId { get; set; }

        [JsonProperty("requirement")]
        public string Requirement { get; set; } = "";
    }

    /// <summary>
    /// Represents skill learning requirements.
    /// </summary>
    public class SkillRequirements
    {
        [JsonProperty("characterLevel")]
        public int CharacterLevel { get; set; } = 1;

        [JsonProperty("stats")]
        public Dictionary<string, int> Stats { get; set; } = new();

        [JsonProperty("titles")]
        public List<string> Titles { get; set; } = new();
    }

    /// <summary>
    /// Complete skill definition loaded from JSON.
    /// </summary>
    public class SkillDefinition
    {
        [JsonProperty("skillId")]
        public string SkillId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; } = 1;

        [JsonProperty("rarity")]
        public string Rarity { get; set; } = "common";

        [JsonProperty("categories")]
        public List<string> Categories { get; set; } = new();

        [JsonProperty("description")]
        public string Description { get; set; } = "";

        [JsonProperty("narrative")]
        public string Narrative { get; set; } = "";

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("effect")]
        public SkillEffect Effect { get; set; } = new();

        [JsonProperty("cost")]
        public SkillCost Cost { get; set; } = new();

        [JsonProperty("evolution")]
        public SkillEvolution Evolution { get; set; } = new();

        [JsonProperty("requirements")]
        public SkillRequirements Requirements { get; set; } = new();

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("combatTags")]
        public List<string> CombatTags { get; set; } = new();

        [JsonProperty("combatParams")]
        public Dictionary<string, object> CombatParams { get; set; } = new();

        public override string ToString()
        {
            return $"Skill({SkillId}: {Name} T{Tier})";
        }
    }

    /// <summary>
    /// Player's learned skill instance with level, exp, and cooldown state.
    /// </summary>
    public class PlayerSkill
    {
        public string SkillId { get; set; }
        public int Level { get; set; } = 1;
        public int Experience { get; set; }
        public float CurrentCooldown { get; set; }
        public bool IsEquipped { get; set; }
        public int? HotbarSlot { get; set; }

        public PlayerSkill(string skillId)
        {
            SkillId = skillId;
        }

        /// <summary>Max skill level is 10.</summary>
        public const int MaxSkillLevel = 10;

        /// <summary>
        /// EXP for next level: 1000 * 2^(level-1).
        /// Level 1->2 = 1000, Level 2->3 = 2000, etc.
        /// </summary>
        public int GetExpForNextLevel()
        {
            if (Level >= MaxSkillLevel) return 0;
            return 1000 * (1 << (Level - 1));
        }

        /// <summary>
        /// Add skill EXP and check for level up.
        /// Returns (leveledUp, newLevel).
        /// </summary>
        public (bool LeveledUp, int NewLevel) AddExp(int amount)
        {
            if (Level >= MaxSkillLevel) return (false, Level);

            Experience += amount;
            bool leveledUp = false;
            int oldLevel = Level;

            while (Level < MaxSkillLevel)
            {
                int needed = GetExpForNextLevel();
                if (Experience >= needed)
                {
                    Experience -= needed;
                    Level++;
                    leveledUp = true;
                }
                else break;
            }

            return (leveledUp, leveledUp ? Level : oldLevel);
        }

        /// <summary>+10% effectiveness per level. Level 1 = +0%, Level 10 = +90%.</summary>
        public float GetLevelScalingBonus()
        {
            return 0.1f * (Level - 1);
        }

        /// <summary>Check if skill is off cooldown.</summary>
        public bool CanUse() => CurrentCooldown <= 0;

        /// <summary>Update cooldown timer.</summary>
        public void UpdateCooldown(float dt)
        {
            if (CurrentCooldown > 0)
                CurrentCooldown = MathF.Max(0, CurrentCooldown - dt);
        }

        /// <summary>Start cooldown timer.</summary>
        public void StartCooldown(float seconds)
        {
            CurrentCooldown = seconds;
        }
    }
}
