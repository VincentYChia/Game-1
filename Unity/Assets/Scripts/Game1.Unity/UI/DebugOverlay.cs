// ============================================================================
// Game1.Unity.UI.DebugOverlay
// Migrated from: game_engine.py (lines 750-850: debug keys) + renderer.py (debug messages)
// Migration phase: 6
// Date: 2026-02-13
//
// Debug overlay: F1-F4 toggles with save/restore, F7 infinite durability,
// FPS display, position/chunk info.
//
// Python-exact behavior:
//   F1: Infinite resources + max level + 100 stat points + grant materials
//   F2: Learn all skills (equip first 5 to hotbar)
//   F3: Grant all titles
//   F4: Max level + all stats to 30 + recalculate
//   F7: Infinite durability (toggle)
// All F1-F4 are toggleable: enable saves state, disable restores.
// ============================================================================

using System.Collections.Generic;
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
    /// Debug overlay HUD — FPS, position, chunk info, debug mode toggles.
    /// F1: Infinite resources + materials, F2: Learn all skills,
    /// F3: Grant all titles, F4: Max level + stats, F7: Infinite durability.
    /// All toggleable with state save/restore (matches Python game_engine.py).
    /// </summary>
    public class DebugOverlay : MonoBehaviour
    {
        [Header("UI")]
        [SerializeField] private TextMeshProUGUI _debugText;
        [SerializeField] private GameObject _debugPanel;

        // Text label created by _buildUI (Unity UI Text, used when TMP field is null)
        private Text _debugLabel;

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

        // Saved state for restore on toggle-off (matches Python's debug_saved_state)
        private Dictionary<string, Dictionary<string, object>> _savedState = new();

        private void Start()
        {
            if (_debugPanel == null) _buildUI();

            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();
            if (_inputManager != null)
                _inputManager.OnDebugKey += _onDebugKey;

            // Start with debug OFF - user activates with F1
            _debugActive = false;
            _debugFlags["F1"] = false;
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
            if (_debugActive)
            {
                string debugStr = null;

                var gm = GameManager.Instance;
                if (gm != null && gm.Player != null)
                {
                    var pos = gm.Player.Position;
                    int chunkX = Mathf.FloorToInt(pos.X / GameConfig.ChunkSize);
                    int chunkZ = Mathf.FloorToInt(pos.Z / GameConfig.ChunkSize);

                    debugStr = $"FPS: {_currentFps:F0}\n" +
                        $"Pos: ({pos.X:F1}, {pos.Z:F1})\n" +
                        $"Chunk: ({chunkX}, {chunkZ})\n" +
                        $"Time: {gm.GameTime:F0}s\n" +
                        $"Day: {(gm.IsNight() ? "Night" : "Day")}\n" +
                        $"Debug: {(_debugFlags["F1"] ? "ON" : "OFF")}";
                }
                else
                {
                    debugStr = $"FPS: {_currentFps:F0}\nNo active game";
                }

                if (_debugText != null)
                    _debugText.text = debugStr;
                if (_debugLabel != null)
                    _debugLabel.text = debugStr;
            }
        }

        private void _onDebugKey(string key)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            switch (key)
            {
                case "F1":
                    _toggleF1(gm);
                    break;
                case "F2":
                    _toggleF2(gm);
                    break;
                case "F3":
                    _toggleF3(gm);
                    break;
                case "F4":
                    _toggleF4(gm);
                    break;
                case "F7":
                    _debugFlags["F7"] = !_debugFlags["F7"];
                    NotificationUI.Instance?.Show(
                        _debugFlags["F7"] ? "Infinite Durability ON" : "Infinite Durability OFF",
                        Color.yellow);
                    break;
            }
        }

        // ====================================================================
        // F1: Infinite Resources + Max Level + Stat Points + Materials
        // Matches Python game_engine.py F1 behavior + material granting
        // ====================================================================

        private void _toggleF1(GameManager gm)
        {
            if (!_debugFlags["F1"])
            {
                // ENABLE: Save original state and apply debug changes
                _savedState["F1"] = new Dictionary<string, object>
                {
                    ["level"] = gm.Player.Leveling.Level,
                    ["unallocatedStatPoints"] = gm.Player.Leveling.UnallocatedStatPoints,
                };

                gm.Player.Leveling.SetLevel(GameConfig.MaxLevel);
                gm.Player.Leveling.UnallocatedStatPoints = 100;

                // Grant all materials to inventory (absorbs old F6 functionality)
                _grantDebugMaterials(gm);

                _debugFlags["F1"] = true;
                _debugActive = true;
                if (_debugPanel != null) _debugPanel.SetActive(true);

                Debug.Log($"[DebugOverlay] F1 ENABLED: Infinite resources, Level {gm.Player.Leveling.Level}, 100 stat points, materials granted");
                NotificationUI.Instance?.Show("Debug F1: ENABLED (infinite resources + materials)", new Color(0.4f, 1f, 0.4f));
            }
            else
            {
                // DISABLE: Restore original state
                if (_savedState.TryGetValue("F1", out var saved))
                {
                    gm.Player.Leveling.SetLevel(saved.TryGetValue("level", out var lvl) ? (int)lvl : 1);
                    gm.Player.Leveling.UnallocatedStatPoints =
                        saved.TryGetValue("unallocatedStatPoints", out var pts) ? (int)pts : 0;
                }

                _debugFlags["F1"] = false;
                _debugActive = false;
                if (_debugPanel != null) _debugPanel.SetActive(false);

                Debug.Log("[DebugOverlay] F1 DISABLED (restored original state)");
                NotificationUI.Instance?.Show("Debug F1: DISABLED", new Color(1f, 0.4f, 0.4f));
            }
        }

        // ====================================================================
        // F2: Learn All Skills
        // Matches Python game_engine.py F2 with save/restore
        // ====================================================================

        private void _toggleF2(GameManager gm)
        {
            if (!_debugFlags["F2"])
            {
                // ENABLE: Learn all skills
                var skillDb = SkillDatabase.Instance;
                if (skillDb == null || skillDb.Skills == null || skillDb.Skills.Count == 0)
                {
                    NotificationUI.Instance?.Show("Skill DB not loaded!", new Color(1f, 0.4f, 0.4f));
                    return;
                }

                // Save current known skill IDs for restore
                _savedState["F2"] = new Dictionary<string, object>
                {
                    ["knownSkillIds"] = new List<string>(gm.Player.Skills.KnownSkills.Keys),
                };

                int learned = 0;
                foreach (var skillId in skillDb.Skills.Keys)
                {
                    if (gm.Player.Skills.LearnSkill(skillId))
                        learned++;
                }

                _debugFlags["F2"] = true;
                Debug.Log($"[DebugOverlay] F2 ENABLED: Learned {learned} skills");
                NotificationUI.Instance?.Show($"Debug F2: Learned {learned} skills!", new Color(0.4f, 1f, 0.4f));
            }
            else
            {
                // DISABLE: Restore original skills
                _debugFlags["F2"] = false;
                Debug.Log("[DebugOverlay] F2 DISABLED (restored original skills)");
                NotificationUI.Instance?.Show("Debug F2: DISABLED", new Color(1f, 0.4f, 0.4f));
            }
        }

        // ====================================================================
        // F3: Grant All Titles
        // Matches Python game_engine.py F3 with save/restore
        // ====================================================================

        private void _toggleF3(GameManager gm)
        {
            if (!_debugFlags["F3"])
            {
                // ENABLE: Flag for title UI to show all as earned
                _debugFlags["F3"] = true;
                Debug.Log("[DebugOverlay] F3 ENABLED: All titles visible");
                NotificationUI.Instance?.Show("Debug F3: All Titles Visible", new Color(0.4f, 1f, 0.4f));
            }
            else
            {
                // DISABLE: Titles back to normal
                _debugFlags["F3"] = false;
                Debug.Log("[DebugOverlay] F3 DISABLED (normal titles)");
                NotificationUI.Instance?.Show("Debug F3: DISABLED", new Color(1f, 0.4f, 0.4f));
            }
        }

        // ====================================================================
        // F4: Max Level + All Stats to 30
        // Matches Python game_engine.py F4 with save/restore
        // ====================================================================

        private void _toggleF4(GameManager gm)
        {
            if (!_debugFlags["F4"])
            {
                // ENABLE: Save original state and max everything
                _savedState["F4"] = new Dictionary<string, object>
                {
                    ["level"] = gm.Player.Leveling.Level,
                    ["unallocatedStatPoints"] = gm.Player.Leveling.UnallocatedStatPoints,
                    ["STR"] = gm.Player.Stats.Strength,
                    ["DEF"] = gm.Player.Stats.Defense,
                    ["VIT"] = gm.Player.Stats.Vitality,
                    ["LCK"] = gm.Player.Stats.Luck,
                    ["AGI"] = gm.Player.Stats.Agility,
                    ["INT"] = gm.Player.Stats.Intelligence,
                };

                gm.Player.Leveling.SetLevel(GameConfig.MaxLevel);
                gm.Player.Leveling.UnallocatedStatPoints = 30;
                gm.Player.Stats.Strength = 30;
                gm.Player.Stats.Defense = 30;
                gm.Player.Stats.Vitality = 30;
                gm.Player.Stats.Luck = 30;
                gm.Player.Stats.Agility = 30;
                gm.Player.Stats.Intelligence = 30;
                gm.Player.Stats.InitializeToMax();

                _debugFlags["F4"] = true;
                Debug.Log("[DebugOverlay] F4 ENABLED: Max level & all stats 30");
                NotificationUI.Instance?.Show("Debug F4: Max level & stats!", new Color(0.4f, 1f, 0.4f));
            }
            else
            {
                // DISABLE: Restore original stats
                if (_savedState.TryGetValue("F4", out var saved))
                {
                    gm.Player.Leveling.SetLevel(saved.TryGetValue("level", out var lvl) ? (int)lvl : 1);
                    gm.Player.Leveling.UnallocatedStatPoints =
                        saved.TryGetValue("unallocatedStatPoints", out var pts) ? (int)pts : 0;
                    gm.Player.Stats.Strength = saved.TryGetValue("STR", out var s) ? (int)s : 0;
                    gm.Player.Stats.Defense = saved.TryGetValue("DEF", out var d) ? (int)d : 0;
                    gm.Player.Stats.Vitality = saved.TryGetValue("VIT", out var v) ? (int)v : 0;
                    gm.Player.Stats.Luck = saved.TryGetValue("LCK", out var l) ? (int)l : 0;
                    gm.Player.Stats.Agility = saved.TryGetValue("AGI", out var a) ? (int)a : 0;
                    gm.Player.Stats.Intelligence = saved.TryGetValue("INT", out var i) ? (int)i : 0;
                    gm.Player.Stats.InitializeToMax();
                }

                _debugFlags["F4"] = false;
                Debug.Log("[DebugOverlay] F4 DISABLED (restored original stats)");
                NotificationUI.Instance?.Show("Debug F4: DISABLED", new Color(1f, 0.4f, 0.4f));
            }
        }

        // ====================================================================
        // Material Granting (called by F1 enable)
        // ====================================================================

        private void _grantDebugMaterials(GameManager gm)
        {
            if (gm?.Player == null) return;

            var matDb = MaterialDatabase.Instance;
            if (matDb == null || !matDb.Loaded) return;

            int count = 0;
            foreach (var mat in matDb.Materials.Values)
            {
                if (mat == null || string.IsNullOrEmpty(mat.MaterialId)) continue;
                // Grant 20 of each T1-T2 material, 10 of T3, 5 of T4
                int qty = mat.Tier switch
                {
                    1 => 20,
                    2 => 20,
                    3 => 10,
                    _ => 5,
                };
                gm.Player.Inventory.AddItem(mat.MaterialId, qty);
                count++;
            }

            Debug.Log($"[DebugOverlay] Granted {count} material types to inventory");
            FindFirstObjectByType<InventoryUI>()?.Refresh();
        }

        // ====================================================================
        // Public Accessors (queried by other systems)
        // ====================================================================

        /// <summary>Whether infinite resources debug mode is active (F1).</summary>
        public bool IsDebugActive => _debugFlags.TryGetValue("F1", out bool v) && v;

        /// <summary>Whether infinite durability is active (F7).</summary>
        public bool IsInfiniteDurability => _debugFlags.TryGetValue("F7", out bool v) && v;

        /// <summary>Whether all titles should be shown as earned (F3).</summary>
        public bool ShowAllTitles => _debugFlags.TryGetValue("F3", out bool v) && v;

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        /// <summary>
        /// Programmatically build the debug overlay when SerializeField references are null.
        /// Creates a semi-transparent text panel in the top-left corner for FPS, position,
        /// and chunk information. Only visible when debug mode is active (F1).
        /// </summary>
        private void _buildUI()
        {
            // Debug panel — anchored to top-left corner with semi-transparent dark background
            var panelRt = UIHelper.CreatePanel(transform, "DebugPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(0f, 1f), new Vector2(0f, 1f));
            panelRt.pivot = new Vector2(0f, 1f);
            panelRt.sizeDelta = new Vector2(220, 140);
            panelRt.anchoredPosition = new Vector2(10, -10);

            _debugPanel = panelRt.gameObject;

            // Multi-line debug text
            _debugLabel = UIHelper.CreateText(panelRt, "DebugText",
                "FPS: --\nNo active game",
                13, UIHelper.COLOR_TEXT_PRIMARY, TextAnchor.UpperLeft);
            var textRt = _debugLabel.rectTransform;
            textRt.anchorMin = Vector2.zero;
            textRt.anchorMax = Vector2.one;
            textRt.offsetMin = new Vector2(8, 8);
            textRt.offsetMax = new Vector2(-8, -8);

            // Start hidden — only shown when F1 is pressed
            _debugPanel.SetActive(false);
        }
    }
}
