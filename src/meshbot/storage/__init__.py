"""Storage package for MeshBot - file-based storage for messages, nodes, and adverts."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .adverts import AdvertStorage
from .messages import MessageStorage


class MeshBotStorage:
    """
    Unified storage interface combining message and advert storage.

    This facade class provides backward compatibility while delegating
    to specialized storage modules under the hood.
    """

    def __init__(self, data_path: Path):
        """
        Initialize storage with data directory.

        Args:
            data_path: Path to data directory
        """
        self.data_path = data_path

        # Initialize specialized storage components
        self._message_storage = MessageStorage(data_path)
        self._advert_storage = AdvertStorage(data_path)

    async def initialize(self) -> None:
        """Initialize storage (create data directory if needed)."""
        await self._message_storage.initialize()
        await self._advert_storage.initialize()

    async def close(self) -> None:
        """Close storage (no-op for file-based storage)."""
        await self._message_storage.close()
        await self._advert_storage.close()

    # ========== Message Operations (delegate to MessageStorage) ==========

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "direct",
        timestamp: Optional[float] = None,
        sender: Optional[str] = None,
    ) -> None:
        """Add a message to the conversation's message file."""
        return await self._message_storage.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_type=message_type,
            timestamp=timestamp,
            sender=sender,
        )

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages from a conversation."""
        return await self._message_storage.get_conversation_messages(
            conversation_id=conversation_id, limit=limit, offset=offset
        )

    async def search_messages(
        self,
        conversation_id: Optional[str] = None,
        keyword: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search messages with filters."""
        return await self._message_storage.search_messages(
            conversation_id=conversation_id, keyword=keyword, since=since, limit=limit
        )

    async def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation."""
        return await self._message_storage.get_conversation_stats(conversation_id)

    async def get_all_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        return await self._message_storage.get_all_statistics()

    # ========== Node Operations (delegate to AdvertStorage -> NodeStorage) ==========

    async def update_node_name(
        self, pubkey: str, name: str, timestamp: Optional[float] = None
    ) -> None:
        """Update or add a node name mapping."""
        return await self._advert_storage.update_node_name(
            pubkey=pubkey, name=name, timestamp=timestamp
        )

    async def get_node_name(self, pubkey: str) -> Optional[str]:
        """Get friendly name for a node."""
        return await self._advert_storage.get_node_name(pubkey)

    async def get_all_node_names(self) -> List[Tuple[str, str]]:
        """Get all node name mappings."""
        return await self._advert_storage.get_all_node_names()

    async def upsert_node(
        self,
        pubkey: str,
        name: Optional[str] = None,
        is_online: bool = False,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add or update a node in the registry."""
        return await self._advert_storage.upsert_node(
            pubkey=pubkey, name=name, is_online=is_online, timestamp=timestamp
        )

    async def update_node_advert_count(
        self, pubkey: str, timestamp: Optional[float] = None
    ) -> None:
        """Increment advert count and update last_advert timestamp for a node."""
        return await self._advert_storage.update_node_advert_count(
            pubkey=pubkey, timestamp=timestamp
        )

    async def get_node(self, pubkey: str) -> Optional[Dict[str, Any]]:
        """Get node information."""
        return await self._advert_storage.get_node(pubkey)

    async def list_nodes(
        self,
        online_only: bool = False,
        has_name: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List nodes with filters."""
        return await self._advert_storage.list_nodes(
            online_only=online_only, has_name=has_name, limit=limit
        )

    # ========== Advert Operations (delegate to AdvertStorage) ==========

    async def add_advert(
        self,
        node_id: str,
        node_name: Optional[str] = None,
        signal_strength: Optional[int] = None,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add an advertisement event to adverts.csv."""
        return await self._advert_storage.add_advert(
            node_id=node_id,
            node_name=node_name,
            signal_strength=signal_strength,
            details=details,
            timestamp=timestamp,
        )

    async def search_adverts(
        self,
        node_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search advertisements with filters."""
        return await self._advert_storage.search_adverts(
            node_id=node_id, since=since, limit=limit
        )

    async def get_recent_adverts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent advertisements."""
        return await self._advert_storage.get_recent_adverts(limit=limit)

    # ========== Network Event Operations (delegate to AdvertStorage) ==========

    async def add_network_event(
        self,
        event_type: str,
        node_id: Optional[str] = None,
        node_name: Optional[str] = None,
        details: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add a network event."""
        return await self._advert_storage.add_network_event(
            event_type=event_type,
            node_id=node_id,
            node_name=node_name,
            details=details,
            timestamp=timestamp,
        )

    async def get_recent_network_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent network events."""
        return await self._advert_storage.get_recent_network_events(limit=limit)

    async def search_network_events(
        self,
        event_type: Optional[str] = None,
        node_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search network events with filters."""
        return await self._advert_storage.search_network_events(
            event_type=event_type, node_id=node_id, since=since, limit=limit
        )


__all__ = ["MeshBotStorage"]
