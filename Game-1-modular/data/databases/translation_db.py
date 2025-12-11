"""Translation Database - manages skills translation tables"""

import json
from pathlib import Path
from typing import Dict
from core.paths import get_resource_path


class TranslationDatabase:
    _instance = None

    def __init__(self):
        self.magnitude_values = {}
        self.duration_seconds = {}
        self.mana_costs = {}
        self.cooldown_seconds = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        # Use get_resource_path for packaged environment support
        path = get_resource_path("Definitions.JSON/skills-translation-table.JSON")

        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                if 'durationTranslations' in data:
                    for key, val in data['durationTranslations'].items():
                        self.duration_seconds[key] = val.get('seconds', 0)
                if 'manaCostTranslations' in data:
                    for key, val in data['manaCostTranslations'].items():
                        self.mana_costs[key] = val.get('cost', 0)
                print(f"✓ Loaded translations from {path}")
                self.loaded = True
                return
            except Exception as e:
                print(f"⚠ Error loading {path}: {e}")

        self._create_defaults()
        self.loaded = True

    def _create_defaults(self):
        self.magnitude_values = {'minor': 0.5, 'moderate': 1.0, 'major': 2.0, 'extreme': 4.0}
        self.duration_seconds = {'instant': 0, 'brief': 15, 'moderate': 30, 'long': 60}
        self.mana_costs = {'low': 30, 'moderate': 60, 'high': 100}
        self.cooldown_seconds = {'short': 120, 'moderate': 300, 'long': 600}
