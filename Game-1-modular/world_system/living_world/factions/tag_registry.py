"""Tag Registry - durable dictionary of all faction tags ever used.

Tracks tag namespaces, appearance counts, creation metadata, and human glosses.
Central registry for tag validation and inventory across the entire faction system.

Usage:
    registry = TagRegistry.get_instance()
    registry.register("nation:stormguard", "nation", "A major northern kingdom")
    registry.save()

    if registry.validate_tag("guild:merchants"):
        count = registry.appearance_count("guild:merchants")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, ClassVar
import time


@dataclass
class TagEntry:
    """Single tag in the registry."""
    tag: str
    namespace: str
    appearance_count: int
    first_seen_game_time: float
    human_gloss: str
    is_generated: bool
    aliases: List[str] = field(default_factory=list)


class TagRegistry:
    """Singleton registry tracking all tags ever used in the game.

    Persists to disk as tag-registry.json. This is the single source of truth
    for tag validation, namespace checking, and terminology consistency.
    """

    _instance: ClassVar[Optional[TagRegistry]] = None

    def __init__(self, config_path: str = "world_system/config/tag-registry.json"):
        self.config_path = Path(config_path)
        self.tags: Dict[str, TagEntry] = {}
        self._modified = False
        self._load()

    @classmethod
    def get_instance(cls) -> TagRegistry:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def _load(self) -> None:
        """Load registry from disk, or initialize empty."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for tag_name, tag_data in data.get('tags', {}).items():
                        # Add tag name to entry (it's the dict key in JSON)
                        entry_data = {"tag": tag_name, **tag_data}
                        self.tags[tag_name] = TagEntry(**entry_data)
                print(f"✓ Loaded {len(self.tags)} tags from registry")
            except Exception as e:
                print(f"⚠ Error loading tag registry: {e}")
                self.tags = {}
        else:
            self.tags = {}
            self._modified = True

    def save(self) -> None:
        """Persist registry to disk."""
        if not self._modified and self.config_path.exists():
            return

        try:
            data = {
                "metadata": {
                    "version": 1,
                    "last_updated_game_time": time.time(),
                    "total_tags": len(self.tags)
                },
                "tags": {
                    tag_name: {
                        "tag": entry.tag,
                        "namespace": entry.namespace,
                        "appearance_count": entry.appearance_count,
                        "first_seen_game_time": entry.first_seen_game_time,
                        "human_gloss": entry.human_gloss,
                        "is_generated": entry.is_generated,
                        "aliases": entry.aliases
                    }
                    for tag_name, entry in self.tags.items()
                }
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Saved {len(self.tags)} tags to registry")
            self._modified = False
        except Exception as e:
            print(f"✗ Error saving tag registry: {e}")

    def register(self, tag: str, namespace: str, gloss: str,
                 is_generated: bool = False, game_time: float = 0.0) -> bool:
        """Register a new tag or increment its appearance count.

        Args:
            tag: Full tag (e.g., "nation:stormguard")
            namespace: Category (e.g., "nation")
            gloss: Human-readable definition
            is_generated: True if LLM created this tag
            game_time: Game time when tag was first seen

        Returns:
            True if tag was newly registered, False if already existed
        """
        if tag not in self.tags:
            self.tags[tag] = TagEntry(
                tag=tag,
                namespace=namespace,
                appearance_count=1,
                first_seen_game_time=game_time,
                human_gloss=gloss,
                is_generated=is_generated
            )
            self._modified = True
            return True
        else:
            self.tags[tag].appearance_count += 1
            self._modified = True
            return False

    def get(self, tag: str) -> Optional[TagEntry]:
        """Fetch a tag entry by name."""
        return self.tags.get(tag)

    def all_tags(self, namespace: Optional[str] = None) -> List[TagEntry]:
        """Get all tags, optionally filtered by namespace.

        Args:
            namespace: If provided, only return tags in this namespace

        Returns:
            List of TagEntry objects
        """
        tags = list(self.tags.values())
        if namespace:
            tags = [t for t in tags if t.namespace == namespace]
        return tags

    def appearance_count(self, tag: str) -> int:
        """Get count of NPCs using this tag."""
        entry = self.get(tag)
        return entry.appearance_count if entry else 0

    def validate_tag(self, tag: str) -> bool:
        """Check if a tag is registered."""
        return tag in self.tags

    def validate_namespace(self, tag: str, expected_namespace: str) -> bool:
        """Check if tag exists and is in the expected namespace."""
        entry = self.get(tag)
        return entry is not None and entry.namespace == expected_namespace

    def add_alias(self, tag: str, alias: str) -> bool:
        """Add an alias to a tag (for backward compatibility).

        Args:
            tag: The canonical tag name
            alias: The old/alternate name

        Returns:
            True if alias was added, False if tag doesn't exist
        """
        if tag not in self.tags:
            return False
        if alias not in self.tags[tag].aliases:
            self.tags[tag].aliases.append(alias)
            self._modified = True
        return True

    def get_by_alias(self, alias: str) -> Optional[TagEntry]:
        """Look up a tag by one of its aliases."""
        for entry in self.tags.values():
            if alias in entry.aliases:
                return entry
        return None

    def namespaces(self) -> List[str]:
        """Get all unique namespaces in the registry."""
        return list(set(entry.namespace for entry in self.tags.values()))

    def count_by_namespace(self, namespace: str) -> int:
        """Count tags in a specific namespace."""
        return len([t for t in self.tags.values() if t.namespace == namespace])

    def mark_generated(self, tag: str) -> bool:
        """Mark a tag as LLM-generated.

        Args:
            tag: Tag to mark

        Returns:
            True if updated, False if tag doesn't exist
        """
        if tag in self.tags:
            self.tags[tag].is_generated = True
            self._modified = True
            return True
        return False
