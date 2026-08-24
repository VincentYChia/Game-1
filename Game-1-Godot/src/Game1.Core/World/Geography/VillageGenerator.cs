using System.Text.Json.Nodes;
using Game1.Core.Data;

namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/village_generator.py — village placement on
/// the chunk grid from Definitions.JSON/village-config.JSON (v2.0; key
/// order preserved — tier iteration order is load-bearing), MT19937 draws
/// via the certified PythonRandom (seed+777777 stream for placement, fresh
/// seed+locality_id stream per village for buildings), names via hash
/// noise. Mutates WorldMap localities + per-chunk locality_id like Python.
/// </summary>
public sealed class VillageRecord
{
    public (int X, int Y) CenterChunk;
    public List<(int X, int Y)> Chunks = new();
    public int Size;
    public string Tier = "";
    public JsonObject TierConfig = new();      // shared reference, like Python
    public List<(int X, int Y)> NpcPositions = new();
    public List<JsonObject> NpcTemplates = new();
    public int LocalityId;
    public string Name = "";
    public string Nation = "";
}

public static class VillageGenerator
{
    private static JsonObject? _configCache;

    // _load_config — same search order; cache; fallback defaults are dead
    // with the live v2.0 file but ported for fidelity
    public static JsonObject LoadConfig(string contentRoot)
    {
        if (_configCache is not null) return _configCache;
        foreach (var path in new[]
                 {
                     Path.Combine(contentRoot, "Definitions.JSON", "village-config.JSON"),
                     Path.Combine(contentRoot, "world_system", "config", "village-config.JSON"),
                 })
        {
            if (!File.Exists(path)) continue;
            _configCache = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
            if (_configCache is not null) return _configCache;
        }

        _configCache = new JsonObject
        {
            ["placement"] = new JsonObject
            {
                ["target_count"] = 30, ["min_distance"] = 40,
                ["valid_danger_levels"] = new JsonArray { 1, 2, 3 },
                ["excluded_chunk_types"] = new JsonArray
                {
                    "lake", "river", "cursed_marsh", "wetland",
                    "deep_cave", "crystal_cavern", "flooded_cave",
                },
            },
            ["tiers"] = new JsonObject
            {
                ["small"] = new JsonObject
                {
                    ["size"] = 2, ["entrances"] = 4, ["entrance_width"] = 3,
                    ["wall_inset"] = 1, ["npc_min"] = 3, ["npc_max"] = 5,
                    ["buildings_min"] = 2, ["buildings_max"] = 4,
                    ["building_width_range"] = new JsonArray { 4, 6 },
                    ["building_height_range"] = new JsonArray { 3, 4 },
                    ["spawn_weight"] = 100, ["display_name"] = "Hamlet",
                },
            },
            ["npc_templates"] = new JsonArray
            {
                new JsonObject
                {
                    ["npc_id_prefix"] = "village_villager", ["name"] = "Villager",
                    ["sprite_color"] = new JsonArray { 180, 160, 140 },
                    ["dialogue_lines"] = new JsonArray { "Hello!", "Welcome!" },
                    ["spawn_weight"] = 100,
                },
            },
            ["naming"] = new JsonObject
            {
                ["prefixes"] = new JsonArray { "Old", "New" },
                ["suffixes"] = new JsonArray { "haven", "stead" },
            },
        };
        return _configCache;
    }

    public static void ResetConfigCache() => _configCache = null;

    /// <summary>Ordered tier filter: dict-valued entries, no "_" prefix.</summary>
    private static List<(string Name, JsonObject Tier)> FilteredTiers(JsonObject cfg)
    {
        var result = new List<(string, JsonObject)>();
        if (cfg["tiers"] is JsonObject tiers)
            foreach (var kv in tiers)
                if (kv.Value is JsonObject t && !kv.Key.StartsWith("_"))
                    result.Add((kv.Key, t));
        return result;
    }

    private static double Weight(JsonObject o, string key, double dflt) =>
        J.AsNum(o[key]) ?? dflt;

