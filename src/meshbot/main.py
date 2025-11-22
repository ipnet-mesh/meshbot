"""Main entry point for MeshBot."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .agent import MeshBotAgent
from .config import MeshBotConfig, load_config


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper())

    # Configure basic logging
    handlers = []

    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s')
    )
    handlers.append(console_handler)

    # File handler if configured
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    "--custom-prompt",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom prompt file",
)
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (-v for INFO, -vv for DEBUG)"
)
@click.option(
    "--log-file", type=click.Path(path_type=Path), help="Log file path"
)
def run(
    config: Optional[Path],
    model: Optional[str],
    meshcore_type: Optional[str],
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    memory_path: Optional[Path],
    custom_prompt: Optional[Path],
    verbose: int,
    log_file: Optional[Path],
) -> None:
    """Run the MeshBot agent (daemon mode)."""

    # Determine log level from verbosity
    if verbose >= 2:
        level = "DEBUG"
    elif verbose == 1:
        level = "INFO"
    else:
        level = "WARNING"

    # Setup logging first
    setup_logging(level, log_file)
    logger = logging.getLogger(__name__)

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
        if custom_prompt:
            app_config.ai.custom_prompt_file = custom_prompt

    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

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
        max_message_length=app_config.ai.max_message_length,
        custom_prompt=custom_prompt,
        base_url=app_config.ai.base_url,
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
    "--custom-prompt",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom prompt file",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for INFO, -vv for DEBUG)",
)
def test(
    from_id: str,
    message: str,
    config: Optional[Path],
    meshcore_type: str,
    meshcore_port: Optional[str],
    meshcore_host: Optional[str],
    custom_prompt: Optional[Path],
    verbose: int,
) -> None:
    """Send a test message simulating a message from FROM_ID.

    FROM_ID: The sender ID to simulate (e.g., 'node1', 'test_user')
    MESSAGE: The message content to send
    """

    # Determine log level from verbosity
    if verbose >= 2:
        level = "DEBUG"
    elif verbose == 1:
        level = "INFO"
    else:
        level = "WARNING"

    # Load configuration
    try:
        app_config = load_config(config)

        # Override with command line arguments
        app_config.meshcore.connection_type = meshcore_type
        if meshcore_port:
            app_config.meshcore.port = meshcore_port
        if meshcore_host:
            app_config.meshcore.host = meshcore_host
        if custom_prompt:
            app_config.ai.custom_prompt_file = custom_prompt
        app_config.logging.level = level

    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(level)
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
        import os
        from .meshcore_interface import ConnectionType, MeshCoreMessage

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
            memory_path=app_config.memory.storage_path,
            meshcore_connection_type=app_config.meshcore.connection_type,
            activation_phrase=app_config.ai.activation_phrase,
            listen_channel=app_config.ai.listen_channel,
            max_message_length=app_config.ai.max_message_length,
            custom_prompt=custom_prompt,
            base_url=app_config.ai.base_url,
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
                    timeout=30.0  # 30 second timeout
                )
            except asyncio.TimeoutError:
                logger.error("Message processing timed out after 30 seconds")
                logger.warning("This may indicate an API connectivity issue")
            except Exception as e:
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


if __name__ == "__main__":
    cli()
