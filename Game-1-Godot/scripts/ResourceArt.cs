using System.Collections.Generic;
using Game1.Core.World;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Rich, grand, VARIED meshes for harvestable resources. Each resource is ONE
/// clickable Node3D, but its many parts are MERGED into as few surfaces as
/// possible (a tree = one rigid trunk + one combined wind-swaying canopy; a rock
/// = one combined boulder) so dense forests stay cheap: ~2 draw calls per tree
/// instead of ~6. Species-styled (conifer vs broadleaf, per-species colour), the
/// canopy sways on ShaderLib.Wind while the trunk is rigid. Rocks are tinted by
/// ore/stone type with a glowing shard on high tiers. Every builder returns
/// (node, pickRadius, pickCenterY) so the click ray-pick matches the visual size,
/// and a StaticBody named "rbody" carries the collider (toggled on depletion).
/// </summary>
public static class ResourceArt
{
    private static readonly Dictionary<uint, Material> _leafCache = new();
    private static readonly Dictionary<uint, Material> _trunkCache = new();

    // unit primitives, appended into a combined SurfaceTool with a scale/offset
    // transform — one shared mesh per primitive kind (no per-part MeshInstance).
    private static readonly CylinderMesh UnitCone =
        new() { TopRadius = 0.03f, BottomRadius = 1f, Height = 1f, RadialSegments = 7 };
    private static readonly SphereMesh UnitBlob =
        new() { Radius = 1f, Height = 2f, RadialSegments = 8, Rings = 6 };

    // ---------------------------------------------------------------- TREES ---
    public static (Node3D Node, float Radius, float CenterY) Tree(
        string species, float scale, long seed, int tx, int ty)
    {
        var node = new Node3D();
        var (conifer, trunkCol, leafCol) = Style(species);
        var trunkMat = TrunkMat(trunkCol);
        var leafMat = LeafMat(leafCol);
        float h, trunkH;

        var fol = new SurfaceTool();
        fol.Begin(Mesh.PrimitiveType.Triangles);

        if (conifer)
        {
            trunkH = 4.6f * scale;
            node.AddChild(Cyl(0.13f * scale, 0.36f * scale, trunkH, trunkMat, trunkH * 0.5f));
            const int tiers = 6;
            for (var i = 0; i < tiers; i++)
            {
                var f = i / (float)(tiers - 1);                     // 0 bottom → 1 top
                var y = trunkH * 0.5f + f * trunkH * 1.08f;
                var rad = (3.0f - 2.35f * f) * scale;
                var th = (2.3f - 1.0f * f) * scale;
                AppendCone(fol, rad, th, new Vector3(0, y, 0));
            }
            h = trunkH * 0.5f + trunkH * 1.08f + 1.3f * scale;
        }
        else
        {
            trunkH = 3.6f * scale;
            node.AddChild(Cyl(0.18f * scale, 0.40f * scale, trunkH, trunkMat, trunkH * 0.5f));
            var cy = trunkH + 1.2f * scale;                          // canopy base
            AppendBlob(fol, 2.7f * scale, new Vector3(0, cy, 0));
            AppendBlob(fol, 2.0f * scale, new Vector3(1.15f * scale, cy + 1.0f * scale, 0.6f * scale));
            AppendBlob(fol, 1.9f * scale, new Vector3(-1.05f * scale, cy + 0.5f * scale, -0.6f * scale));
            AppendBlob(fol, 1.7f * scale, new Vector3(0.2f * scale, cy + 1.8f * scale, -0.3f * scale));
            AppendBlob(fol, 1.5f * scale, new Vector3(-0.6f * scale, cy + 1.3f * scale, 0.95f * scale));
            h = cy + 3.1f * scale;
        }
        node.AddChild(new MeshInstance3D { Mesh = fol.Commit(), MaterialOverride = leafMat });

        // trunk collision (canopy clears the head)
        var body = new StaticBody3D { Name = "rbody" };
        body.AddChild(new CollisionShape3D
        {
            Shape = new CylinderShape3D { Radius = 0.34f * scale, Height = trunkH },
            Position = new Vector3(0, trunkH * 0.5f, 0),
        });
        node.AddChild(body);
        return (node, h * 0.5f, h * 0.5f);
    }

