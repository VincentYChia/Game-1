// ============================================================================
// Game1.Systems.World.CollisionSystem
// Migrated from: systems/collision_system.py (600 lines)
// Migration phase: 4
// Date: 2026-02-13
//
// Collision detection, line-of-sight checking (Bresenham), and A* pathfinding.
// IPathfinder interface allows Grid A* now, NavMesh later.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;

namespace Game1.Systems.World
{
    // ========================================================================
    // Enums and Result Types
    // ========================================================================

    /// <summary>
    /// Types of collisions that can occur. Matches Python CollisionType enum.
    /// </summary>
    public enum CollisionType
    {
        None,
        Tile,
        Resource,
        Barrier,
        Entity
    }

    /// <summary>
    /// Result of a collision or line-of-sight check.
    /// Matches Python CollisionResult dataclass.
    /// </summary>
    public class CollisionResult
    {
        public bool Blocked { get; set; }
        public CollisionType Type { get; set; } = CollisionType.None;
        public (float x, float z)? CollisionPosition { get; set; }
        public object CollisionObject { get; set; }
        public float DistanceToCollision { get; set; } = float.MaxValue;

        /// <summary>Unblocked result (static instance for common case).</summary>
        public static CollisionResult Unblocked => new CollisionResult { Blocked = false };
    }

    // ========================================================================
    // IPathfinder Interface
    // ========================================================================

    /// <summary>
    /// Pathfinding interface. Grid A* now, NavMesh later -- no logic changes.
    /// Matches Migration-Plan MACRO-7 specification.
    /// </summary>
    public interface IPathfinder
    {
        /// <summary>
        /// Find a path from start to goal tile coordinates.
        /// Returns list of (x, z) waypoints, or null if no path found.
        /// </summary>
        List<(float x, float z)> FindPath(
            int startX, int startZ,
            int endX, int endZ,
            int maxSteps = 200);
    }

    // ========================================================================
    // A* PathNode
    // ========================================================================

    /// <summary>
    /// Node for A* pathfinding. Matches Python PathNode dataclass.
    /// </summary>
    internal class PathNode : IComparable<PathNode>
    {
        public int X { get; }
        public int Z { get; }
        public float GCost { get; set; }
        public float HCost { get; set; }
        public PathNode Parent { get; set; }

        public float FCost => GCost + HCost;

        public PathNode(int x, int z)
        {
            X = x;
            Z = z;
        }

        public int CompareTo(PathNode other)
        {
            int cmp = FCost.CompareTo(other.FCost);
            if (cmp != 0) return cmp;
            return HCost.CompareTo(other.HCost);
        }

        public override bool Equals(object obj) =>
            obj is PathNode other && X == other.X && Z == other.Z;

        public override int GetHashCode() => HashCode.Combine(X, Z);
    }

    // ========================================================================
    // GridPathfinder
    // ========================================================================

    /// <summary>
    /// A* pathfinding on the tile grid. 8-directional movement.
    /// Diagonal cost: 1.414, cardinal cost: 1.0.
    /// Heuristic: octile distance (max(dx,dy) + 0.414 * min(dx,dy)).
    /// Matches Python CollisionSystem.find_path() exactly.
    /// </summary>
    public class GridPathfinder : IPathfinder
    {
        private readonly WorldSystem _world;

        // 8-directional neighbors: 4 cardinal + 4 diagonal
        private static readonly (int dx, int dz)[] Neighbors =
        {
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        };

        public GridPathfinder(WorldSystem world)
        {
            _world = world ?? throw new ArgumentNullException(nameof(world));
        }

