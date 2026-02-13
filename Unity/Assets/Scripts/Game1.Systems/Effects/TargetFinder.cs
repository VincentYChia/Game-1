// Game1.Systems.Effects.TargetFinder
// Migrated from: core/geometry/target_finder.py (436 lines)
// Migration phase: 4
//
// Geometry-based target selection for the tag effect system.
// Finds targets based on geometry tags (single, chain, cone, circle, beam, pierce).
// Uses GamePosition and MathUtils for spatial calculations.
// No UnityEngine dependency.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using Game1.Data.Models;

namespace Game1.Systems.Effects
{
    /// <summary>
    /// Controls whether distance calculations use horizontal-only (XZ) or full 3D.
    /// All game logic starts with Horizontal for Python parity.
    /// Switch to Full3D when height gameplay is introduced.
    /// </summary>
    public enum DistanceMode
    {
        Horizontal,
        Full3D
    }

    /// <summary>
    /// Finds targets for effects based on geometry and context.
    /// Dispatches to specialized methods for each geometry type:
    /// single, chain, cone, circle/aoe, beam/line, pierce.
    /// Handles context flipping for enemy sources.
    /// </summary>
    public class TargetFinder
    {
        /// <summary>
        /// Global distance mode. Default Horizontal (XZ-plane) for Python parity.
        /// </summary>
        public static DistanceMode Mode { get; set; } = DistanceMode.Horizontal;

        /// <summary>Optional logging delegate. Set to route warnings/debug to your logging system.</summary>
        public static Action<string> LogWarning { get; set; }

        /// <summary>
        /// Get distance between two positions using the current DistanceMode.
        /// </summary>
        public static float GetDistance(GamePosition a, GamePosition b)
        {
            return Mode == DistanceMode.Full3D
                ? a.DistanceTo(b)
                : a.HorizontalDistanceTo(b);
        }

        /// <summary>
        /// Find all targets based on geometry, source, primary target, params, and context.
        /// Main dispatch entry point.
        /// </summary>
        /// <param name="geometry">Geometry tag (single_target, chain, cone, circle, aoe, beam, line, pierce).</param>
        /// <param name="source">Source entity (caster/turret).</param>
        /// <param name="target">Primary target entity.</param>
        /// <param name="parms">Effect parameters (chain_count, cone_angle, radius, etc.).</param>
        /// <param name="context">Context filter (enemy, ally, self, all).</param>
        /// <param name="entities">All entities available for targeting.</param>
        /// <returns>List of target entities.</returns>
        public List<object> FindTargets(string geometry, object source, object target,
                                         Dictionary<string, object> parms, string context,
                                         List<object> entities)
        {
            if (parms == null) parms = new Dictionary<string, object>();
            if (entities == null) entities = new List<object>();

            // Handle 'self' context - always targets the source entity
            if (context == "self")
            {
                return source != null ? new List<object> { source } : new List<object>();
            }

            // Flip context for enemy sources (relative targeting):
            // When an enemy uses damage abilities, they target "ally" (player/turrets from their perspective)
            // When an enemy uses healing/buffs, they target "enemy" (other enemies from their perspective)
            if (source != null && _isEnemy(source))
            {
                if (context == "enemy")
                    context = "ally";  // Enemy wants to target hostile entities = player/turrets
                else if (context == "ally")
                    context = "enemy";  // Enemy wants to target friendly entities = other enemies
            }

            switch (geometry)
            {
                case "single_target":
                case "single":
                    return _findSingleTarget(target, context);

                case "chain":
                    return _findChainTargets(
                        source, target,
                        _getInt(parms, "chain_count", 2),
                        _getFloat(parms, "chain_range", 5f),
                        context, entities
                    );

                case "cone":
                    return _findConeTargets(
                        source, target,
                        _getFloat(parms, "cone_angle", 60f),
                        _getFloat(parms, "cone_range", 8f),
                        context, entities
                    );

                case "circle":
                case "aoe":
                {
                    string originType = _getString(parms, "origin", "target");
                    GamePosition center;
                    if (originType == "source")
                        center = GetPosition(source);
                    else
                        center = GetPosition(target);

                    // Check circle_radius first, fallback to radius
                    float radius = parms.ContainsKey("circle_radius")
                        ? _getFloat(parms, "circle_radius", 3f)
                        : _getFloat(parms, "radius", 3f);

                    return _findCircleTargets(
                        center,
                        radius,
                        _getInt(parms, "max_targets", 0),
                        context, entities
                    );
                }

                case "beam":
                case "line":
                    return _findBeamTargets(
                        source, target,
                        _getFloat(parms, "beam_range", 10f),
                        _getFloat(parms, "beam_width", 0.5f),
                        _getInt(parms, "pierce_count", 0),
                        context, entities
                    );

                case "pierce":
                    return _findPierceTargets(
                        source, target,
                        _getFloat(parms, "pierce_range", 10f),
                        _getInt(parms, "pierce_count", 3),
                        _getFloat(parms, "pierce_width", 0.5f),
                        context, entities
                    );

                default:
                    LogWarning?.Invoke($"[TargetFinder] Unknown geometry: {geometry}, using single_target");
                    return _findSingleTarget(target, context);
            }
        }

