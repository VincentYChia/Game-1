using System.Collections.Generic;
using System.Linq;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>One road: a segment between two settlement centres (world tile x,z)
/// with a visual tier (0 feeder path → 3 grand artery).</summary>
public sealed class RoadEdge
{
    public required Vector2 A;
    public required Vector2 B;
    public int Tier;
    /// <summary>A redundant capital-to-capital highway (not part of the spanning tree). Safe
    /// to drop if it can only be drawn as a straight line across water — the tree still connects.</summary>
    public bool Loop;
    /// <summary>Routed polyline (world x,z) over passable ground. Filled once, globally,
    /// by RouteMerged during Build — a feeder's path ends where it JOINS an artery, not
    /// necessarily at B. The router never fails, so once Routed this is non-null.</summary>
    public Vector2[]? Path;
    public bool Routed;
}

/// <summary>
/// A MERGED ARTERIAL network with a hard connectivity guarantee: no dead-ends.
///
/// The backbone is a MINIMUM SPANNING TREE over EVERY settlement (Delaunay
/// candidates, Kruskal by distance) — connected by construction, so there is always a
/// road path between any two settlements. Each tree edge is tiered by the LARGEST
/// settlement it ultimately serves, so roads taper naturally: grand arteries near the
/// big cities → secondary → branch → thin feeder twigs at the hamlets. A few great
/// highways loop the capitals for a networked-kingdom read.
///
/// The critical difference from a bare MST: edges are ROUTED GLOBALLY, ONCE, in
/// root-outward order onto a GROWING network. When a feeder is routed it MERGES into
/// the nearest already-built road at a junction (RoadRouter's onNetwork snap) instead
/// of laying its own parallel ribbon out to the far town. The result reads as a real
/// road system — shared trunks, clean junctions, feeders peeling off — rather than a
/// star of independent point-to-point paths. Computed once at load (needs the terrain
/// field initialised first, which WorldBootstrap guarantees).
/// </summary>
public sealed class RoadNetwork
{
    public readonly List<RoadEdge> Edges = new();

    private static int Rank(string tier) => tier switch
    {
        "fortress" => 5,
        "large" => 4,
        "medium" => 3,
        "small" => 2,
        _ => 1,
    };

    // largest-served rank → visual tier (0 feeder … 3 artery)
    private static int TierOf(int subMax) =>
        subMax >= 5 ? 3 : subMax == 4 ? 2 : subMax == 3 ? 1 : 0;

    public static RoadNetwork Build(List<VillageRecord> villages)
    {
        var net = new RoadNetwork();
        var n = villages.Count;
        if (n < 2) return net;

        var pts = new Vector2[n];
        var rank = new int[n];
        for (var i = 0; i < n; i++)
        {
            pts[i] = new Vector2(villages[i].CenterChunk.X * 16 + 8,
                                 villages[i].CenterChunk.Y * 16 + 8);
            rank[i] = Rank(villages[i].Tier);
        }

        // 1. spanning tree over ALL settlements → guaranteed connectivity.
        var adj = new List<int>[n];
        for (var i = 0; i < n; i++) adj[i] = new List<int>();
        var uf = new int[n];
        for (var i = 0; i < n; i++) uf[i] = i;
        int Find(int x) { while (uf[x] != x) { uf[x] = uf[uf[x]]; x = uf[x]; } return x; }
        void Union(int a, int b, bool tree)
        {
            int ra = Find(a), rb = Find(b);
            if (ra == rb) return;
            uf[ra] = rb;
            if (tree) { adj[a].Add(b); adj[b].Add(a); }
        }

        var links = 0;
        foreach (var (u, v, _) in CandidateEdges(pts).OrderBy(e => e.D))
        {
            if (Find(u) == Find(v)) continue;
            Union(u, v, true);
            if (++links == n - 1) break;
        }
        // Delaunay of a point set is connected, so this is belt-and-braces: if the
        // candidate graph left the world in pieces, stitch the pieces by nearest
        // representative until one connected tree remains.
        if (links < n - 1) StitchComponents(pts, adj, Find, Union, ref links);

        // 2. root at the biggest settlement; tier each tree edge by the largest
        //    settlement hanging off its far (child) side → arteries taper to feeders.
        //    The DFS pre-order (order[]) also fixes the ROUTING order below: a parent
        //    edge is always emitted — and therefore routed — before its children.
        var root = 0;
        for (var i = 1; i < n; i++) if (rank[i] > rank[root]) root = i;

        var parent = new int[n];
        var order = new int[n];
        var seen = new bool[n];
        var oc = 0;
        var stack = new Stack<int>();
        stack.Push(root); seen[root] = true; parent[root] = root;
        while (stack.Count > 0)
        {
            var cur = stack.Pop();
            order[oc++] = cur;
            foreach (var nb in adj[cur])
                if (!seen[nb]) { seen[nb] = true; parent[nb] = cur; stack.Push(nb); }
        }

        var subMax = new int[n];
        for (var i = 0; i < n; i++) subMax[i] = rank[i];
        for (var i = oc - 1; i >= 0; i--)   // reverse topological → accumulate up
        {
            var v = order[i];
            if (v == root) continue;
            var p = parent[v];
            if (subMax[v] > subMax[p]) subMax[p] = subMax[v];
        }
        for (var i = 0; i < oc; i++)
        {
            var v = order[i];
            if (v == root) continue;
            net.Edges.Add(new RoadEdge
            { A = pts[v], B = pts[parent[v]], Tier = TierOf(subMax[v]) });
        }

        // 3. great highways: loop each capital to its nearest capital (arteries),
        //    for a networked kingdom rather than a bare tree. Bounded + dedup'd.
        AddCapitalLoops(net, pts, rank, adj);

        // 4. route every edge ONCE, globally, merging onto the growing network.
        RouteMerged(net, pts[root]);

        return net;
    }

