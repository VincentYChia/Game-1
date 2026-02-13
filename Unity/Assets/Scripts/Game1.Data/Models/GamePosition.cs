// ============================================================================
// Game1.Data.Models.GamePosition
// Migrated from: data/models/world.py (Position class)
// Migration phase: 1 (MACRO-6)
// Date: 2026-02-13
// ============================================================================

using System;

namespace Game1.Data.Models
{
    /// <summary>
    /// Pure C# struct representing a position in 3D space.
    /// No Unity dependency (no Vector3). Uses System.Math for calculations.
    ///
    /// Convention: X = East-West, Y = Height (0 for flat world), Z = North-South.
    /// Python (x, y) maps to C# (X, 0, Z).
    /// </summary>
    public struct GamePosition : IEquatable<GamePosition>
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }

        public GamePosition(float x, float y, float z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        // ====================================================================
        // Factory Methods
        // ====================================================================

        /// <summary>
        /// Create a position from XZ coordinates with Y=0 (ground level).
        /// Use for converting Python 2D (x, y) positions: FromXZ(pythonX, pythonY).
        /// </summary>
        public static GamePosition FromXZ(float x, float z)
        {
            return new GamePosition(x, 0f, z);
        }

        /// <summary>The origin (0, 0, 0).</summary>
        public static GamePosition Zero => new GamePosition(0f, 0f, 0f);

        // ====================================================================
        // Distance Methods
        // ====================================================================

        /// <summary>
        /// Horizontal distance (XZ plane only, ignoring height).
        /// Use this for most game logic during 2D-parity mode.
        /// Matches Python: math.sqrt((x2-x1)^2 + (y2-y1)^2)
        /// </summary>
        public float HorizontalDistanceTo(GamePosition other)
        {
            float dx = X - other.X;
            float dz = Z - other.Z;
            return MathF.Sqrt(dx * dx + dz * dz);
        }

        /// <summary>
        /// Full 3D distance including height difference.
        /// Use when vertical gameplay matters (flying enemies, projectiles).
        /// </summary>
        public float DistanceTo(GamePosition other)
        {
            float dx = X - other.X;
            float dy = Y - other.Y;
            float dz = Z - other.Z;
            return MathF.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        /// <summary>
        /// Squared horizontal distance (avoids sqrt, useful for range checks).
        /// </summary>
        public float HorizontalDistanceSquaredTo(GamePosition other)
        {
            float dx = X - other.X;
            float dz = Z - other.Z;
            return dx * dx + dz * dz;
        }

        // ====================================================================
        // Operator Overloads
        // ====================================================================

        public static GamePosition operator +(GamePosition a, GamePosition b)
        {
            return new GamePosition(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        }

        public static GamePosition operator -(GamePosition a, GamePosition b)
        {
            return new GamePosition(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        }

        public static GamePosition operator *(GamePosition a, float scalar)
        {
            return new GamePosition(a.X * scalar, a.Y * scalar, a.Z * scalar);
        }

        public static GamePosition operator *(float scalar, GamePosition a)
        {
            return a * scalar;
        }

        public static bool operator ==(GamePosition a, GamePosition b)
        {
            return a.Equals(b);
        }

        public static bool operator !=(GamePosition a, GamePosition b)
        {
            return !a.Equals(b);
        }

        // ====================================================================
        // Equality
        // ====================================================================

        public bool Equals(GamePosition other)
        {
            const float epsilon = 0.0001f;
            return MathF.Abs(X - other.X) < epsilon &&
                   MathF.Abs(Y - other.Y) < epsilon &&
                   MathF.Abs(Z - other.Z) < epsilon;
        }

        public override bool Equals(object obj)
        {
            return obj is GamePosition other && Equals(other);
        }

        public override int GetHashCode()
        {
            return HashCode.Combine(X, Y, Z);
        }

        public override string ToString()
        {
            return $"({X:F2}, {Y:F2}, {Z:F2})";
        }
    }
}
