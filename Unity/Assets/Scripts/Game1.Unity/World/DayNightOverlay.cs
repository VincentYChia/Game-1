// ============================================================================
// Game1.Unity.World.DayNightOverlay
// Migrated from: rendering/renderer.py (lines 2037-2097: render_day_night_overlay)
// Migration phase: 6
// Date: 2026-02-13
//
// Time-of-day lighting overlay with alpha blending.
// Tints the screen based on the day/night cycle.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.Core;

namespace Game1.Unity.World
{
    /// <summary>
    /// Full-screen overlay that tints the game based on time of day.
    /// Dawn → Day → Dusk → Night cycle.
    /// </summary>
    public class DayNightOverlay : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private Image _overlayImage;

        [Header("Colors")]
        [SerializeField] private Color _dawnColor = new Color(1f, 0.85f, 0.7f, 0.15f);
        [SerializeField] private Color _dayColor = new Color(1f, 1f, 1f, 0f);
        [SerializeField] private Color _duskColor = new Color(0.8f, 0.5f, 0.3f, 0.2f);
        [SerializeField] private Color _nightColor = new Color(0.1f, 0.1f, 0.3f, 0.5f);

        // Phase boundaries (as fractions of full cycle)
        private const float DawnStart = 0f;       // 0% of cycle
        private const float DayStart = 0.1f;      // 10% of cycle
        private const float DuskStart = 0.55f;    // 55% of cycle
        private const float NightStart = 0.67f;   // 67% of cycle (DayLength/CycleLength)

        private void Update()
        {
            if (_overlayImage == null) return;

            var gm = GameManager.Instance;
            if (gm == null) return;

            float progress = gm.GetDayProgress();
            Color targetColor = _getColorForTime(progress);
            _overlayImage.color = targetColor;
        }

        private Color _getColorForTime(float progress)
        {
            if (progress < DayStart)
            {
                // Dawn → Day transition
                float t = progress / DayStart;
                return Color.Lerp(_dawnColor, _dayColor, t);
            }
            else if (progress < DuskStart)
            {
                // Full day
                return _dayColor;
            }
            else if (progress < NightStart)
            {
                // Dusk → Night transition
                float t = (progress - DuskStart) / (NightStart - DuskStart);
                return Color.Lerp(_duskColor, _nightColor, t);
            }
            else if (progress < 0.95f)
            {
                // Full night
                return _nightColor;
            }
            else
            {
                // Night → Dawn transition
                float t = (progress - 0.95f) / 0.05f;
                return Color.Lerp(_nightColor, _dawnColor, t);
            }
        }
    }
}
