#!/usr/bin/env python3
"""
generate_stat_schema.py — Procedurally generate the complete Layer 1 stat key schema.

Reads all JSON game data files and the StatTracker method signatures to produce:
1. A complete list of every possible stat key that could be written
2. SQL DDL for a pre-populated stats table with all known keys
3. A JSON manifest for retrieval system indexing

This ensures the stat schema is known at startup time, enabling:
- Pre-allocated SQL rows (no INSERT on first encounter, just UPDATE)
- Retrieval system can enumerate all possible dimensions without scanning
- Layer 2+ evaluators know exactly what data exists

Usage:
    python tools/generate_stat_schema.py                # Print all keys to stdout
    python tools/generate_stat_schema.py --sql          # Generate SQL INSERT statements
    python tools/generate_stat_schema.py --json         # Output JSON manifest
    python tools/generate_stat_schema.py --count        # Just count keys
    python tools/generate_stat_schema.py --write-json   # Write manifest to world_system/config/stat-key-manifest.json
"""

import json
import glob
import os
import sys
from typing import Any, Dict, List, Set


# ── JSON Loading ─────────────────────────────────────────────────────

def _deep_extract(data: Any, target_keys: List[str]) -> List[dict]:
    """Recursively extract dicts containing any of target_keys from nested structures."""
    results = []
    if isinstance(data, dict):
        if any(tk in data for tk in target_keys):
            results.append(data)
        for v in data.values():
            if isinstance(v, (dict, list)):
                results.extend(_deep_extract(v, target_keys))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if any(tk in item for tk in target_keys):
                    results.append(item)
                else:
                    results.extend(_deep_extract(item, target_keys))
            elif isinstance(item, list):
                results.extend(_deep_extract(item, target_keys))
    return results


def _safe_key(value: Any) -> str:
    """Match stat_store._safe_key exactly."""
    s = str(value).lower().strip()
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


