using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Game1.Core.World;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Headless DATA-ONLY view of world generation (env: G1_DEBUG=1) — a SECOND, independent
/// way to inspect the world alongside real screenshots. It runs the whole generation
/// (height field, thinned villages, MERGED road routing, resource dry-run) but builds NO
/// meshes/colliders/UI, then dumps a report that is deliberately MORE informative than any
/// one screenshot could be:
///   • top-down ASCII maps of the ENTIRE world (height, biome, road+village network) — a
///     god's-eye view no single camera shot gives;
///   • connectivity (is every settlement actually road-served?), regional 3x3 breakdowns,
///     village spacing, world-WIDE resource sampling (not just spawn);
///   • per-check PASS/FLAG plus NAMED OFFENDERS with world coordinates so a flag is
///     actionable, not just a number.
/// Optional env G1_DEBUG_AT="cx,cy" re-centres the detailed collision + primary resource
/// window on any chunk (inspect the frontier, not just spawn). Writes both stdout and
/// Game-1-Godot/worldgen_debug_report.txt.
/// </summary>
public static class WorldGenDebug
{
    private const float MaxVillageRelief = 13f;   // mirror WorldBootstrap
    private const int CS = 16;                     // chunk size (tiles)

    // ----- small helpers -------------------------------------------------------
    private static float Deg(double x, double y)
    {
        double hl = TerrainHeightField.NaturalHeight(x - 4, y), hr = TerrainHeightField.NaturalHeight(x + 4, y);
        double hd = TerrainHeightField.NaturalHeight(x, y - 4), hu = TerrainHeightField.NaturalHeight(x, y + 4);
        return Mathf.RadToDeg(Mathf.Atan((float)Math.Max(Math.Abs(hr - hl), Math.Abs(hu - hd)) / 8f));
    }
    private static string Pct(double a, double b) => b <= 0 ? "0.0%" : $"{100.0 * a / b:F1}%";
    private static string Mark(bool pass) => pass ? "PASS" : "FLAG";

    private static float SegDist(Vector2 p, Vector2 a, Vector2 b)
    {
        var ab = b - a; var len2 = ab.LengthSquared();
        if (len2 < 1e-6f) return p.DistanceTo(a);
        var t = Mathf.Clamp((p - a).Dot(ab) / len2, 0f, 1f);
        return p.DistanceTo(a + ab * t);
    }

    private static char HeightChar(float h, float wl)
    {
        if (h < wl) return '~';
        var d = h - wl;
        return d < 3 ? '.' : d < 15 ? ':' : d < 40 ? '-' : d < 80 ? '=' : d < 130 ? '+' : d < 190 ? 'o' : d < 250 ? '#' : '^';
    }
    private static char BiomeChar(string t)
    {
        bool C(string s) => t.Contains(s);
        if (C("lake") || C("river") || C("flooded") || C("ocean") || C("sea") || C("water")) return '~';
        if (C("marsh") || C("wetland") || C("swamp") || C("bog")) return 'm';
        if (C("forest") || C("thicket") || C("wood") || C("overgrown") || C("jungle")) return 'f';
        if (C("mountain") || C("alpine") || C("peak") || C("highland") || C("crag") || C("scree")) return '^';
        if (C("quarry")) return 'q';
        if (C("cave") || C("cavern") || C("crystal") || C("grotto")) return 'c';
        if (C("barren") || C("waste") || C("desert") || C("badland")) return 'x';
        if (C("tundra") || C("snow") || C("ice") || C("frost")) return '*';
        if (C("hill") || C("knoll") || C("down")) return 'n';
        if (C("plain") || C("grass") || C("steppe") || C("meadow") || C("field") || C("prairie")) return ',';
        return '.';
    }
    private static char TierChar(string tier) => tier switch
    {
        "fortress" => 'F', "large" => 'L', "medium" => 'M', "small" => 's', "tiny" => 't', _ => 'v',
    };

