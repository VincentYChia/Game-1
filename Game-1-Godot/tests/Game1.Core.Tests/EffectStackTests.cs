using System.Text.Json;
using System.Text.Json.Nodes;
using Game1.Core;
using Game1.Core.Combat;
using Game1.Core.Content;
using Game1.Core.Tags;
using Game1.Core.World;
using Xunit;

namespace Game1.Core.Tests;

/// <summary>
/// Effect-stack parity: TagRegistry vs the loaded JSON, TagParser vs every
/// skill's combat tags, and EffectExecutor vs 25 scenarios executed through
/// the REAL Python executor on a spec-built stub battlefield. The stubs here
/// are constructed from the same specs stored in the fixture.
/// </summary>
public class EffectStackTests
{
    private static readonly JsonElement G = GoldenFixture.Load("db_parity/effect_stack.json");

    private static TagRegistry Registry() =>
        TagRegistry.LoadFrom(ContentPaths.TryGetContentRoot()!);

    private static void AssertMatch(JsonElement expected, JsonNode actual, string label)
    {
        var diffs = JsonTreeComparer.Diff(expected, actual);
        Assert.True(diffs.Count == 0,
            $"{label}: {diffs.Count} diffs:\n  " + string.Join("\n  ", diffs.Take(20)));
    }

    private static JsonNode? PlainToJson(object? v) => v switch
    {
        null => null,
        bool b => JsonValue.Create(b),
        double d => JsonValue.Create(d),
        long l => JsonValue.Create(l),
        int i => JsonValue.Create(i),
        string s => JsonValue.Create(s),
        List<object?> list => new JsonArray(list.Select(PlainToJson).ToArray()),
        Dictionary<string, object?> dict => DictToJson(dict),
        _ => throw new InvalidOperationException($"unexpected plain value {v.GetType()}"),
    };

    private static JsonObject DictToJson(Dictionary<string, object?> dict)
    {
        var o = new JsonObject();
        foreach (var kv in dict) o[kv.Key] = PlainToJson(kv.Value);
        return o;
    }

    private static JsonArray Strings(IEnumerable<string> xs)
    {
        var a = new JsonArray();
        foreach (var x in xs) a.Add(x);
        return a;
    }

    private static Dictionary<string, object?> ParamsFrom(JsonElement el) =>
        TagRegistry.ToPlain(JsonNode.Parse(el.GetRawText()))
            as Dictionary<string, object?> ?? new();

    private static JsonObject ConfigRow(EffectConfig cfg) => new()
    {
        ["raw_tags"] = Strings(cfg.RawTags),
        ["geometry"] = cfg.GeometryTag is null ? null : JsonValue.Create(cfg.GeometryTag),
        ["damage_tags"] = Strings(cfg.DamageTags),
        ["status_tags"] = Strings(cfg.StatusTags),
        ["context_tags"] = Strings(cfg.ContextTags),
        ["special_tags"] = Strings(cfg.SpecialTags),
        ["trigger_tags"] = Strings(cfg.TriggerTags),
        ["context"] = cfg.Context,
        ["base_damage"] = cfg.BaseDamage,
        ["base_healing"] = cfg.BaseHealing,
        ["params"] = DictToJson(cfg.Params),
        ["warnings"] = Strings(cfg.Warnings),
        ["conflicts"] = Strings(cfg.ConflictsResolved),
    };

    // ── Registry parity ──────────────────────────────────────────────────

