using Game1.Core.Data;

namespace Game1.Core.World;

/// <summary>
/// Port of systems/natural_resource.py NaturalResource — harvestable node
/// runtime: JSON-driven health/tool/respawn/loot with the hardcoded
/// fallbacks, crit-doubled damage, seeded loot rolls (condition BEFORE
/// quantity draw per drop, matching Python's list-comprehension order),
/// respawn ticking.
/// </summary>
public sealed class LootDropDef
{
    public string ItemId;
    public int MinQuantity;
    public int MaxQuantity;
    public double Chance;

    public LootDropDef(string itemId, int minQuantity, int maxQuantity,
                       double chance = 1.0)
    {
        ItemId = itemId;
        MinQuantity = minQuantity;
        MaxQuantity = maxQuantity;
        Chance = chance;
    }
}

public sealed class NaturalResourceRuntime
{
    public Position Position;
    public string ResourceType;
    public int Tier;

    public double MaxHp;
    public string RequiredTool = "pickaxe";
    public bool Respawns;
    public double? RespawnTimer;

    public double CurrentHp;
    public double TimeUntilRespawn;
    public List<LootDropDef> LootTable;
    public bool Depleted;

    /// <summary>natural_resource.py fallback loot map (db-miss path; all 28
    /// resources + legacy aliases + fishing spot).</summary>
    private static readonly Dictionary<string, (string Item, int Min, int Max)> FallbackLoot = new()
    {
        ["oak_tree"] = ("oak_log", 3, 5), ["pine_tree"] = ("pine_log", 3, 5),
        ["ash_tree"] = ("ash_log", 2, 4), ["birch_tree"] = ("birch_log", 2, 4),
        ["maple_tree"] = ("maple_log", 2, 4), ["ironwood_tree"] = ("ironwood_log", 1, 2),
        ["ebony_tree"] = ("ebony_log", 1, 2), ["worldtree_sapling"] = ("worldtree_log", 1, 2),
        ["copper_vein"] = ("copper_ore", 3, 5), ["iron_deposit"] = ("iron_ore", 3, 5),
        ["tin_seam"] = ("tin_ore", 2, 4), ["steel_node"] = ("steel_ore", 2, 4),
        ["mithril_cache"] = ("mithril_ore", 1, 2), ["adamantine_lode"] = ("adamantine_ore", 1, 2),
        ["orichalcum_trove"] = ("orichalcum_ore", 1, 2), ["etherion_nexus"] = ("etherion_ore", 1, 2),
        ["limestone_outcrop"] = ("limestone", 4, 8), ["granite_formation"] = ("granite", 4, 8),
        ["shale_bed"] = ("shale", 3, 5), ["basalt_column"] = ("basalt", 2, 4),
        ["marble_quarry"] = ("marble", 2, 4), ["quartz_cluster"] = ("crystal_quartz", 2, 4),
        ["obsidian_flow"] = ("obsidian", 2, 4), ["voidstone_shard"] = ("voidstone", 1, 2),
        ["diamond_geode"] = ("diamond", 1, 2), ["eternity_monolith"] = ("eternity_stone", 1, 2),
        ["primordial_formation"] = ("primordial_crystal", 1, 2),
        ["genesis_structure"] = ("genesis_lattice", 1, 2),
        ["copper_ore"] = ("copper_ore", 1, 3), ["iron_ore"] = ("iron_ore", 1, 3),
        ["steel_ore"] = ("steel_ore", 2, 4), ["mithril_ore"] = ("mithril_ore", 2, 5),
        ["limestone"] = ("limestone", 1, 2), ["granite"] = ("granite", 1, 2),
        ["obsidian"] = ("obsidian", 2, 3), ["star_crystal"] = ("diamond", 1, 2),
        ["fishing_spot"] = ("raw_fish", 1, 3),
    };

