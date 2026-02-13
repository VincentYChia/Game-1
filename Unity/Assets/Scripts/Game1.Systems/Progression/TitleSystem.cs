// ============================================================================
// Game1.Systems.Progression.TitleSystem
// Migrated from: systems/title_system.py (87 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Manages earned titles and their cumulative bonuses.
// Titles are checked against character state via UnlockRequirements.
// Acquisition methods: guaranteed_milestone, event_based_rng,
//   hidden_discovery, special_achievement, random_drop (legacy).
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Systems.Progression
{
    // ========================================================================
    // Title Definition (data model)
    // ========================================================================

    /// <summary>
    /// Definition for an achievement title. Loaded from titles-1.JSON.
    /// Matches Python TitleDefinition dataclass.
    /// </summary>
    public class TitleDefinition
    {
        public string TitleId { get; set; }
        public string Name { get; set; }
        public string Tier { get; set; }
        public string Category { get; set; }
        public string BonusDescription { get; set; }
        public Dictionary<string, float> Bonuses { get; set; } = new();
        public bool Hidden { get; set; }
        public string AcquisitionMethod { get; set; } = "guaranteed_milestone";
        public float GenerationChance { get; set; } = 1.0f;
        public string IconPath { get; set; }

        // Legacy fields
        public string ActivityType { get; set; } = "general";
        public int AcquisitionThreshold { get; set; }
        public List<string> Prerequisites { get; set; } = new();

        /// <summary>
        /// Evaluate whether a character meets the requirements for this title.
        /// Delegates to a requirements evaluator; stub returns true for now.
        /// Full implementation requires UnlockRequirements from Phase 2 data layer.
        /// </summary>
        public bool EvaluateRequirements(ITitleCharacterState character)
        {
            // When UnlockRequirements is available from Phase 2, delegate:
            // return Requirements?.Evaluate(character) ?? true;
            return true;
        }
    }

    /// <summary>
    /// Interface representing the character state needed for title evaluation.
    /// Decouples TitleSystem from concrete Character class.
    /// </summary>
    public interface ITitleCharacterState
    {
        int Level { get; }
        Dictionary<string, int> Activities { get; }
        List<string> EarnedTitleIds { get; }
        string ClassId { get; }
    }

    // ========================================================================
    // Title System
    // ========================================================================

    /// <summary>
    /// Manages earned titles and their cumulative bonuses.
    /// Checks character state against title requirements and awards titles.
    /// Matches Python TitleSystem class exactly.
    /// </summary>
    public class TitleSystem
    {
        private readonly System.Random _rng = new();

        /// <summary>All earned titles.</summary>
        public List<TitleDefinition> EarnedTitles { get; } = new();

        /// <summary>
        /// Reference to title database. Set after database singleton is initialized.
        /// In Python this was TitleDatabase.get_instance(); here it is injected.
        /// </summary>
        public Dictionary<string, TitleDefinition> TitleDatabase { get; set; } = new();

        // ====================================================================
        // Title Checking
        // ====================================================================

        /// <summary>
        /// Check if any new titles should be awarded based on character state.
        /// Iterates all titles in the database; returns the first newly earned one.
        /// Matches Python check_for_title() exactly.
        /// </summary>
        public TitleDefinition CheckTitleUnlocks(ITitleCharacterState character)
        {
            foreach (var (titleId, titleDef) in TitleDatabase)
            {
                // Skip already earned
                if (EarnedTitles.Any(t => t.TitleId == titleId))
                    continue;

                // Check requirements
                if (!titleDef.EvaluateRequirements(character))
                    continue;

                // Handle acquisition method
                switch (titleDef.AcquisitionMethod)
                {
                    case "guaranteed_milestone":
                        AwardTitle(titleDef);
                        return titleDef;

                    case "event_based_rng":
                        if (_rng.NextDouble() < titleDef.GenerationChance)
                        {
                            AwardTitle(titleDef);
                            return titleDef;
                        }
                        break;

                    case "hidden_discovery":
                        AwardTitle(titleDef);
                        return titleDef;

                    case "special_achievement":
                        if (_rng.NextDouble() < titleDef.GenerationChance)
                        {
                            AwardTitle(titleDef);
                            return titleDef;
                        }
                        break;

                    case "random_drop": // Legacy
                    {
                        var tierChances = new Dictionary<string, float>
                        {
                            ["novice"] = 1.0f,
                            ["apprentice"] = 0.20f,
                            ["journeyman"] = 0.10f,
                            ["expert"] = 0.05f,
                            ["master"] = 0.02f,
                        };
                        float chance = tierChances.TryGetValue(titleDef.Tier, out var c) ? c : 0.10f;
                        if (_rng.NextDouble() < chance)
                        {
                            AwardTitle(titleDef);
                            return titleDef;
                        }
                        break;
                    }
                }
            }

            return null;
        }

        // ====================================================================
        // Title Management
        // ====================================================================

        /// <summary>
        /// Award a title to the character. Returns true if newly awarded.
        /// </summary>
        public bool AwardTitle(TitleDefinition title)
        {
            if (title == null) return false;
            if (EarnedTitles.Any(t => t.TitleId == title.TitleId)) return false;

            EarnedTitles.Add(title);
            return true;
        }

        /// <summary>
        /// Check if a specific title has been earned.
        /// Matches Python has_title().
        /// </summary>
        public bool HasTitle(string titleId)
        {
            return EarnedTitles.Any(t => t.TitleId == titleId);
        }

        // ====================================================================
        // Bonus Calculation
        // ====================================================================

        /// <summary>
        /// Get total bonus value for a specific bonus type across all earned titles.
        /// Matches Python get_total_bonus() exactly.
        /// </summary>
        public float GetTotalBonus(string bonusType)
        {
            float total = 0f;
            foreach (var title in EarnedTitles)
            {
                if (title.Bonuses.TryGetValue(bonusType, out float bonus))
                    total += bonus;
            }
            return total;
        }

        /// <summary>
        /// Get all bonuses summed across all earned titles.
        /// Returns dictionary of bonusType -> totalValue.
        /// </summary>
        public Dictionary<string, float> GetTotalBonuses()
        {
            var totals = new Dictionary<string, float>();
            foreach (var title in EarnedTitles)
            {
                foreach (var (bonusType, value) in title.Bonuses)
                {
                    if (!totals.ContainsKey(bonusType))
                        totals[bonusType] = 0f;
                    totals[bonusType] += value;
                }
            }
            return totals;
        }

        // ====================================================================
        // Save/Load
        // ====================================================================

        /// <summary>
        /// Get list of earned title IDs for serialization.
        /// </summary>
        public List<string> GetEarnedTitleIds()
        {
            return EarnedTitles.Select(t => t.TitleId).ToList();
        }

        /// <summary>
        /// Restore earned titles from a list of title IDs (from save data).
        /// </summary>
        public void RestoreFromSave(List<string> titleIds)
        {
            EarnedTitles.Clear();
            foreach (var titleId in titleIds)
            {
                if (TitleDatabase.TryGetValue(titleId, out var titleDef))
                    EarnedTitles.Add(titleDef);
            }
        }
    }
}
