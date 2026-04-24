"""Tests for the WES deterministic shell (v4 §5, P5).

Every test is importable via ``world_system.wes.tests.*`` so a single
``python -m pytest world_system/wes/tests`` invocation picks them up.

Each test module shares the same sys.path shim pattern used by the
shipped ``world_system/tests/`` suite so the files run whether invoked
from the repo root, from ``Game-1-modular/``, or from within the tests
directory itself.
"""
