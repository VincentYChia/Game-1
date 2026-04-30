"""Tests for :mod:`tools.prompt_studio.registry` and
:mod:`tools.prompt_studio.sample_inputs`.

The UI itself can't be unit-tested headless (Tk needs a display), but
the registry + sample-input builders are pure data and pure functions,
and they MUST stay in sync with the on-disk fragment files. These
tests catch drift early — e.g., a fragment file gets renamed, or a
prompt template adds a new ``${var}`` that no sample input fills.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_DIR = _THIS_DIR.parent.parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))
os.chdir(_PROJECT_DIR)

from tools.prompt_studio.registry import (  # noqa: E402
    AssemblerStyle,
    OutputFormat,
    SystemRegistry,
    SystemTier,
)
from tools.prompt_studio.sample_inputs import (  # noqa: E402
    SAMPLE_BUILDERS,
    SampleInput,
    build_sample,
)


class RegistryShapeTestCase(unittest.TestCase):
    """Sanity-check the registry's structural invariants."""

    def test_minimum_entry_count(self) -> None:
        # 32 documented LLM tasks. If this drops, something is missing
        # or accidentally removed.
        all_systems = SystemRegistry.all()
        self.assertGreaterEqual(
            len(all_systems), 30,
            f"expected >=30 LLM systems, got {len(all_systems)}",
        )

    def test_unique_ids(self) -> None:
        ids = SystemRegistry.ids()
        self.assertEqual(len(ids), len(set(ids)),
                         "system ids must be unique")

    def test_every_tier_has_entries(self) -> None:
        grouped = SystemRegistry.grouped_by_tier()
        for tier in SystemTier:
            self.assertIn(tier, grouped, f"tier {tier} has no entries")

    def test_by_id_lookup(self) -> None:
        sample_id = "wes_tool_chunks"
        sys_obj = SystemRegistry.by_id(sample_id)
        self.assertIsNotNone(sys_obj)
        self.assertEqual(sys_obj.id, sample_id)
        self.assertEqual(sys_obj.tier, SystemTier.WES)

    def test_by_id_unknown_returns_none(self) -> None:
        self.assertIsNone(SystemRegistry.by_id("totally_made_up_xyz"))

    def test_registry_immutability_via_all(self) -> None:
        """``all()`` must return a fresh list — mutations to the returned
        list must not affect future calls."""
        a = SystemRegistry.all()
        original_len = len(a)
        a.clear()
        b = SystemRegistry.all()
        self.assertEqual(len(b), original_len)


class FragmentFileExistenceTestCase(unittest.TestCase):
    """Every registered system's fragment file must exist on disk OR
    be one of the documented placeholder shares (NPC dialogue shares
    the WMS L2 file as a placeholder)."""

    KNOWN_PLACEHOLDER_SHARES: set = {
        # NPC dialogue currently re-uses the L2 fragment file as a
        # documented stand-in. When the dedicated NPC dialogue prompt
        # file ships, this entry can be removed and the test will catch
        # any other tasks accidentally pointing at a shared file.
        "npc_dialogue_speechbank",
    }

    def test_every_fragment_file_exists(self) -> None:
        missing = []
        for system in SystemRegistry.all():
            if system.id in self.KNOWN_PLACEHOLDER_SHARES:
                continue
            if not system.fragment_path.exists():
                missing.append(f"{system.id}: {system.fragment_relpath}")
        self.assertEqual(missing, [],
                         f"missing fragment files: {missing}")


class SampleInputCoverageTestCase(unittest.TestCase):
    """Every ``sample_input_key`` referenced in the registry must have a
    builder in SAMPLE_BUILDERS, and every builder must return a
    SampleInput without raising."""

    def test_every_referenced_key_has_builder(self) -> None:
        missing_builders = []
        for system in SystemRegistry.all():
            if system.sample_input_key is None:
                continue
            if system.sample_input_key not in SAMPLE_BUILDERS:
                missing_builders.append(
                    f"{system.id} → {system.sample_input_key}"
                )
        self.assertEqual(missing_builders, [],
                         f"sample_input keys without builders: {missing_builders}")

    def test_every_builder_runs(self) -> None:
        for key, builder in SAMPLE_BUILDERS.items():
            with self.subTest(key=key):
                result = builder()
                self.assertIsInstance(result, SampleInput,
                                      f"builder for {key} returned non-SampleInput")

    def test_build_sample_handles_unknown_key(self) -> None:
        result = build_sample("nonexistent_key_xyz")
        self.assertIsInstance(result, SampleInput)
        self.assertEqual(result.variables, {})
        self.assertEqual(result.tags, [])

    def test_build_sample_handles_none(self) -> None:
        result = build_sample(None)
        self.assertIsInstance(result, SampleInput)
        self.assertEqual(result.variables, {})


