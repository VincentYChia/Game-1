// ============================================================================
// Game1.Entities.Tool
// Migrated from: entities/tool.py
// Migration phase: 3
// Date: 2026-02-21
//
// Represents a tool used for resource gathering (axes, pickaxes, etc.).
// Tools are EquipmentItems with specialized gathering logic.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;
using Game1.Data.Enums;

namespace Game1.Entities
{
    /// <summary>
    /// Tool specialization for resource gathering.
    /// Wraps an EquipmentItem and provides gathering-specific methods.
    ///
    /// Tool types: axe, pickaxe, hammer, chisel, tongs, mortar_pestle
    /// Each tool type is effective against specific resource categories.
    /// </summary>
    public class Tool
    {
        /// <summary>The underlying equipment item for this tool.</summary>
        public EquipmentItem Equipment { get; }

        /// <summary>Tool type determines which resources can be gathered.</summary>
        public string ToolType { get; }

        /// <summary>Tool tier affects gatherable resource tier (can gather up to this tier).</summary>
        public int ToolTier => Equipment.Tier;

        /// <summary>Gathering speed multiplier from tool efficiency.</summary>
        public float GatherSpeed => Equipment.Efficiency * Equipment.GetEffectiveness();

        // ====================================================================
        // Tool Type → Resource Category Mappings
        // Matches Python: tool.py resource_category mappings
        // ====================================================================

        private static readonly Dictionary<string, HashSet<string>> _toolResourceMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["axe"]           = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "wood", "tree", "plant" },
            ["pickaxe"]       = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "ore", "stone", "gem", "metal" },
            ["hammer"]        = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "stone", "ore", "metal" },
            ["chisel"]        = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "gem", "stone" },
            ["tongs"]         = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "metal" },
            ["mortar_pestle"] = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "herb", "plant", "alchemy" },
            ["fishing_rod"]   = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "fish", "water" },
            ["sickle"]        = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "herb", "plant", "fabric" },
        };

        // ====================================================================
        // Constructor
        // ====================================================================

        public Tool(EquipmentItem equipment)
        {
            Equipment = equipment ?? throw new ArgumentNullException(nameof(equipment));

            // Determine tool type from equipment metadata
            ToolType = DetermineToolType(equipment);
        }

        // ====================================================================
        // Gathering Methods
        // ====================================================================

        /// <summary>
        /// Check if this tool can harvest a resource of the given category.
        /// </summary>
        public bool CanHarvest(string resourceCategory)
        {
            if (string.IsNullOrEmpty(resourceCategory)) return false;

            if (_toolResourceMap.TryGetValue(ToolType, out var validCategories))
            {
                return validCategories.Contains(resourceCategory);
            }

            return false;
        }

        /// <summary>
        /// Check if this tool can harvest a resource of the given tier.
        /// Tool tier must be >= resource tier.
        /// </summary>
        public bool CanHarvestTier(int resourceTier)
        {
            return ToolTier >= resourceTier;
        }

        /// <summary>
        /// Calculate gathering effectiveness for a specific resource.
        /// Returns a multiplier (0.0 - 1.0+) applied to gather amount/speed.
        /// </summary>
        public float GetGatherEffectiveness(string resourceCategory, int resourceTier)
        {
            if (!CanHarvest(resourceCategory)) return 0f;
            if (!CanHarvestTier(resourceTier)) return 0f;

            float base_ = GatherSpeed;

            // Tier advantage bonus: +10% per tier above resource
            int tierAdvantage = ToolTier - resourceTier;
            if (tierAdvantage > 0)
            {
                base_ *= 1.0f + tierAdvantage * 0.1f;
            }

            return base_;
        }

        /// <summary>
        /// Apply durability loss from gathering.
        /// Returns the durability actually lost.
        /// </summary>
        public int ApplyGatheringWear(float durabilityLossMultiplier = 1.0f)
        {
            int baseLoss = 1;
            int loss = Math.Max(1, (int)(baseLoss * durabilityLossMultiplier));
            int before = Equipment.DurabilityCurrent;
            Equipment.DurabilityCurrent = Math.Max(0, Equipment.DurabilityCurrent - loss);
            return before - Equipment.DurabilityCurrent;
        }

        // ====================================================================
        // Static Helpers
        // ====================================================================

        /// <summary>
        /// Determine tool type from equipment item fields.
        /// Checks slot, itemType, and tags.
        /// </summary>
        private static string DetermineToolType(EquipmentItem equip)
        {
            // Check if it's in a tool slot
            string slot = equip.SlotRaw?.ToLowerInvariant() ?? "";
            if (slot == "axe") return "axe";
            if (slot == "pickaxe") return "pickaxe";

            // Check itemType
            string type = equip.ItemType?.ToLowerInvariant() ?? "";
            if (type == "axe" || type == "tool_axe") return "axe";
            if (type == "pickaxe" || type == "tool_pickaxe") return "pickaxe";
            if (type == "hammer" || type == "tool_hammer") return "hammer";
            if (type == "chisel" || type == "tool_chisel") return "chisel";
            if (type == "tongs" || type == "tool_tongs") return "tongs";
            if (type == "mortar_pestle") return "mortar_pestle";
            if (type == "fishing_rod") return "fishing_rod";
            if (type == "sickle" || type == "tool_sickle") return "sickle";

            // Check tags for tool type
            if (equip.Tags != null)
            {
                foreach (var tag in equip.Tags)
                {
                    string t = tag.ToLowerInvariant();
                    if (t == "axe" || t == "pickaxe" || t == "hammer" || t == "chisel"
                        || t == "tongs" || t == "mortar_pestle" || t == "fishing_rod" || t == "sickle")
                    {
                        return t;
                    }
                }
            }

            // Check item ID as last resort
            string id = equip.ItemId?.ToLowerInvariant() ?? "";
            if (id.Contains("axe")) return "axe";
            if (id.Contains("pickaxe") || id.Contains("pick")) return "pickaxe";
            if (id.Contains("hammer")) return "hammer";
            if (id.Contains("chisel")) return "chisel";
            if (id.Contains("tongs")) return "tongs";
            if (id.Contains("mortar") || id.Contains("pestle")) return "mortar_pestle";
            if (id.Contains("fishing") || id.Contains("rod")) return "fishing_rod";
            if (id.Contains("sickle")) return "sickle";

            return "unknown";
        }

        /// <summary>
        /// Check if an equipment item is a tool based on its slot or type.
        /// </summary>
        public static bool IsTool(EquipmentItem equip)
        {
            if (equip == null) return false;

            string slot = equip.SlotRaw?.ToLowerInvariant() ?? "";
            if (slot == "axe" || slot == "pickaxe") return true;

            string type = equip.ItemType?.ToLowerInvariant() ?? "";
            return type.StartsWith("tool_") || _toolResourceMap.ContainsKey(type);
        }

        public override string ToString()
        {
            return $"{Equipment.Name} ({ToolType} T{ToolTier})";
        }
    }
}
