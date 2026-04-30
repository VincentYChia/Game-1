"""NPC system for managing non-player characters.

Dialogue priority (NL1 deterministic path, 2026-04-29):

1. The NPC's structured speechbank (``npc_def.speechbank``) is preferred
   when present. First call to :meth:`NPC.get_next_dialogue` returns a
   greeting; subsequent calls cycle through ``idle_barks``. Quest accept
   and quest turn-in have dedicated helpers
   (:meth:`NPC.get_quest_offer_line`, :meth:`NPC.get_quest_complete_line`)
   so per-NPC voice survives across the quest lifecycle.
2. Falls back to ``npc_def.dialogue_lines`` (the legacy flattened list)
   when the structured speechbank is absent or empty. Maintains
   backwards compatibility with NPCs from older saves that pre-date the
   v3 schema.
3. Returns ``"..."`` only when both paths are empty — true graceful
   degrade for malformed NPC definitions.

The LLM-powered :class:`NPCAgentSystem` still wraps this for live
generation; these helpers are the deterministic safety net underneath
when the agent is unavailable or the player is talking to an NPC whose
agent invocation failed.
"""

import math
from typing import List, Optional

from data.models import NPCDefinition, Position
from systems.quest_system import QuestManager


class NPC:
    """Active NPC instance in the world."""

    def __init__(self, npc_def: NPCDefinition):
        self.npc_def = npc_def
        self.position = npc_def.position
        # Legacy flat-list cycle index — still used as a fallback for
        # NPCs without a structured speechbank.
        self.current_dialogue_index = 0
        # Per-NPC cycle indices for the structured speechbank lists.
        # Each list cycles independently so the player hears varied
        # idle_barks even after greeting once.
        self._greeting_index = 0
        self._idle_index = 0
        self._farewell_index = 0
        # Toggle: the very first :meth:`get_next_dialogue` call after
        # the player engages returns a greeting; subsequent calls walk
        # the idle_bark loop. Quest accept / turn-in side-channels do
        # not flip this — they're a separate axis.
        self._has_greeted = False

    def is_near(self, player_pos: Position) -> bool:
        """Check if player is within interaction radius."""
        dx = self.position.x - player_pos.x
        dy = self.position.y - player_pos.y
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.npc_def.interaction_radius

    def reset_dialogue_state(self) -> None:
        """Reset greeting/idle/farewell cycle state.

        Game engine should call this when the player ends a conversation
        so the next interaction starts with a fresh greeting. (Cycle
        indices keep climbing so repeated greetings rotate through the
        bank rather than repeating verbatim.)
        """
        self._has_greeted = False

    def get_next_dialogue(self) -> str:
        """Return the next dialogue line for the active conversation.

        First call after :meth:`reset_dialogue_state` (or NPC creation)
        returns a greeting from ``speechbank["greeting"]``. Subsequent
        calls cycle through ``speechbank["idle_barks"]``. When the
        structured speechbank is absent, falls back to the legacy
        flattened ``npc_def.dialogue_lines`` cycle.
        """
        sb = self.npc_def.speechbank or {}
        greetings = sb.get("greeting")
        if not isinstance(greetings, list):
            greetings = []
        idles = sb.get("idle_barks")
        if not isinstance(idles, list):
            idles = []

        # Greet on first turn of this conversation.
        if not self._has_greeted and greetings:
            line = greetings[self._greeting_index % len(greetings)]
            self._greeting_index += 1
            self._has_greeted = True
            return line

        # Cycle idles for follow-up turns.
        if idles:
            line = idles[self._idle_index % len(idles)]
            self._idle_index += 1
            return line

        # Speechbank absent or empty — legacy flat list cycle.
        if self.npc_def.dialogue_lines:
            dialogue = self.npc_def.dialogue_lines[self.current_dialogue_index]
            self.current_dialogue_index = (
                (self.current_dialogue_index + 1)
                % len(self.npc_def.dialogue_lines)
            )
            return dialogue

        return "..."

    def get_quest_offer_line(self) -> Optional[str]:
        """Per-NPC line shown right after the player accepts a quest.

        Reads ``speechbank["quest_offer"]`` (a single string, not a
        list — the v3 schema commits to one canonical accept line per
        NPC). Returns ``None`` when the speechbank is absent or this
        key is missing / empty, so callers can fall through to
        :meth:`get_next_dialogue`.
        """
        sb = self.npc_def.speechbank or {}
        v = sb.get("quest_offer")
        if isinstance(v, str) and v.strip():
            return v
        return None

    def get_quest_complete_line(self) -> Optional[str]:
        """Per-NPC line shown at quest turn-in.

        The quest may also carry ``QuestDefinition.completion_dialogue``
        — that's per-quest and takes priority. This helper provides the
        per-NPC voice for cases where the quest doesn't author its own
        completion lines.
        """
        sb = self.npc_def.speechbank or {}
        v = sb.get("quest_complete")
        if isinstance(v, str) and v.strip():
            return v
        return None

    def get_farewell_line(self) -> Optional[str]:
        """Cycles through ``speechbank["farewell"]`` if present.

        Game engine can call this when the player closes the dialogue
        panel; current UI doesn't render a parting line, but exposing
        it now lets that ship without further changes here.
        """
        sb = self.npc_def.speechbank or {}
        farewells = sb.get("farewell")
        if isinstance(farewells, list) and farewells:
            line = farewells[self._farewell_index % len(farewells)]
            self._farewell_index += 1
            return line
        return None

    def get_available_quests(self, quest_manager: QuestManager) -> List[str]:
        """Get list of quest_ids this NPC offers that player hasn't completed"""
        available = []
        for quest_id in self.npc_def.quests:
            if quest_id not in quest_manager.active_quests and quest_id not in quest_manager.completed_quests:
                available.append(quest_id)
        return available

    def has_quest_to_turn_in(self, quest_manager: QuestManager, character) -> Optional[str]:
        """Check if player has a completable quest from this NPC"""
        for quest_id in self.npc_def.quests:
            if quest_id in quest_manager.active_quests:
                quest = quest_manager.active_quests[quest_id]
                if quest.check_completion(character):
                    return quest_id
        return None
