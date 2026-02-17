// ============================================================================
// Game1.Systems.Combat.AttackEffects
// Migrated from: systems/attack_effects.py (233 lines)
// Migration phase: 4
// Date: 2026-02-13
// ============================================================================
//
// Visual feedback data for combat: attack lines, blocked indicators,
// hit particles, and AoE area effects.
//
// This is LOGIC ONLY -- no rendering. The renderer reads the effect data
// and draws it. Effects fade over time and are automatically pruned.
//
// Color mapping:
//   Player  = Blue   (50, 150, 255)
//   Turret  = Cyan   (0, 220, 255)
//   Enemy   = Red    (255, 50, 50)
//   Blocked = Yellow (255, 200, 0)
//   Environment = Orange (255, 150, 50)
//
// NO MonoBehaviour, NO UnityEngine. Pure C#.
// ============================================================================

using System;
using System.Collections.Generic;
using Game1.Data.Models;

namespace Game1.Systems.Combat
{
    /// <summary>
    /// Types of attack visual effects.
    /// Python: AttackEffectType enum.
    /// </summary>
    public enum AttackEffectType
    {
        /// <summary>A line from attacker to target.</summary>
        Line,

        /// <summary>Attack blocked indicator (X mark at collision point).</summary>
        Blocked,

        /// <summary>Small particles at hit location.</summary>
        HitParticle,

        /// <summary>Circle effect for AoE attacks.</summary>
        Area
    }

    /// <summary>
    /// Source of the attack, determines color.
    /// Python: AttackSourceType enum.
    /// </summary>
    public enum AttackSourceType
    {
        /// <summary>Player attacks are blue (50, 150, 255).</summary>
        Player,

        /// <summary>Turret attacks are cyan (0, 220, 255).</summary>
        Turret,

        /// <summary>Enemy attacks are red (255, 50, 50).</summary>
        Enemy,

        /// <summary>Environment/other attacks are orange (255, 150, 50).</summary>
        Environment
    }

    /// <summary>
    /// RGBA color tuple (0-255 per channel).
    /// Pure C# replacement for Pygame/Unity Color.
    /// </summary>
    public readonly struct ColorRgba
    {
        public byte R { get; }
        public byte G { get; }
        public byte B { get; }
        public byte A { get; }

        public ColorRgba(byte r, byte g, byte b, byte a)
        {
            R = r;
            G = g;
            B = b;
            A = a;
        }
    }

    /// <summary>
    /// A visual attack effect with position, timing, and appearance data.
    /// Rendered by the UI layer; this class is logic-only.
    ///
    /// Python: @dataclass AttackEffect (lines 34-99)
    /// </summary>
    public class AttackEffect
    {
        /// <summary>Type of visual effect.</summary>
        public AttackEffectType EffectType { get; set; }

        /// <summary>Source type for color determination.</summary>
        public AttackSourceType SourceType { get; set; }

        /// <summary>Start position in world coordinates (attacker or center).</summary>
        public GamePosition StartPos { get; set; }

        /// <summary>End position in world coordinates (target, or same as start for non-lines).</summary>
        public GamePosition EndPos { get; set; }

        /// <summary>Game time when the effect was created.</summary>
        public float StartTime { get; set; }

        /// <summary>
        /// Duration in seconds before full fade out.
        /// Python: duration: float = 0.3
        /// </summary>
        public float Duration { get; set; } = 0.3f;

        /// <summary>Whether this attack was blocked.</summary>
        public bool Blocked { get; set; } = false;

        /// <summary>Damage amount (for scaling effect intensity).</summary>
        public float Damage { get; set; } = 0f;

        /// <summary>Attack tags for special effects (e.g., fire, ice).</summary>
        public List<string> Tags { get; set; } = new();

        /// <summary>
        /// Get the age of this effect in seconds relative to the given time.
        /// Python: @property age -> time.time() - self.start_time
        /// </summary>
        /// <param name="currentTime">Current game time.</param>
        /// <returns>Age in seconds.</returns>
        public float GetAge(float currentTime)
        {
            return currentTime - StartTime;
        }

        /// <summary>
        /// Get the alpha value (0.0-1.0) for fading.
        /// Quick fade-in, slow fade-out starting at 70% of duration.
        ///
        /// Python: @property alpha (lines 54-62)
        ///   fade_start = self.duration * 0.7
        ///   if age < fade_start: return 1.0
        ///   return 1.0 - ((age - fade_start) / (self.duration - fade_start))
        /// </summary>
        /// <param name="currentTime">Current game time.</param>
        /// <returns>Alpha 0.0 (invisible) to 1.0 (fully visible).</returns>
        public float GetAlpha(float currentTime)
        {
            float age = GetAge(currentTime);

            if (age >= Duration)
                return 0f;

            // Quick fade in, slow fade out
            float fadeStart = Duration * 0.7f;
            if (age < fadeStart)
                return 1.0f;

            return 1.0f - ((age - fadeStart) / (Duration - fadeStart));
        }

