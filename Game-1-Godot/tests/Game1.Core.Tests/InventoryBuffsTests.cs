using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core.Data;
using Game1.Core.Progression;
using Xunit;

namespace Game1.Core.Tests;

public class InventoryBuffsTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/inventory_buffs.json");

    private static string MatId => G.GetProperty("material_id").GetString()!;
    private static int MatStack => G.GetProperty("material_max_stack").GetInt32();
    private static string EquipId => G.GetProperty("equipment_id").GetString()!;

    private static Inventory NewInv(int slots) =>
        new(BootedDatabases.All.Value.Materials, BootedDatabases.All.Value.Equipment, slots);

    private static JsonNode SlotsState(Inventory inv)
    {
        var arr = new JsonArray();
        foreach (var s in inv.Slots)
        {
            if (s is null) { arr.Add((JsonNode?)null); continue; }
            arr.Add(new JsonObject
            {
                ["item_id"] = s.ItemId,
                ["quantity"] = s.Quantity,
                ["max_stack"] = s.MaxStack,
                ["rarity"] = s.Rarity,
                ["has_equipment_data"] = s.EquipmentData is not null,
                ["crafted_stats"] = s.CraftedStats?.DeepClone(),
            });
        }
        return arr;
    }

    private static void AssertScenario(string name, Inventory inv, bool? ok = null,
                                       int? count = null)
    {
        var expected = G.GetProperty("inventory").GetProperty(name);
        if (ok is not null)
            Assert.True(expected.GetProperty("ok").GetBoolean() == ok, $"{name}.ok");
        if (count is not null)
            Assert.Equal(expected.GetProperty("count").GetInt32(), count);
        var diffs = JsonTreeComparer.Diff(expected.GetProperty("slots"), SlotsState(inv));
        Assert.True(diffs.Count == 0,
            $"{name}.slots: " + string.Join("; ", diffs.Take(10)));
    }

    [Fact]
    public void Inventory_Scenarios_MatchPython()
    {
        var inv = NewInv(6);
        var ok1 = inv.AddItem(MatId, MatStack * 2 + 5);
        AssertScenario("stack_overflow", inv, ok1, inv.GetItemCount(MatId));

        inv = NewInv(6);
        var ok2 = inv.AddItem(EquipId, 2);
        AssertScenario("equipment_no_stack", inv, ok2);

        inv = NewInv(6);
        inv.AddItem(MatId, 10);
        inv.AddItem(MatId, 10, rarity: "rare");
        inv.AddItem(MatId, 10,
            craftedStats: new JsonObject { ["damage_multiplier"] = 0.1 });
        AssertScenario("rarity_and_stats_split", inv, count: inv.GetItemCount(MatId));

        inv = NewInv(2);
        var ok3 = inv.AddItem(MatId, MatStack * 3);
        AssertScenario("full_inventory_fail", inv, ok3);

        inv = NewInv(6);
        inv.AddItem(MatId, MatStack + 10);
        var removedOk = inv.RemoveItem(MatId, MatStack + 3);
        var removedFail = inv.RemoveItem(MatId, 100);
        var rem = G.GetProperty("inventory").GetProperty("remove_across_stacks");
        Assert.Equal(rem.GetProperty("removed_ok").GetBoolean(), removedOk);
        Assert.Equal(rem.GetProperty("removed_fail").GetBoolean(), removedFail);
        Assert.Equal(rem.GetProperty("has_5").GetBoolean(), inv.HasItem(MatId, 5));
        AssertScenario("remove_across_stacks", inv, count: inv.GetItemCount(MatId));
    }

    [Fact]
    public void Inventory_DragSemantics_MatchPython()
    {
        var inv = NewInv(6);
        inv.AddItem(MatId, 20);
        inv.AddItem(EquipId, 1);
        inv.StartDrag(0);
        inv.EndDrag(1);
        AssertScenario("drag_swap", inv);

        inv = NewInv(6);
        inv.AddItem(MatId, 20);
        inv.Slots[2] = new ItemStack(BootedDatabases.All.Value.Materials,
            BootedDatabases.All.Value.Equipment, MatId, 30);
        inv.StartDrag(0);
        inv.EndDrag(2);
        AssertScenario("drag_merge", inv);

        inv = NewInv(6);
        inv.AddItem(MatId, 20);
        inv.StartDrag(0);
        inv.EndDrag(99);
        AssertScenario("drag_out_of_range", inv);

        inv = NewInv(6);
        inv.AddItem(MatId, 20);
        inv.StartDrag(0);
        inv.CancelDrag();
        AssertScenario("drag_cancel", inv);
    }

    private static ActiveBuff Mk(string id, string etype, string cat, double value,
                                 double dur = 30.0, bool consume = false) =>
        new()
        {
            BuffId = id, Name = id, EffectType = etype, Category = cat,
            BonusValue = value, Duration = dur, DurationRemaining = dur,
            ConsumeOnUse = consume,
        };

    [Fact]
    public void Buffs_Bonuses_Ticks_Consumption_MatchPython()
    {
        var bm = new BuffManager();
        bm.AddBuff(Mk("b1", "empower", "combat", 0.5));
        bm.AddBuff(Mk("b2", "empower", "combat", 0.25));
        bm.AddBuff(Mk("b3", "empower", "mining", 1.0));
        bm.AddBuff(Mk("b4", "quicken", "movement", 0.15));
        bm.AddBuff(Mk("b5", "fortify", "defense", 20.0));
        var bonuses = G.GetProperty("buff_bonuses");
        GoldenFixture.AssertClose(bonuses.GetProperty("empower_combat").GetDouble(),
            bm.GetTotalBonus("empower", "combat"), "empower_combat");
        GoldenFixture.AssertClose(bonuses.GetProperty("damage_combat").GetDouble(),
            bm.GetDamageBonus("combat"), "damage_combat");
        GoldenFixture.AssertClose(bonuses.GetProperty("movement").GetDouble(),
            bm.GetMovementSpeedBonus(), "movement");
        GoldenFixture.AssertClose(bonuses.GetProperty("defense").GetDouble(),
            bm.GetDefenseBonus(), "defense");
        GoldenFixture.AssertClose(bonuses.GetProperty("missing").GetDouble(),
            bm.GetTotalBonus("empower", "fishing"), "missing");

        var bm2 = new BuffManager();
        var shortBuff = Mk("short", "empower", "combat", 0.5, dur: 1.0);
        bm2.AddBuff(shortBuff);
        bm2.AddBuff(Mk("long", "empower", "combat", 0.25, dur: 10.0));
        bm2.Update(0.6);
        var t1 = G.GetProperty("buff_tick1");
        Assert.Equal(t1.GetProperty("active").EnumerateArray().Select(x => x.GetString()),
            bm2.ActiveBuffs.Select(b => b.BuffId));
        GoldenFixture.AssertClose(t1.GetProperty("short_progress").GetDouble(),
            shortBuff.GetProgressPercent(), "short_progress");
        bm2.Update(0.6);
        Assert.Equal(
            G.GetProperty("buff_tick2").GetProperty("active").EnumerateArray()
                .Select(x => x.GetString()),
            bm2.ActiveBuffs.Select(b => b.BuffId));

        var bm3 = new BuffManager();
        bm3.AddBuff(Mk("c1", "empower", "combat", 0.5, consume: true));
        bm3.AddBuff(Mk("c2", "empower", "mining", 0.5, consume: true));
        bm3.AddBuff(Mk("c3", "empower", "smithing", 0.5, consume: true));
        bm3.AddBuff(Mk("c4", "empower", "combat", 0.5, consume: false));
        bm3.ConsumeBuffsForAction("attack");
        Assert.Equal(
            G.GetProperty("consume_after_attack").EnumerateArray().Select(x => x.GetString()),
            bm3.ActiveBuffs.Select(b => b.BuffId));
        bm3.ConsumeBuffsForAction("gather");
        Assert.Equal(
            G.GetProperty("consume_after_gather").EnumerateArray().Select(x => x.GetString()),
            bm3.ActiveBuffs.Select(b => b.BuffId));
        bm3.ConsumeBuffsForAction("craft", "smithing");
        Assert.Equal(
            G.GetProperty("consume_after_craft_smithing").EnumerateArray()
                .Select(x => x.GetString()),
            bm3.ActiveBuffs.Select(b => b.BuffId));
    }
}
