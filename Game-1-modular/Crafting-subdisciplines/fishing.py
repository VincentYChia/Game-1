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

Configuration loaded from: Definitions.JSON/fishing-config.JSON
"""

import pygame
import math
import random
import json
import os
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field


# ============================================================================
# FISHING CONFIG LOADER - JSON-driven configuration
# ============================================================================

class FishingConfig:
    """
    Singleton class that loads and caches fishing minigame configuration from JSON.

    Follows the game's JSON-driven design philosophy - all values that might need
    balancing are stored in Definitions.JSON/fishing-config.JSON.
    """
    _instance = None
    _config = None

    @classmethod
    def get_instance(cls):
        """Get the singleton config instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Load config from JSON file."""
        if FishingConfig._config is None:
            self._load_config()

    def _load_config(self):
        """Load configuration from JSON file with fallback to defaults."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'Definitions.JSON',
            'fishing-config.JSON'
        )

        try:
            with open(config_path, 'r') as f:
                FishingConfig._config = json.load(f)
                print(f"Loaded fishing config from {config_path}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load fishing config ({e}), using defaults")
            FishingConfig._config = self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        """Return default config values if JSON fails to load."""
        return {
            "minigame": {
                "pond_dimensions": {"width": 500, "height": 400, "margin": 50},
                "base_difficulty": {
                    "ripple_count": 8, "target_radius": 40, "expand_speed": 80,
                    "hit_tolerance": 15, "spawn_delay": 1.5, "max_active_ripples": 2
                },
                "scoring": {
                    "perfect_tolerance": 5, "good_tolerance": 10, "fair_tolerance": 15,
                    "perfect_score": 100, "good_score": 75, "fair_score": 50, "min_partial_score": 25
                },
                "success_thresholds": {"min_hit_rate": 0.5, "min_avg_score": 40},
                "quality_tiers": {
                    "legendary": {"min_performance": 0.9, "bonus_mult": 1.5},
                    "masterwork": {"min_performance": 0.75, "bonus_mult": 1.3},
                    "superior": {"min_performance": 0.6, "bonus_mult": 1.15},
                    "fine": {"min_performance": 0.4, "bonus_mult": 1.0},
                    "normal": {"min_performance": 0.0, "bonus_mult": 0.8}
                }
            },
            "stat_effects": {
                "luck": {"ripple_reduction_per_point": 0.1, "min_ripples": 4, "max_ripples": 15},
                "strength": {"tolerance_bonus_per_point": 0.5, "max_tolerance": 30},
                "rod_tier": {"speed_reduction_per_tier": 0.15, "min_speed_mult": 0.55}
            },
            "tier_scaling": {"ripple_multiplier": 0.25, "speed_multiplier": 0.2},
            "xp_rewards": {"tier_1": 100, "tier_2": 400, "tier_3": 1600, "tier_4": 6400},
            "durability": {"success_loss": 1.0, "fail_loss_multiplier": 2.0}
        }

    @property
    def config(self) -> Dict[str, Any]:
        """Get the loaded configuration."""
        return FishingConfig._config

    def get(self, *keys, default=None):
        """
        Get a nested config value by keys.

        Example: config.get('minigame', 'pond_dimensions', 'width')
        """
        result = self.config
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return default
        return result


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

    Configuration is loaded from Definitions.JSON/fishing-config.JSON
    """

    def __init__(self, fishing_spot_tier: int, equipped_rod: Optional[Any] = None,
                 player_stats: Optional[Dict] = None, character: Optional[Any] = None):
        """
        Initialize fishing minigame.

        Args:
            fishing_spot_tier: Tier of the fishing spot (1-4)
            equipped_rod: The equipped fishing rod (for tier/quality)
            player_stats: Player's stats dict with 'luck', 'strength', etc.
            character: The player character (for title/buff bonuses)
        """
        # Load config from JSON
        self.cfg = FishingConfig.get_instance()

        # Store parameters
        self.fishing_spot_tier = fishing_spot_tier
        self.equipped_rod = equipped_rod
        self.player_stats = player_stats or {}
        self.character = character

        # Load base constants from config
        pond = self.cfg.get('minigame', 'pond_dimensions', default={})
        self.POND_WIDTH = pond.get('width', 500)
        self.POND_HEIGHT = pond.get('height', 400)
        self.POND_MARGIN = pond.get('margin', 50)

        # Load base difficulty from config
        base = self.cfg.get('minigame', 'base_difficulty', default={})
        self.BASE_RIPPLE_COUNT = base.get('ripple_count', 8)
        self.BASE_TARGET_RADIUS = base.get('target_radius', 40)
        self.BASE_EXPAND_SPEED = base.get('expand_speed', 80)
        self.BASE_HIT_TOLERANCE = base.get('hit_tolerance', 15)
        self.BASE_SPAWN_DELAY = base.get('spawn_delay', 1.5)
        self.MAX_ACTIVE_RIPPLES = base.get('max_active_ripples', 2)

        # Load scoring thresholds from config
        scoring = self.cfg.get('minigame', 'scoring', default={})
        self.PERFECT_TOLERANCE = scoring.get('perfect_tolerance', 5)
        self.GOOD_TOLERANCE = scoring.get('good_tolerance', 10)
        self.FAIR_TOLERANCE = scoring.get('fair_tolerance', 15)
        self.PERFECT_SCORE = scoring.get('perfect_score', 100)
        self.GOOD_SCORE = scoring.get('good_score', 75)
        self.FAIR_SCORE = scoring.get('fair_score', 50)
        self.MIN_PARTIAL_SCORE = scoring.get('min_partial_score', 25)

        # Load success thresholds
        thresholds = self.cfg.get('minigame', 'success_thresholds', default={})
        self.MIN_HIT_RATE = thresholds.get('min_hit_rate', 0.5)
        self.MIN_AVG_SCORE = thresholds.get('min_avg_score', 40)

        # Extract player stats
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

        # Extract bonuses from titles, skills, and enchantments
        self._extract_bonuses()

        # Calculate adjusted parameters based on stats
        self._calculate_difficulty()

        # Game state
        self.active = False
        self.ripples: List[Ripple] = []

    def _extract_bonuses(self):
        """
        Extract bonuses from titles, skills (buffs), and enchantments.

        Bonuses applied:
        - Title bonuses: fishing_speed, fishing_accuracy, rare_fish_chance, fishing_yield
        - Skill buffs: empower (STR boost), quicken (speed), elevate (quality), enrich (yield)
        - Enchantments: Efficiency (gathering_speed_multiplier) on rod
        """
        # Initialize bonus accumulators
        self.title_speed_bonus = 0.0
        self.title_accuracy_bonus = 0.0
        self.title_rare_fish_bonus = 0.0
        self.title_yield_bonus = 0.0
        self.title_luck_bonus = 0.0

        self.buff_empower_bonus = 0.0  # STR boost for tolerance
        self.buff_quicken_bonus = 0.0  # Speed (slower ripples)
        self.buff_elevate_bonus = 0.0  # Quality (rare fish chance)
        self.buff_enrich_bonus = 0.0   # Yield bonus

        self.enchant_efficiency_bonus = 0.0  # Rod quality multiplier

        # Extract title bonuses
        if self.character and hasattr(self.character, 'titles'):
            self.title_speed_bonus = self.character.titles.get_total_bonus('fishing_speed')
            self.title_accuracy_bonus = self.character.titles.get_total_bonus('fishing_accuracy')
            self.title_rare_fish_bonus = self.character.titles.get_total_bonus('rare_fish_chance')
            self.title_yield_bonus = self.character.titles.get_total_bonus('fishing_yield')
            self.title_luck_bonus = self.character.titles.get_total_bonus('luck_stat')

        # Extract buff bonuses from skills
        if self.character and hasattr(self.character, 'buffs'):
            # Empower buff increases STR calculation (for hit tolerance)
            self.buff_empower_bonus = self.character.buffs.get_total_bonus('empower', 'fishing')
            # Quicken buff slows ripples (more time)
            self.buff_quicken_bonus = self.character.buffs.get_total_bonus('quicken', 'fishing')
            # Elevate buff increases quality/rare fish chance
            self.buff_elevate_bonus = self.character.buffs.get_total_bonus('elevate', 'fishing')
            # Enrich buff increases yield
            self.buff_enrich_bonus = self.character.buffs.get_total_bonus('enrich', 'fishing')

        # Extract enchantment bonuses from equipped rod
        if self.equipped_rod and hasattr(self.equipped_rod, 'enchantments') and self.equipped_rod.enchantments:
            for ench in self.equipped_rod.enchantments:
                effect = ench.get('effect', {})
                # Efficiency enchantment provides gathering_speed_multiplier
                if effect.get('type') == 'gathering_speed_multiplier':
                    self.enchant_efficiency_bonus = effect.get('value', 0.0)
                    break  # Only use first efficiency enchantment

        # Log extracted bonuses if any are present
        total_bonuses = (self.title_speed_bonus + self.title_accuracy_bonus +
                        self.buff_empower_bonus + self.buff_quicken_bonus +
                        self.enchant_efficiency_bonus)
        if total_bonuses > 0:
            print(f"Fishing bonuses extracted:")
            if self.title_speed_bonus > 0:
                print(f"   Title speed: +{self.title_speed_bonus*100:.0f}%")
            if self.title_accuracy_bonus > 0:
                print(f"   Title accuracy: +{self.title_accuracy_bonus*100:.0f}%")
            if self.title_rare_fish_bonus > 0:
                print(f"   Title rare fish: +{self.title_rare_fish_bonus*100:.0f}%")
            if self.title_yield_bonus > 0:
                print(f"   Title yield: +{self.title_yield_bonus*100:.0f}%")
            if self.buff_empower_bonus > 0:
                print(f"   Skill empower (STR): +{self.buff_empower_bonus*100:.0f}%")
            if self.buff_quicken_bonus > 0:
                print(f"   Skill quicken (speed): +{self.buff_quicken_bonus*100:.0f}%")
            if self.buff_elevate_bonus > 0:
                print(f"   Skill elevate (quality): +{self.buff_elevate_bonus*100:.0f}%")
            if self.buff_enrich_bonus > 0:
                print(f"   Skill enrich (yield): +{self.buff_enrich_bonus*100:.0f}%")
            if self.enchant_efficiency_bonus > 0:
                print(f"   Efficiency enchant: +{self.enchant_efficiency_bonus*100:.0f}%")

    def _calculate_difficulty(self):
        """Calculate game parameters based on tier, stats, titles, skills, and enchantments."""
        # Load stat effect configs
        luck_cfg = self.cfg.get('stat_effects', 'luck', default={})
        str_cfg = self.cfg.get('stat_effects', 'strength', default={})
        rod_cfg = self.cfg.get('stat_effects', 'rod_tier', default={})
        tier_cfg = self.cfg.get('tier_scaling', default={})

        # Base difficulty scales with fishing spot tier
        tier_mult = tier_cfg.get('ripple_multiplier', 0.25)
        tier_multiplier = 1.0 + (self.fishing_spot_tier - 1) * tier_mult

        # LCK reduces ripple count (makes game shorter)
        # Title luck bonus adds to effective luck
        luck_reduction_per = luck_cfg.get('ripple_reduction_per_point', 0.1)
        min_ripples = luck_cfg.get('min_ripples', 4)
        max_ripples = luck_cfg.get('max_ripples', 15)

        effective_luck = self.luck + (self.luck * self.title_luck_bonus)
        luck_reduction = effective_luck * luck_reduction_per
        self.required_ripples = max(min_ripples, int(self.BASE_RIPPLE_COUNT - luck_reduction))

        # Higher tier fishing spots need more ripples
        self.required_ripples = int(self.required_ripples * tier_multiplier)
        self.required_ripples = max(min_ripples, min(max_ripples, self.required_ripples))

        # STR increases hit tolerance (larger click area)
        # Empower buff and accuracy title bonus add to tolerance
        tolerance_per = str_cfg.get('tolerance_bonus_per_point', 0.5)
        max_tolerance = str_cfg.get('max_tolerance', 30)

        # Calculate effective STR with empower buff bonus
        effective_str = self.strength * (1.0 + self.buff_empower_bonus)
        str_bonus = effective_str * tolerance_per

        # Title accuracy bonus adds directly to tolerance
        accuracy_bonus = self.BASE_HIT_TOLERANCE * self.title_accuracy_bonus

        self.hit_tolerance = self.BASE_HIT_TOLERANCE + str_bonus + accuracy_bonus
        self.hit_tolerance = min(max_tolerance, self.hit_tolerance)

        # Rod tier affects expansion speed (higher tier = slower = more time)
        # Efficiency enchantment and quicken buff further reduce speed (more time)
        speed_reduction = rod_cfg.get('speed_reduction_per_tier', 0.15)
        min_speed_mult = rod_cfg.get('min_speed_mult', 0.55)

        rod_speed_mult = 1.0 - (self.rod_tier - 1) * speed_reduction

        # Efficiency enchantment acts as additional rod tier boost
        # Each 20% efficiency = ~1 tier worth of speed reduction
        efficiency_speed_reduction = self.enchant_efficiency_bonus * 0.75
        rod_speed_mult -= efficiency_speed_reduction

        rod_speed_mult = max(min_speed_mult, rod_speed_mult)

        # Fishing spot tier increases speed (harder)
        spot_speed_multiplier = tier_cfg.get('speed_multiplier', 0.2)
        spot_speed_mult = 1.0 + (self.fishing_spot_tier - 1) * spot_speed_multiplier

        # Apply quicken buff and title speed bonus to reduce expand speed
        speed_bonus = self.buff_quicken_bonus + self.title_speed_bonus
        final_speed_mult = rod_speed_mult * spot_speed_mult * (1.0 - speed_bonus * 0.5)
        final_speed_mult = max(0.3, final_speed_mult)  # Don't let it go too slow

        self.expand_speed = self.BASE_EXPAND_SPEED * final_speed_mult

        # Spawn delay also affected by rod (more time between ripples)
        self.spawn_delay = self.BASE_SPAWN_DELAY * (1.0 / rod_speed_mult)
        self.spawn_delay = max(0.8, min(2.5, self.spawn_delay))

        # Target radius stays constant, but max radius increases with tier
        self.target_radius = self.BASE_TARGET_RADIUS
        self.max_radius = self.target_radius * 2.5  # Miss if expand past this

        # Log difficulty info
        print(f"Fishing difficulty calculated:")
        print(f"   Spot Tier: {self.fishing_spot_tier}, Rod Tier: {self.rod_tier}")
        print(f"   LCK: {self.luck} (eff: {effective_luck:.1f}) -> {self.required_ripples} ripples")
        print(f"   STR: {self.strength} (eff: {effective_str:.1f}) -> {self.hit_tolerance:.1f}px tolerance")
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
        if (len([r for r in self.ripples if r.active]) < self.MAX_ACTIVE_RIPPLES and
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
            # Calculate score based on accuracy using config values
            if ring_distance <= self.PERFECT_TOLERANCE:
                score = self.PERFECT_SCORE
                self.perfect_hits += 1
                print(f"   PERFECT! (+{score})")
            elif ring_distance <= self.GOOD_TOLERANCE:
                score = self.GOOD_SCORE
                print(f"   Good! (+{score})")
            elif ring_distance <= self.FAIR_TOLERANCE:
                score = self.FAIR_SCORE
                print(f"   Fair (+{score})")
            else:
                # Partial hit
                score = max(self.MIN_PARTIAL_SCORE, int(self.FAIR_SCORE * (1 - ring_distance / self.hit_tolerance)))
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
        """End the minigame and calculate results using JSON config, titles, and skills."""
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
        # Apply elevate buff and rare fish title bonus to boost performance
        base_performance = (avg_score / 100) * hit_rate
        quality_bonus = self.buff_elevate_bonus + self.title_rare_fish_bonus
        performance = min(1.0, base_performance * (1.0 + quality_bonus))

        # Success threshold from config
        self.success = hit_rate >= self.MIN_HIT_RATE and avg_score >= self.MIN_AVG_SCORE

        # Determine quality tier based on performance using config
        quality_tiers = self.cfg.get('minigame', 'quality_tiers', default={})

        # Check tiers in order from highest to lowest
        if performance >= quality_tiers.get('legendary', {}).get('min_performance', 0.9):
            quality_tier = "Legendary"
            bonus_mult = quality_tiers.get('legendary', {}).get('bonus_mult', 1.5)
        elif performance >= quality_tiers.get('masterwork', {}).get('min_performance', 0.75):
            quality_tier = "Masterwork"
            bonus_mult = quality_tiers.get('masterwork', {}).get('bonus_mult', 1.3)
        elif performance >= quality_tiers.get('superior', {}).get('min_performance', 0.6):
            quality_tier = "Superior"
            bonus_mult = quality_tiers.get('superior', {}).get('bonus_mult', 1.15)
        elif performance >= quality_tiers.get('fine', {}).get('min_performance', 0.4):
            quality_tier = "Fine"
            bonus_mult = quality_tiers.get('fine', {}).get('bonus_mult', 1.0)
        else:
            quality_tier = "Normal"
            bonus_mult = quality_tiers.get('normal', {}).get('bonus_mult', 0.8)

        # Apply title and skill yield bonuses to bonus_mult
        yield_bonus = self.title_yield_bonus + self.buff_enrich_bonus
        bonus_mult *= (1.0 + yield_bonus)

        # XP reward based on fishing spot tier from config
        xp_config = self.cfg.get('xp_rewards', default={})
        tier_key = f"tier_{self.fishing_spot_tier}"
        base_xp = xp_config.get(tier_key, 100 * (4 ** (self.fishing_spot_tier - 1)))
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

        # Create minigame with character for title/buff bonuses
        self.active_minigame = FishingMinigame(
            fishing_spot_tier=resource.tier,
            equipped_rod=equipped_rod,
            player_stats=player_stats,
            character=character
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

        # Load durability config
        cfg = FishingConfig.get_instance()
        durability_cfg = cfg.get('durability', default={})
        success_loss = durability_cfg.get('success_loss', 1.0)
        fail_loss_mult = durability_cfg.get('fail_loss_multiplier', 2.0)

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

            # Normal durability loss from config
            durability_loss = success_loss

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
            # FAIL: No loot, multiplied durability loss from config
            durability_loss = success_loss * fail_loss_mult

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

                # Unbreaking enchantment reduces durability loss
                if hasattr(equipped_rod, 'enchantments') and equipped_rod.enchantments:
                    for ench in equipped_rod.enchantments:
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'durability_multiplier':
                            reduction = effect.get('value', 0.0)
                            loss_mult *= (1.0 - reduction)
                            break

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
