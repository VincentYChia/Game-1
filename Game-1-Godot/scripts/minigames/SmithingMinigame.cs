using Godot;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace Game1.Godot;

/// <summary>
/// SMITHING â€” "Forge Rush" â€” a top-down StarCraft-2-style micro-battle (master plan Â§3.1). You command a HERO
/// forged from the recipe and survive an enemy WAVE. Recipe KNOWLEDGE is your loadout: ingredient tags grant/tier
/// hero abilities (precedence 4/3/2/1; tier => ability rank) and some tags spawn controllable allies; OUTPUT tags set
/// the enemy wave character. The minigame itself is pure MICRO â€” positioning (right-click move), ability timing
/// (Q/W/E at the cursor, R passive), and ally control (left-click select/command). Difficulty scales intensity;
/// tags scale character. perf âˆˆ [PERF_FLOOR,1] flows through the certified seam (Finish); Game1.Core is 0-diff.
///
/// Everything is drawn PROCEDURALLY from CraftFx / CraftColor / StateVisual primitives â€” no raster PNG assets â€” so
/// the game renders + plays before any art exists (Â§6, Â§9-R3). FullscreenScene owns the whole viewport.
///
/// This is a FULL REWRITE of the old "Draw &amp; Temper" mechanic; only the class shell + Discipline key are kept.
/// The doc it transcribes (SMITHING_IMPLEMENTATION.md) required inventing nothing: every constant, table, formula,
/// layout rect and colour below is taken verbatim from that doc. Private members of the shared toolkit are NOT
/// touched â€” the small tables MinigameTagEffects keeps private are DUPLICATED here as SmithingMinigame statics
/// (ThemeTag / SmithModTable / SmithChExc / â€¦ / the 7 ThemeColor HSV constants), keeping the shared toolkit 0-diff.
/// </summary>
public partial class SmithingMinigame : MinigameOverlay
{
    protected override string Discipline => "smithing";
    protected override bool FullscreenScene => true;
    protected override bool ShowAmbient => true;
    // Forge theme â€” warm arena (CraftStyle["smithing"] Top/Bottom/Glow, Â§6).
    protected override (Color, Color, Color)? BackdropTint =>
        (new Color(0.16f, 0.09f, 0.06f), new Color(0.03f, 0.02f, 0.02f), new Color(1f, 0.48f, 0.14f));

    // ============================================================ Â§1 DATA MODEL

    private enum Phase { Ready, Countdown, Play, Settle, Done }              // Â§3 state machine
    internal enum Theme { Fire, Water, Ice, Earth, Life, Shadow, Air }       // 7 elemental themes (index 0..6) â€” internal: the internal ThemeTag dict exposes it
    private enum AbilitySlot { Q = 0, W = 1, E = 2, R = 3 }                  // 3 active + 1 passive
    private enum AbilityKind
    {
        None,
        Nuke,        // FIRE  â€” AoE burst at cursor
        SlowField,   // ICE   â€” radial slow/root zone
        Bulwark,     // EARTH â€” hero shield + taunt pull
        Rally,       // LIFE  â€” spawn/heal an ally
        Leech,       // SHADOWâ€” lifesteal nova, self-risk
        Blink,       // AIR   â€” dash + brief haste
        Torrent,     // WATER â€” heal-over-time flow + cleanse hero debuffs
        PassiveCrit, // sharp rider â†’ +crit on hero autos
        PassiveRegen // life/water rider â†’ hero HP regen
    }
    private enum AllyKind { None, Sprout, Guardian }                        // Sprout=LIFE dps, Guardian=EARTH tank
    private enum EnemyKind { Rusher, Bruiser }                              // wave character from output tags
    private enum UnitTeam { Hero, Ally, Enemy }

    // Â§1.2 Unit (the lightweight non-physics actor)
    private sealed class Unit
    {
        public UnitTeam Team;
        public EnemyKind EKind;
        public AllyKind AKind;
        public Vector2 Pos;
        public Vector2 Vel;
        public float Facing;
        public float Radius;
        public float Hp;
        public float HpMax;
        public float MoveSpeed;
        public float Damage;
        public float AttackCd;
        public float AttackTimer;
        public float Shield;
        public float SlowUntil;
        public float SlowFactor = 1f;
        public float Phased;
        public float HitFlash;
        public float SpawnT;
        public bool Alive => Hp > 0;
        public int Seed;
        public bool IsMiniBoss;
        public Vector2 PrevPos;   // for the Blink wake trail (Â§6.3)

        // --- projectile-combat attributes (playtest rework: projectiles + readable animations) ---
        public float Range;             // px â€” attack range (ranged units big, melee-ish units tiny)
        public float ProjSpeed;         // px/s â€” projectile travel speed (fast for melee strikes, slow for lobs)
        public float SplashRadius;      // px â€” >0 => this unit's projectiles deal AoE splash on impact (tag-driven)
        public Theme Tint;              // colour source for this unit's projectiles/telegraph
        public float Windup;            // s remaining in the pre-fire telegraph (lean/flash); 0 = not winding up
        public float WindupLen;         // s â€” full windup length (for the telegraph draw ramp)
        public Vector2 AimAt;           // world point the windup is aimed at (locked when the windup starts)
        public Unit? AimTarget;         // the unit the windup is tracking (null => fixed-point strike)
        public float MuzzleFlash;       // 0..1 fades out â€” a bright flash at the barrel the frame a shot fires

        // --- selection + command state (SC2 micro) â€” only meaningful for Hero/Ally units ---
        public bool Selected;           // in the current selection group (drawn with a selection bracket)
        public CmdMode Cmd;             // active order kind
        public Vector2 CmdPoint;        // move / attack-move destination
        public Unit? CmdFocus;          // right-click-on-enemy focus-fire target (cleared when it dies)
    }

    private enum CmdMode { None, Move, AttackMove }

    // Â§1.3 Ability
    private sealed class Ability
    {
        public AbilitySlot Slot;
        public AbilityKind Kind;
        public int Rank = 1;
        public Theme Source;
        public float Cooldown;
        public float CdTimer;
        public float Radius;
        public float Magnitude;
        public float Duration;
        public bool Targeted;
        public string Label = "";
        public bool Ready => CdTimer <= 0 && Kind != AbilityKind.None;
    }

    // Â§1.4 Active effect + hero buffs
    private struct FieldEffect
    {
        public AbilityKind Kind;
        public Vector2 Pos;
        public float Radius;
        public float Magnitude;
        public float Until;
        public float Started;
        public Theme Source;
    }
    private struct HeroBuff
    {
        public float HasteUntil; public float HasteMul;
        public float RegenUntil; public float RegenPerS;
        public float CritChance;
        public float LeechFrac;
        public float LeechUntil;
    }

    // Â§1.4b Projectile â€” the core of the playtest rework. Every UNIT auto-attack now spawns one of these; damage is
    // applied ON IMPACT (finite travel time), so range + reload speed + travel are all READABLE. Ability casts stay
    // instant (they have their own VFX). Homing is soft: the shot re-aims at a living target each tick but keeps flying
    // to the last-seen point if that target dies, so it never stalls.
    private sealed class Projectile
    {
        public UnitTeam Team;           // who fired it (Hero/Ally hit Enemies; Enemy hits Hero/Allies)
        public Vector2 Pos;
        public Vector2 Vel;
        public Vector2 Target;          // current aim point (updated toward AimTarget while it lives)
        public Unit? AimTarget;         // soft-homing target (may die mid-flight)
        public float Speed;
        public float Damage;
        public float Radius;            // visual size
        public float SplashRadius;      // >0 => AoE on impact
        public bool Crit;
        public bool Leech;              // hero-sourced + leech window => heals hero for HP removed
        public bool Toxic;              // applies the enemy DoT on impact
        public Theme Tint;
        public float Life;              // s alive (auto-expires if it never connects)
        public Vector2 PrevPos;         // for the tracer trail
    }

    // Â§1.5 Loadout
    private sealed class Loadout
    {
        public Ability[] Abilities = new Ability[4];
        public List<(AllyKind Kind, int Rank)> StartAllies = new();
        public Theme HeroTheme;
        public float HeroHpBonus;
        public float HeroDamageMul = 1f;
    }

    // Â§1.6 Wave
    private sealed class Wave
    {
        public Theme Character;
        public float Duration;
        public int TotalToSpawn;
        public float SpawnInterval;
        public float EnemyHpMul = 1f;
        public float EnemyDmgMul = 1f;
        public float RusherFrac = 0.5f;
        public bool SecondWave;
        public bool MiniBoss;
        public int Spawned;
        public float NextSpawnAt;
        public float SpawnJitterAmp = 1f;   // Fire character rider Ã—1.4 (Â§4.2)
        public float EvasiveAmp = 1f;       // Air/Shadow wander amp (Â§4.4)
        public bool SecondWaveTriggered;
        public bool MiniBossSpawned;
    }

    // Â§1.7 Root play state
    private Phase _phase;
    private double _clock;
    private double _countdown;
    private double _anim;
    private Loadout _loadout = new();
    private Wave _wave = new();
    private Unit _hero = new();
    private readonly List<Unit> _allies = new();
    private readonly List<Unit> _enemies = new();
    private readonly List<FieldEffect> _fields = new();
    private readonly List<Projectile> _projectiles = new();
    private HeroBuff _heroBuff;
    private Vector2 _cursor;
    private Vector2 _moveTarget;
    private bool _hasMoveTarget;
    private Rect2 _arenaRect;

    // --- SC2 selection + command state (playtest rework) ---
    private bool _boxDragging;        // left-drag selection box in progress
    private Vector2 _boxStart;        // drag anchor (world)
    private Vector2 _boxCur;          // drag current (world)
    private bool _attackMoveArmed;    // 'A' pressed â†’ next left-click issues an attack-move
    private struct CmdPing { public Vector2 Pos; public float Until; public Color Col; public bool Attack; }
    private readonly List<CmdPing> _pings = new();
    private const float SELECT_DRAG_MIN = 8f;   // px drag distance before a click becomes a box
    private const float CMD_PING_DUR = 0.55f;

    // --- COSMETIC ONLY: a themed death-dissolve marker per fallen unit (a shrinking body ghost + a themed ring). This
    // is pure VFX drawn over a couple of frames after a unit is culled; it holds no HP / stats and NEVER feeds scoring
    // or the sim (CullDead already applied the kill). Kept off the tight sim loops â€” appended on cull, drawn + expired
    // in the draw pass' companion list. Capacity is naturally bounded by the enemy/ally caps + short lifetime.
    private struct DeathFx { public Vector2 Pos; public float Radius; public float Until; public float Born; public Color Col; public bool Big; public bool Enemy; }
    private readonly List<DeathFx> _deaths = new();
    private const float DEATH_FX_DUR = 0.42f;

    // --- COSMETIC ONLY: draw-pass impact rings. Projectile impacts resolve inside the SIM tick (TickProjectiles), so
    // immediate-mode ring draws there would be no-ops; instead an impact queues a short-lived ring here that the draw
    // pass expands + fades. Holds no gameplay state; capacity-capped; expired in UpdatePlay next to pings/deaths.
    private struct ImpactRing { public Vector2 Pos; public float BaseR; public float Until; public float Born; public Color Col; public float Width; public float Spread; }
    private readonly List<ImpactRing> _impacts = new();
    private const float IMPACT_RING_DUR = 0.3f;

    // Â§4.6 scoring accumulators
    private float _heroDmgDealt;
    private int _enemiesKilled;
    private int _enemiesTotal;
    private float _squadHpMaxTotal;   // starting hero+allies max HP â€” denominator of the squad-survival score
    private int _abilitiesCast;
    private int _abilitiesLandedValue;
    private bool _heroDied;
    private double _lowestHpFrac = 1.0;

    // toxic DoT bookkeeping (per-enemy, Â§2.1 toxic row): (enemy, dmgPerS, until)
    private readonly List<(Unit U, float Dps, float Until)> _poison = new();
    private bool _hasToxic;
    private bool _heroSplash;   // loadout tags imply AoE â†’ hero + allies fire splash projectiles
    private bool _waveSplash;   // wave (output) tags imply AoE â†’ enemies fire splash projectiles

    private MinigameDevLog _dev = null!;

    private System.Random _rng = new(0);
    private int _rankJitter;   // chaos Â±1 (Â§8), applied per ability build

    private bool _finished;
    private double _settleT;
    private double _perf;

    // pending spawn telegraphs (Â§6.6 / Â§8): the exact future spawn point drawn SPAWN_TELL before the unit exists
    private struct Telegraph { public Vector2 Pos; public float At; public bool Boss; public EnemyKind Kind; }
    private readonly List<Telegraph> _telegraphs = new();

    private Control _arena = null!;
    private Control _abilityBarCtl = null!;

    // ============================================================ Â§4 CONSTANTS

    private const float ARENA_MARGIN = 0.06f;
    private const float HERO_HP0 = 300f;
    private const float HERO_SPD = 210f;
    private const float HERO_DMG0 = 18f;
    private const float HERO_ATTACK_CD = 0.55f;
    private const float HERO_RANGE = 120f;
    private const float SEP_RADIUS_MUL = 2.2f;
    private const float SEP_FORCE = 260f;
    private const float ATK_REACH = 6f;
    private const float EVASIVE = 18f;
    private const float ALLY_AGGRO = 260f;
    private const float SPAWN_TELL = 0.6f;
    private const float BOSS_TELL = 1.5f;
    private const float BLINK_LOOKAHEAD = 0.4f;
    private const float POISON_DPS = 6f;
    private const float POISON_DUR = 2f;
    private const int BASE_ENEMIES = 4;
    private const int MAX_ENEMIES_LIVE = 24;
    private const int MAX_ALLIES = 6;
    private const int MAX_FIELDS = 8;
    private const int MAX_START_ALLIES = 2;
    private const float GUARDIAN_HP_FALLBACK = 30f;
    private const float SPROUT_HP_FALLBACK = 20f;

    private const float EN_RUSH_HP = 42f;
    private const float EN_BRUI_HP = 120f;

    // --- projectile-combat tuning (playtest rework) ---
    private const float WINDUP_HERO = 0.14f;   // s telegraph before the hero fires (readable lean/flash)
    private const float WINDUP_RANGED = 0.16f; // s telegraph for ranged units (sprout / ranged enemies)
    private const float WINDUP_MELEE = 0.10f;  // s telegraph for melee-ish units (short, snappy strike)
    private const float PROJ_MAX_LIFE = 2.2f;  // s a projectile lives before auto-expiring (prevents strays)
    private const float PROJ_HIT_PAD = 5f;     // px added to target radius for the impact test
    private const int MAX_PROJECTILES = 96;    // hard cap on live projectiles (frame budget)
    // per-archetype ranged profile: (range px, projectile speed px/s). Melee-ish = short range + fast strike.
    private const float RUSH_RANGE = 40f, RUSH_PROJ = 640f;    // rusher = a fast short lunge-strike
    private const float BRUI_RANGE = 58f, BRUI_PROJ = 300f;    // bruiser = heavy slow close-range swing
    private const float SPROUT_RANGE = 150f, SPROUT_PROJ = 460f; // sprout = a ranged spitter (life bolt)
    private const float GUARD_RANGE = 46f, GUARD_PROJ = 520f;  // guardian = short melee shield-bash
    private const float HERO_PROJ = 520f;                       // hero bolt speed (HERO_RANGE already 120)
    private const float SPLASH_RADIUS = 48f;                    // impact splash radius for AoE-tagged units

    private const double PERF_FLOOR = 0.05;
    private const double FAILCRAFT_FLOOR = 0.0;   // disabled by default â†’ always Finish, never FailCraft (Â§3)

    // Forge palette (Â§6): accent/glow/ember.
    private static readonly Color Accent2 = new(0.98f, 0.55f, 0.32f);   // #FA8C52
    private static readonly Color GlowCol = new(1f, 0.478f, 0.14f);      // #FF7A24
    private static readonly Color EmberCol = new(1f, 0.6f, 0.22f);       // #FF9938
    private static readonly Color Ink = new(0.95f, 0.92f, 0.86f);
    private static readonly Color Sub = new(0.95f, 0.92f, 0.86f, 0.6f);
    private static readonly Color AllyGreen = new(0.42f, 1f, 0.42f);    // #6CFF6C
    private static readonly Color LowRed = new(1f, 0.3f, 0.25f);

    // Â§6.0 ThemeColor â€” the 7 self-contained HSV constants (indexed by (int)Theme).
    private static readonly Color[] ThemeColors =
    {
        Color.FromHsv(0.03f, 0.85f, 1.00f),   // Fire   â€” red-orange
        Color.FromHsv(0.57f, 0.72f, 0.98f),   // Water  â€” blue
        Color.FromHsv(0.53f, 0.35f, 1.00f),   // Ice    â€” pale cyan
        Color.FromHsv(0.09f, 0.55f, 0.80f),   // Earth  â€” earthy gold
        Color.FromHsv(0.32f, 0.66f, 0.85f),   // Life   â€” green
        Color.FromHsv(0.78f, 0.60f, 0.85f),   // Shadow â€” violet
        Color.FromHsv(0.53f, 0.20f, 0.98f),   // Air    â€” near-white cyan
    };
    private static Color ThemeColor(Theme t) => ThemeColors[(int)t];

    // ================================================= Â§2.3 RESOLUTION TABLES

    // tag â†’ Theme (the seven bodies). Anything absent is a pure rider.
    internal static readonly Dictionary<string, Theme> ThemeTag = new()
    {
        // FIRE bodies (energetic riders lightning/storm/radiant/light/chaos are deliberately absent â€” riders, not bodies)
        ["fire"] = Theme.Fire, ["flame"] = Theme.Fire, ["ember"] = Theme.Fire, ["molten"] = Theme.Fire,
        ["forge"] = Theme.Fire, ["volcanic"] = Theme.Fire,
        // WATER
        ["water"] = Theme.Water, ["aqua"] = Theme.Water, ["liquid"] = Theme.Water, ["solvent"] = Theme.Water,
        // ICE (the AQUA cold-split, pre-resolved)
        ["ice"] = Theme.Ice, ["frost"] = Theme.Ice, ["frozen"] = Theme.Ice, ["chill"] = Theme.Ice,
        // EARTH (elemental earth + all structural metals + crystal/gem)
        ["earth"] = Theme.Earth, ["stone"] = Theme.Earth, ["sand"] = Theme.Earth, ["mineral"] = Theme.Earth,
        ["metal"] = Theme.Earth, ["metallic"] = Theme.Earth, ["iron"] = Theme.Earth, ["steel"] = Theme.Earth,
        ["bronze"] = Theme.Earth, ["copper"] = Theme.Earth, ["tin"] = Theme.Earth, ["mithril"] = Theme.Earth,
        ["adamantine"] = Theme.Earth, ["silver"] = Theme.Earth, ["gold"] = Theme.Earth, ["orichalcum"] = Theme.Earth,
        ["alloy"] = Theme.Earth, ["crystal"] = Theme.Earth, ["gem"] = Theme.Earth,
        // LIFE (elemental life + all wood species + feral)
        ["wood"] = Theme.Life, ["oak"] = Theme.Life, ["ash"] = Theme.Life, ["ironwood"] = Theme.Life,
        ["ebony"] = Theme.Life, ["birch"] = Theme.Life, ["willow"] = Theme.Life, ["worldtree"] = Theme.Life,
        ["exotic"] = Theme.Life, ["plant"] = Theme.Life, ["herb"] = Theme.Life, ["leather"] = Theme.Life,
        ["living"] = Theme.Life, ["monster"] = Theme.Life, ["fang"] = Theme.Life, ["scales"] = Theme.Life,
        ["bone"] = Theme.Life, ["gel"] = Theme.Life, ["carapace"] = Theme.Life, ["blood"] = Theme.Life,
        // SHADOW
        ["void"] = Theme.Shadow, ["dark"] = Theme.Shadow, ["shadow"] = Theme.Shadow, ["spectral"] = Theme.Shadow,
        ["poison"] = Theme.Shadow, ["venom"] = Theme.Shadow, ["toxic"] = Theme.Shadow, ["acid"] = Theme.Shadow,
        ["arcane"] = Theme.Shadow, ["magical"] = Theme.Shadow, ["essence"] = Theme.Shadow,
        // AIR
        ["air"] = Theme.Air, ["wind"] = Theme.Air, ["vapor"] = Theme.Air, ["gas"] = Theme.Air,
    };

