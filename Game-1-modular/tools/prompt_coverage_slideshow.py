"""Prompt-coverage slideshow — representative WMS prompt samples.

Instead of hand-clicking tag permutations in Prompt Studio, this tool
computes a MINIMAL set of representative assembled prompts that covers
every prompt fragment at least once, in a VALID context — then renders
them as a self-contained HTML slideshow (arrow keys / click to step).

The math (2026-07-11, user-directed):
- The fragment space is NOT a plain permutation grid: fragments only
  make sense in certain company (species fragments ride combat domains,
  disciplines ride crafting, factions ride social...). A COMPATIBILITY
  MAP restricts which categories may co-occur with which domain, so no
  slide shows a nonsense combination.
- Fragments are NOT equally important: each category carries a WEIGHT.
  Slide selection is weighted greedy set-cover — each new slide is the
  compatible combination covering the largest weighted mass of not-yet-
  covered fragments. High-weight categories (domain, species,
  discipline, faction) are guaranteed early, low-weight tails pack into
  later slides.
- Deterministic: same fragments file -> same slideshow.

Usage:
    python tools/prompt_coverage_slideshow.py            # writes HTML next to this file
    python tools/prompt_coverage_slideshow.py --out X.html --max-slides 40
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from typing import Dict, List, Tuple

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from world_system.world_memory.prompt_assembler import PromptAssembler  # noqa: E402


# ── Weights: not all fragments are worth the same ────────────────────
# Designer-tunable. Higher weight = covered earlier, more slides give
# it context variety.
CATEGORY_WEIGHTS: Dict[str, float] = {
    "domain": 3.0,
    "species": 2.5,
    "discipline": 2.5,
    "faction": 2.5,
    "element": 2.0,
    "status_effect": 2.0,
    "material_category": 2.0,
    "attack_type": 1.5,
    "item_category": 1.5,
    "resource": 1.5,
    "npc": 1.5,
    "affinity": 1.5,
    "interaction": 1.5,
    "tier": 1.0,
    "rarity": 1.0,
    "result": 1.0,
    "action": 1.0,
    "quality": 1.0,
    "rank": 1.0,
    "tool": 1.0,
    "source": 1.0,
}

# ── Compatibility: which categories may ride which domain ────────────
# "*" = compatible with every domain (global axes).
DOMAIN_COMPAT: Dict[str, List[str]] = {
    "combat": ["species", "element", "status_effect", "attack_type",
               "rank", "result"],
    "gathering": ["resource", "material_category", "tool", "result"],
    "crafting": ["discipline", "material_category", "item_category",
                 "quality", "result"],
    "social": ["faction", "npc", "affinity", "interaction"],
    "economy": ["item_category", "faction", "npc"],
    "progression": ["rank", "result"],
    "exploration": ["source", "result"],
    "skills": ["element", "status_effect", "action"],
    "items": ["item_category", "rarity", "quality"],
    "fishing": ["species", "tool", "result", "quality"],
    "dungeon": ["species", "rank", "source"],
}
GLOBAL_CATS = ["tier", "rarity", "action", "source"]
MAX_SECONDARIES_PER_SLIDE = 5

# Representative data block per domain so the USER prompt reads real.
DATA_BLOCKS: Dict[str, str] = {
    "combat": ("Event: combat (kill)\nTrigger count: 25\n"
               "Location: Whispering Woods\nContext: sustained culling."),
    "gathering": ("Event: resource_gathered\nTrigger count: 40\n"
                  "Location: riverbank\nContext: steady logging."),
    "crafting": ("Event: craft_attempted\nTrigger count: 12\n"
                 "Location: village forge\nContext: a smithing surge."),
    "social": ("Event: npc_dialogue\nTrigger count: 8\n"
               "Location: harbor town\nContext: rumors of raiders."),
    "_default": ("Event: activity\nTrigger count: 10\n"
                 "Context: a notable pattern emerged."),
}


def _compatible_domains(category: str) -> List[str]:
    return [d for d, cats in DOMAIN_COMPAT.items() if category in cats]


def build_slides(assembler: PromptAssembler,
                 max_slides: int) -> Tuple[List[dict], dict]:
    """Weighted greedy set-cover over the live fragment inventory."""
    by_cat: Dict[str, List[str]] = {}
    for key in assembler.list_keys():
        if key.startswith("_") or ":" not in key:
            continue
        cat, val = key.split(":", 1)
        by_cat.setdefault(cat, []).append(val)
    for vals in by_cat.values():
        vals.sort()

    uncovered: Dict[str, float] = {}
    for cat, vals in by_cat.items():
        w = CATEGORY_WEIGHTS.get(cat, 1.0)
        for v in vals:
            uncovered[f"{cat}:{v}"] = w

    domains = list(by_cat.get("domain", []))
    slides: List[dict] = []

    while uncovered and len(slides) < max_slides:
        # Candidate per domain: pack the highest-weight uncovered
        # compatible fragments into one slide.
        best = None
        for domain in domains:
            tags = []
            score = 0.0
            dkey = f"domain:{domain}"
            if dkey in uncovered:
                score += uncovered[dkey]
            tags.append(dkey)
            compat = DOMAIN_COMPAT.get(domain, []) + GLOBAL_CATS
            # pick at most one uncovered value per compatible category,
            # highest weight first
            candidates = []
            for cat in compat:
                for v in by_cat.get(cat, []):
                    k = f"{cat}:{v}"
                    if k in uncovered:
                        candidates.append((uncovered[k], k, cat))
            candidates.sort(reverse=True)
            # Large categories (faction:15, species:13, status_effect:13)
            # may pack several values per slide, or their tail never
            # fits — a narration can legitimately mention two factions.
            used_per_cat: Dict[str, int] = {}
            for w, k, cat in candidates:
                cap = 1 + len(by_cat.get(cat, [])) // 8
                if used_per_cat.get(cat, 0) >= cap:
                    continue
                if len(tags) - 1 >= MAX_SECONDARIES_PER_SLIDE + 2:
                    break
                tags.append(k)
                used_per_cat[cat] = used_per_cat.get(cat, 0) + 1
                score += w
            if best is None or score > best[0]:
                best = (score, domain, tags)

        score, domain, tags = best
        if score <= 0:
            break  # nothing compatible remains coverable
        for t in tags:
            uncovered.pop(t, None)

        data_block = DATA_BLOCKS.get(domain, DATA_BLOCKS["_default"])
        prompt = assembler.assemble(tags, data_block=data_block)
        used_keys = [k for k, _ in prompt.fragments_used]
        slides.append({
            "index": len(slides) + 1,
            "domain": domain,
            "tags": tags,
            "fragments_used": used_keys,
            "missing": [t for t in tags if t not in used_keys
                        and not t.startswith("_")],
            "system": prompt.system,
            "user": prompt.user,
            "tokens": prompt.token_estimate,
            "covered_weight": round(score, 2),
        })

    total = sum(CATEGORY_WEIGHTS.get(k.split(":")[0], 1.0)
                for cat, vals in by_cat.items() for k in
                (f"{cat}:{v}" for v in vals))
    stats = {
        "fragments_total": sum(len(v) for v in by_cat.values()),
        "fragments_covered": sum(len(v) for v in by_cat.values()) - len(uncovered),
        "weight_total": round(total, 1),
        "weight_uncovered": round(sum(uncovered.values()), 1),
        "uncovered_keys": sorted(uncovered.keys()),
        "slides": len(slides),
    }
    return slides, stats


_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>WMS Prompt Coverage Slideshow</title>
<style>
 body {{ background:#14161a; color:#d7dae0; font-family:Consolas,monospace;
        margin:0; }}
 .slide {{ display:none; padding:24px 40px; }}
 .slide.active {{ display:block; }}
 h1 {{ color:#7fd4a8; font-size:18px; }}
 .chip {{ display:inline-block; background:#243040; border:1px solid #3d5470;
         border-radius:10px; padding:2px 10px; margin:2px; font-size:12px; }}
 .chip.missing {{ background:#402424; border-color:#705050; }}
 .meta {{ color:#8a93a3; font-size:12px; margin:6px 0; }}
 pre {{ background:#1b1f26; border:1px solid #2c3340; border-radius:6px;
       padding:12px; white-space:pre-wrap; font-size:12px; max-height:38vh;
       overflow:auto; }}
 .nav {{ position:fixed; bottom:12px; right:20px; color:#8a93a3;
        font-size:13px; }}
 table {{ border-collapse:collapse; font-size:13px; }}
 td, th {{ border:1px solid #2c3340; padding:4px 12px; }}
</style></head><body>
{slides_html}
<div class="nav">&#8592;/&#8594; or click to navigate &mdash; slide
 <span id="cur">1</span>/{n}</div>
<script>
 const slides = document.querySelectorAll('.slide');
 let i = 0;
 function show(k) {{
   i = Math.max(0, Math.min(slides.length - 1, k));
   slides.forEach((s, j) => s.classList.toggle('active', j === i));
   document.getElementById('cur').textContent = i + 1;
 }}
 document.addEventListener('keydown', e => {{
   if (e.key === 'ArrowRight' || e.key === ' ') show(i + 1);
   if (e.key === 'ArrowLeft') show(i - 1);
 }});
 document.addEventListener('click', () => show(i + 1));
 show(0);
</script></body></html>"""


