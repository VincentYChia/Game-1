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
public sealed class PlayerCharacter : ICombatEntity, ICharacterQuery
{
    public CharacterStats Stats;
    public TitleSystem Titles = new();
    public BuffManager Buffs = new();
    public EquipmentManager Equipment = new();
    public LevelingSystem Leveling = new();
    public Inventory Inventory;
    public ActivityTracker Activities = new();

    public double Health;
    public double MaxHealthValue;

    /// <summary>character.py:88 Config.INTERACTION_RANGE default.</summary>
    public double InteractionRange = 3.0;

    /// <summary>character.py:119 — shield/barrier buff absorption pool.</summary>
    public double ShieldAmount;

    /// <summary>Phase status immunity (is_phased attr, set by PhaseEffect).</summary>
    public bool IsPhased;

    /// <summary>class_system.get_bonus seam — 0 with no class selected
    /// (default); the full ClassSystem tag-bonus port arrives with skills.</summary>
    public Func<string, double> ClassBonus = _ => 0.0;

    /// <summary>combat-config.JSON shieldMechanics (min/max damage reduction);
    /// defaults mirror character.py:2509-2510.</summary>
    public double ShieldMinReduction;
    public double ShieldMaxReduction = 0.75;

    /// <summary>hasattr(character, 'stat_tracker') seam — the oracle Python
    /// character deletes its tracker, so conditions resolve unavailable.</summary>
    public Func<string, double?> StatTrackerLookup = _ => null;

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

    // ── character.py take_damage (:1803-1876) — the REAL pipeline ────────
    // Phase immunity → shield absorption → health → armor durability
    // (attacks only) → death reset. Defense/armor REDUCTION happens in the
    // caller (EnemyAttackResolver), matching combat_manager.

    public bool SupportsTakeDamage => true;

    public bool DebugInfiniteDurability;

    public void TakeDamageFull(double damage, bool fromAttack = false)
    {
        if (IsPhased) return;   // fully negated

        if (ShieldAmount > 0)
        {
            var absorbed = Math.Min(damage, ShieldAmount);
            ShieldAmount -= absorbed;
            damage -= absorbed;
        }

        Health -= damage;

        if (fromAttack && damage > 0 && !DebugInfiniteDurability)
        {
            var durabilityLoss = 1.0 * Stats.GetDurabilityLossMultiplier();
            foreach (var slot in new[]
                     { "helmet", "chestplate", "leggings", "boots", "gauntlets" })
            {
                var armorPiece = Equipment.Slots.GetValueOrDefault(slot);
                if (armorPiece is null) continue;
                var pieceLoss = durabilityLoss;
                foreach (var ench in armorPiece.Enchantments)
                {
                    var effect = ench["effect"] as System.Text.Json.Nodes.JsonObject;
                    if (effect?["type"]?.GetValue<string>() == "durability_multiplier")
                        pieceLoss *= 1.0 - (Data.J.AsNum(effect["value"]) ?? 0.0);
                }
                // Python durability is float-decremented then max(0, ...);
                // C# DurabilityCurrent is int — Python keeps fractional loss.
                // Track fractions exactly via the per-item remainder map.
                ApplyFractionalDurabilityLoss(armorPiece, pieceLoss);
            }
        }

        if (Health <= 0)
        {
            Health = 0;
            // _handle_death minimal port: respawn heal (death chest /
            // dungeon exit are engine seams)
            Health = MaxHealthValue;
        }
    }

    /// <summary>Python stores durability as float (1.0 * DEF multiplier can
    /// be fractional); C# EquipmentItem.DurabilityCurrent is int. Exact
    /// fractional tracking so repeated hits match Python's running float.</summary>
    private readonly Dictionary<EquipmentItem, double> _durabilityExact = new();

    public double ExactDurability(EquipmentItem item) =>
        _durabilityExact.TryGetValue(item, out var v) ? v : item.DurabilityCurrent;

