using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core.Data;
using Game1.Core.World;
using Godot;

namespace Game1.Godot;

/// <summary>
/// The ONE harvestable-resource system, run for every streamed window.
///
/// Every tree / ore / stone the player sees is a REAL certified node
/// (NaturalResourceRuntime) — there are no decorative stand-ins masquerading as
/// harvestable (ground cover is the ONLY decoration, and it is unmistakably
/// small). Distribution is a smooth DENSITY FIELD × biome profile × tier/rarity:
/// woods thicken and thin gradually, higher tiers are rarer, and everything is
/// spaced (Poisson), kept off roads/villages/water/cliffs, and seated on the mesh
/// — all through the shared <see cref="WorldContext"/>, so the frontier gets the
/// exact same treatment as the settled core.
///
/// Rendering delegates to the proven <see cref="ResourceArt"/> node builders and
/// registers through the certified <c>CombatWorld.RegisterResource</c> seam
/// unchanged — this class owns only WHERE resources go, not the harvest rules.
/// </summary>
public sealed class ResourcePlacer
{
    // Perf backstop AND anti-barren-corner headroom: the window is (2R+1)² chunks, so a
    // uniformly dense biome must fit UNDER this or the FIFO chunk drain leaves a barren
    // far corner. Deposit density (below) is tuned so even a thicket window requests fewer
    // than this, so the cap is a true backstop, not a routinely-hit ceiling.
    private const int ResourceCap = 1700;
    // No single resource type may carpet a window: a hard per-type budget keeps any
    // one rock/crystal/tree from taking over a biome (the "purple stone ring" bug).
    private const int TypeWindowCap = 150;
    // Resources refuse steep ground — 0.42 (~23°) keeps them off mountain FACES and
    // cliffs (a stone circle stuck to a sheer wall reads as broken), not just verticals.
    private const float MaxResourceSlope = 0.42f;
    // DEPOSITS: instead of 14 independent random slots per chunk (a "plopped-down"
    // carpet), resources gather into a FEW coherent, MONOTYPE stands — a copper vein, a
    // birch grove, a boulder field — each with a dense core that THINS OUTWARD
    // (diminishing returns) and open ground between. Fewer, larger structures that add
    // to the world instead of speckling it.
    private const int MaxDepositsPerChunk = 2;
    private const float DepositsPerDensity = 0.7f;    // biome woodedness → expected deposits (kept under the cap)
    // Definitive on-road gate: anything on the carved corridor (crown or graded shoulder)
    // is rejected outright, so a stand never sprouts through the road surface.
    private const float OnRoadReject = 0.04f;

    private readonly ResourceNodeDatabase _db;
    private readonly ChunkGenerator _chunkGen;
    private readonly long _seed;
    private int _count;
    private readonly Dictionary<string, int> _typeCount = new();
    private static StandardMaterial3D? _fishMat;

    // ---- headless debug (G1_DEBUG): run every placement gate but build NO visuals and
    // register nothing — just record where each node WOULD land, for statistical checks. ----
    private bool _dryRun;
    private readonly List<(Vector2 Pos, string Cat, string Id)> _dryLog = new();

    // ---- live spawn diagnostics (F9 overlay) ----
    private int _treeC, _oreC, _stoneC, _fishC;
    private int _blkSlope, _blkCap, _blkOccupy, _blkRoad, _blkWater, _blkStation, _blkDensity;
    private int _remaining;
    /// <summary>Human-readable summary of the last completed window's placement —
    /// how many of each family rendered, and WHY slots were rejected — so a flyover
    /// confirms resources still spawn and the new caps aren't starving anything.</summary>
    public string LastSummary { get; private set; } = "resources: (pending first window)";

    public ResourcePlacer(ResourceNodeDatabase db, ChunkGenerator chunkGen, long seed)
    {
        _db = db;
        _chunkGen = chunkGen;
        _seed = seed;
    }