def render_html(slides: List[dict], stats: dict) -> str:
    parts = []
    # Summary slide
    unc = "".join(f"<span class='chip missing'>{html.escape(k)}</span>"
                  for k in stats["uncovered_keys"]) or "(none)"
    parts.append(
        "<div class='slide'><h1>Coverage summary</h1>"
        f"<table><tr><th>Fragments covered</th>"
        f"<td>{stats['fragments_covered']} / {stats['fragments_total']}</td></tr>"
        f"<tr><th>Weighted mass uncovered</th>"
        f"<td>{stats['weight_uncovered']} / {stats['weight_total']}</td></tr>"
        f"<tr><th>Slides</th><td>{stats['slides']}</td></tr></table>"
        f"<div class='meta'>Uncovered (raise --max-slides or fix "
        f"compatibility map): {unc}</div>"
        "<div class='meta'>Each slide = one representative assembled "
        "prompt. Chips = requested tags; red = tag had no fragment "
        "(silent-drop candidates).</div></div>"
    )
    for s in slides:
        chips = "".join(
            f"<span class='chip{' missing' if t in s['missing'] else ''}'>"
            f"{html.escape(t)}</span>" for t in s["tags"])
        frags = ", ".join(html.escape(k) for k in s["fragments_used"])
        parts.append(
            f"<div class='slide'><h1>#{s['index']} &mdash; "
            f"{html.escape(s['domain'])}</h1>"
            f"<div>{chips}</div>"
            f"<div class='meta'>fragments used: {frags} &mdash; "
            f"~{s['tokens']} tokens &mdash; weighted coverage "
            f"{s['covered_weight']}</div>"
            f"<b>SYSTEM</b><pre>{html.escape(s['system'])}</pre>"
            f"<b>USER</b><pre>{html.escape(s['user'])}</pre></div>"
        )
    return _PAGE.format(slides_html="\n".join(parts), n=len(slides) + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(_THIS,
                    "prompt_coverage_slideshow.html"))
    ap.add_argument("--max-slides", type=int, default=40)
    args = ap.parse_args()

    assembler = PromptAssembler()
    assembler.load()
    slides, stats = build_slides(assembler, args.max_slides)
    html_text = render_html(slides, stats)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"Wrote {args.out}")
    print(f"  slides: {stats['slides']}  fragments: "
          f"{stats['fragments_covered']}/{stats['fragments_total']} covered")
    if stats["uncovered_keys"]:
        print(f"  UNCOVERED: {', '.join(stats['uncovered_keys'][:12])}"
              f"{' ...' if len(stats['uncovered_keys']) > 12 else ''}")


if __name__ == "__main__":
    main()
