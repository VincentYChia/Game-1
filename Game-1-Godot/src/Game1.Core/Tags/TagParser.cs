using System.Globalization;

namespace Game1.Core.Tags;

/// <summary>Port of core/effect_context.py EffectConfig.</summary>
public sealed class EffectConfig
{
    public List<string> RawTags = new();
    public string? GeometryTag;
    public List<string> DamageTags = new();
    public List<string> StatusTags = new();
    public List<string> ContextTags = new();
    public List<string> SpecialTags = new();
    public List<string> TriggerTags = new();
    public string Context = "enemy";
    public double BaseDamage;
    public double BaseHealing;
    public Dictionary<string, object?> Params = new();
    public List<string> Warnings = new();
    public List<string> ConflictsResolved = new();
}

/// <summary>
/// Port of core/tag_parser.py — tags + effectParams → EffectConfig.
/// Warning strings match Python character-for-character (they are dumped
/// into the conformance fixture).
/// </summary>
public sealed class TagParser
{
    private readonly TagRegistry _registry;

    public TagParser(TagRegistry registry)
    {
        _registry = registry;
    }

    internal static double Num(object? v, double dflt = 0.0) => v switch
    {
        double d => d,
        long l => l,
        int i => i,
        bool b => b ? 1.0 : 0.0,
        _ => dflt,
    };

    /// <summary>Python repr of a list of strings: ['a', 'b'].</summary>
    private static string PyListRepr(IEnumerable<string> xs) =>
        "[" + string.Join(", ", xs.Select(x => "'" + x + "'")) + "]";

    public EffectConfig Parse(List<string> tags, Dictionary<string, object?> paramsIn)
    {
        var config = new EffectConfig { RawTags = new List<string>(tags) };

        var resolvedTags = tags.Select(_registry.ResolveAlias).ToList();

        var geometryTags = new List<string>();
        var damageTags = new List<string>();
        var statusTags = new List<string>();
        var contextTags = new List<string>();
        var specialTags = new List<string>();
        var triggerTags = new List<string>();

        foreach (var tag in resolvedTags)
        {
            var category = _registry.GetCategory(tag);
            switch (category)
            {
                case "geometry": geometryTags.Add(tag); break;
                case "damage_type": damageTags.Add(tag); break;
                case "status_debuff":
                case "status_buff": statusTags.Add(tag); break;
                case "context": contextTags.Add(tag); break;
                case "special": specialTags.Add(tag); break;
                case "trigger": triggerTags.Add(tag); break;
                case "equipment": break;
                case "unknown":
                    config.Warnings.Add($"Unknown tag: {tag}");
                    break;
                    // any other category (class/playstyle/armor_type/null)
                    // falls through silently, as in Python
            }
        }

        if (geometryTags.Count > 1)
        {
            var resolvedGeometry = _registry.ResolveGeometryConflict(geometryTags);
            config.GeometryTag = resolvedGeometry;
            var ignored = geometryTags.Where(g => g != resolvedGeometry).ToList();
            config.ConflictsResolved.Add(
                $"Geometry conflict: using '{resolvedGeometry}', ignoring {PyListRepr(ignored)}");
        }
        else if (geometryTags.Count == 1)
        {
            config.GeometryTag = geometryTags[0];
        }
        else
        {
            config.GeometryTag = "single_target";
        }

        config.DamageTags = damageTags;
        config.StatusTags = statusTags;
        config.ContextTags = contextTags;
        config.SpecialTags = specialTags;
        config.TriggerTags = triggerTags;

        config.Context = InferContext(contextTags, damageTags, statusTags, paramsIn);

        if (contextTags.Count > 0)
        {
            if (contextTags.Contains("enemy") && damageTags.Count > 0)
            {
                // expected
            }
            else if (contextTags.Contains("enemy")
                     && (resolvedTags.Contains("healing")
                         || Num(paramsIn.GetValueOrDefault("baseHealing"), 0) > 0))
            {
                config.Warnings.Add("Healing effect on enemy context - is this intentional?");
            }
            else if (contextTags.Contains("ally") && damageTags.Count > 0)
            {
                config.Warnings.Add("Damage effect on ally context - friendly fire?");
            }
        }

        config.Params = MergeAllParams(resolvedTags, paramsIn);

        // NOTE Python order: base damage/healing extracted BEFORE synergies —
        // a synergy that boosts params['baseDamage'] does NOT update these.
        config.BaseDamage = Num(config.Params.GetValueOrDefault("baseDamage"), 0.0);
        config.BaseHealing = Num(config.Params.GetValueOrDefault("baseHealing"), 0.0);

        ApplySynergies(config);
        CheckMutualExclusions(config);

        return config;
    }