    /// <summary>Enqueue this window's harvestable placement as ONE step per chunk,
    /// so it streams in over the next frames instead of hard-freezing on a chunk
    /// crossing. Each chunk registers its nodes with the combat runtime as it builds
    /// (harvest just lights up as resources pop in). The parent is validity-checked
    /// so a step left over from a superseded window is a safe no-op.</summary>
    public void QueueWindow(Node3D parent, WorldContext ctx, CombatWorld combat,
                            Queue<System.Action> queue)
    {
        _fishMat ??= new StandardMaterial3D { AlbedoColor = new Color(0.2f, 0.5f, 0.9f) };
        _count = 0;
        _typeCount.Clear();
        _treeC = _oreC = _stoneC = _fishC = 0;
        _blkSlope = _blkCap = _blkOccupy = _blkRoad = _blkWater = _blkStation = _blkDensity = 0;
        _remaining = (2 * ctx.ResourceRadius + 1) * (2 * ctx.ResourceRadius + 1);
        for (var cy = ctx.CenterCY - ctx.ResourceRadius; cy <= ctx.CenterCY + ctx.ResourceRadius; cy++)
            for (var cx = ctx.CenterCX - ctx.ResourceRadius; cx <= ctx.CenterCX + ctx.ResourceRadius; cx++)
            {
                int ccx = cx, ccy = cy;
                queue.Enqueue(() =>
                {
                    if (!GodotObject.IsInstanceValid(parent)) return;
                    PlaceChunk(parent, ctx, combat, ccx, ccy);
                });
            }
    }

    private void PlaceChunk(Node3D parent, WorldContext ctx, CombatWorld combat, int cx, int cy)
    {
        var type = ctx.ChunkType(cx, cy);
        if (type.Contains("lake") || type.Contains("river") || type.Contains("flooded"))
        {
            // certified fishing-spot placement on water
            var (gt, gd) = ctx.GeoInfo(cx, cy);
            var chunk = _chunkGen.Generate(cx, cy, seed: ctx.ChunkSeed(cx, cy),
                geoChunkType: gt, geoDangerLevel: gd);
            foreach (var res in chunk.Resources)
                if (res.ResourceType.Contains("fishing"))
                    RenderFishing(parent, ctx, combat, res.ResourceType,
                                  (int)res.Tier, res.X, res.Y);
            FinishChunk();
            return;
        }
        PlaceLand(parent, ctx, combat, cx, cy, type, ctx.Danger(cx, cy));
        FinishChunk();
    }

    /// <summary>Count a chunk done; when the whole window's chunks have streamed in,
    /// publish + log the spawn diagnostics.</summary>
    private void FinishChunk()
    {
        if (--_remaining > 0) return;
        LastSummary =
            $"resources {_count}  (tree {_treeC}  ore {_oreC}  stone {_stoneC}  fish {_fishC})"
            + $"   ·   blocked  slope {_blkSlope}  typecap {_blkCap}  spacing {_blkOccupy}"
            + $"  road {_blkRoad}  water {_blkWater}  station {_blkStation}  density {_blkDensity}";
        GD.Print("[ResDebug] " + LastSummary);
    }

    /// <summary>chunk biome → (which resource family, base woodedness).</summary>
    private static (string Cat, float Density) BiomeProfile(string type)
    {
        if (type.Contains("thicket")) return ("tree", 1.9f);
        if (type.Contains("forest")) return ("tree", 1.4f);
        if (type.Contains("overgrown")) return ("tree", 1.1f);
        if (type.Contains("wetland") || type.Contains("marsh")) return ("tree", 0.55f);
        if (type.Contains("crystal") || type.Contains("cave")) return ("ore", 0.30f);
        if (type.Contains("quarry")) return ("stone", 0.42f);
        if (type.Contains("rock") || type.Contains("highlands")) return ("stone", 0.22f);
        if (type.Contains("barren")) return ("stone", 0.16f);
        return ("tree", 0.28f);   // plains / steppe — the odd sparse tree
    }

    private static (double Min, double Max) TierRange(int danger) =>
        danger <= 2 ? (1, 2) : danger <= 4 ? (1, 3) : (1, 4);

