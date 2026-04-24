# Part 3: Entity Registry & Interest Tags

## Purpose

Every queryable thing in the world gets an entry in the Entity Registry. This is the **starting point** for all queries — you never search events directly. You find the entity first, then radiate outward through its location, interests, and awareness.

The interest tag system is the **crux** of this architecture. Tags are not a filter — they ARE the entity's identity to the information system. They define what events are relevant, what an NPC would notice, what a region is known for.

## Entity Definition

```python
class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"
    ENEMY_TYPE = "enemy_type"         # Not individual enemies — enemy *species*
    RESOURCE_TYPE = "resource_type"    # Not individual nodes — resource *kind*
    LOCATION = "location"             # Named regions from the geographic system
    STATION = "station"               # Crafting stations
    FACTION = "faction"               # Groups of NPCs/entities

@dataclass
class WorldEntity:
    entity_id: str                    # Unique: "npc_blacksmith_gareth", "enemy_type_wolf"
    entity_type: EntityType
    name: str                         # Display: "Gareth the Blacksmith", "Gray Wolf"

    # Position (None for abstract entities like resource types or factions)
    position_x: Optional[float]
    position_y: Optional[float]

    # Geographic anchoring
    home_region_id: Optional[str]     # Primary region this entity belongs to
    home_district_id: Optional[str]   # Cached parent for faster queries
    home_province_id: Optional[str]   # Cached parent for faster queries

    # HOW FAR THIS ENTITY'S AWARENESS EXTENDS (in tiles)
    awareness_radius: float           # NPC: ~32-48, Region: its own bounds, Player: global

    # THE IDENTITY — Interest Tags
    tags: List[str]                   # See comprehensive tag system below

    # Activity log — bounded circular buffer of Layer 2 event IDs
    activity_log: List[str]           # Most recent N event_ids directly involving this entity
    activity_log_max: int = 100       # How many to keep in the buffer

    # Entity-specific metadata (varies by type)
    metadata: Dict[str, Any]          # Static properties specific to entity type
```

## The Interest Tag System — Entity Identity

### Philosophy

Tags are **overapplied by design**. An NPC blacksmith isn't just tagged `["job:blacksmith"]`. They're tagged with everything that defines what they'd notice, care about, or know about. This is their fingerprint in the information system.

### Tag Categories

Every tag follows the format `category:value`. Categories are:

```
SPECIES/TYPE
  species:human, species:dwarf, species:elf
  type:npc, type:hostile, type:passive, type:resource

LOCATION (where they live/belong)
  location:iron_hills, location:eastern_highlands
  origin:northern_reaches
  territory:whispering_woods

AFFILIATION (groups, factions, allegiances)
  faction:miners_guild, faction:forest_wardens
  allegiance:crown, allegiance:independent
  guild:smithing, guild:alchemy

JOB/ROLE (what they do)
  job:blacksmith, job:merchant, job:guard, job:hunter
  role:quest_giver, role:trainer, role:shopkeeper

DOMAIN (knowledge/expertise areas)
  domain:smithing, domain:metalwork, domain:weapons, domain:armor
  domain:alchemy, domain:herbs, domain:potions
  domain:combat, domain:hunting, domain:tracking
  domain:mining, domain:forestry, domain:fishing

RESOURCE INTEREST (what materials matter to them)
  resource:iron, resource:steel, resource:mithril
  resource:wood, resource:herbs, resource:leather
  resource:stone, resource:gems

TENDENCY (behavioral patterns)
  tendency:cautious, tendency:aggressive, tendency:curious
  tendency:generous, tendency:greedy, tendency:honest
  tendency:gossip, tendency:secretive

HOBBY/PREFERENCE (what they enjoy/value)
  preference:quality_over_quantity
  preference:rare_materials, preference:common_goods
  hobby:storytelling, hobby:collecting, hobby:exploring

CONCERN (what worries/motivates them)
  concern:safety, concern:profit, concern:reputation
  concern:scarcity, concern:wildlife, concern:weather

BIOME (what environments they relate to)
  biome:forest, biome:cave, biome:quarry, biome:water

COMBAT (for enemy types and combat-aware NPCs)
  combat:melee, combat:ranged, combat:magic
  tier:1, tier:2, tier:3, tier:4
  element:fire, element:ice, element:lightning

EVENT INTEREST (what kinds of events catch their attention)
  event:trade, event:combat, event:crafting, event:gathering
  event:death, event:discovery, event:quest
```

### Example Entity Tag Sets

