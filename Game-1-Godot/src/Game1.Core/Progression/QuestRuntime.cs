using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// Port of systems/quest_system.py + the npc_system.py dialogue-state layer
/// (contract npc_quest.json). Preserved semantics: baseline-delta progress
/// (items owned before accepting don't count; spending counted items
/// reduces progress), one-shot quests (isRepeatable unenforced),
/// requirements loaded but NOT enforced, only gather+combat completable
/// (others False forever), turn-in order check → consume → grant → move,
/// gold/stat_points rewards are hasattr-dead no-ops (character has neither
/// field — preserved), item rewards on full inventory permanently lost.
/// </summary>
public sealed class ActiveQuest
{
    public required QuestDefinition Def { get; init; }
    public string Status { get; set; } = "in_progress";
    public Dictionary<string, int> BaselineInventory { get; } = new();
    public int BaselineCombatKills { get; set; }
}

/// <summary>Per-NPC dialogue cycling state (npc_system.py:34-108): greeting
/// once per conversation, then idle barks; indices persist across
/// conversations so lines rotate.</summary>
public sealed class NpcDialogueState
{
    public bool HasGreeted;
    public int GreetingIndex;
    public int IdleIndex;

    public void ResetConversation() => HasGreeted = false;   // indices persist

    public string GetNextLine(JsonObject speechbank)
    {
        var greetings = speechbank["greeting"] as JsonArray;
        var idles = speechbank["idle_barks"] as JsonArray;
        if (!HasGreeted && greetings is { Count: > 0 })
        {
            var line = greetings[GreetingIndex % greetings.Count]
                ?.GetValue<string>() ?? "...";
            GreetingIndex++;
            HasGreeted = true;
            return line;
        }
        if (idles is { Count: > 0 })
        {
            var line = idles[IdleIndex % idles.Count]?.GetValue<string>() ?? "...";
            IdleIndex++;
            return line;
        }
        return "...";
    }

    public static string? QuestOffer(JsonObject speechbank) =>
        NonEmpty(speechbank["quest_offer"]);
    public static string? QuestComplete(JsonObject speechbank) =>
        NonEmpty(speechbank["quest_complete"]);

    private static string? NonEmpty(JsonNode? node) =>
        node is JsonValue v && v.TryGetValue<string>(out var s)
        && !string.IsNullOrWhiteSpace(s) ? s : null;
}

public sealed class QuestManager
{
    private readonly PlayerCharacter _ch;
    private readonly TitleDatabase _titles;
    private readonly SkillManager? _skills;

    public Dictionary<string, ActiveQuest> ActiveQuests { get; } = new();
    public List<string> CompletedQuests { get; } = new();

    public QuestManager(PlayerCharacter ch, TitleDatabase titles,
                        SkillManager? skills)
    {
        _ch = ch;
        _titles = titles;
        _skills = skills;
    }

    // quest_system.py:273-299 — one-shot; baselines snapshotted at accept
    public bool StartQuest(QuestDefinition def)
    {
        if (ActiveQuests.ContainsKey(def.QuestId)
            || CompletedQuests.Contains(def.QuestId))
            return false;
        var quest = new ActiveQuest { Def = def };
        if (def.ObjectiveType == "gather" && def.ObjectiveItems is JsonArray items)
            foreach (var item in items)
                if (item is JsonObject o
                    && o["item_id"]?.GetValue<string>() is { } itemId)
                    quest.BaselineInventory[itemId] =
                        _ch.Inventory.GetItemCount(itemId);
        if (def.ObjectiveType == "combat")
            quest.BaselineCombatKills = _ch.Activities.GetCount("combat");
        ActiveQuests[def.QuestId] = quest;
        return true;
    }

    // quest_system.py:67-94 — DELTA since accept; unknown types never complete
    public bool CheckCompletion(ActiveQuest quest)
    {
        var def = quest.Def;
        switch (def.ObjectiveType)
        {
            case "gather":
                if (def.ObjectiveItems is not JsonArray items) return false;
                foreach (var item in items)
                {
                    if (item is not JsonObject o) continue;
                    var itemId = o["item_id"]?.GetValue<string>() ?? "";
                    var required = ItemQty(o);
                    var baseline = quest.BaselineInventory.GetValueOrDefault(itemId);
                    if (_ch.Inventory.GetItemCount(itemId) - baseline < required)
                        return false;
                }
                return true;
            case "combat":
                return _ch.Activities.GetCount("combat")
                       - quest.BaselineCombatKills >= (int)quest.Def.EnemiesKilled;
            default:
                return false;
        }
    }

