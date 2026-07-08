"""
crux-foundry — emergent-life chronicler (the deep-simulated-world payoff).

An autonomous agent LIVES a long, varied life in the world (gather-ish via crafting,
fight, explore, level) over many in-game days, and we extract the EMERGENT CHRONICLE
the World Memory System accumulates -- daily ledgers + milestone template-narratives
(all hermetic, NO LLM) + the life arc. Run thousands with different seeds and you get
a corpus of lived histories: the raw, lived-in past a game can ship with.

Honest scope: the world does not self-evolve (no autonomous NPCs/economy); this is a
rich chronicle of the AGENT'S life plus the local enemy/resource cycles around it.

CLI:  python crux-foundry/life_runner.py <seed> <out_dir> [days]
"""
import os
import sys
import io
import json
import contextlib
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from runner import boot_engine, capture, _GIT_SHA, SCHEMA_VERSION
from loop_runner import _craft_round, _fight_wave, _t1_recipes

DAYS = 8
DAY_TIME = 2.0          # advance game_time by this per "day" (WMS ledger day = 1.0 unit)
STAT_POLICY = ['strength', 'vitality', 'strength']   # rotates as the agent grows


def _advance_day(h):
    """Push in-game time forward so the WMS closes a daily ledger, and tick so the
    world_memory update processes the boundary."""
    h.engine.game_time += DAY_TIME
    h.tick(3)


def live(h, days):
    """A varied life: each 'day' the agent crafts, fights a wave, allocates, and time
    advances. Returns lightweight per-day activity (the WMS records the real history)."""
    c = h.engine.character
    refine = _t1_recipes('refining', 3)
    smith = _t1_recipes('smithing', 3)
    alloc_i = 0
    crafts = kills = 0
    for d in range(days):
        # vary activity by day so the chronicle isn't monotone
        if d % 2 == 0:
            crafts += len(_craft_round(h, refine) + _craft_round(h, smith))
            try:
                h.equip('iron_shortsword'); c._selected_slot = 'mainHand'
            except Exception:
                pass
        kills += _fight_wave(h)
        while c.leveling.unallocated_stat_points > 0:
            c.allocate_stat_point(STAT_POLICY[alloc_i % len(STAT_POLICY)])
            alloc_i += 1
        _advance_day(h)
    return {'crafts': crafts, 'kills': kills}


def _ledger_to_dict(L):
    keys = ('game_day', 'primary_activity', 'enemies_killed', 'deaths', 'damage_dealt',
            'resources_gathered', 'items_crafted', 'chunks_visited', 'quests_completed')
    return {k: getattr(L, k, None) for k in keys}


def extract_chronicle(eng):
    """Pull the emergent history the WMS accumulated: daily ledgers + milestone
    narratives + meta records. All hermetic (no LLM)."""
    ch = {'event_count': None, 'days': [], 'milestones': [], 'meta': {}}
    wms = getattr(eng, 'world_memory', None)
    if wms is None:
        return ch
    es = getattr(wms, 'event_store', None)
    if es is None:
        return ch
    try:
        ch['event_count'] = es.get_event_count()
    except Exception:
        pass
    # daily ledgers (the per-day chronicle)
    mgr = getattr(wms, 'daily_ledger_manager', None)
    if mgr is not None and hasattr(mgr, 'load_ledgers'):
        try:
            for L in mgr.load_ledgers(es):
                ch['days'].append(_ledger_to_dict(L))
        except Exception as e:
            ch['days_error'] = repr(e)
    # milestone narratives (Layer-2 template text -- readable, no LLM)
    if hasattr(es, 'query_interpretations'):
        for kwargs in ({'category': 'player_milestone'}, {}):
            try:
                its = es.query_interpretations(**kwargs)
                for it in its:
                    txt = getattr(it, 'narrative', None) or getattr(it, 'text', None) or str(it)
                    sev = getattr(it, 'severity', None)
                    ch['milestones'].append({'severity': str(sev), 'text': txt})
                if ch['milestones']:
                    break
            except Exception:
                continue
    # meta records (biggest day / longest streaks)
    if hasattr(es, 'load_meta_daily_stats'):
        try:
            ch['meta'] = {'raw': es.load_meta_daily_stats()}
        except Exception:
            pass
    return ch


def narrate(ch, cap, seed):
    """Render the chronicle as a short readable life-story from the factual history."""
    lines = [f"=== THE LIFE OF AGENT #{seed} ==="]
    lines.append(f"Lived through {len(ch['days'])} recorded days; {ch['event_count']} events remembered.")
    for i, d in enumerate(ch['days'], 1):
        bits = []
        if d.get('enemies_killed'):
            bits.append(f"slew {int(d['enemies_killed'])}")
        if d.get('items_crafted'):
            bits.append(f"forged {int(d['items_crafted'])}")
        if d.get('resources_gathered'):
            bits.append(f"gathered {int(d['resources_gathered'])}")
        if d.get('deaths'):
            bits.append(f"died {int(d['deaths'])}x")
        act = d.get('primary_activity') or 'idle'
        lines.append(f"  Day {i}: {act}" + (f" — {', '.join(bits)}" if bits else ""))
    if ch['milestones']:
        from collections import Counter
        uniq = Counter(m['text'] for m in ch['milestones'])
        distinct = len(uniq)
        lines.append(f"Milestones ({len(ch['milestones'])} recorded, {distinct} distinct):")
        for txt, n in list(uniq.items())[:8]:
            lines.append(f"  x{n}: {txt}")
        if distinct <= 2:
            lines.append("  (narrative fragments are UNFURNISHED placeholders — designer task; "
                         "the WMS structure/severity/query all work.)")
    lines.append(f"Ended: level {cap['level']}, exp {cap['exp']}.")
    return "\n".join(lines)


def run_life(seed, out_dir, days=DAYS):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wms_dir = out_dir / 'wms'
    wms_dir.mkdir(exist_ok=True)

    import random
    with contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        eng = boot_engine(wms_dir)
        from tests.integration.harness import PlaytestHarness
        h = PlaytestHarness(eng)
        h.settle()
        h.seed_all(seed)
        drive = live(h, days)
        cap = capture(eng)
        chronicle = extract_chronicle(eng)

    story = narrate(chronicle, cap, seed)
    result = {
        'schema': SCHEMA_VERSION,
        'manifest': {'run_id': f'life-{seed}', 'seed': seed, 'persona': 'life',
                     'config': {'days': days}, 'git_sha': _GIT_SHA},
        'final': {'level': cap['level'], 'exp': cap['exp'],
                  'crafts': drive['crafts'], 'kills': drive['kills']},
        'chronicle': chronicle,
        'story': story,
    }
    tmp = out_dir / 'result.json.tmp'
    tmp.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    os.replace(tmp, out_dir / 'result.json')
    (out_dir / 'story.txt').write_text(story + "\n", encoding='utf-8')
    return result


def main():
    if len(sys.argv) < 3:
        print("usage: life_runner.py <seed> <out_dir> [days]")
        sys.exit(2)
    seed = int(sys.argv[1]); out_dir = sys.argv[2]
    days = int(sys.argv[3]) if len(sys.argv) > 3 else DAYS
    r = run_life(seed, out_dir, days)
    print(r['story'])


if __name__ == '__main__':
    main()
