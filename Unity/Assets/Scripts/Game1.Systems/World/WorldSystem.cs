// ============================================================================
// Game1.Systems.World.WorldSystem
// Migrated from: systems/world_system.py (1,111 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Manages the infinite game world with lazy chunk loading.
// Seed-based deterministic generation, death chests, crafting stations,
// placed entities, and full save/load integration.
// ============================================================================

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Game1.Core;
using Game1.Data.Models;

namespace Game1.Systems.World
{
    /// <summary>
    /// Death chest: items dropped on player death, stored at a position until retrieved.
    /// </summary>
    public class DeathChest
    {
        public string ChestId { get; set; }
        public GamePosition Position { get; set; }
        public List<Dictionary<string, object>> RichItems { get; set; } = new();
        public float CreatedTime { get; set; }

        public DeathChest() { }

        public DeathChest(GamePosition position, List<Dictionary<string, object>> richItems, float gameTime)
        {
            ChestId = $"death_chest_{(int)position.X}_{(int)position.Z}_{(int)gameTime}";
            Position = position;
            RichItems = richItems;
            CreatedTime = gameTime;
        }

        public Dictionary<string, object> ToSaveData()
        {
            return new Dictionary<string, object>
            {
                ["chest_id"] = ChestId,
                ["position"] = new Dictionary<string, object>
                {
                    ["x"] = Position.X, ["y"] = Position.Y, ["z"] = Position.Z
                },
                ["rich_items"] = RichItems,
                ["created_time"] = CreatedTime,
            };
        }

        public static DeathChest FromSaveData(Dictionary<string, object> data)
        {
            var posDict = data["position"] as Dictionary<string, object>;
            return new DeathChest
            {
                ChestId = data.TryGetValue("chest_id", out var id) ? id?.ToString() : "death_chest",
                Position = new GamePosition(
                    Convert.ToSingle(posDict["x"]),
                    Convert.ToSingle(posDict["y"]),
                    Convert.ToSingle(posDict["z"])),
                CreatedTime = data.TryGetValue("created_time", out var ct) ? Convert.ToSingle(ct) : 0f,
            };
        }
    }

    /// <summary>
    /// Manages the infinite game world with lazy chunk loading.
    ///
    /// Features:
    /// - Seed-based deterministic chunk generation
    /// - Chunk load/unload based on player proximity
    /// - Fixed crafting stations at spawn
    /// - Player-placed entities (turrets, barriers, etc.)
    /// - Death chest system
    /// - Full save/load with per-chunk modification tracking
    /// </summary>
    public class WorldSystem
    {
        // ====================================================================
        // Fields
        // ====================================================================

        private readonly Dictionary<(int, int), Chunk> _loadedChunks = new();
        private readonly BiomeGenerator _biomeGenerator;
        private readonly HashSet<(int, int)> _barrierPositions = new();

        // Chunk file save directory (set when save path known)
        private string _chunkSaveDir;

        // ====================================================================
        // Properties
        // ====================================================================

        public int Seed { get; }
        public int ChunkSize => GameConfig.ChunkSize;
        public float GameTime { get; set; }

        /// <summary>Fixed crafting stations at spawn.</summary>
        public List<CraftingStationInstance> CraftingStations { get; } = new();

        /// <summary>Player-placed entities (turrets, traps, barriers, etc.).</summary>
        public List<PlacedEntity> PlacedEntities { get; } = new();

        /// <summary>Death chests (items dropped on death).</summary>
        public List<DeathChest> DeathChests { get; } = new();

        /// <summary>Discovered dungeon entrances, keyed by chunk coords.</summary>
        public Dictionary<(int, int), DungeonEntrance> DiscoveredDungeonEntrances { get; } = new();

        /// <summary>Access to loaded chunks (read-only view for rendering, etc.).</summary>
        public IReadOnlyDictionary<(int, int), Chunk> LoadedChunks => _loadedChunks;

        // ====================================================================
        // Construction
        // ====================================================================

        /// <summary>
        /// Initialize the world system with a seed.
        /// Matches Python WorldSystem.__init__().
        /// </summary>
        public WorldSystem(int seed = -1)
        {
            Seed = seed >= 0 ? seed : new System.Random().Next(0, int.MaxValue);
            _biomeGenerator = new BiomeGenerator(Seed);

            // Load initial chunks around spawn
            int spawnRadius = _biomeGenerator.SpawnAlwaysLoadedRadius;
            for (int cx = -spawnRadius; cx <= spawnRadius; cx++)
            {
                for (int cy = -spawnRadius; cy <= spawnRadius; cy++)
                {
                    GetChunk(cx, cy);
                }
            }

            // Spawn fixed crafting stations at origin
            SpawnStartingStations();
        }