    private static Theme? SmithTheme(string tag) => ThemeTag.TryGetValue(tag, out var t) ? t : (Theme?)null;
    private static bool IsPureRider(string tag) => !ThemeTag.ContainsKey(tag);

    // Â§2.2 SmithModProfile â€” 7 channels (one per Theme), 0 states.
    private sealed class SmithModProfile : MinigameModifierCommon.ModProfile
    {
        public SmithModProfile() : base(7, 0) { }
    }

    // Â§2.1 SmithModTable â€” every base row (Pot=PowerÃ—, Vol=RiskÂ±, Time=CdÃ—, Rx=HP/vigorÃ—), transcribed literally.
    internal static readonly Dictionary<string, (double Pot, double Vol, double Time, double Rx)> SmithModTable = new()
    {
        // --- Quality / Grade (strictly monotone) ---
        ["starter"] = (0.90, +3, 1.05, 0.94), ["basic"] = (0.93, +2, 1.03, 0.96), ["common"] = (0.96, +1, 1.00, 0.98),
        ["standard"] = (1.00, 0, 1.00, 1.00), ["uncommon"] = (1.05, -1, 0.99, 1.03), ["fine"] = (1.08, -2, 0.98, 1.05),
        ["quality"] = (1.11, -3, 0.97, 1.06), ["refined"] = (1.13, -4, 0.96, 1.08), ["rare"] = (1.16, -5, 0.95, 1.10),
        ["advanced"] = (1.19, -6, 0.94, 1.12), ["precious"] = (1.22, -8, 0.93, 1.14), ["epic"] = (1.24, -8, 0.93, 1.15),
        ["legendary"] = (1.28, -10, 0.92, 1.18), ["mythical"] = (1.32, -12, 0.90, 1.20),
        ["superior"] = (1.14, -4, 0.96, 1.10), ["pure"] = (1.10, -10, 0.97, 1.10), ["holy"] = (1.15, -4, 0.96, 1.12),
        ["mundane"] = (0.88, 0, 1.02, 0.94), ["material"] = (1.00, -1, 1.00, 1.00),
        // --- Physical / Structural ---
        ["durable"] = (1.00, -3, 1.10, 1.14), ["hard"] = (1.00, -5, 1.08, 1.10), ["solid"] = (1.00, -8, 1.10, 1.15),
        ["dense"] = (1.00, -6, 1.12, 1.14), ["heavy"] = (1.00, -4, 1.14, 1.12), ["strong"] = (1.12, -2, 0.98, 1.08),
        ["sharp"] = (1.10, +3, 0.90, 1.00), ["layered"] = (1.00, -2, 1.08, 1.05), ["flexible"] = (1.00, -4, 1.02, 1.06),
        ["versatile"] = (1.05, -1, 1.00, 1.05), ["memory"] = (1.05, -4, 1.05, 1.05),
        // --- Energy / Essence ---
        ["magical"] = (1.15, -2, 1.02, 1.02), ["arcane"] = (1.20, -4, 1.05, 0.98), ["essence"] = (1.20, +1, 1.02, 1.05),
        ["radiant"] = (1.18, +2, 1.00, 1.08), ["light"] = (1.10, -3, 1.00, 1.05), ["spectral"] = (0.95, +4, 1.10, 0.90),
        ["blood"] = (1.12, +5, 0.92, 1.06), ["lightning"] = (1.05, +9, 0.80, 1.00), ["chaos"] = (1.00, +14, 0.80, 0.95),
        ["temporal"] = (1.10, -6, 1.30, 1.00), ["storm"] = (1.05, +8, 0.82, 0.98),
        // --- Exotic / Rule-benders ---
        ["quantum"] = (1.00, +4, 0.90, 1.15), ["impossible"] = (1.20, +6, 1.05, 1.10), ["power"] = (1.25, +3, 1.05, 1.15),
        ["harmony"] = (1.10, -8, 1.00, 1.15), ["dangerous"] = (1.10, +11, 0.92, 0.92), ["elemental"] = (1.10, +5, 0.92, 1.05),
        ["ancient"] = (1.30, -11, 1.10, 1.22),
        // --- Function / Output ---
        ["weapon"] = (1.08, +4, 0.95, 1.10), ["combat"] = (1.06, +5, 0.92, 1.12), ["explosive"] = (1.10, +14, 0.80, 1.05),
        ["strength"] = (1.15, +3, 0.95, 1.10), ["armor"] = (1.04, -9, 1.20, 0.85), ["protection"] = (1.05, -8, 1.18, 0.85),
        ["defense"] = (1.02, -8, 1.18, 0.85), ["resistance"] = (1.00, -7, 1.15, 0.88), ["healing"] = (1.05, -6, 1.10, 0.90),
        ["regeneration"] = (1.05, -6, 1.15, 0.92), ["speed"] = (1.05, +4, 0.80, 1.10), ["agility"] = (1.04, +3, 0.82, 1.10),
        ["utility"] = (1.00, -2, 1.00, 0.98), ["tool"] = (1.03, -5, 1.10, 0.90), ["crafting"] = (1.02, -4, 1.05, 0.95),
        ["engineering"] = (1.04, -6, 1.10, 0.90), ["potion"] = (1.02, -2, 1.00, 0.95), ["consumable"] = (1.00, -3, 1.00, 0.95),
        ["fishing"] = (1.00, -4, 1.05, 0.90), ["buff"] = (1.10, +2, 0.95, 1.05), ["enhancement"] = (1.12, -3, 1.00, 1.00),
    };

    // Â§2.2 SmithChExc â€” per-theme emphasis riders (Ch = (int)Theme).
    internal static readonly Dictionary<string, (int Ch, double Mul)[]> SmithChExc = new()
    {
        ["radiant"] = new[] { ((int)Theme.Fire, 1.4) },
        ["lightning"] = new[] { ((int)Theme.Fire, 1.5) },
        ["storm"] = new[] { ((int)Theme.Fire, 1.3) },
        ["chaos"] = new[] { ((int)Theme.Fire, 1.1) },
        ["light"] = new[] { ((int)Theme.Fire, 1.15), ((int)Theme.Shadow, 0.65) },
        ["essence"] = new[] { ((int)Theme.Fire, 1.3), ((int)Theme.Life, 1.3), ((int)Theme.Shadow, 1.3) },
        ["arcane"] = new[] { ((int)Theme.Shadow, 1.30) },
        ["magical"] = new[] { ((int)Theme.Shadow, 1.25) },
        ["strong"] = new[] { ((int)Theme.Earth, 1.30) },
        ["strength"] = new[] { ((int)Theme.Fire, 1.25), ((int)Theme.Earth, 1.20) },
        ["elemental"] = new[] { ((int)Theme.Fire, 1.25), ((int)Theme.Air, 1.25) },
        ["ancient"] = new[] { ((int)Theme.Earth, 1.30) },
        ["metallic"] = new[] { ((int)Theme.Earth, 1.30) },
        ["alloy"] = new[] { ((int)Theme.Earth, 1.30) },
    };

    internal static readonly Dictionary<string, double> SmithStrongExc = new()
    { ["quantum"] = 1.35, ["impossible"] = 1.40, ["power"] = 1.30 };

    // Â§2.2 SmithPvExc â€” feral/blood leech riders (Pri = (int)Theme). Key exists; leech is handled in Â§4.5.
    internal static readonly Dictionary<string, (int Pri, double Pot, double Vol)[]> SmithPvExc = new()
    { ["blood"] = new[] { ((int)Theme.Life, 0.0, 0.0) } };

    // Â§2 function-tag â†’ RusherFrac nudge (per distinct output tag).
    private static readonly Dictionary<string, double> FunctionNudge = new()
    {
        ["weapon"] = +0.20, ["combat"] = +0.20, ["explosive"] = +0.20, ["strength"] = +0.20,
        ["armor"] = -0.20, ["protection"] = -0.20, ["defense"] = -0.20, ["resistance"] = -0.20,
        ["healing"] = -0.10, ["regeneration"] = -0.10, ["speed"] = +0.15, ["agility"] = +0.15,
        ["utility"] = 0.00, ["tool"] = 0.00, ["crafting"] = 0.00, ["engineering"] = 0.00,
        ["potion"] = 0.00, ["consumable"] = 0.00, ["fishing"] = 0.00, ["buff"] = 0.00, ["enhancement"] = 0.00,
        ["harmony"] = -0.10,
    };

    // Â§4.1 hardness set (Earth + metal/hardness tag â†’ spawns a Guardian).
    private static readonly HashSet<string> HARDNESS = new()
    {
        "metal", "metallic", "iron", "steel", "bronze", "copper", "tin", "mithril", "adamantine", "silver", "gold",
        "orichalcum", "alloy", "crystal", "gem", "hard", "durable", "solid", "dense", "heavy",
    };
    private static readonly HashSet<string> FERAL = new() { "monster", "fang", "scales", "bone", "gel", "carapace", "blood" };

    // Â§2 tag-driven AoE/splash set â€” fire/explosive/volatile/heavy/chaos read "splashy" per the Tag Theme Dictionary
    // (FIRE = volatility, explosive/dangerous = big swings, heavy/dense = mass impact). A unit whose loadout/wave tags
    // overlap this fires SPLASH projectiles (impact ring + AoE) consistent with the theme across minigames.
    private static readonly HashSet<string> SPLASH_TAGS = new()
    {
        "fire", "flame", "ember", "molten", "forge", "volcanic",
        "explosive", "chaos", "storm", "lightning", "dangerous", "heavy", "dense", "blast", "combat",
    };

    // Â§4.5 per-kind ability base numbers.
    private static readonly Dictionary<AbilityKind, float> BASE_CD = new()
    {
        [AbilityKind.Nuke] = 7f, [AbilityKind.SlowField] = 9f, [AbilityKind.Bulwark] = 11f, [AbilityKind.Rally] = 12f,
        [AbilityKind.Leech] = 8f, [AbilityKind.Blink] = 5f, [AbilityKind.Torrent] = 10f,
    };
    private static readonly Dictionary<AbilityKind, float> BASE_MAG = new()
    {
        [AbilityKind.Nuke] = 55f, [AbilityKind.SlowField] = 0.45f, [AbilityKind.Bulwark] = 120f, [AbilityKind.Rally] = 60f,
        [AbilityKind.Leech] = 45f, [AbilityKind.Blink] = 220f, [AbilityKind.Torrent] = 22f,
    };
    private static readonly Dictionary<AbilityKind, float> BASE_RAD = new()
    {
        [AbilityKind.Nuke] = 90f, [AbilityKind.SlowField] = 130f, [AbilityKind.Bulwark] = 200f, [AbilityKind.Rally] = 0f,
        [AbilityKind.Leech] = 110f, [AbilityKind.Blink] = 0f, [AbilityKind.Torrent] = 100f,
    };
    private static readonly Dictionary<AbilityKind, float> BASE_DUR = new()
    {
        [AbilityKind.SlowField] = 3.5f, [AbilityKind.Torrent] = 4f, [AbilityKind.Blink] = 1.5f,
        [AbilityKind.Nuke] = 1.2f, [AbilityKind.Bulwark] = 6f, [AbilityKind.Rally] = 0f, [AbilityKind.Leech] = 0f,
    };
    private static readonly Dictionary<AbilityKind, string> KIND_LABEL = new()
    {
        [AbilityKind.Nuke] = "Nuke", [AbilityKind.SlowField] = "Frost", [AbilityKind.Bulwark] = "Bulwark",
        [AbilityKind.Rally] = "Rally", [AbilityKind.Leech] = "Leech", [AbilityKind.Blink] = "Blink",
        [AbilityKind.Torrent] = "Torrent", [AbilityKind.PassiveCrit] = "Crit", [AbilityKind.PassiveRegen] = "Regen",
        [AbilityKind.None] = "â€”",
    };
    private static AbilityKind KindOf(Theme t) => t switch
    {
        Theme.Fire => AbilityKind.Nuke, Theme.Ice => AbilityKind.SlowField, Theme.Earth => AbilityKind.Bulwark,
        Theme.Life => AbilityKind.Rally, Theme.Shadow => AbilityKind.Leech, Theme.Air => AbilityKind.Blink,
        Theme.Water => AbilityKind.Torrent, _ => AbilityKind.None,
    };

    // ================================================================ Â§8 HASH

    private static uint Hash(string s)
    {
        uint h = 2166136261u;
        foreach (byte b in Encoding.UTF8.GetBytes(s ?? "")) { h ^= b; h *= 16777619u; }
        return h;
    }

    private static int SeedFrom(RecipeContext? r)
    {
        var joined = new StringBuilder();
        if (r != null)
        {
            foreach (var ing in r.Inputs) { joined.Append(ing.Id); foreach (var t in ing.Tags) joined.Append(t); }
        }
        unchecked { return (int)(Hash(r?.OutputId ?? "debug") ^ Hash(joined.ToString())); }
    }

