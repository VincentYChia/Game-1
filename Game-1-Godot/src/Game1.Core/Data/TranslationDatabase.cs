using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/translation_db.py — single source of truth for
/// skill enum translations (§15 traps 4+5). Same fallback tables when the
/// JSON files are absent/malformed.
/// </summary>
public sealed class TranslationDatabase
{
    public Dictionary<string, long> ManaCosts { get; } = new();
    public Dictionary<string, long> CooldownSeconds { get; } = new();
    public Dictionary<string, long> DurationSeconds { get; } = new();
    public Dictionary<string, JsonObject> MagnitudeValues { get; } = new();
    public bool Loaded { get; private set; }

    private static readonly Dictionary<string, long> FallbackMana = new()
        { ["low"] = 30, ["moderate"] = 60, ["high"] = 100, ["extreme"] = 150 };
    private static readonly Dictionary<string, long> FallbackCooldown = new()
        { ["short"] = 120, ["moderate"] = 300, ["long"] = 600, ["extreme"] = 1200 };
    private static readonly Dictionary<string, long> FallbackDuration = new()
        { ["instant"] = 0, ["brief"] = 15, ["moderate"] = 30, ["long"] = 60, ["extended"] = 120 };

    public void LoadFromFiles(string contentRoot)
    {
        LoadTranslationTable(Path.Combine(contentRoot,
            "Definitions.JSON", "skills-translation-table.JSON"));
        LoadBaseEffects(Path.Combine(contentRoot,
            "Skills", "skills-base-effects-1.JSON"));
        Loaded = true;
    }

    // translation_db.py:71-88
    private void LoadTranslationTable(string path)
    {
        if (!File.Exists(path)) { ApplyTranslationFallbacks(); return; }
        try
        {
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            foreach (var kv in J.Obj(data, "durationTranslations"))
                DurationSeconds[kv.Key] = (long)J.Num((JsonObject)kv.Value!, "seconds", 0);
            foreach (var kv in J.Obj(data, "manaCostTranslations"))
                ManaCosts[kv.Key] = (long)J.Num((JsonObject)kv.Value!, "cost", 0);
            foreach (var kv in J.Obj(data, "cooldownTranslations"))
                CooldownSeconds[kv.Key] = (long)J.Num((JsonObject)kv.Value!, "seconds", 0);
        }
        catch
        {
            ApplyTranslationFallbacks();
        }
    }

    // translation_db.py:90-105 — magnitude tables kept raw (int/float mix)
    private void LoadBaseEffects(string path)
    {
        if (!File.Exists(path)) return;  // fallback magnitude table omitted: file ships with the game
        try
        {
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            foreach (var kv in J.Obj(data, "BASE_EFFECT_TYPES"))
            {
                if (kv.Value is JsonObject effectData)
                    MagnitudeValues[kv.Key] = J.Obj(effectData, "magnitudeValues");
            }
        }
        catch { /* stale-but-intact preferred */ }
    }

    private void ApplyTranslationFallbacks()
    {
        if (ManaCosts.Count == 0)
            foreach (var kv in FallbackMana) ManaCosts[kv.Key] = kv.Value;
        if (CooldownSeconds.Count == 0)
            foreach (var kv in FallbackCooldown) CooldownSeconds[kv.Key] = kv.Value;
        if (DurationSeconds.Count == 0)
            foreach (var kv in FallbackDuration) DurationSeconds[kv.Key] = kv.Value;
    }
}
