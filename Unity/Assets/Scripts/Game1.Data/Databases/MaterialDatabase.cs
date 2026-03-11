// Game1.Data.Databases.MaterialDatabase
// Migrated from: data/databases/material_db.py (203 lines)
// Phase: 2 - Data Layer
// Loads from items.JSON/items-materials-1.JSON + items-refining-1.JSON + stackable items.
// CRITICAL: THREE separate load methods with DIFFERENT JSON field names.

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using Game1.Data.Models;

namespace Game1.Data.Databases
{
    /// <summary>
    /// Singleton database for material definitions (stackable resources, consumables, devices).
    /// Has 3 load methods: LoadFromFile, LoadRefiningItems, LoadStackableItems.
    /// IMPORTANT: LoadRefiningItems uses "itemId" not "materialId", "stackSize" not "maxStack".
    /// </summary>
    public class MaterialDatabase
    {
        private static MaterialDatabase _instance;
        private static readonly object _lock = new object();

        public Dictionary<string, MaterialDefinition> Materials { get; private set; }
        public bool Loaded { get; private set; }

        public static MaterialDatabase GetInstance()
        {
            if (_instance == null)
            {
                lock (_lock)
                {
                    if (_instance == null)
                        _instance = new MaterialDatabase();
                }
            }
            return _instance;
        }

        private MaterialDatabase()
        {
            Materials = new Dictionary<string, MaterialDefinition>();
        }

        /// <summary>
        /// Primary loader: items-materials-1.JSON. Uses "materialId" as ID field.
        /// </summary>
        public bool LoadFromFile(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                var materialsArr = data["materials"] as JArray;
                if (materialsArr == null)
                {
                    CreatePlaceholders();
                    return false;
                }

                foreach (JObject matData in materialsArr)
                {
                    string materialId = matData.Value<string>("materialId") ?? "";
                    string category = matData.Value<string>("category") ?? "unknown";

                    string iconPath = matData.Value<string>("iconPath");
                    if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                    {
                        iconPath = GetIconSubdir(category) + $"/{materialId}.png";
                    }

                    var flags = matData["flags"] as JObject;
                    var effectTags = new List<string>();
                    if (matData["effectTags"] is JArray etArr)
                        foreach (var t in etArr) effectTags.Add(t.Value<string>());

                    var effectParams = new Dictionary<string, object>();
                    if (matData["effectParams"] is JObject epObj)
                        foreach (var p in epObj.Properties())
                            effectParams[p.Name] = p.Value.ToObject<object>();

                    var mat = new MaterialDefinition
                    {
                        MaterialId = materialId,
                        Name = matData.Value<string>("name") ?? "",
                        Tier = matData.Value<int?>("tier") ?? 1,
                        Category = category,
                        Rarity = matData.Value<string>("rarity") ?? "common",
                        Description = matData.Value<string>("description") ?? "",
                        MaxStack = matData.Value<int?>("maxStack") ?? 99,
                        IconPath = iconPath,
                        Placeable = flags?.Value<bool?>("placeable") ?? false,
                        ItemType = matData.Value<string>("type") ?? "",
                        ItemSubtype = matData.Value<string>("subtype") ?? "",
                        Effect = matData.Value<string>("effect") ?? "",
                        EffectTags = effectTags,
                        EffectParams = effectParams
                    };

                    // Parse properties
                    if (matData["properties"] is JObject propsObj)
                    {
                        foreach (var p in propsObj.Properties())
                            mat.Properties[p.Name] = p.Value.ToObject<object>();
                    }

                    Materials[mat.MaterialId] = mat;
                }

                Loaded = true;
                JsonLoader.Log($"Loaded {Materials.Count} materials");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading materials: {ex.Message}");
                CreatePlaceholders();
                return false;
            }
        }

