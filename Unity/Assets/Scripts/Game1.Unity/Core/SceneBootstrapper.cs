// ============================================================================
// Game1.Unity.Core.SceneBootstrapper
// Created: 2026-02-25
//
// Programmatic scene construction — the cornerstone of the Unity project.
// There are NO Unity scene files, prefabs, or materials checked in; this
// MonoBehaviour creates the entire scene hierarchy from code in Awake().
//
// Execution order -1000 guarantees it runs before every other MonoBehaviour
// so that all GameObjects exist by the time their Awake() methods fire.
//
// Hierarchy created:
//   EventSystem
//   DirectionalLight
//   Managers          (GameStateManager, InputManager, GameManager)
//   PlayerRig         (PlayerController → MainCamera w/ CameraController)
//   WorldRenderer     (WorldRenderer, TerrainMaterialManager)
//   Utilities         (SpriteDatabase, DamageNumbers, AttackEffects, Particles)
//   HUD_Canvas        (StatusBar, SkillBar, Notification, Debug, DayNight)
//   Panel_Canvas      (all menu/panel UIs)
//   Minigame_Canvas   (crafting minigame UIs)
//   Overlay_Canvas    (Tooltip, DragDrop)
// ============================================================================

using UnityEngine;
using UnityEngine.EventSystems;
using Game1.Unity.Core;
using Game1.Unity.UI;
using Game1.Unity.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Creates the entire Unity scene programmatically on startup.
    /// Attach this to an empty GameObject in the bootstrap scene.
    /// DefaultExecutionOrder(-1000) ensures it runs before all other scripts.
    /// </summary>
    [DefaultExecutionOrder(-1000)]
    public class SceneBootstrapper : MonoBehaviour
    {
        // ====================================================================
        // Cached References (available after Awake for wiring)
        // ====================================================================

        private GameStateManager _stateManager;
        private InputManager _inputManager;
        private GameManager _gameManager;
        private CameraController _cameraController;
        private PlayerController _playerController;

        // ====================================================================
        // Bootstrap Entry Point
        // ====================================================================

        private void Awake()
        {
            Debug.Log("[SceneBootstrapper] Building scene hierarchy...");

            // Step 1: EventSystem
            _createEventSystem();

            // Step 2: Lighting
            _createLighting();

            // Step 3: Managers
            _createManagers();

            // Step 4: Player Rig (First Person)
            _createPlayerRig();

            // Step 5: World Rendering
            _createWorldRenderer();

            // Step 6: Utilities
            _createUtilities();

            // Step 7: Canvas Hierarchy (4 layers)
            _createHUDCanvas();
            _createPanelCanvas();
            _createMinigameCanvas();
            _createOverlayCanvas();

            // Step 8: Wire Cross-References
            _wireReferences();

            Debug.Log("[SceneBootstrapper] Scene hierarchy complete.");

            // [DBG] Dump full hierarchy for debugging
            _dumpHierarchy(); // DBG
        }

        // ====================================================================
        // [DBG] Hierarchy Dump
        // ====================================================================

        private void _dumpHierarchy() // DBG
        { // DBG
            Debug.Log("[DBG:BOOT:HIERARCHY] === Full Scene Hierarchy ==="); // DBG
            foreach (var root in gameObject.scene.GetRootGameObjects()) // DBG
            { // DBG
                _dumpGameObject(root, 0); // DBG
            } // DBG
            // Also dump DontDestroyOnLoad objects // DBG
            Debug.Log("[DBG:BOOT:HIERARCHY] === DontDestroyOnLoad Objects ==="); // DBG
            var ddolScene = UnityEngine.SceneManagement.SceneManager.GetSceneAt(0); // DBG
            // We can't easily enumerate DDOL, but we know Managers is there // DBG
            if (_gameManager != null) // DBG
            { // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Managers GO scene: {_gameManager.gameObject.scene.name}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Managers GO active: {_gameManager.gameObject.activeInHierarchy}"); // DBG
            } // DBG
            if (_playerController != null) // DBG
            { // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] PlayerRig GO scene: {_playerController.gameObject.scene.name}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] PlayerRig GO active: {_playerController.gameObject.activeInHierarchy}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] PlayerRig childCount: {_playerController.transform.childCount}"); // DBG
                for (int i = 0; i < _playerController.transform.childCount; i++) // DBG
                { // DBG
                    var child = _playerController.transform.GetChild(i); // DBG
                    Debug.Log($"[DBG:BOOT:HIERARCHY]   Child[{i}]: {child.name} (components: {_getComponentNames(child.gameObject)})"); // DBG
                    Debug.Log($"[DBG:BOOT:HIERARCHY]     parent={child.parent?.name}, localPos={child.localPosition}"); // DBG
                } // DBG
            } // DBG
            if (_cameraController != null) // DBG
            { // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Camera GO: {_cameraController.gameObject.name}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Camera parent: {_cameraController.transform.parent?.name ?? "NULL"}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Camera scene: {_cameraController.gameObject.scene.name}"); // DBG
                Debug.Log($"[DBG:BOOT:HIERARCHY] Camera active: {_cameraController.gameObject.activeInHierarchy}"); // DBG
            } // DBG
        } // DBG

        private void _dumpGameObject(GameObject go, int depth) // DBG
        { // DBG
            string indent = new string(' ', depth * 2); // DBG
            string components = _getComponentNames(go); // DBG
            Debug.Log($"[DBG:BOOT:HIERARCHY] {indent}{go.name} [{components}] active={go.activeSelf}"); // DBG
            for (int i = 0; i < go.transform.childCount; i++) // DBG
            { // DBG
                _dumpGameObject(go.transform.GetChild(i).gameObject, depth + 1); // DBG
            } // DBG
        } // DBG

        private string _getComponentNames(GameObject go) // DBG
        { // DBG
            var comps = go.GetComponents<Component>(); // DBG
            var names = new System.Text.StringBuilder(); // DBG
            foreach (var c in comps) // DBG
            { // DBG
                if (c is Transform) continue; // DBG
                if (names.Length > 0) names.Append(", "); // DBG
                names.Append(c.GetType().Name); // DBG
            } // DBG
            return names.ToString(); // DBG
        } // DBG

        // ====================================================================
        // Step 1: EventSystem
        // ====================================================================

        private void _createEventSystem()
        {
            UIHelper.EnsureEventSystem();
            Debug.Log("[SceneBootstrapper] EventSystem created.");
        }

        // ====================================================================
        // Step 2: Lighting
        // ====================================================================

        private void _createLighting()
        {
            var lightGO = new GameObject("DirectionalLight");
            var light = lightGO.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1f, 0.96f, 0.92f, 1f);
            light.intensity = 1.0f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.6f;
            light.shadowBias = 0.05f;
            light.shadowNormalBias = 0.4f;
            lightGO.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.6f, 1f);

            Shader skyboxShader = Shader.Find("Skybox/Procedural");
            if (skyboxShader != null)
            {
                var skyMat = new Material(skyboxShader);
                skyMat.SetFloat("_SunSize", 0.04f);
                skyMat.SetFloat("_SunSizeConvergence", 5f);
                skyMat.SetFloat("_AtmosphereThickness", 1.0f);
                skyMat.SetColor("_SkyTint", new Color(0.5f, 0.55f, 0.6f));
                skyMat.SetColor("_GroundColor", new Color(0.37f, 0.35f, 0.34f));
                skyMat.SetFloat("_Exposure", 1.3f);
                RenderSettings.skybox = skyMat;
            }

            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.7f, 0.75f, 0.85f);
            RenderSettings.fogStartDistance = 40f;
            RenderSettings.fogEndDistance = 120f;

            Debug.Log("[SceneBootstrapper] Lighting configured.");
        }

        // ====================================================================
        // Step 3: Managers
        // ====================================================================

        private void _createManagers()
        {
            var managersGO = new GameObject("Managers");

            Debug.Log("[DBG:BOOT:01] Creating Managers GO..."); // DBG

            _stateManager = managersGO.AddComponent<GameStateManager>();
            Debug.Log("[DBG:BOOT:02] GameStateManager added."); // DBG

            _inputManager = managersGO.AddComponent<InputManager>();
            Debug.Log("[DBG:BOOT:03] InputManager added."); // DBG

            // NOTE: AddComponent<GameManager>() triggers GameManager.Awake() INLINE,
            // which calls DontDestroyOnLoad(gameObject) — moves Managers to DDOL scene.
            _gameManager = managersGO.AddComponent<GameManager>();
            Debug.Log($"[DBG:BOOT:04] GameManager added. Managers scene now: {managersGO.scene.name}"); // DBG
            Debug.Log($"[DBG:BOOT:05] Managers GO active: {managersGO.activeInHierarchy}, path: {managersGO.transform.GetSiblingIndex()}"); // DBG

            Debug.Log("[SceneBootstrapper] Managers created.");
        }

        // ====================================================================
        // Step 4: Player Rig (First Person)
        // ====================================================================

        private void _createPlayerRig()
        {
            Debug.Log("[DBG:BOOT:10] Creating PlayerRig..."); // DBG

            var playerRigGO = new GameObject("PlayerRig");
            playerRigGO.transform.position = new Vector3(50f, 0f, 50f);

            Debug.Log($"[DBG:BOOT:11] PlayerRig created, scene: {playerRigGO.scene.name}"); // DBG

            _playerController = playerRigGO.AddComponent<PlayerController>();
            Debug.Log($"[DBG:BOOT:12] PlayerController added to PlayerRig"); // DBG

            // Child camera — SetParent BEFORE AddComponent so Awake sees correct parent
            var cameraGO = new GameObject("MainCamera");
            Debug.Log($"[DBG:BOOT:13] MainCamera created, parent BEFORE SetParent: {cameraGO.transform.parent?.name ?? "NULL"}"); // DBG

            cameraGO.transform.SetParent(playerRigGO.transform, false);
            Debug.Log($"[DBG:BOOT:14] MainCamera parent AFTER SetParent: {cameraGO.transform.parent?.name ?? "NULL"}"); // DBG

            cameraGO.transform.localPosition = new Vector3(0f, 1.6f, 0f);
            cameraGO.tag = "MainCamera";

            _cameraController = cameraGO.AddComponent<CameraController>();
            Debug.Log($"[DBG:BOOT:15] CameraController added. Camera parent: {cameraGO.transform.parent?.name ?? "NULL"}"); // DBG

            var camera = cameraGO.GetComponent<Camera>();
            if (camera == null)
                camera = cameraGO.AddComponent<Camera>();
            camera.fieldOfView = 70f;
            camera.nearClipPlane = 0.1f;
            camera.farClipPlane = 500f;
            camera.orthographic = false;

            cameraGO.AddComponent<AudioListener>();

            Debug.Log($"[DBG:BOOT:16] PlayerRig setup complete. Children: {playerRigGO.transform.childCount}"); // DBG
            Debug.Log($"[DBG:BOOT:17] Camera GO components: {_getComponentNames(cameraGO)}"); // DBG
            Debug.Log($"[DBG:BOOT:18] PlayerRig GO components: {_getComponentNames(playerRigGO)}"); // DBG

            Debug.Log("[SceneBootstrapper] Player rig created at (50, 0, 50).");
        }

        // ====================================================================
        // Step 5: World Rendering
        // ====================================================================

        private void _createWorldRenderer()
        {
            var worldGO = new GameObject("WorldRenderer");
            worldGO.AddComponent<WorldRenderer>();
            worldGO.AddComponent<TerrainMaterialManager>();

            Debug.Log("[SceneBootstrapper] World renderer created.");
        }

        // ====================================================================
        // Step 6: Utilities
        // ====================================================================

        private void _createUtilities()
        {
            var utilitiesGO = new GameObject("Utilities");
            utilitiesGO.AddComponent<SpriteDatabase>();

            var damageGO = new GameObject("DamageNumbers");
            damageGO.transform.SetParent(utilitiesGO.transform, false);
            damageGO.AddComponent<DamageNumberRenderer>();

            var attackGO = new GameObject("AttackEffects");
            attackGO.transform.SetParent(utilitiesGO.transform, false);
            attackGO.AddComponent<AttackEffectRenderer>();

            var particleGO = new GameObject("ParticleEffects");
            particleGO.transform.SetParent(utilitiesGO.transform, false);
            particleGO.AddComponent<ParticleEffects>();

            Debug.Log("[SceneBootstrapper] Utilities created.");
        }

        // ====================================================================
        // Step 7a: HUD Canvas (sortOrder 0)
        // ====================================================================

        private void _createHUDCanvas()
        {
            var canvas = UIHelper.CreateCanvas("HUD_Canvas", 0);

            _createUIPanel<StatusBarUI>(canvas.transform, "StatusBarUI",
                new Vector2(0.01f, 0.88f), new Vector2(0.35f, 0.99f));

            _createUIPanel<SkillBarUI>(canvas.transform, "SkillBarUI",
                new Vector2(0.3f, 0.01f), new Vector2(0.7f, 0.07f));

            _createUIPanel<NotificationUI>(canvas.transform, "NotificationUI",
                new Vector2(0.65f, 0.01f), new Vector2(0.99f, 0.25f));

            _createUIPanel<DebugOverlay>(canvas.transform, "DebugOverlay",
                new Vector2(0.01f, 0.60f), new Vector2(0.35f, 0.87f));

            // Crosshair
            var crosshairGO = new GameObject("Crosshair");
            crosshairGO.transform.SetParent(canvas.transform, false);
            var crosshairRT = crosshairGO.AddComponent<RectTransform>();
            crosshairRT.anchorMin = new Vector2(0.5f, 0.5f);
            crosshairRT.anchorMax = new Vector2(0.5f, 0.5f);
            crosshairRT.sizeDelta = new Vector2(6, 6);
            crosshairRT.anchoredPosition = Vector2.zero;
            var crosshairImg = crosshairGO.AddComponent<UnityEngine.UI.Image>();
            crosshairImg.color = new Color(1f, 1f, 1f, 0.7f);
            crosshairImg.raycastTarget = false;

            // DayNightOverlay
            var dayNightGO = new GameObject("DayNightOverlay");
            dayNightGO.transform.SetParent(canvas.transform, false);
            var dayNightRT = dayNightGO.AddComponent<RectTransform>();
            dayNightRT.anchorMin = Vector2.zero;
            dayNightRT.anchorMax = Vector2.one;
            dayNightRT.offsetMin = Vector2.zero;
            dayNightRT.offsetMax = Vector2.zero;
            var overlayImage = dayNightGO.AddComponent<UnityEngine.UI.Image>();
            overlayImage.color = new Color(0f, 0f, 0f, 0f);
            overlayImage.raycastTarget = false;
            dayNightGO.AddComponent<DayNightOverlay>();

            Debug.Log("[SceneBootstrapper] HUD Canvas created.");
        }

        // ====================================================================
        // Step 7b: Panel Canvas (sortOrder 10)
        // ====================================================================

        private void _createPanelCanvas()
        {
            var canvas = UIHelper.CreateCanvas("Panel_Canvas", 10);

            _createUIPanel<StartMenuUI>(canvas.transform, "StartMenuUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _createUIPanel<SaveLoadUI>(canvas.transform, "SaveLoadUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _createUIPanel<ChestUI>(canvas.transform, "ChestUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _createUIPanel<ClassSelectionUI>(canvas.transform, "ClassSelectionUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<InventoryUI>(canvas.transform, "InventoryUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<EquipmentUI>(canvas.transform, "EquipmentUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<CraftingUI>(canvas.transform, "CraftingUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<StatsUI>(canvas.transform, "StatsUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<SkillsMenuUI>(canvas.transform, "SkillsMenuUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<TitleUI>(canvas.transform, "TitleUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<SkillUnlockUI>(canvas.transform, "SkillUnlockUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<EncyclopediaUI>(canvas.transform, "EncyclopediaUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<MapUI>(canvas.transform, "MapUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            _createUIPanel<NPCDialogueUI>(canvas.transform, "NPCDialogueUI",
                new Vector2(0.55f, 0.02f), new Vector2(0.98f, 0.98f));

            Debug.Log("[SceneBootstrapper] Panel Canvas created.");
        }

        // ====================================================================
        // Step 7c: Minigame Canvas (sortOrder 20)
        // ====================================================================

        private void _createMinigameCanvas()
        {
            var canvas = UIHelper.CreateCanvas("Minigame_Canvas", 20);

            var containerRT = UIHelper.CreateContainer(canvas.transform, "MinigameUI",
                Vector2.zero, Vector2.one);

            _createUIPanel<SmithingMinigameUI>(containerRT, "SmithingMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            _createUIPanel<AlchemyMinigameUI>(containerRT, "AlchemyMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            _createUIPanel<RefiningMinigameUI>(containerRT, "RefiningMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            _createUIPanel<EngineeringMinigameUI>(containerRT, "EngineeringMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            _createUIPanel<EnchantingMinigameUI>(containerRT, "EnchantingMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            _createUIPanel<FishingMinigameUI>(containerRT, "FishingMinigameUI",
                new Vector2(0.1f, 0.05f), new Vector2(0.9f, 0.95f));

            Debug.Log("[SceneBootstrapper] Minigame Canvas created.");
        }

        // ====================================================================
        // Step 7d: Overlay Canvas (sortOrder 30)
        // ====================================================================

        private void _createOverlayCanvas()
        {
            var canvas = UIHelper.CreateCanvas("Overlay_Canvas", 30);

            _createUIPanel<TooltipRenderer>(canvas.transform, "TooltipRenderer",
                Vector2.zero, Vector2.one);

            _createUIPanel<DragDropManager>(canvas.transform, "DragDropManager",
                Vector2.zero, Vector2.one);

            Debug.Log("[SceneBootstrapper] Overlay Canvas created.");
        }

        // ====================================================================
        // Step 8: Wire Cross-References
        // ====================================================================

        private void _wireReferences()
        {
            _setSerializedField(_inputManager, "_stateManager", _stateManager);

            Debug.Log("[SceneBootstrapper] Cross-references wired.");
        }

        // ====================================================================
        // Helper: Create a UI Panel with a MonoBehaviour Component
        // ====================================================================

        private T _createUIPanel<T>(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax) where T : MonoBehaviour
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);

            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;

            var component = go.AddComponent<T>();
            return component;
        }

        // ====================================================================
        // Helper: Set a SerializeField via Reflection
        // ====================================================================

        private void _setSerializedField(MonoBehaviour target, string fieldName, object value)
        {
            if (target == null) return;

            var type = target.GetType();
            var field = type.GetField(fieldName,
                System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Instance);

            if (field != null)
            {
                field.SetValue(target, value);
            }
            else
            {
                Debug.LogWarning($"[SceneBootstrapper] Field '{fieldName}' not found on {type.Name}");
            }
        }
    }
}
