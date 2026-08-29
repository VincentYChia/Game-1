"""Grounded coordinate tables -- the stable, code-verified facts the Phase 2-4 extractors
consume (SQLite junction shapes, ML encoders, C# mirrors, Godot unmirrored tables, the
EffectConfig contract). Verified against current source on branch godot-migration
(2026-08-29) by the phase-234 grounding workflow.

These are structural facts about the repo that a call-graph can't derive. They are curated
here (not re-parsed every build) because the schema is code-defined and stable; the Phase 3
coverage self-check + DriftDetector flag when a curated location goes stale (yields zero
sites), so drift is caught rather than silently trusted.

All paths are repo-root-relative (base = Game-1/, forward-slashed) so they're openable.
"""

from __future__ import annotations

# ── Phase 2: SQLite tag-junction stores (for SchemaExtractor + DbRowProbe) ──
# The 4 on-disk WMS/WNS databases and their junction shapes.
STORES = [
    {
        "store": "layer_store", "shape": "split_column", "db": "layer_store.db",
        "module": "Game-1-modular/world_system/world_memory/layer_store.py",
        "ddl_line": 57, "and_match_line": 263,
        "junctions": [f"layer{n}_tags" for n in range(2, 8)],
        "events_tables": [f"layer{n}_events" for n in range(2, 8)],
        "value_col": "tag_value", "cat_col": "tag_category",
        "tags_json": True, "tags_json_note": "layer{N}_events.tags_json (denormalized, keep in sync)",
        "version_gate": None,
        "note": "AND-match: HAVING COUNT(DISTINCT tag_category||':'||tag_value). Junction rows only for tags containing ':'.",
    },
    {
        "store": "stat_store", "shape": "split_column", "db": "world_memory.db",
        "module": "Game-1-modular/world_system/world_memory/stat_store.py",
        "ddl_line": 47, "and_match_line": 456,
        "junctions": ["stat_tags"], "events_tables": ["stats"],
        "value_col": "tag_value", "cat_col": "tag_category",
        "tags_json": True, "tags_json_note": "stats.tags column (redundant with stat_tags)",
        "version_gate": None,
        "note": "Rides EventStore's connection -> physically inside world_memory.db (NO stat_store.db). Junction keyed by stat name.",
    },
    {
        "store": "event_store", "shape": "single_opaque", "db": "world_memory.db",
        "module": "Game-1-modular/world_system/world_memory/event_store.py",
        "ddl_line": 81, "and_match_line": 644,
        "junctions": ["event_tags", "interpretation_tags", "connected_interpretation_tags"],
        "events_tables": ["events"], "tag_col": "tag",
        "tags_json": False, "tags_json_note": "none (raw events store tags ONLY in event_tags)",
        "version_gate": 2,
        "note": "SINGLE-OPAQUE tag column. AND-match = per-tag correlated EXISTS chain, NOT a HAVING COUNT. SCHEMA_VERSION=2 fail-fast gate (schema_meta).",
    },
    {
        "store": "narrative_store", "shape": "single_opaque", "db": "world_narrative.db",
        "module": "Game-1-modular/world_system/wns/narrative_store.py",
        "ddl_line": 124, "and_match_line": None,
        "junctions": [f"nl{n}_tags" for n in range(1, 8)],
        "events_tables": [f"nl{n}_events" for n in range(1, 8)], "tag_col": "tag",
        "tags_json": True, "tags_json_note": "nl{N}_events.tags_json (redundant with nl{N}_tags)",
        "version_gate": 1,
        "note": "SINGLE-OPAQUE, PK(event_id,tag) dedup. NO tag-intersection query (address-keyed retrieval). v1 stored but NOT enforced.",
    },
]
# Directories to search for the on-disk .db files (DbRowProbe). First existing wins per db name.
DB_SEARCH_GLOBS = [
    "crux-foundry/runs/*/wms",
    "Game-1-modular/saves/*/wms",
    "Game-1-modular/saves/wes_sidecar",
    "Game-1-modular/saves",
]

