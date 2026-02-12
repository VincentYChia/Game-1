// Game1.Entities.DamageNumber
// Migrated from: entities/damage_number.py
// Phase: 3 - Entity Layer
// Note: In Phase 6 this becomes a MonoBehaviour/UI element.
// Phase 3 preserves the data model (position, value, color, lifetime).

using System;
using Game1.Data.Models;

namespace Game1.Entities
{
    /// <summary>
    /// Data model for floating damage/heal numbers.
    /// In Python this was a Pygame-rendered sprite. In Unity this will
    /// become a TextMeshPro component (Phase 6).
    /// Phase 3 preserves the data: value, position, color, lifetime.
    /// </summary>
    public class DamageNumber
    {
        public float Value { get; set; }
        public GamePosition Position { get; set; }
        public (int R, int G, int B, int A) Color { get; set; }
        public bool IsCritical { get; set; }
        public float Lifetime { get; set; } = 1.0f;
        public float TimeRemaining { get; set; }
        public float FloatSpeed { get; set; } = 30.0f;  // Pixels/sec upward drift
        public float FadeStartTime { get; set; } = 0.5f; // Start fading at this point

        // Standard colors matching Python
        public static readonly (int, int, int, int) DamageColor = (255, 50, 50, 255);     // Red
        public static readonly (int, int, int, int) CritColor = (255, 200, 0, 255);       // Gold
        public static readonly (int, int, int, int) HealColor = (50, 255, 50, 255);       // Green
        public static readonly (int, int, int, int) ShieldColor = (100, 150, 255, 255);   // Blue
        public static readonly (int, int, int, int) PoisonColor = (150, 0, 200, 255);     // Purple
        public static readonly (int, int, int, int) MissColor = (180, 180, 180, 255);     // Gray

        public DamageNumber(float value, GamePosition position,
            (int R, int G, int B, int A)? color = null, bool isCritical = false)
        {
            Value = value;
            Position = position;
            Color = color ?? DamageColor;
            IsCritical = isCritical;
            TimeRemaining = Lifetime;
        }

        /// <summary>
        /// Update position (float upward) and lifetime.
        /// Returns false if expired.
        /// </summary>
        public bool Update(float dt)
        {
            TimeRemaining -= dt;
            // Float upward (Phase 6 will convert to world-space movement)
            Position = new GamePosition(Position.X, Position.Y - FloatSpeed * dt, Position.Z);
            return TimeRemaining > 0;
        }

        /// <summary>
        /// Get current opacity (0.0-1.0) for fade effect.
        /// </summary>
        public float GetAlpha()
        {
            if (TimeRemaining > FadeStartTime)
                return 1.0f;
            return Math.Max(0f, TimeRemaining / FadeStartTime);
        }
    }
}
