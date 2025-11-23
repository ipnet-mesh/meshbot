"""File-based storage layer for MeshBot data."""

import csv
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

logger = logging.getLogger(__name__)


class MeshBotStorage:
    """File-based storage for messages, adverts, nodes, and network events."""

    def __init__(self, data_path: Path):
        """
        Initialize storage with data directory.

        Args:
            data_path: Path to data directory
        """
        self.data_path = data_path
        self.data_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.nodes_dir = self.data_path / "nodes"
        self.channels_dir = self.data_path / "channels"
        self.nodes_dir.mkdir(exist_ok=True)
        self.channels_dir.mkdir(exist_ok=True)

        # File paths
        self.adverts_file = self.data_path / "adverts.csv"

        # Initialize CSV files with headers if they don't exist
        if not self.adverts_file.exists():
            with open(self.adverts_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["timestamp", "node_id", "node_name", "signal_strength", "details"]
                )

    async def initialize(self) -> None:
        """Initialize storage (create data directory if needed)."""
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage initialized: {self.data_path}")
        except Exception as e:
            logger.error(f"Error initializing storage: {e}")
            raise

    async def close(self) -> None:
        """Close storage (no-op for file-based storage)."""
        pass

    # ========== Helper Methods ==========

    def _is_channel_id(self, conversation_id: str) -> bool:
        """
        Determine if conversation_id is a channel number.
        Channels are numeric strings (0, 1, 2, etc.)
        """
        return conversation_id.isdigit()

    def _get_node_prefix(self, pubkey: str) -> str:
        """Get the first 16 characters of a public key for directory naming."""
        # Sanitize pubkey (remove non-alphanumeric) and take first 16 chars
        safe_key = "".join(c for c in pubkey if c.isalnum())
        return safe_key[:16]

    def _get_node_dir(self, pubkey: str) -> Path:
        """Get the directory path for a node."""
        prefix = self._get_node_prefix(pubkey)
        node_dir = self.nodes_dir / prefix
        node_dir.mkdir(parents=True, exist_ok=True)
        return node_dir

    def _get_channel_dir(self, channel_number: str) -> Path:
        """Get the directory path for a channel."""
        channel_dir = self.channels_dir / channel_number
        channel_dir.mkdir(parents=True, exist_ok=True)
        return channel_dir

    def _get_messages_file(self, conversation_id: str, message_type: str = "direct") -> Path:
        """
        Get the messages file path for a conversation.

        Args:
            conversation_id: Channel number or node pubkey
            message_type: "direct", "channel", or "broadcast"

        Returns:
            Path to messages.txt file
        """
        if message_type == "channel" or self._is_channel_id(conversation_id):
            # Channel: data/channels/{number}/messages.txt
            return self._get_channel_dir(conversation_id) / "messages.txt"
        else:
            # Node: data/nodes/{pubkey_prefix}/messages.txt
            return self._get_node_dir(conversation_id) / "messages.txt"

    def _get_user_messages_file(self, user_id: str) -> Path:
        """Get the messages file path for a user (node)."""
        return self._get_node_dir(user_id) / "messages.txt"

    def _get_user_memory_file(self, user_id: str) -> Path:
        """Get the memory file path for a user (node)."""
        return self._get_node_dir(user_id) / "node.json"

    # ========== Messages ==========

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
                f.write(
                    f"{timestamp}|{message_type}|{role}|{escaped_content}|{sender_str}\n"
                )

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
                    files_to_search = [self._get_channel_dir(conversation_id) / "messages.txt"]
                else:
                    files_to_search = [self._get_node_dir(conversation_id) / "messages.txt"]
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

    # ========== Network Events (Adverts only for now) ==========

    async def add_network_event(
        self,
        event_type: str,
        node_id: Optional[str] = None,
        node_name: Optional[str] = None,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Add a network event (currently only adverts are stored).

        Args:
            event_type: Type of event (ADVERT, etc.)
            node_id: Node public key (optional)
            node_name: Node friendly name (optional)
            details: Additional event details (optional)
            timestamp: Event timestamp (defaults to current time)
        """
        # For now, we only store adverts in adverts.csv
        # Other network events are logged but not persisted
        if event_type.upper() == "ADVERTISEMENT":
            await self.add_advert(
                node_id=node_id or "",
                node_name=node_name,
                signal_strength=None,
                details=details,
                timestamp=timestamp,
            )
        else:
            logger.debug(f"Network event {event_type} logged but not persisted")

    async def get_recent_network_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent network events (adverts only).

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dicts with timestamp, event_type, node_id, node_name, details
        """
        # Return recent adverts as network events
        adverts = await self.get_recent_adverts(limit=limit)
        return [
            {
                "timestamp": advert["timestamp"],
                "event_type": "ADVERTISEMENT",
                "node_id": advert["node_id"],
                "node_name": advert["node_name"],
                "details": advert["details"],
            }
            for advert in adverts
        ]

    async def search_network_events(
        self,
        event_type: Optional[str] = None,
        node_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search network events with filters (adverts only).

        Args:
            event_type: Filter by event type (optional)
            node_id: Filter by node ID (optional)
            since: Only events after this timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of event dicts
        """
        # Only search adverts for now
        if event_type and event_type.upper() != "ADVERTISEMENT":
            return []

        adverts = await self.search_adverts(node_id=node_id, since=since, limit=limit)
        return [
            {
                "timestamp": advert["timestamp"],
                "event_type": "ADVERTISEMENT",
                "node_id": advert["node_id"],
                "node_name": advert["node_name"],
                "details": advert["details"],
            }
            for advert in adverts
        ]

    # ========== Node Names (Legacy Support) ==========

    async def update_node_name(
        self, pubkey: str, name: str, timestamp: Optional[float] = None
    ) -> None:
        """
        Update or add a node name mapping.
        Stored in user memory file for now.

        Args:
            pubkey: Node public key
            name: Friendly name
            timestamp: Mapping timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            memory_file = self._get_user_memory_file(pubkey)

            # Load existing memory or create new
            if memory_file.exists():
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            else:
                memory = {}

            # Update name and timestamp
            memory["name"] = name
            memory["name_timestamp"] = timestamp

            # Save memory
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)

            logger.debug(f"Updated node name: {pubkey[:16]}... -> {name}")
        except Exception as e:
            logger.error(f"Error updating node name: {e}")
            raise

    async def get_node_name(self, pubkey: str) -> Optional[str]:
        """
        Get friendly name for a node.

        Args:
            pubkey: Node public key

        Returns:
            Friendly name if found, None otherwise
        """
        try:
            memory_file = self._get_user_memory_file(pubkey)

            if not memory_file.exists():
                return None

            with open(memory_file, "r", encoding="utf-8") as f:
                memory = json.load(f)

            name = memory.get("name")
            return str(name) if name is not None else None

        except Exception as e:
            logger.error(f"Error getting node name: {e}")
            return None

    async def get_all_node_names(self) -> List[Tuple[str, str]]:
        """
        Get all node name mappings.

        Returns:
            List of (pubkey_prefix, name) tuples ordered by most recent
        """
        try:
            node_names = []

            # Search all node directories
            for node_dir in self.nodes_dir.glob("*/"):
                memory_file = node_dir / "node.json"
                if not memory_file.exists():
                    continue

                try:
                    with open(memory_file, "r", encoding="utf-8") as f:
                        memory = json.load(f)

                    if "name" in memory:
                        pubkey_prefix = node_dir.name
                        name = memory["name"]
                        timestamp = memory.get("name_timestamp", 0)
                        node_names.append((pubkey_prefix, name, timestamp))
                except Exception:
                    continue

            # Sort by timestamp (most recent first)
            node_names.sort(key=lambda x: x[2], reverse=True)

            return [(pubkey, name) for pubkey, name, _ in node_names]

        except Exception as e:
            logger.error(f"Error getting all node names: {e}")
            return []

    # ========== Nodes (Simplified) ==========

    async def upsert_node(
        self,
        pubkey: str,
        name: Optional[str] = None,
        is_online: bool = False,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Add or update a node in the registry.
        Stores basic info in memory file.

        Args:
            pubkey: Node public key
            name: Friendly name (optional)
            is_online: Online status
            timestamp: Timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            memory_file = self._get_user_memory_file(pubkey)

            # Load existing memory or create new
            if memory_file.exists():
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            else:
                memory = {"first_seen": timestamp}

            # Update fields
            memory["last_seen"] = timestamp
            memory["is_online"] = is_online
            if name:
                memory["name"] = name

            # Save memory
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)

            logger.debug(f"Upserted node: {pubkey[:16]}...")

        except Exception as e:
            logger.error(f"Error upserting node: {e}")
            raise

    async def update_node_advert_count(
        self, pubkey: str, timestamp: Optional[float] = None
    ) -> None:
        """
        Increment advert count and update last_advert timestamp for a node.

        Args:
            pubkey: Node public key
            timestamp: Advertisement timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            memory_file = self._get_user_memory_file(pubkey)

            # Load existing memory or create new
            if memory_file.exists():
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            else:
                memory = {"first_seen": timestamp, "total_adverts": 0}

            # Update advert count and timestamp
            memory["total_adverts"] = memory.get("total_adverts", 0) + 1
            memory["last_advert"] = timestamp
            memory["last_seen"] = timestamp

            # Save memory
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating node advert count: {e}")
            raise

    async def get_node(self, pubkey: str) -> Optional[Dict[str, Any]]:
        """
        Get node information.

        Args:
            pubkey: Node public key

        Returns:
            Node dict or None if not found
        """
        try:
            memory_file = self._get_user_memory_file(pubkey)

            if not memory_file.exists():
                return None

            with open(memory_file, "r", encoding="utf-8") as f:
                memory = json.load(f)

            return {
                "pubkey": pubkey,
                "name": memory.get("name"),
                "is_online": memory.get("is_online", False),
                "first_seen": memory.get("first_seen"),
                "last_seen": memory.get("last_seen"),
                "last_advert": memory.get("last_advert"),
                "total_adverts": memory.get("total_adverts", 0),
            }

        except Exception as e:
            logger.error(f"Error getting node: {e}")
            return None

    async def list_nodes(
        self,
        online_only: bool = False,
        has_name: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List nodes with filters.

        Args:
            online_only: Only return online nodes
            has_name: Only return nodes with names
            limit: Maximum number of results

        Returns:
            List of node dicts
        """
        try:
            nodes = []

            # Search all node directories
            for node_dir in self.nodes_dir.glob("*/"):
                memory_file = node_dir / "node.json"
                if not memory_file.exists():
                    continue

                try:
                    with open(memory_file, "r", encoding="utf-8") as f:
                        memory = json.load(f)

                    pubkey_prefix = node_dir.name

                    # Apply filters
                    if online_only and not memory.get("is_online", False):
                        continue
                    if has_name and not memory.get("name"):
                        continue

                    nodes.append(
                        {
                            "pubkey": pubkey_prefix,
                            "name": memory.get("name"),
                            "is_online": memory.get("is_online", False),
                            "first_seen": memory.get("first_seen"),
                            "last_seen": memory.get("last_seen"),
                            "last_advert": memory.get("last_advert"),
                            "total_adverts": memory.get("total_adverts", 0),
                        }
                    )
                except Exception:
                    continue

            # Sort by last_seen (most recent first)
            nodes.sort(key=lambda x: x.get("last_seen", 0) or 0, reverse=True)

            return nodes[:limit]

        except Exception as e:
            logger.error(f"Error listing nodes: {e}")
            return []

    # ========== Adverts ==========

    async def add_advert(
        self,
        node_id: str,
        node_name: Optional[str] = None,
        signal_strength: Optional[int] = None,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Add an advertisement event to adverts.csv.

        Args:
            node_id: Node public key
            node_name: Node friendly name (optional)
            signal_strength: Signal strength (optional)
            details: Additional details (optional)
            timestamp: Event timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            # Append to CSV file
            with open(self.adverts_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        timestamp,
                        node_id,
                        node_name or "",
                        signal_strength or "",
                        details or "",
                    ]
                )

            # Update node registry
            await self.upsert_node(
                node_id, name=node_name, is_online=True, timestamp=timestamp
            )
            await self.update_node_advert_count(node_id, timestamp)

            logger.debug(f"Added advert from {node_id[:16]}...")

        except Exception as e:
            logger.error(f"Error adding advert: {e}")
            raise

    async def search_adverts(
        self,
        node_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search advertisements with filters.
        Efficiently reads only recent lines from the file.

        Args:
            node_id: Filter by node ID (optional, supports partial match)
            since: Only adverts after this timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of advert dicts
        """
        try:
            if not self.adverts_file.exists():
                return []

            adverts = []

            # Read file in reverse to get recent entries efficiently
            # Use deque with maxlen for efficient last-N-lines reading
            with open(self.adverts_file, "r", encoding="utf-8") as f:
                # Skip header
                next(f, None)

                # Read last N lines (limit * 2 to account for filtering)
                lines = deque(f, maxlen=limit * 2)

                reader = csv.reader(lines)
                for row in reader:
                    if len(row) < 5:
                        continue

                    timestamp_val = float(row[0])
                    advert_node_id = row[1]
                    advert_node_name = row[2]
                    signal_strength = row[3]
                    advert_details = row[4]

                    # Apply filters
                    if node_id and node_id not in advert_node_id:
                        continue
                    if since and timestamp_val < since:
                        continue

                    adverts.append(
                        {
                            "timestamp": timestamp_val,
                            "node_id": advert_node_id,
                            "node_name": advert_node_name or None,
                            "signal_strength": int(signal_strength)
                            if signal_strength
                            else None,
                            "details": advert_details or None,
                        }
                    )

            # Sort by timestamp (most recent first) and limit
            adverts.sort(key=lambda x: cast(float, x["timestamp"]), reverse=True)
            return adverts[:limit]

        except Exception as e:
            logger.error(f"Error searching adverts: {e}")
            return []

    async def get_recent_adverts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent advertisements (efficiently reads last few lines).

        Args:
            limit: Maximum number of adverts to return

        Returns:
            List of advert dicts
        """
        return await self.search_adverts(limit=limit)
