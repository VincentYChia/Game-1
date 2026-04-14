"""Layer 5 Manager — orchestrates realm-level summarization from Layer 4.

Trigger: Tag-weighted, **per-realm**. Each Layer 4 event is routed to a
realm-specific WeightedTriggerBucket based on its geographic parent chain
(province → nation → realm). Geographic tags (realm:, nation:, province:,
district:, locality:) are stripped before scoring so only content tags
consume positional weight:
    Position 1 = 10, 2 = 8, 3 = 6, 4 = 5, 5 = 4, 6 = 3, 7-12 = 2, 13+ = 1.

When any content tag crosses the threshold (default 100 points) *within a
realm*, it fires and all contributing L4 events become context for that
realm's summary.

Realm scope: WMS REALM = game's top-level world area. Each realm contains
multiple nations; each nation contains multiple provinces. With today's
game there is a single realm (`realm_0`) but the architecture supports
multi-realm worlds.

Data flow:
    Layer 4 event stored in LayerStore (layer4_events)
           ↓
    Layer5Manager.on_layer4_created()
      — extract province_id from event tags
      — resolve realm_id via geo_registry parent chain
      — strip geographic tags (realm:, nation:, province:, district:, locality:)
      — ingest content tags into per-realm WeightedTriggerBucket
           ↓ (content tag crosses threshold within realm → fires)
    Contributing L4 events become primary context
    Relevant L3 events (fired-tag overlap filter) become two-layers-down context
           ↓
    Layer5Summarizer.summarize() — build template narrative
           ↓
    LLM upgrade — rewrite narrative + ALL tags (66-80% retention, reordered)
           ↓
    Store in layer5_events + layer5_tags (superseding previous summary)

Visibility rule (two-layers-down):
    Layer 5 sees Layer 4 (full) and Layer 3 (filtered by fired-tag overlap).
    Layer 5 does NOT see Layer 2, Layer 1 stats, or Layers 6-7.

Pure WMS pipeline:
    Layer 5 does NOT read FactionSystem, EcosystemAgent, or any other state
    tracker. See docs/ARCHITECTURAL_DECISIONS.md §§4-5.
"""

from __future__ import annotations

import json
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set

from world_system.world_memory.config_loader import get_section
from world_system.world_memory.event_schema import (
    RealmSummaryEvent, SEVERITY_ORDER,
)
from world_system.world_memory.layer5_summarizer import Layer5Summarizer
from world_system.world_memory.tag_assignment import assign_higher_layer_tags
from world_system.world_memory.trigger_registry import TriggerRegistry


# Per-realm bucket name prefix: "layer5_realm_{realm_id}"
BUCKET_PREFIX = "layer5_realm_"

# Geographic tag prefixes stripped before scoring — address tags, not content.
_GEO_TAG_PREFIXES = ("realm:", "nation:", "province:", "district:", "locality:")


