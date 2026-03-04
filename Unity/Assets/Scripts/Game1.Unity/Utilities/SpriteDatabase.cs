// ============================================================================
// Game1.Unity.Utilities.SpriteDatabase
// Migrated from: core/image_cache.py (ImageCache singleton)
// Migration phase: 6
// Date: 2026-02-13
//
// Replaces Python's ImageCache with Unity sprite loading/caching.
// Sprites are loaded from Resources/ or SpriteAtlases.
//
// Sprite directory structure (under Assets/Resources/):
//   Sprites/Items/       ← flat folder: {itemId}.png (materials, equipment, all items)
//   Sprites/Materials/   ← materials: {materialId}.png
//   Sprites/Equipment/   ← weapons/armor/tools: {equipmentId}.png
//   Sprites/Enemies/     ← enemies: {enemyId}.png
//   Sprites/Classes/     ← class icons: {classId}.png
//   Sprites/Resources/   ← world resources: {resourceType}.png
//   Sprites/Skills/      ← skill icons: {skillId}.png
//   Sprites/UI/          ← HUD elements
//   Sprites/World/       ← tile sprites
//
// The Python source stores PNGs in Game-1-modular/assets/ with this structure:
//   assets/items/materials/{materialId}.png
//   assets/items/weapons/{itemId}.png
//   assets/items/tools/{itemId}.png
//   assets/items/armor/{itemId}.png
//   assets/enemies/{enemyId}.png
//   assets/classes/{classId}.png
//   assets/resources/{resourceNodeId}.png
//   assets/skills/{skillId}.png
//
// To set up sprites: copy PNGs from Game-1-modular/assets/ to the matching
// Resources/Sprites/ folders. File names must match item IDs exactly.
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
    /// Generates colored fallback sprites when no PNG is found.
    /// </summary>
    public class SpriteDatabase : MonoBehaviour
    {
        public static SpriteDatabase Instance { get; private set; }

        // ====================================================================
        // Inspector References
        // ====================================================================

        [Header("Sprite Atlases (Optional)")]
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
        private Sprite _generatedFallback;
        private Sprite _generatedEnemyFallback;

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

            // Generate fallback sprites if none assigned in Inspector
            if (_defaultItemSprite == null)
                _defaultItemSprite = _generateFallbackSprite(new Color(0.4f, 0.4f, 0.5f), 32);
            if (_defaultTileSprite == null)
                _defaultTileSprite = _generateFallbackSprite(new Color(0.3f, 0.5f, 0.3f), 32);
            if (_defaultEnemySprite == null)
                _defaultEnemySprite = _generateFallbackSprite(new Color(0.7f, 0.2f, 0.2f), 32);
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>
        /// Get a sprite for an item by its ID.
        /// Searches: atlases → Resources/Sprites/Items/ → Materials/ → Equipment/ → fallback.
        /// </summary>
        public Sprite GetItemSprite(string itemId)
        {
            if (string.IsNullOrEmpty(itemId)) return _defaultItemSprite;

            if (_spriteCache.TryGetValue(itemId, out var cached))
                return cached;

            // Try sprite atlases
            Sprite sprite = _tryGetFromAtlases(itemId);

            // Try flat Items folder first (user can put all item sprites here)
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Items/" + itemId);

            // Try category subfolders
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Materials/" + itemId);
            if (sprite == null)
                sprite = Resources.Load<Sprite>("Sprites/Equipment/" + itemId);

            // Cache result (even null → will use fallback)
            var result = sprite ?? _defaultItemSprite;
            _spriteCache[itemId] = result;
            return result;
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

        /// <summary>Get a class icon sprite by class ID.</summary>
        public Sprite GetClassSprite(string classId)
        {
            if (string.IsNullOrEmpty(classId)) return _defaultItemSprite;

            string key = "class_" + classId;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = Resources.Load<Sprite>("Sprites/Classes/" + classId);
            _spriteCache[key] = sprite ?? _defaultItemSprite;
            return _spriteCache[key];
        }

        /// <summary>Get a skill icon sprite by skill ID.</summary>
        public Sprite GetSkillSprite(string skillId)
        {
            if (string.IsNullOrEmpty(skillId)) return _defaultItemSprite;

            string key = "skill_" + skillId;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = Resources.Load<Sprite>("Sprites/Skills/" + skillId);
            _spriteCache[key] = sprite ?? _defaultItemSprite;
            return _spriteCache[key];
        }

        /// <summary>Get a resource node sprite by resource type.</summary>
        public Sprite GetResourceSprite(string resourceType)
        {
            if (string.IsNullOrEmpty(resourceType)) return _defaultItemSprite;

            string key = "resource_" + resourceType;
            if (_spriteCache.TryGetValue(key, out var cached))
                return cached;

            Sprite sprite = Resources.Load<Sprite>("Sprites/Resources/" + resourceType);
            _spriteCache[key] = sprite ?? _defaultItemSprite;
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

        /// <summary>
        /// Generate a simple colored square sprite as a fallback
        /// when no PNG exists. Better than invisible items.
        /// </summary>
        private static Sprite _generateFallbackSprite(Color color, int size)
        {
            var tex = new Texture2D(size, size);
            var pixels = new Color[size * size];

            // Fill with color, add a 1px darker border
            Color border = color * 0.6f;
            border.a = 1f;
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    bool isBorder = x == 0 || x == size - 1 || y == 0 || y == size - 1;
                    pixels[y * size + x] = isBorder ? border : color;
                }
            }

            tex.SetPixels(pixels);
            tex.filterMode = FilterMode.Point;
            tex.Apply();

            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size);
        }

        private void OnDestroy()
        {
            if (Instance == this)
                Instance = null;
        }
    }
}
