// ============================================================================
// Game1.Unity.UI.AlchemyMinigameUI
// Migrated from: Crafting-subdisciplines/alchemy.py (1,052 lines)
// Migration phase: 6
// Date: 2026-02-13
//
// Alchemy minigame: reaction chain stabilization.
// Player manages reaction stages, keeping stability in green zone.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using Game1.Unity.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Alchemy minigame — reaction chain stabilization.
    /// Keep the reaction stability within the green zone across stages.
    /// </summary>
    public class AlchemyMinigameUI : MinigameUI
    {
        [Header("Alchemy-Specific")]
        [SerializeField] private Image _stabilityBar;
        [SerializeField] private Image _sweetSpot;
        [SerializeField] private TextMeshProUGUI _stageText;
        [SerializeField] private Image[] _stageIndicators;

        private float _stability;
        private float _driftSpeed = 0.3f;
        private float _driftDirection = 1f;
        private int _currentStage;
        private int _totalStages = 5;
        private int _stagesCompleted;
        private float _stageTimer;
        private float _stageInterval = 3f;

        // Fallback text references (programmatic UI)
        private Text _stageTextFallback;
        private Text _ingredientListText;

        // Programmatic UI references
        private Image _reactionBubble;
        private Button _chainButton;
        private Button _stabilizeButton;

        // ====================================================================
        // Programmatic UI Construction
        // ====================================================================

        /// <summary>
        /// Build alchemy-specific UI: reaction bubble (center), stability gauge,
        /// ingredient list (left), chain/stabilize buttons.
        /// </summary>
        protected override void _buildUI()
        {
            base._buildUI();
            var parent = _contentArea != null ? _contentArea : _panel.transform;

            // --- Ingredient list (left side) ---
            var ingredientPanelRt = UIHelper.CreatePanel(parent, "IngredientPanel",
                new Color(0.10f, 0.12f, 0.16f, 1f),
                new Vector2(0.02f, 0.10f), new Vector2(0.22f, 0.90f));
            UIHelper.AddVerticalLayout(ingredientPanelRt, 4f, new RectOffset(6, 6, 8, 8));

            var ingredientHeader = UIHelper.CreateText(ingredientPanelRt, "IngredientHeader",
                "Ingredients", 14, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(ingredientHeader.gameObject, 24f);

            UIHelper.CreateDivider(ingredientPanelRt, 1f);

            _ingredientListText = UIHelper.CreateText(ingredientPanelRt, "IngredientList",
                "- Ingredient 1\n- Ingredient 2\n- Ingredient 3",
                12, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.UpperLeft);
            var ingredientLE = _ingredientListText.gameObject.AddComponent<LayoutElement>();
            ingredientLE.flexibleHeight = 1f;

            // --- Reaction bubble (circular image, center) ---
            var bubbleContainerRt = UIHelper.CreatePanel(parent, "BubbleContainer",
                UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.30f, 0.25f), new Vector2(0.70f, 0.75f));

            // Circular reaction bubble background
            _reactionBubble = UIHelper.CreateImage(bubbleContainerRt, "ReactionBubble",
                new Color(0.15f, 0.30f, 0.15f, 0.8f));
            var bubbleRt = _reactionBubble.rectTransform;
            UIHelper.StretchFill(bubbleRt);

            // Inner glow / reaction indicator
            var innerGlow = UIHelper.CreateImage(bubbleContainerRt, "InnerGlow",
                new Color(0.2f, 0.6f, 0.2f, 0.3f));
            var innerGlowRt = innerGlow.rectTransform;
            innerGlowRt.anchorMin = new Vector2(0.15f, 0.15f);
            innerGlowRt.anchorMax = new Vector2(0.85f, 0.85f);
            innerGlowRt.offsetMin = Vector2.zero;
            innerGlowRt.offsetMax = Vector2.zero;

            // Stage text on the bubble
            _stageTextFallback = UIHelper.CreateText(bubbleContainerRt, "StageText",
                "Stage 1/5", 20, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.MiddleCenter);

            // --- Stability gauge (below the reaction bubble) ---
            var stabilityContainerRt = UIHelper.CreatePanel(parent, "StabilityContainer",
                new Color(0.10f, 0.10f, 0.15f, 1f),
                new Vector2(0.25f, 0.10f), new Vector2(0.75f, 0.20f));

            // Stability label
            var stabilityLabel = UIHelper.CreateText(stabilityContainerRt, "StabilityLabel",
                "Stability", 13, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
            var stabilityLabelRt = stabilityLabel.rectTransform;
            stabilityLabelRt.anchorMin = new Vector2(0f, 0.7f);
            stabilityLabelRt.anchorMax = new Vector2(1f, 1f);
            stabilityLabelRt.offsetMin = Vector2.zero;
            stabilityLabelRt.offsetMax = Vector2.zero;

            // Stability bar background
            var stabilityBarBg = UIHelper.CreateImage(stabilityContainerRt, "StabilityBarBg",
                new Color(0.18f, 0.18f, 0.25f, 1f));
            var stabilityBarBgRt = stabilityBarBg.rectTransform;
            stabilityBarBgRt.anchorMin = new Vector2(0.05f, 0.1f);
            stabilityBarBgRt.anchorMax = new Vector2(0.95f, 0.65f);
            stabilityBarBgRt.offsetMin = Vector2.zero;
            stabilityBarBgRt.offsetMax = Vector2.zero;

            // Sweet spot (green zone indicator in the middle)
            _sweetSpot = UIHelper.CreateImage(stabilityBarBg.rectTransform, "SweetSpot",
                new Color(0f, 0.7f, 0f, 0.25f));
            var sweetSpotRt = _sweetSpot.rectTransform;
            sweetSpotRt.anchorMin = new Vector2(0.35f, 0f);
            sweetSpotRt.anchorMax = new Vector2(0.65f, 1f);
            sweetSpotRt.offsetMin = Vector2.zero;
            sweetSpotRt.offsetMax = Vector2.zero;

            // Stability fill bar
            _stabilityBar = UIHelper.CreateFilledImage(stabilityBarBg.rectTransform,
                "StabilityBarFill", new Color(0f, 0.8f, 0f, 1f));
            var stabilityFillRt = _stabilityBar.rectTransform;
            stabilityFillRt.anchorMin = Vector2.zero;
            stabilityFillRt.anchorMax = Vector2.one;
            stabilityFillRt.offsetMin = new Vector2(2, 2);
            stabilityFillRt.offsetMax = new Vector2(-2, -2);

            // --- Stage indicators (small dots above stability bar) ---
            var stageIndicatorRt = UIHelper.CreatePanel(parent, "StageIndicators",
                UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.35f, 0.21f), new Vector2(0.65f, 0.25f));
            UIHelper.AddHorizontalLayout(stageIndicatorRt, 6f,
                new RectOffset(4, 4, 2, 2), true);

            _stageIndicators = new Image[_totalStages];
            for (int i = 0; i < _totalStages; i++)
            {
                _stageIndicators[i] = UIHelper.CreateImage(stageIndicatorRt, $"Stage_{i}",
                    new Color(0.3f, 0.3f, 0.3f, 1f));
            }

            // --- Chain and Stabilize buttons (right side) ---
            var buttonPanelRt = UIHelper.CreatePanel(parent, "ButtonPanel",
                UIHelper.COLOR_TRANSPARENT,
                new Vector2(0.76f, 0.25f), new Vector2(0.96f, 0.65f));
            UIHelper.AddVerticalLayout(buttonPanelRt, 10f, new RectOffset(4, 4, 8, 8));

            _chainButton = UIHelper.CreateButton(buttonPanelRt, "ChainButton", "Chain",
                new Color(0.6f, 0.4f, 0.1f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 14);
            UIHelper.SetPreferredHeight(_chainButton.gameObject, 45f);
            _chainButton.onClick.AddListener(() =>
            {
                // Chain: risky push toward faster reaction
                _driftSpeed += 0.1f;
                _stageInterval = Mathf.Max(1.5f, _stageInterval - 0.3f);
            });

            _stabilizeButton = UIHelper.CreateButton(buttonPanelRt, "StabilizeButton", "Stabilize",
                new Color(0.1f, 0.5f, 0.3f, 1f), UIHelper.COLOR_TEXT_PRIMARY, 14);
            UIHelper.SetPreferredHeight(_stabilizeButton.gameObject, 45f);
            _stabilizeButton.onClick.AddListener(() =>
            {
                // Stabilize: push stability toward center
                if (_stability < 0.5f) _stability += 0.1f;
                else _stability -= 0.1f;
            });
        }

        // ====================================================================
        // Minigame Logic
        // ====================================================================

        protected override void OnStart()
        {
            _stability = 0.5f;
            _currentStage = 0;
            _stagesCompleted = 0;
            _stageTimer = 0f;
            _driftDirection = 1f;

            // Reset stage indicators
            if (_stageIndicators != null)
            {
                for (int i = 0; i < _stageIndicators.Length; i++)
                {
                    if (_stageIndicators[i] != null)
                        _stageIndicators[i].color = new Color(0.3f, 0.3f, 0.3f, 1f);
                }
            }
        }

        protected override void OnUpdate(float deltaTime)
        {
            // Stability drifts randomly
            _stability += _driftDirection * _driftSpeed * deltaTime;

            // Random drift changes
            if (Random.value < 0.02f)
                _driftDirection = -_driftDirection;

            _stability = Mathf.Clamp01(_stability);

            // Update stability bar
            if (_stabilityBar != null)
            {
                _stabilityBar.fillAmount = _stability;
                bool inZone = _stability >= 0.35f && _stability <= 0.65f;
                _stabilityBar.color = inZone
                    ? new Color(0f, 0.8f, 0f)
                    : new Color(0.8f, 0f, 0f);
            }

            // Update reaction bubble color based on stability
            if (_reactionBubble != null)
            {
                bool inZone = _stability >= 0.35f && _stability <= 0.65f;
                _reactionBubble.color = inZone
                    ? new Color(0.15f, 0.35f, 0.15f, 0.8f)
                    : new Color(0.35f, 0.15f, 0.15f, 0.8f);
            }

            // Stage progression
            _stageTimer += deltaTime;
            if (_stageTimer >= _stageInterval)
            {
                _stageTimer = 0f;
                bool wasStable = _stability >= 0.35f && _stability <= 0.65f;

                // Update stage indicator
                if (_stageIndicators != null && _currentStage < _stageIndicators.Length
                    && _stageIndicators[_currentStage] != null)
                {
                    _stageIndicators[_currentStage].color = wasStable
                        ? UIHelper.COLOR_TEXT_GREEN
                        : UIHelper.COLOR_TEXT_RED;
                }

                if (wasStable) _stagesCompleted++;
                _currentStage++;

                if (_currentStage >= _totalStages)
                {
                    Complete((float)_stagesCompleted / _totalStages);
                    return;
                }

                // Increase difficulty each stage
                _driftSpeed += 0.05f;
            }

            _setStageText($"Stage {_currentStage + 1}/{_totalStages}");

            _performance = (float)_stagesCompleted / Mathf.Max(_currentStage, 1);
        }

        protected override void OnCraftAction()
        {
            // Stabilize: push stability toward center
            if (_stability < 0.5f) _stability += 0.1f;
            else _stability -= 0.1f;

            ParticleEffects.Instance?.PlayBubbles(Vector3.zero, 10);
        }

        private void _setStageText(string text)
        {
            if (_stageText != null) _stageText.text = text;
            else if (_stageTextFallback != null) _stageTextFallback.text = text;
        }
    }
}
