"""
Fast unit tests for the progression score (crux-foundry/scoring.py). Pure — no
engine boot. Run:  python -m pytest crux-foundry/test_scoring.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scoring import compute_score


def test_empty_stats_level1_is_zero():
    s = compute_score({}, 1)
    assert s['total'] == 0.0
    assert all(v == 0.0 for v in s['breakdown'].values())


def test_levels_component():
    # +100 per level GAINED (start at level 1)
    assert compute_score({}, 10)['breakdown']['levels'] == 900.0
    assert compute_score({}, 1)['breakdown']['levels'] == 0.0


def test_skills_and_titles_and_discovery():
    stats = {
        'progression.skills_learned': 2.0,     # +20 each  -> 40
        'progression.titles_earned': 1.0,      # +40       -> 40
        'encyclopedia.discovered': 3.0,        # +5 each   -> 15
    }
    b = compute_score(stats, 1)['breakdown']
    assert b['skills'] == 40.0
    assert b['titles'] == 40.0
    assert b['discovery'] == 15.0


def test_gathering_is_tier_scaled():
    # +1 per 50 resources, scaled by tier
    stats = {'gathering.collected.tier.2': 100.0}   # (100/50)*2 = 4
    assert compute_score(stats, 1)['breakdown']['gathering'] == 4.0
    stats = {'gathering.collected.tier.4': 50.0}    # (50/50)*4 = 4
    assert compute_score(stats, 1)['breakdown']['gathering'] == 4.0


def test_total_is_sum_of_components():
    stats = {
        'progression.skills_learned': 1.0,     # 20
        'encyclopedia.discovered': 2.0,        # 10
        'gathering.collected.tier.1': 100.0,   # 2
    }
    s = compute_score(stats, 5)                # levels: 400
    assert s['total'] == round(sum(s['breakdown'].values()), 2)
    assert s['total'] == 400.0 + 20.0 + 10.0 + 2.0


def test_crafting_diminishing_per_distinct_recipe():
    # +15/+10/+5/0 diminishing per DISTINCT crafted recipe
    stats = {f'crafting.success.recipe.r{i}': 4.0 for i in range(5)}  # 5 distinct
    assert compute_score(stats, 1)['breakdown']['crafting'] == 30.0     # 15+10+5+0+0
    one = {'crafting.success.recipe.r0': 9.0}                           # 1 distinct
    assert compute_score(one, 1)['breakdown']['crafting'] == 15.0


def test_no_raw_event_volume_term():
    # SCORING.md hardening: raw combat/event volume must NOT contribute to score.
    noisy = {'combat.damage_dealt': 1e9, 'combat.kills': 999.0, 'session.started': 1.0}
    assert compute_score(noisy, 1)['total'] == 0.0
