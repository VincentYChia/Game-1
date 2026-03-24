"""World Interpreter — transforms Layer 2 facts into Layer 3 narratives.

Reads raw event patterns and generates text descriptions when prime-number
occurrence counts trigger evaluation. Each PatternEvaluator covers a
different "beat" (population changes, resource pressure, milestones, etc.).

Output is NARRATIVE TEXT ONLY — no JSON game effects.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import ClassVar, Dict, List, Optional

from ai.memory.event_schema import InterpretedEvent, WorldMemoryEvent, SEVERITY_ORDER
from ai.memory.event_store import EventStore
from ai.memory.geographic_registry import GeographicRegistry
from ai.memory.entity_registry import EntityRegistry


class PatternEvaluator(ABC):
    """Base class for pattern detection evaluators."""

    @abstractmethod
    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        """Does this evaluator care about this event type?"""

    @abstractmethod
    def evaluate(self, trigger_event: WorldMemoryEvent,
                 event_store: EventStore,
                 geo_registry: GeographicRegistry,
                 entity_registry: EntityRegistry,
                 interpretation_store: EventStore) -> Optional[InterpretedEvent]:
        """Evaluate patterns and optionally return an interpretation."""


class WorldInterpreter:
    """Reads Layer 2 patterns, generates Layer 3 narrative interpretations.

    Called when EventRecorder detects a prime-number trigger.
    """

    _instance: ClassVar[Optional[WorldInterpreter]] = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self._evaluators: List[PatternEvaluator] = []
        self._interpretations_created: int = 0

    @classmethod
    def get_instance(cls) -> WorldInterpreter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, event_store: EventStore,
                   geo_registry: GeographicRegistry,
                   entity_registry: EntityRegistry) -> None:
        """Wire dependencies and register built-in evaluators."""
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry

        # Register built-in evaluators
        from ai.memory.evaluators.population import PopulationChangeEvaluator
        from ai.memory.evaluators.resources import ResourcePressureEvaluator
        from ai.memory.evaluators.player_milestones import PlayerMilestoneEvaluator
        from ai.memory.evaluators.area_danger import AreaDangerEvaluator
        from ai.memory.evaluators.crafting import CraftingTrendEvaluator

        self._evaluators = [
            PopulationChangeEvaluator(),
            ResourcePressureEvaluator(),
            PlayerMilestoneEvaluator(),
            AreaDangerEvaluator(),
            CraftingTrendEvaluator(),
        ]

    def add_evaluator(self, evaluator: PatternEvaluator) -> None:
        """Register an additional pattern evaluator."""
        self._evaluators.append(evaluator)

    def on_trigger(self, trigger_event: WorldMemoryEvent) -> None:
        """Called when a prime-number trigger fires.

        Evaluates all relevant pattern evaluators and records interpretations.
        """
        if not self.event_store or not self.geo_registry:
            return

        for evaluator in self._evaluators:
            if evaluator.is_relevant(trigger_event):
                try:
                    interpretation = evaluator.evaluate(
                        trigger_event=trigger_event,
                        event_store=self.event_store,
                        geo_registry=self.geo_registry,
                        entity_registry=self.entity_registry,
                        interpretation_store=self.event_store,
                    )
                except Exception as e:
                    print(f"[Interpreter] Evaluator {type(evaluator).__name__} error: {e}")
                    continue

                if interpretation is None:
                    continue

                # Check if this supersedes an existing interpretation
                existing = self.event_store.find_supersedable(
                    category=interpretation.category,
                    affects_tags=interpretation.affects_tags,
                    locality_ids=interpretation.affected_locality_ids,
                )
                if existing:
                    interpretation.supersedes_id = existing.interpretation_id
                    interpretation.update_count = existing.update_count + 1
                    self.event_store.archive_interpretation(existing.interpretation_id)

                self.event_store.record_interpretation(interpretation)
                self._interpretations_created += 1

                # Propagate to region states
                self._propagate(interpretation)

    def _propagate(self, interpretation: InterpretedEvent) -> None:
        """Route interpretation to affected region states."""
        geo = self.geo_registry
        if not geo:
            return

        max_recent = 20

        # Update affected localities
        for locality_id in interpretation.affected_locality_ids:
            region = geo.regions.get(locality_id)
            if not region:
                continue
            region.state.recent_events.append(interpretation.interpretation_id)
            if interpretation.is_ongoing:
                region.state.active_conditions.append(interpretation.interpretation_id)
            if len(region.state.recent_events) > max_recent:
                region.state.recent_events = region.state.recent_events[-max_recent:]

        # Districts get significant+ events
        if interpretation.severity in ("significant", "major", "critical"):
            for district_id in interpretation.affected_district_ids:
                region = geo.regions.get(district_id)
                if not region:
                    continue
                region.state.recent_events.append(interpretation.interpretation_id)
                if interpretation.is_ongoing:
                    region.state.active_conditions.append(interpretation.interpretation_id)
                if len(region.state.recent_events) > max_recent:
                    region.state.recent_events = region.state.recent_events[-max_recent:]

        # Provinces get major+ events
        if interpretation.severity in ("major", "critical"):
            for province_id in interpretation.affected_province_ids:
                region = geo.regions.get(province_id)
                if not region:
                    continue
                region.state.recent_events.append(interpretation.interpretation_id)
                if interpretation.is_ongoing:
                    region.state.active_conditions.append(interpretation.interpretation_id)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "evaluators": len(self._evaluators),
            "interpretations_created": self._interpretations_created,
        }