    public static void Dump(WorldMap? map, long seed, List<VillageRecord> villages, RoadNetwork? roadNet,
                            BiomeGenerator biomes, ResourcePlacer placer, CombatWorld combat,
                            int chunkRadius, int resourceRadius, int chunkSize)
    {
        var sb = new StringBuilder();
        void L(string s = "") { sb.Append(s); sb.Append('\n'); }
        var scorecard = new List<string>();
        void Score(string name, bool pass, string note) => scorecard.Add($"   [{Mark(pass)}] {name,-34} {note}");
        var sw = System.Diagnostics.Stopwatch.StartNew();
        float wl = TerrainHeightField.WaterLevel;
        var ctxG = new WorldContext(0, 0, chunkRadius, resourceRadius, chunkSize, seed, map, biomes, roadNet);

        // detailed-window centre (env override lets us inspect the frontier, not just spawn)
        int dcx = 0, dcy = 0;
        var at = System.Environment.GetEnvironmentVariable("G1_DEBUG_AT");
        if (at != null)
        {
            var p = at.Split(',');
            if (p.Length == 2 && int.TryParse(p[0], out var a0) && int.TryParse(p[1], out var b0)) { dcx = a0; dcy = b0; }
        }

        L("==================== WORLDGEN DEBUG (data-only, no visuals) ====================");
        L($"seed={seed}  world={(map?.WorldSize ?? 0)}ch  villages={villages.Count}  roadEdges={roadNet?.Edges.Count ?? 0}  detailWindow=({dcx},{dcy})");

        // ============================================================ WORLD MAPS
        if (map != null)
        {
            float halfT = map.WorldSize / 2 * 16f;
            L("");
            L("-- WORLD MAPS (top-down, whole world; each cell ~" + (int)(2 * halfT / 100) + "t) --");
            L(RenderMap(100, 50, halfT, (x, y) => HeightChar((float)TerrainHeightField.NaturalHeight(x, y), wl),
                "HEIGHT  (~ water  . shore  : - = + o low->high  # ^ peaks):"));
            L(RenderMap(100, 50, halfT, (x, y) => BiomeChar(ctxG.ChunkType((int)Math.Floor(x / CS), (int)Math.Floor(y / CS))),
                "BIOME   (~ water  f forest  ^ mountain  n hill  , plains  m marsh  q quarry  c cave  x barren  * frozen):"));
            L(RenderNetworkMap(100, 50, halfT, wl, roadNet, villages));
        }

        // ============================================================ TERRAIN + COLLISION
        int R = chunkRadius * CS, ox = dcx * CS, oz = dcy * CS;
        int badFinite = 0; double maxIntDiff = 0, maxBilerp = 0, sumBilerp = 0; int nBilerp = 0, wallSteps = 0, nAdj = 0; double maxStep = 0;
        for (int z = -R; z <= R; z++)
            for (int x = -R; x <= R; x++)
            {
                float h = TerrainHeightField.H(ox + x, oz + z), hm = TerrainHeightField.HMesh(ox + x, oz + z);
                if (!float.IsFinite(h) || !float.IsFinite(hm)) { badFinite++; continue; }
                maxIntDiff = Math.Max(maxIntDiff, Math.Abs(h - hm));
                if (x < R && z < R)
                {
                    float fc = TerrainHeightField.H(ox + x + 0.5, oz + z + 0.5), mc = TerrainHeightField.HMesh(ox + x + 0.5, oz + z + 0.5);
                    var e = Math.Abs(fc - mc); maxBilerp = Math.Max(maxBilerp, e); sumBilerp += e; nBilerp++;
                    var step = Math.Max(Math.Abs(h - TerrainHeightField.H(ox + x + 1, oz + z)), Math.Abs(h - TerrainHeightField.H(ox + x, oz + z + 1)));
                    maxStep = Math.Max(maxStep, step); nAdj++; if (step > 2.5f) wallSteps++;
                }
            }
        L("");
        L($"-- TERRAIN / COLLISION (window {dcx},{dcy}) --");
        L($"   finite H/HMesh: bad={badFinite}   collider==mesh at integer: max|H-HMesh|={maxIntDiff:F4}u");
        L($"   mesh-vs-field(cell centre): max={maxBilerp:F2}u mean={(nBilerp > 0 ? sumBilerp / nBilerp : 0):F3}u    clip walls(>2.5u/tile): {Pct(wallSteps, nAdj)} maxStep={maxStep:F1}u");
        Score("collider==mesh (no fall-through)", badFinite == 0 && maxIntDiff < 0.01, $"max|H-HMesh|={maxIntDiff:F4}u");

        // whole-world height/slope
        if (map != null)
        {
            float halfT = map.WorldSize / 2 * 16f; int step = Math.Max(16, (int)(halfT * 2 / 180));
            var hHist = new int[6]; var sHist = new int[5]; int nS = 0, nW = 0; double sumDeg = 0, maxDeg = 0, maxH = -1e9;
            for (var y = -halfT; y < halfT; y += step)
                for (var x = -halfT; x < halfT; x += step)
                {
                    var h = (float)TerrainHeightField.NaturalHeight(x, y); nS++; if (h < wl) nW++; maxH = Math.Max(maxH, h);
                    hHist[h < wl ? 0 : h < 50 ? 1 : h < 120 ? 2 : h < 250 ? 3 : h < 400 ? 4 : 5]++;
                    var d = Deg(x, y); sumDeg += d; maxDeg = Math.Max(maxDeg, d); sHist[d < 10 ? 0 : d < 25 ? 1 : d < 40 ? 2 : d < 60 ? 3 : 4]++;
                }
            L("");
            L("-- TERRAIN SHAPE (whole world) --");
            L($"   maxH={maxH:F0}u  water={Pct(nW, nS)}  meanSlope={sumDeg / nS:F1}deg  maxSlope={maxDeg:F0}deg");
            L($"   height: water={Pct(hHist[0], nS)} <50={Pct(hHist[1], nS)} 50-120={Pct(hHist[2], nS)} 120-250={Pct(hHist[3], nS)} 250-400={Pct(hHist[4], nS)} 400+={Pct(hHist[5], nS)}");
            L($"   slope:  <10={Pct(sHist[0], nS)} 10-25={Pct(sHist[1], nS)} 25-40={Pct(sHist[2], nS)} 40-60={Pct(sHist[3], nS)} 60+={Pct(sHist[4], nS)}");
            Score("terrain water fraction", nW / (double)nS is > 0.05 and < 0.45, Pct(nW, nS));
        }

        // ============================================================ ROADS
        var segs = new List<(Vector2 A, Vector2 B)>();
        L("");
        L("-- ROADS (walking the ACTUAL routed e.Path) --");
        var badBridges = new List<string>(); var badFallbacks = new List<string>(); var steepRoads = new List<string>();
        if (roadNet == null || roadNet.Edges.Count == 0) L("   (no road network)");
        else
        {
            double totLen = 0, waterLen = 0, steepLen = 0, cliffLen = 0, modLen = 0, maxWaterRun = 0, maxGrade = 0;
            int steepDeck = 0, nDeckSeg = 0, merges = 0, reachedB = 0, fallbacks = 0, noPath = 0, ptsSum = 0, sustainedSteep = 0;
            var gradeHist = new int[4];
            foreach (var e in roadNet.Edges)
            {
                var path = e.Path; if (path == null || path.Length < 2) { noPath++; continue; }
                ptsSum += path.Length;
                for (var i = 0; i + 1 < path.Length; i++) segs.Add((path[i], path[i + 1]));
                var pa = path[0]; var pb = path[^1];
                if (path.Length == 2 && pa.DistanceTo(pb) > 40f)
                {
                    var bad = false; int fs = Math.Max(2, (int)(pa.DistanceTo(pb) / 4f));
                    for (var s = 1; s < fs && !bad; s++)
                    {
                        var p = pa.Lerp(pb, s / (float)fs);
                        if (TerrainHeightField.NaturalHeight(p.X, p.Y) < wl + 0.6 || Deg(p.X, p.Y) > 40) bad = true;
                    }
                    if (bad) { fallbacks++; badFallbacks.Add($"t{e.Tier} ({pa.X:F0},{pa.Y:F0})->({pb.X:F0},{pb.Y:F0}) len={pa.DistanceTo(pb):F0}u"); }
                }
                if (path[^1].DistanceTo(e.B) > 5f) merges++; else reachedB++;
                double run = 0, edgeMaxRun = 0, edgeModLen = 0, edgeSteepLen = 0, edgeMaxGrade = 0; Vector2 runAt = path[0], gradeAt = path[0];
                for (var i = 0; i + 1 < path.Length; i++)
                {
                    var a = path[i]; var b = path[i + 1]; var segLen = a.DistanceTo(b);
                    var g = segLen > 0.5f ? Math.Abs(TerrainHeightField.NaturalHeight(b.X, b.Y) - TerrainHeightField.NaturalHeight(a.X, a.Y)) / segLen : 0;
                    if (g > maxGrade) maxGrade = g; if (g > edgeMaxGrade) { edgeMaxGrade = g; gradeAt = a; }
                    gradeHist[g < 0.10 ? 0 : g < 0.20 ? 1 : g < 0.30 ? 2 : 3]++; if (g > 0.30) steepDeck++; nDeckSeg++;
                    int sub = Math.Max(1, (int)(segLen / 2f));
                    for (var s = 0; s < sub; s++)
                    {
                        var p = a.Lerp(b, (s + 0.5f) / sub); var dl = segLen / sub; totLen += dl;
                        if (TerrainHeightField.NaturalHeight(p.X, p.Y) < wl + 0.3) { waterLen += dl; run += dl; if (run > edgeMaxRun) { edgeMaxRun = run; runAt = p; } if (run > maxWaterRun) maxWaterRun = run; }
                        else run = 0;
                        var d = Deg(p.X, p.Y); if (d > 15) { modLen += dl; edgeModLen += dl; } if (d > 30) { steepLen += dl; edgeSteepLen += dl; } if (d > 45) cliffLen += dl;
                    }
                }
                if (edgeMaxRun > 40) badBridges.Add($"t{e.Tier} run={edgeMaxRun:F0}u at ({runAt.X:F0},{runAt.Y:F0})");
                if (edgeSteepLen > 60) sustainedSteep++;   // a real STEEP (>30deg) mountain climb, not rolling ground
                if (edgeModLen > 40 || edgeMaxGrade > 0.28) steepRoads.Add($"t{e.Tier} onSlope={edgeModLen:F0}u maxGrade={edgeMaxGrade:F2} at ({gradeAt.X:F0},{gradeAt.Y:F0})");
            }
            L($"   edges={roadNet.Edges.Count} totalLen={totLen:F0}u avgPts/path={(double)ptsSum / roadNet.Edges.Count:F1} noPath={noPath}");
            L($"   MERGES(feeder->artery)={merges}  reached-B={reachedB}     underwater={Pct(waterLen, totLen)} maxRun={maxWaterRun:F0}u");
            L($"   on SLOPE(>15deg)={Pct(modLen, totLen)}  on steep(>30)={Pct(steepLen, totLen)}  on cliff(>45)={Pct(cliffLen, totLen)}");
            L($"   deck grade <0.20={Pct(gradeHist[0] + gradeHist[1], nDeckSeg)}  0.20-0.30={Pct(gradeHist[2], nDeckSeg)}  0.30+={Pct(gradeHist[3], nDeckSeg)}   WORST={maxGrade:F2}  steepRoadEdges={steepRoads.Count}");
            Score("roads merge into arteries", merges > 0, $"{merges} merges / {reachedB} reach-B");
            Score("no underwater roads", maxWaterRun < 60, $"maxRun={maxWaterRun:F0}u");
            Score("roads off cliffs", cliffLen / Math.Max(1, totLen) < 0.02, Pct(cliffLen, totLen));
            Score("roads off SLOPES (<12% on >15deg)", modLen / Math.Max(1, totLen) < 0.12, $"{Pct(modLen, totLen)} on >15deg");
            Score("no widespread steep roads (few passes ok)", sustainedSteep <= 4, $"{sustainedSteep} sustained climbs, worst grade {maxGrade:F2}");
            Score("no water/cliff straight fallbacks", fallbacks == 0, $"{fallbacks} of {roadNet.Edges.Count}");
        }

        // ============================================================ CONNECTIVITY + SERVICE
        L("");
        L("-- ROAD CONNECTIVITY + SETTLEMENT SERVICE --");
        {
            var pts = villages.Select(v => new Vector2(v.CenterChunk.X * CS + 8, v.CenterChunk.Y * CS + 8)).ToList();
            var idx = new Dictionary<(int, int), int>();
            for (var i = 0; i < pts.Count; i++) idx[((int)Math.Round(pts[i].X), (int)Math.Round(pts[i].Y))] = i;
            var uf = Enumerable.Range(0, pts.Count).ToArray();
            int Find(int x) { while (uf[x] != x) { uf[x] = uf[uf[x]]; x = uf[x]; } return x; }
            if (roadNet != null)
                foreach (var e in roadNet.Edges)
                    if (idx.TryGetValue(((int)Math.Round(e.A.X), (int)Math.Round(e.A.Y)), out var ia)
                        && idx.TryGetValue(((int)Math.Round(e.B.X), (int)Math.Round(e.B.Y)), out var ib))
                        uf[Find(ia)] = Find(ib);
            int comps = Enumerable.Range(0, pts.Count).Count(i => Find(i) == i);
            // per-village nearest road-centre distance
            int unserved = 0; var unservedList = new List<string>(); double sumNearest = 0;
            for (var i = 0; i < pts.Count; i++)
            {
                float md = 1e9f; foreach (var (a, b) in segs) { md = Math.Min(md, SegDist(pts[i], a, b)); if (md < 6f) break; }
                sumNearest += md;
                if (md > 20f) { unserved++; if (unservedList.Count < 8) unservedList.Add($"{villages[i].Tier} @({pts[i].X:F0},{pts[i].Y:F0}) {md:F0}u from road"); }
            }
            L($"   graph components={comps} (1 => fully connected)   mean village->road dist={sumNearest / Math.Max(1, pts.Count):F1}u");
            L($"   unserved settlements (>20u from any road): {unserved} of {pts.Count} ({Pct(unserved, pts.Count)})");
            if (unservedList.Count > 0) L("     e.g. " + string.Join(" | ", unservedList));
            Score("network fully connected", comps == 1, $"{comps} components");
            Score("settlements road-served", unserved / (double)Math.Max(1, pts.Count) < 0.05, $"{unserved} unserved");
        }

        // ============================================================ VILLAGES + DISTRIBUTION
        L("");
        L("-- VILLAGES (siting + pad + distribution) --");
        {
            var tierCount = new Dictionary<string, int>(); var reliefHist = new int[4]; var cutHist = new int[4];
            double maxRelief = 0, maxCut = 0, worstFootSlope = 0; int under = 0, steep = 0, onSlope = 0;
            var steepList = new List<string>(); var slopeList = new List<string>();
            var pts = new List<Vector2>();
            foreach (var v in villages)
            {
                tierCount[v.Tier] = tierCount.GetValueOrDefault(v.Tier) + 1;
                var walls = VillageGenerator.GetVillageWallTiles(v).ToList();
                double cx, cz;
                if (walls.Count > 0) { double sx = 0, sz = 0; foreach (var (tx, ty) in walls) { sx += tx + 0.5; sz += ty + 0.5; } cx = sx / walls.Count; cz = sz / walls.Count; }
                else { cx = v.CenterChunk.X * CS + 8; cz = v.CenterChunk.Y * CS + 8; }
                pts.Add(new Vector2((float)cx, (float)cz));
                var level = TerrainHeightField.NaturalHeight(cx, cz);
                if (level < wl + 0.5) under++;
                if (Deg(cx, cz) > 25f) { steep++; if (steepList.Count < 6) steepList.Add($"{v.Tier} @({cx:F0},{cz:F0}) {Deg(cx, cz):F0}deg"); }
                if (walls.Count == 0) continue;
                var maxR = 4.0; foreach (var (tx, ty) in walls) { var dx = tx + 0.5 - cx; var dz = ty + 0.5 - cz; maxR = Math.Max(maxR, Math.Sqrt(dx * dx + dz * dz)); }
                double lo = 1e9, hi = -1e9, cut = 0, vMaxSlope = 0; int steepN = 0, totN = 0;
                for (var i = 0; i <= 4; i++) for (var j = 0; j <= 4; j++)
                    {
                        var sxs = cx + (i / 4.0 * 2 - 1) * maxR; var szs = cz + (j / 4.0 * 2 - 1) * maxR;
                        var hh = TerrainHeightField.NaturalHeight(sxs, szs); lo = Math.Min(lo, hh); hi = Math.Max(hi, hh); cut = Math.Max(cut, Math.Abs(hh - level));
                        var dg = Deg(sxs, szs); if (dg > vMaxSlope) vMaxSlope = dg; if (dg > 20) steepN++; totN++;
                    }
                var relief = hi - lo; maxRelief = Math.Max(maxRelief, relief); maxCut = Math.Max(maxCut, cut);
                worstFootSlope = Math.Max(worstFootSlope, vMaxSlope);
                var steepFrac = (double)steepN / Math.Max(1, totN);
                if (steepFrac > 0.30 || vMaxSlope > 30) { onSlope++; if (slopeList.Count < 8) slopeList.Add($"{v.Tier} @({cx:F0},{cz:F0}) maxSlope={vMaxSlope:F0}deg steep={steepFrac * 100:F0}%"); }
                reliefHist[relief < 5 ? 0 : relief < 9 ? 1 : relief < 13 ? 2 : 3]++; cutHist[cut < 4 ? 0 : cut < 8 ? 1 : cut < 13 ? 2 : 3]++;
            }
            // nearest-neighbour spacing
            double sumNN = 0, minNN = 1e9; int nNN = 0;
            for (var i = 0; i < pts.Count; i++) { float md = 1e9f; for (var j = 0; j < pts.Count; j++) if (j != i) md = Math.Min(md, pts[i].DistanceTo(pts[j])); if (md < 1e8f) { sumNN += md; minNN = Math.Min(minNN, md); nNN++; } }
            L($"   kept={villages.Count} by tier: {string.Join(" ", tierCount.OrderByDescending(k => k.Value).Select(k => $"{k.Key}={k.Value}"))}");
            L($"   underwater={under} steep-center(>25)={steep}   footprint relief max={maxRelief:F1}u  pad cut max={maxCut:F1}u");
            L($"   relief: <5={reliefHist[0]} 5-9={reliefHist[1]} 9-13={reliefHist[2]} 13+={reliefHist[3]}   padcut: <4={cutHist[0]} 4-8={cutHist[1]} 8-13={cutHist[2]} 13+={cutHist[3]}");
            L($"   spacing: nearest-neighbour mean={sumNN / Math.Max(1, nNN):F0}u min={minNN:F0}u");
            L($"   ON A STEEP FLANK (>30% of footprint >20deg, or a cliff): {onSlope} of {villages.Count} ({Pct(onSlope, villages.Count)})  worstFootSlope={worstFootSlope:F0}deg");
            if (slopeList.Count > 0) L("   steep-flank offenders: " + string.Join(" | ", slopeList));
            Score("villages not underwater/mesa", under == 0 && maxCut <= MaxVillageRelief + 0.5, $"under={under} maxCut={maxCut:F1}u");
            Score("villages off steep flanks", onSlope / (double)Math.Max(1, villages.Count) < 0.08, $"{onSlope} steep, worst {worstFootSlope:F0}deg");
        }

        // ============================================================ REGIONAL 3x3
        if (map != null)
        {
            float halfT = map.WorldSize / 2 * 16f;
            L("");
            L("-- REGIONAL BREAKDOWN (3x3 tiles of the world: NW..SE) --");
            var rv = new int[9]; var rwater = new int[9]; var rn = new int[9]; var rh = new double[9];
            foreach (var v in villages) { var gx = Reg(v.CenterChunk.X * CS + 8, halfT); var gy = Reg(v.CenterChunk.Y * CS + 8, halfT); rv[gy * 3 + gx]++; }
            int stp = Math.Max(24, (int)(halfT * 2 / 90));
            for (var y = -halfT; y < halfT; y += stp) for (var x = -halfT; x < halfT; x += stp) { var g = Reg(y, halfT) * 3 + Reg(x, halfT); rn[g]++; var h = (float)TerrainHeightField.NaturalHeight(x, y); rh[g] += h; if (h < wl) rwater[g]++; }
            for (var row = 0; row < 3; row++)
            {
                var cells = new List<string>();
                for (var col = 0; col < 3; col++) { var g = row * 3 + col; cells.Add($"[{(rn[g] > 0 ? rh[g] / rn[g] : 0),4:F0}u {Pct(rwater[g], rn[g]),5} {rv[g],3}v]"); }
                L("   " + string.Join(" ", cells));
            }
            L("   (each cell: meanHeight  water%  villageCount — a hollow/empty region stands out)");
        }

        // ============================================================ RESOURCES (multi-window)
        L("");
        L("-- RESOURCES (dry-run, multiple windows across the world) --");
        try
        {
            var centres = new (int X, int Y)[] { (dcx, dcy), (-150, -150), (150, -150), (-150, 150), (150, 150) };
            int totNodes = 0, totOnRoad = 0, totBarren = 0, totLand = 0;
            var allByBiome = new Dictionary<string, int>(); var allByBiomeChunks = new Dictionary<string, int>();
            foreach (var (wcx, wcy) in centres)
            {
                var ctx = new WorldContext(wcx, wcy, chunkRadius, resourceRadius, chunkSize, seed, map, biomes, roadNet);
                var (nodes, tree, ore, stone, fish) = placer.DebugDryPlace(ctx, combat);
                int onRoad = 0;
                foreach (var (pos, _, _) in nodes) { float md = 1e9f; foreach (var (a, b) in segs) { md = Math.Min(md, SegDist(pos, a, b)); if (md < 2.5f) break; } if (md < 2.5f) onRoad++; }
                var perChunk = new Dictionary<(int, int), int>();
                foreach (var (pos, _, _) in nodes) { var k = ((int)Math.Floor(pos.X / CS), (int)Math.Floor(pos.Y / CS)); perChunk[k] = perChunk.GetValueOrDefault(k) + 1; }
                int land = 0, barren = 0;
                for (var cy = wcy - resourceRadius; cy <= wcy + resourceRadius; cy++)
                    for (var cx = wcx - resourceRadius; cx <= wcx + resourceRadius; cx++)
                    {
                        var t = ctxG.ChunkType(cx, cy);
                        if (t.Contains("lake") || t.Contains("river") || t.Contains("flooded") || t.Contains("ocean") || t.Contains("sea")) continue;
                        land++; var n = perChunk.GetValueOrDefault((cx, cy)); if (n == 0) barren++;
                        allByBiome[t] = allByBiome.GetValueOrDefault(t) + n; allByBiomeChunks[t] = allByBiomeChunks.GetValueOrDefault(t) + 1;
                    }
                totNodes += nodes.Count; totOnRoad += onRoad; totBarren += barren; totLand += land;
                L($"   window({wcx,4},{wcy,4}): placed={nodes.Count,4} (t{tree} o{ore} s{stone} f{fish})  on-road={onRoad}  barren={Pct(barren, land)}");
            }
            L($"   TOTAL: placed={totNodes}  on-road={totOnRoad}  barren={Pct(totBarren, totLand)} of land chunks");
            L("   density by biome (nodes/chunk, world-wide): " + string.Join("  ", allByBiome.OrderByDescending(k => k.Value).Take(8).Select(k => $"{k.Key}={(double)k.Value / Math.Max(1, allByBiomeChunks[k.Key]):F1}")));
            Score("nothing placed on roads", totOnRoad == 0, $"{totOnRoad} on-road world-wide");
            Score("no barren wedge", totBarren / (double)Math.Max(1, totLand) < 0.3, Pct(totBarren, totLand));
        }
        catch (Exception ex) { L("   dry-run FAILED: " + ex.Message); }

        // ============================================================ OFFENDERS + SCORECARD
        L("");
        L("-- OFFENDERS (specific flagged entities, world coords) --");
        L("   road long-water spans (>40u): " + (badBridges.Count == 0 ? "none" : string.Join(" | ", badBridges.Take(8))));
        L("   road water/cliff fallbacks:   " + (badFallbacks.Count == 0 ? "none" : string.Join(" | ", badFallbacks.Take(8))));
        L($"   roads ON SLOPES ({steepRoads.Count}): " + (steepRoads.Count == 0 ? "none" : string.Join(" | ", steepRoads.Take(8))));

        L("");
        L("-- SCORECARD --");
        foreach (var s in scorecard) L(s);
        var fails = scorecard.Count(s => s.Contains("[FLAG]"));
        L($"   => {scorecard.Count - fails}/{scorecard.Count} PASS   ({fails} FLAG)");

        L("");
        L($"scan {sw.ElapsedMilliseconds}ms");
        L("================================================================================");

        var report = sb.ToString();
        GD.Print(report);
        try { var path = ProjectSettings.GlobalizePath("res://worldgen_debug_report.txt"); System.IO.File.WriteAllText(path, report); GD.Print("[dbg] wrote " + path); }
        catch (Exception ex) { GD.Print("[dbg] file write skipped: " + ex.Message); }
    }

