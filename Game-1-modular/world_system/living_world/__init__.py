# Living World — Consumer Systems
#
# NOTE: These files are CONSUMERS of the World Memory System, not part of it.
# They live here for organizational convenience but are architecturally separate.
#
# - backends/backend_manager.py  → LLM infrastructure (should eventually move out of world_system/)
# - npc/npc_agent.py             → Dialogue generation (consumer). npc_memory.py is WMS-owned data.
# - factions/faction_system.py   → Reputation decisions (consumer, reads WMS events)
# - ecosystem/ecosystem_agent.py → Resource lifecycle (consumer, reads WMS events)
#
# The World Memory System (world_memory/) collects, interprets, and serves data.
# These consumer systems READ that data and take outgoing actions.
