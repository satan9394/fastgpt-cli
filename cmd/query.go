package cmd

import (
	"fmt"

	"github.com/satan9394/fastgpt-cli/internal/service"
	"github.com/spf13/cobra"
)

// newQueryCmd 返回 query 命令：查询知识库。
func newQueryCmd() *cobra.Command {
	var kbID, question string
	var topK int

	cmd := &cobra.Command{
		Use:   "query",
		Short: "查询知识库",
		Long:  `对指定知识库发起语义检索查询，返回命中文档片段。`,
		RunE: func(cmd *cobra.Command, args []string) error {
			svc := service.NewQueryService(nil)
			results, err := svc.Query(kbID, question, topK)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "查询 %q 返回 %d 条结果（占位逻辑）\n", question, len(results))
			for _, r := range results {
				fmt.Fprintf(cmd.OutOrStdout(), "  - [score=%.3f] %s\n", r.Score, r.Snippet)
			}
			return nil
		},
	}

	cmd.Flags().StringVar(&kbID, "kb", "", "待查询知识库 ID（必填）")
	cmd.Flags().StringVar(&question, "query", "", "查询问题（必填）")
	cmd.Flags().IntVar(&topK, "top-k", 5, "返回结果数量")
	_ = cmd.MarkFlagRequired("kb")
	_ = cmd.MarkFlagRequired("query")

	return cmd
}
