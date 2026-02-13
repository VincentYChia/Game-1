// Game1.Systems.Tags.EffectContext
// Migrated from: core/effect_context.py (EffectContext dataclass)
// Migration phase: 4
//
// Runtime context for effect execution.
// Contains source, target(s), and config.

using System.Collections.Generic;

namespace Game1.Systems.Tags
{
    /// <summary>
    /// Runtime context for effect execution.
    /// Created by EffectExecutor, populated during execution with
    /// resolved targets and timing information.
    /// </summary>
    public class EffectContext
    {
        /// <summary>Entity that created the effect (caster, turret, etc.).</summary>
        public object Source { get; set; }

        /// <summary>Primary target entity before geometry resolution.</summary>
        public object PrimaryTarget { get; set; }

        /// <summary>Parsed effect configuration (tags, params, context).</summary>
        public EffectConfig Config { get; set; }

        /// <summary>Timestamp when the effect was created (game time).</summary>
        public float Timestamp { get; set; } = 0f;

        /// <summary>All resolved targets after geometry selection.</summary>
        public List<object> Targets { get; set; } = new();

        /// <summary>
        /// Creates a new EffectContext. Mirrors Python __post_init__:
        /// if Targets is empty and PrimaryTarget is not null,
        /// Targets is initialized to [PrimaryTarget].
        /// </summary>
        public EffectContext(object source, object primaryTarget, EffectConfig config,
                             float timestamp = 0f, List<object> targets = null)
        {
            Source = source;
            PrimaryTarget = primaryTarget;
            Config = config;
            Timestamp = timestamp;
            Targets = targets ?? new List<object>();

            // Python __post_init__ equivalent
            if (Targets.Count == 0 && PrimaryTarget != null)
            {
                Targets.Add(PrimaryTarget);
            }
        }
    }
}
