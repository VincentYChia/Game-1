using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;
using Game1.Core.Tags;

namespace Game1.Core.Combat;

/// <summary>Port of combat_manager.py CombatConfig — the attack path reads
/// exp_rewards + boss_multiplier; loaded from combat-config.JSON like boot.</summary>
public sealed class CombatConfig
{
    public Dictionary<string, double> ExpRewards = new()
    { ["tier1"] = 100, ["tier2"] = 400, ["tier3"] = 1600, ["tier4"] = 6400 };
    public double BossMultiplier = 10.0;

    public bool LoadFromFile(string path)
    {
        try
        {
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            var expData = data["experienceRewards"] as JsonObject ?? new JsonObject();
            ExpRewards = new Dictionary<string, double>
            {
                ["tier1"] = J.AsNum(expData["tier1"]) ?? 100,
                ["tier2"] = J.AsNum(expData["tier2"]) ?? 400,
                ["tier3"] = J.AsNum(expData["tier3"]) ?? 1600,
                ["tier4"] = J.AsNum(expData["tier4"]) ?? 6400,
            };
            BossMultiplier = J.AsNum(expData["bossMultiplier"]) ?? 10.0;
            return true;
        }
        catch
        {
            return false;
        }
    }
}

public sealed class TagAttackResult
{
    public double TotalDamage;
    public bool IsCrit;
    public List<(string MaterialId, long Quantity)> Loot = new();
}

/// <summary>
/// Port of the COMPUTATIONAL path of combat_manager.py
/// player_attack_enemy_with_tags + _execute_tag_attack_aoe +
/// _player_crit_chance + _apply_weapon_enchantment_effects +
/// _calculate_exp_reward + weapon durability. LOS and visuals are engine
/// seams (the oracle runs Python with skip_visual/skip_los, matching).
///
/// TWO rng streams, exactly like Python: the manager's injected rng draws
/// the crit roll; the GLOBAL random module (globalRng here) is drawn by the
/// effect executor (critical tag, auto-apply status) and Enemy.generate_loot.
/// </summary>
public sealed class TagAttackOrchestrator
{
    // combat_manager.py:17/:24 — env-tunable, defaults pinned by crux
    public const double StrDmgPerPoint = 0.05;
    public const double LckCritPerPoint = 0.12;

    private static readonly string[] DamageTypesForDevastate =
    {
        "physical", "fire", "ice", "lightning", "poison",
        "arcane", "shadow", "holy", "chaos",
    };

    private static readonly string[] ElementalTags =
        { "fire", "ice", "lightning", "poison", "arcane", "shadow", "holy" };

    public PlayerCharacter Character;
    public CombatConfig Config = new();
    public bool DebugInfiniteDurability;

    private readonly EffectExecutor _executor;
    private readonly PythonRandom _managerRng;   // CombatManager._rng (crit)

    /// <summary>The shared effect executor — skill_manager.py routes skill
    /// combat effects through the SAME executor + RNG stream as weapon
    /// attacks; exposing it preserves that stream identity.</summary>
    public EffectExecutor Executor => _executor;

    /// <summary>Ordered active enemies (get_all_active_enemies order).</summary>
    public List<EnemyRuntime> ActiveEnemies = new();

    public TagAttackOrchestrator(PlayerCharacter character, TagRegistry registry,
                                 PythonRandom managerRng, PythonRandom globalRng)
    {
        Character = character;
        _managerRng = managerRng;
        _executor = new EffectExecutor(registry, globalRng.NextDouble);
    }

    private EquipmentItem? EquippedWeapon()
    {
        EquipmentItem? weapon = null;
        if (Character.SelectedSlot is { Length: > 0 } slot)
            weapon = Character.Equipment.Slots.GetValueOrDefault(slot);
        return weapon ?? Character.Equipment.Slots.GetValueOrDefault("mainHand");
    }

    /// <summary>_player_crit_chance (FINDINGS F3) — LCK + pierce buffs +
    /// Precision weapon tag + title criticalChance.</summary>
    public double PlayerCritChance(List<string>? weaponTags = null)
    {
        var chance = LckCritPerPoint * Character.GetEffectiveLuck();

        var pierceBonus = Character.Buffs.GetTotalBonus("pierce", "damage");
        if (pierceBonus == 0)
            pierceBonus = Character.Buffs.GetTotalBonus("pierce", "combat");
        chance += pierceBonus;

        if (weaponTags is { Count: > 0 })
            chance += WeaponTagModifiers.GetCritChanceBonus(weaponTags);

        chance += Character.Titles.GetTotalBonus("criticalChance");
        return chance;
    }

    public long CalculateExpReward(EnemyRuntime enemy)
    {
        var baseExp = Config.ExpRewards.GetValueOrDefault($"tier{enemy.Definition.Tier}", 100);
        if (enemy.IsBoss)
            baseExp *= Config.BossMultiplier;
        return (long)baseExp;   // Python int() truncation
    }

