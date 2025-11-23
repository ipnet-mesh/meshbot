"""Main entry point for MeshBot."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .agent import MeshBotAgent
from .config import load_config


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Setup logging configuration."""
    # Add custom TRACE level if not already defined
    if not hasattr(logging, "TRACE"):
        logging.TRACE = 5  # type: ignore[attr-defined]
        logging.addLevelName(logging.TRACE, "TRACE")  # type: ignore[attr-defined]

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure basic logging
    handlers: list[logging.Handler] = []

    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    handlers.append(console_handler)

    # File handler if configured
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,
    )


@click.group()
def cli() -> None:
    """MeshBot - AI Agent for MeshCore network communication."""
    pass


@cli.command()
@click.option("--model", "-m", help="AI model to use (e.g., openai:gpt-4o-mini)")
@click.option("--listen-channel", help="Channel to listen to (e.g., 0 for General)")
@click.option(
    "--max-message-length", type=int, help="Maximum message length in characters"
)
@click.option(
    "--meshcore-type",
    type=click.Choice(["mock", "serial", "tcp", "ble"]),
    help="MeshCore connection type",
)
@click.option("--node-name", help="Node name to advertise on the mesh network")
@click.option("--meshcore-port", help="Serial port for MeshCore connection")
@click.option("--meshcore-host", help="TCP host for MeshCore connection")
@click.option("--meshcore-address", help="BLE address for MeshCore connection")
@click.option("--meshcore-baudrate", type=int, help="Serial baudrate (default: 115200)")
@click.option("--meshcore-debug", is_flag=True, help="Enable MeshCore debug logging")
@click.option(
    "--meshcore-auto-reconnect/--no-meshcore-auto-reconnect",
    default=None,
    help="Enable/disable MeshCore auto-reconnect",
)
@click.option("--meshcore-timeout", type=int, help="MeshCore timeout in seconds")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory path")
@click.option(
    "--custom-prompt",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom prompt file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for DEBUG, -vv for TRACE)",
)
@click.option("--log-file", type=click.Path(path_type=Path), help="Log file path")
def run(
    model: Optional[str],
    listen_channel: Optional[str],
    max_message_length: Optional[int],
    meshcore_type: Optional[str],
    node_name: Optional[str],
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    meshcore_address: Optional[str],
    meshcore_baudrate: Optional[int],
    meshcore_debug: bool,
    meshcore_auto_reconnect: Optional[bool],
    meshcore_timeout: Optional[int],
    data_dir: Optional[Path],
    custom_prompt: Optional[Path],
    verbose: int,
    log_file: Optional[Path],
) -> None:
    """Run the MeshBot agent (daemon mode)."""

    # Determine log level from verbosity
    if verbose >= 2:
        level = "TRACE"
    elif verbose == 1:
        level = "DEBUG"
    else:
        level = "INFO"

    # Setup logging first
    setup_logging(level, log_file)
    logger = logging.getLogger(__name__)

    # Load configuration from environment variables
    try:
        app_config = load_config()

        # Override with command line arguments (highest priority)
        # AI configuration
        if model:
            app_config.ai.model = model
        if listen_channel:
            app_config.ai.listen_channel = listen_channel
        if max_message_length:
            app_config.ai.max_message_length = max_message_length
        if custom_prompt:
            app_config.ai.custom_prompt_file = custom_prompt

        # MeshCore configuration
        if meshcore_type:
            app_config.meshcore.connection_type = meshcore_type
        if node_name:
            app_config.meshcore.node_name = node_name
        if meshcore_port:
            app_config.meshcore.port = meshcore_port
        if meshcore_host:
            app_config.meshcore.host = meshcore_host
        if meshcore_address:
            app_config.meshcore.address = meshcore_address
        if meshcore_baudrate:
            app_config.meshcore.baudrate = meshcore_baudrate
        if meshcore_debug:
            app_config.meshcore.debug = meshcore_debug
        if meshcore_auto_reconnect is not None:
            app_config.meshcore.auto_reconnect = meshcore_auto_reconnect
        if meshcore_timeout:
            app_config.meshcore.timeout = meshcore_timeout

        # Data directory configuration
        if data_dir:
            app_config.memory.storage_path = data_dir

    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Load custom prompt if provided
    custom_prompt_content: Optional[str] = None
    if app_config.ai.custom_prompt_file and app_config.ai.custom_prompt_file.exists():
        try:
            with open(app_config.ai.custom_prompt_file, "r", encoding="utf-8") as f:
                custom_prompt_content = f.read().strip()
            logger.info(f"Loaded custom prompt from {app_config.ai.custom_prompt_file}")
        except Exception as e:
            logger.warning(f"Failed to load custom prompt: {e}")

    # Create and run agent
    agent = MeshBotAgent(
        model=app_config.ai.model,
        data_dir=app_config.memory.storage_path,
        meshcore_connection_type=app_config.meshcore.connection_type,
        listen_channel=app_config.ai.listen_channel,
        max_message_length=app_config.ai.max_message_length,
        custom_prompt=custom_prompt_content,
        base_url=app_config.ai.base_url,
        node_name=app_config.meshcore.node_name,
        port=app_config.meshcore.port,
        baudrate=app_config.meshcore.baudrate,
        host=app_config.meshcore.host,
        address=app_config.meshcore.address,
        debug=app_config.meshcore.debug,
        auto_reconnect=app_config.meshcore.auto_reconnect,
        timeout=app_config.meshcore.timeout,
    )

    # Run the agent
    try:
        asyncio.run(run_agent(agent))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        sys.exit(1)


