# Part 2: Living World AI System

**Priority**: P2 — After Combat Visuals
**Goal**: Build the agent infrastructure that makes the world feel alive — NPCs with memory, factions with relationships, ecosystems with pressure, and events with consequence.

---

## What Exists Today

| System | State | Gap |
|--------|-------|-----|
| LLM Integration | Claude API for item generation, MockBackend fallback | Single backend, no local model support |
| Classifiers | CNN + LightGBM for crafting validation | Working, no gaps for current use |
| NPC System | Static JSON dialogue, quest dispensers | No memory, no personality, no context |
| Quest System | Static objectives from JSON | No generation, no world-awareness |
| World System | Seed-based chunk generation, static resources | No ecosystem tracking, no depletion |
| Event System | None | No world events, no triggers |
| Faction System | None | No factions, no reputation |
| Save System | Full state serialization (JSON) | Ready to persist new data |

---

## Phase 2.1: Memory Layer (FOUNDATION)

**New files**: `ai/memory/event_store.py`, `ai/memory/event_schema.py`, `ai/memory/query.py`

This is the **most critical infrastructure**. Without it, every agent is stateless.

### Event Schema

```python
@dataclass
class WorldEvent:
    """Atomic unit of world memory — every notable thing that happens"""
    event_id: str                    # UUID
    timestamp: float                 # Game time (not real time)
    real_timestamp: float            # Real time for debugging
    event_type: str                  # Category (see EventType enum)

    # WHO
    actor_id: str                    # Who did it (player_id, npc_id, enemy_id, "world")
    actor_type: str                  # "player", "npc", "enemy", "system"

    # WHAT
    action: str                      # Verb: "killed", "crafted", "gathered", "spoke_to", "discovered"
    target_id: Optional[str]         # What was acted upon
    target_type: Optional[str]       # "enemy", "npc", "item", "location", "resource"

    # CONTEXT
    location_chunk: Tuple[int, int]  # Which chunk this happened in
    location_biome: str              # Biome type
    context: Dict[str, Any]          # Flexible context data

    # OUTCOME
    outcome: str                     # "success", "failure", "partial"
    significance: float              # 0.0 (trivial) to 1.0 (world-changing)

    # TAGS for efficient querying
    tags: List[str]                  # ["combat", "boss", "faction:wolves"]

class EventType(Enum):
    # Combat
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DIED = "player_died"
    DAMAGE_DEALT = "damage_dealt"
    DAMAGE_TAKEN = "damage_taken"

    # Crafting
    ITEM_CRAFTED = "item_crafted"
    ITEM_INVENTED = "item_invented"
    RECIPE_DISCOVERED = "recipe_discovered"

    # Gathering
    RESOURCE_GATHERED = "resource_gathered"
    RESOURCE_DEPLETED = "resource_depleted"  # Node fully harvested

    # Social
    NPC_TALKED = "npc_talked"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    FACTION_REP_CHANGED = "faction_rep_changed"

    # World
    AREA_DISCOVERED = "area_discovered"
    DUNGEON_ENTERED = "dungeon_entered"
    DUNGEON_CLEARED = "dungeon_cleared"
    WORLD_EVENT_TRIGGERED = "world_event_triggered"

    # Progression
    LEVEL_UP = "level_up"
    TITLE_EARNED = "title_earned"
    SKILL_LEARNED = "skill_learned"
    CLASS_CHANGED = "class_changed"

    # Economy
    ITEM_BOUGHT = "item_bought"
    ITEM_SOLD = "item_sold"
```

### Event Store (SQLite)

