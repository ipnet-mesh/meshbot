"""Utility tools for general purpose tasks."""

import logging
from typing import Any

from pydantic_ai import RunContext

from .logging_wrapper import create_logging_tool_decorator

logger = logging.getLogger(__name__)


def register_utility_tools(agent: Any) -> None:
    """Register utility tools.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    # Create logging tool decorator
    tool = create_logging_tool_decorator(agent)

    @tool()
    async def calculate(ctx: RunContext[Any], expression: str) -> str:
        """Evaluate a mathematical expression safely.

        Args:
            expression: Math expression to evaluate (e.g., "2 + 2", "sqrt(16)", "pi * 2")

        Returns:
            Result of the calculation or error message
        """
        try:
            import math
            import re

            # Allow only safe characters (numbers, operators, math functions)
            if not re.match(r"^[0-9+\-*/()., a-z]+$", expression.lower()):
                return "Invalid expression. Use only numbers and basic math operators."

            # Create safe namespace with math functions
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": math.sqrt,
                "pi": math.pi,
                "e": math.e,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "ceil": math.ceil,
                "floor": math.floor,
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)
            return f"{expression} = {result}"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return f"Error calculating: {str(e)[:50]}"

    @tool()
    async def get_current_time(ctx: RunContext[Any], format: str = "human") -> str:
        """Get current date and time.

        Args:
            format: Output format - "human" (readable), "unix" (timestamp), or "iso" (ISO 8601)

        Returns:
            Current time in requested format
        """
        try:
            from datetime import datetime

            now = datetime.now()

            if format == "unix":
                return f"Unix timestamp: {int(now.timestamp())}"
            elif format == "iso":
                return f"ISO 8601: {now.isoformat()}"
            else:  # human readable
                return now.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error getting time: {e}")
            return "Error retrieving current time"

    @tool()
    async def get_bot_status(ctx: RunContext[Any]) -> str:
        """Get current bot status and statistics.

        Returns:
            Bot status information including uptime, memory stats, and connection status
        """
        try:
            # Get memory statistics
            memory_stats = await ctx.deps.memory.get_statistics()

            # Get connection status
            is_connected = ctx.deps.meshcore.is_connected()

            # Get contacts count
            contacts = await ctx.deps.meshcore.get_contacts()
            online_count = sum(1 for c in contacts if c.is_online)

            status = (
                f"Bot Status:\n"
                f"Connected: {'Yes' if is_connected else 'No'}\n"
                f"Contacts: {online_count}/{len(contacts)} online\n"
                f"Total messages: {memory_stats.get('total_messages', 0)}\n"
                f"Users: {memory_stats.get('total_users', 0)}"
            )

            return status
        except Exception as e:
            logger.error(f"Error getting bot status: {e}")
            return "Error retrieving bot status"
