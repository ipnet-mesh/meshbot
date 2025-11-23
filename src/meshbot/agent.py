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
        self._mention_name: Optional[str] = None  # Will be set to @nodename after initialization

        # Initialize components
        self.meshcore: Optional[MeshCoreInterface] = None
        self.memory: Optional[MemoryManager] = None
        self.agent: Optional[Agent[MeshBotDependencies, AgentResponse]] = None
        self._own_public_key: Optional[str] = None

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

        # Initialize memory manager with file-based chat logs
        self.memory = MemoryManager(
            storage_path=self.memory_path
            or Path("logs"),  # Not used, kept for compatibility
            max_lines=1000,  # Keep last 1000 lines per log file
        )
        await self.memory.load()

        # Build agent instructions
        base_instructions = (
            "You are MeshBot, an AI assistant that communicates through the MeshCore network. "
            "You are helpful, concise, and knowledgeable. "
            "MeshCore is a simple text messaging system with strict limitations:\n"
            f"- Keep responses SHORT and TO THE POINT (max {self.max_message_length} chars)\n"
            "- NO emoji, NO newlines, NO complex formatting\n"
            "- Use plain text only\n"
            "- Be direct and clear\n"
            "- If you need to say more, keep it brief anyway\n"
            "- IMPORTANT: Use tools ONLY when absolutely necessary. For simple queries, respond directly.\n"
            "- NEVER call multiple tools for a single simple request.\n"
            "When users send 'ping', respond with 'pong'."
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
            retries=0,  # Disable retries to reduce API calls
            end_strategy="early",  # Stop early when final result is found
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

                info = f"User: {memory.get('user_name') or user_id}\n"
                info += f"Total messages: {memory.get('total_messages', 0)}\n"
                info += f"First seen: {memory.get('first_seen', 'Never')}\n"
                info += f"Last seen: {memory.get('last_seen', 'Never')}\n"

                return info
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
                return "Error retrieving user information."

        @self.agent.tool
        async def status_request(
            ctx: RunContext[MeshBotDependencies], destination: str
        ) -> str:
            """Send a status request to a MeshCore node (similar to ping)."""
            try:
                # Use send_statusreq instead of ping (which doesn't exist)
                # This will request status from the destination node
                success = await ctx.deps.meshcore.ping_node(destination)
                return f"Status request to {destination}: {'Success' if success else 'Failed'}"
            except Exception as e:
                logger.error(f"Error sending status request: {e}")
                return f"Status request to {destination} failed"

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
                    role = "User" if msg["role"] == "user" else "Assistant"
                    response += f"{role}: {msg['content']}\n"

                return response.strip()
            except Exception as e:
                logger.error(f"Error getting conversation history: {e}")
                return "Error retrieving conversation history."

        # Utility Tools
        @self.agent.tool
        async def calculate(
            ctx: RunContext[MeshBotDependencies], expression: str
        ) -> str:
            """Evaluate a mathematical expression safely.

            Args:
                expression: Math expression to evaluate (e.g., "2 + 2", "sqrt(16)", "pi * 2")

            Returns:
                Result of the calculation or error message
            """
            try:
                import math
                import re

                # Allow only safe characters (numbers, operators, math functions)
                if not re.match(r"^[0-9+\-*/()., a-z]+$", expression.lower()):
                    return (
                        "Invalid expression. Use only numbers and basic math operators."
                    )

                # Create safe namespace with math functions
                safe_dict = {
                    "abs": abs,
                    "round": round,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "pow": pow,
                    "sqrt": math.sqrt,
                    "pi": math.pi,
                    "e": math.e,
                    "sin": math.sin,
                    "cos": math.cos,
                    "tan": math.tan,
                    "log": math.log,
                    "log10": math.log10,
                    "ceil": math.ceil,
                    "floor": math.floor,
                }

                result = eval(expression, {"__builtins__": {}}, safe_dict)
                return f"{expression} = {result}"
            except ZeroDivisionError:
                return "Error: Division by zero"
            except Exception as e:
                logger.error(f"Calculation error: {e}")
                return f"Error calculating: {str(e)[:50]}"

        @self.agent.tool
        async def get_current_time(
            ctx: RunContext[MeshBotDependencies], format: str = "human"
        ) -> str:
            """Get current date and time.

            Args:
                format: Output format - "human" (readable), "unix" (timestamp), or "iso" (ISO 8601)

            Returns:
                Current time in requested format
            """
            try:
                from datetime import datetime

                now = datetime.now()

                if format == "unix":
                    return f"Unix timestamp: {int(now.timestamp())}"
                elif format == "iso":
                    return f"ISO 8601: {now.isoformat()}"
                else:  # human readable
                    return now.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.error(f"Error getting time: {e}")
                return "Error retrieving current time"

        @self.agent.tool
        async def search_history(
            ctx: RunContext[MeshBotDependencies],
            user_id: str,
            keyword: str,
            limit: int = 5,
        ) -> str:
            """Search conversation history for messages containing a keyword.

            Args:
                user_id: User/channel ID to search
                keyword: Keyword to search for (case-insensitive)
                limit: Maximum number of results to return

            Returns:
                Matching messages or no results message
            """
            try:
                # Get full history
                history = await ctx.deps.memory.get_conversation_history(
                    user_id, limit=100
                )

                if not history:
                    return f"No conversation history with {user_id}"

                # Search for keyword (case-insensitive)
                keyword_lower = keyword.lower()
                matches = [
                    msg for msg in history if keyword_lower in msg["content"].lower()
                ][:limit]

                if not matches:
                    return f"No messages found containing '{keyword}'"

                response = f"Found {len(matches)} message(s) with '{keyword}':\n"
                for msg in matches:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    content_preview = (
                        msg["content"][:60] + "..."
                        if len(msg["content"]) > 60
                        else msg["content"]
                    )
                    response += f"{role}: {content_preview}\n"

                return response.strip()
            except Exception as e:
                logger.error(f"Error searching history: {e}")
                return "Error searching conversation history"

        @self.agent.tool
        async def get_bot_status(ctx: RunContext[MeshBotDependencies]) -> str:
            """Get current bot status and statistics.

            Returns:
                Bot status information including uptime, memory stats, and connection status
            """
            try:
                # Get memory statistics
                memory_stats = await ctx.deps.memory.get_statistics()

                # Get connection status
                is_connected = ctx.deps.meshcore.is_connected()

                # Get contacts count
                contacts = await ctx.deps.meshcore.get_contacts()
                online_count = sum(1 for c in contacts if c.is_online)

                status = (
                    f"Bot Status:\n"
                    f"Connected: {'Yes' if is_connected else 'No'}\n"
                    f"Contacts: {online_count}/{len(contacts)} online\n"
                    f"Total messages: {memory_stats.get('total_messages', 0)}\n"
                    f"Users: {memory_stats.get('total_users', 0)}"
                )

                return status
            except Exception as e:
                logger.error(f"Error getting bot status: {e}")
                return "Error retrieving bot status"

        # Fun/Interactive Tools
        @self.agent.tool
        async def roll_dice(
            ctx: RunContext[MeshBotDependencies], count: int = 1, sides: int = 6
        ) -> str:
            """Roll dice and return the results.

            Args:
                count: Number of dice to roll (1-10)
                sides: Number of sides per die (2-100)

            Returns:
                Dice roll results
            """
            try:
                import random

                # Validate inputs
                if not 1 <= count <= 10:
                    return "Please roll between 1 and 10 dice"
                if not 2 <= sides <= 100:
                    return "Dice must have between 2 and 100 sides"

                rolls = [random.randint(1, sides) for _ in range(count)]
                total = sum(rolls)

                if count == 1:
                    return f"Rolled 1d{sides}: {rolls[0]}"
                else:
                    rolls_str = ", ".join(map(str, rolls))
                    return f"Rolled {count}d{sides}: [{rolls_str}] = {total}"
            except Exception as e:
                logger.error(f"Error rolling dice: {e}")
                return "Error rolling dice"

        @self.agent.tool
        async def flip_coin(ctx: RunContext[MeshBotDependencies]) -> str:
            """Flip a coin and return the result.

            Returns:
                Either "Heads" or "Tails"
            """
            try:
                import random

                result = random.choice(["Heads", "Tails"])
                return f"Coin flip: {result}"
            except Exception as e:
                logger.error(f"Error flipping coin: {e}")
                return "Error flipping coin"

        @self.agent.tool
        async def random_number(
            ctx: RunContext[MeshBotDependencies],
            min_value: int = 1,
            max_value: int = 100,
        ) -> str:
            """Generate a random number within a range.

            Args:
                min_value: Minimum value (inclusive)
                max_value: Maximum value (inclusive)

            Returns:
                Random number in the specified range
            """
            try:
                import random

                if min_value >= max_value:
                    return "Min value must be less than max value"

                if max_value - min_value > 1000000:
                    return "Range too large (max 1 million)"

                result = random.randint(min_value, max_value)
                return f"Random number ({min_value}-{max_value}): {result}"
            except Exception as e:
                logger.error(f"Error generating random number: {e}")
                return "Error generating random number"

        @self.agent.tool
        async def magic_8ball(
            ctx: RunContext[MeshBotDependencies], question: str
        ) -> str:
            """Ask the magic 8-ball a yes/no question.

            Args:
                question: Your yes/no question

            Returns:
                Magic 8-ball response
            """
            try:
                import random

                responses = [
                    # Positive
                    "It is certain",
                    "It is decidedly so",
                    "Without a doubt",
                    "Yes definitely",
                    "You may rely on it",
                    "As I see it, yes",
                    "Most likely",
                    "Outlook good",
                    "Yes",
                    "Signs point to yes",
                    # Non-committal
                    "Reply hazy, try again",
                    "Ask again later",
                    "Better not tell you now",
                    "Cannot predict now",
                    "Concentrate and ask again",
                    # Negative
                    "Don't count on it",
                    "My reply is no",
                    "My sources say no",
                    "Outlook not so good",
                    "Very doubtful",
                ]

                response = random.choice(responses)
                return f"🎱 {response}"
            except Exception as e:
                logger.error(f"Error with magic 8-ball: {e}")
                return "The magic 8-ball is cloudy"

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

        # Sync companion node clock
        try:
            await self.meshcore.sync_time()
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
            logger.warning(
                "Bot will only respond to DMs, not channel mentions"
            )

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
        # Remove any newlines and extra whitespace
        message = " ".join(message.split())

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
        current_chunk = []
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
            return True

        # For channel messages, check channel and node name mention
        if message.message_type == "channel":
            # Check if it's the channel we're listening to
            # Handle both string channel names and numeric IDs
            message_channel = str(getattr(message, "channel", "0"))
            if message_channel != self.listen_channel:
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

            # Direct match
            if mention_lower in content_lower:
                return True

            # Check for bracketed format: @[nodename]
            # Extract node name without @ prefix
            if mention_lower.startswith('@'):
                node_name = mention_lower[1:]  # Remove @ prefix
                bracketed_format = f"@[{node_name}]"
                if bracketed_format in content_lower:
                    return True

            return False

        # Default: don't respond to broadcast messages or unknown types
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
            logger.info(f"Received message from {message.sender}: {message.content}")

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

            # Build the prompt with conversation history and network context
            # Get recent network events for situational awareness
            network_events = self.meshcore.get_recent_network_events(limit=5)

            if (
                context and len(context) > 1
            ):  # Only include history if there's more than just current message
                # Include previous context in the prompt (excluding the message we just added)
                prompt = ""

                # Add network events if available
                if network_events:
                    prompt += "Recent Network Activity:\n"
                    for event in network_events:
                        prompt += f"  {event}\n"
                    prompt += "\n"

                prompt += "Conversation history:\n"
                for msg in context[:-1][-10:]:  # Last 10 messages, excluding current
                    role_name = "User" if msg["role"] == "user" else "Assistant"
                    prompt += f"{role_name}: {msg['content']}\n"
                prompt += f"\nUser: {message.content}\nAssistant:"
            else:
                # For first message, still include network events if available
                if network_events:
                    prompt = "Recent Network Activity:\n"
                    for event in network_events:
                        prompt += f"  {event}\n"
                    prompt += f"\nUser: {message.content}\nAssistant:"
                else:
                    prompt = message.content

            # Run agent with conversation context
            # Limit API requests to prevent excessive costs
            from pydantic_ai import UsageLimits

            usage_limits = UsageLimits(
                request_limit=5,  # Max 5 LLM requests per message (includes tool calls)
            )
            result = await self.agent.run(prompt, deps=deps, usage_limits=usage_limits)

            # Send response
            response = result.output.response
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

                # Send all chunks
                for i, chunk in enumerate(message_chunks):
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
                except:
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
