package config

import (
	"fmt"
	"strconv"
)

// FieldPointer 描述一个可被 config set 修改的字段。
// 通过一个指向 Config 子字段的可写引用暴露，供 applyField 使用。
type FieldPointer interface {
	set(s string) error
}

type strField struct{ dst *string }

func (f strField) set(s string) error { *f.dst = s; return nil }

type intField struct{ dst *int }

func (f intField) set(s string) error {
	n, err := strconv.Atoi(s)
	if err != nil {
		return fmt.Errorf("期望整数，得到 %q: %w", s, err)
	}
	*f.dst = n
	return nil
}

// ApplyField 按点路径把 string 值写入 cfg。整数字段自动转换。
// 支持：server.host / server.port / server.api_key /
//       defaults.model / defaults.chunk_size / defaults.chunk_overlap /
//       logging.level / logging.file
func ApplyField(cfg *Config, key, value string) error {
	var f FieldPointer
	switch key {
	case "server.host":
		f = strField{&cfg.Server.Host}
	case "server.port":
		f = intField{&cfg.Server.Port}
	case "server.api_key":
		f = strField{&cfg.Server.APIKey}
	case "defaults.model":
		f = strField{&cfg.Defaults.Model}
	case "defaults.chunk_size":
		f = intField{&cfg.Defaults.ChunkSize}
	case "defaults.chunk_overlap":
		f = intField{&cfg.Defaults.ChunkOverlap}
	case "logging.level":
		f = strField{&cfg.Logging.Level}
	case "logging.file":
		f = strField{&cfg.Logging.File}
	case "chat.base_url":
		f = strField{&cfg.Chat.BaseURL}
	case "chat.model":
		f = strField{&cfg.Chat.Model}
	default:
		return fmt.Errorf("未知配置项 %q（可用: server.host/server.port/server.api_key/defaults.model/defaults.chunk_size/defaults.chunk_overlap/logging.level/logging.file/chat.base_url/chat.model）", key)
	}
	return f.set(value)
}
