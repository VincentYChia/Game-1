// Game1.Data.Models.GamePosition
// Migrated from: data/models/world.py Position class
// Phase: 1 - Foundation
// MACRO-6: GamePosition wrapping Vector3 for 3D-ready architecture

using System;
using Newtonsoft.Json;

namespace Game1.Data.Models
{
    /// <summary>
    /// 3D position in the game world. Wraps coordinates for 3D-ready architecture.
    /// Python (x,y) maps to Unity (x, 0, z) with height defaulting to 0.
    /// Uses MathF.Floor for grid snapping (NOT int cast) to handle negative coordinates correctly.
    /// </summary>
    [Serializable]
    public struct GamePosition : IEquatable<GamePosition>
    {
        [JsonProperty("x")]
        public float X { get; set; }

        [JsonProperty("y")]
        public float Y { get; set; }

        [JsonProperty("z")]
        public float Z { get; set; }

        public GamePosition(float x, float y, float z = 0f)
        {
            X = x;
            Y = y;
            Z = z;
        }

        /// <summary>
        /// Calculate 3D distance to another position.
        /// </summary>
        public float DistanceTo(GamePosition other)
        {
            float dx = X - other.X;
            float dy = Y - other.Y;
            float dz = Z - other.Z;
            return MathF.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        /// <summary>
        /// Snap position to integer grid coordinates.
        /// CRITICAL: Uses MathF.Floor(), NOT (int) cast.
        /// MathF.Floor(-0.5f) = -1.0f, but (int)(-0.5f) = 0.
        /// </summary>
        public GamePosition SnapToGrid()
        {
            return new GamePosition(MathF.Floor(X), MathF.Floor(Y), MathF.Floor(Z));
        }

        /// <summary>
        /// Convert position to string key for tile lookups.
        /// Uses MathF.Floor for proper handling of negative coordinates.
        /// </summary>
        public string ToKey()
        {
            return $"{MathF.Floor(X)},{MathF.Floor(Y)},{MathF.Floor(Z)}";
        }

        public GamePosition Copy()
        {
            return new GamePosition(X, Y, Z);
        }

        // IEquatable<GamePosition> - Python dataclasses have value equality by default
        public bool Equals(GamePosition other)
        {
            return X == other.X && Y == other.Y && Z == other.Z;
        }

        public override bool Equals(object obj)
        {
            return obj is GamePosition other && Equals(other);
        }

        public override int GetHashCode()
        {
            return HashCode.Combine(X, Y, Z);
        }

        public static bool operator ==(GamePosition left, GamePosition right) => left.Equals(right);
        public static bool operator !=(GamePosition left, GamePosition right) => !left.Equals(right);

        public override string ToString() => $"({X}, {Y}, {Z})";
    }
}
