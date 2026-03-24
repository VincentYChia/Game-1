"""Player Milestone Evaluator — detects notable player achievements."""

from __future__ import annotations

from typing import Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry
from ai.memory.interpreter import PatternEvaluator


class PlayerMilestoneEvaluator(PatternEvaluator):

    RELEVANT_TYPES = {
        "enemy_killed", "level_up", "title_earned",
        "craft_attempted", "skill_learned", "class_changed",
    }

    # Milestones: (event_type, count) → (severity, narrative_template)
    KILL_MILESTONES = {
        1: ("minor", "The adventurer has slain their first {enemy} in {region}."),
        5: ("minor", "The adventurer is becoming experienced at hunting {enemy}s in {region}."),
        11: ("moderate", "The adventurer has become a proficient {enemy} hunter, with {count} kills in {region}."),
        29: ("significant", "The adventurer is a seasoned {enemy} slayer. {count} have fallen in {region}."),
        97: ("major", "The adventurer is legendary among {enemy} hunters. {count} kills in {region}."),
    }

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

        if level in (5, 10, 15, 20, 25, 30):
            severity = "significant" if level >= 20 else "moderate"
            narrative = (
                f"The adventurer has reached level {int(level)} in {region_name}. "
                f"{'A major milestone of power.' if level >= 20 else 'Growing stronger with each challenge.'}"
            )
        elif level == 1:
            return None  # Starting level, not interesting
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
        # Only fire at specific milestone counts
        milestone = None
        for threshold in sorted(self.KILL_MILESTONES.keys(), reverse=True):
            if count >= threshold:
                milestone = threshold
                break
        if milestone is None or count != milestone:
            # Only fire exactly at milestone counts (since we're triggered at primes)
            # Find the highest milestone <= count
            for threshold in sorted(self.KILL_MILESTONES.keys(), reverse=True):
                if count == threshold:
                    milestone = threshold
                    break
            else:
                return None

        severity, template = self.KILL_MILESTONES[milestone]
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
        if count < 3:
            return None
        quality = event.quality or "normal"

        if quality in ("masterwork", "legendary"):
            severity = "significant"
            narrative = (
                f"The adventurer has crafted a {quality} quality item. "
                f"Such skill is rare and noteworthy."
            )
        elif count in (5, 11, 29):
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
