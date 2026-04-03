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
# DATABASE CREATION — mirrors layer_store.py (canonical) + event_store.py (raw pipeline)
# layer_store.py is the newer, tag-indexed design (March 26).
# event_store.py provides the raw event pipeline + occurrence counters.
# ══════════════════════════════════════════════════════════════════════

def create_database(db_path: str) -> sqlite3.Connection:
    """Create simulation database with all WMS tables."""
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # ── stat_store.py: Layer 1 flat counters (write-path) ────────
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS stats (
        key TEXT PRIMARY KEY,
        count INTEGER DEFAULT 0,
        total REAL DEFAULT 0.0,
        max_value REAL DEFAULT 0.0,
        updated_at REAL DEFAULT 0.0
    );
    CREATE INDEX IF NOT EXISTS idx_stats_prefix ON stats(key COLLATE NOCASE);
    """)

    # ── event_store.py: Raw Event Pipeline + tracking ────────────
    conn.executescript("""
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
        tag TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
    CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);

    -- Dual-track threshold counting
    CREATE TABLE IF NOT EXISTS occurrence_counts (
        actor_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_subtype TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (actor_id, event_type, event_subtype)
    );

    CREATE TABLE IF NOT EXISTS regional_counters (
        region_id TEXT NOT NULL,
        event_category TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (region_id, event_category)
    );
    """)

    # ── layer_store.py: Per-layer tag-indexed tables (canonical) ─
    # Layer 1: Stats with structured tag junction
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS layer1_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        count INTEGER DEFAULT 0,
        total REAL DEFAULT 0.0,
        max_value REAL DEFAULT 0.0,
        tags_json TEXT DEFAULT '[]',
        updated_at REAL DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS layer1_tags (
        stat_id INTEGER NOT NULL,
        tag_category TEXT NOT NULL,
        tag_value TEXT NOT NULL,
        FOREIGN KEY (stat_id) REFERENCES layer1_stats(id)
    );
    CREATE INDEX IF NOT EXISTS idx_l1_tags ON layer1_tags(tag_category, tag_value);
    CREATE INDEX IF NOT EXISTS idx_l1_tags_id ON layer1_tags(stat_id);

    -- Layer 2: Evaluator outputs with structured tags
    CREATE TABLE IF NOT EXISTS layer2_events (
        id TEXT PRIMARY KEY,
        narrative TEXT NOT NULL,
        origin_stat_key TEXT NOT NULL,
        game_time REAL NOT NULL,
        real_time REAL NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        significance TEXT NOT NULL DEFAULT 'minor',
        tags_json TEXT DEFAULT '[]',
        evaluator_id TEXT
    );
    CREATE TABLE IF NOT EXISTS layer2_tags (
        event_id TEXT NOT NULL,
        tag_category TEXT NOT NULL,
        tag_value TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES layer2_events(id)
    );
    CREATE INDEX IF NOT EXISTS idx_l2_tags ON layer2_tags(tag_category, tag_value);
    CREATE INDEX IF NOT EXISTS idx_l2_tags_id ON layer2_tags(event_id);
    CREATE INDEX IF NOT EXISTS idx_l2_time ON layer2_events(game_time);
    CREATE INDEX IF NOT EXISTS idx_l2_cat ON layer2_events(category);
    """)

    # Layers 3-7: Same schema pattern with origin column pointing to previous layer
    for layer_num in range(3, 8):
        origin_col = f"origin_layer{layer_num - 1}_ids"
        table = f"layer{layer_num}_events"
        tag_table = f"layer{layer_num}_tags"
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                narrative TEXT NOT NULL,
                {origin_col} TEXT NOT NULL DEFAULT '[]',
                game_time REAL NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                significance TEXT NOT NULL DEFAULT 'minor',
                tags_json TEXT DEFAULT '[]'
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {tag_table} (
                event_id TEXT NOT NULL,
                tag_category TEXT NOT NULL,
                tag_value TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES {table}(id)
            )
        """)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_tags "
                     f"ON {tag_table}(tag_category, tag_value)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_tags_id "
                     f"ON {tag_table}(event_id)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_l{layer_num}_time "
                     f"ON {table}(game_time)")

    conn.commit()
    return conn


def _insert_tags(conn: sqlite3.Connection, table: str, id_col: str,
                 id_val, tags: List[str]):
    """Insert structured (tag_category, tag_value) pairs into a tag junction table."""
    for tag in tags:
        if ":" in tag:
            cat, val = tag.split(":", 1)
            conn.execute(f"INSERT INTO {table} ({id_col}, tag_category, tag_value) "
                        "VALUES (?, ?, ?)", (id_val, cat, val))


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

    # Also populate layer1_stats + layer1_tags (layer_store.py canonical schema)
    conn.execute("PRAGMA defer_foreign_keys=ON")
    for key, count, total, mx, updated in rows:
        if key.startswith("_padding"):
            continue
        tags = _derive_tags_for_stat(key)
        conn.execute(
            "INSERT OR REPLACE INTO layer1_stats (key, count, total, max_value, tags_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, count, total, max(mx, total), json.dumps(tags), updated)
        )
    conn.commit()
    # Now insert tags (foreign keys satisfied)
    for key, count, total, mx, updated in rows:
        if key.startswith("_padding"):
            continue
        row_id = conn.execute("SELECT id FROM layer1_stats WHERE key = ?", (key,)).fetchone()
        if row_id is None:
            continue
        row_id = row_id[0]
        for tag in _derive_tags_for_stat(key):
            if ":" in tag:
                cat, val = tag.split(":", 1)
                conn.execute("INSERT INTO layer1_tags (stat_id, tag_category, tag_value) VALUES (?, ?, ?)",
                            (row_id, cat, val))
    conn.commit()
    return len(rows)


def _derive_tags_for_stat(key: str) -> List[str]:
    """Derive structured tags from a stat key. Mirrors layer1-stat-tags.json logic."""
    tags = []
    parts = key.split(".")

    # Domain tag from top-level
    domain_map = {
        "combat": "combat", "gathering": "gathering", "crafting": "crafting",
        "items": "items", "skills": "skills", "exploration": "exploration",
        "economy": "economy", "progression": "progression", "dungeon": "dungeon",
        "social": "social", "time": "time", "misc": "misc",
        "barriers": "items", "records": "records", "encyclopedia": "encyclopedia",
    }
    if parts[0] in domain_map:
        tags.append(f"domain:{domain_map[parts[0]]}")

    # Action tag from second level
    action_map = {
        "kills": "kill", "damage_dealt": "damage_deal", "damage_taken": "damage_take",
        "collected": "gather", "actions": "gather", "fishing": "fish",
        "attempts": "craft", "success": "craft", "inventions": "invent",
        "used": "use", "equipped": "equip", "dropped": "drop",
        "distance": "move", "deaths": "die", "healing": "heal",
        "dodge_rolls": "dodge", "blocks": "block", "level_ups": "level_up",
    }
    if len(parts) > 1 and parts[1] in action_map:
        tags.append(f"action:{action_map[parts[1]]}")

    # Dimensional tags from deeper parts (e.g., combat.kills.species.wolf → species:wolf)
    i = 2
    while i < len(parts) - 1:
        dim_name = parts[i]
        dim_value = parts[i + 1]
        if dim_name in ("species", "resource", "tier", "type", "attack",
                        "weapon_element", "to", "from", "location", "category",
                        "discipline", "rarity", "recipe", "fish", "skill",
                        "biome", "item", "slot", "element", "rank"):
            tags.append(f"{dim_name}:{dim_value}")
        i += 2

    # Metric tag
    if any(p in key for p in ["longest_streak", "longest_killstreak", "current_level"]):
        tags.append("metric:maximum")
    elif ".count" in key or parts[-1] in ("critical", "rare_drops"):
        tags.append("metric:count")
    else:
        tags.append("metric:total")

    return tags


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
    """Generate Layer 2 interpretations from threshold hits.
    Writes to layer2_events + layer2_tags (layer_store.py canonical schema)."""
    entries = []  # List of (iid, narrative, origin_key, gt, category, severity, tags)

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

        tags = [
            f"domain:{EVENT_CATEGORIES.get(etype.replace('regional_',''), 'other')}",
            f"location:{locality}",
            f"district:{region['district']}",
            f"province:{region['province']}",
            f"biome:{region['biome']}",
            f"scope:local",
            f"significance:{severity}",
        ]
        entries.append((iid, narrative, eid, gt, category, severity, tags))

    # Write to layer2_events + layer2_tags
    for iid, narrative, origin_key, gt, category, severity, tags in entries:
        conn.execute("""
            INSERT INTO layer2_events (id, narrative, origin_stat_key, game_time,
                real_time, category, severity, significance, tags_json, evaluator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (iid, narrative, str(origin_key), gt, gt,
              category, severity, severity, json.dumps(tags), category))
        _insert_tags(conn, "layer2_tags", "event_id", iid, tags)

    conn.commit()
    return len(entries)