    private string InferContext(List<string> contextTags, List<string> damageTags,
                                List<string> statusTags,
                                Dictionary<string, object?> paramsIn)
    {
        if (contextTags.Count > 0)
            return contextTags[0];

        var hasDamage = damageTags.Count > 0
            || Num(paramsIn.GetValueOrDefault("baseDamage"), 0) > 0;
        var hasHealing = Num(paramsIn.GetValueOrDefault("baseHealing"), 0) > 0;

        var debuffStatuses = statusTags
            .Where(t => _registry.GetCategory(t) == "status_debuff").ToList();
        var buffStatuses = statusTags
            .Where(t => _registry.GetCategory(t) == "status_buff").ToList();

        if (hasDamage || debuffStatuses.Count > 0)
            return "enemy";
        if (hasHealing || buffStatuses.Count > 0)
            return "ally";
        return "enemy";
    }

    private Dictionary<string, object?> MergeAllParams(
        List<string> tags, Dictionary<string, object?> userParams)
    {
        var merged = new Dictionary<string, object?>();
        foreach (var tag in tags)
            foreach (var kv in _registry.GetDefaultParams(tag))
                merged[kv.Key] = kv.Value;
        foreach (var kv in userParams)
            merged[kv.Key] = kv.Value;
        return merged;
    }

    private void ApplySynergies(EffectConfig config)
    {
        foreach (var tag in config.RawTags)
        {
            var tagDef = _registry.GetDefinition(tag);
            if (tagDef is null || tagDef.Synergies.Count == 0)
                continue;

            foreach (var (synergyTag, bonusesObj) in tagDef.Synergies)
            {
                if (!config.RawTags.Contains(synergyTag)) continue;
                if (bonusesObj is not Dictionary<string, object?> bonuses) continue;

                foreach (var (param, bonusObj) in bonuses)
                {
                    if (!param.EndsWith("_bonus")) continue;
                    var baseParam = param.Replace("_bonus", "");
                    if (!config.Params.ContainsKey(baseParam)) continue;

                    var bonus = Num(bonusObj);
                    var current = Num(config.Params[baseParam]);
                    config.Params[baseParam] = current * (1.0 + bonus);
                    // Python f"...+{bonus*100:.0f}%" — round-half-even
                    var pct = Math.Round(bonus * 100, MidpointRounding.ToEven)
                        .ToString("0", CultureInfo.InvariantCulture);
                    config.Warnings.Add(
                        $"Synergy: {tag} + {synergyTag} = {baseParam} +{pct}%");
                }
            }
        }
    }

    private void CheckMutualExclusions(EffectConfig config)
    {
        var allTags = config.DamageTags
            .Concat(config.StatusTags)
            .Concat(config.ContextTags)
            .Concat(config.SpecialTags)
            .ToList();

        for (var i = 0; i < allTags.Count; i++)
        {
            for (var j = i + 1; j < allTags.Count; j++)
            {
                if (_registry.CheckMutualExclusion(allTags[i], allTags[j]))
                {
                    config.Warnings.Add(
                        $"Mutually exclusive tags: {allTags[i]} and {allTags[j]} - " +
                        $"{allTags[j]} will override {allTags[i]}");
                }
            }
        }
    }
}
