"""
Playtest scenario 10 (crux-foundry P1): capture-path proof.

The automated playtester MUST drive combat through the real action-combat path
(harness.melee_swing) so the StatStore records combat analytics. The low-level
combat_manager.player_attack_enemy skips record_damage_dealt / record_enemy_killed
(those rows live only on the player_attack_enemy_with_tags path reached via the
hitbox resolver). This test locks in that melee_swing feeds the capture layer, so
a future refactor can't silently make runs capture-blind.

Spawns a controlled, hitbox-registered enemy adjacent to the player (mirroring the
real spawn path) so the test is deterministic and order-independent under the
session-scoped engine. (The training dummy is NOT hurtbox-registered, so the real
action-combat hitbox can't hit it — only the low-level API can.)
"""


def _combat_stats(play):
    store = play.engine.character.stat_tracker._store
    store.flush()
    return store.get_prefix('combat')


def test_melee_swing_populates_statstore(play):
    eng = play.engine
    cm = eng.combat_manager
    c = eng.character

    # Spawn a T1 enemy 1 tile in front of the player and register it with the
    # action-combat hitbox system (exactly as spawn_initial_enemies does).
    from Combat.enemy import Enemy
    edef = cm.enemy_db.get_random_enemy(1)
    assert edef is not None, "need a T1 enemy definition to spawn a target"
    px, py = c.position.x, c.position.y
    chunk_coords = (int(px) // 16, int(py) // 16)   # CHUNK_SIZE = 16
    enemy = Enemy(edef, (px + 1.0, py), chunk_coords)
    cm.enemies.setdefault(chunk_coords, []).append(enemy)
    cm._register_enemy_action_combat(enemy)

    before = _combat_stats(play).get('combat.damage_dealt', 0.0)
    for _ in range(8):
        if not enemy.is_alive:
            break
        play.melee_swing(enemy, frames=30)
    after = _combat_stats(play)

    assert after.get('combat.damage_dealt', 0.0) > before, \
        "melee_swing did not record combat.damage_dealt (capture-blind path?)"
    assert after.get('combat.damage_dealt.attack.melee', 0.0) > 0.0, \
        "expected a melee damage-dealt breakdown row in the StatStore"
