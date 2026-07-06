# Crux Foundry — Scoring & Viability (the universal yardstick)

**Role:** the common currency that lets heterogeneous personas be compared for *relative* balance (METHODOLOGY §2.2).
This is a **fitness function**, and because search-based personas optimize it, it is designed to resist gaming
(Goodhart's law: any measure used as a target degrades). Grounded in procedural-persona playtesting (Holmgård,
Green, Liapis, Togelius — personas as utility functions).

## Primary metric: time-to-threshold (NOT raw cumulative score)
Cumulative score always grows; only the *rate* is meaningful. So the primary measurement is:

> **Time (game-time or action-count) for a persona to reach the viability threshold.**
> A persona that never reaches it within the budget is **below the floor** (non-viable under current parameters).

**Viability threshold (user-set, to be calibrated by trials):** reach **level 10** OR **2000 progression points**
within a time budget **T**. `T` is unknown a priori — set it after baseline trials by inspecting the score/time
distribution in the daily ledger.

## The progression score (v1 — refined from the user's draft)
| Component | Points | Notes |
|-----------|--------|-------|
| Level gained | **+100 / level** | Universal progress spine (all paths yield EXP). Flat is fine below L10. |
| Craft a **new** recipe | **+15, +10, +5, 0** (diminishing per *distinct* recipe) | Rewards crafting *breadth*, not spam. Confirm: diminishing counts distinct recipes/discipline, not repeated crafts. |
| Gather resources | **+1 per 50 collected × resource tier** | Tier-scaled (higher tier worth more). |
| Title earned | **+40** | Sparse, meaningful unlock. |
| Skill learned | **+20** | Sparse, meaningful unlock. |
| **First-time discovery** | **+N** (small) | REPLACES "+3 per WMS note". Score *novel* discoveries (encyclopedia first-entry, area-discovered) — sparse and ungameable. |

**Removed:** `+3 per WMS note`. Reason (Goodhart / reward-hacking): it rewards raw *event volume*, biases toward
combat (most events), double-counts kills (already scored via level), and invites low-value spam by search agents.
Discovery intent is preserved via first-time-discovery points instead.

## Observability vs scoring — keep them separate
- **Score = the ruler** (small, clean, deliberate: the table above).
- **WMS + daily ledger = the microscope** (understand *what happened* and *when*). The daily ledger is the
  progression-over-time view used to calibrate `T`, diagnose runs, and detect stalls. **P1 must verify the daily
  ledger populates correctly per run** — it is both a tool and a system-under-test (dogfooding, DC7).
- Do **not** feed the raw event log into the score (that is how Issue-1 gaming happens).

## Secondary metrics (observed, NOT scored) — the Goodhart defense
Pair the score with opposing indicators so a low score can be attributed to *path weakness* vs *policy weakness*
(METHODOLOGY §2.5):
- **Deaths + cause** — a build that only "progresses" by dying/respawning is not viable.
- **Gear/power at threshold** — best weapon tier equipped, total stat power (esp. for combat balance).
- **Efficiency/waste** — idle time, failed actions, wasted mana, redundant crafts.

## Universal score (v1) vs per-persona utility (v2 fallback)
- **v1 — one universal score** (above): all paths judged by progression rate. Matches the user's threshold; simple.
- **v2 — per-persona utility** (if trials show v1 unfairly crushes a legitimate path): each persona scored on its
  own objective (harvester = throughput, crafter = tiers reached), balance = each reaches its own goal comparably.
- **Decision rule:** start v1. If a non-combat path *structurally* cannot reach the threshold, treat it first as a
  **balance signal** (the EXP economy under-rewards that path — the thing we want to find); switch to v2 only if the
  path is legitimately un-scorable on a universal currency.

## Calibration plan (trials first — the user's instinct, and correct)
1. Run baseline trials per persona at current (unchanged) parameters.
2. Inspect score-vs-game-time curves in the **daily ledger** for each persona.
3. Set `T` (time budget) and confirm the level-10 / 2000-pt threshold sits in a discriminating region (not so low
   everyone passes instantly, not so high everyone fails).
4. Record the calibrated `T`, threshold, and the observed per-persona baseline spread as the reference point the
   optimizer improves against.
