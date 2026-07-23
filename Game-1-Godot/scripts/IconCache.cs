using Godot;

namespace Game1.Godot;

/// <summary>
/// Runtime loader for the game's icon PNGs (rendering/image_cache.py port).
/// Item paths ("materials/copper_ore.png", "armor/iron_boots.png") get the
/// "items/" prefix; entity paths ("skills/…", "enemies/…", "npcs/…",
/// "titles/…", "resources/…", "quests/…", "classes/…") are direct under
/// assets/. Loaded from the Game-1-modular content root at runtime (the
/// PNGs live outside the Godot project), cached by path, null on miss so
/// callers fall back to text.
/// </summary>
public static class IconCache
{
    private static readonly string[] DirectPrefixes =
    {
        "enemies/", "resources/", "skills/", "titles/",
        "npcs/", "quests/", "classes/",
    };

    private static string? _assetsRoot;
    private static readonly Dictionary<string, Texture2D?> _cache = new();

    public static void Init(string contentRoot) =>
        _assetsRoot = System.IO.Path.Combine(contentRoot, "assets");

    public static Texture2D? Get(string? iconPath)
    {
        if (string.IsNullOrEmpty(iconPath) || _assetsRoot is null) return null;
        if (_cache.TryGetValue(iconPath, out var cached)) return cached;

        var direct = DirectPrefixes.Any(p =>
            iconPath.StartsWith(p, StringComparison.Ordinal));
        var full = direct
            ? System.IO.Path.Combine(_assetsRoot, iconPath)
            : System.IO.Path.Combine(_assetsRoot, "items", iconPath);

        Texture2D? tex = null;
        if (File.Exists(full))
        {
            var img = Image.LoadFromFile(full);
            if (img is not null) tex = ImageTexture.CreateFromImage(img);
        }
        _cache[iconPath] = tex;   // cache misses too (avoid re-stat every frame)
        return tex;
    }
}
