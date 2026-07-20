using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.World;

namespace Game1.Core.Progression;

/// <summary>
/// Port of the character.py gathering path: can_harvest_resource,
/// get_equipped_tool, _single_node_harvest (tool damage composition, crit,
/// DEF-scaled fractional durability, LCK loot processing, Fortune/enrich),
/// _execute_aoe_gathering (devastate Chain Harvest), harvest_resource
/// (activity/title/EXP bookkeeping incl. the check_for_title acquisition
/// rolls). RNG = the global-random stream (injected PythonRandom).
/// </summary>
public sealed class GatheringSystem
{
    private readonly PlayerCharacter _ch;
    private readonly TitleDatabase _titleDb;
    private readonly PythonRandom _rng;   // global random module stream

    public GatheringSystem(PlayerCharacter character, TitleDatabase titleDb,
                           PythonRandom rng)
    {
        _ch = character;
        _titleDb = titleDb;
        _rng = rng;
    }

    private static readonly Dictionary<string, string> ActivityMap = new()
    {
        ["pickaxe"] = "mining", ["axe"] = "forestry", ["fishing_rod"] = "fishing",
    };

    private static readonly Dictionary<int, long> GatherExp = new()
    { [1] = 10, [2] = 40, [3] = 160, [4] = 640 };

    // character.py get_equipped_tool — selected slot first, tool slot,
    // (dead fishing-rod subtype branch: Python EquipmentItem has no
    // subtype attr, hasattr is always False), mainHand fallback
    public EquipmentItem? GetEquippedTool(string toolType)
    {
        if (_ch.SelectedSlot is { Length: > 0 } slot
            && _ch.Equipment.Slots.GetValueOrDefault(slot) is { } selectedItem)
            return selectedItem;

        if (toolType is "axe" or "pickaxe" or "fishing_rod"
            && _ch.Equipment.Slots.GetValueOrDefault(toolType) is { } equippedTool)
            return equippedTool;

        return _ch.Equipment.Slots.GetValueOrDefault("mainHand");
    }

    // character.py can_harvest_resource
    public (bool Ok, string Reason) CanHarvestResource(NaturalResourceRuntime resource)
    {
        var equippedTool = GetEquippedTool(resource.RequiredTool);
        if (equippedTool is null)
        {
            var toolName = resource.RequiredTool switch
            {
                "axe" => "axe", "pickaxe" => "pickaxe",
                "fishing_rod" => "fishing rod", _ => resource.RequiredTool,
            };
            return (false, $"No {toolName} equipped");
        }
        if (_ch.GetPosition().DistanceTo(resource.Position) > _ch.InteractionRange)
            return (false, "Too far away");
        if (equippedTool.Tier < resource.Tier)
            return (false, $"Tool tier too low (need T{resource.Tier})");
        if (_ch.ExactDurability(equippedTool) <= 0)   // debug-infinite is engine seam
            return (false, "Tool broken");
        return (true, "OK");
    }

