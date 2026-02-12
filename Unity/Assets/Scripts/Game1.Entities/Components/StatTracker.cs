// Game1.Entities.Components.StatTracker
// Migrated from: entities/components/stat_tracker.py (1,722 lines)
// Phase: 3 - Entity Layer

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game1.Entities.Components
{
    // === Supporting Data Classes ===

    /// <summary>
    /// Generic stat entry for counting and aggregating numeric values.
    /// </summary>
    [Serializable]
    public class StatEntry
    {
        public int Count { get; set; }
        public float TotalValue { get; set; }
        public float MaxValue { get; set; }
        public double? LastUpdated { get; set; }

        public void Record(float value = 1.0f)
        {
            Count++;
            TotalValue += value;
            if (value > MaxValue) MaxValue = value;
            LastUpdated = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        }

        public float GetAverage() => Count > 0 ? TotalValue / Count : 0f;

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "count", Count },
                { "total_value", TotalValue },
                { "max_value", MaxValue },
                { "last_updated", LastUpdated }
            };
        }

        public static StatEntry FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return new StatEntry();
            return new StatEntry
            {
                Count = Convert.ToInt32(data.GetValueOrDefault("count", 0)),
                TotalValue = Convert.ToSingle(data.GetValueOrDefault("total_value", 0f)),
                MaxValue = Convert.ToSingle(data.GetValueOrDefault("max_value", 0f)),
                LastUpdated = data.TryGetValue("last_updated", out var lu) && lu != null
                    ? Convert.ToDouble(lu)
                    : null
            };
        }
    }

    /// <summary>
    /// Specialized tracking for crafting recipes.
    /// </summary>
    [Serializable]
    public class CraftingEntry
    {
        public int TotalAttempts { get; set; }
        public int SuccessfulCrafts { get; set; }
        public int FailedCrafts { get; set; }
        public int PerfectCrafts { get; set; }
        public int FirstTryBonuses { get; set; }
        public float AverageQualityScore { get; set; }
        public float BestQualityScore { get; set; }
        public float TotalCraftingTime { get; set; }
        public float FastestCraftTime { get; set; } = float.PositiveInfinity;
        public int CommonCrafted { get; set; }
        public int UncommonCrafted { get; set; }
        public int RareCrafted { get; set; }
        public int LegendaryCrafted { get; set; }
        public Dictionary<string, int> MaterialsConsumed { get; set; } = new();

        public void RecordCraft(bool success, float qualityScore = 0f, float craftTime = 0f,
            string outputRarity = "common", bool isPerfect = false, bool isFirstTry = false,
            Dictionary<string, int> materials = null)
        {
            TotalAttempts++;
            if (success)
            {
                SuccessfulCrafts++;
                if (isPerfect) PerfectCrafts++;
                if (isFirstTry) FirstTryBonuses++;

                if (qualityScore > 0)
                {
                    float totalQuality = AverageQualityScore * (SuccessfulCrafts - 1);
                    AverageQualityScore = (totalQuality + qualityScore) / SuccessfulCrafts;
                    if (qualityScore > BestQualityScore) BestQualityScore = qualityScore;
                }

                if (craftTime > 0)
                {
                    TotalCraftingTime += craftTime;
                    if (craftTime < FastestCraftTime) FastestCraftTime = craftTime;
                }

                switch (outputRarity.ToLower())
                {
                    case "common": CommonCrafted++; break;
                    case "uncommon": UncommonCrafted++; break;
                    case "rare": RareCrafted++; break;
                    case "legendary": LegendaryCrafted++; break;
                }

                if (materials != null)
                {
                    foreach (var (matId, qty) in materials)
                        MaterialsConsumed[matId] = MaterialsConsumed.GetValueOrDefault(matId) + qty;
                }
            }
            else
            {
                FailedCrafts++;
            }
        }

        public float GetSuccessRate() => TotalAttempts > 0 ? (float)SuccessfulCrafts / TotalAttempts * 100f : 0f;

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "total_attempts", TotalAttempts },
                { "successful_crafts", SuccessfulCrafts },
                { "failed_crafts", FailedCrafts },
                { "perfect_crafts", PerfectCrafts },
                { "first_try_bonuses", FirstTryBonuses },
                { "average_quality_score", AverageQualityScore },
                { "best_quality_score", BestQualityScore },
                { "total_crafting_time", TotalCraftingTime },
                { "fastest_craft_time", float.IsPositiveInfinity(FastestCraftTime) ? (object)null : FastestCraftTime },
                { "common_crafted", CommonCrafted },
                { "uncommon_crafted", UncommonCrafted },
                { "rare_crafted", RareCrafted },
                { "legendary_crafted", LegendaryCrafted },
                { "materials_consumed", new Dictionary<string, int>(MaterialsConsumed) }
            };
        }

        public static CraftingEntry FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return new CraftingEntry();
            var entry = new CraftingEntry
            {
                TotalAttempts = Convert.ToInt32(data.GetValueOrDefault("total_attempts", 0)),
                SuccessfulCrafts = Convert.ToInt32(data.GetValueOrDefault("successful_crafts", 0)),
                FailedCrafts = Convert.ToInt32(data.GetValueOrDefault("failed_crafts", 0)),
                PerfectCrafts = Convert.ToInt32(data.GetValueOrDefault("perfect_crafts", 0)),
                FirstTryBonuses = Convert.ToInt32(data.GetValueOrDefault("first_try_bonuses", 0)),
                AverageQualityScore = Convert.ToSingle(data.GetValueOrDefault("average_quality_score", 0f)),
                BestQualityScore = Convert.ToSingle(data.GetValueOrDefault("best_quality_score", 0f)),
                TotalCraftingTime = Convert.ToSingle(data.GetValueOrDefault("total_crafting_time", 0f)),
                CommonCrafted = Convert.ToInt32(data.GetValueOrDefault("common_crafted", 0)),
                UncommonCrafted = Convert.ToInt32(data.GetValueOrDefault("uncommon_crafted", 0)),
                RareCrafted = Convert.ToInt32(data.GetValueOrDefault("rare_crafted", 0)),
                LegendaryCrafted = Convert.ToInt32(data.GetValueOrDefault("legendary_crafted", 0)),
            };
            var fct = data.GetValueOrDefault("fastest_craft_time");
            entry.FastestCraftTime = fct == null ? float.PositiveInfinity : Convert.ToSingle(fct);
            if (entry.FastestCraftTime == 0f) entry.FastestCraftTime = float.PositiveInfinity;
            return entry;
        }
    }

    /// <summary>
    /// Specialized tracking for skill usage.
    /// </summary>
    [Serializable]
    public class SkillStatEntry
    {
        public int TimesUsed { get; set; }
        public float TotalValueDelivered { get; set; }
        public float ManaSpent { get; set; }
        public int TargetsAffected { get; set; }
        public float BestSingleUse { get; set; }

        public void RecordUse(float value = 0f, float manaCost = 0f, int targets = 0)
        {
            TimesUsed++;
            TotalValueDelivered += value;
            ManaSpent += manaCost;
            TargetsAffected += targets;
            if (value > BestSingleUse) BestSingleUse = value;
        }

        public float GetAverageValue() => TimesUsed > 0 ? TotalValueDelivered / TimesUsed : 0f;

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "times_used", TimesUsed },
                { "total_value_delivered", TotalValueDelivered },
                { "mana_spent", ManaSpent },
                { "targets_affected", TargetsAffected },
                { "best_single_use", BestSingleUse }
            };
        }

        public static SkillStatEntry FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return new SkillStatEntry();
            return new SkillStatEntry
            {
                TimesUsed = Convert.ToInt32(data.GetValueOrDefault("times_used", 0)),
                TotalValueDelivered = Convert.ToSingle(data.GetValueOrDefault("total_value_delivered", 0f)),
                ManaSpent = Convert.ToSingle(data.GetValueOrDefault("mana_spent", 0f)),
                TargetsAffected = Convert.ToInt32(data.GetValueOrDefault("targets_affected", 0)),
                BestSingleUse = Convert.ToSingle(data.GetValueOrDefault("best_single_use", 0f))
            };
        }
    }

    // === Main StatTracker ===

    /// <summary>
    /// Comprehensive stat tracking system (850-1000+ stats across 14 categories).
    /// Migrated from Python's StatTracker.
    /// Uses dictionaries for aggregate stats to maintain JSON save compatibility.
    /// </summary>
    public class StatTracker
    {
        public double? SessionStartTime { get; set; }
        public float TotalPlaytimeSeconds { get; set; }
        public int SessionCount { get; set; }

        // Per-entity tracking
        public Dictionary<string, StatEntry> ResourcesGathered { get; set; } = new();
        public Dictionary<string, CraftingEntry> RecipesCrafted { get; set; } = new();
        public Dictionary<string, SkillStatEntry> SkillsUsed { get; set; } = new();
        public Dictionary<string, int> ItemsCollected { get; set; } = new();
        public Dictionary<string, int> ItemsUsed { get; set; } = new();

        // Aggregate stats (14 categories)
        public Dictionary<string, object> GatheringTotals { get; private set; }
        public Dictionary<string, object> GatheringAdvanced { get; private set; }
        public Dictionary<string, Dictionary<string, object>> CraftingByDiscipline { get; private set; }
        public Dictionary<string, object> CraftingAdvanced { get; private set; }
        public Dictionary<string, object> CombatDamage { get; private set; }
        public Dictionary<string, object> CombatKills { get; private set; }
        public Dictionary<string, object> CombatActions { get; private set; }
        public Dictionary<string, object> CombatStatusEffects { get; private set; }
        public Dictionary<string, object> CombatSurvival { get; private set; }
        public Dictionary<string, object> ItemCollection { get; private set; }
        public Dictionary<string, object> ItemUsage { get; private set; }
        public Dictionary<string, object> ItemManagement { get; private set; }
        public Dictionary<string, object> SkillUsage { get; private set; }
        public Dictionary<string, object> SkillProgression { get; private set; }
        public Dictionary<string, object> DistanceTraveled { get; private set; }
        public Dictionary<string, object> Exploration { get; private set; }
        public Dictionary<string, object> Economy { get; private set; }
        public Dictionary<string, object> ExperienceStats { get; private set; }
        public Dictionary<string, object> ProgressionMilestones { get; private set; }
        public Dictionary<string, object> TimeStats { get; private set; }
        public Dictionary<string, object> Records { get; private set; }
        public Dictionary<string, object> SocialStats { get; private set; }
        public Dictionary<string, object> EncyclopediaStats { get; private set; }
        public Dictionary<string, object> MiscStats { get; private set; }
        public Dictionary<string, object> DungeonStats { get; private set; }
        public Dictionary<string, object> BarrierStats { get; private set; }
        public Dictionary<string, int> BarriersByMaterial { get; private set; } = new();

        private HashSet<(int, int)> _uniqueChunksVisited = new();

        public StatTracker()
        {
            InitAllCategories();
        }

        private void InitAllCategories()
        {
            InitGatheringStats();
            InitCraftingStats();
            InitCombatStats();
            InitItemStats();
            InitSkillStats();
            InitExplorationStats();
            InitEconomyStats();
            InitProgressionStats();
            InitTimeStats();
            InitRecordsStats();
            InitSocialStats();
            InitEncyclopediaStats();
            InitMiscStats();
            InitDungeonStats();
        }

        // Category initializers — exactly match Python structure for JSON compatibility.
        // Using Dictionary<string, object> preserves Python save format.

        private void InitGatheringStats()
        {
            GatheringTotals = new Dictionary<string, object>
            {
                { "total_trees_chopped", 0 }, { "total_ores_mined", 0 },
                { "total_stones_mined", 0 }, { "total_plants_gathered", 0 },
                { "total_fish_caught", 0 },
                { "tier_1_resources_gathered", 0 }, { "tier_2_resources_gathered", 0 },
                { "tier_3_resources_gathered", 0 }, { "tier_4_resources_gathered", 0 },
                { "fire_resources_gathered", 0 }, { "ice_resources_gathered", 0 },
                { "lightning_resources_gathered", 0 }, { "nature_resources_gathered", 0 },
                { "shadow_resources_gathered", 0 }, { "holy_resources_gathered", 0 },
                { "total_critical_gathers", 0 }, { "total_rare_drops_while_gathering", 0 },
                { "total_gathering_damage_dealt", 0.0 },
                { "axe_swings", 0 }, { "pickaxe_swings", 0 }, { "fishing_rod_casts", 0 },
                { "axe_durability_lost", 0.0 }, { "pickaxe_durability_lost", 0.0 },
                { "fishing_rod_durability_lost", 0.0 },
                { "tools_repaired", 0 }, { "tools_broken", 0 }
            };
            GatheringAdvanced = new Dictionary<string, object>
            {
                { "fastest_tree_chop_time", null }, { "fastest_ore_mine_time", null },
                { "most_resources_one_session", 0 },
                { "current_gather_streak", 0 }, { "longest_gather_streak", 0 },
                { "aoe_gathers_performed", 0 }, { "nodes_broken_via_aoe", 0 },
                { "distance_traveled_to_resources", 0.0 },
                { "largest_fish_caught", 0 }, { "fish_catch_streak", 0 },
                { "longest_fish_catch_streak", 0 },
                { "rare_fish_caught", 0 }, { "legendary_fish_caught", 0 }
            };
        }

        private void InitCraftingStats()
        {
            string[] disciplines = { "smithing", "alchemy", "refining", "engineering", "enchanting" };
            CraftingByDiscipline = new Dictionary<string, Dictionary<string, object>>();
            foreach (string disc in disciplines)
            {
                CraftingByDiscipline[disc] = new Dictionary<string, object>
                {
                    { "total_crafts", 0 }, { "total_attempts", 0 }, { "success_rate", 0.0 },
                    { "perfect_crafts", 0 }, { "first_try_bonuses", 0 },
                    { "tier_1_crafts", 0 }, { "tier_2_crafts", 0 },
                    { "tier_3_crafts", 0 }, { "tier_4_crafts", 0 },
                    { "legendary_crafts", 0 },
                    { "total_time_spent", 0.0 }, { "average_craft_time", 0.0 }
                };
            }
            CraftingAdvanced = new Dictionary<string, object>
            {
                { "total_crafts_all_disciplines", 0 }, { "total_crafting_time_all", 0.0 },
                { "tier_1_crafts_total", 0 }, { "tier_2_crafts_total", 0 },
                { "tier_3_crafts_total", 0 }, { "tier_4_crafts_total", 0 },
                { "common_items_crafted", 0 }, { "uncommon_items_crafted", 0 },
                { "rare_items_crafted", 0 }, { "legendary_items_crafted", 0 },
                { "total_perfect_crafts", 0 }, { "total_first_try_bonuses", 0 },
                { "consecutive_first_try_bonuses", 0 }, { "longest_first_try_streak", 0 },
                { "average_minigame_score", 0.0 }, { "best_minigame_score", 0.0 },
                { "worst_minigame_score", 1.0 },
                { "total_materials_consumed", new Dictionary<string, int>() },
                { "most_used_material", "" }, { "most_used_material_count", 0 }
            };
        }

        private void InitCombatStats()
        {
            CombatDamage = new Dictionary<string, object>
            {
                { "total_damage_dealt", 0.0 }, { "melee_damage_dealt", 0.0 },
                { "ranged_damage_dealt", 0.0 }, { "magic_damage_dealt", 0.0 },
                { "physical_damage_dealt", 0.0 }, { "fire_damage_dealt", 0.0 },
                { "ice_damage_dealt", 0.0 }, { "lightning_damage_dealt", 0.0 },
                { "poison_damage_dealt", 0.0 }, { "arcane_damage_dealt", 0.0 },
                { "shadow_damage_dealt", 0.0 }, { "holy_damage_dealt", 0.0 },
                { "total_damage_taken", 0.0 }, { "melee_damage_taken", 0.0 },
                { "ranged_damage_taken", 0.0 }, { "magic_damage_taken", 0.0 },
                { "physical_damage_taken", 0.0 }, { "fire_damage_taken", 0.0 },
                { "ice_damage_taken", 0.0 }, { "lightning_damage_taken", 0.0 },
                { "poison_damage_taken", 0.0 }, { "arcane_damage_taken", 0.0 },
                { "shadow_damage_taken", 0.0 }, { "holy_damage_taken", 0.0 },
                { "highest_single_hit_dealt", 0.0 }, { "highest_single_hit_taken", 0.0 },
                { "highest_dps_burst", 0.0 }
            };
            CombatKills = new Dictionary<string, object>
            {
                { "total_enemies_defeated", 0 }, { "total_kills", 0 },
                { "tier_1_enemies_killed", 0 }, { "tier_2_enemies_killed", 0 },
                { "tier_3_enemies_killed", 0 }, { "tier_4_enemies_killed", 0 },
                { "boss_enemies_killed", 0 }, { "dragon_boss_defeated", 0 },
                { "elite_enemies_killed", 0 }, { "miniboss_enemies_killed", 0 }
            };
            CombatActions = new Dictionary<string, object>
            {
                { "total_attacks", 0 }, { "melee_attacks", 0 },
                { "ranged_attacks", 0 }, { "magic_attacks", 0 },
                { "critical_hits", 0 }, { "critical_hit_rate", 0.0 },
                { "perfect_dodges", 0 }, { "blocks", 0 }, { "parries", 0 },
                { "sword_attacks", 0 }, { "axe_attacks", 0 },
                { "bow_attacks", 0 }, { "staff_attacks", 0 },
                { "dual_wield_attacks", 0 }, { "unarmed_attacks", 0 },
                { "used_fire_weapon", false }, { "used_ice_weapon", false },
                { "used_lightning_weapon", false },
                { "fire_weapon_kills", 0 }, { "ice_weapon_kills", 0 },
                { "lightning_weapon_kills", 0 }
            };
            CombatStatusEffects = new Dictionary<string, object>
            {
                { "status_effects_applied", new Dictionary<string, int>
                {
                    { "burn", 0 }, { "freeze", 0 }, { "poison", 0 }, { "stun", 0 },
                    { "root", 0 }, { "slow", 0 }, { "bleed", 0 }, { "shock", 0 },
                    { "weaken", 0 }, { "vulnerable", 0 }
                }},
                { "status_effects_received", new Dictionary<string, int>
                {
                    { "burn", 0 }, { "freeze", 0 }, { "poison", 0 }, { "stun", 0 },
                    { "root", 0 }, { "slow", 0 }, { "bleed", 0 }, { "shock", 0 },
                    { "weaken", 0 }, { "vulnerable", 0 }
                }},
                { "dot_damage_dealt", 0.0 }, { "dot_damage_taken", 0.0 },
                { "enemies_cc_duration", 0.0 }, { "player_cc_duration", 0.0 }
            };
            CombatSurvival = new Dictionary<string, object>
            {
                { "total_deaths", 0 }, { "death_by_element", new Dictionary<string, int>() },
                { "total_healing_received", 0.0 }, { "potions_consumed_in_combat", 0 },
                { "health_regenerated", 0.0 }, { "lifesteal_healing", 0.0 },
                { "damage_blocked_by_armor", 0.0 }, { "damage_blocked_by_shield", 0.0 },
                { "damage_reflected", 0.0 },
                { "longest_killstreak", 0 }, { "current_killstreak", 0 },
                { "enemies_killed_without_damage", 0 }
            };
        }

        private void InitItemStats()
        {
            ItemCollection = new Dictionary<string, object>
            {
                { "materials_collected", 0 }, { "equipment_collected", 0 },
                { "consumables_collected", 0 }, { "tools_collected", 0 },
                { "common_items_collected", 0 }, { "uncommon_items_collected", 0 },
                { "rare_items_collected", 0 }, { "legendary_items_collected", 0 },
                { "rare_drops_total", 0 }, { "first_time_discoveries", 0 }
            };
            ItemUsage = new Dictionary<string, object>
            {
                { "total_potions_consumed", 0 }, { "total_food_consumed", 0 },
                { "total_buffs_consumed", 0 },
                { "potions_used_in_combat", 0 }, { "potions_used_out_combat", 0 }
            };
            ItemManagement = new Dictionary<string, object>
            {
                { "items_picked_up", 0 }, { "items_dropped", 0 },
                { "items_destroyed", 0 }, { "inventory_sorts", 0 },
                { "equipment_equipped", new Dictionary<string, int>() },
                { "equipment_unequipped", new Dictionary<string, int>() },
                { "total_equipment_swaps", 0 },
                { "items_repaired", 0 }, { "durability_restored", 0.0 },
                { "repair_materials_used", new Dictionary<string, int>() }
            };
        }

        private void InitSkillStats()
        {
            SkillUsage = new Dictionary<string, object>
            {
                { "total_skills_activated", 0 },
                { "gathering_skills_used", 0 }, { "combat_skills_used", 0 },
                { "crafting_skills_used", 0 }, { "utility_skills_used", 0 },
                { "total_mana_spent", 0.0 }, { "total_mana_regenerated", 0.0 },
                { "skills_on_cooldown_missed", 0 }
            };
            SkillProgression = new Dictionary<string, object>
            {
                { "skills_learned", 0 },
                { "skills_unlocked_via_quest", 0 }, { "skills_unlocked_via_milestone", 0 },
                { "skills_unlocked_via_level", 0 }, { "skills_unlocked_via_purchase", 0 },
                { "skills_unlocked_via_title", 0 },
                { "skill_levels_gained", 0 }, { "max_level_skills", 0 },
                { "total_skill_exp_earned", new Dictionary<string, int>() }
            };
        }

        private void InitExplorationStats()
        {
            DistanceTraveled = new Dictionary<string, object>
            {
                { "total_distance", 0.0 }, { "distance_walked", 0.0 },
                { "distance_sprinted", 0.0 }, { "distance_while_encumbered", 0.0 },
                { "distance_in_forest", 0.0 }, { "distance_in_mountains", 0.0 },
                { "distance_in_plains", 0.0 }, { "distance_in_caves", 0.0 }
            };
            Exploration = new Dictionary<string, object>
            {
                { "unique_chunks_visited", 0 }, { "total_chunk_entries", 0 },
                { "furthest_distance_from_spawn", 0.0 },
                { "resource_nodes_discovered", 0 }, { "crafting_stations_discovered", 0 },
                { "npcs_met", 0 }, { "landmarks_discovered", 0 },
                { "dungeons_discovered", 0 }, { "bosses_discovered", 0 }
            };
        }

        private void InitEconomyStats()
        {
            Economy = new Dictionary<string, object>
            {
                { "total_gold_earned", 0 }, { "total_gold_spent", 0 },
                { "current_gold", 0 }, { "highest_gold_balance", 0 },
                { "trades_made", 0 }, { "items_bought", 0 }, { "items_sold", 0 },
                { "gold_from_combat", 0 }, { "gold_from_quests", 0 },
                { "gold_from_selling", 0 },
                { "gold_spent_on_skills", 0 }, { "gold_spent_on_items", 0 },
                { "gold_spent_on_repairs", 0 }
            };
        }

        private void InitProgressionStats()
        {
            ExperienceStats = new Dictionary<string, object>
            {
                { "total_exp_earned", 0 }, { "total_exp_to_next_level", 0 },
                { "exp_from_gathering", 0 }, { "exp_from_crafting", 0 },
                { "exp_from_combat", 0 }, { "exp_from_quests", 0 },
                { "exp_from_exploration", 0 }, { "exp_from_fishing", 0 },
                { "total_levels_gained", 0 }, { "highest_level_reached", 0 },
                { "stat_points_allocated", 0 }, { "stat_points_remaining", 0 }
            };
            ProgressionMilestones = new Dictionary<string, object>
            {
                { "titles_earned", 0 },
                { "novice_titles", 0 }, { "apprentice_titles", 0 },
                { "journeyman_titles", 0 }, { "expert_titles", 0 },
                { "master_titles", 0 }, { "hidden_titles", 0 },
                { "class_selected", "" }, { "class_changes", 0 },
                { "achievements_unlocked", 0 }
            };
        }

        private void InitTimeStats()
        {
            TimeStats = new Dictionary<string, object>
            {
                { "total_playtime_seconds", 0.0 }, { "session_count", 0 },
                { "current_session_time", 0.0 }, { "longest_session", 0.0 },
                { "average_session_length", 0.0 },
                { "time_spent_gathering", 0.0 }, { "time_spent_crafting", 0.0 },
                { "time_spent_in_combat", 0.0 }, { "time_spent_exploring", 0.0 },
                { "time_spent_in_menus", 0.0 }, { "time_spent_idle", 0.0 },
                { "first_played_timestamp", null }, { "last_played_timestamp", null },
                { "days_since_first_played", 0 }
            };
        }

        private void InitRecordsStats()
        {
            Records = new Dictionary<string, object>
            {
                { "highest_damage_single_hit", 0.0 }, { "highest_dps_5_seconds", 0.0 },
                { "longest_combat_duration", 0.0 },
                { "fastest_boss_kill", null }, { "fastest_craft", null },
                { "best_minigame_score", 0.0 },
                { "longest_crafting_session", 0 }, { "most_resources_single_node", 0 },
                { "fastest_node_break", null }, { "longest_gathering_session", 0 },
                { "current_first_try_streak", 0 }, { "longest_first_try_streak", 0 },
                { "current_no_damage_streak", 0 }, { "longest_killstreak", 0 },
                { "best_exp_per_hour", 0.0 }, { "best_gold_per_hour", 0.0 },
                { "best_crafts_per_hour", 0 }
            };
        }

        private void InitSocialStats()
        {
            SocialStats = new Dictionary<string, object>
            {
                { "npcs_met", 0 }, { "npc_dialogues_completed", 0 },
                { "npc_reputation", new Dictionary<string, int>() },
                { "quests_started", 0 }, { "quests_completed", 0 }, { "quests_failed", 0 },
                { "quest_exp_earned", 0 }, { "quest_gold_earned", 0 },
                { "gathering_quests_completed", 0 }, { "combat_quests_completed", 0 },
                { "crafting_quests_completed", 0 }, { "exploration_quests_completed", 0 }
            };
        }

        private void InitEncyclopediaStats()
        {
            EncyclopediaStats = new Dictionary<string, object>
            {
                { "unique_items_discovered", 0 }, { "unique_recipes_discovered", 0 },
                { "unique_enemies_encountered", 0 }, { "unique_resources_found", 0 },
                { "encyclopedia_completion_percent", 0.0 },
                { "materials_encyclopedia_complete", false },
                { "equipment_encyclopedia_complete", false },
                { "recipes_encyclopedia_complete", false },
                { "first_time_item_finds", 0 }, { "first_time_recipe_unlocks", 0 }
            };
        }

        private void InitMiscStats()
        {
            MiscStats = new Dictionary<string, object>
            {
                { "inventory_opens", 0 }, { "crafting_menu_opens", 0 },
                { "skill_menu_opens", 0 }, { "map_opens", 0 },
                { "manual_saves", 0 }, { "auto_saves", 0 }, { "game_loads", 0 },
                { "debug_mode_activations", 0 }, { "debug_resources_spawned", 0 },
                { "jumps", 0 }, { "emotes_used", 0 }, { "screenshots_taken", 0 },
                { "total_deaths", 0 }, { "items_lost_on_death", 0 },
                { "soulbound_items_kept_on_death", 0 }
            };
            BarrierStats = new Dictionary<string, object>
            {
                { "barriers_placed", 0 }, { "barriers_picked_up", 0 },
                { "attacks_blocked_by_barriers", 0 },
                { "enemy_attacks_blocked", 0 }, { "player_attacks_blocked", 0 },
                { "turret_attacks_blocked", 0 }
            };
        }

        private void InitDungeonStats()
        {
            DungeonStats = new Dictionary<string, object>
            {
                { "dungeons_entered", 0 }, { "dungeons_completed", 0 },
                { "dungeons_abandoned", 0 },
                { "common_dungeons_completed", 0 }, { "uncommon_dungeons_completed", 0 },
                { "rare_dungeons_completed", 0 }, { "epic_dungeons_completed", 0 },
                { "legendary_dungeons_completed", 0 }, { "unique_dungeons_completed", 0 },
                { "dungeon_enemies_killed", 0 }, { "dungeon_deaths", 0 },
                { "waves_completed", 0 },
                { "dungeon_chests_opened", 0 }, { "dungeon_items_received", 0 },
                { "fastest_dungeon_clear", null }, { "highest_rarity_cleared", "" },
                { "most_enemies_killed_single_dungeon", 0 },
                { "total_dungeon_exp_earned", 0 }
            };
        }

        // === Recording Methods ===

        public void StartSession()
        {
            SessionStartTime = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            SessionCount++;
            TimeStats["session_count"] = SessionCount;
            if (TimeStats["first_played_timestamp"] == null)
                TimeStats["first_played_timestamp"] = SessionStartTime;
        }

        public void RecordResourceGathered(string resourceId, int quantity = 1, int tier = 1,
            string category = "ore", string element = null, bool isCrit = false, bool isRareDrop = false)
        {
            if (!ResourcesGathered.ContainsKey(resourceId))
                ResourcesGathered[resourceId] = new StatEntry();
            ResourcesGathered[resourceId].Record(quantity);

            string catLower = category.ToLower();
            if (catLower.Contains("tree") || catLower.Contains("wood"))
                IncrementInt(GatheringTotals, "total_trees_chopped");
            else if (catLower.Contains("ore"))
                IncrementInt(GatheringTotals, "total_ores_mined");
            else if (catLower.Contains("stone") || catLower.Contains("rock"))
                IncrementInt(GatheringTotals, "total_stones_mined");
            else if (catLower.Contains("plant") || catLower.Contains("herb"))
                IncrementInt(GatheringTotals, "total_plants_gathered");
            else if (catLower.Contains("fish"))
                IncrementInt(GatheringTotals, "total_fish_caught", quantity);

            IncrementInt(GatheringTotals, $"tier_{tier}_resources_gathered");
            if (!string.IsNullOrEmpty(element))
                IncrementInt(GatheringTotals, $"{element.ToLower()}_resources_gathered");
            if (isCrit)
                IncrementInt(GatheringTotals, "total_critical_gathers");
            if (isRareDrop)
            {
                IncrementInt(GatheringTotals, "total_rare_drops_while_gathering");
                IncrementInt(ItemCollection, "rare_drops_total");
            }
        }

        public void RecordDamageDealt(float amount, string damageType = "physical",
            string attackType = "melee", bool wasCrit = false)
        {
            IncrementFloat(CombatDamage, "total_damage_dealt", amount);
            IncrementFloat(CombatDamage, $"{attackType.ToLower()}_damage_dealt", amount);
            IncrementFloat(CombatDamage, $"{damageType.ToLower()}_damage_dealt", amount);

            float current = Convert.ToSingle(CombatDamage.GetValueOrDefault("highest_single_hit_dealt", 0.0));
            if (amount > current) CombatDamage["highest_single_hit_dealt"] = (double)amount;

            IncrementInt(CombatActions, "total_attacks");
            IncrementInt(CombatActions, $"{attackType.ToLower()}_attacks");
            if (wasCrit) IncrementInt(CombatActions, "critical_hits");
        }

        public void RecordDamageTaken(float amount, string damageType = "physical", string attackType = "melee")
        {
            IncrementFloat(CombatDamage, "total_damage_taken", amount);
            IncrementFloat(CombatDamage, $"{attackType.ToLower()}_damage_taken", amount);
            IncrementFloat(CombatDamage, $"{damageType.ToLower()}_damage_taken", amount);

            float current = Convert.ToSingle(CombatDamage.GetValueOrDefault("highest_single_hit_taken", 0.0));
            if (amount > current) CombatDamage["highest_single_hit_taken"] = (double)amount;

            CombatSurvival["current_killstreak"] = 0;
        }

        public void RecordEnemyKilled(int tier = 1, bool isBoss = false, bool isDragon = false)
        {
            IncrementInt(CombatKills, "total_enemies_defeated");
            IncrementInt(CombatKills, "total_kills");
            IncrementInt(CombatKills, $"tier_{tier}_enemies_killed");
            if (isBoss) IncrementInt(CombatKills, "boss_enemies_killed");
            if (isDragon) IncrementInt(CombatKills, "dragon_boss_defeated");

            int streak = Convert.ToInt32(CombatSurvival.GetValueOrDefault("current_killstreak", 0)) + 1;
            CombatSurvival["current_killstreak"] = streak;
            int longest = Convert.ToInt32(CombatSurvival.GetValueOrDefault("longest_killstreak", 0));
            if (streak > longest) CombatSurvival["longest_killstreak"] = streak;
        }

        public void RecordSkillUsed(string skillId, float value = 0f, float manaCost = 0f,
            int targets = 0, string category = "utility")
        {
            if (!SkillsUsed.ContainsKey(skillId))
                SkillsUsed[skillId] = new SkillStatEntry();
            SkillsUsed[skillId].RecordUse(value, manaCost, targets);

            IncrementInt(SkillUsage, "total_skills_activated");
            IncrementFloat(SkillUsage, "total_mana_spent", manaCost);
            IncrementInt(SkillUsage, $"{category.ToLower()}_skills_used");
        }

        public void RecordMovement(float distance, (int, int) chunkCoords,
            bool isSprinting = false, bool isEncumbered = false)
        {
            IncrementFloat(DistanceTraveled, "total_distance", distance);
            IncrementFloat(DistanceTraveled, isSprinting ? "distance_sprinted" : "distance_walked", distance);
            if (isEncumbered) IncrementFloat(DistanceTraveled, "distance_while_encumbered", distance);

            if (_uniqueChunksVisited.Add(chunkCoords))
                Exploration["unique_chunks_visited"] = _uniqueChunksVisited.Count;
            IncrementInt(Exploration, "total_chunk_entries");
        }

        public void RecordEquipmentSwap(string equipKey, bool isEquip)
        {
            IncrementInt(ItemManagement, "total_equipment_swaps");
        }

        public void RecordDeath()
        {
            IncrementInt(MiscStats, "total_deaths");
        }

        // === Utility ===

        /// <summary>
        /// Get a stat value by dotted path (e.g., "combat_damage.total_damage_dealt").
        /// Used by ICharacterState.GetStatTrackerValue().
        /// </summary>
        public float GetValue(string path)
        {
            string[] parts = path.Split('.');
            if (parts.Length < 2) return 0f;

            Dictionary<string, object> category = parts[0] switch
            {
                "gathering_totals" => GatheringTotals,
                "combat_damage" => CombatDamage,
                "combat_kills" => CombatKills,
                "combat_actions" => CombatActions,
                "combat_survival" => CombatSurvival,
                "exploration" => Exploration,
                "economy" => Economy,
                "experience_stats" => ExperienceStats,
                "progression_milestones" => ProgressionMilestones,
                "misc_stats" => MiscStats,
                "dungeon_stats" => DungeonStats,
                _ => null
            };

            if (category != null && category.TryGetValue(parts[1], out var val) && val != null)
            {
                try { return Convert.ToSingle(val); }
                catch { return 0f; }
            }
            return 0f;
        }

        // === Serialization ===

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                { "version", "1.0" },
                { "session_start_time", SessionStartTime },
                { "total_playtime_seconds", TotalPlaytimeSeconds },
                { "session_count", SessionCount },
                { "resources_gathered", ResourcesGathered.ToDictionary(kv => kv.Key, kv => (object)kv.Value.ToSaveData()) },
                { "recipes_crafted", RecipesCrafted.ToDictionary(kv => kv.Key, kv => (object)kv.Value.ToSaveData()) },
                { "skills_used", SkillsUsed.ToDictionary(kv => kv.Key, kv => (object)kv.Value.ToSaveData()) },
                { "items_collected", new Dictionary<string, int>(ItemsCollected) },
                { "items_used", new Dictionary<string, int>(ItemsUsed) },
                { "gathering_totals", new Dictionary<string, object>(GatheringTotals) },
                { "gathering_advanced", new Dictionary<string, object>(GatheringAdvanced) },
                { "crafting_by_discipline", CraftingByDiscipline },
                { "crafting_advanced", new Dictionary<string, object>(CraftingAdvanced) },
                { "combat_damage", new Dictionary<string, object>(CombatDamage) },
                { "combat_kills", new Dictionary<string, object>(CombatKills) },
                { "combat_actions", new Dictionary<string, object>(CombatActions) },
                { "combat_status_effects", new Dictionary<string, object>(CombatStatusEffects) },
                { "combat_survival", new Dictionary<string, object>(CombatSurvival) },
                { "item_collection", new Dictionary<string, object>(ItemCollection) },
                { "item_usage", new Dictionary<string, object>(ItemUsage) },
                { "item_management", new Dictionary<string, object>(ItemManagement) },
                { "skill_usage", new Dictionary<string, object>(SkillUsage) },
                { "skill_progression", new Dictionary<string, object>(SkillProgression) },
                { "distance_traveled", new Dictionary<string, object>(DistanceTraveled) },
                { "exploration", new Dictionary<string, object>(Exploration) },
                { "unique_chunks_visited", _uniqueChunksVisited.Select(c => new[] { c.Item1, c.Item2 }).ToList() },
                { "economy", new Dictionary<string, object>(Economy) },
                { "experience_stats", new Dictionary<string, object>(ExperienceStats) },
                { "progression_milestones", new Dictionary<string, object>(ProgressionMilestones) },
                { "time_stats", new Dictionary<string, object>(TimeStats) },
                { "records", new Dictionary<string, object>(Records) },
                { "social_stats", new Dictionary<string, object>(SocialStats) },
                { "encyclopedia_stats", new Dictionary<string, object>(EncyclopediaStats) },
                { "misc_stats", new Dictionary<string, object>(MiscStats) },
                { "dungeon_stats", new Dictionary<string, object>(DungeonStats) },
                { "barrier_stats", new Dictionary<string, object>(BarrierStats) },
                { "barriers_by_material", new Dictionary<string, int>(BarriersByMaterial) }
            };
        }

        public static StatTracker FromSaveData(Dictionary<string, object> data)
        {
            if (data == null) return new StatTracker();

            var tracker = new StatTracker();
            if (data.TryGetValue("session_start_time", out var sst) && sst != null)
                tracker.SessionStartTime = Convert.ToDouble(sst);
            tracker.TotalPlaytimeSeconds = Convert.ToSingle(data.GetValueOrDefault("total_playtime_seconds", 0f));
            tracker.SessionCount = Convert.ToInt32(data.GetValueOrDefault("session_count", 0));

            // Restore per-entity tracking would require deep deserialization.
            // Full restoration is delegated to save_system integration (Phase 4).
            // Session-level aggregates are restored here for ICharacterState.GetStatTrackerValue().

            RestoreDict(tracker.GatheringTotals, data, "gathering_totals");
            RestoreDict(tracker.CombatDamage, data, "combat_damage");
            RestoreDict(tracker.CombatKills, data, "combat_kills");
            RestoreDict(tracker.CombatActions, data, "combat_actions");
            RestoreDict(tracker.CombatSurvival, data, "combat_survival");
            RestoreDict(tracker.Exploration, data, "exploration");
            RestoreDict(tracker.Economy, data, "economy");
            RestoreDict(tracker.ExperienceStats, data, "experience_stats");
            RestoreDict(tracker.ProgressionMilestones, data, "progression_milestones");
            RestoreDict(tracker.MiscStats, data, "misc_stats");
            RestoreDict(tracker.DungeonStats, data, "dungeon_stats");
            RestoreDict(tracker.BarrierStats, data, "barrier_stats");
            RestoreDict(tracker.TimeStats, data, "time_stats");
            RestoreDict(tracker.Records, data, "records");

            return tracker;
        }

        // === Helper methods for incrementing dict values ===

        private static void IncrementInt(Dictionary<string, object> dict, string key, int amount = 1)
        {
            if (dict.ContainsKey(key))
                dict[key] = Convert.ToInt32(dict[key]) + amount;
        }

        private static void IncrementFloat(Dictionary<string, object> dict, string key, double amount)
        {
            if (dict.ContainsKey(key))
                dict[key] = Convert.ToDouble(dict[key]) + amount;
        }

        private static void RestoreDict(Dictionary<string, object> target, Dictionary<string, object> source, string key)
        {
            if (source.TryGetValue(key, out var val) && val is Dictionary<string, object> dict)
            {
                foreach (var kv in dict)
                {
                    if (target.ContainsKey(kv.Key))
                        target[kv.Key] = kv.Value;
                }
            }
        }
    }
}
