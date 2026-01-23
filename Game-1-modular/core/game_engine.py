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
from .minigame_effects import (
    get_effects_manager,
    ColorPalette,
    SparkParticle,
    EmberParticle,
    BubbleParticle,
    SteamParticle,
    GearToothParticle,
    AnimatedProgressBar,
    AnimatedButton,
    lerp_color,
    ease_out_cubic,
)

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
        from data.databases import SkillUnlockDatabase
        SkillUnlockDatabase.get_instance().load_from_file(str(get_resource_path("progression/skill-unlocks.JSON")))
        NPCDatabase.get_instance().load_from_files()  # Load NPCs and Quests

        # Load content from installed Update-N packages
        from data.databases.update_loader import load_all_updates
        load_all_updates(get_resource_path(""))

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

        # Interactive crafting UI state
        self.interactive_crafting_active = False  # True when interactive UI is open
        self.interactive_ui = None  # InteractiveBaseUI instance (from core.interactive_crafting)
        self.interactive_button_rect = None  # "Interactive Mode" button rect in crafting UI
        self.interactive_material_rects = []  # Material palette click regions
        self.interactive_placement_rects = []  # Placement area click regions
        self.interactive_button_rects = {}  # Craft buttons: {'clear': rect, 'instant': rect, 'minigame': rect}

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

                # Collect enchantment metadata tags and apply enchantment effects
                if hasattr(weapon, 'enchantments') and weapon.enchantments:
                    enchant_tags = []
                    damage_multiplier = 1.0

                    for ench in weapon.enchantments:
                        # Collect metadata tags
                        metadata_tags = ench.get('metadata_tags', [])
                        if metadata_tags:
                            enchant_tags.extend(metadata_tags)

                        # Apply damage multiplier enchantments (Sharpness, etc.)
                        effect = ench.get('effect', {})
                        if effect.get('type') == 'damage_multiplier':
                            damage_multiplier += effect.get('value', 0.0)

                    # Merge enchantment tags with weapon tags (avoid duplicates)
                    if enchant_tags:
                        effect_tags = list(set(effect_tags + enchant_tags))

                    # Apply damage multiplier to baseDamage
                    if damage_multiplier != 1.0 and 'baseDamage' in effect_params:
                        effect_params = effect_params.copy()
                        effect_params['baseDamage'] *= damage_multiplier

                # Apply weaken status damage reduction
                if hasattr(self.character, 'status_manager'):
                    weaken_effect = self.character.status_manager._find_effect('weaken')
                    if weaken_effect:
                        stat_reduction = weaken_effect.params.get('stat_reduction', 0.25)
                        affected_stats = weaken_effect.params.get('affected_stats', ['damage', 'defense'])

                        if 'damage' in affected_stats and 'baseDamage' in effect_params:
                            effect_params = effect_params.copy()
                            effect_params['baseDamage'] *= (1.0 - stat_reduction)

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
                    elif self.interactive_crafting_active:
                        # Close interactive crafting UI (priority over regular crafting UI)
                        self._close_interactive_crafting()
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
                    # Get mouse world position for directional skills
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_world_pos = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1])
                    success, msg = self.character.skills.use_skill(0, self.character, self.combat_manager, mouse_world_pos)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_2:
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_world_pos = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1])
                    success, msg = self.character.skills.use_skill(1, self.character, self.combat_manager, mouse_world_pos)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_3:
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_world_pos = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1])
                    success, msg = self.character.skills.use_skill(2, self.character, self.combat_manager, mouse_world_pos)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_4:
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_world_pos = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1])
                    success, msg = self.character.skills.use_skill(3, self.character, self.combat_manager, mouse_world_pos)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_5:
                    mouse_pos = pygame.mouse.get_pos()
                    mouse_world_pos = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1])
                    success, msg = self.character.skills.use_skill(4, self.character, self.combat_manager, mouse_world_pos)
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

                elif event.key == pygame.K_F7:
                    # Toggle infinite durability (separate from F1 resources)
                    Config.DEBUG_INFINITE_DURABILITY = not Config.DEBUG_INFINITE_DURABILITY
                    if Config.DEBUG_INFINITE_DURABILITY:
                        print("🔧 DEBUG F7: Infinite Durability ENABLED")
                        self.add_notification("Infinite Durability: ON", (100, 255, 100))
                    else:
                        print("🔧 DEBUG F7: Infinite Durability DISABLED")
                        self.add_notification("Infinite Durability: OFF", (255, 100, 100))

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

                # Handle mouse wheel scrolling for enchantment selection UI
                if hasattr(self, 'enchantment_selection_active') and self.enchantment_selection_active:
                    if hasattr(self, 'enchantment_selection_rect') and self.enchantment_selection_rect:
                        if self.enchantment_selection_rect.collidepoint(self.mouse_pos):
                            # Scroll the enchantment item list
                            self.enchantment_scroll_offset -= event.y  # event.y is positive for scroll up
                            # Clamp to valid range
                            max_scroll = max(0, len(self.enchantment_compatible_items) - 5)  # ~5 items visible
                            self.enchantment_scroll_offset = max(0, min(self.enchantment_scroll_offset, max_scroll))
                            continue  # Skip other scroll handlers

                # Handle mouse wheel scrolling for interactive crafting material palette
                if self.interactive_crafting_active and self.interactive_ui and self.crafting_window_rect:
                    if self.crafting_window_rect.collidepoint(self.mouse_pos):
                        # Scroll the material palette
                        self.interactive_ui.material_palette_scroll -= event.y  # event.y is positive for scroll up
                        # Clamp to valid range (0 to max materials)
                        available_materials = self.interactive_ui.get_available_materials()
                        max_scroll = max(0, len(available_materials) - 10)  # Assume ~10 visible items
                        self.interactive_ui.material_palette_scroll = max(0, min(self.interactive_ui.material_palette_scroll, max_scroll))
                        continue  # Skip other scroll handlers

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
        """Handle right-click events (SHIFT+right for consumables, right-click for offhand attacks, right-click to remove materials in interactive crafting)"""
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

        # Handle right-click in interactive crafting UI to remove materials
        if self.interactive_crafting_active and self.interactive_ui:
            for placement_rect, position in self.interactive_placement_rects:
                if placement_rect.collidepoint(mouse_pos):
                    # Remove material from this position
                    removed = self.interactive_ui.remove_material(position)
                    if removed:
                        print(f"✓ Removed {removed.item_id} from position {position}")
                        self.add_notification("Material removed", (200, 200, 200))
                    return  # Don't process world clicks

        # Handle inventory SHIFT+right-clicks for consumables
        if shift_held and mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
            # Calculate start_y to match renderer: tools_y(+55) + tool_slot(50) + padding(20) = +125
            tools_y = Config.INVENTORY_PANEL_Y + 55
            start_x, start_y = 20, tools_y + 50 + 20  # = INVENTORY_PANEL_Y + 125
            slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10  # Must match renderer spacing
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
            # Check if metadata overlay is blocking - dismiss on click
            effects = get_effects_manager()
            if effects.metadata_overlay.is_blocking():
                effects.metadata_overlay.dismiss()
                return

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

            # Check engineering puzzle cells first (rotation/toggle)
            if self.minigame_type == 'engineering' and hasattr(self, 'engineering_puzzle_rects'):
                for rect, action_data in self.engineering_puzzle_rects:
                    if rect.collidepoint(mouse_pos):
                        action_type = action_data[0]
                        row, col = action_data[1], action_data[2]

                        if action_type == 'rotate':
                            # Rotate pipe piece
                            self.active_minigame.handle_action('rotate', row=row, col=col)
                        elif action_type == 'toggle':
                            # Toggle logic switch
                            self.active_minigame.handle_action('toggle', row=row, col=col)
                        elif action_type == 'view_toggle':
                            # Toggle between current and target view with slide animation
                            if hasattr(self, '_logic_switch_view'):
                                self._logic_switch_slide_start = pygame.time.get_ticks()
                                self._logic_switch_slide_from = self._logic_switch_view
                                if self._logic_switch_view == 'current':
                                    self._logic_switch_view = 'target'
                                else:
                                    self._logic_switch_view = 'current'
                            return  # Don't check puzzle completion for view toggle
                        elif action_type == 'reset':
                            # Reset current puzzle to initial state
                            self.active_minigame.handle_action('reset')
                            self.add_notification("Puzzle reset to initial state", (200, 200, 100))
                            return  # Don't check puzzle completion for reset
                        elif action_type == 'slide':
                            # Slide tile (legacy)
                            self.active_minigame.handle_action('slide', row=row, col=col)

                        # Check if puzzle was solved
                        prev_puzzle_idx = self.active_minigame.current_puzzle_index
                        if self.active_minigame.check_current_puzzle():
                            puzzle_idx = self.active_minigame.current_puzzle_index
                            total = self.active_minigame.puzzle_count
                            efficiencies = getattr(self.active_minigame, 'puzzle_efficiencies', [])
                            if efficiencies:
                                eff = efficiencies[-1] * 100
                                print(f"✅ Puzzle {puzzle_idx}/{total} solved! Efficiency: {eff:.0f}%")
                            else:
                                print(f"✅ Puzzle {puzzle_idx}/{total} solved!")

                            # If we moved to a new puzzle (not completed all), show info overlay
                            if puzzle_idx < total and puzzle_idx > prev_puzzle_idx:
                                # Reset logic switch view state for new puzzle
                                self._logic_switch_view = 'current'
                                self._logic_switch_slide_start = 0
                                self._logic_switch_slide_from = 'current'

                                # Show info overlay for the new puzzle
                                effects = get_effects_manager()
                                current_puzzle = self.active_minigame.puzzles[puzzle_idx]
                                puzzle_state = current_puzzle.get_state()
                                puzzle_mode = puzzle_state.get('puzzle_mode', 'Unknown')
                                ideal_moves = puzzle_state.get('ideal_moves', 10)
                                grid_size = puzzle_state.get('grid_size', 4)

                                effects.show_metadata({
                                    'discipline': 'Engineering',
                                    'difficulty_tier': f'Puzzle {puzzle_idx + 1}/{total}',
                                    'difficulty_points': self.active_minigame.difficulty_points,
                                    'time_limit': None,  # No time limit display for puzzle info
                                    'max_bonus': 1.0 + self.active_minigame.difficulty_points * 0.02,
                                    'special_params': {
                                        'Puzzle Mode': puzzle_mode,
                                        'Grid Size': f'{grid_size}x{grid_size}',
                                        'Ideal Moves': ideal_moves
                                    }
                                })
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

        # Interactive Crafting UI (priority over regular crafting UI)
        if self.interactive_crafting_active and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                self._handle_interactive_click(mouse_pos)
                return
            # Click outside - close interactive UI
            else:
                self._close_interactive_crafting()
                return

        # Regular Crafting UI
        if self.character.crafting_ui_open and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                # Check if "Interactive Mode" button was clicked
                if self.interactive_button_rect and self.interactive_button_rect.collidepoint(mouse_pos):
                    self._open_interactive_crafting()
                    return

                # Regular crafting click handling
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
            slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10  # Must match renderer spacing
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

                                        # Place the entity (with tags and crafted_stats to preserve minigame bonuses)
                                        item_crafted_stats = item_stack.crafted_stats if hasattr(item_stack, 'crafted_stats') else None
                                        self.world.place_entity(
                                            player_pos,
                                            item_stack.item_id,
                                            entity_type,
                                            tier=mat_def.tier,
                                            range=range_val if entity_type != PlacedEntityType.CRAFTING_STATION else 0.0,
                                            damage=damage_val if entity_type != PlacedEntityType.CRAFTING_STATION else 0.0,
                                            tags=effect_tags,
                                            effect_params=effect_params,
                                            crafted_stats=item_crafted_stats
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

            # Check if stunned or frozen (cannot attack)
            if hasattr(self.character, 'status_manager'):
                if self.character.status_manager.has_status('stun'):
                    self.add_notification("Cannot attack while stunned!", (255, 100, 100))
                    return
                if self.character.status_manager.has_status('freeze'):
                    self.add_notification("Cannot attack while frozen!", (255, 100, 100))
                    return

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
                        # Add item back to inventory with preserved crafted_stats (minigame bonuses)
                        mat_db = MaterialDatabase.get_instance()
                        mat_def = mat_db.get_material(placed_entity.item_id)
                        if mat_def:
                            # Restore crafted_stats from placed entity
                            entity_crafted_stats = placed_entity.crafted_stats if hasattr(placed_entity, 'crafted_stats') and placed_entity.crafted_stats else None
                            # Try to add to inventory with preserved stats
                            success = self.character.inventory.add_item(
                                placed_entity.item_id, 1,
                                crafted_stats=entity_crafted_stats
                            )
                            if success:
                                # Remove from world
                                self.world.placed_entities.remove(placed_entity)
                                bonus_msg = " (with bonuses)" if entity_crafted_stats else ""
                                self.add_notification(f"Picked up {mat_def.name}{bonus_msg}", (100, 255, 100))
                                print(f"✓ Picked up {mat_def.name}{bonus_msg}")
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

            # Pass nearby resources for AoE gathering (Chain Harvest skill)
            result = self.character.harvest_resource(resource, nearby_resources=self.world.resources)
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

        # Initialize all bonus variables (prevents UnboundLocalError)
        buff_time_bonus = 0.0
        buff_quality_bonus = 0.0
        title_time_bonus = 0.0
        title_quality_bonus = 0.0
        total_time_bonus = 0.0
        total_quality_bonus = 0.0

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
            # Other crafting disciplines use buff bonuses + title bonuses
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

            # Calculate title bonuses for this crafting discipline
            # (Already initialized at function start)

            if recipe.station_type == 'smithing':
                title_time_bonus = self.character.titles.get_total_bonus('smithingTime')
                title_quality_bonus = self.character.titles.get_total_bonus('smithingQuality')
            elif recipe.station_type == 'refining':
                # Refining shares smithingTime and uses refiningPrecision for quality
                title_time_bonus = self.character.titles.get_total_bonus('smithingTime')
                title_quality_bonus = self.character.titles.get_total_bonus('refiningPrecision')
            elif recipe.station_type == 'alchemy':
                title_time_bonus = self.character.titles.get_total_bonus('alchemyTime')
                title_quality_bonus = self.character.titles.get_total_bonus('alchemyQuality')
            elif recipe.station_type == 'engineering':
                title_time_bonus = self.character.titles.get_total_bonus('engineeringTime')
                title_quality_bonus = self.character.titles.get_total_bonus('engineeringQuality')

            # Combine skill buffs and title bonuses
            total_time_bonus = buff_time_bonus + title_time_bonus
            total_quality_bonus = buff_quality_bonus + title_quality_bonus

            # Create minigame instance with combined bonuses
            minigame = crafter.create_minigame(recipe.recipe_id, total_time_bonus, total_quality_bonus)
            if not minigame:
                self.add_notification("Minigame not available!", (255, 100, 100))
                return

        if total_time_bonus > 0 or total_quality_bonus > 0:
            print(f"⚡ Active bonuses:")
            if buff_time_bonus > 0:
                print(f"   +{buff_time_bonus*100:.0f}% minigame time (skills)")
            if title_time_bonus > 0:
                print(f"   +{title_time_bonus*100:.0f}% minigame time (titles)")
            if total_time_bonus > 0:
                print(f"   Total: +{total_time_bonus*100:.0f}% minigame time")
            if buff_quality_bonus > 0:
                print(f"   +{buff_quality_bonus*100:.0f}% quality bonus (skills)")
            if title_quality_bonus > 0:
                print(f"   +{title_quality_bonus*100:.0f}% quality bonus (titles)")
            if total_quality_bonus > 0:
                print(f"   Total: +{total_quality_bonus*100:.0f}% quality bonus")

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

    # ===========================================================================
    # INTERACTIVE CRAFTING UI METHODS
    # ===========================================================================

    def _open_interactive_crafting(self):
        """Open the interactive crafting UI for the current station"""
        from core.interactive_crafting import create_interactive_ui

        if not self.character.active_station:
            print("⚠ No active station - cannot open interactive crafting")
            return

        # Create interactive UI instance
        station_type = self.character.active_station.station_type.value
        station_tier = self.character.active_station.tier

        self.interactive_ui = create_interactive_ui(
            station_type,
            station_tier,
            self.character.inventory
        )

        if self.interactive_ui:
            self.interactive_crafting_active = True
            print(f"✓ Opened interactive crafting UI for {station_type} (T{station_tier})")
            self.add_notification("Interactive Mode Activated", (100, 255, 100))
        else:
            print(f"✗ Failed to create interactive UI for {station_type}")
            self.add_notification("Failed to open interactive mode", (255, 100, 100))

    def _close_interactive_crafting(self):
        """Close interactive crafting UI and return all borrowed materials"""
        if self.interactive_ui:
            # Return all borrowed materials to inventory
            self.interactive_ui.return_all_materials()
            print(f"✓ Returned {len(self.interactive_ui.borrowed_materials)} material types to inventory")

        # Clear state
        self.interactive_ui = None
        self.interactive_crafting_active = False
        self.interactive_material_rects = []
        self.interactive_placement_rects = []
        self.interactive_button_rects = {}

        print("✓ Closed interactive crafting UI")

    def _handle_interactive_click(self, mouse_pos: Tuple[int, int]):
        """Handle click events in the interactive crafting UI"""
        if not self.interactive_ui or not self.interactive_crafting_active:
            return

        # Check button clicks (Clear, Instant Craft, Minigame)
        for button_name, button_rect in self.interactive_button_rects.items():
            if button_rect and button_rect.collidepoint(mouse_pos):
                print(f"🖱 Clicked interactive button: {button_name}")

                if button_name == 'clear':
                    # Clear placement
                    self.interactive_ui.clear_placement()
                    self.add_notification("Placement cleared", (200, 200, 200))
                    return

                elif button_name == 'instant' and self.interactive_ui.matched_recipe:
                    # Instant craft
                    self._handle_interactive_craft(use_minigame=False)
                    return

                elif button_name == 'minigame' and self.interactive_ui.matched_recipe:
                    # Start minigame
                    self._handle_interactive_craft(use_minigame=True)
                    return

        # Check material palette clicks
        for mat_rect, item_stack in self.interactive_material_rects:
            if mat_rect.collidepoint(mouse_pos):
                # Select material
                self.interactive_ui.selected_material = item_stack
                # Deselect shape if this is adornments (material and shape are mutually exclusive)
                from core.interactive_crafting import InteractiveAdornmentsUI
                if isinstance(self.interactive_ui, InteractiveAdornmentsUI):
                    self.interactive_ui.selected_shape_type = None
                print(f"✓ Selected material: {item_stack.item_id}")
                return

        # Check placement area clicks
        from core.interactive_crafting import InteractiveAdornmentsUI
        for placement_rect, position in self.interactive_placement_rects:
            if placement_rect.collidepoint(mouse_pos):
                # Handle adornments-specific controls
                if isinstance(self.interactive_ui, InteractiveAdornmentsUI):
                    if isinstance(position, tuple) and len(position) == 2:
                        if position[0] == 'shape_select':
                            # Shape selection button clicked
                            shape_type = position[1]
                            self.interactive_ui.selected_shape_type = shape_type
                            # Deselect material (shape and material are mutually exclusive)
                            self.interactive_ui.selected_material = None
                            print(f"✓ Selected shape: {shape_type}")
                            return

                        elif position[0] == 'rotation':
                            # Rotation button clicked
                            rot_delta = position[1]
                            self.interactive_ui.selected_rotation = (self.interactive_ui.selected_rotation + rot_delta) % 360
                            print(f"✓ Rotation: {self.interactive_ui.selected_rotation}°")
                            return

                        elif position[0] == 'delete_shape':
                            # Delete shape button clicked
                            shape_idx = position[1]
                            success = self.interactive_ui.remove_shape(shape_idx)
                            if success:
                                print(f"✓ Deleted shape {shape_idx + 1}")
                                self.add_notification("Shape removed", (200, 200, 200))
                            return

                        # Otherwise it's a grid click for shape placement or vertex material assignment
                        cart_x, cart_y = position

                        # If a shape is selected, try to place the shape
                        if self.interactive_ui.selected_shape_type:
                            success = self.interactive_ui.place_shape(
                                self.interactive_ui.selected_shape_type,
                                cart_x, cart_y,
                                self.interactive_ui.selected_rotation
                            )
                            if success:
                                print(f"✓ Placed shape {self.interactive_ui.selected_shape_type} at ({cart_x},{cart_y})")
                                self.add_notification("Shape placed", (100, 255, 100))
                            else:
                                print(f"✗ Failed to place shape at ({cart_x},{cart_y})")
                                self.add_notification("Cannot place shape there", (255, 100, 100))
                            return

                        # If material is selected and this is a vertex, assign material
                        elif self.interactive_ui.selected_material:
                            success = self.interactive_ui.place_material(position, self.interactive_ui.selected_material)
                            if success:
                                print(f"✓ Assigned {self.interactive_ui.selected_material.item_id} to vertex ({cart_x},{cart_y})")
                                if self.interactive_ui.matched_recipe:
                                    recipe = self.interactive_ui.matched_recipe
                                    print(f"🎯 RECIPE MATCHED: {recipe.recipe_id}")
                                    self.add_notification(f"Recipe Matched!", (100, 255, 100))
                            else:
                                print(f"✗ Cannot assign material to ({cart_x},{cart_y}) - not a vertex")
                                self.add_notification("Not a valid vertex", (255, 100, 100))
                            return

                # Handle normal placement for other disciplines
                elif self.interactive_ui.selected_material:
                    success = self.interactive_ui.place_material(position, self.interactive_ui.selected_material)
                    if success:
                        # Format coordinates based on discipline
                        if self.interactive_ui.station_type == 'smithing':
                            # Smithing uses grid - show 1-indexed "row,col" format
                            x, y = position
                            coord_str = f'"{y+1},{x+1}"'  # row,col = Y,X
                        else:
                            # Other disciplines - show as-is
                            coord_str = str(position)

                        print(f"✓ Placed {self.interactive_ui.selected_material.item_id} at {coord_str}")

                        # Check if recipe matched
                        if self.interactive_ui.matched_recipe:
                            recipe = self.interactive_ui.matched_recipe
                            print(f"🎯 RECIPE MATCHED: {recipe.recipe_id}")
                            self.add_notification(f"Recipe Matched!", (100, 255, 100))
                        else:
                            print("   No recipe matched yet")
                    else:
                        print(f"✗ Failed to place material at {position}")
                        self.add_notification("Cannot place material", (255, 100, 100))
                    return

    def _handle_interactive_craft(self, use_minigame: bool = False):
        """Handle crafting from the interactive UI"""
        if not self.interactive_ui or not self.interactive_ui.matched_recipe:
            self.add_notification("No valid recipe!", (255, 100, 100))
            return

        recipe = self.interactive_ui.matched_recipe

        print(f"\n{'='*80}")
        print(f"🔨 INTERACTIVE CRAFT")
        print(f"Recipe: {recipe.recipe_id}")
        print(f"Output: {recipe.output_id} x{recipe.output_qty}")
        print(f"Station: {recipe.station_type}")
        print(f"Is Enchantment: {recipe.is_enchantment}")
        print(f"Use Minigame: {use_minigame}")
        print(f"{'='*80}")

        # Check if this is an enchantment recipe (adornments)
        if recipe.is_enchantment or recipe.station_type == 'adornments':
            # For enchantments, we need to open item selection UI first
            print("🔮 Enchantment recipe detected - opening item selection UI")

            # Set the flag to control whether to use minigame after item selection
            self.enchantment_use_minigame = use_minigame

            # Close interactive UI but DON'T return borrowed materials yet
            # They'll be consumed after enchantment is applied
            borrowed_backup = self.interactive_ui.borrowed_materials.copy()
            self._close_interactive_crafting()

            # Manually restore borrowed materials to inventory for now
            # They'll be consumed properly when enchantment is applied
            for item_id, quantity in borrowed_backup.items():
                self.character.inventory.add_item(item_id, quantity)

            # Open enchantment selection UI
            self._open_enchantment_selection(recipe)
            return

        # Materials are already borrowed from inventory, so we can proceed directly
        # The borrowed_materials dict tracks what was temporarily removed

        if use_minigame:
            # Start minigame - materials stay borrowed until minigame completes
            print("🎮 Starting minigame...")
            self._start_minigame(recipe)

            # Close interactive UI (materials already consumed/borrowed)
            self._close_interactive_crafting()

        else:
            # Instant craft - use existing instant craft logic
            print("⚡ Instant crafting...")
            self._instant_craft(recipe)

            # Close interactive UI and return remaining materials
            # (instant craft already consumed the required materials via recipe_db)
            # We need to clear the borrowed materials dict to avoid double-return
            self.interactive_ui.borrowed_materials.clear()
            self._close_interactive_crafting()

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

        # Get title bonuses for crafting
        alloy_quality_bonus = 0.0
        if recipe.station_type == 'refining' and hasattr(self.character, 'titles'):
            alloy_quality_bonus = self.character.titles.get_total_bonus('alloyQuality')

        # Use crafter to process minigame result
        craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result, alloy_quality_bonus=alloy_quality_bonus)

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

            new_title = self.character.titles.check_for_title(self.character)
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

                # Apply firstTryBonus if eligible
                first_try_eligible = craft_result.get('first_try_eligible', False)
                if first_try_eligible and hasattr(self.character, 'titles'):
                    first_try_bonus = self.character.titles.get_total_bonus('firstTryBonus')
                    if first_try_bonus > 0 and stats:
                        # Apply bonus to all numeric stats
                        for stat_name, stat_value in stats.items():
                            if isinstance(stat_value, (int, float)):
                                boosted_value = stat_value * (1.0 + first_try_bonus)
                                stats[stat_name] = int(boosted_value) if isinstance(stat_value, int) else boosted_value
                        print(f"   🌟 First-try bonus applied! +{first_try_bonus*100:.0f}% to all stats")

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
        from entities.components.crafted_stats import apply_crafted_stats_to_equipment
        equip_db = EquipmentDatabase.get_instance()

        if equip_db.is_equipment(item_id):
            # Equipment - create with stats if provided
            for i in range(quantity):
                equipment = equip_db.create_equipment_from_id(item_id)
                if equipment and stats:
                    # Apply crafted stats using the crafted_stats system
                    # This properly filters stats by item type and applies to bonuses dict
                    apply_crafted_stats_to_equipment(equipment, stats)

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

            # DISABLED: Material replacement functionality removed in favor of interactive mode
            # Placement slots now only show tooltips (no clicking to add/remove materials)
            # Use "Interactive Mode" button to manually place materials

            # Check for craft buttons
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

            # DEBUG: Log backwards compatibility offset calculation
            print(f"🔍 [PLACEMENT DEBUG] {discipline.upper()} Validation:")
            print(f"   Recipe: {recipe.recipe_id} | Recipe Grid: {recipe_grid_w}x{recipe_grid_h}")
            print(f"   Station Tier: T{self.active_station_tier} | Station Grid: {station_grid_w}x{station_grid_h}")
            print(f"   Offset: ({offset_x}, {offset_y}) | Backwards Compat: {'YES' if recipe_grid_w < station_grid_w else 'NO'}")

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
            # Hub-and-spoke validation with backwards compatibility
            required_core = placement_data.core_inputs
            required_surrounding = placement_data.surrounding_inputs

            # DEBUG: Log refining backwards compatibility
            print(f"🔍 [PLACEMENT DEBUG] REFINING Validation:")
            print(f"   Recipe: {recipe.recipe_id} | Required: {len(required_core)} core + {len(required_surrounding)} surrounding")
            print(f"   Station Tier: T{self.active_station_tier}")

            # Check core slots
            for i, core_input in enumerate(required_core):
                slot_id = f"core_{i}"
                required_mat = core_input.get('itemId') or core_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing core material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong core material: expected {required_mat}, got {user_mat}")

            # Check surrounding slots
            for i, surrounding_input in enumerate(required_surrounding):
                slot_id = f"surrounding_{i}"
                required_mat = surrounding_input.get('itemId') or surrounding_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing surrounding material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong surrounding material: expected {required_mat}, got {user_mat}")

            # BACKWARDS COMPATIBILITY: Only check for extra materials if using all required slots
            # This allows T1 recipes (1 core + 2 surr) to work in T2+ stations (1 core + 4+ surr)
            # Extra slots can be filled but will be ignored by the crafting logic
            expected_slots = set(f"core_{i}" for i in range(len(required_core)))
            expected_slots.update(f"surrounding_{i}" for i in range(len(required_surrounding)))

            # Only enforce "no extra materials" check if this is same-tier crafting
            # For cross-tier (T1 recipe in T2+ station), allow extra materials in unused slots
            recipe_tier = recipe.station_tier
            station_tier = self.active_station_tier

            if recipe_tier == station_tier:
                # Same tier: strict validation (no extra materials)
                for slot_id in user_placement.keys():
                    if slot_id.startswith('core_') or slot_id.startswith('surrounding_'):
                        if slot_id not in expected_slots:
                            return (False, f"Extra material in {slot_id} (not required)")
            else:
                # Cross-tier: permissive validation (allow extra materials, they'll be ignored)
                print(f"   ✅ Backwards Compat: T{recipe_tier} recipe in T{station_tier} station - allowing extra slots")

            return (True, "Refining placement correct!")

        elif discipline == 'alchemy':
            # Sequential validation with backwards compatibility
            required_ingredients = placement_data.ingredients

            # DEBUG: Log alchemy backwards compatibility
            print(f"🔍 [PLACEMENT DEBUG] ALCHEMY Validation:")
            print(f"   Recipe: {recipe.recipe_id} | Required: {len(required_ingredients)} ingredients")
            print(f"   Station Tier: T{self.active_station_tier}")

            # Check each sequential slot
            for ingredient in required_ingredients:
                slot_num = ingredient.get('slot')
                slot_id = f"seq_{slot_num}"
                required_mat = ingredient.get('itemId') or ingredient.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing ingredient in slot {slot_num}: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong ingredient in slot {slot_num}: expected {required_mat}, got {user_mat}")

            # BACKWARDS COMPATIBILITY: Allow extra slots for cross-tier crafting
            # This allows T1 recipes (2-3 ingredients) to work in T2+ stations (4+ slots)
            expected_slots = set(f"seq_{ing.get('slot')}" for ing in required_ingredients)

            # Only enforce "no extra materials" check if this is same-tier crafting
            recipe_tier = recipe.station_tier
            station_tier = self.active_station_tier

            if recipe_tier == station_tier:
                # Same tier: strict validation (no extra materials)
                for slot_id in user_placement.keys():
                    if slot_id.startswith('seq_'):
                        if slot_id not in expected_slots:
                            return (False, f"Extra ingredient in {slot_id} (not required)")
            else:
                # Cross-tier: permissive validation (allow extra materials, they'll be ignored)
                print(f"   ✅ Backwards Compat: T{recipe_tier} recipe in T{station_tier} station - allowing extra slots")

            return (True, "Alchemy sequence correct!")

        elif discipline == 'engineering':
            # Slot-type validation with backwards compatibility
            required_slots = placement_data.slots

            # DEBUG: Log engineering backwards compatibility
            print(f"🔍 [PLACEMENT DEBUG] ENGINEERING Validation:")
            print(f"   Recipe: {recipe.recipe_id} | Required: {len(required_slots)} slots")
            print(f"   Station Tier: T{self.active_station_tier}")

            # Check each slot
            for i, slot_data in enumerate(required_slots):
                slot_id = f"eng_slot_{i}"
                required_mat = slot_data.get('itemId') or slot_data.get('materialId', '')

                if slot_id not in user_placement:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Missing material in {slot_type} slot: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Wrong material in {slot_type} slot: expected {required_mat}, got {user_mat}")

            # BACKWARDS COMPATIBILITY: Allow extra slots for cross-tier crafting
            # This allows T1 recipes (2-3 slots) to work in T2+ stations (4+ slots)
            expected_slots = set(f"eng_slot_{i}" for i in range(len(required_slots)))

            # Only enforce "no extra materials" check if this is same-tier crafting
            recipe_tier = recipe.station_tier
            station_tier = self.active_station_tier

            if recipe_tier == station_tier:
                # Same tier: strict validation (no extra materials)
                for slot_id in user_placement.keys():
                    if slot_id.startswith('eng_slot_'):
                        if slot_id not in expected_slots:
                            return (False, f"Extra material in {slot_id} (not required)")
            else:
                # Cross-tier: permissive validation (allow extra materials, they'll be ignored)
                print(f"   ✅ Backwards Compat: T{recipe_tier} recipe in T{station_tier} station - allowing extra slots")

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

        new_title = self.character.titles.check_for_title(self.character)
        if new_title:
            self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

        self.add_notification(f"Applied {recipe.enchantment_name} to {equipment.name}!", (100, 255, 255))
        self._close_enchantment_selection()

    def _open_enchantment_selection(self, recipe: Recipe):
        """Open the item selection UI for applying enchantment"""
        equip_db = EquipmentDatabase.get_instance()

        # Get ONLY compatible equipment (filter by can_apply_enchantment)
        compatible_items = []

        # From inventory
        for slot_idx, stack in enumerate(self.character.inventory.slots):
            if stack and equip_db.is_equipment(stack.item_id):
                equipment = stack.get_equipment()  # Use actual equipment instance from stack
                if equipment:
                    # FILTER: Only include items that can receive this enchantment
                    can_apply, reason = equipment.can_apply_enchantment(
                        recipe.output_id, recipe.applicable_to, recipe.effect
                    )
                    if can_apply:
                        compatible_items.append(('inventory', slot_idx, stack, equipment))

        # From equipped slots
        for slot_name, equipped_item in self.character.equipment.slots.items():
            if equipped_item:
                # FILTER: Only include items that can receive this enchantment
                can_apply, reason = equipped_item.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append(('equipped', slot_name, None, equipped_item))

        if not compatible_items:
            self.add_notification("No compatible items for this enchantment!", (255, 100, 100))
            print("❌ No compatible items found for enchantment")
            return

        # Open the selection UI with scroll offset
        self.enchantment_selection_active = True
        self.enchantment_recipe = recipe
        self.enchantment_compatible_items = compatible_items
        self.enchantment_scroll_offset = 0  # Initialize scroll offset
        print(f"✨ Opened enchantment selection UI ({len(compatible_items)} compatible items)")

    def _close_enchantment_selection(self):
        """Close the enchantment selection UI"""
        self.enchantment_selection_active = False
        self.enchantment_recipe = None
        self.enchantment_compatible_items = []
        self.enchantment_selection_rect = None
        self.enchantment_scroll_offset = 0

    def handle_mouse_release(self, mouse_pos: Tuple[int, int]):
        # Skip if no character exists yet (e.g., still in start menu)
        if self.character is None:
            return

        if self.character.inventory.dragging_stack:
            if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
                # Calculate start_y to match renderer: tools_y(+55) + tool_slot(50) + padding(20) = +125
                tools_y = Config.INVENTORY_PANEL_Y + 55
                start_x, start_y = 20, tools_y + 50 + 20  # = INVENTORY_PANEL_Y + 125
                slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10  # Must match renderer spacing
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

        # Update playtime tracking
        if hasattr(self.character, 'stat_tracker'):
            self.character.stat_tracker.update_playtime(dt)

        if not self.character.class_selection_open:
            # Calculate effective movement speed with encumbrance penalty
            base_speed = self.character.movement_speed
            encumbrance_mult = self.character.get_encumbrance_speed_penalty()
            effective_speed = base_speed * encumbrance_mult

            # Warn if over-encumbered
            if encumbrance_mult <= 0:
                # Can't move at all - 50% or more over capacity
                if any(k in self.keys_pressed for k in [pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d]):
                    if not hasattr(self, '_last_encumbered_warning') or curr - self._last_encumbered_warning > 2000:
                        self.add_notification("Too encumbered to move!", (255, 100, 100))
                        self._last_encumbered_warning = curr
                effective_speed = 0

            dx = dy = 0
            if pygame.K_w in self.keys_pressed:
                dy -= effective_speed
            if pygame.K_s in self.keys_pressed:
                dy += effective_speed
            if pygame.K_a in self.keys_pressed:
                dx -= effective_speed
            if pygame.K_d in self.keys_pressed:
                dx += effective_speed

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
            self.character.update_knockback(dt, self.world)

            # Update turret system
            self.turret_system.update(self.world.placed_entities, self.combat_manager, dt)
        else:
            # Update active minigame
            # Skip update while metadata overlay is blocking
            effects = get_effects_manager()
            if not effects.metadata_overlay.is_blocking():
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
            self.renderer.render_debug_messages()
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
        self.renderer.render_debug_messages()

        if self.character.class_selection_open:
            result = self.renderer.render_class_selection_ui(self.character, self.mouse_pos)
            if result:
                self.class_selection_rect, self.class_buttons = result
        else:
            self.class_selection_rect = None
            self.class_buttons = []

            if self.interactive_crafting_active and self.interactive_ui:
                # Interactive crafting UI (priority over regular crafting UI)
                result = self.renderer.render_interactive_crafting_ui(
                    self.character, self.interactive_ui, self.mouse_pos
                )
                if result:
                    # Extract click regions from result dict
                    self.crafting_window_rect = result['window_rect']
                    self.interactive_material_rects = result['material_rects']
                    self.interactive_placement_rects = result['placement_rects']
                    self.interactive_button_rects = result['button_rects']
                else:
                    self.crafting_window_rect = None
                    self.interactive_material_rects = []
                    self.interactive_placement_rects = []
                    self.interactive_button_rects = {}

            elif self.character.crafting_ui_open:
                # Regular crafting UI
                # Pass scroll offset via temporary attribute (renderer doesn't have direct access to game state)
                self.renderer._temp_scroll_offset = self.recipe_scroll_offset
                result = self.renderer.render_crafting_ui(self.character, self.mouse_pos, self.selected_recipe, self.user_placement, self.active_minigame is not None)
                if result:
                    # Unpack with 4 values (added interactive_button_rect)
                    self.crafting_window_rect, self.crafting_recipes, self.placement_grid_rects, self.interactive_button_rect = result
                else:
                    self.crafting_window_rect = None
                    self.crafting_recipes = []
                    self.interactive_button_rect = None
            else:
                self.crafting_window_rect = None
                self.crafting_recipes = []
                self.interactive_button_rect = None

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
                scroll_offset = getattr(self, 'enchantment_scroll_offset', 0)
                result = self.renderer.render_enchantment_selection_ui(
                    self.mouse_pos, self.enchantment_recipe, self.enchantment_compatible_items, scroll_offset)
                if result:
                    self.enchantment_selection_rect, self.enchantment_item_rects = result
            else:
                self.enchantment_selection_rect = None
                self.enchantment_item_rects = None

        # Minigame rendering (rendered on top of EVERYTHING)
        if self.active_minigame:
            self._render_minigame()

        # Render deferred tooltips LAST (on top of all UI including modals)
        self.renderer.render_pending_tooltip()

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
            print(f"⚠ Consuming materials after FAILURE")
            consumed = recipe_db.consume_materials(recipe, self.character.inventory)
            print(f"   Consumed: {consumed}")

            # NEW: Track failed crafting attempts
            if hasattr(self.character, 'stat_tracker'):
                activity_map = {
                    'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                    'engineering': 'engineering', 'adornments': 'enchanting'
                }
                activity_type = activity_map.get(self.minigame_type, 'smithing')

                # Collect materials consumed
                materials_consumed = {}
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId') or inp.get('itemId')
                    qty = inp.get('quantity', 1)
                    if mat_id:
                        materials_consumed[mat_id] = qty

                # Record failed craft
                self.character.stat_tracker.record_crafting(
                    recipe_id=recipe.recipe_id,
                    discipline=activity_type,
                    success=False,
                    tier=recipe.station_tier,
                    materials=materials_consumed
                )
        else:
            # Success - consume materials and add output
            print(f"✅ Consuming materials after SUCCESS")
            consumed = recipe_db.consume_materials(recipe, self.character.inventory)
            print(f"   Consumed: {consumed}")

            # Record activity and XP
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(self.minigame_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            # NEW: Comprehensive crafting stat tracking
            if hasattr(self.character, 'stat_tracker'):
                # Extract minigame result data
                quality_score = getattr(result, 'bonus_percentage', 0.0) if result else 0.0
                craft_time = getattr(self.active_minigame, 'elapsed_time', 0.0) if self.active_minigame else 0.0
                output_rarity = craft_result.get('rarity', 'common')
                is_perfect = craft_result.get('is_perfect', False)
                is_first_try = craft_result.get('is_first_try', False)

                # Collect materials consumed from recipe
                materials_consumed = {}
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId') or inp.get('itemId')
                    qty = inp.get('quantity', 1)
                    if mat_id:
                        materials_consumed[mat_id] = qty

                # Record comprehensive crafting stats
                self.character.stat_tracker.record_crafting(
                    recipe_id=recipe.recipe_id,
                    discipline=activity_type,
                    success=True,
                    tier=recipe.station_tier,
                    quality_score=quality_score,
                    craft_time=craft_time,
                    output_rarity=output_rarity,
                    is_perfect=is_perfect,
                    is_first_try=is_first_try,
                    materials=materials_consumed
                )

            # Extra XP for minigame (50% bonus)
            xp_reward = int(20 * recipe.station_tier * 1.5)
            leveled_up = self.character.leveling.add_exp(xp_reward)
            if leveled_up:
                self.character.check_and_notify_new_skills()

            new_title = self.character.titles.check_for_title(self.character)
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))
                self.character.check_skill_unlocks(trigger_type='title_earned', trigger_value=new_title.title_id)

            # Check for activity-based skill unlocks
            self.character.check_skill_unlocks(trigger_type='activity_threshold')

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
                rarity = craft_result.get('rarity') or 'common'  # Ensure not None
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

            # IMPORTANT: Consume crafting buffs after successful craft
            # This includes skills like Smith's Focus, Alchemist's Insight, Engineer's Precision, etc.
            if hasattr(self.character, 'buffs'):
                self.character.buffs.consume_buffs_for_action("craft", category=activity_type)
                print(f"   ⚡ Consumed {activity_type} crafting buffs")

        # Clear minigame state
        self.active_minigame = None
        self.minigame_type = None
        self.minigame_recipe = None

    def _render_smithing_minigame(self):
        """Render smithing minigame UI with enhanced forge/anvil aesthetic"""
        state = self.active_minigame.get_state()
        effects = get_effects_manager()

        # Create overlay
        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        # Initialize effects if needed
        if not hasattr(self, '_smithing_effects_initialized') or not self._smithing_effects_initialized:
            effects.initialize_discipline('smithing', pygame.Rect(wx, wy, ww, wh))
            self._smithing_effects_initialized = True
            self._smithing_metal_progress = 0.0
            self._smithing_last_hit_time = 0
            self._smithing_sparks_active = False
            # Show metadata overlay
            difficulty_tier = getattr(self.active_minigame, 'difficulty_tier', 'Unknown')
            difficulty_points = getattr(self.active_minigame, 'difficulty_points', 0)
            effects.show_metadata({
                'discipline': 'Smithing',
                'difficulty_tier': difficulty_tier,
                'difficulty_points': difficulty_points,
                'time_limit': state.get('time_limit', 60),
                'max_bonus': 1.0 + difficulty_points * 0.015,
                'special_params': {
                    'Required Strikes': state.get('required_hits', 5),
                    'Temperature Range': f"{state.get('temp_ideal_min', 60)}-{state.get('temp_ideal_max', 80)}°C"
                }
            })

        # Update effects
        dt = 1/60  # Approximate delta time
        effects.update(dt)

        # Update metal progress based on hits
        if state['hammer_hits'] > 0:
            self._smithing_metal_progress = min(1.0, state['hammer_hits'] / state['required_hits'])

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)

        # Enhanced forge gradient background
        for y in range(wh):
            progress = y / wh
            # Darker at top, warm glow at bottom
            r = int(25 + 55 * progress * progress)
            g = int(15 + 25 * progress * progress)
            b = int(20 - 15 * progress)
            pygame.draw.line(surf, (max(0, r), max(0, g), max(0, b)), (0, y), (ww, y))

        # Forge glow at bottom
        tick = pygame.time.get_ticks()
        glow_intensity = 0.7 + 0.3 * math.sin(tick * 0.003)
        for y in range(150):
            alpha = int(80 * (1 - y / 150) * glow_intensity)
            glow_color = (255, 100 + int(50 * glow_intensity), 20, alpha)
            glow_surf = pygame.Surface((ww, 1), pygame.SRCALPHA)
            glow_surf.fill(glow_color)
            surf.blit(glow_surf, (0, wh - 150 + y))

        # Animated flames at bottom
        flame_base_y = wh - 30
        for i in range(16):
            flame_x = 30 + i * 60
            flame_phase = tick * 0.008 + i * 0.7
            flame_height = 40 + 25 * math.sin(flame_phase) + 15 * math.sin(flame_phase * 2.3)

            # Multi-layer flames
            for layer in range(3):
                layer_height = flame_height * (1 - layer * 0.25)
                layer_width = 25 - layer * 5

                if state['temperature'] > 70:
                    colors = [(255, 240, 180), (255, 180, 50), (255, 100, 20)]
                elif state['temperature'] > 50:
                    colors = [(255, 200, 100), (255, 140, 30), (200, 60, 10)]
                else:
                    colors = [(100, 120, 200), (60, 80, 180), (40, 50, 120)]

                flame_points = [
                    (flame_x - layer_width//2, flame_base_y),
                    (flame_x - layer_width//4, flame_base_y - layer_height * 0.5),
                    (flame_x, flame_base_y - layer_height),
                    (flame_x + layer_width//4, flame_base_y - layer_height * 0.6),
                    (flame_x + layer_width//2, flame_base_y),
                ]
                pygame.draw.polygon(surf, colors[layer], flame_points)

        # Animated ember particles
        for i in range(20):
            ember_phase = tick * 0.002 + i * 1.3
            ember_x = 50 + (i * 47 + int(tick * 0.05)) % (ww - 100)
            ember_y = wh - 80 - (int(tick * 0.03 + i * 17) % 250)
            ember_size = 2 + int(2 * math.sin(ember_phase))
            ember_alpha = int(150 + 80 * math.sin(ember_phase * 1.5))
            ember_alpha = max(50, min(230, ember_alpha))

            ember_surf = pygame.Surface((ember_size * 3, ember_size * 3), pygame.SRCALPHA)
            # Glow
            pygame.draw.circle(ember_surf, (255, 150, 50, ember_alpha // 3),
                             (ember_size * 1.5, ember_size * 1.5), ember_size * 1.5)
            # Core
            pygame.draw.circle(ember_surf, (255, 200, 100, ember_alpha),
                             (ember_size * 1.5, ember_size * 1.5), ember_size)
            surf.blit(ember_surf, (int(ember_x), int(ember_y)))

        # Header with forge theme
        header_surf = self.renderer.font.render("FORGE", True, (255, 200, 100))
        surf.blit(header_surf, (ww//2 - header_surf.get_width()//2, 15))
        sub_header = self.renderer.small_font.render("Shape the metal with precise strikes", True, (180, 160, 140))
        surf.blit(sub_header, (ww//2 - sub_header.get_width()//2, 45))

        # Temperature display with enhanced forge visualization
        temp_x, temp_y = 50, 85
        temp_width = 100
        temp_height = 180

        temp = state['temperature']
        ideal_min = state['temp_ideal_min']
        ideal_max = state['temp_ideal_max']
        in_ideal = ideal_min <= temp <= ideal_max

        # Forge container with brick texture
        for row in range(12):
            for col in range(4):
                brick_x = temp_x - 8 + col * 30
                brick_y = temp_y - 8 + row * 17
                brick_color = (90 + (row + col) % 3 * 10, 45 + (row * col) % 15, 30)
                pygame.draw.rect(surf, brick_color, (brick_x, brick_y, 28, 15))
                pygame.draw.rect(surf, (60, 30, 20), (brick_x, brick_y, 28, 15), 1)

        # Inner furnace (dark)
        pygame.draw.rect(surf, (30, 20, 15), (temp_x, temp_y, temp_width, temp_height))

        # Flame visualization with temperature-based colors
        flame_height = int((temp / 100) * temp_height * 0.9)

        for layer in range(4):
            wave = math.sin(tick / 150 + layer * 0.8) * 6
            layer_width = temp_width - layer * 15
            layer_x = temp_x + layer * 7

            # Flame color palette based on temperature
            if temp > 85:
                colors = [(255, 255, 240), (255, 240, 180), (255, 200, 100), (255, 150, 50)]
            elif temp > 70:
                colors = [(255, 220, 150), (255, 180, 80), (255, 130, 40), (220, 80, 20)]
            elif temp > 50:
                colors = [(255, 180, 80), (255, 130, 40), (220, 80, 20), (180, 50, 10)]
            elif temp > 30:
                colors = [(255, 120, 40), (200, 70, 20), (150, 40, 10), (100, 30, 10)]
            else:
                colors = [(80, 100, 180), (60, 80, 150), (40, 60, 120), (30, 40, 90)]

            color = colors[layer]

            if flame_height > 15:
                points = [
                    (layer_x, temp_y + temp_height),
                    (layer_x + layer_width * 0.2, temp_y + temp_height - flame_height * 0.5 + wave),
                    (layer_x + layer_width * 0.4, temp_y + temp_height - flame_height * 0.8 - wave * 0.5),
                    (layer_x + layer_width * 0.5, temp_y + temp_height - flame_height),
                    (layer_x + layer_width * 0.6, temp_y + temp_height - flame_height * 0.85 + wave * 0.3),
                    (layer_x + layer_width * 0.8, temp_y + temp_height - flame_height * 0.55 - wave),
                    (layer_x + layer_width, temp_y + temp_height),
                ]
                pygame.draw.polygon(surf, color, points)

        # Ideal range markers with glow when in range
        ideal_y_min = temp_y + temp_height - int((ideal_min / 100) * temp_height)
        ideal_y_max = temp_y + temp_height - int((ideal_max / 100) * temp_height)

        if in_ideal:
            # Draw glow band for ideal zone
            zone_surf = pygame.Surface((temp_width + 30, ideal_y_min - ideal_y_max + 10), pygame.SRCALPHA)
            zone_surf.fill((100, 255, 100, 40))
            surf.blit(zone_surf, (temp_x - 15, ideal_y_max - 5))

        mark_color = (100, 255, 100) if in_ideal else (180, 180, 180)
        pygame.draw.line(surf, mark_color, (temp_x - 15, ideal_y_min), (temp_x - 3, ideal_y_min), 3)
        pygame.draw.line(surf, mark_color, (temp_x - 15, ideal_y_max), (temp_x - 3, ideal_y_max), 3)
        pygame.draw.line(surf, mark_color, (temp_x + temp_width + 3, ideal_y_min), (temp_x + temp_width + 15, ideal_y_min), 3)
        pygame.draw.line(surf, mark_color, (temp_x + temp_width + 3, ideal_y_max), (temp_x + temp_width + 15, ideal_y_max), 3)

        # Temperature label
        label_color = (100, 255, 100) if in_ideal else (255, 200, 150)
        temp_label = self.renderer.small_font.render(f"{int(temp)}°C", True, label_color)
        surf.blit(temp_label, (temp_x + temp_width//2 - temp_label.get_width()//2, temp_y - 22))

        status_text = "IDEAL" if in_ideal else ("TOO HOT" if temp > ideal_max else "TOO COLD")
        status_color = (100, 255, 100) if in_ideal else ((255, 100, 100) if temp > ideal_max else (100, 150, 255))
        status_label = self.renderer.tiny_font.render(status_text, True, status_color)
        surf.blit(status_label, (temp_x + temp_width//2 - status_label.get_width()//2, temp_y + temp_height + 8))

        # Fan flames instruction
        fan_label = self.renderer.tiny_font.render("[SPACE] Fan", True, (180, 160, 140))
        surf.blit(fan_label, (temp_x + temp_width//2 - fan_label.get_width()//2, temp_y + temp_height + 25))

        # Enhanced Anvil and Metal display
        anvil_x, anvil_y = 200, 130
        anvil_width = 500
        anvil_height = 80

        # Draw anvil base (3D effect)
        anvil_dark = (50, 50, 60)
        anvil_mid = (70, 70, 80)
        anvil_light = (90, 90, 100)
        anvil_highlight = (120, 120, 130)

        # Anvil shadow
        pygame.draw.ellipse(surf, (20, 15, 15), (anvil_x + 20, anvil_y + anvil_height + 5, anvil_width - 40, 20))

        # Anvil body (main surface)
        anvil_body = [
            (anvil_x + 30, anvil_y + 10),
            (anvil_x + anvil_width - 30, anvil_y + 10),
            (anvil_x + anvil_width - 10, anvil_y + anvil_height),
            (anvil_x + 10, anvil_y + anvil_height),
        ]
        pygame.draw.polygon(surf, anvil_mid, anvil_body)

        # Anvil top surface (lighter)
        anvil_top = [
            (anvil_x + 30, anvil_y + 10),
            (anvil_x + anvil_width - 30, anvil_y + 10),
            (anvil_x + anvil_width - 50, anvil_y + 25),
            (anvil_x + 50, anvil_y + 25),
        ]
        pygame.draw.polygon(surf, anvil_light, anvil_top)
        pygame.draw.polygon(surf, anvil_highlight, anvil_body, 2)

        # Horn on left side
        horn_points = [(anvil_x + 30, anvil_y + 35), (anvil_x - 20, anvil_y + 45), (anvil_x + 30, anvil_y + 55)]
        pygame.draw.polygon(surf, anvil_mid, horn_points)
        pygame.draw.polygon(surf, anvil_highlight, horn_points, 2)

        # Metal workpiece on anvil (transforms based on progress)
        metal_x = anvil_x + anvil_width // 2
        metal_y = anvil_y + 5
        progress = self._smithing_metal_progress

        # Metal color based on temperature
        if temp > 80:
            metal_color = (255, 230, 180)  # White-hot
            metal_glow = (255, 200, 100, 100)
        elif temp > 60:
            metal_color = (255, 160, 80)   # Orange-hot
            metal_glow = (255, 120, 50, 80)
        elif temp > 40:
            metal_color = (200, 80, 50)    # Red-hot
            metal_glow = (200, 50, 30, 60)
        else:
            metal_color = (100, 100, 110)  # Cold metal
            metal_glow = None

        # Metal shape transforms from ingot to elongated shape
        base_width = 60
        base_height = 25
        # As progress increases, metal gets longer and thinner
        metal_width = int(base_width + progress * 120)
        metal_height = int(base_height - progress * 10)

        metal_rect = pygame.Rect(metal_x - metal_width//2, metal_y, metal_width, max(12, metal_height))

        # Draw glow if hot
        if metal_glow:
            glow_surf = pygame.Surface((metal_width + 30, metal_height + 30), pygame.SRCALPHA)
            pygame.draw.ellipse(glow_surf, metal_glow, (0, 0, metal_width + 30, metal_height + 30))
            surf.blit(glow_surf, (metal_rect.x - 15, metal_rect.y - 15))

        # Draw metal
        pygame.draw.rect(surf, metal_color, metal_rect, border_radius=3)
        # Highlight on top
        highlight_color = lerp_color(metal_color, (255, 255, 255), 0.3)
        highlight_rect = pygame.Rect(metal_rect.x + 3, metal_rect.y + 2, metal_rect.width - 6, metal_rect.height // 3)
        pygame.draw.rect(surf, highlight_color, highlight_rect, border_radius=2)

        # Target zones on anvil - scale from game bar width to visual anvil width
        hammer_bar_width_for_zones = state.get('hammer_bar_width', 400)
        scale_factor = anvil_width / hammer_bar_width_for_zones
        center = anvil_width / 2
        target_w = state['target_width'] * scale_factor
        perfect_w = state['perfect_width'] * scale_factor
        target_x = anvil_x + int(center - target_w / 2)
        perfect_x = anvil_x + int(center - perfect_w / 2)

        # Target zone indicator (subtle lines)
        pygame.draw.line(surf, (100, 100, 60, 150), (target_x, anvil_y + 30), (target_x, anvil_y + anvil_height - 10), 2)
        pygame.draw.line(surf, (100, 100, 60, 150), (target_x + int(target_w), anvil_y + 30), (target_x + int(target_w), anvil_y + anvil_height - 10), 2)

        # Perfect zone indicator
        pygame.draw.line(surf, (150, 200, 80), (perfect_x, anvil_y + 30), (perfect_x, anvil_y + anvil_height - 10), 3)
        pygame.draw.line(surf, (150, 200, 80), (perfect_x + int(perfect_w), anvil_y + 30), (perfect_x + int(perfect_w), anvil_y + anvil_height - 10), 3)

        # Hammer indicator - scale to visual anvil width
        hammer_bar_width = state.get('hammer_bar_width', 400)
        hammer_pos_scaled = int(state['hammer_position'] * anvil_width / hammer_bar_width)
        hammer_head_x = anvil_x + hammer_pos_scaled
        hammer_head_y = anvil_y - 55

        # Hammer oscillation animation
        hammer_bob = math.sin(tick * 0.015) * 3

        # Hammer head (3D effect)
        head_width, head_height = 40, 30
        pygame.draw.rect(surf, (50, 45, 45), (hammer_head_x - head_width//2 + 2, hammer_head_y + hammer_bob + 2, head_width, head_height))
        pygame.draw.rect(surf, (80, 75, 70), (hammer_head_x - head_width//2, hammer_head_y + hammer_bob, head_width, head_height))
        pygame.draw.rect(surf, (100, 95, 85), (hammer_head_x - head_width//2, hammer_head_y + hammer_bob, head_width, head_height // 3))
        pygame.draw.rect(surf, (60, 55, 50), (hammer_head_x - head_width//2, hammer_head_y + hammer_bob, head_width, head_height), 2)

        # Hammer handle
        pygame.draw.rect(surf, (120, 80, 50), (hammer_head_x - 6, hammer_head_y + head_height + hammer_bob, 12, 40))
        pygame.draw.rect(surf, (100, 65, 40), (hammer_head_x - 6, hammer_head_y + head_height + hammer_bob, 12, 40), 1)

        # Impact indicator line
        pygame.draw.line(surf, (255, 255, 200, 100), (hammer_head_x, hammer_head_y + head_height + hammer_bob), (hammer_head_x, anvil_y + 30), 1)

        # Strike counter with progress bar
        strikes_x = anvil_x
        strikes_y = anvil_y - 30
        strikes_label = self.renderer.small_font.render(f"Strikes: {state['hammer_hits']}/{state['required_hits']}", True, (255, 220, 180))
        surf.blit(strikes_label, (strikes_x, strikes_y))

        # Progress bar for strikes
        prog_width = 150
        prog_height = 8
        prog_x = strikes_x + strikes_label.get_width() + 15
        pygame.draw.rect(surf, (40, 35, 30), (prog_x, strikes_y + 5, prog_width, prog_height), border_radius=3)
        fill_width = int(prog_width * progress)
        if fill_width > 0:
            prog_color = (255, 200, 100) if progress < 1 else (100, 255, 100)
            pygame.draw.rect(surf, prog_color, (prog_x, strikes_y + 5, fill_width, prog_height), border_radius=3)
        pygame.draw.rect(surf, (100, 90, 80), (prog_x, strikes_y + 5, prog_width, prog_height), 1, border_radius=3)

        # Strike button (styled to match forge theme)
        btn_w, btn_h = 180, 55
        btn_x, btn_y = anvil_x + anvil_width // 2 - btn_w // 2, 230
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        # Button with metallic style
        pygame.draw.rect(surf, (60, 45, 25), (btn_x + 3, btn_y + 3, btn_w, btn_h), border_radius=8)
        pygame.draw.rect(surf, (100, 75, 40), btn_rect, border_radius=8)
        pygame.draw.rect(surf, (130, 100, 60), (btn_x, btn_y, btn_w, btn_h // 3), border_radius=8)
        pygame.draw.rect(surf, (255, 200, 100), btn_rect, 3, border_radius=8)

        strike_text = self.renderer.font.render("STRIKE", True, (255, 220, 150))
        surf.blit(strike_text, (btn_x + btn_w//2 - strike_text.get_width()//2, btn_y + btn_h//2 - strike_text.get_height()//2))

        # Timer display (bottom left panel)
        timer_panel_x, timer_panel_y = 50, 320
        timer_panel_w, timer_panel_h = 140, 80

        pygame.draw.rect(surf, (40, 30, 25), (timer_panel_x, timer_panel_y, timer_panel_w, timer_panel_h), border_radius=8)
        pygame.draw.rect(surf, (80, 60, 45), (timer_panel_x, timer_panel_y, timer_panel_w, timer_panel_h), 2, border_radius=8)

        time_left = int(state['time_left'])
        if time_left < 10:
            time_color = (255, 80, 80)
            pulse = 1 + 0.1 * math.sin(tick * 0.02)
        elif time_left < 20:
            time_color = (255, 200, 100)
            pulse = 1
        else:
            time_color = (200, 200, 200)
            pulse = 1

        time_label = self.renderer.tiny_font.render("TIME", True, (150, 130, 110))
        surf.blit(time_label, (timer_panel_x + timer_panel_w//2 - time_label.get_width()//2, timer_panel_y + 8))

        time_value = self.renderer.font.render(f"{time_left}s", True, time_color)
        surf.blit(time_value, (timer_panel_x + timer_panel_w//2 - time_value.get_width()//2, timer_panel_y + 30))

        # Strike quality panel (right side)
        quality_panel_x, quality_panel_y = 750, 100
        quality_panel_w, quality_panel_h = 220, 200

        pygame.draw.rect(surf, (35, 30, 28), (quality_panel_x, quality_panel_y, quality_panel_w, quality_panel_h), border_radius=8)
        pygame.draw.rect(surf, (70, 55, 45), (quality_panel_x, quality_panel_y, quality_panel_w, quality_panel_h), 2, border_radius=8)

        quality_title = self.renderer.small_font.render("Strike Quality", True, (200, 180, 150))
        surf.blit(quality_title, (quality_panel_x + quality_panel_w//2 - quality_title.get_width()//2, quality_panel_y + 10))

        if state['hammer_scores']:
            for i, score in enumerate(state['hammer_scores'][-6:]):
                y_pos = quality_panel_y + 40 + i * 25
                if score >= 90:
                    color = (255, 215, 100)
                    quality = "PERFECT"
                    bar_color = (255, 200, 50)
                elif score >= 70:
                    color = (100, 255, 100)
                    quality = "Good"
                    bar_color = (100, 200, 80)
                elif score >= 50:
                    color = (200, 200, 100)
                    quality = "Fair"
                    bar_color = (180, 180, 80)
                else:
                    color = (150, 100, 100)
                    quality = "Miss"
                    bar_color = (150, 80, 80)

                # Score bar
                bar_width = int((score / 100) * 100)
                pygame.draw.rect(surf, (50, 45, 40), (quality_panel_x + 15, y_pos, 100, 12), border_radius=3)
                pygame.draw.rect(surf, bar_color, (quality_panel_x + 15, y_pos, bar_width, 12), border_radius=3)

                # Quality text
                qual_text = self.renderer.tiny_font.render(quality, True, color)
                surf.blit(qual_text, (quality_panel_x + 125, y_pos - 2))

        # Result (if completed)
        if state['result']:
            result = state['result']
            result_w, result_h = 550, 320
            result_x, result_y = ww//2 - result_w//2, wh//2 - result_h//2

            result_surf = pygame.Surface((result_w, result_h), pygame.SRCALPHA)

            # Background with forge theme
            pygame.draw.rect(result_surf, (25, 20, 18, 245), (0, 0, result_w, result_h), border_radius=12)
            pygame.draw.rect(result_surf, (100, 75, 50), (0, 0, result_w, result_h), 4, border_radius=12)

            if result['success']:
                # Success header with warm glow
                header_text = "FORGING COMPLETE"
                header_surf = self.renderer.font.render(header_text, True, (100, 255, 100))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 25))

                # Decorative line
                pygame.draw.line(result_surf, (100, 80, 60), (50, 60), (result_w - 50, 60), 2)

                # Quality tier display with special styling
                quality = result.get('quality_tier', 'Normal')
                quality_colors = {
                    'Normal': (180, 180, 180),
                    'Fine': (100, 220, 100),
                    'Superior': (100, 160, 255),
                    'Masterwork': (220, 100, 255),
                    'Legendary': (255, 215, 50)
                }
                q_color = quality_colors.get(quality, (200, 200, 200))

                quality_label = self.renderer.small_font.render("Quality:", True, (180, 160, 140))
                result_surf.blit(quality_label, (60, 85))
                quality_value = self.renderer.font.render(quality, True, q_color)
                result_surf.blit(quality_value, (160, 80))

                # Performance stats
                score = int(result.get('score', 0))
                perf_label = self.renderer.small_font.render("Performance:", True, (180, 160, 140))
                result_surf.blit(perf_label, (60, 125))

                # Performance bar
                bar_x, bar_y, bar_w, bar_h = 180, 128, 200, 16
                pygame.draw.rect(result_surf, (50, 45, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
                fill_w = int(bar_w * score / 100)
                perf_color = (100, 255, 100) if score >= 80 else ((255, 200, 100) if score >= 50 else (255, 100, 100))
                pygame.draw.rect(result_surf, perf_color, (bar_x, bar_y, fill_w, bar_h), border_radius=4)
                score_text = self.renderer.small_font.render(f"{score}%", True, (255, 255, 255))
                result_surf.blit(score_text, (bar_x + bar_w + 15, bar_y - 2))

                # Stat bonus
                bonus = result.get('bonus', result.get('bonus_pct', 0))
                bonus_label = self.renderer.small_font.render("Stat Bonus:", True, (180, 160, 140))
                result_surf.blit(bonus_label, (60, 165))
                bonus_value = self.renderer.font.render(f"+{bonus}%", True, (255, 200, 100))
                result_surf.blit(bonus_value, (180, 160))

                # First-try bonus
                if result.get('first_try_bonus_applied'):
                    ftb_surf = pygame.Surface((result_w - 80, 30), pygame.SRCALPHA)
                    ftb_surf.fill((255, 180, 100, 40))
                    result_surf.blit(ftb_surf, (40, 205))
                    ftb_text = self.renderer.small_font.render("First-Try Bonus Applied! (+10%)", True, (255, 200, 150))
                    result_surf.blit(ftb_text, (result_w//2 - ftb_text.get_width()//2, 210))

                # Message
                msg = result.get('message', 'Item crafted successfully!')
                msg_text = self.renderer.small_font.render(msg, True, (200, 180, 160))
                result_surf.blit(msg_text, (result_w//2 - msg_text.get_width()//2, 255))

            else:
                # Failure header
                header_text = "FORGING FAILED"
                header_surf = self.renderer.font.render(header_text, True, (255, 100, 100))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 35))

                pygame.draw.line(result_surf, (100, 60, 50), (50, 75), (result_w - 50, 75), 2)

                # Material loss
                loss_pct = result.get('loss_percentage', 50)
                loss_label = self.renderer.small_font.render("Materials Lost:", True, (200, 160, 140))
                result_surf.blit(loss_label, (60, 110))
                loss_value = self.renderer.font.render(f"{loss_pct}%", True, (255, 120, 100))
                result_surf.blit(loss_value, (220, 105))

                # Message
                msg = result.get('message', 'The forging process failed.')
                msg_text = self.renderer.small_font.render(msg, True, (200, 180, 160))
                result_surf.blit(msg_text, (result_w//2 - msg_text.get_width()//2, 180))

            # Close hint
            close_text = self.renderer.tiny_font.render("Press any key to continue", True, (140, 120, 100))
            result_surf.blit(close_text, (result_w//2 - close_text.get_width()//2, result_h - 30))

            surf.blit(result_surf, (result_x, result_y))

        # Draw metadata overlay if active
        effects.metadata_overlay.draw(surf, (ww//2, wh//2), self.renderer.small_font)

        self.screen.blit(surf, (wx, wy))

        # Store button rect for click detection (relative to screen)
        self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

        # Reset effects when minigame ends
        if state['result']:
            self._smithing_effects_initialized = False

    def _render_alchemy_minigame(self):
        """Render alchemy minigame UI with lab/wizard tower aesthetic"""
        state = self.active_minigame.get_state()
        effects = get_effects_manager()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        # Initialize effects if needed
        if not hasattr(self, '_alchemy_effects_initialized') or not self._alchemy_effects_initialized:
            effects.initialize_discipline('alchemy', pygame.Rect(wx, wy, ww, wh))
            self._alchemy_effects_initialized = True
            self._alchemy_bubbles = []
            self._alchemy_steam = []
            # Show metadata overlay
            difficulty_tier = getattr(self.active_minigame, 'difficulty_tier', 'Unknown')
            difficulty_points = getattr(self.active_minigame, 'difficulty_points', 0)
            effects.show_metadata({
                'discipline': 'Alchemy',
                'difficulty_tier': difficulty_tier,
                'difficulty_points': difficulty_points,
                'time_limit': state.get('time_limit', 90),
                'max_bonus': 1.0 + difficulty_points * 0.018,
                'special_params': {
                    'Ingredients': state.get('total_ingredients', 3),
                    'Volatility': getattr(self.active_minigame, 'volatility', 'Normal')
                }
            })

        dt = 1/60
        effects.update(dt)
        tick = pygame.time.get_ticks()

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)

        # Clean lab-style gradient background (light professional)
        for y in range(wh):
            progress = y / wh
            r = int(240 - 30 * progress)
            g = int(245 - 25 * progress)
            b = int(250 - 20 * progress)
            pygame.draw.line(surf, (r, g, b), (0, y), (ww, y))

        # Wood paneling at bottom (lab workbench)
        wood_y = wh - 120
        pygame.draw.rect(surf, (120, 85, 55), (0, wood_y, ww, 120))
        for i in range(8):
            line_y = wood_y + 15 + i * 14
            pygame.draw.line(surf, (100, 70, 45), (0, line_y), (ww, line_y), 1)
        pygame.draw.rect(surf, (90, 65, 40), (0, wood_y, ww, 8))

        # Lab shelves on left with bottles
        shelf_y = 100
        pygame.draw.rect(surf, (100, 75, 50), (30, shelf_y, 150, 12))
        pygame.draw.rect(surf, (80, 60, 40), (30, shelf_y + 8, 150, 4))

        # Decorative bottles on shelf
        bottle_positions = [(50, shelf_y - 35, (100, 200, 150)), (90, shelf_y - 30, (180, 120, 200)),
                          (130, shelf_y - 40, (200, 180, 100))]
        for bx, by, bcolor in bottle_positions:
            pygame.draw.rect(surf, bcolor, (bx, by, 20, 35), border_radius=3)
            pygame.draw.rect(surf, (80, 80, 90), (bx + 5, by - 8, 10, 10))

        # Second shelf
        pygame.draw.rect(surf, (100, 75, 50), (30, shelf_y + 80, 150, 12))

        # Mystical elements - floating runes on right side
        for i in range(5):
            rune_x = ww - 100 + math.sin(tick * 0.001 + i) * 30
            rune_y = 150 + i * 70 + math.cos(tick * 0.0015 + i * 0.5) * 20
            rune_alpha = int(100 + 50 * math.sin(tick * 0.003 + i))
            rune_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(rune_surf, (100, 180, 150, rune_alpha), (15, 15), 12, 2)
            # Simple rune symbol
            pygame.draw.line(rune_surf, (100, 180, 150, rune_alpha), (15, 5), (15, 25), 2)
            pygame.draw.line(rune_surf, (100, 180, 150, rune_alpha), (8, 10), (22, 20), 2)
            surf.blit(rune_surf, (int(rune_x), int(rune_y)))

        # Header
        header = self.renderer.font.render("ALCHEMIST'S WORKSHOP", True, (60, 120, 80))
        surf.blit(header, (ww//2 - header.get_width()//2, 18))
        sub_header = self.renderer.small_font.render("Time your chains to create the perfect mixture", True, (100, 130, 110))
        surf.blit(sub_header, (ww//2 - sub_header.get_width()//2, 48))

        # Enhanced progress bar
        progress = state['total_progress']
        prog_x, prog_y = 250, 85
        prog_width = 500
        prog_height = 25

        # Progress bar background with lab styling
        pygame.draw.rect(surf, (180, 185, 190), (prog_x - 3, prog_y - 3, prog_width + 6, prog_height + 6), border_radius=5)
        pygame.draw.rect(surf, (220, 225, 230), (prog_x, prog_y, prog_width, prog_height), border_radius=4)

        # Progress fill with gradient
        fill_width = int(progress * prog_width)
        if fill_width > 0:
            for x in range(fill_width):
                ratio = x / max(fill_width, 1)
                color = lerp_color((80, 180, 120), (100, 220, 140), ratio)
                pygame.draw.line(surf, color, (prog_x + x, prog_y + 2), (prog_x + x, prog_y + prog_height - 2))

        pygame.draw.rect(surf, (100, 110, 100), (prog_x, prog_y, prog_width, prog_height), 2, border_radius=4)

        prog_label = self.renderer.small_font.render(f"Completion: {int(progress * 100)}%", True, (60, 80, 70))
        surf.blit(prog_label, (prog_x + prog_width//2 - prog_label.get_width()//2, prog_y + 3))

        # Central cauldron visualization
        cauldron_x, cauldron_y = ww // 2, 340
        cauldron_w, cauldron_h = 200, 140

        # Cauldron body with 3D effect
        pygame.draw.ellipse(surf, (50, 45, 50), (cauldron_x - cauldron_w//2 + 5, cauldron_y - 20 + 5, cauldron_w, cauldron_h))
        pygame.draw.ellipse(surf, (70, 65, 75), (cauldron_x - cauldron_w//2, cauldron_y - 20, cauldron_w, cauldron_h))

        # Cauldron rim
        pygame.draw.ellipse(surf, (90, 85, 95), (cauldron_x - cauldron_w//2 - 8, cauldron_y - 35, cauldron_w + 16, 35))
        pygame.draw.ellipse(surf, (60, 55, 65), (cauldron_x - cauldron_w//2, cauldron_y - 30, cauldron_w, 25))

        # Liquid in cauldron - color based on reaction stage
        if state['current_reaction']:
            reaction = state['current_reaction']
            stage = reaction.get('stage', 1)

            # Liquid color changes with stage
            if stage == 1:
                liquid_color = (80, 160, 120)  # Green-blue
            elif stage == 2:
                liquid_color = (100, 200, 140)  # Brighter green
            elif stage == 3:
                liquid_color = (200, 220, 100)  # Golden (sweet spot)
            elif stage == 4:
                liquid_color = (200, 150, 80)  # Orange
            else:
                liquid_color = (200, 80, 80)  # Red (danger)

            # Animated liquid surface
            liquid_points = []
            for i in range(20):
                lx = cauldron_x - cauldron_w//2 + 20 + i * 8
                ly = cauldron_y - 15 + math.sin(tick * 0.005 + i * 0.5) * 5
                liquid_points.append((lx, ly))

            liquid_points.append((cauldron_x + cauldron_w//2 - 20, cauldron_y + 40))
            liquid_points.append((cauldron_x - cauldron_w//2 + 20, cauldron_y + 40))

            pygame.draw.polygon(surf, liquid_color, liquid_points)
            pygame.draw.polygon(surf, lerp_color(liquid_color, (255, 255, 255), 0.2), liquid_points, 2)

            # Bubbles rising from liquid
            for i in range(8):
                bubble_phase = tick * 0.003 + i * 1.2
                bubble_x = cauldron_x - 60 + i * 18 + math.sin(bubble_phase * 2) * 10
                bubble_y = cauldron_y - 20 - (tick * 0.05 + i * 30) % 80
                bubble_size = 4 + int(3 * math.sin(bubble_phase))
                bubble_alpha = int(150 - (tick * 0.05 + i * 30) % 80 * 1.5)
                if bubble_alpha > 0:
                    bubble_surf = pygame.Surface((bubble_size * 2 + 4, bubble_size * 2 + 4), pygame.SRCALPHA)
                    pygame.draw.circle(bubble_surf, (*liquid_color, bubble_alpha), (bubble_size + 2, bubble_size + 2), bubble_size)
                    pygame.draw.circle(bubble_surf, (255, 255, 255, bubble_alpha // 2), (bubble_size, bubble_size), bubble_size // 2)
                    surf.blit(bubble_surf, (int(bubble_x), int(bubble_y)))

            # Steam rising above cauldron
            for i in range(5):
                steam_phase = tick * 0.002 + i * 0.8
                steam_x = cauldron_x - 40 + i * 20 + math.sin(steam_phase) * 15
                steam_y = cauldron_y - 60 - (tick * 0.02 + i * 20) % 100
                steam_size = 15 + int(10 * ((tick * 0.02 + i * 20) % 100) / 100)
                steam_alpha = int(80 - (tick * 0.02 + i * 20) % 100 * 0.7)
                if steam_alpha > 0:
                    steam_surf = pygame.Surface((steam_size * 2, steam_size * 2), pygame.SRCALPHA)
                    pygame.draw.circle(steam_surf, (240, 245, 250, steam_alpha), (steam_size, steam_size), steam_size)
                    surf.blit(steam_surf, (int(steam_x), int(steam_y)))

        # Stirring spoon animation
        spoon_angle = math.sin(tick * 0.004) * 0.3
        spoon_x = cauldron_x + 60
        spoon_y = cauldron_y - 50

        # Spoon handle
        handle_end_x = spoon_x + math.sin(spoon_angle) * 80
        handle_end_y = spoon_y - math.cos(spoon_angle) * 80
        pygame.draw.line(surf, (140, 100, 60), (spoon_x, spoon_y), (handle_end_x, handle_end_y), 8)
        pygame.draw.line(surf, (160, 120, 80), (spoon_x, spoon_y), (handle_end_x, handle_end_y), 4)

        # Spoon bowl
        pygame.draw.ellipse(surf, (120, 90, 55), (spoon_x - 20, spoon_y - 10, 35, 20))

        # Current reaction visualization - quality indicator only (removed stage names)
        if state['current_reaction']:
            reaction = state['current_reaction']

            # Quality panel on left side (removed stage name indicators per user request)
            stage_panel_x, stage_panel_y = 50, 130
            stage_panel_w, stage_panel_h = 150, 120

            pygame.draw.rect(surf, (230, 235, 240), (stage_panel_x, stage_panel_y, stage_panel_w, stage_panel_h), border_radius=8)
            pygame.draw.rect(surf, (150, 160, 155), (stage_panel_x, stage_panel_y, stage_panel_w, stage_panel_h), 2, border_radius=8)

            # Quality indicator (KEEP THIS - shows percentage)
            quality = reaction.get('quality', 0.5)
            qual_label = self.renderer.font.render(f"{int(quality * 100)}%", True, (60, 120, 80))
            surf.blit(qual_label, (stage_panel_x + stage_panel_w//2 - qual_label.get_width()//2, stage_panel_y + 20))

            quality_subtext = self.renderer.small_font.render("Current Quality", True, (80, 100, 90))
            surf.blit(quality_subtext, (stage_panel_x + stage_panel_w//2 - quality_subtext.get_width()//2, stage_panel_y + 55))

            # Quality bar
            qbar_w = 120
            qbar_h = 14
            qbar_x = stage_panel_x + stage_panel_w//2 - qbar_w//2
            qbar_y = stage_panel_y + 80
            pygame.draw.rect(surf, (200, 205, 210), (qbar_x, qbar_y, qbar_w, qbar_h), border_radius=4)
            qfill = int(quality * qbar_w)
            if qfill > 0:
                qcolor = (80, 180, 100) if quality >= 0.7 else ((180, 180, 80) if quality >= 0.4 else (180, 100, 80))
                pygame.draw.rect(surf, qcolor, (qbar_x, qbar_y, qfill, qbar_h), border_radius=4)
            pygame.draw.rect(surf, (140, 150, 145), (qbar_x, qbar_y, qbar_w, qbar_h), 1, border_radius=4)

        # Ingredient progress panel on right
        ingr_panel_x, ingr_panel_y = ww - 230, 130
        ingr_panel_w, ingr_panel_h = 180, 100

        pygame.draw.rect(surf, (230, 235, 240), (ingr_panel_x, ingr_panel_y, ingr_panel_w, ingr_panel_h), border_radius=8)
        pygame.draw.rect(surf, (150, 160, 155), (ingr_panel_x, ingr_panel_y, ingr_panel_w, ingr_panel_h), 2, border_radius=8)

        ingr_label = self.renderer.small_font.render("Ingredients", True, (80, 100, 90))
        surf.blit(ingr_label, (ingr_panel_x + ingr_panel_w//2 - ingr_label.get_width()//2, ingr_panel_y + 10))

        current_ingr = state['current_ingredient_index'] + 1
        total_ingr = state['total_ingredients']
        ingr_text = self.renderer.font.render(f"{current_ingr} / {total_ingr}", True, (60, 120, 80))
        surf.blit(ingr_text, (ingr_panel_x + ingr_panel_w//2 - ingr_text.get_width()//2, ingr_panel_y + 45))

        # Timer panel
        timer_panel_x, timer_panel_y = ww - 230, 250
        timer_panel_w, timer_panel_h = 180, 80

        pygame.draw.rect(surf, (230, 235, 240), (timer_panel_x, timer_panel_y, timer_panel_w, timer_panel_h), border_radius=8)
        pygame.draw.rect(surf, (150, 160, 155), (timer_panel_x, timer_panel_y, timer_panel_w, timer_panel_h), 2, border_radius=8)

        time_left = int(state['time_left'])
        time_color = (180, 80, 80) if time_left < 15 else ((180, 150, 80) if time_left < 30 else (80, 120, 100))
        time_label = self.renderer.small_font.render("Time", True, (80, 100, 90))
        surf.blit(time_label, (timer_panel_x + timer_panel_w//2 - time_label.get_width()//2, timer_panel_y + 10))
        time_text = self.renderer.font.render(f"{time_left}s", True, time_color)
        surf.blit(time_text, (timer_panel_x + timer_panel_w//2 - time_text.get_width()//2, timer_panel_y + 35))

        # Action buttons with lab styling
        btn_w, btn_h = 160, 50
        chain_btn = pygame.Rect(ww // 2 - btn_w - 20, wh - 180, btn_w, btn_h)
        stabilize_btn = pygame.Rect(ww // 2 + 20, wh - 180, btn_w, btn_h)

        # Chain button
        pygame.draw.rect(surf, (70, 130, 90), chain_btn, border_radius=8)
        pygame.draw.rect(surf, (100, 180, 120), (chain_btn.x, chain_btn.y, chain_btn.width, chain_btn.height // 3), border_radius=8)
        pygame.draw.rect(surf, (50, 100, 70), chain_btn, 2, border_radius=8)
        chain_text = self.renderer.small_font.render("CHAIN [C]", True, (220, 240, 230))
        surf.blit(chain_text, (chain_btn.centerx - chain_text.get_width()//2, chain_btn.centery - chain_text.get_height()//2))

        # Stabilize button
        pygame.draw.rect(surf, (80, 120, 160), stabilize_btn, border_radius=8)
        pygame.draw.rect(surf, (100, 150, 200), (stabilize_btn.x, stabilize_btn.y, stabilize_btn.width, stabilize_btn.height // 3), border_radius=8)
        pygame.draw.rect(surf, (60, 90, 130), stabilize_btn, 2, border_radius=8)
        stab_text = self.renderer.small_font.render("STABILIZE [S]", True, (220, 230, 250))
        surf.blit(stab_text, (stabilize_btn.centerx - stab_text.get_width()//2, stabilize_btn.centery - stab_text.get_height()//2))

        # Result display
        if state['result']:
            result = state['result']
            result_w, result_h = 500, 280
            result_x, result_y = ww//2 - result_w//2, wh//2 - result_h//2

            result_surf = pygame.Surface((result_w, result_h), pygame.SRCALPHA)
            pygame.draw.rect(result_surf, (235, 240, 245, 250), (0, 0, result_w, result_h), border_radius=12)
            pygame.draw.rect(result_surf, (100, 130, 110), (0, 0, result_w, result_h), 4, border_radius=12)

            if result['success']:
                header = "POTION COMPLETE"
                header_surf = self.renderer.font.render(header, True, (60, 150, 80))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 25))

                pygame.draw.line(result_surf, (150, 170, 155), (50, 65), (result_w - 50, 65), 2)

                quality_text = result.get('quality', 'Standard')
                qual_surf = self.renderer.font.render(quality_text, True, (80, 140, 100))
                result_surf.blit(qual_surf, (result_w//2 - qual_surf.get_width()//2, 90))

                prog_text = f"Final Progress: {int(result.get('progress', 0) * 100)}%"
                prog_surf = self.renderer.small_font.render(prog_text, True, (80, 100, 90))
                result_surf.blit(prog_surf, (result_w//2 - prog_surf.get_width()//2, 140))

                msg = result.get('message', 'Potion brewed successfully!')
                msg_surf = self.renderer.small_font.render(msg, True, (100, 120, 110))
                result_surf.blit(msg_surf, (result_w//2 - msg_surf.get_width()//2, 180))
            else:
                header = "BREWING FAILED"
                header_surf = self.renderer.font.render(header, True, (180, 80, 80))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 35))

                pygame.draw.line(result_surf, (180, 140, 140), (50, 75), (result_w - 50, 75), 2)

                msg = result.get('message', 'The mixture became unstable.')
                msg_surf = self.renderer.small_font.render(msg, True, (120, 100, 100))
                result_surf.blit(msg_surf, (result_w//2 - msg_surf.get_width()//2, 120))

            close_text = self.renderer.tiny_font.render("Press any key to continue", True, (130, 140, 135))
            result_surf.blit(close_text, (result_w//2 - close_text.get_width()//2, result_h - 30))

            surf.blit(result_surf, (result_x, result_y))

        # Draw metadata overlay if active
        effects.metadata_overlay.draw(surf, (ww//2, wh//2), self.renderer.small_font)

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = pygame.Rect(wx + chain_btn.x, wy + chain_btn.y, chain_btn.width, chain_btn.height)
        self.minigame_button_rect2 = pygame.Rect(wx + stabilize_btn.x, wy + stabilize_btn.y, stabilize_btn.width, stabilize_btn.height)

        # Reset effects when minigame ends
        if state['result']:
            self._alchemy_effects_initialized = False

    def _render_refining_minigame(self):
        """Render refining minigame UI with enhanced kiln/foundry aesthetic"""
        state = self.active_minigame.get_state()
        effects = get_effects_manager()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        # Initialize effects if needed
        if not hasattr(self, '_refining_effects_initialized') or not self._refining_effects_initialized:
            effects.initialize_discipline('refining', pygame.Rect(wx, wy, ww, wh))
            self._refining_effects_initialized = True
            # Show metadata overlay
            difficulty_tier = getattr(self.active_minigame, 'difficulty_tier', 'Unknown')
            difficulty_points = getattr(self.active_minigame, 'difficulty_points', 0)
            effects.show_metadata({
                'discipline': 'Refining',
                'difficulty_tier': difficulty_tier,
                'difficulty_points': difficulty_points,
                'time_limit': state.get('time_limit', 60),
                'max_bonus': 1.0 + difficulty_points * 0.012,
                'special_params': {
                    'Tumblers': state.get('total_cylinders', 3),
                    'Attempts': state.get('allowed_failures', 2)
                }
            })

        dt = 1/60
        effects.update(dt)
        tick = pygame.time.get_ticks()

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)

        # Bronze/copper gradient background
        for y in range(wh):
            progress = y / wh
            r = int(45 + 25 * progress)
            g = int(32 + 15 * progress)
            b = int(22 + 8 * progress)
            pygame.draw.line(surf, (r, g, b), (0, y), (ww, y))

        # Kiln arch glow at bottom
        glow_intensity = 0.6 + 0.3 * math.sin(tick * 0.002)
        for y in range(180):
            alpha = int(100 * (1 - y / 180) * glow_intensity)
            glow_color = (255, 160 + int(40 * glow_intensity), 60, alpha)
            glow_surf = pygame.Surface((ww, 1), pygame.SRCALPHA)
            glow_surf.fill(glow_color)
            surf.blit(glow_surf, (0, wh - 180 + y))

        # Kiln mouth arch
        arch_center_x = ww // 2
        arch_y = wh - 100
        arch_width, arch_height = 400, 120

        # Outer brickwork
        for row in range(8):
            for col in range(14):
                brick_x = arch_center_x - 210 + col * 30
                brick_y = wh - 130 + row * 16
                if row < 3 or abs(col - 7) > 4 - row:
                    brick_color = (120 + (row * col) % 20, 70 + (row + col) % 15, 45)
                    pygame.draw.rect(surf, brick_color, (brick_x, brick_y, 28, 14))
                    pygame.draw.rect(surf, (80, 50, 35), (brick_x, brick_y, 28, 14), 1)

        # Inner kiln glow
        inner_rect = pygame.Rect(arch_center_x - 150, wh - 90, 300, 90)
        for i in range(5):
            shrink = i * 15
            glow_alpha = int(150 * (1 - i/5) * glow_intensity)
            inner_glow = pygame.Surface((300 - shrink*2, 90), pygame.SRCALPHA)
            inner_glow.fill((255, 180 - i*20, 80 - i*15, glow_alpha))
            surf.blit(inner_glow, (inner_rect.x + shrink, inner_rect.y))

        # Animated flames inside kiln
        for i in range(8):
            flame_x = arch_center_x - 100 + i * 28
            flame_phase = tick * 0.01 + i * 0.9
            flame_height = 50 + 20 * math.sin(flame_phase) + 10 * math.sin(flame_phase * 2.1)

            for layer in range(3):
                lh = flame_height * (1 - layer * 0.25)
                lw = 18 - layer * 4
                colors = [(255, 220, 140), (255, 160, 60), (255, 100, 30)]

                pts = [
                    (flame_x - lw//2, wh - 10),
                    (flame_x - lw//4, wh - 10 - lh * 0.5),
                    (flame_x, wh - 10 - lh),
                    (flame_x + lw//4, wh - 10 - lh * 0.6),
                    (flame_x + lw//2, wh - 10),
                ]
                pygame.draw.polygon(surf, colors[layer], pts)

        # Decorative gears in corners
        gear_positions = [
            (80, 80, 45, 10, 25),
            (ww - 80, 80, 40, 8, -30),
            (100, wh - 200, 35, 8, 20),
            (ww - 100, wh - 200, 50, 12, -18),
        ]

        for gx, gy, radius, teeth, speed in gear_positions:
            angle = (tick * speed / 1000) % 360
            gear_color = (180, 140, 80)
            gear_dark = (120, 90, 55)

            # Outer ring
            pygame.draw.circle(surf, gear_color, (gx, gy), radius, 4)
            pygame.draw.circle(surf, gear_dark, (gx, gy), radius - 8, 2)

            # Teeth
            for t in range(teeth):
                tooth_angle = math.radians(angle + t * (360 / teeth))
                inner_tx = gx + math.cos(tooth_angle) * radius
                inner_ty = gy + math.sin(tooth_angle) * radius
                outer_tx = gx + math.cos(tooth_angle) * (radius + 10)
                outer_ty = gy + math.sin(tooth_angle) * (radius + 10)
                pygame.draw.line(surf, gear_color, (inner_tx, inner_ty), (outer_tx, outer_ty), 4)

            # Center
            pygame.draw.circle(surf, gear_dark, (gx, gy), radius // 4)

        # Header
        header = self.renderer.font.render("MATERIAL REFINERY", True, (220, 180, 120))
        surf.blit(header, (ww//2 - header.get_width()//2, 18))
        sub_header = self.renderer.small_font.render("Align the tumblers to unlock the refined material", True, (180, 150, 120))
        surf.blit(sub_header, (ww//2 - sub_header.get_width()//2, 48))

        # Progress panel (left side) - styled with bronze theme
        panel_x, panel_y = 50, 90
        panel_w, panel_h = 180, 170

        pygame.draw.rect(surf, (50, 38, 28), (panel_x, panel_y, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(surf, (140, 100, 60), (panel_x, panel_y, panel_w, panel_h), 3, border_radius=8)

        # Tumbler progress
        tumbler_label = self.renderer.small_font.render("Tumblers", True, (200, 170, 130))
        surf.blit(tumbler_label, (panel_x + panel_w//2 - tumbler_label.get_width()//2, panel_y + 12))

        aligned = state['aligned_count']
        total = state['total_cylinders']

        # Visual tumbler indicators
        tumbler_y = panel_y + 45
        tumbler_spacing = min(25, (panel_w - 30) // max(total, 1))
        tumbler_start_x = panel_x + panel_w//2 - (total * tumbler_spacing) // 2

        for i in range(total):
            tx = tumbler_start_x + i * tumbler_spacing
            if i < aligned:
                pygame.draw.circle(surf, (100, 220, 100), (tx + 10, tumbler_y), 10)
                pygame.draw.circle(surf, (150, 255, 150), (tx + 10, tumbler_y), 10, 2)
            elif i == aligned:
                pulse = 0.7 + 0.3 * math.sin(tick * 0.01)
                pygame.draw.circle(surf, (int(255 * pulse), int(200 * pulse), 50), (tx + 10, tumbler_y), 10)
                pygame.draw.circle(surf, (255, 215, 100), (tx + 10, tumbler_y), 10, 2)
            else:
                pygame.draw.circle(surf, (80, 60, 50), (tx + 10, tumbler_y), 10)
                pygame.draw.circle(surf, (120, 90, 70), (tx + 10, tumbler_y), 10, 2)

        # Attempts remaining
        failures_left = max(0, state['allowed_failures'] - state['failed_attempts'])
        attempts_label = self.renderer.small_font.render("Attempts", True, (200, 170, 130))
        surf.blit(attempts_label, (panel_x + panel_w//2 - attempts_label.get_width()//2, panel_y + 70))

        fail_color = (255, 80, 80) if failures_left == 0 else ((255, 180, 80) if failures_left <= 1 else (200, 200, 180))
        attempts_value = self.renderer.font.render(str(failures_left), True, fail_color)
        surf.blit(attempts_value, (panel_x + panel_w//2 - attempts_value.get_width()//2, panel_y + 92))

        # Timer
        time_left = int(state['time_left'])
        time_color = (255, 80, 80) if time_left < 10 else ((255, 180, 80) if time_left < 20 else (200, 200, 180))
        time_label = self.renderer.small_font.render("Time", True, (200, 170, 130))
        surf.blit(time_label, (panel_x + panel_w//2 - time_label.get_width()//2, panel_y + 125))
        time_value = self.renderer.font.render(f"{time_left}s", True, time_color)
        surf.blit(time_value, (panel_x + panel_w//2 - time_value.get_width()//2, panel_y + 142))

        # Main lock mechanism visualization with bronze/brass theme
        cx, cy = ww // 2, 300
        radius = 130
        current_cyl = state['current_cylinder']
        total = state['total_cylinders']

        # Lock body - ornate brass/bronze casing
        lock_w = radius * 2 + 80
        lock_h = radius * 2 + 100
        lock_x = cx - lock_w // 2
        lock_y = cy - radius - 40

        # Shadow
        pygame.draw.ellipse(surf, (30, 25, 20, 100), (lock_x + 10, lock_y + lock_h - 10, lock_w, 30))

        # Main body layers for depth
        pygame.draw.rect(surf, (60, 45, 35), (lock_x + 6, lock_y + 6, lock_w, lock_h), border_radius=15)
        pygame.draw.rect(surf, (100, 75, 50), (lock_x, lock_y, lock_w, lock_h), border_radius=15)

        # Inner decorative border
        pygame.draw.rect(surf, (140, 105, 65), (lock_x + 8, lock_y + 8, lock_w - 16, lock_h - 16), 3, border_radius=12)

        # Outer frame highlight
        pygame.draw.rect(surf, (180, 140, 90), (lock_x, lock_y, lock_w, lock_h), 4, border_radius=15)

        # Corner rivets
        rivet_positions = [
            (lock_x + 20, lock_y + 20),
            (lock_x + lock_w - 20, lock_y + 20),
            (lock_x + 20, lock_y + lock_h - 20),
            (lock_x + lock_w - 20, lock_y + lock_h - 20),
        ]
        for rx, ry in rivet_positions:
            pygame.draw.circle(surf, (160, 120, 70), (rx, ry), 8)
            pygame.draw.circle(surf, (200, 160, 100), (rx, ry), 8, 2)
            pygame.draw.circle(surf, (120, 90, 55), (rx, ry), 4)

        # Keyhole at bottom
        pygame.draw.ellipse(surf, (40, 35, 30), (cx - 18, cy + radius + 25, 36, 24))
        pygame.draw.rect(surf, (40, 35, 30), (cx - 10, cy + radius + 42, 20, 30))
        pygame.draw.ellipse(surf, (60, 50, 40), (cx - 18, cy + radius + 25, 36, 24), 2)

        # Main tumbler cylinder with bronze/brass colors
        # Outer glow when in ideal zone
        pygame.draw.circle(surf, (60, 50, 40), (cx, cy), radius + 5)
        pygame.draw.circle(surf, (80, 65, 50), (cx, cy), radius)
        pygame.draw.circle(surf, (100, 80, 60), (cx, cy), radius - 15)
        pygame.draw.circle(surf, (70, 55, 45), (cx, cy), radius - 30)

        # Outer ring (brass with shine)
        pygame.draw.circle(surf, (200, 160, 100), (cx, cy), radius, 5)
        pygame.draw.circle(surf, (140, 110, 70), (cx, cy), radius - 3, 2)

        # Decorative inner rings
        pygame.draw.circle(surf, (150, 120, 80), (cx, cy), radius - 40, 2)
        pygame.draw.circle(surf, (120, 95, 65), (cx, cy), radius - 60, 2)

        # Pin indicators around the edge (showing progress)
        for i in range(total):
            angle = (i / total) * 2 * math.pi - math.pi / 2  # Start from top
            pin_x = cx + int((radius + 40) * math.cos(angle))
            pin_y = cy + int((radius + 40) * math.sin(angle))

            if i < len(state.get('aligned_cylinders', [])):
                pin_color = (80, 200, 80)
                pin_border = (120, 255, 120)
            elif i == current_cyl:
                pulse = 0.7 + 0.3 * math.sin(tick * 0.01)
                pin_color = (int(255 * pulse), int(180 * pulse), 50)
                pin_border = (255, 220, 100)
            else:
                pin_color = (70, 55, 45)
                pin_border = (100, 80, 60)

            pygame.draw.circle(surf, pin_color, (pin_x, pin_y), 12)
            pygame.draw.circle(surf, pin_border, (pin_x, pin_y), 12, 2)
            pygame.draw.circle(surf, (50, 40, 35), (pin_x, pin_y), 5)

        # Current cylinder tumbler
        if current_cyl < len(state['cylinders']):
            cyl = state['cylinders'][current_cyl]
            angle = cyl['angle']
            inner_radius = radius - 40

            # Draw notch pattern with brass styling
            notch_count = 12
            for i in range(notch_count):
                notch_angle = (i / notch_count) * 2 * math.pi
                outer_x = cx + int(inner_radius * math.cos(notch_angle))
                outer_y = cy + int(inner_radius * math.sin(notch_angle))
                inner_x = cx + int((inner_radius - 18) * math.cos(notch_angle))
                inner_y = cy + int((inner_radius - 18) * math.sin(notch_angle))
                pygame.draw.line(surf, (50, 40, 35), (inner_x, inner_y), (outer_x, outer_y), 3)

            # Target zone at top (green arc with glow)
            target_width_deg = state['timing_window'] * cyl['speed'] * 360
            target_half = target_width_deg / 2

            # Target zone glow
            for a in range(int(-target_half * 1.2), int(target_half * 1.2) + 1):
                rad = math.radians(a - 90)
                x1 = cx + int((inner_radius - 15) * math.cos(rad))
                y1 = cy + int((inner_radius - 15) * math.sin(rad))
                x2 = cx + int((inner_radius + 12) * math.cos(rad))
                y2 = cy + int((inner_radius + 12) * math.sin(rad))
                glow_alpha = int(80 * (1 - abs(a) / (target_half * 1.2)))
                pygame.draw.line(surf, (80, 200, 80), (x1, y1), (x2, y2), 3)

            # Target zone markers
            for a in range(int(-target_half), int(target_half) + 1, 2):
                rad = math.radians(a - 90)
                x1 = cx + int((inner_radius - 10) * math.cos(rad))
                y1 = cy + int((inner_radius - 10) * math.sin(rad))
                x2 = cx + int((inner_radius + 8) * math.cos(rad))
                y2 = cy + int((inner_radius + 8) * math.sin(rad))
                pygame.draw.line(surf, (100, 255, 100), (x1, y1), (x2, y2), 2)

            # Rotating indicator (the "pick") with brass styling
            angle_rad = math.radians(angle - 90)
            ind_inner = 30
            ind_outer = inner_radius - 8

            # Pick shadow
            shadow_offset = 3
            shadow_inner_x = cx + int(ind_inner * math.cos(angle_rad)) + shadow_offset
            shadow_inner_y = cy + int(ind_inner * math.sin(angle_rad)) + shadow_offset
            shadow_outer_x = cx + int(ind_outer * math.cos(angle_rad)) + shadow_offset
            shadow_outer_y = cy + int(ind_outer * math.sin(angle_rad)) + shadow_offset
            pygame.draw.line(surf, (40, 35, 30), (shadow_inner_x, shadow_inner_y), (shadow_outer_x, shadow_outer_y), 6)

            # Main pick
            inner_x = cx + int(ind_inner * math.cos(angle_rad))
            inner_y = cy + int(ind_inner * math.sin(angle_rad))
            outer_x = cx + int(ind_outer * math.cos(angle_rad))
            outer_y = cy + int(ind_outer * math.sin(angle_rad))

            pygame.draw.line(surf, (180, 140, 80), (inner_x, inner_y), (outer_x, outer_y), 5)
            pygame.draw.line(surf, (220, 180, 120), (inner_x, inner_y), (outer_x, outer_y), 3)

            # Pick head
            pygame.draw.circle(surf, (200, 160, 90), (outer_x, outer_y), 12)
            pygame.draw.circle(surf, (255, 215, 100), (outer_x, outer_y), 12, 3)
            pygame.draw.circle(surf, (150, 120, 70), (outer_x, outer_y), 5)

        # Feedback flash
        feedback_timer = state.get('feedback_timer', 0)
        if feedback_timer > 0:
            alpha = int(200 * (feedback_timer / 0.3))
            aligned_count = len(state.get('aligned_cylinders', []))

            if aligned_count > 0 and state.get('current_cylinder', 0) > 0:
                # Success flash with brass color
                flash_surf = pygame.Surface((220, 220), pygame.SRCALPHA)
                pygame.draw.circle(flash_surf, (100, 255, 100, alpha), (110, 110), 90)
                pygame.draw.circle(flash_surf, (150, 255, 150, alpha // 2), (110, 110), 110)
                surf.blit(flash_surf, (cx - 110, cy - 110))

                click_text = self.renderer.font.render("ALIGNED!", True, (100, 255, 100))
                surf.blit(click_text, (cx - click_text.get_width()//2, cy - radius - 55))

        # Instructions
        instruction = self.renderer.small_font.render("[SPACE] Align when pick reaches green zone", True, (200, 170, 130))
        surf.blit(instruction, (ww//2 - instruction.get_width()//2, wh - 195))

        # Result (if completed)
        if state['result']:
            result = state['result']
            result_w, result_h = 500, 280
            result_x, result_y = ww//2 - result_w//2, wh//2 - result_h//2

            result_surf = pygame.Surface((result_w, result_h), pygame.SRCALPHA)

            # Background with bronze theme
            pygame.draw.rect(result_surf, (45, 35, 28, 248), (0, 0, result_w, result_h), border_radius=12)
            pygame.draw.rect(result_surf, (160, 120, 70), (0, 0, result_w, result_h), 4, border_radius=12)

            if result['success']:
                header_text = "REFINEMENT COMPLETE"
                header_surf = self.renderer.font.render(header_text, True, (100, 255, 100))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 25))

                pygame.draw.line(result_surf, (140, 105, 65), (50, 65), (result_w - 50, 65), 2)

                # Success message
                msg = "Material successfully refined!"
                msg_text = self.renderer.small_font.render(msg, True, (200, 180, 150))
                result_surf.blit(msg_text, (result_w//2 - msg_text.get_width()//2, 90))

                # Quality if available
                quality = result.get('quality_tier', result.get('quality', 'Standard'))
                qual_label = self.renderer.small_font.render("Quality:", True, (180, 150, 120))
                result_surf.blit(qual_label, (60, 130))
                qual_value = self.renderer.font.render(str(quality), True, (100, 220, 100))
                result_surf.blit(qual_value, (160, 125))

                # Additional message
                detail = result.get('message', '')
                if detail:
                    detail_text = self.renderer.small_font.render(detail, True, (180, 160, 130))
                    result_surf.blit(detail_text, (result_w//2 - detail_text.get_width()//2, 180))

            else:
                header_text = "REFINEMENT FAILED"
                header_surf = self.renderer.font.render(header_text, True, (255, 100, 100))
                result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 25))

                pygame.draw.line(result_surf, (120, 70, 50), (50, 65), (result_w - 50, 65), 2)

                # Material loss
                loss_pct = result.get('loss_percentage', 50)
                loss_label = self.renderer.small_font.render("Materials Lost:", True, (200, 150, 130))
                result_surf.blit(loss_label, (60, 100))
                loss_value = self.renderer.font.render(f"{loss_pct}%", True, (255, 120, 100))
                result_surf.blit(loss_value, (220, 95))

                msg = result.get('message', 'The lock mechanism jammed.')
                msg_text = self.renderer.small_font.render(msg, True, (200, 170, 150))
                result_surf.blit(msg_text, (result_w//2 - msg_text.get_width()//2, 160))

            # Close hint
            close_text = self.renderer.tiny_font.render("Press any key to continue", True, (150, 120, 90))
            result_surf.blit(close_text, (result_w//2 - close_text.get_width()//2, result_h - 30))

            surf.blit(result_surf, (result_x, result_y))

        # Draw metadata overlay if active
        effects.metadata_overlay.draw(surf, (ww//2, wh//2), self.renderer.small_font)

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = None

        # Reset effects when minigame ends
        if state['result']:
            self._refining_effects_initialized = False

    def _render_engineering_minigame(self):
        """Render engineering minigame UI with workbench aesthetic"""
        state = self.active_minigame.get_state()
        effects = get_effects_manager()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        # Initialize effects if needed
        if not hasattr(self, '_engineering_effects_initialized') or not self._engineering_effects_initialized:
            effects.initialize_discipline('engineering', pygame.Rect(wx, wy, ww, wh))
            self._engineering_effects_initialized = True
            # Reset logic switch view state for new puzzle
            self._logic_switch_view = 'current'
            self._logic_switch_slide_start = 0
            self._logic_switch_slide_from = 'current'
            # Track last shown puzzle index
            self._engineering_last_puzzle_shown = -1

        # Show info overlay for each new puzzle (including first)
        current_puzzle_idx = self.active_minigame.current_puzzle_index
        if not hasattr(self, '_engineering_last_puzzle_shown'):
            self._engineering_last_puzzle_shown = -1

        if current_puzzle_idx > self._engineering_last_puzzle_shown:
            self._engineering_last_puzzle_shown = current_puzzle_idx
            # Reset logic switch view state for new puzzle
            self._logic_switch_view = 'current'
            self._logic_switch_slide_start = 0
            self._logic_switch_slide_from = 'current'

            # Get puzzle info
            difficulty_tier = getattr(self.active_minigame, 'difficulty_tier', 'Unknown')
            difficulty_points = getattr(self.active_minigame, 'difficulty_points', 0)
            current_puzzle = state.get('current_puzzle', {})
            total_puzzles = state.get('total_puzzles', 1)

            # Detect puzzle type and mode
            puzzle_type = current_puzzle.get('puzzle_type', 'rotation_pipe')
            if puzzle_type == 'logic_switch':
                puzzle_mode = current_puzzle.get('puzzle_mode', 'random -> uniform')
                ideal_moves = current_puzzle.get('ideal_moves', 10)
                grid_size = current_puzzle.get('grid_size', 4)
                special_params = {
                    'Puzzle Type': 'Logic Switch',
                    'Puzzle Mode': puzzle_mode,
                    'Grid Size': f'{grid_size}x{grid_size}',
                    'Ideal Moves': ideal_moves
                }
            else:
                grid_size = current_puzzle.get('grid_size', 4)
                special_params = {
                    'Puzzle Type': 'Pipe Rotation',
                    'Grid Size': f'{grid_size}x{grid_size}',
                    'Goal': 'Connect input to output'
                }

            effects.show_metadata({
                'discipline': 'Engineering',
                'difficulty_tier': f'Puzzle {current_puzzle_idx + 1}/{total_puzzles}' if total_puzzles > 1 else difficulty_tier,
                'difficulty_points': difficulty_points,
                'time_limit': state.get('time_limit', 120) if current_puzzle_idx == 0 else None,
                'max_bonus': 1.0 + difficulty_points * 0.02,
                'special_params': special_params
            })

        dt = 1/60
        effects.update(dt)
        tick = pygame.time.get_ticks()

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)

        # Workbench wood background
        for y in range(wh):
            progress = y / wh
            r = int(100 + 30 * math.sin(y * 0.02))
            g = int(70 + 20 * math.sin(y * 0.02))
            b = int(50 + 10 * math.sin(y * 0.02))
            pygame.draw.line(surf, (r, g, b), (0, y), (ww, y))

        # Wood grain texture
        for i in range(0, wh, 25):
            grain_intensity = 10 + int(10 * math.sin(i * 0.1))
            pygame.draw.line(surf, (90 + grain_intensity, 60 + grain_intensity, 45), (0, i), (ww, i), 1)

        # Warm overhead lighting effect
        light_intensity = 0.85 + 0.1 * math.sin(tick * 0.001)
        for y in range(200):
            alpha = int(60 * (1 - y / 200) * light_intensity)
            light_surf = pygame.Surface((ww, 1), pygame.SRCALPHA)
            light_surf.fill((255, 230, 180, alpha))
            surf.blit(light_surf, (0, y))

        # Scattered tools decoration
        tool_positions = [
            ('wrench', 50, 80, 20),
            ('screwdriver', ww - 80, 100, -15),
            ('pliers', 70, wh - 120, 30),
            ('hammer', ww - 100, wh - 100, -25),
        ]

        for tool_type, tx, ty, angle in tool_positions:
            tool_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
            tool_color = (120, 125, 130)
            handle_color = (140, 100, 60)

            if tool_type == 'wrench':
                pygame.draw.line(tool_surf, tool_color, (10, 30), (50, 30), 5)
                pygame.draw.circle(tool_surf, tool_color, (50, 30), 10, 3)
                pygame.draw.circle(tool_surf, tool_color, (10, 30), 8, 3)
            elif tool_type == 'screwdriver':
                pygame.draw.line(tool_surf, handle_color, (10, 30), (35, 30), 8)
                pygame.draw.line(tool_surf, tool_color, (35, 30), (55, 30), 4)
            elif tool_type == 'pliers':
                pygame.draw.line(tool_surf, tool_color, (15, 25), (45, 35), 4)
                pygame.draw.line(tool_surf, tool_color, (15, 35), (45, 25), 4)
                pygame.draw.circle(tool_surf, (80, 80, 85), (30, 30), 5)
            elif tool_type == 'hammer':
                pygame.draw.line(tool_surf, handle_color, (10, 35), (35, 35), 7)
                pygame.draw.rect(tool_surf, tool_color, (35, 22, 20, 26))

            rotated = pygame.transform.rotate(tool_surf, angle)
            surf.blit(rotated, (tx - rotated.get_width()//2, ty - rotated.get_height()//2))

        # Header with workbench theme
        header = self.renderer.font.render("ENGINEER'S WORKBENCH", True, (60, 80, 100))
        surf.blit(header, (ww//2 - header.get_width()//2, 18))
        sub_header = self.renderer.small_font.render("Solve the puzzles to assemble the device", True, (90, 100, 110))
        surf.blit(sub_header, (ww//2 - sub_header.get_width()//2, 48))

        # Progress panel (left side)
        panel_x, panel_y = 50, 90
        panel_w, panel_h = 160, 100

        pygame.draw.rect(surf, (70, 55, 45), (panel_x, panel_y, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(surf, (140, 120, 100), (panel_x, panel_y, panel_w, panel_h), 3, border_radius=8)

        puzzle_label = self.renderer.small_font.render("Puzzle", True, (180, 170, 160))
        surf.blit(puzzle_label, (panel_x + panel_w//2 - puzzle_label.get_width()//2, panel_y + 12))

        current_puzzle = state['current_puzzle_index'] + 1
        total_puzzles = state['total_puzzles']
        puzzle_text = self.renderer.font.render(f"{current_puzzle} / {total_puzzles}", True, (220, 210, 200))
        surf.blit(puzzle_text, (panel_x + panel_w//2 - puzzle_text.get_width()//2, panel_y + 40))

        # Time panel (right side)
        time_x, time_y = ww - 210, 90
        time_w, time_h = 160, 100

        time_remaining = state.get('time_remaining', 0)
        time_limit = state.get('time_limit', 1)
        time_ratio = time_remaining / max(1, time_limit)

        # Color based on time remaining
        if time_ratio > 0.5:
            time_color = (100, 180, 100)
        elif time_ratio > 0.25:
            time_color = (200, 180, 80)
        else:
            time_color = (220, 100, 80)

        pygame.draw.rect(surf, (70, 55, 45), (time_x, time_y, time_w, time_h), border_radius=8)
        pygame.draw.rect(surf, (140, 120, 100), (time_x, time_y, time_w, time_h), 3, border_radius=8)

        time_label = self.renderer.small_font.render("Time Left", True, (180, 170, 160))
        surf.blit(time_label, (time_x + time_w//2 - time_label.get_width()//2, time_y + 12))

        minutes = int(time_remaining) // 60
        seconds = int(time_remaining) % 60
        time_text = self.renderer.font.render(f"{minutes}:{seconds:02d}", True, time_color)
        surf.blit(time_text, (time_x + time_w//2 - time_text.get_width()//2, time_y + 40))

        # Time bar
        bar_x, bar_y = time_x + 10, time_y + 75
        bar_w, bar_h = time_w - 20, 10
        pygame.draw.rect(surf, (50, 45, 40), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pygame.draw.rect(surf, time_color, (bar_x, bar_y, int(bar_w * time_ratio), bar_h), border_radius=3)

        # Solved counter (smaller, below puzzle count)
        solved_label = self.renderer.small_font.render("Solved", True, (180, 170, 160))
        surf.blit(solved_label, (panel_x + 10, panel_y + 68))

        solved_text = self.renderer.small_font.render(str(state['solved_count']), True, (100, 200, 120))
        surf.blit(solved_text, (panel_x + panel_w - 30, panel_y + 68))

        # Store puzzle cell rects for click detection
        self.engineering_puzzle_rects = []

        # Puzzle-specific rendering
        if state['current_puzzle']:
            puzzle = state['current_puzzle']

            # Detect puzzle type and render accordingly
            if puzzle.get('puzzle_type') == 'logic_switch':
                # Logic Switch Puzzle (new)
                self._render_logic_switch_puzzle(surf, puzzle, wx, wy)
            elif 'grid' in puzzle and 'rotations' in puzzle:
                # Rotation Pipe Puzzle
                self._render_rotation_pipe_puzzle(surf, puzzle, wx, wy)
            elif 'grid' in puzzle and 'moves' in puzzle and not puzzle.get('deprecated'):
                # Sliding Tile Puzzle (legacy)
                self._render_sliding_tile_puzzle(surf, puzzle, wx, wy)
            elif puzzle.get('placeholder') or puzzle.get('deprecated'):
                # Placeholder or deprecated puzzle - auto-complete
                puzzle_rect = pygame.Rect(200, 250, 600, 300)
                pygame.draw.rect(surf, (40, 40, 40), puzzle_rect)
                pygame.draw.rect(surf, (100, 100, 100), puzzle_rect, 2)
                msg = "Deprecated puzzle - Click COMPLETE" if puzzle.get('deprecated') else "Puzzle placeholder - Click COMPLETE"
                _temp_surf = self.renderer.small_font.render(msg, True, (200, 200, 200))
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
            result_w, result_h = 500, 250
            result_x, result_y = ww//2 - result_w//2, wh//2 - result_h//2

            result_surf = pygame.Surface((result_w, result_h), pygame.SRCALPHA)
            pygame.draw.rect(result_surf, (60, 50, 42, 248), (0, 0, result_w, result_h), border_radius=12)
            pygame.draw.rect(result_surf, (140, 120, 100), (0, 0, result_w, result_h), 4, border_radius=12)

            header = "DEVICE ASSEMBLED"
            header_surf = self.renderer.font.render(header, True, (100, 200, 120))
            result_surf.blit(header_surf, (result_w//2 - header_surf.get_width()//2, 20))

            pygame.draw.line(result_surf, (120, 100, 80), (50, 55), (result_w - 50, 55), 2)

            puzzles_text = f"Puzzles Solved: {state['solved_count']}/{state['total_puzzles']}"
            puzzles_surf = self.renderer.small_font.render(puzzles_text, True, (180, 170, 160))
            result_surf.blit(puzzles_surf, (result_w//2 - puzzles_surf.get_width()//2, 70))

            # Show efficiency score
            efficiency = result.get('efficiency', 1.0)
            eff_pct = int(efficiency * 100)
            if efficiency >= 0.9:
                eff_color = (100, 255, 100)
                eff_label = "Perfect!"
            elif efficiency >= 0.7:
                eff_color = (200, 200, 100)
                eff_label = "Good"
            elif efficiency >= 0.5:
                eff_color = (200, 150, 80)
                eff_label = "Okay"
            else:
                eff_color = (200, 100, 100)
                eff_label = "Needs Work"

            eff_text = f"Efficiency: {eff_pct}% - {eff_label}"
            eff_surf = self.renderer.small_font.render(eff_text, True, eff_color)
            result_surf.blit(eff_surf, (result_w//2 - eff_surf.get_width()//2, 100))

            # Show performance
            performance = result.get('performance', 0)
            perf_pct = int(performance * 100)
            perf_text = f"Overall Performance: {perf_pct}%"
            perf_surf = self.renderer.small_font.render(perf_text, True, (180, 190, 200))
            result_surf.blit(perf_surf, (result_w//2 - perf_surf.get_width()//2, 130))

            # Time expired warning
            if result.get('time_expired'):
                warn_text = "Time Expired - Partial Completion"
                warn_surf = self.renderer.small_font.render(warn_text, True, (220, 100, 80))
                result_surf.blit(warn_surf, (result_w//2 - warn_surf.get_width()//2, 165))

            msg = result.get('message', 'Device successfully constructed!')
            msg_surf = self.renderer.tiny_font.render(msg, True, (150, 140, 130))
            result_surf.blit(msg_surf, (result_w//2 - msg_surf.get_width()//2, 195))

            close_text = self.renderer.tiny_font.render("Press any key to continue", True, (150, 130, 110))
            result_surf.blit(close_text, (result_w//2 - close_text.get_width()//2, result_h - 25))

            surf.blit(result_surf, (result_x, result_y))

        # Draw metadata overlay if active
        effects.metadata_overlay.draw(surf, (ww//2, wh//2), self.renderer.small_font)

        self.screen.blit(surf, (wx, wy))

        # Reset effects when minigame ends
        if state['result']:
            self._engineering_effects_initialized = False

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

    def _render_logic_switch_puzzle(self, surf, puzzle, wx, wy):
        """Render logic switch puzzle with sliding view toggle between current and target"""
        grid_size = puzzle['grid_size']
        grid = puzzle['grid']
        target = puzzle['target']
        moves = puzzle.get('moves', 0)
        ideal_moves = puzzle.get('ideal_moves', 0)
        efficiency = puzzle.get('efficiency', 1.0)
        tick = pygame.time.get_ticks()

        # Initialize view state if needed
        if not hasattr(self, '_logic_switch_view'):
            self._logic_switch_view = 'current'  # 'current' or 'target'
            self._logic_switch_slide_start = 0
            self._logic_switch_slide_from = 'current'

        # Calculate slide animation progress (0.0 to 1.0)
        slide_duration = 300  # ms
        slide_progress = 1.0
        if self._logic_switch_slide_start > 0:
            elapsed = tick - self._logic_switch_slide_start
            if elapsed < slide_duration:
                # Easing function (ease out cubic)
                t = elapsed / slide_duration
                slide_progress = 1 - (1 - t) ** 3
            else:
                self._logic_switch_slide_start = 0
                slide_progress = 1.0

        # Calculate cell size and centered position
        puzzle_area_size = min(420, 420)
        cell_size = puzzle_area_size // grid_size
        grid_width = cell_size * grid_size
        center_x = 500  # Center of 1000px width
        start_y = 200

        # Header with instructions
        instruction = "Toggle switches to match the target pattern"
        _temp_surf = self.renderer.small_font.render(instruction, True, (180, 200, 160))
        surf.blit(_temp_surf, (center_x - _temp_surf.get_width() // 2, start_y - 75))

        # Moves and efficiency info
        moves_text = f"Moves: {moves}"
        if ideal_moves > 0:
            moves_text += f" (Ideal: {ideal_moves})"
        _temp_surf = self.renderer.small_font.render(moves_text, True, (150, 180, 140))
        surf.blit(_temp_surf, (center_x - 150, start_y - 50))

        efficiency_pct = int(efficiency * 100)
        if efficiency >= 0.9:
            eff_color = (100, 255, 100)
        elif efficiency >= 0.7:
            eff_color = (200, 200, 100)
        else:
            eff_color = (255, 150, 100)
        _temp_surf = self.renderer.small_font.render(f"Efficiency: {efficiency_pct}%", True, eff_color)
        surf.blit(_temp_surf, (center_x + 50, start_y - 50))

        # Calculate slide offset for animation
        slide_offset = 0
        if self._logic_switch_slide_start > 0:
            full_offset = grid_width + 50  # Distance to slide
            if self._logic_switch_slide_from == 'current':
                # Sliding from current to target (slide left)
                slide_offset = int(-full_offset * slide_progress)
            else:
                # Sliding from target to current (slide right)
                slide_offset = int(full_offset * slide_progress)

        # Determine which grid(s) to draw based on animation state
        show_current = self._logic_switch_view == 'current' or self._logic_switch_slide_start > 0
        show_target = self._logic_switch_view == 'target' or self._logic_switch_slide_start > 0

        # Current grid position (centered or sliding)
        if self._logic_switch_view == 'current':
            current_x = center_x - grid_width // 2 + slide_offset
        else:
            current_x = center_x - grid_width // 2 + (grid_width + 50) + slide_offset

        # Target grid position
        if self._logic_switch_view == 'target':
            target_x = center_x - grid_width // 2 + slide_offset
        else:
            target_x = center_x - grid_width // 2 - (grid_width + 50) + slide_offset

        # Draw CURRENT grid (interactive)
        if show_current and current_x > -grid_width and current_x < 1000 + grid_width:
            # Label
            label_color = (100, 200, 140) if self._logic_switch_view == 'current' else (100, 130, 150)
            grid_label = self.renderer.font.render("CURRENT", True, label_color)
            surf.blit(grid_label, (current_x + grid_width // 2 - grid_label.get_width() // 2, start_y - 28))

            for r in range(grid_size):
                for c in range(grid_size):
                    x = current_x + c * cell_size
                    y = start_y + r * cell_size

                    is_on = grid[r][c] == 1
                    target_is_on = target[r][c] == 1
                    matches_target = is_on == target_is_on

                    # Only register click rects if current view is active and visible
                    if self._logic_switch_view == 'current' and self._logic_switch_slide_start == 0:
                        self.engineering_puzzle_rects.append((
                            pygame.Rect(wx + int(x), wy + y, cell_size, cell_size),
                            ('toggle', r, c)
                        ))

                    # Cell background - ON (green) / OFF (dark), with subtle orange if ON but should be OFF
                    if is_on:
                        if matches_target:
                            base_color = (80, 180, 110)  # Bright green for correct ON
                        else:
                            base_color = (160, 120, 70)  # Subtle orange for ON but should be OFF
                    else:
                        base_color = (50, 65, 75)    # Dark gray for OFF

                    pygame.draw.rect(surf, base_color, (int(x) + 2, y + 2, cell_size - 4, cell_size - 4), border_radius=8)

                    # Border - blue trace if OFF but should be ON, orange if ON but should be OFF
                    if matches_target:
                        border_color = (130, 220, 150) if is_on else (80, 120, 100)
                    elif not is_on and target_is_on:
                        # OFF but should be ON - blue trace on surrounding square
                        border_color = (80, 140, 220)  # Noticeable blue
                    else:
                        # ON but should be OFF - orange border
                        border_color = (200, 150, 100)
                    pygame.draw.rect(surf, border_color, (int(x) + 2, y + 2, cell_size - 4, cell_size - 4), 2, border_radius=8)

                    # Switch indicator
                    indicator_size = cell_size // 4
                    cx = int(x) + cell_size // 2
                    cy = y + cell_size // 2

                    if is_on:
                        glow_surf = pygame.Surface((indicator_size * 3, indicator_size * 3), pygame.SRCALPHA)
                        pygame.draw.circle(glow_surf, (100, 220, 130, 100),
                                          (indicator_size * 3 // 2, indicator_size * 3 // 2), indicator_size * 3 // 2)
                        surf.blit(glow_surf, (cx - indicator_size * 3 // 2, cy - indicator_size * 3 // 2))
                        pygame.draw.circle(surf, (130, 240, 160), (cx, cy), indicator_size)
                    else:
                        if not matches_target:
                            # OFF but should be ON - blue trace on circle too
                            pygame.draw.circle(surf, (60, 100, 160), (cx, cy), indicator_size)
                            pygame.draw.circle(surf, (80, 140, 220), (cx, cy), indicator_size, 2)  # Blue ring
                        else:
                            pygame.draw.circle(surf, (60, 75, 90), (cx, cy), indicator_size)

        # Draw TARGET grid (reference only)
        if show_target and target_x > -grid_width and target_x < 1000 + grid_width:
            # Label
            label_color = (100, 200, 140) if self._logic_switch_view == 'target' else (100, 130, 150)
            grid_label = self.renderer.font.render("TARGET", True, label_color)
            surf.blit(grid_label, (target_x + grid_width // 2 - grid_label.get_width() // 2, start_y - 28))

            for r in range(grid_size):
                for c in range(grid_size):
                    x = target_x + c * cell_size
                    y = start_y + r * cell_size

                    is_on = target[r][c] == 1

                    # Softer colors for target (reference only)
                    if is_on:
                        base_color = (60, 130, 90)
                    else:
                        base_color = (40, 50, 60)

                    pygame.draw.rect(surf, base_color, (int(x) + 2, y + 2, cell_size - 4, cell_size - 4), border_radius=8)
                    pygame.draw.rect(surf, (80, 100, 120), (int(x) + 2, y + 2, cell_size - 4, cell_size - 4), 2, border_radius=8)

                    # Switch indicator
                    indicator_size = cell_size // 4
                    cx = int(x) + cell_size // 2
                    cy = y + cell_size // 2

                    if is_on:
                        pygame.draw.circle(surf, (100, 180, 130), (cx, cy), indicator_size)
                    else:
                        pygame.draw.circle(surf, (55, 65, 75), (cx, cy), indicator_size)

        # Buttons row: View Toggle and Reset
        btn_y = start_y + grid_width + 25
        btn_w, btn_h = 160, 40
        is_animating = self._logic_switch_slide_start > 0

        # View toggle button (left)
        view_btn_x = center_x - btn_w - 10
        view_btn_rect = pygame.Rect(view_btn_x, btn_y, btn_w, btn_h)

        if is_animating:
            btn_color = (60, 65, 70)
            btn_border = (90, 100, 110)
        else:
            btn_color = (70, 90, 110)
            btn_border = (120, 160, 200)

        pygame.draw.rect(surf, btn_color, view_btn_rect, border_radius=8)
        pygame.draw.rect(surf, btn_border, view_btn_rect, 2, border_radius=8)

        if self._logic_switch_view == 'current':
            btn_text = "◄ View TARGET ►"
        else:
            btn_text = "◄ View CURRENT ►"
        _temp_surf = self.renderer.small_font.render(btn_text, True, (180, 200, 220))
        surf.blit(_temp_surf, (view_btn_x + btn_w // 2 - _temp_surf.get_width() // 2, btn_y + btn_h // 2 - _temp_surf.get_height() // 2))

        if not is_animating:
            self.engineering_puzzle_rects.append((
                pygame.Rect(wx + view_btn_x, wy + btn_y, btn_w, btn_h),
                ('view_toggle', 0, 0)
            ))

        # Reset button (right)
        reset_btn_x = center_x + 10
        reset_btn_rect = pygame.Rect(reset_btn_x, btn_y, btn_w, btn_h)

        reset_color = (110, 70, 70)
        reset_border = (180, 100, 100)
        pygame.draw.rect(surf, reset_color, reset_btn_rect, border_radius=8)
        pygame.draw.rect(surf, reset_border, reset_btn_rect, 2, border_radius=8)

        reset_text = "↻ RESET"
        _temp_surf = self.renderer.small_font.render(reset_text, True, (255, 200, 200))
        surf.blit(_temp_surf, (reset_btn_x + btn_w // 2 - _temp_surf.get_width() // 2, btn_y + btn_h // 2 - _temp_surf.get_height() // 2))

        self.engineering_puzzle_rects.append((
            pygame.Rect(wx + reset_btn_x, wy + btn_y, btn_w, btn_h),
            ('reset', 0, 0)
        ))

        # Hint about toggle mechanic
        hint = "Click switch to toggle it + adjacent cells"
        _temp_surf = self.renderer.tiny_font.render(hint, True, (120, 140, 160))
        surf.blit(_temp_surf, (center_x - _temp_surf.get_width() // 2, btn_y + btn_h + 15))

    def _render_enchanting_minigame(self):
        """Render enchanting wheel minigame UI with light blue spirit aesthetic"""
        if not self.active_minigame:
            return

        state = self.active_minigame.get_state()
        effects = get_effects_manager()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        # Initialize effects if needed
        if not hasattr(self, '_enchanting_effects_initialized') or not self._enchanting_effects_initialized:
            effects.initialize_discipline('enchanting', pygame.Rect(wx, wy, ww, wh))
            self._enchanting_effects_initialized = True
            # Show metadata overlay
            difficulty_tier = getattr(self.active_minigame, 'difficulty_tier', 'Unknown')
            difficulty_points = getattr(self.active_minigame, 'difficulty_points', 0)
            effects.show_metadata({
                'discipline': 'Enchanting',
                'difficulty_tier': difficulty_tier,
                'difficulty_points': difficulty_points,
                'time_limit': None,  # No time limit for enchanting
                'max_bonus': 1.0 + difficulty_points * 0.025,
                'special_params': {
                    'Starting Currency': state.get('current_currency', 100),
                    'Spins': '3'
                }
            })

        dt = 1/60
        effects.update(dt)
        tick = pygame.time.get_ticks()

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)

        # Light blue spirit gradient background
        for y in range(wh):
            progress = y / wh
            r = int(20 + 25 * progress)
            g = int(35 + 30 * progress)
            b = int(55 + 20 * progress)
            pygame.draw.line(surf, (r, g, b), (0, y), (ww, y))

        # Floating spirit particles
        for i in range(25):
            particle_phase = tick * 0.001 + i * 0.5
            px = 50 + (i * 37) % (ww - 100) + math.sin(particle_phase) * 30
            py = 50 + (i * 53) % (wh - 100) + math.cos(particle_phase * 0.7) * 25
            particle_size = 3 + int(2 * math.sin(particle_phase * 2))
            particle_alpha = int(80 + 60 * math.sin(particle_phase * 1.5))

            particle_surf = pygame.Surface((particle_size * 4, particle_size * 4), pygame.SRCALPHA)
            # Soft glow
            pygame.draw.circle(particle_surf, (150, 200, 255, particle_alpha // 3),
                             (particle_size * 2, particle_size * 2), particle_size * 2)
            # Core
            pygame.draw.circle(particle_surf, (180, 220, 255, particle_alpha),
                             (particle_size * 2, particle_size * 2), particle_size)
            surf.blit(particle_surf, (int(px), int(py)))

        # Central aura glow
        aura_intensity = 0.5 + 0.3 * math.sin(tick * 0.002)
        for r in range(150, 0, -10):
            alpha = int(25 * (r / 150) * aura_intensity)
            aura_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura_surf, (100, 180, 240, alpha), (r, r), r)
            surf.blit(aura_surf, (ww//2 - r, 350 - r))

        # Header with spirit theme
        header = self.renderer.font.render("SPIRIT WHEEL", True, (150, 200, 255))
        surf.blit(header, (ww//2 - header.get_width()//2, 18))
        sub_header = self.renderer.small_font.render("Channel the spirits to enhance your item", True, (120, 160, 200))
        surf.blit(sub_header, (ww//2 - sub_header.get_width()//2, 48))

        # Currency panel (left side)
        currency_panel_x, currency_panel_y = 50, 90
        currency_panel_w, currency_panel_h = 160, 80

        pygame.draw.rect(surf, (30, 45, 60, 200), (currency_panel_x, currency_panel_y, currency_panel_w, currency_panel_h), border_radius=10)
        pygame.draw.rect(surf, (100, 150, 200), (currency_panel_x, currency_panel_y, currency_panel_w, currency_panel_h), 2, border_radius=10)

        currency_label = self.renderer.small_font.render("Essence", True, (150, 180, 210))
        surf.blit(currency_label, (currency_panel_x + currency_panel_w//2 - currency_label.get_width()//2, currency_panel_y + 10))

        current_currency = state.get('current_currency', 100)
        currency_text = self.renderer.font.render(str(current_currency), True, (150, 255, 200))
        surf.blit(currency_text, (currency_panel_x + currency_panel_w//2 - currency_text.get_width()//2, currency_panel_y + 35))

        # Spin counter panel (right side)
        spin_panel_x, spin_panel_y = ww - 210, 90
        spin_panel_w, spin_panel_h = 160, 80

        pygame.draw.rect(surf, (30, 45, 60, 200), (spin_panel_x, spin_panel_y, spin_panel_w, spin_panel_h), border_radius=10)
        pygame.draw.rect(surf, (100, 150, 200), (spin_panel_x, spin_panel_y, spin_panel_w, spin_panel_h), 2, border_radius=10)

        spin_label = self.renderer.small_font.render("Spin", True, (150, 180, 210))
        surf.blit(spin_label, (spin_panel_x + spin_panel_w//2 - spin_label.get_width()//2, spin_panel_y + 10))

        spin_num = state.get('current_spin_number', 0) + 1
        spin_text = self.renderer.font.render(f"{spin_num} / 3", True, (180, 200, 230))
        surf.blit(spin_text, (spin_panel_x + spin_panel_w//2 - spin_text.get_width()//2, spin_panel_y + 35))

        # Phase-specific rendering
        phase = state.get('phase', 'betting')

        # Wheel area with spirit theme
        wheel_center = (ww // 2, 350)
        wheel_radius = 170
        wheel_visible = state.get('wheel_visible', False)

        if wheel_visible:
            # Draw spinning wheel with spirit colors
            current_wheel = state.get('current_wheel', [])
            wheel_rotation = state.get('wheel_rotation', 0.0)

            if current_wheel:
                # Outer glow ring
                for r in range(wheel_radius + 30, wheel_radius, -3):
                    glow_alpha = int(40 * (1 - (r - wheel_radius) / 30))
                    glow_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, (100, 180, 255, glow_alpha), (r, r), r, 3)
                    surf.blit(glow_surf, (wheel_center[0] - r, wheel_center[1] - r))

                # Wheel background
                pygame.draw.circle(surf, (35, 50, 65), wheel_center, wheel_radius)

                # Draw 20 slices with spirit-themed colors
                slice_angle = 360 / 20
                color_map = {
                    'green': (80, 200, 150),   # Spirit green
                    'red': (200, 100, 120),    # Soft red
                    'grey': (100, 130, 160)    # Spirit grey
                }

                for i, color_name in enumerate(current_wheel):
                    start_angle = i * slice_angle - wheel_rotation - 90
                    end_angle = (i + 1) * slice_angle - wheel_rotation - 90
                    start_rad = math.radians(start_angle)
                    end_rad = math.radians(end_angle)

                    points = [wheel_center]
                    num_arc_points = 5
                    for j in range(num_arc_points + 1):
                        angle = start_rad + (end_rad - start_rad) * (j / num_arc_points)
                        px = wheel_center[0] + int(wheel_radius * math.cos(angle))
                        py = wheel_center[1] + int(wheel_radius * math.sin(angle))
                        points.append((px, py))

                    color = color_map.get(color_name, (100, 130, 160))
                    pygame.draw.polygon(surf, color, points)
                    pygame.draw.polygon(surf, (60, 80, 100), points, 2)

                # Spirit pointer at top
                pointer_points = [
                    (wheel_center[0], wheel_center[1] - wheel_radius - 25),
                    (wheel_center[0] - 18, wheel_center[1] - wheel_radius - 5),
                    (wheel_center[0] + 18, wheel_center[1] - wheel_radius - 5)
                ]
                pygame.draw.polygon(surf, (150, 220, 255), pointer_points)
                pygame.draw.polygon(surf, (100, 160, 200), pointer_points, 2)

                # Center spirit orb
                orb_pulse = 0.8 + 0.2 * math.sin(tick * 0.005)
                pygame.draw.circle(surf, (50, 70, 90), wheel_center, 35)
                pygame.draw.circle(surf, (100, 160, 220), wheel_center, int(25 * orb_pulse))
                pygame.draw.circle(surf, (150, 200, 255), wheel_center, int(15 * orb_pulse))
                pygame.draw.circle(surf, (120, 170, 220), wheel_center, 35, 3)
        else:
            # Wheel hidden - mysterious spirit orb
            orb_pulse = 0.7 + 0.3 * math.sin(tick * 0.003)
            pygame.draw.circle(surf, (40, 55, 70), wheel_center, int(100 * orb_pulse))
            pygame.draw.circle(surf, (60, 90, 120), wheel_center, int(70 * orb_pulse))
            pygame.draw.circle(surf, (80, 130, 170, 150), wheel_center, int(100 * orb_pulse), 3)

            mystery_text = self.renderer.font.render("?", True, (120, 170, 220))
            text_rect = mystery_text.get_rect(center=wheel_center)
            surf.blit(mystery_text, text_rect)

            hint_text = self.renderer.small_font.render("Place bet to reveal the wheel", True, (100, 140, 180))
            hint_rect = hint_text.get_rect(center=(wheel_center[0], wheel_center[1] + 60))
            surf.blit(hint_text, hint_rect)

        # Payout display panel (right side) - Spirit themed
        current_multiplier = state.get('current_multiplier', {})
        if current_multiplier:
            panel_x = ww - 220
            panel_y = 180
            panel_w = 200
            panel_h = 260

            # Spirit panel background with soft glow
            panel_surf = pygame.Surface((panel_w + 10, panel_h + 10), pygame.SRCALPHA)
            pygame.draw.rect(panel_surf, (30, 45, 60, 200), (5, 5, panel_w, panel_h), border_radius=12)
            pygame.draw.rect(panel_surf, (100, 160, 200, 150), (5, 5, panel_w, panel_h), 2, border_radius=12)
            surf.blit(panel_surf, (panel_x - 5, panel_y - 5))

            # Title with spirit glow
            _temp_surf = self.renderer.small_font.render("SPIRIT PAYOUTS", True, (150, 200, 255))
            surf.blit(_temp_surf, (panel_x + panel_w//2 - _temp_surf.get_width()//2, panel_y + 10))

            _temp_surf = self.renderer.tiny_font.render(f"(Spin {spin_num})", True, (120, 160, 190))
            surf.blit(_temp_surf, (panel_x + panel_w//2 - _temp_surf.get_width()//2, panel_y + 32))

            # Color labels and multipliers
            color_y = panel_y + 60
            spacing = 60

            # Green - Spirit green
            pygame.draw.rect(surf, (80, 200, 150), (panel_x + 20, color_y, 40, 40), border_radius=6)
            pygame.draw.rect(surf, (100, 220, 170), (panel_x + 20, color_y, 40, 40), 2, border_radius=6)
            _temp_surf = self.renderer.small_font.render("GREEN", True, (180, 220, 200))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('green', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (100, 255, 180))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 20))

            # Grey - Spirit grey
            color_y += spacing
            pygame.draw.rect(surf, (100, 130, 160), (panel_x + 20, color_y, 40, 40), border_radius=6)
            pygame.draw.rect(surf, (120, 150, 180), (panel_x + 20, color_y, 40, 40), 2, border_radius=6)
            _temp_surf = self.renderer.small_font.render("GREY", True, (160, 180, 200))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('grey', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (180, 200, 220))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 20))

            # Red - Soft spirit red
            color_y += spacing
            pygame.draw.rect(surf, (200, 100, 120), (panel_x + 20, color_y, 40, 40), border_radius=6)
            pygame.draw.rect(surf, (220, 120, 140), (panel_x + 20, color_y, 40, 40), 2, border_radius=6)
            _temp_surf = self.renderer.small_font.render("RED", True, (220, 180, 190))
            surf.blit(_temp_surf, (panel_x + 70, color_y + 5))
            mult_text = f"{current_multiplier.get('red', 0)}x"
            _temp_surf = self.renderer.font.render(mult_text, True, (255, 150, 170))
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
                # Spirit themed button colors
                if amount <= current_currency:
                    btn_color = (50, 80, 100)
                    border_color = (100, 160, 200)
                else:
                    btn_color = (40, 50, 60)
                    border_color = (70, 90, 110)

                pygame.draw.rect(surf, btn_color, btn_rect, border_radius=6)
                pygame.draw.rect(surf, border_color, btn_rect, 2, border_radius=6)
                _temp_surf = self.renderer.tiny_font.render(btn_text, True, (180, 210, 240))
                text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + 20 + btn_h//2))
                surf.blit(_temp_surf, text_rect)

                # Store for click detection (in screen coordinates)
                bet_button_rects.append((pygame.Rect(wx + btn_x, wy + btn_y + 20, btn_w, btn_h), amount))

            self.wheel_bet_buttons = bet_button_rects

            # Confirm bet button - Spirit themed
            confirm_x, confirm_y = ww//2 - 100, 630
            confirm_w, confirm_h = 200, 50
            confirm_btn_rect = pygame.Rect(confirm_x, confirm_y, confirm_w, confirm_h)
            confirm_enabled = self.wheel_slider_bet_amount > 0 and self.wheel_slider_bet_amount <= current_currency

            if confirm_enabled:
                confirm_color = (60, 100, 140)
                border_color = (100, 180, 240)
            else:
                confirm_color = (40, 55, 70)
                border_color = (70, 100, 130)

            pygame.draw.rect(surf, confirm_color, confirm_btn_rect, border_radius=10)
            pygame.draw.rect(surf, border_color, confirm_btn_rect, 3, border_radius=10)
            _temp_surf = self.renderer.font.render("CHANNEL SPIRITS", True, (150, 200, 255))
            text_rect = _temp_surf.get_rect(center=(confirm_x + confirm_w//2, confirm_y + confirm_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_confirm_bet_button = pygame.Rect(wx + confirm_x, wy + confirm_y, confirm_w, confirm_h)

        elif phase == 'ready_to_spin':
            # Show current bet and spin button - Spirit themed
            current_bet = state.get('current_bet', 0)
            _temp_surf = self.renderer.small_font.render(f"Essence Wagered: {current_bet}", True, (150, 200, 255))
            surf.blit(_temp_surf, (50, 600))

            # Spin button - Spirit themed with glow
            btn_x, btn_y = ww//2 - 100, 620
            btn_w, btn_h = 200, 50
            spin_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

            # Button glow effect
            glow_intensity = 0.7 + 0.3 * math.sin(tick * 0.005)
            glow_surf = pygame.Surface((btn_w + 20, btn_h + 20), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (100, 180, 240, int(60 * glow_intensity)),
                           (0, 0, btn_w + 20, btn_h + 20), border_radius=15)
            surf.blit(glow_surf, (btn_x - 10, btn_y - 10))

            pygame.draw.rect(surf, (60, 100, 140), spin_btn_rect, border_radius=10)
            pygame.draw.rect(surf, (100, 180, 240), spin_btn_rect, 3, border_radius=10)
            _temp_surf = self.renderer.font.render("SPIN THE WHEEL", True, (180, 220, 255))
            text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + btn_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_spin_button = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

        elif phase == 'spinning':
            # Show spinning message - Spirit themed with pulsing
            pulse = 0.7 + 0.3 * math.sin(tick * 0.008)
            spin_color = (int(150 * pulse), int(200 * pulse), 255)
            _temp_surf = self.renderer.font.render("CHANNELING...", True, spin_color)
            text_rect = _temp_surf.get_rect(center=(ww//2, 620))
            surf.blit(_temp_surf, text_rect)
            self.wheel_spin_button = None

        elif phase == 'spin_result':
            # Show result of this spin - Spirit themed
            spin_results = state.get('spin_results', [])
            if spin_results:
                last_result = spin_results[-1]
                result_y = 580

                color_text = last_result['color'].upper()
                profit = last_result['profit']
                profit_text = f"+{profit}" if profit >= 0 else f"-{abs(profit)}"

                # Spirit-themed result colors
                if profit >= 0:
                    profit_color = (100, 255, 180)  # Spirit green
                else:
                    profit_color = (255, 150, 170)  # Spirit red

                # Result panel
                result_panel = pygame.Surface((300, 80), pygame.SRCALPHA)
                pygame.draw.rect(result_panel, (30, 45, 60, 200), (0, 0, 300, 80), border_radius=10)
                pygame.draw.rect(result_panel, (100, 160, 200), (0, 0, 300, 80), 2, border_radius=10)
                surf.blit(result_panel, (ww//2 - 150, result_y - 10))

                _temp_surf = self.renderer.small_font.render(f"Spirit landed on: {color_text}", True, (180, 210, 240))
                surf.blit(_temp_surf, (ww//2 - _temp_surf.get_width()//2, result_y))
                _temp_surf = self.renderer.font.render(profit_text, True, profit_color)
                surf.blit(_temp_surf, (ww//2 - _temp_surf.get_width()//2, result_y + 28))

            # Next button - Spirit themed
            btn_x, btn_y = ww//2 - 100, 650
            btn_w, btn_h = 200, 40
            next_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            pygame.draw.rect(surf, (50, 80, 100), next_btn_rect, border_radius=8)
            pygame.draw.rect(surf, (100, 160, 200), next_btn_rect, 2, border_radius=8)
            btn_text = "CONTINUE" if spin_num < 3 else "COMPLETE RITUAL"
            _temp_surf = self.renderer.small_font.render(btn_text, True, (180, 210, 240))
            text_rect = _temp_surf.get_rect(center=(btn_x + btn_w//2, btn_y + btn_h//2))
            surf.blit(_temp_surf, text_rect)

            self.wheel_next_button = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

        elif phase == 'completed':
            # Show final result - Spirit themed
            result = state.get('result', {})
            if result:
                efficacy_percent = result.get('efficacy_percent', 0)
                final_currency = result.get('final_currency', 100)
                currency_diff = result.get('currency_diff', 0)

                # Spirit-themed result panel
                result_surf = pygame.Surface((600, 350), pygame.SRCALPHA)

                # Gradient background
                for y in range(350):
                    progress = y / 350
                    r = int(25 + 15 * progress)
                    g = int(40 + 20 * progress)
                    b = int(60 + 15 * progress)
                    pygame.draw.line(result_surf, (r, g, b, 240), (0, y), (600, y))

                # Border with glow
                pygame.draw.rect(result_surf, (100, 160, 200), (0, 0, 600, 350), 3, border_radius=15)

                # Title with spirit glow
                title_text = "SPIRITS APPEASED"
                _temp_surf = self.renderer.font.render(title_text, True, (150, 220, 255))
                result_surf.blit(_temp_surf, (300 - _temp_surf.get_width()//2, 30))

                # Decorative spirit swirl
                for i in range(8):
                    angle = tick * 0.002 + i * (math.pi / 4)
                    r = 40 + 10 * math.sin(tick * 0.003 + i)
                    px = 300 + int(r * math.cos(angle))
                    py = 80 + int(r * 0.3 * math.sin(angle))
                    pygame.draw.circle(result_surf, (100, 180, 240, 100), (px, py), 4)

                # Stats display
                _temp_surf = self.renderer.small_font.render(f"Final Essence: {final_currency}", True, (180, 200, 220))
                result_surf.blit(_temp_surf, (300 - _temp_surf.get_width()//2, 120))

                diff_text = f"+{currency_diff}" if currency_diff >= 0 else f"-{abs(currency_diff)}"
                diff_color = (100, 255, 180) if currency_diff >= 0 else (255, 150, 170)
                _temp_surf = self.renderer.small_font.render(f"Spirit Gift: {diff_text}", True, diff_color)
                result_surf.blit(_temp_surf, (300 - _temp_surf.get_width()//2, 155))

                # Main efficacy display
                eff_text = f"{efficacy_percent:+.1f}%"
                eff_color = (100, 255, 180) if efficacy_percent >= 0 else (255, 150, 170)
                _temp_surf = self.renderer.font.render(f"Enchantment Power: {eff_text}", True, eff_color)
                result_surf.blit(_temp_surf, (300 - _temp_surf.get_width()//2, 210))

                _temp_surf = self.renderer.small_font.render("Click anywhere to continue", True, (120, 150, 180))
                result_surf.blit(_temp_surf, (300 - _temp_surf.get_width()//2, 290))

                surf.blit(result_surf, (ww//2 - 300, wh//2 - 175))

        # Draw metadata overlay if active
        effects.metadata_overlay.draw(surf, (ww//2, wh//2), self.renderer.small_font)

        # Reset effects when minigame ends
        if state.get('result'):
            self._enchanting_effects_initialized = False

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
