package cmd

import (
	"fmt"
	"strings"

	"github.com/satan9394/fastgpt-cli/internal/client"
	"github.com/satan9394/fastgpt-cli/internal/config"
	"github.com/satan9394/fastgpt-cli/internal/service"
	"github.com/spf13/cobra"
)

// newChatCmd 返回 chat 命令：通过 OpenAI 兼容的对话补全端点与 LLM 对话（默认 mimo-v2.5）。
func newChatCmd() *cobra.Command {
	var prompt, baseURL, model, apiKey string
	var maxTokens int
	var temperature float64

	cmd := &cobra.Command{
		Use:   "chat <问题>",
		Short: "与 LLM 对话（OpenAI 兼容 chat completions）",
		Long: `调用 OpenAI 兼容的 /chat/completions 端点与模型对话。
默认 Endpoint 为 OpenCode Go（mimo-v2.5）。API Key 从环境变量读取：
  FASTGPT_CHAT_API_KEY 或 OPENCODE_API_KEY。
安全提醒：密钥只从环境变量（或 --api-key）读取，运行时使用，不写入配置或日志。`,
		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if prompt == "" && len(args) > 0 {
				prompt = strings.Join(args, " ")
			}
			if strings.TrimSpace(prompt) == "" {
				return fmt.Errorf("需要提供问题（位置参数或 --prompt）")
			}

			cfg, _, err := loadEffectiveConfig(cmd)
			if err != nil {
				return err
			}
			if baseURL == "" {
				baseURL = cfg.Chat.BaseURL
			}
			if model == "" {
				model = cfg.Chat.Model
			}
			if apiKey == "" {
				apiKey = config.ChatAPIKey()
			}
			if apiKey == "" {
				return fmt.Errorf("未设置 API Key：请设环境变量 FASTGPT_CHAT_API_KEY 或 OPENCODE_API_KEY")
			}

			c := client.NewChatClient(baseURL, model, apiKey)
			svc := service.NewChatService(c)
			reply, err := svc.Chat(prompt, service.ChatOptions{MaxTokens: maxTokens, Temperature: temperature})
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "%s\n", reply)
			return nil
		},
	}

	cmd.Flags().StringVar(&prompt, "prompt", "", "对话内容（也可用位置参数）")
	cmd.Flags().StringVar(&baseURL, "base-url", "", "OpenAI 兼容端点（默认从配置读，标准为 https://opencode.ai/zen/go/v1）")
	cmd.Flags().StringVar(&model, "model", "", "模型（默认从配置读，标准为 mimo-v2.5）")
	cmd.Flags().StringVar(&apiKey, "api-key", "", "API Key（推荐用环境变量，此标志仅用于临时覆盖，不持久化）")
	cmd.Flags().IntVar(&maxTokens, "max-tokens", 0, "最大生成 token 数（0=后端默认）")
	cmd.Flags().Float64Var(&temperature, "temperature", 0, "采样温度（0=不发送，交后端默认）")

	return cmd
}
