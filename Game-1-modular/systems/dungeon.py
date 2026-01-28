"""
Dungeon System - Instanced dungeon encounters with waves of enemies and loot chests.

Dungeons are separate 2x2 chunk instances (32x32 tiles) that players enter.
Each dungeon has a rarity that determines mob count, difficulty, and rewards.

Rarity Distribution:
- Common (25%): 20 mobs, mostly T1
- Uncommon (30%): 30 mobs, T1-T2 mix
- Rare (20%): 40 mobs, T2-T3 mix
- Epic (15%): 50 mobs, mostly T3
- Legendary (8%): 50 mobs, T3-T4 heavy
- Unique (2%): 50 mobs, almost all T4

Features:
- 3 waves of enemies per dungeon
- 2x EXP from dungeon mobs
- No material drops from dungeon mobs
- Loot chest appears after clearing all waves
- Save/load support for mid-dungeon saves
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import random
import time

from data.models.world import (
    Position, TileType, WorldTile, PlacedEntityType,
    DungeonRarity, DUNGEON_CONFIG
)
from core.config import Config


# Dungeon size constants
DUNGEON_CHUNK_SIZE = 2  # 2x2 chunks
DUNGEON_TILE_SIZE = DUNGEON_CHUNK_SIZE * Config.CHUNK_SIZE  # 32x32 tiles


@dataclass
class LootChest:
    """
    A loot chest entity that can contain items, materials, weapons, and consumables.

    Designed to be reusable for:
    - Dungeon reward chests (generated loot based on tier)
    - Future: Player-placed storage chests
    """
    position: Position
    tier: int = 1  # 1-3, affects loot quality
    is_opened: bool = False
    contents: List[Tuple[str, int]] = field(default_factory=list)  # [(item_id, quantity), ...]
    is_player_storage: bool = False  # If True, player can store items
    chest_id: str = ""  # Unique identifier for save/load

    def __post_init__(self):
        if not self.chest_id:
            self.chest_id = f"chest_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        if not self.contents and not self.is_player_storage:
            self._generate_loot()

    def _generate_loot(self):
        """Generate random loot based on chest tier."""
        # Import here to avoid circular dependency
        from data.databases.material_db import MaterialDatabase
        from data.databases.equipment_db import EquipmentDatabase

        self.contents = []

        # Number of items based on tier
        num_items = random.randint(2 + self.tier, 4 + self.tier * 2)

        # Loot pools by tier
        # T1: Common materials, basic consumables
        # T2: Uncommon materials, equipment, potions
        # T3: Rare materials, rare equipment, powerful consumables

        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        # Get materials by tier
        all_materials = list(mat_db.materials.values()) if hasattr(mat_db, 'materials') else []

        for _ in range(num_items):
            roll = random.random()

            if roll < 0.50:  # 50% chance for materials
                # Filter materials by tier (chest tier +/- 1)
                valid_materials = [
                    m for m in all_materials
                    if hasattr(m, 'tier') and abs(m.tier - self.tier) <= 1
                ]
                if valid_materials:
                    mat = random.choice(valid_materials)
                    mat_id = mat.material_id if hasattr(mat, 'material_id') else mat.get('materialId', 'oak_log')
                    qty = random.randint(1, 3 + self.tier)
                    self.contents.append((mat_id, qty))

            elif roll < 0.75:  # 25% chance for equipment
                # Get equipment items matching tier
                valid_equipment = []
                if hasattr(equip_db, 'equipment'):
                    for eq in equip_db.equipment.values():
                        eq_tier = eq.tier if hasattr(eq, 'tier') else eq.get('tier', 1)
                        if abs(eq_tier - self.tier) <= 1:
                            valid_equipment.append(eq)

                if valid_equipment:
                    eq = random.choice(valid_equipment)
                    eq_id = eq.item_id if hasattr(eq, 'item_id') else eq.get('itemId', 'iron_sword')
                    self.contents.append((eq_id, 1))

            elif roll < 0.90:  # 15% chance for consumables
                # Common consumables by tier
                consumables = {
                    1: ["health_potion_minor", "mana_potion_minor"],
                    2: ["health_potion", "mana_potion", "stamina_potion"],
                    3: ["health_potion_major", "mana_potion_major", "elixir_of_power"]
                }
                tier_consumables = consumables.get(self.tier, consumables[1])
                self.contents.append((random.choice(tier_consumables), random.randint(1, 2)))

            else:  # 10% chance for engineering items (turrets, traps)
                engineering_items = {
                    1: ["basic_turret", "spike_trap"],
                    2: ["flame_turret", "frost_trap", "lightning_turret"],
                    3: ["void_turret", "chaos_trap", "plasma_turret"]
                }
                tier_items = engineering_items.get(self.tier, engineering_items[1])
                self.contents.append((random.choice(tier_items), 1))

    def open(self) -> List[Tuple[str, int]]:
        """Open the chest and return its contents."""
        if self.is_opened:
            return []
        self.is_opened = True
        return self.contents.copy()

    def add_item(self, item_id: str, quantity: int = 1) -> bool:
        """Add an item to a player storage chest."""
        if not self.is_player_storage:
            return False
        # Find existing stack or add new
        for i, (existing_id, existing_qty) in enumerate(self.contents):
            if existing_id == item_id:
                self.contents[i] = (item_id, existing_qty + quantity)
                return True
        self.contents.append((item_id, quantity))
        return True

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """Remove an item from a player storage chest."""
        if not self.is_player_storage:
            return False
        for i, (existing_id, existing_qty) in enumerate(self.contents):
            if existing_id == item_id:
                if existing_qty >= quantity:
                    new_qty = existing_qty - quantity
                    if new_qty > 0:
                        self.contents[i] = (item_id, new_qty)
                    else:
                        self.contents.pop(i)
                    return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize chest to dictionary for saving."""
        return {
            "chest_id": self.chest_id,
            "position": {"x": self.position.x, "y": self.position.y, "z": self.position.z},
            "tier": self.tier,
            "is_opened": self.is_opened,
            "contents": self.contents,
            "is_player_storage": self.is_player_storage
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LootChest':
        """Deserialize chest from dictionary."""
        pos_data = data.get("position", {"x": 0, "y": 0, "z": 0})
        chest = cls(
            position=Position(pos_data["x"], pos_data["y"], pos_data.get("z", 0)),
            tier=data.get("tier", 1),
            is_opened=data.get("is_opened", False),
            is_player_storage=data.get("is_player_storage", False),
            chest_id=data.get("chest_id", "")
        )
        chest.contents = [tuple(item) for item in data.get("contents", [])]
        return chest


@dataclass
class DungeonInstance:
    """
    A single dungeon instance with waves of enemies.

    The dungeon is a 2x2 chunk area (32x32 tiles) separate from the main world.
    Players enter, defeat 3 waves of enemies, then collect loot from a chest.
    """
    rarity: DungeonRarity
    dungeon_id: str = ""

    # Wave state
    current_wave: int = 1
    total_waves: int = 3
    wave_enemies_remaining: int = 0
    total_enemies_killed: int = 0

    # Dungeon state
    is_cleared: bool = False
    is_active: bool = True
    entrance_time: float = 0.0

    # World state
    tiles: Dict[str, WorldTile] = field(default_factory=dict)
    chest: Optional[LootChest] = None

    # Player's original position (to return after dungeon)
    return_position: Optional[Position] = None

    # Enemies spawned (managed by combat_manager, tracked here for save/load)
    spawned_enemy_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.dungeon_id:
            self.dungeon_id = f"dungeon_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        if not self.tiles:
            self._generate_tiles()
        if not self.chest:
            self._create_chest()
        self.entrance_time = time.time()

    def _generate_tiles(self):
        """Generate the 32x32 dungeon floor."""
        self.tiles = {}

        # Dungeon uses a stone/dirt floor theme
        for x in range(DUNGEON_TILE_SIZE):
            for y in range(DUNGEON_TILE_SIZE):
                # Edge tiles are walls (non-walkable)
                is_edge = x == 0 or y == 0 or x == DUNGEON_TILE_SIZE - 1 or y == DUNGEON_TILE_SIZE - 1

                # Mix of stone and dirt for dungeon floor
                if is_edge:
                    tile_type = TileType.STONE
                    walkable = False
                else:
                    tile_type = TileType.STONE if random.random() < 0.7 else TileType.DIRT
                    walkable = True

                pos = Position(x, y, 0)
                self.tiles[pos.to_key()] = WorldTile(
                    position=pos,
                    tile_type=tile_type,
                    walkable=walkable
                )

    def _create_chest(self):
        """Create the reward chest at the center of the dungeon."""
        config = DUNGEON_CONFIG[self.rarity]
        center = DUNGEON_TILE_SIZE // 2
        self.chest = LootChest(
            position=Position(center, center, 0),
            tier=config["chest_tier"]
        )

    @property
    def config(self) -> Dict[str, Any]:
        """Get configuration for this dungeon's rarity."""
        return DUNGEON_CONFIG[self.rarity]

    @property
    def total_mobs(self) -> int:
        """Total number of mobs for this dungeon."""
        return self.config["total_mobs"]

    @property
    def mobs_per_wave(self) -> List[int]:
        """Number of mobs per wave (roughly equal split across 3 waves)."""
        total = self.total_mobs
        base = total // self.total_waves
        remainder = total % self.total_waves

        waves = [base] * self.total_waves
        # Distribute remainder to later waves (harder)
        for i in range(remainder):
            waves[self.total_waves - 1 - i] += 1

        return waves

    def get_current_wave_mob_count(self) -> int:
        """Get number of mobs for the current wave."""
        if self.current_wave > self.total_waves:
            return 0
        return self.mobs_per_wave[self.current_wave - 1]

    def get_enemy_tier_for_spawn(self) -> int:
        """Select an enemy tier based on rarity weights."""
        tier_weights = self.config["tier_weights"]
        total = sum(tier_weights.values())
        roll = random.randint(1, total)

        cumulative = 0
        for tier, weight in tier_weights.items():
            cumulative += weight
            if roll <= cumulative:
                return tier
        return 1  # Fallback

    def get_spawn_position(self) -> Position:
        """Get a valid spawn position for an enemy."""
        margin = 3  # Stay away from walls
        x = random.randint(margin, DUNGEON_TILE_SIZE - margin - 1)
        y = random.randint(margin, DUNGEON_TILE_SIZE - margin - 1)

        # Avoid spawning too close to center (where player spawns)
        center = DUNGEON_TILE_SIZE // 2
        while abs(x - center) < 5 and abs(y - center) < 5:
            x = random.randint(margin, DUNGEON_TILE_SIZE - margin - 1)
            y = random.randint(margin, DUNGEON_TILE_SIZE - margin - 1)

        return Position(x, y, 0)

    def get_player_spawn_position(self) -> Position:
        """Get the player's spawn position in the dungeon."""
        center = DUNGEON_TILE_SIZE // 2
        return Position(center, center + 5, 0)  # Slightly south of center

    def start_wave(self) -> int:
        """Start the current wave and return number of enemies to spawn."""
        if self.current_wave > self.total_waves:
            return 0

        mob_count = self.get_current_wave_mob_count()
        self.wave_enemies_remaining = mob_count
        return mob_count

    def enemy_killed(self):
        """Called when an enemy in this dungeon is killed."""
        self.wave_enemies_remaining = max(0, self.wave_enemies_remaining - 1)
        self.total_enemies_killed += 1

        # Check if wave is complete
        if self.wave_enemies_remaining <= 0:
            if self.current_wave >= self.total_waves:
                self.is_cleared = True
            else:
                self.current_wave += 1

    def is_wave_complete(self) -> bool:
        """Check if the current wave is complete."""
        return self.wave_enemies_remaining <= 0

    def get_progress(self) -> Tuple[int, int, int]:
        """Get dungeon progress: (current_wave, enemies_killed, total_enemies)."""
        return (self.current_wave, self.total_enemies_killed, self.total_mobs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize dungeon instance for saving."""
        return {
            "dungeon_id": self.dungeon_id,
            "rarity": self.rarity.value,
            "current_wave": self.current_wave,
            "total_waves": self.total_waves,
            "wave_enemies_remaining": self.wave_enemies_remaining,
            "total_enemies_killed": self.total_enemies_killed,
            "is_cleared": self.is_cleared,
            "is_active": self.is_active,
            "entrance_time": self.entrance_time,
            "chest": self.chest.to_dict() if self.chest else None,
            "return_position": {
                "x": self.return_position.x,
                "y": self.return_position.y,
                "z": self.return_position.z
            } if self.return_position else None,
            "spawned_enemy_ids": self.spawned_enemy_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DungeonInstance':
        """Deserialize dungeon instance from save data."""
        rarity = DungeonRarity(data.get("rarity", "common"))

        instance = cls(
            rarity=rarity,
            dungeon_id=data.get("dungeon_id", "")
        )

        instance.current_wave = data.get("current_wave", 1)
        instance.total_waves = data.get("total_waves", 3)
        instance.wave_enemies_remaining = data.get("wave_enemies_remaining", 0)
        instance.total_enemies_killed = data.get("total_enemies_killed", 0)
        instance.is_cleared = data.get("is_cleared", False)
        instance.is_active = data.get("is_active", True)
        instance.entrance_time = data.get("entrance_time", time.time())
        instance.spawned_enemy_ids = data.get("spawned_enemy_ids", [])

        if data.get("chest"):
            instance.chest = LootChest.from_dict(data["chest"])

        if data.get("return_position"):
            rp = data["return_position"]
            instance.return_position = Position(rp["x"], rp["y"], rp.get("z", 0))

        return instance


class DungeonManager:
    """
    Manages dungeon instances, entry/exit, and wave spawning.

    Integrates with:
    - GameEngine: For player position, rendering context
    - CombatManager: For enemy spawning with dungeon modifiers
    - SaveManager: For persisting dungeon state
    - StatTracker: For tracking dungeon statistics
    """

    def __init__(self):
        self.current_dungeon: Optional[DungeonInstance] = None
        self.in_dungeon: bool = False

        # Dungeon statistics (also tracked in StatTracker)
        self.dungeons_completed: int = 0
        self.dungeons_by_rarity: Dict[str, int] = {r.value: 0 for r in DungeonRarity}

    @staticmethod
    def roll_dungeon_rarity() -> DungeonRarity:
        """Roll for dungeon rarity based on spawn weights."""
        total_weight = sum(DUNGEON_CONFIG[r]["spawn_weight"] for r in DungeonRarity)
        roll = random.randint(1, total_weight)

        cumulative = 0
        for rarity in DungeonRarity:
            cumulative += DUNGEON_CONFIG[rarity]["spawn_weight"]
            if roll <= cumulative:
                return rarity

        return DungeonRarity.COMMON  # Fallback

    def enter_dungeon(self, player_position: Position, rarity: Optional[DungeonRarity] = None) -> DungeonInstance:
        """
        Enter a new dungeon instance.

        Args:
            player_position: Player's current world position (to return to later)
            rarity: Optional specific rarity, or roll randomly

        Returns:
            The new dungeon instance
        """
        if rarity is None:
            rarity = self.roll_dungeon_rarity()

        self.current_dungeon = DungeonInstance(rarity=rarity)
        self.current_dungeon.return_position = player_position.copy()
        self.in_dungeon = True

        return self.current_dungeon

    def exit_dungeon(self) -> Optional[Position]:
        """
        Exit the current dungeon.

        Returns:
            The position to return the player to, or None if not in dungeon
        """
        if not self.in_dungeon or not self.current_dungeon:
            return None

        return_pos = self.current_dungeon.return_position

        # Track completion if cleared
        if self.current_dungeon.is_cleared:
            self.dungeons_completed += 1
            self.dungeons_by_rarity[self.current_dungeon.rarity.value] += 1

        self.current_dungeon.is_active = False
        self.current_dungeon = None
        self.in_dungeon = False

        return return_pos

    def get_player_dungeon_position(self) -> Optional[Position]:
        """Get the player's spawn position within the current dungeon."""
        if not self.current_dungeon:
            return None
        return self.current_dungeon.get_player_spawn_position()

    def start_next_wave(self) -> int:
        """Start the next wave in the current dungeon."""
        if not self.current_dungeon:
            return 0
        return self.current_dungeon.start_wave()

    def on_enemy_killed(self):
        """Notify that an enemy was killed in the dungeon."""
        if self.current_dungeon:
            self.current_dungeon.enemy_killed()

    def is_wave_complete(self) -> bool:
        """Check if the current wave is complete."""
        if not self.current_dungeon:
            return False
        return self.current_dungeon.is_wave_complete()

    def is_dungeon_cleared(self) -> bool:
        """Check if the dungeon is fully cleared."""
        if not self.current_dungeon:
            return False
        return self.current_dungeon.is_cleared

    def get_chest(self) -> Optional[LootChest]:
        """Get the dungeon's loot chest if cleared."""
        if not self.current_dungeon or not self.current_dungeon.is_cleared:
            return None
        return self.current_dungeon.chest

    def open_chest(self) -> List[Tuple[str, int]]:
        """Open the dungeon chest and return contents."""
        chest = self.get_chest()
        if chest and not chest.is_opened:
            return chest.open()
        return []

    def get_dungeon_tiles(self) -> Dict[str, WorldTile]:
        """Get the tiles for the current dungeon (for rendering)."""
        if not self.current_dungeon:
            return {}
        return self.current_dungeon.tiles

    def get_visible_tiles(self, camera_pos: Position, viewport_width: int, viewport_height: int) -> List[WorldTile]:
        """Get visible tiles in the dungeon for rendering."""
        if not self.current_dungeon:
            return []

        tw = viewport_width // Config.TILE_SIZE + 2
        th = viewport_height // Config.TILE_SIZE + 2
        sx = camera_pos.x - tw // 2
        ex = camera_pos.x + tw // 2
        sy = camera_pos.y - th // 2
        ey = camera_pos.y + th // 2

        return [
            tile for tile in self.current_dungeon.tiles.values()
            if sx <= tile.position.x <= ex and sy <= tile.position.y <= ey
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize dungeon manager state for saving."""
        return {
            "in_dungeon": self.in_dungeon,
            "current_dungeon": self.current_dungeon.to_dict() if self.current_dungeon else None,
            "dungeons_completed": self.dungeons_completed,
            "dungeons_by_rarity": self.dungeons_by_rarity
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DungeonManager':
        """Deserialize dungeon manager from save data."""
        manager = cls()
        manager.in_dungeon = data.get("in_dungeon", False)
        manager.dungeons_completed = data.get("dungeons_completed", 0)
        manager.dungeons_by_rarity = data.get("dungeons_by_rarity", {r.value: 0 for r in DungeonRarity})

        if data.get("current_dungeon"):
            manager.current_dungeon = DungeonInstance.from_dict(data["current_dungeon"])

        return manager