    private double Interp(double easy, double hard)
        => easy + (hard - easy) * Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
    private double Points01 => Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);
    private float Now => (float)_clock;

    // ============================================================== Â§6 BUILDUI

    protected override void BuildUi(VBoxContainer host)
    {
        var wrap = new Control { SizeFlagsHorizontal = Control.SizeFlags.ExpandFill, SizeFlagsVertical = Control.SizeFlags.ExpandFill };
        wrap.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        host.AddChild(wrap);

        _arena = new Control { MouseFilter = Control.MouseFilterEnum.Stop };
        _arena.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _arena.Draw += DrawArena;
        _arena.GuiInput += OnArenaInput;
        wrap.AddChild(_arena);

        _abilityBarCtl = new Control { MouseFilter = Control.MouseFilterEnum.Ignore };
        _abilityBarCtl.SetAnchorsPreset(Control.LayoutPreset.FullRect);
        _abilityBarCtl.Draw += DrawAbilityBar;
        wrap.AddChild(_abilityBarCtl);

        _dev = new MinigameDevLog("smithing");
        _dev.Context = () =>
        {
            var hpFrac = _hero.HpMax > 0 ? _hero.Hp / _hero.HpMax : 0f;
            return $"t={_clock,5:0.0} | {_phase,-9} | hp={hpFrac:0%} | killed {_enemiesKilled}/{_enemiesTotal}";
        };
        _dev.NoteSubmitted += OnDevNote;
        _dev.BuildNotesPanel(wrap);
    }

    private void OnDevNote(string text) => _dev.Note(text, SnapshotLines());

    private IEnumerable<string> SnapshotLines()
    {
        yield return $"phase={_phase} clock={_clock:0.0}/{_wave.Duration:0.0} hp={_hero.Hp:0}/{_hero.HpMax:0}";
        yield return $"hero theme={_loadout.HeroTheme} dmgMul={_loadout.HeroDamageMul:0.00} hpBonus={_loadout.HeroHpBonus:0}";
        for (var i = 0; i < 4; i++)
        {
            var a = _loadout.Abilities[i];
            yield return $"  {(AbilitySlot)i}: {a.Kind} r{a.Rank} src={a.Source} cd={a.Cooldown:0.0} mag={a.Magnitude:0.0}";
        }
        yield return $"wave char={_wave.Character} total={_wave.TotalToSpawn} spawned={_wave.Spawned} killed={_enemiesKilled}/{_enemiesTotal}";
        yield return $"wave rusherFrac={_wave.RusherFrac:0.00} hpMul={_wave.EnemyHpMul:0.00} dmgMul={_wave.EnemyDmgMul:0.00} interval={_wave.SpawnInterval:0.00}";
        yield return $"allies={_allies.Count} enemiesLive={_enemies.Count} fields={_fields.Count} perf={ComputePerf():0.00}";
    }

    private IEnumerable<string> BuildLogHeader()
    {
        yield return $"output={Recipe?.OutputId ?? "debug"}  tier={DifficultyTier}  pts={DifficultyPoints:0.#}";
        yield return $"hero={_loadout.HeroTheme}  wave={_wave.Character}  seed={SeedFrom(Recipe)}";
        yield return $"abilities=[{string.Join(", ", _loadout.Abilities.Select(a => $"{a.Slot}:{a.Kind}r{a.Rank}"))}]";
        yield return $"allies=[{string.Join(", ", _loadout.StartAllies.Select(a => $"{a.Kind}r{a.Rank}"))}]";
    }

    // ============================================================== Â§4.1 BEGIN

    protected override void OnBegin()
    {
        _finished = false;
        _phase = Phase.Ready;
        _clock = 0; _countdown = 3.0; _anim = 0; _settleT = 0; _perf = 0;
        _allies.Clear(); _enemies.Clear(); _fields.Clear(); _poison.Clear(); _telegraphs.Clear();
        _projectiles.Clear(); _pings.Clear(); _deaths.Clear(); _impacts.Clear();
        _heroBuff = default; _heroBuff.HasteMul = 1f;
        _cursor = Vector2.Zero; _moveTarget = Vector2.Zero; _hasMoveTarget = false;
        _boxDragging = false; _attackMoveArmed = false;
        _heroDmgDealt = 0; _enemiesKilled = 0; _abilitiesCast = 0; _abilitiesLandedValue = 0;
        _heroDied = false; _lowestHpFrac = 1.0; _hasToxic = false; _heroSplash = false; _waveSplash = false; _rankJitter = 0;

        _rng = new System.Random(SeedFrom(Recipe));
        _arenaRect = ComputeArenaRect();

        BuildLoadout();
        BuildWave();
        BuildHero();

        // spawn start allies at t=0 (near the hero)
        foreach (var (kind, rank) in _loadout.StartAllies)
            SpawnAlly(kind, rank, _hero.Pos + new Vector2((_allies.Count - 0.5f) * 40f, -46f));

        _enemiesTotal = _wave.TotalToSpawn;

        // total starting max HP of your whole squad (hero + initial allies) = the survival denominator.
        _squadHpMaxTotal = _hero.HpMax;
        foreach (var a in _allies) _squadHpMaxTotal += a.HpMax;

        SetQuality(0);
        SetHeaderSub($"{_loadout.HeroTheme} hero vs {_wave.Character} wave  Â·  {DescribeWave()}");
        HideTimer();
        _dev.BeginSession(BuildLogHeader());
        _arena.QueueRedraw(); _abilityBarCtl.QueueRedraw();
    }

    private Rect2 ComputeArenaRect()
    {
        var sz = _arena != null && _arena.Size.X > 1 ? _arena.Size : GetViewport().GetVisibleRect().Size;
        var aw = sz.X; var ah = sz.Y;
        return new Rect2(aw * 0.02f, ah * 0.10f, aw * 0.96f, ah * 0.78f);
    }

    private void BuildHero()
    {
        var ar = _arenaRect;
        _hero = new Unit
        {
            Team = UnitTeam.Hero,
            Pos = new Vector2(ar.Position.X + ar.Size.X * 0.5f, ar.Position.Y + ar.Size.Y * 0.72f),
            Radius = 16f,
            MoveSpeed = HERO_SPD,
            AttackCd = HERO_ATTACK_CD,
            AttackTimer = 0f,
            SpawnT = 0f,
            Range = HERO_RANGE,
            ProjSpeed = HERO_PROJ,
            Tint = _loadout.HeroTheme,
            SplashRadius = _heroSplash ? SPLASH_RADIUS : 0f,
        };
        var pHero = _lastHeroProfile;
        var vigor = pHero != null ? (float)pHero.Rx : 1f;
        _hero.HpMax = Mathf.Max(1f, HERO_HP0 * (0.9f + 0.1f * (float)Points01) * vigor + _loadout.HeroHpBonus);
        _hero.Hp = _hero.HpMax;
        var pot = pHero != null ? (float)pHero.Pot : 1f;
        _hero.Damage = HERO_DMG0 * pot * _loadout.HeroDamageMul;
        _hero.PrevPos = _hero.Pos;
    }

    // held between BuildLoadout and BuildHero so the vigor/pot muls reach hero stats
    private SmithModProfile? _lastHeroProfile;
    private SmithModProfile? _lastWaveProfile;

    // ============================================================ Â§2.2 / Â§4.5

    private struct Ing { public List<string> Tags; public int Qty; public int Tier; }

    private List<Ing> GatherInputs()
    {
        var list = new List<Ing>();
        if (Recipe?.Inputs is { Count: > 0 } inp)
        {
            foreach (var i in inp)
                list.Add(new Ing { Tags = i.Tags ?? new List<string>(), Qty = Math.Max(1, i.Qty), Tier = Math.Max(1, i.MaterialTier) });
        }
        else
        {
            // null Recipe (debug): sample a plausible loadout (Â§1.8)
            list.Add(new Ing { Tags = new List<string> { "fire", "sharp" }, Qty = 1, Tier = 2 });
            list.Add(new Ing { Tags = new List<string> { "earth", "durable" }, Qty = 1, Tier = 2 });
        }
        return list;
    }

    private List<string> OutputTagList()
    {
        if (Recipe?.OutputTags is { Count: > 0 } ot) return ot;
        if (Recipe != null) return new List<string>();
        return new List<string> { "weapon", "combat" };   // debug output tags (Â§1.8)
    }

    // Â§2.2 DominantTheme â€” dominant tag by precedence 4/3/2/1; all-zero row â†’ Earth.
    private static Theme DominantThemeOf(IReadOnlyList<string> tags)
    {
        var weight = new double[7];
        var rank = 0;
        foreach (var tag in tags)
        {
            var t = SmithTheme(tag);
            if (t != null)
            {
                var w = rank switch { 0 => 4.0, 1 => 3.0, 2 => 2.0, _ => 1.0 };
                weight[(int)t.Value] += w;
            }
            rank++;
        }
        var any = weight.Any(w => w > 0);
        if (!any) return Theme.Earth;
        var best = 0; var bv = weight[0];
        for (var i = 1; i < 7; i++) if (weight[i] > bv) { bv = weight[i]; best = i; }
        return (Theme)best;
    }

    private void BuildLoadout()
    {
        _loadout = new Loadout();
        var inputs = GatherInputs();
        var outputTags = OutputTagList();

        // count dicts (Qty-weighted for ingredients; distinct-ish for output)
        var ingredientCounts = new Dictionary<string, int>();
        foreach (var ing in inputs)
            foreach (var tag in ing.Tags)
                ingredientCounts[tag] = ingredientCounts.GetValueOrDefault(tag) + ing.Qty;
        var outputCounts = new Dictionary<string, int>();
        foreach (var tag in outputTags) outputCounts[tag] = outputCounts.GetValueOrDefault(tag) + 1;

        var recipeTier = inputs.Count > 0 ? inputs.Max(i => i.Tier) : 1;

        // hero profile
        var pHero = new SmithModProfile();
        MinigameModifierCommon.Fold(pHero, ingredientCounts, SmithModTable, SmithChExc, null, SmithStrongExc, SmithPvExc);
        pHero.Rx *= 1 + (Math.Max(1, recipeTier) - 1) * 0.05;
        MinigameModifierCommon.Clamp(pHero, 0.5, 2.0, -24, 24, 0.55, 1.8, 0.6, 1.6);
        _lastHeroProfile = pHero;

        // wave profile
        var pWave = new SmithModProfile();
        MinigameModifierCommon.Fold(pWave, outputCounts, SmithModTable, SmithChExc, null, SmithStrongExc, SmithPvExc);
        MinigameModifierCommon.Clamp(pWave, 0.5, 2.0, -24, 24, 0.55, 1.8, 0.6, 1.6);
        _lastWaveProfile = pWave;

        _loadout.HeroDamageMul = (float)pHero.Pot;

        // union of all ingredient tags (rider predicates)
        var allTags = new HashSet<string>();
        foreach (var ing in inputs) foreach (var t in ing.Tags) allTags.Add(t);
        _hasToxic = allTags.Overlaps(new[] { "poison", "venom", "toxic", "acid" });
        // tag-driven splash: a fire/explosive/heavy loadout gives the hero+allies AoE bolts (Â§2 splash set).
        _heroSplash = allTags.Overlaps(SPLASH_TAGS);

        // chaos rank jitter (Â±1) â€” one draw for the whole loadout (Â§8), applied per ability build
        _rankJitter = allTags.Contains("chaos") ? _rng.Next(0, 3) - 1 : 0;

        // temporal â†’ SlowField Duration +50% (Â§4.5); set before abilities are built (BuildWave re-sets it harmlessly).
        _lastTemporalPresent = allTags.Contains("temporal");

        // --- ability slot assignment (Qâ†’Wâ†’E first-free; duplicate themes stack the pool) ---
        for (var i = 0; i < 4; i++) _loadout.Abilities[i] = new Ability { Slot = (AbilitySlot)i, Kind = AbilityKind.None };

        var slotThemes = new Dictionary<Theme, (int Slot, int Rank)>();
        var nextSlot = 0;   // Q=0, W=1, E=2
        foreach (var ing in inputs)
        {
            var theme = DominantThemeOf(ing.Tags);
            if (KindOf(theme) == AbilityKind.None) continue;
            if (slotThemes.ContainsKey(theme))
            {
                // duplicate theme stacks the pool â†’ raise Rank toward this ingredient's tier
                var cur = slotThemes[theme];
                slotThemes[theme] = (cur.Slot, Math.Max(cur.Rank, ing.Tier));
                continue;
            }
            if (nextSlot > 2) continue;   // scope cap: 3 active
            slotThemes[theme] = (nextSlot, ing.Tier);
            nextSlot++;
        }

        // dominant loadout theme (hero tint) = the theme with the highest pooled ingredient weight
        _loadout.HeroTheme = DominantLoadoutTheme(inputs);

        foreach (var kv in slotThemes)
        {
            var theme = kv.Key; var slot = kv.Value.Slot; var rank = Math.Clamp(kv.Value.Rank + _rankJitter, 1, 4);
            _loadout.Abilities[slot] = BuildAbility((AbilitySlot)slot, theme, rank, pHero);
        }

        // --- R (passive) slot ---
        var passive = new Ability { Slot = AbilitySlot.R, Kind = AbilityKind.None, Source = _loadout.HeroTheme, Label = "â€”" };
        if (allTags.Contains("sharp") || allTags.Contains("strength"))
        {
            var copies = (allTags.Contains("sharp") ? 1 : 0) + (allTags.Contains("strength") ? 1 : 0);
            _heroBuff.CritChance = (float)Math.Clamp(0.20 + 0.08 * (copies - 1), 0, 0.6);
            passive.Kind = AbilityKind.PassiveCrit; passive.Label = "Crit";
        }
        else if (inputs.Any(i => { var d = DominantThemeOf(i.Tags); return d == Theme.Life || d == Theme.Water; }))
        {
            _heroBuff.RegenPerS = 6f; _heroBuff.RegenUntil = float.MaxValue;
            passive.Kind = AbilityKind.PassiveRegen; passive.Label = "Regen";
        }
        _loadout.Abilities[3] = passive;

        // --- feral/blood passive leech rider (independent of R) ---
        if (allTags.Contains("blood") || inputs.Any(i => i.Tags.Any(FERAL.Contains)))
        {
            _heroBuff.LeechFrac = Math.Max(_heroBuff.LeechFrac, 0.12f);
            _heroBuff.LeechUntil = float.MaxValue;
        }

        // --- ally build ---
        var startAllies = new List<(AllyKind Kind, int Rank)>();
        foreach (var ing in inputs)
        {
            var theme = DominantThemeOf(ing.Tags);
            if (theme == Theme.Life)
                startAllies.Add((AllyKind.Sprout, ing.Tier));
            else if (theme == Theme.Earth && ing.Tags.Any(HARDNESS.Contains))
                startAllies.Add((AllyKind.Guardian, ing.Tier));
        }
        for (var i = 0; i < startAllies.Count; i++)
        {
            if (i < MAX_START_ALLIES) _loadout.StartAllies.Add(startAllies[i]);
            else _loadout.HeroHpBonus += startAllies[i].Kind == AllyKind.Guardian ? GUARDIAN_HP_FALLBACK : SPROUT_HP_FALLBACK;
        }

        // EARTH/quality HP stacking flows through pHero.Rx (vigor) applied in BuildHero; HeroHpBonus is the ally overflow.
    }

    private static Theme DominantLoadoutTheme(List<Ing> inputs)
    {
        var weight = new double[7];
        foreach (var ing in inputs)
        {
            var rank = 0;
            foreach (var tag in ing.Tags)
            {
                var t = SmithTheme(tag);
                if (t != null)
                {
                    var w = rank switch { 0 => 4.0, 1 => 3.0, 2 => 2.0, _ => 1.0 };
                    weight[(int)t.Value] += w * Math.Max(1, ing.Qty);
                }
                rank++;
            }
        }
        var any = weight.Any(w => w > 0);
        if (!any) return Theme.Earth;
        var best = 0; var bv = weight[0];
        for (var i = 1; i < 7; i++) if (weight[i] > bv) { bv = weight[i]; best = i; }
        return (Theme)best;
    }

    private Ability BuildAbility(AbilitySlot slot, Theme source, int rank, SmithModProfile pHero)
    {
        var kind = KindOf(source);
        float tierMul = rank switch { 1 => 1.0f, 2 => 1.35f, 3 => 1.8f, _ => 2.4f };
        var hasTemporal = _lastTemporalPresent;
        var ability = new Ability
        {
            Slot = slot,
            Kind = kind,
            Rank = rank,
            Source = source,
            Cooldown = (float)(BASE_CD[kind] * pHero.Time),
            Magnitude = (float)(BASE_MAG[kind] * tierMul * pHero.Pot * pHero.Ch[(int)source]),
            Radius = (float)(BASE_RAD[kind] * (0.85 + 0.15 * tierMul)),
            Duration = BASE_DUR.TryGetValue(kind, out var d) ? d * (hasTemporal && kind == AbilityKind.SlowField ? 1.5f : 1f) : 0f,
            Targeted = kind is AbilityKind.Nuke or AbilityKind.SlowField or AbilityKind.Blink,
            Label = KIND_LABEL[kind],
            CdTimer = 0f,
        };
        return ability;
    }

    private bool _lastTemporalPresent;

    // ============================================================= Â§4.2 WAVE

    private static int TierIndexOf(string tier) => tier switch
    {
        "common" => 0, "uncommon" => 1, "rare" => 2, "epic" => 3, "legendary" => 4, _ => 0,
    };

    private void BuildWave()
    {
        var inputs = GatherInputs();
        _lastTemporalPresent = inputs.Any(i => i.Tags.Contains("temporal"));

        var outputTags = OutputTagList();
        var pWave = _lastWaveProfile ?? new SmithModProfile();
        // tag-driven splash on the enemy wave: an explosive/fiery output makes enemy shots AoE (Â§2 splash set).
        _waveSplash = outputTags.Any(SPLASH_TAGS.Contains);

        // tierIndex: DifficultyTier wins whenever present; else Recipe.Tier (debug).
        var tierIndex = Recipe != null ? TierIndexOf(DifficultyTier)
            : TierIndexOf(string.IsNullOrEmpty(DifficultyTier) ? (Recipe?.Tier ?? "common") : DifficultyTier);

        _wave = new Wave
        {
            Character = DominantThemeOf(outputTags),
            Duration = (float)Interp(24, 40),
            TotalToSpawn = (int)Math.Round(BASE_ENEMIES + DifficultyPoints / 8.0),
            SecondWave = tierIndex >= 2,
            MiniBoss = tierIndex >= 4,
        };

        _wave.EnemyHpMul = (float)((1 + 0.03 * DifficultyPoints) * ClampWave(pWave.Pot));
        _wave.EnemyDmgMul = (float)((0.9 + 0.35 * Points01) * (1 + pWave.Vol / 60.0));

        // wave-side AmpStrongest â€” amplify the higher of Hp/Dmg gain fraction (Hp on tie).
        if (Math.Abs(pWave.AmpStrongest - 1) > 1e-6)
        {
            var hpGain = _wave.EnemyHpMul - 1;
            var dmgGain = _wave.EnemyDmgMul - 1;
            if (hpGain >= dmgGain) _wave.EnemyHpMul *= (float)pWave.AmpStrongest;
            else _wave.EnemyDmgMul *= (float)pWave.AmpStrongest;
        }

        // RusherFrac: 0.5 + Î£ functionNudge over distinct output tags, then Ice adj, then clamp.
        double nudge = 0;
        foreach (var tag in outputTags.Distinct()) if (FunctionNudge.TryGetValue(tag, out var v)) nudge += v;
        var iceRusherAdj = _wave.Character == Theme.Ice ? -0.15 : 0.0;
        _wave.RusherFrac = (float)Math.Clamp(0.5 + nudge + iceRusherAdj, 0.15, 0.85);

        // spawn-interval sequencing: base â†’ Water rider â†’ fixed mean.
        var baseInterval = _wave.Duration / (_wave.TotalToSpawn + 1);
        if (_wave.Character == Theme.Water) baseInterval *= 1.15f;
        _wave.SpawnInterval = Mathf.Max(0.2f, baseInterval);

        // character riders on spawn jitter / evasion.
        _wave.SpawnJitterAmp = _wave.Character == Theme.Fire ? 1.4f : 1f;
        _wave.EvasiveAmp = _wave.Character is Theme.Air or Theme.Shadow ? 1.5f : 1f;

        _wave.NextSpawnAt = 0f;
    }

    private static double ClampWave(double x) => Math.Clamp(x, 0.8, 1.6);

    private string DescribeWave()
    {
        var mix = _wave.RusherFrac >= 0.6 ? "rusher-heavy" : _wave.RusherFrac <= 0.4 ? "bruiser-heavy" : "mixed";
        var extra = (_wave.SecondWave ? " +2nd wave" : "") + (_wave.MiniBoss ? " +mini-boss" : "");
        return $"{_wave.TotalToSpawn} foes, {mix}, {_wave.Duration:0}s{extra}";
    }

    // ============================================================ SPAWN / STATS

    private (float hp, float speed, float dmg, float cd, float radius) EnemyBase(EnemyKind kind)
    {
        return kind == EnemyKind.Rusher
            ? (EN_RUSH_HP, 170f, 8f, 0.8f, 11f)
            : (EN_BRUI_HP, 95f, 18f, 1.3f, 17f);
    }

    private Unit MakeEnemy(EnemyKind kind, Vector2 pos, bool boss = false)
    {
        var (hp, speed, dmg, cd, radius) = EnemyBase(kind);
        hp *= _wave.EnemyHpMul; dmg *= _wave.EnemyDmgMul;

        // single per-theme character rider on enemy stats (Â§4.2).
        switch (_wave.Character)
        {
            case Theme.Fire: speed *= 1.15f; break;
            case Theme.Air: speed *= 1.20f; break;
            case Theme.Ice: hp *= 1.25f; break;
            case Theme.Earth: hp *= 1.25f; speed *= 0.9f; break;
            case Theme.Shadow: dmg *= 1.2f; break;
            // Water/Life handled via spawn interval / regrow.
        }

        var u = new Unit
        {
            Team = UnitTeam.Enemy,
            EKind = kind,
            Pos = pos,
            PrevPos = pos,
            Radius = radius,
            HpMax = hp,
            Hp = hp,
            MoveSpeed = speed,
            Damage = dmg,
            AttackCd = cd,
            AttackTimer = cd,
            SpawnT = Now,
            Seed = _rng.Next(0, 100000),
            Tint = _wave.Character,
            // Rusher = fast short lunge-strike; Bruiser = heavy slow close swing (both projectile-based, readable).
            Range = kind == EnemyKind.Rusher ? RUSH_RANGE : BRUI_RANGE,
            ProjSpeed = kind == EnemyKind.Rusher ? RUSH_PROJ : BRUI_PROJ,
            SplashRadius = _waveSplash ? SPLASH_RADIUS : 0f,
        };

        if (boss)
        {
            u.IsMiniBoss = true;
            u.HpMax *= 4f; u.Hp = u.HpMax; u.Radius = 26f; u.Damage *= 1.5f;
            u.Range = BRUI_RANGE + 26f; u.SplashRadius = SPLASH_RADIUS * 1.2f;   // the boss always lobs a splash swing
        }

        // Shadow rider: 10% of enemies phase (untargetable 0.4s) on spawn.
        if (_wave.Character == Theme.Shadow && _rng.NextDouble() < 0.10) u.Phased = Now + 0.4f;

        return u;
    }

    private Vector2 EdgeSpawn()
    {
        var ar = _arenaRect;
        var edge = _rng.Next(0, 4);
        var t = (float)_rng.NextDouble();
        return edge switch
        {
            0 => new Vector2(ar.Position.X + ar.Size.X * t, ar.Position.Y + 4),                    // top
            1 => new Vector2(ar.Position.X + ar.Size.X * t, ar.Position.Y + ar.Size.Y - 4),        // bottom
            2 => new Vector2(ar.Position.X + 4, ar.Position.Y + ar.Size.Y * t),                    // left
            _ => new Vector2(ar.Position.X + ar.Size.X - 4, ar.Position.Y + ar.Size.Y * t),        // right
        };
    }

    private void SpawnAlly(AllyKind kind, int rank, Vector2 pos)
    {
        if (_allies.Count >= MAX_ALLIES) { _loadout.HeroHpBonus += kind == AllyKind.Guardian ? GUARDIAN_HP_FALLBACK : SPROUT_HP_FALLBACK; return; }
        float tierMul = rank switch { 1 => 1.0f, 2 => 1.35f, 3 => 1.8f, _ => 2.4f };
        var u = new Unit
        {
            Team = UnitTeam.Ally,
            AKind = kind,
            Pos = pos,
            PrevPos = pos,
            SpawnT = Now,
            Seed = _rng.Next(0, 100000),
        };
        if (kind == AllyKind.Sprout)
        {
            u.Radius = 12f; u.HpMax = 60f * tierMul; u.MoveSpeed = 190f; u.Damage = 10f * tierMul; u.AttackCd = 0.7f;
            u.Range = SPROUT_RANGE; u.ProjSpeed = SPROUT_PROJ; u.Tint = Theme.Life;   // sprout = ranged life-bolt spitter
        }
        else // Guardian
        {
            u.Radius = 15f; u.HpMax = 140f * tierMul; u.MoveSpeed = 130f; u.Damage = 8f * tierMul; u.AttackCd = 1.0f;
            u.Range = GUARD_RANGE; u.ProjSpeed = GUARD_PROJ; u.Tint = Theme.Earth;    // guardian = short melee bash
        }
        u.SplashRadius = _heroSplash ? SPLASH_RADIUS : 0f;
        u.Hp = u.HpMax; u.AttackTimer = u.AttackCd;
        _allies.Add(u);
    }

    // ============================================================= Â§3 / Â§4 TICK

    protected override void OnTick(double delta)
    {
        _anim += delta;
        if (_phase == Phase.Done) return;

        switch (_phase)
        {
            case Phase.Ready:
                _arena.QueueRedraw(); _abilityBarCtl.QueueRedraw();
                break;

            case Phase.Countdown:
                _countdown -= delta;
                if (_countdown <= 0) EnterPlay();
                _arena.QueueRedraw();
                break;

            case Phase.Play:
                _clock += delta;
                UpdatePlay((float)delta);
                _arena.QueueRedraw(); _abilityBarCtl.QueueRedraw();
                break;

            case Phase.Settle:
                _clock += delta;
                _settleT += delta;
                if (_settleT >= 1.1) EnterDone();
                _arena.QueueRedraw(); _abilityBarCtl.QueueRedraw();
                break;
        }
    }

    private void EnterPlay()
    {
        _phase = Phase.Play;
        _clock = 0;
        _wave.NextSpawnAt = 0;
        _heroDmgDealt = 0; _enemiesKilled = 0; _abilitiesCast = 0; _abilitiesLandedValue = 0;
        // default selection = hero + every ally, so a right-click commands the whole squad from t=0 (SC2 feel; the
        // player can still left-click / box / shift to narrow the selection).
        SelectAllFriendlies();
        _dev.Log($"FORGE! wave {_wave.Character} x{_wave.TotalToSpawn}");
    }

    // --- selection helpers (used by input + EnterPlay) ---
    private IEnumerable<Unit> Friendlies()
    {
        if (_hero != null) yield return _hero;   // hero is a controllable unit too
        foreach (var a in _allies) yield return a;
    }

    private void SelectAllFriendlies()
    {
        foreach (var f in Friendlies()) f.Selected = f.Alive;
    }

    private void ClearSelection()
    {
        foreach (var f in Friendlies()) f.Selected = false;
    }

    private IEnumerable<Unit> Selected()
    {
        foreach (var f in Friendlies()) if (f.Selected && f.Alive) yield return f;
    }

    private void UpdatePlay(float dt)
    {
        // cooldowns
        foreach (var a in _loadout.Abilities) if (a.CdTimer > 0) a.CdTimer = Mathf.Max(0, a.CdTimer - dt);

        // hero regen buff
        if (Now < _heroBuff.RegenUntil && _heroBuff.RegenPerS > 0 && _hero.Alive)
            HealHero(_heroBuff.RegenPerS * dt);

        // spawn scheduling + telegraphs
        ScheduleSpawns();
        ResolveTelegraphs();

        // unit sim
        TickUnits(dt);

        // expire command pings + death-dissolve + impact-ring VFX (cosmetic lists only)
        for (var i = _pings.Count - 1; i >= 0; i--) if (Now >= _pings[i].Until) _pings.RemoveAt(i);
        for (var i = _deaths.Count - 1; i >= 0; i--) if (Now >= _deaths[i].Until) _deaths.RemoveAt(i);
        for (var i = _impacts.Count - 1; i >= 0; i--) if (Now >= _impacts[i].Until) _impacts.RemoveAt(i);

        // track lowest HP
        var frac = _hero.HpMax > 0 ? _hero.Hp / _hero.HpMax : 0f;
        if (frac < _lowestHpFrac) _lowestHpFrac = frac;

        // live scoring + timer
        SetQuality(ComputePerf());
        SetTimer(Math.Max(0, _wave.Duration - _clock));

        // terminal checks
        if (!_hero.Alive) { EnterSettle(dead: true); return; }
        var allSpawned = _wave.Spawned >= _enemiesTotal;
        if (_enemiesKilled >= _enemiesTotal && _enemiesTotal > 0) { EnterSettle(dead: false); return; }
        if (_clock >= _wave.Duration && allSpawned && _enemies.Count == 0) { EnterSettle(dead: false); return; }
    }

    private void EnterSettle(bool dead)
    {
        if (_phase != Phase.Play) return;
        _phase = Phase.Settle;
        _settleT = 0;
        _heroDied = dead || !_hero.Alive;
        HideTimer();
        _dev.Log(dead ? "HERO DOWN" : "WAVE CLEARED");
        if (!dead)
        {
            CraftFx.Burst(_arena, _hero.Pos, Accent2, 34, 320f, 0.9f, 5f, 120f);
            CraftFx.Burst(_arena, _hero.Pos, Colors.White, 16, 220f, 0.7f, 3f, 60f);
        }
        else
        {
            CraftFx.Burst(_arena, _hero.Pos, LowRed, 24, 260f, 0.8f, 4f, 200f);
        }
    }

    private void EnterDone()
    {
        _phase = Phase.Done;
        if (_finished) return;
        _finished = true;
        _perf = Math.Clamp(Math.Max(ComputePerf(), PERF_FLOOR), 0, 1);
        _dev.Log($"DONE perf={_perf:0.00} killed {_enemiesKilled}/{_enemiesTotal} died={_heroDied}");
        if (FAILCRAFT_FLOOR > 0.0 && _perf < FAILCRAFT_FLOOR) FailCraft();
        else Finish(_perf);
    }

    // ------------------------------------------------------------ Â§4.3 SPAWN

    private void ScheduleSpawns()
    {
        // SecondWave budget bump when clock crosses Duration*0.5
        if (_wave.SecondWave && !_wave.SecondWaveTriggered && _clock >= _wave.Duration * 0.5)
        {
            _wave.SecondWaveTriggered = true;
            var add = (int)Math.Round(_wave.TotalToSpawn * 0.6);
            _wave.TotalToSpawn += add;
            _enemiesTotal += add;
            _dev.Log($"2ND WAVE +{add}");
        }

        // MiniBoss telegraph at 60% Duration.
        if (_wave.MiniBoss && !_wave.MiniBossSpawned && _clock >= _wave.Duration * 0.6)
        {
            _wave.MiniBossSpawned = true;
            _enemiesTotal += 1;
            var pos = EdgeSpawn();
            _telegraphs.Add(new Telegraph { Pos = pos, At = Now + BOSS_TELL, Boss = true, Kind = EnemyKind.Bruiser });
            _dev.Log("MINI-BOSS incoming");
        }

        while (_wave.Spawned < _wave.TotalToSpawn && _clock >= _wave.NextSpawnAt)
        {
            if (_enemies.Count >= MAX_ENEMIES_LIVE) { _wave.NextSpawnAt = Now + 0.25f; break; }
            var kind = _rng.NextDouble() < _wave.RusherFrac ? EnemyKind.Rusher : EnemyKind.Bruiser;
            var pos = EdgeSpawn();
            _telegraphs.Add(new Telegraph { Pos = pos, At = Now + SPAWN_TELL, Boss = false, Kind = kind });
            _wave.Spawned++;
            var jitter = (kind == EnemyKind.Rusher ? 0.15f : 0.05f) * _wave.SpawnJitterAmp;
            jitter = Mathf.Clamp(jitter, 0f, 0.15f);
            _wave.NextSpawnAt += _wave.SpawnInterval * (1 + ((float)_rng.NextDouble() * 2 - 1) * jitter);
        }
    }

    private void ResolveTelegraphs()
    {
        for (var i = _telegraphs.Count - 1; i >= 0; i--)
        {
            if (Now >= _telegraphs[i].At)
            {
                var tg = _telegraphs[i];
                if (_enemies.Count < MAX_ENEMIES_LIVE)
                    _enemies.Add(MakeEnemy(tg.Kind, tg.Pos, tg.Boss));
                _telegraphs.RemoveAt(i);
            }
        }
    }

    // -------------------------------------------------- Â§4.4 UNIT TICK

    private void TickUnits(float dt)
    {
        var ar = _arenaRect;

        // clear any dead focus targets before steering (so a command never chases a corpse)
        foreach (var f in Friendlies()) if (f.CmdFocus != null && !f.CmdFocus.Alive) f.CmdFocus = null;

        // (1) hero steering â€” driven by its command (Move / AttackMove / focus), else it holds + auto-fires
        var hasteMul = Now < _heroBuff.HasteUntil ? _heroBuff.HasteMul : 1f;
        _hero.PrevPos = _hero.Pos;
        IntegrateUnit(_hero, CommandDesired(_hero) * hasteMul, dt);
        // keep the legacy hero move-marker in sync with the hero's current move order (draw layer reads it)
        _hasMoveTarget = _hero.Cmd == CmdMode.Move;
        _moveTarget = _hero.CmdPoint;

        // (2) enemy seek
        var taunt = _activeTauntUntil > Now ? _hero : null;
        foreach (var e in _enemies)
        {
            if (!e.Alive) continue;
            var target = SeekTargetForEnemy(e, taunt);
            var slowMul = Now < e.SlowUntil ? e.SlowFactor : 1f;
            // stop short of the target once inside firing range so ranged enemies actually shoot instead of piling in
            var desired = Vector2.Zero;
            if (target != null)
            {
                var to = target.Pos - e.Pos;
                var gap = to.Length() - (e.Radius + target.Radius + e.Range * 0.7f);
                if (gap > 0) desired = to.Normalized() * e.MoveSpeed * slowMul;
            }
            desired += Wander(e.Seed) * (_wave.EvasiveAmp);
            e.PrevPos = e.Pos;
            IntegrateUnit(e, desired, dt, applySep: true);
        }

        // (3) ally seek â€” a command overrides the archetype behaviour (Â§5); else fall back to the archetype AI
        for (var ai = 0; ai < _allies.Count; ai++)
        {
            var a = _allies[ai];
            if (!a.Alive) continue;
            Vector2 desired;
            if (a.Cmd != CmdMode.None || a.CmdFocus != null)
            {
                desired = CommandDesired(a);
            }
            else if (a.AKind == AllyKind.Sprout)
            {
                var enemy = NearestEnemy(a.Pos, ALLY_AGGRO);
                desired = enemy != null ? ApproachToRange(a, enemy) : FollowHero(a, 60f);
            }
            else // Guardian: interpose between hero and nearest enemy
            {
                var enemy = NearestEnemy(_hero.Pos, 9999f);
                if (enemy != null)
                {
                    var mid = (_hero.Pos + enemy.Pos) * 0.5f;
                    desired = (mid - a.Pos);
                    desired = desired.Length() > 4f ? desired.Normalized() * a.MoveSpeed : Vector2.Zero;
                }
                else desired = FollowHero(a, 46f);
            }
            a.PrevPos = a.Pos;
            IntegrateUnit(a, desired, dt, applySep: true, sepWeight: a.AKind == AllyKind.Guardian ? 1.6f : 1f);
        }

        // (6) attacks â€” windups â†’ projectiles â†’ impact
        DoAttacks(dt);
        TickProjectiles(dt);

        // (7) field effects
        TickFields(dt);
        TickPoison(dt);

        // hero HitFlash decay + facing
        foreach (var u in AllUnits()) { if (u.HitFlash > 0) u.HitFlash = Mathf.Max(0, u.HitFlash - dt * 4f); UpdateFacing(u); }

        // clamp positions to arena
        foreach (var u in AllUnits()) u.Pos = ClampToArena(u.Pos, ar);

        // (8) cull
        CullDead();
    }

    private void IntegrateUnit(Unit u, Vector2 desired, float dt, bool applySep = false, float sepWeight = 1f)
    {
        if (applySep) desired += Separation(u) * sepWeight;
        u.Vel = desired;                 // INSTANT acceleration + turning (no drift) — commands feel responsive
        u.Pos += u.Vel * dt;
    }

    // Desired velocity for a FRIENDLY unit from its current order (SC2 command model):
    //  â€¢ CmdFocus (right-click enemy)  â†’ chase that enemy, stop at firing range.
    //  â€¢ Move                          â†’ beeline to point, IGNORE enemies; arriving clears the order (hold).
    //  â€¢ AttackMove                    â†’ advance to point but PEEL OFF to engage any enemy that comes into aggro range.
    //  â€¢ None                          â†’ hold position (auto-fire handles the rest).
    private const float ATTACK_MOVE_AGGRO = 190f;   // px an attack-moving unit will divert to engage an enemy
    private Vector2 CommandDesired(Unit u)
    {
        var spd = u.MoveSpeed;
        // an explicit focus-fire target always wins
        if (u.CmdFocus != null && u.CmdFocus.Alive)
            return ApproachToRange(u, u.CmdFocus);

        switch (u.Cmd)
        {
            case CmdMode.Move:
            {
                var to = u.CmdPoint - u.Pos;
                if (to.Length() < 8f) { u.Cmd = CmdMode.None; return Vector2.Zero; }
                return to.Normalized() * spd;
            }
            case CmdMode.AttackMove:
            {
                // engage the nearest enemy in aggro range; else keep marching to the point.
                var enemy = NearestEnemy(u.Pos, ATTACK_MOVE_AGGRO);
                if (enemy != null) return ApproachToRange(u, enemy);
                var to = u.CmdPoint - u.Pos;
                if (to.Length() < 8f) { u.Cmd = CmdMode.None; return Vector2.Zero; }
                return to.Normalized() * spd;
            }
            default:
                return Vector2.Zero;   // hold
        }
    }

    // Move toward a target only until inside firing range, then stop (so ranged units kite instead of body-blocking).
    private Vector2 ApproachToRange(Unit u, Unit target)
    {
        var to = target.Pos - u.Pos;
        var gap = to.Length() - (u.Radius + target.Radius + u.Range * 0.7f);
        if (gap <= 0) return Vector2.Zero;
        return to.Normalized() * u.MoveSpeed;
    }

    private Vector2 Separation(Unit u)
    {
        var push = Vector2.Zero;
        foreach (var o in AllUnits())
        {
            if (o == u || !o.Alive) continue;
            var to = u.Pos - o.Pos;
            var d = to.Length();
            var range = (u.Radius + o.Radius) * SEP_RADIUS_MUL;
            if (d > 0.1f && d < range) push += to.Normalized() * SEP_FORCE * (1 - d / range);
        }
        return push;
    }

    private Vector2 Wander(int seed) => new Vector2(0, 0) + PerpSine(seed);

    private Vector2 PerpSine(int seed)
    {
        // deterministic small perpendicular sine â€” replay-safe (no GD.Randf)
        var amp = EVASIVE;
        var s = Mathf.Sin((float)_anim * 1.7f + seed);
        return new Vector2(s * amp * 0.5f, Mathf.Cos((float)_anim * 1.3f + seed) * amp * 0.5f);
    }

    private Vector2 FollowHero(Unit a, float dist)
    {
        var to = _hero.Pos - a.Pos;
        if (to.Length() < dist) return Vector2.Zero;
        return to.Normalized() * a.MoveSpeed;
    }

    private Unit? SeekTargetForEnemy(Unit e, Unit? taunt)
    {
        if (taunt != null && taunt.Alive) return taunt;
        // nearest of {hero, selected ally within range}
        Unit? best = _hero.Alive ? _hero : null;
        var bd = best != null ? e.Pos.DistanceTo(best.Pos) : float.MaxValue;
        foreach (var a in _allies)
        {
            if (!a.Alive) continue;
            var d = e.Pos.DistanceTo(a.Pos);
            if (d < bd) { bd = d; best = a; }
        }
        return best;
    }

    private Unit? NearestEnemy(Vector2 from, float within)
    {
        Unit? best = null; var bd = within;
        foreach (var e in _enemies)
        {
            if (!e.Alive || Now < e.Phased) continue;
            var d = from.DistanceTo(e.Pos);
            if (d < bd) { bd = d; best = e; }
        }
        return best;
    }

    private void UpdateFacing(Unit u)
    {
        if (u.Vel.Length() > 4f) { u.Facing = u.Vel.Angle(); return; }
        if (u.Team == UnitTeam.Hero)
        {
            var target = NearestEnemy(u.Pos, HERO_RANGE);
            u.Facing = target != null ? (target.Pos - u.Pos).Angle() : (_cursor - u.Pos).Angle();
            return;
        }
        if (u.Team == UnitTeam.Enemy)
        {
            var t = SeekTargetForEnemy(u, _activeTauntUntil > Now ? _hero : null);
            if (t != null) u.Facing = (t.Pos - u.Pos).Angle();
            return;
        }
        // ally: face nearest enemy
        var en = NearestEnemy(u.Pos, 9999f);
        if (en != null) u.Facing = (en.Pos - u.Pos).Angle();
    }

    private float _activeTauntUntil;

    // Â§1.2b damage application â€” Shield-then-HP; returns HP actually removed (leech-eligible).
    private float Hurt(Unit u, float dmg)
    {
        if (dmg <= 0 || !u.Alive) return 0;
        if (u.Team == UnitTeam.Enemy && Now < u.Phased) return 0;
        u.HitFlash = 1;
        var toShield = Mathf.Min(u.Shield, dmg);
        u.Shield -= toShield;
        var toHp = dmg - toShield;
        u.Hp = Mathf.Max(0, u.Hp - toHp);
        return toHp;
    }

    private void HealHero(float x)
    {
        if (x <= 0 || !_hero.Alive) return;
        _hero.Hp = Mathf.Min(_hero.HpMax, _hero.Hp + x);
    }

    // Â§4.4a PROJECTILE ATTACK MODEL (playtest rework). Every unit auto-attack is now: reload (AttackTimer) â†’ a short
    // WINDUP telegraph (lean/flash) â†’ spawn a Projectile that flies at finite speed â†’ damage ON IMPACT. This makes
    // range + reload + travel all READABLE. Ability casts are unchanged (they keep their own instant AoE VFX).
    private void DoAttacks(float dt)
    {
        if (_hero.Alive) StepUnitAttack(_hero, dt, PickHeroTarget(_hero), WINDUP_HERO, isHero: true);
        foreach (var a in _allies) if (a.Alive) StepUnitAttack(a, dt, PickAllyTarget(a), a.AKind == AllyKind.Sprout ? WINDUP_RANGED : WINDUP_MELEE, isHero: false);
        foreach (var e in _enemies) if (e.Alive) StepUnitAttack(e, dt, PickEnemyTarget(e), e.EKind == EnemyKind.Rusher ? WINDUP_MELEE : WINDUP_RANGED, isHero: false);
    }

    // Advance one unit's attack state machine. `target` is the (already range-checked) unit to shoot, or null.
    private void StepUnitAttack(Unit u, float dt, Unit? target, float windupLen, bool isHero)
    {
        if (u.MuzzleFlash > 0) u.MuzzleFlash = Mathf.Max(0, u.MuzzleFlash - dt * 5f);

        // resolve an in-progress windup â€” fire when it elapses (re-aim at the live target so a strafing shot tracks)
        if (u.Windup > 0)
        {
            if (target != null) { u.AimTarget = target; u.AimAt = target.Pos; }
            u.Windup = Mathf.Max(0, u.Windup - dt);
            if (u.Windup <= 0) FireProjectile(u, isHero);
            return;   // a unit that is winding up isn't also counting down its reload
        }

        if (u.AttackTimer > 0) u.AttackTimer -= dt;
        if (u.AttackTimer > 0) return;

        // reload ready â€” begin a windup if we have a target in range, else stay hot (fire the instant one appears)
        if (target != null)
        {
            u.Windup = windupLen; u.WindupLen = windupLen;
            u.AimTarget = target; u.AimAt = target.Pos;
        }
        else u.AttackTimer = 0f;   // ready â€” no cooldown drain while there's nothing to shoot
    }

    // Fire the windup's shot: spawn a Projectile toward the locked aim, reset reload, muzzle flash.
    private void FireProjectile(Unit u, bool isHero)
    {
        if (_projectiles.Count >= MAX_PROJECTILES) { u.AttackTimer = u.AttackCd; u.MuzzleFlash = 1f; return; }
        var crit = isHero && _rng.NextDouble() < _heroBuff.CritChance;
        var dmg = u.Damage * (crit ? 2f : 1f);
        var origin = u.Pos + AngleVec(u.Facing) * (u.Radius + 3f);
        var aim = u.AimTarget is { Alive: true } t ? t.Pos : u.AimAt;
        var dir = (aim - origin);
        dir = dir.LengthSquared() > 1e-3f ? dir.Normalized() : AngleVec(u.Facing);
        var friendly = u.Team != UnitTeam.Enemy;
        _projectiles.Add(new Projectile
        {
            Team = u.Team,
            Pos = origin,
            PrevPos = origin,
            Vel = dir * u.ProjSpeed,
            Target = aim,
            AimTarget = u.AimTarget is { Alive: true } ? u.AimTarget : null,
            Speed = u.ProjSpeed,
            Damage = dmg,
            Radius = u.IsMiniBoss ? 8f : (u.SplashRadius > 0 ? 6f : 4f),
            SplashRadius = u.SplashRadius,
            Crit = crit,
            Leech = isHero,
            Toxic = friendly && _hasToxic,     // only the smith's side carries the toxic rider (Â§2.1)
            Tint = u.Tint,
            Life = 0f,
        });
        u.MuzzleFlash = 1f;
        u.AttackTimer = u.AttackCd;
        u.Windup = 0f;
        Shake(isHero && crit ? 3f : 0f);
    }

    // ------- target selection (already range-checked so StepUnitAttack just consumes it) -------
    private Unit? PickHeroTarget(Unit h)
    {
        // honour a focus-fire order if it's in range; otherwise auto-target the nearest enemy in range
        if (h.CmdFocus is { Alive: true } f && h.Pos.DistanceTo(f.Pos) <= h.Range && Now >= f.Phased) return f;
        return NearestEnemy(h.Pos, h.Range);
    }

    private Unit? PickAllyTarget(Unit a)
    {
        if (a.CmdFocus is { Alive: true } f && a.Pos.DistanceTo(f.Pos) <= a.Range && Now >= f.Phased) return f;
        // while ordered to a plain Move, allies HOLD FIRE (SC2 move ignores enemies); attack-move + idle both shoot
        if (a.Cmd == CmdMode.Move && a.CmdFocus == null) return null;
        return NearestEnemy(a.Pos, a.Range);
    }

    private Unit? PickEnemyTarget(Unit e)
    {
        var t = SeekTargetForEnemy(e, _activeTauntUntil > Now ? _hero : null);
        if (t == null || !t.Alive) return null;
        return e.Pos.DistanceTo(t.Pos) <= e.Range + e.Radius + t.Radius ? t : null;
    }

    // ------- projectile flight + impact -------
    private void TickProjectiles(float dt)
    {
        for (var i = _projectiles.Count - 1; i >= 0; i--)
        {
            var p = _projectiles[i];
            p.Life += dt;
            p.PrevPos = p.Pos;

            // soft homing: gently re-steer toward a living target so a moving foe still gets hit (kept subtle so
            // dodging by repositioning still works â€” the shot curves a little, not a guaranteed lock)
            if (p.AimTarget is { Alive: true } tgt && Now >= tgt.Phased)
            {
                p.Target = tgt.Pos;
                var want = (tgt.Pos - p.Pos).Normalized() * p.Speed;
                p.Vel = p.Vel.MoveToward(want, p.Speed * 6f * dt);
            }
            p.Pos += p.Vel * dt;

            // impact test: hit the tracked target, or any opposing unit the tracer passed near, or expire
            var hit = ProjectileHit(p);
            if (hit != null) { ResolveImpact(p, hit.Pos); _projectiles.RemoveAt(i); continue; }
            if (p.Life >= PROJ_MAX_LIFE || !InArenaLoose(p.Pos))
            {
                // a splash shot still bursts where it dies (a lobbed shell that lands short); a single shot just fizzles
                if (p.SplashRadius > 0) ResolveImpact(p, p.Pos);
                _projectiles.RemoveAt(i);
            }
        }
    }

    // Nearest opposing unit within the projectile's swept segment this frame (segment test avoids tunneling).
    private Unit? ProjectileHit(Projectile p)
    {
        Unit? best = null; var bd = float.MaxValue;
        foreach (var u in AllUnits())
        {
            if (!u.Alive) continue;
            var opposing = p.Team == UnitTeam.Enemy ? u.Team != UnitTeam.Enemy : u.Team == UnitTeam.Enemy;
            if (!opposing) continue;
            if (u.Team == UnitTeam.Enemy && Now < u.Phased) continue;   // can't hit a phased enemy
            var d = DistToSegment(u.Pos, p.PrevPos, p.Pos);
            if (d < u.Radius + p.Radius + PROJ_HIT_PAD && d < bd) { bd = d; best = u; }
        }
        return best;
    }

    // Apply a projectile's damage at impact â€” direct hit + optional splash + impact VFX.
    private void ResolveImpact(Projectile p, Vector2 at)
    {
        var col = ThemeColor(p.Tint);
        var friendly = p.Team != UnitTeam.Enemy;

        if (p.SplashRadius > 0)
        {
            // AoE: hit every opposing unit within SplashRadius, full at centre â†’ half at the rim
            foreach (var u in AllUnits())
            {
                if (!u.Alive) continue;
                var opposing = friendly ? u.Team == UnitTeam.Enemy : u.Team != UnitTeam.Enemy;
                if (!opposing) continue;
                var d = u.Pos.DistanceTo(at);
                if (d > p.SplashRadius) continue;
                var falloff = 1f - 0.5f * (d / p.SplashRadius);
                ApplyProjectileDamage(p, u, p.Damage * falloff, friendly);
            }
            // impact â€” a hot themed spark burst + a white flash core burst (bigger than a single hit). These are
            // particle NODES (they persist + render on their own); a matching draw-time shock ring is queued below so
            // the AoE footprint is readable inside the draw pass too.
            CraftFx.Burst(_arena, at, col, 20, 300f, 0.5f, 4f, 40f);
            CraftFx.Burst(_arena, at, Colors.White, 8, 200f, 0.35f, 3f, 20f);
            AddImpactRing(at, p.SplashRadius, new Color(CraftColor.Lighten(col, 0.4f), 0.95f), true);
        }
        else
        {
            // single target: hit the nearest opposing unit at the impact point
            Unit? victim = null; var bd = float.MaxValue;
            foreach (var u in AllUnits())
            {
                if (!u.Alive) continue;
                var opposing = friendly ? u.Team == UnitTeam.Enemy : u.Team != UnitTeam.Enemy;
                if (!opposing) continue;
                if (u.Team == UnitTeam.Enemy && Now < u.Phased) continue;
                var d = u.Pos.DistanceTo(at);
                if (d < u.Radius + p.Radius + PROJ_HIT_PAD && d < bd) { bd = d; victim = u; }
            }
            if (victim != null) ApplyProjectileDamage(p, victim, p.Damage, friendly);
            // single-hit impact â€” a small spark burst (particle node) + a quick contact ring (draw-pass). A crit is
            // brighter + a touch bigger so a lucky hit reads.
            var sparkCol = p.Crit ? CraftColor.Lighten(col, 0.4f) : col;
            CraftFx.Burst(_arena, at, sparkCol, p.Crit ? 14 : 7, p.Crit ? 260f : 170f, 0.4f, p.Crit ? 4f : 3f, 30f);
            AddImpactRing(at, p.Crit ? 14f : 8f, new Color(sparkCol, p.Crit ? 0.95f : 0.65f), false);
        }
    }

    private void ApplyProjectileDamage(Projectile p, Unit victim, float dmg, bool friendly)
    {
        var removed = Hurt(victim, dmg);
        if (friendly)
        {
            _heroDmgDealt += removed;
            if (p.Leech && Now < _heroBuff.LeechUntil) HealHero(removed * _heroBuff.LeechFrac);
            if (p.Toxic && victim.Team == UnitTeam.Enemy) AddPoison(victim);
        }
    }

    // --- small geometry helpers (no toolkit change) ---
    private static Vector2 AngleVec(float a) => new(Mathf.Cos(a), Mathf.Sin(a));

    private static float DistToSegment(Vector2 pt, Vector2 a, Vector2 b)
    {
        var ab = b - a;
        var len2 = ab.LengthSquared();
        if (len2 < 1e-6f) return pt.DistanceTo(a);
        var t = Mathf.Clamp((pt - a).Dot(ab) / len2, 0f, 1f);
        return pt.DistanceTo(a + ab * t);
    }

    private bool InArenaLoose(Vector2 p)
    {
        var ar = _arenaRect;
        const float pad = 24f;
        return p.X >= ar.Position.X - pad && p.X <= ar.Position.X + ar.Size.X + pad
            && p.Y >= ar.Position.Y - pad && p.Y <= ar.Position.Y + ar.Size.Y + pad;
    }

    private void AddPoison(Unit enemy)
    {
        for (var i = 0; i < _poison.Count; i++)
            if (_poison[i].U == enemy) { _poison[i] = (enemy, POISON_DPS, Now + POISON_DUR); return; }
        _poison.Add((enemy, POISON_DPS, Now + POISON_DUR));
    }

    private void TickPoison(float dt)
    {
        for (var i = _poison.Count - 1; i >= 0; i--)
        {
            var (u, dps, until) = _poison[i];
            if (u == null || !u.Alive || Now >= until) { _poison.RemoveAt(i); continue; }
            var removed = Hurt(u, dps * dt);
            _heroDmgDealt += removed;
        }
    }

    private void TickFields(float dt)
    {
        for (var i = _fields.Count - 1; i >= 0; i--)
        {
            var f = _fields[i];
            if (Now >= f.Until) { _fields.RemoveAt(i); continue; }
            switch (f.Kind)
            {
                case AbilityKind.SlowField:
                    foreach (var e in _enemies)
                        if (e.Alive && e.Pos.DistanceTo(f.Pos) < f.Radius)
                        { e.SlowUntil = Now + 0.2f; e.SlowFactor = f.Magnitude; }
                    break;
                case AbilityKind.Torrent:
                    if (_hero.Alive && _hero.Pos.DistanceTo(f.Pos) < f.Radius) HealHero(f.Magnitude * dt);
                    foreach (var a in _allies)
                        if (a.Alive && a.Pos.DistanceTo(f.Pos) < f.Radius) a.Hp = Mathf.Min(a.HpMax, a.Hp + f.Magnitude * dt);
                    // cleanse hero slow while in flow
                    if (_hero.Pos.DistanceTo(f.Pos) < f.Radius) _hero.SlowUntil = 0;
                    break;
                case AbilityKind.Nuke:
                    foreach (var e in _enemies)
                        if (e.Alive && e.Pos.DistanceTo(f.Pos) < f.Radius)
                        {
                            var removed = Hurt(e, f.Magnitude * dt);
                            _heroDmgDealt += removed;
                            if (Now < _heroBuff.LeechUntil) HealHero(removed * _heroBuff.LeechFrac);
                        }
                    break;
            }
        }
    }

    private void CullDead()
    {
        // enemies
        for (var i = _enemies.Count - 1; i >= 0; i--)
        {
            if (_enemies[i].Hp <= 0)
            {
                var e = _enemies[i];
                _enemiesKilled++;
                CraftFx.Burst(_arena, e.Pos, new Color(ThemeColor(_wave.Character), 0.9f), e.IsMiniBoss ? 30 : 14, 240f, 0.6f, 4f, 120f);
                if (e.IsMiniBoss) CraftFx.Burst(_arena, e.Pos, Colors.White, 14, 300f, 0.7f, 4f, 60f);
                AddDeathFx(e, enemy: true);
                _enemies.RemoveAt(i);
                // Life-rider regrow: 25% chance to spawn 1 half-HP Rusher (capped).
                if (_wave.Character == Theme.Life && _rng.NextDouble() < 0.25 && _regrown < (int)(_wave.TotalToSpawn * 0.3))
                {
                    if (_enemies.Count < MAX_ENEMIES_LIVE)
                    {
                        var r = MakeEnemy(EnemyKind.Rusher, e.Pos);
                        r.HpMax *= 0.5f; r.Hp = r.HpMax;
                        _enemies.Add(r);
                        _regrown++;
                        _enemiesTotal++;
                    }
                }
            }
        }
        // allies
        for (var i = _allies.Count - 1; i >= 0; i--)
            if (_allies[i].Hp <= 0)
            {
                var a = _allies[i];
                CraftFx.Burst(_arena, a.Pos, new Color(ThemeColor(a.Tint), 0.9f), 12, 200f, 0.55f, 3.5f, 120f);
                AddDeathFx(a, enemy: false);
                _allies.RemoveAt(i);
            }
        // dead ally units drop out of _allies here; their Selected/Cmd state dies with them. Friendly focus/AimTarget
        // refs pointing at culled enemies are cleared each tick (top of TickUnits + the `is { Alive: true }` guards).
    }

    private int _regrown;

    // COSMETIC: register a death-dissolve marker at a culled unit's last position (drawn + expired in the draw layer).
    private void AddDeathFx(Unit u, bool enemy)
    {
        if (_deaths.Count > 48) _deaths.RemoveAt(0);   // hard cap â€” never let VFX unbounded-grow
        _deaths.Add(new DeathFx
        {
            Pos = u.Pos,
            Radius = u.Radius,
            Until = Now + DEATH_FX_DUR,
            Born = Now,
            Col = ThemeColor(u.Tint),
            Big = u.IsMiniBoss,
            Enemy = enemy,
        });
    }

    // COSMETIC: queue a short expanding impact ring for the draw pass (splash = big shock ring, single = small kick).
    private void AddImpactRing(Vector2 at, float baseR, Color col, bool splash)
    {
        if (_impacts.Count > 40) _impacts.RemoveAt(0);
        _impacts.Add(new ImpactRing
        {
            Pos = at, BaseR = baseR, Until = Now + IMPACT_RING_DUR, Born = Now,
            Col = col, Width = splash ? 3.5f : 2f, Spread = splash ? 0.9f : 1.3f,
        });
    }

    private IEnumerable<Unit> AllUnits()
    {
        if (_hero.Alive) yield return _hero;
        foreach (var a in _allies) yield return a;
        foreach (var e in _enemies) yield return e;
    }

    private Vector2 ClampToArena(Vector2 p, Rect2 ar)
        => new(Mathf.Clamp(p.X, ar.Position.X, ar.Position.X + ar.Size.X),
               Mathf.Clamp(p.Y, ar.Position.Y, ar.Position.Y + ar.Size.Y));

    // ============================================================= Â§4.6 SCORING

    private double ComputePerf()
    {
        // SQUAD SURVIVAL â€” how many of your combatants live AND how healthy they end (hero + allies).
        // Dead allies are culled from _allies, so they contribute 0 HP: this captures "combatants alive
        // and health" directly. Summoned reinforcements can offset losses (capped at full).
        float squadHpNow = _hero.Alive ? _hero.Hp : 0f;
        foreach (var a in _allies) if (a.Alive) squadHpNow += a.Hp;
        double squadHealthFrac = _squadHpMaxTotal > 0 ? Math.Clamp(squadHpNow / _squadHpMaxTotal, 0, 1) : 0;

        double waveClearedFrac = _enemiesTotal > 0 ? Math.Clamp((double)_enemiesKilled / _enemiesTotal, 0, 1) : 1;

        // You must WIN (clear the wave) to score well; squad health then sets the band.
        //   cleared + full squad            â†’ ~1.00  (Legendary)
        //   cleared + ~88% squad health     â†’ ~0.90  (Legendary floor)
        //   cleared + ~65% squad health     â†’ ~0.69  (Superior)
        //   enemies left alive multiplies everything down, so a sloppy/pyrrhic win can't reach Legendary.
        double raw = waveClearedFrac * (0.12 + 0.88 * squadHealthFrac);
        if (_heroDied) raw *= 0.5;   // losing the hero can never be a great craft

        return Math.Clamp(Math.Max(raw, PERF_FLOOR), 0, 1);
    }

    // ================================================================ Â§5 INPUT

    public override void _Input(InputEvent @event)
    {
        if (!Running) return;
        if (@event is not InputEventKey { Pressed: true, Echo: false } k) return;
        if (_dev.NotesEditHasFocus && k.PhysicalKeycode is not (Key.F1 or Key.F7)) return;   // typing a note
        // claim F1/F7 at the earliest stage so they never reach the world's global debug handler.
        if (_dev.HandleKey(k.PhysicalKeycode)) { GetViewport().SetInputAsHandled(); _arena.QueueRedraw(); }
    }

    protected override void OnInput(InputEvent @event)
    {
        // F1/F7 are claimed in _Input; here we handle gameplay keys (the base already ate Esc).
        if (@event is InputEventKey { Pressed: true, Echo: false } k)
        {
            if (_dev.NotesEditHasFocus) return;
            switch (k.PhysicalKeycode)
            {
                case Key.Space:
                    if (_phase == Phase.Ready) { _phase = Phase.Countdown; _countdown = 3.0; GetViewport().SetInputAsHandled(); }
                    break;
                case Key.Q: if (_phase == Phase.Play) { CastAbility(AbilitySlot.Q); GetViewport().SetInputAsHandled(); } break;
                case Key.W: if (_phase == Phase.Play) { CastAbility(AbilitySlot.W); GetViewport().SetInputAsHandled(); } break;
                case Key.E: if (_phase == Phase.Play) { CastAbility(AbilitySlot.E); GetViewport().SetInputAsHandled(); } break;
                case Key.R: break;   // passive â€” ignored
                case Key.A:
                    // SC2 attack-move: arm it; the next left-click issues the attack-move to that point.
                    if (_phase == Phase.Play) { _attackMoveArmed = true; GetViewport().SetInputAsHandled(); }
                    break;
                case Key.Escape:
                    // let the base handle abandon; but cancel an armed attack-move first (harmless â€” no SetInputAsHandled)
                    _attackMoveArmed = false;
                    break;
            }
        }
    }

    // SC2-style pointer handling: left-click select / left-drag box-select / shift-add / right-click move-or-attack /
    // A+left-click attack-move. All hit-tests are in arena-local pixels (the arena Control's own space).
    private void OnArenaInput(InputEvent @event)
    {
        if (@event is InputEventMouseMotion)
        {
            _cursor = _arena.GetLocalMousePosition();
            if (_boxDragging) _boxCur = _cursor;
            return;
        }
        if (@event is not InputEventMouseButton mb) return;
        _cursor = mb.Position;

        if (_phase == Phase.Ready)
        {
            if (mb.Pressed) { _phase = Phase.Countdown; _countdown = 3.0; }
            return;
        }
        if (_phase != Phase.Play) return;

        if (mb.ButtonIndex == MouseButton.Left)
        {
            if (mb.Pressed) OnLeftDown(mb.Position, mb.ShiftPressed);
            else OnLeftUp(mb.Position, mb.ShiftPressed);
        }
        else if (mb.ButtonIndex == MouseButton.Right && mb.Pressed)
        {
            OnRightClick(mb.Position);
        }
    }

    private void OnLeftDown(Vector2 p, bool shift)
    {
        // an armed attack-move consumes the left-click as a command, not a selection.
        if (_attackMoveArmed)
        {
            IssueAttackMove(p);
            _attackMoveArmed = false;
            return;
        }
        // begin a potential drag-box; the real select/box decision happens on release (based on drag distance).
        _boxDragging = true;
        _boxStart = p;
        _boxCur = p;
    }

    private void OnLeftUp(Vector2 p, bool shift)
    {
        if (!_boxDragging) return;
        _boxDragging = false;
        var dragDist = _boxStart.DistanceTo(p);

        if (dragDist >= SELECT_DRAG_MIN)
        {
            // BOX select: friendlies whose body centre is inside the rect (shift = add to the current selection)
            var rect = RectFrom(_boxStart, p);
            if (!shift) ClearSelection();
            var any = false;
            foreach (var f in Friendlies())
            {
                if (!f.Alive) continue;
                if (rect.HasPoint(f.Pos)) { f.Selected = true; any = true; }
            }
            // a box that caught nothing and wasn't additive clears selection (SC2 behaviour)
            if (!any && !shift) ClearSelection();
            return;
        }

        // CLICK select: nearest friendly under the cursor
        var hit = FriendlyAt(p);
        if (hit != null)
        {
            if (shift) hit.Selected = !hit.Selected;         // shift toggles this unit in/out of the group
            else { ClearSelection(); hit.Selected = true; }  // plain click = select just this one
        }
        else if (!shift)
        {
            ClearSelection();   // click on empty ground deselects (unless shift)
        }
    }

    private void OnRightClick(Vector2 p)
    {
        _attackMoveArmed = false;
        var enemy = EnemyAt(p);
        if (enemy != null)
        {
            // right-click ON an enemy = focus-attack it with the whole selection
            foreach (var u in Selected()) { u.CmdFocus = enemy; u.Cmd = CmdMode.None; }
            AddPing(enemy.Pos, true);
        }
        else
        {
            // right-click empty ground = MOVE (ignore enemies en route)
            foreach (var u in Selected()) { u.Cmd = CmdMode.Move; u.CmdPoint = p; u.CmdFocus = null; }
            AddPing(p, false);
        }
    }

    private void IssueAttackMove(Vector2 p)
    {
        foreach (var u in Selected()) { u.Cmd = CmdMode.AttackMove; u.CmdPoint = p; u.CmdFocus = null; }
        AddPing(p, true);
    }

    private void AddPing(Vector2 pos, bool attack)
        => _pings.Add(new CmdPing { Pos = pos, Until = Now + CMD_PING_DUR, Attack = attack, Col = attack ? LowRed : AllyGreen });

    private static Rect2 RectFrom(Vector2 a, Vector2 b)
        => new(new Vector2(Mathf.Min(a.X, b.X), Mathf.Min(a.Y, b.Y)), (b - a).Abs());

    private Unit? FriendlyAt(Vector2 p)
    {
        Unit? best = null; var bd = float.MaxValue;
        foreach (var f in Friendlies())
        {
            if (!f.Alive) continue;
            var d = p.DistanceTo(f.Pos);
            if (d < f.Radius + 8f && d < bd) { bd = d; best = f; }
        }
        return best;
    }

    private Unit? EnemyAt(Vector2 p)
    {
        Unit? best = null; var bd = float.MaxValue;
        foreach (var e in _enemies)
        {
            if (!e.Alive) continue;
            var d = p.DistanceTo(e.Pos);
            if (d < e.Radius + 10f && d < bd) { bd = d; best = e; }
        }
        return best;
    }

    // ============================================================= Â§5 CASTING

    private void CastAbility(AbilitySlot slot)
    {
        var ability = _loadout.Abilities[(int)slot];
        if (!ability.Ready) return;
        ability.CdTimer = ability.Cooldown;
        _abilitiesCast++;

        var castPoint = ability.Targeted ? _cursor : _hero.Pos;
        var col = ThemeColor(ability.Source);
        var useful = false;

        switch (ability.Kind)
        {
            case AbilityKind.Nuke:
            {
                var hit = 0;
                foreach (var e in _enemies)
                    if (e.Alive && e.Pos.DistanceTo(castPoint) < ability.Radius)
                    {
                        var removed = Hurt(e, ability.Magnitude);
                        _heroDmgDealt += removed;
                        if (Now < _heroBuff.LeechUntil) HealHero(removed * _heroBuff.LeechFrac);
                        if (_hasToxic) AddPoison(e);
                        hit++;
                    }
                PushField(AbilityKind.Nuke, castPoint, ability.Radius, ability.Magnitude / Mathf.Max(0.1f, ability.Duration), ability.Duration, ability.Source);
                CraftFx.Burst(_arena, castPoint, col, 26, 320f, 0.7f, 5f, 60f);
                useful = hit >= 1;
                break;
            }
            case AbilityKind.SlowField:
            {
                var overlap = _enemies.Any(e => e.Alive && e.Pos.DistanceTo(castPoint) < ability.Radius);
                PushField(AbilityKind.SlowField, castPoint, ability.Radius, Mathf.Clamp(1f - ability.Magnitude, 0.35f, 1f), ability.Duration, ability.Source);
                CraftFx.RingPulse(_arena, castPoint, ability.Radius, 0f, new Color(col, 0.8f));
                useful = overlap;
                break;
            }
            case AbilityKind.Bulwark:
            {
                _hero.Shield = ability.Magnitude;
                _activeTauntUntil = Now + ability.Duration;
                CraftFx.Ring(_arena, _hero.Pos, _hero.Radius + 8, new Color(ThemeColor(Theme.Earth), 0.7f), 3f);
                useful = _enemies.Any(e => e.Alive && e.Pos.DistanceTo(_hero.Pos) < ability.Radius);   // taunt reach
                break;
            }
            case AbilityKind.Rally:
            {
                var lowAlly = _allies.Where(a => a.Alive).OrderBy(a => a.Hp / a.HpMax).FirstOrDefault();
                var anyHurt = (_hero.Alive && _hero.Hp < _hero.HpMax * 0.9f) || _allies.Any(a => a.Alive && a.Hp < a.HpMax * 0.9f);
                if (lowAlly != null && lowAlly.Hp < lowAlly.HpMax)
                    lowAlly.Hp = Mathf.Min(lowAlly.HpMax, lowAlly.Hp + ability.Magnitude);
                else
                    SpawnAlly(AllyKind.Sprout, ability.Rank, _hero.Pos + new Vector2(30, -30));
                CraftFx.Burst(_arena, _hero.Pos, col, 16, 180f, 0.6f, 4f, -60f);
                useful = anyHurt || _allies.Count > 0;
                break;
            }
            case AbilityKind.Leech:
            {
                var hit = 0; float healed = 0;
                _heroBuff.LeechFrac = 0.6f; _heroBuff.LeechUntil = Now + 3f;   // nova window
                foreach (var e in _enemies)
                    if (e.Alive && e.Pos.DistanceTo(_hero.Pos) < ability.Radius)
                    {
                        var removed = Hurt(e, ability.Magnitude);
                        _heroDmgDealt += removed;
                        healed += removed * _heroBuff.LeechFrac;
                        hit++;
                    }
                // self 8% HP cost
                _hero.Hp = Mathf.Max(1, _hero.Hp - _hero.HpMax * 0.08f);
                HealHero(healed);
                CraftFx.RingPulse(_arena, _hero.Pos, ability.Radius, 0f, new Color(ThemeColor(Theme.Shadow), 0.85f));
                useful = hit >= 1;
                break;
            }
            case AbilityKind.Blink:
            {
                var prePos = _hero.Pos;
                var before = ImminentThreats(prePos);
                var dir = (_cursor - _hero.Pos);
                dir = dir.Length() > 1e-3f ? dir.Normalized() : Vector2.Right;
                var dash = Mathf.Min(ability.Magnitude, (_cursor - _hero.Pos).Length());
                _hero.Pos = ClampToArena(_hero.Pos + dir * dash, _arenaRect);
                _heroBuff.HasteUntil = Now + ability.Duration; _heroBuff.HasteMul = 1.5f;
                var after = ImminentThreats(_hero.Pos);
                CraftFx.Wake(_arena, prePos, _hero.Pos, new Color(col, 0.5f));
                useful = before >= 1 && after < before;
                break;
            }
            case AbilityKind.Torrent:
            {
                var anyHurt = _hero.Hp < _hero.HpMax * 0.9f || _allies.Any(a => a.Alive && a.Hp < a.HpMax * 0.9f);
                PushField(AbilityKind.Torrent, _hero.Pos, ability.Radius, ability.Magnitude, ability.Duration, ability.Source);
                _hero.SlowUntil = 0;   // cleanse
                useful = anyHurt;
                break;
            }
        }

        if (useful) _abilitiesLandedValue++;
        _dev.Log($"CAST {slot} {ability.Kind} r{ability.Rank} {(useful ? "hit" : "miss")}");
        Shake(4f);
    }

    private int ImminentThreats(Vector2 pos)
    {
        var n = 0;
        foreach (var e in _enemies)
        {
            if (!e.Alive) continue;
            var reach = e.Radius + _hero.Radius + ATK_REACH + e.MoveSpeed * BLINK_LOOKAHEAD;
            if (e.Pos.DistanceTo(pos) < reach) n++;
        }
        return n;
    }

    private void PushField(AbilityKind kind, Vector2 pos, float radius, float mag, float dur, Theme src)
    {
        if (_fields.Count >= MAX_FIELDS) _fields.RemoveAt(0);
        _fields.Add(new FieldEffect { Kind = kind, Pos = pos, Radius = radius, Magnitude = mag, Until = Now + dur, Started = Now, Source = src });
    }

    // ================================================================ Â§6 DRAW

    private void DrawArena()
    {
        _arenaRect = ComputeArenaRect();
        var font = _arena.GetThemeDefaultFont();
        var ar = _arenaRect;

        // z0: floor plate â€” a warm forge-stone bed with a soft topâ†’bottom vertical shade so the arena reads as a lit
        // surface rather than a flat card. Bands are cheap (no shader); the round outer plate frames it.
        CraftFx.RoundRect(_arena, ar, new Color(0.10f, 0.06f, 0.04f), new Color(0.30f, 0.18f, 0.11f), 2, 14);
        {
            const int bands = 26;
            var topShade = new Color(0.135f, 0.082f, 0.055f);
            var botShade = new Color(0.055f, 0.032f, 0.024f);
            for (var i = 0; i < bands; i++)
            {
                var t = i / (float)bands; var st = t * t * (3 - 2 * t);   // smoothstep
                _arena.DrawRect(new Rect2(ar.Position.X, ar.Position.Y + ar.Size.Y * t, ar.Size.X, ar.Size.Y / bands + 1.5f),
                    new Color(topShade.Lerp(botShade, st), 0.62f));
            }
        }
        var aw = _arena.Size.X;
        for (var gx = ar.Position.X; gx < ar.Position.X + ar.Size.X; gx += aw * 0.08f)
            _arena.DrawLine(new Vector2(gx, ar.Position.Y), new Vector2(gx, ar.Position.Y + ar.Size.Y), new Color(0, 0, 0, 0.10f), 1f);
        for (var gy = ar.Position.Y; gy < ar.Position.Y + ar.Size.Y; gy += aw * 0.08f)
            _arena.DrawLine(new Vector2(ar.Position.X, gy), new Vector2(ar.Position.X + ar.Size.X, gy), new Color(0, 0, 0, 0.10f), 1f);

        // z1: forge-heat pool â€” a gently breathing warm glow pooled toward the lower-centre (where the hero stands), so
        // the middle of the arena reads hotter/brighter and the important action pops out of a darker rim.
        var heatPos = ar.Position + new Vector2(ar.Size.X * 0.5f, ar.Size.Y * 0.62f);
        var breathe = 0.09f + 0.025f * Mathf.Sin((float)_anim * 1.3f);
        CraftFx.Glow(_arena, heatPos, ar.Size.Y * 0.34f, new Color(GlowCol, breathe), 7);
        CraftFx.Glow(_arena, heatPos, ar.Size.Y * 0.16f, new Color(EmberCol, 0.07f), 5);

        // z1.1: contact vignette â€” darken the four inner edges so units near the middle feel lit and the rim recedes.
        {
            var vig = new Color(0, 0, 0, 0.05f);
            for (var b = 6; b >= 1; b--)
            {
                var d = ar.Size.Y * 0.03f * b;
                _arena.DrawRect(new Rect2(ar.Position.X, ar.Position.Y, ar.Size.X, d), vig);
                _arena.DrawRect(new Rect2(ar.Position.X, ar.Position.Y + ar.Size.Y - d, ar.Size.X, d), vig);
                _arena.DrawRect(new Rect2(ar.Position.X, ar.Position.Y, d, ar.Size.Y), vig);
                _arena.DrawRect(new Rect2(ar.Position.X + ar.Size.X - d, ar.Position.Y, d, ar.Size.Y), vig);
            }
        }

        // z2: spawn telegraphs â€” a warning glow pool + a converging pulse ring + a "!" so an incoming foe reads early.
        foreach (var tg in _telegraphs)
        {
            var remaining = tg.At - Now;
            var total = tg.Boss ? BOSS_TELL : SPAWN_TELL;
            var phase = Mathf.Clamp(1 - remaining / total, 0f, 1f);
            var r = tg.Boss ? 34f : 22f;
            var tcol = ThemeColor(_wave.Character);
            var warn = tg.Boss ? Accent2 : tcol;
            // pulsing warning pool (brighter as spawn nears)
            _arena.DrawCircle(tg.Pos, r * 0.7f, new Color(warn, (0.06f + 0.12f * phase)));
            // a ring that CONVERGES inward as the spawn approaches (reads as "charging up")
            CraftFx.Ring(_arena, tg.Pos, r * (1.4f - 0.4f * phase), new Color(warn, 0.35f + 0.5f * phase), tg.Boss ? 3f : 2f);
            CraftFx.RingPulse(_arena, tg.Pos, r, phase, new Color(warn, 0.85f), 3f);
            if (font != null)
            {
                CraftFx.Glow(_arena, tg.Pos, 10f, new Color(warn, 0.25f * phase), 4);
                _arena.DrawString(font, tg.Pos - new Vector2(4, -6), "!", HorizontalAlignment.Left, -1, tg.Boss ? 26 : 20, new Color(CraftColor.Lighten(warn, 0.3f), 0.95f));
            }
        }

        // z3: field effects
        DrawFields();

        // z3.5: RANGE RINGS under selected units â€” a faint filled disc + a crisper ring showing each selected unit's
        // attack reach (so the player can read who threatens what). Kept subtle so it never muddies the action.
        if (_phase == Phase.Play)
            foreach (var f in Friendlies())
                if (f.Selected && f.Alive && f.Range > 1)
                {
                    var rc = ThemeColor(f.Tint);
                    _arena.DrawCircle(f.Pos, f.Range, new Color(rc, 0.045f));
                    CraftFx.Ring(_arena, f.Pos, f.Range, new Color(CraftColor.Lighten(rc, 0.2f), 0.22f), 1.5f, 44);
                }

        // z3.6: command pings (green move / red attack) at the target ground
        DrawCommandPings();

        // z3.7: death dissolves â€” a themed collapsing burst where a unit just fell (drawn under living bodies)
        DrawDeaths();

        // z4-7: shadows, enemies, allies, hero
        foreach (var u in AllUnits()) DrawShadow(u);
        foreach (var e in _enemies) DrawEnemy(e);
        foreach (var a in _allies) DrawAlly(a);
        if (_hero.Alive || _phase == Phase.Settle) DrawHero();

        // z7.5: PROJECTILES + tracers (over bodies so the shots read clearly) â€” the heart of "animations matter"
        DrawProjectiles();

        // z7.6: impact shock rings (expand + fade over the bodies where shots landed)
        DrawImpacts();

        // z8: HP bars
        foreach (var u in AllUnits()) DrawHpBar(u);

        // z8.5: selection brackets + reload arcs on selected friendlies (read reload speed)
        if (_phase == Phase.Play)
            foreach (var f in Friendlies())
                if (f.Selected && f.Alive) DrawSelectionMarks(f);

        // z9: aim reticle
        DrawReticle();

        // z10: move-target marker (hero legacy marker; group pings already drawn at z3.6)
        if (_hasMoveTarget)
            CraftFx.RingPulse(_arena, _moveTarget, 10, (float)((_anim * 1.5) % 1.0), new Color(Accent2, 0.7f));

        // z11: drag-select box
        if (_boxDragging)
        {
            var rect = RectFrom(_boxStart, _boxCur);
            _arena.DrawRect(rect, new Color(AllyGreen, 0.10f));
            _arena.DrawRect(rect, new Color(AllyGreen, 0.7f), false, 1.5f);
        }

        // z11.5: attack-move armed hint â€” a red reticle at the cursor telling the player the next click is an A-move
        if (_attackMoveArmed && font != null)
        {
            CraftFx.Ring(_arena, _cursor, 14, new Color(LowRed, 0.85f), 2f);
            _arena.DrawString(font, _cursor + new Vector2(16, 5), "ATTACK", HorizontalAlignment.Left, -1, 13, new Color(LowRed, 0.9f));
        }

        // z9.5: numeric-UI kill-progress bar (under the timer, feel not "12/20")
        if (font != null && _phase is Phase.Play or Phase.Settle)
        {
            var barRect = new Rect2(_arena.Size.X * 0.5f - 90, 74, 180, 8);
            var frac = _enemiesTotal > 0 ? (float)_enemiesKilled / _enemiesTotal : 1f;
            CraftFx.Bar(_arena, barRect, frac, new Color(0, 0, 0, 0.55f), Accent2, 4);
        }

        // z12: persistent controls legend (bottom strip) â€” always on-screen so nothing must be memorised
        if (font != null && _phase is Phase.Play or Phase.Ready)
        {
            const string legend = "L-CLICK select   Â·   DRAG box   Â·   SHIFT add   Â·   R-CLICK move / attack   Â·   A attack-move   Â·   Q W E cast";
            float lw = font.GetStringSize(legend, HorizontalAlignment.Left, -1, 14).X;
            _arena.DrawString(font, new Vector2(_arena.Size.X * 0.5f - lw * 0.5f, _arena.Size.Y - 22),
                legend, HorizontalAlignment.Left, -1, 14, new Color(0.85f, 0.88f, 0.95f, 0.72f));
        }

        // z13: countdown / settle banner
        DrawBanner(font);

        // ready-screen loadout preview
        if (_phase == Phase.Ready) DrawReadyCard(font);

        // z14: F1 dev log
        if (_dev.ShowLog && font != null)
        {
            var logRect = new Rect2(_arena.Size.X - 260, _arena.Size.Y * 0.12f, 250, _arena.Size.Y * 0.6f);
            _dev.DrawLog(_arena, logRect, font, PinnedStatus());
        }
    }

    private IReadOnlyList<(string, Color)> PinnedStatus() => new List<(string, Color)>
    {
        ($"hero {_loadout.HeroTheme} hp {_hero.Hp:0}/{_hero.HpMax:0}", Accent2),
        ($"wave {_wave.Character} {_enemiesKilled}/{_enemiesTotal}", new Color(ThemeColor(_wave.Character))),
        ($"perf {ComputePerf() * 100:0}%", Ink),
    };

    private void DrawShadow(Unit u)
    {
        // a soft two-layer contact ellipse: a wide faint penumbra + a tighter darker core, so the unit reads as
        // resting ON the forge floor (grounded) rather than floating. Spawn-fade keeps a newly-arrived unit subtle.
        var a = SpawnAlpha(u);
        var at = u.Pos + new Vector2(0, u.Radius * 0.72f);
        var outer = CraftFx.Ellipse(at, u.Radius * 1.15f, u.Radius * 0.46f);
        _arena.DrawColoredPolygon(outer, new Color(0, 0, 0, 0.16f * a));
        var core = CraftFx.Ellipse(at, u.Radius * 0.82f, u.Radius * 0.32f);
        _arena.DrawColoredPolygon(core, new Color(0, 0, 0, 0.34f * a));
    }

    // Themed death dissolve â€” a collapsing body ghost + an outward ring, tinted by the fallen unit's theme. Cosmetic.
    private void DrawDeaths()
    {
        foreach (var d in _deaths)
        {
            var life = Mathf.Clamp((Now - d.Born) / DEATH_FX_DUR, 0f, 1f);   // 0 â†’ 1
            var fade = 1f - life;
            // shrinking, brightening body ghost
            var ghostR = d.Radius * (1f - 0.7f * life);
            _arena.DrawCircle(d.Pos, ghostR, new Color(CraftColor.Lighten(d.Col, 0.4f), 0.5f * fade));
            // outward shock ring â€” bigger for a boss
            var ringBase = d.Radius * (d.Big ? 1.6f : 1.1f);
            CraftFx.RingPulse(_arena, d.Pos, ringBase, life, new Color(d.Col, 0.85f), d.Big ? 3.5f : 2f, d.Big ? 1.4f : 0.9f);
            // a bright core spark that fades fast
            if (life < 0.5f)
                CraftFx.Glow(_arena, d.Pos, d.Radius * (1.4f - life), new Color(Colors.White, 0.45f * (1f - life * 2f)), 4);
        }
    }

    // Expanding impact rings queued from projectile hits (resolved in the sim tick). Cosmetic.
    private void DrawImpacts()
    {
        foreach (var im in _impacts)
        {
            var life = Mathf.Clamp((Now - im.Born) / IMPACT_RING_DUR, 0f, 1f);
            CraftFx.RingPulse(_arena, im.Pos, im.BaseR, life, im.Col, im.Width, im.Spread);
        }
    }

    private float SpawnAlpha(Unit u) => Mathf.Clamp((Now - u.SpawnT) / 0.25f, 0f, 1f);

    // A shot in flight: a bright head + a fading tapered tracer along its recent path. Splash shots draw a small
    // pulsing halo so the player can read "this one will burst." Colour is the firer's theme.
    private void DrawProjectiles()
    {
        foreach (var p in _projectiles)
        {
            var col = ThemeColor(p.Tint);
            var head = p.Crit ? CraftColor.Lighten(col, 0.4f) : CraftColor.Lighten(col, 0.15f);
            var vdir = p.Vel.LengthSquared() > 1e-3f ? p.Vel.Normalized() : Vector2.Right;
            // tracer trail â€” a longer TAPERED streak (thick at the head â†’ thin + fading at the tail) so even fast
            // shots leave a readable comet-tail. A soft under-glow along the streak gives it body.
            var tailLen = p.Radius * 5f + 10f + (p.Crit ? 6f : 0f);
            var tail = p.Pos - vdir * tailLen;
            CraftFx.Streak(_arena, tail, p.Pos, new Color(col, 0.35f), p.Radius * 2.4f, 8);   // soft wide under-trail
            CraftFx.Streak(_arena, tail, p.Pos, new Color(head, 0.9f), p.Radius * 1.3f, 8);    // bright core trail
            // glowing head + white-hot centre
            CraftFx.Glow(_arena, p.Pos, p.Radius * 2.7f, new Color(head, 0.55f), 5);
            _arena.DrawCircle(p.Pos, p.Radius, new Color(head, 0.97f));
            _arena.DrawCircle(p.Pos, p.Radius * 0.5f, new Color(1, 1, 1, 0.95f));
            // splash marker â€” a faint pulsing ring hint that this projectile is AoE (will burst)
            if (p.SplashRadius > 0)
            {
                var ph = (float)((_anim * 2.2 + p.Life) % 1.0);
                CraftFx.RingPulse(_arena, p.Pos, p.Radius * 3.4f, ph, new Color(head, 0.55f), 1.5f, 0.5f);
            }
        }
    }

    // Green move ping / red attack ping â€” a quick shrinking ring at the commanded ground point.
    private void DrawCommandPings()
    {
        foreach (var ping in _pings)
        {
            var t = Mathf.Clamp((ping.Until - Now) / CMD_PING_DUR, 0f, 1f);   // 1 â†’ 0 as it ages
            var age = 1f - t;
            // a crisp expanding ring + a faint trailing echo ring for a satisfying "command landed" pop
            var r = 6f + 18f * age;
            CraftFx.Ring(_arena, ping.Pos, r, new Color(ping.Col, 0.25f + 0.65f * t), 2.5f);
            CraftFx.Ring(_arena, ping.Pos, r + 6f * age, new Color(ping.Col, 0.4f * t), 1.5f);
            // a small centre dot at the target ground
            _arena.DrawCircle(ping.Pos, 2.5f, new Color(ping.Col, 0.5f + 0.4f * t));
            if (ping.Attack)
            {
                // a small red X for attack pings (plain diagonal lines â€” no glyph tofu)
                var d = 5f;
                _arena.DrawLine(ping.Pos + new Vector2(-d, -d), ping.Pos + new Vector2(d, d), new Color(ping.Col, 0.7f * t + 0.2f), 2f);
                _arena.DrawLine(ping.Pos + new Vector2(-d, d), ping.Pos + new Vector2(d, -d), new Color(ping.Col, 0.7f * t + 0.2f), 2f);
            }
        }
    }

    // A selected friendly gets: a corner bracket (the selection read) + a reload arc (fills up â†’ ready to fire).
    private void DrawSelectionMarks(Unit u)
    {
        var r = u.Radius + 6f;
        // a soft pulsing under-glow ring + crisp corner brackets â€” the classic RTS selection read (no glyphs).
        var pulse = 0.5f + 0.5f * Mathf.Sin((float)_anim * 5f);
        CraftFx.Ring(_arena, u.Pos, r + 1.5f, new Color(AllyGreen, 0.18f + 0.16f * pulse), 3f);
        var col = new Color(AllyGreen, 0.98f);
        var arm = r * 0.55f;
        foreach (var (cx, cy) in new[] { (-1, -1), (1, -1), (-1, 1), (1, 1) })
        {
            var corner = u.Pos + new Vector2(cx * r, cy * r);
            // a faint dark backing stroke makes the bright bracket pop on any body colour
            _arena.DrawLine(corner, corner - new Vector2(cx * arm, 0), new Color(0, 0, 0, 0.45f), 3.5f);
            _arena.DrawLine(corner, corner - new Vector2(0, cy * arm), new Color(0, 0, 0, 0.45f), 3.5f);
            _arena.DrawLine(corner, corner - new Vector2(cx * arm, 0), col, 2f);
            _arena.DrawLine(corner, corner - new Vector2(0, cy * arm), col, 2f);
        }

        // reload arc â€” a thin ring that FILLS as the unit's attack cools down (empty = just fired, full = ready).
        var reloadR = r + 4f;
        var frac = 1f;   // ready
        if (u.Windup > 0 && u.WindupLen > 0)
            frac = 1f;   // winding up = charged (about to fire) â†’ show full + a hot tint
        else if (u.AttackTimer > 0 && u.AttackCd > 0)
            frac = Mathf.Clamp(1f - u.AttackTimer / u.AttackCd, 0f, 1f);
        var start = -Mathf.Pi / 2f;
        // faint full track
        CraftFx.Ring(_arena, u.Pos, reloadR, new Color(0, 0, 0, 0.35f), 2f);
        if (frac > 0.01f)
        {
            var arcCol = frac >= 0.999f ? new Color(1f, 0.95f, 0.5f, 0.95f) : new Color(AllyGreen, 0.85f);
            _arena.DrawArc(u.Pos, reloadR, start, start + Mathf.Tau * frac, 40, arcCol, 2.5f);
        }
    }

    // The attack TELL every unit shares (allies AND enemies â€” the player's top ask). Two beats:
    //  â€¢ WINDUP: a hot charging spark at the muzzle that grows + a lean/flash on the body as the shot readies.
    //  â€¢ MUZZLE FLASH: a bright pop at the barrel the frame the shot leaves.
    // Returns the body draw offset (the "lean" toward the aim) so the caller can shift the body a couple px.
    private Vector2 DrawAttackTell(Unit u, float bodyR, float alpha = 1f)
    {
        var col = ThemeColor(u.Tint);
        var aimDir = AngleVec(u.Facing);
        var muzzle = u.Pos + aimDir * (bodyR + 3f);
        var lean = Vector2.Zero;

        if (u.Windup > 0 && u.WindupLen > 0)
        {
            var charge = Mathf.Clamp(1f - u.Windup / u.WindupLen, 0f, 1f);   // 0 â†’ 1 as it nears firing
            var lit = CraftColor.Lighten(col, 0.35f);
            // ANTICIPATION: the body pulls BACK from the aim early in the windup, then eases FORWARD as it releases â€”
            // classic anticipation read. (Pure draw offset; the sim body position is unchanged.)
            lean = aimDir * (-2.5f * (1f - charge) + 4.5f * charge);
            // a converging charge halo that TIGHTENS onto the muzzle as the shot readies (energy gathering)
            var haloR = 12f * (1f - charge) + 4f;
            CraftFx.Ring(_arena, muzzle, haloR, new Color(lit, (0.25f + 0.45f * charge) * alpha), 1.5f);
            // growing hot core spark at the muzzle
            CraftFx.Glow(_arena, muzzle, (3f + 8f * charge), new Color(lit, (0.5f + 0.5f * charge) * alpha), 5);
            // a brightening charge line from body to muzzle
            CraftFx.Streak(_arena, u.Pos, muzzle + aimDir * (6f * charge), new Color(CraftColor.Lighten(col, 0.45f), (0.55f + 0.45f * charge) * alpha), 2.6f);
        }

        if (u.MuzzleFlash > 0)
        {
            var m = u.MuzzleFlash;
            // bright bloom + a hot ring kick + a white-hot core â€” a satisfying "crack" on release
            CraftFx.Glow(_arena, muzzle, (8f + 9f * m), new Color(1f, 0.95f, 0.72f, 0.9f * m * alpha), 6);
            CraftFx.Ring(_arena, muzzle, 4f + 9f * m, new Color(CraftColor.Lighten(col, 0.6f), 0.7f * m * alpha), 2f);
            _arena.DrawCircle(muzzle, 3.5f + 2.5f * m, new Color(1, 1, 1, 0.9f * m * alpha));
        }
        return lean;
    }

    // COSMETIC: a small body-scale pulse driven by attack state â€” a brief squash on windup and a recoil pop on the
    // muzzle flash. Returns a multiplier around 1.0; pure presentation (feeds only the body draw radius).
    private float AttackSquash(Unit u)
    {
        var s = 1f;
        if (u.Windup > 0 && u.WindupLen > 0)
        {
            var charge = Mathf.Clamp(1f - u.Windup / u.WindupLen, 0f, 1f);
            s *= 1f - 0.06f * charge;   // squash down as it charges
        }
        if (u.MuzzleFlash > 0) s *= 1f + 0.10f * u.MuzzleFlash;   // pop on release
        return s;
    }

    // A short facing spike (a rendered "nose") toward the aim â€” the small facing indicator every unit shares.
    private void DrawFacingSpike(Vector2 pos, float facing, float bodyR, Color col, float alpha, float lenMul = 0.95f)
    {
        var dir = AngleVec(facing);
        var perp = new Vector2(-dir.Y, dir.X);
        var tip = pos + dir * bodyR * (1f + lenMul);
        var baseA = pos + perp * bodyR * 0.42f + dir * bodyR * 0.6f;
        var baseB = pos - perp * bodyR * 0.42f + dir * bodyR * 0.6f;
        _arena.DrawColoredPolygon(new[] { tip, baseA, baseB }, new Color(col, alpha));
    }

    private void DrawHero()
    {
        var themeCol = ThemeColor(_loadout.HeroTheme);
        var lean = DrawAttackTell(_hero, _hero.Radius);
        var pos = _hero.Pos + lean;
        var r = _hero.Radius * AttackSquash(_hero);
        var dir = new Vector2(Mathf.Cos(_hero.Facing), Mathf.Sin(_hero.Facing));

        // an ambient hero aura â€” a soft themed halo so the player's own unit always reads as the brightest thing on
        // the field (allies/enemies get no aura), plus a hero-marker ring at the base.
        CraftFx.Glow(_arena, pos, r * 2.1f, new Color(CraftColor.Lighten(themeCol, 0.2f), 0.16f), 5);

        // facing spike UNDER the body (points the way the hero aims)
        DrawFacingSpike(pos, _hero.Facing, r, CraftColor.Lighten(themeCol, 0.25f), 0.95f);

        // body â€” lit sphere (dark base â†’ bright top-left highlight)
        CraftColor.RadialGrad(_arena, pos, r, new Vector2(-r * 0.28f, -r * 0.34f),
            CraftColor.DeMuddy(CraftColor.Darken(themeCol, 0.5f), themeCol),
            CraftColor.Lighten(themeCol, 0.5f));

        // rim light â€” a bright crescent on the lit side + an inner-shadow crescent on the far side (depth)
        _arena.DrawArc(pos, r - 1f, _hero.Facing + 2.0f, _hero.Facing + 4.3f, 22, new Color(0, 0, 0, 0.30f), 2.5f);
        _arena.DrawArc(pos, r - 1f, _hero.Facing - 2.3f, _hero.Facing - 0.1f, 22, new Color(CraftColor.Lighten(themeCol, 0.55f), 0.8f), 2f);

        // plating chips (kept, but tighter + a bright top chip)
        var chip = CraftColor.Brighten(themeCol, 0.12f);
        foreach (var off in new[] { new Vector2(r * 0.42f, r * 0.34f), new Vector2(-r * 0.42f, r * 0.34f), new Vector2(0, -r * 0.42f) })
            _arena.DrawRect(new Rect2(pos + off - new Vector2(r * 0.22f, r * 0.22f), new Vector2(r * 0.44f, r * 0.44f)), chip);
        // specular dot
        _arena.DrawCircle(pos + new Vector2(-r * 0.32f, -r * 0.36f), r * 0.16f, new Color(1, 1, 1, 0.7f));

        // facing / weapon line (bright forward stroke)
        CraftFx.Streak(_arena, pos, pos + dir * r * 1.5f, new Color(CraftColor.Lighten(themeCol, 0.4f), 1f), 4.5f);

        // shield
        if (_hero.Shield > 0)
        {
            var pulse = 0.5f + 0.3f * Mathf.Sin((float)_anim * 6f);
            CraftFx.Ring(_arena, pos, r + 6, new Color(ThemeColor(Theme.Earth), 0.4f + 0.2f * pulse), 3f);
            CraftFx.Ring(_arena, pos, r + 6, new Color(CraftColor.Lighten(ThemeColor(Theme.Earth), 0.5f), 0.25f * pulse), 1.5f);
        }

        // haste wake
        if (Now < _heroBuff.HasteUntil)
            CraftFx.Wake(_arena, _hero.PrevPos, pos, new Color(themeCol, 0.5f));

        // hit flash
        if (_hero.HitFlash > 0) _arena.DrawCircle(pos, r, new Color(1, 1, 1, _hero.HitFlash * 0.7f));

        // low-HP ring
        var frac = _hero.HpMax > 0 ? _hero.Hp / _hero.HpMax : 0f;
        if (frac < 0.3f)
        {
            var pulse = 0.4f + 0.4f * Mathf.Sin((float)_anim * 9f);
            CraftFx.Ring(_arena, pos, r + 3, new Color(LowRed, pulse), 2f);
        }
    }

    private void DrawEnemy(Unit e)
    {
        // enemies read as a HOT, angry palette leaning to the wave theme but pushed away from muddiness so ally-green
        // vs enemy is never ambiguous. A thin dark outline separates enemy bodies from the warm floor.
        var waveCol = CraftColor.DeMuddy(ThemeColor(_wave.Character), ThemeColor(_wave.Character), 0f, 0.6f, 0.62f);
        var a = SpawnAlpha(e);
        var r = e.Radius * (0.4f + 0.6f * a) * AttackSquash(e);
        var alpha = a * (Now < e.Phased ? 0.4f : 1f);
        var facingDir = new Vector2(Mathf.Cos(e.Facing), Mathf.Sin(e.Facing));

        // enemy attack tell (windup spark + muzzle flash + lean) â€” enemies telegraph exactly like allies (Â§ player ask)
        var bpos = e.Pos + DrawAttackTell(e, r, alpha);
        var lit = new Color(CraftColor.Lighten(waveCol, 0.45f), alpha);
        var dark = new Color(CraftColor.Darken(waveCol, 0.45f), alpha);

        if (e.EKind == EnemyKind.Rusher)
        {
            // a sharp forward-swept dart (asymmetric diamond leaning toward the aim) â€” reads as fast + aggressive
            var perp = new Vector2(-facingDir.Y, facingDir.X);
            var nose = bpos + facingDir * r * 1.35f;
            var tailC = bpos - facingDir * r * 0.9f;
            var wingL = bpos + perp * r * 0.9f;
            var wingR = bpos - perp * r * 0.9f;
            _arena.DrawColoredPolygon(new[] { nose, wingL, tailC, wingR }, new Color(waveCol, alpha));
            // outline + a bright leading edge on the nose
            _arena.DrawPolyline(new[] { nose, wingL, tailC, wingR, nose }, new Color(0, 0, 0, 0.35f * alpha), 1.5f);
            _arena.DrawLine(wingL, nose, lit, 2f);
            _arena.DrawLine(wingR, nose, lit, 2f);
            _arena.DrawCircle(bpos, r * 0.28f, dark);
        }
        else
        {
            // a heavy plated hexagon: shaded outer plate, a darker recessed core, a bright top-left facet = mass + depth
            var hexCol = waveCol;
            var hex = new Vector2[6];
            for (var i = 0; i < 6; i++) { var ang = Mathf.Tau * i / 6f + 0.26f; hex[i] = bpos + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * r; }
            _arena.DrawColoredPolygon(hex, new Color(hexCol, alpha));
            _arena.DrawPolyline(new[] { hex[0], hex[1], hex[2], hex[3], hex[4], hex[5], hex[0] }, new Color(0, 0, 0, 0.32f * alpha), 1.5f);
            var inner = new Vector2[6];
            for (var i = 0; i < 6; i++) { var ang = Mathf.Tau * i / 6f + 0.26f; inner[i] = bpos + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * r * 0.58f; }
            _arena.DrawColoredPolygon(inner, new Color(CraftColor.Darken(hexCol, 0.4f), alpha));
            // top-left facet highlight
            _arena.DrawArc(bpos, r - 1f, e.Facing - 2.6f, e.Facing - 0.6f, 16, new Color(CraftColor.Lighten(hexCol, 0.4f), 0.7f * alpha), 2f);
            // facing spike so even a slow bruiser shows where it aims
            DrawFacingSpike(bpos, e.Facing, r, lit, alpha, 0.55f);
            if (e.IsMiniBoss)
            {
                var spin = (float)_anim * 0.8f;
                CraftFx.Glow(_arena, bpos, r * 1.9f, new Color(Accent2, 0.18f * alpha), 5);
                CraftFx.Ring(_arena, bpos, r + 5, new Color(Accent2, 0.75f * alpha), 3f);
                CraftFx.Ring(_arena, bpos, r + 9, new Color(GlowCol, 0.4f * alpha), 1.5f);
                for (var i = 0; i < 5; i++)
                {
                    var ang = spin + Mathf.Tau * i / 5f;
                    CraftFx.DrawStar(_arena, bpos + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * (r + 8), 4f, new Color(Accent2, alpha));
                }
            }
        }

        if (e.HitFlash > 0) _arena.DrawCircle(bpos, r, new Color(1, 1, 1, e.HitFlash * 0.6f * alpha));
    }

    private void DrawAlly(Unit a)
    {
        var alpha = SpawnAlpha(a);
        var r = a.Radius * (0.4f + 0.6f * alpha) * AttackSquash(a);
        // ally attack tell (windup spark + muzzle flash + lean) â€” mirrors enemies + hero
        var bpos = a.Pos + DrawAttackTell(a, r, alpha);

        // a faint cool-green base ring on EVERY ally so friendlies are instantly separable from the warm enemies.
        CraftFx.Ring(_arena, bpos, r + 2f, new Color(AllyGreen, 0.35f * alpha), 1.5f);

        if (a.AKind == AllyKind.Sprout)
        {
            var col = ThemeColor(Theme.Life);
            // lit round body + specular + facing spike, then the vine flourish on top
            CraftColor.RadialGrad(_arena, bpos, r, new Vector2(-r * 0.3f, -r * 0.34f),
                CraftColor.DeMuddy(CraftColor.Darken(col, 0.45f), col), CraftColor.Lighten(col, 0.45f));
            DrawFacingSpike(bpos, a.Facing, r, CraftColor.Lighten(col, 0.3f), alpha, 0.6f);
            _arena.DrawCircle(bpos + new Vector2(-r * 0.3f, -r * 0.32f), r * 0.16f, new Color(1, 1, 1, 0.6f * alpha));
            StateVisual.Vines(_arena, bpos, r * 1.2f, col, 0.6f, (float)_anim);
        }
        else // Guardian â€” a heavy shaded block + a bright shield facet arc toward the aim
        {
            var col = ThemeColor(Theme.Earth);
            var rect = new Rect2(bpos - new Vector2(r, r), new Vector2(r * 2, r * 2));
            _arena.DrawRect(rect, new Color(col, alpha));
            // inner recess + a bright top-left plate for depth
            _arena.DrawRect(new Rect2(bpos - new Vector2(r * 0.55f, r * 0.55f), new Vector2(r * 1.1f, r * 1.1f)), new Color(CraftColor.Darken(col, 0.35f), alpha));
            _arena.DrawRect(new Rect2(bpos - new Vector2(r * 0.9f, r * 0.9f), new Vector2(r * 0.7f, r * 0.7f)), new Color(CraftColor.Lighten(col, 0.35f), 0.7f * alpha));
            _arena.DrawRect(rect, new Color(0, 0, 0, 0.3f * alpha), false, 1.5f);
            var f = a.Facing;
            CraftFx.Arc(_arena, bpos, r + 3, f - 0.6f, f + 0.6f, new Color(CraftColor.Lighten(col, 0.35f), alpha), 4f);
        }
        if (a.HitFlash > 0) _arena.DrawCircle(bpos, r, new Color(1, 1, 1, a.HitFlash * 0.6f * alpha));
    }

    private void DrawFields()
    {
        foreach (var f in _fields)
        {
            var alpha = Mathf.Clamp((f.Until - Now) / Mathf.Max(0.1f, f.Until - f.Started), 0f, 1f);
            switch (f.Kind)
            {
                case AbilityKind.SlowField:
                {
                    var ice = ThemeColor(Theme.Ice);
                    _arena.DrawCircle(f.Pos, f.Radius, new Color(ice, 0.08f * alpha));
                    CraftFx.Ring(_arena, f.Pos, f.Radius, new Color(ice, 0.6f * alpha), 3f);
                    StateVisual.RippleOut(_arena, f.Pos, f.Radius, ice, 0.7f, (float)_anim);
                    break;
                }
                case AbilityKind.Torrent:
                {
                    var water = ThemeColor(Theme.Water);
                    _arena.DrawCircle(f.Pos, f.Radius, new Color(water, 0.06f * alpha));
                    StateVisual.RippleOut(_arena, f.Pos, f.Radius, water, 0.6f, (float)_anim);
                    break;
                }
                case AbilityKind.Nuke:
                {
                    var fire = ThemeColor(Theme.Fire);
                    var phase = (float)((_anim * 2.0) % 1.0);
                    CraftFx.RingPulse(_arena, f.Pos, f.Radius, phase, new Color(fire, alpha));
                    StateVisual.Flame(_arena, f.Pos, f.Radius, fire, 0.6f * alpha, (float)_anim);
                    break;
                }
            }
        }
    }

    private void DrawHpBar(Unit u)
    {
        if (u.HpMax <= 0) return;
        var frac = Mathf.Clamp(u.Hp / u.HpMax, 0f, 1f);

        // DECLUTTER: only show a bar when it's meaningful â€” the unit is hurt, selected, shielded, or is the mini-boss
        // (which always shows its threat). A full-health mob in the pack draws nothing, so the field stays clean.
        var show = frac < 0.999f || u.Selected || u.Shield > 0 || u.IsMiniBoss;
        if (!show) return;

        // a thin rounded bar; fill colour lerps smoothly GREEN â†’ YELLOW â†’ RED with remaining HP so a hurt unit reads
        // instantly regardless of team (team identity is already carried by body colour + the ally/enemy shapes).
        var fillCol = frac > 0.5f
            ? AllyGreen.Lerp(new Color(0.95f, 0.85f, 0.30f), (1f - frac) * 2f)   // green â†’ yellow
            : new Color(0.95f, 0.85f, 0.30f).Lerp(LowRed, (0.5f - frac) * 2f);   // yellow â†’ red
        var w = u.Radius * 2f;
        var rect = new Rect2(u.Pos.X - u.Radius, u.Pos.Y - u.Radius - (u.IsMiniBoss ? 12f : 9f), w, u.IsMiniBoss ? 4.5f : 3f);
        // track (slightly inset dark) + rounded fill
        CraftFx.RoundRect(_arena, rect, new Color(0, 0, 0, 0.55f), null, 0, 2);
        var fw = rect.Size.X * frac;
        if (fw > 1f) CraftFx.RoundRect(_arena, new Rect2(rect.Position, new Vector2(fw, rect.Size.Y)), fillCol, null, 0, 2);

        if (u.Shield > 0)
        {
            var sw = Mathf.Clamp(u.Shield / u.HpMax, 0f, 1f) * rect.Size.X;
            CraftFx.RoundRect(_arena, new Rect2(rect.Position - new Vector2(0, rect.Size.Y + 1f), new Vector2(sw, rect.Size.Y)),
                new Color(0.78f, 0.9f, 1f, 0.85f), null, 0, 2);
        }
    }

    private void DrawReticle()
    {
        if (_phase != Phase.Play) return;
        // reticle for the first ready Targeted ability (Q priority)
        Ability? aim = null;
        foreach (var a in _loadout.Abilities)
            if (a.Targeted && a.Ready) { aim = a; break; }
        if (aim == null) return;
        var baseCol = ThemeColor(aim.Source);
        var col = new Color(baseCol, 0.55f);
        if (aim.Radius > 1)
        {
            // a faint themed fill + a crisp lit ring shows the ability's AoE footprint under the cursor
            _arena.DrawCircle(_cursor, aim.Radius, new Color(baseCol, 0.05f));
            CraftFx.Ring(_arena, _cursor, aim.Radius, new Color(CraftColor.Lighten(baseCol, 0.3f), 0.5f), 2f);
        }
        // a gapped crosshair (clearer centre) + a small centre dot
        _arena.DrawLine(_cursor - new Vector2(10, 0), _cursor - new Vector2(3, 0), col, 1.5f);
        _arena.DrawLine(_cursor + new Vector2(3, 0), _cursor + new Vector2(10, 0), col, 1.5f);
        _arena.DrawLine(_cursor - new Vector2(0, 10), _cursor - new Vector2(0, 3), col, 1.5f);
        _arena.DrawLine(_cursor + new Vector2(0, 3), _cursor + new Vector2(0, 10), col, 1.5f);
        _arena.DrawCircle(_cursor, 1.5f, new Color(CraftColor.Lighten(baseCol, 0.4f), 0.8f));
    }

    private void DrawBanner(Font? font)
    {
        if (font == null) return;
        var center = new Vector2(_arena.Size.X * 0.5f, _arena.Size.Y * 0.45f);
        if (_phase == Phase.Countdown)
        {
            var n = (int)Math.Ceiling(_countdown);
            var text = n <= 0 ? "FORGE!" : n.ToString();
            _arena.DrawString(font, center - new Vector2(60, 0), text, HorizontalAlignment.Center, 120, 64, Accent2);
        }
        else if (_phase == Phase.Settle)
        {
            var win = !_heroDied;
            var text = win ? "FORGED!" : "SHATTERED";
            var col = win ? new Color(CraftFx.QualityColor(ComputePerf())) : LowRed;
            _arena.DrawString(font, center - new Vector2(160, 0), text, HorizontalAlignment.Center, 320, 52, col);
        }
    }

    private void DrawReadyCard(Font? font)
    {
        if (font == null) return;
        var w = 470f; var h = 288f;
        var origin = new Vector2(_arena.Size.X * 0.5f - w * 0.5f, _arena.Size.Y * 0.16f);
        CraftFx.RoundRect(_arena, new Rect2(origin, new Vector2(w, h)), new Color(0.06f, 0.05f, 0.07f, 0.92f), Accent2, 2, 14);
        var x = origin.X + 22; var y = origin.Y + 30;
        _arena.DrawString(font, new Vector2(x, y), "FORGE RUSH â€” command your hero", HorizontalAlignment.Left, w - 40, 20, Accent2); y += 30;
        _arena.DrawString(font, new Vector2(x, y), $"Hero: {_loadout.HeroTheme}", HorizontalAlignment.Left, w - 40, 15, Ink); y += 22;
        foreach (var a in _loadout.Abilities)
        {
            if (a.Kind == AbilityKind.None) continue;
            var kd = a.Kind is AbilityKind.PassiveCrit or AbilityKind.PassiveRegen ? "passive" : $"cd {a.Cooldown:0.0}s";
            _arena.DrawString(font, new Vector2(x + 8, y), $"[{a.Slot}] {a.Label}  r{a.Rank}  ({kd})", HorizontalAlignment.Left, w - 60, 14, Sub); y += 18;
        }
        if (_loadout.StartAllies.Count > 0)
        { _arena.DrawString(font, new Vector2(x, y), $"Allies: {string.Join(", ", _loadout.StartAllies.Select(s => s.Kind))}", HorizontalAlignment.Left, w - 40, 14, new Color(AllyGreen, 0.9f)); y += 20; }
        _arena.DrawString(font, new Vector2(x, y), $"Wave: {DescribeWave()}", HorizontalAlignment.Left, w - 40, 14, new Color(ThemeColor(_wave.Character))); y += 24;
        _arena.DrawString(font, new Vector2(x, y), "Left-click / drag-box select Â· Shift adds Â· Right-click move or attack", HorizontalAlignment.Left, w - 40, 13, Sub); y += 18;
        _arena.DrawString(font, new Vector2(x, y), "[A] then click = attack-move Â· Q/W/E abilities Â· [Space] BEGIN", HorizontalAlignment.Left, w - 40, 13, Sub);
    }

    // ---- Â§6.8 ability bar -----------------------------------------------------

    private void DrawAbilityBar()
    {
        if (_phase == Phase.Ready) return;
        var font = _abilityBarCtl.GetThemeDefaultFont();
        var aw = _abilityBarCtl.Size.X; var ah = _abilityBarCtl.Size.Y;
        var bar = new Rect2(aw * 0.30f, ah * 0.905f, aw * 0.40f, ah * 0.075f);
        var gap = 8f;
        var slotW = bar.Size.X / 4f - gap;
        var slotH = bar.Size.Y;

        for (var i = 0; i < 4; i++)
        {
            var a = _loadout.Abilities[i];
            var sx = bar.Position.X + i * (slotW + gap);
            var rect = new Rect2(sx, bar.Position.Y, slotW, slotH);
            var empty = a.Kind == AbilityKind.None;
            var border = empty || a.CdTimer > 0 ? new Color(0.2f, 0.2f, 0.2f) : Accent2;

            // ready pulse glow
            if (!empty && a.Ready)
                CraftFx.Glow(_abilityBarCtl, rect.GetCenter(), slotW * 0.7f, new Color(ThemeColor(a.Source), 0.25f));

            CraftFx.RoundRect(_abilityBarCtl, rect, new Color(0.07f, 0.06f, 0.055f), border, 2, 8);

            // cooldown radial wipe
            if (!empty && a.CdTimer > 0 && a.Cooldown > 0)
            {
                var frac = a.CdTimer / a.Cooldown;
                DrawCdWedge(rect.GetCenter(), slotW * 0.5f, frac);
            }

            if (font != null)
            {
                var slotName = ((AbilitySlot)i).ToString();
                _abilityBarCtl.DrawString(font, rect.Position + new Vector2(4, 14), slotName, HorizontalAlignment.Left, -1, 12, Sub);
                var label = empty ? "â€”" : a.Label;
                _abilityBarCtl.DrawString(font, rect.Position + new Vector2(0, slotH * 0.55f), label, HorizontalAlignment.Center, (int)slotW, 13, empty ? Sub : Ink);
            }

            if (!empty)
            {
                // theme dot bottom-right
                _abilityBarCtl.DrawCircle(rect.Position + new Vector2(slotW - 8, slotH - 8), 5f, ThemeColor(a.Source));
                // rank pips (stars) bottom row
                for (var k = 0; k < a.Rank; k++)
                    CraftFx.DrawStar(_abilityBarCtl, rect.Position + new Vector2(8 + k * 11, slotH - 8), 4f, Accent2);
            }
        }
    }

    private void DrawCdWedge(Vector2 c, float r, float frac)
    {
        frac = Mathf.Clamp(frac, 0f, 1f);
        var steps = Mathf.Max(2, (int)(frac * 24));
        var pts = new List<Vector2> { c };
        var start = -Mathf.Pi / 2f;
        var sweep = Mathf.Tau * frac;
        for (var i = 0; i <= steps; i++)
        {
            var ang = start + sweep * i / steps;
            pts.Add(c + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * r);
        }
        if (pts.Count >= 3) _abilityBarCtl.DrawColoredPolygon(pts.ToArray(), new Color(0, 0, 0, 0.55f));
    }
}
