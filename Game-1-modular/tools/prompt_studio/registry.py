"""LLMSystem registry — declarative metadata for every LLM task.

Single source of truth for the Prompt Studio UI. Each entry describes:

- ``id``              : canonical task code (e.g. ``"wes_tool_chunks"``).
  Matches the BackendManager task code AND the LLMFixtureRegistry key.
- ``label``           : short human-readable name for the tree view.
- ``tier``            : grouping bucket (WMS / WNS / WES / NPC).
- ``fragment_path``   : on-disk JSON the assembler reads.
- ``assembler_style`` : ``"wms"`` (tag-indexed) or ``"wes"`` (templated).
- ``output_format``   : ``"json"`` or ``"xml"`` (hubs emit XML batches).
- ``sample_input_key``: optional key into :mod:`sample_inputs` for
  realistic var generation. None → only awareness blocks fill the prompt.
- ``description``     : 1-line summary shown in the panel header.

Adding a new LLM task: add a row here AND register a fixture in
:mod:`world_system.living_world.infra.llm_fixtures.builtin` (the
simulator will fall through to the live BackendManager otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Dict, List, Optional


# ── Project root so all fragment paths can be relative ──────────────────

_PROJECT_DIR = Path(__file__).parent.parent.parent  # Game-1-modular/


# ── Enums ───────────────────────────────────────────────────────────────

class SystemTier(str, Enum):
    """Tier grouping in the Prompt Studio tree view."""
    WMS = "WMS — World Memory"
    WNS = "WNS — World Narrative"
    WES = "WES — World Executor"
    NPC = "NPC — Dialogue"


class AssemblerStyle(str, Enum):
    """Which prompt assembler reads the fragment file."""

    # Tag-indexed style. world_system/world_memory/prompt_assembler.py
    # reads layered fragment files keyed by tag (species:wolf_grey,
    # action:deplete, ...) and assembles a system+user prompt by
    # picking the fragments matching the firing event's tags.
    WMS = "wms"

    # Templated style. world_system/wes/llm_tiers/prompt_assembler.py
    # reads {_meta, _core: {system, user_template}, _output: {schema, example}}
    # and substitutes ${var} tokens with caller-supplied variables.
    WES = "wes"


class OutputFormat(str, Enum):
    """Expected output format the LLM should emit."""
    JSON = "json"
    XML = "xml"          # WES hubs emit <specs> XML batches.


# ── Dataclass ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LLMSystem:
    """One LLM task's metadata."""
    id: str
    label: str
    tier: SystemTier
    fragment_path: Path
    assembler_style: AssemblerStyle
    output_format: OutputFormat
    description: str
    sample_input_key: Optional[str] = None

    @property
    def fragment_relpath(self) -> str:
        """Path relative to the project root, for compact display."""
        try:
            return str(self.fragment_path.relative_to(_PROJECT_DIR))
        except ValueError:
            return str(self.fragment_path)


# ── Registry ────────────────────────────────────────────────────────────

def _wms_path(filename: str) -> Path:
    return _PROJECT_DIR / "world_system" / "config" / filename


