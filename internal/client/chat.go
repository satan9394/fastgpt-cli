package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// ChatClient 是 OpenAI 兼容 Chat 补全的 HTTP 客户端。
// API Key 在构造时传入（由 cmd 层从环境变量读取），绝不落日志/档案。
type ChatClient struct {
	baseURL   string
	model     string
	apiKey    string
	http      *http.Client
	timeout   time.Duration
	maxRetry  int
}

// NewChatClient 构造客户端。
// baseURL 例如 https://opencode.ai/zen/go/v1；apiKey 为空时不带 Authorization 头。
func NewChatClient(baseURL, model, apiKey string) *ChatClient {
	return &ChatClient{
		baseURL:  strings.TrimRight(baseURL, "/"),
		model:    model,
		apiKey:   apiKey,
		http:     &http.Client{Timeout: 60 * time.Second},
		timeout:  60 * time.Second,
		maxRetry: 2,
	}
}

// Chat 调用 /chat/completions 并返回解析后的响应。
// 使用 context.Background；如需取消可扩展带 ctx 的变体。
func (c *ChatClient) Chat(req ChatRequest) (ChatResponse, error) {
	if req.Model == "" {
		req.Model = c.model
	}
	if len(req.Messages) == 0 {
		return ChatResponse{}, fmt.Errorf("messages 不能为空")
	}
	body, err := json.Marshal(req)
	if err != nil {
		return ChatResponse{}, fmt.Errorf("序列化请求失败: %w", err)
	}

	endpoint := c.baseURL + "/chat/completions"
	resp, err := c.doWithRetry(endpoint, body)
	if err != nil {
		return ChatResponse{}, err
	}

	var out ChatResponse
	if err := json.Unmarshal(resp, &out); err != nil {
		return ChatResponse{}, fmt.Errorf("解析响应失败: %w", err)
	}
	if out.Error != nil && out.Error.Message != "" {
		return out, fmt.Errorf("服务端错误: %s", out.Error.Message)
	}
	if len(out.Choices) == 0 {
		return out, fmt.Errorf("响应无 choices 字段")
	}
	return out, nil
}

func (c *ChatClient) doWithRetry(endpoint string, body []byte) ([]byte, error) {
	var lastErr error
	for attempt := 0; attempt <= c.maxRetry; attempt++ {
		if attempt > 0 {
			time.Sleep(time.Duration(attempt) * 500 * time.Millisecond)
		}
		data, err := c.doOnce(endpoint, body)
		if err == nil {
			return data, nil
		}
		lastErr = err
		// 仅对 429 / 5xx 重试；4xx 客户端错误不重试（避免浪费）。
		if he, ok := err.(*httpStatusError); ok && he.code < 500 && he.code != 429 {
			return nil, lastErr
		}
	}
	return nil, lastErr
}

type httpStatusError struct{ code int }

func (e *httpStatusError) Error() string { return fmt.Sprintf("HTTP %d", e.code) }

func (c *ChatClient) doOnce(endpoint string, body []byte) ([]byte, error) {
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求失败: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}
	if resp.StatusCode >= 400 {
		return nil, &httpStatusError{code: resp.StatusCode}
	}
	return data, nil
}
