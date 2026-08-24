using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Tags;

/// <summary>
/// Port of core/tag_system.py — loads Definitions.JSON/tag-definitions.JSON
/// (single source of truth) and provides lookups the parser/executor use.
/// JSON values are held as plain objects: bool / double / string / list /
/// ordered dict — mirroring Python's json.load types.
/// </summary>
public sealed class TagDefinition
{
    public required string Name;
    public string Category = "unknown";
    public string Description = "";
    public double Priority;
    public List<string> RequiresParams = new();
    public Dictionary<string, object?> DefaultParams = new();
    public List<string> ConflictsWith = new();
    public List<string> Aliases = new();
    public string? AliasOf;
    public string? Stacking;
    public List<string> Immunity = new();
    public Dictionary<string, object?> Synergies = new();
    public Dictionary<string, object?> ContextBehavior = new();
    public double AutoApplyChance;
    public string? AutoApplyStatus;
    public string? Parent;
}

public sealed class TagRegistry
{
    public readonly Dictionary<string, TagDefinition> Definitions = new();
    public readonly List<string> DefinitionOrder = new();
    public readonly Dictionary<string, List<string>> Categories = new();
    public readonly Dictionary<string, string> Aliases = new();
    public readonly List<string> GeometryPriority = new();
    public readonly Dictionary<string, List<string>> MutuallyExclusive = new();
    public readonly Dictionary<string, string> ContextInference = new();

    /// <summary>json.load equivalence: object/array/str/number/bool/null →
    /// Dictionary (insertion-ordered) / List / string / double / bool / null.</summary>
    public static object? ToPlain(JsonNode? n)
    {
        switch (n)
        {
            case null:
                return null;
            case JsonArray a:
                return a.Select(ToPlain).ToList();
            case JsonObject o:
                var d = new Dictionary<string, object?>();
                foreach (var kv in o) d[kv.Key] = ToPlain(kv.Value);
                return d;
            default:
                var v = n.AsValue();
                if (v.TryGetValue<bool>(out var b)) return b;
                if (v.TryGetValue<double>(out var num)) return num;
                if (v.TryGetValue<string>(out var s)) return s;
                if (v.TryGetValue<long>(out var l)) return (double)l;
                return null;
        }
    }

    public static List<string> StrList(JsonNode? n) =>
        n is JsonArray a
            ? a.Select(x => x?.GetValue<string>() ?? "").ToList()
            : new List<string>();

    public static TagRegistry LoadFrom(string projectRoot)
    {
        var reg = new TagRegistry();
        var path = Path.Combine(projectRoot, "Definitions.JSON", "tag-definitions.JSON");
        var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();

        if (data["categories"] is JsonObject cats)
            foreach (var kv in cats)
                reg.Categories[kv.Key] = StrList(kv.Value);

        if (data["tag_definitions"] is JsonObject defs)
        {
            foreach (var kv in defs)
            {
                var td = kv.Value!.AsObject();
                var def = new TagDefinition
                {
                    Name = kv.Key,
                    Category = J.Str(td, "category", "unknown"),
                    Description = J.Str(td, "description", ""),
                    Priority = td["priority"] is { } p ? (double)ToPlain(p)! : 0,
                    RequiresParams = StrList(td["requires_params"]),
                    DefaultParams = ToPlain(td["default_params"]) as Dictionary<string, object?> ?? new(),
                    ConflictsWith = StrList(td["conflicts_with"]),
                    Aliases = StrList(td["aliases"]),
                    AliasOf = td["alias_of"]?.GetValue<string>(),
                    Stacking = td["stacking"]?.GetValue<string>(),
                    Immunity = StrList(td["immunity"]),
                    Synergies = ToPlain(td["synergies"]) as Dictionary<string, object?> ?? new(),
                    ContextBehavior = ToPlain(td["context_behavior"]) as Dictionary<string, object?> ?? new(),
                    AutoApplyChance = td["auto_apply_chance"] is { } ac ? (double)ToPlain(ac)! : 0.0,
                    AutoApplyStatus = td["auto_apply_status"]?.GetValue<string>(),
                    Parent = td["parent"]?.GetValue<string>(),
                };
                reg.Definitions[kv.Key] = def;
                reg.DefinitionOrder.Add(kv.Key);
                foreach (var alias in def.Aliases)
                    reg.Aliases[alias] = kv.Key;
            }
        }

        if (data["conflict_resolution"] is JsonObject conf)
        {
            foreach (var g in StrList(conf["geometry_priority"]))
                reg.GeometryPriority.Add(g);
            if (conf["mutually_exclusive"] is JsonObject mx)
                foreach (var kv in mx)
                    reg.MutuallyExclusive[kv.Key] = StrList(kv.Value);
        }

        if (data["context_inference"] is JsonObject ci)
            foreach (var kv in ci)
                reg.ContextInference[kv.Key] = kv.Value?.GetValue<string>() ?? "";

        return reg;
    }

    public string ResolveAlias(string tag) =>
        Aliases.TryGetValue(tag, out var real) ? real : tag;

    public TagDefinition? GetDefinition(string tag) =>
        Definitions.TryGetValue(ResolveAlias(tag), out var d) ? d : null;

    public string? GetCategory(string tag) => GetDefinition(tag)?.Category;

    public bool IsGeometryTag(string tag) => GetCategory(tag) == "geometry";

    public string? ResolveGeometryConflict(List<string> tags)
    {
        var geometryTags = tags.Where(IsGeometryTag).ToList();
        if (geometryTags.Count <= 1)
            return geometryTags.Count > 0 ? geometryTags[0] : null;
        foreach (var priorityTag in GeometryPriority)
            if (geometryTags.Contains(priorityTag))
                return priorityTag;
        return geometryTags[0];
    }

    public bool CheckMutualExclusion(string tag1, string tag2)
    {
        tag1 = ResolveAlias(tag1);
        tag2 = ResolveAlias(tag2);
        return MutuallyExclusive.TryGetValue(tag1, out var ex) && ex.Contains(tag2);
    }

    public Dictionary<string, object?> GetDefaultParams(string tag)
    {
        var def = GetDefinition(tag);
        return def is null ? new() : new Dictionary<string, object?>(def.DefaultParams);
    }
}