```python
class EventStore:
    """Persistent event storage using SQLite"""

    DB_FILE = "world_memory.db"

    def __init__(self, save_dir: str):
        self.db_path = os.path.join(save_dir, self.DB_FILE)
        self._init_db()

    def _init_db(self):
        """Create tables if not exist"""
        # events table: all columns from WorldEvent
        # event_tags table: event_id × tag (for efficient tag queries)
        # Indexes on: event_type, actor_id, target_id, timestamp, location_chunk

    def record(self, event: WorldEvent) -> None:
        """Store an event"""

    def query(self, **filters) -> List[WorldEvent]:
        """Flexible query interface"""
        # Filters: event_type, actor_id, target_id, since_timestamp,
        #          location_chunk, tags, min_significance, limit

    def get_recent(self, n: int = 50, event_types: List[str] = None) -> List[WorldEvent]:
        """Get N most recent events, optionally filtered by type"""

    def get_actor_history(self, actor_id: str, limit: int = 20) -> List[WorldEvent]:
        """Get all events involving this actor"""

    def get_location_history(self, chunk: Tuple[int, int], limit: int = 20) -> List[WorldEvent]:
        """Get all events in this chunk"""

    def summarize_period(self, since: float, until: float) -> Dict[str, int]:
        """Count events by type in time period — for pacing model"""

    def count_by_type(self, event_type: str, since: float = None) -> int:
        """Count specific event type — for threshold triggers"""
```

### Event Bus Integration

```python
class GameEventBus:
    """Pub/sub system — all game systems publish events, memory layer subscribes"""
    _instance: ClassVar[Optional['GameEventBus']] = None

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}  # event_type → handlers

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type. Handlers receive WorldEvent."""

    def publish(self, event: WorldEvent) -> None:
        """Broadcast event to all subscribers for its type"""

    def subscribe_all(self, handler: Callable) -> None:
        """Subscribe to ALL events (for memory layer)"""
```

### How Events Flow

```
Game Action (combat hit, item crafted, NPC talked to, etc.)
    │
    ├── Existing game logic executes normally (unchanged)
    │
    └── GameEventBus.publish(WorldEvent(...))
            │
            ├── EventStore.record(event)      ← Persists to SQLite
            ├── EcosystemAgent.on_event(event) ← Updates resource tracking
            ├── FactionAgent.on_event(event)   ← Updates reputation
            ├── NPCAgent.on_event(event)       ← Updates NPC knowledge
            └── PacingModel.on_event(event)    ← Tracks tension/reward cadence
```

### Save/Load Integration

The SQLite database file lives alongside save files:
```
saves/
├── save_1.json           # Existing game state
├── save_1_memory.db      # NEW: Event memory for this save
├── save_2.json
└── save_2_memory.db
```

On save: DB is already persisted (SQLite auto-commits). Just ensure path is correct.
On load: Open the corresponding .db file. If missing, start fresh (new game or legacy save).

---

## Phase 2.2: Model Backend Abstraction

**New files**: `ai/backends/base_backend.py`, `ai/backends/ollama_backend.py`, `ai/backends/claude_backend.py`, `ai/backends/mock_backend.py`, `ai/backends/backend_config.py`

### Abstract Interface

```python
class ModelBackend(ABC):
    """Abstract interface for LLM inference — supports any backend"""

    @abstractmethod
    async def generate(self,
                       system_prompt: str,
                       user_prompt: str,
                       examples: List[Dict[str, str]] = None,
                       temperature: float = 0.4,
                       max_tokens: int = 2000,
                       response_format: str = "json") -> str:
        """Generate text. Returns raw string (caller parses JSON if needed)."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is ready (model loaded, API key set, etc.)"""

    @abstractmethod
    def get_model_info(self) -> Dict[str, str]:
        """Return model name, backend type, and capabilities"""

class OllamaBackend(ModelBackend):
    """Local model via Ollama API (http://localhost:11434)"""

    def __init__(self, model_name: str = "llama3.1:8b",
                 base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    async def generate(self, system_prompt, user_prompt, **kwargs) -> str:
        """POST to /api/generate with system + user prompt"""

class ClaudeBackend(ModelBackend):
    """Anthropic API — refactored from existing llm_item_generator.py"""

    def __init__(self, model: str = "claude-sonnet-4-20250514",
                 api_key: str = None):
        # Existing logic from LLMItemGenerator

class MockBackend(ModelBackend):
    """Deterministic responses for testing — refactored from existing MockBackend"""
    # Returns template-based responses based on prompt keywords
```

