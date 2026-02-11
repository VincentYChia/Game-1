# Unity Project (Game-1 Unity)

This directory will contain the Unity project for the Game-1 migration.

## Status: Not Yet Created

The Unity project will be initialized when Phase 1 of the migration begins.

## Planned Structure
```
Unity/
├── Assets/
│   ├── Scripts/
│   │   ├── Game1.Core/          # GameManager, Config, MigrationLogger
│   │   ├── Game1.Data/          # Models and Databases
│   │   │   ├── Models/          # C# data classes
│   │   │   └── Databases/       # Singleton database loaders
│   │   ├── Game1.Entities/      # Character, Components, Enemies
│   │   │   ├── Character/       # Player character
│   │   │   ├── Components/      # Stats, Inventory, Equipment, Skills
│   │   │   └── Enemies/         # Enemy definitions and AI
│   │   ├── Game1.Systems/       # Game systems
│   │   │   ├── Combat/          # Combat manager, damage pipeline
│   │   │   ├── Crafting/        # Crafting logic and minigames
│   │   │   ├── World/           # World generation, chunks, biomes
│   │   │   ├── ML/              # ONNX model inference via Sentis
│   │   │   ├── LLM/             # LLM stub interface
│   │   │   └── Save/            # Save/load system
│   │   └── Game1.UI/            # UI Toolkit components
│   ├── Resources/
│   │   ├── JSON/                # Game data files (copied from Python)
│   │   └── Models/              # ONNX model files
│   ├── Tests/
│   │   ├── EditMode/            # Unit tests (no scene required)
│   │   └── PlayMode/            # Integration tests (scene required)
│   └── StreamingAssets/
│       └── Content/             # Moddable JSON content
├── Packages/                    # Unity package manifest
└── ProjectSettings/             # Unity project settings
```

## Prerequisites
- Unity 2022.3 LTS or later
- Unity Sentis package (for ML model inference)
- NUnit (included with Unity Test Framework)
