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
    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key/identifier."""
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

    def is_connected(self) -> bool:
        """Check if mock connected."""
        return self._connected

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add a handler for incoming messages."""
        self._message_handlers.append(handler)

    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key."""
        return self._own_public_key

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
        self._message_handlers: List[Callable[[MeshCoreMessage], Any]] = []

        # Network event logging
        self._network_events_path = Path("logs") / "network_events.txt"
        self._network_events_path.parent.mkdir(exist_ok=True)
        self._max_network_events = 100  # Keep last 100 events

        # Node names tracking
        self._node_names_path = Path("logs") / "node_names.txt"
        self._node_names_path.parent.mkdir(exist_ok=True)
        self._max_node_names = 1000  # Keep last 1000 name mappings

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

            # Get bot's own public key for message filtering
            try:
                self_info = self._meshcore.self_info
                if self_info and isinstance(self_info, dict):
                    self._own_public_key = self_info.get("public_key") or self_info.get(
                        "pubkey_prefix"
                    )
                    if self._own_public_key:
                        logger.info(f"Bot public key: {self._own_public_key[:16]}...")
                    else:
                        logger.warning(
                            "self_info does not contain public_key or pubkey_prefix"
                        )
                        self._own_public_key = None
                else:
                    logger.warning(
                        f"self_info returned unexpected type: {type(self_info)}"
                    )
                    self._own_public_key = None
            except Exception as e:
                logger.warning(f"Could not retrieve own public key: {e}")
                self._own_public_key = None

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
            if (
                destination.isdigit()
                and len(destination) <= 3
                and int(destination) < 256
            ):
                # Send to channel
                channel_id = int(destination)
                logger.debug(f"Sending to channel {channel_id}")
                result = await self._meshcore.commands.send_chan_msg(
                    channel_id, message
                )
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

    def add_message_handler(self, handler: Callable[[MeshCoreMessage], Any]) -> None:
        """Add handler for incoming messages."""
        self._message_handlers.append(handler)

    async def get_own_public_key(self) -> Optional[str]:
        """Get the bot's own public key."""
        return self._own_public_key

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
                timestamp=(
                    float(sender_timestamp)
                    if sender_timestamp
                    else asyncio.get_event_loop().time()
                ),
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

                # Update node name mapping if we have both
                if sender != "unknown" and name:
                    self._update_node_name(sender, name)

                # Try to get friendly name from our mapping
                friendly_name = (
                    self._get_node_name(sender) if sender != "unknown" else None
                )

                # If sender is still unknown, log the full payload for debugging
                if sender == "unknown":
                    logger.warning(
                        f"Could not extract sender from advertisement: {payload}"
                    )

                # Format event with friendly name if available
                sender_display = sender[:16] if sender != "unknown" else sender
                event_info = f"ADVERT from {sender_display}"
                if friendly_name:
                    event_info += f" ({friendly_name})"
            elif event_type == "new_contact":
                pubkey = (
                    payload.get("public_key")
                    or payload.get("pubkey_prefix")
                    or payload.get("pubkey")
                    or "unknown"
                )
                name = payload.get("adv_name", "") or payload.get("name", "")

                # Update node name mapping if we have both
                if pubkey != "unknown" and name:
                    self._update_node_name(pubkey, name)

                # Try to get friendly name from our mapping
                friendly_name = (
                    self._get_node_name(pubkey) if pubkey != "unknown" else None
                )

                # Format event with friendly name if available
                pubkey_display = pubkey[:16] if pubkey != "unknown" else pubkey
                event_info = f"NEW_CONTACT {pubkey_display}"
                if friendly_name:
                    event_info += f" ({friendly_name})"
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
                    self._get_node_name(from_node) if from_node != "unknown" else None
                )

                # Format event with friendly name if available
                from_node_display = (
                    from_node[:16] if from_node != "unknown" else from_node
                )
                event_info = f"STATUS from {from_node_display}"
                if friendly_name:
                    event_info += f" ({friendly_name})"

            # Log to file
            log_line = f"{timestamp}|{event_info}"

            # Append to file
            with open(self._network_events_path, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")

            # Trim file if too large
            try:
                with open(self._network_events_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) > self._max_network_events:
                    with open(self._network_events_path, "w", encoding="utf-8") as f:
                        f.writelines(lines[-self._max_network_events :])
            except:
                pass  # If trimming fails, just continue

            logger.debug(f"Network event logged: {event_info}")

        except Exception as e:
            logger.error(f"Error processing network event: {e}")

    def get_recent_network_events(self, limit: int = 10) -> List[str]:
        """Get recent network events for context."""
        try:
            if not self._network_events_path.exists():
                return []

            with open(self._network_events_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Get last N lines and format them
            recent = lines[-limit:]
            events = []
            for line in recent:
                try:
                    timestamp_str, event_info = line.strip().split("|", 1)
                    # Format timestamp to relative time
                    import time

                    timestamp = float(timestamp_str)
                    age_seconds = time.time() - timestamp
                    if age_seconds < 60:
                        time_ago = f"{int(age_seconds)}s ago"
                    elif age_seconds < 3600:
                        time_ago = f"{int(age_seconds/60)}m ago"
                    else:
                        time_ago = f"{int(age_seconds/3600)}h ago"

                    events.append(f"[{time_ago}] {event_info}")
                except:
                    continue

            return events

        except Exception as e:
            logger.error(f"Error getting network events: {e}")
            return []

    def _update_node_name(self, pubkey: str, name: str) -> None:
        """Update or add a node name mapping.

        Args:
            pubkey: The node's public key (can be full or prefix)
            name: The friendly name for the node
        """
        try:
            import time

            # Read existing mappings
            mappings = {}
            if self._node_names_path.exists():
                with open(self._node_names_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            parts = line.strip().split("|")
                            if len(parts) >= 2:
                                mappings[parts[0]] = {
                                    "name": parts[1],
                                    "timestamp": (
                                        float(parts[2]) if len(parts) > 2 else 0
                                    ),
                                }
                        except:
                            continue

            # Update or add mapping
            mappings[pubkey] = {"name": name, "timestamp": time.time()}

            # Write back (keeping only most recent entries)
            with open(self._node_names_path, "w", encoding="utf-8") as f:
                # Sort by timestamp, keep most recent
                sorted_mappings = sorted(
                    mappings.items(), key=lambda x: x[1]["timestamp"], reverse=True
                )
                for key, data in sorted_mappings[: self._max_node_names]:
                    f.write(f"{key}|{data['name']}|{data['timestamp']}\n")

            logger.debug(f"Updated node name: {pubkey[:16]}... -> {name}")

        except Exception as e:
            logger.error(f"Error updating node name: {e}")

    def _get_node_name(self, pubkey: str) -> Optional[str]:
        """Get a friendly name for a node by public key.

        Args:
            pubkey: The node's public key (can be full or prefix)

        Returns:
            The friendly name if found, None otherwise
        """
        try:
            if not self._node_names_path.exists():
                return None

            with open(self._node_names_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        parts = line.strip().split("|")
                        if len(parts) >= 2 and parts[0] == pubkey:
                            return parts[1]
                    except:
                        continue

            return None

        except Exception as e:
            logger.error(f"Error getting node name: {e}")
            return None

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
                    self._update_node_name(key_to_use, name)

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
