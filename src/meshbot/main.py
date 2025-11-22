"""Main entry point for MeshBot."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .agent import MeshBotAgent
from .config import MeshBotConfig, load_config

console = Console()


def setup_logging(config: MeshBotConfig) -> None:
    """Setup logging configuration."""
    level = getattr(logging, config.logging.level.upper())

    # Configure rich handler for console
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=config.logging.format,
        handlers=[console_handler],
        force=True,
    )

    # Add file handler if configured
    if config.logging.file_path:
        file_handler = logging.FileHandler(config.logging.file_path)
        file_handler.setFormatter(logging.Formatter(config.logging.format))
        logging.getLogger().addHandler(file_handler)


@click.group()
def cli() -> None:
    """MeshBot - AI Agent for MeshCore network communication."""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--model", "-m", help="AI model to use (e.g., openai:gpt-4o-mini)")
@click.option(
    "--meshcore-type",
    type=click.Choice(["mock", "serial", "tcp", "ble"]),
    help="MeshCore connection type",
)
@click.option("--meshcore-port", help="Serial port for MeshCore connection")
@click.option("--meshcore-host", help="TCP host for MeshCore connection")
@click.option(
    "--memory-path", type=click.Path(path_type=Path), help="Memory storage file path"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Logging level",
)
def run(
    config: Optional[Path],
    model: Optional[str],
    meshcore_type: Optional[str],
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    memory_path: Optional[Path],
    log_level: Optional[str],
) -> None:
    """Run the MeshBot agent (daemon mode)."""

    # Load configuration
    try:
        app_config = load_config(config)

        # Override with command line arguments
        if model:
            app_config.ai.model = model
        if meshcore_type:
            app_config.meshcore.connection_type = meshcore_type
        if meshcore_port:
            app_config.meshcore.port = meshcore_port
        if meshcore_host:
            app_config.meshcore.host = meshcore_host
        if memory_path:
            app_config.memory.storage_path = memory_path
        if log_level:
            app_config.logging.level = log_level

    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Setup logging
    setup_logging(app_config)
    logger = logging.getLogger(__name__)

    # Load custom prompt if provided
    custom_prompt = None
    if app_config.ai.custom_prompt_file and app_config.ai.custom_prompt_file.exists():
        try:
            with open(app_config.ai.custom_prompt_file, "r", encoding="utf-8") as f:
                custom_prompt = f.read().strip()
            logger.info(f"Loaded custom prompt from {app_config.ai.custom_prompt_file}")
        except Exception as e:
            logger.warning(f"Failed to load custom prompt: {e}")

    # Create and run agent
    agent = MeshBotAgent(
        model=app_config.ai.model,
        memory_path=app_config.memory.storage_path,
        meshcore_connection_type=app_config.meshcore.connection_type,
        activation_phrase=app_config.ai.activation_phrase,
        listen_channel=app_config.ai.listen_channel,
        custom_prompt=custom_prompt,
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
    try:
        # Initialize and start agent
        await agent.initialize()
        await agent.start()

        console.print("[green]✓ MeshBot started successfully![/green]")

        # Show status
        status = await agent.get_status()
        console.print(f"[blue]Model: {status['model']}[/blue]")
        console.print(
            f"[blue]MeshCore: {status['meshcore_type']} ({'Connected' if status['meshcore_connected'] else 'Disconnected'})[/blue]"
        )
        console.print("[blue]Running in daemon mode. Press Ctrl+C to stop.[/blue]")

        # Run indefinitely
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    finally:
        await agent.stop()
        console.print("[yellow]MeshBot stopped[/yellow]")


@cli.command()
@click.argument("from_id")
@click.argument("message")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--meshcore-type",
    type=click.Choice(["mock", "serial", "tcp", "ble"]),
    default="mock",
    help="MeshCore connection type (default: mock)",
)
@click.option("--meshcore-port", help="Serial port for MeshCore connection")
@click.option("--meshcore-host", help="TCP host for MeshCore connection")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def test(
    from_id: str,
    message: str,
    config: Optional[Path],
    meshcore_type: str,
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    log_level: str,
) -> None:
    """Send a test message simulating a message from FROM_ID.

    FROM_ID: The sender ID to simulate (e.g., 'node1', 'test_user')
    MESSAGE: The message content to send
    """

    # Load configuration
    try:
        app_config = load_config(config)

        # Override with command line arguments
        app_config.meshcore.connection_type = meshcore_type
        if meshcore_port:
            app_config.meshcore.port = meshcore_port
        if meshcore_host:
            app_config.meshcore.host = meshcore_host
        app_config.logging.level = log_level

    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Setup logging
    setup_logging(app_config)
    logger = logging.getLogger(__name__)

    # Load custom prompt if provided
    custom_prompt = None
    if app_config.ai.custom_prompt_file and app_config.ai.custom_prompt_file.exists():
        try:
            with open(app_config.ai.custom_prompt_file, "r", encoding="utf-8") as f:
                custom_prompt = f.read().strip()
            logger.info(f"Loaded custom prompt from {app_config.ai.custom_prompt_file}")
        except Exception as e:
            logger.warning(f"Failed to load custom prompt: {e}")

    # Create and run test
    async def run_test():
        """Run the test message."""
        from .meshcore_interface import ConnectionType, MeshCoreMessage

        # Create agent
        agent = MeshBotAgent(
            model=app_config.ai.model,
            memory_path=app_config.memory.storage_path,
            meshcore_connection_type=app_config.meshcore.connection_type,
            activation_phrase=app_config.ai.activation_phrase,
            listen_channel=app_config.ai.listen_channel,
            custom_prompt=custom_prompt,
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

            console.print("[green]✓ MeshBot started successfully![/green]")
            console.print(f"[blue]Simulating message from: {from_id}[/blue]")
            console.print(f"[blue]Message: {message}[/blue]\n")

            # Create simulated message
            simulated_message = MeshCoreMessage(
                sender=from_id,
                sender_name=from_id,
                content=message,
                timestamp=asyncio.get_event_loop().time(),
                message_type="direct",
            )

            # Process message through agent's handler
            await agent._handle_message(simulated_message)

            # Give it a moment to complete
            await asyncio.sleep(1)

            console.print("\n[green]✓ Test completed![/green]")

        finally:
            await agent.stop()

    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error running test: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
