using System.Text.Json.Nodes;

namespace Game1.Core;

/// <summary>Plain-object (bool/double/long/string/list/dict) → JsonNode,
/// the inverse of TagRegistry.ToPlain. Used where executor param dicts meet
/// JsonObject-based APIs (status manager, dumps).</summary>
public static class PlainJson
{
    public static JsonNode? ToNode(object? v) => v switch
    {
        null => null,
        bool b => JsonValue.Create(b),
        double d => JsonValue.Create(d),
        long l => JsonValue.Create(l),
        int i => JsonValue.Create(i),
        string s => JsonValue.Create(s),
        List<object?> list => new JsonArray(list.Select(ToNode).ToArray()),
        Dictionary<string, object?> dict => ToObject(dict),
        JsonNode n => n.DeepClone(),
        _ => throw new InvalidOperationException($"unexpected plain value {v.GetType()}"),
    };

    public static JsonObject ToObject(Dictionary<string, object?> dict)
    {
        var o = new JsonObject();
        foreach (var kv in dict) o[kv.Key] = ToNode(kv.Value);
        return o;
    }
}
