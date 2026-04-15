"""Layer 5 Manager — orchestrates region-level summarization from Layer 4.

Aggregation tier: **game Region** (parent of game Province). Each
Layer 5 event consolidates Layer 4 events across the provinces of a
single game Region.

Trigger: Tag-weighted, **per-region**. Each Layer 4 event is routed to
a region-specific WeightedTriggerBucket based on its ``region:X`` tag.
Address tags (world/nation/region/province/district/locality) are
stripped before scoring so only content tags consume positional weight:

    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1.

When any content tag crosses the threshold (default 100 points) *within
a region*, it fires and all contributing L4 events become context for
that region's summary.

Address tag drop rule:
    Layer 5 output tags include: world, nation, region.
    The `province:` tag is dropped at this layer because the
    consolidation is summed across every province in the region, not
    a single province. `district:` and `locality:` tags are also
    dropped (they were already dropped at L4/L3).

Data flow:
    Layer 4 event stored in LayerStore (layer4_events)
           ↓
    Layer5Manager.on_layer4_created()
      — extract region_id directly from the event's `region:` tag
        (address tags are facts, always present; no parent-chain walk)
      — strip all address tags before scoring
      — ingest content tags into per-region WeightedTriggerBucket
           ↓ (content tag crosses threshold within region → fires)
    Contributing L4 events become primary context
    Relevant L3 events (fired-tag overlap filter) become two-layers-down context
           ↓
    Layer5Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — rewrites ONLY content tags (address tags are
    re-attached by layer code after the LLM call)
           ↓
    Store in layer5_events + layer5_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 5 sees Layer 4 (full) and Layer 3 (filtered by fired-tag overlap).
    Layer 5 does NOT see Layer 2, Layer 1 stats, or Layers 6-7.

Pure WMS pipeline, address immutability:
    Layer 5 does NOT read FactionSystem, EcosystemAgent, or any other
    state tracker. Address tags are FACTS assigned at L2 capture; this
    layer never synthesizes or rewrites them. See
    docs/ARCHITECTURAL_DECISIONS.md §§4-5.
"""

from __future__ import annotations

import json
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import (
    RegionSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES, is_address_tag, partition_address_and_content,
)
from world_system.world_memory.layer5_summarizer import Layer5Summarizer
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.trigger_registry import TriggerRegistry


# Per-region bucket name prefix: "layer5_region_{region_id}"
BUCKET_PREFIX = "layer5_region_"


