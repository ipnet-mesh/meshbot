"""SQLite storage layer for MeshBot data."""

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MeshBotStorage:
    """SQLite storage for messages, network events, and node names."""

    def __init__(self, db_path: Path):
        """
        Initialize storage with SQLite database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            # SQLite doesn't support async natively, but we can use run_in_executor
            # For simplicity, we'll use sync operations since SQLite is fast
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row  # Enable column access by name

            # Create tables
            self._create_tables()

            logger.info(f"Storage initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing storage: {e}")
            raise

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Messages table
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

        # Network events table
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

        # Node names table
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
        if self.conn:
            self.conn.close()
            self.conn = None

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
