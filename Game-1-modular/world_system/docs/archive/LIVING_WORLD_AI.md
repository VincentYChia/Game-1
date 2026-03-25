# Living World AI — Phase 2 Systems

**Created**: 2026-03-24
**Updated**: 2026-03-24
**Status**: Active — Phases 2.2–2.5 implemented, integration pending. Layer architecture redesigned (see [LAYER_ARCHITECTURE.md](LAYER_ARCHITECTURE.md))
**Depends on**: Phase 2.1 (World Memory System)

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        GameEventBus                             │
│  ENEMY_KILLED · ITEM_CRAFTED · RESOURCE_GATHERED · LEVEL_UP    │
└──────┬──────────────┬──────────────┬──────────────┬─────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
  ┌─────────┐   ┌──────────┐  ┌──────────┐   ┌──────────┐
  │ Memory  │   │ Faction  │  │Ecosystem │   │   NPC    │
  │ System  │   │ System   │  │  Agent   │   │  Agent   │
  │ (2.1)   │   │ (2.4)    │  │ (2.5)    │   │  (2.3)   │
  └────┬────┘   └────┬─────┘  └────┬─────┘   └────┬─────┘
       │              │              │              │
       │    ┌─────────┴──────────────┴──────────────┘
       │    │         Shared dependency
       ▼    ▼
  ┌──────────────┐         ┌──────────────────────────┐
  │   SQLite     │         │   BackendManager (2.2)   │
  │  EventStore  │         │  ollama → claude → mock  │
  └──────────────┘         └──────────────────────────┘
```

All systems communicate **exclusively** through the GameEventBus.
No system imports another directly. Each subscribes to events it cares about.

---

## File Map

```
world_system/
├── living_world/
│   ├── backends/
│   │   └── backend_manager.py       # 2.2  ModelBackend ABC + 3 backends + manager
│   ├── npc/
│   │   ├── npc_memory.py            # 2.3  Per-NPC persistent state
│   │   └── npc_agent.py             # 2.3  Dialogue generation + gossip engine
│   ├── factions/
│   │   └── faction_system.py        # 2.4  Reputation tracking + ripple effects
│   └── ecosystem/
│       └── ecosystem_agent.py       # 2.5  Biome resource pressure + regeneration
├── world_memory/                    # 2.1  World Memory System
│   ├── event_store.py               #      SQLite schema (Layers 2-7)
│   ├── evaluators/                  #      9 Layer 3 evaluators
│   └── interpreter.py               #      Evaluator orchestrator
├── config/                          # All JSON configuration
│   ├── backend-config.json, npc-personalities.json, faction-definitions.json,
│   └── ecosystem-config.json, memory-config.json, geographic-map.json
└── tests/
    └── test_phase2_systems.py       #      32 tests across all systems
```

---

## Phase 2.2 — BackendManager

**What it does**: Unified LLM interface. Route any AI task to the best available backend.

```
Task arrives ("dialogue", "quest", "lore", "faction_narrative")
     │
     ▼
 ┌─ BackendManager ──────────────────────────────────┐
 │  1. Look up primary backend for this task          │
 │  2. Check availability + rate limit                │
 │  3. Call backend.generate(system, user, temp, max) │
 │  4. On failure → next in fallback chain            │
 └────────────────────────────────────────────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
 OllamaBackend       ClaudeBackend        MockBackend
 (local, fast)       (API, quality)       (always works)
```

**Fallback chain**: `ollama → claude → mock`. The game never crashes from AI failure.

| Backend | When to use | Latency | Quality |
|---------|-------------|---------|---------|
| Ollama | Player has local model running | ~2-5s | Good for dialogue |
| Claude | High-stakes generation (quests, lore) | ~3-8s | Best quality |
| Mock | Testing, no internet, all backends down | <1ms | Template-only |

**Key API**:
```python
manager = BackendManager.get_instance()
manager.initialize()
text, err = manager.generate(task="dialogue", system_prompt="...", user_prompt="...")
```

---

## Phase 2.3 — NPC Agent System

**What it does**: Gives each NPC persistent memory, personality-driven dialogue, and awareness of world events through gossip.

### NPCMemory — What an NPC "knows"

```
┌─ NPCMemory("blacksmith_01") ──────────────────────────┐
│                                                         │
│  relationship_score:  0.35  ──── "friendly"            │
│  emotional_state:     "impressed"                       │
│  interaction_count:   7                                 │
│  knowledge:                                             │
│    • "A dire wolf pack was slain near the forge"        │
│    • "Iron ore is becoming scarce in the mountains"     │
│    • "The player crafted a masterwork longsword"        │
│  conversation_summary:                                  │
│    "Discussed swords. Player asked about rare metals."  │
│  reputation_tags:                                       │
│    ["crafter", "beast_slayer"]                          │
│  quest_state:                                           │
│    {"forge_quest_01": "active"}                         │
└─────────────────────────────────────────────────────────┘
```

Memory is **bounded** — max 30 knowledge items, 500-char summary. Old facts are pruned.
This keeps LLM context windows tight and inference fast.

### Dialogue Generation Flow

```
Player talks to NPC
        │
        ▼