        // ====================================================================
        // Geometry Methods
        // ====================================================================

        /// <summary>Single target - return the primary target if context-valid.</summary>
        private List<object> _findSingleTarget(object target, string context)
        {
            if (target != null && _isValidContext(target, context))
                return new List<object> { target };
            return new List<object>();
        }

        /// <summary>
        /// Chain targeting: start at primary, find nearest unvisited within chain_range,
        /// up to chain_count additional jumps.
        /// </summary>
        private List<object> _findChainTargets(object source, object initialTarget,
                                                int chainCount, float chainRange,
                                                string context, List<object> entities)
        {
            var targets = new List<object>();
            var hitSet = new HashSet<object>(ReferenceEqualityComparer.Instance);
            object currentTarget = initialTarget;

            // Add initial target
            if (initialTarget == null || !_isValidContext(initialTarget, context))
                return targets;

            targets.Add(initialTarget);
            hitSet.Add(initialTarget);

            // Chain jumps
            for (int jump = 0; jump < chainCount; jump++)
            {
                object nextTarget = _findNearestValidTarget(
                    currentTarget, chainRange, context, entities, hitSet
                );

                if (nextTarget == null)
                    break;

                targets.Add(nextTarget);
                hitSet.Add(nextTarget);
                currentTarget = nextTarget;
            }

            return targets;
        }

        /// <summary>
        /// Cone targeting: find all entities within cone_range that fall within
        /// cone_angle of the facing direction from source toward target.
        /// </summary>
        private List<object> _findConeTargets(object source, object primaryTarget,
                                               float coneAngle, float coneRange,
                                               string context, List<object> entities)
        {
            GamePosition sourcePos = GetPosition(source);

            // Determine cone facing direction
            (float dx, float dz) facing;
            if (primaryTarget != null)
            {
                GamePosition targetPos = GetPosition(primaryTarget);
                facing = MathUtils.GetFacingFromTarget(sourcePos, targetPos);
            }
            else
            {
                facing = MathUtils.EstimateFacingDirection(source);
            }

            var targets = new List<object>();
            foreach (object entity in entities)
            {
                if (!_isValidContext(entity, context))
                    continue;

                GamePosition entityPos = GetPosition(entity);
                if (MathUtils.IsInCone(sourcePos, facing, entityPos, coneAngle, coneRange))
                {
                    targets.Add(entity);
                }
            }

            return targets;
        }

        /// <summary>
        /// Circle/AoE targeting: find all entities within radius of center.
        /// Results sorted by distance (closest first). Optional max_targets limit.
        /// </summary>
        private List<object> _findCircleTargets(GamePosition center, float radius,
                                                 int maxTargets, string context,
                                                 List<object> entities)
        {
            var targetsWithDist = new List<(object entity, float dist)>();

            foreach (object entity in entities)
            {
                if (!_isValidContext(entity, context))
                    continue;

                GamePosition entityPos = GetPosition(entity);
                if (MathUtils.IsInCircle(center, entityPos, radius))
                {
                    float dist = MathUtils.Distance(center, entityPos);
                    targetsWithDist.Add((entity, dist));
                }
            }

            // Sort by distance (closest first)
            targetsWithDist.Sort((a, b) => a.dist.CompareTo(b.dist));

            // Apply max_targets limit (0 = unlimited)
            if (maxTargets > 0 && targetsWithDist.Count > maxTargets)
            {
                targetsWithDist.RemoveRange(maxTargets, targetsWithDist.Count - maxTargets);
            }

            var result = new List<object>();
            foreach (var (entity, _) in targetsWithDist)
            {
                result.Add(entity);
            }
            return result;
        }

