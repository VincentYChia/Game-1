using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/npc_db.py — NPCs AND quests, v3 canonical schema
/// (progression/npcs-3.JSON + quests-3.JSON). The v2 legacy adapter path is
/// NOT ported (documented deviation: v3 files are canonical and shipped;
/// contract doc 03 flags v2 as candidate dead code — if only v2 exists this
/// loader logs and loads nothing rather than silently adapting).
/// MergeGeneratedFiles mirrors reload-time overlay; boot does NOT call it.
/// </summary>
public sealed class NpcDatabase
{
    public Dictionary<string, NpcDefinition> Npcs { get; } = new();
    public Dictionary<string, QuestDefinition> Quests { get; } = new();
    public string SourceVersion { get; private set; } = "";
    public string QuestSourceVersion { get; private set; } = "";
    public bool Loaded { get; private set; }

    public void LoadFromFiles(string contentRoot)
    {
        var v3Npc = Path.Combine(contentRoot, "progression", "npcs-3.JSON");
        if (File.Exists(v3Npc))
        {
            var data = JsonNode.Parse(File.ReadAllText(v3Npc))!.AsObject();
            foreach (var node in J.Arr(data, "npcs"))
                if (node is JsonObject n)
                {
                    var npc = BuildNpcFromV3(n);
                    Npcs[npc.NpcId] = npc;
                }
            SourceVersion = "v3";
        }
        else
        {
            Console.Error.WriteLine(
                "[NpcDatabase] npcs-3.JSON not found (v2 fallback not ported — see contract doc 03)");
        }

        var v3Quest = Path.Combine(contentRoot, "progression", "quests-3.JSON");
        if (File.Exists(v3Quest))
        {
            var data = JsonNode.Parse(File.ReadAllText(v3Quest))!.AsObject();
            foreach (var node in J.Arr(data, "quests"))
                if (node is JsonObject q)
                {
                    var quest = BuildQuestFromV3(q);
                    Quests[quest.QuestId] = quest;
                }
            QuestSourceVersion = "v3";
        }
        else
        {
            Console.Error.WriteLine(
                "[NpcDatabase] quests-3.JSON not found (v2 fallback not ported)");
        }

        Loaded = true;
    }

    /// <summary>npc_db.py:410-455 — reload-time overlay of WES-generated files.</summary>
    public void MergeGeneratedFiles(string contentRoot)
    {
        var dir = Path.Combine(contentRoot, "progression");
        foreach (var path in J.GlobSorted(dir, "npcs-generated-*.JSON"))
        {
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            foreach (var node in J.Arr(data, "npcs"))
                if (node is JsonObject n)
                {
                    var npc = BuildNpcFromV3(n);
                    Npcs[npc.NpcId] = npc;
                }
        }
        foreach (var path in J.GlobSorted(dir, "quests-generated-*.JSON"))
        {
            var data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            foreach (var node in J.Arr(data, "quests"))
                if (node is JsonObject q)
                {
                    var quest = BuildQuestFromV3(q, sourceOrigin: "generated");
                    Quests[quest.QuestId] = quest;
                }
        }
    }

    // npc_db.py:19-33
    private static List<string> FlattenSpeechbank(JsonObject speechbank)
    {
        var lines = new List<string>();
        if (speechbank.TryGetPropertyValue("greeting", out var g) && g is JsonArray ga)
            foreach (var l in ga)
                lines.Add(l?.GetValue<string>() ?? "");
        if (speechbank.TryGetPropertyValue("idle_barks", out var b) && b is JsonArray ba)
            foreach (var l in ba)
                lines.Add(l?.GetValue<string>() ?? "");
        return lines;
    }

    // npc_db.py:36-62
    private static NpcDefinition BuildNpcFromV3(JsonObject n)
    {
        var pos = J.Obj(n, "position");
        var speechbank = J.Obj(n, "speechbank");
        var metadata = J.Obj(n, "metadata");
        return new NpcDefinition
        {
            NpcId = J.Str(n, "npc_id"),
            Name = J.Str(n, "name"),
            Title = J.Str(n, "title"),
            Narrative = J.Str(n, "narrative"),
            Personality = J.Node(n, "personality", () => new JsonObject()),
            Locality = J.Node(n, "locality", () => new JsonObject()),
            Faction = J.Node(n, "faction", () => new JsonObject()),
            AffinitySeeds = J.Node(n, "affinity_seeds", () => new JsonObject()),
            Services = J.Node(n, "services", () => new JsonObject()),
            UnlockConditions = J.Node(n, "unlockConditions", () => new JsonObject()),
            Speechbank = speechbank.DeepClone().AsObject(),
            Quests = J.Node(n, "quests", () => new JsonArray()),
            PosX = J.Num(pos, "x", 0.0),
            PosY = J.Num(pos, "y", 0.0),
            PosZ = J.Num(pos, "z", 0.0),
            SpriteColor = J.Node(n, "sprite_color",
                () => new JsonArray(200, 200, 200)),
            InteractionRadius = J.Num(n, "interaction_radius", 3.0),
            Tags = J.Node(metadata, "tags", () => new JsonArray()),
            DialogueLines = FlattenSpeechbank(speechbank),
        };
    }

