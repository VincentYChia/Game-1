using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/skill_db.py. Sacred glob Skills/skills-skills-*.JSON
/// (skipping any name containing "generated"), then skills-generated-*.JSON
/// overlay — generated wins on id collision. Translation enum lookups
/// delegate to TranslationDatabase (single source of truth, §15 trap 5).
/// </summary>
public sealed class SkillDatabase
{
    public Dictionary<string, SkillDefinition> Skills { get; } = new();
    public bool Loaded { get; private set; }

    public const string SacredDir = "Skills";
    public const string SacredGlob = "skills-skills-*.JSON";
    public const string GeneratedGlob = "skills-generated-*.JSON";

    public void LoadFromFiles(string contentRoot)
    {
        Skills.Clear();
        var dir = Path.Combine(contentRoot, SacredDir);
        foreach (var path in J.GlobSorted(dir, SacredGlob))
        {
            if (Path.GetFileName(path).ToLowerInvariant().Contains("generated"))
                continue;
            LoadFromFile(path);
        }
        foreach (var path in J.GlobSorted(dir, GeneratedGlob))
            LoadFromFile(path);
        Loaded = Skills.Count > 0;
    }

    // skill_db.py:125-200
    public void LoadFromFile(string filepath)
    {
        var data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        foreach (var node in J.Arr(data, "skills"))
        {
            if (node is not JsonObject s) continue;

            var effect = J.Obj(s, "effect");
            var cost = J.Obj(s, "cost");
            var evo = J.Obj(s, "evolution");
            var req = J.Obj(s, "requirements");

            var skillId = J.Str(s, "skillId");
            var iconPath = J.Str(s, "iconPath", "");
            if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(skillId))
                iconPath = $"skills/{skillId}.png";

            var nextSkillId = J.Str(evo, "nextSkillId", "");
            var hasNext = evo.TryGetPropertyValue("nextSkillId", out var nextNode)
                          && nextNode is not null;

            var skill = new SkillDefinition
            {
                SkillId = skillId,
                Name = J.Str(s, "name"),
                Tier = J.Num(s, "tier", 1),
                Rarity = J.Str(s, "rarity", "common"),
                Categories = J.Node(s, "categories", () => new JsonArray()),
                Description = J.Str(s, "description"),
                Narrative = J.Str(s, "narrative"),
                Tags = J.Node(s, "tags", () => new JsonArray()),
                EffectType = J.Str(effect, "type"),
                EffectCategory = J.Str(effect, "category"),
                EffectMagnitude = J.Str(effect, "magnitude"),
                EffectTarget = J.Str(effect, "target", "self"),
                EffectDuration = J.Str(effect, "duration", "instant"),
                AdditionalEffects = J.Node(effect, "additionalEffects", () => new JsonArray()),
                CostMana = J.Node(cost, "mana", () => JsonValue.Create("moderate")!),
                CostCooldown = J.Node(cost, "cooldown", () => JsonValue.Create("moderate")!),
                CanEvolve = J.Bool(evo, "canEvolve", false),
                NextSkillId = hasNext ? nextSkillId : null,
                EvolutionRequirement = J.Str(evo, "requirement"),
                RequiredCharacterLevel = J.Num(req, "characterLevel", 1),
                RequiredStats = J.Node(req, "stats", () => new JsonObject()),
                RequiredTitles = J.Node(req, "titles", () => new JsonArray()),
                IconPath = string.IsNullOrEmpty(iconPath) ? null : iconPath,
                CombatTags = J.Node(s, "combatTags", () => new JsonArray()),
                CombatParams = J.Node(s, "combatParams", () => new JsonObject()),
            };
            Skills[skill.SkillId] = skill;
        }
        Loaded = true;
    }

    public SkillDefinition? GetSkill(string skillId) => Skills.GetValueOrDefault(skillId);
}
