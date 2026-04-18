"""Phase 6 - Advanced Affinity Features.

Implements affinity tiers, ripples, decay, and milestones for deep
faction integration. All four systems work together via FactionDatabase.

Components:
- AffinityTierSystem: Check if player meets thresholds for special interactions
- AffinityRippleSystem: Propagate affinity changes to related tags
- AffinityDecayScheduler: Background time-based affinity degradation
- AffinityMilestoneSystem: Publish events when crossing reputation thresholds

Usage:
    # Initialize all features
    tier_sys = AffinityTierSystem()
    ripple_sys = AffinityRippleSystem()
    decay_sys = AffinityDecayScheduler()
    milestone_sys = AffinityMilestoneSystem()

    # Apply affinity change → triggers ripples & milestones
    db.add_player_affinity_delta(player_id, tag, delta)
    ripple_sys.apply_ripples(player_id, tag, delta)
    milestone_sys.check_milestone(player_id, tag, new_affinity)

    # Background decay
    decay_sys.start()  # Runs in background thread
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Tuple, ClassVar
from dataclasses import dataclass
from world_system.living_world.factions.database import FactionDatabase
from events.event_bus import get_event_bus


# ── Configuration ─────────────────────────────────────────────────────

@dataclass
class AffinityTierDefinition:
    """Definition of an affinity tier and its effects."""
    threshold: float                      # Minimum affinity to reach this tier
    name: str                             # e.g., "beloved", "hated", "reviled"
    effects: Dict[str, str] = None        # Effect tags applied at this tier
    special_interactions: List[str] = None  # Quest types or NPC behaviors enabled

    def __post_init__(self):
        if self.effects is None:
            self.effects = {}
        if self.special_interactions is None:
            self.special_interactions = []


# Default affinity tiers (these can be customized per faction later)
DEFAULT_AFFINITY_TIERS = [
    AffinityTierDefinition(75, "beloved", special_interactions=["exclusive_quest", "gift_access"]),
    AffinityTierDefinition(50, "favored", special_interactions=["discount_trading"]),
    AffinityTierDefinition(25, "respected", special_interactions=[]),
    AffinityTierDefinition(0, "neutral", special_interactions=[]),
    AffinityTierDefinition(-25, "disliked", special_interactions=["increased_prices"]),
    AffinityTierDefinition(-50, "hated", special_interactions=["quest_refusal"]),
    AffinityTierDefinition(-80, "reviled", special_interactions=["active_opposition"]),
]

# Affinity ripple relationships (tag A → [(tag B, ripple_strength), ...])
# These define how reputation changes propagate across related factions
RIPPLE_RELATIONSHIPS: Dict[str, List[Tuple[str, float]]] = {
    "guild:smiths": [
        ("guild:crafters", 0.3),
        ("nation:stormguard", 0.1),
    ],
    "guild:merchants": [
        ("guild:crafters", 0.2),
        ("nation:merchant_alliance", 0.4),
    ],
    "nation:stormguard": [
        ("guild:smiths", 0.2),
        ("region:northlands", 0.3),
    ],
    # Add more as needed
}


# ── Affinity Tier System ───────────────────────────────────────────────

class AffinityTierSystem:
    """Check affinity tiers and provide tier-based effects."""

    def __init__(self):
        self.tiers = {tier.name: tier for tier in DEFAULT_AFFINITY_TIERS}
        self.tier_order = sorted(DEFAULT_AFFINITY_TIERS, key=lambda t: t.threshold, reverse=True)

    def get_tier(self, affinity: float) -> AffinityTierDefinition:
        """Get the tier for an affinity value."""
        for tier in self.tier_order:
            if affinity >= tier.threshold:
                return tier
        return self.tier_order[-1]

    def get_tier_name(self, affinity: float) -> str:
        """Get tier name for an affinity value."""
        return self.get_tier(affinity).name

    def can_access_interaction(self, affinity: float,
                              interaction: str) -> bool:
        """Check if player can access a special interaction at this affinity."""
        tier = self.get_tier(affinity)
        return interaction in tier.special_interactions

    def get_all_accessible_interactions(self, affinity: float) -> List[str]:
        """Get all interactions accessible at this affinity level."""
        interactions = []
        for tier in self.tier_order:
            if affinity >= tier.threshold:
                interactions.extend(tier.special_interactions)
        return list(set(interactions))


# ── Affinity Ripple System ────────────────────────────────────────────

class AffinityRippleSystem:
    """Propagate affinity changes to related tags."""

    def __init__(self):
        self._db: Optional[FactionDatabase] = None
        self.ripple_map = RIPPLE_RELATIONSHIPS

    def initialize(self, db: Optional[FactionDatabase] = None):
        self._db = db or FactionDatabase.get_instance()

    def apply_ripples(self, player_id: str, source_tag: str,
                     source_delta: float) -> None:
        """Apply ripple affinity changes from a source tag.

        When player gains affinity with a tag, related tags receive
        proportional affinity gains.

        Args:
            player_id: Player ID
            source_tag: Tag that changed
            source_delta: Amount the source changed
        """
        if not self._db:
            return

        related = self.ripple_map.get(source_tag, [])
        for target_tag, ripple_strength in related:
            ripple_delta = source_delta * ripple_strength
            if abs(ripple_delta) < 0.1:  # Ignore tiny ripples
                continue

            new_affinity = self._db.add_player_affinity_delta(
                player_id, target_tag, ripple_delta
            )

            print(
                f"[Ripple] {source_tag} +{source_delta:.1f} → "
                f"{target_tag} +{ripple_delta:.1f} (now {new_affinity:.1f})"
            )

    def add_ripple_relationship(self, source: str, target: str,
                               strength: float) -> None:
        """Add a new ripple relationship at runtime."""
        if source not in self.ripple_map:
            self.ripple_map[source] = []
        self.ripple_map[source].append((target, strength))


# ── Affinity Decay Scheduler ───────────────────────────────────────────

class AffinityDecayScheduler:
    """Background thread that applies time-based affinity decay."""

    def __init__(self):
        self._db: Optional[FactionDatabase] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._decay_rate = -0.1  # Per day without interaction
        self._check_interval = 60.0  # Check every 60 real seconds
        self._last_game_time = 0.0

    def initialize(self, db: Optional[FactionDatabase] = None):
        self._db = db or FactionDatabase.get_instance()

    def start(self) -> None:
        """Start the background decay scheduler."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._decay_loop, daemon=True)
        self._thread.start()
        print("[AffinityDecayScheduler] Started")

    def stop(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        print("[AffinityDecayScheduler] Stopped")

    def _decay_loop(self) -> None:
        """Background loop that applies decay."""
        while self._running:
            try:
                # In a real implementation, get actual game time from game_engine
                # For now, use real time as proxy
                current_time = time.time()

                if not self._db or not self._db.connection or not self._db._initialized:
                    time.sleep(self._check_interval)
                    continue

                # Get all players and apply decay
                # This would require a query on all players (currently using "player" as placeholder)
                # For Phase 6, we apply decay uniformly
                decay_per_check = self._decay_rate / 86400.0 * self._check_interval
                self._apply_decay_to_all_affinities("player", decay_per_check)

                self._last_game_time = current_time
                time.sleep(self._check_interval)

            except Exception as e:
                print(f"[AffinityDecayScheduler] Error: {e}")
                time.sleep(self._check_interval)

    def _apply_decay_to_all_affinities(self, player_id: str, decay: float) -> None:
        """Apply decay to all affinities for a player (soft decay)."""
        if not self._db:
            return

        try:
            # Get all affinity entries
            affinities = self._db.get_all_player_affinities(player_id)
            for tag, current_value in affinities.items():
                # Soft decay: decay toward 0, never cross
                if current_value > 0:
                    decayed = max(0, current_value + decay)
                elif current_value < 0:
                    decayed = min(0, current_value - decay)
                else:
                    continue

                if abs(decayed - current_value) > 0.01:  # Only update if meaningful
                    self._db.add_player_affinity_delta(
                        player_id, tag, decayed - current_value
                    )

        except Exception as e:
            print(f"[AffinityDecayScheduler] Decay error: {e}")


# ── Affinity Milestone System ──────────────────────────────────────────

class AffinityMilestoneSystem:
    """Track and publish events when affinity crosses thresholds."""

    # Define milestones: affinity threshold → event description
    MILESTONES = {
        75: "beloved",
        50: "favored",
        25: "respected",
        0: "neutral",
        -25: "disliked",
        -50: "hated",
        -80: "reviled",
    }

    def __init__(self):
        self._db: Optional[FactionDatabase] = None
        self._event_bus = None
        self._published_milestones: Dict[Tuple[str, str], float] = {}  # (player, tag) → last_value

    def initialize(self, db: Optional[FactionDatabase] = None,
                  event_bus=None):
        self._db = db or FactionDatabase.get_instance()
        self._event_bus = event_bus or get_event_bus()

    def check_milestone(self, player_id: str, tag: str,
                       new_affinity: float) -> None:
        """Check if affinity change crossed a milestone.

        Publishes AFFINITY_MILESTONE event if a threshold is crossed.

        Args:
            player_id: Player ID
            tag: Faction tag
            new_affinity: Current affinity value
        """
        if not self._event_bus:
            return

        key = (player_id, tag)
        old_affinity = self._published_milestones.get(key, 0.0)

        # Check each milestone threshold
        for threshold in sorted(self.MILESTONES.keys(), reverse=True):
            milestone_name = self.MILESTONES[threshold]

            # Did we cross this threshold?
            crossed = (old_affinity < threshold <= new_affinity or
                      old_affinity > threshold >= new_affinity)

            if not crossed:
                continue

            direction = "reached" if new_affinity >= threshold else "lost"
            narrative = (
                f"You have {direction} {milestone_name} status with {tag}. "
                f"(Affinity: {new_affinity:+.0f})"
            )

            try:
                self._event_bus.publish(
                    "AFFINITY_MILESTONE",
                    {
                        "player_id": player_id,
                        "tag": tag,
                        "milestone": milestone_name,
                        "affinity": new_affinity,
                        "direction": direction,
                        "narrative": narrative,
                    },
                    source="AffinityMilestoneSystem",
                )
                print(f"[Milestone] {narrative}")

            except Exception as e:
                print(f"[AffinityMilestoneSystem] Error publishing: {e}")

        # Update last known value
        self._published_milestones[key] = new_affinity