    private static int Reg(double v, float halfT) => Math.Clamp((int)((v + halfT) / (2 * halfT) * 3), 0, 2);

    /// <summary>Render a whole-world top-down ASCII map from a per-point char sampler. Rows
    /// are half the columns so square world reads square in a ~2:1 terminal cell.</summary>
    private static string RenderMap(int cols, int rows, float halfT, Func<double, double, char> sample, string title)
    {
        var m = new StringBuilder(); m.Append(title).Append('\n');
        double span = 2 * halfT, minX = -halfT, minY = -halfT;
        for (var r = 0; r < rows; r++)
        {
            for (var c = 0; c < cols; c++)
            {
                double x = minX + (c + 0.5) / cols * span, y = minY + (r + 0.5) / rows * span;
                m.Append(sample(x, y));
            }
            m.Append('\n');
        }
        return m.ToString();
    }

    /// <summary>The killer view: the whole ROAD NETWORK + settlement distribution over a
    /// faint land/water base — structure no single screenshot can show.</summary>
    private static string RenderNetworkMap(int cols, int rows, float halfT, float wl, RoadNetwork? roadNet, List<VillageRecord> villages)
    {
        double span = 2 * halfT, minX = -halfT, minY = -halfT;
        (int C, int Rr) Cell(double x, double y) => (Math.Clamp((int)((x - minX) / span * cols), 0, cols - 1), Math.Clamp((int)((y - minY) / span * rows), 0, rows - 1));
        var road = new bool[cols * rows];
        if (roadNet != null)
            foreach (var e in roadNet.Edges)
            {
                var p = e.Path; if (p == null) continue;
                for (var i = 0; i + 1 < p.Length; i++)
                {
                    var a = p[i]; var b = p[i + 1]; var stepW = span / cols * 0.5; int n = Math.Max(1, (int)(a.DistanceTo(b) / stepW));
                    for (var s = 0; s <= n; s++) { var q = a.Lerp(b, s / (float)n); var (cc, rr) = Cell(q.X, q.Y); road[rr * cols + cc] = true; }
                }
            }
        var vil = new char[cols * rows];
        foreach (var v in villages) { var (cc, rr) = Cell(v.CenterChunk.X * CS + 8, v.CenterChunk.Y * CS + 8); vil[rr * cols + cc] = TierChar(v.Tier); }
        var m = new StringBuilder();
        m.Append("NETWORK (# roads  F/L/M/s/t villages by tier  ~ water  . land):\n");
        for (var r = 0; r < rows; r++)
        {
            for (var c = 0; c < cols; c++)
            {
                var i = r * cols + c;
                if (vil[i] != '\0') { m.Append(vil[i]); continue; }
                if (road[i]) { m.Append('#'); continue; }
                double x = minX + (c + 0.5) / cols * span, y = minY + (r + 0.5) / rows * span;
                m.Append(TerrainHeightField.NaturalHeight(x, y) < wl ? '~' : '.');
            }
            m.Append('\n');
        }
        return m.ToString();
    }
}