# ══════════════════════════════════════════════════════════════════════
# LAYER 3: Cross-domain consolidation
# Triggers when locality has 3+ Layer 2 interpretations OR 2+ categories
# ══════════════════════════════════════════════════════════════════════

def populate_layer3(conn: sqlite3.Connection) -> int:
    """Generate Layer 3 from Layer 2 accumulation.
    Reads layer2_events + layer2_tags, writes to layer3_events + layer3_tags."""
    # Group Layer 2 by locality using structured tags
    cursor = conn.execute("""
        SELECT e.id, e.narrative, e.category, e.severity, e.game_time,
               t.tag_value
        FROM layer2_events e
        JOIN layer2_tags t ON t.event_id = e.id
        WHERE t.tag_category = 'location'
    """)
    by_locality = {}
    for row in cursor:
        eid, narrative, category, severity, game_time, locality = row
        by_locality.setdefault(locality, []).append({
            "id": eid, "narrative": narrative, "category": category,
            "severity": severity, "game_time": game_time
        })

    count = 0
    for locality, interps in by_locality.items():
        categories = set(i["category"] for i in interps)
        # Trigger: 3+ interpretations OR 2+ different categories
        if len(interps) >= 3 or len(categories) >= 2:
            region = REGIONS.get(locality, REGIONS["spawn_crossroads"])
            source_ids = [i["id"] for i in interps]
            latest_time = max(i["game_time"] for i in interps)

            activity_summary = ", ".join(sorted(categories))
            severity = "significant" if len(interps) >= 5 else "moderate"
            narrative = (f"The {locality.replace('_', ' ').title()} is experiencing "
                        f"correlated activity across {len(categories)} domains: "
                        f"{activity_summary}. {len(interps)} notable events recorded.")

            cid = _uid()
            # Layer 3 tags: inherited + new Layer 3 categories
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

            conn.execute("""
                INSERT INTO layer3_events (id, narrative, origin_layer2_ids,
                    game_time, category, severity, significance, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, narrative, json.dumps(source_ids), latest_time,
                  "cross_domain_synthesis", severity, severity, json.dumps(tags)))
            _insert_tags(conn, "layer3_tags", "event_id", cid, tags)
            count += 1

    conn.commit()
    return count


# ══════════════════════════════════════════════════════════════════════
# LAYER 4: Province summaries
# Triggers when 3+ Layer 3 events in child districts
# ══════════════════════════════════════════════════════════════════════

def populate_layer4(conn: sqlite3.Connection) -> int:
    """Generate Layer 4 from Layer 3. Reads layer3_tags, writes to layer4_events + layer4_tags."""
    # Group Layer 3 by province using structured tags
    cursor = conn.execute("""
        SELECT e.id, e.narrative, e.severity, e.game_time, t.tag_value
        FROM layer3_events e
        JOIN layer3_tags t ON t.event_id = e.id
        WHERE t.tag_category = 'province'
    """)
    by_province = {}
    for row in cursor:
        eid, narrative, severity, game_time, province = row
        by_province.setdefault(province, []).append({
            "id": eid, "narrative": narrative, "severity": severity, "game_time": game_time
        })

    count = 0
    for province, events in by_province.items():
        source_ids = [e["id"] for e in events]
        latest_time = max(e["game_time"] for e in events)
        threat = "moderate" if any(e["severity"] in ("significant", "major") for e in events) else "low"
        summary = (f"Province {province.replace('_', ' ').title()}: "
                  f"{len(events)} notable regional pattern(s). Threat level: {threat}.")

        l4id = _uid()
        tags = [
            f"province:{province}",
            f"scope:regional",
            f"significance:{threat}",
            f"urgency_level:{'moderate' if threat == 'moderate' else 'low'}",
            f"event_status:ongoing",
            f"player_impact:player_driven",
        ]
        conn.execute("""
            INSERT INTO layer4_events (id, narrative, origin_layer3_ids,
                game_time, category, severity, significance, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (l4id, summary, json.dumps(source_ids), latest_time,
              "provincial_summary", threat, threat, json.dumps(tags)))
        _insert_tags(conn, "layer4_tags", "event_id", l4id, tags)
        count += 1

    conn.commit()
    return count


# ══════════════════════════════════════════════════════════════════════
# LAYER 5: Realm state
# ══════════════════════════════════════════════════════════════════════

def populate_layer5(conn: sqlite3.Connection) -> int:
    """Generate Layer 5 from Layer 4. Reads layer4_events, writes to layer5_events + layer5_tags."""
    cursor = conn.execute("SELECT id, narrative, severity, game_time FROM layer4_events")
    l4_events = cursor.fetchall()
    if not l4_events:
        return 0

    source_ids = [r[0] for r in l4_events]
    latest_time = max(r[3] for r in l4_events)
    narrative = ("Realm Known Lands: Active resource extraction and crafting economy. "
                "Rising adventurer with combat and crafting focus. "
                f"{len(l4_events)} provincial patterns tracked.")

    l5id = _uid()
    tags = [
        "scope:global",
        "significance:moderate",
        "political:stabilizing",
        "living_impact:noticeable",
    ]
    conn.execute("""
        INSERT INTO layer5_events (id, narrative, origin_layer4_ids,
            game_time, category, severity, significance, tags_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (l5id, narrative, json.dumps(source_ids), latest_time,
          "realm_summary", "moderate", "moderate", json.dumps(tags)))
    _insert_tags(conn, "layer5_tags", "event_id", l5id, tags)

    conn.commit()
    return 1


# ══════════════════════════════════════════════════════════════════════
# LAYERS 6-7: World narrative
# ══════════════════════════════════════════════════════════════════════

def populate_layers_6_7(conn: sqlite3.Connection) -> int:
    """Generate Layers 6-7 from Layer 5. Writes to layer6/7_events + tags."""
    count = 0

    # Layer 6: Cross-realm (only 1 realm, so this is a pass-through)
    cursor = conn.execute("SELECT id, narrative, game_time FROM layer5_events")
    l5_events = cursor.fetchall()
    if l5_events:
        l6id = _uid()
        latest = max(r[2] for r in l5_events)
        l6_narrative = ("Cross-realm: Single realm active (Known Lands). "
                       "No inter-realm patterns yet.")
        l6_tags = [
            "scope:world",
            "significance:minor",
            "regional_significance:minor",
        ]
        conn.execute("""
            INSERT INTO layer6_events (id, narrative, origin_layer5_ids,
                game_time, category, severity, significance, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (l6id, l6_narrative, json.dumps([r[0] for r in l5_events]),
              latest, "intercountry_state", "minor", "minor", json.dumps(l6_tags)))
        _insert_tags(conn, "layer6_tags", "event_id", l6id, l6_tags)
        count += 1

        # Layer 7: World narrative thread
        l7id = _uid()
        l7_narrative = ("World narrative: A newcomer arrived and began shaping the known lands. "
                       "Iron deposits strained under heavy mining. "
                       "The adventurer chose the warrior path.")
        l7_tags = [
            "scope:world",
            "significance:notable",
            "world_significance:notable",
            "narrative_role:origin",
            "era_effect:era_continuing",
            "world_theme:discovery",
            "world_theme:growth",
        ]
        conn.execute("""
            INSERT INTO layer7_events (id, narrative, origin_layer6_ids,
                game_time, category, severity, significance, tags_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (l7id, l7_narrative, json.dumps([l6id]),
              latest, "world_narrative", "notable", "notable", json.dumps(l7_tags)))
        _insert_tags(conn, "layer7_tags", "event_id", l7id, l7_tags)
        count += 1

    conn.commit()
    return count


# ══════════════════════════════════════════════════════════════════════
# MAIN: Build simulation and dump results
# ══════════════════════════════════════════════════════════════════════

def dump_summary(conn: sqlite3.Connection):
    """Print summary of all layers using layer_store.py canonical tables."""
    print("=" * 70)
    print("WORLD MEMORY SYSTEM — SIMULATION DATABASE SUMMARY")
    print("=" * 70)

    # Layer 1: stats table (write-path) + layer1_stats (read-path)
    row = conn.execute("SELECT COUNT(*), SUM(count), SUM(total) FROM stats").fetchone()
    l1_tagged = conn.execute("SELECT COUNT(*) FROM layer1_stats").fetchone()[0]
    l1_tags = conn.execute("SELECT COUNT(*) FROM layer1_tags").fetchone()[0]
    print(f"\nLayer 1 (Stats): {row[0]} keys, {int(row[1] or 0)} total counts, {row[2] or 0:.0f} total values")
    print(f"  layer1_stats: {l1_tagged} rows with {l1_tags} structured tags")
    print("  Top 10 by count:")
    for r in conn.execute("SELECT key, count, total FROM stats ORDER BY count DESC LIMIT 10"):
        print(f"    {r[0]:45s} count={r[1]:>6d}  total={r[2]:>10.1f}")
    # Sample tag query
    print("  Tag query example (domain:combat):")
    for r in conn.execute("""
        SELECT s.key, s.count FROM layer1_stats s
        JOIN layer1_tags t ON t.stat_id = s.id
        WHERE t.tag_category = 'domain' AND t.tag_value = 'combat'
        ORDER BY s.count DESC LIMIT 5
    """):
        print(f"    {r[0]:45s} count={r[1]}")

    # Raw events
    row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    print(f"\nRaw Event Pipeline: {row[0]} events")
    for r in conn.execute("SELECT event_type, COUNT(*) c FROM events GROUP BY event_type ORDER BY c DESC LIMIT 8"):
        print(f"    {r[0]:25s}: {r[1]}")

    # Threshold tracking
    row = conn.execute("SELECT COUNT(*) FROM occurrence_counts WHERE count > 0").fetchone()
    print(f"  Stream counters: {row[0]}")
    row = conn.execute("SELECT COUNT(*) FROM regional_counters WHERE count > 0").fetchone()
    print(f"  Regional counters: {row[0]}")

    # Layers 2-7: all use layerN_events + layerN_tags
    for layer in range(2, 8):
        table = f"layer{layer}_events"
        tag_table = f"layer{layer}_tags"
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            tag_count = conn.execute(f"SELECT COUNT(*) FROM {tag_table}").fetchone()[0]
        except Exception:
            continue
        if row[0] == 0:
            print(f"\nLayer {layer}: 0 entries")
            continue

        layer_names = {2: "Evaluator Outputs", 3: "Cross-Domain Patterns",
                      4: "Province Summaries", 5: "Realm State",
                      6: "Intercountry", 7: "World Narrative"}
        print(f"\nLayer {layer} ({layer_names.get(layer, '')}): {row[0]} entries, {tag_count} structured tags")

        if layer == 2:
            for r in conn.execute(f"SELECT category, COUNT(*) c FROM {table} GROUP BY category ORDER BY c DESC"):
                print(f"    {r[0]:30s}: {r[1]}")
            print("  Sample narratives:")
            for r in conn.execute(f"SELECT narrative, severity FROM {table} ORDER BY game_time LIMIT 3"):
                print(f"    [{r[1]:>12s}] {r[0][:80]}")
        else:
            for r in conn.execute(f"SELECT narrative, severity FROM {table}"):
                print(f"    [{r[1]:>12s}] {r[0][:85]}")

        # Show unique tag categories at this layer
        cats = conn.execute(f"SELECT DISTINCT tag_category FROM {tag_table} ORDER BY tag_category").fetchall()
        if cats:
            print(f"  Tag categories: {', '.join(r[0] for r in cats)}")

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
