"""L1 — the enemy control surface.

`PolicyEnemy` subclasses the game's `Enemy` and overrides `update_ai` (exactly the
extension point `TrainingDummy` already uses). It replaces the hand-coded FSM
decision core with:  build observation -> policy(obs) -> actuate.

Crucially it changes NOTHING about how attacks land: `combat_manager.update()`
already runs the windup->active->recovery lifecycle and applies damage whenever an
enemy is in `AIState.ATTACK` with its cooldown ready (see combat_manager.py:598-608).
So the policy's "commit the swing" lever is simply *which state we leave the enemy
in* each frame — ATTACK to commit, CHASE to keep repositioning. Movement and
collision go through the existing `_move_towards`, so water / resources / barriers
are avoided reactively for free.

The metadata the policy reads (tier, category, tags, hp, reach, speed) all comes
off `EnemyDefinition` — no content JSON is touched. This is the seam that later
stages (obs vector -> scripted-smart policy -> evolved policy) fill in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from Combat.enemy import Enemy, EnemyDefinition, AIState


# ── the contract structs (v1; widened in L2) ────────────────────────────────

@dataclass
class Observation:
    """What one pack member perceives this frame. All cheap floats, all derivable
    from state that already exists. Widened in L2 (target facing/windup, obstacle
    /LOS flags); L1 carries what the hand-written pincer policy needs."""
    # self / build metadata
    hp_frac: float
    reach: float
    cooldown_ready: bool
    speed: float
    tier: int
    category: str
    pos: Tuple[float, float]
    # target (the player, relative)
    target_pos: Tuple[float, float]
    dist: float
    bearing: float                      # radians, angle from me to target
    # pack (the piece the stock FSM lacks — enemy.py:1245 TODO)
    ally_count: int
    ally_bearings: List[float] = field(default_factory=list)   # each ally's angle around the target
    allies_engaging: int = 0            # packmates already within engage range of target
    # assigned coordination slot (stable per member) — the pincer seed
    flank_angle: float = 0.0            # radians; the side of the target this member takes


@dataclass
class Action:
    """What the policy asks for this frame, mapped 1:1 onto existing actuators."""
    move_target: Tuple[float, float]    # -> _move_towards
    face_angle: float                   # degrees -> facing_angle
    commit: bool                        # True -> leave in ATTACK (combat loop fires the swing)


Policy = Callable[[Observation], Action]


# ── the L1 hand-written policy: coherent pack, with pincer/spacing seeds ─────

def heuristic_pack_policy(obs: Observation) -> Action:
    """A deliberately-simple but *coherent* pack policy. It is generation-0 for the
    evolutionary trainer, and it already exhibits three real behaviours so the
    control surface is visibly working (not just "walk at the player"):

      1. SPACING — approach to just inside reach (`optimal`), not on top of the
         target; don't crowd. Prevents the whiff-at-max-range failure the design
         doc calls out (AGENT_DESIGN.md, the pincer example).
      2. FLANK / PINCER — each member approaches from its assigned angle around the
         target (`flank_angle`), so the pack surrounds instead of stacking.
      3. COMMIT TIMING — only commit the swing when actually inside reach and off
         cooldown; otherwise keep repositioning.

    Every constant here becomes an evolvable weight in L4. The point of L1 is the
    *mechanism*, not optimality."""
    px, py = obs.target_pos
    # Approach a point on a ring around the target, on this member's flank.
    # Cap inside the combat loop's hardcoded 1.5 melee-trigger envelope
    # (combat_manager.py:606) — spacing at reach*0.8 alone can park long-reach
    # enemies *outside* where a swing actually fires, so they never connect.
    optimal = max(0.6, min(obs.reach, 1.5) * 0.85)   # just inside the swing envelope
    ax = px + optimal * math.cos(obs.flank_angle)
    ay = py + optimal * math.sin(obs.flank_angle)

    face_deg = math.degrees(obs.bearing)

    # Commit only when in reach and ready. `dist` is centre-to-centre; the combat
    # loop fires a melee swing at <= 1.5, so gate on the same envelope.
    in_reach = obs.dist <= max(1.5, obs.reach)
    commit = in_reach and obs.cooldown_ready

    return Action(move_target=(ax, ay), face_angle=face_deg, commit=commit)


# ── the control surface ─────────────────────────────────────────────────────

class PolicyEnemy(Enemy):
    """An Enemy whose per-frame decision comes from a Policy instead of the FSM.

    Attach `pack` (the list of packmates, including self) so the observation can
    include allies. `flank_angle` is this member's assigned side of the target."""

    def __init__(self, definition: EnemyDefinition, position, chunk_coords,
                 policy: Policy = heuristic_pack_policy,
                 flank_angle: float = 0.0):
        super().__init__(definition, position, chunk_coords)
        self.policy: Policy = policy
        self.flank_angle: float = flank_angle
        self.pack: List["PolicyEnemy"] = [self]
        # reach: prefer the enemy's own primary attack range, else melee default.
        self._reach: float = (self.definition.attacks[0].range
                              if self.definition.attacks else 1.5)
        # lightweight per-run telemetry (read by the demo / fitness harness)
        self.commits: int = 0
        self.min_dist_seen: float = float('inf')

    # ── observation ─────────────────────────────────────────────────────────

    def _build_obs(self, player_position: Tuple[float, float]) -> Observation:
        sx, sy = self.position[0], self.position[1]
        px, py = player_position[0], player_position[1]
        dx, dy = px - sx, py - sy
        dist = math.hypot(dx, dy)
        bearing = math.atan2(dy, dx)

        ally_bearings: List[float] = []
        allies_engaging = 0
        for mate in self.pack:
            if mate is self or not mate.is_alive:
                continue
            mdx = mate.position[0] - px
            mdy = mate.position[1] - py
            ally_bearings.append(math.atan2(mdy, mdx))
            if math.hypot(mdx, mdy) <= max(1.5, self._reach):
                allies_engaging += 1

        return Observation(
            hp_frac=(self.current_health / self.max_health) if self.max_health else 0.0,
            reach=self._reach,
            cooldown_ready=(self.attack_cooldown <= 0 and self.attack_phase == 'idle'),
            speed=self.definition.speed,
            tier=self.definition.tier,
            category=self.definition.category,
            pos=(sx, sy),
            target_pos=(px, py),
            dist=dist,
            bearing=bearing,
            ally_count=sum(1 for m in self.pack if m is not self and m.is_alive),
            ally_bearings=ally_bearings,
            allies_engaging=allies_engaging,
            flank_angle=self.flank_angle,
        )

    # ── the overridden decision core ─────────────────────────────────────────

    def update_ai(self, dt: float, player_position: Tuple[float, float],
                  aggro_multiplier: float = 1.0, speed_multiplier: float = 1.0,
                  world_system=None, safe_zone_center: Tuple[float, float] = None,
                  safe_zone_radius: float = 0.0):
        # --- housekeeping mirrored from Enemy.update_ai (movement/collision needs
        # these side-channels; ticking timers keeps attacks/statuses correct) ---
        self._world_system = world_system
        self._safe_zone_center = safe_zone_center
        self._safe_zone_radius = safe_zone_radius

        if not self.is_alive:
            if self.ai_state == AIState.DEAD:
                self.ai_state = AIState.CORPSE
            self.time_since_death += dt
            return

        self._aggro_multiplier = aggro_multiplier
        self._speed_multiplier = speed_multiplier

        self.update_knockback(dt)
        if hasattr(self, 'status_manager'):
            self.status_manager.update(dt)
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.attack_anim_timer > 0:
            self.attack_anim_timer -= dt
        for aid in self.ability_cooldowns:
            if self.ability_cooldowns[aid] > 0:
                self.ability_cooldowns[aid] -= dt
        if self.attack_state_machine is not None:
            self.attack_state_machine.update(dt * 1000)

        # --- decide ---
        obs = self._build_obs(player_position)
        action = self.policy(obs)

        # --- actuate ---
        self.facing_angle = action.face_angle
        # If mid-swing (windup/active/recovery) the enemy is committed: hold position,
        # let the combat loop run the phase. Otherwise move toward the policy's point.
        if self.attack_phase == 'idle':
            self._move_towards(action.move_target, dt)

        # The commit lever: ATTACK state lets combat_manager.update() fire the swing
        # (it checks can_attack() -> ai_state == ATTACK, then start_phased_attack).
        if action.commit:
            self.ai_state = AIState.ATTACK
            self.commits += 1
        else:
            self.ai_state = AIState.CHASE

        self.min_dist_seen = min(self.min_dist_seen, obs.dist)


