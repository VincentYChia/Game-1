// Game1.Systems.Tags.EffectConfig
// Migrated from: core/effect_context.py (EffectConfig dataclass)
// Migration phase: 4
//
// Configuration for an effect parsed from tags.
// This is the unified structure all effects use.

using System.Collections.Generic;

namespace Game1.Systems.Tags
{
    /// <summary>
    /// Configuration for an effect parsed from tags.
    /// Contains categorized tags, resolved context, base parameters,
    /// merged effect parameters, and any warnings/conflicts from parsing.
    /// </summary>
    public class EffectConfig
    {
        // --- Source tags ---

        /// <summary>Original tags as provided before alias resolution.</summary>
        public List<string> RawTags { get; set; } = new();

        // --- Categorized tags ---

        /// <summary>Resolved geometry tag (single_target, chain, cone, circle, beam, pierce). Nullable.</summary>
        public string GeometryTag { get; set; }

        /// <summary>Damage type tags (physical, fire, ice, lightning, poison, arcane, shadow, holy).</summary>
        public List<string> DamageTags { get; set; } = new();

        /// <summary>Status effect tags (burn, bleed, freeze, empower, etc.).</summary>
        public List<string> StatusTags { get; set; } = new();

        /// <summary>Context tags (enemy, ally, self, all).</summary>
        public List<string> ContextTags { get; set; } = new();

        /// <summary>Special mechanic tags (lifesteal, knockback, execute, critical, etc.).</summary>
        public List<string> SpecialTags { get; set; } = new();

        /// <summary>Trigger condition tags (on_hit, on_kill, periodic, etc.).</summary>
        public List<string> TriggerTags { get; set; } = new();

        // --- Resolved context ---

        /// <summary>Resolved targeting context: "enemy", "ally", "self", "all". Default "enemy".</summary>
        public string Context { get; set; } = "enemy";

        // --- Base parameters ---

        /// <summary>Base damage value extracted from merged params (baseDamage key).</summary>
        public float BaseDamage { get; set; } = 0f;

        /// <summary>Base healing value extracted from merged params (baseHealing key).</summary>
        public float BaseHealing { get; set; } = 0f;

        // --- All effect parameters (merged defaults + user params) ---

        /// <summary>
        /// All effect parameters. Built by merging tag default_params for every tag,
        /// then overriding with user-supplied effectParams from JSON.
        /// </summary>
        public Dictionary<string, object> Params { get; set; } = new();

        // --- Warnings / conflicts ---

        /// <summary>Non-fatal warnings generated during parsing (unknown tags, unusual combos).</summary>
        public List<string> Warnings { get; set; } = new();

        /// <summary>Conflicts that were automatically resolved (e.g., geometry priority).</summary>
        public List<string> ConflictsResolved { get; set; } = new();
    }
}
