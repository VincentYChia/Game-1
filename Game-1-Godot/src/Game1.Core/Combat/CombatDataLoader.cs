namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/combat_data_loader.py — dynamic attack generation from
/// weapon properties, enemy definitions, and tags. No JSON.
/// Python uses the global `random` module for weighted attack selection;
/// this port takes an explicit PythonRandom so seeded runs replay exactly.
/// </summary>
public static class CombatGen
{
    public static readonly Dictionary<string, (string Shape, double Arc, double Radius, double Windup, double Active, double Recovery)>
        WeaponProfiles = new()
        {
            ["sword_1h"] = ("arc", 55, 0, 300, 200, 240),
            ["sword_2h"] = ("arc", 75, 0, 500, 300, 400),
            ["dagger"] = ("arc", 25, 0, 160, 120, 160),
            ["axe"] = ("arc", 65, 0, 400, 240, 360),
            ["mace"] = ("arc", 50, 0, 440, 260, 400),
            ["hammer_2h"] = ("arc", 75, 0, 600, 360, 500),
            ["spear"] = ("arc", 15, 0, 360, 200, 300),
            ["staff"] = ("arc", 30, 0, 400, 240, 320),
            ["bow"] = ("projectile", 0, 0, 600, 100, 400),
            ["unarmed"] = ("arc", 50, 0, 200, 160, 200),
        };

    public static readonly Dictionary<string, int[]> ElementColors = new()
    {
        ["physical"] = new[] { 230, 230, 255 },
        ["fire"] = new[] { 255, 100, 20 },
        ["ice"] = new[] { 80, 200, 255 },
        ["frost"] = new[] { 80, 200, 255 },
        ["lightning"] = new[] { 255, 255, 60 },
        ["poison"] = new[] { 80, 255, 60 },
        ["arcane"] = new[] { 200, 60, 255 },
        ["shadow"] = new[] { 160, 60, 220 },
        ["holy"] = new[] { 255, 255, 160 },
    };

    public static readonly Dictionary<string, (string Shape, double Arc, double Radius, double Windup, double Active, double Recovery)>
        EnemyAttackProfiles = new()
        {
            ["beast"] = ("arc", 80, 0, 600, 240, 400),
            ["ooze"] = ("circle", 0, 1.0, 800, 400, 600),
            ["insect"] = ("arc", 60, 0, 400, 160, 300),
            ["construct"] = ("arc", 100, 0, 800, 400, 600),
            ["undead"] = ("arc", 90, 0, 700, 300, 500),
            ["elemental"] = ("circle", 0, 1.2, 700, 360, 500),
            ["aberration"] = ("arc", 120, 0, 600, 320, 400),
            ["dragon"] = ("cone", 140, 0, 1000, 500, 700),
            ["humanoid"] = ("arc", 80, 0, 500, 200, 360),
        };

    private static readonly string[] WeaponStatusTags =
        { "burn", "bleed", "poison", "freeze", "stun", "slow" };

    public static List<int> ColorFromTags(IReadOnlyList<string> tags, int[]? fallback = null)
    {
        fallback ??= new[] { 220, 220, 240 };
        foreach (var t in tags)
            if (ElementColors.TryGetValue(t, out var c))
                return new List<int>(c);
        return new List<int>(fallback);
    }

    public static AttackDefinition GenerateWeaponAttack(
        string weaponType, double weaponRange,
        double attackSpeed = 1.0, List<string>? weaponTags = null)
    {
        var tags = weaponTags ?? new List<string>();
        var profile = WeaponProfiles.TryGetValue(weaponType, out var p)
            ? p : WeaponProfiles["unarmed"];

        var speedFactor = 1.0 / Math.Max(0.3, attackSpeed);

        var shape = profile.Shape;
        var hp = new HitboxParams { OffsetForward = 0.8 };

        if (shape == "arc")
        {
            hp.Shape = "arc";
            hp.Radius = weaponRange;
            hp.ArcDegrees = profile.Arc;
        }
        else if (shape == "line")
        {
            hp.Shape = "line";
            hp.Length = weaponRange;
        }
        else if (shape == "projectile")
        {
            hp.Shape = "arc";
            hp.Radius = 0.5;
            hp.ArcDegrees = 30;
        }

        var telegraphColor = ColorFromTags(tags);

        return new AttackDefinition
        {
            AttackId = $"dynamic_{weaponType}",
            WindupMs = profile.Windup * speedFactor,
            ActiveMs = profile.Active * speedFactor,
            RecoveryMs = profile.Recovery * speedFactor,
            CooldownMs = 100 * speedFactor,
            HitboxShape = hp.Shape ?? "arc",
            HitboxParamsData = hp,
            DamageMultiplier = 1.0,
            MovementMultiplier = 0.7,
            CanBeInterrupted = true,
            AnimationId = $"swing_{weaponType}",
            ProjectileId = shape == "projectile" ? $"dynamic_{weaponType}_proj" : null,
            StatusTags = tags.Where(t => WeaponStatusTags.Contains(t)).ToList(),
            ScreenShake = false,
            TelegraphColor = telegraphColor,
            Tags = tags,
        };
    }

