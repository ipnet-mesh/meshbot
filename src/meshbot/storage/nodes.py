"""Node registry and name mapping storage."""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseStorage

logger = logging.getLogger(__name__)


class NodeStorage(BaseStorage):
    """Handles node registry and name mapping operations."""

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

            # Update name, timestamp, and pubkey
            memory["pubkey"] = pubkey  # Store full public key
            memory["name"] = name
            memory["name_timestamp"] = timestamp

            # Save memory
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)

            logger.debug(f"Updated node name: {pubkey[:8]}... -> {name}")
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
            memory["pubkey"] = pubkey  # Store full public key
            memory["last_seen"] = timestamp
            memory["is_online"] = is_online
            if name:
                memory["name"] = name

            # Save memory
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)

            logger.debug(f"Upserted node: {pubkey[:8]}...")

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

            # Update advert count, timestamp, and pubkey
            memory["pubkey"] = pubkey  # Store full public key
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
                "pubkey": memory.get(
                    "pubkey", pubkey
                ),  # Use stored pubkey, fallback to parameter
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
                            "pubkey": memory.get(
                                "pubkey", pubkey_prefix
                            ),  # Use stored full pubkey, fallback to prefix
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
