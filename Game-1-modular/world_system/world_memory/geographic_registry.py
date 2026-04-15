"""Geographic Registry — named region hierarchy overlaid on the chunk grid.

Maps every position to a human-readable address, following the **game's**
geographic hierarchy 1:1:

    World > Nation > Region > Province > District > Locality (sparse POI)

Hierarchy rules:
- Every chunk deterministically has World, Nation, Region, Province, and
  District. These tiers are always present.
- Locality is sparse — a chunk only has a Locality when a POI (e.g.
  village) has been placed there. See
  systems/geography/village_generator.py.

Address tags emitted at Layer 2 capture mirror this hierarchy exactly:
  world:world_0, nation:nation_{id}, region:region_{id},
  province:province_{id}, district:district_{id},
  locality:locality_{id}  (optional).

This registry is the source of truth for parent→child walking and for
`get_full_address(x, y)` lookups used by the event recorder.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Tuple


class RegionLevel(Enum):
    """6-tier hierarchy matching the game's geography system 1:1.

    Order (finest → coarsest): LOCALITY, DISTRICT, PROVINCE, REGION,
    NATION, WORLD.
    """
    LOCALITY = "locality"     # Sparse POI — only present if chunk has locality_id >= 0
    DISTRICT = "district"     # Game District — always present per chunk
    PROVINCE = "province"     # Game Province — always present per chunk
    REGION = "region"         # Game Region — always present per chunk
    NATION = "nation"         # Game Nation — always present per chunk
    WORLD = "world"           # Game World — always present (singleton)


# ══════════════════════════════════════════════════════════════════
# Canonical address tiers — single source of truth
# ══════════════════════════════════════════════════════════════════
#
# Every module that touches address tags — layer managers, layer
# summarizers, event recorder, tag assigner, tag library, tests —
# imports from here. DO NOT redeclare these tuples elsewhere.
#
# See docs/ARCHITECTURAL_DECISIONS.md §6:
#   - Address tags are FACTS, assigned at L2 capture.
#   - One tier per layer; each layer drops the finest address tag
#     on its output.
#   - The LLM is never allowed to synthesize or rewrite address tags.

# Coarse → fine ordering (used by event emission / L2 tag assignment)
ADDRESS_TIERS_COARSE_TO_FINE: Tuple[RegionLevel, ...] = (
    RegionLevel.WORLD,
    RegionLevel.NATION,
    RegionLevel.REGION,
    RegionLevel.PROVINCE,
    RegionLevel.DISTRICT,
    RegionLevel.LOCALITY,
)

# Fine → coarse ordering (used by finest-region-at-point lookup)
ADDRESS_TIERS_FINE_TO_COARSE: Tuple[RegionLevel, ...] = tuple(
    reversed(ADDRESS_TIERS_COARSE_TO_FINE)
)

# Address tag prefixes, e.g. ("world:", "nation:", "region:", ...).
# Used by every layer manager to strip address tags before scoring
# content tags, and by every layer summarizer/upgrade path to
# partition address vs content when calling the LLM.
ADDRESS_TAG_PREFIXES: Tuple[str, ...] = tuple(
    f"{lvl.value}:" for lvl in ADDRESS_TIERS_COARSE_TO_FINE
)


def is_address_tag(tag: str) -> bool:
    """True if the tag is an address fact (never LLM-rewritable)."""
    return any(tag.startswith(p) for p in ADDRESS_TAG_PREFIXES)


def strip_address_tags(tags: List[str]) -> List[str]:
    """Return a new list containing only non-address (content) tags."""
    return [t for t in tags if not is_address_tag(t)]


def partition_address_and_content(tags: List[str]) -> Tuple[List[str], List[str]]:
    """Split a tag list into (address_tags, content_tags).

    Preserves the original order within each partition. Used by
    Layer 4+ `_upgrade_narrative` before calling the LLM.
    """
    address: List[str] = []
    content: List[str] = []
    for t in tags:
        (address if is_address_tag(t) else content).append(t)
    return address, content


def propagate_address_facts(
    origin_events: List[Dict[str, Any]],
    retain_tiers: Tuple[RegionLevel, ...],
) -> List[str]:
    """Extract the first address tag at each retained tier from origin events.

    Layer N+1 produces a summary that spans multiple Layer N inputs.
    Those inputs all belong to the same ancestor at every tier above
    the aggregation boundary, so the address is deterministic — we
    just need to read it from any input. This helper does that once
    for a whole set of tiers and returns them in canonical coarse →
    fine order.

    Args:
        origin_events: List of event dicts (each with a "tags" field).
        retain_tiers: Which tiers to copy through. Typical usage for a
            layer that aggregates to game Region:
                (RegionLevel.WORLD, RegionLevel.NATION, RegionLevel.REGION)
            The layer's own aggregation-target tier should be INCLUDED
            here; the caller decides not to read it and to emit its
            own `{tier}:{id}` instead if the target id is known
            independently.

    Returns:
        A list of tags like `["world:world_0", "nation:nation_1",
        "region:region_17"]` in coarsest → finest order. Missing
        tiers are silently omitted.
    """
    wanted_prefixes = tuple(f"{lvl.value}:" for lvl in retain_tiers)
    found: Dict[str, str] = {}
    for event in origin_events:
        for tag in event.get("tags", []):
            for pref in wanted_prefixes:
                if pref not in found and tag.startswith(pref):
                    found[pref] = tag
                    break
        if len(found) == len(wanted_prefixes):
            break
    # Emit in the requested canonical order, skipping any missing
    return [found[pref] for pref in wanted_prefixes if pref in found]


@dataclass
class RegionState:
    """Mutable state of a region — updated by the aggregation pipeline."""
    active_conditions: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    summary_text: str = ""
    last_updated: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_conditions": self.active_conditions,
            "recent_events": self.recent_events,
            "summary_text": self.summary_text,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RegionState:
        return cls(
            active_conditions=data.get("active_conditions", []),
            recent_events=data.get("recent_events", []),
            summary_text=data.get("summary_text", ""),
            last_updated=data.get("last_updated", 0.0),
        )


@dataclass
class Region:
    """A named geographic region at any level of the hierarchy."""
    region_id: str
    name: str
    level: RegionLevel

    # Spatial bounds (tile coordinates, axis-aligned rectangle)
    bounds_x1: int
    bounds_y1: int
    bounds_x2: int
    bounds_y2: int

    # Hierarchy
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)

    # Identity
    biome_primary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Mutable state
    state: RegionState = field(default_factory=RegionState)

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bounds_x1 + self.bounds_x2) / 2.0,
            (self.bounds_y1 + self.bounds_y2) / 2.0,
        )

    @property
    def area(self) -> float:
        return (self.bounds_x2 - self.bounds_x1) * (self.bounds_y2 - self.bounds_y1)

    def contains(self, x: float, y: float) -> bool:
        return (self.bounds_x1 <= x <= self.bounds_x2 and
                self.bounds_y1 <= y <= self.bounds_y2)


class GeographicRegistry:
    """Maps positions to named regions. Singleton.

    Supports loading from a static JSON map, procedural generation from
    biome data, and runtime additions (discovered regions).
    """

    _instance: ClassVar[Optional[GeographicRegistry]] = None

    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.world: Optional[Region] = None

        # Caches
        self._chunk_to_locality: Dict[Tuple[int, int], Optional[str]] = {}
        self._locality_chain: Dict[str, Dict[str, str]] = {}

    # Backwards-compat alias — some older code still reads `self.realm`.
    # `realm` is no longer a hierarchy tier; the attribute points at the
    # top-level WORLD region. Prefer `self.world` in new code.
    @property
    def realm(self) -> Optional[Region]:
        return self.world

    @realm.setter
    def realm(self, value: Optional[Region]) -> None:
        self.world = value

    @classmethod
    def get_instance(cls) -> GeographicRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── Loading ──────────────────────────────────────────────────────

    def load_base_map(self, filepath: str) -> None:
        """Load region definitions from a JSON map file.

        Supports both the new 6-tier layout (`world`, `nations`,
        `regions`, `provinces`, `districts`, `localities`) and the
        legacy 4-tier layout (`realm`, `provinces`, `districts`,
        `localities`) for backwards compatibility with old fixture
        files. Legacy files load as-declared and do not get
        auto-promoted — they're assumed to already reference the
        correct RegionLevel values.
        """
        if not os.path.exists(filepath):
            print(f"[GeoRegistry] Map file not found: {filepath} — starting empty")
            return

        with open(filepath, "r") as f:
            data = json.load(f)

        # Load top-level region — accept both "world" (new) and "realm"
        # (legacy). Either one is parsed and stored under its declared
        # region_id. The RegionLevel is whatever the file says.
        top_key = "world" if "world" in data else ("realm" if "realm" in data else None)
        if top_key:
            r = data[top_key]
            top = self._parse_region(r)
            self.regions[top.region_id] = top
            self.world = top

        # Load all tiers. Order matters for parent wiring, so walk from
        # coarser to finer.
        for level_key in ("nations", "regions", "provinces", "districts", "localities"):
            for r in data.get(level_key, []):
                region = self._parse_region(r)
                self.regions[region.region_id] = region
                # Wire parent → child
                if region.parent_id and region.parent_id in self.regions:
                    parent = self.regions[region.parent_id]
                    if region.region_id not in parent.child_ids:
                        parent.child_ids.append(region.region_id)

        self._invalidate_cache()
        print(f"[GeoRegistry] Loaded {len(self.regions)} regions from {filepath}")

    def _parse_region(self, data: Dict[str, Any]) -> Region:
        bounds = data.get("bounds", [0, 0, 0, 0])
        return Region(
            region_id=data["region_id"],
            name=data["name"],
            level=RegionLevel(data["level"]),
            bounds_x1=bounds[0],
            bounds_y1=bounds[1],
            bounds_x2=bounds[2],
            bounds_y2=bounds[3],
            parent_id=data.get("parent_id"),
            child_ids=data.get("child_ids", []),
            biome_primary=data.get("biome_primary", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )

    def load_from_world_map(self, world_map) -> None:
        """Load region hierarchy from the game's WorldMap.

        Maps the game's 6-tier hierarchy 1:1 to WMS RegionLevels. The
        game's own terminology is preserved — no tier shifting.

            Game World    → WMS WORLD     (Layer 7 scope, future)
            Game Nation   → WMS NATION    (Layer 6 scope, future)
            Game Region   → WMS REGION    (Layer 5 scope)
            Game Province → WMS PROVINCE  (Layer 4 scope)
            Game District → WMS DISTRICT  (Layer 3 scope)
            Game Locality → WMS LOCALITY  (Layer 2 capture, sparse POI)

        Locality is optional — only present if the game generated a
        POI (e.g. a village) on that chunk. Non-locality chunks still
        get the full District/Province/Region/Nation/World address.

        Args:
            world_map: WorldMap from systems.geography.models
        """
        self.regions.clear()
        self._invalidate_cache()
        chunk_size = 16

        # Create the top-level World region
        half = world_map.world_size // 2
        world_bounds = [-half * chunk_size, -half * chunk_size,
                        half * chunk_size, half * chunk_size]
        world = Region(
            region_id="world_0",
            name="The Known Lands",
            level=RegionLevel.WORLD,
            bounds_x1=world_bounds[0], bounds_y1=world_bounds[1],
            bounds_x2=world_bounds[2], bounds_y2=world_bounds[3],
        )
        self.regions["world_0"] = world
        self.world = world

        # Register game Nations as WMS NATION
        for nid, nation in world_map.nations.items():
            nation_id = f"nation_{nid}"
            child_ids = []
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            for rid in nation.region_ids:
                region = world_map.regions.get(rid)
                if region:
                    bx1, by1, bx2, by2 = region.bounds
                    min_x = min(min_x, bx1 * chunk_size)
                    min_y = min(min_y, by1 * chunk_size)
                    max_x = max(max_x, bx2 * chunk_size)
                    max_y = max(max_y, by2 * chunk_size)
                    child_ids.append(f"region_{rid}")

            self.regions[nation_id] = Region(
                region_id=nation_id,
                name=nation.name,
                level=RegionLevel.NATION,
                bounds_x1=int(min_x) if min_x != float('inf') else 0,
                bounds_y1=int(min_y) if min_y != float('inf') else 0,
                bounds_x2=int(max_x) if max_x != float('-inf') else 0,
                bounds_y2=int(max_y) if max_y != float('-inf') else 0,
                parent_id="world_0",
                child_ids=child_ids,
                tags=[f"nation:{nation.name.lower()}", f"flavor:{nation.naming_flavor.value}"],
            )
            world.child_ids.append(nation_id)

        # Register game Regions as WMS REGION (Layer 5 scope)
        for rid, region in world_map.regions.items():
            region_id = f"region_{rid}"
            bx1, by1, bx2, by2 = region.bounds
            nation = world_map.nations.get(region.nation_id)
            parent_id = f"nation_{region.nation_id}"

            # Children are game Provinces
            child_ids = [f"province_{pid}" for pid in region.province_ids]

            self.regions[region_id] = Region(
                region_id=region_id,
                name=region.name,
                level=RegionLevel.REGION,
                bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                parent_id=parent_id,
                child_ids=child_ids,
                biome_primary=region.identity.value,
                tags=[f"identity:{region.identity.value}",
                      f"nation:{nation.name.lower()}" if nation else ""],
            )

        # Register game Provinces as WMS PROVINCE (Layer 4 scope)
        for pid, province in world_map.provinces.items():
            province_id = f"province_{pid}"
            bx1, by1, bx2, by2 = province.bounds
            parent_id = f"region_{province.region_id}"

            # Children are game Districts
            child_ids = []
            if hasattr(province, 'district_ids'):
                child_ids = [f"district_{did}" for did in province.district_ids]

            self.regions[province_id] = Region(
                region_id=province_id,
                name=province.name,
                level=RegionLevel.PROVINCE,
                bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                parent_id=parent_id,
                child_ids=child_ids,
            )

        # Register game Districts as WMS DISTRICT (Layer 3 scope)
        if hasattr(world_map, 'districts') and world_map.districts:
            for did, district in world_map.districts.items():
                district_id = f"district_{did}"
                bx1, by1, bx2, by2 = district.bounds
                parent_id = f"province_{district.province_id}"

                self.regions[district_id] = Region(
                    region_id=district_id,
                    name=district.name,
                    level=RegionLevel.DISTRICT,
                    bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                    bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                    parent_id=parent_id,
                )

        # Register game Localities as WMS LOCALITY (sparse POIs)
        # Locality parent is determined by looking at a chunk the
        # locality occupies and reading its stamped district_id. This
        # gives a deterministic district parent; no heuristics.
        nl_registered = 0
        if hasattr(world_map, 'localities') and world_map.localities:
            for lid, locality in world_map.localities.items():
                parent_district_id: Optional[str] = None
                parent_region: Optional[Region] = None

                # Find the containing district from any occupied chunk.
                # locality.adjacent_chunks may be empty for legacy data,
                # so fall back to (chunk_x, chunk_y).
                candidate_chunks = list(locality.adjacent_chunks or [])
                if not candidate_chunks:
                    candidate_chunks = [(locality.chunk_x, locality.chunk_y)]

                for (cx, cy) in candidate_chunks:
                    gd = world_map.chunk_data.get((cx, cy))
                    if gd and gd.district_id >= 0:
                        parent_district_id = f"district_{gd.district_id}"
                        parent_region = self.regions.get(parent_district_id)
                        if parent_region is not None:
                            break

                if parent_region is None:
                    # Can't parent this locality — skip rather than
                    # registering an orphaned tier. Log once.
                    continue

                # Bounds: enclosing rectangle over all adjacent chunks
                if candidate_chunks:
                    xs = [c[0] for c in candidate_chunks]
                    ys = [c[1] for c in candidate_chunks]
                    min_cx, max_cx = min(xs), max(xs)
                    min_cy, max_cy = min(ys), max(ys)
                    bx1 = min_cx * chunk_size
                    by1 = min_cy * chunk_size
                    bx2 = (max_cx + 1) * chunk_size - 1
                    by2 = (max_cy + 1) * chunk_size - 1
                else:
                    bx1 = locality.chunk_x * chunk_size
                    by1 = locality.chunk_y * chunk_size
                    bx2 = bx1 + chunk_size - 1
                    by2 = by1 + chunk_size - 1

                wms_loc_id = f"locality_{lid}"
                self.regions[wms_loc_id] = Region(
                    region_id=wms_loc_id,
                    name=locality.name,
                    level=RegionLevel.LOCALITY,
                    bounds_x1=bx1, bounds_y1=by1,
                    bounds_x2=bx2, bounds_y2=by2,
                    parent_id=parent_district_id,
                    tags=[f"feature:{locality.feature_type}"] if locality.feature_type else [],
                )
                if wms_loc_id not in parent_region.child_ids:
                    parent_region.child_ids.append(wms_loc_id)
                nl_registered += 1

        self._invalidate_cache()
        nn = len(world_map.nations)
        nr = len(world_map.regions)
        np_ = len(world_map.provinces)
        nd = len(world_map.districts) if hasattr(world_map, 'districts') else 0
        print(f"[GeoRegistry] Loaded from WorldMap: "
              f"1 world, {nn} nations, {nr} regions, "
              f"{np_} provinces, {nd} districts, "
              f"{nl_registered} localities")

    def generate_from_biomes(self, chunk_biomes: Dict[Tuple[int, int], str],
                             chunk_size: int = 16) -> None:
        """Generate a basic region hierarchy from chunk biome data.

        Fallback used when no WorldMap is available. Produces a
        minimal 3-tier hierarchy (WORLD → PROVINCE quadrants →
        LOCALITY chunks) that skips Nation/Region/District. Real
        gameplay always goes through `load_from_world_map`.
        """
        if not chunk_biomes:
            return

        # Find world bounds from chunk coordinates
        all_cx = [c[0] for c in chunk_biomes]
        all_cy = [c[1] for c in chunk_biomes]
        min_cx, max_cx = min(all_cx), max(all_cx)
        min_cy, max_cy = min(all_cy), max(all_cy)

        # Create top-level World covering the whole known area
        world = Region(
            region_id="known_lands",
            name="The Known Lands",
            level=RegionLevel.WORLD,
            bounds_x1=min_cx * chunk_size,
            bounds_y1=min_cy * chunk_size,
            bounds_x2=(max_cx + 1) * chunk_size - 1,
            bounds_y2=(max_cy + 1) * chunk_size - 1,
            description="The explored world.",
        )
        self.regions[world.region_id] = world
        self.world = world

        # Group chunks into quadrant-based provinces
        mid_x = (min_cx + max_cx) // 2
        mid_y = (min_cy + max_cy) // 2
        quadrants = {
            "nw": (min_cx, min_cy, mid_x, mid_y, "Northwestern Reaches"),
            "ne": (mid_x + 1, min_cy, max_cx, mid_y, "Northeastern Highlands"),
            "sw": (min_cx, mid_y + 1, mid_x, max_cy, "Southwestern Lowlands"),
            "se": (mid_x + 1, mid_y + 1, max_cx, max_cy, "Southeastern Frontier"),
        }

        for qid, (cx1, cy1, cx2, cy2, name) in quadrants.items():
            prov_id = f"province_{qid}"
            province = Region(
                region_id=prov_id,
                name=name,
                level=RegionLevel.PROVINCE,
                bounds_x1=cx1 * chunk_size,
                bounds_y1=cy1 * chunk_size,
                bounds_x2=(cx2 + 1) * chunk_size - 1,
                bounds_y2=(cy2 + 1) * chunk_size - 1,
                parent_id=world.region_id,
            )
            self.regions[prov_id] = province
            world.child_ids.append(prov_id)

            # Create localities from individual chunks in this quadrant
            for (cx, cy), biome in chunk_biomes.items():
                if cx1 <= cx <= cx2 and cy1 <= cy <= cy2:
                    loc_id = f"loc_{cx}_{cy}"
                    biome_base = biome.replace("peaceful_", "").replace("dangerous_", "").replace("rare_", "").replace("hidden_", "").replace("ancient_", "").replace("deep_", "")
                    loc = Region(
                        region_id=loc_id,
                        name=f"{biome_base.replace('_', ' ').title()} ({cx},{cy})",
                        level=RegionLevel.LOCALITY,
                        bounds_x1=cx * chunk_size,
                        bounds_y1=cy * chunk_size,
                        bounds_x2=(cx + 1) * chunk_size - 1,
                        bounds_y2=(cy + 1) * chunk_size - 1,
                        parent_id=prov_id,
                        biome_primary=biome,
                        tags=[f"biome:{biome_base}", f"terrain:{biome_base}"],
                    )
                    self.regions[loc_id] = loc
                    province.child_ids.append(loc_id)

        self._invalidate_cache()
        print(f"[GeoRegistry] Generated {len(self.regions)} regions from biome data")

    # ── Lookup ───────────────────────────────────────────────────────

    # Tier precedence from finest → coarsest. `get_region_at` returns the
    # first (finest) containing region. Locality is finest; it's optional
    # per chunk so the lookup may fall through to district.
    _TIER_SEARCH_ORDER: ClassVar[Tuple[RegionLevel, ...]] = (
        RegionLevel.LOCALITY,
        RegionLevel.DISTRICT,
        RegionLevel.PROVINCE,
        RegionLevel.REGION,
        RegionLevel.NATION,
        RegionLevel.WORLD,
    )

    def get_region_at(self, x: float, y: float) -> Optional[Region]:
        """Get the finest-tier containing region for a position.

        Returns a LOCALITY region if one covers (x, y); otherwise
        falls back to DISTRICT, then PROVINCE, and so on. Result is
        cached per chunk.
        """
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        cache_key = (chunk_x, chunk_y)

        if cache_key in self._chunk_to_locality:
            loc_id = self._chunk_to_locality[cache_key]
            return self.regions.get(loc_id) if loc_id else None

        # Walk finest → coarsest, return the first match
        for level in self._TIER_SEARCH_ORDER:
            for region in self.regions.values():
                if region.level == level and region.contains(x, y):
                    self._chunk_to_locality[cache_key] = region.region_id
                    return region

        self._chunk_to_locality[cache_key] = None
        return None

    def get_full_address(self, x: float, y: float) -> Dict[str, str]:
        """Get the full address hierarchy for a position.

        Returns a dict keyed by RegionLevel.value (lower-case tier
        name) containing every tier from the finest containing region
        up to the World root.

        Possible keys: ``locality`` (optional — only if the point is
        inside a registered Locality POI), ``district``, ``province``,
        ``region``, ``nation``, ``world``. Chunks that exist outside
        any Locality POI still get the other five tiers (assuming the
        registry is fully loaded).

        Returns an empty dict if the point is outside every registered
        region (e.g. before `load_from_world_map` has been called).
        """
        start = self.get_region_at(x, y)
        if not start:
            return {}

        # Check chain cache keyed by the finest tier's region_id
        if start.region_id in self._locality_chain:
            return dict(self._locality_chain[start.region_id])

        result: Dict[str, str] = {start.level.value: start.region_id}
        current = start
        while current.parent_id:
            parent = self.regions.get(current.parent_id)
            if not parent:
                break
            result[parent.level.value] = parent.region_id
            current = parent

        self._locality_chain[start.region_id] = result
        return dict(result)

    def get_regions_by_level(self, level: RegionLevel) -> List[Region]:
        return [r for r in self.regions.values() if r.level == level]

    def get_regions_by_tag(self, tag: str) -> List[Region]:
        return [r for r in self.regions.values() if tag in r.tags]

    def get_nearby_regions(self, x: float, y: float, radius: float,
                           level: RegionLevel = RegionLevel.LOCALITY) -> List[Region]:
        results = []
        for region in self.regions.values():
            if region.level != level:
                continue
            cx, cy = region.center
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist <= radius:
                results.append(region)
        return results

    def get_children(self, region_id: str) -> List[Region]:
        region = self.regions.get(region_id)
        if not region:
            return []
        return [self.regions[cid] for cid in region.child_ids
                if cid in self.regions]

    # ── Mutation ─────────────────────────────────────────────────────

    def register_region(self, region: Region) -> None:
        """Add a new region at runtime."""
        self.regions[region.region_id] = region
        if region.parent_id and region.parent_id in self.regions:
            parent = self.regions[region.parent_id]
            if region.region_id not in parent.child_ids:
                parent.child_ids.append(region.region_id)
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        self._chunk_to_locality.clear()
        self._locality_chain.clear()

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all region states (not definitions — those come from JSON)."""
        return {
            region_id: region.state.to_dict()
            for region_id, region in self.regions.items()
        }

    def restore_states(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Restore region states from save data."""
        for region_id, state_data in data.items():
            if region_id in self.regions:
                self.regions[region_id].state = RegionState.from_dict(state_data)
