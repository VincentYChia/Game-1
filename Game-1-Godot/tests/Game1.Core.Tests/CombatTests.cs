using System.Text.Json;
using Game1.Core.Combat;
using Xunit;

namespace Game1.Core.Tests;

public class CritChanceTests
{
    private static readonly JsonElement G = GoldenFixture.Load("crit_chance.json");

    [Fact]
    public void LckPerPoint_MatchesPython() =>
        GoldenFixture.AssertClose(G.GetProperty("lck_crit_per_point").GetDouble(),
                                  Game1.Core.GameConstants.LckCritPerPoint,
                                  "lck_crit_per_point");

    [Fact]
    public void Composition_MatchesPython()
    {
        foreach (var c in G.GetProperty("cases").EnumerateArray())
        {
            var tags = c.GetProperty("weapon_tags").EnumerateArray()
                        .Select(t => t.GetString()!).ToList();
            var chance = CritChance.Compute(
                c.GetProperty("effective_luck").GetDouble(),
                c.GetProperty("pierce_buff").GetDouble(),
                c.GetProperty("title_crit").GetDouble(),
                tags);
            GoldenFixture.AssertClose(c.GetProperty("chance").GetDouble(), chance,
                $"crit(luck={c.GetProperty("effective_luck")}, tags=[{string.Join(",", tags)}])");
        }
    }
}

public class DefenseReductionTests
{
    private static readonly JsonElement G = GoldenFixture.Load("defense_reduction.json");

    [Fact]
    public void Grid_MatchesPython()
    {
        foreach (var c in G.GetProperty("cases").EnumerateArray())
        {
            var defense = c.GetProperty("defense").GetDouble();
            var pen = c.GetProperty("armor_penetration").GetDouble();
            GoldenFixture.AssertClose(c.GetProperty("reduction").GetDouble(),
                DefenseReduction.Reduction(defense, pen),
                $"reduction(def={defense}, pen={pen})");
            GoldenFixture.AssertClose(c.GetProperty("damage_multiplier").GetDouble(),
                DefenseReduction.Apply(1.0, defense, pen),
                $"multiplier(def={defense}, pen={pen})");
        }
    }
}

public class DamageCompositionTests
{
    private static readonly JsonElement G = GoldenFixture.Load("damage_composition.json");

    [Fact]
    public void Constants_MatchPython()
    {
        GoldenFixture.AssertClose(G.GetProperty("str_dmg_per_point").GetDouble(),
                                  Game1.Core.GameConstants.StrDamagePerPoint,
                                  "str_dmg_per_point");
        GoldenFixture.AssertClose(G.GetProperty("lck_crit_per_point").GetDouble(),
                                  Game1.Core.GameConstants.LckCritPerPoint,
                                  "lck_crit_per_point");
    }

    [Fact]
    public void ScenarioMatrix_MatchesPython()
    {
        foreach (var c in G.GetProperty("cases").EnumerateArray())
        {
            var i = c.GetProperty("inputs");
            var inputs = new DamageInputs(
                BaseDamage: i.GetProperty("base").GetDouble(),
                WeaponDamage: i.GetProperty("weapon").GetDouble(),
                HandMultiplier: i.GetProperty("hand_mult").GetDouble(),
                Strength: i.GetProperty("strength").GetInt32(),
                TitleMeleeBonus: i.GetProperty("title_melee").GetDouble(),
                EnemyTypeTitleMultiplier: i.GetProperty("enemy_mult").GetDouble(),
                Intelligence: i.GetProperty("intelligence").GetInt32(),
                HasElementalTag: i.GetProperty("elemental").GetBoolean(),
                CrushingBonus: i.GetProperty("crushing").GetDouble(),
                EnemyDefense: i.GetProperty("enemy_def").GetDouble(),
                EmpowerBonus: i.GetProperty("empower").GetDouble(),
                IsCrit: i.GetProperty("crit").GetBoolean(),
                ArmorPenetration: i.GetProperty("armor_pen").GetDouble());
            GoldenFixture.AssertClose(c.GetProperty("final_damage").GetDouble(),
                DamageComposition.Compose(inputs), "final_damage");
        }
    }
}
