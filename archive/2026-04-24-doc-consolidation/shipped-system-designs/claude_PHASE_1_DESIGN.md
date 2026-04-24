# Phase 1: Tag Registry, Archetype Library, Affinity Defaults

**Status**: Design (Pre-Implementation)
**Depends On**: None (bootstrap phase)
**Deliverables**: Config files + TagRegistry + AffinityDefaults singletons
**Est. Effort**: Medium (3 config files + 2 classes + tests)

---

## Deliverable 1: tag-registry.json

**Purpose**: Durable, append-only dictionary of all tags ever used in the game.

**Location**: `Game-1-modular/world_system/config/tag-registry.json`

**Format**:

```json
{
  "metadata": {
    "version": 1,
    "last_updated_game_time": 0.0,
    "total_tags": 47
  },
  "tags": {
    "nation:stormguard": {
      "namespace": "nation",
      "appearance_count": 12,
      "first_seen_game_time": 0.0,
      "human_gloss": "A major northern kingdom known for defensive strength",
      "is_generated": false,
      "aliases": []
    },
    "guild:merchants": {
      "namespace": "guild",
      "appearance_count": 8,
      "first_seen_game_time": 0.0,
      "human_gloss": "A widespread trading consortium with regional chapters",
      "is_generated": false,
      "aliases": ["guild:merchant_union"]
    },
    "cult:thorn": {
      "namespace": "cult",
      "appearance_count": 2,
      "first_seen_game_time": 100.5,
      "human_gloss": "A secretive nature-worship movement",
      "is_generated": true,
      "aliases": []
    },
    "profession:blacksmith": {
      "namespace": "profession",
      "appearance_count": 1,
      "first_seen_game_time": 0.0,
      "human_gloss": "Craft profession: working with metal and stone",
      "is_generated": false,
      "aliases": []
    }
  }
}
```

**Rules**:
- Tags are NEVER deleted, only marked deprecated if needed
- appearance_count increments each time an NPC is created with that tag
- is_generated = true if LLM created the tag; false if authored
- aliases track name changes (backward compatibility)
- human_gloss is author-provided definition (not LLM-generated)

**Bootstrap Content** (pre-authored for static 4-nation map):

```
Nations (4):
  nation:stormguard
  nation:blackoak
  nation:shattered_isles
  nation:verdant_reaches

Professions (6):
  profession:blacksmith
  profession:merchant
  profession:guard
  profession:farmer
  profession:fisher
  profession:scholar

Guilds (3):
  guild:merchants
  guild:smiths
  guild:fishers

Locations (4, seed):
  locality:village_westhollow
  locality:city_ironhold
  locality:port_tidemark
  locality:forest_haven

[+ any others visible in current NPCs + quests]
```

---

## Deliverable 2: faction-archetypes.json

**Purpose**: Prompt guidance + suggested tag spreads for NPC creation.

**Location**: `Game-1-modular/world_system/config/faction-archetypes.json`

**Format**:

```json
{
  "archetypes": {
    "village_blacksmith": {
      "description": "A master craftsperson in a small settlement",
      "narrative_seed": "Skilled at their craft, known locally, tied to the town through generations or circumstance",
      "suggested_tags": [
        {
          "tag": "profession:blacksmith",
          "suggested_significance": 0.8,
          "role": "master",
          "rationale": "Central to their identity"
        },
        {
          "tag": "locality:{location_name}",
          "suggested_significance": 0.7,
          "role": "resident",
          "rationale": "They live and work here"
        },
        {
          "tag": "guild:smiths",
          "suggested_significance": 0.5,
          "role": "member",
          "rationale": "Professional affiliation, loose"
        }
      ],
      "affinity_considerations": [
        "Smiths often have affinity toward nobles (they buy weapons) or against merchants (they compete)",
        "Loyalty to their locality is strong; less concern for broader nation"
      ]
    },
    "merchant_trader": {
      "description": "A traveling or settled merchant working for a larger guild",
      "narrative_seed": "Mobile, profit-driven, networked across regions",
      "suggested_tags": [
        {
          "tag": "guild:merchants",
          "suggested_significance": 0.8,
          "role": "member",
          "rationale": "Professional identity"
        },
        {
          "tag": "locality:{location_name}",
          "suggested_significance": 0.4,
          "role": "regular",
          "rationale": "They trade here but aren't rooted"
        }
      ],
      "affinity_considerations": [
        "Merchants typically have affinity toward wealthy NPCs and cities",
        "May be suspicious of isolationist factions"
      ]
    },
    "town_guard": {
      "description": "A soldier or watchman defending a settlement",
      "narrative_seed": "Duty-bound, protective, often concerned with local threats and order",
      "suggested_tags": [
        {
          "tag": "profession:guard",
          "suggested_significance": 0.9,
          "role": "active_duty",
          "rationale": "Central professional identity"
        },
        {
          "tag": "nation:{nation_name}",
          "suggested_significance": 0.6,
          "role": "soldier",
          "rationale": "Sworn to broader authority"
        },
        {
          "tag": "locality:{location_name}",
          "suggested_significance": 0.7,
          "role": "protector",
          "rationale": "This is their assigned post"
        }
      ],
      "affinity_considerations": [
        "High affinity for order-keeping factions, law, stability",
        "Affinity varies by nation's current politics"
      ]
    }
  },
  "guidelines": {
    "use_in_prompt": "If the NPC's role matches an archetype, include suggested tags but let LLM override",
    "override_note": "Archetypes are seeds, not chains. LLM may invent new tags or skip suggested ones.",
    "location_templating": "Replace {location_name} and {nation_name} with actual geography"
  }
}
```

