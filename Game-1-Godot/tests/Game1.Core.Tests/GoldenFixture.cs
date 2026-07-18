using System.Text.Json;

namespace Game1.Core.Tests;

/// <summary>
/// Loads golden fixtures produced by conformance/generate_goldens.py from the
/// live Python reference build. Located by walking up from the test binary to
/// the Game-1-Godot directory (override with GAME1_GOLDENS_DIR).
/// </summary>
public static class GoldenFixture
{
    private static readonly Lazy<string> Dir = new(Locate);

    private static string Locate()
    {
        var env = Environment.GetEnvironmentVariable("GAME1_GOLDENS_DIR");
        if (!string.IsNullOrEmpty(env) && Directory.Exists(env))
            return env;

        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            var candidate = Path.Combine(dir.FullName, "conformance", "goldens");
            if (Directory.Exists(candidate))
                return candidate;
            dir = dir.Parent!;
        }
        throw new InvalidOperationException(
            "conformance/goldens not found — run: python Game-1-Godot/conformance/generate_goldens.py");
    }

    public static JsonElement Load(string name)
    {
        var path = Path.Combine(Dir.Value, name);
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        return doc.RootElement.Clone();
    }

    public static void AssertClose(double expected, double actual, string context)
    {
        if (Math.Abs(expected - actual) >= 1e-9)
            throw new Xunit.Sdk.XunitException(
                $"{context}: expected {expected:R}, got {actual:R} (|diff| = {Math.Abs(expected - actual):R})");
    }
}
