"""Quest management system"""

import time
from typing import Dict, List, Tuple, Optional

from data.models import QuestDefinition
from data.models.quests import QuestRewards
from data.databases import TitleDatabase, MaterialDatabase, SkillDatabase


class Quest:
    """Active quest instance for a character.

    Adaptive reward lifecycle (v3, 2026-04-26):
    - Canonical quests (``quest_def.source_origin == "canonical"``)
      use their hand-authored ``quest_def.rewards`` directly. No LLM
      calls. Preserves tutorial / hand-tuned reward economy.
    - Generated quests (``source_origin == "generated"``) pass through
      a pre-generation step at receive time (materializes prose →
      concrete numbers) and an adaptation step at turn-in (LLM may
      adjust based on actual play context — urgency, time taken,
      narrative weight). Failure of either step falls back through:
      adapted_rewards ?? pre_generated_rewards ?? quest_def.rewards.
    - ``effective_rewards`` is what :meth:`grant_rewards` actually
      applies. The resolver writes here; if no LLM step ran, it
      points at ``quest_def.rewards``.
    """
    def __init__(self, quest_def: QuestDefinition, character=None):
        self.quest_def = quest_def
        self.status = "in_progress"  # in_progress, completed, turned_in
        self.progress = {}  # Track progress: {"item_id": current_quantity} or {"enemies_killed": count}

        # Track baselines to only count progress AFTER quest acceptance
        self.baseline_combat_kills = 0
        self.baseline_inventory = {}

        # Adaptive reward lifecycle state (only populated for
        # generated quests; canonical quests leave these at None).
        self.received_at_game_time: float = time.time()
        self.objectives_met_at: Optional[float] = None
        self.turned_in_at: Optional[float] = None
        self.pre_generated_rewards: Optional[QuestRewards] = None
        self.pre_generated_completion_dialogue: List[str] = []
        self.adapted_rewards: Optional[QuestRewards] = None
        self.actual_rewards_granted: Optional[QuestRewards] = None
        # ``effective_rewards`` is the resolved-at-grant-time reward
        # bundle. Defaults to the design-time concrete rewards on the
        # quest_def (so canonical/tutorial quests behave identically
        # to pre-v3). Adaptive flow may overwrite before grant_rewards.
        self.effective_rewards: QuestRewards = quest_def.rewards

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

                # Check if we've gathered enough NEW items
                if gathered_since_start < required_qty:
                    return False
            return True

        elif self.quest_def.objectives.objective_type == "combat":
            # Check enemy kills SINCE quest acceptance
            required_kills = self.quest_def.objectives.enemies_killed
            current_kills = character.activities.get_count('combat')
            kills_since_start = current_kills - self.baseline_combat_kills
            return kills_since_start >= required_kills

        return False

    def consume_items(self, character) -> bool:
        """Remove quest items from inventory (for gather quests)"""
        if self.quest_def.objectives.objective_type != "gather":
            return True

        # Remove required items from inventory
        for required_item in self.quest_def.objectives.items:
            item_id = required_item["item_id"]
            required_qty = required_item["quantity"]
            remaining = required_qty

            for i, item_stack in enumerate(character.inventory.slots):
                if item_stack and item_stack.item_id == item_id and remaining > 0:
                    if item_stack.quantity <= remaining:
                        remaining -= item_stack.quantity
                        character.inventory.slots[i] = None
                    else:
                        item_stack.quantity -= remaining
                        remaining = 0

            if remaining > 0:
                print(f"⚠️  Quest failed to consume items! Still need {remaining}x {item_id}")
                return False  # Failed to consume all items
        return True

    def grant_rewards(self, character) -> List[str]:
        """Grant quest rewards to character. Returns list of reward messages.

        Uses ``self.effective_rewards`` — the resolved bundle. For
        canonical quests this is identical to ``quest_def.rewards``;
        for generated quests with a successful adapt step it is the
        adapted bundle; otherwise it falls back to the pre-generated
        bundle, then to the design rewards (typically empty for LLM
        quests). The fallback chain ensures that a failed LLM call
        never produces a quest with zero reward when pre-generation
        succeeded.
        """
        messages = []
        rewards = self.effective_rewards
        # Snapshot what's actually being granted so save/load and the
        # WNS archive can reference the receipt.
        self.actual_rewards_granted = rewards

        # Experience
        if rewards.experience > 0:
            old_level = character.leveling.level
            leveled_up = character.leveling.add_exp(rewards.experience)
            messages.append(f"+{rewards.experience} XP")
            if leveled_up:
                messages.append(f"Level up! Now level {character.leveling.level}")

        # Health restore
        if rewards.health_restore > 0:
            character.health = min(character.max_health, character.health + rewards.health_restore)
            messages.append(f"+{rewards.health_restore} HP")

        # Mana restore
        if rewards.mana_restore > 0:
            character.mana = min(character.max_mana, character.mana + rewards.mana_restore)
            messages.append(f"+{rewards.mana_restore} Mana")

        # Skills
        for skill_id in rewards.skills:
            learned = character.skills.learn_skill(skill_id, character=character, skip_checks=True)
            if learned:
                skill_db = SkillDatabase.get_instance()
                skill_name = skill_db.skills[skill_id].name if skill_id in skill_db.skills else skill_id
                messages.append(f"Learned skill: {skill_name}")

        # Items
        mat_db = MaterialDatabase.get_instance()
        for item_reward in rewards.items:
            item_id = item_reward["item_id"]
            quantity = item_reward["quantity"]

            # Try to add to inventory
            added = character.inventory.add_item(item_id, quantity)
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
                # Track gold earned from quest reward
                if hasattr(character, 'stat_tracker'):
                    character.stat_tracker.record_gold_earned(rewards.gold, source="quest")
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
        """Start a new quest (with character to track baselines).

        For ``source_origin == "generated"`` quests, also pre-generates
        the concrete reward bundle and completion dialogue via the
        :class:`QuestRewardAdapter`. Best-effort — pre-gen failure
        leaves the quest with the design rewards (typically zeros for
        LLM quests) and the resolver chain handles fallback at
        turn-in.

        Canonical quests skip pre-generation entirely; their
        hand-tuned ``quest_def.rewards`` flows straight to
        ``Quest.effective_rewards`` and grant_rewards uses them
        verbatim.
        """
        if quest_def.quest_id in self.active_quests or quest_def.quest_id in self.completed_quests:
            return False  # Already have this quest

        quest = Quest(quest_def, character)
        self.active_quests[quest_def.quest_id] = quest

        # Generated quests trigger pre-generation. The adapter
        # handles canonical quests as a no-op so this branch is safe
        # to call unconditionally — explicit guard kept for clarity.
        if quest_def.source_origin == "generated":
            self._pregenerate_rewards(quest, character)

        # Stat tracking and event bus publish
        if character and hasattr(character, 'stat_tracker'):
            character.stat_tracker.record_quest_accepted(
                quest_id=quest_def.quest_id,
                quest_type=quest_def.objectives.objective_type
            )
        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("QUEST_ACCEPTED", {
                "quest_id": quest_def.quest_id,
                "quest_type": quest_def.objectives.objective_type,
                "npc_id": quest_def.npc_id,
            })
        except Exception:
            pass

        return True

    @staticmethod
    def _pregenerate_rewards(quest: Quest, character) -> None:
        """Best-effort pre-generation. Mutates the quest in place.

        Stores the LLM-derived QuestRewards on
        ``quest.pre_generated_rewards`` and the dialogue lines on
        ``quest.pre_generated_completion_dialogue``. Also updates
        ``quest.effective_rewards`` to the pre-generated bundle so
        grant_rewards has a meaningful reward even if turn-in
        adaptation fails.

        Failure of any kind is swallowed — generated quests with
        failed pre-gen retain their (typically empty) design
        rewards. Logged via ``log_degrade``.
        """
        try:
            from world_system.wes.quest_reward_adapter import (
                get_reward_adapter,
            )
        except Exception as e:
            print(f"[QUEST] reward adapter import failed: {e}")
            return
        try:
            result = get_reward_adapter().pregenerate(quest.quest_def, character)
        except Exception as e:
            print(f"[QUEST] reward pregen raised: {e}")
            return
        if result is None:
            return
        rewards, dialogue = result
        quest.pre_generated_rewards = rewards
        quest.pre_generated_completion_dialogue = dialogue
        quest.effective_rewards = rewards

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

        # Adapt rewards at turn-in for generated quests. Adapter
        # bypasses canonical quests as a no-op. Failure leaves
        # effective_rewards at the pre-generated baseline (or design
        # rewards if pre-gen also failed). The resolution chain is:
        #   adapted ?? pre_generated ?? quest_def.rewards
        if quest.quest_def.source_origin == "generated":
            self._adapt_rewards(quest, character)

        # Snapshot turn-in time for archive/observability.
        quest.turned_in_at = time.time()

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

        # Stat tracking and event bus publish — use effective_rewards
        # so generated quests report the pre-gen / adapted numbers,
        # not the (typically zero) design rewards.
        eff = quest.effective_rewards
        if hasattr(character, 'stat_tracker'):
            character.stat_tracker.record_quest_completed(
                quest_id=quest_id,
                quest_type=quest.quest_def.objectives.objective_type,
                exp_reward=float(eff.experience),
                gold_reward=float(eff.gold)
            )
        try:
            from events.event_bus import get_event_bus
            # Use "player" as player_id (single-player game convention)
            player_id = "player"
            if character and hasattr(character, 'name'):
                player_id = character.name or "player"
            get_event_bus().publish("QUEST_COMPLETED", {
                "quest_id": quest_id,
                "player_id": player_id,
                "quest_type": quest.quest_def.objectives.objective_type,
                "npc_id": quest.quest_def.npc_id,
                "rewards": {
                    "experience": eff.experience,
                    "gold": eff.gold,
                },
            })
        except Exception:
            pass

        return True, messages

    @staticmethod
    def _adapt_rewards(quest: Quest, character) -> None:
        """Best-effort turn-in adaptation. Mutates quest in place.

        On success: ``quest.adapted_rewards`` is the LLM-adjusted
        bundle and ``quest.effective_rewards`` is updated to point at
        it (so grant_rewards uses the adapted numbers).

        On any failure: state is unchanged. ``quest.effective_rewards``
        stays at the pre-generated baseline (or the design rewards if
        pre-gen also failed) and the player still receives the
        promised floor — no penalty for the LLM hiccup.
        """
        try:
            from world_system.wes.quest_reward_adapter import (
                get_reward_adapter,
            )
        except Exception as e:
            print(f"[QUEST] reward adapter import failed at turn-in: {e}")
            return
        try:
            result = get_reward_adapter().adapt(
                quest=quest, character=character, game_time_now=time.time(),
            )
        except Exception as e:
            print(f"[QUEST] reward adapt raised: {e}")
            return
        if result is None:
            return
        quest.adapted_rewards = result
        quest.effective_rewards = result

    def abandon_quest(self, quest_id: str, character=None) -> bool:
        """Abandon an active quest."""
        if quest_id not in self.active_quests:
            return False
        quest = self.active_quests.pop(quest_id)
        quest_type = quest.quest_def.objectives.objective_type if quest.quest_def else "unknown"

        if character and hasattr(character, 'stat_tracker'):
            character.stat_tracker.record_quest_failed(
                quest_id=quest_id,
                quest_type=quest_type
            )
        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("QUEST_FAILED", {
                "quest_id": quest_id,
                "quest_type": quest_type,
            })
        except Exception:
            pass
        return True

    def has_completed(self, quest_id: str) -> bool:
        """Check if quest has been completed and turned in"""
        return quest_id in self.completed_quests

    def restore_from_save(self, quest_state: dict):
        """
        Restore quest state from save data.

        Args:
            quest_state: Dictionary containing quest state data from save file
        """
        # Clear existing state
        self.active_quests.clear()
        self.completed_quests.clear()

        # Restore completed quests
        self.completed_quests = list(quest_state.get("completed_quests", []))

        # Restore active quests (if any)
        active_quests_data = quest_state.get("active_quests", {})

        # If there are no active quests, skip quest restoration
        if not active_quests_data:
            print(f"Restored 0 active quests and {len(self.completed_quests)} completed quests")
            return

        # Try to load quest database if we have active quests
        try:
            # Note: QuestDatabase may not exist yet - quest system is not fully implemented
            # For now, we'll just skip restoring active quests if the database doesn't exist
            # This allows saves to work even without a quest system
            print(f"⚠ Quest database not implemented - skipping {len(active_quests_data)} active quests")
            print(f"Restored 0 active quests and {len(self.completed_quests)} completed quests")
        except ImportError:
            print(f"⚠ Quest database not available - skipping quest restoration")
            print(f"Restored 0 active quests and {len(self.completed_quests)} completed quests")
