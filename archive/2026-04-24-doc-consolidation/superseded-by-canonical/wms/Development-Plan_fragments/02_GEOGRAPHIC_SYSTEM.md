# Part 2: Geographic System

## Purpose

The game world is a grid of 16x16 tile chunks with biome assignments. The Geographic System superimposes a **named address hierarchy** onto this grid — giving every position a human-readable location identity that the memory system and NPC agents can reference.

This is like overlaying a political/cultural map onto a topographic one. The chunks and biomes are the terrain. The geographic regions are the "countries, states, counties, cities" that give places names, narrative identity, and administrative grouping.

## Hierarchy

```
Realm (entire world)
  └── Province (~25x50 or ~50x25 tiles, 2-4 per realm)
        └── District (~12x12 to ~25x25 tiles, 2-6 per province)
              └── Locality (~8x8 to ~16x16 tiles, roughly chunk-sized, 2-4 per district)
```

**Tile count for a 100x100 world:**
- 1 Realm
- ~4 Provinces (each covering roughly a quadrant, irregularly shaped)
- ~12-20 Districts (named areas like "Iron Hills", "Whispering Woods")
- ~40-80 Localities (named spots like "Blacksmith's Crossing", "Old Mine")

These numbers are approximate. The system supports any number at any level.

## Region Definition

```python
class RegionLevel(Enum):
    LOCALITY = "locality"
    DISTRICT = "district"
    PROVINCE = "province"
    REALM = "realm"

@dataclass
class Region:
    region_id: str                    # Unique identifier: "iron_hills", "eastern_highlands"
    name: str                         # Display name: "Iron Hills", "Eastern Highlands"
    level: RegionLevel                # Which tier in the hierarchy

    # Spatial bounds (tile coordinates, axis-aligned rectangle)
    bounds_x1: int                    # Left edge (inclusive)
    bounds_y1: int                    # Top edge (inclusive)
    bounds_x2: int                    # Right edge (inclusive)
    bounds_y2: int                    # Bottom edge (inclusive)

    # Hierarchy
    parent_id: Optional[str]          # Parent region (None for realm)
    child_ids: List[str]              # Direct children

    # Identity (static, defined at creation)
    biome_primary: str                # Dominant biome type
    description: str                  # Narrative description for LLM context
    tags: List[str]                   # Geographic identity tags (see below)

    # Mutable state (updated by event propagation)
    state: RegionState                # Current conditions (see below)
```

### Region State

```python
@dataclass
class RegionState:
    """Mutable state of a region — updated by event propagation pipeline"""

    # Layer 3 interpreted events affecting this region
    active_conditions: List[str]      # IDs of ongoing Layer 3 events
    recent_events: List[str]          # IDs of recent Layer 3 events (bounded)

    # Narrative summary (regenerated when conditions change)
    summary_text: str                 # "The Iron Hills are under resource pressure..."
    last_updated: float               # Game time of last state change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_conditions": self.active_conditions,
            "recent_events": self.recent_events,
            "summary_text": self.summary_text,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionState':
        return cls(
            active_conditions=data.get("active_conditions", []),
            recent_events=data.get("recent_events", []),
            summary_text=data.get("summary_text", ""),
            last_updated=data.get("last_updated", 0.0)
        )
```

## Geographic Tags on Regions

Regions carry tags that describe their identity — same tag system used for entities. These tags enable the Propagator to route events to affected regions by tag matching.

```python
# Example region tags:
"iron_hills" → [
    "terrain:hills", "terrain:rocky",
    "resource:iron", "resource:stone", "resource:copper",
    "biome:quarry", "biome:cave",
    "danger:moderate",
    "feature:mines", "feature:ore_veins",
    "climate:temperate"
]

"whispering_woods" → [
    "terrain:forest", "terrain:dense",
    "resource:wood", "resource:herbs", "resource:wildlife",
    "biome:forest",
    "danger:low",
    "feature:ancient_trees", "feature:clearings",
    "climate:temperate", "atmosphere:mysterious"
]

"northern_pines" → [
    "terrain:forest", "terrain:mountainous",
    "resource:wood", "resource:wildlife",
    "biome:forest",
    "danger:moderate",
    "feature:pine_forest", "feature:mountain_pass",
    "climate:cold"
]
```

When a "forest fire" interpreted event is created with `affects_tags: ["terrain:forest", "resource:wood"]`, the Propagator finds all regions whose tags overlap and updates their state.

## Position-to-Region Lookup

### At Runtime

Given a position `(x, y)`, determine which locality → district → province → realm it belongs to:

