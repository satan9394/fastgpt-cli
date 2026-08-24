"""Configuration with semantics migrated from Go internal/config.

Precedence (lowest -> highest): built-in defaults < config file < environment variables.
API keys never land in the config file --- they are always read from env vars at runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ServerConfig:
    host: str = "localhost"
    port: int = 3000
    api_key: str = ""


@dataclass
class DefaultsConfig:
    model: str = "text-embedding-3-small"
    chunk_size: int = 500
    chunk_overlap: int = 50


@dataclass
class LoggingConfig:
    level: str = "info"
    file: str = ""


@dataclass
class ChatConfig:
    # api_key is never written to config; read from env at runtime.
    base_url: str = "https://opencode.ai/zen/go/v1"
    model: str = "mimo-v2.5"


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)

    def server_addr(self) -> str:
        return f"{self.server.host.rstrip('/')}:{self.server.port}"


def chat_api_key() -> str:
    """Read chat API key from env only (never from config file).

    Order: FASTGPT_CHAT_API_KEY, then OPENCODE_API_KEY. Empty string if unset.
    """
    for name in ("FASTGPT_CHAT_API_KEY", "OPENCODE_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    return ""


def defaults_path() -> Path:
    """Default config dir: ~/.fastgpt-cli/config.yaml, overridable by FASTGPT_CONFIG_DIR."""
    base = os.environ.get("FASTGPT_CONFIG_DIR")
    if base:
        return Path(base) / "config.yaml"
    return Path.home() / ".fastgpt-cli" / "config.yaml"


def from_env(cfg: Config) -> Config:
    """Apply FASTGPT_* environment overrides over a base config."""
    cfg = Config(
        server=ServerConfig(
            host=os.environ.get("FASTGPT_SERVER_HOST", cfg.server.host),
            port=_env_int("FASTGPT_SERVER_PORT", cfg.server.port),
            api_key=os.environ.get("FASTGPT_SERVER_API_KEY", cfg.server.api_key),
        ),
        defaults=DefaultsConfig(
            model=os.environ.get("FASTGPT_DEFAULTS_MODEL", cfg.defaults.model),
            chunk_size=_env_int("FASTGPT_DEFAULTS_CHUNK_SIZE", cfg.defaults.chunk_size),
            chunk_overlap=_env_int("FASTGPT_DEFAULTS_CHUNK_OVERLAP", cfg.defaults.chunk_overlap),
        ),
        logging=LoggingConfig(
            level=os.environ.get("FASTGPT_LOGGING_LEVEL", cfg.logging.level),
            file=os.environ.get("FASTGPT_LOGGING_FILE", cfg.logging.file),
        ),
        chat=ChatConfig(
            base_url=os.environ.get("FASTGPT_CHAT_BASE_URL", cfg.chat.base_url),
            model=os.environ.get("FASTGPT_CHAT_MODEL", cfg.chat.model),
        ),
    )
    return cfg


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load(explicit_path: str | None = None) -> tuple[Config, Path]:
    """Load config with default < file < env precedence.

    Returns (config, path). Missing file is not an error (defaults retained).
    """
    path = Path(explicit_path) if explicit_path else defaults_path()
    cfg = Config()

    if path.exists():
        try:
            data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            cfg = _apply_dict(cfg, data)
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"解析配置文件 {path} 失败: {exc}") from exc

    return from_env(cfg), path


def _apply_dict(cfg: Config, data: dict[str, Any]) -> Config:
    server = data.get("server") or {}
    defaults = data.get("defaults") or {}
    logging = data.get("logging") or {}
    chat = data.get("chat") or {}
    return Config(
        server=ServerConfig(
            host=server.get("host", cfg.server.host),
            port=server.get("port", cfg.server.port),
            api_key=server.get("api_key", cfg.server.api_key),
        ),
        defaults=DefaultsConfig(
            model=defaults.get("model", cfg.defaults.model),
            chunk_size=defaults.get("chunk_size", cfg.defaults.chunk_size),
            chunk_overlap=defaults.get("chunk_overlap", cfg.defaults.chunk_overlap),
        ),
        logging=LoggingConfig(
            level=logging.get("level", cfg.logging.level),
            file=logging.get("file", cfg.logging.file),
        ),
        chat=ChatConfig(
            base_url=chat.get("base_url", cfg.chat.base_url),
            model=chat.get("model", cfg.chat.model),
        ),
    )


def to_dict(cfg: Config) -> dict[str, Any]:
    """Serialize to a plain dict (API key excluded from file output)."""
    return {
        "server": {"host": cfg.server.host, "port": cfg.server.port},
        "defaults": {
            "model": cfg.defaults.model,
            "chunk_size": cfg.defaults.chunk_size,
            "chunk_overlap": cfg.defaults.chunk_overlap,
        },
        "logging": {"level": cfg.logging.level, "file": cfg.logging.file},
        "chat": {"base_url": cfg.chat.base_url, "model": cfg.chat.model},
    }


def save(cfg: Config, path: Path | str) -> None:
    """Atomically write config YAML (create parent dirs; tmp file + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(to_dict(cfg), allow_unicode=True), encoding="utf-8")
    tmp.replace(path)
