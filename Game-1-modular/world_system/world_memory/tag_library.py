"""Tag Library — the 65-category tag taxonomy for the World Memory System.

This is the SINGLE SOURCE OF TRUTH for what tag categories exist,
what values they accept, and which layer unlocks them.

Tags are the primary indexing/retrieval mechanism. Format: "category:value".
Each item carries 5-10 tags. Higher layers inherit + override tags from below.

Key behaviors:
- `significance` is RECREATED at every layer (fresh judgment per scope)
- Key tags (scope, urgency, address) are UPDATED, not blindly inherited
- Tags describe EVENTS, not regions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


@dataclass(frozen=True)
class TagCategory:
    """Definition of a single tag category."""
    category_id: str          # e.g., "domain", "species", "significance"
    values: FrozenSet[str]    # Known values (empty = dynamic/any value accepted)
    layer_unlocked: int       # Which layer this category first becomes available
    is_dynamic: bool = False  # True if values are open-ended (species, resource, etc.)
    is_key_tag: bool = False  # True if this tag gets UPDATED (not just inherited)
    is_recreated: bool = False  # True if RECREATED fresh at each layer (significance)
    description: str = ""


# ══════════════════════════════════════════════════════════════════
# LAYER 1: Factual Dimensions (30 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_1_CATEGORIES = {
    # Identity (5)
    "domain": TagCategory(
        "domain",
        frozenset({"combat", "gathering", "crafting", "exploration", "social",
                   "economy", "progression", "dungeon", "items", "skills"}),
        layer_unlocked=1,
        description="Top-level classification of what this data is about",
    ),
    "action": TagCategory(
        "action",
        frozenset({"kill", "damage_deal", "damage_take", "gather", "deplete",
                   "craft", "invent", "discover", "equip", "unequip", "trade",
                   "buy", "sell", "quest_accept", "quest_complete", "quest_fail",
                   "level_up", "learn", "die", "dodge", "block", "heal", "repair",
                   "move", "fish", "enchant", "place", "use", "consume", "swing"}),
        layer_unlocked=1,
        description="What specifically happened",
    ),
    "metric": TagCategory(
        "metric",
        frozenset({"count", "total", "maximum", "rate", "streak",
                   "duration", "percentage", "current"}),
        layer_unlocked=1,
        description="What kind of number this is",
    ),
    "actor": TagCategory(
        "actor",
        frozenset({"player", "enemy", "npc", "world", "system"}),
        layer_unlocked=1,
        description="Who originated this",
    ),
    "target": TagCategory(
        "target",
        frozenset({"player", "enemy", "npc", "resource", "item", "node", "station"}),
        layer_unlocked=1,
        description="What was acted upon",
    ),

    # Entity (7)
    "species": TagCategory(
        "species", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Enemy/creature type (wolf, goblin, dragon...)",
    ),
    "resource": TagCategory(
        "resource", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Material type (iron, oak, mithril...)",
    ),
    "item": TagCategory(
        "item", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Specific item (iron_sword, health_potion...)",
    ),
    "skill": TagCategory(
        "skill", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Specific skill (fireball, heal, dash...)",
    ),
    "recipe": TagCategory(
        "recipe", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Specific recipe (iron_sword_001...)",
    ),
    "npc": TagCategory(
        "npc", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Specific NPC (tutorial_guide, mysterious_trader...)",
    ),
    "quest": TagCategory(
        "quest", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Specific quest (main_quest_1, gather_herbs...)",
    ),

    # Classification (8)
    "tier": TagCategory(
        "tier",
        frozenset({"1", "2", "3", "4"}),
        layer_unlocked=1,
        description="Power tier",
    ),
    "element": TagCategory(
        "element",
        frozenset({"physical", "fire", "ice", "lightning", "poison",
                   "arcane", "shadow", "holy"}),
        layer_unlocked=1,
        description="Damage/magic element",
    ),
    "quality": TagCategory(
        "quality",
        frozenset({"normal", "fine", "superior", "masterwork", "legendary"}),
        layer_unlocked=1,
        description="Craft output quality",
    ),
    "rarity": TagCategory(
        "rarity",
        frozenset({"common", "uncommon", "rare", "epic", "legendary"}),
        layer_unlocked=1,
        description="Item/drop rarity",
    ),
    "discipline": TagCategory(
        "discipline",
        frozenset({"smithing", "alchemy", "refining", "engineering", "enchanting"}),
        layer_unlocked=1,
        description="Crafting discipline",
    ),
    "material_category": TagCategory(
        "material_category",
        frozenset({"ore", "tree", "stone", "plant", "fish", "gem"}),
        layer_unlocked=1,
        description="Resource category",
    ),
    "item_category": TagCategory(
        "item_category",
        frozenset({"material", "equipment", "consumable", "weapon", "armor",
                   "tool", "device", "potion"}),
        layer_unlocked=1,
        description="Item category",
    ),
    "rank": TagCategory(
        "rank",
        frozenset({"normal", "elite", "boss", "dragon", "unique"}),
        layer_unlocked=1,
        description="Enemy rank",
    ),

    # Combat (4)
    "attack_type": TagCategory(
        "attack_type",
        frozenset({"melee", "ranged", "magic"}),
        layer_unlocked=1,
        description="Attack method",
    ),
    "weapon_type": TagCategory(
        "weapon_type",
        frozenset({"sword", "axe", "bow", "staff", "dagger", "hammer", "spear"}),
        layer_unlocked=1,
        description="Weapon used",
    ),
    "status_effect": TagCategory(
        "status_effect",
        frozenset({"burn", "bleed", "poison", "freeze", "stun",
                   "root", "slow", "shock", "chill"}),
        layer_unlocked=1,
        description="Status effect applied/received",
    ),
    "slot": TagCategory(
        "slot",
        frozenset({"head", "chest", "legs", "feet", "main_hand",
                   "off_hand", "accessory", "ring"}),
        layer_unlocked=1,
        description="Equipment slot",
    ),

    # Context (6)
    "result": TagCategory(
        "result",
        frozenset({"success", "failure", "critical", "perfect",
                   "first_try", "miss", "block", "dodge"}),
        layer_unlocked=1,
        description="Outcome of action",
    ),
    "source": TagCategory(
        "source",
        frozenset({"quest", "enemy", "vendor", "level_up", "book", "crafting",
                   "gathering", "fishing", "dungeon", "trade", "loot"}),
        layer_unlocked=1,
        description="Where reward/exp came from",
    ),
    "tool": TagCategory(
        "tool",
        frozenset({"axe", "pickaxe", "fishing_rod", "hammer"}),
        layer_unlocked=1,
        description="Tool used",
    ),
    "class": TagCategory(
        "class",
        frozenset({"warrior", "ranger", "scholar", "artisan", "scavenger", "adventurer"}),
        layer_unlocked=1,
        description="Player class",
    ),
    "title_tier": TagCategory(
        "title_tier",
        frozenset({"novice", "apprentice", "journeyman", "expert", "master", "special"}),
        layer_unlocked=1,
        description="Title rank tier",
    ),
    "location": TagCategory(
        "location", frozenset(), layer_unlocked=1, is_dynamic=True,
        description="Where it happened (from stat dimension)",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 2: Simple Text Events (6 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_2_CATEGORIES = {
    "nation": TagCategory(
        "nation", frozenset(), layer_unlocked=2, is_dynamic=True,
        is_key_tag=True,
        description="Nation-level geographic address (largest sovereign division)",
    ),
    "region": TagCategory(
        "region", frozenset(), layer_unlocked=2, is_dynamic=True,
        is_key_tag=True,
        description="Region-level geographic address (geographic identity within nation)",
    ),
    "locality": TagCategory(
        "locality", frozenset(), layer_unlocked=2, is_dynamic=True,
        is_key_tag=True,
        description="Precise geographic address (locality level)",
    ),
    "district": TagCategory(
        "district", frozenset(), layer_unlocked=2, is_dynamic=True,
        is_key_tag=True,
        description="District-level geographic address",
    ),
    "province": TagCategory(
        "province", frozenset(), layer_unlocked=2, is_dynamic=True,
        is_key_tag=True,
        description="Province-level geographic address",
    ),
    "biome": TagCategory(
        "biome",
        frozenset({"forest", "dense_thicket", "cave", "deep_cave", "quarry",
                   "rocky_highlands", "wetland", "lake", "river", "flooded_cave",
                   "rocky_forest", "crystal_cavern", "overgrown_ruins",
                   "barren_waste", "cursed_marsh"}),
        layer_unlocked=2,
        description="Chunk biome type (15 types derived from region identity)",
    ),
    "scope": TagCategory(
        "scope",
        frozenset({"chunk", "local", "district", "regional",
                   "cross_regional", "global", "world"}),
        layer_unlocked=2, is_key_tag=True,
        description="Geographic scope of this event — KEY TAG, updated at higher layers",
    ),
    "significance": TagCategory(
        "significance",
        frozenset({"minor", "moderate", "significant", "major", "critical"}),
        layer_unlocked=2, is_recreated=True,
        description="How noteworthy — RECREATED at every layer with fresh judgment",
    ),
    "resource_harvesting": TagCategory(
        "resource_harvesting",
        frozenset({"active", "heavy", "depleted_50", "depleted_75",
                   "depleted_90", "exhausted", "recovering"}),
        layer_unlocked=2,
        description="Factual observation of resource extraction level in an ecosystem. Feeds Layer 3 resource_status.",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 3: Municipality/Local (9 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_3_CATEGORIES = {
    "sentiment": TagCategory(
        "sentiment",
        frozenset({"positive", "negative", "neutral", "dangerous", "fortunate",
                   "prosperous", "declining", "hopeful", "grim"}),
        layer_unlocked=3,
        description="Emotional read of the consolidated event",
    ),
    "alignment": TagCategory(
        "alignment",
        frozenset({"good", "evil", "just", "unjust", "chaotic", "orderly",
                   "natural", "unnatural", "merciful", "cruel"}),
        layer_unlocked=3,
        description="Moral/ethical dimension of the event",
    ),
    "trend": TagCategory(
        "trend",
        frozenset({"increasing", "decreasing", "stable", "volatile",
                   "emerging", "dying", "cyclical", "accelerating"}),
        layer_unlocked=3,
        description="Directional pattern over time",
    ),
    "intensity": TagCategory(
        "intensity",
        frozenset({"light", "moderate", "heavy", "extreme"}),
        layer_unlocked=3,
        description="Magnitude judgment — needs multi-event context",
    ),
    "setting": TagCategory(
        "setting",
        frozenset({"village", "settlement", "wilderness", "dungeon",
                   "underground", "ruins", "crossroads", "market", "camp"}),
        layer_unlocked=3,
        description="Environmental context of event",
    ),
    "terrain": TagCategory(
        "terrain",
        frozenset({"forest", "hills", "cave", "clearing", "path",
                   "rocky", "dense", "water", "plains", "swamp"}),
        layer_unlocked=3,
        description="Physical terrain where event occurred",
    ),
    "population_status": TagCategory(
        "population_status",
        frozenset({"thriving", "declining", "extinct", "migrating",
                   "stable", "recovering"}),
        layer_unlocked=3,
        description="Creature population state from event patterns",
    ),
    "resource_status": TagCategory(
        "resource_status",
        frozenset({"abundant", "steady", "scarce", "critical",
                   "depleted", "recovering"}),
        layer_unlocked=3,
        description="Resource availability from event patterns",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 4: Smaller Region (5 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_4_CATEGORIES = {
    "faction": TagCategory(
        "faction",
        frozenset({"village_guard", "crafters_guild", "forest_wardens",
                   "miners_collective"}),
        layer_unlocked=4,
        description="Which faction this event touches",
    ),
    "urgency_level": TagCategory(
        "urgency_level",
        frozenset({"none", "low", "moderate", "high", "critical", "emergency"}),
        layer_unlocked=4, is_key_tag=True,
        description="How urgent — KEY TAG, updated at higher layers",
    ),
    "event_status": TagCategory(
        "event_status",
        frozenset({"emerging", "developing", "ongoing", "resolving",
                   "resolved", "recurring", "escalating"}),
        layer_unlocked=4,
        description="Lifecycle status of the event pattern",
    ),
    "player_impact": TagCategory(
        "player_impact",
        frozenset({"player_driven", "partially_player", "world_driven", "mixed"}),
        layer_unlocked=4,
        description="Proportion of player vs world causation",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 5: Larger Region / Country (5 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_5_CATEGORIES = {
    "political": TagCategory(
        "political",
        frozenset({"stabilizing", "destabilizing", "neutral", "provocative",
                   "unifying", "divisive"}),
        layer_unlocked=5,
        description="Political dimension of the event",
    ),
    "military": TagCategory(
        "military",
        frozenset({"peaceful", "escalating", "defensive", "offensive",
                   "deterrent", "provocative"}),
        layer_unlocked=5,
        description="Military dimension of the event",
    ),
    "living_impact": TagCategory(
        "living_impact",
        frozenset({"minimal", "noticeable", "significant", "dire",
                   "nightmarish", "beneficial", "transformative"}),
        layer_unlocked=5,
        description="Impact on quality of life",
    ),
    "migration": TagCategory(
        "migration",
        frozenset({"causing_inflow", "causing_outflow", "displacement",
                   "attraction", "neutral"}),
        layer_unlocked=5,
        description="Whether event drives population movement",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 6: Intercountry (5 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_6_CATEGORIES = {
    "relation_effect": TagCategory(
        "relation_effect",
        frozenset({"hostility", "alliance", "friendship", "hatred", "war",
                   "trade_disruption", "cooperation", "indifference"}),
        layer_unlocked=6,
        description="What the event triggers between provinces/factions",
    ),
    "diplomacy": TagCategory(
        "diplomacy",
        frozenset({"treaty", "embargo", "negotiation", "escalation",
                   "de_escalation", "neutral"}),
        layer_unlocked=6,
        description="Diplomatic consequence of the event",
    ),
    "regional_effect": TagCategory(
        "regional_effect",
        frozenset({"unifying", "fragmenting", "isolating", "connecting",
                   "destabilizing", "strengthening"}),
        layer_unlocked=6,
        description="How event affects regional cohesion",
    ),
    "regional_significance": TagCategory(
        "regional_significance",
        frozenset({"negligible", "minor", "notable", "major", "defining"}),
        layer_unlocked=6,
        description="Significance at cross-regional scope (separate from per-layer significance)",
    ),
}

# ══════════════════════════════════════════════════════════════════
# LAYER 7: World Level (5 categories)
# ══════════════════════════════════════════════════════════════════

LAYER_7_CATEGORIES = {
    "world_significance": TagCategory(
        "world_significance",
        frozenset({"negligible", "passing", "notable", "historic", "epochal"}),
        layer_unlocked=7,
        description="Significance at world scale",
    ),
    "narrative_role": TagCategory(
        "narrative_role",
        frozenset({"catalyst", "turning_point", "escalation", "resolution",
                   "echo", "origin", "consequence", "climax"}),
        layer_unlocked=7,
        description="What role this event plays in the world story",
    ),
    "era_effect": TagCategory(
        "era_effect",
        frozenset({"no_effect", "era_continuing", "era_shifting",
                   "era_defining", "era_ending", "era_beginning"}),
        layer_unlocked=7,
        description="Does this event mark or affect a world epoch",
    ),
    "world_theme": TagCategory(
        "world_theme",
        frozenset({"conflict", "discovery", "decline", "growth", "balance",
                   "chaos", "order", "renewal", "stagnation"}),
        layer_unlocked=7,
        description="What thematic thread this event reinforces",
    ),
}


# ══════════════════════════════════════════════════════════════════
# UNIFIED REGISTRY
# ══════════════════════════════════════════════════════════════════

# All categories merged into one dict
ALL_CATEGORIES: Dict[str, TagCategory] = {}
ALL_CATEGORIES.update(LAYER_1_CATEGORIES)
ALL_CATEGORIES.update(LAYER_2_CATEGORIES)
ALL_CATEGORIES.update(LAYER_3_CATEGORIES)
ALL_CATEGORIES.update(LAYER_4_CATEGORIES)
ALL_CATEGORIES.update(LAYER_5_CATEGORIES)
ALL_CATEGORIES.update(LAYER_6_CATEGORIES)
ALL_CATEGORIES.update(LAYER_7_CATEGORIES)

# Note: significance appears in LAYER_2_CATEGORIES but is_recreated=True
# means every layer creates its own. It's listed once in the registry
# but used at every layer.


def get_categories_for_layer(layer: int) -> Dict[str, TagCategory]:
    """Get all tag categories available at a given layer (includes lower layers)."""
    return {k: v for k, v in ALL_CATEGORIES.items() if v.layer_unlocked <= layer}


def get_new_categories_at_layer(layer: int) -> Dict[str, TagCategory]:
    """Get only the categories that UNLOCK at a specific layer."""
    return {k: v for k, v in ALL_CATEGORIES.items() if v.layer_unlocked == layer}


def get_key_tags() -> Dict[str, TagCategory]:
    """Get all key tags that get UPDATED (not just inherited) at higher layers."""
    return {k: v for k, v in ALL_CATEGORIES.items() if v.is_key_tag}


def get_recreated_tags() -> Dict[str, TagCategory]:
    """Get all tags that are RECREATED fresh at each layer."""
    return {k: v for k, v in ALL_CATEGORIES.items() if v.is_recreated}


def validate_tag(tag: str, layer: int) -> bool:
    """Check if a tag string is valid at a given layer.

    Args:
        tag: Tag string in "category:value" format.
        layer: The layer attempting to use this tag.

    Returns:
        True if the tag category is unlocked at this layer and the value
        is either in the known set or the category is dynamic.
    """
    if ":" not in tag:
        return False
    category, value = tag.split(":", 1)
    cat_def = ALL_CATEGORIES.get(category)
    if cat_def is None:
        return False
    if cat_def.layer_unlocked > layer:
        return False
    if cat_def.is_dynamic:
        return True
    return value in cat_def.values


def parse_tag(tag: str) -> Tuple[str, str]:
    """Parse a "category:value" tag into its components."""
    if ":" not in tag:
        return (tag, tag)
    return tuple(tag.split(":", 1))


def format_tag(category: str, value: str) -> str:
    """Create a tag string from category and value."""
    return f"{category}:{value}"


# ══════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════

def get_library_stats() -> Dict[str, int]:
    """Summary statistics about the tag library."""
    by_layer = {}
    for cat in ALL_CATEGORIES.values():
        layer = cat.layer_unlocked
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        "total_categories": len(ALL_CATEGORIES),
        "dynamic_categories": sum(1 for c in ALL_CATEGORIES.values() if c.is_dynamic),
        "key_tags": sum(1 for c in ALL_CATEGORIES.values() if c.is_key_tag),
        "recreated_tags": sum(1 for c in ALL_CATEGORIES.values() if c.is_recreated),
        "categories_by_layer": by_layer,
    }
