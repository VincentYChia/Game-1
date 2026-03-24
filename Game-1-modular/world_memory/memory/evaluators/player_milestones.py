"""Player Milestone Evaluator — detects notable player achievements."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from world_memory.memory.config_loader import get_evaluator_config
from world_memory.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from world_memory.memory.event_store import EventStore
from world_memory.memory.geographic_registry import GeographicRegistry
from world_memory.memory.entity_registry import EntityRegistry
from world_memory.memory.interpreter import PatternEvaluator


class PlayerMilestoneEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {
        "enemy_killed", "level_up", "title_earned",
        "craft_attempted", "skill_learned", "class_changed",
    }

    def __init__(self):
        cfg = get_evaluator_config("player_milestones")
        # Build kill milestones from config
        raw_kills = cfg.get("kill_milestones", {
            "1":  {"severity": "minor",       "template": "The adventurer has slain their first {enemy} in {region}."},
            "5":  {"severity": "minor",       "template": "The adventurer is becoming experienced at hunting {enemy}s in {region}."},
            "11": {"severity": "moderate",    "template": "The adventurer has become a proficient {enemy} hunter, with {count} kills in {region}."},
            "29": {"severity": "significant", "template": "The adventurer is a seasoned {enemy} slayer. {count} have fallen in {region}."},
            "97": {"severity": "major",       "template": "The adventurer is legendary among {enemy} hunters. {count} kills in {region}."},
        })
        self.kill_milestones: Dict[int, Tuple[str, str]] = {
            int(k): (v["severity"], v["template"]) for k, v in raw_kills.items()
        }
        self.level_milestones = tuple(cfg.get("level_milestones", [5, 10, 15, 20, 25, 30]))
        self.level_major_threshold = cfg.get("level_major_threshold", 20)
        self.craft_min_count = cfg.get("craft_minimum_count", 3)
        self.craft_milestones = set(cfg.get("craft_milestones", [5, 11, 29]))
        self.high_quality_types = set(cfg.get("high_quality_types", ["masterwork", "legendary"]))

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        et = trigger_event.event_type

        if et == "level_up":
            return self._eval_level_up(trigger_event, geo_registry)
        if et == "title_earned":
            return self._eval_title(trigger_event, geo_registry)
        if et == "enemy_killed":
            return self._eval_kill_milestone(trigger_event, event_store, geo_registry)
        if et == "craft_attempted":
            return self._eval_craft_milestone(trigger_event, event_store, geo_registry)
        if et == "class_changed":
            return self._eval_class_change(trigger_event, geo_registry)
        return None

    def _eval_level_up(self, event: WorldMemoryEvent,
                       geo: GeographicRegistry) -> Optional[InterpretedEvent]:
        level = event.context.get("new_level", event.magnitude)
        region = geo.regions.get(event.locality_id or "") if event.locality_id else None
        region_name = region.name if region else "the wilds"

        if level in self.level_milestones:
            severity = "significant" if level >= self.level_major_threshold else "moderate"
            narrative = (
                f"The adventurer has reached level {int(level)} in {region_name}. "
                f"{'A major milestone of power.' if level >= self.level_major_threshold else 'Growing stronger with each challenge.'}"
            )
        elif level == 1:
            return None
        else:
            severity = "minor"
            narrative = f"The adventurer has grown to level {int(level)}."

        return InterpretedEvent.create(
            narrative=narrative,
            category="player_milestone",
            severity=severity,
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", f"event:{event.event_type}"],
        )

    def _eval_title(self, event: WorldMemoryEvent,
                    geo: GeographicRegistry) -> Optional[InterpretedEvent]:
        title = event.context.get("title", event.event_subtype)
        narrative = f"The adventurer has earned the title: {title}. Word of their deeds spreads."
        return InterpretedEvent.create(
            narrative=narrative,
            category="player_milestone",
            severity="moderate",
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:title_earned"],
        )

    def _eval_kill_milestone(self, event: WorldMemoryEvent,
                             store: EventStore,
                             geo: GeographicRegistry) -> Optional[InterpretedEvent]:
        count = event.interpretation_count
        milestone = None
        for threshold in sorted(self.kill_milestones.keys(), reverse=True):
            if count == threshold:
                milestone = threshold
                break
        if milestone is None:
            return None

        severity, template = self.kill_milestones[milestone]
        enemy_name = event.event_subtype.replace("killed_", "").replace("_", " ")
        region = geo.regions.get(event.locality_id or "")
        region_name = region.name if region else "the wilds"

        narrative = template.format(
            enemy=enemy_name, region=region_name, count=count
        )
        return InterpretedEvent.create(
            narrative=narrative,
            category="player_milestone",
            severity=severity,
            trigger_event_id=event.event_id,
            trigger_count=count,
            game_time=event.game_time,
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", f"species:{enemy_name.replace(' ', '_')}"],
        )

    def _eval_craft_milestone(self, event: WorldMemoryEvent,
                              store: EventStore,
                              geo: GeographicRegistry) -> Optional[InterpretedEvent]:
        count = event.interpretation_count
        if count < self.craft_min_count:
            return None
        quality = event.quality or "normal"

        if quality in self.high_quality_types:
            severity = "significant"
            narrative = (
                f"The adventurer has crafted a {quality} quality item. "
                f"Such skill is rare and noteworthy."
            )
        elif count in self.craft_milestones:
            severity = "minor"
            narrative = (
                f"The adventurer continues to hone their crafting skill, "
                f"with {count} items of this type now created."
            )
        else:
            return None

        return InterpretedEvent.create(
            narrative=narrative,
            category="player_milestone",
            severity=severity,
            trigger_event_id=event.event_id,
            trigger_count=count,
            game_time=event.game_time,
            affected_locality_ids=[event.locality_id] if event.locality_id else [],
            epicenter_x=event.position_x,
            epicenter_y=event.position_y,
            affects_tags=["type:player", "event:crafting"],
        )

    def _eval_class_change(self, event: WorldMemoryEvent,
                           geo: GeographicRegistry) -> Optional[InterpretedEvent]:
        new_class = event.context.get("class", event.event_subtype)
        narrative = f"The adventurer has chosen the path of the {new_class}."
        return InterpretedEvent.create(
            narrative=narrative,
            category="player_milestone",
            severity="moderate",
            trigger_event_id=event.event_id,
            trigger_count=event.interpretation_count,
            game_time=event.game_time,
            affects_tags=["type:player", f"class:{new_class}"],
        )
