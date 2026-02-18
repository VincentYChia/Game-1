// ============================================================================
// Game1.Unity.World.DayNightOverlay
// Migrated from: rendering/renderer.py (lines 2037-2097: render_day_night_overlay)
// Migration phase: 6 (upgraded for 3D lighting)
// Date: 2026-02-18
//
// Day/night cycle controller that drives both a directional light (3D mode)
// and an optional screen overlay (2D fallback). Rotates the sun light through
// the sky, adjusts ambient color, and provides atmospheric tinting.
// ============================================================================

using UnityEngine;
using UnityEngine.UI;
using Game1.Unity.Core;

namespace Game1.Unity.World
{
    /// <summary>
    /// Day/night cycle controller. In 3D mode, rotates a directional light
    /// and adjusts ambient lighting. Also drives an optional screen overlay
    /// for atmospheric color tinting (preserved from 2D migration).
    /// </summary>
    public class DayNightOverlay : MonoBehaviour
    {
        // ====================================================================
        // Inspector Configuration
        // ====================================================================

        [Header("Rendering Mode")]
        [Tooltip("Use directional light for day/night. If false, uses screen overlay only.")]
        [SerializeField] private bool _use3DLighting = true;

        [Header("Screen Overlay (2D fallback / atmospheric tint)")]
        [SerializeField] private Image _overlayImage;

        [Header("Directional Light (3D mode)")]
        [Tooltip("The scene's directional light (sun). Created if null.")]
        [SerializeField] private Light _sunLight;

        [Header("Sun Colors")]
        [SerializeField] private Color _sunDawnColor = new Color(1f, 0.7f, 0.4f);
        [SerializeField] private Color _sunDayColor = new Color(1f, 0.96f, 0.92f);
        [SerializeField] private Color _sunDuskColor = new Color(1f, 0.5f, 0.2f);
        [SerializeField] private Color _sunNightColor = new Color(0.15f, 0.15f, 0.3f);

        [Header("Ambient Colors")]
        [SerializeField] private Color _ambientDawn = new Color(0.4f, 0.35f, 0.45f);
        [SerializeField] private Color _ambientDay = new Color(0.5f, 0.5f, 0.5f);
        [SerializeField] private Color _ambientDusk = new Color(0.35f, 0.25f, 0.35f);
        [SerializeField] private Color _ambientNight = new Color(0.08f, 0.08f, 0.15f);

        [Header("Sun Intensity")]
        [SerializeField] private float _sunDayIntensity = 1.2f;
        [SerializeField] private float _sunDawnIntensity = 0.6f;
        [SerializeField] private float _sunDuskIntensity = 0.5f;
        [SerializeField] private float _sunNightIntensity = 0.08f;

        [Header("Overlay Colors (atmospheric tint)")]
        [SerializeField] private Color _overlayDawnColor = new Color(1f, 0.85f, 0.7f, 0.1f);
        [SerializeField] private Color _overlayDayColor = new Color(1f, 1f, 1f, 0f);
        [SerializeField] private Color _overlayDuskColor = new Color(0.8f, 0.5f, 0.3f, 0.12f);
        [SerializeField] private Color _overlayNightColor = new Color(0.1f, 0.1f, 0.3f, 0.25f);

        // Phase boundaries (as fractions of full cycle)
        private const float DawnStart = 0f;
        private const float DayStart = 0.1f;
        private const float DuskStart = 0.55f;
        private const float NightStart = 0.67f;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Start()
        {
            if (_use3DLighting && _sunLight == null)
            {
                _createSunLight();
            }
        }

        private void _createSunLight()
        {
            var sunGO = new GameObject("Sun_DirectionalLight");
            sunGO.transform.SetParent(transform, false);
            _sunLight = sunGO.AddComponent<Light>();
            _sunLight.type = LightType.Directional;
            _sunLight.color = _sunDayColor;
            _sunLight.intensity = _sunDayIntensity;
            _sunLight.shadows = LightShadows.Soft;
            _sunLight.shadowStrength = 0.6f;
            _sunLight.shadowBias = 0.05f;
            _sunLight.shadowNormalBias = 0.4f;

            // Initial rotation: midday (sun high, slightly angled)
            sunGO.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
        }

        // ====================================================================
        // Update
        // ====================================================================

