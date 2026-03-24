# AI Touchpoint Map — Current State & Design Analysis

**Created**: 2026-03-24
**Scope**: Every place AI inference or narrative interpretation fires in the Living World system

---

## The 9 Touchpoints

```
TOUCHPOINT                          TYPE            FIRES WHEN
─────────────────────────────────── ─────────────── ──────────────────────────────
1. PopulationChangeEvaluator        Template        Prime-count enemy_killed
2. ResourcePressureEvaluator        Template        Prime-count resource_gathered
3. PlayerMilestoneEvaluator         Template        Prime-count level/kill/craft/title
4. AreaDangerEvaluator              Template        Prime-count damage_taken/death
5. CraftingTrendEvaluator           Template        Prime-count craft_attempted
6. NPCAgentSystem.generate_dialogue LLM (fallback)  Player talks to NPC
7. FactionSystem._on_milestone      Event only      Rep crosses 0.25/0.50/0.75
8. EcosystemAgent._check_thresholds Event only      Depletion hits 70%/90%
9. LLMItemGenerator.generate        LLM (separate)  Player invents item in crafting UI
```

**Template** = hardcoded f-string with `{enemy}`, `{region}`, `{count}` slots
**LLM** = calls BackendManager → ollama/claude/mock chain
**Event only** = publishes data to bus, generates zero narrative text

---

## Touchpoints 1–5: The Pattern Evaluators

All five share identical architecture:

```
GameEventBus event
    → EventRecorder (wildcard subscriber, priority -10)
    → Convert to WorldMemoryEvent, write to SQLite
    → Increment occurrence count for (actor, type, subtype)
    → If count is prime (1,2,3,5,7,11,13...) → trigger interpreter
    → WorldInterpreter.on_trigger() → each evaluator.evaluate()
    → If threshold met → InterpretedEvent with narrative string
    → Store in SQLite, propagate to region states
```

### What each evaluator sees and produces:

| # | Evaluator | Listens to | Key data at trigger | Narrative example | Severity tiers |
|---|-----------|-----------|-------------------|-------------------|----------------|
| 1 | Population | `enemy_killed` | Kill count in locality over lookback window | "The wolf population has been devastated in Old Forest. 47 killed." | 5→minor, 10→moderate, 20→significant, 50→major |
| 2 | Resources | `resource_gathered` | Gather count in locality over lookback | "Iron Ore deposits are critically strained in Iron Hills." | 10→minor, 25→moderate, 50→significant, 100→major |
| 3 | Milestones | kills, levels, crafts, titles, class | Occurrence count matches milestone list | "The adventurer has reached level 10. A major milestone." | Per-milestone configured |
| 4 | Danger | `damage_taken`, `player_death` | threat_score = hits + deaths×10 | "Old Forest is extremely dangerous. 3 deaths." | 5→minor, 10→moderate, 20→significant, 3deaths→major |
| 5 | Crafting | `craft_attempted` | Discipline distribution, quality ratios | "The adventurer is becoming a master smithing crafter." | By specialization ratio + quality |

### What evaluators CAN'T see (and my take on whether they should):

| Missing context | Available in | Should evaluators use it? |
|----------------|-------------|--------------------------|
| Ecosystem depletion % | EcosystemAgent | **No** — evaluators are about *player behavior patterns*, not world state. ResourcePressure already covers this angle via event counting. Double-tracking is waste. |
| Faction reputation | FactionSystem | **No** — evaluators produce world-level narratives, not faction-aware ones. Faction context belongs in NPC dialogue prompts. |
| NPC reactions | NPCMemory | **No** — evaluators shouldn't know about NPCs. Narratives propagate TO NPCs via region states + gossip. Keep the separation. |
| Other evaluator outputs | Interpreter | **Maybe** — a "compound event" evaluator that reads existing interpretations could detect interesting intersections (danger + scarcity = crisis). Worth considering later, not now. |

### My recommendation on evaluators:

Templates are **fine** for these. They fire infrequently (prime-gated), produce one-sentence narratives consumed by region state and NPC knowledge. LLM-upgrading them adds latency for marginal quality gain on text that players rarely read directly — it's background context for NPC prompts. **Don't LLM-enhance evaluators.**

The one exception: if you want evaluators to produce *flavor variations* so the same pattern doesn't always say the exact same thing, an LLM call with tight constraints (30-50 tokens, cached by severity+category) could work. But this is polish, not priority.

---

## Touchpoint 6: NPC Dialogue — The Main LLM Consumer

**File**: `ai/npc/npc_agent.py:142-185`

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

## Touchpoint 7: Faction Milestones — The Empty Event

**File**: `ai/factions/faction_system.py:318-336`

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

## Touchpoint 8: Ecosystem Scarcity Events — Data Without Story

**File**: `ai/ecosystem/ecosystem_agent.py:244-286`

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

## Touchpoint 9: LLM Item Generator — Separate System

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

## The Big Picture: Data Flow Audit

```
GAME ACTION (kill, gather, craft, level up)
    │
    ├── GameEventBus ──────────────────────────────────────────────┐
    │       │              │                │                      │
    │  Visual FX (p10) Faction (p5)    Ecosystem (p5)     EventRecorder (p-10)
    │       │              │                │                      │
    │  Screen shake   Rep change ±     Track depletion      Write to SQLite
    │  Damage nums    Ripple allies    Scarcity events      Prime→Interpreter
    │  Death FX       Milestone?       Regen tick               │
    │                     │                │               5 Evaluators
    │                     │                │                      │
    │                     │                │              InterpretedEvent
    │                     │                │              (narrative text)
    │                     │                │                      │
    │                     └────── NOT CONNECTED ──────────────────┘
    │                                                             │
    │                                                    Region states
    │                                                    NPC knowledge
    │                                                             │
    │                                                             ▼
    │                                               WorldQuery.query_entity()
    │                                               (rich context, UNDERUSED)
    │                                                             │
    │                                                             ▼
    │                                               NPC Dialogue prompt
    │                                               (only uses 3 conditions)
    │
    └── PLAYER SEES: damage numbers, level up text, NPC dialogue
```

### The three disconnects:

1. **Faction milestones → player feedback**: Events fire, nothing visible happens
2. **Ecosystem scarcity → NPC awareness**: Data exists, no gossip bridge
3. **WorldQuery richness → NPC prompts**: query_entity() returns 5 contextual fields, only global summary used

### Design philosophy I'm proposing:

**Don't collect more data. Wire what exists.**

The memory system already records, interprets, and indexes everything. WorldQuery already assembles entity-specific context windows. The evaluators already produce narratives. The ecosystem already tracks scarcity. The faction system already detects milestones.

The work is **plumbing**, not architecture:
- 1 line in system prompt adds faction context
- 1 function swap replaces `get_world_summary()` with `query_entity()`
- 1 subscriber bridges scarcity events to gossip
- 1 template dict gives milestones visible text
- 2 entries in BUS_TO_MEMORY_TYPE map ecosystem events to memory

None of this requires new systems. It requires connecting existing ones.
