// Package client 封装对 FastGPT Server 与外部 LLM 端点的 API 访问（gRPC/REST）。
package client

// Client 定义对外部服务的访问接口，供 Service 层依赖注入。
// 暂定收敛为 OpenAI 兼容的 Chat 补全；后续接入 FastGPT 具体 API 时再扩展。
type Client interface {
	// Chat 调用 OpenAI 兼容的 /chat/completions 端点，返回助手回复内容。
	Chat(req ChatRequest) (ChatResponse, error)
}
