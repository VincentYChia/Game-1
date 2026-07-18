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
