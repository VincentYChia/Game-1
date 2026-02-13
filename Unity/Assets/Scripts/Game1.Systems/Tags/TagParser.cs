// Game1.Systems.Tags.TagParser
// Migrated from: core/tag_parser.py (192 lines)
// Migration phase: 4
//
// Parses tags + params into EffectConfig.
// Uses TagRegistry as single source of truth.

using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace Game1.Systems.Tags
{
    /// <summary>
    /// Parses tags from item/skill JSON and creates EffectConfig.
    /// Handles alias resolution, categorization, geometry conflict resolution,
    /// context inference, parameter merging, synergy application, and
    /// mutual exclusion checking.
    /// </summary>
    public class TagParser
    {
        private readonly TagRegistry _registry;

        public TagParser()
        {
            _registry = TagRegistry.Instance;
        }

        /// <summary>
        /// Accepts an explicit registry (useful for testing with a pre-loaded instance).
        /// </summary>
        public TagParser(TagRegistry registry)
        {
            _registry = registry ?? throw new ArgumentNullException(nameof(registry));
        }

        /// <summary>
        /// Parse tags and params into EffectConfig.
        /// </summary>
        /// <param name="tags">List of tag strings from JSON definition.</param>
        /// <param name="effectParams">effectParams dict from JSON definition.</param>
        /// <returns>Fully resolved EffectConfig with categorized tags and merged parameters.</returns>
        public EffectConfig Parse(List<string> tags, Dictionary<string, object> effectParams)
        {
            if (tags == null) tags = new List<string>();
            if (effectParams == null) effectParams = new Dictionary<string, object>();

            var config = new EffectConfig
            {
                RawTags = new List<string>(tags)
            };

            // Resolve all aliases first
            var resolvedTags = new List<string>();
            foreach (string tag in tags)
            {
                resolvedTags.Add(_registry.ResolveAlias(tag));
            }

            // Categorize tags
            var geometryTags = new List<string>();
            var damageTags = new List<string>();
            var statusTags = new List<string>();
            var contextTags = new List<string>();
            var specialTags = new List<string>();
            var triggerTags = new List<string>();

            foreach (string tag in resolvedTags)
            {
                string category = _registry.GetCategory(tag);

                if (category == "geometry")
                {
                    geometryTags.Add(tag);
                }
                else if (category == "damage_type")
                {
                    damageTags.Add(tag);
                }
                else if (category == "status_debuff" || category == "status_buff")
                {
                    statusTags.Add(tag);
                }
                else if (category == "context")
                {
                    contextTags.Add(tag);
                }
                else if (category == "special")
                {
                    specialTags.Add(tag);
                }
                else if (category == "trigger")
                {
                    triggerTags.Add(tag);
                }
                else if (category == "equipment")
                {
                    // Handled elsewhere
                }
                else if (category == "unknown" || category == null)
                {
                    config.Warnings.Add($"Unknown tag: {tag}");
                }
            }

            // Resolve geometry conflicts
            if (geometryTags.Count > 1)
            {
                string resolvedGeometry = _registry.ResolveGeometryConflict(geometryTags);
                config.GeometryTag = resolvedGeometry;

                var ignored = new List<string>();
                foreach (string g in geometryTags)
                {
                    if (g != resolvedGeometry) ignored.Add(g);
                }
                config.ConflictsResolved.Add(
                    $"Geometry conflict: using '{resolvedGeometry}', ignoring [{string.Join(", ", ignored)}]"
                );
            }
            else if (geometryTags.Count == 1)
            {
                config.GeometryTag = geometryTags[0];
            }
            else
            {
                // Default to single_target
                config.GeometryTag = "single_target";
            }

            // Store categorized tags
            config.DamageTags = damageTags;
            config.StatusTags = statusTags;
            config.ContextTags = contextTags;
            config.SpecialTags = specialTags;
            config.TriggerTags = triggerTags;

            // Resolve context
            config.Context = _inferContext(contextTags, damageTags, statusTags, effectParams);

            // Check for unusual context combinations
            if (contextTags.Count > 0)
            {
                bool hasHealing = resolvedTags.Contains("healing") || _getFloat(effectParams, "baseHealing") > 0;

                if (contextTags.Contains("enemy") && damageTags.Count > 0)
                {
                    // Expected combination - no warning
                }
                else if (contextTags.Contains("enemy") && hasHealing)
                {
                    config.Warnings.Add("Healing effect on enemy context - is this intentional?");
                }
                else if (contextTags.Contains("ally") && damageTags.Count > 0)
                {
                    config.Warnings.Add("Damage effect on ally context - friendly fire?");
                }
            }

            // Merge parameters with defaults
            config.Params = _mergeAllParams(resolvedTags, effectParams);

            // Extract base damage/healing
            config.BaseDamage = _getFloat(config.Params, "baseDamage");
            config.BaseHealing = _getFloat(config.Params, "baseHealing");

            // Check for synergies
            _applySynergies(config);

            // Check for mutual exclusions
            _checkMutualExclusions(config);

            return config;
        }

        /// <summary>
        /// Infer context if not explicitly specified.
        /// Priority: explicit context tag > damage/debuff => "enemy" > healing/buff => "ally" > default "enemy".
        /// </summary>
        private string _inferContext(List<string> contextTags, List<string> damageTags,
                                     List<string> statusTags, Dictionary<string, object> effectParams)
        {
            if (contextTags.Count > 0)
            {
                // Use first explicit context tag
                return contextTags[0];
            }

            // Infer from effect type
            bool hasDamage = damageTags.Count > 0 || _getFloat(effectParams, "baseDamage") > 0;
            bool hasHealing = _getFloat(effectParams, "baseHealing") > 0;

            // Check status tags category
            bool hasDebuffStatus = false;
            bool hasBuffStatus = false;
            foreach (string tag in statusTags)
            {
                string cat = _registry.GetCategory(tag);
                if (cat == "status_debuff") hasDebuffStatus = true;
                if (cat == "status_buff") hasBuffStatus = true;
            }

            if (hasDamage || hasDebuffStatus)
                return "enemy";
            else if (hasHealing || hasBuffStatus)
                return "ally";
            else
                return "enemy";  // Default
        }

        /// <summary>
        /// Merge all tag default params with user params.
        /// Iterates all resolved tags, collects their defaults,
        /// then applies user overrides on top.
        /// </summary>
        private Dictionary<string, object> _mergeAllParams(List<string> resolvedTags,
                                                            Dictionary<string, object> userParams)
        {
            var merged = new Dictionary<string, object>();

            // Start with defaults for each tag
            foreach (string tag in resolvedTags)
            {
                var tagDefaults = _registry.GetDefaultParams(tag);
                foreach (var kvp in tagDefaults)
                {
                    merged[kvp.Key] = kvp.Value;
                }
            }

            // Override with user params
            foreach (var kvp in userParams)
            {
                merged[kvp.Key] = kvp.Value;
            }

            return merged;
        }

        /// <summary>
        /// Apply tag synergies (e.g., lightning + chain = +20% range).
        /// For each tag with synergies, if the synergy partner tag is present,
        /// apply multiplicative bonuses: current * (1.0 + bonus) for _bonus suffixed params.
        /// </summary>
        private void _applySynergies(EffectConfig config)
        {
            foreach (string tag in config.RawTags)
            {
                TagDefinition tagDef = _registry.GetDefinition(tag);
                if (tagDef == null || tagDef.Synergies == null || tagDef.Synergies.Count == 0)
                    continue;

                foreach (var synergyEntry in tagDef.Synergies)
                {
                    string synergyTag = synergyEntry.Key;
                    Dictionary<string, object> bonuses = synergyEntry.Value;

                    if (!config.RawTags.Contains(synergyTag))
                        continue;

                    // Apply bonuses
                    foreach (var bonusEntry in bonuses)
                    {
                        string paramName = bonusEntry.Key;
                        if (!paramName.EndsWith("_bonus"))
                            continue;

                        // Multiplicative bonus
                        string baseParam = paramName.Substring(0, paramName.Length - "_bonus".Length);
                        if (config.Params.ContainsKey(baseParam))
                        {
                            float current = _getFloat(config.Params, baseParam);
                            float bonus = _convertToFloat(bonusEntry.Value);
                            config.Params[baseParam] = (double)(current * (1.0f + bonus));
                            config.Warnings.Add(
                                $"Synergy: {tag} + {synergyTag} = {baseParam} +{bonus * 100f:F0}%"
                            );
                        }
                    }
                }
            }
        }

        /// <summary>
        /// Check for mutually exclusive tags across all categorized tag lists.
        /// Performs pairwise comparison using the registry's mutual exclusion rules.
        /// </summary>
        private void _checkMutualExclusions(EffectConfig config)
        {
            var allTags = new List<string>();
            allTags.AddRange(config.DamageTags);
            allTags.AddRange(config.StatusTags);
            allTags.AddRange(config.ContextTags);
            allTags.AddRange(config.SpecialTags);

            for (int i = 0; i < allTags.Count; i++)
            {
                for (int j = i + 1; j < allTags.Count; j++)
                {
                    if (_registry.CheckMutualExclusion(allTags[i], allTags[j]))
                    {
                        config.Warnings.Add(
                            $"Mutually exclusive tags: {allTags[i]} and {allTags[j]} - {allTags[j]} will override {allTags[i]}"
                        );
                    }
                }
            }
        }

        // --- Utility Helpers ---

        /// <summary>
        /// Safely extract a float from a dictionary value.
        /// Handles int, long, float, double, and string representations.
        /// Returns 0f if key is missing or unconvertible.
        /// </summary>
        private static float _getFloat(Dictionary<string, object> dict, string key)
        {
            if (dict == null || !dict.TryGetValue(key, out object val))
                return 0f;
            return _convertToFloat(val);
        }

        /// <summary>
        /// Convert an object (potentially boxed numeric) to float.
        /// </summary>
        private static float _convertToFloat(object val)
        {
            if (val == null) return 0f;

            if (val is float f) return f;
            if (val is double d) return (float)d;
            if (val is int i) return i;
            if (val is long l) return l;
            if (val is decimal dec) return (float)dec;

            if (val is string s && float.TryParse(s, System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out float parsed))
                return parsed;

            return 0f;
        }
    }
}
