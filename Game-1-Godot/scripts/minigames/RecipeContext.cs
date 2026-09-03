using System.Collections.Generic;

namespace Game1.Godot;

/// <summary>
/// The recipe a minigame is playing — handed in so play can be driven by the material/output
/// TAGS, not just an abstract difficulty number. Built Godot-side by CraftingScreen from the
/// certified Recipe + MaterialDatabase (Core untouched). Null for non-crafting launches
/// (fishing / harvest), so every minigame must degrade gracefully when Recipe is null.
///
/// See Development-Plan/MINIGAME_TAG_EFFECTS.md for how tags map to effects.
/// </summary>
public sealed class RecipeContext
{
    public string OutputId = "";
    public List<string> OutputTags = new();     // metadata.tags of the crafted output (sets the target/character)
    public List<Ingredient> Inputs = new();      // one per recipe input line (per-ingredient behavior)
    public double Points;
    public string Tier = "common";

    public sealed class Ingredient
    {
        public string Id = "";
        public string Name = "";
        public List<string> Tags = new();        // ordered metadata.tags — precedence is list order
        public int Qty = 1;
        public int MaterialTier = 1;
    }
}
