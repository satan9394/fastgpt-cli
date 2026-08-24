package cmd

import (
	"fmt"

	"github.com/satan9394/fastgpt-cli/internal/service"
	"github.com/spf13/cobra"
)

// newCreateKBCmd 返回 create-kb 命令：创建新知识库。
func newCreateKBCmd() *cobra.Command {
	var name, model, desc string

	cmd := &cobra.Command{
		Use:   "create-kb",
		Short: "创建新知识库",
		Long:  `创建新的 FastGPT 知识库，并指定嵌入模型与描述。`,
		RunE: func(cmd *cobra.Command, args []string) error {
			// 未显式指定 --model 时，回落到配置的默认模型。
			if !cmd.Flags().Changed("model") {
				cfg, _, err := loadEffectiveConfig(cmd)
				if err != nil {
					return err
				}
				model = cfg.Defaults.Model
			}
			svc := service.NewKBService(nil)
			kbID, err := svc.Create(name, model, desc)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "知识库已创建 id=%s name=%q model=%q\n", kbID, name, model)
			return nil
		},
	}

	cmd.Flags().StringVar(&name, "name", "", "知识库名称（必填）")
	cmd.Flags().StringVar(&model, "model", "text-embedding-3-small", "嵌入模型")
	cmd.Flags().StringVar(&desc, "desc", "", "知识库描述")
	_ = cmd.MarkFlagRequired("name")

	return cmd
}
