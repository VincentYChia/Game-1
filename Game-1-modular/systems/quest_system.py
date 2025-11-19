"""Quest management system"""

from typing import Dict, List, Tuple, Optional

from data.models import QuestDefinition
from data.databases import TitleDatabase, MaterialDatabase, SkillDatabase


class Quest:
    """Active quest instance for a character"""
    def __init__(self, quest_def: QuestDefinition, character=None):
        self.quest_def = quest_def
        self.status = "in_progress"  # in_progress, completed, turned_in
        self.progress = {}  # Track progress: {"item_id": current_quantity} or {"enemies_killed": count}

        # Track baselines to only count progress AFTER quest acceptance
        self.baseline_combat_kills = 0
        self.baseline_inventory = {}

        # Initialize baselines if character provided
        if character:
            self._initialize_baselines(character)

    def _initialize_baselines(self, character):
        """Snapshot current state when quest is accepted"""
        if self.quest_def.objectives.objective_type == "combat":
            self.baseline_combat_kills = character.activities.get_count('combat')
        elif self.quest_def.objectives.objective_type == "gather":
            # Snapshot current inventory counts for quest items
            for required_item in self.quest_def.objectives.items:
                item_id = required_item["item_id"]
                current_count = character.inventory.get_item_count(item_id)
                self.baseline_inventory[item_id] = current_count

    def check_completion(self, character) -> bool:
        """Check if quest objectives are met based on character state (only counting progress AFTER quest acceptance)"""
        if self.quest_def.objectives.objective_type == "gather":
            # Check if character has gathered required items SINCE quest acceptance
            for required_item in self.quest_def.objectives.items:
                item_id = required_item["item_id"]
                required_qty = required_item["quantity"]

                # Count current items in inventory
                current_qty = character.inventory.get_item_count(item_id)

                # Calculate items gathered since quest start
                baseline_qty = self.baseline_inventory.get(item_id, 0)
                gathered_since_start = current_qty - baseline_qty

                print(f"[QUEST DEBUG] Gather check for {item_id}: current={current_qty}, baseline={baseline_qty}, gathered={gathered_since_start}, required={required_qty}")

                # Check if we've gathered enough NEW items
                if gathered_since_start < required_qty:
                    print(f"[QUEST DEBUG] Not enough {item_id} gathered!")
                    return False
            return True

        elif self.quest_def.objectives.objective_type == "combat":
            # Check enemy kills SINCE quest acceptance
            required_kills = self.quest_def.objectives.enemies_killed
            current_kills = character.activities.get_count('combat')
            kills_since_start = current_kills - self.baseline_combat_kills
            print(f"[QUEST DEBUG] Combat check: current_kills={current_kills}, baseline={self.baseline_combat_kills}, since_start={kills_since_start}, required={required_kills}")
            result = kills_since_start >= required_kills
            print(f"[QUEST DEBUG] Combat quest complete: {result}")
            return result

        return False

    def consume_items(self, character) -> bool:
        """Remove quest items from inventory (for gather quests)"""
        if self.quest_def.objectives.objective_type != "gather":
            print(f"[QUEST DEBUG] Quest type is {self.quest_def.objectives.objective_type}, skipping item consumption")
            return True

        print(f"[QUEST DEBUG] Consuming items for gather quest")
        # Remove required items from inventory
        for required_item in self.quest_def.objectives.items:
            item_id = required_item["item_id"]
            required_qty = required_item["quantity"]
            remaining = required_qty
            print(f"[QUEST DEBUG] Need to consume {required_qty}x {item_id}")

            for i, item_stack in enumerate(character.inventory.slots):
                if item_stack and item_stack.item_id == item_id and remaining > 0:
                    if item_stack.quantity <= remaining:
                        print(f"[QUEST DEBUG] Removing {item_stack.quantity}x {item_id} from slot {i}")
                        remaining -= item_stack.quantity
                        character.inventory.slots[i] = None
                    else:
                        print(f"[QUEST DEBUG] Reducing {item_id} in slot {i} by {remaining}")
                        item_stack.quantity -= remaining
                        remaining = 0

            if remaining > 0:
                print(f"[QUEST DEBUG] Failed to consume all items! Still need {remaining}x {item_id}")
                return False  # Failed to consume all items
            print(f"[QUEST DEBUG] Successfully consumed {required_qty}x {item_id}")
        return True

    def grant_rewards(self, character) -> List[str]:
        """Grant quest rewards to character. Returns list of reward messages."""
        messages = []
        rewards = self.quest_def.rewards

        print(f"[REWARD DEBUG] Granting rewards for quest: {self.quest_def.quest_id}")
        print(f"[REWARD DEBUG] Character before: HP={character.health}/{character.max_health}, XP={character.leveling.current_exp}, Level={character.leveling.level}")

        # Experience
        if rewards.experience > 0:
            old_xp = character.leveling.current_exp
            old_level = character.leveling.level
            leveled_up = character.leveling.add_exp(rewards.experience)
            new_xp = character.leveling.current_exp
            print(f"[REWARD DEBUG] XP: {old_xp} + {rewards.experience} = {new_xp}")
            messages.append(f"+{rewards.experience} XP")
            if leveled_up:
                messages.append(f"Level up! Now level {character.leveling.level}")
                print(f"[REWARD DEBUG] Level up: {old_level} -> {character.leveling.level}")

        # Health restore
        if rewards.health_restore > 0:
            old_health = character.health
            character.health = min(character.max_health, character.health + rewards.health_restore)
            print(f"[REWARD DEBUG] Health: {old_health} + {rewards.health_restore} = {character.health}")
            messages.append(f"+{rewards.health_restore} HP")

        # Mana restore
        if rewards.mana_restore > 0:
            old_mana = character.mana
            character.mana = min(character.max_mana, character.mana + rewards.mana_restore)
            print(f"[REWARD DEBUG] Mana: {old_mana} + {rewards.mana_restore} = {character.mana}")
            messages.append(f"+{rewards.mana_restore} Mana")

        # Skills
        print(f"[REWARD DEBUG] Processing {len(rewards.skills)} skills: {rewards.skills}")
        for skill_id in rewards.skills:
            print(f"[REWARD DEBUG] Attempting to learn skill: {skill_id}")
            learned = character.skills.learn_skill(skill_id, character=character, skip_checks=True)
            print(f"[REWARD DEBUG] Skill {skill_id} learn result: {learned}")
            if learned:
                skill_db = SkillDatabase.get_instance()
                skill_name = skill_db.skills[skill_id].name if skill_id in skill_db.skills else skill_id
                messages.append(f"Learned skill: {skill_name}")
            else:
                print(f"[REWARD DEBUG] Failed to learn skill {skill_id} - may already be known")

        # Items
        mat_db = MaterialDatabase.get_instance()
        print(f"[REWARD DEBUG] Processing {len(rewards.items)} item rewards")
        for item_reward in rewards.items:
            item_id = item_reward["item_id"]
            quantity = item_reward["quantity"]
            print(f"[REWARD DEBUG] Adding item: {item_id} x{quantity}")

            # Try to add to inventory
            added = character.inventory.add_item(item_id, quantity)
            print(f"[REWARD DEBUG] Item add result: {added}")
            if added:
                item_def = mat_db.get_material(item_id)
                item_name = item_def.name if item_def else item_id
                messages.append(f"+{quantity}x {item_name}")
            else:
                item_def = mat_db.get_material(item_id)
                item_name = item_def.name if item_def else item_id
                messages.append(f"Inventory full! Lost {quantity}x {item_name}")

        # Gold
        if rewards.gold > 0:
            # Check if character has a gold/currency attribute
            if hasattr(character, 'gold'):
                old_gold = character.gold
                character.gold += rewards.gold
                print(f"[REWARD DEBUG] Gold: {old_gold} + {rewards.gold} = {character.gold}")
                messages.append(f"+{rewards.gold} Gold")
            else:
                print(f"[REWARD DEBUG] Character has no gold attribute - skipping gold reward")

        # Stat Points
        if rewards.stat_points > 0:
            # Check if character has stat points system
            if hasattr(character, 'stat_points'):
                old_points = character.stat_points
                character.stat_points += rewards.stat_points
                print(f"[REWARD DEBUG] Stat Points: {old_points} + {rewards.stat_points} = {character.stat_points}")
                messages.append(f"+{rewards.stat_points} Stat Points")
            elif hasattr(character, 'unallocated_points'):
                old_points = character.unallocated_points
                character.unallocated_points += rewards.stat_points
                print(f"[REWARD DEBUG] Unallocated Points: {old_points} + {rewards.stat_points} = {character.unallocated_points}")
                messages.append(f"+{rewards.stat_points} Stat Points")
            else:
                print(f"[REWARD DEBUG] Character has no stat points attribute - skipping stat point reward")

        # Title
        if rewards.title:
            print(f"[REWARD DEBUG] Granting title: {rewards.title}")
            title_db = TitleDatabase.get_instance()
            if rewards.title in title_db.titles:
                title_def = title_db.titles[rewards.title]
                awarded = character.titles.award_title(title_def)
                print(f"[REWARD DEBUG] Title award result: {awarded}")
                if awarded:
                    messages.append(f"Earned title: {title_def.name}")

        # Status Effects (future expansion)
        if rewards.status_effects:
            print(f"[REWARD DEBUG] Processing {len(rewards.status_effects)} status effects")
            for effect in rewards.status_effects:
                effect_id = effect.get("effect_id", "")
                duration = effect.get("duration", 0)
                print(f"[REWARD DEBUG] Status effect: {effect_id} for {duration}s - NOT YET IMPLEMENTED")
                # TODO: Implement status effect system
                # if hasattr(character, 'status_effects'):
                #     character.status_effects.add(effect_id, duration)
                #     messages.append(f"Gained effect: {effect_id}")

        # Buffs (future expansion)
        if rewards.buffs:
            print(f"[REWARD DEBUG] Processing {len(rewards.buffs)} buffs")
            for buff in rewards.buffs:
                stat = buff.get("stat", "")
                amount = buff.get("amount", 0)
                duration = buff.get("duration", 0)
                print(f"[REWARD DEBUG] Buff: +{amount} {stat} for {duration}s - NOT YET IMPLEMENTED")
                # TODO: Implement buff system
                # if hasattr(character, 'buffs'):
                #     character.buffs.add(stat, amount, duration)
                #     messages.append(f"Buff: +{amount} {stat}")

        print(f"[REWARD DEBUG] Character after: HP={character.health}/{character.max_health}, XP={character.leveling.current_exp}, Level={character.leveling.level}")
        print(f"[REWARD DEBUG] Generated {len(messages)} reward messages")
        return messages