```python
class GeographicRegistry:
    """Maps positions to named regions. Singleton."""
    _instance = None

    def __init__(self):
        self.regions: Dict[str, Region] = {}       # region_id → Region
        self.realm: Optional[Region] = None         # The top-level realm

        # Spatial index: chunk → locality mapping (cached)
        self._chunk_to_locality: Dict[Tuple[int, int], str] = {}
        # Locality → district → province chain (cached)
        self._locality_chain: Dict[str, List[str]] = {}

    def get_region_at(self, x: float, y: float) -> Optional[Region]:
        """Get the most specific (locality-level) region for a position"""
        # First check chunk cache
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        cache_key = (chunk_x, chunk_y)

        if cache_key in self._chunk_to_locality:
            return self.regions[self._chunk_to_locality[cache_key]]

        # Scan localities for containment (only needed once per chunk)
        for region in self.regions.values():
            if region.level == RegionLevel.LOCALITY:
                if (region.bounds_x1 <= x <= region.bounds_x2 and
                    region.bounds_y1 <= y <= region.bounds_y2):
                    self._chunk_to_locality[cache_key] = region.region_id
                    return region

        return None  # Position outside all defined localities

    def get_full_address(self, x: float, y: float) -> Dict[str, str]:
        """Get full address hierarchy for a position"""
        locality = self.get_region_at(x, y)
        if not locality:
            return {}

        result = {"locality": locality.region_id}
        current = locality
        while current.parent_id:
            parent = self.regions[current.parent_id]
            result[parent.level.value] = parent.region_id
            current = parent
        return result

    def get_regions_by_tag(self, tag: str) -> List[Region]:
        """Find all regions with a specific tag"""
        return [r for r in self.regions.values() if tag in r.tags]

    def get_nearby_regions(self, x: float, y: float, radius: float,
                           level: RegionLevel = RegionLevel.LOCALITY) -> List[Region]:
        """Find all regions of a given level within radius of a point"""
        results = []
        for region in self.regions.values():
            if region.level != level:
                continue
            # Check center-to-point distance
            cx = (region.bounds_x1 + region.bounds_x2) / 2
            cy = (region.bounds_y1 + region.bounds_y2) / 2
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist <= radius:
                results.append(region)
        return results
```

### Chunk-to-Region Mapping

Computed once per chunk load, cached. Since chunks are 16x16 and localities are roughly chunk-sized, most chunks map to exactly one locality. If a chunk straddles a boundary, the center tile's locality wins.

```python
# On chunk load (in WorldSystem):
address = geographic_registry.get_full_address(chunk_center_x, chunk_center_y)
chunk.locality_id = address.get("locality")
chunk.district_id = address.get("district")
chunk.province_id = address.get("province")
```

Every Layer 2 event recorded in this chunk automatically gets these region IDs stamped — zero per-event lookup cost.

## Map Definition — Static or Procedural

### Option A: Static Map (Configuration JSON)

A hand-authored JSON file defining all regions. Best for curated world design.

```json
{
  "realm": {
    "region_id": "known_lands",
    "name": "The Known Lands",
    "level": "realm",
    "bounds": [0, 0, 99, 99],
    "description": "A frontier land of forests, hills, and ancient ruins."
  },
  "provinces": [
    {
      "region_id": "eastern_highlands",
      "name": "Eastern Highlands",
      "level": "province",
      "bounds": [50, 0, 99, 49],
      "parent_id": "known_lands",
      "biome_primary": "quarry",
      "description": "Rocky highlands rich with mineral deposits.",
      "tags": ["terrain:hills", "terrain:rocky", "resource:iron", "resource:stone", "climate:temperate"]
    }
  ],
  "districts": [
    {
      "region_id": "iron_hills",
      "name": "Iron Hills",
      "level": "district",
      "bounds": [60, 10, 80, 30],
      "parent_id": "eastern_highlands",
      "biome_primary": "quarry",
      "description": "The heart of the highlands mining region.",
      "tags": ["terrain:hills", "resource:iron", "resource:copper", "feature:mines", "danger:moderate"]
    }
  ],
  "localities": [
    {
      "region_id": "old_mine_shaft",
      "name": "Old Mine Shaft",
      "level": "locality",
      "bounds": [65, 15, 75, 25],
      "parent_id": "iron_hills",
      "biome_primary": "cave",
      "description": "An abandoned mine with deep iron veins. Dangerous creatures lurk below.",
      "tags": ["terrain:cave", "resource:iron", "feature:abandoned_mine", "danger:high", "atmosphere:dark"]
    }
  ]
}
```

### Option B: Procedural Generation at World Creation

Generate region names and boundaries from the existing biome generator output. Uses the chunk biome assignments to cluster chunks into named regions.

```python
class ProceduralGeographer:
    """Generates named regions from biome data at world creation"""

    def generate_map(self, biome_generator: BiomeGenerator,
                     world_seed: int) -> Dict[str, Region]:
        """
        1. Get biome type for all chunks in the play area
        2. Cluster adjacent chunks of similar biome into localities
        3. Group localities into districts based on biome category
        4. Group districts into provinces based on quadrant
        5. Assign names from a name pool seeded by world_seed
        6. Generate tags from biome data
        """
        ...
```

### Option C: Hybrid (Recommended)

Start with procedural generation for the basic structure, then allow hand-authored overrides and additions. New regions can be added via:
- Developer injection (new JSON entries)
- Narrative threads (a "discovered" region gets named and registered)
- World expansion (new areas beyond current bounds)

```python
class GeographicRegistry:
    def load_base_map(self, filepath: str):
        """Load static map definition"""
        ...

    def generate_unnamed_regions(self, biome_generator: BiomeGenerator):
        """Fill gaps with procedurally named regions"""
        ...

    def register_region(self, region: Region):
        """Add a new region at runtime (expansion, discovery)"""
        self.regions[region.region_id] = region
        self._invalidate_cache()
```

## Scalability Considerations

**World expansion**: Adding new territory means defining new regions with new bounds. Existing regions don't change. The realm boundary is conceptual — there's no array indexed 0-100 to resize.

**Region overlap**: Regions at the same level should NOT overlap. The hierarchy enforces containment: every locality is inside exactly one district, etc. If needed, a "border zone" locality can be created.

**Performance**: With ~80 localities, the scan in `get_region_at()` is trivial. For larger worlds (1000+ localities), switch to an R-tree spatial index or a grid-based lookup table.

**Chunk alignment**: Localities don't need to align exactly to chunk boundaries. The chunk-center mapping handles edge cases. But aligning roughly to chunk boundaries simplifies everything.