        /// <summary>
        /// Check if this effect should be removed.
        /// Python: @property is_expired -> self.age >= self.duration
        /// </summary>
        /// <param name="currentTime">Current game time.</param>
        /// <returns>True if effect is expired.</returns>
        public bool IsExpired(float currentTime)
        {
            return GetAge(currentTime) >= Duration;
        }

        /// <summary>
        /// Get RGBA color based on source type and blocked state.
        ///
        /// Python: get_color() (lines 69-88)
        ///   Blocked = yellow (255, 200, 0)
        ///   Player  = blue   (50, 150, 255)
        ///   Turret  = cyan   (0, 220, 255)
        ///   Enemy   = red    (255, 50, 50)
        ///   Other   = orange (255, 150, 50)
        /// </summary>
        /// <param name="currentTime">Current game time (for alpha calculation).</param>
        /// <returns>RGBA color with current alpha.</returns>
        public ColorRgba GetColor(float currentTime)
        {
            byte alpha = (byte)(GetAlpha(currentTime) * 255);

            if (Blocked)
            {
                return new ColorRgba(255, 200, 0, alpha);
            }

            return SourceType switch
            {
                AttackSourceType.Player => new ColorRgba(50, 150, 255, alpha),
                AttackSourceType.Turret => new ColorRgba(0, 220, 255, alpha),
                AttackSourceType.Enemy => new ColorRgba(255, 50, 50, alpha),
                AttackSourceType.Environment => new ColorRgba(255, 150, 50, alpha),
                _ => new ColorRgba(255, 150, 50, alpha)
            };
        }

        /// <summary>
        /// Get line width based on damage amount (scaled by alpha).
        ///
        /// Python: get_line_width() (lines 90-99)
        ///   damage > 50 -> base 4
        ///   damage > 20 -> base 3
        ///   else -> base 2
        ///   return max(1, int(base_width * self.alpha))
        /// </summary>
        /// <param name="currentTime">Current game time (for alpha).</param>
        /// <returns>Line width in pixels (1-4).</returns>
        public int GetLineWidth(float currentTime)
        {
            int baseWidth = 2;
            if (Damage > 50f)
                baseWidth = 4;
            else if (Damage > 20f)
                baseWidth = 3;

            return Math.Max(1, (int)(baseWidth * GetAlpha(currentTime)));
        }
    }

    // GamePosition is defined in Game1.Data.Models — use that canonical definition.

    /// <summary>
    /// Manages all active attack visual effects.
    /// Provides methods to add effects and query/prune active ones.
    ///
    /// Python: AttackEffectsManager (lines 102-233)
    ///
    /// Usage:
    ///   manager.AddAttackLine(sourcePos, targetPos, sourceType, damage);
    ///   manager.Update(currentTime);
    ///   var effects = manager.GetActiveEffects(currentTime);
    /// </summary>
    public class AttackEffectsManager
    {
        /// <summary>All tracked effects (including potentially expired ones).</summary>
        private readonly List<AttackEffect> _effects = new();

        /// <summary>
        /// Maximum number of effects before pruning.
        /// Python: self.max_effects = 100
        /// </summary>
        public int MaxEffects { get; set; } = 100;

        // ====================================================================
        // Add Effects
        // ====================================================================

        /// <summary>
        /// Add an attack line effect from source to target.
        /// Python: add_attack_line()
        /// </summary>
        /// <param name="sourcePos">World position of attacker.</param>
        /// <param name="targetPos">World position of target.</param>
        /// <param name="sourceType">Source type for color.</param>
        /// <param name="currentTime">Current game time.</param>
        /// <param name="damage">Damage amount for scaling.</param>
        /// <param name="blocked">Whether attack was blocked.</param>
        /// <param name="tags">Attack tags for special effects.</param>
        /// <param name="duration">Effect duration (default 0.3s).</param>
        public void AddAttackLine(GamePosition sourcePos, GamePosition targetPos,
                                  AttackSourceType sourceType, float currentTime,
                                  float damage = 0f, bool blocked = false,
                                  List<string> tags = null, float duration = 0.3f)
        {
            var effect = new AttackEffect
            {
                EffectType = AttackEffectType.Line,
                SourceType = sourceType,
                StartPos = sourcePos,
                EndPos = targetPos,
                StartTime = currentTime,
                Duration = duration,
                Blocked = blocked,
                Damage = damage,
                Tags = tags ?? new List<string>()
            };

            _addEffect(effect);
        }

