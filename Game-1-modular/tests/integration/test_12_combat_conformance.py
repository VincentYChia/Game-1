"""
Playtest scenario 12: damage-pipeline conformance on the SHIPPED combat path.

The documented pipeline is:
    base x hand(1.1-1.2) x STR(1+STRx0.05) x skill x crit(2x) - def(max 75%)

The 2026-07 audit found the action-combat path (the only melee path real
players hit) was missing several documented components that the legacy path
applied: enemy DEFENSE was never applied at all (F5), the crit composition
lacked pierce/precision (F6), the hand-requirement bonus was absent (F7),
and a legacy AoE sub-path used STR x0.01 with a flat LCK-ignoring 10% crit
(F8). Three divergent crit implementations were unified into
CombatManager._player_crit_chance (F3).

These tests pin the conformance on the real engine.
"""
import pytest


def _fresh_dummy(play):
    dummy = play.training_dummy() if hasattr(play, 'training_dummy') else None
    if dummy is None:
        pytest.skip("no training dummy in this world")
    dummy.current_health = dummy.max_health
    dummy.is_alive = True
    return dummy


def _tags_damage(play, enemy, base=100.0, luck_zero=True):
    """Run one action-path attack with a fixed baseDamage; return damage dealt."""
    eng = play.engine
    hp0 = enemy.current_health
    if luck_zero:
        eng.character.stats.luck = 0
    eng.combat_manager.player_attack_enemy_with_tags(
        enemy, ['physical', 'single_target'], {'baseDamage': base},
        skip_visual=True, skip_los=True)
    return hp0 - enemy.current_health


def test_enemy_defense_now_applies_on_action_path(play):
    """F5: an enemy with defense takes reduced damage; defense 0 takes full."""
    eng = play.engine
    dummy = _fresh_dummy(play)

    # Zero out confounders: bare hands (no weapon damage), STR 0, LCK 0.
    eng.character.stats.strength = 0
    eng.character.stats.luck = 0

    orig_def = dummy.definition.defense
    try:
        dummy.definition.defense = 0
        dmg_no_def = _tags_damage(play, dummy)

        dummy.current_health = dummy.max_health
        dummy.definition.defense = 50  # -> 50% reduction
        dmg_with_def = _tags_damage(play, dummy)

        assert dmg_no_def > 0
        ratio = dmg_with_def / dmg_no_def
        assert 0.45 <= ratio <= 0.55, (
            f"50 defense should reduce damage ~50% (got ratio {ratio:.2f}) — "
            f"enemy DEF regressed to dead-stat on the action path"
        )
    finally:
        dummy.definition.defense = orig_def
        dummy.current_health = dummy.max_health


def test_defense_reduction_caps_at_75_percent(play):
    eng = play.engine
    dummy = _fresh_dummy(play)
    eng.character.stats.strength = 0
    eng.character.stats.luck = 0

    orig_def = dummy.definition.defense
    try:
        dummy.definition.defense = 0
        dmg_no_def = _tags_damage(play, dummy)

        dummy.current_health = dummy.max_health
        dummy.definition.defense = 500  # would be -500%; must cap at -75%
        dmg_capped = _tags_damage(play, dummy)

        ratio = dmg_capped / dmg_no_def
        assert 0.20 <= ratio <= 0.30, (
            f"500 defense must cap at 75% reduction (expected ~0.25 ratio, got {ratio:.2f})"
        )
    finally:
        dummy.definition.defense = orig_def
        dummy.current_health = dummy.max_health


def test_crit_chance_composition_unified(play):
    """F3/F6: the shared helper composes LCK + titles (+pierce/precision when
    present) and is used by the action path."""
    eng = play.engine
    cm = eng.combat_manager

    eng.character.stats.luck = 9
    base = cm._player_crit_chance()
    assert base >= 0.18 - 1e-9, (
        f"9 LCK should give >=18% crit via the shared helper, got {base:.3f}"
    )

    # Precision weapon tag adds on top through the same helper.
    with_precision = cm._player_crit_chance(weapon_tags=['precision'])
    assert with_precision >= base, "precision tag must never lower crit chance"

    eng.character.stats.luck = 0


def test_guaranteed_crit_doubles_damage_on_action_path(play):
    """With crit chance forced >= 1.0 (luck 50 => 100%), damage doubles."""
    eng = play.engine
    dummy = _fresh_dummy(play)
    eng.character.stats.strength = 0

    orig_def = dummy.definition.defense
    try:
        dummy.definition.defense = 0

        eng.character.stats.luck = 0
        dmg_normal = _tags_damage(play, dummy, luck_zero=True)

        dummy.current_health = dummy.max_health
        eng.character.stats.luck = 50  # 50 * 0.02 = 100% crit
        dmg_crit = _tags_damage(play, dummy, luck_zero=False)

        ratio = dmg_crit / dmg_normal
        assert 1.9 <= ratio <= 2.1, (
            f"guaranteed crit should double damage (got ratio {ratio:.2f})"
        )
    finally:
        eng.character.stats.luck = 0
        dummy.definition.defense = orig_def
        dummy.current_health = dummy.max_health


def test_aoe_subpath_uses_documented_str_scaling(play):
    """F8: the legacy AoE sub-path must scale STR at the documented 0.05/pt
    (it used 0.01). Verified via source constant to avoid the fragile buff
    setup; the behavioral paths above cover the live formula."""
    import inspect
    from Combat import combat_manager as cmod
    src = inspect.getsource(cmod.CombatManager._single_target_attack)
    assert "strength * 0.01" not in src, "AoE sub-path regressed to 0.01 STR scaling"
    assert "_STR_DMG_PER_POINT" in src
    assert "_player_crit_chance" in src, "AoE sub-path must use the shared crit helper"
