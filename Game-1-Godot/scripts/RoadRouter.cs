using System;
using System.Collections.Generic;
using Godot;

namespace Game1.Godot;

/// <summary>
/// Routes ONE road onto the gentlest available ground with three hard behaviours the
/// old finite-cost router lacked:
///
///   • MERGE — when an <paramref name="onNetwork"/> predicate is supplied the search
///     terminates the instant it reaches an already-built road (past a short stub from
///     the start). A feeder therefore joins the nearest artery at a real junction
///     instead of running its own parallel ribbon all the way to the far town. This is
///     what turns a bundle of independent MST edges into an arterial network.
///
///   • WATER IS NOT A ROADBED — water is crossable only as a BRIDGE across a NARROW
///     gap. A hard cap on the number of CONSECUTIVE water cells (MaxBridgeSpan, wider
///     for arteries) means a river or inlet gets bridged but a lake or the sea forces a
///     land detour. Roads never trail along or through open water.
///
///   • MOUNTAINS ARE ROUNDED, NOT GOUGED — steep faces are near-walls and there is NO
///     cheap open-cut "tunnel". The gentlest crossing of a ridge is its natural PASS
///     (a low saddle the terrain already carves), so the cost field drives roads to
///     those passes or around the massif entirely — never a trench through the peak.
///
/// A* on an adaptive cost grid (bounded to GridSpan² cells so even a long road routes,
/// coarser). Always returns a non-null polyline; routed ONCE per edge and cached.
/// </summary>
public static class RoadRouter
{
    private const int GridSpan = 170;       // max cells across either axis
    private const float MinCell = 6f;       // finest cell (short roads)

    // --- water / bridges -------------------------------------------------------
    private const float WaterPad = 0.6f;    // treat as water this far above the datum
    private const float BridgeCost = 11f;   // per water cell on a bridge (affordable, not free)
    // Longest run of consecutive water a road may bridge, in WORLD UNITS (not cells — the
    // grid cell size is adaptive, so a cell cap let a long road bridge ~200u of open water).
    // A river or a narrow inlet fits; a lake or the sea does not, so the road detours around.
    private static float MaxBridgeWorld(int tier) => tier >= 2 ? 42f : tier >= 1 ? 30f : 18f;

    // --- slope shaping ---------------------------------------------------------
    private const float SoftStart = 0.10f;   // above this the road already prefers flatter ground
    private const float SoftPenalty = 90f;   // strongly seek the flat within the allowed band
    // Above this (~17°) ground is STEEP. Roads belong to gentle land — a road on a slope is what
    // stretched / staircased / gouged a scar. Steep is not impassable (forbidding it boxes a flat
    // village into a steep bowl and forces an ugly straight-line fallback across water); it is made
    // VERY costly, so roads avoid it for through-routes yet can still make a SHORT last-resort
    // approach to a walled-in settlement instead of plunging into a lake.
    private const float RoadMaxGrade = 0.30f;
    private const float SteepCost = 70f;     // base cost of a steep cell (≫ a flat cell's 1): a detour or
                                             // a pass beats climbing where one exists, without diverting
                                             // roads into lakes when it doesn't (mountain-locked sites are
                                             // culled upstream, so roads rarely face a forced climb at all)
    private const float SteepRamp = 250f;    // steeper still → costlier, so the gentlest steep is chosen

    // Climbing FAST is what makes a road look vertical / staircased. Charge heavily for
    // elevation gained past a walkable grade so the router would rather traverse to a
    // pass or detour than scale a face. This is the dominant term that bends roads away
    // from mountains toward their saddles.
    private const float MaxRoadGrade = 0.26f;
    private const float ClimbPenalty = 44f;

    // Near-admissible: explores the gentle go-arounds the slope/climb costs reward while
    // still pruning enough to stay fast. Bounded by the grid; routed once then cached.
    private const float HeuristicWeight = 1.05f;

