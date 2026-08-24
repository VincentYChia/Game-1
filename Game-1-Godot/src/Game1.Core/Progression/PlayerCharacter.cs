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

    /// <summary>Mana pool (character.py:114,722-731): base 100 + INT*20
    /// (stats-calculations.JSON maxManaPerPoint) + class + equipment
    /// max_mana bonuses. Regen = 1% of max per second (character.py:1454).</summary>
    public double Mana = 100;
    public double BaseMaxMana = 100;
    public const double ManaPerIntPoint = 20.0;
    public double MaxMana =>
        BaseMaxMana + Stats.Intelligence * ManaPerIntPoint
        + ClassBonus("max_mana")
        + Equipment.GetStatBonuses().GetValueOrDefault("max_mana", 0);

    /// <summary>character.py:733-741 allocate_stat_point + :703-731
    /// recalculate_stats. Permanent (no respec). Max HP = 100 + VIT*15 +
    /// class + equipment; HP/mana rescale proportionally with int()
    /// truncation (allocating while damaged does not heal for free).</summary>
    public bool AllocateStatPoint(string statName)
    {
        if (Leveling.UnallocatedStatPoints <= 0) return false;
        var oldMaxHp = MaxHealthValue;
        var oldHp = Health;
        var oldMaxMana = MaxMana;
        var oldMana = Mana;
        switch (statName.ToLowerInvariant())
        {
            case "strength": Stats.Strength++; break;
            case "defense": Stats.Defense++; break;
            case "vitality": Stats.Vitality++; break;
            case "luck": Stats.Luck++; break;
            case "agility": Stats.Agility++; break;
            case "intelligence": Stats.Intelligence++; break;
            default: return false;
        }
        Leveling.UnallocatedStatPoints--;

        MaxHealthValue = 100 + Stats.Vitality * 15
            + ClassBonus("max_health")
            + Equipment.GetStatBonuses().GetValueOrDefault("max_health", 0);
        if (oldMaxHp > 0)
            Health = Math.Min(MaxHealthValue, (int)(MaxHealthValue * oldHp / oldMaxHp));
        if (oldMaxMana > 0)
            Mana = Math.Min(MaxMana, (int)(MaxMana * oldMana / oldMaxMana));
        return true;
    }

    /// <summary>Per-frame regen + buff ticks: mana 1%/s; buff durations;
    /// regenerate-buff HoT side effects (health/mana per second).</summary>
    public void TickManaAndBuffs(double dt)
    {
        Mana = Math.Min(MaxMana, Mana + MaxMana * 0.01 * dt);
        foreach (var b in Buffs.ActiveBuffs)
        {
            if (b.EffectType != "regenerate") continue;
            if (b.Category == "mana")
                Mana = Math.Min(MaxMana, Mana + b.BonusValue * dt);
            else if (b.Category is "health" or "defense")
                Health = Math.Min(MaxHealthValue, Health + b.BonusValue * dt);
        }
        Buffs.Update(dt);
    }

    /// <summary>core/config.py:184 Config.INTERACTION_RANGE (verifier fix:
    /// was wrongly 3.0).</summary>
    public double InteractionRange = 3.5;

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

    /// <summary>Regen gates (character.py:154-157): harvesting/attacking
    /// reset dealt; being hit resets taken. Consumed by the VIT regen tick
    /// when the character update loop is ported.</summary>
    public double TimeSinceLastDamageTaken;
    public double TimeSinceLastDamageDealt;
    public bool PlayerInCombat;

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
                armorPiece.DurabilityCurrent =
                    Math.Max(0, armorPiece.DurabilityCurrent - pieceLoss);
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

    // (Fractional durability lives directly on EquipmentItem.DurabilityCurrent
    // — a double matching Python's float field — after the verifier found the
    // per-character exactness map desynced against Repair/combat writers.)

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
