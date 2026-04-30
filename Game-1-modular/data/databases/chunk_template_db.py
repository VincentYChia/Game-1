"""ChunkTemplateDatabase — single source of truth for biome chunk templates.

Loads two layers and overlays them last-writer-wins:

1. Sacred templates from ``Definitions.JSON/Chunk-templates-*.JSON``
   (the canonical, hand-tuned biome library).
2. Generated templates from ``Definitions.JSON/Chunk-templates-generated-*.JSON``
   (additive files written by :mod:`world_system.content_registry` after WES
   commits new biome templates). Generated entries override duplicates.

Each sacred / generated file has the same wrapper shape::

    {"metadata": {...}, "templates": [ {chunkType, name, ...}, ... ]}

The database also loads the geographic dispatch bridge at
``world_system/config/geo_chunk_dispatch.json``, which maps biome strings
emitted by the geography system (``"forest"``, ``"dense_thicket"``, ...) to
canonical ``chunkType`` values that exist in the templates.

A WES-generated template can declare its own ``geoTypes: ["..."]`` array to
auto-register additional dispatch entries without editing the bridge file
(sacred dispatch wins on collision — designers stay in control of the
canonical mapping).

This module is imported by:

- ``systems/chunk.py`` (chunk dispatch + density-driven resource spawning)
- ``Combat/combat_manager.py`` (enemy spawn pool weighting)
- ``world_system/content_registry/database_reloader.py`` (post-commit reload)

It never raises on disk errors — the singleton degrades to whatever it
loaded successfully and prints a warning. This matches the policy of every
other singleton database in :mod:`data.databases`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from core.paths import get_resource_path


# ── Density / tier-bias allow-lists ───────────────────────────────────────
# Mirrors prompt_fragments_tool_chunks.json. Spawn weights are the
# multiplicative factors applied to a base 1.0x weight in chunk.py /
# combat_manager.py. Keep these in sync with combat-config.JSON's
# density_weights mirror.

DENSITY_WEIGHTS: Dict[str, float] = {
    "very_low":  0.5,
    "low":       0.75,
    "moderate":  1.0,
    "high":      2.0,
    "very_high": 3.0,
}

TIER_BIAS_ORDER: Dict[str, int] = {
    "low":       1,
    "mid":       2,
    "high":      3,
    "legendary": 4,
}


# ── Typed records ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResourceDensitySpec:
    """One row of a template's ``resourceDensity`` map."""
    resource_id: str
    density: str            # one of DENSITY_WEIGHTS keys
    tier_bias: str          # one of TIER_BIAS_ORDER keys

    @property
    def spawn_weight(self) -> float:
        """Resolve density string → weight float, fallback 1.0 on unknown."""
        return DENSITY_WEIGHTS.get(self.density, 1.0)

    @property
    def tier_bias_rank(self) -> int:
        return TIER_BIAS_ORDER.get(self.tier_bias, 1)


@dataclass(frozen=True)
class EnemySpawnSpec:
    """One row of a template's ``enemySpawns`` map."""
    enemy_id: str
    density: str            # one of DENSITY_WEIGHTS keys
    tier: int               # 1-4

    @property
    def spawn_weight(self) -> float:
        return DENSITY_WEIGHTS.get(self.density, 1.0)


@dataclass(frozen=True)
class GenerationRules:
    """``generationRules`` block on a template."""
    roll_weight: int = 1
    spawn_area_allowed: bool = False
    adjacency_preference: tuple = ()
    edge_only: bool = False
    min_distance_between: int = 0


@dataclass
class ChunkTemplate:
    """One biome template loaded from JSON."""

    chunk_type: str
    name: str
    category: str           # peaceful / dangerous / rare / water / rare_water
    theme: str              # forest / quarry / cave / water
    resource_density: Dict[str, ResourceDensitySpec] = field(default_factory=dict)
    enemy_spawns: Dict[str, EnemySpawnSpec] = field(default_factory=dict)
    generation_rules: GenerationRules = field(default_factory=GenerationRules)
    narrative: str = ""
    tags: List[str] = field(default_factory=list)
    tile_pattern: Optional[Dict] = None
    geo_types: List[str] = field(default_factory=list)
    source: str = "sacred"  # "sacred" | "generated"

    @property
    def is_water(self) -> bool:
        return self.theme == "water" or self.category in ("water", "rare_water")

    def spawn_pool_resources(self) -> List[ResourceDensitySpec]:
        """Resource specs as a list, ordered by resource_id (stable iteration)."""
        return [self.resource_density[k] for k in sorted(self.resource_density)]

    def spawn_pool_enemies(self) -> List[EnemySpawnSpec]:
        return [self.enemy_spawns[k] for k in sorted(self.enemy_spawns)]


# ── Loaders ───────────────────────────────────────────────────────────────

def _build_resource_density(raw: Dict) -> Dict[str, ResourceDensitySpec]:
    out: Dict[str, ResourceDensitySpec] = {}
    if not isinstance(raw, dict):
        return out
    for resource_id, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        out[resource_id] = ResourceDensitySpec(
            resource_id=resource_id,
            density=str(spec.get("density", "moderate")),
            tier_bias=str(spec.get("tierBias", "low")),
        )
    return out


