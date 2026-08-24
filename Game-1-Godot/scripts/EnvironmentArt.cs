using System.Collections.Generic;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Modular environment-art library — the placeholder-to-real-art seam.
///
/// Every visible decoration (tree, boulder, bush, grass, flower, crystal) is
/// COMPOSED from a small palette of primitive meshes: trunk, pine tier, leaf
/// blob, boulder, bush, grass blade, stem, blossom, crystal. Each primitive is
/// rendered as ONE MultiMesh, so the whole world's foliage costs a handful of
/// draw calls no matter how dense it gets.
///
/// The art is stylized-low-poly PLACEHOLDER today, but the architecture is the
/// point — it is designed so the eventual art drops in without touching callers:
///   • new decoration  → add a Place*() composer (+ a decor-table entry);
///   • swap placeholder → real art → replace a primitive's Mesh with a loaded
///     .glb/.tscn in Prim() — every Place*() and the whole scatter keep working;
///   • retune look      → change a primitive's mesh/color/roughness in one line.
///
/// Usage: new EnvironmentArt() → Place*() per position → Commit(parent).
/// </summary>
public sealed class EnvironmentArt
{
    private readonly Dictionary<string, (Mesh Mesh, Material Mat)> _prim = new();
    private readonly Dictionary<string, List<Transform3D>> _batch = new();

    public EnvironmentArt()
    {
        // ---- the primitive palette (placeholders — swap Mesh for real art) ----
        Prim("trunk", new CylinderMesh { TopRadius = 0.13f, BottomRadius = 0.18f, Height = 1f },
             new Color(0.36f, 0.26f, 0.16f));
        Prim("pine", Cone(0.62f), new Color(0.15f, 0.37f, 0.19f), wind: true);   // conifer tiers
        Prim("leaf", LowSphere(), new Color(0.22f, 0.46f, 0.22f), wind: true);   // broadleaf canopy
        Prim("boulder", LowSphere(), new Color(0.47f, 0.45f, 0.42f), 0.85f);
        Prim("bush", LowSphere(), new Color(0.24f, 0.42f, 0.20f), wind: true);
        Prim("grass", Cone(0.16f), new Color(0.36f, 0.53f, 0.27f), wind: true);  // tuft
        Prim("stem", new CylinderMesh { TopRadius = 0.03f, BottomRadius = 0.04f, Height = 1f },
             new Color(0.30f, 0.45f, 0.24f), wind: true);
        Prim("crystal", Cone(0.30f), new Color(0.56f, 0.46f, 0.80f), 0.25f);
        Prim("bloomA", LowSphere(), new Color(0.92f, 0.78f, 0.32f), wind: true);  // yellow blossom
        Prim("bloomB", LowSphere(), new Color(0.86f, 0.38f, 0.48f), wind: true);  // pink blossom
        // richer undergrowth
        Prim("fern", Cone(0.7f), new Color(0.22f, 0.44f, 0.20f), wind: true);
        Prim("mushcap", LowSphere(), new Color(0.72f, 0.28f, 0.24f));            // red cap
        Prim("mushstem", new CylinderMesh { TopRadius = 0.05f, BottomRadius = 0.06f, Height = 1f },
             new Color(0.90f, 0.86f, 0.72f));
        Prim("moss", LowSphere(), new Color(0.28f, 0.46f, 0.24f), wind: true);
        Prim("log", new CylinderMesh { TopRadius = 0.22f, BottomRadius = 0.24f, Height = 1f },
             new Color(0.34f, 0.25f, 0.16f), 0.95f);
    }

    // Low-poly primitives: a 7-sided cone (via a near-zero-top cylinder) and a
    // coarse sphere read as stylized foliage/stone. Unit-sized; scaled per use.
    private static Mesh Cone(float radius) =>
        new CylinderMesh { TopRadius = 0.001f, BottomRadius = radius, Height = 1f, RadialSegments = 7 };
    private static Mesh LowSphere() =>
        new SphereMesh { Radius = 0.5f, Height = 1f, RadialSegments = 6, Rings = 4 };

    private void Prim(string key, Mesh mesh, Color color, float rough = 0.92f,
                      bool wind = false)
    {
        // Foliage rides a shared vertex-WIND shader (per-key albedo, one shader)
        // so the world breathes; rigid props stay on a plain lit material.
        Material mat = wind
            ? ShaderLib.Wind(color, rough)
            : new StandardMaterial3D { AlbedoColor = color, Roughness = rough };
        _prim[key] = (mesh, mat);
        _batch[key] = new List<Transform3D>();
    }

    private void Add(string key, Vector3 pos, Vector3 scale, float yaw) =>
        _batch[key].Add(new Transform3D(
            Basis.Identity.Scaled(scale).Rotated(Vector3.Up, yaw), pos));

    // ---- composers: a "decoration" is a few primitives stacked ----

    /// <summary>Conifer: trunk + 3 shrinking foliage tiers.</summary>
    public void PlacePine(Vector3 ground, float sc, float yaw)
    {
        var th = 1.6f * sc;
        Add("trunk", ground + Vector3.Up * (th * 0.5f), new Vector3(sc, th, sc), yaw);
        Add("pine", ground + Vector3.Up * (th * 0.85f), new Vector3(1.7f * sc, 1.7f * sc, 1.7f * sc), yaw);
        Add("pine", ground + Vector3.Up * (th * 1.35f), new Vector3(1.2f * sc, 1.5f * sc, 1.2f * sc), yaw);
        Add("pine", ground + Vector3.Up * (th * 1.8f), new Vector3(0.7f * sc, 1.2f * sc, 0.7f * sc), yaw);
    }

