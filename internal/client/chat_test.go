package client

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// newTestServer 起一个假 chat/completions 端点，记录收到的 Authorization 头。
func newTestServer(t *testing.T, status int, body string, captureAuth *string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Errorf("路径不符: %s", r.URL.Path)
		}
		if captureAuth != nil {
			*captureAuth = r.Header.Get("Authorization")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
}

func TestChatSuccess(t *testing.T) {
	resp := ChatResponse{
		ID: "chatcmpl-test",
		Choices: []ChatChoice{{
			Index: 0,
			Message: ChatMessage{
				Role:    "assistant",
				Content: "你好，我在。",
			},
			FinishReason: "stop",
		}},
	}
	encoded, _ := json.Marshal(resp)
	var auth string
	srv := newTestServer(t, 200, string(encoded), &auth)
	defer srv.Close()

	c := NewChatClient(srv.URL, "mimo-v2.5", "sk-test-key")
	got, err := c.Chat(ChatRequest{Messages: []ChatMessage{{Role: "user", Content: "hi"}}})
	if err != nil {
		t.Fatalf("Chat 出错: %v", err)
	}
	if got.Choices[0].Message.Content != "你好，我在。" {
		t.Errorf("reply 不符: %q", got.Choices[0].Message.Content)
	}
	if !strings.Contains(auth, "sk-test-key") {
		t.Errorf("Authorization 未携带密钥: %q", auth)
	}
}

func TestChatModelDefault(t *testing.T) {
	var gotReq string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := make([]byte, r.ContentLength)
		_, _ = r.Body.Read(buf)
		gotReq = string(buf)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"choices":[{"message":{"role":"assistant","content":"ok"}}]}`))
	}))
	defer srv.Close()

	c := NewChatClient(srv.URL, "mimo-v2.5", "k")
	if _, err := c.Chat(ChatRequest{Messages: []ChatMessage{{Role: "user", Content: "x"}}}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(gotReq, `"model":"mimo-v2.5"`) {
		t.Errorf("请求未带默认模型: %s", gotReq)
	}
}

func TestChatMissingMessages(t *testing.T) {
	c := NewChatClient("http://x", "m", "k")
	if _, err := c.Chat(ChatRequest{}); err == nil {
		t.Error("空 messages 应报错")
	}
}

func TestChatServerErrorRetry(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(500)
	}))
	defer srv.Close()

	c := NewChatClient(srv.URL, "m", "k")
	if _, err := c.Chat(ChatRequest{Messages: []ChatMessage{{Role: "user", Content: "x"}}}); err == nil {
		t.Error("5xx 应报错")
	}
	if calls < 2 {
		t.Errorf("5xx 应触发重试，实际调用 %d 次", calls)
	}
}

func TestChatAPIErrorSurface(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"error":{"message":"invalid key"}}`))
	}))
	defer srv.Close()

	c := NewChatClient(srv.URL, "m", "k")
	_, err := c.Chat(ChatRequest{Messages: []ChatMessage{{Role: "user", Content: "x"}}})
	if err == nil || !strings.Contains(err.Error(), "invalid key") {
		t.Errorf("API 错误未透出: %v", err)
	}
}