        /// <summary>
        /// Beam/line targeting: find entities along a line from source toward target.
        /// Entities within beam_width/2 perpendicular distance and within beam_range
        /// are hit. Results sorted by distance along beam. pierce_count limits hits
        /// (0 = first only, -1 = infinite).
        /// </summary>
        private List<object> _findBeamTargets(object source, object primaryTarget,
                                               float beamRange, float beamWidth,
                                               int pierceCount, string context,
                                               List<object> entities)
        {
            GamePosition sourcePos = GetPosition(source);
            GamePosition targetPos = GetPosition(primaryTarget);
            var beamDirection = MathUtils.DirectionVector(sourcePos, targetPos);

            var targetsWithDist = new List<(object entity, float distAlong)>();

            foreach (object entity in entities)
            {
                if (!_isValidContext(entity, context))
                    continue;

                GamePosition entityPos = GetPosition(entity);

                // Check if entity is along the beam line
                float distAlongBeam = _distanceAlongLine(sourcePos, beamDirection, entityPos);

                if (distAlongBeam < 0 || distAlongBeam > beamRange)
                    continue;

                // Check perpendicular distance (beam width)
                float perpDist = _perpendicularDistance(sourcePos, beamDirection, entityPos);

                if (perpDist <= beamWidth / 2f)
                {
                    targetsWithDist.Add((entity, distAlongBeam));
                }
            }

            // Sort by distance along beam
            targetsWithDist.Sort((a, b) => a.distAlong.CompareTo(b.distAlong));

            // Apply pierce limit (pierceCount >= 0 means limited; -1 means infinite)
            if (pierceCount >= 0 && targetsWithDist.Count > pierceCount + 1)
            {
                targetsWithDist.RemoveRange(pierceCount + 1, targetsWithDist.Count - (pierceCount + 1));
            }

            var result = new List<object>();
            foreach (var (entity, _) in targetsWithDist)
            {
                result.Add(entity);
            }
            return result;
        }

        /// <summary>
        /// Pierce targeting: ray through targets along direction from source to target.
        /// Similar to beam but uses pierce_count for total targets and pierce_width for width.
        /// </summary>
        private List<object> _findPierceTargets(object source, object primaryTarget,
                                                 float pierceRange, int pierceCount,
                                                 float pierceWidth, string context,
                                                 List<object> entities)
        {
            // Pierce uses the same logic as beam with pierce parameters
            return _findBeamTargets(source, primaryTarget, pierceRange, pierceWidth,
                                     pierceCount - 1, context, entities);
        }

        // ====================================================================
        // Helper Methods
        // ====================================================================

        /// <summary>
        /// Extract GamePosition from an entity.
        /// Handles: GamePosition directly, objects with a Position property (GamePosition or has X/Z),
        /// objects with X and Z properties directly.
        /// </summary>
        public static GamePosition GetPosition(object entity)
        {
            if (entity == null)
                return GamePosition.Zero;

            // If entity IS a GamePosition (boxed struct)
            if (entity is GamePosition gp)
                return gp;

            var type = entity.GetType();

            // Check for Position property
            var posProp = type.GetProperty("Position");
            if (posProp != null)
            {
                object posVal = posProp.GetValue(entity);
                if (posVal is GamePosition gpVal)
                    return gpVal;

                // Position object with X, Y, Z properties
                if (posVal != null)
                {
                    var posType = posVal.GetType();
                    var xProp = posType.GetProperty("X");
                    var zProp = posType.GetProperty("Z");
                    if (xProp != null && zProp != null)
                    {
                        float x = Convert.ToSingle(xProp.GetValue(posVal));
                        float z = Convert.ToSingle(zProp.GetValue(posVal));
                        float y = 0f;
                        var yProp = posType.GetProperty("Y");
                        if (yProp != null)
                            y = Convert.ToSingle(yProp.GetValue(posVal));
                        return new GamePosition(x, y, z);
                    }
                }
            }

            // Check for X and Z properties directly on entity
            var directX = type.GetProperty("X");
            var directZ = type.GetProperty("Z");
            if (directX != null && directZ != null)
            {
                float x = Convert.ToSingle(directX.GetValue(entity));
                float z = Convert.ToSingle(directZ.GetValue(entity));
                float y = 0f;
                var directY = type.GetProperty("Y");
                if (directY != null)
                    y = Convert.ToSingle(directY.GetValue(entity));
                return new GamePosition(x, y, z);
            }

            LogWarning?.Invoke($"[TargetFinder] Cannot get position from {type.Name}");
            return GamePosition.Zero;
        }

        /// <summary>
        /// Check if entity matches context filter.
        /// Context values: "all", "self", "enemy"/"hostile", "ally"/"friendly",
        /// "player", "turret"/"device", "construct", "undead", "mechanical".
        /// </summary>
        private bool _isValidContext(object entity, string context)
        {
            if (entity == null) return false;
            if (context == "all") return true;
            if (context == "self") return false; // Caller handles self-targeting

            // Check entity category/type
            string entityCategory = _getStringProp(entity, "Category");
            string entityTypeName = entity.GetType().Name.ToLowerInvariant();

            switch (context)
            {
                case "enemy":
                case "hostile":
                    // Enemy entities: have Definition and IsAlive, or type name contains "enemy",
                    // or category is beast/undead/construct/mechanical/elemental
                    if (_isEnemy(entity))
                        return true;
                    if (entityTypeName.Contains("enemy"))
                        return true;
                    if (entityCategory != null &&
                        (entityCategory == "beast" || entityCategory == "undead" ||
                         entityCategory == "construct" || entityCategory == "mechanical" ||
                         entityCategory == "elemental"))
                        return true;
                    return false;

                case "ally":
                case "friendly":
                    return entityTypeName == "character" ||
                           entityTypeName == "player" ||
                           entityTypeName == "placedentity" ||
                           entityTypeName.Contains("turret");

                case "player":
                    return entityTypeName == "character" || entityTypeName == "player";

                case "turret":
                case "device":
                    return entityTypeName == "placedentity" || entityTypeName.Contains("turret");

                case "construct":
                    return entityCategory == "construct";

                case "undead":
                    return entityCategory == "undead";

                case "mechanical":
                    return entityCategory == "mechanical";

                default:
                    // Unknown context - allow by default
                    return true;
            }
        }

