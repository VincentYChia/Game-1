using Game1.Core.Content;
using Game1.Core.Data;
using Game1.Core.World;
using Game1.Core.World.Geography;
using Godot;

namespace Game1.Godot;

/// <summary>
/// P3 engine entry — a SINGLE, streamed, mask-driven world generator.
///
/// The world used to be built by two DISAGREEING code paths: a rich static core
/// at spawn (villages, NPCs, enemies, spaced harvestables) and a cruder streamed
/// frontier (terrain + scatter only). That split — plus a dozen Build* passes
/// each re-deriving biome/height/slope/road-clearance independently — is why the
/// world read as "pieced together" and why the frontier never matched the core.
///
/// This is the rebuild: ONE pipeline, <see cref="BuildWindow"/>, runs for every
/// streamed window (spawn and frontier alike), and every placer reads the SAME
/// masks from a shared <see cref="WorldContext"/>. Terrain, roads, villages, NPCs,
/// harvestable resources, ground cover, caves, and enemies ALL stream together, so
/// the frontier is core-quality by construction. Origin fixtures (the 20 starter
/// stations, the UI, the player, the sky) are built once. Simulation stays planar
/// (ADR-6): tile (x, y) → world (x, 0, z); every rule is certified.
/// </summary>
public partial class WorldBootstrap : Node3D
{
    [Export] public long WorldSeed { get; set; } = 12345;
    [Export] public int ChunkRadius { get; set; } = 8;
    [Export] public int ChunkSize { get; set; } = 16;

    /// <summary>Generate the full certified geographic world (nations, regions,
    /// biomes, danger, villages). Off = legacy biome-generator world.</summary>
    [Export] public bool UseGeographic { get; set; } = true;

    // --- vibrancy dials (live-tunable; "punchy storybook" defaults) ---
    [Export] public float Saturation { get; set; } = 1.18f;
    [Export] public float Contrast { get; set; } = 1.06f;
    [Export] public float GlowStrength { get; set; } = 1.1f;
    // Off by default for speed: volumetric fog is one of the heaviest GPU effects and the cheap
    // distance Fog below already carries the atmosphere. Flip on in the inspector for godrays.
    [Export] public bool EnableVolumetricFog { get; set; } = false;
    [Export] public bool EnableDayNight { get; set; } = true;
    /// <summary>Heaviest GPU effect — off by default (perf toggle, not needed for
    /// correctness; SSIL already gives the color-bleed "alive" read).</summary>
    [Export] public bool EnableSdfgi { get; set; } = false;

    // The playable resource core radius (chunks). Resources stream over this reach;
    // terrain/villages/NPCs/caves use the wider ChunkRadius.
    private const int ResourceRadius = 5;

    private WorldMap? _worldMap;
    private List<VillageRecord> _villages = new();
    // A settlement belongs on a genuinely FLAT basin, not a hillside. The gate is on FLATNESS,
    // not relief: sample the footprint (+ verge) and require the large majority of it to be
    // gentle ground, with no cliff anywhere in town. The old relief gate let a village terrace
    // across a uniform slope as long as its total rise stayed under a cap — which read as "town
    // on a mountainside". Requiring most of the footprint to be near-level is what actually looks
    // right, and it pairs with roads (which now refuse steep ground) so neither climbs a slope.
    // Reject a STEEP FLANK, not "not-perfectly-flat": this terrain deliberately rolls at ~9-12°,
    // so a gentle-rolling footprint (which the pad flattens cleanly) is fine — only a genuine
    // hillside perch reads wrong. So gate on how much of the footprint is actually STEEP.
    private const double VillageSteepSlope = 20.0;   // a footprint sample steeper than this is "steep"
    private const double VillageMaxSteepFrac = 0.20; // reject if more than this fraction of the footprint is steep
    private const double VillageHardSlope = 28.0;    // and NO sample may be that steep (no cliff/flank in town)
    private const double VillageMaxRelief = 13.0;    // footprint relief cap → the flattening pad stays a shelf, not a mesa
    private BiomeGenerator? _biomes;
    private MapWaypointConfig? _mapConfig;
    private RoadNetwork? _roadNet;                 // settlement roads (built once)
    private ResourcePlacer? _resourcePlacer;       // harvestable-resource system
    private Label? _resDebug;                       // F9 resource-spawn diagnostics overlay

    // Streaming: the world follows the player so they never walk off the built
    // window into the void. _center is the chunk the current window is built
    // around; when the player wanders far enough, we rebuild around them.
    private PlayerController? _streamPlayer;
    private int _centerCX, _centerCY;
    private const int StreamThreshold = 5;
    private CombatWorld? _combat;

    // Distant low-detail terrain (no collision) — a HORIZON to navigate toward, and a
    // stable backdrop so the near-window rebuild isn't a blank-fog pop. Rebuilt only
    // every FarThreshold chunks and sits ~3u under the detailed near terrain, which
    // covers it where they overlap.
    private int _farCX = 99999, _farCY = 99999;
    private const int FarRadius = 44;
    private const int FarStep = 10;
    private const int FarThreshold = 14;

    // Mid-detail APRON: a coarse, collision-free sheet that reaches ChunkRadius+ApronExtra
    // chunks past the sharp near window, seated ApronDrop below it so the core overdraws
    // the seam (same trick as the far skirt, but denser + closer). It fills the fidelity
    // gap between the crisp core and the distant skirt so the eye "renders more at once"
    // without multiplying draw calls — the whole apron is ONE mesh.
    private const int ApronExtra = 10;
    private const int ApronStep = 4;
    private const float ApronDrop = 1.2f;   // seated just under the core; small enough the seam lip barely reads

    // Amortised build: TERRAIN is built synchronously each window (so the player is
    // always grounded — no fall-through), but the heavy DECORATION + RESOURCES fill
    // in over the next frames from this queue, so crossing a chunk boundary no longer
    // hard-freezes — it loads smoothly instead.
    private readonly Queue<System.Action> _streamQueue = new();
    private const int StreamStepsPerFrame = 3;

    // Per-tier road half-basis for the terrain GRADE corridor + visual ribbon
    // widths (road CLEARANCE lives in WorldContext).
    private static readonly float[] RoadWidth = { 1.0f, 1.9f, 3.2f, 5.0f };

    // Atmosphere refs retained so DayNightCycle can drive them each frame.
    private DirectionalLight3D? _sun;
    private ProceduralSkyMaterial? _skyMat;
    private global::Godot.Environment? _env;
    private DayNightCycle? _dayNight;

    // Env-gated screenshot harness (G1_SHOT=<dir>) — a headless run captures the world
    // to PNGs (overview / eye-level / top-down) for visual verification. Off in play.
    private string? _shotDir;
    private int _shotTick;
    private Camera3D? _shotCam;

    /// <summary>Chunk → biome type (geo chunk type, else legacy biome) — shared by
    /// AmbientLife so ambience matches the ground.</summary>
    internal string BiomeTypeAt(int cx, int cy) =>
        _worldMap?.GetChunkData(cx, cy)?.ChunkType
        ?? _biomes?.GetChunkType(cx, cy) ?? "forest";

    // The 15 geographic chunk types → terrain colors (glue-only palette; internal
    // so MapScreen paints the world map from the same table).
    internal static readonly Dictionary<string, Color> GeoColors = new()
    {
        ["forest"] = new Color(0.24f, 0.47f, 0.24f),
        ["dense_thicket"] = new Color(0.16f, 0.35f, 0.18f),
        ["cave"] = new Color(0.41f, 0.41f, 0.43f),
        ["deep_cave"] = new Color(0.27f, 0.27f, 0.31f),
        ["quarry"] = new Color(0.59f, 0.55f, 0.49f),
        ["rocky_highlands"] = new Color(0.51f, 0.49f, 0.45f),
        ["wetland"] = new Color(0.35f, 0.51f, 0.43f),
        ["lake"] = new Color(0.27f, 0.43f, 0.71f),
        ["river"] = new Color(0.31f, 0.51f, 0.75f),
        ["flooded_cave"] = new Color(0.29f, 0.37f, 0.51f),
        ["rocky_forest"] = new Color(0.39f, 0.47f, 0.35f),
        ["crystal_cavern"] = new Color(0.55f, 0.43f, 0.71f),
        ["overgrown_ruins"] = new Color(0.47f, 0.51f, 0.39f),
        ["barren_waste"] = new Color(0.67f, 0.59f, 0.43f),
        ["cursed_marsh"] = new Color(0.39f, 0.35f, 0.47f),
    };

    // =====================================================================
    //  BOOT — one-time setup, then hand off to the streamed pipeline
    // =====================================================================
    public override void _Ready()
    {
        var root = ContentPaths.TryGetContentRoot();
        if (root is null)
        {
            GD.PushError("Game-1-modular content root not found — set GAME1_CONTENT_ROOT");
            return;
        }
        IconCache.Init(root);   // item/skill/etc PNG loader

        var worldGen = new WorldGenerationConfig();
        worldGen.Load(root);
        var mapConfig = new MapWaypointConfig();
        mapConfig.Load(root);
        var biomes = new BiomeGenerator(WorldSeed, worldGen);
        _biomes = biomes;
        _mapConfig = mapConfig;

        var resourceDb = new ResourceNodeDatabase();
        resourceDb.LoadFromFiles(root);
        var templateDb = new ChunkTemplateDatabase();
        templateDb.LoadFromFiles(root);
        var chunkGen = new ChunkGenerator(resourceDb, worldGen, templateDb);

        if (UseGeographic)
        {
            // The certified geographic pipeline — full 512x512 world in a few
            // seconds; same seed = same world as the Python game.
            var geoCfg = GeographicConfig.Load(root);
            var pipe = new WorldGeneratorPipeline(WorldSeed, geoCfg, root);
            _worldMap = pipe.Generate();
            _villages = pipe.Villages;
            GD.Print($"Geography: {_worldMap.Nations.Count} nations, " +
                     $"{_worldMap.Regions.Count} regions, {_villages.Count} villages — " +
                     string.Join(", ", _worldMap.Nations.Values.Select(nn => nn.Name)));
        }

        // Elevation field + settlement road network (both built once).
        TerrainHeightField.Init(_worldMap, WorldSeed);
        _villages = ThinVillages(_villages);   // halve density + drop cliff-perched sites
        _roadNet = RoadNetwork.Build(_villages);
        GD.Print($"Roads: {_roadNet.Edges.Count} edges across {_villages.Count} settlements");

        // Sky + player (origin fixtures).
        AddSun();
        var player = AddPlayer();
        _streamPlayer = player;
        player.AddChild(new AmbientLife(BiomeTypeAt, () => _dayNight?.Fraction ?? 0.5f)
        { Name = "AmbientLife" });

        // The certified combat/sim slice. Enemies are NOT spawned here anymore —
        // they stream with the window (see StreamEnemies), so the frontier gets
        // hostiles too instead of an origin-only cluster.
        var combat = new CombatWorld { Name = "CombatWorld" };
        AddChild(combat);
        combat.Build(root, WorldSeed, biomes, chunkGen, player,
                     enemyChunkRadius: ChunkRadius, worldMap: _worldMap);
        combat.RecenterWorld = RecenterWorld;   // F5/F6 tour + map clicks
        _combat = combat;
        _resourcePlacer = new ResourcePlacer(resourceDb, chunkGen, WorldSeed);
        AddRoadLandmarks(combat);   // longest bridge / tunnel → the tour

        // Headless DATA-ONLY verification (env G1_DEBUG): everything generative has run
        // (height field, thinned villages, MERGED road routing, resource placer) — dump a
        // statistical report and QUIT before building any meshes/UI. Lets changes be checked
        // by numbers (road paths, collisions, village relief, resource placement) not pixels.
        if (System.Environment.GetEnvironmentVariable("G1_DEBUG") != null)
        {
            WorldGenDebug.Dump(_worldMap, WorldSeed, _villages, _roadNet!, biomes, _resourcePlacer,
                               combat, ChunkRadius, ResourceRadius, ChunkSize);
            GetTree().Quit();
            return;
        }

        // Origin fixtures: the 20 free starter stations (world_system.py:671-692)
        // and the whole UI. Built once — they don't stream.
        BuildStations(combat);
        BuildUi(combat, player);

        // The whole streamed world (terrain, roads, villages, NPCs, resources,
        // ground cover, caves, enemies) through the ONE pipeline, centred on spawn.
        BuildWindow(0, 0);
        BuildFarTerrain(0, 0);

        GD.Print($"World built: seed {WorldSeed}, streaming window ±{ChunkRadius} chunks");

        _shotDir = System.Environment.GetEnvironmentVariable("G1_SHOT");
        if (_shotDir != null && _dayNight != null) _dayNight.SetFraction(0.5f);  // noon — clearest light
        DumpWorldStats();
    }

