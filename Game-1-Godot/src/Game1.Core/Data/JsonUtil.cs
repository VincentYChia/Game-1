using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// dict.get()-style accessors mirroring the Python loaders' defaulting
/// semantics, plus deep-clone helpers (JsonNode instances are single-parent).
/// </summary>
internal static class J
{
    public static string Str(JsonObject o, string key, string def = "")
    {
        if (o.TryGetPropertyValue(key, out var n) && n is JsonValue v)
        {
            if (v.TryGetValue<string>(out var s)) return s;
        }
        return def;
    }

    public static double Num(JsonObject o, string key, double def)
    {
        if (o.TryGetPropertyValue(key, out var n) && n is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return d;
        }
        return def;
    }

    public static int Int(JsonObject o, string key, int def) =>
        (int)Num(o, key, def);

    public static bool Bool(JsonObject o, string key, bool def)
    {
        if (o.TryGetPropertyValue(key, out var n) && n is JsonValue v)
        {
            if (v.TryGetValue<bool>(out var b)) return b;
        }
        return def;
    }

    /// <summary>Raw node clone, or null when absent (Python .get(key) → None).</summary>
    public static JsonNode? NodeOrNull(JsonObject o, string key) =>
        o.TryGetPropertyValue(key, out var n) && n is not null ? n.DeepClone() : null;

    /// <summary>Raw node clone, or the given fallback factory (Python .get(key, default)).</summary>
    public static JsonNode Node(JsonObject o, string key, Func<JsonNode> def) =>
        o.TryGetPropertyValue(key, out var n) && n is not null ? n.DeepClone() : def();

    public static JsonArray Arr(JsonObject o, string key) =>
        o.TryGetPropertyValue(key, out var n) && n is JsonArray a
            ? (JsonArray)a.DeepClone() : new JsonArray();

    public static JsonObject Obj(JsonObject o, string key) =>
        o.TryGetPropertyValue(key, out var n) && n is JsonObject ob
            ? (JsonObject)ob.DeepClone() : new JsonObject();

    /// <summary>Python str() of a JSON number: integral values print without
    /// a decimal point (content uses ints; a true float would print
    /// differently in Python — not present in shipped content).</summary>
    public static string PyNum(double v) =>
        v == Math.Floor(v) && !double.IsInfinity(v)
            ? ((long)v).ToString()
            : v.ToString(System.Globalization.CultureInfo.InvariantCulture);

    /// <summary>Files matching pattern, sorted ordinal. Deterministic where
    /// Python's update_loader uses list(set(glob)) (unordered) — a documented
    /// deviation that only matters on intra-update id collisions.</summary>
    public static IEnumerable<string> GlobSorted(string dir, params string[] patterns)
    {
        if (!Directory.Exists(dir)) return Enumerable.Empty<string>();
        var found = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var pattern in patterns)
            foreach (var f in Directory.GetFiles(dir, pattern))
                found.Add(f);
        return found;
    }
}
