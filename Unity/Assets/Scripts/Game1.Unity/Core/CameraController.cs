// ============================================================================
// Game1.Unity.Core.CameraController
// Migrated from: core/camera.py + game_engine.py camera logic
// Migration phase: 6 (reworked for first-person 2026-02-26)
//
// First-person camera controller. Camera is a child of the player rig.
// Reads InputManager.LookDelta directly each frame (no event dependency).
// Mouse look rotates yaw (player body) and pitch (camera head).
// ============================================================================

using UnityEngine;

namespace Game1.Unity.Core
{
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
        private Transform _playerBody;
        private float _currentPitch;
        private float _currentYaw;
        private float _bobTimer;
        private InputManager _inputManager;
        private bool _initialized;
        private bool _loggedLook; // DBG
        private float _dbgTimer; // DBG

        // ====================================================================
        // Properties
        // ====================================================================

        public float Pitch => _currentPitch;
        public float Yaw => _currentYaw;
        public Camera Camera => _camera;

        public Vector3 ForwardXZ
        {
            get
            {
                Vector3 fwd = transform.forward;
                fwd.y = 0;
                return fwd.normalized;
            }
        }

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
            Debug.Log($"[DBG:CAMERA:AWAKE] CameraController.Awake() on '{gameObject.name}', " + // DBG
                $"parent={transform.parent?.name ?? "NULL"}, " + // DBG
                $"scene={gameObject.scene.name}"); // DBG

            _camera = GetComponent<Camera>();
            if (_camera == null)
                _camera = gameObject.AddComponent<Camera>();

