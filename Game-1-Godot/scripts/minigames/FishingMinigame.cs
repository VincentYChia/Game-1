using Godot;
using System;

namespace Game1.Godot;

/// <summary>
/// FISHING — "Bite &amp; Line". A reactive tension tug-of-war: read the fish, don't mash.
///
/// THREE LAYERS, each moving perf on its own:
///   • MICRO (the on-ramp) — THE BITE. After a random pause the '!' + ripple appears; tap
///     [Space] inside a shrinking window to set the hook. Tap too early = SPOOK (re-arm with a
///     longer wait — punishes itchy fingers); let it lapse = SLIP (re-arm normal). A blown bite
///     costs ~4s off a tightening timer, so it only bleeds the speed bonus — never a hard fail.
///   • MESO (the fight) — THE LINE. One analog channel: HOLD [Space] to reel, release to ease.
///     Tension has INERTIA (velocity + momentum), so you cannot re-pin the band the instant it
///     jumps — you must EASE on the telegraph a beat early. A fish-state-driven SAFE BAND (green)
///     must be held between a red SNAP cap and a blue SLACK floor. Two meters gate the fight:
///     fish STAMINA (drains ONLY when TIRED, faster the closer to band-centre you reel) and LINE
///     INTEGRITY (discrete notches; frays on red-zone strikes or deep-slack stalls; 0 = SNAP).
///   • MACRO (re-read per phase) — RUN / DIVE / HEAD-SHAKE. As stamina crosses thresholds the
///     pattern flips: surges frequent + band low/narrow (RUN), band drifts down (DIVE), or band
///     jitters ±0.08 for a beat (HEAD-SHAKE). Each entry gets a distinct anim + a one-word banner.
///
/// ANTI-SOLVE: feathering (pin tension at the safe-band top, reel always) breaks because the band
/// is FISH-DRIVEN — a surge drops its top BELOW a high feather, so the feather sits in the red and
/// frays a notch every surge; stamina only drains when TIRED, so feathering a surge spends integrity
/// for zero progress; and inertia means you can't re-pin instantly — you had to ease on the telegraph.
/// Reader ~0.95, masher ~0.35.
///
/// Seam untouched: the overlay owns only the play loop and hands a performance 0..1 to Finish().
///   perf = 0.55·landed + 0.30·(notchesLeft/notchesMax) + 0.15·(timeLeft/timeLimit).
///   A line-break caps at 0.15; a timeout unlanded = 0.55·staminaDepletedFraction (no other credit).
/// </summary>
public partial class FishingMinigame : MinigameOverlay
{
    protected override string Discipline => "fishing";

    // --- draw layout (local to the pond surface) ---
    private const float PondW = 660f, PondH = 320f;
    private const float GaugeX = 40f, GaugeY = 20f, GaugeW = 66f, GaugeH = 284f;   // vertical tension gauge
    private const float FishAreaX = 150f, FishAreaW = 470f;                        // fish silhouette region
    private const float FishY = 118f;                                              // fish vertical anchor
    private const float StamX = 150f, StamY = 236f, StamW = 470f, StamH = 22f;     // stamina bar
    private const float IntegX = 150f, IntegY = 274f, IntegW = 470f;              // integrity strands row

    private static readonly Color Water = new(0.42f, 0.82f, 1f);
    private static readonly Color SafeCol = new(0.36f, 0.95f, 0.55f);
    private static readonly Color SnapCol = new(1f, 0.35f, 0.32f);
    private static readonly Color SlackCol = new(0.34f, 0.55f, 1f);
    private static readonly Color FishCol = new(0.62f, 0.72f, 0.82f);
    private static readonly Color Gold = new(1f, 0.9f, 0.4f);

    private enum FishState { Calm, Surge, Tired }
    private enum Macro { Run, Dive, HeadShake }

    // --- difficulty-interpolated params ---
    private double _biteWindow, _bandHalfCalm, _tensionRise, _tensionEase, _surgeStrength;
    private double _staminaTotal, _telegraphLead, _surgeInterval, _timeLimit;
    private int _phases, _integrityNotches;

    // --- bite (micro) state ---
    private bool _biteArmed;          // the '!' is showing, window open
    private double _biteAt;           // time (play clock) the '!' appeared
    private double _biteDelay;        // countdown to next '!'
    private double _biteSpookMult = 1.0;
    private double _ripple;           // ripple anim 0..1 when bite shows
    private int _blownBites;

