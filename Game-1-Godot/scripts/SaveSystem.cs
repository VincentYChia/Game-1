using System.Text.Json.Nodes;
using Game1.Core.Data;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Godot-native save/load (save_load.json contract shape, v1 format).
/// Captures character (level/exp/points/stats/HP/mana/class), inventory
/// slot layout with equipment durability, equipment slots, skills (known
/// levels/exp/cooldowns + hotbar), titles, activity counts, quests, and
/// per-resource depletion. PYTHON PARITY QUIRK PRESERVED: active quests
/// are WRITTEN to the save but deliberately DROPPED on load — only the
/// completed list survives (quest_system.py:564-595). Cross-loading
/// Python .json saves is the P8 boundary, not this format.
/// </summary>
public static class SaveSystem
{
    private static string SavePath(int slot) =>
        ProjectSettings.GlobalizePath($"user://game1_save_{slot}.json");

    public static string Save(CombatWorld combat, PlayerController player,
                              int slot = 1)
    {
        var pc = combat.Pc;
        var skills = combat.SkillMgr;
        var quests = combat.QuestMgr;
        if (pc is null || skills is null || quests is null)
            return "nothing to save";

        var inventory = new JsonArray();
        for (var i = 0; i < pc.Inventory.Slots.Count; i++)
        {
            var stack = pc.Inventory.Slots[i];
            if (stack is null) continue;
            var entry = new JsonObject
            {
                ["slot"] = i,
                ["itemId"] = stack.ItemId,
                ["qty"] = stack.Quantity,
                ["rarity"] = stack.Rarity,
            };
            if (stack.EquipmentData is { } eq)
                entry["durability"] = eq.DurabilityCurrent;
            inventory.Add(entry);
        }

        var equipment = new JsonObject();
        foreach (var (slotName, item) in pc.Equipment.Slots)
            if (item is not null)
                equipment[slotName] = new JsonObject
                {
                    ["itemId"] = item.ItemId,
                    ["durability"] = item.DurabilityCurrent,
                };

        var known = new JsonObject();
        foreach (var (id, ps) in skills.Known)
            known[id] = new JsonObject
            {
                ["level"] = ps.Level,
                ["exp"] = ps.Exp,
                ["cooldown"] = ps.CurrentCooldown,
            };

        var activeQuests = new JsonObject();
        foreach (var (id, q) in quests.ActiveQuests)
        {
            var baselines = new JsonObject();
            foreach (var (item, count) in q.BaselineInventory)
                baselines[item] = count;
            activeQuests[id] = new JsonObject
            {
                ["status"] = q.Status,
                ["baseline_inventory"] = baselines,
                ["baseline_combat_kills"] = q.BaselineCombatKills,
            };
        }

        var activities = new JsonObject();
        foreach (var (type, count) in pc.Activities.ActivityCounts)
            activities[type] = count;

        var resources = new JsonArray();
        for (var i = 0; i < combat.Resources.Count; i++)
        {
            var node = combat.Resources[i].Node;
            if (node.Depleted || node.CurrentHp < node.MaxHp)
                resources.Add(new JsonObject
                {
                    ["index"] = i,
                    ["depleted"] = node.Depleted,
                    ["hp"] = node.CurrentHp,
                });
        }

        var root = new JsonObject
        {
            ["version"] = 1,
            ["seed"] = 12345,
            ["class"] = SelectedClassId ?? "",
            ["player"] = new JsonObject
            {
                ["x"] = player.Position.X,
                ["y"] = player.Position.Y,
                ["z"] = player.Position.Z,
                ["level"] = pc.Leveling.Level,
                ["exp"] = pc.Leveling.CurrentExp,
                ["points"] = pc.Leveling.UnallocatedStatPoints,
                ["health"] = pc.Health,
                ["maxHealth"] = pc.MaxHealthValue,
                ["mana"] = pc.Mana,
                ["str"] = pc.Stats.Strength,
                ["def"] = pc.Stats.Defense,
                ["vit"] = pc.Stats.Vitality,
                ["lck"] = pc.Stats.Luck,
                ["agi"] = pc.Stats.Agility,
                ["int"] = pc.Stats.Intelligence,
            },
            ["inventory"] = inventory,
            ["equipment"] = equipment,
            ["skills"] = new JsonObject
            {
                ["known"] = known,
                ["equipped"] = new JsonArray(
                    skills.Equipped.Select(e => (JsonNode?)e).ToArray()),
            },
            ["titles"] = new JsonArray(pc.Titles.EarnedTitles
                .Select(t => (JsonNode?)t.TitleId).ToArray()),
            ["activities"] = activities,
            ["quests"] = new JsonObject
            {
                ["active"] = activeQuests,   // written; dropped on load (parity)
                ["completed"] = new JsonArray(quests.CompletedQuests
                    .Select(q => (JsonNode?)q).ToArray()),
            },
            ["resources"] = resources,
        };

        var path = SavePath(slot);
        File.WriteAllText(path, root.ToJsonString(
            new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
        return $"saved to slot {slot}";
    }

    /// <summary>Class id chosen this session (ClassSelectScreen sets it).</summary>
    public static string? SelectedClassId;

    public static string Load(CombatWorld combat, PlayerController player,
                              int slot = 1)
    {
        var path = SavePath(slot);
        if (!File.Exists(path)) return "no save found";
        var pc = combat.Pc;
        var skills = combat.SkillMgr;
        var quests = combat.QuestMgr;
        if (pc is null || skills is null || quests is null) return "not ready";

        var root = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
        var p = root["player"]!.AsObject();

        player.Position = new Vector3(
            (float)Num(p["x"]), (float)Num(p["y"]) + 0.5f, (float)Num(p["z"]));
        pc.Leveling.Level = (int)Num(p["level"], 1);
        pc.Leveling.CurrentExp = (long)Num(p["exp"]);
        pc.Leveling.UnallocatedStatPoints = (int)Num(p["points"]);
        pc.Stats.Strength = (int)Num(p["str"]);
        pc.Stats.Defense = (int)Num(p["def"]);
        pc.Stats.Vitality = (int)Num(p["vit"]);
        pc.Stats.Luck = (int)Num(p["lck"]);
        pc.Stats.Agility = (int)Num(p["agi"]);
        pc.Stats.Intelligence = (int)Num(p["int"]);
        pc.MaxHealthValue = Num(p["maxHealth"], 100);
        pc.Health = Num(p["health"], 100);
        pc.Mana = Num(p["mana"], 100);

        // class re-apply
        var classId = root["class"]?.GetValue<string>() ?? "";
        if (classId.Length > 0
            && combat.ClassDb?.Classes.GetValueOrDefault(classId) is { } classDef)
            ClassSelectScreen.ApplyClass(combat, classDef, refill: false);

        // inventory: exact slot layout
        for (var i = 0; i < pc.Inventory.Slots.Count; i++)
            pc.Inventory.Slots[i] = null;
        if (root["inventory"] is JsonArray inv)
            foreach (var node in inv)
            {
                if (node is not JsonObject o) continue;
                var slotIdx = (int)Num(o["slot"]);
                var itemId = o["itemId"]?.GetValue<string>() ?? "";
                var qty = (int)Num(o["qty"], 1);
                var rarity = o["rarity"]?.GetValue<string>() ?? "common";
                EquipmentItem? eq = null;
                if (o["durability"] is not null)
                {
                    eq = combat.EquipDb?.CreateEquipmentFromId(itemId);
                    if (eq is not null) eq.DurabilityCurrent = Num(o["durability"], 100);
                }
                if (slotIdx >= 0 && slotIdx < pc.Inventory.Slots.Count)
                    pc.Inventory.Slots[slotIdx] = new ItemStack(
                        combat.MaterialDb, combat.EquipDb, itemId, qty,
                        equipmentData: eq, rarity: rarity);
            }

        // equipment slots
        foreach (var key in pc.Equipment.Slots.Keys.ToList())
            pc.Equipment.Slots[key] = null;
        if (root["equipment"] is JsonObject eqRoot)
            foreach (var (slotName, node) in eqRoot)
            {
                if (node is not JsonObject o) continue;
                var item = combat.EquipDb?.CreateEquipmentFromId(
                    o["itemId"]?.GetValue<string>() ?? "");
                if (item is null) continue;
                item.DurabilityCurrent = Num(o["durability"], 100);
                pc.Equipment.Slots[slotName] = item;
            }

        // skills
        skills.Known.Clear();
        for (var i = 0; i < skills.Equipped.Length; i++) skills.Equipped[i] = null;
        if (root["skills"]?["known"] is JsonObject knownRoot)
            foreach (var (id, node) in knownRoot)
            {
                if (node is not JsonObject o) continue;
                skills.Learn(id, skipChecks: true);
                if (skills.Known.TryGetValue(id, out var ps))
                {
                    ps.Level = (int)Num(o["level"], 1);
                    ps.Exp = Num(o["exp"]);
                    ps.CurrentCooldown = Num(o["cooldown"]);
                }
            }
        if (root["skills"]?["equipped"] is JsonArray equippedArr)
            for (var i = 0; i < equippedArr.Count && i < skills.Equipped.Length; i++)
                if (equippedArr[i]?.GetValue<string>() is { Length: > 0 } sid)
                    skills.Equip(sid, i);

        // titles
        pc.Titles.EarnedTitles.Clear();
        if (root["titles"] is JsonArray titles && combat.TitleDb is { } titleDb)
            foreach (var t in titles)
                if (t?.GetValue<string>() is { } tid
                    && titleDb.Titles.GetValueOrDefault(tid) is { } tdef)
                    pc.Titles.EarnedTitles.Add(tdef);

        // activities
        pc.Activities.ActivityCounts.Clear();
        if (root["activities"] is JsonObject acts)
            foreach (var (type, v) in acts)
                pc.Activities.ActivityCounts[type] = (int)Num(v);

        // quests: PYTHON PARITY — active quests in the save are dropped;
        // only the completed list is restored
        quests.ActiveQuests.Clear();
        quests.CompletedQuests.Clear();
        if (root["quests"]?["completed"] is JsonArray completed)
            foreach (var q in completed)
                if (q?.GetValue<string>() is { } qid)
                    quests.CompletedQuests.Add(qid);

        // resource depletion
        if (root["resources"] is JsonArray resArr)
            foreach (var node in resArr)
            {
                if (node is not JsonObject o) continue;
                var idx = (int)Num(o["index"], -1);
                if (idx < 0 || idx >= combat.Resources.Count) continue;
                var res = combat.Resources[idx].Node;
                res.Depleted = o["depleted"]?.GetValue<bool>() ?? false;
                res.CurrentHp = Num(o["hp"], res.MaxHp);
            }

        return $"loaded slot {slot}";
    }

    private static double Num(JsonNode? node, double fallback = 0)
    {
        if (node is JsonValue v)
        {
            if (v.TryGetValue<double>(out var d)) return d;
            if (v.TryGetValue<int>(out var i)) return i;
            if (v.TryGetValue<long>(out var l)) return l;
        }
        return fallback;
    }
}
