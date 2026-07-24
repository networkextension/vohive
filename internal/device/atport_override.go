package device

import (
	"os"
	"strings"

	"github.com/iniwex5/vohive/internal/config"
	"github.com/iniwex5/vohive/pkg/logger"
)

// applyATPortOverride 允许在没有内核串口枚举的平台（如 macOS，模组的 class-0xFF
// AT 口不会生成 /dev/tty*）通过环境变量硬指定设备的 AT 口路径，从而跳过依赖
// Linux /sys / ttyUSB 扫描的硬件发现。
//
// 查找顺序：VOHIVE_AT_PORT_<ID> 优先，回退到全局 VOHIVE_AT_PORT。
// 仅在 devCfg.ATPort 尚未解析时生效；一旦命中即同时填充 ManagePort，使
// AddWorkerFromConfig 的非 QMI 分支绕过发现直接用该端口打开 AT 串口
// （典型场景：把 USB AT 接口桥接成一个 PTY，再把该 PTY 路径喂进来）。
func applyATPortOverride(devCfg config.DeviceConfig) config.DeviceConfig {
	if strings.TrimSpace(devCfg.ATPort) != "" {
		return devCfg
	}
	port := atPortOverrideFor(devCfg.ID)
	if port == "" {
		return devCfg
	}
	devCfg.ATPort = port
	devCfg.ManagePort = port
	logger.Info("使用环境变量指定的 AT 口，跳过硬件发现",
		"device", devCfg.ID,
		"at_port", port)
	return devCfg
}

func atPortOverrideFor(id string) string {
	if id = strings.TrimSpace(id); id != "" {
		if v := strings.TrimSpace(os.Getenv("VOHIVE_AT_PORT_" + id)); v != "" {
			return v
		}
	}
	return strings.TrimSpace(os.Getenv("VOHIVE_AT_PORT"))
}
