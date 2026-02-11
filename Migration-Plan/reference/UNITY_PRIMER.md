# Unity Primer for Game-1 Migrators

**Audience**: Developers who know C# but are new to Unity.
**Purpose**: Everything you need to know about Unity to execute this migration. No more, no less.

---

## 1. The Two Worlds: MonoBehaviour vs Plain C#

Unity has two kinds of classes. Understanding the difference is critical.

### Plain C# Classes (Most of Your Work)
These are normal C# classes. They don't need Unity at all. They run in unit tests without a scene.

**Use for**: Data models, databases, calculations, game logic, ML preprocessing.

```csharp
// This is a plain C# class. No Unity dependency.
namespace Game1.Data.Models
{
    [Serializable]
    public class MaterialDefinition
    {
        public string MaterialId { get; set; }
        public string Name { get; set; }
        public int Tier { get; set; }
    }
}
```

**Phase 1, 2, 3, 4, 5** are almost entirely plain C# classes.

### MonoBehaviour Classes (Phase 6 Only)
These are Unity components that attach to GameObjects in a scene. They have a lifecycle (Awake, Start, Update). They can access Unity-specific features (rendering, physics, UI).

**Use for**: Rendering, input handling, UI panels, camera, player controller.

```csharp
// This is a MonoBehaviour. It must be attached to a GameObject.
using UnityEngine;

namespace Game1.UI
{
    public class InventoryPanel : MonoBehaviour
    {
        [SerializeField] private Transform _slotContainer;

        private void OnEnable()
        {
            RefreshSlots();
        }

        private void RefreshSlots()
        {
            // Read from Character.Inventory (plain C# class)
            // Update UI elements
        }
    }
}
```

### The Rule
> **If it doesn't touch the screen, the camera, or user input, it's a plain C# class.**
> **If it displays something, moves something, or reads input, it's a MonoBehaviour.**

### Why This Matters for Migration
- Phases 1-5: You're writing plain C# classes. You can test them in EditMode tests (no scene needed). This is just like writing C# in any other project.
- Phase 6: You're writing MonoBehaviours that CALL INTO the plain C# classes. The MonoBehaviours are thin wrappers that bridge game logic to Unity's rendering and input systems.

---

## 2. MonoBehaviour Lifecycle (The Order Things Happen)

When a scene loads, Unity calls methods on MonoBehaviours in a specific order:

```
Scene Loads
    │
    ▼
Awake()         ← Called once when object is created. Use for: self-initialization,
    │              finding your own components, singleton setup.
    │              All Awake() calls finish before any Start() call.
    ▼
OnEnable()      ← Called when object becomes active. Use for: subscribing to events,
    │              refreshing UI data. Called every time object is re-enabled.
    ▼
Start()         ← Called once before first Update. Use for: initialization that
    │              depends on other objects being ready (they all had Awake() already).
    ▼
Update()        ← Called every frame (~60 times/sec at 60 FPS). Use for: input
    │              polling, movement, game logic tick. DELTA TIME: Time.deltaTime
    ▼
LateUpdate()    ← Called after all Update() calls. Use for: camera follow (so it
    │              moves after the player moves).
    ▼
OnDisable()     ← Called when object becomes inactive. Use for: unsubscribing events,
    │              cleanup. Called every time object is disabled.
    ▼
OnDestroy()     ← Called when object is destroyed or scene unloads.
```

### For Game-1, This Means

```csharp
public class GameManager : MonoBehaviour
{
    // Singleton
    public static GameManager Instance { get; private set; }

    void Awake()
    {
        // STEP 1: Singleton setup
        if (Instance != null) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);

        // STEP 2: Load all databases (plain C# singletons)
        DatabaseInitializer.InitializeAll();

        // STEP 3: Initialize game systems (plain C# singletons)
        // CombatManager, WorldSystem, etc. are plain C# — no scene needed
    }

    void Start()
    {
        // STEP 4: Create or load character (databases are ready from Awake)
        LoadOrCreateCharacter();

        // STEP 5: Initialize UI (MonoBehaviour panels need data from character)
        UIManager.Instance.Initialize();
    }

    void Update()
    {
        // Game loop — called every frame
        float dt = Time.deltaTime;
        CombatManager.Instance.Update(dt);
        WorldSystem.Instance.UpdateChunks(Character.Position);
    }
}
```

### Common Mistake
```csharp
// BAD: Accessing another object in Awake() — it might not be Awake yet
void Awake()
{
    var combat = CombatManager.Instance; // Might be null if CombatManager hasn't Awake'd
}

// GOOD: Access other objects in Start() — all Awake() calls are done
void Start()
{
    var combat = CombatManager.Instance; // Safe — everything is initialized
}
```

