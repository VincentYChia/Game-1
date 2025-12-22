"""Main game engine - orchestrates all game systems"""

from __future__ import annotations
import pygame
import sys
import os
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Core systems
from .config import Config
from .camera import Camera
from .notifications import Notification
from .testing import CraftingSystemTester
from .paths import get_resource_path

# Entities
from entities import Character, DamageNumber

# Data
from data import (
    MaterialDatabase,
    EquipmentDatabase,
    TranslationDatabase,
    SkillDatabase,
    RecipeDatabase,
    PlacementDatabase,
    TitleDatabase,
    ClassDatabase,
    NPCDatabase,
)

from data.models import Position, Recipe, PlacedEntityType, StationType
from entities.components import ItemStack

# Systems
from systems import WorldSystem, NPC
from systems.turret_system import TurretSystem
from systems.save_manager import SaveManager

# Rendering
from rendering import Renderer

# Combat system
sys.path.insert(0, str(Path(__file__).parent.parent / "Combat"))
from Combat import CombatManager

# Crafting subdisciplines (optional)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "Crafting-subdisciplines"))
    from smithing import SmithingCrafter
    from refining import RefiningCrafter
    from alchemy import AlchemyCrafter
    from engineering import EngineeringCrafter
    from enchanting import EnchantingCrafter
    from rarity_utils import rarity_system
    CRAFTING_MODULES_LOADED = True
    print("✓ Loaded crafting subdisciplines modules")
except ImportError as e:
    CRAFTING_MODULES_LOADED = False
    print(f"⚠ Could not load crafting subdisciplines: {e}")
    print("  Crafting will use legacy instant-craft only")


