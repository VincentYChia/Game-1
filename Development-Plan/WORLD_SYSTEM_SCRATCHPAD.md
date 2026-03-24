# World System Architecture Scratchpad

**Purpose**: Working document for reasoning through the information flow architecture of the Living World system. This is a thinking document, not a spec.

**Date**: 2026-03-14

---

## The Core Problem Statement

The game has ~10 content generation systems (5 crafting disciplines + hostiles, materials, resource nodes, skills, titles). None of these systems can trigger themselves. They are **tools** — they produce output when called. The question is: **what calls them, with what context, and why?**

The World System is the answer. It serves two roles:
1. **Information Storage & State Management** — the "memory" of what has happened, what exists, what matters
2. **Narrative Routing** — ensuring that when generation happens, it happens coherently within a unified story

The user's key insight: *"The updates will likely be narrative."* The World System doesn't just track state — it maintains narrative threads that give generation calls their context and purpose.

---

## Two Usage Modes

### Mode 1: Reactive / Living World
The world reacts to player actions in real-time. An NPC mentions something, a resource runs dry, a faction shifts. These are **local reactions** that ripple outward based on significance.

### Mode 2: Content Development / Thematic Updates
A developer (or the World System itself over time) wants to introduce a new theme — a new race, a new region, a new conflict. This is a **global injection** that flows downward, informing all the generation tools about the new context.

Both modes flow through the same World System, but in opposite directions:
- **Reactive**: Bottom-up (event happens → local effect → maybe propagates to global)
- **Thematic**: Top-down (narrative decision → flows to all relevant generators)

---

## Research Synthesis: What Works in Practice

### From D&D AI / Story AI Systems

