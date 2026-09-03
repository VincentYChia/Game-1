using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Godot;

namespace Game1.Godot;

public enum InventionStatus { Discovered, Invalid, Unavailable }

/// <summary>The outcome of a discovery attempt (see <see cref="InventionService"/>).</summary>
public sealed record InventionResult(
    InventionStatus Status, string Message,
    JsonObject? Item = null, string OutputId = "", string ItemName = "",
    JsonArray? RecipeInputs = null, int StationTier = 1);

/// <summary>
/// RECIPE DISCOVERY bridge. The C# port can't run the trained CNN/LightGBM placement
/// classifiers or the Claude item generator, so this spawns the Python INVENTION SIDECAR
/// (Game-1-Godot/sidecar/invention_sidecar.py) — which reuses the 2D game's exact models
/// and prompts — and talks to it over a newline-JSON stdio protocol. A placement that the
/// classifier rejects is remembered in a PERSISTED invalid-placement cache so the same dud
/// arrangement is refused instantly next time without paying for a model run (the UX ask).
///
/// All requests are blocking + serialized; call from a background task (the workbench does)
/// and marshal the result back to the Godot main thread. If Python / the models / the API
/// key are unavailable the service degrades to <see cref="InventionStatus.Unavailable"/> —
/// it never throws into the game loop.
/// </summary>
public sealed class InventionService
{
    private readonly string? _script;
    private readonly string _exe;
    private readonly string _cachePath;
    private readonly HashSet<string> _invalid = new();
    private readonly object _lock = new();
    private Process? _proc;
    private bool _spawnFailed;

    public InventionService(string contentRoot)
    {
        _script = LocateScript(contentRoot);
        _exe = LocatePython(_script);
        _cachePath = System.IO.Path.Combine(OS.GetUserDataDir(), "invention_invalid.json");
        LoadInvalidCache();
    }

    public bool Available => _script is not null && !_spawnFailed;

    // ------------------------------------------------------------- public API ----

    /// <summary>Validate + (if valid) generate a novel item for an unmatched placement.</summary>
    public InventionResult Invent(JsonObject signature, string narrative)
    {
        if (IsKnownInvalid(signature))
            return new(InventionStatus.Invalid, "Nothing takes shape — you've tried this arrangement before.");

        var reply = Request(new JsonObject
        {
            ["op"] = "invent",
            ["signature"] = signature.DeepClone(),
            ["narrative"] = narrative,
        });
        if (reply is null)
            return new(InventionStatus.Unavailable,
                "The inventor's workshop is unreachable (Python sidecar / models not found).");
        if (!Truthy(reply["ok"]))
            return new(InventionStatus.Unavailable, Str(reply["error"], "Discovery is unavailable for this craft."));
        if (!Truthy(reply["valid"]))
        {
            RecordInvalid(signature);
            return new(InventionStatus.Invalid, "These materials refuse to combine into anything.");
        }

        var item = reply["item"] as JsonObject;
        var outId = Str(reply["itemId"], null)
                    ?? item?["itemId"]?.GetValue<string>()
                    ?? item?["materialId"]?.GetValue<string>()
                    ?? "invented_item";
        var name = Str(reply["itemName"], null) ?? item?["name"]?.GetValue<string>() ?? "Curious Invention";
        var inputs = reply["recipeInputs"] as JsonArray;
        var tier = Int(reply["stationTier"], 1);
        return new(InventionStatus.Discovered, $"Invented {name}!", item, outId, name, inputs, tier);
    }

    // ---------------------------------------------------- invalid-placement cache ----

    public bool IsKnownInvalid(JsonObject sig)
    {
        lock (_lock) return _invalid.Contains(Signature(sig));
    }

    private void RecordInvalid(JsonObject sig)
    {
        lock (_lock)
        {
            if (_invalid.Add(Signature(sig))) SaveInvalidCache();
        }
    }

