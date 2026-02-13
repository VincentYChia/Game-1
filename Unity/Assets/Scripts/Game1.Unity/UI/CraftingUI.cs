// ============================================================================
// Game1.Unity.UI.CraftingUI
// Migrated from: rendering/renderer.py (lines 4429-5720: crafting UI)
//              + game_engine.py (lines 3169-3550: interactive clicks)
// Migration phase: 6
// Date: 2026-02-13
//
// Crafting station interaction: recipe selection, material placement, craft/invent.
// Handles all 5 disciplines' placement grids.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
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

        private GameStateManager _stateManager;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
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
        // Public API
        // ====================================================================

        /// <summary>Open crafting UI for a specific discipline and station tier.</summary>
        public void Open(string discipline, int stationTier)
        {
            _currentDiscipline = discipline;
            _stationTier = stationTier;
            _selectedRecipe = null;
            _placedMaterials.Clear();

            _loadRecipes();
            _buildGrid();
            _buildPalette();
            _updateDifficulty();

            _stateManager?.TransitionTo(GameState.CraftingOpen);
        }

        /// <summary>Close the crafting UI.</summary>
        public void Close()
        {
            _stateManager?.TransitionTo(GameState.Playing);
        }

        // ====================================================================
        // Recipe Loading
        // ====================================================================

        private void _loadRecipes()
        {
            _availableRecipes.Clear();

            var recipes = RecipeDatabase.Instance.GetRecipesForStation(_currentDiscipline, _stationTier);
            if (recipes != null)
            {
                _availableRecipes.AddRange(recipes);
            }

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
                if (_recipeEntryPrefab == null || _recipeListContainer == null) continue;

                var entry = Instantiate(_recipeEntryPrefab, _recipeListContainer);
                var text = entry.GetComponentInChildren<TextMeshProUGUI>();
                if (text != null) text.text = recipe.OutputId;

                var button = entry.GetComponent<Button>();
                var capturedRecipe = recipe;
                if (button != null)
                    button.onClick.AddListener(() => _selectRecipe(capturedRecipe));
            }
        }

        private void _selectRecipe(Recipe recipe)
        {
            _selectedRecipe = recipe;
            if (_selectedRecipeTitle != null)
                _selectedRecipeTitle.text = recipe.OutputId;
            if (_selectedRecipeDesc != null)
                _selectedRecipeDesc.text = $"Tier: {recipe.StationTier} | Qty: {recipe.OutputQty}";

            _placedMaterials.Clear();
            _buildGrid();
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

        private void _buildSmithingGrid()
        {
            // Grid size based on station tier: T1=3x3, T2=5x5, T3=7x7, T4=9x9
            int gridSize = 3 + (_stationTier - 1) * 2;
            gridSize = Mathf.Clamp(gridSize, 3, 9);

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
            // Sequential ingredient slots
            int slots = 3 + _stationTier;
            for (int i = 0; i < slots; i++)
            {
                _createGridSlot($"seq_{i}");
            }
        }

        private void _buildRefiningHub()
        {
            // Hub-spoke layout: 1 core + surrounding slots
            _createGridSlot("core");
            int surrounding = 4 + _stationTier;
            for (int i = 0; i < surrounding; i++)
            {
                _createGridSlot($"surround_{i}");
            }
        }

        private void _buildEngineeringSlots()
        {
            // Named slot types
            string[] slotTypes = { "frame", "core", "mechanism", "power", "output" };
            foreach (string slot in slotTypes)
            {
                _createGridSlot(slot);
            }
        }

        private void _buildEnchantingGrid()
        {
            // Cartesian grid for adornment patterns
            int gridSize = 4 + _stationTier;
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
            if (_gridSlotPrefab == null || _gridContainer == null) return;

            var slot = Instantiate(_gridSlotPrefab, _gridContainer);
            var slotComp = slot.GetComponent<CraftingGridSlot>();
            if (slotComp == null) slotComp = slot.AddComponent<CraftingGridSlot>();
            slotComp.Initialize(slotKey, this);
        }

        // ====================================================================
        // Material Palette
        // ====================================================================

        private void _buildPalette()
        {
            if (_paletteContainer == null) return;

            foreach (Transform child in _paletteContainer)
                Destroy(child.gameObject);

            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            // Show inventory materials
            var allSlots = gm.Player.Inventory.GetAllSlots();
            foreach (var itemSlot in allSlots)
            {
                if (itemSlot == null || string.IsNullOrEmpty(itemSlot.ItemId)) continue;

                if (_paletteItemPrefab != null)
                {
                    var item = Instantiate(_paletteItemPrefab, _paletteContainer);
                    var icon = item.GetComponentInChildren<Image>();
                    if (icon != null && SpriteDatabase.Instance != null)
                        icon.sprite = SpriteDatabase.Instance.GetItemSprite(itemSlot.ItemId);

                    var qty = item.GetComponentInChildren<TextMeshProUGUI>();
                    if (qty != null)
                        qty.text = itemSlot.Quantity.ToString();
                }
            }
        }

        // ====================================================================
        // Material Placement
        // ====================================================================

        public void PlaceMaterial(string slotKey, string materialId)
        {
            _placedMaterials[slotKey] = materialId;
            _updateDifficulty();
        }

        public void RemoveMaterial(string slotKey)
        {
            _placedMaterials.Remove(slotKey);
            _updateDifficulty();
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

            // Start minigame for this recipe
            _stateManager?.TransitionTo(GameState.MinigameActive);
        }

        private void _onClearClicked()
        {
            _placedMaterials.Clear();
            _buildGrid();
            _updateDifficulty();
        }

        private void _onInventClicked()
        {
            if (_placedMaterials.Count == 0)
            {
                NotificationUI.Instance?.Show("Place materials first!", Color.yellow);
                return;
            }

            // Validate via classifier (Phase 5)
            NotificationUI.Instance?.Show("Validating placement...", Color.cyan);
            // ClassifierManager.Instance.Validate(_currentDiscipline, ...) would be called here
        }

        private void _updateDifficulty()
        {
            if (_difficultyText == null) return;

            int points = _placedMaterials.Count; // Simplified
            string tier = points switch
            {
                <= 4 => "Common",
                <= 10 => "Uncommon",
                <= 20 => "Rare",
                <= 40 => "Epic",
                _ => "Legendary"
            };

            _difficultyText.text = $"Difficulty: {tier} ({points} pts)";
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

    /// <summary>Single slot in the crafting placement grid.</summary>
    public class CraftingGridSlot : MonoBehaviour, IDropHandler, IPointerClickHandler
    {
        private string _slotKey;
        private CraftingUI _craftingUI;
        private string _placedMaterialId;
        private Image _iconImage;

        public void Initialize(string slotKey, CraftingUI craftingUI)
        {
            _slotKey = slotKey;
            _craftingUI = craftingUI;
            _iconImage = GetComponentInChildren<Image>();
        }

        public void OnDrop(PointerEventData eventData)
        {
            var ddm = DragDropManager.Instance;
            if (ddm == null || !ddm.IsDragging) return;

            _placedMaterialId = ddm.DraggedItemId;
            _craftingUI?.PlaceMaterial(_slotKey, _placedMaterialId);

            if (_iconImage != null && SpriteDatabase.Instance != null)
                _iconImage.sprite = SpriteDatabase.Instance.GetItemSprite(_placedMaterialId);

            ddm.CompleteDrop(DragDropManager.DragSource.CraftingGrid, 0);
        }

        public void OnPointerClick(PointerEventData eventData)
        {
            if (eventData.button == PointerEventData.InputButton.Right && _placedMaterialId != null)
            {
                _placedMaterialId = null;
                _craftingUI?.RemoveMaterial(_slotKey);
                if (_iconImage != null) _iconImage.sprite = null;
            }
        }
    }
}