**Bootstrap Content** (3-5 archetypes for common roles):
- village_blacksmith
- merchant_trader
- town_guard
- village_mayor / regional_administrator
- wanderer / refugee

**Expansion**: As game content grows, add more archetypes. This is a living library.

---

## Deliverable 3: affinity-defaults.json

**Purpose**: World-scale, nation-scale, region-scale, province-scale, district-scale, locality-scale affinity defaults.

**Location**: `Game-1-modular/world_system/config/affinity-defaults.json`

**Format**:

```json
{
  "world": {
    "comment": "Baseline affinity for all tags everywhere (unless overridden)",
    "guild:merchants": -0.1,
    "guild:smiths": 0.0,
    "profession:guard": 0.1,
    "profession:blacksmith": 0.05
  },
  
  "nations": {
    "nation:stormguard": {
      "comment": "Kingdom values defensive strength",
      "guild:merchants": -0.2,
      "guild:smiths": 0.15,
      "profession:guard": 0.2,
      "profession:merchant": -0.15,
      "ideology:separatist": -0.3
    },
    "nation:blackoak": {
      "comment": "Trade-oriented, mercantile",
      "guild:merchants": 0.2,
      "guild:smiths": 0.0,
      "profession:merchant": 0.25,
      "profession:guard": -0.05,
      "ideology:unifier": 0.1
    }
  },

  "regions": {
    "region:northern_marches": {
      "comment": "Border region, defensive mindset",
      "guild:merchants": -0.25,
      "profession:guard": 0.3,
      "profession:merchant": -0.2
    }
  },

  "provinces": {
    "province:iron_hills": {
      "comment": "Mining/smithing center",
      "guild:smiths": 0.25,
      "profession:blacksmith": 0.3,
      "guild:merchants": -0.35
    }
  },

  "districts": {
    "district:whispering_woods": {
      "comment": "Forest area, nature-inclined",
      "cult:verdant": 0.1,
      "ideology:wilderness_first": 0.15
    }
  },

  "localities": {
    "village_westhollow": {
      "comment": "Small grain farming settlement",
      "guild:merchants": -0.3,
      "profession:farmer": 0.2,
      "nation:stormguard": 0.05
    },
    "city_ironhold": {
      "comment": "Major smithing and mining city",
      "guild:smiths": 0.3,
      "profession:blacksmith": 0.25,
      "guild:merchants": -0.1
    }
  }
}
```

**Rules**:
- Lookup order (for any NPC affinity): world → nation → region → province → district → locality
- First found value wins; others are ignored
- 0.0 = neutral/default
- Values are meant to be tuned through play (quests, events may modify)
- Missing values default to 0.0

**Content Strategy**:
1. Bootstrap with world-level defaults for all major tags
2. Per-nation overrides based on known politics (e.g., Stormguard dislikes merchants)
3. Per-locality overrides for unique flavor (e.g., mining town = pro-smith)
4. As quests execute, world-scale values may shift (e.g., guild scandal drops merchant affinity)

---

## Deliverable 4: TagRegistry Class

**Location**: `Game-1-modular/world_system/faction/tag_registry.py`

**Interface**:

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
import json
from pathlib import Path

@dataclass
class TagEntry:
    tag: str
    namespace: str
    appearance_count: int
    first_seen_game_time: float
    human_gloss: str
    is_generated: bool
    aliases: List[str]

