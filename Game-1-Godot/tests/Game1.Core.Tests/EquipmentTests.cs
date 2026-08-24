using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Combat;
using Game1.Core.Crafting;
using Game1.Core.Data;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

public class EquipmentTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/equipment_items.json");

    private static EquipmentItem Synth(
        (int, int)? damage = null, int defense = 0, int cur = 100, int max = 100,
        string itemType = "weapon", double efficiency = 1.0,
        JsonObject? bonuses = null, string slot = "mainHand")
    {
        var it = new EquipmentItem
        {
            ItemId = "synth", Name = "Synth", Tier = 1, Rarity = "common",
            Slot = slot, Damage = damage ?? (10, 20), Defense = defense,
            DurabilityCurrent = cur, DurabilityMax = max, ItemType = itemType,
        };
        it.Efficiency = efficiency;
        if (bonuses is not null) it.Bonuses = bonuses;
        return it;
    }

    [Fact]
    public void Materialization_MatchesPython_All38Items()
    {
        var db = BootedDatabases.All.Value.Equipment;
        var expected = G.GetProperty("items");
        var count = 0;
        foreach (var e in expected.EnumerateObject())
        {
            count++;
            var item = db.CreateEquipmentFromId(e.Name);
            Assert.NotNull(item);
            var diffs = JsonTreeComparer.Diff(e.Value, item!.ToParityNode());
            Assert.True(diffs.Count == 0,
                $"item[{e.Name}]: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(15)));
        }
        Assert.Equal(G.GetProperty("count").GetInt32(), count);
    }

    [Fact]
    public void EffectivenessCurve_And_Urgency_MatchPython()
    {
        foreach (var e in G.GetProperty("effectiveness").EnumerateObject())
        {
            var parts = e.Name.Split('/');
            var it = Synth(cur: int.Parse(parts[0]), max: int.Parse(parts[1]));
            GoldenFixture.AssertClose(e.Value.GetDouble(), it.GetEffectiveness(),
                $"effectiveness[{e.Name}]");
        }
        foreach (var e in G.GetProperty("repair_urgency").EnumerateObject())
        {
            var parts = e.Name.Split('/');
            var it = Synth(cur: int.Parse(parts[0]), max: int.Parse(parts[1]));
            Assert.Equal(e.Value.GetString(), it.GetRepairUrgency());
        }
    }

    [Fact]
    public void Repair_MatchesPython()
    {
        var rep = G.GetProperty("repair");

        var a = Synth(cur: 10);
        Assert.Equal(rep.GetProperty("amount_25").GetProperty("restored").GetInt32(),
            a.Repair(amount: 25));
        Assert.Equal(rep.GetProperty("amount_25").GetProperty("now").GetInt32(),
            a.DurabilityCurrent);

        var p = Synth(cur: 10);
        Assert.Equal(rep.GetProperty("percent_50").GetProperty("restored").GetInt32(),
            p.Repair(percent: 0.5));
        Assert.Equal(rep.GetProperty("percent_50").GetProperty("now").GetInt32(),
            p.DurabilityCurrent);

        var f = Synth(cur: 10);
        Assert.Equal(rep.GetProperty("full").GetProperty("restored").GetInt32(), f.Repair());
        Assert.Equal(rep.GetProperty("full").GetProperty("now").GetInt32(), f.DurabilityCurrent);
    }

    private static JsonObject Ench(string id, string type, double value)
    {
        return new JsonObject
        {
            ["enchantment_id"] = id, ["name"] = id,
            ["effect"] = new JsonObject { ["type"] = type, ["value"] = value },
        };
    }

    [Fact]
    public void ActualDamage_And_Defense_MatchPython()
    {
        var d = G.GetProperty("actual_damage");

        void AssertDamage(string key, EquipmentItem it)
        {
            var expected = d.GetProperty(key);
            var (min, max) = it.GetActualDamage();
            Assert.True(expected[0].GetInt32() == min && expected[1].GetInt32() == max,
                $"actual_damage[{key}]: expected {expected.GetRawText()}, got ({min},{max})");
        }

        AssertDamage("plain", Synth());
        AssertDamage("crafted_mult",
            Synth(bonuses: new JsonObject { ["damage_multiplier"] = 0.25 }));
        AssertDamage("tool_efficiency", Synth(itemType: "tool", efficiency: 1.2));
        AssertDamage("weapon_efficiency_ignored", Synth(itemType: "weapon", efficiency: 1.2));
        var enchItem = Synth();
        enchItem.Enchantments.Add(Ench("sharpness_1", "damage_multiplier", 0.15));
        AssertDamage("ench_mult", enchItem);
        AssertDamage("worn_30", Synth(cur: 30));
        AssertDamage("broken_0", Synth(cur: 0));
        var stacked = Synth(cur: 30, itemType: "tool", efficiency: 1.2,
            bonuses: new JsonObject { ["damage_multiplier"] = 0.25 });
        stacked.Enchantments.Add(Ench("sharpness_1", "damage_multiplier", 0.15));
        AssertDamage("stacked", stacked);

        var def = G.GetProperty("defense");
        Assert.Equal(def.GetProperty("plain").GetInt32(),
            Synth(damage: (0, 0), defense: 50, slot: "chestplate", itemType: "armor")
                .GetDefenseWithEnchantments());
        var mixed = Synth(damage: (0, 0), defense: 50, slot: "chestplate", itemType: "armor",
            bonuses: new JsonObject { ["defense_multiplier"] = -0.1 });
        mixed.Enchantments.Add(Ench("protection_1", "defense_multiplier", 0.2));
        Assert.Equal(def.GetProperty("crafted_and_ench").GetInt32(),
            mixed.GetDefenseWithEnchantments());
        Assert.Equal(def.GetProperty("worn_10").GetInt32(),
            Synth(damage: (0, 0), defense: 50, slot: "chestplate", itemType: "armor", cur: 10)
                .GetDefenseWithEnchantments());
    }

    [Fact]
    public void EnchantSequence_FamilyTierConflictRules_MatchPython()
    {
        var item = Synth();
        foreach (var step in G.GetProperty("enchant_sequence").EnumerateArray())
        {
            var id = step.GetProperty("apply").GetString()!;
            JsonObject effect = id switch
            {
                "sharpness_2" => new JsonObject { ["type"] = "damage_multiplier", ["value"] = 0.2 },
                "sharpness_1" => new JsonObject { ["type"] = "damage_multiplier", ["value"] = 0.1 },
                "sharpness_3" => new JsonObject { ["type"] = "damage_multiplier", ["value"] = 0.3 },
                "frost_1" => new JsonObject
                {
                    ["type"] = "slow", ["value"] = 0.3,
                    ["conflictsWith"] = new JsonArray("sharpness_3"),
                },
                _ => throw new InvalidOperationException(id),
            };
            var name = id switch
            {
                "sharpness_2" => "Sharpness II", "sharpness_1" => "Sharpness I",
                "sharpness_3" => "Sharpness III", _ => "Frost I",
            };
            var (ok, reason) = item.ApplyEnchantment(id, name, effect);
            Assert.Equal(step.GetProperty("ok").GetBoolean(), ok);
            Assert.Equal(step.GetProperty("reason").GetString(), reason);
            var now = item.Enchantments.Select(e => e["enchantment_id"]!.GetValue<string>()).ToList();
            var expectedNow = step.GetProperty("now").EnumerateArray()
                .Select(x => x.GetString()!).ToList();
            Assert.Equal(expectedNow, now);
        }
    }

    [Fact]
    public void ItemTypeGrid_And_CanEquip_MatchPython()
    {
        foreach (var row in G.GetProperty("item_type_grid").EnumerateArray())
        {
            var it = Synth(
                damage: (row.GetProperty("damage")[0].GetInt32(),
                         row.GetProperty("damage")[1].GetInt32()),
                slot: row.GetProperty("slot").GetString()!,
                itemType: row.GetProperty("item_type_in").GetString()!);
            Assert.Equal(row.GetProperty("resolved").GetString(), it.ResolveItemType());
        }

        var stub = new FixedCharacter(level: 4, strength: 8, agility: 3);
        var reqsByCase = new Dictionary<string, JsonObject>
        {
            ["level_fail"] = new() { ["level"] = 5 },
            ["level_ok"] = new() { ["level"] = 4 },
            ["stat_fail"] = new() { ["stats"] = new JsonObject { ["STR"] = 10 } },
            ["stat_ok"] = new() { ["stats"] = new JsonObject { ["str"] = 8 } },
            ["dex_alias"] = new() { ["stats"] = new JsonObject { ["DEX"] = 5 } },
            ["combined_fail"] = new()
            { ["level"] = 3, ["stats"] = new JsonObject { ["AGI"] = 4 } },
            ["empty"] = new(),
        };
        foreach (var e in G.GetProperty("can_equip").EnumerateObject())
        {
            var it = Synth();
            it.Requirements = reqsByCase[e.Name];
            var (ok, reason) = it.CanEquip(stub);
            Assert.True(e.Value.GetProperty("ok").GetBoolean() == ok,
                $"can_equip[{e.Name}].ok");
            Assert.Equal(e.Value.GetProperty("reason").GetString(), reason);
        }
    }

    [Fact]
    public void TagModifiers_SlotInference_EnchantRules_MatchPython()
    {
        foreach (var e in G.GetProperty("weapon_tag_modifiers").EnumerateObject())
        {
            var tags = e.Name == "none" ? Array.Empty<string>() : e.Name.Split('-');
            var v = e.Value;
            GoldenFixture.AssertClose(v.GetProperty("dmg_no_off").GetDouble(),
                WeaponTagModifiers.GetDamageMultiplier(tags, false), $"{e.Name}.dmg_no_off");
            GoldenFixture.AssertClose(v.GetProperty("dmg_off").GetDouble(),
                WeaponTagModifiers.GetDamageMultiplier(tags, true), $"{e.Name}.dmg_off");
            GoldenFixture.AssertClose(v.GetProperty("speed").GetDouble(),
                WeaponTagModifiers.GetAttackSpeedBonus(tags), $"{e.Name}.speed");
            GoldenFixture.AssertClose(v.GetProperty("crit").GetDouble(),
                WeaponTagModifiers.GetCritChanceBonus(tags), $"{e.Name}.crit");
            GoldenFixture.AssertClose(v.GetProperty("range").GetDouble(),
                WeaponTagModifiers.GetRangeBonus(tags), $"{e.Name}.range");
            GoldenFixture.AssertClose(v.GetProperty("pen").GetDouble(),
                WeaponTagModifiers.GetArmorPenetration(tags), $"{e.Name}.pen");
            GoldenFixture.AssertClose(v.GetProperty("vs_armored").GetDouble(),
                WeaponTagModifiers.GetDamageVsArmoredBonus(tags), $"{e.Name}.vs_armored");
            Assert.Equal(v.GetProperty("cleaving").GetBoolean(),
                WeaponTagModifiers.HasCleaving(tags));
        }

        foreach (var e in G.GetProperty("slot_inference").EnumerateObject())
        {
            var tags = e.Name == "none" ? Array.Empty<string>() : e.Name.Split('-');
            var expected = e.Value.ValueKind == JsonValueKind.Null ? null : e.Value.GetString();
            Assert.Equal(expected, SmithingTagProcessor.GetEquipmentSlot(tags));
        }

        foreach (var e in G.GetProperty("enchant_applicability").EnumerateObject())
        {
            var parts = e.Name.Split('|');
            var tags = parts[0] == "none" ? Array.Empty<string>() : parts[0].Split('-');
            var (ok, reason) = EnchantingTagProcessor.CanApplyToItem(tags, parts[1]);
            Assert.True(e.Value.GetProperty("ok").GetBoolean() == ok, $"ench[{e.Name}].ok");
            Assert.Equal(e.Value.GetProperty("reason").GetString(), reason);
        }
    }

    private sealed class FixedCharacter : ICharacterQuery
    {
        private readonly int _level, _strength, _agility;
        public FixedCharacter(int level, int strength, int agility)
        { _level = level; _strength = strength; _agility = agility; }
        public int Level => _level;
        public int GetStat(string statName) => statName switch
        {
            "strength" => _strength, "agility" => _agility, _ => 0,
        };
        public int GetActivityCount(string activityType) => 0;
        public bool HasTitle(string titleId) => false;
        public bool KnowsSkill(string skillId) => false;
        public bool IsQuestCompleted(string questId) => false;
        public string? CurrentClassId => null;
        public double? GetStatTrackerValue(string statPath) => null;
    }
}