    public void ApplyFractionalDurabilityLoss(EquipmentItem item, double loss)
    {
        var current = ExactDurability(item);
        current = Math.Max(0, current - loss);
        _durabilityExact[item] = current;
        item.DurabilityCurrent = (int)current;   // int view floors like print
    }

    /// <summary>equipment.py get_effectiveness computed from the EXACT
    /// (possibly fractional) durability — Python's durability_current is a
    /// float after DEF-scaled losses and the curve reads that float.</summary>
    public double GetEffectivenessExact(EquipmentItem item)
    {
        var current = ExactDurability(item);
        if (current <= 0) return 0.5;
        var durPct = current / item.DurabilityMax;
        return durPct >= 0.5 ? 1.0 : 1.0 - (0.5 - durPct) * 0.5;
    }

    /// <summary>character.py get_effective_max_durability — VIT ×1%/pt +
    /// title durabilityBonus, int-truncated.</summary>
    public int GetEffectiveMaxDurability(EquipmentItem item)
    {
        var vitMult = Stats.GetDurabilityBonusMultiplier();
        var titleMult = 1.0 + Titles.GetTotalBonus("durabilityBonus");
        return (int)(item.DurabilityMax * vitMult * titleMult);
    }

    // ── character.py shield helpers (:2456-2512) ─────────────────────────

    public EquipmentItem? GetEquippedShield()
    {
        var offhand = Equipment.Slots.GetValueOrDefault("offHand");
        if (offhand is { ItemType: "shield" }) return offhand;
        var mainhand = Equipment.Slots.GetValueOrDefault("mainHand");
        if (mainhand is { ItemType: "shield" }) return mainhand;
        return null;
    }

    public bool IsShieldActive() => GetEquippedShield() is not null;

    public double GetShieldDamageReduction()
    {
        var shield = GetEquippedShield();
        if (shield is null) return 0.0;

        var damageMultiplier = shield.StatMultipliers is System.Text.Json.Nodes.JsonObject sm
            ? Data.J.AsNum(sm["damage"]) ?? 1.0 : 1.0;
        var baseReduction = 1.0 - damageMultiplier;
        var defenseMult = 1.0 + (Data.J.AsNum(shield.Bonuses["defense_multiplier"]) ?? 0.0);
        var enhancedReduction = baseReduction * defenseMult;
        return Math.Max(ShieldMinReduction, Math.Min(ShieldMaxReduction, enhancedReduction));
    }

    void ICombatEntity.TakeDamage(double damage, string damageType,
                                  ICombatEntity? source, IReadOnlyList<string> tags)
        => TakeDamageFull(damage, fromAttack: false);

    // ── ICharacterQuery (title/skill-unlock requirement evaluation) ──────

    public int Level => Leveling.Level;

    public int GetStat(string statName) => statName.ToLowerInvariant() switch
    {
        "strength" => Stats.Strength,
        "defense" => Stats.Defense,
        "vitality" => Stats.Vitality,
        "luck" => Stats.Luck,
        "agility" => Stats.Agility,
        "intelligence" => Stats.Intelligence,
        _ => 0,
    };

    public int GetActivityCount(string activityType) => Activities.GetCount(activityType);

    public bool HasTitle(string titleId) => Titles.HasTitle(titleId);

    public bool KnowsSkill(string skillId) => false;   // skills port pending

    public bool IsQuestCompleted(string questId) => false;

    public string? CurrentClassId => null;

    public double? GetStatTrackerValue(string statPath) => StatTrackerLookup(statPath);

    public bool SupportsHeal => false;   // Python Character has no heal()
    public void Heal(double amount) { }

    public bool HasStatusManager => false;   // player statuses arrive with enemy→player port
    public void ApplyStatus(string statusTag, Dictionary<string, object?> statusParams,
                            ICombatEntity? source = null) { }

    public bool HasKnockbackFields => false;
    public void SetKnockback(double vx, double vy, double durationRemaining) { }
}
