"""
AI context management — budget/truncation guards (2026-07 audit, Phase A).

Design doctrine (WORLD_SYSTEM_WORKING_DOC §8.4): budgets are enforced at
assembly time, and truncation respects content boundaries. These tests pin
the shared text_budget utilities and their integration points:
- WMS L2-L7 data blocks are bounded at the WmsAI choke point (whole-event
  truncation with an <omitted/> marker),
- NPC conversation summaries trim whole snippets (never mid-snippet),
- the assembler counts tags whose fragments are missing instead of
  dropping them silently.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from world_system.world_memory.text_budget import (  # noqa: E402
    truncate_at_boundary,
    clamp_snippet_window,
    clamp_xml_events_to_budget,
)


# ── truncate_at_boundary ─────────────────────────────────────────────

def test_truncate_within_budget_is_identity():
    assert truncate_at_boundary("short text", 100) == "short text"


def test_truncate_prefers_sentence_boundary():
    text = "First sentence here. Second sentence is long. " + "x" * 200
    out = truncate_at_boundary(text, 60)
    assert len(out) <= 60
    # Cut lands after a sentence, not mid-word.
    assert "Second" in out or out.rstrip(" […]").endswith(".")
    assert not out.rstrip(" […]").endswith("x")


def test_truncate_never_cuts_mid_word():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    out = truncate_at_boundary(text, 30)
    core = out.replace(" […]", "")
    # Every emitted word must be a whole word from the source.
    for word in core.split():
        assert word in text.split(), f"mid-word cut produced {word!r}"


# ── clamp_snippet_window (NPC conversation summary) ──────────────────

def test_snippet_window_drops_oldest_whole_snippets():
    snippets = [f"Player: hello {i}. NPC: reply {i}" for i in range(10)]
    summary = " | ".join(snippets)
    out = clamp_snippet_window(summary, 120)
    assert len(out) <= 120
    # Newest snippet survives intact; no partial snippet at the head.
    assert out.endswith("Player: hello 9. NPC: reply 9")
    assert out.split(" | ")[0].startswith("Player: "), (
        f"head is a partial snippet: {out.split(' | ')[0]!r}"
    )


def test_snippet_window_single_oversized_snippet_boundary_truncates():
    out = clamp_snippet_window("word " * 100, 50)
    assert len(out) <= 50


# ── clamp_xml_events_to_budget (WMS data blocks) ─────────────────────

def _xml_block(n_events: int) -> str:
    lines = ['<district name="Testshire">', '  <locality name="Testville">']
    for i in range(n_events):
        lines.append(
            f'    <event category="combat" severity="minor">'
            f'Event number {i} happened with some narrative text.</event>')
    lines += ['  </locality>', '</district>']
    return "\n".join(lines)


def test_xml_clamp_within_budget_unchanged():
    block = _xml_block(3)
    out, omitted = clamp_xml_events_to_budget(block, 10_000)
    assert out == block and omitted == 0


def test_xml_clamp_drops_oldest_events_and_keeps_structure():
    block = _xml_block(40)
    out, omitted = clamp_xml_events_to_budget(block, 1200)
    assert omitted > 0
    assert len(out) <= 1200 + 100  # marker line allowance
    # Structure preserved.
    assert out.startswith('<district')
    assert out.rstrip().endswith('</district>')
    assert '<omitted count="%d"' % omitted in out
    # Newest events survive, oldest dropped.
    assert "Event number 39" in out
    assert "Event number 0" not in out


def test_xml_clamp_no_events_falls_back_to_boundary_truncation():
    block = "just a long plain text " * 50
    out, omitted = clamp_xml_events_to_budget(block, 100)
    assert omitted == 0
    assert len(out) <= 100


# ── WmsAI choke-point integration ────────────────────────────────────

def test_wms_ai_layer_config_has_data_budgets():
    from world_system.world_memory.wms_ai import LAYER_CONFIG
    for layer, cfg in LAYER_CONFIG.items():
        assert cfg.get("data_budget", 0) > 0, f"layer {layer} missing data_budget"


# ── PromptAssembler missing-fragment telemetry ───────────────────────

def test_assembler_counts_missing_fragments():
    from world_system.world_memory.prompt_assembler import PromptAssembler
    pa = PromptAssembler()
    pa.load()
    pa.select_fragments(["species:definitely_not_a_real_species_xyz"])
    assert pa.missing_fragment_tags.get(
        "species:definitely_not_a_real_species_xyz", 0) >= 1, (
        "missing fragment (no fallback) must be counted, not dropped silently"
    )
