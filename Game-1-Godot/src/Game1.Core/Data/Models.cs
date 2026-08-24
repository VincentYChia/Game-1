using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Ports of data/models/*.py dataclasses (tranche 1). Arbitrary-shape JSON
/// fields (properties, effect params, inputs, ...) stay JsonNode so content
/// round-trips byte-faithfully. Each model emits a parity node whose keys
/// mirror Python dataclasses.asdict() (snake_case field names) — that is the
/// loader-parity contract checked against conformance/goldens/db_parity/.
/// </summary>
public sealed class MaterialDefinition
{
    public required string MaterialId { get; init; }
    public required string Name { get; init; }
    public required double Tier { get; init; }
    public required string Category { get; init; }
    public required string Rarity { get; init; }
    public string Description { get; init; } = "";
    public double MaxStack { get; init; } = 99;
    public JsonNode Properties { get; init; } = new JsonObject();
    public string? IconPath { get; init; }
    public bool Placeable { get; init; }
    public string ItemType { get; init; } = "";
    public string ItemSubtype { get; init; } = "";
    public string Effect { get; init; } = "";
    public JsonNode EffectTags { get; init; } = new JsonArray();
    public JsonNode EffectParams { get; init; } = new JsonObject();
    public string Narrative { get; init; } = "";
    public JsonNode Tags { get; init; } = new JsonArray();

    public JsonObject ToParityNode() => new()
    {
        ["material_id"] = MaterialId,
        ["name"] = Name,
        ["tier"] = Tier,
        ["category"] = Category,
        ["rarity"] = Rarity,
        ["description"] = Description,
        ["max_stack"] = MaxStack,
        ["properties"] = Properties.DeepClone(),
        ["icon_path"] = IconPath is null ? null : JsonValue.Create(IconPath),
        ["placeable"] = Placeable,
        ["item_type"] = ItemType,
        ["item_subtype"] = ItemSubtype,
        ["effect"] = Effect,
        ["effect_tags"] = EffectTags.DeepClone(),
        ["effect_params"] = EffectParams.DeepClone(),
        ["narrative"] = Narrative,
        ["tags"] = Tags.DeepClone(),
        ["gather_quest_id"] = null,
        ["inherited_from_chunk_id"] = null,
    };
}

public sealed class Recipe
{
    public required string RecipeId { get; init; }
    public required string OutputId { get; init; }
    public required double OutputQty { get; init; }
    public required string StationType { get; init; }
    public required double StationTier { get; init; }
    public JsonNode Inputs { get; init; } = new JsonArray();
    public bool IsEnchantment { get; init; }
    public string EnchantmentName { get; init; } = "";
    public JsonNode ApplicableTo { get; init; } = new JsonArray();
    public JsonNode Effect { get; init; } = new JsonObject();

    public JsonObject ToParityNode() => new()
    {
        ["recipe_id"] = RecipeId,
        ["output_id"] = OutputId,
        ["output_qty"] = OutputQty,
        ["station_type"] = StationType,
        ["station_tier"] = StationTier,
        ["inputs"] = Inputs.DeepClone(),
        ["grid_size"] = "3x3",
        ["mini_game_type"] = "",
        ["metadata"] = new JsonObject(),
        ["is_enchantment"] = IsEnchantment,
        ["enchantment_name"] = EnchantmentName,
        ["applicable_to"] = ApplicableTo.DeepClone(),
        ["effect"] = Effect.DeepClone(),
    };
}

public sealed class SkillDefinition
{
    public required string SkillId { get; init; }
    public required string Name { get; init; }
    public required double Tier { get; init; }
    public required string Rarity { get; init; }
    public JsonNode Categories { get; init; } = new JsonArray();
    public string Description { get; init; } = "";
    public string Narrative { get; init; } = "";
    public JsonNode Tags { get; init; } = new JsonArray();

    // effect
    public string EffectType { get; init; } = "";
    public string EffectCategory { get; init; } = "";
    public string EffectMagnitude { get; init; } = "";
    public string EffectTarget { get; init; } = "self";
    public string EffectDuration { get; init; } = "instant";
    public JsonNode AdditionalEffects { get; init; } = new JsonArray();

    // cost (string enum OR number — kept raw)
    public JsonNode CostMana { get; init; } = JsonValue.Create("moderate")!;
    public JsonNode CostCooldown { get; init; } = JsonValue.Create("moderate")!;

    // evolution
    public bool CanEvolve { get; init; }
    public string? NextSkillId { get; init; }
    public string EvolutionRequirement { get; init; } = "";

    // requirements
    public double RequiredCharacterLevel { get; init; } = 1;
    public JsonNode RequiredStats { get; init; } = new JsonObject();
    public JsonNode RequiredTitles { get; init; } = new JsonArray();

    public string? IconPath { get; init; }
    public JsonNode CombatTags { get; init; } = new JsonArray();
    public JsonNode CombatParams { get; init; } = new JsonObject();

    public JsonObject ToParityNode() => new()
    {
        ["skill_id"] = SkillId,
        ["name"] = Name,
        ["tier"] = Tier,
        ["rarity"] = Rarity,
        ["categories"] = Categories.DeepClone(),
        ["description"] = Description,
        ["narrative"] = Narrative,
        ["tags"] = Tags.DeepClone(),
        ["effect"] = new JsonObject
        {
            ["effect_type"] = EffectType,
            ["category"] = EffectCategory,
            ["magnitude"] = EffectMagnitude,
            ["target"] = EffectTarget,
            ["duration"] = EffectDuration,
            ["additional_effects"] = AdditionalEffects.DeepClone(),
        },
        ["cost"] = new JsonObject
        {
            ["mana"] = CostMana.DeepClone(),
            ["cooldown"] = CostCooldown.DeepClone(),
        },
        ["evolution"] = new JsonObject
        {
            ["can_evolve"] = CanEvolve,
            ["next_skill_id"] = NextSkillId is null ? null : JsonValue.Create(NextSkillId),
            ["requirement"] = EvolutionRequirement,
        },
        ["requirements"] = new JsonObject
        {
            ["character_level"] = RequiredCharacterLevel,
            ["stats"] = RequiredStats.DeepClone(),
            ["titles"] = RequiredTitles.DeepClone(),
        },
        ["icon_path"] = IconPath is null ? null : JsonValue.Create(IconPath),
        ["combat_tags"] = CombatTags.DeepClone(),
        ["combat_params"] = CombatParams.DeepClone(),
        ["taught_by_npc_id"] = null,
        ["rewarded_by_quest_id"] = null,
    };
}

public sealed class TitleDefinition
{
    public required string TitleId { get; init; }
    public required string Name { get; init; }
    public required string Tier { get; init; }
    public required string Category { get; init; }
    public required string BonusDescription { get; init; }
    public required JsonObject Bonuses { get; init; }

    /// <summary>Raw prerequisites JSON — the typed UnlockRequirements
    /// condition graph is a Phase-2 port (ICharacterQuery). Excluded from
    /// Phase-1 parity, matching the dump.</summary>
    public JsonObject RequirementsRaw { get; init; } = new();

    public bool Hidden { get; init; }
    public string AcquisitionMethod { get; init; } = "guaranteed_milestone";
    public JsonNode GenerationChance { get; init; } = JsonValue.Create(1.0)!;
    public string? IconPath { get; init; }
    public string ActivityType { get; init; } = "general";
    public JsonNode AcquisitionThreshold { get; init; } = JsonValue.Create(0)!;
    public JsonNode Prerequisites { get; init; } = new JsonArray();

    public JsonObject ToParityNode() => new()
    {
        ["title_id"] = TitleId,
        ["name"] = Name,
        ["tier"] = Tier,
        ["category"] = Category,
        ["bonus_description"] = BonusDescription,
        ["bonuses"] = Bonuses.DeepClone(),
        ["hidden"] = Hidden,
        ["acquisition_method"] = AcquisitionMethod,
        ["generation_chance"] = GenerationChance.DeepClone(),
        ["icon_path"] = IconPath is null ? null : JsonValue.Create(IconPath),
        ["activity_type"] = ActivityType,
        ["acquisition_threshold"] = AcquisitionThreshold.DeepClone(),
        ["prerequisites"] = Prerequisites.DeepClone(),
        ["granted_by_quest_id"] = null,
        ["granted_by_npc_id"] = null,
    };
}

public sealed class PlacementData
{
    public required string RecipeId { get; init; }
    public required string Discipline { get; init; }
    public string GridSize { get; init; } = "";
    public JsonNode PlacementMap { get; init; } = new JsonObject();
    public JsonNode CoreInputs { get; init; } = new JsonArray();
    public JsonNode SurroundingInputs { get; init; } = new JsonArray();
    public JsonNode Ingredients { get; init; } = new JsonArray();
    public JsonNode Slots { get; init; } = new JsonArray();
    public JsonNode Pattern { get; init; } = new JsonArray();
    public string Narrative { get; init; } = "";
    public string OutputId { get; init; } = "";
    public double StationTier { get; init; } = 1;

    public JsonObject ToParityNode() => new()
    {
        ["recipe_id"] = RecipeId,
        ["discipline"] = Discipline,
        ["grid_size"] = GridSize,
        ["placement_map"] = PlacementMap.DeepClone(),
        ["core_inputs"] = CoreInputs.DeepClone(),
        ["surrounding_inputs"] = SurroundingInputs.DeepClone(),
        ["ingredients"] = Ingredients.DeepClone(),
        ["slots"] = Slots.DeepClone(),
        ["pattern"] = Pattern.DeepClone(),
        ["narrative"] = Narrative,
        ["output_id"] = OutputId,
        ["station_tier"] = StationTier,
    };
}

public sealed class ResourceDrop
{
    public required string MaterialId { get; init; }
    public required string Quantity { get; init; }   // few/several/many/abundant
    public required string Chance { get; init; }     // guaranteed/high/moderate/low/rare/improbable

    // resources.py:14-22
    public (int Min, int Max) GetQuantityRange() => Quantity switch
    {
        "few" => (1, 2), "several" => (2, 4), "many" => (3, 5), "abundant" => (4, 8),
        _ => (1, 3),
    };

    // resources.py:24-34
    public double GetChanceValue() => Chance switch
    {
        "guaranteed" => 1.0, "high" => 0.8, "moderate" => 0.5,
        "low" => 0.25, "rare" => 0.1, "improbable" => 0.05,
        _ => 1.0,
    };

    public JsonObject ToParityNode() => new()
    {
        ["material_id"] = MaterialId,
        ["quantity"] = Quantity,
        ["chance"] = Chance,
    };
}

public sealed class ResourceNodeDefinition
{
    public required string ResourceId { get; init; }
    public required string Name { get; init; }
    public required string Category { get; init; }   // tree / ore / stone
    public required double Tier { get; init; }
    public required string RequiredTool { get; init; }
    public required double BaseHealth { get; init; }
    public List<ResourceDrop> Drops { get; init; } = new();
    public string? RespawnTime { get; init; }
    public JsonNode Tags { get; init; } = new JsonArray();
    public string Narrative { get; init; } = "";

    public bool IsTree => Category == "tree";
    public bool IsOre => Category == "ore";
    public bool IsStone => Category == "stone";

    // resources.py:56-76 — incl. the "quick" synonym (G18.4 fix)
    public double? GetRespawnSeconds() => RespawnTime switch
    {
        null => null,
        "quick" => 30.0, "fast" => 30.0, "normal" => 60.0,
        "slow" => 120.0, "very_slow" => 300.0,
        _ => 60.0,
    };

    public bool DoesRespawn => RespawnTime is not null;

    public JsonObject ToParityNode()
    {
        var drops = new JsonArray();
        foreach (var d in Drops) drops.Add(d.ToParityNode());
        return new JsonObject
        {
            ["resource_id"] = ResourceId,
            ["name"] = Name,
            ["category"] = Category,
            ["tier"] = Tier,
            ["required_tool"] = RequiredTool,
            ["base_health"] = BaseHealth,
            ["drops"] = drops,
            ["respawn_time"] = RespawnTime is null ? null : JsonValue.Create(RespawnTime),
            ["tags"] = Tags.DeepClone(),
            ["narrative"] = Narrative,
            ["inherited_from_chunk_id"] = null,
        };
    }
}

public sealed class NpcDefinition
{
    public required string NpcId { get; init; }
    public required string Name { get; init; }
    public string Title { get; init; } = "";
    public string Narrative { get; init; } = "";
    public JsonNode Personality { get; init; } = new JsonObject();
    public JsonNode Locality { get; init; } = new JsonObject();
    public JsonNode Faction { get; init; } = new JsonObject();
    public JsonNode AffinitySeeds { get; init; } = new JsonObject();
    public JsonNode Services { get; init; } = new JsonObject();
    public JsonNode UnlockConditions { get; init; } = new JsonObject();
    public JsonNode Speechbank { get; init; } = new JsonObject();
    public JsonNode Quests { get; init; } = new JsonArray();
    public double PosX { get; init; }
    public double PosY { get; init; }
    public double PosZ { get; init; }
    public JsonNode SpriteColor { get; init; } = new JsonArray(200, 200, 200);
    public double InteractionRadius { get; init; } = 3.0;
    public JsonNode Tags { get; init; } = new JsonArray();
    public List<string> DialogueLines { get; init; } = new();

    public JsonObject ToParityNode()
    {
        var lines = new JsonArray();
        foreach (var l in DialogueLines) lines.Add(l);
        return new JsonObject
        {
            ["npc_id"] = NpcId,
            ["name"] = Name,
            ["title"] = Title,
            ["narrative"] = Narrative,
            ["personality"] = Personality.DeepClone(),
            ["locality"] = Locality.DeepClone(),
            ["faction"] = Faction.DeepClone(),
            ["affinity_seeds"] = AffinitySeeds.DeepClone(),
            ["services"] = Services.DeepClone(),
            ["unlock_conditions"] = UnlockConditions.DeepClone(),
            ["speechbank"] = Speechbank.DeepClone(),
            ["quests"] = Quests.DeepClone(),
            ["position"] = new JsonObject { ["x"] = PosX, ["y"] = PosY, ["z"] = PosZ },
            ["sprite_color"] = SpriteColor.DeepClone(),
            ["interaction_radius"] = InteractionRadius,
            ["tags"] = Tags.DeepClone(),
            ["dialogue_lines"] = lines,
        };
    }
}

public sealed class QuestDefinition
{
    public required string QuestId { get; init; }
    public string Title { get; init; } = "";
    public string Description { get; init; } = "";
    public string NpcId { get; init; } = "";
    public string ObjectiveType { get; init; } = "gather";
    public JsonNode ObjectiveItems { get; init; } = new JsonArray();
    public double EnemiesKilled { get; init; }
    public JsonObject RewardsNode { get; init; } = new();
    public JsonNode CompletionDialogue { get; init; } = new JsonArray();
    public string Name { get; init; } = "";
    public string QuestType { get; init; } = "side";
    public long Tier { get; init; } = 1;
    public string GivenBy { get; init; } = "";
    public string ReturnTo { get; init; } = "";
    public JsonNode DescriptionFull { get; init; } = new JsonObject();
    public JsonNode RewardsProse { get; init; } = new JsonObject();
    public JsonNode Requirements { get; init; } = new JsonObject();
    public JsonNode Expiration { get; init; } = new JsonObject();
    public JsonNode Progression { get; init; } = new JsonObject();
    public string WnsThreadId { get; init; } = "";
    public JsonNode Tags { get; init; } = new JsonArray();
    public JsonNode Metadata { get; init; } = new JsonObject();
    public string SourceOrigin { get; init; } = "canonical";

    public JsonObject ToParityNode() => new()
    {
        ["quest_id"] = QuestId,
        ["title"] = Title,
        ["description"] = Description,
        ["npc_id"] = NpcId,
        ["objectives"] = new JsonObject
        {
            ["objective_type"] = ObjectiveType,
            ["items"] = ObjectiveItems.DeepClone(),
            ["enemies_killed"] = EnemiesKilled,
        },
        ["rewards"] = RewardsNode.DeepClone(),
        ["completion_dialogue"] = CompletionDialogue.DeepClone(),
        ["name"] = Name,
        ["quest_type"] = QuestType,
        ["tier"] = Tier,
        ["given_by"] = GivenBy,
        ["return_to"] = ReturnTo,
        ["description_full"] = DescriptionFull.DeepClone(),
        ["rewards_prose"] = RewardsProse.DeepClone(),
        ["requirements"] = Requirements.DeepClone(),
        ["expiration"] = Expiration.DeepClone(),
        ["progression"] = Progression.DeepClone(),
        ["wns_thread_id"] = WnsThreadId,
        ["tags"] = Tags.DeepClone(),
        ["metadata"] = Metadata.DeepClone(),
        ["source_origin"] = SourceOrigin,
    };
}

public sealed class ClassDefinition
{
    public required string ClassId { get; init; }
    public required string Name { get; init; }
    public required string Description { get; init; }
    public required JsonObject Bonuses { get; init; }
    public string StartingSkill { get; init; } = "";
    public JsonNode RecommendedStats { get; init; } = new JsonArray();
    public JsonNode Tags { get; init; } = new JsonArray();
    public JsonNode PreferredDamageTypes { get; init; } = new JsonArray();
    public string PreferredArmorType { get; init; } = "";

    /// <summary>classes.py:33-46 — +5% per matching tag (case-insensitive
    /// set intersection), capped at +20%. Sacred class-affinity component of
    /// the damage pipeline.</summary>
    public double GetSkillAffinityBonus(IReadOnlyList<string> skillTags)
    {
        var ownTags = Tags is JsonArray arr
            ? arr.OfType<JsonValue>()
                 .Select(v => v.TryGetValue<string>(out var s) ? s.ToLowerInvariant() : null)
                 .Where(s => s is not null).Cast<string>().ToHashSet()
            : new HashSet<string>();
        if (skillTags.Count == 0 || ownTags.Count == 0)
            return 0.0;
        var matching = skillTags.Select(t => t.ToLowerInvariant()).ToHashSet();
        matching.IntersectWith(ownTags);
        return Math.Min(matching.Count * 0.05, 0.20);
    }

    public JsonObject ToParityNode() => new()
    {
        ["class_id"] = ClassId,
        ["name"] = Name,
        ["description"] = Description,
        ["bonuses"] = Bonuses.DeepClone(),
        ["starting_skill"] = StartingSkill,
        ["recommended_stats"] = RecommendedStats.DeepClone(),
        ["tags"] = Tags.DeepClone(),
        ["preferred_damage_types"] = PreferredDamageTypes.DeepClone(),
        ["preferred_armor_type"] = PreferredArmorType,
    };
}
