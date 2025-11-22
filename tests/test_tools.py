"""Tests for MeshBot agent tools."""

import pytest

from meshbot.agent import MeshBotAgent


class TestToolIntegration:
    """Integration tests for tools."""

    @pytest.mark.asyncio
    async def test_agent_initialization_with_tools(self) -> None:
        """Test that agent initializes successfully with all tools."""
        agent = MeshBotAgent(meshcore_connection_type="mock")
        await agent.initialize()

        # Verify agent is initialized
        assert agent.agent is not None
        assert agent.meshcore is not None
        assert agent.memory is not None

        # Verify agent can start
        await agent.start()
        assert agent._running

        # Cleanup
        await agent.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
