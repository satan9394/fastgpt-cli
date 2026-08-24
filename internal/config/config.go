// Package config 提供配置文件读写、环境变量覆盖与默认值管理。
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Config 是 CLI 的运行时配置根结构。
type Config struct {
	Server   ServerConfig   `yaml:"server"`
	Defaults DefaultsConfig `yaml:"defaults"`
	Logging  LoggingConfig  `yaml:"logging"`
	Chat     ChatConfig     `yaml:"chat"`
}

// ChatConfig 描述 OpenAI 兼容对话补全端点（如 OpenCode Go）。
// api_key 不落在配置文件——始终从环境变量 OPENCODE_API_KEY 读取（见 ClientAPIKey）。
type ChatConfig struct {
	BaseURL string `yaml:"base_url"`
	Model   string `yaml:"model"`
	APIKey  string `yaml:"-"` // 不入配置文件：运行时从 OPENCODE_API_KEY 注入
}

// ServerConfig 描述 FastGPT 服务端连接参数。
type ServerConfig struct {
	Host   string `yaml:"host"`
	Port   int    `yaml:"port"`
	APIKey string `yaml:"api_key"`
}

// DefaultsConfig 描述默认参数。
type DefaultsConfig struct {
	Model        string `yaml:"model"`
	ChunkSize    int    `yaml:"chunk_size"`
	ChunkOverlap int    `yaml:"chunk_overlap"`
}

// LoggingConfig 描述日志配置。
type LoggingConfig struct {
	Level string `yaml:"level"`
	File  string `yaml:"file"`
}

// Default 返回一份内置默认配置。默认值优先级最低，随后是配置文件、环境变量、命令行标志。
func Default() Config {
	return Config{
		Server: ServerConfig{
			Host: "localhost",
			Port: 3000,
		},
		Defaults: DefaultsConfig{
			Model:        "text-embedding-3-small",
			ChunkSize:    500,
			ChunkOverlap: 50,
		},
		Logging: LoggingConfig{
			Level: "info",
			File:  "",
		},
		Chat: ChatConfig{
			BaseURL: "https://opencode.ai/zen/go/v1", // OpenCode Go
			Model:   "mimo-v2.5",
		},
	}
}

// ChatAPIKey 返回对话补全用的 API Key，仅从环境变量读取，不落配置/档案。
// 读取顺序：FASTGPT_CHAT_API_KEY，其次 OPENCODE_API_KEY；未设则返回空串，由调用方决定是否报错。
func ChatAPIKey() string {
	if v := os.Getenv("FASTGPT_CHAT_API_KEY"); v != "" {
		return v
	}
	return os.Getenv("OPENCODE_API_KEY")
}

// DefaultsPath 返回默认配置文件路径（~/.fastgpt-cli/config.yaml）。
// 支持 FASTGPT_CONFIG_DIR 环境变量覆盖目录。
func DefaultsPath() (string, error) {
	if dir := os.Getenv("FASTGPT_CONFIG_DIR"); dir != "" {
		return filepath.Join(dir, "config.yaml"), nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("无法定位用户主目录: %w", err)
	}
	return filepath.Join(home, ".fastgpt-cli", "config.yaml"), nil
}

// Load 按优先级合并配置：默认值 < 配置文件 < 环境变量。
// explicitPath 非空时读取该文件；为空则用 DefaultsPath 且文件不存在时不报错（保留默认值）。
func Load(explicitPath string) (Config, string, error) {
	cfg := Default()
	path := explicitPath
	if path == "" {
		def, err := DefaultsPath()
		if err != nil {
			return cfg, "", err
		}
		path = def
	}

	data, err := os.ReadFile(path)
	switch {
	case err == nil:
		if perr := parseYAML(data, &cfg); perr != nil {
			return cfg, path, fmt.Errorf("解析配置文件 %s 失败: %w", path, perr)
		}
	case os.IsNotExist(err):
		// 文件尚不存在：保留默认值。显式指定的路径也可能尚未生成，交由调用方决定是否写回。
		return applyEnv(cfg), path, nil
	default:
		return cfg, path, fmt.Errorf("读取配置文件 %s 失败: %w", path, err)
	}

	return applyEnv(cfg), path, nil
}

// applyEnv 用环境变量覆盖配置。约定前缀 FASTGPT_，路径用下划线分隔。
// 例：FASTGPT_SERVER_HOST、FASTGPT_SERVER_PORT、FASTGPT_SERVER_API_KEY、
//     FASTGPT_DEFAULTS_MODEL、FASTGPT_LOGGING_LEVEL。
func applyEnv(cfg Config) Config {
	setStr := func(env string, dst *string) {
		if v, ok := os.LookupEnv(env); ok {
			*dst = v
		}
	}
	setInt := func(env string, dst *int) {
		if v, ok := os.LookupEnv(env); ok {
			if n, err := strconv.Atoi(v); err == nil {
				*dst = n
			}
		}
	}

	setStr("FASTGPT_SERVER_HOST", &cfg.Server.Host)
	setInt("FASTGPT_SERVER_PORT", &cfg.Server.Port)
	setStr("FASTGPT_SERVER_API_KEY", &cfg.Server.APIKey)
	setStr("FASTGPT_DEFAULTS_MODEL", &cfg.Defaults.Model)
	setInt("FASTGPT_DEFAULTS_CHUNK_SIZE", &cfg.Defaults.ChunkSize)
	setInt("FASTGPT_DEFAULTS_CHUNK_OVERLAP", &cfg.Defaults.ChunkOverlap)
	setStr("FASTGPT_LOGGING_LEVEL", &cfg.Logging.Level)
	setStr("FASTGPT_LOGGING_FILE", &cfg.Logging.File)
	setStr("FASTGPT_CHAT_BASE_URL", &cfg.Chat.BaseURL)
	setStr("FASTGPT_CHAT_MODEL", &cfg.Chat.Model)

	return cfg
}

// MarshalYAML 序列化为 YAML 文本（供 config set / 备份导出）。
func (c Config) MarshalYAML() ([]byte, error) {
	return marshalYAML(c)
}

// ServerAddr 返回 host:port 组合，供 client 连接使用。
func (c Config) ServerAddr() string {
	return strings.TrimRight(c.Server.Host, "/") + ":" + strconv.Itoa(c.Server.Port)
}
