"""Minimal BalanceValidator stub (§9.Q3, PLACEHOLDER_LEDGER §9).

Per the v4 resolution, the full BalanceValidator is a separate
project (see ``Development-Plan/SHARED_INFRASTRUCTURE.md``). Until
that lands, this stub keeps generator outputs inside a
tier-relative numeric envelope so obvious outliers are rejected
before content stages into the registry.

The stub:

- Loads ``tierMultipliers`` from
  ``Definitions.JSON/stats-calculations.JSON``.
- Accepts a single numeric ``field_value`` alongside the tier the
  content claims and the logical ``field_name`` (``hp`` / ``attack``
  / ``defense``; more below).
- Computes the nominal expected value as
  ``globalBases[<stat>] × tierMultipliers["tier<tier>"]``.
- Returns a reason string if ``field_value`` falls outside
  ``[0.5×nominal, 2×nominal]``. Returns ``None`` if within range or if
  no check applies (unknown field, missing config, etc.).

TODO(PLACEHOLDER_LEDGER §9):
    - Range multipliers (0.5x / 2x) are placeholders.
    - Supported field names are a minimal set (hp, attack, defense).
      Designer decides real scope.
    - Hostile stats do not yet have canonical bases in
      ``stats-calculations.JSON`` — see the HOSTILE_HP_BASES fallback.

This stub MUST NOT be interpreted as a balance pass — it only
rejects obvious outliers. Real balance review is a downstream
designer concern.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from world_system.living_world.infra.graceful_degrade import log_degrade


# Acceptable tier integers (§3 / §7 of working doc).
_VALID_TIERS = (1, 2, 3, 4)

# Placeholder stat->globalBase mapping. ``stats-calculations.JSON``
# has ``globalBases`` for weaponDamage/armorDefense/etc. Our
# ``field_name`` is the generator-side label; we map it onto a
# globalBase key here.
# TODO(PLACEHOLDER_LEDGER §9): extend as additional generator fields
# arrive (mana_cost, cooldown, yield rate, etc.).
_FIELD_TO_GLOBAL_BASE = {
    "attack": "weaponDamage",
    "damage": "weaponDamage",
    "defense": "armorDefense",
    "gathering": "toolGathering",
    "durability": "durability",
    "weight": "weight",
}


# Hostile HP has no globalBase in stats-calculations.JSON. Placeholder
# nominal per tier so hostiles aren't skipped entirely. These numbers
# are a vague lineage check only — not a design statement.
# TODO(PLACEHOLDER_LEDGER §9): designer replaces with real ranges.
_HOSTILE_HP_BASES = {
    1: 100.0,
    2: 250.0,
    3: 600.0,
    4: 1500.0,
}


# Placeholder tolerance — see PLACEHOLDER_LEDGER §9.
_LOWER_MULT = 0.5
_UPPER_MULT = 2.0


_cached_bases: Optional[Dict[str, Any]] = None
_cached_tier_multipliers: Optional[Dict[str, float]] = None


def _load_stats_config() -> None:
    """Load ``stats-calculations.JSON`` into module cache.

    Degrades gracefully — if the file can't be loaded (missing,
    malformed, path resolution failed), ``_cached_bases`` remains
    ``None`` and ``check_within_tier_range`` returns ``None`` for
    everything. The failure is logged once via ``log_degrade``.
    """
    global _cached_bases, _cached_tier_multipliers

    if _cached_bases is not None:
        return

    try:
        # PathManager resolution — we prefer the canonical path
        # resolved via ``core.paths``, but if the caller hasn't set
        # that up (e.g. in a standalone test), we fall back to a
        # best-effort walk from this module's location.
        try:
            from core.paths import get_resource_path

            config_path = get_resource_path(
                "Definitions.JSON/stats-calculations.JSON"
            )
        except Exception:
            this_dir = os.path.dirname(os.path.abspath(__file__))
            # content_registry/ -> world_system/ -> Game-1-modular/
            root = os.path.abspath(
                os.path.join(this_dir, "..", "..")
            )
            config_path = os.path.join(
                root, "Definitions.JSON", "stats-calculations.JSON"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        _cached_bases = dict(data.get("globalBases") or {})
        tm = data.get("tierMultipliers") or {}
        _cached_tier_multipliers = {
            "tier1": float(tm.get("tier1", 1.0)),
            "tier2": float(tm.get("tier2", 2.0)),
            "tier3": float(tm.get("tier3", 4.0)),
            "tier4": float(tm.get("tier4", 8.0)),
        }
    except Exception as e:
        log_degrade(
            subsystem="content_registry",
            operation="balance_validator_stub.load_stats_config",
            failure_reason=f"{type(e).__name__}: {e}",
            fallback_taken="stats config unavailable; all checks skipped",
            severity="warning",
        )
        _cached_bases = {}
        _cached_tier_multipliers = {
            "tier1": 1.0,
            "tier2": 2.0,
            "tier3": 4.0,
            "tier4": 8.0,
        }


def _expected_nominal(field_name: str, tier: int) -> Optional[float]:
    """Return the expected nominal value for ``field_name`` at
    ``tier``. Returns ``None`` if the field is unknown."""
    _load_stats_config()
    tier_key = f"tier{tier}"
    if _cached_tier_multipliers is None:
        return None
    tier_mult = _cached_tier_multipliers.get(tier_key)
    if tier_mult is None:
        return None

    # Hostile HP special case — no globalBase exists for it.
    if field_name in ("hp", "health", "max_health", "maxHealth"):
        return float(_HOSTILE_HP_BASES.get(tier, 0.0))

    base_key = _FIELD_TO_GLOBAL_BASE.get(field_name)
    if base_key is None:
        return None
    if _cached_bases is None:
        return None
    base_value = _cached_bases.get(base_key)
    if not isinstance(base_value, (int, float)):
        return None
    return float(base_value) * tier_mult


def check_within_tier_range(
    field_value: Any, tier: int, field_name: str
) -> Optional[str]:
    """Stat-sanity check for generator output.

    Args:
        field_value: the numeric value being validated.
        tier: integer 1..4.
        field_name: logical field label (``"attack"``, ``"defense"``,
            ``"hp"``, ``"damage"``, ``"gathering"``, ``"durability"``,
            ``"weight"``).

    Returns:
        ``None`` if the value is within the tier envelope, OR if no
        check applies (unknown field, out-of-range tier, missing
        config, non-numeric value). A reason string if the value is
        outside ``[0.5×nominal, 2×nominal]``.

    Contract note: this is a **soft** validator — ``None`` means
    "no objection", not "approved". Absence of a rule is the default.
    """
    # Coerce + validate inputs.
    if tier not in _VALID_TIERS:
        return None
    if not isinstance(field_value, (int, float)):
        return None
    if isinstance(field_value, bool):  # bool is int subclass; reject.
        return None

    nominal = _expected_nominal(field_name, tier)
    if nominal is None or nominal <= 0.0:
        return None

    lower = nominal * _LOWER_MULT
    upper = nominal * _UPPER_MULT

    if field_value < lower:
        return (
            f"{field_name}={field_value} is below placeholder tier-{tier} "
            f"lower bound {lower:.2f} (nominal {nominal:.2f}). "
            f"PLACEHOLDER_LEDGER §9."
        )
    if field_value > upper:
        return (
            f"{field_name}={field_value} is above placeholder tier-{tier} "
            f"upper bound {upper:.2f} (nominal {nominal:.2f}). "
            f"PLACEHOLDER_LEDGER §9."
        )
    return None


def reset_cache() -> None:
    """Test helper — drop cached config so the next call re-reads."""
    global _cached_bases, _cached_tier_multipliers
    _cached_bases = None
    _cached_tier_multipliers = None
