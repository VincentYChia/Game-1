"""NL1 Ingestor — deterministic NPC-mention extractor.

Per §4.4 of the working doc and CC6: NL1 is **pre-generated NPC dialogue**
captured deterministically at speech-bank generation time. A mention
extractor (no LLM call) runs over speech-bank text and writes one
NL1 event per extracted mention, addressed to the NPC's current locality.

**Deterministic only.** No LLM call here. The mention extractor is simple
by design — it catches named entities via a placeholder regex / keyword
list. When that proves insufficient the designer replaces the vocabulary
(and/or the extractor heuristic) per PLACEHOLDER_LEDGER.md.

Output shape per row:

- ``narrative`` — the dialogue excerpt that triggered the mention.
- ``address``   — the speaker's ``locality:<...>`` tag (passed in).
- ``tags``      — ``["mention:<entity>", "claim_type:<type>",
  "significance:<hint>", address tags]``.
- ``payload``   — ``{"npc_id", "speech_bank_key", "entity",
  "claim_type", "significance"}``.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from world_system.wns.narrative_store import NarrativeRow, NarrativeStore


# ── Placeholder vocabulary ───────────────────────────────────────────
# TODO(designer): replace this keyword set with the real NPC-mention
# vocabulary. See Development-Plan/PLACEHOLDER_LEDGER.md §5 / §2 for
# scope commitments — extracted_mentions shape is still `List[Dict]`
# with keys {entity, claim_type, significance}.

# Claim-type keywords drive a crude but deterministic classification.
_CLAIM_TYPE_KEYWORDS: Dict[str, Sequence[str]] = {
    "rumor":        ("rumor", "say", "heard", "they say", "whispers", "word is"),
    "observation":  ("saw", "watched", "noticed", "see", "seen"),
    "recollection": ("remember", "recall", "once", "years ago", "used to"),
    "boast":        ("i will", "i'll", "i can", "my", "watch me"),
}

# Placeholder entity keyword list — bands that recur across many
# speech-banks. Designer refines with real taxonomy.
_ENTITY_KEYWORDS: Sequence[str] = (
    "bandits",
    "copper",
    "iron",
    "guild",
    "forge",
    "king",
    "queen",
    "dragon",
    "wolves",
    "road",
    "market",
    "guard",
    "strike",
    "rush",
    "trade",
    "mine",
    "prices",
    "apprentices",
)


# Significance heuristic — very rough. Count exclamation/capitalization
# signals. Designer replaces per PLACEHOLDER_LEDGER.md §2.
def _estimate_significance(snippet: str) -> str:
    if "!" in snippet or any(w.isupper() and len(w) > 2 for w in snippet.split()):
        return "significant"
    if len(snippet) > 80:
        return "moderate"
    return "minor"


# ── Main extractor ───────────────────────────────────────────────────

class NL1Ingestor:
    """Deterministic NPC-mention extractor writing NL1 rows.

    Not a singleton — one ingestor per :class:`WorldNarrativeSystem`
    facade instance, constructed with that system's :class:`NarrativeStore`.
    """

    def __init__(self, store: NarrativeStore) -> None:
        self._store = store

    # ── Public API ───────────────────────────────────────────────────

    def ingest_speech_bank(
        self,
        npc_id: str,
        speech_bank_json: Dict[str, Any],
        address: str,
        game_time: Optional[float] = None,
    ) -> List[NarrativeRow]:
        """Extract mentions from a speech bank and write NL1 rows.

        Args:
            npc_id:             Stable NPC identifier.
            speech_bank_json:   The speech-bank dict — keys per fixture
                                shape ``{greeting, quest_accept, quest_turnin,
                                closing}`` but this method is tolerant of
                                any string-valued mapping.
            address:            Speaker's current locality tag,
                                e.g. ``"locality:tarmouth_copperdocks"``.
                                **Must** be the full ``<prefix>:<id>`` form.
            game_time:          Optional game-time override; defaults to
                                ``time.time()``.

        Returns:
            The :class:`NarrativeRow` instances written (may be empty if
            no mentions extracted).
        """
        if game_time is None:
            game_time = time.time()

        rows_written: List[NarrativeRow] = []
        # Iterate deterministically over speech-bank keys for stable output.
        for key in sorted(speech_bank_json.keys()):
            value = speech_bank_json[key]
            if not isinstance(value, str):
                continue
            extracted = self._extract_mentions(value)
            for m in extracted:
                row = self._build_row(
                    npc_id=npc_id,
                    speech_bank_key=key,
                    dialogue_snippet=value,
                    mention=m,
                    address=address,
                    game_time=game_time,
                )
                self._store.insert_row(row)
                rows_written.append(row)

        return rows_written

    # ── Extraction helpers ───────────────────────────────────────────

    def _extract_mentions(self, dialogue: str) -> List[Dict[str, Any]]:
        """Return a list of mention dicts — one per entity keyword hit."""
        if not dialogue:
            return []
        lower = dialogue.lower()
        claim_type = self._classify_claim_type(lower)
        mentions: List[Dict[str, Any]] = []
        for ent in _ENTITY_KEYWORDS:
            if re.search(rf"\b{re.escape(ent)}\b", lower):
                mentions.append(
                    {
                        "entity": ent,
                        "claim_type": claim_type,
                        "significance": _estimate_significance(dialogue),
                    }
                )
        return mentions

    @staticmethod
    def _classify_claim_type(dialogue_lower: str) -> str:
        for claim, keywords in _CLAIM_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in dialogue_lower:
                    return claim
        return "observation"

    # ── Row assembly ─────────────────────────────────────────────────

    def _build_row(
        self,
        *,
        npc_id: str,
        speech_bank_key: str,
        dialogue_snippet: str,
        mention: Dict[str, Any],
        address: str,
        game_time: float,
    ) -> NarrativeRow:
        tags: List[str] = [
            address,  # address tag carried verbatim (immutable)
            f"mention:{mention['entity']}",
            f"claim_type:{mention['claim_type']}",
            f"significance:{mention['significance']}",
            f"witness:{npc_id}",
        ]
        payload: Dict[str, Any] = {
            "npc_id": npc_id,
            "speech_bank_key": speech_bank_key,
            "dialogue": dialogue_snippet,
            "extracted_mention": mention,
        }
        return NarrativeRow(
            id=str(uuid.uuid4()),
            created_at=game_time,
            layer=1,
            address=address,
            narrative=dialogue_snippet,
            tags=tags,
            payload=payload,
        )
