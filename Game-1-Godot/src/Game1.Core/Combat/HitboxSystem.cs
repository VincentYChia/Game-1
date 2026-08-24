namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/hitbox_system.py — melee collision. World-space tiles;
/// angles in degrees, 0 = right, 90 = down (pygame y-down; the Godot
/// presentation layer maps to 3D, the sim keeps this convention).
/// </summary>
public sealed class HitboxDefinition
{
    public string Shape = "arc";          // "circle", "arc", "rect", "line"
    public double Radius = 1.5;
    public double ArcDegrees = 90.0;
    public double Width = 1.0;
    public double Height = 0.5;
    public double Length = 2.0;
    public double OffsetForward = 0.8;
    public double OffsetLateral = 0.0;
    public bool Piercing;

    public (double X, double Y) ComputeWorldPosition(
        double entityX, double entityY, double facingAngle)
    {
        var angleRad = PyMath.Radians(facingAngle);
        var wx = entityX + Math.Cos(angleRad) * OffsetForward;
        var wy = entityY + Math.Sin(angleRad) * OffsetForward;

        if (OffsetLateral != 0)
        {
            var perpRad = angleRad + Math.PI / 2.0;
            wx += Math.Cos(perpRad) * OffsetLateral;
            wy += Math.Sin(perpRad) * OffsetLateral;
        }

        return (wx, wy);
    }
}

public sealed class ActiveHitbox
{
    public HitboxDefinition Definition;
    public double WorldX;
    public double WorldY;
    public double FacingAngle;
    public string OwnerId;
    public double RemainingMs;
    public Dictionary<string, object?> DamageContext;
    public HashSet<string> Hits = new();

    public ActiveHitbox(HitboxDefinition definition, double worldX, double worldY,
                        double facingAngle, string ownerId, double durationMs,
                        Dictionary<string, object?> damageContext)
    {
        Definition = definition;
        WorldX = worldX;
        WorldY = worldY;
        FacingAngle = facingAngle;
        OwnerId = ownerId;
        RemainingMs = durationMs;
        DamageContext = damageContext;
    }
}

public sealed class Hurtbox
{
    public string EntityId;
    public double Radius;
    public double WorldX;
    public double WorldY;
    public bool Invulnerable;

    public Hurtbox(string entityId, double radius)
    {
        EntityId = entityId;
        Radius = radius;
    }
}

public sealed class HitboxSystem
{
    public List<ActiveHitbox> ActiveHitboxes = new();
    // Python dict preserves insertion order; iteration order matters for the
    // order hit events are emitted in — mirror with an ordered list + index.
    private readonly List<Hurtbox> _hurtboxOrder = new();
    private readonly Dictionary<string, Hurtbox> _hurtboxes = new();

    public IReadOnlyList<Hurtbox> Hurtboxes => _hurtboxOrder;

    public Hurtbox RegisterHurtbox(string entityId, double radius)
    {
        var hb = new Hurtbox(entityId, radius);
        // Python dict: assigning an existing key keeps its insertion slot.
        if (_hurtboxes.TryGetValue(entityId, out var existing))
            _hurtboxOrder[_hurtboxOrder.IndexOf(existing)] = hb;
        else
            _hurtboxOrder.Add(hb);
        _hurtboxes[entityId] = hb;
        return hb;
    }

    public void UnregisterHurtbox(string entityId)
    {
        if (_hurtboxes.Remove(entityId, out var hb))
            _hurtboxOrder.Remove(hb);
    }

    public Hurtbox? GetHurtbox(string entityId) =>
        _hurtboxes.TryGetValue(entityId, out var hb) ? hb : null;

    public void UpdateHurtboxPosition(string entityId, double worldX, double worldY)
    {
        if (_hurtboxes.TryGetValue(entityId, out var hb))
        {
            hb.WorldX = worldX;
            hb.WorldY = worldY;
        }
    }

    public ActiveHitbox SpawnHitbox(HitboxDefinition definition,
                                    (double X, double Y) worldPos,
                                    double facingAngle, string ownerId,
                                    double durationMs,
                                    Dictionary<string, object?> damageContext)
    {
        var hb = new ActiveHitbox(definition, worldPos.X, worldPos.Y,
                                  facingAngle, ownerId, durationMs, damageContext);
        ActiveHitboxes.Add(hb);
        return hb;
    }

    /// <summary>Advance timers, check collisions, return hits (in Python's
    /// hitbox-then-hurtbox iteration order).</summary>
    public List<HitEvent> Update(double dtMs)
    {
        var hits = new List<HitEvent>();
        var expired = new List<ActiveHitbox>();

        foreach (var hitbox in ActiveHitboxes)
        {
            hitbox.RemainingMs -= dtMs;
            if (hitbox.RemainingMs <= 0)
            {
                expired.Add(hitbox);
                continue;
            }

            foreach (var hurtbox in _hurtboxOrder)
            {
                if (hurtbox.EntityId == hitbox.OwnerId) continue;
                if (hitbox.Hits.Contains(hurtbox.EntityId) && !hitbox.Definition.Piercing) continue;
                if (hurtbox.Invulnerable) continue;

                if (CheckCollision(hitbox, hurtbox))
                {
                    hitbox.Hits.Add(hurtbox.EntityId);
                    hits.Add(new HitEvent(
                        attackerId: hitbox.OwnerId,
                        targetId: hurtbox.EntityId,
                        damageContext: hitbox.DamageContext,
                        hitPosition: (hurtbox.WorldX, hurtbox.WorldY),
                        isProjectile: false));
                }
            }
        }

        foreach (var hb in expired)
            ActiveHitboxes.Remove(hb);

        return hits;
    }