        // ====================================================================
        // Chunk Access
        // ====================================================================

        /// <summary>
        /// Get or generate a chunk at the given coordinates.
        /// Primary method for chunk access. Matches Python get_chunk().
        /// </summary>
        public Chunk GetChunk(int chunkX, int chunkY)
        {
            var key = (chunkX, chunkY);

            if (_loadedChunks.TryGetValue(key, out var cached))
                return cached;

            // Try loading from save file
            var chunk = LoadChunkFromFile(chunkX, chunkY);

            if (chunk == null)
            {
                // Generate new chunk
                chunk = new Chunk(chunkX, chunkY, biomeGenerator: _biomeGenerator);
                chunk.GenerateTiles();
                // Note: resource spawning happens via chunk constructor or explicit call
            }

            _loadedChunks[key] = chunk;
            return chunk;
        }

        /// <summary>
        /// Get the chunk containing a world position.
        /// </summary>
        public Chunk GetChunkAtWorldPos(float worldX, float worldZ)
        {
            var (cx, cy) = WorldToChunk(worldX, worldZ);
            return GetChunk(cx, cy);
        }

        /// <summary>
        /// Convert world coordinates to chunk coordinates.
        /// Uses integer division with floor for negative coordinate handling.
        /// </summary>
        public (int chunkX, int chunkY) WorldToChunk(float worldX, float worldZ)
        {
            int tileX = (int)MathF.Floor(worldX);
            int tileZ = (int)MathF.Floor(worldZ);
            // Python-style integer division: floor division handles negatives
            int cx = tileX >= 0 ? tileX / ChunkSize : (tileX - ChunkSize + 1) / ChunkSize;
            int cy = tileZ >= 0 ? tileZ / ChunkSize : (tileZ - ChunkSize + 1) / ChunkSize;
            return (cx, cy);
        }

        /// <summary>
        /// Convert tile coordinates to world-space GamePosition.
        /// </summary>
        public GamePosition TileToWorld(int tileX, int tileZ)
        {
            return GamePosition.FromXZ(tileX, tileZ);
        }

        // ====================================================================
        // Chunk Loading Management
        // ====================================================================

        /// <summary>
        /// Update which chunks are loaded based on player position.
        /// Loads chunks within radius and unloads distant ones.
        /// Matches Python update_loaded_chunks().
        /// </summary>
        public void EnsureChunksLoaded(float playerX, float playerZ, int loadRadius = 4)
        {
            var (playerCx, playerCy) = WorldToChunk(playerX, playerZ);
            int spawnRadius = _biomeGenerator.SpawnAlwaysLoadedRadius;

            var shouldBeLoaded = new HashSet<(int, int)>();

            // Spawn area always loaded
            for (int dx = -spawnRadius; dx <= spawnRadius; dx++)
            {
                for (int dy = -spawnRadius; dy <= spawnRadius; dy++)
                {
                    shouldBeLoaded.Add((dx, dy));
                }
            }

            // Player vicinity
            for (int dx = -loadRadius; dx <= loadRadius; dx++)
            {
                for (int dy = -loadRadius; dy <= loadRadius; dy++)
                {
                    shouldBeLoaded.Add((playerCx + dx, playerCy + dy));
                }
            }

            // Load missing chunks
            foreach (var key in shouldBeLoaded)
            {
                if (!_loadedChunks.ContainsKey(key))
                    GetChunk(key.Item1, key.Item2);
            }

            // Unload distant chunks
            var toUnload = new List<(int, int)>();
            foreach (var key in _loadedChunks.Keys)
            {
                if (!shouldBeLoaded.Contains(key))
                    toUnload.Add(key);
            }

            foreach (var key in toUnload)
                UnloadChunk(key);
        }

        private void UnloadChunk((int, int) key)
        {
            if (!_loadedChunks.TryGetValue(key, out var chunk))
                return;

            chunk.PrepareForUnload(GameTime);

            if (chunk.HasModifications())
                SaveChunkToFile(chunk);

            _loadedChunks.Remove(key);
        }

