"""Tests for the JSON config schema validator (2026-06-09).

Closes Cross-cutting Risk #5 (no schema validation at boot). Confirms
that:

- The validator catches missing required keys.
- The validator catches wrong types.
- The validator recurses through nested schemas.
- Boot-time pass against the real `world_system/config/` produces zero
  issues right now (catches drift introduced later).
- Every issue lands in the graceful_degrade log → F12 ring buffer.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

from world_system.config.schema_validator import (  # noqa: E402
    SCHEMA_BACKEND_CONFIG,
    SCHEMA_MEMORY_CONFIG,
    SCHEMA_NPC_PERSONALITIES,
    validate_against_schema,
    validate_known_configs,
)
from world_system.living_world.infra.graceful_degrade import (  # noqa: E402
    GracefulDegradeLogger,
)
from world_system.wes.observability_runtime import (  # noqa: E402
    EVT_GRACEFUL_DEGRADE,
    RuntimeObservability,
    install_graceful_degrade_bridge,
    obs_recent,
)


class TestSchemaCorrectness(unittest.TestCase):
    """The generic validator catches the obvious failure modes."""

    def test_missing_required_key_reported(self) -> None:
        schema = {"required_keys": ["name", "version"]}
        issues = validate_against_schema(
            {"name": "x"}, schema, config_name="test.json",
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("version", issues[0])
        self.assertIn("missing", issues[0])

    def test_wrong_type_reported(self) -> None:
        schema = {"type_checks": {"count": int}}
        issues = validate_against_schema(
            {"count": "not a number"}, schema, config_name="test.json",
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("wrong type", issues[0])

    def test_tuple_type_spec_accepts_any(self) -> None:
        schema = {"type_checks": {"value": (int, float)}}
        self.assertEqual(
            validate_against_schema({"value": 1}, schema, config_name="t.json"),
            [],
        )
        self.assertEqual(
            validate_against_schema({"value": 1.5}, schema, config_name="t.json"),
            [],
        )
        issues = validate_against_schema(
            {"value": "s"}, schema, config_name="t.json",
        )
        self.assertEqual(len(issues), 1)

    def test_nested_schema_recurses(self) -> None:
        schema = {
            "required_keys": ["root"],
            "nested": {
                "root": {
                    "required_keys": ["inner"],
                    "type_checks": {"inner": int},
                },
            },
        }
        # Missing inner.
        issues = validate_against_schema(
            {"root": {}}, schema, config_name="t.json",
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("inner", issues[0])
        self.assertIn("test.json".replace("test", "t"), issues[0])

    def test_non_dict_root_reported(self) -> None:
        issues = validate_against_schema(
            [1, 2, 3], {"required_keys": ["x"]}, config_name="t.json",
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("expected dict at root", issues[0])


class TestRegisteredSchemas(unittest.TestCase):
    """Sanity-check that the registered schemas accept their real configs."""

    def setUp(self) -> None:
        self.config_dir = (
            Path(__file__).resolve().parent.parent
            / "world_system" / "config"
        )

    def test_backend_config_passes_schema(self) -> None:
        path = self.config_dir / "backend-config.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = validate_against_schema(
            data, SCHEMA_BACKEND_CONFIG, config_name="backend-config.json",
        )
        self.assertEqual(issues, [], f"unexpected schema issues: {issues}")

    def test_memory_config_passes_schema(self) -> None:
        path = self.config_dir / "memory-config.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = validate_against_schema(
            data, SCHEMA_MEMORY_CONFIG, config_name="memory-config.json",
        )
        self.assertEqual(issues, [], f"unexpected schema issues: {issues}")

    def test_npc_personalities_passes_schema(self) -> None:
        path = self.config_dir / "npc-personalities.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = validate_against_schema(
            data, SCHEMA_NPC_PERSONALITIES, config_name="npc-personalities.json",
        )
        self.assertEqual(issues, [], f"unexpected schema issues: {issues}")


class TestBootTimeValidationPass(unittest.TestCase):
    """validate_known_configs returns clean for the real config dir today."""

    def test_no_issues_on_real_config_dir(self) -> None:
        report = validate_known_configs()
        # Sum up issues across all known configs; expect zero today.
        total = sum(len(v) for v in report.values())
        self.assertEqual(
            total, 0,
            f"baseline drift detected; issues: {report}",
        )


class TestIssuesSurfaceInF12(unittest.TestCase):
    """Every validator-detected issue lands in the F12 observability buffer."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        GracefulDegradeLogger.reset(log_dir=self.temp_dir)
        RuntimeObservability.reset()
        install_graceful_degrade_bridge()

    def tearDown(self) -> None:
        GracefulDegradeLogger.reset()
        RuntimeObservability.reset()
        try:
            for name in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, name))
            os.rmdir(self.temp_dir)
        except Exception:
            pass

    def test_invalid_config_dir_emits_observability_events(self) -> None:
        # Empty temp dir → every known schema reports "file not found".
        empty_dir = tempfile.mkdtemp()
        try:
            report = validate_known_configs(config_root=Path(empty_dir))
            self.assertGreater(len(report), 0)
            events = [
                e for e in obs_recent(50)
                if e.event_type == EVT_GRACEFUL_DEGRADE
            ]
            # One event per registered schema.
            self.assertGreaterEqual(len(events), len(report))
        finally:
            try:
                os.rmdir(empty_dir)
            except Exception:
                pass

    def test_malformed_json_surfaces_as_warning(self) -> None:
        # Drop a single broken file into the temp dir; check it lands as a
        # warning-severity event.
        broken = Path(self.temp_dir) / "backend-config.json"
        broken.write_text("{ this is not valid json")
        # Other files don't exist — that's fine.
        validate_known_configs(config_root=Path(self.temp_dir))
        events = [
            e for e in obs_recent(50)
            if e.event_type == EVT_GRACEFUL_DEGRADE
        ]
        # Find at least one event tagged with 'parse'.
        parse_events = [e for e in events if "parse" in e.message]
        self.assertGreaterEqual(len(parse_events), 1)
        # Severity is warning, not info.
        self.assertEqual(parse_events[0].fields.get("severity"), "warning")


if __name__ == "__main__":
    unittest.main()
