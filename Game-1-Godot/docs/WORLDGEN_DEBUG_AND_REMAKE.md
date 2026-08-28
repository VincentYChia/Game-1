# World Generation — Debug Harness & Remake Methodology

**Scope:** Godot 3D world generation (terrain, roads, resources, villages, rendering) and the
headless statistical debug harness that drives it. This doc is the entry point to **revive this
improvement area** — the methodology, how to run the oracle, every tuning knob, the known
residual defects, and where to push next.

**Status (seed 12345):** harness scorecard **12/14 PASS**. Villages **1.8%** on steep flanks
(was 62%), roads **7.6%** of length on slopes (was 20.8%), 0 fallbacks, network fully connected.
Two open flags are *honest and structural* (see [Known residual](#known-residual-open-flags)).

---

## 0. The one lesson: measure what the eye sees, then remake against it

The turning point in this work: the harness reported **13/13 PASS while a screenshot was clearly
bad** (a road stretched up a mountain, a village terraced across a slope). The bug was in the
*oracle*, not just the world — I had flagged the *fraction* of steep road segments, not the
*worst* one, so a 73° road passed. **A metric that averages away the visible defect is worse than
no metric.**

The reusable loop:

1. **Look** at a screenshot; name the specific visual defect.
2. **Make the harness capture it** (a metric that would FLAG that screenshot). If the harness
   still says PASS, the metric is wrong — fix the metric first.
3. **Confirm** the honest harness now flags the current generation.
4. **Remake** the owning system from a principle (not a tweak), re-running the harness each change.
5. **Watch the couplings** the harness surfaces (fixing roads changed water; fixing villages
   changed pad-cut) and correct them.
6. **Be honest about residual** — if a flag is structural (geography-inherent), say so; don't
   re-threshold it green.

You cannot measure GPU frame-rate headless — that still needs a human's eyes. Everything else
(geometry, placement, connectivity, distributions) the harness measures better than a screenshot.

---

## 1. Running the debug harness

The harness generates the *entire* world (terrain field, thinned villages, merged road routing,
a dry-run of resource placement) with **no meshes / colliders / UI**, dumps a report, and quits
(~2–9s). It is env-gated in `WorldBootstrap._Ready` (runs before the visual build).

```bash
# from repo root (python launch.py --dry-run prints the exact Godot path)
GODOT="/c/Users/vipVi/AppData/Local/Programs/Godot/Godot_v4.4.1-stable_mono_win64/Godot_v4.4.1-stable_mono_win64_console.exe"
cd Game-1-Godot
dotnet build Game1.Godot.csproj                       # build the C# first
G1_DEBUG=1 "$GODOT" --headless --path .               # writes worldgen_debug_report.txt + stdout
```

- `G1_DEBUG=1` — run the data-only session and quit.
- `G1_DEBUG_AT="cx,cy"` — re-centre the *detailed* collision + primary resource window on any
  chunk (inspect the frontier, not just spawn). Maps are always whole-world.
- Output: `Game-1-Godot/worldgen_debug_report.txt` (also stdout). **This file is gitignored** —
  it is a regenerable artifact.
- The main scene *is* `WorldBootstrap` (`scenes/Main.tscn`), so headless runs `_Ready` directly —
  no menu to click through.

### What the report contains (a second view, richer than a screenshot)
- **Three whole-world ASCII maps** — HEIGHT, BIOME, and NETWORK (the road+village graph over a
  land/water base). The NETWORK map is the killer view no single camera shot gives.
- **Terrain/collision** — `collider==mesh` integer match (0 ⇒ no fall-through), clip-wall count.
- **Roads** — walks the *actual routed `e.Path`* (not straight A→B): merges, underwater run, deck
  grade, on-slope %, sustained steep climbs, + named offenders with world coords.
- **Connectivity** — graph components, per-village distance to nearest road (unserved settlements).
- **Villages** — steep-flank %, footprint relief, pad cut, tier mix, spacing, offenders.
- **Regional 3×3** — mean height / water% / village count per region (an empty region stands out).
- **Resources (multi-window)** — dry-run over 5 windows: placed, on-road, barren%, density by biome.
- **Scorecard** — 14 PASS/FLAG checks (see below).

Code: [`scripts/WorldGenDebug.cs`](../scripts/WorldGenDebug.cs), hook in
[`scripts/WorldBootstrap.cs`](../scripts/WorldBootstrap.cs) `_Ready` (search `G1_DEBUG`), dry-run in
[`scripts/ResourcePlacer.cs`](../scripts/ResourcePlacer.cs) (`DebugDryPlace` / `_dryRun`).

---

## 2. The design principles (what was remade, and why)

- **Roads & villages belong to the flatlands.** Not "penalise" steep ground — make it *very
  costly* (roads) and *reject* it (villages). A road on a slope is exactly what stretches /
  staircases / gouges a scar; a village on a slope terraces into a mesa.
- **The network is terrain-aware.** The MST weights candidate edges by the steep/water they'd
  cross (`TerrainCost`), so the tree connects through valleys and around massifs instead of
  drawing a straight edge over a ridge. This is what stopped roads gouging mountains — a *routing*
  cost cannot fix a *topology* that chose to cross the mountain.
- **Rendering is batched.** The near window is ONE merged mesh + ONE continuous heightmap collider
  (was ~289 of each), plus a coarse dropped apron for view distance.
- **Don't forbid what you can't reroute.** Hard-forbidding steep terrain boxed flat villages into
  steep bowls and forced straight-line fallbacks across lakes. Very-high-but-finite cost + culling
  the truly-locked *sites* is the robust pattern.

---

## 3. Tuning knobs (for bolstering)

### Roads — [`scripts/RoadRouter.cs`](../scripts/RoadRouter.cs)
| Const | Now | Meaning |
|---|---|---|
| `RoadMaxGrade` | 0.30 | above ~17° is "steep" |
| `SteepCost` / `SteepRamp` | 70 / 250 | cost of a steep cell (≫ flat's 1); raise → roads detour harder (but can divert into water if too high) |
| `SoftStart` / `SoftPenalty` | 0.18 / 34 | gentle-roll discouragement (seek the flat) |
| `MaxBridgeWorld(tier)` | 42/30/18u | longest **world-unit** water span a road may bridge (was cells — adaptive cell size let a "bridge" span ~200u) |
| `SnapMinDist` | 16u | a feeder must leave this stub before it may merge onto an artery |
| `HeuristicWeight` | 1.05 | near-admissible A* (explores gentle detours) |

### Road network — [`scripts/RoadNetwork.cs`](../scripts/RoadNetwork.cs)
- `TerrainCost(a,b)` — MST edge weight = distance + **steep penalty** (`30 * seg * slope/0.30`)
  + water penalty (`6 * seg`). Raise the steep coefficient → fewer/gentler mountain crossings
  (diminishing once crossings are structural).
- `RouteMerged` — routes all edges once, globally, root-outward, with `onNetwork` merge-snap; then
  drops redundant capital **loops** whose route `CrossesWater` or `SteepRoute` (sustained >0.27 for
  >120u). Tree edges are never dropped (connectivity).

### Villages — [`scripts/WorldBootstrap.cs`](../scripts/WorldBootstrap.cs) (`ThinVillages`)
| Const | Now | Meaning |
|---|---|---|
| `VillageSteepSlope` / `VillageMaxSteepFrac` | 20° / 0.20 | reject if >20% of footprint+verge is >20° |
| `VillageHardSlope` | 28° | and no footprint sample may be this steep (a cliff in town) |
| `VillageMaxRelief` | 13u | footprint relief cap → the flattening pad stays a shelf, not a mesa |
| water-locked ring | 26u, ≥5/8 water | island/spit rejected (would need a sea causeway) |
| mountain-locked rings | 45u >55% **or** 90u >70% steep | a flat pocket walled by mountains (no gentle road out) rejected |
| `SlopeDeg` | — | local slope helper used by the gates |

Pad: `BuildVillagePads` — `radius = maxR + 2` (full footprint, no cap — safe because relief ≤13),
`blend = 10`, `level = NaturalHeight(centroid)`.

### Rendering — [`scripts/WorldBootstrap.cs`](../scripts/WorldBootstrap.cs)
- Terrain mesh + collider: `BuildTerrain` (merged core), `BuildTerrainApron` (parallel coarse
  sheet), consts `ApronExtra=10`, `ApronStep=4`, `ApronDrop=1.2`, far skirt `FarRadius=44`.
- **FPS knobs** (`AddSun`): `EnableVolumetricFog` default **false** (toggle in inspector for
  godrays), `SsilEnabled=false`, SSAO radius 1.0 / intensity 1.2, shadows `Parallel2Splits` +
  `DirectionalShadowMaxDistance=180`, near-water subdivide 96². These trade the heaviest,
  most-subtle effects for speed while keeping glow + distance haze.

### Resources — [`scripts/ResourcePlacer.cs`](../scripts/ResourcePlacer.cs)
- Deposit-based (monotype stands, dense core → thinning edge). `ResourceCap=1700`,
  `DepositsPerDensity=0.7`, `MaxDepositsPerChunk=2`, `OnRoadReject=0.04` (RoadWeight gate),
  tree road-clearance `edge=2.0`.

---

## 4. The scorecard (what "done" measures)

14 checks in `WorldGenDebug` (`Score(...)`). Current status seed 12345:

| Check | Status | Note |
|---|---|---|
| collider==mesh (no fall-through) | PASS | max\|H−HMesh\|=0 |
| roads merge into arteries | PASS | ~240 merges |
| no underwater roads | PASS | maxRun 57u (bridges only) |
| roads off cliffs / off slopes | PASS | 7.6% on >15° |
| **no widespread steep roads** | **FLAG** | 8 *structural* mountain-pass crossings (see below) |
| no water/cliff straight fallbacks | PASS | 0 |
| network fully connected | PASS | 1 component |
| settlements road-served | PASS | 0 unserved |
| villages off steep flanks | PASS | 1.8% |
| villages not underwater/mesa | PASS | max pad cut 12.7u |
| **nothing placed on roads** | **FLAG** | 8 world-wide = window-boundary dry-run artifact (RoadWeight gate covers it in-game) |
| no barren wedge | PASS | |

---

## 5. Known residual (open flags) — for the next bolster

1. **~8 structural mountain-pass crossings.** Population clusters separated by mountain ranges —
   the network *must* cross somewhere. Verified persistent even at 2× the MST steep penalty, so it
   is **not** fixable by routing/topology tuning. A realistic mountain-pass highway, unlike the
   *widespread* slope-climbing before. To actually remove them you must change one of:
   - **Terrain:** carve guaranteed low **passes** through ranges (the router already prefers low
     saddles — give it one). This is the cleanest fix but touches `TerrainHeightField` (a 7/10 you
     may not want to disturb).
   - **Render them well:** a proper switchbacked/tunnelled mountain-pass ribbon instead of a draped
     climb (risk: staircase look — needs a smoothed deck + switchback geometry).
   - **Cull the far cluster:** drop settlements a range away that only connect by a steep crossing
     (a leaf-cull was tried; it disconnected *other* leaves without touching the through-routes —
     needs a smarter component/pass analysis).
2. **8 on-road resources (dry-run only).** A window-boundary artifact: the dry-run has no
   `RoadWeight` corridor gate (that's set per-window in `BuildRoadGrid`), only `RoadClear`. In-game
   both gates run. To make the harness faithful, call the road-grid rasterisation for the test
   window before the dry placement.
3. **Recenter hitch `sync≈490ms`** (`[worldbuild]` line: roadgrid 248 + terrain 168). Not FPS —
   the per-window road-grade carve + mesh build. Candidate: cache the global road grid instead of
   re-rasterising per window.
4. **Rendering FPS unverified.** The GPU cuts (fog/SSIL/shadows) are high-confidence but need a
   human to confirm the frame-rate actually moved and the look still satisfies.

---

## 6. File map

| File | Role |
|---|---|
| `scripts/WorldGenDebug.cs` | the harness (maps, scorecard, offenders, dry-run analysis) |
| `scripts/RoadRouter.cs` | A* road routing (steep-costly, water-bridge-capped, merge-snap, partial-path fallback) |
| `scripts/RoadNetwork.cs` | terrain-aware MST + tiering + capital loops + `RouteMerged` |
| `scripts/WorldBootstrap.cs` | pipeline: terrain mesh/collider/apron, `ThinVillages`, `BuildVillagePads`, `BuildRoadGrid`, rendering env, `G1_DEBUG` hook |
| `scripts/TerrainHeightField.cs` | the global height field `H/HMesh/NaturalHeight/PadHeight` (a 7/10 — preserve its seam) |
| `scripts/ResourcePlacer.cs` | deposit placement + `DebugDryPlace` |
| `scripts/WorldContext.cs` | per-window shared spatial model (ChunkType, Slope, RoadClear, occupancy) |

**Seams that must not break:** `TerrainHeightField.H(x,y)` and siblings (100+ consumers incl.
player collision + save/load), node names (`Terrain/Roads/Villages/Resources/Scatter/Npcs/Caves`),
`BuildWindow` order (pads → road-grid → terrain → villages → npcs → enemies, then queued).
