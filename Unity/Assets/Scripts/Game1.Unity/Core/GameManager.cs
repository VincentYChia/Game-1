// ============================================================================
// Game1.Unity.Core.GameManager
// Migrated from: core/game_engine.py (lines 91-400: __init__)
// Migration phase: 6
// Date: 2026-02-13
//
// Bootstrap MonoBehaviour that initializes all game systems in correct order.
// Thin wrapper — all game logic lives in Phase 1-5 pure C# classes.
// ============================================================================

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using Game1.Core;
using Game1.Data.Databases;
using Game1.Data.Models;
using Game1.Entities;
using Game1.Systems.World;
using Game1.Systems.Combat;
using Game1.Systems.Crafting;
using Game1.Systems.Save;
using Game1.Systems.Classifiers;
using Game1.Unity.ML;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Main game manager — singleton MonoBehaviour that owns the game lifecycle.
    /// Initialization order mirrors Python game_engine.py __init__ (lines 91-400):
    ///   1. Paths → 2. Databases → 3. World → 4. Character → 5. Combat → 6. UI
    /// </summary>
    public class GameManager : MonoBehaviour
    {
        // ====================================================================
        // Singleton
        // ====================================================================

        public static GameManager Instance { get; private set; }

        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Scene References")]
        [SerializeField] private GameStateManager _stateManager;
        [SerializeField] private InputManager _inputManager;
        [SerializeField] private CameraController _cameraController;
        [SerializeField] private AudioManager _audioManager;

        [Header("Configuration")]
        [SerializeField] private GameConfigAsset _configAsset;

        // ====================================================================
        // Game State
        // ====================================================================

        /// <summary>Active player character (null until game starts).</summary>
        public Character Player { get; private set; }

        /// <summary>Active world system instance.</summary>
        public WorldSystem World { get; private set; }

        /// <summary>Current game time in seconds.</summary>
        public float GameTime { get; private set; }

        /// <summary>Whether all systems are initialized and ready.</summary>
        public bool IsInitialized { get; private set; }

        // Day/night cycle constants (from game_engine.py)
        public const float DayLength = 960f;    // 16 minutes
        public const float NightLength = 480f;   // 8 minutes
        public const float CycleLength = 1440f;  // 24 minutes total

        // ====================================================================
        // Combat & Crafting Systems
        // ====================================================================

        /// <summary>Active combat manager (null until game starts).</summary>
        public CombatManager CombatManager { get; private set; }

        private CombatConfig _combatConfig;
        private EnemySpawner _enemySpawner;
        private CharacterCombatAdapter _playerCombatAdapter;

        // ====================================================================
        // Initialization (mirrors game_engine.py __init__)
        // ====================================================================

        private void Awake()
        {
            // Singleton setup
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);

            // Step 1: Configure paths (must be before any database loads)
            string contentPath = Path.Combine(Application.streamingAssetsPath, "Content");
            GamePaths.SetBasePath(contentPath);
            GamePaths.SetSavePath(Path.Combine(Application.persistentDataPath, "Saves"));
            GamePaths.EnsureSaveDirectory();

            Debug.Log("[GameManager] Paths configured: " + contentPath);

            // Step 2: Load all databases (Phase 2 DatabaseInitializer)
            try
            {
                DatabaseInitializer.InitializeAll();
                Debug.Log("[GameManager] All databases loaded successfully");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[GameManager] Database initialization failed: {ex.Message}");
            }

            // Step 2b: Load enemy database (lives in Game1.Systems.Combat)
            try
            {
                EnemyDatabaseAdapter.Instance.LoadFromFile("Definitions.JSON/hostiles-1.JSON");
                Debug.Log($"[GameManager] Enemy database loaded: {EnemyDatabaseAdapter.Instance.EnemyCount} enemies");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[GameManager] Enemy database load failed (non-fatal): {ex.Message}");
            }

            // Step 3: Initialize ML classifier backend (Phase 5 → Phase 6 bridge)
            try
            {
                ClassifierManager.Instance.Initialize(new SentisBackendFactory());
                Debug.Log("[GameManager] Classifier backend initialized");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[GameManager] Classifier init failed (non-fatal): {ex.Message}");
            }

            // Step 4: Load combat configuration
            _combatConfig = new CombatConfig();
            string combatConfigPath = GamePaths.GetContentPath("Definitions.JSON/combat-config-1.JSON");
            if (File.Exists(combatConfigPath))
            {
                _combatConfig.LoadFromFile(combatConfigPath);
                Debug.Log("[GameManager] Combat config loaded");
            }
            else
            {
                Debug.LogWarning("[GameManager] Combat config not found, using defaults");
            }

            // Step 5: Apply target frame rate
            Application.targetFrameRate = GameConfig.FPS;
        }

        private void Start()
        {
            // Auto-discover scene references if not assigned in Inspector
            if (_stateManager == null)
                _stateManager = FindFirstObjectByType<GameStateManager>();
            if (_inputManager == null)
                _inputManager = FindFirstObjectByType<InputManager>();
            if (_cameraController == null)
                _cameraController = FindFirstObjectByType<CameraController>();
            if (_audioManager == null)
                _audioManager = FindFirstObjectByType<AudioManager>();

            // Systems are loaded in Awake; Start handles cross-references
            if (_stateManager != null)
            {
                _stateManager.TransitionTo(GameState.StartMenu);
            }

            IsInitialized = true;
            Debug.Log("[GameManager] Initialization complete");
        }

        // ====================================================================
        // Game Lifecycle
        // ====================================================================

        /// <summary>
        /// Start a new game with the given player name and class.
        /// Called from ClassSelectionUI after player picks a class.
        /// </summary>
        public void StartNewGame(string playerName, string classId, int worldSeed = -1)
        {
            // Create world
            int seed = worldSeed >= 0 ? worldSeed : UnityEngine.Random.Range(0, int.MaxValue);
            World = new WorldSystem(seed);
            Debug.Log($"[GameManager] World created with seed {seed}");

            // Create character at spawn
            var spawnPos = GamePosition.FromXZ(GameConfig.PlayerSpawnX, GameConfig.PlayerSpawnZ);
            Player = new Character(spawnPos);
            Player.Name = playerName;
            Player.SelectClass(classId);

            // Initialize combat system with adapter
            InitializeCombatSystem();

            GameTime = 0f;

            // Transition to gameplay
            _stateManager?.TransitionTo(GameState.Playing);

            Debug.Log($"[GameManager] New game started: {playerName} ({classId})");
        }

        /// <summary>
        /// Load a saved game from a save slot.
        /// </summary>
        public void LoadGame(string saveName)
        {
            try
            {
                var saveManager = new SaveManager();
                var saveData = saveManager.LoadFromFile(saveName);

                if (saveData == null)
                {
                    Debug.LogError($"[GameManager] Failed to load save: {saveName}");
                    return;
                }

                // Restore world from save data
                if (saveData.TryGetValue("world_seed", out object seedObj) && seedObj is long seedLong)
                {
                    World = new WorldSystem((int)seedLong);
                }
                else
                {
                    World = new WorldSystem(12345); // fallback seed
                }

                // Restore character
                if (saveData.TryGetValue("character", out object charObj)
                    && charObj is Dictionary<string, object> charData)
                {
                    float px = charData.TryGetValue("position_x", out object pxo) ? Convert.ToSingle(pxo) : 0f;
                    float pz = charData.TryGetValue("position_z", out object pzo) ? Convert.ToSingle(pzo) : 0f;
                    Player = new Character(GamePosition.FromXZ(px, pz));

                    if (charData.TryGetValue("name", out object nameObj))
                        Player.Name = nameObj.ToString();

                    if (charData.TryGetValue("class_id", out object clsObj) && !string.IsNullOrEmpty(clsObj?.ToString()))
                        Player.SelectClass(clsObj.ToString());
                }
                else
                {
                    Player = new Character(GamePosition.FromXZ(0, 0));
                }

                // Restore game time
                if (saveData.TryGetValue("game_time", out object timeObj))
                    GameTime = Convert.ToSingle(timeObj);

                // Initialize combat system with adapter
                InitializeCombatSystem();

                _stateManager?.TransitionTo(GameState.Playing);
                Debug.Log($"[GameManager] Game loaded: {saveName}");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[GameManager] Load failed: {ex.Message}");
            }
        }

        /// <summary>
        /// Save the current game to a save slot.
        /// </summary>
        public void SaveGame(string saveName)
        {
            if (Player == null || World == null)
            {
                Debug.LogWarning("[GameManager] Cannot save — no active game");
                return;
            }

            try
            {
                var saveManager = new SaveManager();
                var characterData = new Dictionary<string, object>
                {
                    ["name"] = Player.Name,
                    ["class_id"] = Player.ClassId,
                    ["position_x"] = Player.Position.X,
                    ["position_z"] = Player.Position.Z,
                    ["facing"] = Player.Facing,
                };

                var saveData = saveManager.CreateSaveData(
                    characterData, World, null, null, null, GameTime, null
                );

                saveManager.SaveToFile(saveName, saveData);
                Debug.Log($"[GameManager] Game saved: {saveName}");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[GameManager] Save failed: {ex.Message}");
            }
        }

        // ====================================================================
        // Game Loop (mirrors game_engine.py run/update)
        // ====================================================================

        private void Update()
        {
            if (!IsInitialized || Player == null) return;

            float dt = Time.deltaTime;

            // Only update game systems when in gameplay state
            if (_stateManager == null || _stateManager.CurrentState == GameState.Playing)
            {
                // Update game time (day/night cycle)
                GameTime += dt;

                // Update player character (cooldowns, buffs, knockback)
                Player.Update(dt);

                // Update world chunks around player
                World?.EnsureChunksLoaded(Player.Position.X, Player.Position.Z);

                // Update combat system
                if (CombatManager != null && _playerCombatAdapter != null)
                {
                    CombatManager.Update(dt, _playerCombatAdapter, false, IsNight());
                }

            }

            // Update crafting minigame (runs during MinigameActive state)
            if (_stateManager != null && _stateManager.CurrentState == GameState.MinigameActive)
            {
                if (InteractiveCrafting.Instance.IsActive)
                {
                    InteractiveCrafting.Instance.Update(dt);

                    if (InteractiveCrafting.Instance.IsFinished)
                    {
                        var result = InteractiveCrafting.Instance.GetResult();
                        if (result != null && result.Success)
                        {
                            Player?.Inventory.AddItem(result.OutputItemId, result.OutputQuantity);
                            GameEvents.RaiseItemCrafted(
                                InteractiveCrafting.Instance.CurrentDiscipline,
                                result.OutputItemId);
                        }

                        _stateManager.TransitionTo(GameState.Playing);
                    }
                }
            }
        }

        // ====================================================================
        // Combat System Initialization
        // ====================================================================

        /// <summary>
        /// Initialize the combat system with the current player character.
        /// Called from StartNewGame() and LoadGame().
        /// </summary>
        private void InitializeCombatSystem()
        {
            if (Player == null) return;

            try
            {
                _playerCombatAdapter = new CharacterCombatAdapter(Player);
                _enemySpawner = new EnemySpawner(_combatConfig, EnemyDatabaseAdapter.Instance);
                CombatManager = new CombatManager(_combatConfig, _enemySpawner);

                // Load chunk templates for enemy spawning
                string templatesPath = GamePaths.GetContentPath("Definitions.JSON/chunk-templates-1.JSON");
                if (File.Exists(templatesPath))
                {
                    _enemySpawner.LoadChunkTemplates(templatesPath);
                }

                Debug.Log("[GameManager] Combat system initialized");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[GameManager] Combat init failed (non-fatal): {ex.Message}");
                CombatManager = null;
            }
        }

        /// <summary>
        /// Get the enemy at a world position (for click-based combat).
        /// </summary>
        public ICombatEnemy GetEnemyAtPosition(float x, float z)
        {
            return CombatManager?.GetEnemyAtPosition(x, z);
        }

        /// <summary>
        /// Player attacks a specific enemy.
        /// </summary>
        public (float Damage, bool IsCritical) PlayerAttack(ICombatEnemy enemy, string hand = "mainHand")
        {
            if (CombatManager == null || _playerCombatAdapter == null || enemy == null)
                return (0, false);

            var result = CombatManager.PlayerAttackEnemy(enemy, _playerCombatAdapter, hand);
            return (result.Damage, result.IsCritical);
        }

        // ====================================================================
        // Day/Night Cycle Helpers
        // ====================================================================

        /// <summary>
        /// Get the current time-of-day phase (0 = midnight, 0.5 = noon).
        /// </summary>
        public float GetDayProgress()
        {
            return (GameTime % CycleLength) / CycleLength;
        }

        /// <summary>
        /// Whether it's currently night time.
        /// </summary>
        public bool IsNight()
        {
            float progress = GetDayProgress();
            float dayFraction = DayLength / CycleLength;
            return progress >= dayFraction;
        }

        // ====================================================================
        // Cleanup
        // ====================================================================

        private void OnDestroy()
        {
            if (Instance == this)
            {
                Instance = null;
            }
        }
    }
}