### Backend Configuration

```python
@dataclass
class BackendConfig:
    """Which backend to use for which task — loaded from JSON"""
    crafting: str = "ollama"        # Backend name for crafting agents
    dialogue: str = "ollama"        # Backend for NPC dialogue
    quests: str = "ollama"          # Backend for quest generation
    lore: str = "ollama"            # Backend for lore/descriptions
    balance_check: str = "mock"     # Backend for balance validation (rule-based)

    # Per-backend settings
    ollama_model: str = "llama3.1:8b"
    ollama_url: str = "http://localhost:11434"
    claude_model: str = "claude-sonnet-4-20250514"
    claude_api_key: str = ""        # From env or .env file

    # Fallback chain: if primary fails, try next
    fallback_order: List[str] = field(default_factory=lambda: ["ollama", "claude", "mock"])

class BackendManager:
    """Manages backend instances and routing"""
    _instance: ClassVar[Optional['BackendManager']] = None

    def get_backend(self, task: str) -> ModelBackend:
        """Get the configured backend for a task type"""

    def generate(self, task: str, system_prompt: str,
                 user_prompt: str, **kwargs) -> str:
        """Route generation to correct backend with fallback chain"""
```

### JSON Config: `AI-Config.JSON/backend-config.json`

```json
{
  "backends": {
    "crafting": "ollama",
    "dialogue": "ollama",
    "quests": "ollama",
    "lore": "ollama",
    "balance_check": "rule_based"
  },
  "ollama": {
    "model": "llama3.1:8b",
    "url": "http://localhost:11434",
    "timeout_seconds": 30
  },
  "claude": {
    "model": "claude-sonnet-4-20250514",
    "timeout_seconds": 30
  },
  "fallback_order": ["ollama", "claude", "mock"],
  "rate_limits": {
    "ollama": { "max_concurrent": 2, "cooldown_ms": 100 },
    "claude": { "max_concurrent": 1, "cooldown_ms": 1000 }
  }
}
```

### Migration Path from Existing Code

The existing `llm_item_generator.py` (1,393 lines) has a working Claude integration. The refactoring:

1. Extract `_call_claude_api()` → `ClaudeBackend.generate()`
2. Extract `MockBackend` class → `ai/backends/mock_backend.py`
3. Extract threading logic → reusable `AsyncAgentRunner`
4. Keep `LLMItemGenerator` as a consumer of `BackendManager` (not the owner of API logic)

---

## Phase 2.3: NPC Agent System

**New files**: `ai/agents/npc_agent.py`, `AI-Config.JSON/npc-personalities.json`

### NPC Memory Model

