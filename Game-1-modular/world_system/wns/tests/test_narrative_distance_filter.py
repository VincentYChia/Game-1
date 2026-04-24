"""Tests for NarrativeDistanceFilter — sibling rejection + depth rules."""

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wns.narrative_distance_filter import (  # noqa: E402
    NarrativeDistanceFilter,
)
from world_system.wns.narrative_store import NarrativeRow  # noqa: E402


def _row(layer: int, address: str, narrative: str = "") -> NarrativeRow:
    return NarrativeRow(
        id=f"{layer}:{address}",
        created_at=0.0,
        layer=layer,
        address=address,
        narrative=narrative or f"L{layer}@{address}",
        tags=[address],
    )


class TestNarrativeDistanceFilter(unittest.TestCase):
    def test_drops_sibling_address_at_firing_layer(self):
        filt = NarrativeDistanceFilter()
        firing_addr = "locality:a"
        # All candidates at layer 2 with different addresses.
        rows = [
            _row(2, "locality:a"),
            _row(2, "locality:b"),  # sibling
            _row(1, "locality:a"),  # full detail at L1 per default NL2 rule
            _row(1, "locality:c"),  # sibling at L1
        ]
        result = filt.filter_for_firing(
            layer=2, address=firing_addr, all_narratives=rows
        )
        # Only matching-address rows kept.
        got_addresses = {r.address for r in result.all()}
        self.assertEqual(got_addresses, {"locality:a"})

    def test_parent_layer_kept_even_if_address_differs(self):
        """Parents at higher layers don't share the firing address, but
        they are listed in brief_summary_layers so they must survive.

        Default NL2 rule: full=[2,1], brief=[3,4,5,6,7]. A parent at layer
        5 at address ``nation:v`` is a legitimate parent summary.
        """
        filt = NarrativeDistanceFilter()
        rows = [
            _row(5, "nation:v"),           # parent, different address — kept
            _row(3, "district:neighbor"),  # parent, different address — kept
            _row(2, "locality:other"),     # sibling at firing layer — dropped
        ]
        result = filt.filter_for_firing(
            layer=2, address="locality:a", all_narratives=rows
        )
        layers_kept = sorted(r.layer for r in result.all())
        self.assertEqual(layers_kept, [3, 5])

    def test_full_detail_vs_brief_classification(self):
        filt = NarrativeDistanceFilter()
        rows = [
            _row(2, "locality:a"),  # full
            _row(1, "locality:a"),  # full
            _row(4, "region:r"),    # brief
            _row(7, "world:w"),     # brief
        ]
        result = filt.filter_for_firing(
            layer=2, address="locality:a", all_narratives=rows,
        )
        self.assertEqual(
            sorted(r.layer for r in result.full_detail), [1, 2]
        )
        self.assertEqual(
            sorted(r.layer for r in result.brief_summary), [4, 7]
        )

    def test_load_config_from_json(self):
        import json
        import tempfile
        cfg = {
            "distance_filter": {
                "nl3": {
                    "full_detail_layers": [3],
                    "brief_summary_layers": [4, 5],
                }
            }
        }
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(cfg, f)
            tmp = f.name
        try:
            filt = NarrativeDistanceFilter()
            filt.load_config(tmp)
            # Under new rule, layer 2 rows are outside the window and dropped.
            rows = [
                _row(3, "district:a"),
                _row(2, "district:a"),  # not in either full or brief set -> drop
                _row(4, "region:r"),
            ]
            result = filt.filter_for_firing(
                layer=3, address="district:a", all_narratives=rows,
            )
            layers_kept = sorted(r.layer for r in result.all())
            self.assertEqual(layers_kept, [3, 4])
        finally:
            os.remove(tmp)


if __name__ == "__main__":
    unittest.main()
