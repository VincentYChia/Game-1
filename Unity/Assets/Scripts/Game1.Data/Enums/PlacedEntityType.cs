// Game1.Data.Enums.PlacedEntityType
// Migrated from: data/models/world.py (lines 274-283)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum PlacedEntityType
    {
        Turret,
        Trap,
        Bomb,
        UtilityDevice,
        CraftingStation,
        TrainingDummy,
        Barrier,
        DroppedItem
    }

    public static class PlacedEntityTypeExtensions
    {
        private static readonly Dictionary<PlacedEntityType, string> ToStringMap = new()
        {
            { PlacedEntityType.Turret, "turret" },
            { PlacedEntityType.Trap, "trap" },
            { PlacedEntityType.Bomb, "bomb" },
            { PlacedEntityType.UtilityDevice, "utility_device" },
            { PlacedEntityType.CraftingStation, "crafting_station" },
            { PlacedEntityType.TrainingDummy, "training_dummy" },
            { PlacedEntityType.Barrier, "barrier" },
            { PlacedEntityType.DroppedItem, "dropped_item" }
        };

        private static readonly Dictionary<string, PlacedEntityType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this PlacedEntityType type) => ToStringMap[type];

        public static PlacedEntityType PlacedEntityTypeFromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : PlacedEntityType.Turret;
    }
}