# ── arena setup helpers ──────────────────────────────────────────────────────

def disable_safe_zone(engine) -> None:
    """Neutralise the origin spawn safe-zone (combat_manager.config.safe_zone_radius,
    default 15 tiles at (0,0)). `_move_towards` refuses any step that would enter it,
    which otherwise freezes a pack trying to reach a player standing near spawn. The
    safe zone is a gameplay spawn-protection feature, not part of combat — a training
    arena must turn it off (or be sited far from origin). Reusable by the L3 harness."""
    cfg = getattr(engine.combat_manager, 'config', None)
    if cfg is not None:
        cfg.safe_zone_radius = 0.0


# ── the spawn "verb" (lives in the sandbox, not in game infra) ───────────────

def spawn_policy_pack(engine, n: int, tier: int,
                      policy: Policy = heuristic_pack_policy,
                      center: Tuple[float, float] = (0.0, 0.0),
                      radius: float = 8.0,
                      compose_seed: Optional[int] = None) -> List[PolicyEnemy]:
    """Clear the arena and spawn a policy-driven pack of `n` tier-`tier` enemies in
    a ring of `radius` around `center`, each assigned a distinct flank angle. They
    share a `pack` reference so each can observe its allies. Registered for action
    combat like the balance gauntlet (runner.spawn_gauntlet) so the full combat
    lifecycle applies.

    `compose_seed`, if given, makes the *composition* (which enemy types) identical
    across runs while leaving the run's RNG stream untouched — same trick the
    balance foundry uses for a fixed challenge."""
    import random
    cm = engine.combat_manager
    cm.enemies.clear()
    cm.corpses.clear()

    cx, cy = center
    chunk = (int(cx // 16), int(cy // 16))

    _state = None
    if compose_seed is not None:
        _state = random.getstate()
        random.seed(compose_seed)
    try:
        pack: List[PolicyEnemy] = []
        for i in range(n):
            edef = cm.enemy_db.get_random_enemy(tier)
            if edef is None:
                continue
            ang = 2.0 * math.pi * i / max(1, n)
            # spawn on a ring so the pack starts spread out and must close in
            spawn = (cx + radius * math.cos(ang), cy + radius * math.sin(ang))
            e = PolicyEnemy(edef, spawn, chunk, policy=policy, flank_angle=ang)
            cm.enemies.setdefault(chunk, []).append(e)
            cm._register_enemy_action_combat(e)
            pack.append(e)
    finally:
        if _state is not None:
            random.setstate(_state)

    # wire the shared pack reference so allies are observable
    for e in pack:
        e.pack = pack
    return pack
