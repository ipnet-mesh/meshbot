"""Memory management for MeshBot with file-based storage."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import MeshBotStorage

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation history using file-based storage."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_lines: int = 1000,
    ):
        """
        Initialize MemoryManager with file-based storage.

        Args:
            storage_path: Path to data directory (defaults to data/)
            max_lines: Maximum number of messages to return in conversation context (for compatibility)
        """
        # Use the data directory for storage
        if storage_path is None:
            data_path = Path("data")
        elif storage_path.is_file():
            # If it's a file path, use its parent directory
            data_path = storage_path.parent
        else:
            data_path = storage_path

        self.storage = MeshBotStorage(data_path)
        self.max_lines = max_lines

        logger.info(f"Memory manager initialized: {data_path}")

    async def load(self) -> None:
        """Initialize file-based storage (create data directory if needed)."""
        try:
            await self.storage.initialize()
            logger.info("Storage initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing storage: {e}")

    async def save(self) -> None:
        """Save is a no-op since file writes are immediate."""
        pass

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
            user_id: The user/conversation ID
            role: "user" or "assistant"
            content: The message content
            message_type: "direct", "channel", or "broadcast"
            timestamp: Message timestamp (defaults to current time)
        """
        try:
            await self.storage.add_message(
                conversation_id=user_id,
                role=role,
                content=content,
                message_type=message_type,
                timestamp=timestamp,
            )
            logger.debug(f"Added message to {message_type} conversation {user_id}")
        except Exception as e:
            logger.error(f"Error saving message: {e}")

    async def get_conversation_context(
        self,
        user_id: str,
        message_type: str = "direct",
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Get conversation context for the LLM.

        Args:
            user_id: The user/conversation ID
            message_type: "direct" or "channel"
            max_messages: Maximum messages to return (defaults to self.max_lines)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        try:
            # Use max_lines if max_messages not specified
            limit = max_messages if max_messages is not None else self.max_lines

            messages = await self.storage.get_conversation_messages(
                conversation_id=user_id,
                limit=limit,
            )

            # Return only role and content for LLM context
            return [
                {"role": msg["role"], "content": msg["content"]} for msg in messages
            ]

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []

    async def get_conversation_history(
        self, user_id: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get recent conversation history with a user (for tools).

        Args:
            user_id: The user/conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        return await self.get_conversation_context(user_id, "direct", limit)

    async def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """
        Get basic info about a user based on their conversation stats.

        Returns a dict with user_id, total_messages, first_seen, last_seen.
        """
        try:
            stats = await self.storage.get_conversation_stats(user_id)

            return {
                "user_id": user_id,
                "user_name": None,
                "total_messages": stats["total_messages"],
                "first_seen": stats["first_seen"],
                "last_seen": stats["last_seen"],
            }
        except Exception as e:
            logger.error(f"Error getting user memory: {e}")
            return {
                "user_id": user_id,
                "user_name": None,
                "total_messages": 0,
                "first_seen": None,
                "last_seen": None,
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        try:
            stats = await self.storage.get_all_statistics()

            return {
                "total_users": stats["total_conversations"],
                "total_messages": stats["total_messages"],
                "dm_conversations": stats["total_conversations"],
                "channel_messages": stats["channel_messages"],
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_users": 0,
                "total_messages": 0,
                "dm_conversations": 0,
                "channel_messages": 0,
            }
