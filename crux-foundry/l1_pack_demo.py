"""L1 local test — the enemy control surface, with obstacles.

Boots the real headless engine, drops a policy-driven pack on a ring around a
(passive, high-HP) player, places OBSTACLES (water + non-walkable tiles) on the
pack's approach lanes, runs the real per-frame loop, and asserts the pack behaves
*coherently*:

  1. CLOSE IN     — mean distance to the player collapses (they pursue).
  2. NAVIGATE     — they reach melee despite water/rock on the direct path
                    (proves _move_towards collision-sliding is exercised).
  3. ENGAGE       — they commit swings and the player actually takes damage
                    (proves the ATTACK-state commit lever drives the real combat
                    lifecycle end-to-end).
  4. PINCER       — at engagement they stay spread around the player (assigned
                    flank angles), not stacked on one point.

This is the L1 acceptance gate. No learning yet — it validates the *mechanism*
the later stages evolve. Deterministic under a fixed seed.

Run:  python crux-foundry/l1_pack_demo.py [seed] [n] [tier]
Exit: 0 = all gates pass, 1 = a gate failed.
"""
import io
import math
import os
import sys
import contextlib

for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('GAME1_HERMETIC', '1')

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(os.path.dirname(HERE), 'Game-1-modular')
for p in (PROJECT_ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(PROJECT_ROOT)

from runner import boot_engine                       # reuse the hermetic boot
from agents.enemy_control import spawn_policy_pack, disable_safe_zone, prepare_arena


def place_obstacles(world, center=(0.0, 0.0)):
    """Flip tiles to impassable (water + rock) on a broken ring between the spawn
    ring (r~8) and the player (r=0), so approaching members must slide around.
    Leaves gaps — a full wall would just trap them and prove nothing.

    Returns the list of (x,y) tiles made impassable (for reporting)."""
    from data.models.world import Position, TileType
    cx, cy = center
    blocked = []
    # a short WATER wall on the +x side (radius ~3.5), a few rows tall
    for dy in (-2, -1, 0, 1, 2):
        for r in (3, 4):
            x, y = int(cx + r), int(cy + dy)
            t = world.get_tile(Position(x, y, 0))
            if t is not None:
                t.tile_type = TileType.WATER
                t.walkable = False
                blocked.append((x, y))
    # a couple of ROCK (non-walkable) tiles on the -y side, with a gap between them
    for (x, y) in ((int(cx - 1), int(cy - 4)), (int(cx + 1), int(cy - 4)),
                   (int(cx - 3), int(cy + 3))):
        t = world.get_tile(Position(x, y, 0))
        if t is not None:
            t.walkable = False
            blocked.append((x, y))
    return blocked


def _mean_dist(pack, px, py):
    live = [e for e in pack if e.is_alive]
    if not live:
        return 0.0
    return sum(math.hypot(e.position[0] - px, e.position[1] - py) for e in live) / len(live)


def _min_flank_gap_deg(pack, px, py):
    """Smallest angular gap (deg) between adjacent living members around the player.
    High = well spread (pincer); near 0 = stacked."""
    angs = sorted(math.degrees(math.atan2(e.position[1] - py, e.position[0] - px)) % 360
                  for e in pack if e.is_alive)
    if len(angs) < 2:
        return 360.0
    gaps = [(angs[(i + 1) % len(angs)] - angs[i]) % 360 for i in range(len(angs))]
    return min(g for g in gaps if g > 0) if any(g > 0 for g in gaps) else 0.0


def run(seed=7, n=6, tier=2, frames=500):
    import random
    report = {}
    with contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        eng = boot_engine(os.path.join(HERE, 'runs', '_l1demo_wms'))
        from tests.integration.harness import PlaytestHarness
        h = PlaytestHarness(eng)
        h.settle()
        h.seed_all(seed)

        c = eng.character
        c.position.x, c.position.y = 0.0, 0.0
        c.max_health = 100000.0          # passive, survives the encounter (test rig)
        c.health = 100000.0
        disable_safe_zone(eng)           # arena: let the pack actually reach the player
        prepare_arena(eng, (0.0, 0.0), radius=12)   # clean walkable plane (+ auto-load chunks)

        blocked = place_obstacles(eng.world, (0.0, 0.0))
        pack = spawn_policy_pack(eng, n=n, tier=tier, center=(0.0, 0.0), radius=7.0,
                                 compose_seed=20260706)

        px, py = c.position.x, c.position.y
        start_mean = _mean_dist(pack, px, py)
        hp_start = c.health

        # run the real per-frame loop; sample the pincer gap at closest approach
        best_gap_at_engage = 0.0
        closest_mean = start_mean
        for _ in range(frames):
            h.tick(1)
            px, py = c.position.x, c.position.y
            m = _mean_dist(pack, px, py)
            if m < closest_mean:
                closest_mean = m
                best_gap_at_engage = _min_flank_gap_deg(pack, px, py)

        px, py = c.position.x, c.position.y
        end_mean = _mean_dist(pack, px, py)
        min_reached = min((e.min_dist_seen for e in pack), default=float('inf'))
        total_commits = sum(e.commits for e in pack)
        hp_end = c.health

    report = {
        'seed': seed, 'n': n, 'tier': tier, 'frames': frames,
        'obstacles_placed': len(blocked),
        'pack_ids': [e.definition.enemy_id for e in pack],
        'start_mean_dist': round(start_mean, 2),
        'end_mean_dist': round(end_mean, 2),
        'closest_mean_dist': round(closest_mean, 2),
        'min_dist_reached': round(min_reached, 2),
        'flank_gap_at_engage_deg': round(best_gap_at_engage, 1),
        'total_commits': total_commits,
        'player_hp_start': round(hp_start, 1),
        'player_hp_end': round(hp_end, 1),
        'player_damage_taken': round(hp_start - hp_end, 1),
        'living_at_end': sum(1 for e in pack if e.is_alive),
    }

    # ── acceptance gates ──
    ideal_gap = 360.0 / max(1, n)
    gates = {
        'closed_in':  end_mean < start_mean * 0.5,
        'navigated':  min_reached <= 1.6,                       # reached melee past obstacles
        'engaged':    total_commits > 0 and (hp_start - hp_end) > 0,
        'pincer':     best_gap_at_engage > ideal_gap * 0.3,     # spread, not stacked
    }
    return report, gates


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    tier = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    report, gates = run(seed=seed, n=n, tier=tier)

    print("── L1 pack control-surface demo ──")
    for k, v in report.items():
        print(f"  {k:24s} {v}")
    print("── gates ──")
    for k, ok in gates.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {k}")
    ok = all(gates.values())
    print(f"\n{'ALL GATES PASS' if ok else 'GATE FAILURE'}")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
