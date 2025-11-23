"""Configuration management for MeshBot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class MeshCoreConfig:
    """Configuration for MeshCore connection."""

    connection_type: str = field(
        default_factory=lambda: os.getenv("MESHCORE_CONNECTION_TYPE", "mock")
    )
    node_name: Optional[str] = field(
        default_factory=lambda: os.getenv("MESHCORE_NODE_NAME", "MeshBot")
    )
    port: Optional[str] = field(default_factory=lambda: os.getenv("MESHCORE_PORT"))
    baudrate: int = field(
        default_factory=lambda: int(os.getenv("MESHCORE_BAUDRATE", "115200"))
    )
    host: Optional[str] = field(default_factory=lambda: os.getenv("MESHCORE_HOST"))
    address: Optional[str] = field(
        default_factory=lambda: os.getenv("MESHCORE_ADDRESS")
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("MESHCORE_DEBUG", "false").lower() == "true"
    )
    auto_reconnect: bool = field(
        default_factory=lambda: os.getenv("MESHCORE_AUTO_RECONNECT", "true").lower()
        == "true"
    )
    timeout: int = field(
        default_factory=lambda: int(os.getenv("MESHCORE_TIMEOUT", "30"))
    )


@dataclass
class AIConfig:
    """Configuration for AI model and LLM API."""

    model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
    )
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    base_url: Optional[str] = field(default_factory=lambda: os.getenv("LLM_BASE_URL"))
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("AI_MAX_TOKENS", "500"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("AI_TEMPERATURE", "0.7"))
    )
    listen_channel: str = field(
        default_factory=lambda: os.getenv("LISTEN_CHANNEL", "0")
    )
    max_message_length: int = field(
        default_factory=lambda: int(os.getenv("MAX_MESSAGE_LENGTH", "120"))
    )
    custom_prompt_file: Optional[Path] = field(default=None)

    def __post_init__(self) -> None:
        """Post-initialization to handle custom_prompt_file."""
        prompt_file_env = os.getenv("CUSTOM_PROMPT_FILE")
        if prompt_file_env and not self.custom_prompt_file:
            self.custom_prompt_file = Path(prompt_file_env)


@dataclass
class MemoryConfig:
    """Configuration for memory management."""

    storage_path: Path = field(
        default_factory=lambda: Path(os.getenv("MEMORY_PATH", "data/meshbot.db"))
    )


@dataclass
class WeatherConfig:
    """Configuration for weather service."""

    latitude: Optional[float] = field(
        default_factory=lambda: float(os.getenv("WEATHER_LATITUDE"))
        if os.getenv("WEATHER_LATITUDE")
        else None
    )
    longitude: Optional[float] = field(
        default_factory=lambda: float(os.getenv("WEATHER_LONGITUDE"))
        if os.getenv("WEATHER_LONGITUDE")
        else None
    )
    forecast_days: int = field(
        default_factory=lambda: int(os.getenv("WEATHER_FORECAST_DAYS", "3"))
    )
    max_messages_per_user: int = field(
        default_factory=lambda: int(os.getenv("MEMORY_MAX_MESSAGES", "100"))
    )
    cleanup_days: int = field(
        default_factory=lambda: int(os.getenv("MEMORY_CLEANUP_DAYS", "30"))
    )


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = field(
        default_factory=lambda: os.getenv(
            "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    file_path: Optional[Path] = None


@dataclass
class MeshBotConfig:
    """Main configuration for MeshBot."""

    meshcore: MeshCoreConfig = field(default_factory=MeshCoreConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_file(cls, config_path: Optional[Path]) -> "MeshBotConfig":
        """Load configuration from JSON file."""
        import json

        if not config_path or not config_path.exists():
            return cls()

        with open(str(config_path), "r") as f:
            data = json.load(f)

        return cls(
            meshcore=MeshCoreConfig(**data.get("meshcore", {})),
            ai=AIConfig(**data.get("ai", {})),
            memory=MemoryConfig(**data.get("memory", {})),
            logging=LoggingConfig(**data.get("logging", {})),
        )

    def to_file(self, config_path: Path) -> None:
        """Save configuration to JSON file."""
        import json

        data = {
            "meshcore": self.meshcore.__dict__,
            "ai": self.ai.__dict__,
            "memory": self.memory.__dict__,
            "logging": self.logging.__dict__,
        }

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(config_path), "w") as f:
            json.dump(data, f, indent=2)

    def validate(self) -> None:
        """Validate configuration."""
        # Validate MeshCore config
        if self.meshcore.connection_type == "serial" and not self.meshcore.port:
            raise ValueError("Serial connection requires port to be specified")

        if self.meshcore.connection_type == "tcp" and not self.meshcore.host:
            raise ValueError("TCP connection requires host to be specified")

        # Validate AI config - check if API key is needed
        # Most models require an API key unless using local Ollama without auth
        if self.ai.model.startswith("openai") and not self.ai.api_key:
            if not os.getenv("LLM_API_KEY"):
                raise ValueError(
                    "LLM API key required. Set LLM_API_KEY environment variable"
                )

        # Validate paths
        self.memory.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if self.logging.file_path:
            self.logging.file_path.parent.mkdir(parents=True, exist_ok=True)


def get_default_config() -> MeshBotConfig:
    """Get default configuration from environment variables."""
    return MeshBotConfig()


def load_config() -> MeshBotConfig:
    """Load configuration from environment variables.

    Configuration priority:
    1. Command-line arguments (handled by caller)
    2. Environment variables (loaded here)
    3. Default values (defined in dataclass field defaults)
    """
    config = get_default_config()
    config.validate()
    return config
