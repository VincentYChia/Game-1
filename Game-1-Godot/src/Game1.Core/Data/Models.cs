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
