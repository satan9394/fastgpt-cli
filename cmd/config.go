package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/satan9394/fastgpt-cli/internal/config"
	"github.com/spf13/cobra"
)

// newConfigCmd 返回 config 命令：配置管理。
func newConfigCmd() *cobra.Command {
	root := &cobra.Command{
		Use:   "config",
		Short: "配置管理",
		Long: `查看、修改 FastGPT CLI 配置。

配置来源优先级：命令行标志 > 环境变量(FASTGPT_*) > 配置文件 > 内置默认值。`,
	}

	root.AddCommand(
		newConfigShowCmd(),
		newConfigPathCmd(),
		newConfigSetCmd(),
		newConfigInitCmd(),
	)

	return root
}

// effectiveCfg 从 root 的 --config 标志加载并解析配置。
func effectiveCfg(cmd *cobra.Command) (config.Config, string, error) {
	return loadEffectiveConfig(cmd)
}

// newConfigShowCmd 打印解析后的完整配置。
func newConfigShowCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "show",
		Short: "显示当前生效配置",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, path, err := effectiveCfg(cmd)
			if err != nil {
				return err
			}
			outFmt, _ := cmd.Flags().GetString("output")
			switch outFmt {
			case "json":
				data, _ := json.MarshalIndent(cfg, "", "  ")
				fmt.Fprintln(cmd.OutOrStdout(), string(data))
			default:
				y, _ := cfg.MarshalYAML()
				fmt.Fprintf(cmd.OutOrStdout(), "配置文件: %s\n\n%s", path, string(y))
			}
			return nil
		},
	}
}

// newConfigPathCmd 打印配置文件路径。
func newConfigPathCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "path",
		Short: "显示配置文件路径",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			_, path, err := effectiveCfg(cmd)
			if err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), path)
			return nil
		},
	}
}

// newConfigInitCmd 写入一份默认配置文件到目标路径。
func newConfigInitCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "init",
		Short: "生成默认配置文件",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			_, path, err := effectiveCfg(cmd)
			if err != nil {
				return err
			}
			if err := config.Save(config.Default(), path); err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "已生成默认配置: %s\n", path)
			return nil
		},
	}
}

// newConfigSetCmd 把 key=value 写入配置文件。
// key 支持点路径，如 server.host / defaults.model，只覆盖对应字段。
func newConfigSetCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "set <key=value>",
		Short: "设置配置项并写回配置文件",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			key, value, ok := splitKV(args[0])
			if !ok {
				return fmt.Errorf("参数格式应为 key=value")
			}
			cfg, path, err := effectiveCfg(cmd)
			if err != nil {
				return err
			}
			if err := config.ApplyField(&cfg, key, value); err != nil {
				return err
			}
			if err := config.Save(cfg, path); err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "已写入 %s=%s → %s\n", key, value, path)
			return nil
		},
	}
}

func splitKV(s string) (string, string, bool) {
	for i := 0; i < len(s); i++ {
		if s[i] == '=' {
			return s[:i], s[i+1:], true
		}
	}
	return "", "", false
}
