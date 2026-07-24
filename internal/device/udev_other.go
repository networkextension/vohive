//go:build !linux

package device

// 非 Linux 平台没有 netlink KOBJECT_UEVENT，无法监听内核热插拔事件。
// 提供同签名空壳：设备发现改由静态/轮询路径驱动（见 darwin 静态发现）。

type UdevWatcher struct{}

// NewUdevWatcher 在非 Linux 平台返回空壳监听器。
func NewUdevWatcher(_ *Pool) *UdevWatcher { return &UdevWatcher{} }

func (w *UdevWatcher) Start() {}

func (w *UdevWatcher) Stop() {}