async def run_agent(agent: MeshBotAgent) -> None:
    """Run the agent in daemon mode."""
    logger = logging.getLogger(__name__)

    try:
        # Initialize and start agent
        await agent.initialize()
        await agent.start()

        logger.info("✓ MeshBot started successfully!")

        # Show status
        status = await agent.get_status()
        logger.info(f"Model: {status['model']}")
        logger.info(
            f"MeshCore: {status['meshcore_type']} ({'Connected' if status['meshcore_connected'] else 'Disconnected'})"
        )
        logger.info("Running in daemon mode. Press Ctrl+C to stop.")

        # Run indefinitely
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    finally:
        await agent.stop()
        logger.info("MeshBot stopped")


@cli.command()
@click.argument("from_id")
@click.argument("message")
@click.option("--model", "-m", help="AI model to use (e.g., openai:gpt-4o-mini)")
@click.option("--listen-channel", help="Channel to listen to (e.g., 0 for General)")
@click.option(
    "--max-message-length", type=int, help="Maximum message length in characters"
)
@click.option(
    "--meshcore-type",
    type=click.Choice(["mock", "serial", "tcp", "ble"]),
    default="mock",
    help="MeshCore connection type (default: mock)",
)
@click.option("--node-name", help="Node name to advertise on the mesh network")
@click.option("--meshcore-port", help="Serial port for MeshCore connection")
@click.option("--meshcore-host", help="TCP host for MeshCore connection")
@click.option("--meshcore-address", help="BLE address for MeshCore connection")
@click.option("--meshcore-baudrate", type=int, help="Serial baudrate (default: 115200)")
@click.option("--meshcore-debug", is_flag=True, help="Enable MeshCore debug logging")
@click.option(
    "--meshcore-auto-reconnect/--no-meshcore-auto-reconnect",
    default=None,
    help="Enable/disable MeshCore auto-reconnect",
)
@click.option("--meshcore-timeout", type=int, help="MeshCore timeout in seconds")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory path")
@click.option(
    "--custom-prompt",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom prompt file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for DEBUG, -vv for TRACE)",
)
def test(
    from_id: str,
    message: str,
    model: Optional[str],
    listen_channel: Optional[str],
    max_message_length: Optional[int],
    meshcore_type: str,
    node_name: Optional[str],
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    meshcore_address: Optional[str],
    meshcore_baudrate: Optional[int],
    meshcore_debug: bool,
    meshcore_auto_reconnect: Optional[bool],
    meshcore_timeout: Optional[int],
    data_dir: Optional[Path],
    custom_prompt: Optional[Path],
    verbose: int,
) -> None:
    """Send a test message simulating a message from FROM_ID.

    FROM_ID: The sender ID to simulate (e.g., 'node1', 'test_user')
    MESSAGE: The message content to send
    """

    # Determine log level from verbosity
    if verbose >= 2:
        level = "TRACE"
    elif verbose == 1:
        level = "DEBUG"
    else:
        level = "INFO"

    # Load configuration from environment variables
    try:
        app_config = load_config()

        # Override with command line arguments (highest priority)
        # AI configuration
        if model:
            app_config.ai.model = model
        if listen_channel:
            app_config.ai.listen_channel = listen_channel
        if max_message_length:
            app_config.ai.max_message_length = max_message_length
        if custom_prompt:
            app_config.ai.custom_prompt_file = custom_prompt

        # MeshCore configuration
        app_config.meshcore.connection_type = meshcore_type
        if node_name:
            app_config.meshcore.node_name = node_name
        if meshcore_port:
            app_config.meshcore.port = meshcore_port
        if meshcore_host:
            app_config.meshcore.host = meshcore_host
        if meshcore_address:
            app_config.meshcore.address = meshcore_address
        if meshcore_baudrate:
            app_config.meshcore.baudrate = meshcore_baudrate
        if meshcore_debug:
            app_config.meshcore.debug = meshcore_debug
        if meshcore_auto_reconnect is not None:
            app_config.meshcore.auto_reconnect = meshcore_auto_reconnect
        if meshcore_timeout:
            app_config.meshcore.timeout = meshcore_timeout

        # Data directory configuration
        if data_dir:
            app_config.memory.storage_path = data_dir

        # Logging configuration
        app_config.logging.level = level

    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(level)
    logger = logging.getLogger(__name__)

    # Load custom prompt if provided
    custom_prompt_content: Optional[str] = None
    if app_config.ai.custom_prompt_file and app_config.ai.custom_prompt_file.exists():
        try:
            with open(app_config.ai.custom_prompt_file, "r", encoding="utf-8") as f:
                custom_prompt_content = f.read().strip()
            logger.info(f"Loaded custom prompt from {app_config.ai.custom_prompt_file}")
        except Exception as e:
            logger.warning(f"Failed to load custom prompt: {e}")

    # Create and run test
    async def run_test():
        """Run the test message."""
        import os

        from .meshcore_interface import MeshCoreMessage

        # Check if API key is configured
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            logger.error("LLM_API_KEY environment variable not set!")
            logger.info("Please set your LLM API key:")
            logger.info("  export LLM_API_KEY='your-api-key-here'")
            logger.info("Or create a .env file with:")
            logger.info("  LLM_API_KEY=your-api-key-here")
            sys.exit(1)

        # Create agent
        agent = MeshBotAgent(
            model=app_config.ai.model,
            data_dir=app_config.memory.storage_path,
            meshcore_connection_type=app_config.meshcore.connection_type,
            listen_channel=app_config.ai.listen_channel,
            max_message_length=app_config.ai.max_message_length,
            custom_prompt=custom_prompt_content,
            base_url=app_config.ai.base_url,
            node_name=app_config.meshcore.node_name,
            port=app_config.meshcore.port,
            baudrate=app_config.meshcore.baudrate,
            host=app_config.meshcore.host,
            address=app_config.meshcore.address,
            debug=app_config.meshcore.debug,
            auto_reconnect=app_config.meshcore.auto_reconnect,
            timeout=app_config.meshcore.timeout,
        )

        try:
            # Initialize and start agent
            await agent.initialize()
            await agent.start()

            logger.info("✓ MeshBot started successfully!")
            logger.info(f"Simulating message from: {from_id}")
            logger.info(f"Message: {message}")

            # Create simulated message
            simulated_message = MeshCoreMessage(
                sender=from_id,
                sender_name=from_id,
                content=message,
                timestamp=asyncio.get_event_loop().time(),
                message_type="direct",
            )

            # Process message through agent's handler with timeout
            logger.info("Processing message (this may take a few seconds)...")
            success = False
            try:
                success = await asyncio.wait_for(
                    agent._handle_message(simulated_message, raise_errors=True),
                    timeout=30.0,  # 30 second timeout
                )
            except asyncio.TimeoutError:
                logger.error("Message processing timed out after 30 seconds")
                logger.warning("This may indicate an API connectivity issue")
            except Exception:
                # Error already logged by agent, just note it failed
                pass

            # Give it a moment for any async operations to complete
            await asyncio.sleep(0.5)

            if not success:
                logger.error("✗ Test failed - see errors above")
                logger.info("Common issues:")
                logger.info("  • Invalid or expired API key")
                logger.info("  • No credits on OpenAI account")
                logger.info("  • Network connectivity issues")
                logger.info("  • Model not accessible with your API key")
                return False
            else:
                logger.info("✓ Test completed successfully!")
                return True

        finally:
            await agent.stop()

    try:
        success = asyncio.run(run_test())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"Error running test: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--db-path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("data"),
    help="Path to data files (default: data/)",
)
@click.option(
    "--table",
    type=click.Choice(
        ["all", "messages", "adverts", "nodes", "network_events", "node_names"]
    ),
    default="all",
    help="Which table(s) to dump (default: all)",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    help="Maximum rows to display per table (default: 100)",
)
def dump(db_path: Path, table: str, limit: int) -> None:
    """Dump SQLite database contents in human-readable text format for debugging."""
    import sqlite3
    from datetime import datetime

    try:
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        click.echo(f"\n=== MeshBot Database Dump: {db_path} ===\n")

        # Determine which tables to dump
        tables_to_dump = []
        if table == "all":
            tables_to_dump = [
                "messages",
                "adverts",
                "nodes",
                "network_events",
                "node_names",
            ]
        else:
            tables_to_dump = [table]

        # Dump each table
        for table_name in tables_to_dump:
            click.echo(f"\n--- {table_name.upper()} ---")

            # Get row count
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            total_count = cursor.fetchone()["count"]
            click.echo(f"Total rows: {total_count}")

            if total_count == 0:
                click.echo("(empty)\n")
                continue

            # Fetch rows (some tables use different ordering)
            if table_name == "node_names":
                cursor.execute(
                    f"SELECT * FROM {table_name} ORDER BY timestamp DESC LIMIT {limit}"
                )
            elif table_name == "nodes":
                cursor.execute(
                    f"SELECT * FROM {table_name} ORDER BY last_seen DESC LIMIT {limit}"
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}"
                )
            rows = cursor.fetchall()

            if table_name == "messages":
                click.echo("\nFormat: [TIMESTAMP] CONV_ID (TYPE) ROLE: CONTENT")
                click.echo("-" * 80)
                for row in rows:
                    ts = datetime.fromtimestamp(row["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    conv_id = (
                        row["conversation_id"][:16] + "..."
                        if len(row["conversation_id"]) > 16
                        else row["conversation_id"]
                    )
                    msg_type = row["message_type"][:3].upper()  # DM/CHA
                    role = row["role"]
                    content = (
                        row["content"][:60] + "..."
                        if len(row["content"]) > 60
                        else row["content"]
                    )
                    click.echo(f"[{ts}] {conv_id} ({msg_type}) {role}: {content}")

            elif table_name == "adverts":
                click.echo("\nFormat: [TIMESTAMP] NODE_ID (NAME) DETAILS")
                click.echo("-" * 80)
                for row in rows:
                    ts = datetime.fromtimestamp(row["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    node_id = (
                        row["node_id"][:16] + "..."
                        if row["node_id"] and len(row["node_id"]) > 16
                        else row["node_id"] or "unknown"
                    )
                    node_name = f" ({row['node_name']})" if row["node_name"] else ""
                    details = row["details"] or ""
                    click.echo(f"[{ts}] {node_id}{node_name} {details}")

            elif table_name == "nodes":
                click.echo(
                    "\nFormat: PUBKEY (NAME) STATUS | FIRST_SEEN -> LAST_SEEN | ADVERTS"
                )
                click.echo("-" * 80)
                for row in rows:
                    pubkey = (
                        row["pubkey"][:16] + "..."
                        if len(row["pubkey"]) > 16
                        else row["pubkey"]
                    )
                    name = f" ({row['name']})" if row["name"] else ""
                    status = "🟢" if row["is_online"] else "🔴"
                    first_seen = datetime.fromtimestamp(row["first_seen"]).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    last_seen = datetime.fromtimestamp(row["last_seen"]).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    total_adverts = row["total_adverts"]
                    click.echo(
                        f"{pubkey}{name} {status} | {first_seen} -> {last_seen} | {total_adverts} adverts"
                    )

            elif table_name == "network_events":
                click.echo("\nFormat: [TIMESTAMP] TYPE: DETAILS")
                click.echo("-" * 80)
                for row in rows:
                    ts = datetime.fromtimestamp(row["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    event_type = row["event_type"]
                    details = row["details"] or ""
                    click.echo(f"[{ts}] {event_type}: {details}")

            elif table_name == "node_names":
                click.echo("\nFormat: PUBKEY -> NAME (UPDATED)")
                click.echo("-" * 80)
                for row in rows:
                    pubkey = (
                        row["pubkey"][:16] + "..."
                        if len(row["pubkey"]) > 16
                        else row["pubkey"]
                    )
                    name = row["name"]
                    ts = datetime.fromtimestamp(row["timestamp"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    click.echo(f"{pubkey} -> {name} (updated: {ts})")

            if total_count > limit:
                click.echo(f"\n(Showing latest {limit} of {total_count} rows)")

            click.echo()

        conn.close()
        click.echo("=== End of dump ===\n")

    except sqlite3.Error as e:
        click.echo(f"Error reading database: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
