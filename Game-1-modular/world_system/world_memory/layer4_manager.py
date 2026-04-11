"""Layer 4 Manager — orchestrates province-level summarization from Layer 3.

Trigger: Tag-weighted, **per-province**. Each Layer 3 event is routed to a
province-specific WeightedTriggerBucket based on its geographic address.
Geographic tags (province:, district:, locality:, nation:) are stripped before
scoring so only content tags consume positional weight:
    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1.

When any content tag crosses 50 points *within a province*, it fires and all
contributing L3 events become context for that province's summary.

Province scope: WMS PROVINCE = game Region (region_X). Each province
contains multiple districts (game provinces = province_X).

Data flow:
    Layer 3 event stored in LayerStore (layer3_events)
           ↓
    Layer4Manager.on_layer3_created()
      — extract province_id from event tags
      — strip geographic tags (province:, district:, locality:, nation:)
      — ingest content tags into per-province WeightedTriggerBucket
           ↓ (content tag crosses threshold within province → fires)
    Contributing L3 events become primary context
    Relevant L2 events (strict tag-position filter) become supporting context
           ↓
    Layer4Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — rewrite narrative + ALL tags (66-80% retention, reordered)
           ↓
    Store in layer4_events + layer4_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 4 sees Layer 3 (full) and Layer 2 (filtered — trigger tag in top 3).
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


# Per-province bucket name prefix: "layer4_province_{province_id}"
BUCKET_PREFIX = "layer4_province_"

# For L2 visibility: trigger tag must be in these top N positions
_L2_TAG_POSITION_CUTOFF = 3

# Geographic tag prefixes stripped before scoring — these are address tags,
# not content tags.  Stripping them ensures content tags get full positional
# weight (e.g. domain:combat moves from position 2 → 0 = 10 pts, not 6).
_GEO_TAG_PREFIXES = ("province:", "district:", "locality:", "nation:")


class Layer4Manager:
    """Orchestrates Layer 4 province summarization. Singleton.

    Uses WeightedTriggerBucket to score Layer 3 events by tag position.
    When a tag fires, contributing L3 events + relevant L2 events are
    gathered and summarized into a ProvinceSummaryEvent.
    """

    _instance: ClassVar[Optional[Layer4Manager]] = None

    def __init__(self):
        self._summarizer: Layer4Summarizer = Layer4Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Per-province bucket tracking (set of bucket names)
        self._province_buckets: Set[str] = set()

        # Config
        self._trigger_threshold: int = 50
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
        """Wire dependencies and register weighted trigger bucket.

        Args:
            layer_store: LayerStore for reading L3/L2 and writing L4.
            geo_registry: GeographicRegistry for province hierarchy.
            wms_ai: WmsAI for LLM narration (optional).
            trigger_registry: TriggerRegistry instance (optional).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        cfg = get_section("layer4")
        self._trigger_threshold = cfg.get("trigger_threshold", 50)
        self._max_l3_per_province = cfg.get("max_l3_per_province", 50)
        self._max_l2_relevance = cfg.get("max_l2_relevance", 15)

        # Per-province buckets created lazily in on_layer3_created().
        # Recover any existing province buckets from a prior session.
        self._trigger_registry = trigger_registry or TriggerRegistry.get_instance()
        self._province_buckets = set(
            self._trigger_registry.get_weighted_bucket_names(BUCKET_PREFIX)
        )

        self._initialized = True
        print(f"[Layer4] Initialized — per-province weighted triggers, "
              f"threshold {self._trigger_threshold} points, "
              f"{len(self._province_buckets)} existing province buckets")

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer3_created(self, l3_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 3 consolidation is stored.

        Extracts province_id from the event's tags, strips geographic
        address tags, and ingests content tags into the province-specific
        WeightedTriggerBucket.  Geographic tags are stripped so content
        tags receive full positional weight (position 0 = 10 pts).
        """
        if not self._initialized or not self._trigger_registry:
            return

        event_id = l3_event_dict.get("id", "")
        tags = l3_event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        if not event_id or not tags:
            return

        # Extract province_id(s) from tags — route to each province bucket
        province_ids = [
            t.split(":", 1)[1] for t in tags if t.startswith("province:")
        ]
        if not province_ids:
            return

        # Strip geographic address tags so content tags get full positional
        # weight (e.g. domain:combat at position 0 = 10 pts, not position 2 = 6)
        content_tags = [
            t for t in tags
            if not any(t.startswith(p) for p in _GEO_TAG_PREFIXES)
        ]
        if not content_tags:
            return

        # Ingest into each province's bucket (usually one, could span)
        for province_id in province_ids:
            bucket_name = f"{BUCKET_PREFIX}{province_id}"
            if bucket_name not in self._province_buckets:
                self._trigger_registry.register_weighted_bucket(
                    bucket_name, threshold=self._trigger_threshold)
                self._province_buckets.add(bucket_name)

            self._trigger_registry.ingest_event_weighted(
                bucket_name, event_id, content_tags)

    def should_run(self) -> bool:
        """Check if any content tag in any province bucket has crossed the threshold."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.any_weighted_fired_with_prefix(BUCKET_PREFIX)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all province buckets that have fired.

        Each province bucket fires independently when its content tags
        cross the threshold.  Contributing event IDs are already scoped
        to the correct province — no post-hoc grouping needed.

        Returns the number of Layer 4 summaries created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        # Pop fired tags from every province bucket at once
        all_fired = self._trigger_registry.pop_all_fired_weighted_with_prefix(
            BUCKET_PREFIX)
        if not all_fired:
            return 0

        created = 0
        for bucket_name, fired_tags in all_fired.items():
            province_id = bucket_name[len(BUCKET_PREFIX):]

            # Collect all contributing event IDs across all fired tags
            context_event_ids: Set[str] = set()
            for event_ids in fired_tags.values():
                context_event_ids.update(event_ids)

            summary = self._summarize_province(
                province_id, context_event_ids, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(f"[Layer4] Summarization run #{self._runs_completed}: "
                  f"{created} province summaries from "
                  f"{len(all_fired)} province buckets")

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _summarize_province(
        self, province_id: str, context_event_ids: Set[str],
        game_time: float,
    ) -> Optional[ProvinceSummaryEvent]:
        """Produce a summary for one province using context events."""
        # 1. Get the contributing L3 events (primary context)
        l3_events = self._fetch_l3_events(province_id, context_event_ids)
        if not l3_events:
            return None

        # 2. Get relevant L2 events (strict tag-position filter)
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

        # 5. Upgrade narrative via LLM (includes full tag rewrite)
        if self._wms_ai:
            self._upgrade_narrative(summary, l3_events, l2_events,
                                    geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner
        #    If LLM provided a rewrite, use the rewrite_all path
        origin_tags = [e.get("tags", []) for e in l3_events]
        enriched = assign_higher_layer_tags(
            layer=4,
            origin_event_tags=origin_tags,
            significance=summary.severity,
            layer_specific_tags=summary.tags,
            rewrite_all=summary.tags if self._wms_ai else None,
        )
        summary.tags = enriched

        return summary

    def _fetch_l3_events(
        self, province_id: str, context_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Fetch L3 events — prioritize contributing events, fill from province."""
        if not self._layer_store:
            return []

        # Start with all L3 events for this province
        all_l3 = self._layer_store.query_by_tags(
            layer=3,
            tags=[f"province:{province_id}"],
            match_all=True,
            limit=self._max_l3_per_province,
        )

        if not context_event_ids:
            return all_l3

        # Sort: contributing events first, then others
        contributors = []
        others = []
        for event in all_l3:
            if event.get("id") in context_event_ids:
                contributors.append(event)
            else:
                others.append(event)

        return contributors + others

    def _query_relevant_l2(
        self,
        province_id: str,
        l3_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query L2 events relevant to this province, using strict filtering.

        An L2 event is included only if the fired trigger tag appears in
        the L2 event's top 3 tag positions. This ensures only the most
        directly relevant L2 detail surfaces.
        """
        if not self._layer_store:
            return []

        # Collect content tags from L3 events (for matching)
        l3_content_tags: Set[str] = set()
        for event in l3_events:
            for tag in event.get("tags", []):
                if not tag.startswith(("significance:", "scope:",
                                       "consolidator:")):
                    l3_content_tags.add(tag)

        if not l3_content_tags:
            return []

        # Get L2 events in this province
        l2_candidates = self._layer_store.query_by_tags(
            layer=2,
            tags=[f"province:{province_id}"],
            match_all=True,
            limit=100,
        )

        # Strict filter: L3 content tag must appear in L2's top N positions
        relevant = []
        for event in l2_candidates:
            event_tags = event.get("tags", [])
            top_tags = set(event_tags[:_L2_TAG_POSITION_CUTOFF])
            if top_tags & l3_content_tags:
                relevant.append(event)

        # Sort by severity descending
        relevant.sort(
            key=lambda e: SEVERITY_ORDER.get(e.get("severity", "minor"), 0),
            reverse=True,
        )
        return relevant[:self._max_l2_relevance]

    def _build_geo_context(self, province_id: str) -> Dict[str, Any]:
        """Build geographic context for a province (WMS PROVINCE = game region)."""
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
        """Replace template narrative with LLM-generated one.

        At Layer 4, the LLM performs a FULL TAG REWRITE: it receives the
        aggregate inherited tags as input context and outputs a complete
        reordered tag list (keeping ~66-80% of aggregate tags, reordered
        by relevance to the narrative it generated).
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

                # Full tag rewrite: LLM output replaces ALL tags
                if llm_result.tags:
                    summary.tags = llm_result.tags
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

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        trigger_info: Dict[str, Any] = {}
        if self._trigger_registry:
            per_province: Dict[str, Any] = {}
            for bucket_name in sorted(self._province_buckets):
                bucket = self._trigger_registry.get_weighted_bucket(bucket_name)
                if bucket:
                    province_id = bucket_name[len(BUCKET_PREFIX):]
                    per_province[province_id] = {
                        "tags_tracked": len(bucket.tag_scores),
                        "tags_fired": len(bucket.fired_tags),
                    }
            trigger_info = {
                "provinces_tracked": len(self._province_buckets),
                "threshold": self._trigger_threshold,
                "per_province": per_province,
            }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