            Debug.Log($"[DBG:CAMERA:AWAKE:02] Camera component: {_camera != null}"); // DBG
        }

        private void Start()
        {
            Debug.Log("[DBG:CAMERA:START:01] CameraController.Start() BEGIN"); // DBG

            _inputManager = InputManager.Instance ?? FindFirstObjectByType<InputManager>();
            Debug.Log($"[DBG:CAMERA:START:02] InputManager = {(_inputManager != null ? "FOUND on " + _inputManager.gameObject.name : "NULL")}"); // DBG

            // Find player body (parent transform for yaw rotation)
            _playerBody = transform.parent;
            Debug.Log($"[DBG:CAMERA:START:03] transform.parent = {(_playerBody != null ? "'" + _playerBody.name + "'" : "NULL")}"); // DBG

            // Robust fallback: if parent is null, find or CREATE the PlayerRig.
            // This handles scenes where SceneBootstrapper didn't run (e.g. the default
            // Unity scene has a root "Main Camera" with no parent PlayerRig).
            if (_playerBody == null)
            {
                Debug.LogWarning("[DBG:CAMERA:START:03b] Parent is NULL! Attempting fallback search..."); // DBG

                // Try finding an existing PlayerController first
                var playerCtrl = FindFirstObjectByType<PlayerController>();
                if (playerCtrl != null)
                {
                    _playerBody = playerCtrl.transform;
                    Debug.LogWarning($"[DBG:CAMERA:START:03c] Found PlayerController on '{playerCtrl.gameObject.name}' — reparenting under it"); // DBG
                    transform.SetParent(_playerBody, false);
                    transform.localPosition = new Vector3(0, _eyeHeight, 0);
                    transform.localRotation = Quaternion.identity;
                }
                else
                {
                    // No PlayerRig exists at all — create one dynamically.
                    // This is the self-bootstrap path for scenes without SceneBootstrapper.
                    Debug.LogWarning("[DBG:CAMERA:START:03d] No PlayerController found — creating PlayerRig dynamically"); // DBG

                    var rigGO = new GameObject("PlayerRig");
                    // Place at world center (50,0,50) — matches GameManager auto-start position.
                    // PlayerController._syncTransform() will snap to Player.Position each frame.
                    rigGO.transform.position = new Vector3(50f, 0f, 50f);
                    Debug.Log($"[DBG:CAMERA:START:03e] PlayerRig created at {rigGO.transform.position}"); // DBG

                    // Add PlayerController (its Awake runs inline, Start runs next frame)
                    var pc = rigGO.AddComponent<PlayerController>();
                    Debug.Log($"[DBG:CAMERA:START:03f] PlayerController added to PlayerRig"); // DBG

                    // Reparent camera under the rig
                    transform.SetParent(rigGO.transform, false);
                    transform.localPosition = new Vector3(0, _eyeHeight, 0);
                    transform.localRotation = Quaternion.identity;
                    _playerBody = rigGO.transform;

                    Debug.Log($"[DBG:CAMERA:START:03g] Camera reparented. parent={transform.parent?.name}, localPos={transform.localPosition}"); // DBG
                }
            }

            // [DBG] Dump full transform chain
            { // DBG
                Transform t = transform; // DBG
                string chain = t.name; // DBG
                while (t.parent != null) // DBG
                { // DBG
                    t = t.parent; // DBG
                    chain = t.name + " > " + chain; // DBG
                } // DBG
                Debug.Log($"[DBG:CAMERA:START:04] Transform chain: {chain}"); // DBG
            } // DBG

            _setupCamera();
            _initialized = true;

            // Ensure UI canvases exist (creates them if SceneBootstrapper didn't run)
            UIBootstrap.EnsureUIExists();

            Debug.Log($"[CameraController] Start() complete. " +
                $"InputManager={_inputManager != null}, " +
                $"PlayerBody={_playerBody != null}, " +
                $"Camera={_camera != null}");

            Debug.Log($"[DBG:CAMERA:START:05] Initialized. " + // DBG
                $"eyeHeight={_eyeHeight}, fov={_fieldOfView}, " + // DBG
                $"localPos={transform.localPosition}, " + // DBG
                $"localRot={transform.localRotation.eulerAngles}"); // DBG
        }

        private void _setupCamera()
        {
            _camera.fieldOfView = _fieldOfView;
            _camera.nearClipPlane = _nearClip;
            _camera.farClipPlane = _farClip;
            _camera.orthographic = false;

            transform.localPosition = new Vector3(0, _eyeHeight, 0);
            transform.localRotation = Quaternion.identity;

            if (Camera.main == null || Camera.main == _camera)
                gameObject.tag = "MainCamera";
        }

        // ====================================================================
        // Late Update — Read Look Input & Apply Rotation
        // ====================================================================

        private void LateUpdate()
        {
            if (!_initialized) return;

            // Read look delta directly from InputManager property
            if (_inputManager != null)
            {
                Vector2 lookDelta = _inputManager.LookDelta;
                if (lookDelta.sqrMagnitude > 0.0001f)
                {
                    _currentYaw += lookDelta.x;
                    _currentYaw %= 360f; // Wrap to prevent float accumulation
                    _currentPitch += lookDelta.y;
                    _currentPitch = Mathf.Clamp(_currentPitch, _minPitch, _maxPitch);

                    if (!_loggedLook) // DBG
                    { // DBG
                        Debug.Log($"[DBG:CAMERA:LOOK] First look applied: delta={lookDelta} " + // DBG
                            $"yaw={_currentYaw:F1} pitch={_currentPitch:F1} " + // DBG
                            $"playerBody={_playerBody != null}"); // DBG
                        _loggedLook = true; // DBG
                    } // DBG
                }
            }

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
                Vector3 localPos = transform.localPosition;
                localPos.y = _eyeHeight + Mathf.Sin(_bobTimer) * _bobAmount;
                transform.localPosition = localPos;
            }

            // [DBG] Periodic state dump
            _dbgTimer += Time.deltaTime; // DBG
            if (_dbgTimer >= 2.0f) // DBG
            { // DBG
                _dbgTimer = 0f; // DBG
                Debug.Log($"[DBG:CAMERA:TICK] yaw={_currentYaw:F1} pitch={_currentPitch:F1} " + // DBG
                    $"fwd={ForwardXZ} right={RightXZ} " + // DBG
                    $"playerBody={(_playerBody != null ? _playerBody.position.ToString() : "NULL")} " + // DBG
                    $"lookDelta={(_inputManager != null ? _inputManager.LookDelta.ToString() : "no_mgr")}"); // DBG
            } // DBG
        }

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

        public void SetYaw(float yaw) => _currentYaw = yaw;

        public void SetPitch(float pitch) =>
            _currentPitch = Mathf.Clamp(pitch, _minPitch, _maxPitch);

        public void SnapOrientation(float yaw, float pitch)
        {
            _currentYaw = yaw;
            _currentPitch = Mathf.Clamp(pitch, _minPitch, _maxPitch);
            if (_playerBody != null)
                _playerBody.localRotation = Quaternion.Euler(0, _currentYaw, 0);
            transform.localRotation = Quaternion.Euler(_currentPitch, 0, 0);
        }

        public Rect GetVisibleBounds()
        {
            if (_camera == null) return new Rect(0, 0, 100, 100);

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
                    Vector3 pos = transform.position;
                    return new Rect(pos.x - 60, pos.z - 60, 120, 120);
                }
            }

            if (minX == float.MaxValue)
            {
                Vector3 pos = transform.position;
                return new Rect(pos.x - 60, pos.z - 60, 120, 120);
            }

            float padX = (maxX - minX) * 0.15f;
            float padZ = (maxZ - minZ) * 0.15f;
            return new Rect(minX - padX, minZ - padZ, maxX - minX + padX * 2, maxZ - minZ + padZ * 2);
        }

        public Vector3 ScreenToWorldXZ(Vector2 screenPos)
        {
            if (_camera == null) return Vector3.zero;
            Ray ray = _camera.ScreenPointToRay(screenPos);
            var plane = new Plane(Vector3.up, Vector3.zero);
            if (plane.Raycast(ray, out float distance))
                return ray.GetPoint(distance);
            return Vector3.zero;
        }

        public Ray GetCenterRay()
        {
            if (_camera == null) return new Ray(Vector3.zero, Vector3.forward);
            return _camera.ScreenPointToRay(new Vector3(Screen.width / 2f, Screen.height / 2f, 0));
        }
    }
}
