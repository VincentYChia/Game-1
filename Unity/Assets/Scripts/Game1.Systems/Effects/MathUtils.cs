// Game1.Systems.Effects.MathUtils
// Migrated from: core/geometry/math_utils.py (113 lines)
// Migration phase: 4
//
// Pure static math utility class for geometry calculations.
// Uses GamePosition struct (pure C#). No UnityEngine dependency.
// All distance calculations use horizontal (XZ-plane) by default
// to match Python 2D behavior.

using System;
using Game1.Data.Models;

namespace Game1.Systems.Effects
{
    /// <summary>
    /// Static math utilities for effect geometry calculations.
    /// Provides distance, angle, direction, and shape-test functions
    /// used by TargetFinder and EffectExecutor.
    /// </summary>
    public static class MathUtils
    {
        /// <summary>Degrees-to-radians conversion factor.</summary>
        private const float Deg2Rad = MathF.PI / 180f;

        /// <summary>Radians-to-degrees conversion factor.</summary>
        private const float Rad2Deg = 180f / MathF.PI;

        /// <summary>
        /// Calculate horizontal distance between two positions (XZ-plane).
        /// Matches Python: pos1.distance_to(pos2) which is effectively 2D.
        /// </summary>
        public static float Distance(GamePosition a, GamePosition b)
        {
            return a.HorizontalDistanceTo(b);
        }

        /// <summary>
        /// Normalize a 2D vector (dx, dz).
        /// Returns (0, 0) if the vector has zero length.
        /// </summary>
        public static (float dx, float dz) NormalizeVector(float dx, float dz)
        {
            float length = MathF.Sqrt(dx * dx + dz * dz);
            if (length == 0f)
                return (0f, 0f);
            return (dx / length, dz / length);
        }

        /// <summary>
        /// Calculate dot product of two 2D vectors.
        /// </summary>
        public static float DotProduct((float x, float z) v1, (float x, float z) v2)
        {
            return v1.x * v2.x + v1.z * v2.z;
        }

        /// <summary>
        /// Calculate angle between two normalized vectors in degrees.
        /// Returns value between 0 and 180.
        /// Clamps the dot product to [-1, 1] to avoid NaN from Acos.
        /// </summary>
        public static float AngleBetweenVectors((float x, float z) v1, (float x, float z) v2)
        {
            float dot = DotProduct(v1, v2);
            // Clamp to avoid numerical errors with Acos
            dot = Math.Clamp(dot, -1f, 1f);
            float angleRad = MathF.Acos(dot);
            return angleRad * Rad2Deg;
        }

        /// <summary>
        /// Get normalized direction vector from one position to another (XZ-plane).
        /// Returns (0, 0) if positions are identical.
        /// </summary>
        public static (float dx, float dz) DirectionVector(GamePosition from, GamePosition to)
        {
            float dx = to.X - from.X;
            float dz = to.Z - from.Z;
            return NormalizeVector(dx, dz);
        }

        /// <summary>
        /// Check if a target position is inside a cone.
        /// coneAngle is the TOTAL angle of the cone in degrees;
        /// the test uses halfAngle = coneAngle / 2.
        /// </summary>
        /// <param name="source">Origin of the cone.</param>
        /// <param name="facing">Normalized direction the cone faces (dx, dz).</param>
        /// <param name="target">Position to test.</param>
        /// <param name="coneAngle">Total cone angle in degrees.</param>
        /// <param name="coneRange">Maximum range of the cone.</param>
        /// <returns>True if target is within the cone.</returns>
        public static bool IsInCone(GamePosition source, (float dx, float dz) facing,
                                     GamePosition target, float coneAngle, float coneRange)
        {
            // Check range first
            float dist = Distance(source, target);
            if (dist > coneRange)
                return false;

            // Avoid division by zero for coincident points
            if (dist < 0.0001f)
                return true;

            // Check angle
            var toTarget = DirectionVector(source, target);
            float angle = AngleBetweenVectors(facing, toTarget);

            // Cone angle is total angle, so half-angle for each side
            float halfAngle = coneAngle / 2f;

            return angle <= halfAngle;
        }

        /// <summary>
        /// Check if a target position is inside a circle (XZ-plane).
        /// </summary>
        public static bool IsInCircle(GamePosition center, GamePosition target, float radius)
        {
            return Distance(center, target) <= radius;
        }

        /// <summary>
        /// Get facing direction vector from source toward target (XZ-plane).
        /// Convenience wrapper around DirectionVector.
        /// </summary>
        public static (float dx, float dz) GetFacingFromTarget(GamePosition source, GamePosition target)
        {
            return DirectionVector(source, target);
        }

        /// <summary>
        /// Estimate facing direction for an entity by checking common properties.
        /// Tries: LastMoveDirection property, then falls back to (1, 0) (facing East).
        ///
        /// Uses duck typing via reflection since entity types are not known at this layer.
        /// </summary>
        public static (float dx, float dz) EstimateFacingDirection(object source)
        {
            if (source == null)
                return (1f, 0f);

            // Try last_move_direction / LastMoveDirection property
            var type = source.GetType();

            // Check for a LastMoveDirection property returning a tuple-like or array
            var prop = type.GetProperty("LastMoveDirection");
            if (prop != null)
            {
                object val = prop.GetValue(source);
                if (val != null)
                {
                    var dirResult = _extractDirection(val);
                    if (dirResult.HasValue)
                    {
                        var (dx, dz) = dirResult.Value;
                        if (dx != 0f || dz != 0f)
                            return NormalizeVector(dx, dz);
                    }
                }
            }

            // Try Velocity property
            var velProp = type.GetProperty("Velocity");
            if (velProp != null)
            {
                object vel = velProp.GetValue(source);
                if (vel != null)
                {
                    var dirResult = _extractDirection(vel);
                    if (dirResult.HasValue)
                    {
                        var (dx, dz) = dirResult.Value;
                        if (dx != 0f || dz != 0f)
                            return NormalizeVector(dx, dz);
                    }
                }
            }

            // Default facing right (East)
            return (1f, 0f);
        }

        /// <summary>
        /// Try to extract a 2D direction from an object.
        /// Handles GamePosition, value tuples, arrays, and objects with X/Z properties.
        /// </summary>
        private static (float dx, float dz)? _extractDirection(object val)
        {
            if (val is GamePosition gp)
                return (gp.X, gp.Z);

            if (val is ValueTuple<float, float> tuple)
                return tuple;

            if (val is float[] arr && arr.Length >= 2)
                return (arr[0], arr[1]);

            // Check for X and Z properties via reflection
            var valType = val.GetType();
            var xProp = valType.GetProperty("X");
            var zProp = valType.GetProperty("Z");
            if (xProp != null && zProp != null)
            {
                try
                {
                    float x = Convert.ToSingle(xProp.GetValue(val));
                    float z = Convert.ToSingle(zProp.GetValue(val));
                    return (x, z);
                }
                catch
                {
                    // Ignore conversion failures
                }
            }

            return null;
        }
    }
}