    private void PlaceLand(Node3D parent, WorldContext ctx, CombatWorld combat,
                           int cx, int cy, string type, int danger)
    {
        var (cat, baseD) = BiomeProfile(type);
        if (baseD <= 0f) return;
        var pool = cat == "stone" ? _db.Stones : cat == "ore" ? _db.Ores : _db.Trees;
        if (pool.Count == 0) pool = _db.Trees.Count > 0 ? _db.Trees : _db.Stones;
        if (pool.Count == 0) return;
        var (tmin, tmax) = TierRange(danger);
        var eligible = pool.Where(r => r.Tier >= tmin && r.Tier <= tmax).ToList();
        if (eligible.Count == 0) eligible = pool;
        // min spacing so nodes never overlap (rocks are bulky; trees can crowd more) plus
        // the object's own radius so its EDGE clears the road, not just its centre.
        var minDist = cat == "stone" ? 9.5f : cat == "ore" ? 7.0f : 3.6f;
        var edge = cat == "stone" ? 3.5f : cat == "ore" ? 2.5f : 2.0f;   // keep even trees off the verge

        // A chunk hosts a FEW deposits, more in richer biomes. Each is a monotype stand
        // anchored on good ground; nodes fan out from its centre, thinning with radius.
        var expected = Mathf.Clamp(baseD * DepositsPerDensity, 0f, MaxDepositsPerChunk);
        for (var d = 0; d < MaxDepositsPerChunk; d++)
        {
            if (_count >= ResourceCap) return;
            // deterministic count: deposit slot d exists only while expectation remains.
            var slotChance = Mathf.Clamp(expected - d, 0f, 1f);
            if ((float)GeoNoise.Hash2D(cx * 911 + d, cy * 911 - d, _seed + 701) > slotChance) continue;

            // deposit centre — jittered within the chunk, validated on GOOD ground so the
            // stand reads well (off water, cliff, road corridor, station).
            var jx = (float)GeoNoise.Hash2D(cx * 71 + d * 13, cy * 71, _seed + 131);
            var jz = (float)GeoNoise.Hash2D(cx * 71, cy * 71 + d * 13, _seed + 137);
            double ccx = cx * ctx.ChunkSize + jx * ctx.ChunkSize;
            double ccz = cy * ctx.ChunkSize + jz * ctx.ChunkSize;
            if (ctx.IsWater(ccx, ccz)) { _blkWater++; continue; }
            if (ctx.Slope(ccx, ccz) > MaxResourceSlope) { _blkSlope++; continue; }
            if (TerrainHeightField.RoadWeight(ccx, ccz) > OnRoadReject
                || !ctx.RoadClear(ccx, ccz, edge)) { _blkRoad++; continue; }
            if (WorldContext.NearStation(ccx, ccz, 4.0f)) { _blkStation++; continue; }
            // a stand won't seed high on a bare peak (woods/veins belong on the flanks).
            if (cat == "tree" && ctx.MeshHeight(ccx, ccz) > 210f) { _blkDensity++; continue; }

            var def = PickByRarity(eligible,
                (float)GeoNoise.Hash2D(cx * 131 + d, cy * 131 + d, _seed + 53));
            if (_typeCount.GetValueOrDefault(def.ResourceId, 0) >= TypeWindowCap) { _blkCap++; continue; }

            // richer biomes → bigger, further-reaching stands.
            var rich = 0.4f + baseD * 0.6f
                     + (float)GeoNoise.Hash2D(cx * 17 + d, cy * 17 + d, _seed + 211) * 0.4f;
            int nodes = Mathf.Clamp(Mathf.RoundToInt(3f + rich * 4f), 2, cat == "tree" ? 9 : 7);
            // Reach scales with spacing × √nodes so the stand's disc actually has room for all
            // its nodes at the required Poisson spacing — otherwise a widely-spaced stone
            // "vein" (minDist 9.5) only ever fits ~2 rocks and reads as a pair, not a field.
            float reach = minDist * Mathf.Sqrt(nodes) * 0.62f;
            PlaceDeposit(parent, ctx, combat, def, cat, ccx, ccz, nodes, reach, minDist, edge, cx, cy, d);
        }
    }

