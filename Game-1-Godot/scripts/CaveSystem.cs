using Godot;
using Game1.Core.World;
using Game1.Core.World.Geography;

namespace Game1.Godot;

/// <summary>
/// Ground features — cave grottoes and quarry pits, rebuilt from scratch to sit
/// ON the ground (never floating) and to be impossible to get stuck in.
///
/// The earlier dome floated because it was a roof placed ABOVE a carved bowl at a
/// single height. This design has no roof: TerrainHeightField carves a walkable
/// bowl (the divot / pit — the solid floor and climbable walls), and everything
/// this builder adds is SEATED on the real terrain height at its own position, so
/// it follows the ground exactly:
///   • a RING OF BOULDERS around the rim (each a convex, collidable rock seated on
///     the terrain, with an ENTRANCE GAP) frames the hollow and gives it walls you
///     can't walk through — but it is open to the sky, so you can never be trapped.
///   • caves add a stone ENTRANCE ARCH + glowing crystals / stalagmites; crystal
///     caverns glow purple. Quarries add scattered ore boulders + a timber support.
/// Deterministic from (chunk, seed). Local features, not one connected underworld.
/// </summary>
public static class CaveSystem
{
    private const int ChunkSize = 16;

    public static void Build(Node3D root, WorldMap? map, long seed,
                             int cCX, int cCY, int radius)
    {
        var parent = new Node3D { Name = "Caves" };
        root.AddChild(parent);
        if (map is null) return;

        var built = 0;
        for (var cy = cCY - radius; cy <= cCY + radius; cy++)
            for (var cx = cCX - radius; cx <= cCX + radius; cx++)
            {
                if (TerrainHeightField.GrottoAt(cx, cy)) { BuildGrotto(parent, map, seed, cx, cy); built++; }
                // Quarries: the terrain carves the pit and the resource field seeds
                // harvestable stone/ore — no more elevated boulder stacks. (Merging
                // them into a few large terraced pits is a terrain-redo item.)
            }
        if (built > 0) GD.Print($"Ground features in view: {built}");
    }

