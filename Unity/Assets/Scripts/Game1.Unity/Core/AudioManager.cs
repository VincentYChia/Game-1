// ============================================================================
// Game1.Unity.Core.AudioManager
// Migrated from: N/A (placeholder — Python uses pygame.mixer)
// Migration phase: 6
// Date: 2026-02-13
//
// Placeholder audio manager. The Python version has minimal audio.
// This provides the interface for future sound effect integration.
// ============================================================================

using System.Collections.Generic;
using UnityEngine;

namespace Game1.Unity.Core
{
    /// <summary>
    /// Placeholder audio manager for sound effects and music.
    /// DontDestroyOnLoad ensures persistence across scenes.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        [Header("Audio Sources")]
        [SerializeField] private AudioSource _sfxSource;
        [SerializeField] private AudioSource _musicSource;

        [Header("Volume")]
        [SerializeField] [Range(0f, 1f)] private float _masterVolume = 1f;
        [SerializeField] [Range(0f, 1f)] private float _sfxVolume = 1f;
        [SerializeField] [Range(0f, 1f)] private float _musicVolume = 0.5f;

        private Dictionary<string, AudioClip> _clipCache = new Dictionary<string, AudioClip>();

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);

            if (_sfxSource == null)
            {
                _sfxSource = gameObject.AddComponent<AudioSource>();
                _sfxSource.playOnAwake = false;
            }

            if (_musicSource == null)
            {
                _musicSource = gameObject.AddComponent<AudioSource>();
                _musicSource.playOnAwake = false;
                _musicSource.loop = true;
            }
        }

        /// <summary>Play a one-shot sound effect.</summary>
        public void PlaySFX(AudioClip clip, float volumeScale = 1f)
        {
            if (clip == null || _sfxSource == null) return;
            _sfxSource.PlayOneShot(clip, _sfxVolume * _masterVolume * volumeScale);
        }

        /// <summary>Play a sound effect by name (loads from Resources/Audio/).</summary>
        public void PlaySFX(string clipName, float volumeScale = 1f)
        {
            if (!_clipCache.TryGetValue(clipName, out var clip))
            {
                clip = Resources.Load<AudioClip>("Audio/" + clipName);
                if (clip != null) _clipCache[clipName] = clip;
            }
            PlaySFX(clip, volumeScale);
        }

        /// <summary>Play background music.</summary>
        public void PlayMusic(AudioClip clip)
        {
            if (_musicSource == null) return;
            _musicSource.clip = clip;
            _musicSource.volume = _musicVolume * _masterVolume;
            _musicSource.Play();
        }

        /// <summary>Stop background music.</summary>
        public void StopMusic()
        {
            _musicSource?.Stop();
        }

        /// <summary>Set master volume (0-1).</summary>
        public void SetMasterVolume(float volume)
        {
            _masterVolume = Mathf.Clamp01(volume);
            if (_musicSource != null)
                _musicSource.volume = _musicVolume * _masterVolume;
        }

        private void OnDestroy()
        {
            if (Instance == this)
                Instance = null;
        }
    }
}
