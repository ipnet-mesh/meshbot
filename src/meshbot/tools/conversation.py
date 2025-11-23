"""Conversation and user interaction tools."""

import logging
from typing import Any

from pydantic_ai import RunContext

from .logging_wrapper import create_logging_tool_decorator

logger = logging.getLogger(__name__)


def register_conversation_tools(agent: Any) -> None:
    """Register conversation-related tools.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    # Create logging tool decorator
    tool = create_logging_tool_decorator(agent)

    @tool()
    async def get_user_info(ctx: RunContext[Any], user_id: str) -> str:
        """Get information about a user."""
        try:
            memory = await ctx.deps.memory.get_user_memory(user_id)

            info = f"User: {memory.get('user_name') or user_id}\n"
            info += f"Total messages: {memory.get('total_messages', 0)}\n"
            info += f"First seen: {memory.get('first_seen', 'Never')}\n"
            info += f"Last seen: {memory.get('last_seen', 'Never')}\n"

            return info
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return "Error retrieving user information."

    @tool()
    async def status_request(ctx: RunContext[Any], destination: str) -> str:
        """Send a status request to a MeshCore node (similar to ping)."""
        try:
            # Use send_statusreq instead of ping (which doesn't exist)
            # This will request status from the destination node
            success = await ctx.deps.meshcore.ping_node(destination)
            result = (
                f"Status request to {destination}: {'Success' if success else 'Failed'}"
            )
            return result
        except Exception as e:
            logger.error(f"Error sending status request: {e}")
            return f"Status request to {destination} failed"

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
