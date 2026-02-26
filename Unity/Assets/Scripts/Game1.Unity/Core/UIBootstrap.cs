// ============================================================================
// Game1.Unity.Core.UIBootstrap
// Created: 2026-02-26
//
// Lightweight UI initialization for scenes where SceneBootstrapper is absent.
// Creates Canvas hierarchy + panel MonoBehaviours. Each panel self-builds its
// own UI in Start() via _buildUI(), finds managers via static Instance props,
// and subscribes to InputManager events for key-toggle functionality.
//
// Called from CameraController's auto-bootstrap fallback path.
//
// IDEMPOTENT: Each canvas and panel is checked individually. A stale/empty
// Panel_Canvas (e.g. baked into the scene from a prior session) won't block
// creation of missing child panels.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.UI;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Creates UI canvases and panel GameObjects when SceneBootstrapper didn't run.
    /// Truly idempotent — checks each panel individually, safe to call multiple times.
    /// </summary>
    public static class UIBootstrap
    {
        // NOTE: Do NOT use static bool for initialization tracking — static fields
        // persist across Editor Play sessions in Unity and cause the bootstrap
        // to be skipped on second run. Always check scene state directly.

        /// <summary>
        /// Ensure all UI canvases and panel components exist.
        /// Each panel's Start() handles its own UI construction and event wiring.
        /// </summary>
        public static void EnsureUIExists()
        {
            Debug.Log("[UIBootstrap] EnsureUIExists() — checking canvases and panels...");

            // EventSystem (required for UI raycasting)
            UIHelper.EnsureEventSystem();

            // ================================================================
            // HUD Canvas (sortOrder 0) — always visible during gameplay
            // ================================================================
            var hud = _findOrCreateCanvas("HUD_Canvas", 0);

            _ensurePanel<StatusBarUI>(hud.transform, "StatusBarUI",
                new Vector2(0.01f, 0.88f), new Vector2(0.35f, 0.99f));

            _ensurePanel<SkillBarUI>(hud.transform, "SkillBarUI",
                new Vector2(0.3f, 0.01f), new Vector2(0.7f, 0.07f));

            _ensurePanel<NotificationUI>(hud.transform, "NotificationUI",
                new Vector2(0.65f, 0.01f), new Vector2(0.99f, 0.25f));

            _ensurePanel<DebugOverlay>(hud.transform, "DebugOverlay",
                new Vector2(0.01f, 0.60f), new Vector2(0.35f, 0.87f));

            // Crosshair (center dot)
            if (hud.transform.Find("Crosshair") == null)
            {
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
            }

            // ================================================================
            // Panel Canvas (sortOrder 10) — modal UI panels (one at a time)
            // ================================================================
            var panels = _findOrCreateCanvas("Panel_Canvas", 10);

            // Key-toggle panels (hotkey → GameState)
            _ensurePanel<InventoryUI>(panels.transform, "InventoryUI",           // Tab
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<EquipmentUI>(panels.transform, "EquipmentUI",           // I
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<StatsUI>(panels.transform, "StatsUI",                   // C
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<SkillsMenuUI>(panels.transform, "SkillsMenuUI",         // K
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<MapUI>(panels.transform, "MapUI",                       // M
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<EncyclopediaUI>(panels.transform, "EncyclopediaUI",     // J
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            // Non-toggle panels (opened by interaction or game flow)
            _ensurePanel<CraftingUI>(panels.transform, "CraftingUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<ChestUI>(panels.transform, "ChestUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _ensurePanel<NPCDialogueUI>(panels.transform, "NPCDialogueUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<TitleUI>(panels.transform, "TitleUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<SaveLoadUI>(panels.transform, "SaveLoadUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _ensurePanel<StartMenuUI>(panels.transform, "StartMenuUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _ensurePanel<ClassSelectionUI>(panels.transform, "ClassSelectionUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _ensurePanel<SkillUnlockUI>(panels.transform, "SkillUnlockUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            // ================================================================
            // Overlay Canvas (sortOrder 30) — always-on-top (tooltips, drag)
            // ================================================================
            var overlay = _findOrCreateCanvas("Overlay_Canvas", 30);

            _ensurePanel<TooltipRenderer>(overlay.transform, "TooltipRenderer",
                Vector2.zero, Vector2.one);

            _ensurePanel<DragDropManager>(overlay.transform, "DragDropManager",
                Vector2.zero, Vector2.one);

            Debug.Log("[UIBootstrap] UI hierarchy verified/created.");
        }

        // ====================================================================
        // Helper: Find existing canvas or create a new one
        // ====================================================================

        private static Transform _findOrCreateCanvas(string name, int sortOrder)
        {
            var existing = GameObject.Find(name);
            if (existing != null)
            {
                // Ensure all required Canvas components exist (stale scene objects
                // may have a Canvas but lack CanvasScaler or GraphicRaycaster)
                if (existing.GetComponent<Canvas>() == null)
                {
                    var canvas = existing.AddComponent<Canvas>();
                    canvas.renderMode = RenderMode.ScreenSpaceOverlay;
                    canvas.sortingOrder = sortOrder;
                }
                if (existing.GetComponent<CanvasScaler>() == null)
                {
                    var scaler = existing.AddComponent<CanvasScaler>();
                    scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
                    scaler.referenceResolution = new Vector2(1920, 1080);
                    scaler.matchWidthOrHeight = 0.5f;
                }
                if (existing.GetComponent<GraphicRaycaster>() == null)
                    existing.AddComponent<GraphicRaycaster>();

                return existing.transform;
            }

            return UIHelper.CreateCanvas(name, sortOrder).transform;
        }

        // ====================================================================
        // Helper: Ensure a panel exists as a child with the correct component
        // ====================================================================

        private static T _ensurePanel<T>(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax) where T : MonoBehaviour
        {
            // Check if this panel already exists as a child
            var child = parent.Find(name);
            if (child != null)
            {
                var existing = child.GetComponent<T>();
                if (existing != null) return existing;

                // Child exists but lacks the component — add it
                return child.gameObject.AddComponent<T>();
            }

            // Create from scratch
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
