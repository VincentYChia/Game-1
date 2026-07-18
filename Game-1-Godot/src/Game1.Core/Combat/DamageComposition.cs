namespace Game1.Core.Combat;

/// <summary>
/// The action-path damage multiplier order from
/// Combat/combat_manager.py::player_attack_enemy_with_tags (~1608-1692) plus
/// the executor defense seam — the ONLY melee path real players hit.
/// Order: (+ weapon x hand) x STR x titleMelee x enemyTypeTitle x
/// INT-elemental (tag-gated) x crushing (defense &gt; 10) x empower x
/// crit (2.0, applied LAST on the fully-bonused damage) → per-target defense.
/// Pinned by conformance/goldens/damage_composition.json; superseded by
/// crux-foundry scenario parity in Phase 4.
/// </summary>
public readonly record struct DamageInputs(
    double BaseDamage,
    double WeaponDamage,
    double HandMultiplier,
    int Strength,
    double TitleMeleeBonus,
    double EnemyTypeTitleMultiplier,
    int Intelligence,
    bool HasElementalTag,
    double CrushingBonus,
    double EnemyDefense,
    double EmpowerBonus,
    bool IsCrit,
    double ArmorPenetration);

public static class DamageComposition
{
    public static double Compose(in DamageInputs i)
    {
        var damage = i.BaseDamage;

        // combat_manager.py:1630-1634 — hand bonus applies to the weapon component
        var weaponComponent = i.WeaponDamage * i.HandMultiplier;
        if (weaponComponent > 0)
            damage += weaponComponent;

        // :1637-1638 — STR multiplier
        damage *= 1.0 + i.Strength * GameConstants.StrDamagePerPoint;

        // :1641-1642 — title meleeDamage
        damage *= 1.0 + i.TitleMeleeBonus;

        // :1648 — enemy-specific title bonuses (beastDamage, ...)
        damage *= i.EnemyTypeTitleMultiplier;

        // :1653-1659 — INT elemental, only when the attack carries an
        // elemental tag AND the multiplier exceeds 1.0
        if (i.HasElementalTag)
        {
            var intMult = 1.0 + i.Intelligence * GameConstants.IntElementalPerPoint;
            if (intMult > 1.0)
                damage *= intMult;
        }

        // :1662-1663 — crushing bonus vs armored (defense > 10) targets
        if (i.CrushingBonus > 0 && i.EnemyDefense > 10)
            damage *= 1.0 + i.CrushingBonus;

        // :1666-1672 — empower skill buffs
        if (i.EmpowerBonus > 0)
            damage *= 1.0 + i.EmpowerBonus;

        // :1679-1682 — crit LAST, on the fully-bonused damage
        if (i.IsCrit)
            damage *= GameConstants.CritMultiplier;

        // effect_executor.py:162-168 — per-target defense
        return DefenseReduction.Apply(damage, i.EnemyDefense, i.ArmorPenetration);
    }
}
