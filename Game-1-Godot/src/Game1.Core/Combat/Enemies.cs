using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/enemy.py (EnemyDatabase + definitions) and
/// Combat/attack_profile_generator.py (deterministic per-enemy attack
/// profiles derived from category/tier/behavior/stats/tags — zero JSON
/// changes). Loot uses the injected Python-exact RNG so seeded streams
/// reproduce. Pinned by conformance/goldens/db_parity/enemies.json.
/// </summary>
public sealed record DropDefinition(
    string MaterialId, long QuantityMin, long QuantityMax, double Chance);

public sealed record SpecialAbility(
    string AbilityId, string Name, double Cooldown, List<string> Tags,
    JsonObject Params, double HealthThreshold, double DistanceMin,
    double DistanceMax, long EnemyCount, long AllyCount, bool OncePerFight,
    long MaxUsesPerFight, long Priority);

public sealed record AiPattern(
    string DefaultState, bool AggroOnDamage, bool AggroOnProximity,
    double FleeAtHealth, double CallForHelpRadius, bool PackCoordination,
    List<string> SpecialAbilities);

public sealed class EnemyAttackDef
{
    public required string AttackId { get; set; }
    public required string Shape { get; init; }
    public double Arc { get; init; } = 80.0;
    public double Range { get; init; } = 1.5;
    public double Windup { get; init; } = 500.0;
    public double Active { get; init; } = 200.0;
    public double Recovery { get; init; } = 350.0;
    public long Weight { get; init; } = 1;
    public List<string> Tags { get; init; } = new() { "physical" };
    public bool ScreenShake { get; init; }
    public double DamageMultiplier { get; init; } = 1.0;
    public List<string> StatusTags { get; init; } = new();
}

public sealed class EnemyDefinition
{
    public required string EnemyId { get; init; }
    public required string Name { get; init; }
    public required long Tier { get; init; }
    public required string Category { get; init; }
    public required string Behavior { get; init; }
    public double MaxHealth { get; init; }
    public double DamageMin { get; init; }
    public double DamageMax { get; init; }
    public double Defense { get; init; }
    public double Speed { get; init; }
    public double AggroRange { get; init; }
    public double AttackSpeed { get; init; }
    public List<DropDefinition> Drops { get; init; } = new();
    public required AiPattern Ai { get; init; }
    public List<SpecialAbility> SpecialAbilities { get; init; } = new();
    public List<EnemyAttackDef> Attacks { get; set; } = new();
    public string Narrative { get; init; } = "";
    public List<string> Tags { get; init; } = new();
    public string? IconPath { get; init; }

    // enemy.py:135-153 — computed visual size (category base × tier, cap 8)
    private static readonly Dictionary<string, double> CategoryBaseSize = new()
    {
        ["beast"] = 1.0, ["ooze"] = 1.0, ["insect"] = 1.0, ["construct"] = 1.2,
        ["undead"] = 1.0, ["elemental"] = 1.1, ["aberration"] = 1.3,
        ["dragon"] = 1.5, ["humanoid"] = 1.0,
    };

    private static readonly Dictionary<long, double> TierSizeMultiplier = new()
    { [1] = 1.0, [2] = 1.4, [3] = 2.0, [4] = 3.0 };

    public double VisualSize =>
        Math.Min(8.0, Math.Max(1.0,
            CategoryBaseSize.GetValueOrDefault(Category, 1.0)
            * TierSizeMultiplier.GetValueOrDefault(Tier, 1.0)));

    public double HurtboxRadius => Math.Max(0.4, VisualSize * 0.4);

    /// <summary>enemy.py:682-689 — REAL loot semantics: roll &lt;= chance
    /// (inclusive), then randint on [min, max]. Injected Python-exact RNG.</summary>
    public List<(string MaterialId, long Quantity)> GenerateLoot(PythonRandom rng)
    {
        var loot = new List<(string, long)>();
        foreach (var drop in Drops)
            if (rng.NextDouble() <= drop.Chance)
                loot.Add((drop.MaterialId, rng.RandInt(drop.QuantityMin, drop.QuantityMax)));
        return loot;
    }
}

public sealed class EnemyDatabase
{
    private static readonly Dictionary<string, double> ChanceMap = new()
    {
        ["guaranteed"] = 1.0, ["high"] = 0.75, ["moderate"] = 0.5,
        ["low"] = 0.25, ["rare"] = 0.10, ["improbable"] = 0.05,
    };

    public Dictionary<string, EnemyDefinition> Enemies { get; } = new();
    public Dictionary<long, List<EnemyDefinition>> EnemiesByTier { get; } = new()
    { [1] = new(), [2] = new(), [3] = new(), [4] = new() };
    public bool Loaded { get; private set; }

