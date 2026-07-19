namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/setting_resolver.py — the factual geographic
/// setting tag: village > underground > ruins > waterside > wasteland >
/// thicket > wilderness. Sequential early-return; a non-village locality
/// falls through to chunk-type checks.
/// </summary>
public static class SettingResolver
{
    private static readonly HashSet<string> UndergroundTypes = new()
    {
        NewChunkTypes.Cave, NewChunkTypes.DeepCave,
        NewChunkTypes.CrystalCavern, NewChunkTypes.FloodedCave,
    };

    private static readonly HashSet<string> WaterTypes = new()
    { NewChunkTypes.Lake, NewChunkTypes.River, NewChunkTypes.Wetland };

    public static string ResolveSetting(GeographicData geo, WorldMap? worldMap = null)
    {
        // locality_id >= 0 (0 IS valid; sentinel is -1)
        if (geo.LocalityId >= 0 && worldMap is not null)
        {
            var loc = worldMap.Localities.GetValueOrDefault(geo.LocalityId);
            if (loc is not null && loc.FeatureType == "village")
                return "village";
        }

        if (UndergroundTypes.Contains(geo.ChunkType)) return "underground";
        if (geo.ChunkType == NewChunkTypes.OvergrownRuins) return "ruins";
        if (WaterTypes.Contains(geo.ChunkType)) return "waterside";
        if (geo.ChunkType == NewChunkTypes.BarrenWaste) return "wasteland";
        if (geo.ChunkType == NewChunkTypes.DenseThicket) return "thicket";
        return "wilderness";
    }
}