build_system_prompt()                    build_user_prompt()
┌─────────────────────┐                 ┌──────────────────────┐
│ Personality voice    │                 │ Player's words       │
│ Knowledge (10 facts) │                 │ Player level/class   │
│ Emotion + relation   │                 │ World conditions     │
│ Past conversations   │                 │ (from WorldQuery)    │
│ Dialogue style rules │                 └──────────┬───────────┘
└─────────┬───────────┘                             │
          └──────────────┬──────────────────────────┘
                         ▼
              BackendManager.generate(task="dialogue")
                         │
                         ▼
              Parse JSON: {dialogue, emotion, disposition_change}
                         │
                         ▼
              Update NPCMemory (interaction++, emotion, summary)
```

### Gossip Propagation

Events spread outward from their source with time delays:

| Distance | Delay | Example |
|----------|-------|---------|
| Same chunk | Immediate | NPC saw it happen |
| Adjacent chunks | ~60s | Word travels quickly |
| Same district | ~180s | Merchants carry news |
| Global | ~420s | Eventually everyone hears |

Only events above `significance > 0.1` propagate. NPCs only absorb gossip matching their `gossip_interests` tags. A blacksmith hears about crafting and resources; a guard hears about combat and danger.

### 6 Personality Archetypes

| Archetype | Voice | Cares about | Reacts positively to | Reacts negatively to |
|-----------|-------|-------------|---------------------|---------------------|
| **Blacksmith** | Gruff, practical | Smithing, metals | Player crafts weapons | Violence near forge |
| **Herbalist** | Gentle, metaphorical | Alchemy, nature | Player gathers herbs | Over-harvesting |
| **Merchant** | Shrewd, friendly | Trading, prices | Player levels up | — |
| **Guard** | Stern, duty-focused | Combat, patrols | Player kills enemies | Player dies nearby |
| **Scholar** | Curious, verbose | Enchanting, lore | Player enchants items | — |
| **Default** | Friendly villager | General | Player kills enemies | — |

---

## Phase 2.4 — Faction System

**What it does**: Tracks player reputation with 4 factions. Actions ripple through faction alliances. Crossing thresholds unlocks content.

### The 4 Factions

```
          Village Guard ──── allied (0.3) ──── Crafters Guild
              │                                      │
          allied (0.2)                          allied (0.4)
              │                                      │
         Miners Collective ── hostile (-0.3) ── Forest Wardens
```

### Reputation Scale

```
 -1.0          -0.5          -0.25           0.0           0.25          0.5           0.75          1.0
  ├──── Hostile ─┤── Shunned ──┤── Distrusted ─┤── Neutral ──┤─ Recognized ─┤─ Respected ──┤── Honored ──┤
  │              │             │               │             │              │              │             │
  │    Attacks   │  No service │  Cold dialogue│             │  New dialogue│  Quest access│ Recipe access│
  │    on sight  │             │               │             │              │              │             │
```

### Ripple Mechanics

When your reputation changes with one faction, allied and hostile factions feel it:

```
Player kills 20 bandits → Village Guard rep +0.15

Ripple calculation:
  Crafters Guild:  allied (0.3) × ripple_factor (0.3) × 0.15 = +0.014
  Miners Collective: allied (0.2) × 0.3 × 0.15 = +0.009
  Forest Wardens: neutral (0.1) × 0.3 × 0.15 = +0.005 (below threshold, ignored)
