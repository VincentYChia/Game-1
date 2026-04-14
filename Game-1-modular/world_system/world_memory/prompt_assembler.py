"""Prompt assembly engine — core logic for selecting and assembling
LLM prompts from tag-indexed fragments.

Supports multiple fragment files:
- prompt_fragments.json: Layer 2 fragments (123 fragments)
- prompt_fragments_l3.json: Layer 3 consolidation fragments

This module has no UI dependencies. It is used by:
- tools/prompt_editor.py (tkinter visual editor)
- Layer 2 evaluators (runtime prompt assembly)
- Layer 3 consolidators (runtime prompt assembly)
- Tests

The prompt_editor.py UI imports this for its preview/simulation logic.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Paths ───────────────────────────────────────────────────────────

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_FRAGMENTS_PATH = _CONFIG_DIR / "prompt_fragments.json"
_L3_FRAGMENTS_PATH = _CONFIG_DIR / "prompt_fragments_l3.json"
_L4_FRAGMENTS_PATH = _CONFIG_DIR / "prompt_fragments_l4.json"
_L5_FRAGMENTS_PATH = _CONFIG_DIR / "prompt_fragments_l5.json"

# Fragment categories that get matched from trigger tags
FRAGMENT_CATEGORIES = frozenset({
    "species", "material_category", "discipline",
    "tier", "element", "rank", "status_effect",
    "action", "result", "attack_type", "item_category",
    "tool", "npc", "source", "resource", "quality", "rarity",
})

# Domain mapping from event types
EVENT_TO_DOMAIN = {
    "enemy_killed": "combat", "attack_performed": "combat",
    "damage_taken": "combat", "player_death": "combat",
    "dodge_performed": "combat", "status_applied": "combat",
    "resource_gathered": "gathering", "node_depleted": "gathering",
    "craft_attempted": "crafting", "item_invented": "crafting",
    "recipe_discovered": "crafting",
    "level_up": "progression", "skill_learned": "progression",
    "title_earned": "progression", "class_changed": "progression",
    "skill_used": "skills",
    "chunk_entered": "exploration", "area_discovered": "exploration",
    "npc_interaction": "social", "quest_accepted": "social",
    "quest_completed": "social", "quest_failed": "social",
    "item_acquired": "items", "item_equipped": "items",
    "repair_performed": "economy",
    "world_event": "combat",
    "position_sample": "exploration",
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


class PromptAssembler:
    """Loads prompt fragments and assembles prompts from tags.

    Usage:
        assembler = PromptAssembler()
        assembler.load()
        prompt = assembler.assemble(
            tags=["domain:combat", "species:wolf_grey", "tier:1"],
            data_block="Count today: 8\\nAll-time: 47\\n..."
        )
        # prompt.system = "You narrate events... Combat events... Grey Wolf..."
        # prompt.user = "Count today: 8\\nAll-time: 47\\n...\\nWrite ONE factual..."
    """

    def __init__(self, fragments_path: Optional[str] = None):
        self._path = Path(fragments_path) if fragments_path else _FRAGMENTS_PATH
        self.fragments: Dict[str, Any] = {}
        self._l3_fragments: Dict[str, Any] = {}
        self._l4_fragments: Dict[str, Any] = {}
        self._l5_fragments: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> int:
        """Load fragments from JSON files. Returns total fragment count.

        Loads Layer 2 fragments from prompt_fragments.json, Layer 3
        fragments from prompt_fragments_l3.json, Layer 4 from
        prompt_fragments_l4.json, and Layer 5 from prompt_fragments_l5.json
        (each loaded only if present).
        """
        total = 0
        if self._path.exists():
            with open(self._path) as f:
                self.fragments = json.load(f)
            total += self.fragments.get("_meta", {}).get("total_fragments", 0)

        # Load Layer 3 fragments from separate file
        l3_path = self._path.parent / "prompt_fragments_l3.json"
        if l3_path.exists():
            with open(l3_path) as f:
                self._l3_fragments = json.load(f)
            total += self._l3_fragments.get("_meta", {}).get("total_fragments", 0)

        # Load Layer 4 fragments from separate file
        l4_path = self._path.parent / "prompt_fragments_l4.json"
        if l4_path.exists():
            with open(l4_path) as f:
                self._l4_fragments = json.load(f)
            total += self._l4_fragments.get("_meta", {}).get("total_fragments", 0)

        # Load Layer 5 fragments from separate file
        l5_path = self._path.parent / "prompt_fragments_l5.json"
        if l5_path.exists():
            with open(l5_path) as f:
                self._l5_fragments = json.load(f)
            total += self._l5_fragments.get("_meta", {}).get("total_fragments", 0)

        self._loaded = True
        return total

    def save(self):
        """Save current fragments back to JSON."""
        # Update meta
        cats: Dict[str, int] = {}
        for key in self.fragments:
            if key.startswith("_meta"):
                continue
            if key.startswith("_"):
                cats[key] = 1
            else:
                cat = key.split(":")[0] if ":" in key else key
                cats[cat] = cats.get(cat, 0) + 1
        self.fragments.setdefault("_meta", {})
        self.fragments["_meta"]["total_fragments"] = sum(cats.values())
        self.fragments["_meta"]["categories"] = cats

        with open(self._path, "w") as f:
            json.dump(self.fragments, f, indent=2)
            f.write("\n")

    @property
    def fragment_count(self) -> int:
        return self.fragments.get("_meta", {}).get("total_fragments", 0)

    def get_fragment(self, key: str) -> str:
        """Get a single fragment by key. Returns empty string if missing."""
        val = self.fragments.get(key, "")
        return val if isinstance(val, str) else ""

    def set_fragment(self, key: str, text: str):
        """Set a fragment's text."""
        self.fragments[key] = text

    def list_keys(self) -> List[str]:
        """List all fragment keys (excluding _meta)."""
        return sorted(k for k in self.fragments if k != "_meta")

    def list_by_category(self) -> Dict[str, List[str]]:
        """Group fragment keys by category."""
        groups: Dict[str, List[str]] = {}
        for key in self.list_keys():
            if key.startswith("_"):
                cat = key
            else:
                cat = key.split(":")[0] if ":" in key else "other"
            groups.setdefault(cat, []).append(key)
        return groups

    # ── Core Assembly ───────────────────────────────────────────────

    def select_fragments(self, tags: List[str]) -> List[Tuple[str, str]]:
        """Select prompt fragments matching the given tags.

        Returns list of (key, text) tuples in assembly order:
        [_core, domain:X, species:Y, tier:N, ..., _output]
        """
        selected = []

        # Core (always)
        core = self.get_fragment("_core")
        if core:
            selected.append(("_core", core))

        # Domain (first matching)
        for tag in tags:
            if tag.startswith("domain:") and tag in self.fragments:
                selected.append((tag, self.get_fragment(tag)))
                break

        # Entity/context fragments (all matching, deduplicated)
        seen_texts = {text for _, text in selected}
        for tag in tags:
            if ":" not in tag:
                continue
            cat = tag.split(":")[0]
            if cat in FRAGMENT_CATEGORIES:
                text = self.get_fragment(tag)
                if text and text not in seen_texts:
                    selected.append((tag, text))
                    seen_texts.add(text)
                elif not text:
                    # Fallback: try tier if species missing, etc.
                    fallback = self._find_fallback(tag, tags)
                    if fallback and fallback[1] not in seen_texts:
                        selected.append(fallback)
                        seen_texts.add(fallback[1])

        # Output instruction (always)
        output = self.get_fragment("_output")
        if output:
            selected.append(("_output", output))

        return selected

    def _find_fallback(self, missing_tag: str, all_tags: List[str]
                       ) -> Optional[Tuple[str, str]]:
        """Find a fallback fragment when the specific one is missing."""
        cat = missing_tag.split(":")[0]

        fallback_map = {
            "species": "tier",
            "resource": "material_category",
            "discipline": "domain",
            "skill": "domain",
            "npc": "domain",
        }
        fallback_cat = fallback_map.get(cat)
        if not fallback_cat:
            return None

        for tag in all_tags:
            if tag.startswith(f"{fallback_cat}:"):
                text = self.get_fragment(tag)
                if text:
                    return (f"{tag} (fallback for {missing_tag})", text)
        return None

    def assemble(self, tags: List[str],
                 data_block: str = "") -> "AssembledPrompt":
        """Assemble a complete prompt from tags and data.

        Returns an AssembledPrompt with system and user components.
        """
        selected = self.select_fragments(tags)

        # System prompt = all fragments except _output
        system_parts = []
        output_text = ""
        for key, text in selected:
            if key == "_output":
                output_text = text
            else:
                system_parts.append(text)

        system = "\n\n".join(system_parts)
        user = data_block
        if output_text:
            user = f"{data_block}\n\n{output_text}" if data_block else output_text

        return AssembledPrompt(
            system=system,
            user=user,
            fragments_used=selected,
            tags=tags,
            token_estimate=estimate_tokens(system) + estimate_tokens(user),
        )

    def tags_from_event(self, event_type: str, event_subtype: str = "",
                        tier: Optional[int] = None,
                        extra_tags: Optional[List[str]] = None) -> List[str]:
        """Derive prompt-relevant tags from an event type and subtype.

        Utility for evaluators to get the tag list they should pass to assemble().
        """
        tags = []

        # Domain
        domain = EVENT_TO_DOMAIN.get(event_type, "combat")
        tags.append(f"domain:{domain}")

        # Entity from subtype
        if event_type == "enemy_killed" and event_subtype.startswith("killed_"):
            species = event_subtype[len("killed_"):]
            tags.append(f"species:{species}")
        elif event_type == "resource_gathered" and event_subtype.startswith("gathered_"):
            resource = event_subtype[len("gathered_"):]
            tags.append(f"resource:{resource}")
        elif event_type == "craft_attempted" and event_subtype.startswith("crafted_"):
            # Could map to discipline if we had recipe→discipline mapping
            pass

        # Tier
        if tier is not None:
            tags.append(f"tier:{tier}")

        # Extra tags from the event's tag list
        if extra_tags:
            for tag in extra_tags:
                cat = tag.split(":")[0] if ":" in tag else ""
                if cat in FRAGMENT_CATEGORIES:
                    tags.append(tag)

        return tags

    # ── Coverage Validation ─────────────────────────────────────────

    def validate_coverage(self, game_entities: Optional[dict] = None
                          ) -> Dict[str, List[str]]:
        """Check which game entities lack fragments.

        Returns {"missing": [...], "covered": [...]}.
        """
        missing = []
        covered = []

        if game_entities:
            for e in game_entities.get("enemies", []):
                key = f"species:{e.get('id', e.get('enemyId', ''))}"
                if key in self.fragments:
                    covered.append(key)
                else:
                    missing.append(key)

            for d in game_entities.get("disciplines", []):
                key = f"discipline:{d}"
                if key in self.fragments:
                    covered.append(key)
                else:
                    missing.append(key)

        # Always check tiers
        for t in range(1, 5):
            key = f"tier:{t}"
            if key in self.fragments:
                covered.append(key)
            else:
                missing.append(key)

        return {"missing": missing, "covered": covered}

    # ── Layer 3 Assembly ───────────────────────────────────────────

    def get_l3_fragment(self, key: str) -> str:
        """Get a Layer 3 fragment by key. Falls back to Layer 2 fragments."""
        val = self._l3_fragments.get(key, "")
        if isinstance(val, str) and val:
            return val
        # Fallback to L2 fragments
        return self.get_fragment(key)

    def assemble_l3(self, consolidator_id: str,
                    data_block: str = "") -> "AssembledPrompt":
        """Assemble a Layer 3 prompt for a specific consolidator.

        Uses Layer 3 fragments (_l3_core, _l3_output, consolidator-specific).
        Falls back to Layer 2 _core/_output if L3 versions are missing.

        Args:
            consolidator_id: The consolidator type (e.g., 'regional_synthesis').
            data_block: XML-formatted Layer 2 events data.

        Returns:
            AssembledPrompt with system and user components.
        """
        selected = []

        # L3 core (always)
        core = self.get_l3_fragment("_l3_core")
        if core:
            selected.append(("_l3_core", core))

        # Consolidator-specific fragment
        cons_key = f"l3_consolidator:{consolidator_id}"
        cons_frag = self.get_l3_fragment(cons_key)
        if cons_frag:
            selected.append((cons_key, cons_frag))

        # Example if available — try exact match, then prefix
        example_key = f"l3_example:{consolidator_id}"
        example_frag = self.get_l3_fragment(example_key)
        if not example_frag:
            # Try prefix match (e.g., regional_synthesis → regional)
            prefix = consolidator_id.split("_")[0]
            example_key = f"l3_example:{prefix}"
            example_frag = self.get_l3_fragment(example_key)
        if example_frag:
            selected.append((example_key, example_frag))

        # L3 output instruction
        output_text = self.get_l3_fragment("_l3_output")

        # Build system prompt
        system_parts = [text for _, text in selected]
        system = "\n\n".join(system_parts)

        # Build user prompt
        user = data_block
        if output_text:
            user = f"{data_block}\n\n{output_text}" if data_block else output_text

        return AssembledPrompt(
            system=system,
            user=user,
            fragments_used=selected,
            tags=[f"consolidator:{consolidator_id}"],
            token_estimate=estimate_tokens(system) + estimate_tokens(user),
        )


    # ── Layer 4 Assembly ───────────────────────────────────────────

    def get_l4_fragment(self, key: str) -> str:
        """Get a Layer 4 fragment by key. Falls back to L3, then L2."""
        val = self._l4_fragments.get(key, "")
        if isinstance(val, str) and val:
            return val
        return self.get_l3_fragment(key)

    def get_l5_fragment(self, key: str) -> str:
        """Get a Layer 5 fragment by key. Falls back to L4, then L3, then L2."""
        val = self._l5_fragments.get(key, "")
        if isinstance(val, str) and val:
            return val
        return self.get_l4_fragment(key)

    def _collect_all_tag_fragments(self, event_tags: List[str]) -> List[Tuple[str, str]]:
        """Collect matching tag fragments from ALL layers (L2 + L3 + L4 + L5).

        Higher layers can see all lower-layer fragments. This gives them
        richer context about the entities and concepts in their events.
        Returns (key, text) pairs with deduplication by text content.
        """
        selected = []
        seen_texts: Set[str] = set()

        # Check all fragment sources in priority order: L5 → L4 → L3 → L2
        all_sources = [
            self._l5_fragments, self._l4_fragments,
            self._l3_fragments, self.fragments,
        ]

        for tag in event_tags:
            if ":" not in tag:
                continue
            cat = tag.split(":")[0]
            # Look for matching fragments in any layer
            for source in all_sources:
                text = source.get(tag, "")
                if isinstance(text, str) and text and text not in seen_texts:
                    selected.append((tag, text))
                    seen_texts.add(text)
                    break  # Found in highest-priority source

        return selected

    def assemble_l4(self, data_block: str = "",
                    event_tags: Optional[List[str]] = None,
                    ) -> "AssembledPrompt":
        """Assemble a Layer 4 prompt for province summarization.

        Aggregates fragments from ALL layers (L2, L3, L4). Higher layers
        see everything below them, giving the LLM full context about
        species, materials, disciplines, etc. referenced in the events.

        Args:
            data_block: XML-formatted Layer 3 + L2 events data.
            event_tags: Optional aggregate tags from input events — used
                        to pull matching entity/context fragments from L2/L3.

        Returns:
            AssembledPrompt with system and user components.
        """
        selected = []

        # L4 core (always)
        core = self.get_l4_fragment("_l4_core")
        if core:
            selected.append(("_l4_core", core))

        # Province summary context fragment
        ctx_key = "l4_context:province_summary"
        ctx_frag = self.get_l4_fragment(ctx_key)
        if ctx_frag:
            selected.append((ctx_key, ctx_frag))

        # Aggregate entity/context fragments from ALL lower layers
        # based on tags present in the input events
        if event_tags:
            tag_frags = self._collect_all_tag_fragments(event_tags)
            selected.extend(tag_frags)

        # Example if available
        example_key = "l4_example:province"
        example_frag = self.get_l4_fragment(example_key)
        if example_frag:
            selected.append((example_key, example_frag))

        # L4 output instruction
        output_text = self.get_l4_fragment("_l4_output")

        # Build system prompt
        system_parts = [text for _, text in selected]
        system = "\n\n".join(system_parts)

        # Build user prompt
        user = data_block
        if output_text:
            user = f"{data_block}\n\n{output_text}" if data_block else output_text

        return AssembledPrompt(
            system=system,
            user=user,
            fragments_used=selected,
            tags=["layer:4", "scope:province"],
            token_estimate=estimate_tokens(system) + estimate_tokens(user),
        )

    # ── Layer 5 Assembly ───────────────────────────────────────────

    def assemble_l5(self, data_block: str = "",
                    event_tags: Optional[List[str]] = None,
                    ) -> "AssembledPrompt":
        """Assemble a Layer 5 prompt for realm summarization.

        Aggregates fragments from ALL lower layers (L2 + L3 + L4 + L5).
        Like Layer 4, the LLM performs a full tag rewrite, so the prompt
        emphasizes producing a complete reordered tag list alongside the
        narrative.

        Args:
            data_block: XML-formatted Layer 4 + L3 events data.
            event_tags: Optional aggregate tags from input events — used
                        to pull matching entity/context fragments from
                        any lower layer.

        Returns:
            AssembledPrompt with system and user components.
        """
        selected = []

        # L5 core (always)
        core = self.get_l5_fragment("_l5_core")
        if core:
            selected.append(("_l5_core", core))

        # Realm summary context fragment
        ctx_key = "l5_context:realm_summary"
        ctx_frag = self.get_l5_fragment(ctx_key)
        if ctx_frag:
            selected.append((ctx_key, ctx_frag))

        # Aggregate entity/context fragments from ALL lower layers
        # based on tags present in the input events
        if event_tags:
            tag_frags = self._collect_all_tag_fragments(event_tags)
            selected.extend(tag_frags)

        # Example if available
        example_key = "l5_example:realm"
        example_frag = self.get_l5_fragment(example_key)
        if example_frag:
            selected.append((example_key, example_frag))

        # L5 output instruction
        output_text = self.get_l5_fragment("_l5_output")

        # Build system prompt
        system_parts = [text for _, text in selected]
        system = "\n\n".join(system_parts)

        # Build user prompt
        user = data_block
        if output_text:
            user = f"{data_block}\n\n{output_text}" if data_block else output_text

        return AssembledPrompt(
            system=system,
            user=user,
            fragments_used=selected,
            tags=["layer:5", "scope:realm"],
            token_estimate=estimate_tokens(system) + estimate_tokens(user),
        )


class AssembledPrompt:
    """The result of assembling a prompt from fragments + data."""

    def __init__(self, system: str, user: str,
                 fragments_used: List[Tuple[str, str]],
                 tags: List[str], token_estimate: int):
        self.system = system
        self.user = user
        self.fragments_used = fragments_used
        self.tags = tags
        self.token_estimate = token_estimate

    def __repr__(self):
        return (f"AssembledPrompt(tags={self.tags}, "
                f"fragments={len(self.fragments_used)}, "
                f"~{self.token_estimate} tokens)")
