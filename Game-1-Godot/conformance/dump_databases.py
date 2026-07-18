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

    # Update-N overlay LAST, exactly like boot (also touches enemy /
    # skill-unlock DBs — harmless here, they just load too).
    load_all_updates(get_resource_path(""))

    return {
        "materials": mat_db, "translations": trans_db, "recipes": recipe_db,
        "equipment": equip_db, "titles": title_db, "classes": class_db,
        "skills": skill_db, "placements": placement_db,
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
