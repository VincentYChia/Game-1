// ============================================================================
// Game1.Unity.Config.GameConfigAsset
// Migrated from: core/config.py (Unity-specific display/camera settings)
// Migration phase: 6
// Date: 2026-02-13
//
// ScriptableObject for Unity-specific settings (camera, display, performance).
// Game balance constants remain in Game1.Core.GameConfig (Phase 1).
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Unity-specific configuration as a ScriptableObject.
    /// Game balance/formula constants stay in Game1.Core.GameConfig.
    /// This only holds display, camera, and performance tuning.
    /// </summary>
    [CreateAssetMenu(fileName = "GameConfig", menuName = "Game1/GameConfig")]
    public class GameConfigAsset : ScriptableObject
    {
        [Header("Display")]
        public int ReferenceWidth = 1600;
        public int ReferenceHeight = 900;
        public int TargetFPS = 60;

        [Header("Camera")]
        public float CameraFollowSpeed = 8f;
        public float MinZoom = 3f;
        public float MaxZoom = 15f;
        public float DefaultZoom = 8f;
        public float ZoomSpeed = 2f;
        public float CameraHeight = 50f;

        [Header("Performance")]
        public int ChunkLoadRadius = 4;
        public int ChunkUnloadRadius = 6;
        public int MaxEnemiesPerChunk = 8;

        [Header("Rendering")]
        public int PixelsPerUnit = 32;
        public FilterMode SpriteFilterMode = FilterMode.Point;

        [Header("UI")]
        public int InventorySlotSize = 40;
        public int InventorySlotPadding = 4;
        public int TooltipPadding = 8;
        public float TooltipDelay = 0.3f;

        [Header("Effects")]
        public float DamageNumberRiseSpeed = 30f;
        public float DamageNumberLifetime = 1.5f;
        public float AttackLineDuration = 0.3f;
        public float AttackLineFadeStart = 0.7f;
    }
}
