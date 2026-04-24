"""Tests for :mod:`database_reloader`.

Covers two scenarios explicitly:
- Databases that expose a ``reload()`` method are called.
- Databases that don't are logged (graceful degrade) but the
  dispatcher itself does not raise.
"""

from __future__ import annotations

import sys
import types
import unittest

from world_system.content_registry import database_reloader


class _StubDatabaseWithReload:
    """Singleton stub that tracks calls."""

    _instance = None

    def __init__(self) -> None:
        self.reload_called = 0

    @classmethod
    def get_instance(cls) -> "_StubDatabaseWithReload":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reload(self) -> None:
        self.reload_called += 1


class _StubDatabaseNoReload:
    _instance = None

    def __init__(self) -> None:
        self.attr = 0

    @classmethod
    def get_instance(cls) -> "_StubDatabaseNoReload":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class _StubDatabaseRaises:
    _instance = None

    def __init__(self) -> None:
        self.reload_called = 0

    @classmethod
    def get_instance(cls) -> "_StubDatabaseRaises":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reload(self) -> None:
        self.reload_called += 1
        raise RuntimeError("boom")


class DatabaseReloaderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Reset the underscore-singletons per stub.
        _StubDatabaseWithReload._instance = None
        _StubDatabaseNoReload._instance = None
        _StubDatabaseRaises._instance = None
        # Mount fake modules on sys.modules so the reloader's
        # ``importlib.import_module`` finds them.
        self._injected_modules = []
        self._install_fake_module(
            "world_system.content_registry.tests._reload_fake_with",
            {"StubWithReload": _StubDatabaseWithReload},
        )
        self._install_fake_module(
            "world_system.content_registry.tests._reload_fake_no",
            {"StubNoReload": _StubDatabaseNoReload},
        )
        self._install_fake_module(
            "world_system.content_registry.tests._reload_fake_raises",
            {"StubRaises": _StubDatabaseRaises},
        )
        # Snapshot the reload-target table so tests can mutate cleanly.
        self._orig_targets = database_reloader.registered_targets()

    def tearDown(self) -> None:
        # Remove fake modules.
        for name in self._injected_modules:
            sys.modules.pop(name, None)
        # Restore the original target registry.
        database_reloader._RELOAD_TARGETS.clear()
        for k, v in self._orig_targets.items():
            database_reloader._RELOAD_TARGETS[k] = list(v)

    def _install_fake_module(self, name: str, symbols: dict) -> None:
        mod = types.ModuleType(name)
        for k, v in symbols.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        self._injected_modules.append(name)


class TestReloadForTools(DatabaseReloaderTestCase):
    def test_calls_reload_when_method_exists(self) -> None:
        database_reloader._RELOAD_TARGETS["materials"] = [
            (
                "world_system.content_registry.tests._reload_fake_with",
                "StubWithReload",
                ("reload",),
            )
        ]
        results = database_reloader.reload_for_tools(["materials"])
        self.assertEqual(results.get("StubWithReload"), True)
        self.assertEqual(
            _StubDatabaseWithReload.get_instance().reload_called, 1
        )

    def test_logs_warning_when_reload_missing(self) -> None:
        database_reloader._RELOAD_TARGETS["materials"] = [
            (
                "world_system.content_registry.tests._reload_fake_no",
                "StubNoReload",
                ("reload", "_reload"),
            )
        ]
        results = database_reloader.reload_for_tools(["materials"])
        self.assertEqual(results.get("StubNoReload"), False)

    def test_unknown_tool_is_info_level(self) -> None:
        # Empty registration — not registered at all.
        database_reloader._RELOAD_TARGETS.pop("materials", None)
        results = database_reloader.reload_for_tools(["materials"])
        self.assertEqual(results, {})

    def test_module_import_failure_degrades_gracefully(self) -> None:
        database_reloader._RELOAD_TARGETS["materials"] = [
            (
                "world_system.content_registry.tests._definitely_not_real",
                "Whatever",
                ("reload",),
            )
        ]
        results = database_reloader.reload_for_tools(["materials"])
        self.assertEqual(results.get("Whatever"), False)

    def test_reload_method_that_raises_is_caught(self) -> None:
        database_reloader._RELOAD_TARGETS["materials"] = [
            (
                "world_system.content_registry.tests._reload_fake_raises",
                "StubRaises",
                ("reload",),
            )
        ]
        results = database_reloader.reload_for_tools(["materials"])
        self.assertEqual(results.get("StubRaises"), False)
        # The exception was caught — attempt count incremented.
        self.assertEqual(
            _StubDatabaseRaises.get_instance().reload_called, 1
        )

    def test_register_reload_target_adds_to_table(self) -> None:
        database_reloader._RELOAD_TARGETS.pop("materials", None)
        database_reloader.register_reload_target(
            "materials",
            "world_system.content_registry.tests._reload_fake_with",
            "StubWithReload",
            ("reload",),
        )
        targets = database_reloader.registered_targets().get("materials", [])
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0][1], "StubWithReload")


if __name__ == "__main__":
    unittest.main()