    public void LoadFromFiles(string contentRoot)
    {
        Enemies.Clear();
        foreach (var list in EnemiesByTier.Values) list.Clear();
        var dir = Path.Combine(contentRoot, "Definitions.JSON");
        foreach (var path in J.GlobSorted(dir, "hostiles-*.JSON"))
        {
            if (Path.GetFileName(path).ToLowerInvariant().Contains("generated"))
                continue;
            LoadFromFile(path);
        }
        foreach (var path in J.GlobSorted(dir, "hostiles-generated-*.JSON"))
            LoadFromFile(path);
        Loaded = Enemies.Count > 0;
    }

    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        ParseData(data);
        Loaded = true;
    }

    private void ParseData(JsonObject data)
    {
        // enemy.py:277-295 — top-level abilities array, referenced by id
        var abilityMap = new Dictionary<string, SpecialAbility>();
        foreach (var node in J.Arr(data, "abilities"))
        {
            if (node is not JsonObject a) continue;
            var trigger = J.Obj(a, "triggerConditions");
            var ability = new SpecialAbility(
                J.Str(a, "abilityId"), J.Str(a, "name"),
                J.Num(a, "cooldown", 10.0), Strings(a, "tags"),
                J.Obj(a, "effectParams"),
                J.Num(trigger, "healthThreshold", 1.0),
                J.Num(trigger, "distanceMin", 0.0),
                J.Num(trigger, "distanceMax", 999.0),
                (long)J.Num(trigger, "enemyCount", 0),
                (long)J.Num(trigger, "allyCount", 0),
                J.Bool(trigger, "oncePerFight", false),
                (long)J.Num(trigger, "maxUsesPerFight", 0),
                (long)J.Num(a, "priority", 0));
            abilityMap[ability.AbilityId] = ability;
        }

        foreach (var node in J.Arr(data, "enemies"))
        {
            if (node is not JsonObject e) continue;
            var stats = J.Obj(e, "stats");
            var (dmgMin, dmgMax) = MinMax(stats, "damage", 5, 10);

            var drops = new List<DropDefinition>();
            foreach (var dropNode in J.Arr(e, "drops"))
            {
                if (dropNode is not JsonObject d) continue;
                var (qMin, qMax) = MinMax(d, "quantity", 1, 1);
                drops.Add(new DropDefinition(
                    J.Str(d, "materialId"), (long)qMin, (long)qMax,
                    ChanceMap.GetValueOrDefault(J.Str(d, "chance", "low"), 0.5)));
            }

            var aiData = J.Obj(e, "aiPattern");
            var abilityIds = Strings(aiData, "specialAbilities");
            var ai = new AiPattern(
                J.Str(aiData, "defaultState", "idle"),
                J.Bool(aiData, "aggroOnDamage", true),
                J.Bool(aiData, "aggroOnProximity", false),
                J.Num(aiData, "fleeAtHealth", 0.0),
                J.Num(aiData, "callForHelpRadius", 0.0),
                J.Bool(aiData, "packCoordination", false),
                abilityIds);

            var specials = abilityIds
                .Where(abilityMap.ContainsKey)
                .Select(id => abilityMap[id]).ToList();

            var metadata = J.Obj(e, "metadata");
            var enemyId = J.Str(e, "enemyId");
            var iconPath = J.Str(e, "iconPath", "");
            if (string.IsNullOrEmpty(iconPath) && enemyId.Length > 0)
                iconPath = $"enemies/{enemyId}.png";

            var def = new EnemyDefinition
            {
                EnemyId = enemyId,
                Name = J.Str(e, "name", "Unknown Enemy"),
                Tier = (long)J.Num(e, "tier", 1),
                Category = J.Str(e, "category", "beast"),
                Behavior = J.Str(e, "behavior", "passive_patrol"),
                MaxHealth = J.Num(stats, "health", 50),
                DamageMin = dmgMin,
                DamageMax = dmgMax,
                Defense = J.Num(stats, "defense", 0),
                Speed = J.Num(stats, "speed", 1.0),
                AggroRange = J.Num(stats, "aggroRange", 5),
                AttackSpeed = J.Num(stats, "attackSpeed", 1.0),
                Drops = drops,
                Ai = ai,
                SpecialAbilities = specials,
                Narrative = J.Str(metadata, "narrative"),
                Tags = Strings(metadata, "tags"),
                IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
            };
            def.Attacks = AttackProfileGenerator.Generate(def);

            Enemies[def.EnemyId] = def;
            if (EnemiesByTier.TryGetValue(def.Tier, out var tierList))
                tierList.Add(def);
        }
    }

    private static (double Min, double Max) MinMax(
        JsonObject o, string key, double defMin, double defMax)
    {
        if (o.TryGetPropertyValue(key, out var n))
        {
            if (n is JsonArray a && a.Count >= 2)
                return (J.AsNum(a[0]) ?? defMin, J.AsNum(a[1]) ?? defMax);
            if (J.AsNum(n) is { } scalar)
                return (scalar, scalar);
        }
        return (defMin, defMax);
    }

    private static List<string> Strings(JsonObject o, string key) =>
        o.TryGetPropertyValue(key, out var n) && n is JsonArray a
            ? a.OfType<JsonValue>()
               .Select(v => v.TryGetValue<string>(out var s) ? s : null)
               .Where(s => s is not null).Cast<string>().ToList()
            : new List<string>();
}