    private static string Pct(int a, int b) => b == 0 ? "0.0%" : $"{100f * a / b:F1}%";

    /// <summary>Env-gated (G1_STATS) descriptive scan of the generated world — height
    /// &amp; slope distributions, cave/grotto density, and how many settlements/road
    /// samples land underwater or on a cliff. Numbers to tune generation against
    /// (steepness, buried lakes, grotto spam) instead of eyeballing screenshots.</summary>
    private void DumpWorldStats()
    {
        if (System.Environment.GetEnvironmentVariable("G1_STATS") == null || _worldMap == null) return;
        var sw = System.Diagnostics.Stopwatch.StartNew();
        float wl = TerrainHeightField.WaterLevel;
        int halfC = _worldMap.WorldSize / 2;
        float halfT = halfC * 16f;
        int step = Mathf.Max(16, (int)(halfT * 2 / 200));   // ~200 samples/axis

        // --- height + slope over the whole world (NaturalHeight = no roads) ---
        var hHist = new int[8]; var sHist = new int[6]; var rHist = new int[5];
        int nSamp = 0, nWater = 0, nLandRelief = 0; float maxH = -1e9f, sumH = 0, sumDeg = 0, maxDeg = 0, sumRelief = 0;
        float Deg(double x, double y)
        {
            double hl = TerrainHeightField.NaturalHeight(x - 4, y), hr = TerrainHeightField.NaturalHeight(x + 4, y);
            double hd = TerrainHeightField.NaturalHeight(x, y - 4), hu = TerrainHeightField.NaturalHeight(x, y + 4);
            return Mathf.RadToDeg(Mathf.Atan((float)Math.Max(Math.Abs(hr - hl), Math.Abs(hu - hd)) / 8f));
        }
        for (var y = -halfT; y < halfT; y += step)
            for (var x = -halfT; x < halfT; x += step)
            {
                var h = (float)TerrainHeightField.NaturalHeight(x, y);
                nSamp++; sumH += h; maxH = Mathf.Max(maxH, h);
                if (h < wl) nWater++;
                hHist[h < 0 ? 0 : h < 50 ? 1 : h < 100 ? 2 : h < 200 ? 3 : h < 300 ? 4 : h < 400 ? 5 : h < 500 ? 6 : 7]++;
                var deg = Deg(x, y); sumDeg += deg; maxDeg = Mathf.Max(maxDeg, deg);
                sHist[deg < 15 ? 0 : deg < 30 ? 1 : deg < 45 ? 2 : deg < 60 ? 3 : deg < 75 ? 4 : 5]++;
                // LOCAL RELIEF = elevation range over a ~48-tile walking window (does the
                // ground give you something at the scale you actually walk?). Land-only.
                if (h >= wl)
                {
                    float mn = 1e9f, mx = -1e9f;   // true local max-min over a 5x5 @12t grid
                    for (var ry = -24; ry <= 24; ry += 12)
                        for (var rx = -24; rx <= 24; rx += 12)
                        {
                            var hh = (float)TerrainHeightField.NaturalHeight(x + rx, y + ry);
                            mn = Mathf.Min(mn, hh); mx = Mathf.Max(mx, hh);
                        }
                    var relief = mx - mn;
                    sumRelief += relief; nLandRelief++;
                    rHist[relief < 5 ? 0 : relief < 15 ? 1 : relief < 30 ? 2 : relief < 60 ? 3 : 4]++;
                }
            }
        GD.Print($"[stats] world={_worldMap.WorldSize}ch samples={nSamp} step={step}t  maxH={maxH:F0} meanH={sumH / nSamp:F0}  under-water={Pct(nWater, nSamp)}");
        GD.Print($"[stats] height:  <0={Pct(hHist[0], nSamp)} 0-50={Pct(hHist[1], nSamp)} 50-100={Pct(hHist[2], nSamp)} 100-200={Pct(hHist[3], nSamp)} 200-300={Pct(hHist[4], nSamp)} 300-400={Pct(hHist[5], nSamp)} 400-500={Pct(hHist[6], nSamp)} 500+={Pct(hHist[7], nSamp)}");
        GD.Print($"[stats] slope:  <15={Pct(sHist[0], nSamp)} 15-30={Pct(sHist[1], nSamp)} 30-45={Pct(sHist[2], nSamp)} 45-60={Pct(sHist[3], nSamp)} 60-75={Pct(sHist[4], nSamp)} 75+={Pct(sHist[5], nSamp)}   mean={sumDeg / nSamp:F1}deg max={maxDeg:F0}deg");
        GD.Print($"[stats] relief@48t (land):  flat<5={Pct(rHist[0], nLandRelief)} 5-15={Pct(rHist[1], nLandRelief)} 15-30={Pct(rHist[2], nLandRelief)} 30-60={Pct(rHist[3], nLandRelief)} 60+={Pct(rHist[4], nLandRelief)}   mean={sumRelief / Math.Max(1, nLandRelief):F1}u");

        // --- chunk types + grotto (cave-chunk) density ---
        var typeCount = new Dictionary<string, int>();
        int caveChunks = 0, grottos = 0, total = 0;
        foreach (var (k, geo) in _worldMap.ChunkData)
        {
            total++;
            typeCount[geo.ChunkType] = typeCount.GetValueOrDefault(geo.ChunkType) + 1;
            if (TerrainHeightField.IsCaveChunk(k.X, k.Y)) caveChunks++;
            if (TerrainHeightField.GrottoAt(k.X, k.Y)) grottos++;
        }
        GD.Print($"[stats] chunks={total}  cave-chunks={caveChunks} ({Pct(caveChunks, total)})  actual grottos={grottos} ({Pct(grottos, total)})");
        GD.Print("[stats] top types: " + string.Join("  ", typeCount.OrderByDescending(kv => kv.Value).Take(8).Select(kv => $"{kv.Key}={kv.Value}")));

        // --- villages: underwater / on steep ---
        int vWater = 0, vSteep = 0, vOk = 0;
        foreach (var v in _villages)
        {
            double cx = v.CenterChunk.X * 16 + 8, cy = v.CenterChunk.Y * 16 + 8;
            var h = TerrainHeightField.NaturalHeight(cx, cy);
            if (h < wl + 0.5) vWater++; else if (Deg(cx, cy) > 25f) vSteep++; else vOk++;
        }
        GD.Print($"[stats] villages={_villages.Count}  underwater={vWater}  steep(>25deg)={vSteep}  ok={vOk}");

        // --- roads: straight A->B samples over water / over cliff ---
        int rSamp = 0, rWater = 0, rSteep = 0;
        if (_roadNet != null)
            foreach (var e in _roadNet.Edges)
            {
                var n = Mathf.Max(2, (int)(e.A.DistanceTo(e.B) / 8f));
                for (var i = 0; i <= n; i++)
                {
                    var p = e.A.Lerp(e.B, i / (float)n); rSamp++;
                    if (TerrainHeightField.NaturalHeight(p.X, p.Y) < wl) rWater++;
                    if (Deg(p.X, p.Y) > 45f) rSteep++;
                }
            }
        GD.Print($"[stats] road straight-samples={rSamp}  over-water={Pct(rWater, rSamp)}  over-cliff(>45deg)={Pct(rSteep, rSamp)}");
        GD.Print($"[stats] scan {sw.ElapsedMilliseconds}ms");
    }

    // =====================================================================
    //  THE ONE PIPELINE — builds an identical, coherent window anywhere
    // =====================================================================

    /// <summary>Build every streamed system for the window centred on
    /// (<paramref name="cx"/>, <paramref name="cy"/>), reading one shared
    /// <see cref="WorldContext"/> so the frontier is generated exactly like the
    /// core. Order matters: grade the ground to the roads → terrain → villages
    /// (which reserve their footprint) → road ribbons → harvestables (spaced clear
    /// of roads/villages) → ground cover → NPCs → caves → enemies.</summary>
    private void BuildWindow(int cx, int cy)
    {
        if (_biomes is null || _combat is null || _resourcePlacer is null) return;

        _streamQueue.Clear();   // drop any steps still pending for a superseded window

        var ctx = new WorldContext(cx, cy, ChunkRadius, ResourceRadius, ChunkSize,
                                   WorldSeed, _worldMap, _biomes, _roadNet);

        // --- SYNC (grounds the player before the frame ends) ---
        // Per-phase timing: this is the work that BLOCKS the main thread on an F5/F6
        // teleport or a stream-recenter. One compact line per rebuild in the console.
        var _sw = System.Diagnostics.Stopwatch.StartNew();
        long _lap() { var ms = _sw.ElapsedMilliseconds; _sw.Restart(); return ms; }
        BuildVillagePads(ctx);         var tPads = _lap();  // carve flat shelves FIRST
        BuildRoadGrid(ctx);            var tRoad = _lap();  // grade terrain toward roads
        BuildTerrain(ctx);             var tTerr = _lap();  // "Terrain" (+ water)
        BuildVillages(ctx);            var tVill = _lap();  // "Villages" on the shelf
        BuildNpcs(ctx);                var tNpc  = _lap();  // "Npcs"
        _combat.StreamEnemies(cx, cy); var tEnem = _lap();  // hostiles (certified spawn)
        GD.Print($"[worldbuild] c=({cx},{cy}) pads={tPads} roadgrid={tRoad} " +
                 $"terrain={tTerr} villages={tVill} npcs={tNpc} enemies={tEnem} " +
                 $"sync={tPads + tRoad + tTerr + tVill + tNpc + tEnem}ms");

        // --- STREAMED over the next frames (decoration + resources; none of this
        //     grounds the player, so it can fill in without a freeze) ---
        var resParent = new Node3D { Name = "Resources" };
        AddChild(resParent);
        _resourcePlacer.QueueWindow(resParent, ctx, _combat, _streamQueue);
        QueueScatter(ctx);            // "Scatter" ground cover (decoration only)
        QueueRoads(ctx);              // "Roads" ribbons
        _streamQueue.Enqueue(() => BuildCaves(ctx));   // "Caves"

        _centerCX = cx;
        _centerCY = cy;
    }

    /// <summary>Rebuild the streamed world around a new centre — frees the window
    /// nodes and re-runs the ONE pipeline. Shared by movement streaming, the F5/F6
    /// landscape tour, and map clicks, so every entry point yields the SAME world.
    /// Origin fixtures (stations, UI, player, sky) are untouched.</summary>
    public void RecenterWorld(int cx, int cy)
    {
        _streamQueue.Clear();        // drop the old window's pending build steps FIRST
        _combat?.ClearResources();   // drop stale resource handles before visuals free
        _combat?.ClearNpcs();        // drop stale NPC handles before visuals free
        GetNodeOrNull("Terrain")?.Free();
        GetNodeOrNull("Villages")?.Free();
        GetNodeOrNull("Roads")?.Free();
        GetNodeOrNull("Resources")?.Free();
        GetNodeOrNull("Scatter")?.Free();
        GetNodeOrNull("Npcs")?.Free();
        GetNodeOrNull("Caves")?.Free();
        BuildWindow(cx, cy);
    }