    /// <summary>_single_node_harvest — returns (loot, damage, crit) on
    /// depletion, else null.</summary>
    public (List<(string ItemId, long Qty)> Loot, double Damage, bool Crit)?
        SingleNodeHarvest(NaturalResourceRuntime resource, EquipmentItem tool,
                          string activity)
    {
        // tuple damage average with // 2 floor (both components non-negative)
        var baseDamage = (tool.Damage.Min + tool.Damage.Max) / 2;

        var durabilityEffectiveness = _ch.GetEffectivenessExact(tool);
        var toolTypeEffectiveness = _ch.GetToolEffectivenessForAction(tool, activity);
        var totalEffectiveness = durabilityEffectiveness * toolTypeEffectiveness;

        var statBonus = _ch.Stats.GetBonus(activity == "mining" ? "strength" : "agility");
        var titleBonus = _ch.Titles.GetTotalBonus($"{activity}_damage");
        var buffBonus = _ch.Buffs.GetDamageBonus(activity);
        var damageMult = 1.0 + statBonus + titleBonus + buffBonus;

        // Efficiency enchant (first match only) + title speed
        var enchantmentSpeedBonus = 0.0;
        foreach (var ench in tool.Enchantments)
        {
            var effect = ench["effect"] as JsonObject;
            if (effect?["type"]?.GetValue<string>() == "gathering_speed_multiplier")
            {
                enchantmentSpeedBonus = J.AsNum(effect["value"]) ?? 0.0;
                break;
            }
        }
        var titleSpeedBonus = _ch.Titles.GetTotalBonus($"{activity}Speed");
        var efficiencyMult = 1.0 + enchantmentSpeedBonus + titleSpeedBonus;

        // Crit: LCK 0.02/pt + class + pierce-per-activity buffs
        var effectiveLuck = _ch.GetEffectiveLuck();
        var critChance = effectiveLuck * 0.02 + _ch.ClassBonus("crit_chance");
        critChance += _ch.Buffs.GetTotalBonus("pierce", activity);

        var isCrit = _rng.NextDouble() < critChance;
        var damage = (int)(baseDamage * totalEffectiveness * damageMult * efficiencyMult);
        var (actualDamage, depleted) = resource.TakeDamage(damage, isCrit);

        // DEF-scaled fractional durability + Unbreaking
        var baseDurabilityLoss = toolTypeEffectiveness >= 1.0 ? 1.0 : 2.0;
        var durabilityLoss = baseDurabilityLoss * _ch.Stats.GetDurabilityLossMultiplier();
        foreach (var ench in tool.Enchantments)
        {
            var effect = ench["effect"] as JsonObject;
            if (effect?["type"]?.GetValue<string>() == "durability_multiplier")
                durabilityLoss *= 1.0 - (J.AsNum(effect["value"]) ?? 0.0);
        }
        _ch.ApplyFractionalDurabilityLoss(tool, durabilityLoss);

        if (!depleted)
            return null;

        var loot = resource.GetLoot(_rng);
        var processedLoot = new List<(string, long)>();
        foreach (var (itemId, qtyIn) in loot)
        {
            // LCK multiplicative (BASE luck stat), int truncation
            var qty = (long)(qtyIn * (1.0 + _ch.Stats.Luck * 0.02));

            // effective-luck bonus roll (re-derived per item, like Python)
            var luckChance = _ch.GetEffectiveLuck() * 0.02
                             + _ch.ClassBonus("resource_quality");
            if (_rng.NextDouble() < luckChance)
                qty += 1;

            var enrichBonus = (long)_ch.Buffs.GetTotalBonus("enrich", activity);
            if (enrichBonus > 0)
                qty += enrichBonus;

            // Fortune — one proc max per item
            foreach (var ench in tool.Enchantments)
            {
                var effect = ench["effect"] as JsonObject;
                if (effect?["type"]?.GetValue<string>() == "bonus_yield_chance")
                {
                    var bonusChance = J.AsNum(effect["value"]) ?? 0.0;
                    if (_rng.NextDouble() < bonusChance)
                        qty += 1;
                    break;
                }
            }

            processedLoot.Add((itemId, qty));
            _ch.Inventory.AddItem(itemId, (int)qty);
        }

        return (processedLoot, actualDamage, isCrit);
    }

    // _execute_aoe_gathering — Chain Harvest devastate
    public (List<(string ItemId, long Qty)> Loot, double Damage, bool Crit)?
        ExecuteAoeGathering(NaturalResourceRuntime primary, int radius,
                            List<NaturalResourceRuntime> allResources,
                            EquipmentItem tool)
    {
        var activity = ActivityMap.GetValueOrDefault(primary.RequiredTool, "forestry");

        var targets = new List<NaturalResourceRuntime>();
        foreach (var res in allResources)
        {
            if (res.RequiredTool == primary.RequiredTool && !res.Depleted)
            {
                var dx = res.Position.X - _ch.GetPosition().X;
                var dy = res.Position.Y - _ch.GetPosition().Y;
                if (Math.Sqrt(dx * dx + dy * dy) <= radius)
                    targets.Add(res);
            }
        }
        if (targets.Count == 0)
            targets.Add(primary);

        _ch.Buffs.ConsumeBuffsForAction("gather", category: activity);

        var totalLoot = new List<(string, long)>();
        var totalDamage = 0.0;
        var anyCrit = false;
        foreach (var resource in targets)
        {
            var result = SingleNodeHarvest(resource, tool, activity);
            if (result is { } r)
            {
                totalLoot.AddRange(r.Loot);
                totalDamage += r.Damage;
                anyCrit = anyCrit || r.Crit;
            }
        }

        return totalLoot.Count > 0 ? (totalLoot, totalDamage, anyCrit) : null;
    }

