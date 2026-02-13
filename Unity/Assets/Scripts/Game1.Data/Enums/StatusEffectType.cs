// ============================================================================
// Game1.Data.Enums.StatusEffectType
// Migrated from: entities/status_effect.py, entities/status_manager.py
// Migration phase: 1
// Date: 2026-02-13
// ============================================================================

using System;
using System.Collections.Generic;

namespace Game1.Data.Enums
{
    /// <summary>
    /// Status effect types for the combat system.
    /// Categories: DoT, CC, Buffs, Debuffs, Special.
    /// </summary>
    public enum StatusEffectType
    {
        // DoT (Damage over Time)
        Burn,
        Bleed,
        Poison,
        Shock,

        // CC (Crowd Control)
        Freeze,
        Stun,
        Root,
        Slow,

        // Buffs
        Empower,
        Fortify,
        Haste,
        Regeneration,
        Shield,

        // Debuffs
        Vulnerable,
        Weaken,

        // Special
        Phase,
        Invisible
    }

    public static class StatusEffectTypeExtensions
    {
        private static readonly Dictionary<string, StatusEffectType> _fromJsonMap = new(StringComparer.OrdinalIgnoreCase)
        {
            ["burn"]         = StatusEffectType.Burn,
            ["bleed"]        = StatusEffectType.Bleed,
            ["poison"]       = StatusEffectType.Poison,
            ["shock"]        = StatusEffectType.Shock,
            ["freeze"]       = StatusEffectType.Freeze,
            ["stun"]         = StatusEffectType.Stun,
            ["root"]         = StatusEffectType.Root,
            ["slow"]         = StatusEffectType.Slow,
            ["chill"]        = StatusEffectType.Slow,          // alias
            ["empower"]      = StatusEffectType.Empower,
            ["fortify"]      = StatusEffectType.Fortify,
            ["haste"]        = StatusEffectType.Haste,
            ["regeneration"] = StatusEffectType.Regeneration,
            ["regen"]        = StatusEffectType.Regeneration,  // alias
            ["shield"]       = StatusEffectType.Shield,
            ["barrier"]      = StatusEffectType.Shield,        // alias
            ["vulnerable"]   = StatusEffectType.Vulnerable,
            ["weaken"]       = StatusEffectType.Weaken,
            ["phase"]        = StatusEffectType.Phase,
            ["ethereal"]     = StatusEffectType.Phase,         // alias
            ["invisible"]    = StatusEffectType.Invisible,
        };

        private static readonly Dictionary<StatusEffectType, string> _toJsonMap = new()
        {
            [StatusEffectType.Burn]         = "burn",
            [StatusEffectType.Bleed]        = "bleed",
            [StatusEffectType.Poison]       = "poison",
            [StatusEffectType.Shock]        = "shock",
            [StatusEffectType.Freeze]       = "freeze",
            [StatusEffectType.Stun]         = "stun",
            [StatusEffectType.Root]         = "root",
            [StatusEffectType.Slow]         = "slow",
            [StatusEffectType.Empower]      = "empower",
            [StatusEffectType.Fortify]      = "fortify",
            [StatusEffectType.Haste]        = "haste",
            [StatusEffectType.Regeneration] = "regeneration",
            [StatusEffectType.Shield]       = "shield",
            [StatusEffectType.Vulnerable]   = "vulnerable",
            [StatusEffectType.Weaken]       = "weaken",
            [StatusEffectType.Phase]        = "phase",
            [StatusEffectType.Invisible]    = "invisible",
        };

        public static string ToJsonString(this StatusEffectType type)
        {
            return _toJsonMap.TryGetValue(type, out var str) ? str : "burn";
        }

        public static StatusEffectType FromJsonString(string json)
        {
            if (string.IsNullOrEmpty(json)) return StatusEffectType.Burn;
            return _fromJsonMap.TryGetValue(json, out var type) ? type : StatusEffectType.Burn;
        }

        /// <summary>Check if this is a DoT (damage over time) effect.</summary>
        public static bool IsDot(this StatusEffectType type)
        {
            return type == StatusEffectType.Burn ||
                   type == StatusEffectType.Bleed ||
                   type == StatusEffectType.Poison ||
                   type == StatusEffectType.Shock;
        }

        /// <summary>Check if this is a CC (crowd control) effect.</summary>
        public static bool IsCC(this StatusEffectType type)
        {
            return type == StatusEffectType.Freeze ||
                   type == StatusEffectType.Stun ||
                   type == StatusEffectType.Root ||
                   type == StatusEffectType.Slow;
        }

        /// <summary>Check if this is a buff.</summary>
        public static bool IsBuff(this StatusEffectType type)
        {
            return type == StatusEffectType.Empower ||
                   type == StatusEffectType.Fortify ||
                   type == StatusEffectType.Haste ||
                   type == StatusEffectType.Regeneration ||
                   type == StatusEffectType.Shield;
        }

        /// <summary>Check if this is a debuff.</summary>
        public static bool IsDebuff(this StatusEffectType type)
        {
            return type == StatusEffectType.Vulnerable ||
                   type == StatusEffectType.Weaken;
        }
    }
}
