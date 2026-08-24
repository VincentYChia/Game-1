namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/attack_profile_generator.py — deterministic per-enemy
/// attack profiles derived from category archetype × tier scaling × behavior
/// tempo × stat feel × ability-tag inference. Python round() is banker's
/// rounding; Math.Round's default MidpointRounding.ToEven matches.
/// </summary>
public static class AttackProfileGenerator
{
    private sealed record Template(
        string Id, string Shape, int Arc, double Range, double Windup,
        double Active, double Recovery, int Weight, string[] Tags,
        bool Shake = false, double DmgMult = 1.0);

    private static readonly Dictionary<string, (Template Primary, Template Secondary, Template Heavy)> Archetypes = new()
    {
        ["beast"] = (
            new("bite", "arc", 55, 1.4, 500, 200, 350, 3, new[] { "physical" }),
            new("claw", "arc", 90, 1.2, 400, 180, 300, 2, new[] { "physical" }),
            new("lunge", "arc", 35, 2.2, 650, 220, 450, 1, new[] { "physical" }, true, 1.3)),
        ["ooze"] = (
            new("engulf", "circle", 360, 1.2, 700, 350, 500, 3, new[] { "physical" }),
            new("splash", "circle", 360, 1.8, 850, 400, 600, 1, new[] { "physical" }, false, 0.8),
            new("dissolve", "circle", 360, 2.0, 950, 450, 700, 1, new[] { "physical" }, true, 1.2)),
        ["insect"] = (
            new("mandible", "arc", 45, 1.2, 350, 140, 250, 3, new[] { "physical" }),
            new("sting", "arc", 30, 1.6, 400, 160, 280, 2, new[] { "physical" }),
            new("charge", "arc", 40, 2.5, 550, 200, 400, 1, new[] { "physical" }, true, 1.4)),
        ["construct"] = (
            new("slam", "arc", 100, 1.6, 750, 350, 550, 3, new[] { "physical" }),
            new("sweep", "arc", 140, 1.8, 850, 400, 600, 2, new[] { "physical" }),
            new("smash", "arc", 120, 2.4, 1000, 450, 700, 1, new[] { "physical" }, true, 1.5)),
        ["undead"] = (
            new("swipe", "arc", 80, 1.4, 600, 260, 420, 3, new[] { "physical" }),
            new("grab", "arc", 50, 1.6, 700, 300, 500, 2, new[] { "physical" }),
            new("rend", "arc", 70, 2.0, 800, 350, 550, 1, new[] { "physical" }, true, 1.3)),
        ["elemental"] = (
            new("pulse", "circle", 360, 1.5, 600, 300, 450, 3, new[] { "arcane" }),
            new("blast", "arc", 120, 1.8, 650, 320, 480, 2, new[] { "arcane" }),
            new("eruption", "circle", 360, 2.5, 800, 400, 600, 1, new[] { "arcane" }, true, 1.4)),
        ["aberration"] = (
            new("lash", "arc", 110, 1.6, 550, 280, 380, 3, new[] { "shadow" }),
            new("warp_strike", "circle", 360, 1.4, 600, 300, 400, 2, new[] { "shadow" }),
            new("devour", "arc", 90, 2.2, 700, 350, 500, 1, new[] { "shadow" }, true, 1.4)),
        ["dragon"] = (
            new("bite", "arc", 80, 2.0, 800, 400, 600, 3, new[] { "physical" }),
            new("breath", "arc", 140, 3.0, 1000, 500, 700, 2, new[] { "fire" }, false, 1.2),
            new("tail_sweep", "arc", 180, 2.5, 900, 450, 650, 1, new[] { "physical" }, true, 1.5)),
        ["humanoid"] = (
            new("swing", "arc", 75, 1.4, 450, 180, 320, 3, new[] { "physical" }),
            new("thrust", "arc", 35, 1.8, 500, 200, 360, 2, new[] { "physical" }),
            new("overhead", "arc", 60, 1.6, 600, 240, 420, 1, new[] { "physical" }, true, 1.3)),
    };

    // attack_profile_generator.py:97-105 — keyword CONTAINMENT, dict order
    private static readonly (string Keyword, double Windup, double Recovery, bool Heavy)[] BehaviorMods =
    {
        ("passive", 1.15, 1.1, false), ("docile", 1.2, 1.15, false),
        ("stationary", 1.3, 1.2, false), ("territorial", 1.0, 1.0, false),
        ("aggressive", 0.85, 0.9, true), ("boss", 0.9, 0.85, true),
    };

    private static readonly Dictionary<string, string> AbilityTagToStatus = new()
    {
        ["bleed"] = "bleed", ["poison"] = "poison", ["poison_status"] = "poison",
        ["burn"] = "burn", ["freeze"] = "freeze", ["chill"] = "chill",
        ["stun"] = "stun", ["slow"] = "slow", ["shock"] = "shock",
    };

    private static readonly Dictionary<string, string> AbilityTagToElement = new()
    {
        ["fire"] = "fire", ["ice"] = "ice", ["lightning"] = "lightning",
        ["poison"] = "poison", ["arcane"] = "arcane", ["shadow"] = "shadow",
        ["holy"] = "holy", ["chaos"] = "shadow",
    };

