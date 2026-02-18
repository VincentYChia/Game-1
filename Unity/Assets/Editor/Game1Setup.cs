// ============================================================================
// Game1 Editor Setup Script
// Creates the complete 3D game scene hierarchy with one menu click.
// Menu: Game1 > Setup > Create Game Scene
// Updated: 2026-02-18 — Full 3D scene with all UI panels
// ============================================================================

#if UNITY_EDITOR
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Tilemaps;
using UnityEditor;
using UnityEditor.SceneManagement;
using TMPro;
using Game1.Unity.Core;
using Game1.Unity.UI;
using Game1.Unity.World;
using Game1.Unity.Utilities;

public static class Game1Setup
{
    [MenuItem("Game1/Setup/Create Game Scene")]
    public static void CreateGameScene()
    {
        if (!EditorUtility.DisplayDialog("Create Game Scene",
            "This will create a new 3D scene with all Game-1 systems.\nAny unsaved changes in the current scene will be lost.\n\nContinue?",
            "Create", "Cancel"))
            return;

        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        // ================================================================
        // 1. Configure Camera for 3D perspective
        // ================================================================
        var cam = Camera.main;
        if (cam == null)
        {
            var newCamGO = new GameObject("Main Camera");
            newCamGO.tag = "MainCamera";
            cam = newCamGO.AddComponent<Camera>();
            newCamGO.AddComponent<AudioListener>();
        }

        var cameraGO = cam.gameObject;
        // Position will be set by CameraController (perspective orbit)
        cameraGO.transform.position = new Vector3(0f, 14f, -12f);
        cameraGO.transform.rotation = Quaternion.Euler(50f, 0f, 0f);

        cam.orthographic = false;
        cam.fieldOfView = 50f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.12f, 0.14f, 0.22f);
        cam.nearClipPlane = 0.3f;
        cam.farClipPlane = 500f;

        cameraGO.AddComponent<CameraController>();

        // Remove default directional light (DayNightOverlay creates its own)
        var defaultLight = GameObject.Find("Directional Light");
        if (defaultLight != null) Object.DestroyImmediate(defaultLight);

        // ================================================================
        // 2. Manager GameObjects
        // ================================================================
        var gmGO = new GameObject("GameManager");
        gmGO.AddComponent<GameManager>();

        var gsmGO = new GameObject("GameStateManager");
        gsmGO.AddComponent<GameStateManager>();

        var inputGO = new GameObject("InputManager");
        inputGO.AddComponent<InputManager>();

        var audioGO = new GameObject("AudioManager");
        audioGO.AddComponent<AudioManager>();

        var spriteDbGO = new GameObject("SpriteDatabase");
        spriteDbGO.AddComponent<SpriteDatabase>();

        // ================================================================
        // 3. Terrain Material Manager (3D terrain system)
        // ================================================================
        var terrainMatGO = new GameObject("TerrainMaterialManager");
        terrainMatGO.AddComponent<TerrainMaterialManager>();

        // ================================================================
        // 4. World Renderer (3D mesh terrain by default)
        // ================================================================
        var wrGO = new GameObject("WorldRenderer");
        var worldRenderer = wrGO.AddComponent<WorldRenderer>();

        // Water surface animator (CPU-side wave animation)
        wrGO.AddComponent<WaterSurfaceAnimator>();

        // Also create a legacy tilemap as fallback (disabled by default)
        var gridGO = new GameObject("Grid_Legacy");
        gridGO.AddComponent<Grid>();
        gridGO.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
        gridGO.SetActive(false);

        var tilemapGO = new GameObject("GroundTilemap");
        tilemapGO.transform.SetParent(gridGO.transform, false);
        tilemapGO.AddComponent<Tilemap>();
        tilemapGO.AddComponent<TilemapRenderer>();

        // ================================================================
        // 5. Player (billboard sprite in 3D world)
        // ================================================================
        var playerGO = new GameObject("Player");
        playerGO.transform.position = new Vector3(0f, 0.5f, 0f);

