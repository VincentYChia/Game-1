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
//
// IMPORTANT: All containers use full-stretch anchors (0,0)-(1,1). Each panel's
// _buildUI() handles its own positioning. Do NOT set specific anchors here —
// it creates a double-nesting problem where _buildUI positions relative to
// the container instead of the canvas, causing offset/duplicate visuals.
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

            _ensurePanel<StatusBarUI>(hud.transform, "StatusBarUI");
            _ensurePanel<SkillBarUI>(hud.transform, "SkillBarUI");
            _ensurePanel<NotificationUI>(hud.transform, "NotificationUI");
            _ensurePanel<DebugOverlay>(hud.transform, "DebugOverlay");

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
            _ensurePanel<InventoryUI>(panels.transform, "InventoryUI");
            _ensurePanel<EquipmentUI>(panels.transform, "EquipmentUI");
            _ensurePanel<StatsUI>(panels.transform, "StatsUI");
            _ensurePanel<SkillsMenuUI>(panels.transform, "SkillsMenuUI");
            _ensurePanel<MapUI>(panels.transform, "MapUI");
            _ensurePanel<EncyclopediaUI>(panels.transform, "EncyclopediaUI");

            // Non-toggle panels (opened by interaction or game flow)
            _ensurePanel<CraftingUI>(panels.transform, "CraftingUI");
            _ensurePanel<ChestUI>(panels.transform, "ChestUI");
            _ensurePanel<NPCDialogueUI>(panels.transform, "NPCDialogueUI");
            _ensurePanel<TitleUI>(panels.transform, "TitleUI");
            _ensurePanel<SaveLoadUI>(panels.transform, "SaveLoadUI");
            _ensurePanel<StartMenuUI>(panels.transform, "StartMenuUI");
            _ensurePanel<ClassSelectionUI>(panels.transform, "ClassSelectionUI");
            _ensurePanel<SkillUnlockUI>(panels.transform, "SkillUnlockUI");

            // ================================================================
            // Overlay Canvas (sortOrder 30) — always-on-top (tooltips, drag)
            // ================================================================
            var overlay = _findOrCreateCanvas("Overlay_Canvas", 30);

            _ensurePanel<TooltipRenderer>(overlay.transform, "TooltipRenderer");
            _ensurePanel<DragDropManager>(overlay.transform, "DragDropManager");

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
        // Helper: Ensure a panel exists as a child with the correct component.
        //
        // All containers use full-stretch anchors (0,0)-(1,1). Each panel's
        // _buildUI() creates its own positioned child panel. This avoids
        // double-nesting where _buildUI positions relative to a container
        // instead of the canvas, causing offset/duplicate visuals.
        // ====================================================================

        private static T _ensurePanel<T>(Transform parent, string name)
            where T : MonoBehaviour
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

            // Create from scratch — full-stretch container
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            return go.AddComponent<T>();
        }
    }
}
