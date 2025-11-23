"""MeshBot tools module - organized tool functions for the AI agent."""

from typing import Any


def register_all_tools(agent: Any) -> None:
    """Register all tools with the agent.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    from .conversation import register_conversation_tools
    from .fun import register_fun_tools
    from .query import register_query_tools
    from .utility import register_utility_tools
    from .weather import register_weather_tool

    # Register all tool groups
    register_conversation_tools(agent)
    register_utility_tools(agent)
    register_fun_tools(agent)
    register_query_tools(agent)
    register_weather_tool(agent)


__all__ = ["register_all_tools"]
