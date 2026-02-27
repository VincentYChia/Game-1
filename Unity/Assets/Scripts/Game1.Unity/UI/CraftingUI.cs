// ============================================================================
// Game1.Unity.UI.CraftingUI
// Migrated from: rendering/renderer.py (lines 4429-5720: crafting UI)
//              + game_engine.py (lines 3169-3550: interactive clicks)
// Migration phase: 6
// Date: 2026-02-13
//
// Crafting station interaction: recipe selection, material placement, craft/invent.
// Handles all 5 disciplines' placement grids.
// Self-building: if _panel is null at startup, _buildUI() constructs the
// entire hierarchy from code using UIHelper (no prefab/scene setup needed).
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Data.Models;
using Game1.Systems.Crafting;
using Game1.Systems.Classifiers;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Crafting UI panel — recipe selection sidebar + material placement grid.
    /// Supports all 5 disciplines with discipline-specific grid layouts.
    /// </summary>
    public class CraftingUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Recipe Sidebar")]
        [SerializeField] private Transform _recipeListContainer;
        [SerializeField] private GameObject _recipeEntryPrefab;
        [SerializeField] private ScrollRect _recipeScrollRect;
        [SerializeField] private TextMeshProUGUI _selectedRecipeTitle;
        [SerializeField] private TextMeshProUGUI _selectedRecipeDesc;

        [Header("Placement Grid")]
        [SerializeField] private Transform _gridContainer;
        [SerializeField] private GameObject _gridSlotPrefab;

        [Header("Material Palette")]
        [SerializeField] private Transform _paletteContainer;
        [SerializeField] private GameObject _paletteItemPrefab;

        [Header("Action Buttons")]
        [SerializeField] private Button _craftButton;
        [SerializeField] private Button _clearButton;
        [SerializeField] private Button _inventButton;

        [Header("Difficulty Display")]
        [SerializeField] private TextMeshProUGUI _difficultyText;
        [SerializeField] private Image _difficultyBar;

        // ====================================================================
        // State
        // ====================================================================

        private string _currentDiscipline;
        private int _stationTier;
        private Recipe _selectedRecipe;
        private List<Recipe> _availableRecipes = new List<Recipe>();
        private Dictionary<string, string> _placedMaterials = new Dictionary<string, string>();
        private string _selectedMaterialId; // Currently selected palette material for placement

        private GameStateManager _stateManager;

        // References populated by _buildUI()
        private Text _recipeTitleLabel;
        private Text _recipeDescLabel;
        private Text _difficultyLabel;
        private Text _headerLabel;
        private ScrollRect _recipeScroll;
        private RectTransform _recipeScrollContent;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            if (_stateManager != null)
                _stateManager.OnStateChanged += _onStateChanged;

            if (_craftButton != null) _craftButton.onClick.AddListener(_onCraftClicked);
            if (_clearButton != null) _clearButton.onClick.AddListener(_onClearClicked);
            if (_inventButton != null) _inventButton.onClick.AddListener(_onInventClicked);

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_stateManager != null)
                _stateManager.OnStateChanged -= _onStateChanged;
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        /// <summary>
        /// Construct the entire crafting panel hierarchy from code.
        /// Right-side panel with:
        ///   Header
        ///   Left column (40%): scrollable recipe list
        ///   Right column (60%): material placement grid
        ///   Bottom row: Instant Craft / Minigame / Interactive buttons
        /// </summary>
        private void _buildUI()
        {
            // -- Root panel: centered on screen, 600 x 650
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "CraftingPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(600, 650), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);

            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(6, 6, 6, 6));

            // -- Header (updated dynamically when station is opened)
            var (_, headerTitle, _) = UIHelper.CreateHeaderRow(panelRt, "CRAFTING", "[ESC]", height: 38f);
            _headerLabel = headerTitle;

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Main content: horizontal split (recipe list | grid)
            var contentRow = UIHelper.CreatePanel(
                panelRt, "ContentRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var contentImg = contentRow.GetComponent<Image>();
            if (contentImg != null) contentImg.raycastTarget = false;
            var contentLE = contentRow.gameObject.AddComponent<LayoutElement>();
            contentLE.flexibleHeight = 1f;

            UIHelper.AddHorizontalLayout(contentRow, spacing: 4f,
                padding: new RectOffset(0, 0, 0, 0), childForceExpand: false);

            // ---- Left column: Recipe list (40%)
            var leftCol = UIHelper.CreatePanel(
                contentRow, "RecipeColumn", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            var leftLE = leftCol.gameObject.AddComponent<LayoutElement>();
            leftLE.flexibleWidth = 0.4f;
            leftLE.flexibleHeight = 1f;

            UIHelper.AddVerticalLayout(leftCol, spacing: 2f,
                padding: new RectOffset(4, 4, 4, 4));

            // Recipe column title
            var recipeHeader = UIHelper.CreateText(leftCol, "RecipeHeader", "Recipes",
                15, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(recipeHeader.gameObject, 24f);

            UIHelper.CreateDivider(leftCol, 1f);

            // Scrollable recipe list
            var recipeScrollPanel = UIHelper.CreatePanel(
                leftCol, "RecipeScrollArea", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var recipeScrollImg = recipeScrollPanel.GetComponent<Image>();
            if (recipeScrollImg != null) recipeScrollImg.raycastTarget = false;
            var recipeScrollLE = recipeScrollPanel.gameObject.AddComponent<LayoutElement>();
            recipeScrollLE.flexibleHeight = 1f;

            var (recipeScroll, recipeContent) = UIHelper.CreateScrollView(
                recipeScrollPanel, "RecipeScroll", UIHelper.COLOR_TRANSPARENT);
            _recipeScroll = recipeScroll;
            _recipeScrollContent = recipeContent;
            _recipeListContainer = recipeContent;

            // Selected recipe info (below recipe list)
            UIHelper.CreateDivider(leftCol, 1f);

            var selectedPanel = UIHelper.CreatePanel(
                leftCol, "SelectedInfo", UIHelper.COLOR_BG_SLOT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(selectedPanel.gameObject, 60f);
            UIHelper.AddVerticalLayout(selectedPanel, spacing: 2f,
                padding: new RectOffset(6, 6, 4, 4));

            _recipeTitleLabel = UIHelper.CreateText(selectedPanel, "RecipeTitle",
                "Select a recipe", 14, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_recipeTitleLabel.gameObject, 20f);

            _recipeDescLabel = UIHelper.CreateText(selectedPanel, "RecipeDesc",
                "", 12, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
            UIHelper.SetPreferredHeight(_recipeDescLabel.gameObject, 16f);

            // ---- Right column: Grid + palette (60%)
            var rightCol = UIHelper.CreatePanel(
                contentRow, "GridColumn", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            var rightLE = rightCol.gameObject.AddComponent<LayoutElement>();
            rightLE.flexibleWidth = 0.6f;
            rightLE.flexibleHeight = 1f;

            UIHelper.AddVerticalLayout(rightCol, spacing: 4f,
                padding: new RectOffset(4, 4, 4, 4));

            // Grid header
            var gridHeader = UIHelper.CreateText(rightCol, "GridHeader", "Placement Grid",
                15, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(gridHeader.gameObject, 24f);

            UIHelper.CreateDivider(rightCol, 1f);

            // Grid container (where discipline-specific grids are built)
            var gridArea = UIHelper.CreatePanel(
                rightCol, "GridArea", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var gridAreaImg = gridArea.GetComponent<Image>();
            if (gridAreaImg != null) gridAreaImg.raycastTarget = false;
            var gridAreaLE = gridArea.gameObject.AddComponent<LayoutElement>();
            gridAreaLE.flexibleHeight = 1f;
            _gridContainer = gridArea;

            // Difficulty display
            UIHelper.CreateDivider(rightCol, 1f);

            var diffRow = UIHelper.CreatePanel(
                rightCol, "DifficultyRow", UIHelper.COLOR_BG_SLOT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(diffRow.gameObject, 24f);

            _difficultyLabel = UIHelper.CreateText(diffRow, "DifficultyText",
                "Difficulty: --", 13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);

            // -- Material palette (scrollable, between grid and buttons)
            UIHelper.CreateDivider(rightCol, 1f);

            var paletteHeader = UIHelper.CreateText(rightCol, "PaletteHeader", "Materials",
                13, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(paletteHeader.gameObject, 20f);

            var paletteScrollPanel = UIHelper.CreatePanel(
                rightCol, "PaletteScrollArea", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var paletteScrollImg = paletteScrollPanel.GetComponent<Image>();
            if (paletteScrollImg != null) paletteScrollImg.raycastTarget = false;
            var paletteScrollLE = paletteScrollPanel.gameObject.AddComponent<LayoutElement>();
            paletteScrollLE.preferredHeight = 100f;
            paletteScrollLE.flexibleHeight = 0.3f;

            var (paletteScroll, paletteContent) = UIHelper.CreateScrollView(
                paletteScrollPanel, "PaletteScroll", UIHelper.COLOR_BG_SLOT);

            // Replace VLG with a grid for palette items
            var existingPaletteVLG = paletteContent.GetComponent<VerticalLayoutGroup>();
            if (existingPaletteVLG != null) Object.DestroyImmediate(existingPaletteVLG);

            var paletteGrid = paletteContent.gameObject.AddComponent<GridLayoutGroup>();
            paletteGrid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            paletteGrid.constraintCount = 6;
            paletteGrid.cellSize = new Vector2(40, 40);
            paletteGrid.spacing = new Vector2(3, 3);
            paletteGrid.padding = new RectOffset(4, 4, 4, 4);
            paletteGrid.childAlignment = TextAnchor.UpperLeft;

            _paletteContainer = paletteContent;

            // -- Divider before buttons
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Bottom button row
            var buttonRow = UIHelper.CreatePanel(
                panelRt, "ButtonRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var buttonRowImg = buttonRow.GetComponent<Image>();
            if (buttonRowImg != null) buttonRowImg.raycastTarget = false;
            UIHelper.SetPreferredHeight(buttonRow.gameObject, 44f);
            UIHelper.AddHorizontalLayout(buttonRow, spacing: 6f,
                padding: new RectOffset(4, 4, 4, 4), childForceExpand: true);

            _craftButton = UIHelper.CreateButton(
                buttonRow, "InstantCraftBtn", "Instant Craft",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14,
                _onCraftClicked);
            var craftLE = _craftButton.gameObject.AddComponent<LayoutElement>();
            craftLE.flexibleWidth = 1f;

            var minigameBtn = UIHelper.CreateButton(
                buttonRow, "MinigameBtn", "Minigame",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14,
                _onCraftClicked);
            var mgLE = minigameBtn.gameObject.AddComponent<LayoutElement>();
            mgLE.flexibleWidth = 1f;

            _inventButton = UIHelper.CreateButton(
                buttonRow, "InteractiveBtn", "Interactive",
                UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GOLD, 14,
                _onInventClicked);
            var invLE = _inventButton.gameObject.AddComponent<LayoutElement>();
            invLE.flexibleWidth = 1f;

            _clearButton = UIHelper.CreateButton(
                panelRt, "ClearBtn", "Clear Grid",
                new Color(0.5f, 0.2f, 0.2f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 13,
                _onClearClicked);
            UIHelper.SetPreferredHeight(_clearButton.gameObject, 30f);
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Open crafting UI for a specific discipline and station tier.</summary>
        public void Open(string discipline, int stationTier)
        {
            _currentDiscipline = discipline;
            _stationTier = stationTier;
            _selectedRecipe = null;
            _selectedMaterialId = null;
            _placedMaterials.Clear();

            // Update header to show discipline + tier
            string discTitle = (discipline ?? "crafting").ToUpperInvariant();
            if (_headerLabel != null)
                _headerLabel.text = $"{discTitle} (T{stationTier})";

            _loadRecipes();
            _buildGrid();
            _buildPalette();
            _updateDifficulty();

            _stateManager?.TransitionTo(GameState.CraftingOpen);
        }

        /// <summary>Close the crafting UI, returning any borrowed materials.</summary>
        public void Close()
        {
            // Return any placed materials to inventory before closing
            if (!_isDebugMode() && _placedMaterials.Count > 0)
            {
                var gm = GameManager.Instance;
                if (gm?.Player != null)
                {
                    foreach (var matId in _placedMaterials.Values)
                        gm.Player.Inventory.AddItem(matId, 1);
                }
            }
            _placedMaterials.Clear();
            _stateManager?.TransitionTo(GameState.Playing);
        }

        // ====================================================================
        // Recipe Loading
        // ====================================================================

        private void _loadRecipes()
        {
            _availableRecipes.Clear();

            var recipeDb = RecipeDatabase.Instance;
            if (recipeDb == null || !recipeDb.Loaded)
            {
                Debug.LogWarning("[CraftingUI] RecipeDatabase not loaded yet");
                return;
            }

            var recipes = recipeDb.GetRecipesForStation(_currentDiscipline, _stationTier);
            if (recipes != null)
            {
                _availableRecipes.AddRange(recipes);
            }

            Debug.Log($"[CraftingUI] Loaded {_availableRecipes.Count} recipes for {_currentDiscipline} T{_stationTier}");
            _populateRecipeList();
        }

        private void _populateRecipeList()
        {
            // Clear existing entries
            if (_recipeListContainer != null)
            {
                foreach (Transform child in _recipeListContainer)
                    Destroy(child.gameObject);
            }

            foreach (var recipe in _availableRecipes)
            {
                if (_recipeEntryPrefab != null && _recipeListContainer != null)
                {
                    // Prefab path
                    var entry = Instantiate(_recipeEntryPrefab, _recipeListContainer);
                    var text = entry.GetComponentInChildren<TextMeshProUGUI>();
                    if (text != null) text.text = recipe.OutputId;

                    var button = entry.GetComponent<Button>();
                    var capturedRecipe = recipe;
                    if (button != null)
                        button.onClick.AddListener(() => _selectRecipe(capturedRecipe));
                }
                else if (_recipeListContainer != null)
                {
                    // Programmatic path: create a button entry using UIHelper
                    var capturedRecipe = recipe;
                    string displayName = recipe.OutputId.Replace("_", " ");
                    int inputCount = recipe.Inputs?.Count ?? 0;
                    string label = $"{displayName} ({inputCount} mats)";

                    var entryBtn = UIHelper.CreateButton(
                        _recipeListContainer, $"Recipe_{recipe.OutputId}",
                        label,
                        UIHelper.COLOR_BG_SLOT, UIHelper.COLOR_TEXT_PRIMARY, 12,
                        () => _selectRecipe(capturedRecipe));
                    UIHelper.SetPreferredHeight(entryBtn.gameObject, 32f);
                }
            }
        }

        private void _selectRecipe(Recipe recipe)
        {
            _selectedRecipe = recipe;

            string displayName = recipe.OutputId.Replace("_", " ");
            string title = $"{displayName} (x{recipe.OutputQty})";

            // Build material requirements description with availability coloring
            string desc = $"T{recipe.StationTier} | ";
            bool debug = _isDebugMode();
            var gm = GameManager.Instance;

            if (recipe.Inputs != null && recipe.Inputs.Count > 0)
            {
                var parts = new List<string>();
                foreach (var input in recipe.Inputs)
                {
                    string matName = input.MaterialId?.Replace("_", " ") ?? "?";
                    bool hasEnough = debug || (gm?.Player?.Inventory?.HasItem(input.MaterialId, input.Quantity) ?? false);
                    int have = debug ? 99 : (gm?.Player?.Inventory?.GetItemCount(input.MaterialId) ?? 0);
                    string status = hasEnough ? "✓" : $"({have}/{input.Quantity})";
                    parts.Add($"{matName} x{input.Quantity} {status}");
                }
                desc += string.Join(", ", parts);
            }
            else
            {
                desc += "No material requirements";
            }

            // Update TMP labels if set via inspector
            if (_selectedRecipeTitle != null)
                _selectedRecipeTitle.text = title;
            if (_selectedRecipeDesc != null)
                _selectedRecipeDesc.text = desc;

            // Update programmatic labels
            if (_recipeTitleLabel != null)
                _recipeTitleLabel.text = title;
            if (_recipeDescLabel != null)
                _recipeDescLabel.text = desc;

            _placedMaterials.Clear();
            _buildGrid();
            _buildPalette();
            _updateDifficulty();
        }

        // ====================================================================
        // Grid Building (discipline-specific)
        // ====================================================================

        private void _buildGrid()
        {
            if (_gridContainer == null) return;

            // Clear existing grid
            foreach (Transform child in _gridContainer)
                Destroy(child.gameObject);

            // Remove old layout group before adding new one
            var existingLayout = _gridContainer.GetComponent<LayoutGroup>();
            if (existingLayout != null) Object.DestroyImmediate(existingLayout);

            // Build grid based on discipline
            switch (_currentDiscipline?.ToLowerInvariant())
            {
                case "smithing":
                    _buildSmithingGrid();
                    break;
                case "alchemy":
                    _buildAlchemySequence();
                    break;
                case "refining":
                    _buildRefiningHub();
                    break;
                case "engineering":
                    _buildEngineeringSlots();
                    break;
                case "enchanting":
                    _buildEnchantingGrid();
                    break;
            }
        }

        // Python-exact grid/slot configs per discipline and tier
        private static readonly Dictionary<int, int> SMITHING_GRID = new() { {1,3},{2,5},{3,7},{4,9} };
        private static readonly Dictionary<int, int> ALCHEMY_SLOTS = new() { {1,2},{2,3},{3,4},{4,6} };
        private static readonly Dictionary<int, (int cores, int surrounding)> REFINING_SLOTS = new()
            { {1,(1,2)},{2,(1,4)},{3,(2,5)},{4,(3,6)} };
        private static readonly Dictionary<int, string[]> ENGINEERING_SLOTS = new()
        {
            {1, new[]{"FRAME","FUNCTION","POWER"}},
            {2, new[]{"FRAME","FUNCTION","POWER"}},
            {3, new[]{"FRAME","FUNCTION","POWER","MODIFIER","UTILITY"}},
            {4, new[]{"FRAME","FUNCTION","POWER","MODIFIER","UTILITY"}},
        };
        private static readonly Dictionary<int, int> ENCHANTING_GRID = new() { {1,8},{2,10},{3,12},{4,14} };

        private void _buildSmithingGrid()
        {
            int gridSize = SMITHING_GRID.TryGetValue(_stationTier, out int gs) ? gs : 3;

            var grid = _gridContainer.gameObject.AddComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = gridSize;
            grid.cellSize = new Vector2(48, 48);
            grid.spacing = new Vector2(4, 4);
            grid.padding = new RectOffset(4, 4, 4, 4);
            grid.childAlignment = TextAnchor.MiddleCenter;

            for (int z = 0; z < gridSize; z++)
            {
                for (int x = 0; x < gridSize; x++)
                {
                    _createGridSlot($"{x},{z}");
                }
            }
        }

        private void _buildAlchemySequence()
        {
            // Sequential ingredient slots — horizontal row
            // Python: T1=2, T2=3, T3=4, T4=6
            var hlg = _gridContainer.gameObject.AddComponent<HorizontalLayoutGroup>();
            hlg.spacing = 8f;
            hlg.padding = new RectOffset(8, 8, 8, 8);
            hlg.childAlignment = TextAnchor.MiddleCenter;
            hlg.childForceExpandWidth = false;
            hlg.childForceExpandHeight = false;

            int slots = ALCHEMY_SLOTS.TryGetValue(_stationTier, out int s) ? s : 2;
            for (int i = 0; i < slots; i++)
            {
                _createGridSlot($"seq_{i}");
            }
        }

        private void _buildRefiningHub()
        {
            // Hub-spoke layout: cores + surrounding
            // Python: T1=(1c,2s) T2=(1c,4s) T3=(2c,5s) T4=(3c,6s)
            var (cores, surrounding) = REFINING_SLOTS.TryGetValue(_stationTier, out var cfg) ? cfg : (1, 2);
            int total = cores + surrounding;

            var grid = _gridContainer.gameObject.AddComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = Mathf.Min(total, 4);
            grid.cellSize = new Vector2(48, 48);
            grid.spacing = new Vector2(6, 6);
            grid.padding = new RectOffset(4, 4, 4, 4);
            grid.childAlignment = TextAnchor.MiddleCenter;

            for (int i = 0; i < cores; i++)
                _createGridSlot($"core_{i}");
            for (int i = 0; i < surrounding; i++)
                _createGridSlot($"surround_{i}");
        }

        private void _buildEngineeringSlots()
        {
            // Named slot types — vertical list
            // Python: T1-T2: FRAME,FUNCTION,POWER; T3-T4: +MODIFIER,UTILITY
            var vlg = _gridContainer.gameObject.AddComponent<VerticalLayoutGroup>();
            vlg.spacing = 6f;
            vlg.padding = new RectOffset(8, 8, 8, 8);
            vlg.childAlignment = TextAnchor.MiddleCenter;
            vlg.childForceExpandWidth = false;
            vlg.childForceExpandHeight = false;

            string[] slotTypes = ENGINEERING_SLOTS.TryGetValue(_stationTier, out var slots)
                ? slots : new[] { "FRAME", "FUNCTION", "POWER" };
            foreach (string slot in slotTypes)
            {
                _createGridSlot(slot);
            }
        }

        private void _buildEnchantingGrid()
        {
            // Cartesian grid for adornment patterns
            // Python: T1=8, T2=10, T3=12, T4=14
            int gridSize = ENCHANTING_GRID.TryGetValue(_stationTier, out int eg) ? eg : 8;

            var grid = _gridContainer.gameObject.AddComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = gridSize;
            grid.cellSize = new Vector2(48, 48);
            grid.spacing = new Vector2(4, 4);
            grid.padding = new RectOffset(4, 4, 4, 4);
            grid.childAlignment = TextAnchor.MiddleCenter;

            for (int z = 0; z < gridSize; z++)
            {
                for (int x = 0; x < gridSize; x++)
                {
                    _createGridSlot($"{x},{z}");
                }
            }
        }

        private void _createGridSlot(string slotKey)
        {
            if (_gridContainer == null) return;

            if (_gridSlotPrefab != null)
            {
                var slot = Instantiate(_gridSlotPrefab, _gridContainer);
                var slotComp = slot.GetComponent<CraftingGridSlot>();
                if (slotComp == null) slotComp = slot.AddComponent<CraftingGridSlot>();
                slotComp.Initialize(slotKey, this);
            }
            else
            {
                // Programmatic: use UIHelper.CreateItemSlot
                var (root, bg, icon, qty, border) = UIHelper.CreateItemSlot(
                    _gridContainer, $"GridSlot_{slotKey}", 48f);
                var slotComp = root.gameObject.AddComponent<CraftingGridSlot>();
                slotComp.Initialize(slotKey, this);
            }
        }

        // ====================================================================
        // Material Palette
        // ====================================================================

        private void _buildPalette()
        {
            if (_paletteContainer == null)
            {
                Debug.LogWarning("[CraftingUI] _paletteContainer is null - palette cannot be built");
                return;
            }

            foreach (Transform child in _paletteContainer)
                Destroy(child.gameObject);

            var gm = GameManager.Instance;

            // In debug mode, show all materials from the database
            var debugOverlay = FindFirstObjectByType<DebugOverlay>();
            bool isDebug = debugOverlay != null && debugOverlay.IsDebugActive;

            if (isDebug)
            {
                _buildDebugPalette();
                return;
            }

            if (gm == null || gm.Player == null) return;

            // Show inventory materials filtered by station tier
            var matDb = MaterialDatabase.Instance;
            var allSlots = gm.Player.Inventory.GetAllSlots();
            int count = 0;

            foreach (var itemSlot in allSlots)
            {
                if (itemSlot == null || string.IsNullOrEmpty(itemSlot.ItemId)) continue;

                // Filter: only show materials at or below station tier
                if (matDb != null)
                {
                    var mat = matDb.GetMaterial(itemSlot.ItemId);
                    if (mat != null && mat.Tier > _stationTier) continue;
                }

                _createPaletteEntry(itemSlot.ItemId, itemSlot.Quantity);
                count++;
            }

            Debug.Log($"[CraftingUI] Built palette with {count} materials (station tier {_stationTier})");
        }

        private void _buildDebugPalette()
        {
            // In debug mode, show all materials from database with quantity 99
            var matDb = MaterialDatabase.Instance;
            if (matDb == null) return;

            int count = 0;
            foreach (var mat in matDb.Materials.Values)
            {
                if (mat == null || string.IsNullOrEmpty(mat.MaterialId)) continue;
                if (mat.Tier > _stationTier) continue;

                _createPaletteEntry(mat.MaterialId, 99);
                count++;
            }
            Debug.Log($"[CraftingUI] Built DEBUG palette with {count} materials");
        }

        private void _createPaletteEntry(string itemId, int quantity)
        {
            if (_paletteItemPrefab != null && _paletteContainer != null)
            {
                var item = Instantiate(_paletteItemPrefab, _paletteContainer);
                var icon = item.GetComponentInChildren<Image>();
                if (icon != null && SpriteDatabase.Instance != null)
                    icon.sprite = SpriteDatabase.Instance.GetItemSprite(itemId);

                var qty = item.GetComponentInChildren<TextMeshProUGUI>();
                if (qty != null)
                    qty.text = quantity.ToString();
            }
            else if (_paletteContainer != null)
            {
                // Programmatic palette entry
                var (root, bg, icon, qty, border) = UIHelper.CreateItemSlot(
                    _paletteContainer, $"Palette_{itemId}", 40f);
                if (SpriteDatabase.Instance != null)
                {
                    icon.sprite = SpriteDatabase.Instance.GetItemSprite(itemId);
                    icon.enabled = true;
                }

                // Show material name as tooltip text on the icon
                string displayName = itemId.Replace("_", " ");
                var tooltip = root.gameObject.AddComponent<PaletteItemTooltip>();
                tooltip.ItemId = itemId;
                tooltip.DisplayName = displayName;

                qty.text = quantity > 1 ? quantity.ToString() : "";

                // Add click handler to select material for placement
                var btn = root.gameObject.GetComponent<Button>();
                if (btn == null) btn = root.gameObject.AddComponent<Button>();
                btn.onClick.AddListener(() => _selectPaletteMaterial(itemId));
            }
        }

        // ====================================================================
        // Material Selection & Placement
        // ====================================================================

        private void _selectPaletteMaterial(string materialId)
        {
            _selectedMaterialId = materialId;
            _highlightSelectedPalette();
            string displayName = materialId.Replace("_", " ");
            NotificationUI.Instance?.Show($"Selected: {displayName}", Color.white);
        }

        private void _highlightSelectedPalette()
        {
            if (_paletteContainer == null) return;

            foreach (Transform child in _paletteContainer)
            {
                var bg = child.GetComponent<Image>();
                if (bg == null) continue;

                bool isSelected = child.name == $"Palette_{_selectedMaterialId}";
                bg.color = isSelected
                    ? new Color(0.35f, 0.45f, 0.35f, 1f)
                    : UIHelper.COLOR_BG_SLOT;

                // Update border (Outline component on the border child)
                var border = child.Find("Border");
                if (border != null)
                {
                    var outline = border.GetComponent<Outline>();
                    if (outline != null)
                        outline.effectColor = isSelected ? new Color(1f, 0.84f, 0f) : UIHelper.COLOR_BORDER;
                }
            }
        }

        /// <summary>Get the currently selected palette material (for grid slot click placement).</summary>
        public string GetSelectedMaterial() => _selectedMaterialId;

        public void PlaceMaterial(string slotKey, string materialId)
        {
            // In non-debug mode, borrow material from inventory
            if (!_isDebugMode())
            {
                var gm = GameManager.Instance;
                if (gm?.Player != null && !gm.Player.Inventory.HasItem(materialId, 1))
                {
                    NotificationUI.Instance?.Show("Not enough materials!", Color.red);
                    return;
                }
                gm?.Player?.Inventory?.RemoveItem(materialId, 1);
            }

            _placedMaterials[slotKey] = materialId;
            _updateDifficulty();
        }

        public void RemoveMaterial(string slotKey)
        {
            // Return borrowed material to inventory
            if (_placedMaterials.TryGetValue(slotKey, out string matId) && !_isDebugMode())
            {
                GameManager.Instance?.Player?.Inventory?.AddItem(matId, 1);
            }

            _placedMaterials.Remove(slotKey);
            _updateDifficulty();
        }

        private bool _isDebugMode()
        {
            var debug = FindFirstObjectByType<DebugOverlay>();
            return debug != null && debug.IsDebugActive;
        }

        // ====================================================================
        // Actions
        // ====================================================================

        private void _onCraftClicked()
        {
            if (_selectedRecipe == null)
            {
                NotificationUI.Instance?.Show("Select a recipe first!", Color.yellow);
                return;
            }

            bool debug = _isDebugMode();
            var gm = GameManager.Instance;

            // Validate materials
            if (!debug)
            {
                if (gm?.Player == null)
                {
                    NotificationUI.Instance?.Show("No active player!", Color.red);
                    return;
                }

                // Check all required inputs are available
                if (_selectedRecipe.Inputs != null)
                {
                    foreach (var input in _selectedRecipe.Inputs)
                    {
                        if (!gm.Player.Inventory.HasItem(input.MaterialId, input.Quantity))
                        {
                            string matName = input.MaterialId?.Replace("_", " ") ?? "?";
                            NotificationUI.Instance?.Show($"Missing: {matName} x{input.Quantity}", Color.red);
                            return;
                        }
                    }
                }
            }

            // Consume materials (non-debug only)
            if (!debug && _selectedRecipe.Inputs != null)
            {
                foreach (var input in _selectedRecipe.Inputs)
                    gm.Player.Inventory.RemoveItem(input.MaterialId, input.Quantity);
            }

            // Calculate difficulty points from recipe inputs
            int diffPoints = 0;
            var matDb = MaterialDatabase.Instance;
            if (_selectedRecipe.Inputs != null)
            {
                foreach (var input in _selectedRecipe.Inputs)
                {
                    int tier = 1;
                    if (matDb != null)
                    {
                        var mat = matDb.GetMaterial(input.MaterialId);
                        if (mat != null) tier = mat.Tier;
                    }
                    diffPoints += tier * input.Quantity;
                }
            }

            // Calculate reward using Instant Craft performance (80% base — no minigame)
            float instantPerformance = 0.80f;
            float maxMult = RewardCalculator.CalculateMaxRewardMultiplier(diffPoints);
            string qualityTier = RewardCalculator.GetQualityTier(instantPerformance);
            int bonusPct = RewardCalculator.CalculateBonusPct(instantPerformance, maxMult);

            // Create output item and add to inventory
            string outputId = _selectedRecipe.OutputId;
            int outputQty = _selectedRecipe.OutputQty;

            // Build crafted stats for equipment items
            var equipDb = EquipmentDatabase.Instance;
            bool isEquipment = equipDb != null && equipDb.Loaded && equipDb.IsEquipment(outputId);

            if (isEquipment)
            {
                var craftedStats = new CraftedStats
                {
                    Quality = qualityTier.ToLowerInvariant(),
                    PerformanceScore = instantPerformance,
                    Discipline = _currentDiscipline ?? "",
                    CraftedBy = gm?.Player?.Name ?? "Player",
                    BonusDamage = bonusPct > 0 ? bonusPct / 2 : 0,
                    BonusDefense = bonusPct > 0 ? bonusPct / 3 : 0,
                    BonusDurability = bonusPct > 0 ? bonusPct * 2 : 0,
                };
                var equip = ItemFactory.CreateCrafted(outputId, craftedStats);
                if (equip != null)
                {
                    gm?.Player?.Inventory.AddItem(equip.ItemId, 1, equip, equip.Rarity, craftedStats.ToDict());
                }
                else
                {
                    gm?.Player?.Inventory.AddItem(outputId, outputQty);
                }
            }
            else
            {
                gm?.Player?.Inventory.AddItem(outputId, outputQty);
            }

            // Raise crafted event
            GameEvents.RaiseItemCrafted(_currentDiscipline, outputId);

            // Show success notification
            string displayName = outputId.Replace("_", " ");
            Color qualityColor = qualityTier switch
            {
                "Legendary" => new Color(1f, 0.5f, 0f),
                "Masterwork" => new Color(0.64f, 0.21f, 0.93f),
                "Superior" => new Color(0f, 0.44f, 0.87f),
                "Fine" => new Color(0.12f, 1f, 0f),
                _ => Color.white,
            };
            NotificationUI.Instance?.Show(
                $"Crafted {qualityTier} {displayName} x{outputQty}! (+{bonusPct}%)", qualityColor);

            // Refresh palette and inventory
            _buildPalette();
            FindFirstObjectByType<InventoryUI>()?.Refresh();
        }

        private void _onClearClicked()
        {
            // Return all borrowed materials to inventory
            if (!_isDebugMode())
            {
                var gm = GameManager.Instance;
                if (gm?.Player != null)
                {
                    foreach (var matId in _placedMaterials.Values)
                        gm.Player.Inventory.AddItem(matId, 1);
                }
            }
            _placedMaterials.Clear();

            // Clear all slot visuals
            if (_gridContainer != null)
            {
                foreach (var slot in _gridContainer.GetComponentsInChildren<CraftingGridSlot>())
                    slot.ClearSlot();
            }

            _buildPalette();
            _updateDifficulty();
        }

        private void _onInventClicked()
        {
            if (_selectedRecipe == null)
            {
                NotificationUI.Instance?.Show("Select a recipe first!", Color.yellow);
                return;
            }

            if (_placedMaterials.Count == 0)
            {
                NotificationUI.Instance?.Show("Place materials on the grid first!", Color.yellow);
                return;
            }

            // Start the interactive minigame for this discipline
            var ic = InteractiveCrafting.Instance;
            var inputs = new Dictionary<string, int>(_placedMaterials.Count);
            foreach (var kvp in _placedMaterials)
                inputs[kvp.Value] = inputs.TryGetValue(kvp.Value, out int c) ? c + 1 : 1;

            var minigame = ic.StartCrafting(
                _currentDiscipline, _stationTier, _selectedRecipe, inputs);

            if (minigame != null)
            {
                _stateManager?.TransitionTo(GameState.MinigameActive);
                NotificationUI.Instance?.Show($"Starting {_currentDiscipline} minigame...", Color.cyan);
            }
            else
            {
                NotificationUI.Instance?.Show("Minigame not available yet — use Instant Craft", Color.yellow);
            }
        }

        private void _updateDifficulty()
        {
            int points = 0;
            var matDb = MaterialDatabase.Instance;

            foreach (var materialId in _placedMaterials.Values)
            {
                if (matDb != null)
                {
                    var mat = matDb.GetMaterial(materialId);
                    if (mat != null)
                    {
                        points += mat.Tier; // T1=1pt, T2=2pts, T3=3pts, T4=4pts
                        continue;
                    }
                }
                points += 1; // Default 1pt if material not found
            }

            string tier = points switch
            {
                <= 4 => "Common",
                <= 10 => "Uncommon",
                <= 20 => "Rare",
                <= 40 => "Epic",
                _ => "Legendary"
            };

            string text = $"Difficulty: {tier} ({points} pts)";

            // Update TMP label if set via inspector
            if (_difficultyText != null)
                _difficultyText.text = text;

            // Update programmatic label
            if (_difficultyLabel != null)
                _difficultyLabel.text = text;
        }

        // ====================================================================
        // State Changes
        // ====================================================================

        private void _onStateChanged(GameState oldState, GameState newState)
        {
            _setVisible(newState == GameState.CraftingOpen);
        }

        private void _setVisible(bool visible)
        {
            if (_panel != null) _panel.SetActive(visible);
            else gameObject.SetActive(visible);
        }
    }

    /// <summary>Simple tooltip component for palette items.</summary>
    public class PaletteItemTooltip : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
    {
        public string ItemId;
        public string DisplayName;

        public void OnPointerEnter(PointerEventData eventData)
        {
            if (!string.IsNullOrEmpty(ItemId))
                TooltipRenderer.Instance?.Show(ItemId, DisplayName, eventData.position);
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            TooltipRenderer.Instance?.Hide();
        }
    }

    /// <summary>Single slot in the crafting placement grid.</summary>
    public class CraftingGridSlot : MonoBehaviour, IDropHandler, IPointerClickHandler, IPointerEnterHandler, IPointerExitHandler
    {
        private string _slotKey;
        private CraftingUI _craftingUI;
        private string _placedMaterialId;
        private Image _iconImage;
        private Image _bgImage;
        private Text _labelText;

        private static readonly Color COLOR_EMPTY = new Color(0.18f, 0.20f, 0.24f);
        private static readonly Color COLOR_HOVER = new Color(0.28f, 0.32f, 0.38f);
        private static readonly Color COLOR_FILLED_T1 = new Color(0.24f, 0.24f, 0.28f);
        private static readonly Color COLOR_FILLED_T2 = new Color(0.24f, 0.32f, 0.24f);
        private static readonly Color COLOR_FILLED_T3 = new Color(0.24f, 0.28f, 0.36f);
        private static readonly Color COLOR_FILLED_T4 = new Color(0.36f, 0.24f, 0.36f);

        public void Initialize(string slotKey, CraftingUI craftingUI)
        {
            _slotKey = slotKey;
            _craftingUI = craftingUI;

            // Find child components
            var images = GetComponentsInChildren<Image>();
            _bgImage = GetComponent<Image>();
            foreach (var img in images)
            {
                if (img.gameObject != gameObject && img.gameObject.name == "Icon")
                    _iconImage = img;
            }
            if (_iconImage == null && images.Length > 1)
                _iconImage = images[1]; // Fallback to second image

            // Set initial style
            if (_bgImage != null)
                _bgImage.color = COLOR_EMPTY;

            // Add slot label for engineering slots and refining core/surround
            if (_slotKey.StartsWith("core_") || _slotKey.StartsWith("surround_") ||
                _slotKey == "FRAME" || _slotKey == "FUNCTION" || _slotKey == "POWER" ||
                _slotKey == "MODIFIER" || _slotKey == "UTILITY")
            {
                string label = _slotKey.StartsWith("core_") ? "CORE" :
                               _slotKey.StartsWith("surround_") ? "SURR" :
                               _slotKey;
                _addLabel(label);
            }
        }

        private void _addLabel(string text)
        {
            var lblGo = new GameObject("SlotLabel");
            lblGo.transform.SetParent(transform, false);
            var lblRt = lblGo.AddComponent<RectTransform>();
            lblRt.anchorMin = new Vector2(0, 1);
            lblRt.anchorMax = new Vector2(1, 1);
            lblRt.pivot = new Vector2(0.5f, 1f);
            lblRt.sizeDelta = new Vector2(0, 14);
            lblRt.anchoredPosition = new Vector2(0, -1);
            _labelText = lblGo.AddComponent<Text>();
            _labelText.text = text;
            _labelText.fontSize = 9;
            _labelText.color = new Color(0.7f, 0.7f, 0.8f);
            _labelText.alignment = TextAnchor.UpperCenter;
            _labelText.font = UIHelper.GetFont();
            _labelText.raycastTarget = false;
        }

        private Color _getTierColor(string materialId)
        {
            var matDb = MaterialDatabase.Instance;
            if (matDb == null) return COLOR_FILLED_T1;
            var mat = matDb.GetMaterial(materialId);
            if (mat == null) return COLOR_FILLED_T1;
            return mat.Tier switch
            {
                2 => COLOR_FILLED_T2,
                3 => COLOR_FILLED_T3,
                4 => COLOR_FILLED_T4,
                _ => COLOR_FILLED_T1,
            };
        }

        private void _updateVisual()
        {
            if (_placedMaterialId != null)
            {
                if (_bgImage != null)
                    _bgImage.color = _getTierColor(_placedMaterialId);

                if (_iconImage != null && SpriteDatabase.Instance != null)
                {
                    _iconImage.sprite = SpriteDatabase.Instance.GetItemSprite(_placedMaterialId);
                    _iconImage.enabled = true;
                }

                // Update label to show material name
                if (_labelText != null)
                {
                    string displayName = _placedMaterialId.Replace("_", " ");
                    if (displayName.Length > 8) displayName = displayName.Substring(0, 7) + "…";
                    _labelText.text = displayName;
                    _labelText.color = new Color(0.9f, 0.9f, 0.7f);
                }
            }
            else
            {
                if (_bgImage != null)
                    _bgImage.color = COLOR_EMPTY;

                if (_iconImage != null)
                {
                    _iconImage.sprite = null;
                    _iconImage.enabled = false;
                }
            }
        }

        public void OnDrop(PointerEventData eventData)
        {
            var ddm = DragDropManager.Instance;
            if (ddm == null || !ddm.IsDragging) return;

            _placedMaterialId = ddm.DraggedItemId;
            _craftingUI?.PlaceMaterial(_slotKey, _placedMaterialId);
            _updateVisual();
            ddm.CompleteDrop(DragDropManager.DragSource.CraftingGrid, 0);
        }

        public void OnPointerClick(PointerEventData eventData)
        {
            if (eventData.button == PointerEventData.InputButton.Right && _placedMaterialId != null)
            {
                // Right-click to remove placed material
                _placedMaterialId = null;
                _craftingUI?.RemoveMaterial(_slotKey);
                _updateVisual();
            }
            else if (eventData.button == PointerEventData.InputButton.Left && _placedMaterialId == null)
            {
                // Left-click to place the currently selected palette material
                var selectedMat = _craftingUI?.GetSelectedMaterial();
                if (!string.IsNullOrEmpty(selectedMat))
                {
                    _placedMaterialId = selectedMat;
                    _craftingUI?.PlaceMaterial(_slotKey, _placedMaterialId);
                    _updateVisual();
                }
            }
        }

        public void OnPointerEnter(PointerEventData eventData)
        {
            if (_placedMaterialId == null && _bgImage != null)
                _bgImage.color = COLOR_HOVER;

            // Show tooltip for placed material
            if (_placedMaterialId != null)
            {
                var matDb = MaterialDatabase.Instance;
                var mat = matDb?.GetMaterial(_placedMaterialId);
                string name = mat?.Name ?? _placedMaterialId.Replace("_", " ");
                int tier = mat?.Tier ?? 1;
                TooltipRenderer.Instance?.Show(_placedMaterialId, $"{name} (T{tier})", eventData.position);
            }
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            if (_placedMaterialId == null && _bgImage != null)
                _bgImage.color = COLOR_EMPTY;
            TooltipRenderer.Instance?.Hide();
        }

        /// <summary>Clear this slot's placed material (used by Clear Grid).</summary>
        public void ClearSlot()
        {
            _placedMaterialId = null;
            _updateVisual();
        }
    }
}
