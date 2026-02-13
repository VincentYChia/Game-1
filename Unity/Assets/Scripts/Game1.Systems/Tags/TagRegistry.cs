// Game1.Systems.Tags.TagRegistry
// Migrated from: core/tag_system.py (193 lines)
// Migration phase: 4
//
// Central registry for all tag definitions.
// Loads from tag-definitions.JSON (single source of truth).
// Thread-safe singleton with double-checked locking.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Game1.Systems.Tags
{
    /// <summary>
    /// Single tag definition loaded from JSON.
    /// Maps 1:1 to tag_definitions entries in tag-definitions.JSON.
    /// </summary>
    public class TagDefinition
    {
        public string Name { get; set; }
        public string Category { get; set; }
        public string Description { get; set; }
        public int Priority { get; set; } = 0;
        public List<string> RequiresParams { get; set; } = new();
        public Dictionary<string, object> DefaultParams { get; set; } = new();
        public List<string> ConflictsWith { get; set; } = new();
        public List<string> Aliases { get; set; } = new();
        public string AliasOf { get; set; }               // nullable
        public string Stacking { get; set; }               // nullable
        public List<string> Immunity { get; set; } = new();

        /// <summary>
        /// Synergies: outer key = synergy partner tag name,
        /// inner dict = param_name -> bonus value.
        /// Example: { "chain": { "chain_range_bonus": 0.2 } }
        /// </summary>
        public Dictionary<string, Dictionary<string, object>> Synergies { get; set; } = new();

        /// <summary>
        /// Context-dependent behavior overrides.
        /// Key = target category (e.g., "undead"), value = behavior dict.
        /// </summary>
        public Dictionary<string, object> ContextBehavior { get; set; } = new();

        public float AutoApplyChance { get; set; } = 0f;
        public string AutoApplyStatus { get; set; }        // nullable
        public string Parent { get; set; }                 // nullable
    }

    /// <summary>
    /// Central registry for all tag definitions.
    /// Loads from Definitions.JSON/tag-definitions.JSON.
    /// Provides lookup, alias resolution, conflict resolution, and
    /// parameter merging for the tag-based effect system.
    /// </summary>
    public class TagRegistry
    {
        // --- Singleton ---

        private static TagRegistry _instance;
        private static readonly object _lock = new object();

        public static TagRegistry Instance
        {
            get
            {
                if (_instance == null)
                {
                    lock (_lock)
                    {
                        if (_instance == null)
                        {
                            _instance = new TagRegistry();
                        }
                    }
                }
                return _instance;
            }
        }

        private TagRegistry() { }

        /// <summary>
        /// Reset singleton for testing only. Never call in production.
        /// </summary>
        public static void ResetInstance()
        {
            lock (_lock)
            {
                _instance = null;
            }
        }

        // --- State ---

        public bool Loaded { get; private set; }

        private readonly Dictionary<string, TagDefinition> _definitions = new();
        private readonly Dictionary<string, List<string>> _categories = new();
        private readonly Dictionary<string, string> _aliases = new();  // alias -> real tag name
        private List<string> _geometryPriority = new();
        private Dictionary<string, List<string>> _mutuallyExclusive = new();
        private Dictionary<string, string> _contextInference = new();

        // --- Loading ---

        /// <summary>
        /// Load tag definitions from JSON file.
        /// </summary>
        /// <param name="jsonPath">
        /// Full path to tag-definitions.JSON.
        /// In Unity this would be Path.Combine(Application.streamingAssetsPath, "Content/Definitions.JSON/tag-definitions.JSON").
        /// For testing, pass the path directly.
        /// </param>
        public void Load(string jsonPath)
        {
            if (Loaded)
                return;

            if (!File.Exists(jsonPath))
                throw new FileNotFoundException($"Tag definitions not found: {jsonPath}");

            string json = File.ReadAllText(jsonPath);
            JObject data = JObject.Parse(json);

            // Load categories
            JObject categoriesObj = data["categories"] as JObject;
            if (categoriesObj != null)
            {
                foreach (var kvp in categoriesObj)
                {
                    var tagList = kvp.Value.ToObject<List<string>>() ?? new List<string>();
                    _categories[kvp.Key] = tagList;
                }
            }

            // Load tag definitions
            JObject tagDefsObj = data["tag_definitions"] as JObject;
            if (tagDefsObj != null)
            {
                foreach (var kvp in tagDefsObj)
                {
                    string tagName = kvp.Key;
                    JObject tagData = kvp.Value as JObject;
                    if (tagData == null) continue;

                    var tagDef = new TagDefinition
                    {
                        Name = tagName,
                        Category = tagData.Value<string>("category") ?? "unknown",
                        Description = tagData.Value<string>("description") ?? "",
                        Priority = tagData.Value<int?>("priority") ?? 0,
                        RequiresParams = tagData["requires_params"]?.ToObject<List<string>>() ?? new List<string>(),
                        DefaultParams = _parseObjectDict(tagData["default_params"] as JObject),
                        ConflictsWith = tagData["conflicts_with"]?.ToObject<List<string>>() ?? new List<string>(),
                        Aliases = tagData["aliases"]?.ToObject<List<string>>() ?? new List<string>(),
                        AliasOf = tagData.Value<string>("alias_of"),
                        Stacking = tagData.Value<string>("stacking"),
                        Immunity = tagData["immunity"]?.ToObject<List<string>>() ?? new List<string>(),
                        Synergies = _parseSynergies(tagData["synergies"] as JObject),
                        ContextBehavior = _parseObjectDict(tagData["context_behavior"] as JObject),
                        AutoApplyChance = tagData.Value<float?>("auto_apply_chance") ?? 0f,
                        AutoApplyStatus = tagData.Value<string>("auto_apply_status"),
                        Parent = tagData.Value<string>("parent")
                    };

                    _definitions[tagName] = tagDef;

                    // Register aliases
                    foreach (string alias in tagDef.Aliases)
                    {
                        _aliases[alias] = tagName;
                    }
                }
            }

            // Load conflict resolution rules
            JObject conflictData = data["conflict_resolution"] as JObject;
            if (conflictData != null)
            {
                _geometryPriority = conflictData["geometry_priority"]?.ToObject<List<string>>() ?? new List<string>();

                JObject meObj = conflictData["mutually_exclusive"] as JObject;
                if (meObj != null)
                {
                    foreach (var kvp in meObj)
                    {
                        _mutuallyExclusive[kvp.Key] = kvp.Value.ToObject<List<string>>() ?? new List<string>();
                    }
                }
            }

            // Load context inference rules
            JObject ctxObj = data["context_inference"] as JObject;
            if (ctxObj != null)
            {
                foreach (var kvp in ctxObj)
                {
                    _contextInference[kvp.Key] = kvp.Value.Value<string>() ?? "";
                }
            }

            Loaded = true;
        }

        // --- Lookup Methods ---

        /// <summary>Resolve an alias to the canonical tag name. Returns the tag itself if not an alias.</summary>
        public string ResolveAlias(string tag)
        {
            return _aliases.TryGetValue(tag, out string realTag) ? realTag : tag;
        }

        /// <summary>Get tag definition by name (handles aliases). Returns null if not found.</summary>
        public TagDefinition GetDefinition(string tag)
        {
            string realTag = ResolveAlias(tag);
            return _definitions.TryGetValue(realTag, out TagDefinition def) ? def : null;
        }

        /// <summary>Get tag category. Returns null if tag is not registered.</summary>
        public string GetCategory(string tag)
        {
            TagDefinition def = GetDefinition(tag);
            return def?.Category;
        }

        /// <summary>Check if tag is a geometry tag (category == "geometry").</summary>
        public bool IsGeometryTag(string tag)
        {
            return GetCategory(tag) == "geometry";
        }

        /// <summary>Check if tag is a damage type (category == "damage_type").</summary>
        public bool IsDamageTag(string tag)
        {
            return GetCategory(tag) == "damage_type";
        }

        /// <summary>Check if tag is a status effect (category in {status_debuff, status_buff}).</summary>
        public bool IsStatusTag(string tag)
        {
            string cat = GetCategory(tag);
            return cat == "status_debuff" || cat == "status_buff";
        }

        /// <summary>Check if tag is a context tag (category == "context").</summary>
        public bool IsContextTag(string tag)
        {
            return GetCategory(tag) == "context";
        }

        /// <summary>Get all non-alias tags in a given category.</summary>
        public List<string> GetTagsByCategory(string category)
        {
            var result = new List<string>();
            foreach (var kvp in _definitions)
            {
                if (kvp.Value.Category == category && kvp.Value.AliasOf == null)
                {
                    result.Add(kvp.Key);
                }
            }
            return result;
        }

        /// <summary>
        /// Resolve conflicting geometry tags by priority.
        /// Returns the highest-priority geometry tag, or null if none.
        /// </summary>
        public string ResolveGeometryConflict(List<string> tags)
        {
            var geometryTags = new List<string>();
            foreach (string t in tags)
            {
                if (IsGeometryTag(t))
                    geometryTags.Add(t);
            }

            if (geometryTags.Count <= 1)
                return geometryTags.Count == 1 ? geometryTags[0] : null;

            // Use priority list
            foreach (string priorityTag in _geometryPriority)
            {
                if (geometryTags.Contains(priorityTag))
                    return priorityTag;
            }

            // Fallback: use first one
            return geometryTags[0];
        }

        /// <summary>
        /// Check if two tags are mutually exclusive.
        /// Resolves aliases before checking.
        /// </summary>
        public bool CheckMutualExclusion(string tag1, string tag2)
        {
            tag1 = ResolveAlias(tag1);
            tag2 = ResolveAlias(tag2);

            if (_mutuallyExclusive.TryGetValue(tag1, out List<string> exclusions))
            {
                return exclusions.Contains(tag2);
            }
            return false;
        }

        /// <summary>Get a copy of the default parameters for a tag. Returns empty dict if tag not found.</summary>
        public Dictionary<string, object> GetDefaultParams(string tag)
        {
            TagDefinition def = GetDefinition(tag);
            if (def == null || def.DefaultParams == null)
                return new Dictionary<string, object>();

            return new Dictionary<string, object>(def.DefaultParams);
        }

        /// <summary>Merge user params with tag defaults (user overrides defaults).</summary>
        public Dictionary<string, object> MergeParams(string tag, Dictionary<string, object> userParams)
        {
            var merged = GetDefaultParams(tag);
            if (userParams != null)
            {
                foreach (var kvp in userParams)
                {
                    merged[kvp.Key] = kvp.Value;
                }
            }
            return merged;
        }

        /// <summary>Get the context inference rules loaded from JSON.</summary>
        public Dictionary<string, string> GetContextInference()
        {
            return new Dictionary<string, string>(_contextInference);
        }

        // --- JSON Parsing Helpers ---

        /// <summary>
        /// Parse a JObject into Dictionary&lt;string, object&gt;, converting
        /// JValue tokens to their .NET equivalents (float, int, string, bool).
        /// </summary>
        private static Dictionary<string, object> _parseObjectDict(JObject obj)
        {
            var dict = new Dictionary<string, object>();
            if (obj == null) return dict;

            foreach (var kvp in obj)
            {
                dict[kvp.Key] = _convertJToken(kvp.Value);
            }
            return dict;
        }

        /// <summary>
        /// Parse synergies: outer key = partner tag, inner = param dict.
        /// </summary>
        private static Dictionary<string, Dictionary<string, object>> _parseSynergies(JObject obj)
        {
            var result = new Dictionary<string, Dictionary<string, object>>();
            if (obj == null) return result;

            foreach (var kvp in obj)
            {
                result[kvp.Key] = _parseObjectDict(kvp.Value as JObject);
            }
            return result;
        }

        /// <summary>
        /// Convert a JToken to its .NET equivalent.
        /// Handles nested objects, arrays, and primitive types.
        /// </summary>
        private static object _convertJToken(JToken token)
        {
            if (token == null) return null;

            switch (token.Type)
            {
                case JTokenType.Integer:
                    return token.Value<long>();
                case JTokenType.Float:
                    return token.Value<double>();
                case JTokenType.String:
                    return token.Value<string>();
                case JTokenType.Boolean:
                    return token.Value<bool>();
                case JTokenType.Null:
                    return null;
                case JTokenType.Object:
                    return _parseObjectDict(token as JObject);
                case JTokenType.Array:
                    var list = new List<object>();
                    foreach (var item in token)
                    {
                        list.Add(_convertJToken(item));
                    }
                    return list;
                default:
                    return token.ToString();
            }
        }
    }
}
