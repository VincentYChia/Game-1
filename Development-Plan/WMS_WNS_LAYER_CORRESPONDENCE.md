# WMS → WNS Layer Correspondence — Design Trace (2026-06-05)

This is a thought-tracing design doc for the layer-correspondence work the project owner asked for. **Read this before reading any code in the WMS/WNS layer-flow area** — it explains the gap that was found, the architectural choice in front of us, and the implementation plan once that choice is made.

## 1. What's wired today (verified against code)

### 1.1 WMS producer pipeline — full, working

Raw event → Layer 2 interpretation → Layer 3 consolidation → Layer 4 province summary → Layer 5 region summary → Layer 6 nation summary → Layer 7 world summary. Each layer's manager registers a callback with the previous layer's manager at boot ([world_memory_system.py:201, 219-220, 239-240, 259-260, 279-280](Game-1-modular/world_system/world_memory/world_memory_system.py#L201)). Each layer writes its summary to its own SQL table ([layer_store.py:85-119](Game-1-modular/world_system/world_memory/layer_store.py#L85) creates `layer3_events` through `layer7_events`). The pump at [world_memory_system.py:490-522](Game-1-modular/world_system/world_memory/world_memory_system.py#L490) calls `should_run()` + `run_summarization()` on each layer once per frame.

This part is fine.

### 1.2 WNS independent trigger — separate trigger system

WNS has its own trigger system. Two variants exist in the codebase:

- **`nl_trigger_manager.py`** — per-layer per-address every-N-events buckets. Default N varies by layer (NL2=5, NL3=5, NL4=8, NL5=12, NL6=15, NL7=20).
- **`cascade_trigger.py`** — uniform geometric cascade with N=3. NL_N+1 fires when N NL_N fires occur at the parent address. Per design discussion 2026-04-26, replaces the per-layer model.

The active production wiring uses `cascade_trigger.py`. `WMSToWNSBridge` subscribes to `WMS_INTERPRETATION_CREATED` (the only WMS bus event today, fired by `WorldInterpreter` at Layer 2 creation), drives the cascade trigger, and on each cascade fire calls `wns.run_weaver(layer=N, address=A, wms_brief=…)`.

This is the trigger the v4 working doc describes at line 13: "WNS fires at every layer NL1-NL7 on an every-N-events-per-layer-per-address cadence."

### 1.3 WMS context fed to WNS weavers — Layer 2 only

When `WMSToWNSBridge` invokes a weaver, it passes a `wms_brief` built by [wms_context_builder.py:46-180](Game-1-modular/world_system/wns/wms_context_builder.py#L46). That builder calls `event_store.query_interpretations(...)` (Layer 2 only) at [wms_context_builder.py:164](Game-1-modular/world_system/wns/wms_context_builder.py#L164). There are no readers of Layer 3, 4, 5, 6, or 7 events anywhere in WNS, WES, or any other gameplay-facing code path.

Verified: `grep -r "layer3_events|layer4_events|layer5_events|layer6_events|layer7_events" --include="*.py"` outside `world_memory/` and `tools/simulate_world_memory.py` returns zero matches.

### 1.4 No WMS bus events for L3-L7

`grep -n "publish|event_bus|GameEventBus|notify|emit"` in all five WMS layer managers returns zero matches. The L2 producer (`WorldInterpreter._publish_interpretation_created` at [interpreter.py:166-188](Game-1-modular/world_system/world_memory/interpreter.py#L166)) is the only WMS layer that publishes a bus event.

## 2. The gap, in one sentence

WMS Layers 3-7 are fully implemented, produce summaries on real triggers, and write to their own SQL tables — but no consumer reads them, and they don't broadcast that they've fired.

## 3. The architectural choice — which model do you want?

Your message said:

> "the context should already cascade downwards, sorting by relevance in reverse similar to how the WMS triggers. But the WNS at higher layers should not trigger unless the WMS triggers it. I suppose you could go straight through pure dialog and NPC interaction so maybe a cascade as a backup is nice. But really what is meant to happen is the the WMS write from the corresponding WNS layer + relevant context as described in the code and documents."

That intent reads against the v4 doc's independent-cascade model. There are two coherent ways to honour your direction. They're not equivalent and they pull the system in different directions.

### Model A — WMS-gated (your message taken literally)

- **WMS L_N firing is the primary trigger for NL_N at the same address tier.** When a region summary fires at `region:silverdocks`, NL5 weaves at `region:silverdocks` reading that summary as primary context.
- The independent cadence (`nl_trigger_manager` / `cascade_trigger`) is demoted to a **backup** path. It still fires when the WMS hasn't crossed its threshold but the player is generating dialog/NPC interactions worth narrative-weaving over.
- NL_N's primary context input is the **corresponding WMS L_N summary** for that address; cascade-down (read L_(N-1), L_(N-2), …, L_2 by relevance) is the fallback when no L_N summary exists yet.
- **Implication for v4 doc**: §3 and §4 need a clarification that WNS-cadence is the backup path; WMS-firing is the lead. This is a real design shift relative to what's written.
- **Pro**: aligns trigger frequency with semantic significance (a region summary is real news; cadence-only NL5 firings can be noisier).
- **Pro**: makes the WMS aggregation pipeline a load-bearing part of the system instead of a write-only sink.
- **Con**: WMS-gated NL_N firings are sparse (NL5+ may rarely fire in short play sessions); cadence is what keeps the narrative engine running consistently.

### Model B — Independent triggers, cascade-down context only

- **Triggers stay as v4 specifies** (`cascade_trigger` independent of WMS).
- The only change: `wms_context_builder.build_wms_brief` is widened so that when NL_N fires at address A, the builder picks the **most-specific-available** WMS layer summary for A — i.e. L_N if one exists at that address, else L_(N-1), … down to L_2 interpretations.
- WMS L3-L7 publishes summary-created bus events for observability, but those events don't trigger NL_N.
- **Implication for v4 doc**: no change. The cascade-down read is a clarification, not a redirection.
- **Pro**: smallest delta; doesn't fight the existing trigger architecture.
- **Pro**: still closes the L3-L7-read gap so the aggregation pipeline has a downstream consumer.
- **Con**: the WMS firing → WNS firing correspondence the user asked for isn't enforced; you'd never get "WMS L5 just fired so NL5 also fires."

### Model C — Both (hybrid)

- Independent cascade fires NL_N as it does today (steady cadence).
- AND when WMS L_N fires for an address, that **additionally** triggers an NL_N weave at that address (event-driven peak).
- NL_N's context builder always uses the cascade-down read (most-specific-available L_N summary first).
- **Pro**: keeps cadence + adds semantic-significance peaks. Closest to "WMS triggers WNS when it has news, cascade keeps things flowing otherwise."
- **Con**: more LLM calls. Cost-control becomes a real concern unless you also tune the cadence down a bit (which is also fine).
- **Implication for v4 doc**: adds a "WMS-firing peak" footnote to §3 trigger model.

## 4. My read on what fits the user's intent best

After re-reading the user's message multiple times, **Model A** is the literal read of "the WNS at higher layers should not trigger unless the WMS triggers it." Model C is the most faithful read of "cascade as a backup is nice." Model B is the smallest-delta read of "context should already cascade downwards."

If I had to pick without further input: **Model C** is the safest bet. It honors both halves of the user's message — WMS-firing is the primary trigger for NL_N AND cascade is the backup. The only cost is some LLM-call inflation, which is fixable by tuning N upward.

But this is a design choice you should make. So pausing for confirmation.

## 5. Implementation plan (independent of model choice)

These changes are needed regardless of which model is picked. They're the "close the L3-L7 read gap" work.

### 5.1 LayerStore — add read methods

`LayerStore` currently has only write + supersession-query methods for layers 3-7. Add:

```python
def get_recent_layer_event(self, layer: int, address: str) -> Optional[Dict]:
    """Return the single most-recent layer-N event at `address`, or None."""

def get_layer_events_for_address(
    self, layer: int, address: str, *, limit: int = 5,
) -> List[Dict]:
    """Return up to `limit` most-recent layer-N events at `address`,
    newest first."""

def get_layer_events_for_ancestor(
    self, layer: int, ancestor_address: str, *, limit: int = 5,
) -> List[Dict]:
    """Return layer-N events whose address is `ancestor_address` or a
    descendant. Used for cross-layer cascade where NL_N looks at L_N+1
    summaries from its parent."""
```

These mirror the existing internal supersession query pattern. ~50 lines of code total.

### 5.2 `wms_context_builder.build_wms_brief` — cascade-down

Today's behaviour is "always read L2 interpretations." New behaviour:

```python
def build_wms_brief(
    *,
    firing_address: str,
    firing_layer: int,                    # NEW — passed by bridge
    event_store: Optional[Any],
    layer_store: Optional[Any],           # NEW — passed by bridge
    geographic_registry: Optional[Any] = None,
    char_budget: int = DEFAULT_CHAR_BUDGET,
    ...
) -> str:
    """Cascade-down read:
    1. Try L_(firing_layer) summary at firing_address.
    2. If empty, try L_(firing_layer - 1) at firing_address.
    3. Continue down to L_2 interpretations.
    4. Render the first non-empty layer's content within char_budget.
    Fail-quiet: return "" if nothing available.
    """
```

The cascade-down is the read-side mirror of the WMS triggers cascading up. Builder honours the char budget and the existing truncation marker. ~80 lines.

### 5.3 WMS layer managers — publish on summary creation

Each of layer3_manager.py through layer7_manager.py adds, inside `_store_summary` after the SQL write succeeds:

```python
self._publish_summary_created(summary, game_time)
```

with a helper:

```python
def _publish_summary_created(self, summary, game_time: float) -> None:
    """Best-effort publish of WMS_LAYER_N_SUMMARY_CREATED."""
    try:
        from events.event_bus import GameEventBus
        bus = GameEventBus.get_instance()
        bus.publish(
            "WMS_LAYER_N_SUMMARY_CREATED",        # N substituted per layer
            {
                "layer": N,
                "address": summary.address,       # region:.. / nation:.. / world:..
                "event_id": summary.event_id,
                "tags": summary.tags,
                "game_time": game_time,
            },
        )
    except Exception:
        pass  # best-effort; never crashes the layer
```

This is needed for Model A and Model C. Not strictly needed for Model B but cheap and adds observability. ~5 per layer × 5 layers = 25 lines.

### 5.4 `WMSToWNSBridge` — subscribe to L3-L7 if Model A or C

Add subscriptions:

```python
for n in (3, 4, 5, 6, 7):
    bus.subscribe(f"WMS_LAYER_{n}_SUMMARY_CREATED", self._on_wms_layer_fired)

def _on_wms_layer_fired(self, event: Any) -> None:
    payload = event.data
    layer = int(payload.get("layer", 0))
    address = payload.get("address", "")
    if not layer or not address:
        return
    # Direct fire — bypass the cascade for the WMS-triggered path.
    self._fire_weaver(layer=layer, address=address)
```

`_fire_weaver` is a refactored helper that the cascade callback also uses. ~40 lines.

### 5.5 Observability

Add to `world_system/wes/observability_runtime.py`:

```python
EVT_WMS_LAYER_3_SUMMARY = "WMS_LAYER_3_SUMMARY_CREATED"
# ... through Layer 7
EVT_WMS_LAYER_FIRED_WNS = "WMS_LAYER_FIRED_WNS"   # bridge-side
```

So the F12 overlay can show the L3-L7 cascade firing in real time. ~15 lines.

### 5.6 Documentation cleanup

- **`Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`** §3 and §4 trigger model — add a clarification subsection describing whichever model is chosen.
- **`world_system/docs/WORLD_MEMORY_SYSTEM.md`** §7.4 "Layer 6 (future)" — replace with current-state description; this section is months stale.
- **`world_system/docs/HANDOFF_STATUS.md`** — confirm canonical; the agent audit found it to be the current authoritative state doc.
- **`world_system/docs/POLITICAL_AND_WMS_USAGE_PLAN.md`** — relevance unknown; needs read.
- **`Development-Plan/SYSTEMS_CATALOG.md`** — update the L5-7 row from "needs end-to-end verification" to "verified producer-side, consumer-side wired with Model X."

## 6. What I'm NOT doing without confirmation

I'm not writing any code yet. The model choice changes which files get touched and what semantics they implement, and I don't want to write code that contradicts the v4 doc unless that's what you want.

## 7. Question for you

Which model? **A** (WMS-gated primary, cascade backup), **B** (independent cadence, cascade-down context only), or **C** (both — WMS-firing is a peak, cascade is the baseline)?

If you're not sure, **C** is my recommendation. It costs more LLM calls than B and is harder to reason about than A, but it's the only one that lets both your stated intent ("WMS triggers WNS") AND the v4 doc's stated cadence model coexist.

Once you pick, I'll implement the plan in §5 in a single change, then do the doc cleanup pass in §5.6 as a second commit. Estimated implementation work: 4-6 hours; doc cleanup: 2-3 hours.
