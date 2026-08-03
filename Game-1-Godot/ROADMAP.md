# Game-1 (Godot) — 3D-First Roadmap

**Thesis:** ship a clean, high-fidelity **3D game first**; the "super-computer-solvable" compute foundry
(trained pathing + combat co-evolution) bolts on **later**, as a layer — *not* a rewrite. This works because
**most of the game-feel work IS the foundry's substrate.** We build the game; we honor a few cheap seams;
resuming the foundry becomes a port, not a retrofit.

**Priority order (locked 2026-07-28):**
1. **Now — a real, nice 3D game feel & experience** (Phase 1, then Phase 2).
2. **Later — make it super-computer solvable** (Phase 3; detailed in `../crux-foundry/RESOLUTE_BACKEND_CONTRACT.md`).

Item tags: **[FEEL]** game experience · **[FIX]** a real correctness bug today · **[SUBSTRATE]** also required by the future foundry.

---

## Future-proofing principles (cheap seams honored throughout Phase 1–2)

These are good game architecture on their own; they also happen to be everything Phase 3 needs.

1. **Decision ⊥ actuation.** AI/combat *decisions* (target, commit, goal-point, ability choice) stay separable
   from *physics actuation* (Godot moves the body). Later the trained policy replaces the decision half without
   touching physics. `Game1.Core` already models this; keep it clean as we wire 3D movement.
2. **A queryable state surface.** Positions, facing, cooldowns, HP, nearby-obstacle info, target data are readable
   through clean accessors. Good AI + debugging need this now; the obs-encoder needs it later.
3. **Deterministic where it counts.** Fixed physics tick + seeded content/scenario RNG. Makes the game
   reproducible/debuggable now; is the determinism floor the foundry needs later.
4. **`Game1.Core` stays the combat authority.** Godot owns movement/collision/verticality; the certified kernel
   owns damage/hitbox/status/crit/defense, called in-process. Combat stays correct in the game *and* reusable by the trainer.
5. **2D is a subset of 3D.** Any state/schema we add leaves room for height/verticality terms (0 in the flat case),
   so the future obs schema extends rather than gets rewritten.

---

## Phase 1 — The 3D world & feel  *(PRIORITY — start here)*

**Goal:** it feels like a *real 3D game*, not a 2D game viewed through a 3D camera. Explorable, solid, good to move in.

- **1.1 Real 3D terrain** **[FEEL][SUBSTRATE]** — the height field becomes actual walkable geometry: heightmap →
  terrain **mesh + collider**, real hills/slopes, water and cliffs as true 3D features. *This is the single biggest
  "now it's 3D" win.*
- **1.2 Working collision** **[FEEL][FIX][SUBSTRATE]** — player *and* enemies collide with terrain + obstacles
  (rocks/trees/water/buildings). Today enemies **phase through everything** (`CombatWorld.cs:890` wires no
  collision) — a real, visible bug. Fix it as part of going 3D.
- **1.3 Navmesh bake** **[FEEL][SUBSTRATE]** — a `NavigationRegion3D` over terrain+obstacles so enemies **navigate
  around** things instead of walking into them. Immediate game-feel win; it is *also* the exact pathfinding
  substrate Phase 3's trained pather rides on (navmesh does locomotion; the policy will do tactics).
- **1.4 Movement feel** **[FEEL]** — polish player `CharacterBody3D` (jump/gravity/momentum/responsiveness);
  drive enemy movement from the `Game1.Core` AI decision → navmesh path → Godot actuation (principle #1).
- **1.5 Combat-feel consolidation** **[FEEL]** — the moment-to-moment: ground **telegraph arcs** from enemy windup,
  hit flash / screen shake / damage numbers, death effects, the existing enemy lunge. Make hits *read*.

**Phase-1 done =** a genuinely 3D, solid, good-feeling world you can explore and fight in.

---

## Phase 2 — Combat & enemy depth  *(game correctness + depth; also foundry substrate)*

**Goal:** enemies that navigate, attack, and use abilities; player combat that feels complete. Every item here is
a game-quality need *and* a foundry substrate need — near-zero wasted work.

- **2.1 Wire enemy collision + safe-zone** **[FIX][SUBSTRATE]** — the ported, unit-tested collision/safe-zone that's
  currently **dead at runtime**; make live == kernel (also stops enemies chasing into the spawn flat).
- **2.2 Real spawn director** **[FIX][SUBSTRATE]** — replace the ad-hoc, divergent `CombatWorld.cs` spawn with the
  authoritative weighted pools + per-danger tier caps + density weights (port `combat_manager.py:302-546`).
- **2.3 Enemy ability execution** **[FEEL][SUBSTRATE]** — enemies today do **basic melee only**; wire leap/charge/
  pounce/AoE (port `use_special_ability`). This is where fights get interesting — and where pack tactics live later.
- **2.4 Player dodge + i-frames** **[FEEL][SUBSTRATE]** — author the dodge/roll verb + invulnerability window
  (net-new 3D; freeze it). Core defensive game feel; a required agent action later.
- **2.5 Player facing + targeting feel** **[FEEL][SUBSTRATE]** — a real player facing field + click/aim-to-target;
  fixes the "player facing is a constant" gap that also blocks the future adversarial obs.
- **2.6 Verticality combat rules** **[FEEL][SUBSTRATE]** — decide + freeze how height reads in combat (reach across
  ledges, jump/gap traversal, aggro up/down elevation) now that terrain is truly 3D.

**Phase-2 done =** a combat game with navigating, ability-using enemies and complete player options.

---

## Phase 3 — Super-computer solvable  *(FUTURE — bolts on via the seams; no rewrite)*

Built on the clean Phase 1–2 game. Full detail: `../crux-foundry/RESOLUTE_BACKEND_CONTRACT.md` + `AGENT_DESIGN.md`.

- **3.1 De-risk** — determinism self-check (seeds 1,2,1) + throughput micro-benchmark on a headless Godot arena.
- **3.2 Adapters** — obs encoder (reads the Principle-#2 state surface) + actuator (Principle #1 intent → physics).
- **3.3 Fitness + battery** — hit-efficiency, path efficiency, tactical terms; common-random-number scenario battery.
- **3.4 Evolutionary trainer** — headless Godot, CPU, interpretable weight-vector policy; curriculum
  flat-reach → static obstacles → **verticality/gaps** → dynamic target → pack → adversarial.
- **3.5 The endgame** — hostile-pather vs player-pather co-evolution (navmesh = shared infra, tactics = the learned,
  competing layer). The pathing + combat intelligence you're ultimately after.

**Because Phase 1–2 honored the five principles, Phase 3 adds two thin adapters + a trainer — it does not rewrite the game.**

---

*This roadmap supersedes the scattered in-conversation planning. The game comes first; the compute layer is a
clean bolt-on. Start at Phase 1.1.*
