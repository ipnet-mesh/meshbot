"""Basic tests for MeshBot."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from meshbot.memory import ConversationMessage, MemoryManager
from meshbot.meshcore_interface import MeshCoreMessage, MockMeshCoreInterface


class TestMemoryManager:
    """Test memory management functionality."""

    @pytest.fixture
    async def memory_manager(self, tmp_path: Path) -> MemoryManager:
        """Create a memory manager for testing."""
        # Use a test-specific database to avoid conflicts
        db_path = tmp_path / "test_memori.db"
        manager = MemoryManager(
            storage_path=tmp_path / "test_memory.json",
            database_url=f"sqlite:///{db_path}",
        )
        await manager.load()
        return manager

    @pytest.mark.asyncio
    async def test_user_memory_creation(self, memory_manager: MemoryManager) -> None:
        """Test creating and retrieving user memory."""
        user_id = "test_user_123"

        # Get user memory (should create new one)
        memory = await memory_manager.get_user_memory(user_id)

        assert memory.user_id == user_id
        assert memory.total_messages == 0
        # conversation_history starts empty
        assert memory.conversation_history == []

    @pytest.mark.asyncio
    async def test_adding_messages(self, memory_manager: MemoryManager) -> None:
        """Test adding messages to user memory (metadata only)."""
        user_id = "test_user_456"

        # Create a test message
        message = MeshCoreMessage(
            sender=user_id,
            sender_name="TestUser",
            content="Hello, bot!",
            timestamp=1234567890.0,
        )

        # Add message
        await memory_manager.add_message(message, is_from_user=True)

        # Check memory - message count should increment
        memory = await memory_manager.get_user_memory(user_id)
        assert memory.total_messages == 1
        assert memory.user_name == "TestUser"
        # Note: conversation_history is managed by Memori, not stored in metadata
        assert memory.conversation_history == []

    @pytest.mark.asyncio
    async def test_conversation_history(self, memory_manager: MemoryManager) -> None:
        """Test conversation history with Memori integration."""
        user_id = "test_user_789"

        # Add multiple messages
        for i in range(5):
            message = MeshCoreMessage(
                sender=user_id,
                sender_name="TestUser",
                content=f"Message {i}",
                timestamp=1234567890.0 + i,
            )
            await memory_manager.add_message(message, is_from_user=i % 2 == 0)

        # Check message count
        memory = await memory_manager.get_user_memory(user_id)
        assert memory.total_messages == 5

        # Note: Actual conversation history is managed by Memori
        # and automatically injected into LLM calls
        history = await memory_manager.get_conversation_history(user_id)
        assert isinstance(history, list)  # Returns empty list for compatibility

    @pytest.mark.asyncio
    async def test_user_preferences(self, memory_manager: MemoryManager) -> None:
        """Test user preferences."""
        user_id = "test_user_prefs"

        # Set preferences
        await memory_manager.set_user_preference(user_id, "language", "en")
        await memory_manager.set_user_preference(user_id, "timezone", "UTC")

        # Get preferences
        lang = await memory_manager.get_user_preference(user_id, "language")
        tz = await memory_manager.get_user_preference(user_id, "timezone")

        assert lang == "en"
        assert tz == "UTC"

        # Test default value
        missing = await memory_manager.get_user_preference(
            user_id, "missing_key", default="default_value"
        )
        assert missing == "default_value"

    @pytest.mark.asyncio
    async def test_user_context(self, memory_manager: MemoryManager) -> None:
        """Test user context."""
        user_id = "test_user_context"

        # Set context
        await memory_manager.set_user_context(user_id, "project", "meshbot")
        await memory_manager.set_user_context(user_id, "skill_level", "expert")

        # Get context
        project = await memory_manager.get_user_context(user_id, "project")
        skill = await memory_manager.get_user_context(user_id, "skill_level")

        assert project == "meshbot"
        assert skill == "expert"


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
        db_path = tmp_path / "integration_memori.db"
        memory = MemoryManager(
            storage_path=tmp_path / "memory.json",
            database_url=f"sqlite:///{db_path}",
        )
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
        await memory.add_message(message, is_from_user=True)

        # Verify
        user_memory = await memory.get_user_memory("test_user")
        assert user_memory.total_messages == 1
        assert user_memory.user_name == "TestUser"

        # Cleanup
        await meshcore.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