    // ---- global merged routing ------------------------------------------------

    private const float NetCell = 5f;   // network stamp / merge tolerance (world units)

    private static long Key(int cx, int cy) => ((long)cx << 32) ^ (uint)cy;

    /// <summary>Mark a 3×3 block of network cells around a world point, so a road that
    /// comes within ~one cell of an existing road is treated as touching it (merge).</summary>
    private static void Stamp(HashSet<long> set, Vector2 p)
    {
        int cx = Mathf.FloorToInt(p.X / NetCell), cy = Mathf.FloorToInt(p.Y / NetCell);
        for (var dy = -1; dy <= 1; dy++)
            for (var dx = -1; dx <= 1; dx++)
                set.Add(Key(cx + dx, cy + dy));
    }

    private static void StampPath(HashSet<long> set, Vector2[]? path)
    {
        if (path is null) return;
        for (var i = 0; i + 1 < path.Length; i++)
        {
            var a = path[i];
            var b = path[i + 1];
            var d = a.DistanceTo(b);
            var steps = Mathf.Max(1, Mathf.CeilToInt(d / (NetCell * 0.5f)));
            for (var s = 0; s <= steps; s++) Stamp(set, a.Lerp(b, (float)s / steps));
        }
    }

    private static bool OnNet(HashSet<long> set, Vector2 p) =>
        set.Contains(Key(Mathf.FloorToInt(p.X / NetCell), Mathf.FloorToInt(p.Y / NetCell)));

    /// <summary>Route every edge in list order (tree edges root-outward, then capital
    /// loops) onto a growing network seeded at the capital. Each route merges into the
    /// nearest existing road, so shared trunks and junctions emerge instead of parallel
    /// spokes.</summary>
    private static void RouteMerged(RoadNetwork net, Vector2 rootPt)
    {
        var netCells = new HashSet<long>();
        Stamp(netCells, rootPt);
        System.Func<Vector2, bool> onNet = p => OnNet(netCells, p);
        foreach (var e in net.Edges)
        {
            e.Path = RoadRouter.Route(e.A, e.B, e.Tier, onNet);
            e.Routed = true;
            StampPath(netCells, e.Path);
        }
        // Drop any REDUNDANT capital-loop highway that turned out badly: a straight line across
        // water (a boxed-in capital A* couldn't route out of), OR a route that climbs sustained
        // steep ground (a highway gouged over a mountain). The spanning tree already connects
        // those capitals, so a clean map beats a phantom sea-bridge or a mountain scar.
        net.Edges.RemoveAll(e => e.Loop && e.Path is { Length: >= 2 } p
            && (SteepRoute(p) || (p.Length == 2 && CrossesWater(p[0], p[1]))));
    }

    private static bool CrossesWater(Vector2 a, Vector2 b)
    {
        var n = Mathf.Max(2, (int)(a.DistanceTo(b) / 6f));
        for (var i = 0; i <= n; i++)
        {
            var q = a.Lerp(b, i / (float)n);
            if (TerrainHeightField.H(q.X, q.Y) < TerrainHeightField.WaterLevel + 0.6f) return true;
        }
        return false;
    }

    /// <summary>True if a routed path climbs more than a short stretch of steep ground — used to
    /// drop a redundant loop that would gouge a mountain scar rather than serve any real need.</summary>
    private static bool SteepRoute(Vector2[] path)
    {
        double steepLen = 0;
        for (var i = 0; i + 1 < path.Length; i++)
        {
            var a = path[i]; var b = path[i + 1];
            var mid = a.Lerp(b, 0.5f);
            var hl = TerrainHeightField.H(mid.X - 8, mid.Y); var hr = TerrainHeightField.H(mid.X + 8, mid.Y);
            var hd = TerrainHeightField.H(mid.X, mid.Y - 8); var hu = TerrainHeightField.H(mid.X, mid.Y + 8);
            var slope = Mathf.Max(Mathf.Abs(hr - hl), Mathf.Abs(hu - hd)) / 16f;
            if (slope > 0.27f) steepLen += a.DistanceTo(b);
            if (steepLen > 120) return true;
        }
        return false;
    }

