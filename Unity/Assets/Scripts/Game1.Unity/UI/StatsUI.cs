// ============================================================================
// Game1.Unity.UI.StatsUI
// Migrated from: rendering/renderer.py (lines 6426-6538: render_stats_ui)
// Migration phase: 6
// Date: 2026-02-13
//
// Character stats allocation screen — 6 stats with point spending.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Unity.Core;

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

        [System.Serializable]
        public class StatRow
        {
            public string StatName;
            public TextMeshProUGUI NameLabel;
            public TextMeshProUGUI ValueLabel;
            public TextMeshProUGUI BonusLabel;
            public Button AllocateButton;
        }

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
            _inputManager = FindFirstObjectByType<InputManager>();

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

        public void Refresh()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null || _statRows == null) return;

            var stats = gm.Player.Stats;
            var leveling = gm.Player.Leveling;

            foreach (var row in _statRows)
            {
                if (row == null) continue;

                int value = stats.GetStat(row.StatName);
                if (row.ValueLabel != null)
                    row.ValueLabel.text = value.ToString();

                if (row.BonusLabel != null)
                {
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
                    row.BonusLabel.text = bonus;
                }

                if (row.AllocateButton != null)
                    row.AllocateButton.interactable = leveling.UnallocatedStatPoints > 0 && value < 30;
            }

            if (_pointsText != null)
                _pointsText.text = $"Points: {leveling.UnallocatedStatPoints}";
        }

        private void _allocateStat(string statName)
        {
            var gm = GameManager.Instance;
            if (gm?.Player?.AllocateStatPoint(statName) == true)
            {
                Refresh();
            }
        }

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
