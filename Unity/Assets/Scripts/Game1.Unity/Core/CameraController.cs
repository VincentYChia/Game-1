// ============================================================================
// Game1.Unity.Core.CameraController
// Migrated from: core/camera.py (30 lines) + game_engine.py camera logic
// Migration phase: 6
// Date: 2026-02-13
//
// Orthographic top-down camera following the player on the XZ plane.
// 3D-ready: supports toggle to perspective mode via _orthographic flag.
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Camera controller that follows the player with smooth interpolation.
    /// Uses orthographic projection looking down at XZ plane for 2D parity.
    /// 3D-ready: toggle _orthographic to false for perspective mode.
    /// </summary>
    public class CameraController : MonoBehaviour
    {
        // ====================================================================
        // Inspector Configuration
        // ====================================================================

        [Header("Camera Mode")]
        [SerializeField] private bool _orthographic = true;
        [SerializeField] private float _orthographicSize = 8f;
        [SerializeField] private float _perspectiveFOV = 60f;
        [SerializeField] private float _cameraHeight = 50f;

        [Header("Follow")]
        [SerializeField] private float _followSpeed = 8f;
        [SerializeField] private Vector3 _offset = new Vector3(0f, 50f, 0f);

        [Header("Zoom")]
        [SerializeField] private float _minZoom = 3f;
        [SerializeField] private float _maxZoom = 15f;
        [SerializeField] private float _zoomSpeed = 2f;

        // ====================================================================
        // State
        // ====================================================================

        private Camera _camera;
        private Vector3 _targetPosition;
        private float _currentZoom;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            _camera = GetComponent<Camera>();
            if (_camera == null)
                _camera = Camera.main;

            _currentZoom = _orthographicSize;
        }

        private void Start()
        {
            if (_camera == null) return;

            // Configure camera mode
            _camera.orthographic = _orthographic;

            if (_orthographic)
            {
                _camera.orthographicSize = _orthographicSize;
                // Look straight down at XZ plane
                transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            }
            else
            {
                _camera.fieldOfView = _perspectiveFOV;
            }
        }

        // ====================================================================
        // Camera Follow (LateUpdate — after player moves)
        // ====================================================================

        private void LateUpdate()
        {
            if (_camera == null) return;

            // Smoothly follow target
            Vector3 desiredPosition = _targetPosition + _offset;
            transform.position = Vector3.Lerp(transform.position, desiredPosition, _followSpeed * Time.deltaTime);

            // Apply zoom (orthographic mode)
            if (_orthographic)
            {
                _camera.orthographicSize = Mathf.Lerp(
                    _camera.orthographicSize,
                    _currentZoom,
                    _zoomSpeed * Time.deltaTime
                );
            }
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Set the camera follow target position.</summary>
        public void SetTarget(Vector3 worldPosition)
        {
            _targetPosition = worldPosition;
        }

        /// <summary>Snap camera immediately to target (no interpolation).</summary>
        public void SnapToTarget(Vector3 worldPosition)
        {
            _targetPosition = worldPosition;
            transform.position = worldPosition + _offset;
        }

        /// <summary>
        /// Adjust zoom level. Positive delta zooms in, negative zooms out.
        /// </summary>
        public void Zoom(float delta)
        {
            _currentZoom = Mathf.Clamp(_currentZoom - delta * _zoomSpeed, _minZoom, _maxZoom);
        }

        /// <summary>Get the current visible world bounds (for chunk culling).</summary>
        public Rect GetVisibleBounds()
        {
            if (_camera == null) return new Rect(0, 0, 100, 100);

            float halfHeight = _camera.orthographicSize;
            float halfWidth = halfHeight * _camera.aspect;

            return new Rect(
                transform.position.x - halfWidth,
                transform.position.z - halfHeight,
                halfWidth * 2f,
                halfHeight * 2f
            );
        }

        /// <summary>Convert a screen point to world position on XZ plane.</summary>
        public Vector3 ScreenToWorldXZ(Vector2 screenPos)
        {
            if (_camera == null) return Vector3.zero;

            Ray ray = _camera.ScreenPointToRay(screenPos);
            var plane = new Plane(Vector3.up, Vector3.zero);
            if (plane.Raycast(ray, out float distance))
            {
                return ray.GetPoint(distance);
            }
            return Vector3.zero;
        }
    }
}
