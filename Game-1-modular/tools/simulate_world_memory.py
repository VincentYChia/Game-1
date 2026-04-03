#!/usr/bin/env python3
"""
simulate_world_memory.py — Build a realistic WMS simulation database.

Creates a SQLite database populated with:
- Layer 1: 500 stat rows with realistic play-session values
- Raw Event Pipeline: ~200 events from a simulated play session
- Layer 2: Evaluator outputs triggered by threshold hits
- Layers 3-7: Cascaded consolidations following design doc rules

Usage:
    python tools/simulate_world_memory.py              # Build sim.db
    python tools/simulate_world_memory.py --dump       # Build + dump contents
    python tools/simulate_world_memory.py --stats      # Summary only
"""

import json
import math
import os
import random
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Constants from design doc ────────────────────────────────────────

THRESHOLDS = [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000]
THRESHOLD_SET = set(THRESHOLDS)

EVENT_CATEGORIES = {
    "attack_performed": "combat",
    "damage_taken": "combat",
    "enemy_killed": "combat",
    "player_death": "combat",
    "dodge_performed": "combat",
    "status_applied": "combat",
    "resource_gathered": "gathering",
    "node_depleted": "gathering",
    "craft_attempted": "crafting",
    "item_invented": "crafting",
    "recipe_discovered": "crafting",
    "item_acquired": "economy",
    "item_equipped": "economy",
    "repair_performed": "economy",
    "level_up": "progression",
    "skill_learned": "progression",
    "skill_used": "progression",
    "title_earned": "progression",
    "class_changed": "progression",
    "chunk_entered": "exploration",
    "area_discovered": "exploration",
    "npc_interaction": "social",
    "quest_accepted": "social",
    "quest_completed": "social",
    "quest_failed": "social",
}

SEVERITY_LEVELS = ["minor", "moderate", "significant", "major", "critical"]

# ── Geographic data (from geographic-map.json) ───────────────────────

REGIONS = {
    "spawn_crossroads": {"district": "whispering_woods", "province": "northwestern_reaches", "biome": "peaceful_forest"},
    "south_clearing": {"district": "whispering_woods", "province": "northwestern_reaches", "biome": "peaceful_forest"},
    "elder_grove": {"district": "whispering_woods", "province": "northwestern_reaches", "biome": "forest"},
    "traders_corner": {"district": "iron_hills", "province": "northeastern_highlands", "biome": "peaceful_quarry"},
    "east_path": {"district": "iron_hills", "province": "northeastern_highlands", "biome": "quarry"},
    "deep_caverns": {"district": "iron_hills", "province": "northeastern_highlands", "biome": "cave"},
}

# ── Game entities (from JSON data) ───────────────────────────────────

ENEMIES = [
    {"id": "wolf_grey", "tier": 1, "rank": "normal"},
    {"id": "wolf_dire", "tier": 2, "rank": "normal"},
    {"id": "wolf_elder", "tier": 3, "rank": "elite"},
    {"id": "slime_green", "tier": 1, "rank": "normal"},
    {"id": "slime_acid", "tier": 2, "rank": "normal"},
    {"id": "beetle_brown", "tier": 1, "rank": "normal"},
    {"id": "beetle_armored", "tier": 2, "rank": "normal"},
    {"id": "golem_stone", "tier": 3, "rank": "elite"},
    {"id": "golem_crystal", "tier": 4, "rank": "boss"},
]

RESOURCES = [
    "copper_ore", "iron_ore", "tin_ore", "oak_log", "pine_log",
    "ash_log", "limestone", "granite", "basalt", "steel_ore",
    "mithril_ore", "birch_log", "maple_log", "marble", "quartz",
]

MATERIALS_BY_TIER = {
    1: ["copper_ore", "iron_ore", "tin_ore", "oak_log", "pine_log", "limestone", "granite"],
    2: ["steel_ore", "ash_log", "birch_log", "maple_log", "basalt", "marble", "quartz"],
    3: ["mithril_ore", "adamantine_ore", "ironwood_log", "obsidian"],
    4: ["orichalcum_ore", "etherion_ore", "voidstone"],
}

DISCIPLINES = ["smithing", "alchemy", "refining", "engineering", "enchanting", "fishing"]

SKILLS = ["combat_strike", "fireball", "heal", "shield_bash", "chain_lightning",
          "battle_fury", "arctic_cone", "shadow_step", "nature_ward", "bountiful_harvest"]

DAMAGE_TYPES = ["physical", "fire", "ice", "lightning", "poison"]

STATUS_EFFECTS = ["burn", "bleed", "poison", "freeze", "stun", "slow"]


def find_project_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    while d != '/':
        if os.path.exists(os.path.join(d, 'main.py')) and os.path.exists(os.path.join(d, 'entities')):
            return d
        d = os.path.dirname(d)
    return '.'


def _uid() -> str:
    return str(uuid.uuid4())[:12]


def _safe_key(value: Any) -> str:
    s = str(value).lower().strip()
    return s.replace(" ", "_").replace("-", "_").replace(".", "_")


# ══════════════════════════════════════════════════════════════════════
# DATABASE CREATION — mirrors actual event_store.py + layer_store.py + stat_store.py schemas
# ══════════════════════════════════════════════════════════════════════

