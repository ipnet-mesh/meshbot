# MeshBot - AI Agent for MeshCore Network

MeshBot is an intelligent AI agent that communicates through the MeshCore network using Pydantic AI as its framework. It maintains conversation history with users, provides access to a local knowledge base, and can handle various types of interactions including ping requests, user queries, and command processing.

## Features

- **🤖 AI-Powered**: Built with Pydantic AI for structured, type-safe agent development
- **📡 MeshCore Integration**: Communicates via MeshCore network (serial, TCP, BLE, or mock)
- **🧠 Memory System**: Maintains conversation history and user preferences
- **📚 Knowledge Base**: Local text file search with optional vector embeddings
- **🔧 Tool System**: Extensible tools for searching, pinging, and user management
- **⚙️ Configurable**: Flexible configuration via files and environment variables
- **🎯 Message Routing**: Intelligent message handling with priority-based routing

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd meshbot

# Install in development mode
pip install -e .

# Install optional dependencies for knowledge base
pip install -e ".[knowledge]"
```

### Basic Usage

```bash
# Run with mock connection (for testing)
meshbot --meshcore-type mock --interactive

# Run with serial connection
meshbot --meshcore-type serial --meshcore-port /dev/ttyUSB0

# Run with custom model
meshbot --model openai:gpt-4o --meshcore-type mock
```

### Environment Variables

Create a `.env` file:

```bash
# AI Configuration
AI_MODEL=openai:gpt-4o-mini
OPENAI_API_KEY=your_api_key_here

# MeshCore Configuration
MESHCORE_CONNECTION_TYPE=mock
# MESHCORE_PORT=/dev/ttyUSB0
# MESHCORE_HOST=192.168.1.100
# MESHCORE_BAUDRATE=115200

# Storage Configuration
MEMORY_PATH=memory.json
KNOWLEDGE_DIR=knowledge

# Logging
LOG_LEVEL=INFO
```

## Architecture

### Core Components

1. **MeshCore Interface** (`meshcore_interface.py`)
   - Abstract interface for MeshCore communication
   - Mock implementation for testing
   - Real implementation using meshcore_py library

2. **Memory Manager** (`memory.py`)
   - User conversation history
   - Preference storage
   - Context management

3. **Knowledge Base** (`knowledge.py`)
   - Text file indexing and search
   - Optional vector embeddings
   - RAG capabilities

4. **AI Agent** (`agent.py`)
   - Pydantic AI agent with tools
   - Structured responses
   - Dependency injection

5. **Message Router** (`message_router.py`)
   - Priority-based message handling
   - Command parsing
   - Extensible handler system

6. **Configuration** (`config.py`)
   - Environment-based configuration
   - JSON file support
   - Validation

## Usage Examples

### Interactive Mode

```bash
meshbot --interactive
```

In interactive mode, you can:
- Send messages: `node1: Hello, how are you?`
- Check status: `status`
- List contacts: `contacts`
- Get help: `help`

### Programmatic Usage

```python
import asyncio
from meshbot import MeshBotAgent
from pathlib import Path

async def main():
    # Create agent
    agent = MeshBotAgent(
        model="openai:gpt-4o-mini",
        knowledge_dir=Path("knowledge"),
        meshcore_connection_type="mock"
    )
    
    # Initialize and start
    await agent.initialize()
    await agent.start()
    
    # Send a message
    success = await agent.send_message("node1", "Hello!")
    
    # Keep running
    await asyncio.sleep(10)
    
    # Stop
    await agent.stop()

