"""Base storage class with common functionality."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseStorage:
    """Base class for file-based storage with common helpers."""

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
        """Get the first 8 characters of a public key for directory naming."""
        # Sanitize pubkey (remove non-alphanumeric) and take first 8 chars
        safe_key = "".join(c for c in pubkey if c.isalnum())
        return safe_key[:8]

    def _get_node_dir_path(self, pubkey: str) -> Path:
        """Get the directory path for a node WITHOUT creating it."""
        prefix = self._get_node_prefix(pubkey)
        return self.nodes_dir / prefix

    def _get_node_dir(self, pubkey: str) -> Path:
        """Get the directory path for a node and create it if needed."""
        node_dir = self._get_node_dir_path(pubkey)
        node_dir.mkdir(parents=True, exist_ok=True)
        return node_dir

    def _get_channel_dir_path(self, channel_number: str) -> Path:
        """Get the directory path for a channel WITHOUT creating it."""
        return self.channels_dir / channel_number

    def _get_channel_dir(self, channel_number: str) -> Path:
        """Get the directory path for a channel and create it if needed."""
        channel_dir = self._get_channel_dir_path(channel_number)
        channel_dir.mkdir(parents=True, exist_ok=True)
        return channel_dir

    def _get_messages_file(
        self, conversation_id: str, message_type: str = "direct"
    ) -> Path:
        """
        Get the messages file path for a conversation and create directory if needed.

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

    def _get_messages_file_path(
        self, conversation_id: str, message_type: str = "direct"
    ) -> Path:
        """
        Get the messages file path for a conversation WITHOUT creating directory.

        Args:
            conversation_id: Channel number or node pubkey
            message_type: "direct", "channel", or "broadcast"

        Returns:
            Path to messages.txt file
        """
        if message_type == "channel" or self._is_channel_id(conversation_id):
            # Channel: data/channels/{number}/messages.txt
            return self._get_channel_dir_path(conversation_id) / "messages.txt"
        else:
            # Node: data/nodes/{pubkey_prefix}/messages.txt
            return self._get_node_dir_path(conversation_id) / "messages.txt"

    def _get_user_messages_file(self, user_id: str) -> Path:
        """Get the messages file path for a user (node) and create directory if needed."""
        return self._get_node_dir(user_id) / "messages.txt"

    def _get_user_messages_file_path(self, user_id: str) -> Path:
        """Get the messages file path for a user (node) WITHOUT creating directory."""
        return self._get_node_dir_path(user_id) / "messages.txt"

    def _get_user_memory_file(self, user_id: str) -> Path:
        """Get the memory file path for a user (node) and create directory if needed."""
        return self._get_node_dir(user_id) / "node.json"

    def _get_user_memory_file_path(self, user_id: str) -> Path:
        """Get the memory file path for a user (node) WITHOUT creating directory."""
        return self._get_node_dir_path(user_id) / "node.json"
