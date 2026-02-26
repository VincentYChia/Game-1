// ============================================================================
// Game1.Unity.UI.StatusBarUI
// Migrated from: rendering/renderer.py (lines 2256-2323: health/mana/buff bars)
// Migration phase: 6
// Date: 2026-02-13
//
// HUD element: HP bar, Mana bar, EXP bar, level display, buff icons.
// Always visible during gameplay.
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
    /// Status bar HUD — HP, Mana, EXP bars with numeric labels.
    /// Updates every frame from Character stats.
    /// </summary>
    public class StatusBarUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private RectTransform _panel;

        [Header("Health Bar")]
        [SerializeField] private Image _healthFill;
        [SerializeField] private TextMeshProUGUI _healthText;
        [SerializeField] private Color _healthFullColor = new Color(0f, 0.8f, 0f);
        [SerializeField] private Color _healthLowColor = new Color(0.8f, 0f, 0f);

        [Header("Mana Bar")]
        [SerializeField] private Image _manaFill;
        [SerializeField] private TextMeshProUGUI _manaText;
        [SerializeField] private Color _manaColor = new Color(0.2f, 0.4f, 1f);

        [Header("Experience Bar")]
        [SerializeField] private Image _expFill;
        [SerializeField] private TextMeshProUGUI _expText;
        [SerializeField] private Color _expColor = new Color(1f, 0.84f, 0f);

        [Header("Level")]
        [SerializeField] private TextMeshProUGUI _levelText;

        [Header("Buff Container")]
        [SerializeField] private Transform _buffContainer;
        [SerializeField] private GameObject _buffIconPrefab;

        // Labels created by _buildUI (Unity UI Text used internally, mapped to TMP fields)
        private Text _healthLabel;
        private Text _manaLabel;
        private Text _expLabel;
        private Text _levelLabel;

        private GameStateManager _stateManager;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
        }

        private void Update()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            // Only show during gameplay
            bool visible = _stateManager == null
                || _stateManager.CurrentState == GameState.Playing
                || _stateManager.IsInModalUI;

            foreach (Transform child in transform)
                child.gameObject.SetActive(visible);

            if (!visible) return;

            var player = gm.Player;

            // Health
            float healthPct = player.MaxHealth > 0 ? player.CurrentHealth / player.MaxHealth : 0f;
            if (_healthFill != null)
            {
                _healthFill.fillAmount = healthPct;
                _healthFill.color = Color.Lerp(_healthLowColor, _healthFullColor, healthPct);
            }
            if (_healthText != null)
                _healthText.text = $"{Mathf.CeilToInt(player.CurrentHealth)}/{Mathf.CeilToInt(player.MaxHealth)}";
            if (_healthLabel != null)
                _healthLabel.text = $"HP: {Mathf.CeilToInt(player.CurrentHealth)}/{Mathf.CeilToInt(player.MaxHealth)}";

            // Mana
            float manaPct = player.MaxMana > 0 ? player.CurrentMana / player.MaxMana : 0f;
            if (_manaFill != null)
            {
                _manaFill.fillAmount = manaPct;
                _manaFill.color = _manaColor;
            }
            if (_manaText != null)
                _manaText.text = $"{Mathf.CeilToInt(player.CurrentMana)}/{Mathf.CeilToInt(player.MaxMana)}";
            if (_manaLabel != null)
                _manaLabel.text = $"Mana: {Mathf.CeilToInt(player.CurrentMana)}/{Mathf.CeilToInt(player.MaxMana)}";

            // Experience
            int level = player.Leveling.Level;
            int currentExp = player.Leveling.CurrentExp;
            int expNeeded = GameConfig.GetExpForLevel(level);
            float expPct = expNeeded > 0 ? (float)currentExp / expNeeded : 0f;
            if (_expFill != null)
            {
                _expFill.fillAmount = expPct;
                _expFill.color = _expColor;
            }
            if (_expText != null)
                _expText.text = $"{currentExp}/{expNeeded}";
            if (_expLabel != null)
                _expLabel.text = $"EXP: {currentExp}/{expNeeded}";

            // Level
            if (_levelText != null)
                _levelText.text = $"Lv. {level}";
            if (_levelLabel != null)
                _levelLabel.text = $"Lv. {level}";
        }

        /// <summary>
        /// Programmatically build all UI elements when SerializeField references are null.
        /// Creates HP, Mana, and EXP progress bars with label overlays and a level text.
        /// </summary>
        private void _buildUI()
        {
            // Root panel — anchored to top-left corner
            _panel = UIHelper.CreatePanel(transform, "StatusPanel", UIHelper.COLOR_TRANSPARENT,
                new Vector2(0f, 1f), new Vector2(0f, 1f));
            _panel.pivot = new Vector2(0f, 1f);
            _panel.sizeDelta = new Vector2(320, 90);
            _panel.anchoredPosition = new Vector2(10, -10);

            // --- HP Bar ---
            var (hpRoot, hpBg, hpFill, hpLabel) = UIHelper.CreateProgressBar(
                _panel, "HealthBar",
                UIHelper.COLOR_BG_DARK, UIHelper.COLOR_HP_FULL,
                new Vector2(300, 24),
                new Vector2(0, -12));
            // Anchor to top-left within panel
            hpRoot.anchorMin = new Vector2(0f, 1f);
            hpRoot.anchorMax = new Vector2(0f, 1f);
            hpRoot.pivot = new Vector2(0f, 1f);
            hpRoot.anchoredPosition = new Vector2(5, -2);

            _healthFill = hpFill;
            _healthLabel = hpLabel;
            _healthLabel.text = "HP: 100/100";

            // --- Mana Bar ---
            var (manaRoot, manaBg, manaFill, manaLabel) = UIHelper.CreateProgressBar(
                _panel, "ManaBar",
                UIHelper.COLOR_BG_DARK, UIHelper.COLOR_MANA,
                new Vector2(300, 20),
                new Vector2(0, 0));
            manaRoot.anchorMin = new Vector2(0f, 1f);
            manaRoot.anchorMax = new Vector2(0f, 1f);
            manaRoot.pivot = new Vector2(0f, 1f);
            manaRoot.anchoredPosition = new Vector2(5, -30);

            _manaFill = manaFill;
            _manaLabel = manaLabel;
            _manaLabel.text = "Mana: 100/100";

            // --- EXP Bar ---
            var (expRoot, expBg, expFill, expLabel) = UIHelper.CreateProgressBar(
                _panel, "ExpBar",
                UIHelper.COLOR_BG_DARK, UIHelper.COLOR_EXP,
                new Vector2(300, 16),
                new Vector2(0, 0));
            expRoot.anchorMin = new Vector2(0f, 1f);
            expRoot.anchorMax = new Vector2(0f, 1f);
            expRoot.pivot = new Vector2(0f, 1f);
            expRoot.anchoredPosition = new Vector2(5, -54);

            _expFill = expFill;
            _expLabel = expLabel;
            _expLabel.text = "EXP: 0/200";

            // --- Level Text — top-right of panel ---
            _levelLabel = UIHelper.CreateSizedText(
                _panel, "LevelText", "Lv. 1",
                18, UIHelper.COLOR_TEXT_GOLD,
                new Vector2(80, 24), Vector2.zero,
                TextAnchor.MiddleRight);
            var levelRt = _levelLabel.rectTransform;
            levelRt.anchorMin = new Vector2(1f, 1f);
            levelRt.anchorMax = new Vector2(1f, 1f);
            levelRt.pivot = new Vector2(1f, 1f);
            levelRt.anchoredPosition = new Vector2(-5, -4);
        }
    }
}
