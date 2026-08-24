using Game1.Core.Tags;
using Game1.Core.World;

namespace Game1.Core.Combat;

/// <summary>
/// Port of core/geometry/target_finder.py + math_utils.py — geometry-based
/// target selection (single/chain/cone/circle/beam) with context filtering
/// and enemy-source context flipping.
/// </summary>
public sealed class TargetFinder
{
    // ── math_utils.py ────────────────────────────────────────────────────

    public static double Distance(Position a, Position b) => a.DistanceTo(b);

    public static (double X, double Y) NormalizeVector(double dx, double dy)
    {
        var length = Math.Sqrt(dx * dx + dy * dy);
        if (length == 0) return (0.0, 0.0);
        return (dx / length, dy / length);
    }

    public static double DotProduct((double X, double Y) v1, (double X, double Y) v2) =>
        v1.X * v2.X + v1.Y * v2.Y;

    public static double AngleBetweenVectors((double X, double Y) v1, (double X, double Y) v2)
    {
        var dot = DotProduct(v1, v2);
        dot = Math.Max(-1.0, Math.Min(1.0, dot));
        return PyMath.Degrees(Math.Acos(dot));
    }

    public static (double X, double Y) DirectionVector(Position from, Position to) =>
        NormalizeVector(to.X - from.X, to.Y - from.Y);

    public static bool IsInCone(Position sourcePos, (double X, double Y) sourceFacing,
                                Position targetPos, double coneAngle, double coneRange)
    {
        var dist = Distance(sourcePos, targetPos);
        if (dist > coneRange) return false;
        var toTarget = DirectionVector(sourcePos, targetPos);
        var angle = AngleBetweenVectors(sourceFacing, toTarget);
        return angle <= coneAngle / 2.0;
    }

    public static bool IsInCircle(Position center, Position targetPos, double radius) =>
        Distance(center, targetPos) <= radius;

    public static (double X, double Y) EstimateFacingDirection(ICombatEntity source)
    {
        if (source.LastMoveDirection is { } lmd)
            return NormalizeVector(lmd.Dx, lmd.Dy);
        return (1.0, 0.0);
    }

    // ── target_finder.py ─────────────────────────────────────────────────

    public static Position GetPosition(object entity) => entity switch
    {
        Position p => p,
        ICombatEntity e => e.GetPosition(),
        _ => throw new ArgumentException($"Cannot get position from {entity.GetType()}"),
    };

    public List<ICombatEntity> FindTargets(string? geometry, ICombatEntity? source,
                                           object? primaryTarget,
                                           Dictionary<string, object?> params_,
                                           string context,
                                           List<ICombatEntity> availableEntities)
    {
        if (context == "self")
            return source is not null
                ? new List<ICombatEntity> { source }
                : new List<ICombatEntity>();

        // Enemy source flips relative targeting
        if (source is not null && source.IsEnemyLike)
        {
            if (context == "enemy") context = "ally";
            else if (context == "ally") context = "enemy";
        }

        double Num(string key, double dflt) =>
            TagParser.Num(params_.GetValueOrDefault(key), dflt);

        switch (geometry)
        {
            case "single_target":
                return FindSingleTarget(primaryTarget, context);

            case "chain":
                return FindChainTargets(source, primaryTarget as ICombatEntity,
                    (int)Num("chain_count", 2), Num("chain_range", 5.0),
                    context, availableEntities);

            case "cone":
                return FindConeTargets(source!, primaryTarget,
                    Num("cone_angle", 60), Num("cone_range", 8.0),
                    context, availableEntities);

            case "circle":
            case "aoe":
            {
                var originType = params_.GetValueOrDefault("origin") as string ?? "target";
                Position center;
                if (originType == "target")
                    center = GetPosition(primaryTarget!);
                else if (originType == "source")
                    center = GetPosition(source!);
                else
                    center = GetPosition(primaryTarget!);

                return FindCircleTargets(center,
                    Num("circle_radius", Num("radius", 3.0)),
                    (int)Num("max_targets", 0),
                    context, availableEntities);
            }

            case "beam":
            case "line":
                return FindBeamTargets(source!, primaryTarget!,
                    Num("beam_range", 10.0), Num("beam_width", 0.5),
                    (int)Num("pierce_count", 0),
                    context, availableEntities);

            default:
                return FindSingleTarget(primaryTarget, context);
        }
    }

    public List<ICombatEntity> FindSingleTarget(object? target, string context)
    {
        if (target is ICombatEntity e && IsValidContext(e, context))
            return new List<ICombatEntity> { e };
        return new List<ICombatEntity>();
    }

    public List<ICombatEntity> FindChainTargets(ICombatEntity? source,
                                                ICombatEntity? initialTarget,
                                                int chainCount, double chainRange,
                                                string context,
                                                List<ICombatEntity> availableEntities)
    {
        var targets = new List<ICombatEntity>();
        var hitSet = new HashSet<ICombatEntity>(ReferenceEqualityComparer.Instance);

        if (initialTarget is not null && IsValidContext(initialTarget, context))
        {
            targets.Add(initialTarget);
            hitSet.Add(initialTarget);
        }
        else
        {
            return targets;
        }

        var currentTarget = initialTarget;
        for (var jump = 0; jump < chainCount; jump++)
        {
            var nextTarget = FindNearestValidTarget(currentTarget!, chainRange,
                context, availableEntities, hitSet);
            if (nextTarget is null) break;

            targets.Add(nextTarget);
            hitSet.Add(nextTarget);
            currentTarget = nextTarget;
        }

        return targets;
    }

