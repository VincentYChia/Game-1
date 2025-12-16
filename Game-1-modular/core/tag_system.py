"""
Tag System Core - Single Source of Truth Loader
Loads tag definitions from JSON and provides lookup functions
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class TagDefinition:
    """Single tag definition"""
    name: str
    category: str
    description: str
    priority: int = 0
    requires_params: List[str] = field(default_factory=list)
    default_params: Dict[str, Any] = field(default_factory=dict)
    conflicts_with: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    alias_of: Optional[str] = None
    stacking: Optional[str] = None
    immunity: List[str] = field(default_factory=list)
    synergies: Dict[str, Any] = field(default_factory=dict)
    context_behavior: Dict[str, Any] = field(default_factory=dict)
    auto_apply_chance: float = 0.0
    auto_apply_status: Optional[str] = None
    parent: Optional[str] = None


class TagRegistry:
    """
    Central registry for all tag definitions
    Loads from tag-definitions.JSON (single source of truth)
    """
    _instance = None

    def __init__(self):
        self.definitions: Dict[str, TagDefinition] = {}
        self.categories: Dict[str, List[str]] = {}
        self.aliases: Dict[str, str] = {}  # alias -> real tag name
        self.geometry_priority: List[str] = []
        self.mutually_exclusive: Dict[str, List[str]] = {}
        self.context_inference: Dict[str, str] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = TagRegistry()
            cls._instance.load()
        return cls._instance

    def load(self):
        """Load tag definitions from JSON"""
        if self._loaded:
            return

        # Find tag-definitions.JSON
        base_dir = Path(__file__).parent.parent
        tag_def_path = base_dir / "Definitions.JSON" / "tag-definitions.JSON"

        if not tag_def_path.exists():
            raise FileNotFoundError(f"Tag definitions not found: {tag_def_path}")

        with open(tag_def_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Load categories
        self.categories = data.get('categories', {})

        # Load tag definitions
        for tag_name, tag_data in data.get('tag_definitions', {}).items():
            tag_def = TagDefinition(
                name=tag_name,
                category=tag_data.get('category', 'unknown'),
                description=tag_data.get('description', ''),
                priority=tag_data.get('priority', 0),
                requires_params=tag_data.get('requires_params', []),
                default_params=tag_data.get('default_params', {}),
                conflicts_with=tag_data.get('conflicts_with', []),
                aliases=tag_data.get('aliases', []),
                alias_of=tag_data.get('alias_of'),
                stacking=tag_data.get('stacking'),
                immunity=tag_data.get('immunity', []),
                synergies=tag_data.get('synergies', {}),
                context_behavior=tag_data.get('context_behavior', {}),
                auto_apply_chance=tag_data.get('auto_apply_chance', 0.0),
                auto_apply_status=tag_data.get('auto_apply_status'),
                parent=tag_data.get('parent')
            )

            self.definitions[tag_name] = tag_def

            # Register aliases
            for alias in tag_def.aliases:
                self.aliases[alias] = tag_name

        # Load conflict resolution rules
        conflict_data = data.get('conflict_resolution', {})
        self.geometry_priority = conflict_data.get('geometry_priority', [])
        self.mutually_exclusive = conflict_data.get('mutually_exclusive', {})

        # Load context inference rules
        self.context_inference = data.get('context_inference', {})

        self._loaded = True

    def resolve_alias(self, tag: str) -> str:
        """Resolve alias to real tag name"""
        return self.aliases.get(tag, tag)

    def get_definition(self, tag: str) -> Optional[TagDefinition]:
        """Get tag definition by name (handles aliases)"""
        real_tag = self.resolve_alias(tag)
        return self.definitions.get(real_tag)

    def get_category(self, tag: str) -> Optional[str]:
        """Get tag category"""
        tag_def = self.get_definition(tag)
        return tag_def.category if tag_def else None

    def is_geometry_tag(self, tag: str) -> bool:
        """Check if tag is a geometry tag"""
        return self.get_category(tag) == 'geometry'

    def is_damage_tag(self, tag: str) -> bool:
        """Check if tag is a damage type"""
        return self.get_category(tag) == 'damage_type'

    def is_status_tag(self, tag: str) -> bool:
        """Check if tag is a status effect"""
        cat = self.get_category(tag)
        return cat in ['status_debuff', 'status_buff']

    def is_context_tag(self, tag: str) -> bool:
        """Check if tag is a context tag"""
        return self.get_category(tag) == 'context'

    def get_tags_by_category(self, category: str) -> List[str]:
        """Get all tags in a category"""
        return [name for name, tag_def in self.definitions.items()
                if tag_def.category == category and not tag_def.alias_of]

    def resolve_geometry_conflict(self, tags: List[str]) -> Optional[str]:
        """Resolve conflicting geometry tags by priority"""
        geometry_tags = [t for t in tags if self.is_geometry_tag(t)]

        if len(geometry_tags) <= 1:
            return geometry_tags[0] if geometry_tags else None

        # Use priority list
        for priority_tag in self.geometry_priority:
            if priority_tag in geometry_tags:
                return priority_tag

        # Fallback: use first one
        return geometry_tags[0]

    def check_mutual_exclusion(self, tag1: str, tag2: str) -> bool:
        """Check if two tags are mutually exclusive"""
        tag1 = self.resolve_alias(tag1)
        tag2 = self.resolve_alias(tag2)

        exclusions = self.mutually_exclusive.get(tag1, [])
        return tag2 in exclusions

    def get_default_params(self, tag: str) -> Dict[str, Any]:
        """Get default parameters for a tag"""
        tag_def = self.get_definition(tag)
        return tag_def.default_params.copy() if tag_def else {}

    def merge_params(self, tag: str, user_params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user params with defaults"""
        defaults = self.get_default_params(tag)
        defaults.update(user_params)
        return defaults


# Global singleton instance
_tag_registry = None

def get_tag_registry() -> TagRegistry:
    """Get global tag registry instance"""
    global _tag_registry
    if _tag_registry is None:
        _tag_registry = TagRegistry.get_instance()
    return _tag_registry