    // npc_db.py:65-75 — 'or' semantics: empty 'long' falls through to 'short'
    private static string FlattenDescription(JsonNode? desc)
    {
        if (desc is JsonValue v && v.TryGetValue<string>(out var s))
            return s;
        if (desc is JsonObject o)
        {
            var longDesc = J.Str(o, "long", "");
            if (!string.IsNullOrEmpty(longDesc)) return longDesc;
            var shortDesc = J.Str(o, "short", "");
            if (!string.IsNullOrEmpty(shortDesc)) return shortDesc;
        }
        return "";
    }

    // npc_db.py:104-140 (+78-101 objective/reward builders)
    private static QuestDefinition BuildQuestFromV3(JsonObject q, string sourceOrigin = "canonical")
    {
        var title = J.Str(q, "title", J.Str(q, "name", "Untitled Quest"));
        var name = J.Str(q, "name", title);

        // description_full or (falsy → the flat 'description' field)
        JsonNode? descriptionFull = q.TryGetPropertyValue("description_full", out var df)
            ? df : null;
        var descFullObj = descriptionFull as JsonObject;
        JsonNode? descSource = descFullObj is { Count: > 0 }
            ? descFullObj
            : (q.TryGetPropertyValue("description", out var d) ? d : null);
        var description = FlattenDescription(descSource);

        var npcId = J.Str(q, "npc_id", J.Str(q, "given_by", ""));
        var givenBy = J.Str(q, "given_by", npcId);
        var returnTo = J.Str(q, "return_to", givenBy);

        var obj = J.Obj(q, "objectives");
        var rew = J.Obj(q, "rewards");
        var metadata = J.Obj(q, "metadata");

        // npc_db.py:88-101 — rewards normalized to the QuestRewards shape
        var rewardsNode = new JsonObject
        {
            ["experience"] = J.Node(rew, "experience", () => JsonValue.Create(0)!),
            ["gold"] = J.Node(rew, "gold", () => JsonValue.Create(0)!),
            ["health_restore"] = J.Node(rew, "health_restore", () => JsonValue.Create(0)!),
            ["mana_restore"] = J.Node(rew, "mana_restore", () => JsonValue.Create(0)!),
            ["skills"] = J.Node(rew, "skills", () => new JsonArray()),
            ["items"] = J.Node(rew, "items", () => new JsonArray()),
            ["title"] = string.IsNullOrEmpty(J.Str(rew, "title", "")) ? "" : J.Str(rew, "title"),
            ["stat_points"] = J.Node(rew, "stat_points",
                () => J.Node(rew, "statPoints", () => JsonValue.Create(0)!)),
            ["status_effects"] = J.Node(rew, "status_effects", () => new JsonArray()),
            ["buffs"] = J.Node(rew, "buffs", () => new JsonArray()),
        };

        return new QuestDefinition
        {
            QuestId = J.Str(q, "quest_id"),
            Title = title,
            Description = description,
            NpcId = npcId,
            ObjectiveType = J.Str(obj, "objective_type", J.Str(obj, "type", "gather")),
            ObjectiveItems = J.Node(obj, "items", () => new JsonArray()),
            EnemiesKilled = J.Num(obj, "enemies_killed", 0),
            RewardsNode = rewardsNode,
            CompletionDialogue = J.Node(q, "completion_dialogue", () => new JsonArray()),
            Name = name,
            QuestType = J.Str(q, "quest_type", "side"),
            Tier = (long)J.Num(q, "tier", 1),
            GivenBy = givenBy,
            ReturnTo = returnTo,
            DescriptionFull = descFullObj is not null
                ? descFullObj.DeepClone() : new JsonObject(),
            RewardsProse = J.Node(q, "rewards_prose", () => new JsonObject()),
            Requirements = J.Node(q, "requirements", () => new JsonObject()),
            Expiration = J.Node(q, "expiration", () => new JsonObject()),
            Progression = J.Node(q, "progression", () => new JsonObject()),
            WnsThreadId = J.Str(q, "wns_thread_id"),
            Tags = J.Node(metadata, "tags", () => new JsonArray()),
            Metadata = metadata.DeepClone().AsObject(),
            SourceOrigin = sourceOrigin,
        };
    }
}
