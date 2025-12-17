"""
Training Dummy System for Tag Testing
Provides detailed feedback on effects applied, perfect for testing tag combinations
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from data.models import PlacedEntity, PlacedEntityType, Position
from entities.status_manager import add_status_manager_to_entity


@dataclass
class DamageReport:
    """Report of damage/effects applied to training dummy"""
    timestamp: float
    source_name: str
    tags_used: List[str]
    primary_damage: float
    damage_type: str
    targets_hit: int
    status_effects_applied: List[str]
    geometry_used: Optional[str]
    total_damage_dealt: float

    def format_report(self) -> str:
        """Format damage report for console output"""
        lines = [
            "=" * 60,
            f"🎯 TRAINING DUMMY HIT REPORT",
            "=" * 60,
            f"Source: {self.source_name}",
            f"Tags: {', '.join(self.tags_used)}",
            f"Geometry: {self.geometry_used or 'single_target'}",
            f"",
            f"Primary Damage: {self.primary_damage:.1f} {self.damage_type}",
            f"Targets Hit: {self.targets_hit}",
            f"Total Damage Dealt: {self.total_damage_dealt:.1f}",
        ]

        if self.status_effects_applied:
            lines.append(f"Status Effects Applied:")
            for effect in self.status_effects_applied:
                lines.append(f"  - {effect}")
        else:
            lines.append(f"Status Effects: None")

        lines.append("=" * 60)
        return "\n".join(lines)


class TrainingDummy:
    """
    Training dummy for testing tag effects

    Features:
    - High HP (doesn't die easily)
    - Detailed damage reporting
    - Status effect tracking
    - Tag combination feedback
    - Resets automatically
    """

    def __init__(self, position: Position, max_health: float = 10000.0):
        self.position = position
        self.max_health = max_health
        self.current_health = max_health
        self.name = "Training Dummy"
        self.category = "construct"  # Immune to poison, bleed
        self.is_alive = True

        # Add status manager
        add_status_manager_to_entity(self)

        # Tracking
        self.total_damage_taken = 0.0
        self.hit_count = 0
        self.damage_reports: List[DamageReport] = []
        self.last_hit_timestamp = 0.0

        # For tag system
        self.definition = type('obj', (object,), {
            'name': 'Training Dummy',
            'category': 'construct'
        })()

    def take_damage(self, damage: float, damage_type: str = "physical",
                   source: Any = None, tags: List[str] = None,
                   context: Any = None):
        """
        Take damage and generate detailed report

        Args:
            damage: Amount of damage
            damage_type: Type of damage (physical, fire, etc.)
            source: Source entity
            tags: Tags used in the attack
            context: EffectContext from tag system
        """
        import time

        # Apply damage
        actual_damage = damage * self.damage_taken_multiplier
        self.current_health -= actual_damage
        self.total_damage_taken += actual_damage
        self.hit_count += 1
        self.last_hit_timestamp = time.time()

        # Generate report
        source_name = getattr(source, 'name', getattr(source, 'item_id', 'Unknown'))
        tags_used = tags or []

        # Get active status effects
        active_statuses = []
        if hasattr(self, 'status_manager'):
            active_statuses = [effect.name for effect in self.status_manager.active_effects]

        # Get geometry from context
        geometry = None
        targets_hit = 1
        if context:
            geometry = context.config.geometry_tag
            targets_hit = len(context.targets)

        report = DamageReport(
            timestamp=self.last_hit_timestamp,
            source_name=source_name,
            tags_used=tags_used,
            primary_damage=actual_damage,
            damage_type=damage_type,
            targets_hit=targets_hit,
            status_effects_applied=active_statuses,
            geometry_used=geometry,
            total_damage_dealt=actual_damage
        )

        self.damage_reports.append(report)

        # Print report
        print(report.format_report())

        # Print current status
        self._print_status()

        # Auto-reset if health gets low
        if self.current_health <= self.max_health * 0.1:
            self.reset()

    def _print_status(self):
        """Print current dummy status"""
        hp_percent = (self.current_health / self.max_health) * 100

        print(f"\n📊 DUMMY STATUS:")
        print(f"   HP: {self.current_health:.1f}/{self.max_health:.1f} ({hp_percent:.1f}%)")
        print(f"   Total Damage Taken: {self.total_damage_taken:.1f}")
        print(f"   Hits: {self.hit_count}")

        # Show active status effects
        if hasattr(self, 'status_manager') and self.status_manager.active_effects:
            print(f"   Active Status Effects:")
            for effect in self.status_manager.active_effects:
                time_left = effect.duration_remaining
                stacks = getattr(effect, 'stacks', 1)
                print(f"      - {effect.name}: {time_left:.1f}s remaining, {stacks} stacks")

        print()

    def reset(self):
        """Reset dummy to full health and clear status effects"""
        print("\n" + "=" * 60)
        print("🔄 TRAINING DUMMY RESET")
        print("=" * 60)
        print(f"Total damage taken: {self.total_damage_taken:.1f}")
        print(f"Total hits: {self.hit_count}")

        self.current_health = self.max_health
        self.total_damage_taken = 0.0
        self.hit_count = 0
        self.damage_reports.clear()

        if hasattr(self, 'status_manager'):
            self.status_manager.clear_all()

        print("Ready for testing!")
        print("=" * 60 + "\n")

    def update(self, dt: float):
        """Update status effects"""
        if hasattr(self, 'status_manager'):
            self.status_manager.update(dt)

    def print_summary(self):
        """Print summary of all damage reports"""
        if not self.damage_reports:
            print("No damage reports yet.")
            return

        print("\n" + "=" * 60)
        print("📋 TRAINING DUMMY SUMMARY")
        print("=" * 60)
        print(f"Total Hits: {len(self.damage_reports)}")
        print(f"Total Damage: {self.total_damage_taken:.1f}")
        print(f"Average Damage: {self.total_damage_taken / len(self.damage_reports):.1f}")
        print()

        # Group by tag combination
        tag_combos: Dict[tuple, List[float]] = {}
        for report in self.damage_reports:
            key = tuple(sorted(report.tags_used))
            if key not in tag_combos:
                tag_combos[key] = []
            tag_combos[key].append(report.total_damage_dealt)

        print("Damage by Tag Combination:")
        for tags, damages in sorted(tag_combos.items(), key=lambda x: sum(x[1]), reverse=True):
            avg_dmg = sum(damages) / len(damages)
            total_dmg = sum(damages)
            print(f"  {', '.join(tags) or 'No tags'}: {len(damages)} hits, {avg_dmg:.1f} avg, {total_dmg:.1f} total")

        print("=" * 60 + "\n")


def create_training_dummy_entity(position: Position) -> PlacedEntity:
    """
    Create a PlacedEntity configured as a training dummy

    Returns PlacedEntity that can be placed in the world
    """
    dummy = PlacedEntity(
        position=position,
        item_id="training_dummy",
        entity_type=PlacedEntityType.UTILITY_DEVICE,
        tier=1,
        health=10000.0,
        range=0.0,  # Not an attacking entity
        damage=0.0,
        attack_speed=0.0,
        lifetime=float('inf'),  # Never expires
        time_remaining=float('inf')
    )

    # Add custom attributes for dummy
    dummy.max_health = 10000.0
    dummy.current_health = 10000.0
    dummy.total_damage_taken = 0.0
    dummy.hit_count = 0
    dummy.category = "construct"
    dummy.name = "Training Dummy"

    # Add status manager
    add_status_manager_to_entity(dummy)

    return dummy


def create_training_dummy_item_definition():
    """
    Create item definition for training dummy

    This should be added to items-engineering-1.JSON
    """
    return {
        "metadata": {
            "narrative": "Indestructible training dummy for testing combat abilities. Reports detailed damage and effect information. Immune to most status effects due to construct nature.",
            "tags": ["device", "training", "utility", "indestructible"]
        },
        "itemId": "training_dummy",
        "name": "Training Dummy",
        "category": "device",
        "type": "utility",
        "subtype": "training",
        "tier": 1,
        "rarity": "uncommon",
        "effect": "Provides detailed combat feedback for testing. 10,000 HP, auto-resets at 10%.",
        "stackSize": 5,
        "statMultipliers": {
            "weight": 2.0
        },
        "requirements": {
            "level": 1,
            "stats": {}
        },
        "flags": {
            "stackable": True,
            "placeable": True,
            "repairable": False,
            "indestructible": True
        }
    }


# Example usage for testing
if __name__ == "__main__":
    print("Training Dummy System Test")
    print("-" * 60)

    # Create dummy
    dummy = TrainingDummy(Position(10, 10))

    # Simulate some hits
    print("\n1. Testing basic damage:")
    dummy.take_damage(50, "physical", tags=["physical", "single_target"])

    print("\n2. Testing fire + burn:")
    dummy.take_damage(80, "fire", tags=["fire", "circle", "burn"])

    print("\n3. Testing chain lightning:")
    dummy.take_damage(70, "lightning", tags=["lightning", "chain", "shock"])

    # Print summary
    dummy.print_summary()