    private static string Signature(JsonObject sig)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(sig.ToJsonString()));
        return System.Convert.ToHexString(bytes);
    }

    private void LoadInvalidCache()
    {
        try
        {
            if (!System.IO.File.Exists(_cachePath)) return;
            if (JsonNode.Parse(System.IO.File.ReadAllText(_cachePath)) is JsonArray arr)
                foreach (var n in arr)
                    if (n?.GetValue<string>() is { } s) _invalid.Add(s);
        }
        catch { /* corrupt cache is non-fatal */ }
    }

    private void SaveInvalidCache()
    {
        try
        {
            var arr = new JsonArray();
            foreach (var s in _invalid) arr.Add(s);
            System.IO.File.WriteAllText(_cachePath, arr.ToJsonString());
        }
        catch { /* best-effort */ }
    }

    // --------------------------------------------------------- sidecar transport ----

    private JsonObject? Request(JsonObject req)
    {
        lock (_lock)
        {
            if (!EnsureProc() || _proc is null) return null;
            try
            {
                _proc.StandardInput.WriteLine(req.ToJsonString());
                _proc.StandardInput.Flush();
                // stdout is pure JSON (the sidecar routes library chatter to stderr); skip
                // any stray blank line, then parse the reply.
                string? line;
                while ((line = _proc.StandardOutput.ReadLine()) is not null)
                {
                    var t = line.TrimStart();
                    if (t.StartsWith('{')) return JsonNode.Parse(t) as JsonObject;
                }
                return null;   // pipe closed
            }
            catch
            {
                try { _proc?.Kill(true); } catch { /* ignore */ }
                _proc = null;
                return null;
            }
        }
    }

    private bool EnsureProc()
    {
        if (_proc is { HasExited: false }) return true;
        if (_spawnFailed || _script is null) return false;
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = _exe,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
            };
            psi.ArgumentList.Add(_script);
            _proc = Process.Start(psi);
            if (_proc is null) { _spawnFailed = true; return false; }
            // Tie the sidecar to the game process so it can never be orphaned and
            // left spinning in the background if the game is force-killed (editor
            // Stop / Ctrl+C / crash), where Shutdown() below never runs.
            ProcessJob.Register(_proc);
            // drain stderr so a full pipe never blocks the sidecar
            _proc.ErrorDataReceived += (_, _) => { };
            _proc.BeginErrorReadLine();
            return true;
        }
        catch
        {
            _spawnFailed = true;
            return false;
        }
    }

    // ---------------------------------------------------------------- locate ----

    private static string? LocateScript(string contentRoot)
    {
        var dir = new System.IO.DirectoryInfo(contentRoot);
        for (var i = 0; i < 5 && dir is not null; i++, dir = dir.Parent)
        {
            var p = System.IO.Path.Combine(dir.FullName, "Game-1-Godot", "sidecar", "invention_sidecar.py");
            if (System.IO.File.Exists(p)) return p;
        }
        return null;
    }

    /// <summary>Prefer the repo venv, then an env override, then PATH python.</summary>
    private static string LocatePython(string? script)
    {
        if (script is not null)
        {
            var repo = System.IO.Directory.GetParent(script)?.Parent?.Parent?.FullName;   // .../sidecar → Godot → repo
            if (repo is not null)
            {
                var venv = System.IO.Path.Combine(repo, ".venv", "Scripts", "python.exe");
                if (System.IO.File.Exists(venv)) return venv;
            }
        }
        var env = System.Environment.GetEnvironmentVariable("GAME1_PYTHON");
        return !string.IsNullOrWhiteSpace(env) ? env : "python";
    }

    // ------------------------------------------------------------- json utils ----
    private static bool Truthy(JsonNode? n) => n is JsonValue v && v.TryGetValue<bool>(out var b) && b;
    private static string? Str(JsonNode? n, string? fallback)
        => n is JsonValue v && v.TryGetValue<string>(out var s) ? s : fallback;
    private static int Int(JsonNode? n, int fallback)
    {
        if (n is JsonValue v)
        {
            if (v.TryGetValue<int>(out var i)) return i;
            if (v.TryGetValue<double>(out var d)) return (int)d;
        }
        return fallback;
    }

    public void Shutdown()
    {
        lock (_lock)
        {
            try { _proc?.Kill(true); } catch { /* ignore */ }
            _proc = null;
        }
    }
}
