package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDefault(t *testing.T) {
	cfg := Default()
	if cfg.Server.Host != "localhost" || cfg.Server.Port != 3000 {
		t.Errorf("默认服务端配置不符: %+v", cfg.Server)
	}
	if cfg.Defaults.Model != "text-embedding-3-small" {
		t.Errorf("默认模型不符: %q", cfg.Defaults.Model)
	}
	if cfg.Defaults.ChunkSize != 500 || cfg.Defaults.ChunkOverlap != 50 {
		t.Errorf("默认分块参数不符: %+v", cfg.Defaults)
	}
	if cfg.Chat.BaseURL != "https://opencode.ai/zen/go/v1" {
		t.Errorf("默认 chat base_url 不符: %q", cfg.Chat.BaseURL)
	}
	if cfg.Chat.Model != "mimo-v2.5" {
		t.Errorf("默认 chat model 不符: %q", cfg.Chat.Model)
	}
}

func TestChatAPIKeyFromEnv(t *testing.T) {
	_ = os.Unsetenv("FASTGPT_CHAT_API_KEY")
	_ = os.Setenv("OPENCODE_API_KEY", "sk-env-test")
	defer os.Unsetenv("OPENCODE_API_KEY")
	if got := ChatAPIKey(); got != "sk-env-test" {
		t.Errorf("应从 OPENCODE_API_KEY 读取: %q", got)
	}

	_ = os.Setenv("FASTGPT_CHAT_API_KEY", "sk-pref")
	if got := ChatAPIKey(); got != "sk-pref" {
		t.Errorf("FASTGPT_CHAT_API_KEY 应优先: %q", got)
	}
	_ = os.Unsetenv("FASTGPT_CHAT_API_KEY")

	_ = os.Unsetenv("OPENCODE_API_KEY")
	if got := ChatAPIKey(); got != "" {
		t.Errorf("未设环境变量应返回空: %q", got)
	}
}

func TestLoadFromFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	yaml := "server:\n  host: myhost\n  port: 8080\ndefaults:\n  model: m2\n"
	if err := os.WriteFile(path, []byte(yaml), 0o600); err != nil {
		t.Fatal(err)
	}

	cfg, gotPath, err := Load(path)
	if err != nil {
		t.Fatalf("Load 出错: %v", err)
	}
	if gotPath != path {
		t.Errorf("返回路径不符: %q", gotPath)
	}
	if cfg.Server.Host != "myhost" || cfg.Server.Port != 8080 {
		t.Errorf("文件解析后服务端配置不符: %+v", cfg.Server)
	}
	if cfg.Defaults.Model != "m2" {
		t.Errorf("文件解析后默认模型不符: %q", cfg.Defaults.Model)
	}
	// 未写文件的字段应保留默认值。
	if cfg.Defaults.ChunkSize != 500 {
		t.Errorf("未指定字段应保留默认值: %d", cfg.Defaults.ChunkSize)
	}
}

func TestLoadMissingFileUsesDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nope.yaml")
	cfg, _, err := Load(path)
	if err != nil {
		t.Fatalf("缺失文件不应报错: %v", err)
	}
	if cfg.Server.Host != "localhost" {
		t.Errorf("缺失文件应回落到默认值: %+v", cfg.Server)
	}
}

func TestEnvOverride(t *testing.T) {
	_ = os.Setenv("FASTGPT_SERVER_HOST", "envhost2")
	defer os.Unsetenv("FASTGPT_SERVER_HOST")

	cfg := applyEnv(Default())
	if cfg.Server.Host != "envhost2" {
		t.Errorf("环境变量未覆盖 host: %q", cfg.Server.Host)
	}
}

func TestDefaultsPathEnvOverride(t *testing.T) {
	_ = os.Setenv("FASTGPT_CONFIG_DIR", string(filepath.Separator)+"tmp"+string(filepath.Separator)+"fgdir")
	defer os.Unsetenv("FASTGPT_CONFIG_DIR")
	p, err := DefaultsPath()
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(p, string(filepath.Separator)+"config.yaml") {
		t.Errorf("DefaultsPath 应指向 config.yaml: %q", p)
	}
}

func TestApplyField(t *testing.T) {
	cfg := Default()
	if err := ApplyField(&cfg, "server.host", "x.example"); err != nil {
		t.Fatal(err)
	}
	if cfg.Server.Host != "x.example" {
		t.Errorf("ApplyField 未写入 host: %q", cfg.Server.Host)
	}
	if err := ApplyField(&cfg, "server.port", "9000"); err != nil {
		t.Fatal(err)
	}
	if cfg.Server.Port != 9000 {
		t.Errorf("ApplyField 未写入 port: %d", cfg.Server.Port)
	}
	if err := ApplyField(&cfg, "server.port", "abc"); err == nil {
		t.Error("非法整数应报错")
	}
	if err := ApplyField(&cfg, "nope.key", "1"); err == nil {
		t.Error("未知 key 应报错")
	}
}

func TestSaveRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "c", "config.yaml")
	cfg := Default()
	cfg.Server.Host = "round.example"
	if err := Save(cfg, path); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("保存后文件不存在: %v", err)
	}
	got, _, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got.Server.Host != "round.example" {
		t.Errorf("回读 host 不符: %q", got.Server.Host)
	}
	if !strings.Contains(mustYAML(cfg), "round.example") {
		t.Error("MarshalYAML 未包含写入值")
	}
}

func mustYAML(cfg Config) string {
	b, err := cfg.MarshalYAML()
	if err != nil {
		return ""
	}
	return string(b)
}

func TestServerAddr(t *testing.T) {
	cfg := Default()
	if cfg.ServerAddr() != "localhost:3000" {
		t.Errorf("ServerAddr 不符: %q", cfg.ServerAddr())
	}
}