    /// <summary>Fan a monotype stand out from its centre: an inward-biased radius gives a
    /// DENSE CORE and an outward acceptance falloff gives DIMINISHING RETURNS, so the
    /// stand reads as one structure — thick heart, ragged edge — not a uniform disc. Every
    /// node is still gated off water/cliff/road and Poisson-spaced.</summary>
    private void PlaceDeposit(Node3D parent, WorldContext ctx, CombatWorld combat,
                              ResourceNodeDefinition def, string cat, double cx, double cz,
                              int nodes, float reach, float minDist, float edge,
                              int chx, int chy, int slot)
    {
        var placed = 0;
        var attempts = nodes * 5;
        for (var a = 0; a < attempts && placed < nodes; a++)
        {
            if (_count >= ResourceCap) return;
            if (_typeCount.GetValueOrDefault(def.ResourceId, 0) >= TypeWindowCap) { _blkCap++; return; }
            var ha = (float)GeoNoise.Hash2D(chx * 401 + slot * 29 + a, chy * 401 - a, _seed + 811);
            var hb = (float)GeoNoise.Hash2D(chx * 409 - a, chy * 409 + slot * 31 + a, _seed + 821);
            var hc = (float)GeoNoise.Hash2D(chx * 419 + a * 3, chy * 419 + slot + a, _seed + 831);
            var rr = reach * Mathf.Pow(ha, 0.65f);          // inward-biased → dense core
            if (hc > 1f - rr / reach * 0.65f) continue;      // outer ring sparser → diminishing returns
            var ang = hb * Mathf.Tau;
            double px = cx + rr * Mathf.Cos(ang);
            double pz = cz + rr * Mathf.Sin(ang);
            if (ctx.IsWater(px, pz)) { _blkWater++; continue; }
            if (ctx.Slope(px, pz) > MaxResourceSlope) { _blkSlope++; continue; }
            if (TerrainHeightField.RoadWeight(px, pz) > OnRoadReject
                || !ctx.RoadClear(px, pz, edge)) { _blkRoad++; continue; }
            if (!ctx.TryOccupy(px, pz, minDist)) { _blkOccupy++; continue; }
            if (cat == "stone") _stoneC++; else if (cat == "ore") _oreC++; else _treeC++;
            RenderResource(parent, ctx, combat, def, px, pz);
            placed++;
        }
    }

    /// <summary>Weighted pick where higher tiers are rarer (rarity ∝ 1/tier^1.6).</summary>
    private static ResourceNodeDefinition PickByRarity(List<ResourceNodeDefinition> list, float h)
    {
        double total = 0;
        foreach (var r in list) total += 1.0 / Math.Pow(r.Tier, 1.6);
        var pick = h * total;
        foreach (var r in list)
        {
            pick -= 1.0 / Math.Pow(r.Tier, 1.6);
            if (pick <= 0) return r;
        }
        return list[^1];
    }

    /// <summary>Seat + build a harvestable tree/rock node (no floating card) and
    /// register it with the certified combat runtime.</summary>
    private void RenderResource(Node3D parent, WorldContext ctx, CombatWorld combat,
                                ResourceNodeDefinition def, double wx, double wz)
    {
        if (_dryRun)   // headless: record the accepted position, build/register nothing
        {
            var fam = def.IsTree ? "tree" : _db.Ores.Contains(def) ? "ore" : "stone";
            _dryLog.Add((new Vector2((float)wx, (float)wz), fam, def.ResourceId));
            _count++;
            _typeCount[def.ResourceId] = _typeCount.GetValueOrDefault(def.ResourceId, 0) + 1;
            return;
        }
        var rtx = (int)Math.Floor(wx);
        var rty = (int)Math.Floor(wz);
        var groundH = ctx.MeshHeight(wx, wz);
        Node3D visual;
        float pickR, pickCY, baseY;
        if (def.IsTree)
        {
            var vary = 0.7f + (float)GeoNoise.Hash2D(rtx, rty, _seed + 55) * 1.3f;
            var treeScale = (0.8f + 0.35f * (float)def.Tier) * vary;
            var (n, r, cyc) = ResourceArt.Tree(def.ResourceId, treeScale, _seed, rtx, rty);
            visual = n; pickR = r; pickCY = cyc;
            // Bed the trunk to the LOWEST ground under a small footprint so it never floats
            // off a slope (a tree rooted in mid-air breaks the read as badly as a floating rock).
            var tf = Mathf.Clamp(r * 0.5f, 0.5f, 1.5f);
            var tMin = Mathf.Min(groundH,
                Mathf.Min(ctx.MeshHeight(wx + tf, wz), ctx.MeshHeight(wx - tf, wz)));
            baseY = tMin - 0.3f;
        }
        else
        {
            var vary = 0.8f + (float)GeoNoise.Hash2D(rtx, rty, _seed + 66) * 1.2f;
            var rockScale = (0.9f + 0.3f * (float)def.Tier) * vary * 0.92f;   // bigger, fewer boulders
            var (n, r, cyc) = ResourceArt.Rock(def.ResourceId, (int)def.Tier, rockScale, _seed, rtx, rty);
            visual = n; pickR = r; pickCY = cyc;
            // Seat a BULKY rock at the LOWEST ground under its footprint so no lump floats
            // off a downhill slope — it beds slightly into the uphill side instead (a
            // half-buried boulder reads fine; a floating one shatters the illusion).
            var fr = Mathf.Clamp(r * 0.7f, 1.0f, 4.0f);
            var gMin = Mathf.Min(groundH,
                Mathf.Min(Mathf.Min(ctx.MeshHeight(wx + fr, wz), ctx.MeshHeight(wx - fr, wz)),
                          Mathf.Min(ctx.MeshHeight(wx, wz + fr), ctx.MeshHeight(wx, wz - fr))));
            baseY = gMin - 0.5f;
        }
        visual.Position = new Vector3((float)wx, baseY, (float)wz);
        parent.AddChild(visual);
        combat.RegisterResource(new NaturalResourceRuntime(
            new Game1.Core.World.Position(rtx + 0.5, rty + 0.5, 0),
            def.ResourceId, (int)def.Tier, _db), visual, pickR, pickCY);
        _count++;
        _typeCount[def.ResourceId] = _typeCount.GetValueOrDefault(def.ResourceId, 0) + 1;
    }

