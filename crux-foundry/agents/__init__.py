"""crux-foundry combat-AI agents.

L1: the enemy control surface. A PolicyEnemy overrides the FSM's decision core
(update_ai) and actuates through the game's own primitives (_move_towards,
start_phased_attack via the combat loop's ATTACK-state gate). No combat_manager
or content changes — we *drive* the existing engine, we do not rewrite it.

See ../AGENT_DESIGN.md for the obs/action/fitness contract and the roadmap.
"""