# ============================================================================
# GAME ENGINE
# ============================================================================
class GameEngine:
    def __init__(self):
        # Initialize screen settings first (auto-detects resolution or uses custom)
        Config.init_screen_settings()

        pygame.init()
        self.screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT))
        pygame.display.set_caption("2D RPG Game - Equipment System v2.2")
        self.clock = pygame.time.Clock()
        self.running = True

        print("=" * 60)
        print("Loading databases...")
        print("=" * 60)

        MaterialDatabase.get_instance().load_from_file(str(get_resource_path("items.JSON/items-materials-1.JSON")))
        MaterialDatabase.get_instance().load_refining_items(
            str(get_resource_path("items.JSON/items-refining-1.JSON")))  # FIX #2: Load ingots/planks
        # Load stackable consumables (potions, oils, etc.)
        MaterialDatabase.get_instance().load_stackable_items(
            str(get_resource_path("items.JSON/items-alchemy-1.JSON")), categories=['consumable'])
        # Load stackable devices (turrets, traps, bombs, utility devices)
        MaterialDatabase.get_instance().load_stackable_items(
            str(get_resource_path("items.JSON/items-engineering-1.JSON")), categories=['device'])
        # Load test items for tag system validation
        MaterialDatabase.get_instance().load_stackable_items(
            str(get_resource_path("items.JSON/items-testing-tags.JSON")), categories=['device', 'weapon'])
        # Load placeable crafting stations from items-smithing-2.JSON
        MaterialDatabase.get_instance().load_stackable_items(
            str(get_resource_path("items.JSON/items-smithing-2.JSON")), categories=['station'])
        # Load placeable crafting stations from legacy file (backup)
        MaterialDatabase.get_instance().load_stackable_items(
            str(get_resource_path("Definitions.JSON/crafting-stations-1.JSON")), categories=['station'])
        TranslationDatabase.get_instance().load_from_files()
        SkillDatabase.get_instance().load_from_file()
        RecipeDatabase.get_instance().load_from_files()
        PlacementDatabase.get_instance().load_from_files()

        # Load equipment from all item files
        equip_db = EquipmentDatabase.get_instance()
        equip_db.load_from_file(str(get_resource_path("items.JSON/items-engineering-1.JSON")))
        equip_db.load_from_file(str(get_resource_path("items.JSON/items-smithing-2.JSON")))
        equip_db.load_from_file(str(get_resource_path("items.JSON/items-tools-1.JSON")))
        equip_db.load_from_file(str(get_resource_path("items.JSON/items-alchemy-1.JSON")))
        # Load test weapons for tag system validation
        equip_db.load_from_file(str(get_resource_path("items.JSON/items-testing-tags.JSON")))

        TitleDatabase.get_instance().load_from_file(str(get_resource_path("progression/titles-1.JSON")))
        ClassDatabase.get_instance().load_from_file(str(get_resource_path("progression/classes-1.JSON")))
        SkillDatabase.get_instance().load_from_file(str(get_resource_path("Skills/skills-skills-1.JSON")))
        NPCDatabase.get_instance().load_from_files()  # Load NPCs and Quests

        # Initialize crafting subdisciplines (minigames)
        if CRAFTING_MODULES_LOADED:
            print("\nInitializing crafting subdisciplines...")
            self.smithing_crafter = SmithingCrafter()
            self.refining_crafter = RefiningCrafter()
            self.alchemy_crafter = AlchemyCrafter()
            self.engineering_crafter = EngineeringCrafter()
            self.enchanting_crafter = EnchantingCrafter()
            print("✓ All 5 crafting disciplines loaded")
        else:
            self.smithing_crafter = None
            self.refining_crafter = None
            self.alchemy_crafter = None
            self.engineering_crafter = None
            self.enchanting_crafter = None

        print("\nInitializing systems...")
        self.world = WorldSystem()
        self.save_manager = SaveManager()

        # Check for command line args for temporary world
        import sys
        self.temporary_world = "--temp" in sys.argv or "-t" in sys.argv

        # Start menu state
        self.start_menu_open = not self.temporary_world  # Show menu unless using --temp flag
        self.start_menu_selected_option = 0  # 0=New World, 1=Load World, 2=Load Default Save, 3=Temporary World

        # Initialize character to None (will be created after menu selection)
        self.character = None
        self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
        self.renderer = Renderer(self.screen)

        # If temporary world flag is set, create character immediately
        if self.temporary_world:
            print("🌍 Starting in temporary world mode (no saves)")
            self.character = Character(Position(50.0, 50.0, 0.0))
            self.start_menu_open = False

            # Open class selection for new character
            if not self.character.class_system.current_class:
                self.character.class_selection_open = True
                print("✓ Opening class selection...")

        # Initialize automated testing framework
        self.test_system = CraftingSystemTester(self)

        # Initialize combat system (with temporary character if needed for loading)
        print("Loading combat system...")
        temp_char = self.character if self.character else Character(Position(50.0, 50.0, 0.0))
        self.combat_manager = CombatManager(self.world, temp_char)
        self.combat_manager.load_config(
            "Definitions.JSON/combat-config.JSON",
            "Definitions.JSON/hostiles-1.JSON"
        )
        # Only spawn initial enemies if we have a real character
        if self.character:
            self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)

            # Spawn training dummy for tag testing
            from systems.training_dummy import spawn_training_dummy
            spawn_training_dummy(self.combat_manager, (60.0, 50.0))

        # Initialize NPC system
        print("Loading NPCs...")
        self.npcs: List[NPC] = []
        npc_db = NPCDatabase.get_instance()
        if npc_db.loaded:
            for npc_def in npc_db.npcs.values():
                npc = NPC(npc_def)
                self.npcs.append(npc)
            print(f"✓ Spawned {len(self.npcs)} NPCs in the world")

        # NPC interaction state
        self.npc_dialogue_open = False
        self.active_npc: Optional[NPC] = None
        self.npc_dialogue_lines: List[str] = []
        self.npc_available_quests: List[str] = []
        self.npc_quest_to_turn_in: Optional[str] = None
        self.npc_dialogue_window_rect = None

        # Minigame state
        self.active_minigame = None  # Current minigame instance
        self.minigame_type = None  # 'smithing', 'alchemy', etc.
        self.minigame_recipe = None  # Recipe being crafted
        self.minigame_paused = False
        self.minigame_button_rect = None  # Primary button rect
        self.minigame_button_rect2 = None  # Secondary button rect (alchemy)

        # Placement state - for material placement UIs
        self.placement_mode = False  # True when in placement UI
        self.placement_recipe = None  # Recipe selected for placement
        self.placement_data = None  # PlacementData from database

        # Placed materials - different structures for different crafting types
        self.placed_materials_grid = {}  # Smithing/Enchanting: "x,y" -> (materialId, quantity)
        self.placed_materials_hub = {'core': [], 'surrounding': []}  # Refining: hub-spoke
        self.placed_materials_sequential = []  # Alchemy: ordered list
        self.placed_materials_slots = {}  # Engineering: slot_type -> (materialId, quantity)

        # Turret system
        self.turret_system = TurretSystem()

        # Debug mode state tracking (for reverting when toggled off)
        self.debug_saved_state = {
            'f1': None,  # Saved state for F1 (level/stat points)
            'f2': None,  # Saved state for F2 (skills)
            'f3': None,  # Saved state for F3 (titles)
            'f4': None   # Saved state for F4 (level/stats)
        }
        self.debug_mode_active = {
            'f1': False,
            'f2': False,
            'f3': False,
            'f4': False
        }

        # Placement UI rects
        self.placement_grid_rects = {}  # Grid slot rects for smithing
        self.placement_slot_rects = {}  # Generic slot rects
        self.placement_craft_button_rect = None  # Craft button (appears when valid)
        self.placement_minigame_button_rect = None  # Minigame button
        self.placement_clear_button_rect = None  # Clear placement button

        self.damage_numbers: List[DamageNumber] = []
        self.notifications: List[Notification] = []
        self.crafting_window_rect = None
        self.crafting_recipes = []
        self.selected_recipe = None  # Currently selected recipe in crafting UI (for placement display)
        self.user_placement = {}  # User's current material placement: "x,y" -> materialId for grids, or other structures
        self.active_station_tier = 1  # Currently open crafting station's tier (determines grid size shown)
        self.placement_grid_rects = []  # Grid cell rects for click detection: list of (pygame.Rect, (grid_x, grid_y) or slot_id)
        self.recipe_scroll_offset = 0  # Scroll offset for recipe list in crafting UI
        self.stats_window_rect = None
        self.stats_buttons = []
        self.equipment_window_rect = None
        self.equipment_rects = {}
        self.skills_window_rect = None
        self.skills_hotbar_rects = []
        self.skills_list_rects = []
        self.skills_available_rects = []
        self.encyclopedia_window_rect = None
        self.encyclopedia_tab_rects = []
        self.class_selection_rect = None
        self.class_buttons = []

        # Enchantment/Adornment selection UI
        self.enchantment_selection_active = False
        self.enchantment_recipe = None
        self.enchantment_use_minigame = False  # Whether to start minigame after item selection
        self.enchantment_selected_item = None  # The item selected for enchanting (for minigame)
        self.enchantment_compatible_items = []
        self.enchantment_selection_rect = None
        self.enchantment_item_rects = None  # Item rects for click detection

        # Minigame state
        self.active_minigame = None  # Current minigame instance (SmithingMinigame, etc.)
        self.minigame_type = None  # Station type: 'smithing', 'alchemy', 'refining', 'engineering', 'adornments'
        self.minigame_recipe = None  # Recipe being crafted with minigame
        self.minigame_button_rect = None  # For click detection on minigame buttons
        self.minigame_button_rect2 = None  # For secondary buttons (e.g., alchemy stabilize)

        self.keys_pressed = set()
        self.mouse_buttons_pressed = set()  # Track which mouse buttons are held down
        self.mouse_pos = (0, 0)
        self.last_tick = pygame.time.get_ticks()
        self.last_click_time = 0
        self.last_clicked_slot = None

        # Start menu UI rects
        self.start_menu_buttons = []

        # Open class selection if character exists and has no class
        if self.character and not self.character.class_system.current_class:
            self.character.class_selection_open = True

        print("\n" + "=" * 60)
        print("✓ Game ready!")
        if Config.DEBUG_INFINITE_RESOURCES:
            print("⚠ DEBUG MODE ENABLED (F1 to toggle)")
        print("=" * 60 + "\n")

    def add_notification(self, message: str, color: Tuple[int, int, int] = Config.COLOR_NOTIFICATION):
        self.notifications.append(Notification(message, 3.0, color))

    def _get_weapon_effect_data(self, hand: str = 'mainHand') -> tuple:
        """
        Extract effect tags and params from equipped weapon for tag-based combat.

        Args:
            hand: Which hand to check ('mainHand' or 'offHand')

        Returns:
            tuple: (effect_tags: List[str], effect_params: Dict)
        """
        weapon = self.character.equipment.slots.get(hand)

        if weapon and hasattr(weapon, 'get_effect_tags'):
            effect_tags = weapon.get_effect_tags()
            effect_params = weapon.get_effect_params()

            # If weapon has effect tags, use them
            if effect_tags:
                # Ensure baseDamage is set from weapon damage if not specified
                if 'baseDamage' not in effect_params and weapon.damage != (0, 0):
                    # Use average of damage range
                    avg_damage = (weapon.damage[0] + weapon.damage[1]) / 2
                    effect_params = effect_params.copy()
                    effect_params['baseDamage'] = avg_damage

                return (effect_tags, effect_params)

        # Fallback: No effect tags, create basic physical attack
        fallback_tags = ["physical", "single"]
        fallback_params = {}

        if weapon and weapon.damage != (0, 0):
            avg_damage = (weapon.damage[0] + weapon.damage[1]) / 2
            fallback_params['baseDamage'] = avg_damage
        else:
            # Unarmed
            fallback_params['baseDamage'] = 5

        return (fallback_tags, fallback_params)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Autosave on quit (unless temporary world)
                if self.character and not self.temporary_world:
                    if self.save_manager.save_game(
                        self.character,
                        self.world,
                        self.character.quests,
                        self.npcs,
                        "autosave.json"
                    ):
                        print("💾 Autosaved on quit")
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.keys_pressed.add(event.key)

                # Start menu event handling (highest priority)
                if self.start_menu_open:
                    if event.key == pygame.K_UP:
                        self.start_menu_selected_option = (self.start_menu_selected_option - 1) % 4
                    elif event.key == pygame.K_DOWN:
                        self.start_menu_selected_option = (self.start_menu_selected_option + 1) % 4
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.handle_start_menu_selection(self.start_menu_selected_option)
                    elif event.key == pygame.K_ESCAPE:
                        # Autosave on quit from start menu (if character exists and not temporary world)
                        if self.character and not self.temporary_world:
                            if self.save_manager.save_game(
                                self.character,
                                self.world,
                                self.character.quests,
                                self.npcs,
                                "autosave.json"
                            ):
                                print("💾 Autosaved on start menu quit")
                        self.running = False
                    continue  # Skip other event handling

                # Minigame input handling (highest priority)
                if self.active_minigame:
                    if event.key == pygame.K_ESCAPE:
                        # Cancel minigame (lose materials)
                        print(f"🚫 Minigame cancelled by player")
                        self.add_notification("Minigame cancelled!", (255, 100, 100))
                        self.active_minigame = None
                        self.minigame_type = None
                        self.minigame_recipe = None
                    elif self.minigame_type == 'smithing' and event.key == pygame.K_SPACE:
                        self.active_minigame.handle_fan()
                    elif self.minigame_type == 'alchemy':
                        if event.key == pygame.K_c:
                            self.active_minigame.chain()
                        elif event.key == pygame.K_s:
                            self.active_minigame.stabilize()
                    elif self.minigame_type == 'refining' and event.key == pygame.K_SPACE:
                        self.active_minigame.handle_attempt()
                    # engineering uses button clicks, no keyboard input needed
                    # Skip other key handling when minigame is active
                    continue

                # Skip character-dependent input if no character exists yet
                if self.character is None:
                    continue

                if event.key == pygame.K_ESCAPE:
                    if self.enchantment_selection_active:
                        self._close_enchantment_selection()
                        print("🚫 Enchantment selection cancelled")
                    elif self.character.crafting_ui_open:
                        self.character.close_crafting_ui()
                    elif self.character.stats_ui_open:
                        self.character.toggle_stats_ui()
                    elif self.character.equipment_ui_open:
                        self.character.toggle_equipment_ui()
                    elif self.character.skills_ui_open:
                        self.character.toggle_skills_ui()
                    elif self.character.encyclopedia.is_open:
                        self.character.encyclopedia.toggle()
                    elif self.character.class_selection_open:
                        pass
                    else:
                        # Autosave on quit (unless temporary world)
                        if not self.temporary_world:
                            if self.save_manager.save_game(
                                self.character,
                                self.world,
                                self.character.quests,
                                self.npcs,
                                "autosave.json"
                            ):
                                print("💾 Autosaved on ESC quit")
                        self.running = False
                elif event.key == pygame.K_TAB:
                    tool_name = self.character.switch_tool()
                    if tool_name:
                        self.add_notification(f"Switched to {tool_name}", (100, 200, 255))
                elif event.key == pygame.K_c:
                    self.character.toggle_stats_ui()
                elif event.key == pygame.K_e:
                    self.character.toggle_equipment_ui()
                elif event.key == pygame.K_k:
                    self.character.toggle_skills_ui()
                elif event.key == pygame.K_l:
                    self.character.encyclopedia.toggle()
                elif event.key == pygame.K_f:
                    # NPC interaction
                    self.handle_npc_interaction()

                # Skill hotbar (keys 1-5)
                elif event.key == pygame.K_1:
                    success, msg = self.character.skills.use_skill(0, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_2:
                    success, msg = self.character.skills.use_skill(1, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_3:
                    success, msg = self.character.skills.use_skill(2, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_4:
                    success, msg = self.character.skills.use_skill(3, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_5:
                    success, msg = self.character.skills.use_skill(4, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_F1:
                    # Toggle infinite resources + level/stat points
                    if not self.debug_mode_active['f1']:
                        # ENABLE: Save original state and apply debug changes
                        self.debug_saved_state['f1'] = {
                            'level': self.character.leveling.level,
                            'unallocated_stat_points': self.character.leveling.unallocated_stat_points
                        }
                        Config.DEBUG_INFINITE_RESOURCES = True
                        self.character.leveling.level = self.character.leveling.max_level
                        self.character.leveling.unallocated_stat_points = 100
                        self.debug_mode_active['f1'] = True

                        print(f"🔧 DEBUG MODE F1 ENABLED:")
                        print(f"   • Infinite resources (no materials consumed)")
                        print(f"   • Level set to {self.character.leveling.level}")
                        print(f"   • 100 stat points available")
                        self.add_notification("Debug F1: ENABLED", (100, 255, 100))
                    else:
                        # DISABLE: Restore original state
                        Config.DEBUG_INFINITE_RESOURCES = False
                        if self.debug_saved_state['f1']:
                            self.character.leveling.level = self.debug_saved_state['f1']['level']
                            self.character.leveling.unallocated_stat_points = self.debug_saved_state['f1']['unallocated_stat_points']
                        self.debug_mode_active['f1'] = False

                        print(f"🔧 DEBUG MODE F1 DISABLED (restored original state)")
                        self.add_notification("Debug F1: DISABLED", (255, 100, 100))

                elif event.key == pygame.K_F2:
                    # Toggle: Learn all skills
                    if not self.debug_mode_active['f2']:
                        # ENABLE: Save original state and learn all skills
                        self.debug_saved_state['f2'] = {
                            'known_skills': dict(self.character.skills.known_skills),
                            'equipped_skills': list(self.character.skills.equipped_skills)
                        }

                        skill_db = SkillDatabase.get_instance()
                        if skill_db.loaded and skill_db.skills:
                            skills_learned = 0
                            for skill_id in skill_db.skills.keys():
                                if self.character.skills.learn_skill(skill_id, character=self, skip_checks=True):
                                    skills_learned += 1

                            # Equip first 5 skills to hotbar
                            skills_equipped = 0
                            for i, skill_id in enumerate(list(skill_db.skills.keys())[:5]):
                                if self.character.skills.equip_skill(skill_id, i):
                                    skills_equipped += 1

                            self.debug_mode_active['f2'] = True
                            print(f"🔧 DEBUG F2 ENABLED: Learned {skills_learned} skills, equipped {skills_equipped}")
                            self.add_notification(f"Debug F2: Learned {skills_learned} skills!", (100, 255, 100))
                        else:
                            print(f"⚠ WARNING: Skill database not loaded!")
                            self.add_notification("Skill DB not loaded!", (255, 100, 100))
                    else:
                        # DISABLE: Restore original skills
                        if self.debug_saved_state['f2']:
                            self.character.skills.known_skills = self.debug_saved_state['f2']['known_skills']
                            self.character.skills.equipped_skills = self.debug_saved_state['f2']['equipped_skills']
                        self.debug_mode_active['f2'] = False

                        print(f"🔧 DEBUG F2 DISABLED (restored original skills)")
                        self.add_notification("Debug F2: DISABLED", (255, 100, 100))

                elif event.key == pygame.K_F3:
                    # Toggle: Grant all titles
                    if not self.debug_mode_active['f3']:
                        # ENABLE: Save original state and grant all titles
                        self.debug_saved_state['f3'] = {
                            'earned_titles': list(self.character.titles.earned_titles)
                        }

                        title_db = TitleDatabase.get_instance()
                        if title_db.loaded and title_db.titles:
                            titles_granted = 0
                            for title in title_db.titles.values():
                                if title not in self.character.titles.earned_titles:
                                    self.character.titles.earned_titles.append(title)
                                    titles_granted += 1

                            self.debug_mode_active['f3'] = True
                            print(f"🔧 DEBUG F3 ENABLED: Granted {titles_granted} titles!")
                            self.add_notification(f"Debug F3: Granted {titles_granted} titles!", (100, 255, 100))
                        else:
                            print(f"⚠ WARNING: Title database not loaded!")
                            self.add_notification("Title DB not loaded!", (255, 100, 100))
                    else:
                        # DISABLE: Restore original titles
                        if self.debug_saved_state['f3']:
                            self.character.titles.earned_titles = self.debug_saved_state['f3']['earned_titles']
                        self.debug_mode_active['f3'] = False

                        print(f"🔧 DEBUG F3 DISABLED (restored original titles)")
                        self.add_notification("Debug F3: DISABLED", (255, 100, 100))

                elif event.key == pygame.K_F4:
                    # Toggle: Max out level and stats
                    if not self.debug_mode_active['f4']:
                        # ENABLE: Save original state and max everything
                        self.debug_saved_state['f4'] = {
                            'level': self.character.leveling.level,
                            'unallocated_stat_points': self.character.leveling.unallocated_stat_points,
                            'strength': self.character.stats.strength,
                            'defense': self.character.stats.defense,
                            'vitality': self.character.stats.vitality,
                            'luck': self.character.stats.luck,
                            'agility': self.character.stats.agility,
                            'intelligence': self.character.stats.intelligence
                        }

                        self.character.leveling.level = 30
                        self.character.leveling.unallocated_stat_points = 30
                        self.character.stats.strength = 30
                        self.character.stats.defense = 30
                        self.character.stats.vitality = 30
                        self.character.stats.luck = 30
                        self.character.stats.agility = 30
                        self.character.stats.intelligence = 30
                        self.character.recalculate_stats()

                        self.debug_mode_active['f4'] = True
                        print(f"🔧 DEBUG F4 ENABLED: Max level & stats!")
                        print(f"   • Level: 30")
                        print(f"   • All stats: 30")
                        print(f"   • Unallocated points: 30")
                        self.add_notification("Debug F4: Max level & stats!", (100, 255, 100))
                    else:
                        # DISABLE: Restore original stats
                        if self.debug_saved_state['f4']:
                            self.character.leveling.level = self.debug_saved_state['f4']['level']
                            self.character.leveling.unallocated_stat_points = self.debug_saved_state['f4']['unallocated_stat_points']
                            self.character.stats.strength = self.debug_saved_state['f4']['strength']
                            self.character.stats.defense = self.debug_saved_state['f4']['defense']
                            self.character.stats.vitality = self.debug_saved_state['f4']['vitality']
                            self.character.stats.luck = self.debug_saved_state['f4']['luck']
                            self.character.stats.agility = self.debug_saved_state['f4']['agility']
                            self.character.stats.intelligence = self.debug_saved_state['f4']['intelligence']
                            self.character.recalculate_stats()

                        self.debug_mode_active['f4'] = False
                        print(f"🔧 DEBUG F4 DISABLED (restored original stats)")
                        self.add_notification("Debug F4: DISABLED", (255, 100, 100))

                elif event.key == pygame.K_F5:
                    # Save game (only if not temporary world)
                    if self.temporary_world:
                        self.add_notification("Cannot save in temporary world!", (255, 200, 100))
                    else:
                        if self.save_manager.save_game(
                            self.character,
                            self.world,
                            self.character.quests,
                            self.npcs,
                            "autosave.json"
                        ):
                            self.add_notification("Game saved!", (100, 255, 100))

                elif event.key == pygame.K_F6:
                    # Quick save with timestamp
                    if not self.temporary_world:
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        if self.save_manager.save_game(
                            self.character,
                            self.world,
                            self.character.quests,
                            self.npcs,
                            f"save_{timestamp}.json"
                        ):
                            self.add_notification(f"Saved!", (100, 255, 100))

                elif event.key == pygame.K_F9:
                    # Load game (Shift+F9 for default save, F9 for autosave)
                    shift_held = pygame.K_LSHIFT in self.keys_pressed or pygame.K_RSHIFT in self.keys_pressed

                    if shift_held:
                        # Load default save
                        save_filename = "default_save.json"
                        load_message = "Default save loaded!"
                    else:
                        # Load autosave
                        save_filename = "autosave.json"
                        load_message = "Game loaded!"

                    save_data = self.save_manager.load_game(save_filename)
                    if save_data:
                        # Restore character state
                        self.character.restore_from_save(save_data["player"])

                        # Restore world state
                        self.world.restore_from_save(save_data["world_state"])

                        # Restore quest state
                        self.character.quests.restore_from_save(save_data["quest_state"])

                        # Restore NPC state
                        SaveManager.restore_npc_state(self.npcs, save_data["npc_state"])

                        # Reset camera
                        self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
                        self.add_notification(load_message, (100, 255, 100))
                    else:
                        if shift_held:
                            self.add_notification("Default save not found! Run: python save_system/create_default_save.py", (255, 100, 100))
                        else:
                            self.add_notification("No save file found!", (255, 100, 100))

                elif event.key == pygame.K_F10:
                    # Run automated test suite
                    print("\n🧪 Running Automated Test Suite...")
                    self.test_system.run_all_tests()
                    self.add_notification("Test suite completed - check console", (100, 200, 255))

                elif event.key == pygame.K_F11:
                    # Toggle fullscreen
                    flags = Config.toggle_fullscreen()
                    self.screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT), flags)
                    self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
                    mode = "Fullscreen" if Config.FULLSCREEN else "Windowed"
                    self.add_notification(f"Switched to {mode} mode", (100, 200, 255))
                    print(f"🖥️  Switched to {mode}: {Config.SCREEN_WIDTH}x{Config.SCREEN_HEIGHT}")

            elif event.type == pygame.KEYUP:
                self.keys_pressed.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos

                # Handle slider dragging for betting
                if self.active_minigame and self.minigame_type == 'adornments':
                    state = self.active_minigame.get_state()
                    if state.get('phase') == 'betting' and event.buttons[0]:  # Left mouse button held
                        if hasattr(self, 'wheel_slider_rect') and self.wheel_slider_rect:
                            if self.wheel_slider_rect.collidepoint(event.pos):
                                # Calculate bet amount from slider position
                                max_currency, slider_x, slider_w = self.wheel_slider_info
                                local_x = event.pos[0] - self.wheel_slider_rect.x
                                slider_pos = max(0, min(local_x, slider_w))
                                bet_amount = int((slider_pos / slider_w) * max_currency)
                                self.wheel_slider_bet_amount = max(1, min(bet_amount, max_currency))
            elif event.type == pygame.MOUSEWHEEL:
                # Skip if no character exists yet
                if self.character is None:
                    continue

                # Handle mouse wheel scrolling for recipe list
                if self.character.crafting_ui_open and self.crafting_window_rect:
                    if self.crafting_window_rect.collidepoint(self.mouse_pos):
                        # Scroll the recipe list
                        self.recipe_scroll_offset -= event.y  # event.y is positive for scroll up

                        # Calculate max scroll based on current recipe list
                        if self.crafting_recipes:
                            mat_db = MaterialDatabase.get_instance()
                            equip_db = EquipmentDatabase.get_instance()
                            s = Config.scale

                            # Build flat list (same as renderer/click handler)
                            grouped_recipes = self.renderer._group_recipes_by_type(self.crafting_recipes, equip_db, mat_db)
                            flat_list = []
                            for type_name, type_recipes in grouped_recipes:
                                flat_list.append(('header', type_name))
                                for recipe in type_recipes:
                                    flat_list.append(('recipe', recipe))

                            total_items = len(flat_list)

                            # Calculate how many items can actually fit on screen
                            # Simulate rendering to count items that fit
                            wh = Config.MENU_MEDIUM_H
                            max_y = wh - s(20)
                            y_test = s(70)
                            items_that_fit = 0

                            for item in flat_list:
                                if item[0] == 'header':
                                    needed_height = s(28)
                                else:
                                    recipe = item[1]
                                    num_inputs = len(recipe.inputs)
                                    needed_height = max(s(70), s(35) + num_inputs * s(16) + s(5)) + s(8)

                                if y_test + needed_height > max_y:
                                    break
                                items_that_fit += 1
                                y_test += needed_height

                            # Max scroll is total items minus how many fit on screen
                            max_scroll = max(0, total_items - items_that_fit)

                            # Clamp scroll offset to valid range [0, max_scroll]
                            self.recipe_scroll_offset = max(0, min(self.recipe_scroll_offset, max_scroll))
                        else:
                            self.recipe_scroll_offset = max(0, self.recipe_scroll_offset)
                # Handle mouse wheel scrolling for encyclopedia
                elif self.character.encyclopedia.is_open and hasattr(self, 'encyclopedia_window_rect') and self.encyclopedia_window_rect:
                    if self.encyclopedia_window_rect.collidepoint(self.mouse_pos):
                        # Scroll the encyclopedia content
                        self.character.encyclopedia.scroll_offset -= event.y * 20  # Scroll by 20 pixels per wheel notch
                        # Clamp to valid range (min 0, max handled in render)
                        self.character.encyclopedia.scroll_offset = max(0, self.character.encyclopedia.scroll_offset)
                # Handle mouse wheel scrolling for skills menu
                elif self.character.skills_ui_open:
                    # Scroll the skills list
                    self.character.skills_menu_scroll_offset -= event.y  # event.y is positive for scroll up
                    # Clamp is handled in render_skills_menu_ui
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_buttons_pressed.add(1)
                self.handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_buttons_pressed.discard(1)
                self.handle_mouse_release(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                # Right-click handler (for consumables and offhand attacks)
                self.mouse_buttons_pressed.add(3)
                shift_held = pygame.K_LSHIFT in self.keys_pressed or pygame.K_RSHIFT in self.keys_pressed
                self.handle_right_click(event.pos, shift_held)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                # Right mouse button released
                self.mouse_buttons_pressed.discard(3)

    def handle_right_click(self, mouse_pos: Tuple[int, int], shift_held: bool = False):
        """Handle right-click events (SHIFT+right for consumables, right-click for offhand attacks)"""
        # Check if clicking on UI elements first (high priority)
        if self.start_menu_open or self.active_minigame or self.enchantment_selection_active:
            return  # Don't handle right-click on UI

        # Skip if no character exists yet
        if self.character is None:
            return

        if self.character.class_selection_open or self.character.skills_ui_open:
            return  # Don't handle right-click on UI

        if self.character.stats_ui_open or self.character.encyclopedia.is_open:
            return  # Don't handle right-click on UI

        if self.npc_dialogue_open or self.character.equipment_ui_open:
            return  # Don't handle right-click on UI

        # Handle inventory SHIFT+right-clicks for consumables
        if shift_held and mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
            start_x, start_y = 20, Config.INVENTORY_PANEL_Y
            slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
            rel_x, rel_y = mouse_pos[0] - start_x, mouse_pos[1] - start_y

            if rel_x >= 0 and rel_y >= 0:
                col, row = rel_x // (slot_size + spacing), rel_y // (slot_size + spacing)
                in_x = rel_x % (slot_size + spacing) < slot_size
                in_y = rel_y % (slot_size + spacing) < slot_size

                if in_x and in_y:
                    idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                    if 0 <= idx < self.character.inventory.max_slots:
                        item_stack = self.character.inventory.slots[idx]
                        if item_stack:
                            mat_db = MaterialDatabase.get_instance()
                            item_def = mat_db.get_material(item_stack.item_id)
                            if item_def:
                                # Check if item is consumable
                                if item_def.category == "consumable":
                                    # Use ONE consumable from THIS SPECIFIC stack
                                    crafted_stats = item_stack.crafted_stats if hasattr(item_stack, 'crafted_stats') else None
                                    success, message = self.character.use_consumable(item_stack.item_id, crafted_stats, consume_from_inventory=False)
                                    if success:
                                        # Manually decrement from THIS specific slot (not the first matching item_id)
                                        if item_stack.quantity > 1:
                                            item_stack.quantity -= 1
                                        else:
                                            self.character.inventory.slots[idx] = None
                                        self.add_notification(message, (100, 255, 100))
                                    else:
                                        self.add_notification(message, (255, 100, 100))
            return  # Don't process world clicks if SHIFT+clicking on inventory

        # Handle world right-clicks for offhand attacks
        if mouse_pos[0] >= Config.VIEWPORT_WIDTH:
            return  # Don't attack outside viewport

        # Get offhand weapon
        offhand_weapon = self.character.equipment.slots.get('offHand')
        if not offhand_weapon:
            return  # No offhand equipped

        # Convert to world coordinates
        wx = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
        wy = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y

        # Check for enemy at position
        enemy = self.combat_manager.get_enemy_at_position((wx, wy))
        if enemy and enemy.is_alive:
            # Check if offhand can attack
            if not self.character.can_attack('offHand'):
                return  # Still on cooldown

            # Check if in range (using offhand weapon's range)
            weapon_range = self.character.equipment.get_weapon_range('offHand')
            dist = enemy.distance_to((self.character.position.x, self.character.position.y))
            if dist > weapon_range:
                self.add_notification(f"Enemy too far (offhand range: {weapon_range})", (255, 100, 100))
                return

            # Attack with offhand (using tag system)
            effect_tags, effect_params = self._get_weapon_effect_data('offHand')
            damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(
                enemy, effect_tags, effect_params
            )
            self.damage_numbers.append(DamageNumber(int(damage), Position(enemy.position[0], enemy.position[1], 0), is_crit))
            self.character.reset_attack_cooldown(is_weapon=True, hand='offHand')

            if not enemy.is_alive:
                self.add_notification(f"Defeated {enemy.definition.name}!", (255, 215, 0))
                self.character.activities.record_activity('combat', 1)

                # Show loot notifications (auto-looted)
                if loot:
                    mat_db = MaterialDatabase.get_instance()
                    for material_id, qty in loot:
                        mat = mat_db.get_material(material_id)
                        item_name = mat.name if mat else material_id
                        self.add_notification(f"+{qty} {item_name}", (100, 255, 100))

    def handle_npc_dialogue_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks on NPC dialogue buttons (accept/turn in quests)"""
        for button_info in self.npc_dialogue_buttons:
            action, quest_id, button_rect = button_info
            if button_rect.collidepoint(mouse_pos):
                npc_db = NPCDatabase.get_instance()

                if action == 'accept':
                    # Accept quest
                    if quest_id in npc_db.quests:
                        quest_def = npc_db.quests[quest_id]
                        if self.character.quests.start_quest(quest_def, self.character):
                            print(f"📜 Quest accepted: {quest_def.title}")
                            self.add_notification(f"Quest accepted: {quest_def.title}", (100, 255, 100))
                            # Update dialogue state
                            self.npc_available_quests.remove(quest_id)
                            # Refresh NPC dialogue to show updated quest list
                            self.npc_dialogue_lines = [self.active_npc.get_next_dialogue()]
                            self.npc_available_quests = self.active_npc.get_available_quests(self.character.quests)
                            self.npc_quest_to_turn_in = self.active_npc.has_quest_to_turn_in(self.character.quests, self.character)
                        else:
                            self.add_notification("Already have this quest!", (255, 100, 100))

                elif action == 'turn_in':
                    # Turn in quest
                    success, messages = self.character.quests.complete_quest(quest_id, self.character)
                    if success:
                        print(f"✅ Quest completed: {quest_id}")
                        for msg in messages:
                            print(f"   {msg}")
                            self.add_notification(msg, (100, 255, 100))

                        # Show completion dialogue
                        if quest_id in npc_db.quests:
                            quest_def = npc_db.quests[quest_id]
                            self.npc_dialogue_lines = quest_def.completion_dialogue

                        # Update quest state
                        self.npc_quest_to_turn_in = None
                        self.npc_available_quests = self.active_npc.get_available_quests(self.character.quests)
                    else:
                        print(f"❌ Failed to turn in quest: {messages}")
                        for msg in messages:
                            self.add_notification(msg, (255, 100, 100))
                break

    def handle_npc_interaction(self):
        """Handle F key press to interact with nearby NPCs"""
        # If dialogue is already open, close it
        if self.npc_dialogue_open:
            self.npc_dialogue_open = False
            self.active_npc = None
            self.npc_dialogue_lines = []
            self.npc_available_quests = []
            self.npc_quest_to_turn_in = None
            return

        # Find nearby NPC
        nearby_npc = None
        for npc in self.npcs:
            if npc.is_near(self.character.position):
                nearby_npc = npc
                break

        if nearby_npc:
            # Open dialogue with this NPC
            self.npc_dialogue_open = True
            self.active_npc = nearby_npc

            # Get dialogue lines
            self.npc_dialogue_lines = [nearby_npc.get_next_dialogue()]

            # Check for available quests
            self.npc_available_quests = nearby_npc.get_available_quests(self.character.quests)

            # Check for completable quests
            self.npc_quest_to_turn_in = nearby_npc.has_quest_to_turn_in(self.character.quests, self.character)

            print(f"💬 Talking to {nearby_npc.npc_def.name}")
            if self.npc_available_quests:
                print(f"   📜 {len(self.npc_available_quests)} quest(s) available")
            if self.npc_quest_to_turn_in:
                print(f"   ✅ Quest ready to turn in: {self.npc_quest_to_turn_in}")
        else:
            self.add_notification("No one nearby to talk to", (200, 200, 200))

    def handle_start_menu_selection(self, option_index: int):
        """Handle start menu option selection (0=New World, 1=Load World, 2=Load Default Save, 3=Temporary World)"""
        if option_index == 0:
            # New World - Create new character
            print("🌍 Starting new world...")
            self.start_menu_open = False
            self.temporary_world = False
            self.character = Character(Position(50.0, 50.0, 0.0))
            # Update combat manager with new character
            self.combat_manager.character = self.character
            # Spawn initial enemies
            self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)
            # Spawn training dummy for tag testing
            from systems.training_dummy import spawn_training_dummy
            spawn_training_dummy(self.combat_manager, (60.0, 50.0))
            self.add_notification("Welcome to your new world!", (100, 255, 100))

            # Open class selection for new character
            if not self.character.class_system.current_class:
                self.character.class_selection_open = True
                print("✓ Opening class selection...")

        elif option_index == 1:
            # Load World - Load from autosave.json using new SaveManager
            print("📂 Loading saved world...")
            save_data = self.save_manager.load_game("autosave.json")
            if save_data:
                self.start_menu_open = False
                self.temporary_world = False

                # Create character at starting position first
                self.character = Character(Position(50.0, 50.0, 0.0))

                # Restore character state from save
                self.character.restore_from_save(save_data["player"])

                # Restore world state (placed entities, modified resources)
                self.world.restore_from_save(save_data["world_state"])

                # Restore quest state
                self.character.quests.restore_from_save(save_data["quest_state"])

                # Restore NPC state
                SaveManager.restore_npc_state(self.npcs, save_data["npc_state"])

                # Update combat manager with loaded character
                self.combat_manager.character = self.character

                # Spawn enemies near loaded position
                self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)

                # Spawn training dummy for tag testing
                from systems.training_dummy import spawn_training_dummy
                spawn_training_dummy(self.combat_manager, (60.0, 50.0))

                print(f"✓ Loaded character: Level {self.character.leveling.level}")
                self.add_notification("World loaded successfully!", (100, 255, 100))
            else:
                # Keep menu open and show notification
                print("❌ No save file found or failed to load")
                self.add_notification("No save file found! Create a new world or use Temporary World.", (255, 100, 100))

        elif option_index == 2:
            # Load Default Save - Load from default_save.json
            print("📂 Loading default save...")
            save_data = self.save_manager.load_game("default_save.json")
            if save_data:
                self.start_menu_open = False
                self.temporary_world = False

                # Create character at starting position first
                self.character = Character(Position(50.0, 50.0, 0.0))

                # Restore character state from save
                self.character.restore_from_save(save_data["player"])

                # Restore world state (placed entities, modified resources)
                self.world.restore_from_save(save_data["world_state"])

                # Restore quest state
                self.character.quests.restore_from_save(save_data["quest_state"])

                # Restore NPC state
                SaveManager.restore_npc_state(self.npcs, save_data["npc_state"])

                # Update combat manager with loaded character
                self.combat_manager.character = self.character

                # Spawn enemies near loaded position
                self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)

                # Spawn training dummy for tag testing
                from systems.training_dummy import spawn_training_dummy
                spawn_training_dummy(self.combat_manager, (60.0, 50.0))

                print(f"✓ Loaded default save: Level {self.character.leveling.level}")
                self.add_notification("Default save loaded successfully!", (100, 255, 100))
            else:
                # Keep menu open and show notification
                print("❌ Default save file not found!")
                print("   Run 'python save_system/create_default_save.py' to create it.")
                self.add_notification("Default save not found! Run: python save_system/create_default_save.py", (255, 100, 100))

        elif option_index == 3:
            # Temporary World - Create character but prevent saving
            print("🌍 Starting temporary world (no saves)...")
            self.start_menu_open = False
            self.temporary_world = True
            self.character = Character(Position(50.0, 50.0, 0.0))
            # Update combat manager with new character
            self.combat_manager.character = self.character
            # Spawn initial enemies
            self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)
            # Spawn training dummy for tag testing
            from systems.training_dummy import spawn_training_dummy
            spawn_training_dummy(self.combat_manager, (60.0, 50.0))
            self.add_notification("Temporary world started (no saves)", (255, 215, 0))

            # Open class selection for new character
            if not self.character.class_system.current_class:
                self.character.class_selection_open = True
                print("✓ Opening class selection...")

    def handle_mouse_click(self, mouse_pos: Tuple[int, int]):
        # Start menu clicks (highest priority)
        if self.start_menu_open:
            if hasattr(self, 'start_menu_buttons') and self.start_menu_buttons:
                for idx, button_rect in enumerate(self.start_menu_buttons):
                    if button_rect.collidepoint(mouse_pos):
                        self.handle_start_menu_selection(idx)
                        return
            return  # Ignore all other clicks when start menu is open

        shift_held = pygame.K_LSHIFT in self.keys_pressed or pygame.K_RSHIFT in self.keys_pressed

        # Check double-click (increased from 300ms to 500ms for better reliability)
        current_time = pygame.time.get_ticks()
        is_double_click = (current_time - self.last_click_time < 500)
        self.last_click_time = current_time

        # Minigame button clicks (highest priority)
        if self.active_minigame:
            # Check spinning wheel minigame clicks
            if self.minigame_type == 'adornments':
                state = self.active_minigame.get_state()
                phase = state.get('phase', 'betting')

                # Handle betting phase
                if phase == 'betting':
                    # Handle slider drag
                    if hasattr(self, 'wheel_slider_rect') and self.wheel_slider_rect:
                        if self.wheel_slider_rect.collidepoint(mouse_pos):
                            # Calculate bet amount from slider position
                            max_currency, slider_x, slider_w = self.wheel_slider_info
                            local_x = mouse_pos[0] - self.wheel_slider_rect.x
                            slider_pos = max(0, min(local_x, slider_w))
                            bet_amount = int((slider_pos / slider_w) * max_currency)
                            self.wheel_slider_bet_amount = max(1, min(bet_amount, max_currency))
                            return

                    # Handle quick bet buttons (set slider amount)
                    if hasattr(self, 'wheel_bet_buttons'):
                        for btn_rect, amount in self.wheel_bet_buttons:
                            if btn_rect.collidepoint(mouse_pos):
                                if amount <= state.get('current_currency', 0):
                                    self.wheel_slider_bet_amount = amount
                                    print(f"✓ Bet amount set to ${amount}")
                                return

                    # Handle confirm bet button
                    if hasattr(self, 'wheel_confirm_bet_button') and self.wheel_confirm_bet_button:
                        if self.wheel_confirm_bet_button.collidepoint(mouse_pos):
                            if self.active_minigame.place_bet(self.wheel_slider_bet_amount):
                                print(f"✓ Bet placed: ${self.wheel_slider_bet_amount}")
                            return

                # Handle spin button click
                if phase == 'ready_to_spin' and hasattr(self, 'wheel_spin_button'):
                    if self.wheel_spin_button and self.wheel_spin_button.collidepoint(mouse_pos):
                        if self.active_minigame.spin_wheel():
                            print("🎡 Spinning wheel...")
                        return

                # Handle next button click
                if phase == 'spin_result' and hasattr(self, 'wheel_next_button'):
                    if self.wheel_next_button and self.wheel_next_button.collidepoint(mouse_pos):
                        self.active_minigame.advance_to_next_spin()
                        # Reset slider for next spin
                        if hasattr(self, 'wheel_slider_bet_amount'):
                            next_currency = self.active_minigame.current_currency
                            self.wheel_slider_bet_amount = min(self.wheel_slider_bet_amount, next_currency)
                        return

                # Handle completion click (anywhere in window)
                if phase == 'completed' and hasattr(self, 'enchanting_minigame_window'):
                    if self.enchanting_minigame_window.collidepoint(mouse_pos):
                        # Complete the minigame
                        self._complete_minigame()
                        # Clean up slider state
                        if hasattr(self, 'wheel_slider_bet_amount'):
                            delattr(self, 'wheel_slider_bet_amount')
                        return

            # Check engineering puzzle cells first (rotation/sliding)
            if self.minigame_type == 'engineering' and hasattr(self, 'engineering_puzzle_rects'):
                for rect, action_data in self.engineering_puzzle_rects:
                    if rect.collidepoint(mouse_pos):
                        action_type = action_data[0]
                        row, col = action_data[1], action_data[2]

                        if action_type == 'rotate':
                            # Rotate pipe piece
                            self.active_minigame.handle_action('rotate', row=row, col=col)
                        elif action_type == 'slide':
                            # Slide tile
                            self.active_minigame.handle_action('slide', row=row, col=col)

                        # Check if puzzle was solved
                        if self.active_minigame.check_current_puzzle():
                            print(f"✅ Puzzle {self.active_minigame.current_puzzle_index}/{self.active_minigame.puzzle_count} solved!")
                        return

            if hasattr(self, 'minigame_button_rect') and self.minigame_button_rect:
                if self.minigame_button_rect.collidepoint(mouse_pos):
                    # Handle minigame-specific buttons
                    if self.minigame_type == 'smithing':
                        self.active_minigame.handle_hammer()
                    elif self.minigame_type == 'alchemy':
                        # Chain button (minigame_button_rect is chain button)
                        self.active_minigame.chain()
                    elif self.minigame_type == 'engineering':
                        # Complete button for placeholder puzzles
                        self.active_minigame.check_current_puzzle()
                    # Removed adornments button handler - now uses specific wheel buttons
                    return
            # Check secondary button (alchemy stabilize)
            if hasattr(self, 'minigame_button_rect2') and self.minigame_button_rect2:
                if self.minigame_button_rect2.collidepoint(mouse_pos):
                    if self.minigame_type == 'alchemy':
                        self.active_minigame.stabilize()
                    return
            # Consume all clicks when minigame is active (don't interact with world)
            return

        # Skip character-dependent clicks if no character exists yet
        if self.character is None:
            return

        # Enchantment selection UI (priority over other UIs)
        if self.enchantment_selection_active and self.enchantment_selection_rect:
            if self.enchantment_selection_rect.collidepoint(mouse_pos):
                self.handle_enchantment_selection_click(mouse_pos)
                return

        # Class selection
        if self.character.class_selection_open and self.class_selection_rect:
            if self.class_selection_rect.collidepoint(mouse_pos):
                self.handle_class_selection_click(mouse_pos)
                return

        # Skills UI
        if self.character.skills_ui_open and self.skills_window_rect:
            if self.skills_window_rect.collidepoint(mouse_pos):
                self.handle_skills_menu_click(mouse_pos)
                return
            # Click outside skills UI - close it
            else:
                self.character.toggle_skills_ui()
                return

        # Stats UI
        if self.character.stats_ui_open and self.stats_window_rect:
            if self.stats_window_rect.collidepoint(mouse_pos):
                self.handle_stats_click(mouse_pos)
                return
            # Click outside stats UI - close it
            else:
                self.character.toggle_stats_ui()
                return

        # Encyclopedia UI
        if self.character.encyclopedia.is_open and self.encyclopedia_window_rect:
            if self.encyclopedia_window_rect.collidepoint(mouse_pos):
                self.handle_encyclopedia_click(mouse_pos)
                return
            # Click outside encyclopedia UI - close it
            else:
                self.character.encyclopedia.toggle()
                return

        # NPC Dialogue UI
        if self.npc_dialogue_open and self.npc_dialogue_window_rect:
            if self.npc_dialogue_window_rect.collidepoint(mouse_pos):
                self.handle_npc_dialogue_click(mouse_pos)
                return
            # Click outside dialogue UI - close it
            else:
                self.handle_npc_interaction()  # Close dialogue
                return

        # Equipment UI
        if self.character.equipment_ui_open and self.equipment_window_rect:
            if self.equipment_window_rect.collidepoint(mouse_pos):
                self.handle_equipment_click(mouse_pos, shift_held)
                return
            # Click outside equipment UI - close it
            else:
                self.character.toggle_equipment_ui()
                return

        # Crafting UI
        if self.character.crafting_ui_open and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                self.handle_craft_click(mouse_pos)
                return
            # Click outside crafting UI - close it
            else:
                self.character.close_crafting_ui()
                return

        # Inventory - check for equipment equipping
        if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
            # CRITICAL: These values MUST match the renderer exactly!
            # Renderer: tools_y = INVENTORY_PANEL_Y + 35 + 20 = +55
            # Renderer: start_y = tools_y + 50 (tool slot) + 20 = INVENTORY_PANEL_Y + 125
            tools_y = Config.INVENTORY_PANEL_Y + 55
            tool_slot_size = 50
            start_x = 20
            start_y = tools_y + tool_slot_size + 20  # = INVENTORY_PANEL_Y + 125
            slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
            rel_x, rel_y = mouse_pos[0] - start_x, mouse_pos[1] - start_y

            if rel_x >= 0 and rel_y >= 0:
                col, row = rel_x // (slot_size + spacing), rel_y // (slot_size + spacing)
                in_x = rel_x % (slot_size + spacing) < slot_size
                in_y = rel_y % (slot_size + spacing) < slot_size

                if in_x and in_y:
                    idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                    if 0 <= idx < self.character.inventory.max_slots:
                        # Double-click to equip equipment or tools
                        if is_double_click and self.last_clicked_slot == idx:
                            # Check if item is being dragged (first click started drag)
                            # If so, cancel drag and use the dragging_stack
                            if self.character.inventory.dragging_slot == idx:
                                item_stack = self.character.inventory.dragging_stack
                                self.character.inventory.cancel_drag()
                            else:
                                item_stack = self.character.inventory.slots[idx]

                            print(f"\n🖱️  Double-click detected on slot {idx}")
                            if item_stack:
                                print(f"   Item: {item_stack.item_id}")
                                is_equip = item_stack.is_equipment()
                                print(f"   is_equipment(): {is_equip}")
                                if is_equip:
                                    equipment = item_stack.get_equipment()
                                    print(f"   get_equipment(): {equipment}")
                                    if equipment:
                                        # Put item back in slot before equipping
                                        self.character.inventory.slots[idx] = item_stack
                                        # Equip all equipment (including tools) using standard equipment system
                                        success, msg = self.character.try_equip_from_inventory(idx)
                                        if success:
                                            self.add_notification(f"Equipped {equipment.name}", (100, 255, 100))
                                        else:
                                                self.add_notification(f"Cannot equip: {msg}", (255, 100, 100))
                                    else:
                                        print(f"   ❌ equipment is None!")
                                        self.add_notification("Invalid equipment data", (255, 100, 100))
                                        # Put item back if equipping failed
                                        self.character.inventory.slots[idx] = item_stack
                                else:
                                    # Check if it's a placeable item (turret, trap, station)
                                    mat_def = MaterialDatabase.get_instance().get_material(item_stack.item_id)
                                    if mat_def and mat_def.placeable:
                                        # Place item at player's position (snapped to grid)
                                        player_pos = self.character.position.snap_to_grid()

                                        # Check if square is already occupied
                                        existing_entity = self.world.get_entity_at(player_pos)
                                        if existing_entity:
                                            self.add_notification("Square already occupied!", (255, 100, 100))
                                            self.character.inventory.slots[idx] = item_stack
                                            return

                                        # Determine entity type using EngineeringTagProcessor
                                        from core.crafting_tag_processor import EngineeringTagProcessor

                                        # Get tags from material definition
                                        mat_tags = mat_def.metadata.get('tags', []) if hasattr(mat_def, 'metadata') and mat_def.metadata else []

                                        # Use tag processor to determine behavior type
                                        if mat_tags:
                                            behavior_type = EngineeringTagProcessor.get_behavior_type(mat_tags)

                                            # Map behavior type to PlacedEntityType
                                            behavior_to_entity_map = {
                                                'placeable_combat': PlacedEntityType.TURRET,
                                                'placeable_triggered': PlacedEntityType.TRAP,
                                                'placeable_crafting': PlacedEntityType.CRAFTING_STATION,
                                                'usable': PlacedEntityType.UTILITY_DEVICE,  # Usable items placed like devices
                                                'consumable': PlacedEntityType.BOMB,        # Consumables placed as bombs
                                                'placeable': PlacedEntityType.UTILITY_DEVICE,  # Generic placeable
                                            }
                                            entity_type = behavior_to_entity_map.get(behavior_type, PlacedEntityType.TURRET)
                                        else:
                                            # Fallback to legacy logic if no tags
                                            if mat_def.category == 'station':
                                                entity_type = PlacedEntityType.CRAFTING_STATION
                                            else:
                                                entity_type_map = {
                                                    'turret': PlacedEntityType.TURRET,
                                                    'trap': PlacedEntityType.TRAP,
                                                    'bomb': PlacedEntityType.BOMB,
                                                    'utility': PlacedEntityType.UTILITY_DEVICE,
                                                }
                                                entity_type = entity_type_map.get(mat_def.item_type, PlacedEntityType.TURRET)

                                        # Extract effect tags and params for tag system
                                        effect_tags = mat_def.effect_tags if hasattr(mat_def, 'effect_tags') else []
                                        effect_params = mat_def.effect_params if hasattr(mat_def, 'effect_params') else {}

                                        # Parse stats from effect string (only for combat entities) - legacy fallback
                                        range_val = effect_params.get('range', 5.0)
                                        damage_val = effect_params.get('baseDamage', 20.0)
                                        if entity_type != PlacedEntityType.CRAFTING_STATION and mat_def.effect and not effect_tags:
                                            import re
                                            range_match = re.search(r'(\d+)\s*unit range', mat_def.effect)
                                            damage_match = re.search(r'(\d+)\s*damage', mat_def.effect)
                                            if range_match:
                                                range_val = float(range_match.group(1))
                                            if damage_match:
                                                damage_val = float(damage_match.group(1))

                                        # Place the entity (with tags)
                                        self.world.place_entity(
                                            player_pos,
                                            item_stack.item_id,
                                            entity_type,
                                            tier=mat_def.tier,
                                            range=range_val if entity_type != PlacedEntityType.CRAFTING_STATION else 0.0,
                                            damage=damage_val if entity_type != PlacedEntityType.CRAFTING_STATION else 0.0,
                                            tags=effect_tags,
                                            effect_params=effect_params
                                        )

                                        # Remove one item from inventory
                                        if item_stack.quantity > 1:
                                            item_stack.quantity -= 1
                                            self.character.inventory.slots[idx] = item_stack
                                        else:
                                            self.character.inventory.slots[idx] = None

                                        self.add_notification(f"Placed {mat_def.name}", (100, 255, 100))
                                        print(f"✓ Placed {mat_def.name} at player position")
                                    elif mat_def and mat_def.category == "consumable":
                                        # Double-click to use consumable - use ONE from THIS SPECIFIC stack
                                        crafted_stats = item_stack.crafted_stats if hasattr(item_stack, 'crafted_stats') else None
                                        success, message = self.character.use_consumable(item_stack.item_id, crafted_stats, consume_from_inventory=False)
                                        if success:
                                            # Manually decrement from THIS specific slot (not the first matching item_id)
                                            if item_stack.quantity > 1:
                                                item_stack.quantity -= 1
                                            else:
                                                self.character.inventory.slots[idx] = None
                                            self.add_notification(message, (100, 255, 100))
                                        else:
                                            self.add_notification(message, (255, 100, 100))
                                    else:
                                        print(f"   ⚠️  Not equipment, placeable, or consumable, skipping")
                                        # Put non-actionable item back in slot
                                        self.character.inventory.slots[idx] = item_stack
                            else:
                                print(f"   ⚠️  item_stack is None")
                            # Reset last_clicked_slot to prevent repeated double-clicks
                            self.last_clicked_slot = None
                            return

                        self.last_clicked_slot = idx

                        # Regular drag
                        if self.character.inventory.slots[idx] is not None:
                            self.character.inventory.start_drag(idx)
            return

        # World interaction
        if mouse_pos[0] >= Config.VIEWPORT_WIDTH:
            return

        wx = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
        wy = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y
        world_pos = Position(wx, wy, 0)

        # Check for enemy click (living enemies)
        enemy = self.combat_manager.get_enemy_at_position((wx, wy))
        if enemy and enemy.is_alive:
            # Check if player can attack with mainhand
            if not self.character.can_attack('mainHand'):
                return  # Still on cooldown

            # Check if in range (using mainhand weapon's range)
            weapon_range = self.character.equipment.get_weapon_range('mainHand')
            dist = enemy.distance_to((self.character.position.x, self.character.position.y))
            if dist > weapon_range:
                weapon_name = self.character.equipment.slots.get('mainHand')
                range_msg = f"Enemy too far (range: {weapon_range})" if weapon_name else "Enemy too far away"
                self.add_notification(range_msg, (255, 100, 100))
                return

            # Attack enemy with mainhand (using tag system)
            effect_tags, effect_params = self._get_weapon_effect_data('mainHand')
            damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(
                enemy, effect_tags, effect_params
            )
            self.damage_numbers.append(DamageNumber(int(damage), Position(enemy.position[0], enemy.position[1], 0), is_crit))
            self.character.reset_attack_cooldown(is_weapon=True, hand='mainHand')

            if not enemy.is_alive:
                self.add_notification(f"Defeated {enemy.definition.name}!", (255, 215, 0))
                self.character.activities.record_activity('combat', 1)

                # Show loot notifications (auto-looted)
                if loot:
                    mat_db = MaterialDatabase.get_instance()
                    for material_id, qty in loot:
                        mat = mat_db.get_material(material_id)
                        item_name = mat.name if mat else material_id
                        self.add_notification(f"+{qty} {item_name}", (100, 255, 100))
            return

        # Note: Corpse looting is now automatic when enemy dies
        # Manual corpse looting has been removed as loot is auto-added to inventory

        # Check for placed entity pickup (turrets, traps, etc.)
        if is_double_click:
            placed_entity = self.world.get_entity_at(world_pos)
            if placed_entity:
                # Check if entity is pickupable (not crafting stations)
                pickupable_types = [
                    PlacedEntityType.TURRET,
                    PlacedEntityType.TRAP,
                    PlacedEntityType.BOMB,
                    PlacedEntityType.UTILITY_DEVICE
                ]
                if placed_entity.entity_type in pickupable_types:
                    # Check if player is in range (use 2.0 units as pickup range)
                    dist = self.character.position.distance_to(placed_entity.position)
                    if dist <= 2.0:
                        # Add item back to inventory
                        mat_db = MaterialDatabase.get_instance()
                        mat_def = mat_db.get_material(placed_entity.item_id)
                        if mat_def:
                            # Try to add to inventory
                            success = self.character.inventory.add_item(placed_entity.item_id, 1)
                            if success:
                                # Remove from world
                                self.world.placed_entities.remove(placed_entity)
                                self.add_notification(f"Picked up {mat_def.name}", (100, 255, 100))
                                print(f"✓ Picked up {mat_def.name}")
                                return
                            else:
                                self.add_notification("Inventory full!", (255, 100, 100))
                                return
                    else:
                        self.add_notification("Too far to pick up", (255, 100, 100))
                        return

        station = self.world.get_station_at(world_pos)

        # Also check placed entities for crafting stations
        if not station:
            placed_entity = self.world.get_entity_at(world_pos)
            if placed_entity and placed_entity.entity_type == PlacedEntityType.CRAFTING_STATION:
                # Convert placed entity to a CraftingStation for interaction
                # Determine station type from item_id
                station_type_map = {
                    # New format from items-smithing-2.JSON
                    'forge_t1': StationType.SMITHING,
                    'forge_t2': StationType.SMITHING,
                    'forge_t3': StationType.SMITHING,
                    'forge_t4': StationType.SMITHING,
                    'alchemy_table_t1': StationType.ALCHEMY,
                    'alchemy_table_t2': StationType.ALCHEMY,
                    'alchemy_table_t3': StationType.ALCHEMY,
                    'alchemy_table_t4': StationType.ALCHEMY,
                    'refinery_t1': StationType.REFINING,
                    'refinery_t2': StationType.REFINING,
                    'refinery_t3': StationType.REFINING,
                    'refinery_t4': StationType.REFINING,
                    'engineering_bench_t1': StationType.ENGINEERING,
                    'engineering_bench_t2': StationType.ENGINEERING,
                    'engineering_bench_t3': StationType.ENGINEERING,
                    'engineering_bench_t4': StationType.ENGINEERING,
                    'enchanting_table_t1': StationType.ADORNMENTS,
                    'enchanting_table_t2': StationType.ADORNMENTS,
                    'enchanting_table_t3': StationType.ADORNMENTS,
                    'enchanting_table_t4': StationType.ADORNMENTS,
                    # Legacy format from crafting-stations-1.JSON (for backward compatibility)
                    'tier_1_forge': StationType.SMITHING,
                    'tier_2_forge': StationType.SMITHING,
                    'tier_3_forge': StationType.SMITHING,
                    'tier_4_forge': StationType.SMITHING,
                    'tier_1_alchemy_table': StationType.ALCHEMY,
                    'tier_2_alchemy_table': StationType.ALCHEMY,
                    'tier_3_alchemy_table': StationType.ALCHEMY,
                    'tier_4_alchemy_table': StationType.ALCHEMY,
                    'tier_1_refinery': StationType.REFINING,
                    'tier_2_refinery': StationType.REFINING,
                    'tier_3_refinery': StationType.REFINING,
                    'tier_4_refinery': StationType.REFINING,
                    'tier_1_engineering_bench': StationType.ENGINEERING,
                    'tier_2_engineering_bench': StationType.ENGINEERING,
                    'tier_3_engineering_bench': StationType.ENGINEERING,
                    'tier_4_engineering_bench': StationType.ENGINEERING,
                    'tier_1_enchanting_table': StationType.ADORNMENTS,
                    'tier_2_enchanting_table': StationType.ADORNMENTS,
                    'tier_3_enchanting_table': StationType.ADORNMENTS,
                    'tier_4_enchanting_table': StationType.ADORNMENTS,
                }
                station_type = station_type_map.get(placed_entity.item_id, StationType.SMITHING)
                from data.models import CraftingStation
                station = CraftingStation(
                    position=placed_entity.position,
                    station_type=station_type,
                    tier=placed_entity.tier
                )

        if station:
            self.character.interact_with_station(station)
            self.active_station_tier = station.tier  # Capture tier for placement UI
            self.user_placement = {}  # Clear any previous placement
            self.selected_recipe = None  # Clear selected recipe
            self.recipe_scroll_offset = 0  # Reset recipe list scroll
            return

        resource = self.world.get_resource_at(world_pos)
        if resource:
            can_harvest, reason = self.character.can_harvest_resource(resource)
            if not can_harvest:
                self.add_notification(f"Cannot harvest: {reason}", (255, 100, 100))
                return

            result = self.character.harvest_resource(resource)
            if result:
                loot, dmg, is_crit = result
                self.damage_numbers.append(DamageNumber(dmg, resource.position.copy(), is_crit))
                if loot:
                    mat_db = MaterialDatabase.get_instance()
                    for item_id, qty in loot:
                        mat = mat_db.get_material(item_id)
                        item_name = mat.name if mat else item_id
                        self.add_notification(f"+{qty} {item_name}", (100, 255, 100))

    def handle_enchantment_selection_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks on the enchantment selection UI"""
        print(f"🔍 Enchantment click handler called at {mouse_pos}")

        if not self.enchantment_item_rects:
            print(f"⚠️ No item rects available!")
            return

        print(f"📋 Checking {len(self.enchantment_item_rects)} item rects")
        wx, wy = self.enchantment_selection_rect.x, self.enchantment_selection_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
        print(f"   Window at ({wx}, {wy}), relative click at ({rx}, {ry})")

        for idx, (item_rect, source_type, source_id, item_stack, equipment) in enumerate(self.enchantment_item_rects):
            print(f"   Rect {idx}: {item_rect}, contains? {item_rect.collidepoint(rx, ry)}")

            if item_rect.collidepoint(rx, ry):
                print(f"✨ Selected {equipment.name} for enchantment")
                self._complete_enchantment_application(source_type, source_id, item_stack, equipment)
                break

    def handle_skills_menu_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks on the skills menu"""
        wx, wy = self.skills_window_rect.x, self.skills_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        # Check hotbar slots (right-click to unequip)
        for slot_rect, slot_idx, skill_id in self.skills_hotbar_rects:
            if slot_rect.collidepoint(rx, ry):
                if skill_id:  # Right-click to unequip
                    self.character.skills.unequip_skill(slot_idx)
                    self.add_notification(f"Unequipped from slot {slot_idx + 1}", (255, 200, 100))
                return

        # Check skill list (click to equip)
        for skill_rect, skill_id, player_skill, skill_def in self.skills_list_rects:
            if skill_rect.collidepoint(rx, ry):
                # Find first empty slot
                empty_slot = None
                for i in range(5):
                    if not self.character.skills.equipped_skills[i]:
                        empty_slot = i
                        break

                if empty_slot is not None:
                    self.character.skills.equip_skill(skill_id, empty_slot)
                    self.add_notification(f"Equipped {skill_def.name} to slot {empty_slot + 1}", (100, 255, 150))
                else:
                    self.add_notification("All hotbar slots full! Unequip a skill first.", (255, 150, 100))
                return

        # Check available skills (click to learn)
        for skill_rect, skill_id, skill_def in self.skills_available_rects:
            if skill_rect.collidepoint(rx, ry):
                if self.character.skills.learn_skill(skill_id, character=self.character, skip_checks=False):
                    self.add_notification(f"Learned {skill_def.name}!", (100, 255, 100))
                    print(f"✅ Learned skill: {skill_def.name}")
                else:
                    self.add_notification("Failed to learn skill!", (255, 100, 100))
                return

    def handle_class_selection_click(self, mouse_pos: Tuple[int, int]):
        if not self.class_buttons:
            return

        wx, wy = self.class_selection_rect.x, self.class_selection_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        for card_rect, class_def in self.class_buttons:
            if card_rect.collidepoint(rx, ry):
                self.character.select_class(class_def)
                self.character.class_selection_open = False
                self.add_notification(f"Welcome, {class_def.name}!", (255, 215, 0))
                print(f"\n🎉 Welcome, {class_def.name}!")
                print(f"   {class_def.description}")
                break

    def handle_equipment_click(self, mouse_pos: Tuple[int, int], shift_held: bool):
        if not self.equipment_rects:
            print(f"   ⚠️ equipment_rects is empty")
            return

        wx, wy = self.equipment_window_rect.x, self.equipment_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
        print(f"   🖱️ Equipment click: mouse_pos={mouse_pos}, relative=({rx}, {ry}), shift={shift_held}")

        for slot_name, (rect, _, _) in self.equipment_rects.items():
            if rect.collidepoint(rx, ry):
                print(f"🎯 Equipment slot clicked: {slot_name}, shift_held: {shift_held}")
                item = self.character.equipment.slots.get(slot_name)
                print(f"   Item in slot: {item.name if item else 'None'}")

                if shift_held:
                    # Unequip
                    print(f"   Attempting to unequip from {slot_name}")
                    success, msg = self.character.try_unequip_to_inventory(slot_name)
                    if success:
                        self.add_notification(f"Unequipped item", (100, 255, 100))
                        print(f"   ✅ Unequipped successfully")
                    else:
                        self.add_notification(f"Cannot unequip: {msg}", (255, 100, 100))
                        print(f"   ❌ Failed: {msg}")
                else:
                    print(f"   Regular click (no shift), no action")
                break
        else:
            print(f"   No slot matched the click position")

    def handle_stats_click(self, mouse_pos: Tuple[int, int]):
        if not self.stats_window_rect or not self.stats_buttons:
            return
        wx, wy = self.stats_window_rect.x, self.stats_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        for btn_rect, stat_name in self.stats_buttons:
            if btn_rect.collidepoint(rx, ry):
                if self.character.allocate_stat_point(stat_name):
                    self.add_notification(f"+1 {stat_name.upper()}", (100, 255, 100))
                    print(f"✓ +1 {stat_name.upper()}")
                break

    def handle_encyclopedia_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks in encyclopedia UI"""
        if not self.encyclopedia_window_rect or not self.encyclopedia_tab_rects:
            return
        wx, wy = self.encyclopedia_window_rect.x, self.encyclopedia_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        # Check tab clicks
        for tab_rect, tab_id in self.encyclopedia_tab_rects:
            if tab_rect.collidepoint(rx, ry):
                self.character.encyclopedia.current_tab = tab_id
                print(f"📚 Switched to {tab_id} tab")
                break

    # ========================================================================
    # CRAFTING INTEGRATION HELPERS
    # ========================================================================
    def inventory_to_dict(self) -> Dict[str, int]:
        """Convert main.py Inventory to crafter-compatible Dict[material_id: quantity]"""
        materials = {}
        for slot in self.character.inventory.slots:
            if slot and not slot.is_equipment():
                # Only include non-equipment items (materials)
                if slot.item_id in materials:
                    materials[slot.item_id] += slot.quantity
                else:
                    materials[slot.item_id] = slot.quantity
        return materials

    def get_crafter_for_station(self, station_type: str):
        """Get the appropriate crafter module for a station type"""
        if not CRAFTING_MODULES_LOADED:
            return None

        crafter_map = {
            'smithing': self.smithing_crafter,
            'refining': self.refining_crafter,
            'alchemy': self.alchemy_crafter,
            'engineering': self.engineering_crafter,
            'adornments': self.enchanting_crafter
        }
        return crafter_map.get(station_type)

    def _start_minigame(self, recipe: Recipe):
        """Start the appropriate minigame for this recipe"""
        crafter = self.get_crafter_for_station(recipe.station_type)
        if not crafter:
            self.add_notification("Invalid crafting station!", (255, 100, 100))
            return

        # Initialize buff bonuses
        buff_time_bonus = 0.0
        buff_quality_bonus = 0.0

        # Enchanting has different minigame signature (requires target_item, no buff bonuses)
        if recipe.station_type == 'adornments':
            # Get target item from stored enchantment selection
            target_item = None
            if self.enchantment_selected_item:
                target_item = self.enchantment_selected_item.get('equipment')

            minigame = crafter.create_minigame(recipe.recipe_id, target_item)
            if not minigame:
                self.add_notification("Minigame not available!", (255, 100, 100))
                return
        else:
            # Other crafting disciplines use buff bonuses
            # Calculate skill buff bonuses for this crafting discipline
            if hasattr(self.character, 'buffs'):
                # Quicken buff: Extends minigame time
                quicken_general = self.character.buffs.get_total_bonus('quicken', recipe.station_type)
                quicken_smithing_alt = self.character.buffs.get_total_bonus('quicken', 'smithing') if recipe.station_type in ['smithing', 'refining'] else 0
                buff_time_bonus = max(quicken_general, quicken_smithing_alt)

                # Empower/Elevate buff: Improves quality
                empower_bonus = self.character.buffs.get_total_bonus('empower', recipe.station_type)
                elevate_bonus = self.character.buffs.get_total_bonus('elevate', recipe.station_type)
                buff_quality_bonus = max(empower_bonus, elevate_bonus)

            # Create minigame instance with buff bonuses
            minigame = crafter.create_minigame(recipe.recipe_id, buff_time_bonus, buff_quality_bonus)
            if not minigame:
                self.add_notification("Minigame not available!", (255, 100, 100))
                return

        if buff_time_bonus > 0 or buff_quality_bonus > 0:
            print(f"⚡ Skill buffs active:")
            if buff_time_bonus > 0:
                print(f"   +{buff_time_bonus*100:.0f}% minigame time")
            if buff_quality_bonus > 0:
                print(f"   +{buff_quality_bonus*100:.0f}% quality bonus")

        # Start minigame
        minigame.start()

        # Store minigame state
        self.active_minigame = minigame
        self.minigame_type = recipe.station_type
        self.minigame_recipe = recipe

        # Close crafting UI
        self.character.close_crafting_ui()

        print(f"🎮 Started {recipe.station_type} minigame for {recipe.recipe_id}")
        self.add_notification(f"Minigame Started!", (255, 215, 0))

    def _complete_minigame(self):
        """Complete the active minigame and process results"""
        if not self.active_minigame or not self.minigame_recipe:
            return

        print(f"\n{'='*80}")
        print(f"🎮 MINIGAME COMPLETED")
        print(f"Recipe: {self.minigame_recipe.recipe_id}")
        print(f"Type: {self.minigame_type}")
        print(f"Result: {self.active_minigame.result}")
        print(f"{'='*80}\n")

        recipe = self.minigame_recipe
        result = self.active_minigame.result
        crafter = self.get_crafter_for_station(self.minigame_type)

        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Convert inventory to dict
        inv_dict = self.inventory_to_dict()

        # DEBUG MODE: Add infinite quantities of required materials (same as in craft_item)
        if Config.DEBUG_INFINITE_RESOURCES:
            print("🔧 DEBUG MODE: Adding infinite materials for minigame completion")
            rarity_system.debug_mode = True
            for inp in recipe.inputs:
                mat_id = inp.get('materialId', '')
                inv_dict[mat_id] = 999999
        else:
            rarity_system.debug_mode = False

        # Use crafter to process minigame result
        craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result)

        if not craft_result.get('success'):
            # Failure - materials may have been lost
            message = craft_result.get('message', 'Crafting failed')
            self.add_notification(message, (255, 100, 100))

            # Sync inventory back (consume materials even on failure)
            recipe_db.consume_materials(recipe, self.character.inventory)

            # Clear enchantment selection if this was an enchantment
            if self.enchantment_selected_item:
                self.enchantment_selected_item = None
        else:
            # Success - consume materials and process output
            recipe_db.consume_materials(recipe, self.character.inventory)

            # Record activity and XP
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(self.minigame_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            # Minigame gives XP (50% bonus over instant craft)
            xp_reward = int(20 * recipe.station_tier * 1.5)
            leveled_up = self.character.leveling.add_exp(xp_reward)
            if leveled_up:
                self.character.check_and_notify_new_skills()

            new_title = self.character.titles.check_for_title(
                activity_type, self.character.activities.get_count(activity_type)
            )
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

            # Handle enchantment application (apply to selected item instead of adding to inventory)
            if self.minigame_type == 'adornments' and self.enchantment_selected_item:
                equipment = self.enchantment_selected_item['equipment']
                enchantment_data = craft_result.get('enchantment', {})

                # Apply enchantment to the equipment
                success, message = equipment.apply_enchantment(
                    recipe.output_id,
                    recipe.enchantment_name,
                    recipe.effect
                )

                if success:
                    self.add_notification(f"Applied {recipe.enchantment_name} to {equipment.name}!", (100, 255, 255))
                else:
                    self.add_notification(f"❌ {message}", (255, 100, 100))

                # Clear the stored item
                self.enchantment_selected_item = None
            else:
                # Normal crafting - add output to inventory with rarity and stats
                output_id = craft_result.get('outputId', recipe.output_id)
                output_qty = craft_result.get('quantity', recipe.output_qty)
                rarity = craft_result.get('rarity', 'common')
                stats = craft_result.get('stats')

                self.add_crafted_item_to_inventory(output_id, output_qty, rarity, stats)

            # Get proper name for notification
            if equip_db.is_equipment(output_id):
                equipment = equip_db.create_equipment_from_id(output_id)
                out_name = equipment.name if equipment else output_id
            else:
                out_mat = mat_db.get_material(output_id)
                out_name = out_mat.name if out_mat else output_id

            message = craft_result.get('message', f"Crafted {out_name} x{output_qty}")
            self.add_notification(message, (100, 255, 100))
            print(f"✅ Minigame crafting complete: {out_name} x{output_qty}")

        # Clear minigame state
        self.active_minigame = None
        self.minigame_type = None
        self.minigame_recipe = None

    def add_crafted_item_to_inventory(self, item_id: str, quantity: int,
                                     rarity: str = 'common', stats: Dict = None):
        """Add a crafted item to inventory with rarity and stats"""
        equip_db = EquipmentDatabase.get_instance()

        if equip_db.is_equipment(item_id):
            # Equipment - create with stats if provided
            for i in range(quantity):
                equipment = equip_db.create_equipment_from_id(item_id)
                if equipment and stats:
                    # Apply crafted stats to equipment
                    for stat_name, stat_value in stats.items():
                        if hasattr(equipment, stat_name):
                            # Special handling for damage - must be tuple
                            if stat_name == 'damage' and isinstance(stat_value, (int, float)):
                                # Convert single damage value to (min, max) tuple
                                # Use 80-100% of damage value for min-max range
                                dmg_min = int(stat_value * 0.8)
                                dmg_max = int(stat_value)
                                setattr(equipment, stat_name, (dmg_min, dmg_max))
                            else:
                                setattr(equipment, stat_name, stat_value)

                # Use add_item which handles equipment properly (doesn't stack)
                success = self.character.inventory.add_item(item_id, 1, equipment_instance=equipment,
                                                            rarity=rarity, crafted_stats=stats)
                if not success:
                    self.add_notification("Inventory full!", (255, 100, 100))
                    break
        else:
            # Material - use add_item which handles stacking properly
            # Pass crafted_stats so materials with different bonuses don't stack together
            success = self.character.inventory.add_item(item_id, quantity, rarity=rarity, crafted_stats=stats)
            if not success:
                self.add_notification("Inventory full!", (255, 100, 100))

    def handle_craft_click(self, mouse_pos: Tuple[int, int]):
        """
        Handle clicks in the new two-panel crafting UI
        - Left panel: Click recipe to select it
        - Right panel: Click Instant or Minigame buttons to craft
        """
        if not self.crafting_window_rect or not self.crafting_recipes:
            return

        # Prevent crafting while minigame is active
        if self.active_minigame:
            return

        rx = mouse_pos[0] - self.crafting_window_rect.x
        ry = mouse_pos[1] - self.crafting_window_rect.y

        recipe_db = RecipeDatabase.get_instance()

        # Layout constants (matching render_crafting_ui) - MUST use Config.scale()!
        s = Config.scale
        left_panel_w = s(450)
        right_panel_x = left_panel_w + s(20) + s(20)  # separator + padding
        right_panel_w = s(500)  # Must match renderer

        # ======================
        # LEFT PANEL: Recipe Selection (WITH GROUPED HEADERS)
        # ======================
        if rx < left_panel_w:
            # Click in left panel - select recipe
            # Need to use the same grouping logic as the renderer
            mat_db = MaterialDatabase.get_instance()
            equip_db = EquipmentDatabase.get_instance()

            # Group recipes by type (same as renderer)
            grouped_recipes = self.renderer._group_recipes_by_type(self.crafting_recipes, equip_db, mat_db)

            # Flatten grouped recipes with headers
            flat_list = []
            for type_name, type_recipes in grouped_recipes:
                flat_list.append(('header', type_name))
                for recipe in type_recipes:
                    flat_list.append(('recipe', recipe))

            # Apply scroll offset (match renderer logic exactly)
            total_items = len(flat_list)
            start_idx = min(self.recipe_scroll_offset, max(0, total_items - 1))
            visible_items = flat_list[start_idx:]  # All items from scroll offset, will stop at vertical limit

            # Get window dimensions (must match renderer)
            wh = Config.MENU_MEDIUM_H
            max_y = wh - s(20)  # Leave 20px margin at bottom

            y_off = s(70)
            for i, item in enumerate(visible_items):
                item_type, item_data = item

                # Calculate height needed for this item
                if item_type == 'header':
                    needed_height = s(28)
                else:
                    recipe = item_data
                    num_inputs = len(recipe.inputs)
                    needed_height = max(s(70), s(35) + num_inputs * s(16) + s(5)) + s(8)

                # Stop if we're out of vertical space (match renderer)
                if y_off + needed_height > max_y:
                    break

                if item_type == 'header':
                    # Header - just skip over it (height = 28)
                    y_off += s(28)
                elif item_type == 'recipe':
                    recipe = item_data
                    num_inputs = len(recipe.inputs)
                    btn_height = max(s(70), s(35) + num_inputs * s(16) + s(5))

                    if y_off <= ry <= y_off + btn_height:
                        # Recipe clicked - select it
                        self.selected_recipe = recipe
                        print(f"📋 Selected recipe: {recipe.recipe_id}")
                        # Auto-load recipe placement
                        self.load_recipe_placement(recipe)
                        return

                    y_off += btn_height + s(8)

        # ======================
        # RIGHT PANEL: Grid Cells & Craft Buttons
        # ======================
        elif rx >= right_panel_x:
            if not self.selected_recipe:
                return  # No recipe selected, nothing to interact with

            # First check for placement slot clicks (grid cells or hub slots)
            for cell_rect, slot_data in self.placement_grid_rects:
                if cell_rect.collidepoint(mouse_pos):
                    # Slot clicked!
                    # slot_data can be either (grid_x, grid_y) tuple for grids or "slot_id" string for others
                    if isinstance(slot_data, tuple):
                        # Grid-based (smithing, adornments)
                        grid_x, grid_y = slot_data
                        slot_key = f"{grid_x},{grid_y}"
                        slot_display = f"({grid_x}, {grid_y})"
                    else:
                        # Slot-based (refining, alchemy, engineering)
                        slot_key = slot_data
                        slot_display = slot_key

                    if slot_key in self.user_placement:
                        # Slot already has material - remove it
                        removed_mat = self.user_placement.pop(slot_key)
                        print(f"🗑️ Removed {removed_mat} from {slot_display}")
                    else:
                        # Slot is empty - place first material from recipe inputs
                        # This is a simple approach; later we can add material picker UI
                        if self.selected_recipe.inputs:
                            first_mat_id = self.selected_recipe.inputs[0].get('materialId', '')
                            if first_mat_id:
                                self.user_placement[slot_key] = first_mat_id
                                print(f"✅ Placed {first_mat_id} in {slot_display}")
                    return  # Slot click handled

            # Then check for craft buttons
            recipe = self.selected_recipe
            can_craft = recipe_db.can_craft(recipe, self.character.inventory)

            if not can_craft:
                return  # Can't craft, buttons not shown

            # Button positions (matching render_crafting_ui) - MUST use Config.scale()!
            placement_h = s(380)
            right_panel_y = s(70)
            btn_y = right_panel_y + placement_h + s(20)

            instant_btn_w, instant_btn_h = s(120), s(40)
            minigame_btn_w, minigame_btn_h = s(120), s(40)

            total_btn_w = instant_btn_w + minigame_btn_w + s(20)
            start_x = right_panel_x + (right_panel_w - s(40) - total_btn_w) // 2

            instant_btn_x = start_x
            minigame_btn_x = start_x + instant_btn_w + s(20)

            # Convert to relative coordinates
            instant_left = instant_btn_x
            instant_right = instant_btn_x + instant_btn_w
            minigame_left = minigame_btn_x
            minigame_right = minigame_btn_x + minigame_btn_w
            btn_top = btn_y
            btn_bottom = btn_y + instant_btn_h

            if instant_left <= rx <= instant_right and btn_top <= ry <= btn_bottom:
                # Instant craft clicked
                print(f"🔨 Instant craft clicked for {recipe.recipe_id}")
                self.craft_item(recipe, use_minigame=False)
            elif minigame_left <= rx <= minigame_right and btn_top <= ry <= btn_bottom:
                # Minigame clicked
                print(f"🎮 Minigame clicked for {recipe.recipe_id}")
                self.craft_item(recipe, use_minigame=True)

    def load_recipe_placement(self, recipe: Recipe):
        """
        Auto-load recipe placement into user_placement when recipe is selected.
        This pre-fills the placement so user can craft immediately or modify as needed.
        """
        placement_db = PlacementDatabase.get_instance()
        placement_data = placement_db.get_placement(recipe.recipe_id)

        if not placement_data:
            # No placement data - clear user placement
            self.user_placement = {}
            return

        # Clear existing placement
        self.user_placement = {}

        # Load based on discipline
        if placement_data.discipline == 'smithing' or placement_data.discipline == 'adornments':
            # Grid-based: copy placement_map with offset for centering
            recipe_grid_w, recipe_grid_h = 3, 3  # Default
            if placement_data.grid_size:
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass

            # Calculate offset to center recipe on station grid
            station_tier = self.active_station_tier
            station_grid_w, station_grid_h = self._get_grid_size_for_tier(station_tier, placement_data.discipline)
            offset_x = (station_grid_w - recipe_grid_w) // 2
            offset_y = (station_grid_h - recipe_grid_h) // 2

            # Copy placements with offset
            for pos, mat_id in placement_data.placement_map.items():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        self.user_placement[f"{station_x},{station_y}"] = mat_id
                    except ValueError:
                        pass

        elif placement_data.discipline == 'refining':
            # Hub-and-spoke: copy core and surrounding inputs
            for i, core_input in enumerate(placement_data.core_inputs):
                mat_id = core_input.get('materialId', '')
                if mat_id:
                    self.user_placement[f"core_{i}"] = mat_id

            for i, surrounding_input in enumerate(placement_data.surrounding_inputs):
                mat_id = surrounding_input.get('materialId', '')
                if mat_id:
                    self.user_placement[f"surrounding_{i}"] = mat_id

        elif placement_data.discipline == 'alchemy':
            # Sequential: copy ingredients
            for ingredient in placement_data.ingredients:
                slot_num = ingredient.get('slot')
                mat_id = ingredient.get('materialId', '')
                if slot_num and mat_id:
                    self.user_placement[f"seq_{slot_num}"] = mat_id

        elif placement_data.discipline == 'engineering':
            # Slot-type: copy slots
            for i, slot in enumerate(placement_data.slots):
                mat_id = slot.get('materialId', '')
                if mat_id:
                    self.user_placement[f"eng_slot_{i}"] = mat_id

        print(f"✅ Loaded {len(self.user_placement)} placements for {recipe.recipe_id}")

    def _get_grid_size_for_tier(self, tier: int, discipline: str) -> Tuple[int, int]:
        """Get grid dimensions based on station tier (matches Renderer method)"""
        if discipline not in ['smithing', 'adornments']:
            return (3, 3)
        tier_to_grid = {1: (3, 3), 2: (5, 5), 3: (7, 7), 4: (9, 9)}
        return tier_to_grid.get(tier, (3, 3))

    def validate_placement(self, recipe: Recipe, user_placement: Dict[str, str]) -> Tuple[bool, str]:
        """
        Validate user's material placement against recipe requirements

        Args:
            recipe: Recipe being crafted
            user_placement: User's current placement (Dict[str, str] mapping "x,y" -> materialId)

        Returns:
            (is_valid, error_message): Tuple of validation result and error message
        """
        placement_db = PlacementDatabase.get_instance()

        # Get required placement data
        placement_data = placement_db.get_placement(recipe.recipe_id)
        if not placement_data:
            # No placement data - placement not required
            return (True, "")

        discipline = placement_data.discipline

        if discipline == 'smithing' or discipline == 'adornments':
            # Grid-based validation with centering offset
            required_map = placement_data.placement_map

            # Get recipe and station grid sizes
            recipe_grid_w, recipe_grid_h = 3, 3
            if placement_data.grid_size:
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass

            station_grid_w, station_grid_h = self._get_grid_size_for_tier(self.active_station_tier, discipline)
            offset_x = (station_grid_w - recipe_grid_w) // 2
            offset_y = (station_grid_h - recipe_grid_h) // 2

            # Check if all required positions are filled (with offset)
            for pos, required_mat in required_map.items():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        station_pos = f"{station_x},{station_y}"

                        if station_pos not in user_placement:
                            return (False, f"Missing material at {pos} ({required_mat})")

                        user_mat = user_placement[station_pos]
                        if user_mat != required_mat:
                            return (False, f"Wrong material at {pos}: expected {required_mat}, got {user_mat}")
                    except ValueError:
                        pass

            # Check for extra materials (allow placements within recipe bounds only)
            expected_positions = set()
            for pos in required_map.keys():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        expected_positions.add(f"{station_x},{station_y}")
                    except ValueError:
                        pass

            for pos in user_placement.keys():
                if pos not in expected_positions:
                    return (False, f"Extra material at {pos} (not part of recipe)")

            return (True, "Placement correct!")

        elif discipline == 'refining':
            # Hub-and-spoke validation
            required_core = placement_data.core_inputs
            required_surrounding = placement_data.surrounding_inputs

            # Check core slots
            for i, core_input in enumerate(required_core):
                slot_id = f"core_{i}"
                required_mat = core_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing core material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong core material: expected {required_mat}, got {user_mat}")

            # Check surrounding slots
            for i, surrounding_input in enumerate(required_surrounding):
                slot_id = f"surrounding_{i}"
                required_mat = surrounding_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing surrounding material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong surrounding material: expected {required_mat}, got {user_mat}")

            # Check for extra materials in wrong slots
            expected_slots = set(f"core_{i}" for i in range(len(required_core)))
            expected_slots.update(f"surrounding_{i}" for i in range(len(required_surrounding)))

            for slot_id in user_placement.keys():
                if slot_id.startswith('core_') or slot_id.startswith('surrounding_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra material in {slot_id} (not required)")

            return (True, "Refining placement correct!")

        elif discipline == 'alchemy':
            # Sequential validation
            required_ingredients = placement_data.ingredients

            # Check each sequential slot
            for ingredient in required_ingredients:
                slot_num = ingredient.get('slot')
                slot_id = f"seq_{slot_num}"
                required_mat = ingredient.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing ingredient in slot {slot_num}: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong ingredient in slot {slot_num}: expected {required_mat}, got {user_mat}")

            # Check for extra materials in wrong slots
            expected_slots = set(f"seq_{ing.get('slot')}" for ing in required_ingredients)

            for slot_id in user_placement.keys():
                if slot_id.startswith('seq_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra ingredient in {slot_id} (not required)")

            return (True, "Alchemy sequence correct!")

        elif discipline == 'engineering':
            # Slot-type validation
            required_slots = placement_data.slots

            # Check each slot
            for i, slot_data in enumerate(required_slots):
                slot_id = f"eng_slot_{i}"
                required_mat = slot_data.get('materialId', '')

                if slot_id not in user_placement:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Missing material in {slot_type} slot: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Wrong material in {slot_type} slot: expected {required_mat}, got {user_mat}")

            # Check for extra materials
            expected_slots = set(f"eng_slot_{i}" for i in range(len(required_slots)))

            for slot_id in user_placement.keys():
                if slot_id.startswith('eng_slot_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra material in {slot_id} (not required)")

            return (True, "Engineering placement correct!")

        else:
            # Unknown discipline
            return (True, "")

    def craft_item(self, recipe: Recipe, use_minigame: bool = False):
        """
        Craft an item either instantly or via minigame

        Args:
            recipe: Recipe to craft
            use_minigame: If True, start minigame. If False, instant craft.
        """
        # Prevent crafting while minigame is already active (prevents double crafting)
        if self.active_minigame:
            self.add_notification("Minigame already in progress!", (255, 100, 100))
            print("❌ Cannot craft - minigame already active")
            return

        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        print("\n" + "="*80)
        print(f"🔨 CRAFT_ITEM - Using New Crafting System")
        print(f"Recipe ID: {recipe.recipe_id}")
        print(f"Output ID: {recipe.output_id}")
        print(f"Station Type: {recipe.station_type}")
        print(f"Use Minigame: {use_minigame}")
        print("="*80)

        # Check if we have materials
        if not recipe_db.can_craft(recipe, self.character.inventory):
            self.add_notification("Not enough materials!", (255, 100, 100))
            print("❌ Cannot craft - not enough materials")
            return

        # Validate placement (if required)
        is_valid, error_msg = self.validate_placement(recipe, self.user_placement)
        if not is_valid:
            self.add_notification(f"Invalid placement: {error_msg}", (255, 100, 100))
            print(f"❌ Cannot craft - invalid placement: {error_msg}")
            return
        elif error_msg:  # Valid with message
            print(f"✓ Placement validated: {error_msg}")

        # Handle enchanting recipes differently (apply to existing items)
        if recipe.is_enchantment:
            print(f"⚠ Enchantment recipe - opening item selection UI (use_minigame={use_minigame})")
            # Store whether to use minigame for this enchantment
            self.enchantment_use_minigame = use_minigame
            self._open_enchantment_selection(recipe)
            return

        # Choose crafting method
        if use_minigame:
            print("🎮 Starting minigame...")
            self._start_minigame(recipe)
            return
        else:
            print("⚡ Using instant craft...")
            self._instant_craft(recipe)
            return

    def _instant_craft(self, recipe: Recipe):
        """Perform instant crafting (no minigame, 0 EXP)"""
        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Get the appropriate crafter for this discipline
        crafter = self.get_crafter_for_station(recipe.station_type)

        if crafter and CRAFTING_MODULES_LOADED:
            # NEW SYSTEM: Use crafting subdisciplines
            print(f"✓ Using {recipe.station_type} crafter from subdisciplines")

            # Convert inventory to dict format
            inv_dict = self.inventory_to_dict()

            # DEBUG MODE: Add infinite quantities of required materials
            if Config.DEBUG_INFINITE_RESOURCES:
                print("🔧 DEBUG MODE: Adding infinite materials and bypassing rarity checks")
                # Enable debug mode in rarity system to bypass rarity uniformity checks
                rarity_system.debug_mode = True
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId', '')
                    # Add huge quantity - rarity is checked from material database, not inventory
                    inv_dict[mat_id] = 999999
            else:
                # Ensure debug mode is off
                rarity_system.debug_mode = False

            # Check if crafter can craft (with rarity checks)
            can_craft_result = crafter.can_craft(recipe.recipe_id, inv_dict)
            if isinstance(can_craft_result, tuple):
                can_craft, error_msg = can_craft_result
            else:
                can_craft, error_msg = can_craft_result, None

            if not can_craft:
                self.add_notification(f"Cannot craft: {error_msg or 'Unknown error'}", (255, 100, 100))
                print(f"❌ Crafter blocked: {error_msg}")
                return

            # Use instant craft (minigames come later)
            print(f"📦 Calling crafter.craft_instant()...")
            result = crafter.craft_instant(recipe.recipe_id, inv_dict)

            if result.get('success'):
                output_id = result.get('outputId')
                quantity = result.get('quantity', 1)
                rarity = result.get('rarity', 'common')
                stats = result.get('stats')

                print(f"✓ Craft successful: {quantity}x {output_id} ({rarity})")
                if stats:
                    print(f"   Stats: {stats}")

                # Add to inventory with rarity and stats
                self.add_crafted_item_to_inventory(output_id, quantity, rarity, stats)

                # Record activity and award XP (instant craft = 0 XP per Game Mechanics v5)
                activity_map = {
                    'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                    'engineering': 'engineering', 'adornments': 'enchanting'
                }
                activity_type = activity_map.get(recipe.station_type, 'smithing')
                self.character.activities.record_activity(activity_type, 1)

                # Instant craft gives 0 EXP (only minigames give EXP)
                print("  (Instant craft = 0 EXP, use minigame for EXP)")

                # Check for titles
                new_title = self.character.titles.check_for_title(
                    activity_type, self.character.activities.get_count(activity_type)
                )
                if new_title:
                    self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

                # Get item name for notification
                if equip_db.is_equipment(output_id):
                    equipment = equip_db.create_equipment_from_id(output_id)
                    item_name = equipment.name if equipment else output_id
                else:
                    material = mat_db.get_material(output_id)
                    item_name = material.name if material else output_id

                rarity_str = f" ({rarity})" if rarity != 'common' else ""
                self.add_notification(f"Crafted {item_name}{rarity_str} x{quantity}", (100, 255, 100))
                print("="*80 + "\n")
            else:
                error_msg = result.get('message', 'Crafting failed')
                self.add_notification(f"Failed: {error_msg}", (255, 100, 100))
                print(f"❌ {error_msg}")
                print("="*80 + "\n")

        else:
            # FALLBACK: Legacy instant craft system
            print("⚠ Crafting modules not loaded, using legacy system")
            if recipe.is_enchantment:
                self._apply_enchantment(recipe)
                return

            # Old instant craft logic
            if recipe_db.consume_materials(recipe, self.character.inventory):
                self.character.inventory.add_item(recipe.output_id, recipe.output_qty)
                self.add_notification(f"Crafted (legacy) {recipe.output_id} x{recipe.output_qty}", (100, 255, 100))

    def _apply_enchantment(self, recipe: Recipe):
        """Apply an enchantment to an item - shows selection UI"""
        # Find compatible items in inventory
        compatible_items = []
        for i, slot in enumerate(self.character.inventory.slots):
            if slot and slot.is_equipment() and slot.equipment_data:
                equipment = slot.equipment_data
                can_apply, reason = equipment.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append(('inventory', i, slot, equipment))

        # Also check equipped items
        for slot_name, equipped_item in self.character.equipment.slots.items():
            if equipped_item:
                can_apply, reason = equipped_item.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append(('equipped', slot_name, None, equipped_item))

        if not compatible_items:
            self.add_notification("No compatible items found!", (255, 100, 100))
            return

        # Open selection UI
        self.enchantment_selection_active = True
        self.enchantment_recipe = recipe
        self.enchantment_compatible_items = compatible_items
        print(f"🔮 Opening enchantment selection UI with {len(compatible_items)} compatible items")

    def _complete_enchantment_application(self, source_type: str, source_id, item_stack, equipment):
        """Complete the enchantment application after user selects an item"""
        recipe = self.enchantment_recipe
        recipe_db = RecipeDatabase.get_instance()

        # Check if enchantment can be applied BEFORE consuming materials
        can_apply, reason = equipment.can_apply_enchantment(recipe.output_id, recipe.applicable_to, recipe.effect)
        if not can_apply:
            self.add_notification(f"❌ Cannot apply: {reason}", (255, 100, 100))
            print(f"   ❌ Cannot apply enchantment: {reason}")
            self._close_enchantment_selection()
            return

        # If using minigame, store item details and start pattern-matching minigame instead
        if self.enchantment_use_minigame:
            print("🎮 Starting pattern-matching minigame for enchantment...")
            # Store the selected item details for after minigame completion
            self.enchantment_selected_item = {
                'source_type': source_type,
                'source_id': source_id,
                'item_stack': item_stack,
                'equipment': equipment
            }
            # Close enchantment selection UI
            self._close_enchantment_selection()
            # Start the pattern-matching minigame
            self._start_minigame(recipe)
            return

        # Pre-check for tier protection and duplicates (without modifying the item)
        # Create a copy to test on
        import copy as copy_module
        test_enchantments = copy_module.deepcopy(equipment.enchantments)
        test_success, test_message = equipment.apply_enchantment(recipe.output_id, recipe.enchantment_name, recipe.effect)

        # Revert the test application
        equipment.enchantments = test_enchantments

        if not test_success:
            self.add_notification(f"❌ {test_message}", (255, 100, 100))
            print(f"   ❌ Enchantment blocked: {test_message}")
            self._close_enchantment_selection()
            return

        # Now consume materials (after all checks pass)
        if not recipe_db.consume_materials(recipe, self.character.inventory):
            self.add_notification("Failed to consume materials!", (255, 100, 100))
            self._close_enchantment_selection()
            return

        # Apply enchantment to the equipment instance (for real this time)
        success, message = equipment.apply_enchantment(recipe.output_id, recipe.enchantment_name, recipe.effect)

        if not success:
            # This shouldn't happen since we already checked, but handle it anyway
            self.add_notification(f"❌ {message}", (255, 100, 100))
            print(f"   ❌ Unexpected enchantment failure: {message}")
            self.enchantment_selection_items = []
            return

        # Record activity
        self.character.activities.record_activity('enchanting', 1)
        xp_reward = 20 * recipe.station_tier
        leveled_up = self.character.leveling.add_exp(xp_reward)
        if leveled_up:
            self.character.check_and_notify_new_skills()

        new_title = self.character.titles.check_for_title(
            'enchanting', self.character.activities.get_count('enchanting')
        )
        if new_title:
            self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

        self.add_notification(f"Applied {recipe.enchantment_name} to {equipment.name}!", (100, 255, 255))
        self._close_enchantment_selection()

    def _open_enchantment_selection(self, recipe: Recipe):
        """Open the item selection UI for applying enchantment"""
        equip_db = EquipmentDatabase.get_instance()

        # Get all equipment from inventory and equipped slots
        compatible_items = []

        # From inventory
        for slot_idx, stack in enumerate(self.character.inventory.slots):
            if stack and equip_db.is_equipment(stack.item_id):
                equipment = stack.get_equipment()  # Use actual equipment instance from stack
                if equipment:
                    compatible_items.append(('inventory', slot_idx, stack, equipment))

        # From equipped slots
        for slot_name, equipped_item in self.character.equipment.slots.items():
            if equipped_item:
                compatible_items.append(('equipped', slot_name, None, equipped_item))

        if not compatible_items:
            self.add_notification("No equipment to enchant!", (255, 100, 100))
            print("❌ No compatible items found for enchantment")
            return

        # Open the selection UI
        self.enchantment_selection_active = True
        self.enchantment_recipe = recipe
        self.enchantment_compatible_items = compatible_items
        print(f"✨ Opened enchantment selection UI ({len(compatible_items)} compatible items)")

    def _close_enchantment_selection(self):
        """Close the enchantment selection UI"""
        self.enchantment_selection_active = False
        self.enchantment_recipe = None
        self.enchantment_compatible_items = []
        self.enchantment_selection_rect = None

    def handle_mouse_release(self, mouse_pos: Tuple[int, int]):
        # Skip if no character exists yet (e.g., still in start menu)
        if self.character is None:
            return

        if self.character.inventory.dragging_stack:
            if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
                start_x, start_y = 20, Config.INVENTORY_PANEL_Y
                slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
                rel_x, rel_y = mouse_pos[0] - start_x, mouse_pos[1] - start_y

                if rel_x >= 0 and rel_y >= 0:
                    col, row = rel_x // (slot_size + spacing), rel_y // (slot_size + spacing)
                    in_x = rel_x % (slot_size + spacing) < slot_size
                    in_y = rel_y % (slot_size + spacing) < slot_size

                    if in_x and in_y:
                        idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                        if 0 <= idx < self.character.inventory.max_slots:
                            self.character.inventory.end_drag(idx)
                            return
            self.character.inventory.cancel_drag()

    def update(self):
        # Skip updates if in start menu or no character
        if self.start_menu_open or self.character is None:
            return

        curr = pygame.time.get_ticks()
        dt = (curr - self.last_tick) / 1000.0
        self.last_tick = curr

        if not self.character.class_selection_open:
            dx = dy = 0
            if pygame.K_w in self.keys_pressed:
                dy -= self.character.movement_speed
            if pygame.K_s in self.keys_pressed:
                dy += self.character.movement_speed
            if pygame.K_a in self.keys_pressed:
                dx -= self.character.movement_speed
            if pygame.K_d in self.keys_pressed:
                dx += self.character.movement_speed

            if dx != 0 and dy != 0:
                dx *= 0.7071
                dy *= 0.7071

            if dx != 0 or dy != 0:
                self.character.move(dx, dy, self.world)

        self.camera.follow(self.character.position)

        # Only update world/combat if minigame isn't active
        if not self.active_minigame:
            self.world.update(dt)

            # Check if player is blocking with shield (right mouse held OR X key held)
            shield_blocking = (3 in self.mouse_buttons_pressed or pygame.K_x in self.keys_pressed) and self.character.is_shield_active()

            # Handle X key for offhand attacks (when not blocking)
            if pygame.K_x in self.keys_pressed and not shield_blocking:
                # Get offhand weapon
                offhand_weapon = self.character.equipment.slots.get('offHand')
                if offhand_weapon and offhand_weapon.item_type != "shield":
                    # Try to attack enemy at mouse position
                    mouse_pos = pygame.mouse.get_pos()
                    if mouse_pos[0] < Config.VIEWPORT_WIDTH:  # In viewport
                        # Convert to world coordinates
                        wx = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
                        wy = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y

                        # Check for enemy at position
                        enemy = self.combat_manager.get_enemy_at_position((wx, wy))
                        if enemy and enemy.is_alive:
                            # Check if offhand can attack
                            if self.character.can_attack('offHand'):
                                # Check if in range
                                weapon_range = self.character.equipment.get_weapon_range('offHand')
                                dist = enemy.distance_to((self.character.position.x, self.character.position.y))
                                if dist <= weapon_range:
                                    # Attack with offhand (using tag system)
                                    effect_tags, effect_params = self._get_weapon_effect_data('offHand')
                                    damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(
                                        enemy, effect_tags, effect_params
                                    )
                                    self.damage_numbers.append(DamageNumber(int(damage), Position(enemy.position[0], enemy.position[1], 0), is_crit))
                                    self.character.reset_attack_cooldown(is_weapon=True, hand='offHand')

                                    if not enemy.is_alive:
                                        self.add_notification(f"Defeated {enemy.definition.name}!", (255, 215, 0))
                                        self.character.activities.record_activity('combat', 1)

                                        # Show loot notifications
                                        if loot:
                                            mat_db = MaterialDatabase.get_instance()
                                            for material_id, qty in loot:
                                                mat = mat_db.get_material(material_id)
                                                item_name = mat.name if mat else material_id
                                                self.add_notification(f"+{qty} {item_name}", (100, 255, 100))

            self.combat_manager.update(dt, shield_blocking=shield_blocking)
            self.character.update_attack_cooldown(dt)
            self.character.update_health_regen(dt)
            self.character.update_buffs(dt)

            # Update turret system
            self.turret_system.update(self.world.placed_entities, self.combat_manager, dt)
        else:
            # Update active minigame (skip for engineering - it's turn-based)
            if self.minigame_type != 'engineering':
                self.active_minigame.update(dt)

            # Check if minigame completed
            if hasattr(self.active_minigame, 'result') and self.active_minigame.result is not None:
                self._complete_minigame()

        self.damage_numbers = [d for d in self.damage_numbers if d.update(dt)]
        self.notifications = [n for n in self.notifications if n.update(dt)]

    def render(self):
        self.screen.fill(Config.COLOR_BACKGROUND)

        # Show start menu if open
        if self.start_menu_open:
            result = self.renderer.render_start_menu(self.start_menu_selected_option, self.mouse_pos)
            if result:
                self.start_menu_buttons = result
            # Render notifications even when menu is open
            self.renderer.render_notifications(self.notifications)
            pygame.display.flip()
            return

        # Skip rendering if no character
        if self.character is None:
            pygame.display.flip()
            return

        # Pass NPCs to renderer via temporary attribute
        self.renderer._temp_npcs = self.npcs
        self.renderer.render_world(self.world, self.camera, self.character, self.damage_numbers, self.combat_manager)
        self.renderer.render_ui(self.character, self.mouse_pos)
        self.renderer.render_inventory_panel(self.character, self.mouse_pos)

        # Render skill hotbar at bottom center (over viewport)
        self.renderer.render_skill_hotbar(self.character)

        self.renderer.render_notifications(self.notifications)

        if self.character.class_selection_open:
            result = self.renderer.render_class_selection_ui(self.character, self.mouse_pos)
            if result:
                self.class_selection_rect, self.class_buttons = result
        else:
            self.class_selection_rect = None
            self.class_buttons = []

            if self.character.crafting_ui_open:
                # Pass scroll offset via temporary attribute (renderer doesn't have direct access to game state)
                self.renderer._temp_scroll_offset = self.recipe_scroll_offset
                result = self.renderer.render_crafting_ui(self.character, self.mouse_pos, self.selected_recipe, self.user_placement, self.active_minigame is not None)
                if result:
                    self.crafting_window_rect, self.crafting_recipes, self.placement_grid_rects = result
            else:
                self.crafting_window_rect = None
                self.crafting_recipes = []

            if self.character.stats_ui_open:
                result = self.renderer.render_stats_ui(self.character, self.mouse_pos)
                if result:
                    self.stats_window_rect, self.stats_buttons = result
            else:
                self.stats_window_rect = None
                self.stats_buttons = []

            if self.character.skills_ui_open:
                result = self.renderer.render_skills_menu_ui(self.character, self.mouse_pos)
                if result:
                    self.skills_window_rect, self.skills_hotbar_rects, self.skills_list_rects, self.skills_available_rects = result
            else:
                self.skills_window_rect = None
                self.skills_hotbar_rects = []
                self.skills_list_rects = []
                self.skills_available_rects = []

            if self.character.equipment_ui_open:
                result = self.renderer.render_equipment_ui(self.character, self.mouse_pos)
                if result:
                    self.equipment_window_rect, self.equipment_rects = result
            else:
                self.equipment_window_rect = None
                self.equipment_rects = {}

            if self.character.encyclopedia.is_open:
                result = self.renderer.render_encyclopedia_ui(self.character, self.mouse_pos)
                if result:
                    self.encyclopedia_window_rect, self.encyclopedia_tab_rects = result
            else:
                self.encyclopedia_window_rect = None
                self.encyclopedia_tab_rects = []

            # NPC dialogue UI
            if self.npc_dialogue_open and self.active_npc:
                result = self.renderer.render_npc_dialogue_ui(
                    self.active_npc, self.npc_dialogue_lines, self.npc_available_quests,
                    self.npc_quest_to_turn_in, self.mouse_pos)
                if result:
                    self.npc_dialogue_window_rect, self.npc_dialogue_buttons = result
            else:
                self.npc_dialogue_window_rect = None
                self.npc_dialogue_buttons = []

            # Enchantment selection UI (rendered on top of everything)
            if self.enchantment_selection_active:
                result = self.renderer.render_enchantment_selection_ui(
                    self.mouse_pos, self.enchantment_recipe, self.enchantment_compatible_items)
                if result:
                    self.enchantment_selection_rect, self.enchantment_item_rects = result
            else:
                self.enchantment_selection_rect = None
                self.enchantment_item_rects = None

        # Minigame rendering (rendered on top of EVERYTHING)
        if self.active_minigame:
            self._render_minigame()

        pygame.display.flip()

    def _render_minigame(self):
        """Render the active minigame"""
        if not self.active_minigame or not self.minigame_type:
            return

        # Route to appropriate renderer based on minigame type
        if self.minigame_type == 'smithing':
            self._render_smithing_minigame()
        elif self.minigame_type == 'alchemy':
            self._render_alchemy_minigame()
        elif self.minigame_type == 'refining':
            self._render_refining_minigame()
        elif self.minigame_type == 'engineering':
            self._render_engineering_minigame()
        elif self.minigame_type == 'adornments':
            self._render_enchanting_minigame()

    def _complete_minigame(self):
        """Complete the active minigame and process results"""
        if not self.active_minigame or not self.minigame_recipe:
            return

        print(f"\n{'='*80}")
        print(f"🎮 MINIGAME COMPLETED")
        print(f"Recipe: {self.minigame_recipe.recipe_id}")
        print(f"Type: {self.minigame_type}")
        print(f"Result: {self.active_minigame.result}")
        print(f"{'='*80}\n")

        recipe = self.minigame_recipe
        result = self.active_minigame.result
        crafter = self.get_crafter_for_station(self.minigame_type)

        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Convert inventory to dict
        inv_dict = {}
        for slot in self.character.inventory.slots:
            if slot:
                inv_dict[slot.item_id] = inv_dict.get(slot.item_id, 0) + slot.quantity

        # Add recipe inputs to inv_dict with 0 if missing (defensive programming)
        for inp in recipe.inputs:
            mat_id = inp.get('materialId') or inp.get('itemId')
            if mat_id and mat_id not in inv_dict:
                inv_dict[mat_id] = 0
                print(f"⚠ Warning: Recipe material '{mat_id}' not in inventory!")

        # Use crafter to process minigame result
        # For adornments, pass target_item if available
        if self.minigame_type == 'adornments' and hasattr(self, 'enchantment_selected_item') and self.enchantment_selected_item:
            target_item = self.enchantment_selected_item.get('equipment')
            craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result, target_item=target_item)
        else:
            craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result)

        if not craft_result.get('success'):
            # Failure - materials may have been lost
            message = craft_result.get('message', 'Crafting failed')
            self.add_notification(message, (255, 100, 100))

            # Sync inventory back
            recipe_db.consume_materials(recipe, self.character.inventory)
        else:
            # Success - consume materials and add output
            recipe_db.consume_materials(recipe, self.character.inventory)

            # Record activity and XP
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(self.minigame_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            # Extra XP for minigame (50% bonus)
            xp_reward = int(20 * recipe.station_tier * 1.5)
            leveled_up = self.character.leveling.add_exp(xp_reward)
            if leveled_up:
                self.character.check_and_notify_new_skills()

            new_title = self.character.titles.check_for_title(
                activity_type, self.character.activities.get_count(activity_type)
            )
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

            # Check if this was an enchantment applied to an item (not a new item created)
            if 'enchanted_item' in craft_result:
                # Enchantment was applied to existing item - no need to add to inventory
                message = craft_result.get('message', 'Applied enchantment')
                self.add_notification(message, (100, 255, 255))
                print(f"✅ Enchantment applied: {message}")

                # Clear enchantment selection
                if hasattr(self, 'enchantment_selected_item'):
                    self.enchantment_selected_item = None
            else:
                # Normal crafting - add output to inventory with minigame bonuses
                output_id = craft_result.get('outputId', recipe.output_id)
                output_qty = craft_result.get('quantity', recipe.output_qty)
                rarity = craft_result.get('rarity', 'common')
                stats = craft_result.get('stats', {})
                bonus_pct = craft_result.get('bonus', 0)

                # Use add_crafted_item_to_inventory to apply enhanced stats
                self.add_crafted_item_to_inventory(output_id, output_qty, rarity, stats)

                # Get proper name for notification
                if equip_db.is_equipment(output_id):
                    equipment = equip_db.create_equipment_from_id(output_id)
                    out_name = equipment.name if equipment else output_id
                else:
                    out_mat = mat_db.get_material(output_id)
                    out_name = out_mat.name if out_mat else output_id

                # Enhanced message showing rarity and bonus
                if bonus_pct > 0:
                    message = f"Crafted {rarity.capitalize()} {out_name} x{output_qty} (+{bonus_pct}% bonus)!"
                else:
                    message = f"Crafted {rarity.capitalize()} {out_name} x{output_qty}"

                self.add_notification(message, (100, 255, 100))
                print(f"✅ Minigame crafting complete: {rarity} {out_name} x{output_qty} with stats: {stats}")

        # Clear minigame state
        self.active_minigame = None
        self.minigame_type = None
        self.minigame_recipe = None

    def _render_smithing_minigame(self):
        """Render smithing minigame UI with enhanced visuals"""
        state = self.active_minigame.get_state()

        # Create overlay
        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header with glow effect
        _temp_surf = self.renderer.font.render("SMITHING MINIGAME", True, (255, 215, 0))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[SPACE] Fan Flames | [CLICK HAMMER BUTTON] Strike", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Temperature bar with enhanced visuals
        temp_x, temp_y = 50, 100
        temp_width = 300
        temp_height = 40

        # Draw temp bar background with gradient
        pygame.draw.rect(surf, (40, 40, 40), (temp_x, temp_y, temp_width, temp_height))

        # Draw ideal range with pulse effect
        ideal_min = state['temp_ideal_min']
        ideal_max = state['temp_ideal_max']
        ideal_start = int((ideal_min / 100) * temp_width)
        ideal_width_px = int(((ideal_max - ideal_min) / 100) * temp_width)
        pulse = abs(math.sin(pygame.time.get_ticks() / 500.0)) * 20
        ideal_color = (60 + int(pulse), 80 + int(pulse), 60)
        pygame.draw.rect(surf, ideal_color, (temp_x + ideal_start, temp_y, ideal_width_px, temp_height))

        # Draw current temperature with gradient
        temp_pct = state['temperature'] / 100
        temp_fill = int(temp_pct * temp_width)

        # Enhanced color gradient based on temperature
        if temp_pct > 0.8:
            temp_color = (255, 100 + int((1 - temp_pct) * 500), 100)  # Hot red-white
        elif temp_pct > 0.5:
            temp_color = (255, 165, int((temp_pct - 0.5) * 400))  # Orange
        else:
            temp_color = (100, 150, 200 + int((0.5 - temp_pct) * 110))  # Cool blue

        pygame.draw.rect(surf, temp_color, (temp_x, temp_y, temp_fill, temp_height))

        # Add glow effect if in ideal range
        in_ideal = ideal_min <= state['temperature'] <= ideal_max
        if in_ideal:
            glow_surf = pygame.Surface((temp_width + 10, temp_height + 10), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (100, 255, 100, 60), (0, 0, temp_width + 10, temp_height + 10), border_radius=8)
            surf.blit(glow_surf, (temp_x - 5, temp_y - 5))

        pygame.draw.rect(surf, (200, 200, 200), (temp_x, temp_y, temp_width, temp_height), 2)

        # Temperature label with color based on status
        label_color = (100, 255, 100) if in_ideal else (255, 255, 255)
        _temp_surf = self.renderer.small_font.render(f"Temperature: {int(state['temperature'])}°C", True, label_color)
        surf.blit(_temp_surf, (temp_x, temp_y - 25))

        if in_ideal:
            _temp_surf = self.renderer.tiny_font.render("✓ IDEAL RANGE", True, (100, 255, 100))
            surf.blit(_temp_surf, (temp_x + temp_width - 80, temp_y - 25))

        # Hammer bar
        hammer_x, hammer_y = 50, 200
        hammer_width = state['hammer_bar_width']
        hammer_height = 60

        # Draw hammer bar background
        pygame.draw.rect(surf, (40, 40, 40), (hammer_x, hammer_y, hammer_width, hammer_height))

        # Draw target zone (center)
        center = hammer_width / 2
        target_start = int(center - state['target_width'] / 2)
        pygame.draw.rect(surf, (80, 80, 60), (hammer_x + target_start, hammer_y, state['target_width'], hammer_height))

        # Draw perfect zone (center of target)
        perfect_start = int(center - state['perfect_width'] / 2)
        pygame.draw.rect(surf, (100, 120, 60), (hammer_x + perfect_start, hammer_y, state['perfect_width'], hammer_height))

        # Draw hammer indicator
        hammer_pos = int(state['hammer_position'])
        pygame.draw.circle(surf, (255, 215, 0), (hammer_x + hammer_pos, hammer_y + hammer_height // 2), 15)

        pygame.draw.rect(surf, (200, 200, 200), (hammer_x, hammer_y, hammer_width, hammer_height), 2)
        _temp_surf = self.renderer.small_font.render(f"Hammer Timing: {state['hammer_hits']}/{state['required_hits']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (hammer_x, hammer_y - 25))

        # Hammer button
        btn_w, btn_h = 200, 60
        btn_x, btn_y = ww // 2 - btn_w // 2, 300
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(surf, (80, 60, 20), btn_rect)
        pygame.draw.rect(surf, (255, 215, 0), btn_rect, 3)
        _temp_surf = self.renderer.font.render("HAMMER", True, (255, 215, 0))
        surf.blit(_temp_surf, (btn_x + 40, btn_y + 15))

        # Timer and scores
        _temp_surf = self.renderer.font.render(f"Time Left: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 400))

        if state['hammer_scores']:
            _temp_surf = self.renderer.small_font.render("Hammer Scores:", True, (200, 200, 200))
            surf.blit(_temp_surf, (50, 450))
            for i, score in enumerate(state['hammer_scores'][-5:]):  # Last 5 scores
                color = (100, 255, 100) if score >= 90 else (255, 215, 0) if score >= 70 else (255, 100, 100)
                _temp_surf = self.renderer.small_font.render(f"Hit {i+1}: {score}", True, color)
                surf.blit(_temp_surf, (70, 480 + i * 25))

        # Result (if completed)
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 300), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render("SUCCESS!", True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(f"Score: {int(result['score'])}", True, (255, 255, 255))
                result_surf.blit(_temp_surf, (150, 120))
                _temp_surf = self.renderer.small_font.render(f"Bonus: +{result['bonus']}%", True, (255, 215, 0))
                result_surf.blit(_temp_surf, (150, 150))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 200))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 120))

            surf.blit(result_surf, (200, 200))

        self.screen.blit(surf, (wx, wy))

        # Store button rect for click detection (relative to screen)
        self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

    def _render_alchemy_minigame(self):
        """Render alchemy minigame UI"""
        state = self.active_minigame.get_state()

        # Create overlay
        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("ALCHEMY MINIGAME", True, (60, 180, 60))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[C] Chain Ingredient | [S] Stabilize & Complete", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress bar
        progress = state['total_progress']
        prog_x, prog_y = 50, 100
        prog_width = 600
        prog_height = 30
        pygame.draw.rect(surf, (40, 40, 40), (prog_x, prog_y, prog_width, prog_height))
        pygame.draw.rect(surf, (60, 180, 60), (prog_x, prog_y, int(progress * prog_width), prog_height))
        pygame.draw.rect(surf, (200, 200, 200), (prog_x, prog_y, prog_width, prog_height), 2)
        _temp_surf = self.renderer.small_font.render(f"Total Progress: {int(progress * 100)}%", True, (255, 255, 255))
        surf.blit(_temp_surf, (prog_x, prog_y - 25))

        # Current reaction visualization
        if state['current_reaction']:
            reaction = state['current_reaction']
            rx, ry = 50, 180

            # Reaction bubble
            bubble_size = int(100 * reaction['size'])
            bubble_color = (int(60 + 140 * reaction['color_shift']), int(180 * reaction['glow']), int(60 + 140 * reaction['color_shift']))
            pygame.draw.circle(surf, bubble_color, (rx + 100, ry + 100), bubble_size)
            pygame.draw.circle(surf, (200, 200, 200), (rx + 100, ry + 100), bubble_size, 2)

            # Stage info
            stage_names = ["Initiation", "Building", "SWEET SPOT", "Degrading", "Critical", "EXPLOSION!"]
            stage_idx = reaction['stage'] - 1
            stage_name = stage_names[stage_idx] if 0 <= stage_idx < len(stage_names) else "Unknown"
            stage_color = (255, 215, 0) if reaction['stage'] == 3 else (255, 100, 100) if reaction['stage'] >= 5 else (200, 200, 200)

            _temp_surf = self.renderer.font.render(f"Stage: {stage_name}", True, stage_color)
            surf.blit(_temp_surf, (rx, ry + 220))
            _temp_surf = self.renderer.small_font.render(f"Quality: {int(reaction['quality'] * 100)}%", True, (200, 200, 200))
            surf.blit(_temp_surf, (rx, ry + 250))

        # Ingredient progress
        _temp_surf = self.renderer.small_font.render(f"Ingredient: {state['current_ingredient_index'] + 1}/{state['total_ingredients']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 450))

        # Buttons
        btn_w, btn_h = 150, 50
        chain_btn = pygame.Rect(ww // 2 - btn_w - 10, 550, btn_w, btn_h)
        stabilize_btn = pygame.Rect(ww // 2 + 10, 550, btn_w, btn_h)

        pygame.draw.rect(surf, (60, 80, 20), chain_btn)
        pygame.draw.rect(surf, (255, 215, 0), chain_btn, 2)
        _temp_surf = self.renderer.small_font.render("CHAIN [C]", True, (255, 215, 0))
        surf.blit(_temp_surf, (chain_btn.x + 30, chain_btn.y + 15))

        pygame.draw.rect(surf, (20, 60, 80), stabilize_btn)
        pygame.draw.rect(surf, (100, 200, 255), stabilize_btn, 2)
        _temp_surf = self.renderer.small_font.render("STABILIZE [S]", True, (100, 200, 255))
        surf.blit(_temp_surf, (stabilize_btn.x + 15, stabilize_btn.y + 15))

        # Timer
        _temp_surf = self.renderer.font.render(f"Time: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 620))

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 300), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render(result['quality'], True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(f"Progress: {int(result['progress'] * 100)}%", True, (255, 255, 255))
                result_surf.blit(_temp_surf, (150, 120))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 150))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 120))

            surf.blit(result_surf, (200, 200))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = pygame.Rect(wx + chain_btn.x, wy + chain_btn.y, chain_btn.width, chain_btn.height)
        self.minigame_button_rect2 = pygame.Rect(wx + stabilize_btn.x, wy + stabilize_btn.y, stabilize_btn.width, stabilize_btn.height)

    def _render_refining_minigame(self):
        """Render refining minigame UI"""
        state = self.active_minigame.get_state()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("REFINING MINIGAME", True, (180, 120, 60))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[SPACE] Align Cylinder", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress
        _temp_surf = self.renderer.font.render(f"Cylinders: {state['aligned_count']}/{state['total_cylinders']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 100))
        _temp_surf = self.renderer.font.render(f"Failures: {state['failed_attempts']}/{state['allowed_failures']}", True, (255, 100, 100))
        surf.blit(_temp_surf, (50, 140))
        _temp_surf = self.renderer.font.render(f"Time: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 180))

        # Current cylinder visualization
        if state['current_cylinder'] < len(state['cylinders']):
            cyl = state['cylinders'][state['current_cylinder']]
            cx, cy = ww // 2, 300
            radius = 100

            # Draw cylinder circle
            pygame.draw.circle(surf, (60, 60, 60), (cx, cy), radius)
            pygame.draw.circle(surf, (200, 200, 200), (cx, cy), radius, 3)

            # Draw indicator at current angle
            angle_rad = math.radians(cyl['angle'])
            ind_x = cx + int(radius * 0.8 * math.cos(angle_rad - math.pi/2))
            ind_y = cy + int(radius * 0.8 * math.sin(angle_rad - math.pi/2))
            pygame.draw.circle(surf, (255, 215, 0), (ind_x, ind_y), 15)

            # Draw target zone at top
            pygame.draw.circle(surf, (100, 255, 100), (cx, cy - radius), 20, 3)

        # Instructions
        _temp_surf = self.renderer.small_font.render("Press SPACE when indicator is at the top!", True, (200, 200, 200))
        surf.blit(_temp_surf, (ww//2 - 150, 450))

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 200), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render("SUCCESS!", True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 100))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 100))

            surf.blit(result_surf, (200, 250))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = None

    def _render_engineering_minigame(self):
        """Render engineering minigame UI with actual puzzle visualization"""
        state = self.active_minigame.get_state()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("ENGINEERING MINIGAME", True, (60, 120, 180))
        surf.blit(_temp_surf, (ww//2 - 120, 20))
        _temp_surf = self.renderer.small_font.render("Solve puzzles to complete device", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress
        _temp_surf = self.renderer.font.render(f"Puzzle: {state['current_puzzle_index'] + 1}/{state['total_puzzles']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 100))
        _temp_surf = self.renderer.font.render(f"Solved: {state['solved_count']}", True, (100, 255, 100))
        surf.blit(_temp_surf, (50, 140))

        # Store puzzle cell rects for click detection
        self.engineering_puzzle_rects = []

        # Puzzle-specific rendering
        if state['current_puzzle']:
            puzzle = state['current_puzzle']

            # Detect puzzle type and render accordingly
            if 'grid' in puzzle and 'rotations' in puzzle:
                # Rotation Pipe Puzzle
                self._render_rotation_pipe_puzzle(surf, puzzle, wx, wy)
            elif 'grid' in puzzle and 'moves' in puzzle:
                # Sliding Tile Puzzle
                self._render_sliding_tile_puzzle(surf, puzzle, wx, wy)
            elif puzzle.get('placeholder'):
                # Placeholder puzzle
                puzzle_rect = pygame.Rect(200, 250, 600, 300)
                pygame.draw.rect(surf, (40, 40, 40), puzzle_rect)
                pygame.draw.rect(surf, (100, 100, 100), puzzle_rect, 2)
                _temp_surf = self.renderer.small_font.render("Puzzle placeholder - Click COMPLETE", True, (200, 200, 200))
                surf.blit(_temp_surf, (puzzle_rect.x + 20, puzzle_rect.y + 20))

        # Complete button (for placeholder/testing only)
        btn_w, btn_h = 200, 50
        btn_x, btn_y = ww // 2 - btn_w // 2, 600
        complete_btn = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        # Only show complete button for placeholder puzzles
        if state['current_puzzle'] and state['current_puzzle'].get('placeholder'):
            pygame.draw.rect(surf, (60, 100, 60), complete_btn)
            pygame.draw.rect(surf, (100, 200, 100), complete_btn, 2)
            _temp_surf = self.renderer.small_font.render("COMPLETE PUZZLE", True, (200, 200, 200))
            surf.blit(_temp_surf, (btn_x + 40, btn_y + 15))
            self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)
        else:
            self.minigame_button_rect = None

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 200), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            _temp_surf = self.renderer.font.render("DEVICE CREATED!", True, (100, 255, 100))
            result_surf.blit(_temp_surf, (200, 50))
            _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
            result_surf.blit(_temp_surf, (150, 100))
            surf.blit(result_surf, (200, 250))

        self.screen.blit(surf, (wx, wy))

    def _render_rotation_pipe_puzzle(self, surf, puzzle, wx, wy):
        """Render rotation pipe puzzle with visual pipe pieces"""
        grid_size = puzzle['grid_size']
        grid = puzzle['grid']
        rotations = puzzle['rotations']
        input_pos = puzzle['input_pos']
        output_pos = puzzle['output_pos']

        # Calculate cell size and position
        puzzle_area_size = min(500, 500)
        cell_size = puzzle_area_size // grid_size
        start_x = (1000 - (cell_size * grid_size)) // 2
        start_y = 200

        _temp_surf = self.renderer.small_font.render("Click pipes to rotate", True, (180, 180, 180))
        surf.blit(_temp_surf, (start_x, start_y - 30))

        # Draw grid
        for r in range(grid_size):
            for c in range(grid_size):
                x = start_x + c * cell_size
                y = start_y + r * cell_size

                # Cell background
                cell_color = (50, 50, 60) if (r, c) in [input_pos, output_pos] else (40, 40, 50)
                pygame.draw.rect(surf, cell_color, (x, y, cell_size, cell_size))
                pygame.draw.rect(surf, (80, 80, 90), (x, y, cell_size, cell_size), 1)

                piece_type = grid[r][c]
                rotation = rotations[r][c]

                # Store rect for click detection (relative to screen coordinates)
                self.engineering_puzzle_rects.append((
                    pygame.Rect(wx + x, wy + y, cell_size, cell_size),
                    ('rotate', r, c)
                ))

                # Draw pipe piece
                if piece_type != 0:
                    self._draw_pipe_piece(surf, x, y, cell_size, piece_type, rotation)

                # Mark input/output
                if (r, c) == input_pos:
                    _temp_surf = self.renderer.tiny_font.render("IN", True, (100, 255, 100))
                    surf.blit(_temp_surf, (x + 5, y + 5))
                elif (r, c) == output_pos:
                    _temp_surf = self.renderer.tiny_font.render("OUT", True, (255, 100, 100))
                    surf.blit(_temp_surf, (x + 5, y + 5))

    def _draw_pipe_piece(self, surf, x, y, size, piece_type, rotation):
        """Draw a pipe piece with the given type and rotation"""
        center_x = x + size // 2
        center_y = y + size // 2
        pipe_width = max(4, size // 8)
        pipe_color = (100, 180, 220)

        if piece_type == 1:  # Straight
            if rotation in [0, 180]:  # Horizontal
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size, pipe_width))
            else:  # Vertical
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size))

        elif piece_type == 2:  # L-bend
            if rotation == 0:  # Top-Right
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size//2 + pipe_width//2))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))
            elif rotation == 90:  # Right-Bottom
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, pipe_width, size//2 + pipe_width//2))
            elif rotation == 180:  # Bottom-Left
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, pipe_width, size//2 + pipe_width//2))
            else:  # Left-Top
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size//2 + pipe_width//2))

        elif piece_type == 3:  # T-junction
            # Draw based on which direction is missing
            if rotation == 0:  # Missing bottom
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size, pipe_width))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size//2 + pipe_width//2))
            elif rotation == 90:  # Missing left
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))
            elif rotation == 180:  # Missing top
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size, pipe_width))
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, center_y - pipe_width//2, pipe_width, size//2 + pipe_width//2))
            else:  # Missing right
                pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size))
                pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size//2 + pipe_width//2, pipe_width))

        elif piece_type == 4:  # Cross
            pygame.draw.rect(surf, pipe_color, (x, center_y - pipe_width//2, size, pipe_width))
            pygame.draw.rect(surf, pipe_color, (center_x - pipe_width//2, y, pipe_width, size))

    def _render_sliding_tile_puzzle(self, surf, puzzle, wx, wy):
        """Render sliding tile puzzle with numbered tiles"""
        grid_size = puzzle['grid_size']
        grid = puzzle['grid']
        empty_pos = puzzle['empty_pos']
        moves = puzzle.get('moves', 0)

        # Calculate cell size and position
        puzzle_area_size = min(400, 400)
        cell_size = puzzle_area_size // grid_size
        start_x = (1000 - (cell_size * grid_size)) // 2
        start_y = 200

        _temp_surf = self.renderer.small_font.render(f"Click tiles to slide - Moves: {moves}", True, (180, 180, 180))
        surf.blit(_temp_surf, (start_x, start_y - 30))

        # Draw grid
        for r in range(grid_size):
            for c in range(grid_size):
                x = start_x + c * cell_size
                y = start_y + r * cell_size

                tile_num = grid[r][c]

                # Store rect for click detection
                self.engineering_puzzle_rects.append((
                    pygame.Rect(wx + x, wy + y, cell_size, cell_size),
                    ('slide', r, c)
                ))

                if tile_num == 0:  # Empty space
                    pygame.draw.rect(surf, (30, 30, 40), (x, y, cell_size, cell_size))
                    pygame.draw.rect(surf, (60, 60, 70), (x, y, cell_size, cell_size), 2)
                else:
                    # Draw tile
                    pygame.draw.rect(surf, (60, 90, 120), (x+2, y+2, cell_size-4, cell_size-4))
                    pygame.draw.rect(surf, (100, 140, 180), (x+2, y+2, cell_size-4, cell_size-4), 2)

                    # Draw number
                    _temp_surf = self.renderer.font.render(str(tile_num), True, (255, 255, 255))
                    text_rect = _temp_surf.get_rect(center=(x + cell_size//2, y + cell_size//2))
                    surf.blit(_temp_surf, text_rect)

    def _render_enchanting_minigame(self):
        """Render spinning wheel gambling minigame UI"""
        if not self.active_minigame:
            return

        state = self.active_minigame.get_state()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("SPINNING WHEEL MINIGAME", True, (255, 215, 0))
        surf.blit(_temp_surf, (ww//2 - 180, 20))

        # Currency display
        current_currency = state.get('current_currency', 100)
        _temp_surf = self.renderer.font.render(f"Currency: {current_currency}", True, (100, 255, 100))
        surf.blit(_temp_surf, (50, 80))

        # Spin counter
        spin_num = state.get('current_spin_number', 0) + 1
        _temp_surf = self.renderer.small_font.render(f"Spin {spin_num} / 3", True, (200, 200, 200))
        surf.blit(_temp_surf, (ww - 150, 80))

        # Phase-specific rendering
        phase = state.get('phase', 'betting')

        # Wheel area
        wheel_center = (ww // 2, 350)
        wheel_radius = 180
        wheel_visible = state.get('wheel_visible', False)

        if wheel_visible:
            # Draw spinning wheel
            current_wheel = state.get('current_wheel', [])
            wheel_rotation = state.get('wheel_rotation', 0.0)

            if current_wheel:
                # Draw wheel background
                pygame.draw.circle(surf, (40, 40, 50), wheel_center, wheel_radius)
                pygame.draw.circle(surf, (200, 200, 200), wheel_center, wheel_radius, 4)

                # Draw 20 slices
                slice_angle = 360 / 20  # 18 degrees per slice
                color_map = {
                    'green': (50, 200, 50),
                    'red': (200, 50, 50),
                    'grey': (120, 120, 120)
                }

                for i, color_name in enumerate(current_wheel):
                    # Calculate slice angles
                    start_angle = i * slice_angle - wheel_rotation - 90  # -90 to start at top
                    end_angle = (i + 1) * slice_angle - wheel_rotation - 90

                    # Convert to radians
                    start_rad = math.radians(start_angle)
                    end_rad = math.radians(end_angle)

                    # Draw slice as a polygon (triangle fan from center)
                    points = [wheel_center]
                    # Generate arc points
                    num_arc_points = 5
                    for j in range(num_arc_points + 1):
                        angle = start_rad + (end_rad - start_rad) * (j / num_arc_points)
                        px = wheel_center[0] + int(wheel_radius * math.cos(angle))
                        py = wheel_center[1] + int(wheel_radius * math.sin(angle))
                        points.append((px, py))

                    color = color_map.get(color_name, (100, 100, 100))
                    pygame.draw.polygon(surf, color, points)
                    pygame.draw.polygon(surf, (0, 0, 0), points, 2)

                # Draw pointer at top
                pointer_points = [
                    (wheel_center[0], wheel_center[1] - wheel_radius - 20),
                    (wheel_center[0] - 15, wheel_center[1] - wheel_radius - 5),
                    (wheel_center[0] + 15, wheel_center[1] - wheel_radius - 5)
                ]
                pygame.draw.polygon(surf, (255, 255, 0), pointer_points)
                pygame.draw.polygon(surf, (0, 0, 0), pointer_points, 2)

                # Draw center circle
                pygame.draw.circle(surf, (60, 60, 70), wheel_center, 30)
                pygame.draw.circle(surf, (200, 200, 200), wheel_center, 30, 3)
        else:
            # Wheel hidden
            _temp_surf = self.renderer.font.render("???", True, (100, 100, 100))
            text_rect = _temp_surf.get_rect(center=wheel_center)
            surf.blit(_temp_surf, text_rect)
            _temp_surf = self.renderer.small_font.render("Place bet to reveal wheel", True, (150, 150, 150))
            text_rect = _temp_surf.get_rect(center=(wheel_center[0], wheel_center[1] + 40))
            surf.blit(_temp_surf, text_rect)

        # Payout display panel (right side)
        current_multiplier = state.get('current_multiplier', {})
        if current_multiplier:
            panel_x = ww - 220
            panel_y = 140
            panel_w = 200
            panel_h = 280

            # Draw panel background
            pygame.draw.rect(surf, (30, 30, 40, 200), (panel_x, panel_y, panel_w, panel_h))
            pygame.draw.rect(surf, (100, 100, 120), (panel_x, panel_y, panel_w, panel_h), 2)

            # Title
            _temp_surf = self.renderer.small_font.render("PAYOUTS", True, (255, 215, 0))
            surf.blit(_temp_surf, (panel_x + 55, panel_y + 10))

            _temp_surf = self.renderer.tiny_font.render(f"(Spin {spin_num})", True, (180, 180, 180))
            surf.blit(_temp_surf, (panel_x + 65, panel_y + 35))

            # Color labels and multipliers
            color_y = panel_y + 65
            spacing = 60

            # Green
            pygame.draw.rect(surf, (50, 200, 50), (panel_x + 20, color_y, 40, 40))
            pygame.draw.rect(surf, (0, 0, 0), (panel_x + 20, color_y, 40, 40), 2)
            _temp_surf = self.renderer.small_font.render("GREEN", True, (255, 255, 255))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('green', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (100, 255, 100))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 20))

            # Grey
            color_y += spacing
            pygame.draw.rect(surf, (120, 120, 120), (panel_x + 20, color_y, 40, 40))
            pygame.draw.rect(surf, (0, 0, 0), (panel_x + 20, color_y, 40, 40), 2)
            _temp_surf = self.renderer.small_font.render("GREY", True, (255, 255, 255))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('grey', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (200, 200, 200))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 20))

            # Red
            color_y += spacing
            pygame.draw.rect(surf, (200, 50, 50), (panel_x + 20, color_y, 40, 40))
            pygame.draw.rect(surf, (0, 0, 0), (panel_x + 20, color_y, 40, 40), 2)
            _temp_surf = self.renderer.small_font.render("RED", True, (255, 255, 255))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('red', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (255, 100, 100))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 20))

        # Betting controls
        if phase == 'betting':
            # Initialize bet amount if not set
            if not hasattr(self, 'wheel_slider_bet_amount'):
                self.wheel_slider_bet_amount = min(10, current_currency)

            bet_y = 560
            _temp_surf = self.renderer.small_font.render("Place Bet:", True, (200, 200, 200))
            surf.blit(_temp_surf, (50, bet_y))

            # Bet amount display
            _temp_surf = self.renderer.font.render(f"${self.wheel_slider_bet_amount}", True, (255, 215, 0))
            surf.blit(_temp_surf, (50, bet_y + 25))

            # Slider
            slider_x = 50
            slider_y = bet_y + 65
            slider_w = 400
            slider_h = 10

            # Slider background
            pygame.draw.rect(surf, (60, 60, 70), (slider_x, slider_y, slider_w, slider_h))
            pygame.draw.rect(surf, (100, 100, 120), (slider_x, slider_y, slider_w, slider_h), 2)

            # Slider handle position
            if current_currency > 0:
                slider_pos = (self.wheel_slider_bet_amount / current_currency) * slider_w
            else:
                slider_pos = 0

            handle_x = slider_x + int(slider_pos)
            handle_y = slider_y - 5
            handle_w = 15
            handle_h = 20

            # Draw slider handle
            pygame.draw.rect(surf, (100, 150, 200), (handle_x - handle_w//2, handle_y, handle_w, handle_h))
            pygame.draw.rect(surf, (150, 200, 255), (handle_x - handle_w//2, handle_y, handle_w, handle_h), 2)

            # Store slider rect for click detection
            self.wheel_slider_rect = pygame.Rect(wx + slider_x, wy + slider_y - 10, slider_w, slider_h + 20)
            self.wheel_slider_info = (current_currency, slider_x, slider_w)

            # Quick bet buttons
            btn_y = bet_y + 95
            _temp_surf = self.renderer.tiny_font.render("Quick Bet:", True, (150, 150, 150))
            surf.blit(_temp_surf, (50, btn_y))

            bet_amounts = [10, 25, 50, current_currency]
            bet_button_rects = []
            for i, amount in enumerate(bet_amounts):
                btn_x = 50 + i * 85
                btn_w, btn_h = 75, 30
                btn_rect = pygame.Rect(btn_x, btn_y + 20, btn_w, btn_h)

                btn_text = "ALL" if i == 3 else f"${amount}"
                btn_color = (80, 100, 60) if amount <= current_currency else (60, 60, 60)

                pygame.draw.rect(surf, btn_color, btn_rect)
                pygame.draw.rect(surf, (150, 180, 120), btn_rect, 2)
                _temp_surf = self.renderer.tiny_font.render(btn_text, True, (255, 255, 255))
                text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + 20 + btn_h//2))
                surf.blit(_temp_surf, text_rect)

                # Store for click detection (in screen coordinates)
                bet_button_rects.append((pygame.Rect(wx + btn_x, wy + btn_y + 20, btn_w, btn_h), amount))

            self.wheel_bet_buttons = bet_button_rects

            # Confirm bet button
            confirm_x, confirm_y = ww//2 - 100, 630
            confirm_w, confirm_h = 200, 50
            confirm_btn_rect = pygame.Rect(confirm_x, confirm_y, confirm_w, confirm_h)
            confirm_enabled = self.wheel_slider_bet_amount > 0 and self.wheel_slider_bet_amount <= current_currency
            confirm_color = (100, 60, 120) if confirm_enabled else (60, 40, 60)

            pygame.draw.rect(surf, confirm_color, confirm_btn_rect)
            pygame.draw.rect(surf, (200, 120, 240), confirm_btn_rect, 3)
            _temp_surf = self.renderer.font.render("PLACE BET", True, (255, 255, 255))
            text_rect = _temp_surf.get_rect(center=(confirm_x + confirm_w//2, confirm_y + confirm_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_confirm_bet_button = pygame.Rect(wx + confirm_x, wy + confirm_y, confirm_w, confirm_h)

        elif phase == 'ready_to_spin':
            # Show current bet and spin button
            current_bet = state.get('current_bet', 0)
            _temp_surf = self.renderer.small_font.render(f"Current Bet: ${current_bet}", True, (255, 215, 0))
            surf.blit(_temp_surf, (50, 600))

            # Spin button
            btn_x, btn_y = ww//2 - 100, 620
            btn_w, btn_h = 200, 50
            spin_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            pygame.draw.rect(surf, (100, 60, 120), spin_btn_rect)
            pygame.draw.rect(surf, (200, 120, 240), spin_btn_rect, 3)
            _temp_surf = self.renderer.font.render("SPIN!", True, (255, 255, 255))
            text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + btn_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_spin_button = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

        elif phase == 'spinning':
            # Show spinning message
            _temp_surf = self.renderer.font.render("SPINNING...", True, (255, 215, 0))
            text_rect = _temp_surf.get_rect(center=(ww//2, 620))
            surf.blit(_temp_surf, text_rect)
            self.wheel_spin_button = None

        elif phase == 'spin_result':
            # Show result of this spin
            spin_results = state.get('spin_results', [])
            if spin_results:
                last_result = spin_results[-1]
                result_y = 590

                color_text = last_result['color'].upper()
                profit = last_result['profit']
                profit_text = f"+${profit}" if profit >= 0 else f"-${abs(profit)}"
                profit_color = (100, 255, 100) if profit >= 0 else (255, 100, 100)

                _temp_surf = self.renderer.font.render(f"Result: {color_text}", True, (255, 255, 255))
                surf.blit(_temp_surf, (ww//2 - 100, result_y))
                _temp_surf = self.renderer.font.render(profit_text, True, profit_color)
                surf.blit(_temp_surf, (ww//2 - 60, result_y + 35))

            # Next button
            btn_x, btn_y = ww//2 - 100, 635
            btn_w, btn_h = 200, 40
            next_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            pygame.draw.rect(surf, (60, 100, 80), next_btn_rect)
            pygame.draw.rect(surf, (120, 200, 160), next_btn_rect, 3)
            btn_text = "NEXT SPIN" if spin_num < 3 else "FINISH"
            _temp_surf = self.renderer.small_font.render(btn_text, True, (255, 255, 255))
            text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + btn_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_next_button = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

        elif phase == 'completed':
            # Show final result
            result = state.get('result', {})
            if result:
                efficacy_percent = result.get('efficacy_percent', 0)
                final_currency = result.get('final_currency', 100)
                currency_diff = result.get('currency_diff', 0)

                result_surf = pygame.Surface((800, 400), pygame.SRCALPHA)
                result_surf.fill((10, 10, 20, 240))

                _temp_surf = self.renderer.font.render("MINIGAME COMPLETE!", True, (255, 215, 0))
                result_surf.blit(_temp_surf, (250, 50))

                _temp_surf = self.renderer.small_font.render(f"Final Currency: ${final_currency}", True, (200, 200, 200))
                result_surf.blit(_temp_surf, (270, 120))

                diff_text = f"+${currency_diff}" if currency_diff >= 0 else f"-${abs(currency_diff)}"
                diff_color = (100, 255, 100) if currency_diff >= 0 else (255, 100, 100)
                _temp_surf = self.renderer.small_font.render(f"Profit/Loss: {diff_text}", True, diff_color)
                result_surf.blit(_temp_surf, (270, 150))

                eff_text = f"{efficacy_percent:+.1f}%"
                eff_color = (100, 255, 100) if efficacy_percent >= 0 else (255, 100, 100)
                _temp_surf = self.renderer.font.render(f"Efficacy Bonus: {eff_text}", True, eff_color)
                result_surf.blit(_temp_surf, (220, 200))

                _temp_surf = self.renderer.small_font.render("Click anywhere to continue", True, (150, 150, 150))
                result_surf.blit(_temp_surf, (250, 320))

                surf.blit(result_surf, (100, 150))

        self.screen.blit(surf, (wx, wy))
        self.enchanting_minigame_window = pygame.Rect(wx, wy, ww, wh)

    def run(self):
        print("=== GAME STARTED ===")
        print("Controls:")
        print("  WASD - Move")
        print("  Click - Harvest/Interact")
        print("  TAB - Switch Tool")
        print("  C - Stats")
        print("  E - Equipment")
        print("  F1 - Toggle Debug Mode")
        print("  ESC - Close/Quit")
        print("\nEquipment:")
        print("  Double-click item in inventory to equip")
        print("  Shift+click equipment slot to unequip")
        print("\nTip: Crafting stations are right next to you!")
        print()

        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(Config.FPS)

        pygame.quit()
        sys.exit()