```

Only ripples above `0.001` apply. This prevents infinite cascades.

### Event → Reputation Mapping

| Event | Village Guard | Crafters Guild | Forest Wardens | Miners |
|-------|:---:|:---:|:---:|:---:|
| ENEMY_KILLED | +0.02 | — | -0.01 | — |
| ITEM_CRAFTED | — | +0.01 | — | +0.005 |
| RESOURCE_GATHERED | — | — | -0.005 | +0.005 |
| LEVEL_UP | +0.01 | — | — | — |

---

## Phase 2.5 — Ecosystem Agent

**What it does**: Tracks resource depletion per biome. Detects scarcity. Resources regenerate over time.

### Resource Lifecycle

```
 Initial     Player gathers    Scarcity flag     Critical flag    Regeneration
  pool          resources        at 70%            at 90%          over time
   │               │               │                │                │
   ▼               ▼               ▼                ▼                ▼
 ████████████  ████████░░░░  ███░░░░░░░░░░  █░░░░░░░░░░░░░  ███████░░░░░░
 100%           67%           30%             10%              55%
                                 │                │
                                 ▼                ▼
                          RESOURCE_SCARCITY  RESOURCE_SCARCITY
                          severity: scarce   severity: critical
```

### Regeneration Rates

| Rate | Seconds/unit | Use case |
|------|:---:|------------|
| quick | 120 | Common herbs, flowers |
| normal | 300 | Standard wood, basic ore |
| slow | 600 | Iron, marble, ash wood |
| very_slow | 1200 | Mithril, obsidian, crystal |
| null | ∞ | Non-renewable (not currently used) |

### Biome Resource Pools (6 biomes configured)

| Biome | Key Resources | Initial Pools |
|-------|---------------|:---:|
| Peaceful Forest | Oak, herbs, flowers, mushrooms | 80–200 |
| Forest | Oak, ash, herbs (common + rare) | 80–300 |
| Mountain | Iron, copper, stone, mithril | 20–500 |
| Cave | Iron, copper, crystal, obsidian | 15–300 |
| Plains | Herbs, clay, limestone | 150–200 |
| Unknown | Stone (fallback) | 100 |

New resources gathered in untracked biomes are added dynamically.

---

## SQL Schema (EventStore expansion)

6 new tables added to `event_store.py` alongside the existing 7:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `npc_memory` | Per-NPC persistent state | relationship, emotion, knowledge, conversation |
| `faction_state` | Player rep per faction | reputation score, milestones, last change |
| `faction_reputation_history` | Audit trail of rep changes | delta, reason, game_time, is_ripple |
| `biome_resource_state` | Resource tracking per biome | initial, current, gathered, scarce/critical |
| `event_triggers` | Future: world event cooldowns | last_fired, fire_count, is_exhausted |
| `pacing_state` | Future: tension/reward tracking | key-value store for pacing model |

All new tables use `CREATE TABLE IF NOT EXISTS` — zero risk to existing data.

---

## How Each System Uses LLM — Analysis

### Current Reality vs. Intent

The architecture collects rich data but the LLM inference points are **deliberately minimal** right now. Here's where each system stands and what it needs:

### NPC Dialogue — The Primary LLM Consumer

This is the only system that currently calls `BackendManager.generate()`.

**What the prompt sees today**:

```
SYSTEM: "You are Thorin, a gruff blacksmith. Relationship: friendly (0.35).
         You know: [wolf pack killed, iron scarce, player crafted longsword].
         Past talks: Discussed swords. Keep under 150 chars."

USER:   "The player says: 'Got any good weapons?'
         Player level: 12, class: Warrior.
         World conditions: Wolf attacks increase; iron deposits strained."
```

**What it's missing — and what would make it *smart***:

| Missing context | Source | Why it matters |
|----------------|--------|----------------|
| Faction reputation with this NPC's faction | `FactionSystem.get_reputation()` | A "hostile" faction NPC should refuse service, not chat |
| This NPC's recent activity (from WorldQuery) | `WorldQuery.query_entity(npc_id)` | NPC should reference things that happened *to them* |
| Local region conditions | `WorldQuery.query_entity()` → `local_context` | "It's been dangerous around here" — grounded in data |
| Ecosystem scarcity for resources NPC cares about | `EcosystemAgent.get_scarcity_report()` | Blacksmith should mention iron shortage unprompted |
| Recent gossip (with freshness) | Gossip delivery timestamp | "I just heard that..." vs stale knowledge |

The fix is **not more data** — it's **smarter selection**. The prompt should assemble a ~500 token context window from the most *relevant* sources, scored by the NPC's personality tags.

### Faction Milestones — Ungenerated Narratives

When the player crosses a reputation threshold (0.25, 0.50, 0.75), the system publishes `FACTION_MILESTONE_REACHED` but **generates no narrative text**. This is the most obvious place for an LLM call:

```python
# What happens now:
print("[FactionSystem] Milestone: Village Guard → Recognized (score: 0.26)")

