"""Tests for :func:`check_within_tier_range` — the BalanceValidator stub."""

from __future__ import annotations

import unittest

from world_system.content_registry.balance_validator_stub import (
    check_within_tier_range,
    reset_cache,
)


class TestBalanceValidatorStub(unittest.TestCase):
    def setUp(self) -> None:
        reset_cache()

    def test_within_tier1_attack_range_accepted(self) -> None:
        # T1 weaponDamage nominal = 10 × 1.0 = 10. Range [5, 20].
        self.assertIsNone(
            check_within_tier_range(10, tier=1, field_name="attack")
        )

    def test_above_upper_bound_rejected(self) -> None:
        # Clearly above 2x nominal.
        reason = check_within_tier_range(
            1_000_000, tier=1, field_name="attack"
        )
        self.assertIsNotNone(reason)
        self.assertIn("above", reason)

    def test_below_lower_bound_rejected(self) -> None:
        reason = check_within_tier_range(0.01, tier=1, field_name="attack")
        self.assertIsNotNone(reason)
        self.assertIn("below", reason)

    def test_tier_scaling(self) -> None:
        # T4 weaponDamage nominal = 10 × 8.0 = 80. Range [40, 160].
        self.assertIsNone(
            check_within_tier_range(80, tier=4, field_name="attack")
        )
        self.assertIsNone(
            check_within_tier_range(50, tier=4, field_name="attack")
        )
        reason = check_within_tier_range(
            10, tier=4, field_name="attack"
        )
        self.assertIsNotNone(reason)

    def test_unknown_field_returns_none(self) -> None:
        self.assertIsNone(
            check_within_tier_range(
                999, tier=1, field_name="totally_unknown_field"
            )
        )

    def test_invalid_tier_returns_none(self) -> None:
        self.assertIsNone(
            check_within_tier_range(100, tier=99, field_name="attack")
        )
        self.assertIsNone(
            check_within_tier_range(100, tier=0, field_name="attack")
        )

    def test_non_numeric_value_returns_none(self) -> None:
        self.assertIsNone(
            check_within_tier_range("not a number", 1, "attack")
        )
        self.assertIsNone(
            check_within_tier_range(None, 1, "attack")
        )

    def test_bool_is_rejected_not_treated_as_int(self) -> None:
        # ``bool`` is an int subclass in Python — make sure we don't
        # accidentally accept True/False as 1/0.
        self.assertIsNone(
            check_within_tier_range(True, 1, "attack")
        )

    def test_hostile_hp_uses_placeholder_bases(self) -> None:
        # T1 hostile HP placeholder nominal = 100. Range [50, 200].
        self.assertIsNone(
            check_within_tier_range(100, tier=1, field_name="hp")
        )
        self.assertIsNotNone(
            check_within_tier_range(10, tier=1, field_name="hp")
        )
        self.assertIsNotNone(
            check_within_tier_range(99_999, tier=1, field_name="hp")
        )

    def test_defense_scaling(self) -> None:
        # T2 armorDefense nominal = 10 × 2.0 = 20. Range [10, 40].
        self.assertIsNone(
            check_within_tier_range(20, tier=2, field_name="defense")
        )
        reason = check_within_tier_range(500, tier=2, field_name="defense")
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()
