using Game1.Core.World;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Explorable cave interiors. TerrainHeightField carves a WALKABLE grotto bowl
/// into the (fully collidable) heightfield at every cave/cavern chunk; this
/// builder roofs each one with a collidable stone dome that has a MOUTH you walk
/// in through, then fills the chamber with stalagmites/stalactites, crystals,
/// and a soft interior glow (bright + colored in crystal caverns). Deterministic
/// from (chunk, seed). Local interiors, not a single connected underworld.
///
/// Because the floor IS the carved heightfield, the player never goes below H —
/// so the existing collision + catastrophe floor-net keep working unchanged.
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
                if (!TerrainHeightField.IsCaveChunk(cx, cy)) continue;
                BuildGrotto(parent, map, seed, cx, cy);
                built++;
            }
        if (built > 0) GD.Print($"Caves in view: {built}");
    }

    private static void BuildGrotto(Node3D parent, WorldMap map, long seed,
                                    int cx, int cy)
    {
        var type = map.GetChunkData(cx, cy)?.ChunkType ?? "cave";
        var crystal = type == "crystal_cavern";

        var gx = cx * ChunkSize + 8.0;   // grotto centre (tile x → world x)
        var gz = cy * ChunkSize + 8.0;   // (tile y → world z)
        var floorY = TerrainHeightField.H(gx, gz);   // carved chamber floor
        var baseY = TerrainHeightField.H(
            gx + TerrainHeightField.CaveRadius + 2, gz);   // surrounding surface

        var domeR = (float)TerrainHeightField.CaveRadius + 1.5f;
        const float apex = 4.2f;          // ceiling rises this far above the rim
        var mouthAng = (float)(GeoNoise.Hash2D(cx, cy, seed + 7001) * Mathf.Tau);

        BuildDome(parent, new Vector3((float)gx, (float)baseY, (float)gz),
                  domeR, apex, mouthAng, crystal);

        // interior glow so the chamber reads (bright + colored in crystal caverns)
        parent.AddChild(new OmniLight3D
        {
            Position = new Vector3((float)gx, (float)floorY + 2.6f, (float)gz),
            OmniRange = domeR * 2.4f,
            LightEnergy = crystal ? 2.2f : 0.9f,
            LightColor = crystal ? new Color(0.60f, 0.50f, 1f)
                                 : new Color(1f, 0.82f, 0.55f),
            ShadowEnabled = false,
        });

        // stalagmites / stalactites / crystals
        var stoneMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.34f, 0.33f, 0.36f), Roughness = 0.95f };
        float Hsh(int k) =>
            (float)GeoNoise.Hash2D(cx * 71 + k, cy * 71 + k * 3, seed + 2200 + k);

        for (var k = 0; k < 10; k++)
        {
            var ang = Hsh(k) * Mathf.Tau;
            var rr = (0.2f + Hsh(k + 40) * 0.7f) * (float)TerrainHeightField.CaveRadius;
            var px = gx + Mathf.Cos(ang) * rr;
            var pz = gz + Mathf.Sin(ang) * rr;
            var py = TerrainHeightField.H(px, pz);

            if (crystal && k % 3 == 0)
            {
                AddCrystal(parent, new Vector3((float)px, (float)py, (float)pz),
                           0.8f + Hsh(k + 80) * 1.4f);
                continue;
            }
            // stalagmite up from the floor
            AddCone(parent, stoneMat, new Vector3((float)px, (float)py, (float)pz),
                    0.45f + Hsh(k + 160) * 0.4f, 0.8f + Hsh(k + 120) * 1.8f, false);
            // stalactite down from the dome ceiling above the same spot
            var a = Mathf.Acos(Mathf.Clamp(rr / domeR, 0f, 1f));
            var ceilY = baseY + apex * Mathf.Sin(a);
            AddCone(parent, stoneMat, new Vector3((float)px, (float)ceilY, (float)pz),
                    0.30f + Hsh(k + 200) * 0.3f, 0.6f + Hsh(k + 240) * 1.2f, true);
        }
    }

    /// <summary>A squashed stone dome (ceiling) over the grotto with a doorway
    /// gap around the mouth direction. Two-sided (seen inside &amp; out) with a
    /// trimesh collider so it genuinely encloses the chamber.</summary>
    private static void BuildDome(Node3D parent, Vector3 center, float domeR,
                                  float apex, float mouthAng, bool crystal)
    {
        const int rings = 6;
        const int seg = 22;
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);

        Vector3 V(int j, int k)
        {
            var a = j / (float)rings * (Mathf.Pi / 2f);
            var radius = domeR * Mathf.Cos(a);
            var hy = apex * Mathf.Sin(a);
            var th = k / (float)seg * Mathf.Tau;
            return center + new Vector3(Mathf.Cos(th) * radius, hy, Mathf.Sin(th) * radius);
        }

        for (var j = 0; j < rings; j++)
            for (var k = 0; k < seg; k++)
            {
                var th = k / (float)seg * Mathf.Tau;
                // leave a doorway in the lower wall around the mouth direction
                if (j < 3 && Mathf.Abs(Mathf.AngleDifference(th, mouthAng)) < 0.5f)
                    continue;
                var v00 = V(j, k);
                var v01 = V(j, k + 1);
                var v10 = V(j + 1, k);
                var v11 = V(j + 1, k + 1);
                st.AddVertex(v00); st.AddVertex(v10); st.AddVertex(v11);
                st.AddVertex(v00); st.AddVertex(v11); st.AddVertex(v01);
            }

        st.GenerateNormals();
        var mesh = st.Commit();

        var mi = new MeshInstance3D
        {
            Mesh = mesh,
            MaterialOverride = new StandardMaterial3D
            {
                AlbedoColor = crystal ? new Color(0.30f, 0.26f, 0.36f)
                                      : new Color(0.30f, 0.29f, 0.31f),
                Roughness = 0.97f,
                CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            },
        };
        parent.AddChild(mi);

        var body = new StaticBody3D();
        body.AddChild(new CollisionShape3D { Shape = mesh.CreateTrimeshShape() });
        mi.AddChild(body);
    }

    /// <summary>A stone spike — stalagmite (up from floor) or, inverted,
    /// a stalactite (down from ceiling).</summary>
    private static void AddCone(Node3D parent, Material mat, Vector3 anchor,
                                float radius, float height, bool inverted)
    {
        parent.AddChild(new MeshInstance3D
        {
            Mesh = new CylinderMesh
            {
                TopRadius = inverted ? radius : 0.02f,
                BottomRadius = inverted ? 0.02f : radius,
                Height = height,
                RadialSegments = 6,
            },
            MaterialOverride = mat,
            Position = anchor + new Vector3(0,
                inverted ? -height * 0.5f : height * 0.5f, 0),
        });
    }

    /// <summary>A small glowing crystal cluster (emissive), for crystal caverns.</summary>
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
            var h = (1.2f + i * 0.4f) * sc;
            parent.AddChild(new MeshInstance3D
            {
                Mesh = new CylinderMesh
                {
                    TopRadius = 0.001f,
                    BottomRadius = 0.18f * sc,
                    Height = h,
                    RadialSegments = 5,
                },
                MaterialOverride = mat,
                Position = ground + new Vector3((i - 1) * 0.35f * sc, h * 0.5f,
                                                (i % 2) * 0.3f * sc),
                RotationDegrees = new Vector3((i - 1) * 8f, 0, (i - 1) * 6f),
            });
        }
    }
}
