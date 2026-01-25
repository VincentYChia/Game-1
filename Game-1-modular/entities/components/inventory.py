"""Inventory system components"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from data.models import EquipmentItem, MaterialDefinition
from data.databases import MaterialDatabase, EquipmentDatabase


@dataclass
class ItemStack:
    item_id: str
    quantity: int
    max_stack: int = 99
    equipment_data: Optional['EquipmentItem'] = None  # For equipment items, store actual instance
    rarity: str = 'common'  # Rarity for materials and crafted items
    crafted_stats: Optional[Dict[str, Any]] = None  # Stats from minigame crafting with rarity modifiers

    def __post_init__(self):
        mat_db = MaterialDatabase.get_instance()
        if mat_db.loaded:
            mat = mat_db.get_material(self.item_id)
            if mat:
                self.max_stack = mat.max_stack

        # Equipment items don't stack
        equip_db = EquipmentDatabase.get_instance()
        is_equip = equip_db.is_equipment(self.item_id)

        if is_equip:
            self.max_stack = 1
            # Create equipment instance if not already set
            if self.equipment_data is None:
                self.equipment_data = equip_db.create_equipment_from_id(self.item_id)

    def can_add(self, amount: int) -> bool:
        return self.quantity + amount <= self.max_stack

    def add(self, amount: int) -> int:
        space = self.max_stack - self.quantity
        added = min(space, amount)
        self.quantity += added
        return amount - added

    def get_material(self) -> Optional[MaterialDefinition]:
        return MaterialDatabase.get_instance().get_material(self.item_id)

    def is_equipment(self) -> bool:
        """Check if this item stack is equipment"""
        # If equipment_data is set, it's equipment (handles invented items)
        if self.equipment_data is not None:
            return True
        return EquipmentDatabase.get_instance().is_equipment(self.item_id)

    def get_equipment(self) -> Optional[EquipmentItem]:
        """Get equipment data if this is equipment"""
        # Return the stored equipment instance if available (handles invented items)
        if self.equipment_data:
            return self.equipment_data
        # Check if this is a known equipment type from database
        if not EquipmentDatabase.get_instance().is_equipment(self.item_id):
            return None
        # Create a new one from database (shouldn't happen for equipment items with proper data)
        return EquipmentDatabase.get_instance().create_equipment_from_id(self.item_id)

    def can_stack_with(self, other: 'ItemStack') -> bool:
        """
        Check if this item can stack with another item.

        Items can stack if:
        1. Same item_id
        2. Both are not equipment (equipment never stacks)
        3. Both have identical rarity
        4. Both have identical crafted_stats (or both have None/empty stats)

        Args:
            other: Another ItemStack to check compatibility with

        Returns:
            bool: True if items can stack together
        """
        # Must be same item
        if self.item_id != other.item_id:
            return False

        # Equipment never stacks
        if self.is_equipment() or other.is_equipment():
            return False

        # Must have same rarity
        if self.rarity != other.rarity:
            return False

        # Check crafted_stats compatibility
        # Both None or empty = can stack
        self_stats = self.crafted_stats
        other_stats = other.crafted_stats

        # Normalize None and empty dict to be equivalent
        if not self_stats:
            self_stats = {}
        if not other_stats:
            other_stats = {}

        # Must have identical stats to stack
        return self_stats == other_stats


class Inventory:
    def __init__(self, max_slots: int = 30):
        self.slots: List[Optional[ItemStack]] = [None] * max_slots
        self.max_slots = max_slots
        self.dragging_slot: Optional[int] = None
        self.dragging_stack: Optional[ItemStack] = None
        self.dragging_from_equipment: bool = False  # Track if dragging from equipment slot

    def add_item(self, item_id: str, quantity: int, equipment_instance: Optional['EquipmentItem'] = None,
                 rarity: str = 'common', crafted_stats: Optional[Dict[str, Any]] = None) -> bool:
        remaining = quantity
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        # Equipment doesn't stack
        is_equip = equip_db.is_equipment(item_id)

        if is_equip:
            for i in range(quantity):
                empty = self.get_empty_slot()
                if empty is None:
                    return False
                # Use provided equipment instance or create new one
                equip_data = equipment_instance if equipment_instance else equip_db.create_equipment_from_id(item_id)
                if not equip_data:
                    print(f"WARNING: Could not create equipment data for {item_id}")
                    return False

                stack = ItemStack(item_id, 1, 1, equip_data, rarity=rarity, crafted_stats=crafted_stats)
                self.slots[empty] = stack
            return True

        # Normal materials can stack (but only if crafted_stats match)
        mat = mat_db.get_material(item_id)
        max_stack = mat.max_stack if mat else 99

        # Create a temporary ItemStack to check stacking compatibility
        temp_stack = ItemStack(item_id, 1, max_stack, rarity=rarity, crafted_stats=crafted_stats)

        # Try to add to existing stacks with matching crafted_stats
        for slot in self.slots:
            if slot and remaining > 0 and temp_stack.can_stack_with(slot):
                remaining = slot.add(remaining)

        # Create new stacks for remaining items
        while remaining > 0:
            empty = self.get_empty_slot()
            if empty is None:
                return False
            stack_size = min(remaining, max_stack)
            self.slots[empty] = ItemStack(item_id, stack_size, max_stack, rarity=rarity, crafted_stats=crafted_stats)
            remaining -= stack_size
        return True

    def get_empty_slot(self) -> Optional[int]:
        for i, slot in enumerate(self.slots):
            if slot is None:
                return i
        return None

    def get_item_count(self, item_id: str) -> int:
        return sum(slot.quantity for slot in self.slots if slot and slot.item_id == item_id)

    def start_drag(self, slot_index: int):
        if 0 <= slot_index < self.max_slots and self.slots[slot_index]:
            self.dragging_slot = slot_index
            self.dragging_stack = self.slots[slot_index]
            self.slots[slot_index] = None
            self.dragging_from_equipment = False

    def end_drag(self, target_slot: int):
        if self.dragging_stack is None:
            return
        if 0 <= target_slot < self.max_slots:
            if self.slots[target_slot] is None:
                self.slots[target_slot] = self.dragging_stack
            elif self.dragging_stack.can_stack_with(self.slots[target_slot]):
                # Can stack: same item, both not equipment, and matching crafted_stats
                overflow = self.slots[target_slot].add(self.dragging_stack.quantity)
                if overflow > 0:
                    self.dragging_stack.quantity = overflow
                    self.slots[self.dragging_slot] = self.dragging_stack
            else:
                # Can't stack: swap the items
                self.slots[target_slot], self.dragging_stack = self.dragging_stack, self.slots[target_slot]
                if self.dragging_stack and self.dragging_slot is not None:
                    self.slots[self.dragging_slot] = self.dragging_stack
        else:
            if self.dragging_slot is not None:
                self.slots[self.dragging_slot] = self.dragging_stack
        self.dragging_slot = None
        self.dragging_stack = None
        self.dragging_from_equipment = False

    def cancel_drag(self):
        if self.dragging_stack and self.dragging_slot is not None and not self.dragging_from_equipment:
            self.slots[self.dragging_slot] = self.dragging_stack
        self.dragging_slot = None
        self.dragging_stack = None
        self.dragging_from_equipment = False

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        """Check if inventory has at least quantity of item_id"""
        return self.get_item_count(item_id) >= quantity

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        """Remove quantity of item_id from inventory. Returns True if successful."""
        if not self.has_item(item_id, quantity):
            return False

        remaining = quantity
        for i, slot in enumerate(self.slots):
            if slot and slot.item_id == item_id and remaining > 0:
                if slot.quantity <= remaining:
                    remaining -= slot.quantity
                    self.slots[i] = None
                else:
                    slot.quantity -= remaining
                    remaining = 0
                    break

        return remaining == 0
