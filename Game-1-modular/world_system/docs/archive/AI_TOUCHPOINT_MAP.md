# AI Touchpoint Map — Current State & Design Analysis

**Created**: 2026-03-24
**Updated**: 2026-03-24
**Scope**: Every place AI inference or narrative interpretation fires in the Living World system
**Note**: The exact touchpoint design is secondary to the data layer design. All touchpoints build entirely on the 7-layer data collection system. Get storage and retrieval right first — touchpoints follow naturally.

---

## The 9 Touchpoints

```
TOUCHPOINT                          TYPE            FIRES WHEN
─────────────────────────────────── ─────────────── ──────────────────────────────
LAYER 3 EVALUATORS (milestone-triggered, template output):
 1. Population Dynamics             Template        Milestone enemy_killed
 2. Ecosystem Pressure              Template        Milestone resource_gathered
 3. Combat Proficiency              Template        Milestone kills/damage/dodge/death
 4. Crafting Mastery                Template        Milestone craft/invent
 5. Player Milestones               Template        Milestone level/title/class/skill
 6. Exploration & Discovery         Template        Milestone chunk_entered/area_discovered
 7. Social & Reputation             Template        Milestone npc_interaction/quest
 8. Economy & Items                 Template        Milestone item_acquired/equipped
 9. Dungeon Progress                Template        Milestone dungeon events

LAYER 4 EVALUATORS (accumulation-triggered, template output):
10. Regional Activity Synthesizer   Template        3+ L3 interpretations in district
11. Cross-Domain Pattern Detector   Template        2+ L3 categories in same area
12. Player Identity Consolidator    Template        Every 10 L3 interpretations
13. Faction Narrative Synthesizer   Template        Faction milestone or 5+ social L3s

OTHER TOUCHPOINTS:
14. NPCAgentSystem.generate_dialogue LLM (fallback)  Player talks to NPC
15. FactionSystem._on_milestone      Event only      Rep crosses 0.25/0.50/0.75
16. EcosystemAgent._check_thresholds Event only      Depletion hits 70%/90%
17. LLMItemGenerator.generate        LLM (separate)  Player invents item in crafting UI
```

**Template** = hardcoded f-string with `{enemy}`, `{region}`, `{count}` slots
**LLM** = calls BackendManager → ollama/claude/mock chain
**Event only** = publishes data to bus, generates zero narrative text
**Milestone thresholds**: `1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000`

---

## Touchpoints 1–13: The Layer 3 and Layer 4 Evaluators

### Layer 3 Flow (milestone-triggered)

```
GameEventBus event
    → EventRecorder (wildcard subscriber, priority -10)
    → Convert to WorldMemoryEvent, write to SQLite
    → Increment occurrence count for (actor, type, subtype)
    → If count hits milestone (1,3,5,10,25,50,100...) → trigger interpreter
    → WorldInterpreter.on_trigger() → each Layer 3 evaluator.evaluate()
    → If pattern notable → InterpretedEvent with narrative string
    → Store in SQLite, propagate to region states
    → Check Layer 4 accumulation thresholds
```

### Layer 3 Evaluators (9 total)

| # | Evaluator | Listens to | Key data | Example output |
|---|-----------|-----------|----------|----------------|
| 1 | Population Dynamics | enemy_killed | Kill distribution by species/tier/region + L1 totals | "Wolf population declining in Old Forest. 23 killed." |
| 2 | Ecosystem Pressure | resource_gathered, node_depleted | Depletion state + regen rate + gather rate | "Iron ore nearly exhausted in Eastern Caves. 95% depleted." |
| 3 | Combat Proficiency | kills, damage, dodge, death, status | Full combat picture: kills, near-death, flawless, weapons | "Flawless victory against T2 pack — no damage taken." |
| 4 | Crafting Mastery | craft_attempted, item_invented | ALL discipline counts, quality by discipline, 95%+ scores | "Dual specialty: smithing+enchanting, both 30+ crafts." |
| 5 | Player Milestones | level_up, title, class, skill | Progression stats, milestone significance | "Level 10 reached. A significant milestone." |
| 6 | Exploration | chunk_entered, area_discovered | Unique chunks, distance, biome coverage | "25 unique areas explored. Well-traveled." |
| 7 | Social & Reputation | npc_interaction, quest, faction | NPC/faction metadata, likes/dislikes, region | "Village Guard: Recognized (0.28)." |
| 8 | Economy & Items | item_acquired, equipped, consumed | Collection, usage patterns, equipment swaps | "Heavy potion usage — 8 consumed in recent fights." |
| 9 | Dungeon Progress | dungeon events | Completions by rarity, deaths, clears | "3 rare dungeons completed." |

