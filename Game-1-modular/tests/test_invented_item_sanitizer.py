"""2026-07 LLM-pipeline audit — invented-item sanity gate.

Before this gate, the ONLY validation on an LLM-invented item was
"has an itemId": damage 999999, tier 99, or an id shadowing a sacred
item all flowed straight into the inventory (BalanceValidator is spec
only — Development-Plan/SHARED_INFRASTRUCTURE.md).
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from systems.llm_item_generator import LLMItemGenerator  # noqa: E402


def _gen():
    g = LLMItemGenerator.__new__(LLMItemGenerator)
    g.materials_db = None
    return g


def test_tier_clamped_to_1_4():
    out = _gen()._sanitize_item_data({"itemId": "x", "tier": 99})
    assert out["tier"] == 4
    out = _gen()._sanitize_item_data({"itemId": "x", "tier": 0})
    assert out["tier"] == 1


def test_non_numeric_tier_defaults_to_1():
    out = _gen()._sanitize_item_data({"itemId": "x", "tier": "legendary"})
    assert out["tier"] == 1


def test_combat_stats_clamped_to_tier_ceiling():
    out = _gen()._sanitize_item_data(
        {"itemId": "x", "tier": 1, "damage": 999999, "healing": 50000})
    assert out["damage"] == 60
    assert out["healing"] == 60
    out = _gen()._sanitize_item_data({"itemId": "x", "tier": 4, "damage": 999999})
    assert out["damage"] == 480


def test_sane_item_untouched():
    data = {"itemId": "copper_charm", "tier": 1, "damage": 12}
    out = _gen()._sanitize_item_data(dict(data))
    assert out == data


def test_id_collision_gets_invented_prefix():
    class _FakeMats:
        materials = {"iron_ore": object()}

    g = _gen()
    g.materials_db = _FakeMats()
    out = g._sanitize_item_data({"materialId": "iron_ore", "tier": 1})
    assert out["materialId"] == "invented_iron_ore"


def test_equipment_collision_detected_when_db_loaded():
    from data.databases.equipment_db import EquipmentDatabase
    eq = EquipmentDatabase.get_instance()
    if "iron_shortsword" not in getattr(eq, "items", {}):
        import pytest
        pytest.skip("equipment db not loaded in this context")
    out = _gen()._sanitize_item_data({"itemId": "iron_shortsword", "tier": 2})
    assert out["itemId"] == "invented_iron_shortsword"
