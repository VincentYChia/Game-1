// ============================================================================
// Game1 Editor Setup Script
// Creates the complete game scene hierarchy with one menu click.
// Menu: Game1 > Setup > Create Game Scene
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
        // Confirm with user
        if (!EditorUtility.DisplayDialog("Create Game Scene",
            "This will create a new scene with all Game-1 systems.\nAny unsaved changes in the current scene will be lost.\n\nContinue?",
            "Create", "Cancel"))
            return;

        // Create fresh scene
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ================================================================
        // 1. Main Camera
        // ================================================================
        var cameraGO = new GameObject("Main Camera");
        cameraGO.tag = "MainCamera";
        cameraGO.transform.position = new Vector3(0f, 50f, 0f);
        cameraGO.transform.rotation = Quaternion.Euler(90f, 0f, 0f);

        var cam = cameraGO.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = 8f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.12f, 0.12f, 0.18f);
        cam.nearClipPlane = 0.1f;
        cam.farClipPlane = 200f;

        cameraGO.AddComponent<AudioListener>();
        cameraGO.AddComponent<CameraController>();

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
        // 3. Grid + Tilemap (rotated to align XY tilemap with XZ world)
        // ================================================================
        var gridGO = new GameObject("Grid");
        gridGO.AddComponent<Grid>();
        gridGO.transform.rotation = Quaternion.Euler(90f, 0f, 0f);

        var tilemapGO = new GameObject("GroundTilemap");
        tilemapGO.transform.SetParent(gridGO.transform, false);
        var tilemap = tilemapGO.AddComponent<Tilemap>();
        tilemapGO.AddComponent<TilemapRenderer>();

        // ================================================================
        // 4. WorldRenderer (wire tilemap references)
        // ================================================================
        var wrGO = new GameObject("WorldRenderer");
        var worldRenderer = wrGO.AddComponent<WorldRenderer>();
        WireField(worldRenderer, "_groundTilemap", tilemap);
        WireField(worldRenderer, "_grid", gridGO.GetComponent<Grid>());

        // ================================================================
        // 5. Player
        // ================================================================
        var playerGO = new GameObject("Player");
        playerGO.transform.position = new Vector3(0f, 0.5f, 0f);

        var sr = playerGO.AddComponent<SpriteRenderer>();
        sr.sprite = CreatePlaceholderSprite(Color.cyan);
        sr.sortingOrder = 10;

        playerGO.AddComponent<PlayerRenderer>();

        // ================================================================
        // 6. UI Canvas
        // ================================================================
        var canvasGO = new GameObject("UICanvas");
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 100;

        var scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1600f, 900f);
        scaler.matchWidthOrHeight = 0.5f;

        canvasGO.AddComponent<GraphicRaycaster>();

        // Also need an EventSystem for UI clicks
        var eventSystemGO = new GameObject("EventSystem");
        eventSystemGO.AddComponent<UnityEngine.EventSystems.EventSystem>();
        eventSystemGO.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();

        // ================================================================
        // 6a. Start Menu Panel
        // ================================================================
        var startMenuPanel = CreatePanel(canvasGO.transform, "StartMenuPanel");
        AddBackground(startMenuPanel, new Color(0.08f, 0.08f, 0.12f, 0.95f));
        var startMenuUI = startMenuPanel.AddComponent<StartMenuUI>();

        // Title
        var titleGO = CreateTextElement(startMenuPanel.transform, "TitleText", "Game-1",
            64, TextAlignmentOptions.Center, new Vector2(0.5f, 0.7f));

        // Quick Start button
        var quickStartBtn = CreateButton(startMenuPanel.transform, "QuickStartButton", "Quick Start",
            new Vector2(0.5f, 0.45f), new Vector2(300, 50));

        // New World button
        var newWorldBtn = CreateButton(startMenuPanel.transform, "NewWorldButton", "New World",
            new Vector2(0.5f, 0.35f), new Vector2(300, 50));

        // Name Panel (hidden by default)
        var namePanel = CreateSubPanel(startMenuPanel.transform, "NamePanel",
            new Vector2(0.5f, 0.55f), new Vector2(400, 120));
        namePanel.SetActive(false);

        CreateTextElement(namePanel.transform, "NameLabel", "Enter your name:",
            20, TextAlignmentOptions.Center, new Vector2(0.5f, 0.8f));

        var nameInputGO = CreateInputField(namePanel.transform, "NameInput",
            new Vector2(0.5f, 0.45f), new Vector2(350, 40));

        var confirmNameBtn = CreateButton(namePanel.transform, "ConfirmNameButton", "Confirm",
            new Vector2(0.5f, 0.1f), new Vector2(200, 40));

        // Wire StartMenuUI fields
        WireField(startMenuUI, "_panel", startMenuPanel);
        WireField(startMenuUI, "_titleText", titleGO.GetComponent<TextMeshProUGUI>());
        WireField(startMenuUI, "_newWorldButton", newWorldBtn.GetComponent<Button>());
        WireField(startMenuUI, "_tempWorldButton", quickStartBtn.GetComponent<Button>());
        WireField(startMenuUI, "_namePanel", namePanel);
        WireField(startMenuUI, "_playerNameInput", nameInputGO.GetComponent<TMP_InputField>());
        WireField(startMenuUI, "_confirmNameButton", confirmNameBtn.GetComponent<Button>());

        // ================================================================
        // 6b. Class Selection Panel (hidden by default)
        // ================================================================
        var classPanel = CreatePanel(canvasGO.transform, "ClassSelectionPanel");
        AddBackground(classPanel, new Color(0.08f, 0.08f, 0.12f, 0.95f));
        classPanel.SetActive(false);
        var classUI = classPanel.AddComponent<ClassSelectionUI>();

        CreateTextElement(classPanel.transform, "ClassTitle", "Select Your Class",
            36, TextAlignmentOptions.Center, new Vector2(0.5f, 0.9f));

        // Card container with vertical layout
        var cardContainer = new GameObject("ClassCardContainer");
        cardContainer.transform.SetParent(classPanel.transform, false);
        var cardContainerRT = cardContainer.AddComponent<RectTransform>();
        SetAnchors(cardContainerRT, new Vector2(0.1f, 0.2f), new Vector2(0.5f, 0.8f));
        var vlg = cardContainer.AddComponent<VerticalLayoutGroup>();
        vlg.spacing = 8;
        vlg.childForceExpandWidth = true;
        vlg.childForceExpandHeight = false;

        // Class card template (inactive — instantiated at runtime for each class)
        var cardTemplate = CreateButton(cardContainer.transform, "ClassCardTemplate", "ClassName",
            Vector2.zero, new Vector2(0, 45));
        cardTemplate.SetActive(false);

        // Detail text fields
        var classNameText = CreateTextElement(classPanel.transform, "SelectedClassName", "",
            28, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.75f), new Vector2(0.9f, 0.85f));

        var classDescText = CreateTextElement(classPanel.transform, "SelectedClassDesc", "",
            18, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.5f), new Vector2(0.9f, 0.73f));

        var classBonusText = CreateTextElement(classPanel.transform, "SelectedClassBonuses", "",
            16, TextAlignmentOptions.TopLeft, new Vector2(0.55f, 0.25f), new Vector2(0.9f, 0.48f));

        // Confirm button
        var confirmClassBtn = CreateButton(classPanel.transform, "ConfirmClassButton", "Select Class",
            new Vector2(0.7f, 0.12f), new Vector2(250, 50));

        // Wire ClassSelectionUI fields
        WireField(classUI, "_panel", classPanel);
        WireField(classUI, "_classCardContainer", cardContainer.transform);
        WireField(classUI, "_classCardPrefab", cardTemplate);
        WireField(classUI, "_selectedClassName", classNameText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_selectedClassDesc", classDescText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_selectedClassBonuses", classBonusText.GetComponent<TextMeshProUGUI>());
        WireField(classUI, "_confirmButton", confirmClassBtn.GetComponent<Button>());

        // ================================================================
        // 6c. Status Bar
        // ================================================================
        var statusBarGO = new GameObject("StatusBar");
        statusBarGO.transform.SetParent(canvasGO.transform, false);
        var statusBarRT = statusBarGO.AddComponent<RectTransform>();
        SetAnchors(statusBarRT, new Vector2(0f, 0.92f), new Vector2(0.4f, 1f));
        statusBarGO.AddComponent<StatusBarUI>();

        // ================================================================
        // 6d. Notifications (top-right)
        // ================================================================
        var notifGO = new GameObject("NotificationContainer");
        notifGO.transform.SetParent(canvasGO.transform, false);
        var notifRT = notifGO.AddComponent<RectTransform>();
        notifRT.anchorMin = new Vector2(0.6f, 0.7f);
        notifRT.anchorMax = new Vector2(1f, 1f);
        notifRT.offsetMin = Vector2.zero;
        notifRT.offsetMax = Vector2.zero;
        notifGO.AddComponent<NotificationUI>();

        // ================================================================
        // 6e. Debug Overlay (hidden by default)
        // ================================================================
        var debugPanel = new GameObject("DebugPanel");
        debugPanel.transform.SetParent(canvasGO.transform, false);
        var debugPanelRT = debugPanel.AddComponent<RectTransform>();
        SetAnchors(debugPanelRT, new Vector2(0f, 0f), new Vector2(0.3f, 0.5f));
        debugPanel.SetActive(false);

        var debugTextGO = CreateTextElement(debugPanel.transform, "DebugText", "",
            14, TextAlignmentOptions.TopLeft, new Vector2(0f, 0f), new Vector2(1f, 1f));

        var debugOverlay = debugPanel.AddComponent<DebugOverlay>();
        WireField(debugOverlay, "_debugPanel", debugPanel);
        WireField(debugOverlay, "_debugText", debugTextGO.GetComponent<TextMeshProUGUI>());

        // ================================================================
        // 6f. Day/Night Overlay
        // ================================================================
        var dayNightGO = new GameObject("DayNightOverlay");
        dayNightGO.transform.SetParent(canvasGO.transform, false);
        var dayNightRT = dayNightGO.AddComponent<RectTransform>();
        SetAnchors(dayNightRT, Vector2.zero, Vector2.one);
        var dayNightImage = dayNightGO.AddComponent<Image>();
        dayNightImage.color = new Color(0, 0, 0, 0);
        dayNightImage.raycastTarget = false;

        var dayNightOverlay = dayNightGO.AddComponent<DayNightOverlay>();
        WireField(dayNightOverlay, "_overlayImage", dayNightImage);

        // ================================================================
        // 7. Validation
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

        // Check Input System setting
