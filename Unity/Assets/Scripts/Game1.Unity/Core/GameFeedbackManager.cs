// ============================================================================
// Game1.Unity.Core.GameFeedbackManager
// Date: 2026-03-04
//
// Bridges GameEvents to visual feedback systems (DamageNumberRenderer,
// NotificationUI). Provides on-screen feedback for combat damage, resource
// harvesting, item pickups, tool swapping, and other game events.
// ============================================================================

using UnityEngine;
using Game1.Core;
using Game1.Data.Enums;
using Game1.Entities;
using Game1.Systems.Combat;
using Game1.Unity.UI;
using Game1.Unity.World;
using Game1.Unity.Utilities;

namespace Game1.Unity.Core
{
    public class GameFeedbackManager : MonoBehaviour
    {
        public static GameFeedbackManager Instance { get; private set; }

        private void Awake()
        {
            Instance = this;
        }

        private void OnEnable()
        {
            GameEvents.OnDamageDealt += _onDamageDealt;
            GameEvents.OnResourceHarvested += _onResourceHarvested;
            GameEvents.OnResourceDepleted += _onResourceDepleted;
            GameEvents.OnActiveToolChanged += _onToolChanged;
            GameEvents.OnItemCrafted += _onItemCrafted;
            GameEvents.OnLevelUp += _onLevelUp;
            GameEvents.OnEnemyKilled += _onEnemyKilled;
        }

        private void OnDisable()
        {
            GameEvents.OnDamageDealt -= _onDamageDealt;
            GameEvents.OnResourceHarvested -= _onResourceHarvested;
            GameEvents.OnResourceDepleted -= _onResourceDepleted;
            GameEvents.OnActiveToolChanged -= _onToolChanged;
            GameEvents.OnItemCrafted -= _onItemCrafted;
            GameEvents.OnLevelUp -= _onLevelUp;
            GameEvents.OnEnemyKilled -= _onEnemyKilled;
        }

        // ====================================================================
        // Combat Damage
        // ====================================================================

        private void _onDamageDealt(object attacker, object target, float amount)
        {
            if (DamageNumberRenderer.Instance == null) return;

            // Determine target position for floating number
            Vector3 targetPos = Vector3.zero;
            bool isCrit = amount > 0 && amount == Mathf.Round(amount) && amount % 2 == 0;
            // Heuristic: we don't have isCrit flag in event, but we can check for even numbers
            // from the 2x crit multiplier. For now just show the number.

            if (target is Enemy enemy)
            {
                targetPos = new Vector3(enemy.Position.X, 1f, enemy.Position.Z);
                float terrainY = ChunkMeshGenerator.SampleTerrainHeight(
                    targetPos.x, targetPos.z, "grass");
                targetPos.y = terrainY + 1.5f;
            }
            else if (target is ICombatEnemy combatEnemy)
            {
                // ICombatEnemy might have position info
                targetPos = _getPlayerForwardPoint(2f);
                targetPos.y += 1f;
            }
            else
            {
                targetPos = _getPlayerForwardPoint(2f);
                targetPos.y += 1f;
            }

            DamageNumberRenderer.Instance.SpawnDamageNumber(
                targetPos, amount, false, "physical");
        }

        // ====================================================================
        // Resource Harvesting
        // ====================================================================

        /// <summary>Show floating damage number on resource hit.</summary>
        public void ShowHarvestDamage(Vector3 resourcePos, int damage, bool isCrit)
        {
            if (DamageNumberRenderer.Instance == null) return;

            Vector3 pos = resourcePos + Vector3.up * 1.5f;
            // Use a distinct color for harvest damage
            DamageNumberRenderer.Instance.SpawnDamageNumber(
                pos, damage, isCrit, "physical");
        }

