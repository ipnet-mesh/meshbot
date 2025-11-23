"""Message storage operations."""

import logging
import time
from typing import Any, Dict, List, Optional, cast

from .base import BaseStorage

logger = logging.getLogger(__name__)


class MessageStorage(BaseStorage):
    """Handles message storage and retrieval operations."""

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "direct",
        timestamp: Optional[float] = None,
        sender: Optional[str] = None,
    ) -> None:
        """
        Add a message to the conversation's message file.

        Args:
            conversation_id: Conversation/user/channel ID
            role: "user" or "assistant"
            content: Message content
            message_type: "direct", "channel", or "broadcast"
            timestamp: Message timestamp (defaults to current time)
            sender: Sender public key (optional)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            messages_file = self._get_messages_file(conversation_id, message_type)

            # Append message to file
            # Format: timestamp|message_type|role|content|sender
            with open(messages_file, "a", encoding="utf-8") as f:
                # Escape pipes in content
                escaped_content = content.replace("|", "\\|")
                sender_str = sender or ""
                msg_line = f"{timestamp}|{message_type}|{role}|"
                msg_line += f"{escaped_content}|{sender_str}\n"
                f.write(msg_line)

            logger.debug(
                f"Added message to {message_type} conversation {conversation_id}"
            )
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: Conversation/user/channel ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of message dicts with keys: role, content, timestamp, sender
        """
        try:
            # Determine if it's a channel or node
            if self._is_channel_id(conversation_id):
                messages_file = self._get_channel_dir(conversation_id) / "messages.txt"
            else:
                messages_file = self._get_user_messages_file(conversation_id)

            if not messages_file.exists():
                return []

            messages = []
            with open(messages_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Parse line: timestamp|message_type|role|content|sender
                    parts = line.split("|")
                    if len(parts) >= 4:
                        timestamp_str = parts[0]
                        _ = parts[1]  # message_type (not used here, but part of format)
                        role = parts[2]
                        # Content might contain escaped pipes
                        content = "|".join(parts[3:-1]) if len(parts) > 4 else parts[3]
                        content = content.replace("\\|", "|")  # Unescape
                        sender = parts[-1] if len(parts) > 4 else None

                        messages.append(
                            {
                                "role": role,
                                "content": content,
                                "timestamp": float(timestamp_str),
                                "sender": sender,
                            }
                        )

            # Apply offset and limit
            if offset > 0:
                messages = messages[offset:]
            if limit is not None:
                messages = messages[:limit]

            return messages

        except Exception as e:
            logger.error(f"Error getting conversation messages: {e}")
            return []

    async def search_messages(
        self,
        conversation_id: Optional[str] = None,
        keyword: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search messages with filters.

        Args:
            conversation_id: Filter by conversation (optional)
            keyword: Search for keyword in content (optional, case-insensitive)
            since: Only messages after this timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of message dicts
        """
        try:
            messages = []

            # Determine which files to search
            if conversation_id:
                # Determine if it's a channel or node
                if self._is_channel_id(conversation_id):
                    files_to_search = [
                        self._get_channel_dir(conversation_id) / "messages.txt"
                    ]
                else:
                    files_to_search = [
                        self._get_node_dir(conversation_id) / "messages.txt"
                    ]
            else:
                # Search all message files (both nodes and channels)
                files_to_search = []
                # Search node directories
                for node_dir in self.nodes_dir.glob("*/"):
                    msg_file = node_dir / "messages.txt"
                    if msg_file.exists():
                        files_to_search.append(msg_file)
                # Search channel directories
                for channel_dir in self.channels_dir.glob("*/"):
                    msg_file = channel_dir / "messages.txt"
                    if msg_file.exists():
                        files_to_search.append(msg_file)

            for messages_file in files_to_search:
                if not messages_file.exists():
                    continue

                # Extract conversation_id from parent directory name
                # For nodes: data/nodes/{prefix}/messages.txt -> use prefix
                # For channels: data/channels/{number}/messages.txt -> use number
                file_conv_id = messages_file.parent.name

                with open(messages_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        # Parse line: timestamp|message_type|role|content|sender
                        parts = line.split("|")
                        if len(parts) >= 4:
                            timestamp_str = parts[0]
                            _ = parts[
                                1
                            ]  # message_type (not used here, but part of format)
                            role = parts[2]
                            content = (
                                "|".join(parts[3:-1]) if len(parts) > 4 else parts[3]
                            )
                            content = content.replace("\\|", "|")
                            sender = parts[-1] if len(parts) > 4 else None

                            timestamp_val = float(timestamp_str)

                            # Apply filters
                            if since and timestamp_val < since:
                                continue
                            if keyword and keyword.lower() not in content.lower():
                                continue

                            messages.append(
                                {
                                    "conversation_id": file_conv_id,
                                    "role": role,
                                    "content": content,
                                    "timestamp": timestamp_val,
                                    "sender": sender,
                                }
                            )

            # Sort by timestamp (most recent first) and limit
            messages.sort(key=lambda x: cast(float, x["timestamp"]), reverse=True)
            return messages[:limit]

        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []

    async def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get statistics for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Dict with total_messages, first_seen, last_seen
        """
        try:
            # Determine if it's a channel or node
            if self._is_channel_id(conversation_id):
                messages_file = self._get_channel_dir(conversation_id) / "messages.txt"
            else:
                messages_file = self._get_user_messages_file(conversation_id)

            if not messages_file.exists():
                return {
                    "total_messages": 0,
                    "first_seen": None,
                    "last_seen": None,
                }

            total = 0
            first_seen = None
            last_seen = None

            with open(messages_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    total += 1
                    # Extract timestamp
                    parts = line.split("|")
                    if len(parts) >= 1:
                        timestamp = float(parts[0])
                        if first_seen is None or timestamp < first_seen:
                            first_seen = timestamp
                        if last_seen is None or timestamp > last_seen:
                            last_seen = timestamp

            return {
                "total_messages": total,
                "first_seen": first_seen,
                "last_seen": last_seen,
            }

        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {"total_messages": 0, "first_seen": None, "last_seen": None}

    async def get_all_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        try:
            # Count all message files from nodes and channels
            message_files = []
            for node_dir in self.nodes_dir.glob("*/"):
                msg_file = node_dir / "messages.txt"
                if msg_file.exists():
                    message_files.append(msg_file)
            for channel_dir in self.channels_dir.glob("*/"):
                msg_file = channel_dir / "messages.txt"
                if msg_file.exists():
                    message_files.append(msg_file)

            total_conversations = len(message_files)

            total_messages = 0
            channel_messages = 0
            dm_messages = 0

            for messages_file in message_files:
                with open(messages_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        total_messages += 1
                        # Parse message type
                        parts = line.split("|")
                        if len(parts) >= 2:
                            message_type = parts[1]
                            if message_type == "channel":
                                channel_messages += 1
                            elif message_type == "direct":
                                dm_messages += 1

            return {
                "total_messages": total_messages,
                "total_conversations": total_conversations,
                "channel_messages": channel_messages,
                "dm_messages": dm_messages,
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_messages": 0,
                "total_conversations": 0,
                "channel_messages": 0,
                "dm_messages": 0,
            }
