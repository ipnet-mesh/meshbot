# MeshBot Development Agents

This document outlines the development workflow and rules for the MeshBot project.

## 🚀 Quick Setup

```bash
# Clone and navigate
cd /home/user/data/dev/meshbot

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
   - Event-based message handling (DMs and channels)

2. **AI Agent** (`src/meshbot/agent.py`)
   - Pydantic AI agent with tools
   - Dependency injection system
   - Structured responses
   - Automatic message splitting for MeshCore length limits
   - Smart message routing (DM vs channel)

3. **Memory System** (`src/meshbot/memory.py`)
   - Simple text file-based chat logs
   - Separate logs for DMs and channels
   - Automatic trimming to 1000 lines per conversation
   - Format: `timestamp|role|content`
   - Persistent across restarts

4. **Configuration** (`src/meshbot/config.py`)
   - Environment variable support
   - JSON configuration files
   - Validation
   - OpenAI-compatible endpoint configuration

### Dependencies

#### Core Dependencies
- `pydantic-ai` - AI agent framework
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
git clone <repository-url>
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
# Test CLI with mock connection (interactive mode)
meshbot test --meshcore-type mock

# Test with custom prompt file
meshbot --custom-prompt my_prompt.txt --meshcore-type mock

# Test with custom configuration
meshbot --config test_config.json --meshcore-type mock

# Run with verbose logging
meshbot -vv --meshcore-type mock

# Run examples
python examples/basic_usage.py
```

## 📁 Directory Structure

```
meshbot/
├── .venv/                 # Virtual environment (gitignored)
├── src/meshbot/           # Main package
│   ├── __init__.py
│   ├── agent.py           # Pydantic AI agent with message splitting
│   ├── meshcore_interface.py  # MeshCore communication
│   ├── memory.py          # Text file-based chat logs
│   ├── config.py          # Configuration management
│   └── main.py           # CLI entry point
├── logs/                  # Chat log files (auto-created)
│   ├── channel.txt        # Channel conversation log
│   └── dm_*.txt          # Direct message logs per user
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

### Adding New Configuration Option
1. Add field to appropriate config class in `src/meshbot/config.py`
2. Add environment variable loading with `os.getenv()`
3. Add validation in `validate()` method
4. Update `.env.example`
5. Update documentation

### Modifying Memory System
The memory system uses simple text files in `logs/`:
- **Channel messages**: `logs/channel.txt`
- **Direct messages**: `logs/dm_{user_id}.txt`
- **Format**: `timestamp|role|content` (pipes in content are escaped to `│`)
- **Limit**: 1000 lines per file (auto-trimmed)

To modify:
1. Update `src/meshbot/memory.py`
2. Maintain backward compatibility with existing log files
3. Update documentation if format changes

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