using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;

namespace Game1.Core.Combat;

/// <summary>
/// Port of combat_manager.py _enemy_attack_player's COMPUTATIONAL core
/// (LOS/visuals/events are engine seams): per-attack damage multiplier from
/// the pending phased attack, DEF multiplier (crux F7: armor effectiveness
/// +3%/DEF pt), Protection enchants, shield blocking (config-capped),
/// fortify flat reduction, min-1 damage, armor durability via the real
/// take_damage, and Thorns reflection (capped 80%) that can kill the enemy.
/// </summary>
public static class EnemyAttackResolver
{
    private static readonly string[] ArmorSlots =
        { "helmet", "chestplate", "leggings", "boots", "gauntlets" };

    /// <summary>Returns the final damage applied to the player.</summary>
    public static double Resolve(EnemyRuntime enemy, PlayerCharacter character,
                                 bool shieldBlocking = false)
    {
        var pending = enemy.AttackPendingData;
        var atkDmgMult = pending is not null
            && pending.TryGetValue("damage_multiplier", out var dm) && dm is double d
            ? d : 1.0;

        var damage = enemy.PerformAttack() * atkDmgMult;

        // DEF multiplier (weaken status seam: player statuses arrive with the
        // status-manager wiring; with none active Python behaves identically)
        double defenseStat = character.Stats.Defense;
        var defMultiplier = 1.0 - defenseStat * 0.02;

        // Armor bonus with DEF armor-effectiveness (+3%/pt, crux F7)
        var armorBonus = (double)character.Equipment.GetTotalDefense();
        armorBonus *= 1.0 + character.Stats.Defense * 0.03;
        var armorMultiplier = 1.0 - armorBonus * 0.01;

        // Protection enchantments
        var protectionReduction = 0.0;
        foreach (var slot in ArmorSlots)
        {
            var armorPiece = character.Equipment.Slots.GetValueOrDefault(slot);
            if (armorPiece is null) continue;
            foreach (var ench in armorPiece.Enchantments)
            {
                var effect = ench["effect"] as JsonObject;
                if (effect?["type"]?.GetValue<string>() == "damage_reduction")
                    protectionReduction += J.AsNum(effect["value"]) ?? 0.0;
            }
        }
        var protectionMultiplier = 1.0 - protectionReduction;

        var finalDamage = damage * defMultiplier * armorMultiplier * protectionMultiplier;

        if (shieldBlocking && character.IsShieldActive())
        {
            var shieldReduction = character.GetShieldDamageReduction();
            finalDamage *= 1.0 - shieldReduction;
        }

        var fortifyReduction = character.Buffs.GetDefenseBonus();
        if (fortifyReduction > 0)
            finalDamage = Math.Max(0, finalDamage - fortifyReduction);

        finalDamage = Math.Max(1, finalDamage);

        character.TakeDamageFull(finalDamage, fromAttack: true);

        // Thorns/reflect (only while the enemy still lives), capped at 80%
        if (enemy.IsAlive)
        {
            var reflectPercent = 0.0;
            foreach (var slot in ArmorSlots)
            {
                var armorPiece = character.Equipment.Slots.GetValueOrDefault(slot);
                if (armorPiece is null) continue;
                foreach (var ench in armorPiece.Enchantments)
                {
                    var effect = ench["effect"] as JsonObject;
                    var enchType = effect?["type"]?.GetValue<string>() ?? "unknown";
                    if (enchType is "reflect" or "thorns" or "reflect_damage")
                        reflectPercent += J.AsNum(effect!["value"]) ?? 0.0;
                }
            }
            reflectPercent = Math.Min(reflectPercent, 0.80);

            if (reflectPercent > 0)
            {
                var reflectDamage = finalDamage * reflectPercent;
                enemy.CurrentHealth -= reflectDamage;
                if (enemy.CurrentHealth <= 0)
                {
                    enemy.IsAlive = false;
                    enemy.CurrentHealth = 0;
                }
            }
        }

        return finalDamage;
    }
}