def _build_enemy_spawns(raw: Dict) -> Dict[str, EnemySpawnSpec]:
    out: Dict[str, EnemySpawnSpec] = {}
    if not isinstance(raw, dict):
        return out
    for enemy_id, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        try:
            tier_int = int(spec.get("tier", 1))
        except (TypeError, ValueError):
            tier_int = 1
        out[enemy_id] = EnemySpawnSpec(
            enemy_id=enemy_id,
            density=str(spec.get("density", "moderate")),
            tier=max(1, min(4, tier_int)),
        )
    return out


def _build_generation_rules(raw: Dict) -> GenerationRules:
    if not isinstance(raw, dict):
        return GenerationRules()
    try:
        roll_weight = int(raw.get("rollWeight", 1))
    except (TypeError, ValueError):
        roll_weight = 1
    adj = raw.get("adjacencyPreference", [])
    if not isinstance(adj, list):
        adj = []
    try:
        min_dist = int(raw.get("minDistanceBetween", 0))
    except (TypeError, ValueError):
        min_dist = 0
    return GenerationRules(
        roll_weight=roll_weight,
        spawn_area_allowed=bool(raw.get("spawnAreaAllowed", False)),
        adjacency_preference=tuple(adj),
        edge_only=bool(raw.get("edgeOnly", False)),
        min_distance_between=min_dist,
    )


def _build_template(raw: Dict, source: str) -> Optional[ChunkTemplate]:
    if not isinstance(raw, dict):
        return None
    chunk_type = raw.get("chunkType")
    if not isinstance(chunk_type, str) or not chunk_type:
        return None
    metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {}
    geo_types_raw = raw.get("geoTypes", [])
    if not isinstance(geo_types_raw, list):
        geo_types_raw = []
    return ChunkTemplate(
        chunk_type=chunk_type,
        name=str(raw.get("name", chunk_type)),
        category=str(raw.get("category", "peaceful")),
        theme=str(raw.get("theme", "forest")),
        resource_density=_build_resource_density(raw.get("resourceDensity", {})),
        enemy_spawns=_build_enemy_spawns(raw.get("enemySpawns", {})),
        generation_rules=_build_generation_rules(raw.get("generationRules", {})),
        narrative=str(metadata.get("narrative", "")),
        tags=list(metadata.get("tags", [])) if isinstance(metadata.get("tags"), list) else [],
        tile_pattern=raw.get("tilePattern") if isinstance(raw.get("tilePattern"), dict) else None,
        geo_types=[str(g) for g in geo_types_raw if isinstance(g, str)],
        source=source,
    )


# ── Singleton ─────────────────────────────────────────────────────────────