**NPC: Gareth the Blacksmith**
```python
tags = [
    # What he is
    "species:human", "type:npc",
    # Where he is
    "location:blacksmiths_crossing", "location:iron_hills",
    # What he does
    "job:blacksmith", "role:shopkeeper", "role:quest_giver",
    "guild:smithing",
    # What he knows about
    "domain:smithing", "domain:metalwork", "domain:weapons",
    "domain:armor", "domain:repair",
    # What resources matter to him
    "resource:iron", "resource:steel", "resource:mithril",
    "resource:coal", "resource:leather",
    # His personality
    "tendency:honest", "tendency:perfectionist",
    "preference:quality_over_quantity",
    "preference:rare_materials",
    # What concerns him
    "concern:scarcity", "concern:reputation",
    # What events he notices
    "event:trade", "event:crafting",
    # Biome awareness
    "biome:quarry", "biome:cave"
]
```

**NPC: Elara the Herbalist**
```python
tags = [
    "species:elf", "type:npc",
    "location:whispering_woods", "location:riverside_camp",
    "job:herbalist", "role:shopkeeper", "role:quest_giver",
    "guild:alchemy",
    "domain:alchemy", "domain:herbs", "domain:potions",
    "domain:nature", "domain:healing",
    "resource:herbs", "resource:mushrooms", "resource:flowers",
    "resource:water",
    "tendency:cautious", "tendency:curious",
    "preference:natural_remedies", "preference:rare_herbs",
    "concern:wildlife", "concern:deforestation",
    "concern:pollution",
    "event:gathering", "event:discovery",
    "biome:forest", "biome:water",
    "hobby:exploring", "hobby:collecting"
]
```

**Enemy Type: Gray Wolf**
```python
tags = [
    "species:wolf", "type:hostile",
    "tier:1",
    "biome:forest", "biome:plains",
    "combat:melee",
    "resource:wolf_pelt", "resource:wolf_fang",
    "behavior:pack", "behavior:territorial",
    "concern:territory", "concern:prey"
]
```

**Region: Iron Hills (as an entity)**
```python
tags = [
    "type:location", "level:district",
    "terrain:hills", "terrain:rocky",
    "biome:quarry", "biome:cave",
    "resource:iron", "resource:copper", "resource:stone",
    "resource:coal", "resource:gems",
    "feature:mines", "feature:ore_veins",
    "danger:moderate",
    "climate:temperate",
    "industry:mining", "industry:smithing"
]
```

**Player (singleton)**
```python
tags = [
    "type:player",
    # Dynamic tags added/updated based on behavior (from PlayerProfile):
    "playstyle:combat_focused",  # or crafting_focused, explorer, etc.
    "preference:melee",          # or ranged, magic
    "level:tier_2",              # derived from current level
    # Dynamic tags from achievements:
    "title:journeyman_smith",
    "class:warrior",
    # Dynamic tags from recent activity:
    "active_in:iron_hills",
    "hunting:wolves"
]
```

### Tag Matching — How Interest Filtering Works

When assembling "what does this entity know about?", the system matches event tags against entity interest tags:

```python
def calculate_relevance(entity_tags: List[str], event_tags: List[str]) -> float:
    """
    Score how relevant an event is to an entity based on tag overlap.
    Returns 0.0 (irrelevant) to 1.0 (directly relevant).
    """
    if not entity_tags or not event_tags:
        return 0.0

    # Extract categories from tags
    entity_categories = {}
    for tag in entity_tags:
        cat, val = tag.split(":", 1) if ":" in tag else (tag, tag)
        entity_categories.setdefault(cat, set()).add(val)

    event_categories = {}
    for tag in event_tags:
        cat, val = tag.split(":", 1) if ":" in tag else (tag, tag)
        event_categories.setdefault(cat, set()).add(val)

    # Score: what fraction of the event's tag categories does the entity care about?
    matches = 0
    total = len(event_categories)
    for cat, vals in event_categories.items():
        if cat in entity_categories:
            # Category match — check value overlap
            if entity_categories[cat] & vals:
                matches += 1
            else:
                matches += 0.3  # Same category, different value = partial match

    return min(1.0, matches / max(total, 1))
```

### Entity Registration

The registry loads entities from multiple sources at startup:

