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
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Skill hotbar UI — 5 slots with skill icons, cooldown overlays, and key labels.
    /// </summary>
    public class SkillBarUI : MonoBehaviour
    {
        [Header("Slot References")]
        [SerializeField] private SkillSlot[] _slots = new SkillSlot[GameConfig.HotbarSlots];

        [Header("Colors")]
        [SerializeField] private Color _readyColor = Color.white;
        [SerializeField] private Color _cooldownColor = new Color(0.3f, 0.3f, 0.3f, 0.8f);
        [SerializeField] private Color _noManaColor = new Color(0.2f, 0.2f, 0.5f, 0.8f);

        private InputManager _inputManager;

        [System.Serializable]
        public class SkillSlot
        {
            public Image IconImage;
            public Image CooldownOverlay;
            public TextMeshProUGUI KeyLabel;
            public TextMeshProUGUI SkillNameLabel;
        }

        private void Start()
        {
            _inputManager = FindFirstObjectByType<InputManager>();
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
            if (gm == null || gm.Player == null) return;

            var skillManager = gm.Player.Skills;

            for (int i = 0; i < _slots.Length; i++)
            {
                if (_slots[i] == null) continue;

                string skillId = skillManager.GetHotbarSkillId(i);

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
                    continue;
                }

                // Has skill in slot
                if (_slots[i].IconImage != null)
                {
                    _slots[i].IconImage.enabled = true;
                    if (SpriteDatabase.Instance != null)
                        _slots[i].IconImage.sprite = SpriteDatabase.Instance.GetItemSprite(skillId);
                }

                // Cooldown overlay
                if (_slots[i].CooldownOverlay != null)
                {
                    float cooldownRemaining = skillManager.GetCooldownRemaining(skillId);
                    float cooldownTotal = skillManager.GetCooldownTotal(skillId);

                    if (cooldownRemaining > 0 && cooldownTotal > 0)
                    {
                        _slots[i].CooldownOverlay.fillAmount = cooldownRemaining / cooldownTotal;
                        _slots[i].CooldownOverlay.color = _cooldownColor;
                    }
                    else
                    {
                        _slots[i].CooldownOverlay.fillAmount = 0f;
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
                string skillId = gm.Player.Skills.GetHotbarSkillId(slotIndex);
                if (!string.IsNullOrEmpty(skillId))
                {
                    gm.Player.Skills.ActivateSkill(skillId);
                }
            }
        }
    }
}