        /// <summary>
        /// Add a blocked attack indicator at a position.
        /// Python: add_blocked_indicator()
        /// </summary>
        /// <param name="position">World position where attack was blocked.</param>
        /// <param name="sourceType">Source type for context.</param>
        /// <param name="currentTime">Current game time.</param>
        /// <param name="duration">Indicator duration (default 0.5s).</param>
        public void AddBlockedIndicator(GamePosition position, AttackSourceType sourceType,
                                        float currentTime, float duration = 0.5f)
        {
            var effect = new AttackEffect
            {
                EffectType = AttackEffectType.Blocked,
                SourceType = sourceType,
                StartPos = position,
                EndPos = position,
                StartTime = currentTime,
                Duration = duration,
                Blocked = true
            };

            _addEffect(effect);
        }

        /// <summary>
        /// Add an area effect indicator (for AoE attacks).
        /// Python: add_area_effect()
        ///
        /// Note: EndPos.X encodes radius (EndPos = center + (radius, 0)).
        /// This matches the Python hack: end_pos=(center_pos[0] + radius, center_pos[1]).
        /// </summary>
        /// <param name="centerPos">Center of AoE in world coordinates.</param>
        /// <param name="radius">Radius of effect in tiles.</param>
        /// <param name="sourceType">Source type for color.</param>
        /// <param name="currentTime">Current game time.</param>
        /// <param name="duration">Effect duration (default 0.4s).</param>
        public void AddAreaEffect(GamePosition centerPos, float radius,
                                  AttackSourceType sourceType, float currentTime,
                                  float duration = 0.4f)
        {
            var effect = new AttackEffect
            {
                EffectType = AttackEffectType.Area,
                SourceType = sourceType,
                StartPos = centerPos,
                EndPos = new GamePosition(centerPos.X + radius, centerPos.Y, centerPos.Z),
                StartTime = currentTime,
                Duration = duration,
                Damage = 0f,
                Tags = new List<string> { "circle" }
            };

            _addEffect(effect);
        }

        /// <summary>
        /// Get the radius from an area effect.
        /// Computed from EndPos.X - StartPos.X.
        /// </summary>
        public static float GetAreaRadius(AttackEffect effect)
        {
            return effect.EndPos.X - effect.StartPos.X;
        }

        // ====================================================================
        // Update / Query
        // ====================================================================

        /// <summary>
        /// Remove expired effects.
        /// Python: update() — self.effects = [e for e in self.effects if not e.is_expired]
        /// </summary>
        /// <param name="currentTime">Current game time.</param>
        public void Update(float currentTime)
        {
            _effects.RemoveAll(e => e.IsExpired(currentTime));
        }

        /// <summary>
        /// Get all currently active (non-expired) effects.
        /// Python: get_active_effects()
        /// </summary>
        /// <param name="currentTime">Current game time.</param>
        /// <returns>List of active effects for rendering.</returns>
        public List<AttackEffect> GetActiveEffects(float currentTime)
        {
            var active = new List<AttackEffect>();
            foreach (var effect in _effects)
            {
                if (!effect.IsExpired(currentTime))
                    active.Add(effect);
            }
            return active;
        }

        /// <summary>
        /// Get the number of active effects.
        /// </summary>
        public int ActiveCount(float currentTime)
        {
            int count = 0;
            foreach (var effect in _effects)
            {
                if (!effect.IsExpired(currentTime))
                    count++;
            }
            return count;
        }

        /// <summary>
        /// Clear all effects.
        /// Python: clear()
        /// </summary>
        public void Clear()
        {
            _effects.Clear();
        }

        // ====================================================================
        // Private
        // ====================================================================

        /// <summary>
        /// Add an effect, pruning old ones if over the max limit.
        /// Python: _add_effect()
        /// </summary>
        private void _addEffect(AttackEffect effect)
        {
            _effects.Add(effect);

            // Prune expired if over limit
            // Python: if len(self.effects) > self.max_effects:
            //             self.effects = [e for e in self.effects if not e.is_expired]
            if (_effects.Count > MaxEffects)
            {
                // Use effect's StartTime + Duration to check expiry without a currentTime param
                // This is a conservative prune -- some effects might still be alive
                float pruneTime = effect.StartTime;
                _effects.RemoveAll(e => e.IsExpired(pruneTime));
            }
        }
    }
}