        /// <summary>Show resource health bar info as notification.</summary>
        public void ShowHarvestHit(string resourceId, int currentHp, int maxHp, int damage, bool isCrit)
        {
            // Floating number at resource position is handled by ShowHarvestDamage
            // Show a brief notification for the hit
            if (NotificationUI.Instance == null) return;

            string critStr = isCrit ? " CRIT!" : "";
            Color hitColor = isCrit ? new Color(1f, 0.8f, 0f) : new Color(0.8f, 0.8f, 0.8f);
            NotificationUI.Instance.Show(
                $"{_formatResourceName(resourceId)}: {damage} dmg{critStr} ({currentHp}/{maxHp} HP)",
                hitColor, 1.5f);
        }

        private void _onResourceHarvested(string resourceId, string itemId, int quantity)
        {
            if (NotificationUI.Instance == null) return;

            string itemName = _formatItemName(itemId);
            NotificationUI.Instance.Show(
                $"+ {quantity}x {itemName}",
                new Color(0.4f, 1f, 0.4f), // Green for loot
                3f);
        }

        private void _onResourceDepleted(string resourceId)
        {
            if (NotificationUI.Instance == null) return;

            NotificationUI.Instance.Show(
                $"{_formatResourceName(resourceId)} depleted",
                new Color(0.7f, 0.7f, 0.7f), 2f);
        }

        // ====================================================================
        // Tool Swap
        // ====================================================================

        private void _onToolChanged(int toolSlot)
        {
            if (NotificationUI.Instance == null) return;

            var player = GameManager.Instance?.Player;
            if (player == null) return;

            var slot = (EquipmentSlot)toolSlot;
            var equipped = player.Equipment.GetEquipped(slot);
            string toolName = equipped?.Name ?? "(empty)";

            NotificationUI.Instance.Show(
                $"Tool: {slot} — {toolName}",
                new Color(0.6f, 0.8f, 1f), 2f);
        }

        // ====================================================================
        // Crafting
        // ====================================================================

        private void _onItemCrafted(string discipline, string itemId)
        {
            if (NotificationUI.Instance == null) return;

            NotificationUI.Instance.Show(
                $"Crafted: {_formatItemName(itemId)} ({discipline})",
                new Color(1f, 0.85f, 0.3f), 4f);
        }

        // ====================================================================
        // Level Up
        // ====================================================================

        private void _onLevelUp(object character, int newLevel)
        {
            if (NotificationUI.Instance == null) return;

            NotificationUI.Instance.Show(
                $"LEVEL UP! You are now level {newLevel}!",
                new Color(1f, 0.9f, 0.2f), 5f);
        }

        // ====================================================================
        // Enemy Killed
        // ====================================================================

        private void _onEnemyKilled(object enemy)
        {
            if (NotificationUI.Instance == null) return;

            string name = "Enemy";
            if (enemy is Enemy e)
                name = e.Name;

            NotificationUI.Instance.Show(
                $"Defeated: {name}",
                new Color(1f, 0.5f, 0.5f), 3f);
        }

        // ====================================================================
        // Helpers
        // ====================================================================

        private Vector3 _getPlayerForwardPoint(float distance)
        {
            var cam = Camera.main;
            if (cam != null)
            {
                return cam.transform.position + cam.transform.forward * distance;
            }
            // Fallback: use player position
            var player = GameManager.Instance?.Player;
            if (player != null)
            {
                return new Vector3(player.Position.X, 1f, player.Position.Z);
            }
            return Vector3.zero;
        }

        private static string _formatItemName(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) return "Unknown";
            // Convert snake_case to Title Case: "pine_log" → "Pine Log"
            var parts = itemId.Split('_');
            for (int i = 0; i < parts.Length; i++)
            {
                if (parts[i].Length > 0)
                    parts[i] = char.ToUpper(parts[i][0]) + parts[i].Substring(1);
            }
            return string.Join(" ", parts);
        }

        private static string _formatResourceName(string resourceId)
        {
            return _formatItemName(resourceId);
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }
    }
}