# ── Phase 2: ML encoders (for MlVocabExtractor + ml_vocab_impact) ──
CRAFTING_CLASSIFIER = "Game-1-modular/systems/crafting_classifier.py"
# Each spec: the encoder, where it lives, its kind, whether count-sensitive, its key vocab,
# the mirror copies that must stay in sync, and the model artifacts it bakes into.
ENCODER_SPECS = [
    {"name": "ELEMENT_HUES", "line": 88, "kind": "cnn_hue", "count_sensitive": False,
     "keys": ["fire", "water", "earth", "air", "lightning", "ice", "light", "dark", "void", "chaos"],
     "role": "CNN hue for category=='elemental' -- first material TAG wins the hue",
     "silent_failure": "rename -> CNN encodes a different color than trained -> silent accuracy loss, no error",
     "mirror_group": "cnn_smithing_encoder", "artifacts": ["smithing", "adornments"]},
    {"name": "CATEGORY_HUES", "line": 77, "kind": "cnn_hue", "count_sensitive": False,
     "keys": ["metal", "wood", "stone", "monster_drop", "gem", "herb", "fabric"],
     "role": "CNN hue by material.category",
     "silent_failure": "rename -> different training-vs-runtime color; adornment mirror ALREADY DRIFTED (wood/stone)",
     "mirror_group": "cnn_smithing_encoder", "artifacts": ["smithing", "adornments"]},
    {"name": "CATEGORY_TO_IDX", "line": 512, "kind": "category_idx", "count_sensitive": True,
     "keys": ["elemental", "metal", "monster_drop", "stone", "wood"],
     "role": "LightGBM alchemy category->int index (frozen snapshot of trainer sorted vocab)",
     "silent_failure": "add/remove a category -> desyncs trainer indices -> wrong feature; must regen + retrain all 3 LGBM",
     "mirror_group": "lgbm_category_vocab", "artifacts": ["alchemy", "engineering", "refining"]},
    {"name": "lgbm_5category_order", "line": 626, "kind": "lgbm_positional", "count_sensitive": True,
     "keys": ["elemental", "metal", "monster_drop", "stone", "wood"],
     "role": "LightGBM Counter->5 fixed columns in EXACT order (refining 626 / alchemy 716 / engineering 805)",
     "silent_failure": "rename within count -> column reads 0; count change -> feature-shape mismatch (guard crafting_classifier.py:974)",
     "mirror_group": "lgbm_category_vocab", "artifacts": ["alchemy", "engineering", "refining"]},
    {"name": "engineering_slot_order", "line": 784, "kind": "slot_onehot", "count_sensitive": True,
     "keys": ["FRAME", "FUNCTION", "POWER", "MODIFIER", "UTILITY", "ENHANCEMENT", "CORE", "CATALYST"],
     "role": "LightGBM engineering 8-slot one-hot (28-feature vector)",
     "silent_failure": "reorder/rename -> column reads 0; count change -> 28-feature shape mismatch",
     "mirror_group": None, "artifacts": ["engineering"]},
    {"name": "REFINEMENT_VOCAB", "line": 523, "kind": "lgbm_positional", "count_sensitive": True,
     "keys": ["basic"],
     "role": "LightGBM refinement-level (only 'basic' counted -> 1 column)",
     "silent_failure": "adding a refinement level -> feature-shape mismatch",
     "mirror_group": None, "artifacts": ["alchemy", "engineering", "refining"]},
]
# CNN encoder duplicate copies (mirror_group cnn_smithing_encoder) -- the drift surface.
CNN_ENCODER_COPIES = [
    ("Scaled JSON Development/Convolution Neural Network (CNN)/Smithing/valid_smithing_data_v2.py", 57, "in-sync -- declared source of smithing_best.keras"),
    ("Scaled JSON Development/LLM Training Data/crafting_training_data.py", 349, "in-sync"),
    ("Scaled JSON Development/Convolution Neural Network (CNN)/Adornment/data_augment_adornment_v2.py", 52, "*** DRIFTED: wood:30/stone:0 vs runtime wood:45/stone:200 -- adornment_best.keras stale ***"),
    ("Scaled JSON Development/Convolution Neural Network (CNN)/Smithing/CNN_game_runner_smithing.py", 16, "shape-only mirror, in-sync"),
]
MODEL_ARTIFACTS = {
    "smithing": ["Scaled JSON Development/crafting_classifier_models/smithing/smithing_best.keras"],
    "adornments": ["Scaled JSON Development/crafting_classifier_models/adornment/adornment_best.keras"],
    "alchemy": ["Scaled JSON Development/crafting_classifier_models/alchemy/alchemy_model.txt"],
    "engineering": ["Scaled JSON Development/crafting_classifier_models/engineering/engineering_model.txt"],
    "refining": ["Scaled JSON Development/crafting_classifier_models/refining/refining_model.txt"],
}
ML_COUNT_MISMATCH_SITE = (CRAFTING_CLASSIFIER, 974,
                          "LightGBM feature-count mismatch guard -> returns 0.0 (validation error, non-blocking)")
