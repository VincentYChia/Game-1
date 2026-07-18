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
        "world_generation": wg_db,
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