    // _select_tier — danger pool first (one uniform), spawn-weight fallback
    public static (string Name, JsonObject Tier) SelectTier(
        JsonObject cfg, PythonRandom rng, int dangerLevel = 3)
    {
        var tiers = FilteredTiers(cfg);
        var tierLookup = tiers.ToDictionary(t => t.Name, t => t.Tier);

        var pool = (cfg["tier_selection_by_danger"] as JsonObject)?
            [dangerLevel.ToString()] as JsonArray;
        if (pool is { Count: > 0 })
        {
            var total = 0.0;
            foreach (var entry in pool)
                total += J.AsNum(entry![1]) ?? 0;
            var roll = rng.Uniform(0, total);
            var cumulative = 0.0;
            foreach (var entry in pool)
            {
                var tierName = entry![0]!.GetValue<string>();
                cumulative += J.AsNum(entry[1]) ?? 0;
                if (roll <= cumulative && tierLookup.ContainsKey(tierName))
                    return (tierName, tierLookup[tierName]);
            }
            // fall through consumes a SECOND uniform below
        }

        var entries = tiers;
        var fallbackTotal = 0.0;
        foreach (var (_, t) in entries)
            fallbackTotal += Weight(t, "spawn_weight", 1);
        var fallbackRoll = rng.Uniform(0, fallbackTotal);   // draws even when empty
        var cum = 0.0;
        foreach (var (name, t) in entries)
        {
            cum += Weight(t, "spawn_weight", 1);
            if (fallbackRoll <= cum)
                return (name, t);
        }
        return entries.Count > 0 ? entries[^1] : ("small", new JsonObject());
    }

    // _select_npc_template — empty list → hardcoded default, NO draw
    public static JsonObject SelectNpcTemplate(JsonObject cfg, PythonRandom rng)
    {
        var templates = cfg["npc_templates"] as JsonArray;
        if (templates is null || templates.Count == 0)
        {
            return new JsonObject
            {
                ["npc_id_prefix"] = "villager", ["name"] = "Villager",
                ["sprite_color"] = new JsonArray { 180, 160, 140 },
                ["dialogue_lines"] = new JsonArray { "Hello!" },
            };
        }
        var total = 0.0;
        foreach (var t in templates)
            total += Weight((JsonObject)t!, "spawn_weight", 1);
        var roll = rng.Uniform(0, total);
        var cumulative = 0.0;
        foreach (var t in templates)
        {
            cumulative += Weight((JsonObject)t!, "spawn_weight", 1);
            if (roll <= cumulative)
                return (JsonObject)t!;
        }
        return (JsonObject)templates[^1]!;
    }

    // _distribute_entrances — [south, north, east, west] priority
    public static List<string> DistributeEntrances(int numEntrances)
    {
        var walls = new[] { "south", "north", "east", "west" };
        if (numEntrances <= 0) return new List<string>();
        if (numEntrances >= 4)
        {
            var result = walls.ToList();
            for (var i = 0; i < numEntrances - 4; i++)
                result.Add(walls[i % 4]);
            return result;
        }
        return walls.Take(numEntrances).ToList();
    }