**For Game-1**: Database singletons (plain C# with lazy init) don't have this problem. They initialize on first access. But MonoBehaviour singletons (GameManager, UIManager) DO have this problem.

---

## 3. SerializeField: The Inspector Connection

`[SerializeField]` exposes a private field in the Unity Inspector (the visual editor). You drag-and-drop references in the editor instead of hardcoding them.

```csharp
public class WorldRenderer : MonoBehaviour
{
    [SerializeField] private Tilemap _groundTilemap;   // Drag tilemap here in editor
    [SerializeField] private Tilemap _objectTilemap;    // Drag tilemap here in editor
    [SerializeField] private int _chunkSize = 16;       // Editable in inspector

    void Start()
    {
        // _groundTilemap is already set (from inspector drag-and-drop)
        _groundTilemap.SetTile(position, tile);
    }
}
```

### When to Use SerializeField vs Hardcode
| Situation | Approach |
|-----------|----------|
| Reference to another object in the scene | `[SerializeField]` — drag in inspector |
| Constant that never changes | `private const int ChunkSize = 16;` |
| Tunable value you might adjust | `[SerializeField] private float _moveSpeed = 5f;` |
| Reference found at runtime | `FindObjectOfType<T>()` or singleton pattern |

---

## 4. ScriptableObject: Data Assets

ScriptableObjects are data containers that live as files in your project. They're like JSON files but editor-friendly.

**For Game-1**: We use ScriptableObjects ONLY for Unity-specific configuration (display settings, camera settings). Game data stays in JSON for moddability.

```csharp
[CreateAssetMenu(fileName = "GameConfig", menuName = "Game1/GameConfig")]
public class GameConfigAsset : ScriptableObject
{
    [Header("Display")]
    public int BaseWidth = 1600;
    public int BaseHeight = 900;
    public int TargetFPS = 60;

    [Header("Camera")]
    public float ZoomSpeed = 2f;
    public float MinZoom = 3f;
    public float MaxZoom = 12f;
}

// Usage:
public class GameManager : MonoBehaviour
{
    [SerializeField] private GameConfigAsset _config;

    void Awake()
    {
        Application.targetFrameRate = _config.TargetFPS;
    }
}
```

**Create in editor**: Right-click in Project → Create → Game1 → GameConfig

---

## 5. Unity's Canvas System (UI)

All UI in Unity goes on a Canvas. Think of it as a Pygame surface that overlays the game.

### Hierarchy
```
Canvas (Screen Space - Overlay)
├── HUD Panel                    ← Always visible during gameplay
│   ├── HealthBar
│   ├── ManaBar
│   ├── ExperienceBar
│   └── MinimapPanel
├── Inventory Panel              ← Toggle with I key
│   ├── SlotGrid (30 slots)
│   └── ItemTooltip
├── Equipment Panel              ← Toggle with E key
│   └── 8 equipment slots
├── Crafting Panel               ← Opens at crafting station
│   ├── RecipeList
│   ├── MaterialGrid
│   └── CraftButton
├── Skills Panel                 ← Toggle with K key
└── Tooltip (highest sort order) ← Always on top
```

### How Panels Work
```csharp
public class UIManager : MonoBehaviour
{
    [SerializeField] private GameObject _inventoryPanel;
    [SerializeField] private GameObject _equipmentPanel;
    [SerializeField] private GameObject _craftingPanel;
    [SerializeField] private GameObject _skillsPanel;

    public void ToggleInventory()
    {
        // SetActive(true/false) shows/hides the panel
        // OnEnable() is called when shown — refreshes data
        _inventoryPanel.SetActive(!_inventoryPanel.activeSelf);
    }

    public void ShowCrafting(string stationType, int tier)
    {
        _craftingPanel.SetActive(true);
        _craftingPanel.GetComponent<CraftingPanel>().Initialize(stationType, tier);
    }

    public void HideAllPanels()
    {
        _inventoryPanel.SetActive(false);
        _equipmentPanel.SetActive(false);
        _craftingPanel.SetActive(false);
        _skillsPanel.SetActive(false);
    }
}
```

---

## 6. Input System

Unity has two input systems. Use the **new** Input System (Input Action Assets).

### Setup
1. Install package: Window → Package Manager → Input System
2. Create Input Action Asset: Right-click → Create → Input Actions
3. Define action maps: Player, UI, Crafting, Debug

### Usage
```csharp
using UnityEngine.InputSystem;

public class PlayerController : MonoBehaviour
{
    private PlayerInput _playerInput;
    private InputAction _moveAction;
    private InputAction _interactAction;

    void Awake()
    {
        _playerInput = GetComponent<PlayerInput>();
        _moveAction = _playerInput.actions["Move"];
        _interactAction = _playerInput.actions["Interact"];
    }

    void Update()
    {
        // Read movement (WASD or gamepad stick)
        Vector2 moveInput = _moveAction.ReadValue<Vector2>();
        transform.Translate(moveInput * _moveSpeed * Time.deltaTime);

        // Check interaction (E key)
        if (_interactAction.WasPressedThisFrame())
        {
            TryInteract();
        }
    }
}
```

### Action Map Switching (for Game States)
```csharp
// When entering crafting mode:
_playerInput.SwitchCurrentActionMap("Crafting");

// When returning to gameplay:
_playerInput.SwitchCurrentActionMap("Player");
```

---

## 7. Tilemap (World Rendering)

Unity's Tilemap system replaces Pygame's tile-by-tile rendering.

```csharp
using UnityEngine.Tilemaps;

public class WorldRenderer : MonoBehaviour
{
    [SerializeField] private Tilemap _groundTilemap;
    [SerializeField] private TileBase _grassTile;
    [SerializeField] private TileBase _waterTile;
    [SerializeField] private TileBase _stoneTile;

    public void RenderChunk(Chunk chunk, Vector2Int chunkPos)
    {
        for (int x = 0; x < 16; x++)
        {
            for (int y = 0; y < 16; y++)
            {
                var tileType = chunk.GetTile(x, y);
                var worldPos = new Vector3Int(
                    chunkPos.x * 16 + x,
                    chunkPos.y * 16 + y,
                    0
                );

                TileBase tile = tileType switch
                {
                    TileType.Grass => _grassTile,
                    TileType.Water => _waterTile,
                    TileType.Stone => _stoneTile,
                    _ => _grassTile
                };

                _groundTilemap.SetTile(worldPos, tile);
            }
        }
    }
}
```

---

## 8. Coroutines and Async (Replacing Python Threading)

Python uses `threading.Thread` for async LLM calls. Unity has two options:

### Option A: Coroutines (Unity-native, recommended for game logic)
```csharp
private IEnumerator FadeOutNotification(float duration)
{
    float elapsed = 0f;
    while (elapsed < duration)
    {
        elapsed += Time.deltaTime;
        float alpha = 1f - (elapsed / duration);
        _canvasGroup.alpha = alpha;
        yield return null; // Wait one frame
    }
    gameObject.SetActive(false);
}

// Start coroutine:
StartCoroutine(FadeOutNotification(3f));
```

### Option B: Async/Await (for API calls, file I/O)
```csharp
public async Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request)
{
    // Simulate API delay
    await Task.Delay(500);
    return new GeneratedItem { /* ... */ };
}

// Call from coroutine bridge:
private IEnumerator GenerateItemCoroutine(ItemGenerationRequest request)
{
    var task = _generator.GenerateItemAsync(request);
    while (!task.IsCompleted)
        yield return null;

    var item = task.Result;
    // Use item...
}
```

**Rule**: Use `async/await` for LLM stub and file I/O. Use coroutines for animations and timed events. Never use `Thread` — it breaks Unity's main thread requirement.

---

## 9. Unity Sentis (ML Model Inference)

Unity Sentis replaces Python's TensorFlow/LightGBM for running ML models.

### Setup
1. Install: Window → Package Manager → Unity Sentis
2. Import ONNX: Drag `.onnx` file into `Assets/Resources/Models/`
3. Unity auto-imports it as a `ModelAsset`

### Usage
```csharp
using Unity.Sentis;

public class SmithingClassifier
{
    private Worker _worker;

    public void Initialize()
    {
        var modelAsset = Resources.Load<ModelAsset>("Models/smithing_cnn");
        var model = ModelLoader.Load(modelAsset);
        _worker = new Worker(model, BackendType.GPUCompute);
    }

    public ClassifierResult Predict(float[,,] image)
    {
        // Create input tensor (36x36x3)
        using var inputTensor = new Tensor<float>(new TensorShape(1, 36, 36, 3));
        // Fill tensor with image data...

        // Run inference
        _worker.Schedule(inputTensor);

        // Read output
        var outputTensor = _worker.PeekOutput() as Tensor<float>;
        outputTensor.ReadbackAndClone(); // GPU -> CPU
        float confidence = outputTensor[0, 1]; // Probability of "valid"

        return new ClassifierResult
        {
            IsValid = confidence > 0.5f,
            Confidence = confidence
        };
    }

    public void Dispose()
    {
        _worker?.Dispose();
    }
}
```

---

## 10. Testing in Unity

### EditMode Tests (Unit Tests — No Scene Required)
These test plain C# code. This is where 90% of your tests go.

```csharp
using NUnit.Framework;
using Game1.Data.Models;

namespace Game1.Tests.EditMode
{
    [TestFixture]
    public class MaterialDefinitionTests
    {
        [Test]
        public void Constructor_SetsProperties()
        {
            var mat = new MaterialDefinition
            {
                MaterialId = "iron_ore",
                Name = "Iron Ore",
                Tier = 1,
                Category = "metal"
            };

            Assert.AreEqual("iron_ore", mat.MaterialId);
            Assert.AreEqual(1, mat.Tier);
        }

        [Test]
        public void Tier_ClampsToValidRange()
        {
            var mat = new MaterialDefinition { Tier = 99 };
            Assert.AreEqual(4, mat.Tier); // Clamped to max
        }
    }
}
```

**Setup**: Create assembly definition `Tests/EditMode/Game1.Tests.EditMode.asmdef` with test runner reference.

### PlayMode Tests (Integration Tests — Require Scene)
These test MonoBehaviours and cross-system integration.

```csharp
using System.Collections;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Game1.Tests.PlayMode
{
    public class GameFlowTests
    {
        [UnityTest]
        public IEnumerator NewGame_SpawnsCharacter()
        {
            // Load test scene
            yield return LoadTestScene();

            // Verify character exists
            var player = GameObject.FindObjectOfType<PlayerController>();
            Assert.IsNotNull(player);

            yield return null; // Wait one frame
        }
    }
}
```

---

## 11. Common Unity Mistakes (and How to Avoid Them)

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Accessing another MonoBehaviour in Awake() | NullReferenceException | Access in Start() instead |
| Using `new MonoBehaviour()` | Unity error — can't construct | Use `AddComponent<T>()` or attach in editor |
| Modifying Transform from non-main thread | Crash | Use main thread or dispatcher |
| Forgetting `Time.deltaTime` | Frame-rate dependent behavior | Always multiply movement/timers by deltaTime |
| Using `Find()` or `FindObjectOfType()` in Update() | Massive performance hit | Cache reference in Start() |
| Not disposing Sentis Worker | Memory leak | Use `using` or call `Dispose()` in `OnDestroy()` |
| Reading from StreamingAssets with `Resources.Load()` | Returns null | Use `File.ReadAllText(Application.streamingAssetsPath + ...)` |

---

## 12. Project Setup Checklist

When creating the Unity project for Phase 1:

1. **Create project**: Unity Hub → New → 2D (URP) or 2D Core → Name: "Game-1-Unity"
2. **Install packages**:
   - Newtonsoft.Json: `com.unity.nuget.newtonsoft-json`
   - Input System: `com.unity.inputsystem`
   - Unity Sentis: `com.unity.sentis` (for Phase 5)
   - Test Framework: included by default
3. **Create folder structure**:
   ```
   Assets/
   ├── Scripts/
   │   ├── Game1.Core/
   │   ├── Game1.Data/
   │   │   ├── Models/
   │   │   ├── Databases/
   │   │   └── Enums/
   │   ├── Game1.Entities/
   │   ├── Game1.Systems/
   │   └── Game1.UI/
   ├── Resources/
   │   └── Models/         (ONNX files go here)
   ├── StreamingAssets/
   │   └── Content/         (Copy all JSON here)
   └── Tests/
       ├── EditMode/
       └── PlayMode/
   ```
4. **Copy JSON files**: Copy entire `Game-1-modular/items.JSON/`, `recipes.JSON/`, etc. into `StreamingAssets/Content/`
5. **Create assembly definitions** (`.asmdef` files) for each namespace folder
6. **Set scripting backend**: Project Settings → Player → Scripting Backend → IL2CPP (for builds)
7. **Add MIGRATION_VALIDATION define**: Project Settings → Player → Scripting Define Symbols → `MIGRATION_VALIDATION`

---

## Quick Reference Card

| Python/Pygame | Unity/C# |
|--------------|-----------|
| `pygame.time.get_ticks()` | `Time.time * 1000f` (seconds→ms) |
| `pygame.display.set_mode()` | Set in Project Settings or script |
| `pygame.event.get()` | Input System actions |
| `screen.blit(surface, pos)` | SpriteRenderer or Tilemap |
| `pygame.draw.rect()` | UI Image component |
| `pygame.font.render()` | TextMeshPro component |
| `time.sleep(n)` | `yield return new WaitForSeconds(n)` |
| `threading.Thread(target=fn)` | `async Task` or `StartCoroutine()` |
| `json.load(file)` | `JsonConvert.DeserializeObject<T>(text)` |
| `random.random()` | `UnityEngine.Random.value` |
| `random.randint(a,b)` | `UnityEngine.Random.Range(a, b+1)` |
| `math.sqrt(x)` | `Mathf.Sqrt(x)` |
| `print(msg)` | `Debug.Log(msg)` |
| `if __name__ == '__main__':` | No equivalent needed |
