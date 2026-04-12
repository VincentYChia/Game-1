"""Layer 3 Manager — orchestrates consolidation of Layer 2 interpretations.

Trigger: Every N Layer 2 events created (default 15, configurable).
When triggered, runs all 4 consolidators for each district that has
accumulated new Layer 2 events since last consolidation.

Data flow:
    Layer 2 interpretation stored in LayerStore
           ↓
    Layer3Manager.on_layer2_created() increments counter
           ↓ (every N events)
    For each district with 3+ L2 events:
      1. Query LayerStore: layer2_events by district tag
      2. Run all consolidators
      3. Enrich tags via HigherLayerTagAssigner
      4. Call WmsAI.generate_narration(layer=3)
      5. Store result in layer3_events + layer3_tags

Visibility rule (two-layers-down):
    Layer 3 sees Layer 2 (full) and Raw Event Pipeline (limited).
    Layer 3 does NOT see Layer 1 stats or Layers 4-7.
"""

from __future__ import annotations

import json
import time
from typing import Any, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import ConsolidatedEvent, SEVERITY_ORDER
from world_system.world_memory.consolidator_base import ConsolidatorBase
from world_system.world_memory.tag_assignment import assign_higher_layer_tags


class Layer3Manager:
    """Orchestrates Layer 3 consolidation. Singleton.

    Tracks Layer 2 event creation count, triggers consolidation runs,
    manages consolidator registration, and stores results.
    """

    _instance: ClassVar[Optional[Layer3Manager]] = None

    def __init__(self):
        self._consolidators: List[ConsolidatorBase] = []
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._initialized = False

        # Trigger tracking
        self._l2_events_since_last_run: int = 0
        self._trigger_interval: int = 15  # Run every N L2 events
        self._districts_with_new_l2: Set[str] = set()

        # Layer 4 callback — notified when L3 events are stored
        self._layer4_callback = None

        # Stats
        self._consolidations_created: int = 0
        self._runs_completed: int = 0
        self._last_run_game_time: float = 0.0

        # Minimum L2 events per district to trigger consolidation
        self._min_l2_per_district: int = 3
        self._min_categories_per_district: int = 2

    @classmethod
    def get_instance(cls) -> Layer3Manager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, layer_store, geo_registry, wms_ai=None) -> None:
        """Wire dependencies and register consolidators.

        Args:
            layer_store: LayerStore for reading L2 and writing L3.
            geo_registry: GeographicRegistry for district hierarchy.
            wms_ai: WmsAI for LLM narration (optional, templates used as fallback).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        # Load config
        cfg = get_section("layer3")
        self._trigger_interval = cfg.get("trigger_interval", 15)
        self._min_l2_per_district = cfg.get("min_l2_per_district", 3)
        self._min_categories_per_district = cfg.get("min_categories_per_district", 2)

        # Register all consolidators
        self._consolidators = []
        self._register_all_consolidators()

        self._initialized = True
        print(f"[Layer3] Initialized — {len(self._consolidators)} consolidators, "
              f"trigger every {self._trigger_interval} L2 events")

    def _register_all_consolidators(self) -> None:
        """Register all built-in Layer 3 consolidators."""
        consolidator_modules = [
            ("world_system.world_memory.consolidators.regional_synthesis",
             "RegionalSynthesisConsolidator"),
            ("world_system.world_memory.consolidators.cross_domain",
             "CrossDomainConsolidator"),
            ("world_system.world_memory.consolidators.player_identity",
             "PlayerIdentityConsolidator"),
            ("world_system.world_memory.consolidators.faction_narrative",
             "FactionNarrativeConsolidator"),
        ]

        import importlib
        for module_path, class_name in consolidator_modules:
            try:
                mod = importlib.import_module(module_path)
                consolidator_cls = getattr(mod, class_name)
                self._consolidators.append(consolidator_cls())
            except Exception as e:
                print(f"[Layer3] Failed to load {class_name}: {e}")

    def add_consolidator(self, consolidator: ConsolidatorBase) -> None:
        """Register an additional consolidator."""
        self._consolidators.append(consolidator)

    def set_layer4_callback(self, callback) -> None:
        """Register a callback invoked when L3 events are stored.

        The callback receives the stored L3 event dict (as it would appear
        from LayerStore). Used by Layer4Manager to track per-province triggers.
        """
        self._layer4_callback = callback

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer2_created(self, l2_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 2 interpretation is stored.

        Tracks which districts have new L2 events and increments the
        trigger counter. When the counter reaches the trigger interval,
        a consolidation run is scheduled.

        Args:
            l2_event_dict: The Layer 2 event as stored in LayerStore.
        """
        if not self._initialized:
            return

        self._l2_events_since_last_run += 1

        # Track which district this L2 event belongs to
        tags = l2_event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("district:"):
                district_id = tag.split(":", 1)[1]
                self._districts_with_new_l2.add(district_id)
                break

    def should_run(self) -> bool:
        """Check if consolidation should trigger."""
        return (self._initialized and
                self._l2_events_since_last_run >= self._trigger_interval)

    def run_consolidation(self, game_time: float) -> int:
        """Execute a consolidation pass across all districts with new L2 events.

        Returns the number of Layer 3 events created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        created = 0
        districts_to_process = list(self._districts_with_new_l2)

        # Also run global consolidators (player_identity, faction)
        # by processing with empty district_id
        districts_to_process.append("")

        for district_id in districts_to_process:
            if district_id:
                # Get L2 events for this district
                l2_events = self._query_l2_for_district(district_id)
            else:
                # Global scope — get all recent L2 events
                l2_events = self._query_l2_global()

            if not l2_events:
                continue

            # Build geographic context
            geo_context = self._build_geo_context(district_id)

            # Run each consolidator
            for consolidator in self._consolidators:
                if not consolidator.is_applicable(l2_events, district_id):
                    continue

                try:
                    result = consolidator.consolidate(
                        l2_events=l2_events,
                        district_id=district_id,
                        geo_context=geo_context,
                        game_time=game_time,
                    )
                except Exception as e:
                    print(f"[Layer3] {consolidator.consolidator_id} error: {e}")
                    continue

                if result is None:
                    continue

                # Upgrade narrative via LLM if available.
                # LLM also assigns interpretive tags (sentiment, trend, etc.)
                # which replace the consolidator's template tags.
                if self._wms_ai:
                    self._upgrade_narrative(result, consolidator, l2_events,
                                            geo_context)

                # Enrich tags via HigherLayerTagAssigner:
                # Inherits from L2 origin events + merges LLM/consolidator tags
                origin_tags = [e.get("tags", []) for e in l2_events]
                enriched = assign_higher_layer_tags(
                    layer=3,
                    origin_event_tags=origin_tags,
                    significance=result.severity,
                    layer_specific_tags=result.affects_tags,
                )
                result.affects_tags = enriched

                # Store in LayerStore
                self._store_consolidation(result, game_time)
                created += 1
                self._consolidations_created += 1

        # Reset trigger state
        self._l2_events_since_last_run = 0
        self._districts_with_new_l2.clear()
        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(f"[Layer3] Consolidation run #{self._runs_completed}: "
                  f"{created} events created")

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _query_l2_for_district(self, district_id: str) -> List[Dict[str, Any]]:
        """Query all Layer 2 events for a specific district."""
        if not self._layer_store:
            return []
        return self._layer_store.query_by_tags(
            layer=2,
            tags=[f"district:{district_id}"],
            match_all=True,
            limit=100,
        )

    def _query_l2_global(self) -> List[Dict[str, Any]]:
        """Query recent Layer 2 events across all districts."""
        if not self._layer_store:
            return []
        # Get all recent L2 events (no tag filter, sorted by time desc)
        c = self._layer_store.connection
        rows = c.execute(
            "SELECT * FROM layer2_events ORDER BY game_time DESC LIMIT 100"
        ).fetchall()
        return [self._layer_store._row_to_dict(row) for row in rows]

    def _build_geo_context(self, district_id: str) -> Dict[str, Any]:
        """Build geographic context for a district."""
        if not self._geo_registry or not district_id:
            return {"district_name": "", "province_name": "",
                    "localities": []}

        district = self._geo_registry.regions.get(district_id)
        if not district:
            return {"district_name": district_id, "province_name": "",
                    "localities": []}

        # Get province (parent)
        province_name = ""
        if district.parent_id:
            province = self._geo_registry.regions.get(district.parent_id)
            if province:
                province_name = province.name

        # Get localities (children)
        localities = []
        for child_id in district.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child:
                localities.append({"id": child_id, "name": child.name})

        return {
            "district_name": district.name,
            "province_name": province_name,
            "localities": localities,
        }

    def _upgrade_narrative(self, result: ConsolidatedEvent,
                           consolidator: ConsolidatorBase,
                           l2_events: List[Dict[str, Any]],
                           geo_context: Dict[str, Any]) -> None:
        """Replace template narrative and tags with LLM-generated ones.

        The LLM returns JSON with both 'narrative' and 'tags' fields.
        LLM-assigned tags (sentiment, trend, intensity, etc.) replace
        the consolidator's template tags. Geographic/structural tags
        (district, consolidator) are preserved from the consolidator.
        """
        if not self._wms_ai:
            return

        # Build XML data block for the LLM
        localities_map = {
            loc["id"]: loc["name"]
            for loc in geo_context.get("localities", [])
        }
        district_name = geo_context.get("district_name", "Unknown District")
        data_block = consolidator.build_xml_data_block(
            l2_events, district_name, localities_map)

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type=f"layer3_{consolidator.consolidator_id}",
                event_subtype=consolidator.category,
                tags=result.affects_tags,
                data_block=data_block,
                layer=3,
            )

            if llm_result.success and llm_result.text:
                result.narrative = llm_result.text
                if llm_result.severity != "minor":
                    result.severity = llm_result.severity

                # Replace consolidator's template tags with LLM-assigned tags.
                # Keep structural tags (district:, consolidator:, scope:)
                # from the consolidator and add LLM interpretive tags.
                if llm_result.tags:
                    structural_prefixes = ("district:", "consolidator:",
                                           "scope:", "province:", "domain:")
                    structural = [t for t in result.affects_tags
                                  if any(t.startswith(p)
                                         for p in structural_prefixes)]
                    result.affects_tags = structural + llm_result.tags
                else:
                    print(f"[Layer3] WARNING: LLM returned no tags for "
                          f"L3 {consolidator.consolidator_id} — "
                          f"check prompt or LLM output format")

        except Exception as e:
            print(f"[Layer3] LLM upgrade failed for "
                  f"{consolidator.consolidator_id}: {e}")

    def _store_consolidation(self, result: ConsolidatedEvent,
                             game_time: float) -> None:
        """Store a ConsolidatedEvent in LayerStore layer3_events."""
        if not self._layer_store:
            return

        # Check for superseding — find existing L3 event with same
        # category and district
        existing_id = self._find_supersedable(result)
        if existing_id:
            result.supersedes_id = existing_id

        origin_ref = json.dumps(result.source_interpretation_ids)
        self._layer_store.insert_event(
            layer=3,
            narrative=result.narrative,
            game_time=game_time,
            category=result.category,
            severity=result.severity,
            significance=result.severity,
            tags=result.affects_tags,
            origin_ref=origin_ref,
            event_id=result.consolidation_id,
        )

        # Notify Layer 4 of the new L3 event
        if self._layer4_callback:
            try:
                l3_event_dict = {
                    "id": result.consolidation_id,
                    "narrative": result.narrative,
                    "category": result.category,
                    "severity": result.severity,
                    "tags": result.affects_tags,
                    "game_time": game_time,
                }
                self._layer4_callback(l3_event_dict)
            except Exception as e:
                print(f"[Layer3] Layer 4 callback error: {e}")

    def _find_supersedable(self, result: ConsolidatedEvent) -> Optional[str]:
        """Find an existing L3 event that this result supersedes.

        A consolidation supersedes a previous one with the same category
        and overlapping districts.
        """
        if not self._layer_store or not result.affected_district_ids:
            return None

        # Query existing L3 events with same category
        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer3_events WHERE category = ? "
            "ORDER BY game_time DESC LIMIT 10",
            (result.category,)
        ).fetchall()

        for row in rows:
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            for tag in tags:
                if tag.startswith("district:"):
                    existing_district = tag.split(":", 1)[1]
                    if existing_district in result.affected_district_ids:
                        return row["id"]

        return None

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "consolidators": len(self._consolidators),
            "consolidations_created": self._consolidations_created,
            "runs_completed": self._runs_completed,
            "l2_events_pending": self._l2_events_since_last_run,
            "districts_pending": len(self._districts_with_new_l2),
            "trigger_interval": self._trigger_interval,
            "last_run_game_time": self._last_run_game_time,
        }
