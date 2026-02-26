// ============================================================================
// Game1.Unity.UI.StatsUI
// Migrated from: rendering/renderer.py (lines 6426-6538: render_stats_ui)
// Migration phase: 6
// Date: 2026-02-13
//
// Character stats allocation screen — 6 stats with point spending.
// Self-building: if _panel is null at startup, _buildUI() constructs the
// entire hierarchy from code using UIHelper (no prefab/scene setup needed).
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Character stats allocation panel.
    /// 6 stats (STR, DEF, VIT, LCK, AGI, INT) with +/- buttons.
    /// </summary>
    public class StatsUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Stat Rows")]
        [SerializeField] private StatRow[] _statRows;

        [Header("Unallocated Points")]
        [SerializeField] private TextMeshProUGUI _pointsText;

        private GameStateManager _stateManager;
        private InputManager _inputManager;

        // References populated by _buildUI()
        private Text _pointsLabel;
        private Text _levelClassLabel;

        [System.Serializable]
        public class StatRow
        {
            public string StatName;
            public TextMeshProUGUI NameLabel;
            public TextMeshProUGUI ValueLabel;
            public TextMeshProUGUI BonusLabel;
            public Button AllocateButton;

            // Additional references for programmatic construction
            [System.NonSerialized] public Text NameText;
            [System.NonSerialized] public Text ValueText;
            [System.NonSerialized] public Text BonusText;
            [System.NonSerialized] public Button DecrementButton;
        }

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();

            if (_inputManager != null) _inputManager.OnToggleStats += _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged += _onStateChanged;

            // Bind allocate buttons
            if (_statRows != null)
            {
                foreach (var row in _statRows)
                {
                    if (row.AllocateButton != null)
                    {
                        var statName = row.StatName;
                        row.AllocateButton.onClick.AddListener(() => _allocateStat(statName));
                    }
                }
            }

            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null) _inputManager.OnToggleStats -= _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged -= _onStateChanged;
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private static readonly string[] STAT_NAMES = { "STR", "DEF", "VIT", "LCK", "AGI", "INT" };
        private static readonly string[] STAT_DESCRIPTIONS =
        {
            "+5% melee/mining dmg per pt",
            "+2% damage reduction per pt",
            "+15 HP per pt",
            "+2% crit chance per pt",
            "+5% forestry dmg per pt",
            "-2% difficulty, +20 mana per pt"
        };

        /// <summary>
        /// Construct the entire stats panel hierarchy from code.
        /// Right-side panel with:
        ///   Header "CHARACTER STATS [C/ESC]"
        ///   Level / class info
        ///   Unallocated points display
        ///   6 stat rows: Name | Value | -/+ buttons | bonus text
        ///   Footer close hint
        /// </summary>
        private void _buildUI()
        {
            // -- Root panel: right side, 380 x full height
            var panelRt = UIHelper.CreatePanel(
                transform, "StatsPanel", UIHelper.COLOR_BG_DARK,
                anchorMin: new Vector2(1, 0),
                anchorMax: new Vector2(1, 1),
                offsetMin: new Vector2(-380, 8),
                offsetMax: new Vector2(-8, -8));

            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 6, 6));

            // -- Header
            UIHelper.CreateHeaderRow(panelRt, "CHARACTER STATS", "[C / ESC]", height: 38f);

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Level / Class info row
            var infoRow = UIHelper.CreatePanel(
                panelRt, "InfoRow", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(infoRow.gameObject, 28f);

            _levelClassLabel = UIHelper.CreateText(infoRow, "LevelClassLabel",
                "Level 1 | No Class", 15, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);

            // -- Unallocated points row
            var pointsRow = UIHelper.CreatePanel(
                panelRt, "PointsRow", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(pointsRow.gameObject, 30f);

            _pointsLabel = UIHelper.CreateText(pointsRow, "PointsLabel",
                "Unallocated Points: 0", 16, UIHelper.COLOR_TEXT_GREEN, TextAnchor.MiddleCenter);

            // -- Divider
            UIHelper.CreateDivider(panelRt, 2f);

            // -- Stat rows
            _statRows = new StatRow[STAT_NAMES.Length];

            for (int i = 0; i < STAT_NAMES.Length; i++)
            {
                var stat = STAT_NAMES[i];
                var desc = STAT_DESCRIPTIONS[i];

                // Row container
                var rowRt = UIHelper.CreatePanel(
                    panelRt, $"StatRow_{stat}", UIHelper.COLOR_BG_PANEL,
                    Vector2.zero, Vector2.one);
                UIHelper.SetPreferredHeight(rowRt.gameObject, 48f);

                // Horizontal layout for row contents
                UIHelper.AddHorizontalLayout(rowRt, spacing: 4f,
                    padding: new RectOffset(8, 8, 4, 4), childForceExpand: false);

                // Stat name label (fixed width ~50)
                var nameGo = new GameObject($"Name_{stat}");
                nameGo.transform.SetParent(rowRt, false);
                nameGo.AddComponent<RectTransform>();
                var nameText = UIHelper.CreateText(nameGo.transform, "Text", stat,
                    18, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleLeft);
                var nameLE = nameGo.AddComponent<LayoutElement>();
                nameLE.preferredWidth = 50f;
                nameLE.flexibleWidth = 0f;

                // Value label (fixed width ~36)
                var valGo = new GameObject($"Value_{stat}");
                valGo.transform.SetParent(rowRt, false);
                valGo.AddComponent<RectTransform>();
                var valText = UIHelper.CreateText(valGo.transform, "Text", "0",
                    18, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);
                var valLE = valGo.AddComponent<LayoutElement>();
                valLE.preferredWidth = 36f;
                valLE.flexibleWidth = 0f;

                // Minus button
                var capturedStat = stat;
                var minusBtn = UIHelper.CreateButton(
                    rowRt, $"Minus_{stat}", "-",
                    UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_RED, 18,
                    () => _deallocateStat(capturedStat));
                var minusBtnLE = minusBtn.gameObject.AddComponent<LayoutElement>();
                minusBtnLE.preferredWidth = 32f;
                minusBtnLE.preferredHeight = 32f;
                minusBtnLE.flexibleWidth = 0f;

                // Plus button
                var plusBtn = UIHelper.CreateButton(
                    rowRt, $"Plus_{stat}", "+",
                    UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_GREEN, 18,
                    () => _allocateStat(capturedStat));
                var plusBtnLE = plusBtn.gameObject.AddComponent<LayoutElement>();
                plusBtnLE.preferredWidth = 32f;
                plusBtnLE.preferredHeight = 32f;
                plusBtnLE.flexibleWidth = 0f;

                // Bonus description text (fills remaining space)
                var bonusGo = new GameObject($"Bonus_{stat}");
                bonusGo.transform.SetParent(rowRt, false);
                bonusGo.AddComponent<RectTransform>();
                var bonusText = UIHelper.CreateText(bonusGo.transform, "Text", desc,
                    12, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleLeft);
                var bonusLE = bonusGo.AddComponent<LayoutElement>();
                bonusLE.flexibleWidth = 1f;

                // Build the StatRow reference
                _statRows[i] = new StatRow
                {
                    StatName = stat,
                    NameText = nameText,
                    ValueText = valText,
                    BonusText = bonusText,
                    AllocateButton = plusBtn,
                    DecrementButton = minusBtn
                };
            }

            // -- Spacer to push content up
            var spacer = new GameObject("Spacer");
            spacer.transform.SetParent(panelRt, false);
            spacer.AddComponent<RectTransform>();
            var spacerLE = spacer.AddComponent<LayoutElement>();
            spacerLE.flexibleHeight = 1f;
        }

        // ====================================================================
        // Refresh
        // ====================================================================

        public void Refresh()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null || _statRows == null) return;

            var stats = gm.Player.Stats;
            var leveling = gm.Player.Leveling;

            // Update level / class info (programmatic label)
            if (_levelClassLabel != null)
            {
                string className = gm.Player.GetClassDefinition()?.Name ?? "No Class";
                _levelClassLabel.text = $"Level {leveling.Level} | {className}";
            }

            foreach (var row in _statRows)
            {
                if (row == null) continue;

                int value = stats.GetStat(row.StatName);

                // Update TMP labels (inspector-wired path)
                if (row.ValueLabel != null)
                    row.ValueLabel.text = value.ToString();

                // Update programmatic labels
                if (row.ValueText != null)
                    row.ValueText.text = value.ToString();

                // Compute bonus text
                string bonus = row.StatName switch
                {
                    "STR" => $"+{value * GameConfig.StrDamagePerPoint * 100:F0}% dmg",
                    "DEF" => $"+{value * GameConfig.DefReductionPerPoint * 100:F0}% red",
                    "VIT" => $"+{value * GameConfig.VitHpPerPoint} HP",
                    "LCK" => $"+{value * GameConfig.LckCritPerPoint * 100:F0}% crit",
                    "AGI" => $"+{value * GameConfig.AgiForestryPerPoint * 100:F0}% forestry",
                    "INT" => $"-{value * GameConfig.IntDifficultyPerPoint * 100:F0}% diff, +{value * GameConfig.IntManaPerPoint} mana",
                    _ => ""
                };

                // Update TMP bonus label (inspector path)
                if (row.BonusLabel != null)
                    row.BonusLabel.text = bonus;

                // Update programmatic bonus label
                if (row.BonusText != null)
                    row.BonusText.text = bonus;

                // Enable/disable allocate button
                bool canAllocate = leveling.UnallocatedStatPoints > 0 && value < 30;
                if (row.AllocateButton != null)
                    row.AllocateButton.interactable = canAllocate;

                // Enable/disable minus button
                if (row.DecrementButton != null)
                    row.DecrementButton.interactable = value > 0;
            }

            // Update points text (TMP path)
            if (_pointsText != null)
                _pointsText.text = $"Points: {leveling.UnallocatedStatPoints}";

            // Update points text (programmatic path)
            if (_pointsLabel != null)
                _pointsLabel.text = $"Unallocated Points: {leveling.UnallocatedStatPoints}";
        }

        // ====================================================================
        // Stat Allocation
        // ====================================================================

        private void _allocateStat(string statName)
        {
            var gm = GameManager.Instance;
            if (gm?.Player?.AllocateStatPoint(statName) == true)
            {
                Refresh();
            }
        }

        private void _deallocateStat(string statName)
        {
            // TODO: Implement deallocation if supported by game design
            // For now this is a no-op placeholder for the minus button
        }

        // ====================================================================
        // Visibility
        // ====================================================================

        private void _onToggle() => _stateManager?.TogglePanel(GameState.StatsOpen);
        private void _onStateChanged(GameState old, GameState next)
        {
            _setVisible(next == GameState.StatsOpen);
            if (next == GameState.StatsOpen) Refresh();
        }

        private void _setVisible(bool v)
        {
            if (_panel != null) _panel.SetActive(v);
        }
    }
}
