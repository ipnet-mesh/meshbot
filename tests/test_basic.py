"""Basic tests for MeshBot."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from meshbot.memory import MemoryManager, ConversationMessage
from meshbot.knowledge import SimpleKnowledgeBase
from meshbot.meshcore_interface import MockMeshCoreInterface, MeshCoreMessage


class TestMemoryManager:
    """Test memory management functionality."""

    @pytest.fixture
    async def memory_manager(self, tmp_path):
        """Create a memory manager for testing."""
        manager = MemoryManager(tmp_path / "test_memory.json")
        await manager.load()
        return manager

    @pytest.mark.asyncio
    async def test_user_memory_creation(self, memory_manager):
        """Test creating and retrieving user memory."""
        user_id = "test_user_123"

        # Get user memory (should create new one)
        memory = await memory_manager.get_user_memory(user_id)

        assert memory.user_id == user_id
        assert memory.total_messages == 0
        assert memory.conversation_history == []

    @pytest.mark.asyncio
    async def test_adding_messages(self, memory_manager):
        """Test adding messages to user memory."""
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

        # Check memory
        memory = await memory_manager.get_user_memory(user_id)
        assert memory.total_messages == 1
        assert len(memory.conversation_history) == 1
        assert memory.conversation_history[0].content == "Hello, bot!"
        assert memory.conversation_history[0].role == "user"

    @pytest.mark.asyncio
    async def test_conversation_history(self, memory_manager):
        """Test retrieving conversation history."""
        user_id = "test_user_789"

        # Add multiple messages
        for i in range(5):
            message = MeshCoreMessage(
                sender=user_id, content=f"Message {i}", timestamp=1234567890.0 + i
            )
            await memory_manager.add_message(message, is_from_user=i % 2 == 0)

        # Get history
        history = await memory_manager.get_conversation_history(user_id)
        assert len(history) == 5

        # Get limited history
        limited_history = await memory_manager.get_conversation_history(
            user_id, limit=3
        )
        assert len(limited_history) == 3


class TestKnowledgeBase:
    """Test knowledge base functionality."""

    @pytest.fixture
    async def knowledge_base(self, tmp_path):
        """Create a knowledge base for testing."""
        # Create test files
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        (kb_dir / "test1.txt").write_text(
            "This is a test file about MeshCore networking."
        )
        (kb_dir / "test2.md").write_text(
            "# Test Markdown\n\nThis file contains **important** information."
        )
        (kb_dir / "subdir").mkdir()
        (kb_dir / "subdir" / "test3.txt").write_text("This is in a subdirectory.")

        kb = SimpleKnowledgeBase(kb_dir)
        await kb.load()
        return kb

    @pytest.mark.asyncio
    async def test_loading_files(self, knowledge_base):
        """Test loading files into knowledge base."""
        stats = await knowledge_base.get_statistics()
        assert stats["total_files"] == 3
        assert stats["total_chunks"] > 0

    @pytest.mark.asyncio
    async def test_search_functionality(self, knowledge_base):
        """Test searching the knowledge base."""
        # Search for "MeshCore"
        results = await knowledge_base.search("MeshCore")
        assert len(results) > 0
        assert "MeshCore" in results[0].excerpt.lower()

        # Search for "important"
        results = await knowledge_base.search("important")
        assert len(results) > 0

        # Search for non-existent term
        results = await knowledge_base.search("nonexistent")
        assert len(results) == 0


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
    async def test_message_flow(self, tmp_path):
        """Test complete message flow."""
        # Setup components
        memory = MemoryManager(tmp_path / "memory.json")
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