class ChunkTemplateDatabase:
    """Singleton chunk-template registry.

    Lifecycle::

        db = ChunkTemplateDatabase.get_instance()
        db.load_from_files()           # called automatically on first access
        template = db.get("peaceful_forest")
        for t in db.get_for_geo_type("forest"):
            ...

        # After ContentRegistry commits a generated file:
        db.reload()
    """

    _instance: ClassVar[Optional["ChunkTemplateDatabase"]] = None

    SACRED_GLOB: ClassVar[str] = "Chunk-templates-*.JSON"
    GENERATED_GLOB: ClassVar[str] = "Chunk-templates-generated-*.JSON"
    SACRED_DIR: ClassVar[str] = "Definitions.JSON"
    DISPATCH_PATH: ClassVar[str] = "world_system/config/geo_chunk_dispatch.json"

    def __init__(self) -> None:
        self.templates: Dict[str, ChunkTemplate] = {}
        self._geo_dispatch: Dict[str, str] = {}
        self._loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ChunkTemplateDatabase":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_from_files()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton so the next get_instance reloads."""
        cls._instance = None

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ── Loading ──────────────────────────────────────────────────────────

    def load_from_files(self) -> None:
        """Read sacred + generated template files and the geo dispatch bridge.

        Idempotent. Never raises — failures degrade to whatever was already
        loaded (or empty state on first call).
        """
        try:
            self.templates = {}
            self._geo_dispatch = {}
            self._load_sacred_templates()
            self._load_generated_templates()
            self._load_geo_dispatch()
            self._auto_register_geo_types()
            self._loaded = True
        except Exception as e:
            print(f"[ChunkTemplateDatabase] load_from_files outer error: {e}")
            self._loaded = False

    def reload(self) -> None:
        """Re-read all template + dispatch files from disk.

        Called by :func:`world_system.content_registry.database_reloader`
        after the Content Registry commits new ``Chunk-templates-generated-*``
        files. Drops in-memory caches and reloads. Never raises; on any
        failure the previous in-memory state is preserved (prefer stale-
        but-intact over crashing the chunk dispatcher).
        """
        old_templates = dict(self.templates)
        old_dispatch = dict(self._geo_dispatch)
        old_loaded = self._loaded
        try:
            self.load_from_files()
        except Exception as e:
            print(f"[ChunkTemplateDatabase] reload failed, keeping previous: {e}")
            self.templates = old_templates
            self._geo_dispatch = old_dispatch
            self._loaded = old_loaded

    def _load_sacred_templates(self) -> None:
        """Load every ``Definitions.JSON/Chunk-templates-*.JSON`` that is
        not a generated file. Iteration order is deterministic — sorted by
        filename — so later sacred numbered files override earlier ones.
        """
        try:
            sacred_dir = get_resource_path(self.SACRED_DIR)
        except Exception:
            return
        if not sacred_dir.exists():
            return

        # glob is case-sensitive on Linux; match the actual on-disk
        # capitalization (Chunk-templates-2.JSON).
        for path in sorted(sacred_dir.glob(self.SACRED_GLOB)):
            # Skip generated files — they are loaded second so they win.
            if "generated" in path.name.lower():
                continue
            self._merge_template_file(path, source="sacred")

    def _load_generated_templates(self) -> None:
        """Overlay any generated files on top of sacred."""
        try:
            sacred_dir = get_resource_path(self.SACRED_DIR)
        except Exception:
            return
        if not sacred_dir.exists():
            return
        for path in sorted(sacred_dir.glob(self.GENERATED_GLOB)):
            self._merge_template_file(path, source="generated")

    def _merge_template_file(self, path: Path, *, source: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ChunkTemplateDatabase] failed to load {path.name}: {e}")
            return
        # Sacred file uses "templates"; tolerate the placeholder
        # "chunkTemplates" key in case any old generated file used that.
        templates_raw = data.get("templates")
        if templates_raw is None:
            templates_raw = data.get("chunkTemplates", [])
        if not isinstance(templates_raw, list):
            return
        for raw in templates_raw:
            tmpl = _build_template(raw, source=source)
            if tmpl is None:
                continue
            self.templates[tmpl.chunk_type] = tmpl

    def _load_geo_dispatch(self) -> None:
        """Load ``world_system/config/geo_chunk_dispatch.json``.

        Format: ``{"<geo_type>": "<chunk_type>", ...}``. Missing file is
        non-fatal — fallback to empty dict, callers degrade to legacy
        behavior (chunk.py keeps an internal default for back-compat).
        """
        try:
            dispatch_path = get_resource_path(self.DISPATCH_PATH)
        except Exception:
            return
        if not dispatch_path.exists():
            return
        try:
            with open(dispatch_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ChunkTemplateDatabase] failed to load dispatch: {e}")
            return
        mapping = data.get("geo_to_chunk_type", data)
        if not isinstance(mapping, dict):
            return
        for geo_key, chunk_type in mapping.items():
            if isinstance(geo_key, str) and isinstance(chunk_type, str):
                self._geo_dispatch[geo_key] = chunk_type

    def _auto_register_geo_types(self) -> None:
        """Honor templates' ``geoTypes`` arrays.

        Sacred dispatch entries (loaded from JSON) win on collision so the
        designer stays in control of the canonical mapping. Generated
        templates can introduce NEW geo_type → chunk_type entries when
        the sacred file doesn't already define them.
        """
        for template in self.templates.values():
            for geo_type in template.geo_types:
                self._geo_dispatch.setdefault(geo_type, template.chunk_type)

    # ── Queries ──────────────────────────────────────────────────────────

    def get(self, chunk_type: str) -> Optional[ChunkTemplate]:
        return self.templates.get(chunk_type)

    def has(self, chunk_type: str) -> bool:
        return chunk_type in self.templates

    def list_chunk_types(self) -> List[str]:
        return sorted(self.templates)

    def get_all(self) -> List[ChunkTemplate]:
        return [self.templates[k] for k in sorted(self.templates)]

    def get_by_category(self, category: str) -> List[ChunkTemplate]:
        return [t for t in self.get_all() if t.category == category]

    def get_by_theme(self, theme: str) -> List[ChunkTemplate]:
        return [t for t in self.get_all() if t.theme == theme]

    def get_for_geo_type(self, geo_type: str) -> Optional[ChunkTemplate]:
        """Return the canonical template for a geographic system biome string.

        Returns None if no dispatch entry exists or the dispatched chunk_type
        doesn't resolve to a loaded template.
        """
        chunk_type = self._geo_dispatch.get(geo_type)
        if not chunk_type:
            return None
        return self.templates.get(chunk_type)

    def geo_dispatch_map(self) -> Dict[str, str]:
        """Expose the resolved geo→chunk_type bridge for callers that
        need the raw map (e.g. tests, debug overlay, prompt studio).
        """
        return dict(self._geo_dispatch)

    def stats(self) -> Dict[str, int]:
        sacred = sum(1 for t in self.templates.values() if t.source == "sacred")
        generated = sum(1 for t in self.templates.values() if t.source == "generated")
        return {
            "total": len(self.templates),
            "sacred": sacred,
            "generated": generated,
            "geo_dispatch_entries": len(self._geo_dispatch),
        }


__all__ = [
    "ChunkTemplateDatabase",
    "ChunkTemplate",
    "ResourceDensitySpec",
    "EnemySpawnSpec",
    "GenerationRules",
    "DENSITY_WEIGHTS",
    "TIER_BIAS_ORDER",
]