asyncio.run(main())
```

## Knowledge Base

The knowledge base automatically indexes text files from the configured directory:

### Supported File Types
- `.txt` - Plain text
- `.md` - Markdown
- `.rst` - reStructuredText
- `.py` - Python code
- `.js` - JavaScript
- `.html` - HTML
- `.css` - CSS

### Search Capabilities

- **Keyword Search**: Fast text-based search
- **Vector Search**: Semantic search with sentence transformers (optional)
- **Contextual Results**: Excerpts with highlighting

### Example Knowledge Files

```
knowledge/
├── README.md
├── meshcore_basics.txt
├── getting_started.md
└── troubleshooting.txt
```

## Configuration

### Configuration File

Create `config.json`:

```json
{
  "meshcore": {
    "connection_type": "serial",
    "port": "/dev/ttyUSB0",
    "baudrate": 115200,
    "debug": false,
    "auto_reconnect": true
  },
  "ai": {
    "model": "openai:gpt-4o-mini",
    "max_tokens": 500,
    "temperature": 0.7
  },
  "memory": {
    "storage_path": "memory.json",
    "max_messages_per_user": 100,
    "cleanup_days": 30
  },
  "knowledge": {
    "knowledge_dir": "knowledge",
    "use_vectors": false,
    "max_search_results": 5
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

## Commands

### Built-in Commands

- `ping` - Test connectivity (responds with "pong")
- `help` - Show available commands and help information
- `search <query>` - Search knowledge base
- `contacts` - List available MeshCore contacts
- `info` - Get your user information and statistics
- `history` - Show recent conversation history
- `status` - Show bot status and statistics

### AI Tools

The agent has access to several tools:

- **Knowledge Search**: Search the local knowledge base
- **User Info**: Retrieve information about users
- **Ping Node**: Test connectivity to specific nodes
- **Get Contacts**: List available contacts
- **Conversation History**: Access recent messages

## Development

### Project Structure

```
meshbot/
├── src/meshbot/
│   ├── __init__.py
│   ├── agent.py              # Main AI agent
│   ├── meshcore_interface.py  # MeshCore communication
│   ├── memory.py             # User memory management
│   ├── knowledge.py          # Knowledge base system
│   ├── message_router.py     # Message handling
│   ├── config.py            # Configuration management
│   └── main.py             # CLI entry point
├── knowledge/               # Knowledge base files
├── tests/                   # Test suite
├── examples/               # Usage examples
└── pyproject.toml          # Project configuration
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=meshbot
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
```

## Production Deployment

### Real MeshCore Connection

For production use with real MeshCore hardware:

```bash
# Serial connection
meshbot --meshcore-type serial --meshcore-port /dev/ttyUSB0

# TCP connection
meshbot --meshcore-type tcp --meshcore-host 192.168.1.100

# BLE connection
meshbot --meshcore-type ble --meshcore-address XX:XX:XX:XX:XX:XX
```

### Environment Setup

```bash
# Production environment variables
export AI_MODEL=openai:gpt-4o-mini
export OPENAI_API_KEY=your_production_key
export MESHCORE_CONNECTION_TYPE=serial
export MESHCORE_PORT=/dev/ttyUSB0
export LOG_LEVEL=INFO
export MEMORY_PATH=/var/lib/meshbot/memory.json
export KNOWLEDGE_DIR=/etc/meshbot/knowledge
```

### Systemd Service

Create `/etc/systemd/system/meshbot.service`:

```ini
[Unit]
Description=MeshBot AI Agent
After=network.target

[Service]
Type=simple
User=meshbot
WorkingDirectory=/opt/meshbot
Environment=PYTHONPATH=/opt/meshbot/src
ExecStart=/opt/meshbot/venv/bin/meshbot --config /etc/meshbot/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed with `pip install -e ".[knowledge]"`
2. **MeshCore Connection**: Check port permissions and device availability
3. **API Keys**: Set `OPENAI_API_KEY` environment variable
4. **Memory File**: Ensure write permissions for memory file path
5. **Knowledge Base**: Verify knowledge directory exists and contains text files

### Debug Mode

```bash
# Enable debug logging
meshbot --log-level DEBUG

# Enable MeshCore debug
export MESHCORE_DEBUG=true
meshbot
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Pydantic AI](https://ai.pydantic.dev/) - Agent framework
- [MeshCore](https://github.com/meshcore) - Network communication library
- [Rich](https://rich.readthedocs.io/) - Terminal output
- [Click](https://click.palletsprojects.com/) - CLI framework