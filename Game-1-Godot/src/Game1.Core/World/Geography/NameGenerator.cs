namespace Game1.Core.World.Geography;

/// <summary>
/// Port of systems/geography/name_generator.py — pure hash-indexed names
/// from per-flavor banks (verbatim, order load-bearing; IMPERIAL suffixes
/// contain "ium" twice by design). Every name_* mutates the entity's Name.
/// Locality naming uses the FIRST-INSERTED nation's bank (Python dict-order
/// quirk) — callers pass nations with an insertion-order key list.
/// </summary>
public static class NameGenerator
{
    private sealed class Bank
    {
        public required string[] NationNames;
        public required string[] Adjectives;
        public required string[] Prefixes;
        public required string[] Suffixes;
        public required string[] DistrictNouns;
    }

    private static readonly Dictionary<string, Bank> Banks = new()
    {
        ["stoic"] = new Bank
        {
            NationNames = new[] { "Korsheim", "Nordhaven", "Grimwald", "Stonereach", "Drakmoor", "Ashgard", "Frostholm", "Ironmark", "Wraithgard", "Blackthorn" },
            Adjectives = new[] { "Ashen", "Iron", "Storm", "Grey", "Frost", "Dark", "Grim", "Stark", "Cold", "Dread", "Stone", "Black", "Hollow", "Bleak" },
            Prefixes = new[] { "Storm", "Iron", "Grey", "Frost", "Dark", "Stone", "Grim", "Ash", "Dread", "Cold", "Black", "Thorn", "Wolf", "Hawk" },
            Suffixes = new[] { "crest", "hold", "watch", "guard", "haven", "fall", "gate", "moor", "helm", "keep", "wall", "rock", "vale", "mark" },
            DistrictNouns = new[] { "Quarter", "Ward", "Gate", "Reach", "Heights", "Depths", "Crossing", "Hollow", "Ridge", "Passage" },
        },
        ["flowing"] = new Bank
        {
            NationNames = new[] { "Silvanel", "Brightmere", "Dewhollow", "Willowveil", "Faelind", "Glenmist", "Thornweald", "Moonhaven", "Riverbend", "Starfall" },
            Adjectives = new[] { "Verdant", "Silver", "Misty", "Wild", "Ancient", "Bright", "Gentle", "Wandering", "Woven", "Dappled", "Quiet", "Living" },
            Prefixes = new[] { "Silver", "Green", "Moon", "Star", "Willow", "Briar", "Glen", "Fern", "Dew", "Rose", "Lily", "Thorn", "Moss", "Rain" },
            Suffixes = new[] { "vale", "mere", "haven", "brook", "glade", "dell", "wood", "fall", "weald", "shire", "glen", "dale", "leaf", "song" },
            DistrictNouns = new[] { "Glade", "Dell", "Hollow", "Bower", "Thicket", "Meadow", "Copse", "Grove", "Circle", "Clearing" },
        },
        ["imperial"] = new Bank
        {
            NationNames = new[] { "Aurelium", "Corvanta", "Valdris", "Solareth", "Magistrum", "Imperion", "Regalis", "Dominara", "Luxenheim", "Gloriana" },
            Adjectives = new[] { "Grand", "Golden", "Crimson", "Noble", "Sacred", "Azure", "Royal", "Sovereign", "Exalted", "Pristine", "Gilded", "High" },
            Prefixes = new[] { "Sol", "Val", "Cor", "Rex", "Aur", "Lux", "Dom", "Mag", "Pax", "Gal", "Reg", "Cel", "Tri", "Vic" },
            // "ium" at BOTH index 0 and 10 — verbatim duplicate, indices matter
            Suffixes = new[] { "ium", "anta", "aris", "eth", "orium", "andria", "aven", "heim", "oria", "ence", "ium", "alis", "entus", "erra" },
            DistrictNouns = new[] { "Plaza", "Terrace", "Forum", "Court", "Citadel", "Precinct", "Arcade", "Sanctum", "Promenade", "Quarter" },
        },
        ["stoneworn"] = new Bank
        {
            NationNames = new[] { "Duskmere", "Cindervault", "Bleakhaven", "Ashenmire", "Rustholm", "Emberfell", "Bonecrag", "Hollowdeep", "Grimstone", "Palereach" },
            Adjectives = new[] { "Bitter", "Deep", "Hollow", "Pale", "Ember", "Bleak", "Cinder", "Rust", "Dusk", "Worn", "Cracked", "Sunken" },
            Prefixes = new[] { "Dusk", "Cinder", "Bone", "Rust", "Ash", "Pale", "Hollow", "Deep", "Ember", "Grey", "Old", "Worn", "Bleak", "Dust" },
            Suffixes = new[] { "mere", "vault", "haven", "mire", "fell", "crag", "deep", "stone", "reach", "pit", "den", "barrow", "cairn", "forge" },
            DistrictNouns = new[] { "Barrow", "Cairn", "Pit", "Undercroft", "Foundation", "Catacombs", "Ruins", "Cellar", "Burrow", "Vault" },
        },
        ["ethereal"] = new Bank
        {
            NationNames = new[] { "Aelindra", "Lumareth", "Orivane", "Twilindor", "Veyloria", "Silpharion", "Crysthaven", "Shimmerdeep", "Mythalore", "Celestine" },
            Adjectives = new[] { "Luminous", "Twilight", "Silent", "Opal", "Veiled", "Woven", "Shimmering", "Fading", "Dreamlit", "Prismatic", "Spectral", "Iridescent" },
            Prefixes = new[] { "Ael", "Lum", "Ori", "Twi", "Vey", "Sil", "Crys", "Myth", "Cel", "Neb", "Iri", "Pha", "Zeph", "Aur" },
            Suffixes = new[] { "indra", "areth", "vane", "indor", "oria", "arion", "haven", "deep", "alore", "estine", "iel", "anthe", "endra", "ilis" },
            DistrictNouns = new[] { "Sanctum", "Spire", "Atrium", "Nexus", "Wellspring", "Observatory", "Reliquary", "Archive", "Threshold", "Mirage" },
        },
    };