        var sr = playerGO.AddComponent<SpriteRenderer>();
        sr.sprite = CreatePlaceholderSprite(Color.cyan);
        sr.sortingOrder = 10;

        playerGO.AddComponent<PlayerRenderer>();

        // ================================================================
        // 5b. Particle Effects System
        // ================================================================
        var particleGO = new GameObject("ParticleEffects");
        particleGO.AddComponent<ParticleEffects>();

        // ================================================================
        // 6. Effect Renderers
        // ================================================================
        var dmgNumGO = new GameObject("DamageNumberRenderer");
        dmgNumGO.AddComponent<DamageNumberRenderer>();

        var atkFxGO = new GameObject("AttackEffectRenderer");
        atkFxGO.AddComponent<AttackEffectRenderer>();

        // ================================================================
        // 7. Day/Night Overlay (3D directional lighting)
        // ================================================================
        var dayNightGO = new GameObject("DayNightSystem");
        var dayNightOverlay = dayNightGO.AddComponent<DayNightOverlay>();

        // ================================================================
        // 8. UI Canvas System (Screen Space Overlay)
        // ================================================================

        // --- HUD Canvas (Sort Order 0) — Always visible ---
        var hudCanvas = CreateCanvas("HUD_Canvas", 0);

        // Status Bars (HP/Mana/EXP)
        var statusBarGO = CreateUIPanel(hudCanvas.transform, "StatusBar",
            new Vector2(0f, 0.92f), new Vector2(0.35f, 1f));
        statusBarGO.AddComponent<StatusBarUI>();

        // Skill Bar (bottom center)
        var skillBarGO = CreateUIPanel(hudCanvas.transform, "SkillBar",
            new Vector2(0.3f, 0f), new Vector2(0.7f, 0.08f));
        skillBarGO.AddComponent<SkillBarUI>();

        // Notifications (top right)
        var notifGO = CreateUIPanel(hudCanvas.transform, "NotificationContainer",
            new Vector2(0.6f, 0.75f), new Vector2(1f, 1f));
        notifGO.AddComponent<NotificationUI>();

        // Debug Overlay (left side, hidden)
        var debugPanel = CreateUIPanel(hudCanvas.transform, "DebugPanel",
            new Vector2(0f, 0f), new Vector2(0.25f, 0.5f));
        debugPanel.SetActive(false);
        var debugTextGO = CreateTextElement(debugPanel.transform, "DebugText", "",
            14, TextAlignmentOptions.TopLeft, new Vector2(0f, 0f), new Vector2(1f, 1f));
        var debugOverlay = debugPanel.AddComponent<DebugOverlay>();
        WireField(debugOverlay, "_debugPanel", debugPanel);
        WireField(debugOverlay, "_debugText", debugTextGO.GetComponent<TextMeshProUGUI>());

        // --- Panel Canvas (Sort Order 10) — Modal panels ---
        var panelCanvas = CreateCanvas("Panel_Canvas", 10);

        // Inventory Panel
        var invPanel = CreateModalPanel(panelCanvas.transform, "InventoryPanel");
        invPanel.AddComponent<InventoryUI>();

        // Equipment Panel
        var equipPanel = CreateModalPanel(panelCanvas.transform, "EquipmentPanel");
        equipPanel.AddComponent<EquipmentUI>();

        // Stats Panel
        var statsPanel = CreateModalPanel(panelCanvas.transform, "StatsPanel");
        statsPanel.AddComponent<StatsUI>();

        // Crafting Panel
        var craftPanel = CreateModalPanel(panelCanvas.transform, "CraftingPanel");
        craftPanel.AddComponent<CraftingUI>();

        // Map Panel
        var mapPanel = CreateModalPanel(panelCanvas.transform, "MapPanel");
        mapPanel.AddComponent<MapUI>();

        // Encyclopedia Panel
        var encyclopediaPanel = CreateModalPanel(panelCanvas.transform, "EncyclopediaPanel");
        encyclopediaPanel.AddComponent<EncyclopediaUI>();

