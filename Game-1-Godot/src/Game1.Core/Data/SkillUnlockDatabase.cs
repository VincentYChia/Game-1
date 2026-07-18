using System.Text.Json.Nodes;
using Game1.Core.Progression;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/skill_unlock_db.py — the 16th and final P1
/// database, unblocked by the UnlockConditions port. Cost payment/character
/// mutation (UnlockCost.can_afford/pay) arrives with the inventory component;
/// the data + condition evaluation surface is complete here.
/// </summary>
public sealed record UnlockTrigger(string Type, JsonNode? TriggerValue, string Message);

public sealed record UnlockCost(double Gold, JsonNode Materials, double SkillPoints);

public sealed class SkillUnlock
{
    public required string UnlockId { get; init; }
    public required string SkillId { get; init; }
    public required string UnlockMethod { get; init; }
    public required UnlockRequirements Requirements { get; init; }
    public required UnlockTrigger Trigger { get; init; }
    public required UnlockCost Cost { get; init; }
    public string Narrative { get; init; } = "";
    public string Category { get; init; } = "";

    public bool CheckConditions(ICharacterQuery character) =>
        Requirements.Evaluate(character);
}

public sealed class SkillUnlockDatabase
{
    public Dictionary<string, SkillUnlock> Unlocks { get; } = new();
    public Dictionary<string, SkillUnlock> UnlocksBySkill { get; } = new();
    public bool Loaded { get; private set; }

    // skill_unlock_db.py:30-58
    public void LoadFromFile(string filepath)
    {
        if (!File.Exists(filepath)) return;
        JsonObject data;
        try
        {
            data = JsonNode.Parse(File.ReadAllText(filepath))!.AsObject();
        }
        catch
        {
            return;  // warn-and-continue posture
        }
        foreach (var node in J.Arr(data, "skillUnlocks"))
        {
            if (node is not JsonObject u) continue;
            var unlock = Parse(u);
            if (unlock is null) continue;
            Unlocks[unlock.UnlockId] = unlock;
            UnlocksBySkill[unlock.SkillId] = unlock;
        }
        Loaded = true;
    }

    // skill_unlock_db.py:60-117
    private static SkillUnlock? Parse(JsonObject data)
    {
        var unlockId = J.Str(data, "unlockId");
        var skillId = J.Str(data, "skillId");
        var unlockMethod = J.Str(data, "unlockMethod");
        if (unlockId.Length == 0 || skillId.Length == 0 || unlockMethod.Length == 0)
            return null;

        var conditions = data.TryGetPropertyValue("conditions", out var c)
                         && c is JsonArray ca ? (JsonArray)ca.DeepClone() : new JsonArray();
        var requirements = ConditionFactory.CreateRequirementsFromJson(
            new JsonObject { ["conditions"] = conditions });

        var triggerData = J.Obj(data, "unlockTrigger");
        var trigger = new UnlockTrigger(
            J.Str(triggerData, "type", "unknown"),
            J.NodeOrNull(triggerData, "triggerValue"),
            J.Str(triggerData, "message", $"Unlocked {skillId}!"));

        var costData = J.Obj(data, "cost");
        var cost = new UnlockCost(
            J.Num(costData, "gold", 0),
            J.Node(costData, "materials", () => new JsonArray()),
            J.Num(costData, "skillPoints", 0));

        var metadata = J.Obj(data, "metadata");
        return new SkillUnlock
        {
            UnlockId = unlockId,
            SkillId = skillId,
            UnlockMethod = unlockMethod,
            Requirements = requirements,
            Trigger = trigger,
            Cost = cost,
            Narrative = J.Str(metadata, "narrative"),
            Category = J.Str(metadata, "category"),
        };
    }

    public SkillUnlock? GetUnlockForSkill(string skillId) =>
        UnlocksBySkill.GetValueOrDefault(skillId);
}
