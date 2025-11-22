"""Message handling and routing system for MeshBot."""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .meshcore_interface import MeshCoreMessage

logger = logging.getLogger(__name__)


@dataclass
class HandlerResult:
    """Result from a message handler."""

    handled: bool
    response: Optional[str] = None
    action: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None
    continue_processing: bool = True


class MessageHandler:
    """Base class for message handlers."""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority

    async def can_handle(self, message: MeshCoreMessage) -> bool:
        """Check if this handler can process the message."""
        return True

    async def handle(self, message: MeshCoreMessage) -> HandlerResult:
        """Handle the message and return result."""
        return HandlerResult(handled=False, continue_processing=True)


class PingHandler(MessageHandler):
    """Handler for ping/pong messages."""

    def __init__(self):
        super().__init__("ping", priority=100)  # High priority

    async def can_handle(self, message: MeshCoreMessage) -> bool:
        """Check if message is a ping."""
        content = message.content.strip().lower()
        return content in ["ping", "ping!", "🏓"]

    async def handle(self, message: MeshCoreMessage) -> HandlerResult:
        """Handle ping with pong."""
        logger.info(f"Responding to ping from {message.sender}")
        return HandlerResult(
            handled=True,
            response="pong",
            continue_processing=False,  # Don't process further
        )


class HelpHandler(MessageHandler):
    """Handler for help requests."""

    def __init__(self):
        super().__init__("help", priority=90)

    async def can_handle(self, message: MeshCoreMessage) -> bool:
        """Check if message is a help request."""
        content = message.content.strip().lower()
        return any(
            keyword in content for keyword in ["help", "commands", "?", "how to"]
        )

    async def handle(self, message: MeshCoreMessage) -> HandlerResult:
        """Handle help request."""
        help_text = """
🤖 MeshBot Help

Available commands:
• ping - Test connectivity (responds with "pong")
• help - Show this help message
• search <query> - Search knowledge base
• contacts - List available contacts
• info - Get your user information
• history - Show recent conversation

You can also just chat with me normally! I can answer questions and help with tasks using my knowledge base.
        """.strip()

        return HandlerResult(
            handled=True, response=help_text, continue_processing=False
        )


class StatusHandler(MessageHandler):
    """Handler for status requests."""

    def __init__(self, agent_instance):
        super().__init__("status", priority=80)
        self.agent = agent_instance

    async def can_handle(self, message: MeshCoreMessage) -> bool:
        """Check if message is a status request."""
        content = message.content.strip().lower()
        return any(keyword in content for keyword in ["status", "stats", "info bot"])

    async def handle(self, message: MeshCoreMessage) -> HandlerResult:
        """Handle status request."""
        try:
            status = await self.agent.get_status()

            status_text = f"""
📊 MeshBot Status
• Running: {"🟢 Yes" if status["running"] else "🔴 No"}
• Model: {status["model"]}
• MeshCore: {"🟢 Connected" if status["meshcore_connected"] else "🔴 Disconnected"}
• Connection Type: {status["meshcore_type"]}
            """.strip()

            if "memory" in status:
                mem = status["memory"]
                status_text += f"""
📈 Memory Stats
• Total Users: {mem["total_users"]}
• Total Messages: {mem["total_messages"]}
• Active (24h): {mem["active_users_24h"]}
                """.strip()

            if "knowledge" in status:
                kb = status["knowledge"]
                status_text += f"""
📚 Knowledge Base
• Files: {kb["total_files"]}
• Chunks: {kb["total_chunks"]}
• Directory: {kb["knowledge_directory"]}
                """.strip()

            return HandlerResult(
                handled=True, response=status_text.strip(), continue_processing=False
            )

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return HandlerResult(
                handled=True,
                response="Sorry, I couldn't retrieve my status right now.",
                continue_processing=False,
            )


