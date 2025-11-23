# MeshBot Development Agents

This document outlines the development workflow and rules for the MeshBot project.

## Requirements

* MUST activate or create virtual environment at `.venv` in project root
* MUST install development dependencies with `pip install -e ".[dev]"`
* MUST install `pre-commit` and setup hooks with `pre-commit install`
* MUST run `pre-commit` checks before committing code
* MUST follow code quality standards (formatting, type checking, linting, security)

## 🚀 Quick Setup

```bash
# Clone and navigate
git clone https://github.com/ipnet-mesh/meshbot.git
cd meshbot

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## 📋 Development Rules

### 1. Virtual Environment (MANDATORY)
**ALWAYS activate the virtual environment before any development action:**

```bash
# From project root
source .venv/bin/activate
```

The virtual environment should be located at `.venv` in the project root.

### 2. Pre-commit Hooks (MANDATORY)
**ALWAYS run pre-commit before committing:**

```bash
# Run on all files
pre-commit run --all-files

# Or just run on staged files (after git add)
pre-commit run
```

### 3. Code Quality Standards

#### Formatting
```bash
# Format code
black src/ tests/ examples/

# Sort imports
isort src/ tests/ examples/
```

#### Type Checking
```bash
# Run type checking
mypy src/
```

#### Linting
```bash
# Run linting
flake8 src/ tests/ examples/
```

#### Security
```bash
# Run security checks
bandit -r src/
```

### 4. Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=meshbot --cov-report=html

# Run specific test file
pytest tests/test_basic.py -v
```

## 🏗️ Project Architecture

### Core Components

1. **MeshCore Interface** (`src/meshbot/meshcore_interface.py`)
   - Abstract communication layer
   - Mock implementation for testing
   - Real implementation using meshcore library
   - Auto clock sync and local advertisement on startup
   - **Node name configuration** - sets advertised name via `set_name()` command on startup (configurable via `MESHCORE_NODE_NAME`)
   - Event-based message handling (DMs and channels)
   - Network event tracking (ADVERTISEMENT, NEW_CONTACT, PATH_UPDATE, NEIGHBOURS_RESPONSE, STATUS_RESPONSE)
   - Automatic node name discovery from contacts
   - Node name mapping storage in SQLite database
   - Network events logged to SQLite database

2. **AI Agent** (`src/meshbot/agent.py`)
   - Pydantic AI agent with rich tool set
   - **Utility tools**: calculate, get_current_time, search_history, get_bot_status
   - **Fun tools**: roll_dice, flip_coin, random_number, magic_8ball
   - **Network/mesh tools**: status_request, get_contacts, get_user_info, get_conversation_history
   - **Query tools**: search_messages (for historical searches)
   - Dependency injection system
   - Structured responses
   - Automatic message splitting for MeshCore length limits
   - Smart message routing (DM vs channel)
   - **Smart activation** - responds to DMs and `@{node_name}` mentions in channels
   - Node name set on startup before sending local advertisement
   - API request limits (max 5 requests per message via UsageLimits)
   - Network context injection (last 5 network events included in prompts)
   - Graceful handling of usage limit errors

3. **Memory System** (`src/meshbot/memory.py` + `src/meshbot/storage.py`)
   - SQLite-based storage for all data
   - Single database file: `data/meshbot.db`
   - Three main tables: messages, network_events, node_names
   - Indexed for fast queries (conversation lookups, content search, event filtering)
   - Automatic connection management
   - Supports complex queries (time ranges, keyword search, filtering)
   - Persistent across restarts
   - Query tools for historical data access

4. **Configuration** (`src/meshbot/config.py`)
   - Environment variable support
   - Command-line argument overrides
   - Configuration priority: CLI args > env vars > defaults
   - Validation
   - OpenAI-compatible endpoint configuration
   - No config files - follows 12-factor app principles

### Dependencies

#### Core Dependencies
- `pydantic-ai-slim` - AI agent framework (without temporalio dependency)
- `pydantic` - Data validation
- `meshcore` - MeshCore communication library
- `python-dotenv` - Environment variables
- `click` - CLI framework

#### Development Dependencies
- `pytest` - Testing framework
- `pytest-asyncio` - Async testing
- `pytest-cov` - Coverage reporting
- `black` - Code formatting
- `mypy` - Type checking
- `isort` - Import sorting
- `flake8` - Linting
- `bandit` - Security checking
- `pre-commit` - Git hooks

## 🔄 Development Workflow

### 1. Setup (First Time)
```bash
# Clone repository
git clone https://github.com/ipnet-mesh/meshbot.git
cd meshbot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### 2. Development Cycle
```bash
# ALWAYS activate virtual environment first
source .venv/bin/activate