        public List<(float x, float z)> FindPath(int startX, int startZ, int endX, int endZ, int maxSteps = 200)
        {
            // Quick check: if goal is unwalkable, find nearest walkable
            if (!IsWalkable(endX, endZ))
            {
                var nearest = FindNearestWalkable(endX, endZ);
                if (nearest == null) return null;
                endX = nearest.Value.x;
                endZ = nearest.Value.z;
            }

            var startNode = new PathNode(startX, startZ)
            {
                HCost = Heuristic(startX, startZ, endX, endZ)
            };

            // Priority queue via sorted list (SortedSet does not allow duplicates by FCost)
            var openList = new List<PathNode> { startNode };
            var closedSet = new HashSet<(int, int)>();
            var openDict = new Dictionary<(int, int), PathNode> { [(startX, startZ)] = startNode };

            int iterations = 0;

            while (openList.Count > 0 && iterations < maxSteps)
            {
                iterations++;

                // Find lowest FCost node
                int bestIdx = 0;
                for (int i = 1; i < openList.Count; i++)
                {
                    if (openList[i].FCost < openList[bestIdx].FCost)
                        bestIdx = i;
                }

                var current = openList[bestIdx];
                openList.RemoveAt(bestIdx);
                var currentKey = (current.X, current.Z);

                if (closedSet.Contains(currentKey))
                    continue;

                // Reached goal
                if (current.X == endX && current.Z == endZ)
                {
                    return ReconstructPath(current);
                }

                closedSet.Add(currentKey);

                // Explore 8 neighbors
                foreach (var (dx, dz) in Neighbors)
                {
                    int nx = current.X + dx;
                    int nz = current.Z + dz;
                    var neighborKey = (nx, nz);

                    if (closedSet.Contains(neighborKey)) continue;
                    if (!IsWalkable(nx, nz)) continue;

                    // Diagonal movement: ensure not cutting corners
                    if (dx != 0 && dz != 0)
                    {
                        if (!IsWalkable(current.X + dx, current.Z)) continue;
                        if (!IsWalkable(current.X, current.Z + dz)) continue;
                    }

                    float moveCost = (dx != 0 && dz != 0) ? 1.414f : 1.0f;
                    float newG = current.GCost + moveCost;

                    if (openDict.TryGetValue(neighborKey, out var existing) && newG >= existing.GCost)
                        continue;

                    var neighbor = new PathNode(nx, nz)
                    {
                        GCost = newG,
                        HCost = Heuristic(nx, nz, endX, endZ),
                        Parent = current
                    };

                    openList.Add(neighbor);
                    openDict[neighborKey] = neighbor;
                }
            }

            return null; // No path found
        }

        /// <summary>
        /// Octile distance heuristic for 8-way movement.
        /// Matches Python _heuristic() exactly.
        /// </summary>
        private static float Heuristic(int x1, int z1, int x2, int z2)
        {
            int dx = Math.Abs(x2 - x1);
            int dz = Math.Abs(z2 - z1);
            return Math.Max(dx, dz) + 0.414f * Math.Min(dx, dz);
        }

        private bool IsWalkable(int x, int z)
        {
            return _world.IsWalkable(GamePosition.FromXZ(x, z));
        }

        private List<(float x, float z)> ReconstructPath(PathNode node)
        {
            var path = new List<(float, float)>();
            var current = node;
            while (current != null)
            {
                // Center of tile: +0.5
                path.Add((current.X + 0.5f, current.Z + 0.5f));
                current = current.Parent;
            }
            path.Reverse();
            return path;
        }

        private (int x, int z)? FindNearestWalkable(int x, int z)
        {
            for (int radius = 1; radius < 5; radius++)
            {
                (int x, int z)? bestTile = null;
                float bestDist = float.MaxValue;

                for (int dx = -radius; dx <= radius; dx++)
                {
                    for (int dz = -radius; dz <= radius; dz++)
                    {
                        if (Math.Abs(dx) != radius && Math.Abs(dz) != radius) continue;

                        int nx = x + dx;
                        int nz = z + dz;
                        if (IsWalkable(nx, nz))
                        {
                            float dist = MathF.Sqrt(dx * dx + dz * dz);
                            if (dist < bestDist)
                            {
                                bestDist = dist;
                                bestTile = (nx, nz);
                            }
                        }
                    }
                }

                if (bestTile.HasValue) return bestTile;
            }
            return null;
        }
    }

