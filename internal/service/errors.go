package service

import "errors"

var (
	// errNilClient 客户端未注入时返回。
	errNilClient = errors.New("client 未初始化")
	// errEmptyChoices 服务端未返回任何选项时返回。
	errEmptyChoices = errors.New("服务端未返回 choices")
)
