"""World Interpreter — reads Raw Event Pipeline data and Layer 1 stats
to generate Layer 2 interpreted events (the first narrative layer).

Layer 1 is pure cumulative counters (StatStore).  The Raw Event Pipeline
(EventStore) holds timestamped structured facts.  Neither is an "event"
in the narrative sense.  Layer 2 is where meaning first emerges — evaluators
read raw data and produce one-sentence narrative interpretations.

Each PatternEvaluator has a specific INPUT FRAME OF REFERENCE — defined by
what data it queries and how it processes it. The same raw event can trigger
multiple evaluators because each reads it through a different lens
(e.g., regional vs global, per-species vs per-tier).

33 evaluators covering combat, gathering, crafting, progression,
exploration, social, economy, and items.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import ClassVar, Dict, List, Optional

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import InterpretedEvent, WorldMemoryEvent, SEVERITY_ORDER
from world_system.world_memory.event_store import EventStore
from world_system.world_memory.geographic_registry import GeographicRegistry
from world_system.world_memory.entity_registry import EntityRegistry


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
    """Reads raw event pipeline patterns, generates Layer 2 narrative interpretations.

    Called when EventRecorder detects a prime-number trigger.
    """

    _instance: ClassVar[Optional[WorldInterpreter]] = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.layer_store = None  # LayerStore for per-layer tag-indexed storage
        self.wms_ai = None       # WmsAI for LLM narration (optional)
        self._evaluators: List[PatternEvaluator] = []
        self._interpretations_created: int = 0
        self._layer3_callback = None  # Callback to notify Layer3Manager of L2 events

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
                   entity_registry: EntityRegistry,
                   layer_store=None,
                   wms_ai=None) -> None:
        """Wire dependencies and register built-in evaluators."""
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.layer_store = layer_store
        self.wms_ai = wms_ai

        # Register all evaluators
        self._evaluators = []
        self._register_all_evaluators()

    def _register_all_evaluators(self) -> None:
        """Register all built-in evaluators. Each handles a specific input frame."""
        evaluator_modules = [
            # Legacy evaluators (kept for backward compatibility)
            ("world_system.world_memory.evaluators.population", "PopulationChangeEvaluator"),
            ("world_system.world_memory.evaluators.resources", "ResourcePressureEvaluator"),
            ("world_system.world_memory.evaluators.player_milestones", "PlayerMilestoneEvaluator"),
            ("world_system.world_memory.evaluators.area_danger", "AreaDangerEvaluator"),
            ("world_system.world_memory.evaluators.crafting", "CraftingTrendEvaluator"),
            # Combat evaluators
            ("world_system.world_memory.evaluators.combat_kills_regional_low_tier", "CombatKillsRegionalLowTierEvaluator"),
            ("world_system.world_memory.evaluators.combat_kills_regional_high_tier", "CombatKillsRegionalHighTierEvaluator"),
            ("world_system.world_memory.evaluators.combat_kills_global", "CombatKillsGlobalEvaluator"),
            ("world_system.world_memory.evaluators.combat_boss_kills", "CombatBossKillsEvaluator"),
            ("world_system.world_memory.evaluators.combat_damage_regional", "CombatDamageRegionalEvaluator"),
            ("world_system.world_memory.evaluators.combat_style", "CombatStyleEvaluator"),
            # Gathering evaluators
            ("world_system.world_memory.evaluators.gathering_regional", "GatheringRegionalEvaluator"),
            ("world_system.world_memory.evaluators.gathering_depletion", "GatheringDepletionEvaluator"),
            ("world_system.world_memory.evaluators.gathering_global", "GatheringGlobalEvaluator"),
            ("world_system.world_memory.evaluators.gathering_tools", "GatheringToolsEvaluator"),
            # Crafting evaluators (per discipline)
            ("world_system.world_memory.evaluators.crafting_smithing", "CraftingSmithingEvaluator"),
            ("world_system.world_memory.evaluators.crafting_alchemy", "CraftingAlchemyEvaluator"),
            ("world_system.world_memory.evaluators.crafting_refining", "CraftingRefiningEvaluator"),
            ("world_system.world_memory.evaluators.crafting_engineering", "CraftingEngineeringEvaluator"),
            ("world_system.world_memory.evaluators.crafting_enchanting", "CraftingEnchantingEvaluator"),
            ("world_system.world_memory.evaluators.crafting_minigame", "CraftingMinigameEvaluator"),
            ("world_system.world_memory.evaluators.crafting_inventions", "CraftingInventionsEvaluator"),
            # Progression evaluators
            ("world_system.world_memory.evaluators.progression_levels", "ProgressionLevelsEvaluator"),
            ("world_system.world_memory.evaluators.progression_skills", "ProgressionSkillsEvaluator"),
            ("world_system.world_memory.evaluators.progression_identity", "ProgressionIdentityEvaluator"),
            ("world_system.world_memory.evaluators.progression_equipment", "ProgressionEquipmentEvaluator"),
            # Exploration evaluators
            ("world_system.world_memory.evaluators.exploration_territory", "ExplorationTerritoryEvaluator"),
            ("world_system.world_memory.evaluators.exploration_dungeons", "ExplorationDungeonsEvaluator"),
            # Social evaluators
            ("world_system.world_memory.evaluators.social_npc", "SocialNpcEvaluator"),
            ("world_system.world_memory.evaluators.social_quests", "SocialQuestsEvaluator"),
            # Economy evaluators
            ("world_system.world_memory.evaluators.economy_flow", "EconomyFlowEvaluator"),
            # Items evaluators
            ("world_system.world_memory.evaluators.items_equipment", "ItemsEquipmentEvaluator"),
            ("world_system.world_memory.evaluators.items_inventory", "ItemsInventoryEvaluator"),
        ]

        import importlib
        for module_path, class_name in evaluator_modules:
            try:
                mod = importlib.import_module(module_path)
                evaluator_cls = getattr(mod, class_name)
                self._evaluators.append(evaluator_cls())
            except Exception as e:
                print(f"[Interpreter] Failed to load {class_name}: {e}")

    def add_evaluator(self, evaluator: PatternEvaluator) -> None:
        """Register an additional pattern evaluator."""
        self._evaluators.append(evaluator)

    def set_layer3_callback(self, callback) -> None:
        """Set callback to notify Layer3Manager when L2 events are created.

        The callback receives a dict representing the L2 event as stored
        in LayerStore (with 'tags' as a list of strings).
        """
        self._layer3_callback = callback

    def on_trigger(self, trigger_input) -> None:
        """Called when a threshold trigger fires.

        Accepts either a TriggerAction (from the new threshold system)
        or a WorldMemoryEvent (for backward compatibility).
        Evaluates all relevant pattern evaluators, enriches tags via
        the tag assignment system, and records interpretations.
        """
        if not self.event_store or not self.geo_registry:
            return

        # Support both TriggerAction and direct WorldMemoryEvent
        if hasattr(trigger_input, 'event'):
            # TriggerAction from the new threshold system
            trigger_event = trigger_input.event
        else:
            # Direct WorldMemoryEvent (backward compatibility)
            trigger_event = trigger_input

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

                # Enrich tags via tag assignment system (Layer 2)
                self._enrich_tags(interpretation, trigger_event)

                # Upgrade narrative via LLM if WmsAI available
                if self.wms_ai:
                    self._upgrade_narrative(interpretation, trigger_event)

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

                # Write to LayerStore (tag-indexed read-path)
                if self.layer_store:
                    try:
                        origin_key = trigger_event.event_type
                        if trigger_event.event_subtype:
                            origin_key = f"{trigger_event.event_type}.{trigger_event.event_subtype}"
                        self.layer_store.insert_event(
                            layer=2,
                            narrative=interpretation.narrative,
                            game_time=interpretation.created_at,
                            category=interpretation.category,
                            severity=interpretation.severity,
                            significance=interpretation.severity,
                            tags=interpretation.affects_tags or [],
                            origin_ref=origin_key,
                            evaluator_id=type(evaluator).__name__,
                            real_time=interpretation.created_at,
                            event_id=interpretation.interpretation_id,
                        )
                    except Exception as e:
                        print(f"[Interpreter] LayerStore write failed: {e}")

                # Notify Layer3Manager of new L2 event
                if self._layer3_callback:
                    try:
                        l2_dict = {
                            "id": interpretation.interpretation_id,
                            "narrative": interpretation.narrative,
                            "category": interpretation.category,
                            "severity": interpretation.severity,
                            "tags": interpretation.affects_tags or [],
                            "game_time": interpretation.created_at,
                        }
                        self._layer3_callback(l2_dict)
                    except Exception as e:
                        print(f"[Interpreter] Layer3 callback failed: {e}")

                # Propagate to region states
                self._propagate(interpretation)

    def _enrich_tags(self, interpretation: InterpretedEvent,
                     trigger_event: WorldMemoryEvent) -> None:
        """Enrich interpretation tags using the Layer 2 tag assignment system.

        Takes the evaluator's manually-set affects_tags as extra_tags,
        then builds the full Layer 2 tag set by inheriting from the
        origin stat's Layer 1 tags + adding geographic/scope/significance.

        The evaluator's original affects_tags are preserved as extra_tags
        that get merged into the full set.
        """
        try:
            from world_system.world_memory.tag_assignment import assign_layer2_tags

            # Derive the origin stat key from the trigger event
            # The stat key pattern is: "{event_type}" or "{event_type}.{subtype}"
            origin_stat_key = trigger_event.event_type
            if trigger_event.event_subtype:
                origin_stat_key = f"{trigger_event.event_type}.{trigger_event.event_subtype}"

            # Determine scope from the interpretation's geographic coverage
            if interpretation.affected_province_ids:
                scope = "regional"
            elif interpretation.affected_district_ids:
                scope = "district"
            elif interpretation.affected_locality_ids:
                scope = "local"
            else:
                scope = "global"

            # Build full Layer 2 tag set (6-tier address)
            enriched_tags = assign_layer2_tags(
                origin_stat_key=origin_stat_key,
                locality_id=trigger_event.locality_id or "",
                district_id=trigger_event.district_id or "",
                province_id=trigger_event.province_id or "",
                region_id=getattr(trigger_event, 'region_id', "") or "",
                nation_id=getattr(trigger_event, 'nation_id', "") or "",
                world_id=getattr(trigger_event, 'world_id', "") or "",
                biome=trigger_event.biome or "",
                scope=scope,
                significance=interpretation.severity,
                evaluator_category=interpretation.category,
                extra_tags=interpretation.affects_tags,
            )

            interpretation.affects_tags = enriched_tags
        except Exception as e:
            # If tag enrichment fails, keep original evaluator tags
            print(f"[Interpreter] Tag enrichment failed: {e}")

    def _upgrade_narrative(self, interpretation: InterpretedEvent,
                           trigger_event: WorldMemoryEvent) -> None:
        """Replace the template narrative with an LLM-generated one.

        Uses WmsAI to generate a richer narration from the evaluator's
        data (category, severity, tags, spatial scope) plus StatStore
        context. The evaluator's template narrative becomes the fallback
        if the LLM call fails.

        Called synchronously for now. Can be switched to async by queuing
        triggers and processing results in WorldMemorySystem.update().
        """
        if not self.wms_ai:
            return

        # Build data block from the evaluator's output + trigger context
        region_name = ""
        if trigger_event.locality_id and self.geo_registry:
            region = self.geo_registry.regions.get(trigger_event.locality_id)
            if region:
                region_name = region.name

        # Include the evaluator's template as context
        data_lines = [
            f"Event: {trigger_event.event_type} ({trigger_event.event_subtype})",
            f"Category: {interpretation.category}",
            f"Severity: {interpretation.severity}",
            f"Trigger count: {trigger_event.interpretation_count}",
        ]
        if region_name:
            data_lines.append(f"Location: {region_name}")
        if trigger_event.biome and trigger_event.biome != "unknown":
            data_lines.append(f"Biome: {trigger_event.biome}")
        if trigger_event.magnitude > 0:
            data_lines.append(f"Magnitude: {trigger_event.magnitude}")
        if trigger_event.tier:
            data_lines.append(f"Tier: {trigger_event.tier}")

        # Add the template narration as reference
        data_lines.append(f"Context: {interpretation.narrative}")

        data_block = "\n".join(data_lines)

        try:
            result = self.wms_ai.generate_narration(
                event_type=trigger_event.event_type,
                event_subtype=trigger_event.event_subtype or "",
                tier=trigger_event.tier,
                tags=interpretation.affects_tags,
                data_block=data_block,
                layer=2,
            )

            if result.success and result.text:
                interpretation.narrative = result.text
                # Update severity if the LLM detected a different level
                if result.severity != "minor":
                    interpretation.severity = result.severity
                # Apply LLM-assigned tags as extra tags
                if result.tags:
                    for tag in result.tags:
                        if tag not in interpretation.affects_tags:
                            interpretation.affects_tags.append(tag)
                else:
                    print(f"[Interpreter] WARNING: LLM returned no tags for "
                          f"L2 event {trigger_event.event_type}"
                          f"/{trigger_event.event_subtype} — "
                          f"check prompt or LLM output format")

        except Exception as e:
            # Keep the evaluator's template narrative on error
            print(f"[Interpreter] LLM upgrade failed: {e}")

    def _propagate(self, interpretation: InterpretedEvent) -> None:
        """Route interpretation to affected region states."""
        geo = self.geo_registry
        if not geo:
            return

        cfg = get_section("interpreter")
        max_recent = cfg.get("max_recent_events_per_region", 20)
        district_severities = set(cfg.get("propagation_to_district",
            ["significant", "major", "critical"]))
        province_severities = set(cfg.get("propagation_to_province",
            ["major", "critical"]))

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
        if interpretation.severity in district_severities:
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
        if interpretation.severity in province_severities:
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
