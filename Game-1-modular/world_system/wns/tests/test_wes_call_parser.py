"""Tests for world_system.wns.wes_call_parser."""

from __future__ import annotations

import unittest

from world_system.wns.wes_call_parser import (
    DEFAULT_MAX_CALLS_PER_RUN,
    WESCall,
    parse_wes_calls,
)


class TestParseWESCalls(unittest.TestCase):
    def test_no_tags_returns_empty_calls(self) -> None:
        calls, cleaned = parse_wes_calls(
            "The copperdocks buzz with prosperity and dread."
        )
        self.assertEqual(calls, [])
        self.assertEqual(
            cleaned, "The copperdocks buzz with prosperity and dread."
        )

    def test_empty_input(self) -> None:
        calls, cleaned = parse_wes_calls("")
        self.assertEqual(calls, [])
        self.assertEqual(cleaned, "")

    def test_single_tag_extracted_and_stripped(self) -> None:
        text = (
            "Narrative before. "
            '<WES purpose="new-npc">A captain for the moors raiders.</WES>'
            " Narrative after."
        )
        calls, cleaned = parse_wes_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].purpose, "new-npc")
        self.assertEqual(calls[0].body, "A captain for the moors raiders.")
        self.assertNotIn("<WES", cleaned)
        self.assertNotIn("</WES>", cleaned)
        self.assertIn("Narrative before.", cleaned)
        self.assertIn("Narrative after.", cleaned)

    def test_two_tags_both_extracted(self) -> None:
        text = (
            'A. <WES purpose="new-npc">Captain.</WES> '
            'B. <WES purpose="new-chunk">A new biome.</WES> C.'
        )
        calls, _ = parse_wes_calls(text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].purpose, "new-npc")
        self.assertEqual(calls[1].purpose, "new-chunk")

    def test_max_calls_cap_drops_excess_calls_and_tags(self) -> None:
        text = (
            'A. <WES purpose="p1">one</WES> '
            'B. <WES purpose="p2">two</WES> '
            'C. <WES purpose="p3">three</WES>'
        )
        calls, cleaned = parse_wes_calls(text, max_calls=2)
        self.assertEqual(len(calls), 2)
        self.assertEqual([c.purpose for c in calls], ["p1", "p2"])
        # ALL tags stripped from cleaned text, even past-cap one.
        self.assertNotIn("<WES", cleaned)
        self.assertNotIn("three", cleaned)  # body of dropped tag too

    def test_default_cap_is_2(self) -> None:
        # Sanity — confirm the module-level constant.
        self.assertEqual(DEFAULT_MAX_CALLS_PER_RUN, 2)

    def test_missing_purpose_attribute_defaults(self) -> None:
        text = "<WES>An untagged directive.</WES>"
        calls, _ = parse_wes_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].purpose, "unspecified")
        self.assertEqual(calls[0].body, "An untagged directive.")

    def test_single_quoted_purpose(self) -> None:
        text = "<WES purpose='affinity-shift'>shift faction</WES>"
        calls, _ = parse_wes_calls(text)
        self.assertEqual(calls[0].purpose, "affinity-shift")

    def test_bareword_purpose(self) -> None:
        text = "<WES purpose=new-skill>a new skill</WES>"
        calls, _ = parse_wes_calls(text)
        self.assertEqual(calls[0].purpose, "new-skill")

    def test_case_insensitive_tag(self) -> None:
        text = '<wes purpose="x">body</wes>'
        calls, _ = parse_wes_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].purpose, "x")
        self.assertEqual(calls[0].body, "body")

    def test_multiline_body_preserved(self) -> None:
        text = (
            '<WES purpose="long">Line one.\n'
            "Line two.\n"
            "Line three.</WES>"
        )
        calls, _ = parse_wes_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertIn("Line one.", calls[0].body)
        self.assertIn("Line three.", calls[0].body)

    def test_body_whitespace_stripped(self) -> None:
        text = '<WES purpose="x">   leading and trailing   </WES>'
        calls, _ = parse_wes_calls(text)
        self.assertEqual(calls[0].body, "leading and trailing")

    def test_malformed_tag_not_extracted(self) -> None:
        # Missing closing tag — shouldn't match
        text = '<WES purpose="x">incomplete'
        calls, cleaned = parse_wes_calls(text)
        self.assertEqual(calls, [])
        # The malformed text passes through unchanged (modulo whitespace
        # normalization — it has no inner newlines so no change here).
        self.assertEqual(cleaned, text)

    def test_cleaned_text_collapses_excess_blank_lines(self) -> None:
        text = (
            "Para one.\n"
            '\n<WES purpose="x">cut me</WES>\n'
            "\n\nPara two."
        )
        calls, cleaned = parse_wes_calls(text)
        self.assertEqual(len(calls), 1)
        # No more than two newlines in a row in cleaned output.
        self.assertNotIn("\n\n\n", cleaned)


if __name__ == "__main__":
    unittest.main()