    // ========================================================================
    // CollisionSystem
    // ========================================================================

    /// <summary>
    /// Central collision and line-of-sight system.
    /// Handles Bresenham LoS checks, movement collision with wall sliding,
    /// and provides pathfinder access.
    ///
    /// Matches Python CollisionSystem class (600 lines).
    /// </summary>
    public class CollisionSystem
    {
        private WorldSystem _world;
        private IPathfinder _pathfinder;

        // Collision cache (cleared on world changes)
        private readonly Dictionary<string, List<(float, float)>> _pathCache = new();

        /// <summary>Tags that bypass line-of-sight checks (AoE effects).</summary>
        public static readonly HashSet<string> BypassLosTags = new() { "circle", "aoe", "ground" };

        /// <summary>Tags that pass through obstacles (future: ethereal, ghost).</summary>
        public static readonly HashSet<string> PassthroughTags = new();

        public CollisionSystem() { }

        public CollisionSystem(WorldSystem world)
        {
            _world = world;
            _pathfinder = new GridPathfinder(world);
        }

        public void SetWorldSystem(WorldSystem world)
        {
            _world = world;
            _pathfinder = new GridPathfinder(world);
            InvalidateCache();
        }

        public void InvalidateCache()
        {
            _pathCache.Clear();
        }

        // ====================================================================
        // Line-of-Sight
        // ====================================================================

        /// <summary>
        /// Check if there is clear line of sight between source and target.
        /// Uses Bresenham's line algorithm. Skips source and target tiles.
        /// Matches Python has_line_of_sight() exactly.
        /// </summary>
        public CollisionResult HasLineOfSight(
            (float x, float z) source,
            (float x, float z) target,
            List<string> attackTags = null,
            bool checkResources = true,
            bool checkBarriers = true,
            bool checkTiles = true)
        {
            if (_world == null) return CollisionResult.Unblocked;

            // Check if attack bypasses LoS
            if (attackTags != null)
            {
                foreach (var tag in attackTags)
                {
                    if (BypassLosTags.Contains(tag) || PassthroughTags.Contains(tag))
                        return CollisionResult.Unblocked;
                }
            }

            // Get tiles along line via Bresenham
            var lineTiles = GetLineTiles(source, target);

            // Skip source (first) and target (last) tiles
            int start = lineTiles.Count > 2 ? 1 : 0;
            int end = lineTiles.Count > 2 ? lineTiles.Count - 1 : lineTiles.Count;

            for (int i = start; i < end; i++)
            {
                var (tx, tz) = lineTiles[i];
                var result = CheckTileCollision(tx, tz, checkResources, checkBarriers, checkTiles);
                if (result.Blocked)
                {
                    float dx = tx - source.x;
                    float dz = tz - source.z;
                    result.DistanceToCollision = MathF.Sqrt(dx * dx + dz * dz);
                    return result;
                }
            }

            return CollisionResult.Unblocked;
        }

        /// <summary>
        /// Bresenham's line algorithm. Returns list of (x, z) tile coordinates.
        /// Matches Python _get_line_tiles() exactly.
        /// </summary>
        private List<(int x, int z)> GetLineTiles((float x, float z) source, (float x, float z) target)
        {
            int x0 = (int)MathF.Floor(source.x);
            int z0 = (int)MathF.Floor(source.z);
            int x1 = (int)MathF.Floor(target.x);
            int z1 = (int)MathF.Floor(target.z);

            var tiles = new List<(int, int)>();

            int dx = Math.Abs(x1 - x0);
            int dz = Math.Abs(z1 - z0);
            int sx = x0 < x1 ? 1 : -1;
            int sz = z0 < z1 ? 1 : -1;
            int err = dx - dz;

            while (true)
            {
                tiles.Add((x0, z0));

                if (x0 == x1 && z0 == z1) break;

                int e2 = 2 * err;
                if (e2 > -dz)
                {
                    err -= dz;
                    x0 += sx;
                }
                if (e2 < dx)
                {
                    err += dx;
                    z0 += sz;
                }
            }

            return tiles;
        }

