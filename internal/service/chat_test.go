package service

import (
	"errors"
	"testing"

	"github.com/satan9394/fastgpt-cli/internal/client"
)

// mockChatClient 是 client.Client 的假实现。
type mockChatClient struct {
	reply string
	err   error
	req   client.ChatRequest
}

func (m *mockChatClient) Chat(req client.ChatRequest) (client.ChatResponse, error) {
	m.req = req
	if m.err != nil {
		return client.ChatResponse{}, m.err
	}
	return client.ChatResponse{
		Choices: []client.ChatChoice{{Message: client.ChatMessage{Role: "assistant", Content: m.reply}}},
	}, nil
}

func TestChatServiceSuccess(t *testing.T) {
	m := &mockChatClient{reply: "回复内容"}
	svc := NewChatService(m)
	got, err := svc.Chat("问题", ChatOptions{MaxTokens: 64})
	if err != nil {
		t.Fatal(err)
	}
	if got != "回复内容" {
		t.Errorf("reply 不符: %q", got)
	}
	if len(m.req.Messages) != 1 || m.req.Messages[0].Role != "user" || m.req.Messages[0].Content != "问题" {
		t.Errorf("请求消息不符: %+v", m.req.Messages)
	}
	if m.req.MaxTokens != 64 {
		t.Errorf("MaxTokens 未透传: %d", m.req.MaxTokens)
	}
}

func TestChatServiceNilClient(t *testing.T) {
	svc := NewChatService(nil)
	if _, err := svc.Chat("q", ChatOptions{}); !errors.Is(err, errNilClient) {
		t.Errorf("应返回 errNilClient, got: %v", err)
	}
}

func TestChatServiceClientError(t *testing.T) {
	someErr := errors.New("上游错误")
	m := &mockChatClient{err: someErr}
	svc := NewChatService(m)
	_, err := svc.Chat("q", ChatOptions{})
	if !errors.Is(err, someErr) {
		t.Errorf("应透传上游错误, got: %v", err)
	}
}
