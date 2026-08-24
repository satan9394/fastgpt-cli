package config

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// parseYAML 把 YAML 字节解析进 cfg。用的是 yaml.v3 的 Unmarshal，字段映射走 yaml tag。
func parseYAML(data []byte, cfg *Config) error {
	return yaml.Unmarshal(data, cfg)
}

// marshalYAML 序列化 Config 为带缩进的 YAML 字节。
func marshalYAML(cfg Config) ([]byte, error) {
	return yaml.Marshal(cfg)
}

// Save 把配置写回指定路径，自动创建父目录。原子写：临时文件 + rename，避免写一半损坏配置。
func Save(cfg Config, path string) error {
	data, err := marshalYAML(cfg)
	if err != nil {
		return err
	}
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp) // 清理临时文件，保留原文件
		return err
	}
	return nil
}
