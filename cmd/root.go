// Package cmd 定义 FastGPT CLI 的 Cobra 命令树。
package cmd

import (
	"fmt"
	"os"

	"github.com/satan9394/fastgpt-cli/internal/config"
	"github.com/spf13/cobra"
)

// version 通过 -ldflags 注入，开发阶段保留默认值。
var version = "0.1.0-dev"

// rootCmd 是命令树根。
var rootCmd = &cobra.Command{
	Use:   "fastgpt",
	Short: "FastGPT CLI - 知识库管理工具",
	Long: `FastGPT CLI 是一个命令行工具，用于管理 FastGPT 知识库。

支持创建知识库、上传文档、智能查询等功能，覆盖知识库全生命周期管理。`,
	Version: version,
}

// Execute 执行根命令，错误时打印并退出。
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	// 全局持久标志：所有子命令共享。
	rootCmd.PersistentFlags().StringP("config", "c", "", "配置文件路径（默认 ~/.fastgpt-cli/config.yaml）")
	rootCmd.PersistentFlags().StringP("output", "o", "text", "输出格式：text | json | table")
	rootCmd.PersistentFlags().BoolP("verbose", "v", false, "详细输出（调试日志）")

	// 注册核心子命令。
	rootCmd.AddCommand(newCreateKBCmd())
	rootCmd.AddCommand(newUploadDocCmd())
	rootCmd.AddCommand(newQueryCmd())
	rootCmd.AddCommand(newConfigCmd())
	rootCmd.AddCommand(newChatCmd())
}

// loadEffectiveConfig 读取并解析配置，供各命令按需使用。
// 显式 --config 优先，否则用默认路径。
func loadEffectiveConfig(cmd *cobra.Command) (config.Config, string, error) {
	explicit, _ := cmd.Flags().GetString("config")
	return config.Load(explicit)
}
