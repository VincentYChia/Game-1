using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

public class EquipmentManagerTests
{
    private static readonly JsonElement S = GoldenFixture.Load("db_parity/status_effects.json")
        .GetProperty("scenarios").GetProperty("equipment_manager");

    private sealed class Char : ICharacterQuery
    {
        public int Level { get; init; } = 30;
        public int GetStat(string statName) => 0;
        public int GetActivityCount(string activityType) => 0;
        public bool HasTitle(string titleId) => false;
        public bool KnowsSkill(string skillId) => false;
        public bool IsQuestCompleted(string questId) => false;
        public string? CurrentClassId => null;
        public double? GetStatTrackerValue(string statPath) => null;
    }

    private static EquipmentItem Weapon(string id, string handType,
        string itemType = "weapon", string slot = "mainHand",
        (int, int)? damage = null, double range = 1.0,
        List<string>? tags = null, JsonObject? bonuses = null,
        JsonObject? reqs = null)
    {
        var it = new EquipmentItem
        {
            ItemId = id, Name = id, Tier = 1, Rarity = "common", Slot = slot,
            Damage = damage ?? (10, 20), HandType = handType, ItemType = itemType,
            Range = range, Tags = tags ?? new List<string>(),
        };
        if (bonuses is not null) it.Bonuses = bonuses;
        if (reqs is not null) it.Requirements = reqs;
        return it;
    }

    private static EquipmentItem Armor(string id, string slot, int defense) => new()
    {
        ItemId = id, Name = id, Tier = 1, Rarity = "common", Slot = slot,
        Damage = (0, 0), Defense = defense, ItemType = "armor",
    };

    [Fact]
    public void HandTypeRules_MatchPython()
    {
        var ch = new Char();
        var expected = S.GetProperty("hand_rules");
        var em = new EquipmentManager();

        void Check(string key, string actual) =>
            Assert.Equal(expected.GetProperty(key).GetString(), actual);

        Check("equip_2h", em.Equip(Weapon("two_hander", "2H"), ch).Reason);
        Check("offhand_vs_2h", em.Equip(Weapon("dagger", "1H", slot: "offHand"), ch).Reason);
        em.Unequip("mainHand");
        Check("equip_default", em.Equip(Weapon("plain_sword", "default"), ch).Reason);
        Check("shield_vs_default",
            em.Equip(Weapon("shield_item", "default", "shield", "offHand"), ch).Reason);
        em.Unequip("offHand");
        Check("oneh_vs_default", em.Equip(Weapon("dagger2", "1H", slot: "offHand"), ch).Reason);
        em.Unequip("mainHand");
        Check("equip_versatile", em.Equip(Weapon("versatile_spear", "versatile"), ch).Reason);
        Check("oneh_vs_versatile", em.Equip(Weapon("dagger3", "1H", slot: "offHand"), ch).Reason);
        em.Unequip("offHand");
        Check("versatile_vs_versatile",
            em.Equip(Weapon("versatile2", "versatile", slot: "offHand"), ch).Reason);

        var em2 = new EquipmentManager();
        Check("offhand_alone", em2.Equip(Weapon("solo_off", "1H", slot: "offHand"), ch).Reason);
        Check("invalid_slot", em2.Equip(Weapon("bad_slot", "1H", slot: "ring"), ch).Reason);
        Check("requirements_fail", em2.Equip(
            Weapon("too_strong", "1H", reqs: new JsonObject { ["level"] = 99 }),
            new Char { Level = 1 }).Reason);
    }

    [Fact]
    public void Aggregations_MatchPython()
    {
        var ch = new Char();
        var q = S.GetProperty("queries");

        var em3 = new EquipmentManager();
        foreach (var (slot, d) in new[]
                 {
                     ("helmet", 10), ("chestplate", 25), ("leggings", 18),
                     ("boots", 8), ("gauntlets", 6),
                 })
            em3.Equip(Armor($"a_{slot}", slot, d), ch);
        em3.Slots["chestplate"]!.DurabilityCurrent = 10;
        Assert.Equal(q.GetProperty("total_defense").GetInt32(), em3.GetTotalDefense());

        var bare = new EquipmentManager();
        var unarmed = q.GetProperty("unarmed_damage");
        Assert.Equal((unarmed[0].GetInt32(), unarmed[1].GetInt32()), bare.GetWeaponDamage());
        var noOff = q.GetProperty("no_offhand_damage");
        Assert.Equal((noOff[0].GetInt32(), noOff[1].GetInt32()), bare.GetWeaponDamage("offHand"));
        GoldenFixture.AssertClose(q.GetProperty("unarmed_range").GetDouble(),
            bare.GetWeaponRange(), "unarmed_range");
        GoldenFixture.AssertClose(q.GetProperty("no_offhand_range").GetDouble(),
            bare.GetWeaponRange("offHand"), "no_offhand_range");

        var em4 = new EquipmentManager();
        em4.Equip(Weapon("reach_spear", "2H", range: 2.5,
            tags: new List<string> { "reach" },
            bonuses: new JsonObject { ["crit_chance"] = 0.05 }), ch);
        em4.Equip(Armor("lucky_helm", "helmet", 5), ch);
        em4.Slots["helmet"]!.Bonuses = new JsonObject
        { ["crit_chance"] = 0.02, ["max_health"] = 10 };

        var wd = q.GetProperty("weapon_damage");
        Assert.Equal((wd[0].GetInt32(), wd[1].GetInt32()), em4.GetWeaponDamage());
        GoldenFixture.AssertClose(q.GetProperty("weapon_range_with_reach").GetDouble(),
            em4.GetWeaponRange(), "range_with_reach");
        GoldenFixture.AssertClose(q.GetProperty("attack_speed_default").GetDouble(),
            em4.GetWeaponAttackSpeed("offHand"), "attack_speed_default");

        var bonusDiffs = JsonTreeComparer.Diff(q.GetProperty("stat_bonuses"),
            new JsonObject(em4.GetStatBonuses()
                .ToDictionary(kv => kv.Key, kv => (JsonNode?)kv.Value)));
        Assert.True(bonusDiffs.Count == 0,
            "stat_bonuses: " + string.Join("; ", bonusDiffs.Take(5)));

        Assert.Equal(q.GetProperty("is_equipped").GetBoolean(), em4.IsEquipped("reach_spear"));
        var unequipped = em4.Unequip("mainHand");
        Assert.Equal(q.GetProperty("unequip_returns").GetString(), unequipped?.ItemId);
        Assert.Equal(q.GetProperty("is_equipped_after").GetBoolean(),
            em4.IsEquipped("reach_spear"));
    }
}
