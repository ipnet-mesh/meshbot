"""Logging wrapper for tool calls."""

import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def with_tool_logging(tool_func: Callable) -> Callable:
    """Decorator to add logging to tool functions.

    This wrapper logs:
    - Tool name and parameters when called
    - Tool result when completed
    - Any errors that occur

    Args:
        tool_func: The tool function to wrap

    Returns:
        Wrapped function with logging
    """

    @functools.wraps(tool_func)
    async def wrapper(*args, **kwargs):
        tool_name = tool_func.__name__

        # Extract meaningful parameters (skip ctx and self)
        params_str = ""
        if kwargs:
            # Filter out context and other internal params
            display_params = {
                k: v
                for k, v in kwargs.items()
                if k not in ["ctx", "self"] and not k.startswith("_")
            }
            if display_params:
                # Truncate long values for readability
                truncated_params = {}
                for k, v in display_params.items():
                    if isinstance(v, str) and len(v) > 50:
                        truncated_params[k] = v[:47] + "..."
                    else:
                        truncated_params[k] = v
                params_str = f" with {truncated_params}"

        logger.info(f"🔧 TOOL CALL: {tool_name}(){params_str}")

        try:
            result = await tool_func(*args, **kwargs)

            # Truncate result for logging
            result_preview = str(result)
            if len(result_preview) > 100:
                result_preview = result_preview[:97] + "..."

            logger.info(f"✅ TOOL RESULT: {tool_name} -> {result_preview}")
            return result

        except Exception as e:
            logger.error(
                f"❌ TOOL ERROR: {tool_name} failed with {type(e).__name__}: {str(e)[:100]}"
            )
            raise

    return wrapper


def create_logging_tool_decorator(agent: Any) -> Callable:
    """Create a tool decorator that automatically adds logging.

    This returns a decorator that can be used like @agent.tool,
    but automatically wraps the function with logging.

    Args:
        agent: The Pydantic AI agent

    Returns:
        A decorator function that registers tools with logging
    """

    def logging_tool(*decorator_args, **decorator_kwargs):
        """Decorator that adds logging to agent tools."""

        def decorator(func: Callable) -> Callable:
            # First wrap with logging
            logged_func = with_tool_logging(func)

            # Then register with agent
            agent.tool(*decorator_args, **decorator_kwargs)(logged_func)

            return logged_func

        return decorator

    return logging_tool
