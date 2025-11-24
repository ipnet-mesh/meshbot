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
        ctx: RunContext[Any],
        path: Optional[str] = None,
        auth_code: Optional[int] = None,
        timeout: float = 10.0,
    ) -> str:
        """Send a trace packet for mesh network routing diagnostics.

        This sends a trace packet through the mesh network to diagnose routing
        and network topology. Like traceroute for mesh networks. Waits for responses.

        Args:
            path: Optional comma-separated path of node IDs to trace through (e.g., "node1,node2,node3")
            auth_code: Optional authentication code for the trace
            timeout: Maximum time to wait for responses in seconds (default: 10s)

        Returns:
            Trace results showing path and latency information
        """
        try:
            if path:
                logger.info(f"Tracing path: {path}")
            else:
                logger.info("Sending trace packet (automatic path)")

            # Send trace and wait for responses
            responses = await ctx.deps.meshcore.send_trace_and_wait(
                path=path, auth_code=auth_code, timeout=timeout
            )

            if not responses:
                return f"✗ No trace responses received within {timeout}s\n(Device may be busy, disconnected, or path unreachable)"

            # Format responses
            msg = f"✓ Trace complete - {len(responses)} hop(s)\n"
            msg += "Path:\n"

            for i, response in enumerate(responses):
                # Extract info from response payload
                hop_num = response.get("hop", i)
                node_id = response.get("node", response.get("node_id", "unknown"))
                latency = response.get("latency_ms", response.get("latency", "?"))

                # Truncate node ID for display
                if isinstance(node_id, str) and len(node_id) > 16:
                    node_id = node_id[:16] + "..."

                msg += f"  {hop_num}. {node_id} ({latency}ms)\n"

            return msg.rstrip()

        except Exception as e:
            logger.error(f"Error sending trace: {e}")
            return f"Error sending trace: {str(e)[:100]}"