class Layer5Manager:
    """Orchestrates Layer 5 region summarization. Singleton.

    Uses WeightedTriggerBucket (one per game Region) to score Layer 4
    events by tag position. When a content tag crosses the threshold
    within a region, contributing L4 events + relevant L3 events are
    gathered and summarized into a RegionSummaryEvent.
    """

    _instance: ClassVar[Optional["Layer5Manager"]] = None

    def __init__(self):
        self._summarizer: Layer5Summarizer = Layer5Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Per-region bucket tracking (set of bucket names)
        self._region_buckets: Set[str] = set()

        # Config
        self._trigger_threshold: int = 100
        self._max_l4_per_region: int = 50
        self._max_l3_relevance: int = 8
        self._min_provinces_contributing: int = 1  # optional quorum gate

        # Stats
        self._summaries_created: int = 0
        self._runs_completed: int = 0
        self._last_run_game_time: float = 0.0

    @classmethod
    def get_instance(cls) -> "Layer5Manager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(
        self,
        layer_store,
        geo_registry,
        wms_ai=None,
        trigger_registry: Optional[TriggerRegistry] = None,
    ) -> None:
        """Wire dependencies and prepare per-region trigger buckets.

        Args:
            layer_store: LayerStore for reading L4/L3 and writing L5.
            geo_registry: GeographicRegistry for region→province walks.
            wms_ai: WmsAI for LLM narration (optional).
            trigger_registry: TriggerRegistry instance (optional).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        cfg = get_section("layer5")
        self._trigger_threshold = cfg.get("trigger_threshold", 100)
        self._max_l4_per_region = cfg.get(
            "max_l4_per_region",
            cfg.get("max_l4_per_realm", 50),  # backwards-compat key
        )
        self._max_l3_relevance = cfg.get("max_l3_relevance", 8)
        self._min_provinces_contributing = cfg.get(
            "min_provinces_contributing", 1)

        # Per-region buckets are created lazily in on_layer4_created().
        # Recover any existing region buckets from a prior session.
        self._trigger_registry = (
            trigger_registry or TriggerRegistry.get_instance()
        )
        self._region_buckets = set(
            self._trigger_registry.get_weighted_bucket_names(BUCKET_PREFIX)
        )

        self._initialized = True
        print(
            f"[Layer5] Initialized — per-region weighted triggers, "
            f"threshold {self._trigger_threshold} points, "
            f"{len(self._region_buckets)} existing region buckets"
        )

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer4_created(self, l4_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 4 province summary is stored.

        Reads the ``region:X`` tag directly off the event — address
        tags are FACTS assigned at capture, so this is a simple tag
        lookup with no parent-chain walking. Strips all address tags
        before ingesting content tags into the region-specific
        WeightedTriggerBucket.
        """
        if not self._initialized or not self._trigger_registry:
            return

        event_id = l4_event_dict.get("id", "")
        tags = l4_event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        if not event_id or not tags:
            return

        # Resolve region_id from the event's `region:` tag. Address tags
        # are guaranteed facts — no fallback needed.
        region_id = self._resolve_region_id_from_tags(tags)
        if not region_id:
            return

        # Strip all address tags so content tags get full positional
        # weight (e.g. domain:combat at position 0 = 10 pts).
        content_tags = [
            t for t in tags
            if not any(t.startswith(p) for p in ADDRESS_TAG_PREFIXES)
        ]
        if not content_tags:
            return

        bucket_name = f"{BUCKET_PREFIX}{region_id}"
        if bucket_name not in self._region_buckets:
            self._trigger_registry.register_weighted_bucket(
                bucket_name, threshold=self._trigger_threshold)
            self._region_buckets.add(bucket_name)

        self._trigger_registry.ingest_event_weighted(
            bucket_name, event_id, content_tags)

    def should_run(self) -> bool:
        """Check if any content tag in any region bucket has crossed threshold."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.any_weighted_fired_with_prefix(
            BUCKET_PREFIX)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all region buckets that have fired.

        Each region bucket fires independently when its content tags
        cross the threshold. Contributing event IDs are already scoped
        to the correct region.

        Returns the number of Layer 5 summaries created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        all_fired = self._trigger_registry.pop_all_fired_weighted_with_prefix(
            BUCKET_PREFIX)
        if not all_fired:
            return 0

        created = 0
        for bucket_name, fired_tags_map in all_fired.items():
            region_id = bucket_name[len(BUCKET_PREFIX):]

            # Collect all contributing L4 event IDs across all fired tags
            context_event_ids: Set[str] = set()
            for event_ids in fired_tags_map.values():
                context_event_ids.update(event_ids)

            # Fired tag set drives L3 filtering (two-layers-down visibility)
            fired_tag_set = set(fired_tags_map.keys())

            summary = self._summarize_region(
                region_id, context_event_ids, fired_tag_set, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(
                f"[Layer5] Summarization run #{self._runs_completed}: "
                f"{created} region summaries from "
                f"{len(all_fired)} region buckets"
            )

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _resolve_region_id_from_tags(
        self, tags: List[str],
    ) -> Optional[str]:
        """Pull the game Region ID from the event's `region:` address tag.

        Address tags are assigned at L2 capture from chunk position and
        propagated unchanged by every higher layer, so a fact-level
        ``region:X`` tag is always present on any L4 event whose
        underlying L2 events came from a real chunk. No parent-chain
        walking is needed.
        """
        for tag in tags:
            if tag.startswith("region:"):
                return tag.split(":", 1)[1]
        return None

    def _summarize_region(
        self,
        region_id: str,
        context_event_ids: Set[str],
        fired_tag_set: Set[str],
        game_time: float,
    ) -> Optional[RegionSummaryEvent]:
        """Produce a summary for one region using contributing L4 + relevant L3."""
        # 1. Fetch L4 events for this region — prioritize contributors
        l4_events = self._fetch_l4_events(region_id, context_event_ids)
        if not l4_events:
            return None

        # 1b. Optional gate: minimum number of contributing provinces
        if self._min_provinces_contributing > 1:
            provinces_seen = set()
            for e in l4_events:
                for t in e.get("tags", []):
                    if t.startswith("province:"):
                        provinces_seen.add(t.split(":", 1)[1])
                        break
            if len(provinces_seen) < self._min_provinces_contributing:
                # Not enough province diversity — skip this firing.
                # Contributing events are NOT re-ingested; they are
                # voided (same as Layer 4 behavior on threshold crossing).
                return None

        # 2. Fetch L3 events (two-layers-down, fired-tag filtered)
        l3_events = self._query_relevant_l3(region_id, fired_tag_set, l4_events)

        # 3. Build geographic context
        geo_context = self._build_geo_context(region_id)

        # 4. Run summarizer
        summary = self._summarizer.summarize(
            l4_events=l4_events,
            l3_events=l3_events,
            region_id=region_id,
            geo_context=geo_context,
            game_time=game_time,
        )
        if summary is None:
            return None

        # 5. Upgrade narrative via LLM (content tag rewrite only)
        if self._wms_ai:
            self._upgrade_narrative(
                summary, l4_events, l3_events, geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner.
        #    The LLM rewrite path is reserved for CONTENT tags only —
        #    address tags (which the summarizer has already set
        #    correctly in summary.tags) are preserved by layer code.
        origin_tags = [e.get("tags", []) for e in l4_events]
        enriched = assign_higher_layer_tags(
            layer=5,
            origin_event_tags=origin_tags,
            significance=summary.severity,
            layer_specific_tags=summary.tags,
            rewrite_all=summary.tags if self._wms_ai else None,
        )
        summary.tags = enriched

        return summary

    def _fetch_l4_events(
        self, region_id: str, context_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Fetch L4 events for the region.

        Every L4 event carries a `region:X` address tag, so we can
        query directly by that tag. No need to enumerate child
        provinces first.
        """
        if not self._layer_store:
            return []

        rows = self._layer_store.query_by_tags(
            layer=4,
            tags=[f"region:{region_id}"],
            match_all=True,
            limit=self._max_l4_per_region,
        )
        if not rows:
            return []

        # Sort: contributors first, then by recency.
        contributors, others = [], []
        for event in rows:
            if event.get("id") in context_event_ids:
                contributors.append(event)
            else:
                others.append(event)

        contributors.sort(key=lambda e: e.get("game_time", 0.0), reverse=True)
        others.sort(key=lambda e: e.get("game_time", 0.0), reverse=True)

        result = contributors + others
        return result[:self._max_l4_per_region]

    def _query_relevant_l3(
        self,
        region_id: str,
        fired_tag_set: Set[str],
        l4_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query L3 candidates across the region and filter by fired tags.

        L3 events also carry a `region:X` tag (propagated from L2
        capture), so we query directly.
        """
        if not self._layer_store:
            return []

        per_region_limit = max(10, self._max_l3_relevance * 4)
        rows = self._layer_store.query_by_tags(
            layer=3,
            tags=[f"region:{region_id}"],
            match_all=True,
            limit=per_region_limit,
        )
        if not rows:
            return []

        filtered = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=rows,
            fired_tags=fired_tag_set,
            l4_events=l4_events,
        )
        return filtered[:self._max_l3_relevance]

    def _provinces_in_region(self, region_id: str) -> List[str]:
        """List the game Province region_ids that are children of a Region."""
        if not self._geo_registry:
            return []

        from world_system.world_memory.geographic_registry import RegionLevel

        region = self._geo_registry.regions.get(region_id)
        if region is None or region.level != RegionLevel.REGION:
            return []

        provinces: List[str] = []
        for child_id in region.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child and child.level == RegionLevel.PROVINCE:
                provinces.append(child.region_id)
        return provinces

    def _build_geo_context(self, region_id: str) -> Dict[str, Any]:
        """Build geographic context (region name + list of game provinces)."""
        if not self._geo_registry:
            return {"region_name": region_id, "provinces": []}

        region = self._geo_registry.regions.get(region_id)
        if not region:
            return {"region_name": region_id, "provinces": []}

        provinces = []
        for pid in self._provinces_in_region(region_id):
            p = self._geo_registry.regions.get(pid)
            if p:
                provinces.append({"id": pid, "name": p.name})

        return {
            "region_name": region.name,
            "provinces": provinces,
        }

    def _upgrade_narrative(
        self,
        summary: RegionSummaryEvent,
        l4_events: List[Dict[str, Any]],
        l3_events: List[Dict[str, Any]],
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> None:
        """Replace template narrative with LLM-generated one.

        The LLM rewrites CONTENT tags only. Address tags
        (world/nation/region) are preserved by layer code — this
        method partitions ``summary.tags`` into address vs content
        halves, sends only the content half to the LLM, and then
        re-attaches the address half after the call returns. See
        docs/ARCHITECTURAL_DECISIONS.md.
        """
        if not self._wms_ai:
            return

        provinces = geo_context.get("provinces", [])
        region_name = geo_context.get("region_name", summary.region_id)

        # Partition existing tags into address (preserved) vs content (LLM-rewritable)
        address_tags, content_tags = partition_address_and_content(summary.tags)

        data_block = self._summarizer.build_xml_data_block(
            l4_events, l3_events, region_name, provinces, game_time,
        )

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type="layer5_region_summary",
                event_subtype="region_summary",
                tags=content_tags,
                data_block=data_block,
                layer=5,
            )

            if llm_result.success and llm_result.text:
                summary.narrative = llm_result.text
                if llm_result.severity != "minor":
                    summary.severity = llm_result.severity

                # LLM rewrites content tags only; address tags are re-
                # attached from the pre-call snapshot. Any address tag
                # the LLM invented is dropped.
                llm_tags = llm_result.tags or []
                llm_content = [t for t in llm_tags if not is_address_tag(t)]
                if llm_content:
                    summary.tags = address_tags + llm_content
                else:
                    print(
                        "[Layer5] WARNING: LLM returned no content tags for "
                        f"region {summary.region_id}; keeping template tags"
                    )

        except Exception as e:
            print(f"[Layer5] LLM upgrade failed for {summary.region_id}: {e}")

    def _store_summary(
        self, summary: RegionSummaryEvent, game_time: float,
    ) -> None:
        """Store a RegionSummaryEvent in LayerStore layer5_events."""
        if not self._layer_store:
            return

        existing_id = self._find_supersedable(summary.region_id)
        if existing_id:
            summary.supersedes_id = existing_id

        origin_ref = json.dumps(summary.source_province_summary_ids)
        self._layer_store.insert_event(
            layer=5,
            narrative=summary.narrative,
            game_time=game_time,
            category="region_summary",
            severity=summary.severity,
            significance=summary.severity,
            tags=summary.tags,
            origin_ref=origin_ref,
            event_id=summary.summary_id,
        )

    def _find_supersedable(self, region_id: str) -> Optional[str]:
        """Find an existing L5 summary for this region to supersede."""
        if not self._layer_store:
            return None

        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer5_events "
            "WHERE category = 'region_summary' "
            "ORDER BY game_time DESC LIMIT 10"
        ).fetchall()

        target = f"region:{region_id}"
        for row in rows:
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            if target in tags:
                return row["id"]
        return None

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        trigger_info: Dict[str, Any] = {}
        if self._trigger_registry:
            per_region: Dict[str, Any] = {}
            for bucket_name in sorted(self._region_buckets):
                bucket = self._trigger_registry.get_weighted_bucket(
                    bucket_name)
                if bucket:
                    region_id = bucket_name[len(BUCKET_PREFIX):]
                    per_region[region_id] = {
                        "tags_tracked": len(bucket.tag_scores),
                        "tags_fired": len(bucket.fired_tags),
                    }
            trigger_info = {
                "regions_tracked": len(self._region_buckets),
                "threshold": self._trigger_threshold,
                "per_region": per_region,
            }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
