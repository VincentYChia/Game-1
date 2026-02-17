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

namespace Game1.Unity.UI
{
    /// <summary>
    /// Status bar HUD — HP, Mana, EXP bars with numeric labels.
    /// Updates every frame from Character stats.
    /// </summary>
    public class StatusBarUI : MonoBehaviour
    {
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

        private GameStateManager _stateManager;

        private void Start()
        {
            _stateManager = FindFirstObjectByType<GameStateManager>();
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

            // Mana
            float manaPct = player.MaxMana > 0 ? player.CurrentMana / player.MaxMana : 0f;
            if (_manaFill != null)
            {
                _manaFill.fillAmount = manaPct;
                _manaFill.color = _manaColor;
            }
            if (_manaText != null)
                _manaText.text = $"{Mathf.CeilToInt(player.CurrentMana)}/{Mathf.CeilToInt(player.MaxMana)}";

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

            // Level
            if (_levelText != null)
                _levelText.text = $"Lv. {level}";
        }
    }
}
