// ============================================================================
// Game1.Unity.Utilities.ColorConverter
// Migrated from: N/A (new — bridges Phase 1-5 color tuples to Unity Color32)
// Migration phase: 6
// Date: 2026-02-13
// ============================================================================

using UnityEngine;
using Game1.Core;

namespace Game1.Unity.Utilities
{
    /// <summary>
    /// Converts between Phase 1-5 color tuples (byte R, byte G, byte B, byte A)
    /// and Unity's Color32/Color types.
    /// AC-002: Phases 1-5 use value tuples, Phase 6 needs Unity colors.
    /// </summary>
    public static class ColorConverter
    {
        /// <summary>
        /// Convert a Phase 1-5 color tuple to Unity Color32.
        /// </summary>
        public static Color32 ToColor32((byte R, byte G, byte B, byte A) tuple)
        {
            return new Color32(tuple.R, tuple.G, tuple.B, tuple.A);
        }

        /// <summary>
        /// Convert a Phase 1-5 color tuple to Unity Color (float 0-1).
        /// </summary>
        public static Color ToColor((byte R, byte G, byte B, byte A) tuple)
        {
            return new Color(tuple.R / 255f, tuple.G / 255f, tuple.B / 255f, tuple.A / 255f);
        }

        /// <summary>
        /// Convert a Unity Color32 back to Phase 1-5 tuple format.
        /// </summary>
        public static (byte R, byte G, byte B, byte A) FromColor32(Color32 color)
        {
            return (color.r, color.g, color.b, color.a);
        }

        /// <summary>
        /// Get rarity color as Unity Color32 from rarity string.
        /// </summary>
        public static Color32 GetRarityColor32(string rarity)
        {
            return ToColor32(GameConfig.GetRarityColor(rarity));
        }

        /// <summary>
        /// Get rarity color as Unity Color from rarity string.
        /// </summary>
        public static Color GetRarityColor(string rarity)
        {
            return ToColor(GameConfig.GetRarityColor(rarity));
        }

        // ====================================================================
        // Tile Colors (from renderer.py, preserved exactly)
        // ====================================================================

        public static readonly Color32 TileGrass   = new Color32(34, 139, 34, 255);
        public static readonly Color32 TileWater   = new Color32(30, 144, 255, 255);
        public static readonly Color32 TileStone   = new Color32(128, 128, 128, 255);
        public static readonly Color32 TileSand    = new Color32(238, 214, 175, 255);
        public static readonly Color32 TileCave    = new Color32(64, 64, 64, 255);
        public static readonly Color32 TileSnow    = new Color32(240, 240, 255, 255);
        public static readonly Color32 TileDirt    = new Color32(139, 90, 43, 255);

        // ====================================================================
        // UI Colors
        // ====================================================================

        public static readonly Color32 UIBackground  = new Color32(30, 30, 30, 220);
        public static readonly Color32 UIBorder      = new Color32(80, 80, 80, 255);
        public static readonly Color32 UIHighlight   = new Color32(255, 255, 100, 255);
        public static readonly Color32 UISlotEmpty   = new Color32(50, 50, 50, 200);
        public static readonly Color32 UISlotHover   = new Color32(80, 80, 80, 200);

        // Damage number colors
        public static readonly Color32 DamagePhysical  = new Color32(255, 255, 255, 255);
        public static readonly Color32 DamageFire      = new Color32(255, 100, 30, 255);
        public static readonly Color32 DamageIce       = new Color32(100, 200, 255, 255);
        public static readonly Color32 DamageLightning = new Color32(255, 255, 50, 255);
        public static readonly Color32 DamagePoison    = new Color32(100, 255, 100, 255);
        public static readonly Color32 DamageHeal      = new Color32(50, 255, 50, 255);
        public static readonly Color32 DamageCrit      = new Color32(255, 50, 50, 255);
    }
}
