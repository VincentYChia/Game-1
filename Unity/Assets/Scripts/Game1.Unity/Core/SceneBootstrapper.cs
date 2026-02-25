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
        }

        // ====================================================================
        // Step 1: EventSystem
        // ====================================================================

        private void _createEventSystem()
        {
            // Use UIHelper's built-in method which checks for existing EventSystem
            UIHelper.EnsureEventSystem();
            Debug.Log("[SceneBootstrapper] EventSystem created.");
        }

        // ====================================================================
        // Step 2: Lighting
        // ====================================================================

        private void _createLighting()
        {
            // Directional light (sun)
            var lightGO = new GameObject("DirectionalLight");
            var light = lightGO.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1f, 0.96f, 0.92f, 1f); // warm white
            light.intensity = 1.0f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.6f;
            light.shadowBias = 0.05f;
            light.shadowNormalBias = 0.4f;
            lightGO.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            // Ambient light: warm outdoor lighting
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.6f, 1f);

            // Procedural skybox for visual depth
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

            // Distance fog for atmosphere and depth cues
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

            _stateManager = managersGO.AddComponent<GameStateManager>();
            _inputManager = managersGO.AddComponent<InputManager>();
            _gameManager = managersGO.AddComponent<GameManager>();

            Debug.Log("[SceneBootstrapper] Managers created.");
        }

        // ====================================================================
        // Step 4: Player Rig (First Person)
        // ====================================================================

        private void _createPlayerRig()
        {
            // Player rig at center of 100x100 world
            var playerRigGO = new GameObject("PlayerRig");
            playerRigGO.transform.position = new Vector3(50f, 0f, 50f);
            _playerController = playerRigGO.AddComponent<PlayerController>();

            // Child camera
            var cameraGO = new GameObject("MainCamera");
            cameraGO.transform.SetParent(playerRigGO.transform, false);
            cameraGO.transform.localPosition = new Vector3(0f, 1.6f, 0f); // eye height
            cameraGO.tag = "MainCamera";

            _cameraController = cameraGO.AddComponent<CameraController>();

            // Camera component (CameraController.Awake will add one if missing,
            // but we create it explicitly for clarity and AudioListener attachment)
            var camera = cameraGO.GetComponent<Camera>();
            if (camera == null)
                camera = cameraGO.AddComponent<Camera>();
            camera.fieldOfView = 70f;
            camera.nearClipPlane = 0.1f;
            camera.farClipPlane = 500f;
            camera.orthographic = false;

            // AudioListener must be on the camera
            cameraGO.AddComponent<AudioListener>();

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

            // DamageNumbers child
            var damageGO = new GameObject("DamageNumbers");
            damageGO.transform.SetParent(utilitiesGO.transform, false);
            damageGO.AddComponent<DamageNumberRenderer>();

            // AttackEffects child
            var attackGO = new GameObject("AttackEffects");
            attackGO.transform.SetParent(utilitiesGO.transform, false);
            attackGO.AddComponent<AttackEffectRenderer>();

            // ParticleEffects child
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

            // StatusBarUI — top-left
            _createUIPanel<StatusBarUI>(canvas.transform, "StatusBarUI",
                new Vector2(0.01f, 0.88f), new Vector2(0.35f, 0.99f));

            // SkillBarUI — bottom-center
            _createUIPanel<SkillBarUI>(canvas.transform, "SkillBarUI",
                new Vector2(0.3f, 0.01f), new Vector2(0.7f, 0.07f));

            // NotificationUI — bottom-right
            _createUIPanel<NotificationUI>(canvas.transform, "NotificationUI",
                new Vector2(0.65f, 0.01f), new Vector2(0.99f, 0.25f));

            // DebugOverlay — top-left, below status bar
            _createUIPanel<DebugOverlay>(canvas.transform, "DebugOverlay",
                new Vector2(0.01f, 0.60f), new Vector2(0.35f, 0.87f));

            // Crosshair — small dot at screen center for first-person orientation
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

            // DayNightOverlay — full-screen tint layer
            var dayNightGO = new GameObject("DayNightOverlay");
            dayNightGO.transform.SetParent(canvas.transform, false);
            var dayNightRT = dayNightGO.AddComponent<RectTransform>();
            dayNightRT.anchorMin = Vector2.zero;
            dayNightRT.anchorMax = Vector2.one;
            dayNightRT.offsetMin = Vector2.zero;
            dayNightRT.offsetMax = Vector2.zero;
            // Add Image for the overlay tint
            var overlayImage = dayNightGO.AddComponent<UnityEngine.UI.Image>();
            overlayImage.color = new Color(0f, 0f, 0f, 0f);
            overlayImage.raycastTarget = false;
            // Add the DayNightOverlay component
            dayNightGO.AddComponent<DayNightOverlay>();

            Debug.Log("[SceneBootstrapper] HUD Canvas created.");
        }

        // ====================================================================
        // Step 7b: Panel Canvas (sortOrder 10)
        // ====================================================================

        private void _createPanelCanvas()
        {
            var canvas = UIHelper.CreateCanvas("Panel_Canvas", 10);

            // --- Centered panels ---
            // anchorMin(0.15, 0.1), anchorMax(0.85, 0.9)

            _createUIPanel<StartMenuUI>(canvas.transform, "StartMenuUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _createUIPanel<SaveLoadUI>(canvas.transform, "SaveLoadUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            _createUIPanel<ChestUI>(canvas.transform, "ChestUI",
                new Vector2(0.15f, 0.1f), new Vector2(0.85f, 0.9f));

            // --- Right-side panels ---
            // anchorMin(0.55, 0.02), anchorMax(0.98, 0.98)

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

            // MinigameUI container — full-screen so minigames can position freely
            var containerRT = UIHelper.CreateContainer(canvas.transform, "MinigameUI",
                Vector2.zero, Vector2.one);

            // Individual minigame UIs — each gets a centered panel
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

            // TooltipRenderer — full-screen container (tooltip positions itself)
            _createUIPanel<TooltipRenderer>(canvas.transform, "TooltipRenderer",
                Vector2.zero, Vector2.one);

            // DragDropManager — full-screen container (drag ghost positions itself)
            _createUIPanel<DragDropManager>(canvas.transform, "DragDropManager",
                Vector2.zero, Vector2.one);

            Debug.Log("[SceneBootstrapper] Overlay Canvas created.");
        }

        // ====================================================================
        // Step 8: Wire Cross-References
        // ====================================================================

        private void _wireReferences()
        {
            // Wire GameManager's serialized references via reflection or
            // let its Start() auto-discover via FindFirstObjectByType.
            // GameManager.Start() already does auto-discovery for all four
            // references (_stateManager, _inputManager, _cameraController,
            // _audioManager), so we only need to wire fields that are
            // checked during Awake() — which is none.

            // Wire InputManager._stateManager so it can respond to state
            // changes immediately when OnEnable fires.
            _setSerializedField(_inputManager, "_stateManager", _stateManager);

            Debug.Log("[SceneBootstrapper] Cross-references wired.");
        }

        // ====================================================================
        // Helper: Create a UI Panel with a MonoBehaviour Component
        // ====================================================================

        /// <summary>
        /// Creates a child GameObject with a RectTransform anchored at the
        /// specified position, then adds the given MonoBehaviour component.
        /// The component's own Awake() can build its internal UI hierarchy.
        /// </summary>
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

        /// <summary>
        /// Sets a private [SerializeField] on a MonoBehaviour at runtime.
        /// Used to wire cross-references that would normally be set in the
        /// Unity Inspector. Falls back gracefully if the field doesn't exist.
        /// </summary>
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