    private static readonly Dictionary<string, string[]> FeaturePrefixes = new()
    {
        ["dungeon"] = new[] { "Forsaken", "Cursed", "Ancient", "Dark", "Lost" },
        ["npc"] = new[] { "Elder's", "Trader's", "Wanderer's", "Sage's", "Hunter's" },
        ["station"] = new[] { "Old", "Master's", "Grand", "Ruined", "Working" },
        ["rare_resource"] = new[] { "Hidden", "Rich", "Glowing", "Precious", "Deep" },
    };

    private static readonly Dictionary<string, string[]> FeatureSuffixes = new()
    {
        ["dungeon"] = new[] { "Pit", "Maw", "Depths", "Tomb", "Lair", "Chasm" },
        ["npc"] = new[] { "Grove", "Corner", "Rest", "Camp", "Post", "Refuge" },
        ["station"] = new[] { "Forge", "Workshop", "Smeltery", "Bench", "Anvil" },
        ["rare_resource"] = new[] { "Vein", "Stand", "Deposit", "Spring", "Cache" },
    };

    /// <summary>RegionIdentity.display_name — Python str.capitalize().</summary>
    private static readonly Dictionary<string, string> IdentityDisplay = new()
    {
        ["forest"] = "Forest", ["mountains"] = "Mountains", ["plains"] = "Plains",
        ["steppe"] = "Steppe", ["lowlands"] = "Lowlands",
        ["marshlands"] = "Marshlands", ["caverns"] = "Caverns",
        ["highlands"] = "Highlands", ["lakeland"] = "Lakeland", ["ruins"] = "Ruins",
    };

    private static Bank GetBank(string flavor) =>
        Banks.GetValueOrDefault(flavor, Banks["stoic"]);

    private static string Pick(string[] items, int idx)
    {
        if (items.Length == 0) return "Unknown";
        return items[idx % items.Length];
    }

    public static string NameNation(NationData nation, long seed)
    {
        var bank = GetBank(nation.NamingFlavor);
        var idx = GeoNoise.Hash2DInt(nation.NationId, 0, seed + 900000,
                                     bank.NationNames.Length);
        var name = Pick(bank.NationNames, idx);
        nation.Name = name;
        return name;
    }

    public static string NameRegion(RegionData region, NationData nation, long seed)
    {
        var bank = GetBank(nation.NamingFlavor);
        var adjIdx = GeoNoise.Hash2DInt(region.RegionId, 1, seed + 910000,
                                        bank.Adjectives.Length);
        var adj = Pick(bank.Adjectives, adjIdx);
        var identityName = IdentityDisplay.GetValueOrDefault(region.Identity, "Forest");
        var name = adj + " " + identityName;
        region.Name = name;
        return name;
    }