# Make your changes...
# Edit files in src/, tests/, examples/

# Run tests
pytest

# Run code quality checks
pre-commit run --all-files

# If everything passes, commit
git add .
git commit -m "Your commit message"
```

### 3. Testing Changes
```bash
# Run specific tests
pytest tests/test_basic.py::TestMemoryManager::test_user_memory_creation -v

# Run with coverage
pytest --cov=meshbot --cov-report=term-missing

# Run integration tests
pytest tests/ -k "integration" -v
```

### 4. Local Testing
```bash
# Test CLI with mock connection
meshbot test user1 "hello" --meshcore-type mock

# Test with custom prompt file
meshbot test user1 "hello" --custom-prompt my_prompt.txt --meshcore-type mock

# Test with custom node name
meshbot test user1 "hello" --node-name TestBot --meshcore-type mock

# Run with verbose logging
meshbot run -vv --meshcore-type mock

# Run with all options via command-line
meshbot run --node-name MyBot --meshcore-type serial --meshcore-port /dev/ttyUSB0

# Run examples
python examples/basic_usage.py
```

## 📁 Directory Structure

```
meshbot/
├── .venv/                 # Virtual environment (gitignored)
├── src/meshbot/           # Main package
│   ├── __init__.py
│   ├── agent.py           # Pydantic AI agent with query tools
│   ├── meshcore_interface.py  # MeshCore communication
│   ├── memory.py          # SQLite storage interface
│   ├── storage.py         # SQLite database layer
│   ├── config.py          # Configuration management
│   └── main.py           # CLI entry point
├── data/                  # Data directory (auto-created, gitignored)
│   └── meshbot.db        # SQLite database (messages, events, node names)
├── tests/                # Test suite
│   ├── test_basic.py
│   └── conftest.py       # pytest configuration
├── examples/              # Usage examples
│   └── basic_usage.py
├── .gitignore            # Git ignore rules
├── .env.example          # Environment template
├── .pre-commit-config.yaml # Pre-commit hooks
├── pyproject.toml        # Project configuration
├── README.md             # Project documentation
├── AGENTS.md             # This file
└── CLAUDE.md             # References AGENTS.md
```

## 🎯 Development Guidelines

### Code Style
- Use **Black** for formatting (88 character line length)
- Use **isort** for import sorting
- Follow **PEP 8** conventions
- Use **type hints** everywhere
- Write **docstrings** for all public functions/classes

### Testing
- Write **unit tests** for all components
- Use **pytest** fixtures for setup
- Test **async functions** properly
- Aim for **high coverage** (>90%)

### Git Workflow
- Use **feature branches** for new work
- Write **descriptive commit messages**
- Run **pre-commit hooks** before committing
- Create **pull requests** for review

### Documentation
- Update **README.md** for user-facing changes
- Update **AGENTS.md** for development changes
- Add **docstrings** for new functions
- Include **examples** for new features

## 🛠️ Common Development Tasks

### Adding New Tool to Agent
1. Add tool method in `src/meshbot/agent.py`
2. Use `@agent.tool` decorator
3. Add proper type hints and docstring
4. Write tests for the tool
5. Update documentation

Example:
```python
@self.agent.tool
async def my_tool(ctx: RunContext[MeshBotDependencies], param: str) -> str:
    """Description of what the tool does."""
    # Implementation here
    return "result"