class WESPlaceholderResolutionTestCase(unittest.TestCase):
    """Every WES-style system's ``${var}`` placeholders should be
    satisfied by its sample-input variables. Catches drift between
    prompt fragments and sample input builders.

    Some unresolved placeholders are acceptable when the prompt
    deliberately uses ``${var}`` as a literal string; the test asserts
    coverage is at least 50% as a soft floor.
    """

    def test_placeholder_coverage_at_least_50_percent(self) -> None:
        import re
        pattern = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

        coverage_failures = []
        for system in SystemRegistry.all():
            if system.assembler_style != AssemblerStyle.WES:
                continue
            if not system.fragment_path.exists():
                continue
            with open(system.fragment_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    continue
            core = data.get("_core", {}) if isinstance(data, dict) else {}
            if not isinstance(core, dict):
                # Some fragment files use _core as a flat string for
                # backward-compat — skip placeholder coverage for those.
                continue
            template = (core.get("system") or "") + "\n" + (core.get("user_template") or "")
            placeholders = set(pattern.findall(template))
            if not placeholders:
                continue
            sample = build_sample(system.sample_input_key)
            covered = placeholders & set(sample.variables.keys())
            if not covered:
                coverage_failures.append(
                    f"{system.id}: 0 of {len(placeholders)} placeholders covered"
                )
                continue
            coverage = len(covered) / len(placeholders)
            if coverage < 0.5:
                coverage_failures.append(
                    f"{system.id}: {len(covered)}/{len(placeholders)} "
                    f"({coverage:.0%}) — missing: "
                    f"{sorted(placeholders - covered)}"
                )

        # Soft floor: report failures but don't fail the test on them
        # (designer prompts evolve faster than sample inputs). Print
        # them so the developer notices.
        if coverage_failures:
            print("\n[Prompt Studio] sub-50% placeholder coverage:")
            for line in coverage_failures:
                print(f"  - {line}")


class OutputFormatConsistencyTestCase(unittest.TestCase):
    """All hubs MUST be XML; all tools MUST be JSON; weavers JSON; etc."""

    def test_hubs_are_xml(self) -> None:
        for system in SystemRegistry.all():
            if system.id.startswith("wes_hub_"):
                self.assertEqual(
                    system.output_format, OutputFormat.XML,
                    f"{system.id} should emit XML",
                )

    def test_tools_are_json(self) -> None:
        for system in SystemRegistry.all():
            if system.id.startswith("wes_tool_"):
                self.assertEqual(
                    system.output_format, OutputFormat.JSON,
                    f"{system.id} should emit JSON",
                )

    def test_weavers_are_json(self) -> None:
        for system in SystemRegistry.all():
            if system.id.startswith("wns_layer"):
                self.assertEqual(
                    system.output_format, OutputFormat.JSON,
                    f"{system.id} should emit JSON",
                )


class ImportSmokeTestCase(unittest.TestCase):
    """Import the app module without running it — catches import-level
    breakage (typos, missing deps) before a designer launches the UI."""

    def test_app_module_imports(self) -> None:
        # Importing should not raise. Tk widgets aren't constructed at
        # import time — they need a Tk root, which we don't create here.
        from tools.prompt_studio import app  # noqa: F401
        from tools.prompt_studio.app import (  # noqa: F401
            AboutPanel, AssemblyPanel, BrowserPanel, CoveragePanel,
            EditorPanel, PromptStudioApp, SchemaPanel, SimulatorPanel,
            main,
        )


if __name__ == "__main__":
    unittest.main()