class TagRegistry:
    """
    Singleton registry of all tags ever used in the game.
    Persists to tag-registry.json.
    """
    
    _instance: Optional['TagRegistry'] = None
    
    def __init__(self, config_path: str = "world_system/config/tag-registry.json"):
        self.config_path = Path(config_path)
        self.tags: Dict[str, TagEntry] = {}
        self._load()
    
    @classmethod
    def get_instance(cls) -> 'TagRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load(self) -> None:
        """Load registry from disk (or initialize empty)"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                for tag_name, tag_data in data.get('tags', {}).items():
                    self.tags[tag_name] = TagEntry(**tag_data)
        else:
            # Initialize empty
            self.tags = {}
    
    def save(self) -> None:
        """Persist registry to disk"""
        data = {
            "metadata": {
                "version": 1,
                "last_updated_game_time": 0.0,
                "total_tags": len(self.tags)
            },
            "tags": {
                tag_name: {
                    "namespace": entry.namespace,
                    "appearance_count": entry.appearance_count,
                    "first_seen_game_time": entry.first_seen_game_time,
                    "human_gloss": entry.human_gloss,
                    "is_generated": entry.is_generated,
                    "aliases": entry.aliases
                }
                for tag_name, entry in self.tags.items()
            }
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register(self, tag: str, namespace: str, gloss: str, 
                 is_generated: bool = False, game_time: float = 0.0) -> None:
        """Register a new tag or increment its count"""
        if tag not in self.tags:
            self.tags[tag] = TagEntry(
                tag=tag,
                namespace=namespace,
                appearance_count=1,
                first_seen_game_time=game_time,
                human_gloss=gloss,
                is_generated=is_generated,
                aliases=[]
            )
        else:
            self.tags[tag].appearance_count += 1
    
    def get(self, tag: str) -> Optional[TagEntry]:
        """Fetch a tag entry"""
        return self.tags.get(tag)
    
    def all_tags(self, namespace: Optional[str] = None) -> List[TagEntry]:
        """Get all tags, optionally filtered by namespace"""
        tags = list(self.tags.values())
        if namespace:
            tags = [t for t in tags if t.namespace == namespace]
        return tags
    
    def appearance_count(self, tag: str) -> int:
        """Get count of NPCs with this tag"""
        entry = self.get(tag)
        return entry.appearance_count if entry else 0
    
    def validate_tag(self, tag: str) -> bool:
        """Check if a tag is registered"""
        return tag in self.tags
    
    def validate_namespace(self, tag: str, namespace: str) -> bool:
        """Check if tag's namespace is correct"""
        entry = self.get(tag)
        return entry and entry.namespace == namespace
    
    def add_alias(self, tag: str, alias: str) -> None:
        """Add an alias (for backward compatibility)"""
        if tag in self.tags:
            if alias not in self.tags[tag].aliases:
                self.tags[tag].aliases.append(alias)
```

---

## Deliverable 5: AffinityDefaults Class

**Location**: `Game-1-modular/world_system/faction/affinity_defaults.py`

**Interface**:

```python
from dataclasses import dataclass
from typing import Dict, Optional
import json
from pathlib import Path

class AffinityDefaults:
    """
    Hierarchical affinity defaults: world → nation → region → province → district → locality.
    Supports lookup with fallback and modification.
    """
    
    _instance: Optional['AffinityDefaults'] = None
    
    def __init__(self, config_path: str = "world_system/config/affinity-defaults.json"):
        self.config_path = Path(config_path)
        self.defaults: Dict = {}
        self._load()
    
    @classmethod
    def get_instance(cls) -> 'AffinityDefaults':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load(self) -> None:
        """Load affinity defaults from disk"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.defaults = json.load(f)
        else:
            # Initialize empty structure
            self.defaults = {
                "world": {},
                "nations": {},
                "regions": {},
                "provinces": {},
                "districts": {},
                "localities": {}
            }
    
    def save(self) -> None:
        """Persist affinity defaults to disk"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.defaults, f, indent=2)
    
    def lookup(self, tag: str, location_hierarchy: Dict[str, str]) -> float:
        """
        Lookup affinity for a tag at a given location.
        
        location_hierarchy: {
            "locality": "village_westhollow",
            "district": "district_whispering_woods",
            "province": "province_iron_hills",
            "region": "region:northern_marches",
            "nation": "nation:stormguard",
            "world": None
        }
        
        Returns: float affinity (0.0 if not found)
        """
        # Lookup order: locality → district → province → region → nation → world
        for tier in ["locality", "district", "province", "region", "nation", "world"]:
            location_id = location_hierarchy.get(tier)
            if location_id is None:
                continue
            
            tier_data = self.defaults.get(tier + "s" if tier != "world" else "world", {})
            if location_id in tier_data:
                affinity = tier_data[location_id].get(tag)
                if affinity is not None:
                    return affinity
        
        # Fallback
        return 0.0
    
    def set_world_affinity(self, tag: str, delta: float) -> None:
        """Update world-level affinity for a tag"""
        self.defaults["world"][tag] = delta
    
    def set_nation_affinity(self, nation_id: str, tag: str, delta: float) -> None:
        """Update nation-level affinity"""
        if nation_id not in self.defaults["nations"]:
            self.defaults["nations"][nation_id] = {}
        self.defaults["nations"][nation_id][tag] = delta
    
    def set_locality_affinity(self, locality_id: str, tag: str, delta: float) -> None:
        """Update locality-level affinity"""
        if locality_id not in self.defaults["localities"]:
            self.defaults["localities"][locality_id] = {}
        self.defaults["localities"][locality_id][tag] = delta
    
    # ... similar methods for region, province, district ...