### Layer 4 Evaluators (4 total, accumulation-triggered)

| # | Evaluator | Consumes | Trigger | Example output |
|---|-----------|----------|---------|----------------|
| 10 | Regional Activity | ALL L3 categories in a district | 3+ L3 interpretations in district | "Player systematically clearing Old Forest — population + resources declining." |
| 11 | Cross-Domain | Different L3 categories in same area | 2+ L3 categories, same area, same window | "Plundering Iron Hills — both wildlife and ore under pressure." |
| 12 | Player Identity | All L3 outputs, weighted | Every 10 L3 interpretations | "Primarily a combatant — 60% of notable activity is combat-related." |
| 13 | Faction Narrative | L3 Social + faction data | Faction milestone OR 5+ social L3s | "Village Guard went from ignoring to recognizing as an ally." |

### What evaluators see (the "two layers down" rule)

| Evaluator Layer | Full visibility | Limited visibility |
|:---:|:---:|:---:|
| Layer 3 | Layer 2 events (in lookback window) | Layer 1 aggregate stats (for broader context) |
| Layer 4 | Layer 3 interpretations (in scope) | Layer 2 events (for supporting detail) |

**Dual coverage is expected and encouraged**: A wolf kill fires both Population ("wolves are dying") and Combat ("player is becoming a skilled hunter"). Context within each evaluator prevents misclassification — Crafting sees ALL discipline counts before declaring a specialty. See [EVALUATOR_DESIGN.md](EVALUATOR_DESIGN.md) for the full specification.

### Templates vs LLM

Templates are correct for Layers 3-4. They fire infrequently, produce one-sentence narratives consumed as background context by NPC prompts. LLM enhancement would add latency for marginal gain on text players rarely read directly.

---

## Touchpoint 14: NPC Dialogue — The Main LLM Consumer

**File**: `living_world/npc/npc_agent.py:142-185`

### What the prompt currently assembles:

**System prompt** (sent as LLM instructions):
```
You are {npc_name}, an NPC in a crafting RPG.
Personality: {voice from personality template}
Knowledge domains: {smithing, metals, weapons, armor}
Current emotion: {emotional_state from NPCMemory}
Relationship with player: {label} ({score})
Interactions so far: {count}

Things you know about the world:
- {knowledge item 1, from gossip/events}
- {knowledge item 2}
- ... (up to 10)

Previous conversation summary: {rolling 500-char summary}
Player reputation: {tags like "crafter", "beast_slayer"}

Return JSON: {"dialogue": "...", "emotion": "...", "disposition_change": 0.0}
```

**User prompt** (the specific interaction):
```
The player says: "{player_input}"
Player level: 12
Player class: Warrior
Player title: Wolf Hunter
Current world conditions: {3 ongoing narratives from WorldQuery.get_world_summary(), truncated to 80 chars each}
```

### What's missing — ranked by impact:

**1. Faction reputation (HIGH IMPACT)**
The NPC belongs to a faction. The player has a reputation with that faction. The NPC doesn't know this.

A guard NPC (Village Guard faction, player rep 0.6 = "respected") should say "The Captain sends regards" — but currently treats the player identically to someone at rep -0.3.

*Data source*: `FactionSystem.get_reputation(faction_id)` + `FactionSystem.get_reputation_label(faction_id)`
*Where to inject*: System prompt, after relationship line. One line: `"Their faction (Village Guard) considers you: respected (0.60)"`

**2. NPC-specific world awareness (MEDIUM IMPACT)**
Currently uses `WorldQuery.get_world_summary()` — a global snapshot. This gives the blacksmith the same world context as the herbalist.

`WorldQuery.query_entity(npc_id)` returns an `EntityQueryResult` with:
- `nearby_relevant_events` — events near this NPC, filtered by their interest tags
- `local_context` — their region's ongoing conditions and recent events
- `ongoing_conditions` — interpretations specifically relevant to this NPC's tags