    /// <summary>Env-gated (G1_SHOT) capture: after streaming settles, park a camera at
    /// three vantages and write PNGs, then quit. Lets a headless run be visually
    /// inspected. Milestones are frame counts so slow streaming just delays the shot.</summary>
    private Vector3 _shotTarget;
    private void StepScreenshots()
    {
        _shotTick++;
        var p = _streamPlayer?.GlobalPosition ?? Vector3.Zero;
        void Cam(Vector3 pos, Vector3 look, Vector3 up)
        {
            _shotCam ??= new Camera3D { Far = 6000f, Fov = 68f };
            if (_shotCam.GetParent() == null) AddChild(_shotCam);
            _shotCam.GlobalPosition = pos;
            _shotCam.LookAt(look, up);
            _shotCam.Current = true;
        }
        void Save(string name)
        {
            var img = GetViewport().GetTexture().GetImage();
            img.SavePng(System.IO.Path.Combine(_shotDir!, name));
            GD.Print($"[shot] saved {name}");
        }
        float Ground(Vector3 c) => TerrainHeightField.H(c.X, c.Z);
        switch (_shotTick)
        {
            case 100:  // clear the boot overlay (a full-screen CanvasLayer) so the world shows
                GetTree().Root.FindChild("ClassSelect", true, false)?.QueueFree();
                break;
            // --- spawn basin ---
            case 180: Cam(p + new Vector3(70, 60, 70), p + new Vector3(0, 2, 0), Vector3.Up); break;
            case 188: Save("spawn_overview.png"); break;
            case 196: Cam(p + new Vector3(0.5f, 300, 0.5f), p, Vector3.Back); break;
            case 204: Save("spawn_topdown.png"); break;
            // --- jump to the tallest mountain within reach, to see steepness + roads ---
            case 214:
            {
                // Jump to a subject region: G1_SHOT_TARGET = "cave" (densest cave area) or
                // default = tallest mountains/highlands chunk.
                var want = System.Environment.GetEnvironmentVariable("G1_SHOT_TARGET");
                int bcx = 0, bcy = 0; float bScore = -1e9f;
                if (_worldMap != null)
                    foreach (var (k, geo) in _worldMap.ChunkData)
                    {
                        float score;
                        if (want == "cave")
                        {
                            if (!TerrainHeightField.IsCaveChunk(k.X, k.Y)) continue;
                            score = 0;
                            for (var dy = -1; dy <= 1; dy++)
                                for (var dx = -1; dx <= 1; dx++)
                                    if (TerrainHeightField.IsCaveChunk(k.X + dx, k.Y + dy)) score++;
                        }
                        else
                        {
                            if (!_worldMap.Regions.TryGetValue(geo.RegionId, out var r)
                                || (r.Identity != "mountains" && r.Identity != "highlands")) continue;
                            score = (float)TerrainHeightField.NaturalHeight(k.X * 16 + 8, k.Y * 16 + 8);
                        }
                        if (score > bScore) { bScore = score; bcx = k.X; bcy = k.Y; }
                    }
                _shotTarget = new Vector3(bcx * 16 + 8, 0, bcy * 16 + 8);
                GD.Print($"[shot] subject={(want ?? "mountain")} chunk ({bcx},{bcy}) score={bScore:F0} -> recenter");
                _streamPlayer = null;   // stop the player-follow from snapping the window back
                RecenterWorld(bcx, bcy);
                break;
            }
            // wait ~110 frames for the mountain window to stream in, then shoot it
            case 326:
            {
                // Stay INSIDE the ±128u built window: elevated + close, looking down at the
                // summit so the local slope + any road reads (a far side-on shot would look
                // at unbuilt void).
                var gh = Ground(_shotTarget);
                Cam(new Vector3(_shotTarget.X + 95, gh + 85, _shotTarget.Z + 95),
                    new Vector3(_shotTarget.X, gh - 30, _shotTarget.Z), Vector3.Up);
                break;
            }
            case 334: Save("mtn_overview.png"); break;
            case 340:
            {
                var gh = Ground(_shotTarget);
                var c = new Vector3(_shotTarget.X, gh + 3.5f, _shotTarget.Z);
                var dir = new Vector3(-_shotTarget.X, 0, -_shotTarget.Z);   // downhill = toward origin
                dir = dir.LengthSquared() < 1f ? Vector3.Right : dir.Normalized();
                Cam(c, c + dir * 40f + Vector3.Down * 10f, Vector3.Up);
                break;
            }
            case 348: Save("mtn_ground.png"); break;
            case 354: Cam(new Vector3(_shotTarget.X + 1, Ground(_shotTarget) + 240, _shotTarget.Z + 1), new Vector3(_shotTarget.X, Ground(_shotTarget) - 40, _shotTarget.Z), Vector3.Back); break;
            case 362: Save("mtn_topdown.png"); break;
            case 370: GetTree().Quit(); break;
        }
    }

    /// <summary>Stream the world with the player: once they wander past the built
    /// window, rebuild everything around their chunk so there's never open void —
    /// and the settlements/hostiles/harvestables follow them (frontier = core).</summary>
    public override void _Process(double delta)
    {
        // fill in a few streamed decoration/resource steps this frame
        for (var i = 0; i < StreamStepsPerFrame && _streamQueue.Count > 0; i++)
            _streamQueue.Dequeue()();

        if (_shotDir != null) StepScreenshots();

        if (_resDebug is { Visible: true })
            _resDebug.Text = "[F9] " + (_resourcePlacer?.LastSummary ?? "resources: —");

        if (_streamPlayer is null) return;
        var pcx = (int)Math.Floor(_streamPlayer.Position.X / 16.0);
        var pcy = (int)Math.Floor(_streamPlayer.Position.Z / 16.0);
        if (Math.Abs(pcx - _centerCX) >= StreamThreshold
            || Math.Abs(pcy - _centerCY) >= StreamThreshold)
            RecenterWorld(pcx, pcy);

        if (Math.Abs(pcx - _farCX) >= FarThreshold || Math.Abs(pcy - _farCY) >= FarThreshold)
            BuildFarTerrain(pcx, pcy);
    }

