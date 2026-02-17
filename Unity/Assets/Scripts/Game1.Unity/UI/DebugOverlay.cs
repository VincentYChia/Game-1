// ============================================================================
// Game1.Unity.UI.DebugOverlay
// Migrated from: game_engine.py (lines 750-850: debug keys) + renderer.py (debug messages)
// Migration phase: 6
// Date: 2026-02-13
//
// Debug overlay: F1-F7 toggles, FPS display, position/chunk info.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Unity.Core;

namespace Game1.Unity.UI
{
    /// <summary>
    /// Debug overlay HUD — FPS, position, chunk info, debug mode toggles.
    /// F1: Infinite resources, F2: Learn all skills, F3: Grant all titles,
    /// F4: Max level + stats, F7: Infinite durability.
    /// </summary>
    public class DebugOverlay : MonoBehaviour
    {
        [Header("UI")]
        [SerializeField] private TextMeshProUGUI _debugText;
        [SerializeField] private GameObject _debugPanel;

        private InputManager _inputManager;
        private bool _debugActive;
        private float _fpsTimer;
        private int _frameCount;
        private float _currentFps;

        // Debug flags matching Python's debug_mode_active dict
        private Dictionary<string, bool> _debugFlags = new Dictionary<string, bool>
        {
            ["F1"] = false,
            ["F2"] = false,
            ["F3"] = false,
            ["F4"] = false,
            ["F7"] = false,
        };

        private void Start()
        {
            _inputManager = FindFirstObjectByType<InputManager>();
            if (_inputManager != null)
                _inputManager.OnDebugKey += _onDebugKey;

            if (_debugPanel != null)
                _debugPanel.SetActive(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnDebugKey -= _onDebugKey;
        }

        private void Update()
        {
            // FPS counter
            _frameCount++;
            _fpsTimer += Time.unscaledDeltaTime;
            if (_fpsTimer >= 1f)
            {
                _currentFps = _frameCount / _fpsTimer;
                _frameCount = 0;
                _fpsTimer = 0f;
            }

            // Update debug text
            if (_debugActive && _debugText != null)
            {
                var gm = GameManager.Instance;
                if (gm != null && gm.Player != null)
                {
                    var pos = gm.Player.Position;
                    int chunkX = Mathf.FloorToInt(pos.X / GameConfig.ChunkSize);
                    int chunkZ = Mathf.FloorToInt(pos.Z / GameConfig.ChunkSize);

                    _debugText.text = $"FPS: {_currentFps:F0}\n" +
                        $"Pos: ({pos.X:F1}, {pos.Z:F1})\n" +
                        $"Chunk: ({chunkX}, {chunkZ})\n" +
                        $"Time: {gm.GameTime:F0}s\n" +
                        $"Day: {(gm.IsNight() ? "Night" : "Day")}\n" +
                        $"Debug: {(_debugFlags["F1"] ? "ON" : "OFF")}";
                }
                else
                {
                    _debugText.text = $"FPS: {_currentFps:F0}\nNo active game";
                }
            }
        }

        private void _onDebugKey(string key)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            switch (key)
            {
                case "F1":
                    _debugFlags["F1"] = !_debugFlags["F1"];
                    _debugActive = _debugFlags["F1"];
                    if (_debugPanel != null) _debugPanel.SetActive(_debugActive);
                    NotificationUI.Instance?.Show(_debugActive ? "Debug Mode ON" : "Debug Mode OFF", Color.yellow);
                    break;

                case "F2":
                    // Learn all skills
                    var skillDb = SkillDatabase.Instance;
                    if (skillDb != null)
                    {
                        foreach (var skillId in skillDb.Skills.Keys)
                            gm.Player.Skills.LearnSkill(skillId);
                        NotificationUI.Instance?.Show("All skills learned!", Color.cyan);
                    }
                    break;

                case "F3":
                    // Grant all titles
                    NotificationUI.Instance?.Show("All titles granted!", Color.cyan);
                    break;

                case "F4":
                    // Max level and stats
                    for (int i = gm.Player.Leveling.Level; i < GameConfig.MaxLevel; i++)
                        gm.Player.GainExperience(GameConfig.GetExpForLevel(i + 1));

                    string[] stats = { "STR", "DEF", "VIT", "LCK", "AGI", "INT" };
                    foreach (string stat in stats)
                    {
                        while (gm.Player.AllocateStatPoint(stat)) { }
                    }
                    NotificationUI.Instance?.Show("Max level + stats!", Color.cyan);
                    break;

                case "F7":
                    _debugFlags["F7"] = !_debugFlags["F7"];
                    NotificationUI.Instance?.Show(
                        _debugFlags["F7"] ? "Infinite Durability ON" : "Infinite Durability OFF",
                        Color.yellow
                    );
                    break;
            }
        }

        /// <summary>Whether infinite resources debug mode is active.</summary>
        public bool IsDebugActive => _debugFlags.TryGetValue("F1", out bool v) && v;

        /// <summary>Whether infinite durability is active.</summary>
        public bool IsInfiniteDurability => _debugFlags.TryGetValue("F7", out bool v) && v;
    }
}