    private void RenderFishing(Node3D parent, WorldContext ctx, CombatWorld combat,
                              string type, int tier, double tx, double ty)
    {
        var groundH = ctx.MeshHeight(tx + 0.5, ty + 0.5);
        if (groundH >= TerrainHeightField.WaterLevel - 0.2f) return;   // dry → skip
        if (!ctx.RoadClear(tx + 0.5, ty + 0.5)) return;
        if (!ctx.TryOccupy(tx + 0.5, ty + 0.5, 3.0f)) return;
        if (_dryRun)   // headless: record the accepted fishing spot, build/register nothing
        {
            _dryLog.Add((new Vector2((float)tx + 0.5f, (float)ty + 0.5f), "fish", type));
            _count++;
            _fishC++;
            return;
        }
        var visual = new MeshInstance3D
        {
            Mesh = new CylinderMesh { TopRadius = 0.5f, BottomRadius = 0.5f, Height = 0.08f },
            MaterialOverride = _fishMat,
            Position = new Vector3((float)tx + 0.5f,
                TerrainHeightField.WaterLevel + 0.02f, (float)ty + 0.5f),
        };
        parent.AddChild(visual);
        combat.RegisterResource(new NaturalResourceRuntime(
            new Game1.Core.World.Position(tx + 0.5, ty + 0.5, 0), type, tier, _db),
            visual, 1.0f, 0.1f);
        _count++;
        _fishC++;
    }

    /// <summary>Headless debug driver: run this window's placement through ALL the same
    /// gates (biome/deposit/slope/road/water/occupancy/cap) but build NO meshes and
    /// register nothing — return where each node WOULD land plus the per-family counts,
    /// so the debug session can verify off-road / density / barren-corner statistically.</summary>
    public (IReadOnlyList<(Vector2 Pos, string Cat, string Id)> Nodes, int Tree, int Ore, int Stone, int Fish)
        DebugDryPlace(WorldContext ctx, CombatWorld combat)
    {
        _fishMat ??= new StandardMaterial3D { AlbedoColor = new Color(0.2f, 0.5f, 0.9f) };
        _dryRun = true;
        _dryLog.Clear();
        _count = 0; _typeCount.Clear();
        _treeC = _oreC = _stoneC = _fishC = 0;
        _blkSlope = _blkCap = _blkOccupy = _blkRoad = _blkWater = _blkStation = _blkDensity = 0;
        _remaining = (2 * ctx.ResourceRadius + 1) * (2 * ctx.ResourceRadius + 1);
        for (var cy = ctx.CenterCY - ctx.ResourceRadius; cy <= ctx.CenterCY + ctx.ResourceRadius; cy++)
            for (var cx = ctx.CenterCX - ctx.ResourceRadius; cx <= ctx.CenterCX + ctx.ResourceRadius; cx++)
                PlaceChunk(null!, ctx, combat, cx, cy);
        _dryRun = false;
        return (_dryLog, _treeC, _oreC, _stoneC, _fishC);
    }
}