**Three-Layer Architecture** (from AI DM research):
- **Interaction Layer**: Real-time, handles immediate context (what's happening RIGHT NOW)
- **Session Layer**: Structured metadata per play session (key decisions, outcomes)
- **World Layer**: Entity embeddings and relationship graphs, updated only on canonical state changes

This maps well to our problem. The interaction layer is the game loop. The session layer is the EventStore (SQLite). The world layer is the narrative state.

**Task Decomposition** (from SLM research, arXiv Jan 2026):
> "Increasing prompt complexity and constraint specificity beyond a certain point reduces narrative coherence and creativity."

This validates the approach of specialized, narrow generation calls (one for hostiles, one for materials, etc.) rather than one monolithic "generate everything" call. The World System routes context to each tool, but the tools stay focused.

**Causal Propagation** (from PAN world model):
> "Separates the modeling of abstract causal dynamics from the generation of realistic observations."

The World System models **what matters** (abstract causal state). The generation tools produce **what the player sees** (concrete content). These are separate concerns.

### From Dwarf Fortress / Gossip Systems

**Dwarf Fortress Rumors**:
- Rumors originate from witnesses of events
- Spread based on proximity: same site → adjacent → farther (based on "importance")
- Knowledge is limited: NPCs are blank slates until told
- No false rumors (except identity-related) — but in our system, we WANT some uncertainty
- Knowledge decays over weeks/years while maintaining reputation effects

**Gossamer Architecture** (Kreminski, academic research):
- Characters can both **originate** (witness/confabulate) and **propagate** (tell others) knowledge
- Propagation influenced by familiarity/interest in the topic
- Memory decay based on relevance and recency
- "Microstories" — compressed narrative units that flow between agents

**Key Takeaway**: Information should flow as **compressed narrative units** (not raw data), and each NPC/system filters what it cares about based on its personality/domain.

### From Emergent Narrative Research

**Recursive Narrative Scaffolding** (from Dwarf Grandpa project):
- Simulation produces raw events
- A narrative layer extracts "story-worthy" events from the simulation
- Scaffolding structures these into coherent narrative arcs

**Talk of the Town** (Ryan):
- Simulates hundreds of years of history
- NPCs embed in social networks and form **subjective (often false) beliefs**
- This creates "narrative material and dramatic intrigue — family feuds, love triangles, struggling businesses"

This is important: NPCs should have **beliefs**, not facts. An NPC far from an event gets a distorted version. This is feature, not bug.

---

## Information Flow Architecture

### The Three Tiers

```
TIER 3: WORLD NARRATIVE STATE ("Heart of Memory")
  │  The canonical story threads, themes, unresolved tensions
  │  Updated rarely, high significance only
  │  Drives: thematic content generation, new region design,
  │          what NPCs far away might have heard as distant rumors
  │
TIER 2: REGIONAL/FACTIONAL STATE ("Shared Knowledge")
  │  Per-biome, per-faction, per-NPC-cluster knowledge
  │  Updated on notable events (significance > 0.3)
  │  Drives: NPC dialogue context, quest generation,
  │          local world events, resource scarcity reactions
  │
TIER 1: EVENT STREAM ("Raw Memory")
     Every notable thing that happens
     SQLite EventStore (already designed in PART_2)
     Drives: immediate NPC reactions, stat tracking,
             significance scoring for upward propagation
```

### What Stays Local (Tier 1 → Tier 2)

These affect the **next interaction** but don't reshape the world:

| Event | Local Effect | Stays At |
|-------|-------------|----------|
| Player gathers 10 iron ore | Resource node depletes | Tier 1 |
| Player kills 3 wolves | Nearby NPCs notice | Tier 1-2 |
| Player completes a quest quickly | NPC impressed, relationship +0.1 | Tier 1 |
| Player crafts a Fine sword | Blacksmith NPC takes note | Tier 1-2 |
| Specific NPC dialogue content | That NPC remembers | Tier 1 |
| Player equips new gear | Visual change, NPCs may comment | Tier 1 |

### What Propagates Regionally (Tier 2)

These inform nearby NPCs and systems:

| Event | Regional Effect | Propagation |
|-------|----------------|-------------|
| Resource critically depleted | NPCs mention scarcity, prices shift | Same biome NPCs |
| 50 wolves killed in 7 days | Wolf pack invasion event | Adjacent chunks |
| Player reaches Level 15 | NPCs treat player with more respect | All nearby NPCs |
| Player earns a Master title | Reputation spreads | Faction-wide |
| Faction reputation crosses threshold | New quests/dialogue unlock | All faction NPCs |

### What Reaches the World Narrative (Tier 3)

These reshape the story itself:

| Event | World Effect | How It Manifests |
|-------|-------------|-----------------|
| NPC mentions "a new race to the east" | Thread created in world narrative | Future generated content in eastern chunks includes this race |
| NPC mentions "a war to the west" | Thread created | Western NPCs have more war-related dialogue, quests involve conflict |
| Player defeats a T4 boss | Legendary event | All NPCs eventually hear, world events adjust |
| Critical resource gone world-wide | Economic shift | New resource nodes spawn, trade routes change |
| Player becomes Master Enchanter | World recognition | NPCs seek player out, new quest types unlock |

---

## The Narrative Threading Problem

This is the hardest part. The user's example is perfect:

> "An NPC mentions a rumor of a new race to the east or a war to the west. This should get passed into the World System. An NPC further to the west might have more stories about the War or more details. The truth doesn't have to be a single path — rumors can change — but the thread should maintain, and if there's confusion in stories it should be either noted or purposeful."

### How Narrative Threads Work

A **Narrative Thread** is a persistent story element that the World System tracks:

```python
@dataclass
class NarrativeThread:
    thread_id: str                    # UUID
    created_at: float                 # Game time when first introduced
    source: str                       # What originated it ("npc_rumor", "world_event", "player_action", "developer")

    # The core narrative element
    theme: str                        # "war", "new_race", "plague", "migration", "discovery"
    summary: str                      # "A war is brewing in the western territories"
    canonical_facts: List[str]        # Facts that ARE true (for consistency checking)
    unresolved_questions: List[str]   # Things that haven't been decided yet

    # Spatial anchoring
    origin_region: str                # Where this thread originated
    spread_radius: float              # How far it has spread (grows over time)
    relevance_by_region: Dict[str, float]  # region → how relevant (1.0 = epicenter)

    # State
    status: str                       # "rumor", "developing", "active", "resolved", "forgotten"
    significance: float               # How important is this thread? (0.0-1.0)
    last_referenced: float            # Last time any system used this thread

    # What this thread means for content generation
    generation_hints: Dict[str, Any]  # Structured data for generators
    # e.g., {"hostile_types": ["orc_scout"], "material_types": ["war_steel"],
    #        "npc_dialogue_themes": ["fear", "preparation", "refugees"]}
```

### Thread Lifecycle

```
1. INTRODUCTION
   An NPC generates dialogue mentioning "rumors of war to the west"
   → World System creates a NarrativeThread with status="rumor"
   → canonical_facts: ["There are rumors of conflict in the western regions"]
   → unresolved_questions: ["Who is fighting?", "Why?", "How close?"]

2. DEVELOPMENT
   Player travels west. World System sees the active thread.
   → NPCs generated in western chunks reference the thread with MORE detail
   → Each interaction can RESOLVE questions or ADD new ones
   → e.g., NPC says "The Ironhold dwarves have been raiding human settlements"
   → canonical_facts UPDATED: ["Ironhold dwarves raiding human settlements"]
   → unresolved_questions UPDATED: ["Why are they raiding?", "How large is the conflict?"]

3. PROPAGATION WITH DISTORTION
   NPCs far from the epicenter get compressed/distorted versions
   → Western NPC (close): "The Ironhold dwarves attacked Millhaven last week"
   → Central NPC (medium): "I heard there's fighting out west, something about dwarves"
   → Eastern NPC (far): "Rumors of some trouble in the west... probably nothing"

   The SAME thread, filtered by distance. The canonical facts stay true,
   but the NPC's VERSION is filtered/compressed based on proximity.

4. ESCALATION (optional)
   If player engages with the thread (travels west, asks about it, takes a quest),
   the thread's significance increases → more content generated around it
   → New hostile types (orc scouts, dwarf raiders) spawn in western chunks
   → New materials available (war steel, siege components)
   → New quests generated around the conflict

5. RESOLUTION or DECAY
   If player resolves the conflict → status="resolved", becomes historical
   If player ignores it → significance slowly decays → status="forgotten"
   → But resolved threads become LORE that future threads can reference
```

### Distance-Based Information Quality

```
Distance from epicenter    → Information quality
================================
Same chunk (0)             → Full detail, accurate, emotional
Adjacent chunks (1-2)      → Good detail, mostly accurate
Same biome (3-5)           → Summary, some distortion
Adjacent biome (6-10)      → Compressed rumor, key facts only
Far away (10+)             → Vague mention, possibly inaccurate
Opposite side of world     → May not have heard at all
```

This is NOT about lying. It's about **information compression and uncertainty**. An NPC 50 chunks away doesn't know if the war involves 100 or 1000 soldiers. They just know "there's trouble."

---

## Sentiment Without Conversation

The user raises a critical point:

> "Player interaction won't be with typing or voice, instead through actions. This will be a practice in data science, where we will have to reliably extract sentiment without having a conversation."

### Action-Based Sentiment Extraction

The player's "personality" and "intent" must be inferred from behavior:

```
OBSERVABLE PLAYER ACTIONS         → INFERRED SENTIMENT/INTENT
============================================================
Quest completion speed            → Dedication/engagement level
  - Fast completion               → Eager, competent, invested
  - Slow/abandoned                → Disinterested, overwhelmed

How they completed the quest      → Approach/values
  - Kill quest: killed extra      → Aggressive, thorough
  - Kill quest: killed minimum    → Efficient, possibly merciful
  - Gather quest: gathered extra  → Generous, thorough, or hoarding

What they do between quests       → Priorities/playstyle
  - Combat-focused                → Fighter, seeks challenge
  - Crafting-focused              → Builder, creative
  - Exploring                     → Curious, discoverer
  - Grinding resources            → Optimizer, patient

How they treat NPCs               → Social disposition
  - Visits same NPC repeatedly    → Loyalty, familiarity
  - Visits all NPCs               → Social, explorer
  - Avoids NPCs                   → Loner, self-sufficient

Resource management               → Economic personality
  - Hoards rare materials         → Cautious, planner
  - Uses materials immediately    → Impulsive, present-focused
  - Sells excess                  → Trader, pragmatic

Combat behavior                   → Risk tolerance
  - Takes on higher-tier enemies  → Bold, risk-taker
  - Avoids combat when possible   → Cautious, strategic
  - Dies frequently but persists  → Determined, stubborn
```

### The Player Profile (Computed, Not Stored)

Rather than asking the player who they are, the system **observes and computes** a profile:

```python
@dataclass
class PlayerProfile:
    """Computed from action patterns — updated periodically from EventStore"""

    # Playstyle weights (0.0 to 1.0, should roughly sum to 1.0)
    combat_focus: float      # Time/events spent in combat
    crafting_focus: float    # Time/events spent crafting
    exploration_focus: float # Time/events spent exploring
    social_focus: float      # Time/events spent with NPCs

    # Behavioral traits (computed from patterns)
    risk_tolerance: float    # 0=cautious, 1=reckless
    thoroughness: float      # 0=rushes, 1=completionist
    generosity: float        # 0=hoards, 1=gives freely
    persistence: float       # 0=gives up, 1=never quits

    # Preferences (what the player gravitates toward)
    preferred_disciplines: List[str]  # Ranked crafting disciplines
    preferred_biomes: List[str]       # Where they spend time
    preferred_combat_style: str       # "melee", "ranged", "magic", "mixed"

    # Quest behavior
    avg_quest_completion_speed: float  # Relative to expected time
    quest_completion_rate: float       # % of accepted quests completed
    quest_type_preferences: Dict[str, float]  # gather/hunt/explore/craft → affinity
```

This profile drives what the World System generates. A combat-focused player gets more invasion events. A crafter gets resource discovery events. An explorer gets mysterious new regions.

---

## The World System as Narrative Router

### What the World System Actually Does

```
INPUTS:
  ├── Tier 1: Raw events from EventStore (continuous stream)
  ├── Tier 2: Regional state changes (periodic summaries)
  ├── Tier 3: Active narrative threads (persistent)
  ├── Player Profile (computed periodically)
  └── Developer injections (new themes, content updates)

PROCESSING:
  ├── Significance scoring (what matters?)
  ├── Thread management (create/update/resolve/decay threads)
  ├── Propagation logic (what spreads where, how distorted?)
  ├── Pacing evaluation (is the world too quiet? too chaotic?)
  └── Generation routing (what needs to be generated next?)

OUTPUTS (calls to generation tools):
  ├── NPC dialogue context (for NPC Agent)
  ├── Quest parameters (for Quest Generator)
  ├── Hostile definitions (for Hostile Generator) — NEW
  ├── Material definitions (for Material Generator) — NEW
  ├── Resource node placements (for World Generator) — NEW
  ├── Skill definitions (for Skill Generator) — NEW
  ├── Title definitions (for Title Generator) — NEW
  ├── Chunk themes (for Chunk Generator) — NEW
  └── World event triggers (for Event System)
```

### Example Flow: "War to the West"

```
1. NPC Agent generates dialogue mentioning "rumors of war to the west"
   (This might come from: a narrative thread, randomized personality lore,
    or an LLM embellishment during dialogue generation)

2. World System receives the NPC output, detects a potential narrative thread
   → Extracts: theme="war", direction="west", specificity="rumor"
   → Creates NarrativeThread(status="rumor", origin="western_region")

3. Player travels west. World System checks active threads for this region.
   → Finds: "war" thread with relevance=0.8 for western chunks

4. World System provides context to ALL generators for western content:
   → Hostile Generator: "Include war-related enemies: scouts, deserters, war beasts"
   → Material Generator: "Include war materials: siege iron, war leather, signal powder"
   → Resource Node Generator: "Include abandoned camps, weapon caches"
   → NPC Generator: "NPCs here should reference the conflict with more detail"
   → Title Generator: "Include war-related titles: Peacemaker, War Profiteer, Scout"
   → Skill Generator: "Include combat skills themed around formation fighting"

5. Player encounters a western NPC who says "The Ironhold clan attacked Millhaven"
   → World System updates thread: canonical_facts += new detail
   → Thread significance increases (player engaged with it)

6. Player returns east. Eastern NPCs might now say:
   "I heard something about trouble with dwarves out west. You look like you've seen it."
   (They reference the thread, but with less detail, and they notice the player was there)

7. Over time, if player ignores the thread, it decays.
   If player engages, it escalates into a full storyline with new quests, factions, etc.
```

---

## Generation Tool Integration

### How the 10 Generation Systems Get Their Context

Each generation system needs to answer: "What should I generate, and in what style?"

The World System provides a **GenerationContext** to each tool:

```python
@dataclass
class GenerationContext:
    """What the World System tells a generation tool about what to make"""

    # Spatial
    target_region: str              # Where this content will exist
    target_biome: str               # Biome type
    target_tier: int                # Difficulty tier (1-4)

    # Narrative
    active_threads: List[NarrativeThread]  # Relevant story threads
    regional_themes: List[str]             # ["war", "scarcity", "mystery"]
    tone: str                              # "peaceful", "tense", "dangerous", "mysterious"

    # Player-aware
    player_profile: PlayerProfile   # What kind of player is this?
    player_level: int               # Current level
    player_needs: Dict[str, float]  # From pacing model

    # Constraints
    existing_content: List[str]     # IDs of content that already exists (avoid duplicates)
    scarcity_data: Dict[str, float] # What resources are scarce/abundant
    faction_standings: Dict[str, float]  # Player's reputation with factions
```

### Per-Tool Context Usage

| Tool | What It Reads from Context | What It Produces |
|------|---------------------------|-----------------|
| **Crafting (5 disciplines)** | Already implemented via CNN/LightGBM + LLM. Context adds: thematic flavor text, war-themed item names | Items with narrative-appropriate names/descriptions |
| **Hostile Generator** | active_threads (war → soldiers), biome, tier, player_level | EnemyDefinition JSON matching regional theme |
| **Material Generator** | active_threads (war → war_steel), scarcity_data, biome | MaterialDefinition JSON for new resources |
| **Resource Node Generator** | scarcity_data, biome, active_threads | Placement data for where resources appear |
| **Skill Generator** | player_profile, active_threads, player_level | SkillDefinition JSON that fits the narrative |
| **Title Generator** | player achievements + active_threads | TitleDefinition JSON (war hero, peacemaker, etc.) |
| **Chunk Generator** | active_threads, biome, faction territories | Themed chunk with appropriate content |
| **Quest Generator** | Full context (already designed in PART_2) | QuestDefinition grounded in world state |
| **NPC Dialogue** | Full context (already designed in PART_2) | Contextual dialogue |
| **World Events** | Pacing model + thresholds (already designed) | Event triggers |

---

## The Heart of Memory: World Narrative State

The "heart" is the persistent narrative state that survives across sessions and gives the world its identity:

```python
@dataclass
class WorldNarrativeState:
    """The world's story — persisted alongside save files"""

    # Active narrative threads
    active_threads: List[NarrativeThread]
    resolved_threads: List[NarrativeThread]  # Historical — informs future generation

    # World identity
    world_themes: List[str]           # ["frontier", "magical_resurgence", "ancient_ruins"]
    world_epoch: str                  # Current era name (can shift with major events)
    world_tone: str                   # Overall mood ("hopeful", "dark", "mysterious")

    # Factional landscape
    faction_relationships: Dict       # The political map
    territorial_control: Dict         # Who controls what

    # Economic state
    global_scarcity: Dict[str, float] # World-wide resource pressure
    trade_routes: List[Dict]          # Connections between regions

    # Cosmological (Dwarf Fortress-inspired)
    pantheon: List[Dict]              # Gods/spirits (if applicable)
    creation_myths: List[str]         # Generated at world creation, immutable
    historical_events: List[Dict]     # Major resolved events become history

    # Generation counters
    content_generated: Dict[str, int] # Track what's been generated to avoid saturation
    last_major_event: float           # Game time — for pacing
```

### What Gets Written to the Heart vs. What Stays Local

```
LOCAL ONLY (Tier 1):
  - Exact NPC dialogue text
  - Individual resource gathering events
  - Minor combat encounters
  - Inventory changes
  - Moment-to-moment gameplay

REGIONAL (Tier 2):
  - NPC relationship states
  - Regional resource pressure
  - Faction reputation changes
  - Quest completions and their outcomes
  - Notable combat events (boss kills, streaks)

WORLD HEART (Tier 3):
  - Narrative thread creation/updates
  - Faction-wide state changes
  - World-level resource crises
  - Major player milestones (first legendary, max level)
  - Thematic shifts (war starts, plague spreads, new race discovered)
  - Developer-injected content themes
```

---

## Rumor Consistency Problem

The user nails the hardest problem:

> "If there is a confusion in stories it should be either noted or purposeful."

### Solution: Canonical Facts + Interpreted Versions

Each NarrativeThread has `canonical_facts` — these are TRUE. When an NPC references a thread, they don't get the canonical facts directly. They get a **distance-filtered interpretation**:

```python
def get_npc_version(thread: NarrativeThread, npc: NPC) -> str:
    """What does this NPC know about this thread?"""
    distance = calculate_distance(npc.position, thread.origin_region)
    npc_interest = calculate_relevance(npc.personality, thread.theme)

    if distance < 3 and npc_interest > 0.5:
        # Close and interested: knows canonical facts + has opinions
        return format_detailed_version(thread.canonical_facts, npc.personality)

    elif distance < 8:
        # Medium distance: knows key facts, missing details
        key_facts = thread.canonical_facts[:2]  # Only the headlines
        return format_summary_version(key_facts, npc.personality)

    elif distance < 15:
        # Far: vague rumor, might have details wrong
        return format_rumor_version(thread.summary, npc.personality)

    else:
        # Very far: may not have heard at all
        if thread.significance > 0.8:
            return format_vague_mention(thread.theme)
        return None  # Never heard of it
```

### Purposeful Confusion

Sometimes you WANT NPCs to disagree. This creates intrigue:

```python
# NPC in the west (close to the war):
"The Ironhold dwarves attacked Millhaven. They want the iron mines."

# NPC in the center (medium distance):
"I heard the dwarves are fighting humans over mining rights."

# NPC in the east (far away):
"Something about dwarves causing trouble? I wouldn't worry about it."

# Unreliable NPC (personality: gossip, embellisher):
"The dwarves have raised an army of ten thousand! The king himself leads them!"
```

The `canonical_facts` say: "Ironhold dwarves attacked Millhaven over iron mines."
Each NPC's version is filtered by distance AND personality. An embellisher exaggerates. A scholar is precise. A merchant focuses on economic impact.

The LLM generates the specific dialogue, but the **constraints** (what facts are available, how distorted) come from the World System's distance/personality filter.

---

## Open Questions to Resolve

1. **Thread Creation Trigger**: When an NPC's LLM-generated dialogue introduces a new narrative element (like "war to the west"), how do we detect that this should become a thread? Options:
   - Post-process NPC dialogue with a classifier
   - Require threads to be pre-seeded (limiting emergent narrative)
   - Let the LLM output structured metadata alongside dialogue
   - Hybrid: LLM can propose threads, World System approves

2. **Thread Conflict Resolution**: What if two threads contradict? (NPC A says dwarves, NPC B says orcs for the same region). Options:
   - First-in-wins (first thread's facts are canonical)
   - World System resolves (picks the more interesting one)
   - Both are true (complex multi-faction conflict)
   - The contradiction IS the story (mystery to investigate)

3. **Generation Budget**: How many LLM calls per game-minute/hour are acceptable? This determines how reactive vs. pre-computed the system needs to be.

4. **Thread Decay vs. Persistence**: How long does an ignored thread live? Too short = world feels forgetful. Too long = clutter. Probably: significance-weighted decay with a minimum lifetime.

5. **Developer vs. Emergent Threads**: The user mentions using this for content development (new themes). Should developer-injected threads use the same system as emergent ones? Probably yes, but with `source="developer"` and `significance=1.0` (never decays).

6. **Bootstrapping**: At world creation, should the system pre-generate some narrative threads to give the world immediate depth? (Dwarf Fortress generates centuries of history before play begins.)

7. **How to Extract "Takeaways" from Interactions**: The user says the exact conversation stays local, but the takeaway propagates. We need a reliable way to compress an NPC interaction into a one-line takeaway. Options:
   - LLM summarization call after each interaction
   - Structured output from the dialogue LLM (dialogue + metadata)
   - Rule-based extraction from quest/reputation changes

---

## Relationship to Existing Systems

### StatTracker (exists, 850+ stats)
- **Stays**: Aggregates are useful for player profile computation
- **Supplement**: Memory layer adds temporal/spatial event data
- StatTracker answers "how many wolves total?" Memory answers "when and where and in what context?"

### EventStore (designed in PART_2, not yet built)
- **Foundation**: This IS Tier 1 of the memory architecture
- **Extension**: Add significance scoring and upward propagation logic
- **Extension**: Add thread detection for narrative-significant events

### GameEventBus (exists, ~150 LOC)
- **Keep**: The pub/sub pattern is correct
- **Extension**: Add World System as a subscriber that does significance filtering

### Save System (exists, full state persistence)
- **Extension**: WorldNarrativeState serializes alongside existing save data
- **Extension**: NarrativeThreads persist in SQLite alongside EventStore

### NPC System (exists, static dialogue)
- **Replace dialogue**: Static lines → LLM-generated with thread context
- **Add memory**: NPCMemory per NPC (designed in PART_2)
- **Add gossip**: Distance-based thread propagation

---

## Next Steps (When Moving from Scratchpad to Implementation)

1. **Define NarrativeThread schema** — the exact dataclass and SQLite table
2. **Define GenerationContext** — what the World System passes to each generator
3. **Define PlayerProfile computation** — how to derive traits from EventStore data
4. **Build the significance scorer** — what events become threads?
5. **Build the distance filter** — how threads compress with distance
6. **Build the World System manager** — the central orchestrator
7. **Wire one generator** (probably NPC dialogue) end-to-end as proof of concept

---

## Research Sources

### Story Generation & Narrative AI
- [Can LLMs Generate Good Stories? (arXiv, 2025)](https://arxiv.org/html/2506.10161v1)
- [StoryVerse: Co-authoring Dynamic Plot (FDG 2024)](https://damassets.autodesk.net/content/dam/autodesk/www/pdfs/storyverse-llm-character-simulation-narrative-planning.pdf)
- [Story2Game: Interactive Fiction Generation (arXiv, 2025)](https://arxiv.org/html/2505.03547v1)
- [High-Quality Dynamic Game Content via Small Language Models (arXiv, Jan 2026)](https://arxiv.org/html/2601.23206)
- [LIGS: LLM-Infused Game System for Emergent Narrative (CHI 2025)](https://dl.acm.org/doi/10.1145/3706599.3720212)
- [Awesome Story Generation Paper Collection](https://github.com/yingpengma/Awesome-Story-Generation)

### Memory Architecture & Agent Systems
- [MIRIX: Multi-Agent Memory System (arXiv, 2025)](https://arxiv.org/html/2507.07957v1)
- [Hierarchical Procedural Memory for LLM Agents (arXiv, Dec 2025)](https://arxiv.org/html/2512.18950v1)
- [Game Knowledge Management System: Schema-Governed LLM Pipeline for RPGs (MDPI, Feb 2026)](https://www.mdpi.com/2079-8954/14/2/175)
- [Agent Memory Paper List (comprehensive collection)](https://github.com/Shichun-Liu/Agent-Memory-Paper-List)
- [MemAgents: ICLR 2026 Workshop on Memory for Agentic Systems](https://openreview.net/pdf?id=U51WxL382H)

### World Simulation & Gossip Systems
- [Gossamer: Toward Better Gossip Simulation (Kreminski, CoG 2023)](https://mkremins.github.io/publications/Gossamer_CoG2023.pdf)
- [Dwarf Fortress Rumor System (Wiki)](https://dwarffortresswiki.org/index.php/Rumor)
- [Emily Short: World Simulation for Story Generation (2018)](https://emshort.blog/2018/07/10/mailbag-world-simulation-plug-ins/)
- [WorldMem: Long-term Consistent World Simulation with Memory (arXiv, 2025)](https://arxiv.org/html/2504.12369v1)

### AI Dungeon Master Architecture
- [How to Build an AI Dungeon Master (Medium)](https://medium.com/@kgiannopoulou4033/how-to-build-an-ai-dungeon-master-for-tabletop-rpgs-548b7dd6d1ee)
- [NeverEndingQuest: AI D&D with persistent NPC memory (GitHub)](https://github.com/MoonlightByte/NeverEndingQuest)
- [Mnehmos MCP Server for D&D](https://skywork.ai/skypage/en/ai-dungeon-master-toolkit/1980458059440967680)
