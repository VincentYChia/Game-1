// Game1.Data.Constants.BarrierHealth
// Migrated from: data/models/world.py (line 335)
// Phase: 1 - Foundation

using System.Collections.Generic;

namespace Game1.Data.Constants
{
    /// <summary>
    /// Barrier health by tier: T1=50, T2=100, T3=200, T4=400
    /// </summary>
    public static class BarrierHealth
    {
        public static readonly Dictionary<int, float> HealthByTier = new()
        {
            { 1, 50f },
            { 2, 100f },
            { 3, 200f },
            { 4, 400f }
        };

        public static float GetHealth(int tier) =>
            HealthByTier.TryGetValue(tier, out var health) ? health : 50f;
    }
}