        // NPC Dialogue Panel
        var npcPanel = CreateModalPanel(panelCanvas.transform, "NPCDialoguePanel");
        npcPanel.AddComponent<NPCDialogueUI>();

        // Chest Panel
        var chestPanel = CreateModalPanel(panelCanvas.transform, "ChestPanel");
        chestPanel.AddComponent<ChestUI>();

        // --- Minigame Canvas (Sort Order 20) ---
        var minigameCanvas = CreateCanvas("Minigame_Canvas", 20);

        var smithingMG = CreateModalPanel(minigameCanvas.transform, "SmithingMinigamePanel");
        smithingMG.AddComponent<SmithingMinigameUI>();

        var alchemyMG = CreateModalPanel(minigameCanvas.transform, "AlchemyMinigamePanel");
        alchemyMG.AddComponent<AlchemyMinigameUI>();

        var refiningMG = CreateModalPanel(minigameCanvas.transform, "RefiningMinigamePanel");
        refiningMG.AddComponent<RefiningMinigameUI>();

        var engineeringMG = CreateModalPanel(minigameCanvas.transform, "EngineeringMinigamePanel");
        engineeringMG.AddComponent<EngineeringMinigameUI>();

        var enchantingMG = CreateModalPanel(minigameCanvas.transform, "EnchantingMinigamePanel");
        enchantingMG.AddComponent<EnchantingMinigameUI>();

        // --- Overlay Canvas (Sort Order 30) — Tooltips, menus, drag ---
        var overlayCanvas = CreateCanvas("Overlay_Canvas", 30);

        // Tooltip
        var tooltipGO = CreateUIPanel(overlayCanvas.transform, "TooltipRenderer",
            Vector2.zero, Vector2.one);
        tooltipGO.AddComponent<TooltipRenderer>();

        // Start Menu
        var startMenuPanel = CreatePanel(overlayCanvas.transform, "StartMenuPanel");
        AddBackground(startMenuPanel, new Color(0.08f, 0.08f, 0.12f, 0.95f));
        var startMenuUI = startMenuPanel.AddComponent<StartMenuUI>();

        var titleGO = CreateTextElement(startMenuPanel.transform, "TitleText", "Game-1",
            64, TextAlignmentOptions.Center, new Vector2(0.5f, 0.7f));

        var quickStartBtn = CreateButton(startMenuPanel.transform, "QuickStartButton", "Quick Start",
            new Vector2(0.5f, 0.45f), new Vector2(300, 50));

        var newWorldBtn = CreateButton(startMenuPanel.transform, "NewWorldButton", "New World",
            new Vector2(0.5f, 0.35f), new Vector2(300, 50));

        var namePanel = CreateSubPanel(startMenuPanel.transform, "NamePanel",
            new Vector2(0.5f, 0.55f), new Vector2(400, 120));
        namePanel.SetActive(false);
        CreateTextElement(namePanel.transform, "NameLabel", "Enter your name:",
            20, TextAlignmentOptions.Center, new Vector2(0.5f, 0.8f));
        var nameInputGO = CreateInputField(namePanel.transform, "NameInput",
            new Vector2(0.5f, 0.45f), new Vector2(350, 40));
        var confirmNameBtn = CreateButton(namePanel.transform, "ConfirmNameButton", "Confirm",
            new Vector2(0.5f, 0.1f), new Vector2(200, 40));

        WireField(startMenuUI, "_panel", startMenuPanel);
        WireField(startMenuUI, "_titleText", titleGO.GetComponent<TextMeshProUGUI>());
        WireField(startMenuUI, "_newWorldButton", newWorldBtn.GetComponent<Button>());
        WireField(startMenuUI, "_tempWorldButton", quickStartBtn.GetComponent<Button>());
        WireField(startMenuUI, "_namePanel", namePanel);
        WireField(startMenuUI, "_playerNameInput", nameInputGO.GetComponent<TMP_InputField>());
        WireField(startMenuUI, "_confirmNameButton", confirmNameBtn.GetComponent<Button>());

