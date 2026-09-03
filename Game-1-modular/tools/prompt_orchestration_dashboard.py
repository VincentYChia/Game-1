"""Prompt-orchestration dashboard — the full World System prompt surface.

Rebuild / superset of ``prompt_coverage_slideshow.py``. Where the old tool
only rendered Layer-2 event narrations, this walks EVERY prompt family the
World System sends to an LLM and, for each, surfaces the things that have
repeatedly turned out to be wrong:

  - the OUTPUT-TAG CONTRACT (what the prompt asks the model to emit, and
    how it is consumed) — because significance is NOT the universal output
    tag, and each tier has its own contract;
  - the TAG-INJECTION MODE (dynamic-from-library / hardcoded / runtime /
    none) — so drift between the injected allow-list and the enforced one
    is visible at a glance;
  - ENFORCEMENT (are returned tags validated against a library, or stored
    as-is?) — WMS enforces, WNS and WES do not;
  - GAPS — literal PLACEHOLDER text, unresolved ``${var}`` template holes,
    and injected-but-unenforced tag lists.

It also renders a real assembled SAMPLE per prompt so you can "almost run
the prompt system" and read what the model actually receives.

Usage:
    python tools/prompt_orchestration_dashboard.py           # writes HTML next to this file
    python tools/prompt_orchestration_dashboard.py --out X.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CONFIG = os.path.join(_ROOT, "world_system", "config")

from world_system.world_memory.prompt_assembler import PromptAssembler  # noqa: E402
from world_system.world_memory import tag_library as WMS_TAGS  # noqa: E402

# WNS pieces (optional — degrade gracefully if the tree isn't present).
try:
    from world_system.wns.nl_weaver import NLWeaver
    from world_system.wns.narrative_tag_library import NarrativeTagLibrary
    _WNS_OK = True
except Exception:  # pragma: no cover - defensive
    _WNS_OK = False


# ── Live fix-state detection ─────────────────────────────────────────
# The dashboard self-checks the code for the audit fixes so it shows green
# when a gap is closed and RED AGAIN if the fix is ever reverted — a
# regression check, not a static claim.

def _src(rel: str) -> str:
    try:
        with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


_NLW_SRC = _src("world_system/wns/nl_weaver.py")
_HUB_SRC = _src("world_system/wes/llm_tiers/llm_execution_hub.py")
_PLN_SRC = _src("world_system/wes/llm_tiers/llm_execution_planner.py")
_CC_SRC = _src("world_system/wns/cascading_context.py")

FIX_C1_WNS_ENFORCES = "_validate_content_tags" in _NLW_SRC
FIX_C2_PLANNER_THREADS = '"thread_headlines"' in _PLN_SRC
FIX_Mn1_HUB_MARKS_EMPTY = "(no recent WMS events)" in _HUB_SRC
FIX_C3_CHILD_CTX = "get_lower_snapshot_aggregated" in _CC_SRC
FIX_M1_WORLD_CASCADE = "render_world_dominant" in _CC_SRC
FIX_M2_REGISTRY_COUNTS = "_registry_counts_summary" in _PLN_SRC


# ── Small helpers ────────────────────────────────────────────────────

_VAR_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _load(name: str) -> Dict[str, Any]:
    with open(os.path.join(_CONFIG, name), encoding="utf-8") as f:
        return json.load(f)


def _walk_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _count_placeholders(obj: Any) -> int:
    """Count PLACEHOLDER only in prompt-bearing content. Skips the top-level
    ``_meta`` block, where 'PLACEHOLDER_LEDGER.md §N' doc-refs live and never
    reach the model."""
    if isinstance(obj, dict):
        obj = {k: v for k, v in obj.items() if k != "_meta"}
    return sum(s.count("PLACEHOLDER") for s in _walk_strings(obj))


def _find_vars(*texts: str) -> List[str]:
    seen: List[str] = []
    for t in texts:
        for m in _VAR_RE.findall(t or ""):
            if m not in seen:
                seen.append(m)
    return seen


# ── Which ${vars} the runtime actually provides (from the code) ──────
# Sourced by reading the substitution call sites. A ${var} in a template
# that is NOT in this set assembles into the live prompt as a literal
# "${var}" — a real gap. Keep in sync with the assemblers.

WNS_PROVIDED_VARS = {
    # nl_weaver._build_user_prompt substitution map
    "address", "geo_context", "self_narrative", "self_active_threads",
    "lower_primary_narrative", "lower_primary_threads", "lower_fading_narrative",
    "wms_context", "above_primary_address", "above_primary_narrative",
    "above_primary_threads", "above_fading_narrative",
    "world_framing",  # M1 cascade-down (weaver_ctx.world_dominant)
    # legacy slots still substituted
    "lower_narrative", "parent_narrative", "threads_in_scope",
}
# WES build variables. Verified against the substitution call sites:
#   - supervisor: llm_supervisor.py var dict (firing_address from scope_hint)
#   - tools: llm_executor_tool.py from ExecutorSpec
#   - planner/hub: from bundle / plan step
WES_PROVIDED_VARS = {
    # executor tools
    "spec_id", "plan_step_id", "item_intent", "hard_constraints",
    "flavor_hints", "cross_ref_hints",
    # supervisor (verified llm_supervisor.py:161 + var dict)
    "behavior_signal_summary", "bundle_directive", "bundle_firing_tier",
    "firing_address", "plan_abandoned", "plan_id", "plan_rationale",
    "plan_steps", "staged_counts", "tier_log_blob", "trigger_archetype",
    # planner / hub bundle-slice vars (per trace 09/10 context contract)
    "firing_narrative", "parent_narratives", "geographic_chain",
    "thread_fragments", "wms_events_summary", "behavior_flavor",
    "plan_step", "purpose", "count", "registry_context", "recent_registry_entries",
    "directive_text", "scope_hint", "co_emitted", "live_context",
    # planner (verified llm_execution_planner.py:238-249)
    "bundle_id", "firing_tier", "bundle_narrative_context",
    "bundle_parent_summaries", "bundle_delta",
    "registry_counts", "prior_rerun_feedback",
    # 'thread_headlines' is added below IFF the planner fix is live — so the
    # dashboard re-flags C2 automatically if the fix is reverted.
    # quest-reward pregen/adapt (verified quest_reward_adapter.py)
    "quest_id", "quest_title", "narrative", "objectives", "rewards_prose",
    "player_level", "player_stats", "expiration", "pre_generated_rewards",
    "time_taken_seconds", "tier",
}
if FIX_C2_PLANNER_THREADS:                 # C2 fix live → planner supplies it
    WES_PROVIDED_VARS = WES_PROVIDED_VARS | {"thread_headlines"}
# Hubs supply the bundle-slice narrative vars the planner omits (verified
# llm_execution_hub.py:288-305), incl. thread_headlines.
HUB_PROVIDED_VARS = WES_PROVIDED_VARS | {
    # verified llm_execution_hub.py:279-302
    "step_intent", "step_slots", "address_hint", "thread_headlines",
    "parent_thread_headlines", "thread_fragments", "parent_thread_fragments",
    "parent_narratives", "wms_events_summary", "npc_dialogue_summary",
    "firing_narrative", "geographic_chain", "behavior_flavor",
    "plan_step_body", "batch_size",
}


# ── Prompt cards ─────────────────────────────────────────────────────


class Card:
    def __init__(self, family: str, ident: str, scope: str, backend: str,
                 injection: str, enforced: Optional[bool],
                 output_contract: str, system: str, user: str,
                 gaps: List[str], vars_used: List[str]):
        self.family = family
        self.ident = ident
        self.scope = scope
        self.backend = backend
        self.injection = injection
        self.enforced = enforced
        self.output_contract = output_contract
        self.system = system
        self.user = user
        self.gaps = gaps
        self.vars_used = vars_used


def _unresolved_vars(vars_used: List[str], provided: set) -> List[str]:
    return [v for v in vars_used if v not in provided]


# ---- WMS Layer 2 (event narration) ---------------------------------

def _wms_l2_card(asm: PromptAssembler) -> Card:
    tags = ["domain:combat", "species:wolf_grey", "tier:1",
            "attack_type:melee", "result:critical"]
    data = ("Event: enemy_killed (killed_wolf_grey)\nCount today: 8\n"
            "All-time: 47\nLocation: Whispering Woods")
    p = asm.assemble(tags, data_block=data)
    return Card(
        family="WMS — memory", ident="L2 event narration",
        scope="one event", backend="wms_layer2 (Haiku)",
        injection="significance hardcoded in _output; content tags are "
                  "code-assigned at capture (not LLM-chosen)",
        enforced=True,
        output_contract="narrative (1 sentence) + significance:"
                        "{minor…critical} → parsed to SEVERITY. "
                        "Content tags are NOT re-emitted here.",
        system=p.system, user=p.user, gaps=[], vars_used=[],
    )


# ---- WMS Layers 3–7 (consolidation / summarization) ----------------

_WMS_HIGHER = {
    3: ("district", lambda a: a.assemble_l3("regional_synthesis",
        "<district name=\"Western Frontier\">…3 district events…</district>")),
    4: ("province", lambda a: a.assemble_l4(
        "<province>…</province>", event_tags=["domain:combat", "domain:gathering"])),
    5: ("region", lambda a: a.assemble_l5(
        "<region>…</region>", event_tags=["domain:combat", "domain:gathering"])),
    6: ("nation", lambda a: a.assemble_l6(
        "<nation>…</nation>", event_tags=["domain:combat"])),
    7: ("world", lambda a: a.assemble_l7(
        "<world>…</world>", event_tags=["domain:combat"])),
}


def _wms_higher_card(asm: PromptAssembler, layer: int) -> Card:
    scope, fn = _WMS_HIGHER[layer]
    p = fn(asm)
    cats = WMS_TAGS.get_llm_assignable_categories_for_layer(layer)
    new = WMS_TAGS.get_new_llm_assignable_at_layer(layer)
    contract = (f"narrative + rewritten tag list: carries content tags up, "
                f"then may ADD from {len(cats)} interpretive categories "
                f"({len(new)} new at this scope). significance→severity. "
                f"Address tags are code-preserved, never emitted.")
    return Card(
        family="WMS — memory", ident=f"L{layer} {scope} summary",
        scope=scope, backend=f"wms_layer{layer}",
        injection="DYNAMIC — {{TAG_ALLOWLIST}} generated live from "
                  "tag_library (single source of truth the parser enforces)",
        enforced=True,
        output_contract=contract,
        system=p.system, user=p.user, gaps=[], vars_used=[],
    )


# ---- WNS NL2–NL7 (narrative weaving) -------------------------------

def _wns_card(layer: int, ntl) -> Card:
    frag = _load(f"narrative_fragments_nl{layer}.json")
    wms = _load("prompt_fragments.json")
    system = user = ""
    gaps: List[str] = []
    if _WNS_OK:
        w = object.__new__(NLWeaver)
        w._layer = layer
        w._tag_library = ntl
        w._prompt_fragments = frag
        w._wms_fragments = wms
        try:
            system = w._build_system_prompt(
                firing_tags=["tier:2", "domain:combat", "species:wolf_dire"])
        except Exception as e:  # pragma: no cover
            system = f"(sample assembly failed: {e})"
    core = frag.get("_core", {})
    user_tmpl = core.get("user_template", "") if isinstance(core, dict) else ""
    user = user_tmpl
    vars_used = _find_vars(user_tmpl)
    unresolved = _unresolved_vars(vars_used, WNS_PROVIDED_VARS)
    ph = _count_placeholders(frag)
    if ph:
        gaps.append(f"{ph} PLACEHOLDER string(s) in fragments")
    if unresolved:
        gaps.append(f"template vars not provided by weaver: "
                    f"{', '.join(unresolved)}")
    # C1: fixed 2026-08 — _validate_content_tags now runs at both storage
    # sites, accepting WNS-or-WMS tags and dropping only invented ones. The
    # flag self-checks the source, so this re-reddens if the fix is reverted.
    if not FIX_C1_WNS_ENFORCES:
        gaps.append("C1: output tags NOT enforced — validate_tag() never "
                    "called; content_tags stored as-is (nl_weaver.py:666,877)")
    if layer >= 3 and not FIX_C3_CHILD_CTX:
        # C3: fixed 2026-08 — build_weaver_context now aggregates lower-layer
        # context from CHILD addresses (get_lower_snapshot_aggregated).
        gaps.append("C3: ${lower_primary_narrative}/${lower_primary_threads} "
                    "are structurally ALWAYS empty (exact-address query vs "
                    "descendant rows), but the template reads as if populated")
    if layer == 7 and not FIX_M1_WORLD_CASCADE:
        # M1: fixed 2026-08 — dominant_* persisted + cascaded DOWN as world
        # framing (render_world_dominant / ${world_framing} in NL2-6).
        gaps.append("M1: NL7 asks for dominant_arcs/regions/factions + severity "
                    "but run_weaving never reads them — tokens wasted")
    scope = frag.get("_meta", {}).get("purpose", "").split(" - ")[0]
    extra = (" + dominant_arcs/regions/factions + severity"
             if layer == 7 else "")
    contract = (f"narrative + threads[] (content_tags) + top-level tags{extra}; "
                f"DYNAMIC allow-list from narrative_tag_library "
                f"(thread_stage/tone/relationship/narrative_domain/agency/"
                f"emergent_entity)")
    return Card(
        family="WNS — narrative", ident=f"NL{layer} weaver",
        scope=scope or f"NL{layer}", backend=f"wns_layer{layer}",
        injection="DYNAMIC — {{TAG_ALLOWLIST}} from narrative_tag_library",
        enforced=FIX_C1_WNS_ENFORCES,
        output_contract=contract,
        system=system, user=user, gaps=gaps, vars_used=vars_used,
    )


# ---- WES executor tools & hubs -------------------------------------

_WES_TOOLS = ["materials", "hostiles", "nodes", "skills", "chunks",
              "npcs", "quests", "titles"]


def _wes_tool_card(name: str) -> Card:
    frag = _load(f"prompt_fragments_tool_{name}.json")
    core = frag.get("_core", {})
    system = core.get("system", "") if isinstance(core, dict) else ""
    user = core.get("user_template", "") if isinstance(core, dict) else ""
    out = frag.get("_output", {})
    schema = out.get("schema_description", "") if isinstance(out, dict) else ""
    vars_used = _find_vars(system, user)
    unresolved = _unresolved_vars(vars_used, WES_PROVIDED_VARS)
    gaps: List[str] = []
    ph = _count_placeholders(frag)
    if ph:
        gaps.append(f"{ph} PLACEHOLDER string(s)")
    if unresolved:
        gaps.append(f"template vars maybe unresolved: {', '.join(unresolved)}")
    has_taglist = "TAG ALLOW-LIST" in system or "tags" in schema.lower()
    if has_taglist:
        gaps.append("tag list is HARDCODED (no library) and output tags are "
                    "NOT validated; 'NEW:' proposal mechanism unimplemented")
    injection = ("HARDCODED content-tag allow-list in _core.system"
                 if "TAG ALLOW-LIST" in system else "no explicit tag list")
    return Card(
        family="WES — content gen", ident=f"tool:{name}",
        scope="one entity", backend=f"wes_tool_{name}",
        injection=injection, enforced=False,
        output_contract=(schema or "(one content JSON object)"),
        system=system, user=user, gaps=gaps, vars_used=vars_used,
    )


def _wes_hub_card(name: str) -> Card:
    frag = _load(f"prompt_fragments_hub_{name}.json")
    core = frag.get("_core", {})
    system = core.get("system", "") if isinstance(core, dict) else ""
    user = core.get("user_template", "") if isinstance(core, dict) else ""
    vars_used = _find_vars(system, user)
    unresolved = _unresolved_vars(vars_used, HUB_PROVIDED_VARS)
    gaps: List[str] = []
    ph = _count_placeholders(frag)
    if ph:
        gaps.append(f"{ph} PLACEHOLDER string(s)")
    if unresolved:
        gaps.append(f"template vars maybe unresolved: {', '.join(unresolved)}")
    # Mn1: fixed 2026-08 — renderers now emit (none)/(no recent …) markers.
    if not FIX_Mn1_HUB_MARKS_EMPTY:
        gaps.append("Mn1: empty parent_narratives/wms_events/npc_dialogue "
                    "render as blank labeled sections (no '(none)' marker)")
    return Card(
        family="WES — content gen", ident=f"hub:{name}",
        scope="tool batch", backend=f"wes_hub_{name}",
        injection="carries bundle-slice narrative context to the tool batch",
        enforced=None,
        output_contract="XML batch of ExecutorSpecs (one per entity to make)",
        system=system, user=user, gaps=gaps, vars_used=vars_used,
    )


# Curated verified findings for the control prompts, keyed by label.
# M2: fixed 2026-08 — registry_counts now pulls live counts
# (_registry_counts_summary); flag only re-appears if that fix is reverted.
_MISC_FINDINGS = {}
if not FIX_M2_REGISTRY_COUNTS:
    _MISC_FINDINGS["planner"] = [
        "M2: ${registry_counts} is a hardcoded 'n/a' stub "
        "(llm_execution_planner.py:247) — the model is asked to reason about "
        "registry density it is always told is n/a",
    ]


def _wes_misc_card(fname: str, label: str) -> Optional[Card]:
    try:
        frag = _load(fname)
    except FileNotFoundError:
        return None
    core = frag.get("_core", {})
    system = core.get("system", "") if isinstance(core, dict) else (
        core if isinstance(core, str) else json.dumps(core)[:800])
    user = core.get("user_template", "") if isinstance(core, dict) else ""
    # scan every string in the fragment for ${vars} — control prompts often
    # hold their template in a field other than _core.user_template.
    vars_used = _find_vars(*[s for s in _walk_strings(
        {k: v for k, v in frag.items() if k != "_meta"})])
    unresolved = _unresolved_vars(vars_used, WES_PROVIDED_VARS)
    gaps: List[str] = []
    ph = _count_placeholders(frag)
    if ph:
        gaps.append(f"{ph} PLACEHOLDER string(s)")
    if unresolved:
        tag = ("C2: " if (label == "planner" and
                          "thread_headlines" in unresolved) else "")
        gaps.append(f"{tag}template var(s) reach the model UNRESOLVED: "
                    f"{', '.join('${%s}' % v for v in unresolved)}")
    gaps.extend(_MISC_FINDINGS.get(label, []))
    return Card(
        family="WES — orchestration", ident=label, scope="plan-level",
        backend=label, injection="n/a (control prompt)", enforced=None,
        output_contract="(see schema in fragment)", system=system,
        user=user, gaps=gaps, vars_used=vars_used,
    )


# ── Build all cards ──────────────────────────────────────────────────

def build_cards() -> List[Card]:
    asm = PromptAssembler()
    asm.load()
    cards: List[Card] = [_wms_l2_card(asm)]
    for layer in (3, 4, 5, 6, 7):
        try:
            cards.append(_wms_higher_card(asm, layer))
        except Exception as e:  # pragma: no cover
            cards.append(Card("WMS — memory", f"L{layer}", "?", "?", "?",
                              True, "(assembly failed)", "", str(e), [], []))
    ntl = NarrativeTagLibrary.get_instance() if _WNS_OK else None
    for layer in (2, 3, 4, 5, 6, 7):
        try:
            cards.append(_wns_card(layer, ntl))
        except Exception as e:  # pragma: no cover
            cards.append(Card("WNS — narrative", f"NL{layer}", "?", "?", "?",
                              False, "(assembly failed)", "", str(e), [], []))
    for name in _WES_TOOLS:
        try:
            cards.append(_wes_tool_card(name))
        except Exception as e:  # pragma: no cover
            cards.append(Card("WES — content gen", f"tool:{name}", "?", "?",
                              "?", False, "(load failed)", "", str(e), [], []))
    for name in _WES_TOOLS:
        try:
            cards.append(_wes_hub_card(name))
        except FileNotFoundError:
            pass
        except Exception as e:  # pragma: no cover
            cards.append(Card("WES — content gen", f"hub:{name}", "?", "?",
                              "?", None, "(load failed)", "", str(e), [], []))
    for fname, label in [
        ("prompt_fragments_wes_execution_planner.json", "planner"),
        ("prompt_fragments_wes_supervisor.json", "supervisor"),
        ("prompt_fragments_wes_quest_reward_pregen.json", "quest_reward:pregen"),
        ("prompt_fragments_wes_quest_reward_adapt.json", "quest_reward:adapt"),
    ]:
        c = _wes_misc_card(fname, label)
        if c:
            cards.append(c)
    return cards


_CODE_RE = re.compile(r"\b(C\d|Mn\d|M\d)\b")


def health(cards: List[Card]) -> Dict[str, Any]:
    fams: Dict[str, int] = {}
    codes: Dict[str, int] = {}
    placeholder_gaps = 0
    unresolved_var_prompts = 0
    unenforced_prompts = 0
    for c in cards:
        fams[c.family] = fams.get(c.family, 0) + 1
        seen_codes = set()
        for g in c.gaps:
            for m in _CODE_RE.findall(g):
                seen_codes.add(m)
            if "PLACEHOLDER" in g:
                placeholder_gaps += 1
            if "UNRESOLVED" in g:
                unresolved_var_prompts += 1
            if "NOT enforced" in g or "NOT validated" in g:
                unenforced_prompts += 1
        for m in seen_codes:
            codes[m] = codes.get(m, 0) + 1
    return {
        "total": len(cards),
        "by_family": fams,
        "codes": dict(sorted(codes.items())),
        "placeholder_gaps": placeholder_gaps,
        "unresolved_var_prompts": unresolved_var_prompts,
        "unenforced_prompts": unenforced_prompts,
        "enforced_families": sorted({c.family for c in cards if c.enforced}),
        "unenforced_families": sorted(
            {c.family for c in cards if c.enforced is False}),
    }


# ── HTML rendering ───────────────────────────────────────────────────

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>WMS/WNS/WES Prompt Orchestration</title>
<style>
 body {{ background:#14161a; color:#d7dae0; font-family:Consolas,monospace; margin:0; }}
 .slide {{ display:none; padding:22px 40px 60px; }}
 .slide.active {{ display:block; }}
 h1 {{ color:#7fd4a8; font-size:17px; margin:0 0 2px; }}
 h2 {{ color:#9ab0d0; font-size:13px; font-weight:normal; margin:0 0 12px; }}
 .row {{ margin:8px 0; }}
 .k {{ color:#8a93a3; display:inline-block; width:130px; vertical-align:top; }}
 .chip {{ display:inline-block; background:#243040; border:1px solid #3d5470;
          border-radius:10px; padding:1px 9px; margin:1px; font-size:12px; }}
 .ok {{ color:#7fd4a8; }} .bad {{ color:#e88; }} .warn {{ color:#e8c07f; }}
 .gap {{ background:#402424; border:1px solid #7a5050; border-radius:6px;
         padding:2px 10px; margin:3px 0; font-size:12px; color:#f0b8b8; }}
 pre {{ background:#1b1f26; border:1px solid #2c3340; border-radius:6px;
        padding:10px; white-space:pre-wrap; font-size:11.5px; max-height:34vh;
        overflow:auto; }}
 table {{ border-collapse:collapse; font-size:13px; }}
 td, th {{ border:1px solid #2c3340; padding:4px 12px; text-align:left; }}
 .nav {{ position:fixed; bottom:10px; right:20px; color:#8a93a3; font-size:13px; }}
</style></head><body>
{slides}
<div class="nav">&#8592;/&#8594; or click &mdash; <span id="cur">1</span>/{n}</div>
<script>
 const s=document.querySelectorAll('.slide'); let i=0;
 function show(k){{i=Math.max(0,Math.min(s.length-1,k));
   s.forEach((x,j)=>x.classList.toggle('active',j===i));
   document.getElementById('cur').textContent=i+1;}}
 document.addEventListener('keydown',e=>{{
   if(e.key==='ArrowRight'||e.key===' ')show(i+1);
   if(e.key==='ArrowLeft')show(i-1);}});
 document.addEventListener('click',()=>show(i+1)); show(0);
</script></body></html>"""


