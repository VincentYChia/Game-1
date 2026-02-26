// ============================================================================
// Game1.Unity.Core.GameStateManager
// Migrated from: core/game_engine.py (lines 518-660: state flags)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's scattered boolean flags with a proper state machine.
// Handles UI panel open/close, game state transitions, and input context.
// ============================================================================

using System;
using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Game state enumeration. Replaces 12+ boolean flags in Python.
    /// Only one modal UI state is active at a time.
    /// </summary>
    public enum GameState
    {
        StartMenu,
        ClassSelection,
        Loading,
        Playing,
        Paused,
        InventoryOpen,
        EquipmentOpen,
        CraftingOpen,
        MinigameActive,
        StatsOpen,
        SkillsOpen,
        EncyclopediaOpen,
        MapOpen,
        NPCDialogue,
        DungeonChestOpen,
        SpawnChestOpen,
        DeathChestOpen,
        EnchantmentSelection,
    }

    /// <summary>
    /// Manages game state transitions.
    /// Ensures only one modal UI is active at a time.
    /// Escape key returns to Playing from any UI state.
    /// MinigameActive blocks all other state transitions until complete.
    /// </summary>
    public class GameStateManager : MonoBehaviour
    {
        // ====================================================================
        // Singleton (reliable access from UI panels, avoids FindFirstObjectByType)
        // ====================================================================

        public static GameStateManager Instance { get; private set; }

        private void Awake()
        {
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        // ====================================================================
        // Events
        // ====================================================================

        /// <summary>
        /// Raised when the game state changes. Args: (oldState, newState).
        /// UI components subscribe to show/hide themselves.
        /// </summary>
        public event Action<GameState, GameState> OnStateChanged;

        // ====================================================================
        // State
        // ====================================================================

        /// <summary>Current game state.</summary>
        public GameState CurrentState { get; private set; } = GameState.StartMenu;

        /// <summary>Previous game state (for returning from menus).</summary>
        public GameState PreviousState { get; private set; } = GameState.StartMenu;

        /// <summary>Whether the game is in a modal UI state (not Playing).</summary>
        public bool IsInModalUI => CurrentState != GameState.Playing
                                 && CurrentState != GameState.StartMenu
                                 && CurrentState != GameState.ClassSelection
                                 && CurrentState != GameState.Loading;

        /// <summary>Whether the game is in an active gameplay state.</summary>
        public bool IsPlaying => CurrentState == GameState.Playing;

        /// <summary>Whether player input should be blocked (modal UI or minigame).</summary>
        public bool IsInputBlocked => CurrentState == GameState.MinigameActive
                                    || CurrentState == GameState.Paused
                                    || CurrentState == GameState.StartMenu
                                    || CurrentState == GameState.ClassSelection
                                    || CurrentState == GameState.Loading;

        // ====================================================================
        // State Transitions
        // ====================================================================

        /// <summary>
        /// Transition to a new state.
        /// Returns false if the transition is blocked (e.g., during minigame).
        /// </summary>
        public bool TransitionTo(GameState newState)
        {
            // Block transitions during minigame (except canceling)
            if (CurrentState == GameState.MinigameActive && newState != GameState.Playing)
            {
                Debug.LogWarning($"[GameStateManager] Blocked transition to {newState} — minigame active");
                return false;
            }

            if (CurrentState == newState) return true;

            var oldState = CurrentState;
            PreviousState = oldState;
            CurrentState = newState;

            Debug.Log($"[GameStateManager] {oldState} → {newState}");
            OnStateChanged?.Invoke(oldState, newState);

            return true;
        }

        /// <summary>
        /// Toggle a UI panel state. If already open, return to Playing.
        /// If another panel is open, switch to the new one.
        /// </summary>
        public void TogglePanel(GameState panelState)
        {
            if (CurrentState == panelState)
            {
                TransitionTo(GameState.Playing);
            }
            else if (CurrentState == GameState.Playing || IsInModalUI)
            {
                TransitionTo(panelState);
            }
        }

        /// <summary>
        /// Handle Escape key — returns to Playing from any UI state.
        /// From Playing, could open pause menu (not implemented in Python).
        /// </summary>
        public void HandleEscape()
        {
            switch (CurrentState)
            {
                case GameState.Playing:
                    TransitionTo(GameState.Paused);
                    break;

                case GameState.Paused:
                    TransitionTo(GameState.Playing);
                    break;

                case GameState.MinigameActive:
                    // Minigame handles its own cancel logic
                    TransitionTo(GameState.Playing);
                    break;

                case GameState.StartMenu:
                case GameState.ClassSelection:
                    // Can't escape from start menu or class selection
                    break;

                default:
                    // Return to gameplay from any open panel
                    TransitionTo(GameState.Playing);
                    break;
            }
        }

        // ====================================================================
        // Query Methods
        // ====================================================================

        /// <summary>Whether a specific panel is currently open.</summary>
        public bool IsPanelOpen(GameState panelState)
        {
            return CurrentState == panelState;
        }

        /// <summary>Whether any chest UI is open.</summary>
        public bool IsChestOpen()
        {
            return CurrentState == GameState.DungeonChestOpen
                || CurrentState == GameState.SpawnChestOpen
                || CurrentState == GameState.DeathChestOpen;
        }
    }
}