    /// <summary>F9 toggles a live resource-spawn diagnostics overlay (rendered counts
    /// per family + why slots were rejected), so a flyover confirms resources still
    /// spawn and the density/slope caps aren't starving anything.</summary>
    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey { Pressed: true, Echo: false, PhysicalKeycode: Key.F9 })
            return;
        if (_resDebug is null)
        {
            var layer = new CanvasLayer { Layer = 5 };
            AddChild(layer);
            _resDebug = new Label { Position = new Vector2(16, 150) };
            _resDebug.AddThemeFontSizeOverride("font_size", 16);
            _resDebug.AddThemeColorOverride("font_color", new Color(0.6f, 1f, 0.7f));
            _resDebug.AddThemeColorOverride("font_outline_color", new Color(0, 0, 0));
            _resDebug.AddThemeConstantOverride("outline_size", 4);
            layer.AddChild(_resDebug);
        }
        _resDebug.Visible = !_resDebug.Visible;
        GetViewport().SetInputAsHandled();
    }

    // =====================================================================
    //  VILLAGES + NPCS — now window-relative (the frontier gets settlements)
    // =====================================================================

    /// <summary>Carve a flat shelf under every in-window settlement BEFORE the
    /// terrain is built, so a mountain village sits on a level part of the slope
    /// (like a real terrace) instead of sprawling down one whole face. Each shelf's
    /// LEVEL is the natural mountainside height at the village centre; its RADIUS is
    /// the wall footprint; the edge blends back into the slope. Roads then grade to
    /// the shelf and buildings seat flat on it.</summary>
    /// <summary>Halve settlement density (deterministic hash) and drop any village
    /// perched on a genuinely steep face — so roads no longer have to claw up a cliff
    /// to reach a doomed hillside hamlet, and the world reads less crowded. Runs once
    /// after the height field exists; the road network is built from the survivors.</summary>
    private List<VillageRecord> ThinVillages(List<VillageRecord> all)
    {
        var kept = new List<VillageRecord>();
        foreach (var v in all)
        {
            var walls = VillageGenerator.GetVillageWallTiles(v).ToList();
            double cx, cz;
            if (walls.Count > 0)
            {
                double sx = 0, sz = 0;
                foreach (var (tx, ty) in walls) { sx += tx + 0.5; sz += ty + 0.5; }
                cx = sx / walls.Count; cz = sz / walls.Count;
            }
            else { cx = v.CenterChunk.X * ChunkSize + ChunkSize / 2.0; cz = v.CenterChunk.Y * ChunkSize + ChunkSize / 2.0; }

            // half the settlements, chosen deterministically so the same seed = same world
            if (GeoNoise.Hash2D((int)cx, (int)cz, WorldSeed + 9001) >= 0.5) continue;

            // no DROWNED villages: the terrace flattens the site to its natural centre
            // height, so a sub-water centre sinks the whole settlement (walls + roofs
            // under the lake). ~25% of sites were landing underwater — reject them.
            if (TerrainHeightField.NaturalHeight(cx, cz) < TerrainHeightField.WaterLevel + 1.2) continue;

            // FLATNESS gate — the site must be a genuinely flat basin. Sample the natural
            // ground across the footprint (+ a verge the pad blends into); require the large
            // majority to be gentle and reject any cliff in town. This is what stops a village
            // reading as "terraced across a mountainside".
            double SlopeDeg(double x, double y)
            {
                var a = TerrainHeightField.NaturalHeight(x - 4, y); var b = TerrainHeightField.NaturalHeight(x + 4, y);
                var c = TerrainHeightField.NaturalHeight(x, y - 4); var d = TerrainHeightField.NaturalHeight(x, y + 4);
                return Mathf.RadToDeg(Mathf.Atan((float)Math.Max(Math.Abs(b - a), Math.Abs(d - c)) / 8f));
            }
            if (walls.Count > 0)
            {
                var maxR = 6.0;
                foreach (var (tx, ty) in walls)
                {
                    var dx = tx + 0.5 - cx; var dz = ty + 0.5 - cz;
                    maxR = Math.Max(maxR, Math.Sqrt(dx * dx + dz * dz));
                }
                const int steps = 4;
                // mesa guard: bound the footprint relief so the flattening pad stays a modest shelf.
                double fLo = double.MaxValue, fHi = double.MinValue;
                for (var i = 0; i <= steps; i++)
                    for (var j = 0; j <= steps; j++)
                    {
                        var h = TerrainHeightField.NaturalHeight(cx + (i / (double)steps * 2 - 1) * maxR,
                                                                 cz + (j / (double)steps * 2 - 1) * maxR);
                        if (h < fLo) fLo = h; if (h > fHi) fHi = h;
                    }
                if (fHi - fLo > VillageMaxRelief) continue;
                // steep-flank guard: sample slope over the footprint + verge.
                var reach = maxR + 6.0;
                int steepN = 0, totN = 0; double vMax = 0;
                for (var i = 0; i <= steps; i++)
                    for (var j = 0; j <= steps; j++)
                    {
                        var g = SlopeDeg(cx + (i / (double)steps * 2 - 1) * reach,
                                         cz + (j / (double)steps * 2 - 1) * reach);
                        if (g > vMax) vMax = g;
                        if (g > VillageSteepSlope) steepN++;
                        totN++;
                    }
                if (vMax > VillageHardSlope) continue;                  // a cliff/flank in town → no
                if (steepN > totN * VillageMaxSteepFrac) continue;     // not perched on a steep flank
            }

            // reject WATER-LOCKED sites (island / spit): a settlement ringed by water could
            // only connect via a straight causeway across the sea. Coastal (water on a side or
            // two) is fine; mostly-surrounded is not. Sample a ring just outside the centre.
            var ringWater = 0;
            const int ringN = 8;
            for (var k = 0; k < ringN; k++)
            {
                var ang = k / (double)ringN * Math.Tau;
                if (TerrainHeightField.NaturalHeight(cx + Math.Cos(ang) * 26, cz + Math.Sin(ang) * 26)
                    < TerrainHeightField.WaterLevel + 0.5) ringWater++;
            }
            if (ringWater >= 5) continue;

            // reject MOUNTAIN-LOCKED sites: a flat pocket ringed by steep ground that a road could
            // only reach by climbing over a wall. A valley town (steep on some sides, a gentle valley
            // mouth on others) still passes; a fully-enclosed basin does not — and culling it here is
            // what keeps roads from having to gouge a stretched track up a mountain to serve it.
            // Check a near AND a wider ring: a site can sit on a small flat shelf (gentle at 45u)
            // yet be walled off by mountains just beyond it, so every road out still climbs. The
            // wider ring catches that; a real valley town (a gentle mouth on some side at BOTH
            // radii) still passes.
            int ringNear = 0, ringFar = 0;
            const int mtnN = 12;
            for (var k = 0; k < mtnN; k++)
            {
                var ang = k / (double)mtnN * Math.Tau;
                if (SlopeDeg(cx + Math.Cos(ang) * 45, cz + Math.Sin(ang) * 45) > 22) ringNear++;
                if (SlopeDeg(cx + Math.Cos(ang) * 90, cz + Math.Sin(ang) * 90) > 22) ringFar++;
            }
            if (ringNear > mtnN * 0.55 || ringFar > mtnN * 0.70) continue;

            kept.Add(v);
        }
        GD.Print($"Villages thinned: {all.Count} → {kept.Count}");
        return kept;
    }

    private void BuildVillagePads(WorldContext ctx)
    {
        var pads = new List<(double Cx, double Cz, double Radius, double Level, double Blend)>();
        if (_villages.Count > 0)
            foreach (var v in _villages)
            {
                if (!v.Chunks.Any(c => ctx.ChunkInWindow(c.X, c.Y))) continue;
                var walls = VillageGenerator.GetVillageWallTiles(v).ToList();
                if (walls.Count == 0) continue;
                double sx = 0, sz = 0;
                foreach (var (tx, ty) in walls) { sx += tx + 0.5; sz += ty + 0.5; }
                var cxw = sx / walls.Count;
                var czw = sz / walls.Count;
                var maxR = 4.0;
                foreach (var (tx, ty) in walls)
                {
                    var dx = tx + 0.5 - cxw; var dz = ty + 0.5 - czw;
                    maxR = Math.Max(maxR, Math.Sqrt(dx * dx + dz * dz));
                }
                var level = TerrainHeightField.NaturalHeight(cxw, czw);
                // Cover the FULL footprint (+ a small verge) so EVERY building — centre and
                // perimeter alike — seats on the shelf, with no cap that would leave edge
                // houses terracing down natural slope. Safe because the relief gate bounds the
                // footprint's total rise (≤ MaxVillageRelief), so this cut/fill is a modest
                // shelf, not a mesa.
                pads.Add((cxw, czw, maxR + 2.0, level, 10.0));
            }
        TerrainHeightField.SetVillagePads(pads);
    }

    /// <summary>Village walls + buildings from the certified layouts, for every
    /// settlement whose footprint intersects THIS window (not just origin). Walls
    /// get a clean gap where a road crosses; the footprint is reserved in the ctx
    /// so no resource spawns inside a building.</summary>
    private void BuildVillages(WorldContext ctx)
    {
        var parent = new Node3D { Name = "Villages" };
        AddChild(parent);
        if (_villages.Count == 0) return;

        var wallMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.58f, 0.56f, 0.52f), Roughness = 0.9f };   // stone
        var buildingMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.66f, 0.56f, 0.44f), Roughness = 0.85f };  // warm plaster
        var roofMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.5f, 0.28f, 0.22f), Roughness = 0.8f };    // clay-tile roof
        var rendered = 0;

        foreach (var v in _villages)
        {
            if (!v.Chunks.Any(c => ctx.ChunkInWindow(c.X, c.Y))) continue;
            rendered++;

            foreach (var (tx, ty) in VillageGenerator.GetVillageWallTiles(v))
            {
                // a road crossing the wall cuts a clean GAP: skip only the wall
                // tiles inside the road corridor, not the whole wall.
                if (!ctx.RoadClear(tx + 0.5, ty + 0.5, 0.7f)) continue;
                var h = ctx.Height(tx + 0.5, ty + 0.5);
                AddSolidBox(parent, wallMat, new Vector3(1f, 2.5f, 1f),
                            new Vector3(tx + 0.5f, h + 1.25f, ty + 0.5f));
                ctx.Reserve(tx + 0.5, ty + 0.5, 0.1f);
            }

            // One HOUSE per building (not per tile), spread ×1.5 and raised to
            // ~3.2 tall with a pitched roof. Same building COUNT.
            foreach (var building in VillageGenerator.GetVillageBuildingTiles(v, WorldSeed))
            {
                var tiles = building.ToList();
                if (tiles.Count == 0) continue;
                foreach (var (btx, bty) in tiles)
                    ctx.Reserve(btx + 0.5, bty + 0.5, 0.1f);
                var minX = tiles.Min(t => t.Item1);
                var maxX = tiles.Max(t => t.Item1);
                var minY = tiles.Min(t => t.Item2);
                var maxY = tiles.Max(t => t.Item2);
                var cxw = (minX + maxX) / 2.0 + 0.5;
                var czw = (minY + maxY) / 2.0 + 0.5;
                var sizeX = (maxX - minX + 1) * 1.5f;
                var sizeZ = (maxY - minY + 1) * 1.5f;
                const float wallH = 3.2f;
                var h = ctx.Height(cxw, czw);
                AddSolidBox(parent, buildingMat, new Vector3(sizeX, wallH, sizeZ),
                            new Vector3((float)cxw, h + wallH * 0.5f, (float)czw));
                parent.AddChild(new MeshInstance3D
                {
                    Mesh = new CylinderMesh
                    {
                        TopRadius = 0f,
                        BottomRadius = Mathf.Max(sizeX, sizeZ) * 0.72f,
                        Height = 1.5f, RadialSegments = 4,
                    },
                    MaterialOverride = roofMat,
                    Position = new Vector3((float)cxw, h + wallH + 0.75f, (float)czw),
                    RotationDegrees = new Vector3(0, 45, 0),
                });
            }
        }
        if (rendered > 0) GD.Print($"Villages in view: {rendered}");
    }

    /// <summary>Clickable NPCs for THIS window: canonical quest-givers (npcs-3.JSON)
    /// whose home is in view, plus villagers at every in-window village's certified
    /// NPC positions. Rebuilt per window (combat.ClearNpcs drops the old handles).</summary>
    private void BuildNpcs(WorldContext ctx)
    {
        var parent = new Node3D { Name = "Npcs" };
        AddChild(parent);
        if (_villages.Count == 0 && _combat?.NpcDb is null) return;
        var npcMat = new StandardMaterial3D
        { AlbedoColor = new Color(0.9f, 0.75f, 0.55f) };
        var placed = 0;

        // Canonical NPCs (npcs-3.JSON) at their JSON positions, when in-window.
        if (_combat is { NpcDb: { } npcDb })
        {
            foreach (var def in npcDb.Npcs.Values)
            {
                var ncx = (int)Math.Floor(def.PosX / 16.0);
                var ncy = (int)Math.Floor(def.PosY / 16.0);
                if (!ctx.ChunkInWindow(ncx, ncy)) continue;

                var (nx, ny) = ((float)def.PosX, (float)def.PosY);
                var color = new Color(0.78f, 0.59f, 1f);
                if (def.SpriteColor is System.Text.Json.Nodes.JsonArray { Count: >= 3 } c)
                    color = new Color(
                        (float)(c[0]?.GetValue<double>() ?? 200) / 255f,
                        (float)(c[1]?.GetValue<double>() ?? 150) / 255f,
                        (float)(c[2]?.GetValue<double>() ?? 255) / 255f);
                var h = ctx.Height(nx + 0.5, ny + 0.5);
                var node = new Node3D { Position = new Vector3(nx + 0.5f, h, ny + 0.5f) };
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new CapsuleMesh { Radius = 0.32f, Height = 1.7f },
                    MaterialOverride = new StandardMaterial3D { AlbedoColor = color },
                    Position = new Vector3(0, 0.85f, 0),
                });
                node.AddChild(new Label3D
                {
                    Text = def.Title.Length > 0 ? $"{def.Name}\n{def.Title}" : def.Name,
                    FontSize = 38, OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Modulate = new Color(1f, 0.95f, 0.7f),
                    Position = new Vector3(0, 2.2f, 0),
                });
                parent.AddChild(node);
                _combat.RegisterNpc(new LiveNpc
                {
                    Node = node, Name = def.Name, Role = def.Title,
                    VillageName = "", NationName = "", Def = def,
                });
                placed++;
            }
        }

        foreach (var v in _villages)
        {
            if (!v.Chunks.Any(c => ctx.ChunkInWindow(c.X, c.Y))) continue;
            for (var i = 0; i < v.NpcPositions.Count; i++)
            {
                var (nx, ny) = v.NpcPositions[i];
                var tmpl = i < v.NpcTemplates.Count ? v.NpcTemplates[i] : null;
                var npcName = tmpl?["name"]?.GetValue<string>() ?? "Villager";
                var h = ctx.Height(nx + 0.5, ny + 0.5);
                var node = new Node3D { Position = new Vector3(nx + 0.5f, h, ny + 0.5f) };
                node.AddChild(new MeshInstance3D
                {
                    Mesh = new CapsuleMesh { Radius = 0.3f, Height = 1.6f },
                    MaterialOverride = npcMat,
                    Position = new Vector3(0, 0.8f, 0),
                });
                node.AddChild(new Label3D
                {
                    Text = npcName, FontSize = 36, OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Position = new Vector3(0, 2.0f, 0),
                });
                parent.AddChild(node);
                _combat?.RegisterNpc(new LiveNpc
                {
                    Node = node, Name = npcName, Role = npcName,
                    VillageName = v.Name,
                    NationName = string.IsNullOrEmpty(v.Nation) ? "frontier" : v.Nation,
                });
                placed++;
            }
        }
        if (placed > 0) GD.Print($"NPCs placed: {placed}");
    }

    // =====================================================================
    //  ORIGIN FIXTURES — stations + UI, built once (never streamed)
    // =====================================================================

    /// <summary>The 20 free starter stations near origin (world_system.py:671-692):
    /// columns x = -8 smithing, -4 refining, 0 adornments, 4 alchemy,
    /// 8 engineering; tiers 1-4 at y = -10/-12/-14/-16.</summary>
    private void BuildStations(CombatWorld combat)
    {
        var parent = new Node3D { Name = "Stations" };
        AddChild(parent);
        var colors = new Dictionary<string, Color>
        {
            ["smithing"] = new(180 / 255f, 60 / 255f, 60 / 255f),
            ["alchemy"] = new(60 / 255f, 180 / 255f, 60 / 255f),
            ["refining"] = new(180 / 255f, 120 / 255f, 60 / 255f),
            ["engineering"] = new(60 / 255f, 120 / 255f, 180 / 255f),
            ["adornments"] = new(180 / 255f, 60 / 255f, 180 / 255f),
        };
        var iconName = new Dictionary<string, string>
        {
            ["smithing"] = "forge", ["refining"] = "refinery",
            ["adornments"] = "enchanting_table", ["alchemy"] = "alchemy_table",
            ["engineering"] = "engineering_bench",
        };
        var columns = new (string Type, int X)[]
        {
            ("smithing", -8), ("refining", -4), ("adornments", 0),
            ("alchemy", 4), ("engineering", 8),
        };
        foreach (var (type, x) in columns)
        {
            for (var tier = 1; tier <= 4; tier++)
            {
                var y = -10 - (tier - 1) * 2;
                // seat on the MESH surface (not the continuous field) so the base
                // rests ON the ground, + a hair up to clear it.
                var h = TerrainHeightField.HMesh(x + 0.5, y + 0.5) + 0.02f;
                var node = new Node3D { Position = new Vector3(x + 0.5f, h, y + 0.5f) };
                var size = 1.1f + 0.12f * tier;
                var stex = IconCache.Get($"stations/{iconName[type]}_t{tier}.png");
                BillboardCube.Build(node, size, colors[type], stex);
                var body = new StaticBody3D { Position = new Vector3(0, size * 0.5f, 0) };
                body.AddChild(new CollisionShape3D
                { Shape = new BoxShape3D { Size = new Vector3(size, size, size) } });
                node.AddChild(body);
                node.AddChild(new Label3D
                {
                    Text = $"{CombatWorld.Prettify(type)} T{tier}",
                    FontSize = 34, OutlineSize = 10,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
                    Position = new Vector3(0, 1.7f + 0.2f * tier, 0),
                });
                parent.AddChild(node);
                combat.RegisterStation(type, tier, node);
            }
        }
    }

    /// <summary>The tabbed menu book + standalone popups + the six minigame
    /// overlays. Built once (UI doesn't stream).</summary>
    private void BuildUi(CombatWorld combat, PlayerController player)
    {
        var book = new MenuBook { Name = "MenuBook" };
        book.AddPage(new InventoryPage(combat));
        book.AddPage(new StatsPage(combat));
        book.AddPage(new SkillsPage(combat));
        book.AddPage(new QuestsPage(combat));
        book.AddPage(new EncyclopediaPage(combat));
        book.AddPage(new MapPage(_worldMap, _villages, player, _roadNet));
        AddChild(book);

        var crafting = new CraftingScreen(combat) { Name = "CraftingScreen" };
        AddChild(crafting);
        combat.CraftingUi = crafting;
        var dialogue = new DialogueScreen(combat) { Name = "DialogueScreen" };
        AddChild(dialogue);
        combat.Dialogue = dialogue;
        var controls = new ControlsScreen { Name = "ControlsScreen" };
        AddChild(controls);
        AddChild(new PauseScreen(combat, player)
        { Name = "PauseScreen", Controls = controls });

        var minigames = new (string Type, MinigameOverlay Overlay)[]
        {
            ("smithing", new SmithingMinigame()),
            ("alchemy", new AlchemyMinigame()),
            ("refining", new RefiningMinigame()),
            ("engineering", new EngineeringMinigame()),
            ("adornments", new EnchantingMinigame()),
            ("fishing", new FishingMinigame()),
        };
        foreach (var (type, overlay) in minigames)
        {
            overlay.Name = $"Minigame_{type}";
            AddChild(overlay);
            combat.Minigames[type] = overlay;
        }

        AddChild(new ClassSelectScreen(combat) { Name = "ClassSelect" });
    }

    // =====================================================================
    //  GROUND COVER — decoration ONLY (harvestables come from ResourcePlacer)
    // =====================================================================

    /// <summary>Deterministic per-chunk ground cover: grass, flowers, ferns,
    /// mushrooms, logs — batched by EnvironmentArt into a handful of MultiMeshes.
    /// GROUND COVER ONLY: every tree/rock is a real harvestable node from the ONE
    /// resource system, so scatter never places decorative stand-ins that would
    /// masquerade as harvestable. Reads all masks from the shared ctx.</summary>
    private void QueueScatter(WorldContext ctx)
    {
        var art = new EnvironmentArt();
        var parent = new Node3D { Name = "Scatter" };
        AddChild(parent);
        var radius = Math.Min(ChunkRadius, 7);
        // enqueue one placement step per chunk ROW, then a single commit at the end
        // (accumulate into ONE EnvironmentArt so scatter stays batched to a handful
        // of MultiMeshes — per-chunk commits would explode the draw calls).
        for (var cy = ctx.CenterCY - radius; cy <= ctx.CenterCY + radius; cy++)
        {
            var ccy = cy;
            _streamQueue.Enqueue(() =>
            {
                for (var cx = ctx.CenterCX - radius; cx <= ctx.CenterCX + radius; cx++)
                    ScatterChunk(art, ctx, cx, ccy);
            });
        }
        _streamQueue.Enqueue(() =>
        {
            if (GodotObject.IsInstanceValid(parent)) art.Commit(parent);
        });
    }

    private void ScatterChunk(EnvironmentArt art, WorldContext ctx, int cx, int cy)
    {
        float HashF(int a, int b, long salt) => (float)GeoNoise.Hash2D(a, b, WorldSeed + salt);
        (double X, double Z) HashPos(int k, int salt)
        {
            var hx = GeoNoise.Hash2D(cx * 131 + k, cy * 131 + salt, WorldSeed + 71);
            var hy = GeoNoise.Hash2D(cx * 131 + k + 1, cy * 131 + salt + 3, WorldSeed + 72);
            return (cx * ChunkSize + hx * ChunkSize, cy * ChunkSize + hy * ChunkSize);
        }

        var type = ctx.ChunkType(cx, cy);
        if (type.Contains("lake") || type.Contains("river") || type.Contains("flooded"))
            return;   // open water — no scatter
        var rocky = type.Contains("rock") || type.Contains("quarry")
                    || type.Contains("barren") || type.Contains("cave");
        var woody = type.Contains("forest") || type.Contains("thicket")
                    || type.Contains("overgrown");
        var marsh = type.Contains("wetland") || type.Contains("marsh");

        // ground cover: grass tufts + occasional wildflowers. Kept SPARSE — dense tall
        // grass was reading as a spiky carpet (especially lit by dusk fog) that buried
        // the ground read; a lighter scatter lets the terrain + real features breathe.
        var grassN = rocky ? 2 : woody ? 9 : marsh ? 5 : 7;
        for (var k = 0; k < grassN; k++)
        {
            var (wx, wz) = HashPos(k, 200);
            if (ctx.IsWater(wx, wz) || ctx.Slope(wx, wz) > 0.5f) continue;
            var h = ctx.MeshHeight(wx, wz);
            if (h > 180f) continue;   // tree line — no grass up on bare rock/scree
            var g = new Vector3((float)wx, h, (float)wz);
            var yaw = HashF(k, cx + cy, 301) * Mathf.Tau;
            var sc = 0.6f + HashF(k, cx - cy, 302) * 0.7f;
            var pick = HashF(k, cx * 3 + cy, 303);
            if (!rocky && pick < 0.14f)
                art.PlaceFlower(g, sc, yaw, HashF(k, cy, 304) < 0.5f);
            else if (!rocky && pick < 0.24f)
                art.PlaceTallGrass(g, sc, yaw);
            else
                art.PlaceGrass(g, sc, yaw);
        }

        // forest-floor & meadow detail — GROUND COVER ONLY.
        for (var k = 0; k < 14; k++)
        {
            var (wx, wz) = HashPos(k, 400);
            if (ctx.IsWater(wx, wz)) continue;
            if (WorldContext.NearStation(wx, wz, 3.0f)) continue;
            if (!ctx.RoadClear(wx, wz)) continue;
            var clump = GeoNoise.FractalNoise2D(wx * 0.09, wz * 0.09, WorldSeed + 7777, 2);
            if (clump < (woody ? -0.1 : 0.2)) continue;
            if (ctx.Slope(wx, wz) > 0.55f) continue;
            // props keep clear of village buildings/walls + resource footprints
            // (both live in the shared occupancy store) — no bush through a table.
            if (ctx.IsReserved(wx, wz, 1.2f)) continue;
            var g = new Vector3((float)wx, ctx.MeshHeight(wx, wz), (float)wz);
            if (g.Y > 200f) continue;   // tree line for the megascale world
            var yaw = HashF(k, cx + cy, 401) * Mathf.Tau;
            var sc = 0.7f + HashF(k, cx - cy, 402) * 0.8f;
            var r = HashF(k, cx * 5 + cy, 403);

            if (woody)
            {
                if (r < 0.34f) art.PlaceBush(g, 0.6f * sc, yaw);
                else if (r < 0.54f) art.PlaceFern(g, sc, yaw);
                else if (r < 0.70f) art.PlaceMushroom(g, sc, yaw);
                else if (r < 0.82f) art.PlaceLog(g, sc, yaw);
                else art.PlaceTallGrass(g, sc, yaw);
            }
            else if (marsh)
            {
                if (r < 0.5f) art.PlaceBush(g, 0.6f * sc, yaw);
                else art.PlaceTallGrass(g, sc, yaw);
            }
            else if (!rocky)
            {
                if (r < 0.4f) art.PlaceBush(g, 0.6f * sc, yaw);
                else if (r < 0.68f) art.PlaceTallGrass(g, sc, yaw);
                else art.PlaceFlower(g, sc, yaw, HashF(k, cy, 405) < 0.5f);
            }
            // rocky / barren: bare ground — the resource system supplies stone.
        }
    }

    // =====================================================================
    //  CAVES
    // =====================================================================
    private void BuildCaves(WorldContext ctx) =>
        CaveSystem.Build(this, _worldMap, WorldSeed, ctx.CenterCX, ctx.CenterCY, ChunkRadius);

    // =====================================================================
    //  ROADS — grade the ground to them, then drape the ribbons
    // =====================================================================

    /// <summary>Grade the terrain toward every road in the window BEFORE the mesh is
    /// built: route each edge, take a smoothed height profile along it, and hand the
    /// segments (+ a flat half-width) to TerrainHeightField so the ground rises/falls
    /// to meet the road and ramps back over an embankment (no patchy poke-through).</summary>
    private void BuildRoadGrid(WorldContext ctx)
    {
        TerrainHeightField.ClearRoads();
        if (_roadNet is null || _roadNet.Edges.Count == 0) return;

        var pad = ChunkSize * 4;
        float minX = (ctx.CenterCX - ChunkRadius) * ChunkSize - pad;
        float maxX = (ctx.CenterCX + ChunkRadius + 1) * ChunkSize + pad;
        float minZ = (ctx.CenterCY - ChunkRadius) * ChunkSize - pad;
        float maxZ = (ctx.CenterCY + ChunkRadius + 1) * ChunkSize + pad;

        var segs = new List<(Vector2 A, Vector2 B, float Ha, float Hb, float Half)>();
        foreach (var e in _roadNet.Edges)
        {
            if (!SegBoxNear(e.A, e.B, minX, minZ, maxX, maxZ)) continue;
            if (!e.Routed) { e.Path = RoadRouter.Route(e.A, e.B, e.Tier); e.Routed = true; }
            if (e.Path is null) continue;
            var pts = Resample(e.Path, 1.5f);   // finer → the carve hugs the curve
            if (pts.Count < 2) continue;

            // smoothed + slope-limited deck: gentle grades BY CONSTRUCTION (steep terrain
            // becomes a level CUT/pass, not a vertical road). The corridor carves the
            // ground to exactly this profile so the road IS the ground.
            var (deck, cut) = RoadDeckProfile(pts, e.Tier);
            // flat CROWN wide enough the ribbon sits entirely on it even on a diagonal
            // heading: ribbon_half*sqrt2 + ~2 grade cells of margin (the anti-clip fix).
            var crown = RoadWidth[e.Tier] * 0.5f * 1.414f + 2.5f;
            for (var i = 0; i < pts.Count - 1; i++)
            {
                if (!SegBoxNear(pts[i], pts[i + 1], minX, minZ, maxX, maxZ)) continue;
                // no ground carve under a bridge (the water body stays; the ribbon arches)
                if (deck[i] <= (float)TerrainHeightField.WaterLevel + 0.6f
                    && deck[i + 1] <= (float)TerrainHeightField.WaterLevel + 0.6f) continue;
                // a real level-cut pass gets a broader notch floor
                var segHalf = (cut[i] || cut[i + 1]) ? crown + 3f : crown;
                segs.Add((pts[i], pts[i + 1], deck[i], deck[i + 1], segHalf));
            }
        }
        // 1.0u corridor grid (matches the mesh lattice) + a 5u base shoulder that ramps
        // back to natural; SetRoads widens banks with cut/fill depth (no vertical walls).
        TerrainHeightField.SetRoads(segs, minX, minZ, maxX, maxZ, 1.0f, 5.0f);
    }

    // Road decks are gentle by construction: the profile is smoothed then slope-limited
    // to this grade (rise/run along travel). Where natural terrain out-slopes it, the
    // deck sits below the ridge — a level CUT/pass the corridor carves through.
    private const float MaxDeckGrade = 0.18f;   // ~10° max road grade
    private const float CutThreshold = 6f;      // deck this far under the ridge = a pass

    /// <summary>Per resampled point: the smoothed, grade-limited road DECK height, and
    /// whether the point is a CUT (deck well below the natural ridge → a level pass).
    /// Samples PadHeight (natural + village terracing, NO road grade) so the profile is
    /// stable before and after the carve it drives. The slope-limiter is what guarantees
    /// gentle roads independent of the router.</summary>
    private static (float[] Deck, bool[] Cut) RoadDeckProfile(List<Vector2> pts, int tier)
    {
        var n = pts.Count;
        var wl = (float)TerrainHeightField.WaterLevel;
        var terr = new float[n];
        var bridge = new bool[n];
        for (var i = 0; i < n; i++)
        {
            terr[i] = (float)TerrainHeightField.PadHeight(pts[i].X, pts[i].Y);
            bridge[i] = terr[i] < wl + 0.6f;
        }
        // 1) longitudinal smooth — a road doesn't chase every bump
        var deck = new float[n];
        for (var i = 0; i < n; i++)
        {
            float s = 0; var c = 0;
            for (var k = -5; k <= 5; k++) { var j = i + k; if (j < 0 || j >= n) continue; s += terr[j]; c++; }
            deck[i] = s / c;
        }
        // bridge points anchor just above the water datum so approaches ramp to the mouth
        for (var i = 0; i < n; i++) if (bridge[i]) deck[i] = wl + 0.4f;
        // 2) slope-limit LAST (forward then backward) → the built grade is gentle
        const float step = 1.5f, // resample spacing
                    maxRise = MaxDeckGrade * step;
        for (var i = 1; i < n; i++)
            deck[i] = Mathf.Clamp(deck[i], deck[i - 1] - maxRise, deck[i - 1] + maxRise);
        for (var i = n - 2; i >= 0; i--)
            deck[i] = Mathf.Clamp(deck[i], deck[i + 1] - maxRise, deck[i + 1] + maxRise);
        // 3) mark deep cuts (a level pass carved through a ridge) — for the tour landmark
        var cut = new bool[n];
        for (var i = 0; i < n; i++) cut[i] = terr[i] - deck[i] > CutThreshold;
        return (deck, cut);
    }

    /// <summary>Draped road ribbons for every RoadNetwork edge crossing the window —
    /// context-aware (bridges over water, kerbs on steeps), clipped to the window.</summary>
    private void QueueRoads(WorldContext ctx)
    {
        var parent = new Node3D { Name = "Roads" };
        AddChild(parent);
        if (_roadNet is null || _roadNet.Edges.Count == 0) return;

        var pad = ChunkSize * 4;
        float minX = (ctx.CenterCX - ChunkRadius) * ChunkSize - pad;
        float maxX = (ctx.CenterCX + ChunkRadius + 1) * ChunkSize + pad;
        float minZ = (ctx.CenterCY - ChunkRadius) * ChunkSize - pad;
        float maxZ = (ctx.CenterCY + ChunkRadius + 1) * ChunkSize + pad;

        var width = new[] { 1.0f, 1.9f, 3.2f, 5.0f };
        var col = new[]
        {
            new Color(0.38f, 0.30f, 0.20f),  // footpath — worn dirt
            new Color(0.42f, 0.34f, 0.24f),  // lane — packed earth
            new Color(0.46f, 0.40f, 0.31f),  // road — earth & gravel
            new Color(0.50f, 0.44f, 0.35f),  // highway — old cobbled earth
        };
        var rough = new[] { 0.99f, 0.96f, 0.92f, 0.88f };
        var mats = new StandardMaterial3D[4];
        for (var i = 0; i < 4; i++)
            mats[i] = new StandardMaterial3D
            {
                AlbedoColor = col[i], Roughness = rough[i], Metallic = 0f,
                CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            };

        // stream one ribbon per edge (the grade is already applied synchronously in
        // BuildRoadGrid, so terrain conforms even before the ribbon draws in).
        foreach (var e in _roadNet.Edges)
        {
            if (!SegBoxNear(e.A, e.B, minX, minZ, maxX, maxZ)) continue;
            var edge = e;
            _streamQueue.Enqueue(() =>
            {
                if (!GodotObject.IsInstanceValid(parent)) return;
                if (!edge.Routed) { edge.Path = RoadRouter.Route(edge.A, edge.B, edge.Tier); edge.Routed = true; }
                if (edge.Path is null) return;
                BuildRoadPolyline(parent, edge.Path, mats[edge.Tier], width[edge.Tier], edge.Tier);
            });
        }
    }

    // shared bridge structure materials, built once
    private static StandardMaterial3D? _railMat, _pierMat;

    /// <summary>A road along a routed polyline: arched BRIDGE deck + timber railings
    /// + stone piers over water, pale KERBS on steeps, flat drape elsewhere. Land
    /// roads paint the (graded) terrain which carries the walk; only bridges add a
    /// collidable deck.</summary>
    private static void BuildRoadPolyline(Node3D parent, Vector2[] path,
                                          Material mat, float width, int tier)
    {
        if (path.Length < 2) return;
        var pts = Resample(path, 1.5f);   // finer → the ribbon hugs the carved ground
        var n = pts.Count;
        if (n < 2) return;

        // clip the ribbon to the carved corridor (+ water spans) so no tail drapes over
        // ungraded ground beyond this window's carve (the streamed-ribbon overrun fix).
        int first = -1, last = -1;
        for (var i = 0; i < n; i++)
        {
            var keep = TerrainHeightField.RoadWeight(pts[i].X, pts[i].Y) > 0.05f
                    || TerrainHeightField.HMesh(pts[i].X, pts[i].Y) < TerrainHeightField.WaterLevel + 0.3f;
            if (keep) { if (first < 0) first = i; last = i; }
        }
        if (first < 0 || last - first < 1) return;
        if (first > 0 || last < n - 1) { pts = pts.GetRange(first, last - first + 1); n = pts.Count; }

        _railMat ??= new StandardMaterial3D
        { AlbedoColor = new Color(0.30f, 0.22f, 0.15f), Roughness = 0.8f,
          CullMode = BaseMaterial3D.CullModeEnum.Disabled };
        _pierMat ??= new StandardMaterial3D
        { AlbedoColor = new Color(0.34f, 0.32f, 0.33f), Roughness = 0.9f };

        var perp = new Vector2[n];
        var terr = new float[n];
        var deckY = new float[n];
        var water = new bool[n];
        for (var i = 0; i < n; i++)
        {
            var dir = i == 0 ? pts[1] - pts[0]
                : i == n - 1 ? pts[i] - pts[i - 1]
                : pts[i + 1] - pts[i - 1];
            if (dir.LengthSquared() < 1e-6f) dir = Vector2.Right;
            dir = dir.Normalized();
            perp[i] = new Vector2(-dir.Y, dir.X);

            // the crown is flat + level under the road, so HMesh (the mesh/collider's own
            // interpolant) here IS the deck height → the ribbon is coplanar, never drapes.
            terr[i] = TerrainHeightField.HMesh(pts[i].X, pts[i].Y);
            water[i] = terr[i] < TerrainHeightField.WaterLevel + 0.2f;
        }

        // Small per-tier lift stops two roads that CROSS from z-fighting / stepping
        // where their decks are otherwise coplanar — the grander artery sits a hair
        // proud of the feeder it meets.
        var lift = tier * 0.02f;
        for (var i = 0; i < n; i++)
            deckY[i] = (water[i] ? TerrainHeightField.WaterLevel + 0.5f : terr[i] + 0.03f) + lift;

        // arch each contiguous water span (a bridge that bows up over the middle)
        for (var i = 0; i < n;)
        {
            if (!water[i]) { i++; continue; }
            var j = i;
            while (j + 1 < n && water[j + 1]) j++;
            var span = j - i;
            for (var k = i; k <= j; k++)
            {
                var t = span > 0 ? (float)(k - i) / span : 0f;
                deckY[k] += Mathf.Sin(t * Mathf.Pi) * Mathf.Min(1.3f, span * 0.28f);
            }
            i = j + 1;
        }

        // A deck point is ELEVATED wherever it stands proud of the ground it spans (a
        // water gap or an arch). This single test now drives BOTH the collision deck and
        // the guard kerbs, so an isolated water cell or a bridge abutment can no longer
        // be a collision hole you fall through.
        var elevated = new bool[n];
        for (var i = 0; i < n; i++)
            elevated[i] = deckY[i] - terr[i] > 0.4f;

        var hw = width * 0.5f;

        // Guard kerbs — the "kerbs on steeps" the ribbon documented but never built
        // (rails were only ever added over water). A low wall runs down an edge wherever
        // the deck stands proud OR the ground drops away just past that edge (an
        // embankment / sidehill shelf), so you cannot step off a raised road into a drop.
        const float KerbProbe = 1.6f, KerbDrop = 1.3f, RailH = 0.55f;
        bool[] KerbMask(float sign)
        {
            var m = new bool[n];
            for (var i = 0; i < n; i++)
            {
                if (elevated[i]) { m[i] = true; continue; }
                var e = pts[i] + perp[i] * (sign * (hw + KerbProbe));
                m[i] = deckY[i] - TerrainHeightField.HMesh(e.X, e.Y) > KerbDrop;
            }
            return m;
        }

        BuildDeck(parent, pts, perp, deckY, mat, width);
        SideRail(parent, _railMat!, pts, perp, deckY, hw, RailH, KerbMask(+1f));
        SideRail(parent, _railMat!, pts, perp, deckY, -hw, RailH, KerbMask(-1f));
        BuildPiers(parent, pts, perp, deckY, hw, water);
        BuildBridgeCollision(parent, pts, perp, deckY, hw, elevated);
    }

    /// <summary>Collision over every ELEVATED deck span (bridges + arches) — on land the
    /// smooth graded terrain carries the walk. Covers a segment where EITHER end is
    /// elevated, so a lone water cell and the bridge abutments are decked too (the old
    /// "both ends water" test left those as fall-through holes).</summary>
    private static void BuildBridgeCollision(Node3D parent, List<Vector2> pts,
                                             Vector2[] perp, float[] deckY, float hw,
                                             bool[] elev)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        var any = false;
        for (var i = 0; i < pts.Count - 1; i++)
        {
            if (!elev[i] && !elev[i + 1]) continue;
            var l0 = new Vector3((pts[i] + perp[i] * hw).X, deckY[i], (pts[i] + perp[i] * hw).Y);
            var r0 = new Vector3((pts[i] - perp[i] * hw).X, deckY[i], (pts[i] - perp[i] * hw).Y);
            var l1 = new Vector3((pts[i + 1] + perp[i + 1] * hw).X, deckY[i + 1], (pts[i + 1] + perp[i + 1] * hw).Y);
            var r1 = new Vector3((pts[i + 1] - perp[i + 1] * hw).X, deckY[i + 1], (pts[i + 1] - perp[i + 1] * hw).Y);
            st.AddVertex(l0); st.AddVertex(r0); st.AddVertex(r1);
            st.AddVertex(l0); st.AddVertex(r1); st.AddVertex(l1);
            any = true;
        }
        if (!any) return;
        var body = new StaticBody3D();
        body.AddChild(new CollisionShape3D { Shape = st.Commit().CreateTrimeshShape() });
        parent.AddChild(body);
    }

    /// <summary>The road surface strip at the given per-point deck heights.</summary>
    private static void BuildDeck(Node3D parent, List<Vector2> pts, Vector2[] perp,
                                  float[] deckY, Material mat, float width)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        var hw = width * 0.5f;
        for (var i = 0; i < pts.Count; i++)
        {
            var l = pts[i] + perp[i] * hw;
            var r = pts[i] - perp[i] * hw;
            st.SetUV(new Vector2(0, i)); st.AddVertex(new Vector3(l.X, deckY[i], l.Y));
            st.SetUV(new Vector2(1, i)); st.AddVertex(new Vector3(r.X, deckY[i], r.Y));
        }
        for (var i = 0; i < pts.Count - 1; i++)
        {
            var b0 = i * 2;
            st.AddIndex(b0); st.AddIndex(b0 + 1); st.AddIndex(b0 + 3);
            st.AddIndex(b0); st.AddIndex(b0 + 3); st.AddIndex(b0 + 2);
        }
        st.GenerateNormals();
        parent.AddChild(new MeshInstance3D { Mesh = st.Commit(), MaterialOverride = mat });
    }

    /// <summary>A low vertical wall along one road edge (bridge railing or mountain
    /// kerb), only where <paramref name="on"/> holds. Two-sided.</summary>
    private static void SideRail(Node3D parent, Material mat, List<Vector2> pts,
                                 Vector2[] perp, float[] deckY, float side, float h,
                                 bool[] on)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        var any = false;
        for (var i = 0; i < pts.Count - 1; i++)
        {
            if (!on[i] || !on[i + 1]) continue;
            var e0 = pts[i] + perp[i] * side;
            var e1 = pts[i + 1] + perp[i + 1] * side;
            var b0 = new Vector3(e0.X, deckY[i], e0.Y);
            var b1 = new Vector3(e1.X, deckY[i + 1], e1.Y);
            var t0 = b0 + Vector3.Up * h;
            var t1 = b1 + Vector3.Up * h;
            st.AddVertex(b0); st.AddVertex(t0); st.AddVertex(t1);
            st.AddVertex(b0); st.AddVertex(t1); st.AddVertex(b1);
            any = true;
        }
        if (!any) return;
        st.GenerateNormals();
        parent.AddChild(new MeshInstance3D { Mesh = st.Commit(), MaterialOverride = mat });
    }

    /// <summary>Stone support piers dropping from a bridge deck to the bed.</summary>
    private static void BuildPiers(Node3D parent, List<Vector2> pts, Vector2[] perp,
                                   float[] deckY, float hw, bool[] water)
    {
        for (var i = 0; i < pts.Count; i++)
        {
            if (!water[i] || i % 3 != 0) continue;
            var bed = Math.Min(TerrainHeightField.HMesh(pts[i].X, pts[i].Y),
                               TerrainHeightField.WaterLevel) - 0.4f;
            var top = deckY[i];
            var hgt = top - bed;
            if (hgt <= 0.2f) continue;
            foreach (var s in new[] { hw * 0.85f, -hw * 0.85f })
            {
                var c = pts[i] + perp[i] * s;
                parent.AddChild(new MeshInstance3D
                {
                    Mesh = new BoxMesh { Size = new Vector3(0.5f, hgt, 0.5f) },
                    MaterialOverride = _pierMat,
                    Position = new Vector3(c.X, bed + hgt * 0.5f, c.Y),
                });
            }
        }
    }

    /// <summary>Resample a polyline to evenly-spaced points (for smooth draping).</summary>
    private static List<Vector2> Resample(Vector2[] path, float spacing)
    {
        var cum = new float[path.Length];
        for (var i = 1; i < path.Length; i++)
            cum[i] = cum[i - 1] + path[i].DistanceTo(path[i - 1]);
        var length = cum[^1];
        if (length < 1e-3f) return new List<Vector2> { path[0], path[^1] };

        var n = Math.Max(1, (int)(length / spacing));
        var outp = new List<Vector2>(n + 1);
        var seg = 0;
        for (var k = 0; k <= n; k++)
        {
            var d = length * k / n;
            while (seg < path.Length - 2 && cum[seg + 1] < d) seg++;
            var t = (d - cum[seg]) / Mathf.Max(1e-4f, cum[seg + 1] - cum[seg]);
            outp.Add(path[seg].Lerp(path[seg + 1], t));
        }
        return outp;
    }

    /// <summary>Does the a→b segment's bounding box overlap the window rect?</summary>
    private static bool SegBoxNear(Vector2 a, Vector2 b, float minX, float minZ,
                                   float maxX, float maxZ)
    {
        float loX = Mathf.Min(a.X, b.X), hiX = Mathf.Max(a.X, b.X);
        float loZ = Mathf.Min(a.Y, b.Y), hiZ = Mathf.Max(a.Y, b.Y);
        return hiX >= minX && loX <= maxX && hiZ >= minZ && loZ <= maxZ;
    }

    /// <summary>Add the longest BRIDGE (contiguous water span) and longest TUNNEL
    /// (bored ridge) on the near-origin road network to the F5/F6 tour. Bounded to
    /// the nearest edges so it stays a modest trek and the load-time routing is cheap
    /// (routes are cached, so they cost nothing when the player later reaches them).</summary>
    private void AddRoadLandmarks(CombatWorld combat)
    {
        if (_roadNet is null || _roadNet.Edges.Count == 0) return;
        float bestBridge = 0f; (int X, int Y)? bridgeAt = null;
        float bestTunnel = 0f; (int X, int Y)? tunnelAt = null;
        var reach = 80f * ChunkSize;   // edges within ~80 chunks of origin
        var reach2 = reach * reach;
        var scanned = 0;
        foreach (var e in _roadNet.Edges.OrderBy(e => ((e.A + e.B) * 0.5f).LengthSquared()))
        {
            if (scanned >= 30) break;   // bounded load-time routing (routes are cached)
            if (((e.A + e.B) * 0.5f).LengthSquared() > reach2) break;
            if (!e.Routed) { e.Path = RoadRouter.Route(e.A, e.B, e.Tier); e.Routed = true; }
            if (e.Path is null) continue;
            scanned++;
            var pts = Resample(e.Path, 1.5f);
            if (pts.Count < 2) continue;
            var (_, cut) = RoadDeckProfile(pts, e.Tier);
            MeasureLongestSpan(pts, cut, ref bestTunnel, ref tunnelAt);
            var water = new bool[pts.Count];
            for (var i = 0; i < pts.Count; i++)
                water[i] = TerrainHeightField.HMesh(pts[i].X, pts[i].Y)
                           < TerrainHeightField.WaterLevel + 0.2f;
            MeasureLongestSpan(pts, water, ref bestBridge, ref bridgeAt);
        }
        if (bridgeAt is { } b && bestBridge > 6f)
            combat.AddTourStop($"The Longest Bridge · {bestBridge:F0}u",
                (int)Math.Floor(b.X / 16.0), (int)Math.Floor(b.Y / 16.0));
        if (tunnelAt is { } t && bestTunnel > 6f)
            combat.AddTourStop($"The Longest Pass · {bestTunnel:F0}u",
                (int)Math.Floor(t.X / 16.0), (int)Math.Floor(t.Y / 16.0));
    }

    private static void MeasureLongestSpan(List<Vector2> pts, bool[] mask,
                                           ref float best, ref (int X, int Y)? at)
    {
        var i = 0;
        while (i < pts.Count)
        {
            if (!mask[i]) { i++; continue; }
            var j = i;
            while (j + 1 < pts.Count && mask[j + 1]) j++;
            var len = pts[i].DistanceTo(pts[j]);
            if (len > best)
            {
                best = len;
                var mid = (pts[i] + pts[j]) * 0.5f;
                at = ((int)mid.X, (int)mid.Y);
            }
            i = j + 1;
        }
    }

    // =====================================================================
    //  TERRAIN
    // =====================================================================
    private void BuildTerrain(WorldContext ctx)
    {
        var terrain = new Node3D { Name = "Terrain" };
        AddChild(terrain);

        var terrainMat = ShaderLib.TerrainSurface();

        // Thread-safe (the terrain vertex work below runs in parallel): concurrent
        // GetOrAdd, computed from immutable palettes only.
        var colorCache = new System.Collections.Concurrent.ConcurrentDictionary<string, Color>();
        Color BiomeColor(string type) => colorCache.GetOrAdd(type, t =>
        {
            if (GeoColors.TryGetValue(t, out var geoColor)) return geoColor;
            var (r, g, b) = _mapConfig!.GetBiomeColor(t);
            return new Color(r / 255f, g / 255f, b / 255f);
        });

        // Continuous biome color — bilinearly blended across chunk centers so there
        // are NO chunk seams (the "quilt").
        Color BlendedBiomeColor(double wx, double wz)
        {
            var fx = wx / 16.0 - 0.5;
            var fy = wz / 16.0 - 0.5;
            var cx0 = (int)Math.Floor(fx);
            var cy0 = (int)Math.Floor(fy);
            var tx = (float)(fx - cx0);
            var ty = (float)(fy - cy0);
            var c00 = BiomeColor(ctx.ChunkType(cx0, cy0));
            var c10 = BiomeColor(ctx.ChunkType(cx0 + 1, cy0));
            var c01 = BiomeColor(ctx.ChunkType(cx0, cy0 + 1));
            var c11 = BiomeColor(ctx.ChunkType(cx0 + 1, cy0 + 1));
            return c00.Lerp(c10, tx).Lerp(c01.Lerp(c11, tx), ty);
        }

        var grassCol = new Color(0.30f, 0.45f, 0.22f);
        var forestCol = new Color(0.19f, 0.34f, 0.17f);
        var stoneCol = new Color(0.42f, 0.40f, 0.38f);
        var screeCol = new Color(0.55f, 0.53f, 0.49f);
        var snowCol = new Color(0.93f, 0.95f, 0.98f);
        var sandCol = new Color(0.78f, 0.72f, 0.52f);
        var bedCol = new Color(0.24f, 0.31f, 0.27f);

        Color VertexColor(double wx, double wz, float h, float slope)
        {
            var c = grassCol.Lerp(BlendedBiomeColor(wx, wz), 0.20f);
            var tex = 1f
                + (float)GeoNoise.ValueNoise2D(wx * 0.10, wz * 0.10, WorldSeed + 4242) * 0.08f
                + (float)GeoNoise.ValueNoise2D(wx * 0.45, wz * 0.45, WorldSeed + 9191) * 0.05f;
            c = new Color(c.R * tex, c.G * tex, c.B * tex);

            // altitude bands rescaled for MEGASCALE peaks (~600-680u): deep-forest
            // flanks → stone with altitude → pale scree high up → snow only near the
            // true summits, so a single massif reads its full vertical zonation.
            // Altitude bands, rescaled to the gentler ~430u peaks so a mountain still
            // reads its full zonation (forest flank → stone → pale scree → snow cap)
            // instead of staying dark rock the whole way up.
            c = c.Lerp(forestCol, Mathf.Clamp((h - 20f) / 110f, 0f, 1f) * 0.38f);
            var sl = Mathf.Clamp((slope - 0.28f) / 0.30f, 0f, 1f);
            c = c.Lerp(stoneCol, sl * 0.9f);
            c = c.Lerp(stoneCol, Mathf.Clamp((h - 120f) / 110f, 0f, 1f) * 0.7f);
            c = c.Lerp(screeCol, Mathf.Clamp((h - 230f) / 110f, 0f, 1f) * 0.7f);
            c = c.Lerp(snowCol, Mathf.Clamp((h - 330f) / 80f, 0f, 1f));

            var ft = ctx.ChunkType((int)Math.Floor(wx / 16.0), (int)Math.Floor(wz / 16.0));
            if (ft.Contains("forest") || ft.Contains("thicket") || ft.Contains("overgrown"))
            {
                var dens = (float)GeoNoise.FractalNoise2D(wx * 0.010, wz * 0.010, WorldSeed + 909, 3) * 0.5f + 0.5f;
                c = c.Lerp(new Color(0.13f, 0.19f, 0.10f), Mathf.Clamp(dens, 0f, 1f) * 0.42f);
            }
            else if (ft.Contains("quarry"))
                c = c.Lerp(new Color(0.42f, 0.35f, 0.26f), 0.55f);

            if (h >= TerrainHeightField.WaterLevel
                && h < TerrainHeightField.WaterLevel + 0.8f && slope < 0.3f)
                c = c.Lerp(sandCol, 0.5f);
            if (h < TerrainHeightField.WaterLevel)
                c = c.Lerp(bedCol, 0.55f);
            return new Color(Mathf.Clamp(c.R, 0, 1), Mathf.Clamp(c.G, 0, 1),
                             Mathf.Clamp(c.B, 0, 1));
        }

        // ---- ONE merged, full-res CORE surface + ONE continuous collider ----------
        // The near window used to be (2R+1)² separate MeshInstance3D + HeightMapShape
        // bodies (~289 draw calls, ~289 colliders, per-chunk collider seams you could
        // fall through). It is now a SINGLE merged mesh over a SINGLE height grid, with
        // ONE heightmap collider spanning the whole walkable window — a few draw calls,
        // no seams. The heavy work (the ~30-octave field + per-vertex colour) is still a
        // pure function of the fixed field, so it stays parallel across cores; only the
        // SurfaceTool commit runs on the main thread.
        var n = ChunkSize;
        int R = ChunkRadius;
        int coreMinX = (ctx.CenterCX - R) * n;
        int coreMinZ = (ctx.CenterCY - R) * n;
        int coreW = (2 * R + 1) * n + 1;      // inclusive samples per axis (matches collider)
        int padW = coreW + 2;                 // +1 border each side for edge normals

        // Pre-warm the chunk-type cache for every chunk the parallel + apron passes can
        // query (core + apron + one blended-colour neighbour) so the legacy biome cache
        // is only READ, never written, during the parallel build.
        int warm = R + ApronExtra + 1;
        for (var cyy = ctx.CenterCY - warm; cyy <= ctx.CenterCY + warm; cyy++)
            for (var cxx = ctx.CenterCX - warm; cxx <= ctx.CenterCX + warm; cxx++)
                ctx.ChunkType(cxx, cyy);

        // 1) padded height grid — the field sampled once per tile across all cores.
        var Hpad = new float[padW * padW];
        System.Threading.Tasks.Parallel.For(0, padW, pz =>
        {
            int wz = coreMinZ - 1 + pz;
            for (var px = 0; px < padW; px++)
                Hpad[pz * padW + px] = TerrainHeightField.H(coreMinX - 1 + px, wz);
        });

        // 2) per-vertex attributes (normal / colour / AO) — parallel, pure.
        int vcount = coreW * coreW;
        var V = new Vector3[vcount]; var Nrm = new Vector3[vcount];
        var Col = new Color[vcount]; var Uv = new Vector2[vcount];
        System.Threading.Tasks.Parallel.For(0, coreW, z =>
        {
            for (var x = 0; x < coreW; x++)
            {
                double wx = coreMinX + x, wz = coreMinZ + z;
                var h = Hpad[(z + 1) * padW + (x + 1)];
                var hl = Hpad[(z + 1) * padW + x];
                var hr = Hpad[(z + 1) * padW + (x + 2)];
                var hd = Hpad[z * padW + (x + 1)];
                var hu = Hpad[(z + 2) * padW + (x + 1)];
                var normal = new Vector3(hl - hr, 2f, hd - hu).Normalized();
                var avgN = (hl + hr + hd + hu) * 0.25f;
                var ao = Mathf.Clamp(1f + (h - avgN) * 0.12f, 0.6f, 1f);
                var vcol = VertexColor(wx, wz, h, 1f - normal.Y);
                vcol.A = ao;
                var vi = z * coreW + x;
                V[vi] = new Vector3((float)wx, h, (float)wz);
                Nrm[vi] = normal; Col[vi] = vcol;
                Uv[vi] = new Vector2((float)wx * 0.25f, (float)wz * 0.25f);
            }
        });

        // 3) commit ONE merged core mesh (main thread).
        var surf = new SurfaceTool();
        surf.Begin(Mesh.PrimitiveType.Triangles);
        for (var vi = 0; vi < vcount; vi++)
        {
            surf.SetColor(Col[vi]); surf.SetNormal(Nrm[vi]);
            surf.SetUV(Uv[vi]); surf.AddVertex(V[vi]);
        }
        for (var z = 0; z < coreW - 1; z++)
            for (var x = 0; x < coreW - 1; x++)
            {
                int i00 = z * coreW + x, i10 = i00 + 1, i01 = i00 + coreW, i11 = i01 + 1;
                surf.AddIndex(i00); surf.AddIndex(i01); surf.AddIndex(i11);
                surf.AddIndex(i00); surf.AddIndex(i11); surf.AddIndex(i10);
            }
        terrain.AddChild(new MeshInstance3D { Mesh = surf.Commit(), MaterialOverride = terrainMat });

        // 4) ONE continuous heightmap collider over the whole walkable window (centred),
        //    sampled from the SAME grid as the mesh so the surface and floor never diverge.
        var mapData = new float[vcount];
        for (var z = 0; z < coreW; z++)
            for (var x = 0; x < coreW; x++)
                mapData[z * coreW + x] = Hpad[(z + 1) * padW + (x + 1)];
        var body = new StaticBody3D
        {
            Position = new Vector3(coreMinX + (coreW - 1) * 0.5f, 0f, coreMinZ + (coreW - 1) * 0.5f),
        };
        body.AddChild(new CollisionShape3D
        {
            Shape = new HeightMapShape3D { MapWidth = coreW, MapDepth = coreW, MapData = mapData },
        });
        terrain.AddChild(body);

        // 5) coarse dropped apron — extends the visible ground far past the sharp core
        //    with a single extra draw call and no collider cost.
        BuildTerrainApron(terrain, ctx, terrainMat, VertexColor);

        AddWater(terrain, ctx.CenterCX, ctx.CenterCY);
    }

    /// <summary>ONE coarse, collision-free sheet reaching ChunkRadius+ApronExtra chunks,
    /// seated ApronDrop below the sharp core so the core overdraws the join. It carries
    /// the SAME colouring as the core (via <paramref name="colorFn"/>) so the mid-band
    /// reads as the same world at lower detail — filling the gap to the far skirt.</summary>
    private void BuildTerrainApron(Node3D terrain, WorldContext ctx, Material mat,
                                   System.Func<double, double, float, float, Color> colorFn)
    {
        int n = ChunkSize;
        int er = ChunkRadius + ApronExtra;
        int minX = (ctx.CenterCX - er) * n;
        int minZ = (ctx.CenterCY - er) * n;
        int spanTiles = (2 * er + 1) * n;
        int step = ApronStep;
        int cols = spanTiles / step + 1;

        // Parallel field sampling (H() is ~30 octaves and this is thousands of samples — the
        // same reason the core is parallel). The main thread does only the SurfaceTool commit.
        var pos = new Vector3[cols * cols];
        var col = new Color[cols * cols];
        System.Threading.Tasks.Parallel.For(0, cols, r =>
        {
            for (var c = 0; c < cols; c++)
            {
                double wx = minX + c * step, wz = minZ + r * step;
                var h = TerrainHeightField.H(wx, wz);
                var dhx = TerrainHeightField.H(wx + step, wz) - TerrainHeightField.H(wx - step, wz);
                var dhz = TerrainHeightField.H(wx, wz + step) - TerrainHeightField.H(wx, wz - step);
                var slope = Mathf.Sqrt(dhx * dhx + dhz * dhz) / (2f * step);
                var vi = r * cols + c;
                pos[vi] = new Vector3((float)wx, h - ApronDrop, (float)wz);   // seat under the core
                col[vi] = colorFn(wx, wz, h, slope);
            }
        });

        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        for (var vi = 0; vi < pos.Length; vi++) { st.SetColor(col[vi]); st.AddVertex(pos[vi]); }
        for (var r = 0; r < cols - 1; r++)
            for (var c = 0; c < cols - 1; c++)
            {
                int i00 = r * cols + c, i10 = i00 + 1, i01 = i00 + cols, i11 = i01 + 1;
                st.AddIndex(i00); st.AddIndex(i01); st.AddIndex(i11);
                st.AddIndex(i00); st.AddIndex(i11); st.AddIndex(i10);
            }
        st.GenerateNormals();
        terrain.AddChild(new MeshInstance3D { Mesh = st.Commit(), MaterialOverride = mat });
    }

    /// <summary>A coarse, collision-free terrain skirt out to FarRadius so distant hills
    /// and mountains are visible on the HORIZON (something to walk toward) and the near
    /// window rebuilds against a stable backdrop instead of blank fog. Sits ~3u below the
    /// detailed near terrain, which draws over it in the overlap; a matching far water
    /// sheet gives distant lakes/ocean. Rebuilt only every FarThreshold chunks.</summary>
    private void BuildFarTerrain(int ccx, int ccy)
    {
        _farCX = ccx; _farCY = ccy;
        GetNodeOrNull("FarTerrain")?.Free();
        var root = new Node3D { Name = "FarTerrain" };
        AddChild(root);

        var mat = new StandardMaterial3D { VertexColorUseAsAlbedo = true, Roughness = 1f };
        var stone = new Color(0.46f, 0.44f, 0.41f);
        var snow = new Color(0.90f, 0.93f, 0.97f);
        Color FarColor(double wx, double wz, float h)
        {
            var t = BiomeTypeAt((int)Math.Floor(wx / 16.0), (int)Math.Floor(wz / 16.0));
            var c = GeoColors.TryGetValue(t, out var bc) ? bc : new Color(0.30f, 0.42f, 0.26f);
            c = c.Lerp(stone, Mathf.Clamp((h - 60f) / 130f, 0f, 1f) * 0.8f);
            c = c.Lerp(snow, Mathf.Clamp((h - 210f) / 110f, 0f, 1f));
            return c;
        }

        int minX = (ccx - FarRadius) * ChunkSize, minZ = (ccy - FarRadius) * ChunkSize;
        int cols = FarRadius * 2 * ChunkSize / FarStep + 1;
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        for (var r = 0; r < cols; r++)
            for (var c = 0; c < cols; c++)
            {
                double wx = minX + c * FarStep, wz = minZ + r * FarStep;
                var h = (float)TerrainHeightField.NaturalHeight(wx, wz);
                st.SetColor(FarColor(wx, wz, h));
                st.AddVertex(new Vector3((float)wx, h - 3f, (float)wz));   // under the near terrain
            }
        for (var r = 0; r < cols - 1; r++)
            for (var c = 0; c < cols - 1; c++)
            {
                int i00 = r * cols + c, i10 = i00 + 1, i01 = i00 + cols, i11 = i01 + 1;
                st.AddIndex(i00); st.AddIndex(i01); st.AddIndex(i11);
                st.AddIndex(i00); st.AddIndex(i11); st.AddIndex(i10);
            }
        st.GenerateNormals();
        root.AddChild(new MeshInstance3D { Mesh = st.Commit(), MaterialOverride = mat });

        var span = (FarRadius * 2 + 6) * ChunkSize;
        root.AddChild(new MeshInstance3D
        {
            Name = "FarWater",
            Mesh = new PlaneMesh { Size = new Vector2(span, span), SubdivideWidth = 24, SubdivideDepth = 24 },
            Position = new Vector3(ccx * ChunkSize + ChunkSize * 0.5f,
                                   TerrainHeightField.WaterLevel - 0.2f, ccy * ChunkSize + ChunkSize * 0.5f),
            MaterialOverride = ShaderLib.Water(),
        });
    }

    /// <summary>A single translucent water plane at sea level, centered on the
    /// rendered window.</summary>
    private void AddWater(Node3D parent, int cCX, int cCY)
    {
        var span = (ChunkRadius * 2 + 4) * ChunkSize;
        parent.AddChild(new MeshInstance3D
        {
            Name = "Water",
            Mesh = new PlaneMesh
            {
                Size = new Vector2(span, span),
                SubdivideWidth = 96,
                SubdivideDepth = 96,
            },
            Position = new Vector3(cCX * ChunkSize + ChunkSize * 0.5f,
                                   TerrainHeightField.WaterLevel,
                                   cCY * ChunkSize + ChunkSize * 0.5f),
            MaterialOverride = ShaderLib.Water(),
            CustomAabb = new Aabb(new Vector3(-span * 0.5f, -2f, -span * 0.5f),
                                  new Vector3(span, 4f, span)),
        });
    }

    /// <summary>A colored box mesh with a matching solid box collider — village
    /// walls and buildings.</summary>
    private static void AddSolidBox(Node3D parent, StandardMaterial3D mat,
                                    Vector3 size, Vector3 position)
    {
        var mesh = new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = size },
            MaterialOverride = mat,
            Position = position,
        };
        var body = new StaticBody3D();
        body.AddChild(new CollisionShape3D { Shape = new BoxShape3D { Size = size } });
        mesh.AddChild(body);
        parent.AddChild(mesh);
    }

    // =====================================================================
    //  SKY + PLAYER (origin fixtures)
    // =====================================================================
    private void AddSun()
    {
        _sun = new DirectionalLight3D
        {
            Name = "Sun",
            ShadowEnabled = true,
            // Shadows only in the near field (2 splits, ~180u) instead of the default 4-split
            // full-range cascade — far terrain + distant forests no longer pay for shadow passes,
            // a big win with the huge merged terrain mesh, and near shadows still read.
            DirectionalShadowMode = DirectionalLight3D.ShadowMode.Parallel2Splits,
            DirectionalShadowMaxDistance = 180f,
            LightColor = new Color(1f, 0.96f, 0.87f),
            LightEnergy = 1.25f,
            Rotation = new Vector3(Mathf.DegToRad(-48), Mathf.DegToRad(35), 0),
            LightVolumetricFogEnergy = 1.0f,
        };
        AddChild(_sun);

        _skyMat = new ProceduralSkyMaterial
        {
            SkyTopColor = new Color(0.28f, 0.48f, 0.78f),
            SkyHorizonColor = new Color(0.72f, 0.80f, 0.86f),
            GroundHorizonColor = new Color(0.68f, 0.72f, 0.74f),
            GroundBottomColor = new Color(0.30f, 0.33f, 0.35f),
            SunAngleMax = 12f,
        };

        _env = new global::Godot.Environment
        {
            BackgroundMode = global::Godot.Environment.BGMode.Sky,
            Sky = new Sky { SkyMaterial = _skyMat, ProcessMode = Sky.ProcessModeEnum.Realtime },
            AmbientLightSource = global::Godot.Environment.AmbientSource.Sky,
            AmbientLightEnergy = 0.6f,
            TonemapMode = global::Godot.Environment.ToneMapper.Filmic,
            TonemapExposure = 1.0f,

            FogEnabled = true,
            FogLightColor = new Color(0.76f, 0.83f, 0.90f),
            // Gentle distance haze only — was 0.00045 (~36% opaque by 1km), which buried
            // every mid/far vista in murk. At 0.00014 distant mountains read through a
            // soft atmospheric veil instead of a brown wall.
            FogDensity = 0.00014f,
            FogSkyAffect = 0.1f,

            AdjustmentEnabled = true,
            AdjustmentSaturation = Saturation,
            AdjustmentContrast = Contrast,
            AdjustmentBrightness = 1.0f,

            GlowEnabled = true,
            GlowIntensity = 0.9f,
            GlowStrength = GlowStrength,
            GlowBloom = 0.15f,
            GlowBlendMode = global::Godot.Environment.GlowBlendModeEnum.Softlight,
            GlowHdrThreshold = 1.0f,

            // SSAO kept but lighter (contact shadows without the full cost); SSIL (screen-space
            // indirect light) is very expensive for a subtle bounce, so it is OFF for speed.
            SsaoEnabled = true,
            SsaoRadius = 1.0f,
            SsaoIntensity = 1.2f,
            SsaoPower = 1.5f,
            SsilEnabled = false,
        };
        _env.SetGlowLevel(0, 1.0f);
        _env.SetGlowLevel(1, 1.0f);
        _env.SetGlowLevel(2, 0.6f);

        if (EnableVolumetricFog)
        {
            _env.VolumetricFogEnabled = true;
            // Was 0.015 over 120u — ~83% extinction by 120u, i.e. a pea-soup wall that
            // hid the whole world past arm's reach. 0.0022 over 200u is a soft, godray-
            // carrying haze that adds depth without erasing the vista.
            _env.VolumetricFogDensity = 0.0022f;
            _env.VolumetricFogAlbedo = new Color(0.90f, 0.93f, 1f);
            _env.VolumetricFogLength = 200f;
            _env.VolumetricFogAnisotropy = 0.3f;
        }
        if (EnableSdfgi)
        {
            _env.SdfgiEnabled = true;
            _env.SdfgiUseOcclusion = true;
        }

        AddChild(new WorldEnvironment { Environment = _env });

        if (EnableDayNight)
        {
            _dayNight = new DayNightCycle(_sun, _skyMat, _env) { Name = "DayNightCycle" };
            AddChild(_dayNight);
        }
    }

    private PlayerController AddPlayer()
    {
        var player = new PlayerController
        {
            Name = "Player",
            Position = new Vector3(8, TerrainHeightField.H(8, 8) + 3f, 8),
        };

        var capsule = new MeshInstance3D
        {
            Name = "Body",
            Mesh = new CapsuleMesh { Radius = 0.33f, Height = 1.7f },
            MaterialOverride = new StandardMaterial3D
            {
                AlbedoColor = new Color(80 / 255f, 180 / 255f, 1f),
            },
            Position = new Vector3(0, 0.85f, 0),
        };
        player.AddChild(capsule);

        var collider = new CollisionShape3D
        {
            Shape = new CapsuleShape3D { Radius = 0.33f, Height = 1.7f },
            Position = new Vector3(0, 0.85f, 0),
        };
        player.AddChild(collider);

        var camera = new OrbitCamera { Name = "OrbitCamera" };
        player.AddChild(camera);

        AddChild(player);
        return player;
    }
}
