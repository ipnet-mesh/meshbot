"""MeshCore interface wrapper for communication with MeshCore devices."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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

    @abstractmethod
    async def send_flood_advert(self) -> bool:
        """Send a flood advertisement to announce presence to all nodes."""
        pass

    @abstractmethod
    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add a message handler callback."""
        pass

    @abstractmethod
    async def set_node_name(self, name: str) -> bool:
        """Set the node's advertised name."""
        pass

    @abstractmethod
    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key/identifier."""
        pass

    @abstractmethod
    async def get_own_node_name(self) -> Optional[str]:
        """Get the bot's own node name (advertised name)."""
        pass

    @abstractmethod
    def get_recent_network_events(self, limit: int = 10) -> List[str]:
        """Get recent network events for context."""
        pass


class MockMeshCoreInterface(MeshCoreInterface):
    """Mock implementation for testing and development."""

    def __init__(self):
        self._connected = False
        self._own_public_key = "meshbot_mock_key"
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

    async def send_flood_advert(self) -> bool:
        """Mock send flood advertisement."""
        if not self._connected:
            return False

        logger.info("Mock: Sending flood advertisement")
        await asyncio.sleep(0.1)
        return True

    async def set_node_name(self, name: str) -> bool:
        """Mock set node name (does nothing)."""
        logger.info(f"Mock: Would set node name to: {name}")
        return True

    def is_connected(self) -> bool:
        """Check if mock connected."""
        return self._connected

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add a handler for incoming messages."""
        self._message_handlers.append(handler)

    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key."""
        return self._own_public_key

    async def get_own_node_name(self) -> Optional[str]:
        """Get the bot's own node name (mock returns None)."""
        return None  # Mock doesn't have a node name

    def get_recent_network_events(self, limit: int = 10) -> List[str]:
        """Get recent network events for context (mock returns empty)."""
        return []  # Mock doesn't track network events

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
        self._own_public_key: Optional[str] = None
        self._own_node_name: Optional[str] = None
        self._message_handlers: List[Callable[[MeshCoreMessage], Any]] = []

        # SQLite storage for network events and node names
        from .storage import MeshBotStorage

        db_path = Path("data")
        self._storage = MeshBotStorage(db_path)

    async def connect(self) -> None:
        """Connect to real MeshCore device."""
        try:
            # Initialize storage
            await self._storage.initialize()
            logger.info("Storage initialized for network events and node names")

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
            assert self._meshcore is not None

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

            # Set up network event subscriptions for situational awareness
            self._meshcore.subscribe(EventType.ADVERTISEMENT, self._on_network_event)
            self._meshcore.subscribe(EventType.NEW_CONTACT, self._on_network_event)
            self._meshcore.subscribe(EventType.PATH_UPDATE, self._on_network_event)
            self._meshcore.subscribe(
                EventType.NEIGHBOURS_RESPONSE, self._on_network_event
            )
            self._meshcore.subscribe(EventType.STATUS_RESPONSE, self._on_network_event)
            logger.info("Subscribed to network events for situational awareness")

            # Sync node names from contacts list (leverages automatic contact discovery)
            await self._sync_node_names_from_contacts()

            # Get bot's own public key and node name for message filtering
            try:
                self_info = self._meshcore.self_info
                logger.debug(f"self_info type: {type(self_info)}, value: {self_info}")

                # Handle different possible types of self_info
                if self_info is None:
                    logger.warning("self_info is None")
                    self._own_public_key = None
                    self._own_node_name = None
                elif isinstance(self_info, dict):
                    self._own_public_key = self_info.get("public_key") or self_info.get(
                        "pubkey_prefix"
                    )
                    self._own_node_name = self_info.get("adv_name")

                    if self._own_public_key:
                        logger.info(f"Bot public key: {self._own_public_key[:16]}...")
                    else:
                        logger.warning(
                            "self_info does not contain public_key or pubkey_prefix"
                        )
                        self._own_public_key = None

                    if self._own_node_name:
                        logger.info(f"Bot node name: {self._own_node_name}")
                    else:
                        logger.info("Bot node name not set (adv_name not in self_info)")
                elif hasattr(self_info, "__dict__"):
                    # Handle object with attributes
                    self._own_public_key = getattr(
                        self_info, "public_key", None
                    ) or getattr(self_info, "pubkey_prefix", None)
                    self._own_node_name = getattr(self_info, "adv_name", None)

                    if self._own_public_key:
                        logger.info(f"Bot public key: {self._own_public_key[:16]}...")
                    if self._own_node_name:
                        logger.info(f"Bot node name: {self._own_node_name}")
                else:
                    logger.warning(
                        f"self_info returned unexpected type: {type(self_info)}, value: {self_info}"
                    )
                    # Try to extract from string representation
                    if isinstance(self_info, str):
                        import re

                        pubkey_match = re.search(
                            r'public_key[\'":\s]*([a-fA-F0-9]+)', self_info
                        )
                        if pubkey_match:
                            self._own_public_key = pubkey_match.group(1)
                            logger.info(
                                f"Extracted public key from string: {self._own_public_key[:16] if self._own_public_key else 'None'}..."
                            )
                        else:
                            self._own_public_key = None
                    else:
                        self._own_public_key = None

                    self._own_node_name = None
            except Exception as e:
                logger.warning(f"Could not retrieve self info: {e}")
                self._own_public_key = None
                self._own_node_name = None

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
            logger.warning(
                f"Cannot send message - not connected (connected={self._connected}, meshcore={self._meshcore is not None})"
            )
            return False

        try:
            # Detect if destination is a channel (numeric string with 1-2 digits)
            # Channel IDs are typically 0-255
            if (
                destination.isdigit()
                and len(destination) <= 3
                and int(destination) < 256
            ):
                # Send to channel
                channel_id = int(destination)
                logger.debug(
                    f"Sending to channel {channel_id}: {message[:50]}{'...' if len(message) > 50 else ''}"
                )
                result = await self._meshcore.commands.send_chan_msg(
                    channel_id, message
                )
            else:
                # Send direct message to contact (public key)
                logger.debug(
                    f"Sending direct message to {destination[:16]}...: {message[:50]}{'...' if len(message) > 50 else ''}"
                )
                result = await self._meshcore.commands.send_msg(destination, message)

            if result is not None:
                logger.debug(f"Message sent successfully to {destination}")
                return True
            else:
                logger.warning(
                    f"Message send returned None (possible queue full or radio busy) - destination: {destination}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to send message to {destination}: {type(e).__name__}: {e}"
            )
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
        """Send status request to node (ping equivalent)."""
        if not self._connected or not self._meshcore:
            return False

        try:
            # MeshCore doesn't have a ping command, use send_statusreq instead
            result = await self._meshcore.commands.send_statusreq(destination)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to send status request: {e}")
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

    async def send_flood_advert(self) -> bool:
        """Send a flood advertisement to announce presence to all nodes."""
        if not self._connected or not self._meshcore:
            return False

        try:
            logger.info("Sending flood advertisement...")
            result = await self._meshcore.commands.send_advert(flood=True)
            logger.info("Flood advertisement sent")
            return result is not None
        except Exception as e:
            logger.error(f"Failed to send flood advert: {e}")
            return False

    async def set_node_name(self, name: str) -> bool:
        """Set the node's advertised name."""
        if not self._connected or not self._meshcore:
            return False

        try:
            logger.info(f"Setting node name to: {name}")
            result = await self._meshcore.commands.set_name(name)
            if result is not None:
                # Update our cached node name
                self._own_node_name = name
                logger.info(f"Node name set successfully to: {name}")
                return True
            else:
                logger.warning("set_name command returned None")
                return False
        except Exception as e:
            logger.error(f"Failed to set node name: {e}")
            return False

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add handler for incoming messages."""
        self._message_handlers.append(handler)

    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key."""
        return self._own_public_key

    async def get_own_node_name(self) -> Optional[str]:
        """Get the bot's own node name (advertised name)."""
        return self._own_node_name

    async def _on_message_received(self, event) -> None:
        """Handle incoming message events."""
        try:
            logger.debug(f"Message event received: {event}")
            payload = event.payload
            logger.debug(f"Message payload: {payload}")

            # Extract message fields from MeshCore event payload
            sender = payload.get("pubkey_prefix", "")
            content = payload.get("text", "")
            sender_timestamp = payload.get("sender_timestamp", 0)
            msg_type = payload.get("type", "PRIV")
            channel = payload.get("channel", "0")  # Extract channel ID

            logger.info(
                f"Processing message: sender={sender}, content='{content}', type={msg_type}, channel={channel}"
            )

            # Map MeshCore message types to our types
            message_type = "direct" if msg_type == "PRIV" else "channel"

            message = MeshCoreMessage(
                sender=sender,
                sender_name=None,  # MeshCore doesn't provide name in message events
                content=content,
                timestamp=(
                    float(sender_timestamp)
                    if sender_timestamp
                    else asyncio.get_event_loop().time()
                ),
                message_type=message_type,
                channel=str(channel) if channel is not None else None,
            )

            logger.info(f"Created MeshCoreMessage: {message}")
            logger.info(f"Calling {len(self._message_handlers)} message handlers")

            # Call all registered handlers
            for i, handler in enumerate(self._message_handlers):
                try:
                    logger.debug(f"Calling handler {i}: {handler}")
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                    logger.debug(f"Handler {i} completed successfully")
                except Exception as e:
                    logger.error(f"Error in message handler {i}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing message event: {e}", exc_info=True)

    async def _on_network_event(self, event) -> None:
        """Handle network events (adverts, contacts, paths, etc.) for situational awareness."""
        try:
            import time

            event_type = (
                event.type.value if hasattr(event.type, "value") else str(event.type)
            )
            payload = event.payload if hasattr(event, "payload") else {}

            # Debug: log the full payload structure to understand what fields are available
            logger.debug(f"Network event payload keys: {list(payload.keys())}")

            # Format event for logging
            timestamp = time.time()
            event_info = f"{event_type}"

            # Extract relevant info based on event type
            if event_type == "advertisement":
                # Try multiple possible field names for the sender
                sender = (
                    payload.get("pubkey_prefix")
                    or payload.get("public_key")
                    or payload.get("pubkey")
                    or payload.get("sender")
                    or payload.get("from")
                    or "unknown"
                )
                name = payload.get("adv_name", "") or payload.get("name", "")

                # If no name in payload, try to get it from contacts list
                # (contacts are auto-populated when adverts are received)
                if sender != "unknown" and not name and self._meshcore:
                    try:
                        await self._meshcore.ensure_contacts()
                        # Try to find contact by matching public_key
                        for contact_data in self._meshcore.contacts.values():
                            contact_pubkey = contact_data.get("public_key", "")
                            contact_prefix = contact_data.get("pubkey_prefix", "")
                            # Match by full key or prefix
                            if sender == contact_pubkey or sender == contact_prefix:
                                name = contact_data.get("adv_name", "")
                                if name:
                                    logger.debug(
                                        f"Found name '{name}' for {sender[:16]}... in contacts"
                                    )
                                break
                    except Exception as e:
                        logger.debug(f"Could not query contacts for name: {e}")

                # Log advertisement to dedicated adverts table
                if sender != "unknown":
                    signal_strength = payload.get("signal_strength")
                    details = f"ADVERT from {sender[:16]}"
                    if name:
                        details += f" ({name})"

                    await self._storage.add_advert(
                        node_id=sender,
                        node_name=name if name else None,
                        signal_strength=signal_strength,
                        details=details,
                        timestamp=timestamp,
                    )
                    logger.debug(f"Advertisement logged: {details}")
                    # Skip adding to network_events since it's in adverts table
                    return
                else:
                    logger.warning(
                        f"Could not extract sender from advertisement: {payload}"
                    )
                    event_info = "ADVERT from unknown"
            elif event_type == "new_contact":
                pubkey = (
                    payload.get("public_key")
                    or payload.get("pubkey_prefix")
                    or payload.get("pubkey")
                    or "unknown"
                )
                name = payload.get("adv_name", "") or payload.get("name", "")

                # Update node registry
                if pubkey != "unknown":
                    await self._storage.upsert_node(
                        pubkey=pubkey,
                        name=name if name else None,
                        is_online=True,
                        timestamp=timestamp,
                    )
                    # Also update legacy node_names for backward compatibility
                    if name:
                        await self._storage.update_node_name(pubkey, name)

                # Format event with name if available
                pubkey_display = pubkey[:16] if pubkey != "unknown" else pubkey
                event_info = f"NEW_CONTACT {pubkey_display}"
                if name:
                    event_info += f" ({name})"
            elif event_type == "path_update":
                dest = (
                    payload.get("destination")
                    or payload.get("dest")
                    or payload.get("to")
                    or "unknown"
                )
                hops = payload.get("hops", 0) or payload.get("hop_count", 0)
                event_info = f"PATH_UPDATE to {dest[:16] if dest != 'unknown' else dest} ({hops} hops)"
            elif event_type == "neighbours_response":
                count = len(
                    payload.get("neighbours", []) or payload.get("neighbors", [])
                )
                event_info = f"NEIGHBOURS {count} nodes"
            elif event_type == "status_response":
                from_node = (
                    payload.get("pubkey_prefix")
                    or payload.get("public_key")
                    or payload.get("from")
                    or "unknown"
                )

                # Try to get friendly name from our mapping
                friendly_name = (
                    await self._storage.get_node_name(from_node)
                    if from_node != "unknown"
                    else None
                )

                # Format event with friendly name if available
                from_node_display = (
                    from_node[:16] if from_node != "unknown" else from_node
                )
                event_info = f"STATUS from {from_node_display}"
                if friendly_name:
                    event_info += f" ({friendly_name})"

            # Log to database
            await self._storage.add_network_event(
                event_type=event_type.upper(),
                details=event_info,
                timestamp=timestamp,
            )

            logger.debug(f"Network event logged: {event_info}")

        except Exception as e:
            logger.error(f"Error processing network event: {e}")

    def get_recent_network_events(self, limit: int = 10) -> List[str]:
        """Get recent network events for context."""
        try:
            import asyncio

            # Get events from SQLite (this is a sync method calling async storage)
            # We need to handle this carefully
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, create a task
                # This is a workaround for calling async from sync
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._storage.get_recent_network_events(limit)  # type: ignore[arg-type]
                    )
                    events_data = future.result()  # type: ignore[assignment]
            else:
                events_data = asyncio.run(  # type: ignore[assignment]
                    self._storage.get_recent_network_events(limit)
                )

            # Format events for display
            events = []
            for event_data in reversed(events_data):  # type: ignore[call-overload]
                try:
                    timestamp = event_data["timestamp"]
                    event_info = event_data["details"]

                    # Format timestamp to relative time
                    import time

                    age_seconds = time.time() - timestamp
                    if age_seconds < 60:
                        time_ago = f"{int(age_seconds)}s ago"
                    elif age_seconds < 3600:
                        time_ago = f"{int(age_seconds/60)}m ago"
                    else:
                        time_ago = f"{int(age_seconds/3600)}h ago"

                    events.append(f"[{time_ago}] {event_info}")
                except Exception:
                    continue

            return events

        except Exception as e:
            logger.error(f"Error getting network events: {e}")
            return []

    async def _sync_node_names_from_contacts(self) -> None:
        """Sync node names from the contacts list.

        This helps populate names for nodes we've seen before but don't
        have names for yet, leveraging the automatic contact discovery.
        """
        try:
            if not self._connected or not self._meshcore:
                return

            await self._meshcore.ensure_contacts()

            for contact_data in self._meshcore.contacts.values():
                pubkey = contact_data.get("public_key", "")
                name = contact_data.get("adv_name", "")

                if pubkey and name:
                    # Use pubkey_prefix if available, otherwise full key
                    key_to_use = contact_data.get("pubkey_prefix", pubkey)
                    await self._storage.update_node_name(key_to_use, name)

            logger.debug("Synced node names from contacts list")

        except Exception as e:
            logger.error(f"Error syncing node names from contacts: {e}")


def create_meshcore_interface(
    connection_type: ConnectionType = ConnectionType.MOCK, **kwargs
) -> MeshCoreInterface:
    """Factory function to create appropriate MeshCore interface."""
    if connection_type == ConnectionType.MOCK:
        return MockMeshCoreInterface()
    else:
        return RealMeshCoreInterface(connection_type, **kwargs)