    public TagAttackResult PlayerAttackEnemyWithTags(EnemyRuntime enemy,
                                                     List<string> tags,
                                                     Dictionary<string, object?>? paramsIn)
    {
        // Devastate buffs (Whirlwind Strike): checked BEFORE the normal
        // composition; consumes the buff, then runs the AoE path.
        foreach (var buff in Character.Buffs.ActiveBuffs)
        {
            if (buff.EffectType == "devastate" && buff.Category is "damage" or "combat")
            {
                var aoeTags = tags.Where(t => DamageTypesForDevastate.Contains(t)).ToList();
                aoeTags.Add("circle");

                var aoeParams = paramsIn is null
                    ? new Dictionary<string, object?>()
                    : new Dictionary<string, object?>(paramsIn);
                aoeParams["circle_radius"] = (double)(long)buff.BonusValue;   // int()

                Character.Buffs.ConsumeBuffsForAction("attack");

                return ExecuteTagAttackAoe(enemy, aoeTags, aoeParams);
            }
        }

        var aliveEnemies = ActiveEnemies.Where(e => e.IsAlive)
            .Cast<ICombatEntity>().ToList();

        var effectParams = paramsIn is null
            ? new Dictionary<string, object?>()
            : new Dictionary<string, object?>(paramsIn);
        var isCrit = false;

        List<string> weaponTags = new();
        if (effectParams.ContainsKey("baseDamage"))
        {
            var baseDamage = TagParser.Num(effectParams["baseDamage"]);

            var equippedWeapon = EquippedWeapon();
            weaponTags = equippedWeapon?.Tags ?? new List<string>();

            var armorPenetration = 0.0;
            var handMult = 1.0;
            var crushingBonus = 0.0;
            if (weaponTags.Count > 0)
            {
                var hasOffhand = Character.Equipment.Slots.GetValueOrDefault("offHand") is not null;
                handMult = WeaponTagModifiers.GetDamageMultiplier(weaponTags, hasOffhand);
                armorPenetration = WeaponTagModifiers.GetArmorPenetration(weaponTags);
                crushingBonus = WeaponTagModifiers.GetDamageVsArmoredBonus(weaponTags);
            }

            // Hand-requirement bonus rides the weapon component (2H +20%)
            var weaponDamage = Character.GetWeaponDamage() * handMult;
            if (weaponDamage > 0)
                baseDamage += weaponDamage;

            baseDamage *= 1.0 + Character.Stats.Strength * StrDmgPerPoint;

            baseDamage *= 1.0 + Character.Titles.GetTotalBonus("meleeDamage");

            baseDamage *= Character.GetEnemyDamageMultiplier(enemy.Definition);

            // INT elemental (+5%/pt) when the attack carries an elemental tag
            if (tags.Any(t => ElementalTags.Contains(t)))
            {
                var intMult = 1.0 + Character.Stats.Intelligence * 0.05;
                if (intMult > 1.0)
                    baseDamage *= intMult;
            }

            if (crushingBonus > 0 && enemy.Definition.Defense > 10)
                baseDamage *= 1.0 + crushingBonus;

            var skillBonus = Math.Max(Character.Buffs.GetDamageBonus("damage"),
                                      Character.Buffs.GetDamageBonus("combat"));
            if (skillBonus > 0)
                baseDamage *= 1.0 + skillBonus;

            // Crit LAST, on the fully-bonused damage (F4/F6)
            var critChance = PlayerCritChance(weaponTags);
            if (_managerRng.NextDouble() < critChance)
            {
                isCrit = true;
                baseDamage *= 2.0;
            }

            effectParams["baseDamage"] = baseDamage;
            // F5: enemy defense applies per-target in the executor
            effectParams["_apply_enemy_defense"] = true;
            effectParams["_armor_penetration"] = armorPenetration;
        }

        _executor.ExecuteEffect(Character, enemy, tags, effectParams, aliveEnemies);

        var equippedWeapon2 = EquippedWeapon();

        // Lifesteal ENCHANT heals from final damage before the death check
        var finalDamage = TagParser.Num(effectParams.GetValueOrDefault("baseDamage"));
        if (equippedWeapon2 is not null)
        {
            foreach (var ench in equippedWeapon2.Enchantments)
            {
                var effect = ench["effect"] as JsonObject ?? new JsonObject();
                if ((effect["type"]?.GetValue<string>()) == "lifesteal")
                {
                    var lifestealPercent = Math.Min(J.AsNum(effect["value"]) ?? 0.1, 0.50);
                    var healAmount = finalDamage * lifestealPercent;
                    Character.Health = Math.Min(Character.MaxHealthValue,
                                                Character.Health + healAmount);
                }
            }
        }

        Character.Buffs.ConsumeBuffsForAction("attack");

        if (enemy.IsAlive)
            ApplyWeaponEnchantmentEffects(enemy);

        var result = new TagAttackResult { IsCrit = isCrit };
        var enemyDied = false;
        if (!enemy.IsAlive)
        {
            enemyDied = true;
            result.TotalDamage += finalDamage;
        }

        if (enemyDied)
        {
            var expReward = CalculateExpReward(enemy);
            Character.Leveling.AddExp(expReward);

            // (no dungeon manager wired — loot always drops, as outside dungeons)
            result.Loot = enemy.GenerateLoot();
            foreach (var (materialId, quantity) in result.Loot)
                Character.Inventory.AddItem(materialId, (int)quantity);
        }

        // Weapon durability loss (improper tool use = 2)
        var equippedWeapon3 = EquippedWeapon();
        if (equippedWeapon3 is not null && !DebugInfiniteDurability)
        {
            var toolTypeEffectiveness =
                Character.GetToolEffectivenessForAction(equippedWeapon3, "combat");
            var durabilityLoss = toolTypeEffectiveness >= 1.0 ? 1 : 2;
            equippedWeapon3.DurabilityCurrent =
                Math.Max(0, equippedWeapon3.DurabilityCurrent - durabilityLoss);
        }

        return result;
    }

