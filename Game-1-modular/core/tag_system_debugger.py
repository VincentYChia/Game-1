"""
Tag System Debugger - Comprehensive tag flow validation and logging

This debugger traces tags through the entire pipeline:
JSON → Database → Placement/Equipment → Combat → Effect Execution → Damage Application

Usage:
    TagSystemDebugger.enable()  # Turn on detailed logging
    TagSystemDebugger.disable() # Turn off logging
    TagSystemDebugger.validate_tag_flow() # Check for issues
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TagFlowEvent:
    """Represents a single event in tag processing"""
    timestamp: str
    stage: str  # "json_load", "database", "placement", "combat", "execution", "damage"
    entity_id: str
    tags: List[str]
    params: Dict[str, Any]
    success: bool
    message: str
    warnings: List[str] = field(default_factory=list)


class TagSystemDebugger:
    """Singleton debugger for tag system validation"""

    _instance = None
    _enabled = False
    _events: List[TagFlowEvent] = []
    _warnings: List[str] = []
    _errors: List[str] = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TagSystemDebugger()
        return cls._instance

    @classmethod
    def enable(cls):
        """Enable detailed tag system logging"""
        cls._enabled = True
        print("\n" + "="*70)
        print("🔍 TAG SYSTEM DEBUGGER ENABLED")
        print("="*70)
        print("All tag flows will be logged and validated.")
        print()

    @classmethod
    def disable(cls):
        """Disable tag system logging"""
        cls._enabled = False
        print("\n🔍 Tag System Debugger Disabled")

    @classmethod
    def is_enabled(cls):
        return cls._enabled

    @classmethod
    def log_stage(cls, stage: str, entity_id: str, tags: List[str],
                  params: Dict[str, Any], success: bool = True,
                  message: str = "", warnings: List[str] = None):
        """Log a stage in tag processing"""
        if not cls._enabled:
            return

        event = TagFlowEvent(
            timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
            stage=stage,
            entity_id=entity_id,
            tags=tags or [],
            params=params or {},
            success=success,
            message=message,
            warnings=warnings or []
        )
        cls._events.append(event)

        # Print immediate feedback
        status = "✅" if success else "❌"
        tag_display = f"tags={tags}" if tags else "⚠️  NO TAGS"

        print(f"{status} [{event.timestamp}] {stage.upper()}: {entity_id}")
        print(f"   {tag_display}")
        if params:
            print(f"   params={list(params.keys())}")
        if message:
            print(f"   💬 {message}")
        if warnings:
            for warning in warnings:
                print(f"   ⚠️  {warning}")
                cls._warnings.append(f"{entity_id}: {warning}")
        if not success:
            cls._errors.append(f"{stage}: {entity_id} - {message}")
        print()

    @classmethod
    def log_json_load(cls, item_id: str, tags: List[str], params: Dict[str, Any]):
        """Log when tags are loaded from JSON"""
        warnings = []
        if not tags:
            warnings.append("No effectTags found in JSON")
        if not params:
            warnings.append("No effectParams found in JSON")

        cls.log_stage(
            stage="json_load",
            entity_id=item_id,
            tags=tags,
            params=params,
            success=bool(tags),
            message=f"Loaded from JSON",
            warnings=warnings
        )

    @classmethod
    def log_database_store(cls, item_id: str, tags: List[str], params: Dict[str, Any],
                          db_type: str = "material"):
        """Log when tags are stored in database"""
        warnings = []
        if not tags:
            warnings.append(f"Tags lost during {db_type} database storage!")

        cls.log_stage(
            stage="database_store",
            entity_id=item_id,
            tags=tags,
            params=params,
            success=bool(tags),
            message=f"Stored in {db_type} database",
            warnings=warnings
        )

    @classmethod
    def log_entity_placement(cls, item_id: str, tags: List[str], params: Dict[str, Any]):
        """Log when entity is placed in world"""
        warnings = []
        if not tags:
            warnings.append("Tags lost during placement!")

        cls.log_stage(
            stage="entity_placement",
            entity_id=item_id,
            tags=tags,
            params=params,
            success=bool(tags),
            message="Entity placed in world",
            warnings=warnings
        )

    @classmethod
    def log_equipment_equip(cls, item_id: str, tags: List[str], params: Dict[str, Any]):
        """Log when equipment is equipped"""
        warnings = []
        if not tags:
            warnings.append("Tags lost during equipment!")

        cls.log_stage(
            stage="equipment_equip",
            entity_id=item_id,
            tags=tags,
            params=params,
            success=bool(tags),
            message="Equipment equipped",
            warnings=warnings
        )

    @classmethod
    def log_combat_action(cls, source_id: str, tags: List[str], params: Dict[str, Any],
                         action_type: str = "attack"):
        """Log when combat action is initiated"""
        warnings = []
        if not tags:
            warnings.append(f"Combat {action_type} has NO TAGS - will use legacy system!")

        cls.log_stage(
            stage="combat_action",
            entity_id=source_id,
            tags=tags,
            params=params,
            success=bool(tags),
            message=f"Initiating {action_type}",
            warnings=warnings
        )

    @classmethod
    def log_effect_execution(cls, source_id: str, tags: List[str], params: Dict[str, Any],
                            targets_affected: int):
        """Log when effect is executed"""
        success = bool(tags) and targets_affected > 0
        warnings = []

        if not tags:
            warnings.append("Effect executed without tags!")
        if targets_affected == 0:
            warnings.append("Effect affected 0 targets!")

        cls.log_stage(
            stage="effect_execution",
            entity_id=source_id,
            tags=tags,
            params=params,
            success=success,
            message=f"Affected {targets_affected} target(s)",
            warnings=warnings
        )

    @classmethod
    def log_damage_application(cls, target_id: str, tags: List[str], damage: float,
                               damage_type: str):
        """Log when damage is applied to target"""
        warnings = []
        if not tags:
            warnings.append("Damage applied without tags!")

        cls.log_stage(
            stage="damage_application",
            entity_id=target_id,
            tags=tags,
            params={"damage": damage, "damage_type": damage_type},
            success=bool(tags),
            message=f"{damage:.1f} {damage_type} damage",
            warnings=warnings
        )

    @classmethod
    def validate_tag_flow(cls, item_id: str) -> Dict[str, Any]:
        """Validate that tags flow correctly for a specific item"""
        item_events = [e for e in cls._events if e.entity_id == item_id]

        if not item_events:
            return {
                "valid": False,
                "error": f"No events found for {item_id}",
                "stages_completed": []
            }

        # Check that tags persist through all stages
        stages_with_tags = [e.stage for e in item_events if e.tags]
        stages_without_tags = [e.stage for e in item_events if not e.tags]

        # Tag flow should NOT lose tags after initial load
        tag_loss_detected = False
        if stages_with_tags and stages_without_tags:
            # Check if tags were lost mid-flow
            first_tag_stage_idx = min(i for i, e in enumerate(item_events) if e.tags)
            for i, event in enumerate(item_events):
                if i > first_tag_stage_idx and not event.tags:
                    tag_loss_detected = True
                    break

        return {
            "valid": not tag_loss_detected and bool(stages_with_tags),
            "stages_completed": [e.stage for e in item_events],
            "stages_with_tags": stages_with_tags,
            "stages_without_tags": stages_without_tags,
            "tag_loss_detected": tag_loss_detected,
            "warnings": [e.warnings for e in item_events if e.warnings]
        }

    @classmethod
    def print_summary(cls):
        """Print summary of all tag flows"""
        print("\n" + "="*70)
        print("🔍 TAG SYSTEM DEBUGGER SUMMARY")
        print("="*70)

        print(f"\n📊 STATISTICS:")
        print(f"   Total events logged: {len(cls._events)}")
        print(f"   Total warnings: {len(cls._warnings)}")
        print(f"   Total errors: {len(cls._errors)}")

        if cls._warnings:
            print(f"\n⚠️  WARNINGS ({len(cls._warnings)}):")
            for warning in cls._warnings:
                print(f"   • {warning}")

        if cls._errors:
            print(f"\n❌ ERRORS ({len(cls._errors)}):")
            for error in cls._errors:
                print(f"   • {error}")

        # Group events by entity
        entities = set(e.entity_id for e in cls._events)
        print(f"\n📦 ENTITIES TRACKED ({len(entities)}):")
        for entity_id in sorted(entities):
            entity_events = [e for e in cls._events if e.entity_id == entity_id]
            validation = cls.validate_tag_flow(entity_id)

            status = "✅" if validation["valid"] else "❌"
            print(f"\n   {status} {entity_id}")
            print(f"      Stages: {' → '.join(validation['stages_completed'])}")

            if validation.get("tag_loss_detected"):
                print(f"      ⚠️  TAG LOSS DETECTED!")
            if validation.get("stages_without_tags"):
                print(f"      ⚠️  Stages without tags: {validation['stages_without_tags']}")

        print("\n" + "="*70 + "\n")

    @classmethod
    def clear(cls):
        """Clear all logged events"""
        cls._events.clear()
        cls._warnings.clear()
        cls._errors.clear()
        print("🔍 Tag debugger cleared")

    @classmethod
    def get_events(cls) -> List[TagFlowEvent]:
        """Get all logged events"""
        return cls._events.copy()