# What should happen:
backend.generate(task="faction_narrative", ...)
→ "Word of your deeds has reached the Guard Captain. Soldiers nod as you
   pass — not warm, but no longer suspicious. The barracks door stands
   open to you for the first time."
```

The prompt needs: faction description, milestone label, recent reputation history (the *why*), and inter-faction context. This is a **low-frequency, high-impact** generation — happens maybe 12 times per playthrough. Worth spending quality tokens on.

### Ecosystem Narratives — The Missing Interpretive Layer

The EcosystemAgent tracks numbers perfectly but **never explains them**. When iron ore hits 90% depletion, the game publishes a data event:

```json
{"biome": "mountain", "resource_id": "iron_ore", "depletion": 0.92, "severity": "critical"}
```

But nobody *narrates* this. Two paths:

1. **Template-based** (current pattern from World Interpreter): Good enough for most cases
2. **LLM-enhanced** (for significant events): Generates flavor text that ripples to NPCs as gossip

The clever approach: only invoke LLM when severity is `"critical"` or when scarcity creates a **chain reaction** (e.g., iron scarcity → weapon recipes affected → blacksmith NPC concerned). The ecosystem agent already has the data; it just needs to compose it into a one-sentence summary for gossip propagation.

### World Interpreter — Template→LLM Upgrade Path

The 5 existing PatternEvaluators generate hardcoded narrative strings:

```python
"The wolf population has been devastated in Old Forest. 47 killed."
```

These work. They don't need LLM. But they could *optionally* be upgraded for `severity >= "significant"` events — LLM adds ecological color, long-term implications, NPC-perspective framing. This is a **nice-to-have**, not a priority.

---

## What's Deliberately *Not* Here

| Absent feature | Why |
|---------------|-----|
| Quest generation | Depends on all 4 systems being integrated first. Phase 2.6+. |
| BalanceValidator | Spec exists but implementation deferred. Rule-based gate for AI output. |
| AsyncAgentRunner | Existing `threading.Thread` pattern (from llm_item_generator) works. Pooled executor deferred. |
| Pacing model | Tables created in schema, but tension/reward tracking is future work. |
| NPC schedule/movement | NPCs are stationary. Animation system (Phase 1) prerequisite. |

---

## Design Principles

**1. Compression upward, not mass collection**
Seven layers compress raw events into progressively concise and impactful information. Milestone triggers (1, 3, 5, 10, 25, 50, 100...) sample with logarithmic spacing — dense early, sparse later. The biggest leaps happen at 1, 10, 100, 1000. Each layer exists to condense the one below for better information transfer.

**2. Bounded context, not infinite history**
NPCMemory caps knowledge at 30 items. Conversation summaries at 500 chars. WorldQuery uses dual-windowed results (static minimum + recency bias). Consumers get the top 5-10 most relevant items, tag-scored against their identity. This prevents LLM context bloat while keeping the most useful information.

**3. Cascade by significance, not by type**
Gossip only propagates when `significance > 0.1`. Ripple effects only trigger when `delta >= 0.1`. Layer 3→4 propagation requires severity "significant"+. The systems are **self-throttling** — quiet games stay quiet, eventful games generate rich narratives.

**4. Dual coverage is encouraged**
The same event fires multiple evaluators. Killing wolves triggers Population ("ecosystem impact") AND Combat ("player proficiency"). These are different truths for different consumers. More evaluators is better than fewer — the cost of a no-op evaluation is near zero.

**5. Every system degrades gracefully**
No LLM? Mock backend returns templates. No Ollama? Falls back to Claude. No API key? Falls back to mock. NPC dialogue falls back to relationship-based templates. The game is always playable.

**6. JSON defines the world, code defines the rules**
All thresholds, personalities, faction relationships, regeneration rates, and routing config live in `world_system/config/`. Tuning the world never requires touching Python.

**7. The world has state beyond the player**
Every layer tracks region state, ecosystem state, and faction state — not just player actions. Even without the player doing anything, resources regenerate, factions have territory, and the world has an identity (Layer 7).

---

## Running Tests

```bash
cd Game-1-modular

# Phase 2.1 (memory system) — 10 tests
python world_system/world_memory/test_memory_system.py

# Phase 2.2–2.5 (new systems) — 32 tests
python world_system/tests/test_phase2_systems.py
```

All 42 tests pass with no external dependencies (no API keys, no Ollama, no pygame).