    public NaturalResourceRuntime(Position position, string resourceType, int tier,
                                  ResourceNodeDatabase? db,
                                  bool debugInfiniteResources = false)
    {
        Position = position;
        ResourceType = resourceType;
        Tier = tier;

        var nodeDef = db is { Loaded: true }
            ? db.Nodes.GetValueOrDefault(resourceType) : null;

        if (nodeDef is not null)
        {
            MaxHp = nodeDef.BaseHealth;
            RequiredTool = nodeDef.RequiredTool;
            Respawns = nodeDef.DoesRespawn;
            var respawnSeconds = nodeDef.GetRespawnSeconds();
            RespawnTimer = respawnSeconds;
            if (debugInfiniteResources && Respawns)
                RespawnTimer = 1.0;
        }
        else
        {
            MaxHp = tier switch { 1 => 100, 2 => 200, 3 => 400, 4 => 800, _ => 100 };
            if (resourceType.Contains("tree"))
            {
                RequiredTool = "axe";
                Respawns = true;
                RespawnTimer = debugInfiniteResources ? 1.0 : 60.0;
            }
            else if (resourceType.Contains("fishing_spot"))
            {
                RequiredTool = "fishing_rod";
                Respawns = true;
                var baseRespawn = tier switch
                { 1 => 30.0, 2 => 45.0, 3 => 60.0, 4 => 90.0, _ => 30.0 };
                RespawnTimer = debugInfiniteResources ? 1.0 : baseRespawn;
                MaxHp = tier switch { 1 => 50, 2 => 75, 3 => 100, 4 => 150, _ => 50 };
            }
            else
            {
                RequiredTool = "pickaxe";
                Respawns = false;
                RespawnTimer = null;
            }
        }

        CurrentHp = MaxHp;
        LootTable = GenerateLootTable(nodeDef);
    }

    private List<LootDropDef> GenerateLootTable(ResourceNodeDefinition? nodeDef)
    {
        if (nodeDef is not null && nodeDef.Drops.Count > 0)
        {
            var lootDrops = new List<LootDropDef>();
            foreach (var drop in nodeDef.Drops)
            {
                var (minQ, maxQ) = drop.GetQuantityRange();
                lootDrops.Add(new LootDropDef(drop.MaterialId, minQ, maxQ,
                                              drop.GetChanceValue()));
            }
            return lootDrops;
        }

        if (FallbackLoot.TryGetValue(ResourceType, out var fb))
            return new List<LootDropDef> { new(fb.Item, fb.Min, fb.Max) };
        return new List<LootDropDef>();
    }

    /// <summary>take_damage — crit ×2; returns (actualDamage, depleted).</summary>
    public (double Actual, bool DepletedNow) TakeDamage(double damage, bool isCrit = false)
    {
        if (Depleted) return (0, false);
        var actualDamage = isCrit ? damage * 2 : damage;
        CurrentHp -= actualDamage;
        if (CurrentHp <= 0)
        {
            CurrentHp = 0;
            Depleted = true;
            return (actualDamage, true);
        }
        return (actualDamage, false);
    }

    /// <summary>get_loot — per drop: chance roll FIRST (&lt;= inclusive),
    /// then quantity randint. Both on the injected (global-random) stream.</summary>
    public List<(string ItemId, long Quantity)> GetLoot(PythonRandom rng)
    {
        var loot = new List<(string, long)>();
        foreach (var drop in LootTable)
            if (rng.NextDouble() <= drop.Chance)
                loot.Add((drop.ItemId, rng.RandInt(drop.MinQuantity, drop.MaxQuantity)));
        return loot;
    }

    public void Update(double dt)
    {
        if (Depleted && Respawns)
        {
            TimeUntilRespawn += dt;
            if (RespawnTimer is { } timer && TimeUntilRespawn >= timer)
            {
                CurrentHp = MaxHp;
                Depleted = false;
                TimeUntilRespawn = 0.0;
            }
        }
    }

    public double GetRespawnProgress()
    {
        if (!Depleted || !Respawns || RespawnTimer is not { } timer)
            return 0.0;
        return Math.Min(1.0, TimeUntilRespawn / timer);
    }
}
