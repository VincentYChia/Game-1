"""Database singletons for loading game data"""

from .translation_db import TranslationDatabase
from .material_db import MaterialDatabase
from .equipment_db import EquipmentDatabase
from .title_db import TitleDatabase
from .npc_db import NPCDatabase
from .class_db import ClassDatabase
from .recipe_db import RecipeDatabase
from .placement_db import PlacementDatabase
from .skill_db import SkillDatabase

__all__ = [
    'TranslationDatabase',
    'MaterialDatabase',
    'EquipmentDatabase',
    'TitleDatabase',
    'NPCDatabase',
    'ClassDatabase',
    'RecipeDatabase',
    'PlacementDatabase',
    'SkillDatabase',
]
