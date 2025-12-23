"""
Debug Message Display System

Provides on-screen debug output with automatic condensing:
- Max 5 messages visible at once
- Oldest messages replaced by newest
- Abbreviated format for readability
- Integrates with existing notification system
"""

from collections import deque
from typing import Optional
import re


class DebugMessageManager:
    """
    Manages on-screen debug messages with automatic condensing.

    Features:
    - Max 5 messages displayed simultaneously
    - FIFO queue (oldest replaced by newest)
    - Message abbreviation for readability
    - Deduplication of repetitive messages
    """

    def __init__(self, max_messages: int = 5):
        """
        Initialize debug message manager.

        Args:
            max_messages: Maximum number of messages to display (default: 5)
        """
        self.max_messages = max_messages
        self.messages = deque(maxlen=max_messages)  # Auto-discards oldest
        self.message_counts = {}  # Track message frequency for deduplication
        self.last_message = None
        self.enabled = True

    def add_message(self, message: str, force: bool = False):
        """
        Add a debug message to the display queue.

        Args:
            message: Debug message to display
            force: If True, always add message (skip deduplication)
        """
        if not self.enabled:
            return

        # Abbreviate message for screen display
        abbreviated = self._abbreviate_message(message)

        # Check for consecutive duplicates
        if not force and abbreviated == self.last_message:
            # Increment counter instead of adding duplicate
            signature = self._get_message_signature(abbreviated)
            self.message_counts[signature] = self.message_counts.get(signature, 1) + 1

            # Update the last message with count
            if self.messages and self.messages[-1].startswith(abbreviated.split()[0]):
                count = self.message_counts[signature]
                # Replace last message with updated count
                base_msg = abbreviated.split(' (x')[0] if ' (x' in abbreviated else abbreviated
                self.messages[-1] = f"{base_msg} (x{count})"
            return

        # Reset count for new message
        signature = self._get_message_signature(abbreviated)
        self.message_counts[signature] = 1
        self.last_message = abbreviated

        # Add to queue (automatically removes oldest if full)
        self.messages.append(abbreviated)

    def _abbreviate_message(self, message: str) -> str:
        """
        Abbreviate message for on-screen display.

        Rules:
        - Truncate long messages to ~60 characters
        - Replace verbose keywords with symbols/abbreviations
        - Keep critical information intact
        """
        # Common abbreviations
        abbreviations = {
            'ENCHANTMENT APPLIED': '✨ ENCH',
            'TURRET ATTACK': '🏹 TURRET',
            'PLAYER ATTACK': '⚔️  ATK',
            'TRAINING DUMMY HIT': '🎯 HIT',
            'Effect Params': 'Params',
            'baseDamage': 'dmg',
            'Damage': 'Dmg',
            'Health': 'HP',
            'including': 'incl',
            'enchantment': 'ench',
        }

        abbreviated = message
        for full, short in abbreviations.items():
            abbreviated = abbreviated.replace(full, short)

        # Truncate if too long
        max_length = 80
        if len(abbreviated) > max_length:
            abbreviated = abbreviated[:max_length-3] + "..."

        return abbreviated

    def _get_message_signature(self, message: str) -> str:
        """
        Get normalized signature for message deduplication.

        Replaces numbers with placeholders to group similar messages.
        """
        # Replace all numbers with N placeholder
        sig = re.sub(r'\d+\.?\d*', 'N', message)
        # Replace N/N patterns with single N
        sig = re.sub(r'N/N', 'N', sig)
        return sig

    def get_messages(self) -> list:
        """
        Get current messages for display.

        Returns:
            List of message strings
        """
        return list(self.messages)

    def clear(self):
        """Clear all messages."""
        self.messages.clear()
        self.message_counts.clear()
        self.last_message = None

    def enable(self):
        """Enable debug message display."""
        self.enabled = True

    def disable(self):
        """Disable debug message display."""
        self.enabled = False

    def is_enabled(self) -> bool:
        """Check if debug messages are enabled."""
        return self.enabled

    def get_stats(self) -> dict:
        """
        Get statistics about message display.

        Returns:
            Dict with message_count, unique_signatures, enabled
        """
        return {
            "message_count": len(self.messages),
            "unique_signatures": len(self.message_counts),
            "enabled": self.enabled,
            "max_messages": self.max_messages
        }


# Global instance
_debug_manager = None


def get_debug_manager(max_messages: int = 5) -> DebugMessageManager:
    """
    Get global debug message manager instance.

    Args:
        max_messages: Maximum messages to display (only used on first call)

    Returns:
        DebugMessageManager instance
    """
    global _debug_manager
    if _debug_manager is None:
        _debug_manager = DebugMessageManager(max_messages)
    return _debug_manager


def debug_print(message: str, force: bool = False):
    """
    Print debug message to both console and on-screen display.

    Args:
        message: Message to display
        force: If True, always add to display (skip deduplication)
    """
    # Print to console
    print(message)

    # Add to on-screen display
    manager = get_debug_manager()
    manager.add_message(message, force=force)


def clear_debug_messages():
    """Clear all on-screen debug messages."""
    manager = get_debug_manager()
    manager.clear()


def toggle_debug_messages() -> bool:
    """
    Toggle debug message display on/off.

    Returns:
        New enabled state (True/False)
    """
    manager = get_debug_manager()
    if manager.is_enabled():
        manager.disable()
        return False
    else:
        manager.enable()
        return True