        // ====================================================================
        // Tile / Resource Access
        // ====================================================================

        /// <summary>
        /// Get the tile at a world position. Auto-loads chunk if needed.
        /// Matches Python get_tile().
        /// </summary>
        public WorldTile GetTile(GamePosition position)
        {
            int tileX = (int)MathF.Floor(position.X);
            int tileZ = (int)MathF.Floor(position.Z);
            var (cx, cy) = WorldToChunk(tileX, tileZ);

            var chunk = GetChunk(cx, cy);
            string key = $"{tileX},{tileZ},0";
            return chunk.Tiles.TryGetValue(key, out var tile) ? tile : null;
        }

        /// <summary>
        /// Check if a world position is walkable. Checks tile, resources, and barriers.
        /// Matches Python is_walkable().
        /// </summary>
        public bool IsWalkable(GamePosition position)
        {
            var tile = GetTile(position);
            if (tile == null) return true; // Unloaded/out-of-range tile — don't block
            if (!tile.Walkable) return false;

            // Check for blocking resources
            int tileX = (int)MathF.Floor(position.X);
            int tileZ = (int)MathF.Floor(position.Z);
            var (cx, cy) = WorldToChunk(tileX, tileZ);

            // Resource blocking radius: 0.3 allows first-person navigation between
            // adjacent resources while still preventing walking through them.
            // (Python used 0.5 for tile-based movement; first-person needs smaller.)
            const float resourceBlockRadius = 0.3f;
            if (_loadedChunks.TryGetValue((cx, cy), out var chunk))
            {
                foreach (var resource in chunk.Resources)
                {
                    if (!resource.IsDepleted)
                    {
                        float dx = MathF.Abs(resource.Position.X - position.X);
                        float dz = MathF.Abs(resource.Position.Z - position.Z);
                        if (dx < resourceBlockRadius && dz < resourceBlockRadius)
                            return false;
                    }
                }
            }

            // Check for blocking barriers (O(1) via cache)
            if (_barrierPositions.Contains((tileX, tileZ)))
                return false;

            return true;
        }

        /// <summary>
        /// Get a resource at a position within tolerance.
        /// Checks current and adjacent chunks. Matches Python get_resource_at().
        /// </summary>
        public NaturalResourceInstance GetResourceAt(GamePosition position, float tolerance = 0.7f)
        {
            int tileX = (int)MathF.Floor(position.X);
            int tileZ = (int)MathF.Floor(position.Z);
            var (cx, cy) = WorldToChunk(tileX, tileZ);

            for (int dx = -1; dx <= 1; dx++)
            {
                for (int dz = -1; dz <= 1; dz++)
                {
                    if (_loadedChunks.TryGetValue((cx + dx, cy + dz), out var chunk))
                    {
                        foreach (var r in chunk.Resources)
                        {
                            if (!r.IsDepleted)
                            {
                                float ddx = MathF.Abs(r.Position.X - position.X);
                                float ddz = MathF.Abs(r.Position.Z - position.Z);
                                if (ddx <= tolerance && ddz <= tolerance)
                                    return r;
                            }
                        }
                    }
                }
            }
            return null;
        }

        /// <summary>
        /// Mark a resource as modified in its chunk for save tracking.
        /// </summary>
        public void MarkResourceModified(NaturalResourceInstance resource)
        {
            int tileX = (int)MathF.Floor(resource.Position.X);
            int tileZ = (int)MathF.Floor(resource.Position.Z);
            var (cx, cy) = WorldToChunk(tileX, tileZ);

            if (_loadedChunks.TryGetValue((cx, cy), out var chunk))
                chunk.MarkResourceModified(resource);
        }

        // ====================================================================
        // Crafting Stations (Fixed at Spawn)
        // ====================================================================

        /// <summary>
        /// Spawn T1-T4 of each station type north of spawn.
        /// Matches Python spawn_starting_stations() exactly.
        /// </summary>
        private void SpawnStartingStations()
        {
            var stationLayout = new (int baseX, StationType type)[]
            {
                (-8, StationType.Smithing),
                (-4, StationType.Refining),
                ( 0, StationType.Adornments),
                ( 4, StationType.Alchemy),
                ( 8, StationType.Engineering),
            };

            foreach (var (baseX, stationType) in stationLayout)
            {
                for (int tier = 1; tier <= 4; tier++)
                {
                    int z = -10 - (tier - 1) * 2; // -10, -12, -14, -16
                    var pos = GamePosition.FromXZ(baseX, z);
                    CraftingStations.Add(new CraftingStationInstance(pos, stationType, tier));
                }
            }
        }