```python
@dataclass
class NPCMemory:
    """Per-NPC persistent memory — loaded/saved with game state"""
    npc_id: str
    relationship_score: float = 0.0   # -1.0 (hostile) to 1.0 (devoted)
    interaction_count: int = 0
    last_interaction_time: float = 0.0
    emotional_state: str = "neutral"  # neutral, happy, angry, fearful, suspicious, grateful
    knowledge: List[str] = field(default_factory=list)  # Facts this NPC knows
    conversation_summary: str = ""    # Compressed history of conversations
    player_reputation_tags: List[str] = field(default_factory=list)  # ["hero", "crafter", "murderer"]
    quest_state: Dict[str, str] = field(default_factory=dict)  # quest_id → state

class NPCAgent:
    """Generates contextual dialogue for a specific NPC"""

    def __init__(self, npc_id: str, npc_def: NPCDefinition,
                 memory: NPCMemory, event_store: EventStore,
                 backend_manager: BackendManager):
        self.npc_id = npc_id
        self.npc_def = npc_def
        self.memory = memory
        self.event_store = event_store
        self.backend = backend_manager

    def build_context(self, player_character) -> str:
        """Build the context window for this NPC's LLM call"""
        # 1. NPC personality (from JSON template)
        # 2. NPC memory (relationship, emotional state, knowledge)
        # 3. Recent interactions between player and this NPC
        # 4. Recent world events this NPC would know about
        # 5. Current faction standings
        # 6. Player's visible state (equipment, title, class, level)

    async def generate_dialogue(self, player_input: str,
                                player_character) -> str:
        """Generate contextual NPC response"""
        context = self.build_context(player_character)
        system_prompt = self._get_personality_prompt()

        response = await self.backend.generate(
            task="dialogue",
            system_prompt=system_prompt,
            user_prompt=f"Context:\n{context}\n\nPlayer says: {player_input}"
        )

        # Update memory
        self.memory.interaction_count += 1
        self.memory.last_interaction_time = current_game_time()
        self._update_emotional_state(response)
        self._update_knowledge(response)

        return response

    def on_world_event(self, event: WorldEvent):
        """Update NPC knowledge based on world events (gossip propagation)"""
        # Only events with significance > threshold
        # Only events in nearby chunks or involving known entities
        if self._is_relevant(event):
            self.memory.knowledge.append(self._summarize_event(event))
            # Trim knowledge to max items (keep most recent/significant)
            self._trim_knowledge()
```

### NPC Personality Templates: `AI-Config.JSON/npc-personalities.json`

```json
{
  "personality_templates": {
    "blacksmith": {
      "voice": "Gruff, practical, values hard work. Speaks in short sentences. Judges people by their craftsmanship.",
      "knowledge_domains": ["smithing", "metals", "weapons", "armor"],
      "reaction_modifiers": {
        "player_crafts_weapon": "+0.05 relationship",
        "player_kills_nearby": "-0.02 relationship",
        "player_brings_rare_ore": "+0.10 relationship"
      },
      "gossip_interest": ["resource_depleted", "enemy_killed", "item_crafted"]
    },
    "herbalist": {
      "voice": "Gentle, knowledgeable about nature. Uses plant metaphors. Worried about ecosystem balance.",
      "knowledge_domains": ["alchemy", "herbs", "potions", "nature"],
      "reaction_modifiers": {
        "player_gathers_herbs": "+0.03 relationship",
        "resource_depleted": "-0.05 relationship, emotional_state → worried"
      },
      "gossip_interest": ["resource_depleted", "item_crafted", "area_discovered"]
    }
  }
}
```

### Gossip Propagation

When a notable event occurs (significance > 0.3):
1. **Immediate**: NPCs in the same chunk hear about it instantly
2. **Short delay** (1 game-day): NPCs in adjacent chunks hear about it
3. **Medium delay** (3 game-days): NPCs in the same biome hear about it
4. **Long delay** (7 game-days): All NPCs hear about it
5. **Never**: Events with significance < 0.1 don't propagate

The propagation is flag-based (lightweight). NPC knowledge list gets a one-line summary, not the full event.

---

## Phase 2.4: Faction System

**New files**: `ai/agents/faction_agent.py`, `AI-Config.JSON/faction-definitions.json`

### Faction Graph

```python
@dataclass
class Faction:
    """A faction in the world"""
    faction_id: str
    name: str
    description: str
    territory_chunks: List[Tuple[int, int]]  # Chunks this faction controls
    member_npc_ids: List[str]
    hostile_to_player_threshold: float = -0.5  # Below this, faction attacks on sight
    allied_threshold: float = 0.5              # Above this, faction offers help

@dataclass
class FactionState:
    """Runtime state of faction relationships"""
    player_reputation: Dict[str, float]        # faction_id → reputation (-1.0 to 1.0)
    inter_faction: Dict[str, Dict[str, float]] # faction_a → faction_b → relationship
    reputation_history: List[Dict]             # Log of changes with reasons

class FactionSystem:
    """Manages faction relationships and reputation"""
    _instance: ClassVar[Optional['FactionSystem']] = None

    def modify_reputation(self, faction_id: str, delta: float, reason: str):
        """Change player's standing with a faction"""
        # Also ripple to allied/hostile factions (dampened)

    def get_npc_disposition(self, npc_id: str) -> str:
        """How does this NPC's faction feel about the player?"""

    def on_event(self, event: WorldEvent):
        """Update faction reputations based on world events"""
        # Killing faction members → large negative
        # Completing faction quests → positive
        # Trading with faction → small positive
        # Killing faction enemies → positive
```

