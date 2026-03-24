"""Entity Registry — central registry of all queryable world entities.

Every NPC, enemy type, resource type, region, and the player get an entry.
Entities carry interest tags that define what events are relevant to them.
Queries always start from an entity and radiate outward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional


class EntityType(Enum):
    PLAYER = "player"
    NPC = "npc"
    ENEMY_TYPE = "enemy_type"
    RESOURCE_TYPE = "resource_type"
    LOCATION = "location"
    STATION = "station"
    FACTION = "faction"


@dataclass
class WorldEntity:
    """A queryable entity in the world memory system."""
    entity_id: str
    entity_type: EntityType
    name: str

    # Position (None for abstract entities like resource types)
    position_x: Optional[float] = None
    position_y: Optional[float] = None

    # Geographic anchoring
    home_region_id: Optional[str] = None
    home_district_id: Optional[str] = None
    home_province_id: Optional[str] = None

    # How far this entity's awareness extends (in tiles)
    awareness_radius: float = 32.0

    # Interest tags — the entity's identity in the information system
    tags: List[str] = field(default_factory=list)

    # Activity log — bounded circular buffer of recent event_ids
    activity_log: List[str] = field(default_factory=list)
    activity_log_max: int = 100

    # Entity-specific metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_activity(self, event_id: str) -> None:
        """Append event to activity log, maintaining max size."""
        self.activity_log.append(event_id)
        if len(self.activity_log) > self.activity_log_max:
            self.activity_log.pop(0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "home_region_id": self.home_region_id,
            "home_district_id": self.home_district_id,
            "home_province_id": self.home_province_id,
            "awareness_radius": self.awareness_radius,
            "tags": self.tags,
            "activity_log": self.activity_log,
            "metadata": self.metadata,
        }


class EntityRegistry:
    """Central registry of all queryable entities. Singleton."""

    _instance: ClassVar[Optional[EntityRegistry]] = None

    def __init__(self):
        self.entities: Dict[str, WorldEntity] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag → [entity_ids]

    @classmethod
    def get_instance(cls) -> EntityRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── Registration ─────────────────────────────────────────────────

    def register(self, entity: WorldEntity) -> None:
        """Add or update an entity."""
        # Remove old tag index entries if updating
        if entity.entity_id in self.entities:
            self._remove_tag_index(entity.entity_id)
        self.entities[entity.entity_id] = entity
        self._build_tag_index(entity)

    def unregister(self, entity_id: str) -> None:
        """Remove an entity."""
        if entity_id in self.entities:
            self._remove_tag_index(entity_id)
            del self.entities[entity_id]

    def _build_tag_index(self, entity: WorldEntity) -> None:
        for tag in entity.tags:
            self._tag_index.setdefault(tag, []).append(entity.entity_id)

    def _remove_tag_index(self, entity_id: str) -> None:
        entity = self.entities.get(entity_id)
        if not entity:
            return
        for tag in entity.tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [
                    eid for eid in self._tag_index[tag] if eid != entity_id
                ]

    # ── Lookup ───────────────────────────────────────────────────────

    def get(self, entity_id: str) -> Optional[WorldEntity]:
        return self.entities.get(entity_id)

    def find_by_tag(self, tag: str) -> List[WorldEntity]:
        ids = self._tag_index.get(tag, [])
        return [self.entities[eid] for eid in ids if eid in self.entities]

    def find_by_tags(self, tags: List[str],
                     match_mode: str = "any") -> List[WorldEntity]:
        """Find entities matching tags.

        match_mode: "any" (at least one tag) or "all" (every tag).
        """
        if not tags:
            return []
        if match_mode == "any":
            result_ids: set = set()
            for tag in tags:
                result_ids.update(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids if eid in self.entities]
        else:
            result_ids_set = set(self._tag_index.get(tags[0], []))
            for tag in tags[1:]:
                result_ids_set &= set(self._tag_index.get(tag, []))
            return [self.entities[eid] for eid in result_ids_set if eid in self.entities]

    def find_by_type(self, entity_type: EntityType) -> List[WorldEntity]:
        return [e for e in self.entities.values() if e.entity_type == entity_type]

    def find_near(self, x: float, y: float, radius: float,
                  entity_type: Optional[EntityType] = None) -> List[WorldEntity]:
        """Find entities within radius of a position."""
        results = []
        radius_sq = radius * radius
        for entity in self.entities.values():
            if entity.position_x is None:
                continue
            if entity_type and entity.entity_type != entity_type:
                continue
            dx = x - entity.position_x
            dy = y - entity.position_y
            if dx * dx + dy * dy <= radius_sq:
                results.append(entity)
        return results

    # ── Tag updates ──────────────────────────────────────────────────

    def update_entity_tags(self, entity_id: str,
                           add_tags: Optional[List[str]] = None,
                           remove_tags: Optional[List[str]] = None) -> None:
        """Add/remove tags on an existing entity."""
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

    # ── Bulk loading from game databases ─────────────────────────────

    def load_from_npcs(self, npc_db, geo_registry=None) -> int:
        """Register all NPCs from the NPC database.

        Args:
            npc_db: NPCDatabase instance with .npcs dict
            geo_registry: Optional GeographicRegistry for address lookup
        Returns:
            Number of NPCs registered.
        """
        count = 0
        for npc_id, npc_def in npc_db.npcs.items():
            tags = self._generate_npc_tags(npc_def)
            entity = WorldEntity(
                entity_id=f"npc_{npc_id}",
                entity_type=EntityType.NPC,
                name=npc_def.name,
                position_x=npc_def.position.x,
                position_y=npc_def.position.y,
                awareness_radius=max(npc_def.interaction_radius * 8, 32.0),
                tags=tags,
                metadata={
                    "dialogue_lines": npc_def.dialogue_lines,
                    "quests": npc_def.quests,
                },
            )
            # Fill geographic anchoring
            if geo_registry:
                address = geo_registry.get_full_address(npc_def.position.x,
                                                        npc_def.position.y)
                entity.home_region_id = address.get("locality")
                entity.home_district_id = address.get("district")
                entity.home_province_id = address.get("province")
                for level, region_id in address.items():
                    entity.tags.append(f"location:{region_id}")
            self.register(entity)
            count += 1
        return count

    def _generate_npc_tags(self, npc_def) -> List[str]:
        """Derive interest tags from an NPC definition."""
        tags = ["species:human", "type:npc"]
        # Infer role from quests
        if npc_def.quests:
            tags.append("role:quest_giver")
        # Name-based heuristics for domain tagging
        name_lower = npc_def.name.lower()
        role_keywords = {
            "smith": ["job:blacksmith", "domain:smithing", "domain:metalwork",
                       "resource:iron", "resource:steel"],
            "herb": ["job:herbalist", "domain:alchemy", "domain:herbs",
                      "resource:herbs"],
            "merchant": ["job:merchant", "role:shopkeeper"],
            "guard": ["job:guard", "domain:combat"],
            "elder": ["role:elder", "domain:lore"],
            "sage": ["role:sage", "domain:lore", "domain:magic"],
            "alchemist": ["job:alchemist", "domain:alchemy", "domain:potions"],
            "miner": ["job:miner", "domain:mining", "resource:iron", "resource:stone"],
            "hunter": ["job:hunter", "domain:hunting", "domain:combat"],
            "engineer": ["job:engineer", "domain:engineering"],
        }
        for keyword, keyword_tags in role_keywords.items():
            if keyword in name_lower:
                tags.extend(keyword_tags)
        return tags

    def load_from_regions(self, geo_registry) -> int:
        """Register all regions as entities (so they can be queried too)."""
        count = 0
        for region_id, region in geo_registry.regions.items():
            cx, cy = region.center
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
                    region.bounds_y2 - region.bounds_y1,
                ) / 2.0,
                metadata={
                    "description": region.description,
                    "biome_primary": region.biome_primary,
                },
            )
            self.register(entity)
            count += 1
        return count

    def register_player(self, character) -> None:
        """Register or update the player entity."""
        tags = ["type:player"]
        # Dynamic tags from character state
        if hasattr(character, "leveling"):
            level = character.leveling.level
            if level <= 10:
                tags.append("level:tier_1")
            elif level <= 20:
                tags.append("level:tier_2")
            else:
                tags.append("level:tier_3")
        if hasattr(character, "class_system") and character.class_system.current_class:
            tags.append(f"class:{character.class_system.current_class}")
        entity = WorldEntity(
            entity_id="player",
            entity_type=EntityType.PLAYER,
            name="Player",
            position_x=character.position.x,
            position_y=character.position.y,
            awareness_radius=9999.0,  # Player is globally aware
            tags=tags,
        )
        self.register(entity)

    def update_player_position(self, x: float, y: float) -> None:
        """Update the player entity's position (called each frame)."""
        player = self.entities.get("player")
        if player:
            player.position_x = x
            player.position_y = y

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize dynamic entity state (activity logs, dynamic tags)."""
        return {
            eid: {
                "tags": e.tags,
                "activity_log": e.activity_log,
            }
            for eid, e in self.entities.items()
        }

    def restore_state(self, data: Dict[str, Any]) -> None:
        """Restore dynamic state from save data."""
        for eid, state in data.items():
            entity = self.entities.get(eid)
            if entity:
                entity.tags = state.get("tags", entity.tags)
                entity.activity_log = state.get("activity_log", [])
