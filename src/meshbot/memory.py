"""Memory management for MeshBot using Memori library."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memori import ConfigManager, Memori

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

    def __post_init__(self) -> None:
        if self.conversation_history is None:
            self.conversation_history = []
        if self.preferences is None:
            self.preferences = {}
        if self.context is None:
            self.context = {}


class MemoryManager:
    """Manages user memory using Memori library for conversation history."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        database_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize MemoryManager with Memori integration.

        Args:
            storage_path: Path for storing user metadata (preferences, context)
            database_url: Database connection string for Memori (default: SQLite)
            openai_api_key: OpenAI API key for Memori (optional)
            base_url: Base URL for OpenAI-compatible endpoints (optional)
        """
        self.storage_path = storage_path or Path("memory_metadata.json")
        self._metadata: Dict[str, UserMemory] = {}
        self._lock = asyncio.Lock()
        self._dirty = False

        # Initialize Memori for conversation history
        if database_url is None:
            # Use SQLite by default in the same directory as metadata
            db_path = self.storage_path.parent / "memori_conversations.db"
            database_url = f"sqlite:///{db_path}"

        # Get API key from environment if not provided
        if openai_api_key is None:
            openai_api_key = os.getenv("OPENAI_API_KEY")

        # Only initialize Memori if we have an API key
        if openai_api_key:
            try:
                memori_kwargs = {
                    "database_connect": database_url,
                    "conscious_ingest": True,  # Enable working memory
                    "auto_ingest": True,  # Enable dynamic search
                    "openai_api_key": openai_api_key,
                }

                # Add base_url if using OpenAI-compatible endpoint
                if base_url:
                    memori_kwargs["base_url"] = base_url
                    logger.debug(f"Using custom base URL for Memori: {base_url}")

                self.memori = Memori(**memori_kwargs)
                self.memori_enabled = False

                log_msg = f"Initialized Memori with database: {database_url}"
                if base_url:
                    log_msg += f" and custom endpoint: {base_url}"
                logger.info(log_msg)
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Memori: {e}. Memory features disabled."
                )
                self.memori = None
                self.memori_enabled = False
        else:
            logger.info(
                "No LLM API key provided, Memori features disabled. "
                "Set LLM_API_KEY environment variable to enable memory features."
            )
            self.memori = None
            self.memori_enabled = False

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

                        # Don't load conversation history - managed by Memori
                        memory_data["conversation_history"] = []

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

    def enable_memori(self) -> None:
        """Enable Memori memory interception for LLM calls."""
        if self.memori and not self.memori_enabled:
            try:
                self.memori.enable()
                self.memori_enabled = True
                logger.info("Memori memory system enabled")
            except Exception as e:
                logger.error(f"Failed to enable Memori: {e}")

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

    async def add_message(
        self, message: MeshCoreMessage, is_from_user: bool = True
    ) -> None:
        """
        Add a message to user's conversation history.

        Note: Conversation history is managed by Memori automatically.
        This method tracks metadata only.
        """
        async with self._lock:
            # Get or create user memory
            if message.sender not in self._metadata:
                self._metadata[message.sender] = UserMemory(user_id=message.sender)
                self._dirty = True

            memory = self._metadata[message.sender]

            # Update user info (inline to avoid lock issues)
            if message.sender_name and message.sender_name != memory.user_name:
                memory.user_name = message.sender_name
                self._dirty = True

            current_time = asyncio.get_event_loop().time()
            if memory.first_seen is None:
                memory.first_seen = current_time
                self._dirty = True

            memory.last_seen = current_time

            # Increment message count
            memory.total_messages += 1
            self._dirty = True

    async def get_conversation_history(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation history for a user.

        Note: With Memori, conversation history is automatically injected
        into LLM calls. This method returns an empty list as a placeholder
        for backward compatibility.
        """
        # Memori handles conversation history automatically
        # Return empty list for backward compatibility
        return []

    async def get_recent_context(self, user_id: str, max_messages: int = 10) -> str:
        """
        Get formatted recent conversation context for AI.

        Note: With Memori enabled, context is automatically injected.
        This returns a placeholder for backward compatibility.
        """
        # Memori handles context injection automatically
        return ""

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
            active_users_24h = len(await self.get_active_users(24))
            active_users_7d = len(await self.get_active_users(24 * 7))

            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "active_users_24h": active_users_24h,
                "active_users_7d": active_users_7d,
                "average_messages_per_user": total_messages / max(total_users, 1),
                "memori_enabled": self.memori_enabled,
            }
