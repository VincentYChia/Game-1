"""Layer 6 Manager — orchestrates nation-level summarization from Layer 5.

Aggregation tier: **game Nation** (parent of game Region). Each
Layer 6 event consolidates Layer 5 events across the regions of a
single game Nation.

Trigger: Tag-weighted, **per-nation**. Each Layer 5 event is routed
to a nation-specific WeightedTriggerBucket based on its ``nation:X``
tag. Address tags (world/nation/region/province/district/locality)
are stripped before scoring so only content tags consume positional
weight:

    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1.

When any content tag crosses the threshold (default 150 points)
*within a nation*, it fires and all contributing L5 events become
context for that nation's summary.

Address tag drop rule:
    Layer 6 output tags include: world, nation.
    The `region:` tag is dropped at this layer because the
    consolidation is summed across every region in the nation, not
    a single region. `province:`, `district:`, `locality:` were
    already dropped at L5/L4/L3.

Data flow:
    Layer 5 event stored in LayerStore (layer5_events)
           ↓
    Layer6Manager.on_layer5_created()
      — extract nation_id directly from the event's `nation:` tag
        (address tags are facts, always present; no parent-chain walk)
      — strip all address tags before scoring
      — ingest content tags into per-nation WeightedTriggerBucket
           ↓ (content tag crosses threshold within nation → fires)
    Contributing L5 events become primary context
    Relevant L4 events (fired-tag overlap filter) become two-layers-down context
           ↓
    Layer6Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — rewrites ONLY content tags (address tags are
    re-attached by layer code after the LLM call)
           ↓
    Store in layer6_events + layer6_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 6 sees Layer 5 (full) and Layer 4 (filtered by fired-tag overlap).
    Layer 6 does NOT see Layer 3, Layer 2, Layer 1 stats, or Layer 7.

Pure WMS pipeline, address immutability:
    Layer 6 does NOT read FactionSystem, EcosystemAgent, or any other
    state tracker. Address tags are FACTS assigned at L2 capture; this
    layer never synthesizes or rewrites them. See
    docs/ARCHITECTURAL_DECISIONS.md §§4-6.
"""

from __future__ import annotations

import json
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import (
    NationSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES, is_address_tag, partition_address_and_content,
)
from world_system.world_memory.layer6_summarizer import Layer6Summarizer
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.trigger_registry import TriggerRegistry


# Per-nation bucket name prefix: "layer6_nation_{nation_id}"
BUCKET_PREFIX = "layer6_nation_"


