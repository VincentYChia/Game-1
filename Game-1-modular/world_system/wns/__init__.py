"""World Narrative System (WNS) — sibling system of WMS.

Scaffolding for the downstream narrative half of Living World. See §4 of
``Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`` for the canonical design.

Architecture (v4):

- **Separate SQLite database** (``world_narrative.db``) — NOT co-located with
  WMS's ``world_memory.db``. Save/load coordinates two files.
- **Separate tag taxonomy** via :class:`NarrativeTagLibrary` (reads
  ``narrative-tag-definitions.JSON``).
- **7 layers, NL1-NL7**. NL1 is deterministic capture of pre-generated NPC
  dialogue (no LLM). NL2-NL7 are LLM weaving calls parameterized by scale.
- **Threads are first-class at every weaving layer** (see §4.5).
- **Every-N-events-per-layer-per-address trigger buckets** via
  :class:`NLTriggerManager`.
- **Address-tag immutability** — narrative addresses (``thread:``, ``arc:``,
  ``witness:``) plus geographic addresses carried through from WMS are
  never LLM-writable (same rule as WMS; reuses
  :func:`partition_address_and_content`).
- Weavers call :meth:`BackendManager.generate(task="wns_layer<N>")`.
  P0 fixture registry provides mock responses for all 6 weaver layers.
- When a weaver's output has ``call_wes: true`` the WNS publishes a
  ``WNS_CALL_WES_REQUESTED`` event on the :class:`GameEventBus` so the
  WES (owned by a later phase) can subscribe.

Public surface: :class:`WorldNarrativeSystem` (facade singleton).
"""

# Re-export the facade + the address-tag prefix list so consumers don't
# have to reach into submodules.
from world_system.wns.world_narrative_system import WorldNarrativeSystem  # noqa: F401
from world_system.wns.narrative_tag_library import (  # noqa: F401
    ADDRESS_TAG_PREFIXES,
    NarrativeTagLibrary,
)