```python
class EntityRegistry:
    """Central registry of all queryable entities. Singleton."""
    _instance = None

    def __init__(self):
        self.entities: Dict[str, WorldEntity] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag → [entity_ids]

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, entity: WorldEntity):
        """Add or update an entity"""
        self.entities[entity.entity_id] = entity
        # Update tag index
        for tag in entity.tags:
            self._tag_index.setdefault(tag, []).append(entity.entity_id)

    def get(self, entity_id: str) -> Optional[WorldEntity]:
        return self.entities.get(entity_id)

    def find_by_tag(self, tag: str) -> List[WorldEntity]:
        """Find all entities with a specific tag"""
        ids = self._tag_index.get(tag, [])
        return [self.entities[eid] for eid in ids if eid in self.entities]

    def find_by_tags(self, tags: List[str], match_mode: str = "any") -> List[WorldEntity]:
        """
        Find entities matching tags.
        match_mode: "any" (at least one tag matches) or "all" (every tag matches)
        """
        if match_mode == "any":
            result_ids = set()
            for tag in tags:
                result_ids.update(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids if eid in self.entities]
        else:  # "all"
            if not tags:
                return []
            result_ids = set(self._tag_index.get(tags[0], []))
            for tag in tags[1:]:
                result_ids &= set(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids if eid in self.entities]

    def find_near(self, x: float, y: float, radius: float,
                  entity_type: Optional[EntityType] = None) -> List[WorldEntity]:
        """Find entities within radius of a position"""
        results = []
        for entity in self.entities.values():
            if entity.position_x is None:
                continue
            if entity_type and entity.entity_type != entity_type:
                continue
            dist = math.sqrt((x - entity.position_x) ** 2 + (y - entity.position_y) ** 2)
            if dist <= radius:
                results.append(entity)
        return results

    def load_from_npcs(self, npc_db: 'NPCDatabase'):
        """Register all NPCs from the existing NPC database"""
        for npc_id, npc_def in npc_db.npcs.items():
            entity = WorldEntity(
                entity_id=f"npc_{npc_id}",
                entity_type=EntityType.NPC,
                name=npc_def.name,
                position_x=npc_def.position.x,
                position_y=npc_def.position.y,
                home_region_id=None,  # Filled by geographic lookup
                tags=self._generate_npc_tags(npc_def),
                awareness_radius=max(npc_def.interaction_radius * 8, 32.0),
                activity_log=[],
                metadata={"dialogue_lines": npc_def.dialogue_lines,
                           "quests": npc_def.quests}
            )
            # Auto-fill geographic data
            geo = GeographicRegistry.get_instance()
            address = geo.get_full_address(npc_def.position.x, npc_def.position.y)
            entity.home_region_id = address.get("locality")
            entity.home_district_id = address.get("district")
            entity.home_province_id = address.get("province")
            # Add location tags
            for level, region_id in address.items():
                entity.tags.append(f"location:{region_id}")

            self.register(entity)

    def load_from_regions(self, geo_registry: 'GeographicRegistry'):
        """Register all regions as entities (so they can be queried too)"""
        for region_id, region in geo_registry.regions.items():
            cx = (region.bounds_x1 + region.bounds_x2) / 2
            cy = (region.bounds_y1 + region.bounds_y2) / 2
            entity = WorldEntity(
                entity_id=f"region_{region_id}",
                entity_type=EntityType.LOCATION,
                name=region.name,
                position_x=cx,
                position_y=cy,
                home_region_id=region_id,
                tags=region.tags + [f"level:{region.level.value}"],
                awareness_radius=max(
                    region.bounds_x2 - region.bounds_x1,
                    region.bounds_y2 - region.bounds_y1
                ) / 2,
                activity_log=[],
                metadata={"description": region.description,
                           "biome_primary": region.biome_primary}
            )
            self.register(entity)
```

### Dynamic Tag Updates

Player tags change over time as behavior changes. NPC tags can change if their role/faction changes:

```python
def update_entity_tags(self, entity_id: str, add_tags: List[str] = None,
                       remove_tags: List[str] = None):
    """Update tags for an entity (e.g., player playstyle changes)"""
    entity = self.entities.get(entity_id)
    if not entity:
        return

    if remove_tags:
        for tag in remove_tags:
            if tag in entity.tags:
                entity.tags.remove(tag)
                if tag in self._tag_index:
                    self._tag_index[tag] = [
                        eid for eid in self._tag_index[tag] if eid != entity_id
                    ]

    if add_tags:
        for tag in add_tags:
            if tag not in entity.tags:
                entity.tags.append(tag)
                self._tag_index.setdefault(tag, []).append(entity_id)
```

### Serialization

```python
def to_dict(self) -> Dict[str, Any]:
    """Serialize for save system"""
    return {
        "entities": {
            eid: {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type.value,
                "name": e.name,
                "position_x": e.position_x,
                "position_y": e.position_y,
                "home_region_id": e.home_region_id,
                "awareness_radius": e.awareness_radius,
                "tags": e.tags,
                "activity_log": e.activity_log,
                "metadata": e.metadata
            }
            for eid, e in self.entities.items()
        }
    }
```