ML_TRAINING_INPUT = "Game-1-modular/items.JSON/items-materials-1.JSON (material master any retrain re-keys against)"

# ── Phase 3: C# core mirrors (curated, each pinned by effect_stack.json) ──
# `covers` = how to attach the mirror to concepts: {"category": X} attaches to every value in
# that combat category; {"values": [...]} attaches to those specific values.
MIRROR_PAIRS = [
    {"group": "special_dispatch", "kind": "dispatch_if_chain", "covers": {"category": "special"},
     "py": ("Game-1-modular/core/effect_executor.py", 225),
     "cs": ("Game-1-Godot/src/Game1.Core/Combat/EffectExecutor.cs", 212),
     "pinned_by_test": "Game-1-Godot/tests/Game1.Core.Tests/EffectStackTests.cs (effect_stack.json)",
     "note": "special_tag if/elif chain (lifesteal/vampiric, knockback, pull, execute, teleport/blink, dash/charge, phase/ethereal). 'summon' TODO both sides."},
    {"group": "category_switch", "kind": "category_switch", "covers": {"kind": "tag_category"},
     "py": ("Game-1-modular/core/tag_parser.py", 43),
     "cs": ("Game-1-Godot/src/Game1.Core/Tags/TagParser.cs", 63),
     "pinned_by_test": "Game-1-Godot/tests/Game1.Core.Tests/EffectStackTests.cs (effect_stack.json)",
     "note": "category bucket switch; status_debuff|status_buff both collapse to status; 'Unknown tag: {tag}' warning byte-compared."},
    {"group": "weapon_tag_modifiers", "kind": "constant_table",
     "covers": {"values": ["2H", "versatile", "fast", "precision", "reach", "armor_breaker", "crushing", "cleaving"]},
     "py": ("Game-1-modular/entities/components/weapon_tag_calculator.py", 15),
     "cs": ("Game-1-Godot/src/Game1.Core/Combat/WeaponTagModifiers.cs", 8),
     "pinned_by_test": "Game-1-Godot/tests/Game1.Core.Tests/EquipmentTests.cs (effect_stack.json)",
     "note": "8 pure functions with hardcoded magic constants (2H x1.2 etc.) -- highest byte-alignment risk (no shared JSON)."},
    {"group": "smithing_slot_inference", "kind": "ordered_dict_lookup", "covers": {"values": ["weapon", "armor", "tool"]},
     "py": ("Game-1-modular/core/crafting_tag_processor.py", 30),
     "cs": ("Game-1-Godot/src/Game1.Core/Crafting/TagProcessors.cs", 8),
     "pinned_by_test": "Game-1-Godot/tests/Game1.Core.Tests/EquipmentTests.cs (effect_stack.json)",
     "note": "recipe-tag -> equipment slot via 3 ordered dict lookups; precedence order load-bearing."},
    {"group": "enchant_applicability", "kind": "rule_dict_lookup", "covers": {"values": ["universal", "weapon", "armor", "tool"]},
     "py": ("Game-1-modular/core/crafting_tag_processor.py", 186),
     "cs": ("Game-1-Godot/src/Game1.Core/Crafting/TagProcessors.cs", 47),
     "pinned_by_test": "Game-1-Godot/tests/Game1.Core.Tests/EquipmentTests.cs (effect_stack.json)",
     "note": "recipe-tag -> allowed item-types; failure string byte-compared."},
]

