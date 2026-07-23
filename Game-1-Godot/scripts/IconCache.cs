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
        // Validate the PNG signature before loading — some assets are Git-LFS
        // pointer stubs / corrupt files, and Image.LoadFromFile spams the
        // console on those. A header check lets us silently fall back to text.
        if (File.Exists(full) && IsPng(full))
        {
            var img = Image.LoadFromFile(full);
            if (img is not null && img.GetWidth() > 0)
                tex = ImageTexture.CreateFromImage(img);
        }
        _cache[iconPath] = tex;   // cache misses too (avoid re-stat every frame)
        return tex;
    }

    private static readonly byte[] PngSig = { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };

    private static bool IsPng(string path)
    {
        try
        {
            using var fs = File.OpenRead(path);
            Span<byte> head = stackalloc byte[8];
            if (fs.Read(head) < 8) return false;
            for (var i = 0; i < 8; i++)
                if (head[i] != PngSig[i]) return false;
            return true;
        }
        catch { return false; }
    }
}
