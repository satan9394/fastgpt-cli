package service

import "github.com/satan9394/fastgpt-cli/internal/client"

// ChatService 提供与 LLM 对话的业务操作。
type ChatService struct {
	client client.Client
}

// NewChatService 构造对话服务。
func NewChatService(c client.Client) *ChatService {
	return &ChatService{client: c}
}

// ChatOptions 携带可选对话参数；零值表示不发送给后端。
type ChatOptions struct {
	MaxTokens   int
	Temperature float64
}

// Chat 发送用户消息并返回助手回复。
func (s *ChatService) Chat(question string, opts ChatOptions) (string, error) {
	if s.client == nil {
		return "", errNilClient
	}
	req := client.ChatRequest{
		Messages: []client.ChatMessage{{Role: "user", Content: question}},
	}
	if opts.MaxTokens > 0 {
		req.MaxTokens = opts.MaxTokens
	}
	if opts.Temperature != 0 {
		req.Temperature = opts.Temperature
	}
	resp, err := s.client.Chat(req)
	if err != nil {
		return "", err
	}
	if len(resp.Choices) == 0 {
		return "", errEmptyChoices
	}
	return resp.Choices[0].Message.Content, nil
}
