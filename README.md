# MeshBot - AI Agent for MeshCore Network

MeshBot is an intelligent AI agent that communicates through the MeshCore network using Pydantic AI as its framework. It maintains conversation history with users through simple text file logs and handles both direct messages and channel communications with automatic message length management for MeshCore's constraints.

## 🐳 Quick Start with Docker (Recommended)

The easiest way to run MeshBot is using our Docker image:

```bash
# Pull the latest image
docker pull ghcr.io/ipnet-mesh/meshbot:latest

# Run with mock connection (for testing)
docker run -it --rm \
  -e LLM_API_KEY=your_api_key_here \
  -e LLM_MODEL=openai:gpt-4o-mini \
  -e MESHCORE_CONNECTION_TYPE=mock \
  ghcr.io/ipnet-mesh/meshbot:latest

# Run with serial connection (real hardware)
docker run -it --rm \
  --device=/dev/ttyUSB0 \
  -v $(pwd)/logs:/app/logs \
  -e LLM_API_KEY=your_api_key_here \
  -e LLM_MODEL=openai:gpt-4o-mini \
  -e MESHCORE_CONNECTION_TYPE=serial \
  -e MESHCORE_PORT=/dev/ttyUSB0 \
  ghcr.io/ipnet-mesh/meshbot:latest

# Run with custom configuration via .env file
docker run -it --rm \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/ipnet-mesh/meshbot:latest
```

### Docker Environment Variables