    /// <summary>CPython random.choices(pop, weights, k=1)[0]: cumulative
    /// weights + bisect_right(cum, random()*total, 0, n-1).</summary>
    public static T WeightedChoice<T>(IReadOnlyList<T> population,
                                      IReadOnlyList<double> weights,
                                      PythonRandom rng)
    {
        var n = population.Count;
        var cum = new double[n];
        double acc = 0;
        for (var i = 0; i < n; i++)
        {
            acc += weights[i];
            cum[i] = acc;
        }
        var total = cum[n - 1];
        var u = rng.NextDouble() * total;
        // bisect_right over cum[0..hi) with hi = n-1
        int lo = 0, hi = n - 1;
        while (lo < hi)
        {
            var mid = (lo + hi) / 2;
            if (u < cum[mid]) hi = mid;
            else lo = mid + 1;
        }
        return population[lo];
    }

    public static AttackDefinition GenerateEnemyAttack(
        EnemyDefinition enemyDef, int attackIndex, PythonRandom rng)
    {
        var category = enemyDef.Category;
        var tier = (int)enemyDef.Tier;
        var enemyTags = enemyDef.Tags;
        var visualSize = enemyDef.VisualSize;

        var tierSpeedMult = tier switch { 1 => 1.0, 2 => 0.95, 3 => 0.9, 4 => 0.85, _ => 1.0 };

        var perEnemyAttacks = enemyDef.Attacks;
        if (perEnemyAttacks.Count > 0)
        {
            var weights = perEnemyAttacks.Select(a => (double)a.Weight).ToList();
            var selected = WeightedChoice(perEnemyAttacks, weights, rng);

            var shape = selected.Shape;
            var hp = new HitboxParams { OffsetForward = visualSize * 0.6 };

            if (shape is "arc" or "cone")
            {
                hp.Shape = "arc";
                hp.Radius = selected.Range;
                hp.ArcDegrees = selected.Arc;
            }
            else if (shape == "circle")
            {
                hp.Shape = "circle";
                hp.Radius = selected.Range;
            }
            else if (shape == "line")
            {
                hp.Shape = "line";
                hp.Length = selected.Range;
            }
            else if (shape == "rect")
            {
                hp.Shape = "rect";
                hp.Width = selected.Range * 0.5;
                hp.Height = selected.Range;
            }

            // Python `selected.tags or enemy_tags` — empty list is falsy
            var atkTags = selected.Tags.Count > 0 ? selected.Tags : enemyTags;
            var telegraphColor = ColorFromTags(atkTags, new[] { 255, 100, 100 });

            return new AttackDefinition
            {
                AttackId = $"enemy_{enemyDef.EnemyId}_{selected.AttackId}",
                WindupMs = selected.Windup * tierSpeedMult,
                ActiveMs = selected.Active * tierSpeedMult,
                RecoveryMs = selected.Recovery * tierSpeedMult,
                CooldownMs = 200 * tierSpeedMult,
                HitboxShape = hp.Shape ?? "arc",
                HitboxParamsData = hp,
                DamageMultiplier = selected.DamageMultiplier,
                MovementMultiplier = 0.5,
                CanBeInterrupted = true,
                AnimationId = $"enemy_{category}_{selected.AttackId}",
                StatusTags = new List<string>(selected.StatusTags),
                ScreenShake = selected.ScreenShake,
                TelegraphColor = telegraphColor,
                Tags = new List<string>(atkTags),
            };
        }

        // Fallback: category-based profile
        var profile = EnemyAttackProfiles.TryGetValue(category, out var pr)
            ? pr : EnemyAttackProfiles["beast"];
        var tierRadiusMult = tier switch { 1 => 1.0, 2 => 1.3, 3 => 1.6, 4 => 2.0, _ => 1.0 };

        var fShape = profile.Shape;
        var fhp = new HitboxParams { OffsetForward = visualSize * 0.6 };
        var baseRadius = visualSize * 0.8 * tierRadiusMult;

        if (fShape is "arc" or "cone")
        {
            fhp.Shape = "arc";
            fhp.Radius = baseRadius;
            fhp.ArcDegrees = profile.Arc == 0 ? 90 : profile.Arc;
        }
        else if (fShape == "circle")
        {
            fhp.Shape = "circle";
            fhp.Radius = baseRadius;
        }
        else if (fShape == "line")
        {
            fhp.Shape = "line";
            fhp.Length = baseRadius * 1.5;
        }

        var fallbackColor = ColorFromTags(enemyTags, new[] { 255, 100, 100 });

        return new AttackDefinition
        {
            AttackId = $"enemy_{enemyDef.EnemyId}_{attackIndex}",
            WindupMs = profile.Windup * tierSpeedMult,
            ActiveMs = profile.Active * tierSpeedMult,
            RecoveryMs = profile.Recovery * tierSpeedMult,
            CooldownMs = 200 * tierSpeedMult,
            HitboxShape = fhp.Shape ?? "arc",
            HitboxParamsData = fhp,
            DamageMultiplier = 1.0,
            MovementMultiplier = 0.5,
            CanBeInterrupted = true,
            AnimationId = $"enemy_{category}_attack",
            StatusTags = new List<string>(),
            ScreenShake = tier >= 3,
            TelegraphColor = fallbackColor,
            Tags = new List<string>(enemyTags),
        };
    }