_REGISTRY: List[LLMSystem] = [
    # ── WMS Layers 2-7 ──────────────────────────────────────────────────
    LLMSystem(
        id="wms_layer2",
        label="L2 — Tagged event interpretation",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 2: turn one tagged gameplay event into a "
                    "narrative interpretation.",
        sample_input_key="wms_layer2",
    ),
    LLMSystem(
        id="wms_layer3",
        label="L3 — Locality consolidation",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments_l3.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 3: consolidate Layer 2 events at locality scale.",
        sample_input_key="wms_layer3",
    ),
    LLMSystem(
        id="wms_layer4",
        label="L4 — District consolidation",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments_l4.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 4: consolidate L3 narratives at district scale.",
        sample_input_key="wms_layer3",
    ),
    LLMSystem(
        id="wms_layer5",
        label="L5 — Region consolidation",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments_l5.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 5: consolidate L4 narratives at region scale.",
        sample_input_key="wms_layer3",
    ),
    LLMSystem(
        id="wms_layer6",
        label="L6 — Province consolidation",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments_l6.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 6: consolidate L5 narratives at province scale.",
        sample_input_key="wms_layer3",
    ),
    LLMSystem(
        id="wms_layer7",
        label="L7 — World summary",
        tier=SystemTier.WMS,
        fragment_path=_wms_path("prompt_fragments_l7.json"),
        assembler_style=AssemblerStyle.WMS,
        output_format=OutputFormat.JSON,
        description="Layer 7: consolidate L6 narratives at world scale.",
        sample_input_key="wms_layer3",
    ),

    # ── WNS Narrative Weavers (NL2-NL7) ─────────────────────────────────
    LLMSystem(
        id="wns_layer2",
        label="NL2 — Locality narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl2.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Cascade-fired narrative weaver for locality-scale "
                    "events. Output may include WES calls.",
        sample_input_key="wns_layer",
    ),
    LLMSystem(
        id="wns_layer3",
        label="NL3 — District narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl3.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="District-scale weaver, fires every 3 NL2 cascades.",
        sample_input_key="wns_layer",
    ),
    LLMSystem(
        id="wns_layer4",
        label="NL4 — Region narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl4.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Region-scale weaver. Fires WES generation more often.",
        sample_input_key="wns_layer",
    ),
    LLMSystem(
        id="wns_layer5",
        label="NL5 — Province narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl5.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Province-scale weaver.",
        sample_input_key="wns_layer",
    ),
    LLMSystem(
        id="wns_layer6",
        label="NL6 — Nation narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl6.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Nation-scale weaver.",
        sample_input_key="wns_layer",
    ),
    LLMSystem(
        id="wns_layer7",
        label="NL7 — World narrative",
        tier=SystemTier.WNS,
        fragment_path=_wms_path("narrative_fragments_nl7.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="World-scale weaver. Top of the cascade.",
        sample_input_key="wns_layer",
    ),

    # ── WES Tier 1 — Execution Planner ──────────────────────────────────
    LLMSystem(
        id="wes_execution_planner",
        label="Execution Planner (Tier 1)",
        tier=SystemTier.WES,
        fragment_path=_wms_path("prompt_fragments_wes_execution_planner.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Given a WNS bundle, plan which tools to invoke "
                    "and at what scale. Output: WESPlan.",
        sample_input_key="wes_planner",
    ),

    # ── WES Tier 2 — Hubs (8 tools, batch XML emit) ─────────────────────
    *[
        LLMSystem(
            id=f"wes_hub_{tool}",
            label=f"Hub: {tool} (Tier 2)",
            tier=SystemTier.WES,
            fragment_path=_wms_path(f"prompt_fragments_hub_{tool}.json"),
            assembler_style=AssemblerStyle.WES,
            output_format=OutputFormat.XML,
            description=f"Batch-emit {tool} ExecutorSpecs as <specs> XML "
                        f"(one LLM call per plan step).",
            sample_input_key=f"wes_hub_{tool}",
        )
        for tool in (
            "hostiles", "materials", "nodes", "skills",
            "titles", "chunks", "npcs", "quests",
        )
    ],

    # ── WES Tier 3 — Executor Tools (8) ─────────────────────────────────
    *[
        LLMSystem(
            id=f"wes_tool_{tool}",
            label=f"Tool: {tool} (Tier 3)",
            tier=SystemTier.WES,
            fragment_path=_wms_path(f"prompt_fragments_tool_{tool}.json"),
            assembler_style=AssemblerStyle.WES,
            output_format=OutputFormat.JSON,
            description=f"Emit one {tool[:-1]} JSON per ExecutorSpec.",
            sample_input_key=f"wes_tool_{tool}",
        )
        for tool in (
            "hostiles", "materials", "nodes", "skills",
            "titles", "chunks", "npcs", "quests",
        )
    ],

    # ── WES Tier 4 — Supervisor ─────────────────────────────────────────
    LLMSystem(
        id="wes_supervisor",
        label="Supervisor (Tier 4)",
        tier=SystemTier.WES,
        fragment_path=_wms_path("prompt_fragments_wes_supervisor.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Cross-tier reviewer; recommends commit, rerun, "
                    "or rollback.",
        sample_input_key="wes_supervisor",
    ),

    # ── WES Quest Reward (pre-gen + adapt) ──────────────────────────────
    LLMSystem(
        id="wes_quest_reward_pregen",
        label="Quest Reward — Pre-generate",
        tier=SystemTier.WES,
        fragment_path=_wms_path("prompt_fragments_wes_quest_reward_pregen.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Materialize prose reward hints into concrete "
                    "QuestRewards + completion dialogue at receive time.",
        sample_input_key="wes_quest_reward",
    ),
    LLMSystem(
        id="wes_quest_reward_adapt",
        label="Quest Reward — Adapt at turn-in",
        tier=SystemTier.WES,
        fragment_path=_wms_path("prompt_fragments_wes_quest_reward_adapt.json"),
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Adapt pre-generated rewards based on actual play "
                    "(0.5x..1.5x bound; soft 1.0x floor).",
        sample_input_key="wes_quest_reward",
    ),

    # ── NPC Dialogue ────────────────────────────────────────────────────
    LLMSystem(
        id="npc_dialogue_speechbank",
        label="NPC Dialogue — speechbank-driven",
        tier=SystemTier.NPC,
        fragment_path=_wms_path("prompt_fragments.json"),  # placeholder
        assembler_style=AssemblerStyle.WES,
        output_format=OutputFormat.JSON,
        description="Generate one NPC dialogue line using their "
                    "speechbank + faction context. (Fragment file "
                    "shared with WMS L2; actual prompt is built "
                    "inline in NPCMemoryManager.)",
        sample_input_key="npc_dialogue",
    ),
]


class SystemRegistry:
    """Singleton-like accessor for the immutable system list."""

    _BY_ID: ClassVar[Optional[Dict[str, LLMSystem]]] = None

    @classmethod
    def all(cls) -> List[LLMSystem]:
        return list(_REGISTRY)

    @classmethod
    def by_tier(cls, tier: SystemTier) -> List[LLMSystem]:
        return [s for s in _REGISTRY if s.tier == tier]

    @classmethod
    def by_id(cls, system_id: str) -> Optional[LLMSystem]:
        if cls._BY_ID is None:
            cls._BY_ID = {s.id: s for s in _REGISTRY}
        return cls._BY_ID.get(system_id)

    @classmethod
    def ids(cls) -> List[str]:
        return [s.id for s in _REGISTRY]

    @classmethod
    def grouped_by_tier(cls) -> Dict[SystemTier, List[LLMSystem]]:
        out: Dict[SystemTier, List[LLMSystem]] = {}
        for s in _REGISTRY:
            out.setdefault(s.tier, []).append(s)
        return out


__all__ = [
    "AssemblerStyle",
    "LLMSystem",
    "OutputFormat",
    "SystemRegistry",
    "SystemTier",
]