    public List<ICombatEntity> FindConeTargets(ICombatEntity source,
                                               object? primaryTarget,
                                               double coneAngle, double coneRange,
                                               string context,
                                               List<ICombatEntity> availableEntities)
    {
        var sourcePos = GetPosition(source);

        (double, double) facing;
        if (primaryTarget is not null)
            facing = DirectionVector(sourcePos, GetPosition(primaryTarget));
        else
            facing = EstimateFacingDirection(source);

        var targets = new List<ICombatEntity>();
        foreach (var entity in availableEntities)
        {
            if (!IsValidContext(entity, context)) continue;
            if (IsInCone(sourcePos, facing, GetPosition(entity), coneAngle, coneRange))
                targets.Add(entity);
        }
        return targets;
    }

    public List<ICombatEntity> FindCircleTargets(Position center, double radius,
                                                 int maxTargets, string context,
                                                 List<ICombatEntity> availableEntities)
    {
        var withDist = new List<(ICombatEntity E, double D)>();
        foreach (var entity in availableEntities)
        {
            if (!IsValidContext(entity, context)) continue;
            var pos = GetPosition(entity);
            if (IsInCircle(center, pos, radius))
                withDist.Add((entity, Distance(center, pos)));
        }

        // Python list.sort is stable — OrderBy is too
        var sorted = withDist.OrderBy(t => t.D).ToList();
        if (maxTargets > 0)
            sorted = sorted.Take(maxTargets).ToList();
        return sorted.Select(t => t.E).ToList();
    }

    public List<ICombatEntity> FindBeamTargets(ICombatEntity source, object primaryTarget,
                                               double beamRange, double beamWidth,
                                               int pierceCount, string context,
                                               List<ICombatEntity> availableEntities)
    {
        var sourcePos = GetPosition(source);
        var targetPos = GetPosition(primaryTarget);
        var beamDirection = DirectionVector(sourcePos, targetPos);

        var withDist = new List<(ICombatEntity E, double D)>();
        foreach (var entity in availableEntities)
        {
            if (!IsValidContext(entity, context)) continue;

            var entityPos = GetPosition(entity);
            var distAlongBeam = DistanceAlongLine(sourcePos, beamDirection, entityPos);
            if (distAlongBeam < 0 || distAlongBeam > beamRange) continue;

            var perpDist = PerpendicularDistance(sourcePos, beamDirection, entityPos);
            if (perpDist <= beamWidth)
                withDist.Add((entity, distAlongBeam));
        }

        var sorted = withDist.OrderBy(t => t.D).ToList();
        if (pierceCount >= 0)
            sorted = sorted.Take(pierceCount + 1).ToList();
        return sorted.Select(t => t.E).ToList();
    }

    public static bool IsValidContext(ICombatEntity entity, string context)
    {
        if (context == "all") return true;
        if (context == "self") return false;

        var entityCategory = entity.Category;
        var entityType = entity.TypeNameLower;

        if (context is "enemy" or "hostile")
        {
            if (entity.IsEnemyLike) return true;
            if (entityType.Contains("enemy")) return true;
            if (entityCategory is "beast" or "undead" or "construct"
                or "mechanical" or "elemental") return true;
            return false;
        }

        if (context is "ally" or "friendly")
            return entityType is "character" or "player" or "placedentity"
                   || entityType.Contains("turret");

        if (context == "player")
            return entityType is "character" or "player";

        if (context is "turret" or "device")
            return entityType == "placedentity" || entityType.Contains("turret");

        if (context == "construct") return entityCategory == "construct";
        if (context == "undead") return entityCategory == "undead";
        if (context == "mechanical") return entityCategory == "mechanical";

        return true;
    }

    private ICombatEntity? FindNearestValidTarget(ICombatEntity fromEntity,
                                                  double maxRange, string context,
                                                  List<ICombatEntity> availableEntities,
                                                  HashSet<ICombatEntity> exclude)
    {
        var fromPos = GetPosition(fromEntity);
        ICombatEntity? nearest = null;
        var nearestDist = double.PositiveInfinity;

        foreach (var entity in availableEntities)
        {
            if (exclude.Contains(entity)) continue;
            if (!IsValidContext(entity, context)) continue;

            var dist = Distance(fromPos, GetPosition(entity));
            if (dist <= maxRange && dist < nearestDist)
            {
                nearest = entity;
                nearestDist = dist;
            }
        }
        return nearest;
    }

    private static double DistanceAlongLine(Position lineStart,
                                            (double X, double Y) lineDirection,
                                            Position point)
    {
        var toPoint = (point.X - lineStart.X, point.Y - lineStart.Y);
        return DotProduct(toPoint, lineDirection);
    }

    private static double PerpendicularDistance(Position lineStart,
                                                (double X, double Y) lineDirection,
                                                Position point)
    {
        var distAlong = DistanceAlongLine(lineStart, lineDirection, point);
        var projX = lineStart.X + lineDirection.X * distAlong;
        var projY = lineStart.Y + lineDirection.Y * distAlong;
        var dx = point.X - projX;
        var dy = point.Y - projY;
        return Math.Sqrt(dx * dx + dy * dy);
    }
}
