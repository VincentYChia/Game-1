// ============================================================================
// Game1.Unity.Core.CameraController
// Migrated from: core/camera.py + game_engine.py camera logic
// Migration phase: 6 (reworked for first-person 2026-02-25)
//
// First-person camera controller. Camera is a child of the player rig.
// Mouse look rotates yaw (player body) and pitch (camera head).
// Supports cursor lock/unlock for UI interaction.
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// First-person camera controller. Attached to the Camera GameObject
    /// which is a child of the player rig. Mouse look rotates the player
    /// body (yaw) and the camera (pitch). Like Minecraft's first-person view.
    /// </summary>
    public class CameraController : MonoBehaviour
    {
        // ====================================================================
        // Inspector Configuration
        // ====================================================================

        [Header("Camera Settings")]
        [SerializeField] private float _fieldOfView = 70f;
        [SerializeField] private float _nearClip = 0.1f;
        [SerializeField] private float _farClip = 500f;

        [Header("Look Settings")]
        [SerializeField] private float _minPitch = -89f;
        [SerializeField] private float _maxPitch = 89f;

        [Header("Camera Position")]
        [Tooltip("Height of the camera above the player pivot (eye level)")]
        [SerializeField] private float _eyeHeight = 1.6f;

        [Header("Head Bob (optional)")]
        [SerializeField] private bool _enableHeadBob = false;
        [SerializeField] private float _bobSpeed = 10f;
        [SerializeField] private float _bobAmount = 0.03f;

        // ====================================================================
        // State
        // ====================================================================

        private Camera _camera;
        private Transform _playerBody; // The parent that rotates on yaw
        private float _currentPitch;
        private float _currentYaw;
        private float _bobTimer;
        private InputManager _inputManager;
        private bool _initialized;

        // ====================================================================
        // Properties
        // ====================================================================

        /// <summary>Current pitch angle (up/down).</summary>
        public float Pitch => _currentPitch;

        /// <summary>Current yaw angle (left/right).</summary>
        public float Yaw => _currentYaw;

        /// <summary>The camera component.</summary>
        public Camera Camera => _camera;

        /// <summary>Forward direction on XZ plane (for movement).</summary>
        public Vector3 ForwardXZ
        {
            get
            {
                Vector3 fwd = transform.forward;
                fwd.y = 0;
                return fwd.normalized;
            }
        }

        /// <summary>Right direction on XZ plane (for movement).</summary>
        public Vector3 RightXZ
        {
            get
            {
                Vector3 right = transform.right;
                right.y = 0;
                return right.normalized;
            }
        }

        // ====================================================================
        // Initialization
        // ====================================================================

        private void Awake()
        {
            _camera = GetComponent<Camera>();
            if (_camera == null)
                _camera = gameObject.AddComponent<Camera>();
        }

        private void Start()
        {
            _inputManager = FindFirstObjectByType<InputManager>();
            if (_inputManager != null)
                _inputManager.OnMouseLook += _onMouseLook;

            _playerBody = transform.parent;

            _setupCamera();
            _initialized = true;
        }

        private void OnDestroy()
        {
            if (_inputManager != null)
                _inputManager.OnMouseLook -= _onMouseLook;
        }

        private void _setupCamera()
        {
            _camera.fieldOfView = _fieldOfView;
            _camera.nearClipPlane = _nearClip;
            _camera.farClipPlane = _farClip;
            _camera.orthographic = false;

            // Position camera at eye level relative to player
            transform.localPosition = new Vector3(0, _eyeHeight, 0);
            transform.localRotation = Quaternion.identity;

            // Tag as MainCamera if no other exists
            if (Camera.main == null || Camera.main == _camera)
                gameObject.tag = "MainCamera";
        }

        // ====================================================================
        // Mouse Look
        // ====================================================================

        private void _onMouseLook(Vector2 lookDelta)
        {
            // Yaw: rotate the player body (or this object's parent)
            _currentYaw += lookDelta.x;

            // Pitch: rotate the camera up/down
            _currentPitch += lookDelta.y;
            _currentPitch = Mathf.Clamp(_currentPitch, _minPitch, _maxPitch);
        }

        // ====================================================================
        // Late Update — Apply Rotation
        // ====================================================================

        private void LateUpdate()
        {
            if (!_initialized) return;

            // Apply yaw to player body (parent)
            if (_playerBody != null)
            {
                _playerBody.localRotation = Quaternion.Euler(0, _currentYaw, 0);
            }

            // Apply pitch to camera (this transform)
            transform.localRotation = Quaternion.Euler(_currentPitch, 0, 0);

            // Head bob while moving
            if (_enableHeadBob)
            {
                var gm = GameManager.Instance;
                if (gm != null && gm.Player != null)
                {
                    // Simple bob based on movement (approximated)
                    Vector3 localPos = transform.localPosition;
                    localPos.y = _eyeHeight + Mathf.Sin(_bobTimer) * _bobAmount;
                    transform.localPosition = localPos;
                }
            }
        }

        /// <summary>Call from PlayerController when player is moving to drive head bob.</summary>
        public void NotifyMoving(bool isMoving)
        {
            if (isMoving && _enableHeadBob)
                _bobTimer += Time.deltaTime * _bobSpeed;
            else
                _bobTimer = 0;
        }

        // ====================================================================
        // Public API
        // ====================================================================

        /// <summary>Set the camera yaw directly (e.g., for teleport).</summary>
        public void SetYaw(float yaw)
        {
            _currentYaw = yaw;
        }

        /// <summary>Set the camera pitch directly.</summary>
        public void SetPitch(float pitch)
        {
            _currentPitch = Mathf.Clamp(pitch, _minPitch, _maxPitch);
        }

        /// <summary>Snap both yaw and pitch.</summary>
        public void SnapOrientation(float yaw, float pitch)
        {
            _currentYaw = yaw;
            _currentPitch = Mathf.Clamp(pitch, _minPitch, _maxPitch);

            if (_playerBody != null)
                _playerBody.localRotation = Quaternion.Euler(0, _currentYaw, 0);
            transform.localRotation = Quaternion.Euler(_currentPitch, 0, 0);
        }

        /// <summary>Get the current visible world bounds (for chunk culling).</summary>
        public Rect GetVisibleBounds()
        {
            if (_camera == null) return new Rect(0, 0, 100, 100);

            // Perspective: compute approximate ground-plane footprint
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
                else
                {
                    // Ray doesn't hit ground (looking up) — use a generous default
                    Vector3 pos = transform.position;
                    return new Rect(pos.x - 60, pos.z - 60, 120, 120);
                }
            }

            if (minX == float.MaxValue)
            {
                Vector3 pos = transform.position;
                return new Rect(pos.x - 60, pos.z - 60, 120, 120);
            }

            // Add padding
            float padX = (maxX - minX) * 0.15f;
            float padZ = (maxZ - minZ) * 0.15f;
            return new Rect(minX - padX, minZ - padZ, maxX - minX + padX * 2, maxZ - minZ + padZ * 2);
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

        /// <summary>Get the forward ray from camera center (for first-person targeting).</summary>
        public Ray GetCenterRay()
        {
            if (_camera == null) return new Ray(Vector3.zero, Vector3.forward);
            return _camera.ScreenPointToRay(new Vector3(Screen.width / 2f, Screen.height / 2f, 0));
        }
    }
}