class CommandHandler(MessageHandler):
    """Handler for structured commands."""

    def __init__(self):
        super().__init__("commands", priority=50)
        self.command_patterns = {
            r"^search\s+(.+)$": self._handle_search,
            r"^contacts?$": self._handle_contacts,
            r"^history\s*(\d*)$": self._handle_history,
            r"^ping\s+(\w+)$": self._handle_ping_node,
            r"^remember\s+(.+?)\s*=\s*(.+)$": self._handle_remember,
            r"^forget\s+(.+)$": self._handle_forget,
        }

    async def can_handle(self, message: MeshCoreMessage) -> bool:
        """Check if message matches any command pattern."""
        content = message.content.strip()
        for pattern in self.command_patterns:
            if re.match(pattern, content, re.IGNORECASE):
                return True
        return False

    async def handle(self, message: MeshCoreMessage) -> HandlerResult:
        """Handle structured commands."""
        content = message.content.strip()

        for pattern, handler in self.command_patterns.items():
            match = re.match(pattern, content, re.IGNORECASE)
            if match:
                try:
                    return await handler(message, match)
                except Exception as e:
                    logger.error(f"Error handling command {pattern}: {e}")
                    return HandlerResult(
                        handled=True,
                        response=f"Error executing command: {e}",
                        continue_processing=False,
                    )

        return HandlerResult(handled=False, continue_processing=True)

    async def _handle_search(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle search command."""
        query = match.group(1)
        return HandlerResult(
            handled=True,
            action="search",
            action_data={"query": query},
            continue_processing=False,
        )

    async def _handle_contacts(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle contacts command."""
        return HandlerResult(handled=True, action="contacts", continue_processing=False)

    async def _handle_history(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle history command."""
        limit = int(match.group(1)) if match.group(1) else 5
        return HandlerResult(
            handled=True,
            action="history",
            action_data={"limit": limit},
            continue_processing=False,
        )

    async def _handle_ping_node(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle ping node command."""
        destination = match.group(1)
        return HandlerResult(
            handled=True,
            action="ping_node",
            action_data={"destination": destination},
            continue_processing=False,
        )

    async def _handle_remember(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle remember command."""
        key = match.group(1).strip()
        value = match.group(2).strip()
        return HandlerResult(
            handled=True,
            action="remember",
            action_data={"key": key, "value": value},
            continue_processing=False,
        )

    async def _handle_forget(self, message: MeshCoreMessage, match) -> HandlerResult:
        """Handle forget command."""
        key = match.group(1).strip()
        return HandlerResult(
            handled=True,
            action="forget",
            action_data={"key": key},
            continue_processing=False,
        )


class MessageRouter:
    """Routes messages to appropriate handlers."""

    def __init__(self, agent_instance=None):
        self.handlers: List[MessageHandler] = []
        self.agent = agent_instance

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        self.register_handler(PingHandler())
        self.register_handler(HelpHandler())
        if self.agent:
            self.register_handler(StatusHandler(self.agent))
        self.register_handler(CommandHandler())

    def register_handler(self, handler: MessageHandler) -> None:
        """Register a message handler."""
        self.handlers.append(handler)
        # Sort by priority (higher priority first)
        self.handlers.sort(key=lambda h: h.priority, reverse=True)
        logger.info(
            f"Registered message handler: {handler.name} (priority: {handler.priority})"
        )

    def unregister_handler(self, handler_name: str) -> bool:
        """Unregister a handler by name."""
        for i, handler in enumerate(self.handlers):
            if handler.name == handler_name:
                del self.handlers[i]
                logger.info(f"Unregistered message handler: {handler_name}")
                return True
        return False

    async def route_message(self, message: MeshCoreMessage) -> HandlerResult:
        """Route a message through the handler chain."""
        logger.debug(f"Routing message from {message.sender}: {message.content}")

        for handler in self.handlers:
            try:
                if await handler.can_handle(message):
                    logger.debug(f"Handler {handler.name} can process message")
                    result = await handler.handle(message)

                    if result.handled:
                        logger.debug(f"Handler {handler.name} processed message")
                        if not result.continue_processing:
                            break
                    else:
                        logger.debug(f"Handler {handler.name} passed on message")

            except Exception as e:
                logger.error(f"Error in handler {handler.name}: {e}")
                continue

        # If no handler processed the message, return default result
        return HandlerResult(handled=False, continue_processing=True)

    def get_handler_info(self) -> List[Dict[str, Any]]:
        """Get information about registered handlers."""
        return [
            {
                "name": handler.name,
                "priority": handler.priority,
                "type": type(handler).__name__,
            }
            for handler in self.handlers
        ]
