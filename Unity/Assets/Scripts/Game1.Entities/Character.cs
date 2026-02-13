// ============================================================================
// Game1.Entities.Character
// Migrated from: entities/character.py (lines 1-100+)
// Migration phase: 3 (MACRO-4: Component Pattern, MACRO-6: GamePosition)
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Core;
using Game1.Data.Models;
using Game1.Data.Databases;
using Game1.Data.Enums;
using Game1.Entities.Components;

namespace Game1.Entities
{
    /// <summary>
    /// Main player character class.
    /// Composed of pluggable components (MACRO-4) with event-driven communication (MACRO-1).
    /// Uses GamePosition for all positions (MACRO-6).
    /// </summary>
    public class Character
    {
        // ====================================================================
        // Identity
        // ====================================================================
        public string Name { get; set; } = "Player";
        public string ClassId { get; private set; } = "";

        // ====================================================================
        // Position (MACRO-6: GamePosition, not raw coordinates)
        // ====================================================================
        public GamePosition Position { get; set; }
        public string Facing { get; set; } = "down";
        public float MovementSpeed { get; set; } = GameConfig.PlayerSpeed;
        public float InteractionRange { get; set; } = GameConfig.InteractionRange;

        // ====================================================================
        // Components (MACRO-4: Character is a composition of components)
        // ====================================================================
        public CharacterStats Stats { get; }
        public Inventory Inventory { get; }
        public EquipmentManager Equipment { get; }
        public SkillManager Skills { get; }
        public BuffManager Buffs { get; }
        public LevelingSystem Leveling { get; }
        public StatTracker StatTracker { get; }

        // ====================================================================
        // Knockback state
        // ====================================================================
        public float KnockbackVelocityX { get; set; }
        public float KnockbackVelocityZ { get; set; }
        public float KnockbackDurationRemaining { get; set; }

        // ====================================================================
        // Combat state
        // ====================================================================
        public bool IsAlive => Stats.IsAlive;
        public float CurrentHealth => Stats.CurrentHealth;
        public float MaxHealth => Stats.MaxHealth;
        public float CurrentMana => Stats.CurrentMana;
        public float MaxMana => Stats.MaxMana;

        // ====================================================================
        // Constructor
        // ====================================================================

        public Character(GamePosition startPosition)
        {
            Position = startPosition;

            // Initialize components
            Stats = new CharacterStats();
            Inventory = new Inventory(GameConfig.DefaultInventorySlots);
            Equipment = new EquipmentManager();
            Skills = new SkillManager();
            Buffs = new BuffManager();
            Leveling = new LevelingSystem();
            StatTracker = new StatTracker();

            // Initialize health/mana to max
            Stats.InitializeToMax();

            // Listen for equipment changes to recalculate stats
            GameEvents.OnEquipmentChanged += _onEquipmentChanged;
            GameEvents.OnEquipmentRemoved += _onEquipmentRemoved;
        }

        // ====================================================================
        // Experience / Leveling
        // ====================================================================

        /// <summary>
        /// Gain experience points. May trigger level up.
        /// </summary>
        public bool GainExperience(int amount, string source = "")
        {
            bool leveledUp = Leveling.GainExperience(amount, this);
            if (leveledUp)
            {
                _onLevelUp();
            }
            StatTracker.RecordActivity("exp_gained", amount);
            return leveledUp;
        }

        // ====================================================================
        // Class Selection
        // ====================================================================

        /// <summary>Select a character class. Can only be set once.</summary>
        public bool SelectClass(string classId)
        {
            if (!string.IsNullOrEmpty(ClassId)) return false;

            var classDef = ClassDatabase.Instance.GetClass(classId);
            if (classDef == null) return false;

            ClassId = classId;

            // Learn starting skill if any
            if (!string.IsNullOrEmpty(classDef.StartingSkill))
            {
                Skills.LearnSkill(classDef.StartingSkill);
            }

            GameEvents.RaiseClassSelected(this, classId);
            return true;
        }

        /// <summary>Get the class definition for the selected class. Null if no class.</summary>
        public ClassDefinition GetClassDefinition()
        {
            if (string.IsNullOrEmpty(ClassId)) return null;
            return ClassDatabase.Instance.GetClass(ClassId);
        }

        // ====================================================================
        // Stat Management
        // ====================================================================

        /// <summary>
        /// Allocate a stat point to a stat.
        /// </summary>
        public bool AllocateStatPoint(string statName)
        {
            if (Leveling.UnallocatedStatPoints <= 0) return false;

            int current = Stats.GetStat(statName);
            if (current >= 30) return false; // Max stat value

            Stats.SetStat(statName, current + 1);
            Leveling.UnallocatedStatPoints--;

            // Recalculate derived stats
            _recalculateStats();
            return true;
        }

        // ====================================================================
        // Private Handlers
        // ====================================================================

        private void _onLevelUp()
        {
            // Update health/mana max
            _recalculateStats();

            // Heal to full on level up
            Stats.CurrentHealth = Stats.MaxHealth;
            Stats.CurrentMana = Stats.MaxMana;
        }

        private void _onEquipmentChanged(object item, int slot)
        {
            _recalculateStats();
        }

        private void _onEquipmentRemoved(object item, int slot)
        {
            _recalculateStats();
        }

        private void _recalculateStats()
        {
            // Health cap check
            if (Stats.CurrentHealth > Stats.MaxHealth)
                Stats.CurrentHealth = Stats.MaxHealth;
            if (Stats.CurrentMana > Stats.MaxMana)
                Stats.CurrentMana = Stats.MaxMana;
        }

        // ====================================================================
        // Update
        // ====================================================================

        /// <summary>Update character per-frame (cooldowns, buffs, knockback).</summary>
        public void Update(float deltaTime)
        {
            // Update skill cooldowns
            Skills.UpdateCooldowns(deltaTime);

            // Update buffs
            Buffs.Update(deltaTime);

            // Update knockback
            if (KnockbackDurationRemaining > 0)
            {
                KnockbackDurationRemaining -= deltaTime;
                Position = new GamePosition(
                    Position.X + KnockbackVelocityX * deltaTime,
                    Position.Y,
                    Position.Z + KnockbackVelocityZ * deltaTime
                );

                if (KnockbackDurationRemaining <= 0)
                {
                    KnockbackVelocityX = 0;
                    KnockbackVelocityZ = 0;
                }
            }
        }
    }
}
