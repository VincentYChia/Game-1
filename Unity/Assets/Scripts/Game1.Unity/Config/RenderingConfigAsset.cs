// ============================================================================
// Game1.Unity.Config.RenderingConfigAsset
// Migrated from: rendering/renderer.py (visual constants)
// Migration phase: 6
// Date: 2026-02-13
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Rendering-specific configuration asset.
    /// </summary>
    [CreateAssetMenu(fileName = "RenderingConfig", menuName = "Game1/RenderingConfig")]
    public class RenderingConfigAsset : ScriptableObject
    {
        [Header("Tile Colors")]
        public Color GrassColor = new Color(34 / 255f, 139 / 255f, 34 / 255f);
        public Color WaterColor = new Color(30 / 255f, 144 / 255f, 255 / 255f);
        public Color StoneColor = new Color(128 / 255f, 128 / 255f, 128 / 255f);
        public Color SandColor = new Color(238 / 255f, 214 / 255f, 175 / 255f);
        public Color CaveColor = new Color(64 / 255f, 64 / 255f, 64 / 255f);
        public Color SnowColor = new Color(240 / 255f, 240 / 255f, 255 / 255f);
        public Color DirtColor = new Color(139 / 255f, 90 / 255f, 43 / 255f);

        [Header("Day/Night Cycle")]
        public Color DawnTint = new Color(1f, 0.85f, 0.7f, 0.15f);
        public Color DayTint = new Color(1f, 1f, 1f, 0f);
        public Color DuskTint = new Color(0.8f, 0.5f, 0.3f, 0.2f);
        public Color NightTint = new Color(0.1f, 0.1f, 0.3f, 0.5f);

        [Header("Sprite Atlases")]
        public Sprite DefaultTileSprite;
        public Sprite DefaultItemIcon;
        public Sprite DefaultEnemySprite;
        public Sprite DefaultResourceSprite;
    }
}
