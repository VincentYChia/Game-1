using System.Text.Json;
using System.Text.Json.Nodes;

namespace Game1.Core.Tests;

/// <summary>
/// Structural JSON comparison for loader-parity: objects key-set compared
/// (order-insensitive), arrays order-sensitive, numbers compared numerically
/// (1e-9), everything else exact. Returns human-readable diff paths.
/// </summary>
public static class JsonTreeComparer
{
    public static List<string> Diff(JsonNode? expected, JsonNode? actual)
    {
        using var e = JsonDocument.Parse(expected?.ToJsonString() ?? "null");
        using var a = JsonDocument.Parse(actual?.ToJsonString() ?? "null");
        var diffs = new List<string>();
        Walk(e.RootElement, a.RootElement, "$", diffs);
        return diffs;
    }

    public static List<string> Diff(JsonElement expected, JsonNode? actual)
    {
        using var a = JsonDocument.Parse(actual?.ToJsonString() ?? "null");
        var diffs = new List<string>();
        Walk(expected, a.RootElement, "$", diffs);
        return diffs;
    }

    private static void Walk(JsonElement e, JsonElement a, string path, List<string> diffs)
    {
        if (diffs.Count > 200) return;  // enough to diagnose

        var eKind = Normalize(e.ValueKind);
        var aKind = Normalize(a.ValueKind);
        if (eKind != aKind)
        {
            diffs.Add($"{path}: kind {e.ValueKind} != {a.ValueKind} " +
                      $"(expected {Snippet(e)}, actual {Snippet(a)})");
            return;
        }

        switch (e.ValueKind)
        {
            case JsonValueKind.Object:
                var eProps = e.EnumerateObject().Select(p => p.Name).ToHashSet();
                var aProps = a.EnumerateObject().Select(p => p.Name).ToHashSet();
                foreach (var missing in eProps.Except(aProps).OrderBy(x => x))
                    diffs.Add($"{path}.{missing}: MISSING in actual");
                foreach (var extra in aProps.Except(eProps).OrderBy(x => x))
                    diffs.Add($"{path}.{extra}: EXTRA in actual");
                foreach (var p in e.EnumerateObject())
                    if (aProps.Contains(p.Name))
                        Walk(p.Value, a.GetProperty(p.Name), $"{path}.{p.Name}", diffs);
                break;

            case JsonValueKind.Array:
                var eArr = e.EnumerateArray().ToList();
                var aArr = a.EnumerateArray().ToList();
                if (eArr.Count != aArr.Count)
                {
                    diffs.Add($"{path}: array length {eArr.Count} != {aArr.Count}");
                    return;
                }
                for (var i = 0; i < eArr.Count; i++)
                    Walk(eArr[i], aArr[i], $"{path}[{i}]", diffs);
                break;

            case JsonValueKind.Number:
                if (Math.Abs(e.GetDouble() - a.GetDouble()) >= 1e-9)
                    diffs.Add($"{path}: {e.GetRawText()} != {a.GetRawText()}");
                break;

            case JsonValueKind.String:
                if (e.GetString() != a.GetString())
                    diffs.Add($"{path}: \"{e.GetString()}\" != \"{a.GetString()}\"");
                break;

            // True/False/Null: kinds already matched (normalized bool), compare raw
            default:
                if (e.ValueKind != a.ValueKind)
                    diffs.Add($"{path}: {e.GetRawText()} != {a.GetRawText()}");
                break;
        }
    }

    private static JsonValueKind Normalize(JsonValueKind k) =>
        k == JsonValueKind.False ? JsonValueKind.True : k;

    private static string Snippet(JsonElement el)
    {
        var raw = el.GetRawText();
        return raw.Length <= 60 ? raw : raw[..60] + "...";
    }
}
