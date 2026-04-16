"""Layer 7 Manager — orchestrates world-level summarization from Layer 6.

Aggregation tier: **game World** (singleton, always ``world_0``). Each
Layer 7 event consolidates Layer 6 events across all nations in the
single game World.

Trigger: Tag-weighted, **per-world** (single bucket). Each Layer 6
event is routed to the world-scoped WeightedTriggerBucket based on its
``world:X`` tag. Address tags (world/nation/region/province/district/
locality) are stripped before scoring so only content tags consume
positional weight:

    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1.

When any content tag crosses the threshold (default 200 points)
*within the world*, it fires and all contributing L6 events become
context for the world summary.

Address tag drop rule:
    Layer 7 output tags include: world only.
    The `nation:` tag is dropped at this layer because the
    consolidation is summed across every nation in the world.
    `region:`, `province:`, `district:`, `locality:` were already
    dropped at L6/L5/L4/L3.

Data flow:
    Layer 6 event stored in LayerStore (layer6_events)
           ↓
    Layer7Manager.on_layer6_created()
      — extract world_id directly from the event's `world:` tag
        (address tags are facts, always present; no parent-chain walk)
      — strip all address tags before scoring
      — ingest content tags into per-world WeightedTriggerBucket
           ↓ (content tag crosses threshold within world → fires)
    Contributing L6 events become primary context
    Relevant L5 events (fired-tag overlap filter) become two-layers-down context
           ↓
    Layer7Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — rewrites ONLY content tags (address tags are
    re-attached by layer code after the LLM call)
           ↓
    Store in layer7_events + layer7_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 7 sees Layer 6 (full) and Layer 5 (filtered by fired-tag overlap).
    Layer 7 does NOT see Layer 4, Layer 3, Layer 2, Layer 1 stats.

No callback beyond Layer 7:
    This is the FINAL aggregation tier. There is no Layer 8 callback.
    The ``_layer7_callback`` pattern in Layer6Manager is NOT mirrored
    here.

Pure WMS pipeline, address immutability:
    Layer 7 does NOT read FactionSystem, EcosystemAgent, or any other
    state tracker. Address tags are FACTS assigned at L2 capture; this
    layer never synthesizes or rewrites them. See
    docs/ARCHITECTURAL_DECISIONS.md §§4-6.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import (
    WorldSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES, is_address_tag, partition_address_and_content,
)
from world_system.world_memory.layer7_summarizer import Layer7Summarizer
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.trigger_registry import TriggerRegistry


# Per-world bucket name prefix: "layer7_world_{world_id}"
# The game has exactly one world so this produces "layer7_world_world_0".
BUCKET_PREFIX = "layer7_world_"


class Layer7Manager:
    """Orchestrates Layer 7 world summarization. Singleton.

    Uses a single WeightedTriggerBucket (named ``layer7_world_world_0``)
    to score Layer 6 events by tag position. When a content tag crosses
    the threshold, contributing L6 events + relevant L5 events are
    gathered and summarized into a WorldSummaryEvent.

    This is the final aggregation tier — no Layer 8 callback exists.
    """

    _instance: ClassVar[Optional["Layer7Manager"]] = None

    def __init__(self):
        self._summarizer: Layer7Summarizer = Layer7Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Per-world bucket tracking (set of bucket names)
        self._world_buckets: Set[str] = set()

        # Config
        self._trigger_threshold: int = 200
        self._max_l6_per_world: int = 20
        self._max_l5_relevance: int = 8

        # Stats
        self._summaries_created: int = 0
        self._runs_completed: int = 0
        self._last_run_game_time: float = 0.0

    @classmethod
    def get_instance(cls) -> "Layer7Manager":
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
        """Wire dependencies and prepare per-world trigger bucket.

        Args:
            layer_store: LayerStore for reading L6/L5 and writing L7.
            geo_registry: GeographicRegistry for world→nation walks.
            wms_ai: WmsAI for LLM narration (optional).
            trigger_registry: TriggerRegistry instance (optional).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        cfg = get_section("layer7")
        self._trigger_threshold = cfg.get("trigger_threshold", 200)
        self._max_l6_per_world = cfg.get("max_l6_per_world", 20)
        self._max_l5_relevance = cfg.get("max_l5_relevance", 8)

        # Per-world bucket is created lazily in on_layer6_created().
        # Recover any existing world bucket from a prior session.
        self._trigger_registry = (
            trigger_registry or TriggerRegistry.get_instance()
        )
        self._world_buckets = set(
            self._trigger_registry.get_weighted_bucket_names(BUCKET_PREFIX)
        )

        self._initialized = True
        print(
            f"[Layer7] Initialized — per-world weighted trigger, "
            f"threshold {self._trigger_threshold} points, "
            f"{len(self._world_buckets)} existing world buckets"
        )

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer6_created(self, l6_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 6 nation summary is stored.

        Reads the ``world:X`` tag directly off the event — address
        tags are FACTS assigned at capture, so this is a simple tag
        lookup with no parent-chain walking. Strips all address tags
        before ingesting content tags into the world-specific
        WeightedTriggerBucket.
        """
        if not self._initialized or not self._trigger_registry:
            return

        event_id = l6_event_dict.get("id", "")
        tags = l6_event_dict.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        if not event_id or not tags:
            return

        # Resolve world_id from the event's `world:` tag. Address tags
        # are guaranteed facts — no fallback needed.
        world_id = self._resolve_world_id_from_tags(tags)
        if not world_id:
            return

        # Strip all address tags so content tags get full positional
        # weight (e.g. domain:combat at position 0 = 10 pts).
        content_tags = [
            t for t in tags
            if not any(t.startswith(p) for p in ADDRESS_TAG_PREFIXES)
        ]
        if not content_tags:
            return

        bucket_name = f"{BUCKET_PREFIX}{world_id}"
        if bucket_name not in self._world_buckets:
            self._trigger_registry.register_weighted_bucket(
                bucket_name, threshold=self._trigger_threshold)
            self._world_buckets.add(bucket_name)

        self._trigger_registry.ingest_event_weighted(
            bucket_name, event_id, content_tags)

    def should_run(self) -> bool:
        """Check if any content tag in the world bucket has crossed threshold."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.any_weighted_fired_with_prefix(
            BUCKET_PREFIX)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all world buckets that have fired.

        In practice there is only one world bucket (``world_0``). The
        loop mirrors the Layer 6 pattern for architectural consistency.

        Returns the number of Layer 7 summaries created.
        """
        if not self._initialized or not self._layer_store:
            return 0

        all_fired = self._trigger_registry.pop_all_fired_weighted_with_prefix(
            BUCKET_PREFIX)
        if not all_fired:
            return 0

        created = 0
        for bucket_name, fired_tags_map in all_fired.items():
            world_id = bucket_name[len(BUCKET_PREFIX):]

            # Collect all contributing L6 event IDs across all fired tags
            context_event_ids: Set[str] = set()
            for event_ids in fired_tags_map.values():
                context_event_ids.update(event_ids)

            # Fired tag set drives L5 filtering (two-layers-down visibility)
            fired_tag_set = set(fired_tags_map.keys())

            summary = self._summarize_world(
                world_id, context_event_ids, fired_tag_set, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(
                f"[Layer7] Summarization run #{self._runs_completed}: "
                f"{created} world summaries from "
                f"{len(all_fired)} world buckets"
            )

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _resolve_world_id_from_tags(
        self, tags: List[str],
    ) -> Optional[str]:
        """Pull the game World ID from the event's `world:` address tag.

        Address tags are assigned at L2 capture from chunk position and
        propagated unchanged by every higher layer, so a fact-level
        ``world:X`` tag is always present on any L6 event. For the
        current game this always resolves to ``world_0``.
        """
        for tag in tags:
            if tag.startswith("world:"):
                return tag.split(":", 1)[1]
        return None

    def _summarize_world(
        self,
        world_id: str,
        context_event_ids: Set[str],
        fired_tag_set: Set[str],
        game_time: float,
    ) -> Optional[WorldSummaryEvent]:
        """Produce a summary for the world using contributing L6 + relevant L5."""
        # 1. Fetch L6 events for this world — prioritize contributors
        l6_events = self._fetch_l6_events(world_id, context_event_ids)
        if not l6_events:
            return None

        # 2. Fetch L5 events (two-layers-down, fired-tag filtered)
        l5_events = self._query_relevant_l5(world_id, fired_tag_set, l6_events)

        # 3. Build geographic context
        geo_context = self._build_geo_context(world_id)

        # 4. Run summarizer
        summary = self._summarizer.summarize(
            l6_events=l6_events,
            l5_events=l5_events,
            world_id=world_id,
            geo_context=geo_context,
            game_time=game_time,
        )
        if summary is None:
            return None

        # 5. Upgrade narrative via LLM (content tag rewrite only)
        if self._wms_ai:
            self._upgrade_narrative(
                summary, l6_events, l5_events, geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner.
        #    The LLM rewrite path is reserved for CONTENT tags only —
        #    address tags (which the summarizer has already set
        #    correctly in summary.tags) are preserved by layer code.
        origin_tags = [e.get("tags", []) for e in l6_events]
        enriched = assign_higher_layer_tags(
            layer=7,
            origin_event_tags=origin_tags,
            significance=summary.severity,
            layer_specific_tags=summary.tags,
            rewrite_all=summary.tags if self._wms_ai else None,
        )
        summary.tags = enriched

        return summary

    def _fetch_l6_events(
        self, world_id: str, context_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Fetch L6 events for the world.

        Every L6 event carries a `world:X` address tag, so we can
        query directly by that tag. No need to enumerate child
        nations first.
        """
        if not self._layer_store:
            return []

        rows = self._layer_store.query_by_tags(
            layer=6,
            tags=[f"world:{world_id}"],
            match_all=True,
            limit=self._max_l6_per_world,
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
        return result[:self._max_l6_per_world]

    def _query_relevant_l5(
        self,
        world_id: str,
        fired_tag_set: Set[str],
        l6_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query L5 candidates across the world and filter by fired tags.

        L5 events also carry a `world:X` tag (propagated from L2
        capture), so we query directly.
        """
        if not self._layer_store:
            return []

        per_world_limit = max(10, self._max_l5_relevance * 4)
        rows = self._layer_store.query_by_tags(
            layer=5,
            tags=[f"world:{world_id}"],
            match_all=True,
            limit=per_world_limit,
        )
        if not rows:
            return []

        filtered = Layer7Summarizer.filter_relevant_l5(
            l5_candidates=rows,
            fired_tags=fired_tag_set,
            l6_events=l6_events,
        )
        return filtered[:self._max_l5_relevance]

    def _nations_in_world(self, world_id: str) -> List[str]:
        """List the game Nation nation_ids that are children of the World."""
        if not self._geo_registry:
            return []

        from world_system.world_memory.geographic_registry import RegionLevel

        world = self._geo_registry.regions.get(world_id)
        if world is None or world.level != RegionLevel.WORLD:
            return []

        nations: List[str] = []
        for child_id in world.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child and child.level == RegionLevel.NATION:
                nations.append(child.region_id)
        return nations

    def _build_geo_context(self, world_id: str) -> Dict[str, Any]:
        """Build geographic context (world name + list of game nations)."""
        if not self._geo_registry:
            return {"world_name": world_id, "nations": []}

        world = self._geo_registry.regions.get(world_id)
        if not world:
            return {"world_name": world_id, "nations": []}

        nations = []
        for nid in self._nations_in_world(world_id):
            n = self._geo_registry.regions.get(nid)
            if n:
                nations.append({"id": nid, "name": n.name})

        return {
            "world_name": world.name,
            "nations": nations,
        }

    def _upgrade_narrative(
        self,
        summary: WorldSummaryEvent,
        l6_events: List[Dict[str, Any]],
        l5_events: List[Dict[str, Any]],
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> None:
        """Replace template narrative with LLM-generated one.

        The LLM rewrites CONTENT tags only. Address tags
        (world only) are preserved by layer code — this method
        partitions ``summary.tags`` into address vs content halves,
        sends only the content half to the LLM, and then re-attaches
        the address half after the call returns. See
        docs/ARCHITECTURAL_DECISIONS.md §6.
        """
        if not self._wms_ai:
            return

        nations = geo_context.get("nations", [])
        world_name = geo_context.get("world_name", summary.world_id)

        # Partition existing tags into address (preserved) vs content (LLM-rewritable)
        address_tags, content_tags = partition_address_and_content(summary.tags)

        data_block = self._summarizer.build_xml_data_block(
            l6_events, l5_events, world_name, nations, game_time,
        )

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type="layer7_world_summary",
                event_subtype="world_summary",
                tags=content_tags,
                data_block=data_block,
                layer=7,
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
                        "[Layer7] WARNING: LLM returned no content tags for "
                        f"world {summary.world_id}; keeping template tags"
                    )

        except Exception as e:
            print(f"[Layer7] LLM upgrade failed for {summary.world_id}: {e}")

    def _store_summary(
        self, summary: WorldSummaryEvent, game_time: float,
    ) -> None:
        """Store a WorldSummaryEvent in LayerStore layer7_events."""
        if not self._layer_store:
            return

        existing_id = self._find_supersedable(summary.world_id)
        if existing_id:
            summary.supersedes_id = existing_id

        origin_ref = json.dumps(summary.source_nation_summary_ids)
        self._layer_store.insert_event(
            layer=7,
            narrative=summary.narrative,
            game_time=game_time,
            category="world_summary",
            severity=summary.severity,
            significance=summary.severity,
            tags=summary.tags,
            origin_ref=origin_ref,
            event_id=summary.summary_id,
        )

    def _find_supersedable(self, world_id: str) -> Optional[str]:
        """Find an existing L7 summary for this world to supersede."""
        if not self._layer_store:
            return None

        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer7_events "
            "WHERE category = 'world_summary' "
            "ORDER BY game_time DESC LIMIT 10"
        ).fetchall()

        target = f"world:{world_id}"
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
            per_world: Dict[str, Any] = {}
            for bucket_name in sorted(self._world_buckets):
                bucket = self._trigger_registry.get_weighted_bucket(
                    bucket_name)
                if bucket:
                    world_id = bucket_name[len(BUCKET_PREFIX):]
                    per_world[world_id] = {
                        "tags_tracked": len(bucket.tag_scores),
                        "tags_fired": len(bucket.fired_tags),
                    }
            trigger_info = {
                "worlds_tracked": len(self._world_buckets),
                "threshold": self._trigger_threshold,
                "per_world": per_world,
            }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
