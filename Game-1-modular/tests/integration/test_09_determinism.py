"""
Playtest scenario 9 (crux-foundry P0): determinism / reproducibility proof.

The automated-playtest foundry needs runs reproducible from a seed. Every piece
of gameplay randomness the sim cares about is drawn from exactly two sources:
  - CombatManager._rng      (crit rolls, enemy tier/count/position, dungeon spawn)
  - the global `random` module (enemy loot/damage, enemy-DB selection, crafting)

harness.seed_all(seed) seeds BOTH. These tests prove the wiring: after seed_all
each stream is reproducible for a fixed seed and diverges for different seeds.
Combined with AI disabled (DC6) and deterministic actions, this makes a whole
run reproducible — the foundation P1+ depends on.
"""
import random


def _draw_streams(play, n=32):
    """Pull n values from each RNG source the game actually draws from."""
    cm = play.engine.combat_manager
    combat_stream = [cm._rng.random() for _ in range(n)]   # crit/spawn source
    global_stream = [random.random() for _ in range(n)]    # loot/db/crafting source
    return combat_stream, global_stream


def test_same_seed_reproduces_rng_streams(play):
    play.seed_all(4242)
    a_combat, a_global = _draw_streams(play)

    play.seed_all(4242)
    b_combat, b_global = _draw_streams(play)

    assert a_combat == b_combat, "CombatManager RNG not reproducible under a fixed seed"
    assert a_global == b_global, "global RNG not reproducible under a fixed seed"


def test_different_seeds_diverge(play):
    play.seed_all(1)
    c1, g1 = _draw_streams(play)

    play.seed_all(2)
    c2, g2 = _draw_streams(play)

    # Proves the seed actually controls both streams (not constant / not ignored).
    assert c1 != c2, "different seeds gave identical CombatManager streams (not seeded?)"
    assert g1 != g2, "different seeds gave identical global streams (not seeded?)"