    /// <summary>Broadleaf: trunk + a rounded canopy.</summary>
    public void PlaceBroadleaf(Vector3 ground, float sc, float yaw)
    {
        var th = 1.7f * sc;
        Add("trunk", ground + Vector3.Up * (th * 0.5f), new Vector3(sc, th, sc), yaw);
        Add("leaf", ground + Vector3.Up * (th + 0.7f * sc), new Vector3(2.0f * sc, 1.8f * sc, 2.0f * sc), yaw);
    }

    public void PlaceBoulder(Vector3 ground, Vector3 size, float yaw) =>
        Add("boulder", ground + Vector3.Up * (size.Y * 0.35f), size, yaw);

    public void PlaceBush(Vector3 ground, float r, float yaw) =>
        Add("bush", ground + Vector3.Up * (r * 0.4f), new Vector3(r, r * 0.8f, r), yaw);

    public void PlaceGrass(Vector3 ground, float sc, float yaw) =>
        Add("grass", ground + Vector3.Up * (0.35f * sc), new Vector3(sc, 0.75f * sc, sc), yaw);

    public void PlaceFlower(Vector3 ground, float sc, float yaw, bool yellow)
    {
        Add("stem", ground + Vector3.Up * (0.3f * sc), new Vector3(sc, 0.6f * sc, sc), yaw);
        Add(yellow ? "bloomA" : "bloomB",
            ground + Vector3.Up * (0.62f * sc),
            new Vector3(0.17f * sc, 0.17f * sc, 0.17f * sc), yaw);
    }

    public void PlaceCrystal(Vector3 ground, float sc, float yaw)
    {
        Add("crystal", ground + Vector3.Up * (0.7f * sc), new Vector3(0.5f * sc, 1.4f * sc, 0.5f * sc), yaw);
        Add("crystal", ground + Vector3.Up * (0.45f * sc), new Vector3(0.32f * sc, 0.9f * sc, 0.32f * sc), yaw + 1.2f);
    }

    /// <summary>A low spray of fern fronds.</summary>
    public void PlaceFern(Vector3 ground, float sc, float yaw)
    {
        Add("fern", ground + Vector3.Up * (0.35f * sc), new Vector3(1.1f * sc, 0.7f * sc, 1.1f * sc), yaw);
        Add("fern", ground + Vector3.Up * (0.30f * sc), new Vector3(0.8f * sc, 0.55f * sc, 0.8f * sc), yaw + 1.1f);
    }

    /// <summary>Capped mushroom (stem + cap).</summary>
    public void PlaceMushroom(Vector3 ground, float sc, float yaw)
    {
        var h = 0.32f * sc;
        Add("mushstem", ground + Vector3.Up * (h * 0.5f), new Vector3(sc, h, sc), yaw);
        Add("mushcap", ground + Vector3.Up * (h + 0.06f * sc),
            new Vector3(0.34f * sc, 0.22f * sc, 0.34f * sc), yaw);
    }

    /// <summary>A dense clump of taller grass blades.</summary>
    public void PlaceTallGrass(Vector3 ground, float sc, float yaw)
    {
        for (var i = 0; i < 3; i++)
            Add("grass", ground + Vector3.Up * (0.6f * sc),
                new Vector3(0.7f * sc, 1.4f * sc, 0.7f * sc), yaw + i * 1.2f);
    }

    /// <summary>A boulder wearing a cap of moss.</summary>
    public void PlaceMossRock(Vector3 ground, Vector3 size, float yaw)
    {
        Add("boulder", ground + Vector3.Up * (size.Y * 0.35f), size, yaw);
        Add("moss", ground + Vector3.Up * (size.Y * 0.55f),
            new Vector3(size.X * 0.7f, size.Y * 0.35f, size.Z * 0.7f), yaw);
    }

    /// <summary>A fallen log lying on its side.</summary>
    public void PlaceLog(Vector3 ground, float sc, float yaw)
    {
        var basis = Basis.Identity
            .Scaled(new Vector3(sc, 1.8f * sc, sc))
            .Rotated(Vector3.Forward, Mathf.Pi * 0.5f)   // lay the cylinder down
            .Rotated(Vector3.Up, yaw);
        _batch["log"].Add(new Transform3D(basis, ground + Vector3.Up * (0.24f * sc)));
    }

    /// <summary>Emit one MultiMeshInstance3D per primitive batch under parent.</summary>
    public void Commit(Node3D parent)
    {
        foreach (var (key, xforms) in _batch)
        {
            if (xforms.Count == 0) continue;
            var (mesh, mat) = _prim[key];
            var mm = new MultiMesh
            {
                Mesh = mesh,
                TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
                InstanceCount = xforms.Count,
            };
            for (var i = 0; i < xforms.Count; i++)
                mm.SetInstanceTransform(i, xforms[i]);
            parent.AddChild(new MultiMeshInstance3D
            { Name = $"env_{key}", Multimesh = mm, MaterialOverride = mat });
        }
    }
}