### Reputation Milestones

When player crosses a reputation threshold (e.g., 0.25, 0.5, 0.75), the system:
1. Generates flavor text via LLM (one-time, cached)
2. Unlocks faction-specific content (recipes, quests, areas)
3. Changes NPC dialogue defaults for that faction

---

## Phase 2.5: Ecosystem Model

**New files**: `ai/agents/ecosystem_agent.py`, `AI-Config.JSON/ecosystem-config.json`

### Resource Pressure Tracking

```python
@dataclass
class BiomeResourceState:
    """Tracks resource pressure for one biome"""
    biome_type: str
    resource_totals: Dict[str, int]     # material_id → total available
    resource_gathered: Dict[str, int]   # material_id → total gathered by player
    depletion_ratio: Dict[str, float]   # material_id → gathered/total (0.0 to 1.0)
    regeneration_rates: Dict[str, float]  # material_id → units per game-day
    scarcity_flags: Dict[str, bool]     # material_id → True if scarce

class EcosystemAgent:
    """Tracks and responds to resource pressure across the world"""

    def __init__(self, event_store: EventStore):
        self.biome_states: Dict[str, BiomeResourceState] = {}
        self.scarcity_threshold: float = 0.7  # 70% depleted = scarce
        self.critical_threshold: float = 0.9  # 90% = critical

    def on_resource_gathered(self, event: WorldEvent):
        """Update resource tracking when player gathers"""

    def tick(self, game_time_delta: float):
        """Called each game-day — regenerate resources, check thresholds"""

    def get_scarcity_report(self) -> Dict[str, List[str]]:
        """Which resources are scarce in which biomes?"""
        # Used by quest generator, NPC dialogue, event triggers

    def get_downstream_effects(self, material_id: str) -> List[str]:
        """What recipes/items are affected by this material's scarcity?"""
        # Walks the recipe dependency graph
```

### Scarcity Propagation

When a resource becomes scarce:
1. **Recipe impact**: Recipes requiring that material are flagged as "expensive"
2. **NPC reactions**: NPCs who care about that resource react in dialogue
3. **Price changes**: (Future) Trading NPCs adjust prices
4. **World events**: At critical threshold, trigger a world event (migration, discovery)
5. **Spawn shifts**: Ecosystem spawns more of depleted resource in adjacent biomes

---

## Phase 2.6: World Event System

**New files**: `ai/agents/event_agent.py`, `AI-Config.JSON/event-triggers.json`

### Event Triggers

```python
@dataclass
class EventTrigger:
    """Condition that fires a world event when met — loaded from JSON"""
    trigger_id: str
    description: str
    conditions: List[Dict[str, Any]]  # AND-combined conditions
    event_template: str               # What happens when triggered
    cooldown_game_days: float         # Minimum time between firings
    one_shot: bool                    # Only fires once ever?

class WorldEventAgent:
    """Monitors thresholds and fires world events"""

    CONDITION_CHECKS = {
        "resource_scarcity": lambda self, c: self._check_scarcity(c),
        "kill_count": lambda self, c: self._check_kills(c),
        "player_level": lambda self, c: self._check_level(c),
        "faction_reputation": lambda self, c: self._check_reputation(c),
        "time_elapsed": lambda self, c: self._check_time(c),
        "area_explored": lambda self, c: self._check_exploration(c),
    }

    def tick(self, game_time: float):
        """Check all triggers each game-day"""
        for trigger in self.triggers:
            if self._all_conditions_met(trigger) and not self._on_cooldown(trigger):
                self._fire_event(trigger)
```

