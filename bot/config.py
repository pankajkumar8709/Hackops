"""Bot configuration -- loads from environment variables."""
import os
from pathlib import Path

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


class BotConfig:
    """Discord bot configuration."""

    # Discord
    DISCORD_TOKEN: str = os.environ.get("DISCORD_TOKEN", "")
    DISCORD_CHANNEL_ID: int = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

    # Backend API
    BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://localhost:8000")

    # Bot behavior
    COMMAND_PREFIX: str = os.environ.get("BOT_COMMAND_PREFIX", "!")
    BOT_NAME: str = "Pulse"

    # Embed colors
    COLOR_INFO = 0x3498DB      # Blue
    COLOR_SUCCESS = 0x2ECC71   # Green
    COLOR_WARNING = 0xF39C12   # Orange
    COLOR_ERROR = 0xE74C3C     # Red
    COLOR_NEUTRAL = 0x95A5A6   # Gray


config = BotConfig()
