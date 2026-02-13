// ============================================================================
// Game1.Unity.Config.CombatConfigAsset
// Migrated from: Combat/combat_manager.py (visual feedback settings)
// Migration phase: 6
// Date: 2026-02-13
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Unity-specific combat visual configuration.
    /// Combat formulas/balance live in Phase 4 CombatManager and DamageCalculator.
    /// </summary>
    [CreateAssetMenu(fileName = "CombatConfig", menuName = "Game1/CombatConfig")]
    public class CombatConfigAsset : ScriptableObject
    {
        [Header("Damage Numbers")]
        public float DamageNumberScale = 1f;
        public float CritDamageNumberScale = 1.5f;
        public float HealNumberScale = 1f;

        [Header("Attack Effects")]
        public float MeleeAttackLineWidth = 0.1f;
        public float RangedAttackLineWidth = 0.05f;
        public float AoECircleWidth = 0.1f;

        [Header("Health Bars")]
        public float EnemyHealthBarWidth = 1.2f;
        public float EnemyHealthBarHeight = 0.15f;
        public float EnemyHealthBarOffset = 0.8f;
        public Color HealthBarFull = new Color(0f, 0.8f, 0f);
        public Color HealthBarLow = new Color(0.8f, 0f, 0f);
        public float HealthBarLowThreshold = 0.25f;

        [Header("Status Effect Icons")]
        public float StatusIconSize = 0.3f;
        public float StatusIconSpacing = 0.05f;

        [Header("Corpse")]
        public float CorpseFadeDuration = 2f;
        public float CorpseLifetime = 30f;
    }
}