### Event Templates: `AI-Config.JSON/event-triggers.json`

```json
{
  "event_triggers": [
    {
      "trigger_id": "iron_famine",
      "description": "Iron ore becomes critically scarce",
      "conditions": [
        { "type": "resource_scarcity", "material_id": "iron_ore", "min_depletion": 0.9 }
      ],
      "event_template": "resource_crisis",
      "event_params": {
        "resource": "iron_ore",
        "narrative": "The iron veins have run dry. Smiths struggle, and prices soar.",
        "effects": ["npc_dialogue_update", "spawn_new_deposit", "quest_generate"]
      },
      "cooldown_game_days": 30,
      "one_shot": false
    },
    {
      "trigger_id": "wolf_pack_invasion",
      "description": "Too many wolves killed — pack retaliates",
      "conditions": [
        { "type": "kill_count", "enemy_type": "wolf", "count": 50, "timeframe_days": 7 }
      ],
      "event_template": "enemy_invasion",
      "event_params": {
        "enemy_type": "wolf_dire",
        "count": 8,
        "narrative": "A dire wolf pack descends from the mountains, seeking vengeance.",
        "spawn_chunks": "player_adjacent"
      },
      "cooldown_game_days": 14,
      "one_shot": false
    },
    {
      "trigger_id": "first_legendary_craft",
      "description": "Player crafts their first legendary item",
      "conditions": [
        { "type": "crafting_milestone", "quality": "legendary", "count": 1 }
      ],
      "event_template": "reputation_event",
      "event_params": {
        "narrative": "Word of your masterwork spreads across the land.",
        "effects": ["all_faction_rep_plus_0.1", "unlock_master_quests"]
      },
      "cooldown_game_days": 0,
      "one_shot": true
    }
  ]
}
```

### Pacing Model

```python
class PacingModel:
    """Tracks tension and reward cadence — prevents grind slumps and reward floods"""

    def __init__(self, event_store: EventStore):
        self.tension_level: float = 0.5      # 0 = boring, 1 = overwhelming
        self.recent_rewards: int = 0
        self.recent_deaths: int = 0
        self.time_since_discovery: float = 0

    def evaluate(self) -> Dict[str, float]:
        """Returns pacing signals for other agents"""
        return {
            "tension": self.tension_level,
            "reward_saturation": self._calc_reward_saturation(),
            "needs_discovery": self.time_since_discovery > DISCOVERY_THRESHOLD,
            "needs_challenge": self.recent_deaths < CHALLENGE_THRESHOLD,
            "needs_reward": self.recent_rewards < REWARD_THRESHOLD,
        }

    def should_trigger_event(self, event_significance: float) -> bool:
        """Pacing gate — prevents stacking too many events"""
        if self.tension_level > 0.8 and event_significance < 0.5:
            return False  # Already tense, skip minor events
        if self.tension_level < 0.3:
            return True   # Boring — trigger anything
        return True
```

---

## Phase 2.7: Quest Generator

**New files**: `ai/agents/quest_agent.py`

### Quest Generation Flow

```
1. Trigger: NPC interaction, world event, or pacing model request
2. Gather context:
   - NPC memory & personality
   - Current world state (scarcity, factions, recent events)
   - Player history (what quests they've done, their playstyle)
   - Pacing signals (needs challenge? needs reward?)
3. LLM generates quest structure:
   - Objectives grounded in REAL world state (not random)
   - Rewards balanced by difficulty calculator
   - Narrative tied to NPC personality and world events
4. Balance validation (rule-based):
   - Rewards within tier range
   - Objectives achievable with current world state
   - Not a duplicate of recent quest
5. Register quest with QuestSystem
6. NPC presents quest in dialogue
```

