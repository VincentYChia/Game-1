namespace Game1.Core.Combat;

/// <summary>
/// Port of Combat/projectile_system.py — travelling hitboxes with optional
/// gravity, homing, piercing, and AoE-on-impact.
/// </summary>
public sealed class ProjectileDefinition
{
    public string ProjectileId = "";
    public double Speed = 10.0;            // tiles/sec
    public double MaxRange = 15.0;         // tiles before despawn
    public double HitboxRadius = 0.3;
    public string SpriteId = "magic_bolt";
    public string? TrailType;
    public double Homing;                  // 0 = straight, 1.0 = missile lock
    public double Gravity;                 // tiles/sec² downward
    public bool Piercing;
    public Dictionary<string, object?>? AoeOnHit;   // hitbox def dict for explosion
    public double AoeDurationMs = 100.0;
    public Dictionary<string, object?> Visual = new();
    public List<string> Tags = new();
}

public sealed class Projectile
{
    public ProjectileDefinition Definition;
    public double X;
    public double Y;
    public string OwnerId;
    public Dictionary<string, object?> DamageContext;
    public bool Alive = true;
    public double DistanceTraveled;
    public HashSet<string> Hits = new();

    public double Vx;
    public double Vy;
    public double FacingAngle;

    public double? TargetX;
    public double? TargetY;

    public Projectile(ProjectileDefinition definition, (double X, double Y) startPos,
                      double directionAngle, string ownerId,
                      Dictionary<string, object?> damageContext)
    {
        Definition = definition;
        X = startPos.X;
        Y = startPos.Y;
        OwnerId = ownerId;
        DamageContext = damageContext;

        var angleRad = PyMath.Radians(directionAngle);
        Vx = Math.Cos(angleRad) * definition.Speed;
        Vy = Math.Sin(angleRad) * definition.Speed;
        FacingAngle = directionAngle;
    }

    public void Update(double dtSec)
    {
        if (!Alive) return;

        if (Definition.Gravity > 0)
            Vy += Definition.Gravity * dtSec;

        if (Definition.Homing > 0 && TargetX is not null)
        {
            var desiredDx = TargetX.Value - X;
            var desiredDy = TargetY!.Value - Y;
            var desiredAngle = Math.Atan2(desiredDy, desiredDx);
            var currentAngle = Math.Atan2(Vy, Vx);

            var angleDiff = PyMath.Mod(desiredAngle - currentAngle + Math.PI, 2 * Math.PI) - Math.PI;
            var steer = angleDiff * Definition.Homing * dtSec * 5.0;
            var newAngle = currentAngle + steer;

            var speed = Math.Sqrt(Vx * Vx + Vy * Vy);
            Vx = Math.Cos(newAngle) * speed;
            Vy = Math.Sin(newAngle) * speed;
        }

        var moveX = Vx * dtSec;
        var moveY = Vy * dtSec;
        X += moveX;
        Y += moveY;
        DistanceTraveled += Math.Sqrt(moveX * moveX + moveY * moveY);

        if (Math.Abs(Vx) > 0.001 || Math.Abs(Vy) > 0.001)
            FacingAngle = PyMath.Degrees(Math.Atan2(Vy, Vx));

        if (DistanceTraveled >= Definition.MaxRange)
            Alive = false;
    }
}

public sealed class ProjectileSystem
{
    public List<Projectile> Projectiles = new();
    public HitboxSystem HitboxSystemRef;

    public ProjectileSystem(HitboxSystem hitboxSystem)
    {
        HitboxSystemRef = hitboxSystem;
    }

    public Projectile Spawn(ProjectileDefinition projDef,
                            (double X, double Y) start, double directionAngle,
                            string ownerId, Dictionary<string, object?> damageContext,
                            (double X, double Y)? targetPos = null)
    {
        var proj = new Projectile(projDef, start, directionAngle, ownerId, damageContext);
        if (targetPos is not null && projDef.Homing > 0)
        {
            proj.TargetX = targetPos.Value.X;
            proj.TargetY = targetPos.Value.Y;
        }
        Projectiles.Add(proj);
        return proj;
    }

    public List<HitEvent> Update(double dtMs)
    {
        var dtSec = dtMs / 1000.0;
        var hits = new List<HitEvent>();
        var dead = new List<Projectile>();

        foreach (var proj in Projectiles)
        {
            proj.Update(dtSec);

            if (!proj.Alive)
            {
                dead.Add(proj);
                continue;
            }

            foreach (var hurtbox in HitboxSystemRef.Hurtboxes)
            {
                if (hurtbox.EntityId == proj.OwnerId) continue;
                if (proj.Hits.Contains(hurtbox.EntityId)) continue;
                if (hurtbox.Invulnerable) continue;

                var dx = hurtbox.WorldX - proj.X;
                var dy = hurtbox.WorldY - proj.Y;
                var distSq = dx * dx + dy * dy;
                var combinedR = proj.Definition.HitboxRadius + hurtbox.Radius;
                if (distSq <= combinedR * combinedR)
                {
                    proj.Hits.Add(hurtbox.EntityId);
                    hits.Add(new HitEvent(
                        attackerId: proj.OwnerId,
                        targetId: hurtbox.EntityId,
                        damageContext: proj.DamageContext,
                        hitPosition: (proj.X, proj.Y),
                        isProjectile: true));

                    if (!proj.Definition.Piercing)
                        proj.Alive = false;

                    if (proj.Definition.AoeOnHit is not null)
                    {
                        var aoeData = proj.Definition.AoeOnHit;
                        var aoeDef = new HitboxDefinition
                        {
                            Shape = aoeData.TryGetValue("shape", out var s) && s is string ss
                                ? ss : "circle",
                            Radius = aoeData.TryGetValue("radius", out var r) && r is double rd
                                ? rd : 2.0,
                        };
                        HitboxSystemRef.SpawnHitbox(
                            aoeDef, (proj.X, proj.Y), 0.0,
                            proj.OwnerId,
                            proj.Definition.AoeDurationMs,
                            proj.DamageContext);
                    }

                    if (!proj.Alive)
                    {
                        dead.Add(proj);
                        break;
                    }
                }
            }
        }

        foreach (var p in dead)
            Projectiles.Remove(p);

        return hits;
    }

    public void Clear() => Projectiles.Clear();

    public int Count => Projectiles.Count;
}
