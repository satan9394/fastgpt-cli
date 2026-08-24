"""Tests for config semantics migrated from Go internal/config."""

from __future__ import annotations

from pathlib import Path

import yaml

from fastgptcli.config.settings import Config, from_env, load, save, to_dict


def test_defaults_load_with_no_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FASTGPT_CONFIG_DIR", str(tmp_path))
    cfg, path = load()
    assert cfg.server.host == "localhost"
    assert cfg.server.port == 3000
    assert cfg.defaults.model == "text-embedding-3-small"
    assert path == tmp_path / "config.yaml"


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("FASTGPT_SERVER_HOST", "10.0.0.5")
    monkeypatch.setenv("FASTGPT_SERVER_PORT", "8080")
    monkeypatch.setenv("FASTGPT_DEFAULTS_MODEL", "text-embedding-3-large")
    cfg = from_env(Config())
    assert cfg.server.host == "10.0.0.5"
    assert cfg.server.port == 8080
    assert cfg.defaults.model == "text-embedding-3-large"


def test_file_then_env_precedence(tmp_path: Path, monkeypatch):
    cfgfile = tmp_path / "config.yaml"
    cfgfile.write_text(
        yaml.safe_dump({"server": {"host": "fromfile", "port": 5000}}), encoding="utf-8"
    )
    monkeypatch.setenv("FASTGPT_CONFIG_DIR", str(tmp_path))
    # No env override: file wins over default.
    cfg, _ = load()
    assert cfg.server.host == "fromfile"
    # Env overrides file.
    monkeypatch.setenv("FASTGPT_SERVER_HOST", "fromenv")
    cfg2, _ = load()
    assert cfg2.server.host == "fromenv"
    assert cfg2.server.port == 5000  # not overridden by env


def test_api_key_never_in_config_output():
    """API key is excluded from to_dict (never lands in config file)."""
    cfg = Config()
    cfg.server.api_key = "SECRET"
    payload = to_dict(cfg)
    assert "api_key" not in payload["server"]


def test_save_and_reload_roundtrip(tmp_path: Path, monkeypatch):
    path = tmp_path / "nested" / "config.yaml"
    cfg = Config()
    cfg.server.host = "saved.example"
    save(cfg, path)
    assert path.exists()
    loaded_raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded_raw["server"]["host"] == "saved.example"


def test_chat_api_key_from_env(monkeypatch):
    monkeypatch.delenv("FASTGPT_CHAT_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    from fastgptcli.config.settings import chat_api_key

    assert chat_api_key() == ""
    monkeypatch.setenv("OPENCODE_API_KEY", "opencode-key")
    assert chat_api_key() == "opencode-key"
    monkeypatch.setenv("FASTGPT_CHAT_API_KEY", "fastgpt-key")
    assert chat_api_key() == "fastgpt-key"
