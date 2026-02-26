// ============================================================================
// Game1.Unity.UI.SkillBarUI
// Migrated from: rendering/renderer.py (lines 2323-2475: render_skill_hotbar)
// Migration phase: 6
// Date: 2026-02-13
//
// 5-slot skill hotbar with cooldown overlays and keybind labels.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Skill hotbar UI — 5 slots with skill icons, cooldown overlays, and key labels.
    /// </summary>
    public class SkillBarUI : MonoBehaviour
    {
        [Header("Panel")]
        [SerializeField] private RectTransform _panel;

        [Header("Slot References")]
        [SerializeField] private SkillSlot[] _slots = new SkillSlot[GameConfig.HotbarSlots];

        [Header("Colors")]
        [SerializeField] private Color _readyColor = Color.white;
        [SerializeField] private Color _cooldownColor = new Color(0.3f, 0.3f, 0.3f, 0.8f);
        [SerializeField] private Color _noManaColor = new Color(0.2f, 0.2f, 0.5f, 0.8f);

        private InputManager _inputManager;

        // Labels created by _buildUI (Unity UI Text, separate from TMP fields in SkillSlot)
        private Text[] _keyLabels;
        private Text[] _nameLabels;

        [System.Serializable]
        public class SkillSlot
        {
            public Image IconImage;
            public Image CooldownOverlay;
            public TextMeshProUGUI KeyLabel;
            public TextMeshProUGUI SkillNameLabel;
        }

        private GameStateManager _stateManager;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();
            if (_inputManager != null)
                _inputManager.OnSkillActivate += _onSkillActivate;

            // Set key labels
            for (int i = 0; i < _slots.Length; i++)
            {
                if (_slots[i]?.KeyLabel != null)
                    _slots[i].KeyLabel.text = (i + 1).ToString();
            }
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnSkillActivate -= _onSkillActivate;
        }

        private void Update()
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null)
            {
                // Hide during StartMenu/ClassSelection when there's no player
                foreach (Transform child in transform)
                    child.gameObject.SetActive(false);
                return;
            }

            // Only show during gameplay (Playing or modal UI panels)
            bool visible = _stateManager == null
                || _stateManager.CurrentState == GameState.Playing
                || _stateManager.IsInModalUI;
            foreach (Transform child in transform)
                child.gameObject.SetActive(visible);
            if (!visible) return;

            var skillManager = gm.Player.Skills;

            for (int i = 0; i < _slots.Length; i++)
            {
                if (_slots[i] == null) continue;

                string skillId = skillManager.GetEquippedSkillAt(i);

                if (string.IsNullOrEmpty(skillId))
                {
                    // Empty slot
                    if (_slots[i].IconImage != null)
                    {
                        _slots[i].IconImage.enabled = false;
                    }
                    if (_slots[i].CooldownOverlay != null)
                        _slots[i].CooldownOverlay.fillAmount = 0f;
                    if (_slots[i].SkillNameLabel != null)
                        _slots[i].SkillNameLabel.text = "";
                    if (_nameLabels != null && _nameLabels[i] != null)
                        _nameLabels[i].text = "";
                    continue;
                }

                // Has skill in slot
                if (_slots[i].IconImage != null)
                {
                    _slots[i].IconImage.enabled = true;
                    if (SpriteDatabase.Instance != null)
                        _slots[i].IconImage.sprite = SpriteDatabase.Instance.GetItemSprite(skillId);
                }

                // Cooldown overlay + mana cost display
                var knownSkill = skillManager.GetKnownSkill(skillId);
                float cooldownRemaining = knownSkill?.CurrentCooldown ?? 0f;
                var skillDb = SkillDatabase.Instance;
                var skillDef = skillDb?.GetSkill(skillId);

                if (_slots[i].CooldownOverlay != null)
                {
                    if (cooldownRemaining > 0)
                    {
                        // Divide by max cooldown (from skill definition) for proper fill
                        float maxCooldown = skillDef != null
                            ? skillDb.GetCooldownSeconds(skillDef.Cost.CooldownRaw) : 300f;
                        _slots[i].CooldownOverlay.fillAmount = Mathf.Clamp01(cooldownRemaining / Mathf.Max(maxCooldown, 1f));
                        _slots[i].CooldownOverlay.color = _cooldownColor;
                    }
                    else
                    {
                        _slots[i].CooldownOverlay.fillAmount = 0f;
                    }
                }

                // Skill name label (code-built path)
                if (_nameLabels != null && i < _nameLabels.Length && _nameLabels[i] != null)
                {
                    string skillName = skillDef?.Name ?? skillId;
                    _nameLabels[i].text = skillName.Length > 8 ? skillName.Substring(0, 8) : skillName;

                    // Show mana cost color: blue if enough mana, red if not
                    if (skillDef != null)
                    {
                        int manaCost = skillDb.GetManaCost(skillDef.Cost.ManaCostRaw);
                        float playerMana = gm.Player.Stats?.CurrentMana ?? 0f;
                        _nameLabels[i].color = playerMana >= manaCost
                            ? UIHelper.COLOR_TEXT_SECONDARY : new Color(1f, 0.3f, 0.3f);
                    }
                }
            }
        }

        private void _onSkillActivate(int slotIndex)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            if (slotIndex >= 0 && slotIndex < GameConfig.HotbarSlots)
            {
                string skillId = gm.Player.Skills.GetEquippedSkillAt(slotIndex);
                if (!string.IsNullOrEmpty(skillId))
                {
                    gm.Player.Skills.ActivateSkill(skillId);
                }
            }
        }

        /// <summary>
        /// Programmatically build the skill bar UI when SerializeField references are null.
        /// Creates 5 horizontal skill slots at bottom-center with icons, keybind labels,
        /// cooldown overlays, and name text below each slot.
        /// </summary>
        private void _buildUI()
        {
            // Root panel — anchored to bottom-center
            _panel = UIHelper.CreatePanel(transform, "SkillBarPanel", UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.5f, 0f), new Vector2(0.5f, 0f));
            _panel.pivot = new Vector2(0.5f, 0f);
            // 5 slots * 60 + 4 * spacing(8) + padding(8+8) = 300 + 32 + 16 = 348
            _panel.sizeDelta = new Vector2(348, 90);
            _panel.anchoredPosition = new Vector2(0, 10);

            // Container with horizontal layout
            var containerRt = UIHelper.CreatePanel(_panel, "SlotContainer", UIHelper.COLOR_BG_DARK,
                Vector2.zero, Vector2.one);
            containerRt.offsetMin = Vector2.zero;
            containerRt.offsetMax = Vector2.zero;

            var hlg = UIHelper.AddHorizontalLayout(containerRt, 8f,
                new RectOffset(8, 8, 4, 4), false);
            hlg.childAlignment = TextAnchor.MiddleCenter;

            _slots = new SkillSlot[GameConfig.HotbarSlots];
            _keyLabels = new Text[GameConfig.HotbarSlots];
            _nameLabels = new Text[GameConfig.HotbarSlots];

            for (int i = 0; i < GameConfig.HotbarSlots; i++)
            {
                // Create each skill slot using UIHelper.CreateItemSlot
                var (slotRoot, slotBg, slotIcon, slotQty, slotBorder) =
                    UIHelper.CreateItemSlot(containerRt, $"SkillSlot_{i}", 60f);

                // Set layout element so HorizontalLayoutGroup sizes it correctly
                UIHelper.SetPreferredSize(slotRoot.gameObject, 60f, 80f);

                // Keybind label — top-left of the slot
                var keyLabel = UIHelper.CreateSizedText(
                    slotRoot, "KeyLabel", (i + 1).ToString(),
                    12, UIHelper.COLOR_TEXT_GOLD,
                    new Vector2(20, 16), Vector2.zero,
                    TextAnchor.UpperLeft);
                var keyRt = keyLabel.rectTransform;
                keyRt.anchorMin = new Vector2(0f, 1f);
                keyRt.anchorMax = new Vector2(0f, 1f);
                keyRt.pivot = new Vector2(0f, 1f);
                keyRt.anchoredPosition = new Vector2(2, -2);
                _keyLabels[i] = keyLabel;

                // Cooldown overlay — filled image covering the slot
                var cooldownImg = UIHelper.CreateFilledImage(slotRoot, "CooldownOverlay",
                    UIHelper.COLOR_COOLDOWN);
                cooldownImg.fillAmount = 0f;
                cooldownImg.raycastTarget = false;

                // Skill name label — below the slot
                var nameLabel = UIHelper.CreateSizedText(
                    slotRoot, "SkillName", "",
                    10, UIHelper.COLOR_TEXT_SECONDARY,
                    new Vector2(60, 14), Vector2.zero,
                    TextAnchor.UpperCenter);
                var nameRt = nameLabel.rectTransform;
                nameRt.anchorMin = new Vector2(0.5f, 0f);
                nameRt.anchorMax = new Vector2(0.5f, 0f);
                nameRt.pivot = new Vector2(0.5f, 1f);
                nameRt.anchoredPosition = new Vector2(0, -2);
                _nameLabels[i] = nameLabel;

                // Build the SkillSlot data
                _slots[i] = new SkillSlot
                {
                    IconImage = slotIcon,
                    CooldownOverlay = cooldownImg,
                    KeyLabel = null,        // TMP field — not used in code-built UI
                    SkillNameLabel = null    // TMP field — not used in code-built UI
                };
            }
        }
    }
}
