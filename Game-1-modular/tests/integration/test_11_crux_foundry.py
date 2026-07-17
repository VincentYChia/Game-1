"""
Playtest scenario 11 (crux-foundry): F4 fix regression guard.

The automated playtester found that luck->crit was missing on the ACTION-combat
path (player_attack_enemy_with_tags applied no crit at all -> LCK was a dead stat).
The fix wires luck-based crit there. This test guards it: a high-luck character
MUST land crits on the action-combat path. If someone reverts the fix, this fails.
"""


def test_f4_luck_crit_wired_on_action_path(play):
    eng = play.engine
    c = eng.character
    cm = eng.combat_manager

    old_luck = c.stats.luck
    try:
        c.stats.luck = 60  # 0.02 * 60 = 120% crit chance -> every hit should crit
        if hasattr(c, 'recalculate_stats'):
            c.recalculate_stats()

        from Combat.enemy import Enemy
        edef = cm.enemy_db.get_random_enemy(1)
        assert edef is not None, "need a T1 enemy to attack"
        px, py = c.position.x, c.position.y
        chunk = (int(px) // 16, int(py) // 16)

        def fresh_target():
            e = Enemy(edef, (px + 1.0, py), chunk)
            cm.enemies.setdefault(chunk, []).append(e)
            return e

        enemy = fresh_target()
        crits = 0
        for _ in range(6):
            if not enemy.is_alive:
                enemy = fresh_target()
            # call the action-combat damage path directly (bypasses the hitbox)
            _dmg, was_crit, _loot = cm.player_attack_enemy_with_tags(
                enemy, ['physical', 'single'], {'baseDamage': 20.0},
                skip_visual=True, skip_los=True)
            if was_crit:
                crits += 1

        assert crits > 0, \
            "F4 regression: luck-based crit is NOT firing on the action-combat path"
    finally:
        c.stats.luck = old_luck
        if hasattr(c, 'recalculate_stats'):
            c.recalculate_stats()