    // ------------------------------------------------------------- CAVES ------
    private static void BuildGrotto(Node3D parent, WorldMap map, long seed, int cx, int cy)
    {
        var crystal = (map.GetChunkData(cx, cy)?.ChunkType ?? "cave") == "crystal_cavern";
        var gx = cx * ChunkSize + 8.0;
        var gz = cy * ChunkSize + 8.0;
        var floorY = TerrainHeightField.H(gx, gz);
        var R = (float)TerrainHeightField.CaveRadius;
        var mouthAng = (float)(GeoNoise.Hash2D(cx, cy, seed + 7001) * Mathf.Tau);

        var rockMat = new StandardMaterial3D
        { AlbedoColor = crystal ? new Color(0.36f, 0.31f, 0.44f) : new Color(0.37f, 0.36f, 0.39f),
          Roughness = 0.96f };

        // rim ring of boulders (an entrance gap faces mouthAng) — boulders -33%
        RimRing(parent, seed, cx, cy, gx, gz, R * 1.02f, 16, mouthAng, 0.55f, rockMat, 1.3f, 2.1f);
        // a stone entrance arch straddling the gap
        BuildArch(parent, gx, gz, R * 1.02f, mouthAng, rockMat);

        // interior glow
        parent.AddChild(new OmniLight3D
        {
            Position = new Vector3((float)gx, (float)floorY + 2.6f, (float)gz),
            OmniRange = R * 3.0f,
            LightEnergy = crystal ? 2.2f : 1.0f,
            LightColor = crystal ? new Color(0.60f, 0.50f, 1f) : new Color(1f, 0.82f, 0.55f),
            ShadowEnabled = false,
        });

        // seated floor formations
        var stoneMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.34f, 0.33f, 0.36f), Roughness = 0.95f };
        float Hsh(int k) => (float)GeoNoise.Hash2D(cx * 71 + k, cy * 71 + k * 3, seed + 2200 + k);
        for (var k = 0; k < 11; k++)
        {
            var ang = Hsh(k) * Mathf.Tau;
            var rr = (0.12f + Hsh(k + 40) * 0.55f) * R;
            var px = gx + Mathf.Cos(ang) * rr;
            var pz = gz + Mathf.Sin(ang) * rr;
            var at = new Vector3((float)px, TerrainHeightField.H(px, pz), (float)pz);
            if (crystal && k % 2 == 0) AddCrystal(parent, at, 0.9f + Hsh(k + 80) * 1.5f);
            else AddStalagmite(parent, stoneMat, at, 0.4f + Hsh(k + 160) * 0.45f, 0.9f + Hsh(k + 120) * 1.9f);
        }
    }

    // ------------------------------------------------------------ helpers -----
    /// <summary>A ring of seated boulders around a rim, leaving an entrance gap.</summary>
    private static void RimRing(Node3D parent, long seed, int cx, int cy,
                                double gx, double gz, float R, int count, float mouthAng,
                                float mouthHalf, StandardMaterial3D mat, float scaleMin,
                                float scaleMax)
    {
        for (var k = 0; k < count; k++)
        {
            var th = k / (float)count * Mathf.Tau;
            if (Mathf.Abs(Mathf.AngleDifference(th, mouthAng)) < mouthHalf) continue;
            var px = gx + Mathf.Cos(th) * R;
            var pz = gz + Mathf.Sin(th) * R;
            var at = new Vector3((float)px, TerrainHeightField.H(px, pz), (float)pz);
            var t = (float)GeoNoise.Hash2D(cx * 97 + k, cy * 97 + k * 7, seed + 900 + k);
            Boulder(parent, at, Mathf.Lerp(scaleMin, scaleMax, t), seed + 500 + k, cx + k * 3, cy + k, mat);
        }
    }

    /// <summary>A convex, collidable boulder seated so it half-rests in the ground.</summary>
    private static void Boulder(Node3D parent, Vector3 at, float scale, long seed,
                                int hx, int hy, StandardMaterial3D mat)
    {
        var node = new Node3D { Position = at };
        var body = new StaticBody3D();
        var lumps = 2 + (int)(GeoNoise.Hash2D(hx, hy, seed) * 2.99);
        for (var i = 0; i < lumps; i++)
        {
            var a = (float)GeoNoise.Hash2D(hx + i * 7, hy, seed + 11 + i);
            var b = (float)GeoNoise.Hash2D(hx, hy + i * 7, seed + 13 + i);
            var rr = (0.75f + (float)GeoNoise.Hash2D(hx + i, hy + i, seed + 17 + i) * 0.7f) * scale;
            var off = new Vector3((a - 0.5f) * 1.1f * scale, rr * 0.35f, (b - 0.5f) * 1.1f * scale);
            node.AddChild(new MeshInstance3D
            {
                Mesh = new SphereMesh { Radius = rr, Height = rr * 1.5f, RadialSegments = 6, Rings = 4 },
                MaterialOverride = mat,
                Position = off,
                Scale = new Vector3(1.2f, 0.82f, 1.1f),
                RotationDegrees = new Vector3((a - 0.5f) * 26f, b * 180f, (b - 0.5f) * 26f),
            });
            body.AddChild(new CollisionShape3D
            { Shape = new SphereShape3D { Radius = rr * 0.85f }, Position = off });
        }
        node.AddChild(body);
        parent.AddChild(node);
    }

    /// <summary>A stone entrance arch (two collidable pillars + a lintel overhead)
    /// straddling the rim gap, each piece seated on the terrain.</summary>
    private static void BuildArch(Node3D parent, double gx, double gz, float R,
                                  float ang, StandardMaterial3D mat)
    {
        var dir = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
        var perp = new Vector2(-dir.Y, dir.X);
        const float halfSpan = 2.4f, pillarH = 4.2f;

        Vector3 Pillar(float s)
        {
            var px = gx + dir.X * R + perp.X * s;
            var pz = gz + dir.Y * R + perp.Y * s;
            var gy = TerrainHeightField.H(px, pz);
            var pos = new Vector3((float)px, gy + pillarH * 0.5f - 0.4f, (float)pz);
            var size = new Vector3(0.9f, pillarH, 0.9f);
            parent.AddChild(new MeshInstance3D { Mesh = new BoxMesh { Size = size }, MaterialOverride = mat, Position = pos });
            var body = new StaticBody3D { Position = pos };
            body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });
            parent.AddChild(body);
            return new Vector3((float)px, gy, (float)pz);
        }
        var a = Pillar(halfSpan);
        var b = Pillar(-halfSpan);
        // lintel across the top (visual — overhead, so no collider to clip into)
        var mid = (a + b) * 0.5f;
        var topY = Mathf.Max(a.Y, b.Y) + pillarH - 0.4f;
        parent.AddChild(new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(halfSpan * 2f + 1.2f, 1.0f, 1.1f) },
            MaterialOverride = mat,
            Position = new Vector3(mid.X, topY, mid.Z),
            RotationDegrees = new Vector3(0, Mathf.RadToDeg(Mathf.Atan2(-(b.Z - a.Z), b.X - a.X)), 0),
        });
    }

    private static void AddStalagmite(Node3D parent, Material mat, Vector3 at,
                                      float radius, float height)
    {
        parent.AddChild(new MeshInstance3D
        {
            Mesh = new CylinderMesh { TopRadius = 0.02f, BottomRadius = radius, Height = height, RadialSegments = 6 },
            MaterialOverride = mat,
            Position = at + new Vector3(0, height * 0.5f, 0),
        });
    }

    /// <summary>A glowing crystal cluster with a convex collider on the tall spire.</summary>
    private static void AddCrystal(Node3D parent, Vector3 ground, float sc)
    {
        var mat = new StandardMaterial3D
        {
            AlbedoColor = new Color(0.55f, 0.42f, 0.85f),
            EmissionEnabled = true,
            Emission = new Color(0.50f, 0.35f, 0.95f),
            EmissionEnergyMultiplier = 2.5f,
            Roughness = 0.2f,
            Metallic = 0.1f,
        };
        for (var i = 0; i < 3; i++)
        {
            var h = (1.3f + i * 0.5f) * sc;
            var off = new Vector3((i - 1) * 0.35f * sc, h * 0.5f, (i % 2) * 0.3f * sc);
            parent.AddChild(new MeshInstance3D
            {
                Mesh = new CylinderMesh { TopRadius = 0.001f, BottomRadius = 0.19f * sc, Height = h, RadialSegments = 5 },
                MaterialOverride = mat,
                Position = ground + off,
                RotationDegrees = new Vector3((i - 1) * 8f, 0, (i - 1) * 6f),
            });
            if (i == 1)
            {
                var body = new StaticBody3D { Position = ground + new Vector3(0, h * 0.5f, 0) };
                body.AddChild(new CollisionShape3D { Shape = new CylinderShape3D { Radius = 0.22f * sc, Height = h } });
                parent.AddChild(body);
            }
        }
    }
}
