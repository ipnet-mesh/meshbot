"""MeshCore interface wrapper for communication with MeshCore devices."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Type of connection to MeshCore device."""

    SERIAL = "serial"
    TCP = "tcp"
    BLE = "ble"
    MOCK = "mock"


@dataclass
class MeshCoreMessage:
    """Represents a message from MeshCore network."""

    sender: str  # Public key or node identifier
    sender_name: Optional[str]  # Human-readable name if available
    content: str
    timestamp: float
    message_type: str = "direct"  # direct, channel, broadcast
    channel: Optional[str] = None  # Channel ID or name (for channel messages)


@dataclass
class MeshCoreContact:
    """Represents a contact in the MeshCore network."""

    public_key: str
    name: Optional[str] = None
    last_seen: Optional[float] = None
    is_online: bool = False


class MeshCoreInterface(ABC):
    """Abstract interface for MeshCore communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to MeshCore device."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from MeshCore device."""
        pass

    @abstractmethod
    async def send_message(self, destination: str, message: str) -> bool:
        """Send a message to a destination."""
        pass

    @abstractmethod
    async def get_contacts(self) -> List[MeshCoreContact]:
        """Get list of contacts."""
        pass

    @abstractmethod
    async def ping_node(self, destination: str) -> bool:
        """Ping a node to check connectivity."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to MeshCore device."""
        pass

    @abstractmethod
    async def sync_time(self) -> bool:
        """Sync companion node's clock to system time."""
        pass

    @abstractmethod
    async def send_local_advert(self) -> bool:
        """Send a local advertisement to announce presence."""
        pass


