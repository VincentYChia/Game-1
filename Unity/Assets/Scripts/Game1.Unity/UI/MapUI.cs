// ============================================================================
// Game1.Unity.UI.MapUI
// Migrated from: rendering/renderer.py (lines 2778-3173: render_map_ui)
// Migration phase: 6
// Date: 2026-02-13
//
// World map with chunk grid, waypoints, fog of war, zoom/pan.
// Self-building: if _panel is null at Start, _buildUI() constructs the full
// UI hierarchy programmatically via UIHelper.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using TMPro;
using Game1.Core;
using Game1.Systems.World;
using Game1.Unity.Core;
using Game1.Unity.Utilities;

namespace Game1.Unity.UI
{
    /// <summary>
    /// World map panel — chunk grid, player marker, waypoints, fog of war.
    /// Supports zoom/scroll and pan.
    /// </summary>
    public class MapUI : MonoBehaviour, IScrollHandler, IDragHandler
    {
        [Header("Panel")]
        [SerializeField] private GameObject _panel;

        [Header("Map Display")]
        [SerializeField] private RawImage _mapImage;
        [SerializeField] private RectTransform _mapContainer;

        [Header("Player Marker")]
        [SerializeField] private RectTransform _playerMarker;

        [Header("Waypoint")]
        [SerializeField] private GameObject _waypointPrefab;
        [SerializeField] private Transform _waypointContainer;

        [Header("Zoom Controls")]
        [SerializeField] private Button _zoomInButton;
        [SerializeField] private Button _zoomOutButton;

        [Header("Waypoint List")]
        [SerializeField] private Transform _waypointListContainer;

        [Header("Settings")]
        [SerializeField] private float _zoomMin = 0.5f;
        [SerializeField] private float _zoomMax = 8f;
        [SerializeField] private float _zoomSpeed = 0.5f;
        [SerializeField] private int _chunkPixelSize = 24;

        private GameStateManager _stateManager;
        private InputManager _inputManager;
        private float _currentZoom = 3f;
        private Texture2D _mapTexture;
        private HashSet<Vector2Int> _exploredChunks = new HashSet<Vector2Int>();
        private Text _zoomLabel;
        private Text _coordsLabel;

        private void Start()
        {
            if (_panel == null) _buildUI();

            _stateManager = GameStateManager.Instance ?? FindFirstObjectByType<GameStateManager>();
            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();

            if (_inputManager != null) _inputManager.OnToggleMap += _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged += _onStateChanged;

            if (_zoomInButton != null)
                _zoomInButton.onClick.AddListener(() => _applyZoom(_zoomSpeed * 2f));
            if (_zoomOutButton != null)
                _zoomOutButton.onClick.AddListener(() => _applyZoom(-_zoomSpeed * 2f));

            _initializeMapTexture();
            _setVisible(false);
        }

        private void OnDestroy()
        {
            if (_inputManager != null) _inputManager.OnToggleMap -= _onToggle;
            if (_stateManager != null) _stateManager.OnStateChanged -= _onStateChanged;
            if (_mapTexture != null) Destroy(_mapTexture);
        }

        private void Update()
        {
            if (_panel == null || !_panel.activeSelf) return;

            _updatePlayerMarker();
            _updateExploredChunks();
        }

        // ====================================================================
        // Self-Building UI
        // ====================================================================

