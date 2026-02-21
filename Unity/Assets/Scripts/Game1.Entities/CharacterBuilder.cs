// ============================================================================
// Game1.Entities.CharacterBuilder
// Migrated from: N/A (new architecture — IMPROVEMENTS.md)
// Migration phase: 3
// Date: 2026-02-21
//
// Builder pattern for constructing fully initialized Character instances.
// Replaces scattered character setup logic in game_engine.py.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Models;
using Game1.Data.Databases;

namespace Game1.Entities
{
    /// <summary>
    /// Builder for creating Character instances with various configurations.
    /// Encapsulates initialization order and default values.
    ///
    /// Usage:
    ///   var player = CharacterBuilder.NewPlayer("Hero", "warrior")
    ///       .AtPosition(GamePosition.FromXZ(50, 50))
    ///       .WithLevel(5)
    ///       .Build();
    /// </summary>
    public class CharacterBuilder
    {
        private string _name = "Player";
        private string _classId = "";
        private GamePosition _position = GamePosition.FromXZ(
            GameConfig.PlayerSpawnX, GameConfig.PlayerSpawnZ);
        private int _level = 1;
        private Dictionary<string, int> _stats;
        private List<string> _startingItems;
        private List<string> _startingSkills;
        private string _titleId;

        private CharacterBuilder() { }

        // ====================================================================
        // Static Factory Methods
        // ====================================================================

        /// <summary>
        /// Start building a new player character.
        /// </summary>
        public static CharacterBuilder NewPlayer(string name, string classId = "")
        {
            return new CharacterBuilder
            {
                _name = name,
                _classId = classId,
            };
        }

        /// <summary>
        /// Start building from save data.
        /// </summary>
        public static CharacterBuilder FromSaveData(Dictionary<string, object> saveData)
        {
            var builder = new CharacterBuilder();

            if (saveData.TryGetValue("name", out var nameObj))
                builder._name = nameObj?.ToString() ?? "Player";
            if (saveData.TryGetValue("class_id", out var classObj))
                builder._classId = classObj?.ToString() ?? "";
            if (saveData.TryGetValue("position_x", out var px) && saveData.TryGetValue("position_z", out var pz))
                builder._position = GamePosition.FromXZ(Convert.ToSingle(px), Convert.ToSingle(pz));
            if (saveData.TryGetValue("level", out var levelObj))
                builder._level = Convert.ToInt32(levelObj);

            return builder;
        }

        // ====================================================================
        // Builder Methods (fluent API)
        // ====================================================================

        public CharacterBuilder AtPosition(GamePosition pos)
        {
            _position = pos;
            return this;
        }

        public CharacterBuilder WithLevel(int level)
        {
            _level = Math.Clamp(level, 1, 30);
            return this;
        }

        public CharacterBuilder WithStats(Dictionary<string, int> stats)
        {
            _stats = stats;
            return this;
        }

        public CharacterBuilder WithStartingItems(List<string> itemIds)
        {
            _startingItems = itemIds;
            return this;
        }

        public CharacterBuilder WithStartingSkills(List<string> skillIds)
        {
            _startingSkills = skillIds;
            return this;
        }

        public CharacterBuilder WithTitle(string titleId)
        {
            _titleId = titleId;
            return this;
        }

        // ====================================================================
        // Build
        // ====================================================================

        /// <summary>
        /// Build and return the fully initialized Character.
        /// </summary>
        public Character Build()
        {
            // Create character at position
            var character = new Character(_position);
            character.Name = _name;

            // Select class (if specified)
            if (!string.IsNullOrEmpty(_classId))
            {
                character.SelectClass(_classId);
            }

            // Apply stats (if specified)
            if (_stats != null)
            {
                foreach (var kvp in _stats)
                {
                    character.Stats.SetStat(kvp.Key, kvp.Value);
                }
            }

            // Set level directly (bypasses EXP requirements)
            if (_level > 1)
            {
                character.Leveling.SetLevel(_level);
            }

            // Add starting items
            if (_startingItems != null)
            {
                foreach (var itemId in _startingItems)
                {
                    character.Inventory.AddItem(itemId, 1);
                }
            }

            // Learn starting skills
            if (_startingSkills != null)
            {
                foreach (var skillId in _startingSkills)
                {
                    character.Skills.LearnSkill(skillId);
                }
            }

            // Apply title
            if (!string.IsNullOrEmpty(_titleId))
            {
                character.StatTracker.RecordActivity("title_earned", 1);
            }

            // Ensure health/mana are at max after all setup
            character.Stats.InitializeToMax();

            return character;
        }
    }
}