class MockMeshCoreInterface(MeshCoreInterface):
    """Mock implementation for testing and development."""

    def __init__(self):
        self._connected = False
        self._contacts: Dict[str, MeshCoreContact] = {
            "node1": MeshCoreContact(
                public_key="node1", name="TestNode1", is_online=True
            ),
            "node2": MeshCoreContact(
                public_key="node2", name="TestNode2", is_online=True
            ),
        }
        self._message_queue: asyncio.Queue[MeshCoreMessage] = asyncio.Queue()
        self._message_handlers: List[Callable[[MeshCoreMessage], Any]] = []

    async def connect(self) -> None:
        """Mock connection - just set connected flag."""
        logger.info("Mock: Connecting to MeshCore device")
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._connected = True
        logger.info("Mock: Connected to MeshCore device")

        # Start simulating incoming messages
        asyncio.create_task(self._simulate_messages())

    async def disconnect(self) -> None:
        """Mock disconnection."""
        logger.info("Mock: Disconnecting from MeshCore device")
        self._connected = False

    async def send_message(self, destination: str, message: str) -> bool:
        """Mock sending a message."""
        if not self._connected:
            logger.warning("Mock: Not connected, cannot send message")
            return False

        logger.info(f"Mock: Sending message to {destination}: {message}")
        await asyncio.sleep(0.05)  # Simulate send delay

        # Simulate a response for testing
        if message.lower() == "ping":
            await asyncio.sleep(0.5)
            response = MeshCoreMessage(
                sender=destination,
                sender_name=(
                    self._contacts.get(destination) or MeshCoreContact("")
                ).name,
                content="pong",
                timestamp=asyncio.get_event_loop().time(),
                message_type="direct",
            )
            await self._message_queue.put(response)

        return True

    async def get_contacts(self) -> List[MeshCoreContact]:
        """Get mock contacts."""
        if not self._connected:
            return []
        return list(self._contacts.values())

    async def ping_node(self, destination: str) -> bool:
        """Mock ping a node."""
        if not self._connected:
            return False

        logger.info(f"Mock: Pinging node {destination}")
        await asyncio.sleep(0.2)  # Simulate ping delay

        # Return True if node exists in contacts
        return destination in self._contacts

    async def sync_time(self) -> bool:
        """Mock sync companion node clock."""
        if not self._connected:
            return False

        logger.info("Mock: Syncing companion node clock to system time")
        await asyncio.sleep(0.1)
        return True

    async def send_local_advert(self) -> bool:
        """Mock send local advertisement."""
        if not self._connected:
            return False

        logger.info("Mock: Sending local advertisement")
        await asyncio.sleep(0.1)
        return True

    def is_connected(self) -> bool:
        """Check if mock connected."""
        return self._connected

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add a handler for incoming messages."""
        self._message_handlers.append(handler)

    async def _simulate_messages(self) -> None:
        """Simulate incoming messages for testing."""
        while self._connected:
            try:
                # Wait for a message or timeout
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)

                # Call all registered handlers
                for handler in self._message_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")

            except asyncio.TimeoutError:
                # No message, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in message simulation: {e}")
                break


class RealMeshCoreInterface(MeshCoreInterface):
    """Real implementation using meshcore_py library."""

    def __init__(self, connection_type: ConnectionType, **kwargs):
        self.connection_type = connection_type
        self.connection_params = kwargs
        self._meshcore = None
        self._connected = False
        self._message_handlers: List[Callable[[MeshCoreMessage], Any]] = []

    async def connect(self) -> None:
        """Connect to real MeshCore device."""
        try:
            from meshcore import (  # type: ignore
                BLEConnection,
                EventType,
                MeshCore,
                SerialConnection,
                TCPConnection,
            )

            # Create appropriate connection
            if self.connection_type == ConnectionType.SERIAL:
                connection = SerialConnection(
                    self.connection_params["port"],
                    self.connection_params.get("baudrate", 115200),
                )
            elif self.connection_type == ConnectionType.TCP:
                connection = TCPConnection(
                    self.connection_params["host"],
                    self.connection_params.get("port", 12345),
                )
            elif self.connection_type == ConnectionType.BLE:
                connection = BLEConnection(self.connection_params.get("address"))
            else:
                raise ValueError(f"Unsupported connection type: {self.connection_type}")

            # Create MeshCore instance
            self._meshcore = MeshCore(
                connection,
                debug=self.connection_params.get("debug", False),
                auto_reconnect=self.connection_params.get("auto_reconnect", True),
            )

            # Connect and start auto message fetching
            logger.info("Connecting to MeshCore...")
            await self._meshcore.connect()
            logger.info("Starting auto message fetching...")
            await self._meshcore.start_auto_message_fetching()

            # Set up message event subscriptions
            self._meshcore.subscribe(
                EventType.CONTACT_MSG_RECV, self._on_message_received
            )
            self._meshcore.subscribe(
                EventType.CHANNEL_MSG_RECV, self._on_message_received
            )

            self._connected = True
            logger.info(
                f"Connected to MeshCore device via {self.connection_type.value}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to MeshCore device: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from real MeshCore device."""
        if self._meshcore:
            try:
                await self._meshcore.stop_auto_message_fetching()
                await self._meshcore.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from MeshCore: {e}")
            finally:
                self._meshcore = None
                self._connected = False

    async def send_message(self, destination: str, message: str) -> bool:
        """Send message via real MeshCore.

        Args:
            destination: Either a channel ID (e.g., "0", "1") or a public key hex string
            message: The message to send

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self._connected or not self._meshcore:
            return False

        try:
            # Detect if destination is a channel (numeric string with 1-2 digits)
            # Channel IDs are typically 0-255
            if destination.isdigit() and len(destination) <= 3 and int(destination) < 256:
                # Send to channel
                channel_id = int(destination)
                logger.debug(f"Sending to channel {channel_id}")
                result = await self._meshcore.commands.send_chan_msg(channel_id, message)
            else:
                # Send direct message to contact (public key)
                logger.debug(f"Sending direct message to {destination[:16]}...")
                result = await self._meshcore.commands.send_msg(destination, message)

            return result is not None
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def get_contacts(self) -> List[MeshCoreContact]:
        """Get contacts from real MeshCore."""
        if not self._connected or not self._meshcore:
            return []

        try:
            await self._meshcore.ensure_contacts()
            contacts = []
            for contact_data in self._meshcore.contacts.values():
                contact = MeshCoreContact(
                    public_key=contact_data.get("public_key", ""),
                    name=contact_data.get("adv_name"),
                    is_online=True,  # Assume contacts in list are reachable
                )
                contacts.append(contact)
            return contacts
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            return []

    async def ping_node(self, destination: str) -> bool:
        """Ping node via real MeshCore."""
        if not self._connected or not self._meshcore:
            return False

        try:
            result = await self._meshcore.commands.ping(destination)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to ping node: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if real MeshCore is connected."""
        return bool(self._connected and self._meshcore and self._meshcore.is_connected)

    async def sync_time(self) -> bool:
        """Sync companion node's clock to system time."""
        if not self._connected or not self._meshcore:
            return False

        try:
            import time
            logger.info("Syncing companion node clock to system time...")
            current_time = int(time.time())
            result = await self._meshcore.commands.set_time(current_time)
            logger.info("Clock sync completed")
            return result is not None
        except Exception as e:
            logger.error(f"Failed to sync time: {e}")
            return False

    async def send_local_advert(self) -> bool:
        """Send a local advertisement to announce presence."""
        if not self._connected or not self._meshcore:
            return False

        try:
            logger.info("Sending local advertisement...")
            result = await self._meshcore.commands.send_advert(flood=False)
            logger.info("Local advertisement sent")
            return result is not None
        except Exception as e:
            logger.error(f"Failed to send local advert: {e}")
            return False

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add handler for incoming messages."""
        self._message_handlers.append(handler)

    async def _on_message_received(self, event) -> None:
        """Handle incoming message events."""
        try:
            payload = event.payload

            # Extract message fields from MeshCore event payload
            sender = payload.get("pubkey_prefix", "")
            content = payload.get("text", "")
            sender_timestamp = payload.get("sender_timestamp", 0)
            msg_type = payload.get("type", "PRIV")
            channel = payload.get("channel", "0")  # Extract channel ID

            # Map MeshCore message types to our types
            message_type = "direct" if msg_type == "PRIV" else "channel"

            message = MeshCoreMessage(
                sender=sender,
                sender_name=None,  # MeshCore doesn't provide name in message events
                content=content,
                timestamp=float(sender_timestamp) if sender_timestamp else asyncio.get_event_loop().time(),
                message_type=message_type,
                channel=str(channel) if channel is not None else None,
            )

            # Call all registered handlers
            for handler in self._message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing message event: {e}")


def create_meshcore_interface(
    connection_type: ConnectionType = ConnectionType.MOCK, **kwargs
) -> MeshCoreInterface:
    """Factory function to create appropriate MeshCore interface."""
    if connection_type == ConnectionType.MOCK:
        return MockMeshCoreInterface()
    else:
        return RealMeshCoreInterface(connection_type, **kwargs)
