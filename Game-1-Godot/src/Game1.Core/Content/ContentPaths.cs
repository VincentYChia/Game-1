namespace Game1.Core.Content;

/// <summary>
/// ADR-4: content JSON is consumed verbatim from the shared repo tree during
/// development. Resolution order: GAME1_CONTENT_ROOT env var, then walk up
/// from the executing assembly looking for the Game-1-modular directory.
/// Exported builds will point this at the bundled content snapshot.
/// </summary>
public static class ContentPaths
{
    public static string? TryGetContentRoot()
    {
        var env = Environment.GetEnvironmentVariable("GAME1_CONTENT_ROOT");
        if (!string.IsNullOrEmpty(env) && Directory.Exists(env))
            return env;

        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            var candidate = Path.Combine(dir.FullName, "Game-1-modular");
            if (Directory.Exists(candidate))
                return candidate;
            dir = dir.Parent;
        }
        return null;
    }

    /// <summary>Resolve a content-relative path (e.g. "Definitions.JSON/stats-calculations.JSON").</summary>
    public static string? TryGetResource(string relativePath)
    {
        var root = TryGetContentRoot();
        if (root is null) return null;
        var full = Path.Combine(root, relativePath);
        return File.Exists(full) ? full : null;
    }
}