        /// <summary>
        /// Secondary loader: items-refining-1.JSON.
        /// DIFFERENT FIELD NAMES: uses "itemId" (not "materialId"), "stackSize" (not "maxStack").
        /// Only adds if not already in dictionary (no overwrites).
        /// </summary>
        public bool LoadRefiningItems(string filepath)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null) return false;

                int count = 0;
                string[] sections = { "basic_ingots", "alloys", "wood_planks" };

                foreach (string section in sections)
                {
                    if (data[section] is JArray sectionArr)
                    {
                        foreach (JObject itemData in sectionArr)
                        {
                            string materialId = itemData.Value<string>("itemId") ?? "";

                            string iconPath = itemData.Value<string>("iconPath");
                            if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                                iconPath = $"materials/{materialId}.png";

                            var metadata = itemData["metadata"] as JObject;
                            string description = metadata?.Value<string>("narrative") ?? "";

                            var mat = new MaterialDefinition
                            {
                                MaterialId = materialId,
                                Name = itemData.Value<string>("name") ?? "",
                                Tier = itemData.Value<int?>("tier") ?? 1,
                                Category = itemData.Value<string>("type") ?? "unknown",
                                Rarity = itemData.Value<string>("rarity") ?? "common",
                                Description = description,
                                MaxStack = itemData.Value<int?>("stackSize") ?? 256,
                                IconPath = iconPath
                            };

                            if (!string.IsNullOrEmpty(mat.MaterialId) && !Materials.ContainsKey(mat.MaterialId))
                            {
                                Materials[mat.MaterialId] = mat;
                                count++;
                            }
                        }
                    }
                }

                JsonLoader.Log($"Loaded {count} additional materials from refining");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading refining items: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Tertiary loader: any items file (alchemy, engineering, tools).
        /// Only loads items where flags.stackable == true OR flags.placeable == true.
        /// Uses "itemId" as ID field. Optional category filter.
        /// </summary>
        public bool LoadStackableItems(string filepath, List<string> categories = null)
        {
            try
            {
                var data = JsonLoader.LoadRawJsonAbsolute(filepath);
                if (data == null) return false;

                int count = 0;
                foreach (var prop in data.Properties())
                {
                    if (prop.Name == "metadata") continue;
                    if (prop.Value is not JArray sectionData) continue;

                    foreach (JObject itemData in sectionData)
                    {
                        string category = itemData.Value<string>("category") ?? "";
                        var flags = itemData["flags"] as JObject;
                        bool isStackable = flags?.Value<bool?>("stackable") ?? false;
                        bool isPlaceable = flags?.Value<bool?>("placeable") ?? false;

                        bool shouldLoad = (isStackable || isPlaceable) &&
                            (categories == null || categories.Contains(category));

                        if (!shouldLoad) continue;

                        string materialId = itemData.Value<string>("itemId") ?? "";

                        string iconPath = itemData.Value<string>("iconPath");
                        if (string.IsNullOrEmpty(iconPath) && !string.IsNullOrEmpty(materialId))
                        {
                            iconPath = GetIconSubdir(category) + $"/{materialId}.png";
                        }

                        var metadata = itemData["metadata"] as JObject;
                        var effectTags = new List<string>();
                        if (itemData["effectTags"] is JArray etArr)
                            foreach (var t in etArr) effectTags.Add(t.Value<string>());

                        var effectParams = new Dictionary<string, object>();
                        if (itemData["effectParams"] is JObject epObj)
                            foreach (var p in epObj.Properties())
                                effectParams[p.Name] = p.Value.ToObject<object>();

                        var mat = new MaterialDefinition
                        {
                            MaterialId = materialId,
                            Name = itemData.Value<string>("name") ?? "",
                            Tier = itemData.Value<int?>("tier") ?? 1,
                            Category = category,
                            Rarity = itemData.Value<string>("rarity") ?? "common",
                            Description = metadata?.Value<string>("narrative") ?? "",
                            MaxStack = itemData.Value<int?>("stackSize") ?? 99,
                            IconPath = iconPath,
                            Placeable = flags?.Value<bool?>("placeable") ?? false,
                            ItemType = itemData.Value<string>("type") ?? "",
                            ItemSubtype = itemData.Value<string>("subtype") ?? "",
                            Effect = itemData.Value<string>("effect") ?? "",
                            EffectTags = effectTags,
                            EffectParams = effectParams
                        };

                        if (!string.IsNullOrEmpty(mat.MaterialId) && !Materials.ContainsKey(mat.MaterialId))
                        {
                            Materials[mat.MaterialId] = mat;
                            count++;
                        }
                    }
                }

                JsonLoader.Log($"Loaded {count} stackable items (categories: {(categories != null ? string.Join(",", categories) : "all")})");
                return true;
            }
            catch (Exception ex)
            {
                JsonLoader.LogWarning($"Error loading stackable items: {ex.Message}");
                return false;
            }
        }

        public MaterialDefinition GetMaterial(string materialId) =>
            Materials.TryGetValue(materialId, out var mat) ? mat : null;

        private static string GetIconSubdir(string category) => category switch
        {
            "consumable" => "consumables",
            "device" => "devices",
            "station" => "stations",
            _ => "materials"
        };

        private void CreatePlaceholders()
        {
            var items = new (string Id, string Name, int Tier, string Cat, string Rarity)[]
            {
                ("oak_log", "Oak Log", 1, "wood", "common"),
                ("birch_log", "Birch Log", 2, "wood", "common"),
                ("maple_log", "Maple Log", 3, "wood", "uncommon"),
                ("ironwood_log", "Ironwood Log", 4, "wood", "rare"),
                ("copper_ore", "Copper Ore", 1, "ore", "common"),
                ("iron_ore", "Iron Ore", 2, "ore", "common"),
                ("steel_ore", "Steel Ore", 3, "ore", "uncommon"),
                ("mithril_ore", "Mithril Ore", 4, "ore", "rare"),
                ("limestone", "Limestone", 1, "stone", "common"),
                ("granite", "Granite", 2, "stone", "common"),
                ("obsidian", "Obsidian", 3, "stone", "uncommon"),
                ("star_crystal", "Star Crystal", 4, "stone", "legendary"),
                ("copper_ingot", "Copper Ingot", 1, "metal", "common"),
                ("iron_ingot", "Iron Ingot", 2, "metal", "common"),
                ("steel_ingot", "Steel Ingot", 3, "metal", "uncommon"),
                ("mithril_ingot", "Mithril Ingot", 4, "metal", "rare")
            };

            foreach (var (id, name, tier, cat, rarity) in items)
            {
                Materials[id] = new MaterialDefinition
                {
                    MaterialId = id,
                    Name = name,
                    Tier = tier,
                    Category = cat,
                    Rarity = rarity,
                    Description = $"A {rarity} {cat} material (Tier {tier})"
                };
            }

            Loaded = true;
            JsonLoader.Log($"Created {Materials.Count} placeholder materials");
        }

        internal static void ResetInstance() => _instance = null;
    }
}
