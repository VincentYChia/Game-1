using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/chunk_template_db.py — biome chunk templates.
/// Sacred Definitions.JSON/Chunk-templates-*.JSON, generated overlay wins,
/// geo dispatch bridge from world_system/config/geo_chunk_dispatch.json
/// (shared with the Python sidecar per ADR-3/doc-03), plus geoTypes
/// auto-registration where sacred dispatch wins on collision.
/// Python-coercion semantics mirrored: str()/int()-with-fallback, tier
/// clamp 1-4, bool() TRUTHINESS for spawnAreaAllowed/edgeOnly.
/// </summary>
public sealed record ResourceDensitySpec(string ResourceId, string Density, string TierBias)
{
    public double SpawnWeight => ChunkTemplateDatabase.DensityWeights.GetValueOrDefault(Density, 1.0);
    public int TierBiasRank => ChunkTemplateDatabase.TierBiasOrder.GetValueOrDefault(TierBias, 1);
}

public sealed record EnemySpawnSpec(string EnemyId, string Density, long Tier)
{
    public double SpawnWeight => ChunkTemplateDatabase.DensityWeights.GetValueOrDefault(Density, 1.0);
}

public sealed record GenerationRules(
    long RollWeight, bool SpawnAreaAllowed, JsonArray AdjacencyPreference,
    bool EdgeOnly, long MinDistanceBetween);

public sealed class ChunkTemplate
{
    public required string ChunkType { get; init; }
    public required string Name { get; init; }
    public required string Category { get; init; }
    public required string Theme { get; init; }
    public Dictionary<string, ResourceDensitySpec> ResourceDensity { get; init; } = new();
    public Dictionary<string, EnemySpawnSpec> EnemySpawns { get; init; } = new();
    public required GenerationRules Rules { get; init; }
    public string Narrative { get; init; } = "";
    public JsonNode Tags { get; init; } = new JsonArray();
    public JsonNode? TilePattern { get; init; }
    public List<string> GeoTypes { get; init; } = new();
    public string Source { get; init; } = "sacred";

    public bool IsWater => Theme == "water" || Category is "water" or "rare_water";

    public JsonObject ToParityNode()
    {
        var density = new JsonObject();
        foreach (var kv in ResourceDensity)
            density[kv.Key] = new JsonObject
            {
                ["resource_id"] = kv.Value.ResourceId,
                ["density"] = kv.Value.Density,
                ["tier_bias"] = kv.Value.TierBias,
            };
        var spawns = new JsonObject();
        foreach (var kv in EnemySpawns)
            spawns[kv.Key] = new JsonObject
            {
                ["enemy_id"] = kv.Value.EnemyId,
                ["density"] = kv.Value.Density,
                ["tier"] = kv.Value.Tier,
            };
        var geo = new JsonArray();
        foreach (var g in GeoTypes) geo.Add(g);
        return new JsonObject
        {
            ["chunk_type"] = ChunkType,
            ["name"] = Name,
            ["category"] = Category,
            ["theme"] = Theme,
            ["resource_density"] = density,
            ["enemy_spawns"] = spawns,
            ["generation_rules"] = new JsonObject
            {
                ["roll_weight"] = Rules.RollWeight,
                ["spawn_area_allowed"] = Rules.SpawnAreaAllowed,
                ["adjacency_preference"] = Rules.AdjacencyPreference.DeepClone(),
                ["edge_only"] = Rules.EdgeOnly,
                ["min_distance_between"] = Rules.MinDistanceBetween,
            },
            ["narrative"] = Narrative,
            ["tags"] = Tags.DeepClone(),
            ["tile_pattern"] = TilePattern?.DeepClone(),
            ["geo_types"] = geo,
            ["source"] = Source,
        };
    }
}

public sealed class ChunkTemplateDatabase
{
    // chunk_template_db.py:52-65
    public static readonly IReadOnlyDictionary<string, double> DensityWeights =
        new Dictionary<string, double>
        {
            ["very_low"] = 0.5, ["low"] = 0.75, ["moderate"] = 1.0,
            ["high"] = 2.0, ["very_high"] = 3.0,
        };

