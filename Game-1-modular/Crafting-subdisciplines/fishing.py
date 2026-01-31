"""
Fishing Minigame Subdiscipline

OSU-style ripple clicking game for fishing.
Player must click on expanding rings when they hit target zones.

Mechanics:
- Ripples spawn at random positions on a pond surface
- Each ripple has a target ring and an expanding outer ring
- Click when the outer ring overlaps the target ring
- Score based on timing accuracy

Stat Effects:
- LCK: Reduces number of ripples needed (shorter game)
- STR: Increases click area (more forgiving timing)
- Rod Quality: Increases time per ripple (slower tick speed = more time)

Win: Get materials and XP like killing a mob
Fail: Get nothing, rod takes double durability loss
"""

import pygame
import math
import random
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Ripple:
    """A single ripple target for the fishing minigame."""
    x: float  # Center X position
    y: float  # Center Y position
    target_radius: float  # The radius the player needs to hit
    current_radius: float = 0.0  # Current expanding ring radius
    max_radius: float = 0.0  # Maximum radius before miss
    expand_speed: float = 60.0  # Pixels per second
    hit: bool = False  # Was this ripple hit?
    score: int = 0  # Score for this ripple (0 = miss, 100 = perfect)
    active: bool = True  # Is this ripple still active?
    spawn_time: float = 0.0  # When this ripple was spawned


