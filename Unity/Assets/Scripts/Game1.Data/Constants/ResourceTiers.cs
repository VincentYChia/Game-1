// Game1.Data.Constants.ResourceTiers
// Migrated from: data/models/world.py (lines 158-214)
// Phase: 1 - Foundation

using System.Collections.Generic;
using Game1.Data.Enums;

namespace Game1.Data.Constants
{
    /// <summary>
    /// Default resource tier mappings. Database override behavior belongs in Phase 2.
    /// </summary>
    public static class ResourceTiers
    {
        public static readonly Dictionary<ResourceType, int> Tiers = new()
        {
            // Trees
            { ResourceType.OakTree, 1 },
            { ResourceType.PineTree, 1 },
            { ResourceType.AshTree, 1 },
            { ResourceType.BirchTree, 2 },
            { ResourceType.MapleTree, 2 },
            { ResourceType.IronwoodTree, 3 },
            { ResourceType.EbonyTree, 3 },
            { ResourceType.WorldtreeSapling, 4 },
            // Ores
            { ResourceType.CopperVein, 1 },
            { ResourceType.IronDeposit, 1 },
            { ResourceType.TinSeam, 1 },
            { ResourceType.SteelNode, 2 },
            { ResourceType.MithrilCache, 2 },
            { ResourceType.AdamantineLode, 3 },
            { ResourceType.OrichalcumTrove, 3 },
            { ResourceType.EtherionNexus, 4 },
            // Stones
            { ResourceType.LimestoneOutcrop, 1 },
            { ResourceType.GraniteFormation, 1 },
            { ResourceType.ShaleBed, 1 },
            { ResourceType.BasaltColumn, 2 },
            { ResourceType.MarbleQuarry, 2 },
            { ResourceType.QuartzCluster, 2 },
            { ResourceType.ObsidianFlow, 3 },
            { ResourceType.VoidstoneShard, 3 },
            { ResourceType.DiamondGeode, 3 },
            { ResourceType.EternityMonolith, 4 },
            { ResourceType.PrimordialFormation, 4 },
            { ResourceType.GenesisStructure, 4 },
            // Water resources
            { ResourceType.FishingSpot, 1 },
            // Fishing spots by tier
            { ResourceType.FishingSpotCarp, 1 },
            { ResourceType.FishingSpotSunfish, 1 },
            { ResourceType.FishingSpotMinnow, 1 },
            { ResourceType.FishingSpotStormfin, 2 },
            { ResourceType.FishingSpotFrostback, 2 },
            { ResourceType.FishingSpotLighteye, 2 },
            { ResourceType.FishingSpotShadowgill, 2 },
            { ResourceType.FishingSpotPhoenixkoi, 3 },
            { ResourceType.FishingSpotVoidswimmer, 3 },
            { ResourceType.FishingSpotTempesteel, 3 },
            { ResourceType.FishingSpotLeviathan, 4 },
            { ResourceType.FishingSpotChaosscale, 4 }
        };

        public static int GetTier(ResourceType type) =>
            Tiers.TryGetValue(type, out var tier) ? tier : 1;
    }
}
