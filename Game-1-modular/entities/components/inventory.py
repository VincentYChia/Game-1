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
        return EquipmentDatabase.get_instance().is_equipment(self.item_id)

    def get_equipment(self) -> Optional[EquipmentItem]:
        """Get equipment data if this is equipment"""
        if not self.is_equipment():
            return None
        # Return the stored equipment instance if available
        if self.equipment_data:
            return self.equipment_data
        # Otherwise create a new one (shouldn't happen for equipment items)
        return EquipmentDatabase.get_instance().create_equipment_from_id(self.item_id)


class Inventory:
    def __init__(self, max_slots: int = 30):
        self.slots: List[Optional[ItemStack]] = [None] * max_slots
        self.max_slots = max_slots
        self.dragging_slot: Optional[int] = None
        self.dragging_stack: Optional[ItemStack] = None
        self.dragging_from_equipment: bool = False  # Track if dragging from equipment slot

    def add_item(self, item_id: str, quantity: int, equipment_instance: Optional['EquipmentItem'] = None) -> bool:
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

                stack = ItemStack(item_id, 1, 1, equip_data)
                self.slots[empty] = stack
            return True

        # Normal materials can stack
        mat = mat_db.get_material(item_id)
        max_stack = mat.max_stack if mat else 99

        for slot in self.slots:
            if slot and slot.item_id == item_id and remaining > 0:
                remaining = slot.add(remaining)

        while remaining > 0:
            empty = self.get_empty_slot()
            if empty is None:
                return False
            stack_size = min(remaining, max_stack)
            self.slots[empty] = ItemStack(item_id, stack_size, max_stack)
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
            elif self.slots[
                target_slot].item_id == self.dragging_stack.item_id and not self.dragging_stack.is_equipment():
                overflow = self.slots[target_slot].add(self.dragging_stack.quantity)
                if overflow > 0:
                    self.dragging_stack.quantity = overflow
                    self.slots[self.dragging_slot] = self.dragging_stack
            else:
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
