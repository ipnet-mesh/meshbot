"""SQLite storage layer for MeshBot data."""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MeshBotStorage:
    """SQLite storage for messages, adverts, nodes, and network events."""

    def __init__(self, db_path: Path):
        """
        Initialize storage with SQLite database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the database connection, ensuring it exists."""
        if self._conn is None:
            raise RuntimeError("Storage not initialized. Call initialize() first.")
        return self._conn

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            # SQLite doesn't support async natively, but we can use run_in_executor
            # For simplicity, we'll use sync operations since SQLite is fast
            # check_same_thread=False allows the connection to be used across threads
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row  # Enable column access by name

            # Create tables
            self._create_tables()

            logger.info(f"Storage initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing storage: {e}")
            raise

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Messages table - chat messages
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                conversation_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sender TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """
        )

        # Index for fast conversation lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, timestamp)
        """
        )

        # Index for search
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_content
            ON messages(content)
        """
        )

        # Nodes table - central node registry
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                pubkey TEXT PRIMARY KEY,
                name TEXT,
                is_online INTEGER DEFAULT 0,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                last_advert REAL,
                total_adverts INTEGER DEFAULT 0,
                updated_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nodes_online
            ON nodes(is_online, last_seen)
        """
        )

        # Adverts table - advertisement events
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS adverts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                node_id TEXT NOT NULL,
                node_name TEXT,
                signal_strength INTEGER,
                details TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (node_id) REFERENCES nodes(pubkey)
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_adverts_node_time
            ON adverts(node_id, timestamp)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_adverts_time
            ON adverts(timestamp)
        """
        )

        # Network events table - other network events (non-adverts)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                node_id TEXT,
                node_name TEXT,
                details TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """
        )

        # Index for event type and time-based queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_type_time
            ON network_events(event_type, timestamp)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_node
            ON network_events(node_id, timestamp)
        """
        )

        # Legacy node_names table - keep for backward compatibility
        # New code should use 'nodes' table instead
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS node_names (
                pubkey TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                timestamp REAL NOT NULL,
                updated_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """
        )

        self.conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

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
        Add a message to the database.

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
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (timestamp, conversation_id, message_type, role, content, sender)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, conversation_id, message_type, role, content, sender),
            )
            self.conn.commit()
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
            cursor = self.conn.cursor()

            query = """
                SELECT role, content, timestamp, sender
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """

            params: List[Any] = [conversation_id]

            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            messages = []
            for row in rows:
                messages.append(
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "sender": row["sender"],
                    }
                )

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
            cursor = self.conn.cursor()

            query = "SELECT conversation_id, role, content, timestamp, sender FROM messages WHERE 1=1"
            params: List[Any] = []

            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)

            if keyword:
                query += " AND LOWER(content) LIKE ?"
                params.append(f"%{keyword.lower()}%")

            if since:
                query += " AND timestamp >= ?"
                params.append(since)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            messages = []
            for row in rows:
                messages.append(
                    {
                        "conversation_id": row["conversation_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "sender": row["sender"],
                    }
                )

            return messages

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
            cursor = self.conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM messages
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            )

            row = cursor.fetchone()

            return {
                "total_messages": row["total"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }

        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {"total_messages": 0, "first_seen": None, "last_seen": None}

    async def get_all_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        try:
            cursor = self.conn.cursor()

            # Total messages
            cursor.execute("SELECT COUNT(*) as total FROM messages")
            total_messages = cursor.fetchone()["total"]

            # Total conversations
            cursor.execute(
                "SELECT COUNT(DISTINCT conversation_id) as total FROM messages"
            )
            total_conversations = cursor.fetchone()["total"]

            # Channel vs DM messages
            cursor.execute(
                "SELECT COUNT(*) as total FROM messages WHERE message_type = 'channel'"
            )
            channel_messages = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) as total FROM messages WHERE message_type = 'direct'"
            )
            dm_messages = cursor.fetchone()["total"]

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
        Add a network event.

        Args:
            event_type: Type of event (ADVERT, NEW_CONTACT, etc.)
            node_id: Node public key (optional)
            node_name: Node friendly name (optional)
            details: Additional event details (optional)
            timestamp: Event timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO network_events (timestamp, event_type, node_id, node_name, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, event_type, node_id, node_name, details),
            )
            self.conn.commit()
            logger.debug(f"Added network event: {event_type}")
        except Exception as e:
            logger.error(f"Error adding network event: {e}")
            raise

    async def get_recent_network_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent network events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dicts with timestamp, event_type, node_id, node_name, details
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, event_type, node_id, node_name, details
                FROM network_events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )

            rows = cursor.fetchall()
            events = []
            for row in rows:
                events.append(
                    {
                        "timestamp": row["timestamp"],
                        "event_type": row["event_type"],
                        "node_id": row["node_id"],
                        "node_name": row["node_name"],
                        "details": row["details"],
                    }
                )

            return events

        except Exception as e:
            logger.error(f"Error getting recent network events: {e}")
            return []

    async def search_network_events(
        self,
        event_type: Optional[str] = None,
        node_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search network events with filters.

        Args:
            event_type: Filter by event type (optional)
            node_id: Filter by node ID (optional)
            since: Only events after this timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of event dicts
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT timestamp, event_type, node_id, node_name, details FROM network_events WHERE 1=1"
            params: List[Any] = []

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.upper())

            if node_id:
                query += " AND node_id LIKE ?"
                params.append(f"%{node_id}%")

            if since:
                query += " AND timestamp >= ?"
                params.append(since)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            events = []
            for row in rows:
                events.append(
                    {
                        "timestamp": row["timestamp"],
                        "event_type": row["event_type"],
                        "node_id": row["node_id"],
                        "node_name": row["node_name"],
                        "details": row["details"],
                    }
                )

            return events

        except Exception as e:
            logger.error(f"Error searching network events: {e}")
            return []

    # ========== Node Names ==========

    async def update_node_name(
        self, pubkey: str, name: str, timestamp: Optional[float] = None
    ) -> None:
        """
        Update or add a node name mapping.

        Args:
            pubkey: Node public key
            name: Friendly name
            timestamp: Mapping timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO node_names (pubkey, name, timestamp)
                VALUES (?, ?, ?)
                """,
                (pubkey, name, timestamp),
            )
            self.conn.commit()
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
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT name FROM node_names WHERE pubkey = ?",
                (pubkey,),
            )
            row = cursor.fetchone()
            return row["name"] if row else None

        except Exception as e:
            logger.error(f"Error getting node name: {e}")
            return None

    async def get_all_node_names(self) -> List[Tuple[str, str]]:
        """
        Get all node name mappings.

        Returns:
            List of (pubkey, name) tuples ordered by most recent
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT pubkey, name
                FROM node_names
                ORDER BY timestamp DESC
                """
            )
            rows = cursor.fetchall()
            return [(row["pubkey"], row["name"]) for row in rows]

        except Exception as e:
            logger.error(f"Error getting all node names: {e}")
            return []

    # ========== Nodes ==========

    async def upsert_node(
        self,
        pubkey: str,
        name: Optional[str] = None,
        is_online: bool = False,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Add or update a node in the registry.

        Args:
            pubkey: Node public key
            name: Friendly name (optional)
            is_online: Online status
            timestamp: Timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        try:
            cursor = self.conn.cursor()

            # Check if node exists
            cursor.execute("SELECT pubkey FROM nodes WHERE pubkey = ?", (pubkey,))
            exists = cursor.fetchone() is not None

            if exists:
                # Update existing node
                update_fields = ["last_seen = ?", "is_online = ?"]
                params: list[Any] = [timestamp, 1 if is_online else 0]

                if name:
                    update_fields.append("name = ?")
                    params.append(name)

                query = f"UPDATE nodes SET {', '.join(update_fields)} WHERE pubkey = ?"
                params.append(pubkey)
                cursor.execute(query, params)
            else:
                # Insert new node
                cursor.execute(
                    """
                    INSERT INTO nodes (pubkey, name, is_online, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pubkey, name, 1 if is_online else 0, timestamp, timestamp),
                )

            self.conn.commit()
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
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE nodes
                SET total_adverts = total_adverts + 1,
                    last_advert = ?,
                    last_seen = ?
                WHERE pubkey = ?
                """,
                (timestamp, timestamp, pubkey),
            )
            self.conn.commit()

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
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT pubkey, name, is_online, first_seen, last_seen,
                       last_advert, total_adverts
                FROM nodes
                WHERE pubkey = ?
                """,
                (pubkey,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "pubkey": row["pubkey"],
                "name": row["name"],
                "is_online": bool(row["is_online"]),
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
                "last_advert": row["last_advert"],
                "total_adverts": row["total_adverts"],
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
            cursor = self.conn.cursor()

            query = """
                SELECT pubkey, name, is_online, first_seen, last_seen,
                       last_advert, total_adverts
                FROM nodes
                WHERE 1=1
            """
            params: List[Any] = []

            if online_only:
                query += " AND is_online = 1"

            if has_name:
                query += " AND name IS NOT NULL"

            query += " ORDER BY last_seen DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            nodes = []
            for row in rows:
                nodes.append(
                    {
                        "pubkey": row["pubkey"],
                        "name": row["name"],
                        "is_online": bool(row["is_online"]),
                        "first_seen": row["first_seen"],
                        "last_seen": row["last_seen"],
                        "last_advert": row["last_advert"],
                        "total_adverts": row["total_adverts"],
                    }
                )

            return nodes

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
        Add an advertisement event.

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
            cursor = self.conn.cursor()

            # Add advert record
            cursor.execute(
                """
                INSERT INTO adverts (timestamp, node_id, node_name, signal_strength, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, node_id, node_name, signal_strength, details),
            )

            # Update node registry (upsert)
            await self.upsert_node(
                node_id, name=node_name, is_online=True, timestamp=timestamp
            )
            await self.update_node_advert_count(node_id, timestamp)

            self.conn.commit()
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

        Args:
            node_id: Filter by node ID (optional, supports partial match)
            since: Only adverts after this timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of advert dicts
        """
        try:
            cursor = self.conn.cursor()

            query = "SELECT timestamp, node_id, node_name, signal_strength, details FROM adverts WHERE 1=1"
            params: List[Any] = []

            if node_id:
                query += " AND node_id LIKE ?"
                params.append(f"%{node_id}%")

            if since:
                query += " AND timestamp >= ?"
                params.append(since)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            adverts = []
            for row in rows:
                adverts.append(
                    {
                        "timestamp": row["timestamp"],
                        "node_id": row["node_id"],
                        "node_name": row["node_name"],
                        "signal_strength": row["signal_strength"],
                        "details": row["details"],
                    }
                )

            return adverts

        except Exception as e:
            logger.error(f"Error searching adverts: {e}")
            return []

    async def get_recent_adverts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent advertisements.

        Args:
            limit: Maximum number of adverts to return

        Returns:
            List of advert dicts
        """
        return await self.search_adverts(limit=limit)