    public static readonly IReadOnlyDictionary<string, int> TierBiasOrder =
        new Dictionary<string, int>
        { ["low"] = 1, ["mid"] = 2, ["high"] = 3, ["legendary"] = 4 };

    public Dictionary<string, ChunkTemplate> Templates { get; } = new();
    private readonly List<string> _insertionOrder = new();  // Python dict-order semantics
    public Dictionary<string, string> GeoDispatch { get; } = new();
    public bool Loaded { get; private set; }

    public void LoadFromFiles(string contentRoot)
    {
        Templates.Clear();
        _insertionOrder.Clear();
        GeoDispatch.Clear();
        var dir = Path.Combine(contentRoot, "Definitions.JSON");
        foreach (var path in J.GlobSorted(dir, "Chunk-templates-*.JSON"))
        {
            if (Path.GetFileName(path).ToLowerInvariant().Contains("generated"))
                continue;
            MergeTemplateFile(path, "sacred");
        }
        foreach (var path in J.GlobSorted(dir, "Chunk-templates-generated-*.JSON"))
            MergeTemplateFile(path, "generated");

        LoadGeoDispatch(Path.Combine(contentRoot,
            "world_system", "config", "geo_chunk_dispatch.json"));
        AutoRegisterGeoTypes();
        Loaded = true;
    }

    private void MergeTemplateFile(string path, string source)
    {
        JsonObject data;
        try
        {
            data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
        }
        catch (Exception e)
        {
            Console.Error.WriteLine(
                $"[ChunkTemplateDatabase] failed to load {Path.GetFileName(path)}: {e.Message}");
            return;
        }
        // chunk_template_db.py:348-350 — "templates", tolerate "chunkTemplates"
        JsonNode? templatesRaw = data.TryGetPropertyValue("templates", out var t) && t is not null
            ? t
            : (data.TryGetPropertyValue("chunkTemplates", out var ct) ? ct : null);
        if (templatesRaw is not JsonArray arr) return;
        foreach (var node in arr)
        {
            if (node is not JsonObject raw) continue;
            var template = BuildTemplate(raw, source);
            if (template is null) continue;
            if (!Templates.ContainsKey(template.ChunkType))
                _insertionOrder.Add(template.ChunkType);
            Templates[template.ChunkType] = template;
        }
    }

    // Python bool() truthiness for JSON values
    private static bool Truthy(JsonObject o, string key)
    {
        if (!o.TryGetPropertyValue(key, out var n) || n is null) return false;
        if (n is JsonValue v)
        {
            if (v.TryGetValue<bool>(out var b)) return b;
            if (v.TryGetValue<double>(out var d)) return d != 0;
            if (v.TryGetValue<string>(out var s)) return s.Length > 0;
        }
        if (n is JsonArray a) return a.Count > 0;
        if (n is JsonObject ob) return ob.Count > 0;
        return true;
    }

    private static long IntOr(JsonObject o, string key, long fallback)
    {
        if (o.TryGetPropertyValue(key, out var n) && n is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return (long)d;
            // Python int("5") succeeds; int("x") -> fallback
            if (v.TryGetValue<string>(out var s) && long.TryParse(s, out var parsed))
                return parsed;
            if (v.TryGetValue<bool>(out var b)) return b ? 1 : 0;
        }
        return fallback;
    }

    // Python str() coercion: string as-is; missing -> default; other -> raw text
    private static string StrCoerce(JsonObject o, string key, string def)
    {
        if (!o.TryGetPropertyValue(key, out var n) || n is null) return def;
        if (n is JsonValue v && v.TryGetValue<string>(out var s)) return s;
        return n.ToJsonString();
    }

