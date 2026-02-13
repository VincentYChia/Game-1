// ============================================================================
// Game1.Unity.Utilities.SpriteDatabase
// Migrated from: core/image_cache.py (ImageCache singleton)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's ImageCache with Unity sprite loading/caching.
// Sprites are loaded from Resources/ or SpriteAtlases.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.U2D;

namespace Game1.Unity.Utilities
{
    /// <summary>
    /// Centralized sprite loading and caching.
    /// Replaces Python's ImageCache singleton.
    /// Maps item IDs to Unity Sprites via Resources or SpriteAtlases.
    /// </summary>
    public class SpriteDatabase : MonoBehaviour
    {
        public static SpriteDatabase Instance { get; private set; }

        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Sprite Atlases")]
        [SerializeField] private SpriteAtlas _materialAtlas;
        [SerializeField] private SpriteAtlas _equipmentAtlas;
        [SerializeField] private SpriteAtlas _worldAtlas;
        [SerializeField] private SpriteAtlas _uiAtlas;
        [SerializeField] private SpriteAtlas _effectsAtlas;

        [Header("Fallbacks")]
        [SerializeField] private Sprite _defaultItemSprite;
        [SerializeField] private Sprite _defaultTileSprite;
        [SerializeField] private Sprite _defaultEnemySprite;

        // ====================================================================
        // Cache
        // ====================================================================

        private Dictionary<string, Sprite> _spriteCache = new Dictionary<string, Sprite>();

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Get a sprite for an item by its ID.
        /// Searches atlases first, then Resources, then returns fallback.
        /// </summary>
        public Sprite GetItemSprite(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) return _defaultItemSprite;

            if (_spriteCache.TryGetValue(itemId, out var cached))
                return cached;

            // Try sprite atlases
            Sprite sprite = _tryGetFromAtlases(itemId);

            // Try Resources folder
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Items/" + itemId);

            // Try by category subfolders
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Materials/" + itemId);
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Equipment/" + itemId);

            // Cache result (even null → will use fallback)
            _spriteCache[itemId] = sprite ?? _defaultItemSprite;
            return _spriteCache[itemId];
        }

        /// <summary>Get a tile sprite by tile type name.</summary>
        public Sprite GetTileSprite(string tileType)
        {
            if (string.IsNullOrEmpty(tileType)) return _defaultTileSprite;

            string key = "tile_" + tileType;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = null;
            if (_worldAtlas != null)
                sprite = _worldAtlas.GetSprite(tileType);
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/World/" + tileType);

            _spriteCache[key] = sprite ?? _defaultTileSprite;
            return _spriteCache[key];
        }

        /// <summary>Get an enemy sprite by enemy ID.</summary>
        public Sprite GetEnemySprite(string enemyId)
        {
            if (string.IsNullOrEmpty(enemyId)) return _defaultEnemySprite;

            string key = "enemy_" + enemyId;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = Resources.Load<Sprite>("Sprites/Enemies/" + enemyId);
            _spriteCache[key] = sprite ?? _defaultEnemySprite;
            return _spriteCache[key];
        }

        /// <summary>Get a UI sprite by name.</summary>
        public Sprite GetUISprite(string spriteName)
        {
            if (string.IsNullOrEmpty(spriteName)) return null;

            string key = "ui_" + spriteName;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = null;
            if (_uiAtlas != null)
                sprite = _uiAtlas.GetSprite(spriteName);
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/UI/" + spriteName);

            _spriteCache[key] = sprite;
            return sprite;
        }

        /// <summary>Clear the sprite cache (e.g., when loading a new game).</summary>
        public void ClearCache()
        {
            _spriteCache.Clear();
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        private Sprite _tryGetFromAtlases(string spriteName)
        {
            Sprite sprite = null;

            if (_materialAtlas != null)
            {
                sprite = _materialAtlas.GetSprite(spriteName);
                if (sprite != null) return sprite;
            }

            if (_equipmentAtlas != null)
            {
                sprite = _equipmentAtlas.GetSprite(spriteName);
                if (sprite != null) return sprite;
            }

            if (_worldAtlas != null)
            {
                sprite = _worldAtlas.GetSprite(spriteName);
                if (sprite != null) return sprite;
            }

            return null;
        }

        private void OnDestroy()
        {
            if (Instance == this)
                Instance = null;
        }
    }
}
