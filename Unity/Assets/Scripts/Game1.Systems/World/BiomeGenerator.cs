// ============================================================================
// Game1.Systems.World.BiomeGenerator
// Migrated from: systems/biome_generator.py (597 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Deterministic biome generation using per-chunk random selection.
// Szudzik's pairing function for unique coordinate hashing.
// Safe zone: within +/-8 chunks of spawn, progressively safer toward origin.
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Systems.World
{
    /// <summary>
    /// High-level biome categories (before danger sub-typing).
    /// </summary>
    public enum BiomeCategory
    {
        Water,
        Forest,
        Cave
    }

    /// <summary>
    /// Deterministic biome generator. Given a world seed and chunk coordinates,
    /// always produces the same ChunkType. Supports infinite world expansion.
    ///
    /// Danger Zones:
    ///   Within +/-8 chunks of spawn: progressive safety (closer = safer).
    ///   Beyond +/-8 chunks: no bias, random danger distribution.
    ///
    /// Distribution defaults (from world_generation.JSON):
    ///   water=0.10, forest=0.55, cave=0.35
    ///   Outer zone: 40% peaceful, 40% dangerous, 20% rare
    /// </summary>
    public class BiomeGenerator
    {
        // Safety zone configuration (matches Python SAFE_ZONE_RADIUS = 8)
        public const int SafeZoneRadius = 8;

        private readonly int _seed;

        // Biome distribution ratios (defaults; can be overridden from JSON config)
        public float WaterRatio { get; set; } = 0.10f;
        public float ForestRatio { get; set; } = 0.55f;
        public float CaveRatio { get; set; } = 0.35f;

        // Water sub-type ratios
        public float LakeChance { get; set; } = 0.6f;

        // Dungeon spawning config
        public float DungeonSpawnChance { get; set; } = 0.08f;
        public int DungeonMinDistanceFromSpawn { get; set; } = 5;
        public bool DungeonsEnabled { get; set; } = true;

        // Spawn area config
        public int SpawnAlwaysLoadedRadius { get; set; } = 1;

        // Cache for chunk types (ensures consistency)
        private readonly Dictionary<(int, int), ChunkType> _typeCache = new();

        public BiomeGenerator(int seed)
        {
            _seed = seed;
        }

        // ====================================================================
        // Chunk Seed Derivation (Szudzik's pairing function)
        // ====================================================================

        /// <summary>
        /// Derive a deterministic seed for a specific chunk.
        /// Uses Szudzik's pairing function, extended for negative coordinates.
        /// Matches Python get_chunk_seed() exactly.
        /// </summary>
        public int GetChunkSeed(int chunkX, int chunkY)
        {
            // Map negatives to positive space
            long ax = chunkX >= 0 ? chunkX * 2L : (-chunkX * 2L) - 1;
            long ay = chunkY >= 0 ? chunkY * 2L : (-chunkY * 2L) - 1;

            // Szudzik's pairing function
            long coordHash = ax >= ay ? ax * ax + ax + ay : ay * ay + ax;

            // Combine with world seed using mixing (matches Python exactly)
            long h = _seed;
            h ^= coordHash;
            h = (h ^ (h >> 16)) * 0x85ebca6bL;
            h = (h ^ (h >> 13)) * 0xc2b2ae35L;
            h = h ^ (h >> 16);

            return (int)(h & 0xFFFFFFFF);
        }

        // ====================================================================
        // Hash Functions (matching Python _hash_2d)
        // ====================================================================

        /// <summary>
        /// Generate a pseudo-random float [0, 1) for 2D coordinates.
        /// Matches Python _hash_2d() exactly.
        /// </summary>
        private float Hash2D(int x, int y, int offset = 0)
        {
            long h = _seed + offset;
            h ^= (long)x * 374761393L;
            h ^= (long)y * 668265263L;
            h = (h ^ (h >> 13)) * 1274126177L;
            h ^= (h >> 16);

            return (float)(h & 0x7FFFFFFF) / 0x7FFFFFFF;
        }

        // ====================================================================
        // Main Entry Point
        // ====================================================================

        /// <summary>
        /// Get the chunk type for any coordinate. Results are deterministic
        /// based on world seed and coordinates. This is the main entry point.
        /// Matches Python get_chunk_type().
        /// </summary>
        public ChunkType DetermineChunkType(int chunkX, int chunkY)
        {
            var key = (chunkX, chunkY);
            if (_typeCache.TryGetValue(key, out var cached))
                return cached;

            ChunkType chunkType;

            if (IsSpawnArea(chunkX, chunkY))
            {
                chunkType = GetSpawnAreaType(chunkX, chunkY);
            }
            else
            {
                var biome = GetBiomeCategory(chunkX, chunkY);
                string danger = GetDangerLevel(chunkX, chunkY);
                chunkType = BiomeToChunkType(biome, danger, chunkX, chunkY);
            }

            _typeCache[key] = chunkType;
            return chunkType;
        }

        // ====================================================================
        // Biome Category
        // ====================================================================

        private BiomeCategory GetBiomeCategory(int chunkX, int chunkY)
        {
            float roll = Hash2D(chunkX, chunkY, offset: 100);

            if (roll < WaterRatio)
                return BiomeCategory.Water;
            else if (roll < WaterRatio + ForestRatio)
                return BiomeCategory.Forest;
            else
                return BiomeCategory.Cave;
        }

        // ====================================================================
        // Danger Level
        // ====================================================================

        /// <summary>
        /// Determine danger level based on distance from spawn.
        /// Within +/-8 chunks: progressive safety. Beyond: random/fair.
        /// Matches Python _get_danger_level() exactly.
        /// </summary>
        private string GetDangerLevel(int chunkX, int chunkY)
        {
            int distance = Math.Max(Math.Abs(chunkX), Math.Abs(chunkY));
            float roll = Hash2D(chunkX, chunkY, offset: 5000);

            if (distance <= SafeZoneRadius)
            {
                // Progressive safety toward spawn
                float safetyFactor = 1.0f - (float)distance / SafeZoneRadius;

                float peacefulThreshold = 0.40f + (0.60f * safetyFactor);   // 0.40 to 1.0
                float dangerousThreshold = peacefulThreshold + 0.45f * (1f - safetyFactor);

                if (roll < peacefulThreshold)
                    return "peaceful";
                else if (roll < dangerousThreshold)
                    return "dangerous";
                else
                    return "rare";
            }
            else
            {
                // Outer zone: 40% peaceful, 40% dangerous, 20% rare
                if (roll < 0.40f)
                    return "peaceful";
                else if (roll < 0.80f)
                    return "dangerous";
                else
                    return "rare";
            }
        }

        // ====================================================================
        // Sub-type Selection
        // ====================================================================

        private float GetTypeClusterValue(int chunkX, int chunkY)
        {
            return Hash2D(chunkX, chunkY, offset: 3000);
        }

        private bool IsSpawnArea(int chunkX, int chunkY)
        {
            return Math.Abs(chunkX) <= SpawnAlwaysLoadedRadius &&
                   Math.Abs(chunkY) <= SpawnAlwaysLoadedRadius;
        }

        private ChunkType GetSpawnAreaType(int chunkX, int chunkY)
        {
            var rng = new System.Random(GetChunkSeed(chunkX, chunkY));
            return rng.Next(3) switch
            {
                0 => ChunkType.PeacefulForest,
                1 => ChunkType.PeacefulQuarry,
                _ => ChunkType.PeacefulCave,
            };
        }

        /// <summary>
        /// Convert biome category + danger level to specific ChunkType.
        /// Matches Python _biome_to_chunk_type() exactly.
        /// </summary>
        private ChunkType BiomeToChunkType(BiomeCategory biome, string danger, int chunkX, int chunkY)
        {
            float typeRoll = GetTypeClusterValue(chunkX, chunkY);

            switch (biome)
            {
                case BiomeCategory.Water:
                    if (danger == "rare")
                        return ChunkType.WaterCursedSwamp;
                    return typeRoll < LakeChance ? ChunkType.WaterLake : ChunkType.WaterRiver;

                case BiomeCategory.Forest:
                    return danger switch
                    {
                        "peaceful" => ChunkType.PeacefulForest,
                        "dangerous" => ChunkType.DangerousForest,
                        _ => ChunkType.RareHiddenForest,
                    };

                default: // Cave (includes quarries)
                    bool isQuarry = typeRoll < 0.5f;
                    return danger switch
                    {
                        "peaceful" => isQuarry ? ChunkType.PeacefulQuarry : ChunkType.PeacefulCave,
                        "dangerous" => isQuarry ? ChunkType.DangerousQuarry : ChunkType.DangerousCave,
                        _ => isQuarry ? ChunkType.RareAncientQuarry : ChunkType.RareDeepCave,
                    };
            }
        }

        // ====================================================================
        // Dungeon Spawning
        // ====================================================================

        /// <summary>
        /// Determine if a dungeon entrance should spawn in this chunk.
        /// Matches Python should_spawn_dungeon().
        /// </summary>
        public bool ShouldSpawnDungeon(int chunkX, int chunkY)
        {
            if (!DungeonsEnabled) return false;

            int distance = Math.Max(Math.Abs(chunkX), Math.Abs(chunkY));
            if (distance < DungeonMinDistanceFromSpawn) return false;

            if (IsSpawnArea(chunkX, chunkY)) return false;

            // No dungeons in water chunks
            var biome = GetBiomeCategory(chunkX, chunkY);
            if (biome == BiomeCategory.Water) return false;

            float roll = Hash2D(chunkX, chunkY, offset: 10000);
            return roll < DungeonSpawnChance;
        }

        /// <summary>
        /// Check if a chunk is a water biome (without full type determination).
        /// </summary>
        public bool IsWaterChunk(int chunkX, int chunkY)
        {
            if (IsSpawnArea(chunkX, chunkY)) return false;
            return GetBiomeCategory(chunkX, chunkY) == BiomeCategory.Water;
        }
    }
}