class QuestManager:
    """Manages active quests for a character"""
    def __init__(self):
        self.active_quests: Dict[str, Quest] = {}  # quest_id -> Quest
        self.completed_quests: List[str] = []  # quest_ids that have been turned in

    def start_quest(self, quest_def: QuestDefinition, character) -> bool:
        """Start a new quest (with character to track baselines)"""
        if quest_def.quest_id in self.active_quests or quest_def.quest_id in self.completed_quests:
            return False  # Already have this quest

        self.active_quests[quest_def.quest_id] = Quest(quest_def, character)
        return True

    def complete_quest(self, quest_id: str, character) -> Tuple[bool, List[str]]:
        """Complete a quest and grant rewards. Returns (success, reward_messages)"""
        print(f"[QUEST DEBUG] ========== COMPLETING QUEST: {quest_id} ==========")

        if quest_id not in self.active_quests:
            print(f"[QUEST DEBUG] Quest not found in active quests!")
            return False, ["Quest not active"]

        quest = self.active_quests[quest_id]
        print(f"[QUEST DEBUG] Quest found: {quest.quest_def.title}")

        # Check if completed
        print(f"[QUEST DEBUG] Checking if quest objectives are met...")
        if not quest.check_completion(character):
            print(f"[QUEST DEBUG] Quest objectives NOT met!")
            return False, ["Quest objectives not met"]
        print(f"[QUEST DEBUG] Quest objectives ARE met!")

        # Consume quest items if needed
        print(f"[QUEST DEBUG] Consuming quest items...")
        if not quest.consume_items(character):
            print(f"[QUEST DEBUG] Failed to consume quest items!")
            return False, ["Failed to consume quest items"]
        print(f"[QUEST DEBUG] Quest items consumed successfully!")

        # Grant rewards
        print(f"[QUEST DEBUG] Granting quest rewards...")
        messages = quest.grant_rewards(character)
        print(f"[QUEST DEBUG] Rewards granted! Generated {len(messages)} messages")

        # Mark as completed
        quest.status = "turned_in"
        self.completed_quests.append(quest_id)
        del self.active_quests[quest_id]
        print(f"[QUEST DEBUG] Quest marked as complete and moved to completed list")
        print(f"[QUEST DEBUG] ========== QUEST COMPLETION FINISHED ==========")

        return True, messages

    def has_completed(self, quest_id: str) -> bool:
        """Check if quest has been completed and turned in"""
        return quest_id in self.completed_quests
