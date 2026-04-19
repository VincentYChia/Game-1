"""NPCAgent — LLM-powered dialogue generation with memory context.

Each NPC has an agent that:
1. Builds a context window from NPC personality + memory + world state
2. Generates dialogue via BackendManager
3. Updates NPC memory after each interaction
4. Processes gossip (world events that reach this NPC)

The system layers on top of the existing 3 stationary NPCs without
replacing their basic dialogue cycling.

Usage:
    agent_system = NPCAgentSystem.get_instance()
    agent_system.initialize(config, npc_memory_manager, world_query)

    response = agent_system.generate_dialogue(npc_id, player_input, character)
    # Returns NPCDialogueResult with text, emotion, relationship change
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from world_system.living_world.npc.npc_memory import NPCMemory, NPCMemoryManager
from world_system.living_world.factions import FactionSystem
from world_system.living_world.factions.dialogue_helper import assemble_dialogue_context


@dataclass
class NPCDialogueResult:
    """Result from NPC dialogue generation."""
    text: str
    emotion: str = "neutral"
    relationship_delta: float = 0.0
    success: bool = True
    from_fallback: bool = False


@dataclass
class GossipEvent:
    """A world event that can propagate to NPCs as gossip."""
    event_summary: str
    significance: float          # 0.0 to 1.0
    source_x: float = 0.0
    source_y: float = 0.0
    source_chunk: Tuple[int, int] = (0, 0)
    event_category: str = ""     # population_change, resource_pressure, etc.
    game_time: float = 0.0
    propagation_delay: float = 0.0  # Seconds before NPC hears this


class NPCAgentSystem:
    """Manages NPC agents for all NPCs. Singleton.

    Coordinates dialogue generation, gossip propagation, and
    event reactions across all NPC agents.
    """

    _instance: ClassVar[Optional[NPCAgentSystem]] = None

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._personality_templates: Dict[str, Dict] = {}
        self._gossip_config: Dict[str, Any] = {}
        self._relationship_thresholds: Dict[str, float] = {}
        self._memory_manager: Optional[NPCMemoryManager] = None
        self._world_query = None  # WorldQuery instance
        self._backend_manager = None  # BackendManager instance
        self._pending_gossip: List[Tuple[str, GossipEvent, float]] = []  # (npc_id, event, deliver_at)
        self._npc_personalities: Dict[str, str] = {}  # npc_id → template_name
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> NPCAgentSystem:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def initialize(self, config_path: Optional[str] = None,
                   memory_manager: Optional[NPCMemoryManager] = None,
                   world_query=None,
                   backend_manager=None) -> None:
        """Initialize the NPC agent system.

        Args:
            config_path: Path to npc-personalities.json.
            memory_manager: NPCMemoryManager instance.
            world_query: WorldQuery instance for world context.
            backend_manager: BackendManager instance for LLM calls.
        """
        if self._initialized:
            return

        # Load config
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                self._config = json.load(f)
        else:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))
            default_path = os.path.join(
                project_root, "world_system", "config", "npc-personalities.json"
            )
            if os.path.exists(default_path):
                with open(default_path, "r") as f:
                    self._config = json.load(f)

        self._personality_templates = self._config.get("personality_templates", {})
        self._gossip_config = self._config.get("gossip_propagation", {})
        self._relationship_thresholds = self._config.get("relationship_thresholds", {})

        # Wire dependencies
        self._memory_manager = memory_manager or NPCMemoryManager.get_instance()
        if not self._memory_manager._initialized:
            self._memory_manager.initialize(self._config)
        self._world_query = world_query
        self._backend_manager = backend_manager

        self._initialized = True
        print(f"[NPCAgentSystem] Initialized with {len(self._personality_templates)} personality templates")

    def assign_personality(self, npc_id: str, template_name: str) -> None:
        """Assign a personality template to an NPC."""
        self._npc_personalities[npc_id] = template_name

    def get_personality(self, npc_id: str) -> Dict[str, Any]:
        """Get the personality template for an NPC."""
        template_name = self._npc_personalities.get(npc_id, "default")
        return self._personality_templates.get(
            template_name,
            self._personality_templates.get("default", {})
        )

    # ── Dialogue Generation ───────────────────────────────────────────

    def generate_dialogue(self, npc_id: str, player_input: str,
                          character=None,
                          npc_name: str = "NPC") -> NPCDialogueResult:
        """Generate contextual dialogue for an NPC.

        Args:
            npc_id: The NPC's unique ID.
            player_input: What the player said/did.
            character: Player Character instance (for visible state).
            npc_name: Display name of the NPC.

        Returns:
            NPCDialogueResult with generated text and metadata.
        """
        if not self._initialized:
            return NPCDialogueResult(
                text="...", success=False, from_fallback=True
            )

        memory = self._memory_manager.get_memory(npc_id)
        personality = self.get_personality(npc_id)

        # Build context
        system_prompt = self._build_system_prompt(npc_id, npc_name, personality, memory)
        user_prompt = self._build_user_prompt(player_input, character, memory)

        # Try LLM generation
        if self._backend_manager:
            text, err = self._backend_manager.generate(
                task="dialogue",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.6,
                max_tokens=personality.get("dialogue_style", {}).get(
                    "max_response_length", 150
                ),
            )
            if text and not err:
                result = self._parse_dialogue_response(text, memory)
                self._update_memory_after_dialogue(memory, player_input, result)
                return result

        # Fallback: use personality-flavored template
        return self._generate_fallback(npc_id, npc_name, personality, memory)

    def _build_system_prompt(self, npc_id: str, npc_name: str,
                             personality: Dict, memory: NPCMemory) -> str:
        """Build the system prompt for NPC dialogue generation."""
        voice = personality.get("voice", "Friendly villager.")
        domains = personality.get("knowledge_domains", ["general"])
        style = personality.get("dialogue_style", {})
        max_len = style.get("max_response_length", 150)

        relationship_label = memory.get_relationship_label(self._relationship_thresholds)

        # Knowledge context
        knowledge_text = ""
        if memory.knowledge:
            recent_knowledge = memory.knowledge[-10:]
            knowledge_text = "\n".join(f"- {k}" for k in recent_knowledge)

        # Conversation history
        history_text = memory.conversation_summary or "No previous conversations."

        # Add faction context if available
        faction_context = self._build_faction_context(npc_id)

        return (
            f"You are {npc_name}, an NPC in a crafting RPG.\n"
            f"Personality: {voice}\n"
            f"Knowledge domains: {', '.join(domains)}\n"
            f"Current emotion: {memory.emotional_state}\n"
            f"Relationship with player: {relationship_label} ({memory.relationship_score:.2f})\n"
            f"Interactions so far: {memory.interaction_count}\n\n"
            f"Things you know about the world:\n{knowledge_text or 'Nothing notable yet.'}\n\n"
            f"Previous conversation summary:\n{history_text}\n\n"
            f"Player reputation: {', '.join(memory.player_reputation_tags) or 'Unknown'}\n\n"
            f"{faction_context}"
            f"Respond in-character. Keep response under {max_len} characters.\n"
            f"Return JSON: {{\"dialogue\": \"your response\", \"emotion\": \"your_emotion\", "
            f"\"disposition_change\": 0.0}}\n"
            f"disposition_change should be between -0.1 and 0.1 based on the interaction."
        )

    def _build_faction_context(self, npc_id: str) -> str:
        """Build faction affinity context for dialogue.

        Returns formatted faction information or empty string if unavailable.
        """
        try:
            fs = FactionSystem.get_instance()
            npc_profile = fs.get_npc_profile(npc_id)
            if not npc_profile or not npc_profile.belonging_tags:
                return ""

            # Summarize NPC's faction tags
            tags = [f"{tag.tag} ({tag.significance:.1%})"
                    for tag in npc_profile.belonging_tags.values()[:5]]
            return f"NPC affiliations: {', '.join(tags)}\n\n"
        except Exception:
            return ""

    def _build_user_prompt(self, player_input: str, character,
                           memory: NPCMemory) -> str:
        """Build the user prompt with player context."""
        parts = [f"The player says: \"{player_input}\""]

        if character:
            if hasattr(character, "leveling") and hasattr(character.leveling, "level"):
                parts.append(f"Player level: {character.leveling.level}")
            if hasattr(character, "class_system"):
                cs = character.class_system
                if hasattr(cs, "current_class") and cs.current_class:
                    parts.append(f"Player class: {cs.current_class}")
            if hasattr(character, "titles"):
                ts = character.titles
                if hasattr(ts, "active_title") and ts.active_title:
                    parts.append(f"Player title: {ts.active_title}")

        # Add world context from WorldQuery if available
        if self._world_query:
            try:
                summary = self._world_query.get_world_summary(0.0)
                conditions = summary.get("ongoing_conditions", [])
                if conditions:
                    cond_text = "; ".join(
                        c.get("narrative", "")[:80] for c in conditions[:3]
                    )
                    parts.append(f"Current world conditions: {cond_text}")
            except Exception:
                pass

        return "\n".join(parts)

    def _parse_dialogue_response(self, text: str,
                                 memory: NPCMemory) -> NPCDialogueResult:
        """Parse LLM response into NPCDialogueResult."""
        try:
            # Handle markdown-wrapped JSON
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.strip().startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.strip().startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                cleaned = "\n".join(json_lines)

            data = json.loads(cleaned)
            return NPCDialogueResult(
                text=data.get("dialogue", text),
                emotion=data.get("emotion", memory.emotional_state),
                relationship_delta=max(-0.1, min(0.1,
                    data.get("disposition_change", 0.0)
                )),
                success=True,
                from_fallback=False,
            )
        except (json.JSONDecodeError, KeyError):
            # Treat raw text as dialogue
            return NPCDialogueResult(
                text=text[:300],
                emotion=memory.emotional_state,
                relationship_delta=0.0,
                success=True,
                from_fallback=False,
            )

    def _update_memory_after_dialogue(self, memory: NPCMemory,
                                      player_input: str,
                                      result: NPCDialogueResult) -> None:
        """Update NPC memory after a dialogue exchange."""
        memory.interaction_count += 1
        memory.last_interaction_time = time.time()
        memory.set_emotion(result.emotion)
        memory.adjust_relationship(result.relationship_delta)

        # Append to conversation summary (keep bounded)
        snippet = f"Player: {player_input[:60]}. NPC: {result.text[:60]}"
        if memory.conversation_summary:
            memory.conversation_summary += f" | {snippet}"
        else:
            memory.conversation_summary = snippet

        max_len = memory._max_summary_length
        if len(memory.conversation_summary) > max_len:
            # Keep the most recent portion
            memory.conversation_summary = memory.conversation_summary[-max_len:]

    def _generate_fallback(self, npc_id: str, npc_name: str,
                           personality: Dict, memory: NPCMemory) -> NPCDialogueResult:
        """Generate template-based fallback dialogue."""
        emotion = memory.emotional_state
        label = memory.get_relationship_label(self._relationship_thresholds)

        # Simple template selection based on relationship and emotion
        if label in ("hostile", "unfriendly"):
            text = "I have nothing to say to you."
        elif label == "neutral":
            text = f"Hmm? What do you need?"
        elif label == "friendly":
            text = f"Good to see you again. What can I help with?"
        elif label in ("trusted", "devoted"):
            text = f"Always a pleasure! What's on your mind?"
        else:
            text = f"Hello there."

        return NPCDialogueResult(
            text=text,
            emotion=emotion,
            relationship_delta=0.0,
            success=True,
            from_fallback=True,
        )

    # ── Gossip Propagation ────────────────────────────────────────────

    def propagate_gossip(self, event_summary: str, significance: float,
                         source_x: float, source_y: float,
                         event_category: str = "",
                         game_time: float = 0.0) -> int:
        """Schedule gossip propagation to nearby NPCs.

        Events spread outward from the source position with time delays
        based on distance. Returns count of NPCs who will hear the gossip.

        Args:
            event_summary: One-line summary of the event.
            significance: How notable (0.0-1.0).
            source_x, source_y: Where the event occurred.
            event_category: Category for interest filtering.
            game_time: Current game time.

        Returns:
            Number of NPCs scheduled to receive this gossip.
        """
        min_sig = self._gossip_config.get("minimum_significance", 0.1)
        if significance < min_sig:
            return 0

        gossip = GossipEvent(
            event_summary=event_summary,
            significance=significance,
            source_x=source_x,
            source_y=source_y,
            source_chunk=(int(source_x) // 16, int(source_y) // 16),
            event_category=event_category,
            game_time=game_time,
        )

        # Get all NPC entities from memory manager
        count = 0
        for npc_id in self._memory_manager.get_all_memories():
            delay = self._calculate_gossip_delay(npc_id, gossip)
            if delay is not None:
                # Check interest
                personality = self.get_personality(npc_id)
                interests = personality.get("gossip_interests", [])
                if event_category and interests and event_category not in interests:
                    continue

                deliver_at = game_time + delay
                self._pending_gossip.append((npc_id, gossip, deliver_at))
                count += 1

        return count

    def _calculate_gossip_delay(self, npc_id: str,
                                gossip: GossipEvent) -> Optional[float]:
        """Calculate how long before an NPC hears gossip based on distance."""
        # For now, use a flat delay based on configuration
        # In a full implementation, we'd look up NPC positions from EntityRegistry
        immediate_r = self._gossip_config.get("immediate_radius_chunks", 0)
        short_r = self._gossip_config.get("short_delay_radius_chunks", 1)
        medium_r = self._gossip_config.get("medium_delay_radius_chunks", 4)

        short_delay = self._gossip_config.get("short_delay_game_seconds", 60.0)
        medium_delay = self._gossip_config.get("medium_delay_game_seconds", 180.0)
        global_delay = self._gossip_config.get("global_delay_game_seconds", 420.0)

        # Default to medium delay (NPC positions would refine this)
        return short_delay

    def update(self, game_time: float) -> int:
        """Process pending gossip. Called from game loop.

        Returns count of gossip items delivered this frame.
        """
        if not self._pending_gossip:
            return 0

        delivered = 0
        remaining = []
        for npc_id, gossip, deliver_at in self._pending_gossip:
            if game_time >= deliver_at:
                memory = self._memory_manager.get_memory(npc_id)
                memory.add_knowledge(gossip.event_summary)
                delivered += 1
            else:
                remaining.append((npc_id, gossip, deliver_at))

        self._pending_gossip = remaining
        return delivered

    # ── Event Reactions ───────────────────────────────────────────────

    def on_world_event(self, event_type: str, event_data: Dict[str, Any],
                       game_time: float = 0.0) -> None:
        """React to a world event. Updates NPC emotions and relationships.

        Called by the EventBus subscriber when relevant events occur.
        """
        for npc_id, template_name in self._npc_personalities.items():
            personality = self.get_personality(npc_id)
            modifiers = personality.get("reaction_modifiers", {})
            modifier = modifiers.get(event_type)
            if not modifier:
                continue

            memory = self._memory_manager.get_memory(npc_id)

            # Apply relationship change
            delta = modifier.get("relationship_delta", 0.0)
            if delta != 0:
                memory.adjust_relationship(delta)

            # Apply emotion change
            emotion = modifier.get("emotion")
            if emotion:
                memory.set_emotion(emotion)

    # ── Serialization ─────────────────────────────────────────────────

    def save(self) -> Dict[str, Any]:
        """Serialize agent system state."""
        return {
            "npc_personalities": dict(self._npc_personalities),
            "pending_gossip_count": len(self._pending_gossip),
            "memories": self._memory_manager.save_all(),
        }

    def load(self, data: Dict[str, Any]) -> None:
        """Restore agent system state."""
        self._npc_personalities = data.get("npc_personalities", {})
        memories_data = data.get("memories", {})
        if memories_data:
            self._memory_manager.load_all(memories_data)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "npc_count": len(self._npc_personalities),
            "pending_gossip": len(self._pending_gossip),
            "memory_stats": self._memory_manager.stats if self._memory_manager else {},
        }