class Layer5Manager:
    """Orchestrates Layer 5 realm summarization. Singleton.

    Uses WeightedTriggerBucket (one per realm) to score Layer 4 events by
    tag position. When a content tag crosses the threshold within a realm,
    contributing L4 events + relevant L3 events are gathered and
    summarized into a RealmSummaryEvent.
    """

    _instance: ClassVar[Optional["Layer5Manager"]] = None

    def __init__(self):
        self._summarizer: Layer5Summarizer = Layer5Summarizer()
        self._layer_store = None
        self._geo_registry = None
        self._wms_ai = None
        self._trigger_registry: Optional[TriggerRegistry] = None
        self._initialized = False

        # Per-realm bucket tracking (set of bucket names)
        self._realm_buckets: Set[str] = set()

        # Config
        self._trigger_threshold: int = 100
        self._max_l4_per_realm: int = 50
        self._max_l3_relevance: int = 8
        self._min_provinces_contributing: int = 1  # see note below

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
        """Wire dependencies and prepare per-realm trigger buckets.

        Args:
            layer_store: LayerStore for reading L4/L3 and writing L5.
            geo_registry: GeographicRegistry for realm hierarchy lookup.
            wms_ai: WmsAI for LLM narration (optional).
            trigger_registry: TriggerRegistry instance (optional).
        """
        self._layer_store = layer_store
        self._geo_registry = geo_registry
        self._wms_ai = wms_ai

        cfg = get_section("layer5")
        self._trigger_threshold = cfg.get("trigger_threshold", 100)
        self._max_l4_per_realm = cfg.get("max_l4_per_realm", 50)
        self._max_l3_relevance = cfg.get("max_l3_relevance", 8)
        self._min_provinces_contributing = cfg.get(
            "min_provinces_contributing", 1)

        # Per-realm buckets created lazily in on_layer4_created().
        # Recover any existing realm buckets from a prior session.
        self._trigger_registry = (
            trigger_registry or TriggerRegistry.get_instance()
        )
        self._realm_buckets = set(
            self._trigger_registry.get_weighted_bucket_names(BUCKET_PREFIX)
        )

        self._initialized = True
        print(
            f"[Layer5] Initialized — per-realm weighted triggers, "
            f"threshold {self._trigger_threshold} points, "
            f"{len(self._realm_buckets)} existing realm buckets"
        )

    # ── Trigger API ─────────────────────────────────────────────────

    def on_layer4_created(self, l4_event_dict: Dict[str, Any]) -> None:
        """Called each time a Layer 4 province summary is stored.

        Resolves the realm_id from the event's province tag by walking the
        geographic parent chain. Strips geographic address tags, then
        ingests content tags into the realm-specific WeightedTriggerBucket.
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

        # Resolve realm_id from any address tag in the event
        realm_id = self._resolve_realm_id_from_tags(tags)
        if not realm_id:
            return

        # Strip geographic address tags so content tags get full positional
        # weight (e.g. domain:combat at position 0 = 10 pts, not 6)
        content_tags = [
            t for t in tags
            if not any(t.startswith(p) for p in _GEO_TAG_PREFIXES)
        ]
        if not content_tags:
            return

        bucket_name = f"{BUCKET_PREFIX}{realm_id}"
        if bucket_name not in self._realm_buckets:
            self._trigger_registry.register_weighted_bucket(
                bucket_name, threshold=self._trigger_threshold)
            self._realm_buckets.add(bucket_name)

        self._trigger_registry.ingest_event_weighted(
            bucket_name, event_id, content_tags)

    def should_run(self) -> bool:
        """Check if any content tag in any realm bucket has crossed threshold."""
        if not self._initialized or not self._trigger_registry:
            return False
        return self._trigger_registry.any_weighted_fired_with_prefix(
            BUCKET_PREFIX)

    def run_summarization(self, game_time: float) -> int:
        """Execute summarization for all realm buckets that have fired.

        Each realm bucket fires independently when its content tags cross
        the threshold. Contributing event IDs are already scoped to the
        correct realm.

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
            realm_id = bucket_name[len(BUCKET_PREFIX):]

            # Collect all contributing L4 event IDs across all fired tags
            context_event_ids: Set[str] = set()
            for event_ids in fired_tags_map.values():
                context_event_ids.update(event_ids)

            # Fired tag set drives L3 filtering (two-layers-down visibility)
            fired_tag_set = set(fired_tags_map.keys())

            summary = self._summarize_realm(
                realm_id, context_event_ids, fired_tag_set, game_time)
            if summary is not None:
                self._store_summary(summary, game_time)
                created += 1
                self._summaries_created += 1

        self._runs_completed += 1
        self._last_run_game_time = game_time

        if created > 0:
            print(
                f"[Layer5] Summarization run #{self._runs_completed}: "
                f"{created} realm summaries from "
                f"{len(all_fired)} realm buckets"
            )

        return created

    # ── Internal Methods ────────────────────────────────────────────

    def _resolve_realm_id_from_tags(
        self, tags: List[str],
    ) -> Optional[str]:
        """Walk geographic hierarchy from any address tag up to the realm.

        L4 events may or may not carry a literal `realm:` tag depending on
        whether the LLM rewrite included it. We handle both cases:
        - If there's already a `realm:X` tag, use it directly.
        - Otherwise, find the most-specific address tag (province >
          nation > district > locality) and walk parents until we hit a
          realm-level region.

        Returns None if no resolvable address is found.
        """
        # Fast path: explicit realm tag
        for tag in tags:
            if tag.startswith("realm:"):
                return tag.split(":", 1)[1]

        if not self._geo_registry:
            return None

        # Try to resolve from any known address level.
        # Priority: nation (one step from realm) > province > district > locality.
        # This biases toward the shortest walk up the tree.
        for prefix in ("nation:", "province:", "district:", "locality:"):
            for tag in tags:
                if tag.startswith(prefix):
                    region_id = tag.split(":", 1)[1]
                    realm = self._walk_to_realm(region_id)
                    if realm:
                        return realm

        return None

    def _walk_to_realm(self, region_id: str) -> Optional[str]:
        """Walk parent chain from any region up to the REALM level.

        Returns the realm region_id or None if the chain is broken or no
        realm ancestor exists.
        """
        if not self._geo_registry:
            return None

        # Import here to avoid circular imports at module load time
        from world_system.world_memory.geographic_registry import RegionLevel

        visited = set()
        current_id: Optional[str] = region_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            region = self._geo_registry.regions.get(current_id)
            if region is None:
                return None
            if region.level == RegionLevel.REALM:
                return region.region_id
            current_id = region.parent_id
        return None

    def _summarize_realm(
        self,
        realm_id: str,
        context_event_ids: Set[str],
        fired_tag_set: Set[str],
        game_time: float,
    ) -> Optional[RealmSummaryEvent]:
        """Produce a summary for one realm using contributing L4 + relevant L3."""
        # 1. Fetch L4 events for this realm — prioritize contributors
        l4_events = self._fetch_l4_events(realm_id, context_event_ids)
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
                # Note: contributing events are NOT re-ingested; they are
                # voided (same as Layer 4 behavior on threshold crossing).
                return None

        # 2. Fetch L3 events (two-layers-down, fired-tag filtered)
        l3_events = self._query_relevant_l3(realm_id, fired_tag_set, l4_events)

        # 3. Build geographic context
        geo_context = self._build_geo_context(realm_id)

        # 4. Run summarizer
        summary = self._summarizer.summarize(
            l4_events=l4_events,
            l3_events=l3_events,
            realm_id=realm_id,
            geo_context=geo_context,
            game_time=game_time,
        )
        if summary is None:
            return None

        # 5. Upgrade narrative via LLM (includes full tag rewrite)
        if self._wms_ai:
            self._upgrade_narrative(
                summary, l4_events, l3_events, geo_context, game_time)

        # 6. Enrich tags via HigherLayerTagAssigner.
        #    If LLM provided a rewrite, use the rewrite_all path.
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
        self, realm_id: str, context_event_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Fetch L4 events for the realm.

        L4 events may not always carry a literal `realm:` tag (the LLM
        rewrite may not include it). So we can't just query by realm tag.
        Instead: gather province IDs under this realm, query by each, and
        merge. Prioritize contributing events.
        """
        if not self._layer_store or not self._geo_registry:
            return []

        province_ids = self._provinces_in_realm(realm_id)
        if not province_ids:
            return []

        collected: Dict[str, Dict[str, Any]] = {}
        for pid in province_ids:
            rows = self._layer_store.query_by_tags(
                layer=4,
                tags=[f"province:{pid}"],
                match_all=True,
                limit=self._max_l4_per_realm,
            )
            for row in rows:
                eid = row.get("id", "")
                if eid and eid not in collected:
                    collected[eid] = row

        all_l4 = list(collected.values())
        if not all_l4:
            return []

        # Sort: contributors first, then by recency.
        contributors, others = [], []
        for event in all_l4:
            if event.get("id") in context_event_ids:
                contributors.append(event)
            else:
                others.append(event)

        contributors.sort(key=lambda e: e.get("game_time", 0.0), reverse=True)
        others.sort(key=lambda e: e.get("game_time", 0.0), reverse=True)

        result = contributors + others
        return result[:self._max_l4_per_realm]

    def _query_relevant_l3(
        self,
        realm_id: str,
        fired_tag_set: Set[str],
        l4_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query L3 candidates across the realm and filter by fired tags.

        Uses the summarizer's filter_relevant_l3 static method so the
        filter logic is testable independently.
        """
        if not self._layer_store or not self._geo_registry:
            return []

        province_ids = self._provinces_in_realm(realm_id)
        if not province_ids:
            return []

        # Gather L3 candidates from every province in the realm.
        # Per-province limit keeps total bounded.
        per_province = max(5, self._max_l3_relevance * 2)
        candidates: Dict[str, Dict[str, Any]] = {}
        for pid in province_ids:
            rows = self._layer_store.query_by_tags(
                layer=3,
                tags=[f"province:{pid}"],
                match_all=True,
                limit=per_province,
            )
            for row in rows:
                eid = row.get("id", "")
                if eid and eid not in candidates:
                    candidates[eid] = row

        if not candidates:
            return []

        filtered = Layer5Summarizer.filter_relevant_l3(
            l3_candidates=list(candidates.values()),
            fired_tags=fired_tag_set,
            l4_events=l4_events,
        )
        return filtered[:self._max_l3_relevance]

    def _provinces_in_realm(self, realm_id: str) -> List[str]:
        """List all province-level region IDs under a realm.

        Walks: realm → nations → provinces. Falls back to any direct
        PROVINCE children of the realm if the nation layer is skipped.
        """
        if not self._geo_registry:
            return []

        from world_system.world_memory.geographic_registry import RegionLevel

        realm = self._geo_registry.regions.get(realm_id)
        if realm is None or realm.level != RegionLevel.REALM:
            return []

        provinces: List[str] = []
        for child_id in realm.child_ids:
            child = self._geo_registry.regions.get(child_id)
            if child is None:
                continue
            if child.level == RegionLevel.PROVINCE:
                provinces.append(child.region_id)
                continue
            # Nation → provinces
            if child.level == RegionLevel.NATION:
                for grandchild_id in child.child_ids:
                    grandchild = self._geo_registry.regions.get(grandchild_id)
                    if grandchild and grandchild.level == RegionLevel.PROVINCE:
                        provinces.append(grandchild.region_id)
        return provinces

    def _build_geo_context(self, realm_id: str) -> Dict[str, Any]:
        """Build geographic context (realm name + list of provinces)."""
        if not self._geo_registry:
            return {"realm_name": realm_id, "provinces": []}

        realm = self._geo_registry.regions.get(realm_id)
        if not realm:
            return {"realm_name": realm_id, "provinces": []}

        provinces = []
        for pid in self._provinces_in_realm(realm_id):
            p = self._geo_registry.regions.get(pid)
            if p:
                provinces.append({"id": pid, "name": p.name})

        return {
            "realm_name": realm.name,
            "provinces": provinces,
        }

    def _upgrade_narrative(
        self,
        summary: RealmSummaryEvent,
        l4_events: List[Dict[str, Any]],
        l3_events: List[Dict[str, Any]],
        geo_context: Dict[str, Any],
        game_time: float,
    ) -> None:
        """Replace template narrative with LLM-generated one.

        At Layer 5, the LLM performs a FULL TAG REWRITE: it receives the
        aggregate inherited tags as input context and outputs a complete
        reordered tag list (keeping ~66-80% of aggregate tags, reordered
        by relevance to the narrative it generated).
        """
        if not self._wms_ai:
            return

        provinces = geo_context.get("provinces", [])
        realm_name = geo_context.get("realm_name", summary.realm_id)

        data_block = self._summarizer.build_xml_data_block(
            l4_events, l3_events, realm_name, provinces, game_time,
        )

        try:
            llm_result = self._wms_ai.generate_narration(
                event_type="layer5_realm_summary",
                event_subtype="realm_summary",
                tags=summary.tags,
                data_block=data_block,
                layer=5,
            )

            if llm_result.success and llm_result.text:
                summary.narrative = llm_result.text
                if llm_result.severity != "minor":
                    summary.severity = llm_result.severity

                # Full tag rewrite: LLM output replaces ALL tags
                if llm_result.tags:
                    summary.tags = llm_result.tags
                else:
                    print(
                        "[Layer5] WARNING: LLM returned no tags for realm "
                        f"{summary.realm_id}"
                    )

        except Exception as e:
            print(f"[Layer5] LLM upgrade failed for {summary.realm_id}: {e}")

    def _store_summary(
        self, summary: RealmSummaryEvent, game_time: float,
    ) -> None:
        """Store a RealmSummaryEvent in LayerStore layer5_events."""
        if not self._layer_store:
            return

        existing_id = self._find_supersedable(summary.realm_id)
        if existing_id:
            summary.supersedes_id = existing_id

        origin_ref = json.dumps(summary.source_province_summary_ids)
        self._layer_store.insert_event(
            layer=5,
            narrative=summary.narrative,
            game_time=game_time,
            category="realm_summary",
            severity=summary.severity,
            significance=summary.severity,
            tags=summary.tags,
            origin_ref=origin_ref,
            event_id=summary.summary_id,
        )

    def _find_supersedable(self, realm_id: str) -> Optional[str]:
        """Find an existing L5 summary for this realm to supersede."""
        if not self._layer_store:
            return None

        c = self._layer_store.connection
        rows = c.execute(
            "SELECT id, tags_json FROM layer5_events "
            "WHERE category = 'realm_summary' "
            "ORDER BY game_time DESC LIMIT 10"
        ).fetchall()

        target = f"realm:{realm_id}"
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
            per_realm: Dict[str, Any] = {}
            for bucket_name in sorted(self._realm_buckets):
                bucket = self._trigger_registry.get_weighted_bucket(
                    bucket_name)
                if bucket:
                    realm_id = bucket_name[len(BUCKET_PREFIX):]
                    per_realm[realm_id] = {
                        "tags_tracked": len(bucket.tag_scores),
                        "tags_fired": len(bucket.fired_tags),
                    }
            trigger_info = {
                "realms_tracked": len(self._realm_buckets),
                "threshold": self._trigger_threshold,
                "per_realm": per_realm,
            }
        return {
            "initialized": self._initialized,
            "summaries_created": self._summaries_created,
            "runs_completed": self._runs_completed,
            "last_run_game_time": self._last_run_game_time,
            "trigger": trigger_info,
        }