        private void _buildUI()
        {
            // Root panel — centered on screen, 600 x 550
            var panelRt = UIHelper.CreateSizedPanel(
                transform, "MapPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(600, 550), Vector2.zero);
            panelRt.anchorMin = new Vector2(0.5f, 0.5f);
            panelRt.anchorMax = new Vector2(0.5f, 0.5f);
            panelRt.pivot = new Vector2(0.5f, 0.5f);
            _panel = panelRt.gameObject;

            UIHelper.AddVerticalLayout(panelRt, spacing: 4f,
                padding: new RectOffset(8, 8, 8, 8));

            // Header: "MAP [M/ESC]"
            var (headerRow, headerTitle, headerHint) = UIHelper.CreateHeaderRow(
                panelRt, "MAP", "[M/ESC]", 40f);

            // --- Main content row: map area + waypoint sidebar ---
            var contentRowRt = UIHelper.CreatePanel(panelRt, "ContentRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            var contentLe = contentRowRt.gameObject.AddComponent<LayoutElement>();
            contentLe.flexibleHeight = 1f;
            UIHelper.AddHorizontalLayout(contentRowRt, spacing: 6f,
                padding: new RectOffset(0, 0, 0, 0));

            // --- Map area (left, takes most space) ---
            var mapAreaRt = UIHelper.CreatePanel(contentRowRt, "MapArea", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            var mapAreaLe = mapAreaRt.gameObject.AddComponent<LayoutElement>();
            mapAreaLe.flexibleWidth = 3f;
            mapAreaLe.flexibleHeight = 1f;

            // Mask for the map so it clips within bounds
            var mapMask = mapAreaRt.gameObject.AddComponent<Mask>();
            mapMask.showMaskGraphic = true;

            // Map container (zoomable/pannable)
            var mapContGo = new GameObject("MapContainer");
            mapContGo.transform.SetParent(mapAreaRt, false);
            _mapContainer = mapContGo.AddComponent<RectTransform>();
            UIHelper.StretchFill(_mapContainer);

            // RawImage for the 100x100 tile map
            var mapImgGo = new GameObject("MapImage");
            mapImgGo.transform.SetParent(_mapContainer, false);
            var mapImgRt = mapImgGo.AddComponent<RectTransform>();
            UIHelper.StretchFill(mapImgRt);
            _mapImage = mapImgGo.AddComponent<RawImage>();
            _mapImage.color = Color.white;

            // Player marker (small colored indicator)
            var markerGo = new GameObject("PlayerMarker");
            markerGo.transform.SetParent(_mapContainer, false);
            _playerMarker = markerGo.AddComponent<RectTransform>();
            _playerMarker.sizeDelta = new Vector2(8, 8);
            var markerImg = markerGo.AddComponent<Image>();
            markerImg.color = new Color(1f, 0.3f, 0.3f, 1f);
            markerImg.raycastTarget = false;

            // --- Waypoint sidebar (right) ---
            var sidebarRt = UIHelper.CreatePanel(contentRowRt, "WaypointSidebar", UIHelper.COLOR_BG_PANEL,
                Vector2.zero, Vector2.one);
            var sidebarLe = sidebarRt.gameObject.AddComponent<LayoutElement>();
            sidebarLe.flexibleWidth = 1f;
            sidebarLe.flexibleHeight = 1f;
            sidebarLe.preferredWidth = 130;

            UIHelper.AddVerticalLayout(sidebarRt, spacing: 4f,
                padding: new RectOffset(4, 4, 4, 4));

            var waypointLabel = UIHelper.CreateText(sidebarRt, "WaypointLabel", "Waypoints",
                14, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);
            UIHelper.SetPreferredHeight(waypointLabel.gameObject, 24);

            UIHelper.CreateDivider(sidebarRt, 1f);

            // Scrollable waypoint list
            var (wpScroll, wpContent) = UIHelper.CreateScrollView(sidebarRt, "WaypointScroll");
            _waypointListContainer = wpContent;
            _waypointContainer = wpContent;

            // --- Zoom controls row ---
            var zoomRowRt = UIHelper.CreatePanel(panelRt, "ZoomRow", UIHelper.COLOR_TRANSPARENT,
                Vector2.zero, Vector2.one);
            UIHelper.SetPreferredHeight(zoomRowRt.gameObject, 36);
            UIHelper.AddHorizontalLayout(zoomRowRt, spacing: 8f,
                padding: new RectOffset(8, 8, 4, 4), childForceExpand: true);

            _zoomOutButton = UIHelper.CreateButton(zoomRowRt, "ZoomOut",
                "Zoom -", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14);

            _zoomLabel = UIHelper.CreateText(zoomRowRt, "ZoomLabel", "1.0x",
                13, UIHelper.COLOR_TEXT_GOLD, TextAnchor.MiddleCenter);

            _zoomInButton = UIHelper.CreateButton(zoomRowRt, "ZoomIn",
                "Zoom +", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14);

            var centerBtn = UIHelper.CreateButton(zoomRowRt, "CenterBtn",
                "Center", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 13,
                _centerOnPlayer);

            // Coordinates display
            _coordsLabel = UIHelper.CreateText(zoomRowRt, "Coords", "",
                12, UIHelper.COLOR_TEXT_SECONDARY, TextAnchor.MiddleCenter);
        }

        // ====================================================================
        // Map Texture
        // ====================================================================

        private void _initializeMapTexture()
        {
            // Create texture for map rendering
            int texSize = 200 * _chunkPixelSize; // Enough for 200x200 chunk range
            _mapTexture = new Texture2D(texSize, texSize, TextureFormat.RGBA32, false);
            _mapTexture.filterMode = FilterMode.Point;

            // Fill with unexplored color (dark)
            Color32[] pixels = new Color32[texSize * texSize];
            for (int i = 0; i < pixels.Length; i++)
                pixels[i] = new Color32(20, 20, 20, 255);
            _mapTexture.SetPixels32(pixels);
            _mapTexture.Apply();

            if (_mapImage != null)
                _mapImage.texture = _mapTexture;
        }

        private void _updatePlayerMarker()
        {
            if (_playerMarker == null) return;

            var gm = GameManager.Instance;
            if (gm == null || gm.Player == null) return;

            var pos = gm.Player.Position;
            float mapX = (pos.X / GameConfig.ChunkSize + 100) * _chunkPixelSize;
            float mapZ = (pos.Z / GameConfig.ChunkSize + 100) * _chunkPixelSize;
            _playerMarker.anchoredPosition = new Vector2(mapX, mapZ);

            // Update coords display
            int cx = Mathf.FloorToInt(pos.X / GameConfig.ChunkSize);
            int cz = Mathf.FloorToInt(pos.Z / GameConfig.ChunkSize);
            if (_coordsLabel != null)
                _coordsLabel.text = $"Chunk ({cx}, {cz})";
        }

        private void _updateExploredChunks()
        {
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            int cx = Mathf.FloorToInt(gm.Player.Position.X / GameConfig.ChunkSize);
            int cz = Mathf.FloorToInt(gm.Player.Position.Z / GameConfig.ChunkSize);

            // Python reveals only the chunk the player is standing in (1x1)
            var coord = new Vector2Int(cx, cz);
            if (_exploredChunks.Add(coord))
            {
                _revealChunk(coord);
            }
        }

        private void _revealChunk(Vector2Int chunkCoord)
        {
            int baseX = (chunkCoord.x + 100) * _chunkPixelSize;
            int baseZ = (chunkCoord.y + 100) * _chunkPixelSize;

            // Get biome color from chunk type
            Color32 color = _getChunkColor(chunkCoord);

            for (int x = 0; x < _chunkPixelSize; x++)
            {
                for (int z = 0; z < _chunkPixelSize; z++)
                {
                    int px = baseX + x;
                    int pz = baseZ + z;

                    // Draw grid border (1px) for visual separation
                    bool isBorder = x == 0 || z == 0;

                    if (px >= 0 && px < _mapTexture.width && pz >= 0 && pz < _mapTexture.height)
                    {
                        if (isBorder)
                        {
                            // Darker border for grid lines
                            _mapTexture.SetPixel(px, pz, new Color32(
                                (byte)(color.r * 0.6f), (byte)(color.g * 0.6f),
                                (byte)(color.b * 0.6f), 255));
                        }
                        else
                        {
                            _mapTexture.SetPixel(px, pz, color);
                        }
                    }
                }
            }

            // Highlight spawn chunk (0,0) with gold border
            if (chunkCoord.x == 0 && chunkCoord.y == 0)
            {
                Color32 gold = new Color32(255, 215, 0, 255);
                for (int i = 0; i < _chunkPixelSize; i++)
                {
                    _setPixelSafe(baseX + i, baseZ, gold);
                    _setPixelSafe(baseX + i, baseZ + _chunkPixelSize - 1, gold);
                    _setPixelSafe(baseX, baseZ + i, gold);
                    _setPixelSafe(baseX + _chunkPixelSize - 1, baseZ + i, gold);
                }
            }

            _mapTexture.Apply();
        }

        private void _setPixelSafe(int x, int y, Color32 color)
        {
            if (x >= 0 && x < _mapTexture.width && y >= 0 && y < _mapTexture.height)
                _mapTexture.SetPixel(x, y, color);
        }

        private Color32 _getChunkColor(Vector2Int chunkCoord)
        {
            // Try to get actual chunk type from world system
            var gm = GameManager.Instance;
            if (gm?.World != null)
            {
                var chunk = gm.World.GetChunk(chunkCoord.x, chunkCoord.y);
                if (chunk != null)
                {
                    string chunkType = chunk.Type.ToJsonString();
                    return _biomeColor(chunkType);
                }
            }

            // Fallback: use position-based heuristic for biome variety
            int hash = chunkCoord.x * 73856093 ^ chunkCoord.y * 19349663;
            hash = hash < 0 ? -hash : hash;
            int biomeIndex = hash % 6;

            return biomeIndex switch
            {
                0 => new Color32(34, 139, 34, 255),   // Forest green
                1 => new Color32(0, 100, 0, 255),     // Dark forest
                2 => new Color32(105, 105, 105, 255), // Cave gray
                3 => new Color32(160, 82, 45, 255),   // Quarry brown
                4 => new Color32(65, 105, 225, 255),  // Water blue
                _ => new Color32(50, 205, 50, 255),   // Light green
            };
        }

        private static Color32 _biomeColor(string chunkType)
        {
            return chunkType switch
            {
                "peaceful_forest"     => new Color32(34, 139, 34, 255),
                "dangerous_forest"    => new Color32(0, 100, 0, 255),
                "rare_hidden_forest"  => new Color32(50, 205, 50, 255),
                "peaceful_cave"       => new Color32(105, 105, 105, 255),
                "dangerous_cave"      => new Color32(64, 64, 64, 255),
                "rare_deep_cave"      => new Color32(138, 43, 226, 255),
                "peaceful_quarry"     => new Color32(160, 82, 45, 255),
                "dangerous_quarry"    => new Color32(139, 69, 19, 255),
                "rare_ancient_quarry" => new Color32(255, 140, 0, 255),
                "water_lake"          => new Color32(65, 105, 225, 255),
                "water_river"         => new Color32(70, 130, 180, 255),
                "water_cursed_swamp"  => new Color32(75, 0, 130, 255),
                _                     => new Color32(34, 139, 34, 255),
            };
        }

        // ====================================================================
        // Zoom / Pan
        // ====================================================================

        private void _applyZoom(float delta)
        {
            _currentZoom = Mathf.Clamp(_currentZoom + delta, _zoomMin, _zoomMax);
            if (_mapContainer != null)
                _mapContainer.localScale = Vector3.one * _currentZoom;
            if (_zoomLabel != null)
                _zoomLabel.text = $"{_currentZoom:F1}x";
        }

        private void _centerOnPlayer()
        {
            if (_mapContainer == null) return;
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            var pos = gm.Player.Position;
            float mapX = (pos.X / GameConfig.ChunkSize + 100) * _chunkPixelSize;
            float mapZ = (pos.Z / GameConfig.ChunkSize + 100) * _chunkPixelSize;

            // Center the map so the player marker is in the middle of the view
            _mapContainer.anchoredPosition = new Vector2(
                -mapX * _currentZoom, -mapZ * _currentZoom);
        }

        public void OnScroll(PointerEventData eventData)
        {
            _applyZoom(eventData.scrollDelta.y * _zoomSpeed);
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (_mapContainer != null)
                _mapContainer.anchoredPosition += eventData.delta;
        }

        private void _onToggle() => _stateManager?.TogglePanel(GameState.MapOpen);
        private void _onStateChanged(GameState old, GameState next)
        {
            bool show = next == GameState.MapOpen;
            _setVisible(show);
            // Auto-center on player when map opens (matches Python behavior)
            if (show) _centerOnPlayer();
        }
        private void _setVisible(bool v) { if (_panel != null) _panel.SetActive(v); }
    }
}
