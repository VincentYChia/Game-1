using System.Text.Json.Nodes;

namespace Game1.Core.Data;

/// <summary>
/// Port of data/databases/visual_config_db.py — thin typed reader over
/// Definitions.JSON/visual-config.JSON so visual tuning data survives the
/// engine swap (the CONSUMERS are Godot-side; this keeps the designer's
/// numbers). Same per-accessor defaults as the Python.
/// </summary>
public sealed class VisualConfig
{
    private JsonObject _data = new();
    public bool Loaded { get; private set; }

    public void Load(string contentRoot)
    {
        var path = Path.Combine(contentRoot, "Definitions.JSON", "visual-config.JSON");
        try
        {
            _data = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
            Loaded = true;
        }
        catch
        {
            _data = new JsonObject();
            Loaded = false;
        }
    }

    private JsonNode? Get(params string[] keys)
    {
        JsonNode? d = _data;
        foreach (var key in keys)
        {
            if (d is JsonObject o && o.TryGetPropertyValue(key, out var next))
                d = next;
            else
                return null;
        }
        return d;
    }

    public double Num(double def, params string[] keys) =>
        Get(keys) is JsonValue v && v.TryGetValue<double>(out var d) ? d : def;

    public bool Bool(bool def, params string[] keys) =>
        Get(keys) is JsonValue v && v.TryGetValue<bool>(out var b) ? b : def;

    public string Str(string def, params string[] keys) =>
        Get(keys) is JsonValue v && v.TryGetValue<string>(out var s) ? s : def;

    public (int R, int G, int B) Color(int r, int g, int b, params string[] keys)
    {
        if (Get(keys) is JsonArray a && a.Count >= 3)
            return ((int)a[0]!.GetValue<double>(), (int)a[1]!.GetValue<double>(),
                    (int)a[2]!.GetValue<double>());
        return (r, g, b);
    }

    // --- Damage numbers (visual_config_db.py:64-108) ---
    public (int, int, int) DamageTypeColor(string damageType)
    {
        if (Get("damageNumbers", "typeColors") is JsonObject colors
            && colors.TryGetPropertyValue(damageType, out var c) && c is JsonArray a
            && a.Count >= 3)
            return ((int)a[0]!.GetValue<double>(), (int)a[1]!.GetValue<double>(),
                    (int)a[2]!.GetValue<double>());
        return (255, 255, 255);
    }

    public double DamageNumberLifetimeMs => Num(1200, "damageNumbers", "lifetimeMs");
    public double DamageNumberVelocityY => Num(-2.5, "damageNumbers", "initialVelocityY");
    public double DamageNumberHorizontalSpread => Num(0.6, "damageNumbers", "horizontalSpread");
    public double DamageNumberGravity => Num(0.08, "damageNumbers", "gravity");
    public double DamageNumberShrinkRate => Num(0.997, "damageNumbers", "shrinkRate");
    public double DamageNumberCritScale => Num(1.8, "damageNumbers", "critScaleMultiplier");
    public (int, int, int) DamageNumberCritColor => Color(255, 220, 50, "damageNumbers", "critColor");
    public double DamageNumberStackOffset => Num(18, "damageNumbers", "stackOffsetPx");

    public (string Text, (int, int, int) Color) DamageSpecialText(string specialType) =>
        (Str(specialType.ToUpperInvariant(), "damageNumbers", $"{specialType}Text"),
         Color(180, 180, 180, "damageNumbers", $"{specialType}Color"));

    // --- Entity visuals (:110-153) ---
    public double PlayerRadiusTiles => Num(0.33, "entityVisuals", "playerRadius");
    public (int, int, int) PlayerColor => Color(80, 180, 255, "entityVisuals", "playerColor");
    public (int, int, int) PlayerOutlineColor => Color(40, 100, 160, "entityVisuals", "playerOutlineColor");
    public double FacingIndicatorLength => Num(0.5, "entityVisuals", "facingIndicatorLength");
    public (int, int, int) FacingIndicatorColor => Color(200, 220, 255, "entityVisuals", "facingIndicatorColor");
    public bool ShadowEnabled => Bool(true, "entityVisuals", "shadowEnabled");
    public double ShadowAlpha => Num(40, "entityVisuals", "shadowAlpha");
    public double ShadowScale => Num(0.7, "entityVisuals", "shadowScale");
    public double IdleBobAmplitude => Num(1.5, "entityVisuals", "idleBobAmplitude");
    public double IdleBobPeriodMs => Num(2000, "entityVisuals", "idleBobPeriodMs");

    // --- Enemy visuals (:155-190) ---
    public double EnemyTierScale(int tier) => Num(1.0, "enemyVisuals", "tierScale", tier.ToString());
    public bool EnemyTierHasGlow(int tier) => Bool(false, "enemyVisuals", "tierGlow", tier.ToString());
    public double EnemyTierGlowIntensity(int tier) => Num(0.0, "enemyVisuals", "tierGlowIntensity", tier.ToString());
    public (int, int, int) BossGlowColor => Color(255, 215, 0, "enemyVisuals", "bossGlowColor");
    public double DeathFadeDurationMs => Num(600, "enemyVisuals", "deathFadeDurationMs");
    public double DeathShrinkFactor => Num(0.3, "enemyVisuals", "deathShrinkFactor");
    public double CorpseLingerMs => Num(5000, "enemyVisuals", "corpseLingerMs");
    public double SpawnFadeInMs => Num(400, "enemyVisuals", "spawnFadeInMs");

    public (int, int, int) EnemyStateColor(string state)
    {
        if (Get("enemyVisuals", "stateIndicatorColors") is JsonObject colors
            && colors.TryGetPropertyValue(state, out var c) && c is JsonArray a
            && a.Count >= 3)
            return ((int)a[0]!.GetValue<double>(), (int)a[1]!.GetValue<double>(),
                    (int)a[2]!.GetValue<double>());
        return (150, 150, 150);
    }

    // --- Telegraphs / particles / screen effects / debug (:192-261) ---
    public (int, int, int) TelegraphPlayerColor => Color(100, 180, 255, "telegraphs", "playerColor");
    public (int, int, int) TelegraphEnemyColor => Color(255, 100, 100, "telegraphs", "enemyColor");
    public double TelegraphPulseFrequency => Num(10.0, "telegraphs", "pulseFrequency");
    public double MaxParticles => Num(400, "particles", "maxParticles");
    public (int Min, int Max) HitSparkCount
    {
        get
        {
            if (Get("particles", "hitSparkCount") is JsonArray a && a.Count >= 2)
                return ((int)a[0]!.GetValue<double>(), (int)a[1]!.GetValue<double>());
            return (5, 8);
        }
    }
    public double DeathBurstCount => Num(12, "particles", "deathBurstCount");
    public double ShakeDecayRate => Num(0.88, "screenEffects", "shakeDecayRate");
    public double ShakeMaxOffset => Num(12, "screenEffects", "shakeMaxOffset");
    public (int, int, int) DebugHitboxColor => Color(255, 60, 60, "debug", "hitboxColor");
    public double DebugHitboxAlpha => Num(100, "debug", "hitboxAlpha");
    public (int, int, int) DebugHurtboxColor => Color(60, 255, 60, "debug", "hurtboxColor");
    public double DebugHurtboxAlpha => Num(80, "debug", "hurtboxAlpha");
    public (int, int, int) DebugIframeColor => Color(60, 60, 255, "debug", "iframeHurtboxColor");
    public bool DebugShowFacing => Bool(true, "debug", "showFacingAngles");
    public bool DebugShowAttackPhase => Bool(true, "debug", "showAttackPhase");
}
