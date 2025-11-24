"""Network diagnostic tools for mesh network operations."""

import logging
from typing import Any, Optional

from pydantic_ai import RunContext

from .logging_wrapper import create_logging_tool_decorator

logger = logging.getLogger(__name__)


def register_network_tools(agent: Any) -> None:
    """Register network diagnostic tools.

    Args:
        agent: The Pydantic AI agent to register tools with
    """
    # Create logging tool decorator
    tool = create_logging_tool_decorator(agent)

    @tool()
    async def ping_node(ctx: RunContext[Any], destination: str) -> str:
        """Ping a mesh node to check connectivity and measure latency.

        This sends a status request to the specified node and waits for a response.
        Use this to test if a node is reachable and measure round-trip time.

        Args:
            destination: Node ID (public key or shortened ID) to ping

        Returns:
            Success/failure message with ping results
        """
        try:
            logger.info(f"Pinging node: {destination}")

            success = await ctx.deps.meshcore.ping_node(destination)

            if success:
                return f"✓ Ping successful to {destination[:16]}..."
            else:
                return f"✗ Ping failed to {destination[:16]}... (node may be offline or unreachable)"

        except Exception as e:
            logger.error(f"Error pinging node {destination}: {e}")
            return f"Error pinging node: {str(e)[:100]}"

    @tool()
    async def trace_path(
        ctx: RunContext[Any], path: Optional[str] = None, auth_code: Optional[int] = None
    ) -> str:
        """Send a trace packet for mesh network routing diagnostics.

        This sends a trace packet through the mesh network to diagnose routing
        and network topology. Like traceroute for mesh networks.

        Args:
            path: Optional comma-separated path of node IDs to trace through (e.g., "node1,node2,node3")
            auth_code: Optional authentication code for the trace

        Returns:
            Success/failure message about trace packet
        """
        try:
            if path:
                logger.info(f"Tracing path: {path}")
            else:
                logger.info("Sending trace packet (automatic path)")

            success = await ctx.deps.meshcore.send_trace(path=path, auth_code=auth_code)

            if success:
                msg = "✓ Trace packet sent successfully"
                if path:
                    msg += f" (path: {path})"
                msg += "\nWait for trace responses from nodes in the path."
                return msg
            else:
                return "✗ Failed to send trace packet (device may be busy or disconnected)"

        except Exception as e:
            logger.error(f"Error sending trace: {e}")
            return f"Error sending trace: {str(e)[:100]}"
