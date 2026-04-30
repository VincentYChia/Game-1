"""Affinity resolver — deterministic post-processor for AffinityShift directives.

Per user direction (memory: wns_affinity_modifier_tool):
- Attach ``time`` (game time when emitted) and ``narrative_event_id``
  (which weaver firing emitted this) to every shift.
- Record into a time-indexed ledger so subsequent narrative consumers
  can trace causation.
- Apply via FactionSystem when wired (faction targets) or via NPC
  dynamic state (npc targets). When unwired, just log to the ledger
  for a future apply pass.

The resolver is intentionally tolerant — malformed effect strings or
unknown target prefixes degrade to "logged but not applied" so a buggy
LLM directive doesn't crash the weaver.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from world_system.wns.affinity_shift_parser import AffinityShift


# Recognized target prefixes. Anything else is "unknown" and the
# resolver just logs without applying.
TARGET_PREFIX_FACTION = "faction:"
TARGET_PREFIX_NPC = "npc:"

# Recognized scope tier prefixes (mirrors WMS RegionLevel).
KNOWN_SCOPE_TIERS = (
    "locality", "district", "region", "province", "nation", "world",
)


@dataclass
class AffinityShiftRecord:
    """A resolved affinity-shift entry with full causation provenance.

    Stored in the in-memory ledger and (in a future commit) flushed
    to a SQLite table for cross-firing traceability.
    """
    target: str
    scope: str
    effect_raw: str
    effect_kind: str  # parsed effect type (e.g. "standing_delta")
    effect_value: Optional[float]  # parsed numeric value (None if non-numeric)
    time: float
    narrative_event_id: str
    weaver_layer: int
    weaver_address: str
    applied: bool  # True if the resolver successfully wrote to a store
    apply_note: str  # diagnostic — why it did or didn't apply

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "scope": self.scope,
            "effect_raw": self.effect_raw,
            "effect_kind": self.effect_kind,
            "effect_value": self.effect_value,
            "time": self.time,
            "narrative_event_id": self.narrative_event_id,
            "weaver_layer": int(self.weaver_layer),
            "weaver_address": self.weaver_address,
            "applied": bool(self.applied),
            "apply_note": self.apply_note,
        }


# ── Effect parsing ────────────────────────────────────────────────────


# Match common effect forms:
#   "standing_delta: -0.15"
#   "standing_delta -0.15"
#   "standing_delta=-0.15"
_EFFECT_KV_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z_][\w]*)\s*[:=]?\s*(?P<val>-?\d+(?:\.\d+)?)\s*$",
)


def parse_effect(effect_raw: str) -> Tuple[str, Optional[float]]:
    """Parse an effect string into (kind, value).

    Returns:
        kind: the parsed key (e.g. ``"standing_delta"``) or ``"unparsed"``.
        value: the numeric value if present, else None. Faction
            affinity is generally on a -100..100 scale (FactionSystem)
            or -1.0..1.0 scale (NPCMemory.relationship_score). The
            resolver passes the raw value through; consumers handle
            scale conversion.
    """
    if not effect_raw:
        return "unparsed", None
    m = _EFFECT_KV_RE.match(effect_raw)
    if not m:
        return "unparsed", None
    return m.group("key").lower(), float(m.group("val"))


# ── Scope parsing ─────────────────────────────────────────────────────


def parse_scope(scope_raw: str) -> Tuple[str, str]:
    """Split ``<tier>:<id>`` into (tier, region_id). Empty pair if malformed."""
    if not scope_raw or ":" not in scope_raw:
        return "", ""
    tier, _, rid = scope_raw.partition(":")
    tier = tier.strip().lower()
    return tier, rid.strip()


def is_known_scope_tier(scope_raw: str) -> bool:
    tier, _ = parse_scope(scope_raw)
    return tier in KNOWN_SCOPE_TIERS


# ── Resolver ──────────────────────────────────────────────────────────


class AffinityResolver:
    """Deterministic resolver for AffinityShift directives.

    Stateful only in the sense that it owns an in-memory ledger of
    every shift it has ever processed. Hand a FactionSystem at
    construction time to opt into actually applying faction targets;
    otherwise the resolver just logs.

    Usage::

        resolver = AffinityResolver(faction_system=fs)
        records = resolver.resolve_batch(
            shifts, weaver_layer=4, weaver_address="region:salt_moors",
            narrative_event_id="row_xyz", game_time=300.0,
        )
        # records is List[AffinityShiftRecord]; resolver.ledger
        # accumulates them across calls.
    """

    def __init__(self, faction_system: Optional[Any] = None) -> None:
        self._faction_system = faction_system
        self._ledger: List[AffinityShiftRecord] = []

    @property
    def ledger(self) -> List[AffinityShiftRecord]:
        return list(self._ledger)

    def reset_ledger(self) -> None:
        self._ledger = []

    def resolve_batch(
        self,
        shifts: List[AffinityShift],
        *,
        weaver_layer: int,
        weaver_address: str,
        narrative_event_id: str,
        game_time: Optional[float] = None,
    ) -> List[AffinityShiftRecord]:
        """Resolve and ledger a batch of shifts. Returns the ledgered records."""
        if game_time is None:
            game_time = time.time()

        records: List[AffinityShiftRecord] = []
        for shift in shifts:
            rec = self._resolve_one(
                shift,
                weaver_layer=weaver_layer,
                weaver_address=weaver_address,
                narrative_event_id=narrative_event_id,
                game_time=game_time,
            )
            self._ledger.append(rec)
            records.append(rec)
        return records

    # ── per-shift resolution ─────────────────────────────────────────

    def _resolve_one(
        self,
        shift: AffinityShift,
        *,
        weaver_layer: int,
        weaver_address: str,
        narrative_event_id: str,
        game_time: float,
    ) -> AffinityShiftRecord:
        kind, value = parse_effect(shift.effect)

        if not is_known_scope_tier(shift.scope):
            return AffinityShiftRecord(
                target=shift.target, scope=shift.scope,
                effect_raw=shift.effect, effect_kind=kind, effect_value=value,
                time=game_time, narrative_event_id=narrative_event_id,
                weaver_layer=weaver_layer, weaver_address=weaver_address,
                applied=False,
                apply_note=f"unknown scope tier: {shift.scope!r}",
            )

        if shift.target.startswith(TARGET_PREFIX_FACTION):
            return self._apply_faction(
                shift, kind, value,
                weaver_layer, weaver_address,
                narrative_event_id, game_time,
            )
        elif shift.target.startswith(TARGET_PREFIX_NPC):
            return self._apply_npc(
                shift, kind, value,
                weaver_layer, weaver_address,
                narrative_event_id, game_time,
            )
        else:
            return AffinityShiftRecord(
                target=shift.target, scope=shift.scope,
                effect_raw=shift.effect, effect_kind=kind, effect_value=value,
                time=game_time, narrative_event_id=narrative_event_id,
                weaver_layer=weaver_layer, weaver_address=weaver_address,
                applied=False,
                apply_note=(
                    f"unknown target prefix; expected '{TARGET_PREFIX_FACTION}' "
                    f"or '{TARGET_PREFIX_NPC}'"
                ),
            )

    def _apply_faction(
        self,
        shift: AffinityShift,
        effect_kind: str,
        effect_value: Optional[float],
        weaver_layer: int,
        weaver_address: str,
        narrative_event_id: str,
        game_time: float,
    ) -> AffinityShiftRecord:
        """Apply a faction-targeted affinity shift.

        Faction tags in this scheme (``faction:moors_raiders``) map to
        WMS-style faction tags (``guild:moors_raiders``, etc.) used by
        FactionSystem. The resolver treats the part after ``faction:``
        as the canonical tag string for player_affinity adjustments
        (location-scoped via the player_id key).

        When FactionSystem is unwired, the shift is ledger-only.
        """
        applied = False
        note = ""

        if self._faction_system is None:
            note = "no faction_system wired; ledger-only"
        elif effect_kind != "standing_delta":
            note = f"unknown effect_kind for faction target: {effect_kind!r}"
        elif effect_value is None:
            note = "effect_value missing/non-numeric"
        else:
            faction_tag = shift.target[len(TARGET_PREFIX_FACTION):]
            try:
                # Player-affinity is keyed by (player_id, tag). Use the
                # SCOPE address as a synthetic player_id-like bucket so
                # the same tag can have different standings per region.
                player_bucket = shift.scope
                self._faction_system.adjust_player_affinity(
                    player_id=player_bucket,
                    tag=faction_tag,
                    delta=float(effect_value),
                    game_time=float(game_time),
                    source=f"wns:{narrative_event_id}",
                )
                applied = True
                note = "applied via FactionSystem.adjust_player_affinity"
            except Exception as e:
                note = f"FactionSystem error: {type(e).__name__}: {e}"

        return AffinityShiftRecord(
            target=shift.target, scope=shift.scope,
            effect_raw=shift.effect, effect_kind=effect_kind,
            effect_value=effect_value,
            time=game_time, narrative_event_id=narrative_event_id,
            weaver_layer=weaver_layer, weaver_address=weaver_address,
            applied=applied, apply_note=note,
        )

    def _apply_npc(
        self,
        shift: AffinityShift,
        effect_kind: str,
        effect_value: Optional[float],
        weaver_layer: int,
        weaver_address: str,
        narrative_event_id: str,
        game_time: float,
    ) -> AffinityShiftRecord:
        """Apply an NPC-targeted affinity shift.

        ``npc:Y`` targets adjust the NPC's standing toward the player
        via FactionSystem.adjust_npc_affinity_toward_player. When
        unwired, ledger-only.
        """
        applied = False
        note = ""

        if self._faction_system is None:
            note = "no faction_system wired; ledger-only"
        elif effect_kind != "standing_delta":
            note = f"unknown effect_kind for npc target: {effect_kind!r}"
        elif effect_value is None:
            note = "effect_value missing/non-numeric"
        else:
            npc_id = shift.target[len(TARGET_PREFIX_NPC):]
            try:
                self._faction_system.adjust_npc_affinity_toward_player(
                    npc_id=npc_id,
                    delta=float(effect_value),
                    game_time=float(game_time),
                )
                applied = True
                note = "applied via FactionSystem.adjust_npc_affinity_toward_player"
            except Exception as e:
                note = f"FactionSystem error: {type(e).__name__}: {e}"

        return AffinityShiftRecord(
            target=shift.target, scope=shift.scope,
            effect_raw=shift.effect, effect_kind=effect_kind,
            effect_value=effect_value,
            time=game_time, narrative_event_id=narrative_event_id,
            weaver_layer=weaver_layer, weaver_address=weaver_address,
            applied=applied, apply_note=note,
        )


__all__ = [
    "AffinityShiftRecord",
    "AffinityResolver",
    "parse_effect",
    "parse_scope",
    "is_known_scope_tier",
    "KNOWN_SCOPE_TIERS",
    "TARGET_PREFIX_FACTION",
    "TARGET_PREFIX_NPC",
]
