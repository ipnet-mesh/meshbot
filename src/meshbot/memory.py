"""Memory management for MeshBot with simple text file chat logs."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation history using simple text file logs."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_lines: int = 1000,
    ):
        """
        Initialize MemoryManager with file-based chat logs.

        Args:
            storage_path: Directory for storing chat log files (not used, kept for compatibility)
            max_lines: Maximum number of lines to keep in each log file
        """
        self.logs_dir = Path("logs")
        self.max_lines = max_lines

        # In-memory cache of loaded logs
        self._dm_logs: Dict[str, List[str]] = {}  # user_id -> list of log lines
        self._channel_log: List[str] = []

        logger.info(f"Memory manager initialized: {max_lines} lines per log file")

    async def load(self) -> None:
        """Load all chat logs from disk."""
        try:
            # Create logs directory if it doesn't exist
            self.logs_dir.mkdir(exist_ok=True)

            # Load channel log
            channel_log_path = self.logs_dir / "channel.txt"
            if channel_log_path.exists():
                with open(channel_log_path, "r", encoding="utf-8") as f:
                    self._channel_log = f.read().splitlines()
                logger.info(f"Loaded {len(self._channel_log)} lines from channel log")

            # Load all DM logs
            dm_log_count = 0
            for log_file in self.logs_dir.glob("dm_*.txt"):
                user_id = log_file.stem.replace("dm_", "")
                with open(log_file, "r", encoding="utf-8") as f:
                    self._dm_logs[user_id] = f.read().splitlines()
                dm_log_count += 1

            logger.info(f"Loaded {dm_log_count} DM logs from disk")

        except Exception as e:
            logger.error(f"Error loading logs: {e}")

    async def save(self) -> None:
        """Save is a no-op since we write directly to files on each message."""
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
        Add a message to conversation history by appending to log file.

        Args:
            user_id: The user ID
            role: "user" or "assistant"
            content: The message content
            message_type: "direct", "channel", or "broadcast"
            timestamp: Message timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = asyncio.get_event_loop().time()

        # Format: timestamp|role|content
        # Escape pipes in content by replacing with unicode pipe char
        safe_content = content.replace("|", "│")
        log_line = f"{timestamp}|{role}|{safe_content}"

        try:
            if message_type == "channel":
                # Append to channel log
                log_path = self.logs_dir / "channel.txt"
                self._channel_log.append(log_line)

                # Trim if too long
                if len(self._channel_log) > self.max_lines:
                    self._channel_log = self._channel_log[-self.max_lines:]

                # Write entire log back to file
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(self._channel_log) + "\n")

            else:
                # Append to DM log for this user
                if user_id not in self._dm_logs:
                    self._dm_logs[user_id] = []

                self._dm_logs[user_id].append(log_line)

                # Trim if too long
                if len(self._dm_logs[user_id]) > self.max_lines:
                    self._dm_logs[user_id] = self._dm_logs[user_id][-self.max_lines:]

                # Write entire log back to file
                log_path = self.logs_dir / f"dm_{user_id}.txt"
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(self._dm_logs[user_id]) + "\n")

            logger.debug(f"Added message to {message_type} log for {user_id}")

        except Exception as e:
            logger.error(f"Error saving message to log: {e}")

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
        try:
            log_lines = []

            if message_type == "channel":
                log_lines = self._channel_log
            else:
                log_lines = self._dm_logs.get(user_id, [])

            # Apply max_messages limit if specified
            if max_messages and len(log_lines) > max_messages:
                log_lines = log_lines[-max_messages:]

            # Parse log lines and convert to LLM format
            messages = []
            for line in log_lines:
                parts = line.split("|", 2)  # Split on first 2 pipes only
                if len(parts) == 3:
                    timestamp, role, content = parts
                    # Restore original pipes (that were escaped)
                    content = content.replace("│", "|")
                    messages.append({"role": role, "content": content})

            return messages

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []

    async def get_conversation_history(
        self, user_id: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get recent conversation history with a user (for tools).

        Args:
            user_id: The user ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        return await self.get_conversation_context(user_id, "direct", limit)

    async def get_user_memory(self, user_id: str) -> Dict[str, any]:
        """
        Get basic info about a user based on their log file.

        Returns a dict with user_id, total_messages, first_seen, last_seen.
        """
        log_lines = self._dm_logs.get(user_id, [])

        first_seen = None
        last_seen = None

        if log_lines:
            # Parse first and last timestamps
            try:
                first_parts = log_lines[0].split("|", 1)
                if first_parts:
                    first_seen = float(first_parts[0])

                last_parts = log_lines[-1].split("|", 1)
                if last_parts:
                    last_seen = float(last_parts[0])
            except (ValueError, IndexError):
                pass

        return {
            "user_id": user_id,
            "user_name": None,
            "total_messages": len(log_lines),
            "first_seen": first_seen,
            "last_seen": last_seen,
        }

    async def get_statistics(self) -> Dict[str, any]:
        """Get memory statistics."""
        total_users = len(self._dm_logs)
        total_messages = sum(len(lines) for lines in self._dm_logs.values())
        total_messages += len(self._channel_log)

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "dm_conversations": total_users,
            "channel_messages": len(self._channel_log),
        }
