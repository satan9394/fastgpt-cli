package client

// ChatMessage 是一条对话消息，role 取 user / assistant / system / developer。
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatRequest 是 OpenAI 兼容 /chat/completions 的请求体（仅用本项目所需字段）。
type ChatRequest struct {
	Model    string        `json:"model"`
	Messages []ChatMessage `json:"messages"`
	// MaxTokens 可选；为 0 时不发送该字段，交后端默认。
	MaxTokens int `json:"max_tokens,omitempty"`
	// Temperature 可选；为 0 时不发送。
	Temperature float64 `json:"temperature,omitempty"`
}

// ChatResponse 是 OpenAI 兼容响应体。
type ChatResponse struct {
	ID      string         `json:"id"`
	Choices []ChatChoice   `json:"choices"`
	Usage   *ChatUsage     `json:"usage,omitempty"`
	Error   *APIError      `json:"error,omitempty"`
}

// ChatChoice 表示一次生成候选。
type ChatChoice struct {
	Index        int         `json:"index"`
	Message      ChatMessage `json:"message"`
	FinishReason string      `json:"finish_reason"`
}

// ChatUsage 统计 token 用量。
type ChatUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// APIError 是服务端返回的错误对象（status + message，message 不含密钥）。
type APIError struct {
	Message string `json:"message"`
	Type    string `json:"type"`
}
