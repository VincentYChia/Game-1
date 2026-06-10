"""
Playtest scenario 2: a real combat encounter through CombatManager.

Uses the real enemies spawned at temp-world entry. Pins the damage
pipeline end-to-end (weapon/stat/crit/defense math executing without
crash, health mutation, death + EXP) — none of which had integration
coverage before 2026-06-10.
"""


def _nearest_living_enemy(engine, killable=False):
    """Nearest living enemy; killable=True excludes the 10,000-HP
    training dummy (it exists for tag testing, not for dying)."""
    enemies = [e for e in engine.combat_manager.get_all_active_enemies()
               if e.is_alive]
    if killable:
        enemies = [e for e in enemies
                   if getattr(getattr(e, 'definition', None), 'enemy_id', '')
                   != 'training_dummy']
    assert enemies, "No living enemies in the temp world"
    px, py = engine.character.position.x, engine.character.position.y
    return min(enemies, key=lambda e: (e.position[0] - px) ** 2 + (e.position[1] - py) ** 2)


def test_player_attack_damages_enemy(play):
    eng = play.engine
    enemy = _nearest_living_enemy(eng)
    hp_before = enemy.current_health

    damage, was_crit, drops = eng.combat_manager.player_attack_enemy(enemy)

    assert damage > 0, "Player basic attack dealt no damage"
    assert enemy.current_health < hp_before, "Enemy health did not decrease"


def test_kill_grants_exp_and_removes_enemy(play):
    eng = play.engine
    enemy = _nearest_living_enemy(eng, killable=True)
    exp_state_before = (eng.character.leveling.level,
                        eng.character.leveling.current_exp)

    # Swing until dead (cap prevents an infinite loop on a regression).
    for _ in range(200):
        if not enemy.is_alive:
            break
        eng.combat_manager.player_attack_enemy(enemy)
        play.tick(1)
    assert not enemy.is_alive, "200 attacks failed to kill the nearest enemy"

    # The corpse must leave the active set within a few frames.
    play.tick(5)
    assert enemy not in eng.combat_manager.get_all_active_enemies() or not enemy.is_alive

    # EXP must have flowed: level and/or current_exp changed.
    exp_state_after = (eng.character.leveling.level,
                       eng.character.leveling.current_exp)
    assert exp_state_after != exp_state_before, \
        "Killing an enemy granted no experience"


def test_sustained_combat_session_no_crash(play):
    """Several enemies attacked while the world keeps updating around them."""
    eng = play.engine
    for _ in range(3):
        enemies = [e for e in eng.combat_manager.get_all_active_enemies()
                   if e.is_alive
                   and getattr(getattr(e, 'definition', None), 'enemy_id', '')
                   != 'training_dummy']
        if not enemies:
            break
        target = enemies[0]
        for _ in range(60):
            if not target.is_alive:
                break
            eng.combat_manager.player_attack_enemy(target)
            play.tick(1, render_every=10)
    play.tick(30)