```

---

## Deliverable 6: Initialization & Save/Load Integration

**Location**: `Game-1-modular/world_system/faction/__init__.py`

```python
from .tag_registry import TagRegistry
from .affinity_defaults import AffinityDefaults

def initialize_faction_system() -> None:
    """Called from game_engine._init_world_memory()"""
    TagRegistry.get_instance()
    AffinityDefaults.get_instance()

def save_faction_system() -> Dict:
    """Called from save_manager"""
    return {
        "tag_registry": {
            # Save state if needed (mostly for appearance_counts)
        },
        "affinity_defaults": AffinityDefaults.get_instance().defaults
    }

def restore_faction_system(save_data: Dict) -> None:
    """Called from save_manager"""
    affinity = AffinityDefaults.get_instance()
    if "affinity_defaults" in save_data:
        affinity.defaults = save_data["affinity_defaults"]
```

---

## Test Coverage (Phase 1)

**Location**: `Game-1-modular/tests/test_faction_phase1.py`

```python
import pytest
from world_system.faction.tag_registry import TagRegistry
from world_system.faction.affinity_defaults import AffinityDefaults

class TestTagRegistry:
    def test_register_new_tag(self):
        registry = TagRegistry()
        registry.register("nation:testland", "nation", "A test nation")
        assert registry.validate_tag("nation:testland")
    
    def test_appearance_count_increment(self):
        registry = TagRegistry()
        registry.register("guild:test", "guild", "A test guild")
        assert registry.appearance_count("guild:test") == 1
        registry.register("guild:test", "guild", "A test guild")
        assert registry.appearance_count("guild:test") == 2
    
    def test_namespace_validation(self):
        registry = TagRegistry()
        registry.register("nation:test", "nation", "Test")
        assert registry.validate_namespace("nation:test", "nation")
        assert not registry.validate_namespace("nation:test", "guild")

class TestAffinityDefaults:
    def test_lookup_world_fallback(self):
        affinity = AffinityDefaults()
        affinity.set_world_affinity("guild:merchants", -0.1)
        
        hierarchy = {
            "locality": None,
            "district": None,
            "province": None,
            "region": None,
            "nation": None
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.1
    
    def test_lookup_hierarchy(self):
        affinity = AffinityDefaults()
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)
        
        hierarchy = {
            "locality": None,
            "district": None,
            "province": None,
            "region": None,
            "nation": "nation:stormguard"
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.2
    
    def test_locality_override(self):
        affinity = AffinityDefaults()
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_locality_affinity("village_westhollow", "guild:merchants", -0.3)
        
        hierarchy = {
            "locality": "village_westhollow",
            "district": None,
            "province": None,
            "region": None,
            "nation": None
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.3
```

---

## Implementation Checklist

- [ ] Create `world_system/faction/` directory
- [ ] Implement `tag_registry.py`
- [ ] Implement `affinity_defaults.py`
- [ ] Implement `__init__.py` with initialization/save/restore functions
- [ ] Create `tag-registry.json` with bootstrap content
- [ ] Create `faction-archetypes.json` with 3-5 starter archetypes
- [ ] Create `affinity-defaults.json` with world/nation/locality defaults
- [ ] Write test suite (test_faction_phase1.py)
- [ ] Integrate initialization into `core/game_engine.py::_init_world_memory()`
- [ ] Integrate save/restore into `systems/save_manager.py`
- [ ] Verify JSON loads without errors
- [ ] Commit and document

---

## File Summary

| File | Type | Purpose |
|------|------|---------|
| `world_system/config/tag-registry.json` | Config | Durable tag dictionary |
| `world_system/config/faction-archetypes.json` | Config | NPC creation guidance |
| `world_system/config/affinity-defaults.json` | Config | Affinity hierarchy |
| `world_system/faction/tag_registry.py` | Code | TagRegistry singleton |
| `world_system/faction/affinity_defaults.py` | Code | AffinityDefaults singleton |
| `world_system/faction/__init__.py` | Code | Initialization & save/load |
| `tests/test_faction_phase1.py` | Tests | Registry & hierarchy tests |

---

## Next Phase (Phase 2)

Once Phase 1 passes tests:
- Implement NPCFactionProfile dataclass
- Implement PlayerFactionProfile dataclass
- Rewrite FactionSystem around tag-indexed store
- Integrate with NPC JSON schema

