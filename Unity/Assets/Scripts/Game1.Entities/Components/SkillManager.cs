// Game1.Entities.Components.SkillManager
// Migrated from: entities/components/skill_manager.py (972 lines)
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Databases;
using Game1.Data.Models;
using Game1.Entities;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Manages character skills: learning, equipping, cooldowns, and activation.
    /// 5 hotbar slots for equipped skills. Skills have mana costs and cooldowns.
    ///
    /// Note: Skill effect execution (_apply_skill_effect, _apply_combat_skill) is
    /// deferred to Phase 4 (EffectExecutor). Phase 3 provides the full management
    /// API and cooldown/mana logic; execution stubs are provided for Phase 4.
    /// </summary>
    public class SkillManager
    {
        public Dictionary<string, PlayerSkill> KnownSkills { get; set; } = new();
        public string[] EquippedSkills { get; set; } = new string[5]; // 5 hotbar slots

        // Magnitude values loaded from JSON (Phase 4 will use these for effect execution)
        public Dictionary<string, Dictionary<string, float>> MagnitudeValues { get; private set; } = new();

        public SkillManager()
        {
            LoadMagnitudeValues();
        }

        private void LoadMagnitudeValues()
        {
            // Try to load from skills-base-effects-1.JSON via SkillDatabase
            // Fallback to hardcoded values matching Python
            MagnitudeValues = new Dictionary<string, Dictionary<string, float>>
            {
                { "empower", new() { { "minor", 0.5f }, { "moderate", 1.0f }, { "major", 2.0f }, { "extreme", 4.0f } } },
                { "quicken", new() { { "minor", 0.3f }, { "moderate", 0.5f }, { "major", 0.75f }, { "extreme", 1.0f } } },
                { "fortify", new() { { "minor", 10f }, { "moderate", 20f }, { "major", 40f }, { "extreme", 80f } } },
                { "pierce", new() { { "minor", 0.1f }, { "moderate", 0.15f }, { "major", 0.25f }, { "extreme", 0.4f } } },
            };
        }

        /// <summary>
        /// Check if character meets requirements to learn a skill.
        /// Returns (canLearn, reason).
        /// </summary>
        public (bool CanLearn, string Reason) CanLearnSkill(string skillId, Character character)
        {
            if (KnownSkills.ContainsKey(skillId))
                return (false, "Already known");

            var skillDb = SkillDatabase.GetInstance();
            var skillDef = skillDb.GetSkill(skillId);
            if (skillDef == null)
                return (false, "Skill not found");

            // Check level
            if (character.Leveling.Level < skillDef.Requirements.CharacterLevel)
                return (false, $"Requires level {skillDef.Requirements.CharacterLevel}");

            // Check stat requirements
            if (skillDef.Requirements.Stats != null)
            {
                foreach (var (statName, required) in skillDef.Requirements.Stats)
                {
                    int current = character.Stats.GetStatByName(statName);
                    if (current < required)
                        return (false, $"Requires {statName} {required}");
                }
            }

            // Check title requirements
            if (skillDef.Requirements.Titles != null && skillDef.Requirements.Titles.Count > 0)
            {
                foreach (string requiredTitle in skillDef.Requirements.Titles)
                {
                    if (!character.HasTitle(requiredTitle))
                        return (false, $"Requires title: {requiredTitle}");
                }
            }

            return (true, "Requirements met");
        }

        /// <summary>
        /// Learn a new skill. If character is provided and skipChecks is false,
        /// requirements will be verified.
        /// </summary>
        public bool LearnSkill(string skillId, Character character = null, bool skipChecks = false)
        {
            if (KnownSkills.ContainsKey(skillId))
                return false;

            if (character != null && !skipChecks)
            {
                var (canLearn, _) = CanLearnSkill(skillId, character);
                if (!canLearn) return false;
            }

            KnownSkills[skillId] = new PlayerSkill { SkillId = skillId };
            return true;
        }

        /// <summary>
        /// Unlock a skill (called by SkillUnlockSystem after conditions verified).
        /// </summary>
        public bool UnlockSkill(string skillId)
        {
            return LearnSkill(skillId, character: null, skipChecks: true);
        }

        /// <summary>
        /// Get list of skill IDs the character can learn but hasn't yet.
        /// </summary>
        public List<string> GetAvailableSkills(Character character)
        {
            var available = new List<string>();
            var skillDb = SkillDatabase.GetInstance();
            if (!skillDb.Loaded) return available;

            foreach (string skillId in skillDb.Skills.Keys)
            {
                if (KnownSkills.ContainsKey(skillId)) continue;
                var (canLearn, _) = CanLearnSkill(skillId, character);
                if (canLearn) available.Add(skillId);
            }

            return available;
        }

        /// <summary>
        /// Equip a skill to a hotbar slot (0-4).
        /// </summary>
        public bool EquipSkill(string skillId, int slot)
        {
            if (slot < 0 || slot >= 5) return false;
            if (!KnownSkills.ContainsKey(skillId)) return false;

            EquippedSkills[slot] = skillId;
            KnownSkills[skillId].IsEquipped = true;
            return true;
        }

        /// <summary>
        /// Unequip a skill from a hotbar slot.
        /// </summary>
        public bool UnequipSkill(int slot)
        {
            if (slot < 0 || slot >= 5 || EquippedSkills[slot] == null) return false;

            string skillId = EquippedSkills[slot];
            EquippedSkills[slot] = null;
            if (KnownSkills.TryGetValue(skillId, out var skill))
                skill.IsEquipped = false;
            return true;
        }

        /// <summary>
        /// Update all skill cooldowns.
        /// </summary>
        public void UpdateCooldowns(float dt)
        {
            foreach (var skill in KnownSkills.Values)
            {
                if (skill.CurrentCooldown > 0)
                    skill.CurrentCooldown = Math.Max(0, skill.CurrentCooldown - dt);
            }
        }

        /// <summary>
        /// Use a skill from hotbar slot. Returns (success, message).
        /// Note: Effect execution is a Phase 4 stub — this method handles
        /// all mana/cooldown/EXP logic, but actual effect application
        /// requires the EffectExecutor (Phase 4).
        /// </summary>
        public (bool Success, string Message) UseSkill(int slot, Character character)
        {
            if (slot < 0 || slot >= 5)
                return (false, "Invalid slot");

            string skillId = EquippedSkills[slot];
            if (skillId == null)
                return (false, "No skill in slot");

            if (!KnownSkills.TryGetValue(skillId, out var playerSkill))
                return (false, "Skill not learned");

            var skillDb = SkillDatabase.GetInstance();
            var skillDef = skillDb.GetSkill(skillId);
            if (skillDef == null)
                return (false, "Skill definition not found");

            // Check cooldown
            if (playerSkill.CurrentCooldown > 0)
                return (false, $"On cooldown ({playerSkill.CurrentCooldown:F1}s)");

            // Check mana cost
            var skillDb = SkillDatabase.GetInstance();
            float manaCost = skillDb.GetManaCost(skillDef.Cost.Mana);
            if (character.Mana < manaCost)
                return (false, $"Not enough mana ({manaCost} required)");

            // Consume mana
            character.Mana -= manaCost;

            // Start cooldown
            float cooldownDuration = skillDb.GetCooldownSeconds(skillDef.Cost.Cooldown);
            playerSkill.CurrentCooldown = cooldownDuration;

            // Phase 4 stub: Apply skill effect
            // _applySkillEffect(skillDef, character, playerSkill, combatManager, mouseWorldPos);

            // Track skill usage
            if (character.StatTracker != null)
            {
                string category = GetSkillCategory(skillDef);
                character.StatTracker.RecordSkillUsed(skillId, 0f, manaCost, 0, category);
            }

            // Award skill EXP (100 EXP per activation)
            var (leveledUp, newLevel) = playerSkill.AddExp(100);
            if (leveledUp)
                return (true, $"Used {skillDef.Name}! Level {newLevel}!");

            return (true, $"Used {skillDef.Name}!");
        }

        /// <summary>
        /// Use skill in combat context with enemy targeting.
        /// Returns (success, message).
        /// </summary>
        public (bool Success, string Message) UseSkillInCombat(int slot, Character character,
            object targetEnemy = null, List<object> availableEnemies = null)
        {
            // Shares mana/cooldown logic with UseSkill
            // Combat execution deferred to Phase 4
            return UseSkill(slot, character);
        }

        /// <summary>
        /// Determine skill category for stat tracking.
        /// </summary>
        private string GetSkillCategory(SkillDefinition skillDef)
        {
            if (skillDef.CombatTags != null && skillDef.CombatTags.Count > 0)
                return "combat";

            string effectCategory = skillDef.Effect?.Category?.ToLower() ?? "";

            string[] gatheringKeywords = { "mining", "forestry", "gathering", "harvest", "wood", "ore", "stone" };
            if (gatheringKeywords.Any(kw => effectCategory.Contains(kw)))
                return "gathering";

            string[] craftingKeywords = { "smithing", "alchemy", "refining", "engineering", "enchanting", "crafting" };
            if (craftingKeywords.Any(kw => effectCategory.Contains(kw)))
                return "crafting";

            return "utility";
        }

        /// <summary>
        /// Get magnitude value for an effect type.
        /// </summary>
        public float GetMagnitudeValue(string effectType, string magnitude)
        {
            if (MagnitudeValues.TryGetValue(effectType, out var magnitudes))
            {
                if (magnitudes.TryGetValue(magnitude, out float value))
                    return value;
            }
            return 0.5f; // Default
        }
    }
}
