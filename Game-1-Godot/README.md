# Game-1-Godot — Godot 4 (.NET) migration target

The 3D migration of Game-1. Plan and decisions live in
[../Godot-Migration/](../Godot-Migration/) — read `MIGRATION_PLAN.md` and
`ARCHITECTURE_DECISIONS.md` before touching anything here.

## Layout

```
Game-1-Godot/
├── project.godot            # Godot 4.4 .NET project
├── Game1.sln                # Game1.Core + Game1.Core.Tests + Game1.Godot
├── Game1.Godot.csproj       # engine glue (thin — calls Game1.Core, never implements rules)
├── scenes/ scripts/         # Godot side
├── src/Game1.Core/          # PURE game logic — no Godot reference, dotnet-testable
├── tests/Game1.Core.Tests/  # xunit conformance suite driven by golden fixtures
└── conformance/
    ├── generate_goldens.py  # runs the LIVE Python game modules → fixtures
    └── goldens/*.json       # committed conformance fixtures
```

## One-time setup

1. .NET 8 SDK — `winget install Microsoft.DotNet.SDK.8`
2. Godot 4.4+ **.NET edition** — godotengine.org/download
   (if your Godot minor version differs, update the `Godot.NET.Sdk/x.y.z`
   version in `Game1.Godot.csproj`)

## Daily loop

```bash
# regenerate conformance fixtures from the Python reference build
python conformance/generate_goldens.py

# prove the C# port matches
dotnet test
```

The Python game in `../Game-1-modular/` remains the reference build until the
parity checklist (Godot-Migration/inventory/08-presentation.md) is fully
ticked. Content JSON is read from the shared repo tree — never copied, never
edited from here (ADR-4).