        /// <summary>
        /// Get crafting station at position with tolerance.
        /// Matches Python get_station_at().
        /// </summary>
        public CraftingStationInstance GetStationAt(GamePosition position, float tolerance = 0.8f)
        {
            foreach (var s in CraftingStations)
            {
                float dx = MathF.Abs(s.Position.X - position.X);
                float dz = MathF.Abs(s.Position.Z - position.Z);
                if (dx <= tolerance && dz <= tolerance)
                    return s;
            }
            return null;
        }

        // ====================================================================
        // Placed Entities
        // ====================================================================

        /// <summary>
        /// Place a player entity in the world.
        /// Matches Python place_entity().
        /// </summary>
        public PlacedEntity PlaceEntity(GamePosition position, string itemId,
            PlacedEntityType entityType, int tier = 1, float range = 5.0f,
            float damage = 20.0f, List<string> tags = null,
            Dictionary<string, object> effectParams = null,
            Dictionary<string, object> craftedStats = null)
        {
            // Snap to grid
            var snapped = GamePosition.FromXZ(
                MathF.Floor(position.X),
                MathF.Floor(position.Z));

            var entity = new PlacedEntity
            {
                Position = snapped,
                ItemId = itemId,
                EntityType = entityType,
                Tier = tier,
                Range = range,
                Damage = damage,
                Tags = tags ?? new List<string>(),
                EffectParams = effectParams ?? new Dictionary<string, object>(),
                CraftedStats = craftedStats ?? new Dictionary<string, object>(),
            };

            entity.ApplyCraftedStats();
            PlacedEntities.Add(entity);

            // Update barrier cache
            if (entityType == PlacedEntityType.Barrier)
            {
                _barrierPositions.Add(((int)snapped.X, (int)snapped.Z));
            }

            return entity;
        }

        /// <summary>
        /// Remove a placed entity from the world.
        /// </summary>
        public bool RemoveEntity(PlacedEntity entity)
        {
            if (!PlacedEntities.Remove(entity)) return false;

            if (entity.EntityType == PlacedEntityType.Barrier)
            {
                _barrierPositions.Remove(((int)entity.Position.X, (int)entity.Position.Z));
            }
            return true;
        }

        /// <summary>
        /// Remove a placed entity by EntityId string.
        /// </summary>
        public void RemoveEntityById(string entityId)
        {
            var entity = PlacedEntities.FirstOrDefault(e => e.EntityId == entityId);
            if (entity != null) RemoveEntity(entity);
        }

        /// <summary>
        /// Get placed entity at position with tolerance.
        /// </summary>
        public PlacedEntity GetEntityAt(GamePosition position, float tolerance = 0.8f)
        {
            foreach (var entity in PlacedEntities)
            {
                float dx = MathF.Abs(entity.Position.X - position.X);
                float dz = MathF.Abs(entity.Position.Z - position.Z);
                if (dx <= tolerance && dz <= tolerance)
                    return entity;
            }
            return null;
        }

        /// <summary>
        /// Get all entities within a range of a center point.
        /// </summary>
        public List<PlacedEntity> GetEntitiesInRange(GamePosition center, float range)
        {
            var result = new List<PlacedEntity>();
            float rangeSq = range * range;

            foreach (var entity in PlacedEntities)
            {
                if (entity.Position.HorizontalDistanceSquaredTo(center) <= rangeSq)
                    result.Add(entity);
            }
            return result;
        }

        // ====================================================================
        // Death Chests
        // ====================================================================

        /// <summary>
        /// Create a death chest at the given position.
        /// Matches Python spawn_death_chest().
        /// </summary>
        public DeathChest CreateDeathChest(GamePosition position, List<Dictionary<string, object>> richItems)
        {
            if (richItems == null || richItems.Count == 0) return null;

            var chest = new DeathChest(position, richItems, GameTime);
            DeathChests.Add(chest);
            return chest;
        }

        /// <summary>
        /// Get a death chest within interaction range.
        /// Matches Python get_nearby_death_chest().
        /// </summary>
        public DeathChest GetNearbyDeathChest(GamePosition position, float maxDistance = 1.5f)
        {
            foreach (var chest in DeathChests)
            {
                if (chest.Position.HorizontalDistanceTo(position) <= maxDistance)
                    return chest;
            }
            return null;
        }

