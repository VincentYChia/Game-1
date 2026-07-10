"""XML batch parser tests — canonical hub fixture cases (§5.3, §6)."""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.living_world.infra.llm_fixtures import (  # noqa: E402
    get_fixture_registry,
)
from world_system.wes.xml_batch_parser import (  # noqa: E402
    XMLBatchParseError,
    parse_xml_batch,
)


class ParseCanonicalFixturesTests(unittest.TestCase):
    """Every hub fixture must be parseable by this module."""

    HUB_CODES = [
        "wes_hub_hostiles",
        "wes_hub_materials",
        "wes_hub_nodes",
        "wes_hub_skills",
        "wes_hub_titles",
    ]

    def test_parses_each_hub_fixture(self) -> None:
        reg = get_fixture_registry()
        for code in self.HUB_CODES:
            fx = reg.require(code)
            specs = parse_xml_batch(fx.canonical_response)
            self.assertGreaterEqual(
                len(specs), 1,
                f"{code}: expected at least one spec",
            )
            spec = specs[0]
            self.assertTrue(spec.spec_id)
            self.assertTrue(spec.plan_step_id)
            self.assertIsInstance(spec.hard_constraints, dict)
            self.assertIsInstance(spec.flavor_hints, dict)
            self.assertIsInstance(spec.cross_ref_hints, dict)


class ParseHandlesCommonVariationsTests(unittest.TestCase):
    def test_multi_spec_batch(self) -> None:
        raw = (
            '<specs plan_step_id="s42" count="2">\n'
            '  <spec id="a" intent="one"\n'
            '        hard_constraints=\'{"tier": 1}\'\n'
            '        flavor_hints=\'{"k": "v"}\'\n'
            '        cross_ref_hints=\'{}\' />\n'
            '  <spec id="b" intent="two"\n'
            '        hard_constraints=\'{"tier": 2}\'\n'
            '        flavor_hints=\'{}\'\n'
            '        cross_ref_hints=\'{}\' />\n'
            '</specs>'
        )
        specs = parse_xml_batch(raw)
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0].spec_id, "a")
        self.assertEqual(specs[0].plan_step_id, "s42")
        self.assertEqual(specs[0].hard_constraints, {"tier": 1})
        self.assertEqual(specs[1].spec_id, "b")
        self.assertEqual(specs[1].hard_constraints, {"tier": 2})

    def test_tolerates_markdown_fences(self) -> None:
        raw = (
            "```xml\n"
            '<specs plan_step_id="s1" count="1">\n'
            '  <spec id="x" intent="a" hard_constraints=\'{}\' '
            "flavor_hints='{}' cross_ref_hints='{}' />\n"
            '</specs>\n'
            "```"
        )
        specs = parse_xml_batch(raw)
        self.assertEqual(len(specs), 1)

    def test_tolerates_preamble(self) -> None:
        raw = (
            "Here is the batch:\n"
            '<specs plan_step_id="s1" count="1">\n'
            '  <spec id="x" intent="a" hard_constraints=\'{}\' '
            "flavor_hints='{}' cross_ref_hints='{}' />\n"
            '</specs>\n'
            "Done."
        )
        specs = parse_xml_batch(raw)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].spec_id, "x")

    def test_missing_optional_attrs_default_empty_dicts(self) -> None:
        raw = (
            '<specs plan_step_id="s1" count="1">\n'
            '  <spec id="x" intent="nothing extra" />\n'
            '</specs>'
        )
        specs = parse_xml_batch(raw)
        self.assertEqual(specs[0].flavor_hints, {})
        self.assertEqual(specs[0].cross_ref_hints, {})
        self.assertEqual(specs[0].hard_constraints, {})


