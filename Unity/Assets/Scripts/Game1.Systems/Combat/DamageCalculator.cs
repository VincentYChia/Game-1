// ============================================================================
// Game1.Systems.Combat.DamageCalculator
// Migrated from: Combat/combat_manager.py (lines 684-982)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Extracted pure-math damage calculation from CombatManager.
// All formulas MUST match Python source exactly.
//
// Damage Pipeline (player attacking enemy):
//   Base Damage (weapon, 0=unarmed=5)
//     x Tool Effectiveness Penalty
//     x Hand Type Bonus (2H=+20%, versatile-no-offhand=+10%)
//     x STR Multiplier (1.0 + STR * 0.05)
//     x Title Melee Bonus (1.0 + totalBonus)
//     x Enemy-Specific Damage Multiplier
//     x Crushing Bonus vs Armored (if defense > 10)
//     x Skill Buff Bonus (empower)
//     x Critical Hit (2x if triggered)
//     - Defense Reduction (effective_defense * 0.01, capped at 0.75)
//   = Final Damage
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Result of a damage calculation. Contains final damage, pre-defense raw damage,
    /// and whether a critical hit occurred.
    /// </summary>
    public class DamageResult
    {
        /// <summary>Final damage after all multipliers and defense reduction.</summary>
        public float FinalDamage { get; set; }

        /// <summary>Whether this attack was a critical hit (2x multiplier applied).</summary>
        public bool IsCritical { get; set; }

        /// <summary>Raw damage before defense reduction was applied.</summary>
        public float RawDamage { get; set; }

        /// <summary>Detailed breakdown of each damage step for debugging/logging.</summary>
        public DamageBreakdown Breakdown { get; set; }
    }

    /// <summary>
    /// Optional damage breakdown for debugging. Each field stores the value
    /// at that step of the pipeline.
    /// </summary>
    public class DamageBreakdown
    {
        public int BaseWeaponDamage { get; set; }
        public float ToolEffectiveness { get; set; }
        public float WeaponTagMultiplier { get; set; }
        public float StrMultiplier { get; set; }
        public float TitleMultiplier { get; set; }
        public float EnemyDamageMultiplier { get; set; }
        public float CrushingMultiplier { get; set; }
        public float SkillBuffMultiplier { get; set; }
        public float CritMultiplier { get; set; }
        public float CritChance { get; set; }
        public float DefenseReduction { get; set; }
        public float ArmorPenetration { get; set; }
    }

    /// <summary>
    /// Weapon tag-derived combat modifiers.
    /// Populated from weapon metadata tags (2H, versatile, precision, crushing, armor_breaker).
    /// Migrated from: entities/components/weapon_tag_calculator.py
    /// </summary>
    public class WeaponTagModifiers
    {
        /// <summary>
        /// Damage multiplier from hand requirement.
        /// 1.2 for 2H, 1.1 for versatile without offhand, 1.0 otherwise.
        /// Python: WeaponTagModifiers.get_damage_multiplier()
        /// </summary>
        public float DamageMultiplier { get; set; } = 1.0f;

        /// <summary>
        /// Bonus damage vs armored enemies (defense > 10).
        /// Python: WeaponTagModifiers.get_damage_vs_armored_bonus()
        /// Crushing tag = +20% = 0.2
        /// </summary>
        public float CrushingBonus { get; set; } = 0f;

        /// <summary>
        /// Bonus crit chance from precision tag.
        /// Python: WeaponTagModifiers.get_crit_chance_bonus()
        /// Precision = +10% = 0.10
        /// </summary>
        public float CritBonus { get; set; } = 0f;

        /// <summary>
        /// Armor penetration fraction (0.0-1.0). Armor_breaker = 0.25 (ignore 25% defense).
        /// Python: WeaponTagModifiers.get_armor_penetration()
        /// </summary>
        public float ArmorPenetration { get; set; } = 0f;

        /// <summary>
        /// Lifesteal percentage from enchantment. Capped at 50% in application.
        /// </summary>
        public float LifestealPercent { get; set; } = 0f;

        /// <summary>
        /// Chain damage percentage per chain target. Default 50% = 0.5.
        /// </summary>
        public float ChainDamagePercent { get; set; } = 0f;

        /// <summary>
        /// Number of enemies to chain to (default 0 = no chain).
        /// </summary>
        public int ChainCount { get; set; } = 0;

        /// <summary>
        /// Populate modifiers from a list of weapon metadata tags.
        /// Mirrors Python WeaponTagModifiers static methods.
        /// </summary>
        /// <param name="tags">Weapon metadata tags (e.g., "2H", "precision", "crushing").</param>
        /// <param name="hasOffhand">Whether the player has an offhand item equipped.</param>
        public static WeaponTagModifiers FromTags(IList<string> tags, bool hasOffhand)
        {
            var mods = new WeaponTagModifiers();

            if (tags == null || tags.Count == 0)
                return mods;

            // Hand requirement damage bonus
            // Python: if "2H" in tags: multiplier *= 1.2
            //         elif "versatile" in tags and not has_offhand: multiplier *= 1.1
            bool is2H = false;
            bool isVersatile = false;
            bool hasPrecision = false;
            bool hasCrushing = false;
            bool hasArmorBreaker = false;

            foreach (string tag in tags)
            {
                switch (tag)
                {
                    case "2H":
                        is2H = true;
                        break;
                    case "versatile":
                        isVersatile = true;
                        break;
                    case "precision":
                        hasPrecision = true;
                        break;
                    case "crushing":
                        hasCrushing = true;
                        break;
                    case "armor_breaker":
                        hasArmorBreaker = true;
                        break;
                }
            }

            if (is2H)
            {
                mods.DamageMultiplier = 1.2f;
            }
            else if (isVersatile && !hasOffhand)
            {
                mods.DamageMultiplier = 1.1f;
            }

            // Precision: +10% crit chance
            if (hasPrecision)
            {
                mods.CritBonus = 0.10f;
            }

            // Crushing: +20% vs armored (defense > 10)
            if (hasCrushing)
            {
                mods.CrushingBonus = 0.20f;
            }

            // Armor breaker: ignore 25% defense
            if (hasArmorBreaker)
            {
                mods.ArmorPenetration = 0.25f;
            }

            return mods;
        }
    }

    /// <summary>
    /// Aggregated title bonuses relevant to combat.
    /// Populated from the title system's earned titles.
    /// </summary>
    public class TitleBonuses
    {
        /// <summary>
        /// Total melee damage bonus from titles (e.g., 0.1 = +10%).
        /// Python: self.character.titles.get_total_bonus('meleeDamage')
        /// </summary>
        public float MeleeDamageBonus { get; set; } = 0f;

        /// <summary>
        /// Total critical chance bonus from titles.
        /// Python: self.character.titles.get_total_bonus('criticalChance')
        /// </summary>
        public float CriticalChanceBonus { get; set; } = 0f;

        /// <summary>
        /// Total counter chance bonus from titles (not yet implemented in Python).
        /// Python: self.character.titles.get_total_bonus('counterChance')
        /// </summary>
        public float CounterChanceBonus { get; set; } = 0f;
    }

    /// <summary>
    /// Minimal stat interface for damage calculation.
    /// Avoids direct dependency on the full CharacterStats class.
    /// </summary>
    public interface ICombatStats
    {
        int Strength { get; }
        int Defense { get; }
        int Luck { get; }

        /// <summary>
        /// Get effective luck including title and skill bonuses.
        /// Python: self.character.get_effective_luck()
        /// </summary>
        int GetEffectiveLuck();

        /// <summary>
        /// Get durability loss multiplier from DEF stat.
        /// Python: self.character.stats.get_durability_loss_multiplier()
        /// </summary>
        float GetDurabilityLossMultiplier();
    }

    /// <summary>
    /// Minimal buff interface for damage calculation.
    /// </summary>
    public interface ICombatBuffs
    {
        /// <summary>
        /// Get total damage bonus from empower buffs for a given category.
        /// Python: self.character.buffs.get_damage_bonus(category)
        /// </summary>
        float GetDamageBonus(string category);

        /// <summary>
        /// Get total bonus of a given type for a given category.
        /// Python: self.character.buffs.get_total_bonus(type, category)
        /// </summary>
        float GetTotalBonus(string type, string category);

        /// <summary>
        /// Get flat defense bonus from fortify buffs.
        /// Python: self.character.buffs.get_defense_bonus()
        /// </summary>
        float GetDefenseBonus();
    }

    /// <summary>
    /// Minimal enemy definition interface for damage calculation.
    /// </summary>
    public interface IEnemyTarget
    {
        float Defense { get; }
        bool IsBoss { get; }
        int Tier { get; }
        string EnemyId { get; }
    }

    /// <summary>
    /// Pure static damage calculator. Extracts all damage math from CombatManager
    /// into a stateless, testable utility class.
    ///
    /// Every constant and formula matches the Python source exactly:
    ///   - STR multiplier: 1.0 + (STR * 0.05)
    ///   - Crit chance: 0.02 * effectiveLuck + pierce + weaponCrit + titleCrit
    ///   - Crit multiplier: 2.0x
    ///   - Defense reduction: effective_defense * 0.01, capped at 0.75
    ///   - Unarmed damage: 5
    /// </summary>
    public static class DamageCalculator
    {
        /// <summary>
        /// Unarmed base damage when no weapon is equipped.
        /// Python: if weapon_damage == 0: weapon_damage = 5
        /// </summary>
        public const int UnarmedDamage = 5;

        /// <summary>
        /// Maximum defense reduction cap (75%).
        /// Python: min(0.75, defense_reduction)
        /// </summary>
        public const float MaxDefenseReduction = 0.75f;

        /// <summary>
        /// Critical hit damage multiplier.
        /// Python: base_damage *= 2.0
        /// </summary>
        public const float CritMultiplier = 2.0f;

        /// <summary>
        /// Critical chance per luck point.
        /// Python: base_crit_chance = 0.02 * effective_luck
        /// </summary>
        public const float CritChancePerLuck = 0.02f;

        /// <summary>
        /// STR damage bonus per point.
        /// Python: str_multiplier = 1.0 + (self.character.stats.strength * 0.05)
        /// </summary>
        public const float StrDamagePerPoint = 0.05f;

        /// <summary>
        /// Maximum lifesteal percentage cap.
        /// Python: lifesteal_percent = min(effect.get('value', 0.1), 0.50)
        /// </summary>
        public const float MaxLifestealPercent = 0.50f;

        /// <summary>
        /// Maximum thorns/reflect damage percentage cap.
        /// Python: reflect_percent = min(reflect_percent, 0.80)
        /// </summary>
        public const float MaxReflectPercent = 0.80f;

        /// <summary>
        /// Defense reduction per enemy defense point.
        /// Python: defense_reduction = effective_defense * 0.01
        /// </summary>
        public const float DefenseReductionPerPoint = 0.01f;

        /// <summary>
        /// Enemy defense threshold for crushing bonus to apply.
        /// Python: if crushing_bonus > 0 and enemy.definition.defense > 10
        /// </summary>
        public const float CrushingDefenseThreshold = 10f;

        /// <summary>
        /// Calculate player damage to an enemy.
        ///
        /// Implements the full damage pipeline from combat_manager.py player_attack_enemy()
        /// lines 684-982. Each step is documented with the corresponding Python source.
        /// </summary>
        /// <param name="weaponDamage">Raw weapon damage (0 = unarmed).</param>
        /// <param name="toolTypeEffectiveness">Tool effectiveness penalty (1.0 = weapon, less for tools).</param>
        /// <param name="weaponTags">Weapon tag modifiers (2H, precision, crushing, etc.).</param>
        /// <param name="strength">Character STR stat value.</param>
        /// <param name="effectiveLuck">Effective luck including title/skill bonuses.</param>
        /// <param name="titles">Aggregated title bonuses.</param>
        /// <param name="empowerBonus">Current empower buff damage bonus (0.0 if none).</param>
        /// <param name="pierceBonus">Current pierce buff crit chance bonus (0.0 if none).</param>
        /// <param name="enemyDamageMultiplier">Enemy-specific damage multiplier (e.g., beastDamage).</param>
        /// <param name="enemyDefense">Enemy defense stat.</param>
        /// <param name="rng">Random number generator for crit rolls.</param>
        /// <returns>DamageResult with final damage, crit flag, and raw (pre-defense) damage.</returns>
        public static DamageResult CalculatePlayerDamage(
            int weaponDamage,
            float toolTypeEffectiveness,
            WeaponTagModifiers weaponTags,
            int strength,
            int effectiveLuck,
            TitleBonuses titles,
            float empowerBonus,
            float pierceBonus,
            float enemyDamageMultiplier,
            float enemyDefense,
            Random rng)
        {
            var breakdown = new DamageBreakdown();

            // Step 1: Base weapon damage (0 = unarmed = 5)
            // Python: if weapon_damage == 0: weapon_damage = 5
            int baseDamage = weaponDamage;
            if (baseDamage == 0)
            {
                baseDamage = UnarmedDamage;
            }
            breakdown.BaseWeaponDamage = baseDamage;

            // Step 2: Tool effectiveness penalty
            // Python: weapon_damage = int(weapon_damage * tool_type_effectiveness)
            breakdown.ToolEffectiveness = toolTypeEffectiveness;
            float damage = (int)(baseDamage * toolTypeEffectiveness);

            // Step 3: Weapon tag damage multiplier (2H=+20%, versatile-no-offhand=+10%)
            // Python: weapon_damage = int(weapon_damage * weapon_tag_damage_mult)
            if (weaponTags != null)
            {
                breakdown.WeaponTagMultiplier = weaponTags.DamageMultiplier;
                damage = (int)(damage * weaponTags.DamageMultiplier);
            }
            else
            {
                breakdown.WeaponTagMultiplier = 1.0f;
            }

            // Step 4: STR multiplier: 1.0 + (STR * 0.05)
            // Python: str_multiplier = 1.0 + (self.character.stats.strength * 0.05)
            float strMultiplier = 1.0f + (strength * StrDamagePerPoint);
            breakdown.StrMultiplier = strMultiplier;
            damage *= strMultiplier;

            // Step 5: Title melee bonus
            // Python: title_multiplier = 1.0 + title_melee_bonus
            float titleMultiplier = 1.0f + (titles?.MeleeDamageBonus ?? 0f);
            breakdown.TitleMultiplier = titleMultiplier;
            damage *= titleMultiplier;

            // Step 6: Enemy-specific damage multiplier
            // Python: enemy_damage_multiplier = self.character.get_enemy_damage_multiplier(enemy)
            breakdown.EnemyDamageMultiplier = enemyDamageMultiplier;
            damage *= enemyDamageMultiplier;

            // Step 7: Crushing bonus vs armored (defense > 10)
            // Python: if crushing_bonus > 0 and enemy.definition.defense > 10:
            //             base_damage *= (1.0 + crushing_bonus)
            float crushingMult = 1.0f;
            if (weaponTags != null && weaponTags.CrushingBonus > 0f && enemyDefense > CrushingDefenseThreshold)
            {
                crushingMult = 1.0f + weaponTags.CrushingBonus;
                damage *= crushingMult;
            }
            breakdown.CrushingMultiplier = crushingMult;

            // Step 8: Skill buff bonus (empower)
            // Python: skill_damage_bonus = max(empower_damage, empower_combat)
            //         base_damage *= (1.0 + skill_damage_bonus)
            float skillBuffMult = 1.0f;
            if (empowerBonus > 0f)
            {
                skillBuffMult = 1.0f + empowerBonus;
                damage *= skillBuffMult;
            }
            breakdown.SkillBuffMultiplier = skillBuffMult;

            // Step 9: Critical hit check
            // Python: base_crit_chance = 0.02 * effective_luck
            //         crit_chance = base_crit_chance + pierce_bonus + weapon_tag_crit_bonus + title_crit_bonus
            //         if random.random() < crit_chance: base_damage *= 2.0
            float baseCritChance = CritChancePerLuck * effectiveLuck;
            float weaponCritBonus = weaponTags?.CritBonus ?? 0f;
            float titleCritBonus = titles?.CriticalChanceBonus ?? 0f;
            float totalCritChance = baseCritChance + pierceBonus + weaponCritBonus + titleCritBonus;
            breakdown.CritChance = totalCritChance;

            bool isCritical = false;
            if (rng.NextDouble() < totalCritChance)
            {
                isCritical = true;
                damage *= CritMultiplier;
                breakdown.CritMultiplier = CritMultiplier;
            }
            else
            {
                breakdown.CritMultiplier = 1.0f;
            }

            // Store raw damage (pre-defense)
            float rawDamage = damage;

            // Step 10: Defense reduction
            // Python: effective_defense = enemy.definition.defense * (1.0 - armor_penetration)
            //         defense_reduction = effective_defense * 0.01
            //         final_damage = base_damage * (1.0 - min(0.75, defense_reduction))
            float armorPen = weaponTags?.ArmorPenetration ?? 0f;
            float effectiveDefense = enemyDefense * (1.0f - armorPen);
            float defenseReduction = effectiveDefense * DefenseReductionPerPoint;
            float clampedReduction = Math.Min(MaxDefenseReduction, defenseReduction);

            breakdown.ArmorPenetration = armorPen;
            breakdown.DefenseReduction = clampedReduction;

            float finalDamage = damage * (1.0f - clampedReduction);

            return new DamageResult
            {
                FinalDamage = finalDamage,
                IsCritical = isCritical,
                RawDamage = rawDamage,
                Breakdown = breakdown
            };
        }

        /// <summary>
        /// Calculate enemy damage to player.
        ///
        /// Implements the full defensive pipeline from combat_manager.py _enemy_attack_player()
        /// lines 1497-1680.
        ///
        /// Pipeline:
        ///   Enemy base damage (perform_attack roll)
        ///     x DEF stat multiplier (1.0 - DEF * 0.02)
        ///     x Armor multiplier (1.0 - armor_bonus * 0.01)
        ///     x Protection enchantment multiplier (1.0 - total_protection)
        ///     x Shield blocking multiplier (1.0 - shield_reduction)
        ///     - Fortify flat reduction
        ///     = Final damage (minimum 1)
        /// </summary>
        /// <param name="baseDamage">Raw enemy damage (from Enemy.PerformAttack()).</param>
        /// <param name="defenseStat">Player DEF stat value.</param>
        /// <param name="armorBonus">Total armor defense from equipment.</param>
        /// <param name="protectionReduction">Total protection enchantment reduction (0.0-1.0).</param>
        /// <param name="shieldBlocking">Whether player is actively blocking with shield.</param>
        /// <param name="shieldReduction">Shield damage reduction percentage (0.0-1.0).</param>
        /// <param name="fortifyReduction">Flat damage reduction from fortify buffs.</param>
        /// <param name="weakenReduction">Defense stat reduction from weaken status (0.0-1.0).</param>
        /// <returns>Final damage after all reductions (minimum 1).</returns>
        public static float CalculateEnemyDamageToPlayer(
            float baseDamage,
            float defenseStat,
            float armorBonus,
            float protectionReduction,
            bool shieldBlocking,
            float shieldReduction,
            float fortifyReduction,
            float weakenReduction = 0f)
        {
            // Apply weaken status to defense stat
            // Python: defense_stat *= (1.0 - stat_reduction)
            float effectiveDefense = defenseStat * (1.0f - weakenReduction);

            // DEF multiplier: 1.0 - (defense_stat * 0.02)
            // Python: def_multiplier = 1.0 - (defense_stat * 0.02)
            float defMultiplier = 1.0f - (effectiveDefense * 0.02f);

            // Armor multiplier: 1.0 - (armor_bonus * 0.01)
            // Python: armor_multiplier = 1.0 - (armor_bonus * 0.01)
            float armorMultiplier = 1.0f - (armorBonus * 0.01f);

            // Protection enchantment multiplier
            // Python: protection_multiplier = 1.0 - protection_reduction
            float protectionMultiplier = 1.0f - protectionReduction;

            // Apply multipliers
            // Python: final_damage = damage * def_multiplier * armor_multiplier * protection_multiplier
            float finalDamage = baseDamage * defMultiplier * armorMultiplier * protectionMultiplier;

            // Shield blocking
            // Python: final_damage = final_damage * (1.0 - shield_reduction)
            if (shieldBlocking)
            {
                finalDamage *= (1.0f - shieldReduction);
            }

            // Fortify flat reduction
            // Python: final_damage = max(0, final_damage - fortify_reduction)
            if (fortifyReduction > 0f)
            {
                finalDamage = Math.Max(0f, finalDamage - fortifyReduction);
            }

            // Minimum 1 damage
            // Python: final_damage = max(1, final_damage)
            return Math.Max(1f, finalDamage);
        }

        /// <summary>
        /// Calculate reflected (thorns) damage back to enemy.
        /// Python: reflect_damage = final_damage * reflect_percent
        /// Reflect percentage is capped at 80%.
        /// </summary>
        /// <param name="incomingDamage">Damage the player received.</param>
        /// <param name="totalReflectPercent">Sum of all thorns enchantment values.</param>
        /// <returns>Damage to reflect back, with capped percentage.</returns>
        public static float CalculateReflectDamage(float incomingDamage, float totalReflectPercent)
        {
            float cappedPercent = Math.Min(totalReflectPercent, MaxReflectPercent);
            return incomingDamage * cappedPercent;
        }

        /// <summary>
        /// Calculate lifesteal heal amount.
        /// Python: lifesteal_percent = min(effect.get('value', 0.1), 0.50)
        ///         heal_amount = final_damage * lifesteal_percent
        /// </summary>
        /// <param name="damageDealt">Damage dealt to enemy.</param>
        /// <param name="lifestealPercent">Raw lifesteal percentage from enchantment.</param>
        /// <returns>Amount to heal (lifesteal capped at 50%).</returns>
        public static float CalculateLifestealHeal(float damageDealt, float lifestealPercent)
        {
            float cappedPercent = Math.Min(lifestealPercent, MaxLifestealPercent);
            return damageDealt * cappedPercent;
        }

        /// <summary>
        /// Calculate EXP reward for killing an enemy.
        /// Python: base_exp from config, * boss_multiplier if boss, * 2 if dungeon.
        /// </summary>
        /// <param name="config">Combat configuration with EXP rewards.</param>
        /// <param name="enemyTier">Enemy tier (1-4).</param>
        /// <param name="isBoss">Whether the enemy is a boss.</param>
        /// <param name="inDungeon">Whether the kill occurred in a dungeon (2x EXP).</param>
        /// <returns>Integer EXP reward.</returns>
        public static int CalculateExpReward(CombatConfig config, int enemyTier, bool isBoss, bool inDungeon)
        {
            // Python: base_exp = self.config.exp_rewards.get(tier_key, 100)
            float baseExp = config.GetExpReward(enemyTier);

            // Python: if enemy.is_boss: base_exp *= self.config.boss_multiplier
            if (isBoss)
            {
                baseExp *= config.BossMultiplier;
            }

            // Python: if self.dungeon_manager and self.dungeon_manager.in_dungeon: base_exp *= 2
            if (inDungeon)
            {
                baseExp *= 2f;
            }

            return (int)baseExp;
        }

        /// <summary>
        /// Calculate weapon durability loss per attack.
        /// Python:
        ///   durability_loss = 1 if tool_type_effectiveness >= 1.0 else 2
        ///   durability_loss *= stats.get_durability_loss_multiplier()
        ///   loss *= (1.0 - unbreaking_value)
        /// </summary>
        /// <param name="isProperWeapon">True if using a weapon for combat, false if using a tool.</param>
        /// <param name="durabilityLossMultiplier">DEF stat multiplier for durability loss.</param>
        /// <param name="unbreakingValue">Unbreaking enchantment reduction value (0.0-1.0).</param>
        /// <returns>Durability to subtract (always >= 0).</returns>
        public static float CalculateDurabilityLoss(bool isProperWeapon, float durabilityLossMultiplier, float unbreakingValue)
        {
            // Python: durability_loss = 1 if tool_type_effectiveness >= 1.0 else 2
            float loss = isProperWeapon ? 1.0f : 2.0f;

            // Python: durability_loss *= self.character.stats.get_durability_loss_multiplier()
            loss *= durabilityLossMultiplier;

            // Python: durability_loss *= (1.0 - reduction) [from unbreaking enchantment]
            if (unbreakingValue > 0f)
            {
                loss *= (1.0f - unbreakingValue);
            }

            return Math.Max(0f, loss);
        }
    }
}
