"""Memory management for MeshBot with simple message history."""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from meshbot.meshcore_interface import MeshCoreMessage

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """Represents a single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    message_type: str = "direct"  # direct, channel, broadcast


@dataclass
class UserMemory:
    """Memory data for a single user."""

    user_id: str  # Public key or node identifier
    user_name: Optional[str] = None
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    total_messages: int = 0
    preferences: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None  # Additional context about the user

    def __post_init__(self) -> None:
        if self.preferences is None:
            self.preferences = {}
        if self.context is None:
            self.context = {}


class MemoryManager:
    """Manages user memory and conversation history."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_dm_history: int = 100,
        max_channel_history: int = 1000,
    ):
        """
        Initialize MemoryManager with simple message history.

        Args:
            storage_path: Path for storing user metadata (preferences, context)
            max_dm_history: Maximum number of messages to keep per DM conversation
            max_channel_history: Maximum number of messages to keep for channel history
        """
        self.storage_path = storage_path or Path("memory_metadata.json")
        self._metadata: Dict[str, UserMemory] = {}
        self._lock = asyncio.Lock()
        self._dirty = False

        # Message history buffers
        self.max_dm_history = max_dm_history
        self.max_channel_history = max_channel_history

        # Per-user DM history (user_id -> deque of messages)
        self._dm_history: Dict[str, Deque[ConversationMessage]] = {}

        # General channel history (deque of messages from all users)
        self._channel_history: Deque[ConversationMessage] = deque(
            maxlen=max_channel_history
        )

        logger.info(
            f"Memory manager initialized: {max_dm_history} messages per DM, "
            f"{max_channel_history} messages in channel history"
        )

    async def load(self) -> None:
        """Load user metadata from storage."""
        async with self._lock:
            try:
                if self.storage_path.exists():
                    with open(self.storage_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    for user_id, memory_data in data.items():
                        # Convert timestamp strings back to floats
                        if memory_data.get("first_seen"):
                            memory_data["first_seen"] = float(memory_data["first_seen"])
                        if memory_data.get("last_seen"):
                            memory_data["last_seen"] = float(memory_data["last_seen"])

                        # Remove old conversation_history field if it exists
                        memory_data.pop("conversation_history", None)

                        self._metadata[user_id] = UserMemory(**memory_data)

                    logger.info(
                        f"Loaded {len(self._metadata)} user metadata from {self.storage_path}"
                    )
                else:
                    logger.info("No existing metadata file found, starting fresh")

            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                self._metadata = {}

    async def save(self) -> None:
        """Save user metadata to storage."""
        async with self._lock:
            if not self._dirty:
                return

            try:
                # Prepare data for JSON serialization
                data = {}
                for user_id, memory in self._metadata.items():
                    memory_dict = {
                        "user_id": memory.user_id,
                        "user_name": memory.user_name,
                        "first_seen": memory.first_seen,
                        "last_seen": memory.last_seen,
                        "total_messages": memory.total_messages,
                        "preferences": memory.preferences,
                        "context": memory.context,
                    }
                    data[user_id] = memory_dict

                # Create parent directory if it doesn't exist
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)

                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                self._dirty = False
                logger.debug(
                    f"Saved {len(self._metadata)} user metadata to {self.storage_path}"
                )

            except Exception as e:
                logger.error(f"Error saving metadata: {e}")

    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        message_type: str = "direct",
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Add a message to conversation history.

        Args:
            user_id: The user ID
            role: "user" or "assistant"
            content: The message content
            message_type: "direct", "channel", or "broadcast"
            timestamp: Message timestamp (defaults to current time)
        """
        logger.debug(f"add_message called: user_id={user_id}, role={role}, message_type={message_type}")

        if timestamp is None:
            timestamp = asyncio.get_event_loop().time()

        msg = ConversationMessage(
            role=role, content=content, timestamp=timestamp, message_type=message_type
        )
        logger.debug("ConversationMessage created, attempting to acquire lock...")

        async with self._lock:
            logger.debug("Lock acquired successfully")
            # Add to channel history if it's a channel message
            if message_type == "channel":
                self._channel_history.append(msg)
                logger.debug(
                    f"Added message to channel history ({len(self._channel_history)}/{self.max_channel_history})"
                )
            else:
                # Add to DM history for this user
                if user_id not in self._dm_history:
                    self._dm_history[user_id] = deque(maxlen=self.max_dm_history)

                self._dm_history[user_id].append(msg)
                logger.debug(
                    f"Added message to DM history for {user_id} "
                    f"({len(self._dm_history[user_id])}/{self.max_dm_history})"
                )

        logger.debug("add_message completed successfully")

    async def get_conversation_context(
        self, user_id: str, message_type: str = "direct", max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation context for the LLM.

        Args:
            user_id: The user ID
            message_type: "direct" or "channel"
            max_messages: Maximum messages to return (defaults to all available)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        async with self._lock:
            messages: List[ConversationMessage] = []

            if message_type == "channel":
                messages = list(self._channel_history)
            else:
                if user_id in self._dm_history:
                    messages = list(self._dm_history[user_id])

            # Apply max_messages limit if specified
            if max_messages and len(messages) > max_messages:
                messages = messages[-max_messages:]

            # Convert to LLM format
            return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def get_user_memory(self, user_id: str) -> UserMemory:
        """Get or create memory for a user."""
        async with self._lock:
            if user_id not in self._metadata:
                self._metadata[user_id] = UserMemory(user_id=user_id)
                self._dirty = True
            return self._metadata[user_id]

    async def update_user_info(
        self, user_id: str, user_name: Optional[str] = None
    ) -> None:
        """Update user information."""
        # Note: This method should be called from within a lock context
        if user_id not in self._metadata:
            self._metadata[user_id] = UserMemory(user_id=user_id)
            self._dirty = True

        memory = self._metadata[user_id]

        if user_name and user_name != memory.user_name:
            memory.user_name = user_name
            self._dirty = True

        current_time = asyncio.get_event_loop().time()

        if memory.first_seen is None:
            memory.first_seen = current_time
            self._dirty = True

        memory.last_seen = current_time
        self._dirty = True


    async def set_user_preference(self, user_id: str, key: str, value: Any) -> None:
        """Set a user preference."""
        async with self._lock:
            if user_id not in self._metadata:
                self._metadata[user_id] = UserMemory(user_id=user_id)
                self._dirty = True

            memory = self._metadata[user_id]
            if memory.preferences is None:
                memory.preferences = {}
            memory.preferences[key] = value
            self._dirty = True

    async def get_user_preference(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get a user preference."""
        async with self._lock:
            if user_id not in self._metadata:
                return default

            memory = self._metadata[user_id]
            if memory.preferences is None:
                return default
            return memory.preferences.get(key, default)

    async def set_user_context(self, user_id: str, key: str, value: Any) -> None:
        """Set user context information."""
        async with self._lock:
            if user_id not in self._metadata:
                self._metadata[user_id] = UserMemory(user_id=user_id)
                self._dirty = True

            memory = self._metadata[user_id]
            if memory.context is None:
                memory.context = {}
            memory.context[key] = value
            self._dirty = True

    async def get_user_context(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get user context information."""
        async with self._lock:
            if user_id not in self._metadata:
                return default

            memory = self._metadata[user_id]
            if memory.context is None:
                return default
            return memory.context.get(key, default)

    async def get_all_users(self) -> List[UserMemory]:
        """Get all user memories."""
        async with self._lock:
            return list(self._metadata.values())

    async def get_active_users(self, hours: int = 24) -> List[UserMemory]:
        """Get users active within the last N hours."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            cutoff_time = current_time - (hours * 3600)

            active_users = []
            for memory in self._metadata.values():
                if memory.last_seen and memory.last_seen >= cutoff_time:
                    active_users.append(memory)

            return active_users

    async def cleanup_old_memories(self, days: int = 30) -> int:
        """Remove metadata for users inactive for more than N days."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            cutoff_time = current_time - (days * 24 * 3600)

            users_to_remove = []
            for user_id, memory in self._metadata.items():
                if memory.last_seen and memory.last_seen < cutoff_time:
                    users_to_remove.append(user_id)

            for user_id in users_to_remove:
                del self._metadata[user_id]

            if users_to_remove:
                self._dirty = True
                logger.info(f"Cleaned up {len(users_to_remove)} inactive user metadata")

            return len(users_to_remove)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self._lock:
            total_users = len(self._metadata)
            total_messages = sum(
                memory.total_messages for memory in self._metadata.values()
            )

            # Calculate active users without calling methods that also acquire the lock
            # This avoids deadlock
            current_time = asyncio.get_event_loop().time()
            cutoff_24h = current_time - (24 * 3600)
            cutoff_7d = current_time - (7 * 24 * 3600)

            active_users_24h = sum(
                1 for memory in self._metadata.values()
                if memory.last_seen and memory.last_seen >= cutoff_24h
            )
            active_users_7d = sum(
                1 for memory in self._metadata.values()
                if memory.last_seen and memory.last_seen >= cutoff_7d
            )

            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "active_users_24h": active_users_24h,
                "active_users_7d": active_users_7d,
                "average_messages_per_user": total_messages / max(total_users, 1),
            }