        /// <summary>
        /// Check if an entity is an Enemy (has Definition and IsAlive properties).
        /// Mirrors Python: hasattr(source, 'definition') and hasattr(source, 'is_alive').
        /// </summary>
        private static bool _isEnemy(object entity)
        {
            if (entity == null) return false;
            var type = entity.GetType();
            return type.GetProperty("Definition") != null && type.GetProperty("IsAlive") != null;
        }

        /// <summary>
        /// Find nearest valid target from an entity within max_range, excluding already-hit entities.
        /// Used by chain targeting.
        /// </summary>
        private object _findNearestValidTarget(object fromEntity, float maxRange,
                                                string context, List<object> entities,
                                                HashSet<object> exclude)
        {
            GamePosition fromPos = GetPosition(fromEntity);
            object nearest = null;
            float nearestDist = float.MaxValue;

            foreach (object entity in entities)
            {
                if (exclude.Contains(entity))
                    continue;
                if (!_isValidContext(entity, context))
                    continue;

                GamePosition entityPos = GetPosition(entity);
                float dist = GetDistance(fromPos, entityPos);

                if (dist <= maxRange && dist < nearestDist)
                {
                    nearest = entity;
                    nearestDist = dist;
                }
            }

            return nearest;
        }

        /// <summary>
        /// Calculate distance along a line from start to the projection of a point onto the line.
        /// </summary>
        private float _distanceAlongLine(GamePosition lineStart, (float dx, float dz) lineDirection,
                                          GamePosition point)
        {
            // Vector from line start to point
            var toPoint = (x: point.X - lineStart.X, z: point.Z - lineStart.Z);
            return MathUtils.DotProduct(toPoint, lineDirection);
        }

        /// <summary>
        /// Calculate perpendicular distance from a point to a line.
        /// </summary>
        private float _perpendicularDistance(GamePosition lineStart, (float dx, float dz) lineDirection,
                                              GamePosition point)
        {
            float distAlong = _distanceAlongLine(lineStart, lineDirection, point);

            // Projection point on line
            float projX = lineStart.X + lineDirection.dx * distAlong;
            float projZ = lineStart.Z + lineDirection.dz * distAlong;

            // Distance from point to projection
            float dx = point.X - projX;
            float dz = point.Z - projZ;
            return MathF.Sqrt(dx * dx + dz * dz);
        }

        // ====================================================================
        // Parameter Extraction Helpers
        // ====================================================================

        private static float _getFloat(Dictionary<string, object> dict, string key, float defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return _convertToFloat(val, defaultValue);
        }

        private static int _getInt(Dictionary<string, object> dict, string key, int defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return _convertToInt(val, defaultValue);
        }

        private static string _getString(Dictionary<string, object> dict, string key, string defaultValue)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return defaultValue;
            return val?.ToString() ?? defaultValue;
        }

        private static float _convertToFloat(object val, float defaultValue)
        {
            if (val is float f) return f;
            if (val is double d) return (float)d;
            if (val is int i) return i;
            if (val is long l) return l;
            if (val is decimal dec) return (float)dec;
            if (val is string s && float.TryParse(s, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out float parsed))
                return parsed;
            return defaultValue;
        }

        private static int _convertToInt(object val, int defaultValue)
        {
            if (val is int i) return i;
            if (val is long l) return (int)l;
            if (val is float f) return (int)f;
            if (val is double d) return (int)d;
            if (val is decimal dec) return (int)dec;
            if (val is string s && int.TryParse(s, out int parsed))
                return parsed;
            return defaultValue;
        }

        /// <summary>
        /// Get a string property value from an entity via reflection.
        /// Returns null if the property doesn't exist or has a null value.
        /// </summary>
        private static string _getStringProp(object entity, string propName)
        {
            if (entity == null) return null;
            var prop = entity.GetType().GetProperty(propName);
            return prop?.GetValue(entity)?.ToString();
        }
    }
}
