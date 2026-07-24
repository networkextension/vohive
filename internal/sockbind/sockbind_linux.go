//go:build linux

package sockbind

import "syscall"

// BindToDevice 把 socket 出站绑定到指定网卡。
func BindToDevice(fd uintptr, iface string) error {
	return syscall.SetsockoptString(int(fd), syscall.SOL_SOCKET, syscall.SO_BINDTODEVICE, iface)
}
