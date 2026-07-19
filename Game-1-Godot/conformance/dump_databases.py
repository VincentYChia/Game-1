"""Loader-parity dump — Phase 1 oracle.

Boots the data layer EXACTLY like game_engine.py:135-182 (tranche-1 subset),
then dumps each database's normalized in-memory state to
goldens/db_parity/*.json. The C# loaders must reproduce these dumps from the
same content files (empty diff = parity).

Tranche 1: materials, equipment (raw store), recipes, skills, titles
(minus the UnlockRequirements object graph — typed in Phase 2), classes,
translations. Update-N overlay included (boot loads it last).

Usage:  python Game-1-Godot/conformance/dump_databases.py
"""
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = REPO / "Game-1-modular"
OUT = HERE / "goldens" / "db_parity"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(SRC))
os.chdir(SRC)


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


SHA = git_sha()


def meta(source: str, note: str = "") -> dict:
    m = {"generated": date.today().isoformat(), "git_sha": SHA, "source": source,
         "doctrine": "dumped from the live Python loaders after the boot sequence"}
    if note:
        m["note"] = note
    return m


def write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False)
    print(f"  wrote {path.relative_to(REPO)}")


def boot() -> dict:
    """Replicate game_engine.py:135-182 for the tranche-1 databases."""
    from core.paths import get_resource_path
    from data.databases.material_db import MaterialDatabase
    from data.databases.translation_db import TranslationDatabase
    from data.databases.recipe_db import RecipeDatabase
    from data.databases.equipment_db import EquipmentDatabase
    from data.databases.title_db import TitleDatabase
    from data.databases.class_db import ClassDatabase
    from data.databases.skill_db import SkillDatabase
    from data.databases.update_loader import load_all_updates

    # game_engine.py:135 — resource nodes load FIRST (world gen depends on it)
    from data.databases.resource_node_db import ResourceNodeDatabase
    res_db = ResourceNodeDatabase.get_instance()
    res_db.load_from_files()

    mat_db = MaterialDatabase.get_instance()
    mat_db.load_from_files()  # sacred 7-call sequence + generated overlay

    trans_db = TranslationDatabase.get_instance()
    trans_db.load_from_files()

    recipe_db = RecipeDatabase.get_instance()
    recipe_db.load_from_files()

    from data.databases.placement_db import PlacementDatabase
    placement_db = PlacementDatabase.get_instance()
    placement_db.load_from_files()

    equip_db = EquipmentDatabase.get_instance()
    for rel in ("items.JSON/items-engineering-1.JSON",
                "items.JSON/items-smithing-2.JSON",
                "items.JSON/items-tools-1.JSON",
                "items.JSON/items-alchemy-1.JSON",
                "items.JSON/items-testing-tags.JSON"):
        p = get_resource_path(rel)
        if p.exists():
            equip_db.load_from_file(str(p))

    title_db = TitleDatabase.get_instance()
    title_db.load_from_files()

    class_db = ClassDatabase.get_instance()
    class_db.load_from_file(str(get_resource_path("progression/classes-1.JSON")))

    skill_db = SkillDatabase.get_instance()
    skill_db.load_from_files()

    # CombatManager.load_config loads sacred hostiles BEFORE Update-N overlay
    from Combat.enemy import EnemyDatabase
    EnemyDatabase.get_instance().load_from_files()

    # game_engine.py:177 — sacred skill-unlocks BEFORE Update-N overlay
    from data.databases.skill_unlock_db import SkillUnlockDatabase
    su_db = SkillUnlockDatabase.get_instance()
    su_db.load_from_file(str(get_resource_path("progression/skill-unlocks.JSON")))

    from data.databases.npc_db import NPCDatabase
    npc_db = NPCDatabase.get_instance()
    npc_db.load_from_files()  # boot does NOT merge generated files (reload-only)

    # Lazy-loaded in-game on first get_instance(); explicit here.
    from data.databases.chunk_template_db import ChunkTemplateDatabase
    chunk_db = ChunkTemplateDatabase.get_instance()

    from data.databases.world_generation_db import WorldGenerationConfig
    wg_db = WorldGenerationConfig.get_instance()

    # Update-N overlay LAST, exactly like boot (also touches enemy /
    # skill-unlock DBs — harmless here, they just load too).
    load_all_updates(get_resource_path(""))

    return {
        "materials": mat_db, "translations": trans_db, "recipes": recipe_db,
        "equipment": equip_db, "titles": title_db, "classes": class_db,
        "skills": skill_db, "placements": placement_db,
        "resource_nodes": res_db, "npcs": npc_db, "chunk_templates": chunk_db,
        "world_generation": wg_db, "skill_unlocks": su_db,
    }


