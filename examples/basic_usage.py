"""Example usage of MeshBot."""

import asyncio
import logging
from pathlib import Path

from meshbot.agent import MeshBotAgent
from meshbot.config import MeshBotConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_example():
    """Basic example of using MeshBot."""
    logger.info("Starting basic MeshBot example...")

    # Create agent with mock connection
    agent = MeshBotAgent(
        model="openai:gpt-4o-mini",
        knowledge_dir=Path("knowledge"),
        memory_path=Path("example_memory.json"),
        meshcore_connection_type="mock",
    )

    try:
        # Initialize and start agent
        await agent.initialize()
        await agent.start()

        logger.info("MeshBot started successfully!")

        # Simulate some interactions
        await simulate_interactions(agent)

        # Show status
        status = await agent.get_status()
        logger.info(f"Agent status: {status}")

    finally:
        await agent.stop()
        logger.info("MeshBot stopped")


async def simulate_interactions(agent: MeshBotAgent):
    """Simulate some message interactions."""
    logger.info("Simulating message interactions...")

    # Wait a bit for setup
    await asyncio.sleep(1)

    # Simulate receiving a ping
    if agent.meshcore:
        # Create a mock message
        from meshbot.meshcore_interface import MeshCoreMessage

        ping_message = MeshCoreMessage(
            sender="node1",
            sender_name="TestNode1",
            content="ping",
            timestamp=asyncio.get_event_loop().time(),
        )

        # Add to message queue (in real scenario, this would come from MeshCore)
        if hasattr(agent.meshcore, "_message_queue"):
            await agent.meshcore._message_queue.put(ping_message)
            logger.info("Sent ping message to agent")

        # Wait for processing
        await asyncio.sleep(2)

        # Send a question
        question_message = MeshCoreMessage(
            sender="node1",
            sender_name="TestNode1",
            content="What is MeshCore?",
            timestamp=asyncio.get_event_loop().time(),
        )

        if hasattr(agent.meshcore, "_message_queue"):
            await agent.meshcore._message_queue.put(question_message)
            logger.info("Sent question message to agent")

        # Wait for processing
        await asyncio.sleep(3)

        # Send a help request
        help_message = MeshCoreMessage(
            sender="node2",
            sender_name="TestNode2",
            content="help",
            timestamp=asyncio.get_event_loop().time(),
        )

        if hasattr(agent.meshcore, "_message_queue"):
            await agent.meshcore._message_queue.put(help_message)
            logger.info("Sent help message to agent")

        # Wait for processing
        await asyncio.sleep(2)


async def configuration_example():
    """Example using configuration file."""
    logger.info("Starting configuration example...")

    # Create a custom configuration
    config = MeshBotConfig()
    config.ai.model = "openai:gpt-4o-mini"
    config.meshcore.connection_type = "mock"
    config.knowledge.knowledge_dir = Path("knowledge")
    config.memory.storage_path = Path("config_example_memory.json")
    config.logging.level = "DEBUG"

    # Validate configuration
    config.validate()

    # Create agent with configuration
    agent = MeshBotAgent(
        model=config.ai.model,
        knowledge_dir=config.knowledge.knowledge_dir,
        memory_path=config.memory.storage_path,
        meshcore_connection_type=config.meshcore.connection_type,
    )

    try:
        await agent.initialize()
        await agent.start()

        logger.info("Agent started with custom configuration")

        # Show configuration
        status = await agent.get_status()
        logger.info(f"Configuration status: {status}")

        await asyncio.sleep(2)

    finally:
        await agent.stop()


async def knowledge_base_example():
    """Example demonstrating knowledge base functionality."""
    logger.info("Starting knowledge base example...")

    agent = MeshBotAgent(
        model="openai:gpt-4o-mini",
        knowledge_dir=Path("knowledge"),
        meshcore_connection_type="mock",
    )

    try:
        await agent.initialize()
        await agent.start()

        # Test knowledge base search
        if agent.knowledge:
            results = await agent.knowledge.search("MeshCore basics")
            logger.info(f"Knowledge search results: {len(results)} items found")
            for result in results[:3]:
                logger.info(f"  - {result.excerpt[:100]}...")

        # Simulate a search query
        from meshbot.meshcore_interface import MeshCoreMessage

        search_message = MeshCoreMessage(
            sender="node1",
            sender_name="TestNode1",
            content="search troubleshooting",
            timestamp=asyncio.get_event_loop().time(),
        )

        if hasattr(agent.meshcore, "_message_queue"):
            await agent.meshcore._message_queue.put(search_message)
            logger.info("Sent search query to agent")

        await asyncio.sleep(3)

    finally:
        await agent.stop()


async def main():
    """Run all examples."""
    logger.info("Running MeshBot examples...")

    try:
        await basic_example()
        print("\n" + "=" * 50 + "\n")

        await configuration_example()
        print("\n" + "=" * 50 + "\n")

        await knowledge_base_example()

    except Exception as e:
        logger.error(f"Error in examples: {e}")
        raise

    logger.info("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
