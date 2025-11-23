"""Basic tests for MeshBot."""

import asyncio
from pathlib import Path

import pytest

from meshbot.memory import MemoryManager
from meshbot.meshcore_interface import MeshCoreMessage, MockMeshCoreInterface


class TestMemoryManager:
    """Test memory management functionality."""

    @pytest.fixture
    async def memory_manager(self, tmp_path: Path) -> MemoryManager:
        """Create a memory manager for testing."""
        # Use a test-specific database to avoid conflicts
        db_path = tmp_path / "test_meshbot.db"
        manager = MemoryManager(storage_path=db_path, max_lines=1000)
        await manager.load()
        return manager

    @pytest.mark.asyncio
    async def test_user_memory_creation(self, memory_manager: MemoryManager) -> None:
        """Test creating and retrieving user memory."""
        user_id = "test_user_123"

        # Get user memory (should return empty stats for new user)
        memory = await memory_manager.get_user_memory(user_id)

        assert memory["user_id"] == user_id
        assert memory["total_messages"] == 0
        assert memory["first_seen"] is None
        assert memory["last_seen"] is None

    @pytest.mark.asyncio
    async def test_adding_messages(self, memory_manager: MemoryManager) -> None:
        """Test adding messages to SQLite database."""
        user_id = "test_user_456"

        # Add a test message
        await memory_manager.add_message(
            user_id=user_id,
            role="user",
            content="Hello, bot!",
            message_type="direct",
            timestamp=1234567890.0,
        )

        # Check memory - message count should increment
        memory = await memory_manager.get_user_memory(user_id)
        assert memory["total_messages"] == 1
        assert memory["first_seen"] == 1234567890.0
        assert memory["last_seen"] == 1234567890.0

    @pytest.mark.asyncio
    async def test_conversation_history(self, memory_manager: MemoryManager) -> None:
        """Test conversation history retrieval."""
        user_id = "test_user_789"

        # Add multiple messages
        for i in range(5):
            role = "user" if i % 2 == 0 else "assistant"
            await memory_manager.add_message(
                user_id=user_id,
                role=role,
                content=f"Message {i}",
                message_type="direct",
                timestamp=1234567890.0 + i,
            )

        # Check message count
        memory = await memory_manager.get_user_memory(user_id)
        assert memory["total_messages"] == 5

        # Get conversation history
        history = await memory_manager.get_conversation_history(user_id, limit=10)
        assert len(history) == 5
        assert history[0]["content"] == "Message 0"
        assert history[-1]["content"] == "Message 4"

    @pytest.mark.asyncio
    async def test_conversation_context(self, memory_manager: MemoryManager) -> None:
        """Test getting conversation context for LLM."""
        user_id = "test_context_user"

        # Add some messages
        await memory_manager.add_message(
            user_id=user_id,
            role="user",
            content="What's the weather?",
            message_type="direct",
        )
        await memory_manager.add_message(
            user_id=user_id,
            role="assistant",
            content="I don't have weather data.",
            message_type="direct",
        )

        # Get context
        context = await memory_manager.get_conversation_context(
            user_id, "direct", max_messages=10
        )
        assert len(context) == 2
        assert all("role" in msg and "content" in msg for msg in context)

    @pytest.mark.asyncio
    async def test_statistics(self, memory_manager: MemoryManager) -> None:
        """Test getting overall statistics."""
        # Add messages for multiple users
        await memory_manager.add_message(
            user_id="user1", role="user", content="Hello", message_type="direct"
        )
        await memory_manager.add_message(
            user_id="user2", role="user", content="Hi", message_type="direct"
        )
        await memory_manager.add_message(
            user_id="channel_0",
            role="user",
            content="Channel msg",
            message_type="channel",
        )

        # Get stats
        stats = await memory_manager.get_statistics()
        assert stats["total_messages"] >= 3
        assert stats["total_users"] >= 2


class TestMockMeshCore:
    """Test mock MeshCore interface."""

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self):
        """Test connecting and disconnecting."""
        mock = MockMeshCoreInterface()

        assert not mock.is_connected()

        await mock.connect()
        assert mock.is_connected()

        await mock.disconnect()
        assert not mock.is_connected()

    @pytest.mark.asyncio
    async def test_sending_messages(self):
        """Test sending messages."""
        mock = MockMeshCoreInterface()
        await mock.connect()

        success = await mock.send_message("node1", "Hello!")
        assert success

        await mock.disconnect()

    @pytest.mark.asyncio
    async def test_getting_contacts(self):
        """Test getting contacts."""
        mock = MockMeshCoreInterface()
        await mock.connect()

        contacts = await mock.get_contacts()
        assert len(contacts) >= 2  # Mock has 2 default contacts

        await mock.disconnect()

    @pytest.mark.asyncio
    async def test_pinging_nodes(self):
        """Test pinging nodes."""
        mock = MockMeshCoreInterface()
        await mock.connect()

        # Ping existing node
        success = await mock.ping_node("node1")
        assert success

        # Ping non-existent node
        success = await mock.ping_node("nonexistent")
        assert not success

        await mock.disconnect()


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_message_flow(self, tmp_path: Path) -> None:
        """Test complete message flow."""
        # Setup components
        db_path = tmp_path / "integration_meshbot.db"
        memory = MemoryManager(storage_path=db_path, max_lines=1000)
        await memory.load()

        meshcore = MockMeshCoreInterface()
        await meshcore.connect()

        # Simulate receiving a message
        message = MeshCoreMessage(
            sender="test_user",
            sender_name="TestUser",
            content="ping",
            timestamp=asyncio.get_event_loop().time(),
        )

        # Add to memory
        await memory.add_message(
            user_id=message.sender,
            role="user",
            content=message.content,
            message_type="direct",
            timestamp=message.timestamp,
        )

        # Verify
        user_memory = await memory.get_user_memory("test_user")
        assert user_memory["total_messages"] == 1
        assert user_memory["first_seen"] is not None

        # Cleanup
        await meshcore.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