def dump_all(dbs: dict) -> None:
    write("materials.json", {
        "_meta": meta("data/databases/material_db.py (sacred sequence + "
                      "generated overlay + Update-N)"),
        "count": len(dbs["materials"].materials),
        "materials": {mid: asdict(m)
                      for mid, m in sorted(dbs["materials"].materials.items())},
    })

    write("equipment.json", {
        "_meta": meta("data/databases/equipment_db.py (raw JSON dict store; "
                      "EquipmentItem materialization is Phase 2)"),
        "count": len(dbs["equipment"].items),
        "items": {iid: d for iid, d in sorted(dbs["equipment"].items.items())},
    })

    write("recipes.json", {
        "_meta": meta("data/databases/recipe_db.py (5 discipline files, "
                      "3 output dialects + Update-N)"),
        "count": len(dbs["recipes"].recipes),
        "recipes": {rid: asdict(r)
                    for rid, r in sorted(dbs["recipes"].recipes.items())},
        "by_station": {station: [r.recipe_id for r in lst]
                       for station, lst in dbs["recipes"].recipes_by_station.items()},
    })

    write("skills.json", {
        "_meta": meta("data/databases/skill_db.py (sacred glob + generated "
                      "overlay + Update-N)"),
        "count": len(dbs["skills"].skills),
        "skills": {sid: asdict(s)
                   for sid, s in sorted(dbs["skills"].skills.items())},
    })

    def title_row(t):
        d = {k: v for k, v in vars(t).items() if k != "requirements"}
        return d

    write("titles.json", {
        "_meta": meta("data/databases/title_db.py",
                      note="'requirements' (UnlockRequirements object graph) is "
                           "EXCLUDED from Phase-1 parity — typed in Phase 2 with "
                           "ICharacterQuery; every other field is gated here"),
        "count": len(dbs["titles"].titles),
        "titles": {tid: title_row(t)
                   for tid, t in sorted(dbs["titles"].titles.items())},
    })

    write("classes.json", {
        "_meta": meta("data/databases/class_db.py"),
        "count": len(dbs["classes"].classes),
        "classes": {cid: asdict(c)
                    for cid, c in sorted(dbs["classes"].classes.items())},
    })

    write("placements.json", {
        "_meta": meta("data/databases/placement_db.py (5 discipline parsers)"),
        "count": len(dbs["placements"].placements),
        "placements": {rid: asdict(p)
                       for rid, p in sorted(dbs["placements"].placements.items())},
    })

    res = dbs["resource_nodes"]
    from data.models.resources import ResourceDrop, ResourceNodeDefinition
    qty_table = {q: list(ResourceDrop("x", q, "guaranteed").get_quantity_range())
                 for q in ["few", "several", "many", "abundant", "__unknown__"]}
    chance_table = {c: ResourceDrop("x", "few", c).get_chance_value()
                    for c in ["guaranteed", "high", "moderate", "low", "rare",
                              "improbable", "__unknown__"]}
    respawn_table = {r: ResourceNodeDefinition(
                        "x", "x", "tree", 1, "axe", 100,
                        respawn_time=r).get_respawn_seconds()
                     for r in ["quick", "fast", "normal", "slow", "very_slow",
                               "__unknown__"]}
    write("resource_nodes.json", {
        "_meta": meta("data/databases/resource_node_db.py + models/resources.py "
                      "(conversion tables EXECUTED from the live model)"),
        "count": len(res.nodes),
        "nodes": {rid: asdict(n) for rid, n in sorted(res.nodes.items())},
        "category_caches": {
            "trees": [n.resource_id for n in res._trees],
            "ores": [n.resource_id for n in res._ores],
            "stones": [n.resource_id for n in res._stones],
        },
        "tier_map": dict(sorted(res._tier_map.items())),
        "quantity_ranges": qty_table,
        "chance_values": chance_table,
        "respawn_seconds": respawn_table,
        "no_respawn_when_null": ResourceNodeDefinition(
            "x", "x", "tree", 1, "axe", 100).get_respawn_seconds() is None,
    })

    npcs = dbs["npcs"]
    write("npcs_quests.json", {
        "_meta": meta("data/databases/npc_db.py (v3 path; boot state — "
                      "generated merge is reload-only)"),
        "npc_count": len(npcs.npcs),
        "quest_count": len(npcs.quests),
        "source_version": npcs.source_version,
        "quest_source_version": npcs.quest_source_version,
        "npcs": {nid: asdict(n) for nid, n in sorted(npcs.npcs.items())},
        "quests": {qid: asdict(q) for qid, q in sorted(npcs.quests.items())},
    })

    chunks = dbs["chunk_templates"]
    import data.databases.chunk_template_db as ctd
    write("chunk_templates.json", {
        "_meta": meta("data/databases/chunk_template_db.py (sacred + generated "
                      "overlay + geo dispatch bridge + geoTypes auto-register)"),
        "count": len(chunks.templates),
        "templates": {ct: asdict(t) for ct, t in sorted(chunks.templates.items())},
        "geo_dispatch": chunks.geo_dispatch_map(),
        "stats": chunks.stats(),
        "density_weights": dict(ctd.DENSITY_WEIGHTS),
        "tier_bias_order": dict(ctd.TIER_BIAS_ORDER),
    })

    wg = dbs["world_generation"]
    write("world_generation.json", {
        "_meta": meta("data/databases/world_generation_db.py (resolved config "
                      "incl. dilutive normalization; zone lookups executed)"),
        "loaded_from_file": wg.loaded_from_file,
        "chunk_loading": asdict(wg.chunk_loading),
        "biome_distribution": asdict(wg.biome_distribution),
        "biome_clustering": asdict(wg.biome_clustering),
        "danger_zones": asdict(wg.danger_zones),
        "spawn_area": asdict(wg.spawn_area),
        "resource_spawning": asdict(wg.resource_spawning),
        "water_chunks": asdict(wg.water_chunks),
        "dungeon_spawning": asdict(wg.dungeon_spawning),
        "chunk_unloading": asdict(wg.chunk_unloading),
        "debug": asdict(wg.debug),
        "danger_distribution_by_distance": {
            str(d): asdict(wg.get_danger_distribution(d))
            for d in [0, 1, 2, 3, 5, 10, 11, 50]},
        "resource_config_by_level": {
            lvl: asdict(wg.get_resource_config(lvl))
            for lvl in ["peaceful", "dangerous", "rare", "unknown"]},
    })

    # Quest archive: in-memory runtime store — BEHAVIORAL fixture (synthetic
    # records through the real class, query results dumped).
    from data.databases.quest_archive_db import (ArchivedQuestRecord,
                                                 QuestArchiveDatabase)
    QuestArchiveDatabase.reset()
    qa = QuestArchiveDatabase.get_instance()
    _recs = [
        ArchivedQuestRecord("q_vendetta_001", {"quest_id": "q_vendetta_001"},
                            100.0, 400.0, 300.0, "succeeded",
                            {"experience": 250}, ["captain_vell"],
                            ["frost_wyrmling"], ["vendetta", "moors"],
                            "thread_a", 3),
        ArchivedQuestRecord("q_gather_002", {"quest_id": "q_gather_002"},
                            50.0, 900.0, 850.0, "failed", {},
                            ["overseer_halda"], ["glacier_tin"],
                            ["moors"], None, 5),
        ArchivedQuestRecord("q_hunt_003", {"quest_id": "q_hunt_003"},
                            10.0, 600.0, 590.0, "succeeded", {"gold": 40},
                            ["captain_vell", "overseer_halda"],
                            ["frost_wyrmling", "icebound_quarry"],
                            ["vendetta", "hunt"], "thread_a", 4),
        ArchivedQuestRecord("q_abandon_004", {"quest_id": "q_abandon_004"},
                            700.0, 750.0, 50.0, "abandoned", {}, [], [],
                            ["moors", "vendetta"], None, 6),
    ]
    for r in _recs:
        qa.archive(r)

    def ids(records):
        return [r.quest_id for r in records]

    write("quest_archive_behavior.json", {
        "_meta": meta("data/databases/quest_archive_db.py (behavioral fixture: "
                      "synthetic records through the REAL class, queries executed)"),
        "records_in": [r.to_dict() for r in _recs],
        "roundtrip": [ArchivedQuestRecord.from_dict(r.to_dict()).to_dict()
                      for r in _recs],
        "query_by_tags_all": ids(qa.query_by_tags(["vendetta", "moors"], match_all=True)),
        "query_by_tags_any": ids(qa.query_by_tags(["vendetta", "moors"], match_all=False)),
        "query_by_tags_empty": ids(qa.query_by_tags([])),
        "query_by_tags_limit1": ids(qa.query_by_tags(["moors"], match_all=False, limit=1)),
        "recent_archived_2": ids(qa.recent_archived(2)),
        "query_by_npc": ids(qa.query_by_npc("captain_vell")),
        "query_by_entity": ids(qa.query_by_entity("frost_wyrmling")),
        "query_by_result_succeeded": ids(qa.query_by_result("succeeded")),
        "count": qa.count(),
    })

    from data.databases.visual_config_db import get_visual_config
    vc = get_visual_config()
    vc_values = {
        "damage_number_lifetime_ms": vc.damage_number_lifetime_ms,
        "damage_number_velocity_y": vc.damage_number_velocity_y,
        "damage_number_horizontal_spread": vc.damage_number_horizontal_spread,
        "damage_number_gravity": vc.damage_number_gravity,
        "damage_number_shrink_rate": vc.damage_number_shrink_rate,
        "damage_number_crit_scale": vc.damage_number_crit_scale,
        "damage_number_crit_color": list(vc.damage_number_crit_color),
        "damage_number_stack_offset": vc.damage_number_stack_offset,
        "player_radius_tiles": vc.player_radius_tiles,
        "player_color": list(vc.player_color),
        "player_outline_color": list(vc.player_outline_color),
        "facing_indicator_length": vc.facing_indicator_length,
        "facing_indicator_color": list(vc.facing_indicator_color),
        "shadow_enabled": vc.shadow_enabled,
        "shadow_alpha": vc.shadow_alpha,
        "shadow_scale": vc.shadow_scale,
        "idle_bob_amplitude": vc.idle_bob_amplitude,
        "idle_bob_period_ms": vc.idle_bob_period_ms,
        "boss_glow_color": list(vc.boss_glow_color),
        "death_fade_duration_ms": vc.death_fade_duration_ms,
        "death_shrink_factor": vc.death_shrink_factor,
        "corpse_linger_ms": vc.corpse_linger_ms,
        "spawn_fade_in_ms": vc.spawn_fade_in_ms,
        "telegraph_player_color": list(vc.telegraph_player_color),
        "telegraph_enemy_color": list(vc.telegraph_enemy_color),
        "telegraph_pulse_frequency": vc.telegraph_pulse_frequency,
        "max_particles": vc.max_particles,
        "hit_spark_count": list(vc.hit_spark_count),
        "death_burst_count": vc.death_burst_count,
        "shake_decay_rate": vc.shake_decay_rate,
        "shake_max_offset": vc.shake_max_offset,
        "debug_hitbox_color": list(vc.debug_hitbox_color()),
        "debug_hitbox_alpha": vc.debug_hitbox_alpha,
        "debug_hurtbox_color": list(vc.debug_hurtbox_color()),
        "debug_hurtbox_alpha": vc.debug_hurtbox_alpha,
        "debug_iframe_color": list(vc.debug_iframe_color()),
        "debug_show_facing": vc.debug_show_facing,
        "debug_show_attack_phase": vc.debug_show_attack_phase,
    }
    write("visual_config.json", {
        "_meta": meta("data/databases/visual_config_db.py (every accessor "
                      "EXECUTED against the live JSON + defaults)"),
        "values": vc_values,
        "damage_type_colors": {t: list(vc.damage_type_color(t)) for t in
                               ["physical", "fire", "ice", "lightning", "poison",
                                "arcane", "shadow", "holy", "__unknown__"]},
        "damage_special_text": {t: [vc.damage_special_text(t)[0],
                                    list(vc.damage_special_text(t)[1])]
                                for t in ["miss", "block", "dodge", "__unknown__"]},
        "enemy_tier_scale": {str(t): vc.enemy_tier_scale(t) for t in [1, 2, 3, 4, 99]},
        "enemy_tier_glow": {str(t): vc.enemy_tier_has_glow(t) for t in [1, 2, 3, 4, 99]},
        "enemy_tier_glow_intensity": {str(t): vc.enemy_tier_glow_intensity(t)
                                      for t in [1, 2, 3, 4, 99]},
        "enemy_state_colors": {s: list(vc.enemy_state_color(s)) for s in
                               ["idle", "aggro", "attacking", "fleeing", "__unknown__"]},
    })

    from data.databases.map_waypoint_db import MapWaypointConfig
    mw = MapWaypointConfig.get_instance()
    write("map_waypoint.json", {
        "_meta": meta("data/databases/map_waypoint_db.py (resolved config + "
                      "executed lookups)"),
        "loaded": mw.loaded,
        "map_display": asdict(mw.map_display),
        "biome_colors": {k: list(v) for k, v in sorted(mw.biome_colors.items())},
        "player_marker": asdict(mw.player_marker),
        "waypoint_marker": asdict(mw.waypoint_marker),
        "dungeon_marker": asdict(mw.dungeon_marker),
        "waypoint": asdict(mw.waypoint),
        "ui": asdict(mw.ui),
        "biome_color_lookup": {t: list(mw.get_biome_color(t)) for t in
                               ["peaceful_forest", "PEACEFUL_FOREST", "lake",
                                "crystal_cavern", "nonexistent_biome"]},
        "max_waypoints_by_level": {str(lvl): mw.get_max_waypoints_for_level(lvl)
                                   for lvl in range(1, 31)},
    })

    # ── Unlock-condition system: parse + evaluate oracles ────────────────
    from types import SimpleNamespace
    from data.models.unlock_conditions import ConditionFactory

    su_db = dbs["skill_unlocks"]

    def stub_char(level=1, stats=None, activities=None, titles=None, skills=None,
                  quests=None, class_id=None, tracker=None):
        s = dict(strength=0, defense=0, vitality=0, luck=0, agility=0,
                 intelligence=0)
        s.update(stats or {})
        acts = activities or {}
        ttl = set(titles or [])
        sk = set(skills or [])
        q = set(quests or [])
        c = SimpleNamespace(
            leveling=SimpleNamespace(level=level),
            stats=SimpleNamespace(**s),
            activities=SimpleNamespace(get_count=lambda a: acts.get(a, 0)),
            titles=SimpleNamespace(has_title=lambda t: t in ttl),
            skills=SimpleNamespace(known_skills=sk),
            quests=SimpleNamespace(is_quest_completed=lambda x: x in q),
            class_system=SimpleNamespace(
                current_class=SimpleNamespace(class_id=class_id) if class_id else None),
        )
        if tracker is not None:
            c.stat_tracker = tracker
        return c

    STUB_SPECS = {
        "fresh": {},
        "veteran": dict(
            level=20, stats={"strength": 12, "luck": 6},
            activities={"mining": 150, "forestry": 40, "smithing": 60},
            titles=["novice_miner", "apprentice_smith"],
            skills=["power_strike", "mining_focus"],
            quests=["q_tutorial", "q_vendetta_001"], class_id="warrior",
            tracker={"gathering_totals": {"total_ores_mined": 500},
                     "combat_kills": {"total_kills": 75},
                     "crafting_by_discipline": {"smithing": {"total_crafts": 30}}}),
        "no_tracker": dict(level=30, stats={"strength": 30}),
    }
    STUBS = {name: stub_char(**spec) for name, spec in STUB_SPECS.items()}

    REQ_SPECS = {
        "new_level": {"conditions": [{"type": "level", "min_level": 10}]},
        "new_stat_reqs": {"conditions": [{"type": "stat",
                                          "requirements": {"luck": 5, "strength": 10}}]},
        "new_stat_abbrev": {"conditions": [{"type": "stat", "stat_name": "STR",
                                            "min_value": 5}]},
        "new_activity": {"conditions": [{"type": "activity", "activity": "mining",
                                         "min_count": 100}]},
        "new_stat_tracker": {"conditions": [{"type": "stat_tracker",
                                             "stat_path": "combat_kills.total_kills",
                                             "min_value": 50}]},
        "new_title_single": {"conditions": [{"type": "title",
                                             "required_title": "novice_miner"}]},
        "new_skill": {"conditions": [{"type": "skill",
                                      "required_skills": ["power_strike"]}]},
        "new_quest": {"conditions": [{"type": "quest",
                                      "required_quests": ["q_vendetta_001"]}]},
        "new_class": {"conditions": [{"type": "class", "required_class": "warrior"}]},
        "new_unknown_type": {"conditions": [{"type": "nonsense", "x": 1}]},
        "new_title_missing_keys": {"conditions": [{"type": "title"}]},
        "legacy_level_stats": {"characterLevel": 15, "stats": {"strength": 10}},
        "legacy_titles_quests": {"titles": ["novice_miner"],
                                 "requiredTitles": ["apprentice_smith"],
                                 "completedQuests": ["q_tutorial"]},
        "legacy_milestones": {"activityMilestones": [
            {"type": "craft_count", "discipline": "smithing", "count": 25},
            {"type": "kill_count", "count": 50},
            {"type": "gather_count", "count": 101}]},
        # keys pre-sorted: the fixture dumps with sort_keys=True, and the C#
        # test re-parses the spec FROM the fixture — insertion order must
        # survive the sorted dump for this order-sensitive legacy dict
        "legacy_activities": {"activities": {"bossesDefeated": 3, "oresMined": 100}},
        "empty": {},
    }

    reqs = {name: ConditionFactory.create_requirements_from_json(spec)
            for name, spec in REQ_SPECS.items()}

    write("unlock_conditions.json", {
        "_meta": meta("data/models/unlock_conditions.py (parse via real "
                      "ConditionFactory; evaluation via real condition classes "
                      "against stub characters)"),
        "specs": REQ_SPECS,
        "stub_specs": STUB_SPECS,
        "parsed": {name: {"to_dict": r.to_dict(),
                          "description": r.get_description()}
                   for name, r in reqs.items()},
        "evaluations": {name: {stub_name: {
                            "met": r.evaluate(c),
                            "missing_count": len(r.get_missing_conditions(c))}
                        for stub_name, c in STUBS.items()}
                        for name, r in reqs.items()},
        "title_requirements": {tid: {"to_dict": t.requirements.to_dict(),
                                     "description": t.requirements.get_description()}
                               for tid, t in sorted(dbs["titles"].titles.items())},
        "skill_unlocks": {uid: {
            "skill_id": u.skill_id,
            "unlock_method": u.unlock_method,
            "narrative": u.narrative,
            "category": u.category,
            "trigger": {"type": u.trigger.type,
                        "trigger_value": u.trigger.trigger_value,
                        "message": u.trigger.message},
            "cost": {"gold": u.cost.gold, "materials": u.cost.materials,
                     "skill_points": u.cost.skill_points},
            "requirements_to_dict": u.requirements.to_dict(),
            "requirements_description": u.requirements.get_description(),
        } for uid, u in sorted(su_db.unlocks.items())},
        "unlocks_by_skill": {sid: u.unlock_id
                             for sid, u in sorted(su_db.unlocks_by_skill.items())},
    })

    # ── Equipment materialization + EquipmentItem behaviors ──────────────
    from data.models.equipment import EquipmentItem
    from entities.components.weapon_tag_calculator import WeaponTagModifiers
    from core.crafting_tag_processor import (SmithingTagProcessor,
                                             EnchantingTagProcessor)

    def item_state(it):
        d = dict(vars(it))
        d["damage"] = list(d["damage"])
        return d

    materialized = {}
    for iid in sorted(dbs["equipment"].items):
        it = dbs["equipment"].create_equipment_from_id(iid)
        if it is not None:
            materialized[iid] = item_state(it)

    def synth(damage=(10, 20), defense=0, cur=100, mx=100, item_type="weapon",
              efficiency=1.0, bonuses=None, ench=None, slot="mainHand"):
        it = EquipmentItem("synth", "Synth", 1, "common", slot,
                           damage=damage, defense=defense,
                           durability_current=cur, durability_max=mx,
                           item_type=item_type)
        it.efficiency = efficiency
        it.bonuses = bonuses or {}
        it.enchantments = ench or []
        return it

    dur_grid = [(100, 100), (75, 100), (60, 100), (50, 100), (49, 100),
                (25, 100), (20, 100), (1, 100), (0, 100)]
    effectiveness = {f"{c}/{m}": synth(cur=c, mx=m).get_effectiveness()
                     for c, m in dur_grid}
    urgency = {f"{c}/{m}": synth(cur=c, mx=m).get_repair_urgency()
               for c, m in dur_grid}

    r1 = synth(cur=10, mx=100)
    rep_amount = r1.repair(amount=25)
    r2 = synth(cur=10, mx=100)
    rep_percent = r2.repair(percent=0.5)
    r3 = synth(cur=10, mx=100)
    rep_full = r3.repair()

    dmg_cases = {
        "plain": synth().get_actual_damage(),
        "crafted_mult": synth(bonuses={"damage_multiplier": 0.25}).get_actual_damage(),
        "tool_efficiency": synth(item_type="tool", efficiency=1.2).get_actual_damage(),
        "weapon_efficiency_ignored": synth(item_type="weapon", efficiency=1.2).get_actual_damage(),
        "ench_mult": synth(ench=[{"enchantment_id": "sharpness_1", "name": "S",
                                  "effect": {"type": "damage_multiplier", "value": 0.15}}]
                           ).get_actual_damage(),
        "worn_30": synth(cur=30).get_actual_damage(),
        "broken_0": synth(cur=0).get_actual_damage(),
        "stacked": synth(cur=30, item_type="tool", efficiency=1.2,
                         bonuses={"damage_multiplier": 0.25},
                         ench=[{"enchantment_id": "sharpness_1", "name": "S",
                                "effect": {"type": "damage_multiplier", "value": 0.15}}]
                         ).get_actual_damage(),
    }
    def_cases = {
        "plain": synth(damage=(0, 0), defense=50, slot="chestplate",
                       item_type="armor").get_defense_with_enchantments(),
        "crafted_and_ench": synth(damage=(0, 0), defense=50, slot="chestplate",
                                  item_type="armor",
                                  bonuses={"defense_multiplier": -0.1},
                                  ench=[{"enchantment_id": "protection_1", "name": "P",
                                         "effect": {"type": "defense_multiplier",
                                                    "value": 0.2}}]
                                  ).get_defense_with_enchantments(),
        "worn_10": synth(damage=(0, 0), defense=50, slot="chestplate",
                         item_type="armor", cur=10).get_defense_with_enchantments(),
    }

    seq_item = synth()
    ench_seq = []
    for eid, name, effect in [
        ("sharpness_2", "Sharpness II", {"type": "damage_multiplier", "value": 0.2}),
        ("sharpness_2", "Sharpness II", {"type": "damage_multiplier", "value": 0.2}),
        ("sharpness_1", "Sharpness I", {"type": "damage_multiplier", "value": 0.1}),
        ("sharpness_3", "Sharpness III", {"type": "damage_multiplier", "value": 0.3}),
        ("frost_1", "Frost I", {"type": "slow", "value": 0.3,
                                "conflictsWith": ["sharpness_3"]}),
    ]:
        ok, reason = seq_item.apply_enchantment(eid, name, effect)
        ench_seq.append({"apply": eid, "ok": ok, "reason": reason,
                         "now": [e["enchantment_id"] for e in seq_item.enchantments]})

    type_grid = []
    for slot, damage, itype in [("mainHand", (5, 9), "weapon"),
                                ("mainHand", (5, 9), "shield"),
                                ("mainHand", (0, 0), ""),
                                ("mainHand", (5, 9), ""),
                                ("tool", (0, 0), ""),
                                ("helmet", (0, 0), ""),
                                ("accessory", (0, 0), ""),
                                ("offHand", (0, 0), "invalid_type")]:
        it = synth(damage=damage, slot=slot, item_type=itype)
        type_grid.append({"slot": slot, "damage": list(damage),
                          "item_type_in": itype, "resolved": it._get_item_type()})

    can_equip_stub = SimpleNamespace(
        leveling=SimpleNamespace(level=4),
        stats=SimpleNamespace(strength=8, defense=0, vitality=0, luck=0,
                              agility=3, intelligence=0))
    ce_cases = {}
    for name, reqs in [("level_fail", {"level": 5}),
                       ("level_ok", {"level": 4}),
                       ("stat_fail", {"stats": {"STR": 10}}),
                       ("stat_ok", {"stats": {"str": 8}}),
                       ("dex_alias", {"stats": {"DEX": 5}}),
                       ("combined_fail", {"level": 3, "stats": {"AGI": 4}}),
                       ("empty", {})]:
        it = synth()
        it.requirements = reqs
        ok, reason = it.can_equip(can_equip_stub)
        ce_cases[name] = {"ok": ok, "reason": reason}

    TAG_SETS = [["2H"], ["versatile"], ["1H"], ["2H", "fast", "precision"],
                ["reach"], ["armor_breaker"], ["crushing"], ["cleaving"],
                ["fast", "reach", "crushing"], []]
    wtm = {"-".join(t) or "none": {
        "dmg_no_off": WeaponTagModifiers.get_damage_multiplier(t, False),
        "dmg_off": WeaponTagModifiers.get_damage_multiplier(t, True),
        "speed": WeaponTagModifiers.get_attack_speed_bonus(t),
        "crit": WeaponTagModifiers.get_crit_chance_bonus(t),
        "range": WeaponTagModifiers.get_range_bonus(t),
        "pen": WeaponTagModifiers.get_armor_penetration(t),
        "vs_armored": WeaponTagModifiers.get_damage_vs_armored_bonus(t),
        "cleaving": WeaponTagModifiers.has_cleaving(t),
    } for t in TAG_SETS}

    SLOT_SETS = [["helmet"], ["chestplate", "armor"], ["pickaxe", "tool"],
                 ["axe"], ["shovel"], ["weapon"], ["shield"], ["accessory"],
                 ["armor"], ["tool"], ["basic", "starter"], []]
    slots = {"-".join(t) or "none": SmithingTagProcessor.get_equipment_slot(t)
             for t in SLOT_SETS}

    ench_rules = {}
    for tags in [["universal"], ["weapon"], ["armor"], ["tool"], ["basic"], []]:
        for itype in ["weapon", "armor", "tool"]:
            ok, reason = EnchantingTagProcessor.can_apply_to_item(tags, itype)
            ench_rules[f"{'-'.join(tags) or 'none'}|{itype}"] = {"ok": ok,
                                                                "reason": reason}

    write("equipment_items.json", {
        "_meta": meta("equipment_db.create_equipment_from_id + models/equipment.py "
                      "+ weapon_tag_calculator + tag processors (ALL EXECUTED)"),
        "count": len(materialized),
        "items": materialized,
        "effectiveness": effectiveness,
        "repair_urgency": urgency,
        "repair": {"amount_25": {"restored": rep_amount, "now": r1.durability_current},
                   "percent_50": {"restored": rep_percent, "now": r2.durability_current},
                   "full": {"restored": rep_full, "now": r3.durability_current}},
        "actual_damage": {k: list(v) for k, v in dmg_cases.items()},
        "defense": def_cases,
        "enchant_sequence": ench_seq,
        "item_type_grid": type_grid,
        "can_equip": ce_cases,
        "weapon_tag_modifiers": wtm,
        "slot_inference": slots,
        "enchant_applicability": ench_rules,
    })

    # ── Inventory + buffs: behavioral fixtures through the REAL classes ──
    from entities.components.inventory import Inventory, ItemStack
    from entities.components.buffs import ActiveBuff, BuffManager

    def slots_state(inv):
        out = []
        for s in inv.slots:
            if s is None:
                out.append(None)
            else:
                out.append({"item_id": s.item_id, "quantity": s.quantity,
                            "max_stack": s.max_stack, "rarity": s.rarity,
                            "has_equipment_data": s.equipment_data is not None,
                            "crafted_stats": s.crafted_stats})
        return out

    # Real ids from the booted DBs: a stackable material + an equipment item
    mat_id = "oak_log" if "oak_log" in dbs["materials"].materials else \
        sorted(dbs["materials"].materials)[0]
    mat_stack = dbs["materials"].materials[mat_id].max_stack
    equip_id = sorted(dbs["equipment"].items)[0]

    inv_scenarios = {}

    inv = Inventory(max_slots=6)
    ok1 = inv.add_item(mat_id, mat_stack * 2 + 5)
    inv_scenarios["stack_overflow"] = {"ok": ok1, "slots": slots_state(inv),
                                       "count": inv.get_item_count(mat_id)}

    inv = Inventory(max_slots=6)
    ok2 = inv.add_item(equip_id, 2)
    inv_scenarios["equipment_no_stack"] = {"ok": ok2, "slots": slots_state(inv)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, 10)
    inv.add_item(mat_id, 10, rarity="rare")
    inv.add_item(mat_id, 10, crafted_stats={"damage_multiplier": 0.1})
    inv_scenarios["rarity_and_stats_split"] = {"slots": slots_state(inv),
                                               "count": inv.get_item_count(mat_id)}

    inv = Inventory(max_slots=2)
    ok3 = inv.add_item(mat_id, mat_stack * 3)
    inv_scenarios["full_inventory_fail"] = {"ok": ok3, "slots": slots_state(inv)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, mat_stack + 10)
    removed_ok = inv.remove_item(mat_id, mat_stack + 3)
    removed_fail = inv.remove_item(mat_id, 100)
    inv_scenarios["remove_across_stacks"] = {
        "removed_ok": removed_ok, "removed_fail": removed_fail,
        "slots": slots_state(inv), "count": inv.get_item_count(mat_id),
        "has_5": inv.has_item(mat_id, 5)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, 20)
    inv.add_item(equip_id, 1)
    inv.start_drag(0)
    inv.end_drag(1)  # onto equipment -> swap
    inv_scenarios["drag_swap"] = {"slots": slots_state(inv)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, 20)
    inv.slots[2] = ItemStack(mat_id, 30)
    inv.start_drag(0)
    inv.end_drag(2)  # onto stackable -> merge
    inv_scenarios["drag_merge"] = {"slots": slots_state(inv)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, 20)
    inv.start_drag(0)
    inv.end_drag(99)  # out of range -> return to origin
    inv_scenarios["drag_out_of_range"] = {"slots": slots_state(inv)}

    inv = Inventory(max_slots=6)
    inv.add_item(mat_id, 20)
    inv.start_drag(0)
    inv.cancel_drag()
    inv_scenarios["drag_cancel"] = {"slots": slots_state(inv)}

    def mk_buff(bid, etype, cat, value, dur=30.0, consume=False):
        return ActiveBuff(bid, bid, etype, cat, "moderate", value, dur, dur,
                          consume_on_use=consume)

    bm = BuffManager()
    bm.add_buff(mk_buff("b1", "empower", "combat", 0.5))
    bm.add_buff(mk_buff("b2", "empower", "combat", 0.25))
    bm.add_buff(mk_buff("b3", "empower", "mining", 1.0))
    bm.add_buff(mk_buff("b4", "quicken", "movement", 0.15))
    bm.add_buff(mk_buff("b5", "fortify", "defense", 20.0))
    buff_bonuses = {
        "empower_combat": bm.get_total_bonus("empower", "combat"),
        "damage_combat": bm.get_damage_bonus("combat"),
        "movement": bm.get_movement_speed_bonus(),
        "defense": bm.get_defense_bonus(),
        "missing": bm.get_total_bonus("empower", "fishing"),
    }

    bm2 = BuffManager()
    short = mk_buff("short", "empower", "combat", 0.5, dur=1.0)
    longer = mk_buff("long", "empower", "combat", 0.25, dur=10.0)
    bm2.add_buff(short)
    bm2.add_buff(longer)
    bm2.update(0.6)
    tick1 = {"active": [b.buff_id for b in bm2.active_buffs],
             "short_progress": short.get_progress_percent()}
    bm2.update(0.6)
    tick2 = {"active": [b.buff_id for b in bm2.active_buffs]}

    bm3 = BuffManager()
    bm3.add_buff(mk_buff("c1", "empower", "combat", 0.5, consume=True))
    bm3.add_buff(mk_buff("c2", "empower", "mining", 0.5, consume=True))
    bm3.add_buff(mk_buff("c3", "empower", "smithing", 0.5, consume=True))
    bm3.add_buff(mk_buff("c4", "empower", "combat", 0.5, consume=False))
    bm3.consume_buffs_for_action("attack")
    consume_attack = [b.buff_id for b in bm3.active_buffs]
    bm3.consume_buffs_for_action("gather")
    consume_gather = [b.buff_id for b in bm3.active_buffs]
    bm3.consume_buffs_for_action("craft", category="smithing")
    consume_craft = [b.buff_id for b in bm3.active_buffs]

    write("inventory_buffs.json", {
        "_meta": meta("entities/components/inventory.py + buffs.py "
                      "(scenarios EXECUTED through the real classes with the "
                      "booted databases)"),
        "material_id": mat_id,
        "material_max_stack": mat_stack,
        "equipment_id": equip_id,
        "inventory": inv_scenarios,
        "buff_bonuses": buff_bonuses,
        "buff_tick1": tick1,
        "buff_tick2": tick2,
        "consume_after_attack": consume_attack,
        "consume_after_gather": consume_gather,
        "consume_after_craft_smithing": consume_craft,
    })

    # ── Status effects: behavioral fixtures through the REAL classes ─────
    from entities.status_manager import (StatusEffectManager,
                                         add_status_manager_to_entity)

    def target(**overrides):
        t = SimpleNamespace(current_health=200.0, max_health=200.0,
                            speed=5.0, attack_speed=1.0, name="stub")
        for k, v in overrides.items():
            setattr(t, k, v)
        add_status_manager_to_entity(t)
        return t

    def effects_state(mgr):
        return [{"status_id": e.status_id, "stacks": e.stacks,
                 "duration": e.duration,
                 "duration_remaining": e.duration_remaining}
                for e in mgr.active_effects]

    st = {}

    t = target()
    m = t.status_manager
    m.apply_status("burn", {"burn_duration": 4.0, "burn_damage_per_second": 10.0})
    hp = []
    for _ in range(3):
        m.update(1.0)
        hp.append(t.current_health)
    m.update(1.5)
    st["burn_dot"] = {"hp_ticks": hp, "hp_final": t.current_health,
                      "effects_after_expiry": effects_state(m)}

    t = target()
    m = t.status_manager
    for _ in range(5):  # additive, default max 3
        m.apply_status("burn", {"burn_duration": 4.0, "burn_damage_per_second": 10.0})
    m.update(1.0)
    st["burn_stacking"] = {"effects": effects_state(m), "hp": t.current_health}

    t = target()
    m = t.status_manager
    for _ in range(3):
        m.apply_status("poison", {"poison_duration": 6.0})
    m.update(1.0)
    st["poison_superlinear"] = {"effects": effects_state(m), "hp": t.current_health}

    t = target()
    m = t.status_manager
    m.apply_status("shock", {"shock_duration": 6.0, "shock_damage_per_tick": 6.0,
                             "shock_tick_rate": 2.0})
    cadence = []
    for dt_step in [1.0, 1.0, 0.5, 1.5, 1.0]:
        m.update(dt_step)
        cadence.append(t.current_health)
    st["shock_cadence"] = {"hp_after_steps": cadence}

    t = target()
    m = t.status_manager
    m.apply_status("freeze", {"freeze_duration": 2.0})
    frozen_speed = t.speed
    frozen_flag = t.is_frozen
    m.update(2.5)
    st["freeze_restore"] = {"speed_during": frozen_speed, "flag_during": frozen_flag,
                            "speed_after": t.speed, "flag_after": t.is_frozen}

    t = target()
    m = t.status_manager
    m.apply_status("slow", {"slow_duration": 5.0, "slow_percent": 0.4})
    slowed = t.speed
    m.apply_status("chill", {"chill_duration": 5.0, "slow_percent": 0.4})
    st["slow_then_chill_alias"] = {"speed_after_slow": slowed,
                                   "speed_after_chill": t.speed,
                                   "effects": effects_state(m)}

    t = target()
    m = t.status_manager
    m.apply_status("burn", {"burn_duration": 5.0})
    m.apply_status("freeze", {"freeze_duration": 2.0})
    after_freeze = [e.status_id for e in m.active_effects]
    m.apply_status("burn", {"burn_duration": 5.0})
    after_reburn = [e.status_id for e in m.active_effects]
    st["mutual_exclusion"] = {"after_freeze": after_freeze,
                              "after_reburn": after_reburn,
                              "speed_after_reburn": t.speed}

    t = target()
    m = t.status_manager
    m.apply_status("haste", {"haste_duration": 3.0, "haste_speed_bonus": 0.3})
    st["haste"] = {"speed": t.speed, "attack_speed": t.attack_speed}
    m.remove_status("haste")
    st["haste"]["speed_after"] = t.speed
    st["haste"]["attack_speed_after"] = t.attack_speed

    t = target()
    m = t.status_manager
    m.apply_status("empower", {"empower_duration": 3.0, "empower_damage_bonus": 0.25})
    m.apply_status("fortify", {"fortify_duration": 3.0, "fortify_defense_bonus": 0.2})
    m.apply_status("weaken", {"weaken_duration": 3.0, "weaken_percent": 0.25})
    m.apply_status("vulnerable", {"vulnerable_duration": 3.0, "vulnerable_percent": 0.25})
    st["stat_modifiers"] = {
        "empower_mult": t.empower_damage_multiplier,
        "fortify_reduction": t.fortify_damage_reduction,
        "damage_mult": t.damage_multiplier,
        "damage_taken_mult": t.damage_taken_multiplier,
    }
    m.clear_debuffs()
    st["stat_modifiers"]["after_cleanse"] = {
        "damage_mult": t.damage_multiplier,
        "damage_taken_mult": t.damage_taken_multiplier,
        "remaining": [e.status_id for e in m.active_effects],
    }

    t = target(current_health=100.0)
    m = t.status_manager
    m.apply_status("shield", {"shield_duration": 5.0, "shield_amount": 40.0})
    m.apply_status("regeneration", {"regen_duration": 5.0,
                                    "regen_heal_per_second": 30.0})
    m.update(1.0)
    st["shield_and_regen"] = {"shield_amount": t.shield_amount,
                              "hp_after_regen": t.current_health}
    m.update(4.5)
    st["shield_and_regen"]["hp_capped"] = t.current_health
    st["shield_and_regen"]["shield_after_expiry"] = t.shield_amount

    t = target()
    m = t.status_manager
    m.apply_status("stun", {"stun_duration": 2.0})
    m.update(1.5)
    m.apply_status("stun", {"stun_duration": 2.0})  # REFRESH
    st["stun_refresh"] = {"effects": effects_state(m),
                          "cc": m.is_crowd_controlled(),
                          "immobilized": m.is_immobilized(),
                          "silenced": m.is_silenced()}

    t = target(get_effect_resistance=lambda tag: 0.5)
    m = t.status_manager
    m.apply_status("burn", {"burn_duration": 8.0})
    st["resistance_halves_duration"] = {"effects": effects_state(m)}

    t = target()
    ok_unknown = t.status_manager.apply_status("nonsense_status", {"duration": 5.0})
    t.status_manager.apply_status("bleed", {"duration": 7.0})   # generic duration key
    t.status_manager.apply_status("root", {})                    # default 5.0
    st["factory_durations"] = {"unknown_ok": ok_unknown,
                               "effects": effects_state(t.status_manager)}

    # Class skill-affinity bonus (classes.py:33-46) executed per real class
    affinity = {}
    for cid, cdef in sorted(dbs["classes"].classes.items()):
        affinity[cid] = {
            "own_tags": cdef.get_skill_affinity_bonus(list(cdef.tags)),
            "one_match": cdef.get_skill_affinity_bonus([cdef.tags[0].upper()]
                                                       if cdef.tags else []),
            "no_match": cdef.get_skill_affinity_bonus(["zzz_not_a_tag"]),
            "empty": cdef.get_skill_affinity_bonus([]),
        }
    st["class_affinity"] = affinity

    # Equipment manager (8 slots + 2 tool slots) through the real class
    from entities.components.equipment_manager import EquipmentManager

    def eq_char(level=30):
        return SimpleNamespace(
            leveling=SimpleNamespace(level=level),
            stats=SimpleNamespace(strength=0, defense=0, vitality=0, luck=0,
                                  agility=0, intelligence=0),
            recalculate_stats=lambda: None)

    def weapon(iid, hand_type, item_type="weapon", slot="mainHand",
               damage=(10, 20), rng=1.0, tags=None, bonuses=None, reqs=None):
        it = EquipmentItem(iid, iid, 1, "common", slot, damage=damage,
                          durability_current=100, durability_max=100,
                          hand_type=hand_type, item_type=item_type)
        it.range = rng
        it.tags = tags or []
        it.bonuses = bonuses or {}
        it.requirements = reqs or {}
        return it

    def armor(iid, slot, defense):
        return EquipmentItem(iid, iid, 1, "common", slot, damage=(0, 0),
                            defense=defense, durability_current=100,
                            durability_max=100, item_type="armor")

    ch = eq_char()
    em = EquipmentManager()
    hand_rules = {}
    _, r = em.equip(weapon("two_hander", "2H"), ch)
    hand_rules["equip_2h"] = r
    _, r = em.equip(weapon("dagger", "1H", slot="offHand"), ch)
    hand_rules["offhand_vs_2h"] = r
    em.unequip("mainHand", ch)
    _, r = em.equip(weapon("plain_sword", "default"), ch)
    hand_rules["equip_default"] = r
    _, r = em.equip(weapon("shield_item", "default", item_type="shield",
                           slot="offHand"), ch)
    hand_rules["shield_vs_default"] = r
    em.unequip("offHand", ch)
    _, r = em.equip(weapon("dagger2", "1H", slot="offHand"), ch)
    hand_rules["oneh_vs_default"] = r
    em.unequip("mainHand", ch)
    _, r = em.equip(weapon("versatile_spear", "versatile"), ch)
    hand_rules["equip_versatile"] = r
    _, r = em.equip(weapon("dagger3", "1H", slot="offHand"), ch)
    hand_rules["oneh_vs_versatile"] = r
    em.unequip("offHand", ch)
    _, r = em.equip(weapon("versatile2", "versatile", slot="offHand"), ch)
    hand_rules["versatile_vs_versatile"] = r
    em2 = EquipmentManager()
    _, r = em2.equip(weapon("solo_off", "1H", slot="offHand"), ch)
    hand_rules["offhand_alone"] = r
    _, r = em2.equip(weapon("bad_slot", "1H", slot="ring"), ch)
    hand_rules["invalid_slot"] = r
    _, r = em2.equip(weapon("too_strong", "1H", reqs={"level": 99}), eq_char(level=1))
    hand_rules["requirements_fail"] = r

    em3 = EquipmentManager()
    for a_slot, d in [("helmet", 10), ("chestplate", 25), ("leggings", 18),
                      ("boots", 8), ("gauntlets", 6)]:
        em3.equip(armor(f"a_{a_slot}", a_slot, d), ch)
    worn = em3.slots["chestplate"]
    worn.durability_current = 10  # effectiveness kicks in
    equip_queries = {
        "total_defense": em3.get_total_defense(),
        "unarmed_damage": list(EquipmentManager().get_weapon_damage()),
        "no_offhand_damage": list(EquipmentManager().get_weapon_damage("offHand")),
        "unarmed_range": EquipmentManager().get_weapon_range(),
        "no_offhand_range": EquipmentManager().get_weapon_range("offHand"),
    }
    em4 = EquipmentManager()
    em4.equip(weapon("reach_spear", "2H", rng=2.5, tags=["reach"],
                     bonuses={"crit_chance": 0.05}), ch)
    em4.equip(armor("lucky_helm", "helmet", 5), ch)
    em4.slots["helmet"].bonuses = {"crit_chance": 0.02, "max_health": 10}
    equip_queries["weapon_damage"] = list(em4.get_weapon_damage())
    equip_queries["weapon_range_with_reach"] = em4.get_weapon_range()
    equip_queries["attack_speed_default"] = em4.get_weapon_attack_speed("offHand")
    equip_queries["stat_bonuses"] = em4.get_stat_bonuses()
    equip_queries["is_equipped"] = em4.is_equipped("reach_spear")
    unequipped = em4.unequip("mainHand", ch)
    equip_queries["unequip_returns"] = unequipped.item_id if unequipped else None
    equip_queries["is_equipped_after"] = em4.is_equipped("reach_spear")

    st["equipment_manager"] = {"hand_rules": hand_rules, "queries": equip_queries}

    write("status_effects.json", {
        "_meta": meta("entities/status_effect.py + status_manager.py + "
                      "equipment_manager.py (scenarios EXECUTED through the "
                      "real classes)"),
        "scenarios": st,
    })

    # ── P3: Python-exact RNG (MT19937) + legacy BiomeGenerator parity ────
    import hashlib
    import random as _pyrandom

    def rng_stream(seed, fn, n):
        r = _pyrandom.Random(seed)
        return [fn(r) for _ in range(n)]

    rng_cases = {}
    for seed in [0, 1, 42, 12345, 2**31 - 1, 2**40 + 123]:
        shuffled = list(range(10))
        _pyrandom.Random(seed).shuffle(shuffled)
        rng_cases[str(seed)] = {
            "random": rng_stream(seed, lambda r: r.random(), 10),
            "getrandbits_5": rng_stream(seed, lambda r: r.getrandbits(5), 10),
            "getrandbits_32": rng_stream(seed, lambda r: r.getrandbits(32), 10),
            "getrandbits_64": [str(v) for v in
                               rng_stream(seed, lambda r: r.getrandbits(64), 5)],
            "randint_3_17": rng_stream(seed, lambda r: r.randint(3, 17), 10),
            "choice_range7": rng_stream(seed, lambda r: r.choice(list(range(7))), 10),
            "uniform_m5_5": rng_stream(seed, lambda r: r.uniform(-5.0, 5.0), 5),
            "shuffle_10": shuffled,
        }
    write("python_rng.json", {
        "_meta": meta("stdlib random.Random (MT19937 + init_by_array + "
                      "_randbelow) — every stream from a FRESH Random(seed)"),
        "cases": rng_cases,
    })

    from systems.biome_generator import BiomeGenerator
    biome_cases = {}
    for seed in [12345, 999]:
        gen = BiomeGenerator(world_seed=seed)
        grid = {}
        water = {}
        dungeon = {}
        for cy in range(-12, 13):
            for cx in range(-12, 13):
                key = f"{cx},{cy}"
                grid[key] = gen.get_chunk_type(cx, cy)
                water[key] = gen.is_water_chunk(cx, cy)
                dungeon[key] = gen.should_spawn_dungeon(cx, cy)
        canon = ";".join(f"{k}:{grid[k]}" for k in sorted(grid))
        biome_cases[str(seed)] = {
            "grid": grid,
            "water": water,
            "dungeon": dungeon,
            "grid_sha256": hashlib.sha256(canon.encode()).hexdigest(),
            "chunk_seeds": {f"{x},{y}": gen.get_chunk_seed(x, y)
                            for x, y in [(0, 0), (5, -3), (-7, 11), (300, -412)]},
            "hash2d_samples": {f"{x},{y},{o}": gen._hash_2d(x, y, o)
                               for x, y, o in [(0, 0, 100), (5, -3, 5000),
                                               (-7, 11, 10000), (12, 12, 3000)]},
        }
    write("biome_generator.json", {
        "_meta": meta("systems/biome_generator.py (legacy fallback — still the "
                      "oracle for pre-geographic saves): 25x25 chunk grid + "
                      "water/dungeon flags EXECUTED per seed; sha256 canon"),
        "cases": biome_cases,
    })

    # ── P3: geography noise module (pure functions, EXECUTED) ────────────
    from systems.geography import noise as geo_noise

    territory = set()
    for ty in range(0, 20):
        for tx in range(0, 30):
            if not (12 <= tx <= 17 and 8 <= ty <= 11):  # notch
                territory.add((tx, ty))
    island = {(50, 50), (51, 50), (50, 51)}
    two_part = territory | island

    def chunks_sorted(s):
        return sorted([list(c) for c in s])

    regions_plain = geo_noise.voronoi_subdivide(territory, 5, seed=4242)
    regions_noisy = geo_noise.voronoi_subdivide(territory, 5, seed=4242,
                                                noise_amplitude=1.5,
                                                noise_frequency=0.05)
    write("geo_noise.json", {
        "_meta": meta("systems/geography/noise.py (hash noise, contiguity, "
                      "Voronoi subdivision — all executed)"),
        "hash_2d": {f"{x},{y},{s}": geo_noise.hash_2d(x, y, s)
                    for x, y, s in [(0, 0, 1), (5, -3, 4242), (-7, 11, 999),
                                    (300, 412, 123456), (511, 511, 1)]},
        "hash_2d_int": {f"{x},{y},{s},{m}": geo_noise.hash_2d_int(x, y, s, m)
                        for x, y, s, m in [(0, 0, 999, 600), (3, 17, 999, 600),
                                           (1, 2, 1000, 7), (4, 4, 1, 0)]},
        "value_noise": {f"{x},{y},{s}": geo_noise.value_noise_2d(x, y, s)
                        for x, y, s in [(0.5, 0.5, 42), (-1.25, 3.75, 42),
                                        (10.1, -20.9, 7), (0.0, 0.0, 7)]},
        "fractal_noise": {f"{x},{y},{s}": geo_noise.fractal_noise_2d(x, y, s)
                          for x, y, s in [(0.5, 0.5, 42), (12.3, 45.6, 7),
                                          (-3.3, 2.2, 99)]},
        "contiguous_true": geo_noise.is_contiguous(territory),
        "contiguous_false": geo_noise.is_contiguous(two_part),
        "components": [chunks_sorted([c])[0] and sorted([list(p) for p in c])
                       for c in sorted(geo_noise.find_components(two_part),
                                       key=len, reverse=True)],
        "corridor_width": geo_noise.measure_min_corridor_width(territory),
        "voronoi_plain": sorted([sorted([list(p) for p in r])
                                 for r in regions_plain]),
        "voronoi_noisy": sorted([sorted([list(p) for p in r])
                                 for r in regions_noisy]),
    })

    # ── P4: EnemyDatabase + attack profiles + loot streams ───────────────
    from Combat.enemy import Enemy, EnemyDatabase

    enemy_db = EnemyDatabase.get_instance()  # sacred loaded in boot(), updates last

    def attack_row(a):
        return {"attack_id": a.attack_id, "shape": a.shape, "arc": a.arc,
                "range": a.range, "windup": a.windup, "active": a.active,
                "recovery": a.recovery, "weight": a.weight, "tags": a.tags,
                "screen_shake": a.screen_shake,
                "damage_multiplier": a.damage_multiplier,
                "status_tags": a.status_tags}

    def enemy_row(e):
        return {
            "enemy_id": e.enemy_id, "name": e.name, "tier": e.tier,
            "category": e.category, "behavior": e.behavior,
            "max_health": e.max_health, "damage_min": e.damage_min,
            "damage_max": e.damage_max, "defense": e.defense, "speed": e.speed,
            "aggro_range": e.aggro_range, "attack_speed": e.attack_speed,
            "drops": [{"material_id": d.material_id,
                       "quantity_min": d.quantity_min,
                       "quantity_max": d.quantity_max, "chance": d.chance}
                      for d in e.drops],
            "ai_pattern": {
                "default_state": e.ai_pattern.default_state,
                "aggro_on_damage": e.ai_pattern.aggro_on_damage,
                "aggro_on_proximity": e.ai_pattern.aggro_on_proximity,
                "flee_at_health": e.ai_pattern.flee_at_health,
                "call_for_help_radius": e.ai_pattern.call_for_help_radius,
                "pack_coordination": e.ai_pattern.pack_coordination,
                "special_abilities": e.ai_pattern.special_abilities,
            },
            "special_ability_ids": [a.ability_id for a in e.special_abilities],
            "narrative": e.narrative, "tags": e.tags, "icon_path": e.icon_path,
            "visual_size": e.visual_size, "hurtbox_radius": e.hurtbox_radius,
            "attacks": [attack_row(a) for a in e.attacks],
        }

    # Loot: execute the REAL Enemy.generate_loot (it reads only
    # self.definition.drops) against the seeded GLOBAL random module.
    loot_streams = {}
    loot_enemies = sorted(enemy_db.enemies)[:6]
    for lseed in [7, 4242]:
        _pyrandom.seed(lseed)
        rolls = []
        for eid in loot_enemies:
            shim = SimpleNamespace(definition=enemy_db.enemies[eid])
            for _ in range(4):
                rolls.append({"enemy": eid,
                              "loot": [list(t) for t in
                                       Enemy.generate_loot(shim)]})
        loot_streams[str(lseed)] = rolls

    write("enemies.json", {
        "_meta": meta("Combat/enemy.py EnemyDatabase + attack_profile_generator "
                      "(deterministic profiles) + REAL generate_loot on seeded "
                      "global random"),
        "count": len(enemy_db.enemies),
        "enemies": {eid: enemy_row(e)
                    for eid, e in sorted(enemy_db.enemies.items())},
        "by_tier": {str(t): [e.enemy_id for e in lst]
                    for t, lst in enemy_db.enemies_by_tier.items()},
        "loot_enemies": loot_enemies,
        "loot_streams": loot_streams,
    })

    # ── P4t2a: action combat core — state machine / hitboxes / projectiles /
    #    combat data loader. Scenarios EXECUTED through the real classes; the
    #    C# tests replay the same scripts and must land on identical state.
    from Combat.attack_state_machine import (AttackDefinition,
                                             AttackStateMachine)
    from Combat.hitbox_system import (ActiveHitbox, HitboxDefinition,
                                      HitboxSystem)
    from Combat.projectile_system import ProjectileDefinition, ProjectileSystem
    from Combat import combat_data_loader as cdl

    def attack_def_row(a):
        return {"attack_id": a.attack_id, "windup_ms": a.windup_ms,
                "active_ms": a.active_ms, "recovery_ms": a.recovery_ms,
                "cooldown_ms": a.cooldown_ms, "hitbox_shape": a.hitbox_shape,
                "hitbox_params": a.hitbox_params,
                "damage_multiplier": a.damage_multiplier,
                "movement_multiplier": a.movement_multiplier,
                "can_be_interrupted": a.can_be_interrupted,
                "animation_id": a.animation_id,
                "projectile_id": a.projectile_id,
                "status_tags": a.status_tags, "screen_shake": a.screen_shake,
                "telegraph_color": a.telegraph_color,
                "combo_next": a.combo_next,
                "combo_window_ms": a.combo_window_ms, "tags": a.tags}

    # 1) Attack state machine — scripted timeline (same script hardcoded in
    #    the C# test; every snapshot must match).
    atk_a = AttackDefinition(
        attack_id="combo_a", windup_ms=300, active_ms=200, recovery_ms=240,
        cooldown_ms=400, movement_multiplier=0.6, combo_next="combo_a2",
        combo_window_ms=250)
    atk_b = AttackDefinition(
        attack_id="locked_b", windup_ms=200, active_ms=150, recovery_ms=100,
        cooldown_ms=300, can_be_interrupted=False)
    atk_c = AttackDefinition(
        attack_id="soft_c", windup_ms=500, active_ms=100, recovery_ms=100,
        cooldown_ms=100)

    def asm_snapshot(sm, events, results=None):
        return {
            "phase": sm.phase.value, "timer": sm.phase_timer,
            "combo_count": sm.combo_count, "combo_timer": sm.combo_timer,
            "movement_multiplier": sm.movement_multiplier,
            "windup_progress": sm.windup_progress,
            "is_attacking": sm.is_attacking,
            "is_active": sm.is_in_active_phase,
            "is_vulnerable": sm.is_vulnerable,
            "current_attack": (sm.current_attack.attack_id
                               if sm.current_attack else None),
            "hits": sorted(sm.hits_this_swing),
            "events": [{"type": ev.event_type, "source": ev.source_id,
                        "phase": ev.data.get("phase"),
                        "attack": (ev.data["attack"].attack_id
                                   if "attack" in ev.data else None)}
                       for ev in events],
            "results": results if results is not None else [],
        }

    sm = AttackStateMachine("player")
    asm_steps = []
    asm_steps.append(asm_snapshot(sm, [], [sm.start_attack(atk_a, {})]))
    asm_steps.append(asm_snapshot(sm, sm.update(100)))
    asm_steps.append(asm_snapshot(sm, sm.update(250)))       # windup -> active
    asm_steps.append(asm_snapshot(sm, [], [sm.record_hit("e1"),
                                           sm.record_hit("e1"),
                                           sm.record_hit("e2")]))
    asm_steps.append(asm_snapshot(sm, sm.update(200)))       # -> recovery
    asm_steps.append(asm_snapshot(sm, sm.update(240)))       # -> cooldown
    asm_steps.append(asm_snapshot(sm, [], [sm.start_attack(atk_a, {})]))  # combo
    for big in (5000, 5000, 5000, 5000):
        asm_steps.append(asm_snapshot(sm, sm.update(big)))
    asm_steps.append(asm_snapshot(sm, sm.update(100)))       # idle combo decay
    asm_steps.append(asm_snapshot(sm, sm.update(200)))       # decay to zero
    asm_steps.append(asm_snapshot(sm, [], [sm.start_attack(atk_b, {}),
                                           sm.interrupt()]))  # not interruptible
    sm.force_reset()
    asm_steps.append(asm_snapshot(sm, []))
    asm_steps.append(asm_snapshot(sm, [], [sm.start_attack(atk_c, {})]))
    asm_steps.append(asm_snapshot(sm, sm.update(50)))
    asm_steps.append(asm_snapshot(sm, [], [sm.interrupt()]))  # interruptible

    # 2) Hitbox system — collision matrix + event-flow scripts.
    hb_shapes = [
        HitboxDefinition(shape="arc", radius=2.0, arc_degrees=90.0),
        HitboxDefinition(shape="arc", radius=2.6, arc_degrees=55.0),
        HitboxDefinition(shape="circle", radius=1.2),
        HitboxDefinition(shape="rect", width=1.0, height=3.0),
        HitboxDefinition(shape="line", length=4.0),
    ]
    hb_facings = [0.0, 37.0, 217.0, -60.0]
    hsys_probe = HitboxSystem()
    matrix = {}
    coords = [-3.05, -1.85, -0.65, 0.55, 1.75, 2.95]
    for si, hd in enumerate(hb_shapes):
        for facing in hb_facings:
            live = ActiveHitbox(hd, 0.0, 0.0, facing, "probe", 1000.0, {})
            for hx in coords:
                for hy in coords:
                    hb = hsys_probe.register_hurtbox("m", 0.5)
                    hb.world_x, hb.world_y = hx, hy
                    matrix[f"{si}|{facing}|{hx},{hy}"] = \
                        hsys_probe._check_collision(live, hb)
    world_pos = {}
    for od in [HitboxDefinition(offset_forward=0.8),
               HitboxDefinition(offset_forward=1.5, offset_lateral=0.7),
               HitboxDefinition(offset_forward=0.0, offset_lateral=-1.2)]:
        for facing in hb_facings:
            world_pos[f"{od.offset_forward},{od.offset_lateral}|{facing}"] = \
                list(od.compute_world_position(3.0, -2.0, facing))

    def hit_rows(hits):
        return [{"attacker": h.attacker_id, "target": h.target_id,
                 "pos": list(h.hit_position), "proj": h.is_projectile}
                for h in hits]

    hsys = HitboxSystem()
    hsys.register_hurtbox("p1", 0.5)
    hsys.register_hurtbox("p2", 0.4)
    hsys.register_hurtbox("p3", 0.3)
    hsys.register_hurtbox("p2", 0.45)   # overwrite keeps insertion slot
    hsys.register_hurtbox("player", 0.5)
    hsys.update_hurtbox_positions({"p1": (2.0, 0.0), "p2": (2.6, 0.9),
                                   "p3": (-1.0, 0.0), "player": (0.0, 0.0)})
    hsys.get_hurtbox("p3").invulnerable = True
    hsys.spawn_hitbox(HitboxDefinition(shape="arc", radius=2.4,
                                       arc_degrees=100.0),
                      (0.75, 0.27), 20.0, "player", 300.0, {"kind": "swing"})
    hsys.spawn_hitbox(HitboxDefinition(shape="line", length=3.0,
                                       piercing=True),
                      (0.0, 0.0), 0.0, "player", 250.0, {"kind": "pierce"})
    hb_flow = []
    for _ in range(4):
        hits = hsys.update(100.0)
        hb_flow.append({"hits": hit_rows(hits),
                        "active": len(hsys.active_hitboxes)})
    hsys.get_hurtbox("p3").invulnerable = False
    hsys.spawn_hitbox(HitboxDefinition(shape="circle", radius=5.0),
                      (0.0, 0.0), 0.0, "npc", 150.0, {})
    hb_flow.append({"hits": hit_rows(hsys.update(100.0)),
                    "active": len(hsys.active_hitboxes)})

    # 3) Projectiles — straight / homing / gravity / piercing / AoE-on-hit.
    def proj_row(p):
        return {"x": p.x, "y": p.y, "vx": p.vx, "vy": p.vy,
                "facing": p.facing_angle, "traveled": p.distance_traveled,
                "alive": p.alive}

    proj_cases = {}

    def run_proj(name, pdef, start, angle, hurts, steps, target=None):
        hs = HitboxSystem()
        for hid, r, (hx, hy) in hurts:
            hb = hs.register_hurtbox(hid, r)
            hb.world_x, hb.world_y = hx, hy
        ps = ProjectileSystem(hs)
        proj = ps.spawn(pdef, start, angle, "player", {"kind": name},
                        target_pos=target)
        rows = []
        for _ in range(steps):
            hits = ps.update(100.0)
            aoe_hits = hs.update(100.0)
            rows.append({"proj": proj_row(proj), "hits": hit_rows(hits),
                         "aoe_hits": hit_rows(aoe_hits),
                         "count": ps.count,
                         "active_hitboxes": len(hs.active_hitboxes)})
        proj_cases[name] = rows

    run_proj("straight",
             ProjectileDefinition(projectile_id="s", speed=10.0,
                                  max_range=12.0, hitbox_radius=0.3),
             (0.0, 0.0), 30.0,
             [("t1", 0.5, (6.0, 3.5)), ("t2", 0.5, (9.0, 5.4))], 15)
    run_proj("homing",
             ProjectileDefinition(projectile_id="h", speed=8.0,
                                  max_range=25.0, homing=0.6),
             (0.0, 0.0), 90.0, [("t1", 0.6, (5.0, -4.0))], 20,
             target=(5.0, -4.0))
    run_proj("gravity",
             ProjectileDefinition(projectile_id="g", speed=12.0,
                                  max_range=20.0, gravity=9.0),
             (0.0, 0.0), -30.0, [("t1", 0.5, (8.0, -1.0))], 18)
    run_proj("piercing",
             ProjectileDefinition(projectile_id="p", speed=10.0,
                                  max_range=14.0, piercing=True),
             (0.0, 0.0), 0.0,
             [("t1", 0.5, (4.0, 0.1)), ("t2", 0.5, (8.0, -0.2))], 15)
    run_proj("aoe",
             ProjectileDefinition(projectile_id="a", speed=10.0,
                                  max_range=14.0,
                                  aoe_on_hit={"shape": "circle",
                                              "radius": 2.0},
                                  aoe_duration_ms=250.0),
             (0.0, 0.0), 0.0,
             [("t1", 0.5, (5.0, 0.0)), ("t2", 0.5, (6.2, 1.1))], 10)

    # 4) Combat data loader — dynamic generation (pure fns + seeded rng).
    weapon_rows = {}
    for wtype in sorted(cdl._WEAPON_PROFILES):
        for wrange, wspeed in [(1.5, 1.0), (3.25, 1.6), (2.0, 0.25)]:
            for ti, wtags in enumerate([[], ["fire", "burn"],
                                        ["ice", "slow", "pierce"]]):
                key = f"{wtype}|{wrange}|{wspeed}|{ti}"
                weapon_rows[key] = attack_def_row(
                    cdl.generate_weapon_attack(wtype, wrange, wspeed, wtags))

    _pyrandom.seed(31337)
    enemy_attack_rows = {}
    for eid in sorted(enemy_db.enemies):
        enemy_attack_rows[eid] = attack_def_row(
            cdl.generate_enemy_attack(enemy_db.enemies[eid], 0))
    fallback_defs = [
        SimpleNamespace(category="dragon", tier=3, tags=["fire"],
                        visual_size=3.0, enemy_id="synthetic_dragon",
                        attacks=[]),
        # visual_size must equal the C# computed value (unknown cat/tier -> 1.0)
        SimpleNamespace(category="slimeking", tier=9, tags=[],
                        visual_size=1.0, enemy_id="synthetic_unknown",
                        attacks=[]),
    ]
    for fd in fallback_defs:
        enemy_attack_rows[fd.enemy_id] = attack_def_row(
            cdl.generate_enemy_attack(fd, 2))

    _pyrandom.seed(991)
    select_rows = {}
    for eid in sorted(enemy_db.enemies)[:4]:
        loader = cdl.CombatDataLoader()
        picks = []
        for dist in [0.5, 1.4, 2.2, 5.0, 999.0]:
            sel = loader.select_enemy_attack(
                eid, dist, enemy_def=enemy_db.enemies[eid])
            picks.append(sel.attack_id if sel else None)
        select_rows[eid] = picks

    proj_def_rows = {}
    for ti, ptags in enumerate([["physical"], ["bow", "arrow"], ["fire"],
                                ["ice", "pierce"], ["lightning", "beam"],
                                ["homing", "arcane"], ["seeking"],
                                ["crystal", "frost"]]):
        p = cdl.generate_projectile_from_tags("bow", ptags)
        proj_def_rows[str(ti)] = {
            "projectile_id": p.projectile_id, "speed": p.speed,
            "max_range": p.max_range, "hitbox_radius": p.hitbox_radius,
            "sprite_id": p.sprite_id, "trail_type": p.trail_type,
            "homing": p.homing, "gravity": p.gravity,
            "piercing": p.piercing, "visual": p.visual, "tags": p.tags,
        }

    write("action_combat.json", {
        "_meta": meta("Combat/attack_state_machine.py + hitbox_system.py + "
                      "projectile_system.py + combat_data_loader.py — "
                      "scripted scenarios EXECUTED through the real classes"),
        "state_machine": asm_steps,
        "hitbox_matrix": matrix,
        "hitbox_world_pos": world_pos,
        "hitbox_flow": hb_flow,
        "projectiles": proj_cases,
        "weapon_attacks": weapon_rows,
        "enemy_attacks_seed_31337": enemy_attack_rows,
        "enemy_attack_select_seed_991": select_rows,
        "projectile_defs": proj_def_rows,
    })

    # ── P4t2b: tag registry / parser / target finder / effect executor ───
    from core.tag_system import get_tag_registry
    from core.tag_parser import get_tag_parser
    from core.effect_executor import EffectExecutor
    from data.databases.skill_db import SkillDatabase

    reg = get_tag_registry()
    reg_defs = {}
    for name in sorted(reg.definitions):
        d = reg.definitions[name]
        reg_defs[name] = {
            "category": d.category, "description": d.description,
            "priority": d.priority, "requires_params": d.requires_params,
            "default_params": d.default_params,
            "conflicts_with": d.conflicts_with, "aliases": d.aliases,
            "alias_of": d.alias_of, "stacking": d.stacking,
            "immunity": d.immunity, "synergies": d.synergies,
            "context_behavior": d.context_behavior,
            "auto_apply_chance": d.auto_apply_chance,
            "auto_apply_status": d.auto_apply_status, "parent": d.parent,
        }

    parser = get_tag_parser()

    def config_row(cfg):
        return {"raw_tags": cfg.raw_tags, "geometry": cfg.geometry_tag,
                "damage_tags": cfg.damage_tags, "status_tags": cfg.status_tags,
                "context_tags": cfg.context_tags,
                "special_tags": cfg.special_tags,
                "trigger_tags": cfg.trigger_tags, "context": cfg.context,
                "base_damage": cfg.base_damage,
                "base_healing": cfg.base_healing, "params": cfg.params,
                "warnings": cfg.warnings,
                "conflicts": cfg.conflicts_resolved}

    sk_db = SkillDatabase.get_instance()
    parse_cases = []
    for sid in sorted(sk_db.skills):
        sk = sk_db.skills[sid]
        if not sk.combat_tags:
            continue
        cfg = parser.parse(list(sk.combat_tags), dict(sk.combat_params))
        parse_cases.append({"id": sid, "tags": list(sk.combat_tags),
                            "params": sk.combat_params,
                            "config": config_row(cfg)})

    # Executor scenarios: stub battlefield built FROM SPEC (the C# test
    # constructs its stubs from the same spec, killing transcription drift).
    # Stub behavior (damage/heal/status recording) is part of the fixture
    # contract — identical by construction on both sides.
    BATTLEFIELD = [
        {"name": "hero", "kind": "character", "position": [0.0, 0.0],
         "health": 100.0, "max_health": 120.0, "take_damage": "simple",
         "has_status_manager": True, "has_knockback": True,
         "last_move_direction": [1.0, 0.0]},
        {"name": "e1", "kind": "enemy", "position": [3.0, 0.0],
         "category": "beast", "current_health": 80.0, "max_health": 80.0,
         "defense": 0.0, "take_damage": "simple",
         "has_status_manager": True, "has_knockback": True},
        {"name": "e2", "kind": "enemy", "position": [5.5, 1.0],
         "category": "undead", "current_health": 60.0, "max_health": 60.0,
         "defense": 20.0, "take_damage": "none",
         "has_status_manager": True, "has_knockback": False},
        {"name": "e3", "kind": "enemy", "position": [7.0, 2.5],
         "category": "construct", "current_health": 150.0,
         "max_health": 150.0, "defense": 40.0, "take_damage": "enhanced",
         "has_status_manager": False, "has_knockback": True},
        {"name": "e4", "kind": "enemy", "position": [4.0, -3.0],
         "category": "elemental", "current_health": 40.0, "max_health": 40.0,
         "defense": 5.0, "take_damage": "none",
         "has_status_manager": True, "has_knockback": False},
        {"name": "e5", "kind": "enemy", "position": [12.0, 0.0],
         "category": "beast", "current_health": 5.0, "max_health": 30.0,
         "defense": 0.0, "take_damage": "simple",
         "has_status_manager": True, "has_knockback": False},
        {"name": "e6", "kind": "enemy", "position": [2.0, 2.0],
         "category": "ooze", "current_health": 50.0, "max_health": 50.0,
         "defense": 80.0, "take_damage": "simple",
         "has_status_manager": True, "has_knockback": False},
    ]

    class _StatusRec:
        def __init__(self):
            self.applied = []

        def apply_status(self, tag, params, source=None):
            self.applied.append({
                "tag": tag,
                "params": {k: params[k] for k in sorted(params)},
                "with_source": source is not None})

    def build_entities(specs):
        out = {}
        order = []
        for spec in specs:
            if spec["kind"] == "character":
                class Character:
                    pass
                ent = Character()
                ent.health = spec["health"]
                ent.max_health = spec["max_health"]
                ent.heal_log = []

                def heal(amount, _e=ent):
                    _e.health = min(_e.max_health, _e.health + amount)
                    _e.heal_log.append(amount)
                ent.heal = heal
            else:
                class Enemy:
                    pass
                ent = Enemy()
                ent.definition = SimpleNamespace(
                    defense=spec.get("defense", 0.0))
                ent.current_health = spec["current_health"]
                ent.max_health = spec["max_health"]
                ent.is_alive = True
            ent.name = spec["name"]
            ent.position = [spec["position"][0], spec["position"][1], 0.0]
            if spec.get("category"):
                ent.category = spec["category"]
            if spec.get("last_move_direction"):
                ent.last_move_direction = tuple(spec["last_move_direction"])
            ent.damage_log = []
            td_kind = spec.get("take_damage", "none")
            if td_kind == "simple":
                if spec["kind"] == "character":
                    def td(damage, damage_type, _e=ent):
                        _e.damage_log.append([damage, damage_type])
                        _e.health = max(0.0, _e.health - damage)
                else:
                    def td(damage, damage_type, _e=ent):
                        _e.damage_log.append([damage, damage_type])
                        _e.current_health -= damage
                        if _e.current_health <= 0:
                            _e.current_health = 0.0
                            _e.is_alive = False
                ent.take_damage = td
            elif td_kind == "enhanced":
                def td(damage, damage_type, source=None, tags=None,
                       context=None, _e=ent):
                    _e.damage_log.append([damage, damage_type,
                                          list(tags or []),
                                          getattr(source, "name", None)])
                    _e.current_health -= damage
                    if _e.current_health <= 0:
                        _e.current_health = 0.0
                        _e.is_alive = False
                ent.take_damage = td
            if spec.get("has_status_manager"):
                ent.status_manager = _StatusRec()
            if spec.get("has_knockback"):
                ent.knockback_velocity_x = 0.0
                ent.knockback_velocity_y = 0.0
                ent.knockback_duration_remaining = 0.0
            out[spec["name"]] = ent
            order.append(ent)
        return out, order

    def entity_row(e):
        return {
            "name": e.name,
            "position": [e.position[0], e.position[1]],
            "alive": getattr(e, "is_alive", None),
            "current_health": getattr(e, "current_health", None),
            "health": getattr(e, "health", None),
            "damage_log": e.damage_log,
            "heal_log": getattr(e, "heal_log", []),
            "statuses": (e.status_manager.applied
                         if hasattr(e, "status_manager") else []),
            "knockback": ([e.knockback_velocity_x, e.knockback_velocity_y,
                           e.knockback_duration_remaining]
                          if hasattr(e, "knockback_velocity_x") else None),
        }

    EXEC_CASES = [
        {"id": "single_physical", "source": "hero", "primary": "e1",
         "tags": ["physical"], "params": {"baseDamage": 50.0}},
        {"id": "defense_armor_pen", "source": "hero", "primary": "e3",
         "tags": ["physical"],
         "params": {"baseDamage": 100.0, "_apply_enemy_defense": True,
                    "_armor_penetration": 0.3}},
        {"id": "defense_cap", "source": "hero", "primary": "e6",
         "tags": ["physical"],
         "params": {"baseDamage": 60.0, "_apply_enemy_defense": True}},
        {"id": "chain_lightning", "source": "hero", "primary": "e1",
         "tags": ["lightning", "chain"],
         "params": {"baseDamage": 40.0, "chain_count": 3,
                    "chain_range": 6.0}},
        {"id": "circle_burn", "source": "hero", "primary": "e1",
         "tags": ["fire", "circle", "burn"],
         "params": {"baseDamage": 30.0, "circle_radius": 5.0}},
        {"id": "circle_origin_source", "source": "hero", "primary": "e1",
         "tags": ["frost", "circle", "chill"],
         "params": {"baseDamage": 20.0, "circle_radius": 4.0,
                    "origin": "source"}},
        {"id": "circle_max_targets", "source": "hero", "primary": "e1",
         "tags": ["physical", "circle"],
         "params": {"baseDamage": 8.0, "circle_radius": 20.0,
                    "max_targets": 3}},
        {"id": "cone_frost", "source": "hero", "primary": "e1",
         "tags": ["frost", "cone"],
         "params": {"baseDamage": 25.0, "cone_angle": 90.0,
                    "cone_range": 8.0}},
        {"id": "beam_arcane", "source": "hero", "primary": "e3",
         "tags": ["arcane", "beam"],
         "params": {"baseDamage": 35.0, "beam_range": 12.0,
                    "beam_width": 1.0, "pierce_count": 2}},
        {"id": "critical", "source": "hero", "primary": "e1",
         "tags": ["physical", "critical"],
         "params": {"baseDamage": 40.0, "crit_chance": 0.6}},
        {"id": "lifesteal", "source": "hero", "primary": "e1",
         "tags": ["physical", "lifesteal"],
         "params": {"baseDamage": 60.0, "lifesteal_percent": 0.25}},
        {"id": "knockback", "source": "hero", "primary": "e1",
         "tags": ["physical", "knockback"],
         "params": {"baseDamage": 10.0, "knockback_distance": 3.0,
                    "knockback_duration": 0.5}},
        {"id": "knockback_no_fields", "source": "hero", "primary": "e2",
         "tags": ["physical", "knockback"], "params": {"baseDamage": 10.0}},
        {"id": "pull", "source": "hero", "primary": "e3",
         "tags": ["physical", "pull"],
         "params": {"baseDamage": 5.0, "pull_distance": 2.0}},
        {"id": "execute", "source": "hero", "primary": "e5",
         "tags": ["physical", "execute"],
         "params": {"baseDamage": 10.0, "threshold_hp": 0.5,
                    "bonus_damage": 3.0}},
        {"id": "heal_ally", "source": "hero", "primary": "hero",
         "tags": ["ally"], "params": {"baseHealing": 30.0}},
        {"id": "enemy_source_flip", "source": "e1", "primary": "hero",
         "tags": ["physical"], "params": {"baseDamage": 25.0}},
        {"id": "teleport", "source": "hero", "primary": "e2",
         "tags": ["arcane", "teleport"], "params": {"teleport_range": 10.0}},
        {"id": "teleport_out_of_range", "source": "hero", "primary": "e5",
         "tags": ["arcane", "teleport"], "params": {"teleport_range": 3.0}},
        {"id": "dash", "source": "hero", "primary": "e3",
         "tags": ["physical", "dash"],
         "params": {"baseDamage": 15.0, "dash_distance": 5.0,
                    "dash_speed": 20.0}},
        {"id": "phase", "source": "hero", "primary": "e1",
         "tags": ["phase"],
         "params": {"phase_duration": 3.0, "can_pass_walls": True}},
        {"id": "multi_damage_tags", "source": "hero", "primary": "e1",
         "tags": ["fire", "physical"], "params": {"baseDamage": 20.0}},
        {"id": "status_override", "source": "hero", "primary": "e1",
         "tags": ["physical", "burn"],
         "params": {"baseDamage": 5.0, "burn_duration": 9.9,
                    "duration": 4.2}},
        {"id": "geometry_conflict", "source": "hero", "primary": "e1",
         "tags": ["fire", "chain", "circle"],
         "params": {"baseDamage": 10.0, "chain_count": 1, "chain_range": 9.0,
                    "circle_radius": 3.0}},
        {"id": "alias_or_unknown_ice", "source": "hero", "primary": "e1",
         "tags": ["ice", "single_target"], "params": {"baseDamage": 12.0}},
    ]

    exec_rows = []
    for i, case in enumerate(EXEC_CASES):
        ents, order = build_entities(BATTLEFIELD)
        _pyrandom.seed(5000 + i)
        executor = EffectExecutor()
        ctx = executor.execute_effect(
            source=ents[case["source"]], primary_target=ents[case["primary"]],
            tags=list(case["tags"]), params=dict(case["params"]),
            available_entities=order)
        exec_rows.append({
            "id": case["id"],
            "targets": [t.name for t in ctx.targets],
            "config": config_row(ctx.config),
            "entities": [entity_row(e) for e in order],
            "rng_check": _pyrandom.random(),
        })

    write("effect_stack.json", {
        "_meta": meta("core/tag_system.py + tag_parser.py + geometry/ + "
                      "effect_executor.py — registry dumped, every skill's "
                      "combat tags parsed, executor scenarios EXECUTED on a "
                      "spec-built stub battlefield with seeded global rng"),
        "registry": {
            "definitions": reg_defs,
            "aliases": {k: reg.aliases[k] for k in sorted(reg.aliases)},
            "categories": reg.categories,
            "geometry_priority": reg.geometry_priority,
            "mutually_exclusive": reg.mutually_exclusive,
            "context_inference": reg.context_inference,
        },
        "parse_skills": parse_cases,
        "battlefield": BATTLEFIELD,
        "cases": EXEC_CASES,
        "results": exec_rows,
    })

    # ── P4t2c: Enemy runtime AI — scripted scenarios on REAL Enemy objects
    def enemy_state_row(e):
        return {
            "pos": [e.position[0], e.position[1]],
            "state": e.ai_state.value,
            "health": e.current_health, "alive": e.is_alive,
            "facing": e.facing_angle,
            "attack_cooldown": e.attack_cooldown,
            "in_combat": e.in_combat,
            "wander_timer": e.wander_timer,
            "wander_cooldown": e.wander_cooldown,
            "target": list(e.target_position) if e.target_position else None,
            "phase": e.attack_phase,
            "phase_timer": e.attack_phase_timer,
            "windup_ms": e._attack_windup_ms,
            "active_ms": e._attack_active_ms,
            "recovery_ms": e._attack_recovery_ms,
            "arc": e._attack_arc_degrees, "radius": e._attack_radius,
            "shape": getattr(e, "_attack_shape", "arc"),
            "anim_timer": e.attack_anim_timer,
            "anim_tags": list(e.attack_anim_tags),
            "anim_lunge": e.attack_anim_lunge,
            "attack_target": (list(e.attack_target_pos)
                              if e.attack_target_pos else None),
            "knockback": [e.knockback_velocity_x, e.knockback_velocity_y,
                          e.knockback_duration_remaining],
            "time_since_death": e.time_since_death,
            "windup_progress": e.windup_progress,
        }

    def run_enemy_ai(edef):
        _pyrandom.seed(20240)
        e = Enemy(edef, (10.0, 10.0), (0, 0))
        rows = [enemy_state_row(e)]
        player = [30.0, 10.0]
        for _ in range(40):
            if player[0] > 11.0:
                player[0] -= 1.0
            e.update_ai(0.1, tuple(player))
            rows.append(enemy_state_row(e))
        d1 = e.take_damage(e.max_health * 0.4)
        rows.append({**{"event": "damaged", "died": d1},
                     **enemy_state_row(e)})
        e.knockback_velocity_x = 4.0
        e.knockback_velocity_y = -2.0
        e.knockback_duration_remaining = 0.5
        for _ in range(6):
            e.update_ai(0.1, tuple(player))
            rows.append(enemy_state_row(e))
        can1 = e.can_attack()
        started = e.start_phased_attack(tuple(player))
        transitions = [e.update_attack_phase(100.0) for _ in range(30)]
        dmg = e.perform_attack()
        rows.append({**{"event": "attack", "can_before": can1,
                        "started": started, "transitions": transitions,
                        "damage": dmg}, **enemy_state_row(e)})
        abil0 = e.can_use_special_ability(2.0)
        e.current_health = e.max_health * 0.15
        abil_by_dist = {}
        for dist in [0.5, 2.0, 10.0, 100.0]:
            a = e.can_use_special_ability(dist)
            abil_by_dist[str(dist)] = a.ability_id if a else None
        d2 = e.take_damage(999999.0)
        e.update_ai(0.5, tuple(player))
        e.update_ai(0.5, tuple(player))
        rows.append({**{"event": "death", "died": d2,
                        "abil_full_hp": (abil0.ability_id if abil0 else None),
                        "abil_by_dist": abil_by_dist},
                     **enemy_state_row(e)})
        return rows

    def run_enemy_night(edef):
        # night multipliers + safe-zone exclusion on the approach path
        _pyrandom.seed(555)
        e = Enemy(edef, (5.0, 5.0), (0, 0))
        rows = []
        for _ in range(25):
            e.update_ai(0.1, (12.0, 5.0), aggro_multiplier=1.3,
                        speed_multiplier=1.15,
                        safe_zone_center=(10.0, 5.0), safe_zone_radius=2.0)
            rows.append(enemy_state_row(e))
        return rows

    ai_ids = sorted(enemy_db.enemies)[:5]
    for eid in sorted(enemy_db.enemies):
        if len(ai_ids) >= 8:
            break
        if enemy_db.enemies[eid].special_abilities and eid not in ai_ids:
            ai_ids.append(eid)
    write("enemy_ai.json", {
        "_meta": meta("Combat/enemy.py Enemy runtime — scripted AI scenarios "
                      "EXECUTED on real Enemy objects (seeded global rng; "
                      "no world_system / statuses — those are separate "
                      "certified systems)"),
        "ai_ids": ai_ids,
        "scenarios": {eid: run_enemy_ai(enemy_db.enemies[eid])
                      for eid in ai_ids},
        "night": {eid: run_enemy_night(enemy_db.enemies[eid])
                  for eid in ai_ids[:3]},
    })

    # ── P3t2: chunk.py per-chunk tile + resource parity ──────────────────
    from systems.chunk import Chunk
    from systems.biome_generator import BiomeGenerator as _BG
    from data.databases.chunk_template_db import ChunkTemplateDatabase

    def chunk_row(c):
        return {
            "chunk_type": c.chunk_type,
            "seed": c.seed,
            "tiles": [[t.position.x, t.position.y, t.tile_type.value,
                       t.walkable] for t in c.tiles.values()],
            "resources": [[r.position.x, r.position.y, r.resource_type,
                           r.tier] for r in c.resources],
        }

    chunk_cases = []

    bg = _BG(world_seed=12345)
    biome_coords = [(0, 0), (3, -2), (-5, 7), (12, 4), (-9, -9)]
    found_water = {}
    for cy in range(-15, 16):
        for cx in range(-15, 16):
            ct = bg.get_chunk_type(cx, cy)
            if (ct in ("water_lake", "water_river", "water_cursed_swamp")
                    and ct not in found_water):
                found_water[ct] = (cx, cy)
    for ct in sorted(found_water):
        biome_coords.append(found_water[ct])
    for cx, cy in biome_coords:
        c = Chunk(cx, cy, biome_generator=bg)
        chunk_cases.append({"mode": "biome", "world_seed": 12345,
                            "cx": cx, "cy": cy, "row": chunk_row(c)})

    for cx, cy, s in [(0, 0, 777001), (1, -1, 777002), (4, 5, 777003),
                      (9, -9, 777004), (-7, 3, 777005), (2, 8, 777006),
                      (5, 5, 777007), (-3, -6, 777008)]:
        c = Chunk(cx, cy, seed=s)
        chunk_cases.append({"mode": "legacy", "seed": s,
                            "cx": cx, "cy": cy, "row": chunk_row(c)})

    template_db = ChunkTemplateDatabase.get_instance()
    geo_keys = sorted(template_db._geo_dispatch)[:6]
    geo_seed = 424242
    for geo in geo_keys:
        for dl in (1, 3, 5):
            geo_seed += 1
            c = Chunk(2, 2, seed=geo_seed,
                      geographic_data=SimpleNamespace(chunk_type=geo,
                                                      danger_level=dl))
            chunk_cases.append({"mode": "geo", "seed": geo_seed,
                                "cx": 2, "cy": 2, "geo_type": geo,
                                "danger": dl, "row": chunk_row(c)})

    write("chunks.json", {
        "_meta": meta("systems/chunk.py — REAL Chunk objects generated in "
                      "all three modes (biome-generator, legacy explicit "
                      "seed, geographic dispatch): full tile grids + "
                      "seeded resource/fishing-spot spawns"),
        "cases": chunk_cases,
    })

    write("translations.json", {
        "_meta": meta("data/databases/translation_db.py"),
        "mana_costs": dbs["translations"].mana_costs,
        "cooldown_seconds": dbs["translations"].cooldown_seconds,
        "duration_seconds": dbs["translations"].duration_seconds,
        "magnitude_values": dbs["translations"].magnitude_values,
    })


if __name__ == "__main__":
    print(f"DB parity dump @ {SHA} (source: {SRC})")
    dump_all(boot())
    print("done.")
