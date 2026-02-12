// Game1.Data.Enums.AIState
// Migrated from: Combat/enemy.py (lines 21-30)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum AIState
    {
        Idle,
        Wander,
        Patrol,
        Guard,
        Chase,
        Attack,
        Flee,
        Dead,
        Corpse
    }

    public static class AIStateExtensions
    {
        private static readonly Dictionary<AIState, string> ToStringMap = new()
        {
            { AIState.Idle, "idle" },
            { AIState.Wander, "wander" },
            { AIState.Patrol, "patrol" },
            { AIState.Guard, "guard" },
            { AIState.Chase, "chase" },
            { AIState.Attack, "attack" },
            { AIState.Flee, "flee" },
            { AIState.Dead, "dead" },
            { AIState.Corpse, "corpse" }
        };

        private static readonly Dictionary<string, AIState> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this AIState state) => ToStringMap[state];

        public static AIState AIStateFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : AIState.Idle;
    }
}