    /// <summary>title_system.py check_for_title — insertion-order scan,
    /// requirement evaluation via ICharacterQuery, acquisition rolls on the
    /// global stream. Returns the awarded title or null.</summary>
    public TitleDefinition? CheckForTitle()
    {
        foreach (var titleId in _titleDb.TitleOrder)
        {
            var titleDef = _titleDb.Titles[titleId];
            if (_ch.Titles.EarnedTitles.Any(t => t.TitleId == titleId))
                continue;

            var requirements =
                ConditionFactory.CreateRequirementsFromJson(titleDef.RequirementsRaw);
            if (!requirements.Evaluate(_ch))
                continue;

            var generationChance = J.AsNum(titleDef.GenerationChance) ?? 1.0;
            switch (titleDef.AcquisitionMethod)
            {
                case "guaranteed_milestone":
                case "hidden_discovery":
                    return Award(titleDef);
                case "event_based_rng":
                case "special_achievement":
                    if (_rng.NextDouble() < generationChance)
                        return Award(titleDef);
                    break;
                case "random_drop":
                    var chance = titleDef.Tier switch
                    {
                        "novice" => 1.0, "apprentice" => 0.20, "journeyman" => 0.10,
                        "expert" => 0.05, "master" => 0.02, _ => 0.10,
                    };
                    if (_rng.NextDouble() < chance)
                        return Award(titleDef);
                    break;
            }
        }
        return null;
    }

    private TitleDefinition Award(TitleDefinition titleDef)
    {
        _ch.Titles.EarnedTitles.Add(titleDef);
        return titleDef;
    }

    /// <summary>harvest_resource — the public entry.</summary>
    public (List<(string ItemId, long Qty)> Loot, double Damage, bool Crit)?
        HarvestResource(NaturalResourceRuntime resource,
                        List<NaturalResourceRuntime>? nearbyResources = null)
    {
        var (canHarvest, _) = CanHarvestResource(resource);
        if (!canHarvest) return null;

        var equippedTool = GetEquippedTool(resource.RequiredTool);
        if (equippedTool is null) return null;

        // Devastate (Chain Harvest) branch
        if (nearbyResources is { Count: > 0 })
        {
            var activityForBuff = ActivityMap.GetValueOrDefault(
                resource.RequiredTool, "forestry");
            foreach (var buff in _ch.Buffs.ActiveBuffs)
            {
                if (buff.EffectType == "devastate"
                    && (buff.Category == activityForBuff || buff.Category == "gathering"))
                {
                    var result0 = ExecuteAoeGathering(resource, (int)buff.BonusValue,
                                                      nearbyResources, equippedTool);
                    _ch.Activities.RecordActivity(activityForBuff, 1);
                    CheckForTitle();   // skill-unlock notify = engine seam
                    _ch.Leveling.AddExp(GatherExp.GetValueOrDefault(resource.Tier, 10));
                    return result0;
                }
            }
        }

        var activity = ActivityMap.GetValueOrDefault(resource.RequiredTool, "forestry");
        var result = SingleNodeHarvest(resource, equippedTool, activity);

        _ch.Activities.RecordActivity(activity, 1);
        CheckForTitle();
        _ch.Leveling.AddExp(GatherExp.GetValueOrDefault(resource.Tier, 10));

        return result;
    }
}
