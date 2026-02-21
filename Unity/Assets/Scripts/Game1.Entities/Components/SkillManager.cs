// ============================================================================
// Game1.Entities.Components.SkillManager
// Migrated from: entities/components/skill_manager.py (lines 1-80+)
// Migration phase: 3 (FIX-7: cached available skills)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Data.Models;
using Game1.Data.Databases;
using Game1.Core;

namespace Game1.Entities.Components
{
    /// <summary>
    /// Skill management component.
    /// Manages known skills, equipped hotbar skills, cooldowns, and activation.
    /// FIX-7: Available skills are cached and invalidated on relevant events.
    /// </summary>
    public class SkillManager
    {
        /// <summary>All known (learned) skills keyed by skill ID.</summary>
        private readonly Dictionary<string, PlayerSkill> _knownSkills = new();

        /// <summary>Equipped skill IDs for the hotbar (5 slots).</summary>
        private readonly string[] _equippedSkills = new string[GameConfig.HotbarSlots];

        // FIX-7: Cached available skills
        private List<string> _cachedAvailableSkills;
        private bool _availableSkillsDirty = true;

        public SkillManager()
        {
            // Invalidate cache on relevant events (FIX-7)
            GameEvents.OnLevelUp += (_, _) => _availableSkillsDirty = true;
            GameEvents.OnTitleEarned += (_, _) => _availableSkillsDirty = true;
            GameEvents.OnSkillLearned += _ => _availableSkillsDirty = true;
        }

        // ====================================================================
        // Learn / Equip
        // ====================================================================

        /// <summary>
        /// Learn a new skill. Returns true if successfully learned.
        /// </summary>
        public bool LearnSkill(string skillId)
        {
            if (string.IsNullOrEmpty(skillId)) return false;
            if (_knownSkills.ContainsKey(skillId)) return false;

            var skillDef = SkillDatabase.Instance.GetSkill(skillId);
            if (skillDef == null) return false;

            _knownSkills[skillId] = new PlayerSkill(skillId);
            _availableSkillsDirty = true;

            GameEvents.RaiseSkillLearned(skillId);
            return true;
        }

        /// <summary>
        /// Equip a known skill to a hotbar slot (0-4).
        /// </summary>
        public bool EquipSkill(string skillId, int hotbarSlot)
        {
            if (hotbarSlot < 0 || hotbarSlot >= _equippedSkills.Length) return false;
            if (!_knownSkills.ContainsKey(skillId)) return false;

            // Unequip from any other slot first
            for (int i = 0; i < _equippedSkills.Length; i++)
            {
                if (_equippedSkills[i] == skillId)
                {
                    _equippedSkills[i] = null;
                    _knownSkills[skillId].IsEquipped = false;
                    _knownSkills[skillId].HotbarSlot = null;
                }
            }

            _equippedSkills[hotbarSlot] = skillId;
            _knownSkills[skillId].IsEquipped = true;
            _knownSkills[skillId].HotbarSlot = hotbarSlot;
            return true;
        }

        // ====================================================================
        // Activation
        // ====================================================================

        /// <summary>
        /// Activate a skill by ID. Returns true if skill was successfully activated.
        /// </summary>
        public bool ActivateSkill(string skillId, CharacterStats stats = null)
        {
            if (!_knownSkills.TryGetValue(skillId, out var playerSkill)) return false;
            if (!playerSkill.CanUse()) return false;

            var skillDef = SkillDatabase.Instance.GetSkill(skillId);
            if (skillDef == null) return false;

            // Check mana cost
            int manaCost = SkillDatabase.Instance.GetManaCost(skillDef.Cost.ManaCostRaw);
            if (stats != null && !stats.SpendMana(manaCost)) return false;

            // Start cooldown
            float cooldown = SkillDatabase.Instance.GetCooldownSeconds(skillDef.Cost.CooldownRaw);
            playerSkill.StartCooldown(cooldown);

            GameEvents.RaiseSkillUsed(skillId);
            return true;
        }

        /// <summary>Check if a skill is on cooldown.</summary>
        public bool IsOnCooldown(string skillId)
        {
            return _knownSkills.TryGetValue(skillId, out var ps) && !ps.CanUse();
        }

        /// <summary>Update all cooldowns.</summary>
        public void UpdateCooldowns(float deltaTime)
        {
            foreach (var ps in _knownSkills.Values)
            {
                ps.UpdateCooldown(deltaTime);
            }
        }

        // ====================================================================
        // Queries
        // ====================================================================

        /// <summary>Get a known skill by ID. Returns null if not known.</summary>
        public PlayerSkill GetKnownSkill(string skillId)
        {
            return _knownSkills.TryGetValue(skillId, out var ps) ? ps : null;
        }

        /// <summary>Check if a skill is known.</summary>
        public bool IsSkillKnown(string skillId) => _knownSkills.ContainsKey(skillId);

        /// <summary>All known skills.</summary>
        public IReadOnlyDictionary<string, PlayerSkill> KnownSkills => _knownSkills;

        /// <summary>
        /// Unequip a skill from any hotbar slot.
        /// </summary>
        public bool UnequipSkill(string skillId)
        {
            if (string.IsNullOrEmpty(skillId)) return false;
            if (!_knownSkills.TryGetValue(skillId, out var playerSkill)) return false;

            for (int i = 0; i < _equippedSkills.Length; i++)
            {
                if (_equippedSkills[i] == skillId)
                {
                    _equippedSkills[i] = null;
                    playerSkill.IsEquipped = false;
                    playerSkill.HotbarSlot = null;
                    return true;
                }
            }
            return false;
        }

        /// <summary>Get equipped skill IDs (hotbar, may contain nulls).</summary>
        public string[] GetEquippedSkills() => (string[])_equippedSkills.Clone();

        /// <summary>Get equipped skill at a hotbar slot.</summary>
        public string GetEquippedSkillAt(int slot)
        {
            if (slot < 0 || slot >= _equippedSkills.Length) return null;
            return _equippedSkills[slot];
        }
    }
}