        /// <summary>
        /// Check if a specific tile blocks line of sight.
        /// Matches Python _check_tile_collision().
        /// </summary>
        private CollisionResult CheckTileCollision(int x, int z,
            bool checkResources, bool checkBarriers, bool checkTiles)
        {
            var pos = GamePosition.FromXZ(x, z);

            // Check non-walkable tiles
            if (checkTiles)
            {
                var tile = _world.GetTile(pos);
                if (tile != null && !tile.Walkable)
                {
                    return new CollisionResult
                    {
                        Blocked = true,
                        Type = CollisionType.Tile,
                        CollisionPosition = (x, z),
                        CollisionObject = tile,
                    };
                }
            }

            // Check resources
            if (checkResources)
            {
                var resource = _world.GetResourceAt(pos, tolerance: 0.5f);
                if (resource != null && !resource.IsDepleted)
                {
                    return new CollisionResult
                    {
                        Blocked = true,
                        Type = CollisionType.Resource,
                        CollisionPosition = (x, z),
                        CollisionObject = resource,
                    };
                }
            }

            // Check barriers
            if (checkBarriers)
            {
                var entity = _world.GetEntityAt(pos);
                if (entity != null && entity.EntityType == PlacedEntityType.Barrier)
                {
                    return new CollisionResult
                    {
                        Blocked = true,
                        Type = CollisionType.Barrier,
                        CollisionPosition = (x, z),
                        CollisionObject = entity,
                    };
                }
            }

            return CollisionResult.Unblocked;
        }

        // ====================================================================
        // Movement Collision
        // ====================================================================

        /// <summary>
        /// Check if a position is walkable (for movement).
        /// Matches Python is_position_walkable().
        /// </summary>
        public bool CanMoveTo(float x, float z)
        {
            return _world != null && _world.IsWalkable(GamePosition.FromXZ(x, z));
        }

        /// <summary>
        /// Check movement with wall sliding. If diagonal is blocked, tries
        /// X-only then Z-only movement.
        /// Matches Python can_move_to().
        /// Returns (canMove, finalX, finalZ).
        /// </summary>
        public (bool canMove, float finalX, float finalZ) CheckMovement(
            GamePosition from, GamePosition to)
        {
            // Direct movement
            if (CanMoveTo(to.X, to.Z))
                return (true, to.X, to.Z);

            // X-only slide
            if (from.X != to.X && CanMoveTo(to.X, from.Z))
                return (true, to.X, from.Z);

            // Z-only slide
            if (from.Z != to.Z && CanMoveTo(from.X, to.Z))
                return (true, from.X, to.Z);

            // Cannot move
            return (false, from.X, from.Z);
        }

        // ====================================================================
        // Pathfinding Delegation
        // ====================================================================

        /// <summary>
        /// Find a path from start to goal using the current IPathfinder implementation.
        /// </summary>
        public List<(float x, float z)> FindPath(
            (float x, float z) start,
            (float x, float z) goal,
            int maxSteps = 200)
        {
            if (_pathfinder == null) return null;

            int sx = (int)MathF.Floor(start.x);
            int sz = (int)MathF.Floor(start.z);
            int gx = (int)MathF.Floor(goal.x);
            int gz = (int)MathF.Floor(goal.z);

            // Check cache
            string cacheKey = $"{sx},{sz}->{gx},{gz}";
            if (_pathCache.TryGetValue(cacheKey, out var cached))
                return cached;

            var path = _pathfinder.FindPath(sx, sz, gx, gz, maxSteps);

            if (path != null && path.Count <= 50)
                _pathCache[cacheKey] = path;

            return path;
        }

        /// <summary>
        /// Get the next step toward a goal (for simple one-step movement).
        /// </summary>
        public (float x, float z)? GetNextStep(
            (float x, float z) current,
            (float x, float z) goal)
        {
            var path = FindPath(current, goal, maxSteps: 100);
            if (path != null && path.Count > 1)
                return path[1];
            return null;
        }
    }
}