    /// <summary>(gathered, required) pairs for the quest-log display —
    /// max(0, now - baseline) (quest_log_overlay.py:214-244).</summary>
    public List<(string Label, int Have, int Need)> Progress(ActiveQuest quest)
    {
        var result = new List<(string, int, int)>();
        var def = quest.Def;
        if (def.ObjectiveType == "gather" && def.ObjectiveItems is JsonArray items)
        {
            foreach (var item in items)
            {
                if (item is not JsonObject o) continue;
                var itemId = o["item_id"]?.GetValue<string>() ?? "";
                var baseline = quest.BaselineInventory.GetValueOrDefault(itemId);
                var have = Math.Max(0, _ch.Inventory.GetItemCount(itemId) - baseline);
                result.Add((itemId, have, ItemQty(o)));
            }
        }
        else if (def.ObjectiveType == "combat")
        {
            var kills = Math.Max(0, _ch.Activities.GetCount("combat")
                                    - quest.BaselineCombatKills);
            result.Add(("kills", kills, (int)def.EnemiesKilled));
        }
        return result;
    }

    /// <summary>Turn-in (quest_system.py:337-426): check → consume →
    /// grant (fixed order) → move to completed. Returns null when not
    /// completable, else the reward messages.</summary>
    public List<string>? CompleteQuest(string questId)
    {
        if (!ActiveQuests.TryGetValue(questId, out var quest)) return null;
        if (!CheckCompletion(quest)) return null;

        // consume_items: exactly the REQUIRED qty, front-to-back scan
        if (quest.Def.ObjectiveType == "gather"
            && quest.Def.ObjectiveItems is JsonArray items)
            foreach (var item in items)
            {
                if (item is not JsonObject o) continue;
                var itemId = o["item_id"]?.GetValue<string>() ?? "";
                if (!_ch.Inventory.RemoveItem(itemId, ItemQty(o)))
                    return null;   // failed consume aborts turn-in
            }

        var messages = GrantRewards(quest.Def.RewardsNode);
        quest.Status = "turned_in";
        CompletedQuests.Add(questId);
        ActiveQuests.Remove(questId);
        return messages;
    }

    public bool AbandonQuest(string questId) =>
        ActiveQuests.Remove(questId);   // no rollback (quest_system.py:538-558)

    // quest_system.py:121-250 — fixed grant order
    private List<string> GrantRewards(JsonObject rewards)
    {
        var messages = new List<string>();

        var exp = (int)Num(rewards["experience"]);
        if (exp > 0)
        {
            var before = _ch.Leveling.Level;
            _ch.Leveling.AddExp(exp);
            messages.Add($"+{exp} XP");
            if (_ch.Leveling.Level > before)
                messages.Add($"Level up! Now level {_ch.Leveling.Level}");
        }

        var hp = Num(rewards["health_restore"]);
        if (hp > 0)
        {
            _ch.Health = Math.Min(_ch.MaxHealthValue, _ch.Health + hp);
            messages.Add($"+{hp:F0} HP");
        }
        var mana = Num(rewards["mana_restore"]);
        if (mana > 0)
        {
            _ch.Mana = Math.Min(_ch.MaxMana, _ch.Mana + mana);
            messages.Add($"+{mana:F0} Mana");
        }

        if (rewards["skills"] is JsonArray skills)
            foreach (var s in skills)
                if (s?.GetValue<string>() is { Length: > 0 } skillId
                    && _skills?.Learn(skillId, skipChecks: true) == true)
                    messages.Add($"Learned skill: {skillId}");

        if (rewards["items"] is JsonArray rewardItems)
            foreach (var item in rewardItems)
            {
                if (item is not JsonObject o) continue;
                var itemId = o["item_id"]?.GetValue<string>() ?? "";
                var qty = ItemQty(o);
                if (itemId.Length == 0 || qty <= 0) continue;
                if (_ch.Inventory.AddItem(itemId, qty))
                    messages.Add($"+{qty}x {itemId}");
                else
                    messages.Add($"Inventory full! Lost {qty}x {itemId}");
            }

        // gold + stat_points: hasattr-dead in Python (character has neither
        // field) — preserved as no-ops per contract hazard

        var titleId = rewards["title"]?.GetValue<string>() ?? "";
        if (titleId.Length > 0
            && _titles.Titles.TryGetValue(titleId, out var titleDef)
            && _ch.Titles.EarnedTitles.All(t => t.TitleId != titleId))
        {
            _ch.Titles.EarnedTitles.Add(titleDef);
            messages.Add($"Earned title: {titleDef.Name}");
        }

        // status_effects / buffs rewards: logged TODOs in Python, not applied
        return messages;
    }

    private static int ItemQty(JsonObject o) =>
        (int)Num(o["quantity"] is null ? o["qty"] : o["quantity"], 1);

    private static double Num(JsonNode? node, double fallback = 0)
    {
        if (node is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return d;
            if (v.TryGetValue<int>(out var i)) return i;
        }
        return fallback;
    }
}
