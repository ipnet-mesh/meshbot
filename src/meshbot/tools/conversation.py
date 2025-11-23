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
    async def get_conversation_history(
        ctx: RunContext[Any], user_id: str, limit: int = 5
    ) -> str:
        """Get recent conversation history with a user."""
        try:
            history = await ctx.deps.memory.get_conversation_history(user_id, limit)
            if not history:
                return "No conversation history with this user."

            response = "Recent conversation:\n"
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                response += f"{role}: {msg['content']}\n"

            return response.strip()
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return "Error retrieving conversation history."
