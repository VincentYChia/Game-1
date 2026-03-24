# Shared Infrastructure

**Cross-cutting systems used by multiple parts of the plan.**

---

## Balance Validator

**New file**: `ai/validators/balance_validator.py`

Shared post-generation gate. Every AI-generated item, quest, or content piece passes through before entering the game world.

```python
class BalanceValidator:
    """Rule-based validation — rejects out-of-range AI outputs"""
    _instance: ClassVar[Optional['BalanceValidator']] = None

    # Tier-based stat ranges (min, max) — derived from existing game data
    DAMAGE_RANGES = {
        1: (5, 25),    2: (20, 60),
        3: (50, 120),  4: (100, 300),
    }
    DEFENSE_RANGES = {
        1: (2, 10),    2: (8, 25),
        3: (20, 50),   4: (40, 120),
    }
    DURABILITY_RANGES = {
        1: (150, 400),  2: (300, 800),
        3: (600, 1500), 4: (1200, 3000),
    }

    def validate_item(self, item_data: dict) -> Tuple[bool, List[str]]:
        """Validate generated item stats are within tier range"""
        errors = []
        tier = item_data.get("tier", 1)
        # Check damage, defense, durability against tier ranges
        # Check that tags are valid (exist in tag-definitions.JSON)
        # Check that rarity matches tier expectations
        return (len(errors) == 0, errors)

    def validate_quest(self, quest_data: dict) -> Tuple[bool, List[str]]:
        """Validate quest rewards and objectives"""
        errors = []
        # Check reward EXP within level-appropriate range
        # Check required materials exist in MaterialDatabase
        # Check enemy targets exist in EnemyDatabase
        return (len(errors) == 0, errors)

    def validate_npc_dialogue(self, dialogue: str) -> Tuple[bool, List[str]]:
        """Basic content validation for generated dialogue"""
        errors = []
        # Length check (not too short, not too long)
        # No out-of-character content (game-world terms only)
        # No real-world references
        return (len(errors) == 0, errors)
```

---

## Async Agent Runner

**New file**: `ai/async_runner.py`

Shared threading infrastructure — extracted from existing `llm_item_generator.py` pattern.

```python
class AsyncAgentRunner:
    """Runs AI agent tasks in background threads without blocking game loop"""

    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.pending_tasks: Dict[str, Future] = {}
        self.results: Dict[str, Any] = {}

    def submit(self, task_id: str, fn: Callable, *args, **kwargs) -> None:
        """Submit task for background execution"""

    def is_complete(self, task_id: str) -> bool:
        """Check if task finished"""

    def get_result(self, task_id: str) -> Optional[Any]:
        """Get result if complete, None if still running"""

    def poll_all(self) -> List[Tuple[str, Any]]:
        """Called from game loop — returns newly completed tasks"""
        # GameEngine.update() calls this each frame
        # Completed tasks are dispatched to their consumers
```

Integration point in `game_engine.py`:
```python
def update(self, dt):
    # ... existing update logic ...

    # Poll async AI tasks
    completed = self.async_runner.poll_all()
    for task_id, result in completed:
        self._handle_ai_result(task_id, result)
```

---

## Event Integration Points

Where to publish events from existing code (minimal changes — just add `event_bus.publish()` calls):

| Existing Code | Event Type | Integration Point |
|---------------|-----------|-------------------|
| `combat_manager.py:apply_damage()` | DAMAGE_DEALT / DAMAGE_TAKEN | After damage applied |
| `combat_manager.py:kill_enemy()` | ENEMY_KILLED | After enemy death |
| `combat_manager.py:player_death()` | PLAYER_DIED | After player death |
| `interactive_crafting.py:complete_craft()` | ITEM_CRAFTED | After item added to inventory |
| `llm_item_generator.py:on_generation_complete()` | ITEM_INVENTED | After LLM item accepted |
| `world_system.py:gather_resource()` | RESOURCE_GATHERED | After resource collected |
| `npc_system.py:interact()` | NPC_TALKED | After dialogue displayed |
| `quest_system.py:complete_quest()` | QUEST_COMPLETED | After rewards granted |
| `quest_system.py:accept_quest()` | QUEST_ACCEPTED | After quest added |
| `leveling.py:level_up()` | LEVEL_UP | After level applied |
| `title_system.py:award_title()` | TITLE_EARNED | After title granted |
| `skill_manager.py:unlock_skill()` | SKILL_LEARNED | After skill added |
| `world_system.py:discover_chunk()` | AREA_DISCOVERED | After first visit to chunk |

Each integration is a **single line addition** — the existing logic is unchanged.

---

## Debug & Monitoring

### AI Dashboard (Debug Mode — F1)

When debug mode is active, add an AI panel showing:
- Current player archetype classification
- Active AI tasks (pending/running)
- Recent world events (last 10)
- NPC memory summaries for nearby NPCs
- Faction reputation bars
- Ecosystem scarcity alerts
- Pacing model tension gauge

### Logging

All AI agent calls logged to `ai_debug_logs/` (same pattern as existing `llm_debug_logs/`):
- Request/response pairs
- Timing data
- Backend used
- Validation results

---

## Data Persistence Summary

| Data | Storage | When Saved |
|------|---------|------------|
| World events | SQLite (`save_X_memory.db`) | Auto-commit on write |
| NPC memories | JSON (in save file) | On game save |
| Faction state | JSON (in save file) | On game save |
| Ecosystem state | JSON (in save file) | On game save |
| Player archetypes | JSON (in save file) | On game save |
| Preferences | JSON (in save file) | On game save |
| Arc stage | Computed (not saved) | Derived on load |
| Backend config | JSON (`AI-Config.JSON/`) | Never (config file) |
| Event triggers | JSON (`AI-Config.JSON/`) | Never (config file) |
