// Game1.Entities.Tool
// Migrated from: entities/tool.py
// Phase: 3 - Entity Layer
// Note: In the migration, Tool functionality is largely replaced by
// EquipmentItem with slot="axe"/"pickaxe". This class is preserved for
// backward compatibility with the legacy Tool concept.

using System;

namespace Game1.Entities
{
    /// <summary>
    /// Legacy Tool class. In the migrated architecture, tools are EquipmentItem
    /// instances in axe/pickaxe slots. This class exists for compatibility with
    /// code that references the Tool abstraction.
    /// </summary>
    [Serializable]
    public class Tool
    {
        public string ToolId { get; set; }
        public string Name { get; set; }
        public string ToolType { get; set; } // axe, pickaxe, fishing_rod
        public int Tier { get; set; } = 1;
        public int Damage { get; set; } = 10;
        public float Efficiency { get; set; } = 1.0f;
        public int DurabilityCurrent { get; set; } = 100;
        public int DurabilityMax { get; set; } = 100;

        public Tool() { }

        public Tool(string toolId, string name, string toolType, int tier = 1,
            int damage = 10, float efficiency = 1.0f, int durability = 100)
        {
            ToolId = toolId;
            Name = name;
            ToolType = toolType;
            Tier = tier;
            Damage = damage;
            Efficiency = efficiency;
            DurabilityCurrent = durability;
            DurabilityMax = durability;
        }

        /// <summary>
        /// Get effectiveness based on durability (matches EquipmentItem formula).
        /// 0% durability = 50% effectiveness, items never break.
        /// </summary>
        public float GetEffectiveness()
        {
            if (DurabilityCurrent <= 0) return 0.5f;
            float durPct = (float)DurabilityCurrent / DurabilityMax;
            return durPct >= 0.5f ? 1.0f : 1.0f - (0.5f - durPct) * 0.5f;
        }

        public void TakeDurabilityDamage(float amount)
        {
            DurabilityCurrent = Math.Max(0, DurabilityCurrent - (int)amount);
        }

        public void Repair(int amount)
        {
            DurabilityCurrent = Math.Min(DurabilityMax, DurabilityCurrent + amount);
        }
    }
}