    [Fact]
    public void Registry_MatchesPython()
    {
        var reg = Registry();

        var defs = new JsonObject();
        foreach (var name in reg.Definitions.Keys.OrderBy(x => x, StringComparer.Ordinal))
        {
            var d = reg.Definitions[name];
            defs[name] = new JsonObject
            {
                ["category"] = d.Category,
                ["description"] = d.Description,
                ["priority"] = d.Priority,
                ["requires_params"] = Strings(d.RequiresParams),
                ["default_params"] = DictToJson(d.DefaultParams),
                ["conflicts_with"] = Strings(d.ConflictsWith),
                ["aliases"] = Strings(d.Aliases),
                ["alias_of"] = d.AliasOf is null ? null : JsonValue.Create(d.AliasOf),
                ["stacking"] = d.Stacking is null ? null : JsonValue.Create(d.Stacking),
                ["immunity"] = Strings(d.Immunity),
                ["synergies"] = DictToJson(d.Synergies),
                ["context_behavior"] = DictToJson(d.ContextBehavior),
                ["auto_apply_chance"] = d.AutoApplyChance,
                ["auto_apply_status"] = d.AutoApplyStatus is null
                    ? null : JsonValue.Create(d.AutoApplyStatus),
                ["parent"] = d.Parent is null ? null : JsonValue.Create(d.Parent),
            };
        }

        var aliases = new JsonObject();
        foreach (var k in reg.Aliases.Keys.OrderBy(x => x, StringComparer.Ordinal))
            aliases[k] = reg.Aliases[k];

        var categories = new JsonObject();
        foreach (var kv in reg.Categories)
            categories[kv.Key] = Strings(kv.Value);

        var mx = new JsonObject();
        foreach (var kv in reg.MutuallyExclusive)
            mx[kv.Key] = Strings(kv.Value);

        var ci = new JsonObject();
        foreach (var kv in reg.ContextInference)
            ci[kv.Key] = kv.Value;

        var actual = new JsonObject
        {
            ["definitions"] = defs,
            ["aliases"] = aliases,
            ["categories"] = categories,
            ["geometry_priority"] = Strings(reg.GeometryPriority),
            ["mutually_exclusive"] = mx,
            ["context_inference"] = ci,
        };
        AssertMatch(G.GetProperty("registry"), actual, "registry");
    }

    // ── Parser parity over real skill content ────────────────────────────

    [Fact]
    public void Parser_SkillCombatTags_MatchPython()
    {
        var parser = new TagParser(Registry());
        foreach (var row in G.GetProperty("parse_skills").EnumerateArray())
        {
            var id = row.GetProperty("id").GetString();
            var tags = row.GetProperty("tags").EnumerateArray()
                .Select(t => t.GetString()!).ToList();
            var params_ = ParamsFrom(row.GetProperty("params"));
            var cfg = parser.Parse(tags, params_);
            AssertMatch(row.GetProperty("config"), ConfigRow(cfg), $"parse[{id}]");
        }
    }

    // ── Executor scenarios ───────────────────────────────────────────────

    /// <summary>Stub entity built from the fixture's battlefield spec —
    /// behavior mirrors the Python stub classes in dump_databases.py.</summary>
    private sealed class ScriptedEntity : ICombatEntity
    {
        public string Name { get; }
        public string TypeNameLower { get; }
        public string? Category { get; }
        public bool IsEnemyLike { get; }
        public (double Dx, double Dy)? LastMoveDirection { get; }

        private double _x, _y;
        private readonly string _kind;
        private readonly string _takeDamage;

        public bool HasCurrentHealth { get; }
        public double CurrentHealth { get; set; }
        public bool HasMaxHealth { get; }
        public double MaxHealth { get; }
        public bool HasIsAlive { get; }
        public bool Alive { get; set; } = true;
        public bool HasHealthField { get; }
        public double Health { get; set; }
        public double DefinitionDefense { get; }

        public bool SupportsTakeDamage => _takeDamage != "none";
        public bool SupportsHeal => _kind == "character";
        public bool HasStatusManager { get; }
        public bool HasKnockbackFields { get; }

        public JsonArray DamageLog = new();
        public List<double> HealLog = new();
        public JsonArray Statuses = new();
        public double[]? Knockback;

        public ScriptedEntity(JsonElement spec)
        {
            Name = spec.GetProperty("name").GetString()!;
            _kind = spec.GetProperty("kind").GetString()!;
            TypeNameLower = _kind == "character" ? "character" : "enemy";
            IsEnemyLike = _kind == "enemy";
            var pos = spec.GetProperty("position");
            _x = pos[0].GetDouble();
            _y = pos[1].GetDouble();
            Category = spec.TryGetProperty("category", out var c) ? c.GetString() : null;
            _takeDamage = spec.TryGetProperty("take_damage", out var td)
                ? td.GetString()! : "none";

            if (_kind == "character")
            {
                HasHealthField = true;
                Health = spec.GetProperty("health").GetDouble();
                MaxHealth = spec.GetProperty("max_health").GetDouble();
                HasMaxHealth = true;
                HasCurrentHealth = false;
                HasIsAlive = false;
                DefinitionDefense = 0;
            }
            else
            {
                HasCurrentHealth = true;
                CurrentHealth = spec.GetProperty("current_health").GetDouble();
                MaxHealth = spec.GetProperty("max_health").GetDouble();
                HasMaxHealth = true;
                HasIsAlive = true;
                HasHealthField = false;
                DefinitionDefense = spec.TryGetProperty("defense", out var def)
                    ? def.GetDouble() : 0.0;
            }

            HasStatusManager = spec.TryGetProperty("has_status_manager", out var sm)
                               && sm.GetBoolean();
            HasKnockbackFields = spec.TryGetProperty("has_knockback", out var kb)
                                 && kb.GetBoolean();
            if (HasKnockbackFields)
                Knockback = new[] { 0.0, 0.0, 0.0 };
            if (spec.TryGetProperty("last_move_direction", out var lmd)
                && lmd.ValueKind == JsonValueKind.Array)
                LastMoveDirection = (lmd[0].GetDouble(), lmd[1].GetDouble());
        }

