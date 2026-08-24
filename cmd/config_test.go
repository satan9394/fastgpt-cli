package cmd

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"
)

// runForTest 执行 rootCmd 并返回 stdout/err。
func runForTest(t *testing.T, args ...string) (string, error) {
	t.Helper()
	rootCmd.SetArgs(args)
	out := new(bytes.Buffer)
	rootCmd.SetOut(out)
	rootCmd.SetErr(out)
	err := rootCmd.Execute()
	return out.String(), err
}

func TestConfigPathCommand(t *testing.T) {
	out, err := runForTest(t, "config", "path", "--config", filepath.Join(t.TempDir(), "cfg.yaml"))
	if err != nil {
		t.Fatalf("config path 出错: %v", err)
	}
	if !strings.Contains(out, "cfg.yaml") {
		t.Errorf("config path 未输出路径: %q", out)
	}
}

func TestConfigShowJSON(t *testing.T) {
	out, err := runForTest(t, "config", "show", "--output", "json", "--config", filepath.Join(t.TempDir(), "cfg.yaml"))
	if err != nil {
		t.Fatalf("config show 出错: %v", err)
	}
	if !strings.Contains(out, `"Port": 3000`) {
		t.Errorf("config show json 未含默认端口: %q", out)
	}
}

func TestConfigSetAndShow(t *testing.T) {
	cfgPath := filepath.Join(t.TempDir(), "cfg.yaml")
	if _, err := runForTest(t, "config", "set", "defaults.model=unit-embed", "--config", cfgPath); err != nil {
		t.Fatalf("config set 出错: %v", err)
	}
	out, err := runForTest(t, "config", "show", "--config", cfgPath)
	if err != nil {
		t.Fatalf("config show 出错: %v", err)
	}
	if !strings.Contains(out, "unit-embed") {
		t.Errorf("config show 未读到写入值: %q", out)
	}
}

func TestConfigSetUnknownKey(t *testing.T) {
	cfgPath := filepath.Join(t.TempDir(), "cfg.yaml")
	_, err := runForTest(t, "config", "set", "bad.key=1", "--config", cfgPath)
	if err == nil || !strings.Contains(err.Error(), "未知配置项") {
		t.Errorf("未知 key 应报错, got: %v", err)
	}
}

func TestHelpShowsConfig(t *testing.T) {
	out, err := runForTest(t, "--help")
	if err != nil {
		t.Fatalf("--help 出错: %v", err)
	}
	for _, want := range []string{"create-kb", "upload-doc", "query", "config"} {
		if !strings.Contains(out, want) {
			t.Errorf("命令树缺少 %q", want)
		}
	}
}
