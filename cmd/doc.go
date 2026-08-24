package cmd

import (
	"fmt"

	"github.com/satan9394/fastgpt-cli/internal/service"
	"github.com/spf13/cobra"
)

// newUploadDocCmd 返回 upload-doc 命令：上传文档到知识库。
func newUploadDocCmd() *cobra.Command {
	var kbID, path string
	var recursive bool

	cmd := &cobra.Command{
		Use:   "upload-doc",
		Short: "上传文档到知识库",
		Long:  `将一个或多个文档上传到指定知识库，支持递归目录。`,
		RunE: func(cmd *cobra.Command, args []string) error {
			svc := service.NewDocService(nil)
			n, err := svc.Upload(kbID, path, recursive)
			if err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "已上传 %d 个文档到知识库 %q\n", n, kbID)
			return nil
		},
	}

	cmd.Flags().StringVar(&kbID, "kb", "", "目标知识库 ID（必填）")
	cmd.Flags().StringVar(&path, "path", "", "文档路径或目录（必填）")
	cmd.Flags().BoolVar(&recursive, "recursive", false, "递归处理目录")
	_ = cmd.MarkFlagRequired("kb")
	_ = cmd.MarkFlagRequired("path")

	return cmd
}
