using Game1.Core.Data;

namespace Game1.Core.World;

/// <summary>
/// Port of systems/biome_generator.py — the legacy fallback generator (still
/// the oracle for pre-geographic saves and graceful degradation). Deterministic
/// per-chunk typing from world seed: Szudzik-paired chunk seeds, custom hash
/// mixing (reproduced with unchecked 64-bit arithmetic — Python's unbounded
/// ints only ever influence the masked low bits), danger zones (progressive
/// safety within ±8 chunks), spawn-area typing via Python-exact MT19937 choice.
/// Pinned by conformance/goldens/db_parity/biome_generator.json (25x25 grid +
/// sha256 canon per seed — the P3 "same seed → identical grid hash" oracle).
/// </summary>
public sealed class BiomeGenerator
{
    public const int SafeZoneRadius = 8;

    private readonly long _seed;
    private readonly WorldGenerationConfig _config;
    private readonly Dictionary<(int, int), string> _typeCache = new();

    public BiomeGenerator(long worldSeed, WorldGenerationConfig config)
    {
        _seed = worldSeed;
        _config = config;
    }

    // biome_generator.py:95-125 — Szudzik pairing + mix, masked to 32 bits
    public long GetChunkSeed(int chunkX, int chunkY)
    {
        long ax = chunkX >= 0 ? chunkX * 2L : -chunkX * 2L - 1;
        long ay = chunkY >= 0 ? chunkY * 2L : -chunkY * 2L - 1;
        var coordHash = ax >= ay ? ax * ax + ax + ay : ay * ay + ax;

        unchecked
        {
            var h = (ulong)_seed;
            h ^= (ulong)coordHash;
            h = (h ^ (h >> 16)) * 0x85ebca6bUL;
            h = (h ^ (h >> 13)) * 0xc2b2ae35UL;
            h ^= h >> 16;
            return (long)(h & 0xFFFFFFFFUL);
        }
    }

    // :127-145 — deterministic float [0, 1)
    public double Hash2D(int x, int y, int offset = 0)
    {
        unchecked
        {
            var h = (ulong)(_seed + offset);
            h ^= (ulong)(x * 374761393L);
            h ^= (ulong)(y * 668265263L);
            h = (h ^ (h >> 13)) * 1274126177UL;
            h ^= h >> 16;
            return (h & 0x7FFFFFFFUL) / (double)0x7FFFFFFF;
        }
    }

    private bool IsSpawnArea(int chunkX, int chunkY)
    {
        var radius = _config.ChunkLoading.SpawnAlwaysLoadedRadius;
        return Math.Abs(chunkX) <= radius && Math.Abs(chunkY) <= radius;
    }

    // :209-232 — category thresholds respect configured ratios exactly
    private string GetBiomeCategory(int chunkX, int chunkY)
    {
        var roll = Hash2D(chunkX, chunkY, 100);
        if (roll < _config.BiomeDistribution.Water) return "water";
        if (roll < _config.BiomeDistribution.Water + _config.BiomeDistribution.Forest)
            return "forest";
        return "cave";
    }

    // :251-295 — progressive safety inside ±8, fair game outside
    private string GetDangerLevel(int chunkX, int chunkY)
    {
        var distance = Math.Max(Math.Abs(chunkX), Math.Abs(chunkY));
        var roll = Hash2D(chunkX, chunkY, 5000);

        if (distance <= SafeZoneRadius)
        {
            var safetyFactor = 1.0 - (double)distance / SafeZoneRadius;
            var peacefulThreshold = 0.40 + 0.60 * safetyFactor;
            var dangerousThreshold = peacefulThreshold + 0.45 * (1 - safetyFactor);
            if (roll < peacefulThreshold) return "peaceful";
            return roll < dangerousThreshold ? "dangerous" : "rare";
        }
        if (roll < 0.40) return "peaceful";
        return roll < 0.80 ? "dangerous" : "rare";
    }

    // :312-351
    public string GetChunkType(int chunkX, int chunkY)
    {
        if (_typeCache.TryGetValue((chunkX, chunkY), out var cached))
            return cached;

        string chunkType;
        if (IsSpawnArea(chunkX, chunkY))
        {
            // :353-371 — Python-exact MT19937 choice over three peaceful types
            var rng = new PythonRandom(GetChunkSeed(chunkX, chunkY));
            chunkType = rng.Choice(new[]
            { "peaceful_forest", "peaceful_quarry", "peaceful_cave" });
        }
        else
        {
            var biome = GetBiomeCategory(chunkX, chunkY);
            var danger = GetDangerLevel(chunkX, chunkY);
            chunkType = BiomeToChunkType(biome, danger, chunkX, chunkY);
        }

        _typeCache[(chunkX, chunkY)] = chunkType;
        return chunkType;
    }

    // :373-417
    private string BiomeToChunkType(string biome, string danger, int chunkX, int chunkY)
    {
        var typeRoll = Hash2D(chunkX, chunkY, 3000);

        if (biome == "water")
        {
            if (danger == "rare") return "water_cursed_swamp";
            return typeRoll < _config.LakeChance ? "water_lake" : "water_river";
        }
        if (biome == "forest")
        {
            return danger switch
            {
                "peaceful" => "peaceful_forest",
                "dangerous" => "dangerous_forest",
                _ => "rare_hidden_forest",
            };
        }
        var isQuarry = typeRoll < 0.5;
        return danger switch
        {
            "peaceful" => isQuarry ? "peaceful_quarry" : "peaceful_cave",
            "dangerous" => isQuarry ? "dangerous_quarry" : "dangerous_cave",
            _ => isQuarry ? "rare_ancient_quarry" : "rare_deep_cave",
        };
    }

    // :419-434
    public bool IsWaterChunk(int chunkX, int chunkY)
    {
        if (IsSpawnArea(chunkX, chunkY)) return false;
        return GetBiomeCategory(chunkX, chunkY) == "water";
    }

    // :436-476
    public bool ShouldSpawnDungeon(int chunkX, int chunkY)
    {
        if (!_config.DungeonSpawning.Enabled) return false;
        var distance = Math.Max(Math.Abs(chunkX), Math.Abs(chunkY));
        if (distance < _config.DungeonSpawning.MinDistanceFromSpawn) return false;
        if (_config.DungeonSpawning.ExcludedInSpawnArea && IsSpawnArea(chunkX, chunkY))
            return false;
        if (_config.DungeonSpawning.ExcludedInWater && IsWaterChunk(chunkX, chunkY))
            return false;
        return Hash2D(chunkX, chunkY, 10000) < _config.DungeonSpawning.SpawnChancePerChunk;
    }
}
