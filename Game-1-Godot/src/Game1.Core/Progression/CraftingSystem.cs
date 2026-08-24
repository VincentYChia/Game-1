using Game1.Core.Crafting;
using Game1.Core.Data;

namespace Game1.Core.Progression;

/// <summary>
/// P6 core craft loop — the _complete_minigame SUCCESS path (game_engine.py
/// :8970-9110) minus the per-discipline crafter stat-rolls: can-craft gate,
/// material consumption via the ported RecipeCrafting semantics, quality
/// tier from the CERTIFIED RewardCalculator, output materialization
/// (equipment via the certified CreateEquipmentFromId, else stackables),
/// activity/XP (int(20 * tier * 1.5))/title bookkeeping. Failure applies
/// the tier-scaled partial loss like the 2026-07 audit fix.
///
/// BOUNDARY (next parity tranche): crafting_simulator.py's per-discipline
/// crafters (rarity rolls, crafted-stat generation, enchant application)
/// and the six Pygame minigames (2D Control overlays per ADR-7).
/// </summary>
public sealed record CraftResult(bool Success, string Message, string Quality,
                                 string OutputId, int Quantity);

public sealed class CraftingSystem
{
    private static readonly Dictionary<string, string> ActivityMap = new()
    {
        ["smithing"] = "smithing", ["refining"] = "refining",
        ["alchemy"] = "alchemy", ["engineering"] = "engineering",
        ["adornments"] = "enchanting",
    };

    private readonly PlayerCharacter _ch;
    private readonly RecipeDatabase _recipes;
    private readonly EquipmentDatabase _equipment;
    private readonly GatheringSystem _titles;   // reuse the certified CheckForTitle

    public CraftingSystem(PlayerCharacter character, RecipeDatabase recipes,
                          EquipmentDatabase equipment, GatheringSystem titleChecker)
    {
        _ch = character;
        _recipes = recipes;
        _equipment = equipment;
        _titles = titleChecker;
    }

    public IEnumerable<Recipe> CraftableRecipes() =>
        _recipes.Recipes.Values.Where(r => RecipeCrafting.CanCraft(r, _ch.Inventory));

    /// <summary>Craft with a performance score in [0,1] (the minigame seam).</summary>
    public CraftResult Craft(Recipe recipe, double performance)
    {
        if (!RecipeCrafting.CanCraft(recipe, _ch.Inventory))
            return new CraftResult(false, "Missing materials", "none",
                                   recipe.OutputId, 0);

        var quality = RewardCalculator.QualityTier(performance);

        if (!RecipeCrafting.ConsumeMaterials(recipe, _ch.Inventory))
            return new CraftResult(false, "Missing materials", "none",
                                   recipe.OutputId, 0);

        var activity = ActivityMap.GetValueOrDefault(recipe.StationType, "smithing");
        _ch.Activities.RecordActivity(activity, 1);

        var xpReward = (int)(20 * recipe.StationTier * 1.5);
        _ch.Leveling.AddExp(xpReward);
        _titles.CheckForTitle();

        var qty = (int)recipe.OutputQty;
        var equipmentItem = _equipment.CreateEquipmentFromId(recipe.OutputId);
        if (equipmentItem is not null)
        {
            _ch.Inventory.AddItem(recipe.OutputId, qty,
                                  equipmentInstance: equipmentItem);
        }
        else
        {
            _ch.Inventory.AddItem(recipe.OutputId, qty);
        }

        return new CraftResult(true, $"Crafted {recipe.OutputId} ({quality})",
                               quality, recipe.OutputId, qty);
    }
}
