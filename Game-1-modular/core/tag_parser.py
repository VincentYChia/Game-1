"""
Tag Parser - Converts tags + params into EffectConfig
"""

from typing import List, Dict, Any, Optional
from core.tag_system import get_tag_registry
from core.effect_context import EffectConfig


class TagParser:
    """
    Parses tags from item/skill JSON and creates EffectConfig
    Uses TagRegistry as single source of truth
    """

    def __init__(self):
        self.registry = get_tag_registry()

    def parse(self, tags: List[str], params: Dict[str, Any]) -> EffectConfig:
        """
        Parse tags and params into EffectConfig

        Args:
            tags: List of tag strings from JSON
            params: effectParams dict from JSON

        Returns:
            EffectConfig with categorized tags and resolved conflicts
        """
        config = EffectConfig(raw_tags=tags.copy())

        # Resolve all aliases first
        resolved_tags = [self.registry.resolve_alias(tag) for tag in tags]

        # Categorize tags
        geometry_tags = []
        damage_tags = []
        status_tags = []
        context_tags = []
        special_tags = []
        trigger_tags = []

        for tag in resolved_tags:
            category = self.registry.get_category(tag)

            if category == 'geometry':
                geometry_tags.append(tag)
            elif category == 'damage_type':
                damage_tags.append(tag)
            elif category in ['status_debuff', 'status_buff']:
                status_tags.append(tag)
            elif category == 'context':
                context_tags.append(tag)
            elif category == 'special':
                special_tags.append(tag)
            elif category == 'trigger':
                trigger_tags.append(tag)
            elif category == 'equipment':
                pass  # Handled elsewhere
            elif category == 'unknown':
                config.warnings.append(f"Unknown tag: {tag}")

        # Resolve geometry conflicts
        if len(geometry_tags) > 1:
            resolved_geometry = self.registry.resolve_geometry_conflict(geometry_tags)
            config.geometry_tag = resolved_geometry
            ignored = [g for g in geometry_tags if g != resolved_geometry]
            config.conflicts_resolved.append(
                f"Geometry conflict: using '{resolved_geometry}', ignoring {ignored}"
            )
        elif geometry_tags:
            config.geometry_tag = geometry_tags[0]
        else:
            # Default to single_target
            config.geometry_tag = "single_target"

        # Store categorized tags
        config.damage_tags = damage_tags
        config.status_tags = status_tags
        config.context_tags = context_tags
        config.special_tags = special_tags
        config.trigger_tags = trigger_tags

        # Resolve context
        config.context = self._infer_context(context_tags, damage_tags, status_tags, params)

        # Check for unusual context combinations
        if context_tags:
            if 'enemy' in context_tags and damage_tags:
                pass  # Expected
            elif 'enemy' in context_tags and ('healing' in resolved_tags or params.get('baseHealing', 0) > 0):
                config.warnings.append("Healing effect on enemy context - is this intentional?")
            elif 'ally' in context_tags and damage_tags:
                config.warnings.append("Damage effect on ally context - friendly fire?")

        # Merge parameters with defaults
        config.params = self._merge_all_params(resolved_tags, params)

        # Extract base damage/healing
        config.base_damage = config.params.get('baseDamage', 0.0)
        config.base_healing = config.params.get('baseHealing', 0.0)

        # Check for synergies
        self._apply_synergies(config)

        # Check for mutual exclusions
        self._check_mutual_exclusions(config)

        return config

    def _infer_context(self, context_tags: List[str], damage_tags: List[str],
                      status_tags: List[str], params: Dict[str, Any]) -> str:
        """Infer context if not explicitly specified"""
        if context_tags:
            # Use first explicit context tag
            return context_tags[0]

        # Infer from effect type
        has_damage = damage_tags or params.get('baseDamage', 0) > 0
        has_healing = params.get('baseHealing', 0) > 0

        # Check status tags category
        debuff_statuses = [tag for tag in status_tags
                          if self.registry.get_category(tag) == 'status_debuff']
        buff_statuses = [tag for tag in status_tags
                        if self.registry.get_category(tag) == 'status_buff']

        if has_damage or debuff_statuses:
            return "enemy"
        elif has_healing or buff_statuses:
            return "ally"
        else:
            return "enemy"  # Default

    def _merge_all_params(self, tags: List[str], user_params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge all tag default params with user params"""
        merged = {}

        # Start with defaults for each tag
        for tag in tags:
            tag_defaults = self.registry.get_default_params(tag)
            merged.update(tag_defaults)

        # Override with user params
        merged.update(user_params)

        return merged

    def _apply_synergies(self, config: EffectConfig):
        """Apply tag synergies (e.g., lightning + chain = +20% range)"""
        for tag in config.raw_tags:
            tag_def = self.registry.get_definition(tag)
            if not tag_def or not tag_def.synergies:
                continue

            for synergy_tag, bonuses in tag_def.synergies.items():
                if synergy_tag in config.raw_tags:
                    # Apply bonuses
                    for param, bonus in bonuses.items():
                        if param.endswith('_bonus'):
                            # Multiplicative bonus
                            base_param = param.replace('_bonus', '')
                            if base_param in config.params:
                                current = config.params[base_param]
                                config.params[base_param] = current * (1.0 + bonus)
                                config.warnings.append(
                                    f"Synergy: {tag} + {synergy_tag} = {base_param} +{bonus*100:.0f}%"
                                )

    def _check_mutual_exclusions(self, config: EffectConfig):
        """Check for mutually exclusive tags"""
        all_tags = (config.damage_tags + config.status_tags +
                   config.context_tags + config.special_tags)

        for i, tag1 in enumerate(all_tags):
            for tag2 in all_tags[i+1:]:
                if self.registry.check_mutual_exclusion(tag1, tag2):
                    config.warnings.append(
                        f"Mutually exclusive tags: {tag1} and {tag2} - {tag2} will override {tag1}"
                    )


# Global parser instance
_parser = None

def get_tag_parser() -> TagParser:
    """Get global tag parser instance"""
    global _parser
    if _parser is None:
        _parser = TagParser()
    return _parser
