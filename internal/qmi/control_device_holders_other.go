//go:build !linux

package qmicore

// 非 Linux 平台没有 /proc，无法探测谁占用了 QMI 控制口。
// QMI 后端在这些平台本就不是主路径（默认 AT），这里给出保守桩：
// 报告「无占用者」，让上层按无冲突继续。

type qmiControlDeviceHolder struct {
	PID     int
	Command string
}

type qmiControlDeviceHolders struct {
	Holders []qmiControlDeviceHolder
	Unknown bool
}

func (h qmiControlDeviceHolders) onlyQMIProxy() bool {
	return false
}

var detectQMIControlDeviceHolders = func(controlDevice string) (qmiControlDeviceHolders, error) {
	return qmiControlDeviceHolders{}, nil
}
