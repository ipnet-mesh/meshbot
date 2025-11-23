"""Advertisement and network event storage."""

import csv
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .nodes import NodeStorage

logger = logging.getLogger(__name__)


class AdvertStorage(NodeStorage):
    """Handles advertisement and network event storage operations."""

    def __init__(self, data_path: Path):
        """
        Initialize advert storage.

        Args:
            data_path: Path to data directory
        """
        super().__init__(data_path)

        # File paths
        self.adverts_file = self.data_path / "adverts.csv"

        # Initialize CSV files with headers if they don't exist
        if not self.adverts_file.exists():
            with open(self.adverts_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["timestamp", "node_id", "node_name", "signal_strength", "details"]
                )

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

            logger.debug(f"Added advert from {node_id[:8]}...")

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
                            "signal_strength": (
                                int(signal_strength) if signal_strength else None
                            ),
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

    # ========== Network Events ==========

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