class FishingMinigame:
    """
    OSU-style fishing minigame.

    The player must click on ripples as expanding rings hit target zones.
    Stats affect gameplay:
    - LCK (Luck): Reduces required ripple count
    - STR (Strength): Increases hit tolerance (larger click area)
    - Rod tier: Slows down ripple expansion (more time to react)
    """

    # Base constants
    POND_WIDTH = 500
    POND_HEIGHT = 400
    POND_MARGIN = 50  # Edge margin for spawning

    # Base difficulty (modified by tier and stats)
    BASE_RIPPLE_COUNT = 8  # Base number of ripples to complete
    BASE_TARGET_RADIUS = 40  # Base target ring size
    BASE_EXPAND_SPEED = 80  # Base expansion speed (pixels/sec)
    BASE_HIT_TOLERANCE = 15  # Base tolerance for hit detection
    BASE_SPAWN_DELAY = 1.5  # Seconds between ripples

    # Scoring
    PERFECT_TOLERANCE = 5  # Within 5px = perfect
    GOOD_TOLERANCE = 10  # Within 10px = good
    FAIR_TOLERANCE = 15  # Within 15px = fair

    def __init__(self, fishing_spot_tier: int, equipped_rod: Optional[Any] = None,
                 player_stats: Optional[Dict] = None):
        """
        Initialize fishing minigame.

        Args:
            fishing_spot_tier: Tier of the fishing spot (1-4)
            equipped_rod: The equipped fishing rod (for tier/quality)
            player_stats: Player's stats dict with 'luck', 'strength', etc.
        """
        self.fishing_spot_tier = fishing_spot_tier
        self.equipped_rod = equipped_rod
        self.player_stats = player_stats or {}

        # Extract stats
        self.luck = self.player_stats.get('luck', 0)
        self.strength = self.player_stats.get('strength', 0)

        # Get rod tier (affects tick speed)
        self.rod_tier = 1
        if equipped_rod:
            self.rod_tier = getattr(equipped_rod, 'tier', 1)
            # Also check for gathering multiplier from rod
            if hasattr(equipped_rod, 'statMultipliers'):
                gathering_mult = equipped_rod.statMultipliers.get('gathering', 1.0)
                self.rod_tier = max(self.rod_tier, int(gathering_mult))

        # Calculate adjusted parameters based on stats
        self._calculate_difficulty()

        # Game state
        self.active = False
        self.ripples: List[Ripple] = []
        self.current_ripple_index = 0
        self.time_since_last_spawn = 0.0
        self.total_time = 0.0
        self.completed = False
        self.success = False
        self.result = None

        # Tracking
        self.hits = 0
        self.misses = 0
        self.perfect_hits = 0
        self.total_score = 0
        self.scores: List[int] = []

        # Visual feedback
        self.last_hit_position: Optional[Tuple[float, float]] = None
        self.last_hit_score: Optional[int] = None
        self.last_hit_time: float = 0.0

    def _calculate_difficulty(self):
        """Calculate game parameters based on tier and stats."""
        # Base difficulty scales with fishing spot tier
        tier_multiplier = 1.0 + (self.fishing_spot_tier - 1) * 0.25

        # LCK reduces ripple count (makes game shorter)
        # Each luck point reduces by 0.1 ripples, min 4 ripples
        luck_reduction = self.luck * 0.1
        self.required_ripples = max(4, int(self.BASE_RIPPLE_COUNT - luck_reduction))

        # Higher tier fishing spots need more ripples
        self.required_ripples = int(self.required_ripples * tier_multiplier)
        self.required_ripples = max(4, min(15, self.required_ripples))  # Clamp 4-15

        # STR increases hit tolerance (larger click area)
        # Each strength point adds 0.5px tolerance
        str_bonus = self.strength * 0.5
        self.hit_tolerance = self.BASE_HIT_TOLERANCE + str_bonus
        self.hit_tolerance = min(30, self.hit_tolerance)  # Cap at 30px

        # Rod tier affects expansion speed (higher tier = slower = more time)
        # T1: 1.0x, T2: 0.85x, T3: 0.70x, T4: 0.55x speed
        rod_speed_mult = 1.0 - (self.rod_tier - 1) * 0.15
        rod_speed_mult = max(0.55, rod_speed_mult)

        # Fishing spot tier increases speed (harder)
        spot_speed_mult = 1.0 + (self.fishing_spot_tier - 1) * 0.2

        self.expand_speed = self.BASE_EXPAND_SPEED * rod_speed_mult * spot_speed_mult

        # Spawn delay also affected by rod (more time between ripples)
        self.spawn_delay = self.BASE_SPAWN_DELAY * (1.0 / rod_speed_mult)
        self.spawn_delay = max(0.8, min(2.5, self.spawn_delay))

        # Target radius stays constant, but max radius increases with tier
        self.target_radius = self.BASE_TARGET_RADIUS
        self.max_radius = self.target_radius * 2.5  # Miss if expand past this

        # Log difficulty info
        print(f"🎣 Fishing difficulty calculated:")
        print(f"   Spot Tier: {self.fishing_spot_tier}, Rod Tier: {self.rod_tier}")
        print(f"   LCK: {self.luck} -> {self.required_ripples} ripples required")
        print(f"   STR: {self.strength} -> {self.hit_tolerance:.1f}px hit tolerance")
        print(f"   Speed: {self.expand_speed:.1f}px/s, Delay: {self.spawn_delay:.1f}s")

    def start(self):
        """Start the fishing minigame."""
        self.active = True
        self.ripples = []
        self.current_ripple_index = 0
        self.time_since_last_spawn = self.spawn_delay  # Spawn first immediately
        self.total_time = 0.0
        self.completed = False
        self.success = False
        self.result = None

        self.hits = 0
        self.misses = 0
        self.perfect_hits = 0
        self.total_score = 0
        self.scores = []

        self.last_hit_position = None
        self.last_hit_score = None
        self.last_hit_time = 0.0

        print(f"🎣 Fishing started! Click {self.required_ripples} ripples to catch the fish!")

    def update(self, dt: float):
        """
        Update minigame state.

        Args:
            dt: Delta time in seconds
        """
        if not self.active:
            return

        self.total_time += dt
        self.time_since_last_spawn += dt

        # Spawn new ripples
        if (len([r for r in self.ripples if r.active]) < 2 and  # Max 2 active
            self.current_ripple_index < self.required_ripples and
            self.time_since_last_spawn >= self.spawn_delay):
            self._spawn_ripple()
            self.time_since_last_spawn = 0.0

        # Update active ripples
        for ripple in self.ripples:
            if ripple.active and not ripple.hit:
                ripple.current_radius += self.expand_speed * dt

                # Check for miss (expanded past max)
                if ripple.current_radius >= ripple.max_radius:
                    ripple.active = False
                    ripple.score = 0
                    self.misses += 1
                    self.scores.append(0)
                    print(f"   ❌ Miss! Ring expanded too far")

        # Check for game end
        completed_count = len([r for r in self.ripples if not r.active or r.hit])
        if completed_count >= self.required_ripples:
            self._end_game()

    def _spawn_ripple(self):
        """Spawn a new ripple at a random position."""
        # Random position within pond bounds
        x = random.uniform(self.POND_MARGIN, self.POND_WIDTH - self.POND_MARGIN)
        y = random.uniform(self.POND_MARGIN, self.POND_HEIGHT - self.POND_MARGIN)

        ripple = Ripple(
            x=x,
            y=y,
            target_radius=self.target_radius,
            current_radius=0.0,
            max_radius=self.max_radius,
            expand_speed=self.expand_speed,
            spawn_time=self.total_time
        )

        self.ripples.append(ripple)
        self.current_ripple_index += 1

    def handle_click(self, click_x: float, click_y: float) -> Optional[int]:
        """
        Handle a click at the given position.

        Args:
            click_x: Click X position relative to pond
            click_y: Click Y position relative to pond

        Returns:
            Score for the click (0-100) or None if no ripple hit
        """
        if not self.active:
            return None

        # Find the closest active ripple to the click
        best_ripple = None
        best_distance = float('inf')

        for ripple in self.ripples:
            if ripple.active and not ripple.hit:
                distance = math.sqrt((click_x - ripple.x)**2 + (click_y - ripple.y)**2)
                if distance < best_distance:
                    best_distance = distance
                    best_ripple = ripple

        if best_ripple is None:
            return None

        # Check if click is within the expanding ring's area
        ring_distance = abs(best_ripple.current_radius - self.target_radius)

        # Check if within hit tolerance (adjusted by STR)
        if ring_distance <= self.hit_tolerance:
            # Calculate score based on accuracy
            if ring_distance <= self.PERFECT_TOLERANCE:
                score = 100
                self.perfect_hits += 1
                print(f"   ✨ PERFECT! (+100)")
            elif ring_distance <= self.GOOD_TOLERANCE:
                score = 75
                print(f"   ⭐ Good! (+75)")
            elif ring_distance <= self.FAIR_TOLERANCE:
                score = 50
                print(f"   ✓ Fair (+50)")
            else:
                # Partial hit
                score = max(25, int(50 * (1 - ring_distance / self.hit_tolerance)))
                print(f"   ~ Late/Early (+{score})")

            best_ripple.hit = True
            best_ripple.score = score
            best_ripple.active = False
            self.hits += 1
            self.total_score += score
            self.scores.append(score)

            # Visual feedback
            self.last_hit_position = (best_ripple.x, best_ripple.y)
            self.last_hit_score = score
            self.last_hit_time = self.total_time

            return score
        else:
            # Miss - clicked but not at the right time
            best_ripple.active = False
            best_ripple.score = 0
            self.misses += 1
            self.scores.append(0)
            print(f"   ❌ Missed! Ring was {ring_distance:.1f}px off")

            return 0

    def _end_game(self):
        """End the minigame and calculate results."""
        self.active = False
        self.completed = True

        # Calculate success based on hit rate
        if self.hits == 0:
            hit_rate = 0.0
        else:
            hit_rate = self.hits / self.required_ripples

        # Average score (0-100)
        if self.scores:
            avg_score = sum(self.scores) / len(self.scores)
        else:
            avg_score = 0

        # Performance rating (0.0 to 1.0)
        performance = (avg_score / 100) * hit_rate

        # Success threshold: need at least 50% hit rate with 40+ avg score
        self.success = hit_rate >= 0.5 and avg_score >= 40

        # Determine quality tier based on performance
        if performance >= 0.9:
            quality_tier = "Legendary"
            bonus_mult = 1.5
        elif performance >= 0.75:
            quality_tier = "Masterwork"
            bonus_mult = 1.3
        elif performance >= 0.6:
            quality_tier = "Superior"
            bonus_mult = 1.15
        elif performance >= 0.4:
            quality_tier = "Fine"
            bonus_mult = 1.0
        else:
            quality_tier = "Normal"
            bonus_mult = 0.8

        # XP reward based on fishing spot tier (like mob kills)
        # T1: 100, T2: 400, T3: 1600, T4: 6400
        base_xp = 100 * (4 ** (self.fishing_spot_tier - 1))
        xp_reward = int(base_xp * bonus_mult) if self.success else 0

        self.result = {
            "success": self.success,
            "hits": self.hits,
            "misses": self.misses,
            "perfect_hits": self.perfect_hits,
            "required_ripples": self.required_ripples,
            "hit_rate": hit_rate,
            "avg_score": avg_score,
            "performance": performance,
            "quality_tier": quality_tier,
            "bonus_mult": bonus_mult,
            "xp_reward": xp_reward,
            "total_time": self.total_time,
            "fishing_spot_tier": self.fishing_spot_tier,
            "rod_tier": self.rod_tier,
            "message": self._get_result_message(hit_rate, avg_score),
        }

        if self.success:
            print(f"🎣 SUCCESS! {quality_tier} catch!")
            print(f"   Hits: {self.hits}/{self.required_ripples}, Avg Score: {avg_score:.1f}")
            print(f"   XP Reward: {xp_reward}")
        else:
            print(f"🎣 FAILED! The fish got away...")
            print(f"   Hits: {self.hits}/{self.required_ripples}, Avg Score: {avg_score:.1f}")

    def _get_result_message(self, hit_rate: float, avg_score: float) -> str:
        """Generate a result message based on performance."""
        if hit_rate < 0.3:
            return "The fish escaped! Keep practicing your timing."
        elif hit_rate < 0.5:
            return "Almost had it! Need better accuracy."
        elif avg_score < 40:
            return "Caught something, but it wiggled free. Timing needs work."
        elif avg_score < 60:
            return "A decent catch! Room for improvement."
        elif avg_score < 80:
            return "Nice catch! Your skills are improving."
        elif avg_score < 95:
            return "Excellent catch! Master angler in the making."
        else:
            return "PERFECT CATCH! A legendary performance!"

    def get_state(self) -> Dict[str, Any]:
        """Get current minigame state for rendering."""
        return {
            "active": self.active,
            "completed": self.completed,
            "success": self.success,
            "ripples": [
                {
                    "x": r.x,
                    "y": r.y,
                    "target_radius": r.target_radius,
                    "current_radius": r.current_radius,
                    "max_radius": r.max_radius,
                    "hit": r.hit,
                    "active": r.active,
                    "score": r.score,
                }
                for r in self.ripples
            ],
            "hits": self.hits,
            "misses": self.misses,
            "perfect_hits": self.perfect_hits,
            "required_ripples": self.required_ripples,
            "total_score": self.total_score,
            "total_time": self.total_time,
            "result": self.result,
            # Visual feedback
            "last_hit_position": self.last_hit_position,
            "last_hit_score": self.last_hit_score,
            "last_hit_time": self.last_hit_time,
            # Config
            "pond_width": self.POND_WIDTH,
            "pond_height": self.POND_HEIGHT,
            "hit_tolerance": self.hit_tolerance,
        }


