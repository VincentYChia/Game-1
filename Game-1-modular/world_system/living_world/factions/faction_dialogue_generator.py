"""Faction Dialogue Generator — Phase 4 integration.

Builds NPCContextForDialogue by combining NPC profile, cultural affinity,
and player affinity data, then generates faction-aware dialogue via BackendManager.

Usage:
    gen = FactionDialogueGenerator()
    context = gen.build_npc_dialogue_context("npc_1", "player")
    dialogue = gen.generate_faction_dialogue(context, player_input="Hello")
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from world_system.living_world.factions.database import FactionDatabase
from world_system.living_world.factions.models import NPCContextForDialogue, NPCBelongingTag
from world_system.living_world.backends.backend_manager import BackendManager


class FactionDialogueGenerator:
    """Generates NPC dialogue enhanced with faction affinity context."""

    def __init__(self):
        self._db: Optional[FactionDatabase] = None
        self._backend: Optional[BackendManager] = None

    def initialize(self, db: Optional[FactionDatabase] = None,
                  backend: Optional[BackendManager] = None) -> None:
        """Initialize with database and backend manager.

        Args:
            db: FactionDatabase instance. If None, gets singleton.
            backend: BackendManager instance. If None, gets singleton.
        """
        self._db = db or FactionDatabase.get_instance()
        self._backend = backend or BackendManager.get_instance()

    def build_npc_dialogue_context(self, npc_id: str,
                                   player_id: str) -> Optional[NPCContextForDialogue]:
        """Build complete dialogue context for an NPC.

        Combines NPC profile, tags, cultural affinity, and player affinity
        into a single context object ready for LLM dialogue generation.

        Args:
            npc_id: NPC to generate context for.
            player_id: Player to calculate affinity for.

        Returns:
            NPCContextForDialogue or None if NPC not found.
        """
        if not self._db or not self._db.connection or not self._db._initialized:
            return None

        try:
            # Get NPC profile
            npc_profile = self._db.get_npc_profile(npc_id)
            if not npc_profile:
                return None

            # Get NPC belonging tags
            npc_tags = self._db.get_npc_belonging_tags(npc_id)

            # Get all tags this NPC belongs to (for cultural affinity lookup)
            tag_names = [tag.tag for tag in npc_tags]

            # Get player affinity with each of NPC's tags
            player_affinity = {}
            for tag_name in tag_names:
                aff = self._db.get_player_affinity(player_id, tag_name)
                player_affinity[tag_name] = aff

            # Get cultural affinity for NPC's location
            # (This comes from the location's default affinity toward tags)
            cultural_affinity = self._db.calculate_cultural_affinity(
                npc_profile.location_id
            )

            # Get recent quest history between this player and NPC
            quest_history = self._db.get_quest_log(player_id, npc_id)

            return NPCContextForDialogue(
                npc_id=npc_id,
                npc_narrative=npc_profile.narrative,
                npc_primary_tag=npc_profile.primary_tag,
                npc_belonging_tags=npc_tags,
                npc_cultural_affinity=cultural_affinity,
                player_id=player_id,
                player_affinity=player_affinity,
                quest_history=quest_history,
                location_id=npc_profile.location_id,
            )
        except Exception as e:
            print(f"[FactionDialogueGenerator] Error building context: {e}")
            return None

    def generate_faction_dialogue(
        self,
        context: NPCContextForDialogue,
        player_input: str,
        character=None,
        npc_name: str = "NPC",
    ) -> Dict[str, Any]:
        """Generate dialogue using faction affinity context.

        Args:
            context: NPCContextForDialogue built by build_npc_dialogue_context().
            player_input: What the player said/did.
            character: Optional Player Character for visible stats.
            npc_name: NPC display name.

        Returns:
            Dict with keys: text, emotion, success, error
        """
        if not self._backend:
            return {
                "text": "...",
                "emotion": "neutral",
                "success": False,
                "error": "BackendManager not initialized"
            }

        try:
            system_prompt = self._build_system_prompt_with_affinity(
                context, npc_name
            )
            user_prompt = self._build_user_prompt_with_affinity(
                context, player_input, character
            )

            text, err = self._backend.generate(
                task="faction_dialogue",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.6,
                max_tokens=300,
            )

            if err:
                return {
                    "text": "",
                    "emotion": "neutral",
                    "success": False,
                    "error": err
                }

            # Parse dialogue response
            result = self._parse_dialogue_response(text)
            return {
                "text": result.get("dialogue", text),
                "emotion": result.get("emotion", "neutral"),
                "success": True,
                "error": None
            }

        except Exception as e:
            return {
                "text": "",
                "emotion": "neutral",
                "success": False,
                "error": str(e)
            }

    def _build_system_prompt_with_affinity(self, context: NPCContextForDialogue,
                                           npc_name: str) -> str:
        """Build system prompt incorporating faction affinity data."""
        # NPC background and personality
        prompt_parts = [
            f"You are {npc_name}, an NPC in a crafting RPG world.",
            f"\nBackground:\n{context.npc_narrative}",
            f"\nPrimary identity: {context.npc_primary_tag}",
        ]

        # NPC's affiliations
        if context.npc_belonging_tags:
            affiliations = []
            for tag in context.npc_belonging_tags:
                role = f" ({tag.role})" if tag.role else ""
                sig = f" - significance: {tag.significance:+.0f}" if tag.significance != 0 else ""
                affiliations.append(f"- {tag.tag}{role}{sig}")
            prompt_parts.append(f"\nAffiliations:\n" + "\n".join(affiliations))

        # Cultural affinity (how the NPC's location feels toward various factions)
        if context.npc_cultural_affinity:
            cultural = []
            for tag, value in sorted(context.npc_cultural_affinity.items(),
                                    key=lambda x: abs(x[1]), reverse=True)[:5]:
                cultural.append(f"- {tag}: {value:+.0f}")
            if cultural:
                prompt_parts.append(f"\nCultural context (local attitudes):\n" + "\n".join(cultural))

        # Player's reputation with NPC's factions (CRITICAL for tone)
        prompt_parts.append(f"\n=== PLAYER REPUTATION ===")
        if context.player_affinity:
            rep_entries = []
            for tag, affinity in sorted(context.player_affinity.items(),
                                       key=lambda x: abs(x[1]), reverse=True):
                tier = self._get_affinity_tier(affinity)
                rep_entries.append(f"- {tag}: {affinity:+.0f} ({tier})")
            prompt_parts.append("\n".join(rep_entries))
        else:
            prompt_parts.append("- Unknown to this NPC")

        # Tone guidance based on player's affinity with NPC's factions
        avg_affinity = self._compute_average_affinity(context.player_affinity)
        tone = self._get_dialogue_tone(avg_affinity)
        prompt_parts.append(
            f"\nDialogue tone: {tone}\n"
            f"Respond in character with this tone. Return JSON: "
            f"{{\"dialogue\": \"your response\", \"emotion\": \"emotion\"}}"
        )

        return "\n".join(prompt_parts)

    def _build_user_prompt_with_affinity(self, context: NPCContextForDialogue,
                                        player_input: str,
                                       character=None) -> str:
        """Build user prompt with faction affinity context."""
        parts = [f"The player says: \"{player_input}\""]

        # Player visible stats
        if character:
            if hasattr(character, "leveling"):
                parts.append(f"Player level: {character.leveling.level}")
            if hasattr(character, "class_system") and character.class_system.current_class:
                parts.append(f"Player class: {character.class_system.current_class}")

        # Quest history with this NPC
        if context.quest_history:
            quests = [q.quest_id for q in context.quest_history[-3:]]
            parts.append(f"Quests completed: {', '.join(quests)}")

        # Affinity summary
        if context.player_affinity:
            favorable = [t for t, a in context.player_affinity.items() if a > 50]
            unfavorable = [t for t, a in context.player_affinity.items() if a < -50]
            if favorable:
                parts.append(f"Friendly toward: {', '.join(favorable)}")
            if unfavorable:
                parts.append(f"Hostile toward: {', '.join(unfavorable)}")

        return "\n".join(parts)

    def _parse_dialogue_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM response into dialogue dict."""
        import json

        try:
            # Handle markdown-wrapped JSON
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                json_lines = [l for l in lines[1:-1] if l.strip() and not l.strip().startswith("```")]
                cleaned = "\n".join(json_lines)

            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Treat raw text as dialogue
            return {"dialogue": text[:300], "emotion": "neutral"}

    def _get_affinity_tier(self, affinity: float) -> str:
        """Map affinity value to readable tier."""
        if affinity >= 75:
            return "beloved"
        elif affinity >= 50:
            return "favored"
        elif affinity >= 25:
            return "respected"
        elif affinity > 0:
            return "liked"
        elif affinity == 0:
            return "neutral"
        elif affinity > -25:
            return "disliked"
        elif affinity >= -50:
            return "hated"
        else:
            return "reviled"

    def _compute_average_affinity(self, affinity_dict: Dict[str, float]) -> float:
        """Compute average affinity across all tags."""
        if not affinity_dict:
            return 0.0
        return sum(affinity_dict.values()) / len(affinity_dict)

    def _get_dialogue_tone(self, avg_affinity: float) -> str:
        """Determine dialogue tone based on average affinity."""
        if avg_affinity >= 50:
            return "Warm, friendly, helpful. This player has earned your respect."
        elif avg_affinity >= 25:
            return "Cordial, professional. You regard this player positively."
        elif avg_affinity > -25:
            return "Neutral, reserved. This player is unremarkable to you."
        elif avg_affinity >= -50:
            return "Cool, dismissive. This player has done things you disapprove of."
        else:
            return "Hostile, contemptuous. This player is an enemy. Refuse to help."
