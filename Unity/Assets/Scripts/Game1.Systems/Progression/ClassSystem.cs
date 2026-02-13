// ============================================================================
// Game1.Systems.Progression.ClassSystem
// Migrated from: systems/class_system.py (70 lines), data/models/classes.py (47 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Character class system with tag-driven bonuses.
// 6 classes, each with tags determining skill affinity, tool bonuses, and identity.
// Max class affinity bonus: 20% (5% per matching tag).
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;

namespace Game1.Systems.Progression
{
    // ========================================================================
    // Class Definition (data model)
    // ========================================================================

    /// <summary>
    /// Definition for a character class with tag-driven identity.
    /// Loaded from classes-1.JSON.
    /// Matches Python ClassDefinition dataclass exactly.
    /// </summary>
    public class ClassDefinition
    {
        public string ClassId { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public Dictionary<string, float> Bonuses { get; set; } = new();
        public string StartingSkill { get; set; } = "";
        public List<string> RecommendedStats { get; set; } = new();
        public List<string> Tags { get; set; } = new();
        public List<string> PreferredDamageTypes { get; set; } = new();
        public string PreferredArmorType { get; set; } = "";

        /// <summary>
        /// Check if class has a specific tag (case-insensitive).
        /// Matches Python ClassDefinition.has_tag().
        /// </summary>
        public bool HasTag(string tag)
        {
            return Tags.Any(t => t.Equals(tag, StringComparison.OrdinalIgnoreCase));
        }

        /// <summary>
        /// Calculate skill affinity bonus based on tag overlap.
        /// Each matching tag adds 5% bonus, up to 20% max.
        /// Matches Python ClassDefinition.get_skill_affinity_bonus() exactly.
        /// </summary>
        public float GetSkillAffinityBonus(List<string> skillTags)
        {
            if (skillTags == null || skillTags.Count == 0 || Tags.Count == 0)
                return 0f;

            var classTagsLower = new HashSet<string>(Tags.Select(t => t.ToLowerInvariant()));
            var skillTagsLower = new HashSet<string>(skillTags.Select(t => t.ToLowerInvariant()));

            int matchCount = classTagsLower.Intersect(skillTagsLower).Count();

            const float bonusPerTag = 0.05f;
            const float maxBonus = GameConfig.MaxClassAffinityBonus; // 0.20

            return MathF.Min(matchCount * bonusPerTag, maxBonus);
        }
    }

    // ========================================================================
    // Class System
    // ========================================================================

    /// <summary>
    /// Manages character class selection and provides tag-driven bonuses.
    /// Matches Python ClassSystem class exactly.
    /// </summary>
    public class ClassSystem
    {
        /// <summary>Currently selected class (null before class selection).</summary>
        public ClassDefinition CurrentClass { get; private set; }

        /// <summary>
        /// Reference to class database. Set after database singleton is initialized.
        /// </summary>
        public Dictionary<string, ClassDefinition> ClassDatabase { get; set; } = new();

        // Callbacks for class change events
        private readonly List<Action<ClassDefinition>> _onClassSetCallbacks = new();

        // ====================================================================
        // Class Selection
        // ====================================================================

        /// <summary>
        /// Select a class by ID from the database.
        /// </summary>
        public bool SelectClass(string classId)
        {
            if (ClassDatabase.TryGetValue(classId, out var classDef))
            {
                SetClass(classDef);
                return true;
            }
            return false;
        }

        /// <summary>
        /// Set the current class directly.
        /// Matches Python ClassSystem.set_class().
        /// </summary>
        public void SetClass(ClassDefinition classDef)
        {
            CurrentClass = classDef;
            foreach (var callback in _onClassSetCallbacks)
                callback(classDef);
        }

        /// <summary>
        /// Register a callback for class changes (e.g., to recalculate stats).
        /// Matches Python ClassSystem.register_on_class_set().
        /// </summary>
        public void RegisterOnClassSet(Action<ClassDefinition> callback)
        {
            _onClassSetCallbacks.Add(callback);
        }

