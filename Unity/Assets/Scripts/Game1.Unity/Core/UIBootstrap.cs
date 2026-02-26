// ============================================================================
// Game1.Unity.Core.UIBootstrap
// Created: 2026-02-26
//
// Lightweight UI initialization for scenes where SceneBootstrapper is absent.
// Creates Canvas hierarchy + panel MonoBehaviours. Each panel self-builds its
// own UI in Start() via _buildUI(), finds managers via FindFirstObjectByType,
// and subscribes to InputManager events for key-toggle functionality.
//
// Called from CameraController's auto-bootstrap fallback path.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.UI;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Creates UI canvases and panel GameObjects when SceneBootstrapper didn't run.
    /// Idempotent — safe to call multiple times.
    /// </summary>
    public static class UIBootstrap
    {
        private static bool _initialized;

        /// <summary>
        /// Ensure all UI canvases and panel components exist.
        /// Each panel's Start() handles its own UI construction and event wiring.
        /// </summary>
        public static void EnsureUIExists()
        {
            if (_initialized) return;
            if (GameObject.Find("Panel_Canvas") != null)
            {
                _initialized = true;
                return;
            }

            Debug.Log("[UIBootstrap] No UI canvases found — creating UI hierarchy");

            // EventSystem (required for UI raycasting)
            UIHelper.EnsureEventSystem();

            // ================================================================
            // HUD Canvas (sortOrder 0) — always visible during gameplay
            // ================================================================
            var hud = UIHelper.CreateCanvas("HUD_Canvas", 0);

            _addPanel<StatusBarUI>(hud.transform, "StatusBarUI",
                new Vector2(0.01f, 0.88f), new Vector2(0.35f, 0.99f));

            _addPanel<SkillBarUI>(hud.transform, "SkillBarUI",
                new Vector2(0.3f, 0.01f), new Vector2(0.7f, 0.07f));

            _addPanel<NotificationUI>(hud.transform, "NotificationUI",
                new Vector2(0.65f, 0.01f), new Vector2(0.99f, 0.25f));

            _addPanel<DebugOverlay>(hud.transform, "DebugOverlay",
                new Vector2(0.01f, 0.60f), new Vector2(0.35f, 0.87f));

            // Crosshair (center dot)
            var crosshairGO = new GameObject("Crosshair");
            crosshairGO.transform.SetParent(hud.transform, false);
            var crosshairRT = crosshairGO.AddComponent<RectTransform>();
            crosshairRT.anchorMin = new Vector2(0.5f, 0.5f);
            crosshairRT.anchorMax = new Vector2(0.5f, 0.5f);
            crosshairRT.sizeDelta = new Vector2(6, 6);
            crosshairRT.anchoredPosition = Vector2.zero;
            var crosshairImg = crosshairGO.AddComponent<Image>();
            crosshairImg.color = new Color(1f, 1f, 1f, 0.7f);
            crosshairImg.raycastTarget = false;

            // ================================================================
            // Panel Canvas (sortOrder 10) — modal UI panels (one at a time)
            // ================================================================
            var panels = UIHelper.CreateCanvas("Panel_Canvas", 10);

            // Key-toggle panels (hotkey → GameState)
            _addPanel<InventoryUI>(panels.transform, "InventoryUI",           // Tab
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<EquipmentUI>(panels.transform, "EquipmentUI",           // I
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<StatsUI>(panels.transform, "StatsUI",                   // C
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<SkillsMenuUI>(panels.transform, "SkillsMenuUI",         // K
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<MapUI>(panels.transform, "MapUI",                       // M
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<EncyclopediaUI>(panels.transform, "EncyclopediaUI",     // J
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            // Non-toggle panels (opened by interaction or game flow)
            _addPanel<CraftingUI>(panels.transform, "CraftingUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<ChestUI>(panels.transform, "ChestUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _addPanel<NPCDialogueUI>(panels.transform, "NPCDialogueUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<TitleUI>(panels.transform, "TitleUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _addPanel<SaveLoadUI>(panels.transform, "SaveLoadUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            // ================================================================
            // Overlay Canvas (sortOrder 30) — always-on-top (tooltips, drag)
            // ================================================================
            var overlay = UIHelper.CreateCanvas("Overlay_Canvas", 30);

            _addPanel<TooltipRenderer>(overlay.transform, "TooltipRenderer",
                Vector2.zero, Vector2.one);

            _addPanel<DragDropManager>(overlay.transform, "DragDropManager",
                Vector2.zero, Vector2.one);

            _initialized = true;
            Debug.Log("[UIBootstrap] UI hierarchy created (HUD + Panels + Overlay)");
        }

        // ====================================================================
        // Helper: Create a panel GameObject with RectTransform + MonoBehaviour
        // ====================================================================

        private static T _addPanel<T>(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax) where T : MonoBehaviour
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            return go.AddComponent<T>();
        }
    }
}
