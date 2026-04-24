"""Living World shared infrastructure (v4 P0).

This package contains plumbing that every later phase needs:

- LLM Fixture Registry (``llm_fixtures``) — canonical mock I/O per LLM role,
  enabling end-to-end pseudo-mock pipeline runs. See CC4 in
  ``Development-Plan/WORLD_SYSTEM_WORKING_DOC.md``.
- Graceful-degrade logger (``graceful_degrade``) — structured log entry for
  every graceful-degrade event across Living World subsystems. See CC3.
- Context bundle (``context_bundle``) — typed ``WESContextBundle`` dataclass
  authored by WNS and consumed by WES. See CC2, §4.7.

Nothing here depends on WNS/WES runtime code; this is pure infrastructure
usable by everything else.
"""
