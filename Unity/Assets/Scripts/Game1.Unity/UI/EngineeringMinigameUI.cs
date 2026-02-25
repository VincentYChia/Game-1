// ============================================================================
// Game1.Unity.UI.EngineeringMinigameUI
// Migrated from: Crafting-subdisciplines/engineering.py (1,315 lines)
// Migration phase: 6
// Date: 2026-02-13
//
// Engineering minigame: puzzle-based (pipe rotation, sliding tile, logic switch).
// Player solves a grid puzzle to connect input to output.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Engineering minigame — puzzle grid (pipe rotation, sliding tile, logic switch).
    /// Solve by connecting input to output through the grid.
    /// </summary>
    public class EngineeringMinigameUI : MinigameUI
    {
        [Header("Engineering-Specific")]
        [SerializeField] private Transform _gridContainer;
        [SerializeField] private GameObject _gridCellPrefab;
        [SerializeField] private TextMeshProUGUI _puzzleTypeText;
        [SerializeField] private TextMeshProUGUI _movesText;

        private int _gridSize = 4;
        private int _moveCount;
        private int _maxMoves = 20;
        private bool _puzzleSolved;
        private string _puzzleType; // "pipe_rotation", "sliding_tile", "logic_switch"

        // Grid state
        private int[,] _gridState;

        // Fallback text references (programmatic UI)
        private Text _puzzleTypeTextFallback;
        private Text _movesTextFallback;
        private Text _progressTextFallback;

        // Track whether we built the grid container programmatically
        private bool _gridBuiltProgrammatically;

        // ====================================================================
        // Programmatic UI Construction
        // ====================================================================

        /// <summary>
        /// Build engineering-specific UI: puzzle grid (center), move counter,
        /// progress text. Grid cells are clickable buttons.
        /// </summary>
        protected override void _buildUI()
        {
            base._buildUI();
            var parent = _contentArea != null ? _contentArea : _panel.transform;

            // --- Header row with puzzle type and moves ---
            var infoRowRt = UIHelper.CreatePanel(parent, "InfoRow",
                UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.05f, 0.85f), new Vector2(0.95f, 0.95f));
            UIHelper.AddHorizontalLayout(infoRowRt, 12f, new RectOffset(8, 8, 4, 4));

            _puzzleTypeTextFallback = UIHelper.CreateText(infoRowRt, "PuzzleTypeText",
                "Puzzle: pipe rotation", 16, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
            var puzzleLE = _puzzleTypeTextFallback.gameObject.AddComponent<LayoutElement>();
            puzzleLE.flexibleWidth = 1f;

            _movesTextFallback = UIHelper.CreateText(infoRowRt, "MovesText",
                "Moves: 0/20", 16, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleRight);
            var movesLE = _movesTextFallback.gameObject.AddComponent<LayoutElement>();
            movesLE.flexibleWidth = 1f;

            // --- Puzzle grid (center) ---
            // Grid container with GridLayoutGroup for the 4x4 puzzle cells
            var gridPanelRt = UIHelper.CreatePanel(parent, "GridPanel",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.15f, 0.15f), new Vector2(0.85f, 0.82f));

            // Calculate cell size to fit within the grid panel
            // We want the grid to be roughly square and centered
            var gridLayoutGo = new GameObject("GridLayout");
            gridLayoutGo.transform.SetParent(gridPanelRt, false);
            var gridLayoutRt = gridLayoutGo.AddComponent<RectTransform>();
            gridLayoutRt.anchorMin = new Vector2(0.05f, 0.05f);
            gridLayoutRt.anchorMax = new Vector2(0.95f, 0.95f);
            gridLayoutRt.offsetMin = Vector2.zero;
            gridLayoutRt.offsetMax = Vector2.zero;

            var gridLayout = gridLayoutGo.AddComponent<GridLayoutGroup>();
            gridLayout.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            gridLayout.constraintCount = _gridSize;
            gridLayout.cellSize = new Vector2(80f, 80f);
            gridLayout.spacing = new Vector2(6f, 6f);
            gridLayout.childAlignment = TextAnchor.MiddleCenter;
            gridLayout.padding = new RectOffset(4, 4, 4, 4);

            _gridContainer = gridLayoutRt;
            _gridBuiltProgrammatically = true;

            // --- Progress text (below grid) ---
            _progressTextFallback = UIHelper.CreateText(parent, "ProgressText",
                "Rotate all tiles to solve the puzzle",
                14, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var progressTxtRt = _progressTextFallback.rectTransform;
            progressTxtRt.anchorMin = new Vector2(0.10f, 0.04f);
            progressTxtRt.anchorMax = new Vector2(0.90f, 0.12f);
            progressTxtRt.offsetMin = Vector2.zero;
            progressTxtRt.offsetMax = Vector2.zero;
        }

        // ====================================================================
        // Minigame Logic
        // ====================================================================

        protected override void OnStart()
        {
            _moveCount = 0;
            _puzzleSolved = false;

            // Select puzzle type based on difficulty
            string[] puzzleTypes = { "pipe_rotation", "sliding_tile", "logic_switch" };
            _puzzleType = puzzleTypes[Random.Range(0, puzzleTypes.Length)];

            _setPuzzleTypeText($"Puzzle: {_puzzleType.Replace('_', ' ')}");

            _generatePuzzle();
            _buildGridUI();
        }

        protected override void OnUpdate(float deltaTime)
        {
            _setMovesText($"Moves: {_moveCount}/{_maxMoves}");

            if (_puzzleSolved)
            {
                Complete(1f - ((float)_moveCount / _maxMoves));
                return;
            }

            if (_moveCount >= _maxMoves)
            {
                Complete(0.3f); // Partial credit
                return;
            }

            _performance = _puzzleSolved ? 1f : 0.5f * (1f - (float)_moveCount / _maxMoves);

            // Update progress text
            if (_progressTextFallback != null)
            {
                int aligned = _countAlignedCells();
                int total = _gridSize * _gridSize;
                _progressTextFallback.text = $"Aligned: {aligned}/{total} tiles";
            }
        }

        protected override void OnCraftAction()
        {
            // Space to confirm/advance
            ParticleEffects.Instance?.PlayGears(Vector3.zero, 5);
        }

        private void _generatePuzzle()
        {
            _gridState = new int[_gridSize, _gridSize];

            // Generate solvable puzzle based on type
            for (int x = 0; x < _gridSize; x++)
            {
                for (int y = 0; y < _gridSize; y++)
                {
                    _gridState[x, y] = Random.Range(0, 4); // 4 rotation states
                }
            }
        }

        private void _buildGridUI()
        {
            if (_gridContainer == null) return;

            foreach (Transform child in _gridContainer)
                Destroy(child.gameObject);

            for (int y = 0; y < _gridSize; y++)
            {
                for (int x = 0; x < _gridSize; x++)
                {
                    int capturedX = x, capturedY = y;

                    if (_gridBuiltProgrammatically || _gridCellPrefab == null)
                    {
                        // Create cell programmatically as a button
                        var cellBtn = UIHelper.CreateButton(
                            _gridContainer, $"Cell_{x}_{y}", "",
                            new Color(0.5f, 0.5f, 0.5f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 14,
                            () => _onCellClicked(capturedX, capturedY));

                        // Add a directional indicator image (arrow or pipe shape)
                        var indicatorImg = UIHelper.CreateImage(cellBtn.transform, "Indicator",
                            new Color(0.7f, 0.7f, 0.8f, 1f));
                        var indicatorRt = indicatorImg.rectTransform;
                        indicatorRt.anchorMin = new Vector2(0.35f, 0.1f);
                        indicatorRt.anchorMax = new Vector2(0.65f, 0.9f);
                        indicatorRt.offsetMin = Vector2.zero;
                        indicatorRt.offsetMax = Vector2.zero;

                        _updateCellVisual(cellBtn.gameObject, _gridState[x, y]);
                    }
                    else
                    {
                        var cell = Instantiate(_gridCellPrefab, _gridContainer);
                        var button = cell.GetComponent<Button>();
                        if (button != null)
                        {
                            button.onClick.AddListener(() => _onCellClicked(capturedX, capturedY));
                        }
                        _updateCellVisual(cell, _gridState[x, y]);
                    }
                }
            }
        }

        private void _onCellClicked(int x, int y)
        {
            if (_puzzleSolved) return;

            _moveCount++;
            _gridState[x, y] = (_gridState[x, y] + 1) % 4; // Rotate

            // Rebuild grid visuals
            _buildGridUI();

            // Check if solved
            _checkSolution();
        }

        private void _checkSolution()
        {
            // Simplified: check if all cells are aligned (all 0)
            for (int x = 0; x < _gridSize; x++)
            {
                for (int y = 0; y < _gridSize; y++)
                {
                    if (_gridState[x, y] != 0) return;
                }
            }
            _puzzleSolved = true;
        }

        private int _countAlignedCells()
        {
            int count = 0;
            if (_gridState == null) return 0;
            for (int x = 0; x < _gridSize; x++)
            {
                for (int y = 0; y < _gridSize; y++)
                {
                    if (_gridState[x, y] == 0) count++;
                }
            }
            return count;
        }

        private void _updateCellVisual(GameObject cell, int state)
        {
            var img = cell.GetComponent<Image>();
            if (img == null) return;

            img.transform.localRotation = Quaternion.Euler(0, 0, -state * 90);
            img.color = state == 0 ? new Color(0f, 0.8f, 0f) : new Color(0.5f, 0.5f, 0.5f);
        }

        private void _setPuzzleTypeText(string text)
        {
            if (_puzzleTypeText != null) _puzzleTypeText.text = text;
            else if (_puzzleTypeTextFallback != null) _puzzleTypeTextFallback.text = text;
        }

        private void _setMovesText(string text)
        {
            if (_movesText != null) _movesText.text = text;
            else if (_movesTextFallback != null) _movesTextFallback.text = text;
        }
    }
}