        private void Update()
        {
            var gm = GameManager.Instance;
            if (gm == null) return;

            float progress = gm.GetDayProgress();

            if (_use3DLighting && _sunLight != null)
            {
                _updateSunLight(progress);
                _updateAmbientLight(progress);
            }

            // Always update overlay if present (atmospheric tint layer)
            if (_overlayImage != null)
            {
                Color overlayColor = _getOverlayColor(progress);
                // In 3D mode, reduce overlay intensity since lighting handles most of it
                if (_use3DLighting)
                    overlayColor.a *= 0.5f;
                _overlayImage.color = overlayColor;
            }
        }

        // ====================================================================
        // 3D Sun Light
        // ====================================================================

        private void _updateSunLight(float progress)
        {
            // Sun rotation: from east (dawn) → overhead (noon) → west (dusk) → below (night)
            // progress 0.0 = dawn, 0.5 = dusk start, 0.67 = night, 1.0 = next dawn
            float sunAngle;

            if (progress < NightStart)
            {
                // Day arc: 0° (horizon east) → 90° (overhead) → 180° (horizon west)
                float dayProgress = progress / NightStart;
                sunAngle = dayProgress * 180f;
            }
            else
            {
                // Night arc: sun below horizon (180° → 360°)
                float nightProgress = (progress - NightStart) / (1f - NightStart);
                sunAngle = 180f + nightProgress * 180f;
            }

            // Apply rotation: X axis = sun altitude, Y axis = slight east-west offset
            _sunLight.transform.rotation = Quaternion.Euler(sunAngle - 90f, -30f, 0f);

            // Sun color and intensity
            Color sunColor;
            float intensity;

            if (progress < DayStart)
            {
                float t = progress / DayStart;
                sunColor = Color.Lerp(_sunDawnColor, _sunDayColor, t);
                intensity = Mathf.Lerp(_sunDawnIntensity, _sunDayIntensity, t);
            }
            else if (progress < DuskStart)
            {
                sunColor = _sunDayColor;
                intensity = _sunDayIntensity;
            }
            else if (progress < NightStart)
            {
                float t = (progress - DuskStart) / (NightStart - DuskStart);
                sunColor = Color.Lerp(_sunDuskColor, _sunNightColor, t);
                intensity = Mathf.Lerp(_sunDuskIntensity, _sunNightIntensity, t);
            }
            else if (progress < 0.95f)
            {
                sunColor = _sunNightColor;
                intensity = _sunNightIntensity;
            }
            else
            {
                float t = (progress - 0.95f) / 0.05f;
                sunColor = Color.Lerp(_sunNightColor, _sunDawnColor, t);
                intensity = Mathf.Lerp(_sunNightIntensity, _sunDawnIntensity, t);
            }

            _sunLight.color = sunColor;
            _sunLight.intensity = intensity;
        }

        private void _updateAmbientLight(float progress)
        {
            Color ambient;

            if (progress < DayStart)
            {
                float t = progress / DayStart;
                ambient = Color.Lerp(_ambientDawn, _ambientDay, t);
            }
            else if (progress < DuskStart)
            {
                ambient = _ambientDay;
            }
            else if (progress < NightStart)
            {
                float t = (progress - DuskStart) / (NightStart - DuskStart);
                ambient = Color.Lerp(_ambientDusk, _ambientNight, t);
            }
            else if (progress < 0.95f)
            {
                ambient = _ambientNight;
            }
            else
            {
                float t = (progress - 0.95f) / 0.05f;
                ambient = Color.Lerp(_ambientNight, _ambientDawn, t);
            }

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = ambient;
        }

        // ====================================================================
        // Overlay Colors (atmospheric tint)
        // ====================================================================

        private Color _getOverlayColor(float progress)
        {
            if (progress < DayStart)
            {
                float t = progress / DayStart;
                return Color.Lerp(_overlayDawnColor, _overlayDayColor, t);
            }
            else if (progress < DuskStart)
            {
                return _overlayDayColor;
            }
            else if (progress < NightStart)
            {
                float t = (progress - DuskStart) / (NightStart - DuskStart);
                return Color.Lerp(_overlayDuskColor, _overlayNightColor, t);
            }
            else if (progress < 0.95f)
            {
                return _overlayNightColor;
            }
            else
            {
                float t = (progress - 0.95f) / 0.05f;
                return Color.Lerp(_overlayNightColor, _overlayDawnColor, t);
            }
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Get the current sun light reference (for shadow adjustments, etc.).</summary>
        public Light SunLight => _sunLight;

        /// <summary>Toggle between 3D directional lighting and 2D overlay mode.</summary>
        public void Set3DLighting(bool enabled)
        {
            _use3DLighting = enabled;
            if (_sunLight != null)
                _sunLight.gameObject.SetActive(enabled);
        }
    }
}