    /// <summary>place_villages — MUTATES worldMap (localities + locality_id).</summary>
    public static List<VillageRecord> PlaceVillages(WorldMap worldMap, long seed,
                                                    string contentRoot)
    {
        var cfg = LoadConfig(contentRoot);
        var placement = cfg["placement"] as JsonObject ?? new JsonObject();
        var rng = new PythonRandom(seed + 777777);

        var targetCount = (int)(J.AsNum(placement["target_count"]) ?? 30);
        var minDistance = (int)(J.AsNum(placement["min_distance"]) ?? 40);
        var validDangers = new HashSet<int>(
            placement["valid_danger_levels"] is JsonArray vd
                ? vd.Select(v => (int)(J.AsNum(v) ?? 0))
                : new[] { 1, 2, 3 });
        var excludedTypes = new HashSet<string>(
            placement["excluded_chunk_types"] is JsonArray et
                ? et.Select(v => v!.GetValue<string>())
                : Enumerable.Empty<string>());

        var tiers = FilteredTiers(cfg);
        var minSize = tiers.Count > 0
            ? tiers.Min(t => (int)Weight(t.Tier, "size", 2)) : 2;

        // Candidate scan — chunk_data INSERTION order (Phase-8 row-major)
        var candidates = new List<(int Cx, int Cy, int Dl)>();
        var checkedSet = new HashSet<(int, int)>();
        foreach (var (cx, cy) in worldMap.ChunkOrder)
        {
            if (checkedSet.Contains((cx, cy))) continue;
            var geo = worldMap.ChunkData[(cx, cy)];
            var ct = geo.ChunkType;
            if (excludedTypes.Contains(ct)) { checkedSet.Add((cx, cy)); continue; }
            var dl = (int)geo.DangerLevel;
            if (!validDangers.Contains(dl)) { checkedSet.Add((cx, cy)); continue; }

            // block validation: existence + excluded type; danger ANCHOR-ONLY
            var valid = true;
            for (var dx = 0; dx < minSize && valid; dx++)
            {
                for (var dy = 0; dy < minSize; dy++)
                {
                    var g = worldMap.ChunkData.GetValueOrDefault((cx + dx, cy + dy));
                    if (g is null || excludedTypes.Contains(g.ChunkType))
                    {
                        valid = false;
                        break;
                    }
                }
            }

            if (valid)
            {
                candidates.Add((cx, cy, dl));
                for (var dx = 0; dx < minSize; dx++)
                    for (var dy = 0; dy < minSize; dy++)
                        checkedSet.Add((cx + dx, cy + dy));
            }
        }

        rng.Shuffle(candidates);

        var selected = new List<(int Cx, int Cy, int Dl)>();
        foreach (var (cx, cy, dl) in candidates)
        {
            if (selected.Count >= targetCount) break;
            var tooClose = selected.Any(s =>
                Math.Abs(cx - s.Cx) + Math.Abs(cy - s.Cy) < minDistance);   // STRICT
            if (tooClose) continue;
            selected.Add((cx, cy, dl));
        }

        var naming = cfg["naming"] as JsonObject ?? new JsonObject();
        var prefixes = naming["prefixes"] is JsonArray pf
            ? pf.Select(v => v!.GetValue<string>()).ToArray() : new[] { "Village" };
        var suffixes = naming["suffixes"] is JsonArray sf
            ? sf.Select(v => v!.GetValue<string>()).ToArray() : new[] { "town" };

        var nextLid = (worldMap.Localities.Count > 0
            ? worldMap.Localities.Values.Max(l => l.LocalityId) : -1) + 1;

        var villages = new List<VillageRecord>();
        for (var i = 0; i < selected.Count; i++)
        {
            var (cx, cy, dl) = selected[i];
            var (tierName, tier) = SelectTier(cfg, rng, dangerLevel: dl);
            var actualSize = (int)Weight(tier, "size", 2);

            var chunks = new List<(int X, int Y)>();
            for (var dx = 0; dx < actualSize; dx++)
                for (var dy = 0; dy < actualSize; dy++)
                    chunks.Add((cx + dx, cy + dy));

            var npcMin = (long)Weight(tier, "npc_min", 3);
            var npcMax = (long)Weight(tier, "npc_max", 5);
            var npcCount = rng.RandInt(npcMin, npcMax);

            var inset = (int)Weight(tier, "wall_inset", 1);
            var innerX = cx * 16 + inset + 3;
            var innerY = cy * 16 + inset + 3;
            var innerW = actualSize * 16 - (inset + 3) * 2;
            var innerH = innerW;

            var npcPositions = new List<(int X, int Y)>();
            var npcTemplates = new List<JsonObject>();
            for (var n = 0; n < npcCount; n++)
            {
                var nx = innerX + (int)rng.RandInt(2, Math.Max(3, innerW - 2));
                var ny = innerY + (int)rng.RandInt(2, Math.Max(3, innerH - 2));
                npcPositions.Add((nx, ny));
                npcTemplates.Add(SelectNpcTemplate(cfg, rng));
            }

            // Names via hash noise (independent of the MT stream)
            var prefix = prefixes[GeoNoise.Hash2DInt(i, 0, seed + 888888, prefixes.Length)];
            var suffix = suffixes[GeoNoise.Hash2DInt(i, 1, seed + 888888, suffixes.Length)];
            var villageName = prefix + suffix;

            var lid = nextLid + i;
            var geo = worldMap.ChunkData.GetValueOrDefault((cx, cy));
            var nation = geo is not null
                ? worldMap.Nations.GetValueOrDefault(geo.NationId) : null;

            var locality = new LocalityData
            {
                LocalityId = lid,
                Name = villageName,
                ChunkX = cx,
                ChunkY = cy,
                FeatureType = "village",
                AdjacentChunks = chunks,
            };
            worldMap.Localities[lid] = locality;

            foreach (var chunkPos in chunks)
            {
                var gd = worldMap.ChunkData.GetValueOrDefault(chunkPos);
                if (gd is not null)
                    gd.LocalityId = lid;
            }

            villages.Add(new VillageRecord
            {
                CenterChunk = (cx, cy),
                Chunks = chunks,
                Size = actualSize,
                Tier = tierName,
                TierConfig = tier,
                NpcPositions = npcPositions,
                NpcTemplates = npcTemplates,
                LocalityId = lid,
                Name = villageName,
                Nation = nation?.Name ?? "Unknown",
            });
        }

        return villages;
    }

