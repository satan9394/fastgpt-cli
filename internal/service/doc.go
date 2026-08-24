package service

import "github.com/satan9394/fastgpt-cli/internal/client"

// DocService 提供文档管理相关业务操作。
type DocService struct {
	client client.Client
}

// NewDocService 构造文档服务。
func NewDocService(c client.Client) *DocService {
	return &DocService{client: c}
}

// Upload 上传文档到知识库（Day 1-2 为占位逻辑）。
func (s *DocService) Upload(kbID, path string, recursive bool) (int, error) {
	// TODO(Day 5-7): 实现文档上传与索引重建。
	return 0, nil
}
