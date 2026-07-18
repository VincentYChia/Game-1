using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/update_loader.py for the tranche-1 databases.
/// Reads updates_manifest.json, scans each installed Update-N directory with
/// per-type filename patterns, and layers content on top of the loaded DBs.
/// Deviation (documented): Python iterates list(set(glob)) — unordered; this
/// port sorts ordinal. Only observable on intra-update id collisions (none
/// exist today). Enemy + skill-unlock update routing arrives with those DBs.
/// </summary>
public sealed class UpdateLoader
{
    public static IReadOnlyList<string> GetInstalledUpdates(string projectRoot)
    {
        var manifest = Path.Combine(projectRoot, "updates_manifest.json");
        if (!File.Exists(manifest)) return Array.Empty<string>();
        try
        {
            var data = JsonNode.Parse(File.ReadAllText(manifest))!.AsObject();
            return J.Arr(data, "installed_updates")
                .Select(n => n?.GetValue<string>() ?? "")
                .Where(s => s.Length > 0)
                .ToList();
        }
        catch
        {
            return Array.Empty<string>();
        }
    }

    /// <summary>Mirrors load_all_updates() ordering for the ported DBs:
    /// equipment → skills → materials → recipes → titles.</summary>
    public static void LoadAll(
        string projectRoot,
        EquipmentDatabase equipment,
        SkillDatabase skills,
        MaterialDatabase materials,
        RecipeDatabase recipes,
        TitleDatabase titles)
    {
        var installed = GetInstalledUpdates(projectRoot);
        foreach (var update in installed)
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;

            // equipment: update_loader.py:45-48
            foreach (var f in J.GlobSorted(dir,
                         "*items*.JSON", "*weapons*.JSON", "*armor*.JSON", "*tools*.JSON"))
                Try(() => equipment.LoadFromFile(f), f);
        }
        foreach (var update in installed)
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in J.GlobSorted(dir, "*skills*.JSON"))
                Try(() => skills.LoadFromFile(f), f);
        }
        foreach (var update in installed)
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;
            // materials: update_loader.py:158-186 — materials files use the
            // full parser; consumables/devices go through load_stackable_items
            foreach (var f in J.GlobSorted(dir,
                         "*materials*.JSON", "*consumables*.JSON", "*devices*.JSON"))
                Try(() =>
                {
                    if (Path.GetFileName(f).ToLowerInvariant().Contains("materials"))
                        materials.LoadFromFile(f);
                    else
                        materials.LoadStackableItems(f, null);
                }, f);
        }
        foreach (var update in installed)
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;
            // recipes: update_loader.py:241-291 — station type from filename
            foreach (var f in J.GlobSorted(dir, "*recipes*.JSON"))
                Try(() =>
                {
                    var name = Path.GetFileName(f).ToLowerInvariant();
                    var station =
                        name.Contains("smithing") ? "smithing" :
                        name.Contains("alchemy") ? "alchemy" :
                        name.Contains("refining") ? "refining" :
                        name.Contains("engineering") ? "engineering" :
                        name.Contains("adornment") || name.Contains("enchanting") ? "adornments" :
                        "smithing";
                    recipes.LoadFile(f, station);
                }, f);
        }
        foreach (var update in installed)
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in J.GlobSorted(dir, "*titles*.JSON"))
                Try(() => titles.LoadFromFile(f), f);
        }
    }

    /// <summary>update_loader.py:215-238 — skill-unlock update routing.</summary>
    public static void LoadSkillUnlockUpdates(string projectRoot, SkillUnlockDatabase db)
    {
        foreach (var update in GetInstalledUpdates(projectRoot))
        {
            var dir = Path.Combine(projectRoot, update);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in J.GlobSorted(dir, "*skill-unlocks*.JSON", "*skill_unlocks*.JSON"))
                Try(() => db.LoadFromFile(f), f);
        }
    }

    private static void Try(Action load, string file)
    {
        try { load(); }
        catch (Exception e)
        {
            Console.Error.WriteLine($"[UpdateLoader] {Path.GetFileName(file)} failed: {e.Message}");
        }
    }
}