    /// <summary>get_village_wall_tiles — pure; Python floor-div midpoints;
    /// append order north row, south row, west column, east column.</summary>
    public static List<(int X, int Y)> GetVillageWallTiles(VillageRecord village)
    {
        var (cx, cy) = village.CenterChunk;
        var tier = village.TierConfig;
        var size = village.Size;
        var inset = (int)Weight(tier, "wall_inset", 1);
        var numEntrances = (int)Weight(tier, "entrances", 4);
        var entranceWidth = (int)Weight(tier, "entrance_width", 3);

        var x1 = cx * 16 + inset;
        var y1 = cy * 16 + inset;
        var x2 = (cx + size) * 16 - inset - 1;
        var y2 = (cy + size) * 16 - inset - 1;

        var midX = GeoBiomeGenerator.FloorDiv(x1 + x2, 2);
        var midY = GeoBiomeGenerator.FloorDiv(y1 + y2, 2);
        var halfEw = entranceWidth / 2;

        var wallsWithEntrances = DistributeEntrances(numEntrances);
        var counts = new Dictionary<string, int>();
        foreach (var w in wallsWithEntrances)
            counts[w] = counts.GetValueOrDefault(w, 0) + 1;

        var wallTiles = new List<(int X, int Y)>();

        bool IsEntrance(int coord, int mid, int n, int lo, int hi)
        {
            if (n == 1)
                return Math.Abs(coord - mid) <= halfEw;
            if (n >= 2)
            {
                var span = hi - lo;
                for (var e = 0; e < n; e++)
                {
                    // double true-division then int-truncation, like Python
                    var pos = lo + (int)(span * (e + 1) / (double)(n + 1));
                    if (Math.Abs(coord - pos) <= halfEw)
                        return true;
                }
            }
            return false;
        }

        var north = counts.GetValueOrDefault("north", 0);
        for (var x = x1; x <= x2; x++)
            if (!IsEntrance(x, midX, north, x1, x2))
                wallTiles.Add((x, y1));

        var south = counts.GetValueOrDefault("south", 0);
        for (var x = x1; x <= x2; x++)
            if (!IsEntrance(x, midX, south, x1, x2))
                wallTiles.Add((x, y2));

        var west = counts.GetValueOrDefault("west", 0);
        for (var y = y1 + 1; y <= y2 - 1; y++)
            if (!IsEntrance(y, midY, west, y1, y2))
                wallTiles.Add((x1, y));

        var east = counts.GetValueOrDefault("east", 0);
        for (var y = y1 + 1; y <= y2 - 1; y++)
            if (!IsEntrance(y, midY, east, y1, y2))
                wallTiles.Add((x2, y));

        return wallTiles;
    }

    /// <summary>get_village_building_tiles — fresh MT19937 per village
    /// (seed + locality_id); perimeter-minus-door occupancy asymmetry
    /// preserved; dropped buildings still consume all draws.</summary>
    public static List<List<(int X, int Y)>> GetVillageBuildingTiles(
        VillageRecord village, long seed)
    {
        var tier = village.TierConfig;
        var rng = new PythonRandom(seed + village.LocalityId);
        var (cx, cy) = village.CenterChunk;
        var size = village.Size;
        var inset = (int)Weight(tier, "wall_inset", 1);

        var x1 = cx * 16 + inset + 2;
        var y1 = cy * 16 + inset + 2;
        var areaW = size * 16 - (inset + 2) * 2;
        var areaH = areaW;

        var bwRange = tier["building_width_range"] is JsonArray bwr
            ? ((int)(J.AsNum(bwr[0]) ?? 4), (int)(J.AsNum(bwr[1]) ?? 6)) : (4, 6);
        var bhRange = tier["building_height_range"] is JsonArray bhr
            ? ((int)(J.AsNum(bhr[0]) ?? 3), (int)(J.AsNum(bhr[1]) ?? 4)) : (3, 4);
        var bMin = (long)Weight(tier, "buildings_min", 2);
        var bMax = (long)Weight(tier, "buildings_max", 4);
        var buildingCount = rng.RandInt(bMin, bMax);

        var buildings = new List<List<(int X, int Y)>>();
        var occupied = new HashSet<(int, int)>();

        for (var b = 0; b < buildingCount; b++)
        {
            var bw = (int)rng.RandInt(bwRange.Item1, bwRange.Item2);
            var bh = (int)rng.RandInt(bhRange.Item1, bhRange.Item2);

            for (var attempt = 0; attempt < 20; attempt++)
            {
                var bx = x1 + (int)rng.RandInt(1, Math.Max(1, areaW - bw - 2));
                var by = y1 + (int)rng.RandInt(1, Math.Max(1, areaH - bh - 2));

                var tiles = new List<(int X, int Y)>();
                for (var dx = 0; dx < bw; dx++)
                    for (var dy = 0; dy < bh; dy++)
                        tiles.Add((bx + dx, by + dy));

                if (tiles.Any(t => occupied.Contains(t)))
                    continue;   // next attempt — 2 more randints consumed

                var buildingWalls = new List<(int X, int Y)>();
                foreach (var (tx, ty) in tiles)
                {
                    if (tx == bx || tx == bx + bw - 1 || ty == by || ty == by + bh - 1)
                    {
                        if (ty == by + bh - 1 && tx == bx + bw / 2)
                            continue;   // door tile
                        buildingWalls.Add((tx, ty));
                        occupied.Add((tx, ty));
                    }
                }
                buildings.Add(buildingWalls);
                break;
            }
        }

        return buildings;
    }
}