    // --- fight (meso) state ---
    private double _tension;          // 0..1 line tension
    private double _tensionVel;       // inertia
    private bool _holding;            // reel held
    private FishState _fish = FishState.Calm;
    private double _bandCenter, _bandHalf;      // current safe band
    private double _bandCenterTarget, _bandHalfTarget;
    private double _surgeTimer;                 // countdown to next surge
    private double _telegraph;                  // >0 during telegraph lead (counts down)
    private double _stamina;                    // remaining (drains to 0 = landed)
    private double _redTime, _slackTime;        // dwell timers for fraying
    private int _notchesLeft;
    private double _fishFlash;                  // white-flash tell 0..1
    private double _lungeAnim;                  // fish lunge/sag pose -1..1
    private double _stamStart;

    // --- macro state ---
    private int _macroPhase;          // 0..phases-1
    private Macro _macro = Macro.Run;
    private double _diveDrift;         // accumulated downward band drift (DIVE)
    private double _shakeTimer;        // HEAD-SHAKE jitter window
    private string _banner = "";
    private double _bannerT;

    // --- run state ---
    private enum Stage { Ready, Biting, Fighting, Landed, Snapped, Done }
    private Stage _stage = Stage.Ready;
    private double _timeLeft, _anim, _splash, _snapAnim;
    private bool _lineBroke, _landed;

    private Control _pond = null!;
    private VBoxContainer _readyBox = null!;
    private Label _readyLabel = null!;

