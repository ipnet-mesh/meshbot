"""Node and conversation tools for MeshBot."""

import logging
from typing import Any, Optional

from pydantic_ai import RunContext

from .logging_wrapper import create_logging_tool_decorator

logger = logging.getLogger(__name__)


def register_node_tools(agent: Any) -> None:
    """Register node-related tools (conversations, queries, and node information).

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    # Create logging tool decorator
    tool = create_logging_tool_decorator(agent)

    # ========== Conversation Tools ==========

    @tool()
    async def get_channel_messages(
        ctx: RunContext[Any], channel: str = "0", limit: int = 5
    ) -> str:
        """Get recent messages from a channel.

        Args:
            channel: Channel number (default: "0" for main channel)
            limit: Number of recent messages to retrieve (default: 5)

        Returns:
            Recent channel messages in time order
        """
        try:
            # Get messages from channel
            messages = await ctx.deps.memory.storage.get_conversation_messages(
                conversation_id=channel, limit=limit
            )
            if not messages:
                return f"No messages in channel {channel}."

            response = f"Last {len(messages)} message(s) in channel {channel}:\n"
            for msg in messages:
                role = "User" if msg["role"] == "user" else "Bot"
                response += f"{role}: {msg['content']}\n"

            return response.strip()
        except Exception as e:
            logger.error(f"Error getting channel messages: {e}")
            return f"Error retrieving messages from channel {channel}."

    @tool()
    async def get_user_messages(
        ctx: RunContext[Any], user_id: str, limit: int = 5
    ) -> str:
        """Get recent private messages with a specific user.

        Args:
            user_id: User's public key (full or first 8-16 characters)
            limit: Number of recent messages to retrieve (default: 5)

        Returns:
            Recent private messages with the user in time order
        """
        try:
            messages = await ctx.deps.memory.storage.get_conversation_messages(
                conversation_id=user_id, limit=limit
            )
            if not messages:
                return f"No conversation history with user {user_id[:16]}..."

            response = f"Last {len(messages)} message(s) with {user_id[:16]}:\n"
            for msg in messages:
                role = "User" if msg["role"] == "user" else "Bot"
                response += f"{role}: {msg['content']}\n"

            return response.strip()
        except Exception as e:
            logger.error(f"Error getting user messages: {e}")
            return f"Error retrieving messages with user {user_id[:16]}..."

    # ========== Query Tools ==========

    @tool()
    async def list_adverts(
        ctx: RunContext[Any],
        node_id: Optional[str] = None,
        hours_ago: Optional[int] = None,
        limit: int = 20,
    ) -> str:
        """List advertisement history with filters.

        Advertisements are announcements from mesh nodes advertising their presence.
        This tool searches the historical log of all advertisements received.

        Args:
            node_id: Filter by node ID (partial match supported, e.g., first 8 chars)
            hours_ago: Only show adverts from last N hours
            limit: Maximum number of results (default 20, max 50)

        Returns:
            Formatted list of matching advertisements
        """
        try:
            import time

            # Calculate timestamp filter if hours_ago is specified
            since = None
            if hours_ago is not None:
                since = time.time() - (hours_ago * 3600)

            # Limit to max 50 results
            limit = min(limit, 50)

            # Query storage
            adverts = await ctx.deps.memory.storage.search_adverts(
                node_id=node_id,
                since=since,
                limit=limit,
            )

            if not adverts:
                filters = []
                if node_id:
                    filters.append(f"node={node_id}")
                if hours_ago:
                    filters.append(f"last {hours_ago}h")
                filter_str = " with " + ", ".join(filters) if filters else ""
                return f"No advertisements found{filter_str}"

            # Format results
            from datetime import datetime

            result = f"Found {len(adverts)} advertisement(s):\n"
            for advert in adverts:
                timestamp = datetime.fromtimestamp(advert["timestamp"])
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                node_display = (
                    advert["node_id"][:16] if advert["node_id"] else "unknown"
                )
                name = f" ({advert['node_name']})" if advert["node_name"] else ""
                result += f"[{time_str}] {node_display}{name}\n"

            return result.strip()

        except Exception as e:
            logger.error(f"Error searching adverts: {e}")
            return "Error searching advertisements"

    @tool()
    async def get_node_info(ctx: RunContext[Any], node_id: str) -> str:
        """Get detailed information about a specific mesh node.

        Args:
            node_id: Node public key (can be partial, e.g., first 8-16 characters)

        Returns:
            Node information including name, status, activity times, and statistics
        """
        try:
            # Try exact match first
            node = await ctx.deps.memory.storage.get_node(node_id)

            # If not found, try to find by partial match
            if not node:
                all_nodes = await ctx.deps.memory.storage.list_nodes(limit=100)
                for n in all_nodes:
                    if n["pubkey"].startswith(node_id):
                        node = n
                        break

            if not node:
                return f"Node not found: {node_id}"

            # Format node information
            from datetime import datetime

            result = f"Node: {node['pubkey'][:16]}...\n"
            if node["name"]:
                result += f"Name: {node['name']}\n"
            result += f"Status: {'Online' if node['is_online'] else 'Offline'}\n"

            first_seen = datetime.fromtimestamp(node["first_seen"])
            last_seen = datetime.fromtimestamp(node["last_seen"])
            result += f"First seen: {first_seen.strftime('%Y-%m-%d %H:%M')}\n"
            result += f"Last seen: {last_seen.strftime('%Y-%m-%d %H:%M')}\n"

            if node["last_advert"]:
                last_advert = datetime.fromtimestamp(node["last_advert"])
                result += f"Last advert: {last_advert.strftime('%Y-%m-%d %H:%M')}\n"

            result += f"Total adverts: {node['total_adverts']}"

            return result

        except Exception as e:
            logger.error(f"Error getting node info: {e}")
            return "Error retrieving node information"

    @tool()
    async def list_nodes(
        ctx: RunContext[Any],
        online_only: bool = False,
        has_name: bool = False,
        limit: int = 20,
    ) -> str:
        """List known mesh nodes with optional filters.

        Args:
            online_only: Only show nodes currently online (default: False)
            has_name: Only show nodes with friendly names (default: False)
            limit: Maximum number of nodes to return (default 20, max 50)

        Returns:
            Formatted list of nodes
        """
        try:
            # Limit to max 50 results
            limit = min(limit, 50)

            # Query storage
            nodes = await ctx.deps.memory.storage.list_nodes(
                online_only=online_only,
                has_name=has_name,
                limit=limit,
            )

            if not nodes:
                filters = []
                if online_only:
                    filters.append("online")
                if has_name:
                    filters.append("named")
                filter_str = " (" + ", ".join(filters) + ")" if filters else ""
                return f"No nodes found{filter_str}"

            # Format results
            from datetime import datetime

            result = f"Found {len(nodes)} node(s):\n"
            for node in nodes:
                status = "🟢" if node["is_online"] else "🔴"
                node_id = node["pubkey"][:16]
                name = f" ({node['name']})" if node["name"] else ""
                last_seen = datetime.fromtimestamp(node["last_seen"])
                time_str = last_seen.strftime("%Y-%m-%d %H:%M")
                adverts = (
                    f", {node['total_adverts']} adverts"
                    if node["total_adverts"] > 0
                    else ""
                )
                result += f"{status} {node_id}{name} - last seen {time_str}{adverts}\n"

            return result.strip()

        except Exception as e:
            logger.error(f"Error listing nodes: {e}")
            return "Error listing nodes"