### Quest Templates

```python
class QuestTemplate(Enum):
    """Quest archetypes — LLM fills in specifics"""
    GATHER = "gather"           # Collect N of resource (grounded in scarcity)
    HUNT = "hunt"               # Kill N enemies (grounded in ecosystem)
    DELIVER = "deliver"         # Bring item to NPC (grounded in NPC needs)
    EXPLORE = "explore"         # Discover location (grounded in unexplored chunks)
    CRAFT = "craft"             # Create specific item (grounded in NPC request)
    DEFEND = "defend"           # Protect area from invasion (grounded in world event)
    INVESTIGATE = "investigate" # Find cause of event (grounded in mystery)

class QuestAgent:
    def generate_quest(self, npc: NPCAgent, context: Dict) -> QuestDefinition:
        """Generate a quest grounded in world state"""
        # Select template based on pacing + NPC personality + world state
        template = self._select_template(npc, context)

        # Build prompt with real world data
        prompt = self._build_quest_prompt(template, npc, context)

        # Generate via LLM
        raw = self.backend.generate(task="quests", ...)

        # Parse and validate
        quest = self._parse_quest(raw)
        if self.balance_validator.validate_quest(quest):
            return quest
        else:
            return self._fallback_quest(template, npc)  # Rule-based fallback
```

---

## Integration Order

```
Week 1-2:  Phase 2.1 (Memory Layer)
           - EventStore with SQLite
           - WorldEvent schema
           - GameEventBus
           - Wire into existing combat_manager, crafting, gathering
           - Save/load integration

Week 3-4:  Phase 2.2 (Backend Abstraction)
           - ModelBackend interface
           - OllamaBackend + ClaudeBackend + MockBackend
           - BackendManager with fallback chain
           - Refactor llm_item_generator.py to use new backends

Week 5-6:  Phase 2.3 (NPC Agents)
           - NPCMemory data model
           - NPCAgent with context building
           - NPC personality templates (JSON)
           - Gossip propagation (flag-based)
           - Wire into existing NPC interaction UI

Week 7-8:  Phase 2.4 + 2.5 (Factions + Ecosystem)
           - Faction data model and reputation system
           - FactionSystem with event-driven updates
           - BiomeResourceState tracking
           - EcosystemAgent with scarcity detection
           - Scarcity → NPC dialogue impact

Week 9-10: Phase 2.6 (World Events)
           - EventTrigger system with JSON config
           - WorldEventAgent with condition checks
           - PacingModel for cadence control
           - First set of event triggers (5-10)

Week 11-12: Phase 2.7 (Quest Generator)
            - QuestTemplate system
            - QuestAgent with LLM generation
            - Balance validation for generated quests
            - Integration with NPC dialogue flow
```

---

## Critical Design Decisions

1. **SQLite over JSON for memory**: Events need indexed queries (by type, actor, time range). JSON would be too slow for real-time agent lookups. SQLite is single-file, no server, ships with Python.

2. **Event-driven over polling**: Agents don't poll for changes. The EventBus pushes events to them. This keeps the game loop clean and agents decoupled.

3. **Significance scoring**: Not all events matter equally. Gathering 1 copper ore (sig: 0.01) doesn't trigger NPC gossip. Killing a T4 boss (sig: 0.95) does. This prevents information overload.

4. **Pacing as a gate, not a generator**: The PacingModel doesn't create events — it vetoes or approves events proposed by other agents. This keeps it simple and prevents the world from feeling artificially managed.

5. **NPC knowledge is compressed**: NPCs store one-line summaries, not full event data. "The player killed the dire wolf pack leader" not the full WorldEvent. This keeps context windows manageable for local models.

6. **Fallback chain for resilience**: If Ollama is down → try Claude → try Mock. The game never crashes due to AI failure. MockBackend returns reasonable template-based responses.