All configuration is done via environment variables (see full list in [Configuration](#configuration)):

```bash
# Required
LLM_API_KEY=your_api_key_here
LLM_MODEL=openai:gpt-4o-mini

# MeshCore Connection
MESHCORE_CONNECTION_TYPE=mock  # or serial, tcp, ble
MESHCORE_PORT=/dev/ttyUSB0     # for serial
# MESHCORE_HOST=192.168.1.100  # for TCP

# Optional
LISTEN_CHANNEL=0
MAX_MESSAGE_LENGTH=120
LOG_LEVEL=INFO
```

### Docker Volumes

Mount volumes to persist logs and use custom prompts:

```bash
docker run -it --rm \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/my_prompt.txt:/app/custom_prompt.txt \
  -e CUSTOM_PROMPT_FILE=/app/custom_prompt.txt \
  --env-file .env \
  ghcr.io/ipnet-mesh/meshbot:latest
```

## Features

- **🤖 AI-Powered**: Built with Pydantic AI for structured, type-safe agent development
- **📡 MeshCore Integration**: Communicates via MeshCore network (serial, TCP, BLE, or mock)
- **🧠 Simple Memory System**: Text file-based chat logs (1000 lines per conversation)
- **💬 Smart Messaging**: Automatic message splitting with length limits (configurable, default 120 chars)
- **🔧 Rich Tool System**: Utility tools (calculator, time, bot status) and fun tools (dice, coin, 8-ball, random numbers)
- **🌐 Network Awareness**: Real-time tracking of mesh network events (adverts, contacts, paths, status)
- **👥 Contact Tracking**: Automatic node name discovery and mapping from mesh advertisements
- **📊 Situational Context**: Network events and node names included in LLM context for awareness
- **💰 Cost Control**: API request limits (max 5 per message) to prevent excessive LLM usage
- **⚙️ Configurable**: Flexible configuration via files and environment variables
- **🎯 Message Routing**: Intelligent DM and channel message handling with @NodeName mentions
- **🔌 OpenAI-Compatible**: Works with any OpenAI-compatible endpoint (OpenAI, Groq, Ollama, etc.)

## Alternative: Install from Source

For development or if you prefer not to use Docker:

### Installation

```bash
# Clone the repository
git clone https://github.com/ipnet-mesh/meshbot.git
cd meshbot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Run with mock connection (for testing)
meshbot test --meshcore-connection-type mock

# Run with serial connection
meshbot --meshcore-connection-type serial --meshcore-port /dev/ttyUSB0

# Run with custom prompt file
meshbot --custom-prompt my_prompt.txt --meshcore-connection-type mock
```

### Environment Variables

Create a `.env` file:

```bash
# LLM Configuration (OpenAI-compatible)
LLM_MODEL=openai:gpt-4o-mini
LLM_API_KEY=your_api_key_here
# LLM_BASE_URL=http://localhost:11434/v1  # For Ollama or other endpoints

# Bot Behavior
LISTEN_CHANNEL=0                # Channel to monitor
MAX_MESSAGE_LENGTH=120          # MeshCore message length limit
# MESHCORE_NODE_NAME=MeshBot    # Bot will respond to @MeshBot mentions

# MeshCore Configuration
MESHCORE_CONNECTION_TYPE=mock
# MESHCORE_PORT=/dev/ttyUSB0
# MESHCORE_HOST=192.168.1.100
# MESHCORE_BAUDRATE=115200

# Logging
LOG_LEVEL=INFO
```

### Using a Custom Prompt File

Create a custom prompt file (e.g., `my_prompt.txt`):

```
You are a helpful assistant for the mesh network.
You specialize in network troubleshooting and device management.
Always be concise and technical in your responses.
```

Run with the custom prompt:

```bash
# Via command line
meshbot --custom-prompt my_prompt.txt --meshcore-connection-type mock

# Via environment variable
export CUSTOM_PROMPT_FILE=my_prompt.txt
meshbot
```

## Architecture

### Core Components

1. **MeshCore Interface** (`meshcore_interface.py`)
   - Abstract interface for MeshCore communication
   - Mock implementation for testing
   - Real implementation using meshcore library
   - Auto clock sync and local advertisement on startup
   - Network event tracking (advertisements, contacts, paths, status)
   - Automatic node name discovery and mapping

2. **Memory Manager** (`memory.py`)
   - Simple text file-based chat logs
   - Separate logs for DMs and channels
   - Network event logs with timestamps
   - Node name mapping storage
   - Automatic trimming to configured limits
   - Format: `timestamp|role|content`

3. **AI Agent** (`agent.py`)
   - Pydantic AI agent with rich tool set
   - Utility tools (calculate, time, bot status)
   - Fun tools (dice, coin, random numbers, magic 8-ball)
   - Network/mesh tools (contact management, conversation history, node queries)
   - Structured responses with message splitting
   - API request limits (max 5 per message)
   - Network context injection for situational awareness
   - Dependency injection

4. **Configuration** (`config.py`)
   - Environment-based configuration
   - Command-line argument overrides
   - Validation

### Message Handling

#### Direct Messages (DMs)
- Bot **always** responds to direct messages
- Each user gets a separate conversation log in `logs/dm_{user_id}.txt`

#### Channel Messages
- Bot only responds when mentioned by node name (e.g., `@MeshBot`)
- Only monitors the configured listen channel (default: channel 0)
- Shared conversation log in `logs/channel.txt`
- Node name is set via `MESHCORE_NODE_NAME` environment variable

Example:
```
User: @MeshBot what's the weather?  → Bot responds
User: hello everyone                → Bot ignores (not mentioned)
```

#### Message Length Limits

MeshCore has character limits (default 120). MeshBot automatically:
- Splits long responses into multiple messages
- Breaks on word boundaries (never mid-word)
- Adds `(1/3)`, `(2/3)`, `(3/3)` indicators
- Adds 0.5s delay between chunks

Example:
```
Long response: "This is a very long message that exceeds the maximum allowed length..."

Sent as:
"This is a very long message that exceeds the (1/2)"
"maximum allowed length... (2/2)"
```

## Usage Examples

### Testing Mode

```bash
# Interactive testing with mock MeshCore
meshbot test --meshcore-connection-type mock

# The test command provides an interactive prompt:
# Enter messages to send (or 'quit' to exit)
# > Hello!
```

### Programmatic Usage

```python
import asyncio
from meshbot import MeshBotAgent
from pathlib import Path

async def main():
    # Create agent with custom prompt
    with open("my_prompt.txt") as f:
        custom_prompt = f.read()

    agent = MeshBotAgent(
        model="openai:gpt-4o-mini",
        meshcore_connection_type="mock",
        node_name="Assistant",  # Bot will respond to @Assistant mentions
        listen_channel="0",
        max_message_length=120,
        custom_prompt=custom_prompt
    )

    # Initialize and start
    await agent.initialize()
    await agent.start()

    # Send a message
    success = await agent.send_message("node1", "Hello!")

    # Keep running
    await asyncio.sleep(60)

    # Stop
    await agent.stop()

asyncio.run(main())
```

## Configuration

### LLM Providers

MeshBot works with any OpenAI-compatible API:

#### OpenAI
```bash
LLM_MODEL=openai:gpt-4o-mini
LLM_API_KEY=sk-...
```

#### Groq
```bash
LLM_MODEL=openai:llama-3.1-70b-versatile
LLM_API_KEY=gsk_...
LLM_BASE_URL=https://api.groq.com/openai/v1
```

#### Ollama (local)
```bash
LLM_MODEL=openai:llama2
LLM_BASE_URL=http://localhost:11434/v1
# No API key needed for local Ollama
```

### Message Behavior

```bash
# Node name - bot responds to @NodeName mentions in channels
MESHCORE_NODE_NAME=MeshBot

# Channel settings
LISTEN_CHANNEL=0              # Which channel to monitor

# Message length
MAX_MESSAGE_LENGTH=120        # Character limit per message chunk

# LoRa duty cycle compliance (prevents message loss)
MESHCORE_MESSAGE_DELAY=5.0    # Delay between message chunks (seconds)
MESHCORE_MESSAGE_RETRY=1      # Number of retry attempts for failed sends
```

**Note**: The `MESHCORE_MESSAGE_DELAY` setting is critical for reliable message delivery over LoRa. LoRa radios have duty cycle restrictions (e.g., 1% in Europe requires ~50 seconds of wait time after a 500ms transmission). The default 5.0 second delay provides a safe balance between speed and reliability. Reduce to 2-3 seconds for less restrictive regions (US), or increase to 7-10 seconds for very strict requirements.

## Chat Logs

Conversation history and network data are stored in simple text files:

```
logs/
├── channel.txt              # Channel conversation (all users)
├── dm_2369759a4926.txt     # Direct message with specific user
├── network_events.txt       # Network events (adverts, contacts, paths, status)
└── node_names.txt          # Node name mappings (pubkey -> friendly name)
```

### Conversation Log Format
```
1734567890.123|user|Hello, how are you?
1734567891.456|assistant|I'm doing well, thanks!
```

### Network Events Log Format
```
1734567890.123|ADVERT from 2369759a49261ac6 (NodeName)
1734567891.456|NEW_CONTACT 4a5b6c7d8e9f0123 (OtherNode)
1734567892.789|STATUS from 2369759a49261ac6 (NodeName)
```

### Node Names Mapping Format
```
2369759a49261ac6|NodeName|1734567890.123
4a5b6c7d8e9f0123|OtherNode|1734567891.456
```

Logs automatically:
- Trim to configured limits when exceeded (1000 for conversations, 100 for network events)
- Persist across restarts
- Include timestamps for all entries
- Network events and node names are included in LLM context for situational awareness
- Can be viewed/edited as plain text files

## AI Tools

The agent has access to three categories of built-in tools:

### Utility Tools
- **Calculate**: Perform mathematical calculations (e.g., "calculate 25 * 4 + 10")
- **Get Current Time**: Get the current date and time
- **Get Bot Status**: Check bot uptime and connection status

### Fun Tools
- **Roll Dice**: Roll dice with custom sides (e.g., "roll 2d6", "roll 1d20")
- **Flip Coin**: Flip a coin (heads or tails)
- **Random Number**: Generate random numbers in a range
- **Magic 8-Ball**: Ask the magic 8-ball for wisdom

### Network/Mesh Tools
- **Get Contacts**: List available MeshCore contacts with their names
- **Get Channel Messages**: Retrieve recent messages from a channel
- **Get User Messages**: Access recent private messages with a user
- **Get Node Info**: Get detailed information about a specific mesh node
- **List Nodes**: List all known nodes with optional filters
- **List Adverts**: Search advertisement history with filters

### Network Awareness
The agent automatically receives context about:
- **Recent Network Events**: Last 5 network events (adverts, new contacts, status responses)
- **Node Names**: Friendly names for all discovered nodes
- **Network Activity**: Timing and frequency of mesh network activity

When users ask questions, the agent can automatically use these tools and has awareness of the mesh network state.

## Development

### Project Structure

```
meshbot/
├── src/meshbot/
│   ├── __init__.py
│   ├── agent.py              # Main AI agent with message splitting
│   ├── meshcore_interface.py  # MeshCore communication
│   ├── memory.py             # Text file-based chat logs
│   ├── config.py            # Configuration management
│   └── main.py             # CLI entry point
├── logs/                     # Chat log files (auto-created)
├── tests/                   # Test suite
├── examples/               # Usage examples
├── CLAUDE.md / AGENTS.md   # Development guidelines
└── pyproject.toml          # Project configuration
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=meshbot --cov-report=html
```

### Code Quality

See `AGENTS.md` for full development workflow including:
- Pre-commit hooks (black, isort, mypy, flake8, bandit)
- Virtual environment setup
- Testing guidelines

## Production Deployment

### Docker Deployment (Recommended)

The recommended way to deploy MeshBot in production is using Docker:

#### Using Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  meshbot:
    image: ghcr.io/ipnet-mesh/meshbot:latest
    container_name: meshbot
    restart: unless-stopped
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0  # For serial connection
    volumes:
      - ./logs:/app/logs
      - ./custom_prompt.txt:/app/custom_prompt.txt:ro  # Optional
    environment:
      - LLM_MODEL=openai:gpt-4o-mini
      - LLM_API_KEY=${LLM_API_KEY}
      - MESHCORE_NODE_NAME=MeshBot
      - MESHCORE_CONNECTION_TYPE=serial
      - MESHCORE_PORT=/dev/ttyUSB0
      - MAX_MESSAGE_LENGTH=120
      - LOG_LEVEL=INFO
    # Optionally use env_file instead:
    # env_file:
    #   - .env
```

Run with:
```bash
# Create .env file with your secrets
echo "LLM_API_KEY=your_key_here" > .env

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Alternative: Direct Installation

For production use with real MeshCore hardware without Docker:

```bash
# Serial connection
meshbot --meshcore-connection-type serial --meshcore-port /dev/ttyUSB0

# TCP connection
meshbot --meshcore-connection-type tcp --meshcore-host 192.168.1.100

# BLE connection
meshbot --meshcore-connection-type ble --meshcore-address XX:XX:XX:XX:XX:XX
```

### Environment Setup

```bash
# Production environment variables
export LLM_MODEL=openai:gpt-4o-mini
export LLM_API_KEY=your_production_key
export MESHCORE_NODE_NAME=MeshBot
export MESHCORE_CONNECTION_TYPE=serial
export MESHCORE_PORT=/dev/ttyUSB0
export MAX_MESSAGE_LENGTH=120
export LOG_LEVEL=INFO
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated and dependencies installed
2. **MeshCore Connection**: Check port permissions (`sudo usermod -a -G dialout $USER`)
3. **API Keys**: Set `LLM_API_KEY` environment variable
4. **Long Messages**: Adjust `MAX_MESSAGE_LENGTH` if messages are too short/long
5. **Channel Not Responding**: Ensure messages mention the bot's node name (e.g., `@MeshBot`)

### Debug Mode

```bash
# Enable verbose logging
meshbot -vv --meshcore-connection-type mock

# Test with specific prompt
meshbot test --custom-prompt debug_prompt.txt -vv --meshcore-connection-type mock
```

### Viewing Logs

```bash
# View channel conversation
cat logs/channel.txt

# View DM with specific user
cat logs/dm_2369759a4926.txt

# View network events
cat logs/network_events.txt

# View node name mappings
cat logs/node_names.txt

# Watch logs in real-time
tail -f logs/channel.txt
tail -f logs/network_events.txt

# Monitor all activity
watch -n 1 'ls -lh logs/'
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run pre-commit hooks: `pre-commit run --all-files`
6. Submit a pull request

See `AGENTS.md` for detailed development guidelines.

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.

## Acknowledgments

- [Pydantic AI](https://ai.pydantic.dev/) - Agent framework
- [MeshCore](https://github.com/meshcore) - Network communication library
- [Click](https://click.palletsprojects.com/) - CLI framework