    public static ProjectileDefinition GenerateProjectileFromTags(
        string weaponType, List<string>? tags = null,
        double baseSpeed = 12.0, double baseRange = 10.0)
    {
        tags ??= new List<string> { "physical" };
        var color = ColorFromTags(tags);

        var isArrow = tags.Any(t => t is "arrow" or "bow" or "crossbow");
        var isBeam = tags.Any(t => t is "beam" or "lightning");
        var isShard = tags.Any(t => t is "ice" or "frost" or "crystal");

        string visShape;
        int lengthPx, widthPx;
        if (isArrow) { visShape = "elongated"; lengthPx = 8; widthPx = 3; }
        else if (isBeam) { visShape = "beam"; lengthPx = 24; widthPx = 8; }
        else if (isShard) { visShape = "elongated"; lengthPx = 8; widthPx = 5; }
        else { visShape = "orb"; lengthPx = 8; widthPx = 8; }

        string? trailType = null;
        foreach (var t in tags)
        {
            if (t is "fire" or "ice" or "frost" or "lightning" or "poison"
                or "arcane" or "shadow" or "holy")
            {
                trailType = $"{t}_trail";
                break;
            }
        }

        var hasGlow = tags.Any(t => t is "fire" or "ice" or "frost" or "lightning"
            or "arcane" or "holy" or "shadow");

        var visual = new Dictionary<string, object?>
        {
            ["shape"] = visShape,
            ["color"] = color,
            ["glow"] = hasGlow,
            ["glow_color"] = color.Select(c => Math.Min(255, c + 60)).ToList(),
            ["length_px"] = lengthPx,
            ["width_px"] = widthPx,
        };

        var homing = tags.Any(t => t is "homing" or "seeking") ? 0.5 : 0.0;

        return new ProjectileDefinition
        {
            ProjectileId = $"dynamic_{weaponType}_proj",
            Speed = baseSpeed,
            MaxRange = baseRange,
            HitboxRadius = 0.3,
            SpriteId = visShape,
            TrailType = trailType,
            Homing = homing,
            Gravity = 0.0,
            Piercing = tags.Any(t => t is "pierce" or "piercing"),
            Visual = visual,
            Tags = tags,
        };
    }
}

