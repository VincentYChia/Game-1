using Godot;

namespace Game1.Godot;

/// <summary>Per-discipline visual identity (glyph, accent, backdrop, embers) —
/// the SINGLE source shared by the minigame CraftStage and the placement stage so
/// the whole Workshop reads with one coherent palette.</summary>
public readonly record struct DisciplineStyle(
    string Glyph, Color Accent, Color Top, Color Bottom, Color Glow, Color Ember, float Rise, string Name);

public static class CraftStyle
{
    public static readonly Dictionary<string, DisciplineStyle> All = new()
    {
        ["smithing"]    = new("⚒", new(0.98f, 0.55f, 0.32f), new(0.16f, 0.09f, 0.06f), new(0.03f, 0.02f, 0.02f), new(1f, 0.48f, 0.14f),  new(1f, 0.6f, 0.22f),  62f, "Forge"),
        ["alchemy"]     = new("⚗", new(0.55f, 0.95f, 0.62f), new(0.06f, 0.13f, 0.10f), new(0.02f, 0.04f, 0.03f), new(0.38f, 0.9f, 0.6f), new(0.5f, 1f, 0.72f),  42f, "Alchemy Lab"),
        ["refining"]    = new("♨", new(0.98f, 0.78f, 0.42f), new(0.13f, 0.10f, 0.07f), new(0.03f, 0.02f, 0.02f), new(0.95f, 0.7f, 0.3f), new(0.92f, 0.8f, 0.5f), 34f, "Refinery"),
        ["engineering"] = new("⚙", new(0.55f, 0.78f, 0.98f), new(0.06f, 0.10f, 0.15f), new(0.02f, 0.03f, 0.05f), new(0.4f, 0.7f, 1f),    new(0.55f, 0.82f, 1f), 30f, "Workshop"),
        ["adornments"]  = new("✦", new(0.82f, 0.55f, 0.98f), new(0.11f, 0.07f, 0.15f), new(0.03f, 0.02f, 0.05f), new(0.7f, 0.4f, 1f),    new(0.82f, 0.6f, 1f),  26f, "Enchanter"),
        ["fishing"]     = new("≈", new(0.4f, 0.8f, 1f),      new(0.04f, 0.11f, 0.19f), new(0.01f, 0.03f, 0.06f), new(0.3f, 0.7f, 1f),    new(0.62f, 0.9f, 1f),  20f, "Fishing"),
    };

    public static DisciplineStyle Get(string discipline)
        => All.GetValueOrDefault(discipline, All["smithing"]);
}
