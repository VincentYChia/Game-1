"""
crux-foundry — the progression score (SCORING.md), as a PURE, side-effect-free
module so it can be unit-tested without booting the engine. runner.py imports it.

The score is the universal viability currency: how far a persona progressed.
Combat performance is NOT scored (it lives in metrics) — a combat gauntlet scores
low by design; meaningful totals need a full-loop persona. Gaming-hardened per
SCORING.md (no raw event-volume term).
"""


def compute_score(stats, level):
    """`stats` is the full StatStore dict (name -> value); `level` the char level."""
    def sv(k):
        return float(stats.get(k, 0.0))

    b = {}
    b['levels'] = 100.0 * max(0, level - 1)                # +100 / level gained (start=1)
    b['skills'] = 20.0 * sv('progression.skills_learned')  # +20 / skill
    b['titles'] = 40.0 * sv('progression.titles_earned')   # +40 / title
    b['discovery'] = 5.0 * sv('encyclopedia.discovered')   # +5 / first-time discovery
    # gathering: +1 per 50 resources, scaled by tier
    g = 0.0
    for t in range(1, 5):
        g += (sv(f'gathering.collected.tier.{t}') / 50.0) * t
    b['gathering'] = g
    # crafting: +15/+10/+5/0 diminishing per DISTINCT recipe first-crafted.
    # (StatStore per-recipe key TBD on a crafting persona; 0 for the combat gauntlet.)
    b['crafting'] = 0.0

    b = {k: round(v, 2) for k, v in b.items()}
    return {'total': round(sum(b.values()), 2), 'breakdown': b}
