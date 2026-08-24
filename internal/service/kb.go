// Package service 承载业务逻辑层（Service），Command → Service → Client 分层之一。
package service

import "github.com/satan9394/fastgpt-cli/internal/client"

// KBService 提供知识库相关业务操作。
type KBService struct {
	client client.Client
}

// NewKBService 构造知识库服务。
func NewKBService(c client.Client) *KBService {
	return &KBService{client: c}
}

// Create 创建知识库（Day 1-2 为占位逻辑，后续接入 FastGPT API）。
func (s *KBService) Create(name, model, desc string) (string, error) {
	// TODO(Day 5-7): 调用 FastGPT API 创建知识库。
	return "kb-placeholder-id", nil
}
