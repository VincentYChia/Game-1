using System.Text.Json.Nodes;
using Game1.Core.Combat;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of entities/components/skill_manager.py (+ data/models/skills.py
/// PlayerSkill) — the hotbar-driven active-skill layer. Known skills, 5
/// hotbar slots, cooldowns, mana gating, per-skill leveling (1-10, +10%
/// per level), and the two dispatch paths: legacy BUFF pipeline (ActiveBuff
/// on the character) and tag-based COMBAT pipeline (combatTags/combatParams
/// through the shared EffectExecutor).
///
/// Preserved hazards (contract skills.json): mana + cooldown + 100 skill
/// EXP are spent BEFORE the effect resolves (enemy-target skills with no
/// enemy fizzle after paying); buff path scales (1 + level + affinity)
/// ADDITIVE while combat params scale (1+level)*(1+affinity) MULTIPLICATIVE;
/// 'instant' buffs become 60s consume-on-use; regenerate always
/// consume_on_use=false; DEX requirement maps to agility; restore amounts
/// are hardcoded (do NOT read the magnitude JSON); additionalEffects are
/// parsed but never executed.
/// </summary>
public sealed class PlayerSkill
{
    public int Level { get; set; } = 1;
    public double Exp { get; set; }
    public double CurrentCooldown { get; set; }
    public bool IsEquipped { get; set; }

    public const int MaxLevel = 10;

    // skills.py:96-130 — 1000 * 2^(level-1), overflow carries, multi-level
    public bool AddExp(double amount)
    {
        Exp += amount;
        var leveled = false;
        while (Level < MaxLevel && Exp >= ExpToNext(Level))
        {
            Exp -= ExpToNext(Level);
            Level++;
            leveled = true;
        }
        return leveled;
    }

    public static double ExpToNext(int level) => 1000.0 * Math.Pow(2, level - 1);

    /// <summary>+0% at L1 … +90% at L10 (skills.py:128-130).</summary>
    public double LevelBonus => 0.1 * (Level - 1);
}

/// <summary>Translation tables (Definitions.JSON/skills-translation-table
/// .JSON) + magnitude tables (Skills/skills-base-effects-1.JSON), with the
/// Python fallback constants when files are missing.</summary>
public sealed class SkillTranslation
{
    private readonly Dictionary<string, double> _mana = new()
    { ["low"] = 30, ["moderate"] = 60, ["high"] = 100, ["extreme"] = 150 };
    private readonly Dictionary<string, double> _cooldown = new()
    { ["short"] = 120, ["moderate"] = 300, ["long"] = 600, ["extreme"] = 1200 };
    private readonly Dictionary<string, double> _duration = new()
    { ["instant"] = 0, ["brief"] = 15, ["moderate"] = 30, ["long"] = 60, ["extended"] = 120 };
    // effect type -> magnitude tier -> value
    private readonly Dictionary<string, Dictionary<string, double>> _magnitudes = new();

    public static SkillTranslation Load(string contentRoot)
    {
        var t = new SkillTranslation();
        try
        {
            var p = Path.Combine(contentRoot, "Definitions.JSON",
                                 "skills-translation-table.JSON");
            if (File.Exists(p) && JsonNode.Parse(File.ReadAllText(p)) is JsonObject o)
            {
                FillTable(o["manaCostTranslations"], t._mana);
                FillTable(o["cooldownTranslations"], t._cooldown);
                FillTable(o["durationTranslations"], t._duration);
            }
        }
        catch { /* fallback constants stand */ }
        try
        {
            var p = Path.Combine(contentRoot, "Skills", "skills-base-effects-1.JSON");
            if (File.Exists(p) && JsonNode.Parse(File.ReadAllText(p)) is JsonObject o
                && o["BASE_EFFECT_TYPES"] is JsonObject types)
            {
                foreach (var (effect, node) in types)
                {
                    if (node is not JsonObject eo
                        || eo["magnitudeValues"] is not JsonObject mv) continue;
                    var table = new Dictionary<string, double>();
                    FillTable(mv, table);
                    t._magnitudes[effect] = table;
                }
            }
        }
        catch { }
        return t;
    }

    private static void FillTable(JsonNode? node, Dictionary<string, double> into)
    {
        if (node is not JsonObject o) return;
        foreach (var (k, v) in o)
            if (v is JsonValue jv)
            {
                if (jv.TryGetValue<double>(out var d)) into[k] = d;
                else if (jv.TryGetValue<int>(out var i)) into[k] = i;
            }
    }

    // skill_db.py:206-222 — numeric passthrough; unknown-string defaults
    public double ManaCost(JsonNode? cost) => Resolve(cost, _mana, 60);
    public double CooldownSeconds(JsonNode? cost) => Resolve(cost, _cooldown, 300);
    public double DurationSeconds(string key) =>
        _duration.GetValueOrDefault(key, 0);

    /// <summary>Magnitude default 0.5 when missing (skill_manager.py:334).</summary>
    public double Magnitude(string effectType, string magnitude) =>
        _magnitudes.TryGetValue(effectType, out var table)
            ? table.GetValueOrDefault(magnitude, 0.5) : 0.5;

    private static double Resolve(JsonNode? cost,
        Dictionary<string, double> table, double stringDefault)
    {
        if (cost is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return d;
            if (v.TryGetValue<int>(out var i)) return i;
            if (v.TryGetValue<string>(out var s))
                return table.GetValueOrDefault(s, stringDefault);
        }
        return stringDefault;
    }
}

public sealed class SkillManager
{
    public const int HotbarSlots = 5;
    public const double ExpPerUse = 100;

    private readonly PlayerCharacter _ch;
    private readonly SkillDatabase _db;
    private readonly SkillTranslation _tr;

    public Dictionary<string, PlayerSkill> Known { get; } = new();
    public string?[] Equipped { get; } = new string?[HotbarSlots];

    /// <summary>Class tags for the affinity bonus (empty until a class is
    /// chosen; 5% per case-insensitive match, cap 20% — classes.py:33-46).</summary>
    public List<string> ClassTags { get; set; } = new();

    /// <summary>Instant devastate (damage/combat) AoE — wired by the engine
    /// glue to hit all enemies within the radius. Returns hit count.</summary>
    public Func<double, int>? InstantAoe { get; set; }

    /// <summary>Combat-path executor handoff (null = combat skills fizzle
    /// with the Python no-executor behavior).</summary>
    public EffectExecutor? Executor { get; set; }
    public Func<List<ICombatEntity>>? LiveEnemies { get; set; }

    /// <summary>Kill handler for combat-path kills (EXP + loot) — glue-owned
    /// like skill_manager.py:1023-1049.</summary>
    public Action<ICombatEntity>? OnSkillKill { get; set; }

    public SkillManager(PlayerCharacter ch, SkillDatabase db, SkillTranslation tr)
    {
        _ch = ch;
        _db = db;
        _tr = tr;
    }

    // ---- learn / equip (skill_manager.py:48-182) ----

    public (bool Ok, string Reason) CanLearn(string skillId)
    {
        if (Known.ContainsKey(skillId)) return (false, "Already known");
        var def = _db.Skills.GetValueOrDefault(skillId);
        if (def is null) return (false, "Unknown skill");
        if (_ch.Leveling.Level < def.RequiredCharacterLevel)
            return (false, $"Requires level {(int)def.RequiredCharacterLevel}");
        if (def.RequiredStats is JsonObject stats)
        {
            foreach (var (key, v) in stats)
            {
                var need = v is JsonValue jv && jv.TryGetValue<double>(out var d) ? d : 0;
                var have = key.ToUpperInvariant() switch
                {
                    "STR" => _ch.Stats.Strength,
                    "DEF" => _ch.Stats.Defense,
                    "VIT" => _ch.Stats.Vitality,
                    "LCK" => _ch.Stats.Luck,
                    "AGI" => _ch.Stats.Agility,
                    "INT" => _ch.Stats.Intelligence,
                    "DEX" => _ch.Stats.Agility,   // DEX maps to agility
                    _ => 0,
                };
                if (have < need) return (false, $"Requires {key} {(int)need}");
            }
        }
        if (def.RequiredTitles is JsonArray titles)
            foreach (var t in titles)
            {
                var id = t?.GetValue<string>() ?? "";
                if (id.Length > 0 && _ch.Titles.EarnedTitles.All(e => e.TitleId != id))
                    return (false, $"Requires title {id}");
            }
        return (true, "OK");
    }

    public bool Learn(string skillId, bool skipChecks = false)
    {
        if (!skipChecks && !CanLearn(skillId).Ok) return false;
        if (Known.ContainsKey(skillId)) return false;
        Known[skillId] = new PlayerSkill();
        return true;
    }

    public bool Equip(string skillId, int slot)
    {
        if (slot is < 0 or >= HotbarSlots || !Known.TryGetValue(skillId, out var ps))
            return false;
        Equipped[slot] = skillId;
        ps.IsEquipped = true;
        return true;
    }

    public bool EquipFirstEmpty(string skillId)
    {
        for (var i = 0; i < HotbarSlots; i++)
            if (Equipped[i] is null)
                return Equip(skillId, i);
        return false;
    }

    public void Unequip(int slot)
    {
        if (slot is < 0 or >= HotbarSlots) return;
        if (Equipped[slot] is { } id && Known.TryGetValue(id, out var ps))
            ps.IsEquipped = false;
        Equipped[slot] = null;
    }

    public void UpdateCooldowns(double dt)
    {
        foreach (var ps in Known.Values)
            ps.CurrentCooldown = Math.Max(0, ps.CurrentCooldown - dt);
    }

    // ---- costs (re-resolved each read, string-or-number) ----

    public double ManaCostOf(SkillDefinition def) => _tr.ManaCost(def.CostMana);
    public double CooldownOf(SkillDefinition def) => _tr.CooldownSeconds(def.CostCooldown);

    // ---- activation (skill_manager.py:190-262) ----

    public (bool Ok, string Message) UseSkill(int slot,
        (double X, double Y)? mouseWorldPos = null)
    {
        if (slot is < 0 or >= HotbarSlots) return (false, "Invalid slot");
        var skillId = Equipped[slot];
        if (skillId is null) return (false, "No skill in slot");
        if (!Known.TryGetValue(skillId, out var ps)) return (false, "Not learned");
        var def = _db.Skills.GetValueOrDefault(skillId);
        if (def is null) return (false, "No skill definition");
        if (ps.CurrentCooldown > 0)
            return (false, $"On cooldown ({ps.CurrentCooldown:F1}s)");
        var manaCost = ManaCostOf(def);
        if (_ch.Mana < manaCost)
            return (false, $"Not enough mana ({(int)manaCost} required)");

        // Cost THEN effect — enemy-target skills may still fizzle after this
        _ch.Mana -= manaCost;
        ps.CurrentCooldown = CooldownOf(def);

        var message = ApplyEffect(def, ps, mouseWorldPos);

        if (ps.AddExp(ExpPerUse))
            message += $"  (skill level {ps.Level}!)";
        return (true, message);
    }

    private double AffinityBonus(SkillDefinition def, bool combatPath)
    {
        if (ClassTags.Count == 0) return 0;
        List<string> skillTags;
        if (combatPath && def.CombatTags is JsonArray ct && ct.Count > 0)
            skillTags = ct.Select(t => t?.GetValue<string>() ?? "").ToList();
        else
            skillTags = new List<string> { def.EffectCategory };
        var matches = skillTags.Count(t =>
            ClassTags.Any(c => string.Equals(c, t, StringComparison.OrdinalIgnoreCase)));
        return Math.Min(0.20, 0.05 * matches);
    }

    private string ApplyEffect(SkillDefinition def, PlayerSkill ps,
                               (double X, double Y)? mouse)
    {
        if (def.CombatTags is JsonArray combatTags && combatTags.Count > 0)
            return ApplyCombatSkill(def, ps, combatTags, mouse);
        return ApplyBuffSkill(def, ps);
    }

    // ---- buff path (skill_manager.py:304-736) ----

    private string ApplyBuffSkill(SkillDefinition def, PlayerSkill ps)
    {
        var levelBonus = ps.LevelBonus;
        var affinity = AffinityBonus(def, combatPath: false);
        var effectType = def.EffectType;
        var category = def.EffectCategory;

        // restore is instant, no buff (skill_manager.py:426-449) —
        // amounts HARDCODED per contract, not the magnitude JSON
        if (effectType == "restore")
        {
            if (category == "durability")
            {
                var pct = def.EffectMagnitude switch
                {
                    "minor" => 0.15, "moderate" => 0.30,
                    "major" => 0.50, "extreme" => 0.75, _ => 0.30,
                } * (1 + levelBonus);
                foreach (var item in _ch.Equipment.Slots.Values)
                    if (item is not null)
                        item.Repair((int)(item.DurabilityMax * pct));
                return $"{def.Name}: repaired equipment {pct:P0}";
            }
            var amount = def.EffectMagnitude switch
            {
                "minor" => 50.0, "moderate" => 100.0,
                "major" => 200.0, "extreme" => 400.0, _ => 100.0,
            };
            if (category == "mana")
            {
                _ch.Mana = Math.Min(_ch.MaxMana, _ch.Mana + amount);
                return $"{def.Name}: +{amount:F0} mana";
            }
            _ch.Health = Math.Min(_ch.MaxHealthValue, _ch.Health + amount);
            return $"{def.Name}: +{amount:F0} health";
        }

        var durationKey = def.EffectDuration;
        var duration = _tr.DurationSeconds(durationKey);
        var consumeOnUse = false;
        if (duration <= 0) { duration = 60.0; consumeOnUse = true; }   // instant idiom
        else duration *= 1 + levelBonus;

        // additive scaling — do NOT unify with the combat path
        var value = _tr.Magnitude(effectType, def.EffectMagnitude)
                    * (1 + levelBonus + affinity);

        switch (effectType)
        {
            case "fortify": category = "defense"; break;
            case "enrich": value = (int)value; break;
            case "transcend": value = (int)value; break;
            case "regenerate":
                consumeOnUse = false;   // always over-time
                if (durationKey == "instant") duration = 60.0;
                break;
            case "devastate":
            {
                var radius = (int)(_tr.Magnitude(effectType, def.EffectMagnitude)
                                   * (1 + levelBonus + affinity));
                if (durationKey == "instant"
                    && category is "damage" or "combat" && InstantAoe is not null)
                {
                    var hits = InstantAoe(radius);
                    return $"{def.Name}: hit {hits} enemies (radius {radius})";
                }
                value = radius;
                break;
            }
        }

        _ch.Buffs.AddBuff(new ActiveBuff
        {
            BuffId = $"{def.SkillId}_{effectType}",
            Name = def.Name,
            EffectType = effectType,
            Category = category,
            Magnitude = def.EffectMagnitude,
            BonusValue = value,
            Duration = duration,
            DurationRemaining = duration,
            ConsumeOnUse = consumeOnUse,
        });
        return $"{def.Name} active!";
    }

    // ---- combat path (skill_manager.py:929-1016) ----

    private string ApplyCombatSkill(SkillDefinition def, PlayerSkill ps,
                                    JsonArray combatTags,
                                    (double X, double Y)? mouse)
    {
        if (Executor is null) return $"{def.Name}: no effect executor";
        var tags = combatTags.Select(t => t?.GetValue<string>() ?? "")
                             .Where(t => t.Length > 0).ToList();

        // multiplicative scaling: *(1+level) then *(1+affinity)
        var levelBonus = ps.LevelBonus;
        var affinity = AffinityBonus(def, combatPath: true);
        var params_ = new Dictionary<string, object?>();
        if (def.CombatParams is JsonObject po)
            foreach (var (k, v) in po)
            {
                object? val = v is JsonValue jv && jv.TryGetValue<double>(out var d)
                    ? d : v?.ToString();
                if (val is double dd && k is "baseDamage" or "baseHealing")
                    val = dd * (1 + levelBonus) * (1 + affinity);
                params_[k] = val;
            }

        var enemies = LiveEnemies?.Invoke() ?? new List<ICombatEntity>();
        var directional = tags.Any(t => t is "beam" or "cone" or "line")
                          && mouse is not null;

        object? primary;
        List<ICombatEntity> entities;
        if (directional)
        {
            primary = (mouse!.Value.X, mouse.Value.Y);
            entities = enemies;
        }
        else
        {
            switch (def.EffectTarget)
            {
                case "enemy":
                case "area":
                    if (enemies.Count == 0)
                        return $"{def.Name}: no target in range";   // paid fizzle
                    primary = enemies[0];   // FIRST, not nearest (parity)
                    entities = enemies;
                    break;
                case "self":
                default:
                    primary = _ch;
                    entities = new List<ICombatEntity> { _ch };
                    break;
            }
        }

        var context = Executor.ExecuteEffect(_ch, primary, tags, params_, entities);
        var kills = 0;
        foreach (var target in context.Targets)
            if (target is EnemyRuntime { IsAlive: false } dead)
            {
                kills++;
                OnSkillKill?.Invoke(dead);
            }
        return kills > 0 ? $"{def.Name}! {kills} killed by skill!" : $"{def.Name}!";
    }
}
