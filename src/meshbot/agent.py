"""Main Pydantic AI agent for MeshBot."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from .knowledge import SimpleKnowledgeBase, create_knowledge_base
from .memory import MemoryManager
from .meshcore_interface import (
    MeshCoreInterface,
    MeshCoreMessage,
    create_meshcore_interface,
)

logger = logging.getLogger(__name__)


@dataclass
class MeshBotDependencies:
    """Dependencies for the MeshBot agent."""

    meshcore: MeshCoreInterface
    memory: MemoryManager
    knowledge: SimpleKnowledgeBase


class AgentResponse(BaseModel):
    """Structured response from the agent."""

    response: str = Field(description="The response message to send")
    action: Optional[str] = Field(
        description="Any action to take (e.g., 'ping', 'search')", default=None
    )
    action_data: Optional[Dict[str, Any]] = Field(
        description="Data for the action", default=None
    )
    confidence: float = Field(
        description="Confidence in the response (0-1)", ge=0, le=1
    )


class MeshBotAgent:
    """Main AI agent for MeshBot."""

    def __init__(
        self,
        model: str = "openai:gpt-4o-mini",
        knowledge_dir: Path = Path("knowledge"),
        memory_path: Optional[Path] = None,
        meshcore_connection_type: str = "mock",
        **meshcore_kwargs,
    ):
        self.model = model
        self.knowledge_dir = knowledge_dir
        self.memory_path = memory_path
        self.meshcore_connection_type = meshcore_connection_type
        self.meshcore_kwargs = meshcore_kwargs

        # Initialize components
        self.meshcore: Optional[MeshCoreInterface] = None
        self.memory: Optional[MemoryManager] = None
        self.knowledge: Optional[SimpleKnowledgeBase] = None
        self.agent: Optional[Agent[MeshBotDependencies, AgentResponse]] = None

        self._running = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing MeshBot agent...")

        # Initialize MeshCore interface
        from .meshcore_interface import ConnectionType

        connection_type = ConnectionType(self.meshcore_connection_type)
        self.meshcore = create_meshcore_interface(
            connection_type, **self.meshcore_kwargs
        )

        # Initialize memory manager
        self.memory = MemoryManager(self.memory_path or Path("memory_metadata.json"))
        await self.memory.load()

        # Enable Memori for automatic conversation memory
        self.memory.enable_memori()

        # Initialize knowledge base
        self.knowledge = create_knowledge_base(self.knowledge_dir)
        await self.knowledge.load()

        # Create Pydantic AI agent
        self.agent = Agent(
            self.model,
            deps_type=MeshBotDependencies,
            output_type=AgentResponse,
            instructions=(
                "You are MeshBot, an AI assistant that communicates through the MeshCore network. "
                "You are helpful, concise, and knowledgeable. "
                "You can answer questions, help with tasks, and provide information from your knowledge base. "
                "Always be friendly and professional in your responses. "
                "When users send 'ping', respond with 'pong'. "
                "Keep responses relatively short and clear for network communication."
            ),
        )

        # Register tools
        self._register_tools()

        # Set up message handler
        self.meshcore.add_message_handler(self._handle_message)

        logger.info("MeshBot agent initialized successfully")

    def _register_tools(self) -> None:
        """Register tools for the agent."""

        @self.agent.tool
        async def search_knowledge(
            ctx: RunContext[MeshBotDependencies], query: str
        ) -> str:
            """Search the knowledge base for information."""
            try:
                results = await ctx.deps.knowledge.search(query, max_results=3)
                if not results:
                    return "No relevant information found in the knowledge base."

                response = "Found the following information:\n\n"
                for i, result in enumerate(results, 1):
                    response += f"{i}. {result.excerpt}\n"
                    response += f"   Source: {result.chunk.source_file}\n\n"

                return response.strip()
            except Exception as e:
                logger.error(f"Error searching knowledge base: {e}")
                return "Error searching knowledge base."

        @self.agent.tool
        async def get_user_info(
            ctx: RunContext[MeshBotDependencies], user_id: str
        ) -> str:
            """Get information about a user."""
            try:
                memory = await ctx.deps.memory.get_user_memory(user_id)
                stats = await ctx.deps.memory.get_statistics()

                info = f"User: {memory.user_name or user_id}\n"
                info += f"Total messages: {memory.total_messages}\n"
                info += f"First seen: {memory.first_seen}\n"
                info += f"Last seen: {memory.last_seen}\n"

                return info
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
                return "Error retrieving user information."

        @self.agent.tool
        async def ping_node(
            ctx: RunContext[MeshBotDependencies], destination: str
        ) -> str:
            """Ping a MeshCore node."""
            try:
                success = await ctx.deps.meshcore.ping_node(destination)
                return f"Ping to {destination}: {'Success' if success else 'Failed'}"
            except Exception as e:
                logger.error(f"Error pinging node: {e}")
                return f"Error pinging {destination}: {e}"

        @self.agent.tool
        async def get_contacts(ctx: RunContext[MeshBotDependencies]) -> str:
            """Get list of available contacts."""
            try:
                contacts = await ctx.deps.meshcore.get_contacts()
                if not contacts:
                    return "No contacts available."

                contact_list = "Available contacts:\n"
                for contact in contacts:
                    status = "🟢" if contact.is_online else "🔴"
                    name = contact.name or contact.public_key[:8] + "..."
                    contact_list += f"{status} {name} ({contact.public_key[:16]}...)\n"

                return contact_list.strip()
            except Exception as e:
                logger.error(f"Error getting contacts: {e}")
                return "Error retrieving contacts."

        @self.agent.tool
        async def get_conversation_history(
            ctx: RunContext[MeshBotDependencies], user_id: str, limit: int = 5
        ) -> str:
            """Get recent conversation history with a user."""
            try:
                history = await ctx.deps.memory.get_conversation_history(user_id, limit)
                if not history:
                    return "No conversation history with this user."

                response = "Recent conversation:\n"
                for msg in history:
                    role = "User" if msg.role == "user" else "Assistant"
                    response += f"{role}: {msg.content}\n"

                return response.strip()
            except Exception as e:
                logger.error(f"Error getting conversation history: {e}")
                return "Error retrieving conversation history."

    async def start(self) -> None:
        """Start the agent."""
        if self._running:
            logger.warning("Agent is already running")
            return

        if not self.agent:
            await self.initialize()

        logger.info("Starting MeshBot agent...")

        # Connect to MeshCore
        await self.meshcore.connect()

        self._running = True
        logger.info("MeshBot agent started successfully")

    async def stop(self) -> None:
        """Stop the agent."""
        if not self._running:
            return

        logger.info("Stopping MeshBot agent...")

        self._running = False

        # Save memory
        if self.memory:
            await self.memory.save()

        # Disconnect from MeshCore
        if self.meshcore:
            await self.meshcore.disconnect()

        logger.info("MeshBot agent stopped")

    async def _handle_message(self, message: MeshCoreMessage) -> None:
        """Handle incoming message."""
        try:
            logger.info(f"Received message from {message.sender}: {message.content}")

            # Store message in memory
            await self.memory.add_message(message, is_from_user=True)

            # Create dependencies for this interaction
            deps = MeshBotDependencies(
                meshcore=self.meshcore, memory=self.memory, knowledge=self.knowledge
            )

            # Run agent (Memori will automatically inject conversation context)
            result = await self.agent.run(message.content, deps=deps)

            # Send response
            response = result.output.response
            if response:
                await self.meshcore.send_message(message.sender, response)

                # Store assistant response in memory
                assistant_message = MeshCoreMessage(
                    sender="meshbot",
                    sender_name="MeshBot",
                    content=response,
                    timestamp=asyncio.get_event_loop().time(),
                    message_type="direct",
                )
                await self.memory.add_message(assistant_message, is_from_user=False)

            # Handle any additional actions
            if result.output.action:
                await self._handle_action(
                    result.output.action, result.output.action_data, message.sender
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            # Send error response
            try:
                await self.meshcore.send_message(
                    message.sender,
                    "Sorry, I encountered an error processing your message.",
                )
            except:
                pass

    async def _handle_action(
        self, action: str, action_data: Optional[Dict[str, Any]], sender: str
    ) -> None:
        """Handle additional actions from the agent."""
        try:
            if action == "ping" and action_data and "destination" in action_data:
                await self.meshcore.ping_node(action_data["destination"])
            # Add more action handlers as needed
        except Exception as e:
            logger.error(f"Error handling action {action}: {e}")

    async def send_message(self, destination: str, message: str) -> bool:
        """Send a message to a destination."""
        if not self.meshcore or not self._running:
            return False

        try:
            success = await self.meshcore.send_message(destination, message)
            if success:
                # Store sent message in memory
                sent_message = MeshCoreMessage(
                    sender="meshbot",
                    sender_name="MeshBot",
                    content=message,
                    timestamp=asyncio.get_event_loop().time(),
                    message_type="direct",
                )
                await self.memory.add_message(sent_message, is_from_user=False)

            return success
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = {
            "running": self._running,
            "model": self.model,
            "meshcore_connected": (
                self.meshcore.is_connected() if self.meshcore else False
            ),
            "meshcore_type": self.meshcore_connection_type,
        }

        if self.memory:
            memory_stats = await self.memory.get_statistics()
            status["memory"] = memory_stats

        if self.knowledge:
            knowledge_stats = await self.knowledge.get_statistics()
            status["knowledge"] = knowledge_stats

        return status
