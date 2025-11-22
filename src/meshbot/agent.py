"""Main Pydantic AI agent for MeshBot."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

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
        memory_path: Optional[Path] = None,
        meshcore_connection_type: str = "mock",
        activation_phrase: str = "@bot",
        listen_channel: str = "0",
        custom_prompt: Optional[str] = None,
        base_url: Optional[str] = None,
        **meshcore_kwargs,
    ):
        self.model = model
        self.memory_path = memory_path
        self.meshcore_connection_type = meshcore_connection_type
        self.activation_phrase = activation_phrase.lower()
        self.listen_channel = listen_channel
        self.custom_prompt = custom_prompt
        self.base_url = base_url
        self.meshcore_kwargs = meshcore_kwargs

        # Initialize components
        self.meshcore: Optional[MeshCoreInterface] = None
        self.memory: Optional[MemoryManager] = None
        self.agent: Optional[Agent[MeshBotDependencies, AgentResponse]] = None

        self._running = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing MeshBot agent...")

        # Set up environment variables for OpenAI-compatible endpoints FIRST
        # This must happen before any component initialization
        import os

        # Map LLM_API_KEY to OPENAI_API_KEY for pydantic-ai and Memori
        # These libraries expect OPENAI_API_KEY, but we use LLM_API_KEY for provider-agnostic config
        llm_api_key = os.getenv("LLM_API_KEY")
        if llm_api_key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = llm_api_key
            logger.debug("Set OPENAI_API_KEY from LLM_API_KEY")

        # Initialize MeshCore interface
        from .meshcore_interface import ConnectionType

        connection_type = ConnectionType(self.meshcore_connection_type)
        self.meshcore = create_meshcore_interface(
            connection_type, **self.meshcore_kwargs
        )

        # Initialize memory manager with simple message history
        self.memory = MemoryManager(
            storage_path=self.memory_path or Path("memory_metadata.json"),
            max_dm_history=100,  # Keep last 100 messages per DM
            max_channel_history=1000,  # Keep last 1000 messages in channel
        )
        await self.memory.load()

        # Build agent instructions
        base_instructions = (
            "You are MeshBot, an AI assistant that communicates through the MeshCore network. "
            "You are helpful, concise, and knowledgeable. "
            "Always be friendly and professional in your responses. "
            "When users send 'ping', respond with 'pong'. "
            "Keep responses relatively short and clear for network communication."
        )

        # Add custom prompt if provided
        if self.custom_prompt:
            instructions = (
                f"{base_instructions}\n\nAdditional Context:\n{self.custom_prompt}"
            )
        else:
            instructions = base_instructions

        # Set base URL for custom endpoints if provided
        if self.base_url:
            os.environ["OPENAI_BASE_URL"] = self.base_url
            logger.info(f"Using custom LLM base URL: {self.base_url}")

        # Create Pydantic AI agent
        self.agent = Agent(
            self.model,
            deps_type=MeshBotDependencies,
            output_type=AgentResponse,
            instructions=instructions,
        )

        # Register tools
        self._register_tools()

        # Set up message handler
        self.meshcore.add_message_handler(self._handle_message)

        logger.info("MeshBot agent initialized successfully")

    def _register_tools(self) -> None:
        """Register tools for the agent."""

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

    def _should_respond_to_message(self, message: MeshCoreMessage) -> bool:
        """
        Determine if the bot should respond to this message.

        Rules:
        - Always respond to DMs (direct messages)
        - For channel messages, only respond if:
          1. Message is on the configured listen_channel
          2. Message contains the activation_phrase
        """
        logger.debug(f"_should_respond_to_message called with message_type={message.message_type}")

        # Always respond to DMs
        if message.message_type == "direct":
            logger.debug("Message is direct, returning True")
            return True

        # For channel messages, check channel and activation phrase
        if message.message_type == "channel":
            # Check if it's the channel we're listening to
            # Handle both string channel names and numeric IDs
            message_channel = str(getattr(message, "channel", "0"))
            if message_channel != self.listen_channel:
                logger.debug(
                    f"Ignoring message from channel {message_channel}, "
                    f"listening to {self.listen_channel}"
                )
                return False

            # Check for activation phrase (case-insensitive)
            if self.activation_phrase.lower() in message.content.lower():
                return True
            else:
                logger.debug(
                    f"Ignoring channel message without activation phrase: {message.content}"
                )
                return False

        # Default: don't respond to broadcast messages or unknown types
        return False

    async def _handle_message(self, message: MeshCoreMessage, raise_errors: bool = False) -> bool:
        """
        Handle incoming message.

        Args:
            message: The incoming message to handle
            raise_errors: If True, re-raise exceptions after logging (useful for testing)

        Returns:
            True if message was handled successfully, False otherwise
        """
        try:
            logger.info(f"Received message from {message.sender}: {message.content}")

            # Check if we should respond to this message
            logger.debug(f"Checking if should respond to message (type={message.message_type})")
            should_respond = self._should_respond_to_message(message)
            logger.debug(f"Should respond: {should_respond}")
            if not should_respond:
                logger.info("Message filtered out, not responding")
                return True  # Not an error, just filtered out

            logger.debug("Passed response filter, proceeding to handle message")

            # Store user message in memory
            logger.debug("Storing user message in memory...")
            await self.memory.add_message(
                user_id=message.sender,
                role="user",
                content=message.content,
                message_type=message.message_type,
                timestamp=message.timestamp,
            )
            logger.debug("User message stored successfully")

            # Get conversation context
            logger.debug("Retrieving conversation context...")
            context = await self.memory.get_conversation_context(
                user_id=message.sender, message_type=message.message_type
            )
            logger.debug(f"Retrieved {len(context)} messages from conversation history")

            # Create dependencies for this interaction
            logger.debug("Creating dependencies for agent...")
            deps = MeshBotDependencies(meshcore=self.meshcore, memory=self.memory)
            logger.debug("Dependencies created successfully")

            # Build the prompt with conversation history
            logger.debug("Building prompt with conversation history...")
            if context and len(context) > 1:  # Only include history if there's more than just current message
                # Include previous context in the prompt (excluding the message we just added)
                prompt = f"Conversation history:\n"
                for msg in context[:-1][-10:]:  # Last 10 messages, excluding current
                    role_name = "User" if msg["role"] == "user" else "Assistant"
                    prompt += f"{role_name}: {msg['content']}\n"
                prompt += f"\nUser: {message.content}\nAssistant:"
                logger.debug(f"Built prompt with {len(context)-1} previous messages")
            else:
                prompt = message.content
                logger.debug("No previous context, using message as-is")

            logger.info(f"Calling LLM with prompt (length: {len(prompt)} chars)")
            # Run agent with conversation context
            result = await self.agent.run(prompt, deps=deps)
            logger.debug(f"LLM returned result: {result.output}")

            # Send response
            response = result.output.response
            if response:
                logger.info(f"Sending response to {message.sender}: {response}")
                await self.meshcore.send_message(message.sender, response)

                # Store assistant response in memory
                await self.memory.add_message(
                    user_id=message.sender,
                    role="assistant",
                    content=response,
                    message_type=message.message_type,
                    timestamp=asyncio.get_event_loop().time(),
                )

            # Handle any additional actions
            if result.output.action:
                await self._handle_action(
                    result.output.action, result.output.action_data, message.sender
                )

            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error handling message: {error_msg}")

            # Check for common API errors and provide helpful messages
            if "status_code: 403" in error_msg or "Access denied" in error_msg:
                logger.error("API Access Denied - Check your API key and account status")
                logger.error("Make sure LLM_API_KEY is valid and has sufficient credits")
            elif "status_code: 401" in error_msg or "Unauthorized" in error_msg:
                logger.error("API Unauthorized - Check your LLM_API_KEY")
            elif "status_code: 429" in error_msg or "rate_limit" in error_msg:
                logger.error("API Rate Limit - Too many requests")

            # Send error response (in production mode)
            if not raise_errors:
                try:
                    await self.meshcore.send_message(
                        message.sender,
                        "Sorry, I encountered an error processing your message.",
                    )
                except:
                    pass

            # Re-raise in test mode
            if raise_errors:
                raise

            return False

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

        return status
