# Conformance Doctrine — proving "no gameplay features lost"

The migration's correctness instrument. Two layers: **golden vectors** (formula/unit
level) and **crux-foundry scenario parity** (emergent/system level).

## Golden vectors

**Generator:** `Game-1-Godot/conformance/generate_goldens.py`
**Fixtures:** `Game-1-Godot/conformance/goldens/*.json` (committed)
**Consumers:** `Game-1-Godot/tests/Game1.Core.Tests/` (xunit, `dotnet test`)

Rules:
1. The generator **imports the live Python game modules** and calls them. It never
   re-derives a formula by hand — if the formula changes in Python, regenerating the
   goldens captures it. Hand-derived fixtures are forbidden (that's how drift happens).
2. Fixtures are deterministic and diff-able. A golden diff after regeneration IS the
   behavioral delta between reference builds — review it like a balance change.
3. C# tests assert exact equality for integers/strings and `1e-9` for floats.
4. Every fixture carries `_meta` (generation date, source modules, git sha) so a
   stale fixture is detectable.

Current fixture inventory (P0):

| Fixture | Pins | Python source of truth |
|---|---|---|
| `exp_curve.json` | Per-level EXP requirements 1→30, cumulative table, cascade scenarios (large grants crossing multiple thresholds, max-level clamp, stat-point grants) | `entities/components/leveling.py` |
| `stat_scaling.json` | All 6 stats × levels 0–30: percent bonus, flat bonuses (HP/mana/slots/carry), durability-loss mult (DEF), durability-bonus mult (VIT), carry mult (STR), effective-luck composition | `entities/components/stats.py` (+ `stats-calculations.JSON` via its own loader) |
| `crit_chance.json` | Crit composition: LCK×0.12 + pierce + precision + titles, sampled grid | `Combat/combat_manager.py::_player_crit_chance` |
| `defense_reduction.json` | Per-target defense: `min(0.75, def×(1−pen)×0.01)` over a def×pen grid incl. 75% cap edge | `core/effect_executor.py` (F5 seam) |
| `damage_composition.json` | Action-path multiplier order: (+weapon×hand) ×STR ×titleMelee ×enemyTitle ×INT-elemental(tag-gated) ×crushing(def>10) ×empower ×crit(2.0) → defense; scenario matrix | `Combat/combat_manager.py::player_attack_enemy_with_tags` |
| `difficulty.json` | Material points, diversity multiplier, per-discipline difficulty (smithing/refining/alchemy/engineering/enchanting) over synthetic recipes, difficulty-tier bands | `core/difficulty_calculator.py` |
| `rewards.json` | Quality tiers by performance, max-reward multiplier by difficulty points, bonus %, stat multiplier, failure penalty + material-loss (30–90% tier-scaled) | `core/reward_calculator.py` |

Planned per later phases: loader-parity dumps (P1), inventory/equipment scenarios
(P2), world-gen tile hashes per seed (P3), status/enchantment tick traces (P4),
minigame scoring scenarios (P6), skill executor traces (P7), save round-trip (P8).

## crux-foundry scenario parity (Phase 4+)

`crux-foundry/` is the deterministic hermetic playtester: seeded personas fight a
scripted gauntlet through the real engine; the viability report is reproducible per
seed. The Godot build must reproduce those outcomes:

- RNG: C# port of MT19937 seeded identically, behind `IRandomSource`, so Python
  `random.Random(seed)` streams reproduce exactly where scenario parity demands it.
- Tolerances: kill/death counts exact; damage traces exact where RNG-aligned,
  else distributional (mean within 1%, spread within 5%) — divergences investigated,
  never waved through.

## Workflow

```bash
# Regenerate goldens from the live Python reference build:
python Game-1-Godot/conformance/generate_goldens.py

# Verify the C# port against them:
cd Game-1-Godot && dotnet test
```

Both steps belong in CI once the Godot build has one.
