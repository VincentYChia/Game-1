// Game1.Data.Models.Skills
// Migrated from: data/models/skills.py (135 lines)
// Phase: 1 - Foundation
// Contains: SkillEffect, SkillCost, SkillEvolution, SkillRequirements, SkillDefinition, PlayerSkill

using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    [Serializable]
    public class SkillEffect
    {
        [JsonProperty("effectType")]
        public string EffectType { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("magnitude")]
        public string Magnitude { get; set; }

        [JsonProperty("target")]
        public string Target { get; set; }

        [JsonProperty("duration")]
        public string Duration { get; set; }

        [JsonProperty("additionalEffects")]
        public List<Dictionary<string, object>> AdditionalEffects { get; set; } = new();
    }

    [Serializable]
    public class SkillCost
    {
        /// <summary>
        /// Mana cost - supports both string ("low", "moderate", "high", "extreme")
        /// and numeric values (20-150). Stored as object for Union compatibility.
        /// </summary>
        [JsonProperty("mana")]
        public object Mana { get; set; }

        /// <summary>
        /// Cooldown - supports both string ("short", "moderate", "long", "extreme")
        /// and numeric values (10-600). Stored as object for Union compatibility.
        /// </summary>
        [JsonProperty("cooldown")]
        public object Cooldown { get; set; }

        public float GetManaAsFloat()
        {
            if (Mana is double d) return (float)d;
            if (Mana is long l) return l;
            if (Mana is int i) return i;
            if (Mana is string s && float.TryParse(s, out float f)) return f;
            return 0f;
        }

        public float GetCooldownAsFloat()
        {
            if (Cooldown is double d) return (float)d;
            if (Cooldown is long l) return l;
            if (Cooldown is int i) return i;
            if (Cooldown is string s && float.TryParse(s, out float f)) return f;
            return 0f;
        }
    }

    [Serializable]
    public class SkillEvolution
    {
        [JsonProperty("canEvolve")]
        public bool CanEvolve { get; set; }

        [JsonProperty("nextSkillId")]
        public string NextSkillId { get; set; }

        [JsonProperty("requirement")]
        public string Requirement { get; set; }
    }

    [Serializable]
    public class SkillRequirements
    {
        [JsonProperty("characterLevel")]
        public int CharacterLevel { get; set; }

        [JsonProperty("stats")]
        public Dictionary<string, int> Stats { get; set; } = new();

        [JsonProperty("titles")]
        public List<string> Titles { get; set; } = new();
    }

    [Serializable]
    public class SkillDefinition
    {
        [JsonProperty("skillId")]
        public string SkillId { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("tier")]
        public int Tier { get; set; }

        [JsonProperty("rarity")]
        public string Rarity { get; set; }

        [JsonProperty("categories")]
        public List<string> Categories { get; set; } = new();

        [JsonProperty("description")]
        public string Description { get; set; }

        [JsonProperty("narrative")]
        public string Narrative { get; set; }

        [JsonProperty("tags")]
        public List<string> Tags { get; set; } = new();

        [JsonProperty("effect")]
        public SkillEffect Effect { get; set; }

        [JsonProperty("cost")]
        public SkillCost Cost { get; set; }

        [JsonProperty("evolution")]
        public SkillEvolution Evolution { get; set; }

        [JsonProperty("requirements")]
        public SkillRequirements Requirements { get; set; }

        [JsonProperty("iconPath")]
        public string IconPath { get; set; }

        [JsonProperty("combatTags")]
        public List<string> CombatTags { get; set; } = new();

        [JsonProperty("combatParams")]
        public Dictionary<string, object> CombatParams { get; set; } = new();
    }

    /// <summary>
    /// Player's learned skill instance with level progression.
    /// Critical Constants:
    ///   Max skill level: 10
    ///   EXP formula: 1000 * 2^(level - 1)
    ///   Level scaling bonus: 10% per level above 1
    /// </summary>
    [Serializable]
    public class PlayerSkill
    {
        [JsonProperty("skillId")]
        public string SkillId { get; set; }

        [JsonProperty("level")]
        public int Level { get; set; } = 1;

        [JsonProperty("experience")]
        public int Experience { get; set; }

        [JsonProperty("currentCooldown")]
        public float CurrentCooldown { get; set; }

        [JsonProperty("isEquipped")]
        public bool IsEquipped { get; set; }

        [JsonProperty("hotbarSlot")]
        public int? HotbarSlot { get; set; }

        /// <summary>
        /// Get EXP required for next level. Formula: 1000 * 2^(level - 1).
        /// Level 1->2 = 1000, 2->3 = 2000, ..., 9->10 = 256000.
        /// Returns 0 at max level (10).
        /// </summary>
        public int GetExpForNextLevel()
        {
            if (Level >= 10) return 0;
            return 1000 * (1 << (Level - 1)); // 1 << n == 2^n
        }

        /// <summary>
        /// Add skill EXP and check for level up. Can level multiple times.
        /// Returns (leveled_up, new_level).
        /// </summary>
        public (bool LeveledUp, int NewLevel) AddExp(int amount)
        {
            if (Level >= 10) return (false, Level);

            Experience += amount;
            bool leveledUp = false;
            int oldLevel = Level;

            while (Level < 10)
            {
                int expNeeded = GetExpForNextLevel();
                if (Experience >= expNeeded)
                {
                    Experience -= expNeeded;
                    Level++;
                    leveledUp = true;
                }
                else
                {
                    break;
                }
            }

            return (leveledUp, leveledUp ? Level : oldLevel);
        }

        /// <summary>
        /// Get effectiveness bonus from skill level (+10% per level).
        /// Level 1 = +0%, Level 10 = +90%.
        /// </summary>
        public float GetLevelScalingBonus() => 0.1f * (Level - 1);

        public bool CanUse() => CurrentCooldown <= 0;

        public void UpdateCooldown(float dt)
        {
            if (CurrentCooldown > 0)
                CurrentCooldown = Math.Max(0, CurrentCooldown - dt);
        }

        public void StartCooldown(float cooldownSeconds)
        {
            CurrentCooldown = cooldownSeconds;
        }
    }
}