    /// <summary>Delaunay triangle edges (dedup'd); all-pairs fallback for tiny or
    /// degenerate (collinear) sets. Weighted by TERRAIN cost, not raw distance, so the
    /// spanning tree connects settlements through easy ground and AVOIDS stitching a pair
    /// straight across a mountain when a valley route (via other towns) exists.</summary>
    private static List<(int U, int V, float D)> CandidateEdges(Vector2[] pts)
    {
        var m = pts.Length;
        var cand = new List<(int, int, float)>();
        if (m >= 3)
        {
            var tris = Geometry2D.TriangulateDelaunay(pts);
            var seen = new HashSet<(int, int)>();
            void AddC(int u, int v)
            {
                if (u == v) return;
                var key = u < v ? (u, v) : (v, u);
                if (seen.Add(key)) cand.Add((key.Item1, key.Item2, TerrainCost(pts[u], pts[v])));
            }
            for (var t = 0; t + 2 < tris.Length; t += 3)
            {
                AddC(tris[t], tris[t + 1]);
                AddC(tris[t + 1], tris[t + 2]);
                AddC(tris[t + 2], tris[t]);
            }
        }
        if (cand.Count == 0)   // collinear / m==2 → all pairs
            for (var u = 0; u < m; u++)
                for (var v = u + 1; v < m; v++)
                    cand.Add((u, v, TerrainCost(pts[u], pts[v])));
        return cand;
    }

    /// <summary>A distance that PUNISHES a straight run across steep or deep-water ground, so
    /// the MST prefers pairs with gentle terrain between them. It samples the direct line only
    /// (cheap — this is topology selection, not the final route); the real road still routes
    /// around, but the tree no longer CHOOSES a mountain-straddling pair when a gentler pair of
    /// hops is available.</summary>
    private static float TerrainCost(Vector2 a, Vector2 b)
    {
        var d = a.DistanceTo(b);
        var n = Mathf.Max(2, (int)(d / 8f));
        var seg = d / n;
        var pen = 0f;
        for (var i = 0; i <= n; i++)
        {
            var p = a.Lerp(b, i / (float)n);
            var h = TerrainHeightField.H(p.X, p.Y);
            if (h < TerrainHeightField.WaterLevel + 0.6f) { pen += 6f * seg; continue; }
            var hl = TerrainHeightField.H(p.X - 8, p.Y); var hr = TerrainHeightField.H(p.X + 8, p.Y);
            var hd = TerrainHeightField.H(p.X, p.Y - 8); var hu = TerrainHeightField.H(p.X, p.Y + 8);
            var slope = Mathf.Max(Mathf.Abs(hr - hl), Mathf.Abs(hu - hd)) / 16f;
            if (slope > 0.30f) pen += 30f * seg * (slope / 0.30f);
        }
        return d + pen;
    }

    /// <summary>Connect any leftover disconnected components by their nearest pair
    /// of representatives (rare — only if the candidate graph was disconnected).</summary>
    private static void StitchComponents(Vector2[] pts, List<int>[] adj,
        System.Func<int, int> Find, System.Action<int, int, bool> Union, ref int links)
    {
        var n = pts.Length;
        // one representative index per component root
        var reps = new Dictionary<int, int>();
        for (var i = 0; i < n; i++) reps.TryAdd(Find(i), i);
        var list = reps.Values.ToList();
        while (list.Count > 1)
        {
            int bi = 0, bj = 1;
            var bd = float.MaxValue;
            for (var i = 0; i < list.Count; i++)
                for (var j = i + 1; j < list.Count; j++)
                {
                    if (Find(list[i]) == Find(list[j])) continue;
                    var d = pts[list[i]].DistanceSquaredTo(pts[list[j]]);
                    if (d < bd) { bd = d; bi = i; bj = j; }
                }
            Union(list[bi], list[bj], true);
            links++;
            list.RemoveAt(bj);
        }
    }

    /// <summary>Add a highway between each capital and its nearest capital
    /// (arteries), skipping pairs already joined by a tree edge. Bounded to at
    /// most one loop per capital.</summary>
    private static void AddCapitalLoops(RoadNetwork net, Vector2[] pts, int[] rank,
                                        List<int>[] adj)
    {
        var caps = Enumerable.Range(0, pts.Length).Where(i => rank[i] >= 4).ToList();
        if (caps.Count < 2) caps = Enumerable.Range(0, pts.Length).Where(i => rank[i] >= 3).ToList();
        if (caps.Count < 2) return;

        var added = new HashSet<(int, int)>();
        foreach (var h in caps)
        {
            var best = -1;
            var bd = float.MaxValue;
            foreach (var o in caps)
            {
                if (o == h) continue;
                var d = TerrainCost(pts[h], pts[o]);   // gently-reachable capital, not just the nearest as-the-crow-flies
                if (d < bd) { bd = d; best = o; }
            }
            if (best < 0) continue;
            var key = h < best ? (h, best) : (best, h);
            if (!added.Add(key)) continue;          // already looped this pair
            if (adj[h].Contains(best)) continue;    // already a tree edge
            net.Edges.Add(new RoadEdge { A = pts[h], B = pts[best], Tier = 3, Loop = true });
        }
    }
}
