"""GameContentIndex — a live mirror of what the game databases currently hold.

WES orphan-detection must know which content EXISTS so a generated artifact can
legitimately reference the *existing* world — a hostile that drops ``iron_ore``,
a chunk that spawns a sacred enemy, an NPC that teaches a real skill. The
ContentRegistry's own store only tracks THIS session's generated rows, so
without this index every reference to sacred (or previously-invented) content
orphans and the plan rolls back.

Design (2026-08-11): the index is a *living* view, in sync with the game in both
directions:
  - **Sacred + startup content:** read lazily from the live singleton databases
    (the same ones the game renders from) — so "what the registry validates
    against" == "what the game sees".
  - **Newly-invented content:** ``refresh(tools)`` is called after every
    commit+reload, so content WES just created becomes referenceable by the very
    next plan. No staleness.

Pure/injectable: pass a ``providers`` map of ``tool -> () -> set[str]`` to test
without the real databases.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, Optional, Set

from world_system.wes.canonical_ids import normalize_id


# tool -> (module_path, class_name, id_dict_attr). The id dict is keyed by the
# artifact's primary id, so ``set(dict.keys())`` is the id set the game holds.
_DB_SPECS: Dict[str, tuple] = {
    "materials": ("data.databases.material_db", "MaterialDatabase", "materials"),
    "skills": ("data.databases.skill_db", "SkillDatabase", "skills"),
    "nodes": ("data.databases.resource_node_db", "ResourceNodeDatabase", "nodes"),
    "hostiles": ("Combat.enemy", "EnemyDatabase", "enemies"),
    "titles": ("data.databases.title_db", "TitleDatabase", "titles"),
    "chunks": ("data.databases.chunk_template_db", "ChunkTemplateDatabase",
               "templates"),
    "npcs": ("data.databases.npc_db", "NPCDatabase", "npcs"),
    "quests": ("data.databases.npc_db", "NPCDatabase", "quests"),
}


def _read_db_ids(module_path: str, class_name: str, attr: str) -> Set[str]:
    """Enumerate a game database's current content ids (defensive)."""
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        db = cls.get_instance()
        # Ensure loaded — the singletons lazy-load from sacred+generated files.
        if not getattr(db, "loaded", True) and hasattr(db, "load_from_files"):
            try:
                db.load_from_files()
            except Exception:
                pass
        d = getattr(db, attr, None)
        if isinstance(d, dict):
            return {str(k) for k in d.keys() if k}
    except Exception:
        pass
    return set()


def _read_db_tags(module_path: str, class_name: str, attr: str) -> Set[str]:
    """Harvest the descriptor/effect tags existing content of a type uses.

    This is the "in-sync" tag vocabulary: generated content should reuse the
    tags the game already understands (which drive UI/search/CNN/stat-tracking),
    and propose anything genuinely new via the ``NEW:`` convention for designer
    review rather than silently inventing tags.
    """
    tags: Set[str] = set()
    try:
        mod = importlib.import_module(module_path)
        db = getattr(mod, class_name).get_instance()
        if not getattr(db, "loaded", True) and hasattr(db, "load_from_files"):
            try:
                db.load_from_files()
            except Exception:
                pass
        d = getattr(db, attr, None)
        if isinstance(d, dict):
            for v in d.values():
                for field_name in ("tags", "effect_tags"):
                    for t in (getattr(v, field_name, None) or []):
                        if isinstance(t, str) and t.strip():
                            tags.add(t.strip())
    except Exception:
        pass
    return tags


def _registry_effect_tags() -> Set[str]:
    """The game's combat/effect tag vocabulary (TagRegistry, tag-definitions)."""
    try:
        from core.tag_system import TagRegistry
        reg = TagRegistry.get_instance()
        names: Set[str] = set(reg.definitions.keys())
        names.update(reg.aliases.keys())
        return {n for n in names if isinstance(n, str) and n}
    except Exception:
        return set()


def _default_providers() -> Dict[str, Callable[[], Set[str]]]:
    return {
        tool: (lambda m=m, c=c, a=a: _read_db_ids(m, c, a))
        for tool, (m, c, a) in _DB_SPECS.items()
    }


def _default_tag_providers() -> Dict[str, Callable[[], Set[str]]]:
    return {
        tool: (lambda m=m, c=c, a=a: _read_db_tags(m, c, a))
        for tool, (m, c, a) in _DB_SPECS.items()
    }


class GameContentIndex:
    """Cache of ``tool -> set(content_id)`` mirroring the live databases."""

    def __init__(
        self,
        providers: Optional[Dict[str, Callable[[], Set[str]]]] = None,
        tag_providers: Optional[Dict[str, Callable[[], Set[str]]]] = None,
    ) -> None:
        self._providers = (
            providers if providers is not None else _default_providers()
        )
        self._tag_providers = (
            tag_providers if tag_providers is not None
            else _default_tag_providers()
        )
        self._cache: Dict[str, Set[str]] = {}
        self._norm: Dict[str, Dict[str, str]] = {}
        self._tag_cache: Dict[str, Set[str]] = {}

    def ids_for(self, tool: str) -> Set[str]:
        if tool not in self._cache:
            ids: Set[str] = set()
            prov = self._providers.get(tool)
            if prov is not None:
                try:
                    ids = set(prov())
                except Exception:
                    ids = set()
            self._cache[tool] = ids
            self._norm[tool] = {normalize_id(i): i for i in ids}
        return self._cache[tool]

    def exists(self, tool: str, content_id: str) -> bool:
        return bool(content_id) and content_id in self.ids_for(tool)

    def canonical_for(self, tool: str, ref: str) -> Optional[str]:
        """The known id ``ref`` folds to under formatting-only normalization."""
        self.ids_for(tool)  # ensure norm map built
        return self._norm.get(tool, {}).get(normalize_id(ref))

    def tags_for(self, tool: str) -> Set[str]:
        """Tag vocabulary generated content of this type may use.

        Union of tags existing content already uses (harvested from the game
        databases — the "in-sync" descriptor tags) and the game's combat/effect
        TagRegistry. Refreshed with the rest of the index after commit+reload,
        so a designer-approved new tag (added to content) becomes valid for the
        next generation.
        """
        if tool not in self._tag_cache:
            tags: Set[str] = set()
            prov = self._tag_providers.get(tool)
            if prov is not None:
                try:
                    tags = set(prov())
                except Exception:
                    tags = set()
            tags |= _registry_effect_tags()
            self._tag_cache[tool] = tags
        return self._tag_cache[tool]

    def refresh(self, tools=None) -> None:
        """Drop cached ids/tags so the next lookup re-reads the databases.

        Called after a commit+reload so newly-invented content is visible
        immediately (keeps the index in sync with the game).
        """
        if tools is None:
            self._cache.clear()
            self._norm.clear()
            self._tag_cache.clear()
        else:
            for t in tools:
                self._cache.pop(t, None)
                self._norm.pop(t, None)
                self._tag_cache.pop(t, None)


__all__ = ["GameContentIndex"]