    /// <summary>_execute_tag_attack_aoe — devastate AoE: weapon damage
    /// WITHOUT the hand multiplier, STR, title melee, empower; NO crit, NO
    /// enemy defense, NO per-enemy titles (documented Python differences).</summary>
    public TagAttackResult ExecuteTagAttackAoe(EnemyRuntime primaryTarget,
                                               List<string> tags,
                                               Dictionary<string, object?> paramsIn)
    {
        var aliveEnemies = ActiveEnemies.Where(e => e.IsAlive)
            .Cast<ICombatEntity>().ToList();

        var effectParams = new Dictionary<string, object?>(paramsIn);

        if (effectParams.ContainsKey("baseDamage"))
        {
            var baseDamage = TagParser.Num(effectParams["baseDamage"]);

            var weaponDamage = Character.GetWeaponDamage();
            if (weaponDamage > 0)
                baseDamage += weaponDamage;

            baseDamage *= 1.0 + Character.Stats.Strength * StrDmgPerPoint;
            baseDamage *= 1.0 + Character.Titles.GetTotalBonus("meleeDamage");

            var skillBonus = Math.Max(Character.Buffs.GetDamageBonus("damage"),
                                      Character.Buffs.GetDamageBonus("combat"));
            if (skillBonus > 0)
                baseDamage *= 1.0 + skillBonus;

            effectParams["baseDamage"] = baseDamage;
        }

        var context = _executor.ExecuteEffect(Character, primaryTarget, tags,
                                              effectParams, aliveEnemies);

        if (primaryTarget.IsAlive)
            ApplyWeaponEnchantmentEffects(primaryTarget);

        var result = new TagAttackResult();
        foreach (var target in context.Targets)
        {
            if (target is EnemyRuntime e && !e.IsAlive)
            {
                result.TotalDamage += TagParser.Num(effectParams.GetValueOrDefault("baseDamage"));

                var expReward = CalculateExpReward(e);
                Character.Leveling.AddExp(expReward);

                var targetLoot = e.GenerateLoot();
                if (targetLoot.Count > 0)
                {
                    foreach (var (materialId, quantity) in targetLoot)
                    {
                        Character.Inventory.AddItem(materialId, (int)quantity);
                        // Python BUG preserved: loot.extend(target_loot)
                        // INSIDE the per-item loop — duplicates the whole
                        // drop list once per item stack
                        result.Loot.AddRange(targetLoot);
                    }
                }
            }
        }

        return result;
    }

    /// <summary>_apply_weapon_enchantment_effects — onHit enchants from BOTH
    /// hands: damage_over_time (element→status map), knockback (via the
    /// executor's knockback), slow.</summary>
    public void ApplyWeaponEnchantmentEffects(EnemyRuntime enemy)
    {
        foreach (var hand in new[] { "mainHand", "offHand" })
        {
            var weapon = Character.Equipment.Slots.GetValueOrDefault(hand);
            if (weapon is null) continue;

            foreach (var enchantment in weapon.Enchantments)
            {
                var effect = enchantment["effect"] as JsonObject ?? new JsonObject();
                var effectType = effect["type"]?.GetValue<string>();

                if (effectType == "damage_over_time")
                {
                    var element = effect["element"]?.GetValue<string>() ?? "physical";
                    var statusTag = element switch
                    {
                        "fire" => "burn",
                        "poison" => "poison",
                        "bleed" => "bleed",
                        _ => "burn",
                    };
                    var statusParams = new Dictionary<string, object?>
                    {
                        ["duration"] = J.AsNum(effect["duration"]) ?? 5.0,
                        ["damage_per_second"] = J.AsNum(effect["damagePerSecond"]) ?? 10.0,
                    };
                    enemy.ApplyStatus(statusTag, statusParams, Character);
                }
                else if (effectType == "knockback")
                {
                    var knockbackParams = new Dictionary<string, object?>
                    {
                        ["knockback_distance"] = J.AsNum(effect["value"]) ?? 2.0,
                    };
                    _executor.ApplyKnockbackDirect(Character, enemy, knockbackParams);
                }
                else if (effectType == "slow")
                {
                    var slowParams = new Dictionary<string, object?>
                    {
                        ["duration"] = J.AsNum(effect["duration"]) ?? 3.0,
                        ["speed_reduction"] = J.AsNum(effect["value"]) ?? 0.3,
                    };
                    enemy.ApplyStatus("slow", slowParams, Character);
                }
            }
        }
    }
}
