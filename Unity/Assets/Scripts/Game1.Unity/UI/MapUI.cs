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
        [SerializeField] private float _zoomMax = 3f;
        [SerializeField] private float _zoomSpeed = 0.2f;
        [SerializeField] private int _chunkPixelSize = 8;

        private GameStateManager _stateManager;
        private InputManager _inputManager;
        private float _currentZoom = 1f;
        private Texture2D _mapTexture;
        private HashSet<Vector2Int> _exploredChunks = new HashSet<Vector2Int>();

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
            // Root panel — right side, full height, 480px wide
            var panelRt = UIHelper.CreatePanel(transform, "MapPanel", UIHelper.COLOR_BG_DARK,
                new Vector2(1f, 0f), new Vector2(1f, 1f),
                new Vector2(-480, 0), Vector2.zero);
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

            _zoomInButton = UIHelper.CreateButton(zoomRowRt, "ZoomIn",
                "Zoom +", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14);
            _zoomOutButton = UIHelper.CreateButton(zoomRowRt, "ZoomOut",
                "Zoom -", UIHelper.COLOR_BG_BUTTON, UIHelper.COLOR_TEXT_PRIMARY, 14);

            // Coordinates display
            var coordText = UIHelper.CreateText(zoomRowRt, "Coords", "",
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
            _playerMarker.anchoredPosition = new Vector2(mapX * _currentZoom, mapZ * _currentZoom);
        }

        private void _updateExploredChunks()
        {
            var gm = GameManager.Instance;
            if (gm?.Player == null) return;

            int cx = Mathf.FloorToInt(gm.Player.Position.X / GameConfig.ChunkSize);
            int cz = Mathf.FloorToInt(gm.Player.Position.Z / GameConfig.ChunkSize);

            for (int dx = -1; dx <= 1; dx++)
            {
                for (int dz = -1; dz <= 1; dz++)
                {
                    var coord = new Vector2Int(cx + dx, cz + dz);
                    if (_exploredChunks.Add(coord))
                    {
                        _revealChunk(coord);
                    }
                }
            }
        }

        private void _revealChunk(Vector2Int chunkCoord)
        {
            int baseX = (chunkCoord.x + 100) * _chunkPixelSize;
            int baseZ = (chunkCoord.y + 100) * _chunkPixelSize;

            // Color based on biome (simplified)
            Color32 color = new Color32(34, 139, 34, 255); // Default grass

            for (int x = 0; x < _chunkPixelSize; x++)
            {
                for (int z = 0; z < _chunkPixelSize; z++)
                {
                    int px = baseX + x;
                    int pz = baseZ + z;
                    if (px >= 0 && px < _mapTexture.width && pz >= 0 && pz < _mapTexture.height)
                        _mapTexture.SetPixel(px, pz, color);
                }
            }
            _mapTexture.Apply();
        }

        // ====================================================================
        // Zoom / Pan
        // ====================================================================

        private void _applyZoom(float delta)
        {
            _currentZoom = Mathf.Clamp(_currentZoom + delta, _zoomMin, _zoomMax);
            if (_mapContainer != null)
                _mapContainer.localScale = Vector3.one * _currentZoom;
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
        private void _onStateChanged(GameState old, GameState next) => _setVisible(next == GameState.MapOpen);
        private void _setVisible(bool v) { if (_panel != null) _panel.SetActive(v); }
    }
}