class Layer6Manager:
    """Orchestrates Layer 6 nation summarization. Singleton.

    Uses WeightedTriggerBucket (one per game Nation) to score Layer 5
    events by tag position. When a content tag crosses the threshold
    within a nation, contributing L5 events + relevant L4 events are
    gathered and summarized into a NationSummaryEvent.
    """

    _instance: ClassVar[Optional["Layer6Manager"]] = None

    def __init__(self):
        self._summarizer: Layer6Summarizer = Layer6Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Per-nation bucket tracking (set of bucket names)
        self._nation_buckets: Set[str] = set()

        # Config
        self._trigger_threshold: int = 150
        self._max_l5_per_nation: int = 40
        self._max_l4_relevance: int = 8
        self._min_regions_contributing: int = 1  # optional quorum gate

        # Stats
        self._summaries_created: int = 0
        self._runs_completed: int = 0
        self._last_run_game_time: float = 0.0

        # Optional L7 callback hook (mirrors L5's L6 callback pattern)
        self._layer7_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    @classmethod
    def get_instance(cls) -> "Layer6Manager":
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
        """Wire dependencies and prepare per-nation trigger buckets.

        Args:
            layer_store: LayerStore for reading L5/L4 and writing L6.
            geo_registry: GeographicRegistry for nation→region walks.
            wms_ai: WmsAI for LLM narration (optional).
            trigger_registry: TriggerRegistry instance (optional).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        cfg = get_section("layer6")
        self._trigger_threshold = cfg.get("trigger_threshold", 150)
        self._max_l5_per_nation = cfg.get("max_l5_per_nation", 40)
        self._max_l4_relevance = cfg.get("max_l4_relevance", 8)
        self._min_regions_contributing = cfg.get(
            "min_regions_contributing", 1)

        # Per-nation buckets are created lazily in on_layer5_created().
        # Recover any existing nation buckets from a prior session.
        self._trigger_registry = (
            trigger_registry or TriggerRegistry.get_instance()
        )
        self._nation_buckets = set(
            self._trigger_registry.get_weighted_bucket_names(BUCKET_PREFIX)
        )

        self._initialized = True
        print(
            f"[Layer6] Initialized — per-nation weighted triggers, "
            f"threshold {self._trigger_threshold} points, "
            f"{len(self._nation_buckets)} existing nation buckets"
        )

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer5_created(self, l5_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 5 region summary is stored.

        Reads the ``nation:X`` tag directly off the event — address
        tags are FACTS assigned at capture, so this is a simple tag
        lookup with no parent-chain walking. Strips all address tags
        before ingesting content tags into the nation-specific
        WeightedTriggerBucket.
        """
        if not self._initialized or not self._trigger_registry:
            return

        event_id = l5_event_dict.get("id", "")
        tags = l5_event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        if not event_id or not tags:
            return

        # Resolve nation_id from the event's `nation:` tag. Address tags
        # are guaranteed facts — no fallback needed.
        nation_id = self._resolve_nation_id_from_tags(tags)
        if not nation_id:
            return

        # Strip all address tags so content tags get full positional
        # weight (e.g. domain:combat at position 0 = 10 pts).
        content_tags = [
            t for t in tags
            if not any(t.startswith(p) for p in ADDRESS_TAG_PREFIXES)
        ]
        if not content_tags:
            return

        bucket_name = f"{BUCKET_PREFIX}{nation_id}"
        if bucket_name not in self._nation_buckets:
            self._trigger_registry.register_weighted_bucket(
                bucket_name, threshold=self._trigger_threshold)
            self._nation_buckets.add(bucket_name)

        self._trigger_registry.ingest_event_weighted(
            bucket_name, event_id, content_tags)

    def should_run(self) -> bool:
        """Check if any content tag in any nation bucket has crossed threshold."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.any_weighted_fired_with_prefix(
            BUCKET_PREFIX)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all nation buckets that have fired.

        Each nation bucket fires independently when its content tags
        cross the threshold. Contributing event IDs are already scoped
        to the correct nation.

        Returns the number of Layer 6 summaries created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        all_fired = self._trigger_registry.pop_all_fired_weighted_with_prefix(
            BUCKET_PREFIX)
        if not all_fired:
            return 0

        created = 0
        for bucket_name, fired_tags_map in all_fired.items():
            nation_id = bucket_name[len(BUCKET_PREFIX):]

            # Collect all contributing L5 event IDs across all fired tags
            context_event_ids: Set[str] = set()
            for event_ids in fired_tags_map.values():
                context_event_ids.update(event_ids)

            # Fired tag set drives L4 filtering (two-layers-down visibility)
            fired_tag_set = set(fired_tags_map.keys())

            summary = self._summarize_nation(
                nation_id, context_event_ids, fired_tag_set, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(
                f"[Layer6] Summarization run #{self._runs_completed}: "
                f"{created} nation summaries from "
                f"{len(all_fired)} nation buckets"
            )

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _resolve_nation_id_from_tags(
        self, tags: List[str],
    ) -> Optional[str]:
        """Pull the game Nation ID from the event's `nation:` address tag.

        Address tags are assigned at L2 capture from chunk position and
        propagated unchanged by every higher layer, so a fact-level
        ``nation:X`` tag is always present on any L5 event whose
        underlying L2 events came from a real chunk. No parent-chain
        walking is needed.
        """
        for tag in tags:
            if tag.startswith("nation:"):
                return tag.split(":", 1)[1]
        return None

    def _summarize_nation(
        self,
        nation_id: str,
        context_event_ids: Set[str],
        fired_tag_set: Set[str],
        game_time: float,
    ) -> Optional[NationSummaryEvent]:
        """Produce a summary for one nation using contributing L5 + relevant L4."""
        # 1. Fetch L5 events for this nation — prioritize contributors
        l5_events = self._fetch_l5_events(nation_id, context_event_ids)
        if not l5_events:
            return None

        # 1b. Optional gate: minimum number of contributing regions
        if self._min_regions_contributing > 1:
            regions_seen = set()
            for e in l5_events:
                for t in e.get("tags", []):
                    if t.startswith("region:"):
                        regions_seen.add(t.split(":", 1)[1])
                        break
            if len(regions_seen) < self._min_regions_contributing:
                # Not enough region diversity — skip this firing.
                # Contributing events are NOT re-ingested; they are
                # voided (same as Layer 5 behavior on threshold crossing).
                return None

        # 2. Fetch L4 events (two-layers-down, fired-tag filtered)
        l4_events = self._query_relevant_l4(nation_id, fired_tag_set, l5_events)

        # 3. Build geographic context
        geo_context = self._build_geo_context(nation_id)

        # 4. Run summarizer
        summary = self._summarizer.summarize(
            l5_events=l5_events,
            l4_events=l4_events,
            nation_id=nation_id,
            geo_context=geo_context,
            game_time=game_time,
        )
        if summary is None:
            return None

        # 5. Upgrade narrative via LLM (content tag rewrite only)
        if self._wms_ai:
            self._upgrade_narrative(
                summary, l5_events, l4_events, geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner.
        #    The LLM rewrite path is reserved for CONTENT tags only —
        #    address tags (which the summarizer has already set
        #    correctly in summary.tags) are preserved by layer code.
        origin_tags = [e.get("tags", []) for e in l5_events]
        enriched = assign_higher_layer_tags(
            layer=6,
            origin_event_tags=origin_tags,
            significance=summary.severity,
            layer_specific_tags=summary.tags,
            rewrite_all=summary.tags if self._wms_ai else None,
        )
        summary.tags = enriched

        return summary

    def _fetch_l5_events(
        self, nation_id: str, context_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Fetch L5 events for the nation.

        Every L5 event carries a `nation:X` address tag, so we can
        query directly by that tag. No need to enumerate child
        regions first.
        """
        if not self._layer_store:
            return []

        rows = self._layer_store.query_by_tags(
            layer=5,
            tags=[f"nation:{nation_id}"],
            match_all=True,
            limit=self._max_l5_per_nation,
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
        return result[:self._max_l5_per_nation]

    def _query_relevant_l4(
        self,
        nation_id: str,
        fired_tag_set: Set[str],
        l5_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query L4 candidates across the nation and filter by fired tags.

        L4 events also carry a `nation:X` tag (propagated from L2
        capture), so we query directly.
        """
        if not self._layer_store:
            return []

        per_nation_limit = max(10, self._max_l4_relevance * 4)
        rows = self._layer_store.query_by_tags(
            layer=4,
            tags=[f"nation:{nation_id}"],
            match_all=True,
            limit=per_nation_limit,
        )
        if not rows:
            return []

        filtered = Layer6Summarizer.filter_relevant_l4(
            l4_candidates=rows,
            fired_tags=fired_tag_set,
            l5_events=l5_events,
        )
        return filtered[:self._max_l4_relevance]

    def _regions_in_nation(self, nation_id: str) -> List[str]:
        """List the game Region region_ids that are children of a Nation."""
        if not self._geo_registry:
            return []

        from world_system.world_memory.geographic_registry import RegionLevel

        nation = self._geo_registry.regions.get(nation_id)
        if nation is None or nation.level != RegionLevel.NATION:
            return []

        regions: List[str] = []
        for child_id in nation.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child and child.level == RegionLevel.REGION:
                regions.append(child.region_id)
        return regions

    def _build_geo_context(self, nation_id: str) -> Dict[str, Any]:
        """Build geographic context (nation name + list of game regions)."""
        if not self._geo_registry:
            return {"nation_name": nation_id, "regions": []}

        nation = self._geo_registry.regions.get(nation_id)
        if not nation:
            return {"nation_name": nation_id, "regions": []}

        regions = []
        for rid in self._regions_in_nation(nation_id):
            r = self._geo_registry.regions.get(rid)
            if r:
                regions.append({"id": rid, "name": r.name})

        return {
            "nation_name": nation.name,
            "regions": regions,
        }

    def _upgrade_narrative(
        self,
        summary: NationSummaryEvent,
        l5_events: List[Dict[str, Any]],
        l4_events: List[Dict[str, Any]],
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> None:
        """Replace template narrative with LLM-generated one.

        The LLM rewrites CONTENT tags only. Address tags
        (world/nation) are preserved by layer code — this method
        partitions ``summary.tags`` into address vs content halves,
        sends only the content half to the LLM, and then re-attaches
        the address half after the call returns. See
        docs/ARCHITECTURAL_DECISIONS.md §6.
        """
        if not self._wms_ai:
            return

        regions = geo_context.get("regions", [])
        nation_name = geo_context.get("nation_name", summary.nation_id)

        # Partition existing tags into address (preserved) vs content (LLM-rewritable)
        address_tags, content_tags = partition_address_and_content(summary.tags)

        data_block = self._summarizer.build_xml_data_block(
            l5_events, l4_events, nation_name, regions, game_time,
        )

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type="layer6_nation_summary",
                event_subtype="nation_summary",
                tags=content_tags,
                data_block=data_block,
                layer=6,
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
                        "[Layer6] WARNING: LLM returned no content tags for "
                        f"nation {summary.nation_id}; keeping template tags"
                    )

        except Exception as e:
            print(f"[Layer6] LLM upgrade failed for {summary.nation_id}: {e}")

    def _store_summary(
        self, summary: NationSummaryEvent, game_time: float,
    ) -> None:
        """Store a NationSummaryEvent in LayerStore layer6_events."""
        if not self._layer_store:
            return

        existing_id = self._find_supersedable(summary.nation_id)
        if existing_id:
            summary.supersedes_id = existing_id

        origin_ref = json.dumps(summary.source_region_summary_ids)
        self._layer_store.insert_event(
            layer=6,
            narrative=summary.narrative,
            game_time=game_time,
            category="nation_summary",
            severity=summary.severity,
            significance=summary.severity,
            tags=summary.tags,
            origin_ref=origin_ref,
            event_id=summary.summary_id,
        )

        # Notify Layer 7 of the new L6 event (future hook — L7 not
        # implemented yet). Same error-isolating pattern as
        # Layer4/Layer5 callbacks.
        if self._layer7_callback:
            try:
                l6_event_dict = {
                    "id": summary.summary_id,
                    "narrative": summary.narrative,
                    "category": "nation_summary",
                    "severity": summary.severity,
                    "tags": list(summary.tags),
                    "game_time": game_time,
                }
                self._layer7_callback(l6_event_dict)
            except Exception as e:
                print(f"[Layer6] Layer 7 callback error: {e}")

    def set_layer7_callback(self, callback) -> None:
        """Register a callback invoked when L6 events are stored.

        The callback receives the stored L6 event dict. Used by a
        future Layer7Manager to track per-world triggers. Not yet
        wired into the pipeline.
        """
        self._layer7_callback = callback

    def _find_supersedable(self, nation_id: str) -> Optional[str]:
        """Find an existing L6 summary for this nation to supersede."""
        if not self._layer_store:
            return None

        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer6_events "
            "WHERE category = 'nation_summary' "
            "ORDER BY game_time DESC LIMIT 10"
        ).fetchall()

        target = f"nation:{nation_id}"
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
            per_nation: Dict[str, Any] = {}
            for bucket_name in sorted(self._nation_buckets):
                bucket = self._trigger_registry.get_weighted_bucket(
                    bucket_name)
                if bucket:
                    nation_id = bucket_name[len(BUCKET_PREFIX):]
                    per_nation[nation_id] = {
                        "tags_tracked": len(bucket.tag_scores),
                        "tags_fired": len(bucket.fired_tags),
                    }
            trigger_info = {
                "nations_tracked": len(self._nation_buckets),
                "threshold": self._trigger_threshold,
                "per_nation": per_nation,
            }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