def find_project_root() -> str:
    """Find Game-1-modular root."""
    for d in [os.path.dirname(os.path.abspath(__file__)),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')]:
        if os.path.exists(os.path.join(d, 'main.py')) and os.path.exists(os.path.join(d, 'entities')):
            return d
    # Try parent directories
    d = os.path.dirname(os.path.abspath(__file__))
    while d != '/':
        if os.path.exists(os.path.join(d, 'main.py')) and os.path.exists(os.path.join(d, 'entities')):
            return d
        d = os.path.dirname(d)
    return '.'


# ── Game Data Extraction ─────────────────────────────────────────────

class GameData:
    """All game entity IDs extracted from JSON files."""

    def __init__(self, root: str):
        self.root = root
        self.items: List[str] = []
        self.item_categories: List[str] = []
        self.item_tiers: List[int] = [1, 2, 3, 4]
        self.equipment_types: List[str] = []
        self.enemies: List[dict] = []  # {id, tier, rank}
        self.enemy_base_ids: List[str] = []
        self.skills: List[str] = []
        self.recipes: List[str] = []
        self.disciplines: List[str] = ['smithing', 'alchemy', 'refining', 'engineering',
                                        'enchanting', 'fishing', 'adornments']
        self.classes: List[str] = []
        self.titles: List[str] = []
        self.title_tiers: List[str] = ['novice', 'apprentice', 'journeyman', 'expert', 'master']
        self.npcs: List[str] = []
        self.quests: List[str] = []
        self.quest_types: List[str] = []
        self.enchantments: List[str] = []
        self.resource_nodes: List[str] = []
        self.resource_categories: List[str] = []
        self.damage_types: List[str] = ['physical', 'fire', 'ice', 'lightning', 'poison',
                                         'arcane', 'shadow', 'holy']
        self.status_effects: List[str] = ['burn', 'bleed', 'poison', 'freeze', 'chill',
                                           'stun', 'root', 'shock', 'weaken', 'vulnerable']
        self.rarity_tiers: List[str] = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        self.attack_types: List[str] = ['melee', 'ranged', 'magic']
        self.tool_types: List[str] = ['axe', 'pickaxe', 'fishing_rod', 'weapon', 'armor',
                                       'accessory', 'shield', 'tool']
        self.biomes: List[str] = []
        self.regions: List[str] = []

        self._load_all()

    def _load_json(self, pattern: str) -> List[dict]:
        items = []
        for f in sorted(glob.glob(os.path.join(self.root, pattern))):
            try:
                data = json.load(open(f))
                items.extend(_deep_extract(data, [
                    'materialId', 'itemId', 'enemyId', 'skillId', 'recipeId',
                    'titleId', 'classId', 'npc_id', 'npcId', 'questId',
                    'resourceId', 'nodeId', 'abilityId', 'enchantmentId'
                ]))
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return items

    def _load_all(self):
        # Items & materials
        item_ids = set()
        cats = set()
        etypes = set()
        for item in self._load_json('items.JSON/*.JSON') + self._load_json('items.JSON/*.json'):
            mid = item.get('materialId', item.get('itemId', ''))
            if mid:
                item_ids.add(mid)
            cat = item.get('category', '')
            if cat:
                cats.add(cat)
            etype = item.get('type', item.get('equipmentType', ''))
            if etype:
                etypes.add(etype)
        self.items = sorted(item_ids)
        self.item_categories = sorted(cats)
        self.equipment_types = sorted(etypes)

        # Enemies
        enemy_set = set()
        for e in self._load_json('Definitions.JSON/hostiles*.JSON'):
            if 'enemyId' in e:
                eid = e['enemyId']
                enemy_set.add(eid)
                # Base ID (strip trailing numbers)
                base = eid.rstrip("0123456789").rstrip("_")
                self.enemies.append({'id': eid, 'tier': e.get('tier', 1),
                                     'rank': e.get('rank', 'normal'), 'base': base})
        self.enemy_base_ids = sorted(set(e['base'] for e in self.enemies))

        # Skills
        for s in self._load_json('Skills/*.JSON') + self._load_json('Skills/*.json'):
            if 'skillId' in s:
                self.skills.append(s['skillId'])
        self.skills = sorted(set(self.skills))

        # Recipes
        for r in (self._load_json('recipes.JSON/*.JSON') + self._load_json('recipes.JSON/*.json')):
            if 'recipeId' in r:
                self.recipes.append(r['recipeId'])
        self.recipes = sorted(set(self.recipes))

        # Classes
        for c in self._load_json('progression/classes*.JSON'):
            if 'classId' in c:
                self.classes.append(c['classId'])
        self.classes = sorted(set(self.classes))

        # Titles
        for t in self._load_json('progression/titles*.JSON'):
            if 'titleId' in t:
                self.titles.append(t['titleId'])
        self.titles = sorted(set(self.titles))

        # NPCs
        for n in self._load_json('progression/npcs*.JSON'):
            nid = n.get('npc_id', n.get('npcId', ''))
            if nid:
                self.npcs.append(nid)
        self.npcs = sorted(set(self.npcs))

        # Quests
        qtypes = set()
        for q in self._load_json('progression/quests*.JSON'):
            if 'questId' in q:
                self.quests.append(q['questId'])
                obj = q.get('objectives', {})
                if isinstance(obj, dict) and 'objectiveType' in obj:
                    qtypes.add(obj['objectiveType'])
        self.quests = sorted(set(self.quests))
        self.quest_types = sorted(qtypes) or ['kill', 'gather', 'craft', 'explore', 'talk']

        # Enchantments
        ench = set()
        for r in (self._load_json('recipes.JSON/*adornment*') +
                  self._load_json('recipes.JSON/*enchant*')):
            if 'recipeId' in r:
                ench.add(r['recipeId'])
        self.enchantments = sorted(ench)

        # Resource nodes
        res_ids = set()
        res_cats = set()
        for n in self._load_json('Definitions.JSON/resource-node*.JSON'):
            rid = n.get('resourceId', '')
            if rid:
                res_ids.add(rid)
            cat = n.get('category', '')
            if cat:
                res_cats.add(cat)
        self.resource_nodes = sorted(res_ids)
        self.resource_categories = sorted(res_cats)

        # Biomes/regions
        geo_path = os.path.join(self.root, 'world_system', 'config', 'geographic-map.json')
        if os.path.exists(geo_path):
            geo = json.load(open(geo_path))
            biomes = set()
            regions = set()

            def _walk(node):
                if isinstance(node, dict):
                    if 'biome_primary' in node:
                        biomes.add(node['biome_primary'])
                    if 'region_id' in node:
                        regions.add(node['region_id'])
                    for v in node.values():
                        _walk(v)
                elif isinstance(node, list):
                    for item in node:
                        _walk(item)

            _walk(geo)
            self.biomes = sorted(biomes)
            self.regions = sorted(regions)

        # Update content
        for item in (self._load_json('Update-*/*.JSON') + self._load_json('Update-*/*.json')):
            mid = item.get('materialId', item.get('itemId', ''))
            if mid and mid not in self.items:
                self.items.append(mid)
                self.items.sort()
            if 'skillId' in item and item['skillId'] not in self.skills:
                self.skills.append(item['skillId'])
                self.skills.sort()
            if 'titleId' in item and item['titleId'] not in self.titles:
                self.titles.append(item['titleId'])
                self.titles.sort()


# ── Key Generation ───────────────────────────────────────────────────

def generate_all_keys(gd: GameData) -> List[str]:
    """Generate every possible stat key from game data + StatTracker method signatures."""
    keys: Set[str] = set()

    def add(base: str, dims: Dict[str, List[str]] = None):
        """Add base key + all dimensional expansions."""
        keys.add(base)
        if dims:
            for dim_name, dim_values in dims.items():
                for val in dim_values:
                    keys.add(f"{base}.{dim_name}.{_safe_key(val)}")

    # ── GATHERING ────────────────────────────────────────────────
    gathering_dims = {
        "resource": gd.items,
        "tier": [str(t) for t in gd.item_tiers],
        "category": gd.item_categories + gd.resource_categories,
        "element": gd.damage_types,
        "location": gd.regions,
    }
    add("gathering.collected", gathering_dims)
    add("gathering.actions", gathering_dims)
    add("gathering.critical")
    add("gathering.rare_drops")
    add("gathering.longest_streak")
    add("gathering.damage_dealt")

    # Fishing
    fish_ids = [i for i in gd.items if 'fish' in i.lower() or any(
        i.startswith(p) for p in ['carp', 'sunfish', 'minnow', 'stormfin', 'frostback',
                                   'lighteye', 'shadowgill', 'phoenixkoi', 'voidswimmer',
                                   'tempesteel', 'leviathan', 'chaosscale'])]
    add("gathering.fishing.caught", {
        "fish": fish_ids or gd.items[:20],
        "tier": [str(t) for t in gd.item_tiers],
        "rarity": gd.rarity_tiers,
    })
    add("gathering.fishing.largest")
    add("gathering.fishing.longest_streak")
    add("gathering.fishing.rare")
    add("gathering.fishing.legendary")
    add("gathering.fishing.failed")

    # Tools
    for tt in gd.tool_types:
        keys.add(f"gathering.tool_swings.{_safe_key(tt)}")
        keys.add(f"gathering.tool_durability_lost.{_safe_key(tt)}")
        keys.add(f"gathering.tools_broken.{_safe_key(tt)}")
        keys.add(f"gathering.tools_repaired.{_safe_key(tt)}")
    add("gathering.tool_swings")
    add("gathering.tools_broken")
    add("gathering.tools_repaired")

    # Node depletion
    for rt in gd.resource_nodes + gd.items[:30]:
        keys.add(f"gathering.nodes_depleted.{_safe_key(rt)}")
    for loc in gd.regions:
        keys.add(f"gathering.nodes_depleted.location.{_safe_key(loc)}")
    add("gathering.nodes_depleted")

    # ── CRAFTING ─────────────────────────────────────────────────
    craft_attempt_dims = {
        "discipline": gd.disciplines,
        "tier": [str(t) for t in gd.item_tiers],
        "result": ["success", "failure"],
    }
    add("crafting.attempts", craft_attempt_dims)

    craft_success_dims = {
        "discipline": gd.disciplines,
        "tier": [str(t) for t in gd.item_tiers],
        "rarity": gd.rarity_tiers,
        "recipe": gd.recipes,
    }
    add("crafting.success", craft_success_dims)

    for d in gd.disciplines:
        keys.add(f"crafting.quality.{_safe_key(d)}")
        keys.add(f"crafting.time.{_safe_key(d)}")
        keys.add(f"crafting.perfect.{_safe_key(d)}")
        keys.add(f"crafting.first_try.{_safe_key(d)}")
        keys.add(f"crafting.inventions.{_safe_key(d)}")
        keys.add(f"crafting.recipes_discovered.{_safe_key(d)}")
    add("crafting.quality")
    add("crafting.perfect")
    add("crafting.first_try")
    add("crafting.longest_first_try_streak")
    add("crafting.inventions")
    add("crafting.recipes_discovered")

    for r in gd.rarity_tiers:
        keys.add(f"crafting.rarity.{_safe_key(r)}")

    for mat in gd.items:
        keys.add(f"crafting.materials.{_safe_key(mat)}")
    add("crafting.materials_consumed")

    for ench in gd.enchantments:
        keys.add(f"crafting.enchantments.{_safe_key(ench)}")
    add("crafting.enchantments")

    # ── COMBAT ───────────────────────────────────────────────────
    combat_dmg_dims = {
        "type": gd.damage_types,
        "attack": gd.attack_types,
        "weapon_element": gd.damage_types,
        "to": gd.enemy_base_ids,
        "location": gd.regions,
    }
    add("combat.damage_dealt", combat_dmg_dims)
    add("combat.damage_dealt.critical")
    add("combat.critical_hits")

    combat_taken_dims = {
        "type": gd.damage_types,
        "attack": gd.attack_types,
        "from": gd.enemy_base_ids,
        "location": gd.regions,
    }
    add("combat.damage_taken", combat_taken_dims)

    combat_kill_dims = {
        "tier": [str(t) for t in gd.item_tiers],
        "species": gd.enemy_base_ids,
        "rank": ["normal", "elite", "boss", "miniboss"],
        "weapon_element": gd.damage_types,
        "location": gd.regions,
    }
    add("combat.kills", combat_kill_dims)
    add("combat.longest_killstreak")
    add("combat.longest_no_damage_streak")

    # Status effects
    for effect in gd.status_effects:
        keys.add(f"combat.status.applied.{_safe_key(effect)}")
        keys.add(f"combat.status.received.{_safe_key(effect)}")
    add("combat.status.applied")
    add("combat.status.received")

    # Deaths
    add("combat.deaths")
    add("combat.deaths.items_lost")
    add("combat.deaths.soulbound_kept")
    for src in ['enemy', 'environment', 'poison', 'fall']:
        keys.add(f"combat.deaths.source.{src}")
    for dt in gd.damage_types:
        keys.add(f"combat.deaths.element.{_safe_key(dt)}")
    for eid in gd.enemy_base_ids:
        keys.add(f"combat.deaths.by.{_safe_key(eid)}")
    for loc in gd.regions:
        keys.add(f"combat.deaths.location.{_safe_key(loc)}")

    # Other combat
    add("combat.blocks")
    add("combat.dodge_rolls")
    add("combat.dodge_rolls.successful")
    add("combat.combos")
    add("combat.projectiles.fired")
    add("combat.projectiles.hit")
    add("combat.healing")
    add("combat.reflect")
    add("combat.damage_blocked")
    add("combat.attacks")

    for src in ['lifesteal', 'potion', 'regen', 'heal_on_kill', 'skill']:
        keys.add(f"combat.healing.{src}")
    for src in ['thorns', 'reflect_enchant']:
        keys.add(f"combat.reflect.{src}")
    for bt in ['armor', 'shield', 'skill']:
        keys.add(f"combat.damage_blocked.{bt}")
        keys.add(f"combat.blocks.{bt}")
    for wt in gd.equipment_types:
        keys.add(f"combat.attacks.weapon_type.{_safe_key(wt)}")

    # ── ITEMS ────────────────────────────────────────────────────
    item_collect_dims = {
        "item": gd.items,
        "category": gd.item_categories,
        "rarity": gd.rarity_tiers,
    }
    add("items.collected", item_collect_dims)
    add("items.first_discoveries")
    add("items.rare_drops")

    item_use_dims = {
        "item": gd.items[:50],  # Mostly consumables
        "type": ["consumable", "potion", "food", "scroll"],
        "context": ["combat", "exploration", "menu"],
    }
    add("items.used", item_use_dims)

    for iid in gd.items[:50]:
        keys.add(f"items.dropped.{_safe_key(iid)}")
        keys.add(f"items.destroyed.{_safe_key(iid)}")
    add("items.dropped")
    add("items.destroyed")

    for iid in gd.items[:50]:
        keys.add(f"items.equipped.{_safe_key(iid)}")
        keys.add(f"items.unequipped.{_safe_key(iid)}")
    for slot in ['mainHand', 'offHand', 'head', 'chest', 'legs', 'feet', 'axe', 'pickaxe']:
        keys.add(f"items.equipped.slot.{_safe_key(slot)}")
        keys.add(f"items.unequipped.slot.{_safe_key(slot)}")
    add("items.equipped")
    add("items.unequipped")
    add("items.equipment_swaps")

    for iid in gd.items[:50]:
        keys.add(f"items.repaired.{_safe_key(iid)}")
    add("items.repaired")
    add("items.durability_restored")

    # Barriers
    for mat in gd.items:
        if 'stone' in mat or 'rock' in mat or 'granite' in mat or 'limestone' in mat:
            keys.add(f"barriers.placed.{_safe_key(mat)}")
            keys.add(f"barriers.picked_up.{_safe_key(mat)}")
    add("barriers.placed")
    add("barriers.picked_up")

    # ── SKILLS ───────────────────────────────────────────────────
    skill_dims = {
        "skill": gd.skills,
        "category": ["combat", "utility", "buff", "heal", "movement"],
    }
    add("skills.used", skill_dims)
    add("skills.mana_spent")
    for sid in gd.skills:
        keys.add(f"skills.mana_spent.{_safe_key(sid)}")
    add("skills.targets_affected")

    # ── EXPLORATION ──────────────────────────────────────────────
    add("exploration.distance")
    add("exploration.distance.sprinting")
    add("exploration.distance.encumbered")
    add("exploration.unique_chunks")
    add("exploration.chunk_entries")
    add("exploration.new_discoveries")
    for biome in gd.biomes:
        keys.add(f"exploration.chunks.biome.{_safe_key(biome)}")
    for lt in ['waypoint', 'dungeon_entrance', 'npc', 'resource_rich']:
        keys.add(f"exploration.landmarks.{lt}")
    add("exploration.landmarks")

    # ── ECONOMY ──────────────────────────────────────────────────
    for src in ['quest', 'loot', 'trade', 'sell']:
        keys.add(f"economy.gold_earned.{src}")
    add("economy.gold_earned")
    for sink in ['skill_unlock', 'trade', 'buy', 'repair']:
        keys.add(f"economy.gold_spent.{sink}")
    add("economy.gold_spent")
    for tt in ['buy', 'sell']:
        keys.add(f"economy.trades.{tt}")
        keys.add(f"economy.trades.{tt}.value")
    add("economy.trades")

    # ── PROGRESSION ──────────────────────────────────────────────
    add("progression.level_ups")
    add("progression.current_level")
    add("progression.stat_points_earned")
    for src in ['combat', 'quest', 'crafting', 'gathering', 'exploration', 'dungeon']:
        keys.add(f"progression.exp.{src}")
    add("progression.exp")

    for tid in gd.titles:
        keys.add(f"progression.titles.{_safe_key(tid)}")
    for tier in gd.title_tiers:
        keys.add(f"progression.titles.tier.{_safe_key(tier)}")
    add("progression.titles")

    for cid in gd.classes:
        keys.add(f"progression.class_changes.{_safe_key(cid)}")
    add("progression.class_changes")

    for src in ['level', 'system', 'quest', 'unlock']:
        keys.add(f"progression.skills_learned.{src}")
    for sid in gd.skills:
        keys.add(f"progression.skills_learned.{_safe_key(sid)}")
    add("progression.skills_learned")

    # ── DUNGEONS ─────────────────────────────────────────────────
    for rarity in gd.rarity_tiers:
        keys.add(f"dungeon.entered.{_safe_key(rarity)}")
        keys.add(f"dungeon.completed.{_safe_key(rarity)}")
        keys.add(f"dungeon.clear_time.{_safe_key(rarity)}")
    add("dungeon.entered")
    add("dungeon.completed")
    add("dungeon.enemies_killed_in_run")
    add("dungeon.exp_earned")
    add("dungeon.abandoned")
    add("dungeon.enemies_killed")
    add("dungeon.waves_completed")
    add("dungeon.deaths")
    add("dungeon.chests_opened")
    add("dungeon.items_received")

    # ── SOCIAL ───────────────────────────────────────────────────
    for nid in gd.npcs:
        keys.add(f"social.npc.{_safe_key(nid)}")
    add("social.npc_interactions")

    for qt in gd.quest_types:
        keys.add(f"social.quests.accepted.{_safe_key(qt)}")
        keys.add(f"social.quests.completed.{_safe_key(qt)}")
        keys.add(f"social.quests.failed.{_safe_key(qt)}")
    add("social.quests.accepted")
    add("social.quests.completed")
    add("social.quests.failed")
    add("social.quests.exp_earned")
    add("social.quests.gold_earned")

    # ── TIME ─────────────────────────────────────────────────────
    for act in ['combat', 'crafting', 'exploration', 'gathering', 'menu', 'dungeon']:
        keys.add(f"time.activity.{act}")
    add("time.activity")
    add("time.sessions.duration")
    add("time.total_playtime")
    for mt in ['stats', 'equipment', 'skills', 'encyclopedia', 'map', 'crafting', 'inventory']:
        keys.add(f"time.menu.{mt}")
    add("time.menu")
    add("time.idle")

    # ── RECORDS ──────────────────────────────────────────────────
    add("records.combat_duration")
    for rt in gd.resource_nodes[:10]:
        keys.add(f"records.fastest_gather.{_safe_key(rt)}")

    # ── ENCYCLOPEDIA ─────────────────────────────────────────────
    for cat in ['material', 'enemy', 'recipe', 'equipment', 'skill']:
        keys.add(f"encyclopedia.discovered.{cat}")
        keys.add(f"encyclopedia.completion.{cat}")
    add("encyclopedia.discovered")

    # ── MISC ─────────────────────────────────────────────────────
    for mt in ['stats', 'equipment', 'skills', 'encyclopedia', 'map', 'crafting', 'inventory']:
        keys.add(f"misc.menu_opened.{mt}")
    add("misc.menu_opened")
    for st in ['manual', 'autosave', 'quick']:
        keys.add(f"misc.saves.{st}")
    add("misc.saves")
    add("misc.game_loads")
    for da in ['f1_infinite_resources', 'f2_learn_all_skills', 'f3_grant_all_titles',
               'f4_max_level_stats', 'f5_keep_inventory_on', 'f5_keep_inventory_off',
               'f7_infinite_durability_on', 'f7_infinite_durability_off']:
        keys.add(f"misc.debug.{da}")
    add("misc.debug")
    add("session.started")

    return sorted(keys)


# ── Output Formatters ────────────────────────────────────────────────

def print_keys(keys: List[str]):
    """Print all keys grouped by top-level category."""
    current_cat = ""
    for key in keys:
        cat = key.split('.')[0]
        if cat != current_cat:
            if current_cat:
                print()
            print(f"── {cat.upper()} ──")
            current_cat = cat
        print(f"  {key}")
    print(f"\nTotal: {len(keys)} stat keys")


def print_sql(keys: List[str]):
    """Generate SQL INSERT statements for pre-populating the stats table."""
    print("-- Pre-populate stats table with all known keys")
    print("-- Generated by generate_stat_schema.py")
    print(f"-- Total keys: {len(keys)}")
    print()
    print("BEGIN TRANSACTION;")
    print()
    for key in keys:
        print(f"INSERT OR IGNORE INTO stats (key, count, total, max_value, updated_at) "
              f"VALUES ('{key}', 0, 0.0, 0.0, 0.0);")
    print()
    print("COMMIT;")
    print(f"\n-- {len(keys)} rows inserted")


def print_json_manifest(keys: List[str], gd: GameData):
    """Generate JSON manifest for retrieval system."""
    # Group by top-level and second-level categories
    categories = {}
    for key in keys:
        parts = key.split('.')
        cat = parts[0]
        subcat = parts[1] if len(parts) > 1 else '_root'
        categories.setdefault(cat, {}).setdefault(subcat, []).append(key)

    manifest = {
        "_meta": {
            "description": "Layer 1 stat key manifest — all possible keys from game data",
            "total_keys": len(keys),
            "generated_from": "tools/generate_stat_schema.py",
            "game_data_counts": {
                "items": len(gd.items),
                "enemies": len(gd.enemy_base_ids),
                "skills": len(gd.skills),
                "recipes": len(gd.recipes),
                "enchantments": len(gd.enchantments),
                "classes": len(gd.classes),
                "titles": len(gd.titles),
                "npcs": len(gd.npcs),
                "regions": len(gd.regions),
                "biomes": len(gd.biomes),
            },
        },
        "categories": {cat: {
            "subcategories": list(subs.keys()),
            "key_count": sum(len(v) for v in subs.values()),
        } for cat, subs in categories.items()},
        "keys": keys,
    }
    print(json.dumps(manifest, indent=2))


def write_manifest(keys: List[str], gd: GameData, root: str):
    """Write manifest to world_system/config/stat-key-manifest.json."""
    categories = {}
    for key in keys:
        parts = key.split('.')
        cat = parts[0]
        categories.setdefault(cat, []).append(key)

    manifest = {
        "_meta": {
            "description": "Layer 1 stat key manifest — all possible keys from game data",
            "total_keys": len(keys),
            "generated_by": "tools/generate_stat_schema.py",
            "regenerate": "python tools/generate_stat_schema.py --write-json",
        },
        "game_entities": {
            "items": len(gd.items),
            "enemies": len(gd.enemy_base_ids),
            "skills": len(gd.skills),
            "recipes": len(gd.recipes),
            "disciplines": gd.disciplines,
            "enchantments": len(gd.enchantments),
            "classes": gd.classes,
            "titles": len(gd.titles),
            "npcs": gd.npcs,
            "regions": gd.regions,
            "biomes": gd.biomes,
            "damage_types": gd.damage_types,
            "status_effects": gd.status_effects,
        },
        "category_counts": {cat: len(ks) for cat, ks in categories.items()},
        "keys": keys,
    }

    out_path = os.path.join(root, 'world_system', 'config', 'stat-key-manifest.json')
    with open(out_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {len(keys)} keys to {out_path}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    root = find_project_root()
    args = sys.argv[1:]

    gd = GameData(root)
    keys = generate_all_keys(gd)

    if '--sql' in args:
        print_sql(keys)
    elif '--json' in args:
        print_json_manifest(keys, gd)
    elif '--count' in args:
        print(f"Total stat keys: {len(keys)}")
        cats = {}
        for k in keys:
            cat = k.split('.')[0]
            cats[cat] = cats.get(cat, 0) + 1
        for cat, count in sorted(cats.items()):
            print(f"  {cat:20s}: {count:,}")
    elif '--write-json' in args:
        write_manifest(keys, gd, root)
    else:
        print_keys(keys)


if __name__ == '__main__':
    main()