def create_database(db_path: str) -> sqlite3.Connection:
    """Create simulation database with all WMS tables."""
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
    -- Layer 1: Stats (from stat_store.py)
    CREATE TABLE IF NOT EXISTS stats (
        key TEXT PRIMARY KEY,
        count INTEGER DEFAULT 0,
        total REAL DEFAULT 0.0,
        max_value REAL DEFAULT 0.0,
        updated_at REAL DEFAULT 0.0
    );

    -- Raw Event Pipeline (from event_store.py)
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        event_subtype TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        actor_type TEXT NOT NULL,
        target_id TEXT,
        target_type TEXT,
        position_x REAL NOT NULL,
        position_y REAL NOT NULL,
        chunk_x INTEGER NOT NULL,
        chunk_y INTEGER NOT NULL,
        locality_id TEXT,
        district_id TEXT,
        province_id TEXT,
        biome TEXT,
        game_time REAL NOT NULL,
        real_time REAL NOT NULL,
        session_id TEXT,
        magnitude REAL DEFAULT 0.0,
        result TEXT DEFAULT 'success',
        quality TEXT,
        tier INTEGER,
        context_json TEXT DEFAULT '{}',
        interpretation_count INTEGER DEFAULT 0,
        triggered_interpretation INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
    CREATE INDEX IF NOT EXISTS idx_events_time ON events(game_time);
    CREATE INDEX IF NOT EXISTS idx_events_locality ON events(locality_id);

    CREATE TABLE IF NOT EXISTS event_tags (
        event_id TEXT NOT NULL,
        tag TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);

    -- Occurrence counters (threshold tracking)
    CREATE TABLE IF NOT EXISTS occurrence_counts (
        actor_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_subtype TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (actor_id, event_type, event_subtype)
    );

    -- Regional counters (Track 2)
    CREATE TABLE IF NOT EXISTS regional_counters (
        region_id TEXT NOT NULL,
        event_category TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (region_id, event_category)
    );

    -- Layer 2: Interpretations (from event_store.py)
    CREATE TABLE IF NOT EXISTS interpretations (
        interpretation_id TEXT PRIMARY KEY,
        created_at REAL NOT NULL,
        narrative TEXT NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        trigger_event_id TEXT,
        trigger_count INTEGER,
        cause_event_ids_json TEXT DEFAULT '[]',
        affected_locality_ids_json TEXT DEFAULT '[]',
        affected_district_ids_json TEXT DEFAULT '[]',
        epicenter_x REAL,
        epicenter_y REAL,
        affects_tags_json TEXT DEFAULT '[]',
        is_ongoing INTEGER DEFAULT 0,
        update_count INTEGER DEFAULT 1,
        archived INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_interp_category ON interpretations(category);

    CREATE TABLE IF NOT EXISTS interpretation_tags (
        interpretation_id TEXT NOT NULL,
        tag TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_interp_tags_tag ON interpretation_tags(tag);

    -- Layer 3: Connected Interpretations (from event_store.py)
    CREATE TABLE IF NOT EXISTS connected_interpretations (
        id TEXT PRIMARY KEY,
        created_at REAL NOT NULL,
        narrative TEXT NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        source_interpretation_ids_json TEXT DEFAULT '[]',
        affected_district_ids_json TEXT DEFAULT '[]',
        affects_tags_json TEXT DEFAULT '[]',
        is_ongoing INTEGER DEFAULT 0,
        archived INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS connected_interpretation_tags (
        id TEXT NOT NULL,
        tag TEXT NOT NULL
    );

    -- Layer 4: Province Summaries (from event_store.py)
    CREATE TABLE IF NOT EXISTS province_summaries (
        province_id TEXT PRIMARY KEY,
        summary_text TEXT DEFAULT '',
        dominant_activities_json TEXT DEFAULT '[]',
        notable_event_ids_json TEXT DEFAULT '[]',
        resource_state_json TEXT DEFAULT '{}',
        threat_level TEXT DEFAULT 'low',
        last_updated REAL DEFAULT 0.0
    );

    -- Layer 5: Realm State (from event_store.py)
    CREATE TABLE IF NOT EXISTS realm_state (
        realm_id TEXT PRIMARY KEY,
        faction_standings_json TEXT DEFAULT '{}',
        economic_summary TEXT DEFAULT '',
        player_reputation TEXT DEFAULT '',
        major_events_json TEXT DEFAULT '[]',
        last_updated REAL DEFAULT 0.0
    );

    -- Layer 6-7: World Narrative (from event_store.py)
    CREATE TABLE IF NOT EXISTS world_narrative (
        id TEXT PRIMARY KEY DEFAULT 'singleton',
        world_themes_json TEXT DEFAULT '[]',
        world_epoch TEXT DEFAULT 'unknown',
        active_thread_ids_json TEXT DEFAULT '[]',
        resolved_thread_ids_json TEXT DEFAULT '[]',
        world_history_json TEXT DEFAULT '[]',
        last_updated REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS narrative_threads (
        thread_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        theme TEXT NOT NULL,
        summary TEXT NOT NULL,
        canonical_facts_json TEXT DEFAULT '[]',
        status TEXT DEFAULT 'rumor',
        significance REAL DEFAULT 0.0,
        origin_region TEXT,
        created_at REAL NOT NULL
    );
    """)
    conn.commit()
    return conn


# ══════════════════════════════════════════════════════════════════════
# LAYER 1: Populate 500 stat rows with realistic values
# ══════════════════════════════════════════════════════════════════════

def populate_layer1(conn: sqlite3.Connection) -> int:
    """Insert 500 realistic stat rows simulating ~2 hours of play."""
    rows = []
    t = time.time()

    def add(key, count=0, total=0.0, mx=0.0):
        rows.append((key, count, total, max(mx, total), t))

    # Combat kills (player killed ~120 enemies total)
    add("combat.kills", 120, 120.0, 120.0)
    for enemy in ENEMIES:
        base = enemy["id"].rstrip("0123456789").rstrip("_")
        kills = random.randint(3, 30) if enemy["tier"] <= 2 else random.randint(1, 8)
        add(f"combat.kills.species.{_safe_key(base)}", kills, float(kills))
        add(f"combat.kills.tier.{enemy['tier']}", kills, float(kills))
    for loc in REGIONS:
        add(f"combat.kills.location.{_safe_key(loc)}", random.randint(5, 25))

    # Combat damage dealt (~15000 total)
    add("combat.damage_dealt", 850, 15234.0, 342.0)
    for dt in DAMAGE_TYPES:
        add(f"combat.damage_dealt.type.{dt}", random.randint(50, 300), random.uniform(1000, 5000), random.uniform(100, 400))
    add("combat.damage_dealt.attack.melee", 700, 12000.0, 342.0)
    add("combat.damage_dealt.attack.ranged", 100, 2000.0, 180.0)
    add("combat.damage_dealt.attack.magic", 50, 1234.0, 250.0)
    add("combat.damage_dealt.critical", 85, 4200.0, 342.0)
    add("combat.critical_hits", 85)

    # Combat damage taken
    add("combat.damage_taken", 200, 3500.0, 89.0)
    add("combat.damage_taken.type.physical", 180, 3000.0, 89.0)
    add("combat.damage_taken.type.poison", 20, 500.0, 35.0)

    # Deaths & survival
    add("combat.deaths", 3)
    add("combat.deaths.source.enemy", 2)
    add("combat.deaths.source.environment", 1)
    add("combat.dodge_rolls", 45)
    add("combat.dodge_rolls.successful", 38)
    add("combat.blocks", 22)
    add("combat.healing", 15, 450.0, 50.0)
    add("combat.healing.potion", 8, 320.0, 50.0)
    add("combat.healing.lifesteal", 7, 130.0, 25.0)
    add("combat.longest_killstreak", 0, 0.0, 12.0)
    add("combat.combos", 34)
    add("combat.projectiles.fired", 28)
    add("combat.projectiles.hit", 22)
    add("combat.status.applied", 45)
    for eff in STATUS_EFFECTS:
        add(f"combat.status.applied.{eff}", random.randint(2, 12))

    # Weapon attacks
    add("combat.attacks", 850)
    add("combat.attacks.weapon_type.sword", 500)
    add("combat.attacks.weapon_type.axe", 200)
    add("combat.attacks.weapon_type.bow", 100)
    add("combat.attacks.weapon_type.staff", 50)

    # Gathering (~300 resources)
    add("gathering.collected", 300, 300.0)
    add("gathering.actions", 300, 300.0)
    for res in RESOURCES:
        qty = random.randint(5, 40)
        tier = 1 if res in MATERIALS_BY_TIER[1] else 2
        add(f"gathering.collected.resource.{_safe_key(res)}", qty, float(qty))
        add(f"gathering.collected.tier.{tier}", qty, float(qty))
    for cat in ["metal", "wood", "stone"]:
        add(f"gathering.collected.category.{cat}", random.randint(50, 120))
    add("gathering.critical", 15)
    add("gathering.rare_drops", 3)
    add("gathering.tool_swings", 450)
    add("gathering.tool_swings.pickaxe", 200)
    add("gathering.tool_swings.axe", 200)
    add("gathering.tool_swings.fishing_rod", 50)
    add("gathering.nodes_depleted", 22)
    add("gathering.fishing.caught", 12, 12.0)
    add("gathering.fishing.failed", 5)

    # Crafting (~50 attempts)
    add("crafting.attempts", 50, 50.0)
    add("crafting.success", 38, 38.0)
    for d in DISCIPLINES[:5]:
        attempts = random.randint(5, 15)
        successes = int(attempts * random.uniform(0.6, 0.9))
        add(f"crafting.attempts.discipline.{d}", attempts)
        add(f"crafting.success.discipline.{d}", successes)
    for r in ["common", "uncommon", "rare"]:
        add(f"crafting.rarity.{r}", random.randint(3, 20))
    add("crafting.materials_consumed", 50, 180.0)
    add("crafting.inventions", 2)
    add("crafting.enchantments", 3)
    add("crafting.quality", 38, 28.5, 0.95)

    # Items
    add("items.collected", 180, 180.0)
    add("items.equipped", 12)
    add("items.equipment_swaps", 8)
    add("items.repaired", 4, 4.0, 45.0)
    add("items.dropped", 3)

    # Skills
    add("skills.used", 200, 200.0)
    for sid in SKILLS[:6]:
        uses = random.randint(10, 50)
        add(f"skills.used.skill.{_safe_key(sid)}", uses, float(uses))
    add("skills.mana_spent", 200, 3500.0)

    # Exploration
    add("exploration.distance", 0, 8500.0, 8500.0)
    add("exploration.unique_chunks", 35)
    add("exploration.chunk_entries", 120)
    for biome in ["forest", "quarry", "cave", "peaceful_forest"]:
        add(f"exploration.chunks.biome.{biome}", random.randint(5, 30))

    # Economy
    add("economy.gold_earned", 5, 450.0)
    add("economy.gold_earned.quest", 3, 300.0)
    add("economy.gold_earned.loot", 2, 150.0)
    add("economy.gold_spent", 1, 50.0)
    add("economy.gold_spent.skill_unlock", 1, 50.0)

    # Progression
    add("progression.level_ups", 8)
    add("progression.current_level", 0, 0.0, 9.0)
    add("progression.exp", 0, 4200.0)
    add("progression.exp.combat", 0, 2800.0)
    add("progression.exp.quest", 0, 900.0)
    add("progression.exp.crafting", 0, 500.0)
    add("progression.titles", 2)
    add("progression.skills_learned", 6)
    add("progression.class_changes", 1)
    add("progression.class_changes.warrior", 1)

    # Dungeons
    add("dungeon.entered", 3)
    add("dungeon.completed", 2)
    add("dungeon.deaths", 1)
    add("dungeon.enemies_killed", 28)
    add("dungeon.waves_completed", 8)
    add("dungeon.chests_opened", 4)

    # Social
    add("social.npc_interactions", 15)
    add("social.npc.tutorial_guide", 5)
    add("social.npc.mysterious_trader", 6)
    add("social.npc.combat_trainer", 4)
    add("social.quests.accepted", 3)
    add("social.quests.completed", 2)

    # Time
    add("time.activity.combat", 0, 1800.0)
    add("time.activity.exploration", 0, 2400.0)
    add("time.activity.crafting", 0, 900.0)
    add("time.activity.menu", 0, 600.0)
    add("time.idle", 0, 300.0)
    add("time.total_playtime", 0, 0.0, 7200.0)

    # Misc
    add("misc.saves.autosave", 4)
    add("misc.menu_opened.inventory", 25)
    add("misc.menu_opened.equipment", 12)
    add("misc.menu_opened.skills", 8)
    add("misc.menu_opened.map", 15)

    # Pad to ~500 with per-location and per-item dimensional keys
    for loc in REGIONS:
        for cat in ["combat", "gathering"]:
            add(f"gathering.collected.location.{_safe_key(loc)}", random.randint(5, 30))

    # Trim or pad to 500
    rows = rows[:500]
    while len(rows) < 500:
        idx = len(rows)
        rows.append((f"_padding.key_{idx}", 0, 0.0, 0.0, t))

    conn.executemany(
        "INSERT OR REPLACE INTO stats (key, count, total, max_value, updated_at) VALUES (?, ?, ?, ?, ?)",
        rows
    )
    conn.commit()
    return len(rows)


# ══════════════════════════════════════════════════════════════════════
# RAW EVENT PIPELINE: Generate ~200 timestamped events
# ══════════════════════════════════════════════════════════════════════

def populate_raw_events(conn: sqlite3.Connection) -> int:
    """Simulate a 2-hour play session generating ~200 raw events."""
    session_id = _uid()
    events = []
    tags_rows = []
    stream_counts = {}   # Track 1: (actor, type, subtype, locality)
    regional_counts = {} # Track 2: (locality, category)
    threshold_hits = []  # Events that hit thresholds

    game_time = 0.0
    real_time = time.time()

    def _add_event(etype, subtype, locality, magnitude=0.0, tier=1,
                   target_id="", result="success", extra_tags=None):
        nonlocal game_time
        game_time += random.uniform(5, 60)  # 5-60 seconds between events
        eid = _uid()
        region = REGIONS.get(locality, REGIONS["spawn_crossroads"])
        pos_x = random.uniform(10, 90)
        pos_y = random.uniform(10, 90)
        chunk_x = int(pos_x) // 16
        chunk_y = int(pos_y) // 16

        events.append((
            eid, etype, subtype, "player", "player",
            target_id, "enemy" if "kill" in etype else "",
            pos_x, pos_y, chunk_x, chunk_y,
            locality, region["district"], region["province"], region["biome"],
            game_time, real_time + game_time, session_id,
            magnitude, result, None, tier, "{}", 0, 0
        ))

        # Auto-tags (mirrors event_recorder._build_event_tags)
        base_tags = [f"domain:{EVENT_CATEGORIES.get(etype, 'other')}",
                     f"event:{etype}", f"tier:{tier}",
                     f"biome:{region['biome']}", f"location:{locality}"]
        if extra_tags:
            base_tags.extend(extra_tags)
        for tag in base_tags:
            tags_rows.append((eid, tag))

        # Track 1: individual stream counting
        skey = ("player", etype, subtype, locality)
        stream_counts[skey] = stream_counts.get(skey, 0) + 1
        if stream_counts[skey] in THRESHOLD_SET:
            threshold_hits.append((eid, etype, subtype, locality,
                                   stream_counts[skey], game_time))

        # Track 2: regional accumulator
        cat = EVENT_CATEGORIES.get(etype, "other")
        rkey = (locality, cat)
        regional_counts[rkey] = regional_counts.get(rkey, 0) + 1
        if regional_counts[rkey] in THRESHOLD_SET:
            threshold_hits.append((eid, f"regional_{cat}", locality, locality,
                                   regional_counts[rkey], game_time))
        return eid

    # ── Simulate play session narrative ──────────────────────────

    # Phase 1: Spawn area (game_time 0-600) — gathering + first combat
    for _ in range(15):
        res = random.choice(MATERIALS_BY_TIER[1])
        _add_event("resource_gathered", f"resource.{res}", "spawn_crossroads",
                   magnitude=random.randint(1, 3), tier=1,
                   extra_tags=[f"resource:{res}", "material_category:metal" if "ore" in res else "material_category:wood"])

    for _ in range(8):
        enemy = random.choice([e for e in ENEMIES if e["tier"] == 1])
        _add_event("enemy_killed", f"enemy.{enemy['id']}", "spawn_crossroads",
                   magnitude=random.uniform(10, 30), tier=1, target_id=enemy["id"],
                   extra_tags=[f"species:{enemy['id']}", f"rank:{enemy['rank']}"])

    _add_event("level_up", "level.2", "spawn_crossroads", magnitude=2, tier=1)
    _add_event("chunk_entered", "chunk.1_1", "spawn_crossroads", tier=1)
    _add_event("npc_interaction", "npc.tutorial_guide", "spawn_crossroads",
               extra_tags=["npc:tutorial_guide"])
    _add_event("quest_accepted", "quest.tutorial_quest", "spawn_crossroads",
               extra_tags=["quest:tutorial_quest"])

    # Phase 2: Whispering Woods (game_time 600-1800) — exploration + combat
    for _ in range(5):
        _add_event("chunk_entered", f"chunk.{random.randint(0,5)}_{random.randint(0,5)}",
                   "south_clearing", tier=1)
    _add_event("area_discovered", "area.south_clearing", "south_clearing",
               extra_tags=["scope:local"])

    for _ in range(20):
        enemy = random.choice([e for e in ENEMIES if e["tier"] <= 2])
        loc = random.choice(["south_clearing", "elder_grove"])
        _add_event("enemy_killed", f"enemy.{enemy['id']}", loc,
                   magnitude=random.uniform(15, 60), tier=enemy["tier"],
                   target_id=enemy["id"],
                   extra_tags=[f"species:{enemy['id']}", f"rank:{enemy['rank']}"])

    for _ in range(10):
        res = random.choice(MATERIALS_BY_TIER[1] + MATERIALS_BY_TIER[2][:3])
        _add_event("resource_gathered", f"resource.{res}", "elder_grove",
                   magnitude=random.randint(1, 5), tier=1 if res in MATERIALS_BY_TIER[1] else 2,
                   extra_tags=[f"resource:{res}"])

    _add_event("level_up", "level.5", "elder_grove", magnitude=5)
    _add_event("skill_learned", "skill.fireball", "elder_grove",
               extra_tags=["skill:fireball"])
    _add_event("quest_completed", "quest.tutorial_quest", "south_clearing",
               magnitude=100, extra_tags=["quest:tutorial_quest"])

    # Phase 3: Iron Hills mining focus (game_time 1800-3600)
    for _ in range(35):
        res = random.choice(["iron_ore", "copper_ore", "iron_ore", "steel_ore", "iron_ore"])
        _add_event("resource_gathered", f"resource.{res}", "traders_corner",
                   magnitude=random.randint(1, 4),
                   tier=1 if res != "steel_ore" else 2,
                   extra_tags=[f"resource:{res}", "material_category:metal"])

    _add_event("node_depleted", "node.iron_deposit", "traders_corner",
               extra_tags=["resource:iron_ore"])
    _add_event("node_depleted", "node.copper_vein", "east_path",
               extra_tags=["resource:copper_ore"])

    for _ in range(15):
        enemy = random.choice([e for e in ENEMIES if e["tier"] <= 2])
        _add_event("enemy_killed", f"enemy.{enemy['id']}",
                   random.choice(["traders_corner", "east_path"]),
                   magnitude=random.uniform(20, 80), tier=enemy["tier"],
                   target_id=enemy["id"],
                   extra_tags=[f"species:{enemy['id']}"])

    # Crafting session
    for _ in range(12):
        disc = random.choice(["smithing", "smithing", "refining", "alchemy"])
        _add_event("craft_attempted", f"recipe.{disc}_{random.randint(1,10)}",
                   "traders_corner", tier=random.choice([1, 1, 2]),
                   result=random.choice(["success", "success", "success", "failure"]),
                   extra_tags=[f"discipline:{disc}"])

    _add_event("level_up", "level.8", "traders_corner", magnitude=8)
    _add_event("title_earned", "title.apprentice_flame_miner", "traders_corner",
               extra_tags=["title_tier:apprentice"])

    # Phase 4: Deep Caverns dungeon (game_time 3600-5400)
    _add_event("chunk_entered", "chunk.dungeon_deep_caverns", "deep_caverns",
               extra_tags=["scope:local"])
    _add_event("area_discovered", "area.deep_caverns", "deep_caverns",
               extra_tags=["scope:district"])

    for _ in range(18):
        enemy = random.choice([e for e in ENEMIES if e["tier"] >= 2])
        _add_event("enemy_killed", f"enemy.{enemy['id']}", "deep_caverns",
                   magnitude=random.uniform(40, 150), tier=enemy["tier"],
                   target_id=enemy["id"],
                   extra_tags=[f"species:{enemy['id']}", f"rank:{enemy['rank']}"])

    _add_event("player_death", "death.combat", "deep_caverns",
               extra_tags=["death_source:enemy"])
    _add_event("dodge_performed", "dodge.1", "deep_caverns")

    for _ in range(8):
        _add_event("skill_used", f"skill.{random.choice(SKILLS[:5])}", "deep_caverns",
                   magnitude=random.uniform(30, 100),
                   extra_tags=[f"skill:{random.choice(SKILLS[:5])}"])

    # Phase 5: Late session (game_time 5400-7200)
    _add_event("npc_interaction", "npc.mysterious_trader", "traders_corner",
               extra_tags=["npc:mysterious_trader"])
    _add_event("quest_accepted", "quest.gathering_quest", "traders_corner",
               extra_tags=["quest:gathering_quest"])
    _add_event("level_up", "level.9", "east_path", magnitude=9)
    _add_event("class_changed", "class.warrior", "traders_corner",
               extra_tags=["class:warrior"])

    for _ in range(10):
        res = random.choice(MATERIALS_BY_TIER[2])
        _add_event("resource_gathered", f"resource.{res}", "east_path",
                   magnitude=random.randint(2, 5), tier=2,
                   extra_tags=[f"resource:{res}"])

    # Insert all events
    conn.executemany("""
        INSERT INTO events (event_id, event_type, event_subtype, actor_id, actor_type,
            target_id, target_type, position_x, position_y, chunk_x, chunk_y,
            locality_id, district_id, province_id, biome,
            game_time, real_time, session_id,
            magnitude, result, quality, tier, context_json,
            interpretation_count, triggered_interpretation)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, events)

    conn.executemany("INSERT INTO event_tags (event_id, tag) VALUES (?, ?)", tags_rows)

    # Store occurrence counts
    for skey, count in stream_counts.items():
        conn.execute("""
            INSERT OR REPLACE INTO occurrence_counts (actor_id, event_type, event_subtype, count)
            VALUES (?, ?, ?, ?)
        """, (skey[0], skey[1], skey[2], count))

    for rkey, count in regional_counts.items():
        conn.execute("""
            INSERT OR REPLACE INTO regional_counters (region_id, event_category, count)
            VALUES (?, ?, ?)
        """, (rkey[0], rkey[1], count))

    conn.commit()
    return len(events), threshold_hits


# ══════════════════════════════════════════════════════════════════════
# LAYER 2: Generate evaluator outputs from threshold hits
# ══════════════════════════════════════════════════════════════════════

# Evaluator templates (from design doc §2.5 + §6.2)
EVALUATOR_TEMPLATES = {
    ("enemy_killed", 1): ("population_change", "A newcomer has begun their first hunt in {loc}."),
    ("enemy_killed", 3): ("population_change", "Hunting activity is picking up in {loc}. {count} creatures killed."),
    ("enemy_killed", 10): ("combat_proficiency", "Active hunter in {loc}. {count} kills, showing combat proficiency."),
    ("enemy_killed", 25): ("population_change", "Significant hunting pressure in {loc}. {count} creatures killed — population may be affected."),
    ("enemy_killed", 50): ("population_change", "Heavy culling in {loc}. {count} kills. Local wildlife populations declining."),
    ("resource_gathered", 1): ("ecosystem_pressure", "Someone has started harvesting resources in {loc}."),
    ("resource_gathered", 5): ("ecosystem_pressure", "Regular harvesting in {loc}. {count} gathering actions recorded."),
    ("resource_gathered", 10): ("ecosystem_pressure", "Sustained resource extraction in {loc}. {count} resources gathered."),
    ("resource_gathered", 25): ("ecosystem_pressure", "Heavy resource extraction in {loc}. {count} gathered — strain on local supply."),
    ("resource_gathered", 50): ("ecosystem_pressure", "Critical harvesting pressure in {loc}. {count} resources — deposits becoming strained."),
    ("craft_attempted", 3): ("crafting_mastery", "Crafting activity emerging. {count} attempts in {loc}."),
    ("craft_attempted", 10): ("crafting_mastery", "Dedicated crafter active. {count} crafting attempts, showing discipline focus."),
    ("level_up", 1): ("player_milestones", "Reached a new level in {loc}."),
    ("chunk_entered", 5): ("exploration_discovery", "Exploring the region around {loc}. {count} areas visited."),
    ("npc_interaction", 3): ("social_reputation", "Building relationships with locals in {loc}. {count} NPC interactions."),
    ("quest_completed", 1): ("player_milestones", "Completed a quest in {loc}."),
    ("title_earned", 1): ("player_milestones", "Earned a new title in {loc}."),
    ("class_changed", 1): ("player_milestones", "Chose a class specialization in {loc}."),
    ("node_depleted", 1): ("ecosystem_pressure", "A resource node has been fully depleted in {loc}."),
    ("player_death", 1): ("combat_proficiency", "Fell in combat in {loc}. Area may be dangerous."),
    ("skill_learned", 1): ("player_milestones", "Learned a new skill in {loc}."),
    # Regional accumulators
    ("regional_combat", 10): ("area_danger", "Moderate combat activity in {loc}. {count} combat events recorded."),
    ("regional_combat", 25): ("area_danger", "Heavy combat zone: {loc}. {count} combat events — area is dangerous."),
    ("regional_gathering", 10): ("resource_pressure", "Active harvesting region: {loc}. {count} gathering events."),
    ("regional_gathering", 25): ("resource_pressure", "Under resource pressure: {loc}. {count} gathering events — supply strained."),
    ("regional_crafting", 5): ("crafting_mastery", "Crafting hub emerging at {loc}. {count} crafting events."),
    ("regional_exploration", 5): ("exploration_discovery", "Actively exploring {loc} area. {count} exploration events."),
}

SEVERITY_BY_COUNT = {1: "minor", 3: "minor", 5: "moderate", 10: "moderate",
                     25: "significant", 50: "major", 100: "critical"}


def populate_layer2(conn: sqlite3.Connection, threshold_hits: list) -> int:
    """Generate Layer 2 interpretations from threshold hits."""
    interp_rows = []
    tag_rows = []

    for hit in threshold_hits:
        eid, etype, subtype, locality, count, gt = hit
        # Strip "regional_" prefix for lookup
        lookup_type = etype
        key = (lookup_type, count)
        if key not in EVALUATOR_TEMPLATES:
            # Try just the type with nearest lower threshold
            for thresh in sorted(EVALUATOR_TEMPLATES.keys(), key=lambda x: x[1], reverse=True):
                if thresh[0] == lookup_type and thresh[1] <= count:
                    key = thresh
                    break
            else:
                continue

        category, template = EVALUATOR_TEMPLATES[key]
        narrative = template.format(loc=locality, count=count, subtype=subtype)
        severity = SEVERITY_BY_COUNT.get(count, "moderate")
        iid = _uid()
        region = REGIONS.get(locality, REGIONS["spawn_crossroads"])

        interp_rows.append((
            iid, gt, narrative, category, severity,
            eid, count, json.dumps([eid]),
            json.dumps([locality]), json.dumps([region["district"]]),
            random.uniform(10, 90), random.uniform(10, 90),
            json.dumps([f"domain:{EVENT_CATEGORIES.get(etype.replace('regional_',''), 'other')}",
                        f"location:{locality}"]),
            0, 1, 0
        ))

        # Tags: inherit from event + add Layer 2 geographic tags
        base_tags = [
            f"domain:{EVENT_CATEGORIES.get(etype.replace('regional_',''), 'other')}",
            f"location:{locality}",
            f"district:{region['district']}",
            f"province:{region['province']}",
            f"biome:{region['biome']}",
            f"scope:local",
            f"significance:{severity}",
            f"category:{category}",
        ]
        for tag in base_tags:
            tag_rows.append((iid, tag))

    conn.executemany("""
        INSERT INTO interpretations (interpretation_id, created_at, narrative,
            category, severity, trigger_event_id, trigger_count,
            cause_event_ids_json, affected_locality_ids_json,
            affected_district_ids_json, epicenter_x, epicenter_y,
            affects_tags_json, is_ongoing, update_count, archived)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, interp_rows)

    conn.executemany(
        "INSERT INTO interpretation_tags (interpretation_id, tag) VALUES (?, ?)",
        tag_rows)

    conn.commit()
    return len(interp_rows)


# ══════════════════════════════════════════════════════════════════════
# LAYER 3: Cross-domain consolidation
# Triggers when locality has 3+ Layer 2 interpretations OR 2+ categories
# ══════════════════════════════════════════════════════════════════════

def populate_layer3(conn: sqlite3.Connection) -> int:
    """Generate Layer 3 connected interpretations from Layer 2 accumulation."""
    # Group Layer 2 interpretations by locality
    cursor = conn.execute("""
        SELECT i.interpretation_id, i.narrative, i.category, i.severity, i.created_at,
               it.tag
        FROM interpretations i
        JOIN interpretation_tags it ON it.interpretation_id = i.interpretation_id
        WHERE it.tag LIKE 'location:%'
    """)
    by_locality = {}
    for row in cursor:
        iid, narrative, category, severity, created_at, tag = row
        locality = tag.replace("location:", "")
        by_locality.setdefault(locality, []).append({
            "id": iid, "narrative": narrative, "category": category,
            "severity": severity, "created_at": created_at
        })

    rows = []
    tag_rows = []
    for locality, interps in by_locality.items():
        categories = set(i["category"] for i in interps)
        # Trigger: 3+ interpretations OR 2+ different categories
        if len(interps) >= 3 or len(categories) >= 2:
            region = REGIONS.get(locality, REGIONS["spawn_crossroads"])
            source_ids = [i["id"] for i in interps]
            latest_time = max(i["created_at"] for i in interps)

            # Synthesize cross-domain narrative
            activity_summary = ", ".join(sorted(categories))
            severity = "significant" if len(interps) >= 5 else "moderate"
            narrative = (f"The {locality.replace('_', ' ').title()} is experiencing "
                        f"correlated activity across {len(categories)} domains: "
                        f"{activity_summary}. {len(interps)} notable events recorded.")

            cid = _uid()
            rows.append((
                cid, latest_time, narrative, "cross_domain_synthesis", severity,
                json.dumps(source_ids),
                json.dumps([region["district"]]),
                json.dumps([f"domain:multiple", f"location:{locality}",
                           f"district:{region['district']}"]),
                1, 0
            ))

            # Tags: merge from sources + add Layer 3 tags
            tags = [
                f"location:{locality}",
                f"district:{region['district']}",
                f"province:{region['province']}",
                f"scope:district",
                f"significance:{severity}",
                f"trend:{'accelerating' if len(interps) >= 5 else 'emerging'}",
                f"intensity:{'heavy' if len(interps) >= 5 else 'moderate'}",
            ]
            for cat in categories:
                tags.append(f"domain:{EVENT_CATEGORIES.get(cat, cat)}")
            for tag in tags:
                tag_rows.append((cid, tag))

    conn.executemany("""
        INSERT INTO connected_interpretations (id, created_at, narrative,
            category, severity, source_interpretation_ids_json,
            affected_district_ids_json, affects_tags_json, is_ongoing, archived)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.executemany(
        "INSERT INTO connected_interpretation_tags (id, tag) VALUES (?, ?)",
        tag_rows)
    conn.commit()
    return len(rows)


# ══════════════════════════════════════════════════════════════════════
# LAYER 4: Province summaries
# Triggers when 3+ Layer 3 events in child districts
# ══════════════════════════════════════════════════════════════════════

def populate_layer4(conn: sqlite3.Connection) -> int:
    """Generate Layer 4 province summaries from Layer 3 consolidation."""
    # Group Layer 3 by province (via district tags)
    cursor = conn.execute("""
        SELECT ci.id, ci.narrative, ci.category, ci.severity, ci.created_at,
               cit.tag
        FROM connected_interpretations ci
        JOIN connected_interpretation_tags cit ON cit.id = ci.id
        WHERE cit.tag LIKE 'province:%'
    """)
    by_province = {}
    for row in cursor:
        cid, narrative, category, severity, created_at, tag = row
        province = tag.replace("province:", "")
        by_province.setdefault(province, []).append({
            "id": cid, "narrative": narrative, "severity": severity
        })

    # Also gather from district tags if province tags are missing
    if not by_province:
        cursor = conn.execute("""
            SELECT ci.id, ci.narrative, ci.severity, cit.tag
            FROM connected_interpretations ci
            JOIN connected_interpretation_tags cit ON cit.id = ci.id
            WHERE cit.tag LIKE 'district:%'
        """)
        for row in cursor:
            cid, narrative, severity, tag = row
            district = tag.replace("district:", "")
            # Map district to province
            for loc, reg in REGIONS.items():
                if reg["district"] == district:
                    by_province.setdefault(reg["province"], []).append({
                        "id": cid, "narrative": narrative, "severity": severity
                    })
                    break

    count = 0
    for province, events in by_province.items():
        dominant = ["combat", "gathering", "crafting"][:min(3, len(events))]
        threat = "moderate" if any(e["severity"] in ("significant", "major") for e in events) else "low"
        summary = (f"Province {province.replace('_', ' ').title()}: "
                  f"{len(events)} notable regional pattern(s). "
                  f"Dominant activities: {', '.join(dominant)}. Threat level: {threat}.")

        conn.execute("""
            INSERT OR REPLACE INTO province_summaries
                (province_id, summary_text, dominant_activities_json,
                 notable_event_ids_json, threat_level, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (province, summary, json.dumps(dominant),
              json.dumps([e["id"] for e in events]), threat,
              max(0, *(e.get("created_at", 0) for e in events)) if events else 0))
        count += 1

    conn.commit()
    return count


# ══════════════════════════════════════════════════════════════════════
# LAYER 5: Realm state
# ══════════════════════════════════════════════════════════════════════

def populate_layer5(conn: sqlite3.Connection) -> int:
    """Generate Layer 5 realm state from province summaries."""
    cursor = conn.execute("SELECT province_id, summary_text, threat_level FROM province_summaries")
    provinces = cursor.fetchall()
    if not provinces:
        return 0

    threat_counts = {"low": 0, "moderate": 0, "high": 0}
    summaries = []
    for pid, summary, threat in provinces:
        threat_counts[threat] = threat_counts.get(threat, 0) + 1
        summaries.append(summary)

    overall_threat = "moderate" if threat_counts.get("moderate", 0) > 0 else "low"
    econ_summary = "Active resource extraction and crafting economy. Gold flow from quests."
    player_rep = "Rising adventurer with combat and crafting focus. Level 9, warrior class."

    conn.execute("""
        INSERT OR REPLACE INTO realm_state
            (realm_id, faction_standings_json, economic_summary,
             player_reputation, major_events_json, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("known_lands", json.dumps({"village_guard": 0.3, "crafters_guild": 0.5}),
          econ_summary, player_rep, json.dumps(summaries), time.time()))
    conn.commit()
    return 1


# ══════════════════════════════════════════════════════════════════════
# LAYERS 6-7: World narrative
# ══════════════════════════════════════════════════════════════════════

def populate_layers_6_7(conn: sqlite3.Connection) -> int:
    """Generate world narrative and threads from realm state."""
    # Create a narrative thread from the iron mining pressure
    thread_id = _uid()
    conn.execute("""
        INSERT INTO narrative_threads
            (thread_id, source, theme, summary, canonical_facts_json,
             status, significance, origin_region, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (thread_id, "ecosystem_pressure",
          "resource_depletion",
          "Iron deposits in the Iron Hills are being heavily mined. "
          "Local supply is strained and node depletion events are increasing.",
          json.dumps(["Player mined 50+ iron ore in Iron Hills",
                      "2 iron nodes fully depleted",
                      "Gathering rate exceeds regeneration"]),
          "developing", 0.6, "iron_hills", time.time()))

    # World narrative singleton
    conn.execute("""
        INSERT OR REPLACE INTO world_narrative
            (id, world_themes_json, world_epoch, active_thread_ids_json,
             world_history_json, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("singleton",
          json.dumps(["discovery", "growth", "conflict"]),
          "early_exploration",
          json.dumps([thread_id]),
          json.dumps([
              "A newcomer arrived and began exploring the known lands.",
              "Heavy iron mining activity detected in the Iron Hills region.",
              "The adventurer chose the warrior path and grew to level 9.",
          ]),
          time.time()))

    conn.commit()
    return 2


# ══════════════════════════════════════════════════════════════════════
# MAIN: Build simulation and dump results
# ══════════════════════════════════════════════════════════════════════

def dump_summary(conn: sqlite3.Connection):
    """Print summary of all layers."""
    print("=" * 70)
    print("WORLD MEMORY SYSTEM — SIMULATION DATABASE SUMMARY")
    print("=" * 70)

    # Layer 1
    row = conn.execute("SELECT COUNT(*), SUM(count), SUM(total) FROM stats").fetchone()
    print(f"\nLayer 1 (Stats): {row[0]} keys, {int(row[1] or 0)} total counts, {row[2] or 0:.0f} total values")

    # Top stats
    print("  Top 10 stats by count:")
    for r in conn.execute("SELECT key, count, total FROM stats ORDER BY count DESC LIMIT 10"):
        print(f"    {r[0]:45s} count={r[1]:>6d}  total={r[2]:>10.1f}")

    # Raw events
    row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    print(f"\nRaw Event Pipeline: {row[0]} events")
    for r in conn.execute("SELECT event_type, COUNT(*) c FROM events GROUP BY event_type ORDER BY c DESC LIMIT 8"):
        print(f"    {r[0]:25s}: {r[1]}")

    # Threshold hits
    row = conn.execute("SELECT COUNT(*) FROM occurrence_counts WHERE count > 0").fetchone()
    print(f"\n  Stream counters: {row[0]}")
    row = conn.execute("SELECT COUNT(*) FROM regional_counters WHERE count > 0").fetchone()
    print(f"  Regional counters: {row[0]}")

    # Layer 2
    row = conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()
    print(f"\nLayer 2 (Interpretations): {row[0]} evaluator outputs")
    for r in conn.execute("SELECT category, COUNT(*) c FROM interpretations GROUP BY category ORDER BY c DESC"):
        print(f"    {r[0]:30s}: {r[1]}")
    print("  Sample narratives:")
    for r in conn.execute("SELECT narrative, severity FROM interpretations ORDER BY created_at LIMIT 5"):
        print(f"    [{r[1]:>12s}] {r[0][:80]}")

    # Layer 3
    row = conn.execute("SELECT COUNT(*) FROM connected_interpretations").fetchone()
    print(f"\nLayer 3 (Consolidated): {row[0]} cross-domain patterns")
    for r in conn.execute("SELECT narrative FROM connected_interpretations"):
        print(f"    {r[0][:90]}")

    # Layer 4
    row = conn.execute("SELECT COUNT(*) FROM province_summaries").fetchone()
    print(f"\nLayer 4 (Province Summaries): {row[0]} provinces")
    for r in conn.execute("SELECT province_id, summary_text, threat_level FROM province_summaries"):
        print(f"    [{r[2]:>8s}] {r[0]}: {r[1][:80]}")

    # Layer 5
    row = conn.execute("SELECT COUNT(*) FROM realm_state").fetchone()
    print(f"\nLayer 5 (Realm State): {row[0]} realm(s)")
    for r in conn.execute("SELECT realm_id, economic_summary, player_reputation FROM realm_state"):
        print(f"    {r[0]}: {r[1][:60]}")
        print(f"    Player: {r[2][:60]}")

    # Layers 6-7
    row = conn.execute("SELECT COUNT(*) FROM narrative_threads").fetchone()
    print(f"\nLayers 6-7 (World Narrative): {row[0]} thread(s)")
    for r in conn.execute("SELECT theme, summary, status, significance FROM narrative_threads"):
        print(f"    [{r[2]}] {r[0]}: {r[1][:70]}")
    for r in conn.execute("SELECT world_epoch, world_themes_json FROM world_narrative"):
        print(f"    Epoch: {r[0]}, Themes: {r[1]}")

    print(f"\n{'=' * 70}")


def main():
    args = sys.argv[1:]
    root = find_project_root()
    db_path = os.path.join(root, "tools", "wms_simulation.db")

    print(f"Building simulation database: {db_path}")
    conn = create_database(db_path)

    # Layer 1
    n_stats = populate_layer1(conn)
    print(f"  Layer 1: {n_stats} stat rows")

    # Raw Event Pipeline
    n_events, threshold_hits = populate_raw_events(conn)
    print(f"  Raw Events: {n_events} events, {len(threshold_hits)} threshold hits")

    # Layer 2
    n_interps = populate_layer2(conn, threshold_hits)
    print(f"  Layer 2: {n_interps} interpretations")

    # Layer 3
    n_consolidated = populate_layer3(conn)
    print(f"  Layer 3: {n_consolidated} consolidated patterns")

    # Layer 4
    n_provinces = populate_layer4(conn)
    print(f"  Layer 4: {n_provinces} province summaries")

    # Layer 5
    n_realms = populate_layer5(conn)
    print(f"  Layer 5: {n_realms} realm state(s)")

    # Layers 6-7
    n_world = populate_layers_6_7(conn)
    print(f"  Layers 6-7: {n_world} world narrative entries")

    if '--dump' in args or '--stats' in args:
        dump_summary(conn)

    conn.close()
    print(f"\nDatabase written to: {db_path}")
    print(f"Inspect with: sqlite3 {db_path}")


if __name__ == '__main__':
    main()
