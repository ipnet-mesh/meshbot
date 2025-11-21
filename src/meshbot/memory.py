"""Memory and history management for MeshBot user interactions."""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

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
    conversation_history: Optional[List[ConversationMessage]] = None
    preferences: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None  # Additional context about the user

    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.preferences is None:
            self.preferences = {}
        if self.context is None:
            self.context = {}


class MemoryManager:
    """Manages user memory and conversation history."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("memory.json")
        self._memories: Dict[str, UserMemory] = {}
        self._lock = asyncio.Lock()
        self._dirty = False

    async def load(self) -> None:
        """Load memories from storage."""
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

                        # Convert conversation history
                        if "conversation_history" in memory_data:
                            history = []
                            for msg_data in memory_data["conversation_history"]:
                                msg_data["timestamp"] = float(msg_data["timestamp"])
                                history.append(ConversationMessage(**msg_data))
                            memory_data["conversation_history"] = history

                        self._memories[user_id] = UserMemory(**memory_data)

                    logger.info(
                        f"Loaded {len(self._memories)} user memories from {self.storage_path}"
                    )
                else:
                    logger.info("No existing memory file found, starting fresh")

            except Exception as e:
                logger.error(f"Error loading memories: {e}")
                self._memories = {}

    async def save(self) -> None:
        """Save memories to storage."""
        async with self._lock:
            if not self._dirty:
                return

            try:
                # Prepare data for JSON serialization
                data = {}
                for user_id, memory in self._memories.items():
                    memory_dict = asdict(memory)
                    # Convert datetime objects to strings for JSON
                    data[user_id] = memory_dict

                # Create parent directory if it doesn't exist
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)

                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                self._dirty = False
                logger.debug(
                    f"Saved {len(self._memories)} user memories to {self.storage_path}"
                )

            except Exception as e:
                logger.error(f"Error saving memories: {e}")

    async def get_user_memory(self, user_id: str) -> UserMemory:
        """Get or create memory for a user."""
        async with self._lock:
            if user_id not in self._memories:
                self._memories[user_id] = UserMemory(user_id=user_id)
                self._dirty = True
            return self._memories[user_id]

    async def update_user_info(
        self, user_id: str, user_name: Optional[str] = None
    ) -> None:
        """Update user information."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)

            if user_name and user_name != memory.user_name:
                memory.user_name = user_name
                self._dirty = True

            current_time = asyncio.get_event_loop().time()

            if memory.first_seen is None:
                memory.first_seen = current_time
                self._dirty = True

            memory.last_seen = current_time
            self._dirty = True

    async def add_message(
        self, message: MeshCoreMessage, is_from_user: bool = True
    ) -> None:
        """Add a message to user's conversation history."""
        async with self._lock:
            memory = await self.get_user_memory(message.sender)

            # Update user info
            await self.update_user_info(message.sender, message.sender_name)

            # Add message to history
            role = "user" if is_from_user else "assistant"
            conversation_message = ConversationMessage(
                role=role,
                content=message.content,
                timestamp=message.timestamp,
                message_type=message.message_type,
            )

            if memory.conversation_history is None:
                memory.conversation_history = []
            memory.conversation_history.append(conversation_message)
            memory.total_messages += 1
            self._dirty = True

            # Keep only last 100 messages to prevent memory bloat
            if memory.conversation_history and len(memory.conversation_history) > 100:
                memory.conversation_history = memory.conversation_history[-100:]
                self._dirty = True

    async def get_conversation_history(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """Get conversation history for a user."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            history = memory.conversation_history or []

            if limit:
                history = history[-limit:]

            return history.copy()

    async def get_recent_context(self, user_id: str, max_messages: int = 10) -> str:
        """Get formatted recent conversation context for AI."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            history = memory.conversation_history or []
            recent_messages = history[-max_messages:]

            if not recent_messages:
                return ""

            context_lines = []
            for msg in recent_messages:
                timestamp_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
                role_name = "User" if msg.role == "user" else "Assistant"
                context_lines.append(f"[{timestamp_str}] {role_name}: {msg.content}")

            return "\n".join(context_lines)

    async def set_user_preference(self, user_id: str, key: str, value: Any) -> None:
        """Set a user preference."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            if memory.preferences is None:
                memory.preferences = {}
            memory.preferences[key] = value
            self._dirty = True

    async def get_user_preference(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get a user preference."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            if memory.preferences is None:
                return default
            return memory.preferences.get(key, default)

    async def set_user_context(self, user_id: str, key: str, value: Any) -> None:
        """Set user context information."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            if memory.context is None:
                memory.context = {}
            memory.context[key] = value
            self._dirty = True

    async def get_user_context(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Get user context information."""
        async with self._lock:
            memory = await self.get_user_memory(user_id)
            if memory.context is None:
                return default
            return memory.context.get(key, default)

    async def get_all_users(self) -> List[UserMemory]:
        """Get all user memories."""
        async with self._lock:
            return list(self._memories.values())

    async def get_active_users(self, hours: int = 24) -> List[UserMemory]:
        """Get users active within the last N hours."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            cutoff_time = current_time - (hours * 3600)

            active_users = []
            for memory in self._memories.values():
                if memory.last_seen and memory.last_seen >= cutoff_time:
                    active_users.append(memory)

            return active_users

    async def cleanup_old_memories(self, days: int = 30) -> int:
        """Remove memories for users inactive for more than N days."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            cutoff_time = current_time - (days * 24 * 3600)

            users_to_remove = []
            for user_id, memory in self._memories.items():
                if memory.last_seen and memory.last_seen < cutoff_time:
                    users_to_remove.append(user_id)

            for user_id in users_to_remove:
                del self._memories[user_id]

            if users_to_remove:
                self._dirty = True
                logger.info(f"Cleaned up {len(users_to_remove)} inactive user memories")

            return len(users_to_remove)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self._lock:
            total_users = len(self._memories)
            total_messages = sum(
                memory.total_messages for memory in self._memories.values()
            )
            active_users_24h = len(await self.get_active_users(24))
            active_users_7d = len(await self.get_active_users(24 * 7))

            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "active_users_24h": active_users_24h,
                "active_users_7d": active_users_7d,
                "average_messages_per_user": total_messages / max(total_users, 1),
            }
