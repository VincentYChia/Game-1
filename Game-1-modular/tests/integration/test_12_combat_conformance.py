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


# ── Batch 2: previously-dead documented stats ────────────────────────

def test_vit_scales_health_regen(play):
    """VIT +1% health regen per point (documented; was flat regardless)."""
    char = play.engine.character
    char.time_since_last_damage_taken = 999.0
    char.time_since_last_damage_dealt = 999.0

    char.stats.vitality = 0
    char.health = 1.0
    char.update_health_regen(1.0)
    gain_v0 = char.health - 1.0

    char.stats.vitality = 20
    char.health = 1.0
    char.time_since_last_damage_taken = 999.0
    char.time_since_last_damage_dealt = 999.0
    char.update_health_regen(1.0)
    gain_v20 = char.health - 1.0

    assert gain_v0 > 0
    ratio = gain_v20 / gain_v0
    assert 1.15 <= ratio <= 1.25, (
        f"20 VIT should give ~1.2x regen (+1%/pt), got {ratio:.2f}x"
    )
    char.stats.vitality = 0
    char.health = char.max_health


def test_int_scales_elemental_damage_on_action_path(play):
    """INT +5% elemental damage per point (documented; had no combat
    consumer). Physical attacks are unaffected."""
    eng = play.engine
    dummy = _fresh_dummy(play)
    eng.character.stats.strength = 0
    orig_def = dummy.definition.defense
    try:
        dummy.definition.defense = 0

        eng.character.stats.intelligence = 0
        phys_i0 = _tags_damage(play, dummy)
        dummy.current_health = dummy.max_health
        eng.combat_manager.player_attack_enemy_with_tags(
            dummy, ['fire', 'single_target'], {'baseDamage': 100.0},
            skip_visual=True, skip_los=True)
        fire_i0 = dummy.max_health - dummy.current_health

        eng.character.stats.intelligence = 20  # -> 2.0x elemental
        dummy.current_health = dummy.max_health
        phys_i20 = _tags_damage(play, dummy)
        dummy.current_health = dummy.max_health
        eng.combat_manager.player_attack_enemy_with_tags(
            dummy, ['fire', 'single_target'], {'baseDamage': 100.0},
            skip_visual=True, skip_los=True)
        fire_i20 = dummy.max_health - dummy.current_health

        assert abs(phys_i20 - phys_i0) < 1e-6, "INT must not scale physical"
        assert abs(fire_i0 - phys_i0) < 1e-6, "at INT 0 fire == physical"
        ratio = fire_i20 / fire_i0
        assert 1.9 <= ratio <= 2.1, (
            f"20 INT should give ~2.0x elemental damage (+5%/pt), got {ratio:.2f}x"
        )
    finally:
        eng.character.stats.intelligence = 0
        dummy.definition.defense = orig_def
        dummy.current_health = dummy.max_health


def test_def_armor_effectiveness_is_wired(play):
    """DEF +3% armor effectiveness per point (documented; armor_bonus
    ignored DEF). Source-pinned: the behavioral path needs worn armor,
    which the harness persona doesn't guarantee."""
    import inspect
    from Combat import combat_manager as cmod
    src = inspect.getsource(cmod.CombatManager._enemy_attack_player)
    assert "defense * 0.03" in src, (
        "armor-effectiveness scaling (+3%/DEF pt) regressed to dead-stat"
    )


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
