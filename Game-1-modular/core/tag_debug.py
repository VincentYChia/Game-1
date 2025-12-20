"""
Tag System Debug Logger
Comprehensive logging for tag system troubleshooting
"""

import os
from enum import Enum
from typing import List, Any, Optional
from core.effect_context import EffectConfig, EffectContext


class LogLevel(Enum):
    """Log levels for tag system"""
    DEBUG = 0    # Everything
    INFO = 1     # Important events
    WARNING = 2  # Unusual combinations, conflicts
    ERROR = 3    # Actual errors
    NONE = 999   # Disable logging


class TagDebugger:
    """
    Centralized debug logging for tag system
    """

    def __init__(self, log_level: LogLevel = LogLevel.INFO):
        self.log_level = log_level
        self.log_to_file = os.getenv('TAG_DEBUG_FILE', 'false').lower() == 'true'
        self.log_file_path = "logs/tag_system.log"

        # Create logs directory if needed
        if self.log_to_file:
            os.makedirs("logs", exist_ok=True)

    def set_level(self, level: LogLevel):
        """Change log level"""
        self.log_level = level

    def _should_log(self, level: LogLevel) -> bool:
        """Check if should log at this level"""
        return level.value >= self.log_level.value

    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal log function"""
        if not self._should_log(level):
            return

        # Format message
        prefix = f"[TAG_{level.name}]"
        formatted = f"{prefix} {message}"

        # Add kwargs if present
        if kwargs:
            kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" | {kwargs_str}"

        # Print to console
        print(formatted)

        # Write to file if enabled
        if self.log_to_file:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(formatted + '\n')

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, message, **kwargs)

    # Specialized logging methods

    def log_config_parse(self, config: EffectConfig):
        """Log parsed effect config"""
        self.debug(
            f"Config parsed: geometry={config.geometry_tag}, "
            f"damage={config.damage_tags}, status={config.status_tags}, "
            f"context={config.context}",
            tags=config.raw_tags
        )

        # Log warnings
        for warning in config.warnings:
            self.warning(warning)

        # Log conflict resolutions
        for conflict in config.conflicts_resolved:
            self.info(conflict)

    def log_effect_application(self, context: EffectContext):
        """Log effect being applied"""
        source_name = getattr(context.source, 'name', 'Unknown')
        target_name = getattr(context.primary_target, 'name', 'Unknown')

        self.debug(
            f"Effect: {source_name} -> {target_name}",
            geometry=context.config.geometry_tag,
            damage=context.config.base_damage,
            healing=context.config.base_healing,
            targets=len(context.targets)
        )

    def log_geometry_calculation(self, geometry: str, targets: List[Any]):
        """Log geometry target calculation"""
        target_names = [getattr(t, 'name', 'Unknown') for t in targets]
        self.debug(
            f"Geometry '{geometry}' found {len(targets)} targets",
            targets=target_names
        )

    def log_status_application(self, target: Any, status: str, params: dict):
        """Log status effect application"""
        target_name = getattr(target, 'name', 'Unknown')
        self.info(
            f"Status '{status}' applied to {target_name}",
            duration=params.get('duration', 'N/A')
        )

    def log_status_immune(self, target: Any, status: str):
        """Log status immunity"""
        target_name = getattr(target, 'name', 'Unknown')
        target_type = getattr(target, 'category', 'unknown')
        self.info(
            f"Status '{status}' blocked - {target_name} immune",
            target_type=target_type
        )

    def log_context_mismatch(self, tag: str, target: Any, context: str):
        """Log context mismatch (e.g., NPC with combat tags)"""
        target_name = getattr(target, 'name', 'Unknown')
        target_type = type(target).__name__
        self.debug(
            f"Tag '{tag}' ignored on {target_name} (type: {target_type}) - no {context} system",
            tag=tag,
            context=context
        )

    def log_tag_conflict(self, tags: List[str], resolution: str):
        """Log tag conflict resolution"""
        self.warning(
            f"Tag conflict detected",
            conflicting_tags=tags,
            resolution=resolution
        )

    def log_synergy_applied(self, tag1: str, tag2: str, bonus: str):
        """Log synergy bonus"""
        self.info(
            f"Synergy activated: {tag1} + {tag2}",
            bonus=bonus
        )

    def log_missing_param(self, tag: str, param: str):
        """Log missing required parameter"""
        self.error(
            f"Missing required parameter for tag '{tag}'",
            required_param=param
        )

    def log_chain_target(self, source: Any, target: Any, jump: int, distance: float):
        """Log chain jump"""
        source_name = getattr(source, 'name', 'Unknown')
        target_name = getattr(target, 'name', 'Unknown')
        self.debug(
            f"Chain jump {jump}: {source_name} -> {target_name}",
            distance=f"{distance:.1f}"
        )

    def log_cone_targets(self, source: Any, angle: float, range: float, count: int):
        """Log cone calculation"""
        source_name = getattr(source, 'name', 'Unknown')
        self.debug(
            f"Cone from {source_name}: {angle}° angle, {range} range",
            targets_found=count
        )

    # Crafting Tag System Logging

    def log_smithing_inheritance(self, recipe_id: str, recipe_tags: List[str], inheritable_tags: List[str]):
        """Log smithing tag inheritance"""
        filtered_out = [t for t in recipe_tags if t not in inheritable_tags]
        self.info(
            f"⚒️  Smithing: Recipe '{recipe_id}' tag inheritance",
            recipe_tags=recipe_tags,
            inherited=inheritable_tags,
            filtered=filtered_out
        )

    def log_refining_bonuses(self, recipe_id: str, recipe_tags: List[str],
                            base_qty: int, base_rarity: str,
                            final_qty: int, final_rarity: str):
        """Log refining probabilistic bonuses"""
        bonus_yield_proc = (final_qty > base_qty)
        quality_upgrade_proc = (final_rarity != base_rarity)

        self.info(
            f"🔨 Refining: Recipe '{recipe_id}' probabilistic bonuses",
            recipe_tags=recipe_tags,
            base_output=f"{base_qty}x {base_rarity}",
            final_output=f"{final_qty}x {final_rarity}",
            yield_proc=bonus_yield_proc,
            quality_proc=quality_upgrade_proc
        )

        if bonus_yield_proc or quality_upgrade_proc:
            self.info(f"   🎲 PROBABILISTIC BONUS ACTIVATED!")

    def log_alchemy_detection(self, recipe_id: str, recipe_tags: List[str],
                              is_consumable: bool, effect_type: Optional[str]):
        """Log alchemy effect detection"""
        output_type = "potion" if is_consumable else "transmutation"
        self.info(
            f"⚗️  Alchemy: Recipe '{recipe_id}' effect detection",
            recipe_tags=recipe_tags,
            output_type=output_type,
            effect_type=effect_type or "None"
        )

    def log_crafting_result(self, discipline: str, recipe_id: str, result: dict):
        """Log crafting result"""
        if not result.get('success'):
            self.warning(
                f"Crafting failed: {discipline}/{recipe_id}",
                reason=result.get('message', 'Unknown')
            )
            return

        self.info(
            f"📦 Crafting complete: {discipline}/{recipe_id}",
            output=f"{result.get('quantity', 1)}x {result.get('outputId', 'unknown')}",
            rarity=result.get('rarity', 'common'),
            tags=result.get('tags'),
            effect_type=result.get('effect_type'),
            is_consumable=result.get('is_consumable')
        )


# Global debugger instance
_debugger = None

def get_tag_debugger() -> TagDebugger:
    """Get global tag debugger instance"""
    global _debugger
    if _debugger is None:
        # Check environment variable for log level
        level_str = os.getenv('TAG_LOG_LEVEL', 'INFO').upper()
        try:
            level = LogLevel[level_str]
        except KeyError:
            level = LogLevel.INFO

        _debugger = TagDebugger(log_level=level)

    return _debugger


def set_log_level(level: LogLevel):
    """Set global log level"""
    debugger = get_tag_debugger()
    debugger.set_level(level)