class ParseFailuresTests(unittest.TestCase):
    def test_empty_raw_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch("")

    def test_none_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(None)  # type: ignore[arg-type]

    def test_no_specs_element_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch("<notspecs />")

    def test_missing_plan_step_id_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch('<specs><spec id="x" /></specs>')

    def test_missing_spec_id_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(
                '<specs plan_step_id="s1"><spec intent="a" /></specs>'
            )

    def test_malformed_json_attr_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(
                '<specs plan_step_id="s1">'
                '<spec id="x" hard_constraints="{bad json}" />'
                '</specs>'
            )

    def test_non_object_json_attr_raises(self) -> None:
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(
                '<specs plan_step_id="s1">'
                '<spec id="x" hard_constraints="[1,2,3]" />'
                '</specs>'
            )

    def test_duplicate_spec_ids_raise(self) -> None:
        """Duplicate ids would clobber/double-execute downstream work
        keyed by spec_id (2026-07 LLM-pipeline audit)."""
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(
                '<specs plan_step_id="s1">'
                '<spec id="a" tool="materials"/>'
                '<spec id="a" tool="materials"/>'
                '</specs>'
            )


class ElementChildrenDialectTests(unittest.TestCase):
    """2026-07-10 real-LLM certification: EVERY real model tested (Haiku
    4.5, qwen2.5:14b, gemma3:4b) ignores the attribute dialect and emits
    payloads as child elements. Only hand-written fixtures used the
    canonical shape, so the WES cascade silently produced ZERO content
    on real backends. These fixtures are captured real model output."""

    # Abridged from Haiku 4.5's actual response, 2026-07-10.
    HAIKU_SHAPE = """```xml
<?xml version="1.0" encoding="UTF-8"?>
<specs>
  <spec>
    <intent>Bog-mineral material anchoring salt moors copper economy</intent>
    <hard_constraints>
      <tier>2</tier>
      <biome>salt_moors</biome>
      <category>stone</category>
    </hard_constraints>
    <flavor_hints>
      <name_hint>Verdigris Silt</name_hint>
      <properties>["copper_affinity", "salt_binding"]</properties>
    </flavor_hints>
    <cross_ref_hints>{}</cross_ref_hints>
    <metadata><address>region:ashfall_moors</address></metadata>
  </spec>
</specs>
```"""

    # Abridged from qwen2.5:14b's actual response, 2026-07-10.
    QWEN_SHAPE = (
        '<specs><spec>'
        '<hard_constraints>{"tier": 2, "biome": "bog"}</hard_constraints>'
        '<flavor_hints>{"name_hint": "Mossy Bog Pebble"}</flavor_hints>'
        '</spec></specs>'
    )

    def test_haiku_element_children_shape_parses(self) -> None:
        specs = parse_xml_batch(self.HAIKU_SHAPE, default_plan_step_id="s1")
        self.assertEqual(len(specs), 1)
        s = specs[0]
        self.assertEqual(s.plan_step_id, "s1")
        self.assertEqual(s.spec_id, "spec_001")
        self.assertIn("Bog-mineral", s.item_intent)
        self.assertEqual(s.hard_constraints["tier"], 2)
        self.assertEqual(s.hard_constraints["biome"], "salt_moors")
        self.assertEqual(s.flavor_hints["properties"],
                         ["copper_affinity", "salt_binding"])
        self.assertEqual(s.cross_ref_hints, {})

    def test_qwen_json_in_elements_shape_parses(self) -> None:
        specs = parse_xml_batch(self.QWEN_SHAPE, default_plan_step_id="s9")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].hard_constraints,
                         {"tier": 2, "biome": "bog"})
        self.assertEqual(specs[0].flavor_hints,
                         {"name_hint": "Mossy Bog Pebble"})

    def test_strict_mode_unchanged_without_default(self) -> None:
        """No default_plan_step_id -> the legacy strict contract holds."""
        with self.assertRaises(XMLBatchParseError):
            parse_xml_batch(self.HAIKU_SHAPE)

    def test_attribute_dialect_still_canonical(self) -> None:
        specs = parse_xml_batch(
            '<specs plan_step_id="s1">'
            '<spec id="a" intent="x" hard_constraints=\'{"tier": 3}\'/>'
            '</specs>',
            default_plan_step_id="ignored",
        )
        self.assertEqual(specs[0].spec_id, "a")
        self.assertEqual(specs[0].plan_step_id, "s1")
        self.assertEqual(specs[0].hard_constraints, {"tier": 3})


if __name__ == "__main__":
    unittest.main()
