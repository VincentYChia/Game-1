// ============================================================================
// Game1.Unity.Core.CameraController
// Migrated from: core/camera.py + game_engine.py camera logic
// Migration phase: 6 (upgraded for 3D rendering)
// Date: 2026-02-18
//
// Perspective camera following the player on the XZ plane at a configurable
// pitch angle. Supports smooth follow, zoom (distance), orbit rotation,
// and seamless ortho/perspective toggle for backward compatibility.
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// 3D camera controller that follows the player with smooth interpolation.
    /// Default mode: perspective at 50° pitch, orbiting the player.
    /// Supports orthographic fallback for 2D parity testing.
    /// </summary>
    public class CameraController : MonoBehaviour
    {
        // ====================================================================
        // Inspector Configuration
        // ====================================================================

        [Header("Camera Mode")]
        [SerializeField] private bool _orthographic = true;
        [SerializeField] private float _orthographicSize = 8f;
        [SerializeField] private float _perspectiveFOV = 50f;

        [Header("3D Camera Rig")]
        [Tooltip("Pitch angle in degrees (0 = horizontal, 90 = top-down)")]
        [SerializeField][Range(20f, 85f)] private float _pitch = 50f;
        [Tooltip("Yaw rotation in degrees (0 = north, 90 = east)")]
        [SerializeField] private float _yaw = 0f;
        [Tooltip("Distance from the camera to the follow target")]
        [SerializeField] private float _distance = 18f;
        [Tooltip("Vertical offset above the target pivot")]
        [SerializeField] private float _heightOffset = 1f;

        [Header("Follow")]
        [SerializeField] private float _followSpeed = 8f;
        [SerializeField] private float _rotationSmoothSpeed = 6f;

        [Header("Zoom")]
        [SerializeField] private float _minDistance = 6f;
        [SerializeField] private float _maxDistance = 40f;
        [SerializeField] private float _zoomSpeed = 3f;

        [Header("Orbit")]
        [Tooltip("Enable right-click drag to orbit camera")]
        [SerializeField] private bool _allowOrbit = true;
        [SerializeField] private float _orbitSpeed = 120f;
        [SerializeField] private float _minPitch = 20f;
        [SerializeField] private float _maxPitch = 80f;

        // ====================================================================
        // State
        // ====================================================================

        private Camera _camera;
        private Vector3 _targetPosition;
        private Vector3 _smoothedPosition;
        private float _currentDistance;
        private float _currentPitch;
        private float _currentYaw;
        private bool _isOrbiting;

        // ====================================================================
        // Properties
        // ====================================================================

        /// <summary>Whether the camera is in orthographic (2D) mode.</summary>
        public bool IsOrthographic => _orthographic;

        /// <summary>Current camera distance from target.</summary>
        public float Distance => _currentDistance;

        /// <summary>Current pitch angle.</summary>
        public float Pitch => _currentPitch;

        /// <summary>Current yaw angle.</summary>
        public float Yaw => _currentYaw;

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            _camera = GetComponent<Camera>();
            if (_camera == null)
                _camera = Camera.main;

            _currentDistance = _distance;
            _currentPitch = _pitch;
            _currentYaw = _yaw;
        }

        private void Start()
        {
            if (_camera == null) return;

            _camera.orthographic = _orthographic;

            if (_orthographic)
            {
                _camera.orthographicSize = _orthographicSize;
                transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            }
            else
            {
                _camera.fieldOfView = _perspectiveFOV;
                _camera.nearClipPlane = 0.3f;
                _camera.farClipPlane = 500f;
            }

            // Initial snap
            _smoothedPosition = _targetPosition;
            _updateCameraTransform(instant: true);
        }

        // ====================================================================
        // Camera Update (LateUpdate — after player moves)
        // ====================================================================

        private void LateUpdate()
        {
            if (_camera == null) return;

            if (_orthographic)
            {
                _updateOrthographic();
            }
            else
            {
                _updatePerspective();
            }
        }

        private void _updateOrthographic()
        {
            Vector3 desiredPosition = _targetPosition + new Vector3(0f, 50f, 0f);
            transform.position = Vector3.Lerp(transform.position, desiredPosition, _followSpeed * Time.deltaTime);

            _camera.orthographicSize = Mathf.Lerp(
                _camera.orthographicSize,
                _currentDistance,
                _zoomSpeed * Time.deltaTime
            );
        }

        private void _updatePerspective()
        {
            // Smooth follow position
            _smoothedPosition = Vector3.Lerp(
                _smoothedPosition,
                _targetPosition,
                _followSpeed * Time.deltaTime
            );

            // Smooth pitch/yaw interpolation
            _currentPitch = Mathf.Lerp(_currentPitch, _pitch, _rotationSmoothSpeed * Time.deltaTime);
            _currentYaw = Mathf.Lerp(_currentYaw, _yaw, _rotationSmoothSpeed * Time.deltaTime);
            _currentDistance = Mathf.Lerp(_currentDistance, _distance, _zoomSpeed * Time.deltaTime);

            _updateCameraTransform(instant: false);
        }

        private void _updateCameraTransform(bool instant)
        {
            Vector3 pivot = (instant ? _targetPosition : _smoothedPosition)
                          + new Vector3(0f, _heightOffset, 0f);

            // Spherical coordinates: distance + pitch + yaw → position offset
            float pitchRad = _currentPitch * Mathf.Deg2Rad;
            float yawRad = _currentYaw * Mathf.Deg2Rad;

            float horizontalDist = _currentDistance * Mathf.Cos(pitchRad);
            float verticalDist = _currentDistance * Mathf.Sin(pitchRad);

            Vector3 offset = new Vector3(
                -horizontalDist * Mathf.Sin(yawRad),
                verticalDist,
                -horizontalDist * Mathf.Cos(yawRad)
            );

            Vector3 desiredPos = pivot + offset;

            if (instant)
            {
                transform.position = desiredPos;
            }
            else
            {
                transform.position = desiredPos;
            }

            // Always look at pivot
            transform.LookAt(pivot);
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
            _smoothedPosition = worldPosition;
            _updateCameraTransform(instant: true);
        }

        /// <summary>Adjust zoom level. Positive delta zooms in, negative zooms out.</summary>
        public void Zoom(float delta)
        {
            if (_orthographic)
            {
                _currentDistance = Mathf.Clamp(_currentDistance - delta * _zoomSpeed, _minDistance, _maxDistance);
            }
            else
            {
                _distance = Mathf.Clamp(_distance - delta * _zoomSpeed, _minDistance, _maxDistance);
            }
        }

        /// <summary>Orbit the camera around the target (horizontal rotation).</summary>
        public void OrbitHorizontal(float delta)
        {
            if (!_allowOrbit) return;
            _yaw += delta * _orbitSpeed * Time.deltaTime;
            // Wrap yaw to 0-360
            if (_yaw < 0f) _yaw += 360f;
            if (_yaw >= 360f) _yaw -= 360f;
        }

        /// <summary>Orbit the camera vertically (change pitch).</summary>
        public void OrbitVertical(float delta)
        {
            if (!_allowOrbit) return;
            _pitch = Mathf.Clamp(_pitch - delta * _orbitSpeed * Time.deltaTime, _minPitch, _maxPitch);
        }

        /// <summary>Reset camera to default orientation.</summary>
        public void ResetOrientation()
        {
            _yaw = 0f;
            _pitch = 50f;
            _distance = 18f;
        }

        /// <summary>Toggle between orthographic and perspective modes.</summary>
        public void ToggleCameraMode()
        {
            _orthographic = !_orthographic;
            if (_camera != null)
            {
                _camera.orthographic = _orthographic;
                if (_orthographic)
                {
                    _camera.orthographicSize = _orthographicSize;
                    transform.rotation = Quaternion.Euler(90f, 0f, 0f);
                }
                else
                {
                    _camera.fieldOfView = _perspectiveFOV;
                    _updateCameraTransform(instant: true);
                }
            }
        }

        /// <summary>Get the current visible world bounds (for chunk culling).</summary>
        public Rect GetVisibleBounds()
        {
            if (_camera == null) return new Rect(0, 0, 100, 100);

            if (_orthographic)
            {
                float halfHeight = _camera.orthographicSize;
                float halfWidth = halfHeight * _camera.aspect;
                return new Rect(
                    transform.position.x - halfWidth,
                    transform.position.z - halfHeight,
                    halfWidth * 2f,
                    halfHeight * 2f
                );
            }

            // Perspective: compute approximate ground-plane footprint
            // Cast rays from the 4 screen corners to the ground plane (Y=0)
            var plane = new Plane(Vector3.up, Vector3.zero);

            float minX = float.MaxValue, maxX = float.MinValue;
            float minZ = float.MaxValue, maxZ = float.MinValue;

            Vector2[] corners = {
                new Vector2(0, 0),
                new Vector2(Screen.width, 0),
                new Vector2(0, Screen.height),
                new Vector2(Screen.width, Screen.height)
            };

            foreach (var corner in corners)
            {
                Ray ray = _camera.ScreenPointToRay(corner);
                if (plane.Raycast(ray, out float dist))
                {
                    Vector3 hit = ray.GetPoint(dist);
                    minX = Mathf.Min(minX, hit.x);
                    maxX = Mathf.Max(maxX, hit.x);
                    minZ = Mathf.Min(minZ, hit.z);
                    maxZ = Mathf.Max(maxZ, hit.z);
                }
            }

            if (minX == float.MaxValue) return new Rect(0, 0, 100, 100);
            return new Rect(minX, minZ, maxX - minX, maxZ - minZ);
        }

        /// <summary>Convert a screen point to world position on XZ plane (Y=0).</summary>
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
