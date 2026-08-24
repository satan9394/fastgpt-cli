package service

import "github.com/satan9394/fastgpt-cli/internal/client"

// QueryResult 表示一条查询命中的文档片段。
type QueryResult struct {
	Score   float64
	Snippet string
}

// QueryService 提供知识库智能查询业务操作。
type QueryService struct {
	client client.Client
}

// NewQueryService 构造查询服务。
func NewQueryService(c client.Client) *QueryService {
	return &QueryService{client: c}
}

// Query 对知识库执行语义检索（Day 1-2 为占位逻辑，返回空结果）。
func (s *QueryService) Query(kbID, question string, topK int) ([]QueryResult, error) {
	// TODO(Day 5-7): 接入 FastGPT 检索接口。
	return []QueryResult{}, nil
}