    private static ChunkTemplate? BuildTemplate(JsonObject raw, string source)
    {
        // chunkType must be a non-empty STRING (py :200-202)
        if (!raw.TryGetPropertyValue("chunkType", out var ctNode)
            || ctNode is not JsonValue ctVal
            || !ctVal.TryGetValue<string>(out var chunkType)
            || string.IsNullOrEmpty(chunkType))
            return null;

        var metadata = raw.TryGetPropertyValue("metadata", out var md) && md is JsonObject mdo
            ? mdo : new JsonObject();

        var density = new Dictionary<string, ResourceDensitySpec>();
        if (raw.TryGetPropertyValue("resourceDensity", out var rd) && rd is JsonObject rdo)
            foreach (var kv in rdo)
                if (kv.Value is JsonObject spec)
                    density[kv.Key] = new ResourceDensitySpec(
                        kv.Key,
                        StrCoerce(spec, "density", "moderate"),
                        StrCoerce(spec, "tierBias", "low"));

        var spawns = new Dictionary<string, EnemySpawnSpec>();
        if (raw.TryGetPropertyValue("enemySpawns", out var es) && es is JsonObject eso)
            foreach (var kv in eso)
                if (kv.Value is JsonObject spec)
                    spawns[kv.Key] = new EnemySpawnSpec(
                        kv.Key,
                        StrCoerce(spec, "density", "moderate"),
                        Math.Max(1, Math.Min(4, IntOr(spec, "tier", 1))));

        var rulesRaw = raw.TryGetPropertyValue("generationRules", out var gr) && gr is JsonObject gro
            ? gro : new JsonObject();
        var adjacency = rulesRaw.TryGetPropertyValue("adjacencyPreference", out var adj)
                        && adj is JsonArray adjArr
            ? (JsonArray)adjArr.DeepClone() : new JsonArray();
        var rules = new GenerationRules(
            RollWeight: IntOr(rulesRaw, "rollWeight", 1),
            SpawnAreaAllowed: Truthy(rulesRaw, "spawnAreaAllowed"),
            AdjacencyPreference: adjacency,
            EdgeOnly: Truthy(rulesRaw, "edgeOnly"),
            MinDistanceBetween: IntOr(rulesRaw, "minDistanceBetween", 0));

        var geoTypes = new List<string>();
        if (raw.TryGetPropertyValue("geoTypes", out var gt) && gt is JsonArray gtArr)
            foreach (var g in gtArr)
                if (g is JsonValue gv && gv.TryGetValue<string>(out var gs))
                    geoTypes.Add(gs);

        var tags = metadata.TryGetPropertyValue("tags", out var tg) && tg is JsonArray tgArr
            ? (JsonNode)tgArr.DeepClone() : new JsonArray();

        return new ChunkTemplate
        {
            ChunkType = chunkType,
            Name = StrCoerce(raw, "name", chunkType),
            Category = StrCoerce(raw, "category", "peaceful"),
            Theme = StrCoerce(raw, "theme", "forest"),
            ResourceDensity = density,
            EnemySpawns = spawns,
            Rules = rules,
            Narrative = J.Str(metadata, "narrative"),
            Tags = tags,
            TilePattern = raw.TryGetPropertyValue("tilePattern", out var tp) && tp is JsonObject tpo
                ? tpo.DeepClone() : null,
            GeoTypes = geoTypes,
            Source = source,
        };
    }

    private void LoadGeoDispatch(string path)
    {
        if (!File.Exists(path)) return;
        JsonObject data;
        try
        {
            data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"[ChunkTemplateDatabase] failed to load dispatch: {e.Message}");
            return;
        }
        var mapping = data.TryGetPropertyValue("geo_to_chunk_type", out var m) && m is JsonObject mo
            ? mo : data;
        foreach (var kv in mapping)
            if (kv.Value is JsonValue v && v.TryGetValue<string>(out var chunkType))
                GeoDispatch[kv.Key] = chunkType;
    }

    // chunk_template_db.py:385-395 — setdefault; template insertion order
    private void AutoRegisterGeoTypes()
    {
        foreach (var key in _insertionOrder)
        {
            var template = Templates[key];
            foreach (var geoType in template.GeoTypes)
                if (!GeoDispatch.ContainsKey(geoType))
                    GeoDispatch[geoType] = template.ChunkType;
        }
    }

    public ChunkTemplate? Get(string chunkType) => Templates.GetValueOrDefault(chunkType);

    public (int Total, int Sacred, int Generated, int GeoDispatchEntries) Stats()
    {
        var sacred = Templates.Values.Count(t => t.Source == "sacred");
        return (Templates.Count, sacred, Templates.Count - sacred, GeoDispatch.Count);
    }
}
