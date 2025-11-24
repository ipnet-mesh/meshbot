"""MeshBot tools module - organized tool functions for the AI agent."""

from typing import Any


def register_all_tools(agent: Any) -> None:
    """Register all tools with the agent.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    from .fun import register_fun_tools
    from .network import register_network_tools
    from .nodes import register_node_tools
    from .utility import register_utility_tools
    from .weather import register_weather_tool

    # Register all tool groups
    register_node_tools(agent)
    register_utility_tools(agent)
    register_fun_tools(agent)
    register_network_tools(agent)
    register_weather_tool(agent)


__all__ = ["register_all_tools"]