    public void Clear() => ActiveHitboxes.Clear();

    public bool CheckCollision(ActiveHitbox hitbox, Hurtbox hurtbox) =>
        hitbox.Definition.Shape switch
        {
            "circle" => CollidesCircleCircle(hitbox, hurtbox),
            "arc" => CollidesArcCircle(hitbox, hurtbox),
            "rect" => CollidesRectCircle(hitbox, hurtbox),
            "line" => CollidesLineCircle(hitbox, hurtbox),
            _ => false,
        };

    private static bool CollidesCircleCircle(ActiveHitbox hitbox, Hurtbox hurtbox)
    {
        var dx = hurtbox.WorldX - hitbox.WorldX;
        var dy = hurtbox.WorldY - hitbox.WorldY;
        var distSq = dx * dx + dy * dy;
        var combinedR = hitbox.Definition.Radius + hurtbox.Radius;
        return distSq <= combinedR * combinedR;
    }

    private static bool CollidesArcCircle(ActiveHitbox hitbox, Hurtbox hurtbox)
    {
        var dx = hurtbox.WorldX - hitbox.WorldX;
        var dy = hurtbox.WorldY - hitbox.WorldY;
        var dist = Math.Sqrt(dx * dx + dy * dy);

        if (dist > hitbox.Definition.Radius + hurtbox.Radius)
            return false;

        var angleToTarget = PyMath.Degrees(Math.Atan2(dy, dx));
        var angleDiff = PyMath.Mod(angleToTarget - hitbox.FacingAngle + 180, 360) - 180;
        var halfArc = hitbox.Definition.ArcDegrees / 2.0;

        if (Math.Abs(angleDiff) <= halfArc)
            return true;

        // Edge overlap: hurtbox circle may still clip the arc's edge rays.
        foreach (var sign in new[] { 1, -1 })
        {
            var edgeAngle = hitbox.FacingAngle + sign * halfArc;
            var edgeRad = PyMath.Radians(edgeAngle);
            var rayEndX = hitbox.WorldX + Math.Cos(edgeRad) * hitbox.Definition.Radius;
            var rayEndY = hitbox.WorldY + Math.Sin(edgeRad) * hitbox.Definition.Radius;

            var segDx = rayEndX - hitbox.WorldX;
            var segDy = rayEndY - hitbox.WorldY;
            var segLenSq = segDx * segDx + segDy * segDy;
            if (segLenSq < 0.0001) continue;

            var t = Math.Max(0.0, Math.Min(1.0,
                ((hurtbox.WorldX - hitbox.WorldX) * segDx +
                 (hurtbox.WorldY - hitbox.WorldY) * segDy) / segLenSq));

            var closestX = hitbox.WorldX + t * segDx;
            var closestY = hitbox.WorldY + t * segDy;
            var ex = hurtbox.WorldX - closestX;
            var ey = hurtbox.WorldY - closestY;
            var edgeDistSq = ex * ex + ey * ey;
            if (edgeDistSq <= hurtbox.Radius * hurtbox.Radius)
                return true;
        }

        return false;
    }

    private static bool CollidesRectCircle(ActiveHitbox hitbox, Hurtbox hurtbox)
    {
        var dx = hurtbox.WorldX - hitbox.WorldX;
        var dy = hurtbox.WorldY - hitbox.WorldY;
        var angleRad = PyMath.Radians(-hitbox.FacingAngle);
        var cosA = Math.Cos(angleRad);
        var sinA = Math.Sin(angleRad);
        var localX = dx * cosA - dy * sinA;
        var localY = dx * sinA + dy * cosA;

        var halfW = hitbox.Definition.Width / 2.0;
        var halfH = hitbox.Definition.Height / 2.0;
        var closestX = Math.Max(-halfW, Math.Min(localX, halfW));
        var closestY = Math.Max(-halfH, Math.Min(localY, halfH));

        var ex = localX - closestX;
        var ey = localY - closestY;
        var distSq = ex * ex + ey * ey;
        return distSq <= hurtbox.Radius * hurtbox.Radius;
    }

    private static bool CollidesLineCircle(ActiveHitbox hitbox, Hurtbox hurtbox)
    {
        var angleRad = PyMath.Radians(hitbox.FacingAngle);
        var endX = hitbox.WorldX + Math.Cos(angleRad) * hitbox.Definition.Length;
        var endY = hitbox.WorldY + Math.Sin(angleRad) * hitbox.Definition.Length;

        var segDx = endX - hitbox.WorldX;
        var segDy = endY - hitbox.WorldY;
        var segLenSq = segDx * segDx + segDy * segDy;

        if (segLenSq < 0.0001)
        {
            var pdx = hurtbox.WorldX - hitbox.WorldX;
            var pdy = hurtbox.WorldY - hitbox.WorldY;
            return pdx * pdx + pdy * pdy <= hurtbox.Radius * hurtbox.Radius;
        }

        var t = Math.Max(0.0, Math.Min(1.0,
            ((hurtbox.WorldX - hitbox.WorldX) * segDx +
             (hurtbox.WorldY - hitbox.WorldY) * segDy) / segLenSq));

        var closestX = hitbox.WorldX + t * segDx;
        var closestY = hitbox.WorldY + t * segDy;
        var ex = hurtbox.WorldX - closestX;
        var ey = hurtbox.WorldY - closestY;
        var distSq = ex * ex + ey * ey;
        return distSq <= hurtbox.Radius * hurtbox.Radius;
    }
}
