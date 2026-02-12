// Game1.Data.Enums.ResourceType
// Migrated from: data/models/world.py (lines 68-136)
// Phase: 1 - Foundation

using System.Collections.Generic;
using System.Linq;

namespace Game1.Data.Enums
{
    public enum ResourceType
    {
        // Trees (8)
        OakTree,
        PineTree,
        AshTree,
        BirchTree,
        MapleTree,
        IronwoodTree,
        EbonyTree,
        WorldtreeSapling,

        // Ores (8)
        CopperVein,
        IronDeposit,
        TinSeam,
        SteelNode,
        MithrilCache,
        AdamantineLode,
        OrichalcumTrove,
        EtherionNexus,

        // Stones (12)
        LimestoneOutcrop,
        GraniteFormation,
        ShaleBed,
        BasaltColumn,
        MarbleQuarry,
        QuartzCluster,
        ObsidianFlow,
        VoidstoneShard,
        DiamondGeode,
        EternityMonolith,
        PrimordialFormation,
        GenesisStructure,

        // Water resources
        FishingSpot,
        // Tier 1 fishing spots
        FishingSpotCarp,
        FishingSpotSunfish,
        FishingSpotMinnow,
        // Tier 2 fishing spots
        FishingSpotStormfin,
        FishingSpotFrostback,
        FishingSpotLighteye,
        FishingSpotShadowgill,
        // Tier 3 fishing spots
        FishingSpotPhoenixkoi,
        FishingSpotVoidswimmer,
        FishingSpotTempesteel,
        // Tier 4 fishing spots
        FishingSpotLeviathan,
        FishingSpotChaosscale
    }

    public static class ResourceTypeExtensions
    {
        private static readonly Dictionary<ResourceType, string> ToStringMap = new()
        {
            // Trees
            { ResourceType.OakTree, "oak_tree" },
            { ResourceType.PineTree, "pine_tree" },
            { ResourceType.AshTree, "ash_tree" },
            { ResourceType.BirchTree, "birch_tree" },
            { ResourceType.MapleTree, "maple_tree" },
            { ResourceType.IronwoodTree, "ironwood_tree" },
            { ResourceType.EbonyTree, "ebony_tree" },
            { ResourceType.WorldtreeSapling, "worldtree_sapling" },
            // Ores
            { ResourceType.CopperVein, "copper_vein" },
            { ResourceType.IronDeposit, "iron_deposit" },
            { ResourceType.TinSeam, "tin_seam" },
            { ResourceType.SteelNode, "steel_node" },
            { ResourceType.MithrilCache, "mithril_cache" },
            { ResourceType.AdamantineLode, "adamantine_lode" },
            { ResourceType.OrichalcumTrove, "orichalcum_trove" },
            { ResourceType.EtherionNexus, "etherion_nexus" },
            // Stones
            { ResourceType.LimestoneOutcrop, "limestone_outcrop" },
            { ResourceType.GraniteFormation, "granite_formation" },
            { ResourceType.ShaleBed, "shale_bed" },
            { ResourceType.BasaltColumn, "basalt_column" },
            { ResourceType.MarbleQuarry, "marble_quarry" },
            { ResourceType.QuartzCluster, "quartz_cluster" },
            { ResourceType.ObsidianFlow, "obsidian_flow" },
            { ResourceType.VoidstoneShard, "voidstone_shard" },
            { ResourceType.DiamondGeode, "diamond_geode" },
            { ResourceType.EternityMonolith, "eternity_monolith" },
            { ResourceType.PrimordialFormation, "primordial_formation" },
            { ResourceType.GenesisStructure, "genesis_structure" },
            // Water resources
            { ResourceType.FishingSpot, "fishing_spot" },
            { ResourceType.FishingSpotCarp, "fishing_spot_carp" },
            { ResourceType.FishingSpotSunfish, "fishing_spot_sunfish" },
            { ResourceType.FishingSpotMinnow, "fishing_spot_minnow" },
            { ResourceType.FishingSpotStormfin, "fishing_spot_stormfin" },
            { ResourceType.FishingSpotFrostback, "fishing_spot_frostback" },
            { ResourceType.FishingSpotLighteye, "fishing_spot_lighteye" },
            { ResourceType.FishingSpotShadowgill, "fishing_spot_shadowgill" },
            { ResourceType.FishingSpotPhoenixkoi, "fishing_spot_phoenixkoi" },
            { ResourceType.FishingSpotVoidswimmer, "fishing_spot_voidswimmer" },
            { ResourceType.FishingSpotTempesteel, "fishing_spot_tempesteel" },
            { ResourceType.FishingSpotLeviathan, "fishing_spot_leviathan" },
            { ResourceType.FishingSpotChaosscale, "fishing_spot_chaosscale" }
        };

        private static readonly Dictionary<string, ResourceType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        /// <summary>
        /// Legacy aliases from Python enum where multiple names mapped to the same value.
        /// In C#, these resolve to the canonical enum member.
        /// </summary>
        public static readonly Dictionary<string, ResourceType> LegacyAliases = new()
        {
            { "copper_vein", ResourceType.CopperVein },
            { "iron_deposit", ResourceType.IronDeposit },
            { "steel_node", ResourceType.SteelNode },
            { "mithril_cache", ResourceType.MithrilCache },
            { "limestone_outcrop", ResourceType.LimestoneOutcrop },
            { "granite_formation", ResourceType.GraniteFormation },
            { "obsidian_flow", ResourceType.ObsidianFlow },
            { "diamond_geode", ResourceType.DiamondGeode }
        };

        public static string ToJsonString(this ResourceType type) => ToStringMap[type];

        public static ResourceType ResourceTypeFromJsonString(string value)
        {
            if (FromStringMap.TryGetValue(value, out var result))
                return result;
            if (LegacyAliases.TryGetValue(value, out var aliased))
                return aliased;
            return ResourceType.OakTree;
        }
    }
}