        public Position GetPosition() => new(_x, _y, 0.0);

        public void SetPositionXY(double x, double y)
        {
            _x = x;
            _y = y;
        }

        public void TakeDamage(double damage, string damageType,
                               ICombatEntity? source, IReadOnlyList<string> tags)
        {
            if (_takeDamage == "enhanced")
            {
                DamageLog.Add(new JsonArray
                {
                    damage, damageType, Strings(tags),
                    source is null ? null : JsonValue.Create(source.Name),
                });
            }
            else
            {
                DamageLog.Add(new JsonArray { damage, damageType });
            }

            if (_kind == "character")
            {
                Health = Math.Max(0.0, Health - damage);
            }
            else
            {
                CurrentHealth -= damage;
                if (CurrentHealth <= 0)
                {
                    CurrentHealth = 0.0;
                    Alive = false;
                }
            }
        }

        public void Heal(double amount)
        {
            Health = Math.Min(MaxHealth, Health + amount);
            HealLog.Add(amount);
        }

        public void ApplyStatus(string statusTag, Dictionary<string, object?> statusParams,
                                ICombatEntity? source = null)
        {
            Statuses.Add(new JsonObject
            {
                ["tag"] = statusTag,
                ["params"] = DictToJson(statusParams),
                ["with_source"] = source is not null,
            });
        }

        public void SetKnockback(double vx, double vy, double durationRemaining)
        {
            Knockback = new[] { vx, vy, durationRemaining };
        }

        public JsonObject Row() => new()
        {
            ["name"] = Name,
            ["position"] = new JsonArray { _x, _y },
            ["alive"] = HasIsAlive ? Alive : null,
            ["current_health"] = HasCurrentHealth ? CurrentHealth : null,
            ["health"] = HasHealthField ? Health : null,
            ["damage_log"] = DamageLog,
            ["heal_log"] = new JsonArray(HealLog.Select(h => (JsonNode?)h).ToArray()),
            ["statuses"] = Statuses,
            ["knockback"] = Knockback is null
                ? null : new JsonArray { Knockback[0], Knockback[1], Knockback[2] },
        };
    }

    [Fact]
    public void Executor_Scenarios_MatchPython()
    {
        var reg = Registry();
        var battlefield = G.GetProperty("battlefield");
        var cases = G.GetProperty("cases").EnumerateArray().ToList();
        var results = G.GetProperty("results").EnumerateArray().ToList();
        Assert.Equal(cases.Count, results.Count);

        for (var i = 0; i < cases.Count; i++)
        {
            var caseEl = cases[i];
            var id = caseEl.GetProperty("id").GetString();

            var byName = new Dictionary<string, ScriptedEntity>();
            var order = new List<ScriptedEntity>();
            foreach (var spec in battlefield.EnumerateArray())
            {
                var ent = new ScriptedEntity(spec);
                byName[ent.Name] = ent;
                order.Add(ent);
            }

            var rng = new PythonRandom(5000 + i);
            var executor = new EffectExecutor(reg, rng.NextDouble);

            var tags = caseEl.GetProperty("tags").EnumerateArray()
                .Select(t => t.GetString()!).ToList();
            var params_ = ParamsFrom(caseEl.GetProperty("params"));

            var ctx = executor.ExecuteEffect(
                byName[caseEl.GetProperty("source").GetString()!],
                byName[caseEl.GetProperty("primary").GetString()!],
                tags, params_,
                order.Cast<ICombatEntity>().ToList());

            var actual = new JsonObject
            {
                ["id"] = id,
                ["targets"] = Strings(ctx.Targets.Select(t => t.Name)),
                ["config"] = ConfigRow(ctx.Config),
                ["entities"] = new JsonArray(order.Select(e => (JsonNode?)e.Row()).ToArray()),
                ["rng_check"] = rng.NextDouble(),
            };
            AssertMatch(results[i], actual, $"case[{id}]");
        }
    }
}