    public static string NameProvince(ProvinceData province, NationData nation, long seed)
    {
        var bank = GetBank(nation.NamingFlavor);
        var pIdx = GeoNoise.Hash2DInt(province.ProvinceId, 2, seed + 920000,
                                      bank.Prefixes.Length);
        var sIdx = GeoNoise.Hash2DInt(province.ProvinceId, 3, seed + 930000,
                                      bank.Suffixes.Length);
        var name = Pick(bank.Prefixes, pIdx) + Pick(bank.Suffixes, sIdx);
        province.Name = name;
        return name;
    }

    public static string NameDistrict(DistrictData district, NationData nation, long seed)
    {
        var bank = GetBank(nation.NamingFlavor);
        var style = GeoNoise.Hash2DInt(district.DistrictId, 4, seed + 940000, 2);
        string name;
        if (style == 0)
        {
            var aIdx = GeoNoise.Hash2DInt(district.DistrictId, 5, seed + 950000,
                                          bank.Adjectives.Length);
            var nIdx = GeoNoise.Hash2DInt(district.DistrictId, 6, seed + 960000,
                                          bank.DistrictNouns.Length);
            name = "The " + Pick(bank.Adjectives, aIdx) + " "
                   + Pick(bank.DistrictNouns, nIdx);
        }
        else
        {
            var pIdx = GeoNoise.Hash2DInt(district.DistrictId, 7, seed + 970000,
                                          bank.Prefixes.Length);
            var sIdx = GeoNoise.Hash2DInt(district.DistrictId, 8, seed + 980000,
                                          bank.Suffixes.Length);
            name = Pick(bank.Prefixes, pIdx) + Pick(bank.Suffixes, sIdx);
        }
        district.Name = name;
        return name;
    }

    public static string NameLocality(LocalityData locality, NationData nation, long seed)
    {
        var bank = GetBank(nation.NamingFlavor);
        var ft = locality.FeatureType;
        var prefixes = FeaturePrefixes.GetValueOrDefault(ft, bank.Adjectives);
        var suffixes = FeatureSuffixes.GetValueOrDefault(ft, bank.DistrictNouns);
        var pIdx = GeoNoise.Hash2DInt(locality.LocalityId, 9, seed + 990000,
                                      prefixes.Length);
        var sIdx = GeoNoise.Hash2DInt(locality.LocalityId, 10, seed + 991000,   // irregular
                                      suffixes.Length);
        var name = Pick(prefixes, pIdx) + " " + Pick(suffixes, sIdx);
        locality.Name = name;
        return name;
    }

    /// <summary>name_all — tiers sorted ascending by id; missing nation →
    /// skip; localities all use the FIRST-INSERTED nation (nationOrder[0]).</summary>
    public static void NameAll(Dictionary<int, NationData> nations,
                               List<int> nationInsertionOrder,
                               Dictionary<int, RegionData> regions,
                               Dictionary<int, ProvinceData> provinces,
                               Dictionary<int, DistrictData> districts,
                               Dictionary<int, LocalityData> localities,
                               long seed)
    {
        foreach (var nid in nations.Keys.OrderBy(k => k))
            NameNation(nations[nid], seed);

        foreach (var rid in regions.Keys.OrderBy(k => k))
        {
            var region = regions[rid];
            var nation = nations.GetValueOrDefault(region.NationId);
            if (nation is not null)
                NameRegion(region, nation, seed);
        }

        foreach (var pid in provinces.Keys.OrderBy(k => k))
        {
            var province = provinces[pid];
            var nation = nations.GetValueOrDefault(province.NationId);
            if (nation is not null)
                NameProvince(province, nation, seed);
        }

        foreach (var did in districts.Keys.OrderBy(k => k))
        {
            var district = districts[did];
            var nation = nations.GetValueOrDefault(district.NationId);
            if (nation is not null)
                NameDistrict(district, nation, seed);
        }

        foreach (var lid in localities.Keys.OrderBy(k => k))
        {
            NationData? nation = null;
            foreach (var nid in nationInsertionOrder)   // first-inserted wins
            {
                nation = nations.GetValueOrDefault(nid);
                break;
            }
            if (nation is not null)
                NameLocality(localities[lid], nation, seed);
        }
    }
}