        /// <summary>
        /// Remove a death chest (when emptied or despawned).
        /// </summary>
        public void RemoveDeathChest(DeathChest chest)
        {
            DeathChests.Remove(chest);
        }

        // ====================================================================
        // Update
        // ====================================================================

        /// <summary>
        /// Update world state: advance game time, update resource respawns.
        /// Matches Python WorldSystem.update(dt).
        /// </summary>
        public void Update(float dt)
        {
            GameTime += dt;

            foreach (var chunk in _loadedChunks.Values)
            {
                foreach (var resource in chunk.Resources)
                {
                    resource.Update(dt);
                }
            }
        }

        // ====================================================================
        // Chunk File Save/Load
        // ====================================================================

        /// <summary>
        /// Set the directory for per-chunk save files based on save name.
        /// </summary>
        public void SetChunkSaveDirectory(string saveName)
        {
            string baseName = Path.GetFileNameWithoutExtension(saveName);
            _chunkSaveDir = Path.Combine(GamePaths.GetSavePath(), $"{baseName}_chunks");
            Directory.CreateDirectory(_chunkSaveDir);
        }

        private string GetChunkFilePath(int cx, int cy)
        {
            if (string.IsNullOrEmpty(_chunkSaveDir))
            {
                _chunkSaveDir = Path.Combine(GamePaths.GetSavePath(), "chunks");
                Directory.CreateDirectory(_chunkSaveDir);
            }
            return Path.Combine(_chunkSaveDir, $"chunk_{cx}_{cy}.json");
        }

        private void SaveChunkToFile(Chunk chunk)
        {
            var saveData = chunk.GetSaveData();
            if (saveData == null) return;

            string path = GetChunkFilePath(chunk.ChunkX, chunk.ChunkY);
            try
            {
                string json = JsonConvert.SerializeObject(saveData, Formatting.Indented);
                File.WriteAllText(path, json);
            }
            catch (Exception e)
            {
                Console.WriteLine($"Warning: Failed to save chunk ({chunk.ChunkX}, {chunk.ChunkY}): {e.Message}");
            }
        }

        private Chunk LoadChunkFromFile(int cx, int cy)
        {
            string path = GetChunkFilePath(cx, cy);
            if (!File.Exists(path)) return null;

            try
            {
                string json = File.ReadAllText(path);
                var saveData = JsonConvert.DeserializeObject<Dictionary<string, object>>(json);

                // Generate the base chunk
                var chunk = new Chunk(cx, cy, biomeGenerator: _biomeGenerator);
                chunk.GenerateTiles();

                // Calculate elapsed time since unload
                float unloadTime = saveData.TryGetValue("unload_timestamp", out var ut)
                    ? Convert.ToSingle(ut) : 0f;
                float elapsed = MathF.Max(0f, GameTime - unloadTime);

                chunk.RestoreModifications(saveData, elapsed);
                return chunk;
            }
            catch (Exception e)
            {
                Console.WriteLine($"Warning: Failed to load chunk ({cx}, {cy}): {e.Message}");
                return null;
            }
        }

        // ====================================================================
        // Save/Load Integration
        // ====================================================================

        /// <summary>
        /// Get world state for saving. Saves all modified chunks to files.
        /// Matches Python get_save_state().
        /// </summary>
        public Dictionary<string, object> ToSaveData()
        {
            // Save all modified chunks to files
            foreach (var chunk in _loadedChunks.Values)
            {
                if (chunk.HasModifications())
                    SaveChunkToFile(chunk);
            }

            return new Dictionary<string, object>
            {
                ["seed"] = Seed,
                ["game_time"] = GameTime,
                ["placed_entities"] = PlacedEntities.Select(e => e.ToSaveData()).ToList(),
                ["crafting_stations"] = CraftingStations.Select(s => s.ToSaveData()).ToList(),
                ["discovered_dungeons"] = SerializeDiscoveredDungeons(),
                ["death_chests"] = DeathChests.Select(c => c.ToSaveData()).ToList(),
            };
        }

