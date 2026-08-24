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
        // The asset files carry a .png extension but are actually a mix of
        // PNG and JPEG (many are JPEG: header FF D8 FF). Dispatch by the real
        // magic number so both load; unknown/corrupt → null → text fallback.
        if (File.Exists(full))
        {
            try
            {
                var bytes = File.ReadAllBytes(full);
                var img = new Image();
                var err = Error.Failed;
                if (bytes.Length >= 3 && bytes[0] == 0xFF && bytes[1] == 0xD8
                    && bytes[2] == 0xFF)
                    err = img.LoadJpgFromBuffer(bytes);
                else if (bytes.Length >= 4 && bytes[0] == 0x89 && bytes[1] == 0x50
                    && bytes[2] == 0x4E && bytes[3] == 0x47)
                    err = img.LoadPngFromBuffer(bytes);
                else if (bytes.Length >= 12 && bytes[0] == 0x52 && bytes[1] == 0x49
                    && bytes[8] == 0x57 && bytes[9] == 0x45)   // RIFF…WEBP
                    err = img.LoadWebpFromBuffer(bytes);
                if (err == Error.Ok && img.GetWidth() > 0)
                    tex = ImageTexture.CreateFromImage(img);
            }
            catch { /* fall back to text */ }
        }
        _cache[iconPath] = tex;   // cache misses too (avoid re-stat every frame)
        return tex;
    }
}