#if !ENABLE_INPUT_SYSTEM
        Debug.LogWarning(
            "[Game1Setup] Unity Input System may not be active!\n" +
            "Go to Edit > Project Settings > Player > Other Settings > Active Input Handling\n" +
            "and set it to 'Both' or 'Input System Package (New)'.\n" +
            "Then restart the Editor.");
#endif

        // ================================================================
        // 8. Mark scene dirty so user saves it
        // ================================================================
        EditorSceneManager.MarkSceneDirty(scene);

        Debug.Log(
            "[Game1Setup] Game scene created successfully!\n" +
            "Save the scene (Ctrl+S), then press Play.\n" +
            "'Quick Start' button starts immediately. 'New World' lets you name your character and pick a class.");

        EditorUtility.DisplayDialog("Scene Created",
            "Game scene created successfully!\n\n" +
            "1. Save the scene (Ctrl+S)\n" +
            "2. Press Play\n" +
            "3. Click 'Quick Start' to jump in\n\n" +
            "Make sure StreamingAssets/Content/ has your JSON data.",
            "OK");
    }

    // ====================================================================
    // Helper: Wire a private [SerializeField] via SerializedObject
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
    // Helper: Create a full-screen UI panel
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

    // ====================================================================
    // Helper: Create TextMeshProUGUI element
    // ====================================================================
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

    // ====================================================================
    // Helper: Create a Button with text
    // ====================================================================
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

        // Button label
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

    // ====================================================================
    // Helper: Create a TMP_InputField
    // ====================================================================
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

        // Text area (child required by TMP_InputField)
        var textArea = new GameObject("Text Area");
        textArea.transform.SetParent(go.transform, false);
        var textAreaRT = textArea.AddComponent<RectTransform>();
        SetAnchors(textAreaRT, Vector2.zero, Vector2.one);
        textAreaRT.offsetMin = new Vector2(10, 2);
        textAreaRT.offsetMax = new Vector2(-10, -2);
        textArea.AddComponent<RectMask2D>();

        // Placeholder
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

        // Text
        var textGO = new GameObject("Text");
        textGO.transform.SetParent(textArea.transform, false);
        var txtRT = textGO.AddComponent<RectTransform>();
        SetAnchors(txtRT, Vector2.zero, Vector2.one);
        var txtTMP = textGO.AddComponent<TextMeshProUGUI>();
        txtTMP.fontSize = 18;
        txtTMP.color = Color.white;
        txtTMP.alignment = TextAlignmentOptions.Left;

        // Input field component
        var inputField = go.AddComponent<TMP_InputField>();
        inputField.textViewport = textAreaRT;
        inputField.textComponent = txtTMP;
        inputField.placeholder = phTMP;
        inputField.text = "Player";

        return go;
    }

    // ====================================================================
    // Helper: Create a placeholder sprite
    // ====================================================================
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

    // ====================================================================
    // Helper: Set RectTransform anchors (stretch mode)
    // ====================================================================
    private static void SetAnchors(RectTransform rt, Vector2 min, Vector2 max)
    {
        rt.anchorMin = min;
        rt.anchorMax = max;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
    }
}
#endif