    // ---------------------------------------------------------------- ROCKS ---
    public static (Node3D Node, float Radius, float CenterY) Rock(
        string oreType, int tier, float scale, long seed, int tx, int ty)
    {
        var node = new Node3D();
        var col = RockColor(oreType);
        var metallic = oreType.Contains("vein") || oreType.Contains("deposit")
            || oreType.Contains("lode") || oreType.Contains("node")
            || oreType.Contains("cache") || oreType.Contains("seam") ? 0.4f : 0.0f;
        var mat = new StandardMaterial3D { AlbedoColor = col, Roughness = 0.86f, Metallic = metallic };

        var lumpMesh = new SurfaceTool();
        lumpMesh.Begin(Mesh.PrimitiveType.Triangles);
        var body = new StaticBody3D { Name = "rbody" };
        var lumps = 3 + (int)(GeoNoise.Hash2D(tx, ty, seed + 7) * 2.99);   // 3-5
        var maxR = 0f;
        for (var i = 0; i < lumps; i++)
        {
            var hx = (float)GeoNoise.Hash2D(tx + i * 7, ty, seed + 11 + i);
            var hz = (float)GeoNoise.Hash2D(tx, ty + i * 7, seed + 13 + i);
            var rr = (0.85f + (float)GeoNoise.Hash2D(tx + i, ty + i, seed + 17 + i) * 0.95f) * scale;
            var off = new Vector3((hx - 0.5f) * 1.35f * scale, rr * 0.32f, (hz - 0.5f) * 1.35f * scale);
            // merged visual lump (squashed, slightly rotated) — one surface for all
            var basis = Basis.Identity.Rotated(Vector3.Up, hz * Mathf.Tau)
                .Scaled(new Vector3(rr * 1.2f, rr * 0.8f, rr * 1.1f));
            lumpMesh.AppendFrom(UnitBlob, 0, new Transform3D(basis, off));
            // convex collider per lump — sized to the VISUAL lump (basis scales it to
            // ~rr*1.2 wide) so you bump the rock where you see it instead of walking a
            // third of the way into a big boulder before colliding.
            body.AddChild(new CollisionShape3D
            { Shape = new SphereShape3D { Radius = rr * 1.08f }, Position = off });
            maxR = Mathf.Max(maxR, rr + off.Length());
        }
        node.AddChild(new MeshInstance3D { Mesh = lumpMesh.Commit(), MaterialOverride = mat });
        node.AddChild(body);

        if (tier >= 3)   // high-tier ore: a glowing shard poking from the rock
            node.AddChild(new MeshInstance3D
            {
                Mesh = new CylinderMesh
                { TopRadius = 0.001f, BottomRadius = 0.22f * scale, Height = 1.2f * scale, RadialSegments = 5 },
                MaterialOverride = new StandardMaterial3D
                {
                    AlbedoColor = col.Lerp(new Color(0.7f, 0.8f, 1f), 0.5f),
                    EmissionEnabled = true, Emission = new Color(0.4f, 0.6f, 1f),
                    EmissionEnergyMultiplier = 1.8f, Roughness = 0.25f,
                },
                Position = new Vector3(0, 0.62f * scale, 0),
            });
        return (node, maxR * 1.1f, maxR * 0.5f);
    }

    // ------------------------------------------------------------- helpers ---
    private static void AppendCone(SurfaceTool st, float rad, float height, Vector3 pos) =>
        st.AppendFrom(UnitCone, 0,
            new Transform3D(Basis.Identity.Scaled(new Vector3(rad, height, rad)), pos));

    private static void AppendBlob(SurfaceTool st, float rad, Vector3 pos) =>
        st.AppendFrom(UnitBlob, 0,
            new Transform3D(Basis.Identity.Scaled(new Vector3(rad, rad * 0.9f, rad)), pos));

    private static MeshInstance3D Cyl(float top, float bot, float height, Material m, float y) =>
        new()
        {
            Mesh = new CylinderMesh { TopRadius = top, BottomRadius = bot, Height = height, RadialSegments = 7 },
            MaterialOverride = m,
            Position = new Vector3(0, y, 0),
        };

    private static Material LeafMat(Color c)
    {
        var k = c.ToRgba32();
        if (!_leafCache.TryGetValue(k, out var m)) _leafCache[k] = m = ShaderLib.Wind(c, 0.9f);
        return m;
    }

    private static Material TrunkMat(Color c)
    {
        var k = c.ToRgba32();
        if (!_trunkCache.TryGetValue(k, out var m))
            _trunkCache[k] = m = new StandardMaterial3D { AlbedoColor = c, Roughness = 0.95f };
        return m;
    }

    private static Color Brown(float v) => new(v, v * 0.72f, v * 0.45f);

    private static (bool Conifer, Color Trunk, Color Leaf) Style(string sp)
    {
        if (sp.Contains("pine")) return (true, Brown(0.34f), new Color(0.15f, 0.37f, 0.19f));
        if (sp.Contains("ash")) return (true, Brown(0.40f), new Color(0.24f, 0.42f, 0.24f));
        if (sp.Contains("ironwood")) return (true, new Color(0.28f, 0.22f, 0.18f), new Color(0.16f, 0.32f, 0.22f));
        if (sp.Contains("ebony")) return (true, new Color(0.16f, 0.13f, 0.12f), new Color(0.12f, 0.26f, 0.18f));
        if (sp.Contains("birch")) return (false, new Color(0.82f, 0.80f, 0.74f), new Color(0.42f, 0.56f, 0.28f));
        if (sp.Contains("maple")) return (false, Brown(0.36f), new Color(0.78f, 0.42f, 0.20f));   // autumn
        if (sp.Contains("world")) return (false, new Color(0.50f, 0.45f, 0.55f), new Color(0.40f, 0.72f, 0.55f));
        return (false, Brown(0.33f), new Color(0.22f, 0.44f, 0.20f));   // oak / default
    }

    private static Color RockColor(string t)
    {
        if (t.Contains("copper")) return new Color(0.72f, 0.45f, 0.30f);
        if (t.Contains("iron") || t.Contains("steel")) return new Color(0.48f, 0.46f, 0.48f);
        if (t.Contains("tin")) return new Color(0.60f, 0.60f, 0.55f);
        if (t.Contains("mithril")) return new Color(0.55f, 0.65f, 0.75f);
        if (t.Contains("adamant")) return new Color(0.35f, 0.40f, 0.45f);
        if (t.Contains("orichalcum")) return new Color(0.60f, 0.50f, 0.30f);
        if (t.Contains("diamond") || t.Contains("quartz")) return new Color(0.80f, 0.85f, 0.90f);
        if (t.Contains("obsidian") || t.Contains("void")) return new Color(0.15f, 0.13f, 0.18f);
        if (t.Contains("marble")) return new Color(0.85f, 0.83f, 0.80f);
        if (t.Contains("granite")) return new Color(0.50f, 0.47f, 0.46f);
        if (t.Contains("basalt")) return new Color(0.28f, 0.28f, 0.30f);
        return new Color(0.45f, 0.45f, 0.48f);
    }
}
