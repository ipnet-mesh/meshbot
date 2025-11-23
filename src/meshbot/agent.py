"""Main Pydantic AI agent for MeshBot."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

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
        listen_channel: str = "0",
        custom_prompt: Optional[str] = None,
        base_url: Optional[str] = None,
        max_message_length: int = 120,
        node_name: Optional[str] = None,
        **meshcore_kwargs,
    ):
        self.model = model
        self.memory_path = memory_path
        self.meshcore_connection_type = meshcore_connection_type
        self.listen_channel = listen_channel
        self.custom_prompt = custom_prompt
        self.base_url = base_url
        self.max_message_length = max_message_length
        self.node_name = node_name
        self.meshcore_kwargs = meshcore_kwargs
        self._mention_name: Optional[
            str
        ] = None  # Will be set to @nodename after initialization

        # Initialize components (set via initialize())
        self._meshcore: Optional[MeshCoreInterface] = None
        self._memory: Optional[MemoryManager] = None
        self._agent: Optional[Agent[MeshBotDependencies, AgentResponse]] = None
        self._own_public_key: Optional[str] = None

        self._running = False

    @property
    def meshcore(self) -> MeshCoreInterface:
        """Get MeshCore interface, ensuring it's initialized."""
        if self._meshcore is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        return self._meshcore

    @property
    def memory(self) -> MemoryManager:
        """Get memory manager, ensuring it's initialized."""
        if self._memory is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        return self._memory

    @property
    def agent(self) -> Agent[MeshBotDependencies, AgentResponse]:
        """Get Pydantic AI agent, ensuring it's initialized."""
        if self._agent is None:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        return self._agent

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
        self._meshcore = create_meshcore_interface(
            connection_type, **self.meshcore_kwargs
        )

        # Initialize memory manager with file-based storage
        self._memory = MemoryManager(
            storage_path=self.memory_path or Path("data"),  # Data directory
            max_lines=1000,  # Max messages in conversation context
        )
        await self.memory.load()

        # Load system prompt from file
        data_dir = self.memory_path or Path("data")
        system_prompt_file = data_dir / "system_prompt.txt"

        # Create default system prompt if it doesn't exist
        if not system_prompt_file.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            default_prompt = (
                "You are MeshBot, an AI assistant that communicates through the MeshCore network. "
                "You are helpful, concise, and knowledgeable. "
                "MeshCore is a simple text messaging system with some limitations:\n"
                f"- Keep responses concise and clear (prefer under 200 chars, max {self.max_message_length})\n"
                "- Use newlines for better readability when helpful\n"
                "- NO emoji, but you CAN use basic punctuation like • — – for lists and separation\n"
                "- Use plain text with good structure\n"
                "- Be direct and helpful\n"
                "- Use tools ONLY when absolutely necessary - prefer direct responses\n"
                "- Maximum 1-2 tool calls per message, avoid chains\n"
                "- For simple questions, respond directly without tools\n"
                "- IMPORTANT: When calling weather API, make the HTTP request INSIDE the tool, don't call the tool repeatedly\n"
                "- CRITICAL: get_weather tool makes HTTP request automatically - call it ONCE only\n"
                "When users send 'ping', respond with 'pong'\n"
                "\n"
                "Examples of good formatting:\n"
                "Status: Connected • 20 contacts online • 51 messages processed\n"
                "Time: 14:30 • Date: 2025-01-15\n"
                "Result: Success • Data saved • Ready for next task\n"
                "Nodes found: 12 online • 8 with names • 4 new today\n"
            )
            with open(system_prompt_file, "w", encoding="utf-8") as f:
                f.write(default_prompt)
            logger.info(f"Created default system prompt: {system_prompt_file}")

        # Load system prompt from file
        try:
            with open(system_prompt_file, "r", encoding="utf-8") as f:
                base_instructions = f.read()
            logger.info(f"Loaded system prompt from: {system_prompt_file}")
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
            # Fall back to default
            base_instructions = "You are MeshBot, an AI assistant that communicates through the MeshCore network."

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
        self._agent = Agent(
            self.model,
            deps_type=MeshBotDependencies,
            output_type=AgentResponse,
            instructions=instructions,
            retries=0,  # Disable retries to reduce API calls
            end_strategy="early",  # Stop early when final result is found
        )

        # Register tools
        from .tools import register_all_tools

        register_all_tools(self.agent)

        # Set up message handler
        self.meshcore.add_message_handler(self._handle_message)

        logger.info("MeshBot agent initialized successfully")

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

        # Get bot's own public key for message filtering
        try:
            self._own_public_key = await self.meshcore.get_own_public_key()
            if self._own_public_key:
                logger.info(
                    f"Bot will filter out messages from self: {self._own_public_key[:16]}..."
                )
        except Exception as e:
            logger.warning(f"Could not retrieve own public key: {e}")

        # Set node name if configured (must be done BEFORE sending local advert)
        if self.node_name:
            try:
                logger.info(f"Setting node name to: {self.node_name}")
                success = await self.meshcore.set_node_name(self.node_name)
                if not success:
                    logger.warning("Failed to set node name")
            except Exception as e:
                logger.warning(f"Could not set node name: {e}")

        # Sync companion node clock (with timeout)
        try:
            logger.info("Syncing companion node clock...")
            await asyncio.wait_for(self.meshcore.sync_time(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Clock sync timed out after 5 seconds - continuing anyway")
        except Exception as e:
            logger.warning(f"Clock sync failed: {e}")

        # Send flood advertisement to announce presence to all nodes (after setting name)
        try:
            await self.meshcore.send_flood_advert()
        except Exception as e:
            logger.warning(f"Flood advert failed: {e}")

        # Get bot's own node name for @ mentions
        try:
            node_name = await self.meshcore.get_own_node_name()
            if node_name:
                # Use the node name with @ prefix for mention detection
                self._mention_name = f"@{node_name}".lower()
                logger.info(
                    f"Bot will respond to DMs and @ mentions of: {self._mention_name}"
                )
            else:
                logger.warning(
                    "Node name not set - bot will only respond to DMs, not channel mentions"
                )
        except Exception as e:
            logger.warning(f"Could not retrieve node name: {e}")
            logger.warning("Bot will only respond to DMs, not channel mentions")

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

    def _split_message(self, message: str) -> List[str]:
        """
        Split a long message into chunks that fit within max_message_length.
        Splits on word boundaries and adds (1/x) indicators.

        Args:
            message: The message to split

        Returns:
            List of message chunks
        """
        # Normalize whitespace but preserve intentional newlines for formatting
        # Replace multiple newlines with single ones, and clean up extra spaces
        lines = message.strip().split("\n")
        cleaned_lines = [" ".join(line.split()) for line in lines]
        message = "\n".join(cleaned_lines)

        # If message fits, return as-is
        if len(message) <= self.max_message_length:
            return [message]

        # Calculate how much space we need for " (X/Y)" suffix
        # Worst case: " (99/99)" = 8 chars
        suffix_space = 8
        chunk_size = self.max_message_length - suffix_space

        # Split into chunks on word boundaries
        words = message.split()
        chunks = []
        current_chunk: list[str] = []
        current_length = 0

        for word in words:
            word_length = len(word) + (1 if current_chunk else 0)  # +1 for space

            if current_length + word_length <= chunk_size:
                current_chunk.append(word)
                current_length += word_length
            else:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)

        # Add the last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Add (X/Y) indicators
        total = len(chunks)
        if total > 1:
            chunks = [f"{chunk} ({i+1}/{total})" for i, chunk in enumerate(chunks)]

        return chunks

    def _should_respond_to_message(self, message: MeshCoreMessage) -> bool:
        """
        Determine if the bot should respond to this message.

        Rules:
        - Never respond to messages from the bot itself
        - Always respond to DMs (direct messages)
        - For channel messages, only respond if:
          1. Message is on the configured listen_channel
          2. Message mentions the bot's node name (e.g., @NodeName)
        """
        logger.debug(
            f"Checking response for message: sender={message.sender}, type={message.message_type}, channel={getattr(message, 'channel', None)}, content='{message.content}'"
        )
        logger.debug(
            f"Bot config: own_key={self._own_public_key}, mention_name={self._mention_name}, listen_channel={self.listen_channel}"
        )

        # CRITICAL: Never respond to messages from the bot itself
        # This prevents infinite loops where the bot responds to its own messages
        if self._own_public_key and message.sender:
            # Check if sender matches our own public key (could be full key or prefix)
            if (
                message.sender == self._own_public_key
                or message.sender.startswith(self._own_public_key[:16])
                or self._own_public_key.startswith(message.sender)
            ):
                logger.debug(f"Ignoring message from self: {message.sender}")
                return False

        # Always respond to DMs
        if message.message_type == "direct":
            logger.debug("Direct message - will respond")
            return True

        # For channel messages, check channel and node name mention
        if message.message_type == "channel":
            # Check if it's the channel we're listening to
            # Handle both string channel names and numeric IDs
            message_channel = str(getattr(message, "channel", "0"))
            if message_channel != self.listen_channel:
                logger.debug(
                    f"Channel message not on listen channel {self.listen_channel}: {message_channel}"
                )
                return False

            # If we don't have a mention name (node name not set), don't respond to channel messages
            if not self._mention_name:
                logger.debug("No mention name set, ignoring channel message")
                return False

            # Check for node name mention (case-insensitive)
            # MeshCore wraps node names in brackets when tagged, so check both formats:
            # 1. @nodename (simple format)
            # 2. @[nodename] (MeshCore tagged format)
            content_lower = message.content.lower()
            mention_lower = self._mention_name.lower()

            logger.debug(
                f"Checking for mention: '{mention_lower}' in '{content_lower}'"
            )

            # Direct match
            if mention_lower in content_lower:
                logger.debug("Found direct mention - will respond")
                return True

            # Check for bracketed format: @[nodename]
            # Extract node name without @ prefix
            if mention_lower.startswith("@"):
                node_name = mention_lower[1:]  # Remove @ prefix
                bracketed_format = f"@[{node_name}]"
                if bracketed_format in content_lower:
                    logger.debug("Found bracketed mention - will respond")
                    return True

            logger.debug("No mention found - will not respond to channel message")
            return False

        # Default: don't respond to broadcast messages or unknown types
        logger.debug(f"Unknown message type {message.message_type} - will not respond")
        return False

    async def _handle_message(
        self, message: MeshCoreMessage, raise_errors: bool = False
    ) -> bool:
        """
        Handle incoming message.

        Args:
            message: The incoming message to handle
            raise_errors: If True, re-raise exceptions after logging (useful for testing)

        Returns:
            True if message was handled successfully, False otherwise
        """
        try:
            logger.info("=== MESSAGE RECEIVED ===")
            logger.info(f"From: {message.sender}")
            logger.info(f"Content: '{message.content}'")
            logger.info(f"Type: {message.message_type}")
            logger.info(f"Channel: {getattr(message, 'channel', None)}")
            logger.info(f"Timestamp: {message.timestamp}")

            # Check if we should respond to this message
            should_respond = self._should_respond_to_message(message)
            if not should_respond:
                logger.info("Message filtered out, not responding")
                return True  # Not an error, just filtered out

            # Determine conversation identifier
            # For channels: use channel as identifier
            # For DMs: use sender as identifier
            if message.message_type == "channel":
                conversation_id = message.channel or "0"
            else:
                conversation_id = message.sender

            # Store user message in memory
            await self.memory.add_message(
                user_id=conversation_id,
                role="user",
                content=message.content,
                message_type=message.message_type,
                timestamp=message.timestamp,
            )

            # Get conversation context
            context = await self.memory.get_conversation_context(
                user_id=conversation_id, message_type=message.message_type
            )

            # Create dependencies for this interaction
            deps = MeshBotDependencies(meshcore=self.meshcore, memory=self.memory)

            # Build the prompt with conversation history
            # Emphasize the current user message and reduce network event prominence

            if (
                context and len(context) > 1
            ):  # Only include history if there's more than just current message
                # Include only recent context to prevent confusion and tool-calling loops
                prompt = ""
                # for msg in context[:-1][-3:]:  # Last 3 messages only, excluding current
                #     role_name = "User" if msg["role"] == "user" else "Assistant"
                #     content = msg['content']
                #     # Truncate very long messages to keep prompt clean
                #     if len(content) > 100:
                #         content = content[:97] + "..."
                #     prompt += f"{role_name}: {content}\n"
                prompt += f"Current message: {message.content}\n"
                prompt += "Respond briefly and directly."
            else:
                # For first message, just use the message content
                prompt = message.content

            # Run agent with conversation context
            # Limit API requests to prevent excessive costs
            from pydantic_ai import UsageLimits

            usage_limits = UsageLimits(
                request_limit=20,  # Increased to 20 for more complex requests
            )

            # Log the full prompt being sent to LLM
            logger.info("=== SENDING PROMPT TO LLM ===")
            logger.info(f"Prompt: {prompt}")
            logger.info(f"Context length: {len(prompt)} characters")
            logger.info("=== END PROMPT ===")

            try:
                result = await self.agent.run(
                    prompt, deps=deps, usage_limits=usage_limits
                )
                logger.info("✅ LLM run completed successfully")
            except Exception as e:
                logger.error(f"❌ LLM run failed: {e}")
                raise

            # Send response
            response = result.output.response
            logger.info("=== LLM RESPONSE ===")
            logger.info(f"Raw response: {result}")
            logger.info(f"Response text: {response}")
            logger.info(f"Confidence: {result.output.confidence}")
            logger.info("=== END LLM RESPONSE ===")

            if response:
                # Determine destination based on message type
                if message.message_type == "channel":
                    # For channel messages, send back to the channel
                    destination = message.channel or "0"
                else:
                    # For DMs, send back to the sender
                    destination = message.sender

                # Split message if it's too long
                message_chunks = self._split_message(response)

                logger.info(
                    f"Sending {len(message_chunks)} message(s) to {destination}"
                )
                logger.info(f"Message chunks: {message_chunks}")

                # Send all chunks
                for i, chunk in enumerate(message_chunks):
                    logger.info(f"Sending chunk {i+1}/{len(message_chunks)}: {chunk}")
                    await self.meshcore.send_message(destination, chunk)

                    # Small delay between messages to avoid flooding
                    if i < len(message_chunks) - 1:
                        await asyncio.sleep(0.5)

                # Store assistant response in memory (original full response)
                # For channels, use channel as user_id; for DMs, use sender
                user_id = (
                    destination if message.message_type == "channel" else message.sender
                )
                await self.memory.add_message(
                    user_id=user_id,
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

            # Check for usage limit exceeded
            if "request_limit" in error_msg or "UsageLimit" in error_msg:
                logger.warning(
                    "API request limit reached - query too complex, simplifying response"
                )
                # Send a helpful message to the user
                try:
                    await self.meshcore.send_message(
                        message.sender,
                        "Sorry, that query is too complex. Please try a simpler question or break it into smaller parts.",
                    )
                    return True  # Handled gracefully
                except Exception:
                    pass

            # Check for common API errors and provide helpful messages
            if "status_code: 403" in error_msg or "Access denied" in error_msg:
                logger.error(
                    "API Access Denied - Check your API key and account status"
                )
                logger.error(
                    "Make sure LLM_API_KEY is valid and has sufficient credits"
                )
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
                except Exception:
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
                await self.memory.add_message(
                    user_id=destination,
                    role="assistant",
                    content=message,
                    message_type="direct",
                    timestamp=asyncio.get_event_loop().time(),
                )

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
