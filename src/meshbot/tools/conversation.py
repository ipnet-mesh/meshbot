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
