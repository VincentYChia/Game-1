"""Tests for NLTriggerManager — bucket increments + fire-at-N behavior."""

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.nl_trigger_manager import NLTriggerManager  # noqa: E402


class TestNLTriggerManager(unittest.TestCase):
    def test_default_n_per_layer(self):
        mgr = NLTriggerManager()
        self.assertEqual(mgr.n_for_layer(2), 5)
        self.assertEqual(mgr.n_for_layer(7), 20)

    def test_should_run_fires_at_threshold(self):
        mgr = NLTriggerManager()
        # NL2 default N = 5. First 4 calls return False, 5th returns True.
        addr = "locality:tarmouth"
        fired_at: int = -1
        for i in range(1, 7):
            fired = mgr.should_run(layer=2, address=addr)
            if fired:
                fired_at = i
                break
        self.assertEqual(fired_at, 5)

    def test_should_run_resets_after_fire(self):
        mgr = NLTriggerManager()
        addr = "locality:a"
        # Burn 5 to fire.
        for _ in range(5):
            mgr.should_run(layer=2, address=addr)
        # Next 4 should NOT fire again.
        for _ in range(4):
            self.assertFalse(mgr.should_run(layer=2, address=addr))
        # 5th after reset fires again.
        self.assertTrue(mgr.should_run(layer=2, address=addr))

    def test_independent_per_address(self):
        mgr = NLTriggerManager()
        # Burn 5 at address A — fires.
        for _ in range(4):
            self.assertFalse(mgr.should_run(layer=2, address="locality:a"))
        self.assertTrue(mgr.should_run(layer=2, address="locality:a"))
        # Address B bucket should be independent and still below threshold.
        self.assertFalse(mgr.should_run(layer=2, address="locality:b"))

    def test_independent_per_layer(self):
        mgr = NLTriggerManager()
        # NL3's N = 5 by default; NL4's = 8.
        addr = "region:r1"
        for _ in range(5):
            mgr.should_run(layer=3, address=addr)
        # NL4 at same address should not have fired yet.
        stats = mgr.peek(layer=4, address=addr)
        self.assertEqual(stats["count"], 0)

    def test_load_config_overrides_defaults(self):
        """Config JSON can move N for any layer; loader finds the first int value."""
        here = os.path.dirname(os.path.abspath(__file__))
        # Write a tmp config file.
        import json
        import tempfile
        cfg = {
            "triggers": {
                "nl2": {"events_per_locality": 2, "description": "test"},
                "nl4": {"events_per_region": 3, "description": "test"},
            }
        }
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(cfg, f)
            tmp_path = f.name
        try:
            mgr = NLTriggerManager()
            mgr.load_config(tmp_path)
            self.assertEqual(mgr.n_for_layer(2), 2)
            self.assertEqual(mgr.n_for_layer(4), 3)
            # NL3 not overridden -> default 5 stays.
            self.assertEqual(mgr.n_for_layer(3), 5)
        finally:
            os.remove(tmp_path)

    def test_load_config_missing_file_keeps_defaults(self):
        mgr = NLTriggerManager()
        mgr.load_config("/nonexistent/path.json")
        self.assertEqual(mgr.n_for_layer(2), 5)


if __name__ == "__main__":
    unittest.main()
