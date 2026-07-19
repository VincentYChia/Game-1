using Game1.Core.Combat;
using Game1.Core.Data;
using Game1.Core.World;

namespace Game1.Core.Progression;

/// <summary>
/// Character composition root — the slice of entities/character.py the
/// combat path reads: stats, titles, buffs, equipment, leveling, inventory,
/// health, selected slot, and the combat query methods. Implements
/// ICombatEntity so the effect executor sees the same duck-type surface the
/// Python Character presents (health/max_health fields, NO heal method —
/// executor lifesteal clamps via the health-field branch, matching Python).
/// </summary>
public sealed class PlayerCharacter : ICombatEntity
{
    public CharacterStats Stats;
    public TitleSystem Titles = new();
    public BuffManager Buffs = new();
    public EquipmentManager Equipment = new();
    public LevelingSystem Leveling = new();
    public Inventory Inventory;

    public double Health;
    public double MaxHealthValue;

    /// <summary>Python _selected_slot — defaults to 'mainHand' (character.py
    /// :125), not None; TAB cycling changes it.</summary>
    public string? SelectedSlot = "mainHand";

    private double _x;
    private double _y;

    public PlayerCharacter(CharacterStats stats, Inventory inventory,
                           (double X, double Y) position)
    {
        Stats = stats;
        Inventory = inventory;
        _x = position.X;
        _y = position.Y;
    }

    // ── character.py get_weapon_damage ───────────────────────────────────

    public double GetWeaponDamage()
    {
        // Python: `if selected_item and selected_item.damage:` — damage is a
        // TUPLE with default (0,0); a non-empty tuple is always truthy, so
        // any item in the selected slot takes the enchant-aware branch.
        if (SelectedSlot is not null
            && Equipment.Slots.GetValueOrDefault(SelectedSlot) is { } selectedItem)
        {
            var (min, max) = selectedItem.GetActualDamage();
            return (min + max) / 2.0;
        }

        var damageRange = Equipment.GetWeaponDamage();
        return (damageRange.Min + damageRange.Max) / 2.0;
    }

    // ── character.py get_effective_luck ──────────────────────────────────

    public double GetEffectiveLuck()
    {
        var titleLuckFlat = Titles.GetTotalBonus("luckStat");
        var titleRareDrops = Titles.GetTotalBonus("rareDropRate");
        var titleLegendaryDrops = Titles.GetTotalBonus("legendaryDropRate");

        var skillLuckBonus = Buffs.GetTotalBonus("luck", "general");

        var totalRareBonus = titleRareDrops + titleLegendaryDrops;

        return Stats.GetEffectiveLuck(
            titleBonus: titleLuckFlat,
            skillBonus: skillLuckBonus,
            rareDropBonus: totalRareBonus);
    }

    // ── character.py get_enemy_damage_multiplier ─────────────────────────

    public double GetEnemyDamageMultiplier(EnemyDefinition definition)
    {
        var totalBonus = 0.0;

        if (!string.IsNullOrEmpty(definition.Category))
        {
            var categoryBonus = Titles.GetTotalBonus($"{definition.Category}Damage");
            if (categoryBonus > 0)
                totalBonus += categoryBonus;
        }

        foreach (var tag in definition.Tags)
        {
            var tagBonus = Titles.GetTotalBonus($"{tag}Damage");
            if (tagBonus > 0)
                totalBonus += tagBonus;
        }

        return 1.0 + totalBonus;
    }

    // ── character.py get_tool_effectiveness_for_action ───────────────────

    public double GetToolEffectivenessForAction(EquipmentItem item, string actionType)
    {
        var toolSlot = item.Slot;
        if (toolSlot == "axe")
            return actionType == "forestry" ? 1.0 : 0.25;
        if (toolSlot == "pickaxe")
            return actionType == "mining" ? 1.0 : 0.25;
        if (toolSlot == "fishing_rod")
            return actionType == "fishing" ? 1.0 : 0.25;
        if (toolSlot is "mainHand" or "offHand")
            return actionType == "combat" ? 1.0 : 0.25;
        return 1.0;
    }

    // ── ICombatEntity (executor source / ally target) ────────────────────

    public string Name => "player";
    public string TypeNameLower => "character";
    public string? Category => null;
    public bool IsEnemyLike => false;
    public Position GetPosition() => new(_x, _y, 0.0);

    public void SetPositionXY(double x, double y)
    {
        _x = x;
        _y = y;
    }

    public (double Dx, double Dy)? LastMoveDirection => null;

    public bool HasCurrentHealth => false;
    public double CurrentHealth { get; set; }
    public bool HasMaxHealth => true;
    public double MaxHealth => MaxHealthValue;
    public bool HasIsAlive => false;
    public bool Alive { get; set; } = true;
    public bool HasHealthField => true;

    double ICombatEntity.Health
    {
        get => Health;
        set => Health = value;
    }

    public double DefinitionDefense => 0;

    // Python Character HAS take_damage (with defense pipeline) but the
    // player-attack path never damages the player through the executor;
    // matching Character's hasattr surface: take_damage exists.
    public bool SupportsTakeDamage => true;

    public void TakeDamage(double damage, string damageType,
                           ICombatEntity? source, IReadOnlyList<string> tags)
    {
        // Placeholder seam: the full Character.take_damage defense pipeline
        // is P4's remaining enemy→player port. Not exercised by the
        // player-attack oracle (enemy targets only).
        Health = Math.Max(0, Health - damage);
    }

    public bool SupportsHeal => false;   // Python Character has no heal()
    public void Heal(double amount) { }

    public bool HasStatusManager => false;   // player statuses arrive with enemy→player port
    public void ApplyStatus(string statusTag, Dictionary<string, object?> statusParams,
                            ICombatEntity? source = null) { }

    public bool HasKnockbackFields => false;
    public void SetKnockback(double vx, double vy, double durationRemaining) { }
}
