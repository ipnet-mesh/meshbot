"""Main entry point for MeshBot."""

import asyncio
import logging
import signal
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


@click.command()
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
@click.option("--interactive", "-i", is_flag=True, help="Run in interactive mode")
def main(
    config: Optional[Path],
    model: Optional[str],
    meshcore_type: Optional[str],
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    memory_path: Optional[Path],
    log_level: Optional[str],
    interactive: bool,
) -> None:
    """MeshBot - AI Agent for MeshCore network communication."""

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

    # Create and run agent
    agent = MeshBotAgent(
        model=app_config.ai.model,
        memory_path=app_config.memory.storage_path,
        meshcore_connection_type=app_config.meshcore.connection_type,
        port=app_config.meshcore.port,
        baudrate=app_config.meshcore.baudrate,
        host=app_config.meshcore.host,
        address=app_config.meshcore.address,
        debug=app_config.meshcore.debug,
        auto_reconnect=app_config.meshcore.auto_reconnect,
        timeout=app_config.meshcore.timeout,
    )

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(agent.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the agent
    try:
        asyncio.run(run_agent(agent, interactive))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        sys.exit(1)


async def run_agent(agent: MeshBotAgent, interactive: bool) -> None:
    """Run the agent with optional interactive mode."""
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

        if interactive:
            await interactive_mode(agent)
        else:
            # Run indefinitely
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

    finally:
        await agent.stop()
        console.print("[yellow]MeshBot stopped[/yellow]")


async def interactive_mode(agent: MeshBotAgent) -> None:
    """Interactive mode for testing and debugging."""
    console.print("\n[bold]Interactive Mode[/bold]")
    console.print("Available commands:")
    console.print("  • Type a message to send (format: <destination>: <message>)")
    console.print("  • 'status' - Show agent status")
    console.print("  • 'contacts' - List available contacts")
    console.print("  • 'quit' or 'exit' - Exit interactive mode")
    console.print("  • 'help' - Show this help")
    console.print()

    while True:
        try:
            command = console.input("[bold cyan]meshbot> [/bold cyan]").strip()

            if not command:
                continue

            if command.lower() in ["quit", "exit"]:
                break
            elif command.lower() == "help":
                console.print("Interactive mode commands:")
                console.print("  • <destination>: <message> - Send message")
                console.print("  • status - Show status")
                console.print("  • contacts - List contacts")
                console.print("  • quit/exit - Exit")
            elif command.lower() == "status":
                status = await agent.get_status()
                console.print(f"[green]Status:[/green] {status}")
            elif command.lower() == "contacts":
                if agent.meshcore:
                    contacts = await agent.meshcore.get_contacts()
                    if contacts:
                        console.print("[green]Available contacts:[/green]")
                        for contact in contacts:
                            name = contact.name or contact.public_key[:8] + "..."
                            console.print(f"  • {name} ({contact.public_key[:16]}...)")
                    else:
                        console.print("[yellow]No contacts available[/yellow]")
                else:
                    console.print("[red]MeshCore not connected[/red]")
            elif ":" in command:
                # Send message
                destination, message = command.split(":", 1)
                destination = destination.strip()
                message = message.strip()

                if destination and message:
                    success = await agent.send_message(destination, message)
                    if success:
                        console.print(f"[green]✓ Message sent to {destination}[/green]")
                    else:
                        console.print(
                            f"[red]✗ Failed to send message to {destination}[/red]"
                        )
                else:
                    console.print(
                        "[red]Invalid format. Use: <destination>: <message>[/red]"
                    )
            else:
                console.print(
                    "[red]Unknown command. Type 'help' for available commands.[/red]"
                )

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    console.print("[yellow]Exiting interactive mode[/yellow]")


if __name__ == "__main__":
    main()