/// <summary>combat_data_loader.py CombatDataLoader — cached dynamic generation.
/// The weapon cache key deliberately excludes weapon_tags (Python quirk:
/// first call's tags win for a given type/range/speed).</summary>
public sealed class CombatDataLoader
{
    private readonly Dictionary<(string, double, double), AttackDefinition> _weaponCache = new();
    private readonly Dictionary<string, List<AttackDefinition>> _enemyCache = new();
    private readonly Dictionary<string, ProjectileDefinition> _projectileCache = new();

    public AttackDefinition GetWeaponAttack(string weaponType,
                                            int comboIndex = 0,
                                            double weaponRange = 1.5,
                                            double attackSpeed = 1.0,
                                            List<string>? weaponTags = null)
    {
        var key = (weaponType, weaponRange, attackSpeed);
        if (!_weaponCache.TryGetValue(key, out var atk))
        {
            atk = CombatGen.GenerateWeaponAttack(weaponType, weaponRange, attackSpeed, weaponTags);
            _weaponCache[key] = atk;
        }
        return atk;
    }

    public List<AttackDefinition> GetEnemyAttacks(string enemyId,
                                                  EnemyDefinition? enemyDef,
                                                  PythonRandom rng)
    {
        if (_enemyCache.TryGetValue(enemyId, out var cached))
            return cached;

        if (enemyDef is null)
        {
            // Python's default stub sets visual_size=1.0; beast/T1 computes 1.0 too
            var stub = new EnemyDefinition
            {
                EnemyId = enemyId, Name = enemyId, Tier = 1, Category = "beast",
                Behavior = "aggressive",
                Ai = new AiPattern("wander", true, true, 0.0, 0.0, false, new List<string>()),
            };
            return new List<AttackDefinition> { CombatGen.GenerateEnemyAttack(stub, 0, rng) };
        }

        var attacks = new List<AttackDefinition> { CombatGen.GenerateEnemyAttack(enemyDef, 0, rng) };
        _enemyCache[enemyId] = attacks;
        return attacks;
    }

    /// <summary>combat_data_loader.py select_enemy_attack — range-gated pool,
    /// then random.choice.</summary>
    public AttackDefinition? SelectEnemyAttack(string enemyId,
                                               double distToPlayer,
                                               EnemyDefinition? enemyDef,
                                               PythonRandom rng)
    {
        var attacks = GetEnemyAttacks(enemyId, enemyDef, rng);
        if (attacks.Count == 0) return null;

        var available = new List<AttackDefinition>();
        foreach (var atk in attacks)
        {
            var maxReach = atk.HitboxRadius + atk.HitboxOffsetForward;
            if (atk.ProjectileId is not null)
                maxReach = 999;
            if (distToPlayer <= maxReach * 1.3)
                available.Add(atk);
        }

        if (available.Count == 0) return null;
        return rng.Choice(available);
    }

    public ProjectileDefinition GetProjectile(string projectileId,
                                              string weaponType = "bow",
                                              List<string>? tags = null)
    {
        if (_projectileCache.TryGetValue(projectileId, out var cached))
            return cached;

        var proj = CombatGen.GenerateProjectileFromTags(weaponType, tags);
        _projectileCache[projectileId] = proj;
        return proj;
    }

    /// <summary>hitbox_def_from_attack — HitboxDefinition from an
    /// AttackDefinition's params with Python .get defaults.</summary>
    public static HitboxDefinition HitboxDefFromAttack(AttackDefinition attackDef)
    {
        var p = attackDef.HitboxParamsData;
        return new HitboxDefinition
        {
            Shape = attackDef.HitboxShape,
            Radius = p.Radius ?? 1.5,
            ArcDegrees = p.ArcDegrees ?? 90.0,
            Width = p.Width ?? 1.0,
            Height = p.Height ?? 0.5,
            Length = p.Length ?? 2.0,
            OffsetForward = p.OffsetForward,
            OffsetLateral = p.OffsetLateral ?? 0.0,
            Piercing = p.Piercing ?? false,
        };
    }

    public void ClearCache()
    {
        _weaponCache.Clear();
        _enemyCache.Clear();
        _projectileCache.Clear();
    }
}
