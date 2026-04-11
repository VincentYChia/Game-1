"""Layer 4 Manager — orchestrates province-level summarization from Layer 3.

Trigger: Per-province. When a province accumulates N Layer 3 events (default 3),
the province summary is regenerated. Uses TriggerRegistry for centralized
per-key counter tracking.

Data flow:
    Layer 3 event stored in LayerStore (layer3_events)
           ↓
    Layer4Manager.on_layer3_created() — extract province tag, increment trigger
           ↓ (province reaches threshold)
    Query all L3 events for that province
    Query relevant L2 events (tag-match filtering)
           ↓
    Layer4Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — replace narrative + assign L4 tags (optional)
           ↓
    HigherLayerTagAssigner — enrich tags from L3 origins
           ↓
    Store in layer4_events + layer4_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 4 sees Layer 3 (full) and Layer 2 (filtered by tag overlap).
    Layer 4 does NOT see Layer 1 stats or Layers 5-7.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import (
    ProvinceSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.layer4_summarizer import Layer4Summarizer
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.trigger_registry import TriggerRegistry


# TriggerRegistry bucket name for Layer 4
BUCKET_NAME = "layer4_provinces"


class Layer4Manager:
    """Orchestrates Layer 4 province summarization. Singleton.

    Tracks Layer 3 event creation via TriggerRegistry per-province buckets.
    When a province fires, queries L3 + relevant L2 events and produces
    a ProvinceSummaryEvent.
    """

    _instance: ClassVar[Optional[Layer4Manager]] = None

    def __init__(self):
        self._summarizer: Layer4Summarizer = Layer4Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Config (loaded during initialize)
        self._trigger_threshold: int = 3
        self._max_l3_per_province: int = 50
        self._max_l2_relevance: int = 15

        # Stats
        self._summaries_created: int = 0
        self._runs_completed: int = 0
        self._last_run_game_time: float = 0.0

    @classmethod
    def get_instance(cls) -> Layer4Manager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, layer_store, geo_registry,
                   wms_ai=None,
                   trigger_registry: Optional[TriggerRegistry] = None) -> None:
        """Wire dependencies and register trigger bucket.

        Args:
            layer_store: LayerStore for reading L3/L2 and writing L4.
            geo_registry: GeographicRegistry for province hierarchy.
            wms_ai: WmsAI for LLM narration (optional, templates used as fallback).
            trigger_registry: TriggerRegistry instance (optional, creates default).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        # Load config
        cfg = get_section("layer4")
        self._trigger_threshold = cfg.get("trigger_threshold", 3)
        self._max_l3_per_province = cfg.get("max_l3_per_province", 50)
        self._max_l2_relevance = cfg.get("max_l2_relevance", 15)

        # Register trigger bucket
        self._trigger_registry = trigger_registry or TriggerRegistry.get_instance()
        self._trigger_registry.register_bucket(
            BUCKET_NAME, threshold=self._trigger_threshold,
        )

        self._initialized = True
        print(f"[Layer4] Initialized — threshold {self._trigger_threshold} "
              f"L3 events per province")

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer3_created(self, l3_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 3 consolidation is stored.

        Extracts the province tag from the event and increments the
        per-province trigger counter. When a province reaches the
        threshold, it will be processed on the next should_run() check.

        Args:
            l3_event_dict: The Layer 3 event as stored in LayerStore.
        """
        if not self._initialized or not self._trigger_registry:
            return

        province_id = self._extract_province(l3_event_dict)
        if province_id:
            self._trigger_registry.increment(BUCKET_NAME, province_id)

    def should_run(self) -> bool:
        """Check if any province has accumulated enough L3 events."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.has_fired(BUCKET_NAME)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all provinces that have fired.

        Returns the number of Layer 4 summaries created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        # Get all provinces that have fired and reset their counters
        fired_provinces = self._trigger_registry.get_and_clear_fired(BUCKET_NAME)
        if not fired_provinces:
            return 0

        created = 0
        for province_id in fired_provinces:
            summary = self._summarize_province(province_id, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(f"[Layer4] Summarization run #{self._runs_completed}: "
                  f"{created} province summaries created "
                  f"({len(fired_provinces)} provinces processed)")

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _summarize_province(
        self, province_id: str, game_time: float,
    ) -> Optional[ProvinceSummaryEvent]:
        """Produce a summary for one province."""
        # 1. Query L3 events for this province
        l3_events = self._query_l3_for_province(province_id)
        if not l3_events:
            return None

        # 2. Query relevant L2 events (filtered by tag overlap)
        l2_events = self._query_relevant_l2(province_id, l3_events)

        # 3. Build geographic context
        geo_context = self._build_geo_context(province_id)

        # 4. Run summarizer
        summary = self._summarizer.summarize(
            l3_events=l3_events,
            l2_events=l2_events,
            province_id=province_id,
            geo_context=geo_context,
            game_time=game_time,
        )
        if summary is None:
            return None

        # 5. Upgrade narrative via LLM if available
        if self._wms_ai:
            self._upgrade_narrative(summary, l3_events, l2_events,
                                    geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner
        origin_tags = [e.get("tags", []) for e in l3_events]
        enriched = assign_higher_layer_tags(
            layer=4,
            origin_event_tags=origin_tags,
            significance=summary.severity,
            layer_specific_tags=summary.tags,
        )
        summary.tags = enriched

        return summary

    def _query_l3_for_province(
        self, province_id: str,
    ) -> List[Dict[str, Any]]:
        """Query all Layer 3 events tagged with this province."""
        if not self._layer_store:
            return []
        return self._layer_store.query_by_tags(
            layer=3,
            tags=[f"province:{province_id}"],
            match_all=True,
            limit=self._max_l3_per_province,
        )

    def _query_relevant_l2(
        self,
        province_id: str,
        l3_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query Layer 2 events relevant to this province's L3 events.

        Returns L2 events that share content tags with the L3 input,
        capped by config.
        """
        if not self._layer_store:
            return []

        # Get all L2 events for this province (broader pool)
        l2_candidates = self._layer_store.query_by_tags(
            layer=2,
            tags=[f"province:{province_id}"],
            match_all=True,
            limit=100,
        )

        # Filter by tag relevance
        relevant = Layer4Summarizer.filter_relevant_l2(l2_candidates, l3_events)
        return relevant[:self._max_l2_relevance]

    def _build_geo_context(self, province_id: str) -> Dict[str, Any]:
        """Build geographic context for a province."""
        if not self._geo_registry:
            return {"province_name": province_id, "districts": []}

        province = self._geo_registry.regions.get(province_id)
        if not province:
            return {"province_name": province_id, "districts": []}

        # Get child districts
        districts = []
        for child_id in province.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child:
                districts.append({"id": child_id, "name": child.name})

        return {
            "province_name": province.name,
            "districts": districts,
        }

    def _upgrade_narrative(
        self,
        summary: ProvinceSummaryEvent,
        l3_events: List[Dict[str, Any]],
        l2_events: List[Dict[str, Any]],
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> None:
        """Replace template narrative and tags with LLM-generated ones.

        The LLM returns JSON with 'narrative', 'tags', and optionally
        'dominant_activities' and 'threat_level' fields. LLM-assigned
        interpretive tags replace the summarizer's template tags.
        Structural tags (province, scope, domain) are preserved.
        """
        if not self._wms_ai:
            return

        districts = geo_context.get("districts", [])
        province_name = geo_context.get("province_name", summary.province_id)

        data_block = self._summarizer.build_xml_data_block(
            l3_events, l2_events, province_name, districts, game_time,
        )

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type="layer4_province_summary",
                event_subtype="province_summary",
                tags=summary.tags,
                data_block=data_block,
                layer=4,
            )

            if llm_result.success and llm_result.text:
                summary.narrative = llm_result.text
                if llm_result.severity != "minor":
                    summary.severity = llm_result.severity

                # Replace template tags with LLM interpretive tags
                if llm_result.tags:
                    structural_prefixes = (
                        "province:", "scope:", "domain:", "threat_level:",
                    )
                    structural = [
                        t for t in summary.tags
                        if any(t.startswith(p) for p in structural_prefixes)
                    ]
                    summary.tags = structural + llm_result.tags
                else:
                    print("[Layer4] WARNING: LLM returned no tags for "
                          f"province {summary.province_id}")

        except Exception as e:
            print(f"[Layer4] LLM upgrade failed for {summary.province_id}: {e}")

    def _store_summary(self, summary: ProvinceSummaryEvent,
                       game_time: float) -> None:
        """Store a ProvinceSummaryEvent in LayerStore layer4_events."""
        if not self._layer_store:
            return

        # Find and supersede previous summary for this province
        existing_id = self._find_supersedable(summary.province_id)
        if existing_id:
            summary.supersedes_id = existing_id

        origin_ref = json.dumps(summary.source_consolidation_ids)
        self._layer_store.insert_event(
            layer=4,
            narrative=summary.narrative,
            game_time=game_time,
            category="province_summary",
            severity=summary.severity,
            significance=summary.severity,
            tags=summary.tags,
            origin_ref=origin_ref,
            event_id=summary.summary_id,
        )

    def _find_supersedable(self, province_id: str) -> Optional[str]:
        """Find an existing L4 summary for this province to supersede."""
        if not self._layer_store:
            return None

        # Query existing L4 events with province_summary category
        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer4_events "
            "WHERE category = 'province_summary' "
            "ORDER BY game_time DESC LIMIT 10"
        ).fetchall()

        for row in rows:
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            for tag in tags:
                if tag == f"province:{province_id}":
                    return row["id"]

        return None

    def _extract_province(self, event_dict: Dict[str, Any]) -> Optional[str]:
        """Extract province_id from an event's tags."""
        tags = event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        for tag in tags:
            if isinstance(tag, str) and tag.startswith("province:"):
                return tag.split(":", 1)[1]

        return None

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        trigger_info = {}
        if self._trigger_registry:
            bucket = self._trigger_registry.get_bucket(BUCKET_NAME)
            if bucket:
                trigger_info = {
                    "provinces_tracked": len(bucket.counters),
                    "provinces_pending": len(bucket.fired),
                    "threshold": bucket.threshold,
                }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
