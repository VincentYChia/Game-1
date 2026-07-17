"""
Regression guard: SkillDatabase / TitleDatabase .reload() must re-merge
Update-N content.

Boot layers Update-N (e.g. Update-2 fishing) on top of the sacred +
generated files via load_all_updates(). A WES content commit calls
db.reload(), which rebuilds the dict from the Skills/ (or titles) files
ALONE — so before the fix a mid-session commit silently deleted the
fishing skills/titles until the next restart. These tests pin the
re-merge.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from core.paths import get_resource_path  # noqa: E402
from data.databases.skill_db import SkillDatabase  # noqa: E402
from data.databases.title_db import TitleDatabase  # noqa: E402
from data.databases.update_loader import (  # noqa: E402
    load_skill_updates,
    load_title_updates,
)

FISHING_SKILL = "anglers_patience"   # Update-2/skills-fishing.JSON
FISHING_TITLE = "novice_fisher"      # Update-2/titles-fishing.JSON


def _boot_skill_db():
    db = SkillDatabase.get_instance()
    db.load_from_files()
    load_skill_updates(get_resource_path(""))  # boot layers Update-N on top
    return db


def _boot_title_db():
    db = TitleDatabase.get_instance()
    db.load_from_files()
    load_title_updates(get_resource_path(""))
    return db


def test_skill_reload_keeps_updaten_fishing_skills():
    db = _boot_skill_db()
    assert FISHING_SKILL in db.skills, (
        "Update-2 fishing skill missing after boot — test premise broken"
    )
    db.reload()
    assert FISHING_SKILL in db.skills, (
        "reload() dropped the Update-2 fishing skill — Update-N re-merge "
        "regressed"
    )


def test_title_reload_keeps_updaten_fishing_titles():
    db = _boot_title_db()
    assert FISHING_TITLE in db.titles, (
        "Update-2 fishing title missing after boot — test premise broken"
    )
    db.reload()
    assert FISHING_TITLE in db.titles, (
        "reload() dropped the Update-2 fishing title — Update-N re-merge "
        "regressed"
    )