        // ====================================================================
        // Bonus Queries
        // ====================================================================

        /// <summary>
        /// Get a specific bonus value from the current class.
        /// Matches Python ClassSystem.get_bonus().
        /// </summary>
        public float GetBonus(string bonusType)
        {
            if (CurrentClass == null) return 0f;
            return CurrentClass.Bonuses.TryGetValue(bonusType, out float val) ? val : 0f;
        }

        /// <summary>
        /// Get all class bonuses as a dictionary.
        /// </summary>
        public Dictionary<string, float> GetClassBonuses()
        {
            if (CurrentClass == null) return new Dictionary<string, float>();
            return new Dictionary<string, float>(CurrentClass.Bonuses);
        }

        /// <summary>
        /// Get skill affinity bonus for the current class based on skill tags.
        /// Each matching tag adds 5% bonus, up to 20% max.
        /// </summary>
        public float GetClassAffinity(List<string> skillTags)
        {
            return CurrentClass?.GetSkillAffinityBonus(skillTags) ?? 0f;
        }

        /// <summary>
        /// Get discipline affinity bonus. Maps discipline name to class bonus keys.
        /// </summary>
        public float GetDisciplineAffinity(string discipline)
        {
            if (CurrentClass == null) return 0f;

            string key = $"{discipline.ToLowerInvariant()}_bonus";
            return CurrentClass.Bonuses.TryGetValue(key, out float val) ? val : 0f;
        }

        /// <summary>
        /// Get tool efficiency bonus based on class tags.
        /// Matches Python ClassSystem.get_tool_efficiency_bonus() exactly.
        ///
        /// Tag-driven bonuses:
        ///   'nature' or 'gathering': +10% axe efficiency
        ///   'gathering' or 'explorer': +10% pickaxe efficiency
        ///   'physical' or 'melee': +5% tool damage (via get_tool_damage_bonus)
        /// </summary>
        public float GetToolEfficiencyBonus(string toolType)
        {
            if (CurrentClass?.Tags == null || CurrentClass.Tags.Count == 0)
                return 0f;

            var tags = new HashSet<string>(CurrentClass.Tags.Select(t => t.ToLowerInvariant()));
            float bonus = 0f;

            switch (toolType.ToLowerInvariant())
            {
                case "axe":
                    if (tags.Contains("nature")) bonus += 0.10f;
                    if (tags.Contains("gathering")) bonus += 0.05f;
                    break;
                case "pickaxe":
                    if (tags.Contains("gathering")) bonus += 0.10f;
                    if (tags.Contains("explorer")) bonus += 0.05f;
                    break;
            }

            return bonus;
        }

        /// <summary>
        /// Get tool damage bonus for combat use based on class tags.
        /// Matches Python ClassSystem.get_tool_damage_bonus() exactly.
        /// </summary>
        public float GetToolDamageBonus()
        {
            if (CurrentClass?.Tags == null || CurrentClass.Tags.Count == 0)
                return 0f;

            var tags = new HashSet<string>(CurrentClass.Tags.Select(t => t.ToLowerInvariant()));
            float bonus = 0f;

            if (tags.Contains("physical")) bonus += 0.05f;
            if (tags.Contains("melee")) bonus += 0.05f;

            return bonus;
        }

        // ====================================================================
        // Save/Load
        // ====================================================================

        /// <summary>
        /// Get current class ID for save data.
        /// </summary>
        public string GetCurrentClassId()
        {
            return CurrentClass?.ClassId;
        }

        /// <summary>
        /// Restore class from save data by class ID.
        /// </summary>
        public void RestoreFromSave(string classId)
        {
            if (!string.IsNullOrEmpty(classId) &&
                ClassDatabase.TryGetValue(classId, out var classDef))
            {
                CurrentClass = classDef;
                // Do NOT fire callbacks during restore (avoid side effects)
            }
        }
    }
}