class FishingManager:
    """
    Manages fishing interactions in the game.

    Handles starting fishing, running the minigame, and processing results.
    """

    def __init__(self):
        """Initialize the fishing manager."""
        self.active_minigame: Optional[FishingMinigame] = None
        self.current_fishing_spot = None

    def can_fish(self, resource, character) -> Tuple[bool, str]:
        """
        Check if the character can fish at the given resource.

        Args:
            resource: The fishing spot resource
            character: The player character

        Returns:
            Tuple of (can_fish, reason)
        """
        # Check if resource is a fishing spot
        from data.models import ResourceType
        if resource.resource_type != ResourceType.FISHING_SPOT and \
           'fishing_spot' not in resource.resource_type.value.lower():
            return False, "Not a fishing spot"

        # Check for equipped fishing rod
        equipped_rod = character.get_equipped_tool('fishing_rod')
        if not equipped_rod:
            return False, "No fishing rod equipped"

        # Check rod tier vs spot tier
        if equipped_rod.tier < resource.tier:
            return False, f"Need T{resource.tier} fishing rod"

        # Check rod durability
        if equipped_rod.durability_current <= 0:
            return False, "Fishing rod is broken"

        return True, "OK"

    def start_fishing(self, resource, character) -> Optional[FishingMinigame]:
        """
        Start fishing at the given resource.

        Args:
            resource: The fishing spot resource
            character: The player character

        Returns:
            FishingMinigame instance or None if can't fish
        """
        can_fish, reason = self.can_fish(resource, character)
        if not can_fish:
            print(f"🎣 Cannot fish: {reason}")
            return None

        # Get rod and stats
        equipped_rod = character.get_equipped_tool('fishing_rod')
        player_stats = {
            'luck': character.stats.luck,
            'strength': character.stats.strength,
            'agility': character.stats.agility,
        }

        # Create minigame
        self.active_minigame = FishingMinigame(
            fishing_spot_tier=resource.tier,
            equipped_rod=equipped_rod,
            player_stats=player_stats
        )
        self.current_fishing_spot = resource
        self.active_minigame.start()

        return self.active_minigame

    def process_result(self, character) -> Dict[str, Any]:
        """
        Process the minigame result and apply rewards/penalties.

        Args:
            character: The player character

        Returns:
            Result dict with loot, xp, durability loss, etc.
        """
        if not self.active_minigame or not self.active_minigame.result:
            return {"success": False, "message": "No active fishing minigame"}

        result = self.active_minigame.result
        equipped_rod = character.get_equipped_tool('fishing_rod')

        if result['success']:
            # SUCCESS: Get loot and XP
            # Loot is handled by the resource's drop table
            loot = self.current_fishing_spot.get_loot() if self.current_fishing_spot else []

            # Apply luck bonus to loot quantities
            processed_loot = []
            for item_id, qty in loot:
                luck_mult = 1.0 + (character.stats.luck * 0.02)
                bonus_qty = int(qty * luck_mult * result['bonus_mult'])
                processed_loot.append((item_id, max(1, bonus_qty)))

            # Normal durability loss
            durability_loss = 1.0

            # Mark resource as depleted (it will respawn)
            if self.current_fishing_spot:
                self.current_fishing_spot.depleted = True
                self.current_fishing_spot.current_hp = 0

            result_data = {
                "success": True,
                "loot": processed_loot,
                "xp": result['xp_reward'],
                "durability_loss": durability_loss,
                "quality_tier": result['quality_tier'],
                "message": result['message'],
            }

        else:
            # FAIL: No loot, double durability loss
            durability_loss = 2.0

            result_data = {
                "success": False,
                "loot": [],
                "xp": 0,
                "durability_loss": durability_loss,
                "quality_tier": "None",
                "message": result['message'],
            }

        # Apply durability loss to rod
        if equipped_rod and not hasattr(character, '_debug_infinite_durability'):
            from core.config import Config
            if not Config.DEBUG_INFINITE_DURABILITY:
                # DEF stat reduces durability loss
                loss_mult = character.stats.get_durability_loss_multiplier()
                final_loss = durability_loss * loss_mult
                equipped_rod.durability_current = max(0, equipped_rod.durability_current - final_loss)

                if result_data['success']:
                    print(f"   🎣 Rod durability: {equipped_rod.durability_current:.0f}/{equipped_rod.durability_max}")
                else:
                    print(f"   💔 Rod took double damage! Durability: {equipped_rod.durability_current:.0f}/{equipped_rod.durability_max}")

        # Clear active minigame
        self.active_minigame = None
        self.current_fishing_spot = None

        return result_data


# Singleton instance
_fishing_manager = None

def get_fishing_manager() -> FishingManager:
    """Get the fishing manager singleton."""
    global _fishing_manager
    if _fishing_manager is None:
        _fishing_manager = FishingManager()
    return _fishing_manager