# ── Phase 3: Godot unmirrored tag tables to regex-scan (kind=csharp_mirror, UNGUARDED) ──
GODOT_TAG_FILES = [
    "Game-1-Godot/scripts/minigames/MinigameTagEffects.cs",
    "Game-1-Godot/scripts/minigames/SmithingMinigame.cs",
    "Game-1-Godot/scripts/minigames/RefiningMinigame.cs",
    "Game-1-Godot/scripts/minigames/EngineeringMinigame.cs",
    "Game-1-Godot/scripts/minigames/EnchantingMinigame.cs",
    "Game-1-Godot/scripts/SkillVfx.cs",
    "Game-1-Godot/scripts/CombatWorld.cs",
]
GODOT_UNMIRRORED_SUMMARY = "~33 tag-keyed tables / ~1230 entries across the Godot presentation layer; the modifier bank exists in 4 independently-tuned copies; ZERO test guards."

# ── Phase 4: EffectConfig output contract (13 fields, 4 lockstep sites) ──
EFFECTCONFIG_FIELDS = [
    "raw_tags", "geometry_tag", "damage_tags", "status_tags", "context_tags",
    "special_tags", "trigger_tags", "context", "base_damage", "base_healing",
    "params", "warnings", "conflicts_resolved",
]
EFFECTCONFIG_SITES = [  # the 4 sites that MUST stay in lockstep
    ("Game-1-modular/core/effect_context.py", 10, "python", "Python @dataclass EffectConfig (13 fields)"),
    ("Game-1-Godot/src/Game1.Core/Tags/TagParser.cs", 6, "csharp", "C# EffectConfig class (PascalCase mirror, colocated in TagParser.cs)"),
    ("Game-1-Godot/conformance/dump_databases.py", 1543, "python", "Python oracle serializer config_row() -> 13-key JSON"),
    ("Game-1-Godot/tests/Game1.Core.Tests/EffectStackTests.cs", 63, "csharp", "C# oracle serializer ConfigRow() -> JSON-tree diff"),
]
ORDERING_SITES = [
    ("Game-1-modular/core/tag_parser.py", 96,
     "base_damage/base_healing snapshotted from params BEFORE synergies; synergies mutate params in place but do NOT re-derive base_damage. Reordering breaks the golden."),
    ("Game-1-Godot/src/Game1.Core/Tags/TagParser.cs", 127,
     "C# mirror of the base-damage-before-synergies invariant (explicit comment)."),
]
GOLDEN_TESTS = [
    ("Game-1-Godot/tests/Game1.Core.Tests/EffectStackTests.cs", "PRIMARY parser-output golden (ConfigRow diff vs effect_stack.json)"),
    ("Game-1-Godot/tests/Game1.Core.Tests/TagAttackTests.cs", "downstream damage/crit/loot cascade (transitively affected)"),
]
GOLDEN_FIXTURE = "Game-1-Godot/conformance/goldens/db_parity/effect_stack.json"

# ── Phase 4: what a NEW combat category structurally requires (category_requires) ──
CATEGORY_REQUIRES = [
    "Game-1-modular/Definitions.JSON/tag-definitions.JSON -- register the new category + its tag VALUES here FIRST (else registry.get_category() returns 'unknown' and the parser branch never fires)",
    "Game-1-modular/core/tag_parser.py:46 -- add an elif branch in the category bucket loop",
    "Game-1-modular/core/effect_context.py -- add a new list field on EffectConfig (Python)",
    "Game-1-Godot/src/Game1.Core/Tags/TagParser.cs:6 -- add the mirror field on C# EffectConfig",
    "Game-1-Godot/src/Game1.Core/Tags/TagParser.cs:63 -- add the C# category switch case",
    "Game-1-modular/core/effect_executor.py -- add a Python consumer that reads the new bucket",
    "Game-1-Godot/src/Game1.Core/Combat/EffectExecutor.cs:116 -- add the C# consumer (parallel to Python at 116/124/181/215; else the category is a SILENT no-op in the built Godot game)",
    "Game-1-Godot/conformance/dump_databases.py:1543 + EffectStackTests.cs:63 -- extend BOTH config_row serializers",
    "Game-1-Godot/conformance/goldens/db_parity/effect_stack.json -- regenerate the golden fixture",
    "VFX/palette tables (SkillVfx.cs, animation/combat_particles.py) -- add a color branch if the category is visual",
]