def _enf(v: Optional[bool]) -> str:
    if v is True:
        return "<span class='ok'>ENFORCED (validate_tag drops invalid)</span>"
    if v is False:
        return "<span class='bad'>NOT enforced (stored as-is)</span>"
    return "<span class='warn'>n/a</span>"


def render(cards: List[Card], h: Dict[str, Any]) -> str:
    slides: List[str] = []
    # Summary slide
    fam_rows = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{v} prompts</td></tr>"
        for k, v in h["by_family"].items())
    slides.append(
        "<div class='slide'><h1>Prompt orchestration — health</h1>"
        "<h2>Every LLM prompt the World System sends, with its output-tag "
        "contract, injection mode, enforcement, and gaps.</h2>"
        f"<table><tr><th>Total prompts</th><td>{h['total']}</td></tr>"
        f"{fam_rows}"
        f"<tr><th>Enforce output tags</th><td class='ok'>"
        f"{', '.join(h['enforced_families']) or '(none)'}</td></tr>"
        f"<tr><th>Do NOT enforce</th><td class='bad'>"
        f"{', '.join(h['unenforced_families']) or '(none)'}</td></tr>"
        f"<tr><th>Prompts with unenforced output tags</th>"
        f"<td class='bad'>{h['unenforced_prompts']}</td></tr>"
        f"<tr><th>Prompts leaking an unresolved ${{var}}</th>"
        f"<td class='bad'>{h['unresolved_var_prompts']}</td></tr>"
        f"<tr><th>PLACEHOLDER leaks</th><td>{h['placeholder_gaps']}</td></tr>"
        f"<tr><th>Verified findings (prompts affected)</th><td>"
        + ", ".join(f"{k}&times;{v}" for k, v in h['codes'].items())
        + "</td></tr></table>"
        "<div class='row' style='margin-top:14px;color:#8a93a3'>Arrow keys to "
        "step through each prompt. Red boxes are gaps.</div></div>")

    for c in cards:
        gaps = "".join(f"<div class='gap'>&#9888; {html.escape(g)}</div>"
                       for g in c.gaps) or \
               "<div class='row ok'>no static gaps detected</div>"
        vars_ = "".join(f"<span class='chip'>${{{html.escape(v)}}}</span>"
                        for v in c.vars_used) or "<span class='k'>none</span>"
        slides.append(
            f"<div class='slide'><h1>{html.escape(c.family)} &mdash; "
            f"{html.escape(c.ident)}</h1>"
            f"<h2>scope: {html.escape(c.scope)} &nbsp;|&nbsp; backend: "
            f"{html.escape(c.backend)}</h2>"
            f"<div class='row'><span class='k'>output contract</span>"
            f"{html.escape(c.output_contract)}</div>"
            f"<div class='row'><span class='k'>tag injection</span>"
            f"{html.escape(c.injection)}</div>"
            f"<div class='row'><span class='k'>enforcement</span>{_enf(c.enforced)}</div>"
            f"<div class='row'><span class='k'>template vars</span>{vars_}</div>"
            f"<div class='row'><span class='k'>gaps</span></div>{gaps}"
            f"<div class='row'><b>SYSTEM</b><pre>{html.escape(c.system[:6000])}</pre></div>"
            + (f"<div class='row'><b>USER template</b><pre>{html.escape(c.user[:3000])}</pre></div>"
               if c.user else "")
            + "</div>")
    return _PAGE.format(slides="\n".join(slides), n=len(slides))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        _THIS, "prompt_orchestration_dashboard.html"))
    args = ap.parse_args()
    cards = build_cards()
    h = health(cards)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(cards, h))
    print(f"Wrote {args.out}")
    print(f"  prompts: {h['total']}  families: {len(h['by_family'])}")
    print(f"  enforced: {', '.join(h['enforced_families'])}")
    print(f"  NOT enforced: {', '.join(h['unenforced_families'])}")
    print(f"  unenforced-output-tag prompts: {h['unenforced_prompts']}  "
          f"unresolved-var prompts: {h['unresolved_var_prompts']}  "
          f"placeholder leaks: {h['placeholder_gaps']}")
    print(f"  verified findings: "
          + ", ".join(f"{k}x{v}" for k, v in h['codes'].items()))
    # console gap digest
    for c in cards:
        if c.gaps:
            print(f"  [{c.ident}] " + "; ".join(c.gaps))


if __name__ == "__main__":
    main()