```

### Implemented Tools

The agent currently has the following tools implemented in `src/meshbot/agent.py`:

**Utility Tools**:
- `calculate`: Perform mathematical calculations using Python's eval (safely)
- `get_current_time`: Return current date and time
- `search_history`: Search conversation history for keywords
- `get_bot_status`: Return bot uptime and connection status

**Fun Tools**:
- `roll_dice`: Roll dice with customizable sides (e.g., 2d6, 1d20)
- `flip_coin`: Flip a coin (heads or tails)
- `random_number`: Generate random number in a range
- `magic_8ball`: Ask the magic 8-ball for wisdom

**Network/Mesh Tools**:
- `status_request`: Send status request to a node (ping equivalent)
- `get_contacts`: List all MeshCore contacts with names
- `get_user_info`: Get user statistics from chat logs
- `get_conversation_history`: Retrieve recent messages with a user

**Query Tools** (Historical Data):
- `search_messages`: Search messages across all conversations
- `search_adverts`: Search advertisement history with filters (node_id, time range)
- `get_node_info`: Get detailed info about a specific mesh node (status, activity, stats)
- `list_nodes`: List all known nodes with filters (online_only, has_name)

### Network Awareness Features

The agent includes network situational awareness implemented in `src/meshbot/meshcore_interface.py`:

**Network Event Tracking**:
- Subscribes to: ADVERTISEMENT, NEW_CONTACT, PATH_UPDATE, NEIGHBOURS_RESPONSE, STATUS_RESPONSE
- Advertisements logged to dedicated `adverts` table
- Other events logged to `network_events` table
- Events indexed for fast queries by event type, node, and time
- Queryable via dedicated tool (`search_adverts`)

**Node Registry**:
- Central node registry in `nodes` table with comprehensive tracking
- Automatically updated when advertisements or contacts are received
- Tracks: name, online status, first/last seen, last advert time, total adverts
- Queryable via `get_node_info` and `list_nodes` tools
- Legacy `node_names` table maintained for backward compatibility

**LLM Context Integration** (`src/meshbot/agent.py`):
- No automatic injection of network stats into prompts (reduced token usage)
- Agent uses tools on-demand to query network information
- Historical queries available via dedicated query tools
- Provides network situational awareness through tool-based queries

**API Cost Control** (`src/meshbot/agent.py`):
- UsageLimits set to max 20 requests per message
- Graceful error handling for usage limit exceeded
- Prevents runaway API costs from excessive tool calling

### Adding New Configuration Option
1. Add field to appropriate config class in `src/meshbot/config.py`
2. Add environment variable loading with `os.getenv()`
3. Add validation in `validate()` method
4. Update `.env.example`
5. Update documentation

### Modifying Memory System
The memory system uses SQLite database storage in `data/meshbot.db`:
- **Messages table**: Stores all conversations (DMs and channels)
- **Adverts table**: Stores advertisement events (dedicated table for mesh adverts)
- **Nodes table**: Central node registry with comprehensive node information
- **Network events table**: Stores other network events (non-advertisements)
- **Node names table**: Legacy table for backward compatibility

**Schema** (see `src/meshbot/storage.py`):
- **Messages**: `id, timestamp, conversation_id, message_type, role, content, sender`
- **Adverts**: `id, timestamp, node_id, node_name, signal_strength, details`
- **Nodes**: `pubkey (PK), name, is_online, first_seen, last_seen, last_advert, total_adverts`
- **Network events**: `id, timestamp, event_type, node_id, node_name, details`
- **Node names**: `pubkey (PK), name, timestamp, updated_at` (legacy)

**Indexes**:
- Messages: conversation_id + timestamp, content (for search)
- Adverts: node_id + timestamp, timestamp
- Nodes: is_online + last_seen
- Network events: event_type + timestamp, node_id + timestamp
- All tables have automatic primary keys

**Key Methods** (see `src/meshbot/storage.py`):
- Adverts: `add_advert()`, `search_adverts()`, `get_recent_adverts()`
- Nodes: `upsert_node()`, `get_node()`, `list_nodes()`, `update_node_advert_count()`
- Network events: `add_network_event()`, `search_network_events()`
- Messages: `add_message()`, `get_conversation_messages()`, `search_messages()`

To modify:
1. Update `src/meshbot/storage.py` for schema changes
2. Update `src/meshbot/memory.py` for interface changes
3. Update `src/meshbot/meshcore_interface.py` for event handling
4. Update `src/meshbot/agent.py` for new tools
5. Add database migrations if changing schema
6. Update documentation if interface changes

## 🚨 Troubleshooting

### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall in development mode
pip install -e ".[dev]"
```

### Pre-commit Issues
```bash
# Reinstall pre-commit hooks
pre-commit uninstall
pre-commit install

# Run on all files to check current state
pre-commit run --all-files
```

### Test Failures
```bash
# Run with verbose output
pytest -v -s

# Run specific failing test
pytest tests/test_file.py::test_function -v -s
```

### Type Checking Errors
```bash
# Check specific file
mypy src/meshbot/module.py

# Ignore specific errors if necessary
mypy src/meshbot --ignore-missing-imports
```

## 📋 Pre-commit Configuration

The project uses these pre-commit hooks:
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Type checking
- **flake8** - Linting
- **bandit** - Security checking

## 🎊 Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Run pre-commit checks
5. Create git tag
6. Build and publish package

```bash
# Build package
python -m build

# Publish to PyPI (if needed)
python -m twine upload dist/*
```

## 📞 Getting Help

- Check the **README.md** for usage instructions
- Look at **examples/** for implementation patterns
- Review **tests/** for expected behavior
- Check **pyproject.toml** for dependency information
- Run `meshbot --help` for CLI options

Remember: **Always activate the virtual environment and run pre-commit hooks!** 🚀