This is the difference between "the world is dangerous" (generic) and "wolves have been thinning near my forge" (grounded in this NPC's location and interests).

*Where to inject*: Replace the `get_world_summary()` call in `_build_user_prompt` with `query_entity(npc_id)`. Extract 3-5 most relevant items.

**3. Ecosystem scarcity for resources NPC cares about (MEDIUM IMPACT)**
Blacksmith should know iron is scarce. Herbalist should know herbs are depleted.

*Data source*: `EcosystemAgent.get_scarcity_report()`, filtered by NPC's `knowledge_domains`
*Where to inject*: User prompt. One line if relevant: `"Resources they'd care about: iron_ore is critically scarce in mountain (92% depleted)"`

**4. Recent gossip freshness (LOW IMPACT)**
NPC "knows" facts from gossip but can't distinguish between stale knowledge and something just heard. "I just heard that..." vs referencing old news.

*Fix*: Add timestamp to knowledge items. Format as `"[recent] wolf pack killed"` vs `"[old] iron shortage"`. Cheap, informative.

### What I'd NOT add to the prompt:

- **Full EntityQueryResult dump** — too much context bloats the prompt and confuses small models. Select the 3-5 most relevant items by tag score.
- **Reputation history** — NPC doesn't need to know *how* reputation changed, just where it stands.
- **Other NPCs' states** — inter-NPC awareness is interesting but adds complexity without clear player value yet.

---

## Touchpoint 15: Faction Milestones — The Empty Event

**File**: `living_world/factions/faction_system.py:318-336`

When player reputation with a faction crosses 0.25, 0.50, or 0.75:

```python
# What happens now:
bus.publish("FACTION_MILESTONE_REACHED", {
    "faction_id": "village_guard",
    "faction_name": "Village Guard",
    "milestone_label": "Recognized",
    "threshold": 0.25,
    "score": 0.26,
    "unlock_type": "dialogue",
})
print("[FactionSystem] Milestone: Village Guard → Recognized (score: 0.26)")
# ...and that's it. No narrative. No player-visible text.
```

### What should happen here — two options:

**Option A: Template narrative (my recommendation)**
```python
MILESTONE_TEMPLATES = {
    "Recognized": "The {faction_name} have taken notice of your deeds. You are no longer a stranger.",
    "Respected": "Members of the {faction_name} greet you warmly. Doors once closed now stand open.",
    "Honored": "The {faction_name} regard you as one of their own. Their deepest knowledge is yours.",
}
```
Simple, predictable, cheap. Happens ~12 times per playthrough. Templates are sufficient.

**Option B: LLM narrative (if you want unique flavor)**
```python
backend.generate(
    task="faction_narrative",
    system_prompt="Write 1-2 sentences about a player earning faction trust. Tone: epic fantasy.",
    user_prompt=f"Faction: {name}. Milestone: {label}. Recent deeds: {last_3_reasons}.",
    max_tokens=80,
)
```
Cache by `(faction_id, threshold)` — same milestone never regenerated. Worth the one-time cost if you value narrative variety.

### What data is available for the prompt:
- Faction definition (name, description, tags, territory)
- Recent reputation history: `get_recent_history(faction_id, limit=5)` — gives you the *reasons* (e.g., "Killed a wolf pack", "Crafted a weapon")
- Inter-faction context: allied/hostile factions and their current scores
- Which NPCs belong to this faction

### My recommendation:
**Start with templates (Option A).** Add LLM (Option B) later as polish. The player needs to *see* something when milestones fire — right now they see nothing. Templates solve 90% of the problem.

---

## Touchpoint 16: Ecosystem Scarcity Events — Data Without Story

**File**: `living_world/ecosystem/ecosystem_agent.py:244-286`

When resource depletion crosses 70% or 90%:

```python
bus.publish("RESOURCE_SCARCITY", {
    "biome": "mountain",
    "resource_id": "iron_ore",
    "depletion": 0.92,
    "severity": "critical",
}, source="EcosystemAgent")
```

### Current state:
- Event published ✓
- EventRecorder captures it as WorldMemoryEvent ✓ (if mapped in BUS_TO_MEMORY_TYPE — **currently it's NOT mapped**)
- ResourcePressureEvaluator fires on resource_gathered events ✓ (overlapping but different — evaluator counts *events*, ecosystem tracks *state*)
- Nobody converts this into gossip for NPCs ✗
- No narrative generated ✗

### The missing bridge:

Something needs to subscribe to `RESOURCE_SCARCITY` and call `NPCAgentSystem.propagate_gossip()`:

```python
# Proposed: either in EcosystemAgent or as a new subscriber
bus.subscribe("RESOURCE_SCARCITY", self._on_scarcity_gossip)

def _on_scarcity_gossip(self, event):
    data = event.data
    summary = f"{data['resource_id'].replace('_', ' ').title()} is {data['severity']} in {data['biome']}"
    npc_system.propagate_gossip(summary, significance=0.7, ...)
```

### My recommendation:
This bridge belongs in `WorldMemorySystem.initialize()` as a lightweight subscriber — not in the ecosystem agent itself (keep systems decoupled). One subscriber, 10 lines, connects ecosystem state to NPC awareness.

Also: add `RESOURCE_SCARCITY` and `RESOURCE_RECOVERED` to the `BUS_TO_MEMORY_TYPE` mapping in `event_schema.py` so they get recorded in the memory layer.

---

## Touchpoint 17: LLM Item Generator — Separate System

**File**: `systems/llm_item_generator.py`

Uses its own `AnthropicBackend`/`MockBackend`, NOT BackendManager. This is intentional — it predates the backend abstraction and has specialized prompt loading from `Fewshot_llm/`.

### Should it migrate to BackendManager?

**No, not now.** It works. It has its own caching, loading states, and prompt management. Wrapping it would add complexity for no gain. The BackendManager is for *new* systems (dialogue, quests, lore).

If Ollama support for crafting is desired later, a thin adapter can route `task="crafting"` through BackendManager while preserving the existing prompt loading.

---

## Unbuilt Touchpoints — What's Next

| Future touchpoint | Consumes | Produces | Priority |
|------------------|----------|----------|----------|
| **Quest generation** | NPC memory + faction rep + ecosystem scarcity + player behavior | Quest definition JSON | High — makes factions/ecosystem *matter* |
| **Scarcity→gossip bridge** | RESOURCE_SCARCITY events | Gossip summaries to NPCs | High — 10 lines, connects two existing systems |
| **Milestone narrative** | Faction milestone events + recent history | 1-2 sentence flavor text | Medium — templates first, LLM later |
| **Compound event evaluator** | Existing interpretations | "Crisis" narratives when danger+scarcity overlap | Low — interesting but not essential |
| **NPC schedule/behavior** | Memory + faction + ecosystem | NPC movement/state changes | Low — blocked by animation system |

---

## The Big Picture: Data Flow (7-Layer)

```
GAME ACTION (kill, gather, craft, level up)
    │
    ├── GameEventBus ──────────────────────────────────────────────┐
    │       │              │                │                      │
    │  Visual FX (p10) Faction (p5)    Ecosystem (p5)     EventRecorder (p-10)
    │       │              │                │                      │
    │  Screen shake   Rep change ±     Track depletion     L1: stat_tracker++
    │  Damage nums    Ripple allies    Scarcity events     L2: INSERT events
    │  Death FX       Milestone?       Regen tick               │
    │                     │                │           occurrence_counts++
    │                     │                │          milestone hit? (1,3,5,10,25...)
    │                     │                │                      │
    │                     │                │              L3: 9 evaluators
    │                     │                │              (template narratives)
    │                     │                │                      │
    │                     │                │              accumulation check
    │                     │                │                      │
    │                     │                │              L4: 4 connected evaluators
    │                     │                │              (cross-domain patterns)
    │                     │                │                      │
    │                     │                │              L5-7: rare, high-impact
    │                     │                │                      │
    │                     └─── gossip bridge (TODO) ──────────────┘
    │                                                             │
    │                                                    Region states
    │                                                    NPC knowledge
    │                                                             │
    │                                                             ▼
    │                                               WorldQuery.query_entity()
    │                                               (tag-scored, distance-filtered)
    │                                                             │
    │                                                             ▼
    │                                               NPC Dialogue / Quest Gen
    │                                               (top 5 relevant items)
    │
    └── PLAYER SEES: damage numbers, level up text, NPC dialogue
```

### Remaining disconnects:

1. **Faction milestones → player feedback**: Events fire, nothing visible happens
2. **Ecosystem scarcity → NPC awareness**: Data exists, no gossip bridge
3. **WorldQuery richness → NPC prompts**: query_entity() returns 5+ contextual fields, only global summary used

### Priority: Storage and retrieval first

The touchpoint design is secondary. All touchpoints build on the data layer. The immediate priority is:
1. Finalize the 7-layer storage schema (see [STORAGE_SCHEMA.md](STORAGE_SCHEMA.md))
2. Implement the milestone trigger system (replacing primes)
3. Expand evaluators from 5 to 9 with dual-coverage
4. Build Layer 4 connected evaluators
5. Wire the retrieval API (entity-first queries with tag scoring)
6. Then connect the plumbing (gossip bridge, faction templates, NPC prompt enrichment)

See [RETRIEVAL_DESIGN.md](RETRIEVAL_DESIGN.md) for the full retrieval strategy.