        // Class Selection
        var classPanel = CreatePanel(overlayCanvas.transform, "ClassSelectionPanel");
        AddBackground(classPanel, new Color(0.08f, 0.08f, 0.12f, 0.95f));
        classPanel.SetActive(false);
        var classUI = classPanel.AddComponent<ClassSelectionUI>();

        CreateTextElement(classPanel.transform, "ClassTitle", "Select Your Class",
            36, TextAlignmentOptions.Center, new Vector2(0.5f, 0.9f));

        var cardContainer = new GameObject("ClassCardContainer");
        cardContainer.transform.SetParent(classPanel.transform, false);
        var cardContainerRT = cardContainer.AddComponent<RectTransform>();
        SetAnchors(cardContainerRT, new Vector2(0.1f, 0.2f), new Vector2(0.5f, 0.8f));
        var vlg = cardContainer.AddComponent<VerticalLayoutGroup>();
        vlg.spacing = 8;
        vlg.childForceExpandWidth = true;
        vlg.childForceExpandHeight = false;

        var cardTemplate = CreateButton(cardContainer.transform, "ClassCardTemplate", "ClassName",
            Vector2.zero, new Vector2(0, 45));
        cardTemplate.SetActive(false);

        var classNameText = CreateTextElement(classPanel.transform, "SelectedClassName", "",
            28, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.75f), new Vector2(0.9f, 0.85f));
        var classDescText = CreateTextElement(classPanel.transform, "SelectedClassDesc", "",
            18, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.5f), new Vector2(0.9f, 0.73f));
        var classBonusText = CreateTextElement(classPanel.transform, "SelectedClassBonuses", "",
            16, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.25f), new Vector2(0.9f, 0.48f));
        var confirmClassBtn = CreateButton(classPanel.transform, "ConfirmClassButton", "Select Class",
            new Vector2(0.7f, 0.12f), new Vector2(250, 50));

        WireField(classUI, "_panel", classPanel);
        WireField(classUI, "_classCardContainer", cardContainer.transform);
        WireField(classUI, "_classCardPrefab", cardTemplate);
        WireField(classUI, "_selectedClassName", classNameText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_selectedClassDesc", classDescText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_selectedClassBonuses", classBonusText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_confirmButton", confirmClassBtn.GetComponent<Button>());

        // Day/Night screen overlay (on overlay canvas, very low alpha in 3D mode)
        var dayNightUIGO = new GameObject("DayNightOverlayUI");
        dayNightUIGO.transform.SetParent(overlayCanvas.transform, false);
        var dayNightRT = dayNightUIGO.AddComponent<RectTransform>();
        SetAnchors(dayNightRT, Vector2.zero, Vector2.one);
        var dayNightImage = dayNightUIGO.AddComponent<Image>();
        dayNightImage.color = new Color(0, 0, 0, 0);
        dayNightImage.raycastTarget = false;
        WireField(dayNightOverlay, "_overlayImage", dayNightImage);

        // ================================================================
        // 9. EventSystem
        // ================================================================
        var eventSystemGO = new GameObject("EventSystem");
        eventSystemGO.AddComponent<UnityEngine.EventSystems.EventSystem>();
        try
        {
            eventSystemGO.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
        }
        catch
        {
            eventSystemGO.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }

        // ================================================================
        // 10. Validation
        // ================================================================
        string contentPath = System.IO.Path.Combine(Application.streamingAssetsPath, "Content");
        if (!System.IO.Directory.Exists(contentPath))
        {
            Debug.LogWarning(
                "[Game1Setup] StreamingAssets/Content/ not found!\n" +
                "Copy JSON data from Game-1/Game-1-modular/ into Assets/StreamingAssets/Content/:\n" +
                "  items.JSON/, recipes.JSON/, placements.JSON/, Definitions.JSON/, progression/, Skills/\n" +
                "Without this data, databases will be empty but the game will still launch.");
        }
        else
        {
            Debug.Log("[Game1Setup] StreamingAssets/Content/ found.");
        }

#if !ENABLE_INPUT_SYSTEM
        Debug.LogWarning(
            "[Game1Setup] Unity Input System may not be active!\n" +
            "Go to Edit > Project Settings > Player > Other Settings > Active Input Handling\n" +
            "and set it to 'Both' or 'Input System Package (New)'.");
#endif

        // ================================================================
        // 11. Mark scene dirty
        // ================================================================
        EditorSceneManager.MarkSceneDirty(scene);

        Debug.Log(
            "[Game1Setup] 3D Game scene created successfully!\n" +
            "Components created:\n" +
            "  - Perspective camera with orbit controls\n" +
            "  - 3D mesh terrain renderer with water animation\n" +
            "  - Directional sun light (day/night cycle)\n" +
            "  - Billboard sprite player with auto-shadow\n" +
            "  - Particle effects system (9 effect types, runtime-created)\n" +
            "  - Attack effect renderer (lines, AoE, beams)\n" +
            "  - All 20+ UI panels (HUD, Panels, Minigames, Overlay)\n" +
            "  - Event system, input manager, audio manager\n" +
            "\nSave the scene (Ctrl+S), then press Play.");

        EditorUtility.DisplayDialog("3D Scene Created",
            "Game scene created with full 3D rendering!\n\n" +
            "1. Save the scene (Ctrl+S)\n" +
            "2. Press Play\n" +
            "3. Click 'Quick Start' to jump in\n\n" +
            "New 3D features:\n" +
            "- Perspective camera with orbit\n" +
            "- 3D mesh terrain with height\n" +
            "- Directional sun lighting\n" +
            "- Billboard sprites with shadows\n\n" +
            "Make sure StreamingAssets/Content/ has your JSON data.",
            "OK");
    }

    // ====================================================================
    // Canvas Creation Helpers
    // ====================================================================

    private static GameObject CreateCanvas(string name, int sortOrder)
    {
        var canvasGO = new GameObject(name);
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = sortOrder;

        var scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1600f, 900f);
        scaler.matchWidthOrHeight = 0.5f;

        canvasGO.AddComponent<GraphicRaycaster>();
        return canvasGO;
    }

    private static GameObject CreateModalPanel(Transform parent, string name)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, Vector2.zero, Vector2.one);
        AddBackground(go, new Color(0.08f, 0.08f, 0.12f, 0.92f));
        go.SetActive(false); // Hidden by default
        return go;
    }

    private static GameObject CreateUIPanel(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax);
        return go;
    }

    // ====================================================================
    // Serialized Field Wiring
    // ====================================================================

    private static void WireField(Component component, string fieldName, Object value)
    {
        var so = new SerializedObject(component);
        var prop = so.FindProperty(fieldName);
        if (prop != null)
        {
            prop.objectReferenceValue = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }
        else
        {
            Debug.LogWarning($"[Game1Setup] Could not find field '{fieldName}' on {component.GetType().Name}");
        }
    }

    // ====================================================================
    // UI Element Helpers
    // ====================================================================

    private static GameObject CreatePanel(Transform parent, string name)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, Vector2.zero, Vector2.one);
        return go;
    }

    private static void AddBackground(GameObject panel, Color color)
    {
        var img = panel.AddComponent<Image>();
        img.color = color;
    }

    private static GameObject CreateSubPanel(Transform parent, string name, Vector2 anchorCenter, Vector2 size)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = rt.anchorMax = anchorCenter;
        rt.sizeDelta = size;

        var img = go.AddComponent<Image>();
        img.color = new Color(0.15f, 0.15f, 0.2f, 0.9f);
        return go;
    }

    private static GameObject CreateTextElement(Transform parent, string name, string text,
        float fontSize, TextAlignmentOptions alignment, Vector2 anchorCenter)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = rt.anchorMax = anchorCenter;
        rt.sizeDelta = new Vector2(500, 80);

        var tmp = go.AddComponent<TextMeshProUGUI>();
        tmp.text = text;
        tmp.fontSize = fontSize;
        tmp.alignment = alignment;
        tmp.color = Color.white;
        return go;
    }

    private static GameObject CreateTextElement(Transform parent, string name, string text,
        float fontSize, TextAlignmentOptions alignment, Vector2 anchorMin, Vector2 anchorMax)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax);

        var tmp = go.AddComponent<TextMeshProUGUI>();
        tmp.text = text;
        tmp.fontSize = fontSize;
        tmp.alignment = alignment;
        tmp.color = Color.white;
        return go;
    }

    private static GameObject CreateButton(Transform parent, string name, string label,
        Vector2 anchorCenter, Vector2 size)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = rt.anchorMax = anchorCenter;
        rt.sizeDelta = size;

        var img = go.AddComponent<Image>();
        img.color = new Color(0.25f, 0.25f, 0.35f, 1f);

        go.AddComponent<Button>();

        var labelGO = new GameObject("Label");
        labelGO.transform.SetParent(go.transform, false);
        var labelRT = labelGO.AddComponent<RectTransform>();
        SetAnchors(labelRT, Vector2.zero, Vector2.one);

        var tmp = labelGO.AddComponent<TextMeshProUGUI>();
        tmp.text = label;
        tmp.fontSize = 22;
        tmp.alignment = TextAlignmentOptions.Center;
        tmp.color = Color.white;

        return go;
    }

    private static GameObject CreateInputField(Transform parent, string name,
        Vector2 anchorCenter, Vector2 size)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var rt = go.AddComponent<RectTransform>();
        rt.anchorMin = rt.anchorMax = anchorCenter;
        rt.sizeDelta = size;

        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.2f, 0.2f, 0.25f, 1f);

        var textArea = new GameObject("Text Area");
        textArea.transform.SetParent(go.transform, false);
        var textAreaRT = textArea.AddComponent<RectTransform>();
        SetAnchors(textAreaRT, Vector2.zero, Vector2.one);
        textAreaRT.offsetMin = new Vector2(10, 2);
        textAreaRT.offsetMax = new Vector2(-10, -2);
        textArea.AddComponent<RectMask2D>();

        var placeholderGO = new GameObject("Placeholder");
        placeholderGO.transform.SetParent(textArea.transform, false);
        var phRT = placeholderGO.AddComponent<RectTransform>();
        SetAnchors(phRT, Vector2.zero, Vector2.one);
        var phTMP = placeholderGO.AddComponent<TextMeshProUGUI>();
        phTMP.text = "Player";
        phTMP.fontSize = 18;
        phTMP.fontStyle = FontStyles.Italic;
        phTMP.color = new Color(0.5f, 0.5f, 0.5f);
        phTMP.alignment = TextAlignmentOptions.Left;

        var textGO = new GameObject("Text");
        textGO.transform.SetParent(textArea.transform, false);
        var txtRT = textGO.AddComponent<RectTransform>();
        SetAnchors(txtRT, Vector2.zero, Vector2.one);
        var txtTMP = textGO.AddComponent<TextMeshProUGUI>();
        txtTMP.fontSize = 18;
        txtTMP.color = Color.white;
        txtTMP.alignment = TextAlignmentOptions.Left;

        var inputField = go.AddComponent<TMP_InputField>();
        inputField.textViewport = textAreaRT;
        inputField.textComponent = txtTMP;
        inputField.placeholder = phTMP;
        inputField.text = "Player";

        return go;
    }

    private static Sprite CreatePlaceholderSprite(Color color)
    {
        var tex = new Texture2D(16, 16);
        for (int x = 0; x < 16; x++)
            for (int y = 0; y < 16; y++)
                tex.SetPixel(x, y, color);
        tex.Apply();
        tex.filterMode = FilterMode.Point;
        return Sprite.Create(tex, new Rect(0, 0, 16, 16), new Vector2(0.5f, 0.5f), 16f);
    }

    private static void SetAnchors(RectTransform rt, Vector2 min, Vector2 max)
    {
        rt.anchorMin = min;
        rt.anchorMax = max;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
    }
}
#endif
