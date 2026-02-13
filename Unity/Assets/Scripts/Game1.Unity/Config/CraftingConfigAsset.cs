// ============================================================================
// Game1.Unity.Config.CraftingConfigAsset
// Migrated from: Crafting-subdisciplines/* (visual settings)
// Migration phase: 6
// Date: 2026-02-13
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Unity-specific crafting visual configuration.
    /// Crafting formulas/balance live in Phase 4 C# classes.
    /// </summary>
    [CreateAssetMenu(fileName = "CraftingConfig", menuName = "Game1/CraftingConfig")]
    public class CraftingConfigAsset : ScriptableObject
    {
        [Header("Smithing Visuals")]
        public Color SmithingHotColor = new Color(1f, 0.3f, 0f);
        public Color SmithingColdColor = new Color(0.2f, 0.2f, 0.8f);
        public Color SmithingPerfectZone = new Color(0f, 1f, 0f, 0.3f);

        [Header("Alchemy Visuals")]
        public Color AlchemyStableColor = new Color(0f, 0.8f, 0f);
        public Color AlchemyUnstableColor = new Color(0.8f, 0f, 0f);
        public Color AlchemySweetSpotColor = new Color(1f, 1f, 0f, 0.4f);

        [Header("Refining Visuals")]
        public Color RefiningAlignedColor = new Color(0f, 1f, 0f);
        public Color RefiningMisalignedColor = new Color(1f, 0f, 0f);

        [Header("Engineering Visuals")]
        public Color EngineeringConnectedColor = new Color(0f, 0.8f, 0f);
        public Color EngineeringDisconnectedColor = new Color(0.5f, 0.5f, 0.5f);

        [Header("Enchanting Visuals")]
        public Color EnchantingBonusZone = new Color(0f, 1f, 0f, 0.5f);
        public Color EnchantingPenaltyZone = new Color(1f, 0f, 0f, 0.5f);
        public Color EnchantingNeutralZone = new Color(0.5f, 0.5f, 0.5f, 0.3f);

        [Header("Grid Sizes")]
        public int MinGridSize = 3;
        public int MaxGridSize = 9;

        [Header("Animation")]
        public float MinigameTransitionSpeed = 5f;
        public float ResultDisplayDuration = 2f;
    }
}
