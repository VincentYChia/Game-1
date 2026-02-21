// ============================================================================
// Game1.Systems.Combat.CharacterCombatAdapter
// Migrated from: N/A (new architecture — bridges Character to ICombatCharacter)
// Migration phase: 4-6 bridge
// Date: 2026-02-21
//
// Adapter that makes Character compatible with CombatManager's ICombatCharacter
// interface without modifying the Character class directly.
// ============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using Game1.Core;
using Game1.Data.Models;
using Game1.Data.Enums;
using Game1.Entities;
using Game1.Entities.Components;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Adapter wrapping a Character to satisfy ICombatCharacter.
    /// Created by GameManager when combat system is initialized.
    /// </summary>
    public class CharacterCombatAdapter : ICombatCharacter
    {
        private readonly Character _character;

        public CharacterCombatAdapter(Character character)
        {
            _character = character ?? throw new ArgumentNullException(nameof(character));
        }

        // ====================================================================
        // Position
        // ====================================================================

        public float PositionX => _character.Position.X;
        public float PositionY => _character.Position.Z; // Z maps to 2D Y

        // ====================================================================
        // Health
        // ====================================================================

        public float Health
        {
            get => _character.Stats.CurrentHealth;
            set => _character.Stats.CurrentHealth = value;
        }

        public float MaxHealth => _character.Stats.MaxHealth;

        // ====================================================================
        // Core Stats
        // ====================================================================

        public int Strength => _character.Stats.Strength;
        public int DefenseStat => _character.Stats.Defense;

        // ====================================================================
        // Weapon / Damage
        // ====================================================================

        public int GetWeaponDamage()
        {
            var (min, max) = _character.Equipment.GetWeaponDamage(EquipmentSlot.MainHand);
            return (min + max) / 2;
        }

        public float GetToolEffectivenessForAction(object weapon, string action)
        {
            // Tool effectiveness defaults to 1.0 for combat actions
            if (weapon is EquipmentItem equip)
            {
                float durabilityRatio = equip.DurabilityMax > 0
                    ? (float)equip.DurabilityCurrent / equip.DurabilityMax
                    : 1.0f;
                return GameConfig.MinDurabilityEffectiveness +
                       (1f - GameConfig.MinDurabilityEffectiveness) * durabilityRatio;
            }
            return 1.0f;
        }

        public float GetEnemyDamageMultiplier(ICombatEnemy enemy)
        {
            // Class affinity bonus
            var classDef = _character.GetClassDefinition();
            if (classDef == null) return 1.0f;

            // Check for damage bonus tags on class vs enemy
            return 1.0f; // Base multiplier; class bonuses applied via tag system
        }

        // ====================================================================
        // Luck / Shield
        // ====================================================================

        public int GetEffectiveLuck()
        {
            return _character.Stats.Luck;
        }

        public bool IsShieldActive()
        {
            var offhand = _character.Equipment.GetEquipped(EquipmentSlot.OffHand);
            return offhand != null && (offhand.Tags?.Contains("shield") ?? false);
        }

        public float GetShieldDamageReduction()
        {
            if (!IsShieldActive()) return 0f;
            var shield = _character.Equipment.GetEquipped(EquipmentSlot.OffHand);
            // Shield defense contribution
            return shield?.Defense ?? 0f;
        }

        // ====================================================================
        // Health Management
        // ====================================================================

        public void TakeDamage(float amount, bool fromAttack = false)
        {
            _character.Stats.TakeDamage(amount);
            if (!_character.Stats.IsAlive)
            {
                GameEvents.RaiseCharacterDied(_character);
            }
        }

        public void Heal(float amount)
        {
            _character.Stats.Heal(amount);
        }

        // ====================================================================
        // Rewards
        // ====================================================================

        public void AddExp(int amount)
        {
            _character.GainExperience(amount, "combat");
        }

        public bool AddItemToInventory(string materialId, int quantity)
        {
            return _character.Inventory.AddItem(materialId, quantity);
        }

        // ====================================================================
        // Equipment Queries
        // ====================================================================

        public object GetEquippedWeapon(string hand)
        {
            var slot = hand == "offHand" ? EquipmentSlot.OffHand : EquipmentSlot.MainHand;
            return _character.Equipment.GetEquipped(slot);
        }

        public string GetSelectedSlot()
        {
            return "mainHand";
        }

        public float GetTotalArmorDefense()
        {
            return _character.Equipment.GetTotalDefense();
        }

        public float GetProtectionEnchantmentReduction()
        {
            // Sum protection enchantment values from all equipped items
            float reduction = 0f;
            foreach (var kvp in _character.Equipment.GetAllEquipped())
            {
                var item = kvp.Value;
                if (item.Enchantments != null)
                {
                    foreach (var ench in item.Enchantments)
                    {
                        if (ench.TryGetValue("type", out var typeObj) &&
                            typeObj?.ToString() == "protection")
                        {
                            if (ench.TryGetValue("value", out var valObj))
                                reduction += Convert.ToSingle(valObj);
                        }
                    }
                }
            }
            return reduction;
        }

        public List<string> GetWeaponMetadataTags(object weapon)
        {
            if (weapon is EquipmentItem equip && equip.Tags != null)
                return equip.Tags.ToList();
            return new List<string>();
        }

        public List<Dictionary<string, object>> GetWeaponEnchantments(object weapon)
        {
            if (weapon is EquipmentItem equip && equip.Enchantments != null)
                return equip.Enchantments.ToList();
            return new List<Dictionary<string, object>>();
        }

        public bool HasOffhand
        {
            get
            {
                var offhand = _character.Equipment.GetEquipped(EquipmentSlot.OffHand);
                return offhand != null;
            }
        }

        // ====================================================================
        // Durability
        // ====================================================================

        public float GetDurabilityLossMultiplier()
        {
            return _character.Stats.GetDurabilityLossMultiplier();
        }

        public float GetWeaponDurability(object weapon)
        {
            if (weapon is EquipmentItem equip)
                return equip.DurabilityCurrent;
            return 100f;
        }

        public void SetWeaponDurability(object weapon, float value)
        {
            if (weapon is EquipmentItem equip)
                equip.DurabilityCurrent = (int)MathF.Max(0, value);
        }

        public float GetWeaponMaxDurability(object weapon)
        {
            if (weapon is EquipmentItem equip)
                return equip.DurabilityMax;
            return 100f;
        }

        // ====================================================================
        // Buff Queries
        // ====================================================================

        public float GetEmpowerBonus()
        {
            return _character.Buffs.GetDamageBonus("combat");
        }

        public float GetPierceBonus()
        {
            return _character.Buffs.GetTotalBonus("pierce", null);
        }

        public float GetFortifyReduction()
        {
            return _character.Buffs.GetDefenseBonus();
        }

        public float GetWeakenReduction()
        {
            return _character.Buffs.GetTotalBonus("weaken", null);
        }

        // ====================================================================
        // Title Bonuses
        // ====================================================================

        public TitleBonuses GetTitleBonuses()
        {
            // Return empty title bonuses — title system integration is Phase 7
            return new TitleBonuses();
        }
    }
}