        /// <summary>
        /// Restore world state from save data.
        /// Matches Python restore_from_save().
        /// </summary>
        public void FromSaveData(Dictionary<string, object> data)
        {
            GameTime = data.TryGetValue("game_time", out var gt) ? Convert.ToSingle(gt) : 0f;

            // Restore placed entities
            PlacedEntities.Clear();
            _barrierPositions.Clear();

            if (data.TryGetValue("placed_entities", out var entitiesObj) && entitiesObj is IEnumerable<object> entityList)
            {
                foreach (var item in entityList)
                {
                    if (item is Dictionary<string, object> entityData)
                    {
                        var entity = PlacedEntity.FromSaveData(entityData);
                        PlacedEntities.Add(entity);

                        if (entity.EntityType == PlacedEntityType.Barrier)
                            _barrierPositions.Add(((int)entity.Position.X, (int)entity.Position.Z));
                    }
                }
            }

            // Restore crafting stations
            if (data.TryGetValue("crafting_stations", out var stationsObj) && stationsObj is IEnumerable<object> stationList)
            {
                CraftingStations.Clear();
                foreach (var item in stationList)
                {
                    if (item is Dictionary<string, object> stationData)
                    {
                        CraftingStations.Add(CraftingStationInstance.FromSaveData(stationData));
                    }
                }
            }

            // Restore discovered dungeons
            DiscoveredDungeonEntrances.Clear();
            if (data.TryGetValue("discovered_dungeons", out var dungeonsObj) && dungeonsObj is IEnumerable<object> dungeonList)
            {
                foreach (var item in dungeonList)
                {
                    if (item is Dictionary<string, object> dungeonData)
                    {
                        int dcx = Convert.ToInt32(dungeonData["chunk_x"]);
                        int dcy = Convert.ToInt32(dungeonData["chunk_y"]);

                        var posDict = dungeonData["position"] as Dictionary<string, object>;
                        var pos = new GamePosition(
                            Convert.ToSingle(posDict["x"]),
                            Convert.ToSingle(posDict["y"]),
                            Convert.ToSingle(posDict["z"]));

                        string rarityStr = dungeonData.TryGetValue("rarity", out var r) ? r?.ToString() : "common";
                        if (!Enum.TryParse<DungeonRarity>(rarityStr, true, out var rarity))
                            rarity = DungeonRarity.Common;

                        var entrance = new DungeonEntrance { Position = pos, Rarity = rarity };
                        DiscoveredDungeonEntrances[(dcx, dcy)] = entrance;

                        // Update loaded chunk if it exists
                        if (_loadedChunks.TryGetValue((dcx, dcy), out var chunk))
                            chunk.DungeonEntrance = entrance;
                    }
                }
            }

            // Restore death chests
            DeathChests.Clear();
            if (data.TryGetValue("death_chests", out var chestsObj) && chestsObj is IEnumerable<object> chestList)
            {
                foreach (var item in chestList)
                {
                    if (item is Dictionary<string, object> chestData)
                        DeathChests.Add(DeathChest.FromSaveData(chestData));
                }
            }
        }

        private List<Dictionary<string, object>> SerializeDiscoveredDungeons()
        {
            var list = new List<Dictionary<string, object>>();
            foreach (var ((cx, cy), entrance) in DiscoveredDungeonEntrances)
            {
                list.Add(new Dictionary<string, object>
                {
                    ["chunk_x"] = cx,
                    ["chunk_y"] = cy,
                    ["position"] = new Dictionary<string, object>
                    {
                        ["x"] = entrance.Position.X,
                        ["y"] = entrance.Position.Y,
                        ["z"] = entrance.Position.Z,
                    },
                    ["rarity"] = entrance.Rarity.ToString().ToLowerInvariant(),
                });
            }
            return list;
        }

        // ====================================================================
        // Legacy Compatibility Properties
        // ====================================================================

        /// <summary>
        /// Get all resources across all loaded chunks.
        /// Prefer GetResourceAt() or per-chunk access for efficiency.
        /// </summary>
        public List<NaturalResourceInstance> AllResources
        {
            get
            {
                var all = new List<NaturalResourceInstance>();
                foreach (var chunk in _loadedChunks.Values)
                    all.AddRange(chunk.Resources);
                return all;
            }
        }

        /// <summary>
        /// Get all dungeon entrances.
        /// </summary>
        public List<DungeonEntrance> AllDungeonEntrances =>
            new List<DungeonEntrance>(DiscoveredDungeonEntrances.Values);
    }
}