    public static List<EnemyAttackDef> Generate(EnemyDefinition def)
    {
        var archetype = Archetypes.GetValueOrDefault(def.Category, Archetypes["beast"]);

        var (windupMult, recoveryMult, includeHeavy) = ResolveBehaviorMod(def.Behavior);
        var metaTags = new HashSet<string>(def.Tags);
        if (metaTags.Contains("aggressive"))
        {
            windupMult *= 0.9;
            recoveryMult *= 0.9;
            includeHeavy = true;
        }
        if (metaTags.Contains("passive") || metaTags.Contains("docile"))
        {
            windupMult *= 1.1;
            recoveryMult *= 1.1;
        }

        var tierRangeMult = def.Tier switch { 1 => 1.0, 2 => 1.15, 3 => 1.3, 4 => 1.5, _ => 1.0 };
        var (inferredElement, inferredStatus) = InferTagsFromAbilities(def.SpecialAbilities);

        var isTanky = def.Defense > 20 && def.Speed <= 0.8;
        var isAgile = def.Speed >= 1.3 && def.Defense < 15;

        var attacks = new List<EnemyAttackDef>
        {
            Build(archetype.Primary, tierRangeMult, windupMult, recoveryMult,
                  isTanky, isAgile),
        };

        if (def.Tier >= 2 || includeHeavy)
        {
            var secondary = archetype.Secondary;
            var tags = secondary.Tags.ToList();
            var status = new List<string>();
            if (inferredStatus is not null && isAgile)
            {
                tags.Add(inferredStatus);
                status.Add(inferredStatus);
            }
            else if (inferredElement is not null)
            {
                tags = new List<string> { inferredElement };
            }
            attacks.Add(Build(secondary with { Tags = tags.ToArray() },
                tierRangeMult, windupMult, recoveryMult, isTanky, isAgile,
                statusTags: status));
        }

        var isBoss = def.Behavior.Contains("boss") || metaTags.Contains("boss");
        if (includeHeavy || isBoss || def.Tier >= 3)
        {
            var heavy = archetype.Heavy;
            var shake = heavy.Shake || isBoss || def.Tier >= 3;
            var arc = isTanky ? Math.Min(360, (int)(heavy.Arc * 1.3)) : heavy.Arc;
            var tags = inferredElement is not null
                ? new[] { inferredElement } : heavy.Tags;
            attacks.Add(Build(heavy with { Shake = shake, Arc = arc, Tags = tags },
                tierRangeMult, windupMult, recoveryMult, isTanky, isAgile));
        }

        foreach (var atk in attacks)
            atk.AttackId = $"{def.Category}_{atk.AttackId}";
        return attacks;
    }

    private static (double, double, bool) ResolveBehaviorMod(string behavior)
    {
        foreach (var (keyword, windup, recovery, heavy) in BehaviorMods)
            if (behavior.Contains(keyword))
                return (windup, recovery, heavy);
        return (1.0, 1.0, false);
    }

    private static (string? Element, string? Status) InferTagsFromAbilities(
        IReadOnlyList<SpecialAbility> abilities)
    {
        var elementCounts = new Dictionary<string, int>();
        var elementOrder = new List<string>();  // Python max() keeps first-seen on ties
        string? foundStatus = null;
        foreach (var ability in abilities)
        {
            foreach (var tag in ability.Tags)
            {
                if (AbilityTagToElement.TryGetValue(tag, out var elem))
                {
                    if (!elementCounts.ContainsKey(elem)) elementOrder.Add(elem);
                    elementCounts[elem] = elementCounts.GetValueOrDefault(elem) + 1;
                }
                if (foundStatus is null && AbilityTagToStatus.TryGetValue(tag, out var status))
                    foundStatus = status;
            }
        }
        string? bestElement = null;
        var bestCount = -1;
        foreach (var elem in elementOrder)  // insertion order = Python dict order
            if (elementCounts[elem] > bestCount)
            {
                bestCount = elementCounts[elem];
                bestElement = elem;
            }
        return (bestElement, foundStatus);
    }

    private static EnemyAttackDef Build(
        Template t, double tierRangeMult, double windupMult, double recoveryMult,
        bool isTanky, bool isAgile, List<string>? statusTags = null)
    {
        double arc = t.Arc;
        var rangeVal = t.Range * tierRangeMult;
        var windup = t.Windup * windupMult;
        var active = t.Active;
        var recovery = t.Recovery * recoveryMult;

        if (isTanky)
        {
            arc = Math.Min(360, (int)(arc * 1.2));
            windup *= 1.1;
            active *= 1.15;
        }
        if (isAgile)
        {
            windup *= 0.85;
            recovery *= 0.85;
            arc = Math.Max(20, (int)(arc * 0.85));
            rangeVal *= 1.1;
        }

        return new EnemyAttackDef
        {
            AttackId = t.Id,
            Shape = t.Shape,
            Arc = arc,
            Range = Math.Round(rangeVal, 2),
            Windup = Math.Round(windup),
            Active = Math.Round(active),
            Recovery = Math.Round(recovery),
            Weight = t.Weight,
            Tags = t.Tags.ToList(),
            ScreenShake = t.Shake,
            DamageMultiplier = t.DmgMult,
            StatusTags = statusTags ?? new List<string>(),
        };
    }
}