    protected override void BuildUi(VBoxContainer host)
    {
        _pond = new Control
        {
            CustomMinimumSize = new Vector2(PondW, PondH),
            SizeFlagsHorizontal = Control.SizeFlags.ShrinkCenter,
        };
        _pond.Draw += DrawPond;
        host.AddChild(_pond);

        var hint = new Label
        {
            Text = "watch for the [ ! ]  ·  [Space] to hook  ·  HOLD [Space] = reel, release = ease  ·  keep the line in the GREEN, ease on the tell",
            Modulate = new Color(0.7f, 0.86f, 1f),
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        hint.AddThemeFontSizeOverride("font_size", 13);
        host.AddChild(hint);

        _readyBox = new VBoxContainer();
        _readyBox.AddThemeConstantOverride("separation", 8);
        host.AddChild(_readyBox);
        _readyLabel = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _readyLabel.AddThemeFontSizeOverride("font_size", 16);
        _readyBox.AddChild(_readyLabel);
        var begin = new Button { Text = "CAST THE LINE  ▸  [Space]", FocusMode = Control.FocusModeEnum.None };
        begin.AddThemeFontSizeOverride("font_size", 20);
        begin.Pressed += StartFishing;
        _readyBox.AddChild(begin);
    }

    protected override void OnBegin()
    {
        _biteWindow    = Interp(1.1, 0.6);
        _bandHalfCalm  = Interp(0.16, 0.085);
        _tensionRise   = Interp(1.4, 1.9);
        _tensionEase   = Interp(1.1, 1.35);
        _surgeStrength = Interp(0.18, 0.30);
        _staminaTotal  = Interp(100.0, 220.0);
        _telegraphLead = Interp(0.5, 0.2);
        _surgeInterval = Interp(4.0, 2.5);
        _timeLimit     = Interp(34.0, 26.0);
        _phases        = (int)Math.Round(Interp(1.0, 3.0));
        _integrityNotches = (int)Math.Round(Interp(4.0, 2.0));

        // --- bite reset ---
        _biteArmed = false;
        _biteDelay = (float)GD.RandRange(0.8, 3.4);
        _biteSpookMult = 1.0;
        _ripple = 0; _blownBites = 0;

        // --- fight reset ---
        _tension = 0.5; _tensionVel = 0; _holding = false;
        _fish = FishState.Calm;
        _bandCenter = 0.5; _bandHalf = _bandHalfCalm;
        _bandCenterTarget = 0.5; _bandHalfTarget = _bandHalfCalm;
        _surgeTimer = (float)GD.RandRange(_surgeInterval * 0.7, _surgeInterval);
        _telegraph = 0;
        _stamina = _staminaTotal; _stamStart = _staminaTotal;
        _redTime = 0; _slackTime = 0;
        _notchesLeft = _integrityNotches;
        _fishFlash = 0; _lungeAnim = 0;

        // --- macro reset ---
        _macroPhase = 0; _macro = Macro.Run;
        _diveDrift = 0; _shakeTimer = 0;
        _banner = ""; _bannerT = 0;

        // --- run reset ---
        _stage = Stage.Ready;
        _timeLeft = _timeLimit; _anim = 0; _splash = 0; _snapAnim = 0;
        _lineBroke = false; _landed = false;

        SetHeaderSub($"{_phases} phase fight  ·  {_integrityNotches} line strands");
        SetQuality(0);
        _readyLabel.Text =
            $"A catch is circling. Set the hook on the [ ! ], then win the fight:\n"
            + "keep the line in the GREEN band. It only tires when the band sits HIGH.\n"
            + "EASE the instant the fish flashes — a surge drops the band and snaps a taut line.";
        _readyBox.Visible = true;
        _pond.QueueRedraw();
    }

    private void StartFishing()
    {
        if (_stage != Stage.Ready) return;
        _readyBox.Visible = false;
        _stage = Stage.Biting;
        _biteDelay = (float)GD.RandRange(0.8, 3.4);
    }

    // ---------------------------------------------------------------- input
    protected override void OnInput(InputEvent @event)
    {
        if (@event is InputEventKey { Echo: false } key && key.PhysicalKeycode == Key.Space)
        {
            if (key.Pressed)
            {
                switch (_stage)
                {
                    case Stage.Ready:   StartFishing(); break;
                    case Stage.Biting:  TrySetHook();   break;
                    case Stage.Fighting: _holding = true; break;
                }
            }
            else if (_stage == Stage.Fighting)
            {
                _holding = false;
            }
            GetViewport().SetInputAsHandled();
        }
    }

    private void TrySetHook()
    {
        if (!_biteArmed)
        {
            // pressed BEFORE the '!' → SPOOK: re-arm with a longer wait
            _biteSpookMult = 1.5;
            _blownBites++;
            _timeLeft = Math.Max(1.0, _timeLeft - 4.0);
            _biteDelay = (float)GD.RandRange(0.8, 3.4) * (float)_biteSpookMult;
            _biteArmed = false; _ripple = 0;
            Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY), "SPOOKED", SnapCol, 24);
            Shake(5f);
            return;
        }
        var react = _anim - _biteAt;
        if (react <= _biteWindow)
        {
            // HOOK SET → into the fight
            _biteArmed = false; _ripple = 0;
            _stage = Stage.Fighting;
            _tension = 0.5; _tensionVel = 0;
            Burst(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY), Water, 22, 260f);
            Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY - 20), "HOOKED!", Gold, 30);
            FlashQuality();
            Shake(7f);
            SetBanner(MacroName(_macro));
        }
    }

    // ---------------------------------------------------------------- tick
    protected override void OnTick(double delta)
    {
        _anim += delta;
        _splash = Math.Max(0, _splash - delta * 1.6);
        _snapAnim = Math.Max(0, _snapAnim - delta * 1.2);
        _fishFlash = Math.Max(0, _fishFlash - delta * 3.2);
        _ripple = _biteArmed ? Mathf.PosMod((float)_ripple + (float)delta * 1.8f, 1f) : 0;
        if (_bannerT > 0) _bannerT = Math.Max(0, _bannerT - delta);

        switch (_stage)
        {
            case Stage.Biting:   TickBite(delta); break;
            case Stage.Fighting: TickFight(delta); break;
        }

        if (_stage is Stage.Biting or Stage.Fighting)
        {
            _timeLeft -= delta;
            SetTimer(_timeLeft);
            if (_timeLeft <= 0) { EndTimeout(); return; }
        }
        _pond.QueueRedraw();
    }

    private void TickBite(double delta)
    {
        if (!_biteArmed)
        {
            _biteDelay -= delta;
            if (_biteDelay <= 0)
            {
                _biteArmed = true;
                _biteAt = _anim;
                _ripple = 0;
                Burst(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY + 10), Water, 12, 150f);
            }
        }
        else if (_anim - _biteAt > _biteWindow)
        {
            // window lapsed → SLIP: re-arm normal (no spook penalty)
            _biteArmed = false; _ripple = 0;
            _biteSpookMult = 1.0;
            _blownBites++;
            _timeLeft = Math.Max(1.0, _timeLeft - 4.0);
            _biteDelay = (float)GD.RandRange(0.8, 3.4);
            Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY), "slipped", new Color(0.7f, 0.75f, 0.85f), 22);
        }
    }

    private void TickFight(double delta)
    {
        // ---- tension integration with inertia ----
        _tensionVel += (_holding ? _tensionRise : -_tensionEase) * delta;
        _tensionVel = Math.Clamp(_tensionVel, -1.6, 1.6);
        _tension += _tensionVel * delta;
        if (_tension <= 0) { _tension = 0; _tensionVel = Math.Max(0, _tensionVel); }
        if (_tension >= 1) { _tension = 1; _tensionVel = Math.Min(0, _tensionVel); }

        // ---- surge scheduling + telegraph ----
        _surgeTimer -= delta;
        var lead = _telegraphLead * (_macro == Macro.Run ? 0.8 : 1.0);
        if (_telegraph <= 0 && _surgeTimer <= lead && _fish != FishState.Surge && _fish != FishState.Tired)
        {
            _telegraph = lead;
            _fishFlash = 1.0;   // the tell
        }
        if (_telegraph > 0)
        {
            _telegraph -= delta;
            if (_surgeTimer <= 0) EnterSurge();
        }

        // ---- fish state machine ----
        UpdateFishState(delta);

        // ---- band drift (macro flavours) + smoothing ----
        var cTarget = _bandCenterTarget;
        var hTarget = _bandHalfTarget;
        if (_macro == Macro.Dive && _fish != FishState.Surge)
        {
            _diveDrift += delta * Interp(0.02, 0.05);
            cTarget = Math.Clamp(cTarget - _diveDrift, 0.18, 0.85);
        }
        if (_macro == Macro.HeadShake && _shakeTimer > 0)
        {
            _shakeTimer -= delta;
            cTarget += Math.Sin(_anim * 22.0) * 0.08;
            if (_shakeTimer <= 0) _shakeTimer = (float)GD.RandRange(2.0, 3.2);   // re-trigger jitter bursts
        }
        _bandCenter = Mathf.Lerp((float)_bandCenter, (float)cTarget, (float)Math.Min(1.0, delta * 9.0));
        _bandHalf   = Mathf.Lerp((float)_bandHalf,   (float)hTarget, (float)Math.Min(1.0, delta * 9.0));

        // ---- integrity fraying ----
        var lo = _bandCenter - _bandHalf;
        var redFloor = 1.0 - Interp(0.14, 0.10);   // top red snap-zone begins here
        if (_tension >= redFloor)
        {
            _redTime += delta;
            if (_redTime >= 0.25) { FrayNotch(strike: true); _redTime = 0; }
        }
        else _redTime = Math.Max(0, _redTime - delta * 2.0);

        var slackFloor = Interp(0.10, 0.08);
        if (_tension <= slackFloor)
        {
            _slackTime += delta;
            if (_slackTime >= 0.4) { FrayNotch(strike: false); _slackTime = 0; }
        }
        else _slackTime = Math.Max(0, _slackTime - delta * 2.0);

        // ---- stamina drain (ONLY when TIRED, proportional to band-centre precision) ----
        if (_fish == FishState.Tired && _tension >= lo && _tension <= _bandCenter + _bandHalf)
        {
            var distFromCenter = Math.Abs(_tension - _bandCenter) / Math.Max(1e-4, _bandHalf);  // 0 centre .. 1 edge
            var precision = 1.0 - 0.5 * Math.Clamp(distFromCenter, 0, 1);  // dead-centre = 1.0, edge = 0.5
            var rate = _staminaTotal * Interp(0.16, 0.11) * precision;      // full-band drain rate
            _stamina = Math.Max(0, _stamina - rate * delta);
            if (GD.Randf() < 0.35f)
                CraftFx.Burst(_pond, new Vector2(GaugeX + GaugeW * 0.5f, TensionToY(_tension)), SafeCol, 2, 60f, 0.4f, 3f, -40f);
            if (_stamina <= 0) { LandFish(); return; }
        }

        // ---- macro phase transitions on stamina thresholds ----
        UpdateMacroPhase();

        // ---- fish pose (lunge on surge, sag when tired) ----
        var poseTarget = _fish switch
        {
            FishState.Surge => 1.0,
            FishState.Tired => -0.7,
            _ => 0.15 * Math.Sin(_anim * 2.0),
        };
        _lungeAnim = Mathf.Lerp((float)_lungeAnim, (float)poseTarget, (float)Math.Min(1.0, delta * 6.0));

        // ---- live quality feedback ----
        RefreshQuality();
    }

    private void EnterSurge()
    {
        _fish = FishState.Surge;
        _surgeTimer = (float)GD.RandRange(0.9, 1.4);   // surge holds briefly
        _telegraph = 0;
        // band SNAPS down + narrows; the deeper the surge, the lower it drops
        _bandCenterTarget = Math.Clamp(0.28 - _surgeStrength * 0.4, 0.14, 0.4);
        _bandHalfTarget = Math.Max(0.06, _bandHalfCalm * 0.62);
        Shake(4f);
        CraftFx.Burst(_pond, FishCenter(), Water, 16, 240f);
    }

    private void UpdateFishState(double delta)
    {
        switch (_fish)
        {
            case FishState.Surge:
                if (_surgeTimer <= 0)
                {
                    // after a surge the fish tires briefly → the window to drain stamina
                    _fish = FishState.Tired;
                    _surgeTimer = (float)GD.RandRange(1.6, 2.6);
                    _bandCenterTarget = 0.68;
                    _bandHalfTarget = Interp(0.20, 0.13);
                }
                break;
            case FishState.Tired:
                if (_surgeTimer <= 0)
                {
                    _fish = FishState.Calm;
                    _surgeTimer = (float)GD.RandRange(_surgeInterval * 0.7, _surgeInterval);
                    _bandCenterTarget = 0.5;
                    _bandHalfTarget = _macro == Macro.Run ? _bandHalfCalm * 0.8 : _bandHalfCalm;
                }
                break;
            case FishState.Calm:
                // calm band recentres (RUN keeps it lower/narrower)
                if (_macro == Macro.Run)
                {
                    _bandCenterTarget = 0.42;
                    _bandHalfTarget = _bandHalfCalm * 0.8;
                }
                else if (_macro != Macro.Dive)
                {
                    _bandCenterTarget = 0.5;
                    _bandHalfTarget = _bandHalfCalm;
                }
                break;
        }
    }

    private void UpdateMacroPhase()
    {
        if (_phases <= 1) return;
        var depleted = 1.0 - _stamina / _stamStart;
        var perStep = 1.0 / _phases;
        var target = Math.Min(_phases - 1, (int)(depleted / perStep));
        if (target > _macroPhase)
        {
            _macroPhase = target;
            _macro = (Macro)((int)Macro.Run + _macroPhase % 3);
            if (_macro == Macro.Dive) _diveDrift = 0;
            if (_macro == Macro.HeadShake) _shakeTimer = 1.5f;
            SetBanner(MacroName(_macro));
            _fishFlash = 1.0;
            Shake(6f);
            CraftFx.Burst(_pond, FishCenter(), Gold, 20, 220f);
        }
    }

    private void FrayNotch(bool strike)
    {
        _notchesLeft--;
        if (strike)
        {
            Shake(10f);
            Popup(_pond, FishCenter(), "STRIKE!", SnapCol, 26);
            CraftFx.Burst(_pond, FishCenter(), SnapCol, 20, 260f);
            // lose 15% of stamina PROGRESS back (fish recovers)
            var progress = _stamStart - _stamina;
            _stamina = Math.Min(_stamStart, _stamina + progress * 0.15);
        }
        else
        {
            Shake(6f);
            Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY + 40), "slack!", SlackCol, 22);
        }
        if (_notchesLeft <= 0) { SnapLine(); return; }
        RefreshQuality();
    }

    private void RefreshQuality()
    {
        // live meter mirrors the FINAL formula's shape so skill reads moment to moment
        var landed = 1.0 - _stamina / Math.Max(1.0, _stamStart);
        var integ = (double)_notchesLeft / _integrityNotches;
        var speed = Math.Clamp(_timeLeft / _timeLimit, 0, 1);
        SetQuality(Math.Clamp(0.55 * landed + 0.30 * integ + 0.15 * speed, 0, 1));
    }

    // ---------------------------------------------------------------- endings
    private void LandFish()
    {
        if (_stage != Stage.Fighting) return;
        _landed = true;
        _stage = Stage.Landed;
        _splash = 1.0;
        Shake(12f);
        Burst(_pond, FishCenter(), Water, 40, 320f);
        Burst(_pond, FishCenter(), Gold, 24, 240f);
        Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY - 30), "LANDED!", Gold, 34);
        FlashQuality();
        FinishRun();
    }

    private void SnapLine()
    {
        if (_stage != Stage.Fighting) return;
        _lineBroke = true;
        _stage = Stage.Snapped;
        _snapAnim = 1.0;
        Shake(14f);
        Burst(_pond, FishCenter(), SnapCol, 30, 300f);
        Popup(_pond, new Vector2(FishAreaX + FishAreaW * 0.5f, FishY), "LINE SNAPPED", SnapCol, 30);
        FinishRun();
    }

    private void EndTimeout()
    {
        if (_stage is Stage.Landed or Stage.Snapped or Stage.Done) return;
        _stage = Stage.Done;
        FinishRun();
    }

    private void FinishRun()
    {
        double perf;
        if (_lineBroke)
        {
            perf = 0.15;   // line-break hard cap
        }
        else if (_landed)
        {
            var integ = (double)_notchesLeft / _integrityNotches;
            var speed = Math.Clamp(_timeLeft / _timeLimit, 0, 1);
            perf = 0.55 * 1.0 + 0.30 * integ + 0.15 * speed;
        }
        else
        {
            // timer-out, fish not landed → stamina-depleted fraction only, no integrity/speed credit
            var depleted = 1.0 - _stamina / Math.Max(1.0, _stamStart);
            perf = 0.55 * depleted;
        }
        _stage = Stage.Done;
        HideTimer();
        Finish(Math.Clamp(perf, 0, 1));
    }

    // ---------------------------------------------------------------- helpers
    private double Interp(double easy, double hard)
        => easy + (hard - easy) * Math.Clamp((DifficultyPoints - 1.0) / 79.0, 0.0, 1.0);

    private void SetBanner(string text) { _banner = text; _bannerT = 1.6; }

    private static string MacroName(Macro m) => m switch
    {
        Macro.Run => "RUN", Macro.Dive => "DIVE", Macro.HeadShake => "SHAKE", _ => "",
    };

    private Vector2 FishCenter() => new(FishAreaX + FishAreaW * 0.5f, FishY);

    // gauge maps tension 0(bottom)..1(top) → y (top of gauge is high tension)
    private float TensionToY(double t) => GaugeY + GaugeH * (1f - (float)t);

    // ---------------------------------------------------------------- draw
    private void DrawPond()
    {
        var font = _pond.GetThemeDefaultFont();

        DrawWaterBackdrop();
        DrawTensionGauge(font);
        DrawFish(font);
        DrawStaminaBar(font);
        DrawIntegrity(font);

        // banner (macro re-read cue)
        if (_bannerT > 0 && _banner.Length > 0)
        {
            var a = (float)Math.Min(1.0, _bannerT / 0.4);
            var col = new Color(1f, 0.95f, 0.6f, a);
            _pond.DrawString(font, new Vector2(FishAreaX, FishY - 70), _banner,
                HorizontalAlignment.Center, FishAreaW, 40, col);
        }

        // splash / snap flourish
        if (_splash > 0)
        {
            var c = FishCenter();
            CraftFx.Glow(_pond, c, 90f * (float)_splash, new Color(Water.R, Water.G, Water.B, 0.5f * (float)_splash));
            for (var i = 0; i < 10; i++)
            {
                var ang = i / 10f * Mathf.Tau;
                var r = (1f - (float)_splash) * 120f;
                _pond.DrawCircle(c + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang) * 0.6f) * r, 4f,
                    new Color(1f, 1f, 1f, (float)_splash * 0.8f));
            }
        }
        if (_snapAnim > 0)
        {
            var c = FishCenter();
            _pond.DrawLine(c, c + new Vector2(-160, -60) * (float)_snapAnim,
                new Color(SnapCol.R, SnapCol.G, SnapCol.B, (float)_snapAnim), 3f);
        }
    }

    private void DrawWaterBackdrop()
    {
        // pond frame
        CraftFx.RoundRect(_pond, new Rect2(0, 0, PondW, PondH),
            new Color(0.05f, 0.12f, 0.2f), new Color(0.2f, 0.4f, 0.6f), 2, 14);
        // drifting surface ripples
        for (var i = 0; i < 5; i++)
        {
            var y = 40 + i * 46 + Mathf.Sin((float)_anim * 0.8f + i) * 4f;
            var a = 0.06f + 0.03f * Mathf.Sin((float)_anim * 1.3f + i * 1.7f);
            _pond.DrawLine(new Vector2(FishAreaX - 10, y), new Vector2(FishAreaX + FishAreaW + 10, y),
                new Color(Water.R, Water.G, Water.B, a), 2f);
        }
    }

    private void DrawTensionGauge(Font font)
    {
        var x = GaugeX; var y = GaugeY; var w = GaugeW; var h = GaugeH;
        CraftFx.RoundRect(_pond, new Rect2(x - 8, y - 8, w + 16, h + 40),
            new Color(0.08f, 0.1f, 0.14f), new Color(0.25f, 0.35f, 0.45f), 2, 10);
        _pond.DrawRect(new Rect2(x, y, w, h), new Color(0.06f, 0.08f, 0.11f));

        // red SNAP cap (top) + blue SLACK floor (bottom)
        var redFloor = 1.0 - Interp(0.14, 0.10);
        var redTopY = y; var redBotY = TensionToY(redFloor);
        _pond.DrawRect(new Rect2(x, redTopY, w, redBotY - redTopY), new Color(SnapCol.R, SnapCol.G, SnapCol.B, 0.20f));
        var slackFloor = Interp(0.10, 0.08);
        var slackTopY = TensionToY(slackFloor);
        _pond.DrawRect(new Rect2(x, slackTopY, w, (y + h) - slackTopY), new Color(SlackCol.R, SlackCol.G, SlackCol.B, 0.20f));

        // the moving SAFE band (green) — this is the whole read
        if (_stage is Stage.Fighting or Stage.Biting or Stage.Ready)
        {
            var hi = Math.Clamp(_bandCenter + _bandHalf, 0, 1);
            var loB = Math.Clamp(_bandCenter - _bandHalf, 0, 1);
            var topY = TensionToY(hi); var botY = TensionToY(loB);
            var pulse = _fish == FishState.Tired ? 0.28f + 0.12f * Mathf.Sin((float)_anim * 5f) : 0.30f;
            _pond.DrawRect(new Rect2(x, topY, w, botY - topY), new Color(SafeCol.R, SafeCol.G, SafeCol.B, pulse));
            _pond.DrawLine(new Vector2(x, topY), new Vector2(x + w, topY), new Color(SafeCol.R, SafeCol.G, SafeCol.B, 0.85f), 2f);
            _pond.DrawLine(new Vector2(x, botY), new Vector2(x + w, botY), new Color(SafeCol.R, SafeCol.G, SafeCol.B, 0.85f), 2f);
            // dead-centre reel line (draining sweet spot when tired)
            var cy = TensionToY(_bandCenter);
            _pond.DrawLine(new Vector2(x, cy), new Vector2(x + w, cy),
                new Color(SafeCol.R, SafeCol.G, SafeCol.B, _fish == FishState.Tired ? 0.9f : 0.4f), 1.5f);

            // telegraph shimmer: the band's FUTURE top edge glows red before a surge
            if (_telegraph > 0)
            {
                var futureHi = Math.Clamp(0.28 - _surgeStrength * 0.4 + Math.Max(0.06, _bandHalfCalm * 0.62), 0, 1);
                var fy = TensionToY(futureHi);
                var flick = 0.4f + 0.5f * Mathf.Abs(Mathf.Sin((float)_anim * 18f));
                _pond.DrawLine(new Vector2(x, fy), new Vector2(x + w, fy), new Color(SnapCol.R, SnapCol.G, SnapCol.B, flick), 3f);
                _pond.DrawString(font, new Vector2(x - 4, fy - 4), "EASE", HorizontalAlignment.Center, w + 8, 13,
                    new Color(1f, 0.6f, 0.5f, flick));
            }
        }

        // the tension needle
        if (_stage == Stage.Fighting)
        {
            var ny = TensionToY(_tension);
            var inSafe = _tension >= _bandCenter - _bandHalf && _tension <= _bandCenter + _bandHalf;
            var nCol = _tension >= redFloor ? SnapCol : _tension <= slackFloor ? SlackCol : inSafe ? SafeCol : Colors.White;
            CraftFx.Glow(_pond, new Vector2(x + w * 0.5f, ny), 16f, new Color(nCol.R, nCol.G, nCol.B, 0.6f), 4);
            _pond.DrawRect(new Rect2(x - 4, ny - 3f, w + 8, 6f), nCol);
            // reel-hand indicator
            var handCol = _holding ? new Color(1f, 0.9f, 0.4f) : new Color(0.6f, 0.65f, 0.75f);
            _pond.DrawString(font, new Vector2(x - 6, ny - 22), _holding ? "REEL" : "ease",
                HorizontalAlignment.Center, w + 12, 13, handCol);
        }

        _pond.DrawRect(new Rect2(x, y, w, h), new Color(0.5f, 0.6f, 0.7f, 0.8f), false, 2f);
        _pond.DrawString(font, new Vector2(x - 6, y + h + 26), "TENSION", HorizontalAlignment.Center, w + 12, 13,
            new Color(0.7f, 0.85f, 1f));
    }

    private void DrawFish(Font font)
    {
        var c = FishCenter();
        var lunge = (float)_lungeAnim;
        // silhouette body: an ellipse-ish polygon that stretches on lunge, sags when tired
        var facing = _fish == FishState.Surge ? -1f : 1f;   // turns OUT to face the deep on surge
        var bodyLen = 78f * (1f + 0.25f * Math.Max(0, lunge));
        var bodyH = 34f * (1f - 0.2f * Math.Max(0, lunge)) * (1f + 0.15f * Math.Max(0, -lunge));
        var yBob = Mathf.Sin((float)_anim * 3f) * 4f + lunge * -14f;
        var cc = c + new Vector2(lunge * 26f * facing, yBob);

        var bodyCol = _fish switch
        {
            FishState.Surge => new Color(0.75f, 0.85f, 0.95f),
            FishState.Tired => new Color(0.45f, 0.52f, 0.6f),
            _ => FishCol,
        };
        // white-flash TELL
        if (_fishFlash > 0.01f)
            bodyCol = bodyCol.Lerp(Colors.White, (float)_fishFlash * 0.9f);

        // body polygon
        var pts = new Vector2[12];
        for (var i = 0; i < 12; i++)
        {
            var a = i / 12f * Mathf.Tau;
            pts[i] = cc + new Vector2(Mathf.Cos(a) * bodyLen * 0.5f * facing, Mathf.Sin(a) * bodyH * 0.5f);
        }
        CraftFx.Glow(_pond, cc, bodyLen * 0.7f, new Color(bodyCol.R, bodyCol.G, bodyCol.B, 0.3f + 0.3f * (float)_fishFlash), 5);
        _pond.DrawColoredPolygon(pts, bodyCol);
        // tail
        var tailBase = cc + new Vector2(-facing * bodyLen * 0.5f, 0);
        var tailFlick = Mathf.Sin((float)_anim * (_fish == FishState.Surge ? 16f : 6f)) * 14f;
        _pond.DrawColoredPolygon(new[]
        {
            tailBase,
            tailBase + new Vector2(-facing * 26f, -16f + tailFlick),
            tailBase + new Vector2(-facing * 26f, 16f + tailFlick),
        }, bodyCol);
        // eye
        _pond.DrawCircle(cc + new Vector2(facing * bodyLen * 0.3f, -bodyH * 0.14f), 3.5f, new Color(0.05f, 0.05f, 0.08f));

        // pre-surge tensing RING pulse
        if (_telegraph > 0)
        {
            var t = 1f - (float)(_telegraph / Math.Max(0.01, _telegraphLead));
            var rr = 40f + t * 60f;
            _pond.DrawArc(cc, rr, 0, Mathf.Tau, 40, new Color(SnapCol.R, SnapCol.G, SnapCol.B, (1f - t) * 0.8f), 3f);
        }

        // bite '!' + ripple
        if (_stage == Stage.Biting && _biteArmed)
        {
            var bob = c + new Vector2(0, Mathf.Sin((float)_anim * 8f) * 3f);
            var rr = 20f + (float)_ripple * 42f;
            _pond.DrawArc(bob, rr, 0, Mathf.Tau, 32, new Color(1f, 1f, 1f, (1f - (float)_ripple) * 0.7f), 2.5f);
            CraftFx.Glow(_pond, bob, 24f, new Color(1f, 0.9f, 0.4f, 0.7f), 5);
            _pond.DrawString(font, new Vector2(bob.X - 20, bob.Y - 44), "!", HorizontalAlignment.Center, 40, 44, Gold);
        }
        else if (_stage == Stage.Biting)
        {
            // waiting bobber
            var bob = c + new Vector2(0, Mathf.Sin((float)_anim * 2f) * 3f);
            _pond.DrawCircle(bob, 8f, new Color(0.9f, 0.35f, 0.35f));
            _pond.DrawCircle(bob, 4f, new Color(1f, 0.8f, 0.8f));
            _pond.DrawString(font, new Vector2(FishAreaX, FishY + 60), "watch for the bite...",
                HorizontalAlignment.Center, FishAreaW, 15, new Color(0.7f, 0.82f, 1f, 0.7f));
        }
    }

    private void DrawStaminaBar(Font font)
    {
        var frac = (float)Math.Clamp(_stamina / Math.Max(1.0, _stamStart), 0, 1);
        var col = _fish == FishState.Tired ? SafeCol : new Color(0.9f, 0.55f, 0.4f);
        CraftFx.RoundRect(_pond, new Rect2(StamX - 2, StamY - 2, StamW + 4, StamH + 4),
            new Color(0.08f, 0.1f, 0.14f), new Color(0.3f, 0.4f, 0.5f), 1, 6);
        // fill shrinks from full → 0 (0 = landed), so draw remaining
        CraftFx.Bar(_pond, new Rect2(StamX, StamY, StamW, StamH), frac,
            new Color(0.12f, 0.14f, 0.18f), col, 6);
        _pond.DrawString(font, new Vector2(StamX + 6, StamY + StamH * 0.5f + 6),
            _fish == FishState.Tired ? "FISH TIRING — REEL!" : "FISH STAMINA",
            HorizontalAlignment.Left, StamW, 13, _fish == FishState.Tired ? new Color(0.1f, 0.2f, 0.1f) : new Color(0.9f, 0.95f, 1f));
    }

    private void DrawIntegrity(Font font)
    {
        var n = _integrityNotches;
        var strandW = (IntegW - (n - 1) * 8f) / n;
        for (var i = 0; i < n; i++)
        {
            var x = IntegX + i * (strandW + 8f);
            var intact = i < _notchesLeft;
            var col = intact ? new Color(0.85f, 0.85f, 0.95f) : new Color(0.5f, 0.15f, 0.12f, 0.5f);
            // strand drawn as a wavering line pair (fray when broken)
            var midY = IntegY + 9f;
            if (intact)
            {
                _pond.DrawLine(new Vector2(x, midY), new Vector2(x + strandW, midY), col, 3f);
                var wob = Mathf.Sin((float)_anim * 4f + i) * 1.5f;
                _pond.DrawLine(new Vector2(x, midY + wob), new Vector2(x + strandW, midY - wob),
                    new Color(col.R, col.G, col.B, 0.4f), 1.5f);
            }
            else
            {
                // split fray: two diverging frayed ends
                var mx = x + strandW * 0.5f;
                _pond.DrawLine(new Vector2(x, midY), new Vector2(mx - 3, midY - 5), col, 2.5f);
                _pond.DrawLine(new Vector2(x + strandW, midY), new Vector2(mx + 3, midY + 5), col, 2.5f);
            }
        }
        _pond.DrawString(font, new Vector2(IntegX, IntegY + 22), $"LINE  ({_notchesLeft}/{_integrityNotches})",
            HorizontalAlignment.Left, IntegW, 13,
            _notchesLeft <= 1 ? new Color(1f, 0.5f, 0.4f) : new Color(0.75f, 0.85f, 1f));
    }
}