    // A merge may only happen once the road has left a short stub around its start, so a
    // town that sits right on an existing road still grows a real (if tiny) spur.
    private const float SnapMinDist = 16f;

    /// <summary>Backwards-compatible 3-arg entry (no network merge): routes fully a→b.</summary>
    public static Vector2[] Route(Vector2 a, Vector2 b, int tier = 0) => Route(a, b, tier, null);

    /// <summary>Route a→b. If <paramref name="onNetwork"/> is non-null the road stops the
    /// moment it reaches existing network (a junction/merge) instead of reaching b.</summary>
    public static Vector2[] Route(Vector2 a, Vector2 b, int tier, Func<Vector2, bool>? onNetwork)
    {
        var maxBridge = MaxBridgeWorld(tier);
        var len = a.DistanceTo(b);
        var margin = Mathf.Max(110f, len * 0.95f);   // room to sweep wide around a massif
        float minX = Mathf.Min(a.X, b.X) - margin, minY = Mathf.Min(a.Y, b.Y) - margin;
        float maxX = Mathf.Max(a.X, b.X) + margin, maxY = Mathf.Max(a.Y, b.Y) + margin;
        float worldW = maxX - minX, worldH = maxY - minY;

        var cell = Mathf.Max(MinCell, Mathf.Max(worldW, worldH) / GridSpan);
        int gw = (int)(worldW / cell) + 1, gh = (int)(worldH / cell) + 1;
        if (gw < 2 || gh < 2) return new[] { a, b };

        Vector2 Center(int cx, int cy) => new(minX + (cx + 0.5f) * cell, minY + (cy + 0.5f) * cell);
        int Idx(int cx, int cy) => cy * gw + cx;

        var startCx = Mathf.Clamp((int)((a.X - minX) / cell), 0, gw - 1);
        var startCy = Mathf.Clamp((int)((a.Y - minY) / cell), 0, gh - 1);
        var goalCx = Mathf.Clamp((int)((b.X - minX) / cell), 0, gw - 1);
        var goalCy = Mathf.Clamp((int)((b.Y - minY) / cell), 0, gh - 1);
        int s = Idx(startCx, startCy), t = Idx(goalCx, goalCy);

        // Lazily-sampled per-cell terrain: land cost, height (for climb), water flag.
        var cost = new float[gw * gh];
        var height = new float[gw * gh];
        var water = new bool[gw * gh];
        System.Array.Fill(cost, float.NaN);
        void Ensure(int i)
        {
            if (!float.IsNaN(cost[i])) return;
            var p = Center(i % gw, i / gw);
            var h = TerrainHeightField.H(p.X, p.Y);
            height[i] = h;
            if (h < TerrainHeightField.WaterLevel + WaterPad) { water[i] = true; cost[i] = BridgeCost; return; }
            var hl = TerrainHeightField.H(p.X - cell, p.Y);
            var hr = TerrainHeightField.H(p.X + cell, p.Y);
            var hd = TerrainHeightField.H(p.X, p.Y - cell);
            var hu = TerrainHeightField.H(p.X, p.Y + cell);
            var slope = Mathf.Max(Mathf.Abs(hr - hl), Mathf.Abs(hu - hd)) / (2f * cell);
            // Steep ground is VERY costly (avoided for through-routes, allowed as a last resort);
            // below the line, flatter is cheaper.
            cost[i] = slope > RoadMaxGrade
                ? SteepCost + (slope - RoadMaxGrade) * SteepRamp
                : 1f + Mathf.Max(0f, slope - SoftStart) * SoftPenalty;
        }

        Ensure(s); Ensure(t);
        cost[s] = 1f; water[s] = false;   // endpoints are always valid land nodes
        cost[t] = 1f; water[t] = false;

        var g = new float[gw * gh];
        var came = new int[gw * gh];
        var wdist = new float[gw * gh];    // consecutive water WORLD DISTANCE ending here (best path)
        var closed = new bool[gw * gh];
        for (var i = 0; i < g.Length; i++) { g[i] = float.PositiveInfinity; came[i] = -1; }
        g[s] = 0f;

        var open = new PriorityQueue<int, float>();
        open.Enqueue(s, 0f);
        var maxGain = MaxRoadGrade * cell;
        var cap = gw * gh;
        var expansions = 0;
        var found = false;
        var snapped = false;
        var terminal = t;
        var bestCell = s;             // closest-to-goal cell reached — the graceful partial fallback
        var bestH = float.MaxValue;
        while (open.Count > 0)
        {
            var cur = open.Dequeue();
            if (closed[cur]) continue;
            closed[cur] = true;
            { float bx = cur % gw - goalCx, by = cur / gw - goalCy; var bh = bx * bx + by * by; if (bh < bestH) { bestH = bh; bestCell = cur; } }
            if (cur == t) { found = true; terminal = t; break; }
            // MERGE: reached an existing road past the start stub → junction here.
            if (onNetwork != null && cur != s)
            {
                var pc = Center(cur % gw, cur / gw);
                if (pc.DistanceTo(a) > SnapMinDist && onNetwork(pc))
                { found = true; snapped = true; terminal = cur; break; }
            }
            if (++expansions > cap) break;
            int ccx = cur % gw, ccy = cur / gw;
            for (var dy = -1; dy <= 1; dy++)
                for (var dx = -1; dx <= 1; dx++)
                {
                    if (dx == 0 && dy == 0) continue;
                    int nx = ccx + dx, ny = ccy + dy;
                    if (nx < 0 || ny < 0 || nx >= gw || ny >= gh) continue;
                    var ni = Idx(nx, ny);
                    if (closed[ni]) continue;
                    Ensure(ni);
                    var step = dx != 0 && dy != 0 ? 1.4142f : 1f;
                    var newWDist = water[ni] ? wdist[cur] + step * cell : 0f;
                    if (newWDist > maxBridge) continue;          // can't bridge that far → no move
                    // level bridge deck → no climb charge on water; else charge over-grade climb.
                    var climb = water[ni] ? 0f
                        : ClimbPenalty * Mathf.Max(0f, Mathf.Abs(height[ni] - height[cur]) - maxGain * step);
                    var ng = g[cur] + step * cost[ni] + climb;
                    if (ng < g[ni])
                    {
                        g[ni] = ng;
                        came[ni] = cur;
                        wdist[ni] = newWDist;
                        float hx = nx - goalCx, hy = ny - goalCy;
                        open.Enqueue(ni, ng + HeuristicWeight * Mathf.Sqrt(hx * hx + hy * hy) * cell);
                    }
                }
        }
        // Unroutable within the grid (walled by open water / cliffs): rather than a naive
        // straight line that plows across the lake, END THE ROAD where the land ran out (the
        // closest-to-goal cell A* reached). The settlement is simply approached, not bridged —
        // far better than an underwater road. Only a truly boxed-in start falls to a straight link.
        if (!found)
        {
            if (bestCell == s) return new[] { a, b };
            terminal = bestCell;
            snapped = true;
        }

        var cells = new List<int>();
        for (var c = terminal; c != -1; c = came[c]) cells.Add(c);
        cells.Reverse();
        var pts = new List<Vector2> { a };
        foreach (var c in cells) pts.Add(Center(c % gw, c / gw));
        if (!snapped) pts.Add(b);
        return Simplify(pts).ToArray();
    }

    /// <summary>Drop interior points that are (nearly) collinear.</summary>
    private static List<Vector2> Simplify(List<Vector2> pts)
    {
        if (pts.Count <= 2) return pts;
        var outp = new List<Vector2> { pts[0] };
        for (var i = 1; i < pts.Count - 1; i++)
        {
            var d0 = (pts[i] - outp[^1]).Normalized();
            var d1 = (pts[i + 1] - pts[i]).Normalized();
            if (d0.Dot(d1) < 0.999f) outp.Add(pts[i]);
        }
        outp.Add(pts[^1]);
        return outp;
    }
}
