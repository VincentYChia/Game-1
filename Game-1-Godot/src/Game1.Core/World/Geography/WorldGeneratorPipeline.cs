namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/world_generator.py WorldGenerator — the single
/// entry point: nations → regions → provinces → districts → biomes →
/// ecosystems → names (localities EMPTY at naming time, like Python) →
/// WorldMap assembly (row-major) → villages (failure → empty list).
/// </summary>
public sealed class WorldGeneratorPipeline
{
    public long Seed;
    public GeographicConfig Config;
    public string ContentRoot;
    public string? TemplatePath;

    public List<VillageRecord> Villages = new();

    public WorldGeneratorPipeline(long seed, GeographicConfig config,
                                  string contentRoot, string? templatePath = null)
    {
        Seed = seed;
        Config = config;
        ContentRoot = contentRoot;
        TemplatePath = templatePath;
    }

    public WorldMap Generate()
    {
        var worldSize = Config.World.WorldSize;

        // Phase 1: Nations
        var (nationMap, nationMetadata) =
            NationGenerator.GenerateNations(Seed, Config, TemplatePath);

        // Phase 2: Regions
        var (regionMap, regionMapOrder, regionMetadata) =
            RegionGenerator.GenerateRegions(nationMap, nationMetadata, Seed, Config);

        // Phase 3: Provinces
        var (provinceMap, provinceMetadata) =
            PoliticalGenerator.GenerateProvinces(regionMap, regionMetadata,
                                                 Seed, Config);

        // Phase 4: Districts
        var (districtMap, districtMetadata) =
            PoliticalGenerator.GenerateDistricts(provinceMap, provinceMetadata,
                                                 Seed, Config);

        // Phase 5: Biomes
        var (chunkTypeMap, chunkTypeOrder, biomeMap, biomeMetadata) =
            GeoBiomeGenerator.GenerateBiomes(regionMap, regionMapOrder,
                                             regionMetadata, Seed, Config);

        // Phase 6: Ecosystems
        var (ecosystemMap, dangerMap, ecosystemMetadata) =
            EcosystemGenerator.GenerateEcosystems(chunkTypeMap, chunkTypeOrder,
                                                  Seed, Config);

        // Phase 7: Names — localities are EMPTY here (villages named later
        // by their own hash path), exactly like Python
        var localities = new Dictionary<int, LocalityData>();
        // nations dict inserted 0..count-1 ascending by GenerateNations
        var nationInsertionOrder = nationMetadata.Keys.ToList();
        NameGenerator.NameAll(nationMetadata, nationInsertionOrder,
                              regionMetadata, provinceMetadata,
                              districtMetadata, localities, Seed);

        // Phase 8: Assemble — row-major y-outer/x-inner
        var worldMap = new WorldMap
        {
            Seed = Seed,
            WorldSize = worldSize,
            Nations = nationMetadata,
            NationOrder = nationInsertionOrder,
            Regions = regionMetadata,
            Provinces = provinceMetadata,
            Districts = districtMetadata,
            Biomes = biomeMetadata,
            Ecosystems = ecosystemMetadata,
            Localities = localities,
        };

        var half = worldSize / 2;
        for (var y = -half; y < half; y++)
        {
            for (var x = -half; x < half; x++)
            {
                var pos = (x, y);
                var geo = new GeographicData
                {
                    NationId = nationMap.Map.GetValueOrDefault(pos, -1),
                    RegionId = regionMap.GetValueOrDefault(pos, -1),
                    ProvinceId = provinceMap.GetValueOrDefault(pos, -1),
                    DistrictId = districtMap.GetValueOrDefault(pos, -1),
                    // Python: chunk_type_map.get(pos, chunk_type_map.get(pos))
                    // — double .get is a None default; unreachable in practice
                    // (every world chunk has a type). Forest guards the edge.
                    ChunkType = chunkTypeMap.GetValueOrDefault(pos, NewChunkTypes.Forest),
                    BiomeId = biomeMap.GetValueOrDefault(pos, -1),
                    EcosystemId = ecosystemMap.GetValueOrDefault(pos, -1),
                    DangerLevel = dangerMap.GetValueOrDefault(pos, DangerLevel.Moderate),
                };
                worldMap.ChunkData[pos] = geo;
                worldMap.ChunkOrder.Add(pos);
            }
        }

        // Phase 9: Villages — Python wraps in try/except → empty list
        try
        {
            Villages = VillageGenerator.PlaceVillages(worldMap, Seed, ContentRoot);
        }
        catch
        {
            Villages = new List<VillageRecord>();
        }

        return worldMap;
    }
}
